# Clean-data contract

## Canonical hourly time contract

Every clean GridSight dataset will use a unique UTC interval as its canonical
time key while retaining Europe/Berlin reporting context and the exact SMARD
source labels.

### Input requirements

- `Start date` and `End date` use SMARD's English 12-hour timestamp text.
- Rows remain in source order.
- Each raw start/end label pair spans one wall-clock hour.
- The source resolution is hourly.

### Output columns

| Column | Type | Meaning |
|---|---|---|
| `source_start_text` | string | Unchanged raw SMARD start label. |
| `source_end_text` | string | Unchanged raw SMARD end label. |
| `interval_start_utc` | timezone-aware datetime | Unique canonical interval key in UTC. |
| `interval_end_utc` | timezone-aware datetime | Exactly one real hour after the UTC start. |
| `interval_start_local` | timezone-aware datetime | Start rendered in `Europe/Berlin`. |
| `interval_end_local` | timezone-aware datetime | Canonical UTC end rendered in `Europe/Berlin`. |
| `utc_offset_minutes` | integer | Local UTC offset: 60 for CET or 120 for CEST. |
| `is_dst` | boolean | Whether the local start is in daylight-saving time. |
| `local_fold` | integer | `1` for the second occurrence of a repeated autumn hour; otherwise `0`. |

### Normalization rules

1. Parse English month abbreviations deterministically without depending on the
   computer's locale.
2. Preserve both source timestamp strings before creating canonical columns.
3. Localize ordered start timestamps to `Europe/Berlin`; source order assigns
   the first and second offsets to repeated autumn hours.
4. Convert localized starts to UTC and require them to be unique, strictly
   increasing, and one hour apart.
5. Derive `interval_end_utc` as `interval_start_utc + 1 hour`, then convert that
   canonical end back to Europe/Berlin for reporting.
6. Reject malformed text, unexpected source ordering, genuine gaps, duplicate
   UTC starts, or non-hourly source label pairs.

### Why source end text is not localized independently

SMARD's spring row from `01:00` to `02:00` ends on a local label that does not
exist when the clock jumps to `03:00`. During the autumn fallback, both source
rows beginning at `02:00` show `03:00` as their end. Independently localizing
those labels would create invalid or two-hour intervals.

GridSight therefore preserves `source_end_text` as lineage evidence but derives
the canonical end from the disambiguated UTC start and declared hourly
resolution. No row is dropped or merged.

### Verification

Run the normalization against all six immutable snapshots without writing clean
data:

```powershell
python -m gridsight.transformation.check_timestamps
```

The command succeeds only if every snapshot becomes continuous, unique hourly
UTC intervals. Focused tests separately cover the spring gap, both autumn
`02:00` occurrences, and rejection of a genuine source gap.

Measure parsing, category-specific names, missing-value flags, and clean-output
storage are defined in later Phase 3 steps.

## Actual-consumption clean dataset

Step 3.2 combines both registered actual-consumption snapshots into one
canonical dataset at `data/processed/actual_consumption_hourly.csv`. The file is
generated reproducibly and remains outside Git.

### Measure mapping

| SMARD source column | Canonical column | Unit |
|---|---|---|
| `grid load [MWh] Calculated resolutions` | `grid_load_mwh` | MWh |
| `Grid load incl. hydro pumped storage [MWh] Calculated resolutions` | `grid_load_including_pumped_storage_mwh` | MWh |
| `Hydro pumped storage [MWh] Calculated resolutions` | `hydro_pumped_storage_mwh` | MWh |
| `Residual load [MWh] Calculated resolutions` | `residual_load_mwh` | MWh |

`grid_load_mw` is the primary forecasting measure. It is derived as
`grid_load_mwh / interval_duration_hours`; for these one-hour intervals the two
columns are numerically equal but have different physical meanings.

### Measure rules

- Remove source thousands commas and parse every measure strictly as numeric.
- Reject blank, marker, infinite, or otherwise non-numeric consumption values.
- Require grid load, grid load including pumped storage, and pumped storage to
  be non-negative.
- Preserve negative residual load as a valid observation.
- Require grid load including pumped storage to equal grid load plus pumped
  storage within 0.011 MWh, allowing the observed 0.01 MWh rounding difference.
- Never relabel MWh as MW; derive average MW using the explicit one-hour
  duration.

### Row-level lineage

Every row carries its export ID, category, geography, resolution, source
period, original filename, normalized raw filename, and raw SHA-256. The two
periods are sorted by UTC start and must form one unique, continuous hourly
series.

### Build command

```powershell
python -m gridsight.transformation.build_consumption
```

The command rechecks both raw hashes, transforms both snapshots, writes the
clean CSV atomically, and prints its row count, UTC coverage, path, and
SHA-256. Re-running it safely replaces only the generated processed output.

### Verified build

The Step 3.2 verification produced:

- 35,064 continuous hourly rows;
- 24 canonical columns;
- UTC coverage from 2021-12-31 23:00 through 2025-12-31 23:00;
- output SHA-256
  `4a0107f087fdd5d87e584c913c6e73187f6e2c81057053964250cf3f1f9316a5`.

The processed file passed its strict measure, arithmetic, lineage, uniqueness,
continuity, atomic-write, and Git-ignore checks.

## Actual-generation clean dataset

Step 3.3 combines both actual-generation snapshots into the long-form dataset
`data/processed/actual_generation_hourly.csv`. Each row represents one unique
UTC interval and technology combination. The generated file remains outside
Git.

### Technology contract

| Technology ID | Display name | Group | Renewable |
|---|---|---|---|
| `biomass` | Biomass | renewable | yes |
| `hydropower` | Hydropower | renewable | yes |
| `wind_offshore` | Wind offshore | renewable | yes |
| `wind_onshore` | Wind onshore | renewable | yes |
| `solar_photovoltaic` | Solar photovoltaic | renewable | yes |
| `other_renewable` | Other renewable | renewable | yes |
| `nuclear` | Nuclear | conventional | no |
| `lignite` | Lignite | conventional | no |
| `hard_coal` | Hard coal | conventional | no |
| `fossil_gas` | Fossil gas | conventional | no |
| `hydro_pumped_storage` | Hydro pumped storage | storage | no |
| `other_conventional` | Other conventional | conventional | no |

Pumped-storage generation is classified separately as storage. It is not
included in renewable generation merely because the technology uses water.

### Value and availability rules

- Parse every reported technology value strictly as non-negative MWh.
- Derive average `generation_mw` from `generation_mwh` and the explicit
  one-hour duration.
- Preserve the original measure header and value text on every long-form row.
- Use `value_status = reported` for numeric source values.
- Allow `value_status = unavailable` only for the Nuclear source marker `-`.
- Store unavailable Nuclear MWh and MW as missing values, never as measured
  zero.
- Reject markers in every other technology and reject blank, invalid, infinite,
  or negative reported values.

Every UTC interval must contain exactly 12 unique technology rows. Both source
periods must combine into continuous interval coverage without duplicate
interval/technology keys. Shared manifest lineage columns use the same contract
as the actual-consumption dataset.

### Build command

```powershell
python -m gridsight.transformation.build_generation
```

The command rechecks both raw hashes, builds the long-form file atomically, and
prints interval, technology, numeric, unavailable, UTC-coverage, output-path,
and SHA-256 results.

### Verified build

The Step 3.3 verification produced:

- 420,768 interval/technology rows across 35,064 hourly intervals;
- 29 canonical columns and 12 technologies per interval;
- 403,932 numeric rows and 16,836 unavailable Nuclear rows;
- UTC coverage from 2021-12-31 23:00 through 2025-12-31 23:00;
- output SHA-256
  `9106f24f0e793a2807d4116edb1454490b5f9fc9a340c75c36e450634a3b328f`.

The output passed technology classification, allowed-marker, non-negative
generation, complete-key, continuity, shared-lineage, atomic-write, and
Git-ignore checks.
