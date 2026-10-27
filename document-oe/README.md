# document-oe 旧用例组件

本目录单独保存旧 OPM/PDF 与 TLC/XLSX 的执行材料，入口 `run.py --scene pdf|xlsx`。它与 `../agent` 一起装入项目根目录唯一 Dockerfile 构建的同一镜像；不需要独立仓库、第二个镜像或兄弟目录运行依赖。

`assets/` 中的 43 个 workload 文件按原冻结 SHA256、大小和模式复制，包含 recipe、输入、Skill、业务 verifier、缓存 CSV 导出等。原 document-oe 容器完全不动。只有 executor 使用 2026-08-13 保存的独立循环执行器，来源及哈希在 `lock.json` 单列，不声称与后来的统一 runner 字节相同。

本组件安装到 `/opt/office-trace-replay/document-oe`，冻结 workload 另按原路径安装到 `/opt/document-bench`，保证 JSON 内命令和脚本绝对路径不变。入口运行前核对安装文件，持有与新五例相同的 OS 锁，恢复旧 Skill 链接后再执行，支持新旧入口在同一容器顺序使用。不会修改旧业务脚本。

静态校验：`python3 -B document-oe/run.py --validate-only`（从项目根目录）。公开入口默认 1 轮；PDF 默认 1 份，可选 10 份。内部旧 executor 仍保留其直接调用时的历史默认值。

构建与运行命令见根 README；本组件无独立 Dockerfile。当前尚未在整合后的新镜像重新运行旧 workload。
