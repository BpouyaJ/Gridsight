# Focused exploratory analysis

## Purpose

Step 5.2 converts the verified PostgreSQL reporting layer and Step 5.1 KPI
contract into a small set of reproducible portfolio figures and bounded
descriptive findings. It deliberately avoids an open-ended notebook and keeps
reusable logic under `src/gridsight/reporting/`.

Run the complete analysis with PostgreSQL available and the verified KPI
snapshot present:

```powershell
python -m gridsight.reporting.build_eda
```

The command first compares the committed KPI snapshot with fresh live KPI
queries. It stops if they differ. It then executes three EDA queries in one
repeatable-read database snapshot, validates their grains, builds a
deterministic JSON summary, and writes four PNG figures.

## Questions and analytical grains

| Question | Grain | Rows |
|---|---|---:|
| Monthly movement in load, renewable share, and price | Europe/Berlin calendar month | 48 |
| Weekday/weekend local-hour load shape | Local hour and day type | 48 |
| Daily associations and unusual-day rankings | Europe/Berlin calendar day | 1,461 |

Every grain must reconcile to the same 35,064 source hours. Monthly and daily
unavailable-generation counts must both reconcile to 16,836.

## Outputs

- `reports/eda_snapshot.json`: query metadata, five daily correlation rows,
  four load-shape extrema, six rule-selected unusual days, 48 monthly rows, and
  48 load-shape rows.
- `reports/figures/01_annual_kpis.png`: annual load, renewable share, and price.
- `reports/figures/02_monthly_energy_market.png`: three separate monthly panels
  with no misleading dual axis.
- `reports/figures/03_weekday_weekend_load_shape.png`: average local-hour load
  and descriptive 10th-90th percentile bands.
- `reports/figures/04_renewable_share_vs_price.png`: daily association separated
  by year.
- `notebooks/02_energy_market_eda.ipynb`: thin presentation notebook calling
  the same tested package functions.

## Methods

Energy is summed over time. Power and price are averaged. Renewable share uses
reported generation as its denominator. Unavailable generation values remain
excluded rather than becoming measured zero.

Daily renewable-share/price and load/price associations use Pearson
correlation. The report includes one complete-period value and one value for
each year because an aggregate coefficient can mix different price regimes.
The coefficients measure linear association only and do not establish
causation.

Six unusual-day rules select the earliest date in a tie:

1. maximum daily average grid-load power;
2. minimum daily average grid-load power;
3. maximum daily average day-ahead price;
4. minimum daily average day-ahead price;
5. maximum renewable share of reported generation;
6. maximum count of negative-price hours.

These labels are transparent descriptive rankings, not anomaly-detection or
operational alerting claims. Average GW, rather than daily GWh, selects the load
extrema so a 23-hour or 25-hour DST date is not mechanically favored by its
duration; daily GWh and observed hours remain in the selected-day context.

## Interpretation limits

- Europe/Berlin calendar days contain 23, 24, or 25 real hours around DST;
  `observed_hour_count` remains explicit.
- Grid load and reported generation are different system concepts and need not
  balance.
- The generation-share denominator excludes unavailable values, including the
  documented Nuclear source markers.
- DE/LU wholesale day-ahead prices are not retail electricity prices.
- The dataset omits explanatory drivers such as weather, fuel, carbon, imports,
  outages, and policy events, so observed associations have multiple possible
  explanations.
- Findings apply to the registered 2022-2025 SMARD snapshots and may differ
  from later source revisions.

## Step boundary

This step produces descriptive evidence only. Forecast targets, feature
availability, chronological splits, baselines, and learned models begin in
Phase 6 after the Phase 5 gate is verified.

## Verified findings

### Annual and monthly movement

- Annual grid-load energy fell from 482.296 TWh in 2022 to 458.382 TWh in
  2023, then partially recovered to 465.818 TWh in 2025. The 2025 value
  remained 3.4% below 2022.
- Renewable share of reported generation rose from 46.66% in 2022 to 58.86%
  in 2025, an increase of 12.20 percentage points.
- Average day-ahead price fell from 235.45 EUR/MWh in 2022 to 89.32 EUR/MWh in
  2025, a 62.1% decrease. It nevertheless increased from 78.51 EUR/MWh in
  2024, so the series is not a monotonic decline.
- Negative-price hours increased from 69 in 2022 to 573 in 2025.
- The highest monthly average load was 62.973 GW in February 2022; the lowest
  was 47.545 GW in August 2025. This is consistent with a visible winter-high,
  summer-low seasonal load pattern within the four-year sample.
- June 2025 had the highest monthly renewable share at 73.30%. August 2022 had
  the highest monthly average price at 465.18 EUR/MWh, while February 2024 had
  the lowest at 61.34 EUR/MWh.

### Local-hour load shape

- The weekday profile averaged its minimum of 43.686 GW at 02:00 and maximum
  of 63.977 GW at 11:00 Europe/Berlin time.
- The weekend profile averaged its minimum of 39.929 GW at 03:00 and maximum
  of 52.347 GW at 11:00.
- The shared 11:00 peak was 11.630 GW lower on weekends. The descriptive
  percentile bands also show substantial day-to-day variation around both
  average profiles.

### Daily associations

- Daily renewable share and average day-ahead price had a Pearson correlation
  of -0.631 across all 1,461 days.
- The association was negative in every individual year: -0.637 in 2022,
  -0.876 in 2023, -0.808 in 2024, and -0.882 in 2025.
- Daily average load and price had a weaker all-period correlation of 0.221,
  while yearly values ranged from -0.023 in 2022 to 0.598 in 2025. This
  instability reinforces that one aggregate coefficient does not explain
  market-price formation.

These coefficients describe association only. The dataset does not isolate
weather, fuel and carbon costs, cross-border flows, outages, bidding behavior,
or policy effects, so the results do not demonstrate that renewable output or
load alone caused prices.

### Rule-selected unusual days

| Rule | Selected local date | Selected value | Relevant context |
|---|---|---:|---|
| Highest average load | 2022-01-20 | 69.641 GW | Thursday; 24 hours |
| Lowest average load | 2023-05-28 | 37.536 GW | Sunday; 24 hours |
| Highest average price | 2022-08-26 | 699.44 EUR/MWh | Renewable share 38.23% |
| Lowest average price | 2023-07-02 | -53.87 EUR/MWh | Renewable share 79.04%; 15 negative hours |
| Highest renewable share | 2025-10-26 | 86.76% | 25-hour DST Sunday; average price 6.52 EUR/MWh |
| Most negative-price hours | 2023-12-24 | 23 hours | Sunday; average price -3.37 EUR/MWh; renewable share 81.80% |

The highest-renewable-share date contains 25 unavailable Nuclear values, one
for each observed hour. Its percentage therefore remains explicitly a share
of reported generation rather than a complete generation-balance claim.

## Verified artifacts and checks

Two consecutive builds produced identical hashes:

- `reports/eda_snapshot.json`:
  `8e2aed814ed1178dd6107974761d571dbae512bf7b6943fd72dee81b4ca7944d`;
- `01_annual_kpis.png`:
  `faca9bc2cd26474d2bafefb39ae0037ab4e5334fc4f8d5e49bd09fc82b515118`;
- `02_monthly_energy_market.png`:
  `5b6889398b1bd01a9a37caf911264d923be336608376f4c62fd3cee5c34d7411`;
- `03_weekday_weekend_load_shape.png`:
  `c4dd6cd2e0e1c997cc859be740b5b90021076cffcd73a36193d9312b292c909b`;
- `04_renewable_share_vs_price.png`:
  `e7c9ac69b8ccd56ad4c90054152f6800845e7a61d21d7d84be7d7ebc6e217af9`.

All four figures passed visual review. The fast suite passed 47 tests with six
live tests deselected. The live PostgreSQL suite passed all six tests with 47
fast tests deselected. Ruff and `git diff --check` passed.
