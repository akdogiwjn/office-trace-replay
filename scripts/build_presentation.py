#!/usr/bin/env python3
"""Build a self-contained HTML briefing from the current qualified report data."""
import argparse
import hashlib
from html import escape
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CONFIG = 'analysis/hotspots/comparison-inputs-pdf5-20261027.json'
TITLE = '文档解析类 Agent 代表性评估报告'
LABELS = dict(opm='OPM', **{'opm-n10': 'OPM'}, irs_w4='IRS W-4', sba1919='SBA 1919',
              tlc='TLC', hr_metro='HR Metro', egrid='eGRID', industry_productivity='Industry Productivity')
PDF = ('opm-n10', 'irs_w4', 'sba1919')
XLSX = ('tlc', 'hr_metro', 'egrid', 'industry_productivity')
BOUNDS = ('Bad Speculation', 'Frontend Bound', 'Backend Bound', 'Retiring')
COLORS = ('#346a9f', '#cf792d', '#347d55', '#b3464c')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def text(value):
    return escape(str(value), quote=True)


def code(value):
    return '<code>' + text(value) + '</code>'


def pct(value):
    return f'{100 * value:.2f}%'


def table(headers, rows, cls=''):
    return '<table class="' + cls + '"><thead><tr>' + ''.join('<th>' + text(v) + '</th>' for v in headers) + \
        '</tr></thead><tbody>' + ''.join('<tr>' + ''.join('<td>' + str(v) + '</td>' for v in row) + '</tr>' for row in rows) + '</tbody></table>'


def bullets(items):
    return '<ul>' + ''.join('<li>' + v + '</li>' for v in items) + '</ul>'


def note(value):
    return '<p class="takeaway">' + value + '</p>'


def resolved_functions(profile, limit):
    return [r for r in profile['functions'] if r['library'] != 'unknown'
            and r['function'] not in ('[unknown]', '[no-frame]')
            and not re.fullmatch(r'0x[0-9a-fA-F]+|[0-9a-fA-F]{12,}', r['function'])][:limit]


def interval_svg(series, dataset):
    """Draw the original points; separate runs without interpolation or smoothing."""
    runs = sorted((r for r in series['runs'] if r['dataset_id'] == dataset), key=lambda r: r['repeat'])
    if [r['repeat'] for r in runs] != [1, 2, 3, 4, 5]:
        raise ValueError('five runs required for curve: ' + dataset)
    parts = []
    offset = 0
    for run in runs:
        points = run['points']
        if [p['sample_index'] for p in points] != list(range(1, len(points) + 1)):
            raise ValueError('noncontiguous curve source')
        xs = [offset + p['sample_index'] for p in points]
        parts.append((run, xs))
        offset = xs[-1] + 2
    width, height = 1120, 398
    left, right, top, bottom = 60, 1098, 62, 338
    x = lambda v: left + (v - 1) / max(1, offset - 3) * (right - left)
    y = lambda v: bottom - v / 100 * (bottom - top)
    output = [f'<svg class="curve" viewBox="0 0 {width} {height}" role="img" aria-label="{text(LABELS[dataset])} 五轮真实采样点曲线">',
              '<rect width="1120" height="398" fill="white"/>']
    for value in range(0, 101, 20):
        yy = y(value)
        output += [f'<line x1="{left}" y1="{yy:.2f}" x2="{right}" y2="{yy:.2f}" stroke="#dce2e8"/>',
                   f'<text x="{left-12}" y="{yy+5:.2f}" text-anchor="end" font-size="16">{value}</text>']
    for index, metric in enumerate(BOUNDS):
        xx = 70 + index * 264
        output += [f'<line x1="{xx}" y1="16" x2="{xx+24}" y2="16" stroke="{COLORS[index]}" stroke-width="3"/>',
                   f'<text x="{xx+32}" y="21" font-size="17">{text(metric)}</text>']
    for index, (run, xs) in enumerate(parts):
        start, end = x(xs[0]), x(xs[-1])
        if index % 2 == 0:
            output.append(f'<rect x="{start:.2f}" y="{top}" width="{end-start:.2f}" height="{bottom-top}" fill="#64748b" opacity=".035"/>')
        output.append(f'<text x="{(start+end)/2:.2f}" y="49" text-anchor="middle" font-size="16">第 {run["repeat"]} 轮</text>')
        if index:
            bx = x(xs[0] - 1.5)
            output.append(f'<line x1="{bx:.2f}" y1="{top}" x2="{bx:.2f}" y2="{bottom}" stroke="#8492a3" stroke-dasharray="3 4"/>')
        for m, metric in enumerate(BOUNDS):
            pairs = [(x(xx), y(point['metrics'][metric])) for xx, point in zip(xs, run['points'])]
            output.append('<polyline class="series" data-repeat="' + str(run['repeat']) + '" data-metric="' + text(metric) +
                          '" data-point-count="' + str(len(pairs)) + '" fill="none" stroke="' + COLORS[m] +
                          '" stroke-width="1.5" points="' + ' '.join(f'{a:.2f},{b:.2f}' for a, b in pairs) + '"/>')
        output += [f'<text x="{start:.2f}" y="360" text-anchor="middle" font-size="14">{xs[0]}</text>',
                   f'<text x="{end:.2f}" y="360" text-anchor="middle" font-size="14">{xs[-1]}</text>']
    output += ['<text x="32" y="53" font-size="16">%</text>',
               '<text x="580" y="388" text-anchor="middle" font-size="17">采样点序号（五轮依次展示；名义输出间隔 1 秒）</text>', '</svg>']
    return ''.join(output)


def load_inputs(root):
    sources = {}
    def read(path, expected=None):
        path = Path(path)
        digest = sha(root / path)
        if expected is not None and digest != expected:
            raise ValueError('presentation source hash mismatch: ' + str(path))
        sources[str(path)] = digest
        return json.loads((root / path).read_text())
    config = read(CONFIG)
    output = Path(config['output'])
    build = read(output / 'build.json')
    if build['config_sha256'] != sha(root / CONFIG):
        raise ValueError('report build belongs to a different config')
    comparison = read(output / 'comparison.json', build['output_sha256']['comparison.json'])
    for path, expected in build['document_sha256'].items():
        if sha(root / path) != expected:
            raise ValueError('report document changed: ' + path)
        sources[path] = expected
    joint = comparison['joint_comparison']
    binding = config['joint_comparison']
    if read(binding['path'], binding['sha256']) != joint:
        raise ValueError('embedded and qualified joint results differ')
    series = read(joint['time_series']['path'], joint['time_series']['sha256'])
    if len(series['runs']) != 35 or set(joint['statistics']) != set(LABELS) - {'opm-n10'}:
        raise ValueError('expected current seven-dataset five-run results')
    if {p['image_id'] for p in comparison['profiles'].values()} != {joint['image_id']}:
        raise ValueError('mixed image evidence')
    pdf_top5 = [{(r['library'], r['function']) for r in resolved_functions(comparison['profiles'][ds], 5)} for ds in PDF]
    if any(len(s) != 5 for s in pdf_top5) or any(s != pdf_top5[0] for s in pdf_top5[1:]):
        raise ValueError('PDF Top-5 headline must agree with current qualified data')
    return config, comparison, joint, series, sources


def make_slides(config, comparison, joint, series):
    profiles = comparison['profiles']
    stats = joint['statistics']
    pairs = joint['pairs']
    by_target = {r['target']: r for r in pairs}
    presentation = comparison['presentation']
    env = joint['measurement_methodology']['replay_environment']
    slides = []
    def add(title, body, section='研究结果', subtitle='', cls=''):
        slides.append(dict(title=title, body=body, section=section, subtitle=subtitle, cls=cls))
    def shared(ds):
        return by_target[ds]['common_top10_count']
    def mean(ds, metric):
        return stats[ds]['statistics'][metric]['mean']
    def cv_range(metric, datasets=XLSX):
        values = [stats[ds]['statistics'][metric]['cv_percent'] for ds in datasets]
        return f'{min(values):.2f}%–{max(values):.2f}%'
    cosine_range = f'{min(r["bound_cosine"] for r in pairs):.6f}–{max(r["bound_cosine"] for r in pairs):.6f}'
    add(TITLE, '<p class="lead">跨领域真实输入下的 CPU 负载特征与场景覆盖</p>' +
        '<div class="cover-facts"><p>7 个真实输入数据集</p><p>每例、每路 5 次独立运行</p><p>perf 热点 ＋ DevKit Topdown</p></div>' +
        note('验证主要计算机制的延续，明确下一步场景扩展方向。'),
        section='汇报版', subtitle='PDF 表单处理 · XLSX 大型工作簿增强', cls='cover')
    add('关键发现：跨领域输入延续主要计算机制', table(['观察维度', '主要结果'], [
        ['PDF 热点', f'W-4、SBA 与 OPM 共享 <strong>{shared("irs_w4")}／{shared("sba1919")}</strong> 个 Top-10 函数'],
        ['XLSX 热点', f'HR、eGRID、Industry 与 TLC 共享 <strong>{shared("hr_metro")}／{shared("egrid")}／{shared("industry_productivity")}</strong> 个 Top-10 函数'],
        ['Topdown 顶层分配', f'五组 Bound 余弦：<strong>{cosine_range}</strong>'],
        ['同环境重复波动', f'XLSX IPC CV：{cv_range("IPC")}；Backend CV：{cv_range("Backend Bound")}']]) +
        note('结果支持已测 PDF／XLSX 任务的跨领域代表性。'), section='关键结论')
    add('研究问题与验证设计', bullets([
        '研究问题：更换业务输入后，原有 PDF／XLSX 的主要 CPU 计算机制是否延续？',
        '对照基准：OPM 表单、TLC 工作簿；新增五个真实业务输入。',
        '共同任务：PDF 批量填写与渲染；XLSX 保留原表并新增 Summary、公式、情景和图表。',
        '验证路径：真实 Agent 轨迹 → 容器回放 → 两路独立测量 → 五轮对比。']) +
        note('先验证同类任务的跨领域延续，再讨论办公场景覆盖。'), section='实验设计')
    add('XLSX：交通、能源、就业与产业生产率', table(['数据集', '领域／发布方', '输入规模'], [
        ['TLC（基准）', '交通出行／NYC TLC', '7 张表；主表 10 万行 × 25 列，约 250 万单元格'],
        ['eGRID', '电力能源／EPA', '11 张表；约 273 万非空单元格'],
        ['HR Metro', '就业工资／BLS', '4 张表；主表约 15 万条、32 列，约 421 万非空单元格'],
        ['Industry Productivity', '产业生产率／BLS', '3 张表；长表约 56.7 万条，约 580 万非空单元格']]) +
        bullets(['选择依据：真实公开来源、自然业务指标、百万级单元格规模。',
                 'TLC 沿用原业务工作簿；新三例保留发布方原始工作表及数据。']), section='数据集')
    add('PDF：雇佣、税务与小企业贷款表单', table(['数据集', '业务与冻结版本', '页数', '字段数'], [
        ['OPM OF-306（基准）', '联邦雇佣申报；08/2023', '3', '38'],
        ['IRS W-4', '所得税预扣；2026', '5', '48'],
        ['SBA Form 1919', '小企业贷款；04/2024 可填写版', '7', '127']]) +
        bullets(['保留公开表单的真实页面、字段类型与结构差异。',
                 '每轮处理 10 条虚构记录，统一执行映射、填写、渲染和验证。']), section='数据集')
    add('轨迹来源：真实 Agent 执行并冻结成功结果', bullets([
        '原 OPM／TLC 沿用原任务与回放材料。',
        '新增五例由 OpenClaw Agent 实际执行，每例独立提示词与业务 helper。',
        'Agent 调用 Skill 完成任务，保存工具调用、生成脚本及修订。',
        '成功轨迹绑定输入、提示词、Skill、环境与验收结果。']) +
        note('轨迹形成任务依据；回放阶段直接执行冻结脚本和工具，不再调用模型。'), section='轨迹与回放')
    add('容器回放：共同的 P01–P04 执行形态', table(['阶段', 'XLSX', 'PDF'], [
        ['P01 检查输入', '结构、特征与原始工作簿检查', '可填写字段检查、抽取、模板渲染'],
        ['P02 生成内容', '业务 helper 新增 Summary、公式、情景和图表', '业务 helper 生成十条记录的字段值'],
        ['P03 重算／批处理', 'LibreOffice 重算，公式／缓存检查，导出 CSV', '逐条填写、逐页渲染'],
        ['P04 验证与交付', '指标、缓存、CSV、交付物验证与摘要', '填写字段、保护字段、PDF／PNG 验证']]) +
        note('正式循环包含 reset 与循环内验证；归档和独立审计在测量循环外。'), section='轨迹与回放', cls='compact')
    add('统一实验环境与容器边界', table(['项目', '配置'], [
        ['处理器', 'HiSilicon HIP09；aarch64；2 路 × 64 核 × 2 线程，4 个 NUMA 节点'],
        ['宿主／容器', 'openEuler；共享宿主内核 '+code(joint['measurement_methodology']['host']['kernel'])],
        ['文档工具', f'Python {text(env["python"])}；openpyxl {text(env["packages"]["openpyxl"])}；LibreOffice {text(env["libreoffice"])}；Poppler {text(env["poppler"])}'],
        ['采集工具', 'perf 6.6.0；DevKit 26.0.RC1'],
        ['CPU 布局', 'workload：逻辑 CPU 0–7；控制／监测：CPU 9'],
        ['容器', '同一固定镜像；每次新建容器；无网络；不挂载覆盖 workload 源码']]) +
        '<p class="small">镜像 '+code('office-trace-replay:agent-traces')+'；实际 ID '+code(joint['image_id'])+'</p>', section='测量方法', cls='compact')
    add('两路测量：分别回答“执行什么”与“流水线特征”', table(['测量', '范围与配置', '统计口径'], [
        ['perf 热点', '回放命令及其后代进程／线程；cycles:u，49 Hz，DWARF 调用栈', '各轮正式 ROI 的原始 period 合并；按脚本、库、物理叶函数统计'],
        ['DevKit Topdown', '按逻辑 CPU 0–7 计数；名义 1 秒输出；另行执行', '每轮 ALL 汇总；五轮均值、标准差、CV']]) +
        bullets(['每路 35 次：7 例 × 5 次；两路共 70 次独立运行。',
                 'PDF 每次处理 10 份；XLSX 每次执行 1 轮。',
                 '核对容器身份、业务成功、ROI／包络、导出完整性和来源哈希。']) +
        '<p class="small">perf 为用户态周期占比；DevKit 为按核 PMU 包络，两者分别解释。</p>', section='测量方法', cls='compact')
    add('相似度：函数集合与流水线分配相互印证', table(['比较量', '输入与计算', '用途'], [
        ['热点重合／Jaccard', '各自 Top-10 的“库类别＋函数名”；交集数 ÷ 并集数', '主要函数集合是否延续'],
        ['Bound 余弦', 'Bad Speculation、Frontend、Backend、Retiring 四维均值；点积 ÷ 模长乘积', '顶层流水线分配形状'],
        ['十维欧氏距离', 'IPC＋四顶层＋四子层＋idle；混合单位，仅辅助展示', '补充数值差异']]) +
        note('Topdown 相似度取五轮 ALL 的均值；过程曲线使用逐秒输出，两者用途不同。') +
        '<p class="small">各指标均值、样本标准差和 CV 分开统计；函数权重不进入 Jaccard，不将三种度量拼成总分。</p>', section='分析方法', cls='compact')
    pdfproc = {ds: {r['script']: r['share_roi'] for r in profiles[ds]['processes']} for ds in PDF}
    add('PDF 热点脚本：转换、填写、渲染与验证', table(['实际脚本／进程', *[LABELS[n] for n in PDF]], [
        [code(name), *[pct(pdfproc[ds].get(name, 0)) for ds in PDF]] for name in
        ('convert_pdf_to_images.py', 'fill_fillable_fields.py', 'pdftoppm', 'verify_pdf_batch.py')]) +
        note('三类表单共同进入相同工具链；页面与字段差异改变各部分权重。'), section='热点对比')
    def function_rows(group):
        names = PDF if group == 'PDF' else XLSX
        title = next(k for k in presentation['function_tables'] if k.startswith(group))
        rows = [r for r in presentation['function_tables'][title] if r['reference_rank'] is not None]
        cells = []
        for row in rows:
            values = []
            for ds in names:
                item = row['datasets'][ds]
                values.append('未采到' if item['share_roi'] is None else pct(item['share_roi']) + (' <b>✓</b>' if item['top10'] else ''))
            cells.append([str(row['reference_rank'])+'. '+code(row['function']), *values])
        return table([group+' 基准 Top-10', *[LABELS[n] for n in names]], cells, 'functions')
    add('PDF 热点函数：Top-5 集合持续重合', function_rows('PDF') +
        '<p class="small">按 OPM Top-10 排序；✓ 表示该函数进入对应数据集的 Top-10。</p>' +
        note('主要机制：Python 解释执行、zlib 压缩编码、Pillow 缩放与编码。'), section='热点对比', cls='dense')
    roles = {ds: {r['role']: r['share_roi'] for r in presentation['xlsx_process_groups'][ds]} for ds in XLSX}
    role_groups = [('输入检查 · inspect_xlsx_structure.py／inspect_xlsx_features.py', ('结构检查', '特征检查')),
                   ('业务增强 · enhance_workbook.py／各例 helper', ('业务增强',)),
                   ('重算与公式／缓存检查 · recalc.py／inspect_xlsx_*.py', ('重算与缓存扫描', '公式检查', '缓存值检查')),
                   ('循环验证 · verify_xlsx_enhanced.py', ('循环内业务验证',)),
                   ('摘要／CSV · write_xlsx_summary.py／export_xlsx_csv.py', ('摘要生成', 'CSV 导出')),
                   ('LibreOffice 主进程 · soffice.bin', ('LibreOffice 主进程',))]
    add('XLSX 热点脚本：按执行职责归并对比', table(['职责与对应脚本', *[LABELS[n] for n in XLSX]], [
        [text(label), *[pct(sum(roles[ds].get(role, 0) for role in keys)) for ds in XLSX]] for label, keys in role_groups], 'roles') +
        note('共同工作包括检查、业务增强、保存、重算和验证；业务处理与公共检查分别列示。'), section='热点对比', cls='compact')
    add('XLSX 热点函数：对象与解释器机制延续', function_rows('XLSX') +
        '<p class="small">按 TLC Top-10 排序；✓ 表示进入对应数据集的 Top-10。各例 libpython 约占 ROI 用户态周期的 79%–82%。</p>' +
        note('主要机制：解释执行、字典查找、对象遍历、垃圾回收和对象释放。'), section='热点对比', cls='dense')
    libs = {n: {r['library']: r['share_roi'] for r in profiles[n]['libraries']} for n in profiles}
    add('库级证据：共同热点对应实际文档处理工作',
        '<div class="columns"><div><h3>PDF</h3>'+table(['库', 'OPM', 'W-4', 'SBA'],
            [[text(lib), *[pct(libs[n].get(lib, 0)) for n in PDF]] for lib in ('libpython','zlib','Pillow','Poppler','FreeType')])+
        '</div><div><h3>XLSX</h3>'+table(['库', 'TLC', 'HR', 'eGRID', 'Industry'],
            [[text(lib), *[pct(libs[n].get(lib, 0)) for n in XLSX]] for lib in ('libpython','LibreOffice','expat','ElementTree','zlib')])+'</div></div>'+
        note('PDF 以解释、压缩和图像处理为主；XLSX 以对象管理、XML 解析及工作簿工具为主。'), section='热点对比', cls='compact')
    add('Topdown 特征：顶层分配总体接近', table(['数据集','IPC','Bad Spec.','Frontend','Backend','Retiring'], [
        [LABELS[ds],f'{mean(ds,"IPC"):.2f}',*[f'{mean(ds,m):.2f}%' for m in BOUNDS]] for ds in stats]) +
        note('七例均以 Backend Bound 为最大的顶层分类。') +
        '<p class="small">表中为五次最终 ALL 的均值；IPC 无量纲，其他为百分比。粗粒度分类接近不等于全部具体瓶颈一致。</p>', section='Topdown 对比', cls='compact metrics')
    add('五组新旧对照：函数与 Topdown 同时比较', table(['基准 → 新输入','共同 Top-10','Jaccard','Bound 余弦'], [
        [text(LABELS[r['reference']]+' → '+LABELS[r['target']]),f"<b>{r['common_top10_count']}/10</b>",
         f"{r['hotspot_jaccard']:.4f}",f"{r['bound_cosine']:.6f}"] for r in pairs]) +
        note('跨领域输入改变排名和权重，主要热点集合与顶层流水线形状保持接近。') +
        '<p class="small">余弦比较四个顶层 Bound；Jaccard 比较函数成员；不要求权重完全相等。</p>', section='代表性验证')
    add('五轮重复：检验同环境下结果的稳定性', table(['数据集','IPC CV','Backend CV','两两 Top-10 共同数'], [
        [LABELS[ds],f"{stats[ds]['statistics']['IPC']['cv_percent']:.2f}%",f"{stats[ds]['statistics']['Backend Bound']['cv_percent']:.2f}%",
         f"{joint['hotspot_repeatability'][ds]['pairwise_common_min']}–{joint['hotspot_repeatability'][ds]['pairwise_common_max']}/10"] for ds in stats]) +
        note('XLSX 主要特征重复接近；PDF 合并五轮识别持续热点，单轮排名波动单独保留。'), section='代表性验证', cls='compact')
    add('覆盖边界：下一步应扩展操作类型', table(['已测任务', '已观测机制', '待补充的操作'], [
        ['PDF 表单填写与渲染', '解释执行、压缩、图像处理、Poppler／字体', '连续文档的重新排版与分页'],
        ['XLSX 大型工作簿增强', '对象管理、GC、XML、Calc', '幻灯片对象、母版、图形与布局构建']]) +
        bullets(['七例支持这两类任务的跨领域代表性。',
                 '下一步由“更换业务输入”扩展到“改变文档操作”。']) +
        note('Word/PPT 用于检验尚未充分覆盖的排版与图形计算机制。'), section='场景扩展')
    add('Word/PPT：主流需求与可测的计算差异', table(['场景','实际需求依据','可能补足的计算机制'], [
        ['Word', 'Copilot 产品落地；公开 Benchmark 提供文档编辑任务', '连续文本流、字体度量、复杂表格与分页；Writer 路径'],
        ['PPT', 'Copilot 产品落地；PPT-Eval 提供 120 个任务', '幻灯片对象、母版与图片布局、图形渲染；Impress 路径']]) +
        '<p class="small">公开任务：OmegaUse-OfficeVal 中 Word 37 项、PowerPoint 39 项；DocOps 覆盖四种办公格式，共 210 项任务。</p>'+
        note('共享 XML、LibreOffice 或 Poppler，仍可能进入不同的文档模型与函数路径。'), section='场景扩展')
    add('结论与下一步', bullets([
        '<strong>已验证：</strong>PDF 表单与 XLSX 增强在跨领域真实输入下延续主要热点机制。',
        '<strong>证据：</strong>脚本／库／函数热点、Top-10 重合、Topdown 特征和五轮波动相互印证。',
        '<strong>下一步：</strong>由真实 Agent 执行 Word/PPT 任务，冻结轨迹并在统一环境回放。',
        '<strong>补充测量：</strong>排版与图形路径热点、CPU-seconds、任务时长、活跃核数与内存峰值。']) +
        note('跨领域代表性已有实测依据；办公场景覆盖继续向排版与图形构建扩展。'), section='汇报结论')
    # Curves are optional appendix pages; every original interval point is retained.
    for ds in ('opm','irs_w4','sba1919',*XLSX):
        runs = [r for r in series['runs'] if r['dataset_id'] == ds]
        counts = [len(r['points']) for r in sorted(runs,key=lambda r:r['repeat'])]
        add('附录 · '+LABELS[ds]+' 五轮 Topdown 过程曲线', interval_svg(series,ds)+
            '<p class="small">每轮输出点数：'+text('／'.join(map(str,counts)))+'。每条线为一个指标；轮间断开；不平滑、不插值。保留采集启动／停止包络。</p>'+
            '<p class="small">相似度采用各轮 ALL 的均值；本页用于查看过程变化。</p>', section='附录曲线', cls='chart-slide')
    add('附录 · 来源与复核入口', bullets([
        '本汇报取自七例五轮的当前正式报告与机器结果；测量和统计口径保持不变。',
        '<a href="https://github.com/akdogiwjn/office-trace-replay/blob/main/docs/representativeness-assessment.md" target="_blank" rel="noopener">代表性评估报告</a>：完整实验环境、轨迹、回放与方法。',
        '<a href="https://github.com/akdogiwjn/office-trace-replay/blob/main/docs/experimental-results.md" target="_blank" rel="noopener">实验数据汇总记录</a>：逐轮指标、实际命令、完整排名与哈希索引。'])+
        '<p class="small">Word/PPT 选型依据：<a href="https://huggingface.co/datasets/baidu-frontier-research/OmegaUse-OfficeVal" target="_blank" rel="noopener">OmegaUse-OfficeVal</a> · '+
        '<a href="https://microsoft.github.io/ppteval/" target="_blank" rel="noopener">PPT-Eval</a> · '+
        '<a href="https://github.com/icip-cas/DocOps" target="_blank" rel="noopener">DocOps</a> · '+
        '<a href="https://learn.microsoft.com/en-us/microsoft-365/copilot/wordexcelppt-agents" target="_blank" rel="noopener">Microsoft Copilot</a></p>'+
        '<p class="small">HTML 图表与样式全部内嵌，离线放映无需访问这些链接。</p>', section='来源')
    return slides


CSS = r'''
:root{font-family:"Noto Sans CJK SC","Microsoft YaHei","PingFang SC",Arial,sans-serif;color:#182535;background:#e9edf2;font-synthesis:none}
*{box-sizing:border-box}body{margin:0}button,select{font:inherit}a{color:#215a8c;text-decoration:underline;text-underline-offset:3px}
.viewport{height:calc(100vh - 50px);width:100vw;display:flex;align-items:center;justify-content:center;overflow:hidden}
.deck{position:relative;width:1280px;height:720px;flex:none;transform-origin:center center}
.slide{position:absolute;inset:0;background:white;padding:35px 56px 54px;display:flex;flex-direction:column;overflow:hidden}
.slide[hidden]{display:none}.eyebrow{font-size:17px;color:#48637e;letter-spacing:1px;margin:0 0 12px;border-top:5px solid #245b88;padding-top:13px}
h1{font-size:36px;line-height:1.3;margin:0 0 24px;font-weight:700;letter-spacing:.1px}.subtitle{font-size:20px;color:#53677e;margin:-10px 0 20px}
.content{flex:1;min-height:0;display:flex;flex-direction:column;gap:12px;font-size:25px;line-height:1.55}.content>p{margin:0}ul{margin:0;padding-left:1.2em}li{padding:6px 0;line-height:1.55}strong,b{color:#174d78}
.takeaway{margin-top:auto!important;border-left:5px solid #245b88;background:#f0f5f9;padding:14px 18px;font-size:24px;line-height:1.45;font-weight:500}
table{border-collapse:collapse;width:100%;font-size:22px;line-height:1.45;table-layout:auto}th{background:#edf3f8;text-align:left;font-weight:600;color:#244d70}th,td{padding:12px 13px;border-bottom:1px solid #d9e1e9;vertical-align:middle}td:not(:first-child){font-variant-numeric:tabular-nums}td:first-child{font-weight:500}
code{font-family:"DejaVu Sans Mono",Consolas,monospace;font-size:.77em;overflow-wrap:anywhere}.small{font-size:17px;line-height:1.5;color:#53677e}.compact table{font-size:20px}.compact th,.compact td{padding:10px 12px}.compact .content{font-size:23px}.dense table{font-size:18px;line-height:1.25}.dense th,.dense td{padding:6px 9px}.dense code{font-size:16px}.dense .takeaway{font-size:22px;padding:10px 14px}.dense .small{font-size:16px}
.functions td:first-child{width:43%}.roles td:first-child{width:42%;font-size:17px}.columns{display:grid;grid-template-columns:1fr 1.1fr;gap:30px}.columns h3{font-size:24px;margin:0 0 12px}.columns table{font-size:18px}.columns th,.columns td{padding:10px 8px}.columns td:first-child{width:28%}
.metrics th,.metrics td{padding:8px 12px}
.footer{position:absolute;left:56px;right:56px;bottom:18px;display:flex;justify-content:space-between;color:#697b8c;font-size:14px;border-top:1px solid #e1e7ed;padding-top:8px}.footer .number{font-variant-numeric:tabular-nums}.cover h1{font-size:43px;margin-top:26px}.cover .lead{font-size:30px;color:#335a7a}.cover-facts{display:flex;gap:44px;flex-wrap:wrap;margin-top:46px;color:#244d70;font-size:26px}.cover-facts p{margin:0;border-top:2px solid #b6c9da;padding-top:15px}.cover .takeaway{margin-bottom:20px}
.curve{width:100%;height:auto;display:block;max-height:415px;font-family:Arial,"Noto Sans CJK SC",sans-serif}.chart-slide h1{font-size:33px}.chart-slide .content{gap:8px}
.toolbar{height:50px;display:flex;align-items:center;justify-content:center;gap:10px;padding:6px 12px;background:white;border-top:1px solid #ccd7e0;font-size:14px}.toolbar button,.toolbar select{border:1px solid #b9c9d6;background:white;color:#244d70;border-radius:3px;padding:5px 10px;cursor:pointer}.toolbar button:disabled{opacity:.4;cursor:default}.toolbar select{max-width:390px}.toolbar .hint{color:#687b8d;margin-left:10px}.toolbar button:focus-visible,.toolbar select:focus-visible{outline:3px solid #63a3d6;outline-offset:2px}.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}
@media(max-width:700px){.toolbar .hint{display:none}.toolbar select{max-width:36vw}.toolbar{gap:5px}.toolbar button{padding:5px 7px}}
@page{size:338.6667mm 190.5mm;margin:0}
@media print{html,body{background:white;width:1280px!important}.toolbar{display:none!important}.viewport{display:block;width:1280px;height:auto;overflow:visible}.deck{position:static;transform:none!important;width:1280px;height:auto}.slide,.slide[hidden]{display:flex!important;position:relative;inset:auto;width:1280px;height:720px;break-after:page;page-break-after:always;print-color-adjust:exact;-webkit-print-color-adjust:exact}.slide:last-child{break-after:auto;page-break-after:auto}}
'''

JS = r'''
(() => {
  const slides = [...document.querySelectorAll('.slide')];
  const deck = document.getElementById('deck');
  const picker = document.getElementById('slide-picker');
  const previous = document.getElementById('previous');
  const next = document.getElementById('next');
  const announcement = document.getElementById('announcement');
  let index = 0;
  const hashIndex = () => {
    const match = location.hash.match(/^#slide=(\d+)$/);
    return match ? Number(match[1]) - 1 : 0;
  };
  function show(requested, updateHash = true) {
    index = Math.max(0, Math.min(slides.length - 1, requested));
    slides.forEach((slide, i) => {
      slide.hidden = i !== index;
      slide.setAttribute('aria-current', String(i === index));
    });
    picker.value = String(index);
    previous.disabled = index === 0;
    next.disabled = index === slides.length - 1;
    announcement.textContent = `第 ${index + 1} 页，共 ${slides.length} 页：${slides[index].dataset.title}`;
    if (updateHash) {
      try { history.replaceState(null, '', '#slide=' + (index + 1)); }
      catch (_) { location.hash = 'slide=' + (index + 1); }
    }
  }
  function resize() {
    const view = document.querySelector('.viewport');
    const scale = Math.max(.1, Math.min(view.clientWidth / 1280, view.clientHeight / 720));
    deck.style.transform = `scale(${scale})`;
  }
  async function fullscreen() {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else if (document.documentElement.requestFullscreen) await document.documentElement.requestFullscreen();
      else announcement.textContent = '浏览器不支持全屏，可使用浏览器自带全屏功能。';
    } catch (_) { announcement.textContent = '请使用浏览器的全屏功能。'; }
  }
  previous.addEventListener('click', () => show(index - 1));
  next.addEventListener('click', () => show(index + 1));
  picker.addEventListener('change', () => show(Number(picker.value)));
  document.getElementById('fullscreen').addEventListener('click', fullscreen);
  document.getElementById('print').addEventListener('click', () => window.print());
  window.addEventListener('hashchange', () => show(hashIndex(), false));
  window.addEventListener('resize', resize);
  document.addEventListener('fullscreenchange', resize);
  document.addEventListener('keydown', event => {
    if (event.altKey || event.ctrlKey || event.metaKey || /^(INPUT|SELECT|TEXTAREA)$/.test(event.target.tagName)) return;
    if (['ArrowRight', 'ArrowDown', 'PageDown', ' '].includes(event.key)) { event.preventDefault(); show(index + 1); }
    else if (['ArrowLeft', 'ArrowUp', 'PageUp'].includes(event.key)) { event.preventDefault(); show(index - 1); }
    else if (event.key === 'Home') { event.preventDefault(); show(0); }
    else if (event.key === 'End') { event.preventDefault(); show(slides.length - 1); }
    else if (event.key.toLowerCase() === 'f') { event.preventDefault(); fullscreen(); }
    else if (event.key.toLowerCase() === 'p') { event.preventDefault(); window.print(); }
  });
  show(hashIndex(), false);
  resize();
})();
'''


def render(slides, metadata):
    sections = []
    for i, slide in enumerate(slides, 1):
        sections.append(f'<section class="slide {text(slide["cls"])}" data-title="{text(slide["title"])}" id="slide-{i}"'+
            (' hidden' if i > 1 else '')+' aria-label="'+text(f'第 {i} 页：{slide["title"]}')+'">'+
            '<p class="eyebrow">'+text(slide['section'])+'</p><h1>'+text(slide['title'])+'</h1>'+
            ('<p class="subtitle">'+text(slide['subtitle'])+'</p>' if slide['subtitle'] else '')+
            '<div class="content">'+slide['body']+'</div><footer class="footer"><span>'+TITLE+
            '</span><span class="number">'+str(i)+' / '+str(len(slides))+'</span></footer></section>')
    options = ''.join(f'<option value="{i}">{i+1}. {text(s["title"])}</option>' for i,s in enumerate(slides))
    embedded = json.dumps(metadata, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    return ('<!doctype html>\n<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'+
        '<title>'+TITLE+'</title><style>'+CSS+'</style></head><body>'+\
        '<main class="viewport"><div class="deck" id="deck">'+''.join(sections)+'</div></main>'+\
        '<nav class="toolbar" aria-label="放映控制"><button id="previous" type="button">上一页</button>'+\
        '<label class="sr-only" for="slide-picker">选择页面</label><select id="slide-picker">'+options+'</select>'+\
        '<button id="next" type="button">下一页</button><button id="fullscreen" type="button">全屏 F</button>'+\
        '<button id="print" type="button">打印 / PDF</button><span class="hint">← / → 翻页 · Home / End 首尾页</span></nav>'+\
        '<p id="announcement" class="sr-only" aria-live="polite"></p>'+\
        '<script type="application/json" id="presentation-provenance">'+embedded+'</script><script>'+JS+'</script>'+\
        '<noscript><style>.slide[hidden]{display:flex}.slide{position:relative}.deck,.viewport{height:auto;display:block;overflow:visible}</style>'+\
        '<p>JavaScript 未启用，已改为连续阅读模式。</p></noscript></body></html>\n')


def build(root=ROOT):
    root = Path(root)
    config, comparison, joint, series, sources = load_inputs(root)
    slides = make_slides(config, comparison, joint, series)
    metadata = dict(schema='representativeness-html-presentation-v1', title=TITLE, slide_count=len(slides),
        image_id=joint['image_id'], sources=sources,
        generator_sha256=sha(Path(__file__)), measurement_changes=False,
        interval_policy='Original points retained; five separate polylines per metric; no smoothing or interpolation.')
    destination = root / 'docs/representativeness-assessment.html'
    destination.write_text(render(slides, metadata))
    manifest = root / 'docs/evidence/presentation.json'
    manifest.write_text(json.dumps(dict(**metadata, output=dict(path=str(destination.relative_to(root)), sha256=sha(destination)),
        slide_titles=[s['title'] for s in slides]), ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(dict(output=str(destination), slides=len(slides), bytes=destination.stat().st_size,
                         sha256=sha(destination)), ensure_ascii=False))
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    build()


if __name__ == '__main__':
    main()
