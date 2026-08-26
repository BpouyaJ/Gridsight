# SQL reporting views

## Purpose

Step 4.3 creates a stable SQL interface between the reconciled analytical model
and later consumers such as exploratory notebooks, Power BI, and Excel. Those
consumers should query `reporting` views instead of depending on staging tables
or rebuilding business rules independently.

Apply and verify the views with PostgreSQL running and both the canonical and
Step 7.2 forecast facts loaded:

```powershell
python -m gridsight.database.apply_reporting
```

The command creates or replaces all six views transactionally, inspects their
exact ordered column contracts, and runs 28 live grain and measure
reconciliation checks.

## View contracts

### `reporting.hourly_energy`

Grain: one unique canonical UTC hour. Expected rows: 35,064.

This is the main hourly analysis view. It combines:

- Europe/Berlin calendar and local-hour attributes;
- UTC offset, DST, and repeated-hour fold context;
- Germany grid-load measures in MWh and MW;
- DE/LU day-ahead price in EUR/MWh;
- reported, renewable, conventional, and storage generation in MWh and MW;
- reported and unavailable technology counts.

Generation totals include only rows with `value_status = reported`. Unavailable
Nuclear values remain unavailable and are not estimated or silently converted
to zero.

### `reporting.hourly_generation_by_technology`

Grain: one unique canonical UTC hour and generation technology. Expected rows:
420,768.

This view preserves all 12 technology members, classification attributes,
numeric MWh/MW, availability status, and source export/hash lineage. It is the
correct source for technology comparisons and detailed renewable composition.

### `reporting.daily_energy`

Grain: one Europe/Berlin calendar date. Expected rows: 1,461.

Daily aggregation deliberately retains `observed_hour_count`. The four spring
clock-change dates contain 23 real hours, the four autumn dates contain 25, and
ordinary dates contain 24. No artificial local hour is inserted or removed.

### `reporting.monthly_energy`

Grain: one Europe/Berlin calendar month. Expected rows: 48.

The view aggregates directly from hourly rows, not from rounded daily
averages. This gives every observed hour equal weight when calculating monthly
average load and price.

### Forecast-performance views

Step 7.2 adds `reporting.forecast_performance_hourly` at one final 2025 origin
and horizon step (8,760 rows) and `reporting.forecast_performance_summary` at
one forecast series and overall-or-horizon scope (75 rows). Their guarded load,
metric formulas, and refresh order are documented in
[`forecast-reporting-mart.md`](forecast-reporting-mart.md).

## Aggregation rules

| Measure | Daily/monthly rule | Reason |
|---|---|---|
| Grid load MWh | Sum | Energy is additive over time. |
| Average grid load MW | Average hourly MW | Power is not additive over time. |
| Peak grid load MW | Maximum hourly MW | Represents the observed period peak. |
| Generation MWh | Sum reported values | Energy is additive; unavailable values remain excluded. |
| Day-ahead EUR/MWh | Average, minimum, maximum | Prices must never be summed. |
| Negative-price hours | Count | Preserves the frequency of market events. |
| Renewable share | Renewable MWh / all reported generation MWh | Uses like-for-like reported energy and exposes the denominator in the name. |

`renewable_share_of_reported_generation_percent` is not a share of electricity
consumption and not a claim about physical supply balance. Reported generation
can omit unavailable Nuclear values and differs conceptually from grid load.
Storage generation remains in its separate storage group and is not relabeled
as renewable.

## Reconciliation

The command and live integration test require:

- exact row counts and unique keys for all six grains;
- exactly 12 technology rows per UTC interval;
- daily and monthly observed-hour totals of 35,064;
- four 23-hour dates and four 25-hour dates;
- exact hourly load and price copies from the electricity fact;
- exact reported and renewable generation totals from the generation fact;
- exact daily and monthly load-energy totals;
- exact daily and monthly negative-price-hour totals.
- exactly 365 complete 24-step forecast origins;
- three overall and 72 horizon-specific forecast summary rows;
- zero weekly-baseline improvement against itself.

The views use `CREATE OR REPLACE VIEW` and contain no data-modifying SQL. They
are evaluated from the current analytical facts, so a successful Step 4.2 full
refresh is immediately reflected without refreshing a materialized object.

## Step boundary

Step 4.3 provides checked data products and KPI-ready grains but does not claim
analytical findings. The next contract is documented in
[`kpi-definitions.md`](kpi-definitions.md); focused exploratory findings remain
a separate Step 5.2 concern.

## Verified Step 4.3 result

Two consecutive command-line applications produced identical results:

- one SQL file and four `CREATE OR REPLACE VIEW` statements;
- four exact live view contracts;
- 19 passed reporting reconciliations and zero failures;
- 35,064 hourly energy rows;
- 420,768 hourly generation/technology rows;
- 1,461 daily rows and 48 monthly rows.

The fast suite passed all 40 selected tests with four live tests deselected.
The live suite passed database identity, idempotent data load, schema contract,
and idempotent reporting-view reconciliation tests with 40 fast tests
deselected. Ruff passed after removal of one unused import. This result
completes the Phase 4 PostgreSQL analytical-model gate.

Step 7.2 later extended the layer to six views. Its repeated live application
verified 8,760 forecast-detail rows, 75 forecast-summary rows, and 28 total
reporting reconciliations. The expanded fast suite passed 77 tests and all six
live PostgreSQL tests passed.
