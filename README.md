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

Phases 1 and 2 are complete, and Phase 3 is in progress. All three canonical datasets now cover the same 35,064 UTC hours with tested lineage and domain-specific value rules. The next step consolidates validation issues and machine-readable run summaries across the clean outputs.

See:

- [Roadmap](docs/roadmap.md)
- [Development setup](docs/development-setup.md)
- [Local PostgreSQL setup](docs/database-setup.md)
- [Initial SMARD source profile](docs/initial-source-profile.md)
- [Reproducible source profiling](docs/source-profiling.md)
- [Clean-data contract](docs/clean-data-contract.md)
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
