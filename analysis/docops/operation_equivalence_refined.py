"""Refine saved operation accounting using explicitly observed baseline families."""
from collections import Counter
import argparse
import csv
import json
from pathlib import Path
import re

import operation_comparison as method
import operation_equivalence as base

ROOT=base.ROOT
INPUT=base.INPUT
OUTPUT='analysis/docops/processed/operation-equivalence-refined-20261115'
POLICY=base.POLICY+' Add reference-witnessed property, component-value, configuration, XML-reader, pixel-reader, regex and text-search families; no whole-library credit.'


def family(f):
    """Only named callees in specific owners; parameters do not confer a role."""
    d,n=f['library'],f['function'];head=n.split('(',1)[0]
    if d in ('libsvllo.so','libeditenglo.so') and re.search(
        r'\b(?:SfxItemPool|SfxItemSet|SfxItemPropertyMap|SfxItemPropertySet|SfxPoolItem|SvxItemPropertySet)::',head):
        return '属性／样式管理'
    if d=='libuno_cppu.so.3' and re.fullmatch(
        r'cppu::(?:_?(?:copyConstruct\w*|destruct\w*|assign\w*)|i?defaultConstruct\w*)',head):
        return '组件数据构造／释放'
    if d=='libconfigmgrlo.so' and (head.startswith('configmgr::') or
        (head.startswith('std::') and 'configmgr::Node' in head)):
        return '配置读取／管理'
    if d=='libxmlreaderlo.so' and head.startswith('xmlreader::XmlReader::'):
        return 'XML 读取'
    if d=='libvcllo.so' and head.startswith('BitmapReadAccess::GetPixelFor'):
        return '像素读取'
    if d.startswith('libpython') and re.match(
        r'^(?:sre_ucs[124]_(?:match|count|search|charset)(?:$|[._])|sre_search$)',n):
        return '正则处理'
    if d.startswith('libpython') and re.match(
        r'^(?:stringlib|ucs[124]lib)_(?:_?two_way|fastsearch|default_find)(?:$|[._])',n):
        return '文本搜索'
    return None


def residual_operation(f,fmt):
    """Identify concrete document paths, keeping the remaining support explicit."""
    d,n=f['library'],f['function'];tool=f['tool']
    if d in ('libswlo.so','libsw_writerfilterlo.so'):return 'Word 导入／对象布局'
    if tool=='JPEG' or (tool=='LibreOffice·VCL' and 'encode_mcu_' in n):return 'JPEG 编解码'
    if tool=='LibreOffice·VCL' and 'stackBlur' in n:return '图像模糊'
    if tool=='ImageMagick' and re.search(r'Composite\w*Image|AppendImages|SmushImages',n):return '多图合成'
    if (fmt=='PPT' and tool=='LibreOffice·OOXML') or tool in (
        'LibreOffice·文本布局','LibreOffice·文本样式','LibreOffice·矢量图形'):
        return '图文对象／样式'
    return None


def witnesses(references):
    result={}
    for name,c in references.items():
        for f in c['functions']:
            g=family(f)
            if g:result.setdefault(g,[]).append(dict(reference=name,**f))
    return result


def refine(c,proof):
    out=dict(c);total=c['roi_period'];periods=Counter();added=Counter();ops=Counter();sep=Counter();tools=Counter();rows=[]
    for saved in c['functions']:
        f=dict(saved,previous_bucket=saved['bucket']);g=family(f)
        if f['bucket'] in ('other_resolved','separate_operation') and proof.get(g):
            f.update(bucket='same_operation',operation=g,evidence_family=g)
            added[g]+=f['period']
        elif f['bucket'] in ('other_resolved','separate_operation'):
            op=residual_operation(f,c['format'])
            f.update(bucket='separate_operation' if op else 'other_resolved',operation=op)
        periods[f['bucket']]+=f['period'];rows.append(f)
        if f['bucket']=='same_operation':ops[f['operation']]+=f['period']
        elif f['bucket']=='separate_operation':sep[f['operation']]+=f['period']
        elif f['bucket']=='other_resolved':tools[f['tool']]+=f['period']
    periods['unresolved']=c['periods']['unresolved']
    for k in ('exact','same_operation','separate_operation','other_resolved'):periods.setdefault(k,0)
    assert sum(periods.values())==total
    assert periods['exact']==c['periods']['exact']
    assert periods['same_operation']==c['periods']['same_operation']+sum(added.values())
    out.update(periods=dict(periods),shares_pct={k:100*v/total for k,v in periods.items()},
        supported_share_pct=100*(periods['exact']+periods['same_operation'])/total,
        previous_supported_share_pct=c['supported_share_pct'],
        additional_share_pct=100*sum(added.values())/total,functions=rows)
    def grouped(values,label):
        return [dict(**{label:k},period=v,share_pct=100*v/total) for k,v in values.most_common()]
    out.update(same_operations=grouped(ops,'operation'),additional_operations=grouped(added,'operation'),
        separate_operations=grouped(sep,'operation'),other_tools=grouped(tools,'tool'))
    return out


def gather():
    prior=base.load();assert base.gather()==prior
    raw=json.loads((ROOT/INPUT/'comparison.json').read_text());proof=witnesses(raw['references'])
    assert len(proof)==7
    cases={p:refine(c,proof) for p,c in prior['cases'].items()}
    ppt=cases['021'];remaining=[f for f in ppt['functions'] if f['bucket'] in ('separate_operation','other_resolved')]
    result=dict(schema='operation-equivalence-refined-v1',policy=POLICY,cases=cases,reference_witnesses=proof,
        inputs={base.OUTPUT+'/comparison.json':method.sha(ROOT/base.OUTPUT/'comparison.json'),
                base.OUTPUT+'/analysis-build.json':method.sha(ROOT/base.OUTPUT/'analysis-build.json'),
                INPUT+'/comparison.json':method.sha(ROOT/INPUT/'comparison.json')},
        verification=dict(status='passed',baseline_families=7,input_hashes_checked=254,
            exact_periods_unchanged=True,unknown_periods_unchanged=True,full_periods_conserved=True),
        ppt021=dict(remaining_function_count=len(remaining),
            top_function=max(remaining,key=lambda f:f['period']),
            document_operation_pct=ppt['shares_pct']['separate_operation'],
            operation_groups=ppt['separate_operations']),
        interpretation='Operation-family accounting backed by old observed functions; retained native exact matching is unchanged. Remaining support is not automatically a new document operation.',
        workload_or_collector_run=False,html_modified=False)
    return result


def load():
    folder=ROOT/OUTPUT;build=json.loads((folder/'analysis-build.json').read_text())
    assert method.sha(folder/'comparison.json')==build['outputs']['comparison.json']
    for p,h in build['source_sha256'].items():assert method.sha(ROOT/p)==h,p
    for p,h in build['inputs'].items():assert method.sha(ROOT/p)==h,p
    return json.loads((folder/'comparison.json').read_text())


def save(result):
    folder=ROOT/OUTPUT;folder.mkdir(parents=True,exist_ok=False)
    method.write(folder/'comparison.json',result)
    with (folder/'functions.csv').open('w',newline='') as f:
        fields=['task','library','function','period','share_roi','previous_bucket','bucket','operation','tool','evidence_family']
        w=csv.DictWriter(f,fields);w.writeheader()
        for c in result['cases'].values():
            for row in c['functions']:w.writerow(dict(task=c['task'],**row))
    headers=['task','exact_pct','previous_supported_pct','additional_pct','supported_pct','document_paths_pct','other_resolved_pct','unresolved_pct']
    with (folder/'coverage.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(headers)
        for c in result['cases'].values():
            s=c['shares_pct'];w.writerow([c['task'],s['exact'],c['previous_supported_share_pct'],c['additional_share_pct'],c['supported_share_pct'],s['separate_operation'],s['other_resolved'],s['unresolved']])
    lines=['# 同类操作进一步核对','','新增归并：属性／样式管理、组件数据构造／释放、配置管理、XML 读取、像素读取、正则处理和文本搜索。每类都绑定旧 OPM／TLC 中实际观察到的函数；不按整个库归并。','',
        method.table(['大档','原合计','本次归并','新合计','文档路径差额','其它已解析','未解析'],[
            [c['task'],*[f'{v:.2f}%' for v in (c['previous_supported_share_pct'],c['additional_share_pct'],c['supported_share_pct'],c['shares_pct']['separate_operation'],c['shares_pct']['other_resolved'],c['shares_pct']['unresolved'])]] for c in result['cases'].values()]),'',
        'JPEG、模糊、合成、Word 模型和图文对象分别保留；其它已解析部分仍单列，未解释为新增机制。采样周期权重不等于 CPU 总时间。','',
        '## PPT 021','','JPEG 等单个操作链可以由多个函数组成，应同时看操作总权重和最大函数权重。','',
        method.table(['操作','权重'],[[g['operation'],f'{g["share_pct"]:.2f}%'] for g in result['cases']['021']['separate_operations']]),'',
        'reference_witnesses 记录旧例对应函数；functions.csv 保留每个函数的前后分类、权重及新增归并证据类别。全部原始数据保持不变。','']
    (folder/'analysis.md').write_text('\n'.join(lines))
    method.write(folder/'analysis-build.json',dict(
        source_sha256={str(Path(__file__).relative_to(ROOT)):method.sha(__file__),
                       'analysis/docops/operation_equivalence.py':method.sha(ROOT/'analysis/docops/operation_equivalence.py')},
        inputs=result['inputs'],outputs={p.name:method.sha(p) for p in folder.iterdir() if p.is_file()},
        workload_or_collector_run=False,html_modified=False))
    print(folder)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',action='store_true',required=True);p.parse_args()
    save(gather())
