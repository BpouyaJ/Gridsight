# Final forecast evaluation

## Purpose

Step 6.5 produces GridSight's single unbiased estimate of next-24-hour load
forecast performance. It accepts the model selected in Step 6.4 without any
new feature, candidate, hyperparameter, or threshold choice.

Run the final workflow from the project root:

```powershell
python -m gridsight.forecasting.evaluate_final
```

This command intentionally opens the 2025 targets. Do not use its results to
change the model design; doing so would turn the test set into another
validation set and invalidate the final performance claim.

## Frozen-design gate

Before reading a test target, the command verifies:

- the Step 6.3 feature-contract and matrix paths and SHA-256 values;
- the Step 6.2 baseline report lineage;
- the Step 6.4 candidate list, validation ranking, selected parameters, and
  scikit-learn version;
- zero test labels and zero test scores in the model-validation report;
- exact row alignment between the redacted features and frozen forecast index;
- unchanged validated consumption and forecast-index lineage.

The selected model must remain
`hist_gradient_boosting_31_leaves`, with learning rate 0.05, 300 iterations,
31 maximum leaves, minimum leaf size 30, L2 regularization 1, disabled internal
early stopping, and random state 42.

## Final fit and test roles

| Role | Inclusive origin period | Rows | Permitted use |
|---|---|---:|---|
| Final development fit | 2022-01-08 through 2024-12-31 | 26,136 | Fit the already-frozen design |
| Final test | 2025-01-01 through 2025-12-31 | 8,760 | Score once; no later design changes |

Combining train and validation for this final fit is permitted only because
model selection is already complete and frozen. No test target is passed to
the estimator's `fit` method. The workflow does not save or commit a model
binary.

## Outputs

The ignored `data/processed/final_forecast_predictions.csv` contains one row
per test origin and horizon step with:

- explicit origin, information cutoff, target timestamp, and horizon;
- actual grid load in MW;
- exact daily and weekly seasonal-naive source timestamps and predictions;
- the frozen learned-model prediction, signed error, and absolute error.

The tracked `reports/final_evaluation_snapshot.json` contains only aggregate
evidence: exact source hashes, final-fit ownership, overall and 24-horizon MAE,
RMSE, and MAPE for the model and both baselines, baseline improvements, and the
ignored prediction-file hash.

## Interpretation rule

MAE in MW remains the primary result. RMSE describes sensitivity to larger
misses, and MAPE provides scale-relative context. Improvement is reported
against both declared baselines. The validation-to-test MAE change is reported
as generalization context, not as permission to tune again.

## Final 2025 results

| Forecast | MAE (MW) | RMSE (MW) | MAPE |
|---|---:|---:|---:|
| Frozen 31-leaf histogram model | 1,398.259 | 2,011.223 | 2.652% |
| Daily seasonal naive | 3,920.524 | 5,816.638 | 7.519% |
| Weekly seasonal naive | 2,615.589 | 3,945.010 | 4.987% |

The frozen learned model improves MAE by 64.335% over the daily baseline and
46.541% over the stronger weekly baseline. Its test MAE is 4.379% lower than
its 1,462.293 MW validation MAE, so the final year does not expose the feared
generalization deterioration.

Every horizon contains 365 observations. Horizon 2 has the lowest model MAE at
743.021 MW, while horizon 14 has the highest at 1,950.843 MW. This horizon
variation is reported as diagnostic evidence only; the test profile cannot be
used for another design choice.

The ignored 8,760-row prediction file independently reconciles to the tracked
aggregate metrics and uses only `hist_gradient_boosting_31_leaves`. Artifact
SHA-256 values are:

- `data/processed/final_forecast_predictions.csv`:
  `e6e1a5c64372942142993e81f8f3f748b609dda67a15a66af5e48260686b38e6`;
- `reports/final_evaluation_snapshot.json`:
  `d65eea94653b1367ec169de60d4ff91fe2a956fa317040746c5a0a3c56fd3065`.

Verification completed with all 69 fast tests passing, including five final
evaluation tests covering frozen lineage, target isolation, refit ownership,
leakage rejection, reconciliation, and deterministic artifacts. Six live
database tests were deliberately deselected because Step 6.5 is file-based.
Ruff and `git diff --check` also passed.
