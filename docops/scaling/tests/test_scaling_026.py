"""Small directed checks for the scaled PPTX 026 synthetic variants.

Builds/validates tiny 2-unit fixtures: synthesis determinism, scale counts,
builder page counts, per-unit native charts and tables, speaker notes, and the
dynamic validator's positive and negative paths (dropped pages, chart data
pointing at the first unit, wrong notes, wrong last-unit facts). No LibreOffice
or pdftoppm is invoked.
"""
from __future__ import annotations

import hashlib
import importlib
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

from pptx import Presentation

synth = importlib.import_module("scaling.cases.026.synth")
expected_mod = importlib.import_module("scaling.cases.026.expected")
bld = importlib.import_module("scaling.cases.026.scripts.build_climate_disclosure_variant")
validate = importlib.import_module("scaling.cases.026.scripts.validate_climate_disclosure_variant")
common = importlib.import_module("scaling.cases.common")


def make_fixture(dir_path: Path, n: int = 2, seed: int = 7):
    units = synth.make_units(n, random.Random(seed))
    source = synth.write_source_pptx(units, dir_path, "in.pptx")
    units_path = synth.write_units_json("026-u5", units, "in.pptx", dir_path)
    data = json.loads(units_path.read_text(encoding="utf-8"))
    data["input_path"] = str(source)
    units_path.write_text(json.dumps(data), encoding="utf-8")
    out = dir_path / "out.pptx"
    bld.build(units_path, out)
    expected_path = dir_path / "expected.json"
    exp = expected_mod.write_expected("026-u5", units_path, expected_path)
    return units, units_path, out, expected_path, exp


def slide_chart_part(pptx_path: Path, slide_index0: int) -> str:
    with zipfile.ZipFile(pptx_path) as z:
        rels = z.read(f"ppt/slides/_rels/slide{slide_index0 + 1}.xml.rels").decode()
    match = re.search(r'Target="\.\./charts/(chart\d+\.xml)"', rels)
    if not match:
        raise AssertionError(f"no chart relation on slide {slide_index0 + 1}")
    return f"ppt/charts/{match.group(1)}"


def rewrite_zip(src: Path, dst: Path, replacements: dict):
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename in replacements:
                data = replacements[item.filename]
            zout.writestr(item, data)


def set_chart_values(xml_bytes: bytes, values: list[str]) -> bytes:
    xml = xml_bytes.decode("utf-8")
    block_re = re.compile(r"<c:numCache>.*?</c:numCache>", re.S)
    body = ["<c:numCache>", f'<c:ptCount val="{len(values)}"/>']
    for index, value in enumerate(values):
        body.append(f'<c:pt idx="{index}"><c:v>{value}</c:v></c:pt>')
    body.append("</c:numCache>")
    return block_re.sub("".join(body), xml).encode("utf-8")


def read_numcache_values(xml_bytes: bytes) -> list[str]:
    block_re = re.compile(r"<c:numCache>.*?</c:numCache>", re.S)
    block = block_re.search(xml_bytes.decode("utf-8"))
    if not block:
        raise AssertionError("no numCache in chart XML")
    return re.findall(r"<c:v>([^<]*)</c:v>", block.group(0))


class TestSynth026(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_same_seed_same_bytes(self):
        a = synth.generate("026-u5", self.dir / "a")["input"]
        b = synth.generate("026-u5", self.dir / "b")["input"]
        self.assertEqual(hashlib.sha256(a.read_bytes()).hexdigest(),
                         hashlib.sha256(b.read_bytes()).hexdigest())

    def test_generation_does_not_touch_official_payload(self):
        official = (common.docops_root() / "payload/tasks/026/seed/root/"
                    "docops_v2_l3_026_pptx_climate_disclosure_chart_rebuild_input.pptx")
        before = hashlib.sha256(official.read_bytes()).hexdigest()
        synth.generate("026-u5", self.dir / "out")
        self.assertEqual(before, hashlib.sha256(official.read_bytes()).hexdigest())

    def test_scale_counts(self):
        for variant, units_n, pages in (("026-u5", 5, 45), ("026-u10", 10, 90)):
            info = synth.generate(variant, self.dir / variant)
            sm = info["scale_metadata"]
            self.assertEqual(sm["units"], units_n)
            self.assertEqual(sm["output_slides"], pages)
            self.assertEqual(sm["input_slides"], units_n + 3)
            self.assertEqual(len(sm["unit_ids"]), units_n)
            self.assertEqual(len(set(sm["unit_ids"])), units_n)
            self.assertEqual(sm["expected_render_images"], pages)

    def test_source_contains_internal_draft_material(self):
        info = synth.generate("026-u5", self.dir / "out")
        prs = Presentation(info["input"])
        text = "\n".join(sh.text_frame.text for s in prs.slides for sh in s.shapes
                         if sh.has_text_frame)
        for term in ("INTERNAL", "PRIVATE", "555-0100", "do not publish",
                     "personal phone"):
            self.assertIn(term, text, term)


class TestBuildValidate026(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.units, self.units_path, self.out, self.expected_path, self.exp = \
            make_fixture(self.dir)

    def test_build_two_units_and_validate(self):
        self.assertEqual(len(Presentation(self.out).slides), 18)
        report = validate.check(self.out, self.expected_path)
        self.assertEqual(report["slide_count"], 18)
        self.assertEqual(report["errors"], [])

    def test_per_unit_charts_match_expected(self):
        prs = Presentation(self.out)
        for group in self.exp["units"]:
            slide = prs.slides[group["chart_page"] - 1]
            charts = [shape.chart for shape in slide.shapes
                      if getattr(shape, "has_chart", False)]
            self.assertEqual(len(charts), 1)
            self.assertEqual(list(charts[0].plots[0].categories),
                             group["chart"]["categories"])
            self.assertEqual([round(float(v), 4) for v in charts[0].series[0].values],
                             [round(float(v), 4) for v in group["chart"]["values"]])

    def test_notes_contain_unit_names(self):
        prs = Presentation(self.out)
        for group in self.exp["units"]:
            slide = prs.slides[group["page_start"] - 1]
            notes = slide.notes_slide.notes_text_frame.text
            self.assertIn(group["name"], notes)
            self.assertIn("FY2026", notes)

    def test_validate_negative_drop_last_unit_pages(self):
        prs = Presentation(self.out)
        sld_id_list = prs.slides._sldIdLst
        for sld_id in list(sld_id_list)[-9:]:
            sld_id_list.remove(sld_id)
            prs.part.drop_rel(sld_id.rId)
        self.out.unlink()
        prs.save(self.out)
        report = validate.check(self.out, self.expected_path)
        self.assertTrue(report["errors"])

    def test_validate_negative_missing_page(self):
        prs = Presentation(self.out)
        sld_id_list = prs.slides._sldIdLst
        sld_id = sld_id_list[-1]
        sld_id_list.remove(sld_id)
        prs.part.drop_rel(sld_id.rId)
        self.out.unlink()
        prs.save(self.out)
        report = validate.check(self.out, self.expected_path)
        self.assertTrue(report["errors"])

    def test_validate_negative_chart_points_to_first_unit(self):
        last_group = self.exp["units"][-1]
        first_group = self.exp["units"][0]
        chart_slide_index0 = last_group["chart_page"] - 1
        chart_member = slide_chart_part(self.out, chart_slide_index0)
        with zipfile.ZipFile(self.out) as z:
            last_chart = z.read(chart_member)
            first_chart = z.read(slide_chart_part(self.out, first_group["chart_page"] - 1))
        first_values = read_numcache_values(first_chart)
        self.assertNotEqual(read_numcache_values(last_chart), first_values)
        tampered = self.dir / "tampered_chart.pptx"
        rewrite_zip(self.out, tampered, {chart_member: set_chart_values(last_chart, first_values)})
        report = validate.check(tampered, self.expected_path)
        self.assertTrue(any("chart values" in e for e in report["errors"]), report["errors"])

    def test_validate_negative_wrong_notes(self):
        prs = Presentation(self.out)
        last_slide = prs.slides[-1]
        last_slide.notes_slide.notes_text_frame.text = "completely wrong note"
        self.out.unlink()
        prs.save(self.out)
        report = validate.check(self.out, self.expected_path)
        self.assertTrue(any("notes" in e for e in report["errors"]), report["errors"])

    def test_validate_negative_last_unit_fact_wrong(self):
        prs = Presentation(self.out)
        last_group = self.exp["units"][-1]
        slide = prs.slides[last_group["inventory_page"] - 1]
        table = next(sh.table for sh in slide.shapes if getattr(sh, "has_table", False))
        table.cell(1, 1).text = "999999"
        self.out.unlink()
        prs.save(self.out)
        report = validate.check(self.out, self.expected_path)
        self.assertTrue(any("inventory table mismatch" in e for e in report["errors"]),
                        report["errors"])


if __name__ == "__main__":
    unittest.main()
