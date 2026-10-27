# OPM 热点采集

当前 Agent 轨迹版，N=10，一轮。新旧对比另见汇总报告。

实际镜像：`sha256:4baef1363ba99a994e17e93fe6a32c904cdb5cb349487adfa2fb13ba42301499`。循环执行及业务验证成功。

正式循环 ROI：563 个样本，period 合计 18,887,909,306。

以下均以完整 ROI 的用户态 `cycles:u` period 为分母，未知项未从分母排除。不是整轮 user+sys CPU 时间占比。

## 脚本与进程

| 实际脚本/程序 | ROI 周期占比 |
|---|---:|
| `fill_fillable_fields.py` | 39.59% |
| `convert_pdf_to_images.py` | 34.85% |
| `verify_pdf_batch.py` | 11.86% |
| `pdftoppm` | 11.22% |
| `check_fillable_fields.py` | 1.46% |
| `extract_form_field_info.py` | 0.94% |
| `pdfinfo` | 0.03% |
| `unknown:bash` | 0.02% |
| `bash` | 0.01% |
| `unknown:pdftoppm` | 0.01% |
| `run_batch_fill_render.py` | 0.00% |
| `unknown:find` | 0.00% |
| `python-inline-or-module` | 0.00% |
| `unknown:sort` | 0.00% |
| `unknown:python3` | 0.00% |
| `unknown:python` | 0.00% |
| `legacy_capture.py` | 0.00% |

## 原生库

| DSO | ROI 周期占比 |
|---|---:|
| `/opt/python-3.12.3/lib/libpython3.12.so.1.0` | 50.43% |
| `/usr/lib64/libz.so.1.2.13` | 21.86% |
| `/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so` | 15.40% |
| `/usr/lib64/libpoppler.so.133.0.0` | 7.95% |
| `/usr/lib64/libfreetype.so.6.20.1` | 2.33% |
| `/usr/lib64/libc.so.6` | 1.87% |
| `/usr/lib/ld-linux-aarch64.so.1` | 0.13% |
| `[unknown]` | 0.02% |
| `/usr/bin/bash` | 0.01% |
| `/opt/python-3.12.3/lib/python3.12/lib-dynload/_posixsubprocess.cpython-312-aarch64-linux-gnu.so` | 0.00% |
| `/opt/python-3.12.3/lib/python3.12/lib-dynload/select.cpython-312-aarch64-linux-gnu.so` | 0.00% |

## Top-20 物理叶函数

| DSO | 函数 | ROI 周期占比 |
|---|---|---:|
| `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 14.59% |
| `libz.so.1.2.13` | `longest_match` | 10.55% |
| `libpython3.12.so.1.0` | `gc_collect_main` | 9.50% |
| `libz.so.1.2.13` | `deflate_slow` | 7.41% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleHorizontal_8bpc` | 6.91% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleVertical_8bpc` | 4.24% |
| `libpoppler.so.133.0.0` | `Splash::pipeRunAARGB8(SplashPipe*)` | 4.11% |
| `libpython3.12.so.1.0` | `_PyObject_GetMethod` | 2.99% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingZipEncode` | 2.42% |
| `libpython3.12.so.1.0` | `_sre_SRE_Pattern_match` | 2.15% |
| `libpython3.12.so.1.0` | `PyUnicode_FromFormatV` | 2.08% |
| `libpoppler.so.133.0.0` | `Splash::drawAALine(SplashPipe*, int, int, int, bool, unsigned char)` | 1.92% |
| `libz.so.1.2.13` | `inflate_fast` | 1.86% |
| `libpython3.12.so.1.0` | `_PyObject_MakeTpCall` | 1.61% |
| `libfreetype.so.6.20.1` | `gray_convert_glyph` | 1.11% |
| `libpython3.12.so.1.0` | `visit_reachable` | 1.07% |
| `libpython3.12.so.1.0` | `subtype_traverse` | 1.05% |
| `libz.so.1.2.13` | `compress_block` | 1.05% |
| `libpython3.12.so.1.0` | `r_object` | 0.96% |
| `libpython3.12.so.1.0` | `deduce_unreachable` | 0.92% |

## 带脚本上下文的 Top-20 函数

| 实际脚本/程序 | DSO | 函数 | ROI 周期占比 |
|---|---|---|---:|
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `longest_match` | 10.55% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `gc_collect_main` | 9.11% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 8.17% |
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `deflate_slow` | 7.41% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleHorizontal_8bpc` | 6.91% |
| `verify_pdf_batch.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 5.55% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleVertical_8bpc` | 4.24% |
| `pdftoppm` | `libpoppler.so.133.0.0` | `Splash::pipeRunAARGB8(SplashPipe*)` | 4.11% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `_PyObject_GetMethod` | 2.99% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingZipEncode` | 2.42% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `_sre_SRE_Pattern_match` | 2.15% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `PyUnicode_FromFormatV` | 2.08% |
| `pdftoppm` | `libpoppler.so.133.0.0` | `Splash::drawAALine(SplashPipe*, int, int, int, bool, unsigned char)` | 1.92% |
| `verify_pdf_batch.py` | `libz.so.1.2.13` | `inflate_fast` | 1.86% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `_PyObject_MakeTpCall` | 1.30% |
| `pdftoppm` | `libfreetype.so.6.20.1` | `gray_convert_glyph` | 1.11% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `visit_reachable` | 1.07% |
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `compress_block` | 1.05% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `r_object` | 0.96% |
| `verify_pdf_batch.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `get_pixel_8` | 0.91% |

## 质量和边界

- 空栈 0.000%；未知叶 DSO 0.015%；未知叶符号 0.022%。这些类别可能重叠。
- 无法关联脚本的 period：0.023%；首次观察前 10 ms 内的推断归属：0.139%。身份来自 10 ms 名义间隔的 /proc 观察，并非精确 exec 事件。
- 完整栈导出与无栈计数导出按 PID/TID/纳秒时间/period/event 的多重集合逐样本核对；ROI 内外 period 守恒。
- 按 CLOCK_MONOTONIC 的实际 ROI 标记裁剪；循环外预检、归档和哈希不计入主表。采集器及 monitor 不在 perf 的目标子树中。
- 同一镜像内 `--no-inline` 导出物理调用链；未知叶节点不继承调用者符号。
- 用户态采样不包含内核 CPU 和阻塞等待；未进行开销校准或重复稳定性检验，也未采集 py-spy。
- perf 聚合统计 SAMPLE=572、LOST 记录=0、LOST_SAMPLES 记录=0；record 日志报告 lost chunks=0。这些诊断不构成采集绝对无损的证明。
- 显示 0.00% 仅表示采样权重很小或未获得明显采样，不表示脚本未执行或实际 CPU 为零。
- perf lost/符号化警告原文保存在 profile.json 的 capture_quality 与 raw 日志；其 ROI 归属未知，不换算成周期权重。

原始证据：`analysis/hotspots/raw/opm-native-pilot-20261027T122437Z-8e39f359`；停止容器：`dfc1b2373f40cff0ce31986960f19b862b689f1bb73f79e9d6cd15ce97999ef2`。
