# 扩大规模后的热点函数与旧 OPM＋TLC 覆盖权重

## 主要结果

Excel 014 放大后旧函数覆盖权重明显提高；PPT 021 放大后仅小幅提高，图像滤波、JPEG 编码和部分页面绘制函数仍是具体缺口。

旧参考使用 OPM＋TLC 的完整已解析函数并集（含低频函数），按库文件名＋完整物理叶函数名精确匹配。以下百分比均以目标完整 workflow ROI 的 cycles:u 样本 period 为分母，不是总 CPU 秒。未知部分不算未覆盖。

| 任务 | 旧参考已见 | 已解析但旧参考未见 | 未解析 | Top-10 占完整 ROI | Top-10 已见函数数 |
|---|---:|---:|---:|---:|---:|
| 014 | 66.17% | 33.15% | 0.68% | 46.55% | 8/10 |
| 014-n1000 | 88.01% | 10.35% | 1.63% | 82.20% | 9/10 |
| 014-n10000 | 91.82% | 7.12% | 1.05% | 85.05% | 9/10 |
| 021 | 46.59% | 51.34% | 2.07% | 38.82% | 5/10 |
| 021-g5 | 49.65% | 48.76% | 1.59% | 49.79% | 4/10 |
| 021-g10 | 50.44% | 47.45% | 2.11% | 48.74% | 5/10 |

## Excel：改善明显，但主要来自渲染与 PNG 压缩的权重上升

| 任务 | pdftoppm 占 ROI | longest_match 占 ROI | 旧参考未见 Python 函数合计 | 旧参考未见 PNG 函数合计 |
|---|---:|---:|---:|---:|
| 014 | 39.47% | 22.52% | 8.22% | 7.57% |
| 014-n1000 | 74.53% | 62.38% | 1.48% | 5.04% |
| 014-n10000 | 76.91% | 65.42% | 0.67% | 4.12% |

1000/10000 行分别生成 81/753 页 PDF 并渲染 PNG。大档中最长匹配压缩函数主要由 pdftoppm 执行；不能将整段压缩权重解释为 XLSX 保存。较低覆盖的 Python 与 LibreOffice 框架函数占比下降，方向与部分固定成本被摊薄一致；但父任务到变体也有参数化与合成输入变化，不能将全部差异归因于规模。

## PPT：放大不能消除图片处理实现的缺口

| 任务 | ImageMagick 未见函数 | LibreOffice VCL 图像未见函数 | JPEG 未见函数 | Poppler 未见函数 | Python 未见函数 |
|---|---:|---:|---:|---:|---:|
| 021 | 10.59% | 10.26% | 5.20% | 6.80% | 4.77% |
| 021-g5 | 12.82% | 12.84% | 5.33% | 7.91% | 2.41% |
| 021-g10 | 11.51% | 8.24% | 7.45% | 7.92% | 1.76% |

这里是未匹配函数权重，不是整库权重。PPT 继续执行转 PDF、JPEG 渲染与联系表拼图。ImageMagick 的横纵向滤波、libjpeg 编码和 LibreOffice 位图缩放随页面处理持续发生，不是单靠小输入或初始化开销能解释的。旧例已有页面渲染和 Pillow 图像处理，但未观察到这些具体工具／函数，不能用操作名称相近代替函数匹配。

## 大档主要未匹配函数


### 014-n10000

| 库 | 函数 | 占完整 ROI |
|---|---|---:|
| libpng16.so.16.40.0 | `png_write_find_filter` | 4.12% |
| libsclo.so | `ScHorizontalAttrIterator::InitForNextRow(bool)` | 0.12% |
| libuno_sal.so.3 | `rtl_math_approxEqual` | 0.10% |
| libpoppler.so.133.0.0 | `SplashXPathScanner::renderAALine(SplashBitmap*, int*, int*, int, bool) const` | 0.08% |
| libpoppler.so.133.0.0 | `SplashXPathScanner::computeIntersections(SplashXPath const&)` | 0.08% |
| libvcllo.so | `rtl_uString_acquire@plt` | 0.07% |
| libpython3.12.so.1.0 | `slot_tp_richcompare` | 0.05% |
| libpython3.12.so.1.0 | `PyDict_MergeFromSeq2` | 0.05% |

### 021-g10

| 库 | 函数 | 占完整 ROI |
|---|---|---:|
| libMagickCore-7.Q16HDRI.so.10.0.2 | `VerticalFilter._omp_fn.0` | 7.62% |
| libMagickCore-7.Q16HDRI.so.10.0.2 | `HorizontalFilter._omp_fn.0` | 3.38% |
| libjpeg.so.62.4.0 | `encode_mcu_gather` | 3.16% |
| libvcllo.so | `vcl::(anonymous namespace)::ImplScaleConvolutionHor(Bitmap const&, Bitmap&, double const&, vcl::Kernel const&)` | 2.77% |
| libvcllo.so | `vcl::(anonymous namespace)::ImplScaleConvolutionVer(Bitmap const&, Bitmap&, double const&, vcl::Kernel const&)` | 1.91% |
| libpoppler.so.133.0.0 | `expandRow(unsigned char*, unsigned char*, int, int, int)` | 1.33% |
| libpoppler.so.133.0.0 | `Splash::scaleImageYupXupBilinear(bool (*)(void*, unsigned char*, unsigned char*), void*, SplashColorMode, int, bool, int, int, int, int, SplashBitmap*)` | 1.26% |
| libpoppler.so.133.0.0 | `Splash::scaleImageYdownXdown(bool (*)(void*, unsigned char*, unsigned char*), void*, SplashColorMode, int, bool, int, int, int, int, SplashBitmap*)` | 1.25% |

## 判断

1. Excel 014：大档旧函数覆盖达到约 92%，本次结果增强了旧两例对这一发布工作流基础计算的代表性证据。保留约 7% 的已解析未匹配函数，最明显的是 PNG 滤波函数。
2. PPT 021：大档仍有约 47% 已解析周期无法在旧清单中匹配，约 50% 能匹配。规模扩大没有消除覆盖缺口，PPT 图形／图片发布任务仍有补充价值。
3. 两类任务不能合并得出“放大规模后缺口都消失”的结论。本批主要用于观察函数权重变化；单次规模采集与原任务十轮批次不支持稳定性或单一因素因果结论。

所有完整函数清单、未见函数分组、脚本上下文及来源哈希见 comparison.json。
