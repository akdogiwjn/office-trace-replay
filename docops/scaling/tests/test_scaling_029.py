"""Small directed checks for the scaled PPTX 029 synthetic variants.

Builds/validates tiny 2-unit fixtures: synthesis determinism, scale counts,
builder page counts, per-unit KPI/risk/mitigation/action/decision tables, the
locked legal page preservation, footers, forbidden draft terms, and the dynamic
validator's positive and negative paths (dropped pages, tampered locked legal
page, wrong last-unit facts, banned text). No LibreOffice or pdftoppm is
invoked.
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

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches

synth = importlib.import_module("scaling.cases.029.synth")
expected_mod = importlib.import_module("scaling.cases.029.expected")
bld = importlib.import_module("scaling.cases.029.scripts.build_qbr_release_variant")
validate = importlib.import_module("scaling.cases.029.scripts.validate_qbr_release_variant")
common = importlib.import_module("scaling.cases.common")


def make_fixture(dir_path: Path, n: int = 2, seed: int = 7):
    units = synth.make_units(n, random.Random(seed))
    legal = dict(synth.legal_slide_content("029-u5", seed))
    source = synth.write_source_pptx(units, dir_path, "in.pptx", legal)
    prs = Presentation(str(source))
    legal["semantic_snapshot"] = synth.legal_semantic_snapshot(prs)
    units_path = synth.write_units_json("029-u5", units, "in.pptx", dir_path, legal)
    data = json.loads(units_path.read_text(encoding="utf-8"))
    data["input_path"] = str(source)
    units_path.write_text(json.dumps(data), encoding="utf-8")
    out = dir_path / "out.pptx"
    bld.build(units_path, out)
    expected_path = dir_path / "expected.json"
    exp = expected_mod.write_expected("029-u5", units_path, expected_path)
    return units, units_path, out, expected_path, exp


def legal_texts(slide) -> list[str]:
    return [shape.text for shape in slide.shapes if getattr(shape, "has_text_frame", False)]


class TestSynth029(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_same_seed_same_bytes(self):
        a = synth.generate("029-u5", self.dir / "a")["input"]
        b = synth.generate("029-u5", self.dir / "b")["input"]
        self.assertEqual(hashlib.sha256(a.read_bytes()).hexdigest(),
                         hashlib.sha256(b.read_bytes()).hexdigest())

    def test_generation_does_not_touch_official_payload(self):
        official = (common.docops_root() / "payload/tasks/029/seed/root/"
                    "docops_v2_l3_029_pptx_qbr_release_deck_input.pptx")
        before = hashlib.sha256(official.read_bytes()).hexdigest()
        synth.generate("029-u5", self.dir / "out")
        self.assertEqual(before, hashlib.sha256(official.read_bytes()).hexdigest())

    def test_scale_counts(self):
        for variant, units_n, pages in (("029-u5", 5, 41), ("029-u10", 10, 81)):
            info = synth.generate(variant, self.dir / variant)
            sm = info["scale_metadata"]
            self.assertEqual(sm["units"], units_n)
            self.assertEqual(sm["output_slides"], pages)
            self.assertEqual(sm["input_slides"], units_n * 8 + 5)
            self.assertEqual(len(set(sm["unit_ids"])), units_n)
            self.assertEqual(sm["expected_render_images"], 1)

    def test_source_contains_draft_material_and_legal_page(self):
        info = synth.generate("029-u5", self.dir / "out")
        prs = Presentation(info["input"])
        self.assertEqual(prs.slides[-1]._element.cSld.get("name"),
                         "Reference - Locked Legal")
        text = "\n".join(sh.text_frame.text for s in prs.slides for sh in s.shapes
                         if sh.has_text_frame)
        for term in ("Draft: QBR Release Deck", "Scratch Backup",
                     "Deprecated Roadmap", "Placeholder -"):
            self.assertIn(term, text, term)

    def test_units_unique(self):
        units = synth.make_units(3, random.Random(7))
        self.assertEqual(len({u["id"] for u in units}), 3)
        self.assertEqual(len({u["name"] for u in units}), 3)


class TestBuildValidate029(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.units, self.units_path, self.out, self.expected_path, self.exp = \
            make_fixture(self.dir)

    def test_build_two_units_and_validate(self):
        self.assertEqual(len(Presentation(self.out).slides), 17)
        report = validate.check(self.out, self.expected_path)
        self.assertEqual(report["slide_count"], 17)
        self.assertEqual(report["errors"], [])

    def test_locked_legal_preserved_last(self):
        prs = Presentation(self.out)
        self.assertEqual(len(prs.slides), 17)
        legal = prs.slides[-1]
        self.assertEqual(legal._element.cSld.get("name"), "Reference - Locked Legal")
        self.assertEqual(len(legal.shapes), self.exp["legal_slide"]["shape_count"])
        self.assertEqual(legal_texts(legal), self.exp["legal_slide"]["texts"])
        self.assertEqual(legal.notes_slide.notes_text_frame.text,
                         self.exp["legal_slide"]["notes"])
        legal_visible = "\n".join(legal_texts(legal))
        self.assertNotIn("QBR Release |", legal_visible)

    def test_footers_and_notes_per_unit(self):
        prs = Presentation(self.out)
        total = self.exp["total_pages"]
        for slide_index in range(1, total):
            text = "\n".join(sh.text for sh in prs.slides[slide_index - 1].shapes
                             if getattr(sh, "has_text_frame", False))
            notes = prs.slides[slide_index - 1].notes_slide.notes_text_frame.text
            self.assertTrue(notes)
            within = None
            for group in self.exp["units"]:
                if group["page_start"] <= slide_index <= group["page_end"]:
                    within = slide_index - group["page_start"]
                    break
            self.assertIsNotNone(within)
            if within in (2, 3, 4, 5, 6, 7):
                self.assertIn("QBR Release | 2026-06-05", text)
                self.assertIn(f"Slide {slide_index} of {total}", text)
            else:
                self.assertNotIn("QBR Release | 2026-06-05", text)

    def test_validate_negative_drop_last_unit_pages(self):
        prs = Presentation(self.out)
        sld_id_list = prs.slides._sldIdLst
        for sld_id in list(sld_id_list)[-9:]:  # 8 public pages + legal
            sld_id_list.remove(sld_id)
            prs.part.drop_rel(sld_id.rId)
        self.out.unlink()
        prs.save(self.out)
        report = validate.check(self.out, self.expected_path)
        self.assertTrue(report["errors"])

    def test_validate_negative_missing_public_page(self):
        prs = Presentation(self.out)
        sld_id_list = prs.slides._sldIdLst
        sld_id = sld_id_list[8]
        sld_id_list.remove(sld_id)
        prs.part.drop_rel(sld_id.rId)
        self.out.unlink()
        prs.save(self.out)
        report = validate.check(self.out, self.expected_path)
        self.assertTrue(report["errors"])

    def test_validate_negative_legal_text_changed(self):
        prs = Presentation(self.out)
        legal = prs.slides[-1]
        text_shapes = [sh for sh in legal.shapes if getattr(sh, "has_text_frame", False)]
        text_shapes[1].text = "Confidentiality language ALTERED."
        self.out.unlink()
        prs.save(self.out)
        report = validate.check(self.out, self.expected_path)
        self.assertTrue(any("legal slide text changed" in e for e in report["errors"]),
                        report["errors"])

    def test_validate_negative_legal_shape_count_changed(self):
        prs = Presentation(self.out)
        legal = prs.slides[-1]
        legal.shapes.add_textbox(0, 0, 1, 1).text = "extra shape"
        self.out.unlink()
        prs.save(self.out)
        report = validate.check(self.out, self.expected_path)
        self.assertTrue(any("shape count changed" in e for e in report["errors"]),
                        report["errors"])

    def test_validate_negative_legal_notes_changed(self):
        prs = Presentation(self.out)
        prs.slides[-1].notes_slide.notes_text_frame.text = "notes altered"
        self.out.unlink()
        prs.save(self.out)
        report = validate.check(self.out, self.expected_path)
        self.assertTrue(any("legal speaker note changed" in e for e in report["errors"]),
                        report["errors"])

    def test_validate_negative_last_unit_fact_wrong(self):
        prs = Presentation(self.out)
        last_group = self.exp["units"][-1]
        slide = prs.slides[last_group["kpi_page"] - 1]
        table = next(sh.table for sh in slide.shapes if getattr(sh, "has_table", False))
        table.cell(1, 1).text = "9.9M"
        self.out.unlink()
        prs.save(self.out)
        report = validate.check(self.out, self.expected_path)
        self.assertTrue(any("KPI table mismatch" in e for e in report["errors"]),
                        report["errors"])

    def test_validate_negative_banned_word_on_public_page(self):
        prs = Presentation(self.out)
        slide = prs.slides[0]
        box = slide.shapes.add_textbox(0, 6.5, 3, 0.3)
        box.text = "Draft: leaked label"
        self.out.unlink()
        prs.save(self.out)
        report = validate.check(self.out, self.expected_path)
        self.assertTrue(any("forbidden pattern" in e for e in report["errors"]),
                        report["errors"])



    def test_legal_semantic_snapshot_present_in_expected(self):
        self.assertIn("semantic_snapshot", self.exp["legal_slide"])
        snap = self.exp["legal_slide"]["semantic_snapshot"]
        self.assertIn("background", snap)
        self.assertIn("shapes", snap)
        self.assertEqual(snap["media_count"], 0)
        self.assertEqual(len(snap["shapes"]), self.exp["legal_slide"]["shape_count"])

    def test_legal_background_changed_fails(self):
        prs = Presentation(self.out)
        legal = prs.slides[-1]
        legal.background.fill.solid()
        legal.background.fill.fore_color.rgb = RGBColor(0xFF, 0x00, 0x00)
        self.out.unlink()
        prs.save(self.out)
        report = validate.check(self.out, self.expected_path)
        self.assertTrue(any("semantic snapshot changed" in e for e in report["errors"]),
                        report["errors"])

    def test_legal_font_color_changed_fails(self):
        prs = Presentation(self.out)
        legal = prs.slides[-1]
        for shape in legal.shapes:
            if getattr(shape, "has_text_frame", False):
                for para in shape.text_frame.paragraphs:
                    for run in para.runs:
                        run.font.color.rgb = RGBColor(0xFF, 0x00, 0x00)
        self.out.unlink()
        prs.save(self.out)
        report = validate.check(self.out, self.expected_path)
        self.assertTrue(any("semantic snapshot changed" in e for e in report["errors"]),
                        report["errors"])

    def test_legal_font_size_changed_fails(self):
        prs = Presentation(self.out)
        legal = prs.slides[-1]
        shape = next(sh for sh in legal.shapes if getattr(sh, "has_text_frame", False))
        shape.text_frame.paragraphs[0].runs[0].font.size = Inches(0.4)
        self.out.unlink()
        prs.save(self.out)
        report = validate.check(self.out, self.expected_path)
        self.assertTrue(any("semantic snapshot changed" in e for e in report["errors"]),
                        report["errors"])

    def test_legal_shape_moved_fails(self):
        prs = Presentation(self.out)
        legal = prs.slides[-1]
        shape = next(sh for sh in legal.shapes if getattr(sh, "has_text_frame", False))
        shape.left = Inches(5.0)
        self.out.unlink()
        prs.save(self.out)
        report = validate.check(self.out, self.expected_path)
        self.assertTrue(any("semantic snapshot changed" in e for e in report["errors"]),
                        report["errors"])

    def test_legal_shape_scaled_fails(self):
        prs = Presentation(self.out)
        legal = prs.slides[-1]
        shape = next(sh for sh in legal.shapes if getattr(sh, "has_text_frame", False))
        shape.width = Inches(11.0)
        self.out.unlink()
        prs.save(self.out)
        report = validate.check(self.out, self.expected_path)
        self.assertTrue(any("semantic snapshot changed" in e for e in report["errors"]),
                        report["errors"])

    def test_normal_parent_template_built_by_builder_still_passes(self):
        # Existing builder output (self.out) passes against the frozen snapshot.
        report = validate.check(self.out, self.expected_path)
        self.assertEqual(report["errors"], [])
if __name__ == "__main__":
    unittest.main()
