"""Small directed checks for the scaled Word 001 synthetic variants.

Runs tiny fixtures only: input synthesis (DRAFT source), the independent
expectation derivation, the parameterized builder's register coverage of the
last record, final rebuild and positive/negative validation. No LibreOffice, no
PDF export and no full-scale processing here.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "docops"))

from docx import Document

synth = importlib.import_module("scaling.cases.001.synth")
expected_mod = importlib.import_module("scaling.cases.001.expected")
bld = importlib.import_module("scaling.cases.001.scripts.build_controlled_document_release_variant")
val = importlib.import_module("scaling.cases.001.scripts.validate_controlled_document_release_variant")
common = importlib.import_module("scaling.cases.common")


def tiny_fixture(dir_path: Path, n: int = 3):
    """A small n-record fixture: records.json + source DOCX + expected.json."""
    rng = random.Random(2026110601)
    records = synth.make_records(n, rng)
    synth.write_records_json("001-u100", records, dir_path)
    src = synth.write_source_docx(records, dir_path, "fixture_input.docx")
    expected_path = dir_path / "expected.json"
    expected_mod.write_expected("001-u100", dir_path / "records.json", expected_path)
    return {"records": records, "records_path": dir_path / "records.json",
            "src": src, "expected_path": expected_path}


def find_register_table(doc):
    for table in doc.tables:
        if table.rows and [c.text for c in table.rows[0].cells] == expected_mod.REGISTER_HEADER:
            return table
    return None


class TestSynth001(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_same_seed_same_bytes_and_business_content(self):
        a = self.dir / "a"
        b = self.dir / "b"
        ia = synth.generate("001-u100", a)["input"]
        ib = synth.generate("001-u100", b)["input"]
        self.assertEqual(hashlib.sha256(ia.read_bytes()).hexdigest(),
                         hashlib.sha256(ib.read_bytes()).hexdigest())
        ids_a = [r["id"] for r in json.loads((a / "records.json").read_text())["records"]]
        ids_b = [r["id"] for r in json.loads((b / "records.json").read_text())["records"]]
        self.assertEqual(ids_a, ids_b)
        self.assertEqual(len(ids_a), 100)
        self.assertEqual(len(set(ids_a)), 100)

    def test_source_carries_draft_marker_and_internal_errors(self):
        info = synth.generate("001-u100", self.dir / "out")
        src = Document(info["input"])
        text = "\n".join(p.text for p in src.paragraphs)
        self.assertIn("DRAFT", text)
        for marker in ("QMS-PR-700", "version 4.1", "2026-07-01", "5 years",
                       "PRIVATE TODO", "aproval", "effectve"):
            self.assertIn(marker, text)

    def test_generation_does_not_touch_official_payload(self):
        official = common.docops_root() / (
            "payload/tasks/001/seed/root/"
            "docops_v2_l3_001_docx_controlled_document_release_repair_input.docx")
        before = hashlib.sha256(official.read_bytes()).hexdigest()
        synth.generate("001-u100", self.dir / "out")
        after = hashlib.sha256(official.read_bytes()).hexdigest()
        self.assertEqual(before, after)


class TestBuilder001(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.fx = tiny_fixture(self.dir, n=3)
        self.out = self.dir / "out.docx"

    def _build(self):
        n = bld.build(self.fx["src"], self.fx["records_path"], self.out)
        return n

    def test_build_three_records_and_validate(self):
        n = self._build()
        self.assertEqual(n, 3)
        report = val.check(self.out, self.fx["expected_path"])
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["measured"]["tables"], 6)
        self.assertEqual(report["measured"]["register_rows"], 3)

    def test_build_output_is_deterministic(self):
        self._build()
        out2 = self.dir / "out2.docx"
        bld.build(self.fx["src"], self.fx["records_path"], out2)
        self.assertEqual(hashlib.sha256(self.out.read_bytes()).hexdigest(),
                         hashlib.sha256(out2.read_bytes()).hexdigest())

    def test_register_covers_last_record(self):
        self._build()
        report = val.check(self.out, self.fx["expected_path"])
        self.assertEqual(report["errors"], [])
        doc = Document(self.out)
        register = find_register_table(doc)
        last = self.fx["records"][-1]
        row = [c.text for c in register.rows[-1].cells]
        self.assertEqual(row[0], last["id"])
        self.assertIn(last["effective_date"], row)

    def test_validate_negative_last_record_deleted(self):
        self._build()
        doc = Document(self.out)
        register = find_register_table(doc)
        self.assertIsNotNone(register)
        register.rows[-1]._tr.getparent().remove(register.rows[-1]._tr)
        self.out.unlink()
        doc.save(self.out)
        report = val.check(self.out, self.fx["expected_path"])
        self.assertFalse(report["passed"], report["errors"])
        self.assertTrue(any("Register holds" in e or "Register rows differ" in e
                            for e in report["errors"]), report["errors"])

    def test_validate_negative_last_record_replaced_by_first(self):
        self._build()
        doc = Document(self.out)
        register = find_register_table(doc)
        first_row = [c.text for c in register.rows[1].cells]
        for index, cell in enumerate(register.rows[-1].cells):
            cell.text = ""
            cell.paragraphs[0].add_run(first_row[index])
        self.out.unlink()
        doc.save(self.out)
        report = val.check(self.out, self.fx["expected_path"])
        self.assertFalse(report["passed"], report["errors"])
        self.assertTrue(any("Register rows differ" in e for e in report["errors"]),
                        report["errors"])

    def test_validate_negative_last_record_key_value(self):
        self._build()
        doc = Document(self.out)
        register = find_register_table(doc)
        last = self.fx["records"][-1]
        cell = register.rows[-1].cells[3]  # effective date column
        cell.text = ""
        cell.paragraphs[0].add_run("2020-01-01")
        self.assertNotEqual(cell.text, last["effective_date"])
        self.out.unlink()
        doc.save(self.out)
        report = val.check(self.out, self.fx["expected_path"])
        self.assertFalse(report["passed"], report["errors"])
        self.assertTrue(any("Register rows differ" in e for e in report["errors"]),
                        report["errors"])

    def test_validate_negative_document_title_changed(self):
        self._build()
        doc = Document(self.out)
        title = next(p for p in doc.paragraphs
                     if p.style and p.style.name == "Title")
        title.runs[0].text = "Wrong Release Title"
        self.out.unlink()
        doc.save(self.out)
        report = val.check(self.out, self.fx["expected_path"])
        self.assertFalse(report["passed"], report["errors"])
        self.assertTrue(any("Headings differ" in e for e in report["errors"]),
                        report["errors"])

    def test_validate_negative_chapter_table_deleted(self):
        self._build()
        doc = Document(self.out)
        revision = next(t for t in doc.tables
                        if t.rows and t.rows[0].cells[0].text == "Version")
        revision._tbl.getparent().remove(revision._tbl)
        self.out.unlink()
        doc.save(self.out)
        report = val.check(self.out, self.fx["expected_path"])
        self.assertFalse(report["passed"], report["errors"])
        self.assertTrue(any("tables, found" in e for e in report["errors"]),
                        report["errors"])

    def test_forbidden_word_as_legal_substring_not_flagged(self):
        self._build()
        doc = Document(self.out)
        # "Version 4.10" contains "4.1" as a substring but "version 4.1" must
        # not be flagged because the token-boundary check stops at the "0".
        register_body = next(p for p in doc.paragraphs
                             if "controlled document register below" in p.text)
        run = register_body.runs[-1]
        run.text = run.text + " Version 4.10 is supported by this register."
        self.out.unlink()
        doc.save(self.out)
        report = val.check(self.out, self.fx["expected_path"])
        self.assertEqual(report["errors"], [])

    def test_actual_forbidden_word_still_rejected(self):
        self._build()
        doc = Document(self.out)
        register_body = next(p for p in doc.paragraphs
                             if "controlled document register below" in p.text)
        run = register_body.runs[-1]
        run.text = run.text + " version 4.1 must not appear."
        self.out.unlink()
        doc.save(self.out)
        report = val.check(self.out, self.fx["expected_path"])
        self.assertFalse(report["passed"], report["errors"])
        self.assertTrue(any("Forbidden visible text" in e for e in report["errors"]),
                        report["errors"])

    def test_token_boundary_helper(self):
        self.assertEqual(val.forbidden_hits("Version 4.10 is current", "version 4.1"), [])
        self.assertEqual(val.forbidden_hits("Obsolete retirement on 2026-08-05", "2026-09-05"), [])
        self.assertEqual(len(val.forbidden_hits("Retire obsolete copy on 2026-09-05", "2026-09-05")), 1)
        self.assertEqual(val.forbidden_hits("DOC-0010 remains", "DOC-001"), [])
        self.assertEqual(len(val.forbidden_hits("A DRAFT copy remains", "DRAFT")), 1)
        self.assertEqual(len(val.forbidden_hits("Retention is 5 years old", "5 years")), 1)


class TestExpected001(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_expected_structure_scales_with_records(self):
        for variant, count in (("001-u100", 100), ("001-u500", 500)):
            info = synth.generate(variant, self.dir / variant)
            exp = expected_mod.compute(info["records"])
            self.assertEqual(exp["record_count"], count)
            self.assertEqual(exp["table_count"], 6)
            self.assertEqual(exp["paragraph_count"], 35)
            self.assertEqual(len(exp["headings"]), 7)
            self.assertEqual(len(exp["register_rows"]), count)
            self.assertEqual(len(exp["records"]), count)
            for section in exp["records"]:
                self.assertIn(section["id"], section["required_public"])

    def test_expected_does_not_share_build_implementation(self):
        build_src = Path(bld.__file__).read_text(encoding="utf-8")
        expected_src = Path(expected_mod.__file__).read_text(encoding="utf-8")
        self.assertIn("def compute", expected_src)
        self.assertNotIn("def compute", build_src)
        self.assertIn("from docx", build_src)  # builder writes OOXML
        self.assertNotIn("OxmlElement", expected_src)


if __name__ == "__main__":
    unittest.main()
