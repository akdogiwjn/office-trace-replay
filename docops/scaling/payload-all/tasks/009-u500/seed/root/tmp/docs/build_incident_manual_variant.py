#!/usr/bin/env python3
"""Parameterized builder for synthetic scaled Word 009 variants.

Mirrors the frozen parent 009 workflow (build_incident_manual_publication.py):
remove draft material, build the public cover and a real TOC field, reorder the
sections, normalize the six data tables, add page breaks, update header/footer,
highlight the open MFA evidence exception and append the final note.

The only parameterized parts are the six data tables: every declared incident
case from the frozen cases.json gets one real row in the response timeline,
customer communication, control exception, action register, evidence index and
approval tables, so the row counts are driven by the actual case count (the
last case is really written).

No random business data is generated during the build: cases.json is frozen at
prepare time and read verbatim. The synthetic DRAFT source is only verified
(its internal material is never carried into the output).
"""
from __future__ import annotations

import argparse
import json
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import (
    WD_ALIGN_PARAGRAPH,
    WD_BREAK,
    WD_COLOR_INDEX,
    WD_LINE_SPACING,
    WD_TAB_ALIGNMENT,
    WD_TAB_LEADER,
)
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

RELEASE_DATE = "2026-06-05"
PUBLIC_TITLE = "Incident Response Manual | Public Release"
PUBLIC_SUBJECT = "Release-safe public incident response manual"
PUBLIC_AUTHOR = "Security Operations Publication Office"
PUBLIC_HEADER = "Incident Response Manual | Public Release | 2026-06-05"
PUBLIC_KEYWORDS = "incident response; public release; control exceptions"
PUBLIC_COMMENTS = "Public edition with privileged and internal material removed."

NAVY = "17324D"
TEAL = "0E7C86"
MIDNIGHT = "102A43"
SLATE = "425466"
MUTED = "627D98"
PALE_TEAL = "E7F3F4"
PALE_BLUE = "EEF3F8"
ROW_ALT = "F6F9FB"
GRID = "D4DEE8"
WHITE = "FFFFFF"
BODY_FONT = "Arial"

HEADINGS = [
    "Publication Summary",
    "Response Timeline",
    "Customer Communication",
    "Control Exceptions",
    "Action Register",
    "Appendix A - Evidence Index",
    "Appendix B - Approval Record",
]
PAGE_BREAK_HEADINGS = [
    "Control Exceptions",
    "Action Register",
    "Appendix A - Evidence Index",
    "Appendix B - Approval Record",
]
TOC_ENTRIES = [
    ("Publication Summary", "1"),
    ("Response Timeline", "1"),
    ("Customer Communication", "1"),
    ("Control Exceptions", "1"),
    ("Action Register", "1"),
    ("Appendix A - Evidence Index", "1"),
    ("Appendix B - Approval Record", "1"),
]

TIMELINE_HEADER = ["Time", "Milestone", "Public Summary"]
COMMUNICATION_HEADER = ["Audience", "Message Owner", "Required Update", "Status"]
EXCEPTION_HEADER = ["Exception ID", "Control", "Owner", "Release Status"]
ACTION_HEADER = ["Action ID", "Owner", "Due Date", "Publish Status"]
EVIDENCE_HEADER = ["Evidence ID", "Public Label", "Disposition"]
APPROVAL_HEADER = ["Approver", "Role", "Decision"]

FIXED_PARAGRAPHS = [
    "This public manual summarizes the June 2026 incident response without "
    "privileged root-cause analysis.",
    "Customer-facing language has been normalized and internal notes have "
    "been removed.",
    "Exception: MFA evidence owner remains unassigned.",
    "Resolved exception: log retention evidence was exported and approved.",
]


def set_run_font(run, *, size=None, bold=None, italic=None, color=None,
                 font=BODY_FONT):
    run.font.name = font
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), font)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    if color:
        run.font.color.rgb = RGBColor.from_string(color)


def set_paragraph_border(paragraph, *, side="bottom", color=GRID, size=6, space=4):
    ppr = paragraph._p.get_or_add_pPr()
    pbdr = ppr.find(qn("w:pBdr"))
    if pbdr is None:
        pbdr = OxmlElement("w:pBdr")
        ppr.append(pbdr)
    border = OxmlElement(f"w:{side}")
    border.set(qn("w:val"), "single")
    border.set(qn("w:sz"), str(size))
    border.set(qn("w:space"), str(space))
    border.set(qn("w:color"), color)
    pbdr.append(border)


def set_paragraph_shading(paragraph, fill):
    ppr = paragraph._p.get_or_add_pPr()
    shd = ppr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        ppr.append(shd)
    shd.set(qn("w:fill"), fill)
    shd.set(qn("w:val"), "clear")


def set_cell_shading(cell, fill):
    tcpr = cell._tc.get_or_add_tcPr()
    shd = tcpr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tcpr.append(shd)
    shd.set(qn("w:fill"), fill)
    shd.set(qn("w:val"), "clear")


def set_cell_margins(cell, *, top=90, start=110, bottom=90, end=110):
    tcpr = cell._tc.get_or_add_tcPr()
    tc_mar = tcpr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tcpr.append(tc_mar)
    for margin_name, margin_value in (("top", top), ("start", start),
                                      ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{margin_name}"))
        if node is None:
            node = OxmlElement(f"w:{margin_name}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(margin_value))
        node.set(qn("w:type"), "dxa")


def set_table_borders(table, color=GRID, size=5):
    tblpr = table._tbl.tblPr
    borders = tblpr.first_child_found_in("w:tblBorders")
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tblpr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        node = borders.find(qn(f"w:{edge}"))
        if node is None:
            node = OxmlElement(f"w:{edge}")
            borders.append(node)
        node.set(qn("w:val"), "single")
        node.set(qn("w:sz"), str(size))
        node.set(qn("w:space"), "0")
        node.set(qn("w:color"), color)


def set_table_fixed_layout(table, widths):
    table.autofit = False
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    tblpr = table._tbl.tblPr
    layout = tblpr.first_child_found_in("w:tblLayout")
    if layout is None:
        layout = OxmlElement("w:tblLayout")
        tblpr.append(layout)
    layout.set(qn("w:type"), "fixed")
    for column, width in zip(table.columns, widths, strict=True):
        column.width = Inches(width)
    for row in table.rows:
        for cell, width in zip(row.cells, widths, strict=True):
            cell.width = Inches(width)


def repeat_table_header(row):
    trpr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    trpr.append(tbl_header)


def prevent_row_split(row):
    trpr = row._tr.get_or_add_trPr()
    cant_split = OxmlElement("w:cantSplit")
    cant_split.set(qn("w:val"), "true")
    trpr.append(cant_split)


def write_cell(cell, text, *, header=False):
    p = cell.paragraphs[0]
    for run in list(p.runs):
        run._element.getparent().remove(run._element)
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1.0
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run(text)
    set_run_font(run, size=8.5 if header else 9.0, bold=header,
                 color=WHITE if header else MIDNIGHT)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    set_cell_margins(cell)


def add_public_table(doc, headers, rows, widths):
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = "Table Grid"
    set_table_borders(table)
    set_table_fixed_layout(table, widths)
    repeat_table_header(table.rows[0])

    for index, value in enumerate(headers):
        cell = table.rows[0].cells[index]
        write_cell(cell, value, header=True)
        set_cell_shading(cell, NAVY)

    for row_index, values in enumerate(rows, start=1):
        prevent_row_split(table.rows[row_index])
        fill = WHITE if row_index % 2 == 1 else ROW_ALT
        for column_index, value in enumerate(values):
            cell = table.rows[row_index].cells[column_index]
            write_cell(cell, value)
            set_cell_shading(cell, fill)

    doc.add_paragraph().paragraph_format.space_after = Pt(0)
    return table


def add_section_heading(doc, text, *, page_break_before=False, space_before=15):
    p = doc.add_paragraph(style="Heading 1")
    p.paragraph_format.page_break_before = page_break_before
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    set_run_font(run, size=18, bold=True, color=NAVY)
    set_paragraph_border(p, color=TEAL, size=12, space=5)
    return p


def add_intro(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    set_run_font(run, size=10, color=SLATE)
    return p


def add_table_caption(doc, text):
    p = doc.add_paragraph(style="Table Caption")
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    set_run_font(run, size=8.5, bold=True, color=TEAL)
    return p


def add_toc(doc):
    p = doc.add_paragraph(style="TOC Entry")
    p.paragraph_format.left_indent = Inches(0)
    p.paragraph_format.first_line_indent = Inches(0)
    p.paragraph_format.right_indent = Inches(0)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1.4
    p.paragraph_format.tab_stops.add_tab_stop(
        Inches(5.9), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)

    begin_run = p.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    begin.set(qn("w:dirty"), "true")
    begin_run._r.append(begin)

    instr_run = p.add_run()
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = ' TOC \\o "1-1" \\h \\z \\u '
    instr_run._r.append(instr)

    separate_run = p.add_run()
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    separate_run._r.append(separate)

    for index, (title, page) in enumerate(TOC_ENTRIES):
        run = p.add_run(title)
        set_run_font(run, size=10.5, bold=False, color=MIDNIGHT)
        tab_run = p.add_run("\t")
        set_run_font(tab_run, size=10.5, color=SLATE)
        page_run = p.add_run(page)
        set_run_font(page_run, size=10.5, bold=True, color=TEAL)
        if index != len(TOC_ENTRIES) - 1:
            line_break_run = p.add_run()
            line_break_run.add_break(WD_BREAK.LINE)

    end_run = p.add_run()
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    end_run._r.append(end)


def find_toc_paragraph(doc):
    """The single paragraph carrying the real TOC field instruction."""
    for p in doc.paragraphs:
        instr = [t.text for t in p._p.iter(qn("w:instrText")) if t.text]
        if any("TOC" in text for text in instr):
            return p
    return None


def extract_toc_entries(doc):
    """[(title, page_str)] from the TOC field's cached result runs."""
    p = find_toc_paragraph(doc)
    if p is None:
        return []
    runs = list(p._p.iter(qn("w:r")))
    entries = []
    pending = None
    for r in runs:
        text = "".join(t.text or "" for t in r.iter(qn("w:t")))
        if text and text.isdigit():
            if pending is not None:
                entries.append((pending, text))
            pending = None
        elif text and not text.startswith("\t"):
            pending = text
    return entries


def set_toc_pages(doc, pages: dict):
    """Replace the TOC field's cached page-number runs with measured pages.

    ``pages`` maps each section title to its real rendered page. The TOC field
    structure (begin/instr/separate ... cached result ... end) is preserved;
    only the digit-only result runs are rewritten.
    """
    p = find_toc_paragraph(doc)
    if p is None:
        raise RuntimeError("real TOC field paragraph not found")
    page_runs = []
    for r in p._p.iter(qn("w:r")):
        text = "".join(t.text or "" for t in r.iter(qn("w:t")))
        if text and text.isdigit():
            page_runs.append(r)
    if len(page_runs) != len(pages):
        raise RuntimeError(
            f"TOC page run count {len(page_runs)} != heading count {len(pages)}")
    for r, title in zip(page_runs, [t for t, _ in extract_toc_entries(doc)]):
        for t in r.iter(qn("w:t")):
            t.text = str(pages[title])
            break


def add_page_number_footer(paragraph):
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    label_run = paragraph.add_run("Page ")
    set_run_font(label_run, size=8.5, bold=True, color=SLATE)

    begin_run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    begin_run._r.append(begin)

    instruction_run = paragraph.add_run()
    instruction = OxmlElement("w:instrText")
    instruction.set(qn("xml:space"), "preserve")
    instruction.text = " PAGE "
    instruction_run._r.append(instruction)

    separate_run = paragraph.add_run()
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    separate_run._r.append(separate)

    result_run = paragraph.add_run("1")
    set_run_font(result_run, size=8.5, bold=True, color=TEAL)

    end_run = paragraph.add_run()
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    end_run._r.append(end)


def configure_styles(doc):
    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = BODY_FONT
    normal._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), BODY_FONT)
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = RGBColor.from_string(MIDNIGHT)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.12

    heading1 = styles["Heading 1"]
    heading1.font.name = BODY_FONT
    heading1.font.size = Pt(18)
    heading1.font.bold = True
    heading1.font.color.rgb = RGBColor.from_string(NAVY)
    heading1.paragraph_format.keep_with_next = True
    heading1.paragraph_format.page_break_before = False

    title = styles["Title"]
    title.font.name = BODY_FONT
    title.font.size = Pt(21)
    title.font.bold = True
    title.font.color.rgb = RGBColor.from_string(NAVY)
    title.paragraph_format.space_after = Pt(12)

    header = styles["Header"]
    header.font.name = BODY_FONT
    header.font.size = Pt(8)
    header.font.color.rgb = RGBColor.from_string(MUTED)

    footer = styles["Footer"]
    footer.font.name = BODY_FONT
    footer.font.size = Pt(8.5)
    footer.font.color.rgb = RGBColor.from_string(MUTED)

    table_caption = styles.add_style("Table Caption", 1)
    table_caption.base_style = styles["Normal"]
    table_caption.font.name = BODY_FONT
    table_caption.font.size = Pt(8.5)
    table_caption.font.bold = True
    table_caption.font.color.rgb = RGBColor.from_string(TEAL)
    table_caption.paragraph_format.space_before = Pt(2)
    table_caption.paragraph_format.space_after = Pt(4)

    toc_entry = styles.add_style("TOC Entry", 1)
    toc_entry.base_style = styles["Normal"]
    toc_entry.font.name = BODY_FONT
    toc_entry.font.size = Pt(10.5)
    toc_entry.font.color.rgb = RGBColor.from_string(MIDNIGHT)
    toc_entry.paragraph_format.space_after = Pt(0)


def configure_header_footer(doc):
    section = doc.sections[0]
    section.header.is_linked_to_previous = False
    header = section.header
    hp = header.paragraphs[0]
    hp.clear()
    hp.alignment = WD_ALIGN_PARAGRAPH.LEFT
    hp.paragraph_format.space_after = Pt(0)
    hr = hp.add_run(PUBLIC_HEADER)
    set_run_font(hr, size=8, bold=True, color=MUTED)
    set_paragraph_border(hp, color=TEAL, size=8, space=4)

    section.footer.is_linked_to_previous = False
    footer = section.footer
    fp = footer.paragraphs[0]
    fp.clear()
    fp.paragraph_format.space_before = Pt(0)
    fp.paragraph_format.space_after = Pt(0)
    add_page_number_footer(fp)


def build_packet(data: dict) -> Document:
    doc = Document()
    section = doc.sections[0]
    section.start_type = WD_SECTION.NEW_PAGE
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1.25)
    section.right_margin = Inches(1.25)
    section.header_distance = Inches(0.3)
    section.footer_distance = Inches(0.35)

    configure_styles(doc)
    configure_header_footer(doc)

    now = datetime(2026, 6, 5, 12, 0, tzinfo=timezone.utc)
    props = doc.core_properties
    props.title = PUBLIC_TITLE
    props.subject = PUBLIC_SUBJECT
    props.author = PUBLIC_AUTHOR
    props.last_modified_by = PUBLIC_AUTHOR
    props.keywords = PUBLIC_KEYWORDS
    props.comments = PUBLIC_COMMENTS
    props.category = "Public Release"
    props.created = now
    props.modified = now
    props.revision = 1

    settings = doc.settings.element
    update_fields = settings.find(qn("w:updateFields"))
    if update_fields is None:
        update_fields = OxmlElement("w:updateFields")
        settings.append(update_fields)
    update_fields.set(qn("w:val"), "true")

    # Cover page.
    kicker = doc.add_paragraph()
    kicker.paragraph_format.space_before = Pt(28)
    kicker.paragraph_format.space_after = Pt(18)
    kicker.alignment = WD_ALIGN_PARAGRAPH.LEFT
    kicker_run = kicker.add_run("PUBLIC RELEASE")
    set_run_font(kicker_run, size=8, bold=True, color=WHITE)
    set_paragraph_shading(kicker, TEAL)

    title = doc.add_paragraph(style="Title")
    title.paragraph_format.space_before = Pt(36)
    title.paragraph_format.space_after = Pt(4)
    title_run = title.add_run(PUBLIC_TITLE)
    set_run_font(title_run, size=21, bold=True, color=NAVY)

    rule = doc.add_paragraph()
    rule.paragraph_format.space_before = Pt(2)
    rule.paragraph_format.space_after = Pt(16)
    set_paragraph_border(rule, color=TEAL, size=16, space=3)

    subtitle = doc.add_paragraph()
    subtitle.paragraph_format.space_after = Pt(32)
    subtitle_run = subtitle.add_run("Release-safe operational record")
    set_run_font(subtitle_run, size=14, italic=True, color=SLATE)

    cover_table = doc.add_table(rows=3, cols=2)
    cover_table.alignment = WD_TABLE_ALIGNMENT.LEFT
    set_table_fixed_layout(cover_table, [1.35, 4.55])
    cover_items = [
        ("Release date", RELEASE_DATE),
        ("Distribution", "Public"),
        ("Publication state", "Approved for release"),
    ]
    for row_index, (label, value) in enumerate(cover_items):
        prevent_row_split(cover_table.rows[row_index])
        for col_index, text in enumerate((label, value)):
            cell = cover_table.rows[row_index].cells[col_index]
            p = cell.paragraphs[0]
            for run in list(p.runs):
                run._element.getparent().remove(run._element)
            p.paragraph_format.space_before = Pt(5)
            p.paragraph_format.space_after = Pt(5)
            run = p.add_run(text)
            set_run_font(run, size=9, bold=(col_index == 0),
                         color=MUTED if col_index == 0 else MIDNIGHT)
            set_cell_margins(cell, top=70, bottom=70, start=90, end=90)
            set_cell_shading(cell, PALE_BLUE if row_index % 2 == 0 else WHITE)

    cover_note = doc.add_paragraph()
    cover_note.paragraph_format.space_before = Pt(32)
    cover_note.paragraph_format.space_after = Pt(0)
    cover_note_run = cover_note.add_run(
        "Prepared by Security Operations for public distribution.")
    set_run_font(cover_note_run, size=9, color=MUTED)

    # Table of contents page.
    toc_title = doc.add_paragraph()
    toc_title.paragraph_format.page_break_before = True
    toc_title.paragraph_format.space_before = Pt(12)
    toc_title.paragraph_format.space_after = Pt(6)
    run = toc_title.add_run("Contents")
    set_run_font(run, size=22, bold=True, color=NAVY)
    set_paragraph_border(toc_title, color=TEAL, size=12, space=5)

    toc_intro = doc.add_paragraph()
    toc_intro.paragraph_format.space_after = Pt(18)
    run = toc_intro.add_run("Public release sections and appendices")
    set_run_font(run, size=10, color=SLATE)
    add_toc(doc)

    cases = data["cases"]
    n = len(cases)

    # Publication Summary.
    add_section_heading(doc, "Publication Summary", page_break_before=True,
                        space_before=0)
    p1 = doc.add_paragraph(FIXED_PARAGRAPHS[0])
    p1.paragraph_format.space_after = Pt(7)
    p2 = doc.add_paragraph(FIXED_PARAGRAPHS[1])
    p2.paragraph_format.space_after = Pt(8)
    p3 = doc.add_paragraph(
        f"This edition covers {n} incident cases and records their public "
        "response timeline, customer communication, control exceptions, action "
        "register, evidence index, and approval decisions.")
    p3.paragraph_format.space_after = Pt(16)

    # Response Timeline.
    add_section_heading(doc, "Response Timeline")
    add_intro(doc, "The public chronology records the major milestones from "
                   "alerting through service restoration.")
    add_table_caption(doc, "Public response chronology")
    add_public_table(
        doc,
        TIMELINE_HEADER,
        [[c["timeline_time"], c["milestone"], c["summary"]] for c in cases],
        [1.25, 1.5, 3.25],
    )

    # Customer Communication.
    add_section_heading(doc, "Customer Communication")
    add_intro(doc, "Required customer and support messages are assigned to "
                   "named owners and tracked to readiness.")
    add_table_caption(doc, "Message readiness")
    add_public_table(
        doc,
        COMMUNICATION_HEADER,
        [[c["audience"], c["message_owner"], c["message_update"], "Ready"]
         for c in cases],
        [1.0, 1.25, 2.65, 1.1],
    )

    # Control Exceptions.
    add_section_heading(doc, "Control Exceptions", page_break_before=True,
                        space_before=0)
    add_intro(doc, "Exceptions are shown with their release status and the "
                   "owner accountable for closure.")
    open_exception = doc.add_paragraph()
    open_exception.paragraph_format.space_before = Pt(4)
    open_exception.paragraph_format.space_after = Pt(7)
    open_exception.paragraph_format.keep_with_next = True
    open_run = open_exception.add_run(FIXED_PARAGRAPHS[2])
    set_run_font(open_run, size=10.5, bold=True, color=MIDNIGHT)
    open_run.font.highlight_color = WD_COLOR_INDEX.YELLOW
    closed_exception = doc.add_paragraph()
    closed_exception.paragraph_format.space_after = Pt(16)
    closed_run = closed_exception.add_run(FIXED_PARAGRAPHS[3])
    set_run_font(closed_run, size=10.5, color=MIDNIGHT)
    add_table_caption(doc, "Exception status")
    add_public_table(
        doc,
        EXCEPTION_HEADER,
        [[c["exception_id"], c["control"], c["exception_owner"],
          c["release_status"]] for c in cases],
        [1.05, 1.45, 1.25, 2.25],
    )

    # Action Register.
    add_section_heading(doc, "Action Register", page_break_before=True,
                        space_before=0)
    add_intro(doc, "The action register tracks public-release follow-up for "
                   "the open evidence exception and customer messaging.")
    add_table_caption(doc, "Required ownership and follow-up")
    add_public_table(
        doc,
        ACTION_HEADER,
        [[c["action_id"], c["action_owner"], c["due_date"],
          c["publish_status"]] for c in cases],
        [1.0, 1.45, 1.25, 2.3],
    )

    # Appendix A.
    add_section_heading(doc, "Appendix A - Evidence Index", page_break_before=True,
                        space_before=0)
    add_intro(doc, "Evidence is identified by a public label and a release "
                   "disposition.")
    add_table_caption(doc, "Release evidence")
    add_public_table(
        doc,
        EVIDENCE_HEADER,
        [[c["evidence_id"], c["public_label"], c["disposition"]] for c in cases],
        [1.15, 3.2, 1.65],
    )

    # Appendix B.
    add_section_heading(doc, "Appendix B - Approval Record", page_break_before=True,
                        space_before=0)
    add_intro(doc, "This final record captures public-release decisions from "
                   "the incident lead and legal.")
    add_table_caption(doc, "Final approval decisions")
    add_public_table(
        doc,
        APPROVAL_HEADER,
        [[c["approver"], c["role"], c["decision"]] for c in cases],
        [1.3, 1.65, 3.05],
    )

    final_note = doc.add_paragraph()
    final_note.paragraph_format.space_before = Pt(8)
    final_note.paragraph_format.space_after = Pt(0)
    final_run = final_note.add_run("Publication status: Approved. Distribution: Public.")
    set_run_font(final_run, size=9, bold=True, color=TEAL)
    return doc


def deterministic_zip(src: Path, dst: Path) -> None:
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w",
                                                      zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            item.date_time = (1980, 1, 1, 0, 0, 0)
            item.extra = b""
            item.comment = b""
            item.compress_type = zipfile.ZIP_DEFLATED
            item.external_attr = 0o600 << 16
            zout.writestr(item, data)


def verify_draft_source(source: Path) -> None:
    doc = Document(str(source))
    text = "\n".join(p.text for p in doc.paragraphs)
    if "Draft:" not in text:
        raise RuntimeError(f"source {source} does not carry the Draft: marker")


def build(source: Path, cases_path: Path, output: Path):
    data = json.loads(Path(cases_path).read_text(encoding="utf-8"))
    verify_draft_source(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    doc = build_packet(data)
    raw = output.parent / f".raw-{output.name}"
    doc.save(str(raw))
    deterministic_zip(raw, output)
    raw.unlink(missing_ok=True)
    return len(data["cases"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases",
                        default=os.environ.get("VARIANT_CASES", "/root/tmp/docs/cases.json"),
                        help="frozen cases.json prepared material")
    parser.add_argument("--input", default=os.environ.get("VARIANT_INPUT"),
                        help="source DOCX path (default: /root input for this variant)")
    parser.add_argument("--output", default=os.environ.get("VARIANT_OUTPUT"),
                        help="output DOCX path")
    args = parser.parse_args(argv)
    if not args.output:
        parser.error("--output is required (or set VARIANT_OUTPUT)")
    cases_path = Path(args.cases)
    if not cases_path.is_file():
        parser.error(f"cases material missing: {cases_path}")
    source = Path(args.input) if args.input else None
    if source is None:
        candidates = sorted(
            Path("/root").glob(
                "docops_v2_l3_009_docx_incident_manual_publication_input_*.docx"))
        if not candidates:
            parser.error("cannot locate the synthetic input DOCX under /root; pass --input")
        source = candidates[0]
    count = build(source, cases_path, Path(args.output))
    print(args.output)
    print(f"Cases: {count}")


if __name__ == "__main__":
    main()
