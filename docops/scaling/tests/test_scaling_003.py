"""Small directed checks for the scaled Word 003 synthetic variants.

Runs tiny fixtures only: input synthesis (per-unit tracked changes, comments,
bookmarks), the independent expectation derivation, the parameterized builder's
per-stage coverage of a second unit, final rebuild and positive/negative
validation. No LibreOffice, no PDF export and no full-scale processing here.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import random
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "docops"))

from docx import Document
from lxml import etree

synth = importlib.import_module("scaling.cases.003.synth")
expected_mod = importlib.import_module("scaling.cases.003.expected")
bld = importlib.import_module("scaling.cases.003.scripts.build_public_packet_variant")
val = importlib.import_module("scaling.cases.003.scripts.validate_public_packet_variant")
common = importlib.import_module("scaling.cases.common")

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}


def tiny_fixture(dir_path: Path, n: int = 2):
    """A small n-unit fixture: units.json + source DOCX + expected.json."""
    rng = random.Random(2026110505)
    units = synth.make_units(n, rng)
    synth.write_units_json("003-u100", units, dir_path)
    src = synth.write_source_docx(
        units, dir_path, "fixture_input.docx")
    expected_path = dir_path / "expected.json"
    expected_mod.write_expected("003-u100", dir_path / "units.json", expected_path)
    return {"units": units, "units_path": dir_path / "units.json",
            "src": src, "expected_path": expected_path}


class TestSynth003(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_same_seed_same_bytes_and_business_content(self):
        a = self.dir / "a"
        b = self.dir / "b"
        ia = synth.generate("003-u100", a)["input"]
        ib = synth.generate("003-u100", b)["input"]
        self.assertEqual(hashlib.sha256(ia.read_bytes()).hexdigest(),
                         hashlib.sha256(ib.read_bytes()).hexdigest())
        da = Document(ia)
        db = Document(ib)
        ids_a = [u["id"] for u in json.loads((a / "units.json").read_text())["units"]]
        ids_b = [u["id"] for u in json.loads((b / "units.json").read_text())["units"]]
        self.assertEqual(ids_a, ids_b)
        self.assertEqual(len(ids_a), 100)

    def test_source_contains_comments_tracked_changes_bookmarks(self):
        info = synth.generate("003-u100", self.dir / "out")
        src = info["input"]
        with zipfile.ZipFile(src) as z:
            names = set(z.namelist())
            doc_root = etree.fromstring(z.read("word/document.xml"))
            comments = etree.fromstring(z.read("word/comments.xml"))
        self.assertIn("word/comments.xml", names)
        self.assertEqual(len(doc_root.xpath(".//w:commentRangeStart", namespaces=NS)), 100)
        self.assertEqual(len(doc_root.xpath(".//w:del", namespaces=NS)), 201)   # 100 units x2 + global
        self.assertEqual(len(doc_root.xpath(".//w:ins", namespaces=NS)), 201)
        self.assertEqual(len(doc_root.xpath(".//w:bookmarkStart", namespaces=NS)), 100)
        # every unit has one comment
        self.assertEqual(len(comments.xpath(".//w:comment", namespaces=NS)), 100)

    def test_generation_does_not_touch_official_payload(self):
        official = common.docops_root() / (
            "payload/tasks/003/seed/root/"
            "docops_v2_l3_003_docx_public_records_release_metadata_cleanup_input.docx")
        before = hashlib.sha256(official.read_bytes()).hexdigest()
        synth.generate("003-u100", self.dir / "out")
        after = hashlib.sha256(official.read_bytes()).hexdigest()
        self.assertEqual(before, after)


class TestBuilder003(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.fx = tiny_fixture(self.dir, n=2)
        self.stages = self.dir / "stages"
        self.out = self.dir / "out.docx"

    def _build(self):
        n = bld.build(self.fx["src"], self.fx["units_path"], self.out, self.stages)
        return n

    def test_build_two_units_and_validate(self):
        n = self._build()
        self.assertEqual(n, 2)
        report = val.check(self.out, self.fx["expected_path"])
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["measured"]["tables"], 5)  # 1 agg + 2 units + category + checklist

    def test_front_stages_cover_second_unit(self):
        """Tracked changes, comments and corrections for unit 2 must all be handled."""
        units = self.fx["units"]
        unit2 = units[1]
        s1 = self.stages / "01.docx"
        bld.stage_1_resolve_tracked_changes(self.fx["src"], s1)
        with zipfile.ZipFile(s1) as z:
            doc1 = etree.fromstring(z.read("word/document.xml"))
        self.assertEqual(len(doc1.xpath(".//w:del", namespaces=NS)), 0)
        self.assertEqual(len(doc1.xpath(".//w:ins", namespaces=NS)), 0)
        text1 = Document(s1)
        p2 = next(p for p in text1.paragraphs if f"Claim {unit2['id']} correction" in p.text)
        self.assertIn("REVIEWED", p2.text)

        s2 = self.stages / "02.docx"
        bld.stage_2_remove_comments(s1, s2)
        with zipfile.ZipFile(s2) as z:
            names = set(z.namelist())
            doc2 = etree.fromstring(z.read("word/document.xml"))
        self.assertNotIn("word/comments.xml", names)
        self.assertEqual(len(doc2.xpath(".//w:commentRangeStart", namespaces=NS)), 0)
        self.assertEqual(len(doc2.xpath(".//w:commentReference", namespaces=NS)), 0)

        s3 = self.stages / "03.docx"
        bld.stage_3_clean_metadata(s2, s3)
        s4 = self.stages / "04.docx"
        data = json.loads(self.fx["units_path"].read_text())
        bld.stage_4_apply_correction_memo(s3, s4, data)
        doc4 = Document(s4)
        p4 = next(p for p in doc4.paragraphs if f"Claim {unit2['id']} correction" in p.text)
        self.assertIn(f"${unit2['right_amount']}", p4.text)
        self.assertIn(unit2["right_status"], p4.text)
        self.assertNotIn(f"${unit2['wrong_amount']}", p4.text)
        self.assertNotIn(unit2["wrong_status"], p4.text)

    def test_final_rebuild_covers_second_unit_and_redacts_private(self):
        self._build()
        report = val.check(self.out, self.fx["expected_path"])
        self.assertEqual(report["errors"], [])
        doc = Document(self.out)
        unit2 = self.fx["units"][1]
        all_text = " ".join(p.text for p in doc.paragraphs)
        self.assertIn(f"Unit {unit2['id']} — {unit2['category']}", all_text)
        self.assertIn(f"${unit2['right_amount']}", all_text)
        self.assertNotIn(unit2["claimant"], all_text)
        self.assertNotIn(unit2["phone"], all_text)

    def test_validate_negative_unit_missing(self):
        self._build()
        doc = Document(self.out)
        unit2 = self.fx["units"][1]
        heading = next(p for p in doc.paragraphs
                       if p.text == f"Unit {unit2['id']} — {unit2['category']}")
        heading._p.getparent().remove(heading._p)
        self.out.unlink()
        doc.save(self.out)
        report = val.check(self.out, self.fx["expected_path"])
        self.assertTrue(any("Headings differ" in e for e in report["errors"]), report["errors"])

    def test_validate_negative_table_missing(self):
        self._build()
        doc = Document(self.out)
        unit2 = self.fx["units"][1]
        # remove unit 2's determination table (first table that contains its id)
        target = None
        for table in doc.tables:
            if unit2["id"] in " ".join(c.text for r in table.rows for c in r.cells):
                target = table
                break
        self.assertIsNotNone(target)
        target._tbl.getparent().remove(target._tbl)
        self.out.unlink()
        doc.save(self.out)
        report = val.check(self.out, self.fx["expected_path"])
        self.assertTrue(any("determination table missing" in e for e in report["errors"]),
                        report["errors"])

    def test_validate_negative_wrong_correction(self):
        self._build()
        doc = Document(self.out)
        unit2 = self.fx["units"][1]
        wrong = f"${unit2['right_amount']}"
        # corrupt the corrected amount everywhere it appears for unit 2 (the
        # builder writes the same corrected value into the narrative and the
        # determination table, so a real correction bug hits both)
        for paragraph in doc.paragraphs:
            for run in paragraph.runs:
                if wrong in run.text:
                    run.text = run.text.replace(wrong, "$1")
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        for run in paragraph.runs:
                            if wrong in run.text:
                                run.text = run.text.replace(wrong, "$1")
        self.out.unlink()
        doc.save(self.out)
        report = val.check(self.out, self.fx["expected_path"])
        self.assertTrue(any(unit2["id"] in e and "required corrected facts" in e
                            for e in report["errors"]), report["errors"])

    def test_build_output_is_deterministic(self):
        bld.build(self.fx["src"], self.fx["units_path"], self.out, self.stages)
        out2 = self.dir / "out2.docx"
        bld.build(self.fx["src"], self.fx["units_path"], out2, self.dir / "stages2")
        self.assertEqual(hashlib.sha256(self.out.read_bytes()).hexdigest(),
                         hashlib.sha256(out2.read_bytes()).hexdigest())

    def test_validate_rejects_mixed_case_private_value_only_in_package_xml(self):
        self._build()
        private_value = self.fx["units"][1]["claimant"]
        with zipfile.ZipFile(self.out) as archive:
            entries = [(info, archive.read(info.filename)) for info in archive.infolist()]
        with zipfile.ZipFile(self.out, "w") as archive:
            for info, content in entries:
                if info.filename == "word/settings.xml":
                    settings = etree.fromstring(content)
                    settings.append(etree.Comment(" " + private_value.swapcase() + " "))
                    content = etree.tostring(settings, xml_declaration=True, encoding="UTF-8")
                archive.writestr(info, content)
        report = val.check(self.out, self.fx["expected_path"])
        self.assertIn(f"Private value remains in package XML: {private_value}", report["errors"])
        self.assertFalse(any("Forbidden visible text" in e for e in report["errors"]))


class TestExpected003(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_expected_structure_scales_with_units(self):
        for variant, count in (("003-u100", 100), ("003-u500", 500)):
            info = synth.generate(variant, self.dir / variant)
            exp = expected_mod.compute(info["units"])
            self.assertEqual(exp["unit_count"], count)
            self.assertEqual(exp["table_count"], count + 3)
            self.assertEqual(len(exp["headings"]), 4 + count + 4)
            self.assertEqual(exp["corrected_values"][1], str(count))
            self.assertEqual(len(exp["per_unit_corrected"]), count)
            for section in exp["units"]:
                self.assertIn(section["id"], section["required_public"])
                self.assertIn(f"${section['right_amount']}", section["required_public"])

    def test_expected_does_not_share_build_implementation(self):
        build_src = Path(bld.__file__).read_text(encoding="utf-8")
        expected_src = Path(expected_mod.__file__).read_text(encoding="utf-8")
        # the builder reads units.json directly; the oracle derives from it too,
        # but they never share a computed-value function for corrected facts.
        self.assertIn("def compute", expected_src)
        self.assertNotIn("def compute", build_src)
        self.assertIn("w:ins", build_src)  # builder writes OOXML
        self.assertNotIn("OxmlElement", expected_src)


if __name__ == "__main__":
    unittest.main()
