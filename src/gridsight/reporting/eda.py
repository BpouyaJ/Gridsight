"""Focused, reproducible exploratory analysis over verified reporting views."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy.engine import Connection, Engine

from gridsight.database.schema_contract import PROJECT_ROOT, split_sql_statements
from gridsight.reporting.kpi_contract import SOURCE_ATTRIBUTION

DEFAULT_EDA_SNAPSHOT = PROJECT_ROOT / "reports" / "eda_snapshot.json"
DEFAULT_FIGURE_DIR = PROJECT_ROOT / "reports" / "figures"
SOURCE_VIEWS = (
    "reporting.hourly_energy",
    "reporting.daily_energy",
    "reporting.monthly_energy",
)


@dataclass(frozen=True)
class EDAQueryContract:
    """Expected SQL file, grain, ordered columns, and current-scope rows."""

    name: str
    sql_path: Path
    grain: str
    columns: tuple[str, ...]
    expected_rows: int


@dataclass(frozen=True)
class EDAQueryResult:
    """One focused analysis query after contract verification."""

    name: str
    columns: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]


EDA_QUERY_CONTRACTS = (
    EDAQueryContract(
        name="monthly_series",
        sql_path=PROJECT_ROOT / "sql" / "analysis" / "004_monthly_eda.sql",
        grain="one Europe/Berlin calendar month",
        columns=(
            "month_start",
            "calendar_year",
            "month_number",
            "month_name",
            "observed_day_count",
            "observed_hour_count",
            "grid_load_twh",
            "average_grid_load_gw",
            "peak_grid_load_gw",
            "reported_generation_twh",
            "renewable_generation_twh",
            "renewable_share_of_reported_generation_percent",
            "average_day_ahead_price_eur_per_mwh",
            "minimum_day_ahead_price_eur_per_mwh",
            "maximum_day_ahead_price_eur_per_mwh",
            "negative_price_hour_count",
            "unavailable_generation_value_count",
        ),
        expected_rows=48,
    ),
    EDAQueryContract(
        name="load_shape",
        sql_path=PROJECT_ROOT / "sql" / "analysis" / "005_load_shape.sql",
        grain="one local clock hour and weekday/weekend class",
        columns=(
            "hour_key",
            "hour_label",
            "day_type",
            "observed_hour_count",
            "average_grid_load_gw",
            "p10_grid_load_gw",
            "p90_grid_load_gw",
        ),
        expected_rows=48,
    ),
    EDAQueryContract(
        name="daily_relationships",
        sql_path=(
            PROJECT_ROOT / "sql" / "analysis" / "006_daily_relationships.sql"
        ),
        grain="one Europe/Berlin calendar day",
        columns=(
            "calendar_date",
            "calendar_year",
            "month_number",
            "weekday_name",
            "is_weekend",
            "observed_hour_count",
            "grid_load_gwh",
            "average_grid_load_gw",
            "peak_grid_load_gw",
            "renewable_generation_gwh",
            "renewable_share_of_reported_generation_percent",
            "average_day_ahead_price_eur_per_mwh",
            "minimum_day_ahead_price_eur_per_mwh",
            "maximum_day_ahead_price_eur_per_mwh",
            "negative_price_hour_count",
            "unavailable_generation_value_count",
        ),
        expected_rows=1_461,
    ),
)


def _execute_query(
    connection: Connection,
    contract: EDAQueryContract,
) -> EDAQueryResult:
    sql_text = contract.sql_path.read_text(encoding="utf-8")
    statements = split_sql_statements(sql_text)
    if len(statements) != 1:
        raise ValueError(
            f"{contract.sql_path.name} must contain exactly one SQL statement"
        )
    result = connection.exec_driver_sql(statements[0])
    columns = tuple(result.keys())
    rows = tuple(dict(row) for row in result.mappings())
    if columns != contract.columns:
        raise RuntimeError(
            f"EDA column contract mismatch for {contract.name}: "
            f"expected {contract.columns}, observed {columns}"
        )
    if len(rows) != contract.expected_rows:
        raise RuntimeError(
            f"EDA row contract mismatch for {contract.name}: "
            f"expected {contract.expected_rows}, observed {len(rows)}"
        )
    return EDAQueryResult(contract.name, columns, rows)


def _result_map(
    results: tuple[EDAQueryResult, ...],
) -> dict[str, EDAQueryResult]:
    result_map = {result.name: result for result in results}
    expected_names = {contract.name for contract in EDA_QUERY_CONTRACTS}
    if set(result_map) != expected_names or len(result_map) != len(results):
        raise RuntimeError("EDA results do not match the declared query contracts")
    return result_map


def validate_eda_results(results: tuple[EDAQueryResult, ...]) -> None:
    """Reject changed grains, incomplete periods, or cross-grain mismatches."""
    result_map = _result_map(results)
    for contract in EDA_QUERY_CONTRACTS:
        result = result_map[contract.name]
        if result.columns != contract.columns:
            raise RuntimeError(f"EDA column contract mismatch for {contract.name}")
        if len(result.rows) != contract.expected_rows:
            raise RuntimeError(f"EDA row contract mismatch for {contract.name}")

    monthly_rows = result_map["monthly_series"].rows
    shape_rows = result_map["load_shape"].rows
    daily_rows = result_map["daily_relationships"].rows
    if monthly_rows[0]["month_start"] != date(2022, 1, 1):
        raise RuntimeError("monthly EDA series must begin at 2022-01-01")
    if monthly_rows[-1]["month_start"] != date(2025, 12, 1):
        raise RuntimeError("monthly EDA series must end at 2025-12-01")
    if sum(row["observed_hour_count"] for row in monthly_rows) != 35_064:
        raise RuntimeError("monthly EDA hours must reconcile to 35,064")

    expected_shape = [
        (day_type, hour_key)
        for day_type in ("weekday", "weekend")
        for hour_key in range(24)
    ]
    observed_shape = [
        (row["day_type"], row["hour_key"]) for row in shape_rows
    ]
    if observed_shape != expected_shape:
        raise RuntimeError("load shape must contain ordered hours 0-23 per day type")
    if sum(row["observed_hour_count"] for row in shape_rows) != 35_064:
        raise RuntimeError("load-shape hours must reconcile to 35,064")

    daily_dates = [row["calendar_date"] for row in daily_rows]
    if daily_dates[0] != date(2022, 1, 1):
        raise RuntimeError("daily EDA series must begin at 2022-01-01")
    if daily_dates[-1] != date(2025, 12, 31):
        raise RuntimeError("daily EDA series must end at 2025-12-31")
    if len(set(daily_dates)) != 1_461:
        raise RuntimeError("daily EDA dates must be unique")
    if sum(row["observed_hour_count"] for row in daily_rows) != 35_064:
        raise RuntimeError("daily EDA hours must reconcile to 35,064")

    unavailable_totals = {
        sum(row["unavailable_generation_value_count"] for row in monthly_rows),
        sum(row["unavailable_generation_value_count"] for row in daily_rows),
    }
    if unavailable_totals != {16_836}:
        raise RuntimeError("EDA availability counts do not reconcile to 16,836")


def run_eda_queries(engine: Engine) -> tuple[EDAQueryResult, ...]:
    """Execute all EDA queries in one repeatable-read database snapshot."""
    with engine.connect().execution_options(
        isolation_level="REPEATABLE READ"
    ) as connection:
        results = tuple(
            _execute_query(connection, contract)
            for contract in EDA_QUERY_CONTRACTS
        )
    validate_eda_results(results)
    return results


def eda_frames(
    results: tuple[EDAQueryResult, ...],
) -> dict[str, pd.DataFrame]:
    """Return independent DataFrames for presentation and tested analysis."""
    validate_eda_results(results)
    return {
        result.name: pd.DataFrame(result.rows, columns=result.columns)
        for result in results
    }


def _numeric(frame: pd.DataFrame, columns: tuple[str, ...]) -> None:
    for column in columns:
        frame[column] = pd.to_numeric(frame[column], errors="raise")


def _prepared_frames(
    results: tuple[EDAQueryResult, ...],
) -> dict[str, pd.DataFrame]:
    frames = eda_frames(results)
    monthly = frames["monthly_series"]
    shape = frames["load_shape"]
    daily = frames["daily_relationships"]
    monthly["month_start"] = pd.to_datetime(monthly["month_start"])
    daily["calendar_date"] = pd.to_datetime(daily["calendar_date"])
    _numeric(
        monthly,
        (
            "grid_load_twh",
            "average_grid_load_gw",
            "renewable_share_of_reported_generation_percent",
            "average_day_ahead_price_eur_per_mwh",
        ),
    )
    _numeric(
        shape,
        (
            "hour_key",
            "average_grid_load_gw",
            "p10_grid_load_gw",
            "p90_grid_load_gw",
        ),
    )
    _numeric(
        daily,
        (
            "calendar_year",
            "grid_load_gwh",
            "average_grid_load_gw",
            "peak_grid_load_gw",
            "renewable_generation_gwh",
            "renewable_share_of_reported_generation_percent",
            "average_day_ahead_price_eur_per_mwh",
            "minimum_day_ahead_price_eur_per_mwh",
            "maximum_day_ahead_price_eur_per_mwh",
            "negative_price_hour_count",
        ),
    )
    return frames


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if value is None or isinstance(value, (bool, float, int, str)):
        return value
    raise TypeError(f"Unsupported EDA value type: {type(value).__name__}")


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {key: _json_value(value) for key, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]


def _correlation_row(frame: pd.DataFrame, period: str) -> dict[str, Any]:
    renewable = frame["renewable_share_of_reported_generation_percent"]
    load = frame["average_grid_load_gw"]
    price = frame["average_day_ahead_price_eur_per_mwh"]
    return {
        "period": period,
        "day_count": int(len(frame)),
        "renewable_share_vs_average_price_pearson": round(
            float(renewable.corr(price)), 3
        ),
        "average_load_vs_average_price_pearson": round(
            float(load.corr(price)), 3
        ),
    }


def _ranked_day(
    frame: pd.DataFrame,
    event_id: str,
    metric: str,
    ascending: bool,
) -> dict[str, Any]:
    selected = frame.sort_values(
        [metric, "calendar_date"],
        ascending=[ascending, True],
        kind="stable",
    ).iloc[0]
    record = {key: _json_value(value) for key, value in selected.items()}
    return {
        "event_id": event_id,
        "selection_metric": metric,
        "selection_direction": "minimum" if ascending else "maximum",
        **record,
    }


def _load_shape_extremes(shape: pd.DataFrame) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for day_type in ("weekday", "weekend"):
        subset = shape.loc[shape["day_type"] == day_type]
        for label, ascending in (("minimum", True), ("maximum", False)):
            selected = subset.sort_values(
                ["average_grid_load_gw", "hour_key"],
                ascending=[ascending, True],
                kind="stable",
            ).iloc[0]
            records.append(
                {
                    "day_type": day_type,
                    "extreme": label,
                    "hour_key": int(selected["hour_key"]),
                    "hour_label": str(selected["hour_label"]),
                    "average_grid_load_gw": float(
                        selected["average_grid_load_gw"]
                    ),
                }
            )
    return records


def build_eda_snapshot(
    results: tuple[EDAQueryResult, ...],
) -> dict[str, Any]:
    """Build deterministic descriptive results and rule-based unusual days."""
    frames = _prepared_frames(results)
    monthly = frames["monthly_series"]
    shape = frames["load_shape"]
    daily = frames["daily_relationships"]
    correlations = [_correlation_row(daily, "2022-2025")]
    correlations.extend(
        _correlation_row(
            daily.loc[daily["calendar_year"] == year],
            str(year),
        )
        for year in range(2022, 2026)
    )
    unusual_specs = (
        ("highest_average_load", "average_grid_load_gw", False),
        ("lowest_average_load", "average_grid_load_gw", True),
        ("highest_average_price", "average_day_ahead_price_eur_per_mwh", False),
        ("lowest_average_price", "average_day_ahead_price_eur_per_mwh", True),
        (
            "highest_renewable_share",
            "renewable_share_of_reported_generation_percent",
            False,
        ),
        ("most_negative_price_hours", "negative_price_hour_count", False),
    )
    unusual_days = [
        _ranked_day(daily, event_id, metric, ascending)
        for event_id, metric, ascending in unusual_specs
    ]
    contracts = {
        contract.name: {
            "grain": contract.grain,
            "row_count": contract.expected_rows,
            "sql_file": contract.sql_path.relative_to(PROJECT_ROOT).as_posix(),
        }
        for contract in EDA_QUERY_CONTRACTS
    }
    return {
        "schema_version": 1,
        "source_attribution": SOURCE_ATTRIBUTION,
        "source_views": list(SOURCE_VIEWS),
        "period": {
            "start_local_date": "2022-01-01",
            "end_local_date": "2025-12-31",
        },
        "query_contracts": contracts,
        "correlation_method": "Pearson correlation over daily observations",
        "daily_correlations": correlations,
        "load_shape_extremes": _load_shape_extremes(shape),
        "unusual_days": unusual_days,
        "monthly_series": _records(monthly),
        "load_shape": _records(shape),
    }


def write_eda_snapshot(snapshot: dict[str, Any], output_path: Path) -> None:
    """Write deterministic EDA JSON atomically."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(f"{output_path.suffix}.tmp")
    payload = json.dumps(snapshot, indent=2, sort_keys=True) + "\n"
    temporary_path.write_text(payload, encoding="utf-8", newline="\n")
    temporary_path.replace(output_path)


def _save_figure(figure: Any, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(
        f"{output_path.stem}.tmp{output_path.suffix}"
    )
    figure.savefig(
        temporary_path,
        dpi=160,
        bbox_inches="tight",
        facecolor="white",
        metadata={"Software": "GridSight"},
    )
    temporary_path.replace(output_path)


def write_eda_figures(
    kpi_snapshot: dict[str, Any],
    results: tuple[EDAQueryResult, ...],
    output_dir: Path,
) -> tuple[Path, ...]:
    """Create four focused PNG figures from verified KPI and EDA results."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    frames = _prepared_frames(results)
    monthly = frames["monthly_series"]
    shape = frames["load_shape"]
    daily = frames["daily_relationships"]
    annual = pd.DataFrame(kpi_snapshot["annual_kpis"])
    colors = {
        "load": "#1f4e79",
        "renewable": "#2e8b57",
        "price": "#c65f18",
        "weekend": "#7b61a8",
    }
    paths: list[Path] = []
    style = {
        "axes.grid": True,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "grid.alpha": 0.25,
        "figure.dpi": 120,
    }
    with plt.rc_context(style):
        figure, axes = plt.subplots(1, 3, figsize=(13, 4.2))
        years = annual["calendar_year"].astype(str)
        axes[0].bar(years, annual["grid_load_twh"], color=colors["load"])
        axes[0].set(title="Grid load", ylabel="TWh")
        axes[1].bar(
            years,
            annual["renewable_share_of_reported_generation_percent"],
            color=colors["renewable"],
        )
        axes[1].set(title="Renewable share", ylabel="Percent")
        axes[2].bar(
            years,
            annual["average_day_ahead_price_eur_per_mwh"],
            color=colors["price"],
        )
        axes[2].set(title="Average day-ahead price", ylabel="EUR/MWh")
        figure.suptitle("GridSight annual KPI overview, 2022-2025")
        figure.tight_layout()
        path = output_dir / "01_annual_kpis.png"
        _save_figure(figure, path)
        plt.close(figure)
        paths.append(path)

        figure, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
        axes[0].plot(
            monthly["month_start"],
            monthly["average_grid_load_gw"],
            color=colors["load"],
        )
        axes[0].set(ylabel="GW", title="Average grid load")
        axes[1].plot(
            monthly["month_start"],
            monthly["renewable_share_of_reported_generation_percent"],
            color=colors["renewable"],
        )
        axes[1].set(ylabel="Percent", title="Renewable share")
        axes[2].plot(
            monthly["month_start"],
            monthly["average_day_ahead_price_eur_per_mwh"],
            color=colors["price"],
        )
        axes[2].axhline(0, color="#333333", linewidth=0.8)
        axes[2].set(ylabel="EUR/MWh", title="Average day-ahead price")
        figure.suptitle("Monthly energy-market indicators")
        figure.tight_layout()
        path = output_dir / "02_monthly_energy_market.png"
        _save_figure(figure, path)
        plt.close(figure)
        paths.append(path)

        figure, axis = plt.subplots(figsize=(10, 5.5))
        for day_type, color in (
            ("weekday", colors["load"]),
            ("weekend", colors["weekend"]),
        ):
            subset = shape.loc[shape["day_type"] == day_type]
            hour = subset["hour_key"].to_numpy(dtype=float)
            average = subset["average_grid_load_gw"].to_numpy(dtype=float)
            lower = subset["p10_grid_load_gw"].to_numpy(dtype=float)
            upper = subset["p90_grid_load_gw"].to_numpy(dtype=float)
            axis.plot(hour, average, label=day_type.title(), color=color)
            axis.fill_between(hour, lower, upper, color=color, alpha=0.12)
        axis.set(
            title="Average local-hour load shape with 10th-90th percentile band",
            xlabel="Europe/Berlin clock hour",
            ylabel="Grid load (GW)",
            xticks=range(0, 24, 2),
        )
        axis.legend(frameon=False)
        figure.tight_layout()
        path = output_dir / "03_weekday_weekend_load_shape.png"
        _save_figure(figure, path)
        plt.close(figure)
        paths.append(path)

        figure, axis = plt.subplots(figsize=(10, 6))
        for year, color in zip(
            range(2022, 2026),
            ("#1f4e79", "#2e8b57", "#c65f18", "#7b61a8"),
            strict=True,
        ):
            subset = daily.loc[daily["calendar_year"] == year]
            axis.scatter(
                subset["renewable_share_of_reported_generation_percent"],
                subset["average_day_ahead_price_eur_per_mwh"],
                s=13,
                alpha=0.45,
                color=color,
                label=str(year),
                edgecolors="none",
            )
        axis.axhline(0, color="#333333", linewidth=0.8)
        axis.set(
            title="Daily renewable share and average day-ahead price",
            xlabel="Renewable share of reported generation (percent)",
            ylabel="Average day-ahead price (EUR/MWh)",
        )
        axis.legend(title="Year", frameon=False)
        figure.tight_layout()
        path = output_dir / "04_renewable_share_vs_price.png"
        _save_figure(figure, path)
        plt.close(figure)
        paths.append(path)
    return tuple(paths)


def sha256_file(path: Path) -> str:
    """Return a lowercase SHA-256 digest for one EDA artifact."""
    return hashlib.sha256(path.read_bytes()).hexdigest()
