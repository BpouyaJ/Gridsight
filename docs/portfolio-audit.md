# Final portfolio audit

## Outcome

GridSight completed its approved Energy Analytics, Business Intelligence, data,
and forecasting scope on 2026-09-08. The repository is designed to be reviewed
from a clean public clone without local raw data, Power BI Desktop, Excel,
Docker, or PostgreSQL.

## Automated gate

The public-clone command is:

```powershell
python -m gridsight.verify_portfolio
```

Verified result:

- checked Power BI contract: passed;
- Ruff: passed;
- pytest: 92 public-clone tests passed;
- exit status: zero;
- evidence log: `logs/portfolio-check.log` (local and ignored by Git).

The local command `python -m gridsight.verify_portfolio
--with-local-artifacts` additionally passed seven tests that require ignored
generated outputs. The six live PostgreSQL tests had already passed after the
final reporting-mart implementation.

Generated-artifact and PostgreSQL tests remain opt-in through
`--with-local-artifacts` and `--with-postgres` because a clean public clone has
neither the intentionally unpublished processed files nor database credentials
and a preloaded service.

## Static repository audit

The final source-control review checked:

- local Markdown links and image paths;
- JSON contracts and Jupyter notebook syntax;
- `pyproject.toml` syntax;
- high-confidence private-key and provider-token patterns;
- accidental tracking of `.env`, raw data, processed data, models, and logs;
- source-controlled files larger than 2 MB;
- Python compilation and Git whitespace errors;
- portable Excel parameters plus native Power Query and PivotTable metadata.

No broken links, malformed checked artifacts, credential patterns, policy
violations, oversized files, Python syntax errors, or whitespace errors were
found.

## Recruiter review path

1. Scan the result table and skills evidence in the root README.
2. Review the Power BI and Excel screenshots without installing desktop tools.
3. Inspect `docs/architecture.md` for system and star-schema decisions.
4. Read `docs/final-forecast-evaluation.md` for the chronological test boundary.
5. Run the one-command verifier to reproduce the public contracts and tests.

## Remaining external settings

Repository visibility, About text, topics, social preview, and GitHub Actions
results are GitHub-hosted settings rather than source-controlled files. The
repository is public with its MIT license detected; topics, social preview, and
the corrected CI result remain to be confirmed after this fix is pushed.
