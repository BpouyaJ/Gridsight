"""CLI for building GridSight's verified KPI snapshot from PostgreSQL."""

from sqlalchemy.exc import SQLAlchemyError

from gridsight.database.connection import create_database_engine
from gridsight.reporting.kpi_contract import (
    DEFAULT_KPI_SNAPSHOT,
    build_kpi_snapshot,
    run_kpi_queries,
    sha256_file,
    write_kpi_snapshot,
)


def main() -> int:
    """Query stable reporting views and write the deterministic KPI artifact."""
    engine = None
    try:
        engine = create_database_engine()
        results = run_kpi_queries(engine)
        snapshot = build_kpi_snapshot(results)
        write_kpi_snapshot(snapshot, DEFAULT_KPI_SNAPSHOT)
    except (OSError, RuntimeError, SQLAlchemyError, TypeError, ValueError) as error:
        print(f"KPI snapshot: FAILED ({error})")
        return 1
    finally:
        if engine is not None:
            engine.dispose()

    headline = snapshot["headline_kpis"]
    print("KPI snapshot: OK")
    print(f"Query contracts: {len(results)}")
    print("Headline rows: 1")
    print(f"Annual rows: {len(snapshot['annual_kpis'])}")
    print(f"Technology rows: {len(snapshot['generation_mix'])}")
    print(f"Observed hours: {headline['observed_hour_count']}")
    print(f"Total grid load: {headline['total_grid_load_twh']:.3f} TWh")
    print(
        "Renewable share: "
        f"{headline['renewable_share_of_reported_generation_percent']:.2f}%"
    )
    print(
        "Average day-ahead price: "
        f"{headline['average_day_ahead_price_eur_per_mwh']:.2f} EUR/MWh"
    )
    relative_output = DEFAULT_KPI_SNAPSHOT.relative_to(
        DEFAULT_KPI_SNAPSHOT.parents[1]
    )
    print(f"Output: {relative_output}")
    print(f"SHA-256: {sha256_file(DEFAULT_KPI_SNAPSHOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
