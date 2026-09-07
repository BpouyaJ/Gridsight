# GridSight Power BI report

GridSight includes a source-controlled Power BI Desktop project built with the
PBIP, PBIR, and TMDL formats. Open `GridSight.pbip` from this folder's parent
directory to inspect the semantic model and five-page report.

## Delivered report

- 15 Import-mode tables
- 12 active one-to-many, single-direction relationships
- one declared Europe/Berlin date table
- 30 explicit DAX measures
- 5 report pages and 21 visuals
- checked sample inputs for a public, compact portfolio review

The pages are Executive Overview, Load & Renewables, Price Analysis, Forecast
Performance, and Data Quality. Screenshots and concise findings are documented
in `docs/power-bi-report.md`.

## Rebuild and validation

The checked design contract remains reproducible from the repository root:

```powershell
python -m gridsight.reporting.build_powerbi_contract
python -m pytest tests/test_powerbi_contract.py -v
```

Power BI Desktop owns the generated PBIP/PBIR/TMDL serialization. The project
is a local portfolio deliverable, not a deployed production BI service. Do not
commit credentials, local caches, autosaves, database extracts outside
`data/samples/`, or workspace-specific connection secrets.

## References

- [Power BI Desktop projects](https://learn.microsoft.com/power-bi/developer/projects/projects-overview)
- [PBIR report folders](https://learn.microsoft.com/power-bi/developer/projects/projects-report)
- [TMDL view](https://learn.microsoft.com/power-bi/transform-model/desktop-tmdl-view)
- [Star-schema guidance](https://learn.microsoft.com/power-bi/guidance/star-schema)
