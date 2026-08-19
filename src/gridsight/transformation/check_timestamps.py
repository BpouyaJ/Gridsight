"""CLI for checking canonical time normalization on all raw snapshots."""

from pathlib import Path

import pandas as pd

from gridsight.ingestion.snapshot_registry import load_export_definitions
from gridsight.transformation.time_normalization import (
    INTERVAL_END_UTC_COLUMN,
    INTERVAL_START_UTC_COLUMN,
    LOCAL_FOLD_COLUMN,
    SOURCE_END_COLUMN,
    SOURCE_START_COLUMN,
    UTC_OFFSET_MINUTES_COLUMN,
    normalize_hourly_timestamps,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "smard_exports.json"
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw"


def main() -> int:
    """Normalize real snapshot timestamps without writing transformed data."""
    try:
        definitions = load_export_definitions(DEFAULT_CONFIG)
        for definition in definitions.values():
            raw_path = DEFAULT_RAW_DIR / definition.local_filename
            frame = pd.read_csv(
                raw_path,
                sep=";",
                encoding="utf-8-sig",
                usecols=[SOURCE_START_COLUMN, SOURCE_END_COLUMN],
                dtype="string",
                keep_default_na=False,
            )
            normalized = normalize_hourly_timestamps(frame)
            offsets = sorted(
                normalized[UTC_OFFSET_MINUTES_COLUMN].unique().tolist()
            )
            repeated_fold_rows = int(
                (normalized[LOCAL_FOLD_COLUMN] == 1).sum()
            )
            first_utc = normalized.iloc[0][INTERVAL_START_UTC_COLUMN]
            last_end_utc = normalized.iloc[-1][INTERVAL_END_UTC_COLUMN]
            print(
                f"{definition.export_id}: rows={len(normalized)}, "
                f"first_utc={first_utc.isoformat()}, "
                f"last_end_utc={last_end_utc.isoformat()}, "
                f"offset_minutes={offsets}, fold_1_rows={repeated_fold_rows}"
            )
    except (OSError, TypeError, ValueError) as error:
        print(f"Timestamp normalization: FAILED ({error})")
        return 1

    print("Timestamp normalization: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
