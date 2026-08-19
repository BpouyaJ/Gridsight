"""Read-only profiling for registered SMARD source snapshots."""

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from gridsight.ingestion.snapshot_registry import (
    ExportDefinition,
    load_export_definitions,
    read_manifest,
    sha256_file,
)

START_COLUMN = "Start date"
END_COLUMN = "End date"
TIME_COLUMNS = (START_COLUMN, END_COLUMN)
CONSUMPTION_TARGET = "grid load [MWh] Calculated resolutions"
PRICE_TARGET = "Germany/Luxembourg [€/MWh] Calculated resolutions"
TARGET_COLUMNS = {
    "actual_consumption": CONSUMPTION_TARGET,
    "day_ahead_price": PRICE_TARGET,
}
ALLOWED_GENERATION_MARKERS = {"-"}
REPORTING_TIMEZONE = "Europe/Berlin"


@dataclass(frozen=True)
class MeasureProfile:
    """Numeric and source-marker observations for one measure column."""

    name: str
    numeric_count: int
    marker_counts: dict[str, int]
    negative_count: int
    zero_count: int
    positive_count: int
    minimum: float | None
    maximum: float | None

    @property
    def marker_count(self) -> int:
        """Return the total number of non-numeric source values."""
        return sum(self.marker_counts.values())


@dataclass(frozen=True)
class SnapshotProfile:
    """Structural and measure-level observations for one raw snapshot."""

    export_id: str
    source_category: str
    period_start: str
    period_end: str
    local_filename: str
    sha256: str
    sha_matches_manifest: bool
    row_count: int
    column_count: int
    headers: tuple[str, ...]
    first_start: str
    last_end: str
    unique_start_count: int
    repeated_start_groups: int
    target_column: str | None
    measures: tuple[MeasureProfile, ...]

    @property
    def target_profile(self) -> MeasureProfile | None:
        """Return the approved analytical target profile, when one exists."""
        if self.target_column is None:
            return None
        return next(
            (
                measure
                for measure in self.measures
                if measure.name == self.target_column
            ),
            None,
        )


@dataclass(frozen=True)
class SourceProfileReport:
    """Profiles and category-level schema compatibility results."""

    snapshots: tuple[SnapshotProfile, ...]
    schema_compatible: dict[str, bool]


def expected_hour_count(period_start: str, period_end: str) -> int:
    """Calculate real hourly intervals across inclusive Europe/Berlin dates."""
    start = pd.Timestamp(period_start).tz_localize(REPORTING_TIMEZONE)
    end_exclusive = (pd.Timestamp(period_end) + pd.Timedelta(days=1)).tz_localize(
        REPORTING_TIMEZONE
    )
    elapsed = end_exclusive.tz_convert("UTC") - start.tz_convert("UTC")
    return int(elapsed / pd.Timedelta(hours=1))


def _profile_measure(name: str, values: pd.Series) -> MeasureProfile:
    raw_values = values.astype("string").fillna("").str.strip()
    numeric_values = pd.to_numeric(
        raw_values.str.replace(",", "", regex=False),
        errors="coerce",
    )
    numeric = numeric_values.dropna()
    marker_counts = Counter(raw_values[numeric_values.isna()].tolist())

    return MeasureProfile(
        name=name,
        numeric_count=int(numeric.count()),
        marker_counts=dict(sorted(marker_counts.items())),
        negative_count=int((numeric < 0).sum()),
        zero_count=int((numeric == 0).sum()),
        positive_count=int((numeric > 0).sum()),
        minimum=float(numeric.min()) if not numeric.empty else None,
        maximum=float(numeric.max()) if not numeric.empty else None,
    )


def profile_snapshot(
    definition: ExportDefinition,
    raw_path: Path,
    manifest_sha256: str,
) -> SnapshotProfile:
    """Profile one immutable CSV without changing its contents."""
    frame = pd.read_csv(
        raw_path,
        sep=";",
        encoding="utf-8-sig",
        dtype="string",
        keep_default_na=False,
    )
    headers = tuple(str(column) for column in frame.columns)
    missing_time_columns = [name for name in TIME_COLUMNS if name not in headers]
    if missing_time_columns:
        missing = ", ".join(missing_time_columns)
        raise ValueError(f"{definition.export_id} lacks time columns: {missing}")
    if frame.empty:
        raise ValueError(f"{definition.export_id} contains no data rows")

    measure_columns = [name for name in headers if name not in TIME_COLUMNS]
    measures = tuple(
        _profile_measure(name, frame[name]) for name in measure_columns
    )
    start_counts = frame[START_COLUMN].value_counts()
    checksum = sha256_file(raw_path)

    return SnapshotProfile(
        export_id=definition.export_id,
        source_category=definition.source_category,
        period_start=definition.period_start,
        period_end=definition.period_end,
        local_filename=definition.local_filename,
        sha256=checksum,
        sha_matches_manifest=checksum == manifest_sha256,
        row_count=int(len(frame)),
        column_count=len(headers),
        headers=headers,
        first_start=str(frame.iloc[0][START_COLUMN]),
        last_end=str(frame.iloc[-1][END_COLUMN]),
        unique_start_count=int(frame[START_COLUMN].nunique()),
        repeated_start_groups=int((start_counts > 1).sum()),
        target_column=TARGET_COLUMNS.get(definition.source_category),
        measures=measures,
    )


def profile_registered_snapshots(
    config_path: Path,
    manifest_path: Path,
    raw_dir: Path,
) -> SourceProfileReport:
    """Profile every approved and registered snapshot in configuration order."""
    definitions = load_export_definitions(config_path)
    manifest_rows = read_manifest(manifest_path)
    records_by_id: dict[str, dict[str, str]] = {}

    for record in manifest_rows:
        export_id = record["export_id"]
        if export_id in records_by_id:
            raise ValueError(f"Duplicate manifest export_id: {export_id}")
        records_by_id[export_id] = record

    unexpected_ids = set(records_by_id) - set(definitions)
    if unexpected_ids:
        unexpected = ", ".join(sorted(unexpected_ids))
        raise ValueError(f"Manifest contains unapproved export IDs: {unexpected}")

    profiles: list[SnapshotProfile] = []
    for export_id, definition in definitions.items():
        record = records_by_id.get(export_id)
        if record is None:
            raise ValueError(f"Missing manifest record: {export_id}")
        if record["local_filename"] != definition.local_filename:
            raise ValueError(f"Manifest filename mismatch: {export_id}")

        raw_path = raw_dir / definition.local_filename
        if not raw_path.is_file():
            raise ValueError(f"Missing raw snapshot: {definition.local_filename}")
        profiles.append(
            profile_snapshot(definition, raw_path, record["sha256"])
        )

    categories = sorted({profile.source_category for profile in profiles})
    schema_compatible = {
        category: len(
            {
                profile.headers
                for profile in profiles
                if profile.source_category == category
            }
        )
        == 1
        for category in categories
    }
    return SourceProfileReport(
        snapshots=tuple(profiles),
        schema_compatible=schema_compatible,
    )


def validate_source_profiles(report: SourceProfileReport) -> tuple[str, ...]:
    """Return Phase 2 contract violations without mutating source data."""
    violations: list[str] = []

    for category, compatible in report.schema_compatible.items():
        if not compatible:
            violations.append(f"{category}: snapshot schemas differ")

    for profile in report.snapshots:
        prefix = profile.export_id
        expected_rows = expected_hour_count(
            profile.period_start,
            profile.period_end,
        )
        expected_repeats = (
            int(profile.period_end[:4]) - int(profile.period_start[:4]) + 1
        )

        if not profile.sha_matches_manifest:
            violations.append(f"{prefix}: raw SHA-256 differs from manifest")
        if profile.row_count != expected_rows:
            violations.append(
                f"{prefix}: expected {expected_rows} rows, "
                f"observed {profile.row_count}"
            )
        if profile.repeated_start_groups != expected_repeats:
            violations.append(
                f"{prefix}: expected {expected_repeats} repeated local-hour "
                f"groups, observed {profile.repeated_start_groups}"
            )

        if profile.target_column is not None:
            target = profile.target_profile
            if target is None:
                violations.append(
                    f"{prefix}: missing target column {profile.target_column!r}"
                )
            elif target.marker_count:
                violations.append(
                    f"{prefix}: target contains {target.marker_count} "
                    "non-numeric values"
                )

        if profile.source_category == "actual_generation":
            if len(profile.measures) != 12:
                violations.append(
                    f"{prefix}: expected 12 generation measures, "
                    f"observed {len(profile.measures)}"
                )
            for measure in profile.measures:
                unexpected_markers = (
                    set(measure.marker_counts) - ALLOWED_GENERATION_MARKERS
                )
                if unexpected_markers:
                    markers = ", ".join(sorted(unexpected_markers))
                    violations.append(
                        f"{prefix}: {measure.name} has unexpected markers: "
                        f"{markers}"
                    )

    return tuple(violations)
