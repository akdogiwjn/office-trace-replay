from collections import Counter
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from xlsx_extension import PLAN,DATASETS
from finalize_five_repeats import combine_topdown


class ExtensionPlanTests(unittest.TestCase):
    def test_exact_32_additional_runs_without_pdf_or_first_repeat(self):
        self.assertEqual(len(PLAN),32)
        self.assertEqual(set(t['dataset_id'] for t in PLAN),set(DATASETS))
        self.assertEqual(set(t['repeat'] for t in PLAN),{2,3,4,5})
        counts=Counter((t['dataset_id'],t['profiler']) for t in PLAN)
        self.assertEqual(set(counts.values()),{4})
        self.assertEqual(len(counts),8)
        self.assertEqual(len({tuple(t.values()) for t in PLAN}),32)

    def test_consolidation_reuses_nineteen_originals_and_requires_new_unique_captures(self):
        datasets=('opm','irs_w4','sba1919',*DATASETS)
        original=[dict(dataset_id=ds,repeat=r,raw=f'{ds}-{r}',summary='summary',summary_sha256='hash')
                  for ds in datasets for r in (range(1,6) if ds in datasets[:3] else [1])]
        added=[dict(t,raw=f'{t["dataset_id"]}-{t["repeat"]}-{t["profiler"]}',summary='summary',summary_sha256='hash')
               for t in PLAN]
        result=combine_topdown(original,added)
        self.assertEqual(len(result),35)
        self.assertEqual(sum(r['reused'] for r in result),19)
        self.assertTrue(all('reused' not in r for r in original))
        with self.assertRaises(ValueError):combine_topdown(original,added[:-1])
        with self.assertRaises(ValueError):combine_topdown(original,[*added,added[-1]])
        bad=[dict(r) for r in added]
        bad[-1]['raw']=original[0]['raw']
        with self.assertRaises(ValueError):combine_topdown(original,bad)


if __name__=='__main__':unittest.main()
