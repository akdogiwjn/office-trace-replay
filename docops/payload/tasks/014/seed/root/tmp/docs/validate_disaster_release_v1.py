import json
import zipfile
from pathlib import Path

from openpyxl import load_workbook


OUTPUT = Path("/root/submission/docops_v2_l3_014_xlsx_disaster_housing_grant_public_release_output.xlsx")
EXPECTED_SHEETS = [
    "Funding Dashboard",
    "Eligibility Register",
    "County Rollup",
    "Appeal Queue",
    "Publication Controls",
]
EXPECTED_TABS = {
    "Funding Dashboard": "FF70AD47",
    "Eligibility Register": "FF5B9BD5",
    "County Rollup": "FFFFC000",
    "Appeal Queue": "FFC00000",
    "Publication Controls": "FF7030A0",
}
EXPECTED_FREEZE = {
    "Funding Dashboard": "A4",
    "Eligibility Register": "A2",
    "County Rollup": "A2",
    "Appeal Queue": "A2",
    "Publication Controls": "A2",
}
EXPECTED_TABLES = {
    "Eligibility Register": ("tblEligibilityRegister", "A1:L13"),
    "County Rollup": ("tblCountyRollup", "A1:D5"),
    "Appeal Queue": ("tblAppealQueue", "A1:E4"),
    "Publication Controls": ("tblPublicationControls", "A1:D5"),
}
FORBIDDEN = [
    "DRAFT",
    "PRIVATE",
    "legal hold",
    "raw intake",
    "duplicate scratch",
    "unverified hardship narrative",
    "personal phone",
    "applicant name",
    "Alicia Tran",
    "Marta Ruiz",
    "Lena Okafor",
    "N. Fork",
    "Minor correction pending",
    "moderate income pending",
]
EXPECTED_IDS = [f"H-{number}" for number in range(101, 113)]
EXPECTED_AMOUNTS = [18000, 28000, 8800, 26500, 42000, 14800, 21500, 8200, 24200, 42000, 18000, 26500]
EXPECTED_SCORES = [30, 70, 10, 50, 80, 30, 60, 30, 40, 80, 20, 70]
EXPECTED_STATUS = [
    "Ready",
    "Senior Review",
    "Appeal Review",
    "Senior Review",
    "Senior Review",
    "Ready",
    "Senior Review",
    "Ready",
    "Senior Review",
    "Senior Review",
    "Ready",
    "Senior Review",
]


wb = load_workbook(OUTPUT, data_only=False)
values_wb = load_workbook(OUTPUT, data_only=True)
checks = {}

checks["sheet_order"] = wb.sheetnames == EXPECTED_SHEETS
checks["tab_colors"] = {
    ws.title: ws.sheet_properties.tabColor.rgb if ws.sheet_properties.tabColor else None
    for ws in wb.worksheets
} == EXPECTED_TABS
checks["freeze_panes"] = {ws.title: ws.freeze_panes for ws in wb.worksheets} == EXPECTED_FREEZE
checks["protected_sheets"] = (
    wb["Funding Dashboard"].protection.sheet is True
    and wb["Publication Controls"].protection.sheet is True
    and wb["Eligibility Register"].protection.sheet is not True
    and wb["County Rollup"].protection.sheet is not True
    and wb["Appeal Queue"].protection.sheet is not True
)
checks["protected_structure"] = wb.security.lockStructure is True
checks["tables"] = {
    ws.title: (next(iter(ws.tables.values())).displayName, next(iter(ws.tables.values())).ref)
    for ws in wb.worksheets
    if ws.tables
} == EXPECTED_TABLES

register = wb["Eligibility Register"]
register_values = values_wb["Eligibility Register"]
checks["deduplicated_ids"] = [register.cell(row, 1).value for row in range(2, 14)] == EXPECTED_IDS
checks["latest_h107"] = register["I8"].value == "2026-05-21"
checks["corrections"] = (
    register["B5"].value == "North Fork"
    and register["C10"].value == "Major"
    and register["F13"].value == "Low"
)
checks["formula_columns"] = all(
    str(register.cell(row, column).value).startswith("=")
    for row in range(2, 14)
    for column in (10, 11, 12)
)
checks["eligible_values"] = [register_values.cell(row, 10).value for row in range(2, 14)] == EXPECTED_AMOUNTS
checks["priority_values"] = [register_values.cell(row, 11).value for row in range(2, 14)] == EXPECTED_SCORES
checks["review_values"] = [register_values.cell(row, 12).value for row in range(2, 14)] == EXPECTED_STATUS

cf_register = {
    str(cf.sqref): [(rule.type, rule.operator, tuple(rule.formula)) for rule in cf.rules]
    for cf in register.conditional_formatting
}
checks["conditional_formats"] = (
    cf_register.get("K2:K13") == [("cellIs", "greaterThanOrEqual", ("70",))]
    and cf_register.get("J2:J13") == [("cellIs", "greaterThan", ("0",))]
)

dashboard_values = values_wb["Funding Dashboard"]
checks["dashboard_metrics"] = [dashboard_values[f"B{row}"].value for row in range(4, 9)] == [
    12,
    278500,
    7,
    1,
    47.5,
]
rollup_values = values_wb["County Rollup"]
checks["rollup_values"] = [
    tuple(rollup_values.cell(row, column).value for column in range(1, 5))
    for row in range(2, 6)
] == [
    ("East Bay", 3, 67000, 2),
    ("North Fork", 2, 68500, 2),
    ("South Ridge", 4, 94700, 2),
    ("West Lake", 3, 48300, 1),
]
appeal_values = values_wb["Appeal Queue"]
checks["appeal_values"] = [
    tuple(appeal_values.cell(row, column).value for column in range(1, 6))
    for row in range(2, 5)
] == [
    ("H-103", "West Lake", "Minor", 8800, "Appeal Review"),
    ("H-105", "South Ridge", "Destroyed", 42000, "Senior Review"),
    ("H-109", "East Bay", "Major", 24200, "Senior Review"),
]

chart = wb["Funding Dashboard"]._charts[0]
series = chart.series[0]
categories_formula = (
    series.cat.numRef.f
    if series.cat.numRef is not None
    else series.cat.strRef.f
)
checks["chart"] = (
    chart.__class__.__name__ == "BarChart"
    and chart.title is not None
    and categories_formula == "'County Rollup'!$A$2:$A$5"
    and series.val.numRef.f == "'County Rollup'!$C$2:$C$5"
)

table_headers = {
    "Funding Dashboard": [wb["Funding Dashboard"]["A3"], wb["Funding Dashboard"]["B3"]],
    "Eligibility Register": list(register[1]),
    "County Rollup": list(wb["County Rollup"][1]),
    "Appeal Queue": list(wb["Appeal Queue"][1]),
    "Publication Controls": list(wb["Publication Controls"][1]),
}
checks["header_styles"] = all(
    cell.fill.fill_type == "solid"
    and cell.fill.fgColor.rgb in ("001F4E79", "FF1F4E79")
    and cell.font.name == "Aptos"
    and cell.font.sz == 11
    and cell.font.bold is True
    and cell.font.color.rgb in ("00FFFFFF", "FFFFFFFF")
    for cells in table_headers.values()
    for cell in cells
)
checks["body_styles"] = all(
    cell.font.name == "Aptos" and cell.font.sz == 11
    for sheet in EXPECTED_SHEETS
    for row in wb[sheet].iter_rows()
    for cell in row
    if cell.value is not None and not (sheet == "Funding Dashboard" and cell.coordinate == "A1")
)
currency_cells = (
    [register.cell(row, column) for row in range(2, 14) for column in (4, 5, 10)]
    + [wb["County Rollup"].cell(row, 3) for row in range(2, 6)]
    + [wb["Appeal Queue"].cell(row, 4) for row in range(2, 5)]
    + [wb["Publication Controls"].cell(row, 2) for row in range(2, 6)]
    + [wb["Funding Dashboard"]["B5"]]
)
checks["currency_formats"] = all(cell.number_format == "$#,##0;($#,##0);-" for cell in currency_cells)

all_cell_text = "\n".join(
    str(cell.value)
    for ws in wb.worksheets
    for row in ws.iter_rows()
    for cell in row
    if cell.value is not None
)
checks["forbidden_cells"] = not any(phrase.lower() in all_cell_text.lower() for phrase in FORBIDDEN)

with zipfile.ZipFile(OUTPUT) as archive:
    xml_text = "\n".join(
        archive.read(name).decode("utf-8", errors="ignore")
        for name in archive.namelist()
        if name.endswith((".xml", ".rels"))
    )
checks["forbidden_uppercase_xml"] = "DRAFT" not in xml_text and "PRIVATE" not in xml_text

formula_errors = []
for ws in values_wb.worksheets:
    for row in ws.iter_rows():
        for cell in row:
            if isinstance(cell.value, str) and cell.value.startswith("#"):
                formula_errors.append(f"{ws.title}!{cell.coordinate}:{cell.value}")
checks["zero_formula_errors"] = not formula_errors

print(json.dumps(checks, indent=2))
if not all(checks.values()):
    raise SystemExit(1)
