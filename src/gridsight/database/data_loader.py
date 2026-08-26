"""Transactional PostgreSQL loading and reconciliation for validated data."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.engine import Connection, Engine

from gridsight.database.schema_contract import (
    PROJECT_ROOT,
    TABLE_CONTRACTS,
    split_sql_statements,
)
from gridsight.ingestion.snapshot_registry import sha256_file
from gridsight.validation.clean_data import ISSUE_COLUMNS

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
DEFAULT_VALIDATION_SUMMARY = PROCESSED_DIR / "validation_summary.json"
DEFAULT_VALIDATION_ISSUES = PROCESSED_DIR / "validation_issues.csv"
TRANSFORMATION_SQL_FILES = (
    PROJECT_ROOT / "sql" / "transformations" / "001_populate_dimensions.sql",
    PROJECT_ROOT / "sql" / "transformations" / "002_populate_facts.sql",
)
STATUS_PASSED = "passed"
STATUS_FAILED = "failed"


@dataclass(frozen=True)
class DatasetLoadSpec:
    """Fixed mapping from a validated artifact to one staging table."""

    dataset: str
    schema: str
    table: str
    relative_path: str
    expected_rows: int

    @property
    def columns(self) -> tuple[str, ...]:
        """Return the staging table's canonical ordered columns."""
        return TABLE_CONTRACTS[(self.schema, self.table)].columns

    @property
    def qualified_table(self) -> str:
        """Return the safe schema-qualified PostgreSQL table name."""
        return f"{self.schema}.{self.table}"


DATASET_LOAD_SPECS = (
    DatasetLoadSpec(
        "consumption",
        "staging",
        "actual_consumption_hourly",
        "data/processed/actual_consumption_hourly.csv",
        35_064,
    ),
    DatasetLoadSpec(
        "generation",
        "staging",
        "actual_generation_hourly",
        "data/processed/actual_generation_hourly.csv",
        420_768,
    ),
    DatasetLoadSpec(
        "price",
        "staging",
        "day_ahead_price_hourly",
        "data/processed/day_ahead_price_hourly.csv",
        35_064,
    ),
)


@dataclass(frozen=True)
class ValidatedDataset:
    """A canonical CSV proven to match the Phase 3 run summary."""

    spec: DatasetLoadSpec
    path: Path
    sha256: str
    metrics: dict[str, Any]


@dataclass(frozen=True)
class ValidatedInputs:
    """All validated artifacts required by one database load."""

    summary_path: Path
    summary_sha256: str
    datasets: tuple[ValidatedDataset, ...]

    def metrics_for(self, dataset: str) -> dict[str, Any]:
        """Return summary metrics for one named dataset."""
        return next(
            item.metrics for item in self.datasets if item.spec.dataset == dataset
        )


@dataclass(frozen=True)
class ReconciliationCheck:
    """One stable post-load database comparison."""

    check_id: str
    status: str
    expected: str
    observed: str


@dataclass(frozen=True)
class DatabaseLoadReport:
    """Committed row counts and reconciliation checks for one load."""

    table_counts: dict[str, int]
    checks: tuple[ReconciliationCheck, ...]
    transformation_statements: int

    @property
    def ok(self) -> bool:
        """Return whether every post-load reconciliation check passed."""
        return all(check.status == STATUS_PASSED for check in self.checks)

    @property
    def problems(self) -> tuple[ReconciliationCheck, ...]:
        """Return only failed reconciliation checks."""
        return tuple(
            check for check in self.checks if check.status == STATUS_FAILED
        )


class DatabaseReconciliationError(ValueError):
    """Raised inside the load transaction when reconciliation fails."""

    def __init__(self, report: DatabaseLoadReport) -> None:
        self.report = report
        failed_ids = ", ".join(check.check_id for check in report.problems)
        super().__init__(f"database reconciliation failed: {failed_ids}")


def _read_csv_header(path: Path) -> tuple[str, ...]:
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.reader(file)
        try:
            return tuple(next(reader))
        except StopIteration as error:
            raise ValueError(f"Validated dataset is empty: {path.name}") from error


def _require_mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"Validation summary {label} must be an object")
    return value


def load_validated_inputs(
    summary_path: Path = DEFAULT_VALIDATION_SUMMARY,
    project_root: Path = PROJECT_ROOT,
) -> ValidatedInputs:
    """Verify the Phase 3 summary, issue file, CSV headers, and output hashes."""
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("Validation summary is missing or invalid") from error
    summary = _require_mapping(summary, "root")
    check_counts = _require_mapping(summary.get("check_counts"), "check_counts")
    issue_counts = _require_mapping(summary.get("issue_counts"), "issue_counts")
    datasets = _require_mapping(summary.get("datasets"), "datasets")
    checks = summary.get("checks")
    if (
        summary.get("schema_version") != 1
        or summary.get("status") != STATUS_PASSED
        or check_counts.get("failed") != 0
        or issue_counts.get("error") != 0
        or not isinstance(checks, list)
        or not checks
        or any(
            not isinstance(check, dict)
            or check.get("status") != STATUS_PASSED
            for check in checks
        )
    ):
        raise ValueError("Validation summary does not represent a passing run")

    issues_path = project_root / "data" / "processed" / "validation_issues.csv"
    expected_issue_header = ",".join(ISSUE_COLUMNS)
    try:
        issue_lines = issues_path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ValueError("Validation issues artifact is missing") from error
    if issue_lines != [expected_issue_header]:
        raise ValueError("Validation issues artifact contains error rows")

    validated_datasets: list[ValidatedDataset] = []
    for spec in DATASET_LOAD_SPECS:
        metrics = _require_mapping(datasets.get(spec.dataset), spec.dataset)
        expected_path = project_root / Path(spec.relative_path)
        if metrics.get("output") != spec.relative_path:
            raise ValueError(f"Unexpected output path for {spec.dataset}")
        if metrics.get("rows") != spec.expected_rows:
            raise ValueError(f"Unexpected row count for {spec.dataset}")
        if metrics.get("columns") != len(spec.columns):
            raise ValueError(f"Unexpected column count for {spec.dataset}")
        if _read_csv_header(expected_path) != spec.columns:
            raise ValueError(f"CSV column contract changed for {spec.dataset}")
        observed_sha256 = sha256_file(expected_path)
        if metrics.get("sha256") != observed_sha256:
            raise ValueError(f"Processed SHA-256 mismatch for {spec.dataset}")
        validated_datasets.append(
            ValidatedDataset(
                spec=spec,
                path=expected_path,
                sha256=observed_sha256,
                metrics=metrics,
            )
        )

    return ValidatedInputs(
        summary_path=summary_path,
        summary_sha256=sha256_file(summary_path),
        datasets=tuple(validated_datasets),
    )


def _copy_dataset(connection: Connection, dataset: ValidatedDataset) -> None:
    columns = ", ".join(dataset.spec.columns)
    copy_sql = (
        f"COPY {dataset.spec.qualified_table} ({columns}) "
        "FROM STDIN WITH (FORMAT CSV, HEADER TRUE, NULL '')"
    )
    driver_connection = connection.connection.driver_connection
    with driver_connection.cursor() as cursor:
        with cursor.copy(copy_sql) as copy:
            with dataset.path.open("rb") as file:
                while chunk := file.read(1024 * 1024):
                    copy.write(chunk)


def _apply_transformations(connection: Connection) -> int:
    statements_executed = 0
    for sql_path in TRANSFORMATION_SQL_FILES:
        sql_text = sql_path.read_text(encoding="utf-8")
        for statement in split_sql_statements(sql_text):
            connection.exec_driver_sql(statement)
            statements_executed += 1
    return statements_executed


def _add_check(
    checks: list[ReconciliationCheck],
    check_id: str,
    expected: object,
    observed: object,
) -> None:
    status = STATUS_PASSED if observed == expected else STATUS_FAILED
    checks.append(
        ReconciliationCheck(
            check_id=check_id,
            status=status,
            expected=str(expected),
            observed=str(observed),
        )
    )


def _scalar(connection: Connection, sql: str) -> Any:
    return connection.exec_driver_sql(sql).scalar_one()


def _expected_local_dates(inputs: ValidatedInputs) -> int:
    metrics = inputs.metrics_for("consumption")
    timezone = ZoneInfo("Europe/Berlin")
    first = datetime.fromisoformat(metrics["first_utc_start"]).astimezone(timezone)
    last_start = (
        datetime.fromisoformat(metrics["last_utc_end"]) - timedelta(hours=1)
    ).astimezone(timezone)
    return (last_start.date() - first.date()).days + 1


def reconcile_database(
    connection: Connection,
    inputs: ValidatedInputs,
    transformation_statements: int,
) -> DatabaseLoadReport:
    """Reconcile database rows and measures with the Phase 3 summary."""
    table_expectations = {
        "staging.actual_consumption_hourly": inputs.metrics_for("consumption")[
            "rows"
        ],
        "staging.actual_generation_hourly": inputs.metrics_for("generation")[
            "rows"
        ],
        "staging.day_ahead_price_hourly": inputs.metrics_for("price")["rows"],
        "analytics.dim_date": _expected_local_dates(inputs),
        "analytics.dim_hour": 24,
        "analytics.dim_generation_technology": inputs.metrics_for("generation")[
            "technologies"
        ],
        "analytics.fact_electricity_hourly": inputs.metrics_for("consumption")[
            "rows"
        ],
        "analytics.fact_generation_hourly": inputs.metrics_for("generation")[
            "rows"
        ],
    }
    checks: list[ReconciliationCheck] = []
    table_counts: dict[str, int] = {}
    for table, expected_rows in table_expectations.items():
        observed_rows = int(_scalar(connection, f"SELECT COUNT(*) FROM {table}"))
        table_counts[table] = observed_rows
        _add_check(
            checks,
            f"{table}.row_count",
            int(expected_rows),
            observed_rows,
        )

    price_metrics = inputs.metrics_for("price")
    price_row = connection.exec_driver_sql(
        """
        SELECT
            COUNT(*) FILTER (WHERE day_ahead_price_eur_per_mwh < 0),
            COUNT(*) FILTER (WHERE day_ahead_price_eur_per_mwh = 0),
            COUNT(*) FILTER (WHERE day_ahead_price_eur_per_mwh > 0),
            MIN(day_ahead_price_eur_per_mwh),
            MAX(day_ahead_price_eur_per_mwh)
        FROM analytics.fact_electricity_hourly
        """
    ).one()
    price_expectations = (
        ("price.negative_rows", int(price_metrics["negative_rows"]), int(price_row[0])),
        ("price.zero_rows", int(price_metrics["zero_rows"]), int(price_row[1])),
        ("price.positive_rows", int(price_metrics["positive_rows"]), int(price_row[2])),
        (
            "price.minimum",
            Decimal(str(price_metrics["minimum_eur_per_mwh"])),
            price_row[3],
        ),
        (
            "price.maximum",
            Decimal(str(price_metrics["maximum_eur_per_mwh"])),
            price_row[4],
        ),
    )
    for check_id, expected, observed in price_expectations:
        _add_check(checks, check_id, expected, observed)

    generation_metrics = inputs.metrics_for("generation")
    generation_row = connection.exec_driver_sql(
        """
        SELECT
            COUNT(*) FILTER (WHERE value_status = 'reported'),
            COUNT(*) FILTER (WHERE value_status = 'unavailable')
        FROM analytics.fact_generation_hourly
        """
    ).one()
    _add_check(
        checks,
        "generation.reported_rows",
        int(generation_metrics["reported_rows"]),
        int(generation_row[0]),
    )
    _add_check(
        checks,
        "generation.unavailable_rows",
        int(generation_metrics["unavailable_rows"]),
        int(generation_row[1]),
    )

    aligned_hours = int(
        _scalar(
            connection,
            """
            SELECT COUNT(*)
            FROM staging.actual_consumption_hourly AS consumption
            FULL OUTER JOIN staging.day_ahead_price_hourly AS price
                USING (interval_start_utc)
            WHERE consumption.interval_start_utc IS NULL
                OR price.interval_start_utc IS NULL
            """,
        )
    )
    _add_check(checks, "cross_dataset.load_price_spine", 0, aligned_hours)

    generation_spine_differences = int(
        _scalar(
            connection,
            """
            SELECT COUNT(*)
            FROM (
                (
                    SELECT interval_start_utc
                    FROM staging.actual_consumption_hourly
                    EXCEPT
                    SELECT interval_start_utc
                    FROM staging.actual_generation_hourly
                )
                UNION ALL
                (
                    SELECT interval_start_utc
                    FROM staging.actual_generation_hourly
                    EXCEPT
                    SELECT interval_start_utc
                    FROM staging.actual_consumption_hourly
                )
            ) AS differences
            """,
        )
    )
    _add_check(
        checks,
        "cross_dataset.generation_spine",
        0,
        generation_spine_differences,
    )

    electricity_mismatches = int(
        _scalar(
            connection,
            """
            SELECT COUNT(*)
            FROM analytics.fact_electricity_hourly AS fact
            INNER JOIN staging.actual_consumption_hourly AS consumption
                USING (interval_start_utc)
            INNER JOIN staging.day_ahead_price_hourly AS price
                USING (interval_start_utc)
            WHERE fact.grid_load_mwh IS DISTINCT FROM consumption.grid_load_mwh
                OR fact.grid_load_mw IS DISTINCT FROM consumption.grid_load_mw
                OR fact.residual_load_mwh
                    IS DISTINCT FROM consumption.residual_load_mwh
                OR fact.day_ahead_price_eur_per_mwh
                    IS DISTINCT FROM price.day_ahead_price_eur_per_mwh
            """,
        )
    )
    _add_check(checks, "fact_electricity.measure_copy", 0, electricity_mismatches)

    generation_mismatches = int(
        _scalar(
            connection,
            """
            SELECT COUNT(*)
            FROM analytics.fact_generation_hourly AS fact
            INNER JOIN analytics.dim_generation_technology AS technology
                USING (technology_key)
            INNER JOIN staging.actual_generation_hourly AS staging
                ON staging.interval_start_utc = fact.interval_start_utc
                AND staging.technology_id = technology.technology_id
            WHERE fact.generation_mwh IS DISTINCT FROM staging.generation_mwh
                OR fact.generation_mw IS DISTINCT FROM staging.generation_mw
                OR fact.value_status IS DISTINCT FROM staging.value_status
                OR fact.source_export_id IS DISTINCT FROM staging.source_export_id
                OR fact.source_sha256 IS DISTINCT FROM staging.source_sha256
            """,
        )
    )
    _add_check(checks, "fact_generation.measure_copy", 0, generation_mismatches)

    return DatabaseLoadReport(
        table_counts=table_counts,
        checks=tuple(checks),
        transformation_statements=transformation_statements,
    )


def load_database(engine: Engine, inputs: ValidatedInputs) -> DatabaseLoadReport:
    """Full-refresh staging and analytics atomically, then reconcile."""
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            TRUNCATE TABLE
                analytics.fact_load_forecast_evaluation,
                analytics.fact_generation_hourly,
                analytics.fact_electricity_hourly,
                analytics.dim_generation_technology,
                analytics.dim_hour,
                analytics.dim_date,
                staging.actual_generation_hourly,
                staging.actual_consumption_hourly,
                staging.day_ahead_price_hourly,
                staging.final_forecast_predictions
            """
        )
        for dataset in inputs.datasets:
            _copy_dataset(connection, dataset)
        transformation_statements = _apply_transformations(connection)
        report = reconcile_database(
            connection,
            inputs,
            transformation_statements,
        )
        if not report.ok:
            raise DatabaseReconciliationError(report)
    return report
