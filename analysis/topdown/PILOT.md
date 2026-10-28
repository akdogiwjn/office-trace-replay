# Topdown 按核采集试点结果

已完成小型父子进程验证，以及 IRS W-4 的一轮真实 PDF 试点。使用现有镜像，没有重新构建镜像，也没有修改七个数据集的 runner、recipe、helper、Skill、输入或业务验证器。

| 项目 | 结果 |
|---|---|
| 小型父子进程 | 成功；CPU 0–7 可观察子进程计算，结束后恢复 CPU 9 |
| IRS W-4 | 10 份记录；请求／完成／成功／失败 = 1／1／1／0 |
| 循环内业务验证 | success |
| DevKit | 正常就绪；SIGINT 后生成完整最终报告；退出码 0 |
| 归档 | 141 个文件逐项核对 SHA256 与大小通过 |
| 软件环境 | 合格镜像内原 Python 3.12.3；DevKit 独立只读挂载 |
| 定向测试 | 6 项通过，覆盖 affinity 门控、异常序列、idle 分母、最终总报告选择、未计数保留和分区检查 |

结果报告：[IRS W-4 试点](reports/irs_w4-cpu-pilot-20261027T151703Z-7808dc1d/report.md)、[机器结果](reports/irs_w4-cpu-pilot-20261027T151703Z-7808dc1d/summary.json)。小型验证：[报告](reports/smoke-cpu-pilot-20261027T151508Z-12df0689/report.md)。先前的 [硬件与工具核验](README.md) 是本次试点前的证据快照。

## 接线方式

`pilot.py` 创建、inspect、启动并保留无网络容器；仅挂载测量代码、DevKit 和结果目录，镜像内 workload 不被覆盖。

`capture.py` 在 CPU 9 上执行预检和控制 DevKit。`workload_entry.py` 载入镜像内原有的 dataset executor，仅在内存中包装已有 `boundary()`：

1. 执行前环境检查与来源快照在 CPU 9。
2. 原循环开始标记之前，等待 DevKit 完成首次 PMU read，随后把 executor 切到 CPU 0–7。
3. 原始 P01–P04 及 reset 使用 CPU 0–7；子进程继承该范围。
4. 原循环结束标记之后，立即恢复 CPU 9，并停止 DevKit。
5. 原工作区归档在 CPU 9，未执行独立审计。

测量进程本身在 CPU 9。上述方式排除了本容器预检、归档和审计在目标核上的执行；目标 CPU 仍可能运行宿主背景任务，不能把按核数据写成 workload 专属的进程计数。

## 本轮数据的边界

DevKit 的计数窗口比业务 ROI 宽：IRS W-4 的业务 ROI 为 14.820 秒，启动包络上界约 1.112 秒，停止包络上界约 0.010 秒。PMU 输出保留为完整包络结果；`/proc/stat` idle 取门控窗口，两者暂不组成正式十维向量。没有按时间比例分摊计数或从分母扣除未知权重。

这轮完成了真实工具链的采集接线验证。正式相似度采集前，还需收敛包络与 ROI、SMT／事件复用口径和未计数状态。相关记录均设置 `formal_similarity_eligible=false`，未将这轮指标混入现有热点代表性报告。

## 文件与复核

采集入口 `pilot.py` 只运行显式选择的一个用例，目前支持 `smoke`、`irs_w4` 和 `sba1919`。不自动展开全套，不自动重试；raw、停止容器和失败记录保留。

离线解析入口 `summarize.py <raw-directory>` 不运行 workload 或采集器，拒绝覆盖报告目录。正式 raw 在 `raw/` 内，由该目录的 `.gitignore` 排除；小型报告、代码与测试可提交。

本轮真实结果的容器：`53b2f912c0eef820035649c90178335b56a8c47c273e3f73acc710c3693815c4`。
镜像：`sha256:4baef1363ba99a994e17e93fe6a32c904cdb5cb349487adfa2fb13ba42301499`。
