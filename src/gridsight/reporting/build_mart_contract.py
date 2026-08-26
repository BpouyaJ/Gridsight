"""CLI for freezing GridSight's Power BI and Excel data-product contract."""

from gridsight.forecasting.contract import sha256_file
from gridsight.reporting.mart_contract import (
    DEFAULT_REPORTING_MART_CONTRACT,
    build_reporting_mart_contract,
    write_reporting_mart_contract,
)


def main() -> int:
    """Verify upstream evidence and publish the deterministic contract."""
    try:
        contract = build_reporting_mart_contract()
        write_reporting_mart_contract(
            contract,
            DEFAULT_REPORTING_MART_CONTRACT,
        )
    except (KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
        print(f"Reporting-mart contract: FAILED ({error})")
        return 1

    products = contract["products"]
    sql_products = [
        product
        for product in products
        if product["source_kind"] == "postgresql_view"
    ]
    print("Reporting-mart contract: OK")
    print(f"Products: {len(products)}")
    print(f"PostgreSQL views: {len(sql_products)}")
    print(f"Checked sample extracts: {len(products)}")
    for product in products:
        print(
            f"{product['product_id']}: "
            f"rows={product['expected_full_rows']}, "
            f"sample_rows={product['sample']['expected_rows']}, "
            f"status={product['implementation_status']}"
        )
    relative_output = DEFAULT_REPORTING_MART_CONTRACT.relative_to(
        DEFAULT_REPORTING_MART_CONTRACT.parents[1]
    )
    print(f"Output: {relative_output}")
    print(f"SHA-256: {sha256_file(DEFAULT_REPORTING_MART_CONTRACT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
