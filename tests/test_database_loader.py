"""Fast tests for validated database-load inputs and SQL transformations."""

import json
from pathlib import Path

import pytest

from gridsight.database.data_loader import (
    DATASET_LOAD_SPECS,
    TRANSFORMATION_SQL_FILES,
    load_validated_inputs,
)
from gridsight.database.schema_contract import split_sql_statements
from gridsight.ingestion.snapshot_registry import sha256_file
from gridsight.validation.clean_data import ISSUE_COLUMNS


def _write_validated_project(project_root: Path) -> Path:
    processed = project_root / "data" / "processed"
    processed.mkdir(parents=True)
    datasets: dict[str, dict[str, object]] = {}
    for spec in DATASET_LOAD_SPECS:
        output_path = project_root / spec.relative_path
        output_path.write_text(
            ",".join(spec.columns) + "\n",
            encoding="utf-8",
        )
        datasets[spec.dataset] = {
            "output": spec.relative_path,
            "rows": spec.expected_rows,
            "columns": len(spec.columns),
            "sha256": sha256_file(output_path),
        }
    issues_path = processed / "validation_issues.csv"
    issues_path.write_text(",".join(ISSUE_COLUMNS) + "\n", encoding="utf-8")
    summary = {
        "schema_version": 1,
        "status": "passed",
        "check_counts": {"passed": 1, "failed": 0},
        "issue_counts": {"error": 0},
        "checks": [{"check_id": "fixture", "status": "passed"}],
        "datasets": datasets,
    }
    summary_path = processed / "validation_summary.json"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    return summary_path


def test_load_validated_inputs_accepts_matching_artifacts(tmp_path: Path) -> None:
    """Passing metadata, exact headers, and matching hashes are loadable."""
    summary_path = _write_validated_project(tmp_path)

    inputs = load_validated_inputs(summary_path, tmp_path)

    assert len(inputs.datasets) == 3
    assert inputs.summary_sha256 == sha256_file(summary_path)
    assert [dataset.spec.dataset for dataset in inputs.datasets] == [
        "consumption",
        "generation",
        "price",
    ]


def test_load_validated_inputs_rejects_failed_summary(tmp_path: Path) -> None:
    """A failed Phase 3 gate can never become a database load input."""
    summary_path = _write_validated_project(tmp_path)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["status"] = "failed"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    with pytest.raises(ValueError, match="passing run"):
        load_validated_inputs(summary_path, tmp_path)


def test_load_validated_inputs_rejects_changed_processed_bytes(
    tmp_path: Path,
) -> None:
    """A post-validation edit is detected before PostgreSQL is touched."""
    summary_path = _write_validated_project(tmp_path)
    consumption_path = tmp_path / DATASET_LOAD_SPECS[0].relative_path
    with consumption_path.open("a", encoding="utf-8") as file:
        file.write("\n")

    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        load_validated_inputs(summary_path, tmp_path)


def test_transformation_sql_is_ordered_and_non_destructive() -> None:
    """Dimensions load before facts and SQL only inserts into empty tables."""
    assert [path.name for path in TRANSFORMATION_SQL_FILES] == [
        "001_populate_dimensions.sql",
        "002_populate_facts.sql",
    ]
    statements = []
    for path in TRANSFORMATION_SQL_FILES:
        sql_text = path.read_text(encoding="utf-8")
        upper_sql = sql_text.upper()
        assert "TRUNCATE " not in upper_sql
        assert "DELETE " not in upper_sql
        assert "DROP " not in upper_sql
        statements.extend(split_sql_statements(sql_text))

    assert len(statements) == 5
    assert all("INSERT INTO" in statement.upper() for statement in statements)
