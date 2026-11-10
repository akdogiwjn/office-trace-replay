"""Independent expectation generator for scaled PPTX 029 variants.

Reads the frozen units.json prepared material and derives the expected page
layout for the FROZEN parent's eight public slide types (title, agenda,
market_context, kpi, risks, mitigation, decision, appendix) parameterized per
business unit: the per-unit tables (KPI, customer-risk, mitigation with colored
status), the agenda slide (six sections with per-unit absolute slide numbers
and owners), the market-context callout bodies, the decision request statements
and speaker note, the appendix data notes, the public footer and the preserved
locked legal page facts. It deliberately shares NO value computation with the
in-replay builder; both read the same material facts independently.
"""
from __future__ import annotations

from pathlib import Path

from .. import common
from . import synth

PAGES_PER_UNIT = synth.PAGES_PER_UNIT
TITLES = list(synth.TITLES)
FORBIDDEN_PATTERNS = list(synth.FORBIDDEN_PATTERNS)

KPI_HEADER = synth.KPI_HEADER
RISK_HEADER = synth.RISK_HEADER
MITIGATION_HEADER = synth.MITIGATION_HEADER
AGENDA_HEADER = synth.AGENDA_HEADER

FOOTER = "QBR Release | 2026-06-05"


def compute(units_path: Path) -> dict:
    data = common.load_json(units_path)
    units = data["units"]
    n = len(units)
    total = n * PAGES_PER_UNIT + 1
    groups = []
    for index, unit in enumerate(units):
        page_start = index * PAGES_PER_UNIT + 1
        owners = unit.get("owners", synth.AGENDA_OWNERS)
        agenda_rows = [
            ["Market Context", str(page_start + 2), owners[0]],
            ["KPI Snapshot", str(page_start + 3), owners[1]],
            ["Customer Risks", str(page_start + 4), owners[2]],
            ["Mitigation Plan", str(page_start + 5), owners[0]],
            ["Decision Request", str(page_start + 6), owners[1]],
            ["Appendix - Data Notes", str(page_start + 7), owners[2]],
        ]
        groups.append({
            "id": unit["id"],
            "name": unit["name"],
            "page_start": page_start,
            "page_end": page_start + PAGES_PER_UNIT - 1,
            "titles": TITLES,
            "market_page": page_start + 2,
            "kpi_page": page_start + 3,
            "risk_page": page_start + 4,
            "mitigation_page": page_start + 5,
            "decision_page": page_start + 6,
            "appendix_page": page_start + 7,
            "agenda_table": [AGENDA_HEADER] + agenda_rows,
            "kpi_table": [KPI_HEADER] + unit["kpi_rows"],
            "risk_table": [RISK_HEADER] + unit["risk_rows"],
            "mitigation_table": [MITIGATION_HEADER] + unit["mitigation_rows"],
            "decision_statements": [row[0] for row in unit["decision_rows"]],
            "decision_note": unit["decision_note"],
            "market_headline": unit["market_headline"],
            "market_callouts": unit["market_callouts"],
            "market_lens": unit["market_lens"],
            "data_notes": unit["data_notes"],
            "data_currency": unit["data_currency"],
            "page_notes": unit["page_notes"],
            "required_texts": [
                unit["name"],
                unit["id"],
                unit["arr_text"],
                f"{unit['nrr']}%",
            ],
        })
    return {
        "schema": "docops-scaling-expectation-v1",
        "variant_task_id": data["variant_task_id"],
        "kind": "pptx",
        "total_pages": total,
        "pages_per_unit": PAGES_PER_UNIT,
        "footer": FOOTER,
        "release_date": data["release_date"],
        "legal_slide": data["legal_slide"],
        "forbidden_patterns": FORBIDDEN_PATTERNS,
        "units": groups,
    }


def write_expected(variant_task_id: str, units_path: Path, expected_path: Path) -> dict:
    result = compute(units_path)
    result["variant_task_id"] = variant_task_id
    common.write_json(expected_path, result)
    return result
