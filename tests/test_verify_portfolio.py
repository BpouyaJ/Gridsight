"""Fast tests for the one-command portfolio verification runner."""

from __future__ import annotations

import logging
import subprocess
import sys

from gridsight.verify_portfolio import (
    VerificationStep,
    build_steps,
    run_steps,
)


def _silent_logger() -> logging.Logger:
    logger = logging.getLogger("tests.gridsight.portfolio_check")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    logger.propagate = False
    return logger


def test_default_sequence_runs_lint_then_the_public_clone_suite() -> None:
    steps = build_steps()

    assert [step.name for step in steps] == ["Ruff", "Public-clone tests"]
    assert steps[0].command == (
        sys.executable,
        "-m",
        "ruff",
        "check",
        ".",
    )
    assert steps[1].command == (sys.executable, "-m", "pytest")


def test_optional_flags_add_the_explicit_local_suites() -> None:
    artifact_steps = build_steps(with_local_artifacts=True)
    postgres_steps = build_steps(with_postgres=True)

    assert artifact_steps[-1].name == "Local generated-artifact tests"
    assert artifact_steps[-1].command == (
        sys.executable,
        "-m",
        "pytest",
        "-m",
        "local_artifact",
    )
    assert postgres_steps[-1].name == "PostgreSQL integration tests"
    assert postgres_steps[-1].command == (
        sys.executable,
        "-m",
        "pytest",
        "-m",
        "integration",
    )


def test_runner_stops_at_the_first_failed_step() -> None:
    commands: list[tuple[str, ...]] = []

    def fake_runner(command: tuple[str, ...], **_: object):
        commands.append(command)
        return subprocess.CompletedProcess(
            command,
            returncode=7 if len(commands) == 2 else 0,
            stdout="test output",
        )

    steps = (
        VerificationStep("first", ("one",)),
        VerificationStep("second", ("two",)),
        VerificationStep("never", ("three",)),
    )

    assert run_steps(steps, logger=_silent_logger(), runner=fake_runner) == 7
    assert commands == [("one",), ("two",)]


def test_runner_reports_process_start_failures() -> None:
    def missing_runner(*_: object, **__: object):
        raise FileNotFoundError("missing executable")

    result = run_steps(
        (VerificationStep("missing", ("missing",)),),
        logger=_silent_logger(),
        runner=missing_runner,
    )

    assert result == 1
