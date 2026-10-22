"""Small build-entry checks; never start Docker or a workload."""
import importlib.util
import json
import subprocess
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('build_image_packaging', ROOT / 'scripts/build_image.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class ImagePackagingTests(unittest.TestCase):
    def test_operator_defaults_use_the_retained_release(self):
        release = json.loads((ROOT / 'reports/evidence/v12/index.json').read_text())
        for name in ('functional_trial.py', 'cpu_measurement_trial.py', 'collector_smoke.py'):
            code = (ROOT / 'analysis/hotspot-comparison/scripts' / name).read_text()
            self.assertIn(release['image_tag'], code)
            self.assertNotIn('office-trace-replay:openeuler-v11', code)
        smoke = (ROOT / 'analysis/hotspot-comparison/scripts/collector_smoke.py').read_text()
        self.assertIn(release['image_id'], smoke)

    def test_future_base_matches_the_qualified_v12_image(self):
        environment = json.loads((ROOT / 'runtime/environment-lock.json').read_text())
        release = json.loads((ROOT / 'reports/evidence/v12/index.json').read_text())
        self.assertEqual(environment['base_image'], release['image_tag'])
        self.assertEqual(environment['base_image_id'], release['image_id'])
        dockerfile = (ROOT / 'runtime/Dockerfile').read_text()
        self.assertIn('ARG BASE_IMAGE=' + environment['base_image'] + '\n', dockerfile)

    def test_build_passes_validated_base_tag_to_docker(self):
        base_id = 'sha256:' + 'a' * 64
        base = {'Id': base_id, 'RootFS': {'Layers': ['shared-runtime']}, 'Size': 100}
        image = {'Id': 'sha256:' + 'b' * 64, 'Architecture': 'arm64',
                 'RootFS': {'Layers': ['shared-runtime', 'new-project']}, 'Size': 120}
        environment = {'base_image': 'qualified-base', 'base_image_id': base_id,
                       'document_runner_sha256': 'runner-hash'}

        def read(path):
            return environment if path.name == 'environment-lock.json' else {'workload': list(range(43))}

        def output(command, **kwargs):
            if '--format' in command:
                return base_id + '\n'
            return json.dumps([base if command[-1] == base_id else image])

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(builder, 'ROOT', root), \
                    patch('sys.argv', ['build_image.py', '--tag', 'new-release']), \
                    patch.object(builder, 'local_image_id', return_value=None), \
                    patch.object(builder, 'read', side_effect=read), \
                    patch.object(builder, 'digest', return_value='runner-hash'), \
                    patch.object(builder, 'git_source_identity', return_value={}), \
                    patch.object(builder, 'context_estimate', return_value={}), \
                    patch.object(builder.subprocess, 'check_output', side_effect=output), \
                    patch.object(builder.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '{}', '')) as run:
                builder.main()
            command = next(call.args[0] for call in run.call_args_list
                           if call.args[0][:2] == ['docker', 'build'])
            self.assertEqual(command[command.index('--build-arg') + 1], 'BASE_IMAGE=qualified-base')

    def test_context_keeps_frozen_nested_reports_but_excludes_host_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for relative in ('reports/host.json', 'analysis/raw/data', 'tests/test.py',
                             'assets/evidence/reports/frozen.json', 'replay/main.py'):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'123')
            self.assertEqual(builder.context_estimate(root),
                             {'file_count': 2, 'payload_bytes_estimate': 6})

    def test_versions_have_distinct_evidence_paths(self):
        root = Path('/fixture')
        v10 = builder.evidence_paths('office-trace-replay:openeuler-v10', root)
        v11 = builder.evidence_paths('office-trace-replay:openeuler-v11', root)
        v12 = builder.evidence_paths('office-trace-replay:openeuler-v12', root)
        self.assertEqual(v10[0].name, 'image-build-v10.json')
        self.assertEqual(v11[1].name, 'image-install-acceptance-v11.json')
        self.assertEqual(v12[0].name, 'image-build-v12.json')
        self.assertTrue(set(v10).isdisjoint(v11))
        self.assertTrue(set(v11).isdisjoint(v12))

    def test_existing_evidence_refuses_before_docker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = builder.evidence_paths('office-trace-replay:openeuler-v12', root)
            record.parent.mkdir()
            record.write_text('preserve me')
            with patch.object(builder, 'ROOT', root), \
                    patch('sys.argv', ['build_image.py']), \
                    patch.object(builder, 'local_image_id', side_effect=AssertionError('Docker called')):
                with self.assertRaises(FileExistsError):
                    builder.main()
            self.assertEqual(record.read_text(), 'preserve me')


if __name__ == '__main__':
    unittest.main()
