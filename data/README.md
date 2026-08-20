# Data policy

GridSight uses real public electricity-market data. Full raw and processed datasets are intentionally excluded from Git.

## Directories

- `raw/`: immutable local source snapshots; ignored by Git
- `manifests/`: tracked source lineage, filenames, filters, and checksums
- `processed/`: generated clean and analytical files; ignored by Git
- `samples/`: small, attributed recruiter/test samples that may be committed

## Essential source

Bundesnetzagentur SMARD: <https://www.smard.de/en/downloadcenter/download-market-data/>

- Licence: CC BY 4.0
- Attribution: `Bundesnetzagentur | SMARD.de`

The exact filters, period, units, time handling, filenames, and manifest requirements are defined in `docs/source-contract.md`.

## Rules

1. Never edit files in `data/raw/`.
2. Never commit full source datasets.
3. Record a SHA-256 checksum for every raw snapshot.
4. Preserve original timestamp and geography fields during ingestion.
5. Store generated files in `data/processed/`.
6. Include source attribution with every committed sample or exported public artifact.

The first Phase 3 generated output is
`processed/actual_consumption_hourly.csv`. It is rebuilt from immutable raw
snapshots and is never committed.

The second generated output is the long-form
`processed/actual_generation_hourly.csv`, with one interval/technology row and
explicit reported-versus-unavailable status. It is also ignored and rebuilt
from immutable raw snapshots.

The third generated output is
`processed/day_ahead_price_hourly.csv`. It contains only the approved DE/LU
price series from the wider market export and remains ignored.

The consolidated clean-data gate also creates
`processed/validation_issues.csv` and `processed/validation_summary.json`.
The issue file is header-only when validation passes. The JSON summary records
stable check results, dataset metrics, output paths, and output SHA-256 values.
Both artifacts are deterministic generated files and remain ignored.

Phase 6 also generates `processed/forecast_index.csv`. It contains one row per
forecast origin and horizon step, including actual load and baseline-source
timestamps, so it remains ignored. Its small tracked companion is
`reports/forecast_contract.json`, which records the protocol, counts, and
artifact hashes without publishing the full target series.

Step 6.3 generates `processed/forecast_features.csv`, one row per forecast
origin and horizon step. It remains ignored because it contains development
labels and derived row-level features. Its test labels are deliberately blank;
the tracked `reports/feature_contract.json` records only schema, counts, paths,
and hashes.

All six approved source snapshots have been registered locally: both Germany
actual-consumption periods, both Germany actual-generation periods, and both
DE/LU day-ahead-price periods. Their raw CSVs are ignored, while their
checksums and lineage records are tracked in the manifest.
