# Project status

Last updated: 2026-08-19

## Current phase

Phase 2 - Data acquisition and profiling

Current step: 2.5 - Second actual-generation snapshot registration and compatibility profile

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

## In progress

None. Step 2.5 is ready for its Git checkpoint.

## Not started

- Remaining two SMARD day-ahead-price snapshots
- Pipeline implementation
- Forecasting
- Power BI
- Excel/Power Query

## Next bounded step

After Step 2.5 is committed and pushed, start Step 2.6: download and register the 2022-2023 DE/LU day-ahead-price CSV, then profile its price schema, unit, negative values, and source markers.

## Current blockers

None.
