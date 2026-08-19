# Project status

Last updated: 2026-08-19

## Current phase

Phase 3 - Validation and transformation

Current step: 3.4 - Canonical DE/LU day-ahead-price transformation

Status: completed

## Completed

- Compared Codex, ChatGPT Work, reasoning settings, agents, skills, and plugins.
- Approved Codex as the primary development environment.
- Researched official and credible energy-data options.
- Selected Bundesnetzagentur SMARD as the essential source.
- Selected Germany/DE-LU, hourly grain, and 2022-2025 coverage.
- Selected Germany-wide load as the only essential forecasting target.
- Approved the architecture, analytical model, Power BI scope, Excel scope, and development phases.
- Created the Git repository and approved folder structure.
- Persisted the roadmap, decision log, source contract, data policy, and agent workflow.
- Verified local Markdown links, ignored-data rules, and the absence of implementation code.
- Created a Python 3.13 virtual environment under `.venv`.
- Added `pyproject.toml` with runtime, analysis, and development dependency groups.
- Installed GridSight as an editable package with its approved analytics and database dependencies.
- Added Windows development-environment instructions.
- Passed the initial package smoke test with pytest.
- Passed the Ruff code-quality check.
- Added a healthy PostgreSQL 17.10 service using Docker Compose.
- Added an ignored local `.env` credential workflow and persistent database volume.
- Added validated database settings and a SQLAlchemy/Psycopg connection factory.
- Passed the Python-to-PostgreSQL connection command.
- Passed the marked PostgreSQL integration test while keeping it out of the default fast test suite.
- Defined the six approved SMARD exports with exact filters, periods, geographies, and normalized filenames.
- Added the tracked source-manifest schema before downloading data.
- Added an immutable, SHA-256-based raw-snapshot registration command.
- Verified idempotent registration and protection against different-content overwrites.
- Passed all four fast tests and the Ruff code-quality check.
- Registered the 2022-2023 Germany actual-consumption snapshot with matching raw and manifest SHA-256 values.
- Confirmed 17,520 hourly rows, six columns, UTF-8 BOM encoding, semicolon delimiter, and MWh measures.
- Selected `grid load [MWh] Calculated resolutions` as the primary load measure.
- Confirmed no missing or non-numeric measure markers in the initial snapshot.
- Documented 23-hour spring and 25-hour autumn daylight-saving behavior and repeated local timestamp text.
- Corrected the export configuration to distinguish expected output series from selectable SMARD filters.
- Re-ran all four fast tests and Ruff successfully after profiling updates.
- Registered the 2024-2025 Germany actual-consumption snapshot with matching raw and manifest SHA-256 values.
- Confirmed its six-column schema, encoding, delimiter, and numeric format match the 2022-2023 snapshot.
- Confirmed 17,544 rows, with the expected extra leap-day hours from 2024.
- Confirmed the same spring/fall daylight-saving behavior and no missing or non-numeric measure markers.
- Verified that both actual-consumption snapshots can use one ingestion schema.
- Re-ran all four fast tests and Ruff successfully after the compatibility update.
- Registered the 2022-2023 Germany actual-generation snapshot with matching raw and manifest SHA-256 values.
- Confirmed 17,520 rows, 14 columns, and 12 explicit generation-technology measures.
- Confirmed the generation file shares the consumption files' encoding, delimiter, numeric format, timestamp format, and DST behavior.
- Confirmed no missing or non-numeric generation measure markers in the snapshot.
- Registered the 2024-2025 Germany actual-generation snapshot with matching raw and manifest SHA-256 values.
- Confirmed its 14-column schema, encoding, delimiter, units, timestamp representation, and DST behavior match the 2022-2023 generation snapshot.
- Confirmed 17,544 rows, including the expected 24 leap-day hours from 2024.
- Identified 16,836 `-` source markers in the Nuclear measure beginning at 2024-01-30 12:00, after 708 numeric zero values.
- Defined `-` as missing/unavailable during parsing rather than silently treating it as measured zero.
- Verified that both actual-generation snapshots can use one structural ingestion schema with a column-aware missing-marker rule.
- Registered the 2022-2023 DE/LU day-ahead-price snapshot with matching raw and manifest SHA-256 values.
- Selected `Germany/Luxembourg [€/MWh] Calculated resolutions` from the 19-column multi-market export as the exact GridSight price measure.
- Confirmed all 17,520 target-price rows are numeric, with 370 negative values, 30 zeroes, and no source markers.
- Recorded the observed target-price range from -500.00 to 871.00 EUR/MWh and classified negative wholesale prices as valid observations.
- Confirmed the price snapshot shares the other sources' encoding, delimiter, local timestamp representation, and DST behavior.
- Registered the 2024-2025 DE/LU day-ahead-price snapshot with matching raw and manifest SHA-256 values.
- Confirmed its 19-column schema exactly matches the 2022-2023 price snapshot and contains the same Germany/Luxembourg target.
- Confirmed all 17,544 later target-price rows are numeric, with 1,030 negative values, 144 zeroes, and no source markers.
- Recorded the later target-price range from -250.32 to 936.28 EUR/MWh.
- Confirmed the expected leap-day and daylight-saving row behavior.
- Completed registration and documented read-only profiling for all six approved SMARD snapshots.
- Added a reusable Pandas-based profiler for every registered raw snapshot.
- Added automated checks for manifest hashes, expected hourly row counts, exact targets, category schemas, source markers, and repeated local hours.
- Added a read-only command that reproduced all documented source-profile results and completed with `Source profiling: OK`.
- Added the reproducible `01_smard_source_profile.ipynb` notebook as a thin presentation layer over tested package code.
- Added focused tests for leap-year/DST interval counts and numeric-versus-marker profiling.
- Passed all six fast tests and Ruff after completing the Phase 2 profiling artifacts.
- Completed the Phase 2 gate with all required acquisition, lineage, profiling, notebook, documentation, and verification deliverables.
- Defined the canonical UTC and Europe/Berlin time columns while preserving raw source labels.
- Implemented locale-independent SMARD timestamp parsing and ordered autumn-hour disambiguation.
- Derived canonical ends from UTC starts plus one hour to handle both DST boundaries safely.
- Added a read-only six-snapshot timestamp-normalization check and focused spring, autumn, and real-gap tests.
- Verified all six snapshots become continuous unique UTC hours with CET/CEST offsets and two second-fold rows per two-year file.
- Passed all nine fast tests and Ruff after completing Step 3.1.
- Mapped all four actual-consumption measures to explicit canonical MWh columns and derived the primary `grid_load_mw` measure.
- Implemented strict numeric parsing while preserving valid negative residual load.
- Added row-level manifest lineage and continuous combination of both consumption periods.
- Added a reproducible atomic build for the ignored clean consumption CSV.
- Verified 35,064 continuous rows, 24 columns, complete UTC coverage, and processed SHA-256 `4a0107f087fdd5d87e584c913c6e73187f6e2c81057053964250cf3f1f9316a5`.
- Passed all 15 fast tests, Ruff, and the processed-file Git-ignore check after completing Step 3.2.
- Defined 12 stable generation technology IDs with renewable, conventional, or storage classification.
- Implemented one interval/technology row with numeric MWh/MW and preserved source value text.
- Represented only the Nuclear `-` marker as unavailable with missing numeric values.
- Extracted shared source-lineage handling for consumption, generation, and later category transformations.
- Verified 420,768 rows, 35,064 intervals, 12 technologies, 403,932 numeric rows, and 16,836 unavailable Nuclear rows.
- Recorded processed generation SHA-256 `9106f24f0e793a2807d4116edb1454490b5f9fc9a340c75c36e450634a3b328f`.
- Passed all 20 fast tests, Ruff, and the generation-output Git-ignore check after completing Step 3.3.
- Required the exact profiled 19-column market-export schema and selected only the Germany/Luxembourg series.
- Implemented strict finite numeric parsing while retaining negative and zero prices.
- Added explicit market-area, currency, unit, source-text, and shared lineage columns.
- Verified 35,064 continuous rows, 25 columns, 1,400 negative prices, 174 zero prices, and a -500.00 to 936.28 EUR/MWh range.
- Recorded processed price SHA-256 `a9a66c7f69900289c944ec72bcc1a62e26fbb3c37839e3ad34f7f405a622e53e`.
- Passed all 25 fast tests, Ruff, and the price-output Git-ignore check after completing Step 3.4.

## In progress

None. Step 3.4 is ready for its Git checkpoint.

## Not started

- Category-specific measure parsing and clean datasets
- Validation-error output and run summaries
- Forecasting
- Power BI
- Excel/Power Query

## Next bounded step

After Step 3.4 is committed and pushed, start Step 3.5: produce structured validation issues and a machine-readable run summary that reconcile UTC coverage, row counts, keys, units, availability, and output hashes across all three clean datasets.

## Current blockers

None.
