import json,hashlib,math,re,collections,csv
from pathlib import Path
root=Path('/home/lcq/office-trace-replay')
folder=root/'analysis/docops/processed/operation-equivalence-review-20261112'
folder.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
source=root/'analysis/docops/processed/unified-scaling-final-20261108/comparison.json'
x=json.loads(source.read_text())
prior=json.loads(Path('/tmp/operation-equivalence-large-20261111.json').read_text())
original=json.loads(Path('/tmp/operation-equivalence-preliminary-20261111.json').read_text())
build=json.loads(source.with_name('analysis-build.json').read_text())
for name,h in build['outputs'].items():assert sha(source.parent/name)==h,name
for name,h in x['input_sha256'].items():assert sha(root/name)==h,name
identity=lambda f:(f['library'],f['function'])
old={identity(f) for b in x['references'].values() for f in b['functions']}
assert len(old)==1339

def raw_valid(f):
 return f['dso']!='[unknown]' and f['function'] not in ('[unknown]','[no-frame]') and not re.fullmatch(r'0x[0-9a-fA-F]+|[0-9a-fA-F]{12,}',f['function'])
def equivalence(f):
 tool,name=f['tool'],f['function']
 if tool in ('PNG','JPEG'):return 'image_codec'
 if tool=='zlib':return 'compression'
 if tool=='Poppler':return 'pdf_parse_render'
 if tool=='LibreOffice·Calc':return 'calc_model_recalc'
 if tool=='ImageMagick' and re.search(r'HorizontalFilter|VerticalFilter|ResizeImage',name):return 'image_rescale'
 if tool=='LibreOffice·VCL':
  if any(t in name for t in ('ImplScaleConvolution','scaleUpPalette')):return 'image_rescale'
  if 'encode_mcu_' in name:return 'image_codec'
 return None

def jpeg_specific(f):return f['tool']=='JPEG' or (f['tool']=='LibreOffice·VCL' and 'encode_mcu_' in f['function'])
checks={};derived={}
for task,c in x['cases'].items():
 T=c['roi_period'];assert T>0
 assert len({identity(f) for f in c['functions']})==len(c['functions'])
 F=sum(f['period'] for f in c['functions'] if identity(f) in old)
 N=sum(f['period'] for f in c['functions'] if identity(f) not in old)
 U=T-F-N
 assert U>=0
 saved=c['presence']['OPM+TLC']
 assert (F,N,U)==tuple(saved[k+'_period'] for k in ('observed','not_observed','unresolved'))
 path=root/c['source']['profile'];raw=json.loads(path.read_text())
 observed=collections.Counter();raw_buckets=collections.Counter()
 for f in raw['functions']:
  if raw_valid(f):
   k=(Path(f['dso']).name,f['function']);observed[k]+=f['period'];raw_buckets['exact' if k in old else 'unseen']+=f['period']
  else:raw_buckets['unknown']+=f['period']
 assert observed==collections.Counter({identity(f):f['period'] for f in c['functions']})
 assert (raw_buckets['exact'],raw_buckets['unseen'],raw_buckets['unknown'])==(F,N,U)
 assert sum(raw_buckets.values())==raw['roi_period']==T
 unseen=c['hotspot_coverage']['unseen_functions'];assert {identity(f) for f in unseen}=={k for k in observed if k not in old}
 E=sum(f['period'] for f in unseen if equivalence(f));J=sum(f['period'] for f in unseen if equivalence(f) and jpeg_specific(f))
 assert F+E+(N-E)+U==T
 compared=prior['results'].get(task) or original['results'][task]
 values={'exact_pct':F/T*100,'additional_equivalent_pct':E/T*100,'supported_pct':(F+E)/T*100,'remaining_pct':(N-E)/T*100,'unknown_pct':U/T*100}
 for k,v in values.items():
  key='remaining_unclassified_pct' if k=='remaining_pct' and k not in compared else k
  assert math.isclose(v,compared[key],abs_tol=1e-10),(task,k)
 context=sum(f['period'] for f in c['contexts']);assert context==T
 checks[task]={'raw_profile_partition_recomputed':True,'unique_identities':True,'full_denominator':True,'no_double_count':True,'previous_values_reproduced':True}
 derived[task]=dict(parent=c['parent'],**values,narrow_excluding_jpeg_pct=(F+E-J)/T*100,jpeg_sensitivity_pp=J/T*100,
  unknown_period=U,exact_period=F,equivalent_period=E,jpeg_equivalent_period=J,roi_period=T,
  lost_chunks=c['source']['capture_quality'].get('perf_record_reported_lost_chunks'),
  cycles_u_lost_samples=c['source']['capture_quality'].get('cycles_u_stats_lost_samples'))

c=x['cases']['016-u500'];T=c['roi_period']
aux=[f for f in c['hotspot_coverage']['unseen_functions'] if f['tool'] in ('Python','lxml','XML 组件')]
assert not any(equivalence(f) for f in aux)
auxpct=sum(f['period'] for f in aux)/T*100
extended=derived['016-u500']['supported_pct']+auxpct
assert math.isclose(extended,prior['task_016_extended_supported_pct'],abs_tol=1e-10)
# The old workload's observed image path is PNG output and Pillow resampling;
# no resolved JPEG-related leaf symbol is present in either full old list.
assert not any(re.search('jpeg',f['library']+' '+f['function'],re.I) for b in x['references'].values() for f in b['functions'])
record=dict(status='passed_arithmetic_with_classification_findings',configuration_count=36,raw_profiles_rechecked=36,
 input_hashes_rechecked=len(x['input_sha256']),old_reference_identities=len(old),checks=checks,results=derived,
 task_016_auxiliary_python_xml_pct=auxpct,task_016_extended_mechanism_pct=extended,
 findings=[
  dict(id='F1',severity='methodology',summary='JPEG inclusion is a broader image-codec convention, not confirmed JPEG-path coverage by old OPM/TLC. Narrow sensitivity excludes it.'),
  dict(id='F2',severity='interpretation',summary='Operation-equivalent period is not exact function coverage, algorithm equivalence, or total CPU time.'),
  dict(id='F3',severity='classification',summary='016 Python/XML additions describe common runtime mechanisms; keep separate from document-operation accounting.'),
  dict(id='F4',severity='quality',summary='Retained-sample accounting conserves. Lost samples/chunks and unknown symbols remain; no correction into missing CPU/period is attempted.'),
  dict(id='F5',severity='scope',summary='Mapping is partial and symbol-based: no guaranteed full stage attribution or complete operation coverage. Contact-sheet composition, Writer/PPT object/style paths and unclassified frameworks are not automatically folded into existing operations.')],
 inputs={'comparison.json':dict(path=str(source.relative_to(root)),sha256=sha(source)),
        'previous_large':dict(path='/tmp/operation-equivalence-large-20261111.json',sha256=sha('/tmp/operation-equivalence-large-20261111.json')),
        'previous_original':dict(path='/tmp/operation-equivalence-preliminary-20261111.json',sha256=sha('/tmp/operation-equivalence-preliminary-20261111.json'))},
 formal_report_modified=False,html_modified=False,workload_or_collector_run=False)
(folder/'audit.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
with (folder/'large-comparison.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['task','exact_pct','previous_broad_operation_supported_pct','narrow_excluding_jpeg_pct','jpeg_sensitivity_pp','remaining_unclassified_pct','unknown_pct','lost_chunks','cycles_u_lost_samples'])
 for p,(_,task) in x['groups'].items():
  r=derived[task];w.writerow([task,r['exact_pct'],r['supported_pct'],r['narrow_excluding_jpeg_pct'],r['jpeg_sensitivity_pp'],r['remaining_pct'],r['unknown_pct'],r['lost_chunks'],r['cycles_u_lost_samples']])
lines=['# 同类操作归并初算审计','',
 '结论：36 项精确匹配及初算四分区从原始 profile 复算一致，无重复计数、分母缩减或未知权重转正。254 份输入哈希一致。分类解释需要调整。','',
 '- JPEG：旧例可确认的是 PNG 输出与 Pillow 缩放，未观察到 JPEG 叶函数；上一版将其归入图片编解码，属于较宽的操作分类。严格区分编码时，021 大档从 82.23% 降至 74.21%，026 从 80.65% 降至 74.80%，029 从 48.24% 降至 47.80%。',
 '- 016：精确函数匹配 80.0253%，明确同类操作归并后约 87.3313%。加入 Python/XML 公共机制约 90.5863%，应单列机制归并层，不标为精确函数覆盖或已验证算法等价。',
 '- 剩余已解析权重包括未归类框架函数，不全部是新增文档操作；未解析权重单列。',
 '- 丢样保留：016 大档记录 435 lost chunks / cycles:u LOST_SAMPLES 1886；它们不相加，不推算为 ROI 丢失周期，也不计算为可纠正的缺失比例。',
 '- 本次只离线复核，不改正式报告或 HTML，不重跑采集。','',
 '详见 audit.json（36项原始 profile 复算、保留样本守恒和分类问题）、large-comparison.csv（十二项大档的归并口径敏感性）。','']
(folder/'review.md').write_text('\n'.join(lines))
script=folder/'audit_operation_equivalence.py';script.write_bytes(Path(__file__).read_bytes())
(folder/'sha256-index.json').write_text(json.dumps({'files':{p.name:sha(p) for p in folder.iterdir() if p.is_file()}},indent=2)+'\n')
print('Audit complete:',folder)
print('Input hashes:',len(x['input_sha256']),'raw profiles:',len(checks),'period partitions and prior values: all passed')
for task in ['016-u500','021-g10','026-u10','029-u10']:
 r=derived[task];print(task,'exact',r['exact_pct'],'broad',r['supported_pct'],'narrow',r['narrow_excluding_jpeg_pct'])
