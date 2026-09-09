"""Fast tests for the latest clean-data validation run status."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gridsight.validation import run_validation


def test_run_status_is_atomic_and_byte_deterministic(tmp_path: Path) -> None:
    status_path = tmp_path / "validation_run_status.json"
    kwargs = {
        "status": "passed",
        "summary_sha256": "a" * 64,
    }

    run_validation.write_validation_run_status(status_path, **kwargs)
    first = status_path.read_bytes()
    run_validation.write_validation_run_status(status_path, **kwargs)

    assert status_path.read_bytes() == first
    assert json.loads(first) == {
        "schema_version": 1,
        "status": "passed",
        "summary_sha256": "a" * 64,
        "failure": None,
    }
    assert not (tmp_path / ".validation_run_status.json.tmp").exists()


def test_exception_records_failure_without_replacing_last_good_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    summary_path = tmp_path / "validation_summary.json"
    issues_path = tmp_path / "validation_issues.csv"
    status_path = tmp_path / "validation_run_status.json"
    summary_bytes = b'{"status":"passed"}\n'
    issues_bytes = b"dataset,check_id\n"
    summary_path.write_bytes(summary_bytes)
    issues_path.write_bytes(issues_bytes)

    def fail_load(*_: object) -> None:
        raise ValueError("snapshot mismatch")

    monkeypatch.setattr(run_validation, "DEFAULT_SUMMARY", summary_path)
    monkeypatch.setattr(run_validation, "DEFAULT_ISSUES", issues_path)
    monkeypatch.setattr(run_validation, "DEFAULT_RUN_STATUS", status_path)
    monkeypatch.setattr(run_validation, "load_consumption_dataset", fail_load)

    assert run_validation.main() == 1
    assert summary_path.read_bytes() == summary_bytes
    assert issues_path.read_bytes() == issues_bytes
    status = json.loads(status_path.read_text(encoding="utf-8"))
    assert status["status"] == "failed"
    assert status["summary_sha256"] is None
    assert status["failure"] == {
        "kind": "exception",
        "type": "ValueError",
        "message": "snapshot mismatch",
    }


def test_interruption_leaves_a_nonpassing_running_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    status_path = tmp_path / "validation_run_status.json"

    def interrupt(*_: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(run_validation, "DEFAULT_RUN_STATUS", status_path)
    monkeypatch.setattr(run_validation, "load_consumption_dataset", interrupt)

    with pytest.raises(KeyboardInterrupt):
        run_validation.main()

    status = json.loads(status_path.read_text(encoding="utf-8"))
    assert status == {
        "schema_version": 1,
        "status": "running",
        "summary_sha256": None,
        "failure": None,
    }
