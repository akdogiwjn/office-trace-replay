"""Small directed checks for the scaled PPTX 021 synthetic variants.

Builds/validates tiny 2-region fixtures and tests the per-region contact-sheet
grouping logic without invoking montage / pdftoppm / LibreOffice.
"""
from __future__ import annotations

import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "docops"))

from pptx import Presentation

synth = importlib.import_module("scaling.cases.021.synth")
expected_mod = importlib.import_module("scaling.cases.021.expected")
bld = importlib.import_module("scaling.cases.021.scripts.build_public_shelter_briefing_variant")
validate = importlib.import_module("scaling.cases.021.scripts.validate_public_shelter_briefing_variant")
cs = importlib.import_module("scaling.cases.021.scripts.make_contact_sheets")
common = importlib.import_module("scaling.cases.common")


def two_regions() -> list[dict]:
    return [
        {"id": "north-district", "name": "North District", "slug": "north-district",
         "shelter_count": 18, "accessible_count": 14, "raw_shelter_count": 16,
         "raw_accessible_count": 11, "hotline": "1-800-555-0148",
         "website": "https://city.example/north-district/public",
         "email": "accessibility-north@city.example", "update_date": "2026-07-20",
         "transit_updates": [["Paratransit", "x"], ["Bus Route 4", "x"],
                             ["Bus Route 9", "x"], ["Shuttle", "x"]]},
        {"id": "south-district", "name": "South District", "slug": "south-district",
         "shelter_count": 12, "accessible_count": 8, "raw_shelter_count": 10,
         "raw_accessible_count": 5, "hotline": "1-800-555-0150",
         "website": "https://city.example/south-district/public",
         "email": "accessibility-south@city.example", "update_date": "2026-07-20",
         "transit_updates": [["Paratransit", "x"], ["Bus Route 4", "x"],
                             ["Bus Route 9", "x"], ["Shuttle", "x"]]},
    ]


class TestSynth021(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_region_scales_and_constraints(self):
        for variant in ("021-g5", "021-g10"):
            info = synth.generate(variant, self.dir / variant)
            sm = info["scale_metadata"]
            self.assertEqual(sm["pages"], sm["regions"] * sm["pages_per_region"])
            self.assertTrue(sm["accessible_le_shelter"])
            self.assertEqual(len(sm["shelter_counts"]), sm["regions"])
            # counts vary across regions and every accessible count fits its shelter count
            self.assertGreaterEqual(len(set(sm["shelter_counts"])), 3)
            self.assertGreaterEqual(len(set(sm["accessible_counts"])), 3)
            for shelter, accessible in zip(sm["shelter_counts"], sm["accessible_counts"]):
                self.assertLessEqual(accessible, shelter)

    def test_input_contains_to_be_fixed_material(self):
        info = synth.generate("021-g5", self.dir / "out")
        prs = Presentation(info["input"])
        text = "\n".join(sh.text_frame.text for s in prs.slides for sh in s.shapes
                         if sh.has_text_frame)
        for term in ("DRAFT", "PRIVATE", "555-0199", "eoc.internal", "off-slide"):
            self.assertIn(term, text, term)


class TestBuilderAndValidate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        data = {"schema": "docops-scaling-regions-v1", "variant_task_id": "021-g5",
                "seed": 1, "pages_per_region": 8, "regions": two_regions()}
        self.regions = self.dir / "regions.json"
        self.regions.write_text(json.dumps(data))
        self.expected = self.dir / "expected.json"
        expected_mod.write_expected("021-g5", self.regions, self.expected)
        self.out = self.dir / "out.pptx"

    def test_build_two_regions_and_validate(self):
        count = bld.build(self.regions, self.out)
        self.assertEqual(count, 16)
        report = validate.check(self.out, self.expected)
        self.assertEqual(report["slide_count"], 16)
        self.assertEqual(report["errors"], [])

    def test_validate_negative_drop_a_slide(self):
        bld.build(self.regions, self.out)
        prs = Presentation(self.out)
        prs.slides._sldIdLst.remove(prs.slides._sldIdLst[0])  # drop page 1
        self.out.unlink()
        prs.save(self.out)
        report = validate.check(self.out, self.expected)
        self.assertTrue(any("slide 1" in e for e in report["errors"]), report["errors"])

    def test_validate_negative_wrong_count(self):
        regions = two_regions()
        regions[0]["shelter_count"] = 19  # breaks accessible share/required text
        data = {"schema": "docops-scaling-regions-v1", "variant_task_id": "021-g5",
                "seed": 1, "pages_per_region": 8, "regions": regions}
        (self.dir / "bad.json").write_text(json.dumps(data))
        bld.build(self.dir / "bad.json", self.out)
        report = validate.check(self.out, self.expected)
        self.assertTrue(report["errors"], "expected mismatched count errors")


class TestContactSheets(unittest.TestCase):
    def test_numeric_sort_beats_lexicographic(self):
        tmp = Path(tempfile.mkdtemp())
        for i in range(1, 17):
            (tmp / f"slide-{i}.jpg").write_bytes(b"")
        files = cs.discover_sorted(tmp)
        self.assertEqual([cs.parse_page(f) for f in files], list(range(1, 17)))
        self.assertEqual(files[1].name, "slide-2.jpg")
        self.assertEqual(sorted(files, key=lambda p: p.name)[1].name, "slide-10.jpg")

    def test_zero_padded_names_and_grouping(self):
        tmp = Path(tempfile.mkdtemp())
        for i in range(1, 17):
            (tmp / f"slide-{i:02d}.jpg").write_bytes(b"")
        files = cs.discover_sorted(tmp)
        groups = cs.group_pages(files, 8)
        self.assertEqual(len(groups), 2)
        self.assertEqual([cs.parse_page(g[0]) for g in groups], [1, 9])
        self.assertEqual([cs.parse_page(g[-1]) for g in groups], [8, 16])

    def test_missing_page_rejected(self):
        tmp = Path(tempfile.mkdtemp())
        for i in range(1, 17):
            if i != 5:
                (tmp / f"slide-{i}.jpg").write_bytes(b"")
        files = cs.discover_sorted(tmp)
        with self.assertRaises(ValueError):
            cs.group_pages(files, 8)

    def test_page_count_drives_group_count(self):
        tmp = Path(tempfile.mkdtemp())
        for i in range(1, 41):
            (tmp / f"slide-{i:02d}.jpg").write_bytes(b"")
        groups = cs.group_pages(cs.discover_sorted(tmp), 8)
        self.assertEqual(len(groups), 5)


class TestContactSheetExpectation(unittest.TestCase):
    """Contact sheets must be validated against the frozen expected.json totals."""

    def _write_expected(self, path: Path, total: int, regions: int):
        data = {"schema": "docops-scaling-expectation-v1", "kind": "pptx",
                "total_pages": total, "pages_per_region": 8,
                "regions": [{"id": f"r{i}", "page_start": i * 8 + 1,
                             "page_end": i * 8 + 8, "titles": [], "links": [],
                             "required_texts": []} for i in range(regions)]}
        path.write_text(json.dumps(data))

    def test_thirty_two_of_forty_rejected(self):
        tmp = Path(tempfile.mkdtemp())
        for i in range(1, 33):
            (tmp / f"slide-{i:02d}.jpg").write_bytes(b"")
        expected_path = Path(tempfile.mkdtemp()) / "expected.json"
        self._write_expected(expected_path, 40, 5)
        files = cs.discover_sorted(tmp)
        with self.assertRaises(ValueError) as ctx:
            cs.group_pages(files, 8, total_pages=40, region_count=5)
        self.assertIn("must exactly cover pages 1..40", str(ctx.exception))

    def test_seventy_two_of_eighty_rejected(self):
        tmp = Path(tempfile.mkdtemp())
        for i in range(1, 73):
            (tmp / f"slide-{i:02d}.jpg").write_bytes(b"")
        expected_path = Path(tempfile.mkdtemp()) / "expected.json"
        self._write_expected(expected_path, 80, 10)
        files = cs.discover_sorted(tmp)
        with self.assertRaises(ValueError) as ctx:
            cs.group_pages(files, 8, total_pages=80, region_count=10)
        self.assertIn("1..80", str(ctx.exception))

    def test_full_forty_pages_five_groups_with_mock_montage(self):
        tmp = Path(tempfile.mkdtemp())
        for i in range(1, 41):
            (tmp / f"slide-{i:02d}.jpg").write_bytes(b"")
        expected_path = tmp / "expected.json"
        self._write_expected(expected_path, 40, 5)
        calls = []
        original_run = cs.subprocess.run

        def fake_run(argv, check=True):
            calls.append(argv)

        cs.subprocess.run = fake_run
        try:
            rc = cs.main([str(tmp), "--expected", str(expected_path)])
        finally:
            cs.subprocess.run = original_run
        self.assertEqual(rc, 0)
        self.assertEqual(len(calls), 5)  # one montage per region
        for argv in calls:
            self.assertEqual(argv[0], "montage")
            pages = [cs.parse_page(Path(a)) for a in argv[1:9]]
            self.assertEqual(pages, list(range(cs.parse_page(Path(argv[1])),
                                               cs.parse_page(Path(argv[1])) + 8)))
            self.assertIn("-thumbnail", argv) and self.assertIn("720x405", argv)
            self.assertIn("-tile", argv) and self.assertIn("2x4", argv)
        for i, argv in enumerate(calls, 1):
            self.assertEqual(Path(argv[-1]).name, f"contact_sheet_region_{i:02d}.jpg")
        # every page 1..40 used exactly once
        all_pages = sorted(p for argv in calls for p in [cs.parse_page(Path(a)) for a in argv[1:9]])
        self.assertEqual(all_pages, list(range(1, 41)))


if __name__ == "__main__":
    unittest.main()


class TestExpected021(unittest.TestCase):
    def test_page_mapping_and_links(self):
        tmp = Path(tempfile.mkdtemp())
        data = {"schema": "docops-scaling-regions-v1", "variant_task_id": "021-g5",
                "seed": 1, "pages_per_region": 8, "regions": two_regions()}
        regions = tmp / "regions.json"
        regions.write_text(json.dumps(data))
        exp = expected_mod.write_expected("021-g5", regions, tmp / "expected.json")
        self.assertEqual(exp["total_pages"], 16)
        self.assertEqual(exp["regions"][0]["page_start"], 1)
        self.assertEqual(exp["regions"][0]["page_end"], 8)
        self.assertEqual(exp["regions"][1]["page_start"], 9)
        self.assertEqual(exp["regions"][0]["titles"][0], "Emergency Shelter Public Briefing")
        self.assertIn("— North District", exp["regions"][0]["titles"][1])
        self.assertIn("https://city.example/north-district/public",
                      exp["regions"][0]["links"])


if __name__ == "__main__":
    unittest.main()
