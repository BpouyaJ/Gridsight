# Checked portfolio samples

These eight compact CSV files are deterministic extracts from GridSight's
verified reporting views, clean-data validation summary, and immutable source
manifest. They support Power BI, Excel/Power Query, automated tests, and GitHub
portfolio review without publishing the full raw or processed datasets.

Generate and verify the complete bundle from the project root with PostgreSQL
running and Step 7.2 loaded:

```powershell
python -m gridsight.reporting.build_samples
```

Exact filters, grains, keys, columns, counts, consumers, source hashes, and
individual sample hashes are recorded in:

- `reports/reporting_mart_contract.json`;
- `reports/sample_extract_manifest.json`.

All market-data-derived samples use the required attribution:

> Bundesnetzagentur | SMARD.de

The files are illustrative checked extracts, not full datasets and not an
operational data feed.
