# Development setup

GridSight uses Python 3.13 and a project-local virtual environment. The
environment keeps this project's packages separate from system Python and
other projects.

## Windows PowerShell

From the repository root, create the environment once:

```powershell
python -m venv .venv
```

If `python` is not on `PATH`, use the installed Python 3.13 interpreter:

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" -m venv .venv
```

Activate the environment whenever opening a new terminal:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Install the package and all development tools:

```powershell
python -m pip install --upgrade pip
python -m pip install -e ".[analysis,dev]"
```

The editable install means changes under `src/gridsight/` are immediately
available without reinstalling the package.

## Verification commands

```powershell
python --version
python -c "import gridsight; print(gridsight.__version__)"
python -m pytest
python -m ruff check .
```

Python should resolve to `.venv\Scripts\python.exe`. The `.venv` directory is
local-only and must not be committed.

## Leave the environment

```powershell
deactivate
```
