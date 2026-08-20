# PostgreSQL analytical model

## Purpose

GridSight uses PostgreSQL to demonstrate explicit analytical modeling rather
than treating a database as storage for one undocumented flat file. Step 4.1
creates the schemas, table contracts, keys, relationships, and database-level
quality constraints. It does not load data.

## Responsibility boundaries

| Schema | Responsibility |
|---|---|
| `staging` | Canonical clean datasets with row-level source lineage. |
| `analytics` | Conformed dimensions and fact tables at declared grains. |
| `reporting` | Stable SQL views for Power BI and Excel in later steps. |

The reporting schema is intentionally empty in Step 4.1. Reporting views will
be created only after the analytical facts are loaded and reconciled.

## Staging tables

| Table | Grain | Expected loaded rows |
|---|---|---:|
| `staging.actual_consumption_hourly` | One Germany UTC hour | 35,064 |
| `staging.actual_generation_hourly` | One Germany UTC hour and technology | 420,768 |
| `staging.day_ahead_price_hourly` | One DE/LU UTC hour | 35,064 |

The three tables preserve every canonical clean column in its defined order.
Primary keys reject duplicate UTC or interval/technology keys. Check
constraints enforce one-hour intervals, allowed CET/CEST offsets, local-fold
values, source category/geography/resolution, lowercase SHA-256 lineage, units,
measure domains, and generation availability semantics.

PostgreSQL stores `TIMESTAMPTZ` as an absolute instant. The canonical UTC key
therefore remains unambiguous. The retained UTC offset, DST flag, local fold,
and exact source timestamp text preserve the reporting and source context that
would otherwise be lost when PostgreSQL renders the instant in a session time
zone.

## Analytics dimensions

### `analytics.dim_date`

One row per Europe/Berlin calendar date. The integer `date_key` uses `YYYYMMDD`
and is constrained to match `calendar_date`. It contains calendar year,
quarter, month, ISO week, day, weekday, and weekend attributes.

### `analytics.dim_hour`

Exactly 24 local clock-hour members, keyed `0` through `23`, with a time value
and `HH:MI` label. A repeated autumn hour maps to the same reporting hour while
remaining two separate fact rows through their distinct UTC keys and fold
values.

### `analytics.dim_generation_technology`

Exactly the 12 approved technologies, with stable keys, IDs, display names,
renewable/conventional/storage groups, renewable flags, and display order.

## Analytics facts

### `analytics.fact_electricity_hourly`

Grain: one canonical UTC hour.

Consumption and DE/LU price share the same complete hourly spine, so this fact
combines their measures without aggregation. Germany load and DE/LU price
geographies remain explicit. Measures retain their names and units: MWh, MW,
and EUR/MWh are never mixed. Consumption and price export IDs and hashes retain
fact-level traceability to staging.

### `analytics.fact_generation_hourly`

Grain: one canonical UTC hour and generation technology.

Generation remains a separate fact because its 12-row-per-hour grain differs
from the one-row electricity fact. Reported MWh and MW must be equal for the
one-hour interval and non-negative. Unavailable values must keep both numeric
columns null. Technology, date, and hour foreign keys enforce conformed
dimensions.

## Apply and inspect the contract

Start PostgreSQL, then run:

```powershell
python -m gridsight.database.apply_schema
```

The command applies three ordered SQL files in one transaction:

1. `sql/schemas/001_create_schemas.sql`
2. `sql/tables/001_create_staging_tables.sql`
3. `sql/tables/002_create_analytics_tables.sql`

All schema, table, and index statements use `IF NOT EXISTS`, so applying the
unchanged contract repeatedly is safe. After applying DDL, Python inspects the
live database and compares schema names, ordered columns, primary keys, foreign
key targets, and minimum check-constraint counts with the declared contract.

`IF NOT EXISTS` does not silently migrate an incompatible existing table. If a
live table differs from the code contract, inspection fails and reports the
specific table-level mismatch. Later schema changes must use a new ordered SQL
file rather than rewriting a deployed contract invisibly.

## Step boundary

Step 4.1 creates empty, verified tables. Step 4.2 implements the transactional
and idempotent loader, dimension and fact population, and reconciliation with
the Phase 3 validation summary. Its operational contract is documented in
`docs/database-loading.md`.

## Verified Step 4.1 result

The live PostgreSQL application and metadata inspection reported:

- three ordered SQL files and 14 executed statements;
- `staging`, `analytics`, and `reporting` schemas;
- three staging tables, five analytics tables, and zero reporting tables;
- a complete match between live columns, keys, references, constraints, and the
  declared Python contract.

The fast suite passed 33 tests with both integration tests deselected. The live
suite passed the PostgreSQL identity test and the schema idempotence/contract
test, with 33 fast tests deselected. Ruff also passed.
