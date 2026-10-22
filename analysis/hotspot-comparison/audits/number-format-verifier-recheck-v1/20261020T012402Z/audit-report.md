# Number-format verifier repair and offline recheck

## 结论

- Retail Online 和 HR Metro 的已有产物均通过修复后的 independent verifier；没有重新生成工作簿、运行 helper/LibreOffice/workload。
- Retail 的日期格式变化是同一日期/时间字段的序列化差异，不再被误判。原审计受 24 个样例上限影响，只显示 E2:E25；新统计在单次扫描中发现 541,909 个此类差异，1 种格式对，严格失败 0。
- 两个输出工作簿的前后 SHA256 相同。历史 v2 Markdown 将 `output_unchanged` 错写为“否”；v2 机器记录及实际哈希为 true。旧报告未覆盖，本报告从哈希重新生成状态表。

## 输出未变化状态（由 SHA256 生成）

| 数据集 | 独立验收 | 失败项 | 审计前后输出一致 | 容器 ID |
|---|---|---|---|---|
| retail_online | success (60/60) | — | 是 | 2859b1f25137ff4fcdf9d41be670a58397b4c7d7aa1f31ad1f84479d48ef666b |
| hr_metro | success (73/73) | — | 是 | c986680c89a9110de9c349701e06dff9e1a090b52ed988253ed2c25ed22bc395 |


## 格式语义规则

- 日期年月日与时分秒字段及顺序参与比较；月份/日期补零、年份两位/四位和格式代码字母大小写按已确认的序列化等价归一。引号字面量、转义文字不被清除。
- `[h]`、`[m]`、`[s]` 作为累计时长单位保留；它们之间以及与普通数字/日期格式不等价。
- 普通/方括号货币、百分比及字面单位保留；locale 和已知颜色标记与币种分离。尾随逗号缩放与千位分组逗号分开解析。
- 不支持的语法仅在原格式代码完全相同时视为未变化；修改后的 opaque 格式不会被推定等价。解析结果按原始格式字符串缓存。

## 实际 Retail 格式差异

| 工作表 | 全部格式差异 | 不同格式对 | 允许表示变化 | 严格失败 | 样例上限 |
|---|---:|---:|---:|---:|---:|
| Online Retail | 541,909 | 1 | 541,909 | 0 | 24 |

格式对明细：

| 源格式 | 输出格式 | 分类 | 数量 | 样例地址 |
|---|---|---|---:|---|
| `m/d/yy h:mm` | `m/d/yyyy\ h:mm` | allowed_representation_change | 541,909 | E2, E3, E4, E5, E6 |

这些 541,909 个差异对应原始 E 列数据行；JSON 同时保留总数、格式对计数和最多 24 个全局单元格样例，E2:E25 只是样例而非影响总范围。

## 离线验收

| 数据集 | 独立验收 | 通过/总项 | 失败项 | 输出前后 hash 一致 |
|---|---|---:|---|---|
| retail_online | success | 60/60 | — | 是 |
| hr_metro | success | 73/73 | — | 是 |

运行环境来自实际容器 inspect：v11 image `sha256:a005ce959428863b81c17d1f296b2bbf888e5cf51dc7332d93a9b35d504293e4`，Python 3.12.3、openpyxl 3.1.5；workspace 只读、报告目录独立可写、网络关闭。容器 ID、实际 source/runner/verifier 哈希、preflight、命令及日志见 `audit-manifest.json` 和各数据集目录。

## 冻结绑定与测试

中央 verifier 已同步到 6 个活动 XLSX source 副本，project-lock 仅更新中央和这些副本对应条目。两个数据集的 source asset、manifest、expected、provenance、input、recipe 和默认 suite 绑定经 preflight 核对；43 个旧 workload 与原始 XLSX、helper、成功输出未修改。

定向测试：`python3 -m unittest tests.test_verifier.NumberFormatMeaningTests tests.test_verifier.OriginalContentPositiveNegativeTests tests.test_deep_audit_report`，30 项通过；相关文件 `py_compile` 通过。未运行完整测试或任何性能采集。

## 限制

解析器不是完整 Excel 格式引擎。对未覆盖语法的变化采取保守失败策略；本次没有重生成工作簿，也没有性能采集。
