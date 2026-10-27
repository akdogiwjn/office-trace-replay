# SBA 1919 热点采集

当前 Agent 轨迹版，N=10，一轮。新旧对比另见汇总报告。

实际镜像：`sha256:4baef1363ba99a994e17e93fe6a32c904cdb5cb349487adfa2fb13ba42301499`。循环执行及业务验证成功。

正式循环 ROI：839 个样本，period 合计 40,184,954,447。

以下均以完整 ROI 的用户态 `cycles:u` period 为分母，未知项未从分母排除。不是整轮 user+sys CPU 时间占比。

## 脚本与进程

| 实际脚本/程序 | ROI 周期占比 |
|---|---:|
| `convert_pdf_to_images.py` | 47.29% |
| `fill_fillable_fields.py` | 25.65% |
| `pdftoppm` | 15.39% |
| `verify_pdf_batch.py` | 11.65% |
| `pdfinfo` | 0.01% |
| `unknown:pdftoppm` | 0.00% |
| `run_batch.py` | 0.00% |
| `check_fillable_fields.py` | 0.00% |
| `build_field_values.py` | 0.00% |
| `extract_form_field_info.py` | 0.00% |
| `write_pdf_batch_summary.py` | 0.00% |
| `unknown:python` | 0.00% |

## 原生库

| DSO | ROI 周期占比 |
|---|---:|
| `/opt/python-3.12.3/lib/libpython3.12.so.1.0` | 35.13% |
| `/usr/lib64/libz.so.1.2.13` | 27.93% |
| `/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so` | 19.47% |
| `/usr/lib64/libfreetype.so.6.20.1` | 10.70% |
| `/usr/lib64/libpoppler.so.133.0.0` | 4.41% |
| `/usr/lib64/libc.so.6` | 1.30% |
| `/usr/lib/ld-linux-aarch64.so.1` | 0.91% |
| `/usr/lib64/libm.so.6` | 0.15% |
| `[unknown]` | 0.00% |
| `/opt/python-3.12.3/lib/python3.12/lib-dynload/_posixsubprocess.cpython-312-aarch64-linux-gnu.so` | 0.00% |

## Top-20 物理叶函数

| DSO | 函数 | ROI 周期占比 |
|---|---|---:|
| `libz.so.1.2.13` | `longest_match` | 16.81% |
| `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 15.94% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleHorizontal_8bpc` | 8.47% |
| `libz.so.1.2.13` | `deflate_slow` | 6.17% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingZipEncode` | 4.88% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleVertical_8bpc` | 4.24% |
| `libfreetype.so.6.20.1` | `gray_render_line` | 3.82% |
| `libz.so.1.2.13` | `slide_hash` | 3.64% |
| `libfreetype.so.6.20.1` | `gray_set_cell` | 2.48% |
| `libpoppler.so.133.0.0` | `Splash::pipeRunAARGB8(SplashPipe*)` | 2.40% |
| `libpython3.12.so.1.0` | `gc_collect_main` | 2.27% |
| `libfreetype.so.6.20.1` | `TT_Load_Simple_Glyph` | 1.90% |
| `libpython3.12.so.1.0` | `PyErr_Format` | 1.89% |
| `libfreetype.so.6.20.1` | `gray_conic_to` | 1.43% |
| `libpython3.12.so.1.0` | `tupledealloc` | 1.19% |
| `libpython3.12.so.1.0` | `_Py_dict_lookup` | 1.17% |
| `ld-linux-aarch64.so.1` | `_dl_tlsdesc_return` | 0.84% |
| `libpython3.12.so.1.0` | `_PyUnicodeWriter_Finish` | 0.73% |
| `libpython3.12.so.1.0` | `deduce_unreachable` | 0.73% |
| `libpython3.12.so.1.0` | `state_fini` | 0.64% |

## 带脚本上下文的 Top-20 函数

| 实际脚本/程序 | DSO | 函数 | ROI 周期占比 |
|---|---|---|---:|
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `longest_match` | 16.81% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 8.76% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleHorizontal_8bpc` | 8.47% |
| `verify_pdf_batch.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 7.03% |
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `deflate_slow` | 6.17% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingZipEncode` | 4.88% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleVertical_8bpc` | 4.24% |
| `pdftoppm` | `libfreetype.so.6.20.1` | `gray_render_line` | 3.82% |
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `slide_hash` | 3.64% |
| `pdftoppm` | `libfreetype.so.6.20.1` | `gray_set_cell` | 2.48% |
| `pdftoppm` | `libpoppler.so.133.0.0` | `Splash::pipeRunAARGB8(SplashPipe*)` | 2.40% |
| `pdftoppm` | `libfreetype.so.6.20.1` | `TT_Load_Simple_Glyph` | 1.90% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `PyErr_Format` | 1.89% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `gc_collect_main` | 1.84% |
| `pdftoppm` | `libfreetype.so.6.20.1` | `gray_conic_to` | 1.43% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `tupledealloc` | 1.19% |
| `verify_pdf_batch.py` | `libpython3.12.so.1.0` | `_Py_dict_lookup` | 1.02% |
| `fill_fillable_fields.py` | `ld-linux-aarch64.so.1` | `_dl_tlsdesc_return` | 0.84% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `_PyUnicodeWriter_Finish` | 0.73% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `state_fini` | 0.64% |

## 质量和边界

- 空栈 0.000%；未知叶 DSO 0.004%；未知叶符号 0.004%。这些类别可能重叠。
- 无法关联脚本的 period：0.002%；首次观察前 10 ms 内的推断归属：0.069%。身份来自 10 ms 名义间隔的 /proc 观察，并非精确 exec 事件。
- 完整栈导出与无栈计数导出按 PID/TID/纳秒时间/period/event 的多重集合逐样本核对；ROI 内外 period 守恒。
- 按 CLOCK_MONOTONIC 的实际 ROI 标记裁剪；循环外预检、归档和哈希不计入主表。采集器及 monitor 不在 perf 的目标子树中。
- 同一镜像内 `--no-inline` 导出物理调用链；未知叶节点不继承调用者符号。
- 用户态采样不包含内核 CPU 和阻塞等待；未进行开销校准或重复稳定性检验，也未采集 py-spy。
- perf 聚合统计 SAMPLE=913、LOST 记录=0、LOST_SAMPLES 记录=0；record 日志报告 lost chunks=0。这些诊断不构成采集绝对无损的证明。
- 显示 0.00% 仅表示采样权重很小或未获得明显采样，不表示脚本未执行或实际 CPU 为零。
- perf lost/符号化警告原文保存在 profile.json 的 capture_quality 与 raw 日志；其 ROI 归属未知，不换算成周期权重。

原始证据：`analysis/hotspots/raw/sba1919-native-pilot-20261027T122651Z-9c112a75`；停止容器：`f91a207ca906a849ed7e4b2cc7d551dc86cf43292ca3f0f0b89ab1171d67b856`。
