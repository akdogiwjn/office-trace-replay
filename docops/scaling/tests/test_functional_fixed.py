"""Directed checks for the reviewed functional campaign driver (F4-F7).

Exercises the pure helpers of ``scaling.functional_fixed_campaign``:
- acceptance gate (F5): any missing/failed fact fails the task;
- read-only verify spec (F4): source/archive/expected/render read-only, report
  dir writable only, and delivered files checked before/after;
- resume/attempt policy (F7): a completed workload is reused or re-checked but
  never rerun; new attempts use fresh directories;
- index ordering/verification (F6): files final before hashing, readback
  actually performed, tamper detection, no index drift, failure recorded.

No docker, no workload, no image build is started.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "docops/scaling"))

import functional_fixed_campaign as drv


def make_state_attempt(workload, verify):
    return {"attempts": [{"dir": "/tmp/x", "workload": workload, "verify": verify}]}


def good_record(task="016-u100"):
    return {
        "status": "passed", "loops": 1,
        "summary": {"requested": 1, "completed": 1, "successes": 1, "failures": 0},
        "steps": [{"id": "01", "status": "ok", "rc": 0}],
        "round_id": "round-001",
        "output": {"archive_path": "016-u100/round-001/submission/x.xlsx", "sha256": "x"},
    }


class TestAcceptanceGate(unittest.TestCase):
    def test_all_good_passes(self):
        verify = {"rc": 0, "report": {"passed": True}, "pre_sha": {"a": "1"}, "post_sha": {"a": "1"}}
        self.assertEqual(drv.acceptance_problems("016-u100", good_record(), verify, [], True, True), [])

    def test_verify_rc_missing_fails(self):
        problems = drv.acceptance_problems("016-u100", good_record(), {"rc": None}, [], True, True)
        self.assertTrue(any("post-verify rc" in p for p in problems))

    def test_verify_rc_one_fails(self):
        problems = drv.acceptance_problems(
            "016-u100", good_record(),
            {"rc": 1, "report": {"passed": True}}, [], True, True)
        self.assertTrue(any("post-verify rc" in p for p in problems))

    def test_passed_missing_fails(self):
        problems = drv.acceptance_problems(
            "016-u100", good_record(), {"rc": 0, "report": {"errors": []}}, [], True, True)
        self.assertTrue(any("passed not explicitly true" in p for p in problems))

    def test_passed_false_fails(self):
        problems = drv.acceptance_problems(
            "016-u100", good_record(), {"rc": 0, "report": {"passed": False}}, [], True, True)
        self.assertTrue(any("passed not explicitly true" in p for p in problems))

    def test_parse_error_fails(self):
        problems = drv.acceptance_problems(
            "016-u100", good_record(),
            {"rc": 0, "report": {"parse_error": "boom"}}, [], True, True)
        self.assertTrue(any("unparseable" in p for p in problems))

    def test_render_problem_fails(self):
        problems = drv.acceptance_problems(
            "016-u100", good_record(),
            {"rc": 0, "report": {"passed": True}}, ["no dashboard.png"], True, True)
        self.assertTrue(any("render contract" in p for p in problems))

    def test_counts_mismatch_fails(self):
        rec = good_record()
        rec["summary"]["successes"] = 0
        problems = drv.acceptance_problems(
            "016-u100", rec, {"rc": 0, "report": {"passed": True}}, [], True, True)
        self.assertTrue(any("loop counts mismatch" in p for p in problems))

    def test_step_failed_fails(self):
        rec = good_record()
        rec["steps"][0]["status"] = "failed"
        problems = drv.acceptance_problems(
            "016-u100", rec, {"rc": 0, "report": {"passed": True}}, [], True, True)
        self.assertTrue(any("step 01" in p for p in problems))

    def test_frozen_or_binding_fail(self):
        self.assertTrue(drv.acceptance_problems(
            "016-u100", good_record(), {"rc": 0, "report": {"passed": True}},
            [], False, True))
        self.assertTrue(drv.acceptance_problems(
            "016-u100", good_record(), {"rc": 0, "report": {"passed": True}},
            [], True, False))

    def test_delivered_changed_fails(self):
        verify = {"rc": 0, "report": {"passed": True},
                  "pre_sha": {"a": "1"}, "post_sha": {"a": "2"}}
        problems = drv.acceptance_problems("016-u100", good_record(), verify, [], True, True)
        self.assertTrue(any("delivered files changed" in p for p in problems))

    def test_verify_report_ok(self):
        self.assertTrue(drv.verify_report_ok({"rc": 0, "report": {"passed": True}}))
        self.assertFalse(drv.verify_report_ok({"rc": 1, "report": {"passed": True}}))
        self.assertFalse(drv.verify_report_ok({"rc": 0, "report": {"passed": False}}))
        self.assertFalse(drv.verify_report_ok({"rc": 0, "report": {"parse_error": "x"}}))
        self.assertFalse(drv.verify_report_ok({"rc": 0, "report": {}}))


class TestRenderContract(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def _attempt(self):
        a = self.dir / "attempt-1"
        (a / "workspace-docs").mkdir(parents=True)
        return a

    def test_016_single_dashboard_passes(self):
        a = self._attempt()
        (a / "workspace-docs/render_landscape").mkdir()
        (a / "workspace-docs/render_landscape/dashboard.png").write_bytes(b"x")
        self.assertEqual(drv.render_contract_problems("016-u100", a), [])

    def test_016_missing_dashboard_fails(self):
        a = self._attempt()
        (a / "workspace-docs/render_landscape").mkdir()
        self.assertTrue(drv.render_contract_problems("016-u100", a))

    def test_016_stray_file_does_not_break_single_gate(self):
        a = self._attempt()
        d = a / "workspace-docs/render_landscape"
        d.mkdir()
        (d / "dashboard.png").write_bytes(b"x")
        (d / "readme.txt").write_bytes(b"y")  # not the dashboard image
        self.assertEqual(drv.render_contract_problems("016-u100", a), [])

    def test_029_single_first_page_passes(self):
        a = self._attempt()
        (a / "workspace-docs/release_final_slide-01.jpg").write_bytes(b"x")
        self.assertEqual(drv.render_contract_problems("029-u5", a), [])

    def test_009_contiguous_matches_pdf(self):
        a = self._attempt()
        d = a / "workspace-docs/rendered_v2"
        d.mkdir()
        for n in range(1, 4):
            (d / f"page-{n}.png").write_bytes(b"x")
        (d / "out.pdf").write_bytes(b"%PDF-1.4\n")  # dummy; pdfinfo is faked
        orig = drv.subprocess.run
        drv.subprocess.run = lambda *args, **kw: type("CP", (), {"stdout": "Pages:           3\n", "returncode": 0})()
        try:
            self.assertEqual(drv.render_contract_problems("009-u500", a), [])
        finally:
            drv.subprocess.run = orig

    def test_009_non_contiguous_fails(self):
        a = self._attempt()
        d = a / "workspace-docs/rendered_v2"
        d.mkdir()
        (d / "page-1.png").write_bytes(b"x")
        (d / "page-3.png").write_bytes(b"x")
        self.assertTrue(drv.render_contract_problems("009-u500", a))


class TestVerifySpecReadOnly(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_mounts_and_delivered_hashes(self):
        task = "016-u100"
        attempt = self.dir / "attempt-1"
        res = attempt / "results" / task
        res.mkdir(parents=True)
        sub = res / "round-001" / "submission"
        sub.mkdir(parents=True)
        artifact = sub / "out.xlsx"
        artifact.write_bytes(b"delivered")
        run = {"archive": {"archive_path": f"{task}/round-001/submission/out.xlsx",
                           "sha256": drv.sha_file(artifact), "bytes": artifact.stat().st_size}}
        (res / "round-001/run.json").write_text(json.dumps(run))
        (attempt / "workspace-docs").mkdir()
        verify_dir = self.dir / "verify-dir"
        verify_dir.mkdir()
        create, mounts, delivered, _run = drv.build_verify_spec(task, attempt, verify_dir)
        self.assertEqual(mounts["/repo"]["rw"], False)
        self.assertEqual(mounts["/results"]["rw"], False)
        self.assertEqual(mounts["/render"]["rw"], False)
        self.assertEqual(mounts["/report"]["rw"], True)
        self.assertEqual(len(delivered), 2)  # output + expected


class TestResumePolicy(unittest.TestCase):
    def test_reuse_passed_verify(self):
        st = {"tasks": {"016-u100": make_state_attempt(
            "passed", {"rc": 0, "report": {"passed": True}})}}
        action, _dir = drv.decide_action(st, "016-u100")
        self.assertEqual(action, "reuse")

    def test_reverify_when_verify_failed(self):
        st = {"tasks": {"016-u100": make_state_attempt(
            "passed", {"rc": 1, "report": {"passed": False}})}}
        action, _dir = drv.decide_action(st, "016-u100")
        self.assertEqual(action, "reverify")

    def test_reverify_when_verify_absent(self):
        st = {"tasks": {"016-u100": make_state_attempt("passed", None)}}
        action, _dir = drv.decide_action(st, "016-u100")
        self.assertEqual(action, "reverify")

    def test_run_when_workload_failed(self):
        st = {"tasks": {"016-u100": make_state_attempt("failed", None)}}
        action, _dir = drv.decide_action(st, "016-u100")
        self.assertEqual(action, "run")

    def test_run_when_no_attempt(self):
        action, _dir = drv.decide_action({"tasks": {}}, "016-u100")
        self.assertEqual(action, "run")

    def test_never_rerun_completed_workload(self):
        for verify in (None, {"rc": 1, "report": {"passed": False}}):
            st = {"tasks": {"016-u100": make_state_attempt("passed", verify)}}
            action, _dir = drv.decide_action(st, "016-u100")
            self.assertIn(action, ("reuse", "reverify"))
            self.assertNotEqual(action, "run")


class TestIndex(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def _make_campaign(self):
        camp = self.dir / "campaign"
        camp.mkdir()
        (camp / "evidence.txt").write_text("data")
        (camp / "sub").mkdir()
        (camp / "sub/attempt-record.json").write_text('{"a": 1}')
        return camp

    def test_fresh_index_passes_and_no_drift(self):
        camp = self._make_campaign()
        state = {"status": "running"}
        drv.index_campaign(camp, state)
        ver = json.loads((camp / "campaign.index-verification.json").read_text())
        self.assertEqual(ver["status"], "passed")
        self.assertEqual(ver["files_checked"], 2)
        idx1 = (camp / "campaign.sha256-index.json").read_bytes()
        # campaign.json and the index itself are excluded from the index
        files = json.loads((camp / "campaign.sha256-index.json").read_text())["files"]
        self.assertNotIn("campaign.json", files)
        self.assertNotIn("campaign.sha256-index.json", files)
        self.assertNotIn("campaign.index-verification.json", files)
        # repeat finalize -> identical index (no drift)
        drv.index_campaign(camp, state)
        self.assertEqual((camp / "campaign.sha256-index.json").read_bytes(), idx1)

    def test_tampered_file_detected(self):
        camp = self._make_campaign()
        drv.index_campaign(camp, {"status": "running"})
        (camp / "evidence.txt").write_text("tampered")
        ok, failures = drv.verify_existing_index(camp)
        self.assertFalse(ok)
        self.assertTrue(any("evidence.txt" in f for f in failures))

    def test_index_failure_recorded(self):
        camp = self._make_campaign()
        (camp / "evidence.txt").write_text("data")
        drv.index_campaign(camp, {"status": "running"})
        (camp / "sub/attempt-record.json").write_text('{"tampered": true}')
        state = {"status": "running"}
        # A fresh finalize over the tampered tree would hash the tampered file
        # and pass, which is why verification re-reads the ORIGINAL index.
        ok, failures = drv.verify_existing_index(camp)
        self.assertFalse(ok)
        (camp / "campaign.index-verification.json").write_text(json.dumps(
            {"status": "failed", "failures": failures}) + "\n")
        self.assertIn("failed", (camp / "campaign.index-verification.json").read_text())



class TestMainFlow(unittest.TestCase):
    """Real main()/resume wiring under mocks (no docker, no workload).

    Covers the F5-main frozen gate and the F7-main reuse gate end to end,
    asserting return codes, persisted campaign/task state, required checks
    being called, workload call counts and that old evidence is untouched."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.workload_calls = []
        self.verify_calls = []
        self.bind_calls = []
        self._orig = (drv.run_task, drv.post_verify, drv.verify_existing_index)
        drv.run_task = self._run_task
        drv.post_verify = self._post_verify

    def tearDown(self):
        drv.run_task, drv.post_verify, drv.verify_existing_index = self._orig

    def _run_task(self, task, image_id, campaign_dir):
        self.workload_calls.append(task)
        return Path(campaign_dir) / task / "mock-attempt", {
            "status": "passed", "loops": 1, "image_id": image_id,
            "summary": {"requested": 1, "completed": 1, "successes": 1, "failures": 0},
            "steps": [{"id": "01", "status": "ok", "rc": 0}],
            "round_id": "round-001", "output": {"archive_path": "x", "sha256": "x"},
        }

    def _post_verify(self, task, attempt_dir, campaign_dir):
        self.verify_calls.append(task)
        return {"rc": 0, "report": {"passed": True}, "pre_sha": {"a": "1"},
                "post_sha": {"a": "1"}, "mounts": [], "delivered_unchanged": True}

    def _attempt(self, task, camp, *, archive=True, verify=True, render=True,
                 recipe_ok=True, expected_ok=True, input_ok=True, image_ok=True,
                 hash_ok=True):
        ad = camp / task / f"attempt-{uuid.uuid4().hex[:8]}"
        if archive:
            res = ad / "results" / task
            res.mkdir(parents=True)
            sub = res / "round-001" / "submission"
            sub.mkdir(parents=True)
            artifact = sub / "out.xlsx"
            artifact.write_bytes(b"EVIDENCE")
            sha_v = drv.sha(artifact) if hash_ok else "deadbeef"
            recipe_sha = drv.sha(drv.PAYLOAD / f"tasks/{task}/recipe.json") if recipe_ok else "wrong-recipe"
            run = {
                "status": "completed", "successes": 1, "failures": [], "completed": True,
                "steps": [{"id": "01", "status": "ok", "rc": 0}],
                "recipe_sha256": recipe_sha,
                "archive": {"archive_path": f"{task}/round-001/submission/out.xlsx",
                            "bytes": artifact.stat().st_size, "sha256": sha_v},
            }
            if expected_ok is not None:
                run["expected_sha256"] = drv.sha(
                    drv.PAYLOAD / f"tasks/{task}/seed/root/tmp/docs/expected.json")
            if not expected_ok:
                run["expected_sha256"] = "wrong-expected"
            (res / "round-001" / "run.json").write_text(json.dumps(run))
            input_sha = drv.recipe_input_sha(task) if input_ok else "wrong-input"
            image_id = drv.EXPECTED_IMAGE_ID if image_ok else "wrong-image"
            (ad / "attempt-record.json").write_text(json.dumps(
                {"image_id": image_id, "input_sha256": input_sha, "status": "passed"}))
        (ad / "workspace-docs").mkdir(parents=True)
        if render:
            (ad / "workspace-docs/render_landscape").mkdir(exist_ok=True)
            (ad / "workspace-docs/render_landscape/dashboard.png").write_bytes(b"d")
        verify_val = None if not verify else {
            "rc": 0, "report": {"passed": True}, "pre_sha": {"a": "1"}, "post_sha": {"a": "1"}}
        record = {"status": "passed", "loops": 1,
                  "summary": {"requested": 1, "completed": 1, "successes": 1, "failures": 0},
                  "steps": [{"id": "01", "status": "ok", "rc": 0}],
                  "round_id": "round-001",
                  "output": {"archive_path": f"{task}/round-001/submission/out.xlsx", "sha256": "x"}}
        return ad, {"dir": str(ad), "workload": "passed", "record": record, "verify": verify_val}

    def _state(self, camp, task, attempt, frozen_before=None):
        state = {"schema": "docops-reviewed-functional-v1", "status": "running",
                 "preflight": {"status": "passed",
                               "frozen_before": frozen_before if frozen_before is not None
                               else drv.frozen_snapshot()},
                 "tasks": {task: {"attempts": [attempt]}},
                 "selected_tasks": [task], "resume_count": 1}
        drv.write(camp / "campaign.json", state)
        return camp, state

    def _run(self, camp):
        return drv.main(["--campaign-dir", str(camp), "--resume"])

    def test_frozen_changed_rejected(self):
        camp = Path(self.base) / "c1"
        camp.mkdir()
        ad, attempt = self._attempt("016-u100", camp)
        fake = {k: "old" for k in drv.FROZEN_KEYS}
        self._state(camp, "016-u100", attempt, frozen_before=fake)
        rc = self._run(camp)
        self.assertNotEqual(rc, 0)
        d = json.loads((camp / "campaign.json").read_text())
        self.assertEqual(d["status"], "failed")
        self.assertTrue(d.get("frozen_problems"))
        self.assertEqual(self.workload_calls, [])
        self.assertEqual(self.verify_calls, [])

    def test_frozen_baseline_missing_rejected(self):
        camp = Path(self.base) / "c2"
        camp.mkdir()
        ad, attempt = self._attempt("016-u100", camp)
        state = {"schema": "docops-reviewed-functional-v1", "status": "running",
                 "preflight": {"status": "passed"},  # no frozen_before
                 "tasks": {"016-u100": {"attempts": [attempt]}}}
        drv.write(camp / "campaign.json", state)
        rc = self._run(camp)
        self.assertNotEqual(rc, 0)
        d = json.loads((camp / "campaign.json").read_text())
        self.assertEqual(d["status"], "failed")
        self.assertTrue(any("baseline" in p for p in d.get("frozen_problems", [])))

    def test_frozen_compute_exception_rejected(self):
        camp = Path(self.base) / "c3"
        camp.mkdir()
        ad, attempt = self._attempt("016-u100", camp)
        self._state(camp, "016-u100", attempt)
        orig_tree = drv.tree_sha
        drv.tree_sha = lambda root: (_ for _ in ()).throw(RuntimeError("boom"))
        try:
            rc = self._run(camp)
        finally:
            drv.tree_sha = orig_tree
        self.assertNotEqual(rc, 0)
        d = json.loads((camp / "campaign.json").read_text())
        self.assertTrue(any("compute failed" in p for p in d.get("frozen_problems", [])))

    def test_reuse_archive_missing_rejected(self):
        camp = Path(self.base) / "c4"
        camp.mkdir()
        ad, attempt = self._attempt("016-u100", camp, archive=False)
        self._state(camp, "016-u100", attempt)
        calls = []
        orig = drv.attempt_archive_problems
        drv.attempt_archive_problems = lambda t, a: calls.append(t) or orig(t, a)
        try:
            rc = self._run(camp)
        finally:
            drv.attempt_archive_problems = orig
        self.assertNotEqual(rc, 0)
        d = json.loads((camp / "campaign.json").read_text())
        self.assertEqual(d["status"], "failed")
        self.assertTrue(any("reuse blocked" in p and "archive" in p
                            for p in d.get("task_failure", {}).get("016-u100", [])))
        self.assertEqual(self.workload_calls, [])
        self.assertGreater(len(calls), 0)  # archive bindings actually checked

    def test_reuse_hash_mismatch_rejected(self):
        camp = Path(self.base) / "c5"
        camp.mkdir()
        ad, attempt = self._attempt("016-u100", camp, hash_ok=False)
        self._state(camp, "016-u100", attempt)
        rc = self._run(camp)
        self.assertNotEqual(rc, 0)
        d = json.loads((camp / "campaign.json").read_text())
        self.assertTrue(any("sha mismatch" in p for p in d.get("task_failure", {}).get("016-u100", [])))

    def test_reuse_identity_mismatch_rejected(self):
        for label, kw in [("recipe", dict(recipe_ok=False)), ("expected", dict(expected_ok=False)),
                          ("input", dict(input_ok=False)), ("image", dict(image_ok=False))]:
            with self.subTest(label=label):
                camp = Path(self.base) / f"c6-{label}"
                camp.mkdir()
                ad, attempt = self._attempt("016-u100", camp, **kw)
                self._state(camp, "016-u100", attempt)
                rc = self._run(camp)
                self.assertNotEqual(rc, 0)
                d = json.loads((camp / "campaign.json").read_text())
                probs = d.get("task_failure", {}).get("016-u100", [])
                self.assertTrue(any("mismatch" in p for p in probs), probs)

    def test_reuse_verify_missing_enters_reverify(self):
        camp = Path(self.base) / "c7"
        camp.mkdir()
        ad, attempt = self._attempt("016-u100", camp, verify=False)
        self._state(camp, "016-u100", attempt)
        rc = self._run(camp)
        self.assertEqual(rc, 0)
        self.assertEqual(self.verify_calls, ["016-u100"])
        self.assertEqual(self.workload_calls, [])

    def test_reuse_render_missing_fails_after_reverify(self):
        # Missing render evidence cannot be fixed by an offline re-check; the
        # task is re-verified (workload not rerun) then rejected.
        camp = Path(self.base) / "c8"
        camp.mkdir()
        ad, attempt = self._attempt("016-u100", camp, verify=True, render=False)
        self._state(camp, "016-u100", attempt)
        rc = self._run(camp)
        self.assertNotEqual(rc, 0)
        self.assertEqual(self.verify_calls, ["016-u100"])
        self.assertEqual(self.workload_calls, [])
        d = json.loads((camp / "campaign.json").read_text())
        self.assertTrue(any("render" in p for p in d.get("task_failure", {}).get("016-u100", [])))

    def test_reuse_index_tampered_rejected(self):
        camp = Path(self.base) / "c9"
        camp.mkdir()
        ad, attempt = self._attempt("016-u100", camp)
        self._state(camp, "016-u100", attempt)
        drv.verify_existing_index = lambda c: (False, ["evidence.txt"])
        rc = self._run(camp)
        self.assertNotEqual(rc, 0)
        d = json.loads((camp / "campaign.json").read_text())
        self.assertTrue(any("index" in p for p in d.get("task_failure", {}).get("016-u100", [])))

    def test_reuse_normal_pass_and_no_rerun(self):
        camp = Path(self.base) / "c10"
        camp.mkdir()
        ad, attempt = self._attempt("016-u100", camp)
        self._state(camp, "016-u100", attempt)
        drv.verify_existing_index = lambda c: (True, [])
        orig_bind = drv.bindings_ok
        drv.bindings_ok = lambda t, a: self.bind_calls.append(t) or orig_bind(t, a)
        try:
            rc = self._run(camp)
        finally:
            drv.bindings_ok = orig_bind
        self.assertEqual(rc, 0)
        d = json.loads((camp / "campaign.json").read_text())
        self.assertEqual(d["status"], "passed")
        self.assertTrue(d["tasks"]["016-u100"]["accepted"])
        self.assertEqual(self.workload_calls, [])
        self.assertEqual(self.verify_calls, [])
        self.assertEqual(self.bind_calls, ["016-u100"])
        # old evidence untouched
        art = list((ad / "results").rglob("out.xlsx"))[0]
        self.assertEqual(art.read_bytes(), b"EVIDENCE")

    def test_reject_paths_never_rerun_or_delete(self):
        camp = Path(self.base) / "c11"
        camp.mkdir()
        ad, attempt = self._attempt("016-u100", camp, archive=False)
        self._state(camp, "016-u100", attempt)
        before = {p.name: p.read_bytes() for p in ad.rglob("*") if p.is_file()}
        rc = self._run(camp)
        self.assertNotEqual(rc, 0)
        self.assertEqual(self.workload_calls, [])
        after = {p.name: p.read_bytes() for p in ad.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

if __name__ == "__main__":
    unittest.main()
