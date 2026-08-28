# GridSight Power BI page wireframes

These wireframes freeze the business question and minimum evidence for each
page. Exact pixel positions and styling are chosen in Power BI Desktop after
the semantic model reconciles to the Step 8.1 acceptance values.

Global rules:

- use a 16:9 canvas and a consistent page header;
- show units in every card, axis, title, and tooltip;
- use Europe/Berlin calendar fields for reporting and UTC for unique events;
- retain negative prices and source-unavailable generation values;
- use DAX measures rather than implicit aggregation of numeric columns;
- never imply causation from the renewable-share/price association;
- never use the 2025 final test to select or tune another forecast model.

## 1. Executive Overview

Business question: What changed across 2022-2025, and what should a
decision-maker notice?

```text
+-----------------------------------------------------------------------+
| GridSight | Executive Overview                      [Year slicer]      |
+----------------+----------------+----------------+--------------------+
| Grid Load TWh  | Renewable %    | Avg Price      | Forecast MAE MW    |
+----------------+----------------+----------------+--------------------+
| Annual Grid Load columns + Renewable Share line | Avg Price by Year  |
|                                                  |                    |
+--------------------------------------------------+--------------------+
| Scope, source attribution, and interpretation limits                  |
+-----------------------------------------------------------------------+
```

Required measures: `Total Grid Load TWh`, `Renewable Share %`, `Average
Day-Ahead Price`, and `Model MAE MW`.

## 2. Load & Renewables

Business question: How do load, renewable output, and technology mix vary over
time?

```text
+-----------------------------------------------------------------------+
| Load & Renewables          [Year] [Month] [Technology group]          |
+-----------------------------------------------------------------------+
| Daily Grid Load and Renewable Generation trend                        |
+--------------------------------------------+--------------------------+
| Generation by Technology stacked area      | Weekday/Weekend Load     |
|                                            | Shape by Hour            |
+--------------------------------------------+--------------------------+
```

Unavailable generation values remain blank and are surfaced through tooltips;
they are never converted to zero.

## 3. Price Analysis

Business question: When are prices negative or extreme, and how do they relate
to renewable generation?

```text
+-----------------------------------------------------------------------+
| Price Analysis                            [Year] [Month]               |
+-----------------------------+-----------------------------------------+
| Negative Price Hours        | Negative Price Share                    |
+-----------------------------+-----------------------------------------+
| DE/LU hourly price trend with visible zero reference line             |
+--------------------------------------------+--------------------------+
| Daily Renewable Share vs Price scatter     | Interpretation note      |
+--------------------------------------------+--------------------------+
```

The scatter plot states that correlation is descriptive and does not establish
causation.

## 4. Forecast Performance

Business question: Does the frozen model beat honest seasonal baselines,
overall and across all 24 horizons?

```text
+-----------------------------------------------------------------------+
| Forecast Performance                   [Date] [Forecast series]        |
+--------------+--------------+--------------+--------------------------+
| MAE MW       | RMSE MW      | MAPE %       | Improvement vs Weekly %  |
+--------------+--------------+--------------+--------------------------+
| Actual vs Model hourly load              | MAE by Horizon             |
|                                          |                            |
+------------------------------------------+----------------------------+
| Selected model vs daily and weekly seasonal-naive baseline MAE        |
+-----------------------------------------------------------------------+
```

The page is final-test evidence only. It must display the frozen model and both
baselines and must not support further model selection.

## 5. Data Quality

Business question: Can a reviewer trace the data and verify the analytical
gates?

```text
+-----------------------------------------------------------------------+
| Data Quality                                                          |
+----------------+----------------+----------------+--------------------+
| Passed Checks  | Pass Rate      | Unavailable    | Source Snapshots   |
+----------------+----------------+----------------+--------------------+
| 29-check validation matrix                                            |
+-----------------------------------------------------------------------+
| Six-row source lineage table with periods and SHA-256                 |
+-----------------------------------------------------------------------+
```

The page shows the individual checks and source rows, not only headline green
cards.
