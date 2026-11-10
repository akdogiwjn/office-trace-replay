## 九、扩展任务操作：十二项 DocOps 完整记录

本节为后续扩展实验，原有七例五次数据与前八节保持不变。本节以原始 OPM、TLC 为对照，采用统一 openEuler 环境下的新十二项 perf 与 DevKit；旧 Debian 首批仅作历史记录，不进入本节数值。

### 9.1 样本与冻结执行链

| 任务 | 格式／业务 | 采用的来源 run | 最终有效链 | 历史内容 reward |
|---|---|---|---|---|
| 031 | PDF／听证材料包扁平化发布 | 09-pdf-031-20261103T105309Z | build_public_packet.py；PDF 渲染；validate_public_packet.py | 0 |
| 037 | PDF／公交绕行材料修复 | 10-pdf-037-20261103T105547Z | build_bus_detour_packet.py；PDF 渲染；validate_bus_detour_packet.py | 0 |
| pdfwf005 | PDF／结算材料包重建 | 11-pdf-pdfwf005-20261103T105800Z | rebuild_closeout_binder.py；PDF 检查；图片／拼图／诊断 | 1 |
| 013 | Excel／采购投标评审发布 | xlsx013-rerun-20261103T112157Z | build_public_bid_workbook.py；recalc.py；verify_public_bid_workbook.py；PDF／拼图 | 0 |
| 014 | Excel／灾害补助公开发布 | 04-xlsx-014-20261103T103608Z | build_disaster_release_v1.py；recalc.py；finalize_disaster_release_ooxml_v3.py；validate_disaster_release_v1.py／渲染 | 1 |
| 016 | Excel／预测模型情景级联 | 05-xlsx-016-20261103T103856Z | build_forecast_dashboard_v1.py；recalc.py；测试副本切换情景并重算 | 0 |
| 001 | Word／受控文档发布修复 | word001-full-20261103T084219Z | create_packet.py；render_docx.py；结构与渲染检查 | 1 |
| 003 | Word／公开记录元数据清理 | 01-docx-003-20261103T091000Z | build_public_packet.py；audit_public_packet.py；render_docx.py | 0 |
| 009 | Word／事件手册发布 | 02-docx-009-20261103T092824Z | build_incident_manual_publication.py；render_docx.py；validate_incident_manual_publication.py | 1 |
| 021 | PPT／庇护所无障碍整改 | 06-pptx-021-20261103T104204Z | build_public_shelter_briefing.py；validate_public_shelter_briefing.py；soffice.py／图片／拼图 | 0 |
| 026 | PPT／气候披露图表重建 | 07-pptx-026-20261103T104652Z | build_climate_disclosure.py；转 PDF／图片；qa_climate_disclosure.py | 0 |
| 029 | PPT／季度业务回顾发布 | 08-pptx-029-20261103T104925Z | build_release_deck.py；validate_release_deck.py；转 PDF／图片 | 0 |

来源判定保持原样，缺失 CTRF、summary-only 及脚本关联推断等来源边界保留在 recipe／机器结果中；回放或采集成功不升级历史内容判定。各任务采用独立冻结脚本；相同脚本名不表示共享同一个业务实现。

### 9.2 环境、窗口和采集方法

原 OPM／TLC 的五次结果绑定镜像 `sha256:4baef1363ba99a994e17e93fe6a32c904cdb5cb349487adfa2fb13ba42301499`；十二项 DocOps 绑定其派生镜像 `sha256:57483856a27942ffd4aef853950ca66b00c12b0787aae6c1dac74371d03e6164`。Python 3.12.3、openpyxl 3.1.5、LibreOffice 25.8.7.3、Poppler 23.12.0、perf 6.6.0-145.3.23.154 与 DevKit 26.0.RC1。DocOps 增加 python-docx 1.2.0、python-pptx 1.0.2、lxml 6.1.2、fontTools 4.68.0、ReportLab 5.0.1、ImageMagick 7.1.2.9 等所需依赖。

perf 按回放入口及其后代采样，`cycles:u`、49 Hz、DWARF 16384、CLOCK_MONOTONIC；同镜像导出物理栈并加载精确 build-id 调试文件。每项原有一次采集、十轮回放；补符号只离线重解析，样本键、叶地址、DSO、进程权重、ROI 分母及原文件哈希已核对不变。
DocOps perf 仅筛选 workflow 步骤区间并集，排除 dispatcher；原七例的循环 ROI 包含 reset。两者都包含各自任务的原有检查，但检查内容和输入规模不相同。未知项始终保留完整周期分母。
DevKit 单独运行，按宿主 CPU 0–7 计数，业务绑 0–7，控制／监测／准备／归档绑 CPU 9。当前 CLI 最小 interval 为 1 秒，采集整份十轮批次，记录实际编号报告和 ALL。完整包络保留就绪、间隙与停止边界，可能包含对应 CPU 上其他宿主活动；不当作精确进程过滤。
硬件沿用 MIDR `0x00000000480fd020` 平台；DevKit 型号横幅仍显示 unknown，采用既有硬件核验与固定工具输出口径。经验公式复算、未计数事件和打印差异保留，未将其冒称完整的官方 HIP09 语义确认。

```bash
perf record -e cycles:u -F 49 -k mono --call-graph dwarf,16384 -- <测量包装入口>
perf script --no-inline --ns -F +pid -i /original/perf.data
devkit tuner top-down -c 0-7 -L 0 -i 1 -l 0
```

Topdown 四顶层总变差＝0.5 × Σ|新指标−基准指标|，指标单位为百分点；IPC 相对变化＝100 × (新 IPC／基准 IPC−1)。子层 Core／Memory、Fetch Latency／Bandwidth 分别展示，避免父子分类重复加权。余弦为辅助；本节不跨不同 idle 窗口计算混合单位十维距离。函数 Jaccard 使用 DSO 文件名＋完整叶函数名；基准清单占比在目标全部已解析函数中查找，不限目标前十。

### 9.3 最终指标、窗口与采集质量

| 配置 | IPC | Bad Speculation | Frontend Bound | Backend Bound | Retiring | Core Bound | Memory Bound | Fetch Latency Bound | Fetch Bandwidth Bound |
|---|---|---|---|---|---|---|---|---|---|
| OPM | 1.226 | 4.676 | 18.120 | 56.762 | 20.440 | 46.412 | 10.350 | 15.874 | 2.244 |
| TLC | 1.234 | 2.478 | 18.100 | 58.846 | 20.572 | 44.734 | 14.116 | 15.640 | 2.462 |
| 031 | 1.060 | 2.980 | 8.940 | 70.480 | 17.600 | 55.130 | 15.350 | 7.730 | 1.210 |
| 037 | 0.990 | 2.580 | 10.280 | 70.650 | 16.490 | 54.050 | 16.590 | 9.170 | 1.120 |
| pdfwf005 | 1.120 | 4.660 | 11.970 | 64.630 | 18.740 | 50.530 | 14.100 | 10.260 | 1.710 |
| 013 | 0.950 | 3.400 | 15.050 | 65.660 | 15.880 | 48.480 | 17.180 | 13.140 | 1.910 |
| 014 | 0.840 | 3.470 | 18.410 | 64.090 | 14.040 | 45.290 | 18.800 | 16.290 | 2.120 |
| 016 | 0.720 | 4.170 | 23.400 | 60.360 | 12.070 | 41.990 | 18.370 | 21.010 | 2.380 |
| 001 | 0.890 | 3.040 | 14.860 | 67.190 | 14.910 | 48.080 | 19.110 | 12.600 | 2.260 |
| 003 | 0.940 | 3.210 | 15.180 | 65.890 | 15.730 | 49.720 | 16.170 | 13.030 | 2.140 |
| 009 | 1.080 | 2.870 | 17.620 | 61.510 | 17.990 | 46.570 | 14.940 | 15.000 | 2.630 |
| 021 | 1.150 | 2.490 | 16.270 | 62.090 | 19.150 | 48.810 | 13.280 | 13.500 | 2.770 |
| 026 | 1.020 | 2.940 | 19.020 | 61.040 | 16.990 | 45.620 | 15.420 | 16.300 | 2.720 |
| 029 | 0.910 | 3.260 | 20.980 | 60.550 | 15.210 | 44.140 | 16.410 | 17.710 | 3.270 |

| 任务 | perf ROI 样本 | 未解析周期占比 | Topdown workflow 秒 | Topdown 包络秒 | 编号过程点 | 全包络 idle % |
|---|---|---|---|---|---|---|
| 031 | 773 | 0.0018% | 17.759 | 20.344 | 21 | 87.204 |
| 037 | 5084 | 0.0463% | 23.062 | 25.620 | 26 | 86.714 |
| pdfwf005 | 1239 | 0.1798% | 17.273 | 19.913 | 20 | 87.450 |
| 013 | 156032 | 0.5092% | 49.519 | 52.710 | 53 | 85.295 |
| 014 | 109567 | 0.6795% | 39.285 | 42.644 | 43 | 85.942 |
| 016 | 166358 | 0.4045% | 50.976 | 54.369 | 55 | 85.106 |
| 001 | 3736 | 2.4878% | 27.817 | 30.810 | 31 | 86.850 |
| 003 | 3280 | 2.8771% | 23.523 | 26.411 | 27 | 83.236 |
| 009 | 7707 | 2.5392% | 22.230 | 25.216 | 26 | 78.530 |
| 021 | 572915 | 2.0744% | 84.528 | 109.190 | 110 | 90.357 |
| 026 | 196298 | 3.0198% | 64.462 | 67.504 | 68 | 89.482 |
| 029 | 201812 | 1.6253% | 49.916 | 52.810 | 53 | 90.932 |

九项指标来自 ALL 最终累计报告，idle 来自本批 /proc/stat 包络；没有重建逐点 idle，也不把逐点百分比均值用作 ALL。每项一次独立采集，尚不计算重复均值、标准差或 CV。perf loss 按原始计数单位保存，ROI 归属未知，不换算为丢失周期。

### 9.4 与 OPM／TLC 的全部比较

| 新任务 | 基准 | 共同 Top-10 | Jaccard | 基准清单在新任务占比 | IPC Δ% | Bad Δpp | FE Δpp | BE Δpp | Retiring Δpp | Bound 总变差 pp | 余弦（辅助） |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 031 | OPM | 3 | 0.1765 | 67.11% | -13.540 | -1.696 | -9.180 | +13.718 | -2.840 | 13.717 | 0.980371 |
| 031 | TLC | 0 | 0.0000 | 2.75% | -14.100 | +0.502 | -9.160 | +11.634 | -2.972 | 12.134 | 0.983233 |
| 037 | OPM | 4 | 0.2500 | 56.07% | -19.250 | -2.096 | -7.840 | +13.888 | -3.950 | 13.887 | 0.981511 |
| 037 | TLC | 1 | 0.0526 | 5.44% | -19.773 | +0.102 | -7.820 | +11.804 | -4.082 | 11.904 | 0.984538 |
| pdfwf005 | OPM | 5 | 0.3333 | 25.93% | -8.646 | -0.016 | -6.150 | +7.868 | -1.700 | 7.867 | 0.991439 |
| pdfwf005 | TLC | 2 | 0.1111 | 7.99% | -9.238 | +2.182 | -6.130 | +5.784 | -1.832 | 7.964 | 0.992521 |
| 013 | OPM | 5 | 0.3333 | 34.26% | -22.512 | -1.276 | -3.070 | +8.898 | -4.560 | 8.902 | 0.991606 |
| 013 | TLC | 1 | 0.0526 | 6.12% | -23.015 | +0.922 | -3.050 | +6.814 | -4.692 | 7.739 | 0.993354 |
| 014 | OPM | 4 | 0.2500 | 32.61% | -31.485 | -1.206 | +0.290 | +7.328 | -6.400 | 7.612 | 0.991818 |
| 014 | TLC | 2 | 0.1111 | 8.37% | -31.929 | +0.992 | +0.310 | +5.244 | -6.532 | 6.539 | 0.993171 |
| 016 | OPM | 2 | 0.1111 | 8.68% | -41.272 | -0.506 | +5.280 | +3.598 | -8.370 | 8.877 | 0.987621 |
| 016 | TLC | 2 | 0.1111 | 12.06% | -41.653 | +1.692 | +5.300 | +1.514 | -8.502 | 8.504 | 0.987813 |
| 001 | OPM | 4 | 0.2500 | 45.33% | -27.406 | -1.636 | -3.260 | +10.428 | -5.530 | 10.427 | 0.988859 |
| 001 | TLC | 2 | 0.1111 | 4.61% | -27.877 | +0.562 | -3.240 | +8.344 | -5.662 | 8.904 | 0.991037 |
| 003 | OPM | 3 | 0.1765 | 44.19% | -23.328 | -1.466 | -2.940 | +9.128 | -4.710 | 9.122 | 0.991317 |
| 003 | TLC | 0 | 0.0000 | 2.00% | -23.825 | +0.732 | -2.920 | +7.044 | -4.842 | 7.769 | 0.993183 |
| 009 | OPM | 4 | 0.2500 | 45.80% | -11.909 | -1.806 | -0.500 | +4.748 | -2.450 | 4.752 | 0.997530 |
| 009 | TLC | 1 | 0.0526 | 3.89% | -12.480 | +0.392 | -0.480 | +2.664 | -2.582 | 3.059 | 0.998647 |
| 021 | OPM | 1 | 0.0526 | 2.59% | -6.199 | -2.186 | -1.850 | +5.328 | -1.290 | 5.327 | 0.997244 |
| 021 | TLC | 1 | 0.0526 | 3.90% | -6.807 | +0.012 | -1.830 | +3.244 | -1.422 | 3.254 | 0.998666 |
| 026 | OPM | 2 | 0.1111 | 4.96% | -16.803 | -1.736 | +0.900 | +4.278 | -3.450 | 5.182 | 0.997047 |
| 026 | TLC | 2 | 0.1111 | 6.34% | -17.342 | +0.462 | +0.920 | +2.194 | -3.582 | 3.579 | 0.998010 |
| 029 | OPM | 1 | 0.0526 | 7.36% | -25.775 | -1.416 | +2.860 | +3.788 | -5.230 | 6.647 | 0.994697 |
| 029 | TLC | 2 | 0.1111 | 12.53% | -26.256 | +0.782 | +2.880 | +1.704 | -5.362 | 5.364 | 0.995378 |

| 新任务 | 基准 | Core Δpp | Memory Δpp | Fetch Latency Δpp | Fetch Bandwidth Δpp |
|---|---|---|---|---|---|
| 031 | OPM | +8.718 | +5.000 | -8.144 | -1.034 |
| 031 | TLC | +10.396 | +1.234 | -7.910 | -1.252 |
| 037 | OPM | +7.638 | +6.240 | -6.704 | -1.124 |
| 037 | TLC | +9.316 | +2.474 | -6.470 | -1.342 |
| pdfwf005 | OPM | +4.118 | +3.750 | -5.614 | -0.534 |
| pdfwf005 | TLC | +5.796 | -0.016 | -5.380 | -0.752 |
| 013 | OPM | +2.068 | +6.830 | -2.734 | -0.334 |
| 013 | TLC | +3.746 | +3.064 | -2.500 | -0.552 |
| 014 | OPM | -1.122 | +8.450 | +0.416 | -0.124 |
| 014 | TLC | +0.556 | +4.684 | +0.650 | -0.342 |
| 016 | OPM | -4.422 | +8.020 | +5.136 | +0.136 |
| 016 | TLC | -2.744 | +4.254 | +5.370 | -0.082 |
| 001 | OPM | +1.668 | +8.760 | -3.274 | +0.016 |
| 001 | TLC | +3.346 | +4.994 | -3.040 | -0.202 |
| 003 | OPM | +3.308 | +5.820 | -2.844 | -0.104 |
| 003 | TLC | +4.986 | +2.054 | -2.610 | -0.322 |
| 009 | OPM | +0.158 | +4.590 | -0.874 | +0.386 |
| 009 | TLC | +1.836 | +0.824 | -0.640 | +0.168 |
| 021 | OPM | +2.398 | +2.930 | -2.374 | +0.526 |
| 021 | TLC | +4.076 | -0.836 | -2.140 | +0.308 |
| 026 | OPM | -0.792 | +5.070 | +0.426 | +0.476 |
| 026 | TLC | +0.886 | +1.304 | +0.660 | +0.258 |
| 029 | OPM | -2.272 | +6.060 | +1.836 | +1.026 |
| 029 | TLC | -0.594 | +2.294 | +2.070 | +0.808 |

总变差、百分点差和函数集合分别描述不同层次；不将它们拼成单一高／中／低标签。

### 9.5 十二项脚本、库与逐函数结果

### 031：PDF／听证材料包扁平化发布

| 实际进程／脚本 | ROI 周期占比 |
|---|---|
| pdftoppm | 78.26% |
| validate_public_packet.py | 16.80% |
| build_public_packet.py | 4.91% |
| unknown:bash | 0.02% |
| bash | 0.01% |
| unknown:taskset | 0.00% |

| 原生组件 | ROI 周期占比 |
|---|---|
| zlib | 66.25% |
| Python | 20.08% |
| PNG | 8.68% |
| Poppler | 2.56% |
| libc | 2.12% |
| libfreetype.so.6.20.1 | 0.15% |
| loader | 0.15% |
| bash | 0.01% |

| 函数排名 | 物理叶函数 | DSO 文件名 | ROI 周期占比 | 属于 OPM Top-10 | 属于 TLC Top-10 |
|---|---|---|---|---|---|
| 1 | `longest_match` | libz.so.1.2.13 | 56.95% | ✓ |  |
| 2 | `png_write_find_filter` | libpng16.so.16.40.0 | 8.68% |  |  |
| 3 | `deflate_slow` | libz.so.1.2.13 | 6.83% | ✓ |  |
| 4 | `slide_hash` | libz.so.1.2.13 | 2.00% | ✓ |  |
| 5 | `Splash::pipeRunAARGB8(SplashPipe*)` | libpoppler.so.133.0.0 | 1.96% |  |  |
| 6 | `PyObject_Vectorcall` | libpython3.12.so.1.0 | 1.87% |  |  |
| 7 | `term_rule` | libpython3.12.so.1.0 | 1.44% |  |  |
| 8 | `shift_expr_rule` | libpython3.12.so.1.0 | 1.09% |  |  |
| 9 | `expression_rule` | libpython3.12.so.1.0 | 0.94% |  |  |
| 10 | `tok_get_normal_mode` | libpython3.12.so.1.0 | 0.89% |  |  |
| 11 | `code_hash` | libpython3.12.so.1.0 | 0.82% |  |  |
| 12 | `cfg_to_instr_sequence.isra.0` | libpython3.12.so.1.0 | 0.77% |  |  |
| 13 | `_PyEval_EvalFrameDefault` | libpython3.12.so.1.0 | 0.76% | ✓ | ✓ |
| 14 | `sum_rule` | libpython3.12.so.1.0 | 0.75% |  |  |
| 15 | `_Py_dict_lookup` | libpython3.12.so.1.0 | 0.57% |  | ✓ |
| 16 | `tupledealloc` | libpython3.12.so.1.0 | 0.56% |  | ✓ |
| 17 | `bitwise_or_rule` | libpython3.12.so.1.0 | 0.43% |  |  |
| 18 | `gc_collect_main` | libpython3.12.so.1.0 | 0.43% | ✓ | ✓ |
| 19 | `__memset_generic` | libc.so.6 | 0.42% |  |  |
| 20 | `bitwise_xor_rule` | libpython3.12.so.1.0 | 0.41% |  |  |

完整未截短函数名称、完整权重、原始采集 loss 与来源 hash 均在机器结果／原 profile 中。
![DocOps 031 九项指标的全部真实过程点](../analysis/docops/processed/task-operation-expansion-20261104/figures/031-all-metrics.svg)

### 037：PDF／公交绕行材料修复

| 实际进程／脚本 | ROI 周期占比 |
|---|---|
| pdftoppm | 68.32% |
| build_bus_detour_packet.py | 18.97% |
| validate_bus_detour_packet.py | 12.43% |
| unknown:awk | 0.09% |
| unknown:grep | 0.04% |
| bash | 0.04% |
| unknown:grepconf.sh | 0.03% |
| unknown:bc | 0.02% |

| 原生组件 | ROI 周期占比 |
|---|---|
| zlib | 52.92% |
| Python | 29.90% |
| PNG | 10.27% |
| Poppler | 4.61% |
| libc | 1.19% |
| loader | 0.62% |
| libfreetype.so.6.20.1 | 0.42% |
| bash | 0.03% |

| 函数排名 | 物理叶函数 | DSO 文件名 | ROI 周期占比 | 属于 OPM Top-10 | 属于 TLC Top-10 |
|---|---|---|---|---|---|
| 1 | `longest_match` | libz.so.1.2.13 | 45.90% | ✓ |  |
| 2 | `png_write_find_filter` | libpng16.so.16.40.0 | 10.27% |  |  |
| 3 | `deflate_slow` | libz.so.1.2.13 | 4.64% | ✓ |  |
| 4 | `Splash::pipeRunAARGB8(SplashPipe*)` | libpoppler.so.133.0.0 | 3.04% |  |  |
| 5 | `_PyEval_EvalFrameDefault` | libpython3.12.so.1.0 | 2.96% | ✓ | ✓ |
| 6 | `_PyPegen_expect_token` | libpython3.12.so.1.0 | 1.50% |  |  |
| 7 | `star_target_rule` | libpython3.12.so.1.0 | 1.47% |  |  |
| 8 | `slide_hash` | libz.so.1.2.13 | 1.43% | ✓ |  |
| 9 | `astfold_expr` | libpython3.12.so.1.0 | 1.34% |  |  |
| 10 | `compiler_visit_expr1` | libpython3.12.so.1.0 | 1.01% |  |  |
| 11 | `tok_get_normal_mode` | libpython3.12.so.1.0 | 0.97% |  |  |
| 12 | `siphash13` | libpython3.12.so.1.0 | 0.95% |  |  |
| 13 | `_Py_dict_lookup` | libpython3.12.so.1.0 | 0.94% |  | ✓ |
| 14 | `compiler_visit_stmt` | libpython3.12.so.1.0 | 0.86% |  |  |
| 15 | `atom_rule` | libpython3.12.so.1.0 | 0.78% |  |  |
| 16 | `unicode_decode_utf8` | libpython3.12.so.1.0 | 0.76% |  |  |
| 17 | `gc_collect_main` | libpython3.12.so.1.0 | 0.75% | ✓ | ✓ |
| 18 | `unsafe_latin_compare` | libpython3.12.so.1.0 | 0.64% |  |  |
| 19 | `Splash::drawAALine(SplashPipe*, int, int, int, bool, unsigned char)` | libpoppler.so.133.0.0 | 0.63% |  |  |
| 20 | `Splash::compositeBackground(unsigned char const*)` | libpoppler.so.133.0.0 | 0.63% |  |  |

完整未截短函数名称、完整权重、原始采集 loss 与来源 hash 均在机器结果／原 profile 中。
![DocOps 037 九项指标的全部真实过程点](../analysis/docops/processed/task-operation-expansion-20261104/figures/037-all-metrics.svg)

### pdfwf005：PDF／结算材料包重建

| 实际进程／脚本 | ROI 周期占比 |
|---|---|
| montage | 35.99% |
| pdftoppm | 29.50% |
| rebuild_closeout_binder.py | 18.29% |
| python-inline-or-module | 16.14% |
| bash | 0.05% |
| pdftotext | 0.02% |
| unknown:mkdir | 0.01% |
| unknown:bash | 0.01% |

| 原生组件 | ROI 周期占比 |
|---|---|
| Python | 31.74% |
| ImageMagick | 25.96% |
| zlib | 23.67% |
| PNG | 11.60% |
| libc | 4.42% |
| png.so | 1.21% |
| Poppler | 0.72% |
| [unknown] | 0.16% |

| 函数排名 | 物理叶函数 | DSO 文件名 | ROI 周期占比 | 属于 OPM Top-10 | 属于 TLC Top-10 |
|---|---|---|---|---|---|
| 1 | `HorizontalFilter._omp_fn.0` | libMagickCore-7.Q16HDRI.so.10.0.2 | 12.59% |  |  |
| 2 | `VerticalFilter._omp_fn.0` | libMagickCore-7.Q16HDRI.so.10.0.2 | 11.46% |  |  |
| 3 | `png_write_find_filter` | libpng16.so.16.40.0 | 10.57% |  |  |
| 4 | `longest_match` | libz.so.1.2.13 | 8.13% | ✓ |  |
| 5 | `deflate_slow` | libz.so.1.2.13 | 7.42% | ✓ |  |
| 6 | `inflate_fast` | libz.so.1.2.13 | 2.97% | ✓ |  |
| 7 | `_PyEval_EvalFrameDefault` | libpython3.12.so.1.0 | 2.83% | ✓ | ✓ |
| 8 | `slide_hash` | libz.so.1.2.13 | 2.71% | ✓ |  |
| 9 | `_Py_dict_lookup` | libpython3.12.so.1.0 | 2.43% |  | ✓ |
| 10 | `adler32_z` | libz.so.1.2.13 | 2.30% |  |  |
| 11 | `__memcpy_generic` | libc.so.6 | 1.99% |  |  |
| 12 | `instr_sequence_to_cfg` | libpython3.12.so.1.0 | 1.60% |  |  |
| 13 | `bitwise_xor_rule` | libpython3.12.so.1.0 | 1.26% |  |  |
| 14 | `deduce_unreachable` | libpython3.12.so.1.0 | 1.13% | ✓ | ✓ |
| 15 | `_PyCfg_OptimizeCodeUnit.isra.0` | libpython3.12.so.1.0 | 1.09% |  |  |
| 16 | `png_read_filter_row_up` | libpng16.so.16.40.0 | 1.03% |  |  |
| 17 | `_PyPegen_fill_token` | libpython3.12.so.1.0 | 1.02% |  |  |
| 18 | `shift_expr_rule` | libpython3.12.so.1.0 | 1.00% |  |  |
| 19 | `ReadOnePNGImage` | png.so | 0.94% |  |  |
| 20 | `term_raw` | libpython3.12.so.1.0 | 0.87% |  |  |

完整未截短函数名称、完整权重、原始采集 loss 与来源 hash 均在机器结果／原 profile 中。
![DocOps pdfwf005 九项指标的全部真实过程点](../analysis/docops/processed/task-operation-expansion-20261104/figures/pdfwf005-all-metrics.svg)

### 013：Excel／采购投标评审发布

| 实际进程／脚本 | ROI 周期占比 |
|---|---|
| pdftoppm | 31.25% |
| montage | 26.79% |
| soffice.bin | 19.23% |
| recalc.py | 7.82% |
| build_public_bid_workbook.py | 7.21% |
| verify_public_bid_workbook.py | 6.79% |
| unknown:thread-pool | 0.79% |
| sh | 0.02% |

| 原生组件 | ROI 周期占比 |
|---|---|
| zlib | 31.66% |
| Python | 19.77% |
| ImageMagick | 13.43% |
| LibreOffice | 10.20% |
| PNG | 8.85% |
| libc | 8.31% |
| pixman | 1.55% |
| loader | 1.47% |

| 函数排名 | 物理叶函数 | DSO 文件名 | ROI 周期占比 | 属于 OPM Top-10 | 属于 TLC Top-10 |
|---|---|---|---|---|---|
| 1 | `longest_match` | libz.so.1.2.13 | 21.24% | ✓ |  |
| 2 | `png_write_find_filter` | libpng16.so.16.40.0 | 8.38% |  |  |
| 3 | `HorizontalFilter._omp_fn.0` | libMagickCore-7.Q16HDRI.so.10.0.2 | 8.05% |  |  |
| 4 | `deflate_slow` | libz.so.1.2.13 | 5.65% | ✓ |  |
| 5 | `VerticalFilter._omp_fn.0` | libMagickCore-7.Q16HDRI.so.10.0.2 | 3.52% |  |  |
| 6 | `_PyEval_EvalFrameDefault` | libpython3.12.so.1.0 | 3.33% | ✓ | ✓ |
| 7 | `__memcpy_generic` | libc.so.6 | 2.73% |  |  |
| 8 | `slide_hash` | libz.so.1.2.13 | 1.92% | ✓ |  |
| 9 | `inflate_fast` | libz.so.1.2.13 | 1.47% | ✓ |  |
| 10 | `_int_free` | libc.so.6 | 1.46% |  |  |
| 11 | `malloc` | libc.so.6 | 1.32% |  |  |
| 12 | `pixman_composite_src_8888_8888_asm_neon` | libpixman-1.so.0.42.2 | 1.01% |  |  |
| 13 | `do_lookup_x` | ld-linux-aarch64.so.1 | 0.85% |  |  |
| 14 | `FcStrHashIgnoreCase` | libfontconfig.so.1.12.1 | 0.80% |  |  |
| 15 | `_Py_dict_lookup` | libpython3.12.so.1.0 | 0.77% |  | ✓ |
| 16 | `CompositeOverImage._omp_fn.0` | libMagickCore-7.Q16HDRI.so.10.0.2 | 0.77% |  |  |
| 17 | `_PyObject_GenericGetAttrWithDict` | libpython3.12.so.1.0 | 0.68% |  | ✓ |
| 18 | `_Py_type_getattro_impl` | libpython3.12.so.1.0 | 0.65% |  |  |
| 19 | `adler32_z` | libz.so.1.2.13 | 0.64% |  |  |
| 20 | `rtl::uri::detail::readUcs4(char16_t const**, char16_t const*, bool, unsigned short, rtl::uri::detail::EscapeType*)` | libuno_sal.so.3 | 0.59% |  |  |

完整未截短函数名称、完整权重、原始采集 loss 与来源 hash 均在机器结果／原 profile 中。
![DocOps 013 九项指标的全部真实过程点](../analysis/docops/processed/task-operation-expansion-20261104/figures/013-all-metrics.svg)

### 014：Excel／灾害补助公开发布

| 实际进程／脚本 | ROI 周期占比 |
|---|---|
| pdftoppm | 39.47% |
| soffice.bin | 30.67% |
| build_disaster_release_v1.py | 12.11% |
| validate_disaster_release_v1.py | 9.09% |
| recalc.py | 7.80% |
| unknown:thread-pool | 0.55% |
| unknown:taskset | 0.07% |
| sh | 0.03% |

| 原生组件 | ROI 周期占比 |
|---|---|
| zlib | 30.54% |
| Python | 25.49% |
| LibreOffice | 17.51% |
| PNG | 7.57% |
| libc | 6.65% |
| loader | 2.68% |
| Poppler | 2.51% |
| libfreeblpriv3.so | 1.94% |

| 函数排名 | 物理叶函数 | DSO 文件名 | ROI 周期占比 | 属于 OPM Top-10 | 属于 TLC Top-10 |
|---|---|---|---|---|---|
| 1 | `longest_match` | libz.so.1.2.13 | 22.52% | ✓ |  |
| 2 | `png_write_find_filter` | libpng16.so.16.40.0 | 7.57% |  |  |
| 3 | `deflate_slow` | libz.so.1.2.13 | 4.90% | ✓ |  |
| 4 | `_PyEval_EvalFrameDefault` | libpython3.12.so.1.0 | 3.15% | ✓ | ✓ |
| 5 | `s_mpv_mul_d_add_prop` | libfreeblpriv3.so | 1.66% |  |  |
| 6 | `do_lookup_x` | ld-linux-aarch64.so.1 | 1.54% |  |  |
| 7 | `_Py_dict_lookup` | libpython3.12.so.1.0 | 1.41% |  | ✓ |
| 8 | `_PyObject_GenericSetAttrWithDict` | libpython3.12.so.1.0 | 1.36% |  |  |
| 9 | `malloc_consolidate` | libc.so.6 | 1.22% |  |  |
| 10 | `slide_hash` | libz.so.1.2.13 | 1.21% | ✓ |  |
| 11 | `inflate_table` | libz.so.1.2.13 | 1.15% |  |  |
| 12 | `_int_free` | libc.so.6 | 1.13% |  |  |
| 13 | `void rtl::str::release<_rtl_uString>(_rtl_uString*)` | libuno_sal.so.3 | 1.11% |  |  |
| 14 | `ScColumnData::GetMostUsedPattern(int, int) const` | libsclo.so | 1.07% |  |  |
| 15 | `pixman_composite_src_8888_8888_asm_neon` | libpixman-1.so.0.42.2 | 1.06% |  |  |
| 16 | `SplashXPathScanner::renderAALine(SplashBitmap*, int*, int*, int, bool) const` | libpoppler.so.133.0.0 | 1.05% |  |  |
| 17 | `PyObject_GC_Del` | libpython3.12.so.1.0 | 1.03% |  | ✓ |
| 18 | `_PyPegen_new_identifier` | libpython3.12.so.1.0 | 0.93% |  |  |
| 19 | `malloc` | libc.so.6 | 0.87% |  |  |
| 20 | `tupledealloc` | libpython3.12.so.1.0 | 0.82% |  | ✓ |

完整未截短函数名称、完整权重、原始采集 loss 与来源 hash 均在机器结果／原 profile 中。
![DocOps 014 九项指标的全部真实过程点](../analysis/docops/processed/task-operation-expansion-20261104/figures/014-all-metrics.svg)

### 016：Excel／预测模型情景级联

| 实际进程／脚本 | ROI 周期占比 |
|---|---|
| soffice.bin | 43.86% |
| recalc.py | 22.25% |
| python-inline-or-module | 19.72% |
| build_forecast_dashboard_v1.py | 9.35% |
| pdftoppm | 3.61% |
| unknown:thread-pool | 0.78% |
| unknown:awk | 0.08% |
| unknown:grep | 0.04% |

| 原生组件 | ROI 周期占比 |
|---|---|
| Python | 47.65% |
| LibreOffice | 27.74% |
| libc | 8.81% |
| loader | 3.62% |
| zlib | 2.92% |
| pixman | 2.37% |
| libfreeblpriv3.so | 1.58% |
| PNG | 1.15% |

| 函数排名 | 物理叶函数 | DSO 文件名 | ROI 周期占比 | 属于 OPM Top-10 | 属于 TLC Top-10 |
|---|---|---|---|---|---|
| 1 | `_PyEval_EvalFrameDefault` | libpython3.12.so.1.0 | 4.57% | ✓ | ✓ |
| 2 | `_Py_dict_lookup` | libpython3.12.so.1.0 | 3.70% |  | ✓ |
| 3 | `std::_Rb_tree<int, int, std::_Identity<int>, std::less<int>, std::allocator<int> >::_M_get_insert_unique_pos(int const&)` | libsclo.so | 3.11% |  |  |
| 4 | `void rtl::str::release<_rtl_uString>(_rtl_uString*)` | libuno_sal.so.3 | 2.13% |  |  |
| 5 | `longest_match` | libz.so.1.2.13 | 2.12% | ✓ |  |
| 6 | `_PyPegen_fill_token` | libpython3.12.so.1.0 | 2.07% |  |  |
| 7 | `pixman_composite_src_8888_8888_asm_neon` | libpixman-1.so.0.42.2 | 1.71% |  |  |
| 8 | `_Py_hashtable_get` | libpython3.12.so.1.0 | 1.45% |  |  |
| 9 | `_int_malloc` | libc.so.6 | 1.42% |  |  |
| 10 | `_int_free` | libc.so.6 | 1.38% |  |  |
| 11 | `malloc` | libc.so.6 | 1.24% |  |  |
| 12 | `png_write_find_filter` | libpng16.so.16.40.0 | 1.15% |  |  |
| 13 | `rtl_uString_acquire` | libuno_sal.so.3 | 1.07% |  |  |
| 14 | `__mbsrtowcs_l` | libc.so.6 | 1.04% |  |  |
| 15 | `func_traverse` | libpython3.12.so.1.0 | 1.00% |  |  |
| 16 | `do_lookup_x` | ld-linux-aarch64.so.1 | 0.93% |  |  |
| 17 | `_PyObject_GenericGetAttrWithDict` | libpython3.12.so.1.0 | 0.91% |  | ✓ |
| 18 | `bitwise_xor_rule` | libpython3.12.so.1.0 | 0.87% |  |  |
| 19 | `gc_collect_main` | libpython3.12.so.1.0 | 0.86% | ✓ | ✓ |
| 20 | `_dl_map_object_from_fd` | ld-linux-aarch64.so.1 | 0.83% |  |  |

完整未截短函数名称、完整权重、原始采集 loss 与来源 hash 均在机器结果／原 profile 中。
![DocOps 016 九项指标的全部真实过程点](../analysis/docops/processed/task-operation-expansion-20261104/figures/016-all-metrics.svg)

### 001：Word／受控文档发布修复

| 实际进程／脚本 | ROI 周期占比 |
|---|---|
| pdftoppm | 50.07% |
| soffice.bin | 25.96% |
| create_packet.py | 14.90% |
| python-inline-or-module | 8.92% |
| pdfinfo | 0.03% |
| bash | 0.02% |
| unknown:gpgconf | 0.01% |
| unknown:sed | 0.01% |

| 原生组件 | ROI 周期占比 |
|---|---|
| zlib | 44.27% |
| Python | 18.74% |
| LibreOffice | 11.65% |
| libc | 7.16% |
| PNG | 5.34% |
| lxml | 2.95% |
| loader | 2.86% |
| pixman | 2.09% |

| 函数排名 | 物理叶函数 | DSO 文件名 | ROI 周期占比 | 属于 OPM Top-10 | 属于 TLC Top-10 |
|---|---|---|---|---|---|
| 1 | `longest_match` | libz.so.1.2.13 | 36.05% | ✓ |  |
| 2 | `deflate_slow` | libz.so.1.2.13 | 5.87% | ✓ |  |
| 3 | `png_write_find_filter` | libpng16.so.16.40.0 | 5.34% |  |  |
| 4 | `_int_free` | libc.so.6 | 2.25% |  |  |
| 5 | `do_lookup_x` | ld-linux-aarch64.so.1 | 1.76% |  |  |
| 6 | `cppu::_copyConstructAnyFromData(_uno_Any*, void*, _typelib_TypeDescriptionReference*, _typelib_TypeDescription*, void (*)(void*), _uno_Mapping*)` | libuno_cppu.so.3 | 1.50% |  |  |
| 7 | `slide_hash` | libz.so.1.2.13 | 1.41% | ✓ |  |
| 8 | `pixman_composite_src_8888_8888_asm_neon` | libpixman-1.so.0.42.2 | 1.41% |  |  |
| 9 | `_PyEval_EvalFrameDefault` | libpython3.12.so.1.0 | 1.39% | ✓ | ✓ |
| 10 | `_Py_dict_lookup` | libpython3.12.so.1.0 | 1.28% |  | ✓ |
| 11 | `func_dealloc` | libpython3.12.so.1.0 | 1.09% |  |  |
| 12 | `malloc` | libc.so.6 | 1.04% |  |  |
| 13 | `s_mpv_mul_d_add_prop` | libfreeblpriv3.so | 0.77% |  |  |
| 14 | `code_hash` | libpython3.12.so.1.0 | 0.76% |  |  |
| 15 | `std::_Rb_tree<rtl::OUString, std::pair<rtl::OUString const, rtl::Reference<configmgr::Node> >, std::_Select1st<std::pair<rtl::OUString const, rtl::Reference<configmgr::Node> > >, …` | libconfigmgrlo.so | 0.74% |  |  |
| 16 | `malloc_consolidate` | libc.so.6 | 0.71% |  |  |
| 17 | `void rtl::str::release<_rtl_uString>(_rtl_uString*)` | libuno_sal.so.3 | 0.70% |  |  |
| 18 | `_Py_type_getattro` | libpython3.12.so.1.0 | 0.70% |  |  |
| 19 | `pixman_composite_src_n_8888_asm_neon` | libpixman-1.so.0.42.2 | 0.68% |  |  |
| 20 | `FcConfigSubstituteWithPat` | libfontconfig.so.1.12.1 | 0.57% |  |  |

完整未截短函数名称、完整权重、原始采集 loss 与来源 hash 均在机器结果／原 profile 中。
![DocOps 001 九项指标的全部真实过程点](../analysis/docops/processed/task-operation-expansion-20261104/figures/001-all-metrics.svg)

### 003：Word／公开记录元数据清理

| 实际进程／脚本 | ROI 周期占比 |
|---|---|
| pdftoppm | 51.54% |
| soffice.bin | 24.73% |
| build_public_packet.py | 13.61% |
| audit_public_packet.py | 9.96% |
| unknown:bash | 0.03% |
| sh | 0.02% |
| unknown:gpgconf | 0.02% |
| unknown:pdftoppm | 0.01% |

| 原生组件 | ROI 周期占比 |
|---|---|
| zlib | 44.62% |
| Python | 14.91% |
| LibreOffice | 14.23% |
| PNG | 9.05% |
| libc | 6.15% |
| loader | 3.54% |
| lxml | 3.14% |
| pixman | 1.43% |

| 函数排名 | 物理叶函数 | DSO 文件名 | ROI 周期占比 | 属于 OPM Top-10 | 属于 TLC Top-10 |
|---|---|---|---|---|---|
| 1 | `longest_match` | libz.so.1.2.13 | 33.55% | ✓ |  |
| 2 | `png_write_find_filter` | libpng16.so.16.40.0 | 9.05% |  |  |
| 3 | `deflate_slow` | libz.so.1.2.13 | 5.91% | ✓ |  |
| 4 | `slide_hash` | libz.so.1.2.13 | 3.21% | ✓ |  |
| 5 | `do_lookup_x` | ld-linux-aarch64.so.1 | 2.48% |  |  |
| 6 | `_PyUnicode_ToLowerFull` | libpython3.12.so.1.0 | 2.22% |  |  |
| 7 | `do_upper_or_lower` | libpython3.12.so.1.0 | 1.77% |  |  |
| 8 | `subtype_dealloc` | libpython3.12.so.1.0 | 1.74% |  |  |
| 9 | `_int_malloc` | libc.so.6 | 1.57% |  |  |
| 10 | `rtl_uString_assign` | libuno_sal.so.3 | 1.52% |  |  |
| 11 | `strchr` | libc.so.6 | 1.27% |  |  |
| 12 | `std::_Rb_tree<rtl::OUString, std::pair<rtl::OUString const, rtl::Reference<configmgr::Node> >, std::_Select1st<std::pair<rtl::OUString const, rtl::Reference<configmgr::Node> > >, …` | libconfigmgrlo.so | 1.20% |  |  |
| 13 | `make_gen` | libpython3.12.so.1.0 | 1.17% |  |  |
| 14 | `PyObject_CallOneArg` | libpython3.12.so.1.0 | 1.17% |  |  |
| 15 | `_int_free` | libc.so.6 | 1.13% |  |  |
| 16 | `_PyEval_EvalFrameDefault` | libpython3.12.so.1.0 | 1.11% | ✓ | ✓ |
| 17 | `(anonymous namespace)::InterfaceTypeDescription::~InterfaceTypeDescription()` | libuno_cppuhelpergcc3.so.3 | 0.99% |  |  |
| 18 | `adler32_z` | libz.so.1.2.13 | 0.93% |  |  |
| 19 | `s_mpv_mul_d_add_prop` | libfreeblpriv3.so | 0.92% |  |  |
| 20 | `pixman_composite_src_n_8888_asm_neon` | libpixman-1.so.0.42.2 | 0.81% |  |  |

完整未截短函数名称、完整权重、原始采集 loss 与来源 hash 均在机器结果／原 profile 中。
![DocOps 003 九项指标的全部真实过程点](../analysis/docops/processed/task-operation-expansion-20261104/figures/003-all-metrics.svg)

### 009：Word／事件手册发布

| 实际进程／脚本 | ROI 周期占比 |
|---|---|
| pdftoppm | 64.00% |
| soffice.bin | 22.33% |
| build_incident_manual_publication.py | 9.44% |
| validate_incident_manual_publication.py | 3.38% |
| render_docx.py | 0.52% |
| unknown:awk | 0.10% |
| unknown:grep | 0.05% |
| bash | 0.04% |

| 原生组件 | ROI 周期占比 |
|---|---|
| zlib | 44.39% |
| PNG | 19.00% |
| LibreOffice | 9.11% |
| Python | 8.86% |
| libc | 7.52% |
| lxml | 2.88% |
| loader | 2.48% |
| pixman | 2.07% |

| 函数排名 | 物理叶函数 | DSO 文件名 | ROI 周期占比 | 属于 OPM Top-10 | 属于 TLC Top-10 |
|---|---|---|---|---|---|
| 1 | `longest_match` | libz.so.1.2.13 | 27.62% | ✓ |  |
| 2 | `png_write_find_filter` | libpng16.so.16.40.0 | 19.00% |  |  |
| 3 | `deflate_slow` | libz.so.1.2.13 | 10.59% | ✓ |  |
| 4 | `slide_hash` | libz.so.1.2.13 | 4.91% | ✓ |  |
| 5 | `_PyEval_EvalFrameDefault` | libpython3.12.so.1.0 | 2.35% | ✓ | ✓ |
| 6 | `_int_free` | libc.so.6 | 1.90% |  |  |
| 7 | `pixman_composite_src_8888_8888_asm_neon` | libpixman-1.so.0.42.2 | 1.53% |  |  |
| 8 | `do_lookup_x` | ld-linux-aarch64.so.1 | 1.23% |  |  |
| 9 | `malloc` | libc.so.6 | 1.09% |  |  |
| 10 | `malloc_consolidate` | libc.so.6 | 1.06% |  |  |
| 11 | `list_dealloc` | libpython3.12.so.1.0 | 0.91% |  |  |
| 12 | `free_keys_object` | libpython3.12.so.1.0 | 0.79% |  |  |
| 13 | `Splash::compositeBackground(unsigned char const*)` | libpoppler.so.133.0.0 | 0.67% |  |  |
| 14 | `unoidl::detail::UnoidlProvider::findEntity(rtl::OUString const&) const` | libunoidllo.so | 0.62% |  |  |
| 15 | `_int_free_create_chunk` | libc.so.6 | 0.62% |  |  |
| 16 | `xmlStrEqual` | etree.cpython-312-aarch64-linux-gnu.so | 0.61% |  |  |
| 17 | `compress_block` | libz.so.1.2.13 | 0.58% |  |  |
| 18 | `s_mpv_mul_d_add_prop` | libfreeblpriv3.so | 0.53% |  |  |
| 19 | `adler32_z` | libz.so.1.2.13 | 0.52% |  |  |
| 20 | `pixman_composite_src_n_8888_asm_neon` | libpixman-1.so.0.42.2 | 0.46% |  |  |

完整未截短函数名称、完整权重、原始采集 loss 与来源 hash 均在机器结果／原 profile 中。
![DocOps 009 九项指标的全部真实过程点](../analysis/docops/processed/task-operation-expansion-20261104/figures/009-all-metrics.svg)

### 021：PPT／庇护所无障碍整改

| 实际进程／脚本 | ROI 周期占比 |
|---|---|
| pdftoppm | 32.54% |
| soffice.bin | 32.24% |
| montage | 14.28% |
| build_public_shelter_briefing.py | 11.61% |
| validate_public_shelter_briefing.py | 7.69% |
| unknown:thread-pool | 1.42% |
| unknown:Parser | 0.08% |
| soffice.py | 0.07% |

| 原生组件 | ROI 周期占比 |
|---|---|
| Poppler | 27.74% |
| LibreOffice | 24.32% |
| Python | 15.95% |
| ImageMagick | 10.59% |
| libc | 7.56% |
| JPEG | 4.76% |
| lxml | 2.12% |
| pixman | 1.98% |

| 函数排名 | 物理叶函数 | DSO 文件名 | ROI 周期占比 | 属于 OPM Top-10 | 属于 TLC Top-10 |
|---|---|---|---|---|---|
| 1 | `Splash::pipeRun(SplashPipe*)` | libpoppler.so.133.0.0 | 9.94% |  |  |
| 2 | `VerticalFilter._omp_fn.0` | libMagickCore-7.Q16HDRI.so.10.0.2 | 6.96% |  |  |
| 3 | `Splash::pipeRunAARGB8(SplashPipe*)` | libpoppler.so.133.0.0 | 6.12% |  |  |
| 4 | `vcl::(anonymous namespace)::ImplScaleConvolutionVer(Bitmap const&, Bitmap&, double const&, vcl::Kernel const&)` | libvcllo.so | 3.89% |  |  |
| 5 | `HorizontalFilter._omp_fn.0` | libMagickCore-7.Q16HDRI.so.10.0.2 | 2.69% |  |  |
| 6 | `__memcpy_generic` | libc.so.6 | 2.29% |  |  |
| 7 | `Splash::drawAALine(SplashPipe*, int, int, int, bool, unsigned char)` | libpoppler.so.133.0.0 | 2.01% |  |  |
| 8 | `_PyEval_EvalFrameDefault` | libpython3.12.so.1.0 | 1.80% | ✓ | ✓ |
| 9 | `BitmapReadAccess::SetPixelForN24BitTcBgr(unsigned char*, long, BitmapColor const&)` | libvcllo.so | 1.61% |  |  |
| 10 | `expandRow(unsigned char*, unsigned char*, int, int, int)` | libpoppler.so.133.0.0 | 1.52% |  |  |
| 11 | `vcl::(anonymous namespace)::ImplScaleConvolutionHor(Bitmap const&, Bitmap&, double const&, vcl::Kernel const&)` | libvcllo.so | 1.49% |  |  |
| 12 | `FlateStream::getChars(int, unsigned char*)` | libpoppler.so.133.0.0 | 1.49% |  |  |
| 13 | `pixman_composite_src_8888_8888_asm_neon` | libpixman-1.so.0.42.2 | 1.42% |  |  |
| 14 | `Splash::scaleImageYdownXdown(bool (*)(void*, unsigned char*, unsigned char*), void*, SplashColorMode, int, bool, int, int, int, int, SplashBitmap*)` | libpoppler.so.133.0.0 | 1.37% |  |  |
| 15 | `decode_mcu_AC_refine` | libjpeg.so.62.4.0 | 1.12% |  |  |
| 16 | `_int_malloc` | libc.so.6 | 1.10% |  |  |
| 17 | `malloc` | libc.so.6 | 1.04% |  |  |
| 18 | `rgb_ycc_convert` | libjpeg.so.62.4.0 | 0.97% |  |  |
| 19 | `_Py_dict_lookup` | libpython3.12.so.1.0 | 0.97% |  | ✓ |
| 20 | `Splash::scaleImageYupXupBilinear(bool (*)(void*, unsigned char*, unsigned char*), void*, SplashColorMode, int, bool, int, int, int, int, SplashBitmap*)` | libpoppler.so.133.0.0 | 0.90% |  |  |

完整未截短函数名称、完整权重、原始采集 loss 与来源 hash 均在机器结果／原 profile 中。
![DocOps 021 九项指标的全部真实过程点](../analysis/docops/processed/task-operation-expansion-20261104/figures/021-all-metrics.svg)

### 026：PPT／气候披露图表重建

| 实际进程／脚本 | ROI 周期占比 |
|---|---|
| pdftoppm | 40.38% |
| soffice.bin | 30.44% |
| build_climate_disclosure.py | 20.77% |
| qa_climate_disclosure.py | 6.24% |
| unknown:thread-pool | 1.63% |
| unknown:awk | 0.14% |
| bash | 0.07% |
| unknown:Parser | 0.06% |

| 原生组件 | ROI 周期占比 |
|---|---|
| Poppler | 36.90% |
| Python | 20.97% |
| LibreOffice | 19.20% |
| libc | 6.60% |
| lxml | 3.60% |
| JPEG | 2.64% |
| loader | 2.26% |
| pixman | 2.09% |

| 函数排名 | 物理叶函数 | DSO 文件名 | ROI 周期占比 | 属于 OPM Top-10 | 属于 TLC Top-10 |
|---|---|---|---|---|---|
| 1 | `Splash::pipeRunAARGB8(SplashPipe*)` | libpoppler.so.133.0.0 | 12.81% |  |  |
| 2 | `Splash::pipeRun(SplashPipe*)` | libpoppler.so.133.0.0 | 11.74% |  |  |
| 3 | `_PyEval_EvalFrameDefault` | libpython3.12.so.1.0 | 2.75% | ✓ | ✓ |
| 4 | `Splash::drawAALine(SplashPipe*, int, int, int, bool, unsigned char)` | libpoppler.so.133.0.0 | 2.52% |  |  |
| 5 | `_PyCfg_OptimizeCodeUnit.isra.0` | libpython3.12.so.1.0 | 1.84% |  |  |
| 6 | `FlateStream::getChars(int, unsigned char*)` | libpoppler.so.133.0.0 | 1.72% |  |  |
| 7 | `s_mpv_mul_d_add_prop` | libfreeblpriv3.so | 1.46% |  |  |
| 8 | `gc_collect_main` | libpython3.12.so.1.0 | 1.44% | ✓ | ✓ |
| 9 | `pixman_composite_src_8888_8888_asm_neon` | libpixman-1.so.0.42.2 | 1.34% |  |  |
| 10 | `expandRow(unsigned char*, unsigned char*, int, int, int)` | libpoppler.so.133.0.0 | 1.29% |  |  |
| 11 | `_int_free` | libc.so.6 | 1.23% |  |  |
| 12 | `_int_malloc` | libc.so.6 | 1.22% |  |  |
| 13 | `SplashClip::testClipPaths(int, int)` | libpoppler.so.133.0.0 | 1.20% |  |  |
| 14 | `Splash::scaleImageYdownXdown(bool (*)(void*, unsigned char*, unsigned char*), void*, SplashColorMode, int, bool, int, int, int, int, SplashBitmap*)` | libpoppler.so.133.0.0 | 1.01% |  |  |
| 15 | `do_lookup_x` | ld-linux-aarch64.so.1 | 0.89% |  |  |
| 16 | `_PyPegen_singleton_seq.isra.0` | libpython3.12.so.1.0 | 0.89% |  |  |
| 17 | `void (anonymous namespace)::stackBlurVertical<(anonymous namespace)::SumFunction8>((anonymous namespace)::BlurSharedData const&, int, int)` | libvcllo.so | 0.88% |  |  |
| 18 | `jsimd_huff_encode_one_block_neon` | libjpeg.so.62.4.0 | 0.79% |  |  |
| 19 | `shift_expr_rule` | libpython3.12.so.1.0 | 0.78% |  |  |
| 20 | `SplashBitmap::getPixel(int, int, unsigned char*)` | libpoppler.so.133.0.0 | 0.75% |  |  |

完整未截短函数名称、完整权重、原始采集 loss 与来源 hash 均在机器结果／原 profile 中。
![DocOps 026 九项指标的全部真实过程点](../analysis/docops/processed/task-operation-expansion-20261104/figures/026-all-metrics.svg)

### 029：PPT／季度业务回顾发布

| 实际进程／脚本 | ROI 周期占比 |
|---|---|
| soffice.bin | 50.44% |
| build_release_deck.py | 24.05% |
| validate_release_deck.py | 17.35% |
| pdftoppm | 6.11% |
| unknown:thread-pool | 1.46% |
| soffice.py | 0.29% |
| unknown:Parser | 0.14% |
| sh | 0.03% |

| 原生组件 | ROI 周期占比 |
|---|---|
| Python | 36.96% |
| LibreOffice | 32.15% |
| libc | 7.61% |
| Poppler | 5.08% |
| loader | 3.86% |
| pixman | 2.93% |
| libstdc++.so.6.0.30 | 2.42% |
| lxml | 1.87% |

| 函数排名 | 物理叶函数 | DSO 文件名 | ROI 周期占比 | 属于 OPM Top-10 | 属于 TLC Top-10 |
|---|---|---|---|---|---|
| 1 | `_PyEval_EvalFrameDefault` | libpython3.12.so.1.0 | 5.31% | ✓ | ✓ |
| 2 | `_Py_dict_lookup` | libpython3.12.so.1.0 | 3.45% |  | ✓ |
| 3 | `oox::drawingml::table::applyTableStylePart(oox::core::XmlFilterBase const&, oox::drawingml::FillProperties&, oox::drawingml::TextCharacterProperties&, oox::drawingml::LineProperti…` | libooxlo.so | 2.00% |  |  |
| 4 | `malloc` | libc.so.6 | 1.91% |  |  |
| 5 | `oox::PropertyMap::fillSequences(com::sun::star::uno::Sequence<rtl::OUString>&, com::sun::star::uno::Sequence<com::sun::star::uno::Any>&) const` | libooxlo.so | 1.85% |  |  |
| 6 | `Splash::pipeRunAARGB8(SplashPipe*)` | libpoppler.so.133.0.0 | 1.76% |  |  |
| 7 | `_PyCfg_OptimizeCodeUnit.isra.0` | libpython3.12.so.1.0 | 1.68% |  |  |
| 8 | `pixman_composite_src_8888_8888_asm_neon` | libpixman-1.so.0.42.2 | 1.67% |  |  |
| 9 | `std::_Hashtable<unsigned short, std::pair<unsigned short const, SfxPoolItem const*>, std::allocator<std::pair<unsigned short const, SfxPoolItem const*> >, std::__detail::_Select1s…` | libsvllo.so | 1.54% |  |  |
| 10 | `std::__detail::_Prime_rehash_policy::_M_need_rehash(unsigned long, unsigned long, unsigned long) const` | libstdc++.so.6.0.30 | 1.47% |  |  |
| 11 | `void rtl::str::release<_rtl_uString>(_rtl_uString*)` | libuno_sal.so.3 | 1.34% |  |  |
| 12 | `_PyObject_FastCallDictTstate` | libpython3.12.so.1.0 | 1.31% |  |  |
| 13 | `pixman_composite_src_n_8888_asm_neon` | libpixman-1.so.0.42.2 | 1.26% |  |  |
| 14 | `s_mpv_mul_d_add_prop` | libfreeblpriv3.so | 1.15% |  |  |
| 15 | `update_one_slot` | libpython3.12.so.1.0 | 1.07% |  |  |
| 16 | `_dl_tlsdesc_return` | ld-linux-aarch64.so.1 | 1.07% |  |  |
| 17 | `_PyObject_GenericGetAttrWithDict` | libpython3.12.so.1.0 | 0.95% |  | ✓ |
| 18 | `do_lookup_x` | ld-linux-aarch64.so.1 | 0.90% |  |  |
| 19 | `_int_free` | libc.so.6 | 0.89% |  |  |
| 20 | `Splash::pipeRun(SplashPipe*)` | libpoppler.so.133.0.0 | 0.85% |  |  |

完整未截短函数名称、完整权重、原始采集 loss 与来源 hash 均在机器结果／原 profile 中。
![DocOps 029 九项指标的全部真实过程点](../analysis/docops/processed/task-operation-expansion-20261104/figures/029-all-metrics.svg)

### 9.6 新任务内部同格式对照（补充）

| 任务 A | 任务 B | 共同 Top-10 | Jaccard | Bound 总变差 pp | 余弦（辅助） |
|---|---|---|---|---|---|
| 031 | 037 | 5 | 0.3333 | 1.510 | 0.999701 |
| 031 | pdfwf005 | 4 | 0.2500 | 5.850 | 0.997509 |
| 037 | pdfwf005 | 5 | 0.3333 | 6.020 | 0.997478 |
| 013 | 014 | 5 | 0.3333 | 3.420 | 0.998306 |
| 013 | 016 | 3 | 0.1765 | 9.115 | 0.988848 |
| 014 | 016 | 3 | 0.1765 | 5.695 | 0.995765 |
| 001 | 003 | 5 | 0.3333 | 1.305 | 0.999844 |
| 001 | 009 | 8 | 0.6667 | 5.845 | 0.996396 |
| 003 | 009 | 5 | 0.3333 | 4.710 | 0.997670 |
| 021 | 026 | 5 | 0.3333 | 3.205 | 0.998549 |
| 021 | 029 | 2 | 0.1111 | 5.480 | 0.995532 |
| 026 | 029 | 4 | 0.2500 | 2.275 | 0.999167 |

### 9.6A 完整函数清单的出现范围与周期分区

该补充统计以 OPM、TLC 各自完整已解析函数清单及其去重并集为参考，按库文件名＋完整物理叶函数名精确匹配。统计目标是新任务中哪些函数已由旧采样观察到；不限定旧前十，也不将旧清单未见项等同为新业务算法或新计算机制。

对每个新任务、每个参考范围：已见 period＋未见 period＋未解析 period＝新任务完整 ROI period。以下百分比的分母均为目标完整 ROI。OPM 与 TLC 出现集合有交集，不相加；OPM+TLC 使用去重并集。旧例中极低权重函数也算已见，故“路径出现过”不证明旧负载充分体现相同成本。

| 任务 | 参考清单 | 已见 period | 未见 period | 未解析 period | 已见 % | 未见 % | 未解析 % | 未见函数数 |
|---|---|---|---|---|---|---|---|---|
| 031 | OPM | 29907346184 | 9524036184 | 725948 | 75.845161 | 24.152998 | 0.001841 | 65 |
| 031 | TLC | 29697233693 | 9734148675 | 725948 | 75.312315 | 24.685844 | 0.001841 | 69 |
| 031 | OPM+TLC | 31209821314 | 8221561054 | 725948 | 79.148244 | 20.849915 | 0.001841 | 54 |
| 037 | OPM | 39988274916 | 16436518864 | 26135206 | 70.837231 | 29.116472 | 0.046297 | 138 |
| 037 | TLC | 37243110581 | 19181683199 | 26135206 | 65.974309 | 33.979393 | 0.046297 | 123 |
| 037 | OPM+TLC | 41079968555 | 15344825225 | 26135206 | 72.771112 | 27.182591 | 0.046297 | 105 |
| pdfwf005 | OPM | 17250417403 | 23199959632 | 72871142 | 42.569187 | 57.250987 | 0.179826 | 112 |
| pdfwf005 | TLC | 16302370738 | 24148006297 | 72871142 | 40.229674 | 59.590500 | 0.179826 | 103 |
| pdfwf005 | OPM+TLC | 18401972879 | 22048404156 | 72871142 | 45.410903 | 54.409272 | 0.179826 | 93 |
| 013 | OPM | 44964540185 | 43201536247 | 451232017 | 50.740133 | 48.750675 | 0.509192 | 528 |
| 013 | TLC | 50205824959 | 37960251473 | 451232017 | 56.654649 | 42.836159 | 0.509192 | 333 |
| 013 | OPM+TLC | 52424821064 | 35741255368 | 451232017 | 59.158670 | 40.332138 | 0.509192 | 315 |
| 014 | OPM | 32934592591 | 30123088683 | 431395318 | 51.874424 | 47.446097 | 0.679480 | 511 |
| 014 | TLC | 40165751851 | 22891929423 | 431395318 | 63.264035 | 36.056485 | 0.679480 | 322 |
| 014 | OPM+TLC | 42010681701 | 21046999573 | 431395318 | 66.169937 | 33.150584 | 0.679480 | 303 |
| 016 | OPM | 25824361613 | 49001827572 | 303889138 | 34.372867 | 65.222649 | 0.404484 | 678 |
| 016 | TLC | 40112955227 | 34713233958 | 303889138 | 53.391340 | 46.204176 | 0.404484 | 447 |
| 016 | OPM+TLC | 42260093003 | 32566096182 | 303889138 | 56.249233 | 43.346283 | 0.404484 | 428 |
| 001 | OPM | 35004349448 | 20359634756 | 1412488230 | 61.652914 | 35.859281 | 2.487806 | 237 |
| 001 | TLC | 39749635481 | 15614348723 | 1412488230 | 70.010752 | 27.501442 | 2.487806 | 171 |
| 001 | OPM+TLC | 40845325993 | 14518658211 | 1412488230 | 71.940584 | 25.571610 | 2.487806 | 158 |
| 003 | OPM | 30669300128 | 21052175771 | 1532136337 | 57.591023 | 39.531921 | 2.877056 | 210 |
| 003 | TLC | 35875694719 | 15845781180 | 1532136337 | 67.367627 | 29.755317 | 2.877056 | 152 |
| 003 | OPM+TLC | 36560345532 | 15161130367 | 1532136337 | 68.653269 | 28.469675 | 2.877056 | 142 |
| 009 | OPM | 39981575365 | 27846561388 | 1767157065 | 57.448677 | 40.012133 | 2.539190 | 271 |
| 009 | TLC | 43930071800 | 23898064953 | 1767157065 | 63.122187 | 34.338622 | 2.539190 | 216 |
| 009 | OPM+TLC | 45242799871 | 22585336882 | 1767157065 | 65.008419 | 32.452391 | 2.539190 | 201 |
| 021 | OPM | 42758646847 | 70614938794 | 2401668723 | 36.932458 | 60.993119 | 2.074423 | 705 |
| 021 | TLC | 27982652715 | 85390932926 | 2401668723 | 24.169805 | 73.755772 | 2.074423 | 532 |
| 021 | OPM+TLC | 53935080006 | 59438505635 | 2401668723 | 46.586017 | 51.339560 | 2.074423 | 497 |
| 026 | OPM | 34248357052 | 33840869975 | 2120158553 | 48.780312 | 48.199923 | 3.019765 | 585 |
| 026 | TLC | 18751954655 | 49337272372 | 2120158553 | 26.708615 | 70.271620 | 3.019765 | 418 |
| 026 | OPM+TLC | 41697987754 | 26391239273 | 2120158553 | 59.390903 | 37.589332 | 3.019765 | 396 |
| 029 | OPM | 14856789509 | 24026685300 | 642425826 | 37.587479 | 60.787192 | 1.625329 | 470 |
| 029 | TLC | 19169826407 | 19713648402 | 642425826 | 48.499404 | 49.875267 | 1.625329 | 320 |
| 029 | OPM+TLC | 21940646517 | 16942828292 | 642425826 | 55.509542 | 42.865129 | 1.625329 | 303 |

### 9.6B 旧两例均未见的主要具体函数

下表每项列旧 OPM／TLC 合并清单未见函数中的前十项，按目标完整 ROI period 排序；函数名称显示最多 180 字符，完整签名和 period 仍在 comparison.json 的函数列表及 function_presence 字段中。旧采样未见不证明永不执行；通用辅助路径、不同实现和具体对象操作分别解释。

**031 听证材料包扁平化发布：未见函数 54 个，合计 20.85%。**

| 函数 | 库文件名 | 目标 period | 完整 ROI 占比 |
|---|---|---|---|
| `png_write_find_filter` | libpng16.so.16.40.0 | 3421412927 | 8.68% |
| `term_rule` | libpython3.12.so.1.0 | 567246634 | 1.44% |
| `shift_expr_rule` | libpython3.12.so.1.0 | 428663053 | 1.09% |
| `expression_rule` | libpython3.12.so.1.0 | 370058830 | 0.94% |
| `tok_get_normal_mode` | libpython3.12.so.1.0 | 349607343 | 0.89% |
| `code_hash` | libpython3.12.so.1.0 | 323985885 | 0.82% |
| `cfg_to_instr_sequence.isra.0` | libpython3.12.so.1.0 | 303514806 | 0.77% |
| `sum_rule` | libpython3.12.so.1.0 | 294543029 | 0.75% |
| `bitwise_or_rule` | libpython3.12.so.1.0 | 169152987 | 0.43% |
| `bitwise_xor_rule` | libpython3.12.so.1.0 | 163140221 | 0.41% |

**037 公交绕行材料修复：未见函数 105 个，合计 27.18%。**

| 函数 | 库文件名 | 目标 period | 完整 ROI 占比 |
|---|---|---|---|
| `png_write_find_filter` | libpng16.so.16.40.0 | 5797867418 | 10.27% |
| `_PyPegen_expect_token` | libpython3.12.so.1.0 | 845923366 | 1.50% |
| `star_target_rule` | libpython3.12.so.1.0 | 832342895 | 1.47% |
| `astfold_expr` | libpython3.12.so.1.0 | 755634100 | 1.34% |
| `compiler_visit_expr1` | libpython3.12.so.1.0 | 570148750 | 1.01% |
| `tok_get_normal_mode` | libpython3.12.so.1.0 | 549244333 | 0.97% |
| `compiler_visit_stmt` | libpython3.12.so.1.0 | 486030611 | 0.86% |
| `atom_rule` | libpython3.12.so.1.0 | 438102907 | 0.78% |
| `shift_expr_rule` | libpython3.12.so.1.0 | 350756704 | 0.62% |
| `term_raw` | libpython3.12.so.1.0 | 348065234 | 0.62% |

**pdfwf005 结算材料包重建：未见函数 93 个，合计 54.41%。**

| 函数 | 库文件名 | 目标 period | 完整 ROI 占比 |
|---|---|---|---|
| `HorizontalFilter._omp_fn.0` | libMagickCore-7.Q16HDRI.so.10.0.2 | 5102262862 | 12.59% |
| `VerticalFilter._omp_fn.0` | libMagickCore-7.Q16HDRI.so.10.0.2 | 4645151623 | 11.46% |
| `png_write_find_filter` | libpng16.so.16.40.0 | 4283600071 | 10.57% |
| `instr_sequence_to_cfg` | libpython3.12.so.1.0 | 646473128 | 1.60% |
| `bitwise_xor_rule` | libpython3.12.so.1.0 | 511402065 | 1.26% |
| `png_read_filter_row_up` | libpng16.so.16.40.0 | 415887179 | 1.03% |
| `_PyPegen_fill_token` | libpython3.12.so.1.0 | 412862893 | 1.02% |
| `shift_expr_rule` | libpython3.12.so.1.0 | 406708457 | 1.00% |
| `ReadOnePNGImage` | png.so | 381398690 | 0.94% |
| `term_raw` | libpython3.12.so.1.0 | 352838622 | 0.87% |

**013 采购投标评审发布：未见函数 315 个，合计 40.33%。**

| 函数 | 库文件名 | 目标 period | 完整 ROI 占比 |
|---|---|---|---|
| `png_write_find_filter` | libpng16.so.16.40.0 | 7423314478 | 8.38% |
| `HorizontalFilter._omp_fn.0` | libMagickCore-7.Q16HDRI.so.10.0.2 | 7129663715 | 8.05% |
| `VerticalFilter._omp_fn.0` | libMagickCore-7.Q16HDRI.so.10.0.2 | 3118338666 | 3.52% |
| `pixman_composite_src_8888_8888_asm_neon` | libpixman-1.so.0.42.2 | 894731742 | 1.01% |
| `FcStrHashIgnoreCase` | libfontconfig.so.1.12.1 | 704536289 | 0.80% |
| `CompositeOverImage._omp_fn.0` | libMagickCore-7.Q16HDRI.so.10.0.2 | 684497496 | 0.77% |
| `rtl::uri::detail::readUcs4(char16_t const**, char16_t const*, bool, unsigned short, rtl::uri::detail::EscapeType*)` | libuno_sal.so.3 | 521699635 | 0.59% |
| `pixman_composite_src_n_8888_asm_neon` | libpixman-1.so.0.42.2 | 482064702 | 0.54% |
| `code_hash` | libpython3.12.so.1.0 | 472765708 | 0.53% |
| `SfxInterface::GetSlot(rtl::OUString const&) const` | libsfxlo.so | 404013552 | 0.46% |

**014 灾害补助公开发布：未见函数 303 个，合计 33.15%。**

| 函数 | 库文件名 | 目标 period | 完整 ROI 占比 |
|---|---|---|---|
| `png_write_find_filter` | libpng16.so.16.40.0 | 4808553703 | 7.57% |
| `s_mpv_mul_d_add_prop` | libfreeblpriv3.so | 1056881590 | 1.66% |
| `ScColumnData::GetMostUsedPattern(int, int) const` | libsclo.so | 679020089 | 1.07% |
| `pixman_composite_src_8888_8888_asm_neon` | libpixman-1.so.0.42.2 | 675512585 | 1.06% |
| `SplashXPathScanner::renderAALine(SplashBitmap*, int*, int*, int, bool) const` | libpoppler.so.133.0.0 | 665314676 | 1.05% |
| `_PyPegen_new_identifier` | libpython3.12.so.1.0 | 592821474 | 0.93% |
| `pixman_composite_src_n_8888_asm_neon` | libpixman-1.so.0.42.2 | 505070087 | 0.80% |
| `primary_raw` | libpython3.12.so.1.0 | 499088978 | 0.79% |
| `std::_Rb_tree<rtl::OUString, std::pair<rtl::OUString const, rtl::Reference<configmgr::Node> >, std::_Select1st<std::pair<rtl::OUString const, rtl::Reference<configmgr::Node> > >, …` | libconfigmgrlo.so | 474289921 | 0.75% |
| `std::_Hashtable<std::basic_string_view<char, std::char_traits<char> >, std::pair<std::basic_string_view<char, std::char_traits<char> > const, unsigned long>, std::allocator<std::p…` | liborcus-parser-0.20.so.0 | 397355800 | 0.63% |

**016 预测模型情景级联：未见函数 428 个，合计 43.35%。**

| 函数 | 库文件名 | 目标 period | 完整 ROI 占比 |
|---|---|---|---|
| `std::_Rb_tree<int, int, std::_Identity<int>, std::less<int>, std::allocator<int> >::_M_get_insert_unique_pos(int const&)` | libsclo.so | 2333994024 | 3.11% |
| `_PyPegen_fill_token` | libpython3.12.so.1.0 | 1553336085 | 2.07% |
| `pixman_composite_src_8888_8888_asm_neon` | libpixman-1.so.0.42.2 | 1284599382 | 1.71% |
| `png_write_find_filter` | libpng16.so.16.40.0 | 861639963 | 1.15% |
| `__mbsrtowcs_l` | libc.so.6 | 780592409 | 1.04% |
| `bitwise_xor_rule` | libpython3.12.so.1.0 | 656380887 | 0.87% |
| `shift_expr_rule` | libpython3.12.so.1.0 | 601845376 | 0.80% |
| `conjunction_rule` | libpython3.12.so.1.0 | 584054454 | 0.78% |
| `s_mpv_mul_d_add` | libfreeblpriv3.so | 565473814 | 0.75% |
| `t_primary_raw` | libpython3.12.so.1.0 | 526658889 | 0.70% |

**001 受控文档发布修复：未见函数 158 个，合计 25.57%。**

| 函数 | 库文件名 | 目标 period | 完整 ROI 占比 |
|---|---|---|---|
| `png_write_find_filter` | libpng16.so.16.40.0 | 3030752044 | 5.34% |
| `cppu::_copyConstructAnyFromData(_uno_Any*, void*, _typelib_TypeDescriptionReference*, _typelib_TypeDescription*, void (*)(void*), _uno_Mapping*)` | libuno_cppu.so.3 | 854286631 | 1.50% |
| `pixman_composite_src_8888_8888_asm_neon` | libpixman-1.so.0.42.2 | 798015082 | 1.41% |
| `s_mpv_mul_d_add_prop` | libfreeblpriv3.so | 438599142 | 0.77% |
| `code_hash` | libpython3.12.so.1.0 | 433364467 | 0.76% |
| `std::_Rb_tree<rtl::OUString, std::pair<rtl::OUString const, rtl::Reference<configmgr::Node> >, std::_Select1st<std::pair<rtl::OUString const, rtl::Reference<configmgr::Node> > >, …` | libconfigmgrlo.so | 417854267 | 0.74% |
| `pixman_composite_src_n_8888_asm_neon` | libpixman-1.so.0.42.2 | 388907942 | 0.68% |
| `FcConfigSubstituteWithPat` | libfontconfig.so.1.12.1 | 326298231 | 0.57% |
| `com::sun::star::lang::cppu_detail_getUnoType(com::sun::star::lang::XComponent const*) [clone .isra.0]` | libcomphelper.so | 286327881 | 0.50% |
| `term_raw` | libpython3.12.so.1.0 | 269746631 | 0.48% |

**003 公开记录元数据清理：未见函数 142 个，合计 28.47%。**

| 函数 | 库文件名 | 目标 period | 完整 ROI 占比 |
|---|---|---|---|
| `png_write_find_filter` | libpng16.so.16.40.0 | 4820020182 | 9.05% |
| `_PyUnicode_ToLowerFull` | libpython3.12.so.1.0 | 1181208257 | 2.22% |
| `do_upper_or_lower` | libpython3.12.so.1.0 | 940464371 | 1.77% |
| `(anonymous namespace)::InterfaceTypeDescription::~InterfaceTypeDescription()` | libuno_cppuhelpergcc3.so.3 | 525105853 | 0.99% |
| `s_mpv_mul_d_add_prop` | libfreeblpriv3.so | 490281519 | 0.92% |
| `pixman_composite_src_n_8888_asm_neon` | libpixman-1.so.0.42.2 | 429757719 | 0.81% |
| `_PyPegen_expect_token` | libpython3.12.so.1.0 | 392806016 | 0.74% |
| `bitwise_xor_rule` | libpython3.12.so.1.0 | 390545667 | 0.73% |
| `std::_Rb_tree<rtl::OUString, std::pair<rtl::OUString const, rtl::Reference<configmgr::Node> >, std::_Select1st<std::pair<rtl::OUString const, rtl::Reference<configmgr::Node> > >, …` | libconfigmgrlo.so | 362782754 | 0.68% |
| `xmlreader::XmlReader::scanName(char const**)` | libxmlreaderlo.so | 362034946 | 0.68% |

**009 事件手册发布：未见函数 201 个，合计 32.45%。**

| 函数 | 库文件名 | 目标 period | 完整 ROI 占比 |
|---|---|---|---|
| `png_write_find_filter` | libpng16.so.16.40.0 | 13221124244 | 19.00% |
| `pixman_composite_src_8888_8888_asm_neon` | libpixman-1.so.0.42.2 | 1064971704 | 1.53% |
| `unoidl::detail::UnoidlProvider::findEntity(rtl::OUString const&) const` | libunoidllo.so | 434952618 | 0.62% |
| `xmlStrEqual` | etree.cpython-312-aarch64-linux-gnu.so | 424283850 | 0.61% |
| `s_mpv_mul_d_add_prop` | libfreeblpriv3.so | 371459659 | 0.53% |
| `pixman_composite_src_n_8888_asm_neon` | libpixman-1.so.0.42.2 | 322445962 | 0.46% |
| `configmgr::ValueParser::endElement()` | libconfigmgrlo.so | 271490796 | 0.39% |
| `configmgr::GroupNode::GroupNode(configmgr::GroupNode const&, bool)` | libconfigmgrlo.so | 154408110 | 0.22% |
| `std::_Rb_tree<rtl::OUString, std::pair<rtl::OUString const, rtl::Reference<configmgr::Node> >, std::_Select1st<std::pair<rtl::OUString const, rtl::Reference<configmgr::Node> > >, …` | libconfigmgrlo.so | 149001943 | 0.21% |
| `rtl_string_assign` | libuno_sal.so.3 | 135824275 | 0.20% |

**021 庇护所无障碍整改：未见函数 497 个，合计 51.34%。**

| 函数 | 库文件名 | 目标 period | 完整 ROI 占比 |
|---|---|---|---|
| `VerticalFilter._omp_fn.0` | libMagickCore-7.Q16HDRI.so.10.0.2 | 8054283077 | 6.96% |
| `vcl::(anonymous namespace)::ImplScaleConvolutionVer(Bitmap const&, Bitmap&, double const&, vcl::Kernel const&)` | libvcllo.so | 4498309322 | 3.89% |
| `HorizontalFilter._omp_fn.0` | libMagickCore-7.Q16HDRI.so.10.0.2 | 3110449977 | 2.69% |
| `BitmapReadAccess::SetPixelForN24BitTcBgr(unsigned char*, long, BitmapColor const&)` | libvcllo.so | 1862579409 | 1.61% |
| `expandRow(unsigned char*, unsigned char*, int, int, int)` | libpoppler.so.133.0.0 | 1765066367 | 1.52% |
| `vcl::(anonymous namespace)::ImplScaleConvolutionHor(Bitmap const&, Bitmap&, double const&, vcl::Kernel const&)` | libvcllo.so | 1728129377 | 1.49% |
| `pixman_composite_src_8888_8888_asm_neon` | libpixman-1.so.0.42.2 | 1638241511 | 1.42% |
| `Splash::scaleImageYdownXdown(bool (*)(void*, unsigned char*, unsigned char*), void*, SplashColorMode, int, bool, int, int, int, int, SplashBitmap*)` | libpoppler.so.133.0.0 | 1584486401 | 1.37% |
| `decode_mcu_AC_refine` | libjpeg.so.62.4.0 | 1295515376 | 1.12% |
| `rgb_ycc_convert` | libjpeg.so.62.4.0 | 1123735968 | 0.97% |

**026 气候披露图表重建：未见函数 396 个，合计 37.59%。**

| 函数 | 库文件名 | 目标 period | 完整 ROI 占比 |
|---|---|---|---|
| `s_mpv_mul_d_add_prop` | libfreeblpriv3.so | 1026985354 | 1.46% |
| `pixman_composite_src_8888_8888_asm_neon` | libpixman-1.so.0.42.2 | 940457347 | 1.34% |
| `expandRow(unsigned char*, unsigned char*, int, int, int)` | libpoppler.so.133.0.0 | 905703410 | 1.29% |
| `SplashClip::testClipPaths(int, int)` | libpoppler.so.133.0.0 | 839534814 | 1.20% |
| `Splash::scaleImageYdownXdown(bool (*)(void*, unsigned char*, unsigned char*), void*, SplashColorMode, int, bool, int, int, int, int, SplashBitmap*)` | libpoppler.so.133.0.0 | 710605042 | 1.01% |
| `_PyPegen_singleton_seq.isra.0` | libpython3.12.so.1.0 | 623546364 | 0.89% |
| `void (anonymous namespace)::stackBlurVertical<(anonymous namespace)::SumFunction8>((anonymous namespace)::BlurSharedData const&, int, int)` | libvcllo.so | 615142019 | 0.88% |
| `jsimd_huff_encode_one_block_neon` | libjpeg.so.62.4.0 | 557913808 | 0.79% |
| `shift_expr_rule` | libpython3.12.so.1.0 | 544492462 | 0.78% |
| `SplashBitmap::getPixel(int, int, unsigned char*)` | libpoppler.so.133.0.0 | 527967918 | 0.75% |

**029 季度业务回顾发布：未见函数 303 个，合计 42.87%。**

| 函数 | 库文件名 | 目标 period | 完整 ROI 占比 |
|---|---|---|---|
| `oox::drawingml::table::applyTableStylePart(oox::core::XmlFilterBase const&, oox::drawingml::FillProperties&, oox::drawingml::TextCharacterProperties&, oox::drawingml::LineProperti…` | libooxlo.so | 788694859 | 2.00% |
| `oox::PropertyMap::fillSequences(com::sun::star::uno::Sequence<rtl::OUString>&, com::sun::star::uno::Sequence<com::sun::star::uno::Any>&) const` | libooxlo.so | 731549829 | 1.85% |
| `pixman_composite_src_8888_8888_asm_neon` | libpixman-1.so.0.42.2 | 659671424 | 1.67% |
| `std::__detail::_Prime_rehash_policy::_M_need_rehash(unsigned long, unsigned long, unsigned long) const` | libstdc++.so.6.0.30 | 579807158 | 1.47% |
| `pixman_composite_src_n_8888_asm_neon` | libpixman-1.so.0.42.2 | 499658661 | 1.26% |
| `s_mpv_mul_d_add_prop` | libfreeblpriv3.so | 456324822 | 1.15% |
| `void (anonymous namespace)::stackBlurVertical<(anonymous namespace)::SumFunction8>((anonymous namespace)::BlurSharedData const&, int, int)` | libvcllo.so | 302309086 | 0.76% |
| `bitwise_or_rule` | libpython3.12.so.1.0 | 294244957 | 0.74% |
| `std::_Rb_tree<rtl::OUString, std::pair<rtl::OUString const, rtl::Reference<configmgr::Node> >, std::_Select1st<std::pair<rtl::OUString const, rtl::Reference<configmgr::Node> > >, …` | libconfigmgrlo.so | 281849467 | 0.71% |
| `SfxItemPool::CheckItemInfoFlag(unsigned short, unsigned short) const` | libsvllo.so | 266149663 | 0.67% |

以上只新增既有数据的集合统计，没有重跑、导出或重新采样。原任务 profile、原基准函数权重、Topdown 指标及 533 个过程点保持原样。

### 9.6C 热点权重分区、工具归属与分类规则

旧热点阈值与新热点阈值均为完整 ROI 的 0.5%。旧清单先按 DSO 文件名＋完整符号合并，同一函数只要在任一旧基准达到阈值即记为旧热点；旧权重取两者最大值作阈值判断，不把两个独立任务的占比相加或平均。以下四分区覆盖目标全部采样周期，非热点长尾和未解析项都保留。

| 任务 | 旧热点函数 period | 旧低频函数 period | 旧未见函数 period | 未解析 period | 新热点总数 | 其中旧未见热点数 | 未见热点 period |
|---|---|---|---|---|---|---|---|
| 031 | 28223769003 | 2986052311 | 8221561054 | 725948 | 16 | 8 | 6059032507 |
| 037 | 35850439369 | 5229529186 | 15344825225 | 26135206 | 28 | 12 | 11611554714 |
| pdfwf005 | 12893921234 | 5508051645 | 22048404156 | 72871142 | 34 | 16 | 18844678208 |
| 013 | 34327209485 | 18097611579 | 35741255368 | 451232017 | 23 | 9 | 21431612431 |
| 014 | 25412458959 | 16598222742 | 21046999573 | 431395318 | 33 | 13 | 11452586783 |
| 016 | 15599147809 | 26660945194 | 32566096182 | 303889138 | 44 | 16 | 12683018544 |
| 001 | 29152938172 | 11692387821 | 14518658211 | 1412488230 | 24 | 9 | 6974405687 |
| 003 | 24543764984 | 12016580548 | 15161130367 | 1532136337 | 27 | 11 | 10225398544 |
| 009 | 33966499631 | 11276300240 | 22585336882 | 1767157065 | 19 | 5 | 15516792075 |
| 021 | 14464356725 | 39470723281 | 59438505635 | 2401668723 | 33 | 21 | 34950082948 |
| 026 | 15114159327 | 26583828427 | 26391239273 | 2120158553 | 33 | 16 | 10119812169 |
| 029 | 7191495113 | 14749151404 | 16942828292 | 642425826 | 50 | 16 | 6203645283 |

分类只对旧两例均未观察到的已解析函数进行；每个函数只归一个类型和一个工具，分别汇总为两种视图。“工具×类型”交叉分组是第三种视图，不能把三种视图的周期相加。具体规则及每个函数的工具、类型、解释在 comparison.json 的 hotspot_coverage 字段中保留。

明确 DrawingML／对象属性符号归为对象路径；PNG／JPEG 归为编码；ImageMagick、Pillow 和 VCL 的明确 Bitmap／Convolution／Blur 函数归为图像处理；Python、UNO／配置／容器、安全库分别作为运行支撑或已有处理类型。仅有库名且无法解释业务用途的部分不强行标成新操作或新算法。

**031 听证材料包扁平化发布：全部旧未见周期的互斥工具×类型分区。**

| 工具 | 类型 | period | 完整 ROI 占比 |
|---|---|---|---|
| Python | 语言运行时／文本与对象 | 4734780038 | 12.01% |
| PNG | 图片编码／解码 | 3421412927 | 8.68% |
| libfreetype | 字体／文本图形处理 | 59037627 | 0.15% |
| libc | 运行支撑／容器与配置 | 4735344 | 0.01% |
| bash | 运行支撑／容器与配置 | 1594740 | 0.00% |
| Poppler | 页面／像素绘制 | 376 | 0.00% |
| loader | 运行支撑／容器与配置 | 2 | 0.00% |

**037 公交绕行材料修复：全部旧未见周期的互斥工具×类型分区。**

| 工具 | 类型 | period | 完整 ROI 占比 |
|---|---|---|---|
| Python | 语言运行时／文本与对象 | 9125450202 | 16.17% |
| PNG | 图片编码／解码 | 5797867418 | 10.27% |
| Poppler | 页面／像素绘制 | 177454317 | 0.31% |
| libfreetype | 字体／文本图形处理 | 177127053 | 0.31% |
| libc | 运行支撑／容器与配置 | 62052571 | 0.11% |
| bash | 运行支撑／容器与配置 | 4171617 | 0.01% |
| loader | 运行支撑／容器与配置 | 701118 | 0.00% |
| grep | 其他已解析／待归因 | 929 | 0.00% |

**pdfwf005 结算材料包重建：全部旧未见周期的互斥工具×类型分区。**

| 工具 | 类型 | period | 完整 ROI 占比 |
|---|---|---|---|
| ImageMagick | 图片滤波／缩放 | 10519790717 | 25.96% |
| Python | 语言运行时／文本与对象 | 6041501235 | 14.91% |
| PNG | 图片编码／解码 | 5188444521 | 12.80% |
| libc | 运行支撑／容器与配置 | 117126295 | 0.29% |
| libfontconfig | 字体／文本图形处理 | 58730114 | 0.14% |
| libfreetype | 字体／文本图形处理 | 58692247 | 0.14% |
| libgomp.so.1.0.0 | 其他已解析／待归因 | 58061161 | 0.14% |
| loader | 运行支撑／容器与配置 | 3006709 | 0.01% |
| bash | 运行支撑／容器与配置 | 2666933 | 0.01% |
| libselinux.so.1 | 其他已解析／待归因 | 384224 | 0.00% |

**013 采购投标评审发布：全部旧未见周期的互斥工具×类型分区。**

| 工具 | 类型 | period | 完整 ROI 占比 |
|---|---|---|---|
| ImageMagick | 图片滤波／缩放 | 11902511193 | 13.43% |
| PNG | 图片编码／解码 | 8231625041 | 9.29% |
| Python | 语言运行时／文本与对象 | 6494231490 | 7.33% |
| LibreOffice·其他组件 | 运行支撑／容器与配置 | 4648622212 | 5.25% |
| pixman | 页面／像素绘制 | 1376796444 | 1.55% |
| libfontconfig | 字体／文本图形处理 | 1279120900 | 1.44% |
| cairo | 页面／像素绘制 | 414512693 | 0.47% |
| XML 组件 | XML／结构解析 | 392605918 | 0.44% |
| 安全／加密组件 | 运行支撑／安全组件 | 316393017 | 0.36% |
| Poppler | 页面／像素绘制 | 239648244 | 0.27% |
| libucpfile1.so | 其他已解析／待归因 | 130041203 | 0.15% |
| p11-kit-trust.so | 其他已解析／待归因 | 117207354 | 0.13% |
| libc | 运行支撑／容器与配置 | 68290969 | 0.08% |
| libi18nlangtag.so | 其他已解析／待归因 | 46518103 | 0.05% |
| liborcus-parser-0.20.so.0 | 其他已解析／待归因 | 44274021 | 0.05% |
| zlib | 压缩／解压 | 11173377 | 0.01% |
| loader | 运行支撑／容器与配置 | 6954500 | 0.01% |
| bash | 运行支撑／容器与配置 | 5933837 | 0.01% |
| libgomp.so.1.0.0 | 其他已解析／待归因 | 5037684 | 0.01% |
| libsqlite3.so.0.8.6 | 其他已解析／待归因 | 5034467 | 0.01% |
| libxstor.so | 其他已解析／待归因 | 1467252 | 0.00% |
| libstdc++ | 运行支撑／容器与配置 | 715792 | 0.00% |
| LibreOffice·Calc | 表格模型／重算路径 | 714554 | 0.00% |
| lxml | XML／结构解析 | 670412 | 0.00% |
| sed | 其他已解析／待归因 | 427908 | 0.00% |
| oosplash | 其他已解析／待归因 | 407954 | 0.00% |
| libcomphelper.so | 其他已解析／待归因 | 304778 | 0.00% |
| LibreOffice·OOXML | 文档对象／样式路径 | 13087 | 0.00% |
| [vdso] | 其他已解析／待归因 | 964 | 0.00% |

**014 灾害补助公开发布：全部旧未见周期的互斥工具×类型分区。**

| 工具 | 类型 | period | 完整 ROI 占比 |
|---|---|---|---|
| LibreOffice·其他组件 | 运行支撑／容器与配置 | 5617988073 | 8.85% |
| Python | 语言运行时／文本与对象 | 5218962350 | 8.22% |
| PNG | 图片编码／解码 | 4808553703 | 7.57% |
| 安全／加密组件 | 运行支撑／安全组件 | 1231629687 | 1.94% |
| pixman | 页面／像素绘制 | 1180582672 | 1.86% |
| Poppler | 页面／像素绘制 | 918727773 | 1.45% |
| liborcus-parser-0.20.so.0 | 其他已解析／待归因 | 397355800 | 0.63% |
| XML 组件 | XML／结构解析 | 323964486 | 0.51% |
| p11-kit-trust.so | 其他已解析／待归因 | 317914256 | 0.50% |
| cairo | 页面／像素绘制 | 285552641 | 0.45% |
| libfontconfig | 字体／文本图形处理 | 177139574 | 0.28% |
| loader | 运行支撑／容器与配置 | 110658442 | 0.17% |
| lxml | XML／结构解析 | 58645144 | 0.09% |
| libtasn1.so.6.6.3 | 其他已解析／待归因 | 57549423 | 0.09% |
| libcomphelper.so | 其他已解析／待归因 | 57364039 | 0.09% |
| libi18nlangtag.so | 其他已解析／待归因 | 56763309 | 0.09% |
| libicuuc.so.77 | 其他已解析／待归因 | 50076441 | 0.08% |
| libgcc_s-12 | 运行支撑／容器与配置 | 49356174 | 0.08% |
| libxstor.so | 其他已解析／待归因 | 46436839 | 0.07% |
| libpackage2.so | 其他已解析／待归因 | 42582166 | 0.07% |
| libc | 运行支撑／容器与配置 | 21324027 | 0.03% |
| bash | 运行支撑／容器与配置 | 7213504 | 0.01% |
| libsqlite3.so.0.8.6 | 其他已解析／待归因 | 6293631 | 0.01% |
| LibreOffice·Calc | 表格模型／重算路径 | 1967472 | 0.00% |
| ls | 其他已解析／待归因 | 864453 | 0.00% |
| oosplash | 其他已解析／待归因 | 648237 | 0.00% |
| libselinux.so.1 | 其他已解析／待归因 | 447724 | 0.00% |
| libstdc++ | 运行支撑／容器与配置 | 436168 | 0.00% |
| [vdso] | 其他已解析／待归因 | 774 | 0.00% |
| libscriptframe.so | 其他已解析／待归因 | 590 | 0.00% |
| libgpgme.so.11 | 其他已解析／待归因 | 1 | 0.00% |

**016 预测模型情景级联：全部旧未见周期的互斥工具×类型分区。**

| 工具 | 类型 | period | 完整 ROI 占比 |
|---|---|---|---|
| Python | 语言运行时／文本与对象 | 13833312327 | 18.41% |
| LibreOffice·其他组件 | 运行支撑／容器与配置 | 10922030231 | 14.54% |
| pixman | 页面／像素绘制 | 1781869512 | 2.37% |
| 安全／加密组件 | 运行支撑／安全组件 | 1277771229 | 1.70% |
| PNG | 图片编码／解码 | 861639963 | 1.15% |
| libc | 运行支撑／容器与配置 | 852697951 | 1.13% |
| libfontconfig | 字体／文本图形处理 | 731466639 | 0.97% |
| XML 组件 | XML／结构解析 | 574339272 | 0.76% |
| p11-kit-trust.so | 其他已解析／待归因 | 438361418 | 0.58% |
| cairo | 页面／像素绘制 | 322838822 | 0.43% |
| libucpfile1.so | 其他已解析／待归因 | 212744764 | 0.28% |
| lxml | XML／结构解析 | 112017642 | 0.15% |
| libfreetype | 字体／文本图形处理 | 93633056 | 0.12% |
| libdeployment.so | 其他已解析／待归因 | 72008071 | 0.10% |
| LibreOffice·Calc | 表格模型／重算路径 | 70786544 | 0.09% |
| libstdc++ | 运行支撑／容器与配置 | 64515144 | 0.09% |
| libm | 运行支撑／容器与配置 | 63911870 | 0.09% |
| libsqlite3.so.0.8.6 | 其他已解析／待归因 | 60976533 | 0.08% |
| loader | 运行支撑／容器与配置 | 58733547 | 0.08% |
| libpackage2.so | 其他已解析／待归因 | 48979298 | 0.07% |
| libi18nutil.so | 其他已解析／待归因 | 48884032 | 0.07% |
| libi18nlangtag.so | 其他已解析／待归因 | 47299056 | 0.06% |
| bash | 运行支撑／容器与配置 | 10891875 | 0.01% |
| oosplash | 其他已解析／待归因 | 2134085 | 0.00% |
| ls | 其他已解析／待归因 | 930188 | 0.00% |
| libgcc_s-12 | 运行支撑／容器与配置 | 533259 | 0.00% |
| libxsec_xmlsec.so | 其他已解析／待归因 | 509245 | 0.00% |
| grep | 其他已解析／待归因 | 279471 | 0.00% |
| libcomphelper.so | 其他已解析／待归因 | 739 | 0.00% |
| libgpgme.so.11 | 其他已解析／待归因 | 399 | 0.00% |

**001 受控文档发布修复：全部旧未见周期的互斥工具×类型分区。**

| 工具 | 类型 | period | 完整 ROI 占比 |
|---|---|---|---|
| Python | 语言运行时／文本与对象 | 3683925900 | 6.49% |
| LibreOffice·其他组件 | 运行支撑／容器与配置 | 3138430130 | 5.53% |
| PNG | 图片编码／解码 | 3030752044 | 5.34% |
| pixman | 页面／像素绘制 | 1186923024 | 2.09% |
| 安全／加密组件 | 运行支撑／安全组件 | 707053655 | 1.25% |
| libfontconfig | 字体／文本图形处理 | 573849340 | 1.01% |
| lxml | XML／结构解析 | 413126750 | 0.73% |
| cairo | 页面／像素绘制 | 386917934 | 0.68% |
| XML 组件 | XML／结构解析 | 325477200 | 0.57% |
| libcomphelper.so | 其他已解析／待归因 | 286327881 | 0.50% |
| Poppler | 页面／像素绘制 | 176922794 | 0.31% |
| liblangtag-lo.so.1 | 其他已解析／待归因 | 153790181 | 0.27% |
| libc | 运行支撑／容器与配置 | 108512579 | 0.19% |
| LibreOffice·Writer | 文字文档模型／布局路径 | 91904272 | 0.16% |
| zlib | 压缩／解压 | 59051059 | 0.10% |
| libicuuc.so.77 | 其他已解析／待归因 | 53854267 | 0.09% |
| p11-kit-trust.so | 其他已解析／待归因 | 53296300 | 0.09% |
| libpackage2.so | 其他已解析／待归因 | 42644385 | 0.08% |
| libi18nlangtag.so | 其他已解析／待归因 | 37247244 | 0.07% |
| libsqlite3.so.0.8.6 | 其他已解析／待归因 | 3467910 | 0.01% |
| loader | 运行支撑／容器与配置 | 3103981 | 0.01% |
| bash | 运行支撑／容器与配置 | 1543045 | 0.00% |
| liblcms2.so.2.0.16 | 其他已解析／待归因 | 536336 | 0.00% |

**003 公开记录元数据清理：全部旧未见周期的互斥工具×类型分区。**

| 工具 | 类型 | period | 完整 ROI 占比 |
|---|---|---|---|
| PNG | 图片编码／解码 | 4820020182 | 9.05% |
| Python | 语言运行时／文本与对象 | 3632328927 | 6.82% |
| LibreOffice·其他组件 | 运行支撑／容器与配置 | 2990795717 | 5.62% |
| XML 组件 | XML／结构解析 | 913131401 | 1.71% |
| pixman | 页面／像素绘制 | 760148979 | 1.43% |
| 安全／加密组件 | 运行支撑／安全组件 | 655523169 | 1.23% |
| libfontconfig | 字体／文本图形处理 | 308362510 | 0.58% |
| lxml | XML／结构解析 | 293769954 | 0.55% |
| cairo | 页面／像素绘制 | 238792292 | 0.45% |
| libc | 运行支撑／容器与配置 | 126669620 | 0.24% |
| LibreOffice·Writer | 文字文档模型／布局路径 | 119205727 | 0.22% |
| p11-kit-trust.so | 其他已解析／待归因 | 74978093 | 0.14% |
| zlib | 压缩／解压 | 58519817 | 0.11% |
| libsqlite3.so.0.8.6 | 其他已解析／待归因 | 58317335 | 0.11% |
| liblangtag-lo.so.1 | 其他已解析／待归因 | 56992265 | 0.11% |
| libucpfile1.so | 其他已解析／待归因 | 45854826 | 0.09% |
| bash | 运行支撑／容器与配置 | 5871970 | 0.01% |
| loader | 运行支撑／容器与配置 | 1365334 | 0.00% |
| oosplash | 其他已解析／待归因 | 481523 | 0.00% |
| libstdc++ | 运行支撑／容器与配置 | 726 | 0.00% |

**009 事件手册发布：全部旧未见周期的互斥工具×类型分区。**

| 工具 | 类型 | period | 完整 ROI 占比 |
|---|---|---|---|
| PNG | 图片编码／解码 | 13221124244 | 19.00% |
| LibreOffice·其他组件 | 运行支撑／容器与配置 | 3693517607 | 5.31% |
| pixman | 页面／像素绘制 | 1438557076 | 2.07% |
| Python | 语言运行时／文本与对象 | 776783813 | 1.12% |
| 安全／加密组件 | 运行支撑／安全组件 | 720896509 | 1.04% |
| XML 组件 | XML／结构解析 | 639402993 | 0.92% |
| cairo | 页面／像素绘制 | 442991754 | 0.64% |
| lxml | XML／结构解析 | 424283850 | 0.61% |
| p11-kit-trust.so | 其他已解析／待归因 | 277958435 | 0.40% |
| libfontconfig | 字体／文本图形处理 | 179127240 | 0.26% |
| libc | 运行支撑／容器与配置 | 170599892 | 0.25% |
| libucb1.so | 其他已解析／待归因 | 118677377 | 0.17% |
| libsqlite3.so.0.8.6 | 其他已解析／待归因 | 116666318 | 0.17% |
| loader | 运行支撑／容器与配置 | 107334332 | 0.15% |
| LibreOffice·Writer | 文字文档模型／布局路径 | 79516390 | 0.11% |
| libucpfile1.so | 其他已解析／待归因 | 61073412 | 0.09% |
| Poppler | 页面／像素绘制 | 59096332 | 0.08% |
| liblangtag-lo.so.1 | 其他已解析／待归因 | 49219759 | 0.07% |
| bash | 运行支撑／容器与配置 | 6723641 | 0.01% |
| libsigsegv.so.2.0.7 | 其他已解析／待归因 | 1291163 | 0.00% |
| grep | 其他已解析／待归因 | 494240 | 0.00% |
| libcomphelper.so | 其他已解析／待归因 | 505 | 0.00% |

**021 庇护所无障碍整改：全部旧未见周期的互斥工具×类型分区。**

| 工具 | 类型 | period | 完整 ROI 占比 |
|---|---|---|---|
| ImageMagick | 图片滤波／缩放 | 12256573961 | 10.59% |
| LibreOffice·VCL | 图片滤波／缩放 | 11880928811 | 10.26% |
| LibreOffice·其他组件 | 运行支撑／容器与配置 | 9284135909 | 8.02% |
| Poppler | 页面／像素绘制 | 7870243140 | 6.80% |
| JPEG | 图片编码／解码 | 6018802327 | 5.20% |
| Python | 语言运行时／文本与对象 | 5521062715 | 4.77% |
| pixman | 页面／像素绘制 | 2291897795 | 1.98% |
| 安全／加密组件 | 运行支撑／安全组件 | 984636599 | 0.85% |
| LibreOffice·OOXML | 文档对象／样式路径 | 843578603 | 0.73% |
| cairo | 页面／像素绘制 | 486174442 | 0.42% |
| libfontconfig | 字体／文本图形处理 | 379033997 | 0.33% |
| XML 组件 | XML／结构解析 | 274593288 | 0.24% |
| lxml | XML／结构解析 | 234286352 | 0.20% |
| p11-kit-trust.so | 其他已解析／待归因 | 222328418 | 0.19% |
| libm | 运行支撑／容器与配置 | 183577421 | 0.16% |
| libcomphelper.so | 其他已解析／待归因 | 153129839 | 0.13% |
| libucpfile1.so | 其他已解析／待归因 | 118646327 | 0.10% |
| libi18nlangtag.so | 其他已解析／待归因 | 109390545 | 0.09% |
| libc | 运行支撑／容器与配置 | 64175545 | 0.06% |
| zlib | 压缩／解压 | 61966860 | 0.05% |
| libucb1.so | 其他已解析／待归因 | 60674374 | 0.05% |
| libfreetype | 字体／文本图形处理 | 57387604 | 0.05% |
| libstdc++ | 运行支撑／容器与配置 | 56310827 | 0.05% |
| libicuuc.so.77 | 其他已解析／待归因 | 6298196 | 0.01% |
| loader | 运行支撑／容器与配置 | 5274737 | 0.00% |
| libgomp.so.1.0.0 | 其他已解析／待归因 | 5222740 | 0.00% |
| bash | 运行支撑／容器与配置 | 4042713 | 0.00% |
| libsqlite3.so.0.8.6 | 其他已解析／待归因 | 3584341 | 0.00% |
| libselinux.so.1 | 其他已解析／待归因 | 513521 | 0.00% |
| [vdso] | 其他已解析／待归因 | 33688 | 0.00% |

**026 气候披露图表重建：全部旧未见周期的互斥工具×类型分区。**

| 工具 | 类型 | period | 完整 ROI 占比 |
|---|---|---|---|
| LibreOffice·其他组件 | 运行支撑／容器与配置 | 5323242105 | 7.58% |
| Python | 语言运行时／文本与对象 | 5081853187 | 7.24% |
| Poppler | 页面／像素绘制 | 5047036263 | 7.19% |
| LibreOffice·VCL | 图片滤波／缩放 | 2421599746 | 3.45% |
| JPEG | 图片编码／解码 | 1853340083 | 2.64% |
| 安全／加密组件 | 运行支撑／安全组件 | 1499250315 | 2.14% |
| pixman | 页面／像素绘制 | 1467469185 | 2.09% |
| libfontconfig | 字体／文本图形处理 | 722571192 | 1.03% |
| LibreOffice·OOXML | 文档对象／样式路径 | 694500235 | 0.99% |
| XML 组件 | XML／结构解析 | 642724618 | 0.92% |
| lxml | XML／结构解析 | 522277394 | 0.74% |
| cairo | 页面／像素绘制 | 440388319 | 0.63% |
| libicuuc.so.77 | 其他已解析／待归因 | 208724666 | 0.30% |
| libi18nlangtag.so | 其他已解析／待归因 | 111844146 | 0.16% |
| libfreetype | 字体／文本图形处理 | 105178347 | 0.15% |
| libc | 运行支撑／容器与配置 | 86180880 | 0.12% |
| libgcc_s-12 | 运行支撑／容器与配置 | 54820269 | 0.08% |
| libxstor.so | 其他已解析／待归因 | 45053633 | 0.06% |
| libpackage2.so | 其他已解析／待归因 | 39468965 | 0.06% |
| bash | 运行支撑／容器与配置 | 10594091 | 0.02% |
| loader | 运行支撑／容器与配置 | 4826377 | 0.01% |
| libsqlite3.so.0.8.6 | 其他已解析／待归因 | 4641729 | 0.01% |
| libm | 运行支撑／容器与配置 | 2571471 | 0.00% |
| libstdc++ | 运行支撑／容器与配置 | 699157 | 0.00% |
| grep | 其他已解析／待归因 | 363332 | 0.00% |
| libcomphelper.so | 其他已解析／待归因 | 9418 | 0.00% |
| [vdso] | 其他已解析／待归因 | 8946 | 0.00% |
| zlib | 压缩／解压 | 1204 | 0.00% |

**029 季度业务回顾发布：全部旧未见周期的互斥工具×类型分区。**

| 工具 | 类型 | period | 完整 ROI 占比 |
|---|---|---|---|
| LibreOffice·其他组件 | 运行支撑／容器与配置 | 5042223254 | 12.76% |
| Python | 语言运行时／文本与对象 | 3443765689 | 8.71% |
| LibreOffice·OOXML | 文档对象／样式路径 | 1928372571 | 4.88% |
| LibreOffice·VCL | 图片滤波／缩放 | 1256553496 | 3.18% |
| pixman | 页面／像素绘制 | 1159330085 | 2.93% |
| 安全／加密组件 | 运行支撑／安全组件 | 840472782 | 2.13% |
| libstdc++ | 运行支撑／容器与配置 | 637265711 | 1.61% |
| Poppler | 页面／像素绘制 | 604275695 | 1.53% |
| libfontconfig | 字体／文本图形处理 | 428982273 | 1.09% |
| lxml | XML／结构解析 | 357049039 | 0.90% |
| XML 组件 | XML／结构解析 | 346086468 | 0.88% |
| cairo | 页面／像素绘制 | 254752404 | 0.64% |
| p11-kit-trust.so | 其他已解析／待归因 | 225162341 | 0.57% |
| JPEG | 图片编码／解码 | 124203358 | 0.31% |
| libc | 运行支撑／容器与配置 | 121862656 | 0.31% |
| libicuuc.so.77 | 其他已解析／待归因 | 56819576 | 0.14% |
| libgcc_s-12 | 运行支撑／容器与配置 | 53645190 | 0.14% |
| libi18nlangtag.so | 其他已解析／待归因 | 52626760 | 0.13% |
| libsqlite3.so.0.8.6 | 其他已解析／待归因 | 3642065 | 0.01% |
| loader | 运行支撑／容器与配置 | 2544552 | 0.01% |
| bash | 运行支撑／容器与配置 | 2485630 | 0.01% |
| libcap.so.2.69 | 其他已解析／待归因 | 405348 | 0.00% |
| oosplash | 其他已解析／待归因 | 203887 | 0.00% |
| libm | 运行支撑／容器与配置 | 82014 | 0.00% |
| libcomphelper.so | 其他已解析／待归因 | 8842 | 0.00% |
| [vdso] | 其他已解析／待归因 | 6606 | 0.00% |

统计是同一批旧数据的新增分组，不重新采样、不剔除或归一化未知权重，也不按阶段分配通用库周期。主报告的扩展建议为初选，不自动改变任务集合。

### 9.6D Top-10／Top-20 数量、权重与完整未匹配清单

旧参考为 OPM＋TLC 的完整已解析函数并集，包含旧例低频函数。下表的“已见数”按函数身份计数；“已见占 Top-10 周期”以所选十个函数的周期和为分母，“Top-10 占 ROI”以目标完整 ROI 为分母。所有排序按 period 降序，平手按库名＋完整符号排序。

| 任务 | Top-10 已见数 | Top-20 已见数 | Top-10 占 ROI | 已见占 Top-10 周期 |
|---|---|---|---|---|
| 031 | 5/10 | 10/20 | 82.63% | 84.23% |
| 037 | 5/10 | 12/20 | 73.57% | 78.81% |
| pdfwf005 | 7/10 | 10/20 | 63.40% | 45.39% |
| 013 | 7/10 | 13/20 | 57.74% | 65.47% |
| 014 | 8/10 | 14/20 | 46.55% | 80.15% |
| 016 | 7/10 | 14/20 | 23.66% | 70.90% |
| 001 | 7/10 | 12/20 | 58.27% | 85.85% |
| 003 | 7/10 | 14/20 | 63.03% | 79.32% |
| 009 | 8/10 | 14/20 | 71.26% | 71.20% |
| 021 | 5/10 | 9/20 | 38.82% | 57.08% |
| 026 | 7/10 | 10/20 | 38.90% | 89.48% |
| 029 | 6/10 | 14/20 | 22.63% | 69.15% |

以下完整列出每项 Top-20 中旧例未匹配函数。# 为新任务排名，函数数等于 Top-20 实际选取数减已匹配数。仅显示时简写参数，匹配仍使用完整符号；操作关联不代表单独测得该阶段 CPU 成本。

**PDF 031：Top-20 未覆盖 10 个。**

实际链路：build_public_packet.py；PDF 渲染；validate_public_packet.py。 [冻结命令](../docops/payload/tasks/031/recipe.json)

| 工具／操作类别 | 全部未覆盖函数（新任务排名） | 关联操作与解释 |
|---|---|---|
| PNG／图片编码／解码（1 个） | #2 `png_write_find_filter` | 预览图片的读写、编码滤波或颜色转换；旧例已有图片输出，差异在具体编码实现。 |
| Python／Python 运行时（9 个） | #7 `term_rule`；#8 `shift_expr_rule`；#9 `expression_rule`；#10 `tok_get_normal_mode`；#11 `code_hash`；#12 `cfg_to_instr_sequence.isra.0`；#14 `sum_rule`；#17 `bitwise_or_rule`；#20 `bitwise_xor_rule` | Python 代码解析、编译和代码对象处理；服务于构建、校验等脚本，具体脚本归属尚未定位，不是 PDF 文本分词。 |

**PDF 037：Top-20 未覆盖 8 个。**

实际链路：build_bus_detour_packet.py；PDF 渲染；validate_bus_detour_packet.py。 [冻结命令](../docops/payload/tasks/037/recipe.json)

| 工具／操作类别 | 全部未覆盖函数（新任务排名） | 关联操作与解释 |
|---|---|---|
| PNG／图片编码／解码（1 个） | #2 `png_write_find_filter` | 预览图片的读写、编码滤波或颜色转换；旧例已有图片输出，差异在具体编码实现。 |
| Python／Python 运行时（7 个） | #6 `_PyPegen_expect_token`；#7 `star_target_rule`；#9 `astfold_expr`；#10 `compiler_visit_expr1`；#11 `tok_get_normal_mode`；#14 `compiler_visit_stmt`；#15 `atom_rule` | Python 代码解析、编译和代码对象处理；服务于构建、校验等脚本，具体脚本归属尚未定位，不是 PDF 文本分词。 |

**PDF pdfwf005：Top-20 未覆盖 10 个。**

实际链路：rebuild_closeout_binder.py；PDF 检查；图片／拼图／诊断。 [冻结命令](../docops/payload/tasks/pdfwf005/recipe.json)

| 工具／操作类别 | 全部未覆盖函数（新任务排名） | 关联操作与解释 |
|---|---|---|
| ImageMagick／图像缩放／滤波／合成（2 个） | #1 `HorizontalFilter._omp_fn.0`；#2 `VerticalFilter._omp_fn.0` | 缩略图、图片缩放及合成处理；结合任务中的 montage 或转换链解释，不能把每个函数都称为拼图。 |
| PNG／图片编码／解码（3 个） | #3 `png_write_find_filter`；#16 `png_read_filter_row_up`；#19 `ReadOnePNGImage` | 预览图片的读写、编码滤波或颜色转换；旧例已有图片输出，差异在具体编码实现。 |
| Python／Python 运行时（5 个） | #12 `instr_sequence_to_cfg`；#13 `bitwise_xor_rule`；#17 `_PyPegen_fill_token`；#18 `shift_expr_rule`；#20 `term_raw` | Python 代码解析、编译和代码对象处理；服务于构建、校验等脚本，具体脚本归属尚未定位，不是 PDF 文本分词。 |

**Excel 013：Top-20 未覆盖 7 个。**

实际链路：build_public_bid_workbook.py；recalc.py；verify_public_bid_workbook.py；PDF／拼图。 [冻结命令](../docops/payload/tasks/013/recipe.json)

| 工具／操作类别 | 全部未覆盖函数（新任务排名） | 关联操作与解释 |
|---|---|---|
| PNG／图片编码／解码（1 个） | #2 `png_write_find_filter` | 预览图片的读写、编码滤波或颜色转换；旧例已有图片输出，差异在具体编码实现。 |
| ImageMagick／图像缩放／滤波／合成（3 个） | #3 `HorizontalFilter._omp_fn.0`；#5 `VerticalFilter._omp_fn.0`；#16 `CompositeOverImage._omp_fn.0` | 缩略图、图片缩放及合成处理；结合任务中的 montage 或转换链解释，不能把每个函数都称为拼图。 |
| pixman／页面／像素绘制（1 个） | #12 `pixman_composite_src_8888_8888_asm_neon` | 页面图像的缩放、裁剪、抗锯齿、像素读写或合成；关联转 PDF／页面预览，属于已有渲染类型的不同子路径。 |
| libfontconfig／字体处理（1 个） | #14 `FcStrHashIgnoreCase` | 字体匹配、替换等辅助路径；关联文档转换和预览，不据此认定新增分页算法。 |
| LibreOffice·其他组件／公共框架／基础库（1 个） | #20 `rtl::uri::detail::readUcs4` | UNO 类型／属性、配置查询、容器或字符转换等通用支撑；不能直接作为新增文档操作。 |

**Excel 014：Top-20 未覆盖 6 个。**

实际链路：build_disaster_release_v1.py；recalc.py；finalize_disaster_release_ooxml_v3.py；validate_disaster_release_v1.py／渲染。 [冻结命令](../docops/payload/tasks/014/recipe.json)

| 工具／操作类别 | 全部未覆盖函数（新任务排名） | 关联操作与解释 |
|---|---|---|
| PNG／图片编码／解码（1 个） | #2 `png_write_find_filter` | 预览图片的读写、编码滤波或颜色转换；旧例已有图片输出，差异在具体编码实现。 |
| 安全／加密组件／安全组件（1 个） | #5 `s_mpv_mul_d_add_prop` | 安全库内部算术；仅确认组件路径，具体调用目的未定位，不据此宣称任务新增加密操作。 |
| LibreOffice·Calc／文档对象／样式（1 个） | #14 `ScColumnData::GetMostUsedPattern` | 表格样式应用、对象属性组织或单元格样式查询；按具体函数区分 PPT 对象处理与已有 Calc 类型。 |
| pixman／页面／像素绘制（1 个） | #15 `pixman_composite_src_8888_8888_asm_neon` | 页面图像的缩放、裁剪、抗锯齿、像素读写或合成；关联转 PDF／页面预览，属于已有渲染类型的不同子路径。 |
| Poppler／页面／像素绘制（1 个） | #16 `SplashXPathScanner::renderAALine` | 页面图像的缩放、裁剪、抗锯齿、像素读写或合成；关联转 PDF／页面预览，属于已有渲染类型的不同子路径。 |
| Python／Python 运行时（1 个） | #18 `_PyPegen_new_identifier` | Python 代码解析、编译和代码对象处理；服务于构建、校验等脚本，具体脚本归属尚未定位，不是 PDF 文本分词。 |

**Excel 016：Top-20 未覆盖 6 个。**

实际链路：build_forecast_dashboard_v1.py；recalc.py；测试副本切换情景并重算。 [冻结命令](../docops/payload/tasks/016/recipe.json)

| 工具／操作类别 | 全部未覆盖函数（新任务排名） | 关联操作与解释 |
|---|---|---|
| LibreOffice·其他组件／公共框架／基础库（1 个） | #3 `std::_Rb_tree<int, …>::_M_get_insert_unique_pos` | UNO 类型／属性、配置查询、容器或字符转换等通用支撑；不能直接作为新增文档操作。 |
| Python／Python 运行时（2 个） | #6 `_PyPegen_fill_token`；#18 `bitwise_xor_rule` | Python 代码解析、编译和代码对象处理；服务于构建、校验等脚本，具体脚本归属尚未定位，不是 PDF 文本分词。 |
| pixman／页面／像素绘制（1 个） | #7 `pixman_composite_src_8888_8888_asm_neon` | 页面图像的缩放、裁剪、抗锯齿、像素读写或合成；关联转 PDF／页面预览，属于已有渲染类型的不同子路径。 |
| PNG／图片编码／解码（1 个） | #12 `png_write_find_filter` | 预览图片的读写、编码滤波或颜色转换；旧例已有图片输出，差异在具体编码实现。 |
| libc／公共框架／基础库（1 个） | #14 `__mbsrtowcs_l` | UNO 类型／属性、配置查询、容器或字符转换等通用支撑；不能直接作为新增文档操作。 |

**Word 001：Top-20 未覆盖 8 个。**

实际链路：create_packet.py；render_docx.py；结构与渲染检查。 [冻结命令](../docops/payload/tasks/001/recipe.json)

| 工具／操作类别 | 全部未覆盖函数（新任务排名） | 关联操作与解释 |
|---|---|---|
| PNG／图片编码／解码（1 个） | #3 `png_write_find_filter` | 预览图片的读写、编码滤波或颜色转换；旧例已有图片输出，差异在具体编码实现。 |
| LibreOffice·其他组件／公共框架／基础库（2 个） | #6 `cppu::_copyConstructAnyFromData`；#15 `std::_Rb_tree<rtl::OUString, …>::find` | UNO 类型／属性、配置查询、容器或字符转换等通用支撑；不能直接作为新增文档操作。 |
| pixman／页面／像素绘制（2 个） | #8 `pixman_composite_src_8888_8888_asm_neon`；#19 `pixman_composite_src_n_8888_asm_neon` | 页面图像的缩放、裁剪、抗锯齿、像素读写或合成；关联转 PDF／页面预览，属于已有渲染类型的不同子路径。 |
| 安全／加密组件／安全组件（1 个） | #13 `s_mpv_mul_d_add_prop` | 安全库内部算术；仅确认组件路径，具体调用目的未定位，不据此宣称任务新增加密操作。 |
| Python／Python 运行时（1 个） | #14 `code_hash` | Python 代码解析、编译和代码对象处理；服务于构建、校验等脚本，具体脚本归属尚未定位，不是 PDF 文本分词。 |
| libfontconfig／字体处理（1 个） | #20 `FcConfigSubstituteWithPat` | 字体匹配、替换等辅助路径；关联文档转换和预览，不据此认定新增分页算法。 |

**Word 003：Top-20 未覆盖 6 个。**

实际链路：build_public_packet.py；audit_public_packet.py；render_docx.py。 [冻结命令](../docops/payload/tasks/003/recipe.json)

| 工具／操作类别 | 全部未覆盖函数（新任务排名） | 关联操作与解释 |
|---|---|---|
| PNG／图片编码／解码（1 个） | #2 `png_write_find_filter` | 预览图片的读写、编码滤波或颜色转换；旧例已有图片输出，差异在具体编码实现。 |
| Python／文本／XML 处理（2 个） | #6 `_PyUnicode_ToLowerFull`；#7 `do_upper_or_lower` | 字符串大小写转换或 XML 字符串比较；关联构建与检查链，不能仅凭符号锁定某条元数据清理语句。 |
| LibreOffice·其他组件／公共框架／基础库（1 个） | #17 `InterfaceTypeDescription::~InterfaceTypeDescription` | UNO 类型／属性、配置查询、容器或字符转换等通用支撑；不能直接作为新增文档操作。 |
| 安全／加密组件／安全组件（1 个） | #19 `s_mpv_mul_d_add_prop` | 安全库内部算术；仅确认组件路径，具体调用目的未定位，不据此宣称任务新增加密操作。 |
| pixman／页面／像素绘制（1 个） | #20 `pixman_composite_src_n_8888_asm_neon` | 页面图像的缩放、裁剪、抗锯齿、像素读写或合成；关联转 PDF／页面预览，属于已有渲染类型的不同子路径。 |

**Word 009：Top-20 未覆盖 6 个。**

实际链路：build_incident_manual_publication.py；render_docx.py；validate_incident_manual_publication.py。 [冻结命令](../docops/payload/tasks/009/recipe.json)

| 工具／操作类别 | 全部未覆盖函数（新任务排名） | 关联操作与解释 |
|---|---|---|
| PNG／图片编码／解码（1 个） | #2 `png_write_find_filter` | 预览图片的读写、编码滤波或颜色转换；旧例已有图片输出，差异在具体编码实现。 |
| pixman／页面／像素绘制（2 个） | #7 `pixman_composite_src_8888_8888_asm_neon`；#20 `pixman_composite_src_n_8888_asm_neon` | 页面图像的缩放、裁剪、抗锯齿、像素读写或合成；关联转 PDF／页面预览，属于已有渲染类型的不同子路径。 |
| LibreOffice·其他组件／公共框架／基础库（1 个） | #14 `unoidl::detail::UnoidlProvider::findEntity` | UNO 类型／属性、配置查询、容器或字符转换等通用支撑；不能直接作为新增文档操作。 |
| lxml／文本／XML 处理（1 个） | #16 `xmlStrEqual` | 字符串大小写转换或 XML 字符串比较；关联构建与检查链，不能仅凭符号锁定某条元数据清理语句。 |
| 安全／加密组件／安全组件（1 个） | #18 `s_mpv_mul_d_add_prop` | 安全库内部算术；仅确认组件路径，具体调用目的未定位，不据此宣称任务新增加密操作。 |

**PPT 021：Top-20 未覆盖 11 个。**

实际链路：build_public_shelter_briefing.py；validate_public_shelter_briefing.py；soffice.py／图片／拼图。 [冻结命令](../docops/payload/tasks/021/recipe.json)

| 工具／操作类别 | 全部未覆盖函数（新任务排名） | 关联操作与解释 |
|---|---|---|
| ImageMagick／图像缩放／滤波／合成（2 个） | #2 `VerticalFilter._omp_fn.0`；#5 `HorizontalFilter._omp_fn.0` | 缩略图、图片缩放及合成处理；结合任务中的 montage 或转换链解释，不能把每个函数都称为拼图。 |
| LibreOffice·VCL／图像缩放／滤波／合成（2 个） | #4 `vcl::ImplScaleConvolutionVer`；#11 `vcl::ImplScaleConvolutionHor` | 缩略图、图片缩放及合成处理；结合任务中的 montage 或转换链解释，不能把每个函数都称为拼图。 |
| LibreOffice·VCL／页面／像素绘制（1 个） | #9 `BitmapReadAccess::SetPixelForN24BitTcBgr` | 页面图像的缩放、裁剪、抗锯齿、像素读写或合成；关联转 PDF／页面预览，属于已有渲染类型的不同子路径。 |
| Poppler／页面／像素绘制（3 个） | #10 `expandRow`；#14 `Splash::scaleImageYdownXdown`；#20 `Splash::scaleImageYupXupBilinear` | 页面图像的缩放、裁剪、抗锯齿、像素读写或合成；关联转 PDF／页面预览，属于已有渲染类型的不同子路径。 |
| pixman／页面／像素绘制（1 个） | #13 `pixman_composite_src_8888_8888_asm_neon` | 页面图像的缩放、裁剪、抗锯齿、像素读写或合成；关联转 PDF／页面预览，属于已有渲染类型的不同子路径。 |
| JPEG／图片编码／解码（2 个） | #15 `decode_mcu_AC_refine`；#18 `rgb_ycc_convert` | 预览图片的读写、编码滤波或颜色转换；旧例已有图片输出，差异在具体编码实现。 |

**PPT 026：Top-20 未覆盖 10 个。**

实际链路：build_climate_disclosure.py；转 PDF／图片；qa_climate_disclosure.py。 [冻结命令](../docops/payload/tasks/026/recipe.json)

| 工具／操作类别 | 全部未覆盖函数（新任务排名） | 关联操作与解释 |
|---|---|---|
| 安全／加密组件／安全组件（1 个） | #7 `s_mpv_mul_d_add_prop` | 安全库内部算术；仅确认组件路径，具体调用目的未定位，不据此宣称任务新增加密操作。 |
| pixman／页面／像素绘制（1 个） | #9 `pixman_composite_src_8888_8888_asm_neon` | 页面图像的缩放、裁剪、抗锯齿、像素读写或合成；关联转 PDF／页面预览，属于已有渲染类型的不同子路径。 |
| Poppler／页面／像素绘制（4 个） | #10 `expandRow`；#13 `SplashClip::testClipPaths`；#14 `Splash::scaleImageYdownXdown`；#20 `SplashBitmap::getPixel` | 页面图像的缩放、裁剪、抗锯齿、像素读写或合成；关联转 PDF／页面预览，属于已有渲染类型的不同子路径。 |
| Python／Python 运行时（2 个） | #16 `_PyPegen_singleton_seq.isra.0`；#19 `shift_expr_rule` | Python 代码解析、编译和代码对象处理；服务于构建、校验等脚本，具体脚本归属尚未定位，不是 PDF 文本分词。 |
| LibreOffice·VCL／图像缩放／滤波／合成（1 个） | #17 `stackBlurVertical<SumFunction8>` | 缩略图、图片缩放及合成处理；结合任务中的 montage 或转换链解释，不能把每个函数都称为拼图。 |
| JPEG／图片编码／解码（1 个） | #18 `jsimd_huff_encode_one_block_neon` | 预览图片的读写、编码滤波或颜色转换；旧例已有图片输出，差异在具体编码实现。 |

**PPT 029：Top-20 未覆盖 6 个。**

实际链路：build_release_deck.py；validate_release_deck.py；转 PDF／图片。 [冻结命令](../docops/payload/tasks/029/recipe.json)

| 工具／操作类别 | 全部未覆盖函数（新任务排名） | 关联操作与解释 |
|---|---|---|
| LibreOffice·OOXML／文档对象／样式（2 个） | #3 `oox::drawingml::table::applyTableStylePart`；#5 `oox::PropertyMap::fillSequences` | 表格样式应用、对象属性组织或单元格样式查询；按具体函数区分 PPT 对象处理与已有 Calc 类型。 |
| pixman／页面／像素绘制（2 个） | #8 `pixman_composite_src_8888_8888_asm_neon`；#13 `pixman_composite_src_n_8888_asm_neon` | 页面图像的缩放、裁剪、抗锯齿、像素读写或合成；关联转 PDF／页面预览，属于已有渲染类型的不同子路径。 |
| libstdc++／公共框架／基础库（1 个） | #10 `std::__detail::_Prime_rehash_policy::_M_need_rehash` | UNO 类型／属性、配置查询、容器或字符转换等通用支撑；不能直接作为新增文档操作。 |
| 安全／加密组件／安全组件（1 个） | #14 `s_mpv_mul_d_add_prop` | 安全库内部算术；仅确认组件路径，具体调用目的未定位，不据此宣称任务新增加密操作。 |

### 9.6E 三例补充方案的集合核验与严格最小组合

候选参考为旧 OPM／TLC 并集加 Excel 013、PPT 021、PPT 029 的完整已解析函数身份集合。对每个目标重新划分已见、未见、未解析 period；未解析分母不变。选中任务匹配自身属于集合构造，单独标记，不当作跨任务或未来输入验证。

| 目标 | 自身在新增参考中 | 原未见 period | 新增参考后未见 period | 新增参考后未见 % | 未解析 period |
|---|---|---|---|---|---|
| 031 | False | 8221561054 | 607612160 | 1.54% | 725948 |
| 037 | False | 15344825225 | 1668296901 | 2.96% | 26135206 |
| pdfwf005 | False | 22048404156 | 1186585775 | 2.93% | 72871142 |
| 013 | True | 35741255368 | 0 | 0.00% | 451232017 |
| 014 | False | 21046999573 | 5554011349 | 8.75% | 431395318 |
| 016 | False | 32566096182 | 11034723585 | 14.69% | 303889138 |
| 001 | False | 14518658211 | 4709234483 | 8.29% | 1412488230 |
| 003 | False | 15161130367 | 5564207846 | 10.45% | 1532136337 |
| 009 | False | 22585336882 | 4439254804 | 6.38% | 1767157065 |
| 021 | True | 59438505635 | 0 | 0.00% | 2401668723 |
| 026 | False | 26391239273 | 7085682422 | 10.09% | 2120158553 |
| 029 | True | 16942828292 | 0 | 0.00% | 642425826 |

Top-20 目标集合：十二项已解析函数各取前二十，减去旧并集，再对身份去重。候选任务提供完整函数集合，允许函数在候选中低频出现，不能据此保证同样的热点权重。

原目标 58 个；三例匹配 49 个，剩 9 个：

| 库文件名 | 仍未匹配的完整函数 |
|---|---|
| etree.cpython-312-aarch64-linux-gnu.so | `xmlStrEqual` |
| libc.so.6 | `__mbsrtowcs_l` |
| libfontconfig.so.1.12.1 | `FcConfigSubstituteWithPat` |
| libpython3.12.so.1.0 | `_PyPegen_singleton_seq.isra.0` |
| libpython3.12.so.1.0 | `_PyUnicode_ToLowerFull` |
| libpython3.12.so.1.0 | `compiler_visit_stmt` |
| libpython3.12.so.1.0 | `do_upper_or_lower` |
| libuno_cppuhelpergcc3.so.3 | `(anonymous namespace)::InterfaceTypeDescription::~InterfaceTypeDescription()` |
| libunoidllo.so | `unoidl::detail::UnoidlProvider::findEntity(rtl::OUString const&) const` |

严格集合覆盖枚举全部候选子集，结果仅适用于已保存函数，不等于未来请求或全部操作的最小基准。Top-20 目标的最小新增数为 7，共有 8 套并列方案：

| 方案 | 新增任务 |
|---|---|
| 1 | 037、013、014、003、021、026、029 |
| 2 | 037、013、016、003、021、026、029 |
| 3 | 037、013、001、003、021、026、029 |
| 4 | 037、013、003、009、021、026、029 |
| 5 | pdfwf005、013、016、003、021、026、029 |
| 6 | 013、014、016、003、021、026、029 |
| 7 | 013、016、001、003、021、026、029 |
| 8 | 013、016、003、009、021、026、029 |

若目标改为全部已解析未见函数（含长尾），目标身份数 1664，最小新增数 12。这不是要求实际增加全部任务，而是说明全函数收集与操作级代表性是不同目标。

以 pdfwf005、021、029 替代三例组合时，原 Top-20 目标仍剩 12 个未匹配；两套方案逐目标完整周期保留在 coverage_augmentation。各目标比例独立计算，不合并不同任务的 period 或简单平均为代表性分数。

### 9.7 来源与离线复算

- 原始基准：`analysis/hotspots/comparison-inputs-pdf5-20261027.json`。
- 原始统一环境 perf：`analysis/docops/raw/unified-symbol-check-20261103T1703Z/campaign.json`。
- 离线符号结果：`analysis/docops/raw/unified-symbol-check-20261103T1703Z/offline-symbol-enrichment-v1/enrichment.json`。
- 统一环境 DevKit：`analysis/docops/raw/unified-topdown-20261104-v1/campaign.json`。
- 本节机器结果：`analysis/docops/processed/task-operation-expansion-20261104/comparison.json`。

```bash
python3 -B analysis/docops/operation_comparison.py --update --publish
```

该命令只读取既有 JSON、日志与冻结 recipe，重建比较表、曲线及追加章节，不启动 workload、容器、perf、DevKit 或模型。

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
