"""Small synthetic fixtures for the public replay entry. Never runs a real
DocOps workload command; workload steps are micro `echo`/`python` fixtures run
under a writable DOC_REPLAY_ROOT so /root is never touched on the host."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("docops_replay", ROOT / "docops/replay.py")
replay = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(replay)


def sha(data):
    return hashlib.sha256(data).hexdigest()


class ReplayFixtureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.replay_root = self.root / "fsroot"
        self.replay_root.mkdir()
        self.results = self.root / "results"
        self.payload = self.root / "payload"
        self.make_payload()

    # -- payload construction -------------------------------------------------
    def recipe(self, task, out_rel, steps, scripts):
        files = []
        for name, body in scripts.items():
            dest = f"/root/tmp/docs{task}/{name}"
            rel = f"tasks/{task}/seed/root/tmp/docs{task}/{name}"
            self.write(rel, body)
            files.append({"kind": "script", "payload": rel, "destination": dest,
                          "sha256": sha(body.encode())})
        for i, st in enumerate(steps, 1):
            body = st["argv"][2]
            rel = f"tasks/{task}/commands/{i:02d}.sh"
            self.write(rel, body)
            st["shell_body"] = rel
            st["shell_sha256"] = sha(body.encode())
            st["source_item_id"] = f"call_{task}_{i}"
        recipe = {
            "schema": "docops-final-effective-recipe-v1", "task": task,
            "task_id": f"fixture_{task}", "format": "pdf", "source_run_id": f"run-{task}",
            "historical_score": {"status": "valid", "reward": 0, "detail": "consumed",
                                 "tests_failed": 1, "tests_error": 0, "source_summary": None,
                                 "ctrf": None, "ctrf_counts": None, "raw_reward": None,
                                 "raw_evidence": "fixture"},
            "output_path": f"/root/tmp/docs{task}/{out_rel}", "files": files,
            "steps": steps, "review": "synthetic fixture", "excluded_items": [],
            "provenance": {"trace": None, "trace_sha256": None, "run_env": None,
                           "run_env_sha256": None},
        }
        rel = f"tasks/{task}/recipe.json"
        self.write(rel, json.dumps(recipe))
        self.rebuild_index()
        return recipe

    def write(self, rel, data):
        path = self.payload / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data if isinstance(data, bytes) else data.encode())

    def rebuild_index(self):
        """Recompute payload-index.json after a recipe/task file changes."""
        index = {}
        for p in self.payload.rglob("*"):
            if p.is_file() and p.name != "payload-index.json":
                index[str(p.relative_to(self.payload))] = {
                    "bytes": p.stat().st_size, "sha256": sha(p.read_bytes())}
        self.write("payload-index.json", json.dumps({"schema": "docops-payload-index-v1",
                                                     "files": index}))

    def make_payload(self):
        # Task A: workflow step writes out.txt in cwd; script build.py -> BUILD_A
        self.recipe("A", "out.txt",
                    [{"id": "01", "name": "build", "phase": "workflow", "cwd": "/root/tmp/docsA",
                      "argv": ["/bin/bash", "-c", "python3 build.py > out.txt"]}],
                    {"build.py": "print('BUILD_A')\n"})
        # Task B: same-named build.py with different body -> BUILD_B, plus a leak check
        self.recipe("B", "out.txt",
                    [{"id": "01", "name": "build", "phase": "workflow", "cwd": "/root/tmp/docsB",
                      "argv": ["/bin/bash", "-c", "python3 build.py > out.txt && cp out.txt leakcheck.txt"]}],
                    {"build.py": "print('BUILD_B')\n"})
        # Task C: environment_setup step (out of ROI) + workflow step
        self.recipe("C", "out.txt",
                    [{"id": "01", "name": "prep_fonts", "phase": "environment_setup",
                      "cwd": "/root/tmp/docsC", "argv": ["/bin/bash", "-c", "echo PREP > prep.txt"]},
                     {"id": "02", "name": "build", "phase": "workflow", "cwd": "/root/tmp/docsC",
                      "argv": ["/bin/bash", "-c", "python3 build.py > out.txt"]}],
                    {"build.py": "print('BUILD_C')\n"})
        # catalog + index
        catalog = {"schema": "docops-final-effective-payload-v1",
                   "status": "source_reviewed_pending_replay_validation",
                   "scope": "final_effective_execution",
                   "tasks": [{"task": t, "recipe": f"tasks/{t}/recipe.json",
                              "steps": 1, "scripts": 1, "historical_reward": 0}
                             for t in ("A", "B", "C")]}
        self.write("catalog.json", json.dumps(catalog))
        index = {}
        for p in self.payload.rglob("*"):
            if p.is_file() and p.name != "payload-index.json":
                index[str(p.relative_to(self.payload))] = {
                    "bytes": p.stat().st_size, "sha256": sha(p.read_bytes())}
        self.write("payload-index.json", json.dumps({"schema": "docops-payload-index-v1",
                                                     "files": index}))

    # -- helpers ----------------------------------------------------------------
    def run_replay(self, *argv):
        env = dict(os.environ)
        env["DOC_REPLAY_ROOT"] = str(self.replay_root)
        return subprocess.run([sys.executable, "-B", str(ROOT / "docops/replay.py"), *argv],
                              capture_output=True, text=True, env=env, timeout=120)

    def run_task(self, task, loops=1, extra=None):
        argv = ["run", "--payload", str(self.payload), "--workdir", str(self.root / "work"),
                "--results-dir", str(self.results), "--task", task, "--loops", str(loops),
                "--no-lock"] + (extra or [])
        return self.run_replay(*argv)

    def read_round(self, task, round_seq=1):
        path = self.results / task / f"round-{round_seq:03d}" / "run.json"
        return json.loads(path.read_text())

    def marker(self, task, name):
        p = self.replay_root / f"root/tmp/docs{task}" / name
        return p.read_text() if p.exists() else None

    # -- tests ------------------------------------------------------------------
    def test_help_list_validate_only_do_not_execute_workload(self):
        for argv in (["list", "--payload", str(self.payload)],
                     ["validate-only", "--payload", str(self.payload), "--workdir", str(self.root / "work")],
                     ["--help"]):
            cp = self.run_replay(*argv)
            self.assertEqual(cp.returncode, 0, cp.stderr[-300:])
        for task in ("A", "B", "C"):
            self.assertIsNone(self.marker(task, "out.txt"), f"workload executed in {argv}")

    def test_list_reports_twelve_task_identity_and_format(self):
        cp = self.run_replay("list", "--payload", str(self.payload))
        data = json.loads(cp.stdout)
        self.assertEqual({t["task"] for t in data["tasks"]}, {"A", "B", "C"})
        self.assertTrue(all(t["format"] for t in data["tasks"]))

    def test_missing_material_rejected_before_execution(self):
        (self.payload / "tasks/A/seed/root/tmp/docsA/build.py").unlink()
        (self.payload / "payload-index.json").unlink()
        self.make_payload()
        (self.payload / "tasks/A/seed/root/tmp/docsA/build.py").unlink()
        cp = self.run_replay("validate-only", "--payload", str(self.payload),
                             "--workdir", str(self.root / "work"))
        self.assertNotEqual(cp.returncode, 0)
        cp2 = self.run_task("A")
        self.assertNotEqual(cp2.returncode, 0)
        self.assertIn("refusing", (cp2.stderr or cp2.stdout))

    def test_tampered_material_rejected_before_execution(self):
        (self.payload / "tasks/B/seed/root/tmp/docsB/build.py").write_text("print('TAMPERED')\n")
        cp = self.run_replay("validate-only", "--payload", str(self.payload),
                             "--workdir", str(self.root / "work"))
        self.assertNotEqual(cp.returncode, 0)
        cp2 = self.run_task("B")
        self.assertNotEqual(cp2.returncode, 0)

    def test_command_cwd_and_same_name_script_isolation(self):
        cp = self.run_task("A")
        self.assertEqual(cp.returncode, 0, cp.stderr[-300:])
        state = self.read_round("A")
        self.assertEqual(state["roi_steps"][0]["rc"], 0)
        self.assertEqual(self.marker("A", "out.txt").strip(), "BUILD_A")
        # placed script is the frozen A body, not B's same-named script
        self.assertEqual((self.replay_root / "root/tmp/docsA/build.py").read_text().strip(),
                         "print('BUILD_A')")

    def test_sequential_tasks_no_state_leak(self):
        for task in ("A", "B"):
            cp = self.run_task(task)
            self.assertEqual(cp.returncode, 0, cp.stderr[-300:])
        self.assertEqual(self.marker("B", "out.txt").strip(), "BUILD_B")
        self.assertEqual(self.marker("B", "leakcheck.txt").strip(), "BUILD_B")
        self.assertEqual((self.replay_root / "root/tmp/docsB/build.py").read_text().strip(),
                         "print('BUILD_B')")

    def test_roi_excludes_prepare_and_archive(self):
        cp = self.run_task("C")
        self.assertEqual(cp.returncode, 0, cp.stderr[-300:])
        state = self.read_round("C")
        self.assertEqual([s["name"] for s in state["roi_steps"]], ["build"])
        self.assertEqual(len(state["prepare"]["font_env"]), 1)  # environment_setup is out of ROI
        self.assertIn("archive", state)
        self.assertEqual(state["status"], "completed")

    def test_loops_and_step_failure_recorded(self):
        # inject a failing step into task A's recipe and re-index
        self.recipe("A", "out.txt",
                    [{"id": "01", "name": "build", "phase": "workflow", "cwd": "/root/tmp/docsA",
                      "argv": ["/bin/bash", "-c", "false"]}],
                    {"build.py": "print('BUILD_A')\n"})
        cp = self.run_task("A", loops=2)
        self.assertNotEqual(cp.returncode, 0)
        state = self.read_round("A", 1)
        self.assertEqual(state["roi_steps"][0]["rc"], 1)
        self.assertEqual(state["roi_steps"][0]["status"], "failed")
        self.assertEqual(state["status"], "failed")
        self.assertFalse((self.results / 'A/round-002').exists())
        summary = json.loads((self.results / "A" / "summary.json").read_text())
        self.assertEqual(summary["requested"], 1)
        self.assertEqual(summary["failures"], 1)

    def test_step_timeout_recorded(self):
        self.recipe("A", "out.txt",
                    [{"id": "01", "name": "slow", "phase": "workflow", "cwd": "/root/tmp/docsA",
                      "argv": ["/bin/bash", "-c", "sleep 5"]}],
                    {"build.py": "print('BUILD_A')\n"})
        cp = self.run_task("A", extra=["--step-timeout", "1"])
        self.assertNotEqual(cp.returncode, 0)
        state = self.read_round("A")
        self.assertEqual(state["roi_steps"][0]["status"], "timeout")
        self.assertIn("timeout", state["failures"][0]["status"])

    def test_archive_missing_output_recorded_not_hidden(self):
        self.recipe("A", "never_written.txt",
                    [{"id": "01", "name": "build", "phase": "workflow", "cwd": "/root/tmp/docsA",
                      "argv": ["/bin/bash", "-c", "python3 build.py > other.txt"]}],
                    {"build.py": "print('BUILD_A')\n"})
        cp = self.run_task("A")
        self.assertNotEqual(cp.returncode, 0)
        state = self.read_round("A")
        self.assertEqual(state["archive"]["status"], "missing_output")
        self.assertEqual(state["successes"], 0)

    def test_workspace_reset_does_not_delete_results(self):
        self.run_task("A")
        archive = self.results / "A" / "round-001" / "submission" / "out.txt"
        self.assertTrue(archive.is_file())
        # a later round resets the workspace but must keep results
        self.run_task("A", loops=2)
        self.assertTrue(archive.is_file())
        self.assertTrue((self.results / "A" / "round-002" / "submission" / "out.txt").is_file())

    def test_concurrent_lock_rejected(self):
        work = self.root / "work"
        with mock.patch.dict(os.environ, {'DOC_REPLAY_ROOT': str(self.replay_root)}):
            lock1 = replay.WorkLock(work)
            lock2 = replay.WorkLock(self.root / 'different-workdir')
        self.assertTrue(lock1.acquire())
        self.assertFalse(lock2.acquire())
        lock1.release()
        self.assertTrue(lock2.acquire())
        lock2.release()

    def test_payload_usable_without_source_repository(self):
        isolated = self.root / "isolated"
        shutil.copytree(self.payload, isolated)
        # simulate removal of the "source" side of this test (there is none here;
        # validate-only must not depend on agent_workload_characterization)
        cp = self.run_replay("validate-only", "--payload", str(isolated),
                             "--workdir", str(self.root / "work"))
        self.assertEqual(cp.returncode, 0, cp.stderr[-300:])
        data = json.loads(cp.stdout)
        self.assertEqual(data["payload"]["tasks"], 3)
        self.assertFalse(data["payload"]["replay_validated"])
        self.assertFalse(data["workload_executed"])

    def test_failed_round_not_masked_by_later_success(self):
        self.recipe("A", "out.txt",
                    [{"id": "01", "name": "build", "phase": "workflow", "cwd": "/root/tmp/docsA",
                      "argv": ["/bin/bash", "-c", "false"]}],
                    {"build.py": "print('BUILD_A')\n"})
        self.run_task("A", loops=1)
        # restore a working recipe for a later round on the same task
        self.recipe("A", "out.txt",
                    [{"id": "01", "name": "build", "phase": "workflow", "cwd": "/root/tmp/docsA",
                      "argv": ["/bin/bash", "-c", "python3 build.py > out.txt"]}],
                    {"build.py": "print('BUILD_A')\n"})
        self.run_task("A", loops=2)
        summary = json.loads((self.results / "A" / "summary.json").read_text())
        # round 1 (failing recipe) + rounds 1,2 (working recipe) = 3 requested
        self.assertEqual(summary["requested"], 3)
        self.assertEqual(summary["failures"], 1)
        self.assertEqual(summary["successes"], 2)
        first = self.read_round("A", 1)
        self.assertEqual(first["roi_steps"][0]["rc"], 1)  # not overwritten

    def test_real_recipe_root_inputs_do_not_delete_skills_or_other_files(self):
        recipe = json.loads((ROOT / 'docops/payload/tasks/031/recipe.json').read_text())
        sentinel = self.replay_root / 'root/.codex/skills/pdf/SKILL.md'
        sentinel.parent.mkdir(parents=True)
        sentinel.write_text('must survive')
        unrelated = self.replay_root / 'root/other-task.txt'
        unrelated.write_text('keep')
        with mock.patch.dict(os.environ, {'DOC_REPLAY_ROOT': str(self.replay_root)}):
            self.assertNotIn('/root', replay.task_scoped_paths(recipe))
            replay.reset_workspace(recipe)
        self.assertEqual(sentinel.read_text(), 'must survive')
        self.assertEqual(unrelated.read_text(), 'keep')

    def test_failed_preparation_stops_workflow_and_returns_failure(self):
        self.recipe('C', 'out.txt', [
            {'id': '01', 'name': 'prep', 'phase': 'environment_setup', 'cwd': '/root/tmp/docsC',
             'argv': ['/bin/bash', '-c', 'false']},
            {'id': '02', 'name': 'must_not_run', 'phase': 'workflow', 'cwd': '/root/tmp/docsC',
             'argv': ['/bin/bash', '-c', 'python3 build.py > out.txt']}], {'build.py': 'print("bad")'})
        cp = self.run_task('C')
        self.assertNotEqual(cp.returncode, 0)
        state = self.read_round('C')
        self.assertEqual(state['successes'], 0)
        self.assertEqual(state['roi_steps'], [])
        self.assertEqual(state['prepare']['status'], 'failed')
        self.assertIsNone(self.marker('C', 'out.txt'))

    def test_fonts_and_profile_restored_exactly_after_failed_round(self):
        fonts = self.replay_root / 'root/.local/share/fonts'
        fonts.mkdir(parents=True)
        (fonts / 'Aptos-regular.ttf').write_text('baseline-font')
        profile = self.replay_root / 'root/.config/libreoffice'
        profile.mkdir(parents=True)
        (profile / 'baseline').write_text('keep-profile')
        command = f'printf changed > {fonts}/Aptos-regular.ttf; printf new > {fonts}/AptosDisplay-bold.ttf'
        self.recipe('C', 'out.txt', [
            {'id': '01', 'name': 'font_prep', 'phase': 'environment_setup', 'cwd': '/root/tmp/docsC',
             'argv': ['/bin/bash', '-c', command]},
            {'id': '02', 'name': 'failure', 'phase': 'workflow', 'cwd': '/root/tmp/docsC',
             'argv': ['/bin/bash', '-c', 'false']}], {'build.py': 'print("unused")'})
        self.assertNotEqual(self.run_task('C').returncode, 0)
        self.assertEqual((fonts / 'Aptos-regular.ttf').read_text(), 'baseline-font')
        self.assertFalse((fonts / 'AptosDisplay-bold.ttf').exists())
        self.assertEqual((profile / 'baseline').read_text(), 'keep-profile')

    def test_timeout_kills_background_descendants(self):
        marker = self.root / 'late-child-output'
        self.recipe('A', 'out.txt', [
            {'id': '01', 'name': 'background', 'phase': 'workflow', 'cwd': '/root/tmp/docsA',
             'argv': ['/bin/bash', '-c', f'(sleep 0.4; touch {marker}) & wait']}],
            {'build.py': 'print("unused")'})
        cp = self.run_task('A', extra=['--step-timeout', '0.05'])
        self.assertNotEqual(cp.returncode, 0)
        time.sleep(0.5)
        self.assertFalse(marker.exists())
        self.assertEqual(self.read_round('A')['roi_steps'][0]['status'], 'timeout')

    def test_results_inside_reset_target_rejected_before_cleanup(self):
        target = self.replay_root / 'root/tmp/docsA'
        target.mkdir(parents=True)
        (target / 'sentinel').write_text('keep')
        cp = self.run_task('A', extra=['--results-dir', str(target / 'results')])
        self.assertNotEqual(cp.returncode, 0)
        self.assertEqual((target / 'sentinel').read_text(), 'keep')

    def test_symlink_cleanup_refused(self):
        outside = self.root / 'outside'
        outside.mkdir()
        (outside / 'sentinel').write_text('keep')
        target = self.replay_root / 'root/tmp/docsA'
        target.parent.mkdir(parents=True)
        target.symlink_to(outside, target_is_directory=True)
        self.assertNotEqual(self.run_task('A').returncode, 0)
        self.assertEqual((outside / 'sentinel').read_text(), 'keep')

    def test_missing_cwd_fails_instead_of_falling_back(self):
        step = {'id': 'x', 'name': 'missing-cwd', 'cwd': '/root/tmp/not-created',
                'phase': 'workflow', 'argv': ['/bin/bash', '-c', 'echo should-not-run']}
        state = {'steps': [], 'run_path': str(self.root / 'state.json')}
        with mock.patch.dict(os.environ, {'DOC_REPLAY_ROOT': str(self.replay_root)}):
            result = replay.run_step(step, state, timeout=1)
        self.assertEqual(result['status'], 'failed')
        self.assertIn('cwd is missing', result['detail'])

    def test_archive_exception_is_persisted(self):
        with mock.patch.dict(os.environ, {'DOC_REPLAY_ROOT': str(self.replay_root)}), \
             mock.patch.object(replay, 'archive_output', side_effect=OSError('fixture archive failure')):
            state = replay.run_one_task('A', self.payload, self.root / 'work', self.results,
                                        'round-001', 1, 1, None)
        self.assertEqual(state['status'], 'failed')
        self.assertEqual(self.read_round('A')['archive']['status'], 'failed')

    def test_host_run_is_rejected_without_fixture_root(self):
        env = dict(os.environ)
        env.pop('DOC_REPLAY_ROOT', None)
        cp = subprocess.run([sys.executable, '-B', str(ROOT / 'docops/replay.py'), 'run',
                             '--payload', str(self.payload), '--task', 'A'],
                            env=env, capture_output=True, text=True)
        self.assertNotEqual(cp.returncode, 0)
        self.assertIn('only in the DocOps image', cp.stderr)

    def test_roi_intervals_cover_only_workflow_steps(self):
        self.assertEqual(self.run_task('C').returncode, 0)
        state = self.read_round('C')
        self.assertEqual(state['roi_clock'], 'CLOCK_MONOTONIC')
        self.assertEqual([i['step'] for i in state['roi_intervals']], ['02'])
        interval = state['roi_intervals'][0]
        self.assertLess(interval['start'], interval['end'])
        self.assertIsInstance(interval['pid'], int)

    def test_environment_version_mismatch_is_an_error(self):
        self.assertTrue(any('python' in e for e in replay.environment_errors(
            {'python': {'present': True, 'version': 'wrong'}})))


if __name__ == "__main__":
    unittest.main()
