# 当前 Agent 轨迹版热点采集

## PDF 五轮重复采样

新增 [PDF 五轮重复统计](reports/pdf-five-repeats-20261027T122345Z-06367392/report.md)。OPM、W-4、SBA 各在五个独立容器中执行一轮，每轮仍处理十份记录；按 OPM→W-4→SBA 的顺序交替完成五组，共 15/15 次成功，没有 workload 重试。ROI 样本分别累计 2,736、3,443、4,275 个。

合并只累加各轮正式 ROI 内的原始 period，不平均各轮百分比。合并后 W-4/SBA 与 OPM 的 Top-10 共同函数数为 9/7；三例合并后的 Top-5 集合相同，累计占比分别为 43.74%/51.65%/48.40%。逐轮排名、范围和来源保存在独立报告中。正式代表性报告的 PDF 表格与结论已全部采用五轮合并结果，不再展示原单轮 PDF 对照；XLSX 数据保持不变。

采集入口 `pdf_repeats.py --collect` 固定各五次；`--summarize <campaign.json>` 只离线重算，拒绝覆盖既有输出。当前重复实验指针为 `reports/latest-pdf-repeats.json`。聚合、排名、职责合并及热点标记等相关定向测试共 22 项通过。

## 七例代表性报告

正式报告采用 PDF 每例五轮合并、XLSX 每例单轮的热点结果。PDF 为 OPM、IRS W-4、SBA 1919（每轮均 N=10）；XLSX 为 TLC、HR Metro、eGRID、Industry Productivity。未采集 Topdown 或 py-spy。

汇总见 [文档解析类 Agent 代表性评估报告](reports/pdf-xlsx-common-hotspots-20261027/report.md)，依次介绍数据集选择与领域覆盖、Agent 轨迹生成、容器化轨迹回放和热点函数对比；机器结果见同目录 `comparison.json`。主表对照五轮合并的 OPM 和已有单轮 TLC；目标是主要热点共同出现，不要求权重相等。W-4、SBA 与 OPM 分别有 9、7 个 Top-10 共同函数；HR、eGRID、Industry 与 TLC 分别有 8、9、8 个。该计数描述当前排名交集，不作为验收阈值。

XLSX 记录了 perf 丢样，函数与库画像用于主要热点结构观察。完整诊断保留在各 profile 和原始日志中。历史摘要按全量实体函数归并、period 加权后冻结在 `baselines/legacy-opm-tlc.json`；本轮只作追溯，不进入主表。汇总重算只读取当前仓库的冻结摘要和 profile，不依赖兄弟仓库。当前正式配置为 `comparison-inputs-pdf5-20261027.json`；原单轮配置 `comparison-inputs-seven-20261027.json` 和初始历史对照配置 `comparison-inputs-20261027.json` 仅作追溯保留。

2026-10-27 试点成功：完整采集/导出 785 个样本，正式循环 ROI 711 个，工作负载与循环业务验证成功。原始 perf.data 约 16.1 MB，停止容器与原始证据保留。最新结果由 [latest-pilot.json](reports/latest-pilot.json) 指向，含脚本、库、Top-20 物理叶函数和带脚本上下文的函数表。

主表是**完整循环 ROI 的用户态 cycles:u 原始 period 占比**，不是整轮 user+sys CPU 时间占比。未知符号与空栈保留分母；直接读取 CLOCK_MONOTONIC 的 roi.jsonl，不从缓冲 stdout 估算边界。完整栈与无栈计数导出按 PID/TID/时间/period/event 多重集合核对，并核对 perf 聚合 SAMPLE 数。它们验证导出/解析完整性，不证明硬件采样绝对无损。

采集使用已验收镜像，运行时只读挂载本目录的采集工具；不覆盖 workload、runner、输入、helper 或 Skill。perf 默认继承子进程计数，workload CPU 0–7（四个物理核的 SMT 线程），monitor/perf 控制端 CPU 9。/proc 身份名义轮询间隔 10 ms，首次观察前最多 10 ms 的推断归属另记质量指标。该试点未校准轮询时间误差和采样开销，不能用于判断小幅差异或稳定性。

同一镜像内用 `--no-inline` 导出物理调用链，避免宿主缺少 Python/Office 文件造成空栈；导出限时、拒绝覆盖，失败保留 partial。导出失败先从原 perf.data 恢复，不自动重跑 workload。`LOST` 能力标记与实际 lost 记录分开，损失不换算为 period。

`raw/<pilot>/out/` 保存 perf.data、样本、身份、原生报告、ROI、runner 与业务产物、最终 collection.json 和哈希索引。`evidence/` 保存实际镜像/容器 inspect、host launch plan 和执行时采集代码快照。raw 被 Git/Docker context 忽略；分析代码与小型报告仍留在当前仓库。

首次 IRS 试点的首份报告将 `read_format=ID|LOST` 能力描述混入丢样诊断；后续仅离线整理为 analysis-v2。原始数据、首份报告和索引未改，函数权重未变。之后的采集直接区分实际 LOST 记录与能力标志。

旧 OPM/TLC 由 `legacy_capture.py` 在采集层观察原 `run_iteration` 的起止单调时钟，执行原函数并保留其结果与异常；磁盘上的 43 个 workload 文件、原 runner 和 recipe 均不修改。观测范围同样覆盖 reset 和四阶段业务执行；工作区归档在 perf 退出后进行。各用例均采用 49 Hz、cycles:u、DWARF 16384 字节、同镜像物理栈导出。

验证命令：

```bash
python3 -B -m unittest discover -s analysis/hotspots/tests -v
```

后续只有明确安排新一次采集时才执行以下命令；会创建新目录和新容器，可选择七个正式 dataset ID，不会自动运行其余配置：

```bash
python3 -B -u analysis/hotspots/pilot.py --dataset sba1919
```

仅在 workload、record、导出均已成功而后续解析/摘要失败时，可用 `recover_native.py --raw <capture-directory>` 离线恢复。恢复校验原索引，不启动 perf 或 workload，不改写原失败状态。各数据集最新指针为 `reports/latest-<dataset>.json`；原 IRS 试点仍保留其独立路径，`latest-pilot.json` 只表示最近一次采集。

前期四项单轮补采均只执行一次，之后 PDF 按上述固定五次方案完成重复采集；XLSX 沿用单轮数据。未运行完整测试套件。
