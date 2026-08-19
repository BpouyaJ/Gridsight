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

One of six approved source snapshots has been registered locally: Germany
actual consumption for 2022-2023. Its raw CSV is ignored, while its checksum
and lineage record are tracked in the manifest.
