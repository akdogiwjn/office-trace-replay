# Agent 轨迹版镜像构建与功能验收

正式标签：`office-trace-replay:agent-traces`。实际镜像 ID：`sha256:4baef1363ba99a994e17e93fe6a32c904cdb5cb349487adfa2fb13ba42301499`。

安装态、七个 workload 的单轮功能验证及五个新用例的独立验收均已获得成功证据。

| 用例 | 请求/完成/成功/失败 | 循环验证 | 独立验收 |
|---|---|---|---|
| irs_w4 | 1/1/1/0 | 通过 | 通过（103 项），输出哈希不变 |
| sba1919 | 1/1/1/0 | 通过 | 通过（123 项），输出哈希不变 |
| opm | 1/1/1/0 | 通过 | 不另加独立验收；保留旧循环 verifier |
| tlc | 1/1/1/0 | 通过 | 不另加独立验收；保留旧循环 verifier |
| egrid | 1/1/1/0 | 通过 | 通过（152 项），输出哈希不变 |
| hr_metro | 1/1/1/0 | 通过 | 通过（117 项），输出哈希不变 |
| industry_productivity | 1/1/1/0 | 通过 | 通过（111 项），输出哈希不变 |

PDF 均为实际填写 N=10。七个用例均只有一轮功能记录，不是性能测量。

**IRS W-4 复用边界：**它在首次构建镜像中完成一次成功运行；随后仅修复循环外 `audit.py` 的私有 Skill 导入路径。最终镜像对这份既有输出做只读独立复验通过，没有重新填写/渲染。其余六项在最终镜像执行。本报告没有宣称七项均在最终镜像重新实跑。

修复的两项打包问题：BuildKit 对裸 image ID 的解析，以及 PDF 独立验收器的私有工具导入。未修改 Agent helper、原 Skill、原始输入或旧 43 个 workload 文件。

测试 52 passed / 0 skipped / 0 failed / 0 errors。五项审计的 workspace 只读挂载，报告另存，输出前后哈希一致。新旧入口均来自镜像内文件，没有源码挂载。

原始功能试跑产物已按最新数据保留策略清理；本文与 JSON 保留构建时的资格结论。冻结 provenance/suite 中的导入状态是历史快照；当前运行资格以本报告及 JSON 为准。镜像内 README 是构建前快照，构建后的资格记录保存在宿主仓库。

构建时的完整 campaign 已清理；保留[机器可读验收](image-qualification-agent-traces.json)。当前每例五次实际运行的证据见[测量索引](../analysis/topdown/CAMPAIGN.md)。

未采集热点或 Topdown，未调用 LLM，未生成新 Agent trace，未提交或推送。
