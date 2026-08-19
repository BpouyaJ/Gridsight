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

## 2022-2023 actual-generation profile

- Export ID: `actual_generation_de_2022_2023`
- Original filename: `Actual_generation_202201010000_202401010000_Hour.csv`
- Normalized raw filename: `smard_actual_generation_de_2022_2023.csv`
- Size: 2,538,427 bytes
- SHA-256: `77175f940312421b40520ed2bc8de70d502ab4ab45ee68aee01ac8c085ebfab9`
- Data rows: 17,520
- Columns: 14
- Unique start-timestamp strings: 17,518

The file uses the same UTF-8 BOM, semicolon delimiter, English local timestamp
format, comma thousands separator, period decimal separator, two-decimal
precision, and hourly MWh unit as the consumption exports.

### Generation measures

1. Biomass
2. Hydropower
3. Wind offshore
4. Wind onshore
5. Photovoltaics
6. Other renewable
7. Nuclear
8. Lignite
9. Hard coal
10. Fossil gas
11. Hydro pumped storage
12. Other conventional

Every measure header follows the observed pattern
`<technology> [MWh] Calculated resolutions`. No blank or non-numeric measure
markers were observed in this snapshot.

### Time behavior

- First interval: 2022-01-01 00:00 to 01:00 local time
- Last interval: 2023-12-31 23:00 to 2024-01-01 00:00 local time
- The two spring transition dates contain 23 intervals.
- The two autumn transition dates contain 25 intervals with one repeated 02:00
  label per date.

The generation and consumption files share the same local-time grain and can
eventually use one UTC-normalization strategy. The generation columns will be
retained explicitly; their analytical shape will be decided during the
transformation and database-model phases.

## 2024-2025 actual-generation compatibility check

- Export ID: `actual_generation_de_2024_2025`
- Original filename: `Actual_generation_202401010000_202601010000_Hour.csv`
- Normalized raw filename: `smard_actual_generation_de_2024_2025.csv`
- Size: 2,435,894 bytes
- SHA-256: `8118719a1cd35b8bac2f3933ca90094fc3fdbe4eaf8b653e88e4097514ae2f64`
- Data rows: 17,544
- Columns: 14
- Unique start-timestamp strings: 17,542

The column names and order match the 2022-2023 generation snapshot exactly.
Encoding, delimiter, timestamp representation, numeric formatting, units, and
daylight-saving behavior also remain compatible. The extra 24 rows are expected
because 2024 is a leap year. Both generation hashes match their manifest
records.

### Nuclear source-marker change

Eleven generation measures remain numeric in every row. The `Nuclear` measure
changes representation during this snapshot:

- 708 rows from 2024-01-01 00:00 through 2024-01-30 11:00 contain numeric
  `0.00` values.
- 16,836 rows from 2024-01-30 12:00 through 2025-12-31 23:00 contain the
  non-numeric source marker `-`.
- No non-zero numeric nuclear values occur in this snapshot.

The marker is not assumed to equal a measured zero. The immutable raw value is
preserved, and the transformation layer will parse `-` as missing/unavailable
while retaining a quality flag. Any later contextual conversion to zero would
require a separate, documented analytical rule.

### Compatibility conclusion

The two generation snapshots can use one structural ingestion schema, with a
column-aware missing-marker rule for generation measures. Later validation must
test the allowed marker, UTC uniqueness, interval continuity, non-negative
generation, and the expected availability pattern rather than applying an
unqualified all-numeric rule.

## 2022-2023 DE/LU day-ahead-price profile

- Export ID: `day_ahead_price_de_lu_2022_2023`
- Original filename: `Day-ahead_prices_202201010000_202401010000_Hour.csv`
- Normalized raw filename: `smard_day_ahead_price_de_lu_2022_2023.csv`
- Size: 2,654,222 bytes
- SHA-256: `ce3c8c83e55168ba15eea8b8ce6979e1a5601954051b8186f0c42fbd436bc17c`
- Data rows: 17,520
- Columns: 19
- Target column: `Germany/Luxembourg [€/MWh] Calculated resolutions`
- Unique start-timestamp strings: 17,518

The export includes price columns for multiple European bidding zones. Only the
exact Germany/Luxembourg column is in GridSight's approved analytical scope;
the other market columns will not be mistaken for features or targets merely
because they occur in the same source file.

### Target-price values

- All 17,520 Germany/Luxembourg values are numeric; no blank or non-numeric
  source markers occur.
- 17,120 values are positive, 30 are zero, and 370 are negative.
- The observed minimum is -500.00 EUR/MWh at 2023-07-02 14:00 local time.
- The observed maximum is 871.00 EUR/MWh at 2022-08-29 19:00 local time.

Negative wholesale prices are legitimate market observations. Validation must
retain them and use documented plausible bounds rather than reject all values
below zero.

### Physical and time compatibility

The file uses UTF-8 with BOM, a semicolon delimiter, two-decimal values, and the
same local timestamp representation as the load and generation snapshots. Its
spring transition dates contain 23 rows, and its autumn transition dates
contain 25 rows with repeated local 02:00 labels. Price data therefore uses the
same required Europe/Berlin-to-UTC normalization strategy.

## 2024-2025 DE/LU day-ahead-price compatibility check

- Export ID: `day_ahead_price_de_lu_2024_2025`
- Original filename: `Day-ahead_prices_202401010000_202601010000_Hour.csv`
- Normalized raw filename: `smard_day_ahead_price_de_lu_2024_2025.csv`
- Size: 2,556,101 bytes
- SHA-256: `300309f929fd3ff100a61c792456df47ba5fef85f2a2cc0567146a219f9c485b`
- Data rows: 17,544
- Columns: 19
- Unique start-timestamp strings: 17,542

The 19 column names and order match the 2022-2023 price snapshot exactly. The
Germany/Luxembourg target remains fully numeric with no blank or non-numeric
markers:

- 16,370 values are positive, 144 are zero, and 1,030 are negative.
- The observed minimum is -250.32 EUR/MWh at 2025-05-11 13:00 local time.
- The observed maximum is 936.28 EUR/MWh at 2024-12-12 17:00 local time.

The additional 24 rows relative to the first period are expected from the 2024
leap day. Encoding, delimiter, units, timestamp representation, and daylight-
saving behavior are also compatible. Both price-file hashes match the tracked
manifest, so one structural ingestion schema and exact-name target selection
can cover both snapshots.
