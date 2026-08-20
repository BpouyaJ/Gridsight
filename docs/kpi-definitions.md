# KPI definitions and query contract

## Purpose

Step 5.1 fixes GridSight's analytical vocabulary before exploratory findings
are written. Each KPI is calculated from the tested PostgreSQL `reporting`
views by a committed, read-only SQL query. This prevents later notebooks and
BI tools from quietly redefining the same metric.

Build the snapshot with PostgreSQL running and the Phase 4 data loaded:

```powershell
python -m gridsight.reporting.build_kpis
```

The command enforces exact columns and row counts, reconciles the three result
grains, and atomically writes `reports/kpi_snapshot.json`. The JSON contains no
runtime timestamp, so unchanged input data and query code produce identical
bytes and a stable SHA-256 hash.

## Query grains

| Query | Output grain | Expected rows |
|---|---|---:|
| `001_headline_kpis.sql` | Complete approved 2022-2025 period | 1 |
| `002_annual_kpis.sql` | Europe/Berlin calendar year | 4 |
| `003_generation_mix.sql` | Generation technology over the complete period | 12 |

The headline and annual queries use `reporting.hourly_energy`. The technology
mix uses `reporting.hourly_generation_by_technology` so it can preserve
reported-versus-unavailable status.

## Headline definitions

| KPI | Definition | Unit |
|---|---|---|
| Observed hours | Count of unique canonical UTC hourly intervals | hours |
| Total grid load | Sum of hourly grid-load energy divided by 1,000,000 | TWh |
| Average grid load | Mean hourly average load divided by 1,000 | GW |
| Minimum/peak grid load | Lowest/highest hourly average load; earliest UTC time wins a tie | GW |
| Reported generation | Sum of generation values whose source status is `reported` | TWh |
| Renewable generation | Reported generation classified as renewable | TWh |
| Conventional generation | Reported generation classified as conventional | TWh |
| Storage generation | Reported pumped-storage generation; not classified as renewable | TWh |
| Renewable share | Renewable reported MWh divided by all reported generation MWh | percent |
| Average/median price | Arithmetic mean/50th percentile of hourly DE/LU day-ahead prices | EUR/MWh |
| Minimum/maximum price | Lowest/highest hourly price; earliest UTC time wins a tie | EUR/MWh |
| Negative-price hours | Count of hourly prices below zero | hours |
| Negative-price share | Negative-price hours divided by all observed hours | percent |
| Unavailable generation values | Count of hour/technology observations marked unavailable | values |

Energy is summed over time. Average power and prices are averaged, not summed.
Peak and minimum power are observed hourly averages rather than instantaneous
system peaks.

## Annual definitions

Annual KPIs use the Europe/Berlin `calendar_year` attached to every canonical
UTC hour. They retain observed-hour counts, including leap year 2024, and use
the same unit and denominator rules as the headline metrics. The annual rows
are intended for comparable trend analysis, not for summing rounded headline
values.

## Generation-mix definitions

The technology query retains all 12 declared technologies in their stable
display order. `reported_hour_count` and `unavailable_hour_count` must sum to
35,064 for every technology.

`generation_twh` sums only numeric reported values. `reported_value_coverage`
shows the percentage of approved intervals with reported values.
`share_of_reported_generation_percent` divides a technology's reported MWh by
reported MWh across all technologies. An unavailable value is excluded from
the energy sum; it is never imputed as zero.

## Interpretation limits

- Grid load and reported generation are different system concepts and are not
  expected to balance in this dataset.
- Renewable share is a composition of reported generation, not a percentage
  of consumption and not a claim about final electricity use.
- DE/LU day-ahead prices are wholesale market observations, not household
  retail prices.
- Correlation does not establish causation. Relationship analysis and unusual
  periods belong to Step 5.2 and must retain this limitation.
- Aggregate values reflect the six immutable SMARD snapshots registered for
  this project and may differ from later source revisions.

## Contract failures

The build command fails instead of publishing a new snapshot when a query file
contains multiple statements, columns change or reorder, expected result
grains change, years are missing, hourly counts do not reconcile, technology
order changes, or unavailable-value counts disagree between grains.

## Step boundary

Step 5.1 defines and materializes descriptive KPIs. It does not select unusual
events, claim relationships between variables, create charts, or build
forecasting features. Those activities begin only after this contract passes
the fast and live PostgreSQL tests.

## Verified Step 5.1 result

Two consecutive builds produced the same deterministic snapshot:

- three query contracts;
- one headline row, four annual rows, and 12 technology rows;
- 35,064 observed hourly intervals;
- 1,871.998 TWh total grid load;
- 54.61% renewable share of reported generation;
- 124.58 EUR/MWh average DE/LU day-ahead price;
- 1,400 negative-price hours;
- 16,836 unavailable generation values;
- SHA-256
  `fa03ee1af919027634aeb45a524c713274bd9effcac9955052d3be449c8395fc`.

The fast suite passed all 43 selected tests with five live tests deselected.
The live suite passed all five PostgreSQL tests with 43 fast tests deselected,
including a complete load, reporting-view application, and KPI reconciliation.
Ruff and `git diff --check` passed.
