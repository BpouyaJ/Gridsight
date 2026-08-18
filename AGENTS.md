# GridSight working agreement

This repository is a learning-first portfolio project for Energy Analytics, Business Intelligence, and forecasting roles. Follow these rules for every task in this repository.

## Sources of truth

1. `docs/roadmap.md` defines the approved project scope and phase order.
2. `docs/project-status.md` records completed work and the next bounded step.
3. `docs/decisions.md` records accepted technical and scope decisions.
4. `docs/source-contract.md` defines the selected data, grain, time range, units, and attribution.

If a requested change conflicts with these files, explain the conflict before changing the project direction.

## Step-by-step workflow

- Work on one bounded step at a time. Do not start a later phase before the current phase is verified.
- Before editing, explain what will be built and why it matters technically and for the target jobs.
- Provide exact files and commands, and explain unfamiliar code in plain language.
- Run a concrete verification appropriate to the step.
- Debug the current step before proposing a redesign.
- After verification, update `docs/project-status.md` and add material decisions to `docs/decisions.md`.
- At every meaningful checkpoint, remind the user to commit and push. Do not claim a commit or push occurred unless it was verified.

## Technical boundaries

- Keep UTC as the canonical timestamp and retain Europe/Berlin values for reporting.
- Never mix MW, MWh, and EUR/MWh. State the grain and unit of every fact and KPI.
- Preserve raw source snapshots unchanged. Transform copies only.
- Never use random train/test splits for forecasting.
- Every forecasting feature must be available at its forecast origin.
- Fit preprocessing and models using training data only.
- Keep notebooks for profiling and exploration; reusable logic belongs under `src/gridsight/`.
- Use explicit SQL dimensions, facts, and reporting views instead of one undocumented flat table.
- Do not commit credentials, full raw datasets, database volumes, temporary outputs, or large model binaries.

## Scope boundaries

- Do not add Streamlit, a backend API, microservices, streaming, cloud orchestration, or deep learning unless the approved roadmap is explicitly revised.
- Do not add a second forecast target before the essential load-forecasting scope is complete.
- Do not present the project as production experience or call basic forecasting an advanced AI system.
- Prefer a small complete implementation over optional features.
- Use subagents primarily for read-heavy research, testing, and review. Avoid parallel edits to the same files.

## Portfolio quality

- Keep claims defensible in an interview.
- Explain business meaning, limitations, and data lineage alongside technical implementation.
- Make final outputs understandable to recruiters and hiring managers, not only programmers.

