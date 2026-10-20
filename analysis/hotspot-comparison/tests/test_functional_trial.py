"""Launcher safety and stop-on-failure tests; no Docker/workload invocation."""
from dataclasses import dataclass
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout
import io

SCRIPT_DIR = Path(__file__).resolve().parents[1] / 'scripts'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


trial = load('functional_trial_test_module', SCRIPT_DIR / 'functional_trial.py')


class FunctionalTrialTests(unittest.TestCase):
    def test_image_and_container_inspect_use_one_docker_subcommand(self):
        image_payload = [{'Id': 'sha256:fixture'}]
        container_payload = [{'Id': 'fixture-container'}]
        with patch.object(trial, 'docker_json', side_effect=[image_payload, container_payload]) as call:
            self.assertEqual(trial.inspect_image(), 'sha256:fixture')
            self.assertEqual(trial.inspect_container('fixture-name')['Id'], 'fixture-container')
        self.assertEqual(call.call_args_list[0].args[0], ['image', 'inspect', trial.IMAGE])
        self.assertEqual(call.call_args_list[1].args[0], ['inspect', 'fixture-name'])

    def test_docker_argv_overrides_entrypoint_before_image_and_quotes_paths_as_argv(self):
        with tempfile.TemporaryDirectory(prefix='repo with spaces ') as tmp:
            original_root = trial.ROOT
            try:
                trial.ROOT = Path(tmp)
                result_dir = Path(tmp) / 'results with spaces'
                host_parent = result_dir / 'workspace parent'
                argv = trial.docker_create_argv(
                    'hr_metro', 'preflight', trial.IMAGE, result_dir,
                    host_parent, 'trial-container')
            finally:
                trial.ROOT = original_root
        image_index = argv.index(trial.IMAGE)
        self.assertLess(argv.index('--entrypoint'), image_index)
        self.assertEqual(argv[image_index + 1:image_index + 3], ['-c', trial.shell_command('hr_metro', 'preflight')])
        self.assertFalse(any(arg == '-lc' for arg in argv))
        self.assertTrue(any('src=' in arg and 'repo with spaces ' in arg for arg in argv))
        self.assertTrue(any('workspace parent' in arg for arg in argv))

    def test_workspace_mount_is_parent_and_reset_removes_only_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recipe = {'workspace': str(trial.WORKSPACE_PARENT_CONTAINER / 'OFFICE-XLSX-HR-METRO')}
            workspace, host_parent = trial.workspace_layout(recipe, root / 'result')
            self.assertEqual(workspace.parent, trial.WORKSPACE_PARENT_CONTAINER)
            self.assertNotEqual(workspace, trial.WORKSPACE_PARENT_CONTAINER)
            self.assertNotEqual(host_parent, root / 'result' / workspace.name)

            seed = root / 'seed'
            (seed / 'input').mkdir(parents=True)
            (seed / 'input/source.xlsx').write_bytes(b'fixture')
            child = root / 'mounted-parent' / workspace.name
            child.mkdir(parents=True)
            (child / 'stale.txt').write_text('stale')
            runner = trial.load_runner()
            runner.reset_workspace(seed, child)
            self.assertFalse((child / 'stale.txt').exists())
            self.assertEqual((child / 'input/source.xlsx').read_bytes(), b'fixture')

    def test_preflight_shell_cannot_reach_workload_and_trial_is_after_preflight(self):
        preflight = trial.shell_command('retail_online', 'preflight')
        self.assertIn('set -euo pipefail', preflight)
        self.assertIn('preflight_replay.py', preflight)
        self.assertIn('--workspace-parent', preflight)
        self.assertIn('--validate-only', preflight)
        self.assertNotIn('--loops 1', preflight)
        self.assertNotIn('--scene xlsx --dataset retail_online --loops', preflight)

        actual_trial = trial.shell_command('retail_online', 'trial')
        self.assertLess(actual_trial.index('preflight_replay.py'),
                        actual_trial.index('--scene xlsx --dataset retail_online --loops 1'))

    def test_dataclass_runner_import_registers_module_before_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner_file = Path(tmp) / 'runner.py'
            runner_file.write_text(
                'from dataclasses import dataclass\n'
                '@dataclass\nclass Layout:\n    workspace: str\n'
                'def dataset_layout(scene, dataset, count):\n'
                '    return Layout("/fixture/workspace")\n')
            imported = trial.load_runner(runner_file)
            self.assertEqual(imported.dataset_layout('xlsx', 'hr_metro', None).workspace,
                             '/fixture/workspace')
            self.assertIs(__import__('sys').modules['functional_trial_runner'], imported)

    def test_existing_container_preflight_imports_dataclass_runner_safely(self):
        preflight = load('functional_trial_preflight_test', SCRIPT_DIR / 'preflight_replay.py')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner_file = root / 'legacy/document-oe/bin/run_document_scene_loop.py'
            runner_file.parent.mkdir(parents=True)
            runner_file.write_text(
                'from dataclasses import dataclass\n'
                '@dataclass\nclass Layout:\n    workspace: str\n'
                'def dataset_layout(scene, dataset, count):\n'
                '    return {"workspace": Layout("/fixture/workspace").workspace,\n'
                '            "operation_timeout": 900, "recalc_timeout": 600}\n')
            runner_file.with_name('run_document_scene_loop_timed.py').write_text('# fixture\n')
            for directory, names in (
                ('compatibility/verification', ('verify.py', 'spreadsheet.py', 'contracts.py', 'workbooks.py')),
                ('source/office_trace_bench', ('verify.py', 'spreadsheet.py', 'contracts.py', 'workbooks.py')),
            ):
                target = root / directory
                target.mkdir(parents=True)
                for name in names:
                    (target / name).write_text('# fixture\n')
            (root / 'replay').mkdir()
            (root / 'replay/entry.py').write_text('# fixture\n')
            recipe_path = root / 'compatibility/recipes/hr_metro.json'
            recipe_path.parent.mkdir(parents=True)
            recipe_path.write_text('{}\n')
            report = root / 'preflight.json'
            recipe = {'source_path': 'source', 'seed_path': 'seed', 'input_hashes': {}}
            with patch.object(preflight, 'REPO', root), patch.object(preflight, 'RUNNER', runner_file), \
                    patch.object(preflight, 'TIMED_RUNNER',
                                 runner_file.with_name('run_document_scene_loop_timed.py')), \
                    patch.object(preflight.platform, 'python_version', return_value='3.12.3'), \
                    patch.object(preflight, '_has_package', return_value=False), \
                    patch('replay.run.validate_project'), \
                    patch('replay.freeze.validate_dataset', return_value=recipe), \
                    patch('replay.freeze._find_entry', return_value=(None, {
                        'recipe_path': 'compatibility/recipes/hr_metro.json'})), \
                    patch('sys.argv', ['preflight_replay.py', '--dataset', 'hr_metro',
                                       '--output', str(report)]), \
                    redirect_stdout(io.StringIO()):
                preflight.main()
            payload = json.loads(report.read_text())
            self.assertEqual(payload['status'], 'success')
            self.assertEqual(payload['workspace'], '/fixture/workspace')

    def test_preflight_failure_stops_before_workload_and_records_unstarted_dataset(self):
        with tempfile.TemporaryDirectory() as tmp:
            campaign = Path(tmp)
            records = {}
            for dataset in trial.DATASETS:
                path = campaign / 'preflight' / dataset / 'run-record.json'
                path.parent.mkdir(parents=True)
                record = {'status': 'success', 'container_image_id': 'sha256:fixture',
                          'bindings': {'project_lock_sha256': 'same'}}
                path.write_text(json.dumps(record))
                records[dataset] = str(path.relative_to(campaign))
            (campaign / 'campaign-record.json').write_text(json.dumps({
                'phase': 'preflight', 'status': 'success', 'datasets': records}))
            calls = []

            def run_one(dataset, phase, result_dir, token):
                calls.append((dataset, phase))
                return {'status': 'failed', 'failure_stage': 'container_preflight'}

            with patch.object(trial, 'ROOT', campaign), \
                    patch.object(trial, 'inspect_image', return_value='sha256:fixture'), \
                    patch.object(trial, 'source_bindings',
                                 return_value=({}, {'project_lock_sha256': 'same'})), \
                    patch.object(trial, 'run_one', side_effect=run_one):
                code = trial.run_trials(campaign, 'token')
            self.assertEqual(code, 1)
            self.assertEqual(calls, [('hr_metro', 'trial')])
            state = json.loads((campaign / 'campaign-record.json').read_text())
            self.assertEqual(state['failed_dataset'], 'hr_metro')
            self.assertEqual(state['not_started'], ['retail_online'])


class OfflineAuditEntryTests(unittest.TestCase):
    """The in-container audit entry: hash-before, hash-after, mutation detection."""

    def _source(self, root, verifier_body):
        source = root / 'compatibility/cases/fixture_ds/source'
        package = source / 'office_trace_bench'
        package.mkdir(parents=True)
        (package / '__init__.py').write_text('')
        (source / 'office.py').write_text('')
        (package / 'contracts.py').write_text(
            'from pathlib import Path\n'
            'import json\n'
            'ROOT = Path(__file__).resolve().parents[1]\n'
            'def dataset_path(kind, dataset_id):\n'
            '    return ROOT / "datasets/xlsx/fixture_ds/manifest.json"\n'
            'def read_json(path): return json.loads(Path(path).read_text())\n')
        (package / 'verify.py').write_text(verifier_body)
        (package / 'spreadsheet.py').write_text('')
        (package / 'workbooks.py').write_text('')
        dataset = source / 'datasets/xlsx/fixture_ds'
        (dataset / 'input').mkdir(parents=True)
        (dataset / 'manifest.json').write_text(json.dumps({
            'output_workbook': 'out.xlsx', 'kind': 'xlsx', 'dataset_id': 'fixture_ds'}))
        return source

    def _run_entry(self, root, verifier_body):
        self._source(root, verifier_body)
        workspace = root / 'workspace'
        (workspace / 'output').mkdir(parents=True)
        output = workspace / 'output/out.xlsx'
        output.write_bytes(b'archived output bytes')
        results = root / 'results'
        results.mkdir()
        import subprocess
        completed = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / 'offline_audit_entry.py'),
             '--dataset', 'fixture_ds', '--repo', str(root),
             '--workspace', str(workspace),
             '--report', str(results / 'independent-verification.json'),
             '--identity', str(results / 'audit-identity.json')],
            capture_output=True, text=True)
        identity = json.loads((results / 'audit-identity.json').read_text())
        return completed, identity, output, results

    def test_read_only_verifier_passes_and_output_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            body = ('def verify(manifest_path, workspace, report_path):\n'
                    '    from pathlib import Path\n'
                    '    Path(report_path).write_text("{\\"status\\": \\"success\\", \\"failures\\": []}")\n'
                    '    return {"status": "success", "failures": []}\n')
            completed, identity, output, results = self._run_entry(root, body)
            self.assertEqual(completed.returncode, 0)
            self.assertEqual(identity['status'], 'success')
            self.assertEqual(identity['verifier_status'], 'success')
            self.assertEqual(identity['output_sha256_before_audit'],
                             identity['output_sha256_after_audit'])
            self.assertTrue(identity['output_unchanged_by_audit'])
            # report location is outside the workspace
            self.assertFalse(results.resolve().is_relative_to((root / 'workspace').resolve()))
            self.assertIn('openpyxl_version', identity)
            self.assertIn('python_version', identity)
            self.assertIn('verifier_module_sha256', identity)

    def test_mutating_verifier_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            body = ('def verify(manifest_path, workspace, report_path):\n'
                    '    from pathlib import Path\n'
                    '    (workspace / "output/out.xlsx").write_bytes(b"TAMPERED")\n'
                    '    Path(report_path).write_text("{\\"status\\": \\"success\\"}")\n'
                    '    return {"status": "success"}\n')
            completed, identity, output, results = self._run_entry(root, body)
            self.assertNotEqual(completed.returncode, 0)
            self.assertEqual(identity['status'], 'failed')
            self.assertFalse(identity['output_unchanged_by_audit'])
            self.assertNotEqual(identity['output_sha256_before_audit'],
                                identity['output_sha256_after_audit'])

    def test_crashing_verifier_records_failure_and_post_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            body = ('def verify(manifest_path, workspace, report_path):\n'
                    '    raise RuntimeError("verifier exploded")\n')
            completed, identity, output, results = self._run_entry(root, body)
            self.assertNotEqual(completed.returncode, 0)
            self.assertEqual(identity['status'], 'failed')
            self.assertIn('RuntimeError', identity['verifier_error'])
            self.assertIn('Traceback', identity.get('traceback', ''))
            # the post-audit hash is still captured on the failure path
            self.assertEqual(identity['output_sha256_after_audit'],
                             identity['output_sha256_before_audit'])
            self.assertTrue(identity['output_unchanged_by_audit'])


class AuditMountEvidenceTests(unittest.TestCase):
    def test_docker_argv_binds_workspace_readonly_and_results_writable(self):
        with tempfile.TemporaryDirectory() as tmp:
            original_root = trial.ROOT
            try:
                trial.ROOT = Path(tmp)
                argv, command = trial._audit_docker_argv(
                    'hr_metro', Path(tmp) / 'ws', Path(tmp) / 'results', 'audit-name')
            finally:
                trial.ROOT = original_root
        mounts = [arg for arg in argv if arg.startswith('type=bind,')]
        self.assertTrue(any('dst=/workspace,readonly' in m for m in mounts))
        self.assertTrue(any('dst=/opt/office-trace-replay,readonly' in m for m in mounts))
        self.assertTrue(any('dst=/results' in m and 'readonly' not in m for m in mounts))
        self.assertIn('--network', argv)
        self.assertIn('offline_audit_entry.py', command)
        self.assertIn('--entrypoint', argv)
        self.assertLess(argv.index('--entrypoint'), argv.index(trial.IMAGE))

    def test_mount_evidence_rejects_writable_workspace_or_missing_results(self):
        def inspect_with(mounts):
            return {'Mounts': mounts}

        good = [
            {'Destination': '/workspace', 'Source': '/host/ws', 'RW': False},
            {'Destination': '/opt/office-trace-replay', 'Source': '/host/repo', 'RW': False},
            {'Destination': '/results', 'Source': '/host/results', 'RW': True},
        ]
        mounts, problems = trial._audit_mount_evidence.__wrapped__ \
            if hasattr(trial._audit_mount_evidence, '__wrapped__') else (None, None)
        with patch.object(trial, 'inspect_container', return_value=inspect_with(good)):
            mounts, problems = trial._audit_mount_evidence('name', Path('/host/ws'), Path('/host/results'))
        self.assertEqual(problems, [])
        self.assertEqual(mounts['/workspace']['RW'], False)

        bad = [dict(item) for item in good]
        bad[0] = {'Destination': '/workspace', 'Source': '/host/ws', 'RW': True}
        with patch.object(trial, 'inspect_container', return_value=inspect_with(bad)):
            _m, problems = trial._audit_mount_evidence('name', Path('/host/ws'), Path('/host/results'))
        self.assertTrue(any('read-only' in p for p in problems))

        wrong_source = [dict(item) for item in good]
        wrong_source[2] = {'Destination': '/results', 'Source': '/somewhere/else', 'RW': True}
        with patch.object(trial, 'inspect_container', return_value=inspect_with(wrong_source)):
            _m, problems = trial._audit_mount_evidence('name', Path('/host/ws'), Path('/host/results'))
        self.assertTrue(any('results mount source' in p for p in problems))


class AcceptArchivedInventoryTests(unittest.TestCase):
    def _campaign(self, base, *, trials=None, trial_status='success', tamper=None,
                  input_hash_break=False, phase='trial', status='success'):
        campaign = base / 'campaign'
        campaign.mkdir(parents=True, exist_ok=True)
        records = {}
        for dataset in (trials if trials is not None else trial.DATASETS):
            record_dir = campaign / 'trials' / dataset
            workspace = record_dir / 'workspace-parent' / f'OFFICE-XLSX-{dataset.upper().replace("_", "-")}'
            (workspace / 'output').mkdir(parents=True)
            output = workspace / 'output' / f'{dataset}_enhanced.xlsx'
            output.write_bytes(b'archived output bytes' * 100000)
            (workspace / 'input').mkdir()
            (workspace / 'input/prepared_selection.json').write_text('{"artifact": true}')
            input_hashes = {'input/prepared_selection.json': sha_json(b'{"artifact": true}')}
            if input_hash_break:
                (workspace / 'input/prepared_selection.json').write_text('{"tampered": true}')
            files = []
            for path in [workspace / 'input/prepared_selection.json', output]:
                files.append({'path': str(path.relative_to(record_dir)),
                              'size_bytes': path.stat().st_size, 'sha256': sha_json(path.read_bytes())})
            (record_dir / 'archive-index.json').write_text(json.dumps(
                {'schema_version': 'functional-trial-archive-v1', 'files': files,
                 'all_hashes_verified': True}))
            if tamper:
                (record_dir / tamper.format(
                    dataset=dataset,
                    upper=dataset.upper().replace('_', '-'))).write_text('tampered')
            (record_dir / 'run-record.json').write_text(json.dumps({
                'dataset': dataset, 'phase': 'trial', 'status': trial_status,
                'container_exit_code': 0 if trial_status == 'success' else 1,
                'workspace_container_path': f'/root/.openclaw/workspace/tool-modeling/OFFICE-XLSX-{dataset.upper().replace("_", "-")}',
                'container_image_id': 'sha256:trial-image', 'image_tag': trial.IMAGE,
                'bindings': {'input_hashes': input_hashes,
                             'recipe_sha256': 'r' * 64, 'manifest_sha256': 'm' * 64,
                             'provenance_sha256': 'p' * 64, 'helper_sha256': 'h' * 64,
                             'runner_sha256': 'u' * 64},
            }))
            records[dataset] = str((record_dir / 'run-record.json').relative_to(campaign))
        (campaign / 'campaign-record.json').write_text(json.dumps({
            'phase': phase, 'status': status, 'trials': records}))
        return campaign

    def test_empty_inventory_cannot_succeed(self):
        with tempfile.TemporaryDirectory() as tmp:
            campaign = self._campaign(Path(tmp), trials=[])
            with patch.object(trial, 'ROOT', campaign):
                with self.assertRaisesRegex(ValueError, 'exactly'):
                    list(trial._verify_trial_inventory(campaign,
                         json.loads((campaign / 'campaign-record.json').read_text())))

    def test_partial_inventory_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            campaign = self._campaign(Path(tmp), trials=['hr_metro'])
            with patch.object(trial, 'ROOT', campaign):
                with self.assertRaisesRegex(ValueError, 'exactly'):
                    list(trial._verify_trial_inventory(campaign,
                         json.loads((campaign / 'campaign-record.json').read_text())))

    def test_failed_trial_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            campaign = self._campaign(Path(tmp), trial_status='failed')
            with patch.object(trial, 'ROOT', campaign):
                with self.assertRaisesRegex(ValueError, 'not a completed successful run'):
                    list(trial._verify_trial_inventory(campaign,
                         json.loads((campaign / 'campaign-record.json').read_text())))

    def test_tampered_archive_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            campaign = self._campaign(
                Path(tmp),
                tamper='workspace-parent/OFFICE-XLSX-{upper}/output/{dataset}_enhanced.xlsx')
            with patch.object(trial, 'ROOT', campaign):
                with self.assertRaisesRegex(ValueError, 'no archive index|no longer match'):
                    list(trial._verify_trial_inventory(campaign,
                         json.loads((campaign / 'campaign-record.json').read_text())))

    def test_workspace_input_hash_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            campaign = self._campaign(Path(tmp), input_hash_break=True)
            with patch.object(trial, 'ROOT', campaign):
                with self.assertRaisesRegex(ValueError, 'workspace input'):
                    list(trial._verify_trial_inventory(campaign,
                         json.loads((campaign / 'campaign-record.json').read_text())))

    def test_acceptance_uses_a_fresh_directory_and_never_rewrites_trials(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            campaign = self._campaign(base)
            trial_record_before = (campaign / 'trials/hr_metro/run-record.json').read_text()
            audit_calls = []

            def fake_audit(dataset, workspace, dataset_dir):
                audit_calls.append((dataset, workspace, dataset_dir))
                (dataset_dir / 'audit-identity.json').write_text(json.dumps({
                    'status': 'success', 'verifier_status': 'success',
                    'output_unchanged_by_audit': True,
                    'output_sha256_before_audit': 'a' * 64,
                    'output_sha256_after_audit': 'a' * 64}))
                (dataset_dir / 'independent-verification.json').write_text(json.dumps(
                    {'status': 'success', 'failures': [], 'validation_contract': 'x'}))
                return {'execution': 'host', 'readonly_enforced': False,
                        'identity': read_json_path(dataset_dir / 'audit-identity.json'),
                        'audit_container_exit_code': 0}

            def read_json_path(path):
                return json.loads(Path(path).read_text())

            with patch.object(trial, 'ROOT', campaign), \
                    patch.object(trial, 'source_bindings',
                                 return_value=({}, {'recipe_sha256': 'r' * 64,
                                                    'manifest_sha256': 'm' * 64,
                                                    'provenance_sha256': 'p' * 64,
                                                    'helper_sha256': 'h' * 64,
                                                    'input_hashes': {'input/prepared_selection.json': sha_json(b'{"artifact": true}')},
                                                    'runner_sha256': 'u' * 64})), \
                    patch.object(trial, '_run_host_audit', side_effect=fake_audit):
                code = trial.accept_archived(campaign, 'tok1', host_mode=True)
            self.assertEqual(code, 0)
            acceptance_dirs = [d for d in campaign.iterdir() if d.name.startswith('acceptance-')]
            self.assertEqual(len(acceptance_dirs), 1)
            record = json.loads((acceptance_dirs[0] / 'hr_metro' / 'acceptance-record.json').read_text())
            self.assertEqual(record['status'], 'success')
            self.assertEqual(record['trial_image_id'], 'sha256:trial-image')
            self.assertFalse(record['audit']['readonly_enforced'])
            self.assertTrue(record['association']['production_materials_all_match'])
            # a second acceptance run must create another directory, not overwrite
            with patch.object(trial, 'ROOT', campaign), \
                    patch.object(trial, 'source_bindings',
                                 return_value=({}, {'recipe_sha256': 'r' * 64,
                                                    'manifest_sha256': 'm' * 64,
                                                    'provenance_sha256': 'p' * 64,
                                                    'helper_sha256': 'h' * 64,
                                                    'input_hashes': {'input/prepared_selection.json': sha_json(b'{"artifact": true}')},
                                                    'runner_sha256': 'u' * 64})), \
                    patch.object(trial, '_run_host_audit', side_effect=fake_audit):
                code2 = trial.accept_archived(campaign, 'tok2', host_mode=True)
            self.assertEqual(code2, 0)
            acceptance_dirs = [d for d in campaign.iterdir() if d.name.startswith('acceptance-')]
            self.assertEqual(len(acceptance_dirs), 2)
            # the original trial record was never rewritten
            self.assertEqual((campaign / 'trials/hr_metro/run-record.json').read_text(),
                             trial_record_before)

    def test_production_material_mismatch_fails_the_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            campaign = self._campaign(base)

            def fake_audit(dataset, workspace, dataset_dir):
                (dataset_dir / 'audit-identity.json').write_text(json.dumps({
                    'status': 'success', 'verifier_status': 'success',
                    'output_unchanged_by_audit': True,
                    'output_sha256_before_audit': 'a' * 64,
                    'output_sha256_after_audit': 'a' * 64}))
                (dataset_dir / 'independent-verification.json').write_text(json.dumps(
                    {'status': 'success', 'failures': []}))
                return {'execution': 'host', 'readonly_enforced': False,
                        'identity': json.loads((dataset_dir / 'audit-identity.json').read_text()),
                        'audit_container_exit_code': 0}

            # current bindings differ from what the trial ran
            with patch.object(trial, 'ROOT', campaign), \
                    patch.object(trial, 'source_bindings',
                                 return_value=({}, {'recipe_sha256': 'different',
                                                    'manifest_sha256': 'm' * 64,
                                                    'provenance_sha256': 'p' * 64,
                                                    'helper_sha256': 'h' * 64,
                                                    'input_hashes': {},
                                                    'runner_sha256': 'u' * 64})), \
                    patch.object(trial, '_run_host_audit', side_effect=fake_audit):
                code = trial.accept_archived(campaign, 'tok3', host_mode=True)
            self.assertEqual(code, 1)
            acceptance_dirs = [d for d in campaign.iterdir() if d.name.startswith('acceptance-')]
            record = json.loads((acceptance_dirs[0] / 'hr_metro' / 'acceptance-record.json').read_text())
            self.assertEqual(record['status'], 'failed')
            self.assertFalse(record['association']['production_materials_all_match'])
            self.assertEqual(record['association']['production_materials']['recipe_sha256']['trial'],
                             'r' * 64)
            self.assertEqual(record['association']['production_materials']['recipe_sha256']['audit'],
                             'different')

    def test_unrecorded_trial_verifier_hash_is_unknown_not_fabricated(self):
        record = {'bindings': {}, 'container_preflight': {'source_verifier_sha256': None}}
        with patch.object(trial, 'ROOT', Path('.')):
            association = trial._source_association('hr_metro', record)
        for name in trial.VERIFIER_PACKAGE_FILES:
            self.assertEqual(association['verifier_comparison'][name]['trial'], 'unknown')


def sha_json(data):
    import hashlib
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()


if __name__ == '__main__':
    unittest.main()
