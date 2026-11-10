"""Small directed checks for the scaled Excel 013 synthetic variants.

Runs tiny fixtures only: input synthesis, the independent expectation
implementation, and the parameterized builder/validator on micro inputs. No
LibreOffice recalc, no PDF export, no full-scale processing is performed here.
Formula caches are injected into the fixture OOXML directly to exercise the
validator's formal cache checks without LibreOffice.
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

synth = importlib.import_module("scaling.cases.013.synth")
expected_mod = importlib.import_module("scaling.cases.013.expected")
bld = importlib.import_module("scaling.cases.013.scripts.build_bid_evaluation_variant")
validate = importlib.import_module("scaling.cases.013.scripts.validate_bid_evaluation_variant")
common = importlib.import_module("scaling.cases.common")

SHEET_FILES = {
    name: f"xl/worksheets/sheet{index}.xml"
    for index, name in enumerate(synth.SHEET_ORDER, start=1)
}


def make_fixture(directory: Path, n: int = 3, seed: int = 42):
    vendors = synth.make_vendors(n, random.Random(seed))
    vendors_path = synth.write_vendors_json("013-v100", vendors, "in.xlsx", directory)
    synth.write_input_workbook(vendors, directory / "in.xlsx")
    data = json.loads(vendors_path.read_text(encoding="utf-8"))
    data["input_path"] = str(directory / "in.xlsx")
    vendors_path.write_text(json.dumps(data), encoding="utf-8")
    out = directory / "out.xlsx"
    bld.build(vendors_path, out)
    expected_path = directory / "expected.json"
    exp = expected_mod.write_expected("013-v100", vendors_path, expected_path)
    return vendors_path, out, expected_path, exp


def inject_cached_values(xlsx_path, cells_by_sheet):
    """Inject `<v>` cached values into formula cells of the fixture OOXML."""

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


def full_cache_map(exp):
    cells = {"Evaluation Summary": {}, "Price Normalization": {}}
    cells["Evaluation Summary"]["B3"] = exp["summary"]["responsive_vendors"]
    cells["Evaluation Summary"]["B4"] = exp["summary"]["recommended_vendor"]
    cells["Evaluation Summary"]["B5"] = exp["summary"]["lowest_corrected_price"]
    cells["Evaluation Summary"]["B6"] = exp["summary"]["average_technical_score"]
    for row in range(2, exp["register_range_end"] + 1):
        cells["Price Normalization"][f"D{row}"] = exp["price_scores"][row - 2]
    return cells


class TestSynth(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_same_seed_same_bytes(self):
        a = synth.generate("013-v100", self.dir / "a")["input"]
        b = synth.generate("013-v100", self.dir / "b")["input"]
        self.assertEqual(hashlib.sha256(a.read_bytes()).hexdigest(),
                         hashlib.sha256(b.read_bytes()).hexdigest())

    def test_generation_does_not_touch_official_payload(self):
        official = (common.docops_root() / "payload/tasks/013/seed/root/"
                    "docops_v2_l3_013_xlsx_procurement_bid_evaluation_release_input.xlsx")
        before = hashlib.sha256(official.read_bytes()).hexdigest()
        synth.generate("013-v100", self.dir / "out")
        self.assertEqual(before, hashlib.sha256(official.read_bytes()).hexdigest())

    def test_scale_counts(self):
        info = synth.generate("013-v100", self.dir / "out")
        sm = info["scale_metadata"]
        self.assertEqual(sm["vendors"], 100)
        self.assertEqual(sm["register_rows"], 100)
        self.assertEqual(sm["scoring_rows"], 300)
        self.assertEqual(sm["price_formula_cells"], 100)
        self.assertEqual(sm["formula_count"], 104)
        self.assertEqual(sm["source_correction_rows"], 2 * 100 + 3)
        self.assertGreaterEqual(sm["responsive_count"], 0)
        self.assertEqual(sm["lowest_price"], min(v["corrected_price"]
                                                 for v in json.loads(info["vendors"].read_text())["vendors"]))

    def test_source_contains_correction_log_and_raw_rows(self):
        info = synth.generate("013-v100", self.dir / "out")
        wb = load_workbook(info["input"], data_only=True)
        self.assertIn("Correction_Log_INTERNAL", wb.sheetnames)
        self.assertIn("Raw Vendor Data_INTERNAL", wb.sheetnames)
        raw = wb["Raw Vendor Data_INTERNAL"]
        self.assertEqual(raw.max_row, 101)
        corr = wb["Correction_Log_INTERNAL"]
        self.assertEqual(corr.max_row, 1 + 2 * 100 + 3)
        # the raw ids are the wrong forms corrected by the log
        self.assertTrue(str(raw.cell(2, 1).value).endswith("x"))


class TestExpected(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_expected_follows_rules(self):
        info = synth.generate("013-v100", self.dir)
        exp = expected_mod.compute(info["vendors"])
        self.assertEqual(exp["n"], 100)
        self.assertEqual(len(exp["vendor_ids"]), 100)
        self.assertEqual(len(exp["scoring_rows"]), 300)
        # price normalization uses the global minimum
        lowest = exp["summary"]["lowest_corrected_price"]
        for record, price_score in zip(exp["records"], exp["price_scores"]):
            self.assertAlmostEqual(price_score, lowest / record["corrected_price"] * 100)
        # award is the top-3 by weighted score
        weighted = sorted(exp["records"],
                          key=lambda r: (-r["technical_score"], r["id"]))
        self.assertEqual([a["vendor_id"] for a in exp["award"]],
                         [r["id"] for r in weighted[:3]])
        self.assertEqual(exp["award"][0]["status"], "Recommend award")
        self.assertEqual(exp["summary"]["responsive_vendors"],
                         sum(1 for r in exp["records"] if r["status"] == "Responsive"))
        # formula and cache counts
        self.assertEqual(exp["formula_count"], 100 + 4)
        self.assertEqual(exp["cached_cells"], 100 + 4)

    def test_forbidden_does_not_false_positive_on_corrected_values(self):
        info = synth.generate("013-v100", self.dir)
        exp = expected_mod.compute(info["vendors"])
        # "Responsiv" and "Leah Moor" are substrings of the corrected values
        # "Responsive" / "Leah Moore", so they must not be forbidden text.
        self.assertNotIn("Responsiv", exp["forbidden_phrases"])
        self.assertNotIn("Leah Moor", exp["forbidden_phrases"])

    def test_weighted_score_independent(self):
        vendor = {"id": "VND-999", "scores": {"REQ-01": 80, "REQ-02": 90, "REQ-03": 100}}
        self.assertAlmostEqual(expected_mod.weighted_score(vendor),
                               0.2 * 80 + 0.3 * 90 + 0.5 * 100)


class TestBuildFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_build_structure(self):
        _vendors, out, _expected, exp = make_fixture(self.dir)
        n = exp["n"]
        last = n + 1
        wb = load_workbook(out, data_only=False)
        self.assertEqual(wb.sheetnames, synth.SHEET_ORDER)
        register = wb["Vendor Register"]
        self.assertEqual([register.cell(r, 1).value for r in range(2, last + 1)],
                         exp["vendor_ids"])
        # corrections applied: no wrong id forms, evaluator/status corrected
        self.assertEqual(register.cell(2, 4).value, "Leah Moore")
        self.assertIn(register.cell(2, 5).value, ("Responsive", "Nonresponsive"))
        self.assertEqual(wb.defined_names["VendorIDs"].attr_text,
                         f"'Vendor Register'!$A$2:$A${last}")
        scoring = wb["Requirements Scoring"]
        self.assertEqual(scoring.max_row, 3 * n + 1)
        self.assertTrue(all(str(scoring.cell(r, 1).value).startswith("REQ")
                            for r in range(2, 3 * n + 2)))
        price = wb["Price Normalization"]
        self.assertEqual(price.cell(last, 4).value,
                         f"=MIN($C$2:$C${last})/C{last}*100")
        summary = wb["Evaluation Summary"]
        self.assertEqual(summary["B3"].value,
                         f'=COUNTIF(\'Vendor Register\'!E2:E{last},"Responsive")')
        self.assertEqual(summary["B6"].value,
                         f"=AVERAGE('Requirements Scoring'!E2:E{3 * n + 1})")
        dv = {str(dv.sqref) for dv in scoring.data_validations.dataValidation}
        self.assertIn(f"B2:B{3 * n + 1}", dv)
        # no internal material survives
        text = " ".join(str(c.value) for ws in wb.worksheets
                        for row in ws.iter_rows() for c in row if c.value is not None)
        self.assertNotIn("PRIVATE", text)
        self.assertNotIn("DRAFT", text)
        self.assertNotIn("x", "".join(exp["vendor_ids"]))  # sanity

    def test_validate_structure_only(self):
        _vendors, out, expected_path, _exp = make_fixture(self.dir)
        result = validate.check(out, expected_path, structure_only=True)
        self.assertEqual(result["mode"], "structure_only")
        self.assertFalse([k for k, v in result["checks"].items() if v is False])
        formal = validate.check(out, expected_path)
        self.assertIs(formal["caches_present"], False)
        self.assertTrue(formal["checks"]["caches_present"] is False)

    def test_builder_does_not_share_value_implementation(self):
        build_src = Path(bld.__file__).read_text(encoding="utf-8")
        expected_src = Path(expected_mod.__file__).read_text(encoding="utf-8")
        # the builder reads the correction log from the source workbook, the
        # oracle reads only vendors.json and never touches the source workbook
        self.assertIn("def read_correction_log", build_src)
        self.assertIn("def apply_corrections", build_src)
        self.assertIn("load_workbook", build_src)
        # the oracle never loads the source workbook; it reads vendors.json only
        self.assertNotIn("load_workbook", expected_src)
        self.assertIn("def weighted_score", build_src)
        self.assertIn("def weighted_score", expected_src)
        # the builder writes the price formula string, the oracle computes the
        # numeric price scores in Python (the oracle only stores the formula
        # template so the validator can compare it)
        self.assertIn("MIN($C$2:$C$", build_src)
        self.assertIn("price_score", expected_src)
        self.assertIn("price_formula_row1", expected_src)


class TestValidatorNegative(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        _vendors, self.out, self.expected_path, self.exp = make_fixture(self.dir)
        self.last = self.exp["register_range_end"]

    def _save(self, wb):
        wb.save(self.out)

    def test_delete_last_vendor_fails(self):
        wb = load_workbook(self.out)
        wb["Vendor Register"].delete_rows(self.last, 1)
        self._save(wb)
        result = validate.check(self.out, self.expected_path, structure_only=True)
        self.assertIs(result["checks"]["vendor_ids"], False)
        self.assertIs(result["checks"]["register_row_count"], False)

    def test_last_vendor_fact_changed_fails(self):
        wb = load_workbook(self.out)
        wb["Vendor Register"].cell(self.last, 2).value = self.exp["records"][0]["name"]
        self._save(wb)
        result = validate.check(self.out, self.expected_path, structure_only=True)
        self.assertIs(result["checks"]["vendor_names"], False)

    def test_last_price_changed_fails(self):
        wb = load_workbook(self.out)
        cell = wb["Price Normalization"].cell(self.last, 3)
        cell.value = float(cell.value) + 1
        self._save(wb)
        result = validate.check(self.out, self.expected_path, structure_only=True)
        self.assertIs(result["checks"]["price_values"], False)

    def test_last_formula_missing_fails(self):
        wb = load_workbook(self.out)
        wb["Price Normalization"].cell(self.last, 4).value = None
        self._save(wb)
        result = validate.check(self.out, self.expected_path, structure_only=True)
        self.assertIs(result["checks"]["price_formulas"], False)
        self.assertIs(result["checks"]["last_row_formula_present"], False)


class TestCacheValidation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        _vendors, self.out, self.expected_path, self.exp = make_fixture(self.dir)

    def test_full_correct_caches_pass(self):
        inject_cached_values(self.out, full_cache_map(self.exp))
        result = validate.check(self.out, self.expected_path)
        self.assertEqual(result["mode"], "formal")
        self.assertIs(result["caches_present"], True)
        self.assertFalse([k for k, v in result["checks"].items() if v is False])

    def test_first_present_but_later_missing_fails(self):
        # only the first summary cells and the first price row get a cache
        cells = {"Evaluation Summary": full_cache_map(self.exp)["Evaluation Summary"],
                 "Price Normalization": {"D2": self.exp["price_scores"][0]}}
        inject_cached_values(self.out, cells)
        result = validate.check(self.out, self.expected_path)
        self.assertIs(result["caches_present"], False)
        self.assertIn(f"Price Normalization!D3", result["checks"]["missing_cache_cells"])
        self.assertNotIn("Price Normalization!D2", result["checks"]["missing_cache_cells"])

    def test_wrong_summary_cache_fails(self):
        cells = full_cache_map(self.exp)
        cells["Evaluation Summary"]["B6"] = self.exp["summary"]["average_technical_score"] + 1
        inject_cached_values(self.out, cells)
        result = validate.check(self.out, self.expected_path)
        self.assertIs(result["caches_present"], True)
        self.assertIs(result["checks"]["summary_values"], False)

    def test_wrong_price_cache_fails(self):
        cells = full_cache_map(self.exp)
        cells["Price Normalization"][f"D{self.exp['register_range_end']}"] = -1.0
        inject_cached_values(self.out, cells)
        result = validate.check(self.out, self.expected_path)
        self.assertIs(result["caches_present"], True)
        self.assertIs(result["checks"]["price_score_values"], False)


if __name__ == "__main__":
    unittest.main()
