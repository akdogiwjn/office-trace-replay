#!/usr/bin/env python3
"""Write the conclusions from current profiles, coverage, and residual evidence."""
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(relative):
    return json.loads((ROOT / relative).read_text())


def merged(profile, field):
    total = sum(d["total_period"] for d in profile["repeats"].values())
    values = defaultdict(float)
    for data in profile["repeats"].values():
        for key, value in data[field].items():
            values[key] += value * data["total_period"] / total
    return values


def percent(value):
    return f"{value:.1%}"


def main():
    profiles = load("processed/all-profiles.json")
    coverage = load("processed/coverage.json")
    residual = load("processed/unconfirmed-residual-decomposition.json")["datasets"]
    claims = load("processed/claims-verification.json")
    lines = [
        "# 最终结论：旧 OPM/TLC 用例的计算机制覆盖范围", "",
        "在当前冻结 suite、Python 3.12.3 和相同采集设置下，新旧用例存在大量共同的原生函数、"
        "运行时机制和部分栈前缀。证据支持旧 OPM/TLC 对这些计算机制具有覆盖价值；"
        "不支持把不同输入视为相同工作负载，或将全部旧性能结论和优化收益直接推广到新数据集。", "",
        "本分析比较离线 replay 的用户态 cycles:u 采样 period，覆盖完整后代进程/线程。"
        "10 个配置各有两次 native 采集；没有重新生成 Agent trace。"
        "实际采集镜像 ID 未记录，v9/运行时配置由计划、runner hash 和已有验收提供来源旁证。", "",
        "## XLSX：共同机制存在，工作量分布有变化", "",
        "| 数据集 | 旧执行路径 | 共同原生机制 | 规范化栈前缀匹配 | 路径∪机制 | 尚未确认覆盖 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for cid in ("retail", "manufacturing", "hr"):
        c = coverage[cid]["merged"]
        lines.append(f"| {cid} | {percent(c['direct_path_share'])} | "
                     f"{percent(c['mechanism_evidence_share'])} | "
                     f"{percent(c['normalized_stack_prefix_fingerprint_match_share'])} | "
                     f"{percent(c['coverage_union_share'])} | {percent(c['uncovered_share'])} |")
    lines += ["", "路径、机制和栈前缀是不同证据维度，不能相加。共享 recalc 及其允许包含的"
              "后代形成一部分旧路径覆盖；新 helper 和 verifier 的不同文件身份不等于不同原生计算机制。", "",
              "| 用户态 cycles 权重 | TLC | Retail | Manufacturing | HR |",
              "|---|---:|---:|---:|---:|"]
    proc = {cid: merged(profiles[cid], "process_layer")
            for cid in ("tlc", "retail", "manufacturing", "hr")}
    for label, roles in (("业务 verifier", ("xlsx-verify",)),
                         ("LibreOffice 及其线程", ("soffice.bin", "lo-thread"))):
        lines.append("| " + label + " | " + " | ".join(
            percent(sum(proc[cid].get(role, 0) for role in roles))
            for cid in ("tlc", "retail", "manufacturing", "hr")) + " |")
    lines += ["", "新 XLSX 的验证进程权重明显高于 TLC；Retail、Manufacturing 的 LibreOffice"
              "权重也更高。因此，旧分析识别出的 Python/原生库计算路径仍有参考价值，"
              "各路径的权重和主导关系需要按数据集重新判断。文件规模、结构和生成结果不同，"
              "不能把差异直接归因于行业。", "", "## 余量：大部分已有相似函数或栈证据", "",
              "| 数据集 | 余量占 ROI | 余量中 R1+R2 | R4 占 ROI | R5 占 ROI |",
              "|---|---:|---:|---:|---:|"]
    for cid in ("retail", "manufacturing", "hr"):
        d = residual[cid]
        cats = d["categories"]
        similar = cats["R1"]["residual_share"] + cats["R2"]["residual_share"]
        lines.append(f"| {cid} | {percent(d['computed_residual_share'])} | {percent(similar)} | "
                     f"{percent(cats['R4']['roi_share'])} | {percent(cats['R5']['roi_share'])} |")
    lines += ["", "R1 是合格栈前缀匹配，R2 只有共同叶函数；R4 是符号已解析但机制分类"
              "尚不具体，R5 是未知或质量受限。它们没有自动并入确定覆盖率。"
              "Retail、Manufacturing 的 R3 为零，HR 仅 2 个采样 period；这只是当前分类粒度和"
              "旧参考样本内未观察到实质性的 R3 权重，不能证明不存在不同算法或新的业务操作。", "",
              "Manufacturing 的余量在两次采集中约为 32.3%/38.9%，R4 约占 ROI 的 6.4%；"
              "该波动和未细分部分应保留在任何代表性论述中。", "",
              "## PDF：匹配记录规模后存在共同工具计算路径", "",
              "| 配置 | 旧执行路径 | 共同原生机制 | 栈前缀匹配 | 路径∪机制 |",
              "|---|---:|---:|---:|---:|"]
    for cid in ("irs_w4-n1", "sba1919-n1", "irs_w4-n10", "sba1919-n10"):
        c = coverage[cid]["merged"]
        lines.append(f"| {cid} | {percent(c['direct_path_share'])} | "
                     f"{percent(c['mechanism_evidence_share'])} | "
                     f"{percent(c['normalized_stack_prefix_fingerprint_match_share'])} | "
                     f"{percent(c['coverage_union_share'])} |")
    lines += ["", "W-4/SBA 与相同 N 的 OPM 比较。填写、图像处理/编码和 Poppler 原生路径"
              "有共同证据；表单页数、字段和数据规模改变了各路径权重。N=1 和 N=10 不能混用，"
              "共同库/栈前缀也不证明具体表单逻辑相同。", "", "## 旧结论能推广到哪里", "",
              "原生函数和相应机制的共同存在有采样证据；精确占比、Python 上层业务操作、"
              "调度行为和优化效果是不同层级的问题。旧百分比不应作为所有新用例的固定比例。", "",
              "| 验证状态 | 结论记录数 |", "|---|---:|"]
    counts = Counter(c["status"] for c in claims)
    labels = {"supported": "支持", "partially-supported": "部分支持",
              "not-supported": "不支持", "insufficient-evidence": "证据不足",
              "not-applicable": "不适用"}
    for status in ("supported", "partially-supported", "not-supported", "insufficient-evidence", "not-applicable"):
        lines.append(f"| {labels[status]} | {counts[status]} |")
    lines += ["", f"上述是 {len(claims)} 条 claim×dataset 记录，并非同等数量的独立科学结论。"
              "完整原文、证据和适用范围见 [逐条验证表](../processed/claims-verification.json)。"
              "缺少 scheduler trace 的串行性判断、测量范围不同的 IPC 对比和未测量的优化收益"
              "继续保留证据缺口。", "", "## 证据边界与冻结", "",
              "本结果是当前 suite 的计算热点覆盖分析，不是行业性能排名、Spreadsheet 准确率评测，"
              "也不是旧优化收益可直接迁移的证明。ROI 通过 marker/stdout 估计对齐；"
              "py-spy 每配置仅一次，W-4 N=1 collector 异常保留为失败；历史逐进程文件 hash 未采集。", "",
              "栈前缀最多 8 帧、至少 4 帧，DSO 归为类别。当前版排除了无同地址实体帧的内联前缀；"
              "历史修正前基线保存在 [history/residual-baseline-v1](../history/residual-baseline-v1/)。"
              "覆盖定义和原余量数值保留，指纹统计由修正后的统一规则重算。", "",
              "代码、汇总 JSON、压缩详细画像及恢复脚本随仓库提交。原始 perf/monitor 数据留在本地，"
              "由 raw/index.json 标识；仅 clone 仓库无法重新验证原始采样。复核命令见 [README](../README.md)。", ""]
    target = ROOT / "reports/final-conclusions.md"
    target.write_text("\n".join(lines))
    print(f"wrote {target}")


if __name__ == "__main__":
    main()
