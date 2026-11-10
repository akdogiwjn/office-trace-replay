#!/usr/bin/env python3
"""Dynamic validator for synthetic scaled Word 001 variants.

Reads the frozen expected.json (generated at prepare time, never regenerated in
the loop) and the rebuilt DOCX, then checks:

- document-level controls exactly once (margins, footer, header, core
  properties, title/heading style, table header fill, page breaks);
- every declared controlled document record: its register row plus required
  corrected facts (first/middle/last are checked together with all records);
- paragraph count, table count and record count against expected.json;
- whole-document forbidden text (token-boundary matched, so legal ids/dates
  that merely contain a forbidden word as a substring are not flagged) and
  package-XML cleanliness.

No per-record check re-runs a document-level control, so the record count does
not inflate the document-level assertions.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import zipfile
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from lxml import etree

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}

# Frozen public facts (validated against the expected oracle, never hardcoded
# checks beyond the oracle itself).
FORBIDDEN_RE = re.compile(r"(?<!\w){}(?!\w)")


def forbidden_hits(text: str, token: str) -> list:
    """Token-boundary matches of ``token`` inside ``text``.

    ``(?<!\w)WORD(?!\w)`` means a legal value that merely contains the word as
    a substring (e.g. ``version 4.10`` containing ``4.1``) is never flagged.
    """
    pattern = re.compile(rf"(?<!\w){re.escape(token)}(?!\w)", re.IGNORECASE)
    return list(pattern.finditer(text))


def body_children_in_order(doc):
    """Yield ("para", paragraph, text) / ("table", table, None) in body order."""
    para_by_el = {p._p: p for p in doc.paragraphs}
    body = doc._element.body
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            paragraph = para_by_el[child]
            yield ("para", paragraph, paragraph.text)
        elif child.tag == qn("w:tbl"):
            from docx.table import Table
            yield ("table", Table(child, doc._part), None)
        elif child.tag == qn("w:sectPr"):
            yield ("sect", None, None)


def collect_visible_text(doc) -> str:
    parts = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                parts.append(cell.text)
    for section in doc.sections:
        for paragraph in section.footer.paragraphs:
            parts.append(paragraph.text)
        for paragraph in section.header.paragraphs:
            parts.append(paragraph.text)
    return "\n".join(parts)


def check(output_path: Path, expected_path: Path) -> dict:
    expected = json.loads(Path(expected_path).read_text(encoding="utf-8"))
    if expected.get("kind") != "docx":
        raise ValueError(f"not a DOCX expectation file: {expected_path}")
    doc = Document(output_path)

    errors = []
    report = {
        "records": {},
        "measured": {
            "paragraphs": len(doc.paragraphs),
            "tables": len(doc.tables),
            "table_rows": sum(len(t.rows) for t in doc.tables),
        },
    }

    def error(message):
        errors.append(message)

    # headings: Title + Heading 1 paragraphs in document order.
    heading_paragraphs = [
        p for p in doc.paragraphs
        if p.style and p.style.name in {"Title", "Heading 1"}
    ]
    actual_headings = [p.text for p in heading_paragraphs]
    expected_headings = expected["headings"]
    if actual_headings != expected_headings:
        error(f"Headings differ: expected {expected_headings!r}, got {actual_headings!r}")

    if len(doc.paragraphs) != expected["paragraph_count"]:
        error(f"Paragraph count {len(doc.paragraphs)} != expected "
              f"{expected['paragraph_count']}")
    if len(doc.tables) != expected["table_count"]:
        error(f"Expected {expected['table_count']} tables, found {len(doc.tables)}")

    # Register table (identified once by its header row).
    register = None
    for table in doc.tables:
        if not table.rows:
            continue
        header = [c.text for c in table.rows[0].cells]
        if header == expected["register_header"]:
            register = table
            break
    if register is None:
        error(f"Controlled Document Register table missing (header "
              f"{expected['register_header']!r})")
    else:
        data_rows = [[c.text for c in row.cells] for row in register.rows[1:]]
        report["measured"]["register_rows"] = len(data_rows)
        if len(data_rows) != expected["record_count"]:
            error(f"Register holds {len(data_rows)} records, expected "
                  f"{expected['record_count']}")
        if data_rows != expected["register_rows"]:
            error("Register rows differ from the expected register")

    # Per-record facts for every record (first/middle/last included) using an
    # O(1) index by position; the register order is the record order.
    expected_by_position = {i: rec for i, rec in enumerate(expected["records"])}
    for index, rec in expected_by_position.items():
        if register is None or index >= len(register.rows) - 1:
            row = []
        else:
            row = [c.text for c in register.rows[index + 1].cells]
        missing = [term for term in rec["required_public"] if term not in row]
        report["records"][rec["id"]] = {
            "required_present": not missing,
            "register_row": row,
        }
        if missing:
            error(f"record {rec['id']}: required corrected facts missing: {missing}")

    # Document-level: corrected global values in table text.
    table_text = "\n".join(
        cell.text for table in doc.tables for row in table.rows for cell in row.cells
    )
    for corrected_value in expected["corrected_values"]:
        if corrected_value not in table_text:
            error(f"Corrected table value missing: {corrected_value}")

    # Document-level: forbidden visible text (token boundary, once-lowered).
    visible_text = collect_visible_text(doc)
    lowered = visible_text.lower()
    for token in expected["forbidden_phrases"]:
        if re.search(rf"(?<!\w){re.escape(token.lower())}(?!\w)", lowered):
            error(f"Forbidden visible text remains: {token}")

    # Document-level: core properties.
    core = doc.core_properties
    for attribute, exp_value in expected["document_level"]["core"].items():
        actual = getattr(core, attribute)
        if actual != exp_value:
            error(f"Core property {attribute}: expected {exp_value!r}, got {actual!r}")

    # Document-level: margins / footer / header.
    dl = expected["document_level"]
    for section in doc.sections:
        margin_twips = {
            "top": section.top_margin.twips,
            "right": section.right_margin.twips,
            "bottom": section.bottom_margin.twips,
            "left": section.left_margin.twips,
        }
        if any(value != dl["margin_twips"] for value in margin_twips.values()):
            error(f"Margins are not all 0.8 inch: {margin_twips}")
        footer_text = "\n".join(p.text for p in section.footer.paragraphs)
        if dl["footer"] not in footer_text:
            error(f"Footer does not contain {dl['footer']!r}: {footer_text!r}")
        if "Page" not in footer_text:
            error(f"Footer page field missing: {footer_text!r}")
        header_text = "\n".join(p.text for p in section.header.paragraphs)
        if dl["header"] not in header_text:
            error(f"Header does not contain {dl['header']!r}: {header_text!r}")

    # Document-level: title style.
    if heading_paragraphs:
        title_run = heading_paragraphs[0].runs[0]
        if title_run.font.name != dl["title_font"]:
            error(f"Title font is {title_run.font.name!r}")
        if title_run.font.size is None or title_run.font.size.pt != dl["title_size_pt"]:
            error(f"Title size is {title_run.font.size!r}")
        if str(title_run.font.color.rgb) != dl["title_color"]:
            error(f"Title color is {title_run.font.color.rgb!r}")
        if not title_run.font.bold:
            error("Title is not bold")
    for heading in heading_paragraphs[1:]:
        for run in heading.runs:
            if str(run.font.color.rgb) != dl["heading_color"]:
                error(f"Heading color wrong for {heading.text!r}")

    # Document-level: page breaks before derived headings.
    break_set = set(expected["page_break_headings"])
    for paragraph in heading_paragraphs:
        if paragraph.text in break_set and not paragraph.paragraph_format.page_break_before:
            error(f"Missing page break before {paragraph.text!r}")

    # Document-level: table header fills (one pass over every table).
    for table_index, table in enumerate(doc.tables, start=1):
        if not table.rows:
            error(f"Table {table_index} has no rows")
            continue
        for header_index, cell in enumerate(table.rows[0].cells):
            tc_pr = cell._tc.tcPr
            shading = tc_pr.find(qn("w:shd")) if tc_pr is not None else None
            fill = shading.get(qn("w:fill")) if shading is not None else None
            if fill != dl["table_header_fill"]:
                error(f"Table {table_index} header cell {header_index} fill is {fill!r}")
            for run in cell.paragraphs[0].runs:
                if str(run.font.color.rgb) != "FFFFFF" or not run.font.bold:
                    error(f"Table {table_index} header cell {header_index} "
                          "does not use white bold text")

    # Package-level: tracked/comment XML and private values must be gone.
    with zipfile.ZipFile(output_path, "r") as z:
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
                error(f"Tracked/comment XML remains at {xpath}: {count}")

        xml_text = "\n".join(
            z.read(name).decode("utf-8", errors="ignore")
            for name in names
            if name.endswith((".xml", ".rels"))
        )
        # Normalize the package once; the forbidden list grows with record
        # count but is matched with token boundaries only.
        xml_lowered = xml_text.lower()
        for token in expected["forbidden_xml"]:
            if re.search(rf"(?<!\w){re.escape(token.lower())}(?!\w)", xml_lowered):
                error(f"Private value remains in package XML: {token}")

    report["errors"] = errors
    report["passed"] = not errors
    report["status"] = "passed" if not errors else "failed"
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=os.environ.get("VARIANT_OUTPUT"),
                        help="output DOCX path")
    parser.add_argument("--expected",
                        default=os.environ.get("VARIANT_EXPECTED", "/root/tmp/docs/expected.json"))
    parser.add_argument("--report",
                        default=os.environ.get("VARIANT_REPORT", "/root/tmp/docs/output_validation.json"))
    args = parser.parse_args(argv)
    if not args.output:
        parser.error("--output is required (or set VARIANT_OUTPUT)")
    report = check(Path(args.output), Path(args.expected))
    Path(args.report).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if report["errors"]:
        raise SystemExit(f"Validation failed with {len(report['errors'])} error(s)")
    print("All structural, content and document-level checks passed.")


if __name__ == "__main__":
    main()
