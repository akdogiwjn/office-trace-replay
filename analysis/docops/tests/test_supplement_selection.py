"""Supplementation must deduplicate gains and keep task weights independent."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import supplement_selection as s
import operation_comparison as method
import operation_equivalence_deep as operation
import unified_scaling_sections as scaling


class SelectionTests(unittest.TestCase):
    def fixture(self):
        def row(name,period,mask):
            witnesses={n:dict(kind='exact',library='a.so',function=name)
                       for i,n in enumerate(['a','b']) if mask&(1<<i)}
            return dict(library='a.so',function=name,period=period,mask=mask,witnesses=witnesses)
        return dict(candidates=['a','b'],cases={
            'small':dict(base_period=40,roi_period=100,unresolved_period=10,
                masks={1:20,2:10,3:10,0:10},
                functions=[row('a',20,1),row('b',10,2),row('both',10,3),row('unseen',10,0)]),
            'large':dict(base_period=900,roi_period=1000,unresolved_period=50,
                masks={1:50},functions=[row('big',50,1)])})

    def test_equal_task_mean_is_not_pooled_periods_and_unknown_is_retained(self):
        result=s.evaluate(self.fixture(),['a'],True)
        self.assertEqual(result['cases']['small']['coverage_pct'],70)
        self.assertEqual(result['cases']['large']['coverage_pct'],95)
        self.assertEqual(result['mean_pct'],82.5)
        self.assertEqual(result['cases']['small']['unresolved_pct'],10)
        both=s.evaluate(self.fixture(),['a','b'],True)
        self.assertEqual(both['cases']['small']['added_period'],40)
        self.assertEqual(len(both['cases']['small']['functions']),3)
        with self.assertRaisesRegex(ValueError,'Duplicate'):s.evaluate(self.fixture(),['a','a'])

    def test_search_checks_singletons_and_reports_unreachable_goal(self):
        with patch.object(s,'TARGET_MEAN',80):
            result=s.search(self.fixture())
            self.assertEqual(result['minimum_count'],1)
            self.assertEqual(result['minimum_solutions'][0]['selected'],['a'])
        with patch.object(s,'TARGET_MEAN',90):
            result=s.search(self.fixture())
            self.assertIsNone(result['minimum_count'])
            self.assertEqual(result['minimum_solutions'],[])

    def test_actual_report_pairs_and_operation_witnesses(self):
        data=s.load();scale,_=scaling.load();accounted=operation.load()
        exact=data['modes']['exact'];op=data['modes']['operation']
        self.assertEqual(exact['minimum_count'],2)
        self.assertEqual(exact['minimum_solutions'][0]['selected'],['013','021'])
        self.assertLess(exact['frontier'][1]['mean_pct'],90)
        self.assertEqual(round(exact['primary']['mean_pct'],2),90.14)
        self.assertEqual(op['minimum_count'],0)
        self.assertEqual(round(op['primary']['mean_pct'],2),96.93)
        for mode in ('exact','operation'):
            primary=data['modes'][mode]['primary'];ids=primary['selected']
            keys={method.key(f) for n in ids for f in scale['cases'][n]['functions']}
            proof=operation.witnesses({n:scale['cases'][n] for n in ids})
            old={method.key(f) for c in scale['references'].values() for f in c['functions']}
            for p,c in accounted['cases'].items():
                fs=[f for f in c['functions'] if (method.key(f) not in old if mode=='exact'
                    else f['bucket'] in ('separate_operation','other_resolved'))]
                matched=[f for f in fs if method.key(f) in keys or (mode=='operation' and proof.get(operation.family(f)))]
                row=primary['cases'][p]
                self.assertEqual(row['added_period'],sum(f['period'] for f in matched))
                self.assertEqual(row['roi_period'],c['roi_period'])
                self.assertAlmostEqual(row['unresolved_pct'],c['shares_pct']['unresolved'])
                for f in row['functions']:
                    self.assertIn(f['candidate'],ids)
                    witness=f['witness']
                    self.assertIn((witness['library'],witness['function']),
                                  {method.key(x) for x in scale['cases'][f['candidate']]['functions']})


if __name__=='__main__':unittest.main()
