# TLC 热点采集

当前 Agent 轨迹版，一轮。新旧对比另见汇总报告。

实际镜像：`sha256:4baef1363ba99a994e17e93fe6a32c904cdb5cb349487adfa2fb13ba42301499`。循环执行及业务验证成功。

正式循环 ROI：35,691 个样本，period 合计 714,766,669,108。

以下均以完整 ROI 的用户态 `cycles:u` period 为分母，未知项未从分母排除。不是整轮 user+sys CPU 时间占比。

## 脚本与进程

| 实际脚本/程序 | ROI 周期占比 |
|---|---:|
| `enhance_workbook.py` | 22.37% |
| `inspect_xlsx_structure.py` | 12.44% |
| `recalc.py` | 11.66% |
| `inspect_xlsx_features.py` | 10.54% |
| `verify_xlsx_enhanced.py` | 10.22% |
| `inspect_xlsx_cached_values.py` | 8.24% |
| `write_xlsx_summary.py` | 8.13% |
| `inspect_xlsx_formulas.py` | 8.02% |
| `soffice.bin` | 4.70% |
| `unknown:thread-pool` | 1.85% |
| `unknown:Parser` | 1.09% |
| `export_xlsx_csv.py` | 0.75% |
| `unknown:bash` | 0.00% |
| `unknown:Unzipping` | 0.00% |
| `bash` | 0.00% |
| `unknown:configmgrWriter` | 0.00% |
| `oosplash` | 0.00% |
| `sh` | 0.00% |
| `unknown:gpgconf` | 0.00% |
| `legacy_capture.py` | 0.00% |
| `gpgconf` | 0.00% |
| `unknown:sh` | 0.00% |
| `unknown:javaldx` | 0.00% |
| `unknown:WakeUpThread` | 0.00% |
| `unknown:gpgsm` | 0.00% |
| `unknown:python` | 0.00% |
| `unknown:soffice.bin` | 0.00% |
| `unknown:soffice` | 0.00% |
| `unknown:python3` | 0.00% |
| `unknown:osl_executeProc` | 0.00% |
| `unknown:timeout` | 0.00% |

## 原生库

| DSO | ROI 周期占比 |
|---|---:|
| `/opt/python-3.12.3/lib/libpython3.12.so.1.0` | 78.95% |
| `/opt/python-3.12.3/lib/python3.12/lib-dynload/pyexpat.cpython-312-aarch64-linux-gnu.so` | 5.58% |
| `/opt/python-3.12.3/lib/python3.12/lib-dynload/_elementtree.cpython-312-aarch64-linux-gnu.so` | 3.76% |
| `/usr/lib64/libc.so.6` | 2.76% |
| `/usr/lib64/libz.so.1.2.13` | 1.62% |
| `/opt/libreoffice25.8-symbols/program/libuno_sal.so.3` | 1.25% |
| `/opt/libreoffice25.8-symbols/program/libsclo.so` | 0.81% |
| `/opt/libreoffice25.8-symbols/program/libuno_cppuhelpergcc3.so.3` | 0.70% |
| `/opt/libreoffice25.8-symbols/program/libsvllo.so` | 0.65% |
| `/opt/libreoffice25.8-symbols/program/libscfiltlo.so` | 0.63% |
| `/opt/libreoffice25.8-symbols/program/libsaxlo.so` | 0.58% |
| `/usr/lib/ld-linux-aarch64.so.1` | 0.56% |
| `/opt/libreoffice25.8-symbols/program/libxml2.so.16` | 0.47% |
| `/opt/python-3.12.3/lib/python3.12/lib-dynload/array.cpython-312-aarch64-linux-gnu.so` | 0.34% |
| `/opt/libreoffice25.8-symbols/program/libooxlo.so` | 0.20% |

## Top-20 物理叶函数

| DSO | 函数 | ROI 周期占比 |
|---|---|---:|
| `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 23.83% |
| `libpython3.12.so.1.0` | `gc_collect_main` | 5.07% |
| `libpython3.12.so.1.0` | `subtype_traverse` | 3.90% |
| `libpython3.12.so.1.0` | `_Py_dict_lookup` | 3.39% |
| `libpython3.12.so.1.0` | `deduce_unreachable` | 3.20% |
| `libpython3.12.so.1.0` | `visit_reachable` | 3.14% |
| `libpython3.12.so.1.0` | `_PyObject_GenericGetAttrWithDict` | 2.04% |
| `libpython3.12.so.1.0` | `dictiter_iternextkey` | 1.86% |
| `libpython3.12.so.1.0` | `tupledealloc` | 1.64% |
| `libpython3.12.so.1.0` | `PyObject_GC_Del` | 1.42% |
| `pyexpat.cpython-312-aarch64-linux-gnu.so` | `storeAtts` | 1.32% |
| `pyexpat.cpython-312-aarch64-linux-gnu.so` | `PyExpat_XML_Parse` | 1.20% |
| `_elementtree.cpython-312-aarch64-linux-gnu.so` | `checkpath` | 1.08% |
| `libpython3.12.so.1.0` | `dict_dealloc` | 1.05% |
| `libpython3.12.so.1.0` | `PyType_GenericAlloc` | 0.91% |
| `libpython3.12.so.1.0` | `_PyObject_GC_New` | 0.89% |
| `libpython3.12.so.1.0` | `PyLong_FromString` | 0.85% |
| `pyexpat.cpython-312-aarch64-linux-gnu.so` | `doContent` | 0.84% |
| `pyexpat.cpython-312-aarch64-linux-gnu.so` | `getAttributeId` | 0.81% |
| `libpython3.12.so.1.0` | `_PyEvalFrameClearAndPop` | 0.69% |

## 带脚本上下文的 Top-20 函数

| 实际脚本/程序 | DSO | 函数 | ROI 周期占比 |
|---|---|---|---:|
| `enhance_workbook.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 6.95% |
| `inspect_xlsx_structure.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 3.40% |
| `recalc.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 3.22% |
| `inspect_xlsx_features.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 2.48% |
| `verify_xlsx_enhanced.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 2.32% |
| `inspect_xlsx_cached_values.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 1.76% |
| `write_xlsx_summary.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 1.76% |
| `inspect_xlsx_formulas.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 1.63% |
| `inspect_xlsx_structure.py` | `libpython3.12.so.1.0` | `dictiter_iternextkey` | 1.24% |
| `enhance_workbook.py` | `libpython3.12.so.1.0` | `gc_collect_main` | 0.86% |
| `enhance_workbook.py` | `libpython3.12.so.1.0` | `subtype_traverse` | 0.74% |
| `inspect_xlsx_structure.py` | `libpython3.12.so.1.0` | `subtype_traverse` | 0.71% |
| `verify_xlsx_enhanced.py` | `libpython3.12.so.1.0` | `gc_collect_main` | 0.68% |
| `inspect_xlsx_features.py` | `libpython3.12.so.1.0` | `gc_collect_main` | 0.68% |
| `inspect_xlsx_structure.py` | `libpython3.12.so.1.0` | `gc_collect_main` | 0.66% |
| `enhance_workbook.py` | `libpython3.12.so.1.0` | `visit_reachable` | 0.65% |
| `enhance_workbook.py` | `libpython3.12.so.1.0` | `deduce_unreachable` | 0.63% |
| `write_xlsx_summary.py` | `libpython3.12.so.1.0` | `gc_collect_main` | 0.62% |
| `inspect_xlsx_cached_values.py` | `libpython3.12.so.1.0` | `gc_collect_main` | 0.61% |
| `inspect_xlsx_formulas.py` | `libpython3.12.so.1.0` | `gc_collect_main` | 0.60% |

## 质量和边界

- 空栈 0.000%；未知叶 DSO 0.081%；未知叶符号 0.122%。这些类别可能重叠。
- 无法关联脚本的 period：2.941%；首次观察前 10 ms 内的推断归属：0.001%。身份来自 10 ms 名义间隔的 /proc 观察，并非精确 exec 事件。
- 完整栈导出与无栈计数导出按 PID/TID/纳秒时间/period/event 的多重集合逐样本核对；ROI 内外 period 守恒。
- 按 CLOCK_MONOTONIC 的实际 ROI 标记裁剪；循环外预检、归档和哈希不计入主表。采集器及 monitor 不在 perf 的目标子树中。
- 同一镜像内 `--no-inline` 导出物理调用链；未知叶节点不继承调用者符号。
- 用户态采样不包含内核 CPU 和阻塞等待；未进行开销校准或重复稳定性检验，也未采集 py-spy。
- perf 聚合统计 SAMPLE=35700、LOST 记录=152、LOST_SAMPLES 记录=6；record 日志报告 lost chunks=152。这些诊断不构成采集绝对无损的证明。
- 显示 0.00% 仅表示采样权重很小或未获得明显采样，不表示脚本未执行或实际 CPU 为零。
- perf lost/符号化警告原文保存在 profile.json 的 capture_quality 与 raw 日志；其 ROI 归属未知，不换算成周期权重。

原始证据：`analysis/hotspots/raw/tlc-native-pilot-20261028T020708Z-46da5c35`；停止容器：`bdf68ae5993627326e75dd7458facc0b773a4aacd1ca3728d24c48e3a9c43817`。
