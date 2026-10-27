# 跨领域真实输入下文档解析类agent负载的代表性评估

本报告通过数据集介绍和热点进程占比对比，评估原 TLC/XLSX、OPM/PDF 用例在更换领域及真实输入后的适用范围。进程占比使用 2026-10-26 正式镜像的新采集：四个 XLSX 各一轮，三个 PDF 的 N=1、N=10 各一轮。这里的 agent 负载指从文档任务整理出的固定工具执行负载，回放时不调用 LLM；HR Metro、Retail Online 是人工适配，其余用例保留各自的历史或 Agent 来源。

## 1. 数据集介绍

### 1.1 领域覆盖与 XLSX 规模

XLSX 以原 TLC 用例为基线，扩展到人力资源、在线零售及工业生产率。四个工作簿均保留完整输入，没有通过复制记录或 synthetic shard 扩大新数据集。

| 数据集 | 领域与来源 | 数据内容与输入形态 | 文件大小（MiB） | 工作表数 | 主要工作表规模（行 × 列） | 全工作簿非空单元格数 |
|---|---|---|---:|---:|---|---:|
| TLC（旧基线） | 交通出行；NYC TLC 原始行程数据 | 真实行程样本与预先汇总构建的 benchmark 工作簿；不是官方原生 XLSX | 11.71 | 7 | Raw_Sample：100,001 × 25 | 2,501,211 |
| HR Metro | 人力资源／劳动力；BLS OEWS | May 2025 metropolitan/nonmetropolitan 区域职业、就业和工资统计原始 XLSX | 29.21 | 4 | MSA_M2025_dl：150,024 × 32 | 4,208,869 |
| Retail Online | 零售；UCI Machine Learning Repository | 真实在线零售交易原始 XLSX；541,909 条交易明细，覆盖 2010-12-01 至 2011-12-09 | 22.62 | 1 | Online Retail：541,910 × 8 | 4,198,746 |
| Industry Productivity | 工业生产率；BLS | 保留详细行业长期序列原始 XLSX，任务选择制造业序列；含 Annual 和 MachineReadable 两种表示 | 21.59 | 3 | Annual：15,183 × 46；MachineReadable：566,659 × 9 | 5,798,274 |

表中行数包含表头或说明行；非空单元格数是文件内容规模，不等于独立业务记录数或有效数值数量。Industry Productivity 的长表和宽表是同一发布数据的不同表示，任务计算不重复汇总两者。各输入的原有 Sheet、类型、公式和样式没有统一成相同模板，因此本组是同数量级的真实工作簿比较，不是严格控制所有输入变量的行业实验。

HR Metro 的选区和 Retail Online 的全表过滤、聚合在正式循环外一次准备，冻结为小 JSON。正式循环仍完整加载大工作簿、增加少量摘要／情景／图表、保存、重算及验证；输入准备时间不进入后文的 CPU 分母。TLC 使用预先存在的汇总表，Industry Productivity 引用原始 Annual 表中的选定单元格。

输入来源边界：HR Metro、Retail Online 为用户提供的官方发布渠道下载文件；Industry Productivity 为用户确认从 BLS 官方下载的文件，独立重下载曾返回 HTTP 403，未宣称独立验证官网字节一致。输入字节和来源说明由各自 manifest/provenance 冻结。

### 1.2 PDF 数据集与规模

PDF 以 OPM 的 OF-306 为基线，扩展到工资税务和小企业申请表。表单使用真实发布文件；填写记录是冻结的虚构测试数据，不是实际申请人的个人信息。

| 数据集 | 领域／发布机构 | 冻结版本 | 文件大小（KiB） | 页数 | 可填写字段数 | 准备记录数 | 画像中的实际填写规模 |
|---|---|---|---:|---:|---:|---:|---|
| OPM（旧基线） | 联邦雇佣申报／OPM | OF-306，August 2023 | 248.5 | 3 | 38 | 10 | N=1、N=10 分别比较 |
| IRS W-4 | 工资税务预扣／IRS | Form W-4，2026 | 204.0 | 5 | 48 | 10 | N=1、N=10 分别比较 |
| SBA 1919 | 小企业借款申请／SBA | Form 1919，04/2024，可填写旧版 | 529.7 | 7 | 127 | 10 | N=1、N=10 分别比较 |

N 表示实际填写和渲染的记录数，不是循环次数。两种模式都准备 10 份字段映射，每轮渲染一次模板，并分别填写、渲染实际选择的 N 份记录。SBA 输入实际来自公开的 SBA Box 链接，规范化文字曾与 SBA.gov 旧版核对；没有宣称文件与官网字节一致，也不将其标为当前最新版。

数据集规模与来源依据：[XLSX 输入元数据](../assets/cases/)、[正式用例集合](../suites/default.json)及各用例 `source/datasets/{xlsx,pdf}/<dataset>/` 中的 `manifest.json`、`provenance.json`、`complexity.json`（XLSX）。

## 2. 热点进程占比对比

本节全部来自同一正式镜像 `office-trace-replay:openeuler-release`，实际 ID 为 `sha256:e68ea4ca0e43340b09dd355b4217f756260fe4ae3d33c576fdb0b8ab4d5f437a`。四个 XLSX 和三个 PDF 的 N=1/N=10 共 10 个配置均各运行一轮，循环内业务验证成功；没有调用 LLM，也没有重跑循环外独立深审。

所有表格统一采用整轮 workload 的 user+sys CPU 占比，包含 Python 及 LibreOffice／Poppler 等子进程。分母为正式循环 ROI 内所有已观察 workload 线程的 CPU 计数之和，父子进程、线程不重复计数；不是 py-spy 样本占比，也不是用户态 cycles:u。

workload 统一绑定 CPU 0～7，控制程序和监控器使用 CPU 9；按 10 ms 名义间隔轮询 `/proc`，实际间隔记录在 JSON。仅挂载只读测量程序和可写结果目录，没有挂载或覆盖项目源码、runner、输入、Skill 或业务脚本。准备、预检、归档和采集器自身不进入 ROI。

### 2.1 XLSX 代表性脚本进程

| 脚本／可执行文件 | 主要操作 | TLC（旧基线） | HR Metro | Retail Online | Industry Productivity |
|---|---|---:|---:|---:|---:|
| `inspect_xlsx_structure.py` | 输入结构检查 | 12.57% | 9.60% | 8.62% | 8.24% |
| `inspect_xlsx_features.py` | 输出副本特征检查 | 10.31% | 9.56% | 8.60% | 8.21% |
| `inspect_xlsx_formulas.py` | 公式检查 | 8.45% | 9.40% | 10.53% | 9.75% |
| `inspect_xlsx_cached_values.py` | 公式缓存值检查 | 7.99% | 9.33% | 9.96% | 9.67% |
| TLC：`enhance_workbook.py`；新增：`.enhance_workbook.runtime.py` | 工作簿增强 | 21.39% | 22.40% | 20.61% | 20.36% |
| `recalc.py` | 启动重算及 Python 侧缓存检查 | 11.22% | 12.44% | 12.55% | 12.83% |
| `soffice.bin` / `oosplash` 及线程 | LibreOffice 重算、加载与保存 | 9.08% | 8.28% | 8.55% | 11.15% |
| `verify_xlsx_enhanced.py` | 循环内业务验证 | 10.00% | 9.77% | 10.59% | 10.22% |
| `write_xlsx_summary.py` | 生成摘要 | 8.24% | 9.16% | 9.94% | 9.52% |
| `export_xlsx_csv.py` | 导出 CSV | 0.74% | 0.04% | 0.05% | 0.03% |
| 其他进程 | runner、原子执行器及辅助命令等 | 0.02% | 0.01% | 0.01% | 0.02% |

各行按实际执行脚本 basename 归集自身 CPU，四个检查脚本分别列出。新增用例的 `.enhance_workbook.runtime.py` 是原子执行时的临时增强脚本，表中保留实际名字。同名用于对齐职责，不表示新旧实现字节相同。其他小型辅助进程合并到“其他进程”，分母仍保留完整已观察 workload CPU。

### 2.2 PDF 代表性脚本进程

N 表示实际填写和渲染的记录数；N=1 和 N=10 分开比较，两者都准备十份字段映射。转换脚本只计算自身 Python CPU，`pdftoppm` 渲染子进程单列，不重复计数。

**N=1：实际填写 1 份记录**

| 脚本／可执行文件 | 主要操作 | OPM（旧基线） | IRS W-4 | SBA 1919 |
|---|---|---:|---:|---:|
| `check_fillable_fields.py` | 可填写字段检查 | 8.72% | 3.99% | 5.15% |
| `extract_form_field_info.py` | 字段信息提取 | 9.23% | 4.35% | 6.23% |
| OPM：`generate_and_run_batch.py`；新增：`build_field_values.py` | 生成字段映射 | 1.03% | 0.36% | 0.27% |
| `run_batch_fill_render.py` | 填写／渲染批处理驱动（仅自身 CPU） | 0.51% | 0.36% | 0.54% |
| `fill_fillable_fields.py` | 填写 PDF | 16.92% | 17.03% | 13.01% |
| `convert_pdf_to_images.py` | Python 侧转换与图像处理 | 33.85% | 37.32% | 37.40% |
| `pdftoppm` | Poppler 渲染子进程 | 13.85% | 13.41% | 16.53% |
| OPM：`verify_pdf_batch.py`；新增：`verify_office.py` | 循环内业务验证 | 13.85% | 22.10% | 19.78% |
| OPM：`write_pdf_batch_summary.py`；新增：`summary.py` | 生成摘要 | 1.03% | 0.72% | 0.27% |
| 其他进程 | runner、原子执行器及辅助命令等 | 1.03% | 0.36% | 0.81% |

**N=10：实际填写 10 份记录**

| 脚本／可执行文件 | 主要操作 | OPM（旧基线） | IRS W-4 | SBA 1919 |
|---|---|---:|---:|---:|
| `check_fillable_fields.py` | 可填写字段检查 | 1.68% | 0.77% | 1.05% |
| `extract_form_field_info.py` | 字段信息提取 | 1.68% | 0.91% | 1.16% |
| OPM：`generate_and_run_batch.py`；新增：`build_field_values.py` | 生成字段映射 | 0.20% | 0.07% | 0.11% |
| `run_batch_fill_render.py` | 填写／渲染批处理驱动（仅自身 CPU） | 0.20% | 0.21% | 0.17% |
| `fill_fillable_fields.py` | 填写 PDF | 33.79% | 31.65% | 26.62% |
| `convert_pdf_to_images.py` | Python 侧转换与图像处理 | 36.17% | 39.65% | 41.91% |
| `pdftoppm` | Poppler 渲染子进程 | 15.51% | 14.95% | 18.92% |
| OPM：`verify_pdf_batch.py`；新增：`verify_office.py` | 循环内业务验证 | 10.47% | 11.51% | 10.01% |
| OPM：`write_pdf_batch_summary.py`；新增：`summary.py` | 生成摘要 | 0.20% | 0.07% | 0.00% |
| 其他进程 | runner、原子执行器及辅助命令等 | 0.10% | 0.21% | 0.06% |

三种表单使用相同类别的字段检查、提取、填写、转换和渲染工具；字段内容、页数和验证规则不同。上表直接展示各职责在本次完整 CPU 工作中的权重，不能由相同工具名称推断占比必须一致。

数据与逐进程明细见 [正式镜像新采集 JSON](../analysis/hotspot-comparison/reports/formal-process-cpu-20261026/comparison.json)，其中关联每个配置的镜像身份、recipe hash、实际进程命令、输出验证结果、原始索引和分析结果。表格由未舍入数据计算后保留两位小数，显示值之和可能有舍入误差。

本次每配置仅一轮，结果是描述性比较。轮询可能遗漏短命进程及退出前最后一段 CPU，尚无整体误差上限；ROI 由容器时钟锚与迭代时间戳对齐，边界误差未独立校准。进程等待不算 CPU；单独记录的整条命令 waited CPU 包含循环外预检／收尾，仅作旁证，不替换表格分母。

交叉核对显示，PDF 整条命令的轮询 CPU 比 waited CPU 参考值低约 4.9%～11.7%，XLSX 约低 0.5%～0.6%。差额包含 ROI 内外，不能直接分摊给某个职责，也不是 ROI 误差界。PDF 单轮较短，表中比例适合粗粒度进程结构比较，不用于判断小百分点差异；显示 0.00% 只表示未获得非零计数，不表示该脚本没有执行或实际 CPU 为零。

原 TLC/OPM 的主要进程职责在本次新增用例中继续出现，可作为这些固定工具负载的分析起点；这不是对所有文档解析 agent 的覆盖证明，也不证明具体函数权重或优化收益相同。
