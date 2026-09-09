"""Build a deterministic, public-safe GridSight source package."""

from __future__ import annotations

import argparse
import hashlib
import io
import re
import subprocess
from collections.abc import Iterable, Sequence
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo, is_zipfile

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = PROJECT_ROOT / "dist" / "GridSight-portfolio.zip"
ARCHIVE_ROOT = "GridSight"
MANIFEST_NAME = "PACKAGE_MANIFEST.txt"

FORBIDDEN_DIRECTORY_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "dist",
    "htmlcov",
    "logs",
    "models",
    "postgres_data",
    "venv",
}
FORBIDDEN_DATA_DIRECTORIES = {("data", "processed"), ("data", "raw")}
ALLOWED_ENV_FILE = ".env.example"
MAX_NESTED_ARCHIVE_BYTES = 50 * 1024 * 1024
SENSITIVE_CONTENT_PATTERNS = (
    (
        "Windows user-profile path",
        re.compile(r"[A-Za-z]:\\Users\\[^\\/\r\n]+", re.IGNORECASE),
    ),
    ("Unix user-home path", re.compile(r"/(?:home|Users)/[^/\s]+/")),
    ("private-key material", re.compile(r"-{5}BEGIN [A-Z0-9 ]*PRIVATE KEY-{5}")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{32,}\b")),
)


def _parts(relative_path: str | Path) -> tuple[str, ...]:
    normalized = str(relative_path).replace("\\", "/")
    path = PurePosixPath(normalized)
    parts = tuple(part for part in path.parts if part not in ("", "."))
    if path.is_absolute() or not parts or ".." in parts:
        raise ValueError(f"Unsafe package path: {relative_path}")
    return parts


def is_forbidden_path(relative_path: str | Path) -> bool:
    """Return whether a repository-relative path is unsafe to publish."""
    parts = _parts(relative_path)
    lowered = tuple(part.casefold() for part in parts)
    filename = lowered[-1]
    if any(part in FORBIDDEN_DIRECTORY_NAMES for part in lowered[:-1]):
        return True
    if len(lowered) >= 2 and lowered[:2] in FORBIDDEN_DATA_DIRECTORIES:
        return True
    if filename.startswith(".env") and filename != ALLOWED_ENV_FILE:
        return True
    if filename in {".coverage", "id_ed25519", "id_rsa"}:
        return True
    return filename.endswith((".key", ".pem", ".pyc", ".pyo"))


def _scan_text(label: str, content: bytes) -> None:
    text = content.decode("utf-8", errors="ignore")
    for description, pattern in SENSITIVE_CONTENT_PATTERNS:
        if pattern.search(text):
            raise ValueError(f"Unsafe {description} found in {label}")


def validate_public_content(relative_path: str | Path, content: bytes) -> None:
    """Reject high-confidence credentials and local paths, including in OOXML."""
    label = str(relative_path).replace("\\", "/")
    _scan_text(label, content)
    stream = io.BytesIO(content)
    if not is_zipfile(stream):
        return
    stream.seek(0)
    with ZipFile(stream) as nested:
        total_size = sum(info.file_size for info in nested.infolist())
        if total_size > MAX_NESTED_ARCHIVE_BYTES:
            raise ValueError(f"Nested archive is too large to inspect safely: {label}")
        for info in nested.infolist():
            if info.is_dir():
                continue
            _scan_text(f"{label}!/{info.filename}", nested.read(info))


def git_visible_files(project_root: Path = PROJECT_ROOT) -> tuple[Path, ...]:
    """List tracked and non-ignored untracked files in stable Git order."""
    try:
        result = subprocess.run(
            (
                "git",
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
            ),
            cwd=project_root,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        message = "Could not enumerate the Git-visible project files"
        raise RuntimeError(message) from error

    paths = []
    for raw_path in result.stdout.split(b"\0"):
        if not raw_path:
            continue
        relative_path = Path(raw_path.decode("utf-8"))
        source = project_root / relative_path
        if not source.exists():
            continue
        if not source.is_file() or source.is_symlink():
            raise ValueError(f"Package input must be a regular file: {relative_path}")
        if is_forbidden_path(relative_path):
            if relative_path.as_posix() in {
                "data/processed/.gitkeep",
                "data/raw/.gitkeep",
            }:
                continue
            raise ValueError(f"Refusing to package unsafe path: {relative_path}")
        paths.append(relative_path)
    return tuple(sorted(set(paths), key=lambda path: path.as_posix()))


def _zip_info(name: str) -> ZipInfo:
    info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def _manifest(files: Iterable[tuple[str, bytes]]) -> bytes:
    records = list(files)
    lines = [
        "GridSight public portfolio package",
        "schema_version: 1",
        f"file_count: {len(records)}",
        "",
    ]
    lines.extend(
        f"{hashlib.sha256(content).hexdigest()}  {path}"
        for path, content in records
    )
    return ("\n".join(lines) + "\n").encode("utf-8")


def write_portfolio_archive(
    project_root: Path,
    relative_paths: Sequence[Path],
    destination: Path,
) -> Path:
    """Write one deterministic ZIP after validating every selected member."""
    records: list[tuple[str, bytes]] = []
    for relative_path in sorted(
        relative_paths,
        key=lambda path: path.as_posix(),
    ):
        if is_forbidden_path(relative_path):
            raise ValueError(f"Refusing to package unsafe path: {relative_path}")
        source = project_root / relative_path
        if not source.is_file() or source.is_symlink():
            raise ValueError(f"Package input must be a regular file: {relative_path}")
        content = source.read_bytes()
        validate_public_content(relative_path, content)
        records.append((relative_path.as_posix(), content))

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    temporary.unlink(missing_ok=True)
    try:
        with ZipFile(
            temporary,
            "w",
            compression=ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            for relative_path, content in records:
                name = f"{ARCHIVE_ROOT}/{relative_path}"
                archive.writestr(_zip_info(name), content)
            manifest_name = f"{ARCHIVE_ROOT}/{MANIFEST_NAME}"
            archive.writestr(_zip_info(manifest_name), _manifest(records))
        validate_portfolio_archive(temporary)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def validate_portfolio_archive(path: Path) -> tuple[str, ...]:
    """Reject corrupt, duplicate, unrooted, or sensitive ZIP members."""
    with ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("Portfolio archive is corrupt")
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Portfolio archive contains duplicate members")
        prefix = f"{ARCHIVE_ROOT}/"
        for name in names:
            if not name.startswith(prefix):
                raise ValueError(
                    f"Portfolio archive member is outside {prefix}: {name}"
                )
            relative = name.removeprefix(prefix)
            if relative != MANIFEST_NAME and is_forbidden_path(relative):
                raise ValueError(f"Portfolio archive contains unsafe member: {name}")
            if relative != MANIFEST_NAME:
                validate_public_content(relative, archive.read(name))
    return tuple(names)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a deterministic ZIP containing public-safe GridSight files."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="destination ZIP (default: dist/GridSight-portfolio.zip)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Build and report the validated public portfolio archive."""
    args = _parser().parse_args(argv)
    destination = args.output
    if not destination.is_absolute():
        destination = PROJECT_ROOT / destination
    files = git_visible_files(PROJECT_ROOT)
    archive = write_portfolio_archive(PROJECT_ROOT, files, destination)
    print(f"Portfolio package: {archive}")
    print(f"Files: {len(files)} + {MANIFEST_NAME}")
    print(f"SHA-256: {hashlib.sha256(archive.read_bytes()).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
