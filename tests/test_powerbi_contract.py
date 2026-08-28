"""Fast tests for the Power BI semantic-model design contract."""

from pathlib import Path

import pytest

from gridsight.reporting.powerbi_contract import (
    EXPECTED_PAGE_NAMES,
    MEASURES,
    PAGES,
    RELATIONSHIPS,
    TABLES,
    build_powerbi_contract,
    render_dax_catalogue,
    validate_powerbi_contracts,
    write_powerbi_artifacts,
)


def test_model_is_a_single_direction_star_schema() -> None:
    validate_powerbi_contracts()

    roles = {table.name: table.role for table in TABLES}
    assert len(TABLES) == 15
    assert len(RELATIONSHIPS) == 12
    assert all(
        roles[relationship.from_table] == "dimension"
        and roles[relationship.to_table] == "fact"
        and relationship.cardinality == "one_to_many"
        and relationship.cross_filter_direction == "single"
        and relationship.active
        for relationship in RELATIONSHIPS
    )


def test_date_table_and_pages_are_explicit() -> None:
    contract = build_powerbi_contract()

    assert contract["date_table"] == {
        "table": "Dim Date",
        "date_column": "calendar_date",
        "marked_as_date_table": True,
        "calendar": "Europe/Berlin",
        "start": "2022-01-01",
        "end": "2025-12-31",
        "unique_contiguous_dates": 1_461,
    }
    assert tuple(page.page_name for page in PAGES) == EXPECTED_PAGE_NAMES
    assert [page["page_name"] for page in contract["pages"]] == list(
        EXPECTED_PAGE_NAMES
    )


def test_measure_catalogue_keeps_units_and_metric_semantics_explicit() -> None:
    measures = {measure.name: measure for measure in MEASURES}

    assert len(measures) == 30
    assert "SUM('Fact Hourly Energy'[grid_load_mwh])" in measures[
        "Total Grid Load TWh"
    ].dax
    assert "AVERAGE('Fact Hourly Energy'[grid_load_mw])" in measures[
        "Average Grid Load GW"
    ].dax
    assert measures["Renewable Share %"].format_string == "0.00%"
    assert "value_status" in measures["Technology Generation TWh"].dax
    assert "observed_hour_count" in measures[
        "Daily Average Day-Ahead Price"
    ].dax
    assert "Weekly Baseline MAE MW" in measures[
        "Model Improvement vs Weekly %"
    ].dax
    assert "further model selection" in next(
        page.default_filter
        for page in PAGES
        if page.page_name == "Forecast Performance"
    ).lower() or any(
        "without further model selection" in visual.purpose
        for page in PAGES
        for visual in page.visuals
    )


def test_contract_and_dax_outputs_are_byte_deterministic(tmp_path: Path) -> None:
    contract = build_powerbi_contract()
    contract_path = tmp_path / "contract.json"
    dax_path = tmp_path / "measures.dax"
    write_powerbi_artifacts(
        contract,
        contract_path=contract_path,
        dax_path=dax_path,
    )
    first_contract = contract_path.read_bytes()
    first_dax = dax_path.read_bytes()
    write_powerbi_artifacts(
        contract,
        contract_path=contract_path,
        dax_path=dax_path,
    )

    assert contract_path.read_bytes() == first_contract
    assert dax_path.read_bytes() == first_dax
    assert dax_path.read_text(encoding="utf-8") == render_dax_catalogue()


def test_contract_rejects_changed_frozen_source(tmp_path: Path) -> None:
    changed_kpi = tmp_path / "kpi_snapshot.json"
    changed_kpi.write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="kpi_snapshot"):
        build_powerbi_contract(kpi_snapshot_path=changed_kpi)
