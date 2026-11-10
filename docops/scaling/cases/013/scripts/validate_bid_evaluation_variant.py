"""Dynamic validator for synthetic scaled Excel 013 variants.

Reads the frozen expected.json (generated at prepare time, never regenerated in
the loop) and checks the rebuilt workbook against it. Every range assertion is
sized from the actual vendor count; nothing assumes the original five vendors.

In formal mode the validator REQUIRES complete LibreOffice-recalculated formula
caches in the Evaluation Summary and in every Price Normalization row. A
missing or incomplete cache fails validation with a non-zero exit. Only ``None``
counts as missing; legal cached values of 0/False are not missing.

A fixture-only ``--structure-only`` mode skips the cache/value assertions so
tiny OOXML fixtures can be tested without LibreOffice; the formal recipes never
pass that flag.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import zipfile
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

ERROR_PATTERN = re.compile(r"#(REF!|DIV/0!|VALUE!|NAME\?|N/A|NUM!|NULL!)")

VALUE_CHECK_KEYS = ["summary_values", "price_score_values"]


def load_expected(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def cached_locations(expected: dict) -> list[tuple[str, int, int]]:
    """Every formula cell that must carry a LibreOffice cached value."""
    last = expected["register_range_end"]
    locs = [("Evaluation Summary", row, 2) for row in range(3, 7)]
    locs += [("Price Normalization", row, 4) for row in range(2, last + 1)]
    return locs


def missing_caches(values_wb, expected: dict) -> list[str]:
    missing = []
    for sheet, row, col in cached_locations(expected):
        if values_wb[sheet].cell(row, col).value is None:
            missing.append(f"{sheet}!{get_column_letter(col)}{row}")
    return missing


def _close(a, b, tol=1e-9):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) <= tol
    return a == b


def check(output_path: Path, expected_path: Path, structure_only: bool = False) -> dict:
    expected = load_expected(expected_path)
    if expected.get("kind") != "xlsx":
        raise ValueError(f"not an XLSX expectation file: {expected_path}")
    n = expected["n"]
    last = expected["register_range_end"]
    scoring_last = expected["scoring_range_end"]

    wb = load_workbook(output_path, data_only=False)
    values_wb = load_workbook(output_path, data_only=True)
    # Capture max_row before any cell access: openpyxl creates empty cells when
    # `ws.cell(row, col)` is read past the current extent, which would otherwise
    # mask a truncated/removed last row.
    max_rows = {ws.title: ws.max_row for ws in wb.worksheets}
    checks = {}

    checks["sheet_order"] = wb.sheetnames == [
        "Evaluation Summary", "Vendor Register", "Requirements Scoring",
        "Price Normalization", "Conflict-of-Interest Log", "Award Recommendation",
        "Debrief Register", "Data Validation Guide", "Publication Style Guide",
        "Appendix Index",
    ]
    checks["sheet_visibility"] = all(
        wb[name].sheet_state == "visible" for name in wb.sheetnames)
    checks["tab_colors"] = {
        ws.title: (ws.sheet_properties.tabColor.rgb[-6:].upper()
                   if ws.sheet_properties.tabColor else None)
        for ws in wb.worksheets
    } == expected["tabs"]

    actual_table_refs = {
        ws.title: ws.auto_filter.ref for ws in wb.worksheets
        if ws.auto_filter.ref is not None
    }
    checks["auto_filters"] = all(
        wb[sheet].auto_filter.ref == ref
        for sheet, ref in expected["table_ranges"].items()
    )
    checks["freeze_panes"] = all(
        wb[sheet].freeze_panes is not None
        for sheet in expected["table_ranges"]
    )

    # ---- Vendor Register: every vendor, first/middle/last included ----------
    register = wb["Vendor Register"]
    actual_ids = [register.cell(row, 1).value for row in range(2, last + 1)]
    checks["vendor_ids"] = actual_ids == expected["vendor_ids"]
    actual_names = [register.cell(row, 2).value for row in range(2, last + 1)]
    checks["vendor_names"] = actual_names == [r["name"] for r in expected["records"]]
    checks["vendor_contacts"] = (
        [register.cell(row, 3).value for row in range(2, last + 1)]
        == [r["contact"] for r in expected["records"]]
    )
    checks["vendor_evaluators"] = (
        [register.cell(row, 4).value for row in range(2, last + 1)]
        == [r["evaluator"] for r in expected["records"]]
    )
    checks["vendor_statuses"] = (
        [register.cell(row, 5).value for row in range(2, last + 1)]
        == [r["status"] for r in expected["records"]]
    )
    checks["register_row_count"] = max_rows["Vendor Register"] == last

    # ---- Requirements Scoring: all 3N rows ---------------------------------
    scoring = wb["Requirements Scoring"]
    checks["scoring_row_count"] = max_rows["Requirements Scoring"] == scoring_last
    expected_scoring = expected["scoring_rows"]
    checks["scoring_req_ids"] = (
        [scoring.cell(row, 1).value for row in range(2, scoring_last + 1)]
        == [r["req_id"] for r in expected_scoring]
    )
    checks["scoring_vendor_ids"] = (
        [scoring.cell(row, 2).value for row in range(2, scoring_last + 1)]
        == [r["vendor_id"] for r in expected_scoring]
    )
    checks["scoring_weights"] = all(
        _close(scoring.cell(row, 4).value, expected_scoring[row - 2]["weight"])
        for row in range(2, scoring_last + 1)
    )
    checks["scoring_scores"] = (
        [scoring.cell(row, 5).value for row in range(2, scoring_last + 1)]
        == [r["score"] for r in expected_scoring]
    )

    # ---- Price Normalization: every row, including the last formula --------
    price = wb["Price Normalization"]
    checks["price_row_count"] = max_rows["Price Normalization"] == last
    checks["price_values"] = all(
        _close(price.cell(row, 3).value, expected["records"][row - 2]["corrected_price"])
        for row in range(2, last + 1)
    )
    expected_formula = expected["price_formula_row1"]
    checks["price_formulas"] = all(
        str(price.cell(row, 4).value)
        == f"=MIN($C$2:$C${last})/C{row}*100"
        for row in range(2, last + 1)
    )
    checks["last_row_formula_present"] = (
        isinstance(price.cell(last, 4).value, str)
        and price.cell(last, 4).value.startswith("=")
        and str(price.cell(last, 4).value) == expected["price_formula_last"]
    )
    checks["price_formula_scope"] = expected_formula == f"=MIN($C$2:$C${last})/C2*100"

    # ---- COI ---------------------------------------------------------------
    coi = wb["Conflict-of-Interest Log"]
    checks["coi_row_count"] = max_rows["Conflict-of-Interest Log"] == last
    checks["coi_rows"] = (
        [tuple(coi.cell(row, col).value for col in range(1, 6))
         for row in range(2, last + 1)]
        == [(c["log_id"], c["vendor_id"], c["reviewer"], c["disclosure"], c["status"])
            for c in expected["coi_rows"]]
    )

    # ---- Award Recommendation (top 3) --------------------------------------
    award = wb["Award Recommendation"]
    checks["award_rows"] = (
        [tuple(award.cell(row, col).value for col in (1, 2, 4))
         for row in range(2, 5)]
        == [(a["rank"], a["vendor_name"], a["status"]) for a in expected["award"]]
    )

    # ---- Evaluation Summary formulas ---------------------------------------
    summary = wb["Evaluation Summary"]
    checks["summary_formulas"] = all(
        summary[coord].value == formula
        for coord, formula in expected["summary_formulas"].items()
    )

    # ---- Named range and data validations ----------------------------------
    checks["named_range"] = (
        "VendorIDs" in wb.defined_names
        and wb.defined_names["VendorIDs"].attr_text == expected["named_range"]
    )
    dv_ok = True
    dv_report = {}
    for sheet, sqref in expected["data_validations"].items():
        matches = [
            dv for dv in wb[sheet].data_validations.dataValidation
            if str(dv.sqref) == sqref
            and dv.type == "list"
            and str(dv.formula1).lstrip("=") == "VendorIDs"
        ]
        dv_report[sheet] = len(matches) == 1
        dv_ok = dv_ok and dv_report[sheet]
    checks["data_validations"] = dv_ok

    # ---- Debrief hyperlinks ------------------------------------------------
    debrief = wb["Debrief Register"]
    link_ok = True
    for row in range(2, last + 1):
        vid = debrief.cell(row, 1).value
        target = debrief.cell(row, 4).hyperlink.target if debrief.cell(row, 4).hyperlink else None
        if not target or not target.startswith("mailto:") or vid not in target:
            link_ok = False
            break
    checks["debrief_hyperlinks"] = link_ok

    # ---- Cache / value checks ----------------------------------------------
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
            summary_values = values_wb["Evaluation Summary"]
            checks["summary_values"] = (
                summary_values["B3"].value == expected["summary"]["responsive_vendors"]
                and summary_values["B4"].value == expected["summary"]["recommended_vendor"]
                and _close(summary_values["B5"].value,
                           expected["summary"]["lowest_corrected_price"])
                and _close(summary_values["B6"].value,
                           expected["summary"]["average_technical_score"])
            )
            price_values = values_wb["Price Normalization"]
            checks["price_score_values"] = all(
                _close(price_values.cell(row, 4).value,
                       expected["price_scores"][row - 2])
                for row in range(2, last + 1)
            )

    # ---- Forbidden material (visible text and hyperlinks) ------------------
    texts = []
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if cell.value is not None:
                    texts.append(str(cell.value))
                if cell.hyperlink and cell.hyperlink.target:
                    texts.append(cell.hyperlink.target)
    all_text = "\n".join(texts)
    lowered = all_text.lower()
    checks["forbidden_cells"] = not any(
        phrase.lower() in lowered for phrase in expected["forbidden_phrases"])

    # ---- No formula errors, correct formula count, zip integrity -----------
    formula_count = sum(
        1 for ws in wb.worksheets for row in ws.iter_rows() for cell in row
        if isinstance(cell.value, str) and cell.value.startswith("=")
    )
    checks["formula_count"] = formula_count == expected["formula_count"]
    error_cells = [
        f"{ws.title}!{cell.coordinate}:{cell.value}"
        for ws in values_wb.worksheets for row in ws.iter_rows() for cell in row
        if isinstance(cell.value, str) and ERROR_PATTERN.search(cell.value)
    ]
    checks["zero_formula_errors"] = not error_cells
    if error_cells:
        checks["error_cells"] = error_cells[:50]
    with zipfile.ZipFile(output_path) as archive:
        checks["zip_integrity"] = archive.testzip() is None

    checks["middle_vendor_facts"] = (
        n >= 3
        and actual_ids[n // 2] == expected["vendor_ids"][n // 2]
        and actual_names[n // 2] == expected["records"][n // 2]["name"]
    )

    return {
        "checks": checks,
        "mode": "structure_only" if structure_only else "formal",
        "vendor_count": n,
        "caches_present": checks.get("caches_present") is True,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=os.environ.get("VARIANT_OUTPUT"),
                        help="output workbook path")
    parser.add_argument("--expected",
                        default=os.environ.get("VARIANT_EXPECTED", "/root/tmp/docs/expected.json"))
    parser.add_argument("--report",
                        default=os.environ.get("VARIANT_REPORT", "/root/tmp/docs/output_validation.json"))
    parser.add_argument("--structure-only", action="store_true",
                        help="fixture mode: skip cache/value assertions (never used by formal recipes)")
    args = parser.parse_args(argv)
    if not args.output:
        parser.error("--output is required (or set VARIANT_OUTPUT)")
    result = check(Path(args.output), Path(args.expected), structure_only=args.structure_only)
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    failed = [name for name, value in result["checks"].items() if value is False]
    if failed:
        raise SystemExit(f"Validation failed: {failed}")
    if not args.structure_only and result.get("caches_present") is not True:
        raise SystemExit("Validation failed: required formula caches are missing or incomplete")
    print("All checks passed.")


if __name__ == "__main__":
    main()
