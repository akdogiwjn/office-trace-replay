# DocOps 统一镜像：官方调试符号检索与精确匹配核验

当前镜像：`sha256:57483856a27942ffd4aef853950ca66b00c12b0787aae6c1dac74371d03e6164`。

结论：10 个官方 openEuler 24.03 LTS SP3 aarch64 调试包，覆盖 12 个目标 ELF；逐文件 build-id、AArch64 架构及 .symtab 均核对通过。所有目标符号文件也包含 .debug_info。版本相同仅用于筛选，最终接受依据是 ELF build-id 一致。

| 组件 | 已安装版本 | 匹配目标 | 结果 |
|---|---|---|---|
| ImageMagick-debuginfo | 7.1.2.9-1.oe2403sp3 | `libMagickCore-7.Q16HDRI.so.10.0.2`, `png.so`, `jpeg.so` | build-id 完全匹配 |
| cairo-debuginfo | 1.18.0-2.oe2403sp3 | `libcairo.so.2.11800.0` | build-id 完全匹配 |
| fontconfig-debuginfo | 2.15.0-2.oe2403sp3 | `libfontconfig.so.1.12.1` | build-id 完全匹配 |
| libjpeg-turbo-debuginfo | 3.0.1-2.oe2403sp3 | `libjpeg.so.62.4.0` | build-id 完全匹配 |
| libpng-debuginfo | 1.6.40-3.oe2403sp3 | `libpng16.so.16.40.0` | build-id 完全匹配 |
| nss-debuginfo | 3.94.0-8.oe2403sp3 | `libfreeblpriv3.so` | build-id 完全匹配 |
| openssl-debuginfo | 3.0.12-31.oe2403sp3 | `libcrypto.so.3.0.12` | build-id 完全匹配 |
| p11-kit-debuginfo | 0.25.0-2.oe2403sp3 | `p11-kit-trust.so` | build-id 完全匹配 |
| pixman-debuginfo | 0.42.2-1.oe2403sp3 | `libpixman-1.so.0.42.2` | build-id 完全匹配 |
| sqlite-debuginfo | 3.42.0-4.oe2403sp3 | `libsqlite3.so.0.8.6` | build-id 完全匹配 |

## lxml 的边界

当前 lxml 6.1.2 的 etree、_elementpath 来自 PyPI manylinux wheel，不属于系统 RPM。核对 PyPI 6.1.2 的 176 个发布工件，未发现单独的调试符号工件；公开检索也未找到与当前两个 build-id 精确匹配的符号文件。此处结论是暂未找到，不推断符号永远无法取得。其他发行版或自行重编译的同版本 lxml，不能直接当作现有 wheel 的匹配符号。

## 后续可做的事

可将已验证的符号文件作为分析侧调试目录，离线重新解析现有 perf.data，无需重新运行 workload 或采集。实际未解析比例下降多少，需完成离线解析后确认；找到符号不保证补齐所有栈帧。

本次只做检索、下载、提取和身份核验。没有安装调试 RPM、修改镜像或运行库、重导出 perf、修改原 profile、重跑 workload 或采集器。用户此前要求停止后续采集的边界保持有效。

## 来源与复核文件

- [openEuler 官方发行说明：debuginfo 软件源](https://docs.openeuler.org/en/docs/24.03_LTS_SP3/server/releasenotes/releasenotes/os_installation.html)
- [官方 aarch64 调试仓库元数据](https://repo.openeuler.org/openEuler-24.03-LTS-SP3/debuginfo/aarch64/repodata/repomd.xml)
- [GDB 官方说明：独立调试文件与 build-id](https://www.sourceware.org/gdb/current/onlinedocs/gdb.html/Separate-Debug-Files.html)
- [lxml 6.1.2 官方发布工件](https://pypi.org/project/lxml/6.1.2/#files)
- `installed-targets.json`：当前镜像的库版本、build-id、SHA256、debuglink。
- `candidates.json`：官方仓库候选包信息；primary 元数据 SHA256 已与 repomd 核对。
- `search-results.json`：包下载 URL、SHA256 和每个调试 ELF 的精确匹配结果。
- `packages/`、`debugfiles/`：本次下载的官方包及选出的目标符号，只是检索材料，尚未装入分析环境。
- `query-installed.py`、`verify-candidates.py`：本次核验脚本。
