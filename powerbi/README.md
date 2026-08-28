# GridSight Power BI workspace

This folder holds the source-controlled Power BI design and, beginning in Step
8.2, the project files created by Power BI Desktop.

## Current Step 8.1 assets

- `dax/measures.dax`: 24 tested, copy-ready DAX measures.
- `page-wireframes.md`: the five report pages, questions, visuals, and fields.
- `reports/powerbi_semantic_model_contract.json`: the machine-readable model
  contract generated from Python.
- `docs/power-bi-semantic-model.md`: the relationship, table, unit, and Desktop
  implementation guide.

Regenerate and validate the design from the repository root:

```powershell
python -m gridsight.reporting.build_powerbi_contract
```

## Step boundary

Step 8.1 does not hand-author a `.pbix`, `.pbip`, PBIR report definition, or
TMDL semantic model. In Step 8.2, Power BI Desktop will create those files from
its supported **Save as Power BI Project** workflow. We will then compare the
Desktop model to the frozen JSON and DAX contracts before building visuals.

Power BI Desktop projects and the enhanced PBIR report format are currently
documented by Microsoft as preview features. Desktop-generated files are used
so their schemas and local metadata are valid for the installed Desktop
version. Local `.pbi` cache and settings files must remain excluded from Git.

Official references:

- [Power BI Desktop projects](https://learn.microsoft.com/power-bi/developer/projects/projects-overview)
- [Power BI project report folder and PBIR](https://learn.microsoft.com/power-bi/developer/projects/projects-report)
- [TMDL view in Power BI Desktop](https://learn.microsoft.com/power-bi/transform-model/desktop-tmdl-view)
- [Star-schema guidance](https://learn.microsoft.com/power-bi/guidance/star-schema)

## Portfolio limits

The report is a local portfolio deliverable, not a deployed production BI
service. Do not commit credentials, local caches, autosaves, database extracts
outside `data/samples/`, or workspace-specific connection secrets.
