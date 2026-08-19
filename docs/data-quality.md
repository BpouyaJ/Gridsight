# Data-quality validation

## Purpose

GridSight's final Phase 3 gate converts transformation rules into one
reproducible, machine-readable validation run. It verifies each canonical
dataset independently and then reconciles all three against one UTC hourly
spine.

## Run command

From the activated project virtual environment, run:

```powershell
python -m gridsight.validation.run_validation
```

The command performs these actions in order:

1. Recheck all six raw snapshot hashes and rebuild the three canonical frames
   in memory.
2. Run the complete validation suite without replacing existing clean files.
3. If validation passes, atomically write all three canonical CSVs.
4. Write deterministic validation issues and summary artifacts.
5. Return exit code `0` for a passing run or `1` for a failed run.

## Validation coverage

Stable check IDs are grouped by dataset:

- `consumption.*`: column and row contracts, unique hours, finite and
  non-negative constrained measures, grid-load arithmetic, hourly MW
  conversion, and lineage.
- `generation.*`: column and row contracts, unique interval/technology keys,
  all 12 technologies per hour, technology metadata, value-status domain,
  unavailable Nuclear semantics, reported value rules, hourly MW conversion,
  and lineage.
- `price.*`: column and row contracts, unique hours, DE/LU market identity,
  finite prices with negative values allowed, and lineage.
- `cross_dataset.*`: identical UTC starts and one-hour interval duration across
  consumption, generation, and price.

Failed checks are not silently downgraded. Each failure becomes an error issue
and makes the overall run fail.

## Structured issues CSV

`data/processed/validation_issues.csv` has this stable schema:

| Column | Meaning |
|---|---|
| `dataset` | `consumption`, `generation`, `price`, or `cross_dataset`. |
| `check_id` | Stable programmatic identifier for the failed rule. |
| `severity` | Currently `error`; every issue blocks publication. |
| `column` | Relevant canonical column, or blank for a wider rule. |
| `affected_rows` | Count of directly affected rows when measurable. |
| `message` | Concise human-readable explanation. |

A passing run still produces the file with its header and no issue rows. This
makes downstream loading predictable.

## Machine-readable JSON summary

`data/processed/validation_summary.json` contains:

- `schema_version` for consumers of the artifact;
- overall `status`;
- passed and failed check counts;
- issue counts by severity;
- ordered individual check results with expected and observed values;
- row, column, interval, coverage, and category-specific dataset metrics;
- canonical output paths and SHA-256 values after a successful publication.

The summary intentionally has no wall-clock run timestamp. With unchanged raw
snapshots and code, both validation artifacts reproduce byte for byte. Source
download timestamps remain available in the tracked manifest.

## Publication safety

Validation happens before the canonical output writers are called. A failed
validation run therefore preserves the last known-good consumption,
generation, and price CSVs while publishing enough diagnostic information to
repair the problem. All generated clean and validation artifacts remain ignored
by Git; their contracts, code, tests, and documented verified hashes are
tracked.

## Verified Phase 3 gate

The completed run produced 29 passed checks, zero failed checks, and zero
issues. The output CSV hashes matched the independently verified Steps 3.2,
3.3, and 3.4 hashes. The generated validation artifacts were:

- `validation_issues.csv` SHA-256:
  `f71d51df4b07a9d80be883432a59eabec1c957b0c8627e499de5c853d06eaecf`;
- `validation_summary.json` SHA-256:
  `5fc1af559d4ebb46712a86d7cff3f5780a0af2c24ce480c0e7016767176de766`.

The full fast suite passed 29 tests with one PostgreSQL integration test
deselected, and the repository passed Ruff. This result completes the Phase 3
validation and transformation gate.
