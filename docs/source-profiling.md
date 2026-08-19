# Reproducible SMARD source profiling

GridSight profiles all six immutable raw snapshots with tested package code.
The command and notebook are read-only: they never edit `data/raw/` or write a
processed dataset.

## Automated command

From the repository root with `.venv` activated, run:

```powershell
python -m gridsight.ingestion.profile_snapshots
```

The command checks:

- all six approved export IDs have one manifest record and one raw file;
- every raw SHA-256 matches its tracked manifest value;
- observed row counts match the real elapsed hours in each requested period;
- the two snapshots in each category have identical ordered schemas;
- the exact consumption and DE/LU price targets exist and are fully numeric;
- generation contains 12 measures and only the documented `-` source marker;
- repeated Europe/Berlin local-hour groups match the expected autumn daylight-
  saving transitions.

The command prints `Source profiling: OK` and returns exit code zero only when
all checks pass. It deliberately permits negative DE/LU prices and the approved
Nuclear `-` markers.

## Notebook

Open `notebooks/01_smard_source_profile.ipynb` from the repository root and run
all cells. The notebook calls the same tested functions, asserts that the
automated contract passes, and displays:

- one structural and target-value summary row per snapshot;
- category-level schema compatibility;
- every measure column containing non-numeric source markers.

Notebook outputs are intentionally not precomputed. A reviewer with the raw
snapshots can reproduce the profile; the tracked factual results remain in
`docs/initial-source-profile.md` because full raw data are excluded from Git.

Launch JupyterLab when an interactive run is useful:

```powershell
python -m jupyter lab
```
