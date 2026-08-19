"""Canonical long-form transformation for SMARD actual generation."""

from dataclasses import dataclass
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

VALUE_STATUS_REPORTED = "reported"
VALUE_STATUS_UNAVAILABLE = "unavailable"
INTERVAL_DURATION_HOURS_COLUMN = "interval_duration_hours"
TECHNOLOGY_ID_COLUMN = "technology_id"
TECHNOLOGY_NAME_COLUMN = "technology_name"
TECHNOLOGY_GROUP_COLUMN = "technology_group"
IS_RENEWABLE_COLUMN = "is_renewable"
TECHNOLOGY_ORDER_COLUMN = "technology_order"
SOURCE_MEASURE_COLUMN = "source_measure_column"
SOURCE_VALUE_TEXT_COLUMN = "source_value_text"
VALUE_STATUS_COLUMN = "value_status"
GENERATION_MWH_COLUMN = "generation_mwh"
GENERATION_MW_COLUMN = "generation_mw"


@dataclass(frozen=True)
class GenerationTechnology:
    """Canonical metadata for one SMARD generation measure."""

    source_column: str
    technology_id: str
    technology_name: str
    technology_group: str
    is_renewable: bool


GENERATION_TECHNOLOGIES = (
    GenerationTechnology(
        "Biomass [MWh] Calculated resolutions",
        "biomass",
        "Biomass",
        "renewable",
        True,
    ),
    GenerationTechnology(
        "Hydropower [MWh] Calculated resolutions",
        "hydropower",
        "Hydropower",
        "renewable",
        True,
    ),
    GenerationTechnology(
        "Wind offshore [MWh] Calculated resolutions",
        "wind_offshore",
        "Wind offshore",
        "renewable",
        True,
    ),
    GenerationTechnology(
        "Wind onshore [MWh] Calculated resolutions",
        "wind_onshore",
        "Wind onshore",
        "renewable",
        True,
    ),
    GenerationTechnology(
        "Photovoltaics [MWh] Calculated resolutions",
        "solar_photovoltaic",
        "Solar photovoltaic",
        "renewable",
        True,
    ),
    GenerationTechnology(
        "Other renewable [MWh] Calculated resolutions",
        "other_renewable",
        "Other renewable",
        "renewable",
        True,
    ),
    GenerationTechnology(
        "Nuclear [MWh] Calculated resolutions",
        "nuclear",
        "Nuclear",
        "conventional",
        False,
    ),
    GenerationTechnology(
        "Lignite [MWh] Calculated resolutions",
        "lignite",
        "Lignite",
        "conventional",
        False,
    ),
    GenerationTechnology(
        "Hard coal [MWh] Calculated resolutions",
        "hard_coal",
        "Hard coal",
        "conventional",
        False,
    ),
    GenerationTechnology(
        "Fossil gas [MWh] Calculated resolutions",
        "fossil_gas",
        "Fossil gas",
        "conventional",
        False,
    ),
    GenerationTechnology(
        "Hydro pumped storage [MWh] Calculated resolutions",
        "hydro_pumped_storage",
        "Hydro pumped storage",
        "storage",
        False,
    ),
    GenerationTechnology(
        "Other conventional [MWh] Calculated resolutions",
        "other_conventional",
        "Other conventional",
        "conventional",
        False,
    ),
)
RAW_GENERATION_COLUMNS = (
    SOURCE_START_COLUMN,
    SOURCE_END_COLUMN,
    *(technology.source_column for technology in GENERATION_TECHNOLOGIES),
)
CANONICAL_GENERATION_COLUMNS = (
    *DATASET_TIME_COLUMNS,
    *LINEAGE_COLUMNS,
    INTERVAL_DURATION_HOURS_COLUMN,
    TECHNOLOGY_ID_COLUMN,
    TECHNOLOGY_NAME_COLUMN,
    TECHNOLOGY_GROUP_COLUMN,
    IS_RENEWABLE_COLUMN,
    TECHNOLOGY_ORDER_COLUMN,
    SOURCE_MEASURE_COLUMN,
    SOURCE_VALUE_TEXT_COLUMN,
    VALUE_STATUS_COLUMN,
    GENERATION_MWH_COLUMN,
    GENERATION_MW_COLUMN,
)
_ONE_HOUR = pd.Timedelta(hours=1)


def _parse_generation_values(
    values: pd.Series,
    technology: GenerationTechnology,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    raw_values = values.astype("string").fillna("").str.strip()
    marker_mask = raw_values == "-"
    if marker_mask.any() and technology.technology_id != "nuclear":
        raise ValueError(
            f"{technology.source_column} contains an unavailable marker"
        )

    numeric_values = pd.to_numeric(
        raw_values.str.replace(",", "", regex=False),
        errors="coerce",
    ).astype("Float64")
    invalid = numeric_values.isna() & ~marker_mask
    if invalid.any():
        position = int(np.flatnonzero(invalid.to_numpy())[0])
        raise ValueError(
            f"{technology.source_column} has a non-numeric value at row "
            f"{position}: {raw_values.iloc[position]!r}"
        )
    numeric_nonmissing = numeric_values.dropna().astype("float64")
    if not np.isfinite(numeric_nonmissing).all():
        raise ValueError(f"{technology.source_column} contains an infinite value")
    if (numeric_nonmissing < 0).any():
        raise ValueError(f"{technology.source_column} contains negative generation")

    statuses = pd.Series(
        np.where(marker_mask, VALUE_STATUS_UNAVAILABLE, VALUE_STATUS_REPORTED),
        index=values.index,
        dtype="string",
    )
    return raw_values, numeric_values, statuses


def transform_generation_snapshot(
    frame: pd.DataFrame,
    lineage: SourceLineage,
) -> pd.DataFrame:
    """Transform one generation snapshot into interval/technology rows."""
    lineage.validate_for("actual_generation", "DE")
    observed_columns = tuple(str(column) for column in frame.columns)
    if observed_columns != RAW_GENERATION_COLUMNS:
        raise ValueError("Actual-generation source columns changed")

    normalized = normalize_hourly_timestamps(frame)
    time_columns = normalized.loc[:, list(DATASET_TIME_COLUMNS)]
    technology_frames: list[pd.DataFrame] = []

    for order, technology in enumerate(GENERATION_TECHNOLOGIES, start=1):
        source_text, generation_mwh, statuses = _parse_generation_values(
            normalized[technology.source_column],
            technology,
        )
        technology_frame = time_columns.copy()
        attach_source_lineage(technology_frame, lineage)
        technology_frame[INTERVAL_DURATION_HOURS_COLUMN] = 1.0
        technology_frame[TECHNOLOGY_ID_COLUMN] = technology.technology_id
        technology_frame[TECHNOLOGY_NAME_COLUMN] = technology.technology_name
        technology_frame[TECHNOLOGY_GROUP_COLUMN] = technology.technology_group
        technology_frame[IS_RENEWABLE_COLUMN] = technology.is_renewable
        technology_frame[TECHNOLOGY_ORDER_COLUMN] = order
        technology_frame[SOURCE_MEASURE_COLUMN] = technology.source_column
        technology_frame[SOURCE_VALUE_TEXT_COLUMN] = source_text
        technology_frame[VALUE_STATUS_COLUMN] = statuses
        technology_frame[GENERATION_MWH_COLUMN] = generation_mwh
        technology_frame[GENERATION_MW_COLUMN] = (
            generation_mwh
            / technology_frame[INTERVAL_DURATION_HOURS_COLUMN]
        )
        technology_frames.append(technology_frame)

    transformed = pd.concat(technology_frames, ignore_index=True)
    transformed = transformed.sort_values(
        [INTERVAL_START_UTC_COLUMN, TECHNOLOGY_ORDER_COLUMN],
        kind="stable",
        ignore_index=True,
    )
    expected_rows = len(frame) * len(GENERATION_TECHNOLOGIES)
    if len(transformed) != expected_rows:
        raise ValueError("Generation long-form row count is incomplete")
    keys = transformed[[INTERVAL_START_UTC_COLUMN, TECHNOLOGY_ID_COLUMN]]
    if keys.duplicated().any():
        raise ValueError("Generation interval/technology keys are not unique")

    return transformed.loc[:, list(CANONICAL_GENERATION_COLUMNS)]


def combine_generation_snapshots(
    snapshots: list[pd.DataFrame],
) -> pd.DataFrame:
    """Combine long snapshots and enforce complete continuous technology rows."""
    if not snapshots:
        raise ValueError("At least one clean generation snapshot is required")
    for snapshot in snapshots:
        if tuple(snapshot.columns) != CANONICAL_GENERATION_COLUMNS:
            raise ValueError("Clean generation columns do not match the contract")

    combined = pd.concat(snapshots, ignore_index=True)
    combined = combined.sort_values(
        [INTERVAL_START_UTC_COLUMN, TECHNOLOGY_ORDER_COLUMN],
        kind="stable",
        ignore_index=True,
    )
    keys = combined[[INTERVAL_START_UTC_COLUMN, TECHNOLOGY_ID_COLUMN]]
    if keys.duplicated().any():
        raise ValueError("Combined generation keys are not unique")

    interval_counts = combined.groupby(
        INTERVAL_START_UTC_COLUMN,
        observed=True,
    ).size()
    expected_technologies = len(GENERATION_TECHNOLOGIES)
    if not (interval_counts == expected_technologies).all():
        raise ValueError("Combined generation intervals are incomplete")

    starts = (
        combined[INTERVAL_START_UTC_COLUMN]
        .drop_duplicates()
        .sort_values(ignore_index=True)
    )
    if not (starts.diff().dropna() == _ONE_HOUR).all():
        raise ValueError("Combined generation UTC starts are not continuous")
    return combined


def load_generation_dataset(
    config_path: Path,
    manifest_path: Path,
    raw_dir: Path,
) -> pd.DataFrame:
    """Load, transform, and combine every approved generation snapshot."""
    definitions = load_export_definitions(config_path)
    generation_definitions = [
        definition
        for definition in definitions.values()
        if definition.source_category == "actual_generation"
    ]
    if len(generation_definitions) != 2:
        raise ValueError("Exactly two generation exports are required")

    records: dict[str, dict[str, str]] = {}
    for record in read_manifest(manifest_path):
        export_id = record["export_id"]
        if export_id in records:
            raise ValueError(f"Duplicate manifest export_id: {export_id}")
        records[export_id] = record

    transformed_snapshots: list[pd.DataFrame] = []
    for definition in generation_definitions:
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
        transformed_snapshots.append(
            transform_generation_snapshot(frame, lineage)
        )

    return combine_generation_snapshots(transformed_snapshots)


def write_generation_csv(frame: pd.DataFrame, output_path: Path) -> None:
    """Atomically write the reproducible clean long-form generation CSV."""
    if tuple(frame.columns) != CANONICAL_GENERATION_COLUMNS:
        raise ValueError("Cannot write generation data outside its contract")

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
