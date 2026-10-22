"""Small mocks for the fixed missing-mode scheduler; no container is started."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
SCRIPTS = HERE / 'scripts'
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


schedule = load('collect_remaining_hotspot_modes_tested',
                SCRIPTS / 'collect_remaining_hotspot_modes.py')
campaign_tools = schedule.campaign_tools


class FakeCollector:
    def __init__(self, fail_at=None):
        self.calls = []
        self.fail_at = fail_at

    def collect_one(self, plan, cfg, mode, campaign_root):
        task = (cfg['dataset'], mode)
        self.calls.append(task)
        stage = Path(campaign_root) / cfg['dataset'] / ('r1' if mode == 'native' else 'pyspy')
        raw, out = stage / 'raw', stage / 'out'
        raw.mkdir(parents=True)
        out.mkdir()
        if mode == 'native':
            (raw / f"{cfg['dataset']}.data").write_bytes(b'tiny perf fixture')
            (raw / f"{cfg['dataset']}.samples.txt").write_text('tiny parsed fixture\n')
        else:
            (raw / f"{cfg['dataset']}.pyspy.raw").write_text('tiny pyspy fixture\n')
        failed = task == self.fail_at
        record = {
            'status': 'failed' if failed else 'success',
            'reason': 'mock failure' if failed else None,
            'stage_status': {
                'workload': 'failed' if failed else 'success',
                'perf_record': 'success' if mode == 'native' else 'not_applicable',
                'perf_export': 'success' if mode == 'native' else 'not_applicable',
                'parser': 'failed' if failed else 'success',
                'roi': 'failed' if failed else 'success',
                'profile_eligible': not failed,
            },
        }
        (out / 'collection-record.json').write_text(json.dumps(record))
        return not failed


def fixture_plan():
    order = list(dict.fromkeys(d for d, _ in schedule.TASKS))
    return {'order': order, 'modes': ['native', 'pyspy']}


def fixture_configs():
    return {dataset: {'config_id': dataset, 'dataset': dataset}
            for dataset in dict.fromkeys(d for d, _ in schedule.TASKS)}


class RemainingHotspotSchedulerTests(unittest.TestCase):
    def test_task_selection_is_exact_and_never_reincludes_retail_native(self):
        self.assertEqual(schedule.validate_tasks(), (
            ('retail', 'pyspy'), ('hr', 'native'), ('hr', 'pyspy'),
            ('industry_productivity', 'native'), ('industry_productivity', 'pyspy')))
        with self.assertRaises(ValueError):
            schedule.validate_tasks((('retail', 'native'),) + schedule.TASKS)

    def test_success_runs_exact_order_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            campaign = Path(tmp)
            manifest = {'status': 'in_progress', 'completed_modes': []}
            campaign_tools.write(campaign / 'campaign-manifest.json', manifest)
            fake = FakeCollector()
            ok = schedule.execute_tasks(fixture_plan(), fixture_configs(), campaign,
                                        manifest, collector=fake)
            self.assertTrue(ok)
            self.assertEqual(fake.calls, list(schedule.TASKS))
            self.assertEqual([(x['dataset'], x['mode']) for x in manifest['completed_modes']],
                             list(schedule.TASKS))
            self.assertEqual(manifest['status'], 'complete')
            self.assertTrue(all(x['profile_eligible'] for x in manifest['completed_modes']))

    def test_failure_stops_and_marks_only_later_selected_tasks_not_started(self):
        with tempfile.TemporaryDirectory() as tmp:
            campaign = Path(tmp)
            manifest = {'status': 'in_progress', 'completed_modes': []}
            campaign_tools.write(campaign / 'campaign-manifest.json', manifest)
            fake = FakeCollector(fail_at=('hr', 'native'))
            ok = schedule.execute_tasks(fixture_plan(), fixture_configs(), campaign,
                                        manifest, collector=fake)
            self.assertFalse(ok)
            self.assertEqual(fake.calls, [('retail', 'pyspy'), ('hr', 'native')])
            self.assertEqual([(x['dataset'], x['mode']) for x in manifest['completed_modes']],
                             [('retail', 'pyspy'), ('hr', 'native')])
            self.assertFalse(manifest['completed_modes'][-1]['profile_eligible'])
            self.assertEqual([(x['dataset'], x['mode']) for x in manifest['not_started']],
                             list(schedule.TASKS[2:]))

    def test_recovery_record_is_hash_checked_as_reference_not_scheduled_work(self):
        with tempfile.TemporaryDirectory(dir=HERE / 'tests') as tmp:
            root = Path(tmp)
            stage = root / 'retail/r1'
            out = stage / 'out'
            out.mkdir(parents=True)
            record_path = out / 'recovery-record.json'
            record = {
                'status': 'offline_reparse_complete', 'final_profile_eligible': True,
                'archive_integrity': {
                    'status': 'complete', 'index_write_status': 'success',
                    'required_raw_sha256_complete': True,
                    'index_path': str(stage / 'sha256-index.json'),
                },
                'source_artifacts': {'perf_data': {'sha256': 'fixture-perf-hash'}},
            }
            record_path.write_text(json.dumps(record))
            record_hash = campaign_tools.sha(record_path)
            index = {'files': [
                {'path': 'out/recovery-record.json', 'status': 'hashed', 'sha256': record_hash},
                {'path': 'raw/retail.data', 'status': 'hashed', 'sha256': 'fixture-perf-hash'},
            ]}
            (stage / 'sha256-index.json').write_text(json.dumps(index))
            reference = schedule.recovery_reference(record_path)
            self.assertTrue(reference['profile_eligible'])
            self.assertIn('not a task completed', reference['relation'])
            self.assertEqual(reference['record_sha256'], record_hash)


if __name__ == '__main__':
    unittest.main()
