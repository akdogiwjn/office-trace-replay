# reviewed 交付复核

实际镜像、两档 016 输出及其只读复核、36 项证据索引、7 项构建索引、419 项镜像构建 payload 输入绑定均核验一致。110 项小型定向测试全部通过；未重跑 workload 或 profiler。

仍有两处旧要求没有接入主流程：

1. **F5 冻结一致性门槛。** acceptance_problems 的 frozen_ok 在 main 中被写死为 True。最终虽然计算 frozen_after，却未比较。mock 注入前 old 后 new，总状态仍 passed、退出码 0。
2. **F7 恢复复用绑定。** reuse 分支直接 accepted=True，绕过 bindings_ok 及归档检查。mock 已完成的归档目录不存在、bindings_ok=False，主流程不调用该检查，仍 passed、退出码 0；没有调用 workload。

当前实际归档哈希与冻结材料是正确的，因此不推翻两档真实运行结果。但这两项不能标为完整修复。现有 helper 单测通过不足以覆盖主流程接线，需补 main/resume 故障注入。

两项均属于宿主验收驱动收尾，可用临时目录与 mock 修复验证；无需因此重建镜像、重跑两档 016 或其他任务。
