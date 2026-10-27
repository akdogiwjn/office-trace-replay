# IRS W-4 热点采集试点

当前 Agent 轨迹版，N=10，一轮。不是新旧数据集的正式对比。

实际镜像：`sha256:4baef1363ba99a994e17e93fe6a32c904cdb5cb349487adfa2fb13ba42301499`。循环执行及业务验证成功。

正式循环 ROI：711 个样本，period 合计 27,013,993,031。

以下均以完整 ROI 的用户态 `cycles:u` period 为分母，未知项未从分母排除。不是整轮 user+sys CPU 时间占比。

## 脚本与进程

| 实际脚本/程序 | ROI 周期占比 |
|---|---:|
| `convert_pdf_to_images.py` | 44.32% |
| `fill_fillable_fields.py` | 35.81% |
| `verify_pdf_batch.py` | 13.36% |
| `pdftoppm` | 6.25% |
| `run.py` | 0.22% |
| `pdfinfo` | 0.02% |
| `run_batch.py` | 0.01% |
| `check_fillable_fields.py` | 0.00% |
| `unknown:pdftoppm` | 0.00% |
| `build_field_values.py` | 0.00% |
| `write_pdf_batch_summary.py` | 0.00% |
| `unknown:python3` | 0.00% |
| `unknown:python` | 0.00% |

## 原生库

| DSO | ROI 周期占比 |
|---|---:|
| `/opt/python-3.12.3/lib/libpython3.12.so.1.0` | 46.72% |
| `/usr/lib64/libz.so.1.2.13` | 26.44% |
| `/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so` | 19.23% |
| `/usr/lib64/libpoppler.so.133.0.0` | 3.82% |
| `/usr/lib64/libc.so.6` | 1.94% |
| `/usr/lib64/libfreetype.so.6.20.1` | 1.32% |
| `[unknown]` | 0.23% |
| `[vdso]` | 0.21% |
| `/usr/lib/ld-linux-aarch64.so.1` | 0.10% |
| `/opt/python-3.12.3/lib/python3.12/lib-dynload/_posixsubprocess.cpython-312-aarch64-linux-gnu.so` | 0.00% |

## Top-20 物理叶函数

| DSO | 函数 | ROI 周期占比 |
|---|---|---:|
| `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 22.85% |
| `libz.so.1.2.13` | `longest_match` | 9.88% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleHorizontal_8bpc` | 9.06% |
| `libz.so.1.2.13` | `deflate_slow` | 6.58% |
| `libz.so.1.2.13` | `compress_block` | 4.67% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingZipEncode` | 4.53% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleVertical_8bpc` | 4.05% |
| `libz.so.1.2.13` | `slide_hash` | 2.60% |
| `libz.so.1.2.13` | `inflate_fast` | 2.26% |
| `libpython3.12.so.1.0` | `gc_collect_main` | 1.93% |
| `libpython3.12.so.1.0` | `_Py_dict_lookup` | 1.92% |
| `libpython3.12.so.1.0` | `deduce_unreachable` | 1.34% |
| `libpoppler.so.133.0.0` | `Splash::pipeRunAARGB8(SplashPipe*)` | 1.25% |
| `libpython3.12.so.1.0` | `PyObject_GC_Del` | 1.09% |
| `libpython3.12.so.1.0` | `_PyFrame_MakeAndSetFrameObject` | 0.97% |
| `libpython3.12.so.1.0` | `_Py_type_getattro` | 0.88% |
| `libpython3.12.so.1.0` | `unicode_dealloc` | 0.86% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingPackRGB` | 0.74% |
| `libpython3.12.so.1.0` | `_PyEvalFrameClearAndPop` | 0.68% |
| `libpoppler.so.133.0.0` | `Splash::compositeBackground(unsigned char const*)` | 0.68% |

## 带脚本上下文的 Top-20 函数

| 实际脚本/程序 | DSO | 函数 | ROI 周期占比 |
|---|---|---|---:|
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 16.21% |
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `longest_match` | 9.88% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleHorizontal_8bpc` | 9.06% |
| `verify_pdf_batch.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 6.63% |
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `deflate_slow` | 6.58% |
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `compress_block` | 4.67% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingZipEncode` | 4.53% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleVertical_8bpc` | 4.05% |
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `slide_hash` | 2.60% |
| `verify_pdf_batch.py` | `libz.so.1.2.13` | `inflate_fast` | 2.26% |
| `verify_pdf_batch.py` | `libpython3.12.so.1.0` | `_Py_dict_lookup` | 1.91% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `gc_collect_main` | 1.71% |
| `pdftoppm` | `libpoppler.so.133.0.0` | `Splash::pipeRunAARGB8(SplashPipe*)` | 1.25% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `deduce_unreachable` | 1.12% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `PyObject_GC_Del` | 1.09% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `_PyFrame_MakeAndSetFrameObject` | 0.97% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `_Py_type_getattro` | 0.88% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingPackRGB` | 0.74% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `_PyEvalFrameClearAndPop` | 0.68% |
| `pdftoppm` | `libpoppler.so.133.0.0` | `Splash::compositeBackground(unsigned char const*)` | 0.68% |

## 质量和边界

- 空栈 0.000%；未知叶 DSO 0.225%；未知叶符号 0.438%。这些类别可能重叠。
- 无法关联脚本的 period：0.003%；首次观察前 10 ms 内的推断归属：0.114%。身份来自 10 ms 名义间隔的 /proc 观察，并非精确 exec 事件。
- 完整栈导出与无栈计数导出按 PID/TID/纳秒时间/period/event 的多重集合逐样本核对；ROI 内外 period 守恒。
- 按 CLOCK_MONOTONIC 的实际 ROI 标记裁剪；循环外预检、归档和哈希不计入主表。采集器及 monitor 不在 perf 的目标子树中。
- 同一镜像内 `--no-inline` 导出物理调用链；未知叶节点不继承调用者符号。
- 用户态采样不包含内核 CPU 和阻塞等待；未进行开销校准或重复稳定性检验，也未采集 py-spy。
- perf lost/符号化警告原文保存在 profile.json 的 capture_quality 与 raw 日志；其 ROI 归属未知，不换算成周期权重。

原始证据：`analysis/hotspots/raw/irs-w4-native-pilot-20261027T103444Z-ea88d68e`；停止容器：`ceb63b1d5376d5143d1014f8da5d517403e39bd6d9522a845f670ea1c54f83c6`。
