"""Fast tests for focused exploratory-analysis contracts and artifacts."""

import json
from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
import pytest

from gridsight.database.schema_contract import split_sql_statements
from gridsight.reporting.eda import (
    EDA_QUERY_CONTRACTS,
    EDAQueryResult,
    build_eda_snapshot,
    validate_eda_results,
    write_eda_figures,
    write_eda_snapshot,
)


def _monthly_rows() -> tuple[dict[str, object], ...]:
    months = pd.date_range("2022-01-01", periods=48, freq="MS")
    rows = []
    for index, month in enumerate(months):
        index_decimal = Decimal(index)
        rows.append(
            {
                "month_start": month.date(),
                "calendar_year": month.year,
                "month_number": month.month,
                "month_name": month.strftime("%B"),
                "observed_day_count": month.days_in_month,
                "observed_hour_count": 730 if index < 47 else 754,
                "grid_load_twh": Decimal("40.000") + index_decimal / 100,
                "average_grid_load_gw": Decimal("52.000") + index_decimal / 100,
                "peak_grid_load_gw": Decimal("70.000") + index_decimal / 100,
                "reported_generation_twh": Decimal("39.000") + index_decimal / 100,
                "renewable_generation_twh": (
                    Decimal("20.000") + index_decimal / 100
                ),
                "renewable_share_of_reported_generation_percent": (
                    Decimal("50.00") + index_decimal / 10
                ),
                "average_day_ahead_price_eur_per_mwh": (
                    Decimal("100.00") - index_decimal / 2
                ),
                "minimum_day_ahead_price_eur_per_mwh": Decimal("-10.00"),
                "maximum_day_ahead_price_eur_per_mwh": Decimal("300.00"),
                "negative_price_hour_count": index,
                "unavailable_generation_value_count": (
                    16_836 if index == 47 else 0
                ),
            }
        )
    return tuple(rows)


def _shape_rows() -> tuple[dict[str, object], ...]:
    rows = []
    for index, (day_type, hour_key) in enumerate(
        (day_type, hour_key)
        for day_type in ("weekday", "weekend")
        for hour_key in range(24)
    ):
        average = Decimal("45.000") + Decimal(hour_key) / 2
        rows.append(
            {
                "hour_key": hour_key,
                "hour_label": f"{hour_key:02d}:00",
                "day_type": day_type,
                "observed_hour_count": 730 if index < 47 else 754,
                "average_grid_load_gw": average,
                "p10_grid_load_gw": average - 5,
                "p90_grid_load_gw": average + 5,
            }
        )
    return tuple(rows)


def _daily_rows() -> tuple[dict[str, object], ...]:
    rows = []
    start = date(2022, 1, 1)
    for index in range(1_461):
        calendar_date = start + timedelta(days=index)
        renewable_share = Decimal(30 + index % 60)
        average_price = Decimal(200) - 2 * renewable_share + Decimal(index % 7)
        rows.append(
            {
                "calendar_date": calendar_date,
                "calendar_year": calendar_date.year,
                "month_number": calendar_date.month,
                "weekday_name": calendar_date.strftime("%A"),
                "is_weekend": calendar_date.weekday() >= 5,
                "observed_hour_count": 24,
                "grid_load_gwh": Decimal(1_000 + index % 100),
                "average_grid_load_gw": Decimal(45 + index % 24),
                "peak_grid_load_gw": Decimal(65 + index % 24),
                "renewable_generation_gwh": Decimal(500 + index % 200),
                "renewable_share_of_reported_generation_percent": (
                    renewable_share
                ),
                "average_day_ahead_price_eur_per_mwh": average_price,
                "minimum_day_ahead_price_eur_per_mwh": average_price - 20,
                "maximum_day_ahead_price_eur_per_mwh": average_price + 20,
                "negative_price_hour_count": index % 5,
                "unavailable_generation_value_count": (
                    16_836 if index == 1_460 else 0
                ),
            }
        )
    return tuple(rows)


def _valid_results() -> tuple[EDAQueryResult, ...]:
    rows_by_name = {
        "monthly_series": _monthly_rows(),
        "load_shape": _shape_rows(),
        "daily_relationships": _daily_rows(),
    }
    return tuple(
        EDAQueryResult(
            name=contract.name,
            columns=contract.columns,
            rows=rows_by_name[contract.name],
        )
        for contract in EDA_QUERY_CONTRACTS
    )


def _kpi_snapshot() -> dict[str, object]:
    return {
        "annual_kpis": [
            {
                "calendar_year": year,
                "grid_load_twh": 470 + index,
                "renewable_share_of_reported_generation_percent": 50 + index,
                "average_day_ahead_price_eur_per_mwh": 100 - index,
            }
            for index, year in enumerate(range(2022, 2026))
        ]
    }


def test_eda_queries_are_ordered_read_only_single_statements() -> None:
    """The three focused query files are stable and non-mutating."""
    assert [contract.sql_path.name for contract in EDA_QUERY_CONTRACTS] == [
        "004_monthly_eda.sql",
        "005_load_shape.sql",
        "006_daily_relationships.sql",
    ]
    forbidden_tokens = ("INSERT ", "UPDATE ", "DELETE ", "TRUNCATE ", "DROP ")
    for contract in EDA_QUERY_CONTRACTS:
        sql_text = contract.sql_path.read_text(encoding="utf-8")
        assert len(split_sql_statements(sql_text)) == 1
        assert not any(token in sql_text.upper() for token in forbidden_tokens)


def test_eda_snapshot_is_valid_deterministic_and_bounded(tmp_path) -> None:
    """The summary keeps declared grains, stable rankings, and no run time."""
    results = _valid_results()
    validate_eda_results(results)
    snapshot = build_eda_snapshot(results)
    output_path = tmp_path / "eda_snapshot.json"
    write_eda_snapshot(snapshot, output_path)
    first_bytes = output_path.read_bytes()
    write_eda_snapshot(snapshot, output_path)

    assert output_path.read_bytes() == first_bytes
    parsed = json.loads(first_bytes)
    assert len(parsed["monthly_series"]) == 48
    assert len(parsed["load_shape"]) == 48
    assert len(parsed["daily_correlations"]) == 5
    assert len(parsed["unusual_days"]) == 6
    assert parsed["unusual_days"][0]["calendar_date"] == "2022-01-24T00:00:00"
    assert "generated_at" not in parsed


def test_eda_validation_rejects_cross_grain_hour_mismatch() -> None:
    """A changed daily spine cannot silently feed findings or charts."""
    results = list(_valid_results())
    daily = results[2]
    changed_rows = list(daily.rows)
    changed_rows[0] = {**changed_rows[0], "observed_hour_count": 23}
    results[2] = EDAQueryResult(daily.name, daily.columns, tuple(changed_rows))
    with pytest.raises(RuntimeError, match="daily EDA hours"):
        validate_eda_results(tuple(results))


def test_eda_figure_writer_creates_four_png_files(tmp_path) -> None:
    """Every declared portfolio figure renders as a non-empty PNG."""
    pytest.importorskip("matplotlib")
    paths = write_eda_figures(_kpi_snapshot(), _valid_results(), tmp_path)

    assert [path.name for path in paths] == [
        "01_annual_kpis.png",
        "02_monthly_energy_market.png",
        "03_weekday_weekend_load_shape.png",
        "04_renewable_share_vs_price.png",
    ]
    assert all(path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n") for path in paths)
    assert all(path.stat().st_size > 10_000 for path in paths)
