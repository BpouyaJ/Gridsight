"""Deterministic checked sample extracts for BI and portfolio consumers."""

from __future__ import annotations

import csv
import json
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy.engine import Connection

from gridsight.database.schema_contract import PROJECT_ROOT
from gridsight.forecasting.contract import sha256_file
from gridsight.reporting.mart_contract import (
    DEFAULT_SOURCE_MANIFEST,
    DEFAULT_VALIDATION_SUMMARY,
    MART_CONTRACTS,
    MartContract,
    build_reporting_mart_contract,
    validate_mart_contracts,
    write_reporting_mart_contract,
)

DEFAULT_SAMPLE_MANIFEST = PROJECT_ROOT / "reports" / "sample_extract_manifest.json"
EXPECTED_SAMPLE_COUNT = 8
EXPECTED_SAMPLE_ROWS = 3_451
ATTRIBUTION = "Bundesnetzagentur | SMARD.de"
_SAFE_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]*$")
_SAFE_QUALIFIED_NAME = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")


@dataclass(frozen=True)
class SampleQuery:
    """Fixed filter and deterministic ordering for one PostgreSQL sample."""

    product_id: str
    where_clause: str
    order_by: tuple[str, ...]


SAMPLE_QUERIES = (
    SampleQuery(
        product_id="hourly_energy",
        where_clause=(
            "calendar_date BETWEEN DATE '2025-01-06' AND DATE '2025-01-12'"
        ),
        order_by=("interval_start_utc",),
    ),
    SampleQuery(
        product_id="hourly_generation_by_technology",
        where_clause=(
            "calendar_date BETWEEN DATE '2025-01-06' AND DATE '2025-01-12'"
        ),
        order_by=("interval_start_utc", "technology_key"),
    ),
    SampleQuery(
        product_id="daily_energy",
        where_clause="calendar_year = 2025",
        order_by=("date_key",),
    ),
    SampleQuery(
        product_id="monthly_energy",
        where_clause="TRUE",
        order_by=("month_key",),
    ),
    SampleQuery(
        product_id="forecast_performance_hourly",
        where_clause=(
            "origin_local_date BETWEEN DATE '2025-01-01' "
            "AND DATE '2025-01-31'"
        ),
        order_by=("forecast_origin_utc", "horizon_step"),
    ),
    SampleQuery(
        product_id="forecast_performance_summary",
        where_clause="TRUE",
        order_by=("forecast_name", "evaluation_scope", "horizon_step"),
    ),
)


def _contract_by_id(product_id: str) -> MartContract:
    return next(
        contract
        for contract in MART_CONTRACTS
        if contract.product_id == product_id
    )


def validate_sample_queries(
    queries: tuple[SampleQuery, ...] = SAMPLE_QUERIES,
) -> None:
    """Reject missing, unsafe, unordered, or non-view sample queries."""
    expected_ids = {
        contract.product_id
        for contract in MART_CONTRACTS
        if contract.source_kind == "postgresql_view"
    }
    observed_ids = [query.product_id for query in queries]
    if len(observed_ids) != len(set(observed_ids)):
        raise ValueError("PostgreSQL sample query IDs must be unique")
    if set(observed_ids) != expected_ids:
        raise ValueError("PostgreSQL sample queries do not match mart products")
    for query in queries:
        contract = _contract_by_id(query.product_id)
        if not _SAFE_QUALIFIED_NAME.fullmatch(contract.source_name):
            raise ValueError(f"Unsafe sample source: {contract.source_name}")
        if (
            not query.where_clause
            or ";" in query.where_clause
            or not query.order_by
        ):
            raise ValueError(f"Unsafe sample query for {query.product_id}")
        if not set(query.order_by).issubset(contract.columns):
            raise ValueError(f"Unknown sample ordering for {query.product_id}")
        if not all(_SAFE_IDENTIFIER.fullmatch(column) for column in query.order_by):
            raise ValueError(f"Unsafe sample ordering for {query.product_id}")


def _sample_sql(query: SampleQuery) -> str:
    contract = _contract_by_id(query.product_id)
    columns = ", ".join(contract.columns)
    ordering = ", ".join(query.order_by)
    return (
        f"SELECT {columns} FROM {contract.source_name} "
        f"WHERE {query.where_clause} ORDER BY {ordering}"
    )


def _read_quality_checks(path: Path) -> pd.DataFrame:
    summary = json.loads(path.read_text(encoding="utf-8"))
    checks = summary.get("checks")
    if (
        summary.get("schema_version") != 1
        or summary.get("status") != "passed"
        or summary.get("check_counts") != {"failed": 0, "passed": 29}
        or not isinstance(checks, list)
        or len(checks) != 29
        or any(check.get("status") != "passed" for check in checks)
    ):
        raise ValueError("Data-quality source is not the passing 29-check gate")
    columns = list(_contract_by_id("data_quality_checks").columns)
    frame = pd.DataFrame(
        (
            {
                "dataset": check["dataset"],
                "check_id": check["check_id"],
                "status": check["status"],
                "expected": check["expected"],
                "observed": check["observed"],
            }
            for check in checks
        ),
        columns=columns,
    )
    return frame.sort_values(["dataset", "check_id"], kind="stable").reset_index(
        drop=True
    )


def _read_source_lineage(path: Path) -> pd.DataFrame:
    contract = _contract_by_id("source_lineage")
    frame = pd.read_csv(path, dtype="string", keep_default_na=False)
    if tuple(frame.columns) != contract.columns:
        raise ValueError("Source-lineage columns changed")
    return frame.sort_values("export_id", kind="stable").reset_index(drop=True)


def build_sample_frames(
    connection: Connection,
    *,
    validation_summary_path: Path = DEFAULT_VALIDATION_SUMMARY,
    source_manifest_path: Path = DEFAULT_SOURCE_MANIFEST,
) -> dict[str, pd.DataFrame]:
    """Read all six SQL and two checked-artifact samples."""
    validate_mart_contracts()
    validate_sample_queries()
    frames: dict[str, pd.DataFrame] = {}
    for query in SAMPLE_QUERIES:
        contract = _contract_by_id(query.product_id)
        rows = connection.exec_driver_sql(_sample_sql(query)).mappings().all()
        frames[query.product_id] = pd.DataFrame(
            rows,
            columns=list(contract.columns),
        )
    frames.update(
        build_checked_sample_frames(
            validation_summary_path=validation_summary_path,
            source_manifest_path=source_manifest_path,
        )
    )
    validate_sample_frames(frames)
    return frames


def build_checked_sample_frames(
    *,
    validation_summary_path: Path = DEFAULT_VALIDATION_SUMMARY,
    source_manifest_path: Path = DEFAULT_SOURCE_MANIFEST,
) -> dict[str, pd.DataFrame]:
    """Build the two non-database checked extracts in contract order."""
    frames = {
        "data_quality_checks": _read_quality_checks(validation_summary_path),
        "source_lineage": _read_source_lineage(source_manifest_path),
    }
    for product_id, frame in frames.items():
        validate_sample_frame(_contract_by_id(product_id), frame)
    return frames


def _date_values(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_datetime(frame[column], errors="raise").dt.date


def _validate_sample_scope(contract: MartContract, frame: pd.DataFrame) -> None:
    product_id = contract.product_id
    if product_id in {"hourly_energy", "hourly_generation_by_technology"}:
        values = _date_values(frame, "calendar_date")
        if values.min() != date(2025, 1, 6) or values.max() != date(2025, 1, 12):
            raise ValueError(f"Date scope changed for {product_id}")
    elif product_id == "daily_energy":
        if set(pd.to_numeric(frame["calendar_year"], errors="raise")) != {2025}:
            raise ValueError("Daily sample must contain only calendar year 2025")
    elif product_id == "monthly_energy":
        month_keys = pd.to_numeric(frame["month_key"], errors="raise")
        expected_months = {
            year * 100 + month
            for year in range(2022, 2026)
            for month in range(1, 13)
        }
        if set(month_keys) != expected_months:
            raise ValueError("Monthly sample scope changed")
    elif product_id == "forecast_performance_hourly":
        values = _date_values(frame, "origin_local_date")
        horizon = pd.to_numeric(frame["horizon_step"], errors="raise")
        horizon_sets = frame.assign(_horizon=horizon).groupby(
            "forecast_origin_utc"
        )["_horizon"].agg(lambda group: set(group))
        if (
            values.min() != date(2025, 1, 1)
            or values.max() != date(2025, 1, 31)
            or len(horizon_sets) != 31
            or any(steps != set(range(1, 25)) for steps in horizon_sets)
        ):
            raise ValueError("Forecast hourly sample scope changed")
    elif product_id == "forecast_performance_summary":
        scopes = set(frame["evaluation_scope"])
        horizons = pd.to_numeric(frame["horizon_step"], errors="raise")
        series_scopes = frame.assign(_horizon=horizons).groupby("forecast_name")
        expected_names = {
            "hist_gradient_boosting_31_leaves",
            "daily_seasonal_naive",
            "weekly_seasonal_naive",
        }
        if (
            scopes != {"overall", "horizon"}
            or set(frame["forecast_name"]) != expected_names
            or any(
                set(group["_horizon"]) != set(range(25))
                for _, group in series_scopes
            )
        ):
            raise ValueError("Forecast summary sample scope changed")
    elif product_id == "data_quality_checks":
        if set(frame["status"]) != {"passed"}:
            raise ValueError("Data-quality sample contains a failed check")
    elif product_id == "source_lineage":
        if set(frame["attribution"]) != {ATTRIBUTION}:
            raise ValueError("Source-lineage attribution changed")


def validate_sample_frame(contract: MartContract, frame: pd.DataFrame) -> None:
    """Verify one sample's exact schema, row count, key, and fixed scope."""
    if tuple(frame.columns) != contract.columns:
        raise ValueError(f"Sample columns changed for {contract.product_id}")
    if len(frame) != contract.sample.expected_rows:
        raise ValueError(f"Sample row count changed for {contract.product_id}")
    key_columns = list(contract.key_columns)
    if frame.loc[:, key_columns].isna().any().any():
        raise ValueError(f"Sample key contains nulls for {contract.product_id}")
    if frame.duplicated(key_columns).any():
        raise ValueError(f"Sample key contains duplicates for {contract.product_id}")
    _validate_sample_scope(contract, frame)


def validate_sample_frames(frames: dict[str, pd.DataFrame]) -> None:
    """Verify the complete ordered eight-product sample bundle."""
    expected_ids = [contract.product_id for contract in MART_CONTRACTS]
    if list(frames) != expected_ids:
        raise ValueError("Sample frame order does not match the mart contract")
    for contract in MART_CONTRACTS:
        validate_sample_frame(contract, frames[contract.product_id])


def _format_csv_value(value: object) -> str | object:
    if value is None or pd.isna(value):
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    return value


def write_sample_csv(frame: pd.DataFrame, path: Path) -> None:
    """Write one deterministic UTF-8 CSV with LF endings."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(frame.columns)
        for row in frame.itertuples(index=False, name=None):
            writer.writerow(_format_csv_value(value) for value in row)


def _sample_record(contract: MartContract, path: Path) -> dict[str, Any]:
    return {
        "product_id": contract.product_id,
        "path": contract.sample.path,
        "sha256": sha256_file(path),
        "rows": contract.sample.expected_rows,
        "columns": list(contract.columns),
        "key_columns": list(contract.key_columns),
        "filter_rule": contract.sample.filter_rule,
        "source_kind": contract.source_kind,
        "source_name": contract.source_name,
    }


def _write_json(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _validate_written_csv(contract: MartContract, path: Path) -> None:
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.reader(file)
        try:
            header = tuple(next(reader))
        except StopIteration as error:
            raise ValueError(f"Published sample is empty: {path.name}") from error
        rows = list(reader)
    if header != contract.columns:
        raise ValueError(f"Published sample header changed: {path.name}")
    if len(rows) != contract.sample.expected_rows:
        raise ValueError(f"Published sample rows changed: {path.name}")
    key_indexes = [header.index(column) for column in contract.key_columns]
    keys = [tuple(row[index] for index in key_indexes) for row in rows]
    if any(not all(key) for key in keys) or len(keys) != len(set(keys)):
        raise ValueError(f"Published sample key is invalid: {path.name}")


def _publish_staged_file(source: Path, target: Path) -> None:
    """Atomically publish bytes while inheriting the destination directory ACL."""
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_target = target.with_name(f".{target.name}.tmp")
    try:
        shutil.copyfile(source, temporary_target)
        temporary_target.replace(target)
    finally:
        temporary_target.unlink(missing_ok=True)


def publish_sample_bundle(
    frames: dict[str, pd.DataFrame],
    mart_contract: dict[str, Any],
    *,
    project_root: Path = PROJECT_ROOT,
    validation_summary_path: Path = DEFAULT_VALIDATION_SUMMARY,
    source_manifest_path: Path = DEFAULT_SOURCE_MANIFEST,
    reporting_checks: int = 28,
) -> dict[str, Any]:
    """Stage, verify, and publish all samples with the manifest written last."""
    validate_sample_frames(frames)
    with tempfile.TemporaryDirectory(
        prefix=".gridsight-samples-",
        dir=project_root,
    ) as temporary_directory:
        staging_root = Path(temporary_directory)
        staged_contract = staging_root / "reports" / "reporting_mart_contract.json"
        write_reporting_mart_contract(mart_contract, staged_contract)

        for contract in MART_CONTRACTS:
            staged_path = staging_root / contract.sample.path
            write_sample_csv(frames[contract.product_id], staged_path)
            _validate_written_csv(contract, staged_path)

        sample_records = [
            _sample_record(contract, staging_root / contract.sample.path)
            for contract in MART_CONTRACTS
        ]
        manifest = {
            "schema_version": 1,
            "status": "passed",
            "attribution": ATTRIBUTION,
            "sample_count": len(sample_records),
            "sample_rows": sum(record["rows"] for record in sample_records),
            "reporting_reconciliation_checks": reporting_checks,
            "reporting_mart_contract": {
                "path": "reports/reporting_mart_contract.json",
                "sha256": sha256_file(staged_contract),
            },
            "source": {
                "validation_summary": {
                    "path": validation_summary_path.relative_to(
                        project_root
                    ).as_posix(),
                    "sha256": sha256_file(validation_summary_path),
                },
                "source_manifest": {
                    "path": source_manifest_path.relative_to(
                        project_root
                    ).as_posix(),
                    "sha256": sha256_file(source_manifest_path),
                },
            },
            "samples": sample_records,
        }
        if (
            manifest["sample_count"] != EXPECTED_SAMPLE_COUNT
            or manifest["sample_rows"] != EXPECTED_SAMPLE_ROWS
        ):
            raise ValueError("Published sample bundle totals changed")
        staged_manifest = staging_root / "reports" / "sample_extract_manifest.json"
        _write_json(manifest, staged_manifest)

        targets = [
            (
                staging_root / contract.sample.path,
                project_root / contract.sample.path,
            )
            for contract in MART_CONTRACTS
        ]
        contract_target = project_root / "reports" / "reporting_mart_contract.json"
        manifest_target = project_root / "reports" / "sample_extract_manifest.json"
        targets.append((staged_contract, contract_target))
        for source, target in targets:
            _publish_staged_file(source, target)
        _publish_staged_file(staged_manifest, manifest_target)
    validate_published_sample_bundle(
        project_root=project_root,
        manifest_path=manifest_target,
    )
    return manifest


def validate_published_sample_bundle(
    *,
    project_root: Path = PROJECT_ROOT,
    manifest_path: Path = DEFAULT_SAMPLE_MANIFEST,
) -> dict[str, Any]:
    """Verify every published file against the manifest and code contract."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = manifest.get("samples")
    if (
        manifest.get("schema_version") != 1
        or manifest.get("status") != "passed"
        or manifest.get("attribution") != ATTRIBUTION
        or manifest.get("sample_count") != EXPECTED_SAMPLE_COUNT
        or manifest.get("sample_rows") != EXPECTED_SAMPLE_ROWS
        or manifest.get("reporting_reconciliation_checks") != 28
        or not isinstance(records, list)
        or len(records) != EXPECTED_SAMPLE_COUNT
    ):
        raise ValueError("Sample-extract manifest contract changed")
    mart_path = project_root / "reports" / "reporting_mart_contract.json"
    if manifest.get("reporting_mart_contract", {}).get("sha256") != sha256_file(
        mart_path
    ):
        raise ValueError("Sample bundle reporting-contract hash changed")
    tracked_mart = json.loads(mart_path.read_text(encoding="utf-8"))
    if tracked_mart != current_mart_contract():
        raise ValueError("Tracked reporting-mart contract is not current")
    for source_name, expected_relative_path in (
        ("validation_summary", "data/processed/validation_summary.json"),
        ("source_manifest", "data/manifests/smard_source_manifest.csv"),
    ):
        source = manifest.get("source", {}).get(source_name, {})
        source_path = project_root / str(source.get("path", ""))
        if (
            source.get("path") != expected_relative_path
            or source.get("sha256") != sha256_file(source_path)
        ):
            raise ValueError(f"Sample bundle source changed: {source_name}")
    for contract, record in zip(MART_CONTRACTS, records, strict=True):
        path = project_root / contract.sample.path
        if (
            record.get("product_id") != contract.product_id
            or record.get("path") != contract.sample.path
            or record.get("rows") != contract.sample.expected_rows
            or tuple(record.get("columns", ())) != contract.columns
            or tuple(record.get("key_columns", ())) != contract.key_columns
            or record.get("filter_rule") != contract.sample.filter_rule
            or record.get("source_kind") != contract.source_kind
            or record.get("source_name") != contract.source_name
            or record.get("sha256") != sha256_file(path)
        ):
            raise ValueError(
                f"Published sample manifest changed: {contract.product_id}"
            )
        _validate_written_csv(contract, path)
    return manifest


def current_mart_contract() -> dict[str, Any]:
    """Return the deterministic post-Step-7.3 mart contract."""
    return build_reporting_mart_contract()
