"""Independent expectation generator for scaled Word 009 variants.

Reads the frozen ``cases.json`` prepared material and derives the full expected
structure of the rebuilt public incident manual: cover facts, TOC, section
headings, the six per-case data tables, paragraph/table counts and
document-level controls. The builder reads the same cases.json but produces
content through python-docx; this module shares NO computation with the builder
(it never writes OOXML). The resulting expected.json is frozen at prepare time.
"""
from __future__ import annotations

from pathlib import Path

from .. import common
from . import synth

RELEASE_DATE = synth.RELEASE_DATE
PUBLIC_TITLE = synth.PUBLIC_TITLE
PUBLIC_SUBJECT = synth.PUBLIC_SUBJECT
PUBLIC_HEADER = synth.PUBLIC_HEADER
PUBLIC_AUTHOR = synth.PUBLIC_AUTHOR
HEADINGS = synth.HEADINGS
PAGE_BREAK_HEADINGS = synth.PAGE_BREAK_HEADINGS
TIMELINE_HEADER = synth.TIMELINE_HEADER
COMMUNICATION_HEADER = synth.COMMUNICATION_HEADER
EXCEPTION_HEADER = synth.EXCEPTION_HEADER
ACTION_HEADER = synth.ACTION_HEADER
EVIDENCE_HEADER = synth.EVIDENCE_HEADER
APPROVAL_HEADER = synth.APPROVAL_HEADER
FORBIDDEN_PHRASES = synth.FORBIDDEN_PHRASES

PUBLIC_KEYWORDS = "incident response; public release; control exceptions"
PUBLIC_COMMENTS = "Public edition with privileged and internal material removed."
PUBLIC_CATEGORY = "Public Release"

NAVY = "17324D"
BODY_FONT = "Arial"

COVER_TABLE_ROWS = [
    ["Release date", RELEASE_DATE],
    ["Distribution", "Public"],
    ["Publication state", "Approved for release"],
]

# Body paragraph count of the rebuilt public manual (cover + TOC + sections +
# one trailing paragraph after each of the six content tables), independent of
# the case count.
PARAGRAPH_COUNT = 39
TABLE_COUNT = 7  # cover + 6 content tables

MARGIN_TWIPS = {
    "top": 1440,       # 1.0 inch
    "bottom": 1440,
    "left": 1800,      # 1.25 inch
    "right": 1800,
}


def timeline_rows(cases: list[dict]) -> list[list[str]]:
    return [[c["timeline_time"], c["milestone"], c["summary"]] for c in cases]


def communication_rows(cases: list[dict]) -> list[list[str]]:
    return [[c["audience"], c["message_owner"], c["message_update"],
             synth.MESSAGE_STATUS] for c in cases]


def exception_rows(cases: list[dict]) -> list[list[str]]:
    return [[c["exception_id"], c["control"], c["exception_owner"],
             c["release_status"]] for c in cases]


def action_rows(cases: list[dict]) -> list[list[str]]:
    return [[c["action_id"], c["action_owner"], c["due_date"],
             c["publish_status"]] for c in cases]


def evidence_rows(cases: list[dict]) -> list[list[str]]:
    return [[c["evidence_id"], c["public_label"], c["disposition"]] for c in cases]


def approval_rows(cases: list[dict]) -> list[list[str]]:
    return [[c["approver"], c["role"], c["decision"]] for c in cases]


def compute(cases_path: Path) -> dict:
    data = common.load_json(cases_path)
    cases = data["cases"]
    n = len(cases)

    rows_by_header = {
        tuple(TIMELINE_HEADER): timeline_rows(cases),
        tuple(COMMUNICATION_HEADER): communication_rows(cases),
        tuple(EXCEPTION_HEADER): exception_rows(cases),
        tuple(ACTION_HEADER): action_rows(cases),
        tuple(EVIDENCE_HEADER): evidence_rows(cases),
        tuple(APPROVAL_HEADER): approval_rows(cases),
    }

    cases_sections = []
    for case in cases:
        cases_sections.append({
            "id": case["id"],
            "required_public": [
                case["timeline_time"], case["milestone"], case["summary"],
                case["audience"], case["message_owner"], case["message_update"],
                case["exception_id"], case["control"], case["exception_owner"],
                case["release_status"], case["action_id"], case["action_owner"],
                case["due_date"], case["publish_status"], case["evidence_id"],
                case["public_label"], case["disposition"], case["approver"],
                case["role"], case["decision"],
            ],
        })

    return {
        "schema": "docops-scaling-expectation-v1",
        "variant_task_id": data["variant_task_id"],
        "kind": "docx",
        "title": PUBLIC_TITLE,
        "toc_entry_titles": HEADINGS,
        "case_count": n,
        "case_ids": [c["id"] for c in cases],
        "headings": list(HEADINGS),
        "page_break_headings": list(PAGE_BREAK_HEADINGS),
        "paragraph_count": PARAGRAPH_COUNT,
        "table_count": TABLE_COUNT,
        "cover_table": {"rows": COVER_TABLE_ROWS},
        "tables": {
            "timeline": {"header": TIMELINE_HEADER, "rows": rows_by_header[tuple(TIMELINE_HEADER)]},
            "communication": {"header": COMMUNICATION_HEADER, "rows": rows_by_header[tuple(COMMUNICATION_HEADER)]},
            "exception": {"header": EXCEPTION_HEADER, "rows": rows_by_header[tuple(EXCEPTION_HEADER)]},
            "action": {"header": ACTION_HEADER, "rows": rows_by_header[tuple(ACTION_HEADER)]},
            "evidence": {"header": EVIDENCE_HEADER, "rows": rows_by_header[tuple(EVIDENCE_HEADER)]},
            "approval": {"header": APPROVAL_HEADER, "rows": rows_by_header[tuple(APPROVAL_HEADER)]},
        },
        "cases": cases_sections,
        "first_case": cases_sections[0],
        "middle_case": cases_sections[n // 2],
        "last_case": cases_sections[-1],
        "fixed_paragraphs": list(synth.FIXED_PARAGRAPHS),
        "required_values": [
            PUBLIC_TITLE, PUBLIC_HEADER, RELEASE_DATE,
            "Incident Response Manual | Public Release",
            "Exception: MFA evidence owner remains unassigned.",
            str(n),
        ],
        "document_level": {
            "core": {
                "author": PUBLIC_AUTHOR,
                "subject": PUBLIC_SUBJECT,
                "title": PUBLIC_TITLE,
                "last_modified_by": PUBLIC_AUTHOR,
                "keywords": PUBLIC_KEYWORDS,
                "comments": PUBLIC_COMMENTS,
                "category": PUBLIC_CATEGORY,
            },
            "header": PUBLIC_HEADER,
            "footer_contains": "Page",
            "margin_twips": dict(MARGIN_TWIPS),
            "title_font": BODY_FONT,
            "title_size_pt": 21,
            "title_color": NAVY,
            "title_bold": True,
            "heading_color": NAVY,
            "table_header_fill": NAVY,
        },
        "forbidden_phrases": list(FORBIDDEN_PHRASES),
        "forbidden_xml": list(FORBIDDEN_PHRASES),
    }


def write_expected(variant_task_id: str, cases_path: Path, expected_path: Path) -> dict:
    result = compute(cases_path)
    common.write_json(expected_path, result)
    return result
