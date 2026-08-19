"""CLI for building the canonical actual-consumption dataset."""

from pathlib import Path

from gridsight.ingestion.snapshot_registry import sha256_file
from gridsight.transformation.consumption import (
    load_consumption_dataset,
    write_consumption_csv,
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
    PROJECT_ROOT / "data" / "processed" / "actual_consumption_hourly.csv"
)


def main() -> int:
    """Build one clean, continuous consumption CSV from both raw periods."""
    try:
        dataset = load_consumption_dataset(
            DEFAULT_CONFIG,
            DEFAULT_MANIFEST,
            DEFAULT_RAW_DIR,
        )
        write_consumption_csv(dataset, DEFAULT_OUTPUT)
    except (OSError, TypeError, ValueError) as error:
        print(f"Consumption transformation: FAILED ({error})")
        return 1

    first_utc = dataset.iloc[0][INTERVAL_START_UTC_COLUMN]
    last_end_utc = dataset.iloc[-1][INTERVAL_END_UTC_COLUMN]
    relative_output = DEFAULT_OUTPUT.relative_to(PROJECT_ROOT)
    print("Consumption transformation: OK")
    print(f"Rows: {len(dataset)}")
    print(f"Columns: {len(dataset.columns)}")
    print(f"First UTC start: {first_utc.isoformat()}")
    print(f"Last UTC end: {last_end_utc.isoformat()}")
    print(f"Output: {relative_output.as_posix()}")
    print(f"SHA-256: {sha256_file(DEFAULT_OUTPUT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
