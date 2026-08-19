"""Structured validation of the three canonical clean datasets."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from gridsight.transformation.consumption import (
    ARITHMETIC_TOLERANCE_MWH,
    CANONICAL_CONSUMPTION_COLUMNS,
    GRID_LOAD_MW_COLUMN,
    NONNEGATIVE_MEASURES,
)
from gridsight.transformation.generation import (
    CANONICAL_GENERATION_COLUMNS,
    GENERATION_MW_COLUMN,
    GENERATION_MWH_COLUMN,
    GENERATION_TECHNOLOGIES,
    IS_RENEWABLE_COLUMN,
    SOURCE_VALUE_TEXT_COLUMN,
    TECHNOLOGY_GROUP_COLUMN,
    TECHNOLOGY_ID_COLUMN,
    TECHNOLOGY_NAME_COLUMN,
    TECHNOLOGY_ORDER_COLUMN,
    VALUE_STATUS_COLUMN,
    VALUE_STATUS_REPORTED,
    VALUE_STATUS_UNAVAILABLE,
)
from gridsight.transformation.lineage import (
    SOURCE_CATEGORY_COLUMN,
    SOURCE_EXPORT_ID_COLUMN,
    SOURCE_GEOGRAPHY_COLUMN,
    SOURCE_RESOLUTION_COLUMN,
    SOURCE_SHA256_COLUMN,
)
from gridsight.transformation.price import (
    CANONICAL_PRICE_COLUMNS,
    CURRENCY_COLUMN,
    DAY_AHEAD_PRICE_COLUMN,
    MARKET_AREA_COLUMN,
    PRICE_UNIT_COLUMN,
)
from gridsight.transformation.time_normalization import (
    INTERVAL_END_UTC_COLUMN,
    INTERVAL_START_UTC_COLUMN,
)

STATUS_PASSED = "passed"
STATUS_FAILED = "failed"
SEVERITY_ERROR = "error"
ISSUE_COLUMNS = (
    "dataset",
    "check_id",
    "severity",
    "column",
    "affected_rows",
    "message",
)


@dataclass(frozen=True)
class CheckResult:
    """Machine-readable result of one stable validation check."""

    check_id: str
    dataset: str
    status: str
    expected: str
    observed: str


@dataclass(frozen=True)
class ValidationIssue:
    """One actionable data-quality failure."""

    dataset: str
    check_id: str
    severity: str
    column: str
    affected_rows: int
    message: str


@dataclass(frozen=True)
class ValidationReport:
    """Complete set of checks and issues for one clean-data run."""

    checks: tuple[CheckResult, ...]
    issues: tuple[ValidationIssue, ...]

    @property
    def status(self) -> str:
        """Return the overall machine-readable status."""
        if self.issues:
            return STATUS_FAILED
        return STATUS_PASSED


class _ReportBuilder:
    def __init__(self) -> None:
        self.checks: list[CheckResult] = []
        self.issues: list[ValidationIssue] = []

    def add(
        self,
        condition: bool,
        *,
        check_id: str,
        dataset: str,
        expected: object,
        observed: object,
        message: str,
        column: str = "",
        affected_rows: int = 0,
    ) -> None:
        status = STATUS_PASSED if condition else STATUS_FAILED
        self.checks.append(
            CheckResult(
                check_id=check_id,
                dataset=dataset,
                status=status,
                expected=str(expected),
                observed=str(observed),
            )
        )
        if not condition:
            self.issues.append(
                ValidationIssue(
                    dataset=dataset,
                    check_id=check_id,
                    severity=SEVERITY_ERROR,
                    column=column,
                    affected_rows=affected_rows,
                    message=message,
                )
            )

    def build(self) -> ValidationReport:
        return ValidationReport(tuple(self.checks), tuple(self.issues))


def _check_columns(
    builder: _ReportBuilder,
    frame: pd.DataFrame,
    dataset: str,
    expected_columns: tuple[str, ...],
) -> bool:
    observed_columns = tuple(str(column) for column in frame.columns)
    matches = observed_columns == expected_columns
    builder.add(
        matches,
        check_id=f"{dataset}.column_contract",
        dataset=dataset,
        expected=len(expected_columns),
        observed=len(observed_columns),
        message=f"{dataset} columns do not match the canonical contract",
    )
    return matches


def _check_lineage(
    builder: _ReportBuilder,
    frame: pd.DataFrame,
    dataset: str,
    category: str,
    geography: str,
) -> None:
    identity = (
        set(frame[SOURCE_CATEGORY_COLUMN].unique()) == {category}
        and set(frame[SOURCE_GEOGRAPHY_COLUMN].unique()) == {geography}
        and set(frame[SOURCE_RESOLUTION_COLUMN].unique()) == {"hour"}
    )
    builder.add(
        identity,
        check_id=f"{dataset}.lineage_identity",
        dataset=dataset,
        expected=f"{category}/{geography}/hour",
        observed="/".join(
            (
                ",".join(sorted(frame[SOURCE_CATEGORY_COLUMN].unique())),
                ",".join(sorted(frame[SOURCE_GEOGRAPHY_COLUMN].unique())),
                ",".join(sorted(frame[SOURCE_RESOLUTION_COLUMN].unique())),
            )
        ),
        message=f"{dataset} contains unexpected source lineage",
    )
    hashes = frame[SOURCE_SHA256_COLUMN].astype("string")
    valid_hashes = hashes.str.fullmatch(r"[0-9a-f]{64}").fillna(False)
    valid_sources = frame[SOURCE_EXPORT_ID_COLUMN].nunique() == 2
    builder.add(
        bool(valid_hashes.all()) and valid_sources,
        check_id=f"{dataset}.lineage_sources",
        dataset=dataset,
        expected="2 exports with lowercase SHA-256",
        observed=(
            f"{frame[SOURCE_EXPORT_ID_COLUMN].nunique()} exports, "
            f"{int((~valid_hashes).sum())} invalid hashes"
        ),
        message=f"{dataset} source lineage is incomplete",
        affected_rows=int((~valid_hashes).sum()),
    )


def _validate_consumption(
    builder: _ReportBuilder,
    frame: pd.DataFrame,
    expected_intervals: int,
) -> None:
    dataset = "consumption"
    columns_match = _check_columns(
        builder,
        frame,
        dataset,
        CANONICAL_CONSUMPTION_COLUMNS,
    )
    builder.add(
        len(frame) == expected_intervals,
        check_id="consumption.row_count",
        dataset=dataset,
        expected=expected_intervals,
        observed=len(frame),
        message="Consumption does not have one row per expected UTC hour",
        affected_rows=abs(len(frame) - expected_intervals),
    )
    if not columns_match:
        return

    duplicated = frame[INTERVAL_START_UTC_COLUMN].duplicated()
    builder.add(
        not duplicated.any(),
        check_id="consumption.unique_interval",
        dataset=dataset,
        expected="unique UTC starts",
        observed=f"{int(duplicated.sum())} duplicates",
        message="Consumption contains duplicate UTC intervals",
        column=INTERVAL_START_UTC_COLUMN,
        affected_rows=int(duplicated.sum()),
    )
    measures = (
        *NONNEGATIVE_MEASURES,
        "residual_load_mwh",
        GRID_LOAD_MW_COLUMN,
    )
    values = frame.loc[:, list(measures)].to_numpy(dtype="float64")
    finite = np.isfinite(values)
    builder.add(
        bool(finite.all()),
        check_id="consumption.finite_measures",
        dataset=dataset,
        expected="all finite",
        observed=f"{int((~finite).sum())} non-finite cells",
        message="Consumption contains non-finite numeric measures",
        affected_rows=int((~finite).any(axis=1).sum()),
    )
    nonnegative = frame.loc[:, list(NONNEGATIVE_MEASURES)] >= 0
    builder.add(
        bool(nonnegative.all().all()),
        check_id="consumption.nonnegative_measures",
        dataset=dataset,
        expected="all nonnegative",
        observed=f"{int((~nonnegative).sum().sum())} negative cells",
        message="Consumption contains a negative constrained measure",
        affected_rows=int((~nonnegative).any(axis=1).sum()),
    )
    identity_difference = (
        frame["grid_load_including_pumped_storage_mwh"]
        - frame["grid_load_mwh"]
        - frame["hydro_pumped_storage_mwh"]
    ).abs()
    identity_ok = identity_difference <= ARITHMETIC_TOLERANCE_MWH
    builder.add(
        bool(identity_ok.all()),
        check_id="consumption.grid_load_identity",
        dataset=dataset,
        expected=f"difference <= {ARITHMETIC_TOLERANCE_MWH}",
        observed=f"maximum {identity_difference.max():.6f}",
        message="Consumption grid-load identity is outside tolerance",
        affected_rows=int((~identity_ok).sum()),
    )
    mw_matches = np.isclose(
        frame[GRID_LOAD_MW_COLUMN],
        frame["grid_load_mwh"],
        rtol=0,
        atol=1e-12,
    )
    builder.add(
        bool(mw_matches.all()),
        check_id="consumption.hourly_power_identity",
        dataset=dataset,
        expected="grid_load_mw equals grid_load_mwh",
        observed=f"{int((~mw_matches).sum())} mismatches",
        message="Consumption hourly MW conversion is invalid",
        affected_rows=int((~mw_matches).sum()),
    )
    _check_lineage(builder, frame, dataset, "actual_consumption", "DE")


def _validate_generation(
    builder: _ReportBuilder,
    frame: pd.DataFrame,
    expected_intervals: int,
) -> None:
    dataset = "generation"
    columns_match = _check_columns(
        builder,
        frame,
        dataset,
        CANONICAL_GENERATION_COLUMNS,
    )
    expected_rows = expected_intervals * len(GENERATION_TECHNOLOGIES)
    builder.add(
        len(frame) == expected_rows,
        check_id="generation.row_count",
        dataset=dataset,
        expected=expected_rows,
        observed=len(frame),
        message="Generation does not have every technology for every hour",
        affected_rows=abs(len(frame) - expected_rows),
    )
    if not columns_match:
        return

    duplicated = frame.duplicated(
        subset=[INTERVAL_START_UTC_COLUMN, TECHNOLOGY_ID_COLUMN]
    )
    builder.add(
        not duplicated.any(),
        check_id="generation.unique_interval_technology",
        dataset=dataset,
        expected="unique UTC start and technology",
        observed=f"{int(duplicated.sum())} duplicates",
        message="Generation contains duplicate interval/technology keys",
        affected_rows=int(duplicated.sum()),
    )
    counts = frame.groupby(INTERVAL_START_UTC_COLUMN).size()
    complete = counts == len(GENERATION_TECHNOLOGIES)
    builder.add(
        bool(complete.all()),
        check_id="generation.complete_technology_set",
        dataset=dataset,
        expected=len(GENERATION_TECHNOLOGIES),
        observed=(
            f"range {int(counts.min()) if len(counts) else 0}-"
            f"{int(counts.max()) if len(counts) else 0}"
        ),
        message="A generation interval has an incomplete technology set",
        affected_rows=int((~complete).sum()),
    )
    expected_metadata = {
        (
            technology.technology_id,
            technology.technology_name,
            technology.technology_group,
            technology.is_renewable,
            order,
        )
        for order, technology in enumerate(GENERATION_TECHNOLOGIES, start=1)
    }
    metadata_columns = [
        TECHNOLOGY_ID_COLUMN,
        TECHNOLOGY_NAME_COLUMN,
        TECHNOLOGY_GROUP_COLUMN,
        IS_RENEWABLE_COLUMN,
        TECHNOLOGY_ORDER_COLUMN,
    ]
    observed_metadata = set(
        frame.loc[:, metadata_columns]
        .drop_duplicates()
        .itertuples(index=False, name=None)
    )
    builder.add(
        observed_metadata == expected_metadata,
        check_id="generation.technology_metadata",
        dataset=dataset,
        expected=len(expected_metadata),
        observed=len(observed_metadata),
        message="Generation technology metadata differs from the contract",
    )
    statuses = set(frame[VALUE_STATUS_COLUMN].unique())
    allowed_statuses = {VALUE_STATUS_REPORTED, VALUE_STATUS_UNAVAILABLE}
    builder.add(
        statuses <= allowed_statuses,
        check_id="generation.value_status_domain",
        dataset=dataset,
        expected=sorted(allowed_statuses),
        observed=sorted(statuses),
        message="Generation contains an unsupported value status",
    )
    unavailable = frame[VALUE_STATUS_COLUMN] == VALUE_STATUS_UNAVAILABLE
    unavailable_valid = (
        (frame[TECHNOLOGY_ID_COLUMN] == "nuclear")
        & (frame[SOURCE_VALUE_TEXT_COLUMN] == "-")
        & frame[GENERATION_MWH_COLUMN].isna()
        & frame[GENERATION_MW_COLUMN].isna()
    )
    invalid_unavailable = unavailable & ~unavailable_valid
    builder.add(
        not invalid_unavailable.any(),
        check_id="generation.unavailable_semantics",
        dataset=dataset,
        expected="nuclear marker with missing measures",
        observed=f"{int(invalid_unavailable.sum())} invalid rows",
        message="An unavailable generation row violates marker semantics",
        affected_rows=int(invalid_unavailable.sum()),
    )
    reported = frame[VALUE_STATUS_COLUMN] == VALUE_STATUS_REPORTED
    reported_values = frame.loc[
        reported,
        [GENERATION_MWH_COLUMN, GENERATION_MW_COLUMN],
    ].to_numpy(dtype="float64", na_value=np.nan)
    reported_valid = np.isfinite(reported_values) & (reported_values >= 0)
    builder.add(
        bool(reported_valid.all()),
        check_id="generation.reported_measures",
        dataset=dataset,
        expected="finite and nonnegative",
        observed=f"{int((~reported_valid).sum())} invalid cells",
        message="A reported generation value is missing or invalid",
        affected_rows=int((~reported_valid).any(axis=1).sum()),
    )
    mw_matches = np.isclose(
        reported_values[:, 0],
        reported_values[:, 1],
        rtol=0,
        atol=1e-12,
    )
    builder.add(
        bool(mw_matches.all()),
        check_id="generation.hourly_power_identity",
        dataset=dataset,
        expected="generation_mw equals generation_mwh",
        observed=f"{int((~mw_matches).sum())} mismatches",
        message="Generation hourly MW conversion is invalid",
        affected_rows=int((~mw_matches).sum()),
    )
    _check_lineage(builder, frame, dataset, "actual_generation", "DE")


def _validate_price(
    builder: _ReportBuilder,
    frame: pd.DataFrame,
    expected_intervals: int,
) -> None:
    dataset = "price"
    columns_match = _check_columns(
        builder,
        frame,
        dataset,
        CANONICAL_PRICE_COLUMNS,
    )
    builder.add(
        len(frame) == expected_intervals,
        check_id="price.row_count",
        dataset=dataset,
        expected=expected_intervals,
        observed=len(frame),
        message="Price does not have one row per expected UTC hour",
        affected_rows=abs(len(frame) - expected_intervals),
    )
    if not columns_match:
        return

    duplicated = frame[INTERVAL_START_UTC_COLUMN].duplicated()
    builder.add(
        not duplicated.any(),
        check_id="price.unique_interval",
        dataset=dataset,
        expected="unique UTC starts",
        observed=f"{int(duplicated.sum())} duplicates",
        message="Price contains duplicate UTC intervals",
        affected_rows=int(duplicated.sum()),
    )
    identity = (
        set(frame[MARKET_AREA_COLUMN].unique()) == {"DE-LU"}
        and set(frame[CURRENCY_COLUMN].unique()) == {"EUR"}
        and set(frame[PRICE_UNIT_COLUMN].unique()) == {"EUR/MWh"}
    )
    builder.add(
        identity,
        check_id="price.market_identity",
        dataset=dataset,
        expected="DE-LU/EUR/EUR/MWh",
        observed=(
            f"{frame[MARKET_AREA_COLUMN].nunique()} market(s), "
            f"{frame[CURRENCY_COLUMN].nunique()} currency value(s)"
        ),
        message="Price contains values outside the DE-LU market contract",
    )
    prices = frame[DAY_AHEAD_PRICE_COLUMN].to_numpy(dtype="float64")
    finite = np.isfinite(prices)
    builder.add(
        bool(finite.all()),
        check_id="price.finite_values",
        dataset=dataset,
        expected="all finite; negative values allowed",
        observed=f"{int((~finite).sum())} non-finite values",
        message="Price contains a non-finite value",
        affected_rows=int((~finite).sum()),
    )
    _check_lineage(builder, frame, dataset, "day_ahead_price", "DE-LU")


def _validate_cross_dataset(
    builder: _ReportBuilder,
    consumption: pd.DataFrame,
    generation: pd.DataFrame,
    price: pd.DataFrame,
) -> None:
    dataset = "cross_dataset"
    consumption_starts = pd.Index(consumption[INTERVAL_START_UTC_COLUMN])
    generation_starts = pd.Index(
        generation[INTERVAL_START_UTC_COLUMN].drop_duplicates()
    )
    price_starts = pd.Index(price[INTERVAL_START_UTC_COLUMN])
    spines_match = (
        consumption_starts.equals(generation_starts)
        and consumption_starts.equals(price_starts)
    )
    builder.add(
        spines_match,
        check_id="cross_dataset.utc_spine",
        dataset=dataset,
        expected=f"{len(consumption_starts)} identical UTC starts",
        observed=(
            f"consumption={len(consumption_starts)}, "
            f"generation={len(generation_starts)}, price={len(price_starts)}"
        ),
        message="Canonical datasets do not share the same UTC spine",
    )
    all_frames = (consumption, generation, price)
    one_hour = pd.Timedelta(hours=1)
    interval_valid = all(
        bool(
            (
                frame[INTERVAL_END_UTC_COLUMN]
                - frame[INTERVAL_START_UTC_COLUMN]
                == one_hour
            ).all()
        )
        for frame in all_frames
    )
    builder.add(
        interval_valid,
        check_id="cross_dataset.interval_duration",
        dataset=dataset,
        expected="all UTC intervals are one hour",
        observed="valid" if interval_valid else "invalid duration found",
        message="A canonical UTC interval is not one hour",
    )


def validate_clean_datasets(
    consumption: pd.DataFrame,
    generation: pd.DataFrame,
    price: pd.DataFrame,
    *,
    expected_intervals: int = 35_064,
) -> ValidationReport:
    """Run deterministic within- and cross-dataset validation checks."""
    builder = _ReportBuilder()
    _validate_consumption(builder, consumption, expected_intervals)
    _validate_generation(builder, generation, expected_intervals)
    _validate_price(builder, price, expected_intervals)
    required_time_columns = {
        INTERVAL_START_UTC_COLUMN,
        INTERVAL_END_UTC_COLUMN,
    }
    if all(required_time_columns <= set(frame.columns) for frame in (
        consumption,
        generation,
        price,
    )):
        _validate_cross_dataset(builder, consumption, generation, price)
    return builder.build()


def summarize_clean_datasets(
    consumption: pd.DataFrame,
    generation: pd.DataFrame,
    price: pd.DataFrame,
    outputs: dict[str, dict[str, str]],
) -> dict[str, dict[str, Any]]:
    """Build stable dataset metrics for the validation summary."""
    prices = price[DAY_AHEAD_PRICE_COLUMN]
    unavailable = generation[VALUE_STATUS_COLUMN] == VALUE_STATUS_UNAVAILABLE
    return {
        "consumption": {
            "rows": len(consumption),
            "columns": len(consumption.columns),
            "intervals": consumption[INTERVAL_START_UTC_COLUMN].nunique(),
            "first_utc_start": consumption.iloc[0][
                INTERVAL_START_UTC_COLUMN
            ].isoformat(),
            "last_utc_end": consumption.iloc[-1][
                INTERVAL_END_UTC_COLUMN
            ].isoformat(),
            **outputs["consumption"],
        },
        "generation": {
            "rows": len(generation),
            "columns": len(generation.columns),
            "intervals": generation[INTERVAL_START_UTC_COLUMN].nunique(),
            "technologies": generation[TECHNOLOGY_ID_COLUMN].nunique(),
            "reported_rows": int((~unavailable).sum()),
            "unavailable_rows": int(unavailable.sum()),
            "first_utc_start": generation.iloc[0][
                INTERVAL_START_UTC_COLUMN
            ].isoformat(),
            "last_utc_end": generation.iloc[-1][
                INTERVAL_END_UTC_COLUMN
            ].isoformat(),
            **outputs["generation"],
        },
        "price": {
            "rows": len(price),
            "columns": len(price.columns),
            "intervals": price[INTERVAL_START_UTC_COLUMN].nunique(),
            "negative_rows": int((prices < 0).sum()),
            "zero_rows": int((prices == 0).sum()),
            "positive_rows": int((prices > 0).sum()),
            "minimum_eur_per_mwh": float(prices.min()),
            "maximum_eur_per_mwh": float(prices.max()),
            "first_utc_start": price.iloc[0][
                INTERVAL_START_UTC_COLUMN
            ].isoformat(),
            "last_utc_end": price.iloc[-1][
                INTERVAL_END_UTC_COLUMN
            ].isoformat(),
            **outputs["price"],
        },
    }


def write_validation_artifacts(
    report: ValidationReport,
    datasets: dict[str, dict[str, Any]],
    issues_path: Path,
    summary_path: Path,
) -> None:
    """Atomically write deterministic CSV issues and JSON run summary."""
    issues_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    issues_temporary = issues_path.with_name(f".{issues_path.name}.tmp")
    summary_temporary = summary_path.with_name(f".{summary_path.name}.tmp")
    try:
        with issues_temporary.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=ISSUE_COLUMNS,
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerows(asdict(issue) for issue in report.issues)
        summary = {
            "schema_version": 1,
            "status": report.status,
            "check_counts": {
                "passed": sum(
                    check.status == STATUS_PASSED for check in report.checks
                ),
                "failed": sum(
                    check.status == STATUS_FAILED for check in report.checks
                ),
            },
            "issue_counts": {SEVERITY_ERROR: len(report.issues)},
            "datasets": datasets,
            "checks": [asdict(check) for check in report.checks],
        }
        summary_temporary.write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        issues_temporary.replace(issues_path)
        summary_temporary.replace(summary_path)
    finally:
        issues_temporary.unlink(missing_ok=True)
        summary_temporary.unlink(missing_ok=True)
