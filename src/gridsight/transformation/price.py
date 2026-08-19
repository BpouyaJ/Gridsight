"""Canonical transformation for SMARD DE/LU day-ahead prices."""

from pathlib import Path

import numpy as np
import pandas as pd

from gridsight.ingestion.snapshot_registry import (
    load_export_definitions,
    read_manifest,
    sha256_file,
)
from gridsight.transformation.lineage import (
    LINEAGE_COLUMNS,
    SourceLineage,
    attach_source_lineage,
)
from gridsight.transformation.time_normalization import (
    DATASET_TIME_COLUMNS,
    INTERVAL_START_UTC_COLUMN,
    SOURCE_END_COLUMN,
    SOURCE_START_COLUMN,
    normalize_hourly_timestamps,
)

RAW_PRICE_TARGET_COLUMN = (
    "Germany/Luxembourg [€/MWh] Calculated resolutions"
)
RAW_PRICE_COLUMNS = (
    SOURCE_START_COLUMN,
    SOURCE_END_COLUMN,
    RAW_PRICE_TARGET_COLUMN,
    "∅ DE/LU neighbours [€/MWh] Calculated resolutions",
    "Belgium [€/MWh] Calculated resolutions",
    "Denmark 1 [€/MWh] Calculated resolutions",
    "Denmark 2 [€/MWh] Calculated resolutions",
    "France [€/MWh] Calculated resolutions",
    "Netherlands [€/MWh] Calculated resolutions",
    "Norway 2 [€/MWh] Calculated resolutions",
    "Austria [€/MWh] Calculated resolutions",
    "Poland [€/MWh] Calculated resolutions",
    "Sweden 4 [€/MWh] Calculated resolutions",
    "Switzerland [€/MWh] Calculated resolutions",
    "Czech Republic [€/MWh] Calculated resolutions",
    "DE/AT/LU [€/MWh] Calculated resolutions",
    "Northern Italy [€/MWh] Calculated resolutions",
    "Slovenia [€/MWh] Calculated resolutions",
    "Hungary [€/MWh] Calculated resolutions",
)
INTERVAL_DURATION_HOURS_COLUMN = "interval_duration_hours"
MARKET_AREA_COLUMN = "market_area"
CURRENCY_COLUMN = "currency"
PRICE_UNIT_COLUMN = "price_unit"
SOURCE_MEASURE_COLUMN = "source_measure_column"
SOURCE_VALUE_TEXT_COLUMN = "source_value_text"
DAY_AHEAD_PRICE_COLUMN = "day_ahead_price_eur_per_mwh"

CANONICAL_PRICE_COLUMNS = (
    *DATASET_TIME_COLUMNS,
    *LINEAGE_COLUMNS,
    INTERVAL_DURATION_HOURS_COLUMN,
    MARKET_AREA_COLUMN,
    CURRENCY_COLUMN,
    PRICE_UNIT_COLUMN,
    SOURCE_MEASURE_COLUMN,
    SOURCE_VALUE_TEXT_COLUMN,
    DAY_AHEAD_PRICE_COLUMN,
)
_ONE_HOUR = pd.Timedelta(hours=1)


def _parse_target_price(values: pd.Series) -> tuple[pd.Series, pd.Series]:
    raw_values = values.astype("string").fillna("").str.strip()
    numeric_values = pd.to_numeric(
        raw_values.str.replace(",", "", regex=False),
        errors="coerce",
    ).astype("float64")
    invalid = numeric_values.isna() | ~np.isfinite(numeric_values)
    if invalid.any():
        position = int(np.flatnonzero(invalid.to_numpy())[0])
        raise ValueError(
            f"{RAW_PRICE_TARGET_COLUMN} has a non-numeric value at row "
            f"{position}: {raw_values.iloc[position]!r}"
        )
    return raw_values, numeric_values


def transform_price_snapshot(
    frame: pd.DataFrame,
    lineage: SourceLineage,
) -> pd.DataFrame:
    """Select and transform only the approved DE/LU price series."""
    lineage.validate_for("day_ahead_price", "DE-LU")
    observed_columns = tuple(str(column) for column in frame.columns)
    if observed_columns != RAW_PRICE_COLUMNS:
        raise ValueError("Day-ahead-price source columns changed")

    transformed = normalize_hourly_timestamps(frame)
    source_text, prices = _parse_target_price(
        transformed[RAW_PRICE_TARGET_COLUMN]
    )
    output = transformed.loc[:, list(DATASET_TIME_COLUMNS)].copy()
    attach_source_lineage(output, lineage)
    output[INTERVAL_DURATION_HOURS_COLUMN] = 1.0
    output[MARKET_AREA_COLUMN] = "DE-LU"
    output[CURRENCY_COLUMN] = "EUR"
    output[PRICE_UNIT_COLUMN] = "EUR/MWh"
    output[SOURCE_MEASURE_COLUMN] = RAW_PRICE_TARGET_COLUMN
    output[SOURCE_VALUE_TEXT_COLUMN] = source_text
    output[DAY_AHEAD_PRICE_COLUMN] = prices
    return output.loc[:, list(CANONICAL_PRICE_COLUMNS)]


def combine_price_snapshots(snapshots: list[pd.DataFrame]) -> pd.DataFrame:
    """Combine clean price periods into one unique continuous UTC series."""
    if not snapshots:
        raise ValueError("At least one clean price snapshot is required")
    for snapshot in snapshots:
        if tuple(snapshot.columns) != CANONICAL_PRICE_COLUMNS:
            raise ValueError("Clean price columns do not match the contract")

    combined = pd.concat(snapshots, ignore_index=True)
    combined = combined.sort_values(
        INTERVAL_START_UTC_COLUMN,
        kind="stable",
        ignore_index=True,
    )
    starts = combined[INTERVAL_START_UTC_COLUMN]
    if starts.duplicated().any():
        raise ValueError("Combined price UTC starts are not unique")
    if not (starts.diff().dropna() == _ONE_HOUR).all():
        raise ValueError("Combined price UTC starts are not continuous")
    return combined


def load_price_dataset(
    config_path: Path,
    manifest_path: Path,
    raw_dir: Path,
) -> pd.DataFrame:
    """Load, transform, and combine both approved DE/LU price snapshots."""
    definitions = load_export_definitions(config_path)
    price_definitions = [
        definition
        for definition in definitions.values()
        if definition.source_category == "day_ahead_price"
    ]
    if len(price_definitions) != 2:
        raise ValueError("Exactly two day-ahead-price exports are required")

    records: dict[str, dict[str, str]] = {}
    for record in read_manifest(manifest_path):
        export_id = record["export_id"]
        if export_id in records:
            raise ValueError(f"Duplicate manifest export_id: {export_id}")
        records[export_id] = record

    transformed_snapshots: list[pd.DataFrame] = []
    for definition in price_definitions:
        record = records.get(definition.export_id)
        if record is None:
            raise ValueError(f"Missing manifest record: {definition.export_id}")
        raw_path = raw_dir / definition.local_filename
        if sha256_file(raw_path) != record["sha256"]:
            raise ValueError(f"Raw SHA-256 mismatch: {definition.export_id}")

        frame = pd.read_csv(
            raw_path,
            sep=";",
            encoding="utf-8-sig",
            dtype="string",
            keep_default_na=False,
        )
        lineage = SourceLineage.from_record(definition, record)
        transformed_snapshots.append(transform_price_snapshot(frame, lineage))

    return combine_price_snapshots(transformed_snapshots)


def write_price_csv(frame: pd.DataFrame, output_path: Path) -> None:
    """Atomically write the reproducible canonical DE/LU price CSV."""
    if tuple(frame.columns) != CANONICAL_PRICE_COLUMNS:
        raise ValueError("Cannot write price data outside its contract")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(f".{output_path.name}.tmp")
    try:
        frame.to_csv(
            temporary_path,
            index=False,
            encoding="utf-8",
            lineterminator="\n",
            float_format="%.2f",
            date_format="%Y-%m-%dT%H:%M:%S%z",
        )
        temporary_path.replace(output_path)
    finally:
        temporary_path.unlink(missing_ok=True)
