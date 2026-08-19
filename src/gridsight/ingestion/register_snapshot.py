"""CLI for listing and registering approved SMARD source snapshots."""

import argparse
from pathlib import Path

from gridsight.ingestion.snapshot_registry import (
    ExportDefinition,
    load_export_definitions,
    register_snapshot,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "smard_exports.json"
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_MANIFEST = (
    PROJECT_ROOT / "data" / "manifests" / "smard_source_manifest.csv"
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Register immutable SMARD CSV snapshots with source lineage."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="List approved exports and SMARD filters.")

    register_parser = subparsers.add_parser(
        "register",
        help="Copy one CSV to data/raw and append its manifest record.",
    )
    register_parser.add_argument("--export-id", required=True)
    register_parser.add_argument("--file", required=True, type=Path)
    register_parser.add_argument("--notes", default="")
    return parser


def _print_export(definition: ExportDefinition) -> None:
    print(definition.export_id)
    print(f"  Period: {definition.period_start} to {definition.period_end}")
    print(f"  Geography: {definition.source_geography}")
    print(f"  Output: {definition.local_filename}")
    for name, value in definition.smard_filters.items():
        label = name.replace("_", " ").title()
        print(f"  {label}: {value}")


def main() -> int:
    """Run the snapshot registry command-line interface."""
    parser = _build_parser()
    arguments = parser.parse_args()

    try:
        definitions = load_export_definitions(DEFAULT_CONFIG)

        if arguments.command == "list":
            for definition in definitions.values():
                _print_export(definition)
            return 0

        definition = definitions.get(arguments.export_id)
        if definition is None:
            available = ", ".join(definitions)
            raise ValueError(
                f"Unknown export ID {arguments.export_id!r}. Available: {available}"
            )

        result = register_snapshot(
            source_file=arguments.file,
            definition=definition,
            raw_dir=DEFAULT_RAW_DIR,
            manifest_path=DEFAULT_MANIFEST,
            notes=arguments.notes,
        )
    except (OSError, ValueError) as error:
        print(f"Snapshot registration: FAILED ({error})")
        return 1

    if result.manifest_appended:
        print("Snapshot registration: OK")
    else:
        print("Snapshot already registered: no manifest change")
    print(f"Raw file: data/raw/{result.record.local_filename}")
    print(f"SHA-256: {result.record.sha256}")
    print(f"Manifest: data/manifests/{DEFAULT_MANIFEST.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
