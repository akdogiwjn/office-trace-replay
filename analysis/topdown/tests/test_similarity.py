import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import compare_similarity as c
import report_methods


class SimilarityTests(unittest.TestCase):
    def profile(self,keys):
        return dict(functions=[dict(library=lib,function=name,share_roi=(20-i)/300)
                               for i,(lib,name) in enumerate(keys)])

    def stats(self):
        return {ds:dict(statistics={m:dict(mean=1) for m in c.VECTOR}) for ds in ('a','b')}

    def test_known_cosine_and_mixed_unit_distance(self):
        self.assertEqual(c.cosine([1,0],[0,1]),0)
        self.assertEqual(c.cosine([1,2],[2,4]),1)
        self.assertEqual(c.vector_distance([0,0],[3,4]),5)
        for a,b in (([0,0],[1,1]),([1],[1,2]),([math.nan],[1]),([math.inf],[1])):
            with self.assertRaises(ValueError):c.cosine(a,b)

    def test_jaccard_uses_union_and_library_identity(self):
        tools=c.hotspot_tools()
        a=[('libpython',f'f{i}') for i in range(10)]
        b=[*a[:9],('zlib','f9')]
        profiles={'a':self.profile(a),'b':self.profile(b)}
        r=c.pair_result('a','b',self.stats(),profiles,tools)
        self.assertEqual(r['common_top10_count'],9)
        self.assertEqual(r['union_top10_count'],11)
        self.assertAlmostEqual(r['hotspot_jaccard'],9/11)
        self.assertEqual(r['bound_cosine'],1)
        for f in profiles['b']['functions']:f['share_roi']*=.01
        self.assertEqual(c.pair_result('a','b',self.stats(),profiles,tools)['hotspot_jaccard'],r['hotspot_jaccard'])

    def test_idle_and_children_not_counted_in_bound_cosine(self):
        tools=c.hotspot_tools();keys=[('libpython',f'f{i}') for i in range(10)]
        stats=self.stats();stats['b']['statistics']['idle_pct']['mean']=90
        stats['b']['statistics']['Memory Bound']['mean']=80
        r=c.pair_result('a','b',stats,{'a':self.profile(keys),'b':self.profile(keys)},tools)
        self.assertEqual(r['bound_cosine'],1)
        self.assertGreater(r['raw_euclid_auxiliary'],100)

    def test_unresolved_or_duplicate_functions_do_not_complete_top10(self):
        tools=c.hotspot_tools()
        keys=[('libpython',f'f{i}') for i in range(9)]
        for extra in (('unknown','[unknown]'),('libpython','0xabcdef1234'),keys[0]):
            with self.assertRaises(ValueError):c.top10_set(self.profile([*keys,extra]),tools)

    def test_binding_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'input.json';path.write_text('{"status":"success"}')
            binding=dict(path=path.name,sha256=c.sha(path))
            with patch.object(c,'ROOT',Path(tmp)):
                self.assertEqual(c.checked(binding)['status'],'success')
                path.write_text('{"status":"failed"}')
                with self.assertRaisesRegex(ValueError,'hash mismatch'):c.checked(binding)

    def test_report_vector_example_has_exact_ten_dimensional_order(self):
        datasets=('opm','irs_w4','sba1919','tlc','hr_metro','egrid','industry_productivity')
        stats={ds:dict(statistics={m:dict(mean=i+.25) for i,m in enumerate(c.VECTOR)}) for ds in datasets}
        keys=[('libpython',f'f{i}') for i in range(10)]
        profiles={ds:self.profile(keys) for ds in datasets}
        result=dict(statistics=stats,pairs=[c.pair_result(a,b,stats,profiles,c.hotspot_tools()) for a,b in c.PAIRS])
        text='\n'.join(c.vector_section(result))
        line=next(line for line in text.splitlines() if line.startswith('TLC 十维'))
        self.assertEqual(json.loads(line.split(' = ',1)[1]),[i+.25 for i in range(10)])
        bound=next(line for line in text.splitlines() if line.startswith('TLC Bound'))
        self.assertEqual(json.loads(bound.split(' = ',1)[1]),[1.25,2.25,3.25,4.25])
        self.assertIn('CV=100×s/|μ|',text)
        self.assertIn('权重不进入 Jaccard',text)

    def test_measurement_text_distinguishes_scope_and_log_level(self):
        datasets=('opm','irs_w4','sba1919','tlc','hr_metro','egrid','industry_productivity')
        methods=dict(host=dict(kernel='test-kernel'),devkit=dict(tool=dict(version='26.0.RC1'),
            cpu_identity=dict(midr_el1='midr',board_name='board')),perf_version='perf-test',
            image_id='image-test',replay_environment=dict(python='3.12.3',packages={},libreoffice='25.8',poppler='23.12'),
            topdown_captures=[dict(dataset_id=ds,roi_seconds=10,startup_envelope_upper_seconds=1.1,
                tail_envelope_upper_seconds=.01) for ds in datasets],hotspot_captures=[dict(archive_files_checked=1)])
        verified=dict(archive_checks_recorded=[dict(checked_files=1)],qualified_runtime_files_unchanged=22,
            old_workload_files_unchanged=43)
        text=report_methods.section(methods,verified)
        for token in ('进程树','按 CPU 统计','不是先找一个已有 Python PID 再 attach',
                      '`-l 0` 开启 debug 日志','本次未显式传 `-r`','dwarf,16384','PmuRead','SIGINT',
                      '不是严格裁剪后的循环计数','guest 已包含','多重集合逐样本核对'):
            self.assertIn(token,text)
        self.assertNotIn('`-l 0` 保持默认全权限',text)


if __name__=='__main__':unittest.main()
