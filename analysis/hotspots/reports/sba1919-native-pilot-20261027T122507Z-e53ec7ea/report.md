# SBA 1919 热点采集

当前 Agent 轨迹版，N=10，一轮。新旧对比另见汇总报告。

实际镜像：`sha256:4baef1363ba99a994e17e93fe6a32c904cdb5cb349487adfa2fb13ba42301499`。循环执行及业务验证成功。

正式循环 ROI：878 个样本，period 合计 40,206,043,103。

以下均以完整 ROI 的用户态 `cycles:u` period 为分母，未知项未从分母排除。不是整轮 user+sys CPU 时间占比。

## 脚本与进程

| 实际脚本/程序 | ROI 周期占比 |
|---|---:|
| `convert_pdf_to_images.py` | 45.62% |
| `fill_fillable_fields.py` | 27.81% |
| `pdftoppm` | 15.71% |
| `verify_pdf_batch.py` | 10.30% |
| `check_fillable_fields.py` | 0.53% |
| `pdfinfo` | 0.02% |
| `unknown:pdftoppm` | 0.00% |
| `run_batch.py` | 0.00% |
| `build_field_values.py` | 0.00% |
| `write_pdf_batch_summary.py` | 0.00% |
| `extract_form_field_info.py` | 0.00% |
| `unknown:python` | 0.00% |

## 原生库

| DSO | ROI 周期占比 |
|---|---:|
| `/opt/python-3.12.3/lib/libpython3.12.so.1.0` | 34.69% |
| `/usr/lib64/libz.so.1.2.13` | 27.39% |
| `/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so` | 19.05% |
| `/usr/lib64/libpoppler.so.133.0.0` | 9.24% |
| `/usr/lib64/libc.so.6` | 4.94% |
| `/usr/lib64/libfreetype.so.6.20.1` | 4.33% |
| `/usr/lib/ld-linux-aarch64.so.1` | 0.21% |
| `[vdso]` | 0.14% |
| `[unknown]` | 0.01% |
| `/opt/python-3.12.3/lib/python3.12/lib-dynload/_posixsubprocess.cpython-312-aarch64-linux-gnu.so` | 0.00% |
| `/opt/python-3.12.3/lib/python3.12/lib-dynload/select.cpython-312-aarch64-linux-gnu.so` | 0.00% |

## Top-20 物理叶函数

| DSO | 函数 | ROI 周期占比 |
|---|---|---:|
| `libz.so.1.2.13` | `longest_match` | 16.03% |
| `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 10.89% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleHorizontal_8bpc` | 7.70% |
| `libz.so.1.2.13` | `deflate_slow` | 6.69% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleVertical_8bpc` | 5.17% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingZipEncode` | 4.60% |
| `libpoppler.so.133.0.0` | `Splash::compositeBackground(unsigned char const*)` | 4.48% |
| `libpython3.12.so.1.0` | `deduce_unreachable` | 2.63% |
| `libpython3.12.so.1.0` | `subtype_traverse` | 2.51% |
| `libpython3.12.so.1.0` | `method_vectorcall` | 2.35% |
| `libpoppler.so.133.0.0` | `Splash::pipeRunAARGB8(SplashPipe*)` | 2.25% |
| `libz.so.1.2.13` | `slide_hash` | 1.91% |
| `libpython3.12.so.1.0` | `_Py_dict_lookup` | 1.86% |
| `libc.so.6` | `strchr` | 1.50% |
| `libc.so.6` | `_IO_file_write@@GLIBC_2.17` | 1.30% |
| `libfreetype.so.6.20.1` | `gray_render_line` | 1.06% |
| `libz.so.1.2.13` | `compress_block` | 1.02% |
| `libfreetype.so.6.20.1` | `gray_conic_to` | 0.97% |
| `libpython3.12.so.1.0` | `gc_collect_main` | 0.87% |
| `libz.so.1.2.13` | `adler32_z` | 0.87% |

## 带脚本上下文的 Top-20 函数

| 实际脚本/程序 | DSO | 函数 | ROI 周期占比 |
|---|---|---|---:|
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `longest_match` | 16.03% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleHorizontal_8bpc` | 7.70% |
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `deflate_slow` | 6.69% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 5.80% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleVertical_8bpc` | 5.17% |
| `verify_pdf_batch.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 5.09% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingZipEncode` | 4.60% |
| `pdftoppm` | `libpoppler.so.133.0.0` | `Splash::compositeBackground(unsigned char const*)` | 4.48% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `subtype_traverse` | 2.37% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `method_vectorcall` | 2.35% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `deduce_unreachable` | 2.34% |
| `pdftoppm` | `libpoppler.so.133.0.0` | `Splash::pipeRunAARGB8(SplashPipe*)` | 2.25% |
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `slide_hash` | 1.91% |
| `fill_fillable_fields.py` | `libc.so.6` | `strchr` | 1.50% |
| `verify_pdf_batch.py` | `libpython3.12.so.1.0` | `_Py_dict_lookup` | 1.43% |
| `pdftoppm` | `libc.so.6` | `_IO_file_write@@GLIBC_2.17` | 1.30% |
| `pdftoppm` | `libfreetype.so.6.20.1` | `gray_render_line` | 1.06% |
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `compress_block` | 1.02% |
| `pdftoppm` | `libfreetype.so.6.20.1` | `gray_conic_to` | 0.97% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `PyObject_GC_Del` | 0.74% |

## 质量和边界

- 空栈 0.000%；未知叶 DSO 0.006%；未知叶符号 0.150%。这些类别可能重叠。
- 无法关联脚本的 period：0.002%；首次观察前 10 ms 内的推断归属：0.080%。身份来自 10 ms 名义间隔的 /proc 观察，并非精确 exec 事件。
- 完整栈导出与无栈计数导出按 PID/TID/纳秒时间/period/event 的多重集合逐样本核对；ROI 内外 period 守恒。
- 按 CLOCK_MONOTONIC 的实际 ROI 标记裁剪；循环外预检、归档和哈希不计入主表。采集器及 monitor 不在 perf 的目标子树中。
- 同一镜像内 `--no-inline` 导出物理调用链；未知叶节点不继承调用者符号。
- 用户态采样不包含内核 CPU 和阻塞等待；未进行开销校准或重复稳定性检验，也未采集 py-spy。
- perf 聚合统计 SAMPLE=945、LOST 记录=0、LOST_SAMPLES 记录=0；record 日志报告 lost chunks=0。这些诊断不构成采集绝对无损的证明。
- 显示 0.00% 仅表示采样权重很小或未获得明显采样，不表示脚本未执行或实际 CPU 为零。
- perf lost/符号化警告原文保存在 profile.json 的 capture_quality 与 raw 日志；其 ROI 归属未知，不换算成周期权重。

原始证据：`analysis/hotspots/raw/sba1919-native-pilot-20261027T122507Z-e53ec7ea`；停止容器：`924efa85910662c93cf53757d1642c3894592408b16c0a98a8aebd6fb88f5125`。
