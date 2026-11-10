"""Small directed checks for the scaled Excel 016 synthetic variants.

Runs tiny fixtures only: input synthesis, the independent expectation
implementation, and the parameterized builder/validator on micro inputs. No
LibreOffice recalc, no PDF export, no full-scale processing is performed here.
Formula caches are injected into the fixture OOXML directly to exercise the
validator's formal cache/value checks and the Base/Stress scenario-cascade
assertions without LibreOffice.

Regression coverage for the round-3 audit findings R1/R2:
- last model row forecast / revenue / capacity cache wrong must fail;
- last chart-data-source cell cache missing or wrong must fail;
- Demand Raw last row tampered must fail;
- a scenario-switch row value wrong while its Breach flag stays unchanged must
  fail;
- legal zero caches pass (Base scenario breaches=0 / overage=0);
- deleting the last exception, replacing it with the first unit's data, or
  wrong exception identity while the count is right must fail;
- a chart that misses the last unit's four-period contribution must fail.
"""
from __future__ import annotations

import importlib
import hashlib
import json
import random
import re
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "docops"))

from openpyxl import load_workbook

synth = importlib.import_module("scaling.cases.016.synth")
expected_mod = importlib.import_module("scaling.cases.016.expected")
bld = importlib.import_module("scaling.cases.016.scripts.build_forecast_dashboard_variant")
validate = importlib.import_module("scaling.cases.016.scripts.validate_forecast_dashboard_variant")
common = importlib.import_module("scaling.cases.common")

SHEET_FILES = {
    "Dashboard": "xl/worksheets/sheet1.xml",
    "Forecast Model": "xl/worksheets/sheet2.xml",
    "Exception Review": "xl/worksheets/sheet3.xml",
    "Assumptions": "xl/worksheets/sheet4.xml",
    "Demand Raw": "xl/worksheets/sheet5.xml",
    "Archive": "xl/worksheets/sheet6.xml",
}


def make_fixture(directory: Path, n: int = 2, seed: int = 7):
    units = synth.make_units(n, random.Random(seed))
    units_path = synth.write_units_json("016-u100", units, "in.xlsx", directory)
    synth.write_input_workbook(units, directory / "in.xlsx")
    data = json.loads(units_path.read_text(encoding="utf-8"))
    data["input_path"] = str(directory / "in.xlsx")
    units_path.write_text(json.dumps(data), encoding="utf-8")
    out = directory / "out.xlsx"
    bld.build(units_path, out)
    expected_path = directory / "expected.json"
    exp = expected_mod.write_expected("016-u100", units_path, expected_path)
    return units_path, out, expected_path, exp


def inject_cached_values(xlsx_path, cells_by_sheet):
    def _escape(value):
        if isinstance(value, str):
            return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return str(value)

    def inject(xml, ref, value):
        is_str = isinstance(value, str)
        t_attr = ' t="str"' if is_str else ""
        pat = re.compile(rf'<c r="{ref}"([^>]*)>(.*?)</c>', re.DOTALL)
        match = pat.search(xml)
        if not match:
            return xml
        attrs, body = match.group(1), match.group(2)
        formula = re.search(r"<f\b[^>]*>.*?</f>", body, re.DOTALL)
        if not formula:
            return xml
        attrs = re.sub(r'\s+t="[^"]*"', "", attrs)
        new_cell = (f'<c r="{ref}"{attrs}{t_attr}>'
                    f'{formula.group(0)}<v>{_escape(value)}</v></c>')
        return pat.sub(lambda _match: new_cell, xml, count=1)

    tmp = xlsx_path.with_suffix(".inject.tmp.xlsx")
    with zipfile.ZipFile(xlsx_path) as zin, zipfile.ZipFile(
            tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename in SHEET_FILES.values():
                xml = data.decode("utf-8")
                for sheet, mapping in cells_by_sheet.items():
                    if item.filename == SHEET_FILES[sheet]:
                        for ref, value in mapping.items():
                            xml = inject(xml, ref, value)
                data = xml.encode("utf-8")
            zout.writestr(item, data)
    tmp.replace(xlsx_path)


def model_cache(rows):
    cells = {}
    rank = 0
    for index, row in enumerate(rows, start=2):
        if row["flag"] == "Breach":
            rank += 1
            breach_rank = rank
        else:
            breach_rank = ""
        values = {
            "A": row["month"], "B": row["base"], "C": row["actual"],
            "D": row["growth"], "E": row["forecast"], "F": row["price"],
            "G": row["revenue"], "H": row["capacity"], "I": row["flag"],
            "J": breach_rank, "K": row["unit"],
        }
        for column, value in values.items():
            cells[f"{column}{index}"] = value
    return cells


def dashboard_cache(kpis, slots, period_sums):
    cells = {
        "A5": kpis["selected_scenario"], "C5": kpis["forecast_units"],
        "E5": kpis["total_revenue"], "G5": kpis["capacity_breaches"],
        "A8": kpis["total_overage"], "C8": kpis["peak_forecast_units"],
        "E8": kpis["average_price"], "G8": kpis["model_records"],
    }
    for index, row in enumerate((13, 14)):
        if index < len(slots):
            slot = slots[index]
            cells[f"A{row}"] = slot["month"]
            cells[f"C{row}"] = slot["forecast"]
            cells[f"E{row}"] = slot["capacity"]
            cells[f"G{row}"] = slot["overage"]
        else:
            for col in ("A", "C", "E", "G"):
                cells[f"{col}{row}"] = ""
    for offset in range(len(period_sums["forecast"])):
        row = 21 + offset
        cells[f"B{row}"] = period_sums["forecast"][offset]
        cells[f"C{row}"] = period_sums["capacity"][offset]
    return cells


def exception_cache(exp, slots):
    cells = {}
    for index, slot in enumerate(slots, start=2):
        cells[f"A{index}"] = slot["unit"]
        cells[f"B{index}"] = slot["month"]
        cells[f"C{index}"] = (
            f"Forecast exceeds capacity by {slot['overage']:.1f} units")
        cells[f"D{index}"] = slot["forecast"]
        cells[f"E{index}"] = slot["capacity"]
        cells[f"F{index}"] = slot["overage"]
    return cells


def full_cache_map(exp):
    rows = exp["rows"]
    default = exp["default_scenario"]
    return {
        "Forecast Model": model_cache(rows),
        "Exception Review": exception_cache(exp, exp["exception_slots"]),
        "Dashboard": dashboard_cache(exp["dashboard"], exp["exception_slots"],
                                     exp["scenario_period_sums"][default]),
    }


def base_cache_map(exp):
    base_rows = expected_mod.row_records(
        [
            {
                "id": uid,
                "base_units": [r["base"] for r in exp["rows"] if r["unit"] == uid],
                "actual_units": [r["actual"] for r in exp["rows"] if r["unit"] == uid],
            }
            for uid in exp["unit_ids"]
        ],
        "Base",
    )
    kpis = {
        "selected_scenario": "Base",
        "forecast_units": sum(r["forecast"] for r in base_rows),
        "total_revenue": sum(r["revenue"] for r in base_rows),
        "capacity_breaches": 0,
        "total_overage": 0,
        "peak_forecast_units": max(r["forecast"] for r in base_rows),
        "average_price": base_rows[0]["price"],
        "model_records": len(base_rows),
    }
    sums = expected_mod.period_sums(
        [
            {
                "id": uid,
                "base_units": [r["base"] for r in exp["rows"] if r["unit"] == uid],
            }
            for uid in exp["unit_ids"]
        ],
        "Base",
    )
    return {
        "Forecast Model": model_cache(base_rows),
        "Exception Review": {},
        "Dashboard": dashboard_cache(kpis, [], sums),
    }


class TestSynth(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_same_seed_same_bytes(self):
        a = synth.generate("016-u100", self.dir / "a")["input"]
        b = synth.generate("016-u100", self.dir / "b")["input"]
        self.assertEqual(hashlib.sha256(a.read_bytes()).hexdigest(),
                         hashlib.sha256(b.read_bytes()).hexdigest())

    def test_generation_does_not_touch_official_payload(self):
        official = (common.docops_root() / "payload/tasks/016/seed/root/"
                    "docops_v2_l3_016_xlsx_forecast_driver_cascade_input.xlsx")
        before = hashlib.sha256(official.read_bytes()).hexdigest()
        synth.generate("016-u100", self.dir / "out")
        self.assertEqual(before, hashlib.sha256(official.read_bytes()).hexdigest())

    def test_scale_counts(self):
        info = synth.generate("016-u100", self.dir / "out")
        sm = info["scale_metadata"]
        self.assertEqual(sm["business_units"], 100)
        self.assertEqual(sm["periods"], 4)
        self.assertEqual(sm["model_rows"], 400)
        self.assertEqual(sm["base_breach_count"], 0)
        self.assertGreater(sm["stress_breach_count"], 0)

    def test_source_contains_assumptions_and_demand(self):
        info = synth.generate("016-u100", self.dir / "out")
        wb = load_workbook(info["input"], data_only=True)
        self.assertEqual(wb.sheetnames, ["Assumptions", "Demand Raw", "Dashboard", "Archive"])
        self.assertEqual(wb["Assumptions"]["B1"].value, "Base")
        self.assertEqual(wb["Assumptions"]["C1"].value, "Stress")
        self.assertEqual(wb["Assumptions"]["B5"].value, "Stress")
        self.assertEqual(wb["Demand Raw"].max_row, 401)


class TestExpected(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_expected_flags_and_aggregates(self):
        info = synth.generate("016-u100", self.dir)
        exp = expected_mod.compute(info["units"])
        self.assertEqual(exp["model_rows"], 400)
        self.assertEqual(exp["model_range_end"], 401)
        self.assertEqual(len(exp["rows"]), 400)
        self.assertTrue(all(f == "OK" for f in exp["scenario_flags"]["Base"]))
        self.assertGreater(exp["breach_count"], 0)
        self.assertEqual(exp["breach_count"],
                         sum(1 for f in exp["scenario_flags"]["Stress"] if f == "Breach"))
        for row in exp["rows"]:
            expected_flag = "Breach" if row["forecast"] > row["capacity"] else "OK"
            self.assertEqual(row["flag"], expected_flag)
        kpis = exp["dashboard"]
        self.assertAlmostEqual(kpis["forecast_units"],
                               sum(r["forecast"] for r in exp["rows"]))
        self.assertAlmostEqual(kpis["total_revenue"],
                               sum(r["revenue"] for r in exp["rows"]))
        self.assertEqual(kpis["capacity_breaches"], exp["breach_count"])
        self.assertEqual(kpis["model_records"], 400)
        self.assertAlmostEqual(kpis["average_price"], 39)

    def test_scenario_rows_are_complete(self):
        info = synth.generate("016-u100", self.dir)
        exp = expected_mod.compute(info["units"])
        for scenario in ("Base", "Stress"):
            self.assertEqual(len(exp["scenario_rows"][scenario]), 400)
            for r in exp["scenario_rows"][scenario]:
                for field in ("unit", "month", "base", "actual", "growth",
                              "forecast", "price", "revenue", "capacity", "flag"):
                    self.assertIn(field, r)

    def test_exception_list_is_complete(self):
        info = synth.generate("016-u100", self.dir)
        exp = expected_mod.compute(info["units"])
        breaches = [r for r in exp["rows"] if r["flag"] == "Breach"]
        self.assertEqual(len(exp["exception_slots"]), len(breaches))
        self.assertEqual(exp["exception_slots"][-1]["unit"], breaches[-1]["unit"])
        self.assertEqual(exp["exception_slots"][-1]["month"], breaches[-1]["month"])

    def test_period_sums_cover_all_units(self):
        info = synth.generate("016-u100", self.dir)
        exp = expected_mod.compute(info["units"])
        default = exp["default_scenario"]
        sums = exp["scenario_period_sums"][default]
        for offset in range(4):
            self.assertAlmostEqual(
                sums["forecast"][offset],
                sum(r["forecast"] for r in exp["rows"]
                    if r["month"] == exp["periods_labels"][offset]))
            self.assertEqual(sums["capacity"][offset],
                             exp["business_units"] * exp["scenarios"][default]["capacity"])


class TestBuildFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_build_structure(self):
        _units, out, _expected, exp = make_fixture(self.dir)
        n = exp["business_units"]
        m = exp["model_range_end"]
        wb = load_workbook(out, data_only=False)
        self.assertEqual(wb.sheetnames, exp["release_order"])
        for hidden in exp["hidden_sheets"]:
            self.assertEqual(wb[hidden].sheet_state, "hidden")
        self.assertEqual(wb["Forecast Model"].max_row, m)
        forecast = wb["Forecast Model"]
        self.assertEqual([forecast.cell(1, c).value for c in range(1, 10)],
                         exp["model_headers"])
        templates = exp["model_formula_templates"]
        for column, offset in zip(templates, range(1, 12)):
            self.assertEqual(forecast.cell(m, offset).value,
                             templates[column].format(row=m))
        exceptions = wb["Exception Review"]
        self.assertEqual(exceptions.max_row, exp["exception_last_row"])
        self.assertEqual([exceptions.cell(1, c).value for c in range(1, 7)],
                         exp["exception_headers"])
        exc_templates = exp["exception_formula_templates"]
        for col, header in enumerate(exc_templates, 1):
            self.assertEqual(exceptions.cell(exp["exception_last_row"], col).value,
                             exc_templates[header].format(r=exp["exception_last_row"]))
        dash = wb["Dashboard"]
        self.assertEqual(dash["A5"].value, exp["kpi_formulas"]["A5"])
        self.assertEqual(dash["G8"].value, exp["kpi_formulas"]["G8"])
        self.assertEqual(len(dash._charts), 1)
        self.assertEqual(dash._charts[0].__class__.__name__, "BarChart")
        # four-period chart: 2 series over 4 categories
        chart = dash._charts[0]
        self.assertEqual(len(chart.series), 2)
        self.assertFalse(validate.verify_chart(wb, exp))
        # print setup: model/exception allow multiple pages, dashboard one page
        self.assertEqual(forecast.page_setup.fitToHeight, 0)
        self.assertEqual(exceptions.page_setup.fitToHeight, 0)
        self.assertEqual(dash.page_setup.fitToHeight, 1)
        text = " ".join(str(c.value) for ws in wb.worksheets
                        for row in ws.iter_rows() for c in row if c.value is not None)
        self.assertNotIn("Draft Forecast Dashboard", text)

    def test_validate_structure_only(self):
        _units, out, expected_path, _exp = make_fixture(self.dir)
        result = validate.check(out, expected_path, structure_only=True)
        self.assertEqual(result["mode"], "structure_only")
        self.assertFalse([k for k, v in result["checks"].items() if v is False])
        formal = validate.check(out, expected_path)
        self.assertIs(formal["caches_present"], False)


class TestValidatorNegative(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        _units, self.out, self.expected_path, self.exp = make_fixture(self.dir)
        self.m = self.exp["model_range_end"]

    def test_delete_last_model_row_fails(self):
        wb = load_workbook(self.out)
        wb["Forecast Model"].delete_rows(self.m, 1)
        wb.save(self.out)
        result = validate.check(self.out, self.expected_path, structure_only=True)
        self.assertIs(result["checks"]["model_row_count"], False)

    def test_demand_raw_last_row_unit_tampered_fails(self):
        wb = load_workbook(self.out)
        wb["Demand Raw"].cell(self.m, 4).value = self.exp["unit_ids"][0]
        wb.save(self.out)
        result = validate.check(self.out, self.expected_path, structure_only=True)
        self.assertIs(result["checks"]["demand_row_count"], True)
        # structure-only does not verify values; formal cache injection does
        inject_cached_values(self.out, full_cache_map(self.exp))
        result = validate.check(self.out, self.expected_path)
        self.assertIs(result["checks"]["demand_values"], False)


class TestCacheValidation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        _units, self.out, self.expected_path, self.exp = make_fixture(self.dir)
        self.m = self.exp["model_range_end"]

    def test_full_correct_caches_pass(self):
        inject_cached_values(self.out, full_cache_map(self.exp))
        result = validate.check(self.out, self.expected_path)
        self.assertEqual(result["mode"], "formal")
        self.assertIs(result["caches_present"], True)
        self.assertFalse([k for k, v in result["checks"].items() if v is False])

    def test_first_present_but_later_missing_fails(self):
        cells = full_cache_map(self.exp)
        keep = {"Forecast Model": {k: v for k, v in cells["Forecast Model"].items()
                                    if k.endswith("2")},
                "Dashboard": cells["Dashboard"]}
        inject_cached_values(self.out, keep)
        result = validate.check(self.out, self.expected_path)
        self.assertIs(result["caches_present"], False)
        self.assertTrue(any("Forecast Model!" in cell
                            for cell in result["checks"]["missing_cache_cells"]))

    def test_last_row_forecast_cache_wrong_fails(self):
        cells = full_cache_map(self.exp)
        cells["Forecast Model"][f"E{self.m}"] = 999999999
        inject_cached_values(self.out, cells)
        result = validate.check(self.out, self.expected_path)
        self.assertIs(result["caches_present"], True)
        self.assertIs(result["checks"]["model_values"], False)

    def test_last_row_revenue_cache_wrong_fails(self):
        cells = full_cache_map(self.exp)
        cells["Forecast Model"][f"G{self.m}"] = 42424242
        inject_cached_values(self.out, cells)
        result = validate.check(self.out, self.expected_path)
        self.assertIs(result["caches_present"], True)
        self.assertIs(result["checks"]["model_values"], False)

    def test_last_row_capacity_cache_wrong_fails(self):
        cells = full_cache_map(self.exp)
        cells["Forecast Model"][f"H{self.m}"] = 1
        inject_cached_values(self.out, cells)
        result = validate.check(self.out, self.expected_path)
        self.assertIs(result["caches_present"], True)
        self.assertIs(result["checks"]["model_values"], False)

    def test_last_chart_source_cache_missing_fails(self):
        cells = full_cache_map(self.exp)
        last_period_row = self.exp["period_summary"]["last_data_row"]
        cells["Dashboard"].pop(f"B{last_period_row}")
        inject_cached_values(self.out, cells)
        result = validate.check(self.out, self.expected_path)
        self.assertIs(result["caches_present"], False)
        self.assertTrue(any(f"Dashboard!B{last_period_row}" in cell
                            for cell in result["checks"]["missing_cache_cells"]))

    def test_last_chart_source_cache_wrong_fails(self):
        cells = full_cache_map(self.exp)
        last_period_row = self.exp["period_summary"]["last_data_row"]
        cells["Dashboard"][f"C{last_period_row}"] = 7
        inject_cached_values(self.out, cells)
        result = validate.check(self.out, self.expected_path)
        self.assertIs(result["caches_present"], True)
        self.assertIs(result["checks"]["period_summary_values"], False)

    def test_chart_misses_last_unit_contribution_fails(self):
        # B24 = last period total forecast; drop the last unit's contribution.
        cells = full_cache_map(self.exp)
        last_period_row = self.exp["period_summary"]["last_data_row"]
        default = self.exp["default_scenario"]
        last_unit_id = self.exp["unit_ids"][-1]
        last_unit_contribution = sum(
            r["forecast"] for r in self.exp["scenario_rows"][default]
            if r["unit"] == last_unit_id and r["month"] == self.exp["periods_labels"][-1])
        cells["Dashboard"][f"B{last_period_row}"] = (
            self.exp["scenario_period_sums"][default]["forecast"][-1]
            - last_unit_contribution)
        inject_cached_values(self.out, cells)
        result = validate.check(self.out, self.expected_path)
        self.assertIs(result["caches_present"], True)
        self.assertIs(result["checks"]["period_summary_values"], False)

    def test_delete_last_exception_fails(self):
        cells = full_cache_map(self.exp)
        last_exc = self.exp["exception_last_row"]
        for col in ("A", "B", "C", "D", "E", "F"):
            cells["Exception Review"].pop(f"{col}{last_exc}")
        inject_cached_values(self.out, cells)
        result = validate.check(self.out, self.expected_path)
        self.assertIs(result["caches_present"], False)
        self.assertTrue(any("Exception Review!" in cell
                            for cell in result["checks"]["missing_cache_cells"]))

    def test_last_exception_replaced_by_first_unit_fails(self):
        cells = full_cache_map(self.exp)
        slots = self.exp["exception_slots"]
        last_exc = self.exp["exception_last_row"]
        first = slots[0]
        cells["Exception Review"][f"A{last_exc}"] = first["unit"]
        cells["Exception Review"][f"B{last_exc}"] = first["month"]
        cells["Exception Review"][f"D{last_exc}"] = first["forecast"]
        cells["Exception Review"][f"E{last_exc}"] = first["capacity"]
        cells["Exception Review"][f"F{last_exc}"] = first["overage"]
        inject_cached_values(self.out, cells)
        result = validate.check(self.out, self.expected_path)
        self.assertIs(result["caches_present"], True)
        self.assertIs(result["checks"]["exception_values"], False)

    def test_exception_identity_wrong_fails(self):
        # exception count stays correct; last exception's unit is wrong.
        cells = full_cache_map(self.exp)
        last_exc = self.exp["exception_last_row"]
        wrong_unit = self.exp["unit_ids"][0]
        cells["Exception Review"][f"A{last_exc}"] = wrong_unit
        inject_cached_values(self.out, cells)
        result = validate.check(self.out, self.expected_path)
        self.assertIs(result["caches_present"], True)
        self.assertIs(result["checks"]["exception_values"], False)

    def test_wrong_capacity_flag_cache_fails(self):
        cells = full_cache_map(self.exp)
        last = self.m
        current = cells["Forecast Model"][f"I{last}"]
        cells["Forecast Model"][f"I{last}"] = "OK" if current == "Breach" else "Breach"
        inject_cached_values(self.out, cells)
        result = validate.check(self.out, self.expected_path)
        self.assertIs(result["caches_present"], True)
        self.assertIs(result["checks"]["model_values"], False)

    def test_wrong_kpi_aggregate_fails(self):
        cells = full_cache_map(self.exp)
        cells["Dashboard"]["G5"] = self.exp["dashboard"]["capacity_breaches"] + 1
        inject_cached_values(self.out, cells)
        result = validate.check(self.out, self.expected_path)
        self.assertIs(result["caches_present"], True)
        self.assertIs(result["checks"]["kpi_values"], False)

    def test_legal_zero_passes(self):
        # Base scenario: breaches and overage are legitimately zero; a cached 0
        # must not be treated as missing.
        cells = base_cache_map(self.exp)
        inject_cached_values(self.out, cells)
        values = load_workbook(self.out, data_only=True)
        self.assertEqual(values["Dashboard"]["G5"].value, 0)
        self.assertEqual(values["Dashboard"]["A8"].value, 0)
        self.assertEqual(validate.verify_kpis(values, self.exp["scenario_kpis"]["Base"]), [])
        self.assertEqual(validate.verify_model_rows(
            values, self.exp["scenario_rows"]["Base"]), [])
        self.assertEqual(validate.verify_period_sums(
            values, self.exp, "Base"), [])
        self.assertEqual(validate.verify_exception_rows_full(
            values, self.exp, "Base"), [])
        self.assertEqual(validate.verify_watch(values, self.exp, "Base"), [])


class TestScenarioCascade(unittest.TestCase):
    """Base must clear every breach; Stress must match the frozen oracle.

    The real replay recalculates a COPY with LibreOffice; here we inject the
    recalculated caches for each scenario and exercise the same full-value
    assertions the formal scenario switch uses. A regression case also proves
    that a row value error survives when the Breach flag is unchanged.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        _units, self.out, _expected_path, self.exp = make_fixture(self.dir)

    def _values_for(self, cells, name):
        path = self.dir / name
        path.write_bytes(self.out.read_bytes())
        inject_cached_values(path, cells)
        return load_workbook(path, data_only=True)

    def test_base_scenario_full_values(self):
        values = self._values_for(base_cache_map(self.exp), "base.xlsx")
        self.assertEqual(validate.verify_model_rows(
            values, self.exp["scenario_rows"]["Base"]), [])
        self.assertEqual(validate.verify_kpis(values, self.exp["scenario_kpis"]["Base"]), [])
        self.assertEqual(validate.verify_period_sums(values, self.exp, "Base"), [])
        self.assertEqual(validate.verify_exception_rows_full(values, self.exp, "Base"), [])
        self.assertEqual(validate.verify_watch(values, self.exp, "Base"), [])

    def test_stress_scenario_full_values(self):
        values = self._values_for(full_cache_map(self.exp), "stress.xlsx")
        self.assertEqual(validate.verify_model_rows(
            values, self.exp["scenario_rows"]["Stress"]), [])
        self.assertEqual(validate.verify_kpis(values, self.exp["scenario_kpis"]["Stress"]), [])
        self.assertEqual(validate.verify_period_sums(values, self.exp, "Stress"), [])
        self.assertEqual(validate.verify_exception_rows_full(values, self.exp, "Stress"), [])
        self.assertEqual(validate.verify_watch(values, self.exp, "Stress"), [])

    def test_row_value_wrong_but_flag_unchanged_fails(self):
        # Change a Stress-scenario model row's forecast cache but keep its
        # Breach flag exactly as expected: flags would still pass, full values fail.
        cells = full_cache_map(self.exp)
        last = self.exp["model_range_end"]
        cells["Forecast Model"][f"E{last}"] = (
            self.exp["scenario_rows"]["Stress"][-1]["forecast"] + 1)
        values = self._values_for(cells, "stress-wrong.xlsx")
        self.assertNotEqual(validate.verify_model_rows(
            values, self.exp["scenario_rows"]["Stress"]), [])




class TestAuditF1F2(unittest.TestCase):
    """F1/F2 audit regressions: exception issue text must describe the overage
    (semantics + value), and the four chart period labels must match the frozen
    order. Temporary OOXML mutations only; the built fixture is regenerated per
    test."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        _units, self.out, self.expected_path, self.exp = make_fixture(self.dir)
        self.m = self.exp["model_range_end"]

    def _inject_full(self):
        inject_cached_values(self.out, full_cache_map(self.exp))

    def test_last_exception_issue_wrong_text_fails(self):
        self._inject_full()
        cells = full_cache_map(self.exp)
        last_exc = self.exp["exception_last_row"]
        cells["Exception Review"][f"C{last_exc}"] = (
            "Forecast exceeds capacity by 999999.0 units")
        inject_cached_values(self.out, cells)
        result = validate.check(self.out, self.expected_path)
        self.assertIs(result["caches_present"], True)
        self.assertIs(result["checks"]["exception_values"], False)

    def test_exception_issue_uses_forecast_fails(self):
        cells = full_cache_map(self.exp)
        last_exc = self.exp["exception_last_row"]
        slot = self.exp["exception_slots"][-1]
        cells["Exception Review"][f"C{last_exc}"] = (
            f"Forecast exceeds capacity by {slot['forecast']:.1f} units")
        inject_cached_values(self.out, cells)
        result = validate.check(self.out, self.expected_path)
        self.assertIs(result["caches_present"], True)
        self.assertIs(result["checks"]["exception_values"], False)

    def test_correct_issue_text_passes(self):
        # every filled exception row carries the overage-based description.
        self._inject_full()
        result = validate.check(self.out, self.expected_path)
        self.assertIs(result["caches_present"], True)
        self.assertIs(result["checks"]["exception_values"], True)

    def _tamper_label(self, coord, value):
        # label cells are static (no formula): change the value with openpyxl,
        # then re-inject the formula caches that a save would drop.
        wb = load_workbook(self.out)
        wb["Dashboard"][coord] = value
        wb.save(self.out)
        self._inject_full()

    def test_last_month_label_wrong_fails(self):
        ps = self.exp["period_summary"]
        self._tamper_label(f"A{ps['last_data_row']}", "WRONG PERIOD")
        result = validate.check(self.out, self.expected_path)
        self.assertIs(result["caches_present"], True)
        self.assertIs(result["checks"]["period_summary_values"], False)

    def test_month_label_duplicate_fails(self):
        ps = self.exp["period_summary"]
        self._tamper_label(f"A{ps['first_data_row'] + 1}", "Sep")  # duplicate last label
        result = validate.check(self.out, self.expected_path)
        self.assertIs(result["caches_present"], True)
        self.assertIs(result["checks"]["period_summary_values"], False)

    def test_month_label_out_of_order_fails(self):
        ps = self.exp["period_summary"]
        self._tamper_label(f"A{ps['first_data_row']}", "Jul")  # wrong first order
        result = validate.check(self.out, self.expected_path)
        self.assertIs(result["caches_present"], True)
        self.assertIs(result["checks"]["period_summary_values"], False)

    def test_legal_empty_slot_passes(self):
        # Base scenario: every exception row (including the issue column) is
        # oracle-proven empty and must pass.
        cells = base_cache_map(self.exp)
        inject_cached_values(self.out, cells)
        values = load_workbook(self.out, data_only=True)
        self.assertEqual(validate.verify_exception_rows_full(
            values, self.exp, "Base"), [])


if __name__ == "__main__":
    unittest.main()
