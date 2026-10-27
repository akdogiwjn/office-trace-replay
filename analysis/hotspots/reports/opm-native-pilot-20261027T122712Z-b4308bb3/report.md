# OPM 热点采集

当前 Agent 轨迹版，N=10，一轮。新旧对比另见汇总报告。

实际镜像：`sha256:4baef1363ba99a994e17e93fe6a32c904cdb5cb349487adfa2fb13ba42301499`。循环执行及业务验证成功。

正式循环 ROI：538 个样本，period 合计 21,645,992,001。

以下均以完整 ROI 的用户态 `cycles:u` period 为分母，未知项未从分母排除。不是整轮 user+sys CPU 时间占比。

## 脚本与进程

| 实际脚本/程序 | ROI 周期占比 |
|---|---:|
| `convert_pdf_to_images.py` | 44.20% |
| `fill_fillable_fields.py` | 36.31% |
| `verify_pdf_batch.py` | 10.65% |
| `pdftoppm` | 6.72% |
| `check_fillable_fields.py` | 2.05% |
| `pdfinfo` | 0.03% |
| `unknown:bash` | 0.01% |
| `bash` | 0.01% |
| `unknown:pdftoppm` | 0.00% |
| `run_batch_fill_render.py` | 0.00% |
| `unknown:ls` | 0.00% |
| `python-inline-or-module` | 0.00% |
| `unknown:sort` | 0.00% |
| `find` | 0.00% |
| `legacy_capture.py` | 0.00% |
| `unknown:python3` | 0.00% |
| `unknown:python` | 0.00% |

## 原生库

| DSO | ROI 周期占比 |
|---|---:|
| `/opt/python-3.12.3/lib/libpython3.12.so.1.0` | 48.74% |
| `/usr/lib64/libz.so.1.2.13` | 30.10% |
| `/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so` | 10.73% |
| `/usr/lib64/libpoppler.so.133.0.0` | 6.01% |
| `/usr/lib64/libc.so.6` | 3.11% |
| `[unknown]` | 1.18% |
| `/usr/lib/ld-linux-aarch64.so.1` | 0.11% |
| `/usr/bin/bash` | 0.01% |
| `/usr/bin/ls` | 0.00% |
| `/opt/python-3.12.3/lib/python3.12/lib-dynload/_posixsubprocess.cpython-312-aarch64-linux-gnu.so` | 0.00% |
| `/usr/lib64/libfreetype.so.6.20.1` | 0.00% |
| `/opt/python-3.12.3/lib/python3.12/lib-dynload/select.cpython-312-aarch64-linux-gnu.so` | 0.00% |

## Top-20 物理叶函数

| DSO | 函数 | ROI 周期占比 |
|---|---|---:|
| `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 20.60% |
| `libz.so.1.2.13` | `longest_match` | 13.49% |
| `libz.so.1.2.13` | `deflate_slow` | 6.05% |
| `libz.so.1.2.13` | `compress_block` | 5.58% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleHorizontal_8bpc` | 5.15% |
| `libpython3.12.so.1.0` | `PyErr_GivenExceptionMatches` | 4.19% |
| `libpython3.12.so.1.0` | `dict_traverse` | 4.19% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingZipEncode` | 3.92% |
| `libz.so.1.2.13` | `slide_hash` | 3.11% |
| `libpoppler.so.133.0.0` | `Splash::compositeBackground(unsigned char const*)` | 2.15% |
| `libpython3.12.so.1.0` | `_PyObject_MakeTpCall` | 2.05% |
| `libpython3.12.so.1.0` | `gc_collect_main` | 1.65% |
| `libpoppler.so.133.0.0` | `Lexer::getChar(bool)` | 1.65% |
| `libpython3.12.so.1.0` | `_Py_type_getattro_impl` | 1.62% |
| `libpython3.12.so.1.0` | `deduce_unreachable` | 1.34% |
| `[unknown]` | `[unknown]` | 1.18% |
| `libpoppler.so.133.0.0` | `NameToCharCode::lookup(char const*) const` | 1.18% |
| `libc.so.6` | `malloc` | 1.08% |
| `libz.so.1.2.13` | `inflate_fast` | 1.06% |
| `libpython3.12.so.1.0` | `visit_reachable` | 0.89% |

## 带脚本上下文的 Top-20 函数

| 实际脚本/程序 | DSO | 函数 | ROI 周期占比 |
|---|---|---|---:|
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 14.71% |
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `longest_match` | 13.49% |
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `deflate_slow` | 6.05% |
| `verify_pdf_batch.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 5.89% |
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `compress_block` | 5.58% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleHorizontal_8bpc` | 5.15% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `PyErr_GivenExceptionMatches` | 4.19% |
| `convert_pdf_to_images.py` | `libpython3.12.so.1.0` | `dict_traverse` | 4.19% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingZipEncode` | 3.92% |
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `slide_hash` | 3.11% |
| `pdftoppm` | `libpoppler.so.133.0.0` | `Splash::compositeBackground(unsigned char const*)` | 2.15% |
| `pdftoppm` | `libpoppler.so.133.0.0` | `Lexer::getChar(bool)` | 1.65% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `_Py_type_getattro_impl` | 1.62% |
| `check_fillable_fields.py` | `libpython3.12.so.1.0` | `_PyObject_MakeTpCall` | 1.51% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `gc_collect_main` | 1.38% |
| `pdftoppm` | `libpoppler.so.133.0.0` | `NameToCharCode::lookup(char const*) const` | 1.18% |
| `fill_fillable_fields.py` | `[unknown]` | `[unknown]` | 1.18% |
| `fill_fillable_fields.py` | `libc.so.6` | `malloc` | 1.08% |
| `verify_pdf_batch.py` | `libz.so.1.2.13` | `inflate_fast` | 1.06% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `visit_reachable` | 0.89% |

## 质量和边界

- 空栈 0.000%；未知叶 DSO 1.183%；未知叶符号 1.189%。这些类别可能重叠。
- 无法关联脚本的 period：0.020%；首次观察前 10 ms 内的推断归属：0.112%。身份来自 10 ms 名义间隔的 /proc 观察，并非精确 exec 事件。
- 完整栈导出与无栈计数导出按 PID/TID/纳秒时间/period/event 的多重集合逐样本核对；ROI 内外 period 守恒。
- 按 CLOCK_MONOTONIC 的实际 ROI 标记裁剪；循环外预检、归档和哈希不计入主表。采集器及 monitor 不在 perf 的目标子树中。
- 同一镜像内 `--no-inline` 导出物理调用链；未知叶节点不继承调用者符号。
- 用户态采样不包含内核 CPU 和阻塞等待；未进行开销校准或重复稳定性检验，也未采集 py-spy。
- perf 聚合统计 SAMPLE=548、LOST 记录=0、LOST_SAMPLES 记录=0；record 日志报告 lost chunks=0。这些诊断不构成采集绝对无损的证明。
- 显示 0.00% 仅表示采样权重很小或未获得明显采样，不表示脚本未执行或实际 CPU 为零。
- perf lost/符号化警告原文保存在 profile.json 的 capture_quality 与 raw 日志；其 ROI 归属未知，不换算成周期权重。

原始证据：`analysis/hotspots/raw/opm-native-pilot-20261027T122712Z-b4308bb3`；停止容器：`56d2d18c599482c0bd2a6c1823fef07d2bfd3bb4131421822cc9cb936c525bcf`。
