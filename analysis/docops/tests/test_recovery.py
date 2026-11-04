import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE.parent/'hotspots'));sys.path.insert(0,str(HERE))
import native_adapter


class RecoveryTests(unittest.TestCase):
    def test_full_offline_recovery_preserves_before_hashes_and_physical_leaf(self):
        with tempfile.TemporaryDirectory()as folder:
            root=Path(folder);original=root/'original';out=root/'results';original.mkdir();out.mkdir()
            before_text='proc 10/10 1.100000000: 10 cycles:u:\n\tab [unknown] (/lib/libx.so)\n\n'
            after_text=before_text.replace('[unknown]','some_function+0x1')
            (original/'samples.txt').write_text(before_text)
            (original/'counter-samples.txt').write_text('10/10 1.100000000: 10 cycles:u:\n')
            (original/'perf.data').write_bytes(b'fake data; exporter is mocked')
            (original/'collection.json').write_text(json.dumps({'status':'passed','task':'test','loops':1}))
            (original/'sha256-index.json').write_text('{}')
            (original/'measurement-ready.json').write_text('{"pid":99}')
            (original/'identities.jsonl').write_text(json.dumps({'event':'identity','t_ns':1000000000,'pid':10,'comm':'proc','argv':['tool']})+'\n'+json.dumps({'event':'monitor_end','t_ns':2000000000})+'\n')
            (original/'perf-record.stderr').write_text('')
            (original/'perf-report.txt').write_text('Aggregated stats:\n SAMPLE events: 1\ncycles:u stats:\n')
            rounds=original/'runner/test/round-001';rounds.mkdir(parents=True)
            (rounds.parent/'summary.json').write_text(json.dumps({'requested':1,'completed':1,'successes':1,'failures':0}))
            (rounds/'run.json').write_text(json.dumps({'status':'completed','failures':[],'environment_restore':{'status':'ok'},'roi_clock':'CLOCK_MONOTONIC','roi_intervals':[{'start':1.,'end':2.}]}))
            samples=native_adapter.parse(original/'samples.txt');native_adapter.attribute(samples,original/'identities.jsonl')
            baseline=native_adapter.profile(samples,(1000000000,2000000000));baseline.update(all_recorded_samples=1,all_recorded_period=10,excluded_period={'outside_workflow':0,'dispatcher_inside_workflow':0})
            (original/'profile.json').write_text(json.dumps(baseline))
            stub=types.ModuleType('native_capture_helpers')
            stub.bounded=lambda argv,target:target.write_text(after_text)
            stub.write=lambda path,value:path.write_text(json.dumps(value))
            spec=importlib.util.spec_from_file_location('docops_recovery_test',HERE/'recover_perf.py')
            with patch.dict(sys.modules,{'native_capture_helpers':stub}):
                module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            def mapped_path(value):
                return original if value=='/original'else out if value=='/results'else Path(value)
            with patch.object(module,'Path',side_effect=mapped_path),patch.object(module,'verify_symbols',return_value={}),patch('subprocess.check_output',return_value='perf fixture'),patch.object(sys,'argv',['recover_perf.py','--allow-limited']),contextlib.redirect_stdout(io.StringIO()):
                code=module.main()
            record=json.loads((out/'recovery-record.json').read_text())
            self.assertEqual(code,0,record.get('error'))
            self.assertTrue(record['original_evidence_unchanged'])
            self.assertTrue(record['dso_parser_correction']['all_original_sample_keys_addresses_and_dsos_verified'])
            self.assertEqual((original/'samples.txt').read_text(),before_text)
            self.assertEqual(record['quality_after']['unknown_leaf_symbol_share'],0)


if __name__=='__main__':unittest.main()
