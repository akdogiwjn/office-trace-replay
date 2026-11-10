"""Parameterized builder for synthetic scaled Excel 013 variants.

Mirrors the frozen parent build (build_public_bid_workbook.py): read the
internal correction log, apply every correction, drop the internal sheets, and
rebuild the ten public sheets in the frozen order. Every fixed range, named
range, data-validation range and summary formula is sized from the actual
vendor count read out of the synthetic source workbook instead of the original
five vendors. No random data is generated here; the source workbook and
vendors.json are frozen at prepare time.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from urllib.parse import quote

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.datavalidation import DataValidation

SHEET_ORDER = [
    "Evaluation Summary",
    "Vendor Register",
    "Requirements Scoring",
    "Price Normalization",
    "Conflict-of-Interest Log",
    "Award Recommendation",
    "Debrief Register",
    "Data Validation Guide",
    "Publication Style Guide",
    "Appendix Index",
]

TAB_COLORS = {
    "Evaluation Summary": "4F2D7F",
    "Vendor Register": "70AD47",
    "Requirements Scoring": "4472C4",
    "Price Normalization": "ED7D31",
    "Conflict-of-Interest Log": "C00000",
    "Award Recommendation": "0F6B6E",
    "Debrief Register": "7030A0",
    "Data Validation Guide": "5B9BD5",
    "Publication Style Guide": "4F2D7F",
    "Appendix Index": "4472C4",
}

REQUIREMENTS = [
    ("REQ-01", "Implementation plan", 0.2),
    ("REQ-02", "Security controls", 0.3),
    ("REQ-03", "Support model", 0.5),
]

COLUMN_WIDTHS = {
    "Evaluation Summary": {"A": 30, "B": 34},
    "Vendor Register": {"A": 14, "B": 24, "C": 22, "D": 18, "E": 18},
    "Requirements Scoring": {"A": 18, "B": 14, "C": 24, "D": 12, "E": 12},
    "Price Normalization": {"A": 14, "B": 24, "C": 19, "D": 14},
    "Conflict-of-Interest Log": {"A": 14, "B": 14, "C": 18, "D": 26, "E": 14},
    "Award Recommendation": {"A": 10, "B": 24, "C": 52, "D": 20},
    "Debrief Register": {"A": 14, "B": 24, "C": 18, "D": 20},
    "Data Validation Guide": {"A": 24, "B": 54},
    "Publication Style Guide": {"A": 24, "B": 36},
    "Appendix Index": {"A": 12, "B": 34, "C": 22, "D": 16},
}

PURPLE = "4F2D7F"
WHITE = "FFFFFF"
APTOS = "Aptos"
HEADER_FILL = PatternFill(fill_type="solid", start_color=PURPLE, end_color=PURPLE)
HEADER_FONT = Font(name=APTOS, size=11, bold=True, color=WHITE)
BODY_FONT = Font(name=APTOS, size=11, color="000000")
HYPERLINK_FONT = Font(name=APTOS, size=11, color="0563C1", underline="single")
HEADER_ALIGNMENT = Alignment(horizontal="center", vertical="center", wrap_text=True)
BODY_ALIGNMENT = Alignment(vertical="center", wrap_text=True)
THIN_SIDE = Side(style="thin", color="D9D2E9")
TABLE_BORDER = Border(
    left=THIN_SIDE,
    right=THIN_SIDE,
    top=THIN_SIDE,
    bottom=THIN_SIDE,
)

CURRENCY_FORMAT = "$#,##0"


def fmt_price(value: int) -> str:
    return f"${value:,.0f}"


def apply_corrections(value, corrections):
    """Same semantics as the frozen parent correction application."""
    if isinstance(value, (int, float)):
        formatted = f"${value:,.0f}"
        for old, new, *_ in corrections:
            if formatted == str(old):
                return float(str(new).replace("$", "").replace(",", ""))
        return value
    corrected = str(value)
    for old, new, *_ in corrections:
        corrected = re.sub(
            rf"(?<!\w){re.escape(str(old))}(?!\w)",
            lambda _: str(new),
            corrected,
        )
    return corrected


def read_correction_log(source):
    rows = list(source["Correction_Log_INTERNAL"].iter_rows(min_row=2, values_only=True))
    return [(str(old), str(new)) for old, new, *_ in rows if old is not None]


def read_vendors(source, corrections):
    ws = source["Raw Vendor Data_INTERNAL"]
    headers = [cell.value for cell in ws[1]]
    index = {name: headers.index(name) for name in headers}
    vendors = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[index["Raw Vendor ID"]] is None:
            continue
        record = {
            "id": apply_corrections(row[index["Raw Vendor ID"]], corrections),
            "name": apply_corrections(row[index["Vendor Name"]], corrections),
            "contact": apply_corrections(row[index["Contact"]], corrections),
            "evaluator": apply_corrections(row[index["Evaluator"]], corrections),
            "status": apply_corrections(row[index["Status"]], corrections),
            "price": apply_corrections(row[index["Raw Corrected Price"]], corrections),
        }
        vendors.append(record)
    vendors.sort(key=lambda r: int(str(r["id"]).split("-")[1]))
    return vendors


def read_requirements(source, corrections, vendor_ids):
    ws = source["Requirements Scratch_INTERNAL"]
    headers = [cell.value for cell in ws[1]]
    index = {name: headers.index(name) for name in headers}
    scores = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[index["Raw Vendor ID"]] is None:
            continue
        vid = apply_corrections(row[index["Raw Vendor ID"]], corrections)
        req_id = apply_corrections(row[index["Requirement ID"]], corrections)
        scores[(vid, req_id)] = row[index["Score"]]
    rows = []
    for vid in vendor_ids:
        for req_id, requirement, weight in REQUIREMENTS:
            rows.append([req_id, vid, requirement, weight, scores[(vid, req_id)]])
    return rows


def weighted_score(scores):
    return sum(weight * scores[req_id] for req_id, _, weight in REQUIREMENTS)


def style_header_row(ws, row, first_col, last_col):
    for cell in ws.iter_rows(min_row=row, max_row=row, min_col=first_col, max_col=last_col):
        for item in cell:
            item.fill = HEADER_FILL
            item.font = HEADER_FONT
            item.alignment = HEADER_ALIGNMENT
            item.border = TABLE_BORDER


def write_rows(ws, rows):
    for row in rows:
        ws.append(row)


def style_public_table(ws, ref, currency_columns=(), percent_columns=()):
    header_row = ws[ref][0]
    for cell in header_row:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = HEADER_ALIGNMENT
        cell.border = TABLE_BORDER

    for row in ws[ref]:
        ws.row_dimensions[row[0].row].height = 22
        for cell in row:
            if cell.row != header_row[0].row:
                cell.font = BODY_FONT
                cell.alignment = BODY_ALIGNMENT
                cell.border = TABLE_BORDER

    for col_letter in currency_columns:
        for cell in ws[col_letter][1:]:
            cell.number_format = CURRENCY_FORMAT
    for col_letter in percent_columns:
        for cell in ws[col_letter][1:]:
            cell.number_format = "0%"

    ws.freeze_panes = f"A{header_row[0].row + 1}"
    ws.auto_filter.ref = ref
    ws.auto_filter.enable = True


def build(vendors_path: Path, output_path: Path):
    data = json.loads(Path(vendors_path).read_text(encoding="utf-8"))
    source_path = Path(data["input_path"])
    source = load_workbook(source_path, data_only=True)
    corrections = read_correction_log(source)
    vendors = read_vendors(source, corrections)
    requirement_rows = read_requirements(source, corrections,
                                         [v["id"] for v in vendors])
    source.close()

    n = len(vendors)
    last = n + 1
    scoring_last = 3 * n + 1
    if n < 3:
        raise ValueError("at least three vendors are required for the award table")

    prices = [float(v["price"]) for v in vendors]
    lowest_price = min(prices)
    responsive = sum(1 for v in vendors if v["status"] == "Responsive")
    all_scores = [row[4] for row in requirement_rows]
    average_score = sum(all_scores) / len(all_scores)
    scores_by_vendor = {
        v["id"]: {row[0]: row[4] for row in requirement_rows if row[1] == v["id"]}
        for v in vendors
    }
    ranked = sorted(
        vendors,
        key=lambda v: (-weighted_score(scores_by_vendor[v["id"]]), v["id"]),
    )
    top = ranked[:3]

    wb = Workbook()
    wb.remove(wb.active)
    for sheet_name in SHEET_ORDER:
        wb.create_sheet(sheet_name)
    wb.active = 0

    vendor_ws = wb["Vendor Register"]
    write_rows(vendor_ws, [["Vendor ID", "Vendor Name", "Contact", "Evaluator", "Status"]])
    for vendor in vendors:
        vendor_ws.append([vendor["id"], vendor["name"], vendor["contact"],
                          vendor["evaluator"], vendor["status"]])

    if "VendorIDs" in wb.defined_names:
        del wb.defined_names["VendorIDs"]
    wb.defined_names.add(
        DefinedName("VendorIDs", attr_text=f"'Vendor Register'!$A$2:$A${last}")
    )

    scoring_ws = wb["Requirements Scoring"]
    write_rows(scoring_ws, [["Requirement ID", "Vendor ID", "Requirement", "Weight", "Score"]])
    write_rows(scoring_ws, requirement_rows)

    price_ws = wb["Price Normalization"]
    write_rows(price_ws, [["Vendor ID", "Vendor Name", "Corrected Price", "Price Score"]])
    for row_num, vendor in enumerate(vendors, start=2):
        price_ws.append([vendor["id"], vendor["name"], float(vendor["price"]),
                         f"=MIN($C$2:$C${last})/C{row_num}*100"])

    coi_ws = wb["Conflict-of-Interest Log"]
    write_rows(coi_ws, [["Log ID", "Vendor ID", "Reviewer", "Disclosure", "Status"]])
    for index, vendor in enumerate(vendors, start=1):
        coi_ws.append([f"COI-{index:03d}", vendor["id"], "Leah Moore",
                       "No conflict disclosed", "Cleared"])

    award_ws = wb["Award Recommendation"]
    write_rows(award_ws, [["Rank", "Recommended Vendor", "Rationale", "Status"]])
    rationales = [
        (f"Highest weighted technical score of {n} vendors; {responsive} "
         f"responsive; lowest corrected price {fmt_price(int(lowest_price))}"),
        f"Reserve rank 2 of {n} vendors; average technical score {average_score:.2f}",
        f"Reserve rank 3 of {n} vendors; average technical score {average_score:.2f}",
    ]
    for rank, vendor in enumerate(top, start=1):
        award_ws.append([
            rank,
            vendor["name"],
            rationales[rank - 1],
            "Recommend award" if rank == 1 else "Reserve",
        ])

    debrief_ws = wb["Debrief Register"]
    write_rows(debrief_ws, [["Vendor ID", "Vendor Name", "Debrief Status", "Debrief Link"]])
    for vendor in vendors:
        debrief_ws.append([vendor["id"], vendor["name"], "Ready", "Email debrief"])

    dv_ws = wb["Data Validation Guide"]
    write_rows(dv_ws, [["Feature", "Requirement"]])
    write_rows(dv_ws, [
        ["Named range", f"VendorIDs = Vendor Register A2:A{last}"],
        ["Scoring validation", f"Requirements Scoring B2:B{scoring_last} uses =VendorIDs"],
        ["Conflict validation", f"Conflict-of-Interest Log B2:B{last} uses =VendorIDs"],
        ["Debrief links", f"Debrief Register D2:D{last} uses mailto hyperlinks"],
    ])

    write_rows(wb["Publication Style Guide"], [
        ["Element", "Requirement"],
        ["Header fill", "4F2D7F"],
        ["Header font", "White bold"],
        ["Body font", "Aptos"],
        ["Currency format", "$#,##0"],
        ["Percent format", "0%"],
        ["Tab colors", "Public color set applied"],
    ])

    write_rows(wb["Appendix Index"], [
        ["Appendix", "Description", "Owner", "Public Status"],
        ["A", "Vendor register extract", "Procurement", "Ready"],
        ["B", "Scoring summary extract", "Evaluation Panel", "Ready"],
        ["C", "Price normalization extract", "Finance", "Ready"],
        ["D", "Debrief register", "Procurement", "Ready"],
    ])

    summary_ws = wb["Evaluation Summary"]
    summary_ws["A1"] = "Procurement Bid Evaluation Release Workbook"
    summary_ws.merge_cells("A1:B1")
    summary_ws["A3"] = "Responsive Vendors"
    summary_ws["B3"] = f'=COUNTIF(\'Vendor Register\'!E2:E{last},"Responsive")'
    summary_ws["A4"] = "Recommended Vendor"
    summary_ws["B4"] = "='Award Recommendation'!B2"
    summary_ws["A5"] = "Lowest Corrected Price"
    summary_ws["B5"] = f"=MIN('Price Normalization'!C2:C{last})"
    summary_ws["A6"] = "Average Technical Score"
    summary_ws["B6"] = f"=AVERAGE('Requirements Scoring'!E2:E{scoring_last})"

    scoring_dv = DataValidation(
        type="list",
        formula1="=VendorIDs",
        allow_blank=False,
        showDropDown=False,
        errorTitle="Invalid vendor",
        error="Select a vendor ID from the Vendor Register.",
        showErrorMessage=True,
    )
    scoring_ws.add_data_validation(scoring_dv)
    scoring_dv.add(f"B2:B{scoring_last}")

    conflict_dv = DataValidation(
        type="list",
        formula1="=VendorIDs",
        allow_blank=False,
        showDropDown=False,
        errorTitle="Invalid vendor",
        error="Select a vendor ID from the Vendor Register.",
        showErrorMessage=True,
    )
    coi_ws.add_data_validation(conflict_dv)
    conflict_dv.add(f"B2:B{last}")

    for row in range(2, last + 1):
        vendor_id = debrief_ws[f"A{row}"].value
        subject = quote(f"Debrief {vendor_id}", safe="")
        debrief_ws[f"D{row}"].hyperlink = (
            f"mailto:procurement@city.example?subject={subject}"
        )

    for sheet_name in SHEET_ORDER:
        ws = wb[sheet_name]
        ws.sheet_properties.tabColor = TAB_COLORS[sheet_name]
        ws.sheet_view.showGridLines = False
        ws.sheet_view.zoomScale = 100
        ws.page_setup.orientation = "landscape"
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        for col_letter, width in COLUMN_WIDTHS[sheet_name].items():
            ws.column_dimensions[col_letter].width = width

    summary_ws["A1"].fill = HEADER_FILL
    summary_ws["A1"].font = Font(name=APTOS, size=16, bold=True, color=WHITE)
    summary_ws["A1"].alignment = Alignment(horizontal="left", vertical="center")
    summary_ws.row_dimensions[1].height = 32
    style_public_table(summary_ws, "A3:B6")
    summary_ws["B5"].number_format = CURRENCY_FORMAT
    summary_ws["B6"].number_format = "0.0"
    for row in range(4, 7):
        summary_ws.row_dimensions[row].height = 22

    style_public_table(vendor_ws, f"A1:E{last}")
    style_public_table(scoring_ws, f"A1:E{scoring_last}", percent_columns=("D",))
    style_public_table(price_ws, f"A1:D{last}", currency_columns=("C",))
    for row in range(2, last + 1):
        price_ws[f"D{row}"].number_format = "0.0"
    style_public_table(coi_ws, f"A1:E{last}")
    style_public_table(award_ws, "A1:D4")
    style_public_table(debrief_ws, f"A1:D{last}")
    style_public_table(dv_ws, "A1:B5")
    style_public_table(wb["Publication Style Guide"], "A1:B7")
    style_public_table(wb["Appendix Index"], "A1:D5")

    for row in range(2, last + 1):
        debrief_ws[f"D{row}"].font = HYPERLINK_FONT

    wb.properties.title = "Procurement Bid Evaluation Release Workbook"
    wb.properties.subject = "Public bid evaluation release"
    wb.properties.creator = "Procurement Evaluation Panel"
    wb.properties.lastModifiedBy = "Procurement Evaluation Panel"
    wb.properties.description = (
        "Corrected public release of the procurement bid evaluation workbook."
    )
    wb.calculation.calcMode = "auto"
    wb.calculation.fullCalcOnLoad = True
    wb.calculation.forceFullCalc = True
    wb.views[0].activeTab = 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    return n


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vendors", default=os.environ.get("VARIANT_VENDORS"),
                        help="frozen vendors.json path")
    parser.add_argument("--output", default=os.environ.get("VARIANT_OUTPUT"),
                        help="output workbook path")
    args = parser.parse_args(argv)
    if not args.vendors or not args.output:
        parser.error("--vendors and --output are required (or set VARIANT_VENDORS/VARIANT_OUTPUT)")
    n = build(Path(args.vendors), Path(args.output))
    print(args.output)
    print(f"Vendors: {n}")


if __name__ == "__main__":
    main()
