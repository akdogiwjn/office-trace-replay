# OPM 热点采集

当前 Agent 轨迹版，N=10，一轮。新旧对比另见汇总报告。

实际镜像：`sha256:4baef1363ba99a994e17e93fe6a32c904cdb5cb349487adfa2fb13ba42301499`。循环执行及业务验证成功。

正式循环 ROI：544 个样本，period 合计 18,375,366,414。

以下均以完整 ROI 的用户态 `cycles:u` period 为分母，未知项未从分母排除。不是整轮 user+sys CPU 时间占比。

## 脚本与进程

| 实际脚本/程序 | ROI 周期占比 |
|---|---:|
| `fill_fillable_fields.py` | 40.74% |
| `convert_pdf_to_images.py` | 31.96% |
| `verify_pdf_batch.py` | 15.03% |
| `pdftoppm` | 9.75% |
| `check_fillable_fields.py` | 2.43% |
| `pdfinfo` | 0.03% |
| `unknown:bash` | 0.02% |
| `bash` | 0.01% |
| `extract_form_field_info.py` | 0.01% |
| `unknown:ls` | 0.01% |
| `run_batch_fill_render.py` | 0.00% |
| `unknown:pdftoppm` | 0.00% |
| `legacy_capture.py` | 0.00% |
| `python-inline-or-module` | 0.00% |
| `unknown:find` | 0.00% |
| `unknown:sort` | 0.00% |
| `unknown:python3` | 0.00% |
| `unknown:python` | 0.00% |

## 原生库

| DSO | ROI 周期占比 |
|---|---:|
| `/opt/python-3.12.3/lib/libpython3.12.so.1.0` | 48.89% |
| `/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so` | 19.88% |
| `/usr/lib64/libz.so.1.2.13` | 19.69% |
| `/usr/lib64/libpoppler.so.133.0.0` | 7.70% |
| `/usr/lib64/libc.so.6` | 2.22% |
| `/usr/lib64/libfreetype.so.6.20.1` | 1.04% |
| `/usr/lib64/libfontconfig.so.1.12.1` | 0.42% |
| `/usr/lib/ld-linux-aarch64.so.1` | 0.12% |
| `/usr/bin/bash` | 0.02% |
| `[unknown]` | 0.02% |
| `/usr/bin/ls` | 0.00% |
| `/opt/python-3.12.3/lib/python3.12/lib-dynload/_posixsubprocess.cpython-312-aarch64-linux-gnu.so` | 0.00% |

## Top-20 物理叶函数

| DSO | 函数 | ROI 周期占比 |
|---|---|---:|
| `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 12.56% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingZipEncode` | 5.25% |
| `libpython3.12.so.1.0` | `do_super_lookup` | 4.99% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleVertical_8bpc` | 4.98% |
| `libz.so.1.2.13` | `slide_hash` | 4.88% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleHorizontal_8bpc` | 4.81% |
| `libz.so.1.2.13` | `inflate_fast` | 4.50% |
| `libpoppler.so.133.0.0` | `Splash::compositeBackground(unsigned char const*)` | 4.44% |
| `libpython3.12.so.1.0` | `PyMethod_New` | 4.22% |
| `libz.so.1.2.13` | `longest_match` | 4.05% |
| `libz.so.1.2.13` | `deflate_slow` | 3.82% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingUnpackRGB` | 2.04% |
| `libpython3.12.so.1.0` | `PyObject_RichCompare` | 1.81% |
| `libz.so.1.2.13` | `compress_block` | 1.79% |
| `libpython3.12.so.1.0` | `tupledealloc` | 1.78% |
| `libpython3.12.so.1.0` | `object_dealloc` | 1.78% |
| `libpython3.12.so.1.0` | `PyUnicode_FromFormatV` | 1.64% |
| `libpython3.12.so.1.0` | `_PyEvalFrameClearAndPop` | 1.46% |
| `libpoppler.so.133.0.0` | `Lexer::getObj(int)` | 1.31% |
| `libpython3.12.so.1.0` | `deduce_unreachable` | 1.27% |

## 带脚本上下文的 Top-20 函数

| 实际脚本/程序 | DSO | 函数 | ROI 周期占比 |
|---|---|---|---:|
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 8.18% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingZipEncode` | 5.25% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleVertical_8bpc` | 4.98% |
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `slide_hash` | 4.88% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleHorizontal_8bpc` | 4.81% |
| `verify_pdf_batch.py` | `libpython3.12.so.1.0` | `do_super_lookup` | 4.67% |
| `pdftoppm` | `libpoppler.so.133.0.0` | `Splash::compositeBackground(unsigned char const*)` | 4.44% |
| `verify_pdf_batch.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 4.37% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `PyMethod_New` | 4.22% |
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `longest_match` | 4.05% |
| `fill_fillable_fields.py` | `libz.so.1.2.13` | `inflate_fast` | 3.87% |
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `deflate_slow` | 3.82% |
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `compress_block` | 1.79% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `tupledealloc` | 1.78% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `object_dealloc` | 1.78% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingUnpackRGB` | 1.72% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `PyUnicode_FromFormatV` | 1.64% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `_PyEvalFrameClearAndPop` | 1.46% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `PyObject_RichCompare` | 1.46% |
| `pdftoppm` | `libpoppler.so.133.0.0` | `Lexer::getObj(int)` | 1.31% |

## 质量和边界

- 空栈 0.000%；未知叶 DSO 0.017%；未知叶符号 0.452%。这些类别可能重叠。
- 无法关联脚本的 period：0.030%；首次观察前 10 ms 内的推断归属：0.111%。身份来自 10 ms 名义间隔的 /proc 观察，并非精确 exec 事件。
- 完整栈导出与无栈计数导出按 PID/TID/纳秒时间/period/event 的多重集合逐样本核对；ROI 内外 period 守恒。
- 按 CLOCK_MONOTONIC 的实际 ROI 标记裁剪；循环外预检、归档和哈希不计入主表。采集器及 monitor 不在 perf 的目标子树中。
- 同一镜像内 `--no-inline` 导出物理调用链；未知叶节点不继承调用者符号。
- 用户态采样不包含内核 CPU 和阻塞等待；未进行开销校准或重复稳定性检验，也未采集 py-spy。
- perf 聚合统计 SAMPLE=553、LOST 记录=0、LOST_SAMPLES 记录=0；record 日志报告 lost chunks=0。这些诊断不构成采集绝对无损的证明。
- 显示 0.00% 仅表示采样权重很小或未获得明显采样，不表示脚本未执行或实际 CPU 为零。
- perf lost/符号化警告原文保存在 profile.json 的 capture_quality 与 raw 日志；其 ROI 归属未知，不换算成周期权重。

原始证据：`analysis/hotspots/raw/opm-native-pilot-20261027T122345Z-2de08010`；停止容器：`95fbeaa247cc71d41dec4b3e5fe860108f1983e17a9be9c52bd21fbc3d66bb8a`。
