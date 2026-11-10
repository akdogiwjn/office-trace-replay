# 审计收尾：宿主验收驱动接线修复（F5-main / F7-main）与主流程回归

针对 `scaling-reviewed-closeout-audit-20261107`（review.md / review.json）定位的两处宿主驱动接线问题，
完成修复并补主流程回归测试。仅修改宿主驱动与相关测试；未重建镜像、未重跑 workload、未启动 Agent/perf/DevKit、
未更新正式报告/HTML、未提交推送、未删除历史材料，保留工作树既有改动。

## 1. 修改文件及主流程接入位置

| 文件 | 修改 | 接入位置 |
|---|---|---|
| `docops/scaling/functional_fixed_campaign.py` | 新增 `frozen_snapshot()`/`frozen_consistency_problems(state)`（从实际文件计算冻结绑定，基线缺失/计算异常/任一键变化均给明确原因）；`main()` 在任何任务前先做冻结一致性检查，`frozen_ok` 由实际结果得出（不再写死 True）；最终成功前再次计算并比较，变化则进不了 passed。`attempt_archive_problems(task, attempt_dir)` 全面核验归档目录/轮次/步骤/工件大小+SHA/recipe/input/expected/image；`bindings_ok` 改由它派生。`main()` 拆分 `process_one_task(task,campaign,state,frozen_ok)`：run / reverify / reuse 三条路径均过同一验收门槛；reuse 前先核 archive 绑定，缺离线复验则进入 reverify（不重跑 workload），reuse 还需校验渲染证据与 campaign 归档索引（`verify_existing_index`）；main 按 `selected_tasks` 处理 | `functional_fixed_campaign.py` 的 `main()`、`process_one_task()`、`attempt_archive_problems()`、`frozen_consistency_problems()` |
| `docops/scaling/functional_all_campaign.py` | 同类最小修复：`reuse_binding_ok()` 在 already_ok 复用前核验归档轮次/工件/recipe；`frozen_consistency_problems()` 在 finally 中比较 preflight.frozen_before 与当前材料，不一致置 failed 并非零退出 | `already_ok()`、`finally` 收尾 |

## 2. 两个复现修复后的返回码与落盘状态

1) frozen_before=old、frozen_after=new（审计复现 F5-main）
   - 修复前：exit 0、campaign passed。
   - 修复后：`main(['--campaign-dir', tmp, '--resume'])` 返回 1；`campaign.json` 落盘 `status=failed`、`frozen_problems` 列出“frozen material changed: …”；workload 调用次数 0。
   - 回归测试：`TestMainFlow.test_frozen_changed_rejected`。

2) 已完成任务归档目录不存在，bindings_ok 原调用 0 次仍 reuse 成功（F7-main）
   - 修复前：reuse 直接 accepted=True、exit 0、bindings_ok 调用 0。
   - 修复后：`process_one_task` 在 reuse/reverify 前调用 `attempt_archive_problems` → “archive results dir missing”→ exit 1、campaign `status=failed`、`task_failure` 含 “reuse blocked: …”、workload 调用 0、归档核验确实被调用（调用次数 >0）。
   - 回归测试：`TestMainFlow.test_reuse_archive_missing_rejected`。

## 3. 主流程测试与既有回归结果

- 新增 `TestMainFlow`（真实 `main()`/resume，mock `run_task`/`post_verify`/`verify_existing_index`，无 Docker、无 workload）覆盖：
  - 冻结前后不同→非零退出/campaign failed；
  - 冻结基线缺失→失败；冻结计算异常（tree_sha 抛错）→失败；
  - 归档目录不存在→reuse 拒绝且归档核验被调用；
  - 工件大小/哈希不符→reuse 拒绝；
  - recipe/expected/input/image 身份任一不符→reuse 拒绝；
  - 验证报告缺失→进入 reverify（仅离线复验，workload 不重跑）；渲染证据缺失→reverify 后因渲染契约失败；
  - 归档索引篡改→reuse 拒绝；
  - 绑定完整且证据合格→正常复用（exit 0、campaign passed、bindings 被调用、workload/verify 0 次）；
  - 所有拒绝/恢复路径 workload 调用 0、旧证据字节不变、无删除。
- 测试断言：返回码、落盘 task/campaign 状态、必需核验被调用、workload 调用次数、原证据内容未变化。
- 既有回归：host `test_functional_fixed`（39）+ `test_pilot_image_selection`（12）+ `test_scaling_016`（36）+ `test_scaling_009`（24）=111 全绿；image venv `test_scaling_029/016/009`（82）全绿；完整 image venv 229 项全绿（skipped=2）。`git diff --check` rc=0，全部改动文件语法编译通过。

## 4. 历史证据保护情况

- 未对历史 campaign 执行可写 resume/收尾；只读核验当前真实 campaign `results/docops/scaling-reviewed-functional-20261106T074957Z-a3703f71/`：`verify_existing_index` 通过（36 文件）、`frozen_before==frozen_after`、`status=passed`、`frozen_consistency_problems` 当前为空。
- 未重建镜像、未重跑 016 或其他任务、未删除任何历史材料/镜像/容器、未改写历史哈希。受保护材料（官方/round1/round2）与既有证据保持不变。
- 保留工作树既有未提交改动，未使用 git reset/clean。

## 5. 未完成项

- 本轮不重建镜像、不重跑 workload（按授权边界）；`functional_all_campaign.py` 为同类最小修复，未用于本轮真实采集。
- 若发现必须修改业务材料/测量口径/重跑任务才能解决的问题，本轮未触发；无其他未完成项。完成后停止，不自动开始采集。
