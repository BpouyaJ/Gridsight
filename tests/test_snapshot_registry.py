"""Tests for immutable raw-snapshot registration."""

import csv
from datetime import UTC, datetime
from pathlib import Path

import pytest

from gridsight.ingestion.snapshot_registry import (
    ExportDefinition,
    load_export_definitions,
    register_snapshot,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _definition() -> ExportDefinition:
    return ExportDefinition(
        export_id="actual_consumption_de_2022_2023",
        source_name="Bundesnetzagentur SMARD",
        source_url="https://www.smard.de/en/downloadcenter/download-market-data/",
        source_category="actual_consumption",
        source_geography="DE",
        source_resolution="hour",
        period_start="2022-01-01",
        period_end="2023-12-31",
        local_filename="smard_actual_consumption_de_2022_2023.csv",
        expected_series="grid load",
        licence="CC BY 4.0",
        attribution="Bundesnetzagentur | SMARD.de",
        smard_filters={"file_type": "CSV"},
    )


def test_approved_config_contains_six_unique_exports() -> None:
    """The project config preserves the approved six-snapshot scope."""
    definitions = load_export_definitions(
        PROJECT_ROOT / "configs" / "smard_exports.json"
    )

    assert len(definitions) == 6
    assert set(definitions) == {
        "actual_consumption_de_2022_2023",
        "actual_consumption_de_2024_2025",
        "actual_generation_de_2022_2023",
        "actual_generation_de_2024_2025",
        "day_ahead_price_de_lu_2022_2023",
        "day_ahead_price_de_lu_2024_2025",
    }
    assert len({item.local_filename for item in definitions.values()}) == 6
    assert all(item.expected_series for item in definitions.values())
    assert all(
        "data_series" not in item.smard_filters for item in definitions.values()
    )


def test_registration_preserves_bytes_and_is_idempotent(tmp_path: Path) -> None:
    """Repeated registration keeps one raw copy and one manifest row."""
    source_file = tmp_path / "original-smard-name.csv"
    source_bytes = b"Datum;Netzlast\n01.01.2022;50000\n"
    source_file.write_bytes(source_bytes)
    raw_dir = tmp_path / "raw"
    manifest_path = tmp_path / "manifests" / "sources.csv"
    timestamp = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)

    first_result = register_snapshot(
        source_file,
        _definition(),
        raw_dir,
        manifest_path,
        notes="Test registration",
        downloaded_at_utc=timestamp,
    )
    second_result = register_snapshot(
        source_file,
        _definition(),
        raw_dir,
        manifest_path,
        downloaded_at_utc=timestamp,
    )

    destination = raw_dir / _definition().local_filename
    assert destination.read_bytes() == source_bytes
    assert first_result.copied is True
    assert first_result.manifest_appended is True
    assert second_result.copied is False
    assert second_result.manifest_appended is False

    with manifest_path.open("r", encoding="utf-8", newline="") as manifest_file:
        rows = list(csv.DictReader(manifest_file))

    assert len(rows) == 1
    assert rows[0]["original_filename"] == source_file.name
    assert rows[0]["downloaded_at_utc"] == "2026-08-19T12:00:00Z"
    assert len(rows[0]["sha256"]) == 64
    assert rows[0]["notes"] == "Test registration"


def test_registration_refuses_different_bytes_for_existing_name(
    tmp_path: Path,
) -> None:
    """A changed source cannot replace an earlier normalized snapshot."""
    first_source = tmp_path / "first.csv"
    second_source = tmp_path / "second.csv"
    first_source.write_text("first snapshot", encoding="utf-8")
    second_source.write_text("revised snapshot", encoding="utf-8")
    raw_dir = tmp_path / "raw"
    manifest_path = tmp_path / "manifests" / "sources.csv"

    register_snapshot(
        first_source,
        _definition(),
        raw_dir,
        manifest_path,
    )

    with pytest.raises(ValueError, match="different SHA-256"):
        register_snapshot(
            second_source,
            _definition(),
            raw_dir,
            manifest_path,
        )
