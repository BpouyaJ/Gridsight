"""Stable BI/Excel reporting-mart and checked-extract contracts."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from gridsight.database.reporting_contract import (
    REPORTING_SQL_FILES,
    VIEW_CONTRACTS,
)
from gridsight.database.schema_contract import PROJECT_ROOT
from gridsight.forecasting.contract import sha256_file
from gridsight.forecasting.final_evaluation import (
    DEFAULT_FINAL_EVALUATION_SNAPSHOT,
    DEFAULT_FINAL_PREDICTIONS,
    FINAL_PREDICTION_COLUMNS,
)

DEFAULT_REPORTING_MART_CONTRACT = (
    PROJECT_ROOT / "reports" / "reporting_mart_contract.json"
)
DEFAULT_VALIDATION_SUMMARY = (
    PROJECT_ROOT / "data" / "processed" / "validation_summary.json"
)
DEFAULT_SOURCE_MANIFEST = (
    PROJECT_ROOT / "data" / "manifests" / "smard_source_manifest.csv"
)
ALLOWED_UNITS = ("MW", "MWh", "EUR/MWh", "percent", "count")
ALLOWED_CONSUMERS = ("power_bi", "excel_power_query", "portfolio_review")


@dataclass(frozen=True)
class SampleExtractContract:
    """One deterministic, checked, public sample-extract rule."""

    path: str
    filter_rule: str
    expected_rows: int
    implementation_status: str = "planned_step_7_3"


@dataclass(frozen=True)
class MartContract:
    """One consumer-facing dataset with explicit grain, key, and units."""

    product_id: str
    display_name: str
    source_kind: str
    source_name: str
    implementation_status: str
    grain: str
    key_columns: tuple[str, ...]
    columns: tuple[str, ...]
    measures: tuple[tuple[str, str], ...]
    expected_full_rows: int
    consumers: tuple[str, ...]
    sample: SampleExtractContract


def _measure_units(columns: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
    measures = []
    for column in columns:
        if column.endswith("_eur_per_mwh"):
            measures.append((column, "EUR/MWh"))
        elif column.endswith("_mwh"):
            measures.append((column, "MWh"))
        elif column.endswith("_mw"):
            measures.append((column, "MW"))
        elif column.endswith("_percent"):
            measures.append((column, "percent"))
        elif column.endswith("_count") or column == "observations":
            measures.append((column, "count"))
    return tuple(measures)


FORECAST_PERFORMANCE_HOURLY_COLUMNS = (
    "forecast_origin_utc",
    "origin_local_date",
    "information_cutoff_utc",
    "target_start_utc",
    "target_start_local",
    "target_date_key",
    "target_calendar_date",
    "target_calendar_year",
    "target_calendar_quarter",
    "target_month_number",
    "target_month_name",
    "target_weekday_number",
    "target_weekday_name",
    "target_is_weekend",
    "target_hour_key",
    "target_hour_label",
    "horizon_step",
    "actual_grid_load_mw",
    "model_name",
    "model_prediction_mw",
    "model_error_mw",
    "model_absolute_error_mw",
    "daily_naive_prediction_mw",
    "weekly_naive_prediction_mw",
)
FORECAST_PERFORMANCE_SUMMARY_COLUMNS = (
    "forecast_name",
    "forecast_role",
    "evaluation_scope",
    "horizon_step",
    "observations",
    "mae_mw",
    "rmse_mw",
    "mape_percent",
    "improvement_over_weekly_percent",
)
DATA_QUALITY_CHECK_COLUMNS = (
    "dataset",
    "check_id",
    "status",
    "expected",
    "observed",
)
SOURCE_LINEAGE_COLUMNS = (
    "export_id",
    "source_name",
    "source_url",
    "source_category",
    "source_geography",
    "source_resolution",
    "period_start",
    "period_end",
    "downloaded_at_utc",
    "original_filename",
    "local_filename",
    "sha256",
    "licence",
    "attribution",
    "notes",
)


MART_CONTRACTS = (
    MartContract(
        product_id="hourly_energy",
        display_name="Hourly energy and market facts",
        source_kind="postgresql_view",
        source_name="reporting.hourly_energy",
        implementation_status="verified_existing",
        grain=VIEW_CONTRACTS["hourly_energy"].grain,
        key_columns=("interval_start_utc",),
        columns=VIEW_CONTRACTS["hourly_energy"].columns,
        measures=_measure_units(VIEW_CONTRACTS["hourly_energy"].columns),
        expected_full_rows=VIEW_CONTRACTS["hourly_energy"].expected_rows,
        consumers=("power_bi", "portfolio_review"),
        sample=SampleExtractContract(
            path="data/samples/hourly_energy_sample.csv",
            filter_rule=(
                "calendar_date from 2025-01-06 through 2025-01-12 inclusive"
            ),
            expected_rows=168,
        ),
    ),
    MartContract(
        product_id="hourly_generation_by_technology",
        display_name="Hourly generation by technology",
        source_kind="postgresql_view",
        source_name="reporting.hourly_generation_by_technology",
        implementation_status="verified_existing",
        grain=VIEW_CONTRACTS["hourly_generation_by_technology"].grain,
        key_columns=("interval_start_utc", "technology_key"),
        columns=VIEW_CONTRACTS["hourly_generation_by_technology"].columns,
        measures=_measure_units(
            VIEW_CONTRACTS["hourly_generation_by_technology"].columns
        ),
        expected_full_rows=VIEW_CONTRACTS[
            "hourly_generation_by_technology"
        ].expected_rows,
        consumers=("power_bi", "portfolio_review"),
        sample=SampleExtractContract(
            path="data/samples/hourly_generation_sample.csv",
            filter_rule=(
                "calendar_date from 2025-01-06 through 2025-01-12 inclusive"
            ),
            expected_rows=2_016,
        ),
    ),
    MartContract(
        product_id="daily_energy",
        display_name="Daily energy and market summary",
        source_kind="postgresql_view",
        source_name="reporting.daily_energy",
        implementation_status="verified_existing",
        grain=VIEW_CONTRACTS["daily_energy"].grain,
        key_columns=("date_key",),
        columns=VIEW_CONTRACTS["daily_energy"].columns,
        measures=_measure_units(VIEW_CONTRACTS["daily_energy"].columns),
        expected_full_rows=VIEW_CONTRACTS["daily_energy"].expected_rows,
        consumers=("power_bi", "excel_power_query", "portfolio_review"),
        sample=SampleExtractContract(
            path="data/samples/daily_energy_sample.csv",
            filter_rule="calendar_year equals 2025",
            expected_rows=365,
        ),
    ),
    MartContract(
        product_id="monthly_energy",
        display_name="Monthly energy and market summary",
        source_kind="postgresql_view",
        source_name="reporting.monthly_energy",
        implementation_status="verified_existing",
        grain=VIEW_CONTRACTS["monthly_energy"].grain,
        key_columns=("month_key",),
        columns=VIEW_CONTRACTS["monthly_energy"].columns,
        measures=_measure_units(VIEW_CONTRACTS["monthly_energy"].columns),
        expected_full_rows=VIEW_CONTRACTS["monthly_energy"].expected_rows,
        consumers=("power_bi", "excel_power_query", "portfolio_review"),
        sample=SampleExtractContract(
            path="data/samples/monthly_energy_sample.csv",
            filter_rule="all 48 complete project months",
            expected_rows=48,
        ),
    ),
    MartContract(
        product_id="forecast_performance_hourly",
        display_name="Final hourly forecast performance",
        source_kind="postgresql_view",
        source_name="reporting.forecast_performance_hourly",
        implementation_status="planned_step_7_2",
        grain="one 2025 forecast origin and horizon step",
        key_columns=("forecast_origin_utc", "horizon_step"),
        columns=FORECAST_PERFORMANCE_HOURLY_COLUMNS,
        measures=_measure_units(FORECAST_PERFORMANCE_HOURLY_COLUMNS),
        expected_full_rows=8_760,
        consumers=("power_bi", "portfolio_review"),
        sample=SampleExtractContract(
            path="data/samples/forecast_performance_hourly_sample.csv",
            filter_rule="origin_local_date from 2025-01-01 through 2025-01-31",
            expected_rows=744,
        ),
    ),
    MartContract(
        product_id="forecast_performance_summary",
        display_name="Forecast metrics overall and by horizon",
        source_kind="postgresql_view",
        source_name="reporting.forecast_performance_summary",
        implementation_status="planned_step_7_2",
        grain="one forecast series and overall or horizon scope",
        key_columns=("forecast_name", "evaluation_scope", "horizon_step"),
        columns=FORECAST_PERFORMANCE_SUMMARY_COLUMNS,
        measures=_measure_units(FORECAST_PERFORMANCE_SUMMARY_COLUMNS),
        expected_full_rows=75,
        consumers=("power_bi", "excel_power_query", "portfolio_review"),
        sample=SampleExtractContract(
            path="data/samples/forecast_performance_summary_sample.csv",
            filter_rule="all three series at overall and 24 horizon scopes",
            expected_rows=75,
        ),
    ),
    MartContract(
        product_id="data_quality_checks",
        display_name="Canonical data-quality checks",
        source_kind="checked_extract",
        source_name="data/processed/validation_summary.json",
        implementation_status="planned_step_7_3",
        grain="one stable validation check",
        key_columns=("dataset", "check_id"),
        columns=DATA_QUALITY_CHECK_COLUMNS,
        measures=(),
        expected_full_rows=29,
        consumers=("power_bi", "portfolio_review"),
        sample=SampleExtractContract(
            path="data/samples/data_quality_checks.csv",
            filter_rule="all 29 canonical validation checks",
            expected_rows=29,
        ),
    ),
    MartContract(
        product_id="source_lineage",
        display_name="SMARD source lineage",
        source_kind="checked_extract",
        source_name="data/manifests/smard_source_manifest.csv",
        implementation_status="planned_step_7_3",
        grain="one immutable registered SMARD export",
        key_columns=("export_id",),
        columns=SOURCE_LINEAGE_COLUMNS,
        measures=(),
        expected_full_rows=6,
        consumers=("power_bi", "portfolio_review"),
        sample=SampleExtractContract(
            path="data/samples/source_lineage.csv",
            filter_rule="all six registered SMARD exports",
            expected_rows=6,
        ),
    ),
)


def validate_mart_contracts(
    contracts: tuple[MartContract, ...] = MART_CONTRACTS,
) -> None:
    """Reject ambiguous grains, keys, units, consumers, or sample policies."""
    if not contracts:
        raise ValueError("At least one reporting-mart contract is required")
    product_ids = [contract.product_id for contract in contracts]
    source_names = [contract.source_name for contract in contracts]
    sample_paths = [contract.sample.path for contract in contracts]
    if len(set(product_ids)) != len(product_ids):
        raise ValueError("Reporting product IDs must be unique")
    if len(set(source_names)) != len(source_names):
        raise ValueError("Reporting source names must be unique")
    if len(set(sample_paths)) != len(sample_paths):
        raise ValueError("Sample-extract paths must be unique")

    for contract in contracts:
        if not contract.grain or not contract.columns or not contract.key_columns:
            raise ValueError(f"Incomplete reporting grain for {contract.product_id}")
        if len(set(contract.columns)) != len(contract.columns):
            raise ValueError(f"Duplicate columns for {contract.product_id}")
        if not set(contract.key_columns).issubset(contract.columns):
            raise ValueError(f"Invalid reporting key for {contract.product_id}")
        if contract.expected_full_rows <= 0:
            raise ValueError(f"Invalid full row count for {contract.product_id}")
        if not 0 < contract.sample.expected_rows <= contract.expected_full_rows:
            raise ValueError(f"Invalid sample row count for {contract.product_id}")
        if not contract.sample.path.startswith("data/samples/"):
            raise ValueError(f"Invalid sample path for {contract.product_id}")
        if not set(contract.consumers).issubset(ALLOWED_CONSUMERS):
            raise ValueError(f"Invalid consumer for {contract.product_id}")
        measure_columns = [column for column, _ in contract.measures]
        if len(set(measure_columns)) != len(measure_columns):
            raise ValueError(f"Duplicate measures for {contract.product_id}")
        if not set(measure_columns).issubset(contract.columns):
            raise ValueError(f"Unknown measure for {contract.product_id}")
        if not all(unit in ALLOWED_UNITS for _, unit in contract.measures):
            raise ValueError(f"Invalid measure unit for {contract.product_id}")

        if contract.implementation_status == "verified_existing":
            view_name = contract.source_name.removeprefix("reporting.")
            view = VIEW_CONTRACTS.get(view_name)
            if view is None:
                raise ValueError(f"Missing existing view for {contract.product_id}")
            if (
                contract.grain != view.grain
                or contract.columns != view.columns
                or contract.expected_full_rows != view.expected_rows
            ):
                raise ValueError(
                    f"Existing view changed for {contract.product_id}"
                )


def _load_final_evaluation(
    snapshot_path: Path,
    predictions_path: Path,
    project_root: Path,
) -> dict[str, Any]:
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    artifact = snapshot.get("prediction_artifact", {})
    expected_path = predictions_path.relative_to(project_root).as_posix()
    if snapshot.get("schema_version") != 1:
        raise ValueError("Final evaluation schema version must equal 1")
    if artifact.get("path") != expected_path:
        raise ValueError("Final prediction path does not match its snapshot")
    if artifact.get("sha256") != sha256_file(predictions_path):
        raise ValueError("Final prediction bytes do not match their snapshot")
    if artifact.get("row_count") != 8_760:
        raise ValueError("Final prediction artifact must contain 8,760 rows")
    if tuple(artifact.get("columns", ())) != FINAL_PREDICTION_COLUMNS:
        raise ValueError("Final prediction columns do not match their snapshot")
    if snapshot.get("final_fit_contract", {}).get(
        "further_model_selection_allowed"
    ) is not False:
        raise ValueError("Final evaluation must prohibit further selection")
    return snapshot


def _load_validation_summary(path: Path) -> dict[str, Any]:
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
        raise ValueError("Validation summary is not the passing 29-check gate")
    return summary


def _validate_source_manifest(path: Path) -> None:
    with path.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    if len(rows) != 6 or len({row.get("export_id") for row in rows}) != 6:
        raise ValueError("Source manifest must contain six unique exports")
    if tuple(rows[0]) != SOURCE_LINEAGE_COLUMNS:
        raise ValueError("Source manifest columns do not match the contract")


def build_reporting_mart_contract(
    *,
    contracts: tuple[MartContract, ...] = MART_CONTRACTS,
    reporting_sql_path: Path = REPORTING_SQL_FILES[0],
    final_snapshot_path: Path = DEFAULT_FINAL_EVALUATION_SNAPSHOT,
    predictions_path: Path = DEFAULT_FINAL_PREDICTIONS,
    validation_summary_path: Path = DEFAULT_VALIDATION_SUMMARY,
    source_manifest_path: Path = DEFAULT_SOURCE_MANIFEST,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    """Build deterministic Phase 7 data-product design evidence."""
    validate_mart_contracts(contracts)
    final_evaluation = _load_final_evaluation(
        final_snapshot_path,
        predictions_path,
        project_root,
    )
    _load_validation_summary(validation_summary_path)
    _validate_source_manifest(source_manifest_path)
    products = []
    for contract in contracts:
        record = asdict(contract)
        record["key_columns"] = list(contract.key_columns)
        record["columns"] = list(contract.columns)
        record["measures"] = [
            {"column": column, "unit": unit}
            for column, unit in contract.measures
        ]
        record["consumers"] = list(contract.consumers)
        products.append(record)
    return {
        "schema_version": 1,
        "status": "frozen_before_mart_implementation",
        "attribution": "Bundesnetzagentur | SMARD.de",
        "source": {
            "reporting_sql": {
                "path": reporting_sql_path.relative_to(project_root).as_posix(),
                "sha256": sha256_file(reporting_sql_path),
                "verified_existing_views": len(VIEW_CONTRACTS),
            },
            "final_evaluation_snapshot": {
                "path": final_snapshot_path.relative_to(project_root).as_posix(),
                "sha256": sha256_file(final_snapshot_path),
            },
            "final_predictions": {
                "path": predictions_path.relative_to(project_root).as_posix(),
                "sha256": sha256_file(predictions_path),
                "rows": final_evaluation["prediction_artifact"]["row_count"],
            },
            "validation_summary": {
                "path": validation_summary_path.relative_to(
                    project_root
                ).as_posix(),
                "sha256": sha256_file(validation_summary_path),
                "checks": 29,
            },
            "source_manifest": {
                "path": source_manifest_path.relative_to(project_root).as_posix(),
                "sha256": sha256_file(source_manifest_path),
                "exports": 6,
            },
        },
        "products": products,
        "implementation_sequence": [
            "Step 7.1: freeze this product and extract contract",
            "Step 7.2: add and reconcile PostgreSQL forecast marts",
            "Step 7.3: build checked public sample extracts",
        ],
        "consumer_rules": [
            "Power BI and Excel consume reporting products, not staging tables",
            "UTC remains the fact key and Europe/Berlin fields support display",
            "MW, MWh, EUR/MWh, percentages, and counts remain explicit",
            "checked samples use fixed filters and deterministic row order",
            "full raw and processed row-level datasets remain excluded from Git",
        ],
    }


def write_reporting_mart_contract(
    contract: dict[str, Any],
    output_path: Path,
) -> None:
    """Write deterministic reporting-mart JSON atomically."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(f"{output_path.suffix}.tmp")
    payload = json.dumps(contract, indent=2, sort_keys=True) + "\n"
    temporary_path.write_text(payload, encoding="utf-8", newline="\n")
    temporary_path.replace(output_path)
