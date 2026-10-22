# Retail / Manufacturing / HR 未确认覆盖余量分解

本报告解释既有路径∪机制覆盖率的余量，不改写 coverage.json。A 是样本所属进程实际匹配旧选中切片路径，B 是叶机制在旧选中切片参考采样中出现；R = ROI 样本集合减去 A∪B。各主类别按 R1→R5 互斥分配，类别和都以完整 workload ROI cycles:u period 为分母。

基线 coverage.json SHA256：`f2e80c5e5a7c67f0e6ba192a89da4e0590782847631e7010cb02b033b0bd08c4`。分解代码 SHA256：`7f95b2150402de07417b1c4de4f74afd7386de049d3f55249443239c30f46701`；当前机制/栈指纹代码 SHA256：`5baae41adfae265210f30bb4e580f29bf12877ce9b731ac4a496f624ff57576e`。

阈值为完整 ROI 的 0.5%，先跨完整重复合并同一贡献项再筛选。表中阈值以下权重和前 10 项以外的合格权重单独列出，全部纳入类别总和。栈指纹沿用 stack-prefix-v1：最多 8 帧、至少 4 帧、无未知帧，符号去偏移，DSO 归并为类别。

## retail

旧参考：tlc；切片 X-S1, X-S2, X-S3, X-S4, X-S5, X-S6, X-S7, X-S8。ROI period `292212811365`；R `34.86%`，原 coverage 余量 `34.86%`。

| 余量类别 | 占完整 ROI | 占余量 | r1 / r2（占各自 ROI） | 主要进程/函数（合并权重） | 证据边界 |
|---|---:|---:|---|---|---|
| R1 规范化栈前缀指纹匹配（42632 samples） | 22.79% | 65.37% | r1 23.17% / r2 22.39% | xlsx-verify · _Py_dict_lookup (0.62%)<br>阈值以下 63.59%; 前十以外 0.00% | 栈前缀相等仅证明归一化前缀相同；原覆盖定义不采用指纹，因此仍留在余量。 |
| R2 仅叶函数匹配（84018 samples） | 9.04% | 25.94% | r1 9.02% / r2 9.07% | xlsx-enhance · insert_to_emptydict (0.28%)<br>xlsx-inspect-tool · arena_map_is_used (0.23%)<br>xlsx-verify · PyCFunction_Call (0.21%)<br>（均低于阈值，计入阈值余量）<br>阈值以下 25.94%; 前十以外 0.00% | 只支持叶函数和 DSO 类别相同；不证明栈上下文、业务操作或算法相同。 |
| R3 具体原生机制已知，旧切片参考未观察到（0 samples） | 0.00% | 0.00% | r1 0.00% / r2 0.00% | —<br>阈值以下 0.00%; 前十以外 0.00% | 采样点机制具体，但未在旧选中切片参考样本中观察到；不是旧切片定义明确排除。 |
| R4 符号/DSO 已解析，机制不够具体（2390 samples） | 2.01% | 5.75% | r1 2.03% / r2 1.98% | xlsx-verify · remove_redundant_nops (0.33%)<br>xlsx-verify · tok_nextc (0.15%)<br>xlsx-verify · _PyPegen_update_memo (0.11%)<br>（均低于阈值，计入阈值余量）<br>阈值以下 5.75%; 前十以外 0.00% | 符号/DSO 已解析，但机制规则或上下文不足以细分；不是符号解析失败。 |
| R5 证据不足（未知项或采样质量限制）（324146 samples） | 1.02% | 2.94% | r1 0.65% / r2 1.42% | xlsx-verify · __GI___memcmpeq (0.10%)<br>xlsx-verify · Py_INCREF (0.06%)<br>xlsx-verify · new_reference (0.06%)<br>（均低于阈值，计入阈值余量）<br>阈值以下 2.94%; 前十以外 0.00% | 未知或质量受限样本；不作为新增机制证据。 |

### 重叠诊断（不可与主类别相加）

上层操作、指纹质量、路径来源候选和具体质量原因按 ROI period 统计；同一样本可同时出现在多个诊断项。

- **上层业务操作**：unknown 34.86%
- **指纹质量**：strong 30.55%；weak-unknown-frame 4.25%；weak-short-stack 0.06%
- **质量原因**：no-quality-blocker 30.55%；unknown-frame-in-prefix 3.23%；unknown-dso 1.01%；short-stack 0.06%；unknown-dso-and-symbol <0.01%；unknown-symbol <0.01%
- **R5 互斥原因**：unknown-dso 1.01%；unknown-dso-and-symbol <0.01%；unknown-symbol <0.01%
- **路径来源证据**：no_old_slice_path_candidate 34.86%

证据文件：`raw/retail/r1/out/samples.jsonl` (SHA256 `1887c944a85f74a287e4f03d9151227494cd2e11483f663933493c060f8ea53c`); `raw/retail/r2/out/samples.jsonl` (SHA256 `77c5eeafe8fb106831653a04bea79a63bf48235060b64d019619f5432faea478`); 旧切片参考：`raw/tlc/r1/out/samples.jsonl` (SHA256 `10c3fd0d7a294bede75110d7063483023a647d7236f91534d551613fdd6627cf`); `raw/tlc/r2/out/samples.jsonl` (SHA256 `4625a7a4ec7bb129ca1ae59225c49f56bfba344b6e951d8537322fc6c5b5d9c5`)

## manufacturing

旧参考：tlc；切片 X-S1, X-S2, X-S3, X-S4, X-S5, X-S6, X-S7, X-S8。ROI period `160118367815`；R `35.56%`，原 coverage 余量 `35.56%`。

| 余量类别 | 占完整 ROI | 占余量 | r1 / r2（占各自 ROI） | 主要进程/函数（合并权重） | 证据边界 |
|---|---:|---:|---|---|---|
| R1 规范化栈前缀指纹匹配（12457 samples） | 12.75% | 35.86% | r1 12.53% / r2 12.97% | xlsx-verify · _Py_call_instrumentation_line (0.41%)<br>xlsx-summary-export · _PyFrame_Initialize (0.38%)<br>xlsx-verify · _DK_ENTRIES (0.36%)<br>（均低于阈值，计入阈值余量）<br>阈值以下 35.86%; 前十以外 0.00% | 栈前缀相等仅证明归一化前缀相同；原覆盖定义不采用指纹，因此仍留在余量。 |
| R2 仅叶函数匹配（26907 samples） | 14.25% | 40.08% | r1 10.88% / r2 17.70% | xlsx-verify · unicodekeys_lookup_unicode (0.79%)<br>xlsx-verify · _PyObject_GC_TRACK (0.58%)<br>xlsx-enhance · _Py_dict_lookup (0.57%)<br>阈值以下 34.64%; 前十以外 0.00% | 只支持叶函数和 DSO 类别相同；不证明栈上下文、业务操作或算法相同。 |
| R3 具体原生机制已知，旧切片参考未观察到（0 samples） | 0.00% | 0.00% | r1 0.00% / r2 0.00% | —<br>阈值以下 0.00%; 前十以外 0.00% | 采样点机制具体，但未在旧选中切片参考样本中观察到；不是旧切片定义明确排除。 |
| R4 符号/DSO 已解析，机制不够具体（1645 samples） | 6.39% | 17.98% | r1 5.89% / r2 6.91% | xlsx-verify · tok_get (0.49%)<br>xlsx-verify · _PyCompile_InstrSize (0.31%)<br>xlsx-verify · _PyPegen_is_memoized (0.28%)<br>（均低于阈值，计入阈值余量）<br>阈值以下 17.98%; 前十以外 0.00% | 符号/DSO 已解析，但机制规则或上下文不足以细分；不是符号解析失败。 |
| R5 证据不足（未知项或采样质量限制）（149932 samples） | 2.16% | 6.09% | r1 2.95% / r2 1.36% | xlsx-verify · translate_newlines (0.50%)<br>xlsx-inspect-tool · new_reference (0.17%)<br>xlsx-verify · index (0.15%)<br>（均低于阈值，计入阈值余量）<br>阈值以下 6.09%; 前十以外 0.00% | 未知或质量受限样本；不作为新增机制证据。 |

### 重叠诊断（不可与主类别相加）

上层操作、指纹质量、路径来源候选和具体质量原因按 ROI period 统计；同一样本可同时出现在多个诊断项。

- **上层业务操作**：unknown 35.56%
- **指纹质量**：strong 28.41%；weak-unknown-frame 7.05%；weak-short-stack 0.11%
- **质量原因**：no-quality-blocker 28.41%；unknown-frame-in-prefix 4.88%；unknown-dso 2.10%；short-stack 0.11%；unknown-dso-and-symbol 0.05%；unknown-symbol <0.01%
- **R5 互斥原因**：unknown-dso 2.10%；unknown-dso-and-symbol 0.05%；unknown-symbol <0.01%
- **路径来源证据**：no_old_slice_path_candidate 35.56%

证据文件：`raw/manufacturing/r1/out/samples.jsonl` (SHA256 `057e3d4d8cc65dae0c8c5ec210bee0a5e71a6cdee2d2f1326491fea41827dc97`); `raw/manufacturing/r2/out/samples.jsonl` (SHA256 `795180be2e5cea6d8f587df14320ec5f4a0ef104af4d4a4f194748c741d74c74`); 旧切片参考：`raw/tlc/r1/out/samples.jsonl` (SHA256 `10c3fd0d7a294bede75110d7063483023a647d7236f91534d551613fdd6627cf`); `raw/tlc/r2/out/samples.jsonl` (SHA256 `4625a7a4ec7bb129ca1ae59225c49f56bfba344b6e951d8537322fc6c5b5d9c5`)

## hr

旧参考：tlc；切片 X-S1, X-S2, X-S3, X-S4, X-S5, X-S6, X-S7, X-S8。ROI period `298398733857`；R `38.99%`，原 coverage 余量 `38.99%`。

| 余量类别 | 占完整 ROI | 占余量 | r1 / r2（占各自 ROI） | 主要进程/函数（合并权重） | 证据边界 |
|---|---:|---:|---|---|---|
| R1 规范化栈前缀指纹匹配（9927 samples） | 24.06% | 61.71% | r1 24.78% / r2 23.35% | xlsx-verify · arena_map_is_used (0.41%)<br>xlsx-inspect-tool · PyObject_GetItem (0.39%)<br>xlsx-verify · dictkeys_generic_lookup (0.37%)<br>（均低于阈值，计入阈值余量）<br>阈值以下 61.71%; 前十以外 0.00% | 栈前缀相等仅证明归一化前缀相同；原覆盖定义不采用指纹，因此仍留在余量。 |
| R2 仅叶函数匹配（19524 samples） | 9.25% | 23.71% | r1 8.78% / r2 9.70% | xlsx-verify · _dl_tlsdesc_return (0.28%)<br>xlsx-enhance · unicodekeys_lookup_unicode (0.28%)<br>xlsx-verify · move_legacy_finalizers (0.26%)<br>（均低于阈值，计入阈值余量）<br>阈值以下 23.71%; 前十以外 0.00% | 只支持叶函数和 DSO 类别相同；不证明栈上下文、业务操作或算法相同。 |
| R3 具体原生机制已知，旧切片参考未观察到（2 samples） | <0.01% | <0.01% | r1 0.00% / r2 <0.01% | xlsx-inspect-tool · _init (<0.01%)<br>xlsx-inspect-tool · call_weak_fn (<0.01%)<br>（均低于阈值，计入阈值余量）<br>阈值以下 <0.01%; 前十以外 0.00% | 采样点机制具体，但未在旧选中切片参考样本中观察到；不是旧切片定义明确排除。 |
| R4 符号/DSO 已解析，机制不够具体（969 samples） | 3.03% | 7.77% | r1 2.61% / r2 3.45% | runner · _Py_GetBaseOpcode (0.30%)<br>xlsx-verify · sum_raw (0.26%)<br>xlsx-verify · init_code (0.21%)<br>（均低于阈值，计入阈值余量）<br>阈值以下 7.77%; 前十以外 0.00% | 符号/DSO 已解析，但机制规则或上下文不足以细分；不是符号解析失败。 |
| R5 证据不足（未知项或采样质量限制）（84827 samples） | 2.66% | 6.81% | r1 3.24% / r2 2.07% | xlsx-inspect-tool · element_add_subelement (0.27%)<br>xlsx-summary-export · unlink_chunk (0.27%)<br>xlsx-verify · Py_IS_TYPE (0.21%)<br>（均低于阈值，计入阈值余量）<br>阈值以下 6.81%; 前十以外 0.00% | 未知或质量受限样本；不作为新增机制证据。 |

### 重叠诊断（不可与主类别相加）

上层操作、指纹质量、路径来源候选和具体质量原因按 ROI period 统计；同一样本可同时出现在多个诊断项。

- **上层业务操作**：unknown 38.99%
- **指纹质量**：strong 33.13%；weak-unknown-frame 5.79%；weak-short-stack 0.08%
- **质量原因**：no-quality-blocker 33.13%；unknown-frame-in-prefix 3.13%；unknown-dso 2.55%；unknown-dso-and-symbol 0.10%；short-stack 0.08%；unknown-symbol <0.01%
- **R5 互斥原因**：unknown-dso 2.55%；unknown-dso-and-symbol 0.10%；unknown-symbol <0.01%
- **路径来源证据**：no_old_slice_path_candidate 38.99%

证据文件：`raw/hr/r1/out/samples.jsonl` (SHA256 `3063d7316547ba7c00eb06253e0383fdd6708464111bf406d4d86d47a327db5b`); `raw/hr/r2/out/samples.jsonl` (SHA256 `fd50779466b96b47ea9d21cb40cd34a0aa400d087a644cd473ed0817bedd1487`); 旧切片参考：`raw/tlc/r1/out/samples.jsonl` (SHA256 `10c3fd0d7a294bede75110d7063483023a647d7236f91534d551613fdd6627cf`); `raw/tlc/r2/out/samples.jsonl` (SHA256 `4625a7a4ec7bb129ca1ae59225c49f56bfba344b6e951d8537322fc6c5b5d9c5`)

## 解释边界

共同函数、栈前缀或原生机制分别只支持相应层级的相似性，不能推出相同 Python 业务操作、相同算法或相同优化收益。R3 表示旧选中切片采样中未观察到该机制；它既不证明旧切片定义排除该机制，也不证明该机制是新算法。R5 才是当前采样无法给出足够分类证据的部分。未确认覆盖不等于已证明未覆盖，也不单独证明旧用例缺乏代表性。
