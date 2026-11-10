"""Small numerical counterexamples for the offline scale comparison."""
import itertools
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unified_scaling_analysis as analysis
import operation_comparison as method


class MinimumCoverTests(unittest.TestCase):
    def test_all_minima_and_unattainable_separate(self):
        r = analysis.exact_cover({'a': {1, 2}, 'b': {2, 3}, 'c': {1, 3}}, {1, 2, 3, 4})
        self.assertFalse(r['complete'])
        self.assertIsNone(r['minimum_count'])
        self.assertEqual(r['minimum_for_attainable'], 2)
        self.assertEqual(r['missing'], [4])
        self.assertEqual(r['solutions'], [['a', 'b'], ['a', 'c'], ['b', 'c']])

    def test_equal_and_dominated_candidates_are_not_lost(self):
        r = analysis.exact_cover({'a': {1}, 'b': {1}, 'c': {2}, 'd': {1, 2}}, {1, 2})
        self.assertEqual(r['solutions'], [['d']])
        r = analysis.exact_cover({'a': {1}, 'b': {1}, 'c': {2}}, {1, 2})
        self.assertEqual(r['solutions'], [['a', 'c'], ['b', 'c']])

    def test_empty_goal(self):
        self.assertEqual(analysis.exact_cover({}, set())['minimum_count'], 0)

    def test_random_small_instances_against_exhaustive_subsets(self):
        rng = random.Random(317)
        for _ in range(35):
            pool = {str(i): {f for f in range(6) if rng.random() < .4} for i in range(6)}
            goal = set().union(*pool.values())
            expected = []
            for n in range(7):
                expected = [list(c) for c in itertools.combinations(pool, n)
                            if goal <= set().union(*(pool[t] for t in c))]
                if expected:
                    break
            actual = analysis.exact_cover(pool, goal, limit=100)
            self.assertEqual(actual['minimum_count'], n)
            self.assertEqual(actual['solutions'], expected)


class MetricAndPartitionTests(unittest.TestCase):
    def test_specialized_lo_functions_refined_without_relabelling_generic_containers(self):
        self.assertEqual(analysis.classify_function(dict(library='libsclo.so',
            function='ScHorizontalAttrIterator::InitForNextRow(bool)'))[0], 'LibreOffice·Calc')
        self.assertEqual(analysis.classify_function(dict(library='libooxlo.so',
            function='oox::ppt::PresentationFragmentHandler::importSlideNames()'))[0], 'LibreOffice·OOXML')
        self.assertEqual(analysis.classify_function(dict(library='libvcllo.so',
            function='encode_mcu_DC_refine'))[0], 'LibreOffice·VCL')
        self.assertEqual(analysis.classify_function(dict(library='libsclo.so',
            function='std::_Rb_tree<int>::find()'))[0], 'LibreOffice·其他组件')

    def test_metrics_use_full_paths_not_duplicate_names(self):
        nodes = [dict(path=k, value=i) for i, k in enumerate(method.BOUNDS)]
        nodes += [dict(path=k, value=i+10) for i, k in enumerate((
            'Backend Bound/Core Bound', 'Backend Bound/Memory Bound',
            'Frontend Bound/Fetch Latency Bound', 'Frontend Bound/Fetch Bandwidth Bound'))]
        nodes += [dict(path='Backend Bound/Memory Bound/L1 Bound/Pipeline', value=99),
                  dict(path='Backend Bound/Memory Bound/L2 Bound/Pipeline', value=9)]
        r = analysis.metrics_from_extract(dict(final=dict(header={'IPC': 1.2}, hierarchy=nodes)))
        self.assertEqual(r['IPC'], 1.2)
        self.assertEqual(r['Core Bound'], 10)
        self.assertEqual(r['Fetch Bandwidth Bound'], 13)

    def test_unknown_kept_and_self_reference_marked(self):
        cases = {'a': dict(parent='x',roi_period=100,functions=[
                    dict(library='p',function='old',period=30),
                    dict(library='p',function='new',period=50)]),
                 'b': dict(parent='y',roi_period=100,functions=[
                    dict(library='p',function='old',period=20),
                    dict(library='p',function='new',period=70)])}
        r = analysis.evaluate_selection(cases, {('p','old')},
            {'a': {('p','new')}, 'b': {('p','new')}}, ['a'])['targets']
        self.assertEqual(r['a']['observed_share_roi'], .8)
        self.assertEqual(r['a']['unresolved_share_roi'], .2)
        self.assertEqual(r['a']['not_observed_share_roi'], 0)
        self.assertTrue(r['a']['selected_as_reference'])
        self.assertFalse(r['b']['same_parent_as_selected'])
        self.assertEqual(r['b']['observed_share_roi'], .9)

    def test_missing_metric_fails(self):
        with self.assertRaises(KeyError):
            analysis.metrics_from_extract(dict(final=dict(header={'IPC': 1.0}, hierarchy=[])))

    def test_tool_refinement_preserves_known_unseen_unknown_period_partition(self):
        references = {'OPM': {'functions': [dict(library='old.so',function='seen',share_roi=.5)]}}
        case = dict(roi_period=100,functions=[
            dict(library='old.so',function='seen',period=10,share_roi=.1),
            dict(library='libsclo.so',function='ScHorizontalAttrIterator::InitForNextRow(bool)',period=80,share_roi=.8)])
        result = analysis.classified_hotspot_coverage(references,case)
        self.assertEqual({r['key']:r['period'] for r in result['partition']},
                         {'old_hot':10,'old_low':0,'unseen':80,'unresolved':10})
        self.assertEqual(result['unseen_by_tool'][0]['tool'],'LibreOffice·Calc')
        self.assertEqual(result['unseen_by_tool'][0]['period'],80)


if __name__ == '__main__':
    unittest.main()
