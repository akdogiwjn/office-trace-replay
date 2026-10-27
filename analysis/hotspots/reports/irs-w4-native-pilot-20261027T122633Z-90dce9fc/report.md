# IRS W-4 热点采集

当前 Agent 轨迹版，N=10，一轮。新旧对比另见汇总报告。

实际镜像：`sha256:4baef1363ba99a994e17e93fe6a32c904cdb5cb349487adfa2fb13ba42301499`。循环执行及业务验证成功。

正式循环 ROI：720 个样本，period 合计 28,398,771,732。

以下均以完整 ROI 的用户态 `cycles:u` period 为分母，未知项未从分母排除。不是整轮 user+sys CPU 时间占比。

## 脚本与进程

| 实际脚本/程序 | ROI 周期占比 |
|---|---:|
| `convert_pdf_to_images.py` | 47.43% |
| `fill_fillable_fields.py` | 31.16% |
| `verify_pdf_batch.py` | 12.23% |
| `pdftoppm` | 8.92% |
| `run.py` | 0.21% |
| `pdfinfo` | 0.02% |
| `unknown:pdftoppm` | 0.01% |
| `check_fillable_fields.py` | 0.00% |
| `run_batch.py` | 0.00% |
| `write_pdf_batch_summary.py` | 0.00% |
| `build_field_values.py` | 0.00% |
| `extract_form_field_info.py` | 0.00% |
| `unknown:python3` | 0.00% |
| `unknown:python` | 0.00% |

## 原生库

| DSO | ROI 周期占比 |
|---|---:|
| `/opt/python-3.12.3/lib/libpython3.12.so.1.0` | 41.16% |
| `/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so` | 26.53% |
| `/usr/lib64/libz.so.1.2.13` | 21.33% |
| `/usr/lib64/libpoppler.so.133.0.0` | 5.03% |
| `/usr/lib64/libc.so.6` | 4.41% |
| `/usr/lib64/libfreetype.so.6.20.1` | 1.43% |
| `/usr/lib/ld-linux-aarch64.so.1` | 0.10% |
| `[unknown]` | 0.00% |
| `/opt/python-3.12.3/lib/python3.12/lib-dynload/_posixsubprocess.cpython-312-aarch64-linux-gnu.so` | 0.00% |
| `/usr/lib64/libstdc++.so.6.0.30` | 0.00% |

## Top-20 物理叶函数

| DSO | 函数 | ROI 周期占比 |
|---|---|---:|
| `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 15.18% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleHorizontal_8bpc` | 11.90% |
| `libz.so.1.2.13` | `longest_match` | 10.98% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingZipEncode` | 9.10% |
| `libz.so.1.2.13` | `deflate_slow` | 5.18% |
| `libpython3.12.so.1.0` | `deduce_unreachable` | 4.48% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleVertical_8bpc` | 3.45% |
| `libpython3.12.so.1.0` | `insertdict` | 3.41% |
| `libc.so.6` | `__memcpy_generic` | 2.71% |
| `libz.so.1.2.13` | `slide_hash` | 2.51% |
| `libpython3.12.so.1.0` | `unicode_dealloc` | 1.87% |
| `libpython3.12.so.1.0` | `_Py_dict_lookup` | 1.83% |
| `libpoppler.so.133.0.0` | `Lexer::getChar(bool)` | 1.33% |
| `libpoppler.so.133.0.0` | `Splash::fillGlyph2(int, int, SplashGlyphBitmap*, bool)` | 1.24% |
| `libpython3.12.so.1.0` | `gc_collect_main` | 1.02% |
| `libpython3.12.so.1.0` | `PyObject_GC_Del` | 1.02% |
| `libz.so.1.2.13` | `inflate_fast` | 0.88% |
| `libpython3.12.so.1.0` | `tuplecontains` | 0.87% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingUnpackRGB` | 0.86% |
| `libpython3.12.so.1.0` | `visit_reachable` | 0.82% |

## 带脚本上下文的 Top-20 函数

| 实际脚本/程序 | DSO | 函数 | ROI 周期占比 |
|---|---|---|---:|
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleHorizontal_8bpc` | 11.90% |
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `longest_match` | 10.98% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingZipEncode` | 9.10% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 8.56% |
| `verify_pdf_batch.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 6.62% |
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `deflate_slow` | 5.18% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `deduce_unreachable` | 4.06% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleVertical_8bpc` | 3.45% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `insertdict` | 3.21% |
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `slide_hash` | 2.51% |
| `pdftoppm` | `libc.so.6` | `__memcpy_generic` | 2.03% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `unicode_dealloc` | 1.87% |
| `verify_pdf_batch.py` | `libpython3.12.so.1.0` | `_Py_dict_lookup` | 1.42% |
| `pdftoppm` | `libpoppler.so.133.0.0` | `Lexer::getChar(bool)` | 1.33% |
| `pdftoppm` | `libpoppler.so.133.0.0` | `Splash::fillGlyph2(int, int, SplashGlyphBitmap*, bool)` | 1.24% |
| `verify_pdf_batch.py` | `libz.so.1.2.13` | `inflate_fast` | 0.88% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `tuplecontains` | 0.87% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingUnpackRGB` | 0.86% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `gc_collect_main` | 0.82% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `PyObject_GC_Del` | 0.82% |

## 质量和边界

- 空栈 0.000%；未知叶 DSO 0.004%；未知叶符号 0.004%。这些类别可能重叠。
- 无法关联脚本的 period：0.005%；首次观察前 10 ms 内的推断归属：0.099%。身份来自 10 ms 名义间隔的 /proc 观察，并非精确 exec 事件。
- 完整栈导出与无栈计数导出按 PID/TID/纳秒时间/period/event 的多重集合逐样本核对；ROI 内外 period 守恒。
- 按 CLOCK_MONOTONIC 的实际 ROI 标记裁剪；循环外预检、归档和哈希不计入主表。采集器及 monitor 不在 perf 的目标子树中。
- 同一镜像内 `--no-inline` 导出物理调用链；未知叶节点不继承调用者符号。
- 用户态采样不包含内核 CPU 和阻塞等待；未进行开销校准或重复稳定性检验，也未采集 py-spy。
- perf 聚合统计 SAMPLE=786、LOST 记录=0、LOST_SAMPLES 记录=0；record 日志报告 lost chunks=0。这些诊断不构成采集绝对无损的证明。
- 显示 0.00% 仅表示采样权重很小或未获得明显采样，不表示脚本未执行或实际 CPU 为零。
- perf lost/符号化警告原文保存在 profile.json 的 capture_quality 与 raw 日志；其 ROI 归属未知，不换算成周期权重。

原始证据：`analysis/hotspots/raw/irs-w4-native-pilot-20261027T122633Z-90dce9fc`；停止容器：`b5d7435c1d12bb75435a9d0df2d7e8e1d59ee3e43142485e66a6805bf9a151ab`。
