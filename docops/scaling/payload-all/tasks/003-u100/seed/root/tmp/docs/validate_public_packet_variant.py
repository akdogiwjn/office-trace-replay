#!/usr/bin/env python3
"""Dynamic validator for synthetic scaled Word 003 variants.

Reads the frozen expected.json (generated at prepare time, never regenerated in
the loop) and the rebuilt DOCX, then checks:

- document-level controls exactly once (margins, footer, core properties,
  title/heading style, table header fill, page breaks);
- every declared business unit: its determination heading/table/narrative and
  required corrected facts, with that unit's private values forbidden;
- whole-document forbidden text and package-XML cleanliness.

No per-unit check re-runs a document-level control, so the unit count does not
inflate the document-level assertions.
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
    return "\n".join(parts)


def check(output_path: Path, expected_path: Path) -> dict:
    expected = json.loads(Path(expected_path).read_text(encoding="utf-8"))
    if expected.get("kind") != "docx":
        raise ValueError(f"not a DOCX expectation file: {expected_path}")
    doc = Document(output_path)

    errors = []
    report = {
        "units": {},
        "measured": {
            "paragraphs": len(doc.paragraphs),
            "tables": len(doc.tables),
            "table_rows": sum(len(t.rows) for t in doc.tables),
        },
    }

    def error(message):
        errors.append(message)

    # headings: Title + Heading 1 paragraphs
    heading_paragraphs = [
        p for p in doc.paragraphs
        if p.style and p.style.name in {"Title", "Heading 1"}
    ]
    actual_headings = [p.text for p in heading_paragraphs]
    expected_headings = expected["headings"]
    if actual_headings != expected_headings:
        error(f"Headings differ: expected {expected_headings!r}, got {actual_headings!r}")

    if len(doc.tables) != expected["table_count"]:
        error(f"Expected {expected['table_count']} tables, found {len(doc.tables)}")

    # per-unit section scoping in document order
    unit_sections = {u["id"]: u for u in expected["units"]}
    unit_order = list(unit_sections)
    # One-time index from the exact unit heading string to its id. Replaces the
    # per-heading scan over every unit (O(N^2)) with O(1) lookup; matching
    # semantics are identical (exact heading string equality).
    unit_heading_to_id = {
        f"Unit {uid} — {unit_sections[uid]['category']}": uid
        for uid in unit_order
    }
    current_unit = None
    unit_block_text = {}
    unit_tables = {}
    for kind, item, text in body_children_in_order(doc):
        if kind == "para":
            if item.style and item.style.name == "Heading 1":
                current_unit = unit_heading_to_id.get(text)
                if current_unit is not None:
                    unit_block_text.setdefault(current_unit, [])
            if current_unit is not None:
                unit_block_text[current_unit].append(text)
        elif kind == "table":
            if current_unit is not None:
                unit_tables.setdefault(current_unit, item)
                for row in item.rows:
                    for cell in row.cells:
                        unit_block_text[current_unit].append(cell.text)

    for unit in expected["units"]:
        uid = unit["id"]
        block = "\n".join(unit_block_text.get(uid, []))
        missing = [term for term in unit["required_public"] if term not in block]
        if missing:
            error(f"unit {uid}: required corrected facts missing: {missing}")
        if uid not in unit_tables:
            error(f"unit {uid}: determination table missing")
        report["units"][uid] = {
            "required_present": not missing,
            "table_found": uid in unit_tables,
            "table_rows": len(unit_tables[uid].rows) if uid in unit_tables else 0,
        }

    # document-level: corrected global values in table text
    table_text = "\n".join(
        cell.text for table in doc.tables for row in table.rows for cell in row.cells
    )
    for corrected_value in expected["corrected_values"]:
        if corrected_value not in table_text:
            error(f"Corrected table value missing: {corrected_value}")

    # document-level: forbidden visible text (global + per-unit private)
    visible_text = collect_visible_text(doc)
    lowered = visible_text.lower()
    for token in expected["forbidden_phrases"]:
        if token.lower() in lowered:
            error(f"Forbidden visible text remains: {token}")

    # document-level: core properties
    core = doc.core_properties
    for attribute, exp_value in expected["document_level"]["core"].items():
        actual = getattr(core, attribute)
        if actual != exp_value:
            error(f"Core property {attribute}: expected {exp_value!r}, got {actual!r}")

    # document-level: margins / footer
    for section in doc.sections:
        margin_twips = {
            "top": section.top_margin.twips,
            "right": section.right_margin.twips,
            "bottom": section.bottom_margin.twips,
            "left": section.left_margin.twips,
        }
        if any(value != expected["document_level"]["margin_twips"]
               for value in margin_twips.values()):
            error(f"Margins are not all 0.75 inch: {margin_twips}")
        footer_text = "\n".join(p.text for p in section.footer.paragraphs).strip()
        if footer_text != expected["document_level"]["footer"]:
            error(f"Unexpected footer text: {footer_text!r}")

    # document-level: title style
    dl = expected["document_level"]
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

    # document-level: page breaks before derived headings
    break_set = set(expected["page_break_headings"])
    for paragraph in heading_paragraphs:
        if paragraph.text in break_set and not paragraph.paragraph_format.page_break_before:
            error(f"Missing page break before {paragraph.text!r}")

    # document-level: table header fills
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

    # package-level: tracked/comment XML and metadata must be gone
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

        if any("comments" in name.lower() for name in names):
            error("A comment-related package part remains")
        if any(
            rel.get("Type", "").endswith("/comments")
            or "comments" in rel.get("Target", "").lower()
            for rel in list(relationships) + list(root_relationships)
        ):
            error("A comment relationship remains")
        if "docProps/thumbnail.jpeg" in names:
            error("Thumbnail metadata remains")
        if any(name.startswith("customXml/") for name in names):
            error("Custom XML metadata remains")

        xml_text = "\n".join(
            z.read(name).decode("utf-8", errors="ignore")
            for name in names
            if name.endswith((".xml", ".rels"))
        )
        # Normalize the package once; the forbidden list grows with unit count.
        xml_lowered = xml_text.lower()
        for private_value in expected["forbidden_xml"]:
            if private_value.lower() in xml_lowered:
                error(f"Private value remains in package XML: {private_value}")

    report["errors"] = errors
    report["passed"] = not errors
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=os.environ.get("VARIANT_OUTPUT"),
                        help="output DOCX path")
    parser.add_argument("--expected", default=os.environ.get("VARIANT_EXPECTED", "/root/tmp/docs/expected.json"))
    parser.add_argument("--report", default=os.environ.get("VARIANT_REPORT", "/root/tmp/docs/output_validation.json"))
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
