# 第三轮规模扩充审计问题修复（R1–R5）与六项真实复验

针对 `analysis/docops/processed/scaling-round3-review-20261106/` 定位的五项问题完成修复，
定向检查、修复镜像构建与受影响六项变体的真实功能复验均通过。未运行 Agent、未做 perf/DevKit 采集、
未更新正式报告/HTML、未提交推送、未删除历史材料/镜像/容器、未做 Git 重置。

## 1. 五项审计问题逐项修复及代码位置

| 审计项 | 问题 | 修复 | 代码位置 |
|---|---|---|---|
| R1 | 016 checker 接受错误的行缓存与缺失的图表数据缓存 | 验证器改为按冻结 expected 逐行核验全模型业务值（month/base/actual/growth/forecast/price/revenue/capacity/flag/rank/unit）、Demand Raw 业务值、完整异常行、KPI、四期图表汇总缓存与图表两条系列的 cat/val 引用；空缓存仅由 oracle 证明（Breach Rank 在非 breach 行）；类型按字段处理（0/False 合法、错误字符串/类型失败）；场景 Base/Stress 对副本全量重算并核验全模型值/KPI/异常/图表。先核验交付工作簿自身缓存，再重算副本 | `cases/016/scripts/validate_forecast_dashboard_variant.py` |
| R2 | 016 用 N 类目图表、固定十条异常槽 | 仪表盘改为四期汇总图表（4 类目×2 系列），删除逐单元 SUMIF 全表重复；Exception Review 完整容纳冻结默认场景全部异常（252/1292），新增 Unit 列实现单元+期次追溯（登记结构变化）；KPI“MODEL RECORDS”命名（不再把 2000 条单元期次记录称为月份）；保留只渲染首页与模型表多页打印 | `cases/016/scripts/build_forecast_dashboard_variant.py`、`cases/016/expected.py` |
| R3 | 009 目录硬编码 3–7 页、验证器只查字段存在 | 009 私有步骤 `update_toc_and_render.py` 用现有 LibreOffice 环境先排版测量各章节真实页号（pdftotext，跳过目录页），将真实页号写入交付 DOCX 的 TOC 缓存，重排版确认稳定（迭代上限 3，实际 2 次稳定），最终 PNG 来自更新后的交付 DOCX；验证器在正式模式独立重排版并核对全部目录项 | `cases/009/scripts/build_incident_manual_variant.py`、`update_toc_and_render.py`、`validate_incident_manual_variant.py` |
| R4 | 029 变体替换了父任务八类页面 | 恢复父任务八类公开页（title/agenda/market_context/kpi/risks/mitigation/decision/appendix）并逐单元参数化；agenda 列出单元内的绝对页号与负责人，decision 恢复为三条陈述卡+日期卡，mitigation 恢复状态着色；页脚只在内容页（父任务同款）；锁定法律页从源保留；每单元传入各自页面引用（按单元索引构建，不用全局同名查找） | `cases/029/scripts/build_qbr_release_variant.py`、`expected.py`、`validate_qbr_release_variant.py`、`cases/029/synth.py` |
| R5 | pilot 仍只读 current-image.json 的 candidate-04 | pilot 新增显式镜像选择：`--image`/`--expected-image-id`（解析并记录实际不可变 image id，不匹配在 workload 前拒绝）、`--installed-payload`（容器内置 payload 路径，不挂载宿主绝对路径）；默认旧调用保持兼容；记录 image/payload_source/runner/recipe/collection 绑定；docker 参数位置正确，runtime/CPU/控制器设置沿用 | `analysis/docops/pilot.py`（`resolve_image`、`build_create`）、`analysis/docops/tests/test_pilot_image_selection.py` |

## 2. 关键错误注入反例修复前后结果

反例在新交付 016-u500 工作簿的临时副本上调用修复后 check()（不动原输出）：

| 反例 | 修复前 | 修复后 |
|---|---|---|
| Forecast Model!E2001 缓存 → 999999999 | 全部通过 | `model_values=False`，拒绝 |
| 最后图表数据源单元格（新布局 Dashboard!B24）缓存缺失 | 通过（旧 B539 布局已变，动态定位最后图表数据源） | `caches_present=False`，报 missing B24 |
| 末行收入/容量缓存错误、Demand Raw 末行篡改、场景切换中行值错但 Breach 标记不变、末异常删除/替换成首单元/身份错误、图表漏掉末单元贡献、合法零值通过 | （旧验证器无此类检查） | 全部回归测试覆盖并失败/通过（见 `tests/test_scaling_016.py`） |

009 目录反例（旧 3–7 页、末项页码错、标题对目标页错、有字段无正确结果）在 `tests/test_scaling_009.py` 中全部失败；029 八类页面/锁定法律页/末单元反例在 `tests/test_scaling_029.py` 中全部失败。

## 3. 016 全量异常、四期图表与双场景数值核验

- 交付工作簿：016-u100 模型 400 行、Exception Review 252 行（=默认 Stress 全部异常）；016-u500 模型 2000 行、异常 1292 行。
- 图表：2 系列（Total Forecast Units / Total Capacity），类目 `Dashboard!$A$21:$A$24`（四个期次），值区 `$B$21:$B$24`/`$C$21:$C$24`；两条系列 cat/val 引用均核验。
- 双场景（对副本重算）：Base 与 Stress 的 `model_values/kpi_values/exception_values/period_summary_values/watch_values` 全部 true；交付工作簿自身缓存全量通过（`caches_present=True`）。
- 每期汇总样例：016-u500 四期 forecast sums ≈ [499290, 502132, 500076, 500570]，capacity sums = 490000（980×500）。

## 4. 009 全部目录项与实际页号核验

- 009-u100 TOC：Publication Summary=3、Response Timeline=3、Customer Communication=7、Control Exceptions=11、Action Register=15、Appendix A=19、Appendix B=23。
- 009-u500 TOC：3、3、21、38、55、72、89（不再把 Control Exceptions 标为 4）。
- 两档均 `toc_page=2`、`iterations=2`、`stable=True`；验证器独立重排版后全部目录项与交付 DOCX 缓存一致（post-verify rc=0 passed=True）；最终 PNG 来自交付 DOCX（rendered_v2/page-*.png，26/105 张）。

## 5. 029 与父任务八类页面的对应表

| 单元内序 | 变体旧页（已废弃） | 恢复后父任务页 | 关键对象 |
|---|---|---|---|
| 1 | market_context | title | 深色标题、三个装饰圆、单元名/ID/日期 |
| 2 | kpi | agenda | 6 段议程表（Section/Slide/Owner，单元内绝对页号） |
| 3 | risks | market_context | 三张 callout + QBR lens |
| 4 | mitigation | kpi | KPI 表 + EXECUTIVE SIGNAL 卡 |
| 5 | decision | risks | 风险表（Risk/Count/Owner/Mitigation） |
| 6 | action_register | mitigation | 措施表 + 状态着色 + EXECUTION WINDOW |
| 7 | data_notes | decision | 三条决策陈述卡 + DECISION DATE 卡 + 备注 |
| 8 | unit_summary | appendix | PUBLIC SOURCE/数据时效/来源标准卡 |

29-u5=41 页、029-u10=81 页；每单元八类页 + 末尾共享锁定法律页（从源保留文字/形状/备注）。页脚只在内容页（within 2..7），与父任务一致；只渲染第一页。

## 6. 六项新镜像真实复验结果与重试记录

新镜像 `docops-replay:openeuler-scaled-fixed`，独立新容器、network=none、cpuset 0-9、保留停止容器、无宿主源码挂载（用镜像内置 payload/脚本）：

| 变体 | 回放轮 | 完成/成功/失败 | ROI(s) | post-verify | 渲染 |
|---|---:|---:|---:|---|---|
| 009-u100 | 1 | 1/1/0 | 20.36 | rc=0 passed | 26 PNG |
| 009-u500 | 1 | 1/1/0 | 87.92 | rc=0 passed | 105 PNG |
| 016-u100 | 1 | 1/1/0 | 8.72 | rc=0 passed | 1 dashboard |
| 016-u500 | 1 | 1/1/0 | 19.54 | rc=0 passed | 1 dashboard |
| 029-u5 | 1 | 1/1/0 | 10.07 | rc=0 passed | 1 首页 |
| 029-u10 | 1 | 1/1/0 | 16.53 | rc=0 passed | 1 首页 |

无失败轮次、无 OOM；失败/重试记录为零（本轮全部一次通过）。独立进程只读复核复用同一验证器（如实命名），补上的验证规则由错误注入反例证明有效。campaign：`results/docops/scaling-fixed-functional-20261106T065416Z-cd25a37f/`（234 文件索引回读通过，索引后无文件被改）。ROI 为墙钟执行记录，非性能结论。

## 7. 新镜像实际 ID、基础 ID 及安装态证据

- 新镜像：`docops-replay:openeuler-scaled-fixed` = `sha256:fb037c236fefa455f63c3a22ac957ad24928a5494cddc4675abb66a1df0de089`
- 基础镜像：`docops-replay:openeuler-unified-candidate-04` = `sha256:57483856a27942ffd4aef853950ca66b00c12b0787aae6c1dac74371d03e6164`（保留）
- 旧 scaled 镜像 `6b32b0a53741…` 保留；不使用 docker commit；构建上下文排除 results/原始性能数据。
- 安装态（network=none、无源码挂载）通过：Python 3.12.3、perf/devkit/soffice/poppler/montage、runtime profile、skills、官方 12 与 scaling 24 均 static_valid 且绑定无缺失、两套 payload 安装态 preflight rc=0。记录：`docops/docker/records/20261106T065158Z-scaled-1fd5f2a7/`。

## 8. 24 项材料集合及未受影响内容哈希核对

- payload-all 重新生成后 24 项、418 文件、static_valid；catalog==dirs==manifest。
- 官方 payload、round1 payload、round2 payload 的 tree 哈希在本轮前后不变（见固定 campaign `frozen_before==frozen_after`）。
- 已有八项在 payload-all 中与各自原 payload 逐字节一致。
- 其他十项新增变体（001/013/026/031/pdfwf005 各 2）在 payload-all 重新生成后与修复前哈希逐字节一致（未受影响）。
- 仅 009×2、016×2、029×2 变化（预期）；029 的 units.json/输入 pptx 因恢复父模板材料结构而变化，已登记新旧哈希（修复前/后 task tree：009-u100 ca4bfff6→a636f69a 等），不伪称与旧输入逐字节一致。

## 9. 显式选择新镜像和内置 payload 的后续采集命令示例

```bash
python3 analysis/docops/pilot.py --task 016-u500 --loops 1 --mode both \
  --image docops-replay:openeuler-scaled-fixed \
  --expected-image-id sha256:fb037c236fefa455f63c3a22ac957ad24928a5494cddc4675abb66a1df0de089 \
  --installed-payload /opt/docops/scaling/payload-all \
  --workload-timeout 7200 --step-timeout 3600 --host-timeout 10800
```
命令构造/身份拒绝/路径与挂载已在 `analysis/docops/tests/test_pilot_image_selection.py`（10 项）验证。

## 10. 尚未解决的问题

- 独立只读复核复用同一验证器（如实命名，非第二套独立实现）；补上的规则正确性由错误注入反例证明。
- 029 的 8 类页面内容为逐单元参数化的父任务构成；对 "content" 页（within 2..7）加页脚，title/agenda 与父任务一致无页脚。
- 016 图表为四期汇总（非每单元类目），异常表完整输出（252/1292 行）；这是已登记的结构调整（新增 Unit 列、移除逐单元 SUMIF）。
- 未做任何正式性能采集/热点覆盖/相似度计算；不更新正式报告/HTML；未提交推送。
