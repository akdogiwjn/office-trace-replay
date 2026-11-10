"""Independent expectation generator for scaled Word 001 variants.

Reads the frozen ``records.json`` prepared material and derives the full
expected structure of the rebuilt controlled document release packet: headings,
per-record register facts, fixed chapter tables, paragraph/table counts and
document-level controls. The builder reads the same records.json but produces
content through python-docx; this module shares NO computation with the builder
(it never writes OOXML). The resulting expected.json is frozen at prepare time.
"""
from __future__ import annotations

from pathlib import Path

from .. import common
from . import synth

DOC_ID = synth.DOC_ID
VERSION = synth.VERSION
EFFECTIVE_DATE = synth.EFFECTIVE_DATE
OWNER = synth.OWNER
APPROVER = synth.APPROVER
TRAINING_DUE = synth.TRAINING_DUE
RETENTION = synth.RETENTION
RETIREMENT = synth.RETIREMENT
PUBLIC_TITLE = synth.PUBLIC_TITLE
PUBLIC_SUBJECT = synth.PUBLIC_SUBJECT
PUBLIC_FOOTER = synth.PUBLIC_FOOTER
HEADINGS = synth.HEADINGS
PAGE_BREAK_HEADINGS = synth.PAGE_BREAK_HEADINGS
CORRECTION_ROWS = synth.CORRECTION_ROWS
METADATA_ROWS = synth.METADATA_ROWS
REVISION_ROWS = synth.REVISION_ROWS
WORKFLOW_ROWS = synth.WORKFLOW_ROWS
RETIREMENT_ROWS = synth.RETIREMENT_ROWS
FORBIDDEN_PHRASES = synth.FORBIDDEN_PHRASES

PUBLIC_AUTHOR = "Quality Systems Office"
PUBLIC_CATEGORY = "Quality Management System"
PUBLIC_KEYWORDS = "QMS-PR-007; version 4.2; controlled release; correction register"
PUBLIC_COMMENTS = "Controlled release record prepared by Quality Systems Office."

REGISTER_HEADER = [
    "Record ID", "Document Name", "Version", "Effective Date",
    "Owner", "Training Due", "Retention", "Status",
]

# Body paragraph count of the rebuilt packet (fixed chapters + appendix,
# independent of the record count; tables are not paragraphs).
PARAGRAPH_COUNT = 35
TABLE_COUNT = 6

TABLE_HEADERS = [
    CORRECTION_ROWS[0],
    METADATA_ROWS[0],
    REVISION_ROWS[0],
    WORKFLOW_ROWS[0],
    RETIREMENT_ROWS[0],
    REGISTER_HEADER,
]


def register_rows(records: list[dict]) -> list[list[str]]:
    return [
        [r["id"], r["name"], r["version"], r["effective_date"],
         r["owner"], r["training_due"], r["retention"], r["status"]]
        for r in records
    ]


def compute(records_path: Path) -> dict:
    data = common.load_json(records_path)
    records = data["records"]
    n = len(records)

    records_sections = []
    for record in records:
        records_sections.append({
            "id": record["id"],
            "name": record["name"],
            "version": record["version"],
            "effective_date": record["effective_date"],
            "owner": record["owner"],
            "training_due": record["training_due"],
            "retention": record["retention"],
            "status": record["status"],
            "required_public": [
                record["id"], record["name"], record["version"],
                record["effective_date"], record["owner"],
                record["training_due"], record["retention"], record["status"],
            ],
        })

    return {
        "schema": "docops-scaling-expectation-v1",
        "variant_task_id": data["variant_task_id"],
        "kind": "docx",
        "record_count": n,
        "record_ids": [r["id"] for r in records],
        "register_header": REGISTER_HEADER,
        "register_rows": register_rows(records),
        "records": records_sections,
        "first_record": records_sections[0],
        "middle_record": records_sections[n // 2],
        "last_record": records_sections[-1],
        "headings": list(HEADINGS),
        "page_break_headings": list(PAGE_BREAK_HEADINGS),
        "paragraph_count": PARAGRAPH_COUNT,
        "table_count": TABLE_COUNT,
        "table_headers": TABLE_HEADERS,
        "corrected_values": [
            DOC_ID, VERSION, EFFECTIVE_DATE, OWNER, APPROVER,
            TRAINING_DUE, RETENTION, RETIREMENT,
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
                "content_status": "Released",
            },
            "footer": PUBLIC_FOOTER,
            "header": "QUALITY MANAGEMENT SYSTEM",
            "margin_twips": 1152,  # 0.8 inch
            "title_font": "Aptos Display",
            "title_size_pt": 18,
            "title_color": "0F4C5C",
            "title_bold": True,
            "body_font": "Aptos",
            "heading_color": "0F4C5C",
            "table_header_fill": "0F4C5C",
        },
        "forbidden_phrases": list(FORBIDDEN_PHRASES),
        "forbidden_xml": list(FORBIDDEN_PHRASES),
    }


def write_expected(variant_task_id: str, records_path: Path, expected_path: Path) -> dict:
    result = compute(records_path)
    common.write_json(expected_path, result)
    return result
