from pathlib import Path

from openpyxl import load_workbook
from openpyxl.chart import BarChart, Reference, Series
from openpyxl.chart.label import DataLabelList
from openpyxl.comments import Comment
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.table import Table, TableStyleInfo


SOURCE = Path("/root/docops_v2_l3_016_xlsx_forecast_driver_cascade_input.xlsx")
OUTPUT = Path(
    "/root/submission/docops_v2_l3_016_xlsx_forecast_driver_cascade_output.xlsx"
)

NAVY = "17365D"
BLUE = "2F75B5"
LIGHT_BLUE = "D9EAF7"
VERY_LIGHT_BLUE = "EEF5FB"
PALE_RED = "FCE4D6"
RED = "C00000"
ORANGE = "C55A11"
DARK_GRAY = "404040"
MID_GRAY = "7F8C8D"
LIGHT_GRAY = "E7E6E6"
WHITE = "FFFFFF"

THIN_GRAY = Side(style="thin", color="B7C9D6")
MEDIUM_BLUE = Side(style="medium", color=BLUE)
THIN_WHITE = Side(style="thin", color=WHITE)


def solid(color):
    return PatternFill(fill_type="solid", start_color=color, end_color=color)


def style_header(cell):
    cell.fill = solid(NAVY)
    cell.font = Font(name="Arial", size=10, bold=True, color=WHITE)
    cell.alignment = Alignment(horizontal="center", vertical="center")
    cell.border = Border(bottom=Side(style="medium", color=BLUE))


def set_cell(cell, value, *, font=None, fill=None, fmt=None, align=None, border=None):
    cell.value = value
    if font is not None:
        cell.font = font
    if fill is not None:
        cell.fill = fill
    if fmt is not None:
        cell.number_format = fmt
    if align is not None:
        cell.alignment = align
    if border is not None:
        cell.border = border


wb = load_workbook(SOURCE)
wb.calculation.fullCalcOnLoad = True
wb.calculation.forceFullCalc = True
wb.calculation.calcMode = "auto"
wb.properties.title = "Scenario-Driven Forecast Dashboard"
wb.properties.subject = "Forecast model, exception review, and dashboard cascade"
wb.properties.creator = "Forecast Operations"

assumptions = wb["Assumptions"]
demand_raw = wb["Demand Raw"]
dashboard = wb["Dashboard"]
archive = wb["Archive"]

forecast = wb.create_sheet("Forecast Model")
exceptions = wb.create_sheet("Exception Review")

for ws in (assumptions, demand_raw, dashboard, forecast, exceptions, archive):
    ws.sheet_view.showGridLines = False
    for row in ws.iter_rows():
        for cell in row:
            cell.font = Font(name="Arial", size=10)

# Assumptions: retain B5 as the only primary scenario control.
assumptions.merge_cells("A1:A1")
for cell in assumptions[1]:
    style_header(cell)

assumption_labels = {
    "A2": "Unit Growth",
    "A3": "Price",
    "A4": "Capacity",
    "A5": "Scenario",
}
for coord, label in assumption_labels.items():
    cell = assumptions[coord]
    set_cell(
        cell,
        label,
        font=Font(name="Arial", size=10, bold=True, color=DARK_GRAY),
        fill=solid(VERY_LIGHT_BLUE),
        align=Alignment(vertical="center"),
        border=Border(bottom=THIN_GRAY),
    )

for row in range(2, 6):
    for col in range(2, 4):
        cell = assumptions.cell(row=row, column=col)
        cell.font = Font(name="Arial", size=10, bold=row == 5, color="0000FF")
        cell.fill = solid(LIGHT_BLUE if row < 5 else "FFF2CC")
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = Border(bottom=THIN_GRAY, left=THIN_GRAY, right=THIN_GRAY)

for cell in ("B2", "C2"):
    assumptions[cell].number_format = "0.0%;(0.0%);-"
for cell in ("B3", "C3"):
    assumptions[cell].number_format = '$#,##0.00;($#,##0.00);-'
for cell in ("B4", "C4"):
    assumptions[cell].number_format = "#,##0;-#,##0;-"

assumptions["B5"].number_format = "@"
assumptions["B5"].fill = solid("FFFF00")
assumptions["B5"].border = Border(
    left=MEDIUM_BLUE, right=MEDIUM_BLUE, top=MEDIUM_BLUE, bottom=MEDIUM_BLUE
)
assumptions["B5"].comment = Comment(
    "Primary scenario driver. Select Base or Stress. Forecast Model, "
    "Exception Review, and Dashboard recalculate from this cell.",
    "Forecast Operations",
)

scenario_validation = DataValidation(
    type="list",
    formula1="$B$1:$C$1",
    allow_blank=False,
    showDropDown=False,
    showErrorMessage=True,
    errorTitle="Select a valid scenario",
    error="Choose Base or Stress from the available scenario headers.",
    promptTitle="Scenario driver",
    prompt="Select Base or Stress. All downstream outputs recalculate.",
)
scenario_validation.add("B5")
assumptions.add_data_validation(scenario_validation)

assumptions.merge_cells("A7:C8")
set_cell(
    assumptions["A7"],
    "Editable scenario driver: B5. Scenario names are defined in B1:C1; "
    "all forecast, exception, and dashboard outputs update from this control.",
    font=Font(name="Arial", size=9, italic=True, color=DARK_GRAY),
    fill=solid(VERY_LIGHT_BLUE),
    align=Alignment(wrap_text=True, vertical="top"),
)
for row in assumptions["A7:C8"]:
    for cell in row:
        cell.fill = solid(VERY_LIGHT_BLUE)

assumptions.column_dimensions["A"].width = 20
assumptions.column_dimensions["B"].width = 16
assumptions.column_dimensions["C"].width = 16
assumptions.row_dimensions[1].height = 24
for row in range(2, 6):
    assumptions.row_dimensions[row].height = 24
assumptions.freeze_panes = "A2"
assumptions.sheet_properties.tabColor = "FFC000"

# Demand Raw stays as the source of the four demand months, but is hidden for release.
for cell in demand_raw[1]:
    style_header(cell)
for row in demand_raw.iter_rows(min_row=2, max_row=5, min_col=1, max_col=3):
    for cell in row:
        cell.font = Font(
            name="Arial",
            size=10,
            color=DARK_GRAY if cell.column == 1 else "0000FF",
            bold=cell.column == 1,
        )
        cell.fill = solid(WHITE if cell.row % 2 == 0 else VERY_LIGHT_BLUE)
        cell.border = Border(bottom=THIN_GRAY)
        cell.alignment = Alignment(
            horizontal="left" if cell.column == 1 else "right", vertical="center"
        )
        if cell.column > 1:
            cell.number_format = "#,##0;-#,##0;-"
demand_raw.column_dimensions["A"].width = 13
demand_raw.column_dimensions["B"].width = 16
demand_raw.column_dimensions["C"].width = 16
demand_raw.row_dimensions[1].height = 24
demand_raw.freeze_panes = "A2"
demand_raw.sheet_properties.tabColor = MID_GRAY

# Forecast Model: a native table with the required nine columns in order.
model_headers = [
    "Month",
    "Base Units",
    "Actual Units",
    "Scenario Growth",
    "Forecast Units",
    "Price",
    "Revenue",
    "Capacity",
    "Capacity Flag",
]
for col, header in enumerate(model_headers, 1):
    set_cell(forecast.cell(row=1, column=col), header)
    style_header(forecast.cell(row=1, column=col))

for row in range(2, 6):
    source_row = row
    forecast.cell(row=row, column=1, value=f"='Demand Raw'!A{source_row}")
    forecast.cell(row=row, column=2, value=f"='Demand Raw'!B{source_row}")
    forecast.cell(row=row, column=3, value=f"='Demand Raw'!C{source_row}")
    forecast.cell(
        row=row,
        column=4,
        value=(
            "=INDEX(Assumptions!$B$2:$C$2,1,"
            "MATCH(Assumptions!$B$5,Assumptions!$B$1:$C$1,0))"
        ),
    )
    forecast.cell(row=row, column=5, value=f"=$B{row}*(1+$D{row})")
    forecast.cell(
        row=row,
        column=6,
        value=(
            "=INDEX(Assumptions!$B$3:$C$3,1,"
            "MATCH(Assumptions!$B$5,Assumptions!$B$1:$C$1,0))"
        ),
    )
    forecast.cell(row=row, column=7, value=f"=$E{row}*$F{row}")
    forecast.cell(
        row=row,
        column=8,
        value=(
            "=INDEX(Assumptions!$B$4:$C$4,1,"
            "MATCH(Assumptions!$B$5,Assumptions!$B$1:$C$1,0))"
        ),
    )
    forecast.cell(
        row=row,
        column=9,
        value=f'=IF($E{row}>$H{row},"Breach","OK")',
    )

    for col in range(1, 10):
        cell = forecast.cell(row=row, column=col)
        cell.border = Border(bottom=THIN_GRAY)
        cell.alignment = Alignment(
            horizontal="left" if col == 1 else "right", vertical="center"
        )
    forecast.cell(row=row, column=1).font = Font(
        name="Arial", size=10, bold=True, color=DARK_GRAY
    )
    for col in (2, 3):
        forecast.cell(row=row, column=col).font = Font(
            name="Arial", size=10, color="008000"
        )
    for col in (2, 3, 8):
        forecast.cell(row=row, column=col).number_format = "#,##0;-#,##0;-"
    forecast.cell(row=row, column=4).number_format = "0.0%;(0.0%);-"
    forecast.cell(row=row, column=5).number_format = "#,##0.0;(#,##0.0);-"
    forecast.cell(row=row, column=6).number_format = '$#,##0.00;($#,##0.00);-'
    forecast.cell(row=row, column=7).number_format = "$#,##0;($#,##0);-"
    forecast.cell(row=row, column=9).alignment = Alignment(horizontal="center")
    forecast.row_dimensions[row].height = 23

model_table = Table(displayName="ForecastModel", ref="A1:I5")
model_table.tableStyleInfo = TableStyleInfo(
    name="TableStyleMedium2",
    showFirstColumn=False,
    showLastColumn=False,
    showRowStripes=True,
    showColumnStripes=False,
)
forecast.add_table(model_table)

# A hidden helper ranks breach months so Exception Review remains formula-driven.
forecast["J1"] = "Breach Rank"
for row in range(2, 6):
    forecast.cell(
        row=row,
        column=10,
        value=f'=IF($I{row}="Breach",COUNTIF($I$2:$I{row},"Breach"),"")',
    )
    forecast.cell(row=row, column=10).font = Font(
        name="Arial", size=9, color=MID_GRAY
    )
    forecast.cell(row=row, column=10).alignment = Alignment(horizontal="center")

forecast.conditional_formatting.add(
    "A2:I5",
    FormulaRule(
        formula=['$I2="Breach"'],
        fill=solid(PALE_RED),
        font=Font(name="Arial", size=10, color=DARK_GRAY),
    ),
)
forecast.conditional_formatting.add(
    "I2:I5",
    FormulaRule(
        formula=['$I2="Breach"'],
        fill=solid(RED),
        font=Font(name="Arial", size=10, bold=True, color=WHITE),
    ),
)

forecast["I2"].comment = Comment(
    "Capacity Flag is formula-driven: Breach when Forecast Units exceed Capacity.",
    "Forecast Operations",
)
forecast.column_dimensions["A"].width = 12
forecast.column_dimensions["B"].width = 14
forecast.column_dimensions["C"].width = 14
forecast.column_dimensions["D"].width = 18
forecast.column_dimensions["E"].width = 17
forecast.column_dimensions["F"].width = 12
forecast.column_dimensions["G"].width = 15
forecast.column_dimensions["H"].width = 14
forecast.column_dimensions["I"].width = 16
forecast.column_dimensions["J"].hidden = True
forecast.column_dimensions["J"].width = 12
forecast.row_dimensions[1].height = 25
forecast.freeze_panes = "B2"
forecast.auto_filter.ref = "A1:I5"
forecast.sheet_properties.tabColor = BLUE
forecast.print_title_rows = "1:1"
forecast.sheet_properties.pageSetUpPr.fitToPage = True
forecast.page_setup.fitToWidth = 1
forecast.page_setup.fitToHeight = 1

# Exception Review: two formula-selected slots cover the current Stress scenario's
# two breach months and clear automatically when no breach exists.
exception_headers = ["Month", "Capacity Issue", "Forecast Units", "Capacity", "Overage"]
for col, header in enumerate(exception_headers, 1):
    set_cell(exceptions.cell(row=1, column=col), header)
    style_header(exceptions.cell(row=1, column=col))

for row in range(2, 4):
    rank_formula = f"ROWS($A$2:A{row})"
    exceptions.cell(
        row=row,
        column=1,
        value=(
            f'=IFERROR(INDEX(\'Forecast Model\'!$A$2:$A$5,'
            f'MATCH({rank_formula},\'Forecast Model\'!$J$2:$J$5,0)),"")'
        ),
    )
    exceptions.cell(
        row=row,
        column=2,
        value=(
            f'=IF($A{row}="","","Forecast exceeds capacity by "&'
            f'TEXT($E{row},"#,##0.0")&" units")'
        ),
    )
    exceptions.cell(
        row=row,
        column=3,
        value=(
            f'=IF($A{row}="","",INDEX(\'Forecast Model\'!$E$2:$E$5,'
            f'MATCH($A{row},\'Forecast Model\'!$A$2:$A$5,0)))'
        ),
    )
    exceptions.cell(
        row=row,
        column=4,
        value=(
            f'=IF($A{row}="","",INDEX(\'Forecast Model\'!$H$2:$H$5,'
            f'MATCH($A{row},\'Forecast Model\'!$A$2:$A$5,0)))'
        ),
    )
    exceptions.cell(
        row=row,
        column=5,
        value=f'=IF($A{row}="","",MAX($C{row}-$D{row},0))',
    )
    for col in range(1, 6):
        cell = exceptions.cell(row=row, column=col)
        cell.fill = solid(PALE_RED)
        cell.border = Border(bottom=THIN_GRAY)
        cell.alignment = Alignment(
            horizontal="left" if col in (1, 2) else "right",
            vertical="center",
            wrap_text=col == 2,
        )
    exceptions.cell(row=row, column=1).font = Font(
        name="Arial", size=10, bold=True, color=DARK_GRAY
    )
    exceptions.cell(row=row, column=3).number_format = "#,##0.0;(#,##0.0);-"
    exceptions.cell(row=row, column=4).number_format = "#,##0;-#,##0;-"
    exceptions.cell(row=row, column=5).number_format = "#,##0.0;(#,##0.0);-"
    exceptions.row_dimensions[row].height = 36

exception_table = Table(displayName="ExceptionReview", ref="A1:E3")
exception_table.tableStyleInfo = TableStyleInfo(
    name="TableStyleMedium2",
    showFirstColumn=False,
    showLastColumn=False,
    showRowStripes=False,
    showColumnStripes=False,
)
exceptions.add_table(exception_table)
exceptions.column_dimensions["A"].width = 13
exceptions.column_dimensions["B"].width = 43
exceptions.column_dimensions["C"].width = 18
exceptions.column_dimensions["D"].width = 15
exceptions.column_dimensions["E"].width = 15
exceptions.row_dimensions[1].height = 25
exceptions.freeze_panes = "A2"
exceptions.sheet_properties.tabColor = ORANGE
exceptions.print_title_rows = "1:1"
exceptions.sheet_properties.pageSetUpPr.fitToPage = True
exceptions.page_setup.fitToWidth = 1
exceptions.page_setup.fitToHeight = 1

# Dashboard: scenario title, formula-backed KPIs, an exception watch area, and chart.
dashboard.merge_cells("A1:H1")
set_cell(
    dashboard["A1"],
    '="Forecast Dashboard - "&Assumptions!$B$5&" Scenario"',
    font=Font(name="Arial", size=22, bold=True, color=WHITE),
    fill=solid(NAVY),
    align=Alignment(horizontal="left", vertical="center"),
)
for row in dashboard["A1:H1"]:
    for cell in row:
        cell.fill = solid(NAVY)

dashboard.merge_cells("A2:H2")
set_cell(
    dashboard["A2"],
    (
        '="Scenario-driven forecast  |  Driver: Assumptions!B5  |  '
        'Updated from ForecastModel"'
    ),
    font=Font(name="Arial", size=10, italic=True, color=DARK_GRAY),
    fill=solid(LIGHT_GRAY),
    align=Alignment(horizontal="left", vertical="center"),
)
for row in dashboard["A2:H2"]:
    for cell in row:
        cell.fill = solid(LIGHT_GRAY)

kpi_cards = [
    ("A4:B4", "A5:B5", "SELECTED SCENARIO", "=Assumptions!$B$5", "@"),
    ("C4:D4", "C5:D5", "FORECAST UNITS", "=SUM('Forecast Model'!$E$2:$E$5)", "#,##0.0"),
    ("E4:F4", "E5:F5", "TOTAL REVENUE", "=SUM('Forecast Model'!$G$2:$G$5)", "$#,##0;($#,##0);-"),
    (
        "G4:H4",
        "G5:H5",
        "CAPACITY BREACHES",
        '=COUNTIF(\'Forecast Model\'!$I$2:$I$5,"Breach")',
        "0;0;0",
    ),
]

for label_range, value_range, label, formula, fmt in kpi_cards:
    dashboard.merge_cells(label_range)
    dashboard.merge_cells(value_range)
    label_cell = dashboard[label_range.split(":")[0]]
    value_cell = dashboard[value_range.split(":")[0]]
    set_cell(
        label_cell,
        label,
        font=Font(name="Arial", size=9, bold=True, color=WHITE),
        fill=solid(BLUE),
        align=Alignment(horizontal="center", vertical="center"),
        border=Border(
            left=THIN_WHITE, right=THIN_WHITE, top=THIN_WHITE, bottom=THIN_WHITE
        ),
    )
    set_cell(
        value_cell,
        formula,
        font=Font(name="Arial", size=16, bold=True, color=NAVY),
        fill=solid(VERY_LIGHT_BLUE),
        fmt=fmt,
        align=Alignment(horizontal="center", vertical="center"),
        border=Border(
            left=THIN_WHITE,
            right=THIN_WHITE,
            top=THIN_WHITE,
            bottom=MEDIUM_BLUE,
        ),
    )
    for row in dashboard[label_range]:
        for cell in row:
            cell.fill = solid(BLUE)
            cell.border = Border(
                left=THIN_WHITE,
                right=THIN_WHITE,
                top=THIN_WHITE,
                bottom=THIN_WHITE,
            )
    for row in dashboard[value_range]:
        for cell in row:
            cell.fill = solid(VERY_LIGHT_BLUE)
            cell.border = Border(
                left=THIN_WHITE,
                right=THIN_WHITE,
                top=THIN_WHITE,
                bottom=MEDIUM_BLUE,
            )

kpi_cards_2 = [
    (
        "A7:B7",
        "A8:B8",
        "TOTAL OVERAGE",
        (
            "=SUMPRODUCT(('Forecast Model'!$I$2:$I$5=\"Breach\")*"
            "('Forecast Model'!$E$2:$E$5-'Forecast Model'!$H$2:$H$5))"
        ),
        "#,##0.0;(#,##0.0);-",
    ),
    (
        "C7:D7",
        "C8:D8",
        "PEAK FORECAST UNITS",
        "=MAX('Forecast Model'!$E$2:$E$5)",
        "#,##0.0;(#,##0.0);-",
    ),
    (
        "E7:F7",
        "E8:F8",
        "AVERAGE PRICE",
        "=AVERAGE('Forecast Model'!$F$2:$F$5)",
        "$#,##0.00;($#,##0.00);-",
    ),
    (
        "G7:H7",
        "G8:H8",
        "MONTHS IN MODEL",
        "=COUNTA('Forecast Model'!$A$2:$A$5)",
        "0;0;0",
    ),
]

for label_range, value_range, label, formula, fmt in kpi_cards_2:
    dashboard.merge_cells(label_range)
    dashboard.merge_cells(value_range)
    label_cell = dashboard[label_range.split(":")[0]]
    value_cell = dashboard[value_range.split(":")[0]]
    set_cell(
        label_cell,
        label,
        font=Font(name="Arial", size=9, bold=True, color=WHITE),
        fill=solid(BLUE),
        align=Alignment(horizontal="center", vertical="center"),
        border=Border(
            left=THIN_WHITE, right=THIN_WHITE, top=THIN_WHITE, bottom=THIN_WHITE
        ),
    )
    set_cell(
        value_cell,
        formula,
        font=Font(name="Arial", size=16, bold=True, color=NAVY),
        fill=solid(VERY_LIGHT_BLUE),
        fmt=fmt,
        align=Alignment(horizontal="center", vertical="center"),
        border=Border(
            left=THIN_WHITE,
            right=THIN_WHITE,
            top=THIN_WHITE,
            bottom=MEDIUM_BLUE,
        ),
    )
    for row in dashboard[label_range]:
        for cell in row:
            cell.fill = solid(BLUE)
            cell.border = Border(
                left=THIN_WHITE,
                right=THIN_WHITE,
                top=THIN_WHITE,
                bottom=THIN_WHITE,
            )
    for row in dashboard[value_range]:
        for cell in row:
            cell.fill = solid(VERY_LIGHT_BLUE)
            cell.border = Border(
                left=THIN_WHITE,
                right=THIN_WHITE,
                top=THIN_WHITE,
                bottom=MEDIUM_BLUE,
            )

dashboard.conditional_formatting.add(
    "G5:H5",
    FormulaRule(
        formula=["G5>0"],
        fill=solid(RED),
        font=Font(name="Arial", size=16, bold=True, color=WHITE),
    ),
)

dashboard.merge_cells("A11:H11")
set_cell(
    dashboard["A11"],
    "EXCEPTION WATCH",
    font=Font(name="Arial", size=11, bold=True, color=WHITE),
    fill=solid(ORANGE),
    align=Alignment(horizontal="left", vertical="center"),
)
for row in dashboard["A11:H11"]:
    for cell in row:
        cell.fill = solid(ORANGE)

watch_headers = [
    ("A12:B12", "MONTH"),
    ("C12:D12", "FORECAST UNITS"),
    ("E12:F12", "CAPACITY"),
    ("G12:H12", "OVERAGE"),
]
for cell_range, text in watch_headers:
    dashboard.merge_cells(cell_range)
    cell = dashboard[cell_range.split(":")[0]]
    set_cell(
        cell,
        text,
        font=Font(name="Arial", size=9, bold=True, color=DARK_GRAY),
        fill=solid(PALE_RED),
        align=Alignment(horizontal="center", vertical="center"),
        border=Border(bottom=THIN_GRAY),
    )
    for row in dashboard[cell_range]:
        for merged_cell in row:
            merged_cell.fill = solid(PALE_RED)
            merged_cell.border = Border(bottom=THIN_GRAY)

for row in (13, 14):
    source_row = row - 11
    watch_cells = [
        ("A", "B", f"='Exception Review'!A{source_row}", "@"),
        ("C", "D", f"='Exception Review'!C{source_row}", "#,##0.0;(#,##0.0);-"),
        ("E", "F", f"='Exception Review'!D{source_row}", "#,##0;-#,##0;-"),
        ("G", "H", f"='Exception Review'!E{source_row}", "#,##0.0;(#,##0.0);-"),
    ]
    for first_col, second_col, formula, fmt in watch_cells:
        cell_range = f"{first_col}{row}:{second_col}{row}"
        dashboard.merge_cells(cell_range)
        cell = dashboard[f"{first_col}{row}"]
        set_cell(
            cell,
            formula,
            font=Font(
                name="Arial",
                size=10,
                bold=first_col == "A",
                color=DARK_GRAY,
            ),
            fill=solid(WHITE if row == 13 else VERY_LIGHT_BLUE),
            fmt=fmt,
            align=Alignment(horizontal="center", vertical="center"),
            border=Border(bottom=THIN_GRAY),
        )
        for merged_row in dashboard[cell_range]:
            for merged_cell in merged_row:
                merged_cell.fill = solid(WHITE if row == 13 else VERY_LIGHT_BLUE)
                merged_cell.border = Border(bottom=THIN_GRAY)
    dashboard.row_dimensions[row].height = 23

dashboard.merge_cells("A16:H16")
set_cell(
    dashboard["A16"],
    (
        "Review every capacity breach before publishing. Exception rows and "
        "dashboard totals recalculate from the ForecastModel table."
    ),
    font=Font(name="Arial", size=9, italic=True, color=MID_GRAY),
    align=Alignment(horizontal="left", vertical="center", wrap_text=True),
)
for row in dashboard["A16:H16"]:
    for cell in row:
        cell.fill = solid(WHITE)

chart = BarChart()
chart.type = "col"
chart.style = 10
chart.title = "Monthly Forecast vs Capacity"
chart.y_axis.title = "Units"
chart.x_axis.title = "Demand Month"
chart.y_axis.majorGridlines = None
chart.legend.position = "b"
chart.gapWidth = 55
chart.overlap = -8
chart.height = 7.8
chart.width = 15.2

data = Reference(forecast, min_col=5, max_col=5, min_row=1, max_row=5)
capacity = Reference(forecast, min_col=8, max_col=8, min_row=1, max_row=5)
categories = Reference(forecast, min_col=1, min_row=2, max_row=5)
chart.add_data(data, titles_from_data=True)
chart.add_data(Reference(forecast, min_col=8, min_row=1, max_row=5), titles_from_data=True)
chart.set_categories(categories)
chart.series[0].graphicalProperties.solidFill = BLUE
chart.series[0].graphicalProperties.line.solidFill = BLUE
chart.series[1].graphicalProperties.solidFill = "F4B183"
chart.series[1].graphicalProperties.line.solidFill = ORANGE
chart.dLbls = DataLabelList()
chart.dLbls.showVal = True
chart.dLbls.showSerName = False
chart.dLbls.showCatName = False
dashboard.add_chart(chart, "A18")

for col_letter, width in {
    "A": 14,
    "B": 14,
    "C": 14,
    "D": 14,
    "E": 17,
    "F": 14,
    "G": 16,
    "H": 16,
}.items():
    dashboard.column_dimensions[col_letter].width = width
dashboard.row_dimensions[1].height = 42
dashboard.row_dimensions[2].height = 22
dashboard.row_dimensions[4].height = 22
dashboard.row_dimensions[5].height = 34
dashboard.row_dimensions[7].height = 22
dashboard.row_dimensions[8].height = 34
dashboard.row_dimensions[11].height = 24
dashboard.row_dimensions[12].height = 22
dashboard.sheet_properties.tabColor = NAVY
dashboard.sheet_view.zoomScale = 90
dashboard.sheet_properties.pageSetUpPr.fitToPage = True
dashboard.page_setup.orientation = "landscape"
dashboard.page_setup.paperSize = dashboard.PAPERSIZE_A4
dashboard.page_setup.fitToWidth = 1
dashboard.page_setup.fitToHeight = 1
dashboard.print_area = "A1:H34"

# Archive retains its placeholder and is hidden for release.
archive["A1"].font = Font(name="Arial", size=10, color=MID_GRAY)
archive["A1"].fill = solid(LIGHT_GRAY)
archive.sheet_properties.tabColor = MID_GRAY

# Release order and visibility.
release_order = [
    "Dashboard",
    "Forecast Model",
    "Exception Review",
    "Assumptions",
    "Demand Raw",
    "Archive",
]
wb._sheets = [wb[name] for name in release_order]
wb["Demand Raw"].sheet_state = "hidden"
wb["Archive"].sheet_state = "hidden"
wb.active = wb.sheetnames.index("Dashboard")

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
wb.save(OUTPUT)
print(OUTPUT)
