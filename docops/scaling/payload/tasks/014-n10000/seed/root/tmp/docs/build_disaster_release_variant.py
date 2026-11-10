"""Parameterized builder for synthetic scaled Excel 014 variants.

Mirrors the frozen parent build (build_disaster_release_v1.py) but sizes every
fixed range from the actual deduplicated record count instead of the original
12 rows. Business calculation rules are unchanged; the oracle values live in the
frozen expected.json and are checked by validate_disaster_release_variant.py.
"""
from __future__ import annotations

import argparse
import datetime
import os
from copy import copy
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.worksheet.protection import SheetProtection
from openpyxl.workbook.protection import WorkbookProtection

PUBLIC_FIELDS = [
    "Application ID",
    "County",
    "Damage Category",
    "Repair Estimate",
    "Insurance Proceeds",
    "Income Band",
    "Vulnerable Household",
    "Appeal Flag",
    "Inspection Date",
]
COUNTIES = ["East Bay", "North Fork", "South Ridge", "West Lake"]
CORRECTIONS = {
    "H-104": {"County": "North Fork"},
    "H-109": {"Damage Category": "Major"},
    "H-112": {"Income Band": "Low"},
}
CAPS = {"Minor": 12000, "Moderate": 18000, "Major": 28000, "Destroyed": 42000}

HEADER_FILL = PatternFill("solid", fgColor="1F4E79")
HEADER_FONT = Font(name="Aptos", size=11, bold=True, color="FFFFFF")
BODY_FONT = Font(name="Aptos", size=11, color="000000")
BODY_FILL = PatternFill("solid", fgColor="FFFFFF")
ALT_FILL = PatternFill("solid", fgColor="EAF2F8")
THIN_BORDER = Border(
    left=Side(style="thin", color="D9E2F3"),
    right=Side(style="thin", color="D9E2F3"),
    top=Side(style="thin", color="D9E2F3"),
    bottom=Side(style="thin", color="D9E2F3"),
)
CURRENCY_FORMAT = "$#,##0;($#,##0);-"
TAB_COLORS = {
    "Funding Dashboard": "70AD47",
    "Eligibility Register": "5B9BD5",
    "County Rollup": "FFC000",
    "Appeal Queue": "C00000",
    "Publication Controls": "7030A0",
}


def style_header(ws, row, first_col, last_col):
    for cell in ws.iter_rows(min_row=row, max_row=row, min_col=first_col, max_col=last_col):
        for item in cell:
            item.fill = HEADER_FILL
            item.font = HEADER_FONT
            item.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            item.border = THIN_BORDER


def style_body(ws, min_row, max_row, min_col, max_col, currency_cols=()):
    for row in ws.iter_rows(min_row=min_row, max_row=max_row, min_col=min_col, max_col=max_col):
        for cell in row:
            cell.font = copy(BODY_FONT)
            cell.border = copy(THIN_BORDER)
            cell.alignment = Alignment(vertical="top", wrap_text=False)
            if cell.row % 2 == 0:
                cell.fill = copy(ALT_FILL)
            else:
                cell.fill = copy(BODY_FILL)
            if cell.column in currency_cols:
                cell.number_format = CURRENCY_FORMAT


def add_table(ws, name, ref):
    table = Table(displayName=name, ref=ref)
    table.tableStyleInfo = TableStyleInfo(
        name="TableStyleMedium2",
        showFirstColumn=False,
        showLastColumn=False,
        showRowStripes=False,
        showColumnStripes=False,
    )
    ws.add_table(table)


def set_widths(ws, widths):
    for column, width in widths.items():
        ws.column_dimensions[column].width = width


def extract_public_records(source):
    ws = source["Raw Intake PRIVATE"]
    headers = [cell.value for cell in ws[1]]
    indexes = {field: headers.index(field) for field in PUBLIC_FIELDS}
    records = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row[indexes["Application ID"]]:
            continue
        records.append({field: row[indexes[field]] for field in PUBLIC_FIELDS})
    return records


def build(source_path: Path, output_path: Path):
    source_wb = load_workbook(source_path, data_only=True)
    records = extract_public_records(source_wb)
    source_wb.close()

    latest_by_id = {}
    for record in records:
        app_id = record["Application ID"]
        inspection_date = datetime.date.fromisoformat(str(record["Inspection Date"]).strip())
        prior = latest_by_id.get(app_id)
        if prior is None or inspection_date > prior[0]:
            latest_by_id[app_id] = (inspection_date, record)
    records = [entry[1] for entry in latest_by_id.values()]
    records.sort(key=lambda row: int(row["Application ID"].split("-")[1]))

    for record in records:
        record.update(CORRECTIONS.get(record["Application ID"], {}))

    n = len(records)
    last = n + 1

    wb = Workbook()
    dashboard = wb.active
    dashboard.title = "Funding Dashboard"
    eligibility = wb.create_sheet("Eligibility Register")
    county = wb.create_sheet("County Rollup")
    appeal = wb.create_sheet("Appeal Queue")
    controls = wb.create_sheet("Publication Controls")

    eligibility_headers = [
        "Application ID",
        "County",
        "Damage Category",
        "Repair Estimate",
        "Insurance Proceeds",
        "Income Band",
        "Vulnerable Household",
        "Appeal Flag",
        "Inspection Date",
        "Eligible Amount",
        "Priority Score",
        "Review Status",
    ]
    eligibility.append(eligibility_headers)
    for row_num, record in enumerate(records, start=2):
        eligibility.append([
            record["Application ID"],
            record["County"],
            record["Damage Category"],
            record["Repair Estimate"],
            record["Insurance Proceeds"],
            record["Income Band"],
            record["Vulnerable Household"],
            record["Appeal Flag"],
            record["Inspection Date"],
        ])
        eligibility.cell(row_num, 10, f"=MAX(0,MIN(D{row_num}-E{row_num},VLOOKUP(C{row_num},'Publication Controls'!$A$2:$B$5,2,FALSE)))")
        eligibility.cell(
            row_num,
            11,
            f'=IF(G{row_num}="Yes",20,0)+IF(C{row_num}="Destroyed",40,IF(C{row_num}="Major",30,IF(C{row_num}="Moderate",20,10)))+IF(F{row_num}="Low",20,IF(F{row_num}="Moderate",10,0))',
        )
        eligibility.cell(row_num, 12, f'=IF(J{row_num}>=20000,"Senior Review",IF(H{row_num}="Yes","Appeal Review","Ready"))')

    county_headers = ["County", "Applications", "Eligible Amount", "Senior Review Count"]
    county.append(county_headers)
    for row_num, county_name in enumerate(COUNTIES, start=2):
        county.append([
            county_name,
            f"=COUNTIF('Eligibility Register'!$B$2:$B${last},A{row_num})",
            f"=SUMIF('Eligibility Register'!$B$2:$B${last},A{row_num},'Eligibility Register'!$J$2:$J${last})",
            f"=COUNTIFS('Eligibility Register'!$B$2:$B${last},A{row_num},'Eligibility Register'!$L$2:$L${last},\"Senior Review\")",
        ])

    appeal_headers = ["Application ID", "County", "Damage Category", "Eligible Amount", "Review Status"]
    appeal.append(appeal_headers)
    register_row_by_id = {
        eligibility.cell(row, 1).value: row for row in range(2, eligibility.max_row + 1)
    }
    appeal_ids = [
        record["Application ID"] for record in records if record["Appeal Flag"] == "Yes"
    ]
    for app_id in appeal_ids:
        source_row = register_row_by_id[app_id]
        record = next(record for record in records if record["Application ID"] == app_id)
        appeal.append([
            app_id,
            record["County"],
            record["Damage Category"],
            f"='Eligibility Register'!J{source_row}",
            f"='Eligibility Register'!L{source_row}",
        ])
    appeal_last = appeal.max_row

    controls.append(["Damage Category", "Assistance Cap", "Public Correction", "Corrected Fact"])
    controls.append(["Minor", 12000, "H-104 county", "North Fork"])
    controls.append(["Moderate", 18000, "H-109 damage category", "Major"])
    controls.append(["Major", 28000, "H-112 income band", "Low"])
    controls.append(["Destroyed", 42000, "Nonpublic notes removed", "Yes"])

    dashboard["A1"] = "Public Disaster Housing Repair Grant Release"
    dashboard["A3"] = "Metric"
    dashboard["B3"] = "Value"
    dashboard.append(["Total Applications", f"=COUNTA('Eligibility Register'!$A$2:$A${last})"])
    dashboard.append(["Total Eligible Amount", f"=SUM('Eligibility Register'!$J$2:$J${last})"])
    dashboard.append(["Senior Review Count", f"=COUNTIF('Eligibility Register'!$L$2:$L${last},\"Senior Review\")"])
    dashboard.append(["Appeal Review Count", f"=COUNTIF('Eligibility Register'!$L$2:$L${last},\"Appeal Review\")"])
    dashboard.append(["Average Priority Score", f"=AVERAGE('Eligibility Register'!$K$2:$K${last})"])

    chart = BarChart()
    chart.type = "col"
    chart.style = 10
    chart.title = "Eligible Amount by County"
    chart.y_axis.title = "Eligible Amount"
    chart.x_axis.title = "County"
    chart.legend = None
    data = Reference(county, min_col=3, min_row=1, max_row=5)
    categories = Reference(county, min_col=1, min_row=2, max_row=5)
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(categories)
    chart.dLbls = None
    chart.height = 8.5
    chart.width = 17
    dashboard.add_chart(chart, "D3")

    for ws in wb.worksheets:
        ws.sheet_properties.tabColor = TAB_COLORS[ws.title]
        ws.sheet_view.showGridLines = False
        for row in ws.iter_rows():
            for cell in row:
                cell.font = copy(BODY_FONT)

    style_header(eligibility, 1, 1, 12)
    style_body(eligibility, 2, last, 1, 12, currency_cols=(4, 5, 10))
    for row in range(2, last + 1):
        eligibility.cell(row, 10).number_format = CURRENCY_FORMAT
        eligibility.cell(row, 11).number_format = "0"
        eligibility.cell(row, 9).number_format = "@"
    eligibility.freeze_panes = "A2"
    eligibility.auto_filter.ref = f"A1:L{last}"
    add_table(eligibility, "tblEligibilityRegister", f"A1:L{last}")
    eligibility.conditional_formatting.add(
        f"K2:K{last}",
        CellIsRule(
            operator="greaterThanOrEqual",
            formula=["70"],
            fill=PatternFill("solid", fgColor="F4B183"),
            font=Font(name="Aptos", size=11, bold=True, color="9C0006"),
        ),
    )
    eligibility.conditional_formatting.add(
        f"J2:J{last}",
        CellIsRule(
            operator="greaterThan",
            formula=["0"],
            fill=PatternFill("solid", fgColor="C6E0B4"),
            font=Font(name="Aptos", size=11, bold=False, color="006100"),
        ),
    )

    style_header(county, 1, 1, 4)
    style_body(county, 2, 5, 1, 4, currency_cols=(3,))
    county.freeze_panes = "A2"
    county.auto_filter.ref = "A1:D5"
    add_table(county, "tblCountyRollup", "A1:D5")

    style_header(appeal, 1, 1, 5)
    style_body(appeal, 2, appeal_last, 1, 5, currency_cols=(4,))
    appeal.freeze_panes = "A2"
    appeal.auto_filter.ref = f"A1:E{appeal_last}"
    add_table(appeal, "tblAppealQueue", f"A1:E{appeal_last}")

    style_header(controls, 1, 1, 4)
    style_body(controls, 2, 5, 1, 4, currency_cols=(2,))
    controls.freeze_panes = "A2"
    controls.auto_filter.ref = "A1:D5"
    add_table(controls, "tblPublicationControls", "A1:D5")
    for row in range(2, 6):
        controls.cell(row, 2).fill = PatternFill("solid", fgColor="FFF2CC")

    style_header(dashboard, 3, 1, 2)
    style_body(dashboard, 4, 8, 1, 2)
    dashboard["A1"].font = Font(name="Aptos", size=20, bold=True, color="FFFFFF")
    dashboard["A1"].fill = HEADER_FILL
    dashboard["A1"].alignment = Alignment(horizontal="left", vertical="center")
    dashboard.merge_cells("A1:H1")
    dashboard.row_dimensions[1].height = 35
    dashboard["B5"].number_format = CURRENCY_FORMAT
    dashboard["B8"].number_format = "0.0"
    dashboard.freeze_panes = "A4"

    set_widths(dashboard, {"A": 24, "B": 24, "C": 3, "D": 13, "E": 13, "F": 13, "G": 13, "H": 13})
    set_widths(eligibility, {"A": 16, "B": 16, "C": 18, "D": 18, "E": 20, "F": 15, "G": 23, "H": 14, "I": 16, "J": 18, "K": 16, "L": 18})
    set_widths(county, {"A": 18, "B": 16, "C": 20, "D": 22})
    set_widths(appeal, {"A": 16, "B": 18, "C": 20, "D": 18, "E": 18})
    set_widths(controls, {"A": 20, "B": 18, "C": 28, "D": 22})

    for ws in (eligibility, county, appeal, controls):
        ws.row_dimensions[1].height = 32
        ws.sheet_view.zoomScale = 90

    dashboard.protection = SheetProtection(sheet=True)
    controls.protection = SheetProtection(sheet=True)
    wb.security = WorkbookProtection(lockStructure=True)
    wb.calculation.fullCalcOnLoad = True
    wb.properties.title = "Public Disaster Housing Repair Grant Release"
    wb.properties.subject = "Corrected, deduplicated public eligibility release (synthetic scale variant)"
    wb.properties.creator = "Disaster Housing Grant Program"
    wb.properties.lastModifiedBy = "Disaster Housing Grant Program"
    wb.properties.keywords = ""
    wb.properties.description = ""
    wb.properties.identifier = ""
    wb.properties.category = "Public release"
    wb.active = 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    return n


def default_arg(name, env_name):
    return os.environ.get(env_name) or name


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=os.environ.get("VARIANT_INPUT"),
                        help="source workbook path")
    parser.add_argument("--output", default=os.environ.get("VARIANT_OUTPUT"),
                        help="output workbook path")
    args = parser.parse_args(argv)
    if not args.input or not args.output:
        parser.error("--input and --output are required (or set VARIANT_INPUT/VARIANT_OUTPUT)")
    n = build(Path(args.input), Path(args.output))
    print(args.output)
    print(f"Records: {n}")


if __name__ == "__main__":
    main()
