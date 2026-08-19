"""Tests for reproducible, read-only SMARD source profiling."""

from pathlib import Path

from gridsight.ingestion.snapshot_registry import ExportDefinition, sha256_file
from gridsight.ingestion.source_profiler import (
    expected_hour_count,
    profile_snapshot,
)


def _generation_definition() -> ExportDefinition:
    return ExportDefinition(
        export_id="actual_generation_de_2022_2023",
        source_name="Bundesnetzagentur SMARD",
        source_url="https://www.smard.de/en/downloadcenter/download-market-data/",
        source_category="actual_generation",
        source_geography="DE",
        source_resolution="hour",
        period_start="2022-01-01",
        period_end="2023-12-31",
        local_filename="generation.csv",
        expected_series="all available generation types",
        licence="CC BY 4.0",
        attribution="Bundesnetzagentur | SMARD.de",
        smard_filters={"file_type": "CSV"},
    )


def test_expected_hour_count_handles_leap_years_and_dst() -> None:
    """Full-year interval counts include leap days without adding DST hours."""
    assert expected_hour_count("2022-01-01", "2023-12-31") == 17_520
    assert expected_hour_count("2024-01-01", "2025-12-31") == 17_544


def test_profile_snapshot_preserves_markers_and_numeric_signs(
    tmp_path: Path,
) -> None:
    """Profiling distinguishes source markers, zeroes, and signed numbers."""
    raw_path = tmp_path / "generation.csv"
    raw_path.write_text(
        "Start date;End date;Biomass [MWh] Calculated resolutions;"
        "Nuclear [MWh] Calculated resolutions\n"
        "Oct 30, 2022 2:00 AM;Oct 30, 2022 2:00 AM;1,234.50;-\n"
        "Oct 30, 2022 2:00 AM;Oct 30, 2022 3:00 AM;-1.00;0.00\n"
        "Oct 30, 2022 3:00 AM;Oct 30, 2022 4:00 AM;0.00;2.00\n",
        encoding="utf-8-sig",
    )

    profile = profile_snapshot(
        _generation_definition(),
        raw_path,
        sha256_file(raw_path),
    )
    biomass, nuclear = profile.measures

    assert profile.row_count == 3
    assert profile.column_count == 4
    assert profile.unique_start_count == 2
    assert profile.repeated_start_groups == 1
    assert profile.sha_matches_manifest is True
    assert biomass.numeric_count == 3
    assert biomass.negative_count == 1
    assert biomass.zero_count == 1
    assert biomass.positive_count == 1
    assert biomass.minimum == -1.0
    assert biomass.maximum == 1234.5
    assert nuclear.marker_counts == {"-": 1}
    assert nuclear.numeric_count == 2
