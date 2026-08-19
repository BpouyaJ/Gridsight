"""Canonical transformation for SMARD actual-consumption snapshots."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from gridsight.ingestion.snapshot_registry import (
    ExportDefinition,
    load_export_definitions,
    read_manifest,
    sha256_file,
)
from gridsight.transformation.time_normalization import (
    INTERVAL_END_LOCAL_COLUMN,
    INTERVAL_END_UTC_COLUMN,
    INTERVAL_START_LOCAL_COLUMN,
    INTERVAL_START_UTC_COLUMN,
    IS_DST_COLUMN,
    LOCAL_FOLD_COLUMN,
    SOURCE_END_COLUMN,
    SOURCE_END_TEXT_COLUMN,
    SOURCE_START_COLUMN,
    SOURCE_START_TEXT_COLUMN,
    UTC_OFFSET_MINUTES_COLUMN,
    normalize_hourly_timestamps,
)

RAW_GRID_LOAD_COLUMN = "grid load [MWh] Calculated resolutions"
RAW_GRID_LOAD_INCLUDING_PUMPED_COLUMN = (
    "Grid load incl. hydro pumped storage [MWh] Calculated resolutions"
)
RAW_PUMPED_STORAGE_COLUMN = (
    "Hydro pumped storage [MWh] Calculated resolutions"
)
RAW_RESIDUAL_LOAD_COLUMN = "Residual load [MWh] Calculated resolutions"
RAW_TO_CANONICAL_MEASURES = {
    RAW_GRID_LOAD_COLUMN: "grid_load_mwh",
    RAW_GRID_LOAD_INCLUDING_PUMPED_COLUMN: (
        "grid_load_including_pumped_storage_mwh"
    ),
    RAW_PUMPED_STORAGE_COLUMN: "hydro_pumped_storage_mwh",
    RAW_RESIDUAL_LOAD_COLUMN: "residual_load_mwh",
}
RAW_CONSUMPTION_COLUMNS = (
    SOURCE_START_COLUMN,
    SOURCE_END_COLUMN,
    *RAW_TO_CANONICAL_MEASURES,
)
NONNEGATIVE_MEASURES = (
    "grid_load_mwh",
    "grid_load_including_pumped_storage_mwh",
    "hydro_pumped_storage_mwh",
)
ARITHMETIC_TOLERANCE_MWH = 0.011

SOURCE_EXPORT_ID_COLUMN = "source_export_id"
SOURCE_CATEGORY_COLUMN = "source_category"
SOURCE_GEOGRAPHY_COLUMN = "source_geography"
SOURCE_RESOLUTION_COLUMN = "source_resolution"
SOURCE_PERIOD_START_COLUMN = "source_period_start"
SOURCE_PERIOD_END_COLUMN = "source_period_end"
SOURCE_ORIGINAL_FILENAME_COLUMN = "source_original_filename"
SOURCE_FILENAME_COLUMN = "source_filename"
SOURCE_SHA256_COLUMN = "source_sha256"
INTERVAL_DURATION_HOURS_COLUMN = "interval_duration_hours"
GRID_LOAD_MW_COLUMN = "grid_load_mw"

CANONICAL_CONSUMPTION_COLUMNS = (
    INTERVAL_START_UTC_COLUMN,
    INTERVAL_END_UTC_COLUMN,
    INTERVAL_START_LOCAL_COLUMN,
    INTERVAL_END_LOCAL_COLUMN,
    UTC_OFFSET_MINUTES_COLUMN,
    IS_DST_COLUMN,
    LOCAL_FOLD_COLUMN,
    SOURCE_START_TEXT_COLUMN,
    SOURCE_END_TEXT_COLUMN,
    SOURCE_EXPORT_ID_COLUMN,
    SOURCE_CATEGORY_COLUMN,
    SOURCE_GEOGRAPHY_COLUMN,
    SOURCE_RESOLUTION_COLUMN,
    SOURCE_PERIOD_START_COLUMN,
    SOURCE_PERIOD_END_COLUMN,
    SOURCE_ORIGINAL_FILENAME_COLUMN,
    SOURCE_FILENAME_COLUMN,
    SOURCE_SHA256_COLUMN,
    INTERVAL_DURATION_HOURS_COLUMN,
    "grid_load_mwh",
    GRID_LOAD_MW_COLUMN,
    "grid_load_including_pumped_storage_mwh",
    "hydro_pumped_storage_mwh",
    "residual_load_mwh",
)
_ONE_HOUR = pd.Timedelta(hours=1)


@dataclass(frozen=True)
class SnapshotLineage:
    """Row-level source lineage copied from an approved manifest record."""

    export_id: str
    source_category: str
    source_geography: str
    source_resolution: str
    period_start: str
    period_end: str
    original_filename: str
    local_filename: str
    sha256: str

    @classmethod
    def from_record(
        cls,
        definition: ExportDefinition,
        record: dict[str, str],
    ) -> "SnapshotLineage":
        """Create validated transformation lineage from config and manifest."""
        matching_fields = (
            "export_id",
            "source_category",
            "source_geography",
            "source_resolution",
            "period_start",
            "period_end",
            "local_filename",
        )
        for field in matching_fields:
            if record[field] != getattr(definition, field):
                raise ValueError(
                    f"Manifest {field} mismatch for {definition.export_id}"
                )

        return cls(
            export_id=record["export_id"],
            source_category=record["source_category"],
            source_geography=record["source_geography"],
            source_resolution=record["source_resolution"],
            period_start=record["period_start"],
            period_end=record["period_end"],
            original_filename=record["original_filename"],
            local_filename=record["local_filename"],
            sha256=record["sha256"],
        )


def _parse_numeric_measure(values: pd.Series, column_name: str) -> pd.Series:
    raw_values = values.astype("string").str.strip()
    numeric_values = pd.to_numeric(
        raw_values.str.replace(",", "", regex=False),
        errors="coerce",
    ).astype("float64")
    invalid = numeric_values.isna() | ~np.isfinite(numeric_values)
    if invalid.any():
        position = int(np.flatnonzero(invalid.to_numpy())[0])
        raise ValueError(
            f"{column_name} has a non-numeric value at row {position}: "
            f"{raw_values.iloc[position]!r}"
        )
    return numeric_values


def _validate_lineage(lineage: SnapshotLineage) -> None:
    if lineage.source_category != "actual_consumption":
        raise ValueError("Consumption transformation requires its source category")
    if lineage.source_geography != "DE":
        raise ValueError("Consumption transformation requires DE geography")
    if lineage.source_resolution != "hour":
        raise ValueError("Consumption transformation requires hourly resolution")
    if len(lineage.sha256) != 64 or any(
        character not in "0123456789abcdef" for character in lineage.sha256
    ):
        raise ValueError("Consumption lineage requires a lowercase SHA-256")


def transform_consumption_snapshot(
    frame: pd.DataFrame,
    lineage: SnapshotLineage,
) -> pd.DataFrame:
    """Transform one source-compatible consumption frame into clean columns."""
    _validate_lineage(lineage)
    observed_columns = tuple(str(column) for column in frame.columns)
    if observed_columns != RAW_CONSUMPTION_COLUMNS:
        raise ValueError("Actual-consumption source columns changed")

    transformed = normalize_hourly_timestamps(frame)
    for raw_name, canonical_name in RAW_TO_CANONICAL_MEASURES.items():
        transformed[canonical_name] = _parse_numeric_measure(
            transformed.pop(raw_name),
            raw_name,
        )

    for measure in NONNEGATIVE_MEASURES:
        if (transformed[measure] < 0).any():
            raise ValueError(f"{measure} contains negative energy")

    identity_difference = (
        transformed["grid_load_including_pumped_storage_mwh"]
        - transformed["grid_load_mwh"]
        - transformed["hydro_pumped_storage_mwh"]
    ).abs()
    if (identity_difference > ARITHMETIC_TOLERANCE_MWH).any():
        raise ValueError(
            "Grid load including pumped storage violates its source identity"
        )

    transformed[INTERVAL_DURATION_HOURS_COLUMN] = 1.0
    transformed[GRID_LOAD_MW_COLUMN] = (
        transformed["grid_load_mwh"]
        / transformed[INTERVAL_DURATION_HOURS_COLUMN]
    )
    transformed[SOURCE_EXPORT_ID_COLUMN] = lineage.export_id
    transformed[SOURCE_CATEGORY_COLUMN] = lineage.source_category
    transformed[SOURCE_GEOGRAPHY_COLUMN] = lineage.source_geography
    transformed[SOURCE_RESOLUTION_COLUMN] = lineage.source_resolution
    transformed[SOURCE_PERIOD_START_COLUMN] = lineage.period_start
    transformed[SOURCE_PERIOD_END_COLUMN] = lineage.period_end
    transformed[SOURCE_ORIGINAL_FILENAME_COLUMN] = lineage.original_filename
    transformed[SOURCE_FILENAME_COLUMN] = lineage.local_filename
    transformed[SOURCE_SHA256_COLUMN] = lineage.sha256

    return transformed.loc[:, list(CANONICAL_CONSUMPTION_COLUMNS)]


def combine_consumption_snapshots(
    snapshots: list[pd.DataFrame],
) -> pd.DataFrame:
    """Combine clean snapshots and enforce one continuous UTC time series."""
    if not snapshots:
        raise ValueError("At least one clean consumption snapshot is required")
    for snapshot in snapshots:
        if tuple(snapshot.columns) != CANONICAL_CONSUMPTION_COLUMNS:
            raise ValueError("Clean consumption columns do not match the contract")

    combined = pd.concat(snapshots, ignore_index=True)
    combined = combined.sort_values(
        INTERVAL_START_UTC_COLUMN,
        kind="stable",
        ignore_index=True,
    )
    starts = combined[INTERVAL_START_UTC_COLUMN]
    if starts.duplicated().any():
        raise ValueError("Combined consumption UTC starts are not unique")
    differences = starts.diff().dropna()
    if not (differences == _ONE_HOUR).all():
        raise ValueError("Combined consumption UTC starts are not continuous")
    return combined


def load_consumption_dataset(
    config_path: Path,
    manifest_path: Path,
    raw_dir: Path,
) -> pd.DataFrame:
    """Load, transform, and combine every approved consumption snapshot."""
    definitions = load_export_definitions(config_path)
    consumption_definitions = [
        definition
        for definition in definitions.values()
        if definition.source_category == "actual_consumption"
    ]
    if len(consumption_definitions) != 2:
        raise ValueError("Exactly two consumption exports are required")

    records: dict[str, dict[str, str]] = {}
    for record in read_manifest(manifest_path):
        export_id = record["export_id"]
        if export_id in records:
            raise ValueError(f"Duplicate manifest export_id: {export_id}")
        records[export_id] = record

    transformed_snapshots: list[pd.DataFrame] = []
    for definition in consumption_definitions:
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
        lineage = SnapshotLineage.from_record(definition, record)
        transformed_snapshots.append(
            transform_consumption_snapshot(frame, lineage)
        )

    return combine_consumption_snapshots(transformed_snapshots)


def write_consumption_csv(frame: pd.DataFrame, output_path: Path) -> None:
    """Atomically write the reproducible clean consumption CSV."""
    if tuple(frame.columns) != CANONICAL_CONSUMPTION_COLUMNS:
        raise ValueError("Cannot write consumption data outside its contract")

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
