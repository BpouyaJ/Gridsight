# GridSight roadmap

## Objective

Build a complete, interview-defensible portfolio project demonstrating energy analytics, data quality, PostgreSQL analytical modeling, forecasting fundamentals, Power BI, and Excel/Power Query.

## Final product

GridSight will analyze hourly German load and generation with DE/LU day-ahead prices for 2022-2025. It will forecast one target only: Germany-wide hourly grid load for the next 24 hours.

## Phase sequence

### Phase 0 - Scope and roadmap

Deliverables:

- Approved problem, boundaries, datasets, architecture, and phase order
- Essential versus optional feature list

Status: completed and persisted in this repository.

### Phase 1 - Foundation

Deliverables:

- Repository structure and project-control documents
- Reproducible Python environment
- PostgreSQL runtime and connection smoke test
- Initial automated test and quality commands

Skills: Python setup, Git, PostgreSQL, reproducibility, technical documentation.

### Phase 2 - Data acquisition and profiling

Deliverables:

- SMARD raw snapshots for 2022-2025
- Source manifest with filters, attribution, checksums, and download dates
- Reproducible ingestion command
- Source-profile notebook and documented observations

Skills: real-world energy data, Pandas, NumPy, lineage, source assessment.

Status: completed. All six snapshots are registered with immutable raw files,
tracked lineage, reproducible automated profiles, a source-profile notebook,
documented observations, and passing tests.

### Phase 3 - Validation and transformation

Deliverables:

- Energy-specific validation rules
- Validation-error output and run summary
- UTC-normalized hourly clean datasets
- Tested handling of duplicates, gaps, DST, units, categories, and impossible values

Skills: data quality, time-series cleaning, plausibility checks, Python testing.

Status: completed. Steps 3.1 through 3.4 established the canonical UTC time
contract and verified complete consumption, long-form generation, and DE/LU
price datasets. Step 3.5 completed the gate with 29 passing consolidated
checks, structured issues, reproducible run summaries, and a passing fast test
and lint suite.

### Phase 4 - PostgreSQL analytical model

Deliverables:

- `staging`, `analytics`, and `reporting` schemas
- Conformed dimensions and fact tables
- Idempotent load process
- Tested SQL reporting views

Skills: SQL, PostgreSQL, star modeling, analytical data foundations.

Status: completed. Steps 4.1 and 4.2 established the schemas, table contracts,
transactional data load, star population, and reconciliation. Step 4.3
completed four unit-aware, DST-safe reporting grains with exact contracts, 19
fact-to-view reconciliations, and passing fast, live, and lint suites.

### Phase 5 - Exploratory analysis and KPIs

Deliverables:

- Focused EDA notebook
- Documented KPI definitions and SQL queries
- Findings about load shapes, renewable patterns, prices, and unusual periods

Skills: energy analytics, trend analysis, business KPIs, analytical communication.

Status: completed. Step 5.1 established verified KPI definitions and query
grains. Step 5.2 completed reconciled monthly, load-shape, and daily analysis;
deterministic JSON and figure artifacts; a thin notebook; documented findings
and limitations; and passing fast, live, lint, and visual checks.

### Phase 6 - Forecasting

Deliverables:

- Daily and weekly seasonal-naive baselines
- Leakage-safe calendar, lag, and rolling features
- Ridge and histogram gradient-boosting models
- Chronological validation and untouched 2025 test evaluation
- MAE, RMSE, MAPE, and baseline-improvement reporting

Skills: NumPy, scikit-learn, feature engineering, time-series validation, model evaluation.

Status: completed. Step 6.1 established the local-midnight forecast schedule,
24-real-hour horizon, information cutoff, chronological train/validation/test
splits, baseline-source timestamps, and evaluation metrics. Step 6.2 is
complete with frozen daily and weekly seasonal-naive baselines, aggregate
overall/horizon metrics, and zero scored test rows. Step 6.3 completed a
deterministic calendar, lag, and rolling feature matrix with redacted test
targets. Step 6.4 completed training-only fitting of fixed Ridge and histogram
gradient-boosting candidates and validation-only selection of the 31-leaf
histogram model. Step 6.5 refit that frozen design on the completed development
period and opened the 2025 test once. The guarded run produced 1,398.259 MW
test MAE, a 46.541% improvement over the weekly baseline, reconciled aggregate
and row-level evidence, and passing forecasting, regression, and lint checks.

### Phase 7 - Reporting marts

Deliverables:

- Stable Power BI and Excel reporting views
- Refreshable checked-in sample extracts
- Reconciliation tests between Python, SQL, and reporting outputs

Skills: reliable BI foundations, reporting design, metric reconciliation.

Status: completed. Step 7.1 froze eight consumer-facing product contracts:
four verified energy SQL views, two forecast-performance views, and checked
data-quality and lineage extracts. Step 7.2 implements the hash-gated forecast
fact load and both SQL views. Step 7.3 now reproducibly publishes all eight
checked samples and the 3,451-row manifest-backed evidence bundle after 28 live
reporting checks. Phase 7 closed with 82 passing fast tests, six passing live
PostgreSQL tests, and clean lint and whitespace gates.

### Phase 8 - Power BI

Deliverables:

- Semantic star model with one-way relationships and declared date table
- Executive Overview
- Load & Renewables
- Price Analysis
- Forecast Performance
- Data Quality
- DAX catalogue and report screenshots

Skills: Power BI, DAX, relationships, dashboard design, business reporting.

### Phase 9 - Excel and Power Query

Deliverables:

- Refreshable Monthly Energy Analyst Pack
- Power Query transformation
- PivotTables and charts
- KPI reconciliation with SQL and Power BI

Skills: Excel analytics, Power Query, PivotTables, business-user reporting.

### Phase 10 - Automation and tests

Deliverables:

- One documented pipeline command
- Logging and failure handling
- Full test suite
- Optional GitHub Actions workflow

Skills: reproducibility, automation, testing, CI fundamentals.

### Phase 11 - Portfolio polish

Deliverables:

- Final recruiter-oriented README
- Architecture and data-model diagrams
- Source, quality, forecasting, result, and limitation documentation
- Power BI screenshots and concise findings
- Final technical and recruiter reviews

Skills: technical communication, presentation, GitHub portfolio quality.

## Essential scope

- Real SMARD data with documented lineage
- Hourly load, generation, and day-ahead prices
- Energy/time-series validation
- PostgreSQL star model and reporting views
- One load forecast target, two baselines, and two learned models
- Time-aware evaluation with MAE, RMSE, and MAPE
- Five-page Power BI report
- Meaningful Excel/Power Query pack
- Tests, pipeline runner, README, screenshots, and limitations

## Optional scope after completion

- DWD weather enrichment with a leakage-safe availability contract
- Explainable residual-based unusual-deviation flags
- Official SMARD/ENTSO-E forecast comparison
- Prediction intervals
- Automated refresh or CI
- Regional comparison

## Explicit exclusions

- Price or renewable-generation forecasting as additional targets
- Deep learning and unnecessary forecasting libraries
- Real-time ingestion, streaming, APIs, and production services
- Streamlit and cloud deployment
- Production alerting, authentication, and enterprise orchestration

## Phase gate

Every phase must be explained, implemented in bounded steps, verified, documented, committed, and pushed before the next phase begins.
