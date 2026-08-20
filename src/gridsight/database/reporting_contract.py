"""Application, inspection, and reconciliation of PostgreSQL reporting views."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import inspect
from sqlalchemy.engine import Connection, Engine

from gridsight.database.schema_contract import PROJECT_ROOT, split_sql_statements

REPORTING_SQL_FILES = (
    PROJECT_ROOT / "sql" / "reporting" / "001_create_reporting_views.sql",
)
STATUS_PASSED = "passed"
STATUS_FAILED = "failed"


@dataclass(frozen=True)
class ViewContract:
    """Declared grain, ordered columns, and expected current-scope rows."""

    grain: str
    columns: tuple[str, ...]
    expected_rows: int


@dataclass(frozen=True)
class ReportingApplication:
    """Summary of one reporting-view SQL application."""

    files_applied: int
    statements_executed: int


@dataclass(frozen=True)
class ReportingContractReport:
    """Live metadata comparison for reporting views."""

    view_count: int
    problems: tuple[str, ...]

    @property
    def ok(self) -> bool:
        """Return whether every view and ordered column contract matched."""
        return not self.problems


@dataclass(frozen=True)
class ReportingCheck:
    """One stable live reporting reconciliation result."""

    check_id: str
    status: str
    expected: str
    observed: str


@dataclass(frozen=True)
class ReportingReconciliation:
    """Row counts and KPI reconciliation for the reporting layer."""

    view_counts: dict[str, int]
    checks: tuple[ReportingCheck, ...]

    @property
    def ok(self) -> bool:
        """Return whether every reporting check passed."""
        return all(check.status == STATUS_PASSED for check in self.checks)

    @property
    def problems(self) -> tuple[ReportingCheck, ...]:
        """Return only failed reporting checks."""
        return tuple(
            check for check in self.checks if check.status == STATUS_FAILED
        )


_DATE_COLUMNS = (
    "date_key",
    "calendar_date",
    "calendar_year",
    "calendar_quarter",
    "month_number",
    "month_name",
    "iso_week",
    "weekday_number",
    "weekday_name",
    "is_weekend",
)
_HOURLY_DATE_COLUMNS = (
    "interval_start_utc",
    "interval_end_utc",
    *_DATE_COLUMNS,
    "hour_key",
    "hour_label",
    "utc_offset_minutes",
    "is_dst",
    "local_fold",
)

VIEW_CONTRACTS = {
    "hourly_energy": ViewContract(
        grain="one canonical UTC hour",
        columns=(
            *_HOURLY_DATE_COLUMNS,
            "load_area",
            "grid_load_mwh",
            "grid_load_mw",
            "grid_load_including_pumped_storage_mwh",
            "hydro_pumped_storage_mwh",
            "residual_load_mwh",
            "price_market_area",
            "day_ahead_price_eur_per_mwh",
            "reported_generation_mwh",
            "reported_generation_mw",
            "renewable_generation_mwh",
            "renewable_generation_mw",
            "conventional_generation_mwh",
            "conventional_generation_mw",
            "storage_generation_mwh",
            "storage_generation_mw",
            "unavailable_technology_count",
            "reported_technology_count",
        ),
        expected_rows=35_064,
    ),
    "hourly_generation_by_technology": ViewContract(
        grain="one canonical UTC hour and generation technology",
        columns=(
            *_HOURLY_DATE_COLUMNS,
            "technology_key",
            "technology_id",
            "technology_name",
            "technology_group",
            "is_renewable",
            "technology_order",
            "generation_mwh",
            "generation_mw",
            "value_status",
            "source_export_id",
            "source_sha256",
        ),
        expected_rows=420_768,
    ),
    "daily_energy": ViewContract(
        grain="one Europe/Berlin calendar date",
        columns=(
            *_DATE_COLUMNS,
            "observed_hour_count",
            "grid_load_mwh",
            "average_grid_load_mw",
            "peak_grid_load_mw",
            "reported_generation_mwh",
            "renewable_generation_mwh",
            "conventional_generation_mwh",
            "storage_generation_mwh",
            "renewable_share_of_reported_generation_percent",
            "average_day_ahead_price_eur_per_mwh",
            "minimum_day_ahead_price_eur_per_mwh",
            "maximum_day_ahead_price_eur_per_mwh",
            "negative_price_hour_count",
            "unavailable_generation_value_count",
        ),
        expected_rows=1_461,
    ),
    "monthly_energy": ViewContract(
        grain="one Europe/Berlin calendar month",
        columns=(
            "month_key",
            "month_start",
            "calendar_year",
            "month_number",
            "month_name",
            "observed_day_count",
            "observed_hour_count",
            "grid_load_mwh",
            "average_grid_load_mw",
            "peak_grid_load_mw",
            "reported_generation_mwh",
            "renewable_generation_mwh",
            "conventional_generation_mwh",
            "storage_generation_mwh",
            "renewable_share_of_reported_generation_percent",
            "average_day_ahead_price_eur_per_mwh",
            "minimum_day_ahead_price_eur_per_mwh",
            "maximum_day_ahead_price_eur_per_mwh",
            "negative_price_hour_count",
            "unavailable_generation_value_count",
        ),
        expected_rows=48,
    ),
}


def apply_reporting_views(engine: Engine) -> ReportingApplication:
    """Create or replace all ordered reporting views transactionally."""
    statements_executed = 0
    with engine.begin() as connection:
        for sql_path in REPORTING_SQL_FILES:
            sql_text = sql_path.read_text(encoding="utf-8")
            for statement in split_sql_statements(sql_text):
                connection.exec_driver_sql(statement)
                statements_executed += 1
    return ReportingApplication(
        files_applied=len(REPORTING_SQL_FILES),
        statements_executed=statements_executed,
    )


def inspect_reporting_contract(engine: Engine) -> ReportingContractReport:
    """Compare live reporting view metadata with exact ordered contracts."""
    inspector = inspect(engine)
    observed_views = set(inspector.get_view_names(schema="reporting"))
    expected_views = set(VIEW_CONTRACTS)
    problems = [
        f"missing view: reporting.{view}"
        for view in sorted(expected_views - observed_views)
    ]
    problems.extend(
        f"unexpected view: reporting.{view}"
        for view in sorted(observed_views - expected_views)
    )
    for view, contract in VIEW_CONTRACTS.items():
        if view not in observed_views:
            continue
        observed_columns = tuple(
            column["name"]
            for column in inspector.get_columns(view, schema="reporting")
        )
        if observed_columns != contract.columns:
            problems.append(f"column contract mismatch: reporting.{view}")
    return ReportingContractReport(
        view_count=len(observed_views),
        problems=tuple(problems),
    )


def _scalar(connection: Connection, sql: str) -> Any:
    return connection.exec_driver_sql(sql).scalar_one()


def _add_check(
    checks: list[ReportingCheck],
    check_id: str,
    expected: object,
    observed: object,
) -> None:
    status = STATUS_PASSED if observed == expected else STATUS_FAILED
    checks.append(
        ReportingCheck(
            check_id=check_id,
            status=status,
            expected=str(expected),
            observed=str(observed),
        )
    )


def reconcile_reporting_views(engine: Engine) -> ReportingReconciliation:
    """Verify view grains, DST coverage, and measure reconciliation."""
    checks: list[ReportingCheck] = []
    view_counts: dict[str, int] = {}
    with engine.connect() as connection:
        for view, contract in VIEW_CONTRACTS.items():
            observed_rows = int(
                _scalar(connection, f"SELECT COUNT(*) FROM reporting.{view}")
            )
            view_counts[view] = observed_rows
            _add_check(
                checks,
                f"reporting.{view}.row_count",
                contract.expected_rows,
                observed_rows,
            )

        hourly_unique = int(
            _scalar(
                connection,
                """
                SELECT COUNT(DISTINCT interval_start_utc)
                FROM reporting.hourly_energy
                """,
            )
        )
        _add_check(checks, "hourly_energy.unique_grain", 35_064, hourly_unique)

        generation_unique = int(
            _scalar(
                connection,
                """
                SELECT COUNT(DISTINCT (interval_start_utc, technology_key))
                FROM reporting.hourly_generation_by_technology
                """,
            )
        )
        _add_check(
            checks,
            "hourly_generation.unique_grain",
            420_768,
            generation_unique,
        )

        technology_range = connection.exec_driver_sql(
            """
            SELECT MIN(technology_count), MAX(technology_count)
            FROM (
                SELECT interval_start_utc, COUNT(*) AS technology_count
                FROM reporting.hourly_generation_by_technology
                GROUP BY interval_start_utc
            ) AS hourly_counts
            """
        ).one()
        _add_check(
            checks,
            "hourly_generation.minimum_technologies",
            12,
            int(technology_range[0]),
        )
        _add_check(
            checks,
            "hourly_generation.maximum_technologies",
            12,
            int(technology_range[1]),
        )

        daily_hours = int(
            _scalar(
                connection,
                "SELECT SUM(observed_hour_count) FROM reporting.daily_energy",
            )
        )
        _add_check(checks, "daily_energy.hour_reconciliation", 35_064, daily_hours)
        spring_days = int(
            _scalar(
                connection,
                """
                SELECT COUNT(*) FROM reporting.daily_energy
                WHERE observed_hour_count = 23
                """,
            )
        )
        autumn_days = int(
            _scalar(
                connection,
                """
                SELECT COUNT(*) FROM reporting.daily_energy
                WHERE observed_hour_count = 25
                """,
            )
        )
        _add_check(checks, "daily_energy.spring_days", 4, spring_days)
        _add_check(checks, "daily_energy.autumn_days", 4, autumn_days)

        monthly_hours = int(
            _scalar(
                connection,
                "SELECT SUM(observed_hour_count) FROM reporting.monthly_energy",
            )
        )
        _add_check(
            checks,
            "monthly_energy.hour_reconciliation",
            35_064,
            monthly_hours,
        )

        electricity_mismatches = int(
            _scalar(
                connection,
                """
                SELECT COUNT(*)
                FROM reporting.hourly_energy AS report
                INNER JOIN analytics.fact_electricity_hourly AS fact
                    USING (interval_start_utc)
                WHERE report.grid_load_mwh IS DISTINCT FROM fact.grid_load_mwh
                    OR report.grid_load_mw IS DISTINCT FROM fact.grid_load_mw
                    OR report.day_ahead_price_eur_per_mwh
                        IS DISTINCT FROM fact.day_ahead_price_eur_per_mwh
                """,
            )
        )
        _add_check(
            checks,
            "hourly_energy.electricity_measure_copy",
            0,
            electricity_mismatches,
        )

        reported_totals = connection.exec_driver_sql(
            """
            SELECT
                (SELECT SUM(reported_generation_mwh)
                 FROM reporting.hourly_energy),
                (SELECT SUM(generation_mwh)
                 FROM analytics.fact_generation_hourly
                 WHERE value_status = 'reported')
            """
        ).one()
        _add_check(
            checks,
            "hourly_energy.reported_generation_total",
            reported_totals[1],
            reported_totals[0],
        )

        renewable_totals = connection.exec_driver_sql(
            """
            SELECT
                (SELECT SUM(renewable_generation_mwh)
                 FROM reporting.hourly_energy),
                (SELECT SUM(fact.generation_mwh)
                 FROM analytics.fact_generation_hourly AS fact
                 INNER JOIN analytics.dim_generation_technology AS technology
                    USING (technology_key)
                 WHERE fact.value_status = 'reported'
                    AND technology.technology_group = 'renewable')
            """
        ).one()
        _add_check(
            checks,
            "hourly_energy.renewable_generation_total",
            renewable_totals[1],
            renewable_totals[0],
        )

        fact_load_total = _scalar(
            connection,
            "SELECT SUM(grid_load_mwh) FROM analytics.fact_electricity_hourly",
        )
        daily_load_total = _scalar(
            connection,
            "SELECT SUM(grid_load_mwh) FROM reporting.daily_energy",
        )
        monthly_load_total = _scalar(
            connection,
            "SELECT SUM(grid_load_mwh) FROM reporting.monthly_energy",
        )
        _add_check(
            checks,
            "daily_energy.load_total",
            fact_load_total,
            daily_load_total,
        )
        _add_check(
            checks,
            "monthly_energy.load_total",
            fact_load_total,
            monthly_load_total,
        )

        fact_negative_prices = int(
            _scalar(
                connection,
                """
                SELECT COUNT(*) FROM analytics.fact_electricity_hourly
                WHERE day_ahead_price_eur_per_mwh < 0
                """,
            )
        )
        daily_negative_prices = int(
            _scalar(
                connection,
                """
                SELECT SUM(negative_price_hour_count)
                FROM reporting.daily_energy
                """,
            )
        )
        monthly_negative_prices = int(
            _scalar(
                connection,
                """
                SELECT SUM(negative_price_hour_count)
                FROM reporting.monthly_energy
                """,
            )
        )
        _add_check(
            checks,
            "daily_energy.negative_price_hours",
            fact_negative_prices,
            daily_negative_prices,
        )
        _add_check(
            checks,
            "monthly_energy.negative_price_hours",
            fact_negative_prices,
            monthly_negative_prices,
        )

    return ReportingReconciliation(
        view_counts=view_counts,
        checks=tuple(checks),
    )
