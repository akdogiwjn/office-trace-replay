#!/usr/bin/env python3
"""Build the water-main-break public records release packet.

The pipeline keeps intermediate stage files under /root/tmp/docs so the
ordered transformation is auditable. The official source is opened read-only.
"""

from __future__ import annotations

import copy
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from lxml import etree


SOURCE = Path(
    "/root/docops_v2_l3_003_docx_public_records_release_metadata_cleanup_input.docx"
)
STAGE_DIR = Path("/root/tmp/docs/stages_v2")
OUTPUT = Path(
    "/root/submission/"
    "docops_v2_l3_003_docx_public_records_release_metadata_cleanup_output.docx"
)

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


CORRECTIONS = {
    "2026-01-08": "2026-01-18",
    "34 claims": "37 claims",
    "$500": "$650",
    "Marcus Vale": "Public Records Desk",
    "Eliza Park": "Public Records Desk",
    "2026-07-31": "2026-08-15",
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
    set_text(
        core,
        DCTERMS_NS,
        "created",
        "2026-11-03T00:00:00Z",
    )
    set_text(
        core,
        DCTERMS_NS,
        "modified",
        "2026-11-03T00:00:00Z",
    )

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


def replace_in_paragraph(paragraph, replacements: dict[str, str]) -> None:
    if not paragraph.runs:
        updated = paragraph.text
        for old, new in replacements.items():
            updated = updated.replace(old, new)
        if updated != paragraph.text:
            paragraph.add_run(updated)
        return

    # Keep the first run's formatting while avoiding text fragmented across runs.
    original = paragraph.text
    updated = original
    for old, new in replacements.items():
        updated = updated.replace(old, new)
    if updated != original:
        paragraph.runs[0].text = updated
        for run in paragraph.runs[1:]:
            run._element.getparent().remove(run._element)


def stage_4_apply_correction_memo(source: Path, destination: Path) -> None:
    doc = Document(source)
    all_text = "\n".join(p.text for p in doc.paragraphs)
    for old, new in CORRECTIONS.items():
        if old not in all_text and old not in {"Marcus Vale", "Eliza Park"}:
            raise RuntimeError(f"Correction memo source value missing: {old}")

    for paragraph in doc.paragraphs:
        replace_in_paragraph(paragraph, CORRECTIONS)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    replace_in_paragraph(paragraph, CORRECTIONS)

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


def stage_6_rebuild_public_packet(source: Path, destination: Path) -> None:
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
        "This packet provides corrected, publicly releasable information about "
        "reimbursement claims following the water main break on 2026-01-18. "
        "The public claim count is deduplicated, and individual claim files are "
        "not included. Eligibility and reimbursement determinations are subject "
        "to the corrected cap and the published response deadline.",
    )
    contact_paragraph = add_body_paragraph(
        doc,
        "Public contact: ",
        bold_lead="Public contact: ",
        space_after=2,
    )
    contact_value = contact_paragraph.add_run("Public Records Desk")
    set_run_font(contact_value, BODY_FONT, 10.5, bold=True)
    deadline_paragraph = add_body_paragraph(
        doc,
        "Response deadline: ",
        bold_lead="Response deadline: ",
        space_after=4,
    )
    deadline_value = deadline_paragraph.add_run("2026-08-15")
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
            ["Incident date", "2026-01-18"],
            ["Deduplicated claim count", "37"],
            ["Reimbursable cap per eligible claim", "$650"],
            ["Public contact", "Public Records Desk"],
            ["Response deadline", "2026-08-15"],
        ],
        [3.35, 3.65],
    )

    add_heading(doc, "Claim Category Table")
    add_body_paragraph(
        doc,
        "These mutually exclusive aggregate categories total 37 deduplicated "
        "claims and exclude individual identifiers.",
    )
    add_public_table(
        doc,
        ["Claim category", "Claims", "Public treatment"],
        [
            ["Residential service line damage", "14", "Included in aggregate"],
            ["Interior property damage", "12", "Included in aggregate"],
            ["Emergency repair costs", "7", "Included in aggregate"],
            ["Documentation and administrative costs", "4", "Included in aggregate"],
            ["Total", "37", "Public count"],
        ],
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
        "Record receipt and confirm eligibility against the $650 corrected cap.",
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
        ("Appendix B", "Claim Category Table", "Section 4"),
        ("Appendix C", "Notification Workflow", "Section 5"),
        ("Appendix D", "Redaction and Metadata Checklist", "Section 6"),
        ("Appendix E", "Release contact and response deadline", "Release Summary"),
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


def main() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(SOURCE)
    STAGE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    stages = [
        ("01_tracked_changes_resolved.docx", stage_1_resolve_tracked_changes),
        ("02_comments_removed.docx", stage_2_remove_comments),
        ("03_metadata_cleaned.docx", stage_3_clean_metadata),
        ("04_correction_memo_applied.docx", stage_4_apply_correction_memo),
        ("05_working_content_redacted.docx", stage_5_redact_working_content),
        ("06_public_packet_rebuilt.docx", stage_6_rebuild_public_packet),
    ]

    previous = SOURCE
    for filename, function in stages:
        destination = STAGE_DIR / filename
        function(previous, destination)
        if not destination.exists() or destination.stat().st_size == 0:
            raise RuntimeError(f"Stage failed to produce {destination}")
        previous = destination

    safety_output = STAGE_DIR / "07_final_package_sanitized.docx"
    sanitize_final_package(previous, safety_output)
    shutil.copyfile(safety_output, OUTPUT)

    manifest = {
        "source": str(SOURCE),
        "output": str(OUTPUT),
        "completed_order": [
            "Resolved tracked insertions and deletions",
            "Removed comment text, ranges, references, and relationships",
            "Cleaned document properties and preview/custom metadata",
            "Applied all five correction-memo determinations",
            "Removed working content containing names, addresses, phones, and legal analysis",
            "Rebuilt sections, three public tables, footer, page breaks, and styles",
            "Sanitized the final package and copied it to the required output path",
        ],
        "corrections": CORRECTIONS,
    }
    (STAGE_DIR / "build_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
