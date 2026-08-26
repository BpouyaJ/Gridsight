"""Fast tests for hash-gated final forecast-mart inputs."""

import json
import shutil
from pathlib import Path

import pytest

from gridsight.database.forecast_mart_loader import (
    EXPECTED_MODEL_NAME,
    EXPECTED_PREDICTION_ROWS,
    load_forecast_mart_artifacts,
)
from gridsight.forecasting.contract import sha256_file
from gridsight.forecasting.final_evaluation import (
    DEFAULT_FINAL_EVALUATION_SNAPSHOT,
    DEFAULT_FINAL_PREDICTIONS,
)


def _copy_final_artifacts(project_root: Path) -> tuple[Path, Path]:
    predictions = project_root / "data" / "processed" / "final_forecast_predictions.csv"
    snapshot = project_root / "reports" / "final_evaluation_snapshot.json"
    predictions.parent.mkdir(parents=True)
    snapshot.parent.mkdir(parents=True)
    shutil.copyfile(DEFAULT_FINAL_PREDICTIONS, predictions)
    shutil.copyfile(DEFAULT_FINAL_EVALUATION_SNAPSHOT, snapshot)
    return predictions, snapshot


def test_final_forecast_artifacts_are_hash_gated_and_complete() -> None:
    artifacts = load_forecast_mart_artifacts()

    assert artifacts.predictions_sha256 == sha256_file(DEFAULT_FINAL_PREDICTIONS)
    assert artifacts.snapshot_sha256 == sha256_file(
        DEFAULT_FINAL_EVALUATION_SNAPSHOT
    )
    assert (
        artifacts.snapshot["prediction_artifact"]["row_count"]
        == EXPECTED_PREDICTION_ROWS
    )
    assert (
        artifacts.snapshot["final_fit_contract"]["selected_candidate"]
        == EXPECTED_MODEL_NAME
    )


def test_forecast_artifact_loader_rejects_changed_prediction_bytes(
    tmp_path: Path,
) -> None:
    predictions, snapshot = _copy_final_artifacts(tmp_path)
    with predictions.open("ab") as file:
        file.write(b"\n")

    with pytest.raises(ValueError, match="bytes do not match"):
        load_forecast_mart_artifacts(
            predictions_path=predictions,
            snapshot_path=snapshot,
            project_root=tmp_path,
        )


def test_forecast_artifact_loader_rejects_changed_frozen_selection(
    tmp_path: Path,
) -> None:
    predictions, snapshot = _copy_final_artifacts(tmp_path)
    payload = json.loads(snapshot.read_text(encoding="utf-8"))
    payload["final_fit_contract"]["selected_candidate"] = "changed_model"
    snapshot.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="selection is not frozen"):
        load_forecast_mart_artifacts(
            predictions_path=predictions,
            snapshot_path=snapshot,
            project_root=tmp_path,
        )
