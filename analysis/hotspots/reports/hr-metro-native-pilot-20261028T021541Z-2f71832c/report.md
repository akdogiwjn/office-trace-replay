# HR Metro 热点采集

当前 Agent 轨迹版，一轮。新旧对比另见汇总报告。

实际镜像：`sha256:4baef1363ba99a994e17e93fe6a32c904cdb5cb349487adfa2fb13ba42301499`。循环执行及业务验证成功。

正式循环 ROI：41,341 个样本，period 合计 931,799,344,438。

以下均以完整 ROI 的用户态 `cycles:u` period 为分母，未知项未从分母排除。不是整轮 user+sys CPU 时间占比。

## 脚本与进程

| 实际脚本/程序 | ROI 周期占比 |
|---|---:|
| `enhance_workforce_v2.py` | 25.27% |
| `recalc.py` | 24.08% |
| `verify_xlsx_enhanced.py` | 11.05% |
| `inspect_xlsx_formulas.py` | 10.99% |
| `inspect_xlsx_structure.py` | 10.57% |
| `inspect_xlsx_features.py` | 10.42% |
| `soffice.bin` | 3.49% |
| `unknown:thread-pool` | 2.54% |
| `unknown:Parser` | 1.56% |
| `export_xlsx_csv.py` | 0.01% |
| `run.py` | 0.01% |
| `unknown:Unzipping` | 0.00% |
| `unknown:configmgrWriter` | 0.00% |
| `unknown:gpgconf` | 0.00% |
| `sh` | 0.00% |
| `write_xlsx_summary.py` | 0.00% |
| `javaldx` | 0.00% |
| `unknown:WakeUpThread` | 0.00% |
| `unknown:grep` | 0.00% |
| `unknown:soffice` | 0.00% |
| `unknown:soffice.bin` | 0.00% |
| `oosplash` | 0.00% |
| `unknown:osl_executeProc` | 0.00% |
| `unknown:python` | 0.00% |
| `unknown:PipeIPC` | 0.00% |
| `unknown:timeout` | 0.00% |

## 原生库

| DSO | ROI 周期占比 |
|---|---:|
| `/opt/python-3.12.3/lib/libpython3.12.so.1.0` | 79.49% |
| `/opt/python-3.12.3/lib/python3.12/lib-dynload/pyexpat.cpython-312-aarch64-linux-gnu.so` | 5.21% |
| `/opt/python-3.12.3/lib/python3.12/lib-dynload/_elementtree.cpython-312-aarch64-linux-gnu.so` | 3.39% |
| `/usr/lib64/libc.so.6` | 2.16% |
| `/usr/lib64/libz.so.1.2.13` | 2.06% |
| `/opt/libreoffice25.8-symbols/program/libuno_sal.so.3` | 1.24% |
| `/opt/libreoffice25.8-symbols/program/libscfiltlo.so` | 1.16% |
| `/opt/libreoffice25.8-symbols/program/libuno_cppuhelpergcc3.so.3` | 0.97% |
| `/opt/libreoffice25.8-symbols/program/libsaxlo.so` | 0.83% |
| `/opt/libreoffice25.8-symbols/program/libxml2.so.16` | 0.60% |
| `/opt/libreoffice25.8-symbols/program/libsclo.so` | 0.48% |
| `/opt/python-3.12.3/lib/python3.12/lib-dynload/array.cpython-312-aarch64-linux-gnu.so` | 0.46% |
| `/usr/lib/ld-linux-aarch64.so.1` | 0.38% |
| `/opt/libreoffice25.8-symbols/program/libooxlo.so` | 0.37% |
| `/opt/libreoffice25.8-symbols/program/libsvllo.so` | 0.29% |

## Top-20 物理叶函数

| DSO | 函数 | ROI 周期占比 |
|---|---|---:|
| `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 22.01% |
| `libpython3.12.so.1.0` | `gc_collect_main` | 7.29% |
| `libpython3.12.so.1.0` | `subtype_traverse` | 4.94% |
| `libpython3.12.so.1.0` | `_Py_dict_lookup` | 4.77% |
| `libpython3.12.so.1.0` | `deduce_unreachable` | 4.27% |
| `libpython3.12.so.1.0` | `visit_reachable` | 3.37% |
| `libpython3.12.so.1.0` | `tupledealloc` | 1.86% |
| `libpython3.12.so.1.0` | `_PyObject_GenericGetAttrWithDict` | 1.20% |
| `pyexpat.cpython-312-aarch64-linux-gnu.so` | `storeAtts` | 1.13% |
| `_elementtree.cpython-312-aarch64-linux-gnu.so` | `checkpath` | 1.12% |
| `libpython3.12.so.1.0` | `PyObject_GC_Del` | 1.10% |
| `pyexpat.cpython-312-aarch64-linux-gnu.so` | `doContent` | 0.99% |
| `pyexpat.cpython-312-aarch64-linux-gnu.so` | `PyExpat_XML_Parse` | 0.98% |
| `libpython3.12.so.1.0` | `dict_dealloc` | 0.96% |
| `libpython3.12.so.1.0` | `_PyObject_GC_New` | 0.96% |
| `libpython3.12.so.1.0` | `PyType_GenericAlloc` | 0.93% |
| `libpython3.12.so.1.0` | `PyLong_FromString` | 0.93% |
| `libpython3.12.so.1.0` | `dict_traverse` | 0.92% |
| `pyexpat.cpython-312-aarch64-linux-gnu.so` | `getAttributeId` | 0.90% |
| `libpython3.12.so.1.0` | `_PyObject_MakeTpCall` | 0.89% |

## 带脚本上下文的 Top-20 函数

| 实际脚本/程序 | DSO | 函数 | ROI 周期占比 |
|---|---|---|---:|
| `enhance_workforce_v2.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 7.61% |
| `recalc.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 5.93% |
| `verify_xlsx_enhanced.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 2.24% |
| `inspect_xlsx_structure.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 2.12% |
| `inspect_xlsx_formulas.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 2.07% |
| `inspect_xlsx_features.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 2.04% |
| `recalc.py` | `libpython3.12.so.1.0` | `_Py_dict_lookup` | 1.96% |
| `recalc.py` | `libpython3.12.so.1.0` | `gc_collect_main` | 1.85% |
| `recalc.py` | `libpython3.12.so.1.0` | `subtype_traverse` | 1.38% |
| `enhance_workforce_v2.py` | `libpython3.12.so.1.0` | `gc_collect_main` | 1.18% |
| `inspect_xlsx_features.py` | `libpython3.12.so.1.0` | `gc_collect_main` | 1.12% |
| `recalc.py` | `libpython3.12.so.1.0` | `deduce_unreachable` | 1.11% |
| `inspect_xlsx_structure.py` | `libpython3.12.so.1.0` | `gc_collect_main` | 1.08% |
| `inspect_xlsx_formulas.py` | `libpython3.12.so.1.0` | `gc_collect_main` | 1.05% |
| `verify_xlsx_enhanced.py` | `libpython3.12.so.1.0` | `gc_collect_main` | 1.02% |
| `recalc.py` | `libpython3.12.so.1.0` | `visit_reachable` | 0.82% |
| `inspect_xlsx_features.py` | `libpython3.12.so.1.0` | `subtype_traverse` | 0.78% |
| `inspect_xlsx_structure.py` | `libpython3.12.so.1.0` | `subtype_traverse` | 0.75% |
| `enhance_workforce_v2.py` | `libz.so.1.2.13` | `longest_match` | 0.72% |
| `verify_xlsx_enhanced.py` | `libpython3.12.so.1.0` | `subtype_traverse` | 0.72% |

## 质量和边界

- 空栈 0.000%；未知叶 DSO 0.074%；未知叶符号 0.094%。这些类别可能重叠。
- 无法关联脚本的 period：4.107%；首次观察前 10 ms 内的推断归属：0.001%。身份来自 10 ms 名义间隔的 /proc 观察，并非精确 exec 事件。
- 完整栈导出与无栈计数导出按 PID/TID/纳秒时间/period/event 的多重集合逐样本核对；ROI 内外 period 守恒。
- 按 CLOCK_MONOTONIC 的实际 ROI 标记裁剪；循环外预检、归档和哈希不计入主表。采集器及 monitor 不在 perf 的目标子树中。
- 同一镜像内 `--no-inline` 导出物理调用链；未知叶节点不继承调用者符号。
- 用户态采样不包含内核 CPU 和阻塞等待；未进行开销校准或重复稳定性检验，也未采集 py-spy。
- perf 聚合统计 SAMPLE=41405、LOST 记录=133、LOST_SAMPLES 记录=7；record 日志报告 lost chunks=133。这些诊断不构成采集绝对无损的证明。
- 显示 0.00% 仅表示采样权重很小或未获得明显采样，不表示脚本未执行或实际 CPU 为零。
- perf lost/符号化警告原文保存在 profile.json 的 capture_quality 与 raw 日志；其 ROI 归属未知，不换算成周期权重。

原始证据：`analysis/hotspots/raw/hr-metro-native-pilot-20261028T021541Z-2f71832c`；停止容器：`45ef259edbeeaa813fe7cf2e227153c1d297cd5aadd991b364439367ca311b32`。
