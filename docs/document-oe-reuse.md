> 此文描述最初的衍生配方机制。当前两个旧基线直接执行 `legacy/document-oe` 的原程序，完全不使用此机制。以 README 和 suites/default.json 为当前入口定义。

# 复用 document-oe 的范围

容器实际目录为 `/opt/document-bench`。复制执行器 `bin/run_document_scene_loop.py`，SHA256 为 `5f1f5d2ab8075ded5b12e6e583c0b733de09389c2c60d63d735c82a252d7c2d1`；已确认本地 snapshot 中的版本一致。该原文件完整保留在 `vendor/document-oe/`。

沿用的部分：四阶段 `scene-key-operations-v2`、read/write/exec 调用格式、重置 seed/workspace、逐阶段执行、Bash 命令、超时后终止进程组，以及成功 business report 检查。没有重写其底层命令执行机制。

新增的部分：七个 dataset 配置、canonical/输入/helper/source 的 hash 绑定、显式成功链选择、每轮 LO profile 与 TLC scratch 清理、原绝对路径恢复、冻结 verifier 的完整独立验收、逐调用日志和新输出保存。默认循环次数为 1，避免沿用旧程序的 20,000 次默认值。

基础镜像采用 `document-oe-snapshot:20260827` 的固定 image ID `sha256:6eb99c666aab38fb4ba04886e42e5db219f4ac71d6e8307cd743b049a6a60111`，不是运行容器最初的 1.49GB 镜像：后者没有当前 Python 3.12.3 venv。snapshot 中的 Python prefix、venv、动态库、Office、字体和 Poppler 一并保留，构建无需外网。

两个必须处理的环境细节：

- 系统默认 Python 为 3.11.6，因此镜像明确设置 venv 的 PATH 和绝对 Python entrypoint。
- symbols 版 Office 的默认 profile 指向安装目录，因此用独立启动包装器指定标准用户 profile，让冻结 Skill 安装的 macro 被真实 Office 读取。旧 document-oe 自己的重算桥也显式指定 profile，但它含旧 TLC 的缓存检查规则，不能直接替换当前七个用例的冻结 Skill。

新项目不修改旧 `document-oe` 容器，也不修改 `office-trace-bench` 的 Agent、Prompt、Skill、manifest 或 canonical pack。
