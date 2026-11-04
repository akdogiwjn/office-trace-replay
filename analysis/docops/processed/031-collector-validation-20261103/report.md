# DocOps 031：perf / DevKit 采集链路验证

两条采集链路已通过短 PDF 031 的真实验证。perf 和 DevKit 分别运行 10 轮，业务均为 10/10/10/0。这里只验证接线、计数、ROI、调用栈与归档，不作十二任务相似度结论。

镜像：`sha256:bda6808f5b05feff831fb1700a24ee90f42c5b332f5411c80a752cf960baf617`；业务脚本、payload 和镜像本轮未修改。

## 实测结果

| 项目 | perf | DevKit Topdown |
|---|---|---|
| 业务循环 | 10 轮全成功 | 10 轮全成功 |
| workflow ROI 合计 | 15.532 秒 | 15.468 秒 |
| 数据 | ROI 694 样本；period 33,621,198,679 | 18 次 PMU read；最终汇总完整 |
| 范围 | 入口与后代采集；按 workflow 区间并集过滤，排除调度器 | CPU 0–7 按核采集；控制器主进程 CPU 9 |
| 完整性 | 栈导出与无栈头计数逐样本交叉核对，period 守恒 | 九项指标经验公式复算在打印精度内；顶层及细分分区加和通过 |
| 函数质量 | 空栈 0；未知叶 DSO 0.00175%；未知叶符号 18.4481% | 非函数采样 |

## 采集方法

调度、重置、种子恢复与归档位于 CPU 9，正式步骤通过 taskset 在 CPU 0–7 运行。perf 采用进程及后代采集；DevKit 另一次回放采用 CPU 范围采集，二者不同时启动。每轮保留单调时钟步骤区间。

```bash
perf record -e cycles:u -F 49 -k mono --call-graph dwarf,16384 -o /results/perf.data -- python3 -B /opt/docops-measurement/worker.py --task 031 --loops 10 --mode perf
perf script --no-inline --ns -F +pid -i /results/perf.data
devkit tuner top-down -c 0-7 -L 0 -i 1 -l 0
```

perf 同镜像导出，按所有 workflow 区间的并集保留样本，排除调度器 PID，区间外及排除权重单列。`--no-inline` 保留物理栈，不展开逻辑内联帧。

DevKit 完整包络 17.679 秒，其中 workflow 外约 2.211 秒；按核结果还可能包含宿主其他活动。idle 87.55% 单列，不视为本任务线程空闲比例，也不和精确 ROI 拼成正式十维向量。

## 热点与 Topdown

| 已识别函数 | ROI cycles:u period 占比 |
|---|---:|
| `longest_match` | 64.03% |
| `deflate_slow` | 7.58% |
| `Splash::pipeRunAARGB8` | 1.94% |
| `_PyEval_EvalFrameDefault` | 1.48% |
| `PyObject_GC_Track` | 1.28% |

本例渲染为主要进程热点，压缩函数 longest_match、deflate_slow 权重较高；这不是所有 DocOps PDF 任务的共同结论。

| Topdown 指标 | 输出 |
|---|---:|
| IPC | 1.05 |
| Bad Speculation | 2.26% |
| Frontend Bound | 7.44% |
| Backend Bound | 72.85% |
| Retiring | 17.45% |
| Core Bound | 57.34% |
| Memory Bound | 15.52% |
| Fetch Latency Bound | 6.50% |
| Fetch Bandwidth Bound | 0.93% |

## 发现并处理的问题

1. 初次 perf 导出存在 92.56% 未解析叶符号。确认是库文件移除了内部符号；从 Debian debuginfod 下载精确 build-id 对应的分析用调试文件，校验 build-id 与 SHA256，以只读挂载补符号。不替换业务库、不重录 perf、不重跑该批业务。恢复后计数、period、进程与 DSO 分布均不变。原失败记录不改写。
2. 初次 DevKit 在导入共用解析模块时因挂载层级过浅退出，没有启动 workload 或 PMU。修正测量挂载路径后完成正式试点。
3. libpng 对应调试文件未从 debuginfod 取得，定制 Python 内部符号也未恢复；这两项合计仍占较大未解析权重。当前允许展示已识别热点及库分布，尚不宜将完整 Top-10 函数集合用于无质量说明的跨任务判定。

## 核验与下一步

针对性测试 5 项通过，测量源码语法和 git diff --check 通过；原采集、离线恢复和 DevKit 的 SHA256 索引逐文件回读通过。原始证据、失败现场与已停止容器全部保留。
下一步可沿用此链路安排十二任务的正式测量；先固定每批真实循环数、独立重复数和符号质量要求。10 轮合在一个 profile 中不等于 10 次独立测量。本轮没有采集其他十一项，也没有计算相似度。

## 证据

- [机器记录](validation.json)
- [原 perf](../../raw/031-chain-pilot-20261103T143556Z-48720214/perf/out/collection.json)
- [离线符号恢复](../../raw/031-perf-symbol-recovery-20261103T144210Z-c74df423/out/recovery-record.json)
- [DevKit](../../raw/031-chain-pilot-20261103T144406Z-0e5f48a2/topdown/out/collection.json)
- [调试符号来源与哈希](../../symbols/index.json)
