#!/usr/bin/env python3
"""Dynamic validator for synthetic scaled Word 009 variants.

Reads the frozen expected.json (generated at prepare time, never regenerated in
the loop) and the rebuilt DOCX, then checks:

- document-level controls exactly once (cover, TOC field, header, footer, core
  properties, title/heading style, margins, table header fill, page breaks,
  exception highlight);
- every declared incident case: its row in each of the six data tables plus
  required public facts (first/middle/last are checked together with all cases);
- paragraph count, table count and case count against expected.json;
- whole-document forbidden text (token-boundary matched, so legal values that
  merely contain a forbidden word as a substring are not flagged) and
  package-XML cleanliness;
- the cached TOC page numbers: in formal mode the DOCX is rendered with the
  existing LibreOffice environment, every section heading's real rendered page
  is measured from that render, and ALL cached TOC entries must match (the old
  hardcoded 3..7 pages must fail).

A fixture-only ``--structure-only`` mode skips the LibreOffice re-render so tiny
OOXML fixtures can be tested without it; the formal recipes never pass that
flag.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from docx import Document
from docx.enum.text import WD_COLOR_INDEX
from docx.oxml.ns import qn
from lxml import etree

try:  # package import (tests) vs script import (payload /root/tmp/docs)
    from .build_incident_manual_variant import extract_toc_entries
    from .update_toc_and_render import measure_heading_pages, page_texts
except ImportError:
    from build_incident_manual_variant import extract_toc_entries
    from update_toc_and_render import measure_heading_pages, page_texts

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}


def forbidden_hits(text: str, token: str) -> list:
    """Token-boundary matches of ``token`` inside ``text``.

    ``(?<!\w)WORD(?!\w)`` means a legal value that merely contains the word as
    a substring is never flagged.
    """
    pattern = re.compile(rf"(?<!\w){re.escape(token)}(?!\w)", re.IGNORECASE)
    return list(pattern.finditer(text))


def table_rows(table) -> list[list[str]]:
    return [[cell.text for cell in row.cells] for row in table.rows]


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


def verify_toc_pages(doc, pages: list[str], headings: list[str]) -> tuple[list[str], dict]:
    """Compare every cached TOC entry page against the measured rendered page."""
    errors = []
    cached = extract_toc_entries(doc)
    measured, toc_page = measure_heading_pages(pages, headings)
    if [title for title, _ in cached] != list(headings):
        errors.append(f"TOC entry titles differ: {[t for t, _ in cached]!r}")
    for title, page_str in cached:
        actual = measured.get(title)
        if actual is None:
            errors.append(f"TOC heading not found in render: {title}")
            continue
        if str(actual) != str(page_str):
            errors.append(
                f"TOC page mismatch for {title!r}: cached {page_str} != rendered {actual}")
    return errors, {"toc_page": toc_page, "cached": dict(cached), "measured": measured}


def render_and_measure(docx_path: Path, headings: list[str]):
    """Render the delivered DOCX with LibreOffice and measure heading pages."""
    with tempfile.TemporaryDirectory(prefix="docops009_validate_") as tmp:
        tmp = Path(tmp)
        subprocess.run(
            ["soffice", "-env:UserInstallation=file:///tmp/lo_toc_validate",
             "--headless", "--convert-to", "pdf", "--outdir", str(tmp),
             str(docx_path)],
            check=True, capture_output=True, timeout=1800)
        pdf = tmp / (docx_path.stem + ".pdf")
        return page_texts(pdf)


def check(output_path: Path, expected_path: Path, structure_only: bool = False) -> dict:
    expected = json.loads(Path(expected_path).read_text(encoding="utf-8"))
    if expected.get("kind") != "docx":
        raise ValueError(f"not a DOCX expectation file: {expected_path}")
    doc = Document(output_path)

    errors = []
    report = {
        "cases": {},
        "measured": {
            "paragraphs": len(doc.paragraphs),
            "tables": len(doc.tables),
            "table_rows": sum(len(t.rows) for t in doc.tables),
        },
    }

    def error(message):
        errors.append(message)

    paragraph_text = [p.text for p in doc.paragraphs]

    # Title paragraph (Title style).
    title_paragraph = next((p for p in doc.paragraphs
                            if p.style and p.style.name == "Title"), None)
    if title_paragraph is None or title_paragraph.text != expected["title"]:
        error(f"Title paragraph missing or wrong: "
              f"{title_paragraph.text if title_paragraph else None!r}")

    # Section headings (Heading 1) in order.
    heading_text = [p.text for p in doc.paragraphs
                    if p.style and p.style.name == "Heading 1"]
    if heading_text != expected["headings"]:
        error(f"Headings differ: expected {expected['headings']!r}, "
              f"got {heading_text!r}")

    if len(doc.paragraphs) != expected["paragraph_count"]:
        error(f"Paragraph count {len(doc.paragraphs)} != expected "
              f"{expected['paragraph_count']}")
    if len(doc.tables) != expected["table_count"]:
        error(f"Expected {expected['table_count']} tables, found {len(doc.tables)}")

    # Tables by header (index built once; O(1) lookup per table).
    tables_by_header = {}
    for table in doc.tables:
        if table.rows:
            header = tuple(c.text for c in table.rows[0].cells)
            tables_by_header.setdefault(header, table)

    # Cover table facts (label/value table with no shaded header row).
    cover = expected["cover_table"]
    cover_table = next(
        (t for t in doc.tables if t.rows and t.rows[0].cells[0].text == "Release date"),
        None)
    if cover_table is None:
        error("Cover table missing")
    else:
        data = table_rows(cover_table)
        if data != cover["rows"]:
            error(f"Cover table rows differ: {data!r}")

    # Per-table row comparison and per-case required facts.
    case_sections = {c["id"]: c for c in expected["cases"]}
    for key, spec in expected["tables"].items():
        table = tables_by_header.get(tuple(spec["header"]))
        if table is None:
            error(f"Table with header {spec['header']!r} missing")
            continue
        data = table_rows(table)[1:]
        if len(data) != expected["case_count"]:
            error(f"Table {key} holds {len(data)} case rows, expected "
                  f"{expected['case_count']}")
        if data != spec["rows"]:
            error(f"Table {key} rows differ from the expected rows")

    # Case facts: every case's required public values must appear in the joined
    # visible text (they are scattered across the six tables).
    visible_text = collect_visible_text(doc)
    lowered = visible_text.lower()
    for case in expected["cases"]:
        cid = case["id"]
        missing = [term for term in case["required_public"] if term not in visible_text]
        report["cases"][cid] = {"required_present": not missing}
        if missing:
            error(f"case {cid}: required public facts missing: {missing}")

    # Document-level: fixed paragraphs and required values.
    for phrase in expected["fixed_paragraphs"]:
        if phrase not in paragraph_text:
            error(f"Fixed paragraph missing: {phrase!r}")
    for value in expected["required_values"]:
        if value not in visible_text:
            error(f"Required value missing: {value!r}")

    # Open exception must be fully highlighted.
    try:
        open_exception = next(p for p in doc.paragraphs
                              if p.text == "Exception: MFA evidence owner remains unassigned.")
    except StopIteration:
        open_exception = None
    if open_exception is None:
        error("Open MFA evidence exception paragraph missing")
    else:
        if not open_exception.runs or not all(
                run.font.highlight_color == WD_COLOR_INDEX.YELLOW
                for run in open_exception.runs):
            error("Open exception paragraph is not fully highlighted")

    # Document-level: forbidden visible text (token boundary, once-lowered).
    for token in expected["forbidden_phrases"]:
        if re.search(rf"(?<!\w){re.escape(token.lower())}(?!\w)", lowered):
            error(f"Forbidden visible text remains: {token}")

    # Document-level: core properties.
    core = doc.core_properties
    for attribute, exp_value in expected["document_level"]["core"].items():
        actual = getattr(core, attribute)
        if actual != exp_value:
            error(f"Core property {attribute}: expected {exp_value!r}, got {actual!r}")

    # Document-level: margins / header / footer.
    dl = expected["document_level"]
    for section in doc.sections:
        actual_margins = {
            "top": section.top_margin.twips,
            "right": section.right_margin.twips,
            "bottom": section.bottom_margin.twips,
            "left": section.left_margin.twips,
        }
        for edge, exp_twips in dl["margin_twips"].items():
            if actual_margins.get(edge) != exp_twips:
                error(f"Margin {edge} is {actual_margins.get(edge)} twips, "
                      f"expected {exp_twips}")
        header_text = "\n".join(p.text for p in section.header.paragraphs)
        if header_text != dl["header"]:
            error(f"Unexpected header text: {header_text!r}")
        footer_text = "\n".join(p.text for p in section.footer.paragraphs)
        if dl["footer_contains"] not in footer_text:
            error(f"Footer does not contain {dl['footer_contains']!r}: "
                  f"{footer_text!r}")

    # Document-level: title style.
    if title_paragraph is not None and title_paragraph.runs:
        title_run = title_paragraph.runs[0]
        if title_run.font.name != dl["title_font"]:
            error(f"Title font is {title_run.font.name!r}")
        if title_run.font.size is None or title_run.font.size.pt != dl["title_size_pt"]:
            error(f"Title size is {title_run.font.size!r}")
        if str(title_run.font.color.rgb) != dl["title_color"]:
            error(f"Title color is {title_run.font.color.rgb!r}")
        if not title_run.font.bold:
            error("Title is not bold")
    for heading in doc.paragraphs:
        if heading.style and heading.style.name == "Heading 1":
            for run in heading.runs:
                if str(run.font.color.rgb) != dl["heading_color"]:
                    error(f"Heading color wrong for {heading.text!r}")

    # Document-level: page breaks before derived headings.
    break_set = set(expected["page_break_headings"])
    for paragraph in doc.paragraphs:
        if paragraph.style and paragraph.style.name == "Heading 1":
            if paragraph.text in break_set and not paragraph.paragraph_format.page_break_before:
                error(f"Missing page break before {paragraph.text!r}")

    # Document-level: table header fills (one pass over every content table;
    # the cover label/value table has no shaded header row).
    for table_index, table in enumerate(doc.tables, start=1):
        if not table.rows:
            error(f"Table {table_index} has no rows")
            continue
        if table.rows[0].cells[0].text == "Release date":
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

    # Package-level: TOC field present and forbidden values gone.
    with zipfile.ZipFile(output_path, "r") as z:
        names = set(z.namelist())
        document_xml = z.read("word/document.xml").decode("utf-8", errors="ignore")
        footer_xml = next(
            (z.read(name).decode("utf-8", errors="ignore")
             for name in names if name.startswith("word/footer")), "")
        xml_text = "\n".join(
            z.read(name).decode("utf-8", errors="ignore")
            for name in names if name.endswith((".xml", ".rels"))
        )
        if 'TOC \\o "1-1"' not in document_xml and "TOC \\o &quot;1-1&quot;" not in document_xml:
            error("Real TOC field is missing")
        if " PAGE " not in footer_xml:
            error("PAGE footer field is missing")

        # Normalize the package once; the forbidden list is matched with token
        # boundaries only.
        xml_lowered = xml_text.lower()
        for token in expected["forbidden_xml"]:
            if re.search(rf"(?<!\w){re.escape(token.lower())}(?!\w)", xml_lowered):
                error(f"Private value remains in package XML: {token}")

    # TOC page numbers must match the real final layout (all entries).
    if structure_only:
        report["toc_pages"] = {"skipped_structure_only": True}
    else:
        pages = render_and_measure(Path(output_path), expected["headings"])
        toc_errors, toc_info = verify_toc_pages(doc, pages, expected["headings"])
        for message in toc_errors:
            error(message)
        report["toc_pages"] = toc_info

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
    parser.add_argument("--structure-only", action="store_true",
                        help="fixture mode: skip the LibreOffice TOC re-render (never used by formal recipes)")
    args = parser.parse_args(argv)
    if not args.output:
        parser.error("--output is required (or set VARIANT_OUTPUT)")
    report = check(Path(args.output), Path(args.expected), structure_only=args.structure_only)
    Path(args.report).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if report["errors"]:
        raise SystemExit(f"Validation failed with {len(report['errors'])} error(s)")
    print("All structural, content, TOC-page and document-level checks passed.")


if __name__ == "__main__":
    main()
