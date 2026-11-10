"""Independent expectation generator for scaled Excel 014 variants.

This module implements the eligibility / priority / review-status business rules
from scratch in Python. It deliberately shares NO computation code with the
in-replay build script (which only writes Excel formula strings). The resulting
expected.json is frozen at preparation time and the replay loop never
regenerates it.
"""
from __future__ import annotations

import datetime
from pathlib import Path

from openpyxl import load_workbook

from .. import common
from . import synth

PUBLIC_FIELDS = synth.PUBLIC_FIELDS
CAPS = synth.CAPS
CORRECTIONS = synth.CORRECTIONS
DAMAGE_POINTS = {"Destroyed": 40, "Major": 30, "Moderate": 20, "Minor": 10}
INCOME_POINTS = {"Low": 20, "Moderate": 10, "High": 0}


def parse_date(value) -> datetime.date:
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    return datetime.date.fromisoformat(str(value).strip())


def read_records(input_path: Path) -> list[dict]:
    wb = load_workbook(input_path, data_only=True)
    ws = wb["Raw Intake PRIVATE"]
    headers = [c.value for c in ws[1]]
    indexes = {f: headers.index(f) for f in PUBLIC_FIELDS}
    records = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row[indexes["Application ID"]]:
            continue
        records.append({f: row[indexes[f]] for f in PUBLIC_FIELDS})
    wb.close()
    return records


def dedupe(records: list[dict]) -> list[dict]:
    latest = {}
    for rec in records:
        app_id = rec["Application ID"]
        date_value = parse_date(rec["Inspection Date"])
        prior = latest.get(app_id)
        if prior is None or date_value > prior[0]:
            latest[app_id] = (date_value, rec)
    result = [entry[1] for entry in latest.values()]
    result.sort(key=lambda r: int(r["Application ID"].split("-")[1]))
    return result


def corrected(records: list[dict]) -> list[dict]:
    out = []
    for rec in records:
        updated = dict(rec)
        updated.update(CORRECTIONS.get(rec["Application ID"], {}))
        out.append(updated)
    return out


def eligible_amount(rec: dict) -> int:
    return max(0, min(int(rec["Repair Estimate"]) - int(rec["Insurance Proceeds"]),
                      CAPS[rec["Damage Category"]]))


def priority_score(rec: dict) -> int:
    vuln = 20 if rec["Vulnerable Household"] == "Yes" else 0
    return vuln + DAMAGE_POINTS[rec["Damage Category"]] + INCOME_POINTS[rec["Income Band"]]


def review_status(rec: dict, amount: int) -> str:
    if amount >= 20000:
        return "Senior Review"
    if rec["Appeal Flag"] == "Yes":
        return "Appeal Review"
    return "Ready"


def compute(input_path: Path) -> dict:
    records = corrected(dedupe(read_records(input_path)))
    n = len(records)

    rows = []
    for rec in records:
        amount = eligible_amount(rec)
        rows.append({
            "app_id": rec["Application ID"],
            "county": rec["County"],
            "damage": rec["Damage Category"],
            "repair": int(rec["Repair Estimate"]),
            "insurance": int(rec["Insurance Proceeds"]),
            "income": rec["Income Band"],
            "vulnerable": rec["Vulnerable Household"],
            "appeal": rec["Appeal Flag"],
            "inspection_date": parse_date(rec["Inspection Date"]).isoformat(),
            "eligible_amount": amount,
            "priority_score": priority_score(rec),
            "review_status": review_status(rec, amount),
        })

    total_eligible = sum(r["eligible_amount"] for r in rows)
    senior = sum(1 for r in rows if r["review_status"] == "Senior Review")
    appeal_review = sum(1 for r in rows if r["review_status"] == "Appeal Review")
    # Keep the exact aggregate value, matching what a spreadsheet engine caches for
    # AVERAGE(...). The workbook's number format ("0.0") is display-only; rounding
    # the oracle to 2 decimals would fail against the real recalculated value.
    avg_priority = sum(r["priority_score"] for r in rows) / n

    rollup = {}
    for county in synth.COUNTIES:
        subset = [r for r in rows if r["county"] == county]
        rollup[county] = [
            len(subset),
            sum(r["eligible_amount"] for r in subset),
            sum(1 for r in subset if r["review_status"] == "Senior Review"),
        ]

    appeal_queue = [
        {
            "app_id": r["app_id"],
            "county": r["county"],
            "damage": r["damage"],
            "eligible_amount": r["eligible_amount"],
            "review_status": r["review_status"],
        }
        for r in rows if r["appeal"] == "Yes"
    ]

    last = n + 1
    appeal_last = len(appeal_queue) + 1
    return {
        "schema": "docops-scaling-expectation-v1",
        "kind": "xlsx",
        "n": n,
        "valid_ids": [r["app_id"] for r in rows],
        "records": rows,
        "dashboard": {
            "total_applications": n,
            "total_eligible_amount": total_eligible,
            "senior_review_count": senior,
            "appeal_review_count": appeal_review,
            "average_priority_score": avg_priority,
        },
        "county_rollup": rollup,
        "appeal_queue": appeal_queue,
        "appeal_count": len(appeal_queue),
        "table_refs": {
            "Eligibility Register": f"A1:L{last}",
            "County Rollup": "A1:D5",
            "Appeal Queue": f"A1:E{appeal_last}",
            "Publication Controls": "A1:D5",
        },
        "conditional_formats": {
            "K2:K{last}".format(last=last): ["greaterThanOrEqual", "70"],
            "J2:J{last}".format(last=last): ["greaterThan", "0"],
        },
        "register_range_end": last,
        "auto_filter": {"Eligibility Register": f"A1:L{last}",
                        "County Rollup": "A1:D5",
                        "Appeal Queue": f"A1:E{appeal_last}",
                        "Publication Controls": "A1:D5"},
        "chart": {
            "type": "BarChart",
            "categories": "'County Rollup'!$A$2:$A$5",
            "values": "'County Rollup'!$C$2:$C$5",
        },
        "formula_count": 3 * n + 5 + 4 * 3 + 2 * len(appeal_queue),
        "forbidden_phrases": [
            "DRAFT", "PRIVATE", "legal hold", "raw intake", "duplicate scratch",
            "unverified hardship narrative", "personal phone", "applicant name",
            "Alicia Tran", "Marta Ruiz", "Lena Okafor", "N. Fork",
            "Minor correction pending", "moderate income pending",
        ],
        "currency_ranges": {
            "register_cols": [4, 5, 10],
            "county_col": 3,
            "appeal_col": 4,
            "controls_col": 2,
            "dashboard_cells": ["B5"],
        },
        "coverage": {
            "damage": {d: sum(1 for r in rows if r["damage"] == d) for d in CAPS},
            "income": {i: sum(1 for r in rows if r["income"] == i) for i in ("Low", "Moderate", "High")},
            "vulnerable": {"Yes": sum(1 for r in rows if r["vulnerable"] == "Yes"),
                           "No": sum(1 for r in rows if r["vulnerable"] == "No")},
            "appeal": {"Yes": sum(1 for r in rows if r["appeal"] == "Yes"),
                       "No": sum(1 for r in rows if r["appeal"] == "No")},
            "review_status": {s: sum(1 for r in rows if r["review_status"] == s)
                              for s in ("Senior Review", "Appeal Review", "Ready")},
            "eligible_zero": sum(1 for r in rows if r["eligible_amount"] == 0),
            "priority_ge_70": sum(1 for r in rows if r["priority_score"] >= 70),
        },
    }


def write_expected(variant_task_id: str, input_path: Path, expected_path: Path) -> dict:
    result = compute(input_path)
    result["variant_task_id"] = variant_task_id
    common.write_json(expected_path, result)
    return result
