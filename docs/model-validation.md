# Chronological model validation

## Purpose

Step 6.4 trains a deliberately small set of learned load-forecast candidates
and selects one using the frozen 2024 validation split. It does not read or
score any 2025 target. The selected learned candidate must also beat the weekly
seasonal-naive validation MAE of 2,657.167 MW to justify final testing.

Run training and validation from the project root:

```powershell
python -m gridsight.forecasting.train_models
```

The command verifies the Step 6.3 feature matrix and contract hashes, verifies
the Step 6.2 baseline lineage and zero-test-row guard, trains fixed candidates,
and writes aggregate evidence to `reports/model_validation_snapshot.json`.
No row-level predictions or fitted model binaries are committed.

## Data boundary

| Split | Use | Forecast rows |
|---|---|---:|
| Train, 2022-2023 | Fit scalers and estimators | 17,352 |
| Validation, 2024 | Compare candidates and select one | 8,784 |
| Test, 2025 | Feature rows only; targets remain redacted | 0 scored |

Ridge scaling is fit on training rows only. Histogram gradient boosting uses
training rows only and disables its automatic internal early-stopping split;
this avoids an unnecessary random holdout inside the chronological training
period. Validation labels are never passed to `fit`.

## Fixed candidates

The bounded candidate list is declared before viewing validation results:

- Ridge with standardized features and alpha 1, 10, or 100;
- histogram gradient boosting with 15 or 31 maximum leaves;
- both histogram candidates use learning rate 0.05, 300 iterations,
  L2 regularization 1, fixed random state 42, and no early stopping.

The histogram variants use minimum leaf sizes of 40 and 30 respectively. This
small comparison covers a transparent linear benchmark and two controlled
nonlinear capacities without turning one validation year into a broad
hyperparameter search.

## Selection and reporting

Each candidate reports train and validation MAE, RMSE, and MAPE overall and for
horizons 1 through 24. Lowest overall validation MAE wins; the candidate name
is the deterministic tie-break. The report then calculates improvement over
the frozen weekly seasonal-naive validation MAE.

Training metrics diagnose underfit or overfit but never select the model. A
candidate that fails to beat the weekly baseline remains honestly reported and
must not be presented as an improvement.

## Verified results

| Candidate | Train MAE (MW) | Validation MAE (MW) | Validation RMSE (MW) | Validation MAPE |
|---|---:|---:|---:|---:|
| Ridge alpha 1 | 1,781.282 | 1,973.747 | 2,718.039 | 3.852% |
| Ridge alpha 10 | 1,779.398 | 1,966.888 | 2,713.068 | 3.838% |
| Ridge alpha 100 | 1,792.840 | 1,955.578 | 2,713.774 | 3.817% |
| Histogram, 15 leaves | 856.763 | 1,532.772 | 2,432.344 | 2.982% |
| Histogram, 31 leaves | 644.460 | 1,462.293 | 2,350.998 | 2.836% |

The 31-leaf histogram model is selected. Its validation MAE is 44.968% lower
than the 2,657.167 MW weekly seasonal-naive benchmark. Its best validation
horizon is step 1 at 767.573 MW MAE; its worst is step 15 at 1,991.471 MW MAE.
All horizon values use 366 observations.

The selected model's 644.460 MW training MAE is substantially below its
1,462.293 MW validation MAE. This is evidence of a generalization gap, not a
reason to revisit the already-viewed validation set with a broader search. The
model remains selected under the predeclared rule, and the untouched 2025 test
is required to establish the final estimate.

The report records scikit-learn 1.9.0, zero test targets, zero test predictions,
and SHA-256
`b6c2b96482e238249300612ee6750b278f63aabb970f56e4f2c150ec67d013f7`.

## Reproducibility and test guard

The report records exact source paths and hashes, scikit-learn version,
candidate parameters, preprocessing ownership, random state, selection rule,
and zero scored test rows. Repeated runs with unchanged inputs and environment
must produce identical JSON bytes.

## Step boundary

Step 6.4 selected one learned design without publishing final performance or
saving a production model. Step 6.5 froze that design, refit it on training
plus validation data, deliberately unlocked the 2025 targets once, and
compared final test performance with both seasonal-naive baselines under the
[final forecast evaluation protocol](final-forecast-evaluation.md).
