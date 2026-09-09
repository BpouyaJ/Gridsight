"""Fast checks for the public-safe portfolio ZIP builder."""

from __future__ import annotations

import io
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from gridsight.package_portfolio import (
    ARCHIVE_ROOT,
    MANIFEST_NAME,
    is_forbidden_path,
    validate_portfolio_archive,
    validate_public_content,
    write_portfolio_archive,
)


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        ".venv/pyvenv.cfg",
        ".git/config",
        "data/raw/private.csv",
        "data/processed/final_forecast_predictions.csv",
        "logs/portfolio-check.log",
        "models/final.joblib",
        "src/gridsight/__pycache__/module.pyc",
        "private-key.pem",
    ],
)
def test_sensitive_or_generated_paths_are_forbidden(path: str) -> None:
    assert is_forbidden_path(path)


@pytest.mark.parametrize(
    "path",
    [
        ".env.example",
        "README.md",
        "data/samples/monthly_energy_sample.csv",
        "powerbi/GridSight.pbip",
    ],
)
def test_public_project_paths_are_allowed(path: str) -> None:
    assert not is_forbidden_path(path)


def test_portfolio_archive_is_deterministic_and_manifested(tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / "docs").mkdir(parents=True)
    (project / "README.md").write_text("GridSight\n", encoding="utf-8")
    (project / "docs" / "note.md").write_text("Evidence\n", encoding="utf-8")
    paths = (Path("README.md"), Path("docs/note.md"))
    first = write_portfolio_archive(project, paths, tmp_path / "first.zip")
    second = write_portfolio_archive(project, paths, tmp_path / "second.zip")

    assert first.read_bytes() == second.read_bytes()
    names = validate_portfolio_archive(first)
    assert names == (
        f"{ARCHIVE_ROOT}/README.md",
        f"{ARCHIVE_ROOT}/docs/note.md",
        f"{ARCHIVE_ROOT}/{MANIFEST_NAME}",
    )
    with ZipFile(first) as archive:
        manifest = archive.read(f"{ARCHIVE_ROOT}/{MANIFEST_NAME}").decode()
    assert "schema_version: 1" in manifest
    assert "file_count: 2" in manifest
    assert "README.md" in manifest
    assert "docs/note.md" in manifest


def test_public_content_rejects_private_paths_and_tokens() -> None:
    private_path = "C:" + "\\Users\\" + "someone\\project\\file.csv"
    access_key = "AKIA" + "A" * 16

    with pytest.raises(ValueError, match="Windows user-profile path"):
        validate_public_content("report.txt", private_path.encode())
    with pytest.raises(ValueError, match="AWS access key"):
        validate_public_content("report.txt", access_key.encode())


def test_public_content_inspects_nested_office_packages() -> None:
    private_path = "C:" + "\\Users\\" + "someone\\GridSight\\excel\\"
    stream = io.BytesIO()
    with ZipFile(stream, "w", compression=ZIP_DEFLATED) as workbook:
        workbook.writestr("xl/workbook.xml", private_path)

    with pytest.raises(ValueError, match="Windows user-profile path"):
        validate_public_content("analyst-pack.xlsx", stream.getvalue())


def test_portfolio_archive_rejects_sensitive_inputs(tmp_path: Path) -> None:
    secret = tmp_path / ".env"
    secret.write_text("POSTGRES_PASSWORD=secret\n", encoding="utf-8")

    with pytest.raises(ValueError, match="unsafe path"):
        write_portfolio_archive(
            tmp_path,
            (Path(".env"),),
            tmp_path / "unsafe.zip",
        )
