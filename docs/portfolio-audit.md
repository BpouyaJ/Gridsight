# Final portfolio audit

## Outcome

GridSight completed its approved Energy Analytics, Business Intelligence, data,
and forecasting scope on 2026-09-08 and completed an independent-review
hardening pass on 2026-09-09. The repository can be reviewed from a clean public
clone without local raw data, Power BI Desktop, Excel, Docker, or PostgreSQL;
full desktop refreshes remain explicit local workflows.

## Automated gate

The public-clone command is:

```powershell
python -m gridsight.verify_portfolio
```

Verified result:

- checked Power BI contract: passed;
- Ruff: passed;
- pytest: 117 public-clone tests passed;
- exit status: zero;
- evidence log: `logs/portfolio-check.log` (local and ignored by Git).

The final local command `python -m gridsight.verify_portfolio
--with-local-artifacts --with-postgres` passed on Windows and Python 3.13.5. It
included the 117 public-clone tests, seven tests requiring ignored generated
outputs, and six live PostgreSQL integration tests.

GitHub Actions passed the earlier 92-test public-clone gate on Ubuntu with
Python 3.13 at commit `11c0675`, confirming that the verification path is
portable beyond Windows. The expanded hosted gate is pending the hardening
push.

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
- Power BI parameterization with no user-specific TMDL paths;
- Excel formula lineage, valid `yyyy-MM` labels, recalculation metadata, and
  preserved native Power Query/PivotTable/chart parts;
- sensitive filenames, high-confidence credentials, user-profile paths, and
  the same content inside nested ZIP/OOXML files;
- deterministic safe-package membership and per-file SHA-256 evidence.

The hardening pass corrected the earlier Excel stale-refresh dependency, two
Power BI user-specific paths, six hardcoded database-source expressions,
validation status ambiguity, a loose model-library range, and unsafe manual ZIP
workflow. The repeated static gates found no remaining broken links, malformed
checked artifacts, credential patterns, policy violations, oversized files,
Python syntax errors, or whitespace errors.

## Recruiter review path

1. Scan the result table and skills evidence in the root README.
2. Review the Power BI and Excel screenshots without installing desktop tools.
3. Inspect `docs/architecture.md` for system and star-schema decisions.
4. Read `docs/final-forecast-evaluation.md` for the chronological test boundary.
5. Run the one-command verifier to reproduce the public contracts and tests.

## Final hosted gate

The repository is public with its MIT license, About text, topics, social
preview, and profile pin configured. The final native checks opened and saved
the PBIP with its three explicit parameters and refreshed the Excel query and
PivotTable. The workbook retained 48 monthly rows, a 1,872.00 TWh PivotTable
grand total, and `PASS` for every reconciliation row. The post-save structural
audit removed local path metadata, restored full recalculation, and preserved
the native query, PivotTable/cache, three tables, and two charts. The final
Python 3.13 verifier then passed every local gate. Only the hardening push and
expanded GitHub Actions confirmation remain.

Only `dist/GridSight-portfolio.zip`, produced by
`python -m gridsight.package_portfolio`, is approved for direct sharing. An
older ZIP made by compressing the development folder can contain ignored
secrets, Git history, environments, and private data and must not be shared.
