# Leakage-safe forecasting features

## Purpose

Step 6.3 creates the reusable model matrix for the 24-hour Germany grid-load
forecast. Every declared feature must be known at the Europe/Berlin midnight
forecast origin. The implementation contains no future generation, price,
target load, fitted preprocessing, or model output.

Build the matrix and its contract from the project root:

```powershell
python -m gridsight.forecasting.build_features
```

The command hash-gates the Step 6.1 forecast contract and index, reads the
validated canonical load source, writes the row-level matrix to ignored
`data/processed/forecast_features.csv`, and writes its small tracked summary to
`reports/feature_contract.json`.

## Grain and target boundary

The primary key remains `(forecast_origin_utc, horizon_step)`: 1,454 origins
times 24 real hourly steps equals 34,896 rows. Training and validation target
labels are included for later model fitting and selection. All 8,760 test
labels are blank in the feature matrix and the contract requires zero
materialized test targets.

Creating calendar and historical inputs for 2025 is allowed because those
values are available at issuance time. Reading or scoring the corresponding
2025 outcomes remains prohibited until model design is frozen.

## Feature families

The 27 numeric model features are:

- forecast horizon step;
- target local hour, weekday, weekend flag, month, day of year, repeated-hour
  fold, and UTC offset;
- sine/cosine encodings for local hour, weekday, and annual position;
- latest completed hourly load at the origin;
- exact 24-hour and 168-hour target-relative load lags;
- mean, population standard deviation, minimum, and maximum for the 24 and 168
  completed hours before the origin;
- latest one-hour and 24-hour observed load changes.

Calendar values are known in advance. Historical-load values use only source
intervals ending at or before the forecast origin. Rolling features end at the
latest completed interval and remain constant across the 24 rows belonging to
one origin. The exact daily and weekly lags vary by horizon, matching the
seasonal-naive definitions.

## DST handling

Target calendar fields are derived by converting canonical UTC timestamps to
Europe/Berlin. The feature matrix retains the repeated-hour fold and the UTC
offset. Lag and rolling windows use consecutive real UTC hours, so spring and
autumn clock changes cannot duplicate or skip history observations.

## Validation rules

The build rejects:

- changed source/index hashes or unexpected columns and row counts;
- duplicated origin/horizon keys or incomplete split counts;
- a latest observation that does not end exactly at the forecast origin;
- missing or non-finite model features and invalid calendar domains;
- inconsistent rolling minimum/mean/maximum relationships;
- missing development labels or any materialized test label.

A target-invariance test changes all 24 future load outcomes for one origin and
proves that the same origin's 27 model features remain identical.

## Verified artifacts

The real-data build produced 34,896 rows, 35 total columns, and 27 declared
model features. All model features are complete. The only missing cells are
the 8,760 deliberately redacted test targets; all 26,136 training and
validation targets are present.

The DST audit found four second-fold target rows. Every one is local hour 02,
fold 1, with a +1-hour UTC offset. Both +1 and +2 UTC offsets occur in the full
matrix as expected.

The artifacts reproduced with these SHA-256 values:

- ignored `data/processed/forecast_features.csv`:
  `eda6e21687fe3cd09681de14370749a03cbb974d81972661196c86b1a4d52ef8`;
- tracked `reports/feature_contract.json`:
  `daac05d8a00a3db3eedb29671d4543e497607aac7e8431898a413effb4ad65ae`.

## Step boundary

Step 6.3 does not fit preprocessing, train a model, select hyperparameters, or
evaluate the test split. Step 6.4 applies the process documented in
[Chronological model validation](model-validation.md): Ridge and histogram
gradient-boosting candidates fit training rows and compete on validation rows
against the weekly seasonal-naive benchmark. The frozen winner proceeds to the
single [final forecast evaluation](final-forecast-evaluation.md).
