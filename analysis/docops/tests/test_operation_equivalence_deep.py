"""Counterexamples for witnessed shared operations and candidate marginal gain."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import operation_equivalence_deep as m


def f(dso, name, period=10, bucket='other_resolved', tool='Python'):
    return dict(library=dso, function=name, period=period, bucket=bucket,
                operation=None, tool=tool, share_roi=period/100)


class DeepEquivalenceTests(unittest.TestCase):
    def test_named_runtime_calls_map_but_whole_libraries_do_not(self):
        self.assertEqual(m.family(f('libpython3.12.so.1.0', 'dictiter_new')), 'Python 字典／哈希管理')
        self.assertEqual(m.family(f('libpython3.12.so.1.0', 'PyObject_VectorcallMethod')), 'Python 对象／调用／内存管理')
        self.assertEqual(m.family(f('libpython3.12.so.1.0', 'term_rule')), 'Python 脚本解析／编译')
        self.assertEqual(m.family(f('libpython3.12.so.1.0', 'code_hash')), 'Python 对象／调用／内存管理')
        for dso in ('libpython3.12.so.1.0', 'libvcllo.so', 'libsvllo.so', 'etree.cpython-312.so'):
            self.assertIsNone(m.family(f(dso, 'unidentified_function')))

    def test_parameters_and_return_types_do_not_confer_operations(self):
        self.assertIsNone(m.family(f('libsvllo.so', 'unrecognized(SfxItemSet const&)')))
        self.assertIsNone(m.family(f('libsvllo.so', 'std::vector<int> application_specific_operation()')))
        self.assertEqual(m.family(f('libsvllo.so', 'std::pair<int, bool> std::_Rb_tree<int>::find(int)')), 'C++ 容器／查找')

    def test_xml_operations_have_explicit_old_cross_library_witnesses(self):
        for n in ('xmlStrcmp', 'xmlDictExists'):
            self.assertEqual(m.family(f('etree.cpython-312-aarch64-linux-gnu.so', n)), 'XML 文本／名称管理')
        self.assertEqual(m.family(f('etree.cpython-312-aarch64-linux-gnu.so', 'xmlXPathNextDescendant')), 'XML 节点查询／遍历')
        self.assertEqual(m.family(f('_elementtree.cpython-312-aarch64-linux-gnu.so', '_elementtree_Element_find')), 'XML 节点查询／遍历')
        self.assertEqual(m.family(f('etree.cpython-312-aarch64-linux-gnu.so', 'xmlSetTreeDoc')), 'XML 节点构建／修改')
        self.assertEqual(m.family(f('libuno_cppu.so.3', 'typelib_typedescriptionreference_release')), 'UNO 数据／类型与引用管理')

    def test_pixel_formats_share_work_but_new_codecs_and_layout_remain_distinct(self):
        self.assertEqual(m.family(f('_imaging.cpython-312.so', 'ImagingPackRGB')), '像素读写／格式转换')
        self.assertEqual(m.family(f('libvcllo.so', 'BitmapReadAccess::SetPixelForN24BitTcBgr(a)')), '像素读写／格式转换')
        self.assertEqual(m.family(f('libvcllo.so', 'stackBlurVertical')), '图像模糊')
        self.assertEqual(m.family(f('libjpeg.so', 'encode_mcu_gather')), 'JPEG 编解码')
        self.assertEqual(m.family(f('libswlo.so', 'SwLayoutFrame::GetLastLower() const')), 'Word 导入／对象布局')
        self.assertEqual(m.family(f('libooxlo.so', 'oox::drawingml::table::applyTableStylePart(a)')), '幻灯片表格样式')

    def fixture(self):
        fs = [f('old.so','old',20,'exact'),
              dict(f('png.so','encode',20,'same_operation'),operation='PNG 编解码'),
              f('libpython3.12.so.1.0','dictiter_new',20),
              f('libswlo.so','SwLayoutFrame::GetLastLower()',10,'separate_operation'),
              f('mystery.so','opaque',20)]
        return dict(task='fixture',format='Word',functions=fs,roi_period=100,
                    periods=dict(exact=20,same_operation=20,separate_operation=10,other_resolved=40,unresolved=10),
                    supported_share_pct=40)

    def test_missing_or_empty_witness_does_not_increase_coverage(self):
        c=self.fixture();before=copy.deepcopy(c)
        self.assertEqual(m.refine(c,{})['supported_share_pct'],40)
        self.assertEqual(m.refine(c,{'Python 字典／哈希管理':[]})['supported_share_pct'],40)
        proof={'Python 字典／哈希管理':[dict(reference='TLC',library='libpython3.12.so.1.0',function='_Py_dict_lookup')]}
        out=m.refine(c,proof)
        self.assertEqual(out['supported_share_pct'],60)
        self.assertEqual(out['periods']['unresolved'],10)
        self.assertEqual(out['periods']['separate_operation'],10)
        self.assertEqual(sum(out['periods'].values()),100)
        self.assertEqual(c,before)

    def test_candidate_credit_is_disjoint_and_word_layout_not_invented(self):
        c=self.fixture()
        raw=dict(cases={'021':dict(functions=[f('libpython3.12.so.1.0','_Py_dict_lookup'),
                                             f('mystery.so','opaque')])})
        out=m.supplement(c,raw,['021'])
        self.assertEqual(out['added_period'],40)
        self.assertEqual(out['supported_share_pct'],80)
        self.assertEqual(len(out['functions']),2)
        self.assertTrue(all(x['library']!='libswlo.so' for x in out['functions']))

    def test_pdf_serialization_requires_frozen_workflow_evidence(self):
        c=self.fixture()
        c['functions'][2]=f('libvcllo.so','vcl::PDFWriterImpl::emitStructure(a)',20)
        self.assertEqual(m.family(c['functions'][2]),'PDF 对象／结构写出')
        self.assertEqual(m.refine(c,{})['supported_share_pct'],40)
        data=m.gather()
        proof=data['reference_witnesses']['PDF 对象／结构写出'][0]
        self.assertEqual(proof['evidence_kind'],'workflow_source')
        self.assertEqual(m.method.sha(m.ROOT/proof['source_path']),proof['source_sha256'])
        self.assertIn(proof['source_path'],data['inputs'])
        self.assertEqual(m.refine(c,{'PDF 对象／结构写出':[proof]})['supported_share_pct'],60)

    def test_actual_measurements_conserve_periods_and_every_new_credit_has_proof(self):
        data=m.gather();old=m.prior.load()
        self.assertEqual(len(data['cases']),12)
        self.assertNotIn('JPEG 编解码', data['reference_witnesses'])
        self.assertNotIn('图像模糊', data['reference_witnesses'])
        self.assertNotIn('Word 导入／对象布局', data['reference_witnesses'])
        for p,c in data['cases'].items():
            self.assertEqual(c['periods']['exact'],old['cases'][p]['periods']['exact'])
            self.assertEqual(c['periods']['unresolved'],old['cases'][p]['periods']['unresolved'])
            self.assertEqual(sum(c['periods'].values()),c['roi_period'])
            self.assertGreaterEqual(c['supported_share_pct'],old['cases'][p]['supported_share_pct'])
            for row in c['functions']:
                if row['previous_bucket'] in ('separate_operation','other_resolved') and row['bucket']=='same_operation':
                    self.assertIn(row['evidence_family'],data['reference_witnesses'])
                    self.assertTrue(row['evidence_reference'] in ('OPM','TLC'))
            for x in data['supplements'][p].values():
                self.assertEqual(x['added_period'],sum(f['period'] for f in x['functions']))
                self.assertEqual(len(x['functions']),len({m.method.key(f) for f in x['functions']}))
                self.assertLessEqual(x['supported_share_pct']+c['shares_pct']['unresolved'],100.00000001)
        word=data['cases']['009']
        self.assertGreater(word['supported_share_pct'],86)
        self.assertLess(data['supplements']['009']['021']['added_share_pct'],1)
        self.assertGreater(sum(x['share_pct'] for x in word['separate_operations']
                               if x['operation']=='Word 导入／对象布局'),7)


if __name__=='__main__':unittest.main()
