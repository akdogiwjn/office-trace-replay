# 新数据集深度审计与性能对比（受阻记录）

审计对象为 v2-02 中已归档的 HR Metro 与 Retail Online 单轮产物。该报告记录实际审计门槛失败，不把单轮 loop 成功等同独立深度验收通过。

## 结论

- 两个功能 run 均为 1/1/1/0，loop 验证成功，实际容器 image ID 为 `sha256:a005ce959428863b81c17d1f296b2bbf888e5cf51dc7332d93a9b35d504293e4`；归档 SHA256 已复核。
- 审计前工作簿 hash：HR Metro `0c4a170ed1c110bce030595d730966824187b926dc00a6219f3996e95cc366b0`；Retail Online `06b6cffb708df1cdd96f4105aba8c2174a28e62b1da5a0e7cf778733cdfcce87`。HR 审计后 hash 未变。
- HR 首次审计包装也有 workspace 挂载根目录错误；容器日志显示 verifier 实际先在 source prompt hash 预检处退出（exit 1），错误并非由 workspace 造成。第二次使用正确 workspace 根目录后仍在同一 prompt hash 预检处失败：声明 prompt hash `b2190fbd466e9b81db54684e388510310418449d728573be7239c4d6a5088579`，source 副本实际 hash `a3502cdc6b95681fc9dc332305c05b9015201d33bab2b3bc12884d89f02c10b4`。工作簿语义扫描未开始，Retail 深审按停止规则未启动。HR 输出审计前后 SHA256 相同。
- 因独立验收未通过，未启动新 perf/py-spy 采集；没有新数据集的热点占比或 load/save 百分比，不能据此回答热点是否接近 TLC/Industry。
- 静态调用清点显示每轮 12 次 `load_workbook`（7 次 normal、5 次 read_only）、1 次 openpyxl `Workbook.save`、1 次 LibreOffice recalc/store。它们是调用次数，不是时间比例。

## 执行流程检查

见 `execution-flow-audit.json` 的 14 项逐条结果。确认 P01-P04 顺序和 loop-only 边界；loop verifier 不做源数据逐单元格/样式深查或递归依赖扫描。完整原始内容、标记、图表/name/merge、深层业务语义检查没有执行。

HR 使用 NYC MSA 35620 的官方总计作为 KPI，并用同范围 top-5 major 组绘图，14 个公式。Retail 保留 541,910×8 的输入，按交易行定义正向销售指标，并计算全期间 KPI 与 2010 月图，16 个公式。该静态差异足以说明工作量不可直接按“行业”归因，但不提供热点测量。

## 读写路径的静态调用数

见 `xlsx-static-load-save.json`。read_only 的延迟扫描在 recalc 的缓存/公式全表检查和 loop verifier 的新增工作表缓存检查中发生。加载与保存的 py-spy 比例、全部 Python 活动分母、脚本内比例均未取得。

## 最小修复建议

保留现有 source manifest 资产校验。核实两个 manual source 中 `prompts/xlsx.txt` 应绑定到哪个冻结版本；若它们应复用共享 prompt，将 source 副本与声明 hash 同步并刷新受影响 source/manifest/project 绑定。然后只对现有归档 workspace 重新运行 independent acceptance；无需重跑 helper、LibreOffice 或 workload。验收通过后，才继续最小 native/py-spy 采集。

## 限制

一次成功 loop 不能估计重复波动；此次没有新 profile。不存在新热点结论、覆盖比例或函数级 load/save 百分比。旧 TLC/Industry/legacy 小 HR/Retail 的既有报告仅列在 performance inventory，未重算或外推到新数据集。
