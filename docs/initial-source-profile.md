# Initial SMARD source profile

## Snapshot

- Export ID: `actual_consumption_de_2022_2023`
- Original filename: `Actual_consumption_202201010000_202401010000_Hour (1).csv`
- Normalized raw filename: `smard_actual_consumption_de_2022_2023.csv`
- Size: 1,409,609 bytes
- SHA-256: `a70ec8ee64d04206c527c3252642d0e5111ae2d906a0d3d4f9281470cfe6f295`
- Requested period: 2022-01-01 through 2023-12-31
- Attribution: `Bundesnetzagentur | SMARD.de`

The raw file is ignored by Git. Its lineage record is tracked in
`data/manifests/smard_source_manifest.csv`.

## Physical structure

- Encoding: UTF-8 with byte-order mark (`EF BB BF`)
- Delimiter: semicolon
- Header rows: 1
- Data rows: 17,520
- Columns: 6
- Timestamp format: English month names with 12-hour AM/PM time
- Numeric format: comma thousands separator and period decimal separator
- Observed numeric precision: two decimal places
- Observed measure unit: MWh per hourly interval

## Columns

1. `Start date`
2. `End date`
3. `grid load [MWh] Calculated resolutions`
4. `Grid load incl. hydro pumped storage [MWh] Calculated resolutions`
5. `Hydro pumped storage [MWh] Calculated resolutions`
6. `Residual load [MWh] Calculated resolutions`

The primary GridSight load measure is column 3. It must not be confused with
the grid-load-including-pumped-storage column.

## Coverage and missing markers

- First interval: 2022-01-01 00:00 to 01:00 local time
- Last interval: 2023-12-31 23:00 to 2024-01-01 00:00 local time
- All 17,520 measure rows matched the observed numeric format.
- No blank or non-numeric measure markers were observed in this snapshot.

These are source-profile observations, not yet final validation results.

## Daylight-saving behavior

- 2022-03-27 contains 23 intervals and omits 02:00 local time.
- 2022-10-30 contains 25 intervals and repeats 02:00 local time.
- Across 2022-2023, there are 17,518 unique start-timestamp strings for 17,520
  rows because the autumn 02:00 label repeats once in each year.

The local timestamp text is therefore not a unique key. Transformation must
localize with Europe/Berlin daylight-saving rules and convert to UTC before
joining or enforcing uniqueness.

## Intake implications

- Read with UTF-8 BOM handling and semicolon delimiter.
- Parse numeric measures by removing thousands commas before conversion.
- Preserve the original timestamp strings for lineage and quality evidence.
- Do not drop or merge repeated local hours.
- Select the exact grid-load column explicitly rather than by position alone.

## 2024-2025 compatibility check

The second approved actual-consumption snapshot was registered and compared
read-only with the first snapshot.

- Original filename: `Actual_consumption_202401010000_202601010000_Hour.csv`
- Normalized raw filename: `smard_actual_consumption_de_2024_2025.csv`
- Size: 1,407,837 bytes
- SHA-256: `ab06c20d5a437b1f1570f5dc26b5e423e9d9b2043b845269faee105dffd19fd2`
- Data rows: 17,544
- First interval start: 2024-01-01 00:00 local time
- Last interval end: 2026-01-01 00:00 local time
- Unique start-timestamp strings: 17,542

The additional 24 rows relative to 2022-2023 are expected because 2024 is a
leap year.

### Compatibility result

- The six column names and order match exactly.
- Encoding remains UTF-8 with BOM.
- The delimiter remains semicolon.
- Numeric formatting and two-decimal precision remain unchanged.
- No blank or non-numeric measure markers were observed.
- Both raw-file hashes match their tracked manifest records.

The two consumption snapshots can therefore use one ingestion schema. This is
a source-profile conclusion only; the later validation phase will still test
row-level values, UTC uniqueness, interval continuity, and plausible ranges.

### Daylight-saving confirmation

- 2024-03-31 and 2025-03-30 each contain 23 intervals.
- 2024-10-27 and 2025-10-26 each contain 25 intervals with a repeated 02:00
  local timestamp label.

The second snapshot confirms that UTC conversion is a required transformation,
not an edge case unique to the first file.
