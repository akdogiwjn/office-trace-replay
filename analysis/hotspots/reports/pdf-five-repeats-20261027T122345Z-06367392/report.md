# PDF 五轮重复采样与热点统计

OPM、IRS W-4、SBA 1919 各独立运行五次，每次使用新容器、执行一轮并处理十份 PDF。使用同一镜像、cycles:u、49 Hz、DWARF 16384 字节、逻辑 CPU 0–7；监测进程绑定 CPU 9。
每次仅选取正式循环 ROI，合并原始 sample period 后重新计算占比；保留逐轮结果用于观察排名波动。

## 统计结论

三例五轮合并后的 Top-5 函数共有 5 个共同项：`ImagingResampleHorizontal_8bpc`、`ImagingZipEncode`、`_PyEval_EvalFrameDefault`、`deflate_slow`、`longest_match`。
各自 Top-5 累计占比为 opm 43.74%、irs_w4 51.65%、sba1919 48.40%。
五轮合并后，与 OPM 的 Top-10 共同函数数为 W-4 9 个、SBA 7 个。
逐轮 Top-10 仍存在排名波动；本批次合并结果更清楚地呈现了共同的解释器执行、压缩编码和图片处理热点。

| 数据集 | 成功重复数 | ROI 样本数合计 | 各轮 ROI 样本数 |
|---|---:|---:|---|
| opm | 5/5 | 2,736 | 544, 563, 566, 525, 538 |
| irs_w4 | 5/5 | 3,443 | 687, 667, 664, 720, 705 |
| sba1919 | 5/5 | 4,275 | 868, 878, 814, 839, 876 |

## 合并后的主要脚本／进程

| 脚本／程序 | OPM | W-4 | SBA 1919 |
|---|---:|---:|---:|
| `convert_pdf_to_images.py` | 38.85% | 44.17% | 44.92% |
| `fill_fillable_fields.py` | 38.44% | 36.41% | 29.00% |
| `pdftoppm` | 8.03% | 6.89% | 14.57% |
| `verify_pdf_batch.py` | 12.26% | 12.40% | 10.64% |
| `check_fillable_fields.py` | 2.16% | 0.00% | 0.61% |

## 合并后的主要库

| 库 | OPM | W-4 | SBA 1919 |
|---|---:|---:|---:|
| `libpython` | 50.41% | 45.21% | 37.28% |
| `zlib` | 25.18% | 23.75% | 23.89% |
| `Pillow` | 14.61% | 21.71% | 21.22% |
| `Poppler` | 6.23% | 3.47% | 6.93% |
| `FreeType` | 1.02% | 2.25% | 6.27% |
| `libc` | 1.86% | 2.55% | 3.74% |
| `ld` | 0.18% | 0.73% | 0.35% |

## 合并后的 Top-10 函数并集

| 库／物理叶函数 | OPM | W-4 | SBA 1919 |
|---|---:|---:|---:|
| `libpython / _PyEval_EvalFrameDefault` | 16.52% | 18.57% | 15.02% |
| `zlib / longest_match` | 10.07% | 11.14% | 12.96% |
| `Pillow / ImagingResampleHorizontal_8bpc` | 5.41% | 8.18% | 8.51% |
| `Pillow / ImagingZipEncode` | 4.70% | 7.54% | 5.78% |
| `zlib / deflate_slow` | 7.04% | 6.22% | 6.12% |
| `Pillow / ImagingResampleVertical_8bpc` | 2.52% | 3.26% | 4.88% |
| `libpython / deduce_unreachable` | 3.42% | 1.56% | 1.47% |
| `zlib / slide_hash` | 2.74% | 3.07% | 2.82% |
| `libpython / gc_collect_main` | 2.92% | 1.81% | 1.52% |
| `Poppler / Splash::pipeRunAARGB8(SplashPipe*)` | 1.08% | 0.95% | 2.55% |
| `zlib / inflate_fast` | 2.47% | 1.06% | 0.46% |
| `Poppler / Splash::compositeBackground(unsigned char const*)` | 2.44% | 0.79% | 1.96% |
| `libpython / _Py_dict_lookup` | 0.47% | 2.44% | 1.30% |
| `FreeType / gray_render_line` | 0.11% | 0.36% | 1.93% |

## 五轮合并共同热点

| 对照 OPM | Top-10 共同函数数 | OPM Top-10 在目标 Top-20 出现 |
|---|---:|---:|
| irs_w4 | 9/10 | 10/10 |
| sba1919 | 7/10 | 9/10 |

## 热点集中度

| 数据集 | 各自 Top-5 合计 | 各自 Top-10 合计 | 三例共同 Top-10 交集函数合计 |
|---|---:|---:|---:|
| opm | 43.74% | 57.81% | 49.00% |
| irs_w4 | 51.65% | 63.80% | 57.99% |
| sba1919 | 48.40% | 62.55% | 56.10% |

三例 Top-10 交集有 7 个函数；交集与各自 Top-5 是不同集合。

## 逐轮排名波动

### opm

五轮两两比较的 Top-10 共同函数数范围为 5–7。

| 合并排名前十的函数 | 五轮合并占比 | 逐轮占比范围 | 进入逐轮 Top-10 的次数 |
|---|---:|---:|---:|
| `_PyEval_EvalFrameDefault` | 16.52% | 12.56%–20.60% | 5/5 |
| `longest_match` | 10.07% | 4.05%–13.49% | 5/5 |
| `deflate_slow` | 7.04% | 3.82%–9.24% | 4/5 |
| `ImagingResampleHorizontal_8bpc` | 5.41% | 4.81%–6.91% | 5/5 |
| `ImagingZipEncode` | 4.70% | 2.42%–8.29% | 5/5 |
| `deduce_unreachable` | 3.42% | 0.92%–7.80% | 2/5 |
| `gc_collect_main` | 2.92% | 1.10%–9.50% | 1/5 |
| `slide_hash` | 2.74% | 0.32%–4.88% | 4/5 |
| `ImagingResampleVertical_8bpc` | 2.52% | 0.27%–4.98% | 2/5 |
| `inflate_fast` | 2.47% | 1.06%–4.50% | 2/5 |

### irs_w4

五轮两两比较的 Top-10 共同函数数范围为 5–8。

| 合并排名前十的函数 | 五轮合并占比 | 逐轮占比范围 | 进入逐轮 Top-10 的次数 |
|---|---:|---:|---:|
| `_PyEval_EvalFrameDefault` | 18.57% | 15.18%–24.08% | 5/5 |
| `longest_match` | 11.14% | 8.01%–13.03% | 5/5 |
| `ImagingResampleHorizontal_8bpc` | 8.18% | 4.92%–12.29% | 5/5 |
| `ImagingZipEncode` | 7.54% | 4.77%–12.08% | 5/5 |
| `deflate_slow` | 6.22% | 4.84%–8.50% | 5/5 |
| `ImagingResampleVertical_8bpc` | 3.26% | 1.45%–5.00% | 4/5 |
| `slide_hash` | 3.07% | 0.94%–6.67% | 4/5 |
| `_Py_dict_lookup` | 2.44% | 0.89%–5.58% | 2/5 |
| `gc_collect_main` | 1.81% | 1.00%–3.05% | 2/5 |
| `deduce_unreachable` | 1.56% | 0.18%–4.48% | 1/5 |

### sba1919

五轮两两比较的 Top-10 共同函数数范围为 6–8。

| 合并排名前十的函数 | 五轮合并占比 | 逐轮占比范围 | 进入逐轮 Top-10 的次数 |
|---|---:|---:|---:|
| `_PyEval_EvalFrameDefault` | 15.02% | 10.89%–18.13% | 5/5 |
| `longest_match` | 12.96% | 9.27%–16.81% | 5/5 |
| `ImagingResampleHorizontal_8bpc` | 8.51% | 7.70%–9.50% | 5/5 |
| `deflate_slow` | 6.12% | 4.62%–8.41% | 5/5 |
| `ImagingZipEncode` | 5.78% | 4.60%–7.68% | 5/5 |
| `ImagingResampleVertical_8bpc` | 4.88% | 4.24%–5.48% | 5/5 |
| `slide_hash` | 2.82% | 1.35%–3.83% | 3/5 |
| `Splash::pipeRunAARGB8(SplashPipe*)` | 2.55% | 2.04%–3.78% | 4/5 |
| `Splash::compositeBackground(unsigned char const*)` | 1.96% | 0.49%–4.48% | 2/5 |
| `gray_render_line` | 1.93% | 1.06%–3.82% | 1/5 |

## 采集记录

本次为预先固定的五次重复，没有根据结果选择或删除轮次。未知项保留分母；损失诊断保留原生单位。详细 period、逐轮函数列表、来源及哈希见 comparison.json。本报告仅采用五轮统计。

- opm r1：LOST=0，LOST_SAMPLES=0，lost chunks=0。
- opm r2：LOST=0，LOST_SAMPLES=0，lost chunks=0。
- opm r3：LOST=0，LOST_SAMPLES=0，lost chunks=0。
- opm r4：LOST=0，LOST_SAMPLES=0，lost chunks=0。
- opm r5：LOST=0，LOST_SAMPLES=0，lost chunks=0。
- irs_w4 r1：LOST=0，LOST_SAMPLES=0，lost chunks=0。
- irs_w4 r2：LOST=0，LOST_SAMPLES=0，lost chunks=0。
- irs_w4 r3：LOST=0，LOST_SAMPLES=0，lost chunks=0。
- irs_w4 r4：LOST=0，LOST_SAMPLES=0，lost chunks=0。
- irs_w4 r5：LOST=0，LOST_SAMPLES=0，lost chunks=0。
- sba1919 r1：LOST=0，LOST_SAMPLES=0，lost chunks=0。
- sba1919 r2：LOST=0，LOST_SAMPLES=0，lost chunks=0。
- sba1919 r3：LOST=0，LOST_SAMPLES=0，lost chunks=0。
- sba1919 r4：LOST=0，LOST_SAMPLES=0，lost chunks=0。
- sba1919 r5：LOST=0，LOST_SAMPLES=0，lost chunks=0。
