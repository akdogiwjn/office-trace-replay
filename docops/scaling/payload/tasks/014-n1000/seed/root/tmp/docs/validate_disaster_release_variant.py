"""Dynamic validator for synthetic scaled Excel 014 variants.

Reads the frozen expected.json (generated at preparation time, never
regenerated inside the loop) and checks the rebuilt workbook against it. Every
range assertion is sized from the actual data; nothing assumes the original 12
rows.

By default (formal mode) the validator REQUIRES complete LibreOffice-recalculated
formula caches in the register, dashboard, county rollup and appeal queue. A
missing, wrong or incomplete cache fails validation with a non-zero exit.

A fixture-only `--structure-only` mode skips the cache/value assertions so tiny
OOXML fixtures can be tested without LibreOffice; the formal recipes never pass
that flag.
"""
from __future__ import annotations

import argparse
import json
import os
import zipfile
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

FORBIDDEN = None  # loaded from expected.json

VALUE_CHECK_KEYS = [
    "eligible_values", "priority_values", "review_values",
    "dashboard_metrics", "rollup_values", "appeal_values",
]


def load_expected(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def cached_locations(expected: dict) -> list[tuple[str, int, int]]:
    """Every formula cell that must carry a LibreOffice cached value.

    Legal cached values of 0/False are NOT missing; only None counts as missing.
    """
    last = expected["register_range_end"]
    locs = []
    for row in range(2, last + 1):
        for col in (10, 11, 12):
            locs.append(("Eligibility Register", row, col))
    for row in range(4, 9):
        locs.append(("Funding Dashboard", row, 2))
    for row in range(2, 6):
        for col in (2, 3, 4):
            locs.append(("County Rollup", row, col))
    for row in range(2, expected["appeal_count"] + 2):
        for col in (4, 5):
            locs.append(("Appeal Queue", row, col))
    return locs


def missing_caches(values_wb, expected: dict) -> list[str]:
    missing = []
    for sheet, row, col in cached_locations(expected):
        if values_wb[sheet].cell(row, col).value is None:
            missing.append(f"{sheet}!{get_column_letter(col)}{row}")
    return missing


def check(output_path: Path, expected_path: Path, structure_only: bool = False) -> dict:
    expected = load_expected(expected_path)
    n = expected["n"]
    last = expected["register_range_end"]

    wb = load_workbook(output_path, data_only=False)
    values_wb = load_workbook(output_path, data_only=True)
    checks = {}

    checks["sheet_order"] = wb.sheetnames == [
        "Funding Dashboard", "Eligibility Register", "County Rollup",
        "Appeal Queue", "Publication Controls",
    ]
    checks["tab_colors"] = {
        ws.title: ws.sheet_properties.tabColor.rgb if ws.sheet_properties.tabColor else None
        for ws in wb.worksheets
    } == {
        "Funding Dashboard": "FF70AD47",
        "Eligibility Register": "FF5B9BD5",
        "County Rollup": "FFFFC000",
        "Appeal Queue": "FFC00000",
        "Publication Controls": "FF7030A0",
    }
    checks["freeze_panes"] = {ws.title: ws.freeze_panes for ws in wb.worksheets} == {
        "Funding Dashboard": "A4",
        "Eligibility Register": "A2",
        "County Rollup": "A2",
        "Appeal Queue": "A2",
        "Publication Controls": "A2",
    }
    checks["protected_sheets"] = (
        wb["Funding Dashboard"].protection.sheet is True
        and wb["Publication Controls"].protection.sheet is True
        and wb["Eligibility Register"].protection.sheet is not True
        and wb["County Rollup"].protection.sheet is not True
        and wb["Appeal Queue"].protection.sheet is not True
    )
    checks["protected_structure"] = wb.security.lockStructure is True

    actual_table_refs = {
        ws.title: next(iter(ws.tables.values())).ref
        for ws in wb.worksheets if ws.tables
    }
    checks["tables"] = actual_table_refs == expected["table_refs"]
    checks["auto_filters"] = all(
        wb[sheet].auto_filter.ref == expected["auto_filter"][sheet]
        for sheet in expected["auto_filter"]
    )

    register = wb["Eligibility Register"]
    register_values = values_wb["Eligibility Register"]
    checks["register_scope"] = register.max_row == last and register.max_column == 12
    actual_ids = [register.cell(row, 1).value for row in range(2, last + 1)]
    checks["deduplicated_ids"] = actual_ids == expected["valid_ids"]

    actual_inspection = [register.cell(row, 9).value for row in range(2, last + 1)]
    expected_inspection = [r["inspection_date"] for r in expected["records"]]
    checks["latest_inspection_kept"] = actual_inspection == expected_inspection

    h104_row = expected["valid_ids"].index("H-104") + 2
    h109_row = expected["valid_ids"].index("H-109") + 2
    h112_row = expected["valid_ids"].index("H-112") + 2
    checks["corrections"] = (
        register.cell(h104_row, 2).value == "North Fork"
        and register.cell(h109_row, 3).value == "Major"
        and register.cell(h112_row, 6).value == "Low"
    )
    checks["formula_columns"] = all(
        str(register.cell(row, column).value).startswith("=")
        for row in range(2, last + 1)
        for column in (10, 11, 12)
    )

    if structure_only:
        checks["caches_present"] = "skipped_structure_only"
        for key in VALUE_CHECK_KEYS:
            checks[key] = "skipped_structure_only"
    else:
        missing = missing_caches(values_wb, expected)
        checks["caches_present"] = not missing
        if missing:
            for key in VALUE_CHECK_KEYS:
                checks[key] = "missing_formula_caches"
            checks["missing_cache_cells"] = missing[:50]
        else:
            register_values = values_wb["Eligibility Register"]
            checks["eligible_values"] = (
                [register_values.cell(row, 10).value for row in range(2, last + 1)]
                == [r["eligible_amount"] for r in expected["records"]]
            )
            checks["priority_values"] = (
                [register_values.cell(row, 11).value for row in range(2, last + 1)]
                == [r["priority_score"] for r in expected["records"]]
            )
            checks["review_values"] = (
                [register_values.cell(row, 12).value for row in range(2, last + 1)]
                == [r["review_status"] for r in expected["records"]]
            )
            dashboard_values = values_wb["Funding Dashboard"]
            checks["dashboard_metrics"] = (
                [dashboard_values[f"B{row}"].value for row in range(4, 9)]
                == [expected["dashboard"]["total_applications"],
                    expected["dashboard"]["total_eligible_amount"],
                    expected["dashboard"]["senior_review_count"],
                    expected["dashboard"]["appeal_review_count"],
                    expected["dashboard"]["average_priority_score"]]
            )
            rollup_values = values_wb["County Rollup"]
            checks["rollup_values"] = {
                rollup_values.cell(row, 1).value: [rollup_values.cell(row, col).value for col in (2, 3, 4)]
                for row in range(2, 6)
            } == expected["county_rollup"]
            appeal_values = values_wb["Appeal Queue"]
            checks["appeal_values"] = (
                [tuple(appeal_values.cell(row, col).value for col in range(1, 6))
                 for row in range(2, expected["appeal_count"] + 2)]
                == [(q["app_id"], q["county"], q["damage"], q["eligible_amount"], q["review_status"])
                    for q in expected["appeal_queue"]]
            )

    cf_register = {
        str(cf.sqref): [(rule.type, rule.operator, tuple(rule.formula)) for rule in cf.rules]
        for cf in register.conditional_formatting
    }
    expected_cf = expected["conditional_formats"]
    checks["conditional_formats"] = all(
        cf_register.get(sqref) == [("cellIs", operator, (formula,))]
        for sqref, (operator, formula) in expected_cf.items()
    )
    checks["conditional_formats_cover_last_row"] = (
        any(str(cf.sqref).split(":")[0] == "K2" and str(cf.sqref).split(":")[1] == f"K{last}"
            for cf in register.conditional_formatting)
        and any(str(cf.sqref).split(":")[0] == "J2" and str(cf.sqref).split(":")[1] == f"J{last}"
                for cf in register.conditional_formatting)
    )

    currency = expected["currency_ranges"]
    currency_cells = (
        [register.cell(row, column) for row in range(2, last + 1) for column in currency["register_cols"]]
        + [wb["County Rollup"].cell(row, currency["county_col"]) for row in range(2, 6)]
        + [wb["Appeal Queue"].cell(row, currency["appeal_col"]) for row in range(2, expected["appeal_count"] + 2)]
        + [wb["Publication Controls"].cell(row, currency["controls_col"]) for row in range(2, 6)]
        + [wb["Funding Dashboard"][cell] for cell in currency["dashboard_cells"]]
    )
    checks["currency_formats"] = all(
        cell.number_format == "$#,##0;($#,##0);-" for cell in currency_cells
    )

    all_cell_text = "\n".join(
        str(cell.value)
        for ws in wb.worksheets
        for row in ws.iter_rows()
        for cell in row
        if cell.value is not None
    )
    checks["forbidden_cells"] = not any(
        phrase.lower() in all_cell_text.lower() for phrase in expected["forbidden_phrases"]
    )

    with zipfile.ZipFile(output_path) as archive:
        xml_text = "\n".join(
            archive.read(name).decode("utf-8", errors="ignore")
            for name in archive.namelist()
            if name.endswith((".xml", ".rels"))
        )
    checks["forbidden_uppercase_xml"] = (
        "DRAFT" not in xml_text and "PRIVATE" not in xml_text
    )

    formula_count = 0
    formula_errors = []
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and cell.value.startswith("="):
                    formula_count += 1
    for ws in values_wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and cell.value.startswith("#"):
                    formula_errors.append(f"{ws.title}!{cell.coordinate}:{cell.value}")
    checks["formula_count"] = formula_count == expected["formula_count"]
    checks["zero_formula_errors"] = not formula_errors

    chart = wb["Funding Dashboard"]._charts[0]
    series = chart.series[0]
    categories_formula = (
        series.cat.numRef.f if series.cat.numRef is not None else series.cat.strRef.f
    )
    checks["chart"] = (
        chart.__class__.__name__ == expected["chart"]["type"]
        and categories_formula == expected["chart"]["categories"]
        and series.val.numRef.f == expected["chart"]["values"]
    )

    return {"checks": checks,
            "mode": "structure_only" if structure_only else "formal",
            "caches_present": checks.get("caches_present") is True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=os.environ.get("VARIANT_OUTPUT"),
                        help="output workbook path")
    parser.add_argument("--expected", default=os.environ.get("VARIANT_EXPECTED", "/root/tmp/docs/expected.json"))
    parser.add_argument("--structure-only", action="store_true",
                        help="fixture mode: skip cache/value assertions (never used by formal recipes)")
    args = parser.parse_args(argv)
    if not args.output:
        parser.error("--output is required (or set VARIANT_OUTPUT)")
    result = check(Path(args.output), Path(args.expected), structure_only=args.structure_only)
    print(json.dumps(result, indent=2))
    failed = [name for name, value in result["checks"].items() if value is False]
    if failed:
        raise SystemExit(f"Validation failed: {failed}")
    if not args.structure_only and result.get("caches_present") is not True:
        raise SystemExit("Validation failed: required formula caches are missing or incomplete")
    print("All checks passed.")


if __name__ == "__main__":
    main()
