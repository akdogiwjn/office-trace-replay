# IRS W-4 热点采集

当前 Agent 轨迹版，N=10，一轮。新旧对比另见汇总报告。

实际镜像：`sha256:4baef1363ba99a994e17e93fe6a32c904cdb5cb349487adfa2fb13ba42301499`。循环执行及业务验证成功。

正式循环 ROI：664 个样本，period 合计 31,998,053,594。

以下均以完整 ROI 的用户态 `cycles:u` period 为分母，未知项未从分母排除。不是整轮 user+sys CPU 时间占比。

## 脚本与进程

| 实际脚本/程序 | ROI 周期占比 |
|---|---:|
| `convert_pdf_to_images.py` | 42.59% |
| `fill_fillable_fields.py` | 38.34% |
| `verify_pdf_batch.py` | 11.94% |
| `pdftoppm` | 7.10% |
| `pdfinfo` | 0.02% |
| `unknown:pdftoppm` | 0.00% |
| `run_batch.py` | 0.00% |
| `check_fillable_fields.py` | 0.00% |
| `extract_form_field_info.py` | 0.00% |
| `build_field_values.py` | 0.00% |
| `write_pdf_batch_summary.py` | 0.00% |
| `unknown:python3` | 0.00% |
| `unknown:python` | 0.00% |

## 原生库

| DSO | ROI 周期占比 |
|---|---:|
| `/opt/python-3.12.3/lib/libpython3.12.so.1.0` | 46.42% |
| `/usr/lib64/libz.so.1.2.13` | 30.58% |
| `/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so` | 14.37% |
| `/usr/lib64/libpoppler.so.133.0.0` | 3.38% |
| `/usr/lib64/libfreetype.so.6.20.1` | 2.82% |
| `/usr/lib64/libc.so.6` | 1.96% |
| `/usr/lib/ld-linux-aarch64.so.1` | 0.27% |
| `/usr/lib64/libstdc++.so.6.0.30` | 0.20% |
| `[unknown]` | 0.00% |
| `/opt/python-3.12.3/lib/python3.12/lib-dynload/_posixsubprocess.cpython-312-aarch64-linux-gnu.so` | 0.00% |

## Top-20 物理叶函数

| DSO | 函数 | ROI 周期占比 |
|---|---|---:|
| `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 24.08% |
| `libz.so.1.2.13` | `longest_match` | 13.03% |
| `libz.so.1.2.13` | `slide_hash` | 6.67% |
| `libz.so.1.2.13` | `deflate_slow` | 5.27% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleHorizontal_8bpc` | 4.92% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingZipEncode` | 4.87% |
| `libpython3.12.so.1.0` | `_PyUnicodeWriter_Finish` | 2.61% |
| `libz.so.1.2.13` | `compress_block` | 2.23% |
| `libpython3.12.so.1.0` | `visit_reachable` | 2.13% |
| `libz.so.1.2.13` | `build_tree` | 1.68% |
| `libpython3.12.so.1.0` | `check_except_type_valid` | 1.46% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleVertical_8bpc` | 1.45% |
| `libpython3.12.so.1.0` | `_Py_dict_lookup` | 1.43% |
| `libpython3.12.so.1.0` | `gc_collect_main` | 1.27% |
| `libpoppler.so.133.0.0` | `Splash::compositeBackground(unsigned char const*)` | 1.26% |
| `libpoppler.so.133.0.0` | `Splash::pipeRunAARGB8(SplashPipe*)` | 1.23% |
| `libz.so.1.2.13` | `inflate_fast` | 1.16% |
| `libpython3.12.so.1.0` | `iter_iternext` | 1.07% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingPackRGB` | 0.96% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingUnpackRGB` | 0.74% |

## 带脚本上下文的 Top-20 函数

| 实际脚本/程序 | DSO | 函数 | ROI 周期占比 |
|---|---|---|---:|
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 20.29% |
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `longest_match` | 13.03% |
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `slide_hash` | 6.67% |
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `deflate_slow` | 5.27% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleHorizontal_8bpc` | 4.92% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingZipEncode` | 4.87% |
| `verify_pdf_batch.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 3.79% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `_PyUnicodeWriter_Finish` | 2.61% |
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `compress_block` | 2.23% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `visit_reachable` | 2.13% |
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `build_tree` | 1.68% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `check_except_type_valid` | 1.46% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleVertical_8bpc` | 1.45% |
| `verify_pdf_batch.py` | `libpython3.12.so.1.0` | `_Py_dict_lookup` | 1.43% |
| `pdftoppm` | `libpoppler.so.133.0.0` | `Splash::compositeBackground(unsigned char const*)` | 1.26% |
| `pdftoppm` | `libpoppler.so.133.0.0` | `Splash::pipeRunAARGB8(SplashPipe*)` | 1.23% |
| `verify_pdf_batch.py` | `libz.so.1.2.13` | `inflate_fast` | 1.16% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `gc_collect_main` | 1.09% |
| `verify_pdf_batch.py` | `libpython3.12.so.1.0` | `iter_iternext` | 1.07% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingPackRGB` | 0.96% |

## 质量和边界

- 空栈 0.000%；未知叶 DSO 0.003%；未知叶符号 0.003%。这些类别可能重叠。
- 无法关联脚本的 period：0.004%；首次观察前 10 ms 内的推断归属：0.085%。身份来自 10 ms 名义间隔的 /proc 观察，并非精确 exec 事件。
- 完整栈导出与无栈计数导出按 PID/TID/纳秒时间/period/event 的多重集合逐样本核对；ROI 内外 period 守恒。
- 按 CLOCK_MONOTONIC 的实际 ROI 标记裁剪；循环外预检、归档和哈希不计入主表。采集器及 monitor 不在 perf 的目标子树中。
- 同一镜像内 `--no-inline` 导出物理调用链；未知叶节点不继承调用者符号。
- 用户态采样不包含内核 CPU 和阻塞等待；未进行开销校准或重复稳定性检验，也未采集 py-spy。
- perf 聚合统计 SAMPLE=715、LOST 记录=0、LOST_SAMPLES 记录=0；record 日志报告 lost chunks=0。这些诊断不构成采集绝对无损的证明。
- 显示 0.00% 仅表示采样权重很小或未获得明显采样，不表示脚本未执行或实际 CPU 为零。
- perf lost/符号化警告原文保存在 profile.json 的 capture_quality 与 raw 日志；其 ROI 归属未知，不换算成周期权重。

原始证据：`analysis/hotspots/raw/irs-w4-native-pilot-20261027T122541Z-70ea9e63`；停止容器：`15704bb6d5785d5bb49bae3f52162e129394ef22df1d537f796689d4387d2606`。
