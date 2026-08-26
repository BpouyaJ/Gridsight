# GridSight

**Renewable Energy Analytics & Forecasting Platform**

GridSight is a portfolio project for analyzing German electricity load, renewable generation, and DE/LU day-ahead prices. It will combine a reproducible Python and PostgreSQL pipeline with time-series forecasting, Power BI reporting, and a focused Excel/Power Query analyst pack.

## Business questions

1. How do electricity load and renewable generation change by hour, weekday, month, and season?
2. How are load and renewable generation associated with day-ahead electricity prices?
3. How accurately can the next 24 hourly load values be forecast using information available at the forecast origin?

## Approved scope

- Geography: Germany for load and generation; DE/LU bidding zone for price
- Analysis period: 2022-01-01 through 2025-12-31
- Analytical grain: hourly
- Primary source: Bundesnetzagentur SMARD
- Forecast target: Germany-wide average hourly grid load
- Forecast horizon: the next 24 hourly observations
- Final reporting: PostgreSQL, Power BI, and Excel/Power Query

The essential project intentionally excludes Streamlit, backend APIs, streaming, cloud deployment, deep learning, and additional forecast targets.

## Planned architecture

```text
SMARD source snapshots
        -> source manifest and immutable raw files
        -> Python ingestion and profiling
        -> energy/time-series validation
        -> UTC-normalized hourly data
        -> PostgreSQL staging and analytical model
        -> SQL KPI and reporting views
        -> forecasting features, baselines, and models
        -> Power BI report and Excel analyst pack
```

## Planned technology stack

- Python, Pandas, NumPy, scikit-learn
- PostgreSQL and SQL
- Jupyter and matplotlib for development analysis
- Power BI and DAX
- Excel and Power Query
- pytest, Git, and GitHub
- Docker Compose only as a convenient PostgreSQL runtime

## Repository map

- `configs/`: source and pipeline configuration
- `data/`: data policy, ignored raw/processed files, and small committed samples
- `src/gridsight/`: reusable pipeline, validation, feature, model, and reporting code
- `sql/`: schemas, tables, transformations, and reporting views
- `notebooks/`: source profiling and exploratory analysis only
- `tests/`: validation, transformation, database, and forecasting tests
- `docs/`: roadmap, status, decisions, source contract, methodology, and limitations
- `powerbi/`: Power BI file, model notes, DAX catalogue, and screenshots
- `excel/`: refreshable monthly analyst pack and documented sample input
- `reports/`: final findings, evaluation, and figures

## Current status

Phases 1 through 4 are complete. All three
canonical datasets cover the same 35,064 UTC hours with tested lineage and
domain-specific value rules. Step 4.1 established verified PostgreSQL staging
contracts, conformed dimensions, and two fact-table grains. Step 4.2 verified a
hash-gated, transactional, idempotent load with 19 database reconciliation
checks. Step 4.3 completed tested hourly, technology, daily, and monthly
reporting views. Phase 5 completed fixed KPI definitions, verified analytical
query grains, deterministic aggregate artifacts, a focused EDA notebook, and
four reviewed figures with carefully limited findings. Phase 6 Step 6.1
completed the 24-hour forecasting contract and leakage-safe chronological
evaluation design. Step 6.2 completed deterministic daily and weekly
seasonal-naive benchmarks without evaluating the untouched 2025 test split;
weekly seasonal naive is the stronger validation benchmark. Step 6.3 completed
an auditable calendar, lag, and rolling feature matrix with redacted test
targets before any learned model is fit.
Step 6.4 selected a 31-leaf histogram gradient-boosting model from fixed Ridge
and tree candidates using only chronological validation performance. Step 6.5
refit that frozen design on 2022-2024 and produced a one-time 2025 test MAE of
1,398.259 MW, 46.541% better than the weekly seasonal-naive baseline. No
further model selection is permitted.

Phase 6 is complete with a frozen, leakage-safe feature and model protocol,
two explicit baselines, chronological validation, and an untouched final-year
evaluation reported overall and across all 24 horizons.
Phase 7 Step 7.1 completed the stable Power BI/Excel product grains, keys,
units, and checked public-sample policies before database migrations.

See:

- [Roadmap](docs/roadmap.md)
- [Development setup](docs/development-setup.md)
- [Local PostgreSQL setup](docs/database-setup.md)
- [PostgreSQL analytical model](docs/database-model.md)
- [PostgreSQL loading and reconciliation](docs/database-loading.md)
- [SQL reporting views](docs/reporting-views.md)
- [KPI definitions and query contract](docs/kpi-definitions.md)
- [Focused exploratory analysis](docs/exploratory-analysis.md)
- [Load-forecasting protocol](docs/forecasting-protocol.md)
- [Seasonal-naive baseline evaluation](docs/baseline-evaluation.md)
- [Leakage-safe forecasting features](docs/feature-engineering.md)
- [Chronological model validation](docs/model-validation.md)
- [Final forecast evaluation](docs/final-forecast-evaluation.md)
- [BI/Excel reporting-mart contract](docs/reporting-mart-contract.md)
- [Initial SMARD source profile](docs/initial-source-profile.md)
- [Reproducible source profiling](docs/source-profiling.md)
- [Clean-data contract](docs/clean-data-contract.md)
- [Data-quality validation](docs/data-quality.md)
- [Project status](docs/project-status.md)
- [Decision log](docs/decisions.md)
- [Source contract](docs/source-contract.md)
- [Data policy](data/README.md)

## Data attribution

SMARD market data are licensed under CC BY 4.0. The required attribution is:

> Bundesnetzagentur | SMARD.de

The repository will document source filters, download dates, licences, and checksums. Full raw datasets will not be committed.

## Project maturity

This is a student portfolio project under active development. It does not claim production deployment or operational forecasting capability.
