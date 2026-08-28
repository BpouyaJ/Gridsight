# Power BI semantic-model contract

## Purpose

Step 8.1 freezes the model before any report visuals are built. The contract
prevents Power BI from introducing ambiguous relationships, implicit measures,
unit drift, or metric definitions that disagree with Python and PostgreSQL.

Build the deterministic artifacts from the project root:

```powershell
python -m gridsight.reporting.build_powerbi_contract
```

The command hash-gates the implemented reporting-mart contract, checked sample
manifest, KPI snapshot, and frozen final forecast evaluation. It writes:

- `reports/powerbi_semantic_model_contract.json`;
- `powerbi/dax/measures.dax`.

Two consecutive verified builds produced identical artifacts:

- semantic-model contract SHA-256:
  `6f94e6bae7d426fd0a1014cf9665d02c857679e36fd773be22e23ab51d0fb32e`;
- DAX catalogue SHA-256:
  `de63d5a9964a08968674bb56bf7eea0a3bb316d937eaef6d9cc8e92d38e676df`.

All 87 fast tests passed with six live PostgreSQL tests deselected, including
the five semantic-model, relationship, date-table, DAX, page, determinism, and
source-lineage contract tests.
All five focused tests passed again after correcting the only Ruff finding,
which was import ordering. Ruff and `git diff --check` then passed cleanly.

## Desktop project decision

Step 8.1 versions the design contract and DAX catalogue. Step 8.2 uses Power BI
Desktop to create the actual PBIP/PBIR/TMDL files through **Save as Power BI
Project**. We do not invent those files by hand because Microsoft currently
documents Power BI Desktop projects and enhanced PBIR report definitions as
preview features with versioned schemas. Desktop can open the generated
project through its `.pbip` or report `definition.pbir` file, while TMDL gives
the semantic model a source-control-friendly representation.

Official references:

- [Power BI Desktop project structure](https://learn.microsoft.com/power-bi/developer/projects/projects-overview)
- [PBIR report-folder structure](https://learn.microsoft.com/power-bi/developer/projects/projects-report)
- [TMDL view and PBIP](https://learn.microsoft.com/power-bi/transform-model/desktop-tmdl-view)
- [Power BI star-schema guidance](https://learn.microsoft.com/power-bi/guidance/star-schema)
- [Set and use a date table](https://learn.microsoft.com/power-bi/transform-model/desktop-date-tables)

## Model tables

The model uses Import mode for a stable, responsive portfolio report.

| Table | Role | Source | Grain |
|---|---|---|---|
| `Dim Date` | Dimension | Reference of `daily_energy` | One Europe/Berlin date |
| `Dim Month` | Dimension | Reference of `monthly_energy` | One Europe/Berlin month |
| `Dim Hour` | Dimension | Distinct reference of `hourly_energy` | One reporting hour label |
| `Dim Technology` | Dimension | Distinct generation reference | One generation technology |
| `Dim Horizon` | Dimension | Generated values 0-24 | Overall or one horizon |
| `Dim Forecast Series` | Dimension | Distinct summary reference | One forecast series |
| `Fact Hourly Energy` | Fact | `reporting.hourly_energy` | One canonical UTC hour |
| `Fact Hourly Generation` | Fact | `reporting.hourly_generation_by_technology` | UTC hour and technology |
| `Fact Daily Energy` | Fact | `reporting.daily_energy` | One Europe/Berlin date |
| `Fact Monthly Energy` | Fact | `reporting.monthly_energy` | One Europe/Berlin month |
| `Fact Forecast Hourly` | Fact | `reporting.forecast_performance_hourly` | Origin and horizon |
| `Fact Forecast Summary` | Fact | `reporting.forecast_performance_summary` | Series and scope |
| `Data Quality Checks` | Evidence | Checked CSV | One stable validation check |
| `Source Lineage` | Evidence | Checked CSV | One registered export |
| `_Measures` | Measure table | Calculated placeholder | One hidden row |

The reporting views remain the business-logic boundary. Power Query may select,
rename, type, hide, or deduplicate dimension columns, but it must not recompute
the upstream energy, price, forecast, or quality semantics.

## Relationships

Every relationship is active, one-to-many, and single-direction from the
dimension to the fact. There are no fact-to-fact or bidirectional
relationships.

| One side | Many side |
|---|---|
| `Dim Date[date_key]` | `Fact Hourly Energy[date_key]` |
| `Dim Date[date_key]` | `Fact Hourly Generation[date_key]` |
| `Dim Date[date_key]` | `Fact Daily Energy[date_key]` |
| `Dim Date[date_key]` | `Fact Forecast Hourly[target_date_key]` |
| `Dim Month[month_key]` | `Fact Monthly Energy[month_key]` |
| `Dim Hour[hour_key]` | `Fact Hourly Energy[hour_key]` |
| `Dim Hour[hour_key]` | `Fact Hourly Generation[hour_key]` |
| `Dim Hour[hour_key]` | `Fact Forecast Hourly[target_hour_key]` |
| `Dim Technology[technology_key]` | `Fact Hourly Generation[technology_key]` |
| `Dim Horizon[horizon_step]` | `Fact Forecast Hourly[horizon_step]` |
| `Dim Horizon[horizon_step]` | `Fact Forecast Summary[horizon_step]` |
| `Dim Forecast Series[forecast_name]` | `Fact Forecast Summary[forecast_name]` |

`Dim Date[calendar_date]` is declared as the date table. It contains 1,461
unique contiguous dates from 2022-01-01 through 2025-12-31. UTC remains the
unique event time in facts; date, month, hour-label, weekday, and DST display
attributes use Europe/Berlin.

## DAX catalogue

The 30 explicit measures live in the `_Measures` table and are grouped into:

- Energy: observed hours, load energy, average load, and peak load;
- Generation: reported, renewable, conventional, and storage energy plus
  renewable share;
- Price: average price, negative-price hours, and negative-price share;
- Forecast: final model MAE/RMSE/MAPE, both baseline MAEs, improvement, and a
  series-selected MAE;
- Data Quality: unavailable values, check counts/pass rate, and source count.

Base numeric columns use **Do not summarize** and are hidden when a measure is
the intended reporting interface. DAX calculations preserve these rules:

- MWh is summed over time and divided by 1,000,000 only when displayed as TWh;
- hourly MW and EUR/MWh are averaged, not summed;
- renewable share is a ratio of summed energy, not an average of percentages;
- negative prices remain in the average and below-zero count;
- unavailable generation values remain unavailable rather than becoming zero;
- forecast metrics use the frozen 2025 test only and do not authorize tuning.

## Acceptance values

Before any page is accepted, Power BI must reproduce these all-period values:

| Measure | Expected |
|---|---:|
| Observed Hours | 35,064 |
| Total Grid Load | 1,871.998 TWh |
| Average Grid Load | 53.388 GW |
| Peak Grid Load | 78.681 GW |
| Renewable Share | 54.61% |
| Average Day-Ahead Price | 124.58 EUR/MWh |
| Negative Price Hours | 1,400 |
| Unavailable Generation Values | 16,836 |
| Model MAE | 1,398.259 MW |
| Model RMSE | 2,011.223 MW |
| Model MAPE | 2.652% |
| Weekly Baseline MAE | 2,615.589 MW |
| Model Improvement vs Weekly | 46.541% |
| Data Quality Checks / Pass Rate | 29 / 100% |
| Registered Source Snapshots | 6 |

The machine-readable contract stores raw ratio values for formatted
percentages, such as `0.5461` for 54.61%, with explicit tolerances.

## Five-page report boundary

The required pages are:

1. Executive Overview
2. Load & Renewables
3. Price Analysis
4. Forecast Performance
5. Data Quality

Their exact business questions, minimum visuals, fields, slicers, and caveats
are frozen in `powerbi/page-wireframes.md` and the JSON contract. Step 8.1 does
not create report screenshots or claim that a Desktop report exists. Those are
verified only after the user completes the Desktop build in later Phase 8
steps.
