"""One-command verification for the public GridSight portfolio."""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from gridsight.reporting.powerbi_contract import validate_written_powerbi_artifacts

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOG_PATH = PROJECT_ROOT / "logs" / "portfolio-check.log"
CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class VerificationStep:
    """One fail-fast subprocess in the public verification workflow."""

    name: str
    command: tuple[str, ...]


def build_steps(
    *,
    with_local_artifacts: bool = False,
    with_postgres: bool = False,
) -> tuple[VerificationStep, ...]:
    """Return the deterministic verification sequence."""
    steps = [
        VerificationStep(
            "Ruff",
            (sys.executable, "-m", "ruff", "check", "."),
        ),
        VerificationStep(
            "Public-clone tests",
            (sys.executable, "-m", "pytest"),
        ),
    ]
    if with_local_artifacts:
        steps.append(
            VerificationStep(
                "Local generated-artifact tests",
                (sys.executable, "-m", "pytest", "-m", "local_artifact"),
            )
        )
    if with_postgres:
        steps.append(
            VerificationStep(
                "PostgreSQL integration tests",
                (sys.executable, "-m", "pytest", "-m", "integration"),
            )
        )
    return tuple(steps)


def _logger(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("gridsight.portfolio_check")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    logger.propagate = False
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(console)
    logger.addHandler(file_handler)
    return logger


def verify_tracked_contracts() -> None:
    """Reject stale checked Power BI design artifacts before tooling runs."""
    validate_written_powerbi_artifacts()


def run_steps(
    steps: Sequence[VerificationStep],
    *,
    logger: logging.Logger,
    runner: CommandRunner = subprocess.run,
) -> int:
    """Run each subprocess once and stop immediately on a non-zero result."""
    for step in steps:
        logger.info("START | %s", step.name)
        try:
            result = runner(
                step.command,
                cwd=PROJECT_ROOT,
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
        except OSError as error:
            logger.error("FAIL | %s | could not start: %s", step.name, error)
            return 1
        output = (result.stdout or "").rstrip()
        if output:
            logger.info("OUTPUT | %s\n%s", step.name, output)
        if result.returncode != 0:
            logger.error(
                "FAIL | %s | exit code %s",
                step.name,
                result.returncode,
            )
            return result.returncode
        logger.info("PASS | %s", step.name)
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Verify checked portfolio contracts, lint, and tests with one "
            "fail-fast command."
        )
    )
    parser.add_argument(
        "--with-local-artifacts",
        action="store_true",
        help=(
            "also run tests that require ignored generated files under "
            "data/processed"
        ),
    )
    parser.add_argument(
        "--with-postgres",
        action="store_true",
        help="also run tests marked integration against the configured database",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=DEFAULT_LOG_PATH,
        help="verification log path (default: logs/portfolio-check.log)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the complete portfolio verification workflow."""
    args = _parser().parse_args(argv)
    log_path = args.log_file
    if not log_path.is_absolute():
        log_path = PROJECT_ROOT / log_path
    logger = _logger(log_path)
    logger.info("GridSight portfolio verification started")
    try:
        logger.info("START | Checked Power BI contracts")
        verify_tracked_contracts()
        logger.info("PASS | Checked Power BI contracts")
    except (KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
        logger.error("FAIL | Checked Power BI contracts | %s", error)
        logger.info("Log: %s", log_path)
        return 1

    result = run_steps(
        build_steps(
            with_local_artifacts=args.with_local_artifacts,
            with_postgres=args.with_postgres,
        ),
        logger=logger,
    )
    if result:
        logger.info("GridSight portfolio verification FAILED")
        logger.info("Log: %s", log_path)
        return result
    logger.info("GridSight portfolio verification PASSED")
    logger.info("Log: %s", log_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
