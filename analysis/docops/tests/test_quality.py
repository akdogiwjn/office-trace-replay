import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import hashlib

spec=importlib.util.spec_from_file_location('docops_quality',Path(__file__).resolve().parents[1]/'quality.py')
quality=importlib.util.module_from_spec(spec);spec.loader.exec_module(quality)


class QualityTests(unittest.TestCase):
    def test_symbol_limit_does_not_discard_valid_acquisition(self):
        value=quality.function_qualification({'empty_stack_share':0.,'unknown_leaf_symbol_share':.6})
        self.assertTrue(value['stack_eligible'])
        self.assertFalse(value['function_profile_eligible'])
        self.assertEqual(value['status'],'limited')

    def test_unusable_stack_and_invalid_quality_rejected(self):
        self.assertFalse(quality.function_qualification({'empty_stack_share':.3,'unknown_leaf_symbol_share':.1})['stack_eligible'])
        with self.assertRaises(ValueError):
            quality.function_qualification({'empty_stack_share':0.,'unknown_leaf_symbol_share':2.})

    def test_symbols_match_recorded_bytes_and_reject_tampering(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); file=root/'test.debug'; file.write_bytes(b'fixture symbol bytes')
            row=dict(status='downloaded',path=file.name,bytes=file.stat().st_size,
                     sha256=hashlib.sha256(file.read_bytes()).hexdigest(),build_id_verified=True)
            (root/'index.json').write_text(json.dumps({'files':[row]}))
            self.assertEqual(len(quality.verify_symbols(root)['files']),1)
            file.write_bytes(b'different symbol file')
            with self.assertRaisesRegex(ValueError,'hash mismatch'):
                quality.verify_symbols(root)

    def test_symbols_reject_external_path_and_unverified_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for row in [dict(status='downloaded',path='../external.debug',build_id_verified=True),
                        dict(status='downloaded',path='test.debug',build_id_verified=False)]:
                (root/'index.json').write_text(json.dumps({'files':[row]}))
                with self.assertRaisesRegex(ValueError,'invalid symbol provenance'):
                    quality.verify_symbols(root)

    def test_interval_union_excludes_gaps_and_dispatcher_and_conserves_period(self):
        samples=[dict(pid=p,t_ns=t,period=w)for p,t,w in [(2,10,3),(2,20,5),(1,12,7),(2,30,11),(2,40,13)]]
        selected,excluded=quality.select_samples(samples,[(10,20),(30,40)],1)
        self.assertEqual(sum(s['period']for s in selected),14)
        self.assertEqual(excluded,{'outside_workflow':18,'dispatcher_inside_workflow':7})

    def fixture(self,root):
        folder=Path(root)/'runner/031';(folder/'round-001').mkdir(parents=True)
        (folder/'summary.json').write_text(json.dumps(dict(requested=1,completed=1,successes=1,failures=0)))
        record=dict(status='completed',failures=[],environment_restore={'status':'ok'},roi_clock='CLOCK_MONOTONIC',
                    roi_intervals=[dict(start=1.,end=2.)])
        (folder/'round-001/run.json').write_text(json.dumps(record))
        return folder,record

    def test_missing_or_failed_round_cannot_qualify(self):
        with tempfile.TemporaryDirectory()as root:
            folder,record=self.fixture(root)
            self.assertEqual(quality.workload_records(root,'031',1)[2],[(1_000_000_000,2_000_000_000)])
            record['failures']=['failed'];(folder/'round-001/run.json').write_text(json.dumps(record))
            with self.assertRaises(ValueError):quality.workload_records(root,'031',1)

    def test_overlapping_or_wrong_clock_rejected(self):
        for change in [dict(roi_clock='REALTIME'),dict(roi_intervals=[dict(start=2.,end=1.)]),
                       dict(roi_intervals=[dict(start=1.,end=2.),dict(start=1.5,end=3.)])]:
            with tempfile.TemporaryDirectory()as root:
                folder,record=self.fixture(root);record.update(change)
                (folder/'round-001/run.json').write_text(json.dumps(record))
                with self.assertRaises(ValueError):quality.workload_records(root,'031',1)


if __name__=='__main__':unittest.main()
