# DocOps 第三轮：剩余八项规模扩充、功能验收与统一镜像打包

本轮一次性完成：八项任务的参数化构建/合成输入/独立 expected/动态验证、新增十六个规模变体、
统一 24 项 payload 组装、小 fixture 正反例、十六项真实功能回放、新统一镜像构建与安装态验收。
未运行 Agent、未做 perf/DevKit 正式采集、未更新正式报告/HTML、未提交推送、未删除旧镜像/容器/输入/历史证据。

## 1. 修改文件与用途

| 文件 | 用途 |
|---|---|
| `docops/scaling/cases/common.py` | 注册 16 个新变体（种子/规模/派生）与 8 个父任务 PARENT_SOURCE；新增 `VARIANT_ORDER_ALL`（24 项） |
| `docops/scaling/prepare.py` | 改为按父任务注册 builder/validator/command/material 的 `PARENT_CONFIG` 分派（013 不会走 014 脚本、001 不会走 003 脚本）；新增 `EXISTING_SOURCE` 将已有 8 项逐字节复制进 payload-all；显式允许 `payload-all` 目标；新增 8 个父任务的命令/阶段/输出路径与 16 项 step 定义 |
| `docops/scaling/cases/001|009|013|016|026|029|031|pdfwf005/` | 每个父任务独立 `synth.py`（合成输入+材料+元数据）、`expected.py`（独立 oracle）、`scripts/build_*.py` 与 `scripts/validate_*.py` |
| `docops/scaling/tests/test_scaling_{001,009,013,016,026,029,031,pdfwf005}.py` | 每项小 fixture 正反例定向测试 |
| `docops/scaling/functional_all_campaign.py` | 十六项串行真实功能回放驱动（独立容器、独立只读复核、渲染计数、索引） |
| `docops/scaling/payload-all/` | 统一 24 项 payload（已有 8 项逐字节 + 新增 16 项），static_valid |
| `docops/scaling/staging-all/` | 新增 16 项生成的 manifest/raw_records 快照 |
| `docops/docker/Dockerfile.scaled` | 基于 candidate-04 构建 `docops-replay:openeuler-scaled`（安装 payload-all 与公共入口） |
| `docops/docker/build_scaled.py`、`docops/docker/check_scaled_install.py` | 构建记录与安装态验收（network=none、无源码挂载） |
| `docops/docker/records/20261106T051308Z-scaled-416cc456/` | 通过安装态验收的构建记录（build-inputs/image-id/install-state/closeout） |
| `results/docops/scaling-all-functional-20261106T041702Z-fa404f12/` | 十六项功能回放 campaign（trial-record、post-verify、渲染证据、索引） |

失败尝试如实保留：`docops/docker/records/20261106T050809Z-scaled-0500d3d5/`（安装态验收首次失败：官方 recipe files 无 bytes 字段，已修复）及功能 campaign 内的多次 `--resume`（修复 001 日期禁止词碰撞、013 平均分口径、016 图表引用引号、pdfwf005 montage 多片联系表、026 soffice --outdir、016 失败轮次残留等）。

## 2. 24 项活动规模集合与新增 16 项事实

| 变体 | 主规模 | 输入页/记录 | 输出结构 | 渲染 | input_sha 前 12 位 |
|---|---|---|---|---|---|
| 001-u100 | 100 受控文档记录 | 100 记录 | 6 表、逐记录行 | 18 PNG(150dpi) | 00b3a7239593 |
| 001-u500 | 500 记录 | 500 记录 | 6 表、逐记录行 | 75 PNG | afa7f706d1a6 |
| 009-u100 | 100 处置案例 | 100 案例 | 6 表、逐案例行 | 26 PNG | 5db028ca830d |
| 009-u500 | 500 案例 | 500 案例 | 6 表、逐案例行 | 105 PNG | 4286180cfee9 |
| 013-v100 | 100 供应商 | 100 | 3N 评分行+N 价格/COI/登记行 | 40 PNG + contact sheet | fc00df0a7695 |
| 013-v1000 | 1000 供应商 | 1000 | 3000 评分行+1000 价格/COI 行 | 340 PNG | 0515f0b98fd0 |
| 016-u100 | 100 单元×4 期=400 模型行 | 400 | 400 行公式+仪表盘聚合 | 1 页 dashboard | 79ee795c1a76 |
| 016-u500 | 500 单元×4 期=2000 模型行 | 2000 | 2000 行公式+仪表盘聚合 | 1 页 dashboard | ac81e92a8e36 |
| 026-u5 | 5 披露单元×9 页 | 45 页 | 45 页、每单元原生图表 | 45 JPEG | ac2a22588d2b |
| 026-u10 | 10 单元×9 页 | 90 页 | 90 页、每单元原生图表 | 90 JPEG | 3e41dcb8bb62 |
| 029-u5 | 5 单元×8 页+1 锁定法律页 | 41 页 | 41 页 | 1 页（首页） | ff1e050ba789 |
| 029-u10 | 10 单元×8 页+1 锁定法律页 | 81 页 | 81 页 | 1 页（首页） | f1d7d269895d |
| 031-u5 | 5 组×5 页 | 25 页 | 25 页+书签 | 25 PNG(144dpi) | 508c842346de |
| 031-u20 | 20 组×5 页 | 100 页 | 100 页+书签 | 100 PNG | 508c842346de |
| pdfwf005-u5 | 5 组×7 输入→6 活页 | 35→30 页 | 30 页+书签/页标签 | 30 PNG + 5 片联系表 | 849dc07a7c1f |
| pdfwf005-u20 | 20 组×7 输入→6 活页 | 140→120 页 | 120 页+书签/页标签 | 120 PNG + 20 片联系表 | b90be649a8ab |

（031-u5/u20 共享同一合成输入 PDF 工件——父任务 builder 不读取输入内容，只重建；规模由 notices.json 的组数驱动。）

## 3. “为什么是真实扩充”的证据

每项 `scale_manifest/scale_metadata` 记录主规模单位与唯一业务 ID 集合、输入实际记录/对象/页数、
输出结构数、渲染范围与实际图片数、首/中/末单元事实、被参数化的固定范围/公式/命令、保留与改变的父行为。
builder 从材料 JSON（units/records/vendors/notices/groups/cases）真实读取并按记录数生成输出：
- 001/009：受控记录/处置案例逐条进入六个业务表；001 有效日期避开父任务禁止日期。
- 013：供应商登记 N 行、评分 3N 行、价格归一化 N 行（公式随 N 变化）、COI N 行、Award 按全量加权分、Summary 全量公式+缓存；所有公式与缓存全量校验。
- 016：Demand Raw 4N 行、Forecast Model 4N 行全量公式（场景 INDEX/MATCH）、Capacity Flag、Exception 槽位、Dashboard 聚合覆盖全部行；Base/Stress 场景切换真实重算并校验。
- 026：每单元实际执行 9 页构建（含原生图表与嵌入数据），绝不复制已完成页；45/90 页全部渲染为 JPEG。
- 029：每单元 8 页真实生成 KPI/风险/措施/决策表格，锁定法律页从源保留；只渲染第一页。
- 031：ReportLab 对每组实际调用 5 类页面绘制；书签绝对页号覆盖全部组。
- pdfwf005：真实读取输入 PDF，逐组删除 DRAFT 前缀、删除废弃页、重排、加书签/页标签；全部保留页渲染进联系表。

## 4. 相对父任务保留与改变的执行行为

- 保留：公共 replay.py 入口、官方 12 项不变、021 字体环境、只渲染首页（016/029）、docx 渲染、144/130/150 DPI 渲染、montage 参数、禁止词 token 边界、workspace reset 不碰 /results。
- 改变（均登记在 modified_workflow）：016 的 Forecast Model/Exception Review 打印改为 fitToWidth=1/fitToHeight=0（避免 fit-to-one-page 压坏大量记录）；026 的 soffice convert 加 `--outdir /root/tmp/docs`（父任务 cwd=/root/tmp/docs）；pdfwf005 联系表因保留页 >6，ImageMagick 按 3×2 网格写出多个编号 tile（同一次 montage 调用，未新增工具启动）。

## 5. 正反例与定向测试

`195 项测试通过`（镜像 venv `unittest` 全绿，含既有 003/014/021/037/replay/word_pdf）。新增 8 个 case 的 fixture 均含正反例：删除最后业务单元→失败、末单元改首单元事实→失败、改末单元关键数值→失败、末行公式缺失/范围截断/后部缓存缺失→失败、图表指向首单元/备注错误/锁定法律页被改→失败、缺最后组/书签目标错误/废弃页与 Draft 残留→失败。禁止词用 token 边界避免合法值子串误报。

## 6. 新增 16 项功能结果、独立复核、重试与证据目录

campaign：`results/docops/scaling-all-functional-20261106T041702Z-fa404f12/`。
每项均为独立新容器（network=none、cpuset 0-9、PERFMON/SYS_PTRACE、seccomp unconfined、保留停止容器），
请求/完成/成功/失败=1/1/1/0，全部步骤 ok；独立只读复核（post-verify，重新运行各 case 验证器于冻结 expected）
rc=0 且 passed=True；渲染计数已核。roi_wall_s 仅作功能执行记录，不作性能结论。无 OOM/超时（除已修复并保留记录的失败轮次）。

## 7. 新镜像实际 ID、基础镜像、版本与安装态

- 新镜像：`docops-replay:openeuler-scaled` = `sha256:6b32b0a53741a42562ca3e93894139c34cf774a214b7995e44af0cec61f14967`
- 基础镜像：`docops-replay:openeuler-unified-candidate-04` = `sha256:57483856a27942ffd4aef853950ca66b00c12b0787aae6c1dac74371d03e6164`（保留未覆盖）
- 构建记录：`docops/docker/records/20261106T051308Z-scaled-416cc456/`；被替换的旧 tag 镜像 id `60b053635c…` 记录在 closeout，未删除。
- 安装态（network=none、无源码挂载）通过：Python 3.12.3 /opt/docops/venv；perf 6.6.0、devkit 26.0.RC1、soffice/pdftoppm/pdftotext/pdfinfo/montage 均在；runtime profile `seven-case-openeuler-unified`；skills doc/xlsx/pptx/pdf 已装；官方 12 项与 scaling 24 项均 static_valid 且全部 recipe 命令/脚本/输入/expected/skills 绑定无缺失；两套 payload 经安装态 replay 入口 `validate-only --env-check` 均 rc=0、无环境错误。
- 明确区分：16 项真实功能回放是在候选镜像 candidate-04 上以只读挂载 payload 完成的；新镜像 `openeuler-scaled` 的验证是安装态解析/预检，不写成“新裸镜像已完成 36 项真实回放”。

## 8. 原十二项、已有八项、历史证据与 HTML 未改写的核对

- 官方 payload：index `8651b0ba…`、catalog `068d0942…`，采集前后 tree 哈希一致（campaign preflight frozen_before==frozen_after）。
- 已有八项在 payload-all 中与各自原 payload 逐字节相同（014×2/021×2/003×2/037×2）。
- round1 `payload/`、round2 `payload-word-pdf/` 未在本轮修改；历史采集/报告/HTML 未动。

## 9. 尚未验证与停止的问题

- 新镜像未跑真实 workload（仅安装态预检/解析，符合“安装态验收”边界）；16 项真实回放证据在 candidate-04 + 挂载 payload。
- 渲染证据为文件计数与结构检查（PDF 页数、PNG/JPEG 张数、联系表 tile 数、书签/页标签、公式缓存），未做人工看图；031-u5/u20 的合成输入为同一占位工件（父任务不读输入内容，属已声明行为）。
- 未做任何 perf/DevKit 正式采集、跨任务热点覆盖、相似度或函数覆盖结论。

## 10. 后续性能采集入口建议（本轮不执行）

新镜像 `docops-replay:openeuler-scaled` 已内置 24 项 payload 与公共 `replay.py` 入口，
可对任意规模变体直接 `--payload /opt/docops/scaling/payload-all --task <variant>` 运行；
采集沿用既有 pilot/measurement 链（perf cycles:u、DevKit top-down、离线补符号），
每项一次独立采集即可获得 hotspot 与 Topdown 数据。本轮不做。
