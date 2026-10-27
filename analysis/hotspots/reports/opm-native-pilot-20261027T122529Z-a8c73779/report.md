# OPM 热点采集

当前 Agent 轨迹版，N=10，一轮。新旧对比另见汇总报告。

实际镜像：`sha256:4baef1363ba99a994e17e93fe6a32c904cdb5cb349487adfa2fb13ba42301499`。循环执行及业务验证成功。

正式循环 ROI：566 个样本，period 合计 21,185,490,122。

以下均以完整 ROI 的用户态 `cycles:u` period 为分母，未知项未从分母排除。不是整轮 user+sys CPU 时间占比。

## 脚本与进程

| 实际脚本/程序 | ROI 周期占比 |
|---|---:|
| `convert_pdf_to_images.py` | 40.84% |
| `fill_fillable_fields.py` | 37.45% |
| `verify_pdf_batch.py` | 12.65% |
| `pdftoppm` | 6.80% |
| `check_fillable_fields.py` | 2.18% |
| `pdfinfo` | 0.03% |
| `unknown:bash` | 0.02% |
| `bash` | 0.01% |
| `unknown:pdftoppm` | 0.01% |
| `extract_form_field_info.py` | 0.00% |
| `run_batch_fill_render.py` | 0.00% |
| `unknown:cat` | 0.00% |
| `legacy_capture.py` | 0.00% |
| `unknown:ls` | 0.00% |
| `python-inline-or-module` | 0.00% |
| `unknown:find` | 0.00% |
| `unknown:python3` | 0.00% |
| `unknown:python` | 0.00% |

## 原生库

| DSO | ROI 周期占比 |
|---|---:|
| `/opt/python-3.12.3/lib/libpython3.12.so.1.0` | 47.64% |
| `/usr/lib64/libz.so.1.2.13` | 26.95% |
| `/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so` | 17.13% |
| `/usr/lib64/libpoppler.so.133.0.0` | 5.31% |
| `/usr/lib64/libfreetype.so.6.20.1` | 1.43% |
| `/usr/lib64/libc.so.6` | 1.12% |
| `/usr/lib/ld-linux-aarch64.so.1` | 0.39% |
| `/usr/bin/bash` | 0.02% |
| `[unknown]` | 0.00% |
| `/opt/python-3.12.3/lib/python3.12/lib-dynload/_posixsubprocess.cpython-312-aarch64-linux-gnu.so` | 0.00% |

## Top-20 物理叶函数

| DSO | 函数 | ROI 周期占比 |
|---|---|---:|
| `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 14.37% |
| `libz.so.1.2.13` | `longest_match` | 11.44% |
| `libz.so.1.2.13` | `deflate_slow` | 9.24% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingZipEncode` | 8.29% |
| `libpython3.12.so.1.0` | `deduce_unreachable` | 7.80% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleHorizontal_8bpc` | 5.27% |
| `libpython3.12.so.1.0` | `visit_reachable` | 4.68% |
| `libpoppler.so.133.0.0` | `Splash::compositeBackground(unsigned char const*)` | 2.80% |
| `libpoppler.so.133.0.0` | `Lexer::getChar(bool)` | 2.52% |
| `libz.so.1.2.13` | `slide_hash` | 2.43% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleVertical_8bpc` | 1.95% |
| `libz.so.1.2.13` | `inflate_fast` | 1.93% |
| `libpython3.12.so.1.0` | `tupledealloc` | 1.37% |
| `libpython3.12.so.1.0` | `_Py_Dealloc` | 1.20% |
| `libpython3.12.so.1.0` | `long_dealloc` | 1.20% |
| `libz.so.1.2.13` | `compress_block` | 1.10% |
| `libpython3.12.so.1.0` | `gc_collect_main` | 1.10% |
| `libpython3.12.so.1.0` | `PyObject_Malloc` | 1.06% |
| `libfreetype.so.6.20.1` | `FT_Vector_Transform` | 0.91% |
| `libpython3.12.so.1.0` | `_in_weak_set` | 0.87% |

## 带脚本上下文的 Top-20 函数

| 实际脚本/程序 | DSO | 函数 | ROI 周期占比 |
|---|---|---|---:|
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `longest_match` | 11.44% |
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `deflate_slow` | 9.24% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingZipEncode` | 8.29% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 7.46% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `deduce_unreachable` | 7.25% |
| `verify_pdf_batch.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 6.38% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleHorizontal_8bpc` | 5.27% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `visit_reachable` | 4.68% |
| `pdftoppm` | `libpoppler.so.133.0.0` | `Splash::compositeBackground(unsigned char const*)` | 2.80% |
| `pdftoppm` | `libpoppler.so.133.0.0` | `Lexer::getChar(bool)` | 2.52% |
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `slide_hash` | 2.43% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleVertical_8bpc` | 1.95% |
| `verify_pdf_batch.py` | `libz.so.1.2.13` | `inflate_fast` | 1.93% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `tupledealloc` | 1.37% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `_Py_Dealloc` | 1.20% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `long_dealloc` | 1.20% |
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `compress_block` | 1.10% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `gc_collect_main` | 1.10% |
| `pdftoppm` | `libfreetype.so.6.20.1` | `FT_Vector_Transform` | 0.91% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `_in_weak_set` | 0.87% |

## 质量和边界

- 空栈 0.000%；未知叶 DSO 0.005%；未知叶符号 0.005%。这些类别可能重叠。
- 无法关联脚本的 period：0.029%；首次观察前 10 ms 内的推断归属：0.097%。身份来自 10 ms 名义间隔的 /proc 观察，并非精确 exec 事件。
- 完整栈导出与无栈计数导出按 PID/TID/纳秒时间/period/event 的多重集合逐样本核对；ROI 内外 period 守恒。
- 按 CLOCK_MONOTONIC 的实际 ROI 标记裁剪；循环外预检、归档和哈希不计入主表。采集器及 monitor 不在 perf 的目标子树中。
- 同一镜像内 `--no-inline` 导出物理调用链；未知叶节点不继承调用者符号。
- 用户态采样不包含内核 CPU 和阻塞等待；未进行开销校准或重复稳定性检验，也未采集 py-spy。
- perf 聚合统计 SAMPLE=575、LOST 记录=0、LOST_SAMPLES 记录=0；record 日志报告 lost chunks=0。这些诊断不构成采集绝对无损的证明。
- 显示 0.00% 仅表示采样权重很小或未获得明显采样，不表示脚本未执行或实际 CPU 为零。
- perf lost/符号化警告原文保存在 profile.json 的 capture_quality 与 raw 日志；其 ROI 归属未知，不换算成周期权重。

原始证据：`analysis/hotspots/raw/opm-native-pilot-20261027T122529Z-a8c73779`；停止容器：`c74b4e054d93c8b0b3ae2e610fd89182711bd08c23a278c066c376aadc7e18c8`。
