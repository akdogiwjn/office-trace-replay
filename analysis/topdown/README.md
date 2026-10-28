# HIP09 Topdown 采集与分析

当前已完成七例各五次 Topdown 采集，并与独立 perf 热点结果联合分析。最新索引、逐轮统计和复核命令见 [CAMPAIGN.md](CAMPAIGN.md)，正式结论见 [代表性评估报告](../../docs/representativeness-assessment.md)。以下保留硬件、工具与事件核验依据。

## 工具与硬件

本机 MIDR 为 `0x480fd020`，主板字符串为 `BC83AMDAL-7270Z`。华为官方[微架构亲和选项](https://www.hikunpeng.com/doc_center/source/zh/kunpengdevps/compiler/opg-bisheng/kunpengbisheng_30_0036.html)将 7270Z 对应到 `hip09`；本机硬件标识与之相符。DevKit 的 CPU Model 显示 `NA`，容器中显示 `unknown`，因此该显示本身没有完成型号确认。

采用官方[获取工具说明](https://www.hikunpeng.com/document/detail/zh/kunpengdevps/install/installguide/KunpengDevKitCli_0003.html)列出的独立 Tuner CLI 包形式，避免安装整套 Web 服务或修改工作负载镜像。包和签名位于忽略提交的 `downloads/`，解压工具位于忽略提交的 `tools/`。下载 URL、SHA256、实际二进制及库 hash 记录在 qualification.json。已取得 `.asc`，尚未取得独立可信公钥并完成 PGP 验证；SHA256 仅用于冻结本次字节身份。

## 已核对的指标与事件

下表公式按百分数表示，`C=r0011`、`I=r0008`、`S=r001b`、`F=r2011`。它们是从本次工具的原始计数复现输出得到的算术关系；尚未取得完整的官方 HIP09 公式定义文件，不将这种复现等同于规范确认。正式计算优先保留固定版本 DevKit 输出及原始事件。

| 指标 | 本次工具使用的事件／可复现算术关系 | 核验状态 |
|---|---|---|
| IPC | `I / C` | 所有成功短探针均与显示精度一致 |
| Retiring | `100 × I / (6 × C)` | 同上 |
| Bad Speculation | `100 × (S − I) / (6 × C)` | 同上 |
| Frontend Bound | `100 × F / (6 × C)` | 同上 |
| Backend Bound | `100 − Retiring − Bad Speculation − Frontend Bound` | 同上 |
| Fetch Latency Bound | `100 × r2012 / C` | 全层级及前端探针与显示精度一致 |
| Fetch Bandwidth Bound | `Frontend Bound − Fetch Latency Bound` | 同上 |
| Memory Bound | `Backend Bound × (r7005 + r7006) / r7001` | 可复现打印结果；`r7006` 有未计数诊断，不能把打印的 0 直接认定为真实零 |
| Core Bound | `Backend Bound − Memory Bound` | 与打印结果一致；继承 Memory Bound 的证据限制 |
| idle | 单独从目标 CPU 范围的 `/proc/stat` 时间增量定义 | 不由上述 PMU 公式生成；正式采集已通过循环门控接入 |

分母系数 6 来自本次原始计数与 DevKit 输出的核对，不是从 sysfs `caps/slots` 猜测出来的，也不套用 HIP08 或 HIP12 公式。具体事件的完整硬件语义、SMT 口径及事件轮转的缩放信息仍需进一步确认。

官方[Topdown 命令说明](https://www.hikunpeng.com/doc_center/source/zh/kunpengdevps/userguide/cliuserguide/KunpengDevKitCli_0033.html)定义 `-L 1` 顶层、`-L 2` Core、`-L 3` Memory、`-L 6` Frontend，且不同版本提供的分类结构有差异。本次实际输出为 `Backend → Core / Memory`，`Resource Bound*` 位于 Core 之下，避免重复加到 Backend。

## 发现并验证的采集范围问题

| 方式 | 2 秒探针结果 | 对文档负载的影响 |
|---|---|---|
| DevKit launch，直接执行忙循环 | 约 57.8 亿 cycles | 单进程计数正常 |
| DevKit launch，父 Python 启动忙循环子进程后等待 | 仅约 1816 万 cycles | 该方式没有证明覆盖子进程，不能直接用于包含 pdftoppm/LibreOffice 的完整工具链 |
| CPU 范围，在目标 CPU 上另启忙循环进程 | 约 58.1 亿 cycles | 已证明可观察目标 CPU 上独立进程；也会包含该 CPU 上其他任务，正式使用需控制干扰 |

CPU 范围探针使用无网络、只读工具挂载的临时容器，增加 `PERFMON` 权限，不修改宿主 PMU 设置。一次从受限 Python 包装器访问 Docker socket 的失败保留在 `devkit-cpu-scope-short-probe.json`；获准直接调用 Docker 后的成功结果另存 stdout/stderr，未覆盖失败记录。

本机 cgroup 为 hybrid 布局，当前 DevKit 文档声明不支持 hybrid cgroup 配置，暂不采用 `-G`。不能只包装宿主 `docker run` 客户端并假定会追踪到容器 workload。

## 当前采集与复核

正式采集采用 CPU 范围模式，控制程序在 CPU 9；perf 则采回放进程树。七例两路各五次，具体窗口、权限范围、包络和证据层级见正式报告。经验公式、SMT 和复用语义的边界继续保留，没有把工具打印零值直接解释为硬件零。

短探针材料仍在 `hip09-preflight-20261027/`，可独立核验：

```bash
python3 -B analysis/topdown/verify_probes.py analysis/topdown/hip09-preflight-20261027
```

五次实际测量的验证与重算见 [CAMPAIGN.md](CAMPAIGN.md)。不要重新执行已完成的补采脚本来“刷新报告”；报告分析只读取现有数据。
