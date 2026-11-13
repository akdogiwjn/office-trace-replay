"""Counterexamples for disjoint operation-equivalence accounting."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import operation_equivalence as m


def sample(tool,name,period=10,library='sample.so'):
    return dict(tool=tool,function=name,period=period,share_roi=period/100,library=library)


class OperationEquivalenceTests(unittest.TestCase):
    def test_jpeg_is_separate_from_old_png(self):
        for f in (sample('JPEG','jpeg_write_scanlines'),sample('LibreOffice·VCL','encode_mcu_AC_first')):
            self.assertIsNone(m.same_operation(f))
            self.assertEqual(m.separate_operation(f,'PPT'),'JPEG')
        self.assertEqual(m.same_operation(sample('PNG','png_write_find_filter')),'PNG 编解码')

    def test_rescaling_does_not_absorb_composition_or_blur(self):
        self.assertEqual(m.same_operation(sample('ImageMagick','VerticalFilter._omp_fn.0')),'图片缩放')
        f=sample('ImageMagick','CompositeOverImage._omp_fn.0')
        self.assertIsNone(m.same_operation(f));self.assertEqual(m.separate_operation(f,'PDF'),'拼图合成')
        self.assertIsNone(m.same_operation(sample('LibreOffice·VCL','stackBlurHorizontal')))

    def test_runtime_and_whole_office_framework_not_credited(self):
        for tool in ('Python','lxml','LibreOffice·其他组件'):
            self.assertIsNone(m.same_operation(sample(tool,'sample_function')))
        self.assertEqual(m.same_operation(sample('LibreOffice·Calc','ScFormulaCell::IsValue()')),'模型／重算')

    def test_whole_roi_preserves_unknown_and_exact_precedence(self):
        rows=[sample('PNG','already_seen',40),sample('PNG','png_write_find_filter',20),
              sample('JPEG','jpeg_write_scanlines',10),sample('Python','parser',25)]
        c=dict(task='fixture',parent='fixture',format='PPT',roi_period=100,
            functions=[{k:v for k,v in f.items() if k!='tool'} for f in rows],
            hotspot_coverage=dict(unseen_functions=rows[1:]),
            presence={'OPM+TLC':dict(observed_period=40,unresolved_period=5)})
        out=m.account(c,{('sample.so','already_seen')})
        self.assertEqual(out['periods'],dict(exact=40,same_operation=20,separate_operation=10,other_resolved=25,unresolved=5))
        self.assertEqual(out['supported_share_pct'],60)
        self.assertEqual(sum(out['periods'].values()),100)

    def test_duplicate_identity_is_rejected(self):
        f=sample('PNG','png_write_find_filter')
        with self.assertRaisesRegex(ValueError,'duplicate'):
            m.account(dict(roi_period=100,functions=[f,f]),set())


if __name__=='__main__':unittest.main()
