"""CLI for the final Phase 3 clean-data validation gate."""

import json
from pathlib import Path
from typing import Any

from gridsight.ingestion.snapshot_registry import sha256_file
from gridsight.transformation.consumption import (
    load_consumption_dataset,
    write_consumption_csv,
)
from gridsight.transformation.generation import (
    load_generation_dataset,
    write_generation_csv,
)
from gridsight.transformation.price import load_price_dataset, write_price_csv
from gridsight.validation.clean_data import (
    STATUS_FAILED,
    STATUS_PASSED,
    summarize_clean_datasets,
    validate_clean_datasets,
    write_validation_artifacts,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "smard_exports.json"
DEFAULT_MANIFEST = (
    PROJECT_ROOT / "data" / "manifests" / "smard_source_manifest.csv"
)
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_PATHS = {
    "consumption": PROCESSED_DIR / "actual_consumption_hourly.csv",
    "generation": PROCESSED_DIR / "actual_generation_hourly.csv",
    "price": PROCESSED_DIR / "day_ahead_price_hourly.csv",
}
DEFAULT_ISSUES = PROCESSED_DIR / "validation_issues.csv"
DEFAULT_SUMMARY = PROCESSED_DIR / "validation_summary.json"
DEFAULT_RUN_STATUS = PROCESSED_DIR / "validation_run_status.json"


def _relative(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def write_validation_run_status(
    status_path: Path,
    *,
    status: str,
    summary_sha256: str | None = None,
    failure: dict[str, Any] | None = None,
) -> None:
    """Atomically expose the outcome of the latest attempted validation run."""
    payload = {
        "schema_version": 1,
        "status": status,
        "summary_sha256": summary_sha256,
        "failure": failure,
    }
    status_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = status_path.with_name(f".{status_path.name}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(status_path)
    finally:
        temporary.unlink(missing_ok=True)


def _record_exception_failure(error: BaseException) -> None:
    try:
        write_validation_run_status(
            DEFAULT_RUN_STATUS,
            status=STATUS_FAILED,
            failure={
                "kind": "exception",
                "type": type(error).__name__,
                "message": str(error),
            },
        )
    except OSError as status_error:
        print(f"Validation run status could not be written ({status_error})")


def main() -> int:
    """Rebuild, validate, and publish the complete clean-data layer."""
    try:
        write_validation_run_status(DEFAULT_RUN_STATUS, status="running")
        consumption = load_consumption_dataset(
            DEFAULT_CONFIG,
            DEFAULT_MANIFEST,
            DEFAULT_RAW_DIR,
        )
        generation = load_generation_dataset(
            DEFAULT_CONFIG,
            DEFAULT_MANIFEST,
            DEFAULT_RAW_DIR,
        )
        price = load_price_dataset(
            DEFAULT_CONFIG,
            DEFAULT_MANIFEST,
            DEFAULT_RAW_DIR,
        )
        report = validate_clean_datasets(consumption, generation, price)
        if report.status != STATUS_PASSED:
            empty_outputs = {name: {} for name in OUTPUT_PATHS}
            datasets = summarize_clean_datasets(
                consumption,
                generation,
                price,
                empty_outputs,
            )
            write_validation_artifacts(
                report,
                datasets,
                DEFAULT_ISSUES,
                DEFAULT_SUMMARY,
            )
            write_validation_run_status(
                DEFAULT_RUN_STATUS,
                status=STATUS_FAILED,
                summary_sha256=sha256_file(DEFAULT_SUMMARY),
                failure={
                    "kind": "validation",
                    "issue_count": len(report.issues),
                },
            )
            print("Clean-data validation: FAILED")
            print(f"Issues: {len(report.issues)}")
            print(f"Issues output: {_relative(DEFAULT_ISSUES)}")
            print(f"Summary output: {_relative(DEFAULT_SUMMARY)}")
            return 1

        write_consumption_csv(consumption, OUTPUT_PATHS["consumption"])
        write_generation_csv(generation, OUTPUT_PATHS["generation"])
        write_price_csv(price, OUTPUT_PATHS["price"])
        output_metadata = {
            name: {
                "output": _relative(path),
                "sha256": sha256_file(path),
            }
            for name, path in OUTPUT_PATHS.items()
        }
        datasets = summarize_clean_datasets(
            consumption,
            generation,
            price,
            output_metadata,
        )
        write_validation_artifacts(
            report,
            datasets,
            DEFAULT_ISSUES,
            DEFAULT_SUMMARY,
        )
        write_validation_run_status(
            DEFAULT_RUN_STATUS,
            status=STATUS_PASSED,
            summary_sha256=sha256_file(DEFAULT_SUMMARY),
        )
    except (OSError, TypeError, ValueError) as error:
        _record_exception_failure(error)
        print(f"Clean-data validation: FAILED ({error})")
        return 1

    passed = sum(check.status == STATUS_PASSED for check in report.checks)
    print("Clean-data validation: OK")
    print(f"Checks: {passed} passed, 0 failed")
    print("Issues: 0")
    for name in ("consumption", "generation", "price"):
        details = datasets[name]
        print(
            f"{name}: rows={details['rows']}, "
            f"intervals={details['intervals']}, sha256={details['sha256']}"
        )
    print(f"Issues output: {_relative(DEFAULT_ISSUES)}")
    print(f"Issues SHA-256: {sha256_file(DEFAULT_ISSUES)}")
    print(f"Summary output: {_relative(DEFAULT_SUMMARY)}")
    print(f"Summary SHA-256: {sha256_file(DEFAULT_SUMMARY)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
