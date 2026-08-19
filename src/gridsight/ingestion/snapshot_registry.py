"""Immutable raw-snapshot registration and source-manifest handling."""

import csv
import hashlib
import json
import shutil
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path

MANIFEST_FIELDS = (
    "export_id",
    "source_name",
    "source_url",
    "source_category",
    "source_geography",
    "source_resolution",
    "period_start",
    "period_end",
    "downloaded_at_utc",
    "original_filename",
    "local_filename",
    "sha256",
    "licence",
    "attribution",
    "notes",
)

ALLOWED_CATEGORIES = {
    "actual_consumption",
    "actual_generation",
    "day_ahead_price",
}
ALLOWED_GEOGRAPHIES = {"DE", "DE-LU"}


@dataclass(frozen=True)
class ExportDefinition:
    """One approved SMARD export and its download filters."""

    export_id: str
    source_name: str
    source_url: str
    source_category: str
    source_geography: str
    source_resolution: str
    period_start: str
    period_end: str
    local_filename: str
    expected_series: str
    licence: str
    attribution: str
    smard_filters: dict[str, str]


@dataclass(frozen=True)
class SnapshotRecord:
    """One persisted source-manifest row."""

    export_id: str
    source_name: str
    source_url: str
    source_category: str
    source_geography: str
    source_resolution: str
    period_start: str
    period_end: str
    downloaded_at_utc: str
    original_filename: str
    local_filename: str
    sha256: str
    licence: str
    attribution: str
    notes: str


@dataclass(frozen=True)
class RegistrationResult:
    """Outcome of an idempotent snapshot registration."""

    record: SnapshotRecord
    copied: bool
    manifest_appended: bool


def _required_text(mapping: dict[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Configuration field {key!r} must be non-empty text")
    return value.strip()


def _validate_definition(definition: ExportDefinition) -> None:
    if definition.source_category not in ALLOWED_CATEGORIES:
        raise ValueError(
            f"Unsupported source category: {definition.source_category}"
        )
    if definition.source_geography not in ALLOWED_GEOGRAPHIES:
        raise ValueError(
            f"Unsupported source geography: {definition.source_geography}"
        )
    if definition.source_resolution != "hour":
        raise ValueError("SMARD export resolution must be 'hour'")

    period_start = date.fromisoformat(definition.period_start)
    period_end = date.fromisoformat(definition.period_end)
    if period_start > period_end:
        raise ValueError("Export period_start must not be after period_end")

    filename = Path(definition.local_filename)
    if filename.name != definition.local_filename or filename.suffix.lower() != ".csv":
        raise ValueError("local_filename must be a plain CSV filename")


def load_export_definitions(config_path: Path) -> dict[str, ExportDefinition]:
    """Load and validate approved SMARD export definitions from JSON."""
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("SMARD export configuration must be a JSON object")

    source = payload.get("source")
    exports = payload.get("exports")
    if not isinstance(source, dict) or not isinstance(exports, list):
        raise ValueError("Configuration requires 'source' and 'exports' sections")

    definitions: dict[str, ExportDefinition] = {}
    filenames: set[str] = set()

    for export in exports:
        if not isinstance(export, dict):
            raise ValueError("Every export definition must be a JSON object")

        filters = export.get("smard_filters")
        if not isinstance(filters, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in filters.items()
        ):
            raise ValueError("smard_filters must contain text keys and values")

        definition = ExportDefinition(
            export_id=_required_text(export, "export_id"),
            source_name=_required_text(source, "source_name"),
            source_url=_required_text(source, "source_url"),
            source_category=_required_text(export, "source_category"),
            source_geography=_required_text(export, "source_geography"),
            source_resolution=_required_text(source, "source_resolution"),
            period_start=_required_text(export, "period_start"),
            period_end=_required_text(export, "period_end"),
            local_filename=_required_text(export, "local_filename"),
            expected_series=_required_text(export, "expected_series"),
            licence=_required_text(source, "licence"),
            attribution=_required_text(source, "attribution"),
            smard_filters=filters,
        )
        _validate_definition(definition)

        if definition.export_id in definitions:
            raise ValueError(f"Duplicate export_id: {definition.export_id}")
        if definition.local_filename in filenames:
            raise ValueError(
                f"Duplicate local_filename: {definition.local_filename}"
            )

        definitions[definition.export_id] = definition
        filenames.add(definition.local_filename)

    if not definitions:
        raise ValueError("At least one SMARD export definition is required")

    return definitions


def sha256_file(path: Path) -> str:
    """Calculate a file's SHA-256 digest without loading it all into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_manifest(manifest_path: Path) -> list[dict[str, str]]:
    """Read a manifest and enforce its exact field order."""
    if not manifest_path.exists() or manifest_path.stat().st_size == 0:
        return []

    with manifest_path.open("r", encoding="utf-8", newline="") as manifest_file:
        reader = csv.DictReader(manifest_file)
        if reader.fieldnames != list(MANIFEST_FIELDS):
            raise ValueError("Source manifest header does not match its contract")
        return list(reader)


def _append_manifest(manifest_path: Path, record: SnapshotRecord) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not manifest_path.exists() or manifest_path.stat().st_size == 0

    with manifest_path.open("a", encoding="utf-8", newline="") as manifest_file:
        writer = csv.DictWriter(
            manifest_file,
            fieldnames=MANIFEST_FIELDS,
            lineterminator="\n",
        )
        if write_header:
            writer.writeheader()
        writer.writerow(asdict(record))


def _utc_timestamp(value: datetime | None) -> str:
    timestamp = value or datetime.now(UTC)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("downloaded_at_utc must be timezone-aware")
    return (
        timestamp.astimezone(UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def register_snapshot(
    source_file: Path,
    definition: ExportDefinition,
    raw_dir: Path,
    manifest_path: Path,
    *,
    notes: str = "",
    downloaded_at_utc: datetime | None = None,
) -> RegistrationResult:
    """Copy one immutable raw CSV and idempotently record its lineage."""
    if not source_file.is_file():
        raise ValueError(f"Source file does not exist: {source_file}")
    if source_file.suffix.lower() != ".csv":
        raise ValueError("Only CSV source snapshots can be registered")
    if source_file.stat().st_size == 0:
        raise ValueError("Source snapshot must not be empty")

    source_checksum = sha256_file(source_file)
    existing_rows = read_manifest(manifest_path)
    matching_rows = [
        row
        for row in existing_rows
        if row["local_filename"] == definition.local_filename
    ]
    if len(matching_rows) > 1:
        raise ValueError(
            f"Manifest contains duplicate filename: {definition.local_filename}"
        )

    existing_row = matching_rows[0] if matching_rows else None
    if existing_row and existing_row["sha256"] != source_checksum:
        raise ValueError(
            "Manifest already contains this filename with a different SHA-256"
        )

    raw_dir.mkdir(parents=True, exist_ok=True)
    destination = raw_dir / definition.local_filename
    copied = False

    if destination.exists():
        if sha256_file(destination) != source_checksum:
            raise FileExistsError(
                f"Refusing to overwrite different raw bytes: {destination}"
            )
    else:
        with source_file.open("rb") as source, destination.open("xb") as target:
            shutil.copyfileobj(source, target, length=1024 * 1024)
        copied = True

    if existing_row:
        record = SnapshotRecord(
            **{field: existing_row[field] for field in MANIFEST_FIELDS}
        )
        return RegistrationResult(
            record=record,
            copied=copied,
            manifest_appended=False,
        )

    record = SnapshotRecord(
        export_id=definition.export_id,
        source_name=definition.source_name,
        source_url=definition.source_url,
        source_category=definition.source_category,
        source_geography=definition.source_geography,
        source_resolution=definition.source_resolution,
        period_start=definition.period_start,
        period_end=definition.period_end,
        downloaded_at_utc=_utc_timestamp(downloaded_at_utc),
        original_filename=source_file.name,
        local_filename=definition.local_filename,
        sha256=source_checksum,
        licence=definition.licence,
        attribution=definition.attribution,
        notes=notes.strip(),
    )
    _append_manifest(manifest_path, record)

    return RegistrationResult(
        record=record,
        copied=copied,
        manifest_appended=True,
    )
