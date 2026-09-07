"""Fast checks for recruiter-facing portfolio documentation."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
ARCHITECTURE = ROOT / "docs" / "architecture.md"
LICENSE = ROOT / "LICENSE"


def test_readme_relative_links_and_images_resolve() -> None:
    text = README.read_text(encoding="utf-8")
    targets = re.findall(r"!?\[[^]]*]\(([^)]+)\)", text)
    local_targets = [
        target
        for target in targets
        if not target.startswith(("http://", "https://", "#", "mailto:"))
    ]

    missing = [target for target in local_targets if not (ROOT / target).exists()]
    assert missing == []


def test_readme_results_match_checked_evidence() -> None:
    readme = README.read_text(encoding="utf-8")
    kpis = json.loads((ROOT / "reports" / "kpi_snapshot.json").read_text())
    evaluation = json.loads(
        (ROOT / "reports" / "final_evaluation_snapshot.json").read_text()
    )
    headline = kpis["headline_kpis"]
    model = evaluation["test_evaluation"]["model"]["overall"]
    comparison = evaluation["test_evaluation"]["comparison"]

    assert f"{headline['observed_hour_count']:,} UTC hours" in readme
    assert f"{headline['total_grid_load_twh']:,.3f} TWh" in readme
    assert (
        f"{headline['renewable_share_of_reported_generation_percent']:.2f}%"
        in readme
    )
    assert f"{model['mae_mw']:,.3f} MW" in readme
    assert f"{model['mape_percent']:.3f}%" in readme
    improvement = comparison["model_improvement_over_weekly_percent"]
    assert f"{improvement:.3f}%" in readme


def test_architecture_and_license_are_explicit() -> None:
    architecture = ARCHITECTURE.read_text(encoding="utf-8")
    license_text = LICENSE.read_text(encoding="utf-8")

    assert architecture.count("```mermaid") == 2
    assert "flowchart TB" in architecture
    assert "erDiagram" in architecture
    assert "FACT_LOAD_FORECAST_EVALUATION" in architecture
    assert license_text.startswith("MIT License\n")
    assert "Copyright (c) 2026 Mohammad Pouya Borji" in license_text


def test_readme_no_longer_presents_completed_work_as_planned() -> None:
    text = README.read_text(encoding="utf-8").lower()
    stale_phrases = (
        "will combine",
        "planned architecture",
        "planned technology stack",
        "under active development",
    )

    assert all(phrase not in text for phrase in stale_phrases)
