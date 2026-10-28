# HIP09 Topdown 核验

已取得 DevKit Tuner CLI 26.0.RC1，并通过基础事件、顶层四分类、前端分解、后端分解及采集范围的短探针。尚未启动七个文档用例，也未计算 Topdown 相似度。证据在 [本次核验目录](hip09-preflight-20261027/qualification.json)，算术核对见 [arithmetic-verification.json](hip09-preflight-20261027/arithmetic-verification.json)。

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
| idle | 单独从目标 CPU 范围的 `/proc/stat` 时间增量定义 | 不由上述 PMU 公式生成；尚未接入正式采集 |

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

## 正式采集前还需完成

1. 冻结当前版本的模型选择依据、公式证据层级、事件及 user/kernel 口径；补核未计数诊断及事件轮转的缩放信息，禁止将未知项默认为 0。
2. 实现 CPU 范围与已有单调时钟 ROI 标记的衔接。覆盖正式循环中的 Python、渲染和 LibreOffice 进程线程，排除预检、归档与独立审计；采集器置于目标范围之外。
3. 用小型父子进程 fixture 验证开始／结束门控和计数范围，再安排一个 PDF 试点。所有用例使用相同的权限态范围、CPU/SMT 布局及指标版本。
4. 试点通过后，再执行七例各三次固定重复。顶层四 Bound 计算余弦相似度；热点使用现有物理函数集计算 Jaccard；idle 和子层指标单独展示。

本轮只运行短硬件诊断与离线核对，未重新构建镜像或运行 PDF/XLSX workload。原热点报告未混入这些合成探针。

离线复核命令：

```bash
python3 -B analysis/topdown/verify_probes.py analysis/topdown/hip09-preflight-20261027
```
