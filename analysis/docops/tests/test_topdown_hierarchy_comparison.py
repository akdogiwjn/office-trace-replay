"""Counterexamples for nonoverlapping Topdown profile comparisons."""
from pathlib import Path
import math
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import topdown_hierarchy_comparison as m


def report(vector):
    nodes=[dict(path=k,value=v) for k,v in zip(m.PATHS,vector)]
    nodes.extend([dict(path='Bad Speculation',value=vector[1]+vector[2]),
        dict(path='Frontend Bound',value=vector[3]+vector[4]),
        dict(path='Backend Bound',value=vector[5]+vector[6])])
    return dict(final=dict(hierarchy=nodes))


class TopdownProfileTests(unittest.TestCase):
    def test_frontier_contains_no_parent_and_child(self):
        self.assertEqual(len(set(m.PATHS)),7)
        for a in m.PATHS:
            for b in m.PATHS:
                self.assertFalse(b.startswith(a+'/'))

    def test_backend_internal_change_is_visible_when_parent_is_unchanged(self):
        a=[20,4,1,4,1,60,10]
        b=[20,4,1,4,1,30,40]
        self.assertEqual(sum(a[-2:]),sum(b[-2:]))
        self.assertAlmostEqual(m.distance(a,b),math.sqrt(30**2+30**2))
        self.assertEqual(m.distance(a,a),0)
        self.assertEqual(m.distance(a,b),m.distance(b,a))

    def test_vector_rejects_duplicate_missing_or_nonconserving_metrics(self):
        a=[20,4,1,4,1,60,10]
        valid=report(a)
        self.assertEqual(m.vector_from_extract(valid)[0],a)
        valid['final']['hierarchy'].append(dict(path='Retiring',value=20))
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            m.vector_from_extract(valid)
        invalid=report(a);invalid['final']['hierarchy'].pop(0)
        with self.assertRaises(KeyError):
            m.vector_from_extract(invalid)
        with self.assertRaisesRegex(ValueError,'conserve'):
            m.vector_from_extract(report([20,4,1,4,1,60,20]))

    def test_nonfinite_values_fail_instead_of_becoming_similarity(self):
        with self.assertRaises(ValueError):m.distance([float('nan')],[1])
        with self.assertRaises(ValueError):m.distance([-1],[1])

    def test_ipc_is_separate_from_profile_distance(self):
        a=dict(task='old',vector=[20,4,1,4,1,60,10],IPC=1)
        b=dict(task='new',vector=a['vector'],IPC=2)
        result=m.compare(a,b)
        self.assertEqual(result['euclidean_pp'],0)
        self.assertEqual(result['ipc_relative_change_pct'],100)
        self.assertAlmostEqual(result['cosine_similarity'],1)

    def test_report_example_and_zero_vector_rejection(self):
        a=dict(task='old',vector=[20,4,1,15,5,45,10],IPC=1)
        b=dict(task='new',vector=[20,4,1,10,5,50,10],IPC=1)
        pair=m.compare(a,b)
        self.assertAlmostEqual(pair['euclidean_pp'],math.sqrt(50))
        self.assertAlmostEqual(pair['cosine_similarity'],0.9933032834313805)
        self.assertAlmostEqual(m.compare(b,a)['cosine_similarity'],pair['cosine_similarity'])
        with self.assertRaisesRegex(ValueError,'nonzero'):
            m.compare(dict(a,vector=[0]*7),b)


if __name__=='__main__':unittest.main()
