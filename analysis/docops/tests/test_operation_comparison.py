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
        self.assertIn('Core Bound＋Memory Bound',report)
        self.assertIn('IPC 单独列相对变化，idle 不加入距离',report)
        self.assertIn('24 组新旧配对',report)
        topdown_section=report.split('### 7.4 ')[1].split('### 7.5 ')[0]
        self.assertNotIn('小档',topdown_section)
        self.assertNotIn('大档',topdown_section)
        self.assertNotIn('-u500',topdown_section)
        self.assertNotIn('-v1000',topdown_section)
        self.assertIn('七维余弦 ↑',topdown_section)
        self.assertIn('七维欧氏距离 ↓',topdown_section)
        self.assertIn('旧清单已见函数权重',report)
        self.assertEqual(report.count('![图 7-'),12)
        self.assertEqual(report.count('**读图：**'),12)
        for task in result['tasks']:
            self.assertIn('/'+task+'-bounds.svg)',report)
        self.assertIn('### 7.5 结论：建议增加哪些用例',report)
        self.assertIn('### 7.6 十二项任务的逐点曲线',report)
        self.assertLess(report.index('### 7.5 结论'),report.index('#### 图 7-1'))
        self.assertNotIn('未见热点／新热点数',report)
        section=report.split('### 7.3 ')[1].split('### 7.4 ')[0]
        self.assertIn('0.5% ROI',section)
        self.assertIn('不是函数个数或总 CPU 时间比例',section)
        self.assertIn('未解析权重单列',section)
        self.assertNotIn('尚未通过控制规模实验',report)
        self.assertIn('100业务单元／74.59%',section)
        self.assertIn('500业务单元／71.58%',section)
        self.assertIn('共 24 个合成规模变体',section)
        self.assertIn('五个原始用例',section)
        self.assertIn('优先一个用例：021；029 为可选强化项',section)
        self.assertIn('覆盖百分比始终按精确函数匹配计算',section)
        self.assertIn('Python 库约 85.9%、构建脚本约 87.5%',section)
        import unified_scaling_sections
        current,_=unified_scaling_sections.load()
        for parent,(_,large) in current['groups'].items():
            value=module.pct(current['cases'][large]['presence']['OPM+TLC']['observed_share_roi'])
            self.assertIn(value,section)
        self.assertIn('93 个',module.detail_section(result,module.ROOT/module.DEFAULT_OUTPUT))
        self.assertIn('JPEG 7.45%、VCL 8.98%、Poppler 7.92%',section)
        self.assertNotIn('各任务 Top-20 未覆盖函数完整清单',section)
        recommendations=report.split('### 7.5 ')[1].split('### 7.6 ')[0]
        self.assertIn('013、016、021、026、029',recommendations)
        self.assertNotIn('七配置',recommendations)
        self.assertNotIn('补齐本节的 49',recommendations)
        for variant in ['013-v100','016-u500','026-u10','029-u5']:
            self.assertNotIn(variant,recommendations)
        self.assertIn('优先增加 PPT 021。',recommendations)
        self.assertNotIn('021-g10',recommendations)
        self.assertNotIn('80 页',recommendations)
        self.assertIn('不宣称覆盖所有 Word／PPT 操作',report)

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
