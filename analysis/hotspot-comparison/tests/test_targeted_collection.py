"""Collector regressions using tiny files and fake container/sampler processes."""
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / 'analysis/hotspot-comparison/scripts'


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


target = load('collect_targeted_hotspots_v2')
collector = load('collect_current_loop_profiles')
exporter = load('bounded_perf_export')
quality = load('collection_quality')


def cfg():
    return dict(config_id='retail', dataset='retail', scene='xlsx',
                record_count=None, loops=1, rate_hz=49)


def new_plan():
    configs = [dict(config_id=d, dataset=d, scene='xlsx', record_count=None,
                    loops=1, rate_hz=49)
               for d in ('hr_metro', 'retail_online')]
    return {'configs': configs, 'order': ['hr_metro', 'retail_online'],
            'modes': ['native', 'pyspy'], 'loops': 1}


class PreflightTests(unittest.TestCase):
    def test_container_preflight_preserves_pdf_scene_and_count(self):
        preflight = load('preflight_replay')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner = root / 'legacy/document-oe/bin/run_document_scene_loop.py'
            runner.parent.mkdir(parents=True)
            runner.write_text("def dataset_layout(scene,dataset,count):\n"
                              "    assert (scene,dataset,count)==('pdf','irs_w4',10)\n"
                              "    return {'workspace':'/fake/pdf-n10','operation_timeout':900,'recalc_timeout':600}\n")
            timed_runner = root / 'legacy/document-oe/bin/run_document_scene_loop_timed.py'
            timed_runner.write_text('# timed fixture\n')
            for parent in ('compatibility/verification', 'source/office_trace_bench'):
                directory = root / parent
                directory.mkdir(parents=True)
                for name in ('pdf.py', 'pdf_loop.py'):
                    (directory / name).write_text('# fixture\n')
            (root / 'replay').mkdir()
            (root / 'replay/entry.py').write_text('# fixture\n')
            recipe_path = root / 'compatibility/recipes/irs_w4-n10.json'
            recipe_path.parent.mkdir()
            recipe_path.write_text('{}')
            report = root / 'preflight.json'
            recipe = dict(source_path='source', seed_path='seed', input_hashes={})
            with patch.object(preflight, 'REPO', root), patch.object(preflight, 'RUNNER', runner), \
                    patch.object(preflight, 'TIMED_RUNNER', timed_runner), \
                    patch.object(preflight.platform, 'python_version', return_value='3.12.3'), \
                    patch.object(preflight, '_has_package', return_value=False), \
                    patch('replay.run.validate_project'), \
                    patch('replay.freeze.validate_dataset', return_value=recipe) as validate, \
                    patch('replay.freeze._find_entry', return_value=(None, {
                        'recipe_path': 'compatibility/recipes/irs_w4-n10.json'})), \
                    patch('sys.argv', ['preflight_replay.py', '--scene', 'pdf', '--dataset', 'irs_w4',
                                       '--pdf-applicant-count', '10', '--output', str(report)]), \
                    redirect_stdout(io.StringIO()):
                preflight.main()
            result = json.loads(report.read_text())
            self.assertEqual(result['record_count'], 10)
            self.assertEqual(result['scene'], 'pdf')
            self.assertEqual(result['recipe'], str(recipe_path))
            self.assertEqual(validate.call_args.args[:2], ('pdf', 'irs_w4'))
            self.assertEqual(validate.call_args.args[3], 10)

    def test_preflight_only_checks_all_without_docker_inventory_or_collection(self):
        fake = Mock()
        plan = new_plan()
        with patch.object(target, 'read', return_value=plan), \
                patch.object(target, 'load_collector', return_value=fake), \
                patch.object(target, 'host_preflight', return_value={'status': 'success'}) as check, \
                patch.object(target.subprocess, 'check_output', side_effect=AssertionError('Docker called')), \
                patch.object(target, 'evidence_inventory', side_effect=AssertionError('inventory called')), \
                patch.object(target, 'write', side_effect=AssertionError('campaign written')), \
                redirect_stdout(io.StringIO()):
            self.assertEqual(target.main(['--preflight-only']), 0)
        self.assertEqual(check.call_count, 2)
        self.assertEqual(check.call_args_list[0].args[1]['dataset'], 'hr_metro')
        fake.collect_one.assert_not_called()

    def test_preflight_failure_returns_nonzero_without_launch(self):
        fake = Mock()
        plan = new_plan()
        with patch.object(target, 'read', return_value=plan), \
                patch.object(target, 'load_collector', return_value=fake), \
                patch.object(target, 'host_preflight', side_effect=ValueError('bad binding')), \
                patch.object(target.subprocess, 'check_output', side_effect=AssertionError('Docker called')), \
                redirect_stdout(io.StringIO()) as output:
            self.assertEqual(target.main(['--preflight-only']), 1)
        self.assertIn('bad binding', output.getvalue())
        fake.collect_one.assert_not_called()

    def test_container_preflight_uses_current_image_mounts_and_no_sampler(self):
        plan = {'image':'v11', 'image_id':'img', 'python':'/venv/python',
                'entry':'/repo/replay/entry.py', 'operation_timeout_seconds':900,
                'recalc_timeout_seconds':600}
        cfg_new = dict(config_id='hr_metro', dataset='hr_metro', scene='xlsx',
                       record_count=None, loops=1, rate_hz=49)
        with tempfile.TemporaryDirectory() as tmp:
            campaign = Path(tmp) / 'campaign'
            campaign.mkdir()
            def run(command, **kwargs):
                if command[1] == 'inspect':
                    return subprocess.CompletedProcess(command, 0, json.dumps([
                        {'Image':'img','Id':'container-id'}]), '')
                report = campaign / 'container-preflight/hr_metro/preflight.json'
                report.parent.mkdir(parents=True, exist_ok=True)
                report.write_text(json.dumps({'status':'success','python_version':'3.12.3',
                    'runner_sha256':'runner','timed_runner_sha256':'timed',
                    'recipe_sha256':'recipe','workspace':'/registry/workspace',
                    'operation_timeout_seconds':900,'recalc_timeout_seconds':600}))
                return subprocess.CompletedProcess(command, 0, '', '')
            with patch.object(target.subprocess, 'run', side_effect=run):
                result = target.container_preflight(plan, cfg_new, campaign, 'token')
            self.assertEqual(result['status'], 'success')
            argv = json.loads((campaign / 'container-preflight/hr_metro/docker-argv.json').read_text())
            self.assertLess(argv.index('--entrypoint'), next(i for i, x in enumerate(argv) if x == 'img'))
            self.assertIn('run_document_scene_loop_timed.py', ' '.join(argv))
            self.assertIn('preflight_replay.py', ' '.join(argv))

    def test_standalone_cli_bootstraps_imports_from_any_cwd(self):
        # A minimal repo fixture exercises the actual CLI, import and hash path
        # without importing the real runner or executing any workload.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scripts = root / 'analysis/hotspot-comparison/scripts'
            scripts.mkdir(parents=True)
            (scripts / 'collect_targeted_hotspots_v2.py').write_bytes(
                (SCRIPTS / 'collect_targeted_hotspots_v2.py').read_bytes())
            (scripts / 'collect_current_loop_profiles.py').write_text(
                "from pathlib import Path\n"
                "def recipe_info(cfg): return {}, Path(__file__), {}\n"
                "def verifier_hashes(scene): return {}\n"
                "def collect_one(*a, **kw): raise AssertionError('sampler started')\n")
            replay = root / 'replay'
            replay.mkdir()
            (replay / '__init__.py').write_text('')
            (replay / 'run.py').write_text('def validate_project(): pass\n')
            (replay / 'freeze.py').write_text(
                "def validate_dataset(*a, **kw): return {'seed_path': '.', 'input_hashes': {}}\n")
            runner = root / 'legacy/document-oe/bin/run_document_scene_loop.py'
            runner.parent.mkdir(parents=True)
            runner.write_text("def dataset_layout(*a): return {'workspace': '/fake/workspace', 'operation_timeout':900, 'recalc_timeout':600}\n")
            compat = root / 'compatibility'
            compat.mkdir()
            (compat / 'suite.json').write_text(json.dumps({'entries': [
                {'dataset_id': d, 'record_count': None,
                 'recipe_path': f'compatibility/recipes/{d}.json'}
                for d in ('hr_metro', 'retail_online')]}))
            (compat / 'recipes').mkdir()
            for dataset in ('hr_metro', 'retail_online'):
                (compat / 'recipes' / f'{dataset}.json').write_text(json.dumps({'input_hashes': {}}))
            plan = root / 'plan.json'
            plan.write_text(json.dumps(new_plan()))
            env = os.environ.copy()
            env.pop('PYTHONPATH', None)
            # An empty PATH guarantees no external Docker command can run.
            env['PATH'] = ''
            for cwd in (root, Path('/tmp')):
                run = subprocess.run([sys.executable, str(scripts / 'collect_targeted_hotspots_v2.py'),
                                      '--plan', str(plan), '--preflight-only'],
                                     cwd=cwd, env=env, capture_output=True, text=True, timeout=10)
                self.assertEqual(run.returncode, 0, run.stderr)
                result = json.loads(run.stdout)
                self.assertEqual([x['dataset'] for x in result['datasets']], ['hr_metro', 'retail_online'])
                self.assertTrue(all(x['status'] == 'success' for x in result['datasets']))


class ContainerScriptTests(unittest.TestCase):
    def run_fake_container(self, root, *, preflight_rc=0, collector_rc=0, output=True):
        src = root / 'host-analysis/scripts'
        src.mkdir(parents=True)
        data = root / 'data'
        workspace = root / 'workspace'
        if output:
            (workspace / 'output').mkdir(parents=True)
            (workspace / 'output/business_verification.json').write_text('{"status":"success"}')
        (src / 'preflight_replay.py').write_text(
            "import argparse,json\nfrom pathlib import Path\n"
            "p=argparse.ArgumentParser(); p.add_argument('--output'); a, _=p.parse_known_args()\n"
            f"Path(a.output).write_text(json.dumps({{'workspace': {str(workspace)!r}, 'status': 'success'}}))\n"
            f"raise SystemExit({preflight_rc})\n")
        marker = root / 'collector-started'
        (src / 'collect_native.sh').write_text(
            f"printf started > {marker}\nexit {collector_rc}\n")
        script = collector.container_script({'python': sys.executable}, cfg(), 'native')
        script = script.replace('/host-analysis', str(root / 'host-analysis'))
        script = script.replace('/tmp/hs-scripts', str(root / 'hs-scripts'))
        script = script.replace('/data', str(data))
        result = subprocess.run(['bash', '-c', script], capture_output=True, text=True, timeout=10)
        return result, data / 'out', marker

    def test_preflight_failure_does_not_start_collector_or_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            run, out, marker = self.run_fake_container(Path(tmp), preflight_rc=9)
            self.assertEqual(run.returncode, 9, run.stderr)
            self.assertFalse(marker.exists())
            self.assertFalse((out / 'archive-exit-code.txt').exists())

    def test_collector_failure_preserved_when_workspace_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            run, out, marker = self.run_fake_container(Path(tmp), collector_rc=7, output=False)
            self.assertEqual(run.returncode, 7, run.stderr)
            self.assertTrue(marker.exists())
            self.assertEqual((out / 'collector-exit-code.txt').read_text().strip(), '7')
            self.assertEqual((out / 'archive-exit-code.txt').read_text().strip(), '1')

    def test_successful_fake_collector_archives_business_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            run, out, _ = self.run_fake_container(Path(tmp))
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads((out / 'business_verification.json').read_text())['status'], 'success')

    def test_invalid_mode_is_rejected_without_creating_stage(self):
        with self.assertRaises(ValueError):
            collector.container_script({}, cfg(), 'invalid')


class QualificationTests(unittest.TestCase):
    def simulate(self, *, mode='native', recipe_hash='hash', image='image-id',
                 business='success', preflight='success', sample_count=1, interrupted=False):
        with tempfile.TemporaryDirectory() as tmp:
            campaign = Path(tmp)
            stage = campaign / 'retail' / ('r1' if mode == 'native' else 'pyspy')
            def invoke(command, log):
                self.assertIn('image-id', command)
                out = stage / 'out'
                (out / 'collector-exit-code.txt').write_text('0\n')
                (out / 'archive-exit-code.txt').write_text('0\n')
                (out / 'preflight.json').write_text(json.dumps({'status': preflight}))
                summary = dict(scene='xlsx', dataset='retail', requested_iterations=1,
                               completed_iterations=1, successes=1, failures=0,
                               recipe_sha256=recipe_hash, interrupted=interrupted,
                               operation_timeout_seconds=900, recalc_timeout_seconds=600)
                (out / 'metadata.json').write_text(json.dumps({
                    'runner_summary': summary, 'perf_rc': 0, 'rc': 0,
                    'perf_record_status': 'success', 'perf_export_status': 'complete',
                    'perf_data_host_read_permission_status': 'success',
                    'raw_host_read_permission_status': 'success',
                    'total_samples': 1}))
                (out / 'business_verification.json').write_text(json.dumps({'status': business, 'failures': []}))
                (stage / 'raw/retail.pyspy.raw').write_text('tiny fake sample')
                return 0
            def run(command, **kwargs):
                out = stage / 'out'
                if command[:2] == ['docker', 'inspect']:
                    return subprocess.CompletedProcess(command, 0, json.dumps([
                        {'State': {'ExitCode': 0}, 'Image': image, 'Id': 'fake-container'}]), '')
                if command[1].endswith('parse_native.py'):
                    (out / 'roi.json').write_text(json.dumps({
                        'roi_samples': sample_count, 'roi_period_total': sample_count * 100,
                        'perf_script_parse': {'recognized_samples_total': 1}}))
                elif command[1].endswith('parse_pyspy.py'):
                    (out / 'pyspy-roles.json').write_text(json.dumps({
                        'roles': {'xlsx-verify': {'samples': sample_count}},
                        'parse_integrity': {'status': 'complete',
                                            'raw_nonempty_line_count': 1,
                                            'parsed_stack_line_count': 1,
                                            'raw_positive_count_sum': 1,
                                            'parsed_count_sum': 1}}))
                else:
                    raise AssertionError(f'unexpected subprocess: {command}')
                return subprocess.CompletedProcess(command, 0, '', '')
            with patch.object(collector, 'recipe_info', return_value=(
                    {'recipe_sha256': 'hash'}, Path('recipe.json'), {'input_hashes': {}})), \
                    patch.object(collector, 'sha', return_value='hash'), \
                    patch.object(collector, 'verifier_hashes', return_value={}), \
                    patch.object(collector, 'invoke', side_effect=invoke), \
                    patch.object(collector.subprocess, 'run', side_effect=run), \
                    redirect_stdout(io.StringIO()):
                ok = collector.collect_one({'image': 'tag', 'image_id': 'image-id'}, cfg(), mode, campaign)
            record = json.loads((stage / 'out/collection-record.json').read_text())
            return ok, record

    def test_full_native_and_pyspy_success_qualify(self):
        for mode in ('native', 'pyspy'):
            with self.subTest(mode=mode):
                ok, record = self.simulate(mode=mode)
                self.assertTrue(ok)
                self.assertTrue(record['stage_status']['profile_eligible'])

    def test_mismatch_failure_and_empty_samples_never_qualify(self):
        for mode in ('native', 'pyspy'):
            for failure in ({'recipe_hash': 'wrong'}, {'image': 'wrong'},
                            {'business': 'failed'}, {'preflight': 'failed'},
                            {'sample_count': 0}, {'interrupted': True}):
                with self.subTest(mode=mode, failure=failure):
                    ok, record = self.simulate(mode=mode, **failure)
                    self.assertFalse(ok)
                    self.assertFalse(record['stage_status']['profile_eligible'])


class ArchiveIndexTests(unittest.TestCase):
    def make_stage(self, campaign, *, acquisition_eligible=True):
        stage = campaign / 'retail/r1'
        raw, out = stage / 'raw', stage / 'out'
        raw.mkdir(parents=True)
        out.mkdir()
        (raw / 'retail.data').write_bytes(b'tiny fixture capture')
        (raw / 'retail.samples.txt').write_text('tiny parsed fixture\n')
        record_path = out / 'collection-record.json'
        record_path.write_text(json.dumps({
            'status': 'success', 'reason': None,
            'stage_status': {'workload': 'success', 'record': 'success',
                             'export': 'success', 'parser': 'success',
                             'profile_eligible': acquisition_eligible}}))
        manifest = {'status': 'in_progress', 'completed_modes': []}
        plan = {'order': ['retail', 'hr', 'industry_productivity'],
                'modes': ['native', 'pyspy']}
        return stage, record_path, manifest, plan

    def finalize(self, campaign, record_path, manifest, plan, *, ok=True):
        return target.finalize_mode(campaign, manifest, plan, 'retail', 'native',
                                    record_path, ok)

    def test_complete_archive_and_final_record_hash_qualify(self):
        with tempfile.TemporaryDirectory() as tmp:
            campaign = Path(tmp)
            _, record_path, manifest, plan = self.make_stage(campaign)
            stage_ok, record, archive = self.finalize(campaign, record_path, manifest, plan)
            self.assertTrue(stage_ok)
            self.assertTrue(record['stage_status']['profile_eligible'])
            self.assertTrue(record['final_profile_eligible'])
            self.assertTrue(archive['final_profile_eligible'])
            self.assertEqual(archive['index_write_status'], 'success')
            index = json.loads((record_path.parent.parent / 'sha256-index.json').read_text())
            rows = {row['path']: row for row in index['files']}
            self.assertEqual(rows['out/collection-record.json']['sha256'], target.sha(record_path))
            self.assertTrue(manifest['completed_modes'][0]['profile_eligible'])

    def test_index_atomic_replace_failure_downgrades_and_stops(self):
        with tempfile.TemporaryDirectory() as tmp:
            campaign = Path(tmp)
            _, record_path, manifest, plan = self.make_stage(campaign)
            real_replace = Path.replace

            def fail_index_replace(path, target_path):
                if path.name == 'sha256-index.json.tmp':
                    raise PermissionError('fixture index replace denied')
                return real_replace(path, target_path)

            with patch.object(Path, 'replace', fail_index_replace):
                stage_ok, record, archive = self.finalize(campaign, record_path, manifest, plan)
            self.assertFalse(stage_ok)
            self.assertFalse(record['stage_status']['profile_eligible'])
            self.assertFalse(record['final_profile_eligible'])
            self.assertTrue(archive['required_raw_sha256_complete'])
            self.assertEqual(archive['index_write_status'], 'failed')
            self.assertIn('fixture index replace denied', archive['index_write_error'])
            saved = json.loads((campaign / 'campaign-manifest.json').read_text())
            self.assertFalse(saved['completed_modes'][0]['profile_eligible'])
            self.assertFalse(saved['completed_modes'][0]['stage_status']['profile_eligible'])
            self.assertFalse(saved['failure']['profile_eligible'])
            self.assertEqual([item['dataset'] for item in saved['not_started']],
                             ['retail', 'hr', 'hr', 'industry_productivity',
                              'industry_productivity'])

    def test_record_update_failure_is_explicitly_false_in_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            campaign = Path(tmp)
            _, record_path, manifest, plan = self.make_stage(campaign)
            real_write = target.write

            def fail_record_write(path, data):
                if Path(path) == record_path:
                    raise PermissionError('fixture record write denied')
                return real_write(path, data)

            with patch.object(target, 'write', side_effect=fail_record_write):
                stage_ok, record, archive = self.finalize(campaign, record_path, manifest, plan)
            self.assertFalse(stage_ok)
            self.assertEqual(archive['record_update_error'],
                             'PermissionError: fixture record write denied')
            saved = json.loads((campaign / 'campaign-manifest.json').read_text())
            completed = saved['completed_modes'][0]
            self.assertFalse(completed['profile_eligible'])
            self.assertFalse(completed['stage_status']['profile_eligible'])
            self.assertFalse(completed['archive_integrity']['final_profile_eligible'])
            self.assertFalse(saved['failure']['profile_eligible'])
            self.assertEqual(saved['failure']['record_path'], 'retail/r1/out/collection-record.json')
            self.assertEqual(saved['status'], 'stopped_on_failure')

    def test_archive_success_does_not_upgrade_failed_acquisition(self):
        with tempfile.TemporaryDirectory() as tmp:
            campaign = Path(tmp)
            _, record_path, manifest, plan = self.make_stage(
                campaign, acquisition_eligible=False)
            stage_ok, record, archive = self.finalize(campaign, record_path, manifest, plan)
            self.assertFalse(stage_ok)
            self.assertEqual(archive['status'], 'complete')
            self.assertEqual(archive['index_write_status'], 'success')
            self.assertFalse(record['acquisition_profile_eligible'])
            self.assertFalse(record['stage_status']['profile_eligible'])
            saved = json.loads((campaign / 'campaign-manifest.json').read_text())
            self.assertFalse(saved['completed_modes'][0]['profile_eligible'])

    def test_permission_error_is_indexed_and_stops_campaign_before_next_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            campaign = Path(tmp)
            stage = campaign / 'retail/r1'
            raw = stage / 'raw'
            out = stage / 'out'
            raw.mkdir(parents=True)
            out.mkdir()
            data = raw / 'retail.data'
            data.write_bytes(b'tiny fixture capture')
            (raw / 'retail.samples.txt').write_text('tiny parsed fixture\n')
            record_path = out / 'collection-record.json'
            record_path.write_text(json.dumps({
                'status': 'success', 'stage_status': {'profile_eligible': True},
                'reason': None}))
            manifest = {'status': 'in_progress', 'completed_modes': []}
            plan = {'order': ['retail', 'hr', 'industry_productivity'],
                    'modes': ['native', 'pyspy']}
            real_sha = target.sha

            def fail_one_file(path):
                if Path(path) == data:
                    raise PermissionError('fixture denied')
                return real_sha(path)

            with patch.object(target, 'sha', side_effect=fail_one_file):
                stage_ok, record, archive = target.finalize_mode(
                    campaign, manifest, plan, 'retail', 'native', record_path, True)

            self.assertFalse(stage_ok)
            self.assertEqual(archive['status'], 'partial')
            self.assertFalse(archive['required_raw_sha256_complete'])
            self.assertEqual(record['status'], 'success', 'keep the acquisition status intact')
            self.assertFalse(record['stage_status']['profile_eligible'])
            self.assertEqual(record['stage_status']['archive_sha256_index'], 'success')
            index = json.loads((stage / 'sha256-index.json').read_text())
            files = {row['path']: row for row in index['files']}
            self.assertEqual(files['raw/retail.data']['status'], 'unreadable')
            self.assertIsNone(files['raw/retail.data']['sha256'])
            self.assertEqual(files['raw/retail.samples.txt']['status'], 'hashed')
            saved_manifest = json.loads((campaign / 'campaign-manifest.json').read_text())
            self.assertEqual(saved_manifest['status'], 'stopped_on_failure')
            self.assertEqual([row['dataset'] for row in saved_manifest['not_started']],
                             ['retail', 'hr', 'hr', 'industry_productivity',
                              'industry_productivity'])

    def test_missing_required_raw_hash_never_qualifies_but_other_archive_errors_are_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'out').mkdir()
            record_path = root / 'out/collection-record.json'
            record_path.write_text(json.dumps({'status': 'success',
                'stage_status': {'profile_eligible': True}}))
            result = target.sha_tree(root, required_raw_files=['raw/missing.data'],
                                     record_path=record_path)
            record = json.loads(record_path.read_text())
            index = json.loads((root / 'sha256-index.json').read_text())
            self.assertEqual(result['status'], 'partial')
            self.assertFalse(record['stage_status']['profile_eligible'])
            self.assertEqual(index['files'][0]['status'], 'missing')


class ExportAndParserTests(unittest.TestCase):
    def test_capture_quality_keeps_loss_counters_scopes_and_symbol_dimensions_separate(self):
        roi = {'roi_period_total': 1000, 'perf_script_parse': {
            'recognized_samples_total': 100, 'perf_metadata_sample_count': 100,
            'true_unknown_dso_samples': 4, 'true_unknown_dso_period': 70,
            'unresolved_leaf_symbol_samples': 5, 'unresolved_leaf_symbol_period': 90,
            'inline_owner_unresolved_samples': 3, 'inline_owner_unresolved_period': 40,
            'inline_recovered_samples': 8, 'inline_recovered_period': 300,
        }}
        result = quality.summarize_native_quality(
            perf_record_log='perf: lost 45 chunks\n',
            report_text='# Total Lost Samples: 471\n',
            perf_script_stderr=(
                'addr2line /root/.debug/.build-id/7c/1fa2b12f21b41ea6d016342b5af7401d42407d/elf: '
                'could not read first record\n'),
            roi=roi, export_status='complete', parser_exit_code=0,
            perf_report_exit_code=0)
        self.assertEqual(result['capture_loss']['lost_chunks']['count'], 45)
        self.assertEqual(result['capture_loss']['lost_samples']['count'], 471)
        self.assertIn('ROI allocation is unknown', result['capture_loss']['lost_chunks']['scope'])
        self.assertTrue(result['sample_text_export']['complete_for_formal_parse_gate'])
        symbols = result['symbol_resolution']
        self.assertEqual(symbols['addr2line_warnings']['warning_count'], 1)
        self.assertEqual(symbols['addr2line_warnings']['warnings_by_build_id'],
                         {'7c1fa2b12f21b41ea6d016342b5af7401d42407d': 1})
        self.assertEqual(symbols['roi_categories']['true_unknown_dso']['samples'], 4)
        self.assertEqual(symbols['roi_categories']['true_unknown_dso']['sample_period'], 70)
        self.assertEqual(symbols['roi_categories']['unresolved_leaf_symbol']['samples'], 5)
        self.assertEqual(symbols['roi_categories']['inline_owner_unresolved']['sample_period'], 40)

    def test_export_zero_does_not_claim_complete_parse_when_sample_counts_differ(self):
        result = quality.summarize_native_quality(
            perf_record_log='', report_text='', perf_script_stderr='',
            roi={'roi_period_total': 10, 'perf_script_parse': {
                'recognized_samples_total': 9, 'perf_metadata_sample_count': 10}},
            export_status='complete', parser_exit_code=0, perf_report_exit_code=0)
        self.assertFalse(result['sample_text_export']['complete_for_formal_parse_gate'])
        self.assertFalse(result['sample_text_export']['counts_match'])

    def test_derived_report_uses_bounded_export_without_running_perf(self):
        with patch.object(exporter, 'bounded_export', return_value={'status': 'complete'}) as export, \
                patch('sys.argv', ['bounded_perf_export.py', 'fake.data', 'out', 'status',
                                   '--report-sort', 'comm,dso', '--force-input']), redirect_stdout(io.StringIO()):
            self.assertEqual(exporter.main(), 0)
        self.assertEqual(export.call_args.kwargs['command'][:2], ['perf', 'report'])
        self.assertIn('-f', export.call_args.kwargs['command'])

    def test_invalid_export_timeout_is_rejected_before_writes(self):
        for seconds in (0, -1, float('inf'), float('nan')):
            with self.assertRaises(ValueError):
                exporter.bounded_export('unused', 'unused', 'unused', seconds)

    def test_pyspy_preserves_process_only_activity_in_denominator(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = root / 'tiny.raw'
            raw.write_text('process 11:"python /tmp/verify_office.py" 3\n'
                           'process 11:"python /tmp/verify_office.py";work (helper.py:1) 2\n')
            (root / 'metadata.json').write_text('{"runner_summary":{"scene":"xlsx"}}')
            result = subprocess.run([sys.executable, str(SCRIPTS / 'parse_pyspy.py'), str(raw), str(root)],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            roles = json.loads((root / 'pyspy-roles.json').read_text())['roles']
            self.assertEqual(roles['xlsx-verify']['samples'], 5)
            self.assertEqual(roles['xlsx-verify']['mechanism_counts']['M-UNCLASSIFIED'], 3)


class NativeShellTests(unittest.TestCase):
    def test_pyspy_shell_returns_sampler_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / 'bin'
            bin_dir.mkdir()
            (bin_dir / 'taskset').write_text('#!/bin/sh\nshift 2\nexec "$@"\n')
            (bin_dir / 'py-spy').write_text('#!/bin/sh\nprintf "fake collector failure\\n" >&2\nexit 19\n')
            for path in bin_dir.iterdir():
                path.chmod(0o755)
            env = os.environ.copy()
            env['PATH'] = str(bin_dir) + os.pathsep + env['PATH']
            run = subprocess.run(['bash', str(SCRIPTS / 'collect_pyspy.sh'), 'retail', 'xlsx',
                                  'retail', '1', '49', str(root / 'out'), str(root / 'raw')],
                                 env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(run.returncode, 19, run.stderr)
            self.assertEqual(json.loads((root / 'out/metadata.json').read_text())['rc'], 19)

    def run_fake_native(self, root, return_code, chmod_exit_code=None, existing_data=False):
        scripts, bin_dir = root / 'scripts', root / 'bin'
        scripts.mkdir()
        bin_dir.mkdir()
        out, raw = root / 'out', root / 'raw'
        if existing_data:
            raw.mkdir(parents=True, exist_ok=True)
            (raw / 'retail.data').write_bytes(b'pre-existing fixture bytes')
        runner = root / 'fake-runner.py'
        runner.write_text('# fixture only; never executed\n')
        native = (SCRIPTS / 'collect_native.sh').read_text().replace(
            'RUNNER=/opt/document-bench/bin/run_document_scene_loop.py', f'RUNNER={runner}')
        native = native.replace('open("/opt/document-bench/bin/run_document_scene_loop.py","rb")',
                                f'open({str(runner)!r},"rb")')
        (scripts / 'collect_native.sh').write_text(native)
        for name in ('bounded_perf_export.py', 'tstamp_pipe.py'):
            (scripts / name).write_bytes((SCRIPTS / name).read_bytes())
        (scripts / 'monitor_procs.py').write_text(
            "import os,time\nfrom pathlib import Path\n"
            "while (Path(os.environ['HOTSPOT_MONITOR_STOP'])/'alive').exists(): time.sleep(.01)\n")
        (bin_dir / 'taskset').write_text('#!/bin/sh\nshift 2\nexec "$@"\n')
        (bin_dir / 'taskset').chmod(0o755)
        (bin_dir / 'perf').write_text(
            f'#!{sys.executable}\n'
            'import json,os,sys\nfrom pathlib import Path\n'
            "out=Path(os.environ['TEST_OUT']); raw=Path(os.environ['TEST_RAW'])\n"
            "if sys.argv[1]=='record':\n"
            f"  if {return_code} == 0:\n"
            "    d=out/'runner-results/xlsx/run'; d.mkdir(parents=True)\n"
            "    (d/'summary.json').write_text(json.dumps(dict(requested_iterations=1,completed_iterations=1,successes=1,failures=0)))\n"
            "    (raw/'retail.data').write_bytes(b'fake, not actual perf data')\n"
            "  print('final stdout line',flush=True)\n"
            f"  raise SystemExit({return_code})\n"
            "if sys.argv[1]=='script': print('python 1 1.0: 100 cycles:u:')\n"
            "elif sys.argv[1]=='report': print('tiny fake report')\n"
            "else: raise SystemExit(99)\n")
        (bin_dir / 'perf').chmod(0o755)
        chmod_marker = root / 'chmod-invoked'
        if chmod_exit_code is not None:
            (bin_dir / 'chmod').write_text(
                f'#!/bin/sh\nprintf "%s\\n" "$*" > {chmod_marker}\nexit {chmod_exit_code}\n')
            (bin_dir / 'chmod').chmod(0o755)
        env = os.environ.copy()
        env.update(PATH=str(bin_dir) + os.pathsep + env['PATH'],
                   TEST_OUT=str(out), TEST_RAW=str(raw))
        result = subprocess.run(['bash', str(scripts / 'collect_native.sh'),
                                 'retail', 'xlsx', 'retail', '1', '49', str(out), str(raw)],
                                env=env, capture_output=True, text=True, timeout=15)
        return result, out

    def test_native_collector_propagates_record_failure_and_preserves_stdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            run, out = self.run_fake_native(Path(tmp), 17)
            self.assertEqual(run.returncode, 17, run.stderr)
            metadata = json.loads((out / 'metadata.json').read_text())
            self.assertEqual(metadata['perf_record_status'], 'failed')
            self.assertEqual(metadata['perf_export_status'], 'not_started')
            self.assertIn('final stdout line', (out / 'stdout.log').read_text())

    def test_native_collector_fake_success_reaches_bounded_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            run, out = self.run_fake_native(Path(tmp), 0)
            self.assertEqual(run.returncode, 0, run.stderr)
            metadata = json.loads((out / 'metadata.json').read_text())
            self.assertEqual(metadata['perf_export_status'], 'complete')
            self.assertEqual(metadata['total_samples'], 1)
            self.assertEqual(metadata['monitor_exit_code'], 0)
            self.assertEqual(metadata['stdout_capture_exit_code'], 0)
            self.assertEqual(metadata['perf_data_host_read_permission_status'], 'success')
            self.assertEqual((Path(tmp) / 'raw/retail.data').stat().st_mode & 0o777, 0o644)
            self.assertEqual(len(list(out.glob('native-*.status.json'))), 4)

    def test_native_collector_records_and_propagates_targeted_chmod_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run, out = self.run_fake_native(root, 0, chmod_exit_code=23)
            metadata = json.loads((out / 'metadata.json').read_text())
            self.assertEqual(run.returncode, 1)
            self.assertEqual(metadata['perf_record_status'], 'success')
            self.assertEqual(metadata['perf_data_host_read_permission_status'], 'failed')
            self.assertEqual(metadata['perf_data_host_read_permission_exit_code'], 23)
            self.assertTrue((root / 'chmod-invoked').is_file())
            self.assertEqual(metadata['perf_export_status'], 'not_started')

    def test_native_collector_refuses_to_chmod_or_overwrite_existing_capture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run, out = self.run_fake_native(root, 0, chmod_exit_code=23, existing_data=True)
            self.assertEqual(run.returncode, 73)
            self.assertEqual((root / 'raw/retail.data').read_bytes(), b'pre-existing fixture bytes')
            self.assertFalse((root / 'chmod-invoked').exists())
            self.assertFalse((out / 'metadata.json').exists())


if __name__ == '__main__':
    unittest.main()
