from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pdf_repeats import merge_profiles,ranks


def fixture(period,function='alpha',dso='/lib/libpython.so'):
    value=dict(dataset_id='opm',image_id='frozen',pdf_applicant_count=10,
        roi_period=period,roi_samples=5,total_period=period+3,total_samples=6,
        outside_roi_period=3,outside_roi_samples=1,
        processes=[dict(script='tool.py',period=period)],
        libraries=[dict(dso=dso,period=period)],
        functions=[dict(dso=dso,function=function,period=period)],
        contexts=[dict(script='tool.py',dso=dso,function=function,period=period)],
        quality=dict(empty_stack_share=0,unknown_categories_may_overlap=True))
    for name in ('processes','libraries','functions','contexts'):
        for row in value[name]:row['share_roi']=row['period']/period
    return value


class PdfRepeats(unittest.TestCase):
    def test_merge_weights_periods_not_mean_percentages(self):
        result=merge_profiles([fixture(10),fixture(90,'beta')])
        shares={f['function']:f['share_roi'] for f in result['functions']}
        self.assertEqual(shares,{'beta':.9,'alpha':.1})
        self.assertEqual((result['roi_period'],result['outside_roi_period'],result['total_period']),(100,6,106))

    def test_unknown_period_stays_in_denominator(self):
        result=merge_profiles([fixture(10),fixture(90,'[unknown]','[unknown]')])
        self.assertEqual(result['roi_period'],100)
        self.assertEqual(sum(f['period'] for f in result['functions']),100)
        self.assertEqual(next(f['share_roi'] for f in result['functions'] if f['function']=='alpha'),.1)

    def test_reject_mixed_image_or_dataset_and_incomplete_layer(self):
        a=fixture(10)
        for field,value in [('image_id','other'),('dataset_id','irs_w4'),('pdf_applicant_count',1)]:
            b=fixture(90);b[field]=value
            with self.assertRaises(ValueError):merge_profiles([a,b])
        b=fixture(90);b['functions'][0]['period']=89
        with self.assertRaises(ValueError):merge_profiles([a,b])

    def test_rank_frequency_uses_each_repetition(self):
        values=[fixture(10),fixture(90,'beta')]
        result=ranks(values,merge_profiles(values))
        self.assertEqual(result['merged_top20'][0]['function'],'beta')
        self.assertEqual(result['merged_top20'][0]['top10_appearance_count'],1)
        self.assertEqual(result['pairwise_top10_common_counts'],[0])


if __name__=='__main__':unittest.main()
