# Load-forecasting protocol

## Purpose

Phase 6 predicts one target only: Germany-wide average hourly grid load for the
next 24 real hourly intervals. Step 6.1 freezes the forecast schedule,
information cutoff, chronological splits, baseline-source timestamps, and
evaluation metrics before any model is trained.

Build and verify the contract from the Phase 3 validated consumption dataset:

```powershell
python -m gridsight.forecasting.build_contract
```

The command writes an ignored row-level index to
`data/processed/forecast_index.csv` and a small tracked summary to
`reports/forecast_contract.json`. Both artifacts are deterministic for
unchanged input data and code.

## Forecast task

| Property | Contract |
|---|---|
| Target | `grid_load_mw` |
| Unit | MW, average power during one real hourly interval |
| Geography | Germany |
| Forecast origin | Europe/Berlin local midnight |
| Frequency | One forecast per local calendar date |
| Horizon | Next 24 consecutive real hourly intervals |
| Horizon step 1 | Interval beginning at the forecast origin |
| Horizon step 24 | Interval beginning 23 real hours after the origin |
| Information cutoff | Only observations with `interval_end_utc <= forecast_origin_utc` |
| Minimum history | 168 hours |

The latest allowed observed load starts one hour before the forecast origin and
ends exactly at it. The target interval beginning at the origin is not yet
observed and cannot be used as a feature.

## Daylight-saving behavior

Forecast origins are selected at local midnight for a consistent business
schedule, then represented canonically in UTC. Consecutive origins are 23 real
hours apart across the spring transition and 25 hours apart across the autumn
transition. Every issued forecast nevertheless contains exactly 24 unique,
continuous UTC target hours.

This means a 24-hour forecast is not always identical to one complete local
calendar day. The contract describes the next 24 observations, as approved in
the project scope, and preserves local timestamps and repeated-hour folds for
interpretation.

## Chronological splits

Splits are assigned by the forecast origin's Europe/Berlin calendar date.

| Split | Inclusive origin dates | Origins | Forecast rows |
|---|---|---:|---:|
| Train | 2022-01-08 through 2023-12-31 | 723 | 17,352 |
| Validation | 2024-01-01 through 2024-12-31 | 366 | 8,784 |
| Test | 2025-01-01 through 2025-12-31 | 365 | 8,760 |
| Total | — | 1,454 | 34,896 |

The first seven days of 2022 are history only so the earliest training origin
has a complete 168-hour weekly lag. Validation is used for feature and model
choices. The 2025 test set remains untouched until preprocessing, features,
models, and hyperparameters are frozen.

Random train/test splitting is prohibited because it would mix future system
conditions into model development and exaggerate expected forecasting
performance.

## Baseline-source timestamps

Each forecast-index row records, without yet calculating predictions:

- daily seasonal-naive source: target start minus 24 real hours;
- weekly seasonal-naive source: target start minus 168 real hours.

For all 24 horizons, each source interval must end at or before its forecast
origin. Horizon 24's daily source is the final completed hour immediately
before the origin, so it remains available.

## Feature-availability rules

Allowed essential inputs are:

- target-calendar attributes known in advance;
- historical grid-load observations complete by the forecast origin;
- lag and rolling features calculated only from that historical window;
- the declared horizon step.

Actual future load is always forbidden. Contemporaneous actual generation and
day-ahead-price observations are excluded from the essential load-only models
because this project has not established that they are available for every
target hour at issuance time. Any later weather extension requires its own
publication-time and forecast-availability contract.

All preprocessing is fit on training rows only. Validation transformations use
the already-fitted training objects. The test split cannot influence feature
selection, preprocessing, model choice, hyperparameters, or thresholds.

## Evaluation contract

Every origin/horizon pair is one forecast observation. Results will be reported
overall and by horizon step 1 through 24.

| Metric | Definition | Unit/use |
|---|---|---|
| MAE | Mean absolute error | MW; primary selection metric |
| RMSE | Square root of mean squared error | MW; emphasizes large errors |
| MAPE | Mean absolute percentage error times 100 | Percent; scale-relative context |
| Baseline improvement | `100 * (baseline MAE - model MAE) / baseline MAE` | Percent |

GridSight load is strictly positive, so MAPE has no zero-target division case.
MAE remains primary because it is directly interpretable in MW and less
dominated by isolated large errors than RMSE.

Learned models must be compared with both the daily and weekly seasonal-naive
baselines. A negative improvement means the model is worse than the declared
baseline and must be reported as such.

## Forecast-index columns

The generated index stores:

- UTC and local forecast origins plus the local origin date;
- chronological split and horizon step;
- explicit information cutoff;
- UTC/local target starts and the target local-fold flag;
- actual target load in MW for later scoring;
- exact daily and weekly baseline source timestamps.

The primary key is `(forecast_origin_utc, horizon_step)`. The row-level index is
generated and ignored because it contains the full target series. The tracked
JSON summary contains only protocol metadata, counts, paths, and hashes.

## Step boundary

Step 6.1 does not calculate baseline predictions, create forecasting features,
fit learned models, or evaluate the 2025 test set. Step 6.2 will implement and
compare the two seasonal-naive baselines on training and validation data under
this frozen contract.
