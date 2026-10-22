# 瘦身源码与离线资产

`main` 保留完整源码和历史，不强推或改写既有历史。`slim-v12` 是独立的无历史发布分支：它保留全部分析代码、已提交的最新/历史分析结果、压缩画像和轻量验收证据，只外置大于等于 1 MiB 的运行输入、canonical 大对象和离线 wheel。原项目本地文件和 raw/results 不删除。

完整 main 的普通 clone 仍会下载原历史。要获得瘦身版，明确指定单分支：

```bash
git clone --single-branch --branch slim-v12 --depth 1 <repository> office-trace-replay-slim
```

该命令仅在 slim-v12 已发布到该 remote 后可用；本地生成分支不等于已经发布。也可以直接解压交付目录中的 `office-trace-replay-slim-v12.tar.gz`，不需要 Git。

## 离线恢复与构建

必须把瘦身源码和 `office-trace-replay-assets-v12.tar` 成对保存/传递。资产包不是 perf raw，不包含完整实验目录，也不包含 Docker 镜像。

```bash
cd office-trace-replay-slim
python3 distribution/assets.py restore --bundle /path/to/office-trace-replay-assets-v12.tar
python3 distribution/assets.py verify
python3 replay/entry.py --validate-only

# 需要新构建时显式使用新 tag；此命令不是瘦身验收的一部分
make image IMAGE=office-trace-replay:openeuler-v13
```

恢复只依赖 Python 标准库，无网络、Git LFS 或官方站点下载。资产按 SHA256 去重，恢复到原路径并核验字节和大小。已有相同文件保持不动，已有不同文件拒绝覆盖；错误包、损坏对象和路径逃逸被拒绝。不会修改 expected、canonical manifest、业务 helper、分析算法或冻结预期 hash。

未来离线构建仍需本地已有锁定的 v12 基础镜像。现有 v12 镜像不重建、不更名；若换机器，需要另行转移镜像。保留了 v12 的本机可继续使用原构建流程。

也可从已导出的本地对象目录恢复：

```bash
python3 distribution/assets.py restore --store /path/to/asset-store
```

完整 main 已有全部文件，可再次创建新的资产副本（拒绝覆盖已有目录/包）：

```bash
python3 distribution/assets.py export --store /external/new-store --bundle /external/new-assets.tar
```

## 分析和数据边界

分析目录不参与本次外置：已有报告、历史基线、压缩 profiles、来源映射和分析代码继续随 slim 源码提交。原始 perf/monitor、实验 workspace 和完整产物本来就仅在采集机保留，本次不移动、不删除、不重新解析。

需要展开历史压缩画像时，仍使用原来的 `analysis/hotspot-comparison/scripts/profile_artifacts.py restore`。需要重新读取原始采样的分析仍须使用原采集机的 raw；瘦身不能凭报告补回此前已删除的采样。

恢复后可直接用原 SHA256/manifest/project-lock 验证输入、canonical 对象、Skill 和分析工件。此版本只改变交付与存储方式，不声明重新完成性能采集或 workload 回归。

不要在现有 main 工作目录直接切换到 slim 分支来清理文件；使用独立 clone、worktree 或源码解压目录。瘦身包不包含既有 main 的大对象历史，原 main 和本机完整数据继续保留。
