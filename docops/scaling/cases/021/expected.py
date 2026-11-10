"""Independent expectation generator for scaled PPTX 021 variants.

Reads the frozen regions.json prepared material and derives the expected page
layout, per-region titles, required public facts and links. The replay loop
never regenerates this file; validate_public_shelter_briefing_variant.py
consumes it.
"""
from __future__ import annotations

from pathlib import Path

from .. import common
from . import synth

TITLE_BASE = [
    "Emergency Shelter Public Briefing",
    "Corrected Shelter Network",
    "Accessibility Map",
    "Transit Access Updates",
    "Service Animal and Medical Equipment",
    "Hotline and Web Links",
    "Update Log",
    "Accessibility Checklist",
]
PAGES_PER_REGION = synth.PAGES_PER_REGION
BANNED = list(synth.BANNED)
FOOTER = "Public Shelter Accessibility Briefing | 2026"


def titles_for(region: dict) -> list[str]:
    out = []
    for base in TITLE_BASE:
        if base == TITLE_BASE[0]:
            out.append(base)
        else:
            out.append(f"{base} — {region['name']}")
    return out


def required_texts_for(region: dict) -> list[str]:
    shelter = region["shelter_count"]
    accessible = region["accessible_count"]
    share = round(accessible / shelter * 100)
    return [
        region["name"],
        str(shelter),
        str(accessible),
        f"{share}%",
        region["hotline"],
        region["website"],
        region["email"],
        region["update_date"],
    ]


def compute(regions_path: Path) -> dict:
    data = common.load_json(regions_path)
    regions = data["regions"]
    total = len(regions) * PAGES_PER_REGION
    groups = []
    allowed_links = set()
    for index, region in enumerate(regions):
        page_start = index * PAGES_PER_REGION + 1
        groups.append({
            "id": region["id"],
            "name": region["name"],
            "shelter_count": region["shelter_count"],
            "accessible_count": region["accessible_count"],
            "hotline": region["hotline"],
            "website": region["website"],
            "email": region["email"],
            "update_date": region["update_date"],
            "page_start": page_start,
            "page_end": page_start + PAGES_PER_REGION - 1,
            "titles": titles_for(region),
            "required_texts": required_texts_for(region),
            "links": [region["website"], f"mailto:{region['email']}"],
        })
        allowed_links.add(region["website"])
        allowed_links.add(f"mailto:{region['email']}")
    return {
        "schema": "docops-scaling-expectation-v1",
        "variant_task_id": data["variant_task_id"],
        "kind": "pptx",
        "total_pages": total,
        "pages_per_region": PAGES_PER_REGION,
        "footer": FOOTER,
        "banned_text": BANNED,
        "style": {
            "title_font": "Aptos Display",
            "title_bold": True,
            "title_slide_title_color": "FFFFFF",
            "content_title_color": "102A43",
            "title_slide_bg": "102A43",
            "content_bg": "F7FBFF",
            "accent_fill": "F59E0B",
            "table_header_fill": "0B5CAD",
            "table_header_font_color": "FFFFFF",
        },
        "minimum_alt_text_length": 25,
        "regions": groups,
        "allowed_links": sorted(allowed_links),
    }


def write_expected(variant_task_id: str, regions_path: Path, expected_path: Path) -> dict:
    result = compute(regions_path)
    common.write_json(expected_path, result)
    return result
