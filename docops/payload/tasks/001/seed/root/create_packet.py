from datetime import datetime, timezone
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_ROW_HEIGHT_RULE
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


OUTPUT = Path("/root/submission/docops_v2_l3_001_docx_controlled_document_release_repair_output.docx")

TEAL = RGBColor(0x0F, 0x4C, 0x5C)
TEAL_HEX = "0F4C5C"
TEAL_DARK_HEX = "0A3641"
TEAL_LIGHT_HEX = "EAF2F4"
TEAL_PALE_HEX = "F5F9FA"
SLATE_HEX = "334E57"
MUTED_HEX = "61757C"
WHITE_HEX = "FFFFFF"
RULE_HEX = "B7CDD3"
GOLD_HEX = "D9A441"
BODY_FONT = "Aptos"
DISPLAY_FONT = "Aptos Display"


def set_run_font(run, name=BODY_FONT, size=10.5, bold=None, color=None, italic=None):
    run.font.name = name
    run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), name)
    run._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), name)
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), name)
    run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    if color is not None:
        run.font.color.rgb = color


def set_style_font(style, name=BODY_FONT, size=10.5, bold=None, color=None):
    style.font.name = name
    style._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), name)
    style._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), name)
    style._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), name)
    style.font.size = Pt(size)
    if bold is not None:
        style.font.bold = bold
    if color is not None:
        style.font.color.rgb = color


def shade_cell(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def shade_paragraph(paragraph, fill):
    p_pr = paragraph._p.get_or_add_pPr()
    shd = p_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        p_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top=55, start=110, bottom=55, end=110):
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for margin, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{margin}"))
        if node is None:
            node = OxmlElement(f"w:{margin}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_cell_border(cell, **edges):
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_borders = tc_pr.first_child_found_in("w:tcBorders")
    if tc_borders is None:
        tc_borders = OxmlElement("w:tcBorders")
        tc_pr.append(tc_borders)
    for edge_name, attrs in edges.items():
        edge = tc_borders.find(qn(f"w:{edge_name}"))
        if edge is None:
            edge = OxmlElement(f"w:{edge_name}")
            tc_borders.append(edge)
        for key, value in attrs.items():
            edge.set(qn(f"w:{key}"), str(value))


def set_repeat_table_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def prevent_row_split(row):
    tr_pr = row._tr.get_or_add_trPr()
    cant_split = OxmlElement("w:cantSplit")
    tr_pr.append(cant_split)


def set_paragraph_border(paragraph, edge="bottom", color=TEAL_HEX, size=8, space=4):
    p_pr = paragraph._p.get_or_add_pPr()
    p_bdr = p_pr.find(qn("w:pBdr"))
    if p_bdr is None:
        p_bdr = OxmlElement("w:pBdr")
        p_pr.append(p_bdr)
    border = p_bdr.find(qn(f"w:{edge}"))
    if border is None:
        border = OxmlElement(f"w:{edge}")
        p_bdr.append(border)
    border.set(qn("w:val"), "single")
    border.set(qn("w:sz"), str(size))
    border.set(qn("w:space"), str(space))
    border.set(qn("w:color"), color)


def set_table_borders(table, color=RULE_HEX, size=4):
    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.first_child_found_in("w:tblBorders")
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tbl_pr.append(borders)
    for edge_name in ("top", "left", "bottom", "right", "insideH", "insideV"):
        edge = borders.find(qn(f"w:{edge_name}"))
        if edge is None:
            edge = OxmlElement(f"w:{edge_name}")
            borders.append(edge)
        edge.set(qn("w:val"), "single")
        edge.set(qn("w:sz"), str(size))
        edge.set(qn("w:space"), "0")
        edge.set(qn("w:color"), color)


def add_page_field(paragraph, instruction):
    run = paragraph.add_run()
    fld_char_begin = OxmlElement("w:fldChar")
    fld_char_begin.set(qn("w:fldCharType"), "begin")
    instr_text = OxmlElement("w:instrText")
    instr_text.set(qn("xml:space"), "preserve")
    instr_text.text = instruction
    fld_char_end = OxmlElement("w:fldChar")
    fld_char_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_char_begin)
    run._r.append(instr_text)
    run._r.append(fld_char_end)
    set_run_font(run, BODY_FONT, 8.2, color=RGBColor(0x61, 0x75, 0x7C))


def add_heading(doc, text, page_break_before=False):
    p = doc.add_paragraph(style="Heading 1")
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.page_break_before = page_break_before
    run = p.add_run(text)
    set_run_font(run, DISPLAY_FONT, 14.5, bold=True, color=TEAL)
    return p


def add_body(doc, text, after=5, before=0, bold_prefix=None, color=None):
    p = doc.add_paragraph(style="Normal")
    p.paragraph_format.space_before = Pt(before)
    p.paragraph_format.space_after = Pt(after)
    if bold_prefix and text.startswith(bold_prefix):
        prefix = p.add_run(bold_prefix)
        set_run_font(prefix, BODY_FONT, 10.5, bold=True, color=TEAL)
        rest = p.add_run(text[len(bold_prefix):])
        set_run_font(rest, BODY_FONT, 10.5, color=color or RGBColor(0x33, 0x4E, 0x57))
    else:
        run = p.add_run(text)
        set_run_font(run, BODY_FONT, 10.5, color=color or RGBColor(0x33, 0x4E, 0x57))
    return p


def add_label(doc, text):
    p = doc.add_paragraph(style="Document Label")
    run = p.add_run(text.upper())
    set_run_font(run, BODY_FONT, 8.5, bold=True, color=TEAL)
    return p


def add_callout(doc, text, dark=False):
    p = doc.add_paragraph(style="Callout")
    shade_paragraph(p, TEAL_HEX if dark else TEAL_LIGHT_HEX)
    set_paragraph_border(p, "left", GOLD_HEX if not dark else "D9A441", size=18, space=8)
    p.paragraph_format.space_before = Pt(7)
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.left_indent = Inches(0.12)
    p.paragraph_format.right_indent = Inches(0.08)
    run = p.add_run(text)
    set_run_font(
        run,
        BODY_FONT,
        10.2,
        bold=True,
        color=RGBColor(0xFF, 0xFF, 0xFF) if dark else TEAL,
    )
    return p


def add_table(doc, rows, widths):
    table = doc.add_table(rows=len(rows), cols=len(rows[0]))
    table.alignment = 1
    table.autofit = False
    table.allow_autofit = False
    set_table_borders(table)
    tbl_pr = table._tbl.tblPr
    tbl_layout = tbl_pr.first_child_found_in("w:tblLayout")
    if tbl_layout is None:
        tbl_layout = OxmlElement("w:tblLayout")
        tbl_pr.append(tbl_layout)
    tbl_layout.set(qn("w:type"), "fixed")
    tbl_width = tbl_pr.first_child_found_in("w:tblW")
    if tbl_width is None:
        tbl_width = OxmlElement("w:tblW")
        tbl_pr.append(tbl_width)
    tbl_width.set(qn("w:type"), "dxa")
    tbl_width.set(qn("w:w"), str(sum(round(width * 1440) for width in widths)))
    for col_idx, width in enumerate(widths):
        table.columns[col_idx].width = Inches(width)
    for row_idx, values in enumerate(rows):
        row = table.rows[row_idx]
        row.height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST
        row.height = Inches(0.29 if row_idx else 0.34)
        prevent_row_split(row)
        if row_idx == 0:
            set_repeat_table_header(row)
        for col_idx, value in enumerate(values):
            cell = row.cells[col_idx]
            cell.width = Inches(widths[col_idx])
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_margins(cell)
            shade_cell(cell, TEAL_HEX if row_idx == 0 else (TEAL_PALE_HEX if row_idx % 2 == 0 else WHITE_HEX))
            set_cell_border(
                cell,
                bottom={"val": "single", "sz": 4, "color": RULE_HEX},
                top={"val": "nil"},
                left={"val": "nil"},
                right={"val": "nil"},
            )
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.0
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            run = p.add_run(value)
            set_run_font(
                run,
                BODY_FONT,
                9.2 if row_idx else 9.0,
                bold=row_idx == 0 or (col_idx == 0 and len(rows[0]) >= 3),
                color=RGBColor(0xFF, 0xFF, 0xFF) if row_idx == 0 else RGBColor(0x33, 0x4E, 0x57),
            )
    return table


doc = Document()

# Keep one portrait section with the controlled release margins.
section = doc.sections[0]
section.top_margin = Inches(0.8)
section.bottom_margin = Inches(0.8)
section.left_margin = Inches(0.8)
section.right_margin = Inches(0.8)
section.header_distance = Inches(0.35)
section.footer_distance = Inches(0.35)

# Global typography.
normal = doc.styles["Normal"]
set_style_font(normal, BODY_FONT, 10.5, color=RGBColor(0x33, 0x4E, 0x57))
normal.paragraph_format.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
normal.paragraph_format.line_spacing = 1.08
normal.paragraph_format.space_after = Pt(4)
normal.paragraph_format.widow_control = True

title_style = doc.styles["Title"]
set_style_font(title_style, DISPLAY_FONT, 18, bold=True, color=TEAL)
title_style.paragraph_format.space_before = Pt(0)
title_style.paragraph_format.space_after = Pt(6)
title_style.paragraph_format.keep_with_next = True

heading_style = doc.styles["Heading 1"]
set_style_font(heading_style, DISPLAY_FONT, 14.5, bold=True, color=TEAL)
heading_style.paragraph_format.space_before = Pt(13)
heading_style.paragraph_format.space_after = Pt(6)
heading_style.paragraph_format.keep_with_next = True
heading_style.paragraph_format.keep_together = True

label_style = doc.styles.add_style("Document Label", 1)
set_style_font(label_style, BODY_FONT, 8.5, bold=True, color=TEAL)
label_style.paragraph_format.space_before = Pt(0)
label_style.paragraph_format.space_after = Pt(3)
label_style.paragraph_format.keep_with_next = True

callout_style = doc.styles.add_style("Callout", 1)
set_style_font(callout_style, BODY_FONT, 10.2, bold=True, color=TEAL)
callout_style.paragraph_format.space_after = Pt(8)

# Header.
header = section.header
header.is_linked_to_previous = False
hp = header.paragraphs[0]
hp.paragraph_format.space_after = Pt(2)
hp.paragraph_format.tab_stops.add_tab_stop(Inches(6.9), alignment=2)
set_paragraph_border(hp, "bottom", TEAL_HEX, size=8, space=3)
run = hp.add_run("QUALITY MANAGEMENT SYSTEM")
set_run_font(run, BODY_FONT, 8.2, bold=True, color=TEAL)
run = hp.add_run("\tCONTROLLED RELEASE RECORD")
set_run_font(run, BODY_FONT, 8.2, bold=True, color=RGBColor(0x61, 0x75, 0x7C))

# Footer.
footer = section.footer
footer.is_linked_to_previous = False
fp = footer.paragraphs[0]
fp.paragraph_format.space_before = Pt(2)
fp.paragraph_format.space_after = Pt(0)
fp.paragraph_format.tab_stops.add_tab_stop(Inches(6.9), alignment=2)
set_paragraph_border(fp, "top", RULE_HEX, size=4, space=4)
run = fp.add_run("QMS-PR-007 | Version 4.2")
set_run_font(run, BODY_FONT, 8.2, bold=True, color=TEAL)
run = fp.add_run("\tControlled Document Release Repair Packet | 2026  |  Page ")
set_run_font(run, BODY_FONT, 8.2, color=RGBColor(0x61, 0x75, 0x7C))
add_page_field(fp, "PAGE")

# Page 1: release packet and correction register.
title = doc.add_paragraph(style="Title")
title.paragraph_format.keep_with_next = True
set_paragraph_border(title, "bottom", GOLD_HEX, size=14, space=7)
run = title.add_run("Controlled Document Release Repair Packet")
set_run_font(run, DISPLAY_FONT, 18, bold=True, color=TEAL)

meta_line = doc.add_paragraph(style="Normal")
meta_line.paragraph_format.space_after = Pt(9)
run = meta_line.add_run("QMS-PR-007  /  VERSION 4.2  /  EFFECTIVE 2026-08-01")
set_run_font(run, BODY_FONT, 8.8, bold=True, color=RGBColor(0x61, 0x75, 0x7C))

add_body(
    doc,
    "This repaired packet applies the correction register across the controlled document release record.",
    after=7,
)
add_callout(doc, "QMS-PR-007 version 4.2 is ready for controlled release.", dark=True)

add_heading(doc, "Correction Register Applied")
correction_rows = [
    ["Issue", "Correct Public Value", "Applied To"],
    ["Document ID", "QMS-PR-007", "Metadata and footer"],
    ["Version", "4.2", "Revision history"],
    ["Effective date", "2026-08-01", "Metadata"],
    ["Owner", "Quality Systems Office", "Metadata"],
    ["Approver", "Compliance Director", "Approval record"],
    ["Training due", "2026-08-15", "Workflow"],
    ["Retention period", "6 years", "Checklist"],
]
add_table(doc, correction_rows, [1.45, 2.35, 3.0])
add_body(
    doc,
    "The obsolete copy retirement date is 2026-08-05. Corrected values replace prior release-record entries wherever they appear.",
    before=6,
    after=5,
)

add_heading(doc, "Controlled Document Metadata")
metadata_rows = [
    ["Field", "Correct Public Value", "Status"],
    ["Document ID", "QMS-PR-007", "Corrected"],
    ["Version", "4.2", "Corrected"],
    ["Effective date", "2026-08-01", "Corrected"],
    ["Owner", "Quality Systems Office", "Corrected"],
    ["Approver", "Compliance Director", "Corrected"],
]
add_table(doc, metadata_rows, [1.55, 3.45, 1.8])
add_body(
    doc,
    "The effective date is 2026-08-01 and training is due by 2026-08-15.",
    before=7,
    after=4,
)
add_body(
    doc,
    "Quality Systems Office owns the document and Compliance Director approves the release.",
    after=5,
)

add_heading(doc, "Revision History")
revision_rows = [
    ["Version", "Date", "Public Change Summary"],
    ["4.0", "2025-04-15", "Baseline controlled release"],
    ["4.1", "2026-02-10", "Minor distribution update"],
    ["4.2", "2026-08-01", "Corrected approval workflow and obsolete copy controls"],
]
add_table(doc, revision_rows, [0.85, 1.35, 4.7])

# Page 2: implementation workflow.
add_heading(doc, "Distribution and Training Workflow", page_break_before=True)
add_body(
    doc,
    "The workflow establishes a single implementation path from release publication through evidence retention. Each step produces a record that can be verified against the controlled release file.",
    after=7,
)
workflow_rows = [
    ["Step", "Owner", "Due Date", "Output"],
    ["Publish controlled copy", "Quality Systems Office", "2026-08-01", "Released controlled document"],
    ["Notify document users", "Quality Systems Office", "2026-08-03", "Distribution notice"],
    ["Complete training", "Department Leads", "2026-08-15", "Training completion record"],
    ["Archive release evidence", "Records Coordinator", "2026-08-20", "Release evidence packet"],
]
add_table(doc, workflow_rows, [1.85, 1.75, 0.95, 2.35])
add_callout(
    doc,
    "Distribution control: users acknowledge the released version, and department leads return completion evidence by the training due date.",
)

# Page 2/3: obsolete copy retirement.
add_heading(doc, "Obsolete Copy Retirement Checklist")
add_body(
    doc,
    "Removal of prior copies is verified before the release record is closed. Retired copies remain within the approved retention controls and are not available for active use.",
    after=7,
)
retirement_rows = [
    ["Control", "Required Result", "Status"],
    ["Obsolete copy retirement", "Complete by 2026-08-05", "Ready"],
    ["Retention period", "6 years", "Ready"],
    ["Approval record", "Compliance Director approval retained", "Ready"],
    ["Distribution list", "Current users notified", "Ready"],
]
add_table(doc, retirement_rows, [2.15, 3.35, 1.3])
add_body(
    doc,
    "All release metadata, revision history, training, and obsolete copy steps have been reconciled.",
    before=8,
    after=5,
)

# Final page: release appendix.
add_heading(doc, "Final Release Appendix", page_break_before=True)
add_label(doc, "Release Verification Summary")
add_body(
    doc,
    "The repair packet consolidates the approved document identity, implementation workflow, and retirement controls into one traceable release record.",
    after=8,
)

verification_items = [
    ("01", "All spelling repairs are complete."),
    ("02", "All incorrect version and date values have been removed."),
    ("03", "All release metadata, revision history, training, and obsolete copy steps have been reconciled."),
]
for number, text in verification_items:
    p = doc.add_paragraph(style="Normal")
    p.paragraph_format.left_indent = Inches(0.0)
    p.paragraph_format.first_line_indent = Inches(-0.0)
    p.paragraph_format.space_after = Pt(7)
    p.paragraph_format.keep_together = True
    run = p.add_run(f"{number}   ")
    set_run_font(run, DISPLAY_FONT, 11, bold=True, color=TEAL)
    run = p.add_run(text)
    set_run_font(run, BODY_FONT, 10.5, bold=False, color=RGBColor(0x33, 0x4E, 0x57))

add_label(doc, "Release Authorization")
auth_values = [
    ("Document ID", "QMS-PR-007"),
    ("Document owner", "Quality Systems Office"),
    ("Approver", "Compliance Director"),
    ("Release version", "4.2"),
    ("Effective date", "2026-08-01"),
    ("Training due", "2026-08-15"),
    ("Retention period", "6 years"),
    ("Obsolete copy retirement", "2026-08-05"),
]
for key, value in auth_values:
    p = doc.add_paragraph(style="Normal")
    p.paragraph_format.space_after = Pt(2.5)
    p.paragraph_format.keep_together = True
    run = p.add_run(f"{key}: ")
    set_run_font(run, BODY_FONT, 9.6, bold=True, color=TEAL)
    run = p.add_run(value)
    set_run_font(run, BODY_FONT, 9.6, color=RGBColor(0x33, 0x4E, 0x57))

add_callout(doc, "Final review status: ready for controlled document release.", dark=True)

closing = doc.add_paragraph(style="Normal")
closing.paragraph_format.space_before = Pt(8)
closing.paragraph_format.space_after = Pt(0)
closing.alignment = WD_ALIGN_PARAGRAPH.LEFT
set_paragraph_border(closing, "top", RULE_HEX, size=4, space=8)
run = closing.add_run("RELEASE RECORD  /  QUALITY SYSTEMS OFFICE  /  2026")
set_run_font(run, BODY_FONT, 8.2, bold=True, color=RGBColor(0x61, 0x75, 0x7C))

# Core document properties.
props = doc.core_properties
props.author = "Quality Systems Office"
props.last_modified_by = "Quality Systems Office"
props.title = "Controlled Document Release Repair Packet"
props.subject = "Controlled document release repair packet for QMS-PR-007 version 4.2"
props.keywords = "QMS-PR-007; version 4.2; controlled release; correction register"
props.category = "Quality Management System"
props.comments = "Controlled release record prepared by Quality Systems Office."
props.created = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)
props.modified = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)
props.revision = 2

# Update Word fields on open and retain the controlled print layout.
settings = doc.settings._element
update_fields = settings.find(qn("w:updateFields"))
if update_fields is None:
    update_fields = OxmlElement("w:updateFields")
    settings.append(update_fields)
update_fields.set(qn("w:val"), "true")

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
doc.save(OUTPUT)
print(f"Saved {OUTPUT} ({OUTPUT.stat().st_size} bytes)")
