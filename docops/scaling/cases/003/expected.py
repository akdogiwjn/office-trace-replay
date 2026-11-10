"""Independent expectation generator for scaled Word 003 variants.

Reads the frozen ``units.json`` prepared material and derives the full expected
structure of the rebuilt public packet: headings, per-unit determination facts,
aggregate tables, forbidden/required content and document-level controls. The
builder reads the same units.json but produces content through the OOXML
pipeline; this module shares NO computation with the builder (it never writes
OOXML). The resulting expected.json is frozen at preparation time.
"""
from __future__ import annotations

from pathlib import Path

from .. import common
from . import synth

CAP = synth.CAP
INCIDENT_DATE = synth.INCIDENT_DATE
DEADLINE = synth.DEADLINE
CONTACT = synth.CONTACT
CATEGORIES = synth.CATEGORIES

PUBLIC_TITLE = "Public Release Packet: Water Main Break Claims"
PUBLIC_AUTHOR = "Public Records Office"
PUBLIC_SUBJECT = "Clean public release packet"
PUBLIC_FOOTER = "Public Records Release | Water Main Break Claims | 2026"

# Document-level headings that always exist, in order, around the per-unit block.
FIXED_HEADINGS_BEFORE = [
    PUBLIC_TITLE,
    "Release Summary",
    "Corrected Determination Facts",
    "Corrected Claim Determinations",
]
FIXED_HEADINGS_AFTER = [
    "Claim Category Table",
    "Notification Workflow",
    "Redaction and Metadata Checklist",
    "Public Appendix Index",
]

# Aggregate determination facts table (derived from the frozen units.json).
def determination_facts_rows(n: int) -> list[list[str]]:
    return [
        ["Incident date", INCIDENT_DATE],
        ["Deduplicated claim count", str(n)],
        ["Reimbursable cap per eligible claim", "$650"],
        ["Public contact", CONTACT],
        ["Response deadline", DEADLINE],
    ]


def category_table_rows(units: list[dict]) -> list[list[str]]:
    counts = {cat: sum(1 for u in units if u["category"] == cat) for cat in CATEGORIES}
    rows = []
    for cat in CATEGORIES:
        rows.append([cat, str(counts[cat]), "Included in aggregate"])
    rows.append(["Total", str(len(units)), "Public count"])
    return rows


def checklist_rows() -> list[list[str]]:
    return [
        ["Claimant identities", "Names and claim-level identifiers excluded", "Complete"],
        ["Home addresses", "Residential addresses removed", "Complete"],
        ["Phone numbers", "Personal numbers removed", "Complete"],
        ["Settlement analysis", "Legal strategy discussion excluded", "Complete"],
        ["Tracked changes", "Changes resolved and structural markers removed", "Complete"],
        ["Review comments", "Comment text and relationships deleted", "Complete"],
        ["Document properties", "Public release metadata only", "Complete"],
        ["Working labels", "Earlier labels removed from content and footer", "Complete"],
    ]


def compute(units_path: Path) -> dict:
    data = common.load_json(units_path)
    units = data["units"]
    n = len(units)

    headings = list(FIXED_HEADINGS_BEFORE)
    for unit in units:
        headings.append(f"Unit {unit['id']} — {unit['category']}")
    headings.extend(FIXED_HEADINGS_AFTER)

    page_break_headings = [
        "Corrected Claim Determinations",
    ]
    for unit in units:
        page_break_headings.append(f"Unit {unit['id']} — {unit['category']}")
    page_break_headings.extend(["Redaction and Metadata Checklist", "Public Appendix Index"])

    unit_sections = []
    for unit in units:
        unit_sections.append({
            "id": unit["id"],
            "claimant": unit["claimant"],
            "address": unit["address"],
            "phone": unit["phone"],
            "category": unit["category"],
            "right_amount": unit["right_amount"],
            "right_status": unit["right_status"],
            "required_public": [
                unit["id"],
                f"${unit['right_amount']}",
                unit["category"],
                unit["right_status"],
            ],
            "forbidden_private": [
                unit["claimant"], unit["address"], unit["phone"], unit["note"],
            ],
        })

    # Global forbidden content: frozen parent private/working labels plus the
    # per-unit private values (everything must be gone from the public packet).
    forbidden_phrases = [
        "DRAFT", "PRIVATE", "INTERNAL", "Nora Chen", "Marcus Vale", "Eliza Park",
        "Avery Stone", "Mira Cole", "Jon Bell", "14 Pine Street", "88 Lake Avenue",
        "5 West Road", "555-", "settlement exposure", "attorney-client",
        "legal hold", "2026-01-08", "2026-07-31", "$500", "34 claims",
        "unverified hardship narrative", "raw intake", "duplicate scratch",
    ]
    forbidden_xml = [
        "Nora Chen", "Marcus Vale", "Eliza Park", "Avery Stone", "Mira Cole",
        "Jon Bell", "14 Pine Street", "88 Lake Avenue", "5 West Road",
        "settlement exposure", "legal hold", "2026-01-08", "2026-07-31",
    ]
    for section in unit_sections:
        forbidden_phrases.extend(section["forbidden_private"])
        forbidden_xml.extend(section["forbidden_private"])

    corrected_values = ["2026-01-18", str(n), "$650", CONTACT, DEADLINE]
    per_unit_corrected = []
    for unit in units:
        per_unit_corrected.append({
            "id": unit["id"],
            "from": [f"${unit['wrong_amount']}", unit["wrong_status"]],
            "to": [f"${unit['right_amount']}", unit["right_status"]],
        })

    return {
        "schema": "docops-scaling-expectation-v1",
        "variant_task_id": data["variant_task_id"],
        "kind": "docx",
        "unit_count": n,
        "unit_ids": [u["id"] for u in units],
        "total_claims": n,
        "headings": headings,
        "page_break_headings": page_break_headings,
        "table_count": n + 3,  # aggregate determination + N per-unit + category + checklist
        "determination_facts_table": determination_facts_rows(n),
        "category_table": category_table_rows(units),
        "checklist_table": checklist_rows(),
        "corrected_values": corrected_values,
        "per_unit_corrected": per_unit_corrected,
        "units": unit_sections,
        "document_level": {
            "core": {
                "author": PUBLIC_AUTHOR,
                "subject": PUBLIC_SUBJECT,
                "title": PUBLIC_TITLE,
                "last_modified_by": PUBLIC_AUTHOR,
                "keywords": "",
                "comments": "",
            },
            "footer": PUBLIC_FOOTER,
            "margin_twips": 1080,  # 0.75 inch
            "title_font": "Aptos Display",
            "title_size_pt": 18,
            "title_color": "1F4E79",
            "title_bold": True,
            "body_font": "Aptos",
            "heading_color": "1F4E79",
            "table_header_fill": "1F4E79",
        },
        "forbidden_phrases": forbidden_phrases,
        "forbidden_xml": forbidden_xml,
    }


def write_expected(variant_task_id: str, units_path: Path, expected_path: Path) -> dict:
    result = compute(units_path)
    common.write_json(expected_path, result)
    return result
