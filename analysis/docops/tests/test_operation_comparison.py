import hashlib
import importlib.util
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


if __name__=='__main__':unittest.main()
