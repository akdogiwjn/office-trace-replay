# office-trace-replay

用不同领域的真实 Office 输入，执行与原 document-oe 基线大体一致的工具工作负载，研究进程、库、函数热点及 CPU/OS 行为。执行时不调用 LLM。

**当前交付版本为 `office-trace-replay:openeuler-v12`。七个正式用例均已完成无源码挂载的单轮功能检查。** PDF 本轮均为 N=1；这不等于性能稳定性或代表性已经证明。

## 正式集合

| 类型 | Dataset | 输入与定位 |
|---|---|---|
| XLSX | `tlc` | 原 document-oe 大规模 TLC 基线，workload 字节冻结 |
| XLSX | `hr_metro` | BLS OEWS metropolitan/nonmetropolitan 原始工作簿 |
| XLSX | `retail_online` | UCI Online Retail 原始交易工作簿 |
| XLSX | `industry_productivity` | BLS detailed industries 原始工作簿，选择制造业序列 |
| PDF | `opm` | 原 document-oe OF-306 基线 |
| PDF | `irs_w4` | 冻结的 2026 W-4；版本、输入 hash 和字段信息见 manifest |
| PDF | `sba1919` | 可填写的 04/2024 旧版；不是当前新版 SBA 1919 |

`hr`、`retail`、`manufacturing` 保留注册，显式选择时仍可运行，作为历史对照。
`pdf`→`opm`、`xlsx`→`tlc` 别名保留。执行默认集合来自 [suites/default.json](suites/default.json)；分析选择单独记录在 [next-comparison-suite.json](analysis/hotspot-comparison/config/next-comparison-suite.json)。

`hr_metro`、`retail_online` 是人工适配的 `manual_workflow_adaptation`，没有 Agent parent trace。其他 Agent-derived recipe 是基于成功 Agent 执行整理的固定工具配方，不宣称逐条重现原 Agent 的全部调试、失败和重试。来源登记中的 `registered_not_run` 是创建时快照，当前运行状态由验收证据单独记录。

## 瘦身交付

`slim-v12` 发布分支/源码包外置大工作簿、canonical 大对象和离线 wheel；全部分析代码、最新/历史分析数据及证据保留。完整 main 和本地 raw/results 不删除或改写。

使用瘦身源码前，先从配套的本地资产包恢复：

```bash
python3 distribution/assets.py restore --bundle /path/to/office-trace-replay-assets-v12.tar
make assets-verify
```

恢复后原路径和字节不变，可继续离线构建及运行分析。现有 v12 镜像不受影响。普通 clone main 仍包含旧历史；要缩小下载，应明确选择独立 slim 分支或源码包。详见 [distribution/README.md](distribution/README.md)。

## 运行

以下命令使用本地已有镜像，只挂载可写结果目录，不需要宿主源码、输入或 Skill 挂载。

```bash
# 七个正式用例，各一轮；PDF 默认 N=1
docker run --rm --network none -v "$PWD/results:/results" \
  office-trace-replay:openeuler-v12 --loops 1 --results-dir /results

# 单个数据集
docker run --rm --network none -v "$PWD/results:/results" \
  office-trace-replay:openeuler-v12 --dataset retail_online --loops 1 --results-dir /results

# PDF N=10（opm、irs_w4、sba1919 均支持）
docker run --rm --network none -v "$PWD/results:/results" \
  office-trace-replay:openeuler-v12 --dataset irs_w4 --pdf-applicant-count 10 --loops 1
```

容器默认入口为 `replay/entry.py`，负责 suite 调度、完整轮次核验，以及新用例循环结束后的独立验收和末轮归档。旧 OPM/TLC 保留原循环 verifier，没有自动独立验收和同样的 workspace 归档；本次验收另从停止容器提取其产物。

底层入口为 `/opt/document-bench/bin/run_document_scene_loop.py`。`--scene` 走兼容的直接 runner 路径，只执行循环内验证，不自动启动 suite 独立验收。直接 runner 保留历史默认 **20,000 轮**，使用时务必显式传入 `--loops 1`。

默认 Python 为 3.12.3；`--legacy-python system` 显式选择系统 3.11.6。`--timed` 输出调用/嵌套计时日志，与普通模式分开比较。历史别名 `opm_v2`、`tlc_v2` 使用 derived-v1 引擎，仅用于来源对比；最后执行，不支持 `--timed`，不受正式 suite 的 PDF 数量等参数控制。

## 统一的执行与验证边界

XLSX 正式循环保留完整输入，不通过复制记录扩展规模：

1. **P01**：检查原输入，复制到最终输出并检查副本。
2. **P02**：通过通用原子执行器运行各数据集 helper，添加少量 KPI、情景、图表和格式，保存一次。
3. **P03**：使用原 XLSX Skill 的 `recalc.py` 原位重算最终输出，再检查公式/缓存、导出 CSV。LibreOffice 保存后不再用 openpyxl 重写文件。
4. **P04**：循环内业务验证，生成通用 summary，检查交付物。

HR Metro 的选区、Retail Online 的全表聚合在循环外一次准备并冻结为 `prepared_selection.json`。正式循环不重新做选区扫描或全表 SUMPRODUCT，但仍完整加载、增强、保存和重算大工作簿。输入和准备工件完整 hash 由执行前绑定校验负责；helper 检查小 JSON、表头及必要锚点，不每轮重新哈希大文件。已发布工件无需为日常运行重新生成。

新 XLSX 共用 loop verifier，检查结构/规模、KPI、公式、情景、图表、缓存、重算错误、CSV 和交付物；原始单元格、公式、格式、名称等深度保护审计在循环外 independent acceptance 中执行。旧 TLC 的 verifier 字节不变，验证类别大致相近，不要求检查条目完全相同。

PDF 共用检查/提取字段、准备 mappings、按记录填写/渲染、summary 和验证的主流程。N=1/N=10 都准备十份 mappings，只要求实际选择的记录具有填写 PDF 和渲染结果；循环内逐条检查实际记录及其一个代表页。页数、字段和业务规则来自数据集定义。深审在循环外进行。

准备、执行前预检、循环外验收和归档不进入被测循环；循环内的检查、重算和业务验证仍计入。阶段分组相近不表示每个输入的工作量相同。

## v12 验收与证据

| 项目 | 结果 |
|---|---|
| 实际 image ID | `sha256:b6753ca41582588a8d19efedf55d301724bc46c7c2c698fdeee53fdfc3b11ded` |
| 环境 | arm64；Python 3.12.3；openpyxl 3.1.5；LibreOffice 25.8.7.3；Poppler 23.12.0 |
| 七个正式用例 | 每项请求/完成/成功/失败均为 `1/1/1/0`，循环验证成功 |
| 独立验收 | 五个新用例通过；旧 OPM/TLC 不适用，保留原循环验证 |
| 隔离运行 | 无网络，仅挂载各自 `/results`，未挂载源码或输入 |

收尾验证与保留边界见 [release-v12.json](reports/release-v12.json)。

构建与安装态记录：[image-build-v12.json](reports/image-build-v12.json)、[实际安装态验收](reports/image-install-acceptance-v12-inspected.json)。

可提交的轻量证据入口：[reports/evidence/v12/index.json](reports/evidence/v12/index.json)。它保存七项 summary、逐轮记录、验证报告、容器 inspect 和原归档索引的字节一致副本，并关联 prepared-v2 的早期成功试跑/深审。完整 XLSX/PDF/PNG、工作目录和性能 raw 留在采集机本地；clone 可核对已提交报告，但不能凭报告重建全部运行产物。

七项原始检查分属 `results/v12-final-function-check-20261020T110841Z-132243af/` 和 `results/v12-remaining-formal-check-20261020T115040Z-74371dd4/`。它们仍在本地，不提交完整临时目录。

## 性能结论的版本与口径

当前 prepared-v2 XLSX 总 CPU 结果以 [离线重算 v2](analysis/hotspot-comparison/reports/total-cpu-recalculation-v2-20261020T104020Z/comparison-report.md) 为准：

| 数据集 | load + read_only 延迟解析 + save，占整轮 CPU |
|---|---:|
| TLC | 82.5% |
| HR Metro | 83.5% |
| Retail Online | 77.2% |
| Industry Productivity | 75.8% |

分子为 openpyxl 读写线程 CPU 区间去重之和；分母为 ROI 内所有已观察 workload 线程的 user+sys CPU 轮询估计，包含 LibreOffice。每项仅一轮，存在轮询遗漏、ROI 边界及测量开销限制。测量使用 **v11 加挂载的测量期代码**，不是 v12 性能采集。

早期 native/py-spy 画像单独保留。尤其 HR Metro/Retail Online 在 prepared-v2 改造前的画像，不能作为当前版本的热点比例；py-spy Python 活动样本比例也不能替代整轮 CPU 比例。分析入口、历史结果及复现边界见 [分析 README](analysis/hotspot-comparison/README.md)。

数据集多样性用于增加工作负载覆盖。工作簿规模、样式、公式和 LibreOffice 工作量仍不同；相近执行机制与功能通过不等于严格行业控制实验，也不证明相同优化收益。

## 开发与维护

```bash
make validate       # 静态冻结绑定与 preparation readiness；不运行 workload
make test           # 仓库测试，显式需要时执行；本次收尾未重新跑完整套件
make replay DATASET=hr_metro
make image          # 默认 v12 已存在，构建器会拒绝覆盖；新构建请显式选择新 tag
```

43 个旧 workload 文件（recipe、输入、helper、Skill、recalc、verifier 等）保持字节冻结；runner 与 timed wrapper 属独立版本化 executor。`assets/project-lock.json` 保护执行资产与代码，文档、分析和交付报告不参与该运行锁。后续只修改说明/证据关联，不要求重建 v12。

后续离线构建锁定 v12 的完整 image ID，构建器核对标签对应的 ID 后显式传入该标签，并在构建后检查基础层身份；新构建需选新 tag，例如 `make image IMAGE=office-trace-replay:openeuler-v13`。现有 v12 的历史构建基础仍为 v4，旧记录不改写；移除 v4 标签不影响 v12 保留的共享层。此次构建基础迁移不重建 v12，也不改变其运行代码、输入或验收结果。

当前流程与维护说明见 [docs/compatible-workflow.md](docs/compatible-workflow.md)；历史文档分类见 [docs/README.md](docs/README.md)。清理只忽略本地临时目录和缓存，不删除 canonical、输入、历史报告或 raw。旧采样删除记录见分析目录的 `metadata/storage-cleanup-*.json`，不把历史索引当作当前文件均存在的证明。
