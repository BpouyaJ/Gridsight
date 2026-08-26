# Forecast reporting mart

## Purpose

Step 7.2 promotes the ignored, final 2025 forecast-evaluation artifact into a
constrained PostgreSQL fact and two stable BI views. Power BI and Excel can
therefore analyze final model performance without reading an ignored local CSV
or recreating metric formulas.

## Trust and transaction boundary

Run the load only after the canonical database load is present:

```powershell
python -m gridsight.database.load_forecast_mart
```

Before connecting, the command verifies:

- the tracked final-evaluation snapshot has schema version 1;
- prediction path, SHA-256, 8,760 rows, and 16 ordered columns match exactly;
- the selected model remains `hist_gradient_boosting_31_leaves`;
- further model selection is forbidden and test data did not select the model;
- all 365 origins have exactly 24 non-leaking horizon rows;
- model errors and absolute errors reconcile to actual and predicted MW.

The load then applies the current schema, replaces forecast staging and fact
rows in one transaction, and commits only if 21 row, grain, lineage, copy, and
metric checks pass. A failure rolls back the replacement.

## Database products

### `staging.final_forecast_predictions`

Grain: one final 2025 forecast origin and horizon step. Expected rows: 8,760.

This table mirrors the verified CSV's 16 columns. Database checks enforce test
scope, horizons 1-24, timestamp arithmetic, daily and weekly lag availability,
positive MW values, the frozen model name, and exact error arithmetic.

### `analytics.fact_load_forecast_evaluation`

Grain: one final 2025 forecast origin and horizon step. Expected rows: 8,760.

The fact adds conformed origin date, target date, and target hour keys plus the
prediction-artifact and final-evaluation-snapshot SHA-256 values. Its target UTC
timestamp must exist in `analytics.fact_electricity_hourly`.

### `reporting.forecast_performance_hourly`

Grain: one final 2025 forecast origin and horizon step. Expected rows: 8,760.

The view exposes actual load, learned-model prediction and errors, both
seasonal-naive predictions, and target calendar/hour fields for Power BI.

### `reporting.forecast_performance_summary`

Grain: one forecast series and overall or horizon scope. Expected rows: 75.

It supplies learned model, daily seasonal naive, and weekly seasonal naive at
one overall plus 24 horizon scopes. MAE, RMSE, MAPE, observations, and MAE
improvement relative to the weekly baseline are computed from the fact. The
overall scope uses horizon key `0`; horizon scopes use `1` through `24`.

## Idempotence and refresh order

The forecast loader is a deterministic full replacement. Running it twice
must produce identical counts and checks. The canonical loader deliberately
clears dependent forecast rows before refreshing the energy facts, so the safe
full refresh order is:

```powershell
python -m gridsight.database.load_data
python -m gridsight.database.load_forecast_mart
```

The second command also creates all six reporting views and runs the complete
reporting reconciliation. Step 7.3 will export the fixed checked samples from
these products.

## Verified Step 7.2 result

Two consecutive command-line loads produced identical artifact hashes, table
counts, and view counts. Each passed 21 transactional load reconciliations and
28 reporting reconciliations with zero failures. The live database contained
8,760 forecast staging rows, 8,760 analytical facts, 8,760 hourly reporting
rows, and 75 summary rows.

The regenerated eight-product contract has SHA-256
`2b6e765eb106a706ae87b1e6c22d502b8bc18e3d995bf429a4d5889051532f95`.
All 77 fast tests passed with six live tests deselected; all six PostgreSQL
integration tests then passed with 77 fast tests deselected. Ruff and
`git diff --check` passed.
