"""Small directed checks for the scaled Excel 014 synthetic variants.

Runs tiny fixtures only: input synthesis, the independent expectation
implementation, and the parameterized builder/validator on micro inputs. No
LibreOffice recalc, no PDF export, no full-scale processing is performed here.
"""
from __future__ import annotations

import importlib
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # /home/lcq/office-trace-replay
sys.path.insert(0, str(ROOT / "docops"))

from openpyxl import Workbook, load_workbook

synth = importlib.import_module("scaling.cases.014.synth")
expected_mod = importlib.import_module("scaling.cases.014.expected")
bld = importlib.import_module("scaling.cases.014.scripts.build_disaster_release_variant")
finalize = importlib.import_module("scaling.cases.014.scripts.finalize_disaster_release_variant_ooxml")
validate = importlib.import_module("scaling.cases.014.scripts.validate_disaster_release_variant")
common = importlib.import_module("scaling.cases.common")

RAW_HEADERS = synth.RAW_HEADERS


def write_tiny_source(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Raw Intake PRIVATE"
    ws.append(RAW_HEADERS)
    rows = [
        ("H-101", "Alicia Tran", "South Ridge", "Moderate", 21500, 3000, "Moderate", "No", "No", "2026-05-14", "unverified hardship narrative", "555-0101"),
        ("H-102", "Marta Ruiz", "East Bay", "Major", 40200, 5000, "Low", "Yes", "No", "2026-05-15", "PRIVATE intake note", "555-0102"),
        ("H-103", "Lena Okafor", "West Lake", "Minor", 8800, 0, "High", "No", "Yes", "2026-05-16", "appeal note legal hold", "555-0103"),
        ("H-104", "Dev Patel", "N. Fork", "Major", 30500, 4000, "Low", "No", "No", "2026-05-18", "county correction pending", "555-0104"),
        ("H-105", "Iris Chen", "South Ridge", "Destroyed", 68000, 12000, "Low", "Yes", "Yes", "2026-05-18", "DRAFT senior review note", "555-0105"),
        ("H-105", "Iris Chen", "South Ridge", "Destroyed", 70000, 15000, "Low", "Yes", "Yes", "2026-05-28", "duplicate scratch row", "555-0105"),
        ("H-107", "Nadia Singh", "West Lake", "Major", 22000, 1000, "Moderate", "Yes", "No", "2026-05-10", "older duplicate scratch row", "555-0107"),
        ("H-107", "Nadia Singh", "West Lake", "Major", 23500, 2000, "Moderate", "Yes", "No", "2026-05-21", "latest duplicate row", "555-0107"),
        ("H-109", "Bianca Flores", "East Bay", "Minor", 26700, 2500, "Moderate", "No", "Yes", "2026-05-22", "Minor correction pending", "555-0109"),
        ("H-112", "Cole Rivera", "South Ridge", "Major", 31500, 5000, "Moderate", "Yes", "No", "2026-05-24", "moderate income pending", "555-0112"),
    ]
    for r in rows:
        ws.append(list(r))
    for name in ("Correction Bulletin DRAFT", "duplicate scratch", "legal hold", "DRAFT Dashboard"):
        wb.create_sheet(name)
    wb.save(path)


class TestSynth(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_same_seed_same_business_content_and_bytes(self):
        a = self.dir / "a"
        b = self.dir / "b"
        ia = synth.generate("014-n1000", a)["input"]
        ib = synth.generate("014-n1000", b)["input"]
        ha = hashlib.sha256(ia.read_bytes()).hexdigest()
        hb = hashlib.sha256(ib.read_bytes()).hexdigest()
        self.assertEqual(ha, hb)
        # business content identical: deduped id set
        wa = load_workbook(a / "docops_v2_l3_014_xlsx_disaster_housing_grant_public_release_input_n1000.xlsx", data_only=True)
        wb = load_workbook(b / "docops_v2_l3_014_xlsx_disaster_housing_grant_public_release_input_n1000.xlsx", data_only=True)
        ids_a = [row[0] for row in wa["Raw Intake PRIVATE"].iter_rows(min_row=2, values_only=True) if row[0]]
        ids_b = [row[0] for row in wb["Raw Intake PRIVATE"].iter_rows(min_row=2, values_only=True) if row[0]]
        self.assertEqual(ids_a, ids_b)

    def test_generation_does_not_touch_official_payload(self):
        official_input = common.docops_root() / "payload/tasks/014/seed/root/docops_v2_l3_014_xlsx_disaster_housing_grant_public_release_input.xlsx"
        before = hashlib.sha256(official_input.read_bytes()).hexdigest()
        synth.generate("014-n1000", self.dir / "out")
        after = hashlib.sha256(official_input.read_bytes()).hexdigest()
        self.assertEqual(before, after)

    def test_scale_counts_and_coverage(self):
        info = synth.generate("014-n1000", self.dir / "out")
        sm = info["scale_metadata"]
        self.assertEqual(sm["valid_applications"], 1000)
        self.assertEqual(sm["raw_rows"] - sm["duplicates"], 1000)
        self.assertGreater(sm["duplicates"], 0)
        self.assertGreater(sm["appeal_count"], 0)
        for bucket in sm["branch_coverage"]["damage"].values():
            self.assertGreater(bucket, 0)
        for bucket in sm["branch_coverage"]["income"].values():
            self.assertGreater(bucket, 0)
        self.assertGreater(sm["branch_coverage"]["appeal"]["Yes"], 0)
        self.assertGreater(sm["branch_coverage"]["appeal"]["No"], 0)


class TestExpected(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_expected_values_follow_business_rules(self):
        info = synth.generate("014-n1000", self.dir)
        exp = expected_mod.write_expected("014-n1000", info["input"], self.dir / "expected.json")
        self.assertEqual(exp["n"], 1000)
        self.assertEqual(len(exp["valid_ids"]), 1000)
        # branch coverage in the oracle
        cov = exp["coverage"]
        for status in ("Senior Review", "Appeal Review", "Ready"):
            self.assertGreater(cov["review_status"][status], 0)
        self.assertGreater(cov["eligible_zero"], 0)
        self.assertGreater(cov["priority_ge_70"], 0)
        # spot-check independent computation on a corrected record
        h104 = next(r for r in exp["records"] if r["app_id"] == "H-104")
        self.assertEqual(h104["county"], "North Fork")
        self.assertEqual(h104["eligible_amount"], min(30500 - 4000, 28000))
        self.assertEqual(h104["priority_score"], 30 + 20)
        self.assertEqual(h104["review_status"], "Senior Review")
        # aggregate identities
        self.assertEqual(exp["dashboard"]["total_applications"], 1000)
        self.assertEqual(exp["formula_count"], 3 * 1000 + 5 + 12 + 2 * exp["appeal_count"])

    def test_negative_review_branch(self):
        # a low eligible amount with appeal Yes must be Appeal Review, not Senior
        rec = {
            "Application ID": "H-900",
            "County": "East Bay",
            "Damage Category": "Minor",
            "Repair Estimate": 8000,
            "Insurance Proceeds": 6000,
            "Income Band": "High",
            "Vulnerable Household": "No",
            "Appeal Flag": "Yes",
            "Inspection Date": "2026-06-01",
        }
        amt = expected_mod.eligible_amount(rec)
        self.assertEqual(amt, 2000)
        self.assertEqual(expected_mod.review_status(rec, amt), "Appeal Review")
        # invert: dropping the appeal branch would misclassify a senior amount
        self.assertEqual(expected_mod.review_status(rec, 30000), "Senior Review")


class TestBuildFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def _build_tiny(self):
        src = self.dir / "src.xlsx"
        out = self.dir / "out.xlsx"
        write_tiny_source(src)
        n = bld.build(src, out)
        return n, out

    def test_dedup_latest_corrections_and_dynamic_ranges(self):
        n, out = self._build_tiny()
        self.assertEqual(n, 8)
        wb = load_workbook(out, data_only=False)
        reg = wb["Eligibility Register"]
        ids = [reg.cell(r, 1).value for r in range(2, reg.max_row + 1)]
        last = n + 1
        self.assertEqual(reg.auto_filter.ref, f"A1:L{last}")
        self.assertEqual(next(iter(reg.tables.values())).ref, f"A1:L{last}")
        h105 = ids.index("H-105") + 2
        self.assertEqual(reg.cell(h105, 9).value, "2026-05-28")
        self.assertEqual(reg.cell(h105, 4).value, 70000)  # latest inspection row kept
        h107 = ids.index("H-107") + 2
        self.assertEqual(reg.cell(h107, 9).value, "2026-05-21")
        self.assertEqual(reg.cell(h107, 4).value, 23500)
        h104 = ids.index("H-104") + 2
        h109 = ids.index("H-109") + 2
        h112 = ids.index("H-112") + 2
        self.assertEqual(reg.cell(h104, 2).value, "North Fork")
        self.assertEqual(reg.cell(h109, 3).value, "Major")
        self.assertEqual(reg.cell(h112, 6).value, "Low")
        cfs = {str(cf.sqref): [(r.type, r.operator, tuple(r.formula)) for r in cf.rules]
               for cf in reg.conditional_formatting}
        self.assertIn(f"K2:K{last}", cfs)
        self.assertIn(f"J2:J{last}", cfs)
        dash = wb["Funding Dashboard"]
        self.assertIn(f"$A$2:$A${last}", str(dash["B4"].value))
        county = wb["County Rollup"]
        self.assertIn(f"$B$2:$B${last}", county["C2"].value)
        appeal = wb["Appeal Queue"]
        self.assertEqual(next(iter(appeal.tables.values())).ref, f"A1:E{appeal.max_row}")
        for row in range(2, last + 1):
            for col in (10, 11, 12):
                self.assertTrue(str(reg.cell(row, col).value).startswith("="))

    def test_negative_dedup_older_row_discarded(self):
        n, out = self._build_tiny()
        wb = load_workbook(out, data_only=False)
        reg = wb["Eligibility Register"]
        ids = [reg.cell(r, 1).value for r in range(2, reg.max_row + 1)]
        self.assertNotEqual(ids.count("H-107"), 2)  # no duplicate id survives
        h107 = ids.index("H-107") + 2
        self.assertEqual(reg.cell(h107, 9).value, "2026-05-21")

    def test_validate_structure_on_fixture(self):
        n, out = self._build_tiny()
        # mirror the real pipeline order: build -> recalc(no-op here) -> finalize -> validate
        finalize.repair(out)
        info = {  # expected.json for the tiny fixture
            "n": n,
            "register_range_end": n + 1,
            "valid_ids": ["H-101", "H-102", "H-103", "H-104", "H-105", "H-107", "H-109", "H-112"],
            "records": [
                {"app_id": a, "county": c, "damage": d, "income": i, "inspection_date": dt}
                for a, c, d, i, dt in [
                    ("H-101", "South Ridge", "Moderate", "Moderate", "2026-05-14"),
                    ("H-102", "East Bay", "Major", "Low", "2026-05-15"),
                    ("H-103", "West Lake", "Minor", "High", "2026-05-16"),
                    ("H-104", "North Fork", "Major", "Low", "2026-05-18"),
                    ("H-105", "South Ridge", "Destroyed", "Low", "2026-05-28"),
                    ("H-107", "West Lake", "Major", "Moderate", "2026-05-21"),
                    ("H-109", "East Bay", "Major", "Moderate", "2026-05-22"),
                    ("H-112", "South Ridge", "Major", "Low", "2026-05-24"),
                ]
            ],
            "appeal_count": 3,
            "table_refs": {"Eligibility Register": "A1:L9", "County Rollup": "A1:D5",
                           "Appeal Queue": "A1:E4", "Publication Controls": "A1:D5"},
            "auto_filter": {"Eligibility Register": "A1:L9", "County Rollup": "A1:D5",
                            "Appeal Queue": "A1:E4", "Publication Controls": "A1:D5"},
            "conditional_formats": {"K2:K9": ["greaterThanOrEqual", "70"],
                                    "J2:J9": ["greaterThan", "0"]},
            "formula_count": 3 * 8 + 5 + 12 + 2 * 3,
            "currency_ranges": {"register_cols": [4, 5, 10], "county_col": 3,
                                "appeal_col": 4, "controls_col": 2, "dashboard_cells": ["B5"]},
            "forbidden_phrases": ["DRAFT", "PRIVATE", "N. Fork", "Alicia Tran"],
            "chart": {"type": "BarChart", "categories": "'County Rollup'!$A$2:$A$5",
                      "values": "'County Rollup'!$C$2:$C$5"},
        }
        (self.dir / "expected.json").write_text(__import__("json").dumps(info))
        # structure-only fixture mode passes without LibreOffice caches
        result = validate.check(out, self.dir / "expected.json", structure_only=True)
        self.assertEqual(result["mode"], "structure_only")
        self.assertFalse([k for k, v in result["checks"].items() if v is False])
        # the same file in formal mode MUST fail: caches are missing
        formal = validate.check(out, self.dir / "expected.json")
        self.assertEqual(formal["mode"], "formal")
        self.assertIs(formal["caches_present"], False)
        self.assertTrue(formal["checks"]["caches_present"] is False)
        # forbidden material must be gone from the rebuilt workbook
        wb = load_workbook(out, data_only=False)
        all_text = " ".join(str(c.value) for ws in wb.worksheets for row in ws.iter_rows()
                            for c in row if c.value is not None)
        self.assertNotIn("N. Fork", all_text)
        self.assertNotIn("DRAFT", all_text)

    def test_expected_and_build_do_not_share_value_implementation(self):
        build_src = Path(bld.__file__).read_text(encoding="utf-8")
        expected_src = Path(expected_mod.__file__).read_text(encoding="utf-8")
        # the builder only writes Excel formula strings and never computes amounts
        self.assertIn("=MAX(0,MIN(", build_src)
        self.assertNotIn("def eligible_amount", build_src)
        # the oracle computes values in Python, it never writes formula strings
        self.assertIn("def eligible_amount", expected_src)
        self.assertNotIn("=MAX(0,MIN(", expected_src)


SHEET_FILES = {
    "Funding Dashboard": "xl/worksheets/sheet1.xml",
    "Eligibility Register": "xl/worksheets/sheet2.xml",
    "County Rollup": "xl/worksheets/sheet3.xml",
    "Appeal Queue": "xl/worksheets/sheet4.xml",
    "Publication Controls": "xl/worksheets/sheet5.xml",
}
COUNTY_ORDER = ["East Bay", "North Fork", "South Ridge", "West Lake"]


def inject_cached_values(xlsx_path, cells_by_sheet):
    """Inject `<v>` cached values into formula cells of a small OOXML fixture.

    `cells_by_sheet` maps sheet title -> {cellref: value}. Only formula cells are
    touched; missing formula cells stay untouched (used for negative cases).
    """
    import re as _re
    import zipfile

    def _escape(value):
        if isinstance(value, str):
            return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return str(value)

    def inject(xml, ref, value):
        is_str = isinstance(value, str)
        t_attr = ' t="str"' if is_str else ""
        pat = _re.compile(rf'<c r="{ref}"([^>]*)>(.*?)</c>', _re.DOTALL)
        m = pat.search(xml)
        if not m:
            return xml
        attrs, body = m.group(1), m.group(2)
        fm = _re.search(r"<f\b[^>]*>.*?</f>", body, _re.DOTALL)
        if not fm:
            return xml
        fpart = fm.group(0)
        attrs = _re.sub(r'\s+t="[^"]*"', "", attrs)
        new_cell = f'<c r="{ref}"{attrs}{t_attr}>{fpart}<v>{_escape(value)}</v></c>'
        return pat.sub(lambda _m: new_cell, xml, count=1)

    tmp = xlsx_path.with_suffix(".inject.tmp.xlsx")
    with zipfile.ZipFile(xlsx_path) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename in (SHEET_FILES[s] for s in cells_by_sheet):
                xml = data.decode("utf-8")
                for sheet, mapping in cells_by_sheet.items():
                    if item.filename == SHEET_FILES[sheet]:
                        for ref, value in mapping.items():
                            xml = inject(xml, ref, value)
                data = xml.encode("utf-8")
            zout.writestr(item, data)
    tmp.replace(xlsx_path)


class TestCacheValidation(unittest.TestCase):
    """Formal mode must require complete formula caches (small OOXML fixtures)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def _build(self):
        src = self.dir / "src.xlsx"
        out = self.dir / "out.xlsx"
        write_tiny_source(src)
        n = bld.build(src, out)
        finalize.repair(out)
        exp = expected_mod.compute(src)
        (self.dir / "expected.json").write_text(__import__("json").dumps(exp))
        return out, exp

    def _full_cache_map(self, exp):
        last = exp["register_range_end"]
        cells = {"Eligibility Register": {}, "Funding Dashboard": {},
                 "County Rollup": {}, "Appeal Queue": {}}
        for row, rec in enumerate(exp["records"], start=2):
            cells["Eligibility Register"][f"J{row}"] = rec["eligible_amount"]
            cells["Eligibility Register"][f"K{row}"] = rec["priority_score"]
            cells["Eligibility Register"][f"L{row}"] = rec["review_status"]
        dash = exp["dashboard"]
        cells["Funding Dashboard"]["B4"] = dash["total_applications"]
        cells["Funding Dashboard"]["B5"] = dash["total_eligible_amount"]
        cells["Funding Dashboard"]["B6"] = dash["senior_review_count"]
        cells["Funding Dashboard"]["B7"] = dash["appeal_review_count"]
        cells["Funding Dashboard"]["B8"] = dash["average_priority_score"]
        for row, county in enumerate(COUNTY_ORDER, start=2):
            apps, total, senior = exp["county_rollup"][county]
            cells["County Rollup"][f"B{row}"] = apps
            cells["County Rollup"][f"C{row}"] = total
            cells["County Rollup"][f"D{row}"] = senior
        for row, q in enumerate(exp["appeal_queue"], start=2):
            cells["Appeal Queue"][f"D{row}"] = q["eligible_amount"]
            cells["Appeal Queue"][f"E{row}"] = q["review_status"]
        return cells

    def test_full_correct_caches_pass(self):
        out, exp = self._build()
        inject_cached_values(out, self._full_cache_map(exp))
        result = validate.check(out, self.dir / "expected.json")
        self.assertEqual(result["mode"], "formal")
        self.assertIs(result["caches_present"], True)
        self.assertFalse([k for k, v in result["checks"].items() if v is False])

    def test_wrong_cache_fails(self):
        out, exp = self._build()
        cells = self._full_cache_map(exp)
        cells["Eligibility Register"]["J2"] = exp["records"][0]["eligible_amount"] + 1
        inject_cached_values(out, cells)
        result = validate.check(out, self.dir / "expected.json")
        self.assertIs(result["caches_present"], True)  # present but wrong
        self.assertIs(result["checks"]["eligible_values"], False)
        self.assertTrue(any(v is False for v in result["checks"].values()))

    def test_all_caches_missing_fails(self):
        out, _exp = self._build()
        result = validate.check(out, self.dir / "expected.json")
        self.assertIs(result["caches_present"], False)
        self.assertEqual(result["checks"]["eligible_values"], "missing_formula_caches")

    def test_first_cell_present_but_later_missing_fails(self):
        out, exp = self._build()
        cells = {"Eligibility Register": {"J2": exp["records"][0]["eligible_amount"]}}
        inject_cached_values(out, cells)
        result = validate.check(out, self.dir / "expected.json")
        self.assertIs(result["caches_present"], False)
        self.assertIn("Eligibility Register!J3", result["checks"]["missing_cache_cells"])
        # the injected first cell is NOT reported missing
        self.assertNotIn("Eligibility Register!J2", result["checks"]["missing_cache_cells"])

    def test_legal_zero_is_not_missing(self):
        out, exp = self._build()
        cells = self._full_cache_map(exp)
        cells["Eligibility Register"]["J2"] = 0  # legal cached 0, wrong value
        inject_cached_values(out, cells)
        result = validate.check(out, self.dir / "expected.json")
        self.assertIs(result["caches_present"], True)  # 0 is not None -> present
        self.assertIs(result["checks"]["eligible_values"], False)  # but wrong value


if __name__ == "__main__":
    unittest.main()
