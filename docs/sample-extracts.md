# Checked reporting sample extracts

## Purpose

Step 7.3 publishes compact, reviewable evidence for Power BI, Excel/Power
Query, automated tests, and GitHub portfolio visitors. Full raw, processed, and
forecast row-level datasets remain excluded from Git.

## Build command

With PostgreSQL running and the Step 7.2 marts loaded, run:

```powershell
python -m gridsight.reporting.build_samples
```

The command first requires the six live reporting views and all 28 reporting
reconciliations to pass. It reads the SQL extracts inside one PostgreSQL
repeatable-read, read-only transaction, builds the two checked artifact
extracts, fixes the database session to UTC, validates all eight frames, stages
every output, and publishes the manifest last.

## Fixed samples

| File | Source and filter | Rows |
|---|---|---:|
| `hourly_energy_sample.csv` | Hourly energy, 2025-01-06 through 2025-01-12 | 168 |
| `hourly_generation_sample.csv` | Same seven dates and all 12 technologies | 2,016 |
| `daily_energy_sample.csv` | Every Europe/Berlin date in 2025 | 365 |
| `monthly_energy_sample.csv` | All 48 months from 2022 through 2025 | 48 |
| `forecast_performance_hourly_sample.csv` | All 31 January 2025 forecast origins | 744 |
| `forecast_performance_summary_sample.csv` | Three series at overall plus 24 horizons | 75 |
| `data_quality_checks.csv` | All passing canonical validation checks | 29 |
| `source_lineage.csv` | All six immutable SMARD registrations | 6 |

Total committed data rows: 3,451.

## Validation and reproducibility

Every file must match its contracted ordered columns, exact row count, unique
key, fixed scope, and deterministic ordering. CSVs use UTF-8 and LF endings.
Dates and timestamps use ISO representations, booleans use lowercase
`true`/`false`, numeric database values retain decimal text, and missing values
remain empty rather than being changed to zero.

`reports/sample_extract_manifest.json` records:

- the exact reporting-mart contract hash;
- the source validation-summary and source-manifest hashes;
- all eight paths, SHA-256 values, row counts, schemas, keys, filters, and
  source products;
- the required attribution and successful 28-check reporting gate.

The builder verifies all staged files before replacement and publishes the
manifest only after the contract and eight CSVs are in place. Repeating the
command against unchanged sources must reproduce identical bytes and hashes.

## Verified Step 7.3 result

Three consecutive live builds produced the same eight file hashes and the same
manifest. The reporting-mart contract SHA-256 is
`54a55962b79d14508eb50882578f2277b9201a678a055006c06f383632c71110`;
the manifest SHA-256 is
`b0a377003820b1321b6b55fb290f08ae07eff2f8e06e4688c9788b42ec42f150`.

| Product | SHA-256 |
|---|---|
| `hourly_energy` | `02e3347e229a3a812eaa086558f33483f1f9a9a19e6ce0c39d01594c78dfebeb` |
| `hourly_generation_by_technology` | `dc39ad656b2f1d8fdd1469112d826980806966a2cd3f75547b5d32476ce73eb7` |
| `daily_energy` | `dfec93328728d2449d5441e4ec05148ab94704e70327e5b00d184ebf384c910b` |
| `monthly_energy` | `86a17351935e5cf9bebec2b1bad8b6da00359363df09e8f65c73fd0422c78676` |
| `forecast_performance_hourly` | `3f8a0dc4bb484b4a322b1da3121039ab4995d63d9a173dbfbc0ec5184ea37bfa` |
| `forecast_performance_summary` | `6c3585dd78372ded0f861579789305b6c24ba724a8d5180aedf56b964b728fa1` |
| `data_quality_checks` | `5bad3f65f96408b69c993262487b76136ab095027de95b7141dad8f83b763e6f` |
| `source_lineage` | `fc1012b6bf2eda5571006bd2637e9ee1c8c596ac7b56dd531907e4a0609d6507` |

Verification closed with 82 passing fast tests, six passing live PostgreSQL
tests, clean Ruff output, and no `git diff --check` errors.

## Attribution and limits

The required market-data attribution is:

> Bundesnetzagentur | SMARD.de

These files are fixed illustrative extracts. They are not complete datasets,
an operational forecast feed, or evidence of production deployment.
