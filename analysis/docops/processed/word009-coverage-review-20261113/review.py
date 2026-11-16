"""Read-only Word 009 residual/cross-task accounting; no report publication."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'analysis/docops'))
import operation_comparison as method
import operation_equivalence as equivalence


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    unified_path = ROOT / equivalence.INPUT / 'comparison.json'
    data = json.loads(unified_path.read_text())
    assert digest(unified_path) == json.loads(
        (ROOT / equivalence.INPUT / 'analysis-build.json').read_text())['outputs']['comparison.json']
    for name, sha in data['input_sha256'].items():
        assert digest(ROOT / name) == sha, name
    saved = equivalence.load()
    assert equivalence.gather() == saved
    c = saved['cases']['009']
    total = c['roi_period']
    rows = [f for f in c['functions'] if f['bucket'] in ('separate_operation', 'other_resolved')]
    keys = {p: {method.key(f) for f in case['functions']} for p, case in data['cases'].items()}
    originals = [p for p in data['groups'] if p != '009']
    scenarios = {'021': ['021'], '021+029': ['021', '029'],
        '013+016+021+026+029': ['013', '016', '021', '026', '029']}
    for fmt in ('Excel', 'PDF', 'PPT'):
        scenarios['all_original_' + fmt] = [p for p in originals if data['cases'][p]['format'] == fmt]
    scenarios['all_original_nonWord'] = [p for p in originals if data['cases'][p]['format'] != 'Word']
    scenarios['all_sizes_nonWord'] = [p for p, x in data['cases'].items() if x['format'] != 'Word']
    scenarios['001+003_original'] = ['001', '003']
    scenarios['all_other_originals'] = originals
    scenarios['all_other_families_all_sizes'] = [p for p in data['cases'] if not p.startswith('009')]
    cross = {}
    for label, selected in scenarios.items():
        union = set().union(*(keys[p] for p in selected))
        matched = [f for f in rows if method.key(f) in union]
        remaining = [f for f in rows if method.key(f) not in union]
        amount = sum(f['period'] for f in matched)
        assert amount + sum(f['period'] for f in remaining) == sum(f['period'] for f in rows)
        cross[label] = dict(selected=selected, additional_exact_period=amount,
            additional_exact_pp=100 * amount / total,
            supported_pct=c['supported_share_pct'] + 100 * amount / total,
            remaining_resolved_pct=100 * sum(f['period'] for f in remaining) / total,
            unresolved_pct=c['shares_pct']['unresolved'], remaining=remaining)
    groups = Counter()
    for f in rows:
        if f['library'] in ('libswlo.so', 'libsw_writerfilterlo.so'):
            group = 'Writer'
        elif f['tool'].startswith('LibreOffice·'):
            group = 'Office common/graphics'
        elif f['tool'] == 'Python':
            group = 'Python'
        elif f['tool'] in ('lxml', 'XML 组件'):
            group = 'XML'
        else:
            group = 'other'
        groups[group] += f['period']
    writer = [f for f in rows if f['library'] in ('libswlo.so', 'libsw_writerfilterlo.so')]
    nonword_keys = set().union(*(keys[p] for p in scenarios['all_sizes_nonWord']))
    assert all(method.key(f) not in nonword_keys for f in writer)
    assert sum(groups.values()) + c['periods']['exact'] + c['periods']['same_operation'] + c['periods']['unresolved'] == total
    sources = [unified_path, ROOT / equivalence.OUTPUT / 'comparison.json',
        ROOT / 'docops/scaling/cases/009/scripts/update_toc_and_render.py',
        ROOT / 'docops/scaling/cases/009/scripts/validate_incident_manual_variant.py']
    result = dict(target='009-u500', roi_period=total, baseline=c['shares_pct'],
        supported_pct=c['supported_share_pct'], residual_by_owner_pct={k: 100*v/total for k,v in groups.items()},
        writer_function_count=len(writer), writer_functions=writer, cross_task=cross,
        inputs={str(p.relative_to(ROOT)): digest(p) for p in sources},
        interpretation='Preserve existing operation credit. Additional candidates contribute exact identities only; no automatic whole-framework credit. Writer is library ownership, not a measured layout-stage time.',
        checks=dict(input_hashes_checked=254, partitions_conserved=True, writer_absent_in_all_nonWord=True),
        report_modified=False, html_modified=False, workload_or_collector_run=False)
    out = Path(__file__).with_name('review.json')
    assert not out.exists(), 'Do not overwrite prior review'
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    note = '# Word 009 大档剩余权重核对\n\n'
    note += '76.25% 为旧 OPM＋TLC 精确函数匹配与已声明同类操作之和。新增候选只计其余函数中的精确匹配；分母与未知权重不变。\n\n'
    note += '| 剩余归属 | ROI 周期权重 |\n|---|---|\n'
    note += ''.join(f'| {k} | {100*v/total:.2f}% |\n' for k,v in groups.items())
    note += f'| 未解析 | {c["shares_pct"]["unresolved"]:.2f}% |\n\n'
    note += '| 补充范围 | 009 大档覆盖权重 |\n|---|---|\n'
    note += ''.join(f'| {k} | {v["supported_pct"]:.2f}% |\n' for k,v in cross.items())
    note += '\nWriter 两库未匹配函数共 8.08%，在本批全部非 Word 配置中均未见精确匹配。库归属不等于全部属于排版算法；其中包含 DOCX 导入、段落／表格对象和布局路径。\n\n'
    note += '这部分有的原被放在 Office 公共组件，属于重新拆组，不能与原对象／布局样式 5.99% 相加。\n\n'
    note += '结论：只加 PPT 不能补足 Word 操作。若同时补充幻灯片对象／拼图和 Word 连续文档／表格／目录排版，建议 021＋009；不是全部函数的严格最小集合覆盖解。\n'
    Path(__file__).with_name('review.md').write_text(note)
    index = {p.name: digest(p) for p in Path(__file__).parent.iterdir() if p.is_file()}
    Path(__file__).with_name('sha256-index.json').write_text(json.dumps(index, indent=2) + '\n')
    print(json.dumps(dict(target=result['target'], residual_by_owner_pct=result['residual_by_owner_pct'],
        writer_functions=len(writer), scenarios={k:v['supported_pct'] for k,v in cross.items()},
        checks=result['checks']), ensure_ascii=False))


if __name__ == '__main__':
    main()
