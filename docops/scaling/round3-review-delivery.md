# 审计收尾（F1–F8 及低优先级边界）交付

针对 `scaling-round3-fix-review-20261106`（review + additional-findings）定位的八项问题及两项低优先级边界，
完成代码修复、定向测试、离线复验与新镜像构建，并仅对 016 两档做真实功能复验。未运行 Agent/model、
未做 perf/DevKit 采集、未更新正式报告/HTML、未提交推送、未删除历史证据/镜像/容器、未做 Git 重置。

## 1. 问题逐项修复位置

| 项 | 问题 | 修复 | 位置 |
|---|---|---|---|
| F1 | 016 异常说明 C 列用 D(预测量) 而非 F(超出量)；验证器漏 C 值 | builder/expected 的 C 公式改用 `TEXT($F...)`；验证器新增 `_parse_issue` 逐条解析 C 文本并与 overage 语义/数值比对（含 Base/Stress），空说明仅 oracle 证明时允许 | `cases/016/scripts/build_forecast_dashboard_variant.py`、`cases/016/expected.py`、`cases/016/scripts/validate_forecast_dashboard_variant.py` |
| F2 | 016 图表月份标签未验 | `verify_period_sums` 增加 A21:A24 标签与顺序核验（含重复/错序），保留 B/C 数值及两条系列 cat/val 引用检查 | `cases/016/scripts/validate_forecast_dashboard_variant.py` |
| F3 | pilot 容器名固定 `-tmp`，保留后重采冲突 | `build_create` 支持唯一容器名；`launch` 传入 campaign/stamp 后缀，不删除旧容器 | `analysis/docops/pilot.py`（`build_create`/`launch`） |
| F4 | 复验未强制只读 | `functional_fixed_campaign` 复验容器：`/repo`、`/results`(归档)、`/render`(渲染证据) 均 ro，报告写入独立可写 `/report`；记录 inspect 挂载证据；复验前后对交付文件计算 SHA256，不一致即失败 | `docops/scaling/functional_fixed_campaign.py`（`build_verify_spec`/`post_verify`） |
| F5 | 验收门槛缺失 | 新增 `acceptance_problems`：workload 状态/轮次/逐步 rc、post_verify rc 显式 0、报告解析成功且 passed 显式 true、渲染契约、frozen 绑定、归档绑定全部必须通过；任一缺失/失败即 task/campaign failed 并停止 | `docops/scaling/functional_fixed_campaign.py`；同步修复 `functional_all_campaign.py` |
| F6 | 索引先算 campaign.json 再改文件 | 重排：被索引文件（证据）先终写→写索引→真实全量回读→在独立排除的 `campaign.index-verification.json` 记录结果；campaign.json 与索引文件/核验记录明确排除（避免自引用）；回读失败落盘 failed 并置 status=failed | `docops/scaling/functional_fixed_campaign.py`（`index_campaign`/`readback_index`/`verify_existing_index`）；同步修复 `functional_all_campaign.py` |
| F7 | resume 删结果/删容器/重跑成功 workload | 每次真实尝试用新 attempt 目录与新唯一容器；已完成 workload 仅复用或离线复验，绝不重跑；workload 失败保留原尝试，新尝试写新目录；`bindings_ok` 复用前核对 recipe/input/expected/归档 | `docops/scaling/functional_fixed_campaign.py`（`new_attempt_dir`/`decide_action`/`run_task`/`bindings_ok`）；`functional_all_campaign.py` 加完成结果防删 |
| F8 | 029 法律页样式未验 | 冻结输入（合成源 pptx）在 prepare 时生成 `legal_slide.semantic_snapshot`（背景、按序形状的类型/几何/填充/线条/字体与文本 run、媒体数、备注）；验证器用同规则归一化快照比对；归一化排除 ZIP 时间戳/rId/部件名重编 | `cases/029/synth.py`、`cases/029/expected.py`（透传）、`cases/029/scripts/validate_qbr_release_variant.py` |
| 边界 a | 009 TOC 收敛误判 | `settle_toc` 以两次实际页号一致为收敛（最后允许迭代收敛也 stable=true）；达上限未收敛明确 `RuntimeError` 并带诊断；最终 DOCX/PDF/PNG/报告对应同一最终状态 | `cases/009/scripts/update_toc_and_render.py` |
| 边界 b | build_scaled 未固定不可变基础 | 构建用本地 pin tag（`docops-replay:base-57483856`，验证解析为不可变 id）作为 `--build-arg BASE_IMAGE`，记录 build_argv 与 base_id | `docops/docker/build_scaled.py`、`Dockerfile.scaled` |

## 2. 正反例及故障注入测试结果

- 016（host 36 项）：末行预测/收入/容量缓存错、末图表源缺失/错、Demand Raw 末行篡改、场景切换行值错而标记不变、末异常删除/替换成首单元/身份错、图表漏末单元贡献、合法零通过；新增 F1 反例（末条说明替换为错误文字、说明用预测量而非超出量）、F2 反例（末月错/重复/错序）全部失败。
- 009（host 24 项）：目录旧页/末项错/标题对目标页错/有字段无结果全部失败；新增 TOC 收敛 mock：首轮收敛、末轮收敛 stable=true、达上限未收敛抛错。
- 029（image 22 项）：法律页背景变色、字体颜色/大小、形状移动/缩放、文字/备注改变全部失败；正常父模板经 builder 保存仍通过；语义快照在 expected 中且 media=0。
- functional_fixed（host 28 项，mock）：验收门槛各缺失分支失败、只读挂载规格（/repo /results /render ro、/report rw）、resume 永不重跑已完成 workload、索引顺序/篡改检测/无漂移/失败落盘。
- pilot（host 12 项）：镜像解析/身份拒绝/安装路径/容器名唯一。
- 全量回归：image venv 229 项 + host 100 项全部通过；`git diff --check` rc=0。

## 3. 真实核验 vs mock

- 真实核验：016 两档（模型缓存与数值、全量异常及正确说明、四期标签/图表引用与汇总、Base/Stress、输出/渲染/归档/只读复验）；029 已有输出（041/081 页）离线复验。
- mock/定向测试：009 目录收敛、pilot 命令构造/身份拒绝/容器名、functional 驱动失败分支与索引、016 错误注入反例（临时 OOXML 副本）、029 法律页样式反例。
- 复验使用同一验证器的独立进程，如实命名，非第二套独立实现；补上的规则正确性由错误注入反例证明。

## 4. 新镜像身份与安装态

- 新镜像 `docops-replay:openeuler-scaled-reviewed` = `sha256:9ae9d418980ab88a305eb37fc2399edadea129a70d803cdbc642357daa56f7d6`
- 基础身份：`--build-arg BASE_IMAGE=docops-replay:base-57483856`，已核验解析为不可变 `sha256:57483856a27942ffd4aef853950ca66b00c12b0787aae6c1dac74371d03e6164`；build_argv 与 base_id 记录在 `docops/docker/records/20261106T074728Z-scaled-6d84f409/build-inputs.json`。
- 安装态（network=none、无源码挂载）通过：Python 3.12.3、既有工具库、官方 12 与 scaling 24 static_valid、环境预检 rc=0、绑定无缺失。记录 `.../install-state.json`。
- 历史镜像保留：`openeuler-scaled`、`openeuler-scaled-fixed`、`openeuler-unified-candidate-04` 及更早候选；旧构建失败记录 `20261106T074544Z-scaled-773b51ac` 保留。

## 5. 016 两档真实复验与正确异常说明样例

| 变体 | 回放 | 完成/成功/失败 | ROI(s) | post-verify | 渲染 | 异常数 |
|---|---:|---:|---:|---|---|---:|
| 016-u100 | 1 | 1/1/0 | 8.80 | rc=0 passed=true 交付未变 | 1 dashboard | 252 |
| 016-u500 | 1 | 1/1/0 | 19.70 | rc=0 passed=true 交付未变 | 1 dashboard | 1292 |

正确说明样例（016-u500 首条异常）：预测量 1044.69、容量 980、超出量 64.69 → C 列“Forecast exceeds capacity by 64.7 units”（使用 F 超出量，不再写成 1044.7）。
四期标签 `Jun/Jul/Aug/Sep`，图表 2 系列（Total Forecast Units/Capacity）引用 `$B$21:$B$24`/`$C$21:$C$24` 与类目 `$A$21:$A$24`；Base/Stress 全模型值/KPI/异常/图表/观察全 true。campaign：`results/docops/scaling-reviewed-functional-20261106T074957Z-a3703f71/`。

## 6. 029 已有输出离线复验

对既有 `scaling-fixed-functional-.../029-u5|u10` 的交付 PPTX（未重新生成）用新语义快照验证器离线复验：errors=[]，slide_count 41/81；对临时副本把背景与文字改红后 errors 含 `locked legal semantic snapshot changed`（背景 BACKGROUND(5)→SOLID(1)/FF0000、字体色→FF0000）。

## 7. 24 项集合与受保护材料哈希

- payload-all 重新生成后 24 项、418 文件、static_valid；catalog==dirs==manifest。
- 官方 payload、round1 payload、round2 payload 的 tree 哈希前后不变；official index `8651b0ba…`。
- 已有八项与各自原 payload 逐字节一致；其他十项新增变体与修复前逐字节一致。
- 受影响六项任务 tree 哈希（旧→新）：009-u100 `a636f69a→dce0adc5`、009-u500 `d1236129→a54fa073`、016-u100 `059efa59→046618fe`、016-u500 `a29f266b→e9defd23`、029-u5 `933078d8→3cd742ad`、029-u10 `8658620b→b6e0f15c`。
- 029 输入 pptx 与上一轮逐字节一致（`ff1e050b…`/`f1d7d269…`）；029 units.json 因新增 `semantic_snapshot` 变化（新哈希 `21227d9c…`/`694ca984…`），已如实登记。

## 8. 全量归档索引核验

- reviewed campaign `campaign.sha256-index.json` 覆盖 36 个证据文件，独立 `campaign.index-verification.json` status=passed、files_checked=36；索引排除范围明确（campaign.json、索引文件、核验记录），无自引用；索引后无被索引文件被修改（files newer than index=[]）。
- 只读回读全部匹配；篡改检测（`verify_existing_index`）与索引失败落盘已 mock 验证。

## 9. 重试、恢复、未解决问题及边界

- 016 两档首次运行即成功；期间经历三次驱动接线修复（docker 前缀、/results rw 断言、`-c` 脚本参数），失败尝试（`attempt-…bbd4aa49`、`attempt-…346cc298`）与 verify 失败记录全部保留，恢复时只对已完成 workload 重试离线复验，未重跑成功 workload、未删除旧文件/容器。
- 009 目录收敛与驱动失败分支用定向测试验证（未真实重跑 009 workload）。
- 029 仅离线复验已有输出，未重新生成 PPT。
- 未解决问题：`functional_all_campaign.py`（历史驱动）已修复同类索引/门槛/防删问题，但未用于本轮真实采集；复验仍复用同一验证器（如实命名）；异常说明数值容忍 0.051（TEXT 一位小数舍入），已用正反例覆盖。
- 完成后停止，不自动开始性能采集。
