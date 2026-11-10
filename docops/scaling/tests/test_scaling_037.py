"""Small directed checks for the scaled PDF 037 synthetic variants.

Runs tiny fixtures only: notices synthesis, independent expectation derivation,
2-group build -> 10 pages with correct bookmarks, positive/negative validation
and the forbidden-substring false-positive guard. No pdftoppm rendering here.
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

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject

synth = importlib.import_module("scaling.cases.037.synth")
expected_mod = importlib.import_module("scaling.cases.037.expected")
bld = importlib.import_module("scaling.cases.037.scripts.build_bus_detour_packet_variant")
val = importlib.import_module("scaling.cases.037.scripts.validate_bus_detour_packet_variant")
common = importlib.import_module("scaling.cases.common")


def two_groups() -> list[dict]:
    rng = random.Random(7)
    return [synth.make_notice_group(0, 12, rng),
            synth.make_notice_group(1, 18, rng)]


def tiny_fixture(dir_path: Path, groups: list[dict] | None = None):
    dir_path.mkdir(parents=True, exist_ok=True)
    groups = groups if groups is not None else two_groups()
    notices = {
        "schema": "docops-scaling-notices-v1",
        "variant_task_id": "037-u5",
        "seed": 7,
        "pages_per_group": 5,
        "page_titles": list(synth.PAGE_TITLES),
        "groups": groups,
    }
    notices_path = dir_path / "notices.json"
    notices_path.write_text(json.dumps(notices))
    expected_path = dir_path / "expected.json"
    expected_mod.write_expected("037-u5", notices_path, expected_path)
    return {"notices_path": notices_path, "expected_path": expected_path,
            "groups": groups}


class TestSynth037(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_same_seed_same_bytes_and_business_content(self):
        a = self.dir / "a"
        b = self.dir / "b"
        ia = synth.generate("037-u5", a)["input"]
        ib = synth.generate("037-u5", b)["input"]
        self.assertEqual(hashlib.sha256(ia.read_bytes()).hexdigest(),
                         hashlib.sha256(ib.read_bytes()).hexdigest())
        ga = [g["id"] for g in json.loads((a / "notices.json").read_text())["groups"]]
        gb = [g["id"] for g in json.loads((b / "notices.json").read_text())["groups"]]
        self.assertEqual(ga, gb)

    def test_scale_counts_and_routes(self):
        info = synth.generate("037-u20", self.dir / "out")
        sm = info["scale_metadata"]
        self.assertEqual(sm["notice_groups"], 20)
        self.assertEqual(sm["pages"], 100)
        self.assertGreaterEqual(len(set(sm["closed_stop_counts"])), 6)
        # no legal stop count of 7 (would collide with the forbidden draft value)
        self.assertNotIn(7, sm["closed_stop_counts"])
        # route 210 is legal and must not collide with forbidden "Route 21"
        self.assertIn("Route 210", sm["routes"])
        # legal dates never equal the forbidden draft dates
        for date in sm["closure_begins"] + sm["reopening_targets"]:
            self.assertNotIn(date, ("2026-10-13", "2026-10-27"))

    def test_generation_does_not_touch_official_payload(self):
        official = common.docops_root() / (
            "payload/tasks/037/seed/root/"
            "docops_v2_l3_037_pdf_bus_detour_notice_layout_repair_input.pdf")
        before = hashlib.sha256(official.read_bytes()).hexdigest()
        synth.generate("037-u5", self.dir / "out")
        after = hashlib.sha256(official.read_bytes()).hexdigest()
        self.assertEqual(before, after)


class TestBuilder037(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.fx = tiny_fixture(self.dir)
        self.out = self.dir / "out.pdf"

    def _build(self, groups=None):
        groups = groups if groups is not None else self.fx["groups"]
        notices = self.dir / "n2.json"
        notices.write_text(json.dumps({
            "schema": "docops-scaling-notices-v1", "variant_task_id": "037-u5",
            "seed": 7, "pages_per_group": 5,
            "page_titles": list(synth.PAGE_TITLES), "groups": groups}))
        return bld.build(notices, self.out, self.dir)

    def test_two_groups_build_ten_pages_and_validate(self):
        pages = self._build()
        self.assertEqual(pages, 10)
        report = val.check(self.out, self.fx["expected_path"])
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["bookmarks_checked"], 10)
        self.assertTrue(self.out.stat().st_size > 0)

    def test_bookmarks_point_to_correct_pages(self):
        self._build()
        reader = PdfReader(str(self.out))
        outlines = reader.outline
        self.assertEqual(len(outlines), 10)
        for index, (item, expected_page) in enumerate(zip(
                outlines, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9])):
            self.assertEqual(reader.get_destination_page_number(item), expected_page,
                             f"bookmark {index}")

    def test_validate_negative_second_group_missing(self):
        pages = self._build([self.fx["groups"][0]])
        self.assertEqual(pages, 5)
        report = val.check(self.out, self.fx["expected_path"])
        self.assertTrue(any("Expected 10 pages" in e for e in report["errors"]),
                        report["errors"])
        self.assertTrue(any("Expected 10 bookmarks" in e for e in report["errors"]),
                        report["errors"])

    def test_validate_negative_bookmarks_point_to_first_group(self):
        self._build()
        reader = PdfReader(str(self.out))
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        # repoint every bookmark at page 0 -> second group's targets are wrong
        for title in ["N-01 | Cover", "N-01 | Summary", "N-01 | Matrix",
                      "N-01 | Timeline", "N-01 | Checklist",
                      "N-02 | Cover", "N-02 | Summary", "N-02 | Matrix",
                      "N-02 | Timeline", "N-02 | Checklist"]:
            writer.add_outline_item(title, 0)
        writer._root_object.update({NameObject("/PageMode"): NameObject("/UseOutlines")})
        broken = self.dir / "broken.pdf"
        with broken.open("wb") as handle:
            writer.write(handle)
        report = val.check(broken, self.fx["expected_path"])
        self.assertTrue(any("points to page 0" in e for e in report["errors"]),
                        report["errors"])

    def test_validate_negative_wrong_business_fact(self):
        self._build()
        expected = json.loads(self.fx["expected_path"].read_text())
        # simulate a frozen oracle that requires a fact the builder never emitted
        expected["groups"][1]["required_texts"][1] = "Route 999"
        (self.dir / "bad_expected.json").write_text(json.dumps(expected))
        report = val.check(self.out, self.dir / "bad_expected.json")
        self.assertTrue(any("N-02" in e and "required business facts" in e
                            for e in report["errors"]), report["errors"])

    def test_forbidden_substring_guard(self):
        """A legal value containing an old forbidden word must not false-flag."""
        self.assertFalse(val.contains_token("All 17 stops are shown", "7 stops"))
        self.assertTrue(val.contains_token("All 7 stops are shown", "7 stops"))
        self.assertFalse(val.contains_token("Route 210 is closed", "Route 21"))
        self.assertTrue(val.contains_token("Route 21 is closed", "Route 21"))
        self.assertFalse(val.contains_token("begins 2026-10-130", "2026-10-13"))
        self.assertTrue(val.contains_token("begins 2026-10-13", "2026-10-13"))
        # a 17-stop second group passes end-to-end against its own expectation
        rng = random.Random(3)
        group17 = synth.make_notice_group(0, 12, rng)
        group17["closed_stop_count"] = 17
        group17["stops"] = group17["stops"][:17]
        fx2 = tiny_fixture(self.dir / "fx17", [self.fx["groups"][0], group17])
        out17 = self.dir / "out17.pdf"
        bld.build(fx2["notices_path"], out17, self.dir)
        report = val.check(out17, fx2["expected_path"])
        self.assertEqual(report["errors"], [])

    def test_build_output_is_deterministic(self):
        self._build()
        out2 = self.dir / "out2.pdf"
        notices = self.dir / "n2.json"
        bld.build(notices, out2, self.dir)
        self.assertEqual(hashlib.sha256(self.out.read_bytes()).hexdigest(),
                         hashlib.sha256(out2.read_bytes()).hexdigest())


class TestExpected037(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_expected_scales_with_groups(self):
        for variant, count in (("037-u5", 5), ("037-u20", 20)):
            info = synth.generate(variant, self.dir / variant)
            exp = expected_mod.compute(info["notices"])
            self.assertEqual(exp["group_count"], count)
            self.assertEqual(exp["total_pages"], count * 5)
            self.assertEqual(len(exp["bookmark_titles"]), count * 5)
            self.assertEqual(len(exp["bookmark_page_indexes"]), count * 5)
            self.assertEqual(exp["groups"][-1]["page_start"], (count - 1) * 5 + 1)
            for group in exp["groups"]:
                self.assertEqual(len(group["page_titles"]), 5)
                self.assertEqual(group["orientation"],
                                 ["portrait", "portrait", "landscape", "portrait", "portrait"])


if __name__ == "__main__":
    unittest.main()
