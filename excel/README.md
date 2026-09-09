# GridSight monthly energy analyst pack

`GridSight_Monthly_Energy_Analyst_Pack.xlsx` is the business-user companion to
the Power BI report. It analyzes the checked 48-row monthly reporting product
with formula-backed KPIs, annual summaries, charts, a native Power Query
connection, a native PivotTable, and a reconciliation sheet.

## Open and review

1. Open the workbook in a current Microsoft Excel desktop release.
2. Start on **Dashboard** for the portfolio view.
3. Use **Reconciliation** to verify that the workbook agrees with Power BI and
   the SQL reporting contract.
4. Use **Native Pivot** to compare monthly grid-load totals by year.
5. Use **MonthlyEnergy** to audit the refreshable query output. **Monthly Data**
   remains a cached row-level reference sheet for transparent review.

## Refresh Power Query

The public workbook is populated from the checked sample so GitHub reviewers
see results immediately. It also contains the native `MonthlyEnergy` Power
Query connection and a query-backed table. To refresh it on another computer:

1. On **Setup**, set `ProjectRoot` to that computer's local GridSight root.
2. Use **Data > Refresh All**.
3. Confirm that the `MonthlyEnergy` table still contains 48 rows and that the
   **Native Pivot** grand total is 1,872.00 TWh (rounded to two decimals).
4. Confirm that every row on **Reconciliation** remains `PASS`.

The source M expression remains versioned at `queries/monthly_energy.pq` so the
transformation can be reviewed without opening Excel.

The M query reads the `GridSightParameters` table, applies explicit types,
preserves the original 20 reporting columns, and adds presentation fields only.
It does not redefine energy, price, availability, or forecasting semantics.
Every formula-backed dashboard, annual summary, pivot-style audit, and
reconciliation output reads `MonthlyEnergy`, so **Refresh All** updates both the
native PivotTable and the visible analytical results from one authoritative
query table.

## Source and limits

- Input: `data/samples/monthly_energy_sample.csv`
- Grain: one Europe/Berlin month
- Scope: 48 complete months, 2022-2025
- Attribution: Bundesnetzagentur | SMARD.de

The workbook uses a checked public extract, not the complete raw dataset or a
live production feed. **Pivot Analysis** remains a formula-backed audit view;
**Native Pivot** demonstrates the equivalent interactive Excel PivotTable.
