"""CLI for building the canonical DE/LU day-ahead-price dataset."""

from pathlib import Path

from gridsight.ingestion.snapshot_registry import sha256_file
from gridsight.transformation.price import (
    DAY_AHEAD_PRICE_COLUMN,
    load_price_dataset,
    write_price_csv,
)
from gridsight.transformation.time_normalization import (
    INTERVAL_END_UTC_COLUMN,
    INTERVAL_START_UTC_COLUMN,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "smard_exports.json"
DEFAULT_MANIFEST = (
    PROJECT_ROOT / "data" / "manifests" / "smard_source_manifest.csv"
)
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_OUTPUT = (
    PROJECT_ROOT / "data" / "processed" / "day_ahead_price_hourly.csv"
)


def main() -> int:
    """Build one clean DE/LU price CSV from both immutable periods."""
    try:
        dataset = load_price_dataset(
            DEFAULT_CONFIG,
            DEFAULT_MANIFEST,
            DEFAULT_RAW_DIR,
        )
        write_price_csv(dataset, DEFAULT_OUTPUT)
    except (OSError, TypeError, ValueError) as error:
        print(f"Price transformation: FAILED ({error})")
        return 1

    prices = dataset[DAY_AHEAD_PRICE_COLUMN]
    first_utc = dataset.iloc[0][INTERVAL_START_UTC_COLUMN]
    last_end_utc = dataset.iloc[-1][INTERVAL_END_UTC_COLUMN]
    relative_output = DEFAULT_OUTPUT.relative_to(PROJECT_ROOT)
    print("Price transformation: OK")
    print(f"Rows: {len(dataset)}")
    print(f"Columns: {len(dataset.columns)}")
    print(f"Negative rows: {int((prices < 0).sum())}")
    print(f"Zero rows: {int((prices == 0).sum())}")
    print(f"Positive rows: {int((prices > 0).sum())}")
    print(f"Minimum: {prices.min():.2f} EUR/MWh")
    print(f"Maximum: {prices.max():.2f} EUR/MWh")
    print(f"First UTC start: {first_utc.isoformat()}")
    print(f"Last UTC end: {last_end_utc.isoformat()}")
    print(f"Output: {relative_output.as_posix()}")
    print(f"SHA-256: {sha256_file(DEFAULT_OUTPUT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
