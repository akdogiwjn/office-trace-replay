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
