#!/usr/bin/env python3
"""Verify the fresh campaign and update only its tables/version associations."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from script_identity import python_script_operand


ROOT = Path(__file__).resolve().parents[3]
XLSX = ['tlc', 'hr_metro', 'retail_online', 'industry_productivity']
PDF = ['opm', 'irs_w4', 'sba1919']


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def write(path, data):
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def relative(path):
    return str(Path(path).resolve().relative_to(ROOT))


def table(rows, names, labels):
    """Compare actual executed script operands, preserving the full denominator."""
    lines = ['| 脚本／可执行文件 | 主要操作 | ' + ' | '.join(names) + ' |',
             '|---|---|' + '---:|' * len(names)]
    selected = [set() for _ in rows]
    for label, operation, selector in labels:
        values = []
        for i, row in enumerate(rows):
            matches = {index for index, process in enumerate(row['processes'])
                       if (python_script_operand(process['command']) in selector.get('scripts', ())
                           or process['role'] in selector.get('roles', ()))}
            if selected[i] & matches:
                raise ValueError('process assigned to more than one script row')
            selected[i].update(matches)
            seconds = sum(row['processes'][index]['cpu_seconds'] for index in matches)
            values.append(seconds / row['denominator_seconds'])
        lines.append('| ' + label + ' | ' + operation + ' | '
                     + ' | '.join(f'{100*value:.2f}%' for value in values) + ' |')
    other = [sum(process['cpu_seconds'] for index, process in enumerate(row['processes'])
                 if index not in selected[i]) / row['denominator_seconds']
             for i, row in enumerate(rows)]
    lines.append('| 其他进程 | runner、原子执行器及辅助命令等 | '
                 + ' | '.join(f'{100*value:.2f}%' for value in other) + ' |')
    return '\n'.join(lines)


XLSX_LABELS = [
    ('`inspect_xlsx_structure.py`', '输入结构检查', {'scripts': ['inspect_xlsx_structure.py']}),
    ('`inspect_xlsx_features.py`', '输出副本特征检查', {'scripts': ['inspect_xlsx_features.py']}),
    ('`inspect_xlsx_formulas.py`', '公式检查', {'scripts': ['inspect_xlsx_formulas.py']}),
    ('`inspect_xlsx_cached_values.py`', '公式缓存值检查', {'scripts': ['inspect_xlsx_cached_values.py']}),
    ('TLC：`enhance_workbook.py`；新增：`.enhance_workbook.runtime.py`', '工作簿增强',
     {'scripts': ['enhance_workbook.py', '.enhance_workbook.runtime.py']}),
    ('`recalc.py`', '启动重算及 Python 侧缓存检查', {'scripts': ['recalc.py']}),
    ('`soffice.bin` / `oosplash` 及线程', 'LibreOffice 重算、加载与保存', {'roles': ['libreoffice']}),
    ('`verify_xlsx_enhanced.py`', '循环内业务验证', {'scripts': ['verify_xlsx_enhanced.py']}),
    ('`write_xlsx_summary.py`', '生成摘要', {'scripts': ['write_xlsx_summary.py']}),
    ('`export_xlsx_csv.py`', '导出 CSV', {'scripts': ['export_xlsx_csv.py']}),
]
PDF_LABELS = [
    ('`check_fillable_fields.py`', '可填写字段检查', {'scripts': ['check_fillable_fields.py']}),
    ('`extract_form_field_info.py`', '字段信息提取', {'scripts': ['extract_form_field_info.py']}),
    ('OPM：`generate_and_run_batch.py`；新增：`build_field_values.py`', '生成字段映射',
     {'scripts': ['generate_and_run_batch.py', 'build_field_values.py']}),
    ('`run_batch_fill_render.py`', '填写／渲染批处理驱动（仅自身 CPU）', {'scripts': ['run_batch_fill_render.py']}),
    ('`fill_fillable_fields.py`', '填写 PDF', {'scripts': ['fill_fillable_fields.py']}),
    ('`convert_pdf_to_images.py`', 'Python 侧转换与图像处理', {'scripts': ['convert_pdf_to_images.py']}),
    ('`pdftoppm`', 'Poppler 渲染子进程', {'roles': ['pdftoppm']}),
    ('OPM：`verify_pdf_batch.py`；新增：`verify_office.py`', '循环内业务验证',
     {'scripts': ['verify_pdf_batch.py', 'verify_office.py']}),
    ('OPM：`write_pdf_batch_summary.py`；新增：`summary.py`', '生成摘要',
     {'scripts': ['write_pdf_batch_summary.py', 'summary.py']}),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign-dir', type=Path, required=True)
    parser.add_argument('--report-dir', type=Path, required=True)
    args = parser.parse_args()
    campaign = args.campaign_dir.resolve()
    output = args.report_dir.resolve()
    if output.exists():
        raise FileExistsError('report directory already exists; refusing overwrite')
    inventory = read(campaign / 'campaign.json')
    if inventory['status'] != 'success':
        raise ValueError('campaign is incomplete; keep the previous report')
    entries = {item['variant']: item for item in inventory['completed']}
    expected = set(XLSX + [f'{dataset}-n{count}' for dataset in PDF for count in (1, 10)] + ['probe'])
    if set(entries) != expected or len(inventory['completed']) != len(expected):
        raise ValueError('campaign does not contain exactly the requested ten configurations and probe')
    release = read(ROOT / 'reports/formal-image-release.json')
    if inventory['image_id'] != release['image_id']:
        raise ValueError('campaign does not use the formal image')
    results = {}
    for variant, entry in entries.items():
        root = campaign / variant
        if sha(root / 'collection-record.json') != entry['record_sha256']:
            raise ValueError('collection record hash mismatch: ' + variant)
        if sha(root / 'sha256-index.json') != entry['index_sha256']:
            raise ValueError('archive index hash mismatch: ' + variant)
        index = read(root / 'sha256-index.json')
        for item in index['files']:
            path = root / item['path']
            if path.stat().st_size != item['size_bytes'] or sha(path) != item['sha256']:
                raise ValueError('archived file changed: ' + str(path))
        if variant == 'probe':
            continue
        data = read(root / 'analysis.json')
        identity = read(root / 'installed-identity.json')
        inspect = read(root / 'container-inspect.json')
        if data['status'] != 'success' or not all(data['checks'].values()):
            raise ValueError('measurement qualification failed: ' + variant)
        if inspect['Image'] != inventory['image_id'] or inspect['State']['ExitCode'] != 0:
            raise ValueError('container identity/exit mismatch: ' + variant)
        if identity['project_lock_sha256'] != release['image_project_lock_sha256']:
            raise ValueError('installed code differs from the packaged release: ' + variant)
        if abs(sum(data['role_cpu_seconds'].values()) - data['denominator_seconds']) > 1e-8:
            raise ValueError('CPU sum mismatch: ' + variant)
        if abs(sum(data['role_share'].values()) - 1) > 1e-8:
            raise ValueError('CPU share sum mismatch: ' + variant)
        run = next((root / 'workload' / identity['scene']).iterdir())
        summary = read(run / 'summary.json')
        if identity['scene'] == 'pdf':
            count = identity['pdf_count']
            if summary['pdf_applicant_count'] != count:
                raise ValueError('PDF execution count binding mismatch: ' + variant)
            if len(list((root / 'output/filled').glob('*.pdf'))) != count:
                raise ValueError('PDF filled output count mismatch: ' + variant)
        if identity['dataset'] in ('hr_metro', 'retail_online', 'industry_productivity'):
            actual_names = set()
            for process in data['processes']:
                argv = shlex.split(process['command'])
                if len(argv) > 1 and Path(argv[0]).name.startswith('python'):
                    actual_names.add(Path(argv[1]).name)
            required = {'inspect_xlsx_structure.py', 'inspect_xlsx_features.py',
                        'inspect_xlsx_formulas.py', 'inspect_xlsx_cached_values.py',
                        '.enhance_workbook.runtime.py', 'verify_xlsx_enhanced.py',
                        'export_xlsx_csv.py', 'write_xlsx_summary.py'}
            if not required.issubset(actual_names):
                raise ValueError('renamed execution entries not observed: ' + variant + str(required-actual_names))
        data['image_id'] = inventory['image_id']
        data['recipe_sha256'] = identity['recipe_sha256']
        data['collection_record'] = relative(root / 'collection-record.json')
        data['collection_record_sha256'] = sha(root / 'collection-record.json')
        data['archive_index'] = relative(root / 'sha256-index.json')
        data['archive_index_sha256'] = sha(root / 'sha256-index.json')
        waited = data['whole_command_waited_cpu_seconds']
        observed = data['whole_command_observed_cpu_seconds']
        data['whole_command_cpu_crosscheck'] = {
            'waited_seconds': waited, 'observed_seconds': observed,
            'waited_minus_observed_seconds': waited - observed,
            'difference_fraction_of_waited': (waited - observed) / waited if waited else None,
            'scope': 'Whole command including preflight/finalization; not an ROI error bound or a per-role correction.'}
        results[variant] = data
    output.mkdir(parents=True)
    comparison = {'schema_version': 'formal-process-cpu-comparison-v1',
                  'created_at_utc': datetime.now(timezone.utc).isoformat(),
                  'image': inventory['image'], 'image_id': inventory['image_id'],
                  'measurement': 'All observed workload thread user+sys CPU within one complete iteration; /proc polling estimate.',
                  'workload_cpus': list(range(8)), 'monitor_cpu': 9,
                  'nominal_poll_interval_ms': 10, 'workload_source_mounts': [],
                  'campaign': relative(campaign / 'campaign.json'),
                  'campaign_sha256': sha(campaign / 'campaign.json'), 'configurations': results,
                  'independent_acceptance_rerun': False,
                  'limitations': ['Single iteration per configuration; no stability claim.',
                                  'Polling may miss short processes and final CPU counters; no global error bound.',
                                  'Clock-anchor ROI alignment has not been independently calibrated.',
                                  'No native/py-spy profile or read/write CPU ledger was collected.']}
    write(output / 'comparison.json', comparison)
    document = ROOT / 'docs/representativeness-assessment.md'
    shutil.copyfile(document, output / 'previous-representativeness-assessment.md')
    intro = document.read_text().split('## 2. 热点进程占比对比', 1)[0]
    old_intro = '报告只使用已保存的实验结果，没有新增运行或性能采集。'
    intro = intro.replace(old_intro, '进程占比使用 2026-10-26 正式镜像的新采集：四个 XLSX 各一轮，三个 PDF 的 N=1、N=10 各一轮。')
    source = '../' + relative(output / 'comparison.json')
    text = [intro.rstrip(), '', '## 2. 热点进程占比对比', '',
            f"本节全部来自同一正式镜像 `{inventory['image']}`，实际 ID 为 `{inventory['image_id']}`。四个 XLSX 和三个 PDF 的 N=1/N=10 共 10 个配置均各运行一轮，循环内业务验证成功；没有调用 LLM，也没有重跑循环外独立深审。", '',
            '所有表格统一采用整轮 workload 的 user+sys CPU 占比，包含 Python 及 LibreOffice／Poppler 等子进程。分母为正式循环 ROI 内所有已观察 workload 线程的 CPU 计数之和，父子进程、线程不重复计数；不是 py-spy 样本占比，也不是用户态 cycles:u。', '',
            'workload 统一绑定 CPU 0～7，控制程序和监控器使用 CPU 9；按 10 ms 名义间隔轮询 `/proc`，实际间隔记录在 JSON。仅挂载只读测量程序和可写结果目录，没有挂载或覆盖项目源码、runner、输入、Skill 或业务脚本。准备、预检、归档和采集器自身不进入 ROI。', '',
            '### 2.1 XLSX 代表性脚本进程', '',
            table([results[ds] for ds in XLSX], ['TLC（旧基线）','HR Metro','Retail Online','Industry Productivity'], XLSX_LABELS), '',
            '各行按实际执行脚本 basename 归集自身 CPU，四个检查脚本分别统计，不合并为一个检查进程。新用例增强脚本的 `.runtime` 名字来自原子执行临时文件，按实际进程名标注；未将它冒称为旧 TLC 的同一份脚本。', '',
            '同名用于对齐职责，不代表新旧脚本源码完全相同。不同输入保留原始结构，业务 helper、验证细节以及 LibreOffice 内部处理仍可不同。占比接近支持主要进程链的相似性，占比差异则如实保留，不能直接归因于行业。', '',
            '### 2.2 PDF 代表性脚本进程', '',
            'N 表示实际填写和渲染的记录数；N=1 和 N=10 分开比较，两者都准备十份字段映射。转换脚本只计算自身 Python CPU，`pdftoppm` 渲染子进程单列，不重复计数。', '']
    for count in (1,10):
        text += [f'**N={count}：实际填写 {count} 份记录**', '',
                 table([results[f'{ds}-n{count}'] for ds in PDF],
                       ['OPM（旧基线）','IRS W-4','SBA 1919'], PDF_LABELS), '']
    text += ['三种表单使用相同类别的字段检查、提取、填写、转换和渲染工具；字段内容、页数和验证规则不同。上表直接展示各职责在本次完整 CPU 工作中的权重，不能由相同工具名称推断占比必须一致。', '',
             f'数据与逐进程明细见 [正式镜像新采集 JSON]({source})，其中关联每个配置的镜像身份、recipe hash、实际进程命令、输出验证结果、原始索引和分析结果。表格由未舍入数据计算后保留两位小数，显示值之和可能有舍入误差。', '',
             '本次每配置仅一轮，结果是描述性比较。轮询可能遗漏短命进程及退出前最后一段 CPU，尚无整体误差上限；ROI 由容器时钟锚与迭代时间戳对齐，边界误差未独立校准。进程等待不算 CPU；单独记录的整条命令 waited CPU 包含循环外预检／收尾，仅作旁证，不替换表格分母。', '',
             '交叉核对显示，PDF 整条命令的轮询 CPU 比 waited CPU 参考值低约 4.9%～11.7%，XLSX 约低 0.5%～0.6%。差额包含 ROI 内外，不能直接分摊给某个职责，也不是 ROI 误差界。PDF 单轮较短，表中比例适合粗粒度进程结构比较，不用于判断小百分点差异；显示 0.00% 只表示未获得非零计数，不表示该脚本没有执行或实际 CPU 为零。', '',
             '原 TLC/OPM 的主要进程职责在本次新增用例中继续出现，可作为这些固定工具负载的分析起点；这不是对所有文档解析 agent 的覆盖证明，也不证明具体函数权重或优化收益相同。', '']
    temporary = document.with_name(document.name + '.tmp')
    temporary.write_text('\n'.join(text))
    temporary.replace(document)
    shutil.copyfile(document, output / 'comparison-report.md')
    write(output / 'analysis-build.json', {
        'generator': relative(__file__), 'generator_sha256': sha(__file__),
        'collector_sha256': inventory['collector_sha256'], 'monitor_sha256': inventory['monitor_sha256'],
        'cpu_accounting_sha256': inventory['analysis_sha256'],
        'comparison_sha256': sha(output / 'comparison.json'),
        'report_sha256': sha(document), 'previous_report_sha256': sha(output / 'previous-representativeness-assessment.md'),
        'raw_rehashed_and_verified': True, 'workload_rerun_by_this_generator': False})
    print(json.dumps({'status':'success','configurations':len(results),'report':relative(document),
                      'comparison':relative(output/'comparison.json')},ensure_ascii=False))


if __name__ == '__main__':
    main()
