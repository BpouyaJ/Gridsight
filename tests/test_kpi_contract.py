"""Fast tests for the stable KPI query and artifact contracts."""

import json
from datetime import UTC, datetime
from decimal import Decimal

from gridsight.database.schema_contract import split_sql_statements
from gridsight.reporting.kpi_contract import (
    KPI_QUERY_CONTRACTS,
    KPIQueryResult,
    build_kpi_snapshot,
    validate_kpi_results,
    write_kpi_snapshot,
)


def _valid_results() -> tuple[KPIQueryResult, ...]:
    headline = {
        "period_start_utc": datetime(2021, 12, 31, 23, tzinfo=UTC),
        "period_end_utc": datetime(2025, 12, 31, 23, tzinfo=UTC),
        "observed_hour_count": 35_064,
        "total_grid_load_twh": Decimal("2.000"),
        "average_grid_load_gw": Decimal("57.000"),
        "minimum_grid_load_gw": Decimal("30.000"),
        "minimum_grid_load_utc": datetime(2022, 1, 1, tzinfo=UTC),
        "peak_grid_load_gw": Decimal("80.000"),
        "peak_grid_load_utc": datetime(2023, 1, 1, tzinfo=UTC),
        "reported_generation_twh": Decimal("1.900"),
        "renewable_generation_twh": Decimal("0.900"),
        "conventional_generation_twh": Decimal("0.950"),
        "storage_generation_twh": Decimal("0.050"),
        "renewable_share_of_reported_generation_percent": Decimal("47.37"),
        "average_day_ahead_price_eur_per_mwh": Decimal("80.00"),
        "median_day_ahead_price_eur_per_mwh": Decimal("75.00"),
        "minimum_day_ahead_price_eur_per_mwh": Decimal("-500.00"),
        "minimum_day_ahead_price_utc": datetime(2023, 7, 2, 12, tzinfo=UTC),
        "maximum_day_ahead_price_eur_per_mwh": Decimal("936.28"),
        "maximum_day_ahead_price_utc": datetime(2022, 8, 26, 18, tzinfo=UTC),
        "negative_price_hour_count": 1_400,
        "negative_price_hour_share_percent": Decimal("3.99"),
        "unavailable_generation_value_count": 16_836,
    }
    annual_rows = tuple(
        {
            "calendar_year": year,
            "observed_hour_count": hours,
            "grid_load_twh": Decimal("500.000"),
            "average_grid_load_gw": Decimal("57.000"),
            "peak_grid_load_gw": Decimal("80.000"),
            "reported_generation_twh": Decimal("475.000"),
            "renewable_generation_twh": Decimal("225.000"),
            "renewable_share_of_reported_generation_percent": Decimal("47.37"),
            "average_day_ahead_price_eur_per_mwh": Decimal("80.00"),
            "minimum_day_ahead_price_eur_per_mwh": Decimal("-500.00"),
            "maximum_day_ahead_price_eur_per_mwh": Decimal("936.28"),
            "negative_price_hour_count": 350,
            "unavailable_generation_value_count": 4_209,
        }
        for year, hours in ((2022, 8_760), (2023, 8_760), (2024, 8_784), (2025, 8_760))
    )
    technology_rows = tuple(
        {
            "technology_order": order,
            "technology_id": f"technology_{order}",
            "technology_name": f"Technology {order}",
            "technology_group": "renewable" if order <= 6 else "conventional",
            "is_renewable": order <= 6,
            "reported_hour_count": 35_064 - (16_836 if order == 12 else 0),
            "unavailable_hour_count": 16_836 if order == 12 else 0,
            "reported_value_coverage_percent": Decimal("100.00"),
            "generation_twh": Decimal("10.000"),
            "share_of_reported_generation_percent": Decimal("8.33"),
        }
        for order in range(1, 13)
    )
    rows_by_name = {
        "headline_kpis": (headline,),
        "annual_kpis": annual_rows,
        "generation_mix": technology_rows,
    }
    return tuple(
        KPIQueryResult(
            name=contract.name,
            columns=contract.columns,
            rows=rows_by_name[contract.name],
        )
        for contract in KPI_QUERY_CONTRACTS
    )


def test_kpi_queries_are_ordered_read_only_single_statements() -> None:
    """The analytical layer contains three bounded, non-mutating queries."""
    assert [contract.sql_path.name for contract in KPI_QUERY_CONTRACTS] == [
        "001_headline_kpis.sql",
        "002_annual_kpis.sql",
        "003_generation_mix.sql",
    ]
    forbidden_tokens = ("INSERT ", "UPDATE ", "DELETE ", "TRUNCATE ", "DROP ")
    for contract in KPI_QUERY_CONTRACTS:
        sql_text = contract.sql_path.read_text(encoding="utf-8")
        assert len(split_sql_statements(sql_text)) == 1
        assert not any(token in sql_text.upper() for token in forbidden_tokens)


def test_kpi_contracts_keep_grains_and_units_explicit() -> None:
    """KPI consumers cannot confuse hourly grains, energy, power, or price."""
    contracts = {contract.name: contract for contract in KPI_QUERY_CONTRACTS}
    assert contracts["headline_kpis"].expected_rows == 1
    assert contracts["annual_kpis"].expected_rows == 4
    assert contracts["generation_mix"].expected_rows == 12
    headline_columns = contracts["headline_kpis"].columns
    assert "total_grid_load_twh" in headline_columns
    assert "peak_grid_load_gw" in headline_columns
    assert "average_day_ahead_price_eur_per_mwh" in headline_columns
    assert "renewable_share_of_reported_generation_percent" in headline_columns
    assert all(
        len(contract.columns) == len(set(contract.columns))
        for contract in contracts.values()
    )


def test_kpi_snapshot_is_valid_deterministic_and_machine_readable(tmp_path) -> None:
    """Verified values serialize identically without a volatile run timestamp."""
    results = _valid_results()
    validate_kpi_results(results)
    snapshot = build_kpi_snapshot(results)
    output_path = tmp_path / "kpi_snapshot.json"

    write_kpi_snapshot(snapshot, output_path)
    first_bytes = output_path.read_bytes()
    write_kpi_snapshot(snapshot, output_path)

    assert output_path.read_bytes() == first_bytes
    parsed = json.loads(first_bytes)
    assert parsed["schema_version"] == 1
    assert parsed["period"]["start_utc"] == "2021-12-31T23:00:00+00:00"
    assert parsed["headline_kpis"]["total_grid_load_twh"] == 2.0
    assert len(parsed["annual_kpis"]) == 4
    assert len(parsed["generation_mix"]) == 12
    assert "generated_at" not in parsed
