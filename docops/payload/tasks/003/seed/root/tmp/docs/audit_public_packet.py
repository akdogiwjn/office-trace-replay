#!/usr/bin/env python3
"""Audit the generated public records release packet."""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from lxml import etree


OUTPUT = Path(
    "/root/submission/"
    "docops_v2_l3_003_docx_public_records_release_metadata_cleanup_output.docx"
)
EXPECTED_HEADINGS = [
    "Public Release Packet: Water Main Break Claims",
    "Release Summary",
    "Corrected Determination Facts",
    "Claim Category Table",
    "Notification Workflow",
    "Redaction and Metadata Checklist",
    "Public Appendix Index",
]
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}
EXPECTED_SUBJECT = "Clean public release packet"
EXPECTED_AUTHOR = "Public Records Office"
EXPECTED_FOOTER = "Public Records Release | Water Main Break Claims | 2026"


def main() -> None:
    doc = Document(OUTPUT)
    failures: list[str] = []

    heading_paragraphs = [
        paragraph
        for paragraph in doc.paragraphs
        if paragraph.style and paragraph.style.name in {"Title", "Heading 1"}
    ]
    actual_headings = [paragraph.text for paragraph in heading_paragraphs]
    if actual_headings != EXPECTED_HEADINGS:
        failures.append(
            f"Headings differ: expected {EXPECTED_HEADINGS!r}, got {actual_headings!r}"
        )

    if len(doc.tables) != 3:
        failures.append(f"Expected 3 tables, found {len(doc.tables)}")

    visible_text = "\n".join(
        [paragraph.text for paragraph in doc.paragraphs]
        + [
            cell.text
            for table in doc.tables
            for row in table.rows
            for cell in row.cells
        ]
        + [
            paragraph.text
            for section in doc.sections
            for paragraph in section.footer.paragraphs
        ]
    )

    forbidden_text = [
        "DRAFT",
        "PRIVATE",
        "INTERNAL",
        "Nora Chen",
        "Marcus Vale",
        "Eliza Park",
        "Avery Stone",
        "Mira Cole",
        "Jon Bell",
        "14 Pine Street",
        "88 Lake Avenue",
        "5 West Road",
        "555-",
        "settlement exposure",
        "attorney-client",
        "legal hold",
        "2026-01-08",
        "2026-07-31",
        "$500",
        "34 claims",
    ]
    for token in forbidden_text:
        if token.lower() in visible_text.lower():
            failures.append(f"Forbidden visible text remains: {token}")

    core = doc.core_properties
    expected_core = {
        "author": EXPECTED_AUTHOR,
        "subject": EXPECTED_SUBJECT,
        "title": EXPECTED_HEADINGS[0],
        "last_modified_by": EXPECTED_AUTHOR,
        "keywords": "",
        "comments": "",
    }
    for attribute, expected in expected_core.items():
        actual = getattr(core, attribute)
        if actual != expected:
            failures.append(
                f"Core property {attribute}: expected {expected!r}, got {actual!r}"
            )

    for section in doc.sections:
        margin_twips = {
            "top": section.top_margin.twips,
            "right": section.right_margin.twips,
            "bottom": section.bottom_margin.twips,
            "left": section.left_margin.twips,
        }
        if any(value != 1080 for value in margin_twips.values()):
            failures.append(f"Margins are not all 0.75 inch: {margin_twips}")
        footer_text = "\n".join(p.text for p in section.footer.paragraphs).strip()
        if footer_text != EXPECTED_FOOTER:
            failures.append(f"Unexpected footer text: {footer_text!r}")

    if heading_paragraphs:
        title_run = heading_paragraphs[0].runs[0]
        if title_run.font.name != "Aptos Display":
            failures.append(f"Title font is {title_run.font.name!r}")
        if title_run.font.size is None or title_run.font.size.pt != 18:
            failures.append(f"Title size is {title_run.font.size!r}")
        if str(title_run.font.color.rgb) != "1F4E79":
            failures.append(f"Title color is {title_run.font.color.rgb!r}")
        if not title_run.font.bold:
            failures.append("Title is not bold")

    for heading in heading_paragraphs[1:]:
        for run in heading.runs:
            if str(run.font.color.rgb) != "1F4E79":
                failures.append(f"Heading color wrong for {heading.text!r}")

    page_break_headings = {
        "Redaction and Metadata Checklist",
        "Public Appendix Index",
    }
    for paragraph in heading_paragraphs:
        if paragraph.text in page_break_headings and not paragraph.paragraph_format.page_break_before:
            failures.append(f"Missing page break before {paragraph.text!r}")

    for table_index, table in enumerate(doc.tables, start=1):
        if not table.rows:
            failures.append(f"Table {table_index} has no rows")
            continue
        for header_index, cell in enumerate(table.rows[0].cells):
            tc_pr = cell._tc.tcPr
            shading = tc_pr.find(qn("w:shd")) if tc_pr is not None else None
            fill = shading.get(qn("w:fill")) if shading is not None else None
            if fill != "1F4E79":
                failures.append(
                    f"Table {table_index} header cell {header_index} fill is {fill!r}"
                )
            for run in cell.paragraphs[0].runs:
                if str(run.font.color.rgb) != "FFFFFF" or not run.font.bold:
                    failures.append(
                        f"Table {table_index} header cell {header_index} "
                        "does not use white bold text"
                    )

    table_text = "\n".join(
        cell.text for table in doc.tables for row in table.rows for cell in row.cells
    )
    for corrected_value in ["2026-01-18", "37", "$650", "Public Records Desk", "2026-08-15"]:
        if corrected_value not in table_text:
            failures.append(f"Corrected table value missing: {corrected_value}")

    with zipfile.ZipFile(OUTPUT, "r") as z:
        names = set(z.namelist())
        document_root = etree.fromstring(z.read("word/document.xml"))
        relationships = etree.fromstring(z.read("word/_rels/document.xml.rels"))
        root_relationships = etree.fromstring(z.read("_rels/.rels"))

        for xpath in (
            ".//w:ins",
            ".//w:del",
            ".//w:delText",
            ".//w:commentRangeStart",
            ".//w:commentRangeEnd",
            ".//w:commentReference",
        ):
            count = len(document_root.xpath(xpath, namespaces=NS))
            if count:
                failures.append(f"Tracked/comment XML remains at {xpath}: {count}")

        if any("comments" in name.lower() for name in names):
            failures.append("A comment-related package part remains")
        if any(
            rel.get("Type", "").endswith("/comments")
            or "comments" in rel.get("Target", "").lower()
            for rel in list(relationships) + list(root_relationships)
        ):
            failures.append("A comment relationship remains")
        if "docProps/thumbnail.jpeg" in names:
            failures.append("Thumbnail metadata remains")
        if any(name.startswith("customXml/") for name in names):
            failures.append("Custom XML metadata remains")

        xml_text = "\n".join(
            z.read(name).decode("utf-8", errors="ignore")
            for name in names
            if name.endswith(".xml")
        )
        for private_value in [
            "Nora Chen",
            "Marcus Vale",
            "Eliza Park",
            "Avery Stone",
            "Mira Cole",
            "Jon Bell",
            "14 Pine Street",
            "88 Lake Avenue",
            "5 West Road",
            "555-0174",
            "555-2201",
            "settlement exposure",
            "legal hold",
            "2026-01-08",
            "2026-07-31",
        ]:
            if private_value.lower() in xml_text.lower():
                failures.append(f"Private value remains in package XML: {private_value}")

    report = {
        "output": str(OUTPUT),
        "size_bytes": OUTPUT.stat().st_size,
        "headings": actual_headings,
        "tables": len(doc.tables),
        "paragraphs": len(doc.paragraphs),
        "visible_characters": len(visible_text),
        "core_properties": {
            "author": core.author,
            "subject": core.subject,
            "title": core.title,
            "keywords": core.keywords,
            "comments": core.comments,
            "last_modified_by": core.last_modified_by,
        },
        "failures": failures,
        "passed": not failures,
    }
    report_path = Path("/root/tmp/docs/audit_report_v2.json")
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
