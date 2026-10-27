# IRS W-4 热点采集

当前 Agent 轨迹版，N=10，一轮。新旧对比另见汇总报告。

实际镜像：`sha256:4baef1363ba99a994e17e93fe6a32c904cdb5cb349487adfa2fb13ba42301499`。循环执行及业务验证成功。

正式循环 ROI：705 个样本，period 合计 29,149,175,824。

以下均以完整 ROI 的用户态 `cycles:u` period 为分母，未知项未从分母排除。不是整轮 user+sys CPU 时间占比。

## 脚本与进程

| 实际脚本/程序 | ROI 周期占比 |
|---|---:|
| `convert_pdf_to_images.py` | 43.25% |
| `fill_fillable_fields.py` | 35.83% |
| `verify_pdf_batch.py` | 12.55% |
| `pdftoppm` | 8.33% |
| `pdfinfo` | 0.02% |
| `unknown:pdftoppm` | 0.01% |
| `run_batch.py` | 0.00% |
| `check_fillable_fields.py` | 0.00% |
| `extract_form_field_info.py` | 0.00% |
| `write_pdf_batch_summary.py` | 0.00% |
| `build_field_values.py` | 0.00% |
| `run.py` | 0.00% |
| `unknown:python3` | 0.00% |
| `unknown:python` | 0.00% |

## 原生库

| DSO | ROI 周期占比 |
|---|---:|
| `/opt/python-3.12.3/lib/libpython3.12.so.1.0` | 44.13% |
| `/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so` | 24.30% |
| `/usr/lib64/libz.so.1.2.13` | 21.14% |
| `/usr/lib64/libfreetype.so.6.20.1` | 3.61% |
| `/usr/lib64/libpoppler.so.133.0.0` | 3.04% |
| `/usr/lib64/libc.so.6` | 2.90% |
| `/usr/lib64/libstdc++.so.6.0.30` | 0.37% |
| `/usr/lib/ld-linux-aarch64.so.1` | 0.29% |
| `[vdso]` | 0.21% |
| `[unknown]` | 0.01% |
| `/opt/python-3.12.3/lib/python3.12/lib-dynload/_posixsubprocess.cpython-312-aarch64-linux-gnu.so` | 0.00% |

## Top-20 物理叶函数

| DSO | 函数 | ROI 周期占比 |
|---|---|---:|
| `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 17.40% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingZipEncode` | 12.08% |
| `libz.so.1.2.13` | `deflate_slow` | 8.50% |
| `libz.so.1.2.13` | `longest_match` | 8.01% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleHorizontal_8bpc` | 5.80% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleVertical_8bpc` | 3.40% |
| `libpython3.12.so.1.0` | `PyObject_GC_Del` | 2.94% |
| `libpython3.12.so.1.0` | `_Py_dict_lookup` | 2.37% |
| `libpython3.12.so.1.0` | `tp_new_wrapper` | 2.03% |
| `libz.so.1.2.13` | `slide_hash` | 1.81% |
| `libpython3.12.so.1.0` | `_PyLong_New` | 1.62% |
| `libpython3.12.so.1.0` | `_Py_bytes_isspace` | 1.52% |
| `libpython3.12.so.1.0` | `deduce_unreachable` | 1.40% |
| `libz.so.1.2.13` | `inflate_fast` | 1.24% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingUnpackRGB` | 1.22% |
| `libpython3.12.so.1.0` | `dict_get` | 1.19% |
| `libpython3.12.so.1.0` | `_PyEvalFrameClearAndPop` | 1.01% |
| `libpython3.12.so.1.0` | `gc_collect_main` | 1.00% |
| `libz.so.1.2.13` | `compress_block` | 0.90% |
| `libfreetype.so.6.20.1` | `gray_render_line` | 0.80% |

## 带脚本上下文的 Top-20 函数

| 实际脚本/程序 | DSO | 函数 | ROI 周期占比 |
|---|---|---|---:|
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 12.24% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingZipEncode` | 12.08% |
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `deflate_slow` | 8.50% |
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `longest_match` | 8.01% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleHorizontal_8bpc` | 5.80% |
| `verify_pdf_batch.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 5.16% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleVertical_8bpc` | 3.40% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `PyObject_GC_Del` | 2.94% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `tp_new_wrapper` | 2.03% |
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `slide_hash` | 1.81% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `_PyLong_New` | 1.62% |
| `verify_pdf_batch.py` | `libpython3.12.so.1.0` | `_Py_dict_lookup` | 1.57% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `_Py_bytes_isspace` | 1.52% |
| `verify_pdf_batch.py` | `libz.so.1.2.13` | `inflate_fast` | 1.24% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `deduce_unreachable` | 1.20% |
| `verify_pdf_batch.py` | `libpython3.12.so.1.0` | `dict_get` | 1.19% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingUnpackRGB` | 1.03% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `_PyEvalFrameClearAndPop` | 1.01% |
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `compress_block` | 0.90% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `gc_collect_main` | 0.80% |

## 质量和边界

- 空栈 0.000%；未知叶 DSO 0.006%；未知叶符号 0.215%。这些类别可能重叠。
- 无法关联脚本的 period：0.007%；首次观察前 10 ms 内的推断归属：0.107%。身份来自 10 ms 名义间隔的 /proc 观察，并非精确 exec 事件。
- 完整栈导出与无栈计数导出按 PID/TID/纳秒时间/period/event 的多重集合逐样本核对；ROI 内外 period 守恒。
- 按 CLOCK_MONOTONIC 的实际 ROI 标记裁剪；循环外预检、归档和哈希不计入主表。采集器及 monitor 不在 perf 的目标子树中。
- 同一镜像内 `--no-inline` 导出物理调用链；未知叶节点不继承调用者符号。
- 用户态采样不包含内核 CPU 和阻塞等待；未进行开销校准或重复稳定性检验，也未采集 py-spy。
- perf 聚合统计 SAMPLE=762、LOST 记录=0、LOST_SAMPLES 记录=0；record 日志报告 lost chunks=0。这些诊断不构成采集绝对无损的证明。
- 显示 0.00% 仅表示采样权重很小或未获得明显采样，不表示脚本未执行或实际 CPU 为零。
- perf lost/符号化警告原文保存在 profile.json 的 capture_quality 与 raw 日志；其 ROI 归属未知，不换算成周期权重。

原始证据：`analysis/hotspots/raw/irs-w4-native-pilot-20261027T122725Z-5e819403`；停止容器：`a7790e403a0986a0066c8424398ff6eb5c8a984ab36bacca94aa518cec66fb5f`。
