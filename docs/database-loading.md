# PostgreSQL data loading and reconciliation

## Purpose

Step 4.2 loads the Phase 3 canonical CSVs into the empty Step 4.1 table
contracts, populates the analytical star model, and proves that PostgreSQL
contains the same rows and measures as the validated files.

## Trust boundary before loading

The loader requires these ignored Phase 3 artifacts:

- `data/processed/validation_summary.json`;
- `data/processed/validation_issues.csv`;
- the three canonical processed CSVs named in the summary.

Before connecting to PostgreSQL, it requires summary schema version 1, overall
status `passed`, zero failed checks, zero error issues, and only passed
individual checks. The issue CSV must contain only its defined header. For each
dataset, the declared path, row count, column count, exact ordered CSV header,
and SHA-256 must match the fixed loading contract and current file bytes.

This creates an auditable chain:

```text
immutable raw snapshots
    -> tested canonical transformation
    -> passing validation summary and output hashes
    -> verified PostgreSQL load
```

## Transactional full refresh

Run the loader with PostgreSQL healthy:

```powershell
python -m gridsight.database.load_data
```

The command applies the Step 4.1 DDL if needed and then performs one database
transaction:

1. Truncate all staging, dimension, and fact tables together, including any
   dependent Step 7.2 forecast rows.
2. Stream the three canonical CSVs from the Python client through PostgreSQL
   `COPY` into staging.
3. Populate date, hour, and technology dimensions with SQL.
4. Populate the hourly electricity and interval/technology generation facts.
5. Run all reconciliation checks.
6. Commit only if every check passes.

PostgreSQL `TRUNCATE` is transactional. A copy, constraint, transformation, or
reconciliation failure rolls back the entire refresh, including the truncate,
so users never see a deliberately committed partial model.

The fixed four-year portfolio dataset is small enough for a full refresh, and
full replacement makes repeatability easier to defend than a partially
incremental merge. Client-side `COPY` keeps the large 420,768-row generation
load efficient without granting the database server filesystem access.

## SQL transformations

Reusable transformation logic remains visible in SQL:

- `sql/transformations/001_populate_dimensions.sql` derives the local date and
  hour dimensions and promotes the 12 technology members.
- `sql/transformations/002_populate_facts.sql` joins aligned consumption and
  price rows and retains generation's different interval/technology grain.

Local reporting dates and hours are derived explicitly with
`AT TIME ZONE 'Europe/Berlin'`. UTC remains the fact key, so both occurrences of
an autumn repeated hour remain distinct even though they share local date and
hour dimension members.

## Reconciliation contract

The load must pass 19 stable checks:

- row counts for three staging tables, three dimensions, and two facts;
- 35,064 consumption rows, 35,064 price rows, and 420,768 generation rows in
  both their staging and analytical destinations;
- 1,461 local dates, 24 hours, and 12 technologies;
- price negative, zero, and positive counts plus minimum and maximum;
- reported and unavailable generation counts;
- identical consumption/price and consumption/generation UTC spines;
- exact copies of selected electricity and generation measures and lineage.

The expected price and availability metrics come from the current Phase 3 JSON
summary rather than being silently recalculated as new expectations after the
load. Output hashes connect those expectations to the exact loaded bytes.

## Idempotence

Running the loader repeatedly produces the same table counts and values. The
live integration test performs two complete loads and requires identical
reconciled counts. This is idempotent full-refresh behavior, not an append that
would duplicate facts.

## Step boundary

Step 4.2 loads and reconciles internal analytical tables. Step 4.3 will add
tested, stable `reporting` views for KPI analysis, Power BI, and Excel without
making those clients depend directly on staging implementation details.

## Verified Step 4.2 result

Two consecutive command-line loads produced identical successful results:

- validation-summary SHA-256
  `5fc1af559d4ebb46712a86d7cff3f5780a0af2c24ce480c0e7016767176de766`;
- five SQL transformation statements;
- 19 passed reconciliation checks and zero failures;
- 35,064 consumption staging and electricity-fact rows;
- 35,064 price staging rows;
- 420,768 generation staging and generation-fact rows;
- 1,461 date, 24 hour, and 12 technology dimension rows.

The complete fast suite passed 37 tests with three live tests deselected. The
live suite passed database identity, repeated full-load reconciliation, and
schema idempotence/contract inspection, with 37 fast tests deselected. Ruff
also passed. The repeated load test completed without duplicated rows or count
drift.

Because forecast facts reference the canonical electricity fact, a canonical
full refresh clears them first. Rebuild them afterward with
`python -m gridsight.database.load_forecast_mart`.
