## 十、规模复测与补充用例选择

本节为 7.3 的补充数据。第九节的十二项原始配置及其 Top-20 集合计算仍保留原批次口径；本节加入八项合成规模变体，重新按明确操作热点选型。原始十二项、规模变体、独立采集次数分别记录。

### 10.1 输入规模、重复次数与完整周期分区

旧 OPM／TLC 是各五次独立重复的函数清单并集；原始 DocOps 十二项各一次采集内十轮回放。八项规模变体各模式一次独立采集；003-u100／037-u5 内含三轮，其余一轮。perf 与 DevKit 分开运行。覆盖分母是各目标 workflow ROI 的 cycles:u period，不是 CPU 秒。

| 配置 | ROI period | ROI 样本 | 回放轮数 | 旧函数已见 | 已解析未见 | 未解析 |
|---|---|---|---|---|---|---|
| 014 | 63489076592 | 109567 | 10 | 66.17% | 33.15% | 0.68% |
| 014-n1000 | 93827635494 | 7990 | 1 | 88.01% | 10.35% | 1.63% |
| 014-n10000 | 907487668199 | 22587 | 1 | 91.82% | 7.12% | 1.05% |
| 021 | 115775254364 | 572915 | 10 | 46.59% | 51.34% | 2.07% |
| 021-g5 | 44958631720 | 274598 | 1 | 49.65% | 48.76% | 1.59% |
| 021-g10 | 90902921214 | 528158 | 1 | 50.44% | 47.45% | 2.11% |
| 003 | 53253612236 | 3280 | 10 | 68.65% | 28.47% | 2.88% |
| 003-u100 | 297102713189 | 5595 | 3 | 74.59% | 24.34% | 1.07% |
| 003-u500 | 479650485764 | 8312 | 1 | 71.58% | 26.94% | 1.48% |
| 037 | 56450928986 | 5084 | 10 | 72.77% | 27.18% | 0.05% |
| 037-u5 | 66582428915 | 1162 | 3 | 83.39% | 16.38% | 0.23% |
| 037-u20 | 87089312211 | 1480 | 1 | 86.72% | 13.28% | <0.01% |

Word 100／500 单元实际排版 104／504 页；PDF 037 为 25／100 页；Excel 两档输出 81／753 页 PDF 与 PNG；PPT 两档 40／80 页并生成 5／10 张联系表。规模变体为合成业务内容和参数化脚本，不标为新增 Agent 轨迹。Word XML 校验器只转小写一次的修复也保留在身份记录中，不能将其效果全部当作规模作用。

### 10.2 补例目标、门槛与精确最少集合

目标：在二十个配置中至少一次达到完整 ROI 0.5%，旧 OPM＋TLC 未见，软件组属于 PNG／JPEG／ImageMagick／Poppler／LibreOffice VCL／LibreOffice OOXML 的已解析叶函数。六组对应已定位的图片、页面、对象操作。其他运行时、文本、XML、公共框架及未知权重仍在完整分区中保留。

目标共 34 个去重身份。候选为原十二项任务的完整函数清单，不限制候选中的函数必须达到 0.5%。枚举全部子集，最少三例，唯一组合为 013、021、029。若允许八个合成规模变体也作为候选，最少仍为三例，但有以下并列组合：

| 组合 |
|---|
| pdfwf005、029、021-g5 |
| 013、021、029 |
| 013、029、021-g5 |

**34 个目标的完整库名和函数身份如下。** 表内函数仅显示时省略参数；selection.json 保留完整符号。

| 软件组 | 库文件名 | 完整身份的函数名（显示简写） | 达到门槛的配置／权重 |
|---|---|---|---|
| ImageMagick | libMagickCore-7.Q16HDRI.so.10.0.2 | `CompositeOverImage._omp_fn.0` | pdfwf005 0.58%；013 0.77%；021 0.79% |
| ImageMagick | libMagickCore-7.Q16HDRI.so.10.0.2 | `HorizontalFilter._omp_fn.0` | pdfwf005 12.59%；013 8.05%；021 2.69%；021-g5 2.70%；021-g10 3.38% |
| ImageMagick | libMagickCore-7.Q16HDRI.so.10.0.2 | `ImportRGBQuantum` | pdfwf005 0.62% |
| ImageMagick | libMagickCore-7.Q16HDRI.so.10.0.2 | `ReadPixelCachePixels` | 021-g5 1.10% |
| ImageMagick | libMagickCore-7.Q16HDRI.so.10.0.2 | `VerticalFilter._omp_fn.0` | pdfwf005 11.46%；013 3.52%；021 6.96%；021-g5 8.51%；021-g10 7.62% |
| JPEG | libjpeg.so.62.4.0 | `decode_mcu_AC_refine` | 021 1.12%；021-g5 0.51% |
| JPEG | libjpeg.so.62.4.0 | `encode_mcu_gather` | 021-g10 3.16% |
| JPEG | libjpeg.so.62.4.0 | `jsimd_fdct_islow_neon` | 021-g5 0.51% |
| JPEG | libjpeg.so.62.4.0 | `jsimd_huff_encode_one_block_neon` | 026 0.79%；021-g10 0.50% |
| JPEG | libjpeg.so.62.4.0 | `jsimd_rgb_ycc_convert_neon.localalias` | 026 0.50% |
| JPEG | libjpeg.so.62.4.0 | `quantize` | 021-g5 1.36% |
| JPEG | libjpeg.so.62.4.0 | `rgb_ycc_convert` | 021 0.97% |
| LibreOffice·OOXML | libooxlo.so | `oox::PropertyMap::fillSequences` | 029 1.85% |
| LibreOffice·OOXML | libooxlo.so | `oox::drawingml::table::applyTableStylePart` | 029 2.00% |
| LibreOffice·OOXML | libooxlo.so | `std::array<oox::drawingml::TextParagraphProperties, 9ul>::~array` | 029 0.53% |
| PNG | libpng16.so.16.40.0 | `png_read_filter_row_up` | pdfwf005 1.03% |
| PNG | libpng16.so.16.40.0 | `png_write_find_filter` | 031 8.68%；037 10.27%；pdfwf005 10.57%；013 8.38%；014 7.57%；016 1.15%；001 5.34%；003 9.05%；009 19.00%；014-n1000 5.04%；014-n10000 4.12%；003-u100 20.45%；003-u500 22.10%；037-u5 12.24%；037-u20 11.22% |
| Poppler | libpoppler.so.133.0.0 | `FlateStream::compHuffmanCodes` | 026 0.74% |
| Poppler | libpoppler.so.133.0.0 | `FlateStream::readSome` | 021 0.61%；021-g5 0.77% |
| Poppler | libpoppler.so.133.0.0 | `Splash::composite` | 021-g5 0.62% |
| Poppler | libpoppler.so.133.0.0 | `Splash::scaleImageYdownXdown` | 021 1.37%；026 1.01%；029 0.54%；021-g5 0.90%；021-g10 1.25% |
| Poppler | libpoppler.so.133.0.0 | `Splash::scaleImageYupXupBilinear` | 021 0.90%；021-g5 0.77%；021-g10 1.26% |
| Poppler | libpoppler.so.133.0.0 | `SplashBitmap::getPixel` | 026 0.75%；021-g5 1.29%；021-g10 0.75% |
| Poppler | libpoppler.so.133.0.0 | `SplashClip::testClipPaths` | 026 1.20% |
| Poppler | libpoppler.so.133.0.0 | `SplashXPathScanner::renderAALine` | 014 1.05% |
| Poppler | libpoppler.so.133.0.0 | `expandRow` | 021 1.52%；026 1.29%；021-g5 1.02%；021-g10 1.33% |
| LibreOffice·VCL | libvcllo.so | `BitmapReadAccess::GetPixelForN24BitTcBgr` | 021 0.61%；021-g5 2.05% |
| LibreOffice·VCL | libvcllo.so | `BitmapReadAccess::SetPixelForN24BitTcBgr` | 021 1.61%；021-g5 4.17% |
| LibreOffice·VCL | libvcllo.so | `BitmapReadAccess::SetPixelForN8BitPal` | 021 0.66%；021-g5 0.54%；021-g10 0.57% |
| LibreOffice·VCL | libvcllo.so | `vcl::ImplScaleConvolutionHor` | 021 1.49%；021-g5 2.05%；021-g10 2.77% |
| LibreOffice·VCL | libvcllo.so | `vcl::ImplScaleConvolutionVer` | 021 3.89%；021-g5 1.67%；021-g10 1.91% |
| LibreOffice·VCL | libvcllo.so | `stackBlurHorizontal<SumFunction8>` | 021 0.59%；026 0.69%；029 0.61%；021-g5 0.68%；021-g10 0.76% |
| LibreOffice·VCL | libvcllo.so | `stackBlurVertical<SumFunction8>` | 021 0.74%；026 0.88%；029 0.76%；021-g5 0.90%；021-g10 0.95% |
| PNG | png.so | `ReadOnePNGImage` | pdfwf005 0.94% |

### 10.3 加例后的完整分区与删例检查

selected_as_reference=True 的三项匹配自身，不作为独立验证。021-g5／g10 与入选原始 021 同父任务，属于相关规模配置。所有目标未知 period 不变。

| 目标 | 选为参考 | 仅旧例：未匹配 | 旧例＋三例：未匹配 | 未解析 |
|---|---|---|---|---|
| 031 | False | 20.85% | 1.54% | <0.01% |
| 037 | False | 27.18% | 2.96% | 0.05% |
| pdfwf005 | False | 54.41% | 2.93% | 0.18% |
| 013 | True | 40.33% | 0.00% | 0.51% |
| 014 | False | 33.15% | 8.75% | 0.68% |
| 016 | False | 43.35% | 14.69% | 0.40% |
| 001 | False | 25.57% | 8.29% | 2.49% |
| 003 | False | 28.47% | 10.45% | 2.88% |
| 009 | False | 32.45% | 6.38% | 2.54% |
| 021 | True | 51.34% | 0.00% | 2.07% |
| 026 | False | 37.59% | 10.09% | 3.02% |
| 029 | True | 42.87% | 0.00% | 1.63% |
| 014-n1000 | False | 10.35% | 3.20% | 1.63% |
| 014-n10000 | False | 7.12% | 2.32% | 1.05% |
| 021-g5 | False | 48.76% | 6.03% | 1.59% |
| 021-g10 | False | 47.45% | 7.72% | 2.11% |
| 003-u100 | False | 24.34% | 1.81% | 1.07% |
| 003-u500 | False | 26.94% | 1.94% | 1.48% |
| 037-u5 | False | 16.38% | 1.59% | 0.23% |
| 037-u20 | False | 13.28% | 1.26% | <0.01% |

**删去 013：保留 021＋029，目标剩 5 个未匹配。**

| 软件组 | 库 | 未匹配函数 |
|---|---|---|
| ImageMagick | libMagickCore-7.Q16HDRI.so.10.0.2 | `ImportRGBQuantum` |
| ImageMagick | libMagickCore-7.Q16HDRI.so.10.0.2 | `ReadPixelCachePixels` |
| PNG | libpng16.so.16.40.0 | `png_read_filter_row_up` |
| PNG | libpng16.so.16.40.0 | `png_write_find_filter` |
| PNG | png.so | `ReadOnePNGImage` |

**删去 021：保留 013＋029，目标剩 11 个未匹配。**

| 软件组 | 库 | 未匹配函数 |
|---|---|---|
| JPEG | libjpeg.so.62.4.0 | `decode_mcu_AC_refine` |
| JPEG | libjpeg.so.62.4.0 | `encode_mcu_gather` |
| JPEG | libjpeg.so.62.4.0 | `jsimd_fdct_islow_neon` |
| JPEG | libjpeg.so.62.4.0 | `jsimd_huff_encode_one_block_neon` |
| JPEG | libjpeg.so.62.4.0 | `jsimd_rgb_ycc_convert_neon.localalias` |
| JPEG | libjpeg.so.62.4.0 | `quantize` |
| JPEG | libjpeg.so.62.4.0 | `rgb_ycc_convert` |
| Poppler | libpoppler.so.133.0.0 | `FlateStream::compHuffmanCodes` |
| Poppler | libpoppler.so.133.0.0 | `Splash::scaleImageYupXupBilinear` |
| Poppler | libpoppler.so.133.0.0 | `SplashClip::testClipPaths` |
| Poppler | libpoppler.so.133.0.0 | `expandRow` |

**删去 029：保留 013＋021，目标剩 1 个未匹配。**

| 软件组 | 库 | 未匹配函数 |
|---|---|---|
| LibreOffice·OOXML | libooxlo.so | `oox::drawingml::table::applyTableStylePart` |

**如果不区分操作与运行支撑：** 全部二十个配置中达到 0.5% 的旧例未见函数共 93 个。允许全部配置作为候选，严格覆盖该集合最少需 8 个配置，组合如下；它与正文“34 个可定位操作热点”的目标不同。

| 全部热点最少组合 |
|---|
| 013、014、016、001、003、026、029、021-g10 |

原十二项候选无法覆盖全部 93 个身份，缺少 `libbasegfxlo.so / basegfx::B2DPolygon::getB2DRange() const`。不将新增变体的函数身份倒填成原任务已经执行。

### 10.4 Topdown 与采集质量

下面规模变体取 DevKit Report-ALL，原任务取已保存批次累计值。四个顶层 Bound 与子项分开理解。

| 配置 | IPC | Bad Spec | Frontend | Backend | Retiring | Core | Memory | Fetch Latency | Fetch BW |
|---|---|---|---|---|---|---|---|---|---|
| 014 | 0.84 | 3.47 | 18.41 | 64.09 | 14.04 | 45.29 | 18.80 | 16.29 | 2.12 |
| 014-n1000 | 1.07 | 2.08 | 11.09 | 69.01 | 17.82 | 54.97 | 14.04 | 9.69 | 1.40 |
| 014-n10000 | 1.07 | 2.05 | 9.38 | 70.77 | 17.79 | 56.24 | 14.53 | 8.18 | 1.19 |
| 021 | 1.15 | 2.49 | 16.27 | 62.09 | 19.15 | 48.81 | 13.28 | 13.50 | 2.77 |
| 021-g5 | 1.36 | 2.07 | 16.99 | 58.30 | 22.65 | 47.65 | 10.65 | 14.14 | 2.85 |
| 021-g10 | 1.36 | 2.34 | 15.87 | 59.13 | 22.66 | 48.90 | 10.23 | 12.85 | 3.02 |
| 003 | 0.94 | 3.21 | 15.18 | 65.89 | 15.73 | 49.72 | 16.17 | 13.03 | 2.14 |
| 003-u100 | 1.82 | 1.60 | 8.27 | 59.82 | 30.30 | 55.08 | 4.75 | 6.33 | 1.94 |
| 003-u500 | 1.86 | 1.45 | 7.47 | 60.10 | 30.99 | 55.72 | 4.38 | 5.66 | 1.81 |
| 037 | 0.99 | 2.58 | 10.28 | 70.65 | 16.49 | 54.05 | 16.59 | 9.17 | 1.12 |
| 037-u5 | 1.12 | 1.75 | 5.34 | 74.28 | 18.63 | 59.44 | 14.84 | 4.49 | 0.86 |
| 037-u20 | 1.15 | 1.74 | 6.22 | 72.85 | 19.19 | 59.19 | 13.65 | 5.21 | 1.01 |

DevKit 统计 CPU 0–7 的包络，控制器位于 CPU 9，含初始读数、步间、轮间及尾部间隙；没有精确 PID／ROI 事件裁剪。perf 采用 workflow 区间并集，二者分母不同。全层级 58 节点及原始 PMU 事件另有保存；带 `<not counted>` 的依赖未证明有效时，不填零加入相似度。

Word／PDF 已使用 build-id 匹配符号离线恢复，原样本数、period、DSO 权重不变；少量 Word lxml 未解析权重保留。Excel／PPT 的原丢样记录保留，未推算丢失 period 或补样。PDF “每个分配 CPU 的平均样本率”约 6/s 不等于任务只有 6Hz：两档总样本／workflow 秒约 47.7／48.1，与请求 49Hz 接近。

### 10.5 证据与离线重算入口

- [统一规模分析](../analysis/docops/processed/all-format-scaling-20261106/analysis.md)／[机器结果](../analysis/docops/processed/all-format-scaling-20261106/comparison.json)。
- [补例选择与完整身份](../analysis/docops/processed/scaling-selection-20261106/selection.json)／[构建绑定](../analysis/docops/processed/scaling-selection-20261106/analysis-build.json)。
- Excel／PPT：`results/docops/scaling-performance-20261105T114539Z/`，修正提取 `scaling-performance-recheck-20261105T124311Z/`，符号恢复 `scaling-symbol-enrich-20261105T132725Z/`。
- Word／PDF：`results/docops/scaling-word-pdf-performance-20261105T170501Z-3865aae0/`。

```bash
python3 -B analysis/docops/scaling_report_sections.py --build
python3 -B analysis/docops/operation_comparison.py --update --publish
```

两条命令只读取既有测量与派生数据，重建 Markdown 和来源绑定，不运行 workload、采集器或 HTML 生成器。
