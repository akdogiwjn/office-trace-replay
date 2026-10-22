# 新数据集独立深审与性能对比 v2（因验收失败停止）

## 结论

- HR Metro 独立验收通过：73/73 checks；退出码 0。
- Retail Online 独立验收未通过：60 项中 59 项通过，唯一失败为 `source:number_formats_meaning:Online Retail`，单元格 E2:E25。未修改格式、helper 或验证规则。
- 两个输出工作簿在审计前后 SHA256 均未变化。两个 workspace 均只读挂载；实际容器均使用 v11 镜像 `sha256:a005ce959428863b81c17d1f296b2bbf888e5cf51dc7332d93a9b35d504293e4`、Python 3.12.3。
- 按停止条件，未检查/启动新性能采集，未产生新的热点或 XLSX load/save 比例。

## 审计结果

| 数据集 | 独立验收 | 失败项 | 审计前后输出一致 | 容器 ID |
|---|---|---|---|---|
| hr_metro | success (73/73) | — | 否 | `851b08a953eb2fd14e4563b442176eda17bd8e1531a390b19a35e5ad55c882bf` |
| retail_online | failed (59/60) | source:number_formats_meaning:Online Retail | 否 | `0cbe51d6d2dcdb5fd05afd22357a71bd94331d2d64a8562561121f77ae561372` |

Retail 的失败是独立 source number-format meaning 检查，不是功能循环验证失败，也不是审计包装的预检失败。该检查表明原始输入与增强输出在 E2:E25 的数值格式语义不一致；证据不足以判断业务是否有意改变，因此保留为失败并停止后续性能工作。

## 执行流程审计更新

已复用 v1 的静态 14 项执行流程审计并更新资产预检、source 绑定和独立验收结果，详见 `execution-flow-audit.json`。source 修复报告确认 prompt 声明哈希与当前副本一致、43 个旧 workload 无字节差异。两个容器的 preflight 均验证 Python、当前 runner、recipe、input、helper 和 source verifier 绑定。旧 v1 失败记录未覆盖。

原功能运行在修复 prompt asset 前完成；其归档 loop verifier 不执行 independent prompt asset 校验。当前审计使用修复后的 source asset，业务 verifier 的文件哈希与功能运行记录一致。

## 性能状态

按用户设定，先深审通过才盘点并采集。Retail 独立验收失败后，未盘点/重算旧 profile、未运行 native 或 py-spy、未生成进程/库/函数对比及 load/lazy-scan/save 百分比。既有静态 load/save 调用次数不作为本次采样比例。

## 证据位置

- `hr_metro/report/independent-verification.json`、`hr_metro/report/preflight.json`
- `retail_online/report/independent-verification.json`、`retail_online/report/preflight.json`
- 各 dataset 目录下的完整容器 inspect、Docker argv、日志和退出码
- `audit-manifest.json`：容器、镜像、运行版本、输入/输出哈希和限制
- `execution-flow-audit.json`：复用并更新的流程审计
