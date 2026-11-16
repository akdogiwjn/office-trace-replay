from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import operation_equivalence_refined as m


def row(dso,name,period=10,bucket='other_resolved',tool='LibreOffice·其他组件',operation=None):
    return dict(library=dso,function=name,period=period,share_roi=period/100,
                bucket=bucket,tool=tool,operation=operation)


class RefinedEquivalenceTests(unittest.TestCase):
    def test_same_library_does_not_imply_same_operation(self):
        self.assertIsNone(m.family(row('libvcllo.so','stackBlurVertical')))
        self.assertIsNone(m.family(row('libswlo.so','SwLayoutFrame::GetLastLower() const')))
        self.assertIsNone(m.family(row('libsvllo.so','unknown_function')))
        self.assertIsNone(m.family(row('libsvllo.so','another_function(SfxItemSet const&)')))

    def test_specific_property_and_component_families(self):
        self.assertEqual(m.family(row('libsvllo.so','SfxItemSet::Get(int)')),'属性／样式管理')
        self.assertEqual(m.family(row('libuno_cppu.so.3','cppu::_copyConstructAnyFromData(a, b)')),'组件数据构造／释放')
        self.assertIsNone(m.family(row('libuno_cppu.so.3','unrecognized(a, b)')))

    def test_pixel_reads_do_not_absorb_writes_or_blur(self):
        for name in ('BitmapReadAccess::GetPixelForN32BitTcBgrx(a)',
                     'BitmapReadAccess::GetPixelForN24BitTcBgr(a)'):
            self.assertEqual(m.family(row('libvcllo.so',name)),'像素读取')
        self.assertIsNone(m.family(row('libvcllo.so','BitmapReadAccess::SetPixelForN8BitPal(a)')))
        self.assertEqual(m.residual_operation(row('libvcllo.so','stackBlurVertical',tool='LibreOffice·VCL'),'PPT'),'图像模糊')

    def test_regex_width_and_text_search_have_matching_old_operations(self):
        for name in ('sre_ucs1_match','sre_ucs2_match','sre_ucs4_charset.constprop.0'):
            self.assertEqual(m.family(row('libpython3.12.so.1.0',name)),'正则处理')
        for name in ('stringlib_default_find.lto_priv.0','ucs2lib__two_way'):
            self.assertEqual(m.family(row('libpython3.12.so.1.0',name)),'文本搜索')
        self.assertIsNone(m.family(row('libpython3.12.so.1.0','_sre_compile')))
        self.assertIsNone(m.family(row('libpython3.12.so.1.0','term_rule')))

    def fixture(self):
        rows=[row('old.so','known',30,'exact',None),row('png.so','encode',20,'same_operation','PNG','PNG 编解码'),
              row('libsvllo.so','SfxItemSet::Get(int)'),row('x.so','unknown_function'),
              row('libjpeg.so','jpeg_write',5,'separate_operation','JPEG','JPEG'),
              row('libvcllo.so','BitmapReadAccess::GetPixelForN24BitTcBgr(a)',tool='LibreOffice·VCL'),
              row('libvcllo.so','stackBlurVertical',tool='LibreOffice·VCL')]
        return dict(task='fixture',parent='fixture',format='PPT',roi_period=100,functions=rows,
                    periods=dict(exact=30,same_operation=20,other_resolved=40,separate_operation=5,unresolved=5),
                    supported_share_pct=50)

    def test_witnesses_are_required_and_full_denominator_conserved(self):
        c=self.fixture();out=m.refine(c,{'属性／样式管理':[{'reference':'TLC'}],'像素读取':[{'reference':'TLC'}]})
        self.assertEqual(out['periods'],dict(exact=30,same_operation=40,other_resolved=10,separate_operation=15,unresolved=5))
        self.assertEqual(out['supported_share_pct'],70)
        self.assertEqual(sum(out['periods'].values()),100)
        self.assertEqual(c['supported_share_pct'],50)
        self.assertEqual(m.refine(c,{})['supported_share_pct'],50)
        self.assertEqual(m.refine(c,{'属性／样式管理':[]})['supported_share_pct'],50)

    def test_all_measured_results_preserve_exact_unknown_and_old_operation_credit(self):
        data=m.gather();self.assertEqual(len(data['cases']),12)
        old=m.base.load()
        for p,c in data['cases'].items():
            self.assertEqual(c['periods']['exact'],old['cases'][p]['periods']['exact'])
            self.assertEqual(c['periods']['unresolved'],old['cases'][p]['periods']['unresolved'])
            self.assertAlmostEqual(c['supported_share_pct']-c['previous_supported_share_pct'],c['additional_share_pct'])
            self.assertEqual(sum(c['periods'].values()),c['roi_period'])
            for f in c['functions']:
                if f.get('evidence_family'):self.assertTrue(data['reference_witnesses'][f['evidence_family']])
        ppt=data['cases']['021']
        jpeg=next(g for g in ppt['separate_operations'] if g['operation']=='JPEG 编解码')
        self.assertGreater(jpeg['share_pct'],8)
        self.assertGreater(data['ppt021']['top_function']['share_roi']*100,3)


if __name__=='__main__':unittest.main()
