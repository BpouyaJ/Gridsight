"""Fast tests for deterministic checked reporting sample extracts."""

from pathlib import Path

import pytest

from gridsight.reporting.mart_contract import MART_CONTRACTS
from gridsight.reporting.sample_extracts import (
    EXPECTED_SAMPLE_COUNT,
    EXPECTED_SAMPLE_ROWS,
    SAMPLE_QUERIES,
    build_checked_sample_frames,
    validate_published_sample_bundle,
    validate_sample_frame,
    validate_sample_queries,
    write_sample_csv,
)


def _contract(product_id: str):
    return next(
        contract
        for contract in MART_CONTRACTS
        if contract.product_id == product_id
    )


def test_sample_queries_cover_six_views_with_fixed_ordering() -> None:
    validate_sample_queries()

    assert len(SAMPLE_QUERIES) == 6
    assert {query.product_id for query in SAMPLE_QUERIES} == {
        contract.product_id
        for contract in MART_CONTRACTS
        if contract.source_kind == "postgresql_view"
    }
    assert all(query.order_by for query in SAMPLE_QUERIES)


def test_checked_artifact_samples_match_source_contracts() -> None:
    frames = build_checked_sample_frames()

    assert list(frames) == ["data_quality_checks", "source_lineage"]
    assert len(frames["data_quality_checks"]) == 29
    assert set(frames["data_quality_checks"]["status"]) == {"passed"}
    assert len(frames["source_lineage"]) == 6
    assert set(frames["source_lineage"]["attribution"]) == {
        "Bundesnetzagentur | SMARD.de"
    }


def test_sample_validation_rejects_duplicate_contract_key() -> None:
    frame = build_checked_sample_frames()["data_quality_checks"].copy()
    frame.loc[frame.index[-1], ["dataset", "check_id"]] = frame.loc[
        frame.index[0], ["dataset", "check_id"]
    ].to_numpy()

    with pytest.raises(ValueError, match="duplicates"):
        validate_sample_frame(_contract("data_quality_checks"), frame)


def test_sample_csv_writer_is_byte_deterministic(tmp_path: Path) -> None:
    frame = build_checked_sample_frames()["data_quality_checks"]
    path = tmp_path / "quality.csv"
    write_sample_csv(frame, path)
    first_bytes = path.read_bytes()
    write_sample_csv(frame, path)

    assert path.read_bytes() == first_bytes
    assert first_bytes.startswith(b"dataset,check_id,status,expected,observed\n")


def test_published_bundle_matches_manifest_and_contract() -> None:
    manifest = validate_published_sample_bundle()

    assert manifest["sample_count"] == EXPECTED_SAMPLE_COUNT
    assert manifest["sample_rows"] == EXPECTED_SAMPLE_ROWS
    assert len(manifest["samples"]) == len(MART_CONTRACTS)
    assert all(
        contract.sample.implementation_status == "verified_existing"
        for contract in MART_CONTRACTS
    )
