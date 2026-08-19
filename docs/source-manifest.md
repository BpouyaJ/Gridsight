# SMARD source manifest and raw-data intake

GridSight records every raw SMARD snapshot before parsing or transformation.
The raw CSV remains outside Git; its small metadata record remains in Git.

## Approved exports

`configs/smard_exports.json` is the machine-readable source of truth for the
six approved exports. It fixes the category, geography, period, hourly
resolution, expected output series, output filename, licence, attribution, and
corresponding SMARD download filters. Expected series are output columns, not
additional controls in the SMARD download form.

## Manifest schema

| Field | Type | Rule |
|---|---|---|
| `export_id` | string | Must match one approved export definition. |
| `source_name` | string | Always `Bundesnetzagentur SMARD`. |
| `source_url` | URL | Official SMARD market-data download page. |
| `source_category` | enum | `actual_consumption`, `actual_generation`, or `day_ahead_price`. |
| `source_geography` | enum | `DE` or `DE-LU`, as defined by the export. |
| `source_resolution` | enum | `hour`. |
| `period_start` | ISO date | Inclusive requested start date. |
| `period_end` | ISO date | Inclusive requested end date. |
| `downloaded_at_utc` | UTC timestamp | Registration time using the `Z` suffix. |
| `original_filename` | string | Filename produced by the source download. |
| `local_filename` | string | Normalized immutable filename under `data/raw/`. |
| `sha256` | string | Lowercase 64-character content digest. |
| `licence` | string | `CC BY 4.0`. |
| `attribution` | string | `Bundesnetzagentur \| SMARD.de`. |
| `notes` | string | Optional factual registration note. |

The tracked manifest is `data/manifests/smard_source_manifest.csv`.

## Intake workflow

1. Use the exact filters shown by the `list` command.
2. Download the CSV to a temporary user location such as `Downloads`.
3. Do not open and resave the source CSV.
4. Register it immediately with its approved export ID.
5. Review the raw filename and manifest record, then commit the manifest only.

List the approved exports:

```powershell
python -m gridsight.ingestion.register_snapshot list
```

Register one downloaded CSV:

```powershell
python -m gridsight.ingestion.register_snapshot register `
  --export-id actual_consumption_de_2022_2023 `
  --file "C:\path\to\downloaded-smard-file.csv"
```

The command copies the bytes to the approved `data/raw/` filename, calculates
SHA-256, and appends one manifest record. Registering the same bytes again is
idempotent. Different bytes can never replace an existing normalized raw file.

## Revision rule

If SMARD publishes revised values, add a new approved export definition with a
revision suffix and a new local filename. Never overwrite the earlier snapshot
or edit its manifest row.
