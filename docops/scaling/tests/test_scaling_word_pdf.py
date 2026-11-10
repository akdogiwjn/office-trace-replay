"""Static prepare/replay integration checks for the Word/PDF scale round.

Host/container-safe: builds a tiny scaling payload from the four new variants
(selective generation), validates it, runs validate-only/list through replay.py,
checks tampered/missing materials are rejected, and runs a micro-fixture replay
to prove result-path isolation. No real DocOps workload step is ever executed
and /root is never touched (DOC_REPLAY_ROOT fixtures only).
"""
from __future__ import annotations

import importlib.util
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
OFFICIAL_PAYLOAD = ROOT / "docops/payload"

# Redirect the prepare-time staging tree away from the repository for the whole
# test module (set before any `scaling.prepare` import happens).
sys.path.insert(0, str(ROOT / "docops"))
sys.path.insert(0, str(SCALING))  # so prepare.py's `from cases import common` works
os.environ.setdefault("SCALING_STAGING",
                      str(Path(tempfile.gettempdir()) / "docops-scaling-test-staging"))

WORD_PDF_VARIANTS = ["003-u100", "003-u500", "037-u5", "037-u20"]


def sha(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()


def run_replay(argv, env=None):
    return subprocess.run([sys.executable, "-B", str(REPLAY), *argv],
                          capture_output=True, text=True, env=env or dict(os.environ),
                          timeout=240)


class TestPrepareWordPdfSelective(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import scaling.prepare as _prepare
        cls.prepare = _prepare

    def _build_payload(self, root: Path, variants):
        out = root / "payload"
        recipes = {v: self.prepare.assemble_variant(v, out, out) for v in variants}
        self.prepare.copy_skills(out)
        (out / "catalog.json").write_text(
            json.dumps(self.prepare.catalog_json(out, variants), ensure_ascii=False))
        self.prepare.build_index(out)
        return out, recipes

    def test_selective_generation_only_declared_variants(self):
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, SCALING_STAGING=str(Path(d) / "staging"))
            sys.path.insert(0, str(SCALING))
            spec = importlib.util.spec_from_file_location("scaling_prepare_wp", SCALING / "prepare.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            try:
                out, recipes = self._build_payload(Path(d), WORD_PDF_VARIANTS)
                catalog = json.loads((out / "catalog.json").read_text())
                self.assertEqual([t["task"] for t in catalog["tasks"]], WORD_PDF_VARIANTS)
                self.assertEqual(mod.validate_payload(out)["status"], "static_valid")
                # default VARIANT_ORDER is untouched
                self.assertEqual(mod.common.VARIANT_ORDER,
                                 ["014-n1000", "014-n10000", "021-g5", "021-g10"])
            finally:
                sys.path.remove(str(SCALING))

    def test_payload_declares_synthetic_provenance(self):
        with tempfile.TemporaryDirectory() as d:
            out, _ = self._build_payload(Path(d), ["003-u100", "037-u5"])
            recipe = json.loads((out / "tasks/003-u100/recipe.json").read_text())
            sv = recipe["synthetic_variant"]
            self.assertTrue(sv["synthetic"])
            self.assertEqual(sv["parent_task"], "003")
            self.assertNotIn("historical_score", recipe)
            recipe2 = json.loads((out / "tasks/037-u5/recipe.json").read_text())
            self.assertEqual(recipe2["synthetic_variant"]["parent_task"], "037")


class TestWordPdfPayloadReplay(unittest.TestCase):
    def _build_payload_copy(self, root: Path):
        out = root / "payload"
        import scaling.prepare as _prepare
        recipes = {v: _prepare.assemble_variant(v, out, out) for v in WORD_PDF_VARIANTS}
        _prepare.copy_skills(out)
        (out / "catalog.json").write_text(
            json.dumps(_prepare.catalog_json(out, WORD_PDF_VARIANTS), ensure_ascii=False))
        _prepare.build_index(out)
        return out

    def test_list_and_validate_only(self):
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, SCALING_STAGING=str(Path(d) / "staging"))
            sys.path.insert(0, str(SCALING))
            try:
                payload = self._build_payload_copy(Path(d))
                cp = run_replay(["list", "--payload", str(payload)], env=env)
                self.assertEqual(cp.returncode, 0, cp.stderr[-500:])
                tasks = {t["task"] for t in json.loads(cp.stdout)["tasks"]}
                self.assertEqual(tasks, set(WORD_PDF_VARIANTS))
                cp2 = run_replay(["validate-only", "--payload", str(payload),
                                  "--workdir", str(Path(d) / "work")], env=env)
                self.assertEqual(cp2.returncode, 0, cp2.stderr[-500:])
                result = json.loads(cp2.stdout)["payload"]
                self.assertEqual(result["status"], "static_valid")
                self.assertEqual(result["tasks"], 4)
            finally:
                sys.path.remove(str(SCALING))

    def test_tampered_or_missing_material_rejected(self):
        for variant, rel in [
            ("003-u100", "tasks/003-u100/seed/root/tmp/docs/units.json"),
            ("037-u5", "tasks/037-u5/seed/root/tmp/docs/notices.json"),
        ]:
            with tempfile.TemporaryDirectory() as d:
                env = dict(os.environ, SCALING_STAGING=str(Path(d) / "staging"))
                sys.path.insert(0, str(SCALING))
                try:
                    payload = self._build_payload_copy(Path(d))
                    target = payload / rel
                    target.write_bytes(target.read_bytes() + b"tampered")
                    cp = run_replay(["validate-only", "--payload", str(payload),
                                     "--workdir", str(Path(d) / "work")], env=env)
                    self.assertNotEqual(cp.returncode, 0, f"{variant} tamper not caught")
                finally:
                    sys.path.remove(str(SCALING))

        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, SCALING_STAGING=str(Path(d) / "staging"))
            sys.path.insert(0, str(SCALING))
            try:
                payload = self._build_payload_copy(Path(d))
                input_file = next(
                    (payload / "tasks/003-u500/seed/root").glob("*input*.docx"))
                input_file.unlink()
                cp = run_replay(["run", "--payload", str(payload), "--task", "003-u500",
                                 "--workdir", str(Path(d) / "work"),
                                 "--results-dir", str(Path(d) / "results"), "--no-lock"],
                                env=env)
                self.assertEqual(cp.returncode, 2)
                self.assertIn("refusing to run", cp.stderr)
            finally:
                sys.path.remove(str(SCALING))


class WordPdfReplayFixture:
    """Tiny scaling-kind payload with two micro tasks for host-safe replay runs."""

    def __init__(self, root: Path):
        self.payload = root / "payload"
        self.replay_root = root / "fsroot"
        self.results = root / "results"
        self.work = root / "work"
        self.replay_root.mkdir()
        for task in ("003-u100", "037-u5"):
            self._recipe(task)
        catalog = {"schema": "docops-final-effective-payload-v1", "kind": "scaling",
                   "tasks": [
                       {"task": "003-u100", "recipe": "tasks/003-u100/recipe.json",
                        "steps": 1, "scripts": 1, "historical_reward": None},
                       {"task": "037-u5", "recipe": "tasks/037-u5/recipe.json",
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
            "task_id": f"fixture_{task}", "format": "docx",
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


class TestWordPdfReplayFixtureRun(unittest.TestCase):
    def test_variant_result_paths_are_isolated(self):
        with tempfile.TemporaryDirectory() as d:
            fx = WordPdfReplayFixture(Path(d))
            cp = fx.run("--task", "003-u100", "--task", "037-u5", "--loops", "1")
            self.assertEqual(cp.returncode, 0, cp.stderr[-500:] + cp.stdout[-500:])
            r1 = fx.results / "003-u100" / "round-001"
            r2 = fx.results / "037-u5" / "round-001"
            self.assertTrue(r1.is_dir() and r2.is_dir())
            self.assertNotEqual(str(r1), str(r2))
            self.assertEqual((fx.replay_root / "root/tmp/docsV003-u100/out.txt").read_text().strip(),
                             "OUT_003-u100")
            self.assertEqual((fx.replay_root / "root/tmp/docsV037-u5/out.txt").read_text().strip(),
                             "OUT_037-u5")
            # no byte leak between variants
            b_script = (fx.replay_root / "root/tmp/docsV037-u5/build.py").read_text()
            self.assertEqual(b_script, "import sys\nsys.stdout.write('OUT_037-u5')\n")
            self.assertNotIn("OUT_003-u100'", b_script)


class TestWordPdfBaseline(unittest.TestCase):
    """Host-only guard: frozen parent inputs/scripts and new payload inputs
    must stay byte-identical to the recorded baseline. Skipped when the
    baseline file is not present (e.g. inside the replay container)."""

    def test_parent_and_payload_hashes_unchanged(self):
        baseline = Path("/tmp/opencode/scaling_baseline_word_pdf.sha")
        if not baseline.exists():
            self.skipTest("word/pdf baseline hash file not present")
        for line in baseline.read_text().splitlines():
            digest, rel = line.split("  ", 1)
            path = ROOT / rel
            self.assertTrue(path.exists(), path)
            self.assertEqual(sha(path.read_bytes()), digest, rel)


if __name__ == "__main__":
    unittest.main()
