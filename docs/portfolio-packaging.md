# Safe portfolio packaging

## Purpose

Do not share a ZIP made by compressing the local project folder. A local folder
can contain `.env`, `.git`, `.venv`, ignored raw/processed data, model outputs,
logs, caches, and other machine-specific files even though GitHub is clean.

Build the recruiter-safe package from the repository root instead:

```powershell
python -m gridsight.package_portfolio
```

The command writes the ignored file `dist/GridSight-portfolio.zip` and prints
its SHA-256. It enumerates tracked plus non-ignored Git-visible files, sorts
them deterministically, fixes ZIP metadata, and includes
`PACKAGE_MANIFEST.txt` with a SHA-256 for every packaged source file.

## Safety gates

The build fails rather than packaging:

- `.env`, `.git`, virtual environments, caches, logs, models, or database
  volumes;
- any file below `data/raw/` or `data/processed/`;
- private-key filenames or high-confidence key/token content;
- Windows or Unix user-profile paths in text content;
- the same private paths or credentials hidden inside nested ZIP/OOXML files,
  including the Excel workbook.

`.env.example`, checked `data/samples/` evidence, PBIP/PBIR/TMDL sources, the
Excel analyst pack, screenshots, tests, and documentation remain eligible.

## Review before sharing

Run the normal verifier first, then build the package:

```powershell
python -m gridsight.verify_portfolio --with-local-artifacts
python -m gridsight.package_portfolio
```

Share only `dist/GridSight-portfolio.zip`. Any older ZIP created directly from
the development folder is a private local backup, not a portfolio artifact,
and should be deleted or retained under an unmistakable do-not-share name.
