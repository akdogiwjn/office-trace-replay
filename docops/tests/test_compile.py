"""Small synthetic trace tests; never execute an archived workload command."""
import csv
import importlib.util
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('docops_replay_compile', ROOT / 'docops/compile.py')
compiler = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(compiler)


class ReplayCompileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, path, value):
        dest = self.root / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(value) if not isinstance(value, str) else value)
        return dest

    def fixture(self):
        task_input = self.write('task/environment/input.docx', 'input fixture')
        code = 'raise RuntimeError("ARCHIVED WORKLOAD MUST NEVER RUN IN COMPILER")\n'
        script = self.write('evidence/build.py', code)
        dbpath = self.root / 'trace.sqlite'
        with sqlite3.connect(dbpath) as db:
            db.execute('CREATE TABLE thread_items (item_id TEXT,item_type TEXT,created_at_ms INTEGER,item_json TEXT)')
            for ident, kind, timestamp, value in [
                ('edit', 'fileChange', 1, {'changes': []}),
                ('build', 'commandExecution', 2, {'command': "/bin/bash -lc 'python /root/build.py'", 'cwd': '/root', 'exitCode': 0}),
                ('failed', 'commandExecution', 3, {'command': "/bin/bash -c 'false'", 'exitCode': 1}),
                ('view', 'imageView', 4, {}),
            ]:
                db.execute('INSERT INTO thread_items VALUES (?,?,?,?)', (ident, kind, timestamp, json.dumps(value)))
        sample = {'task': 'x', 'task_id': 'fixture', 'format': 'docx', 'run_id': 'run',
                  'score': {'source_summary': 'evidence/score.json', 'reward': 0},
                  'trace': {'sqlite': 'trace.sqlite'},
                  'input': {'path': 'task/environment/input.docx'}, 'instruction': 'task/instruction.md'}
        self.write(compiler.INDEX / 'samples.json', {'samples': [sample]})
        self.write('evidence/run-env.json', {'OUTPUT_PATH': '/root/submission/output.docx',
                   'INPUT_PATH': '/root/input.docx', 'injected_files': [
                       {'path': '/root/input.docx', 'bytes': task_input.stat().st_size,
                        'sha256': compiler.digest(task_input.read_bytes())}]})
        row = {'task': 'x', 'original_path': '/root/build.py', 'version': '1',
               'preserved_path': 'evidence/build.py', 'sha256': compiler.digest(script.read_bytes()),
               'bytes': str(script.stat().st_size), 'source_item_id': 'edit',
               'execution_binding': 'inferred'}
        with (self.root / compiler.INDEX / 'script_versions.csv').open('w') as f:
            writer = csv.DictWriter(f, fieldnames=list(row))
            writer.writeheader()
            writer.writerow(row)
        selection = {'environment': {}, 'measurement_policy': {}, 'tasks': {'x': {
            'scripts': [{'path': '/root/build.py', 'version': 1}],
            'steps': [{'name': 'build', 'source_item_id': 'build', 'phase': 'workflow'}],
            'review': 'fixture'}}}
        self.write(compiler.SELECTION, selection)
        self.stage = self.root / 'payload'
        self.stage.mkdir()
        return selection

    def compile_fixture(self):
        selection = self.fixture()
        compiler.compile_payload(self.root, selection, self.stage)
        return selection

    def test_freezes_without_running_command_and_retains_failure_score(self):
        self.compile_fixture()
        recipe = compiler.load(self.stage / 'tasks/x/recipe.json')
        self.assertEqual(recipe['historical_score']['reward'], 0)
        self.assertEqual(recipe['steps'][0]['argv'], ['/bin/bash', '-lc', 'python /root/build.py'])
        self.assertEqual(compiler.validate_payload(self.stage)['replay_validated'], False)

    def test_selected_failed_command_rejected(self):
        s = self.fixture()
        s['tasks']['x']['steps'][0]['source_item_id'] = 'failed'
        with self.assertRaisesRegex(ValueError, 'successful'):
            compiler.compile_payload(self.root, s, self.stage)

    def test_input_tampering_rejected(self):
        s = self.fixture()
        (self.root / 'task/environment/input.docx').write_text('tampered')
        with self.assertRaisesRegex(ValueError, 'identity mismatch'):
            compiler.compile_payload(self.root, s, self.stage)

    def test_script_tampering_rejected(self):
        s = self.fixture()
        (self.root / 'evidence/build.py').write_text('print("different")')
        with self.assertRaisesRegex(ValueError, 'identity mismatch'):
            compiler.compile_payload(self.root, s, self.stage)

    def test_future_script_revision_cannot_be_associated_with_earlier_execution(self):
        s = self.fixture()
        with sqlite3.connect(self.root / 'trace.sqlite') as db:
            db.execute('UPDATE thread_items SET created_at_ms=9 WHERE item_id="edit"')
        with self.assertRaisesRegex(ValueError, 'not active'):
            compiler.compile_payload(self.root, s, self.stage)

    def test_exclusions_recorded_not_silently_dropped(self):
        self.compile_fixture()
        recipe = compiler.load(self.stage / 'tasks/x/recipe.json')
        self.assertEqual({x['source_item_id'] for x in recipe['excluded_items']}, {'edit', 'failed', 'view'})

    def test_cwd_preserved_for_implicit_converter_destination(self):
        s = self.fixture()
        with sqlite3.connect(self.root / 'trace.sqlite') as db:
            value = json.loads(db.execute('SELECT item_json FROM thread_items WHERE item_id="build"').fetchone()[0])
            value['cwd'] = '/root/tmp/docs'
            db.execute('UPDATE thread_items SET item_json=? WHERE item_id="build"', (json.dumps(value),))
        compiler.compile_payload(self.root, s, self.stage)
        self.assertEqual(compiler.load(self.stage / 'tasks/x/recipe.json')['steps'][0]['cwd'], '/root/tmp/docs')

    def test_payload_tampering_rejected(self):
        self.compile_fixture()
        (self.stage / 'tasks/x/commands/01.sh').write_text('echo changed')
        with self.assertRaisesRegex(ValueError, 'identity mismatch'):
            compiler.validate_payload(self.stage)

    def test_unindexed_file_rejected(self):
        self.compile_fixture()
        (self.stage / 'extra').write_text('unbound')
        with self.assertRaisesRegex(ValueError, 'unexpected'):
            compiler.validate_payload(self.stage)

    def test_frozen_payload_validates_without_the_source_repository(self):
        self.compile_fixture()
        with tempfile.TemporaryDirectory() as isolated:
            payload = Path(isolated) / 'payload'
            shutil.copytree(self.stage, payload)
            # Delete this test's source fixture, including its trace and inputs.
            shutil.rmtree(self.root)
            result = compiler.validate_payload(payload)
            self.assertEqual(result['tasks'], 1)
            self.assertFalse(result['replay_validated'])

    def test_destination_traversal_rejected(self):
        for path in ['/root/../../etc/passwd', '/etc/passwd', 'relative', '/root']:
            with self.subTest(path=path), self.assertRaises(ValueError):
                compiler.destination(path)

    def test_argv_must_be_single_shell_body_and_syntax_valid(self):
        self.assertEqual(compiler.command_argv("/bin/bash -c 'echo ok'")[2], 'echo ok')
        for command in ['python /root/build.py', '/bin/bash -c false trailing', "/bin/bash -c 'if'"]:
            with self.subTest(command=command), self.assertRaises(ValueError):
                compiler.command_argv(command)

    def test_missing_task_rejected(self):
        s = self.fixture()
        s['tasks'] = {}
        with self.assertRaisesRegex(ValueError, 'twelve'):
            compiler.compile_payload(self.root, s, self.stage)


if __name__ == '__main__':
    unittest.main()
