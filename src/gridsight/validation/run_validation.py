"""CLI for the final Phase 3 clean-data validation gate."""

from pathlib import Path

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


def _relative(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def main() -> int:
    """Rebuild, validate, and publish the complete clean-data layer."""
    try:
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
    except (OSError, TypeError, ValueError) as error:
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
