"""CLI for reproducible profiling of all registered SMARD snapshots."""

from pathlib import Path

from gridsight.ingestion.source_profiler import (
    profile_registered_snapshots,
    validate_source_profiles,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "smard_exports.json"
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_MANIFEST = (
    PROJECT_ROOT / "data" / "manifests" / "smard_source_manifest.csv"
)


def _format_range(minimum: float | None, maximum: float | None) -> str:
    if minimum is None or maximum is None:
        return "n/a"
    return f"{minimum:.2f} to {maximum:.2f}"


def main() -> int:
    """Profile registered snapshots and enforce the Phase 2 source contract."""
    try:
        report = profile_registered_snapshots(
            DEFAULT_CONFIG,
            DEFAULT_MANIFEST,
            DEFAULT_RAW_DIR,
        )
        violations = validate_source_profiles(report)
    except (OSError, ValueError) as error:
        print(f"Source profiling: FAILED ({error})")
        return 1

    print(f"Registered snapshots profiled: {len(report.snapshots)}")
    for profile in report.snapshots:
        target = profile.target_profile
        if target is None:
            marker_label = "measure_markers"
            marker_count = sum(
                measure.marker_count for measure in profile.measures
            )
        else:
            marker_label = "target_markers"
            marker_count = target.marker_count
        summary = (
            f"{profile.export_id}: rows={profile.row_count}, "
            f"columns={profile.column_count}, {marker_label}={marker_count}, "
            f"sha_match={profile.sha_matches_manifest}"
        )
        if target is not None:
            summary += (
                f", target_range={_format_range(target.minimum, target.maximum)}, "
                f"target_negative={target.negative_count}"
            )
        print(summary)

    for category, compatible in report.schema_compatible.items():
        print(f"Schema compatible [{category}]: {compatible}")

    if violations:
        print("Source profiling: FAILED")
        for violation in violations:
            print(f"- {violation}")
        return 1

    print("Source profiling: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
