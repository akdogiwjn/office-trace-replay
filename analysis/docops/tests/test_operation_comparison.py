import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('docops_operation_comparison',Path(__file__).resolve().parents[1]/'operation_comparison.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class OperationComparisonTests(unittest.TestCase):
    def case(self,metrics,rows):
        return dict(task='fixture',metrics=dict(zip(module.METRICS,metrics)),functions=rows)

    def rows(self,keys):
        return [dict(library=dso,function=name,period=1,share_roi=.01) for dso,name in keys]

    def test_bound_tv_is_half_l1_and_cosine_is_auxiliary(self):
        a=self.case([1.,3.,15.,67.,15.,50.,17.,10.,5.],self.rows([('a.so',str(i)) for i in range(10)]))
        b=self.case([.8,3.,21.,61.,15.,44.,17.,16.,5.],a['functions'])
        row=module.compare_pair(a,b)
        self.assertAlmostEqual(row['bound_total_variation_pp'],6.)
        self.assertAlmostEqual(row['ipc_relative_change_pct'],-20.)
        self.assertGreater(row['bound_cosine_auxiliary'],.99)
        self.assertEqual(row['shared_top10_count'],10)

    def test_reference_list_share_looks_beyond_target_top10(self):
        a=self.case([1.,3.,15.,67.,15.,50.,17.,10.,5.],self.rows([('a.so',str(i)) for i in range(10)]))
        b=self.case(list(a['metrics'].values()),self.rows([('b.so',str(i)) for i in range(10)])+a['functions'])
        row=module.compare_pair(a,b)
        self.assertEqual(row['shared_top10_count'],0)
        self.assertAlmostEqual(row['baseline_top10_share_in_target'],.1)

    def test_function_identity_keeps_owner_and_full_name(self):
        raw=dict(roi_period=100,functions=[
            dict(dso='/lib/a.so',function='f',period=20),
            dict(dso='/other/a.so',function='f',period=10),
            dict(dso='/lib/b.so',function='f',period=30),
            dict(dso='/lib/a.so',function='f.isra.0',period=15),
            dict(dso='[unknown]',function='[unknown]',period=25)])
        rows=module.functions(raw)
        self.assertEqual(sum(r['period'] for r in rows),75)
        self.assertEqual(len(rows),3)
        with self.assertRaisesRegex(ValueError,'conserve'):
            module.functions(dict(raw,roi_period=90))

    def test_append_preserves_exact_original_bytes(self):
        original=b'# original\n\ncontents\n'
        digest=hashlib.sha256(original).hexdigest()
        self.assertEqual(module.original_prefix(original,digest),original)
        self.assertEqual(module.original_prefix(original+module.BEGIN.encode()+b'\nnew section',digest),original)
        with self.assertRaisesRegex(ValueError,'prefix changed'):
            module.original_prefix(b'# modified\n'+original,digest)

    def test_complete_reference_presence_deduplicates_union_and_keeps_unknown(self):
        a=dict(library='a.so',function='shared',period=40,share_roi=.4)
        b=dict(library='a.so',function='second',period=10,share_roi=.1)
        c=dict(library='b.so',function='shared',period=30,share_roi=.3)
        refs={'OPM':{'functions':[a]},'TLC':{'functions':[a,b]}}
        result=module.function_presence(refs,dict(roi_period=100,functions=[a,b,c]))
        self.assertEqual(result['OPM']['observed_period'],40)
        self.assertEqual(result['TLC']['observed_period'],50)
        union=result['OPM+TLC']
        self.assertEqual(union['observed_period'],50)
        self.assertEqual(union['not_observed_period'],30)
        self.assertEqual(union['unresolved_period'],20)
        self.assertEqual(union['reference_function_count'],2)
        self.assertEqual(union['not_observed_top20'],[c])

    def test_presence_checks_entire_list_and_rejects_nonconserving_target(self):
        old=self.rows([('a.so',str(i)) for i in range(12)])
        target=dict(library='a.so',function='11',period=80,share_roi=.8)
        refs={'OPM':{'functions':old},'TLC':{'functions':[]}}
        self.assertEqual(module.function_presence(refs,dict(roi_period=100,functions=[target]))['OPM']['observed_period'],80)
        with self.assertRaisesRegex(ValueError,'exceeds'):
            module.function_presence(refs,dict(roi_period=10,functions=[target]))
        with self.assertRaisesRegex(ValueError,'duplicate'):
            module.function_presence(refs,dict(roi_period=200,functions=[target,target]))

    def test_reader_report_keeps_all_tasks_four_bound_changes_and_figure_notes(self):
        result=json.loads((module.ROOT/module.DEFAULT_OUTPUT/'comparison.json').read_text())
        report=module.main_section(result,module.ROOT/module.DEFAULT_OUTPUT)
        self.assertIn('| 误推测 Δpp | 前端 Δpp | 后端 Δpp | 有效完成 Δpp |',report)
        self.assertIn('共同函数数量少，不一定表示共同计算的权重小',report)
        self.assertEqual(report.count('![图 7-'),12)
        self.assertEqual(report.count('**读图：**'),12)
        for task in result['tasks']:
            self.assertIn('/'+task+'-bounds.svg)',report)
        self.assertIn('### 7.6 最终判断',report)
        self.assertIn('旧两例合并已见',report)
        self.assertIn('016 再次重算属于已有机制重复执行',report)


if __name__=='__main__':unittest.main()
