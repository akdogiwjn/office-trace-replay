"""Static replay-entry integration checks for the synthetic scale payload.

Host-safe: only validate-only / list and micro-fixture replay runs are executed.
No real DocOps workload step is ever run and /root is never touched (all runs use
DOC_REPLAY_ROOT fixtures or validate-only).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REPLAY = ROOT / "docops/replay.py"
SCALING = ROOT / "docops/scaling"
SCALING_PAYLOAD = SCALING / "payload"
OFFICIAL_PAYLOAD = ROOT / "docops/payload"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run_replay(argv, env=None):
    return subprocess.run([sys.executable, "-B", str(REPLAY), *argv],
                          capture_output=True, text=True, env=env or dict(os.environ),
                          timeout=180)


class TestStaticPayloadRecognition(unittest.TestCase):
    def test_scaling_payload_list_and_validate(self):
        cp = run_replay(["list", "--payload", str(SCALING_PAYLOAD)])
        self.assertEqual(cp.returncode, 0, cp.stderr[-500:])
        tasks = {t["task"] for t in json.loads(cp.stdout)["tasks"]}
        self.assertEqual(tasks, {"014-n1000", "014-n10000", "021-g5", "021-g10"})
        cp2 = run_replay(["validate-only", "--payload", str(SCALING_PAYLOAD),
                          "--workdir", str(Path(tempfile.mkdtemp()))])
        self.assertEqual(cp2.returncode, 0, cp2.stderr[-500:])
        payload = json.loads(cp2.stdout)["payload"]
        self.assertEqual(payload["tasks"], 4)
        self.assertTrue(payload["status"] == "static_valid")
        self.assertFalse(payload["replay_validated"])

    def test_official_payload_still_valid_and_kind_official(self):
        cp = run_replay(["validate-only", "--payload", str(OFFICIAL_PAYLOAD),
                         "--workdir", str(Path(tempfile.mkdtemp()))])
        self.assertEqual(cp.returncode, 0, cp.stderr[-500:])
        payload = json.loads(cp.stdout)["payload"]
        self.assertEqual(payload["tasks"], 12)
        catalog = json.loads((OFFICIAL_PAYLOAD / "catalog.json").read_text())
        self.assertEqual(catalog.get("kind", "official"), "official")
        self.assertEqual(len(catalog["tasks"]), 12)

    def test_tampered_scaling_material_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            payload = Path(d) / "payload"
            shutil.copytree(SCALING_PAYLOAD, payload)
            target = payload / "tasks/021-g5/seed/root/tmp/docs/regions.json"
            target.write_bytes(target.read_bytes() + b"tampered")
            cp = run_replay(["validate-only", "--payload", str(payload),
                             "--workdir", str(Path(d) / "work")])
            self.assertNotEqual(cp.returncode, 0)
            cp2 = run_replay(["run", "--payload", str(payload), "--task", "021-g5",
                              "--workdir", str(Path(d) / "work"),
                              "--results-dir", str(Path(d) / "results"), "--no-lock"])
            self.assertEqual(cp2.returncode, 2)

    def test_missing_scaling_input_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            payload = Path(d) / "payload"
            shutil.copytree(SCALING_PAYLOAD, payload)
            (payload / "tasks/014-n10000/seed/root/"
             "docops_v2_l3_014_xlsx_disaster_housing_grant_public_release_input_n10000.xlsx").unlink()
            cp = run_replay(["run", "--payload", str(payload), "--task", "014-n10000",
                             "--workdir", str(Path(d) / "work"),
                             "--results-dir", str(Path(d) / "results"), "--no-lock"])
            self.assertEqual(cp.returncode, 2)
            self.assertIn("refusing to run", cp.stderr)

    def test_recipe_synthetic_declaration(self):
        recipe = json.loads((SCALING_PAYLOAD / "tasks/014-n1000/recipe.json").read_text())
        sv = recipe["synthetic_variant"]
        self.assertTrue(sv["synthetic"])
        self.assertEqual(sv["parent_task"], "014")
        self.assertIn("seed", sv)
        self.assertIn("scale", sv)
        self.assertIn("parent_historical_score", sv)
        self.assertNotIn("historical_score", recipe)  # not inherited as variant score


class ScalingPayloadBuildFixture:
    """Tiny scaling-kind payload with two micro tasks for host-safe replay runs.

    Steps write only relative paths inside the fixture-mapped cwd
    (/root/tmp/docsV<task>), so nothing ever touches the real /root.
    """

    def __init__(self, root: Path):
        self.payload = root / "payload"
        self.replay_root = root / "fsroot"
        self.results = root / "results"
        self.work = root / "work"
        self.replay_root.mkdir()
        for task in ("014-n1000", "014-n10000"):
            self._recipe(task)
        catalog = {"schema": "docops-final-effective-payload-v1", "kind": "scaling",
                   "tasks": [
                       {"task": "014-n1000", "recipe": "tasks/014-n1000/recipe.json",
                        "steps": 1, "scripts": 1, "historical_reward": None},
                       {"task": "014-n10000", "recipe": "tasks/014-n10000/recipe.json",
                        "steps": 1, "scripts": 1, "historical_reward": None},
                   ]}
        self._write("catalog.json", json.dumps(catalog))
        self._rebuild_index()

    def _write(self, rel, data):
        path = self.payload / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data if isinstance(data, bytes) else data.encode())

    def _recipe(self, task):
        work_dir = f"/root/tmp/docsV{task}"
        body = f"import sys\nsys.stdout.write('OUT_{task}')\n"
        script_rel = f"tasks/{task}/seed/root/tmp/docsV{task}/build.py"
        self._write(script_rel, body)
        argv = ["/bin/bash", "-c", "python3 build.py > out.txt"]
        shell_rel = f"tasks/{task}/commands/01.sh"
        self._write(shell_rel, argv[2])
        recipe = {
            "schema": "docops-final-effective-recipe-v1", "task": task,
            "task_id": f"fixture_{task}", "format": "pdf",
            "output_path": f"{work_dir}/out.txt",
            "files": [{"kind": "script", "payload": script_rel,
                       "destination": f"{work_dir}/build.py", "sha256": sha(body.encode())}],
            "steps": [{"id": "01", "name": "build", "phase": "workflow", "cwd": work_dir,
                       "argv": argv, "shell_body": shell_rel,
                       "shell_sha256": sha(argv[2].encode()),
                       "depends_on": []}],
            "review": "fixture", "excluded_items": [],
            "provenance": {"trace": None, "trace_sha256": None, "run_env": None, "run_env_sha256": None},
            "synthetic_variant": {"synthetic": True, "parent_task": task.split("-")[0], "seed": 1},
        }
        self._write(f"tasks/{task}/recipe.json", json.dumps(recipe))

    def _rebuild_index(self):
        index = {}
        for p in self.payload.rglob("*"):
            if p.is_file() and p.name != "payload-index.json":
                index[str(p.relative_to(self.payload))] = {
                    "bytes": p.stat().st_size, "sha256": sha(p.read_bytes())}
        self._write("payload-index.json", json.dumps({"schema": "docops-payload-index-v1",
                                                      "files": index}))

    def run(self, *args):
        env = dict(os.environ)
        env["DOC_REPLAY_ROOT"] = str(self.replay_root)
        return run_replay(["run", "--payload", str(self.payload), "--workdir", str(self.work),
                           "--results-dir", str(self.results), "--no-lock", *args], env=env)


class TestScalingReplayFixtureRun(unittest.TestCase):
    def test_variant_results_paths_are_isolated(self):
        with tempfile.TemporaryDirectory() as d:
            fx = ScalingPayloadBuildFixture(Path(d))
            cp = fx.run("--task", "014-n1000", "--task", "014-n10000", "--loops", "1")
            self.assertEqual(cp.returncode, 0, cp.stderr[-500:] + cp.stdout[-500:])
            r1 = fx.results / "014-n1000" / "round-001"
            r2 = fx.results / "014-n10000" / "round-001"
            self.assertTrue(r1.is_dir() and r2.is_dir())
            self.assertNotEqual(str(r1), str(r2))
            self.assertEqual((fx.replay_root / "root/tmp/docsV014-n1000/out.txt").read_text().strip(),
                             "OUT_014-n1000")
            self.assertEqual((fx.replay_root / "root/tmp/docsV014-n10000/out.txt").read_text().strip(),
                             "OUT_014-n10000")
            # variant B did not leak A's script bytes
            b_script = (fx.replay_root / "root/tmp/docsV014-n10000/build.py").read_text()
            self.assertEqual(b_script, "import sys\nsys.stdout.write('OUT_014-n10000')\n")
            self.assertNotIn("OUT_014-n1000'", b_script)

    def test_original_frozen_materials_hashes_unchanged(self):
        baseline = Path("/tmp/opencode/scaling_baseline_014_021.sha")
        if not baseline.exists():
            self.skipTest("baseline hash file not present")
        lines = baseline.read_text().splitlines()
        self.assertEqual(len(lines), 14)
        for parent, block in (("014", lines[:7]), ("021", lines[7:])):
            for line in block:
                digest, rel = line.split("  ", 1)
                path = OFFICIAL_PAYLOAD / f"tasks/{parent}/seed/root/{rel}"
                self.assertTrue(path.exists(), path)
                self.assertEqual(sha(path.read_bytes()), digest, f"{parent}: {rel}")


class TestEnvironmentPrecheck(unittest.TestCase):
    """Package-kind / task-set precheck in replay.environment_errors."""

    @classmethod
    def setUpClass(cls):
        import importlib.util
        spec = importlib.util.spec_from_file_location("docops_replay", ROOT / "docops/replay.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        cls.replay = mod

    def _errors(self, kind, declared, actual):
        base = {"runtime_profile": "docops-debian-original", "payload_catalog": True,
                "payload_kind": kind, "payload_declared_tasks": declared,
                "payload_tasks": actual}
        return self.replay.environment_errors(base)

    def test_official_twelve_accepted(self):
        declared = actual = [f"{i:03d}" for i in range(1, 13)]
        payload_errors = [e for e in self._errors("official", declared, actual)
                          if "payload" in e or "task" in e]
        self.assertEqual(payload_errors, [])

    def test_unknown_kind_rejected(self):
        errors = self._errors("other", ["a", "b"], ["a", "b"])
        self.assertTrue(any("unsupported payload kind" in e for e in errors))

    def test_official_wrong_count_rejected(self):
        errors = self._errors("official", [f"{i:03d}" for i in range(1, 12)],
                              [f"{i:03d}" for i in range(1, 12)])
        self.assertTrue(any("twelve" in e for e in errors))

    def test_scaling_declared_must_match_dirs(self):
        errors = self._errors("scaling", ["014-n1000", "014-n10000"],
                              ["014-n1000", "014-n10000", "021-g5"])
        self.assertTrue(any("does not match installed" in e for e in errors))

    def test_scaling_duplicate_ids_rejected(self):
        errors = self._errors("scaling", ["a", "a"], ["a"])
        self.assertTrue(any("duplicate task ids" in e for e in errors))

    def test_scaling_empty_declared_rejected(self):
        errors = self._errors("scaling", [], [])
        self.assertTrue(any("non-empty" in e for e in errors))

    def test_scaling_valid_accepted(self):
        declared = actual = ["014-n1000", "014-n10000", "021-g5", "021-g10"]
        payload_errors = [e for e in self._errors("scaling", declared, actual)
                          if "payload" in e or "task" in e]
        self.assertEqual(payload_errors, [])


class TestPrepareSafety(unittest.TestCase):
    """prepare.py output-path protection and sync behaviour (temp dirs only)."""

    @classmethod
    def setUpClass(cls):
        import importlib.util
        sys.path.insert(0, str(SCALING))
        spec = importlib.util.spec_from_file_location("scaling_prepare", SCALING / "prepare.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        cls.prepare = mod

    def _payload_out(self, path):
        return self.prepare.assert_safe_payload_out(Path(path))

    def test_safe_targets_accepted(self):
        self._payload_out(str(SCALING / "payload"))  # default
        tmp = Path(tempfile.mkdtemp()) / "out"
        self.assertEqual(self._payload_out(str(tmp)).name, "out")

    def test_unsafe_targets_rejected(self):
        for path in (ROOT / "docops/payload",        # official payload
                     ROOT,                            # repo root
                     SCALING,                          # source tree
                     SCALING / "staging",             # staging tree
                     ROOT / "docops",                 # docops root (parent of official)
                     ROOT.parent):                    # ancestor of repo root
            with self.assertRaises(ValueError, msg=path):
                self._payload_out(str(path))

    def test_symlink_to_official_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            link = Path(d) / "payload-link"
            link.symlink_to(ROOT / "docops/payload", target_is_directory=True)
            with self.assertRaises(ValueError):
                self._payload_out(str(link))

    def test_build_refuses_existing_target_without_force(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "out"
            out.mkdir()
            with self.assertRaises(ValueError) as ctx:
                self.prepare.cmd_build(self._args_build(str(out)))
            self.assertIn("refusing to overwrite", str(ctx.exception))

    def _args_build(self, payload_out):
        return type("A", (), {"payload_out": Path(payload_out), "variants": ["014-n1000"],
                              "force_replace": False, "skip_static_check": True})()

    def test_sync_preserves_input_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            payload = Path(d) / "payload"
            shutil.copytree(SCALING_PAYLOAD, payload)
            v = "014-n1000"
            rel = ("tasks/014-n1000/seed/root/"
                   "docops_v2_l3_014_xlsx_disaster_housing_grant_public_release_input_n1000.xlsx")
            before = sha((payload / rel).read_bytes())
            self.prepare.cmd_sync(self._args_sync(str(payload), [v]))
            after = sha((payload / rel).read_bytes())
            self.assertEqual(before, after)
            # index and recipe still validate
            result = self.prepare.validate_payload(payload)
            self.assertEqual(result["status"], "static_valid")

    def _args_sync(self, payload_out, variants):
        return type("A", (), {"payload_out": Path(payload_out), "variants": variants,
                              "skip_static_check": False})()

    def test_subset_variants_catalog_only_prepared(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "out"
            recipes = {v: self.prepare.assemble_variant(v, out, out) for v in ("014-n1000",)}
            self.prepare.copy_skills(out)
            (out / "catalog.json").write_text(
                json.dumps(self.prepare.catalog_json(out, ["014-n1000"])))
            self.prepare.build_index(out)
            catalog = json.loads((out / "catalog.json").read_text())
            self.assertEqual([t["task"] for t in catalog["tasks"]], ["014-n1000"])
            self.assertEqual(self.prepare.validate_payload(out)["status"], "static_valid")
            shutil.rmtree(out)


if __name__ == "__main__":
    unittest.main()
