import importlib.util
from pathlib import Path
import sys
import unittest

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
spec=importlib.util.spec_from_file_location('docops_offline_compare',HERE/'compare.py')
compare=importlib.util.module_from_spec(spec);spec.loader.exec_module(compare)


class ComparisonTests(unittest.TestCase):
    def test_cosine_and_invalid_vectors(self):
        self.assertAlmostEqual(compare.cosine([2,3],[2,3]),1.)
        self.assertEqual(compare.cosine([1,0],[0,1]),0.)
        for a,b in [([0,0],[1,2]),([1],[1,2]),([float('nan')],[1])]:
            with self.assertRaises(ValueError):compare.cosine(a,b)

    def test_unknown_weight_retained_and_dso_identity_distinct(self):
        profile={'roi_period':100,'functions':[
            {'dso':'/a/libone.so','function':'[unknown]','period':70},
            {'dso':'/a/libone.so','function':'parse','period':10},
            {'dso':'/b/libtwo.so','function':'parse','period':20}]}
        rows=compare.normalized_functions(profile)
        self.assertEqual(len(rows),2)
        self.assertAlmostEqual(sum(r['share_roi']for r in rows),.3)
        self.assertNotEqual(rows[0]['library'],rows[1]['library'])

    def task(self,name,prefix,quality=True):
        metrics={k:v for k,v in zip(compare.METRICS,[1,3,12,70,15,50,20,10,2])}
        return {'task':name,'format':'pdf','topdown':{'metrics':metrics,'vector':list(metrics.values())+[80.]},
                'resolved_top10':[{'library':'libone.so','function':prefix+str(i)}for i in range(10)],
                'function_qualification':{'function_profile_eligible':quality}}

    def test_similar_bounds_do_not_force_common_functions(self):
        value=compare.pair(self.task('a','first'),self.task('b','second'))
        self.assertAlmostEqual(value['bound_cosine'],1.)
        self.assertEqual(value['observed_resolved_top10_common'],0)
        self.assertEqual(value['observed_resolved_top10_jaccard'],0.)

    def test_partial_symbol_quality_is_not_upgraded_by_overlap(self):
        value=compare.pair(self.task('a','same'),self.task('b','same',quality=False))
        self.assertEqual(value['observed_resolved_top10_common'],10)
        self.assertEqual(value['function_comparison_quality'],'limited_symbols_or_short_list')

    def test_short_function_list_has_no_top10_score(self):
        a=self.task('a','same');a['resolved_top10']=a['resolved_top10'][:2]
        value=compare.pair(a,self.task('b','same'))
        self.assertIsNone(value['observed_resolved_top10_common'])
        self.assertIsNone(value['observed_resolved_top10_jaccard'])

    def test_library_grouping_retains_major_non_python_mechanisms(self):
        self.assertEqual(compare.library('/usr/lib/aarch64-linux-gnu/libpng16.so.16'),'PNG')
        self.assertEqual(compare.library('/usr/lib/libreoffice/program/libsclo.so'),'LibreOffice')
        self.assertEqual(compare.library('/usr/lib/libnew.so'),'libnew.so')


if __name__=='__main__':unittest.main()
