# 文档解析类 Agent 代表性评估报告

## 一、研究目标与关键发现

本评估考察：保留 PDF 批量表单处理和 XLSX 大型工作簿增强任务，更换真实业务输入后，原基准的主要 CPU 计算机制是否延续。进一步据此识别办公 Agent 尚未覆盖的操作类型，为 Word/PPT 场景选型提供依据。

| 关键发现 | 实测证据 | 含义 |
|---|---|---|
| PDF 的主要热点延续 | W-4／SBA 与 OPM 共享 9／7 个 Top-10 函数；三例合并 Top-5 共有 5 个函数 | 解释执行、压缩编码与图像处理路径共同出现 |
| XLSX 的主要热点延续 | HR Metro／eGRID／Industry 与 TLC 共享 8／9／8 个 Top-10 函数 | 对象管理、GC、XML 与工作簿处理机制延续 |
| 顶层流水线分配接近 | 五组 Bound 余弦 0.998858–0.999897 | 支持粗粒度分配形状接近，结合函数证据解释 |
| 固定环境下可重复 | 每例、每路各五次；XLSX IPC CV 0.44%–0.72%，Backend CV 0.23%–0.54% | 主要结果在同环境重复运行中保持接近 |

**主要判断：在本次任务形态和工具链下，跨业务领域输入没有明显改变主要原生热点集合。任务操作与软件执行路径，是解释 CPU 负载特征的重要线索。** 这里验证的是同类任务的跨领域代表性；整个办公 Agent 的场景覆盖还需要检验文档排版与幻灯片构建等不同操作。

本报告完整说明实验设计、测量与结论；逐轮数值、完整热点排名、采样点、命令和证据索引见[实验数据汇总记录](experimental-results.md)。

## 二、数据集选择与任务设计

选择同时考虑官方或公开可信来源、业务领域、工作簿规模和任务可执行性。XLSX 从交通扩展到电力能源、区域就业工资和产业生产率；PDF 从联邦雇佣申报扩展到税务预扣和小企业贷款申请。

| XLSX 数据集 | 领域与来源 | 冻结输入规模 | 任务 |
|---|---|---|---|
| TLC（原基准） | 交通出行；NYC TLC | 7 个工作表；主表 100,000 行 × 25 列，约 250 万单元格 | 真实出租车行程样本及分组汇总；新增运营 Summary、指标、情景和图表 |
| eGRID | 电力能源；美国 EPA | 11 个工作表；约 273 万非空单元格 | 机组、发电机、电厂与区域统计；新增能源业务 Summary |
| HR Metro | 就业与工资；美国 BLS OEWS | 4 个工作表；主表 150,023 条记录、32 列；约 421 万非空单元格 | 都会区／非都会区职业就业与工资统计；新增 Workforce Summary |
| Industry Productivity | 产业生产率；美国 BLS | 3 个工作表；长表约 56.7 万条记录、9 列；约 580 万非空单元格 | 年度宽表与机器可读长表，涵盖生产率、产出、工时、就业和劳动补偿；新增产业 Summary |

| PDF 数据集 | 领域与发布机构 | 冻结版本 | 页数／字段／批处理 |
|---|---|---|---|
| OPM OF-306（原基准） | 联邦雇佣申报；美国 OPM | 08/2023 | 3 页、38 个字段；10 条记录 |
| IRS W-4 | 员工税务预扣；美国 IRS | 2026 | 5 页、48 个字段；10 条记录 |
| SBA Form 1919 | 小企业贷款申请；美国 SBA | 04/2024 可填写版本 | 7 页、127 个字段；10 条记录 |

TLC 沿用基于真实行程记录构建的原业务工作簿；三个新增 XLSX 保留发布方原始工作簿。百万级单元格规模为解析、对象构建和保存提供实际工作量，既有业务指标用于新增 Summary、公式、情景和图表。PDF 使用公开可填写表单与十条虚构记录，覆盖不同页面和字段规模，统一执行字段映射、填写、渲染和验证。

来源依据包括 [TLC 行程数据](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)、[EPA eGRID](https://www.epa.gov/egrid/detailed-data)、[BLS OEWS](https://www.bls.gov/oes/tables.htm)、[BLS 生产率表](https://www.bls.gov/productivity/tables/home.htm)、[OPM OF-306](https://www.opm.gov/forms/pdf_fill/of0306.pdf)、[IRS W-4](https://www.irs.gov/forms-pubs/about-form-w-4) 和 [SBA 1919](https://www.sba.gov/document/sba-form-1919-borrower-information-form)。原始表数量、数据布局及表单页数差异保留；领域多样性用于检验任务机制的延续。

## 三、实验环境、轨迹来源与回放流程

### 3.1 硬件、软件与容器

| 项目 | 实际配置 |
|---|---|
| 处理器平台 | HiSilicon HIP09；MIDR `0x00000000480fd020`，主板 `BC83AMDAL-7270Z`；平台依据为 MIDR、板号及既有硬件核验记录 |
| CPU 拓扑 | aarch64；2 路 × 64 个物理核，每核 2 个硬件线程，共 256 个逻辑 CPU；4 个 NUMA 节点 |
| 频率记录 | lscpu 报告上限 2.9 GHz、下限 0.4 GHz，boost disabled；不将上限写成实测固定运行频率 |
| 宿主内核 | `6.6.0-28.0.0.34.oe2403.aarch64`；容器共享宿主内核 |
| 回放镜像 | `office-trace-replay:agent-traces`；实际 ID `sha256:4baef1363ba99a994e17e93fe6a32c904cdb5cb349487adfa2fb13ba42301499`；arm64 / openEuler 回放环境 |
| Python 与库 | Python 3.12.3；openpyxl 3.1.5、pypdf 6.10.0、pdf2image 1.17.0、pillow 12.2.0 |
| 文档工具 | LibreOffice 25.8.7.3；Poppler 23.12.0 |
| 采集工具 | 容器内 `perf version 6.6.0-145.3.23.154.oe2403sp3.aarch64`；DevKit 26.0.RC1，可执行文件按 SHA256 冻结 |
| CPU 布局 | 容器可用逻辑 CPU 0–9；workload 运行在 0–7，控制程序和身份监测在 9。编号是宿主逻辑 CPU，不是八个独占物理核 |
| 容器隔离与权限 | 每次采集新建容器，`--network none --cpuset-cpus 0-9 --cap-add PERFMON --security-opt seccomp=unconfined`；perf 采集容器另有 `SYS_PTRACE` |
| 挂载与入口 | 测量代码 `/measurement`、证据 `/evidence` 只读，结果 `/results` 可写；Topdown 另只读挂载 `/devkit`。ENTRYPOINT 为固定 venv Python；未挂载覆盖镜像内 workload 源码。运行容器根文件系统可写 |
| 容器启动的测量入口 | perf：`/measurement/collect_native.py --dataset <id> --output /results`；Topdown：`/measurement/capture.py --dataset <id> --output /results`。各入口再按下面的流程启动采集工具与实际回放 |

### 3.2 真实 Agent 轨迹来源

TLC／OPM 沿用原有任务与回放材料。五个新增用例由 OpenClaw Agent 实际执行；每例使用独立提示词，明确业务任务、输入、输出和验收要求。Agent 编写业务 helper 并调用 Skill，保存 trajectory、tool events、脚本修订、输入／提示词及运行环境绑定，选择成功轨迹用于回放。

| 新增用例 | 采用的成功轨迹 | Agent 业务脚本 |
|---|---|---|
| eGRID | `xlsx-egrid-20261027T032347Z-225eb8e9` | `helpers/enhance_energy_report_v2.py` |
| HR Metro | `xlsx-hr_metro-20261027T042913Z-2c0c625f` | `helpers/enhance_workforce_v2.py` |
| Industry Productivity | `xlsx-industry_productivity-20261027T015504Z-769d363e` | `helpers/enhance_workbook_v1.py` |
| IRS W-4 | `pdf-irs_w4-20261027T021455Z-c206db3d` | `build_field_values.py、run_batch.py` |
| SBA 1919 | `pdf-sba1919-20261027T021613Z-ccd6fc4e` | `build_field_values.py、run_batch.py` |

### 3.3 容器内轨迹回放

一个固定镜像支持七例：旧 OPM／TLC 使用 `document-oe/run.py`，新增五例由 `agent/replay.py` 调度私有 runner。每例独立保存输入、业务脚本、Skill、recipe 和 verifier。轨迹中的内联代码整理为独立脚本，回放执行冻结脚本与工具，不再调用模型。

| 阶段 | XLSX | PDF |
|---|---|---|
| P01 输入检查 | 结构、特征检查，读取原工作簿 | 可填写检查、字段抽取、模板渲染 |
| P02 业务内容 | 业务 helper 新增 Summary、公式、情景、图表并保存 | 业务 helper 生成十条记录的字段值 |
| P03 重算／批处理 | `recalc.py` → LibreOffice，公式／缓存检查，导出本轮 CSV | 逐记录填写、逐页渲染 |
| P04 验证与交付 | 指标、缓存、CSV 和交付物验证，生成摘要 | 填写字段、保护字段、PDF／PNG 与批次验证 |

每轮重建工作区。正式循环包含 reset、P01–P04 和循环内验证；归档、哈希及循环外独立审计位于循环外。旧 43 个 workload 文件保持冻结字节与权限。

## 四、采集方法与分析方法

### 4.1 两路独立采集

| 测量 | 实际对象 | 轮次与范围 | 汇总 |
|---|---|---|---|
| perf 热点 | 回放命令及其后代进程／线程 | 七例各五个独立容器；每次一轮，PDF 每轮 N=10；共 35 次 | 正式 ROI 原始 sample period 合并，再计算用户态周期占比 |
| DevKit Topdown | 宿主逻辑 CPU 0–7，按核计数 | 相同七例各五次，另行执行，共 35 次 | 每轮最终 ALL 报告 → 均值、样本标准差和 CV |

perf 采集命令在容器内执行，由它启动回放；没有 `-a`、`-C` 或 `-p`。CPU 0–7 是进程允许运行的位置，控制和身份监测在 CPU 9。DevKit 则明确按 CPU 0–7 统计，可能包含这些 CPU 上的其他宿主活动。

```bash
# 容器内：目标回放命令与后代任务；固定 venv Python 执行实际回放。
perf record -e cycles:u -F 49 -k mono --call-graph dwarf,16384 \
  -o /results/perf.data -- taskset -c 0-7 <回放命令>
perf script --no-inline --ns -F +pid -i /results/perf.data

# 容器内：控制器位于 CPU 9；对 CPU 0–7 计数。
stdbuf -oL -eL /devkit/devkit tuner top-down -c 0-7 -L 0 -i 1 -l 0
```

新用例的 `<回放命令>` 为固定 Python 执行 `agent/replay.py --dataset <id> --loops 1` 并传入结果目录和容器 inspect；旧用例由 `legacy_capture.py` 包装原入口记录相同循环边界。逐次实参见数据记录。

`cycles:u` 只覆盖目标任务用户态执行；以 CLOCK_MONOTONIC 的循环标记筛选 ROI，未知项保留在分母。同镜像导出物理栈，按物理叶函数独占计数并关联脚本和库。它描述采样周期分布，不直接等于总 CPU 时间。

DevKit 在首次完成 PMU 读取后放行循环，循环结束后 SIGINT 停止并取得 ALL。保留启动／停止包络，不将按核 PMU 百分比视为严格 ROI 过滤。`-i 1` 为名义一秒输出，`-l 0` 为 debug 日志；未显式指定 `-r`，采用工具默认权限范围。idle 由循环门控前后 `/proc/stat` 单独计算。

### 4.2 向量、函数集合与相似度

```text
v = [IPC, Bad Speculation, Frontend Bound, Backend Bound, Retiring,
     Core Bound, Memory Bound, Fetch Latency Bound, Fetch Bandwidth Bound, idle_pct]
```

每维取五轮最终结果的算术均值；IPC 无量纲，其余用 0–100 的百分数，不做标准化。均值 `μ=Σx/5`；样本标准差 `s=√(Σ(x−μ)²/4)`；`CV=100s/|μ|`。

| 比较量 | 输入与公式 | 解释 |
|---|---|---|
| Bound 余弦 | 只取四顶层 Bound：`(a·b)/(‖a‖‖b‖)` | 比较粗粒度分配形状，避免重复计入父子项 |
| 热点 Jaccard | 五轮 period 合并排序，取 Top-10「库类别＋物理叶函数」；`&#124;A∩B&#124;/&#124;A∪B&#124;` | 比较主要函数成员，权重不进入集合运算 |
| 原始欧氏距离 | 十维向量：`√Σ(aᵢ−bᵢ)²` | 含混合单位和父子层级，仅作辅助，不拼成总分 |

### 4.3 执行、采样与结果核验

每次要求请求／完成／成功／失败＝1／1／1／0、循环业务验证成功，并核对实际 Docker inspect、输入与 recipe 绑定。perf 栈与无栈导出逐样本交叉核验、ROI 内外 period 守恒；Topdown 校验顶层与子层分区，五轮统计从原始结果复算。丢样、未知符号和未计数事件保留记录，不补算缺失权重。43 个旧 workload、35 次各路采集、来源与报告哈希均有核验记录。SMT／事件复用语义待核验项与按核包络限制随数据记录保留。

## 五、实验结果与代表性分析

### 5.1 主要脚本、库与计算机制

下表按执行职责归并实际脚本。占比为完整 ROI 的已观测用户态 sample period；业务处理与检查／验证分列，避免把公共检查成本直接归为业务计算。

| PDF 职责／脚本 | OPM | IRS W-4 | SBA 1919 |
|---|---|---|---|
| 转换 `convert_pdf_to_images.py` | 38.85% | 44.17% | 44.92% |
| 填写 `fill_fillable_fields.py` | 38.44% | 36.41% | 29.00% |
| 渲染 `pdftoppm` | 8.03% | 6.89% | 14.57% |
| 验证 `verify_pdf_batch.py` | 12.26% | 12.40% | 10.64% |

| XLSX 职责／脚本 | TLC | HR Metro | eGRID | Industry Productivity |
|---|---|---|---|---|
| 输入检查 `inspect_xlsx_structure.py / inspect_xlsx_features.py` | 23.26% | 20.90% | 11.09% | 16.82% |
| 业务增强 `enhance_workbook.py / enhance_*_v*.py` | 22.01% | 25.30% | 25.59% | 20.52% |
| 重算 `recalc.py`，公式／缓存检查 `inspect_xlsx_*.py` | 27.83% | 35.09% | 45.85% | 42.84% |
| 循环验证 `verify_xlsx_enhanced.py` | 10.25% | 11.19% | 11.50% | 10.25% |
| 摘要／CSV `write_xlsx_summary.py / export_xlsx_csv.py` | 9.05% | 0.01% | 0.18% | 0.00% |
| LibreOffice 主进程 `soffice.bin` | 4.66% | 3.44% | 3.13% | 4.51% |

这些行为是完整工具 workload 的组成部分：PDF 验证占约 10%–12%，XLSX 验证占约 10%–12%，共同机制同时出现在业务 helper、检查、重算和验证。表中的 `recalc.py` 包含其 Python 缓存检查，`soffice.bin` 为单列的子进程，不能将两者脚本归属混成同一份周期。未归属线程与剩余小项在数据记录中单列。

| PDF 主要原生库 | OPM | IRS W-4 | SBA 1919 |
|---|---|---|---|
| libpython | 50.41% | 45.21% | 37.28% |
| zlib | 25.18% | 23.75% | 23.89% |
| Pillow | 14.61% | 21.71% | 21.22% |
| Poppler | 6.23% | 3.47% | 6.93% |
| FreeType | 1.02% | 2.25% | 6.27% |

| XLSX 主要原生库 | TLC | HR Metro | eGRID | Industry Productivity |
|---|---|---|---|---|
| libpython | 79.26% | 79.54% | 81.70% | 78.55% |
| LibreOffice | 6.43% | 6.44% | 4.91% | 8.41% |
| expat | 5.65% | 5.15% | 4.97% | 5.28% |
| ElementTree | 3.68% | 3.64% | 3.40% | 3.11% |
| zlib | 1.56% | 2.09% | 1.89% | 1.37% |

PDF 的主要机制为 Python 解释执行、zlib 压缩和 Pillow 图像处理，伴随 Poppler／FreeType 渲染。XLSX 以 libpython 为主，并持续出现 XML 解析和 LibreOffice 路径；这把函数重合与实际工具工作联系起来。

### 5.2 主要热点函数与跨领域重合

★ 为原基准 Top-10，按原排名列出；粗体为该函数在各例中的权重，✓ 表示仍进入该例 Top-10。新例额外进入 Top-10 的函数及完整排名保存在数据记录中。

| PDF 基准热点 | OPM | IRS W-4 | SBA 1919 |
|---|---|---|---|
| ★ 1 · `libpython / _PyEval_EvalFrameDefault` | **16.52% ✓** | **18.57% ✓** | **15.02% ✓** |
| ★ 2 · `zlib / longest_match` | **10.07% ✓** | **11.14% ✓** | **12.96% ✓** |
| ★ 3 · `zlib / deflate_slow` | **7.04% ✓** | **6.22% ✓** | **6.12% ✓** |
| ★ 4 · `Pillow / ImagingResampleHorizontal_8bpc` | **5.41% ✓** | **8.18% ✓** | **8.51% ✓** |
| ★ 5 · `Pillow / ImagingZipEncode` | **4.70% ✓** | **7.54% ✓** | **5.78% ✓** |
| ★ 6 · `libpython / deduce_unreachable` | **3.42% ✓** | **1.56% ✓** | **1.47%** |
| ★ 7 · `libpython / gc_collect_main` | **2.92% ✓** | **1.81% ✓** | **1.52%** |
| ★ 8 · `zlib / slide_hash` | **2.74% ✓** | **3.07% ✓** | **2.82% ✓** |
| ★ 9 · `Pillow / ImagingResampleVertical_8bpc` | **2.52% ✓** | **3.26% ✓** | **4.88% ✓** |
| ★ 10 · `zlib / inflate_fast` | **2.47% ✓** | **1.06%** | **0.46%** |

| XLSX 基准热点 | TLC | HR Metro | eGRID | Industry Productivity |
|---|---|---|---|---|
| ★ 1 · `libpython / _PyEval_EvalFrameDefault` | **23.65% ✓** | **21.97% ✓** | **22.80% ✓** | **21.57% ✓** |
| ★ 2 · `libpython / gc_collect_main` | **5.13% ✓** | **7.31% ✓** | **7.24% ✓** | **7.04% ✓** |
| ★ 3 · `libpython / subtype_traverse` | **3.90% ✓** | **4.84% ✓** | **5.09% ✓** | **4.27% ✓** |
| ★ 4 · `libpython / _Py_dict_lookup` | **3.57% ✓** | **4.77% ✓** | **4.97% ✓** | **4.80% ✓** |
| ★ 5 · `libpython / deduce_unreachable` | **3.23% ✓** | **4.30% ✓** | **4.43% ✓** | **4.10% ✓** |
| ★ 6 · `libpython / visit_reachable` | **2.97% ✓** | **3.33% ✓** | **3.38% ✓** | **3.16% ✓** |
| ★ 7 · `libpython / _PyObject_GenericGetAttrWithDict` | **2.04% ✓** | **1.27% ✓** | **1.35% ✓** | **1.50% ✓** |
| ★ 8 · `libpython / dictiter_iternextkey` | **1.92% ✓** | **0.78%** | **0.81%** | **0.74%** |
| ★ 9 · `libpython / tupledealloc` | **1.61% ✓** | **1.81% ✓** | **1.76% ✓** | **1.69% ✓** |
| ★ 10 · `libpython / PyObject_GC_Del` | **1.49% ✓** | **1.07%** | **1.15% ✓** | **1.02%** |

三种 PDF 五轮合并 Top-5 共有 5 个函数，对应解释器、zlib 匹配／编码和 Pillow 缩放／编码；各自 Top-5 累计 ROI 占比为 OPM 43.74%、IRS W-4 51.65%、SBA 1919 48.40%。XLSX 的共同函数包括解释器、字典查找、对象遍历、GC 和对象释放。这里的共同热点说明主要计算类型延续，允许各输入有不同排名和权重。

### 5.3 Topdown 特征与相似度

| 数据集 | IPC | Bad Spec. | Frontend | Backend | Retiring |
|---|---|---|---|---|---|
| OPM | 1.23 | 4.68% | 18.12% | 56.76% | 20.44% |
| IRS W-4 | 1.27 | 4.67% | 17.62% | 56.54% | 21.17% |
| SBA 1919 | 1.31 | 4.95% | 15.71% | 57.50% | 21.84% |
| TLC | 1.23 | 2.48% | 18.10% | 58.85% | 20.57% |
| HR Metro | 1.22 | 2.33% | 16.31% | 61.01% | 20.35% |
| eGRID | 1.25 | 2.15% | 15.61% | 61.45% | 20.78% |
| Industry Productivity | 1.23 | 2.18% | 16.80% | 60.46% | 20.55% |

| 基准 → 新输入 | Top-10 共同函数 | Jaccard | Bound 余弦 | 十维欧氏距离（辅助） |
|---|---|---|---|---|
| OPM → IRS W-4 | 9/10 | 0.8182 | 0.999897 | 1.457 |
| OPM → SBA 1919 | 7/10 | 0.5385 | 0.998987 | 4.040 |
| TLC → HR Metro | 8/10 | 0.6667 | 0.999314 | 3.852 |
| TLC → eGRID | 9/10 | 0.8182 | 0.998858 | 4.755 |
| TLC → Industry Productivity | 8/10 | 0.6667 | 0.999634 | 2.929 |

七例均以 Backend Bound 为最大的顶层分类；五组余弦接近 1，与主要热点的延续相互补充。Backend 是粗粒度分类，不能单独推出具体瓶颈一致，也不代表执行效率或 CPU 核秒相同。

### 5.4 逐采样点过程与五轮稳定性

下图每条线对应一个顶层指标，横轴为真实采样点；各轮按编号顺序串联展示，轮间留空、分别标注。保留初始与结束包络，不平滑、不补点。不同数据集耗时不同，横轴不用于强行对齐同一执行阶段。

![PDF 五轮逐采样点顶层 Bound](../analysis/topdown/reports/seven-dataset-five-repeats-20261028T020708Z-58392cf7/similarity/pdf-bound-five-repeats.svg)

每个点为原始 DevKit 编号报告，每条线为一个指标；横轴为五轮串联的采样点序号，轮间留空且不连线。名义间隔 1 秒，保留启动和停止包络，不平滑、不插值。

![XLSX 五轮逐采样点顶层 Bound](../analysis/topdown/reports/seven-dataset-five-repeats-20261028T020708Z-58392cf7/similarity/xlsx-bound-five-repeats.svg)

每个点为原始 DevKit 编号报告，每条线为一个指标；横轴为五轮串联的采样点序号，轮间留空且不连线。名义间隔 1 秒，保留启动和停止包络，不平滑、不插值。

| 数据集 | IPC CV | Backend CV | 五轮两两 Top-10 共同数 |
|---|---|---|---|
| OPM | 1.69% | 1.30% | 5–7/10 |
| IRS W-4 | 1.29% | 0.88% | 5–8/10 |
| SBA 1919 | 1.32% | 0.63% | 6–8/10 |
| TLC | 0.44% | 0.23% | 10–10/10 |
| HR Metro | 0.68% | 0.29% | 10–10/10 |
| eGRID | 0.72% | 0.54% | 8–9/10 |
| Industry Productivity | 0.68% | 0.39% | 9–10/10 |

XLSX 的主要特征与热点集合在固定环境重复运行中接近；PDF 单轮热点排名更易波动，五轮合并用于识别持续出现的主要函数。例如 OPM Fetch Bandwidth CV 为 12.36%，因此稳定性按指标分别描述。曲线展示轮内变化，均值和 CV 仍来自每轮 ALL；两者分别回答过程变化与重复波动。

## 六、已有实验的覆盖边界与 Word/PPT 扩展价值

### 6.1 已验证的范围与尚未覆盖的操作

| 场景 | 操作范围 | 已知或待测的机制 |
|---|---|---|
| PDF，已测 | 可填写表单的字段映射、填写、渲染和验证 | 已观察到 Python、压缩编码、图像处理、Poppler／字体路径 |
| XLSX，已测 | 百万级单元格工作簿检查、增强、保存、重算、验证 | 已观察到解释执行、对象管理、GC、XML、Calc 路径 |
| Word，待测 | 长文档结构编辑、样式与复杂表格、分页 | 待检验连续文本布局、字体度量、跨页布局的显著性 |
| PPT，待测 | 幻灯片构建、母版编辑、形状与图片布局 | 待检验演示对象构建、图形布局与渲染的显著性 |

现有结果支持两类已测任务的跨领域代表性，尚未覆盖完整 PDF／XLSX 任务空间。共同解释器和库函数可由业务处理及公共检查共同贡献，不能仅凭函数名称推断相同上层算法。当前统计以相对周期与流水线分配为主，绝对 CPU 工作量需要同一版本的 CPU-seconds 等补充；不混用旧版本账本。

前面的五组对照表明：沿用表单处理与工作簿增强任务时，跨领域输入仍持续进入解释器、对象管理、XML、压缩和渲染等共同路径。因此，继续只更换业务行业，未必能补充新的主要计算类型。下一步应扩展实际操作，重点考察当前较少涉及的连续文档排版和幻灯片图形布局。

### 6.2 为什么选择 Word/PPT

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

下一轮重点检验：Writer／Impress 的布局、字体和图形路径是否成为显著热点；这些工作占多少绝对 CPU 工作量；共享压缩、XML 和渲染机制之外，是否出现 PDF 表单与 XLSX 增强尚未充分覆盖的主导机制。**已有七例用于验证跨领域输入下的机制延续，Word/PPT 用于扩展操作类型的覆盖。**

完整数据、逐次命令和核验材料：[实验数据汇总记录](experimental-results.md)。
