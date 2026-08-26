"""Hash-gated PostgreSQL loading for final forecast-evaluation facts."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from gridsight.database.schema_contract import PROJECT_ROOT, TABLE_CONTRACTS
from gridsight.forecasting.contract import sha256_file
from gridsight.forecasting.final_evaluation import (
    DEFAULT_FINAL_EVALUATION_SNAPSHOT,
    DEFAULT_FINAL_PREDICTIONS,
    FINAL_PREDICTION_COLUMNS,
    validate_final_predictions,
)

EXPECTED_PREDICTION_ROWS = 8_760
EXPECTED_ORIGINS = 365
EXPECTED_MODEL_NAME = "hist_gradient_boosting_31_leaves"
STATUS_PASSED = "passed"
STATUS_FAILED = "failed"


@dataclass(frozen=True)
class ForecastMartArtifacts:
    """Verified final-evaluation inputs for one mart load."""

    predictions_path: Path
    predictions_sha256: str
    snapshot_path: Path
    snapshot_sha256: str
    snapshot: dict[str, Any]


@dataclass(frozen=True)
class ForecastMartCheck:
    """One stable forecast-mart reconciliation result."""

    check_id: str
    status: str
    expected: str
    observed: str


@dataclass(frozen=True)
class ForecastMartLoadReport:
    """Transactional row counts and reconciliation evidence."""

    table_counts: dict[str, int]
    checks: tuple[ForecastMartCheck, ...]

    @property
    def ok(self) -> bool:
        """Return whether all forecast-mart checks passed."""
        return all(check.status == STATUS_PASSED for check in self.checks)

    @property
    def problems(self) -> tuple[ForecastMartCheck, ...]:
        """Return only failed checks."""
        return tuple(
            check for check in self.checks if check.status == STATUS_FAILED
        )


class ForecastMartReconciliationError(ValueError):
    """Raised inside the transaction when forecast reconciliation fails."""

    def __init__(self, report: ForecastMartLoadReport) -> None:
        self.report = report
        failed_ids = ", ".join(check.check_id for check in report.problems)
        super().__init__(f"forecast-mart reconciliation failed: {failed_ids}")


def _read_csv_header(path: Path) -> tuple[str, ...]:
    with path.open("r", encoding="utf-8", newline="") as file:
        try:
            return tuple(next(csv.reader(file)))
        except StopIteration as error:
            raise ValueError("Final prediction artifact is empty") from error


def load_forecast_mart_artifacts(
    *,
    predictions_path: Path = DEFAULT_FINAL_PREDICTIONS,
    snapshot_path: Path = DEFAULT_FINAL_EVALUATION_SNAPSHOT,
    project_root: Path = PROJECT_ROOT,
) -> ForecastMartArtifacts:
    """Verify final prediction bytes, schema, rows, and frozen selection."""
    try:
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("Final evaluation snapshot is missing or invalid") from error

    artifact = snapshot.get("prediction_artifact", {})
    final_fit = snapshot.get("final_fit_contract", {})
    expected_path = predictions_path.relative_to(project_root).as_posix()
    predictions_sha256 = sha256_file(predictions_path)
    if snapshot.get("schema_version") != 1:
        raise ValueError("Final evaluation schema version must equal 1")
    if artifact.get("path") != expected_path:
        raise ValueError("Final prediction path does not match its snapshot")
    if artifact.get("sha256") != predictions_sha256:
        raise ValueError("Final prediction bytes do not match their snapshot")
    if artifact.get("row_count") != EXPECTED_PREDICTION_ROWS:
        raise ValueError("Final prediction row count is not frozen at 8,760")
    if tuple(artifact.get("columns", ())) != FINAL_PREDICTION_COLUMNS:
        raise ValueError("Final prediction columns do not match their snapshot")
    if _read_csv_header(predictions_path) != FINAL_PREDICTION_COLUMNS:
        raise ValueError("Final prediction CSV header changed")
    if (
        final_fit.get("selected_candidate") != EXPECTED_MODEL_NAME
        or final_fit.get("further_model_selection_allowed") is not False
        or final_fit.get("test_influenced_design") is not False
    ):
        raise ValueError("Final model selection is not frozen")

    predictions = pd.read_csv(predictions_path)
    validate_final_predictions(predictions)
    if set(predictions["model_name"]) != {EXPECTED_MODEL_NAME}:
        raise ValueError("Final prediction model differs from the frozen model")
    return ForecastMartArtifacts(
        predictions_path=predictions_path,
        predictions_sha256=predictions_sha256,
        snapshot_path=snapshot_path,
        snapshot_sha256=sha256_file(snapshot_path),
        snapshot=snapshot,
    )


def _copy_predictions(
    connection: Connection,
    artifacts: ForecastMartArtifacts,
) -> None:
    columns = TABLE_CONTRACTS[("staging", "final_forecast_predictions")].columns
    copy_sql = (
        f"COPY staging.final_forecast_predictions ({', '.join(columns)}) "
        "FROM STDIN WITH (FORMAT CSV, HEADER TRUE, NULL '')"
    )
    driver_connection = connection.connection.driver_connection
    with driver_connection.cursor() as cursor:
        with cursor.copy(copy_sql) as copy:
            with artifacts.predictions_path.open("rb") as file:
                while chunk := file.read(1024 * 1024):
                    copy.write(chunk)


def _populate_forecast_fact(
    connection: Connection,
    artifacts: ForecastMartArtifacts,
) -> None:
    connection.execute(
        text(
            """
            INSERT INTO analytics.fact_load_forecast_evaluation (
                forecast_origin_utc,
                origin_date_key,
                horizon_step,
                information_cutoff_utc,
                target_start_utc,
                target_date_key,
                target_hour_key,
                actual_grid_load_mw,
                daily_naive_source_utc,
                daily_naive_prediction_mw,
                weekly_naive_source_utc,
                weekly_naive_prediction_mw,
                model_name,
                model_prediction_mw,
                model_error_mw,
                model_absolute_error_mw,
                prediction_artifact_sha256,
                evaluation_snapshot_sha256
            )
            SELECT
                prediction.forecast_origin_utc,
                origin_date.date_key,
                prediction.horizon_step,
                prediction.information_cutoff_utc,
                prediction.target_start_utc,
                electricity.date_key,
                electricity.hour_key,
                prediction.actual_grid_load_mw,
                prediction.daily_naive_source_utc,
                prediction.daily_naive_prediction_mw,
                prediction.weekly_naive_source_utc,
                prediction.weekly_naive_prediction_mw,
                prediction.model_name,
                prediction.model_prediction_mw,
                prediction.model_error_mw,
                prediction.model_absolute_error_mw,
                :prediction_sha256,
                :snapshot_sha256
            FROM staging.final_forecast_predictions AS prediction
            INNER JOIN analytics.dim_date AS origin_date
                ON origin_date.calendar_date = prediction.origin_local_date
            INNER JOIN analytics.fact_electricity_hourly AS electricity
                ON electricity.interval_start_utc = prediction.target_start_utc
            ORDER BY
                prediction.forecast_origin_utc,
                prediction.horizon_step
            """
        ),
        {
            "prediction_sha256": artifacts.predictions_sha256,
            "snapshot_sha256": artifacts.snapshot_sha256,
        },
    )


def _add_check(
    checks: list[ForecastMartCheck],
    check_id: str,
    expected: object,
    observed: object,
) -> None:
    checks.append(
        ForecastMartCheck(
            check_id=check_id,
            status=STATUS_PASSED if observed == expected else STATUS_FAILED,
            expected=str(expected),
            observed=str(observed),
        )
    )


def _scalar(connection: Connection, sql: str) -> Any:
    return connection.exec_driver_sql(sql).scalar_one()


def _expected_overall_metrics(
    snapshot: dict[str, Any],
) -> dict[str, dict[str, Decimal | int]]:
    evaluation = snapshot.get("test_evaluation", {})
    series = {
        "model": evaluation.get("model", {}).get("overall", {}),
        "daily": evaluation.get("baselines", {})
        .get("daily_seasonal_naive", {})
        .get("overall", {}),
        "weekly": evaluation.get("baselines", {})
        .get("weekly_seasonal_naive", {})
        .get("overall", {}),
    }
    expected: dict[str, dict[str, Decimal | int]] = {}
    for name, metrics in series.items():
        if set(metrics) != {
            "observations",
            "mae_mw",
            "rmse_mw",
            "mape_percent",
        }:
            raise ValueError(f"Final {name} overall metrics are incomplete")
        expected[name] = {
            "observations": int(metrics["observations"]),
            "mae_mw": Decimal(str(metrics["mae_mw"])),
            "rmse_mw": Decimal(str(metrics["rmse_mw"])),
            "mape_percent": Decimal(str(metrics["mape_percent"])),
        }
    return expected


def reconcile_forecast_mart(
    connection: Connection,
    artifacts: ForecastMartArtifacts,
) -> ForecastMartLoadReport:
    """Reconcile forecast grains, lineage, joins, values, and final metrics."""
    checks: list[ForecastMartCheck] = []
    table_counts = {}
    for table in (
        "staging.final_forecast_predictions",
        "analytics.fact_load_forecast_evaluation",
    ):
        observed = int(_scalar(connection, f"SELECT COUNT(*) FROM {table}"))
        table_counts[table] = observed
        _add_check(checks, f"{table}.row_count", EXPECTED_PREDICTION_ROWS, observed)

    grain = connection.exec_driver_sql(
        """
        SELECT
            COUNT(DISTINCT forecast_origin_utc),
            MIN(horizon_step),
            MAX(horizon_step),
            COUNT(DISTINCT (forecast_origin_utc, horizon_step))
        FROM analytics.fact_load_forecast_evaluation
        """
    ).one()
    _add_check(checks, "forecast.origin_count", EXPECTED_ORIGINS, int(grain[0]))
    _add_check(checks, "forecast.minimum_horizon", 1, int(grain[1]))
    _add_check(checks, "forecast.maximum_horizon", 24, int(grain[2]))
    _add_check(
        checks,
        "forecast.unique_grain",
        EXPECTED_PREDICTION_ROWS,
        int(grain[3]),
    )

    mismatches = int(
        _scalar(
            connection,
            """
            SELECT COUNT(*)
            FROM staging.final_forecast_predictions AS staging
            FULL OUTER JOIN analytics.fact_load_forecast_evaluation AS fact
                USING (forecast_origin_utc, horizon_step)
            WHERE staging.forecast_origin_utc IS NULL
                OR fact.forecast_origin_utc IS NULL
                OR staging.target_start_utc IS DISTINCT FROM fact.target_start_utc
                OR staging.actual_grid_load_mw
                    IS DISTINCT FROM fact.actual_grid_load_mw
                OR staging.model_prediction_mw
                    IS DISTINCT FROM fact.model_prediction_mw
                OR staging.daily_naive_prediction_mw
                    IS DISTINCT FROM fact.daily_naive_prediction_mw
                OR staging.weekly_naive_prediction_mw
                    IS DISTINCT FROM fact.weekly_naive_prediction_mw
            """,
        )
    )
    _add_check(checks, "forecast.fact_measure_copy", 0, mismatches)

    lineage = connection.exec_driver_sql(
        """
        SELECT
            COUNT(DISTINCT prediction_artifact_sha256),
            MIN(prediction_artifact_sha256),
            COUNT(DISTINCT evaluation_snapshot_sha256),
            MIN(evaluation_snapshot_sha256)
        FROM analytics.fact_load_forecast_evaluation
        """
    ).one()
    _add_check(checks, "forecast.prediction_hash_count", 1, int(lineage[0]))
    _add_check(
        checks,
        "forecast.prediction_hash",
        artifacts.predictions_sha256,
        lineage[1],
    )
    _add_check(checks, "forecast.snapshot_hash_count", 1, int(lineage[2]))
    _add_check(
        checks,
        "forecast.snapshot_hash",
        artifacts.snapshot_sha256,
        lineage[3],
    )

    observed_metrics = connection.exec_driver_sql(
        """
        SELECT
            COUNT(*),
            ROUND(AVG(ABS(model_prediction_mw - actual_grid_load_mw)), 3),
            ROUND(SQRT(AVG(POWER(model_prediction_mw - actual_grid_load_mw, 2))), 3),
            ROUND(100 * AVG(
                ABS(model_prediction_mw - actual_grid_load_mw)
                    / actual_grid_load_mw
            ), 3),
            ROUND(AVG(ABS(daily_naive_prediction_mw - actual_grid_load_mw)), 3),
            ROUND(SQRT(AVG(POWER(
                daily_naive_prediction_mw - actual_grid_load_mw,
                2
            ))), 3),
            ROUND(100 * AVG(
                ABS(daily_naive_prediction_mw - actual_grid_load_mw)
                    / actual_grid_load_mw
            ), 3),
            ROUND(AVG(ABS(weekly_naive_prediction_mw - actual_grid_load_mw)), 3),
            ROUND(SQRT(AVG(POWER(
                weekly_naive_prediction_mw - actual_grid_load_mw,
                2
            ))), 3),
            ROUND(100 * AVG(
                ABS(weekly_naive_prediction_mw - actual_grid_load_mw)
                    / actual_grid_load_mw
            ), 3)
        FROM analytics.fact_load_forecast_evaluation
        """
    ).one()
    expected_metrics = _expected_overall_metrics(artifacts.snapshot)
    _add_check(
        checks,
        "forecast.metric_observations",
        expected_metrics["model"]["observations"],
        int(observed_metrics[0]),
    )
    offsets = {"model": 1, "daily": 4, "weekly": 7}
    for series, offset in offsets.items():
        for metric_offset, metric in enumerate(
            ("mae_mw", "rmse_mw", "mape_percent")
        ):
            _add_check(
                checks,
                f"forecast.{series}.{metric}",
                expected_metrics[series][metric],
                observed_metrics[offset + metric_offset],
            )
    return ForecastMartLoadReport(
        table_counts=table_counts,
        checks=tuple(checks),
    )


def load_forecast_mart(
    engine: Engine,
    artifacts: ForecastMartArtifacts,
) -> ForecastMartLoadReport:
    """Replace forecast staging and fact rows atomically and reconcile."""
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            TRUNCATE TABLE
                analytics.fact_load_forecast_evaluation,
                staging.final_forecast_predictions
            """
        )
        _copy_predictions(connection, artifacts)
        _populate_forecast_fact(connection, artifacts)
        report = reconcile_forecast_mart(connection, artifacts)
        if not report.ok:
            raise ForecastMartReconciliationError(report)
    return report
