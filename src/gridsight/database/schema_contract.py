"""PostgreSQL DDL application and schema-contract inspection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from gridsight.database.connection import create_database_engine

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_SQL_FILES = (
    PROJECT_ROOT / "sql" / "schemas" / "001_create_schemas.sql",
    PROJECT_ROOT / "sql" / "tables" / "001_create_staging_tables.sql",
    PROJECT_ROOT / "sql" / "tables" / "002_create_analytics_tables.sql",
    PROJECT_ROOT
    / "sql"
    / "tables"
    / "003_create_forecast_evaluation_tables.sql",
)
EXPECTED_SCHEMAS = ("staging", "analytics", "reporting")


@dataclass(frozen=True)
class TableContract:
    """Expected ordered columns, primary key, references, and checks."""

    columns: tuple[str, ...]
    primary_key: tuple[str, ...]
    foreign_key_targets: tuple[tuple[str, str], ...] = ()
    minimum_check_constraints: int = 0


@dataclass(frozen=True)
class SchemaApplication:
    """Summary of one transactional DDL application."""

    files_applied: int
    statements_executed: int


@dataclass(frozen=True)
class DatabaseContractReport:
    """Inspection result for the complete GridSight database contract."""

    schema_table_counts: dict[str, int]
    problems: tuple[str, ...]

    @property
    def ok(self) -> bool:
        """Return whether every declared schema and table contract matched."""
        return not self.problems


_TIME_COLUMNS = (
    "interval_start_utc",
    "interval_end_utc",
    "interval_start_local",
    "interval_end_local",
    "utc_offset_minutes",
    "is_dst",
    "local_fold",
    "source_start_text",
    "source_end_text",
)
_LINEAGE_COLUMNS = (
    "source_export_id",
    "source_category",
    "source_geography",
    "source_resolution",
    "source_period_start",
    "source_period_end",
    "source_original_filename",
    "source_filename",
    "source_sha256",
)

TABLE_CONTRACTS = {
    ("staging", "actual_consumption_hourly"): TableContract(
        columns=(
            *_TIME_COLUMNS,
            *_LINEAGE_COLUMNS,
            "interval_duration_hours",
            "grid_load_mwh",
            "grid_load_mw",
            "grid_load_including_pumped_storage_mwh",
            "hydro_pumped_storage_mwh",
            "residual_load_mwh",
        ),
        primary_key=("interval_start_utc",),
        minimum_check_constraints=6,
    ),
    ("staging", "actual_generation_hourly"): TableContract(
        columns=(
            *_TIME_COLUMNS,
            *_LINEAGE_COLUMNS,
            "interval_duration_hours",
            "technology_id",
            "technology_name",
            "technology_group",
            "is_renewable",
            "technology_order",
            "source_measure_column",
            "source_value_text",
            "value_status",
            "generation_mwh",
            "generation_mw",
        ),
        primary_key=("interval_start_utc", "technology_id"),
        minimum_check_constraints=5,
    ),
    ("staging", "day_ahead_price_hourly"): TableContract(
        columns=(
            *_TIME_COLUMNS,
            *_LINEAGE_COLUMNS,
            "interval_duration_hours",
            "market_area",
            "currency",
            "price_unit",
            "source_measure_column",
            "source_value_text",
            "day_ahead_price_eur_per_mwh",
        ),
        primary_key=("interval_start_utc",),
        minimum_check_constraints=4,
    ),
    ("analytics", "dim_date"): TableContract(
        columns=(
            "date_key",
            "calendar_date",
            "calendar_year",
            "calendar_quarter",
            "month_number",
            "month_name",
            "iso_week",
            "day_of_month",
            "weekday_number",
            "weekday_name",
            "is_weekend",
        ),
        primary_key=("date_key",),
        minimum_check_constraints=2,
    ),
    ("analytics", "dim_hour"): TableContract(
        columns=("hour_key", "hour_start", "hour_label"),
        primary_key=("hour_key",),
        minimum_check_constraints=2,
    ),
    ("analytics", "dim_generation_technology"): TableContract(
        columns=(
            "technology_key",
            "technology_id",
            "technology_name",
            "technology_group",
            "is_renewable",
            "technology_order",
        ),
        primary_key=("technology_key",),
        minimum_check_constraints=2,
    ),
    ("analytics", "fact_electricity_hourly"): TableContract(
        columns=(
            "interval_start_utc",
            "interval_end_utc",
            "date_key",
            "hour_key",
            "utc_offset_minutes",
            "is_dst",
            "local_fold",
            "load_area",
            "grid_load_mwh",
            "grid_load_mw",
            "grid_load_including_pumped_storage_mwh",
            "hydro_pumped_storage_mwh",
            "residual_load_mwh",
            "price_market_area",
            "day_ahead_price_eur_per_mwh",
            "consumption_source_export_id",
            "consumption_source_sha256",
            "price_source_export_id",
            "price_source_sha256",
        ),
        primary_key=("interval_start_utc",),
        foreign_key_targets=(("analytics", "dim_date"), ("analytics", "dim_hour")),
        minimum_check_constraints=3,
    ),
    ("analytics", "fact_generation_hourly"): TableContract(
        columns=(
            "interval_start_utc",
            "interval_end_utc",
            "date_key",
            "hour_key",
            "technology_key",
            "utc_offset_minutes",
            "is_dst",
            "local_fold",
            "generation_mwh",
            "generation_mw",
            "value_status",
            "source_export_id",
            "source_sha256",
        ),
        primary_key=("interval_start_utc", "technology_key"),
        foreign_key_targets=(
            ("analytics", "dim_date"),
            ("analytics", "dim_hour"),
            ("analytics", "dim_generation_technology"),
        ),
        minimum_check_constraints=3,
    ),
    ("staging", "final_forecast_predictions"): TableContract(
        columns=(
            "forecast_origin_utc",
            "origin_local_date",
            "split",
            "horizon_step",
            "information_cutoff_utc",
            "target_start_utc",
            "target_start_local",
            "actual_grid_load_mw",
            "daily_naive_source_utc",
            "daily_naive_prediction_mw",
            "weekly_naive_source_utc",
            "weekly_naive_prediction_mw",
            "model_name",
            "model_prediction_mw",
            "model_error_mw",
            "model_absolute_error_mw",
        ),
        primary_key=("forecast_origin_utc", "horizon_step"),
        minimum_check_constraints=5,
    ),
    ("analytics", "fact_load_forecast_evaluation"): TableContract(
        columns=(
            "forecast_origin_utc",
            "origin_date_key",
            "horizon_step",
            "information_cutoff_utc",
            "target_start_utc",
            "target_date_key",
            "target_hour_key",
            "actual_grid_load_mw",
            "daily_naive_source_utc",
            "daily_naive_prediction_mw",
            "weekly_naive_source_utc",
            "weekly_naive_prediction_mw",
            "model_name",
            "model_prediction_mw",
            "model_error_mw",
            "model_absolute_error_mw",
            "prediction_artifact_sha256",
            "evaluation_snapshot_sha256",
        ),
        primary_key=("forecast_origin_utc", "horizon_step"),
        foreign_key_targets=(
            ("analytics", "dim_date"),
            ("analytics", "dim_hour"),
            ("analytics", "fact_electricity_hourly"),
        ),
        minimum_check_constraints=3,
    ),
}


def split_sql_statements(sql_text: str) -> tuple[str, ...]:
    """Split GridSight's simple DDL files into executable statements."""
    statements = tuple(
        statement.strip()
        for statement in sql_text.split(";")
        if statement.strip()
    )
    if any("\\" in statement for statement in statements):
        raise ValueError("psql meta-commands are not allowed in schema SQL")
    return statements


def apply_database_schema(engine: Engine | None = None) -> SchemaApplication:
    """Apply every ordered DDL file once inside one transaction."""
    resolved_engine = engine or create_database_engine()
    owns_engine = engine is None
    statements_executed = 0
    try:
        with resolved_engine.begin() as connection:
            for sql_path in SCHEMA_SQL_FILES:
                sql_text = sql_path.read_text(encoding="utf-8")
                statements = split_sql_statements(sql_text)
                for statement in statements:
                    connection.exec_driver_sql(statement)
                    statements_executed += 1
    finally:
        if owns_engine:
            resolved_engine.dispose()
    return SchemaApplication(
        files_applied=len(SCHEMA_SQL_FILES),
        statements_executed=statements_executed,
    )


def inspect_database_contract(engine: Engine) -> DatabaseContractReport:
    """Compare live PostgreSQL metadata with the declared table contracts."""
    inspector = inspect(engine)
    observed_schemas = set(inspector.get_schema_names())
    problems = [
        f"missing schema: {schema}"
        for schema in EXPECTED_SCHEMAS
        if schema not in observed_schemas
    ]
    schema_table_counts: dict[str, int] = {}
    tables_by_schema: dict[str, set[str]] = {}
    for schema in EXPECTED_SCHEMAS:
        tables = (
            set(inspector.get_table_names(schema=schema))
            if schema in observed_schemas
            else set()
        )
        tables_by_schema[schema] = tables
        schema_table_counts[schema] = len(tables)

    for (schema, table), contract in TABLE_CONTRACTS.items():
        if table not in tables_by_schema[schema]:
            problems.append(f"missing table: {schema}.{table}")
            continue
        observed_columns = tuple(
            column["name"]
            for column in inspector.get_columns(table, schema=schema)
        )
        if observed_columns != contract.columns:
            problems.append(f"column contract mismatch: {schema}.{table}")
        primary_key = inspector.get_pk_constraint(table, schema=schema)
        observed_primary_key = tuple(primary_key.get("constrained_columns") or ())
        if observed_primary_key != contract.primary_key:
            problems.append(f"primary-key mismatch: {schema}.{table}")
        foreign_keys = inspector.get_foreign_keys(table, schema=schema)
        observed_targets = {
            (foreign_key["referred_schema"], foreign_key["referred_table"])
            for foreign_key in foreign_keys
        }
        if observed_targets != set(contract.foreign_key_targets):
            problems.append(f"foreign-key mismatch: {schema}.{table}")
        check_constraints = inspector.get_check_constraints(table, schema=schema)
        if len(check_constraints) < contract.minimum_check_constraints:
            problems.append(f"check-constraint mismatch: {schema}.{table}")

    return DatabaseContractReport(
        schema_table_counts=schema_table_counts,
        problems=tuple(problems),
    )
