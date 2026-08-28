"""CLI for the frozen GridSight Power BI design contract."""

from __future__ import annotations

from gridsight.reporting.powerbi_contract import (
    DEFAULT_DAX_CATALOGUE,
    DEFAULT_POWERBI_CONTRACT,
    build_powerbi_contract,
    sha256_file,
    validate_written_powerbi_artifacts,
    write_powerbi_artifacts,
)


def main() -> int:
    """Build, validate, and summarize the Step 8.1 artifacts."""
    contract = build_powerbi_contract()
    write_powerbi_artifacts(contract)
    validate_written_powerbi_artifacts()

    print("Power BI design contract: OK")
    print(f"Tables: {len(contract['tables'])}")
    print(f"Relationships: {len(contract['relationships'])}")
    print(f"Measures: {len(contract['measures'])}")
    print(f"Pages: {len(contract['pages'])}")
    print(
        "Relationship policy: active one-to-many, single-direction, "
        "dimension-to-fact"
    )
    print("Date table: Dim Date[calendar_date] (1,461 dates)")
    contract_relative = DEFAULT_POWERBI_CONTRACT.relative_to(
        DEFAULT_POWERBI_CONTRACT.parents[1]
    )
    print(f"Output: {contract_relative}")
    print(f"Output SHA-256: {sha256_file(DEFAULT_POWERBI_CONTRACT)}")
    print(f"DAX: {DEFAULT_DAX_CATALOGUE.relative_to(DEFAULT_DAX_CATALOGUE.parents[2])}")
    print(f"DAX SHA-256: {sha256_file(DEFAULT_DAX_CATALOGUE)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
