"""Small directed checks for the scaled PDF pdfwf005 synthetic variants.

Runs tiny fixtures only: input synthesis (real multi-page PDF with "Draft: "
prefixes and obsolete dividers), independent expectation derivation, 2-group
build -> 12 pages with correct bookmarks/page labels, positive/negative
validation and the forbidden "Draft:"/obsolete residual guards. No pdftoppm /
montage rendering here.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "docops"))

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject

synth = importlib.import_module("scaling.cases.pdfwf005.synth")
expected_mod = importlib.import_module("scaling.cases.pdfwf005.expected")
bld = importlib.import_module("scaling.cases.pdfwf005.scripts.rebuild_closeout_binder_variant")
val = importlib.import_module("scaling.cases.pdfwf005.scripts.validate_closeout_binder_variant")
common = importlib.import_module("scaling.cases.common")


def tiny_fixture(dir_path: Path, n: int = 2):
    """A small n-group fixture: groups.json + input PDF + expected.json."""
    dir_path.mkdir(parents=True, exist_ok=True)
    groups = [synth.make_group(i) for i in range(n)]
    groups_data = {
        "schema": "docops-scaling-groups-v1",
        "variant_task_id": "pdfwf005-u5",
        "seed": 7,
        "pages_per_group": synth.PAGES_PER_GROUP,
        "live_pages_per_group": synth.LIVE_PAGES_PER_GROUP,
        "draft_prefix": synth.DRAFT_PREFIX,
        "obsolete_title": synth.OBSOLETE_TITLE,
        "source_layout": dict(synth.SOURCE_LAYOUT),
        "live_order": list(synth.LIVE_ORDER),
        "groups": groups,
    }
    groups_path = dir_path / "groups.json"
    groups_path.write_text(json.dumps(groups_data))
    src = synth.write_input_pdf(dir_path, "fixture_input.pdf", groups)
    expected_path = dir_path / "expected.json"
    expected_mod.write_expected("pdfwf005-u5", groups_path, expected_path)
    return {"groups": groups, "groups_path": groups_path, "src": src,
            "expected_path": expected_path}


class TestSynthPdfwf005(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_same_seed_same_bytes_and_group_ids(self):
        a = self.dir / "a"
        b = self.dir / "b"
        ia = synth.generate("pdfwf005-u5", a)["input"]
        ib = synth.generate("pdfwf005-u5", b)["input"]
        self.assertEqual(hashlib.sha256(ia.read_bytes()).hexdigest(),
                         hashlib.sha256(ib.read_bytes()).hexdigest())
        ga = [g["group_id"] for g in json.loads((a / "groups.json").read_text())["groups"]]
        gb = [g["group_id"] for g in json.loads((b / "groups.json").read_text())["groups"]]
        self.assertEqual(ga, gb)
        self.assertEqual(len(set(ga)), 5)

    def test_scale_counts(self):
        info = synth.generate("pdfwf005-u20", self.dir / "out")
        sm = info["scale_metadata"]
        self.assertEqual(sm["groups"], 20)
        self.assertEqual(sm["input_pages"], 140)
        self.assertEqual(sm["output_pages"], 120)
        self.assertEqual(sm["bookmarks"], 120)
        self.assertEqual(sm["page_labels"], 120)
        self.assertEqual(sm["render_dpi"], 130)
        self.assertEqual(sm["montage_tile"], "3x2")
        self.assertEqual(sm["unique_group_ids"], 20)

    def test_input_is_real_multi_page_with_prefixes_and_obsolete(self):
        info = synth.generate("pdfwf005-u5", self.dir / "out")
        reader = PdfReader(str(info["input"]))
        self.assertEqual(len(reader.pages), 35)
        for page in reader.pages:
            text = page.extract_text() or ""
            self.assertIn("Draft: ", text)
        obsolete_pages = [p for p in reader.pages
                          if "Obsolete Divider" in (p.extract_text() or "")]
        self.assertEqual(len(obsolete_pages), 5)

    def test_generation_does_not_touch_official_payload(self):
        official = common.docops_root() / (
            "payload/tasks/pdfwf005/seed/root/"
            "pdfwf_005_closeout_binder_page_labels_and_bookmarks_seed.pdf")
        before = hashlib.sha256(official.read_bytes()).hexdigest()
        synth.generate("pdfwf005-u5", self.dir / "out")
        after = hashlib.sha256(official.read_bytes()).hexdigest()
        self.assertEqual(before, after)


class TestBuilderPdfwf005(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.fx = tiny_fixture(self.dir, n=2)
        self.out = self.dir / "out.pdf"

    def test_two_groups_build_twelve_pages_and_validate(self):
        pages = bld.build(self.fx["src"], self.fx["groups_path"], self.out)
        self.assertEqual(pages, 12)
        report = val.check(self.out, self.fx["expected_path"])
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["bookmarks_checked"], 12)
        self.assertEqual(report["labels_checked"], 12)
        self.assertTrue(self.out.stat().st_size > 0)

    def test_bookmarks_and_page_labels(self):
        bld.build(self.fx["src"], self.fx["groups_path"], self.out)
        reader = PdfReader(str(self.out))
        outlines = reader.outline
        expected_titles = (["GRP-001 | " + t for t in synth.LIVE_ORDER] +
                           ["GRP-002 | " + t for t in synth.LIVE_ORDER])
        self.assertEqual([o.title for o in outlines], expected_titles)
        for index, (item, expected_page) in enumerate(zip(
                outlines, list(range(12)))):
            self.assertEqual(reader.get_destination_page_number(item), expected_page,
                             f"bookmark {index}")
        self.assertEqual(list(reader.page_labels), synth.LIVE_ORDER * 2)

    def test_validate_negative_last_group_missing(self):
        fx1 = tiny_fixture(self.dir / "one", n=1)
        out1 = self.dir / "out1.pdf"
        pages = bld.build(fx1["src"], fx1["groups_path"], out1)
        self.assertEqual(pages, 6)
        report = val.check(out1, self.fx["expected_path"])
        self.assertTrue(any("Expected 12 pages" in e for e in report["errors"]),
                        report["errors"])
        self.assertTrue(any("Expected 12 bookmarks" in e for e in report["errors"]),
                        report["errors"])
        self.assertTrue(any("Expected 12 page labels" in e for e in report["errors"]),
                        report["errors"])

    def test_validate_negative_obsolete_remains(self):
        bld.build(self.fx["src"], self.fx["groups_path"], self.out,
                  include_obsolete=True)
        report = val.check(self.out, self.fx["expected_path"])
        self.assertTrue(any("Obsolete divider page text" in e
                            for e in report["errors"]), report["errors"])

    def test_validate_negative_draft_prefix_remains(self):
        bld.build(self.fx["src"], self.fx["groups_path"], self.out,
                  remove_draft=False)
        report = val.check(self.out, self.fx["expected_path"])
        self.assertTrue(any("'Draft: ' residual remains" in e
                            for e in report["errors"]), report["errors"])

    def test_validate_negative_bookmark_target_wrong(self):
        bld.build(self.fx["src"], self.fx["groups_path"], self.out)
        reader = PdfReader(str(self.out))
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        for title in ["GRP-001 | " + t for t in synth.LIVE_ORDER] + \
                     ["GRP-002 | " + t for t in synth.LIVE_ORDER]:
            writer.add_outline_item(title, 0)
        writer._root_object.update({NameObject("/PageMode"): NameObject("/UseOutlines")})
        broken = self.dir / "broken.pdf"
        with broken.open("wb") as handle:
            writer.write(handle)
        report = val.check(broken, self.fx["expected_path"])
        self.assertTrue(any("points to page 0" in e for e in report["errors"]),
                        report["errors"])

    def test_validate_negative_page_label_wrong(self):
        bld.build(self.fx["src"], self.fx["groups_path"], self.out)
        reader = PdfReader(str(self.out))
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        for index in range(12):
            writer.set_page_label(index, index, style=None,
                                  prefix=f"WRONG-{index}", start=0)
        broken = self.dir / "broken_labels.pdf"
        with broken.open("wb") as handle:
            writer.write(handle)
        report = val.check(broken, self.fx["expected_path"])
        self.assertTrue(any("page label" in e and "expected" in e
                            for e in report["errors"]), report["errors"])

    def test_build_output_is_deterministic(self):
        bld.build(self.fx["src"], self.fx["groups_path"], self.out)
        out2 = self.dir / "out2.pdf"
        bld.build(self.fx["src"], self.fx["groups_path"], out2)
        self.assertEqual(hashlib.sha256(self.out.read_bytes()).hexdigest(),
                         hashlib.sha256(out2.read_bytes()).hexdigest())


class TestExpectedPdfwf005(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_expected_scales_with_groups(self):
        for variant, count in (("pdfwf005-u5", 5), ("pdfwf005-u20", 20)):
            info = synth.generate(variant, self.dir / variant)
            exp = expected_mod.compute(info["groups"])
            self.assertEqual(exp["group_count"], count)
            self.assertEqual(exp["total_pages"], count * 6)
            self.assertEqual(len(exp["bookmark_titles"]), count * 6)
            self.assertEqual(len(exp["page_labels"]), count * 6)
            self.assertEqual(exp["groups"][-1]["page_start"], (count - 1) * 6 + 1)
            for group in exp["groups"]:
                self.assertEqual(len(group["live_titles"]), 6)
                self.assertEqual(len(group["bookmark_labels"]), 6)
                self.assertEqual(group["obsolete_title"], "Obsolete Divider")


if __name__ == "__main__":
    unittest.main()
