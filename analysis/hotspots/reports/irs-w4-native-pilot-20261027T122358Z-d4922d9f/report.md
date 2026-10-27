# IRS W-4 热点采集

当前 Agent 轨迹版，N=10，一轮。新旧对比另见汇总报告。

实际镜像：`sha256:4baef1363ba99a994e17e93fe6a32c904cdb5cb349487adfa2fb13ba42301499`。循环执行及业务验证成功。

正式循环 ROI：687 个样本，period 合计 29,384,587,935。

以下均以完整 ROI 的用户态 `cycles:u` period 为分母，未知项未从分母排除。不是整轮 user+sys CPU 时间占比。

## 脚本与进程

| 实际脚本/程序 | ROI 周期占比 |
|---|---:|
| `convert_pdf_to_images.py` | 45.92% |
| `fill_fillable_fields.py` | 38.51% |
| `verify_pdf_batch.py` | 12.07% |
| `pdftoppm` | 3.47% |
| `pdfinfo` | 0.02% |
| `unknown:pdftoppm` | 0.00% |
| `check_fillable_fields.py` | 0.00% |
| `write_pdf_batch_summary.py` | 0.00% |
| `run_batch.py` | 0.00% |
| `extract_form_field_info.py` | 0.00% |
| `run.py` | 0.00% |
| `unknown:python3` | 0.00% |
| `unknown:python` | 0.00% |

## 原生库

| DSO | ROI 周期占比 |
|---|---:|
| `/opt/python-3.12.3/lib/libpython3.12.so.1.0` | 43.01% |
| `/opt/document-bench/.venv/lib/python3.12/site-packages/PIL/_imaging.cpython-312-aarch64-linux-gnu.so` | 26.03% |
| `/usr/lib64/libz.so.1.2.13` | 22.50% |
| `/usr/lib/ld-linux-aarch64.so.1` | 2.84% |
| `/usr/lib64/libpoppler.so.133.0.0` | 2.41% |
| `/usr/lib64/libc.so.6` | 2.00% |
| `/usr/lib64/libfreetype.so.6.20.1` | 0.62% |
| `[vdso]` | 0.21% |
| `[unknown]` | 0.20% |
| `/opt/python-3.12.3/lib/python3.12/lib-dynload/_struct.cpython-312-aarch64-linux-gnu.so` | 0.20% |
| `/opt/python-3.12.3/lib/python3.12/lib-dynload/_posixsubprocess.cpython-312-aarch64-linux-gnu.so` | 0.00% |

## Top-20 物理叶函数

| DSO | 函数 | ROI 周期占比 |
|---|---|---:|
| `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 15.24% |
| `libz.so.1.2.13` | `longest_match` | 12.75% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleHorizontal_8bpc` | 12.29% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingZipEncode` | 6.88% |
| `libpython3.12.so.1.0` | `_Py_dict_lookup` | 5.58% |
| `libz.so.1.2.13` | `deflate_slow` | 4.84% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleVertical_8bpc` | 3.39% |
| `libpython3.12.so.1.0` | `gc_collect_main` | 2.86% |
| `libz.so.1.2.13` | `slide_hash` | 2.83% |
| `ld-linux-aarch64.so.1` | `_dl_tlsdesc_return` | 2.73% |
| `libpython3.12.so.1.0` | `insertdict` | 2.58% |
| `libpython3.12.so.1.0` | `PyUnicode_Decode` | 2.15% |
| `libpython3.12.so.1.0` | `_PyObject_GenericGetAttrWithDict` | 2.13% |
| `libpoppler.so.133.0.0` | `Splash::pipeRunAARGB8(SplashPipe*)` | 1.39% |
| `libz.so.1.2.13` | `inflate_fast` | 1.10% |
| `libpython3.12.so.1.0` | `deduce_unreachable` | 0.99% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `image_item` | 0.96% |
| `libc.so.6` | `sem_post@@GLIBC_2.34` | 0.90% |
| `libpython3.12.so.1.0` | `PyObject_GC_Del` | 0.79% |
| `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingZipDecode` | 0.78% |

## 带脚本上下文的 Top-20 函数

| 实际脚本/程序 | DSO | 函数 | ROI 周期占比 |
|---|---|---|---:|
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `longest_match` | 12.75% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleHorizontal_8bpc` | 12.29% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 9.33% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingZipEncode` | 6.88% |
| `verify_pdf_batch.py` | `libpython3.12.so.1.0` | `_PyEval_EvalFrameDefault` | 5.90% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `_Py_dict_lookup` | 5.19% |
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `deflate_slow` | 4.84% |
| `convert_pdf_to_images.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `ImagingResampleVertical_8bpc` | 3.39% |
| `convert_pdf_to_images.py` | `libz.so.1.2.13` | `slide_hash` | 2.83% |
| `fill_fillable_fields.py` | `ld-linux-aarch64.so.1` | `_dl_tlsdesc_return` | 2.73% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `insertdict` | 2.58% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `gc_collect_main` | 2.47% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `PyUnicode_Decode` | 2.15% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `_PyObject_GenericGetAttrWithDict` | 2.13% |
| `pdftoppm` | `libpoppler.so.133.0.0` | `Splash::pipeRunAARGB8(SplashPipe*)` | 1.39% |
| `verify_pdf_batch.py` | `libz.so.1.2.13` | `inflate_fast` | 1.10% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `deduce_unreachable` | 0.99% |
| `verify_pdf_batch.py` | `_imaging.cpython-312-aarch64-linux-gnu.so` | `image_item` | 0.96% |
| `fill_fillable_fields.py` | `libc.so.6` | `sem_post@@GLIBC_2.34` | 0.90% |
| `fill_fillable_fields.py` | `libpython3.12.so.1.0` | `PyObject_GC_Del` | 0.79% |

## 质量和边界

- 空栈 0.000%；未知叶 DSO 0.199%；未知叶符号 0.405%。这些类别可能重叠。
- 无法关联脚本的 period：0.003%；首次观察前 10 ms 内的推断归属：0.098%。身份来自 10 ms 名义间隔的 /proc 观察，并非精确 exec 事件。
- 完整栈导出与无栈计数导出按 PID/TID/纳秒时间/period/event 的多重集合逐样本核对；ROI 内外 period 守恒。
- 按 CLOCK_MONOTONIC 的实际 ROI 标记裁剪；循环外预检、归档和哈希不计入主表。采集器及 monitor 不在 perf 的目标子树中。
- 同一镜像内 `--no-inline` 导出物理调用链；未知叶节点不继承调用者符号。
- 用户态采样不包含内核 CPU 和阻塞等待；未进行开销校准或重复稳定性检验，也未采集 py-spy。
- perf 聚合统计 SAMPLE=734、LOST 记录=0、LOST_SAMPLES 记录=0；record 日志报告 lost chunks=0。这些诊断不构成采集绝对无损的证明。
- 显示 0.00% 仅表示采样权重很小或未获得明显采样，不表示脚本未执行或实际 CPU 为零。
- perf lost/符号化警告原文保存在 profile.json 的 capture_quality 与 raw 日志；其 ROI 归属未知，不换算成周期权重。

原始证据：`analysis/hotspots/raw/irs-w4-native-pilot-20261027T122358Z-d4922d9f`；停止容器：`38a7e5ee8e0de1930285d5747f53322cd1ec0482b40eccf280fd25d2f11e3756`。
