# 数值格式验证修复与离线复验

## 结果

- Retail Online 与 HR Metro 在最终 verifier 版本下均通过 independent acceptance。没有重新生成或保存工作簿；两个输出的前后 SHA256 均一致。
- Retail 日期格式 `m/d/yy h:mm` → `m/d/yyyy\ h:mm` 被判定为同一日期时间字段序列，仅属表示变化。实际单次扫描发现 541,909 个差异、1 种格式对，允许表示变化 541,909，严格失败 0。
- 旧 v2 Markdown 曾把 `output_unchanged` 显示为“否”，与机器记录和相同的前后 SHA256 矛盾。本报告的状态表由哈希比较函数生成；历史报告保留原状。

## 输出 hash 状态（生产报告函数生成）

| 数据集 | 独立验收 | 失败项 | 审计前后输出一致 | 容器 ID |
|---|---|---|---|---|
| retail_online | success (60/60) | — | 是 | 892330bd5e08627726a142e1db1f1b603bccd5f3d9d4fa988707ca4a2c8549cd |
| hr_metro | success (73/73) | — | 是 | 0dba030c54f2ca49642ec6799d3971b64a5c7be3ce7eb6cf6b0e2e0f0212a574 |

## 格式差异统计

| 表 | 全部差异 | 不同格式对 | 允许表示变化 | 严格失败 | 地址样例上限 |
|---|---:|---:|---:|---:|---:|
| Online Retail | 541,909 | 1 | 541,909 | 0 | 24 |

| 源格式 | 输出格式 | 分类 | 数量 | 样例地址 |
|---|---|---|---:|---|
| `m/d/yy h:mm` | `m/d/yyyy\ h:mm` | allowed_representation_change | 541,909 | E2, E3, E4, E5, E6 |

E2–E25 是有上限的样例，不代表只有 24 个单元格变化。完整扫描统计了 541,909 个日期格式单元格。HR Metro 本次没有 number-format 变化。

## 格式比较规则

- 日期字段保留年月日、时分秒及顺序；月份/日期补零、年份两位到四位、格式代码字母大小写和相同字面量的引号/转义序列归一。
- 普通时间与 `[h]`/`[m]`/`[s]` 累计时长分开；累计单位变化、日期字段丢失/换序均严格失败。
- 普通或方括号币种、百分比、引号/转义中的单位保留；locale 与颜色标记分类处理。尾随缩放逗号与千位分隔逗号区分。
- 未支持格式仅在原始代码完全相同的情况下视为未变；不同的 opaque 格式不会被猜测为等价。解析缓存按格式代码复用。

## 最终版本离线验收

| 数据集 | 结果 | 通过/总项 | 失败项 | 输出工作簿前后 hash |
|---|---|---:|---|---|
| retail_online | success | 60/60 | — | `06b6cffb708df1cdd96f4105aba8c2174a28e62b1da5a0e7cf778733cdfcce87` / `06b6cffb708df1cdd96f4105aba8c2174a28e62b1da5a0e7cf778733cdfcce87` |
| hr_metro | success | 73/73 | — | `0c4a170ed1c110bce030595d730966824187b926dc00a6219f3996e95cc366b0` / `0c4a170ed1c110bce030595d730966824187b926dc00a6219f3996e95cc366b0` |

运行身份来自实际容器 inspect：v11 镜像 `sha256:a005ce959428863b81c17d1f296b2bbf888e5cf51dc7332d93a9b35d504293e4`，Python 3.12.3、openpyxl 3.1.5，网络关闭；workspace 只读挂载，报告独立写入。容器 ID、recipe、input、helper、source verifier、runner 哈希和原始日志见 `audit-manifest.json` 与各数据集目录。

## 冻结绑定与测试

新 verifier 已同步至 6 个活动 XLSX source 副本，project-lock 仅更新这些副本与中央 verifier 的 hash。两个容器 preflight、source asset loader 和默认 suite index 检查均通过。输入、helper、manifest、expected、provenance 和 recipe 绑定未改；本轮未修改旧 43 个 workload、原始 XLSX、helper 或成功输出。

31 项直接相关单元测试通过，涉及格式正反例、真实 `original_content()` 小工作簿统计和报告哈希状态生成；语法编译通过。没有运行完整测试套件。

## 边界

格式解析只支持明确列出的 Excel 格式子集；不支持且发生变化时保守失败。本轮没有执行 workload、helper、LibreOffice、性能采集或镜像构建。
