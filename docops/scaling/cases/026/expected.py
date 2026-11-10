"""Independent expectation generator for scaled PPTX 026 variants.

Reads the frozen units.json prepared material and derives the expected page
layout, per-unit titles, the per-unit native trend chart data, the per-unit
inventory/supplier table facts, the required speaker notes and the public style
tokens. It deliberately shares NO value computation with the in-replay builder;
both read the same material facts independently.
"""
from __future__ import annotations

from pathlib import Path

from .. import common
from . import synth

PAGES_PER_UNIT = synth.PAGES_PER_UNIT
BANNED = list(synth.BANNED)

TITLE_BASE = [
    "Climate Disclosure Briefing",
    "Disclosure Boundary",
    "Corrected Emissions Inventory",
    "Emissions Trend Chart",
    "Assurance Status",
    "Transition Action Plan",
    "Supplier Engagement Register",
    "Board Actions",
    "Publication Style Guide",
]

STYLE = {
    "title_font": "Aptos Display",
    "title_bold": True,
    "title_slide_title_color": "FFFFFF",
    "content_title_color": "0F172A",
    "title_slide_bg": "0F172A",
    "content_bg": "F8FAFC",
    "accent_fill": "22C55E",
    "table_header_fill": "166534",
    "table_header_font_color": "FFFFFF",
    "chart_type": "COLUMN_CLUSTERED",
}

INVENTORY_HEADER = ["Metric", "Public value", "Reporting basis", "Status"]
SUPPLIER_HEADER = ["Supplier segment", "Engagement focus", "Evidence status", "Next step"]


def titles_for(unit: dict) -> list[str]:
    out = []
    for base in TITLE_BASE:
        if base == TITLE_BASE[0]:
            out.append(f"{unit['name']} {base}")
        else:
            out.append(base)
    return out


def inventory_rows(unit: dict) -> list[list[str]]:
    status = unit["submission_status"]
    return [
        ["Metric", "Public value", "Reporting basis", "Status"],
        ["Base year", str(unit["base_year"]), "Annual trend baseline", status],
        ["Scope 1 emissions", f"{unit['scope_1']:,} tCO2e", "Operational control", status],
        ["Scope 2 emissions", f"{unit['scope_2_location_based']:,} tCO2e",
         "Location-based", status],
        ["Renewable electricity", f"{unit['renewable_electricity_pct']}%",
         "Share of electricity use", status],
    ]


def chart_for(unit: dict) -> dict:
    return {
        "categories": unit["trend_years"],
        "series_name": synth.SERIES_NAME,
        "values": [float(value) for value in unit["trend_values"]],
    }


def compute(units_path: Path) -> dict:
    data = common.load_json(units_path)
    units = data["units"]
    n = len(units)
    total = n * PAGES_PER_UNIT
    groups = []
    for index, unit in enumerate(units):
        page_start = index * PAGES_PER_UNIT + 1
        groups.append({
            "id": unit["id"],
            "name": unit["name"],
            "page_start": page_start,
            "page_end": page_start + PAGES_PER_UNIT - 1,
            "titles": titles_for(unit),
            "chart": chart_for(unit),
            "chart_page": page_start + 3,
            "inventory_page": page_start + 2,
            "supplier_page": page_start + 6,
            "inventory_rows": inventory_rows(unit),
            "supplier_rows": [SUPPLIER_HEADER] + unit["supplier_rows"],
            "board_decisions": unit["board_decisions"],
            "transition_actions": unit["transition_actions"],
            "assurance_owner": unit["assurance_owner"],
            "submission_status": unit["submission_status"],
            "required_texts": [
                unit["name"],
                str(unit["base_year"]),
                f"{unit['scope_1']:,} tCO2e",
                f"{unit['scope_2_location_based']:,} tCO2e",
                f"{unit['renewable_electricity_pct']}%",
                unit["assurance_owner"],
                unit["submission_status"],
            ],
            "notes": unit["notes"],
        })
    return {
        "schema": "docops-scaling-expectation-v1",
        "variant_task_id": data["variant_task_id"],
        "kind": "pptx",
        "total_pages": total,
        "pages_per_unit": PAGES_PER_UNIT,
        "chart_categories": data["chart_categories"],
        "series_name": data["series_name"],
        "style": STYLE,
        "banned_text": BANNED,
        "units": groups,
    }


def write_expected(variant_task_id: str, units_path: Path, expected_path: Path) -> dict:
    result = compute(units_path)
    result["variant_task_id"] = variant_task_id
    common.write_json(expected_path, result)
    return result
