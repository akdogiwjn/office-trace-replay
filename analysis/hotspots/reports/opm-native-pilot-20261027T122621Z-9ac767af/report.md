# OPM 热点采集

当前 Agent 轨迹版，N=10，一轮。新旧对比另见汇总报告。

实际镜像：`sha256:4baef1363ba99a994e17e93fe6a32c904cdb5cb349487adfa2fb13ba42301499`。循环执行及业务验证成功。

正式循环 ROI：525 个样本，period 合计 17,577,097,213。

以下均以完整 ROI 的用户态 `cycles:u` period 为分母，未知项未从分母排除。不是整轮 user+sys CPU 时间占比。

## 脚本与进程

| 实际脚本/程序 | ROI 周期占比 |
|---|---:|
| `convert_pdf_to_images.py` | 41.36% |
| `fill_fillable_fields.py` | 38.62% |
| `verify_pdf_batch.py` | 11.30% |
| `pdftoppm` | 5.88% |
| `check_fillable_fields.py` | 2.75% |
| `pdfinfo` | 0.03% |
| `unknown:bash` | 0.02% |
| `bash` | 0.01% |
| `extract_form_field_info.py` | 0.00% |
| `legacy_capture.py` | 0.00% |
| `unknown:ls` | 0.00% |
| `python-inline-or-module` | 0.00% |
| `unknown:find` | 0.00% |
| `unknown:sort` | 0.00% |
| `unknown:wc` | 0.00% |
| `unknown:python3` | 0.00% |
| `unknown:python` | 0.00% |

## 原生库

| DSO | ROI 周期占比 |
|---|---:|
| `/opt/python-3.12.3/lib/libpython3.12.so.1.0` | 57.38% |
| `/usr/lib64/libz.so.1.2.13` | 26.29% |
| `/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so` | 10.02% |
| `/usr/lib64/libpoppler.so.133.0.0` | 4.19% |
| `/usr/lib64/libc.so.6` | 0.82% |
| `[unknown]` | 0.80% |
| `/usr/lib64/libfreetype.so.6.20.1` | 0.35% |
| `/usr/lib/ld-linux-aarch64.so.1` | 0.13% |
| `/usr/bin/bash` | 0.02% |
| `/opt/python-3.12.3/lib/python3.12/lib-dynload/_posixsubprocess.cpython-312-aarch64-linux-gnu.so` | 0.00% |
| `/opt/python-3.12.3/lib/python3.12/lib-dynload/select.cpython-312-aarch64-linux-gnu.so` | 0.00% |

## Top-20 物理叶函数

| DSO | 函数 | ROI 周期占比 |
|---|---|---:|
| `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 20.31% |
| `libz.so.1.2.13` | `longest_match` | 9.97% |
| `libz.so.1.2.13` | `deflate_slow` | 8.58% |
| `libpython3.12.so.1.0` | `deduce_unreachable` | 5.61% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleHorizontal_8bpc` | 4.93% |
| `libz.so.1.2.13` | `inflate_fast` | 3.40% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingZipEncode` | 3.20% |
| `libz.so.1.2.13` | `slide_hash` | 3.02% |
| `libpython3.12.so.1.0` | `_PyObject_MakeTpCall` | 2.90% |
| `libpython3.12.so.1.0` | `func_traverse` | 2.52% |
| `libpython3.12.so.1.0` | `_in_weak_set` | 2.50% |
| `libpoppler.so.133.0.0` | `Splash::compositeBackground(unsigned char const*)` | 2.10% |
| `libpython3.12.so.1.0` | `PyObject_GC_Del` | 2.03% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleVertical_8bpc` | 1.56% |
| `libpython3.12.so.1.0` | `tupledealloc` | 1.47% |
| `libpython3.12.so.1.0` | `gc_collect_main` | 1.33% |
| `libpython3.12.so.1.0` | `PyLong_FromString` | 1.17% |
| `libpoppler.so.133.0.0` | `Splash::pipeRunAARGB8(SplashPipe*)` | 1.13% |
| `libpython3.12.so.1.0` | `_PyFrame_MakeAndSetFrameObject` | 1.00% |
| `libpython3.12.so.1.0` | `_PyObject_GetMethod` | 0.97% |

## 带脚本上下文的 Top-20 函数

| 实际脚本/程序 | DSO | 函数 | ROI 周期占比 |
|---|---|---|---:|
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 12.62% |
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `longest_match` | 9.97% |
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `deflate_slow` | 8.58% |
| `verify_pdf_batch.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 7.69% |
| `convert_pdf_to_images.py` | `libpython3.12.so.1.0` | `deduce_unreachable` | 5.24% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleHorizontal_8bpc` | 4.93% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingZipEncode` | 3.20% |
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `slide_hash` | 3.02% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `_PyObject_MakeTpCall` | 2.90% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `_in_weak_set` | 2.50% |
| `convert_pdf_to_images.py` | `libpython3.12.so.1.0` | `func_traverse` | 2.19% |
| `pdftoppm` | `libpoppler.so.133.0.0` | `Splash::compositeBackground(unsigned char const*)` | 2.10% |
| `check_fillable_fields.py` | `libz.so.1.2.13` | `inflate_fast` | 2.09% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `PyObject_GC_Del` | 2.03% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleVertical_8bpc` | 1.56% |
| `verify_pdf_batch.py` | `libz.so.1.2.13` | `inflate_fast` | 1.32% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `tupledealloc` | 1.14% |
| `pdftoppm` | `libpoppler.so.133.0.0` | `Splash::pipeRunAARGB8(SplashPipe*)` | 1.13% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `_PyFrame_MakeAndSetFrameObject` | 1.00% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `gc_collect_main` | 1.00% |

## 质量和边界

- 空栈 0.000%；未知叶 DSO 0.803%；未知叶符号 0.809%。这些类别可能重叠。
- 无法关联脚本的 period：0.025%；首次观察前 10 ms 内的推断归属：0.120%。身份来自 10 ms 名义间隔的 /proc 观察，并非精确 exec 事件。
- 完整栈导出与无栈计数导出按 PID/TID/纳秒时间/period/event 的多重集合逐样本核对；ROI 内外 period 守恒。
- 按 CLOCK_MONOTONIC 的实际 ROI 标记裁剪；循环外预检、归档和哈希不计入主表。采集器及 monitor 不在 perf 的目标子树中。
- 同一镜像内 `--no-inline` 导出物理调用链；未知叶节点不继承调用者符号。
- 用户态采样不包含内核 CPU 和阻塞等待；未进行开销校准或重复稳定性检验，也未采集 py-spy。
- perf 聚合统计 SAMPLE=534、LOST 记录=0、LOST_SAMPLES 记录=0；record 日志报告 lost chunks=0。这些诊断不构成采集绝对无损的证明。
- 显示 0.00% 仅表示采样权重很小或未获得明显采样，不表示脚本未执行或实际 CPU 为零。
- perf lost/符号化警告原文保存在 profile.json 的 capture_quality 与 raw 日志；其 ROI 归属未知，不换算成周期权重。

原始证据：`analysis/hotspots/raw/opm-native-pilot-20261027T122621Z-9ac767af`；停止容器：`dfc39e528e26875c65287b1984eeefe9ca722b355b352e856b23de25e7a80974`。
