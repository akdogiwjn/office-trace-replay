# PDF / XLSX 热点函数对比方案

目标更新：暂不采集或计算 Topdown 指标，仅比较当前 Agent 轨迹回放与 document-oe 旧基线的热点进程、脚本、原生库和函数。不同输入的共同函数与权重差异是研究对象，不预设高相似结论。

## 对比集合

| 场景 | 旧基线 | 新用例 | 主比较 |
|---|---|---|---|
| XLSX | document-oe TLC | egrid、hr_metro、industry_productivity | 三个新用例分别与 TLC 比较 |
| PDF | document-oe OPM | irs_w4、sba1919 | 三者实际填写数量均为 N=10，两个新用例分别与 OPM 比较 |

先以七个配置各一次的采样形成描述性结果；正式采集与镜像构建另行安排。单次结果不证明差异稳定。五个新用例采用当前各自冻结的真实 Agent 来源及回放适配，不混用旧版人工适配 workload 的结果。

## 已有证据与缺口（2026-10-27 构建前盘点）

- 当前 `agent/suite.json` 的五个新用例均为 `compiled_static_only_not_replayed`；`reports/prebuild-closeout.json` 记录尚未构建新镜像、运行正式 workload 或采集性能。
- 原 main 工作区 `/home/lcq/office-trace-replay/analysis/hotspot-comparison/` 有历史 native 热点结果，可作历史旁证。相同 dataset ID 不代表相同 helper、recipe 或 verifier；只有执行材料和采集口径匹配后才能复用为正式对照。
- `reports/formal-process-cpu-20261026/` 是上一版脚本进程 CPU 分布，不是当前版本的逐函数 profile。
- 因而当前没有可直接组成新版七用例热点函数对比的完整采样集。缺失结果记为未采集，不填零、不沿用旧百分比。

## 测量边界和权重

主表采用完整 workload ROI 内 `cycles:u` 样本的原始 period 权重，包含 Python、LibreOffice、Poppler 等实际 workload 进程及线程的用户态样本。未知符号、未知 DSO 和空栈保留在分母中，单列质量占比；一个样本 period 只计一次。

这一口径是用户态 CPU 周期的采样分布，不是完整 user+sys CPU 时间占比，也不包含阻塞等待。报告必须使用相应列名，不把函数周期占比重命名为总 CPU 时间占比。

新用例以 `roi.jsonl` 中的 `loop_including_reset` 为正式边界，排除准备、预检、归档和独立审计。`workflow` 可作单独的补充口径，不与前者相加。旧入口需要核对可对应的实际循环边界；没有可靠边界时不声称口径一致。只采 Docker 客户端进程不能覆盖容器 workload，采集器必须跟踪真实 workload 及其子进程/线程。

固定镜像、Python/库、采样事件/频率、CPU 绑定、SMT 使用方式与导出选项。CPU 0–7 在当前机器上包含四个物理核的 SMT 线程，不能写成八个独立物理核。采集器与控制程序使用的 CPU 应避开 workload 物理核及其 SMT sibling。

## 函数识别与导出

- 在采集所用镜像内导出符号和物理调用栈；不要以宿主缺失 Python/Office 文件的导出结果替代。
- 所有配置采用一致的物理叶函数口径，优先统一 `perf script --no-inline`。内联帧不与实体叶函数重复计权；不能把未知叶节点替换为不同地址调用者的符号或 DSO。
- 函数身份采用模块/DSO 身份加符号名；记录 build-id。同名不同库不自动匹配，版本变化另列。聚合函数与“脚本+DSO+函数”的上下文表分别输出。
- 脚本归属来自实际执行命令、cwd 和进程身份，不仅靠 basename。同职责脚本可以并排展示，不能当成相同代码身份。
- 保存原始 perf.data、导出日志、解析结果、ROI、进程身份、真实 image inspect 以及 recipe/输入/Skill/helper/verifier/分析代码哈希。

## 最终交付表

1. 每个用例的 Top-20 函数：实际脚本/进程、DSO、函数、period、完整 ROI 占比；未知项另列且保留分母。
2. 新旧配对表：基线占比、新用例占比、百分点差；同时展示进程/脚本和库的聚合分布，解释函数差异出现在哪个执行上下文。
3. 共同与新增热点：报告旧 Top-20 函数在新用例中覆盖的 period 占比，以及新用例 ≥0.5% ROI、旧基线采样未观察到的函数。未观察到不等于旧用例不可能执行。
4. 相似度辅助表：明确以 Top-10/Top-20 的 DSO+函数集合分别计算 Jaccard，并同时给出入选项数量、已解析权重和占比差。未知符号/裸地址不作为共同函数；不单靠固定 Jaccard 阈值判定代表性。
5. 质量表：workload 验证状态、ROI 完整性、period 守恒、lost samples/chunks、空栈与未知符号权重、符号化环境、重复次数。归档完整性和函数分析质量分别判定。

原生 `libpython` 热点只能证明解释器/运行时函数共同出现；不能单凭 `_PyEval_EvalFrameDefault` 推断相同 Python 业务算法。若后续需要 openpyxl 上层函数归属，可另采 py-spy 并单独报告，不能按其比例分摊 native cycles。

## 执行顺序

先完成当前镜像的构建和最小功能验收，再以一个新用例做采集、同镜像有界导出、解析、ROI 和归档的端到端短流程检查。确认采集链路可用后，再安排七配置正式采样；已有合格且身份匹配的结果可复用。可从 perf.data 恢复的导出问题优先离线恢复，不因导出失败自动重跑 workload。

本方案文件的建立没有启动镜像构建、workload、采集器或历史大型数据重解析。

## 后续执行进展

2026-10-27 用户随后授权构建与验证，已完成镜像安装态检查、七用例单轮功能检查及五个新用例的独立验收，具体范围及 IRS W-4 的输出复用边界见[验收报告](../reports/image-qualification-agent-traces.md)。尚未采集当前版本的热点函数数据；上述历史 profile 不能替代新版结果。下一步可基于已验证镜像单独安排热点采集。

2026-10-27 用户另行授权单数据集采集试点，IRS W-4 N=10 单轮 native 采集、同镜像导出、ROI 过滤与解析已经成功。见[试点说明](../analysis/hotspots/README.md)和[最新结果指针](../analysis/hotspots/reports/latest-pilot.json)。这补齐了一个当前版本 profile，其余配置仍未采集，不构成新旧对比结论。
