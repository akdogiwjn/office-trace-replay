"""Dynamic validator for synthetic scaled Excel 016 variants.

Reads the frozen expected.json (generated at prepare time, never regenerated in
the loop) and checks the rebuilt workbook against it. Every range assertion is
sized from the actual unit count.

Formal mode verifies the COMPLETE business values, not just formulas and flags:
- every Forecast Model row (month, base, actual, growth, forecast, price,
  revenue, capacity, flag, breach rank, unit) against the frozen per-scenario
  rows;
- every Demand Raw row business value;
- every Exception Review row (unit, month, forecast, capacity, overage) against
  the complete default-scenario breach list;
- the dashboard KPIs, the two watch rows and the four-period chart summary
  caches and values;
- the native chart's TWO series (category and value references for both series
  and their names);
- the delivered workbook's OWN caches first, then the Base and Stress scenario
  cascade on copies (never on the delivered output), verifying full model
  values, KPIs, exceptions and four-period chart sums per scenario.

Only ``None`` counts as missing (a formula cell whose legitimate result is an
empty string, such as Breach Rank on non-breach rows, is oracle-proven empty).
Legal cached 0/False are handled by field type, never treated as missing, and
an error string or unexpected type always fails.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

ERROR_PATTERN = re.compile(r"#(REF!|DIV/0!|VALUE!|NAME\?|N/A|NUM!|NULL!)")

MODEL_COLUMNS = 11
EXCEPTION_COLUMNS = 6
KPI_CELLS = ["A5", "C5", "E5", "G5", "A8", "C8", "E8", "G8"]
WATCH_CELLS = ["A13", "C13", "E13", "G13", "A14", "C14", "E14", "G14"]

DEFAULT_RECALC = "/root/.codex/skills/xlsx/scripts/recalc.py"


def load_expected(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _close(a, b, tol=1e-6):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) <= tol
    return a == b


def _value_matches(actual, expected) -> bool:
    """Field-type-aware comparison: numeric tolerance for numerics, exact for
    strings/booleans; an error string or a type mismatch always fails."""
    if isinstance(expected, bool) or isinstance(actual, bool):
        return actual is expected
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return _close(actual, expected)
    if isinstance(actual, str) and isinstance(expected, str):
        return actual == expected
    return False


def model_row_cell_map() -> list[tuple[str, int]]:
    return [
        ("month", 1), ("base", 2), ("actual", 3), ("growth", 4),
        ("forecast", 5), ("price", 6), ("revenue", 7), ("capacity", 8),
        ("flag", 9), ("rank", 10), ("unit", 11),
    ]


def expected_ranks(rows: list[dict]) -> list:
    ranks = []
    count = 0
    for r in rows:
        if r["flag"] == "Breach":
            count += 1
            ranks.append(count)
        else:
            ranks.append(None)
    return ranks


def verify_model_rows(values_wb, rows: list[dict]) -> list[str]:
    errors = []
    sheet = values_wb["Forecast Model"]
    ranks = expected_ranks(rows)
    for index, exp in enumerate(rows):
        row = 2 + index
        for field, col in model_row_cell_map():
            actual = sheet.cell(row, col).value
            if field == "rank":
                expected = ranks[index]
                if expected is None:
                    if actual not in (None, ""):
                        errors.append(f"Model!{get_column_letter(col)}{row}: expected empty rank")
                elif not _value_matches(actual, expected):
                    errors.append(f"Model!{get_column_letter(col)}{row}: rank {actual!r} != {expected!r}")
            else:
                if not _value_matches(actual, exp[field]):
                    errors.append(f"Model!{get_column_letter(col)}{row}: {field} {actual!r} != {exp[field]!r}")
    return errors


def verify_demand_raw(values_wb, rows: list[dict]) -> list[str]:
    errors = []
    sheet = values_wb["Demand Raw"]
    for index, exp in enumerate(rows):
        row = 2 + index
        if not _value_matches(sheet.cell(row, 1).value, exp["month"]):
            errors.append(f"Demand Raw!A{row}: month {sheet.cell(row, 1).value!r}")
        if not _value_matches(sheet.cell(row, 2).value, exp["base"]):
            errors.append(f"Demand Raw!B{row}: base {sheet.cell(row, 2).value!r}")
        if not _value_matches(sheet.cell(row, 3).value, exp["actual"]):
            errors.append(f"Demand Raw!C{row}: actual {sheet.cell(row, 3).value!r}")
        if not _value_matches(sheet.cell(row, 4).value, exp["unit"]):
            errors.append(f"Demand Raw!D{row}: unit {sheet.cell(row, 4).value!r}")
    return errors


def _parse_issue(text: str):
    """Parse 'Forecast exceeds capacity by <N> units'; returns the numeric or None."""
    if not isinstance(text, str):
        return None
    m = re.fullmatch(r"Forecast exceeds capacity by ([0-9,]+\.?[0-9]*) units", text.strip())
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def verify_exception_rows_full(values_wb, expected: dict, scenario: str) -> list[str]:
    errors = []
    sheet = values_wb["Exception Review"]
    if scenario == expected["default_scenario"]:
        exc = expected["exception_slots"]
    else:
        exc = []
    total_rows = expected["exception_last_row"] - expected["exception_first_row"] + 1
    for index in range(total_rows):
        row = expected["exception_first_row"] + index
        if index < len(exc):
            exp = exc[index]
            if not _value_matches(sheet.cell(row, 1).value, exp["unit"]):
                errors.append(f"Exception!A{row}: unit {sheet.cell(row, 1).value!r}")
            if not _value_matches(sheet.cell(row, 2).value, exp["month"]):
                errors.append(f"Exception!B{row}: month {sheet.cell(row, 2).value!r}")
            if not _value_matches(sheet.cell(row, 4).value, exp["forecast"]):
                errors.append(f"Exception!D{row}: forecast {sheet.cell(row, 4).value!r}")
            if not _value_matches(sheet.cell(row, 5).value, exp["capacity"]):
                errors.append(f"Exception!E{row}: capacity {sheet.cell(row, 5).value!r}")
            if not _value_matches(sheet.cell(row, 6).value, exp["overage"]):
                errors.append(f"Exception!F{row}: overage {sheet.cell(row, 6).value!r}")
            # C is the human-readable issue text and must describe the OVERAGE
            # (not the forecast). Parse and compare its numeric semantically.
            # The text is rounded to one decimal by TEXT(...,"#,##0.0"), so a
            # 0.051 tolerance covers the rounding of a 2-decimal overage.
            issue = _parse_issue(sheet.cell(row, 3).value)
            if issue is None:
                errors.append(f"Exception!C{row}: issue text missing/unparseable: "
                              f"{sheet.cell(row, 3).value!r}")
            elif not _close(issue, exp["overage"], tol=0.051):
                errors.append(f"Exception!C{row}: issue text numeric {issue} != overage "
                              f"{exp['overage']}")
            elif _close(issue, exp["forecast"]):
                errors.append(f"Exception!C{row}: issue text uses forecast {issue} "
                              "instead of overage")
        else:
            for col in (1, 2, 3, 4, 5, 6):
                if sheet.cell(row, col).value not in (None, ""):
                    errors.append(f"Exception!{get_column_letter(col)}{row}: expected empty slot")
    return errors


def verify_kpis(values_wb, kpis: dict) -> list[str]:
    errors = []
    dashboard = values_wb["Dashboard"]
    pairs = [
        ("A5", "selected_scenario", True), ("C5", "forecast_units", True),
        ("E5", "total_revenue", True), ("G5", "capacity_breaches", True),
        ("A8", "total_overage", True), ("C8", "peak_forecast_units", True),
        ("E8", "average_price", True), ("G8", "model_records", True),
    ]
    for coord, field, numeric in pairs:
        if not _value_matches(dashboard[coord].value, kpis[field]):
            errors.append(f"Dashboard!{coord}: {dashboard[coord].value!r} != {kpis[field]!r}")
    return errors


def verify_period_sums(values_wb, expected: dict, scenario: str) -> list[str]:
    errors = []
    sums = expected["scenario_period_sums"][scenario]
    ps = expected["period_summary"]
    dashboard = values_wb["Dashboard"]
    expected_labels = ps["periods"]
    actual_labels = [dashboard.cell(ps["first_data_row"] + offset, 1).value
                     for offset in range(expected["periods"])]
    if actual_labels != list(expected_labels):
        errors.append(f"Dashboard period labels {actual_labels!r} != {list(expected_labels)!r}")
    for offset in range(expected["periods"]):
        row = ps["first_data_row"] + offset
        if not _value_matches(dashboard.cell(row, 2).value, sums["forecast"][offset]):
            errors.append(f"Dashboard!B{row}: {dashboard.cell(row, 2).value!r}")
        if not _value_matches(dashboard.cell(row, 3).value, sums["capacity"][offset]):
            errors.append(f"Dashboard!C{row}: {dashboard.cell(row, 3).value!r}")
    return errors


def verify_watch(values_wb, expected: dict, scenario: str) -> list[str]:
    errors = []
    if scenario == expected["default_scenario"]:
        exc = expected["exception_slots"]
    else:
        exc = []
    dashboard = values_wb["Dashboard"]
    for slot_index, row in enumerate((13, 14)):
        if slot_index < len(exc):
            exp = exc[slot_index]
            if not _value_matches(dashboard[f"A{row}"].value, exp["month"]):
                errors.append(f"Dashboard!A{row}: {dashboard[f'A{row}'].value!r}")
            if not _value_matches(dashboard[f"C{row}"].value, exp["forecast"]):
                errors.append(f"Dashboard!C{row}")
            if not _value_matches(dashboard[f"E{row}"].value, exp["capacity"]):
                errors.append(f"Dashboard!E{row}")
            if not _value_matches(dashboard[f"G{row}"].value, exp["overage"]):
                errors.append(f"Dashboard!G{row}")
        else:
            for col in ("A", "C", "E", "G"):
                if dashboard[f"{col}{row}"].value not in (None, ""):
                    errors.append(f"Dashboard!{col}{row}: expected empty watch slot")
    return errors


def _chart_ref(ref) -> str | None:
    if ref is None:
        return None
    if ref.numRef is not None:
        return ref.numRef.f
    if ref.strRef is not None:
        return ref.strRef.f
    return None


def verify_chart(wb, expected: dict) -> list[str]:
    errors = []
    dashboard = wb["Dashboard"]
    if len(dashboard._charts) != 1:
        return ["dashboard chart count != 1"]
    chart = dashboard._charts[0]
    if chart.__class__.__name__ != "BarChart":
        return ["dashboard chart is not BarChart"]
    series = chart.series
    if len(series) != 2:
        return [f"dashboard chart series != 2 ({len(series)})"]
    cat0 = _chart_ref(series[0].cat)
    cat1 = _chart_ref(series[1].cat)
    val0 = _chart_ref(series[0].val)
    val1 = _chart_ref(series[1].val)
    exp = expected["chart"]
    expected_cat = exp["categories_ref"].replace("'", "")
    if str(cat0).replace("'", "") != expected_cat:
        errors.append(f"chart series0 cat {cat0!r}")
    if str(cat1).replace("'", "") != expected_cat:
        errors.append(f"chart series1 cat {cat1!r}")
    if str(val0).replace("'", "") != exp["series"][0]["values_ref"].replace("'", ""):
        errors.append(f"chart series0 val {val0!r}")
    if str(val1).replace("'", "") != exp["series"][1]["values_ref"].replace("'", ""):
        errors.append(f"chart series1 val {val1!r}")
    names = []
    for s in series:
        if s.tx is not None and s.tx.strRef is not None:
            names.append(s.tx.strRef.f)
        elif s.tx is not None and s.tx.v is not None:
            names.append(str(s.tx.v))
        else:
            names.append(None)
    for name, expected_series in zip(names, exp["series"]):
        expected_name = expected_series["name"]
        expected_cell = expected_series["name_cell"].replace("'", "")
        ok = (str(name).replace("'", "") == expected_cell
              or name == expected_name
              or (isinstance(name, str) and expected_name in name))
        if not ok:
            errors.append(f"chart series name {name!r} != {expected_name!r}")
    return errors


def missing_caches(values_wb, expected: dict) -> list[str]:
    m = expected["model_range_end"]
    flags = expected["scenario_flags"][expected["default_scenario"]]
    missing = []

    for row in range(2, m + 1):
        breach_row = flags[row - 2] == "Breach"
        for col in range(1, MODEL_COLUMNS + 1):
            if col == 10 and not breach_row:
                continue  # Breach Rank is oracle-proven empty on non-breach rows
            if values_wb["Forecast Model"].cell(row, col).value is None:
                missing.append(f"Forecast Model!{get_column_letter(col)}{row}")

    for row in range(expected["exception_first_row"], expected["exception_last_row"] + 1):
        for col in range(1, EXCEPTION_COLUMNS + 1):
            if values_wb["Exception Review"].cell(row, col).value is None:
                missing.append(f"Exception Review!{get_column_letter(col)}{row}")

    for coord in KPI_CELLS:
        if values_wb["Dashboard"][coord].value is None:
            missing.append(f"Dashboard!{coord}")

    for coord in WATCH_CELLS:
        if values_wb["Dashboard"][coord].value is None:
            missing.append(f"Dashboard!{coord}")

    ps = expected["period_summary"]
    for row in range(ps["first_data_row"], ps["last_data_row"] + 1):
        for col in (2, 3):
            if values_wb["Dashboard"].cell(row, col).value is None:
                missing.append(f"Dashboard!{get_column_letter(col)}{row}")

    return missing


def check(output_path: Path, expected_path: Path, structure_only: bool = False) -> dict:
    expected = load_expected(expected_path)
    if expected.get("kind") != "xlsx":
        raise ValueError(f"not an XLSX expectation file: {expected_path}")
    n = expected["business_units"]
    m = expected["model_range_end"]
    default = expected["default_scenario"]

    wb = load_workbook(output_path, data_only=False)
    values_wb = load_workbook(output_path, data_only=True)
    checks = {}

    checks["sheet_order"] = wb.sheetnames == expected["release_order"]
    checks["sheet_visibility"] = (
        all(wb[name].sheet_state == "visible"
            for name in wb.sheetnames if name not in expected["hidden_sheets"])
        and all(wb[name].sheet_state == "hidden"
                for name in expected["hidden_sheets"])
    )

    assumptions = wb["Assumptions"]
    checks["assumption_scenarios"] = (
        assumptions["B1"].value == "Base" and assumptions["C1"].value == "Stress")
    checks["assumption_facts"] = (
        _close(assumptions["B2"].value, expected["scenarios"]["Base"]["growth"])
        and _close(assumptions["C2"].value, expected["scenarios"]["Stress"]["growth"])
        and _close(assumptions["B3"].value, expected["scenarios"]["Base"]["price"])
        and _close(assumptions["C3"].value, expected["scenarios"]["Stress"]["price"])
        and _close(assumptions["B4"].value, expected["scenarios"]["Base"]["capacity"])
        and _close(assumptions["C4"].value, expected["scenarios"]["Stress"]["capacity"])
    )
    checks["assumption_default_scenario"] = (
        assumptions["B5"].value == default)
    checks["scenario_dropdown"] = any(
        dv.type == "list" and str(dv.sqref) == "B5"
        and str(dv.formula1).lstrip("=") == "$B$1:$C$1"
        for dv in assumptions.data_validations.dataValidation)
    checks["scenario_driver_yellow"] = (
        assumptions["B5"].fill.fgColor.rgb is not None
        and assumptions["B5"].fill.fgColor.rgb.upper().endswith("FFFF00"))

    demand = wb["Demand Raw"]
    checks["demand_row_count"] = demand.max_row == m

    forecast = wb["Forecast Model"]
    checks["model_row_count"] = forecast.max_row == m
    checks["model_headers"] = (
        [forecast.cell(1, col).value for col in range(1, 10)]
        == expected["model_headers"]
    )
    templates = expected["model_formula_templates"]
    columns = list(templates.keys())
    formula_ok = True
    for row in range(2, m + 1):
        for offset, column in enumerate(columns):
            expected_formula = templates[column].format(row=row)
            if forecast.cell(row, offset + 1).value != expected_formula:
                formula_ok = False
                break
        if not formula_ok:
            break
    checks["model_formulas"] = formula_ok
    checks["conditional_formats_cover_all_rows"] = any(
        str(cf.sqref) == f"A2:I{m}" for cf in forecast.conditional_formatting) and any(
        str(cf.sqref) == f"I2:I{m}" for cf in forecast.conditional_formatting)

    exceptions = wb["Exception Review"]
    checks["exception_row_count"] = (
        exceptions.max_row == expected["exception_last_row"])
    checks["exception_headers"] = (
        [exceptions.cell(1, col).value for col in range(1, EXCEPTION_COLUMNS + 1)]
        == expected["exception_headers"])
    exc_templates = expected["exception_formula_templates"]
    exc_formula_ok = True
    for row in range(expected["exception_first_row"], expected["exception_last_row"] + 1):
        for col, header in enumerate(exc_templates, 1):
            expected_formula = exc_templates[header].format(r=row)
            if exceptions.cell(row, col).value != expected_formula:
                exc_formula_ok = False
                break
        if not exc_formula_ok:
            break
    checks["exception_formulas"] = exc_formula_ok

    dashboard = wb["Dashboard"]
    checks["dashboard_title_formula"] = (
        isinstance(dashboard["A1"].value, str)
        and dashboard["A1"].value.startswith("=")
        and "Assumptions!$B$5" in dashboard["A1"].value)
    checks["dashboard_kpi_formulas"] = all(
        dashboard[coord].value == formula
        for coord, formula in expected["kpi_formulas"].items())
    checks["dashboard_watch_formulas"] = all(
        dashboard[coord].value == formula
        for coord, formula in expected["watch_formulas"].items())
    checks["period_summary_formulas"] = all(
        dashboard[coord].value == formula
        for coord, formula in expected["period_summary"]["formulas"].items())
    checks["chart"] = not verify_chart(wb, expected)

    checks["dashboard_print_single_page"] = (
        dashboard.page_setup.fitToWidth == 1
        and dashboard.page_setup.fitToHeight == 1)
    checks["forecast_print_multi_page"] = (
        forecast.page_setup.fitToWidth == 1
        and forecast.page_setup.fitToHeight == 0)
    checks["exception_print_multi_page"] = (
        exceptions.page_setup.fitToWidth == 1
        and exceptions.page_setup.fitToHeight == 0)

    if structure_only:
        checks["caches_present"] = "skipped_structure_only"
        checks["model_values"] = "skipped_structure_only"
        checks["demand_values"] = "skipped_structure_only"
        checks["exception_values"] = "skipped_structure_only"
        checks["kpi_values"] = "skipped_structure_only"
        checks["period_summary_values"] = "skipped_structure_only"
        checks["watch_values"] = "skipped_structure_only"
    else:
        missing = missing_caches(values_wb, expected)
        checks["caches_present"] = not missing
        if missing:
            checks["missing_cache_cells"] = missing[:50]
            checks["model_values"] = "missing_formula_caches"
            checks["demand_values"] = "missing_formula_caches"
            checks["exception_values"] = "missing_formula_caches"
            checks["kpi_values"] = "missing_formula_caches"
            checks["period_summary_values"] = "missing_formula_caches"
            checks["watch_values"] = "missing_formula_caches"
        else:
            checks["model_values"] = not verify_model_rows(
                values_wb, expected["scenario_rows"][default])
            checks["demand_values"] = not verify_demand_raw(
                values_wb, expected["demand_raw_rows"])
            checks["exception_values"] = not verify_exception_rows_full(
                values_wb, expected, default)
            checks["kpi_values"] = not verify_kpis(values_wb, expected["dashboard"])
            checks["period_summary_values"] = not verify_period_sums(
                values_wb, expected, default)
            checks["watch_values"] = not verify_watch(values_wb, expected, default)

    all_text = "\n".join(
        str(cell.value)
        for ws in wb.worksheets for row in ws.iter_rows() for cell in row
        if cell.value is not None)
    lowered = all_text.lower()
    checks["forbidden_cells"] = not any(
        phrase.lower() in lowered for phrase in expected["forbidden_phrases"])

    error_cells = [
        f"{ws.title}!{cell.coordinate}:{cell.value}"
        for ws in values_wb.worksheets for row in ws.iter_rows() for cell in row
        if isinstance(cell.value, str) and ERROR_PATTERN.search(cell.value)]
    checks["zero_formula_errors"] = not error_cells
    if error_cells:
        checks["error_cells"] = error_cells[:50]
    with zipfile.ZipFile(output_path) as archive:
        checks["zip_integrity"] = archive.testzip() is None

    return {
        "checks": checks,
        "mode": "structure_only" if structure_only else "formal",
        "business_units": n,
        "model_rows": expected["model_rows"],
        "exceptions": expected["breach_count"],
        "caches_present": checks.get("caches_present") is True,
    }


def _recalc(path: Path, recalc_py: Path):
    subprocess.run([sys.executable, str(recalc_py), str(path), "120"],
                   check=True, capture_output=True)


def scenario_switch_check(output_path: Path, expected: dict,
                          recalc_py: Path) -> dict:
    """Formal scenario cascade on COPIES (never on the delivered output): for
    Base and Stress, recalc and verify full model values, KPIs, the complete
    exception table and the four-period chart sums against the frozen oracle."""
    results = {}
    with tempfile.TemporaryDirectory(prefix="docops016_scenario_") as temp_dir:
        for scenario in ("Base", "Stress"):
            lake = Path(temp_dir) / f"{scenario}.xlsx"
            shutil.copy(output_path, lake)
            wb = load_workbook(lake)
            wb["Assumptions"]["B5"] = scenario
            wb.save(lake)
            _recalc(lake, recalc_py)
            values = load_workbook(lake, data_only=True)
            results[scenario] = {
                "model_values_ok": not verify_model_rows(
                    values, expected["scenario_rows"][scenario]),
                "kpi_values_ok": not verify_kpis(
                    values, expected["scenario_kpis"][scenario]),
                "exception_values_ok": not verify_exception_rows_full(
                    values, expected, scenario),
                "period_summary_values_ok": not verify_period_sums(
                    values, expected, scenario),
                "watch_values_ok": not verify_watch(values, expected, scenario),
            }
            values.close()
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=os.environ.get("VARIANT_OUTPUT"),
                        help="output workbook path")
    parser.add_argument("--expected",
                        default=os.environ.get("VARIANT_EXPECTED", "/root/tmp/docs/expected.json"))
    parser.add_argument("--report",
                        default=os.environ.get("VARIANT_REPORT", "/root/tmp/docs/output_validation.json"))
    parser.add_argument("--structure-only", action="store_true",
                        help="fixture mode: skip cache/value and scenario recalc (never used by formal recipes)")
    parser.add_argument("--recalc", default=DEFAULT_RECALC,
                        help="recalc.py path used by the formal scenario cascade check")
    args = parser.parse_args(argv)
    if not args.output:
        parser.error("--output is required (or set VARIANT_OUTPUT)")
    output_path = Path(args.output)
    expected_path = Path(args.expected)
    result = check(output_path, expected_path, structure_only=args.structure_only)

    if not args.structure_only:
        expected = load_expected(expected_path)
        recalc_py = Path(args.recalc)
        if recalc_py.is_file():
            switch = scenario_switch_check(output_path, expected, recalc_py)
            result["scenario_switch"] = switch
            for scenario, values in switch.items():
                for key, value in values.items():
                    result["checks"][f"scenario_switch_{scenario}_{key}"] = value
        else:
            result["checks"]["scenario_switch_available"] = False
            result["scenario_switch"] = {"error": f"recalc script not found: {recalc_py}"}

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
