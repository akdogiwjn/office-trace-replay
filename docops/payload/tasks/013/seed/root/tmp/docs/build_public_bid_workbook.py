from pathlib import Path
import re
from urllib.parse import quote

from openpyxl import load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.datavalidation import DataValidation


SOURCE = Path("/root/docops_v2_l3_013_xlsx_procurement_bid_evaluation_release_input.xlsx")
OUTPUT = Path(
    "/root/submission/"
    "docops_v2_l3_013_xlsx_procurement_bid_evaluation_release_output.xlsx"
)

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

PUBLIC_TABLES = {
    "Vendor Register": [
        ["Vendor ID", "Vendor Name", "Contact", "Evaluator", "Status"],
        ["VND-001", "Civic Data Works", "Ada Brooks", "Leah Moor", "Responsive"],
        ["VND-002", "Harbor Systems", "Iris Chen", "Leah Moor", "Responsive"],
        ["VND-03A", "Northstar Analytcs", "Omar Vale", "Leah Moor", "Responsiv"],
        ["VND-004", "SignalBridge Labs", "Mina Patel", "Leah Moor", "Responsive"],
        ["VND-005", "Westport Insight", "Theo Grant", "Leah Moor", "Nonresponsive"],
    ],
    "Requirements Scoring": [
        ["Requirement ID", "Vendor ID", "Requirement", "Weight", "Score"],
        ["REQ-01", "VND-001", "Implementation plan", 0.2, 88],
        ["REQ-02", "VND-001", "Security controls", 0.3, 91],
        ["REQ-03", "VND-001", "Support model", 0.5, 87],
        ["REQ-01", "VND-002", "Implementation plan", 0.2, 83],
        ["REQ-02", "VND-002", "Security controls", 0.3, 86],
        ["REQ-03", "VND-002", "Support model", 0.5, 84],
        ["REQ-01", "VND-003", "Implementation plan", 0.2, 92],
        ["REQ-02", "VND-003", "Security controls", 0.3, 94],
        ["REQ-03", "VND-003", "Support model", 0.5, 93],
        ["REQ-01", "VND-004", "Implementation plan", 0.2, 81],
        ["REQ-02", "VND-004", "Security controls", 0.3, 82],
        ["REQ-03", "VND-004", "Support model", 0.5, 80],
        ["REQ-01", "VND-005", "Implementation plan", 0.2, 70],
        ["REQ-02", "VND-005", "Security controls", 0.3, 68],
        ["REQ-03", "VND-005", "Support model", 0.5, 72],
    ],
    "Price Normalization": [
        ["Vendor ID", "Vendor Name", "Corrected Price", "Price Score"],
        ["VND-001", "Civic Data Works", 1188000, "=MIN($C$2:$C$6)/C2*100"],
        ["VND-002", "Harbor Systems", 1255000, "=MIN($C$2:$C$6)/C3*100"],
        ["VND-003", "Northstar Analytcs", 1240000, "=MIN($C$2:$C$6)/C4*100"],
        ["VND-004", "SignalBridge Labs", 1320000, "=MIN($C$2:$C$6)/C5*100"],
        ["VND-005", "Westport Insight", 1110000, "=MIN($C$2:$C$6)/C6*100"],
    ],
    "Conflict-of-Interest Log": [
        ["Log ID", "Vendor ID", "Reviewer", "Disclosure", "Status"],
        ["COI-001", "VND-001", "Leah Moor", "No conflict disclosed", "Cleared"],
        ["COI-002", "VND-002", "Leah Moor", "No conflict disclosed", "Cleared"],
        ["COI-003", "VND-003", "Leah Moor", "No conflict disclosed", "Cleared"],
        ["COI-004", "VND-004", "Leah Moor", "No conflict disclosed", "Cleared"],
        ["COI-005", "VND-005", "Leah Moor", "No conflict disclosed", "Cleared"],
    ],
    "Award Recommendation": [
        ["Rank", "Recommended Vendor", "Rationale", "Status"],
        [
            1,
            "Northstar Analytcs",
            "Highest technical score with corrected responsive status",
            "Recommend award",
        ],
        [2, "Civic Data Works", "Strong security controls and lower price", "Reserve"],
        [3, "Harbor Systems", "Responsive but lower technical score", "Reserve"],
    ],
    "Debrief Register": [
        ["Vendor ID", "Vendor Name", "Debrief Status", "Debrief Link"],
        ["VND-001", "Civic Data Works", "Ready", "Email debrief"],
        ["VND-002", "Harbor Systems", "Ready", "Email debrief"],
        ["VND-003", "Northstar Analytcs", "Ready", "Email debrief"],
        ["VND-004", "SignalBridge Labs", "Ready", "Email debrief"],
        ["VND-005", "Westport Insight", "Ready", "Email debrief"],
    ],
    "Data Validation Guide": [
        ["Feature", "Requirement"],
        ["Named range", "VendorIDs = Vendor Register A2:A6"],
        ["Scoring validation", "Requirements Scoring B2:B16 uses =VendorIDs"],
        ["Conflict validation", "Conflict-of-Interest Log B2:B6 uses =VendorIDs"],
        ["Debrief links", "Debrief Register D2:D6 uses mailto hyperlinks"],
    ],
    "Publication Style Guide": [
        ["Element", "Requirement"],
        ["Header fill", "4F2D7F"],
        ["Header font", "White bold"],
        ["Body font", "Aptos"],
        ["Currency format", "$#,##0"],
        ["Percent format", "0%"],
        ["Tab colors", "Public color set applied"],
    ],
    "Appendix Index": [
        ["Appendix", "Description", "Owner", "Public Status"],
        ["A", "Vendor register extract", "Procurement", "Ready"],
        ["B", "Scoring summary extract", "Evaluation Panel", "Ready"],
        ["C", "Price normalization extract", "Finance", "Ready"],
        ["D", "Debrief register", "Procurement", "Ready"],
    ],
}

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


def apply_corrections(value, corrections):
    if isinstance(value, (int, float)):
        formatted = f"${value:,.0f}"
        for old, new in corrections:
            if formatted == old:
                return float(new.replace("$", "").replace(",", ""))
        return value

    corrected = str(value)
    for old, new in corrections:
        corrected = re.sub(
            rf"(?<!\w){re.escape(old)}(?!\w)",
            lambda _: new,
            corrected,
        )
    return corrected


def write_table(ws, rows):
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
            cell.number_format = "$#,##0"
    for col_letter in percent_columns:
        for cell in ws[col_letter][1:]:
            cell.number_format = "0%"

    ws.freeze_panes = f"A{header_row[0].row + 1}"
    ws.auto_filter.ref = ref
    ws.auto_filter.enable = True


wb = load_workbook(SOURCE)

# Stage 1: Read the correction instructions, then remove every internal sheet.
correction_rows = list(wb["Correction_Log_INTERNAL"].iter_rows(min_row=2, values_only=True))
corrections = [(str(old), str(new)) for old, new, *_ in correction_rows]
for sheet_name in list(wb.sheetnames):
    del wb[sheet_name]

# Stage 2: Apply fixes to the public source data before any public table is rebuilt.
public_tables = {
    name: [
        [apply_corrections(value, corrections) for value in row]
        for row in rows
    ]
    for name, rows in PUBLIC_TABLES.items()
}

# Preserve the exact required sheet order before populating the workbook.
for sheet_name in SHEET_ORDER:
    wb.create_sheet(sheet_name)
wb.active = 0

# Stage 3: Rebuild the vendor register first.
vendor_ws = wb["Vendor Register"]
write_table(vendor_ws, public_tables["Vendor Register"])

# Stage 4: Create the public vendor-ID named range.
if "VendorIDs" in wb.defined_names:
    del wb.defined_names["VendorIDs"]
wb.defined_names.add(
    DefinedName("VendorIDs", attr_text="'Vendor Register'!$A$2:$A$6")
)

# Stage 5: Rebuild scoring, price normalization, and award summary formulas.
write_table(wb["Requirements Scoring"], public_tables["Requirements Scoring"])
write_table(wb["Price Normalization"], public_tables["Price Normalization"])
write_table(wb["Conflict-of-Interest Log"], public_tables["Conflict-of-Interest Log"])
write_table(wb["Award Recommendation"], public_tables["Award Recommendation"])
write_table(wb["Debrief Register"], public_tables["Debrief Register"])
write_table(wb["Data Validation Guide"], public_tables["Data Validation Guide"])
write_table(wb["Publication Style Guide"], public_tables["Publication Style Guide"])
write_table(wb["Appendix Index"], public_tables["Appendix Index"])

summary_ws = wb["Evaluation Summary"]
summary_ws["A1"] = "Procurement Bid Evaluation Release Workbook"
summary_ws.merge_cells("A1:B1")
summary_ws["A3"] = "Responsive Vendors"
summary_ws["B3"] = '=COUNTIF(\'Vendor Register\'!E2:E6,"Responsive")'
summary_ws["A4"] = "Recommended Vendor"
summary_ws["B4"] = "='Award Recommendation'!B2"
summary_ws["A5"] = "Lowest Corrected Price"
summary_ws["B5"] = "=MIN('Price Normalization'!C2:C6)"
summary_ws["A6"] = "Average Technical Score"
summary_ws["B6"] = "=AVERAGE('Requirements Scoring'!E2:E16)"

# Stage 6: Add named-range-backed dropdown validation.
scoring_dv = DataValidation(
    type="list",
    formula1="=VendorIDs",
    allow_blank=False,
    showDropDown=False,
    errorTitle="Invalid vendor",
    error="Select a vendor ID from the Vendor Register.",
    showErrorMessage=True,
)
wb["Requirements Scoring"].add_data_validation(scoring_dv)
scoring_dv.add("B2:B16")

conflict_dv = DataValidation(
    type="list",
    formula1="=VendorIDs",
    allow_blank=False,
    showDropDown=False,
    errorTitle="Invalid vendor",
    error="Select a vendor ID from the Vendor Register.",
    showErrorMessage=True,
)
wb["Conflict-of-Interest Log"].add_data_validation(conflict_dv)
conflict_dv.add("B2:B6")

# Stage 7: Add public debrief links.
debrief_ws = wb["Debrief Register"]
for row in range(2, 7):
    vendor_id = debrief_ws[f"A{row}"].value
    subject = quote(f"Debrief {vendor_id}", safe="")
    debrief_ws[f"D{row}"].hyperlink = (
        f"mailto:procurement@city.example?subject={subject}"
    )

# Stage 8: Apply the public workbook style migration.
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
summary_ws["B5"].number_format = "$#,##0"
summary_ws["B6"].number_format = "0.0"
for row in range(4, 7):
    summary_ws.row_dimensions[row].height = 22

style_public_table(
    wb["Vendor Register"],
    "A1:E6",
)
style_public_table(
    wb["Requirements Scoring"],
    "A1:E16",
    percent_columns=("D",),
)
style_public_table(
    wb["Price Normalization"],
    "A1:D6",
    currency_columns=("C",),
)
for row in range(2, 7):
    wb["Price Normalization"][f"D{row}"].number_format = "0.0"
style_public_table(
    wb["Conflict-of-Interest Log"],
    "A1:E6",
)
style_public_table(
    wb["Award Recommendation"],
    "A1:D4",
)
style_public_table(
    wb["Debrief Register"],
    "A1:D6",
)
style_public_table(
    wb["Data Validation Guide"],
    "A1:B5",
)
style_public_table(
    wb["Publication Style Guide"],
    "A1:B7",
)
style_public_table(
    wb["Appendix Index"],
    "A1:D5",
)

for row in range(2, 7):
    debrief_ws[f"D{row}"].font = HYPERLINK_FONT

for ws in wb.worksheets:
    for row in ws.iter_rows():
        for cell in row:
            if cell.value is not None and cell.font == Font():
                cell.font = BODY_FONT

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

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
wb.save(OUTPUT)
print(OUTPUT)
