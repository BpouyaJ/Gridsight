# BI and Excel reporting-mart contract

## Purpose

Step 7.1 freezes the interface between GridSight's verified analytical assets
and its later Power BI and Excel deliverables. Consumer files must not invent
new grains, recalculate business rules differently, or read staging tables.

Build and verify the machine-readable contract from the project root:

```powershell
python -m gridsight.reporting.build_mart_contract
```

The command writes `reports/reporting_mart_contract.json`. It hash-gates the
existing reporting SQL, final forecast artifacts, passing 29-check data-quality
summary, and six-row source manifest before publishing any product contract.

## Product catalogue

| Product | Grain | Full rows | Delivery state | Consumers |
|---|---|---:|---|---|
| `hourly_energy` | One canonical UTC hour | 35,064 | Existing verified SQL view | Power BI |
| `hourly_generation_by_technology` | One UTC hour and technology | 420,768 | Existing verified SQL view | Power BI |
| `daily_energy` | One Europe/Berlin date | 1,461 | Existing verified SQL view | Power BI, Excel |
| `monthly_energy` | One Europe/Berlin month | 48 | Existing verified SQL view | Power BI, Excel |
| `forecast_performance_hourly` | One 2025 origin and horizon | 8,760 | Implemented Step 7.2 SQL view | Power BI |
| `forecast_performance_summary` | One series and evaluation scope | 75 | Implemented Step 7.2 SQL view | Power BI, Excel |
| `data_quality_checks` | One stable validation check | 29 | Implemented Step 7.3 extract | Power BI |
| `source_lineage` | One immutable SMARD export | 6 | Implemented Step 7.3 extract | Power BI |

All six SQL view contracts are imported without reinterpretation from the
verified reporting layer. Step 7.2 implements the two predeclared forecast
products through a hash-gated analytical fact. Data-quality and lineage
products remain small checked extracts instead of unnecessary database facts.

## Grain and unit rules

- UTC timestamps remain the unique fact keys; Europe/Berlin attributes exist
  for display, slicing, and DST interpretation.
- Forecast hourly keys are `(forecast_origin_utc, horizon_step)` because a
  target timestamp is not unique across the spring 23-hour origin interval.
- Energy measures retain `MWh`, average/instantaneous power retains `MW`,
  prices retain `EUR/MWh`, shares retain `percent`, and event totals retain
  `count`.
- Summary forecast rows use three series—the frozen learned model, daily
  seasonal naive, and weekly seasonal naive—at overall plus 24 horizon scopes,
  giving exactly `3 * 25 = 75` rows.
- Power BI and Excel may define presentation measures, but they must reconcile
  to the supplied columns and cannot silently change denominators or units.

## Checked public samples

| Sample file | Fixed filter | Rows |
|---|---|---:|
| `hourly_energy_sample.csv` | 2025-01-06 through 2025-01-12 | 168 |
| `hourly_generation_sample.csv` | Same seven dates, all 12 technologies | 2,016 |
| `daily_energy_sample.csv` | Calendar year 2025 | 365 |
| `monthly_energy_sample.csv` | All complete project months | 48 |
| `forecast_performance_hourly_sample.csv` | January 2025 origins | 744 |
| `forecast_performance_summary_sample.csv` | All series and scopes | 75 |
| `data_quality_checks.csv` | All canonical checks | 29 |
| `source_lineage.csv` | All registered exports | 6 |

The samples are deliberately fixed, compact, attributed, and reviewable in
Git. They are not substitutes for the ignored full row-level inputs. Step 7.3
generates them in deterministic order, verifies exact columns and counts,
records SHA-256 values, and reconciles their values with SQL or source artifacts.

## Implementation boundary

Step 7.3 generates the eight checked samples but does not build Power BI or
Excel. Those remain Phases 8 and 9.

## Verified Step 7.1 result

The real build verified four existing views, two planned forecast views, eight
sample policies, 29 passing data-quality checks, six source exports, and every
upstream SHA-256 dependency. The deterministic contract has SHA-256
`acb7d3137aaa2c7c4f6fd688520987e5c573cbbeba245938e564cbc5cf1abdbc`.

All 74 fast tests passed with six live database tests deselected, including the
five new tests for product uniqueness, existing-view compatibility, explicit
units and forecast grains, upstream hash gates, deterministic output, and
fixed portfolio-safe samples. Ruff and `git diff --check` also passed.

## Step 7.2 contract update

After implementing both forecast views, the contract marks all six PostgreSQL
products `verified_existing` while retaining the two Step 7.3 extracts as
planned. The regenerated contract hash is
`2b6e765eb106a706ae87b1e6c22d502b8bc18e3d995bf429a4d5889051532f95`.

## Step 7.3 sample implementation

All eight sample policies are now `verified_existing`. Three consecutive live
builds produced identical files after 28 successful reporting reconciliations.
The implemented contract SHA-256 is
`54a55962b79d14508eb50882578f2277b9201a678a055006c06f383632c71110`,
and the 3,451-row bundle manifest SHA-256 is
`b0a377003820b1321b6b55fb290f08ae07eff2f8e06e4688c9788b42ec42f150`.
All 82 fast tests and all six live PostgreSQL tests passed; Ruff and
`git diff --check` also passed.
