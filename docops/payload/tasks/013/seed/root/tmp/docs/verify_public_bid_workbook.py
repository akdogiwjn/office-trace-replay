import json
import re
import zipfile
from pathlib import Path

from openpyxl import load_workbook


OUTPUT = Path(
    "/root/submission/"
    "docops_v2_l3_013_xlsx_procurement_bid_evaluation_release_output.xlsx"
)
METADATA = Path("/root/task_metadata.json")


def normalized_color(value):
    if not value:
        return None
    return value[-6:].upper()


def normalized_formula(value):
    return str(value).lstrip("=")


def main():
    expected = json.loads(METADATA.read_text())["verifier_expectations"]
    wb = load_workbook(OUTPUT, data_only=False)
    values_wb = load_workbook(OUTPUT, data_only=True)

    assert wb.sheetnames == expected["sheet_order"]
    assert all(wb[name].sheet_state == "visible" for name in wb.sheetnames)
    assert len(wb.sheetnames) == 10

    for sheet_name, color in expected["tab_colors"].items():
        assert normalized_color(wb[sheet_name].sheet_properties.tabColor.rgb) == color

    all_text = []
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if cell.value is not None:
                    all_text.append(str(cell.value))
                if cell.hyperlink and cell.hyperlink.target:
                    all_text.append(cell.hyperlink.target)
    for phrase in expected["forbidden_phrases"]:
        assert all(phrase.lower() not in text.lower() for text in all_text), phrase

    for name, target in expected["named_ranges"].items():
        assert name in wb.defined_names
        assert wb.defined_names[name].attr_text == target

    for item in expected["data_validations"]:
        validations = wb[item["sheet"]].data_validations.dataValidation
        matches = [
            dv
            for dv in validations
            if str(dv.sqref) == item["sqref"]
            and dv.type == "list"
            and normalized_formula(dv.formula1)
            == normalized_formula(item["formula1"])
        ]
        assert len(matches) == 1, item

    for coord, target in expected["hyperlinks"].items():
        sheet_name, cell_ref = coord.split("!")
        assert wb[sheet_name][cell_ref].hyperlink.target == target

    for coord, formula in expected["summary_cells"].items():
        assert wb["Evaluation Summary"][coord].value == formula
    assert values_wb["Evaluation Summary"]["B3"].value == 4
    assert values_wb["Evaluation Summary"]["B4"].value == "Northstar Analytics"
    assert values_wb["Evaluation Summary"]["B5"].value == 1110000
    assert abs(values_wb["Evaluation Summary"]["B6"].value - 83.4) < 1e-9

    for sheet_name, rows in expected["tables"].items():
        ws = wb[sheet_name]
        actual = [
            [ws.cell(row, col).value for col in range(1, len(rows[0]) + 1)]
            for row in range(1, len(rows) + 1)
        ]
        assert actual == rows, sheet_name

    for coord in expected["currency_cells"]:
        sheet_name, cell_ref = coord.split("!")
        assert "$#,##0" in wb[sheet_name][cell_ref].number_format
    for coord in expected["percent_cells"]:
        sheet_name, cell_ref = coord.split("!")
        assert wb[sheet_name][cell_ref].number_format == expected["percent_format"]

    table_ranges = {
        "Evaluation Summary": "A3:B6",
        "Vendor Register": "A1:E6",
        "Requirements Scoring": "A1:E16",
        "Price Normalization": "A1:D6",
        "Conflict-of-Interest Log": "A1:E6",
        "Award Recommendation": "A1:D4",
        "Debrief Register": "A1:D6",
        "Data Validation Guide": "A1:B5",
        "Publication Style Guide": "A1:B7",
        "Appendix Index": "A1:D5",
    }
    for sheet_name, table_ref in table_ranges.items():
        ws = wb[sheet_name]
        header_row = 3 if sheet_name == "Evaluation Summary" else 1
        assert ws.freeze_panes is not None
        assert ws.auto_filter.ref == table_ref
        for cell in ws[header_row]:
            assert normalized_color(cell.fill.fgColor.rgb) == expected["header_fill"]
            assert cell.font.name == expected["body_font"]
            assert cell.font.bold
            assert normalized_color(cell.font.color.rgb) == expected["header_font"]

    summary_title = wb["Evaluation Summary"]["A1"]
    assert normalized_color(summary_title.fill.fgColor.rgb) == expected[
        "summary_title_fill"
    ]
    assert summary_title.font.name == expected["body_font"]
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if cell.value is not None:
                    assert cell.font.name == expected["body_font"], (
                        ws.title,
                        cell.coordinate,
                        cell.font.name,
                    )

    error_pattern = re.compile(r"#(REF!|DIV/0!|VALUE!|NAME\?|N/A|NUM!|NULL!)")
    for ws in values_wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                assert not (
                    isinstance(cell.value, str) and error_pattern.search(cell.value)
                ), (ws.title, cell.coordinate, cell.value)

    with zipfile.ZipFile(OUTPUT) as archive:
        assert archive.testzip() is None

    print(
        json.dumps(
            {
                "status": "success",
                "sheet_count": len(wb.sheetnames),
                "formula_count": sum(
                    1
                    for ws in wb.worksheets
                    for row in ws.iter_rows()
                    for cell in row
                    if isinstance(cell.value, str) and cell.value.startswith("=")
                ),
                "responsive_vendors": values_wb["Evaluation Summary"]["B3"].value,
                "recommended_vendor": values_wb["Evaluation Summary"]["B4"].value,
                "lowest_price": values_wb["Evaluation Summary"]["B5"].value,
                "average_score": values_wb["Evaluation Summary"]["B6"].value,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
