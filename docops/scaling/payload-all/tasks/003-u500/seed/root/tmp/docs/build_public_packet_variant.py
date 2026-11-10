#!/usr/bin/env python3
"""Parameterized builder for synthetic scaled Word 003 variants.

Mirrors the frozen parent build_public_packet.py stage order and tools:

  1 resolve tracked changes -> 2 remove comments -> 3 clean metadata ->
  4 apply correction memo -> 5 redact working content -> 6 rebuild public packet
  -> final OOXML safety sanitize.

The only parameterized parts are stage 4 (the correction memo is derived from
the frozen units.json, global facts plus every unit's corrected amount/status)
and stage 6 (the public packet iterates every declared business unit instead of
emitting one fixed document). The processing stages themselves are unchanged.

No random business data is generated during the build: units.json is frozen at
prepare time and read verbatim.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from lxml import etree

PUBLIC_TITLE = "Public Release Packet: Water Main Break Claims"
PUBLIC_AUTHOR = "Public Records Office"
PUBLIC_SUBJECT = "Clean public release packet"
PUBLIC_FOOTER = "Public Records Release | Water Main Break Claims | 2026"
NAVY = "1F4E79"
BODY_FONT = "Aptos"
TITLE_FONT = "Aptos Display"

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
CP_NS = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
DC_NS = "http://purl.org/dc/elements/1.1/"
DCTERMS_NS = "http://purl.org/dc/terms/"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
EP_NS = (
    "http://schemas.openxmlformats.org/officeDocument/2006/"
    "extended-properties"
)
VT_NS = (
    "http://schemas.openxmlformats.org/officeDocument/2006/"
    "docPropsVTypes"
)

NS = {
    "w": W_NS,
    "cp": CP_NS,
    "dc": DC_NS,
    "dcterms": DCTERMS_NS,
    "xsi": XSI_NS,
    "rel": REL_NS,
    "ct": CT_NS,
    "ep": EP_NS,
    "vt": VT_NS,
}


def xml_bytes(root: etree._Element) -> bytes:
    return etree.tostring(
        root, xml_declaration=True, encoding="UTF-8", standalone=True
    )


def rewrite_package(
    source: Path,
    destination: Path,
    updates: dict[str, bytes] | None = None,
    omit: set[str] | None = None,
) -> None:
    """Copy a docx package, replacing or omitting selected parts."""
    updates = updates or {}
    omit = omit or set()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source, "r") as zin, zipfile.ZipFile(
        destination, "w", compression=zipfile.ZIP_DEFLATED
    ) as zout:
        for info in zin.infolist():
            if info.filename in omit:
                continue
            data = updates.get(info.filename, zin.read(info.filename))
            zout.writestr(info, data)


def stage_1_resolve_tracked_changes(source: Path, destination: Path) -> None:
    with zipfile.ZipFile(source, "r") as z:
        document_root = etree.fromstring(z.read("word/document.xml"))

    deleted = document_root.xpath(".//w:del", namespaces=NS)
    inserted = document_root.xpath(".//w:ins", namespaces=NS)
    if not deleted and not inserted:
        raise RuntimeError("Expected tracked changes in the source document")

    for element in deleted:
        element.getparent().remove(element)

    for element in inserted:
        parent = element.getparent()
        index = parent.index(element)
        for child in list(element):
            parent.insert(index, child)
            index += 1
        parent.remove(element)

    rewrite_package(
        source,
        destination,
        updates={"word/document.xml": xml_bytes(document_root)},
    )


def stage_2_remove_comments(source: Path, destination: Path) -> None:
    with zipfile.ZipFile(source, "r") as z:
        names = set(z.namelist())
        document_root = etree.fromstring(z.read("word/document.xml"))
        relationships = etree.fromstring(z.read("word/_rels/document.xml.rels"))
        content_types = etree.fromstring(z.read("[Content_Types].xml"))

    for xpath in (
        ".//w:commentRangeStart",
        ".//w:commentRangeEnd",
        ".//w:commentReference",
    ):
        for element in document_root.xpath(xpath, namespaces=NS):
            element.getparent().remove(element)

    for relationship in list(relationships):
        if relationship.get("Type", "").endswith("/comments"):
            relationships.remove(relationship)

    for override in list(content_types):
        if override.get("PartName") == "/word/comments.xml":
            content_types.remove(override)

    omit = {
        name
        for name in names
        if name == "word/comments.xml"
        or name.startswith("word/comments")
        or "commentsExtended" in name
    }
    rewrite_package(
        source,
        destination,
        updates={
            "word/document.xml": xml_bytes(document_root),
            "word/_rels/document.xml.rels": xml_bytes(relationships),
            "[Content_Types].xml": xml_bytes(content_types),
        },
        omit=omit,
    )


def set_text(parent: etree._Element, namespace: str, local_name: str, text: str | None) -> None:
    tag = f"{{{namespace}}}{local_name}"
    element = parent.find(tag)
    if element is None:
        element = etree.SubElement(parent, tag)
    element.text = text


def remove_children(parent: etree._Element, *local_names: str) -> None:
    for child in list(parent):
        if child.tag.rsplit("}", 1)[-1] in local_names:
            parent.remove(child)


def stage_3_clean_metadata(source: Path, destination: Path) -> None:
    with zipfile.ZipFile(source, "r") as z:
        names = set(z.namelist())
        core = etree.fromstring(z.read("docProps/core.xml"))
        app = etree.fromstring(z.read("docProps/app.xml"))
        settings = etree.fromstring(z.read("word/settings.xml"))
        root_relationships = etree.fromstring(z.read("_rels/.rels"))
        word_relationships = etree.fromstring(
            z.read("word/_rels/document.xml.rels")
        )
        content_types = etree.fromstring(z.read("[Content_Types].xml"))

    set_text(core, DC_NS, "title", PUBLIC_TITLE)
    set_text(core, DC_NS, "subject", PUBLIC_SUBJECT)
    set_text(core, DC_NS, "creator", PUBLIC_AUTHOR)
    set_text(core, CP_NS, "lastModifiedBy", PUBLIC_AUTHOR)
    set_text(core, CP_NS, "keywords", "")
    set_text(core, DC_NS, "description", "")
    set_text(core, CP_NS, "category", "Public Records")
    set_text(core, CP_NS, "contentStatus", "Released")
    set_text(core, CP_NS, "revision", "1")
    set_text(core, DCTERMS_NS, "created", "2026-11-03T00:00:00Z")
    set_text(core, DCTERMS_NS, "modified", "2026-11-03T00:00:00Z")

    for element in app.findall(f"{{{EP_NS}}}Manager"):
        element.text = ""
    for element in app.findall(f"{{{EP_NS}}}Company"):
        element.text = ""
    for element in app.findall(f"{{{EP_NS}}}TitlesOfParts"):
        lpstrings = element.findall(f".//{{{VT_NS}}}lpstr")
        if lpstrings:
            lpstrings[0].text = PUBLIC_TITLE

    remove_children(
        settings,
        "savePreviewPicture",
        "rsids",
        "trackRevisions",
        "documentProtection",
        "attachedTemplate",
    )

    for relationship in list(root_relationships):
        rel_type = relationship.get("Type", "")
        if rel_type.endswith("/thumbnail") or rel_type.endswith("/custom-properties"):
            root_relationships.remove(relationship)

    for relationship in list(word_relationships):
        target = relationship.get("Target", "")
        rel_type = relationship.get("Type", "")
        if (
            rel_type.endswith("/customXml")
            or "customXml" in target
            or rel_type.endswith("/comments")
            or target.endswith("comments.xml")
        ):
            word_relationships.remove(relationship)

    for override in list(content_types):
        part_name = override.get("PartName", "")
        if (
            part_name.startswith("/customXml/")
            or part_name == "/docProps/thumbnail.jpeg"
            or "comments" in part_name.lower()
            or part_name == "/docProps/custom.xml"
        ):
            content_types.remove(override)

    omit = {
        name
        for name in names
        if name.startswith("customXml/")
        or name == "docProps/thumbnail.jpeg"
        or name == "docProps/custom.xml"
        or "comments" in name.lower()
    }
    rewrite_package(
        source,
        destination,
        updates={
            "docProps/core.xml": xml_bytes(core),
            "docProps/app.xml": xml_bytes(app),
            "word/settings.xml": xml_bytes(settings),
            "_rels/.rels": xml_bytes(root_relationships),
            "word/_rels/document.xml.rels": xml_bytes(word_relationships),
            "[Content_Types].xml": xml_bytes(content_types),
        },
        omit=omit,
    )


def build_corrections(data: dict) -> dict:
    """Global memo facts plus every unit's per-unit corrections (unique keys)."""
    corrections = {
        "2026-01-08": "2026-01-18",
        "34 claims": f"{len(data['units'])} claims",
        "$500": "$650",
        "Marcus Vale": "Public Records Desk",
        "Eliza Park": "Public Records Desk",
        "2026-07-31": "2026-08-15",
    }
    for unit in data["units"]:
        corrections[f"${unit['wrong_amount']}"] = f"${unit['right_amount']}"
        corrections[unit["wrong_status"]] = unit["right_status"]
    return corrections


def replace_in_paragraph(paragraph, replacements: dict[str, str]) -> None:
    if not paragraph.runs:
        updated = paragraph.text
        for old, new in replacements.items():
            updated = updated.replace(old, new)
        if updated != paragraph.text:
            paragraph.add_run(updated)
        return

    original = paragraph.text
    updated = original
    for old, new in replacements.items():
        updated = updated.replace(old, new)
    if updated != original:
        paragraph.runs[0].text = updated
        for run in paragraph.runs[1:]:
            run._element.getparent().remove(run._element)


def stage_4_apply_correction_memo(source: Path, destination: Path, data: dict) -> None:
    corrections = build_corrections(data)
    doc = Document(source)
    all_text = "\n".join(p.text for p in doc.paragraphs)
    for old in corrections:
        if old not in all_text and old not in {"Marcus Vale", "Eliza Park"}:
            raise RuntimeError(f"Correction memo source value missing: {old}")

    for paragraph in doc.paragraphs:
        replace_in_paragraph(paragraph, corrections)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    replace_in_paragraph(paragraph, corrections)

    doc.core_properties.author = PUBLIC_AUTHOR
    doc.core_properties.last_modified_by = PUBLIC_AUTHOR
    doc.core_properties.title = PUBLIC_TITLE
    doc.core_properties.subject = PUBLIC_SUBJECT
    doc.core_properties.keywords = ""
    doc.core_properties.comments = ""
    doc.core_properties.category = "Public Records"
    doc.core_properties.content_status = "Released"
    doc.core_properties.created = datetime(2026, 11, 3, tzinfo=timezone.utc)
    doc.core_properties.modified = datetime(2026, 11, 3, tzinfo=timezone.utc)
    doc.save(destination)


def clear_footer(section) -> None:
    footer = section.footer
    footer.is_linked_to_previous = False
    for paragraph in list(footer.paragraphs)[1:]:
        paragraph._element.getparent().remove(paragraph._element)
    paragraph = footer.paragraphs[0]
    for run in list(paragraph.runs):
        run._element.getparent().remove(run._element)


def stage_5_redact_working_content(source: Path, destination: Path) -> None:
    doc = Document(source)
    body = doc._element.body
    for child in list(body):
        if child.tag != qn("w:sectPr"):
            body.remove(child)

    for section in doc.sections:
        clear_footer(section)

    doc.save(destination)


def set_run_font(run, font_name: str, size: float, bold: bool = False, color: str | None = None):
    run.font.name = font_name
    run.font.size = Pt(size)
    run.font.bold = bold
    if color:
        run.font.color.rgb = RGBColor.from_string(color)
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    for key in ("ascii", "hAnsi", "cs", "eastAsia"):
        rfonts.set(qn(f"w:{key}"), font_name)


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top=50, start=105, bottom=50, end=105):
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for margin, value in (
        ("top", top),
        ("start", start),
        ("bottom", bottom),
        ("end", end),
    ):
        node = tc_mar.find(qn(f"w:{margin}"))
        if node is None:
            node = OxmlElement(f"w:{margin}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_table_borders(table, color="BFC9D4", size="6") -> None:
    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.first_child_found_in("w:tblBorders")
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tbl_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        element = borders.find(qn(f"w:{edge}"))
        if element is None:
            element = OxmlElement(f"w:{edge}")
            borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), size)
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), color)


def mark_repeat_table_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def prevent_row_split(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    cant_split = OxmlElement("w:cantSplit")
    tr_pr.append(cant_split)


def add_heading(doc: Document, text: str, page_break_before: bool = False):
    paragraph = doc.add_paragraph(style="Heading 1")
    paragraph.paragraph_format.space_before = Pt(11 if not page_break_before else 0)
    paragraph.paragraph_format.space_after = Pt(6)
    paragraph.paragraph_format.keep_with_next = True
    if page_break_before:
        paragraph.paragraph_format.page_break_before = True
    run = paragraph.add_run(text)
    set_run_font(run, TITLE_FONT, 13.5, bold=True, color=NAVY)
    return paragraph


def add_body_paragraph(
    doc: Document,
    text: str = "",
    *,
    style: str | None = None,
    bold_lead: str | None = None,
    space_after: float = 5,
):
    paragraph = doc.add_paragraph(style=style)
    paragraph.paragraph_format.space_after = Pt(space_after)
    paragraph.paragraph_format.line_spacing = 1.08
    if bold_lead and text.startswith(bold_lead):
        lead = paragraph.add_run(bold_lead)
        set_run_font(lead, BODY_FONT, 10.5, bold=True)
        rest = paragraph.add_run(text[len(bold_lead):])
        set_run_font(rest, BODY_FONT, 10.5)
    elif text:
        run = paragraph.add_run(text)
        set_run_font(run, BODY_FONT, 10.5)
    return paragraph


def add_public_table(
    doc: Document,
    headers: list[str],
    rows: list[list[str]],
    widths: list[float],
):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    table.autofit = False
    table.allow_autofit = False
    set_table_borders(table)

    header = table.rows[0]
    mark_repeat_table_header(header)
    prevent_row_split(header)
    for index, value in enumerate(headers):
        cell = header.cells[index]
        cell.width = Inches(widths[index])
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        set_cell_shading(cell, NAVY)
        set_cell_margins(cell)
        paragraph = cell.paragraphs[0]
        paragraph.paragraph_format.space_after = Pt(0)
        run = paragraph.add_run(value)
        set_run_font(run, BODY_FONT, 10.5, bold=True, color="FFFFFF")

    for row_index, values in enumerate(rows):
        row = table.add_row()
        prevent_row_split(row)
        if row_index % 2 == 1:
            for cell in row.cells:
                set_cell_shading(cell, "EAF1F8")
        for index, value in enumerate(values):
            cell = row.cells[index]
            cell.width = Inches(widths[index])
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_margins(cell)
            paragraph = cell.paragraphs[0]
            paragraph.paragraph_format.space_after = Pt(0)
            run = paragraph.add_run(value)
            set_run_font(run, BODY_FONT, 10.5, bold=value == "Total")
    return table


def add_numbered_step(doc: Document, text: str):
    paragraph = add_body_paragraph(doc, text, style="List Number", space_after=2)
    paragraph.paragraph_format.left_indent = Inches(0.25)
    paragraph.paragraph_format.first_line_indent = Inches(-0.25)
    return paragraph


def add_footer(section) -> None:
    footer = section.footer
    footer.is_linked_to_previous = False
    paragraph = footer.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(0)
    for run in list(paragraph.runs):
        run._element.getparent().remove(run._element)
    run = paragraph.add_run(PUBLIC_FOOTER)
    set_run_font(run, BODY_FONT, 9, color="595959")

    p_pr = paragraph._p.get_or_add_pPr()
    borders = p_pr.find(qn("w:pBdr"))
    if borders is None:
        borders = OxmlElement("w:pBdr")
        p_pr.append(borders)
    top = OxmlElement("w:top")
    top.set(qn("w:val"), "single")
    top.set(qn("w:sz"), "4")
    top.set(qn("w:space"), "5")
    top.set(qn("w:color"), "BFC9D4")
    borders.append(top)


def stage_6_rebuild_public_packet(source: Path, destination: Path, data: dict) -> None:
    doc = Document(source)
    body = doc._element.body
    for child in list(body):
        if child.tag != qn("w:sectPr"):
            body.remove(child)

    section = doc.sections[0]
    section.top_margin = Inches(0.75)
    section.right_margin = Inches(0.75)
    section.bottom_margin = Inches(0.75)
    section.left_margin = Inches(0.75)
    section.header_distance = Inches(0.35)
    section.footer_distance = Inches(0.35)

    normal = doc.styles["Normal"]
    normal.font.name = BODY_FONT
    normal.font.size = Pt(10.5)
    normal.paragraph_format.space_after = Pt(5)
    normal.paragraph_format.line_spacing = 1.08

    units = data["units"]
    n = len(units)
    cap = data["cap"]
    incident = data["incident_date"]
    deadline = data["deadline"]
    contact = data["contact"]

    title = doc.add_paragraph(style="Title")
    title.paragraph_format.space_before = Pt(0)
    title.paragraph_format.space_after = Pt(8)
    title.paragraph_format.keep_with_next = True
    title_run = title.add_run(PUBLIC_TITLE)
    set_run_font(title_run, TITLE_FONT, 18, bold=True, color=NAVY)

    add_body_paragraph(
        doc,
        "Prepared by the Public Records Office for release on 2026-11-03.",
        space_after=9,
    )

    add_heading(doc, "Release Summary")
    add_body_paragraph(
        doc,
        f"This packet provides corrected, publicly releasable information about "
        f"reimbursement claims following the water main break on {incident}. "
        f"The public claim count is deduplicated to {n} claims, and individual "
        f"claim files are not included. Eligibility and reimbursement "
        f"determinations are subject to the corrected cap and the published "
        f"response deadline.",
    )
    contact_paragraph = add_body_paragraph(
        doc, "Public contact: ", bold_lead="Public contact: ", space_after=2)
    contact_value = contact_paragraph.add_run(contact)
    set_run_font(contact_value, BODY_FONT, 10.5, bold=True)
    deadline_paragraph = add_body_paragraph(
        doc, "Response deadline: ", bold_lead="Response deadline: ", space_after=4)
    deadline_value = deadline_paragraph.add_run(deadline)
    set_run_font(deadline_value, BODY_FONT, 10.5, bold=True)

    add_heading(doc, "Corrected Determination Facts")
    add_body_paragraph(
        doc,
        "The corrected values below supersede earlier dates and amounts used in "
        "preliminary materials.",
    )
    add_public_table(
        doc,
        ["Determination field", "Corrected public value"],
        [
            ["Incident date", incident],
            ["Deduplicated claim count", str(n)],
            ["Reimbursable cap per eligible claim", f"${cap}"],
            ["Public contact", contact],
            ["Response deadline", deadline],
        ],
        [3.35, 3.65],
    )

    add_heading(doc, "Corrected Claim Determinations", page_break_before=True)
    add_body_paragraph(
        doc,
        f"The packet records one corrected public determination for each of the "
        f"{n} deduplicated claims. Amounts reflect the ${cap} cap and the "
        f"published corrections.",
    )
    for unit in units:
        add_heading(
            doc,
            f"Unit {unit['id']} — {unit['category']}",
            page_break_before=True,
        )
        add_body_paragraph(
            doc,
            f"Claim {unit['id']} corrected public determination: "
            f"${unit['right_amount']} reimbursable for {unit['category']}. "
            f"Determination status: {unit['right_status']}.",
        )
        add_public_table(
            doc,
            ["Determination field", "Corrected public value"],
            [
                ["Business ID", unit["id"]],
                ["Claim category", unit["category"]],
                ["Reimbursable amount", f"${unit['right_amount']}"],
                ["Determination status", unit["right_status"]],
            ],
            [3.35, 3.65],
        )

    add_heading(doc, "Claim Category Table")
    add_body_paragraph(
        doc,
        f"These mutually exclusive aggregate categories total {n} deduplicated "
        f"claims and exclude individual identifiers.",
    )
    counts = {cat: sum(1 for u in units if u["category"] == cat)
              for cat in data["categories"]}
    category_rows = [[cat, str(counts[cat]), "Included in aggregate"]
                     for cat in data["categories"]]
    category_rows.append(["Total", str(n), "Public count"])
    add_public_table(
        doc,
        ["Claim category", "Claims", "Public treatment"],
        category_rows,
        [3.2, 0.8, 3.0],
    )

    add_heading(doc, "Notification Workflow")
    add_body_paragraph(
        doc,
        "The public notification and reimbursement workflow follows these steps:",
    )
    workflow = [
        "Publish the corrected facts, Public Records Desk contact, and response deadline.",
        "Direct claimants to submit claim references and documentation to the Public Records Desk.",
        f"Record receipt and confirm eligibility against the ${cap} corrected cap.",
        "Issue a determination notice with the approved amount and next steps.",
        "Update aggregate totals without claimant identities, addresses, phone numbers, or claim-level notes.",
    ]
    for step in workflow:
        add_numbered_step(doc, step)

    add_heading(doc, "Redaction and Metadata Checklist", page_break_before=True)
    add_body_paragraph(
        doc,
        "The release package was checked against these publication controls.",
    )
    add_public_table(
        doc,
        ["Review item", "Public release control", "Status"],
        [
            ["Claimant identities", "Names and claim-level identifiers excluded", "Complete"],
            ["Home addresses", "Residential addresses removed", "Complete"],
            ["Phone numbers", "Personal numbers removed", "Complete"],
            ["Settlement analysis", "Legal strategy discussion excluded", "Complete"],
            ["Tracked changes", "Changes resolved and structural markers removed", "Complete"],
            ["Review comments", "Comment text and relationships deleted", "Complete"],
            ["Document properties", "Public release metadata only", "Complete"],
            ["Working labels", "Earlier labels removed from content and footer", "Complete"],
        ],
        [1.8, 3.9, 1.3],
    )

    add_heading(doc, "Public Appendix Index", page_break_before=True)
    add_body_paragraph(
        doc,
        "The packet is organized into the following public reference items:",
    )
    appendix_items = [
        ("Appendix A", "Corrected Determination Facts", "Section 3"),
        ("Appendix B", "Corrected Claim Determinations", f"{n} claim units"),
        ("Appendix C", "Claim Category Table", "Section 5"),
        ("Appendix D", "Notification Workflow", "Section 6"),
        ("Appendix E", "Redaction and Metadata Checklist", "Section 7"),
        ("Appendix F", "Release contact and response deadline", "Release Summary"),
    ]
    for label, item, location in appendix_items:
        paragraph = add_body_paragraph(doc, space_after=6)
        paragraph.paragraph_format.left_indent = Inches(0.22)
        paragraph.paragraph_format.first_line_indent = Inches(-0.22)
        lead = paragraph.add_run(f"{label}: ")
        set_run_font(lead, BODY_FONT, 10.5, bold=True)
        detail = paragraph.add_run(f"{item} - {location}")
        set_run_font(detail, BODY_FONT, 10.5)

    add_footer(section)
    doc.save(destination)


def sanitize_final_package(source: Path, destination: Path) -> None:
    """Apply a final package-level safety pass after python-docx serialization."""
    with zipfile.ZipFile(source, "r") as z:
        names = set(z.namelist())
        document_root = etree.fromstring(z.read("word/document.xml"))
        core = etree.fromstring(z.read("docProps/core.xml"))
        app = etree.fromstring(z.read("docProps/app.xml"))
        settings = etree.fromstring(z.read("word/settings.xml"))
        root_relationships = etree.fromstring(z.read("_rels/.rels"))
        word_relationships = etree.fromstring(
            z.read("word/_rels/document.xml.rels")
        )
        content_types = etree.fromstring(z.read("[Content_Types].xml"))

    for xpath in (
        ".//w:ins",
        ".//w:del",
        ".//w:commentRangeStart",
        ".//w:commentRangeEnd",
        ".//w:commentReference",
    ):
        for element in document_root.xpath(xpath, namespaces=NS):
            element.getparent().remove(element)

    set_text(core, DC_NS, "title", PUBLIC_TITLE)
    set_text(core, DC_NS, "subject", PUBLIC_SUBJECT)
    set_text(core, DC_NS, "creator", PUBLIC_AUTHOR)
    set_text(core, CP_NS, "lastModifiedBy", PUBLIC_AUTHOR)
    set_text(core, CP_NS, "keywords", "")
    set_text(core, DC_NS, "description", "")
    set_text(core, CP_NS, "category", "Public Records")
    set_text(core, CP_NS, "contentStatus", "Released")
    set_text(core, CP_NS, "revision", "1")
    set_text(core, DCTERMS_NS, "created", "2026-11-03T00:00:00Z")
    set_text(core, DCTERMS_NS, "modified", "2026-11-03T00:00:00Z")

    for element in app.findall(f"{{{EP_NS}}}Manager"):
        element.text = ""
    for element in app.findall(f"{{{EP_NS}}}Company"):
        element.text = ""

    remove_children(
        settings,
        "savePreviewPicture",
        "rsids",
        "trackRevisions",
        "documentProtection",
        "attachedTemplate",
    )

    for relationship in list(root_relationships):
        rel_type = relationship.get("Type", "")
        if rel_type.endswith("/thumbnail") or rel_type.endswith("/custom-properties"):
            root_relationships.remove(relationship)

    for relationship in list(word_relationships):
        rel_type = relationship.get("Type", "")
        target = relationship.get("Target", "")
        if (
            rel_type.endswith("/comments")
            or rel_type.endswith("/customXml")
            or "comments" in target.lower()
            or "customXml" in target
        ):
            word_relationships.remove(relationship)

    for override in list(content_types):
        part_name = override.get("PartName", "")
        if (
            "comments" in part_name.lower()
            or part_name.startswith("/customXml/")
            or part_name == "/docProps/thumbnail.jpeg"
            or part_name == "/docProps/custom.xml"
        ):
            content_types.remove(override)

    omit = {
        name
        for name in names
        if "comments" in name.lower()
        or name.startswith("customXml/")
        or name == "docProps/thumbnail.jpeg"
        or name == "docProps/custom.xml"
    }
    rewrite_package(
        source,
        destination,
        updates={
            "word/document.xml": xml_bytes(document_root),
            "docProps/core.xml": xml_bytes(core),
            "docProps/app.xml": xml_bytes(app),
            "word/settings.xml": xml_bytes(settings),
            "_rels/.rels": xml_bytes(root_relationships),
            "word/_rels/document.xml.rels": xml_bytes(word_relationships),
            "[Content_Types].xml": xml_bytes(content_types),
        },
        omit=omit,
    )


def _deterministic_zip(src: Path, dst: Path) -> None:
    """Repack a docx with fixed entry timestamps so identical content always
    produces identical bytes (the replay loop archives and hashes outputs)."""
    import zipfile as _zipfile

    with _zipfile.ZipFile(src) as zin, _zipfile.ZipFile(
        dst, "w", _zipfile.ZIP_DEFLATED
    ) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            item.date_time = (1980, 1, 1, 0, 0, 0)
            item.extra = b""
            item.comment = b""
            item.compress_type = _zipfile.ZIP_DEFLATED
            item.external_attr = 0o600 << 16
            zout.writestr(item, data)


def build(source: Path, units_path: Path, output: Path, stage_dir: Path | None = None):
    data = json.loads(Path(units_path).read_text(encoding="utf-8"))
    stage_dir = stage_dir or (Path("/root/tmp/docs/stages_v2"))
    stage_dir.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)

    stages = [
        ("01_tracked_changes_resolved.docx", stage_1_resolve_tracked_changes),
        ("02_comments_removed.docx", stage_2_remove_comments),
        ("03_metadata_cleaned.docx", stage_3_clean_metadata),
        ("04_correction_memo_applied.docx",
         lambda s, d: stage_4_apply_correction_memo(s, d, data)),
        ("05_working_content_redacted.docx", stage_5_redact_working_content),
        ("06_public_packet_rebuilt.docx",
         lambda s, d: stage_6_rebuild_public_packet(s, d, data)),
    ]

    previous = source
    for filename, function in stages:
        destination = stage_dir / filename
        function(previous, destination)
        if not destination.exists() or destination.stat().st_size == 0:
            raise RuntimeError(f"Stage failed to produce {destination}")
        previous = destination

    safety_output = stage_dir / "07_final_package_sanitized.docx"
    sanitize_final_package(previous, safety_output)
    raw_output = stage_dir / "08_final_raw.docx"
    shutil.copyfile(safety_output, raw_output)
    _deterministic_zip(raw_output, output)
    return len(data["units"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=os.environ.get("VARIANT_INPUT"),
                        help="source DOCX path")
    parser.add_argument("--units", default=os.environ.get("VARIANT_UNITS", "/root/tmp/docs/units.json"),
                        help="frozen units.json prepared material")
    parser.add_argument("--output", default=os.environ.get("VARIANT_OUTPUT"),
                        help="output DOCX path")
    parser.add_argument("--stage-dir", default=os.environ.get("VARIANT_STAGE_DIR"),
                        help="intermediate stage directory (default /root/tmp/docs/stages_v2)")
    args = parser.parse_args(argv)
    if not args.input or not args.output:
        parser.error("--input and --output are required (or set VARIANT_INPUT/VARIANT_OUTPUT)")
    count = build(Path(args.input), Path(args.units), Path(args.output),
                  Path(args.stage_dir) if args.stage_dir else None)
    print(args.output)
    print(f"Units: {count}")


if __name__ == "__main__":
    main()
