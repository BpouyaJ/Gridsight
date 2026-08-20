# Seasonal-naive baseline evaluation

## Purpose

Step 6.2 establishes the minimum forecasting performance that learned models
must beat. It evaluates two transparent load-only baselines under the frozen
Step 6.1 origin, horizon, split, and information-cutoff contract.

Run the evaluation from the project root:

```powershell
python -m gridsight.forecasting.build_baselines
```

The command verifies the hashes of `reports/forecast_contract.json` and the
ignored `data/processed/forecast_index.csv` before calculating anything. It
writes aggregate evidence to `reports/baseline_snapshot.json`; row-level
predictions are deliberately not committed.

## Baselines

| Baseline | Prediction for one target hour | Lag |
|---|---|---:|
| Daily seasonal naive | Load observed at the declared target timestamp minus 24 real hours | 24 hours |
| Weekly seasonal naive | Load observed at the declared target timestamp minus 168 real hours | 168 hours |

Both values are available at issuance time. For horizon 24, the daily source
interval is the final hour ending at the forecast origin. All other source
intervals end earlier.

The lags use consecutive UTC observations rather than local clock labels. This
preserves an exact one-row lookup across the 23-hour spring and 25-hour autumn
daylight-saving transitions.

## Evaluation boundary

Only these rows are scored:

| Split | Role | Origins | Forecast rows |
|---|---|---:|---:|
| Train | Diagnostic baseline behavior | 723 | 17,352 |
| Validation | Honest baseline comparison and later model selection | 366 | 8,784 |
| Test | Excluded until the modeling design is frozen | 0 scored | 0 scored |

The implementation rejects any result containing a test row. It also rejects
changed input hashes, incomplete 24-step origins, invalid lag timestamps,
source data that extends beyond the forecast origin, or non-positive/non-finite
MW values.

## Metrics and reporting grain

Each baseline is evaluated with MAE, RMSE, and MAPE:

- overall for each included split;
- separately for every horizon step from 1 through 24.

MAE in MW remains the primary comparison metric. The tracked report also names
the stronger validation baseline and expresses the weekly baseline's MAE
improvement over the daily baseline. A negative value means weekly seasonal
naive performs worse.

## Verified results

| Split | Baseline | MAE (MW) | RMSE (MW) | MAPE |
|---|---|---:|---:|---:|
| Train | Daily seasonal naive | 3,950.618 | 5,979.072 | 7.513% |
| Train | Weekly seasonal naive | 2,368.310 | 3,811.770 | 4.579% |
| Validation | Daily seasonal naive | 3,945.112 | 5,898.040 | 7.614% |
| Validation | Weekly seasonal naive | 2,657.167 | 4,101.975 | 5.143% |

Weekly seasonal naive is the stronger validation baseline, reducing MAE by
32.647% relative to daily seasonal naive. Its validation MAE ranges from
2,117.011 MW at horizon 3 to 3,282.861 MW at horizon 15; all horizon metrics
use 366 observations. These results describe the approved 2024 validation
period and are not estimates of final 2025 test performance.

The artifact was reproduced byte-for-byte with SHA-256
`311513a0405761aa6a30db6a956b53c29b3cc38dfd03dc4e74efa62902a4b717`.
No test forecast row was scored.

## Interpretation limit

These baselines do not learn parameters and do not prove production forecast
quality. They are reproducible reference points for the later Ridge and
histogram gradient-boosting models. Model improvement will be credible only if
it uses the same origins, targets, metrics, and untouched-test boundary.
