# Automation and continuous integration

## One-command verification

From an activated development environment at the repository root, run:

```powershell
python -m gridsight.verify_portfolio
```

The command validates the checked Power BI design artifacts, runs Ruff, and
executes the 92-test public-clone pytest suite. It stops on the first failure,
returns that process's non-zero exit code, prints the failing output, and writes
the same evidence to `logs/portfolio-check.log`.

The fast workflow uses only source-controlled contracts and public sample
artifacts. It does not require the ignored raw data, processed data, trained
model binary, Power BI Desktop, Excel, Docker, or a live database.

## Optional generated-artifact verification

After locally generating the ignored files under `data/processed/`, run:

```powershell
python -m gridsight.verify_portfolio --with-local-artifacts
```

This runs the normal public-clone workflow first and then the seven tests that
hash-gate the full forecast-prediction artifact and clean-data validation
summary. Keeping this boundary explicit prevents a fresh GitHub clone from
depending on files that the repository intentionally does not publish.

## Optional PostgreSQL verification

After starting the configured PostgreSQL service and loading `.env`, run:

```powershell
python -m gridsight.verify_portfolio --with-postgres
```

This runs the normal workflow first, then executes the six tests marked
`integration`. Those tests apply and reconcile the database contracts; they
are deliberately excluded from the public-clone and GitHub-hosted workflow.

Use a different log path when needed:

```powershell
python -m gridsight.verify_portfolio --log-file logs/manual-review.log
```

## GitHub Actions

`.github/workflows/portfolio-ci.yml` runs the same default command for pushes,
pull requests, and manual dispatches on Python 3.13. The job has read-only
repository permissions and installs both development and analysis tools so the
92 public-clone tests run without optional visualization skips.

The workflow proves that a clean public clone can validate the checked BI,
Excel, SQL, data-quality, and forecasting contracts without private data or
local desktop software. Live PostgreSQL reconciliation remains a documented
local gate because it requires an external service and credentials.

## Verified result

The final full local gate on 2026-09-08 passed Ruff, 92 public-clone tests, and
seven generated-artifact tests; six PostgreSQL integration tests remained
opt-in. The same command produced `logs/portfolio-check.log` and returned exit
code zero.
