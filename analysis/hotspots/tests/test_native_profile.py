import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import native_profile as p
import collect_native as c
import legacy_capture as legacy


class NativeProfile(unittest.TestCase):
    def test_legacy_iteration_observer_preserves_result_and_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'roi.jsonl';calls=[]
            def original(value):calls.append(value);return {'status':'success','value':value}
            result=legacy.observe_iteration(original,'tlc',path)(7)
            self.assertEqual(result,{'status':'success','value':7});self.assertEqual(calls,[7])
            self.assertLess(*p.roi(path))
            failed=Path(temp)/'failed.jsonl'
            def fail():raise RuntimeError('unchanged')
            with self.assertRaisesRegex(RuntimeError,'unchanged'):
                legacy.observe_iteration(fail,'opm',failed)()
            self.assertLess(*p.roi(failed))

    def test_dataset_dispatch_keeps_old_and_new_paths_separate(self):
        old=c.workload_arguments('opm','/out')
        self.assertIn('legacy_capture.py',old[2]);self.assertIn('-s',old)
        new=c.workload_arguments('egrid','/out')
        self.assertTrue(new[1].endswith('/agent/replay.py'))
        self.assertNotIn('legacy_capture.py',' '.join(new))

    def test_capture_quality_accepts_diagnostic_note(self):
        result=c.capture_quality('captured', 'Aggregated stats:\n SAMPLE events: 10\n', '')
        self.assertEqual(result['aggregated_sample_events'],10)
        self.assertEqual(result['export_warnings'],'')
        self.assertIn('ROI attribution',result['note'])

    def test_loss_capability_is_not_a_loss_record(self):
        d=p.loss_diagnostics('captured 10 samples', '# read_format = ID|LOST\nAggregated stats:\n SAMPLE events: 10\ncycles:u stats:\n SAMPLE events: 10\n')
        self.assertEqual(d['aggregated_sample_events'],10)
        self.assertEqual(d['reported_lost_records'],0)
        d=p.loss_diagnostics('lost 3 chunks', 'Aggregated stats:\n LOST events: 2\n LOST_SAMPLES events: 1\n SAMPLE events: 10\n')
        self.assertEqual((d['reported_lost_records'],d['reported_lost_sample_records'],d['perf_record_reported_lost_chunks']),(2,1,3))

    def test_spaces_cpp_and_nanosecond_timestamp(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'samples'
            path.write_text(' CUPSManager cup 12/13 100.000000123: 17 cycles:u: \n'
                            '\t 123 std::vector<int>::push_back(int const&)+0xab (/lib/cpp.so)\n\n')
            sample=p.parse(path)[0]
            self.assertEqual((sample['comm'],sample['pid'],sample['tid'],sample['t_ns']),('CUPSManager cup',12,13,100000000123))
            self.assertEqual(sample['frames'][0]['symbol'],'std::vector<int>::push_back(int const&)')

    def test_counter_crosscheck_detects_duplicate_or_missing_samples(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'counter'
            line='12/13 100.000000123: 17 cycles:u:\n'
            path.write_text(line)
            samples=[dict(pid=12,tid=13,t_ns=100000000123,period=17,event='cycles:u')]
            self.assertEqual(p.crosscheck(samples,path)['period'],17)
            path.write_text(line*2)
            with self.assertRaises(ValueError): p.crosscheck(samples,path)

    def test_roi_partition_unknown_leaf_and_period_conservation(self):
        samples=[dict(pid=1,tid=1,t_ns=t,period=w,event='cycles:u',script='a.py',identity_basis='observed_identity_window',
                      frames=frames) for t,w,frames in (
                          (9,3,[]),(10,7,[dict(symbol='[unknown]',dso='[unknown]'),dict(symbol='caller',dso='/lib/known.so')]),
                          (11,13,[dict(symbol='add',dso='/lib/known.so')]),(12,5,[]))]
        d=p.profile(samples,(10,12))
        self.assertEqual((d['roi_period'],d['outside_roi_period'],d['total_period']),(20,8,28))
        self.assertEqual(d['quality']['unknown_leaf_dso_share'],7/20)
        self.assertEqual(d['quality']['unknown_leaf_symbol_share'],7/20)
        self.assertEqual(sum(x['period'] for x in d['functions']),20)
        self.assertEqual(d['libraries'][0]['dso'],'/lib/known.so')

    def test_bad_header_and_inline_export_are_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'samples'
            for text in ('garbled 100.000000123: 17 cycles:u:\n',
                         'python 1/1 100.1: 17 cycles:u:\n\t 123 inline_func (inlined)\n'):
                path.write_text(text)
                with self.assertRaises(ValueError): p.parse(path)

    def test_roi_requires_one_complete_pair(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'roi'
            events=[dict(scope='loop_including_reset',event=e,monotonic_ns=n) for e,n in [('start',5),('end',10)]]
            path.write_text('\n'.join(json.dumps(e) for e in events))
            self.assertEqual(p.roi(path),(5,10))
            path.write_text(json.dumps(events[0]))
            with self.assertRaises(ValueError): p.roi(path)

    def test_script_operand_is_not_a_data_argument(self):
        self.assertEqual(p.script(['/opt/venv/bin/python','-B','input/check.py','enhance.py']),'check.py')
        self.assertEqual(p.script(['python3','-c','print("foo.py")']),'python-inline-or-module')

    def test_identity_uses_observed_comm_and_marks_bounded_inference(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'identities'
            events=[dict(event='identity',t_ns=20_000_000,pid=1,comm='python',argv=['python','actual.py']),
                    dict(event='monitor_end',t_ns=30_000_000)]
            path.write_text('\n'.join(json.dumps(e) for e in events))
            samples=[dict(pid=1,comm='python',t_ns=15_000_000),dict(pid=1,comm='other',t_ns=25_000_000)]
            p.attribute(samples,path)
            self.assertEqual(samples[0]['script'],'actual.py')
            self.assertEqual(samples[0]['identity_basis'],'first_observation_within_10ms')
            self.assertEqual(samples[1]['identity_basis'],'unresolved')

    def test_export_refuses_existing_artifact_before_start(self):
        with tempfile.TemporaryDirectory() as t:
            output=Path(t)/'samples'; stderr=Path(str(output)+'.stderr'); stderr.write_text('keep')
            with patch.object(c.subprocess,'Popen') as start:
                with self.assertRaises(ValueError): c.bounded(['perf','script'],output)
                start.assert_not_called()
            self.assertEqual(stderr.read_text(),'keep')


if __name__=='__main__': unittest.main()
