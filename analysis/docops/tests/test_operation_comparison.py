import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
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

    def test_complete_reference_presence_deduplicates_union_and_keeps_unknown(self):
        a=dict(library='a.so',function='shared',period=40,share_roi=.4)
        b=dict(library='a.so',function='second',period=10,share_roi=.1)
        c=dict(library='b.so',function='shared',period=30,share_roi=.3)
        refs={'OPM':{'functions':[a]},'TLC':{'functions':[a,b]}}
        result=module.function_presence(refs,dict(roi_period=100,functions=[a,b,c]))
        self.assertEqual(result['OPM']['observed_period'],40)
        self.assertEqual(result['TLC']['observed_period'],50)
        union=result['OPM+TLC']
        self.assertEqual(union['observed_period'],50)
        self.assertEqual(union['not_observed_period'],30)
        self.assertEqual(union['unresolved_period'],20)
        self.assertEqual(union['reference_function_count'],2)
        self.assertEqual(union['not_observed_top20'],[c])

    def test_presence_checks_entire_list_and_rejects_nonconserving_target(self):
        old=self.rows([('a.so',str(i)) for i in range(12)])
        target=dict(library='a.so',function='11',period=80,share_roi=.8)
        refs={'OPM':{'functions':old},'TLC':{'functions':[]}}
        self.assertEqual(module.function_presence(refs,dict(roi_period=100,functions=[target]))['OPM']['observed_period'],80)
        with self.assertRaisesRegex(ValueError,'exceeds'):
            module.function_presence(refs,dict(roi_period=10,functions=[target]))
        with self.assertRaisesRegex(ValueError,'duplicate'):
            module.function_presence(refs,dict(roi_period=200,functions=[target,target]))

    def test_hotspot_stack_uses_old_threshold_and_full_target_period(self):
        def row(dso,name,period,share):return dict(library=dso,function=name,period=period,share_roi=share)
        refs={'OPM':{'functions':[row('a.so','hot',1,.004),row('b.so','low',1,.0049)]},
              'TLC':{'functions':[row('a.so','hot',1,.005)]}}
        target=dict(roi_period=1000,functions=[row('a.so','hot',100,.1),row('b.so','low',200,.2),row('new.so','new',300,.3)])
        c=module.hotspot_coverage(refs,target)
        self.assertEqual([p['period'] for p in c['partition']],[100,200,300,400])
        self.assertEqual(c['target_hotspots']['count_by_bucket'],{'old_hot':1,'old_low':1,'unseen':1})
        self.assertEqual(sum(g['period'] for g in c['unseen_by_tool_type']),300)
        self.assertEqual(sum(g['period'] for g in c['unseen_by_type']),300)

    def test_nonhot_long_tail_is_not_discarded_or_called_a_hotspot(self):
        refs={'OPM':{'functions':[]},'TLC':{'functions':[]}}
        target=dict(roi_period=1000,functions=[dict(library='x.so',function='small',period=4,share_roi=.004)])
        c=module.hotspot_coverage(refs,target)
        self.assertEqual(c['target_hotspots']['count'],0)
        self.assertEqual(c['partition'][2]['period'],4)
        self.assertEqual(c['partition'][3]['period'],996)

    def test_unseen_classification_separates_objects_runtime_and_image_implementation(self):
        classify=lambda d,n:module.unseen_function_type(dict(library=d,function=n))
        self.assertEqual(classify('libooxlo.so','oox::drawingml::table::applyTableStylePart(...)')[1],'文档对象／样式路径')
        self.assertEqual(classify('libconfigmgrlo.so','find(...)')[1],'运行支撑／容器与配置')
        self.assertEqual(classify('libMagickCore.so','VerticalFilter._omp_fn.0')[1],'图片滤波／缩放')
        self.assertEqual(classify('libpython.so','_PyEval_EvalFrameDefault')[1],'语言运行时／文本与对象')

    def test_unseen_explanations_conserve_and_only_include_unseen_functions(self):
        result=json.loads((module.ROOT/module.DEFAULT_OUTPUT/'comparison.json').read_text())
        for task in result['tasks']:
            with self.subTest(task=task):
                x=module.unseen_explanation(result,task)
                self.assertEqual(sum(g['period'] for g in x['groups'])+x['remainder_period'],
                    result['function_presence'][task]['OPM+TLC']['not_observed_period'])
                self.assertGreaterEqual(x['remainder_period'],0)
                self.assertEqual(len({g['tool'] for g in x['groups']}),len(x['groups']))
                for g in x['groups']:
                    self.assertEqual(g['period'],sum(f['period'] for f in result['hotspot_coverage'][task]['unseen_functions'] if f['tool']==g['tool']))

    def test_topk_matches_complete_union_and_sorts_target_by_period(self):
        old=self.rows([('a.so',str(i)) for i in range(30)])
        target=[dict(library='a.so',function=str(i),period=i+1,share_roi=.01)
                for i in range(25)]
        # Same symbol in a different library must not match; overlap counts once.
        target.append(dict(library='b.so',function='24',period=100,share_roi=.1))
        refs={'OPM':{'functions':old},'TLC':{'functions':old}}
        result=module.topk_presence(refs,{'functions':target})
        self.assertEqual(result['10']['observed_count'],9)
        self.assertEqual(result['20']['observed_count'],19)
        self.assertFalse(result['10']['functions'][0]['observed'])
        self.assertEqual(result['10']['functions'][1]['function'],'24')

    def test_topk_short_list_and_ties_keep_actual_denominator(self):
        rows=[dict(library='a.so',function=f,period=1) for f in ('b','a')]
        result=module.topk_presence({'OPM':{'functions':[]}}, {'functions':rows})
        self.assertEqual(result['20']['selected_count'],2)
        self.assertEqual([f['function'] for f in result['10']['functions']],['a','b'])
        with self.assertRaisesRegex(ValueError,'duplicate'):
            module.topk_presence({}, {'functions':rows+rows})

    def test_top20_unseen_inventory_matches_ranked_target_without_tail(self):
        result=json.loads((module.ROOT/module.DEFAULT_OUTPUT/'comparison.json').read_text())
        identities={module.key(f) for b in result['baselines'].values() for f in b['functions']}
        total=0
        for task,target in result['tasks'].items():
            with self.subTest(task=task):
                ranked=sorted(target['functions'],key=lambda f:(-f['period'],module.key(f)))[:20]
                expected=[(i,module.key(f)) for i,f in enumerate(ranked,1) if module.key(f) not in identities]
                actual=module.top20_unseen_operations(result['baselines'],target)
                self.assertEqual([(f['rank'],module.key(f)) for f in actual],expected)
                self.assertTrue(all(f['operation'] in module.TOP20_OPERATION_NOTES for f in actual))
                total+=len(actual)
        self.assertEqual(total,94)
        evidence=lambda task:module.top20_unseen_operations(result['baselines'],result['tasks'][task])
        self.assertEqual(sum(f['operation']=='Python 运行时' for f in evidence('031')),9)
        self.assertTrue(all(f['operation'] in ('图片编码／解码','图像缩放／滤波／合成','页面／像素绘制') for f in evidence('021')))
        self.assertEqual(sum(f['operation']=='文档对象／样式' for f in evidence('029')),2)

    def test_top20_operation_explanation_separates_styles_and_runtime(self):
        op=lambda dso,name:module.top20_operation(dict(library=dso,function=name))[1]
        self.assertEqual(op('libsclo.so','ScColumnData::GetMostUsedPattern(int, int) const'),'文档对象／样式')
        self.assertEqual(op('libvcllo.so','BitmapReadAccess::SetPixelForN24BitTcBgr(...)'),'页面／像素绘制')
        self.assertEqual(op('libpython3.12.so.1.0','_PyUnicode_ToLowerFull'),'文本／XML 处理')
        self.assertEqual(op('libpython3.12.so.1.0','term_rule'),'Python 运行时')

    def test_weighted_topk_separates_count_ranked_period_and_complete_roi(self):
        def row(name,period):return dict(library='a.so',function=name,period=period)
        refs={'old':dict(functions=[row('heavy',1)])}
        target=dict(roi_period=200,functions=[row('small2',3),row('heavy',90),row('small1',7)])
        out=module.weighted_topk_presence(refs,target,3)
        self.assertEqual((out['observed_count'],out['selected_count']),(1,3))
        self.assertEqual(out['selected_period'],100)
        self.assertEqual(out['observed_share_selected'],.9)
        self.assertEqual(out['observed_share_roi'],.45)
        self.assertEqual(out['selected_share_roi'],.5)
        self.assertEqual(out['observed_period']+out['not_observed_period'],out['selected_period'])
        empty=module.weighted_topk_presence({},dict(roi_period=200,functions=[]),10)
        self.assertIsNone(empty['observed_share_selected'])
        with self.assertRaisesRegex(ValueError,'denominator'):
            module.weighted_topk_presence(refs,dict(target,roi_period=99),1)

    def test_minimum_cover_is_exact_including_greedy_trap_and_ties(self):
        result=module.minimum_function_cover({'a':{1,2,3,4},'b':{1,2,5},'c':{3,4,6}},set(range(1,7)))
        self.assertEqual(result['minimum_count'],2)
        self.assertEqual(result['solutions'],[['b','c']])
        self.assertEqual(module.minimum_function_cover({'a':{1},'b':{1}},{1})['solutions'],[['a'],['b']])
        self.assertEqual(module.minimum_function_cover({},set())['minimum_count'],0)
        with self.assertRaisesRegex(ValueError,'cannot be covered'):
            module.minimum_function_cover({'a':{1}},{1,2})

    def test_actual_augmentation_keeps_unknown_denominator_and_flags_self_match(self):
        result=json.loads((module.ROOT/module.DEFAULT_OUTPUT/'comparison.json').read_text())
        a=module.augmentation_analysis(result['baselines'],result['tasks'])
        self.assertEqual(a['selected_tasks'],['013','021','029'])
        self.assertEqual(a['top20_unseen_unique_count'],58)
        self.assertEqual(a['top20_unseen_identities_matched'],49)
        self.assertEqual(len(a['top20_unseen_identities_remaining']),9)
        self.assertEqual(len(a['alternative']['top20_unseen_identities_remaining']),12)
        self.assertEqual(a['exact_top20_function_cover']['minimum_count'],7)
        self.assertEqual(len(a['exact_top20_function_cover']['solutions']),8)
        self.assertEqual(a['exact_all_function_cover']['minimum_count'],12)
        refs={module.key(f) for b in result['baselines'].values() for f in b['functions']}
        for task in a['selected_tasks']:refs|={module.key(f) for f in result['tasks'][task]['functions']}
        for task,p in a['tasks'].items():
            self.assertEqual(p['selected_as_reference'],task in a['selected_tasks'])
            self.assertEqual(p['observed_period']+p['not_observed_period']+p['unresolved_period'],p['roi_period'])
            self.assertEqual(p['not_observed_period'],sum(f['period'] for f in result['tasks'][task]['functions'] if module.key(f) not in refs))
            self.assertEqual(p['unresolved_period'],result['function_presence'][task]['OPM+TLC']['unresolved_period'])
            self.assertLessEqual(p['not_observed_period'],p['before_not_observed_period'])
        with self.assertRaisesRegex(ValueError,'selection'):
            module.augmentation_analysis(result['baselines'],result['tasks'],selected=('013','013'))

    def test_reader_report_keeps_all_tasks_hierarchical_comparison_and_figure_notes(self):
        result=json.loads((module.ROOT/module.DEFAULT_OUTPUT/'comparison.json').read_text())
        report=module.main_section(result,module.ROOT/module.DEFAULT_OUTPUT)
        self.assertIn('### 7.4 Topdown 相似性',report)
        self.assertIn('七维、不重复计权',report)
        self.assertIn('| Core Bound | 核心执行受限 |',report)
        self.assertIn('| Memory Bound | 缓存／内存供数受限 |',report)
        self.assertIn('IPC 单独列相对变化，idle 不加入距离',report)
        self.assertIn('24 组新旧配对',report)
        topdown_section=report.split('### 7.4 ')[1].split('### 7.5 ')[0]
        self.assertNotIn('小档',topdown_section)
        self.assertNotIn('大档',topdown_section)
        self.assertNotIn('-u500',topdown_section)
        self.assertNotIn('-v1000',topdown_section)
        self.assertIn('七维余弦 ↑',topdown_section)
        self.assertIn('七维欧氏距离 ↓',topdown_section)
        self.assertIn('函数已覆盖',report)
        self.assertEqual(report.count('![图 7-'),12)
        self.assertEqual(report.count('**读图：**'),12)
        for task in result['tasks']:
            self.assertIn('/'+task+'-bounds.svg)',report)
        self.assertIn('### 7.5 结论：建议增加哪些用例',report)
        self.assertIn('### 7.6 十二项任务的逐点曲线',report)
        self.assertLess(report.index('### 7.5 结论'),report.index('#### 图 7-1'))
        self.assertNotIn('未见热点／新热点数',report)
        section=report.split('### 7.3 ')[1].split('### 7.4 ')[0]
        self.assertIn('以 OPM＋TLC 为旧参考，百分比均按热点采样权重计算',section)
        self.assertIn('| 未解析 |',section)
        self.assertNotIn('尚未通过控制规模实验',report)
        self.assertIn('500单元',section)
        self.assertIn('原始、小档、大档完整结果',section)
        self.assertIn('共 24 个规模变体',section)
        self.assertIn('合计覆盖＝已覆盖函数＋未匹配函数中的同类操作',section)
        self.assertIn('JPEG 编解码、图像模糊、多图合成和 Word／PPT 文档对象路径分别保留',section)
        self.assertIn('每类都保留旧 OPM／TLC 的实际依据',section)
        self.assertNotIn('013 的高覆盖主要来自 Python 构建',section)
        import unified_scaling_sections
        current,_=unified_scaling_sections.load()
        for parent,(_,large) in current['groups'].items():
            value=module.pct(current['cases'][large]['presence']['OPM+TLC']['observed_share_roi'])
            self.assertIn(value,section)
        self.assertIn('93 个',module.detail_section(result,module.ROOT/module.DEFAULT_OUTPUT))
        import chapter7_editorial as editorial
        import operation_equivalence_deep as equivalence
        accounted=equivalence.load()
        stages=[section.split('#### 7.3.1 ')[1].split('#### 7.3.2 ')[0],
                section.split('#### 7.3.2 ')[1].split('#### 7.3.3 ')[0]]
        self.assertIn('### 7.3 旧用例覆盖了哪些函数与操作',report)
        self.assertLess(stages[0].index('原始规模的发现'),stages[0].index('为什么扩大规模'))
        self.assertLess(stages[0].index('为什么扩大规模'),stages[0].index('**表 7-4：'))
        self.assertIn('45.41%–79.15%',stages[0])
        self.assertIn('11/12 项大档高于原始任务',stages[0])
        for parent,row in accounted['cases'].items():
            first=[line for line in stages[0].splitlines()
                   if line.startswith('| '+row['format']+' '+parent+' |')]
            self.assertEqual(len(first),1)
            original=100*current['cases'][parent]['presence']['OPM+TLC']['observed_share_roi']
            cells=[x.strip() for x in first[0].split('|')[1:-1]]
            self.assertEqual(cells,[row['format']+' '+parent,editorial.pct(original),
                editorial.pct(row['shares_pct']['exact']),f"{row['shares_pct']['exact']-original:+.2f}"])
            cells=[line for line in stages[1].splitlines()
                   if line.startswith('| '+row['format']+' '+parent+'（')]
            self.assertEqual(len(cells),1)
            self.assertIn('| '+editorial.pct(row['shares_pct']['exact'])+' |',cells[0])
            self.assertTrue(cells[0].endswith('**'+editorial.pct(row['supported_share_pct'])+'** |'))
            self.assertNotIn('继续细分',cells[0])
        self.assertIn('以下使用上表的大规模结果',stages[1])
        self.assertIn('从函数匹配的 71.59% 提高到 87.27%',stages[1])
        self.assertIn('JPEG 编解码 '+editorial.pct(editorial.operation_pct(accounted['cases']['021'],'JPEG 编解码')),section)
        gaps=section.split('#### 7.3.3 ')[1]
        gap_table=gaps.split('Office 公共组件')[0]
        for parent,row in accounted['cases'].items():
            self.assertEqual(sum(line.startswith('| '+row['format']+' '+parent+' |')
                                 for line in gap_table.splitlines()),1)
            line=next(line for line in gap_table.splitlines() if line.startswith('| '+row['format']+' '+parent+' |'))
            self.assertEqual(len(line.split('|')[1:-1]),3)
            self.assertIn(editorial.pct(row['shares_pct']['other_resolved']),line.split('|')[2])
            self.assertIn('| '+editorial.pct(row['shares_pct']['unresolved'])+' |',line)
            for op in row['separate_operations']:
                self.assertIn(op['operation']+' '+editorial.pct(op['share_pct']),line)
            self.assertAlmostEqual(row['supported_share_pct']+sum(op['share_pct'] for op in row['separate_operations'])
                +row['shares_pct']['other_resolved']+row['shares_pct']['unresolved'],100)
        self.assertIn('Word 导入／对象布局 '+editorial.pct(editorial.operation_pct(accounted['cases']['009'],'Word 导入／对象布局')),gaps)
        self.assertIn('CPython 解释器库 `libpython3.12.so.1.0`',gaps)
        self.assertIn('`libswlo.so`',gaps)
        self.assertIn('`libsw_writerfilterlo.so`',gaps)
        self.assertIn('001、003 同样有 Word 路径',gaps)
        self.assertIn('encode_mcu_gather',gaps)
        self.assertIn('3.16%',gaps)
        self.assertNotIn('表 7-5A',gaps)
        self.assertNotIn('只补 PPT 的作用',gaps)
        self.assertNotIn('**选型建议：**',gaps)
        self.assertNotIn('各任务 Top-20 未覆盖函数完整清单',section)
        recommendations=report.split('### 7.5 ')[1].split('### 7.6 ')[0]
        self.assertIn('保留旧 OPM／TLC 作为核心',recommendations)
        self.assertIn('覆盖更多具体函数 | Excel 013＋PPT 021',recommendations)
        self.assertIn('研究 Word 导入与长文档排版时，再加 Word 009',recommendations)
        self.assertIn('具体函数优先补 013＋021',report)
        self.assertIn('前六章考察跨行业输入，本章进一步扩展实际任务操作',report)
        import supplement_selection
        selected=supplement_selection.load()
        decisions=section.split('#### 7.3.4 ')[1]
        self.assertIn('平均覆盖先分别计算十二项大档的覆盖率，再等权取平均',decisions)
        self.assertIn('若以平均覆盖达到 90% 为精简选型目标',decisions)
        self.assertIn('未解析部分仍计入分母',decisions)
        for mode,keys in [('exact',['base','primary']),('operation',['base','primary','ppt_only'])]:
            for key in keys:
                self.assertIn(editorial.pct(selected['modes'][mode][key]['mean_pct']),decisions)
        self.assertIn('67.73%',decisions)
        self.assertIn('86.29%',decisions)
        self.assertNotIn('七配置',recommendations)
        self.assertNotIn('补齐本节的 49',recommendations)
        for variant in ['013-v100','016-u500','026-u10','029-u5']:
            self.assertNotIn(variant,recommendations)
        self.assertNotIn('021-g10',recommendations)
        self.assertNotIn('80 页',recommendations)
        self.assertIn('再选 PPT 029',recommendations)
        self.assertEqual(editorial.revise(report),report)

    def test_library_inventory_distinguishes_python_workflows_from_native_samples(self):
        import chapter7_editorial as editorial
        import unified_scaling_sections
        scale,_=unified_scaling_sections.load()
        data=editorial.library_inventory(scale)
        python={r['library']:r for r in data['python']}
        self.assertEqual(python['python-pptx']['old_tasks'],[])
        self.assertEqual(python['python-pptx']['new_tasks'],['021','026','029'])
        self.assertEqual(python['openpyxl']['old_tasks'],['TLC'])
        self.assertEqual(python['pypdf']['old_tasks'],['OPM'])
        for row in data['python']:
            self.assertEqual({w['task'] for w in row['witnesses']},set(row['old_tasks']+row['new_tasks']))
            for witness in row['witnesses']:
                self.assertEqual(module.sha(module.ROOT/witness['path']),witness['sha256'])
        native={r['library']:r for r in data['native']}
        slides=native['Impress／Draw：`libsdlo.so`']
        self.assertEqual(slides['old_tasks'],[])
        self.assertEqual(slides['new_tasks'],['021','026','029'])
        # The shared OOXML library is observed in Excel/PPT, not the measured Word cases.
        self.assertEqual(native['OOXML：`libooxlo.so`']['new_tasks'],['013','014','016','021','026','029'])
        self.assertEqual(editorial.task_groups(['001'],scale),'Word 001')
        self.assertEqual(editorial.task_groups(['001','003','009'],scale),'Word')
        section=editorial.software_section(scale)
        self.assertIn('7.3 再比较库内实际执行的函数及操作',section)
        self.assertIn('— 表示未观测到',section)
        self.assertIn('Python 权重不是某一个 Python 文档库的单独占比',section)

    def test_native_library_ranking_keeps_full_roi_and_unknown_symbol_weight(self):
        import chapter7_editorial as editorial
        raw=dict(roi_period=100,libraries=[
            dict(dso='/lib/a.so.1',period=40),dict(dso='/other/a.so.1',period=20),
            dict(dso='/lib/b.so',period=15),dict(dso='[unknown]',period=20),
            dict(dso='/usr/bin/tool',period=5)],
            functions=[dict(dso='/lib/a.so.1',function='[unknown]',period=40)])
        rows=editorial.rank_native_libraries(raw)
        self.assertEqual([(r['library'],r['period']) for r in rows],[('a.so.1',60),('b.so',15)])
        self.assertEqual(rows[0]['share_roi'],.6)
        self.assertEqual(rows[1]['share_roi'],.15)
        with self.assertRaisesRegex(ValueError,'conserve'):
            editorial.rank_native_libraries(dict(raw,roi_period=90))

    def test_native_top3_table_uses_concrete_libraries_and_old_presence(self):
        import chapter7_editorial as editorial
        import unified_scaling_sections
        scale,_=unified_scaling_sections.load()
        data=editorial.native_library_hotspots(scale)
        old={r['library'] for p in ('OPM','TLC') for r in data['tasks'][p]['libraries']}
        for p in editorial.ORDER:
            case=data['tasks'][p]
            self.assertEqual(len(case['top3']),3)
            self.assertEqual(case['unranked_period']+sum(r['period'] for r in case['libraries']),case['roi_period'])
            for row in case['libraries']:
                self.assertEqual(row['observed_in_old'],row['library'] in old)
                self.assertAlmostEqual(row['share_roi'],row['period']/case['roi_period'])
            self.assertEqual(sum(r['period'] for r in case['zlib']['by_script']),case['zlib']['period'])
        self.assertEqual([r['library'] for r in data['tasks']['016']['top3']],
                         ['libpython3.12.so.1.0','libc.so.6','libsclo.so'])
        self.assertFalse(data['tasks']['031']['top3'][2]['observed_in_old'])
        cell=editorial.native_library_cell(data['tasks']['031']['top3'][0])
        self.assertIn('`libz.so` ★',cell)
        self.assertIn('66.25%',cell)
        self.assertEqual(data['tasks']['OPM']['preview'],'PNG')
        self.assertEqual(data['tasks']['TLC']['preview'],'不生成页面预览')
        self.assertEqual(round(100*data['tasks']['TLC']['zlib']['share_roi'],2),1.55)
        z=data['tasks']['014']['zlib']
        self.assertEqual(round(100*z['share_roi'],2),30.54)
        self.assertEqual(round(100*next(r['share_roi'] for r in z['by_script'] if r['script']=='pdftoppm'),2),29.27)
        table=editorial.native_hotspot_table(scale,data)
        self.assertEqual(len(table.splitlines()),16)  # header + separator + 14 cases
        self.assertTrue(all(len(line.split('|')[1:-1])==5 for line in table.splitlines()))
        self.assertIn('旧 PDF／OPM | PNG',table)
        self.assertIn('旧 Excel／TLC | 不生成页面预览',table)
        self.assertIn('PNG 压缩为主',table)

    def test_word_gap_and_candidate_gains_preserve_denominator(self):
        import chapter7_editorial as editorial
        import operation_equivalence as equivalence
        data=json.loads((module.ROOT/equivalence.INPUT/'comparison.json').read_text())
        accounted=equivalence.load()['cases']['009']
        review=editorial.word_review()
        remainder=[f for f in accounted['functions'] if f['bucket'] in ('separate_operation','other_resolved')]
        writer=[f for f in remainder if f['library'] in ('libswlo.so','libsw_writerfilterlo.so')]
        self.assertEqual(len(writer),225)
        self.assertAlmostEqual(100*sum(f['period'] for f in writer)/accounted['roi_period'],
                               review['residual_by_owner_pct']['Writer'])
        nonword={module.key(f) for c in data['cases'].values() if c['format']!='Word' for f in c['functions']}
        self.assertTrue(all(module.key(f) not in nonword for f in writer))
        for label,c in review['cross_task'].items():
            keys={module.key(f) for p in c['selected'] for f in data['cases'][p]['functions']}
            gained=sum(f['period'] for f in remainder if module.key(f) in keys)
            self.assertEqual(gained,c['additional_exact_period'],label)
            self.assertAlmostEqual(c['supported_pct'],accounted['supported_share_pct']+100*gained/accounted['roi_period'])
            self.assertAlmostEqual(c['supported_pct']+c['remaining_resolved_pct']+c['unresolved_pct'],100)
        self.assertGreater(review['cross_task']['all_original_nonWord']['supported_pct'],
                           review['cross_task']['021']['supported_pct'])

    def test_word_comparison_shows_modules_present_with_different_weights(self):
        import chapter7_editorial as editorial
        import operation_equivalence_refined as equivalence
        data=json.loads((module.ROOT/equivalence.INPUT/'comparison.json').read_text())
        saved=equivalence.load()
        rows=editorial.word_comparison(data,saved)
        self.assertEqual([r['task'] for r in rows],['001','003','009'])
        for row in rows:
            c=data['cases'][saved['cases'][row['task']]['task']]
            writer=sum(f['period'] for f in c['functions']
                       if f['library'] in ('libswlo.so','libsw_writerfilterlo.so'))
            codec=sum(f['period'] for f in c['functions']
                      if 'libz.so' in f['library'] or 'libpng' in f['library'])
            self.assertGreater(writer,0)
            self.assertAlmostEqual(row['writer_pct'],100*writer/c['roi_period'])
            # Native resolved leaves independently check the displayed aggregated libraries.
            self.assertAlmostEqual(row['compression_png_pct'],100*codec/c['roi_period'])
        self.assertGreater(rows[0]['compression_png_pct'],rows[2]['compression_png_pct'])
        self.assertGreater(rows[1]['compression_png_pct'],rows[0]['compression_png_pct'])
        self.assertGreater(rows[2]['writer_pct'],rows[0]['writer_pct'])
        self.assertGreater(rows[0]['writer_pct'],rows[1]['writer_pct'])

    def test_scaled_operation_selection_is_minimal_and_preserves_unknown(self):
        import itertools
        import scaling_report_sections as scaling
        original,scaled,selection=scaling.load()
        cases=dict(original['tasks']);cases.update(scaled['cases'])
        old={module.key(f) for c in original['baselines'].values() for f in c['functions']}
        required={module.key(f) for c in cases.values() for f in c['functions']
                  if module.key(f) not in old and f['share_roi']>=.005
                  and module.unseen_function_type(f)[0] in scaling.OPERATION_TOOLS}
        self.assertEqual(len(required),34)
        candidates={t:{module.key(f) for f in c['functions']} for t,c in original['tasks'].items()}
        for size in (1,2):
            self.assertFalse(any(required<=set().union(*(candidates[t] for t in choice))
                for choice in itertools.combinations(candidates,size)))
        solutions=[list(choice) for choice in itertools.combinations(candidates,3)
                   if required<=set().union(*(candidates[t] for t in choice))]
        self.assertEqual(solutions,[['013','021','029']])
        self.assertEqual(solutions,selection['minimum_operation_cover']['solutions'])
        for t,row in selection['selected']['targets'].items():
            self.assertEqual(sum(row[k] for k in ('observed_period','not_observed_period','unresolved_period')),
                             row['roi_period'])
            expected=cases[t]['roi_period']-sum(f['period'] for f in cases[t]['functions'])
            self.assertEqual(row['unresolved_period'],expected)
            self.assertLessEqual(row['not_observed_share_roi'],row['before_not_observed_share_roi'])
            self.assertEqual(row['selected_as_reference'],t in ('013','021','029'))


if __name__=='__main__':unittest.main()
