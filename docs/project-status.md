# Project status

Last updated: 2026-08-20

## Current phase

Phase 6 - Forecasting

Current step: 6.5 - Final refit and one-time 2025 test evaluation

Status: completed

## Completed

- Compared Codex, ChatGPT Work, reasoning settings, agents, skills, and plugins.
- Approved Codex as the primary development environment.
- Researched official and credible energy-data options.
- Selected Bundesnetzagentur SMARD as the essential source.
- Selected Germany/DE-LU, hourly grain, and 2022-2025 coverage.
- Selected Germany-wide load as the only essential forecasting target.
- Approved the architecture, analytical model, Power BI scope, Excel scope, and development phases.
- Created the Git repository and approved folder structure.
- Persisted the roadmap, decision log, source contract, data policy, and agent workflow.
- Verified local Markdown links, ignored-data rules, and the absence of implementation code.
- Created a Python 3.13 virtual environment under `.venv`.
- Added `pyproject.toml` with runtime, analysis, and development dependency groups.
- Installed GridSight as an editable package with its approved analytics and database dependencies.
- Added Windows development-environment instructions.
- Passed the initial package smoke test with pytest.
- Passed the Ruff code-quality check.
- Added a healthy PostgreSQL 17.10 service using Docker Compose.
- Added an ignored local `.env` credential workflow and persistent database volume.
- Added validated database settings and a SQLAlchemy/Psycopg connection factory.
- Passed the Python-to-PostgreSQL connection command.
- Passed the marked PostgreSQL integration test while keeping it out of the default fast test suite.
- Defined the six approved SMARD exports with exact filters, periods, geographies, and normalized filenames.
- Added the tracked source-manifest schema before downloading data.
- Added an immutable, SHA-256-based raw-snapshot registration command.
- Verified idempotent registration and protection against different-content overwrites.
- Passed all four fast tests and the Ruff code-quality check.
- Registered the 2022-2023 Germany actual-consumption snapshot with matching raw and manifest SHA-256 values.
- Confirmed 17,520 hourly rows, six columns, UTF-8 BOM encoding, semicolon delimiter, and MWh measures.
- Selected `grid load [MWh] Calculated resolutions` as the primary load measure.
- Confirmed no missing or non-numeric measure markers in the initial snapshot.
- Documented 23-hour spring and 25-hour autumn daylight-saving behavior and repeated local timestamp text.
- Corrected the export configuration to distinguish expected output series from selectable SMARD filters.
- Re-ran all four fast tests and Ruff successfully after profiling updates.
- Registered the 2024-2025 Germany actual-consumption snapshot with matching raw and manifest SHA-256 values.
- Confirmed its six-column schema, encoding, delimiter, and numeric format match the 2022-2023 snapshot.
- Confirmed 17,544 rows, with the expected extra leap-day hours from 2024.
- Confirmed the same spring/fall daylight-saving behavior and no missing or non-numeric measure markers.
- Verified that both actual-consumption snapshots can use one ingestion schema.
- Re-ran all four fast tests and Ruff successfully after the compatibility update.
- Registered the 2022-2023 Germany actual-generation snapshot with matching raw and manifest SHA-256 values.
- Confirmed 17,520 rows, 14 columns, and 12 explicit generation-technology measures.
- Confirmed the generation file shares the consumption files' encoding, delimiter, numeric format, timestamp format, and DST behavior.
- Confirmed no missing or non-numeric generation measure markers in the snapshot.
- Registered the 2024-2025 Germany actual-generation snapshot with matching raw and manifest SHA-256 values.
- Confirmed its 14-column schema, encoding, delimiter, units, timestamp representation, and DST behavior match the 2022-2023 generation snapshot.
- Confirmed 17,544 rows, including the expected 24 leap-day hours from 2024.
- Identified 16,836 `-` source markers in the Nuclear measure beginning at 2024-01-30 12:00, after 708 numeric zero values.
- Defined `-` as missing/unavailable during parsing rather than silently treating it as measured zero.
- Verified that both actual-generation snapshots can use one structural ingestion schema with a column-aware missing-marker rule.
- Registered the 2022-2023 DE/LU day-ahead-price snapshot with matching raw and manifest SHA-256 values.
- Selected `Germany/Luxembourg [€/MWh] Calculated resolutions` from the 19-column multi-market export as the exact GridSight price measure.
- Confirmed all 17,520 target-price rows are numeric, with 370 negative values, 30 zeroes, and no source markers.
- Recorded the observed target-price range from -500.00 to 871.00 EUR/MWh and classified negative wholesale prices as valid observations.
- Confirmed the price snapshot shares the other sources' encoding, delimiter, local timestamp representation, and DST behavior.
- Registered the 2024-2025 DE/LU day-ahead-price snapshot with matching raw and manifest SHA-256 values.
- Confirmed its 19-column schema exactly matches the 2022-2023 price snapshot and contains the same Germany/Luxembourg target.
- Confirmed all 17,544 later target-price rows are numeric, with 1,030 negative values, 144 zeroes, and no source markers.
- Recorded the later target-price range from -250.32 to 936.28 EUR/MWh.
- Confirmed the expected leap-day and daylight-saving row behavior.
- Completed registration and documented read-only profiling for all six approved SMARD snapshots.
- Added a reusable Pandas-based profiler for every registered raw snapshot.
- Added automated checks for manifest hashes, expected hourly row counts, exact targets, category schemas, source markers, and repeated local hours.
- Added a read-only command that reproduced all documented source-profile results and completed with `Source profiling: OK`.
- Added the reproducible `01_smard_source_profile.ipynb` notebook as a thin presentation layer over tested package code.
- Added focused tests for leap-year/DST interval counts and numeric-versus-marker profiling.
- Passed all six fast tests and Ruff after completing the Phase 2 profiling artifacts.
- Completed the Phase 2 gate with all required acquisition, lineage, profiling, notebook, documentation, and verification deliverables.
- Defined the canonical UTC and Europe/Berlin time columns while preserving raw source labels.
- Implemented locale-independent SMARD timestamp parsing and ordered autumn-hour disambiguation.
- Derived canonical ends from UTC starts plus one hour to handle both DST boundaries safely.
- Added a read-only six-snapshot timestamp-normalization check and focused spring, autumn, and real-gap tests.
- Verified all six snapshots become continuous unique UTC hours with CET/CEST offsets and two second-fold rows per two-year file.
- Passed all nine fast tests and Ruff after completing Step 3.1.
- Mapped all four actual-consumption measures to explicit canonical MWh columns and derived the primary `grid_load_mw` measure.
- Implemented strict numeric parsing while preserving valid negative residual load.
- Added row-level manifest lineage and continuous combination of both consumption periods.
- Added a reproducible atomic build for the ignored clean consumption CSV.
- Verified 35,064 continuous rows, 24 columns, complete UTC coverage, and processed SHA-256 `4a0107f087fdd5d87e584c913c6e73187f6e2c81057053964250cf3f1f9316a5`.
- Passed all 15 fast tests, Ruff, and the processed-file Git-ignore check after completing Step 3.2.
- Defined 12 stable generation technology IDs with renewable, conventional, or storage classification.
- Implemented one interval/technology row with numeric MWh/MW and preserved source value text.
- Represented only the Nuclear `-` marker as unavailable with missing numeric values.
- Extracted shared source-lineage handling for consumption, generation, and later category transformations.
- Verified 420,768 rows, 35,064 intervals, 12 technologies, 403,932 numeric rows, and 16,836 unavailable Nuclear rows.
- Recorded processed generation SHA-256 `9106f24f0e793a2807d4116edb1454490b5f9fc9a340c75c36e450634a3b328f`.
- Passed all 20 fast tests, Ruff, and the generation-output Git-ignore check after completing Step 3.3.
- Required the exact profiled 19-column market-export schema and selected only the Germany/Luxembourg series.
- Implemented strict finite numeric parsing while retaining negative and zero prices.
- Added explicit market-area, currency, unit, source-text, and shared lineage columns.
- Verified 35,064 continuous rows, 25 columns, 1,400 negative prices, 174 zero prices, and a -500.00 to 936.28 EUR/MWh range.
- Recorded processed price SHA-256 `a9a66c7f69900289c944ec72bcc1a62e26fbb3c37839e3ad34f7f405a622e53e`.
- Passed all 25 fast tests, Ruff, and the price-output Git-ignore check after completing Step 3.4.
- Added stable structured checks for clean schemas, counts, keys, measures,
  units, generation availability, lineage, and cross-dataset UTC alignment.
- Added deterministic validation-issue CSV and machine-readable JSON run-summary
  writers.
- Added one command that validates before publishing and preserves the last
  known-good canonical outputs on validation failure.
- Added focused passing, failing, actionable-issue, and artifact-reproducibility
  tests for the Phase 3 gate.
- Passed all 29 consolidated clean-data checks with zero validation issues.
- Reproduced the verified consumption, generation, and price output hashes in
  one clean-data run.
- Recorded validation-issues SHA-256
  `f71d51df4b07a9d80be883432a59eabec1c957b0c8627e499de5c853d06eaecf`.
- Recorded validation-summary SHA-256
  `5fc1af559d4ebb46712a86d7cff3f5780a0af2c24ce480c0e7016767176de766`.
- Passed all 29 fast tests with one PostgreSQL integration test deselected.
- Passed Ruff after applying its deterministic import-order correction.
- Completed the Phase 3 gate with canonical clean datasets, structured
  failures, reproducible summaries, tests, and documentation.
- Defined `staging`, `analytics`, and `reporting` PostgreSQL schemas through
  ordered idempotent SQL files.
- Mirrored all 24 consumption, 29 generation, and 25 price canonical columns in
  three constrained staging tables.
- Defined conformed date, hour, and 12-member generation-technology dimensions.
- Defined separate hourly electricity and interval/technology generation fact
  contracts with explicit grains, units, keys, lineage, and foreign keys.
- Added database constraints for UTC duration, domains, arithmetic identities,
  SHA-256 lineage, and reported-versus-unavailable semantics.
- Added a transactional DDL runner and live database contract inspector.
- Added fast SQL-contract tests and an idempotence/live-contract integration
  test.
- Applied all 14 DDL statements successfully and matched the live database to
  all eight declared table contracts.
- Verified three staging, five analytics, and zero reporting tables in their
  expected schemas.
- Proved the schema application is idempotent by applying it twice inside the
  live PostgreSQL integration test.
- Passed all 33 fast tests with two integration tests deselected.
- Passed both live PostgreSQL integration tests with 33 fast tests deselected.
- Passed Ruff after completing the Step 4.1 implementation.
- Added a pre-load trust gate for the Phase 3 summary, issue file, ordered CSV
  headers, expected counts, and exact output hashes.
- Added client-side PostgreSQL `COPY` streaming for all three canonical staging
  datasets.
- Added SQL transformations for the local date/hour/technology dimensions and
  both analytical fact grains.
- Added an atomic full-refresh transaction that rolls back truncation, copies,
  transformations, and reconciliation together on failure.
- Added 19 post-load checks covering every table count, price distribution,
  generation availability, UTC spines, measures, and lineage.
- Added fast artifact/SQL tests and a live integration test that performs two
  complete reconciled loads to prove idempotence.
- Completed two consecutive command-line database loads with identical counts
  and 19 passed reconciliation checks each.
- Loaded 35,064 consumption, 420,768 generation, and 35,064 price staging rows.
- Populated 1,461 dates, 24 hours, 12 technologies, 35,064 electricity facts,
  and 420,768 generation facts.
- Passed all 37 fast tests with three live tests deselected.
- Passed all three live PostgreSQL tests with 37 fast tests deselected,
  including two additional complete idempotent loads.
- Passed Ruff after completing the Step 4.2 implementation.
- Added an hourly energy view combining calendar, load, price, and classified
  generation at one canonical UTC-hour grain.
- Added an hourly generation-by-technology view retaining all 12 members,
  availability status, and source lineage.
- Added DST-aware daily and hourly-weighted monthly reporting views with
  explicit MWh, MW, EUR/MWh, count, peak, and percentage semantics.
- Added exact ordered view contracts and an idempotent transactional
  create-or-replace command.
- Added 19 live reporting reconciliations for row counts, unique grains,
  technology completeness, DST days, and fact-to-view measures.
- Added fast reporting-contract tests and a self-contained PostgreSQL
  integration test for repeated view application and reconciliation.
- Applied all four reporting views twice with identical row counts and 19
  passed reconciliations each time.
- Verified 35,064 hourly energy, 420,768 hourly technology, 1,461 daily, and 48
  monthly reporting rows.
- Passed all 40 fast tests with four live tests deselected.
- Passed all four live PostgreSQL tests with 40 fast tests deselected.
- Passed Ruff after removing the detected unused reporting-contract import.
- Completed the Phase 4 gate with schemas, constrained staging, conformed
  dimensions, facts, idempotent loading, reconciliation, and reporting views.
- Defined three read-only analytical query grains: one full-period headline
  row, four Europe/Berlin annual rows, and 12 technology-mix rows.
- Defined explicit TWh, GW, EUR/MWh, percentage, count, and availability
  semantics for portfolio KPIs.
- Added an exact Python query contract that rejects column, ordering, grain,
  year, hourly-coverage, technology-order, and availability mismatches.
- Added a deterministic atomic `reports/kpi_snapshot.json` builder with source,
  unit, period, and SQL-contract metadata.
- Reproduced the KPI snapshot twice with SHA-256
  `fa03ee1af919027634aeb45a524c713274bd9effcac9955052d3be449c8395fc`.
- Verified one headline row, four annual rows, 12 technology rows, and 35,064
  observed hours.
- Recorded 1,871.998 TWh total grid load, 54.61% renewable share of reported
  generation, and 124.58 EUR/MWh average day-ahead price for the complete
  approved period.
- Reconciled 1,400 negative-price hours and 16,836 unavailable generation
  values across headline, annual, and technology grains.
- Passed all 43 fast tests with five live tests deselected.
- Passed all five live PostgreSQL tests with 43 fast tests deselected.
- Passed Ruff and `git diff --check` after completing Step 5.1.
- Defined monthly, local-hour/day-type, and daily EDA query contracts covering
  48 months, 48 load-shape groups, and 1,461 days.
- Reconciled every EDA grain to 35,064 hours and both aggregate availability
  grains to 16,836 unavailable generation values.
- Added deterministic daily correlations, four load-shape extrema, and six
  explicit unusual-day ranking rules.
- Changed daily load-extreme ranking from GWh to average GW after visual review
  exposed the unfair duration effect on 23/25-hour DST dates.
- Added four deterministic, visually reviewed PNG figures without dual axes or
  causal claims.
- Added the thin `02_energy_market_eda.ipynb` presentation notebook over tested
  package logic.
- Reproduced the EDA JSON and all four figure hashes across two consecutive
  builds.
- Recorded the -0.631 all-period daily renewable-share/price association and
  separate yearly coefficients from -0.637 to -0.882.
- Recorded the 2022-2025 renewable-share increase from 46.66% to 58.86%, the
  price decrease from 235.45 to 89.32 EUR/MWh, and the increase from 69 to 573
  negative-price hours.
- Documented seasonal load movement, weekday/weekend hourly shapes, six
  rule-selected unusual days, missing-generation context, and causal limits.
- Passed all 47 fast tests with six live tests deselected.
- Passed all six live PostgreSQL tests with 47 fast tests deselected.
- Passed Ruff, `git diff --check`, artifact determinism, and visual review.
- Completed the Phase 5 gate with KPI definitions, SQL queries, focused EDA,
  reproducible artifacts, documented findings, and limitations.
- Defined one forecast at each Europe/Berlin local midnight for the next 24
  consecutive real hourly intervals.
- Defined the information cutoff as observations whose intervals end at or
  before the forecast origin.
- Reserved the first seven 2022 dates for weekly history, training origins for
  the remainder of 2022-2023, validation origins for 2024, and untouched test
  origins for 2025.
- Added a deterministic 1,454-origin, 34,896-row forecast-index builder with
  UTC/local timestamps, folds, horizon steps, target MW, and daily/weekly
  baseline-source timestamps.
- Added strict checks for hourly continuity, split counts, 24-step completeness,
  DST origin spacing, positive targets, and baseline availability.
- Added explicit MAE, RMSE, MAPE, and baseline-improvement implementations.
- Added fast tests for chronology, both DST transitions, leakage rejection,
  metrics, and deterministic index writing.
- Generated and reviewed a deterministic 1,454-origin, 34,896-row forecast
  index with SHA-256
  `6089b1d7c2cd3298cfa3d24526f98cc763b1c95947ce2e9e84ff06dc42bbecc4`.
- Generated the tracked forecast-contract summary with SHA-256
  `3a4a2da987089258b3ba5e7d64bc67f0abd62a0a4c5e3fdd31c03df75a060f88`.
- Verified 723 training, 366 validation, and 365 untouched test origins with
  exactly 24 rows per origin and explicit UTC boundaries.
- Passed all 51 fast tests with six live tests deselected, including the four
  new forecasting-contract tests.
- Passed Ruff and `git diff --check` after completing Step 6.1.
- Added hash-gated loading of the frozen Step 6.1 contract and forecast index.
- Added exact 24-hour and 168-hour source lookups against validated canonical
  load observations.
- Limited baseline evaluation to 17,352 training and 8,784 validation rows,
  with an explicit rejection rule for any scored test row.
- Added MAE, RMSE, and MAPE reporting overall and by all 24 horizon steps.
- Added a deterministic aggregate baseline snapshot and validation comparison.
- Added fast tests for source lookup, test exclusion, leakage rejection,
  frozen-input hashes, horizon coverage, and deterministic output.
- Evaluated 17,352 training and 8,784 validation rows while scoring zero test
  rows.
- Recorded validation MAE of 3,945.112 MW for daily seasonal naive and
  2,657.167 MW for weekly seasonal naive.
- Selected weekly seasonal naive as the stronger validation benchmark, with a
  32.647% MAE improvement over daily seasonal naive.
- Reproduced the aggregate baseline artifact twice with SHA-256
  `311513a0405761aa6a30db6a956b53c29b3cc38dfd03dc4e74efa62902a4b717`.
- Passed all 55 fast tests with six live tests deselected, including all four
  new baseline tests.
- Passed Ruff and `git diff --check` after completing Step 6.2.
- Added a deterministic 34,896-row model-matrix builder at the frozen
  origin/horizon grain.
- Added 27 numeric calendar, cyclic, lag, rolling, and recent-change features.
- Derived calendar features from UTC-to-Europe/Berlin conversion with explicit
  repeated-hour fold and UTC offset.
- Limited every load feature to observations ending at or before its origin.
- Redacted all 8,760 test labels while retaining available test-time inputs.
- Added strict schema, split, domain, rolling-consistency, and availability
  validation.
- Added deterministic ignored CSV and tracked JSON contract writers.
- Added fast tests for exact history values, DST fields, future-target
  invariance, test-label redaction, leakage rejection, and artifact bytes.
- Verified 34,896 rows, 35 total columns, 27 complete model features, and
  26,136 materialized development labels.
- Verified that all 8,760 test targets remain redacted and no test evaluation
  was performed.
- Verified four second-fold target rows at local hour 02 with the expected
  standard-time UTC offset.
- Reproduced the ignored feature matrix with SHA-256
  `eda6e21687fe3cd09681de14370749a03cbb974d81972661196c86b1a4d52ef8`.
- Reproduced the tracked feature contract with SHA-256
  `daac05d8a00a3db3eedb29671d4543e497607aac7e8431898a413effb4ad65ae`.
- Passed all 59 fast tests with six live tests deselected, including all four
  new feature-engineering tests.
- Passed Ruff and `git diff --check` after completing Step 6.3.
- Added hash-gated loading for the frozen feature matrix, feature contract, and
  baseline comparison.
- Predeclared three scaled Ridge candidates and two deterministic histogram
  gradient-boosting candidates.
- Fit all preprocessing and estimators on training rows only, with histogram
  internal early stopping disabled.
- Added train and validation MAE, RMSE, and MAPE overall and by 24 horizons.
- Added stable lowest-validation-MAE selection and weekly-baseline improvement.
- Added a deterministic aggregate report with exact source hashes, parameters,
  scikit-learn version, and a zero-test-result guard.
- Added tests for estimator configuration, synthetic fitting, stable selection,
  deterministic reporting, changed bytes, and lineage mismatch.
- Fit all five candidates on 17,352 training rows and evaluated them on 8,784
  validation rows while scoring zero test rows.
- Selected the 31-leaf histogram gradient-boosting candidate with validation
  MAE 1,462.293 MW, RMSE 2,350.998 MW, and MAPE 2.836%.
- Improved validation MAE by 44.968% over the frozen 2,657.167 MW weekly
  seasonal-naive benchmark.
- Recorded the selected model's 644.460 MW training MAE and documented the
  material train/validation generalization gap before final testing.
- Verified 366 observations for every selected-model validation horizon, from
  767.573 MW MAE at step 1 to 1,991.471 MW at step 15.
- Reproduced the scikit-learn 1.9.0 validation report with SHA-256
  `b6c2b96482e238249300612ee6750b278f63aabb970f56e4f2c150ec67d013f7`.
- Passed all 64 fast tests with six live tests deselected, including all five
  new model-validation tests.
- Passed Ruff and `git diff --check` after completing Step 6.4.
- Added a hash-gated loader for the frozen Step 6.4 selection and runtime.
- Added exact target alignment before the deliberately isolated test unlock.
- Added final train-plus-validation refitting without passing test labels to
  `fit`.
- Added ignored row-level model and seasonal-baseline predictions with strict
  grain, time, value, and error reconciliation.
- Added deterministic aggregate final-evaluation reporting and fast tests.
- Refit the frozen 31-leaf histogram model on 26,136 train-plus-validation
  rows and evaluated all 8,760 rows from 365 test origins.
- Recorded final test MAE 1,398.259 MW, RMSE 2,011.223 MW, and MAPE 2.652%.
- Improved final MAE by 64.335% over daily seasonal naive and 46.541% over
  weekly seasonal naive.
- Reconciled the ignored row-level predictions independently to the tracked
  aggregate report and confirmed no further selection is allowed.
- Recorded prediction SHA-256
  `e6e1a5c64372942142993e81f8f3f748b609dda67a15a66af5e48260686b38e6`
  and report SHA-256
  `d65eea94653b1367ec169de60d4ff91fe2a956fa317040746c5a0a3c56fd3065`.
- Passed all 69 fast tests with six live tests deselected, including all five
  new final-evaluation tests.
- Passed Ruff and `git diff --check` after completing Step 6.5 and Phase 6.

## In progress

None. Step 6.5 and Phase 6 are ready for their Git checkpoint.

## Not started

- Power BI
- Excel/Power Query

## Next bounded step

After the Phase 6 Git checkpoint, start Step 7.1 by defining stable
forecast-performance reporting marts and checked sample-extract contracts for
Power BI and Excel.

## Current blockers

None.
