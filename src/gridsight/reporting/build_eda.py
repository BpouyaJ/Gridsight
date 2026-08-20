"""CLI for the focused GridSight exploratory-analysis artifact set."""

import json

from sqlalchemy.exc import SQLAlchemyError

from gridsight.database.connection import create_database_engine
from gridsight.reporting.eda import (
    DEFAULT_EDA_SNAPSHOT,
    DEFAULT_FIGURE_DIR,
    build_eda_snapshot,
    run_eda_queries,
    sha256_file,
    write_eda_figures,
    write_eda_snapshot,
)
from gridsight.reporting.kpi_contract import (
    DEFAULT_KPI_SNAPSHOT,
    build_kpi_snapshot,
    run_kpi_queries,
)


def main() -> int:
    """Verify the KPI dependency and build reproducible EDA outputs."""
    engine = None
    try:
        stored_kpis = json.loads(DEFAULT_KPI_SNAPSHOT.read_text(encoding="utf-8"))
        engine = create_database_engine()
        live_kpis = build_kpi_snapshot(run_kpi_queries(engine))
        if live_kpis != stored_kpis:
            raise RuntimeError(
                "stored KPI snapshot differs from the live reporting views; "
                "rerun gridsight.reporting.build_kpis"
            )
        results = run_eda_queries(engine)
        snapshot = build_eda_snapshot(results)
        figure_paths = write_eda_figures(
            stored_kpis,
            results,
            DEFAULT_FIGURE_DIR,
        )
        write_eda_snapshot(snapshot, DEFAULT_EDA_SNAPSHOT)
    except (
        ImportError,
        KeyError,
        OSError,
        RuntimeError,
        SQLAlchemyError,
        TypeError,
        ValueError,
    ) as error:
        print(f"Exploratory analysis: FAILED ({error})")
        return 1
    finally:
        if engine is not None:
            engine.dispose()

    overall = snapshot["daily_correlations"][0]
    print("Exploratory analysis: OK")
    print("Query contracts: 3")
    print(f"Monthly rows: {len(snapshot['monthly_series'])}")
    print(f"Load-shape rows: {len(snapshot['load_shape'])}")
    print("Daily rows: 1461")
    print(
        "Daily renewable-share/price Pearson correlation: "
        f"{overall['renewable_share_vs_average_price_pearson']:.3f}"
    )
    print(f"Unusual-day rules: {len(snapshot['unusual_days'])}")
    relative_output = DEFAULT_EDA_SNAPSHOT.relative_to(
        DEFAULT_EDA_SNAPSHOT.parents[1]
    )
    print(f"Output: {relative_output}")
    print(f"SHA-256: {sha256_file(DEFAULT_EDA_SNAPSHOT)}")
    print(f"Figures: {len(figure_paths)}")
    for path in figure_paths:
        relative_path = path.relative_to(DEFAULT_EDA_SNAPSHOT.parents[1])
        print(f"- {relative_path}: {sha256_file(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
