# DocOps L3 回放测量与统计

十二项任务的输入、独立脚本和回放镜像在 [docops/](../../docops/README.md)。原始 Agent trace 留在来源仓库，本仓库回放冻结的最终有效执行链。

当前候选已切换为基于原七例运行环境的 `docops-replay:openeuler-unified-candidate-04`（Python 3.12.3、LibreOffice 25.8.7.3）。安装态、核心 ELF/符号一致性、四格式微型检查和十二项各一轮正式回放通过。统一环境的十二项 perf 采集已完成，每项一份 profile、每份回放十轮；随后仅离线补充 build-id 精确匹配的调试符号，十二项均通过原有函数质量门槛，未解析周期占比为 0.0018%–3.02%。统一环境的十二项 DevKit Topdown 也已完成，每项一次独立采集、内部十轮，共 533 个过程点；与 perf 分开运行。下文标为“首批”的数字仍属于原 Debian candidate-05；原始记录和镜像保留，两个环境不混算。

- [统一环境 Topdown 首轮结果](processed/unified-topdown-20261104-v1/report.md)、[完整指标和逐点数据](processed/unified-topdown-20261104-v1/comparison.json)：12/12 采集通过；当前 DevKit 最小间隔为 1 秒，实际每项 20–110 个过程点，逐点计数加总与 ALL 核对通过。
- [统一环境离线补符号效果（最新）](processed/unified-symbol-enrichment-20261104-v1/report.md)、[机器结果](processed/unified-symbol-enrichment-20261104-v1/comparison.json)：同一份原始采样补符号前后对照，没有重新运行任务或采集。
- [统一环境补符号前检查](processed/unified-symbol-check-20261103T1703Z/report.md)：保留此前结果，不被新结果覆盖。
- [扩展任务操作与原始 OPM／TLC 对照](../../docs/representativeness-assessment.md#七扩展任务操作与原始-pdfxlsx-基准比较)、[机器结果](processed/task-operation-expansion-20261104/comparison.json)：以软件栈、物理函数和 Topdown 百分点变化为主要证据；总变差辅助描述分布差异，余弦不作整体负载高相似判据。

**首批已完成：Word、Excel、PPT、PDF 各三项，每项 perf 和 DevKit 各一份 profile，每份执行十轮真实工作。** 031 复用先前两路验证，其余新增 22 路，业务均完成，无 workload 重试。尚未补齐独立重复。

- [十二任务首批对比报告](processed/first-comparison-batch-20261103/report.md)
- [完整机器结果](processed/first-comparison-batch-20261103/comparison.json)、[66 个配对](processed/first-comparison-batch-20261103/pairs.csv)、[分析代码与结果哈希](processed/first-comparison-batch-20261103/analysis-build.json)
- [031 链路验证历史记录](processed/031-collector-validation-20261103/report.md)：记录当时的初步符号质量，不被后续补符号结果覆盖。

## 口径

| 项目 | 范围 |
|---|---|
| 回放 | 最终构建、必要修补、重算、渲染及原有检查；业务脚本逐字节冻结 |
| ROI 外 | 依赖／材料校验、workspace reset、字体准备、种子恢复、归档、哈希与外部评分 |
| perf | 进程及后代、cycles:u、49 Hz、DWARF 16384；同镜像导出物理栈，按 workflow 区间并集筛选，排除调度器 |
| DevKit | 另一次回放按 CPU 0–7 采集，控制器 CPU 9；采用完整 PMU 包络，保留间隙和宿主活动边界 |
| 对比 | 进程／脚本、库、已解析物理叶函数；四顶层 Bound 余弦、已解析 Top-10 Jaccard、辅助十维欧氏距离 |
| 内容结果 | 来源官方评分保持原判定；回放完成与 Agent 原有检查退出 0 不等于重新通过官方评分 |

十轮合在一份 profile 中，仅构成一次独立采集；本轮不计算稳定性、标准差或 CV。原七例的五次结果、环境和正式报告保持独立。

补充调试符号按 build-id 与 SHA256 核对，只用于离线符号化，不替换业务库。补符号前后逐样本核验采样键、物理地址与 DSO，period 守恒，原文件及失败记录保留。原 Debian 首批中，四项 016/021/026/029 的未解析叶符号仍超过试点 20% 门槛，历史结果继续标为符号有限。统一环境离线补符号后十二项通过同一门槛；这是新环境的另一批数据，不改写 Debian 历史判定。未知权重保留分母，不能用 py-spy 或 PMU 比例填补。

## 代码

| 文件 | 用途 |
|---|---|
| `campaign.py` | 首批顺序采集，031 证据复用、冻结与归档检查、严重失败停止 |
| `pilot.py` | 单任务／单模式或两模式启动与实际镜像、容器核验 |
| `worker.py`、`monitor.py` | 测量包装、业务 CPU 0–7、调度／监测 CPU 9、进程身份 |
| `capture.py`、`quality.py` | 两路采集、ROI 与质量核验；采集成功与函数质量分别记录 |
| `native_adapter.py` | DocOps C++ 复杂符号解析，保留匿名命名空间；原七例解析器不改 |
| `fetch_symbols.py` | 精确 build-id 调试符号准备，宿主辅助进程固定 CPU 9；正式重复前准备完成 |
| `recover_perf.py`、`enrich_campaign.py` | 同镜像只读重解析已有 perf.data，不重采；失败使用新输出目录保留原记录 |
| `enrich_unified.py` | 统一环境离线补符号；逐文件挂载补充符号，保留镜像原有调试目录，并核对原采集 build-id |
| `topdown_trial.py` | 统一环境十二任务的 Topdown 独立采集、逐点与 ALL 核验；支持批次 STOP 文件在下一任务启动前停止 |
| `operation_comparison.py` | 只读已有结果，生成原始 OPM／TLC 与十二项任务的 24 组对照；追加主报告、数据记录和曲线，严格核对原文前缀不变 |
| `compare.py`、`tests/` | 离线指标／集合对比、报告生成及定向测试 |

本轮符号下载／校验有部分与 PMU 采集重叠，旧下载进程 affinity 未记录。按核结果未扣除这部分宿主活动；新下载工具绑定 CPU 9 只适用于后续。正式重复应先准备符号，再固定宿主辅助工作范围。

## 数据与复算

- `raw/first-comparison-batch-20261103/campaign.json`：24 路数据的身份、状态与哈希；22 新采集、2 路明确复用。
- `raw/first-comparison-batch-20261103/offline-symbol-enrichment-v3/enrichment.json`：本次实际采用的离线补符号结果。此前离线尝试保留失败状态，不覆盖。
- `raw/first-comparison-batch-20261103/symbols-final/index.json`：补充符号来源、准确包版本、build-id 与 SHA256。
- `processed/first-comparison-batch-20261103/`：初步统计与报告。
- `results/docops/`：原功能试跑产物；本轮没有重跑功能验收或官方评分。

原始 perf、导出文本、下载的调试文件和停止容器保留本地；大型 raw 不提交 Git。采集记录中的路径按仓库相对路径和 SHA256 定位。

仅离线重算，不启动业务或采集器：

```bash
python3 -B analysis/docops/compare.py \
  --campaign analysis/docops/raw/first-comparison-batch-20261103/campaign.json \
  --enrichment analysis/docops/raw/first-comparison-batch-20261103/offline-symbol-enrichment-v3/enrichment.json \
  --output /tmp/docops-first-batch-recomputed
python3 -B -m unittest discover -s analysis/docops/tests -v
```

`campaign.py` 和 `compare.py` 是原 Debian 首批批次的采集与分析入口，其中含旧 031 复用、原环境版本及补符号前提。复算该历史批次仍使用上述命令；不能把该入口原样用于统一环境的新批次。新镜像、原候选关联和小型验收见 [DocOps 环境说明](../../docops/README.md#当前统一环境)。
