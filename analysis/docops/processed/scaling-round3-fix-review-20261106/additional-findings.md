# 补充审计：验收门槛与证据保护

本次在上一轮四项发现之外，新增四项应一并收尾的问题。

| 项 | 发现 | 证据/影响 |
|---|---|---|
| F5 | 复核失败不阻断总成功；渲染计数仅记录，冻结前后未作通过门槛 | mock 注入 rc=1、passed=false、图片 0 张，main 仍 exit=0/status=passed |
| F6 | 索引计算之后又修改 campaign.json | 临时新 campaign 调用真实函数必报 index readback mismatch；失败记录仍写 full_readback_passed=true。已交付 234 项索引实测有效，不混淆历史数据与驱动缺陷 |
| F7 | 恢复时可能删旧结果并重跑 | run_task 开始删除已有 results；create_clean 删除同名容器；post_verify 失败会使 already_ok=false。仅静态核对，未触发删除 |
| F8 | 029 锁定法律页的样式未验 | 在临时副本把法律页背景和两段字体全部改红，真实 checker 仍 errors=[]；原文件只读未改 |

低优先级边界：009 稳定性标记使用迭代次数而非实际收敛比较，最后一次收敛被标不稳定，未收敛也不在该步骤直接失败；当前两档均第 2 次收敛。构建器检查基础 tag ID，但实际 build 未传不可变 BASE_IMAGE，后续构建应显式 pin；本轮记录的基础镜像身份正确。

建议与前四项一次修复并补故障反例。除前述 016 说明公式需要更新输出外，本批新增问题可通过 fixture/mock、只读离线复核解决，无需把 24 项全部重跑。
