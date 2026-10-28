import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('offline_build_image', ROOT / 'scripts/build_image.py')
build_image = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_image)


class OfflineBuild(unittest.TestCase):
    def test_wrong_local_base_is_rejected_before_build(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'container-contract.json').write_text(json.dumps({'base_image_id': 'sha256:expected'}))
            with patch.object(build_image.subprocess, 'check_output', return_value='[{"Id":"sha256:wrong"}]'), \
                 patch.object(build_image.subprocess, 'run') as run:
                with self.assertRaisesRegex(ValueError, 'local base image mismatch'):
                    build_image.build('test:new', root=root)
                run.assert_not_called()

    def test_existing_target_is_not_overwritten(self):
        with patch.object(build_image.subprocess, 'check_output',
                          return_value=json.dumps([{'Id': json.loads((ROOT / 'container-contract.json').read_text())['base_image_id']}])), \
             patch.object(build_image.subprocess, 'run') as run:
            run.return_value.returncode = 0
            with self.assertRaisesRegex(ValueError, 'already exists'):
                build_image.build('test:existing')
            self.assertEqual(run.call_count, 1)
            self.assertIn('inspect', run.call_args.args[0])

    def test_build_evidence_uses_documentation_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'container-contract.json').write_text(json.dumps({'base_image_id': 'sha256:base'}))
            (root / 'Dockerfile').write_text('FROM local-base\n')
            with patch.object(build_image.subprocess, 'check_output', side_effect=[
                    '[{"Id":"sha256:base"}]', '[{"Id":"sha256:new"}]']), \
                 patch.object(build_image.subprocess, 'run') as run:
                run.side_effect = [type('Result', (), {'returncode': 1})(),
                                   type('Result', (), {'returncode': 0})()]
                self.assertEqual(build_image.build('test:new', root=root), 0)
            reports = list((root / 'docs/evidence').glob('image-build-*.json'))
            self.assertEqual(len(reports), 1)
            record = json.loads(reports[0].read_text())
            self.assertEqual(record['status'], 'success')
            self.assertEqual(record['image']['Id'], 'sha256:new')
            self.assertTrue((root / record['log']).is_file())
            self.assertFalse((root / 'reports').exists())
            self.assertIn('--pull=false', record['command'])
            self.assertEqual(record['command'][record['command'].index('--network') + 1], 'none')


if __name__ == '__main__':
    unittest.main()
