# Source contract

## Essential source

- Provider: Bundesnetzagentur SMARD
- Portal: <https://www.smard.de/en/downloadcenter/download-market-data/>
- Licence: Creative Commons Attribution 4.0 International
- Required attribution: `Bundesnetzagentur | SMARD.de`

## Selected coverage

- Load and generation geography: Germany
- Price geography: DE/LU bidding zone
- Start: 2022-01-01
- End: 2025-12-31
- Selected export resolution: hourly
- Canonical processed timezone: UTC
- Reporting timezone: Europe/Berlin

SMARD limits a market-data export to two years. Each category will therefore be downloaded in two immutable snapshots: 2022-2023 and 2024-2025.

## Required categories

### Actual consumption

- Grid load
- Source meaning: electricity taken from the grid, as defined by SMARD
- Observed source column: `grid load [MWh] Calculated resolutions`
- Processed measures: hourly energy in MWh and derived average hourly load in MW

### Actual generation

Retain the available generation categories, including:

- Photovoltaics
- Wind onshore
- Wind offshore
- Biomass
- Hydropower
- Other renewable
- Available conventional generation categories

Processed measure: hourly energy generation in MWh.

### Day-ahead price

- DE/LU day-ahead wholesale price
- Observed source column: `Germany/Luxembourg [€/MWh] Calculated resolutions`
- Unit: EUR/MWh
- Hourly prices are averaged only when source intervals require aggregation; prices are never summed.
- Negative wholesale prices are valid observations and must not be removed by a generic non-negative rule.

## Planned raw filenames

```text
smard_actual_consumption_de_2022_2023.csv
smard_actual_consumption_de_2024_2025.csv
smard_actual_generation_de_2022_2023.csv
smard_actual_generation_de_2024_2025.csv
smard_day_ahead_price_de_lu_2022_2023.csv
smard_day_ahead_price_de_lu_2024_2025.csv
```

The actual downloaded names will be preserved. These normalized names may be used as immutable local copies after their original filenames are recorded in the manifest.

## Manifest fields

Every snapshot must record:

- `export_id`
- `source_name`
- `source_url`
- `source_category`
- `source_geography`
- `source_resolution`
- `period_start`
- `period_end`
- `downloaded_at_utc`
- `original_filename`
- `local_filename`
- `sha256`
- `licence`
- `attribution`
- `notes`

## Time and unit rules

- Raw SMARD timestamps follow CET/CEST conventions and must not be treated as naive unique keys.
- Preserve the original timestamp text before conversion.
- Convert timestamps to timezone-aware UTC before joining datasets.
- Retain Europe/Berlin local timestamp and DST attributes for reporting.
- Never fill repeated or missing daylight-saving hours without an explicit rule and a quality result.
- Preserve SMARD `-` measure markers in raw data and parse them as missing/unavailable with a quality flag; they are not measured zeroes.
- Never sum prices.
- Select the DE/LU price column by exact name because the source export contains other bidding-zone price columns.
- Never label MWh as MW. Average MW is derived from energy divided by interval duration.
- Retain market/source geography so DE/LU prices are not presented as Germany-only measurements.

## Raw-data policy

- Raw snapshots are immutable.
- Full raw files remain outside Git.
- Transformations write to `data/processed/` or PostgreSQL, never back into `data/raw/`.
- A small representative sample may be committed under `data/samples/` with the same attribution.
- Historical revisions require a new snapshot and manifest record, not silent replacement.

## Optional source

DWD Climate Data Center weather observations may be evaluated after the essential load-only forecast works. Observed future weather cannot be used as if it were available at a day-ahead forecast origin. Any forecasting use requires an explicit availability contract or archived forecast data.
