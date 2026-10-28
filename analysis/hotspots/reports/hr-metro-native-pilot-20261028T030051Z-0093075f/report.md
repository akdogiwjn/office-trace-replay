# HR Metro 热点采集

当前 Agent 轨迹版，一轮。新旧对比另见汇总报告。

实际镜像：`sha256:4baef1363ba99a994e17e93fe6a32c904cdb5cb349487adfa2fb13ba42301499`。循环执行及业务验证成功。

正式循环 ROI：41,405 个样本，period 合计 944,704,330,018。

以下均以完整 ROI 的用户态 `cycles:u` period 为分母，未知项未从分母排除。不是整轮 user+sys CPU 时间占比。

## 脚本与进程

| 实际脚本/程序 | ROI 周期占比 |
|---|---:|
| `enhance_workforce_v2.py` | 25.05% |
| `recalc.py` | 23.88% |
| `verify_xlsx_enhanced.py` | 11.27% |
| `inspect_xlsx_formulas.py` | 11.18% |
| `inspect_xlsx_structure.py` | 10.90% |
| `inspect_xlsx_features.py` | 10.25% |
| `soffice.bin` | 3.43% |
| `unknown:thread-pool` | 2.50% |
| `unknown:Parser` | 1.54% |
| `export_xlsx_csv.py` | 0.01% |
| `unknown:Unzipping` | 0.00% |
| `run.py` | 0.00% |
| `unknown:configmgrWriter` | 0.00% |
| `unknown:gpgconf` | 0.00% |
| `write_xlsx_summary.py` | 0.00% |
| `javaldx` | 0.00% |
| `unknown:gpgsm` | 0.00% |
| `unknown:grep` | 0.00% |
| `gpg` | 0.00% |
| `sh` | 0.00% |
| `unknown:soffice.bin` | 0.00% |
| `unknown:python` | 0.00% |
| `unknown:osl_executeProc` | 0.00% |
| `unknown:soffice` | 0.00% |
| `oosplash` | 0.00% |
| `unknown:WakeUpThread` | 0.00% |
| `unknown:sh` | 0.00% |
| `gpgconf` | 0.00% |
| `unknown:timeout` | 0.00% |

## 原生库

| DSO | ROI 周期占比 |
|---|---:|
| `/opt/python-3.12.3/lib/libpython3.12.so.1.0` | 79.87% |
| `/opt/python-3.12.3/lib/python3.12/lib-dynload/pyexpat.cpython-312-aarch64-linux-gnu.so` | 5.07% |
| `/opt/python-3.12.3/lib/python3.12/lib-dynload/_elementtree.cpython-312-aarch64-linux-gnu.so` | 3.64% |
| `/usr/lib64/libz.so.1.2.13` | 2.15% |
| `/usr/lib64/libc.so.6` | 1.75% |
| `/opt/libreoffice25.8-symbols/program/libuno_sal.so.3` | 1.24% |
| `/opt/libreoffice25.8-symbols/program/libscfiltlo.so` | 1.01% |
| `/opt/libreoffice25.8-symbols/program/libuno_cppuhelpergcc3.so.3` | 0.98% |
| `/opt/libreoffice25.8-symbols/program/libsaxlo.so` | 0.81% |
| `/opt/libreoffice25.8-symbols/program/libxml2.so.16` | 0.79% |
| `/opt/libreoffice25.8-symbols/program/libsclo.so` | 0.48% |
| `/usr/lib/ld-linux-aarch64.so.1` | 0.42% |
| `/opt/python-3.12.3/lib/python3.12/lib-dynload/array.cpython-312-aarch64-linux-gnu.so` | 0.39% |
| `/opt/libreoffice25.8-symbols/program/libooxlo.so` | 0.38% |
| `/opt/libreoffice25.8-symbols/program/libsvllo.so` | 0.24% |

## Top-20 物理叶函数

| DSO | 函数 | ROI 周期占比 |
|---|---|---:|
| `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 22.02% |
| `libpython3.12.so.1.0` | `gc_collect_main` | 7.32% |
| `libpython3.12.so.1.0` | `subtype_traverse` | 4.96% |
| `libpython3.12.so.1.0` | `_Py_dict_lookup` | 4.87% |
| `libpython3.12.so.1.0` | `deduce_unreachable` | 4.23% |
| `libpython3.12.so.1.0` | `visit_reachable` | 3.28% |
| `libpython3.12.so.1.0` | `tupledealloc` | 1.76% |
| `libpython3.12.so.1.0` | `_PyObject_GenericGetAttrWithDict` | 1.40% |
| `_elementtree.cpython-312-aarch64-linux-gnu.so` | `checkpath` | 1.25% |
| `pyexpat.cpython-312-aarch64-linux-gnu.so` | `storeAtts` | 1.18% |
| `libpython3.12.so.1.0` | `dict_dealloc` | 1.04% |
| `pyexpat.cpython-312-aarch64-linux-gnu.so` | `PyExpat_XML_Parse` | 1.02% |
| `libpython3.12.so.1.0` | `PyObject_GC_Del` | 1.00% |
| `libpython3.12.so.1.0` | `_PyObject_GC_New` | 0.94% |
| `pyexpat.cpython-312-aarch64-linux-gnu.so` | `getAttributeId` | 0.91% |
| `libpython3.12.so.1.0` | `PyType_GenericAlloc` | 0.90% |
| `libpython3.12.so.1.0` | `dict_traverse` | 0.88% |
| `libpython3.12.so.1.0` | `PyLong_FromString` | 0.88% |
| `libz.so.1.2.13` | `longest_match` | 0.84% |
| `pyexpat.cpython-312-aarch64-linux-gnu.so` | `doContent` | 0.82% |

## 带脚本上下文的 Top-20 函数

| 实际脚本/程序 | DSO | 函数 | ROI 周期占比 |
|---|---|---|---:|
| `enhance_workforce_v2.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 7.66% |
| `recalc.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 5.93% |
| `inspect_xlsx_formulas.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 2.38% |
| `inspect_xlsx_structure.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 2.11% |
| `verify_xlsx_enhanced.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 2.06% |
| `recalc.py` | `libpython3.12.so.1.0` | `_Py_dict_lookup` | 1.91% |
| `recalc.py` | `libpython3.12.so.1.0` | `gc_collect_main` | 1.90% |
| `inspect_xlsx_features.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 1.89% |
| `recalc.py` | `libpython3.12.so.1.0` | `subtype_traverse` | 1.24% |
| `enhance_workforce_v2.py` | `libpython3.12.so.1.0` | `gc_collect_main` | 1.13% |
| `inspect_xlsx_features.py` | `libpython3.12.so.1.0` | `gc_collect_main` | 1.12% |
| `recalc.py` | `libpython3.12.so.1.0` | `deduce_unreachable` | 1.09% |
| `inspect_xlsx_structure.py` | `libpython3.12.so.1.0` | `gc_collect_main` | 1.09% |
| `inspect_xlsx_formulas.py` | `libpython3.12.so.1.0` | `gc_collect_main` | 1.05% |
| `verify_xlsx_enhanced.py` | `libpython3.12.so.1.0` | `gc_collect_main` | 1.02% |
| `recalc.py` | `libpython3.12.so.1.0` | `visit_reachable` | 0.78% |
| `inspect_xlsx_structure.py` | `libpython3.12.so.1.0` | `subtype_traverse` | 0.78% |
| `inspect_xlsx_features.py` | `libpython3.12.so.1.0` | `subtype_traverse` | 0.77% |
| `enhance_workforce_v2.py` | `libpython3.12.so.1.0` | `subtype_traverse` | 0.75% |
| `enhance_workforce_v2.py` | `libz.so.1.2.13` | `longest_match` | 0.75% |

## 质量和边界

- 空栈 0.000%；未知叶 DSO 0.079%；未知叶符号 0.104%。这些类别可能重叠。
- 无法关联脚本的 period：4.033%；首次观察前 10 ms 内的推断归属：0.001%。身份来自 10 ms 名义间隔的 /proc 观察，并非精确 exec 事件。
- 完整栈导出与无栈计数导出按 PID/TID/纳秒时间/period/event 的多重集合逐样本核对；ROI 内外 period 守恒。
- 按 CLOCK_MONOTONIC 的实际 ROI 标记裁剪；循环外预检、归档和哈希不计入主表。采集器及 monitor 不在 perf 的目标子树中。
- 同一镜像内 `--no-inline` 导出物理调用链；未知叶节点不继承调用者符号。
- 用户态采样不包含内核 CPU 和阻塞等待；未进行开销校准或重复稳定性检验，也未采集 py-spy。
- perf 聚合统计 SAMPLE=41476、LOST 记录=117、LOST_SAMPLES 记录=7；record 日志报告 lost chunks=117。这些诊断不构成采集绝对无损的证明。
- 显示 0.00% 仅表示采样权重很小或未获得明显采样，不表示脚本未执行或实际 CPU 为零。
- perf lost/符号化警告原文保存在 profile.json 的 capture_quality 与 raw 日志；其 ROI 归属未知，不换算成周期权重。

原始证据：`analysis/hotspots/raw/hr-metro-native-pilot-20261028T030051Z-0093075f`；停止容器：`d869b25c52da7d689274d3ce2a2fcc128d2ad9fa72a2bdb91f0291cbe390a64f`。
