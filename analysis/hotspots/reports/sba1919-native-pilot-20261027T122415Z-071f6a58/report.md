# SBA 1919 热点采集

当前 Agent 轨迹版，N=10，一轮。新旧对比另见汇总报告。

实际镜像：`sha256:4baef1363ba99a994e17e93fe6a32c904cdb5cb349487adfa2fb13ba42301499`。循环执行及业务验证成功。

正式循环 ROI：868 个样本，period 合计 40,738,129,426。

以下均以完整 ROI 的用户态 `cycles:u` period 为分母，未知项未从分母排除。不是整轮 user+sys CPU 时间占比。

## 脚本与进程

| 实际脚本/程序 | ROI 周期占比 |
|---|---:|
| `convert_pdf_to_images.py` | 44.33% |
| `fill_fillable_fields.py` | 28.11% |
| `pdftoppm` | 15.00% |
| `verify_pdf_batch.py` | 11.35% |
| `extract_form_field_info.py` | 0.67% |
| `check_fillable_fields.py` | 0.53% |
| `pdfinfo` | 0.01% |
| `unknown:pdftoppm` | 0.00% |
| `run.py` | 0.00% |
| `run_batch.py` | 0.00% |
| `build_field_values.py` | 0.00% |
| `unknown:python` | 0.00% |

## 原生库

| DSO | ROI 周期占比 |
|---|---:|
| `/opt/python-3.12.3/lib/libpython3.12.so.1.0` | 37.04% |
| `/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so` | 24.31% |
| `/usr/lib64/libz.so.1.2.13` | 20.66% |
| `/usr/lib64/libpoppler.so.133.0.0` | 7.04% |
| `/usr/lib64/libfreetype.so.6.20.1` | 5.40% |
| `/usr/lib64/libc.so.6` | 5.22% |
| `[vdso]` | 0.14% |
| `/usr/lib64/libstdc++.so.6.0.30` | 0.13% |
| `/usr/lib/ld-linux-aarch64.so.1` | 0.06% |
| `[unknown]` | 0.00% |
| `/opt/python-3.12.3/lib/python3.12/lib-dynload/_posixsubprocess.cpython-312-aarch64-linux-gnu.so` | 0.00% |

## Top-20 物理叶函数

| DSO | 函数 | ROI 周期占比 |
|---|---|---:|
| `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 14.88% |
| `libz.so.1.2.13` | `longest_match` | 12.58% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleHorizontal_8bpc` | 9.50% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingZipEncode` | 7.68% |
| `libz.so.1.2.13` | `deflate_slow` | 4.71% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleVertical_8bpc` | 4.36% |
| `libpython3.12.so.1.0` | `gc_collect_main` | 2.65% |
| `libc.so.6` | `sem_trywait@@GLIBC_2.34` | 2.39% |
| `libpoppler.so.133.0.0` | `Splash::pipeRunAARGB8(SplashPipe*)` | 2.04% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingUnpackRGB` | 1.92% |
| `libfreetype.so.6.20.1` | `gray_render_line` | 1.66% |
| `libc.so.6` | `_int_free` | 1.56% |
| `libz.so.1.2.13` | `slide_hash` | 1.35% |
| `libpython3.12.so.1.0` | `_Py_dict_lookup` | 1.34% |
| `libpython3.12.so.1.0` | `bytes_richcompare` | 1.32% |
| `libpython3.12.so.1.0` | `_PyObject_Malloc` | 1.23% |
| `libpoppler.so.133.0.0` | `Splash::compositeBackground(unsigned char const*)` | 1.10% |
| `libfreetype.so.6.20.1` | `gray_convert_glyph` | 1.00% |
| `libpython3.12.so.1.0` | `PyObject_GC_Del` | 0.82% |
| `libfreetype.so.6.20.1` | `TT_Load_Simple_Glyph` | 0.78% |

## 带脚本上下文的 Top-20 函数

| 实际脚本/程序 | DSO | 函数 | ROI 周期占比 |
|---|---|---|---:|
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `longest_match` | 12.58% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleHorizontal_8bpc` | 9.50% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingZipEncode` | 7.68% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 7.45% |
| `verify_pdf_batch.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 7.27% |
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `deflate_slow` | 4.71% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleVertical_8bpc` | 4.36% |
| `fill_fillable_fields.py` | `libc.so.6` | `sem_trywait@@GLIBC_2.34` | 2.39% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `gc_collect_main` | 2.36% |
| `pdftoppm` | `libpoppler.so.133.0.0` | `Splash::pipeRunAARGB8(SplashPipe*)` | 2.04% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingUnpackRGB` | 1.78% |
| `pdftoppm` | `libfreetype.so.6.20.1` | `gray_render_line` | 1.66% |
| `pdftoppm` | `libc.so.6` | `_int_free` | 1.56% |
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `slide_hash` | 1.35% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `bytes_richcompare` | 1.32% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `_PyObject_Malloc` | 1.23% |
| `pdftoppm` | `libpoppler.so.133.0.0` | `Splash::compositeBackground(unsigned char const*)` | 1.10% |
| `pdftoppm` | `libfreetype.so.6.20.1` | `gray_convert_glyph` | 1.00% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `PyObject_GC_Del` | 0.82% |
| `pdftoppm` | `libfreetype.so.6.20.1` | `TT_Load_Simple_Glyph` | 0.78% |

## 质量和边界

- 空栈 0.000%；未知叶 DSO 0.003%；未知叶符号 0.145%。这些类别可能重叠。
- 无法关联脚本的 period：0.002%；首次观察前 10 ms 内的推断归属：0.072%。身份来自 10 ms 名义间隔的 /proc 观察，并非精确 exec 事件。
- 完整栈导出与无栈计数导出按 PID/TID/纳秒时间/period/event 的多重集合逐样本核对；ROI 内外 period 守恒。
- 按 CLOCK_MONOTONIC 的实际 ROI 标记裁剪；循环外预检、归档和哈希不计入主表。采集器及 monitor 不在 perf 的目标子树中。
- 同一镜像内 `--no-inline` 导出物理调用链；未知叶节点不继承调用者符号。
- 用户态采样不包含内核 CPU 和阻塞等待；未进行开销校准或重复稳定性检验，也未采集 py-spy。
- perf 聚合统计 SAMPLE=919、LOST 记录=0、LOST_SAMPLES 记录=0；record 日志报告 lost chunks=0。这些诊断不构成采集绝对无损的证明。
- 显示 0.00% 仅表示采样权重很小或未获得明显采样，不表示脚本未执行或实际 CPU 为零。
- perf lost/符号化警告原文保存在 profile.json 的 capture_quality 与 raw 日志；其 ROI 归属未知，不换算成周期权重。

原始证据：`analysis/hotspots/raw/sba1919-native-pilot-20261027T122415Z-071f6a58`；停止容器：`e7561c6afd55a0d898a71dae4059f8d0f5e617d9a9d6eaf4a47becb5060eb17f`。
