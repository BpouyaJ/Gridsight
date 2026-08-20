"""Execute stable KPI queries and build a deterministic portfolio snapshot."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy.engine import Engine

from gridsight.database.schema_contract import PROJECT_ROOT, split_sql_statements

DEFAULT_KPI_SNAPSHOT = PROJECT_ROOT / "reports" / "kpi_snapshot.json"
SOURCE_ATTRIBUTION = "Bundesnetzagentur | SMARD.de"
SOURCE_VIEWS = (
    "reporting.hourly_energy",
    "reporting.hourly_generation_by_technology",
)


@dataclass(frozen=True)
class KPIQueryContract:
    """Expected SQL file, grain, ordered columns, and current-scope rows."""

    name: str
    sql_path: Path
    grain: str
    columns: tuple[str, ...]
    expected_rows: int


@dataclass(frozen=True)
class KPIQueryResult:
    """One query result after its ordered contract has been verified."""

    name: str
    columns: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]


KPI_QUERY_CONTRACTS = (
    KPIQueryContract(
        name="headline_kpis",
        sql_path=PROJECT_ROOT / "sql" / "analysis" / "001_headline_kpis.sql",
        grain="one row for the complete approved period",
        columns=(
            "period_start_utc",
            "period_end_utc",
            "observed_hour_count",
            "total_grid_load_twh",
            "average_grid_load_gw",
            "minimum_grid_load_gw",
            "minimum_grid_load_utc",
            "peak_grid_load_gw",
            "peak_grid_load_utc",
            "reported_generation_twh",
            "renewable_generation_twh",
            "conventional_generation_twh",
            "storage_generation_twh",
            "renewable_share_of_reported_generation_percent",
            "average_day_ahead_price_eur_per_mwh",
            "median_day_ahead_price_eur_per_mwh",
            "minimum_day_ahead_price_eur_per_mwh",
            "minimum_day_ahead_price_utc",
            "maximum_day_ahead_price_eur_per_mwh",
            "maximum_day_ahead_price_utc",
            "negative_price_hour_count",
            "negative_price_hour_share_percent",
            "unavailable_generation_value_count",
        ),
        expected_rows=1,
    ),
    KPIQueryContract(
        name="annual_kpis",
        sql_path=PROJECT_ROOT / "sql" / "analysis" / "002_annual_kpis.sql",
        grain="one Europe/Berlin calendar year",
        columns=(
            "calendar_year",
            "observed_hour_count",
            "grid_load_twh",
            "average_grid_load_gw",
            "peak_grid_load_gw",
            "reported_generation_twh",
            "renewable_generation_twh",
            "renewable_share_of_reported_generation_percent",
            "average_day_ahead_price_eur_per_mwh",
            "minimum_day_ahead_price_eur_per_mwh",
            "maximum_day_ahead_price_eur_per_mwh",
            "negative_price_hour_count",
            "unavailable_generation_value_count",
        ),
        expected_rows=4,
    ),
    KPIQueryContract(
        name="generation_mix",
        sql_path=PROJECT_ROOT / "sql" / "analysis" / "003_generation_mix.sql",
        grain="one generation technology for the complete approved period",
        columns=(
            "technology_order",
            "technology_id",
            "technology_name",
            "technology_group",
            "is_renewable",
            "reported_hour_count",
            "unavailable_hour_count",
            "reported_value_coverage_percent",
            "generation_twh",
            "share_of_reported_generation_percent",
        ),
        expected_rows=12,
    ),
)


def _execute_query(engine: Engine, contract: KPIQueryContract) -> KPIQueryResult:
    sql_text = contract.sql_path.read_text(encoding="utf-8")
    statements = split_sql_statements(sql_text)
    if len(statements) != 1:
        raise ValueError(
            f"{contract.sql_path.name} must contain exactly one SQL statement"
        )
    with engine.connect() as connection:
        result = connection.exec_driver_sql(statements[0])
        observed_columns = tuple(result.keys())
        rows = tuple(dict(row) for row in result.mappings())

    if observed_columns != contract.columns:
        raise RuntimeError(
            f"KPI column contract mismatch for {contract.name}: "
            f"expected {contract.columns}, observed {observed_columns}"
        )
    if len(rows) != contract.expected_rows:
        raise RuntimeError(
            f"KPI row contract mismatch for {contract.name}: "
            f"expected {contract.expected_rows}, observed {len(rows)}"
        )
    return KPIQueryResult(
        name=contract.name,
        columns=observed_columns,
        rows=rows,
    )


def _result_map(
    results: tuple[KPIQueryResult, ...],
) -> dict[str, KPIQueryResult]:
    result_map = {result.name: result for result in results}
    expected_names = {contract.name for contract in KPI_QUERY_CONTRACTS}
    if set(result_map) != expected_names or len(result_map) != len(results):
        raise RuntimeError("KPI result set does not match the declared query contracts")
    return result_map


def validate_kpi_results(results: tuple[KPIQueryResult, ...]) -> None:
    """Reject data that violates the approved period and KPI grains."""
    result_map = _result_map(results)
    for contract in KPI_QUERY_CONTRACTS:
        result = result_map[contract.name]
        if result.columns != contract.columns:
            raise RuntimeError(f"KPI column contract mismatch for {contract.name}")
        if len(result.rows) != contract.expected_rows:
            raise RuntimeError(f"KPI row contract mismatch for {contract.name}")
    headline = result_map["headline_kpis"].rows[0]
    annual_rows = result_map["annual_kpis"].rows
    technology_rows = result_map["generation_mix"].rows

    if headline["observed_hour_count"] != 35_064:
        raise RuntimeError("headline KPI hour count must equal 35,064")
    if [row["calendar_year"] for row in annual_rows] != [2022, 2023, 2024, 2025]:
        raise RuntimeError("annual KPI years must be ordered from 2022 through 2025")
    if sum(row["observed_hour_count"] for row in annual_rows) != 35_064:
        raise RuntimeError("annual KPI hour counts do not reconcile to the headline")
    if [row["technology_order"] for row in technology_rows] != list(range(1, 13)):
        raise RuntimeError(
            "generation-mix technologies must retain orders 1 through 12"
        )
    if any(
        row["reported_hour_count"] + row["unavailable_hour_count"] != 35_064
        for row in technology_rows
    ):
        raise RuntimeError("each technology must cover every approved hourly interval")
    unavailable_values = sum(
        row["unavailable_hour_count"] for row in technology_rows
    )
    if unavailable_values != headline["unavailable_generation_value_count"]:
        raise RuntimeError(
            "generation-mix unavailable values do not reconcile to the headline"
        )


def run_kpi_queries(engine: Engine) -> tuple[KPIQueryResult, ...]:
    """Execute all ordered queries and enforce their current-scope contracts."""
    results = tuple(
        _execute_query(engine, contract) for contract in KPI_QUERY_CONTRACTS
    )
    validate_kpi_results(results)
    return results


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if value is None or isinstance(value, (bool, float, int, str)):
        return value
    raise TypeError(f"Unsupported KPI value type: {type(value).__name__}")


def _json_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: _json_value(value) for key, value in row.items()}


def build_kpi_snapshot(results: tuple[KPIQueryResult, ...]) -> dict[str, Any]:
    """Convert verified query results into a deterministic portfolio artifact."""
    validate_kpi_results(results)
    result_map = _result_map(results)
    headline = _json_row(result_map["headline_kpis"].rows[0])
    contracts = {
        contract.name: {
            "grain": contract.grain,
            "row_count": contract.expected_rows,
            "sql_file": contract.sql_path.relative_to(PROJECT_ROOT).as_posix(),
        }
        for contract in KPI_QUERY_CONTRACTS
    }
    return {
        "schema_version": 1,
        "source_attribution": SOURCE_ATTRIBUTION,
        "source_views": list(SOURCE_VIEWS),
        "period": {
            "start_utc": headline["period_start_utc"],
            "end_utc": headline["period_end_utc"],
        },
        "units": {
            "energy": "TWh",
            "power": "GW",
            "price": "EUR/MWh",
            "share": "percent",
        },
        "query_contracts": contracts,
        "headline_kpis": headline,
        "annual_kpis": [
            _json_row(row) for row in result_map["annual_kpis"].rows
        ],
        "generation_mix": [
            _json_row(row) for row in result_map["generation_mix"].rows
        ],
    }


def write_kpi_snapshot(snapshot: dict[str, Any], output_path: Path) -> None:
    """Write deterministic JSON atomically so partial artifacts cannot remain."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(f"{output_path.suffix}.tmp")
    payload = json.dumps(snapshot, indent=2, sort_keys=True) + "\n"
    temporary_path.write_text(payload, encoding="utf-8", newline="\n")
    temporary_path.replace(output_path)


def sha256_file(path: Path) -> str:
    """Return a lowercase SHA-256 digest for a generated KPI artifact."""
    return hashlib.sha256(path.read_bytes()).hexdigest()
