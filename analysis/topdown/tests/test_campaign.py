import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from campaign import PLAN, aggregate
from capture import validate_business
from summarize import METRICS
from workload_entry import legacy


class CampaignTests(unittest.TestCase):
    def test_plan_and_single_repeat_statistics(self):
        self.assertEqual(len(PLAN),19)
        for ds in ('opm','irs_w4','sba1919'):
            self.assertEqual([r for name,r in PLAN if name==ds],[1,2,3,4,5])
        row=dict(dataset_id='tlc',metrics=dict.fromkeys(METRICS,1),idle_pct=80,
            roi_seconds=10,startup_envelope_upper_seconds=1,tail_envelope_upper_seconds=.01,
            arithmetic=dict(debug_not_counted_events=[]))
        result=aggregate([row])['tlc']['statistics']['IPC']
        self.assertIsNone(result['sample_standard_deviation'])
        self.assertIsNone(result['cv_percent'])
        other=dict(row,metrics=dict.fromkeys(METRICS,3))
        result=aggregate([row,other])['tlc']['statistics']['IPC']
        self.assertEqual(result['mean'],2)
        self.assertAlmostEqual(result['sample_standard_deviation'],2**.5)

    def test_legacy_validation_and_post_roi_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);workspace=out/'workspace';(workspace/'output').mkdir(parents=True)
            (workspace/'output/business_verification.json').write_text(json.dumps(dict(status='success',failures=[])))
            folder=out/'runner/pdf/run';folder.mkdir(parents=True)
            (folder/'summary.json').write_text(json.dumps(dict(requested_iterations=1,
                completed_iterations=1,successes=1,failures=0,workspace=str(workspace))))
            original=Path.read_text
            def read(path,*a,**kw):
                if str(path)=='/evidence/container-inspect.before.json':return '[{"Image":"sha256:test"}]'
                return original(path,*a,**kw)
            with patch.object(Path,'read_text',read):result=validate_business(out,'opm')
            self.assertEqual(result['actual_image_id'],'sha256:test')
            self.assertTrue((out/'legacy-output/business_verification.json').is_file())

    def test_legacy_wraps_original_once_and_stops_on_exception(self):
        from types import SimpleNamespace
        calls=[]
        gate=SimpleNamespace(begin=lambda:calls.append('begin'),
            end=lambda m:calls.append('end'),log=lambda *a,**kw:None)
        def iteration(*a):calls.append('original');raise RuntimeError('workload failure')
        runner=SimpleNamespace(run_iteration=iteration,__file__='runner.py')
        runner.main=lambda:runner.run_iteration()
        entry=SimpleNamespace(configure_runtime=lambda:None,validate=lambda **k:None,restore_skill_links=lambda:None)
        with patch('workload_entry.load_module',side_effect=[entry,runner]),patch.object(sys,'argv',[]):
            with self.assertRaisesRegex(RuntimeError,'workload failure'):legacy(gate,Path('/out'),'opm')
        self.assertEqual(calls,['begin','original','end'])


if __name__=='__main__':unittest.main()
