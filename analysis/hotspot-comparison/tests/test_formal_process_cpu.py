"""Small accounting fixtures for installed-image process-only collection."""
import ast
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


COLLECTOR = module('formal_process_test', 'collect_formal_process_cpu.py')
ACCOUNTING = module('formal_cpu_accounting_test', 'analyze_cpu_measurement.py')


class FormalProcessCpuTests(unittest.TestCase):
    def fixture(self, root, scene='pdf'):
        def write(name, value):
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value))
        dataset = 'opm' if scene == 'pdf' else 'tlc'
        write('installed-identity.json', {'dataset': dataset, 'scene': scene,
              'recipe_sha256': 'a'*64, 'pdf_count': 1 if scene == 'pdf' else None})
        write('clock-anchor.json', {'real_ns': 1_000_000_000, 'mono_ns': 0})
        write('capture.json', {'entry_pid': 25, 'clock_ticks_per_second': 100,
              'whole_command_waited_user_seconds': 0.1, 'whole_command_waited_sys_seconds': 0.01})
        write('output/business_verification.json', {'status': 'success', 'failures': []})
        write(f'workload/{scene}/run/summary.json', {'dataset': dataset,
              'recipe_sha256': 'a'*64, 'requested_iterations': 1,
              'completed_iterations': 1, 'successes': 1, 'failures': 0})
        path = root / f'workload/{scene}/run/iterations.jsonl'
        path.write_text(json.dumps({'finished_at': '1970-01-01T00:00:01.100000+00:00',
                                   'elapsed_seconds': 0.1, 'status': 'success'})+'\n')
        commands = ['/opt/python3 /repo/replay/entry.py',
                    '/opt/python3 /skill/fill_fillable_fields.py' if scene == 'pdf'
                    else '/opt/python3 /workspace/.enhance_workbook.runtime.py',
                    '/usr/bin/pdftoppm input output' if scene == 'pdf'
                    else '/opt/office/program/soffice.bin']
        write('monitor/identity.jsonl', {})
        (root / 'monitor/identity.jsonl').write_text(''.join(json.dumps({
            't_ns': 0, 'pid': pid, 'ppid': ppid, 'comm': comm, 'cmdline': command})+'\n'
            for pid,ppid,comm,command in zip([25,30,31],[1,25,25],['python3','python3','pdftoppm' if scene=='pdf' else 'soffice.bin'],commands)))
        (root / 'monitor/monitor.jsonl').write_text(''.join(json.dumps({
            't_ns': stamp, 'threads': [[25,25,'python3',0,0],
                                      [30,30,'python3',fill,0],
                                      [31,31,'child',render,0]]})+'\n'
            for stamp,fill,render in [(0,0,0),(50_000_000,2,1),(100_000_000,5,3),(200_000_000,55,53)]))

    def test_pdf_shares_use_all_workload_thread_cpu_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            result = COLLECTOR.analyse(root, ACCOUNTING)
            self.assertAlmostEqual(result['denominator_seconds'], 0.08)
            self.assertAlmostEqual(result['role_share']['pdf-fill'], 0.625)
            self.assertAlmostEqual(result['role_share']['pdftoppm'], 0.375)
            self.assertAlmostEqual(sum(result['role_share'].values()), 1)
            self.assertGreater(result['whole_command_observed_cpu_seconds'], result['denominator_seconds'])

    def test_xlsx_alias_and_libreoffice_have_separate_cpu(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root, 'xlsx')
            result = COLLECTOR.analyse(root, ACCOUNTING)
            self.assertAlmostEqual(result['role_share']['helper'], 0.625)
            self.assertAlmostEqual(result['role_share']['libreoffice'], 0.375)

    def test_failed_business_output_cannot_qualify(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            (root / 'output/business_verification.json').write_text(json.dumps({'status':'failed','failures':['bad']}))
            with self.assertRaisesRegex(RuntimeError, 'business_success'):
                COLLECTOR.analyse(root, ACCOUNTING)

    def test_synthetic_probe_is_valid_python(self):
        tree = ast.parse(COLLECTOR.PROBE_SOURCE)
        self.assertTrue(any(isinstance(node, ast.While) for node in tree.body))


if __name__ == '__main__':
    unittest.main()
