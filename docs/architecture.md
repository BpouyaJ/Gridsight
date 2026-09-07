# Architecture and analytical data model

## System flow

GridSight separates immutable inputs, generated local data, database products,
checked public evidence, and presentation tools. That boundary lets a reviewer
verify the project from a clean clone without publishing the complete raw or
row-level forecast datasets.

```mermaid
flowchart TB
    subgraph source["Authoritative source"]
        SMARD["Bundesnetzagentur SMARD<br/>load, generation, DE/LU price"]
    end

    subgraph local["Local reproducible pipeline"]
        RAW["Immutable raw CSV snapshots<br/>ignored by Git"]
        MANIFEST["Source manifest<br/>filters, timestamps, SHA-256"]
        PROFILE["Schema and source profiling"]
        CLEAN["UTC-normalized clean datasets<br/>MW, MWh, EUR/MWh explicit"]
        QUALITY["29 deterministic quality checks"]
        FEATURES["27 leakage-safe forecast features"]
        MODELS["Daily and weekly baselines<br/>Ridge and histogram boosting"]
        FINAL["Frozen 2025 evaluation<br/>8,760 forecast rows"]
    end

    subgraph postgres["PostgreSQL 17"]
        STAGING["staging<br/>4 constrained tables"]
        STAR["analytics<br/>3 dimensions and 3 facts"]
        VIEWS["reporting<br/>6 stable views"]
    end

    subgraph public["Source-controlled evidence"]
        REPORTS["Aggregate JSON contracts<br/>KPIs, EDA, model evaluation"]
        SAMPLES["8 checked CSV samples<br/>3,451 rows total"]
        TESTS["95 fast tests and CI"]
    end

    subgraph presentation["Business-facing outputs"]
        PBI["Power BI<br/>5 pages, 21 visuals"]
        EXCEL["Excel and Power Query<br/>dashboard and native PivotTable"]
    end

    SMARD --> RAW
    RAW --> MANIFEST
    RAW --> PROFILE
    MANIFEST --> PROFILE
    PROFILE --> CLEAN
    CLEAN --> QUALITY
    QUALITY --> STAGING
    STAGING --> STAR
    STAR --> VIEWS
    CLEAN --> FEATURES
    FEATURES --> MODELS
    MODELS --> FINAL
    FINAL --> STAR
    VIEWS --> REPORTS
    VIEWS --> SAMPLES
    REPORTS --> TESTS
    SAMPLES --> TESTS
    SAMPLES --> PBI
    SAMPLES --> EXCEL
```

## Analytical star model

The two energy facts stay separate because they have different grains. The
forecast fact links each final-test target to the corresponding actual hourly
fact and to conformed calendar dimensions.

```mermaid
erDiagram
    DIM_DATE {
        int date_key PK
        date calendar_date
        int calendar_year
        int month_number
        int weekday_number
        boolean is_weekend
    }

    DIM_HOUR {
        int hour_key PK
        time hour_start
        string hour_label
    }

    DIM_GENERATION_TECHNOLOGY {
        int technology_key PK
        string technology_id
        string technology_name
        string technology_group
        boolean is_renewable
    }

    FACT_ELECTRICITY_HOURLY {
        datetime interval_start_utc PK
        int date_key FK
        int hour_key FK
        decimal grid_load_mwh
        decimal grid_load_mw
        decimal day_ahead_price_eur_per_mwh
        string consumption_source_sha256
        string price_source_sha256
    }

    FACT_GENERATION_HOURLY {
        datetime interval_start_utc PK
        int technology_key PK
        int date_key FK
        int hour_key FK
        decimal generation_mwh
        decimal generation_mw
        string value_status
        string source_sha256
    }

    FACT_LOAD_FORECAST_EVALUATION {
        datetime forecast_origin_utc PK
        int horizon_step PK
        int origin_date_key FK
        datetime target_start_utc FK
        int target_date_key FK
        int target_hour_key FK
        decimal actual_grid_load_mw
        decimal model_prediction_mw
        decimal model_absolute_error_mw
        string evaluation_snapshot_sha256
    }

    DIM_DATE ||--o{ FACT_ELECTRICITY_HOURLY : "date_key"
    DIM_HOUR ||--o{ FACT_ELECTRICITY_HOURLY : "hour_key"
    DIM_DATE ||--o{ FACT_GENERATION_HOURLY : "date_key"
    DIM_HOUR ||--o{ FACT_GENERATION_HOURLY : "hour_key"
    DIM_GENERATION_TECHNOLOGY ||--o{ FACT_GENERATION_HOURLY : "technology_key"
    DIM_DATE ||--o{ FACT_LOAD_FORECAST_EVALUATION : "origin_date_key"
    DIM_DATE ||--o{ FACT_LOAD_FORECAST_EVALUATION : "target_date_key"
    DIM_HOUR ||--o{ FACT_LOAD_FORECAST_EVALUATION : "target_hour_key"
    FACT_ELECTRICITY_HOURLY ||--o| FACT_LOAD_FORECAST_EVALUATION : "target_start_utc"
```

## Time, unit, and availability rules

| Concern | Enforced rule |
|---|---|
| Fact identity | UTC timestamps are unique; Europe/Berlin fields are reporting attributes. |
| Daylight saving time | Spring gaps and both autumn folds are preserved without duplicate UTC keys. |
| Energy | MWh/TWh are summed only across compatible intervals. |
| Power | MW/GW are averaged or compared at the declared grain, never summed as energy. |
| Price | EUR/MWh is averaged with explicit observed-hour weighting; negative values remain valid. |
| Generation gaps | Source `-` markers become unavailable/null, never measured zero. |
| Forecast availability | Every feature must be complete by its forecast origin. |
| Lineage | Source export IDs and SHA-256 values survive into canonical and analytical products. |

## Reporting boundary

Power BI and Excel read stable reporting products rather than staging tables.
The public PBIP and workbook use deterministic samples so they open with useful
results on another machine. A database-backed rebuild remains available for
the full local pipeline, while source-controlled contracts prevent the desktop
tools from redefining metric semantics.
