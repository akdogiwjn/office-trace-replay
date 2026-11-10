"""Small directed checks for the scaled Word 009 synthetic variants.

Runs tiny fixtures only: input synthesis (DRAFT source), the independent
expectation derivation, the parameterized builder's per-case table coverage of
the last case, final rebuild and positive/negative validation. No LibreOffice,
no PDF export and no full-scale processing here.
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

synth = importlib.import_module("scaling.cases.009.synth")
expected_mod = importlib.import_module("scaling.cases.009.expected")
bld = importlib.import_module("scaling.cases.009.scripts.build_incident_manual_variant")
val = importlib.import_module("scaling.cases.009.scripts.validate_incident_manual_variant")
common = importlib.import_module("scaling.cases.common")
u = importlib.import_module("scaling.cases.009.scripts.update_toc_and_render")


def tiny_fixture(dir_path: Path, n: int = 3):
    """A small n-case fixture: cases.json + source DOCX + expected.json."""
    rng = random.Random(2026110603)
    cases = synth.make_cases(n, rng)
    synth.write_cases_json("009-u100", cases, dir_path)
    src = synth.write_source_docx(cases, dir_path, "fixture_input.docx")
    expected_path = dir_path / "expected.json"
    expected_mod.write_expected("009-u100", dir_path / "cases.json", expected_path)
    return {"cases": cases, "cases_path": dir_path / "cases.json",
            "src": src, "expected_path": expected_path}


def find_table(doc, header):
    for table in doc.tables:
        if table.rows and [c.text for c in table.rows[0].cells] == header:
            return table
    return None


class TestSynth009(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_same_seed_same_bytes_and_business_content(self):
        a = self.dir / "a"
        b = self.dir / "b"
        ia = synth.generate("009-u100", a)["input"]
        ib = synth.generate("009-u100", b)["input"]
        self.assertEqual(hashlib.sha256(ia.read_bytes()).hexdigest(),
                         hashlib.sha256(ib.read_bytes()).hexdigest())
        ids_a = [c["id"] for c in json.loads((a / "cases.json").read_text())["cases"]]
        ids_b = [c["id"] for c in json.loads((b / "cases.json").read_text())["cases"]]
        self.assertEqual(ids_a, ids_b)
        self.assertEqual(len(ids_a), 100)
        self.assertEqual(len(set(ids_a)), 100)

    def test_source_carries_draft_marker_and_internal_material(self):
        info = synth.generate("009-u100", self.dir / "out")
        src = Document(info["input"])
        text = "\n".join(p.text for p in src.paragraphs)
        self.assertIn("Draft:", text)
        for marker in ("[INTERNAL]", "phone bridge", "555-0199",
                       "Do not publish", "privileged vendor-root-cause"):
            self.assertIn(marker, text)

    def test_generation_does_not_touch_official_payload(self):
        official = common.docops_root() / (
            "payload/tasks/009/seed/root/"
            "docops_v2_l3_009_docx_incident_manual_publication_input.docx")
        before = hashlib.sha256(official.read_bytes()).hexdigest()
        synth.generate("009-u100", self.dir / "out")
        after = hashlib.sha256(official.read_bytes()).hexdigest()
        self.assertEqual(before, after)


class TestBuilder009(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.fx = tiny_fixture(self.dir, n=3)
        self.out = self.dir / "out.docx"

    def _build(self):
        n = bld.build(self.fx["src"], self.fx["cases_path"], self.out)
        return n

    def test_build_three_cases_and_validate(self):
        n = self._build()
        self.assertEqual(n, 3)
        report = val.check(self.out, self.fx["expected_path"], structure_only=True)
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["measured"]["tables"], 7)
        self.assertEqual(report["measured"]["paragraphs"], 39)

    def test_build_output_is_deterministic(self):
        self._build()
        out2 = self.dir / "out2.docx"
        bld.build(self.fx["src"], self.fx["cases_path"], out2)
        self.assertEqual(hashlib.sha256(self.out.read_bytes()).hexdigest(),
                         hashlib.sha256(out2.read_bytes()).hexdigest())

    def test_last_case_is_really_written(self):
        self._build()
        report = val.check(self.out, self.fx["expected_path"], structure_only=True)
        self.assertEqual(report["errors"], [])
        doc = Document(self.out)
        last = self.fx["cases"][-1]
        approval = find_table(doc, expected_mod.APPROVAL_HEADER)
        self.assertIsNotNone(approval)
        last_row = [c.text for c in approval.rows[-1].cells]
        self.assertEqual(last_row, [last["approver"], last["role"], last["decision"]])

    def test_validate_negative_last_case_row_deleted(self):
        self._build()
        doc = Document(self.out)
        approval = find_table(doc, expected_mod.APPROVAL_HEADER)
        self.assertIsNotNone(approval)
        approval.rows[-1]._tr.getparent().remove(approval.rows[-1]._tr)
        self.out.unlink()
        doc.save(self.out)
        report = val.check(self.out, self.fx["expected_path"], structure_only=True)
        self.assertFalse(report["passed"], report["errors"])
        self.assertTrue(any("holds" in e and "case rows" in e for e in report["errors"]),
                        report["errors"])

    def test_validate_negative_last_case_replaced_by_first(self):
        self._build()
        doc = Document(self.out)
        timeline = find_table(doc, expected_mod.TIMELINE_HEADER)
        first_row = [c.text for c in timeline.rows[1].cells]
        for index, cell in enumerate(timeline.rows[-1].cells):
            cell.text = ""
            cell.paragraphs[0].add_run(first_row[index])
        self.out.unlink()
        doc.save(self.out)
        report = val.check(self.out, self.fx["expected_path"], structure_only=True)
        self.assertFalse(report["passed"], report["errors"])
        self.assertTrue(any("timeline rows differ" in e for e in report["errors"]),
                        report["errors"])

    def test_validate_negative_last_case_key_value(self):
        self._build()
        doc = Document(self.out)
        action = find_table(doc, expected_mod.ACTION_HEADER)
        last = self.fx["cases"][-1]
        cell = action.rows[-1].cells[2]  # due date column
        cell.text = ""
        cell.paragraphs[0].add_run("2099-01-01")
        self.assertNotEqual(cell.text, last["due_date"])
        self.out.unlink()
        doc.save(self.out)
        report = val.check(self.out, self.fx["expected_path"], structure_only=True)
        self.assertFalse(report["passed"], report["errors"])
        self.assertTrue(any("action rows differ" in e for e in report["errors"]),
                        report["errors"])

    def test_validate_negative_document_title_changed(self):
        self._build()
        doc = Document(self.out)
        title = next(p for p in doc.paragraphs
                     if p.style and p.style.name == "Title")
        title.runs[0].text = "Wrong Manual Title"
        self.out.unlink()
        doc.save(self.out)
        report = val.check(self.out, self.fx["expected_path"], structure_only=True)
        self.assertFalse(report["passed"], report["errors"])
        self.assertTrue(any("Title paragraph" in e or "Title style" in e
                            for e in report["errors"]), report["errors"])

    def test_validate_negative_chapter_table_deleted(self):
        self._build()
        doc = Document(self.out)
        timeline = find_table(doc, expected_mod.TIMELINE_HEADER)
        self.assertIsNotNone(timeline)
        timeline._tbl.getparent().remove(timeline._tbl)
        self.out.unlink()
        doc.save(self.out)
        report = val.check(self.out, self.fx["expected_path"], structure_only=True)
        self.assertFalse(report["passed"], report["errors"])
        self.assertTrue(any("tables, found" in e for e in report["errors"]),
                        report["errors"])

    def test_forbidden_word_as_legal_substring_not_flagged(self):
        self._build()
        doc = Document(self.out)
        # "Draft notification prepared" contains "draft" but the forbidden word
        # "draft:" must not be flagged (token boundary, no colon).
        self.assertEqual(val.forbidden_hits("Draft notification prepared", "draft:"), [])
        summary = next(p for p in doc.paragraphs
                       if "This edition covers" in p.text)
        run = summary.runs[-1]
        run.text = run.text + " Draft notification prepared for review."
        self.out.unlink()
        doc.save(self.out)
        report = val.check(self.out, self.fx["expected_path"], structure_only=True)
        self.assertEqual(report["errors"], [])

    def test_actual_forbidden_word_still_rejected(self):
        self._build()
        doc = Document(self.out)
        summary = next(p for p in doc.paragraphs
                       if "This edition covers" in p.text)
        run = summary.runs[-1]
        run.text = run.text + " Draft: legacy working heading remains."
        self.out.unlink()
        doc.save(self.out)
        report = val.check(self.out, self.fx["expected_path"], structure_only=True)
        self.assertFalse(report["passed"], report["errors"])
        self.assertTrue(any("Forbidden visible text" in e for e in report["errors"]),
                        report["errors"])

    def test_token_boundary_helper(self):
        self.assertEqual(val.forbidden_hits("Draft notification prepared", "draft:"), [])
        self.assertEqual(val.forbidden_hits("Customers were notified", "do not publish"), [])
        self.assertEqual(len(val.forbidden_hits("Do not publish this line", "do not publish")), 1)
        self.assertEqual(val.forbidden_hits("Bridge 555-01990", "555-0199"), [])
        self.assertEqual(len(val.forbidden_hits("phone bridge: 555-0199", "phone bridge")), 1)
        self.assertEqual(val.forbidden_hits("Internal notes removed", "[internal]"), [])
        self.assertEqual(len(val.forbidden_hits("Vendor [INTERNAL] note", "[internal]")), 1)


class TestExpected009(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_expected_structure_scales_with_cases(self):
        for variant, count in (("009-u100", 100), ("009-u500", 500)):
            info = synth.generate(variant, self.dir / variant)
            exp = expected_mod.compute(info["cases"])
            self.assertEqual(exp["case_count"], count)
            self.assertEqual(exp["table_count"], 7)
            self.assertEqual(exp["paragraph_count"], 39)
            self.assertEqual(len(exp["headings"]), 7)
            for key in ("timeline", "communication", "exception", "action",
                        "evidence", "approval"):
                self.assertEqual(len(exp["tables"][key]["rows"]), count)
            for section in exp["cases"]:
                suffix = int(section["id"].split("-")[1])
                self.assertIn(f"EX-{suffix:03d}", section["required_public"])
                self.assertIn(f"ACT-{suffix:03d}", section["required_public"])

    def test_expected_does_not_share_build_implementation(self):
        build_src = Path(bld.__file__).read_text(encoding="utf-8")
        expected_src = Path(expected_mod.__file__).read_text(encoding="utf-8")
        self.assertIn("def compute", expected_src)
        self.assertNotIn("def compute", build_src)
        self.assertIn("from docx", build_src)  # builder writes OOXML
        self.assertNotIn("OxmlElement", expected_src)


def toc_pages_text(measured: dict, toc_page: int = 2, total: int = 8) -> list[str]:
    """A synthetic per-page text list with the TOC page plus each section."""
    headings = [title for title, _ in bld.TOC_ENTRIES]
    pages = [""] * total
    pages[toc_page - 1] = "\n".join(headings)  # TOC page lists every heading
    for title, page in measured.items():
        pages[page - 1] = pages[page - 1] + "\n" + title
    return pages


class TestTocPages(unittest.TestCase):
    """The cached TOC page numbers must match the real rendered layout.

    These run without LibreOffice: they exercise extract_toc_entries,
    set_toc_pages and verify_toc_pages against a synthetic rendered-page list
    that mirrors the audit evidence (the old cached 3..7 pages point at the
    wrong rendered pages once sections span more pages).
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.fx = tiny_fixture(self.dir, n=3)
        self.out = self.dir / "out.docx"
        bld.build(self.fx["src"], self.fx["cases_path"], self.out)
        self.headings = expected_mod.HEADINGS

    def _cached(self, pages: dict):
        doc = Document(self.out)
        bld.set_toc_pages(doc, pages)
        doc.save(self.out)
        return Document(self.out)

    def test_matches_real_layout_when_correct(self):
        measured = {"Publication Summary": 3, "Response Timeline": 3,
                    "Customer Communication": 4, "Control Exceptions": 5,
                    "Action Register": 6, "Appendix A - Evidence Index": 7,
                    "Appendix B - Approval Record": 8}
        doc = self._cached(measured)
        errors, info = val.verify_toc_pages(doc, toc_pages_text(measured), self.headings)
        self.assertEqual(errors, [])
        self.assertEqual(info["measured"], measured)

    def test_old_3_7_pages_rejected(self):
        old = {"Publication Summary": 3, "Response Timeline": 3,
               "Customer Communication": 3, "Control Exceptions": 4,
               "Action Register": 5, "Appendix A - Evidence Index": 6,
               "Appendix B - Approval Record": 7}
        measured = {"Publication Summary": 3, "Response Timeline": 3,
                    "Customer Communication": 4, "Control Exceptions": 5,
                    "Action Register": 6, "Appendix A - Evidence Index": 7,
                    "Appendix B - Approval Record": 8}
        doc = self._cached(old)
        errors, _ = val.verify_toc_pages(doc, toc_pages_text(measured), self.headings)
        self.assertTrue(any("Customer Communication" in e for e in errors))
        self.assertTrue(any("Control Exceptions" in e for e in errors))
        self.assertTrue(any("Appendix B" in e for e in errors))

    def test_last_entry_page_wrong_fails(self):
        measured = {"Publication Summary": 3, "Response Timeline": 3,
                    "Customer Communication": 4, "Control Exceptions": 5,
                    "Action Register": 6, "Appendix A - Evidence Index": 7,
                    "Appendix B - Approval Record": 8}
        wrong = dict(measured)
        wrong["Appendix B - Approval Record"] = 6
        doc = self._cached(wrong)
        errors, _ = val.verify_toc_pages(doc, toc_pages_text(measured), self.headings)
        self.assertTrue(any("Appendix B - Approval Record" in e for e in errors))

    def test_title_correct_but_target_page_wrong_fails(self):
        measured = {"Publication Summary": 3, "Response Timeline": 3,
                    "Customer Communication": 4, "Control Exceptions": 5,
                    "Action Register": 6, "Appendix A - Evidence Index": 7,
                    "Appendix B - Approval Record": 8}
        wrong = dict(measured)
        wrong["Action Register"] = 5  # title fine, wrong target page
        doc = self._cached(wrong)
        errors, _ = val.verify_toc_pages(doc, toc_pages_text(measured), self.headings)
        self.assertTrue(any("Action Register" in e and "5" in e for e in errors))

    def test_toc_field_present_but_result_missing_fails(self):
        measured = {"Publication Summary": 3, "Response Timeline": 3,
                    "Customer Communication": 4, "Control Exceptions": 5,
                    "Action Register": 6, "Appendix A - Evidence Index": 7,
                    "Appendix B - Approval Record": 8}
        doc = Document(self.out)
        # keep the TOC field but clear every cached page run (blank result)
        p = bld.find_toc_paragraph(doc)
        for r in p._p.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}r"):
            texts = r.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t")
            for t in texts:
                if t.text and t.text.isdigit():
                    t.text = ""
        doc.save(self.out)
        doc = Document(self.out)
        errors, _ = val.verify_toc_pages(doc, toc_pages_text(measured), self.headings)
        self.assertTrue(any("TOC entry titles differ" in e for e in errors), errors)




class TestTocConvergence(unittest.TestCase):
    """Settle-loop convergence: stable must reflect real two-pass agreement;
    converging on the last allowed pass is stable; not converging at the cap is
    an explicit failure. LibreOffice/pdftotext are monkeypatched (mock)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.fx = tiny_fixture(self.dir, n=2)
        self.out = self.dir / "out.docx"
        bld.build(self.fx["src"], self.fx["cases_path"], self.out)
        self.headings = expected_mod.HEADINGS
        self._orig = (u.measure_heading_pages, u.convert_pdf, u.page_texts)

    def tearDown(self):
        u.measure_heading_pages, u.convert_pdf, u.page_texts = self._orig

    def _run(self, initial, sequence, max_iter):
        seq = list(sequence)
        calls = {"n": 0}

        def fake_measure(pages, headings):
            i = min(calls["n"], len(seq) - 1)
            calls["n"] += 1
            return dict(seq[i]), 2

        u.measure_heading_pages = fake_measure
        u.convert_pdf = lambda docx, tmp: Path("/tmp/fake.pdf")
        u.page_texts = lambda pdf: [""]
        work = Path(tempfile.mkdtemp(dir=self.dir))
        return u.settle_toc(self.out, self.headings, initial, 2, work, max_iter), calls["n"]

    def test_converges_first_pass_stable(self):
        init = {h: 3 for h in self.headings}
        (pages, toc, iterations, stable), calls = self._run(init, [init], 3)
        self.assertTrue(stable)
        self.assertEqual(iterations, 2)
        self.assertEqual(pages, init)

    def test_converges_on_last_allowed_iteration_is_stable(self):
        init = {h: 3 for h in self.headings}
        target = {h: 5 for h in self.headings}
        (pages, toc, iterations, stable), calls = self._run(init, [target, target], 3)
        self.assertTrue(stable)
        self.assertEqual(iterations, 3)
        self.assertEqual(pages, target)

    def test_non_convergence_raises(self):
        init = {h: 3 for h in self.headings}
        a = {h: 5 for h in self.headings}
        b = {h: 7 for h in self.headings}
        with self.assertRaises(RuntimeError) as ctx:
            self._run(init, [a, b, a, b], 3)
        self.assertIn("did not converge", str(ctx.exception))
if __name__ == "__main__":
    unittest.main()
