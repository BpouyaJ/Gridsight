"""Deterministic Power BI semantic-model and report-design contract."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_MART_CONTRACT = PROJECT_ROOT / "reports" / "reporting_mart_contract.json"
DEFAULT_SAMPLE_MANIFEST = PROJECT_ROOT / "reports" / "sample_extract_manifest.json"
DEFAULT_KPI_SNAPSHOT = PROJECT_ROOT / "reports" / "kpi_snapshot.json"
DEFAULT_FINAL_EVALUATION = (
    PROJECT_ROOT / "reports" / "final_evaluation_snapshot.json"
)
DEFAULT_POWERBI_CONTRACT = (
    PROJECT_ROOT / "reports" / "powerbi_semantic_model_contract.json"
)
DEFAULT_DAX_CATALOGUE = PROJECT_ROOT / "powerbi" / "dax" / "measures.dax"

EXPECTED_PAGE_NAMES = (
    "Executive Overview",
    "Load & Renewables",
    "Price Analysis",
    "Forecast Performance",
    "Data Quality",
)
EXPECTED_SOURCE_HASHES = {
    "reporting_mart_contract": (
        "54a55962b79d14508eb50882578f2277b9201a678a055006c06f383632c71110"
    ),
    "sample_extract_manifest": (
        "b0a377003820b1321b6b55fb290f08ae07eff2f8e06e4688c9788b42ec42f150"
    ),
    "kpi_snapshot": (
        "fa03ee1af919027634aeb45a524c713274bd9effcac9955052d3be449c8395fc"
    ),
    "final_evaluation_snapshot": (
        "d65eea94653b1367ec169de60d4ff91fe2a956fa317040746c5a0a3c56fd3065"
    ),
}


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of one contract input or output."""
    digest = sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class TableContract:
    """One Power BI semantic-model table."""

    name: str
    role: str
    source_product: str
    source_kind: str
    grain: str
    key_columns: tuple[str, ...]
    storage_mode: str = "Import"
    hide_key_columns: bool = True


@dataclass(frozen=True)
class RelationshipContract:
    """One active single-direction model relationship."""

    from_table: str
    from_column: str
    to_table: str
    to_column: str
    cardinality: str = "one_to_many"
    cross_filter_direction: str = "single"
    active: bool = True


@dataclass(frozen=True)
class MeasureContract:
    """One explicit DAX measure with a declared unit and format."""

    name: str
    display_folder: str
    unit: str
    format_string: str
    dax: str
    description: str


@dataclass(frozen=True)
class VisualContract:
    """One required visual in a report-page wireframe."""

    visual_id: str
    visual_type: str
    title: str
    fields: tuple[str, ...]
    purpose: str


@dataclass(frozen=True)
class PageContract:
    """One required Power BI report page."""

    page_order: int
    page_name: str
    business_question: str
    default_filter: str
    visuals: tuple[VisualContract, ...]


TABLES = (
    TableContract(
        "Dim Date",
        "dimension",
        "daily_energy",
        "power_query_reference",
        "one Europe/Berlin calendar date",
        ("date_key",),
    ),
    TableContract(
        "Dim Month",
        "dimension",
        "monthly_energy",
        "power_query_reference",
        "one Europe/Berlin calendar month",
        ("month_key",),
    ),
    TableContract(
        "Dim Hour",
        "dimension",
        "hourly_energy",
        "power_query_reference",
        "one reporting hour label",
        ("hour_key",),
    ),
    TableContract(
        "Dim Technology",
        "dimension",
        "hourly_generation_by_technology",
        "power_query_reference",
        "one generation technology",
        ("technology_key",),
    ),
    TableContract(
        "Dim Horizon",
        "dimension",
        "generated_0_to_24",
        "generated",
        "one overall or forecast horizon step",
        ("horizon_step",),
    ),
    TableContract(
        "Dim Forecast Series",
        "dimension",
        "forecast_performance_summary",
        "power_query_reference",
        "one forecast series",
        ("forecast_name",),
    ),
    TableContract(
        "Fact Hourly Energy",
        "fact",
        "hourly_energy",
        "postgresql_view",
        "one canonical UTC hour",
        ("interval_start_utc",),
    ),
    TableContract(
        "Fact Hourly Generation",
        "fact",
        "hourly_generation_by_technology",
        "postgresql_view",
        "one canonical UTC hour and generation technology",
        ("interval_start_utc", "technology_key"),
    ),
    TableContract(
        "Fact Daily Energy",
        "fact",
        "daily_energy",
        "postgresql_view",
        "one Europe/Berlin calendar date",
        ("date_key",),
    ),
    TableContract(
        "Fact Monthly Energy",
        "fact",
        "monthly_energy",
        "postgresql_view",
        "one Europe/Berlin calendar month",
        ("month_key",),
    ),
    TableContract(
        "Fact Forecast Hourly",
        "fact",
        "forecast_performance_hourly",
        "postgresql_view",
        "one 2025 forecast origin and horizon step",
        ("forecast_origin_utc", "horizon_step"),
    ),
    TableContract(
        "Fact Forecast Summary",
        "fact",
        "forecast_performance_summary",
        "postgresql_view",
        "one forecast series and evaluation scope",
        ("forecast_name", "evaluation_scope", "horizon_step"),
    ),
    TableContract(
        "Data Quality Checks",
        "evidence",
        "data_quality_checks",
        "checked_csv",
        "one stable validation check",
        ("dataset", "check_id"),
    ),
    TableContract(
        "Source Lineage",
        "evidence",
        "source_lineage",
        "checked_csv",
        "one immutable registered SMARD export",
        ("export_id",),
    ),
    TableContract(
        "_Measures",
        "measure_table",
        "none",
        "calculated",
        "one hidden placeholder row",
        ("placeholder",),
    ),
)


RELATIONSHIPS = (
    RelationshipContract("Dim Date", "date_key", "Fact Hourly Energy", "date_key"),
    RelationshipContract(
        "Dim Date", "date_key", "Fact Hourly Generation", "date_key"
    ),
    RelationshipContract("Dim Date", "date_key", "Fact Daily Energy", "date_key"),
    RelationshipContract(
        "Dim Date", "date_key", "Fact Forecast Hourly", "target_date_key"
    ),
    RelationshipContract(
        "Dim Month", "month_key", "Fact Monthly Energy", "month_key"
    ),
    RelationshipContract("Dim Hour", "hour_key", "Fact Hourly Energy", "hour_key"),
    RelationshipContract(
        "Dim Hour", "hour_key", "Fact Hourly Generation", "hour_key"
    ),
    RelationshipContract(
        "Dim Hour", "hour_key", "Fact Forecast Hourly", "target_hour_key"
    ),
    RelationshipContract(
        "Dim Technology",
        "technology_key",
        "Fact Hourly Generation",
        "technology_key",
    ),
    RelationshipContract(
        "Dim Horizon", "horizon_step", "Fact Forecast Hourly", "horizon_step"
    ),
    RelationshipContract(
        "Dim Horizon", "horizon_step", "Fact Forecast Summary", "horizon_step"
    ),
    RelationshipContract(
        "Dim Forecast Series",
        "forecast_name",
        "Fact Forecast Summary",
        "forecast_name",
    ),
)


MEASURES = (
    MeasureContract(
        "Observed Hours",
        "Energy",
        "count",
        "#,0",
        "DISTINCTCOUNT('Fact Hourly Energy'[interval_start_utc])",
        "Unique canonical UTC hourly intervals in the current filter context.",
    ),
    MeasureContract(
        "Total Grid Load TWh",
        "Energy",
        "TWh",
        '0.000 "TWh"',
        "DIVIDE(SUM('Fact Hourly Energy'[grid_load_mwh]), 1000000)",
        "Grid-load energy summed over time and converted from MWh to TWh.",
    ),
    MeasureContract(
        "Average Grid Load GW",
        "Energy",
        "GW",
        '0.000 "GW"',
        "DIVIDE(AVERAGE('Fact Hourly Energy'[grid_load_mw]), 1000)",
        "Arithmetic mean of hourly average grid load, converted from MW to GW.",
    ),
    MeasureContract(
        "Peak Grid Load GW",
        "Energy",
        "GW",
        '0.000 "GW"',
        "DIVIDE(MAX('Fact Hourly Energy'[grid_load_mw]), 1000)",
        "Maximum observed hourly average grid load, converted from MW to GW.",
    ),
    MeasureContract(
        "Reported Generation TWh",
        "Generation",
        "TWh",
        '0.000 "TWh"',
        "DIVIDE(SUM('Fact Hourly Energy'[reported_generation_mwh]), 1000000)",
        "Reported generation energy summed over time and converted to TWh.",
    ),
    MeasureContract(
        "Renewable Generation TWh",
        "Generation",
        "TWh",
        '0.000 "TWh"',
        "DIVIDE(SUM('Fact Hourly Energy'[renewable_generation_mwh]), 1000000)",
        "Reported renewable generation summed over time and converted to TWh.",
    ),
    MeasureContract(
        "Technology Generation TWh",
        "Generation",
        "TWh",
        '0.000 "TWh"',
        (
            "DIVIDE(CALCULATE(SUM('Fact Hourly Generation'[generation_mwh]), "
            "'Fact Hourly Generation'[value_status] = \"reported\"), 1000000)"
        ),
        "Reported generation for the selected technology, converted to TWh.",
    ),
    MeasureContract(
        "Conventional Generation TWh",
        "Generation",
        "TWh",
        '0.000 "TWh"',
        "DIVIDE(SUM('Fact Hourly Energy'[conventional_generation_mwh]), 1000000)",
        "Reported conventional generation summed over time and converted to TWh.",
    ),
    MeasureContract(
        "Storage Generation TWh",
        "Generation",
        "TWh",
        '0.000 "TWh"',
        "DIVIDE(SUM('Fact Hourly Energy'[storage_generation_mwh]), 1000000)",
        "Reported pumped-storage generation summed over time and converted to TWh.",
    ),
    MeasureContract(
        "Renewable Share %",
        "Generation",
        "percent",
        "0.00%",
        "DIVIDE([Renewable Generation TWh], [Reported Generation TWh])",
        "Renewable reported generation divided by all reported generation.",
    ),
    MeasureContract(
        "Average Day-Ahead Price",
        "Price",
        "EUR/MWh",
        '#,0.00 "EUR/MWh"',
        "AVERAGE('Fact Hourly Energy'[day_ahead_price_eur_per_mwh])",
        "Arithmetic mean of hourly DE/LU day-ahead prices.",
    ),
    MeasureContract(
        "Daily Renewable Share %",
        "Price",
        "percent",
        "0.00%",
        (
            "DIVIDE(SUM('Fact Daily Energy'[renewable_generation_mwh]), "
            "SUM('Fact Daily Energy'[reported_generation_mwh]))"
        ),
        "Energy-weighted renewable share at the selected daily context.",
    ),
    MeasureContract(
        "Daily Average Day-Ahead Price",
        "Price",
        "EUR/MWh",
        '#,0.00 "EUR/MWh"',
        (
            "DIVIDE(SUMX('Fact Daily Energy', "
            "'Fact Daily Energy'[average_day_ahead_price_eur_per_mwh] * "
            "'Fact Daily Energy'[observed_hour_count]), "
            "SUM('Fact Daily Energy'[observed_hour_count]))"
        ),
        "Observed-hour-weighted day-ahead price from daily reporting rows.",
    ),
    MeasureContract(
        "Negative Price Hours",
        "Price",
        "count",
        "#,0",
        (
            "CALCULATE(COUNTROWS('Fact Hourly Energy'), "
            "'Fact Hourly Energy'[day_ahead_price_eur_per_mwh] < 0)"
        ),
        "Count of hourly DE/LU day-ahead prices below zero.",
    ),
    MeasureContract(
        "Negative Price Share %",
        "Price",
        "percent",
        "0.00%",
        "DIVIDE([Negative Price Hours], [Observed Hours])",
        "Negative-price hours divided by observed canonical hours.",
    ),
    MeasureContract(
        "Unavailable Generation Values",
        "Data Quality",
        "count",
        "#,0",
        "SUM('Fact Hourly Energy'[unavailable_technology_count])",
        "Unavailable hour/technology observations; never interpreted as zero.",
    ),
    MeasureContract(
        "Model MAE MW",
        "Forecast",
        "MW",
        '#,0.000 "MW"',
        "AVERAGE('Fact Forecast Hourly'[model_absolute_error_mw])",
        "Mean absolute error of the frozen selected model.",
    ),
    MeasureContract(
        "Actual Load MW",
        "Forecast",
        "MW",
        '#,0.000 "MW"',
        "AVERAGE('Fact Forecast Hourly'[actual_grid_load_mw])",
        "Actual hourly grid load for the frozen 2025 final-test rows.",
    ),
    MeasureContract(
        "Model Prediction MW",
        "Forecast",
        "MW",
        '#,0.000 "MW"',
        "AVERAGE('Fact Forecast Hourly'[model_prediction_mw])",
        "Selected-model prediction for the frozen 2025 final-test rows.",
    ),
    MeasureContract(
        "Model RMSE MW",
        "Forecast",
        "MW",
        '#,0.000 "MW"',
        (
            "SQRT(AVERAGEX('Fact Forecast Hourly', "
            "POWER('Fact Forecast Hourly'[model_error_mw], 2)))"
        ),
        "Root mean squared error of the frozen selected model.",
    ),
    MeasureContract(
        "Model MAPE %",
        "Forecast",
        "percent",
        "0.000%",
        (
            "AVERAGEX('Fact Forecast Hourly', "
            "DIVIDE(ABS('Fact Forecast Hourly'[model_error_mw]), "
            "'Fact Forecast Hourly'[actual_grid_load_mw]))"
        ),
        "Mean absolute percentage error of the frozen selected model.",
    ),
    MeasureContract(
        "Daily Baseline MAE MW",
        "Forecast",
        "MW",
        '#,0.000 "MW"',
        (
            "AVERAGEX('Fact Forecast Hourly', "
            "ABS('Fact Forecast Hourly'[daily_naive_prediction_mw] - "
            "'Fact Forecast Hourly'[actual_grid_load_mw]))"
        ),
        "Mean absolute error of the daily seasonal-naive baseline.",
    ),
    MeasureContract(
        "Weekly Baseline MAE MW",
        "Forecast",
        "MW",
        '#,0.000 "MW"',
        (
            "AVERAGEX('Fact Forecast Hourly', "
            "ABS('Fact Forecast Hourly'[weekly_naive_prediction_mw] - "
            "'Fact Forecast Hourly'[actual_grid_load_mw]))"
        ),
        "Mean absolute error of the weekly seasonal-naive baseline.",
    ),
    MeasureContract(
        "Model Improvement vs Weekly %",
        "Forecast",
        "percent",
        "0.000%",
        (
            "DIVIDE([Weekly Baseline MAE MW] - [Model MAE MW], "
            "[Weekly Baseline MAE MW])"
        ),
        "Relative MAE improvement of the selected model over the weekly baseline.",
    ),
    MeasureContract(
        "Selected Forecast MAE MW",
        "Forecast",
        "MW",
        '#,0.000 "MW"',
        (
            "SWITCH(SELECTEDVALUE('Dim Forecast Series'[forecast_name], "
            '"hist_gradient_boosting_31_leaves"), '
            '"daily_seasonal_naive", [Daily Baseline MAE MW], '
            '"weekly_seasonal_naive", [Weekly Baseline MAE MW], '
            "[Model MAE MW])"
        ),
        "MAE selected by the forecast-series slicer.",
    ),
    MeasureContract(
        "Overall Forecast MAE MW",
        "Forecast",
        "MW",
        '#,0.000 "MW"',
        (
            "CALCULATE(MAX('Fact Forecast Summary'[mae_mw]), "
            "'Fact Forecast Summary'[evaluation_scope] = \"overall\")"
        ),
        "Overall MAE for the forecast series selected in summary context.",
    ),
    MeasureContract(
        "Data Quality Checks",
        "Data Quality",
        "count",
        "#,0",
        "COUNTROWS('Data Quality Checks')",
        "Number of stable clean-data validation checks.",
    ),
    MeasureContract(
        "Passed Data Quality Checks",
        "Data Quality",
        "count",
        "#,0",
        (
            "CALCULATE(COUNTROWS('Data Quality Checks'), "
            "'Data Quality Checks'[status] = \"passed\")"
        ),
        "Number of clean-data checks with passing status.",
    ),
    MeasureContract(
        "Data Quality Pass Rate %",
        "Data Quality",
        "percent",
        "0.00%",
        "DIVIDE([Passed Data Quality Checks], [Data Quality Checks])",
        "Passing checks divided by all declared checks.",
    ),
    MeasureContract(
        "Registered Source Snapshots",
        "Data Quality",
        "count",
        "#,0",
        "COUNTROWS('Source Lineage')",
        "Number of immutable registered SMARD source exports.",
    ),
)


PAGES = (
    PageContract(
        1,
        "Executive Overview",
        "What changed across 2022-2025, and what should a decision-maker notice?",
        "All approved years; Europe/Berlin calendar",
        (
            VisualContract(
                "headline_cards",
                "card_group",
                "Portfolio KPIs",
                (
                    "Total Grid Load TWh",
                    "Renewable Share %",
                    "Average Day-Ahead Price",
                    "Model MAE MW",
                ),
                "Four headline outcomes with explicit units.",
            ),
            VisualContract(
                "annual_energy_trend",
                "line_and_clustered_column",
                "Annual Load and Renewable Share",
                (
                    "Dim Date[calendar_year]",
                    "Total Grid Load TWh",
                    "Renewable Share %",
                ),
                "Show annual system scale and generation-mix change together.",
            ),
            VisualContract(
                "annual_price_trend",
                "line_chart",
                "Average Day-Ahead Price by Year",
                ("Dim Date[calendar_year]", "Average Day-Ahead Price"),
                "Make the 2022 price regime visibly distinct.",
            ),
            VisualContract(
                "scope_note",
                "text_box",
                "Scope and Attribution",
                ("Bundesnetzagentur | SMARD.de",),
                "State source, years, geography, and interpretation limits.",
            ),
        ),
    ),
    PageContract(
        2,
        "Load & Renewables",
        "How do load, renewable output, and technology mix vary over time?",
        "All approved years; year and technology slicers visible",
        (
            VisualContract(
                "load_renewable_trend",
                "line_chart",
                "Grid Load and Renewable Generation",
                (
                    "Dim Date[calendar_date]",
                    "Average Grid Load GW",
                    "Renewable Generation TWh",
                ),
                "Compare demand level with renewable energy over time.",
            ),
            VisualContract(
                "generation_mix",
                "stacked_area_chart",
                "Generation by Technology",
                (
                    "Dim Date[calendar_date]",
                    "Dim Technology[technology_name]",
                    "Technology Generation TWh",
                ),
                (
                    "Expose technology composition without treating missing "
                    "values as zero."
                ),
            ),
            VisualContract(
                "load_shape",
                "line_chart",
                "Hourly Load Shape",
                (
                    "Dim Hour[hour_label]",
                    "Average Grid Load GW",
                    "Dim Date[is_weekend]",
                ),
                "Compare weekday and weekend load profiles.",
            ),
        ),
    ),
    PageContract(
        3,
        "Price Analysis",
        "When are prices negative or extreme, and how do they relate to renewables?",
        "All approved years; year and month slicers visible",
        (
            VisualContract(
                "price_trend",
                "line_chart",
                "DE/LU Day-Ahead Price",
                (
                    "Fact Hourly Energy[interval_start_utc]",
                    "Average Day-Ahead Price",
                ),
                "Retain negative prices and make the zero line visible.",
            ),
            VisualContract(
                "negative_price_cards",
                "card_group",
                "Negative-Price Exposure",
                ("Negative Price Hours", "Negative Price Share %"),
                "Quantify negative prices without confusing count and share.",
            ),
            VisualContract(
                "renewable_price_scatter",
                "scatter_chart",
                "Renewable Share vs Day-Ahead Price",
                (
                    "Daily Renewable Share %",
                    "Daily Average Day-Ahead Price",
                    "Dim Date[calendar_date]",
                ),
                "Show association while explicitly avoiding causal claims.",
            ),
        ),
    ),
    PageContract(
        4,
        "Forecast Performance",
        "Does the frozen model beat honest seasonal baselines, overall and by horizon?",
        "Final 2025 test only; selected model fixed",
        (
            VisualContract(
                "forecast_cards",
                "card_group",
                "Final Test Metrics",
                (
                    "Model MAE MW",
                    "Model RMSE MW",
                    "Model MAPE %",
                    "Model Improvement vs Weekly %",
                ),
                "Report frozen final-test metrics without further model selection.",
            ),
            VisualContract(
                "actual_vs_prediction",
                "line_chart",
                "Actual vs Model Load",
                (
                    "Fact Forecast Hourly[target_start_utc]",
                    "Actual Load MW",
                    "Model Prediction MW",
                ),
                "Show forecast tracking over a user-selected date range.",
            ),
            VisualContract(
                "error_by_horizon",
                "line_chart",
                "MAE by Horizon",
                (
                    "Dim Horizon[horizon_step]",
                    "Selected Forecast MAE MW",
                ),
                "Compare degradation across the 24 forecast horizons.",
            ),
            VisualContract(
                "model_baseline_comparison",
                "clustered_bar_chart",
                "Model and Baseline MAE",
                (
                    "Dim Forecast Series[forecast_name]",
                    "Overall Forecast MAE MW",
                ),
                "Keep the learned model and both seasonal baselines visible.",
            ),
        ),
    ),
    PageContract(
        5,
        "Data Quality",
        "Can a reviewer trace the data and verify the analytical gates?",
        "All checks and all six immutable source snapshots",
        (
            VisualContract(
                "quality_cards",
                "card_group",
                "Quality Gate",
                (
                    "Passed Data Quality Checks",
                    "Data Quality Pass Rate %",
                    "Unavailable Generation Values",
                    "Registered Source Snapshots",
                ),
                "Show passing controls and preserved source unavailability.",
            ),
            VisualContract(
                "quality_matrix",
                "matrix",
                "Validation Checks",
                (
                    "Data Quality Checks[dataset]",
                    "Data Quality Checks[check_id]",
                    "Data Quality Checks[status]",
                    "Data Quality Checks[expected]",
                    "Data Quality Checks[observed]",
                ),
                "Expose all 29 stable checks rather than only a green badge.",
            ),
            VisualContract(
                "lineage_table",
                "table",
                "Source Lineage",
                (
                    "Source Lineage[export_id]",
                    "Source Lineage[source_category]",
                    "Source Lineage[period_start]",
                    "Source Lineage[period_end]",
                    "Source Lineage[sha256]",
                ),
                "Make all six immutable SMARD registrations reviewable.",
            ),
        ),
    ),
)


ACCEPTANCE_VALUES = (
    ("Observed Hours", 35_064, 0),
    ("Total Grid Load TWh", 1_871.998, 0.001),
    ("Average Grid Load GW", 53.388, 0.001),
    ("Peak Grid Load GW", 78.681, 0.001),
    ("Renewable Share %", 0.5461, 0.0001),
    ("Average Day-Ahead Price", 124.58, 0.01),
    ("Negative Price Hours", 1_400, 0),
    ("Unavailable Generation Values", 16_836, 0),
    ("Model MAE MW", 1_398.259, 0.001),
    ("Model RMSE MW", 2_011.223, 0.001),
    ("Model MAPE %", 0.02652, 0.00001),
    ("Weekly Baseline MAE MW", 2_615.589, 0.001),
    ("Model Improvement vs Weekly %", 0.46541, 0.00001),
    ("Data Quality Checks", 29, 0),
    ("Data Quality Pass Rate %", 1.0, 0),
    ("Registered Source Snapshots", 6, 0),
)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return payload


def _source_record(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(PROJECT_ROOT).as_posix(),
        "sha256": sha256_file(path),
    }


def validate_powerbi_contracts() -> None:
    """Validate table, relationship, measure, and page design invariants."""
    table_names = [table.name for table in TABLES]
    if len(TABLES) != 15 or len(table_names) != len(set(table_names)):
        raise ValueError("Power BI table names must define 15 unique tables")
    table_by_name = {table.name: table for table in TABLES}
    if {table.storage_mode for table in TABLES} != {"Import"}:
        raise ValueError("Step 8.1 supports Import storage mode only")

    relationship_keys: set[tuple[str, str, str, str]] = set()
    if len(RELATIONSHIPS) != 12:
        raise ValueError("Power BI model must define exactly 12 relationships")
    for relationship in RELATIONSHIPS:
        key = (
            relationship.from_table,
            relationship.from_column,
            relationship.to_table,
            relationship.to_column,
        )
        if key in relationship_keys:
            raise ValueError("Duplicate Power BI relationship")
        relationship_keys.add(key)
        if (
            relationship.from_table not in table_by_name
            or relationship.to_table not in table_by_name
        ):
            raise ValueError("Relationship refers to an unknown table")
        if table_by_name[relationship.from_table].role != "dimension":
            raise ValueError("Relationship one-side must be a dimension")
        if table_by_name[relationship.to_table].role != "fact":
            raise ValueError(
                "Fact-to-fact and dimension-to-dimension relationships are forbidden"
            )
        if (
            relationship.cardinality != "one_to_many"
            or relationship.cross_filter_direction != "single"
            or not relationship.active
        ):
            raise ValueError(
                "Relationships must be active one-to-many and single-direction"
            )

    measure_names = [measure.name for measure in MEASURES]
    if len(MEASURES) != 30 or len(measure_names) != len(set(measure_names)):
        raise ValueError("Power BI measure catalogue must contain 30 unique measures")
    referenced_tables = {
        name
        for measure in MEASURES
        for name in re.findall(r"'([^']+)'\[", measure.dax)
    }
    if not referenced_tables <= set(table_names):
        raise ValueError("A DAX measure references an unknown table")
    if any(not measure.description.endswith(".") for measure in MEASURES):
        raise ValueError("Every DAX measure requires a complete description")
    if {measure.unit for measure in MEASURES} - {
        "count",
        "TWh",
        "GW",
        "MW",
        "EUR/MWh",
        "percent",
    }:
        raise ValueError("A DAX measure has an unsupported unit")

    page_names = tuple(page.page_name for page in PAGES)
    if page_names != EXPECTED_PAGE_NAMES:
        raise ValueError("Power BI pages or their order changed")
    known_fields = set(measure_names)
    for page in PAGES:
        visual_ids = [visual.visual_id for visual in page.visuals]
        if len(visual_ids) != len(set(visual_ids)) or len(visual_ids) < 3:
            raise ValueError(f"Page visual contract is invalid: {page.page_name}")
        for visual in page.visuals:
            for field in visual.fields:
                match = re.fullmatch(r"([^[]+)\[([^]]+)]", field)
                if match and match.group(1) not in table_by_name:
                    raise ValueError(f"Visual references unknown table: {field}")
                if (
                    not match
                    and field not in known_fields
                    and "| SMARD.de" not in field
                ):
                    raise ValueError(f"Visual references unknown measure: {field}")


def _validate_sources(
    mart_contract_path: Path,
    sample_manifest_path: Path,
    kpi_snapshot_path: Path,
    final_evaluation_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    paths = {
        "reporting_mart_contract": mart_contract_path,
        "sample_extract_manifest": sample_manifest_path,
        "kpi_snapshot": kpi_snapshot_path,
        "final_evaluation_snapshot": final_evaluation_path,
    }
    for source_name, path in paths.items():
        if sha256_file(path) != EXPECTED_SOURCE_HASHES[source_name]:
            raise ValueError(f"Frozen Power BI source changed: {source_name}")

    mart = _read_json(mart_contract_path)
    manifest = _read_json(sample_manifest_path)
    kpis = _read_json(kpi_snapshot_path)
    evaluation = _read_json(final_evaluation_path)
    if (
        mart.get("status") != "reporting_marts_and_samples_implemented"
        or len(mart.get("products", [])) != 8
        or manifest.get("status") != "passed"
        or manifest.get("sample_count") != 8
        or manifest.get("sample_rows") != 3_451
        or kpis.get("source_attribution") != "Bundesnetzagentur | SMARD.de"
        or evaluation.get("final_fit_contract", {}).get(
            "further_model_selection_allowed"
        )
        is not False
    ):
        raise ValueError("Power BI upstream semantic gate failed")
    return kpis, evaluation


def _validate_acceptance_sources(
    kpis: dict[str, Any], evaluation: dict[str, Any]
) -> None:
    headline = kpis["headline_kpis"]
    model = evaluation["test_evaluation"]["model"]["overall"]
    weekly = evaluation["test_evaluation"]["baselines"][
        "weekly_seasonal_naive"
    ]["overall"]
    comparison = evaluation["test_evaluation"]["comparison"]
    expected = {
        "Observed Hours": headline["observed_hour_count"],
        "Total Grid Load TWh": headline["total_grid_load_twh"],
        "Average Grid Load GW": headline["average_grid_load_gw"],
        "Peak Grid Load GW": headline["peak_grid_load_gw"],
        "Renewable Share %": (
            headline["renewable_share_of_reported_generation_percent"] / 100
        ),
        "Average Day-Ahead Price": headline[
            "average_day_ahead_price_eur_per_mwh"
        ],
        "Negative Price Hours": headline["negative_price_hour_count"],
        "Unavailable Generation Values": headline[
            "unavailable_generation_value_count"
        ],
        "Model MAE MW": model["mae_mw"],
        "Model RMSE MW": model["rmse_mw"],
        "Model MAPE %": model["mape_percent"] / 100,
        "Weekly Baseline MAE MW": weekly["mae_mw"],
        "Model Improvement vs Weekly %": (
            comparison["model_improvement_over_weekly_percent"] / 100
        ),
        "Data Quality Checks": 29,
        "Data Quality Pass Rate %": 1.0,
        "Registered Source Snapshots": 6,
    }
    for measure_name, value, tolerance in ACCEPTANCE_VALUES:
        if abs(float(expected[measure_name]) - float(value)) > max(
            float(tolerance), 1e-12
        ):
            raise ValueError(f"Power BI acceptance value changed: {measure_name}")


def build_powerbi_contract(
    *,
    mart_contract_path: Path = DEFAULT_MART_CONTRACT,
    sample_manifest_path: Path = DEFAULT_SAMPLE_MANIFEST,
    kpi_snapshot_path: Path = DEFAULT_KPI_SNAPSHOT,
    final_evaluation_path: Path = DEFAULT_FINAL_EVALUATION,
) -> dict[str, Any]:
    """Build the deterministic Step 8.1 design contract."""
    validate_powerbi_contracts()
    kpis, evaluation = _validate_sources(
        mart_contract_path,
        sample_manifest_path,
        kpi_snapshot_path,
        final_evaluation_path,
    )
    _validate_acceptance_sources(kpis, evaluation)
    source_paths = {
        "reporting_mart_contract": mart_contract_path,
        "sample_extract_manifest": sample_manifest_path,
        "kpi_snapshot": kpi_snapshot_path,
        "final_evaluation_snapshot": final_evaluation_path,
    }
    return {
        "schema_version": 1,
        "status": "design_frozen_for_desktop_build",
        "attribution": "Bundesnetzagentur | SMARD.de",
        "desktop_boundary": {
            "step_8_1": "versioned design contract and DAX catalogue",
            "step_8_2": "Power BI Desktop creates PBIP/PBIR/TMDL project files",
            "storage_mode": "Import",
            "report_definition_policy": "do not hand-author preview PBIR files",
        },
        "source": {
            name: _source_record(path) for name, path in source_paths.items()
        },
        "date_table": {
            "table": "Dim Date",
            "date_column": "calendar_date",
            "marked_as_date_table": True,
            "calendar": "Europe/Berlin",
            "start": "2022-01-01",
            "end": "2025-12-31",
            "unique_contiguous_dates": 1_461,
        },
        "tables": [asdict(table) for table in TABLES],
        "relationships": [asdict(relationship) for relationship in RELATIONSHIPS],
        "measures": [asdict(measure) for measure in MEASURES],
        "pages": [asdict(page) for page in PAGES],
        "acceptance_values": [
            {
                "measure": name,
                "expected_value": value,
                "tolerance": tolerance,
            }
            for name, value, tolerance in ACCEPTANCE_VALUES
        ],
        "model_rules": [
            "No fact-to-fact relationships",
            "No bidirectional relationships",
            "Every relationship is active one-to-many from dimension to fact",
            "UTC stays the unique fact timestamp; Europe/Berlin is for reporting",
            "MW, MWh, TWh, EUR/MWh, count, and percent remain distinct",
            "Base numeric columns use Do not summarize and report visuals use measures",
            "Foreign keys and technical lineage columns are hidden from report view",
            "The final 2025 forecast is evidence only and cannot drive model selection",
        ],
    }


def render_dax_catalogue() -> str:
    """Render deterministic copy-ready Power BI formula-bar definitions."""
    lines = [
        "// GridSight Power BI measure catalogue",
        "// Target table: _Measures",
        "// Generated from the tested Step 8.1 semantic-model contract.",
        "",
    ]
    current_folder = ""
    for measure in MEASURES:
        if measure.display_folder != current_folder:
            current_folder = measure.display_folder
            lines.extend((f"// [{current_folder}]", ""))
        lines.extend(
            (
                f"// {measure.description}",
                f"// Unit: {measure.unit}; Format: {measure.format_string}",
                f"{measure.name} =",
                measure.dax,
                "",
            )
        )
    return "\n".join(lines).rstrip() + "\n"


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.tmp")
    temporary_path.write_text(content, encoding="utf-8", newline="\n")
    temporary_path.replace(path)


def write_powerbi_artifacts(
    contract: dict[str, Any],
    *,
    contract_path: Path = DEFAULT_POWERBI_CONTRACT,
    dax_path: Path = DEFAULT_DAX_CATALOGUE,
) -> None:
    """Write deterministic JSON and DAX artifacts atomically."""
    payload = json.dumps(contract, indent=2, sort_keys=True) + "\n"
    _write_text_atomic(contract_path, payload)
    _write_text_atomic(dax_path, render_dax_catalogue())


def validate_written_powerbi_artifacts(
    *,
    contract_path: Path = DEFAULT_POWERBI_CONTRACT,
    dax_path: Path = DEFAULT_DAX_CATALOGUE,
) -> None:
    """Verify tracked artifacts exactly match the current code contract."""
    expected_contract = (
        json.dumps(build_powerbi_contract(), indent=2, sort_keys=True) + "\n"
    )
    if contract_path.read_text(encoding="utf-8") != expected_contract:
        raise ValueError("Tracked Power BI semantic-model contract is not current")
    if dax_path.read_text(encoding="utf-8") != render_dax_catalogue():
        raise ValueError("Tracked Power BI DAX catalogue is not current")
