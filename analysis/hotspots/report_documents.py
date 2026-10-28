"""Publish an explanatory assessment and a separate complete experiment record."""
import hashlib
import json
import os
from pathlib import Path
import re

LABELS = dict(opm='OPM', **{'opm-n10': 'OPM'}, irs_w4='IRS W-4', sba1919='SBA 1919',
              tlc='TLC', hr_metro='HR Metro', egrid='eGRID', industry_productivity='Industry Productivity')
BOUNDS = ('Bad Speculation', 'Frontend Bound', 'Backend Bound', 'Retiring')


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |', '|' + '---|' * len(headers),
                      *['| ' + ' | '.join(str(v).replace('|', '&#124;') for v in row) + ' |' for row in rows]])


def subsection(text, heading):
    match = re.search(r'^' + re.escape(heading) + r'\n', text, re.M)
    if not match:
        raise ValueError('required generated section missing: ' + heading)
    level = len(heading) - len(heading.lstrip('#'))
    end = re.search(r'^#{1,' + str(level) + r'} ', text[match.end():], re.M)
    return text[match.end():match.end() + end.start() if end else len(text)].strip()


def pct(value):
    return f'{100 * value:.2f}%'


def coverage_chapter():
    return '''## 六、Word/PPT 的场景扩展价值

### 6.1 从跨领域延续性转向操作类型覆盖

前面的五组对照表明：沿用表单处理与工作簿增强任务时，跨领域输入仍持续进入解释器、对象管理、XML、压缩和渲染等共同路径。因此，继续只更换业务行业，未必能补充新的主要计算类型。下一步应扩展实际操作，重点考察当前较少涉及的连续文档排版和幻灯片图形布局。

### 6.2 主流场景与实际任务需求

| 证据层次 | 来源与事实 | 对场景选择的意义 |
|---|---|---|
| 生态采用 | 2026-10-28 保存的 Skills.sh 快照：Anthropic DOCX 约 20.85 万、PPTX 约 24.38 万 Installs。[DOCX](https://www.skills.sh/anthropics/skills/docx)、[PPTX](https://www.skills.sh/anthropics/skills/pptx) | 说明相应工具能力有较多采用；Installs 不等于独立用户 |
| 产品落地 | 微软将 Word、PowerPoint 文件创建纳入 Copilot Agent。[产品说明](https://learn.microsoft.com/en-us/microsoft-365/copilot/wordexcelppt-agents) | 说明文字报告和演示材料属于实际产品任务 |
| 公开任务覆盖 | OmegaUse-OfficeVal 的 100 项任务按输出类型包含 Word 37 项、PowerPoint 39 项，另有 1 项 Word＋Excel 跨文件任务。[数据集](https://huggingface.co/datasets/baidu-frontier-research/OmegaUse-OfficeVal) | 提供具体可复现任务；任务集比例不推导市场使用比例 |
| 专项任务 | PPT-Eval 提供 120 个 PowerPoint 创建与编辑任务，覆盖 12 个文件。[项目页](https://microsoft.github.io/ppteval/) | 为幻灯片构建和编辑提供独立评测任务 |
| 跨格式操作 | DocOps 发布 210 项 Excel、Word、PowerPoint、PDF 文档操作任务。[官方仓库](https://github.com/icip-cas/DocOps) | 支持沿原生文档编辑与结果验证选取任务 |

### 6.3 新操作可能补足的 CPU 机制

| 操作 | 工具／软件模块 | 实际计算行为 | 后续关注的热点与指标 |
|---|---|---|---|
| Word 长文档创建、段落和样式修改 | DOCX Skill 的结构处理工具；LibreOffice Writer `sw` | 维护段落／表格结构；内容或样式变化后进行文本布局、字体度量、换行与分页 | 结构构建、布局／字体函数；CPU 核秒、内存、缓存和分支指标 |
| Word 复杂表格、页眉页脚与导出 | Writer 文档模型及布局；PDF 导出 | 计算连续文本流与跨页对象的位置，生成页面描述 | 排版与页面生成的 CPU 工作量、Frontend／Backend 分布 |
| PPT 模板编辑、幻灯片构建 | PPTX Skill；PptxGenJS／Node.js 或 OOXML 编辑；Impress `sd` | 组织幻灯片、母版、文本框、形状、图片及资源关系，计算对象布局 | 对象构建、运行时对象管理、图形／文本布局函数 |
| PPT 渲染与可见性检查 | Impress、Poppler、Pillow | 绘制文本和矢量形状、处理图片、生成缩略图 | 图形、字体、栅格化与图像处理热点，CPU 核秒与内存峰值 |

上述链路依据公开 [DOCX Skill](https://github.com/anthropics/skills/blob/main/skills/docx/SKILL.md)、[PPTX Skill](https://github.com/anthropics/skills/blob/main/skills/pptx/SKILL.md) 及 LibreOffice 的 [Writer](https://github.com/LibreOffice/core/blob/master/sw/README.md)、[Impress](https://github.com/LibreOffice/core/blob/master/sd/README.md)、[Calc](https://github.com/LibreOffice/core/blob/master/sc/README.md) 模块说明整理，是待测机制的选型依据。

同样调用 LibreOffice，Calc、Writer、Impress 进入的文档模型和布局路径不同；同样进入 Poppler，文本、矢量对象与图片的构成也可能改变字体与渲染计算。公共组件能够解释部分共同热点，却不能替代对这些操作的实测。

### 6.4 下一轮实验要回答的问题

选择长文档结构／样式编辑、分页与复杂表格，以及多页幻灯片构建／模板编辑／图形布局任务；由真实 Agent Skill 完成并冻结成功轨迹，在统一环境下回放。继续以 perf 识别主要函数与工具归属，以固定版本 DevKit 比较流水线特征，并增加同一版本的 CPU-seconds、任务时长、活跃核数和内存峰值。

下一轮重点检验：Writer／Impress 的布局、字体和图形路径是否成为显著热点；这些工作占多少绝对 CPU 工作量；共享压缩、XML 和渲染机制之外，是否出现 PDF 表单与 XLSX 增强尚未充分覆盖的主导机制。**已有七例用于验证跨领域输入下的机制延续，Word/PPT 用于扩展操作类型的覆盖。**'''


def render_assessment(config, profiles, presentation, joint, full_markdown, record_link, figure_link):
    assessment = config['assessment']
    pairs = joint['pairs']
    stats = joint['statistics']
    means = lambda ds, m: stats[ds]['statistics'][m]['mean']
    by_target = {p['target']: p for p in pairs}
    shared = lambda ds: by_target[ds]['common_top10_count']
    xlsx_ids = ('tlc', 'hr_metro', 'egrid', 'industry_productivity')
    def cv_range(metric):
        values = [stats[ds]['statistics'][metric]['cv_percent'] for ds in xlsx_ids]
        return f'{min(values):.2f}%–{max(values):.2f}%'
    top5 = {ds: [r for r in profiles[ds]['functions'] if r['library'] != 'unknown'
                 and r['function'] not in ('[unknown]', '[no-frame]')][:5]
            for ds in ('opm-n10', 'irs_w4', 'sba1919')}
    common5 = len(set.intersection(*[{(r['library'], r['function']) for r in rows} for rows in top5.values()]))
    environment = subsection(joint['measurement_section'], '### 4.1 硬件、软件与容器')
    # Remove only the detailed platform discussion; the complete configuration table remains.
    environment = environment.split('\n\n硬件平台')[0]
    lines = ['# 文档解析类 Agent 代表性评估报告', '',
        '## 一、研究目标与关键发现', '',
        '本评估考察：保留 PDF 批量表单处理和 XLSX 大型工作簿增强任务，更换真实业务输入后，'
        '原基准的主要 CPU 计算机制是否延续。进一步据此识别办公 Agent 尚未覆盖的操作类型，为 Word/PPT 场景选型提供依据。', '',
        table(['关键发现', '实测证据', '含义'], [
            ['PDF 的主要热点延续', f'W-4／SBA 与 OPM 共享 {shared("irs_w4")}／{shared("sba1919")} 个 Top-10 函数；三例合并 Top-5 共有 {common5} 个函数', '解释执行、压缩编码与图像处理路径共同出现'],
            ['XLSX 的主要热点延续', f'HR Metro／eGRID／Industry 与 TLC 共享 {shared("hr_metro")}／{shared("egrid")}／{shared("industry_productivity")} 个 Top-10 函数', '对象管理、GC、XML 与工作簿处理机制延续'],
            ['顶层流水线分配接近', f'五组 Bound 余弦 {min(p["bound_cosine"] for p in pairs):.6f}–{max(p["bound_cosine"] for p in pairs):.6f}', '支持粗粒度分配形状接近，结合函数证据解释'],
            ['固定环境下可重复', f'每例、每路各五次；XLSX IPC CV {cv_range("IPC")}，Backend CV {cv_range("Backend Bound")}', '主要结果在同环境重复运行中保持接近']]), '',
        '**主要判断：在本次任务形态和工具链下，跨业务领域输入没有明显改变主要原生热点集合。'
        '任务操作与软件执行路径，是解释 CPU 负载特征的重要线索。** 这里验证的是同类任务的跨领域代表性；'
        '整个办公 Agent 的场景覆盖还需要检验文档排版与幻灯片构建等不同操作。', '',
        f'本报告完整说明实验设计、测量与结论；逐轮数值、完整热点排名、采样点、命令和证据索引见[实验数据汇总记录]({record_link})。', '',
        '## 二、数据集选择与任务设计', '',
        '选择同时考虑官方或公开可信来源、业务领域、工作簿规模和任务可执行性。XLSX 从交通扩展到电力能源、区域就业工资和产业生产率；'
        'PDF 从联邦雇佣申报扩展到税务预扣和小企业贷款申请。', '',
        table(['XLSX 数据集', '领域与来源', '冻结输入规模', '任务'], assessment['xlsx_datasets']), '',
        table(['PDF 数据集', '领域与发布机构', '冻结版本', '页数／字段／批处理'], assessment['pdf_datasets']), '',
        'TLC 沿用基于真实行程记录构建的原业务工作簿；三个新增 XLSX 保留发布方原始工作簿。'
        '百万级单元格规模为解析、对象构建和保存提供实际工作量，既有业务指标用于新增 Summary、公式、情景和图表。'
        'PDF 使用公开可填写表单与十条虚构记录，覆盖不同页面和字段规模，统一执行字段映射、填写、渲染和验证。', '',
        '来源依据包括 [TLC 行程数据](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)、'
        '[EPA eGRID](https://www.epa.gov/egrid/detailed-data)、[BLS OEWS](https://www.bls.gov/oes/tables.htm)、'
        '[BLS 生产率表](https://www.bls.gov/productivity/tables/home.htm)、'
        '[OPM OF-306](https://www.opm.gov/forms/pdf_fill/of0306.pdf)、'
        '[IRS W-4](https://www.irs.gov/forms-pubs/about-form-w-4) 和 '
        '[SBA 1919](https://www.sba.gov/document/sba-form-1919-borrower-information-form)。'
        '原始表数量、数据布局及表单页数差异保留；领域多样性用于检验任务机制的延续。', '',
        '## 三、实验环境、轨迹来源与回放流程', '', '### 3.1 硬件、软件与容器', '', environment, '',
        '### 3.2 真实 Agent 轨迹来源', '',
        'TLC／OPM 沿用原有任务与回放材料。五个新增用例由 OpenClaw Agent 实际执行；每例使用独立提示词，'
        '明确业务任务、输入、输出和验收要求。Agent 编写业务 helper 并调用 Skill，保存 trajectory、tool events、脚本修订、'
        '输入／提示词及运行环境绑定，选择成功轨迹用于回放。', '',
        table(['新增用例', '采用的成功轨迹', 'Agent 业务脚本'],
              [[r[0], '`'+r[1]+'`', '`'+r[2]+'`'] for r in assessment['trace_sources']]), '',
        '### 3.3 容器内轨迹回放', '',
        '一个固定镜像支持七例：旧 OPM／TLC 使用 `document-oe/run.py`，新增五例由 `agent/replay.py` 调度私有 runner。'
        '每例独立保存输入、业务脚本、Skill、recipe 和 verifier。轨迹中的内联代码整理为独立脚本，回放执行冻结脚本与工具，不再调用模型。', '',
        table(['阶段', 'XLSX', 'PDF'], [
            ['P01 输入检查', '结构、特征检查，读取原工作簿', '可填写检查、字段抽取、模板渲染'],
            ['P02 业务内容', '业务 helper 新增 Summary、公式、情景、图表并保存', '业务 helper 生成十条记录的字段值'],
            ['P03 重算／批处理', '`recalc.py` → LibreOffice，公式／缓存检查，导出本轮 CSV', '逐记录填写、逐页渲染'],
            ['P04 验证与交付', '指标、缓存、CSV 和交付物验证，生成摘要', '填写字段、保护字段、PDF／PNG 与批次验证']]), '',
        '每轮重建工作区。正式循环包含 reset、P01–P04 和循环内验证；归档、哈希及循环外独立审计位于循环外。'
        '旧 43 个 workload 文件保持冻结字节与权限。', '',
        '## 四、采集方法与分析方法', '', '### 4.1 两路独立采集', '',
        table(['测量', '实际对象', '轮次与范围', '汇总'], [
            ['perf 热点', '回放命令及其后代进程／线程', '七例各五个独立容器；每次一轮，PDF 每轮 N=10；共 35 次', '正式 ROI 原始 sample period 合并，再计算用户态周期占比'],
            ['DevKit Topdown', '宿主逻辑 CPU 0–7，按核计数', '相同七例各五次，另行执行，共 35 次', '每轮最终 ALL 报告 → 均值、样本标准差和 CV']]), '',
        'perf 采集命令在容器内执行，由它启动回放；没有 `-a`、`-C` 或 `-p`。CPU 0–7 是进程允许运行的位置，'
        '控制和身份监测在 CPU 9。DevKit 则明确按 CPU 0–7 统计，可能包含这些 CPU 上的其他宿主活动。', '',
        '```bash',
        '# 容器内：目标回放命令与后代任务；固定 venv Python 执行实际回放。',
        'perf record -e cycles:u -F 49 -k mono --call-graph dwarf,16384 \\',
        '  -o /results/perf.data -- taskset -c 0-7 <回放命令>',
        'perf script --no-inline --ns -F +pid -i /results/perf.data',
        '', '# 容器内：控制器位于 CPU 9；对 CPU 0–7 计数。',
        'stdbuf -oL -eL /devkit/devkit tuner top-down -c 0-7 -L 0 -i 1 -l 0',
        '```', '',
        '新用例的 `<回放命令>` 为固定 Python 执行 `agent/replay.py --dataset <id> --loops 1` 并传入结果目录和容器 inspect；'
        '旧用例由 `legacy_capture.py` 包装原入口记录相同循环边界。逐次实参见数据记录。', '',
        '`cycles:u` 只覆盖目标任务用户态执行；以 CLOCK_MONOTONIC 的循环标记筛选 ROI，未知项保留在分母。'
        '同镜像导出物理栈，按物理叶函数独占计数并关联脚本和库。它描述采样周期分布，不直接等于总 CPU 时间。', '',
        'DevKit 在首次完成 PMU 读取后放行循环，循环结束后 SIGINT 停止并取得 ALL。'
        '保留启动／停止包络，不将按核 PMU 百分比视为严格 ROI 过滤。`-i 1` 为名义一秒输出，`-l 0` 为 debug 日志；'
        '未显式指定 `-r`，采用工具默认权限范围。idle 由循环门控前后 `/proc/stat` 单独计算。', '',
        '### 4.2 向量、函数集合与相似度', '',
        '```text', 'v = [IPC, Bad Speculation, Frontend Bound, Backend Bound, Retiring,',
        '     Core Bound, Memory Bound, Fetch Latency Bound, Fetch Bandwidth Bound, idle_pct]', '```', '',
        '每维取五轮最终结果的算术均值；IPC 无量纲，其余用 0–100 的百分数，不做标准化。'
        '均值 `μ=Σx/5`；样本标准差 `s=√(Σ(x−μ)²/4)`；`CV=100s/|μ|`。', '',
        table(['比较量', '输入与公式', '解释'], [
            ['Bound 余弦', '只取四顶层 Bound：`(a·b)/(‖a‖‖b‖)`', '比较粗粒度分配形状，避免重复计入父子项'],
            ['热点 Jaccard', '五轮 period 合并排序，取 Top-10「库类别＋物理叶函数」；`|A∩B|/|A∪B|`', '比较主要函数成员，权重不进入集合运算'],
            ['原始欧氏距离', '十维向量：`√Σ(aᵢ−bᵢ)²`', '含混合单位和父子层级，仅作辅助，不拼成总分']]), '',
        '### 4.3 执行、采样与结果核验', '',
        '每次要求请求／完成／成功／失败＝1／1／1／0、循环业务验证成功，并核对实际 Docker inspect、输入与 recipe 绑定。'
        'perf 栈与无栈导出逐样本交叉核验、ROI 内外 period 守恒；Topdown 校验顶层与子层分区，五轮统计从原始结果复算。'
        '丢样、未知符号和未计数事件保留记录，不补算缺失权重。43 个旧 workload、35 次各路采集、来源与报告哈希均有核验记录。'
        'SMT／事件复用语义待核验项与按核包络限制随数据记录保留。', '',
        '## 五、实验结果与代表性分析', '', '### 5.1 主要脚本、库与计算机制', '',
        '下表按执行职责归并实际脚本。占比为完整 ROI 的已观测用户态 sample period；业务处理与检查／验证分列，避免把公共检查成本直接归为业务计算。', '']
    pdfnames = ['opm-n10', 'irs_w4', 'sba1919']
    xlsxnames = ['tlc', 'hr_metro', 'egrid', 'industry_productivity']
    process_maps = {n: {r['script']: r['share_roi'] for r in profiles[n]['processes']} for n in pdfnames}
    lines += [table(['PDF 职责／脚本', *[LABELS[n] for n in pdfnames]], [
        [label, *[pct(sum(process_maps[n].get(s, 0) for s in scripts)) for n in pdfnames]]
        for label, scripts in [('转换 `convert_pdf_to_images.py`', ['convert_pdf_to_images.py']),
                              ('填写 `fill_fillable_fields.py`', ['fill_fillable_fields.py']),
                              ('渲染 `pdftoppm`', ['pdftoppm']),
                              ('验证 `verify_pdf_batch.py`', ['verify_pdf_batch.py'])]]), '']
    roles = {n: {r['role']: r['share_roi'] for r in presentation['xlsx_process_groups'][n]} for n in xlsxnames}
    grouped = [('输入检查 `inspect_xlsx_structure.py / inspect_xlsx_features.py`', ('结构检查', '特征检查')),
               ('业务增强 `enhance_workbook.py / enhance_*_v*.py`', ('业务增强',)),
               ('重算 `recalc.py`，公式／缓存检查 `inspect_xlsx_*.py`', ('重算与缓存扫描', '公式检查', '缓存值检查')),
               ('循环验证 `verify_xlsx_enhanced.py`', ('循环内业务验证',)),
               ('摘要／CSV `write_xlsx_summary.py / export_xlsx_csv.py`', ('摘要生成', 'CSV 导出')),
               ('LibreOffice 主进程 `soffice.bin`', ('LibreOffice 主进程',))]
    lines += [table(['XLSX 职责／脚本', *[LABELS[n] for n in xlsxnames]], [
        [name, *[pct(sum(roles[n].get(k, 0) for k in keys)) for n in xlsxnames]] for name, keys in grouped]), '',
        '这些行为是完整工具 workload 的组成部分：PDF 验证占约 10%–12%，XLSX 验证占约 10%–12%，'
        '共同机制同时出现在业务 helper、检查、重算和验证。表中的 `recalc.py` 包含其 Python 缓存检查，'
        '`soffice.bin` 为单列的子进程，不能将两者脚本归属混成同一份周期。未归属线程与剩余小项在数据记录中单列。', '']
    for title, names, libs in [('PDF', pdfnames, ('libpython', 'zlib', 'Pillow', 'Poppler', 'FreeType')),
                               ('XLSX', xlsxnames, ('libpython', 'LibreOffice', 'expat', 'ElementTree', 'zlib'))]:
        maps = {n: {r['library']: r['share_roi'] for r in profiles[n]['libraries']} for n in names}
        lines += [table([title + ' 主要原生库', *[LABELS[n] for n in names]],
                        [[lib, *[pct(maps[n].get(lib, 0)) for n in names]] for lib in libs]), '']
    lines += ['PDF 的主要机制为 Python 解释执行、zlib 压缩和 Pillow 图像处理，伴随 Poppler／FreeType 渲染。'
              'XLSX 以 libpython 为主，并持续出现 XML 解析和 LibreOffice 路径；这把函数重合与实际工具工作联系起来。', '',
              '### 5.2 主要热点函数与跨领域重合', '',
              '★ 为原基准 Top-10，按原排名列出；粗体为该函数在各例中的权重，✓ 表示仍进入该例 Top-10。'
              '新例额外进入 Top-10 的函数及完整排名保存在数据记录中。', '']
    for group in config['groups']:
        names = group['datasets']
        rows = [r for r in presentation['function_tables'][group['title']] if r['reference_rank'] is not None]
        def cell(row, name):
            v = row['datasets'][name]
            return '未采到' if v['share_roi'] is None else '**' + pct(v['share_roi']) + (' ✓' if v['top10'] else '') + '**'
        lines += [table([('PDF' if names[0] == 'opm-n10' else 'XLSX') + ' 基准热点', *[LABELS[n] for n in names]],
            [[f"★ {r['reference_rank']} · `{r['library']} / {r['function']}`", *[cell(r, n) for n in names]] for r in rows]), '']
    lines += [f'三种 PDF 五轮合并 Top-5 共有 {common5} 个函数，对应解释器、zlib 匹配／编码和 Pillow 缩放／编码；'
              '各自 Top-5 累计 ROI 占比为 '+ '、'.join(LABELS[ds]+' '+pct(sum(r['share_roi'] for r in rows)) for ds,rows in top5.items())+'。XLSX 的共同函数包括解释器、字典查找、'
              '对象遍历、GC 和对象释放。这里的共同热点说明主要计算类型延续，允许各输入有不同排名和权重。', '',
              '### 5.3 Topdown 特征与相似度', '',
              table(['数据集', 'IPC', 'Bad Spec.', 'Frontend', 'Backend', 'Retiring'],
                    [[LABELS[ds], f'{means(ds,"IPC"):.2f}', *[f'{means(ds,m):.2f}%' for m in BOUNDS]] for ds in stats]), '',
              table(['基准 → 新输入', 'Top-10 共同函数', 'Jaccard', 'Bound 余弦', '十维欧氏距离（辅助）'],
                    [[LABELS[p['reference']]+' → '+LABELS[p['target']], f"{p['common_top10_count']}/10",
                      f"{p['hotspot_jaccard']:.4f}", f"{p['bound_cosine']:.6f}", f"{p['raw_euclid_auxiliary']:.3f}"] for p in pairs]), '',
              '七例均以 Backend Bound 为最大的顶层分类；五组余弦接近 1，与主要热点的延续相互补充。'
              'Backend 是粗粒度分类，不能单独推出具体瓶颈一致，也不代表执行效率或 CPU 核秒相同。', '',
              '### 5.4 逐采样点过程与五轮稳定性', '',
              '下图每条线对应一个顶层指标，横轴为真实采样点；各轮按编号顺序串联展示，轮间留空、分别标注。'
              '保留初始与结束包络，不平滑、不补点。不同数据集耗时不同，横轴不用于强行对齐同一执行阶段。', '']
    for f in joint['figures']:
        if not f.get('detail'):
            lines += [f"![{f['title']}]({figure_link(f)})", '', f['caption'], '']
    lines += [table(['数据集', 'IPC CV', 'Backend CV', '五轮两两 Top-10 共同数'],
        [[LABELS[ds], f"{stats[ds]['statistics']['IPC']['cv_percent']:.2f}%",
          f"{stats[ds]['statistics']['Backend Bound']['cv_percent']:.2f}%",
          f"{joint['hotspot_repeatability'][ds]['pairwise_common_min']}–{joint['hotspot_repeatability'][ds]['pairwise_common_max']}/10"] for ds in stats]), '',
        'XLSX 的主要特征与热点集合在固定环境重复运行中接近；PDF 单轮热点排名更易波动，五轮合并用于识别持续出现的主要函数。'
        f'例如 OPM Fetch Bandwidth CV 为 {stats["opm"]["statistics"]["Fetch Bandwidth Bound"]["cv_percent"]:.2f}%，因此稳定性按指标分别描述。曲线展示轮内变化，均值和 CV 仍来自每轮 ALL；'
        '两者分别回答过程变化与重复波动。', '',
        '## 六、已有实验的覆盖边界与 Word/PPT 扩展价值', '',
        '### 6.1 已验证的范围与尚未覆盖的操作', '',
        table(['场景', '操作范围', '已知或待测的机制'], [
            ['PDF，已测', '可填写表单的字段映射、填写、渲染和验证', '已观察到 Python、压缩编码、图像处理、Poppler／字体路径'],
            ['XLSX，已测', '百万级单元格工作簿检查、增强、保存、重算、验证', '已观察到解释执行、对象管理、GC、XML、Calc 路径'],
            ['Word，待测', '长文档结构编辑、样式与复杂表格、分页', '待检验连续文本布局、字体度量、跨页布局的显著性'],
            ['PPT，待测', '幻灯片构建、母版编辑、形状与图片布局', '待检验演示对象构建、图形布局与渲染的显著性']]), '',
        '现有结果支持两类已测任务的跨领域代表性，尚未覆盖完整 PDF／XLSX 任务空间。'
        '共同解释器和库函数可由业务处理及公共检查共同贡献，不能仅凭函数名称推断相同上层算法。'
        '当前统计以相对周期与流水线分配为主，绝对 CPU 工作量需要同一版本的 CPU-seconds 等补充；不混用旧版本账本。', '']
    # Merge the extended argument into chapter six, avoiding a disconnected seventh chapter.
    coverage = coverage_chapter()
    coverage = coverage.split('### 6.1 从跨领域延续性转向操作类型覆盖\n\n', 1)[1]
    coverage = coverage.replace('### 6.2 主流场景与实际任务需求', '### 6.2 为什么选择 Word/PPT')
    lines += [coverage, '', f'完整数据、逐次命令和核验材料：[实验数据汇总记录]({record_link})。']
    return '\n'.join(lines).rstrip() + '\n'


def extend_record(full_markdown, config, profiles, joint, root, record_path):
    rel = lambda p: os.path.relpath(root / p, record_path.parent)
    text = full_markdown.replace('# 文档解析类 Agent 代表性评估报告', '# 文档解析类 Agent 实验数据汇总记录', 1)
    text = text.split('\n## 七、代表性覆盖的缺口：Word 与 PPT', 1)[0].rstrip()
    text = text.replace('## 五、热点函数对比与代表性评估', '## 五、完整热点对比记录')
    text = text.replace('本评估以原有 PDF', '本记录保存七例五轮实验的详细方法与数据。结论与论证见[代表性评估报告](representativeness-assessment.md)。\n\n本评估以原有 PDF', 1)
    extra = ['','## 七、逐轮指标、完整排名与采样点','',
             '以下数值直接取自合格的逐轮结果；过程曲线保留全部九个 PMU 指标，idle 只有整轮门控值，不重建逐秒 idle。','']
    for ds, data in joint['statistics'].items():
        extra += ['### '+LABELS[ds]+'：五轮最终值','',
            table(['指标','R1','R2','R3','R4','R5','均值','样本标准差','CV%'], [
                [m,*[f'{v:.6f}' for v in row['values']],f"{row['mean']:.6f}",
                 '未定义' if row['sample_standard_deviation'] is None else f"{row['sample_standard_deviation']:.6f}",
                 '未定义' if row['cv_percent'] is None else f"{row['cv_percent']:.6f}"]
                for m,row in data['statistics'].items()]),'']
    for name, profile in profiles.items():
        extra += ['### '+LABELS[name]+'：合并物理函数 Top-20','',
            table(['排名','库','物理叶函数','完整 ROI 用户态 period 占比'],
                [[i,row['library'],'`'+row['function']+'`',pct(row['share_roi'])]
                 for i,row in enumerate([r for r in profile['functions'] if r['library']!='unknown' and r['function'] not in ('[unknown]','[no-frame]')][:20],1)]),'']
    extra += ['### 各轮逐采样点数据','',
        f"原始点、时间戳、Cycles／Instructions 和 ALL 汇总见[time-series.json]({rel(joint['time_series']['path'])})。"
        f"共 {joint['time_series']['runs']} 轮、{joint['time_series']['points']:,} 个编号报告；原始日志 SHA256 逐轮绑定。"
        '序号连续性、最终汇总一致性与指标分区已校验。整数计数相加与 ALL 最多容许 1 个打印计数单位偏差，实际差值保存在 JSON，不修正数值。','']
    # Overview curves already occur in the complete generated material; details belong here.
    for f in joint['figures']:
        if f.get('detail'):
            extra += [f"![{f['title']}]({rel(f['path'])})",'',f['caption'],'']
    extra += ['## 八、70 次采集与完整来源索引','',
              '每一条 collection 保存实际采集 argv、工作负载结果、ROI／包络、采集质量；对应 raw 目录下还保存 Docker inspect、'
              '原始 stdout、stderr、解析结果和 SHA256 索引。这里列出逐次来源，完整参数不靠示例命令推断。', '',
              '### perf：35 次独立采集','',
              table(['数据集','重复','ROI 样本数','ROI period','collection（实际命令与质量）'],
                  [[LABELS[r['dataset_id']],r['repeat'],r['roi_samples'],r['roi_period'],
                    '[collection]('+rel(r['raw']+'/out/collection.json')+')'] for r in joint['measurement_methodology']['hotspot_captures']]),'',
              '### DevKit：35 次独立采集','',
              table(['数据集','重复','ROI 秒','启动包络上界秒','停止包络上界秒','实际命令／状态'],
                  [[LABELS[r['dataset_id']],r['repeat'],f"{r['roi_seconds']:.6f}",
                    f"{r['startup_envelope_upper_seconds']:.6f}",f"{r['tail_envelope_upper_seconds']:.6f}",
                    '[profiler]('+rel(r['raw']+'/out/profiler-record.json')+') / [collection]('+rel(r['raw']+'/out/collection.json')+')']
                   for r in joint['measurement_methodology']['topdown_captures']]),'',
              '### 机器数据与核验入口','',
              '- [相似度完整数据]('+rel(config['joint_comparison']['path'])+')：十维向量、配对、排除项和来源。',
              '- [perf 完整函数与脚本数据]('+rel(config['output']+'/comparison.json')+')：包含未展示的小项与未知项。',
              '- [Topdown 原始统计]('+rel(joint['sources']['topdown_statistics']['path'])+')、[35 次核验]('+rel(joint['sources']['topdown_verification']['path'])+')。',
              '- [测量来源哈希清单](evidence/report-split.json)：本次离线拆分、逐采样点导出与测量结果不变检查。','',
              '原始 perf／DevKit 大文件保存在本地 analysis raw 目录，Git 不上传大文件；清单和派生统计保持可追溯。'
              'PMU 公式经验复算、SMT／事件复用和包络边界说明见第四、六节及上述机器记录。','']
    return text + '\n' + '\n'.join(extra)


def publish(config, profiles, presentation, joint, full_markdown, root, report_path):
    root = Path(root)
    declaration = config['document_outputs']
    record_path = root / declaration['experiment_record']
    if (root / declaration['assessment']).resolve() != report_path.resolve():
        raise ValueError('assessment output differs from declared document path')
    if record_path.parent.resolve() != report_path.parent.resolve():
        raise ValueError('assessment and experiment record must share a documentation directory')
    rel = lambda p: os.path.relpath(root / p, report_path.parent)
    assessment = render_assessment(config, profiles, presentation, joint, full_markdown,
                                   rel(declaration['experiment_record']), lambda f: rel(f['path']))
    record = extend_record(full_markdown, config, profiles, joint, root, record_path)
    report_path.write_text(assessment)
    record_path.write_text(record)
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    return {str(p.relative_to(root)): digest(p) for p in (report_path, record_path)}
