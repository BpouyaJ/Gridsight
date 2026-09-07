"""Fast structural checks for the Phase 9 Excel analyst pack."""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "excel" / "GridSight_Monthly_Energy_Analyst_Pack.xlsx"
QUERY = ROOT / "excel" / "queries" / "monthly_energy.pq"
MONTHLY_SAMPLE = ROOT / "data" / "samples" / "monthly_energy_sample.csv"

SPREADSHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def _workbook_xml_parts() -> dict[str, bytes]:
    with ZipFile(WORKBOOK) as archive:
        return {
            name: archive.read(name)
            for name in archive.namelist()
            if name.startswith("xl/") and name.endswith(".xml")
        }


def test_excel_pack_contains_the_approved_sheets_tables_and_charts() -> None:
    parts = _workbook_xml_parts()
    workbook_root = ET.fromstring(parts["xl/workbook.xml"])
    sheet_names = [
        sheet.attrib["name"]
        for sheet in workbook_root.findall(f".//{{{SPREADSHEET_NS}}}sheet")
    ]

    assert sheet_names == [
        "Dashboard",
        "MonthlyEnergy",
        "Setup",
        "Monthly Data",
        "Annual Summary",
        "Pivot Analysis",
        "Reconciliation",
        "Power Query",
        "Native Pivot",
    ]

    table_names = {
        ET.fromstring(xml).attrib["name"]
        for name, xml in parts.items()
        if name.startswith("xl/tables/table")
    }
    assert table_names == {
        "GridSightParameters",
        "MonthlyEnergy",
        "MonthlyEnergyTable",
    }

    shared_strings_root = ET.fromstring(parts["xl/sharedStrings.xml"])
    shared_strings = [
        "".join(
            text.text or ""
            for text in item.findall(
                f".//{{{SPREADSHEET_NS}}}t"
            )
        )
        for item in shared_strings_root
    ]
    assert r"C:\path\to\GridSight" in shared_strings
    assert not any(r"C:\Users\borji" in value for value in shared_strings)

    chart_parts = [name for name in parts if name.startswith("xl/charts/chart")]
    assert len(chart_parts) == 2


def test_excel_formulas_are_present_and_have_no_cached_errors() -> None:
    parts = _workbook_xml_parts()
    worksheet_roots = [
        ET.fromstring(xml)
        for name, xml in parts.items()
        if name.startswith("xl/worksheets/sheet")
    ]
    formulas = {
        formula.text or ""
        for root in worksheet_roots
        for formula in root.findall(f".//{{{SPREADSHEET_NS}}}f")
    }

    assert any(
        "SUM('Monthly Data'!$H$2:$H$49)/1000000" in formula
        for formula in formulas
    )
    assert any(
        "SUMIF('Monthly Data'!$C$2:$C$49,$A6" in formula
        for formula in formulas
    )
    assert any(
        'IF(ABS(E6)<=C6,"PASS","CHECK")' in formula for formula in formulas
    )

    error_cells = [
        cell.attrib.get("r", "")
        for root in worksheet_roots
        for cell in root.findall(f".//{{{SPREADSHEET_NS}}}c")
        if cell.attrib.get("t") == "e"
    ]
    assert error_cells == []


def test_excel_pack_embeds_power_query_and_native_pivot_metadata() -> None:
    parts = _workbook_xml_parts()

    connections_root = ET.fromstring(parts["xl/connections.xml"])
    connections = list(connections_root)
    assert len(connections) == 1
    connection = connections[0]
    assert connection.attrib["name"] == "Query - MonthlyEnergy"
    assert connection.attrib["type"] == "5"
    database_properties = connection.find(
        f"{{{SPREADSHEET_NS}}}dbPr"
    )
    assert database_properties is not None
    assert "Location=MonthlyEnergy" in database_properties.attrib["connection"]

    query_table = ET.fromstring(parts["xl/queryTables/queryTable1.xml"])
    assert query_table.attrib["connectionId"] == connection.attrib["id"]

    pivot_cache = ET.fromstring(
        parts["xl/pivotCache/pivotCacheDefinition1.xml"]
    )
    worksheet_source = pivot_cache.find(
        f".//{{{SPREADSHEET_NS}}}worksheetSource"
    )
    assert worksheet_source is not None
    assert worksheet_source.attrib["name"] == "MonthlyEnergy"

    cache_fields = pivot_cache.findall(
        f".//{{{SPREADSHEET_NS}}}cacheField"
    )
    field_names = [field.attrib["name"] for field in cache_fields]

    pivot_table = ET.fromstring(parts["xl/pivotTables/pivotTable1.xml"])
    location = pivot_table.find(f"{{{SPREADSHEET_NS}}}location")
    assert location is not None
    assert location.attrib["ref"] == "A3:N9"

    row_field = pivot_table.find(
        f"{{{SPREADSHEET_NS}}}rowFields/{{{SPREADSHEET_NS}}}field"
    )
    column_field = pivot_table.find(
        f"{{{SPREADSHEET_NS}}}colFields/{{{SPREADSHEET_NS}}}field"
    )
    data_field = pivot_table.find(
        f"{{{SPREADSHEET_NS}}}dataFields/{{{SPREADSHEET_NS}}}dataField"
    )
    assert row_field is not None
    assert column_field is not None
    assert data_field is not None
    assert field_names[int(row_field.attrib["x"])] == "calendar_year"
    assert field_names[int(column_field.attrib["x"])] == "month_number"
    assert field_names[int(data_field.attrib["fld"])] == "grid_load_twh"
    assert data_field.attrib["name"] == "Sum of grid_load_twh"
    assert data_field.attrib["numFmtId"] == "2"


def test_power_query_contract_targets_the_checked_monthly_sample() -> None:
    query = QUERY.read_text(encoding="utf-8")

    assert "Excel.CurrentWorkbook()" in query
    assert "GridSightParameters" in query
    assert "monthly_energy_sample.csv" not in query
    assert "File.Contents(SourcePath)" in query
    assert 'Columns = 20' in query
    assert '{"month_start", type date}' in query
    assert '"negative_price_hour_share"' in query
    assert '"price_hour_weighted_sum"' in query

    sample_sha256 = hashlib.sha256(MONTHLY_SAMPLE.read_bytes()).hexdigest()
    assert sample_sha256 == (
        "86a17351935e5cf9bebec2b1bad8b6da00359363df09e8f65c73fd0422c78676"
    )
