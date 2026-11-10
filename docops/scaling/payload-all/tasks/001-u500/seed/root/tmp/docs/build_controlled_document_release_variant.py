#!/usr/bin/env python3
"""Parameterized builder for synthetic scaled Word 001 variants.

Mirrors the frozen parent 001 workflow (create_packet.py stage order): remove
draft material, apply the correction register, rebuild the controlled document
release packet with metadata, revision history, distribution/training workflow,
obsolete-copy retirement checklist and final release appendix.

The only parameterized parts are:

- the register content: every declared controlled document record from the
  frozen records.json gets one real row in the Controlled Document Register
  table, so the register row count is driven by the actual record count;
- the fixed chapter tables and release facts stay byte-equivalent to the
  frozen parent public values.

No random business data is generated during the build: records.json is frozen
at prepare time and read verbatim. The synthetic DRAFT source is only verified
(its internal errors are never carried into the output).
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

# Frozen public facts (identical to parent task 001).
PUBLIC_TITLE = "Controlled Document Release Repair Packet"
PUBLIC_SUBJECT = (
    "Controlled document release repair packet for QMS-PR-007 version 4.2"
)
PUBLIC_AUTHOR = "Quality Systems Office"
PUBLIC_KEYWORDS = "QMS-PR-007; version 4.2; controlled release; correction register"
PUBLIC_COMMENTS = "Controlled release record prepared by Quality Systems Office."
PUBLIC_FOOTER = "Controlled Document Release Repair Packet | 2026"
PUBLIC_CATEGORY = "Quality Management System"
DOC_ID = "QMS-PR-007"
VERSION = "4.2"
EFFECTIVE_DATE = "2026-08-01"
OWNER = "Quality Systems Office"
APPROVER = "Compliance Director"
TRAINING_DUE = "2026-08-15"
RETENTION = "6 years"
RETIREMENT = "2026-08-05"

TEAL = "0F4C5C"
TEAL_DARK = "0A3641"
TEAL_PALE = "EAF2F4"
SLATE = "334E57"
MUTED = "61757C"
WHITE = "FFFFFF"
RULE = "B7CDD3"
GOLD = "D9A441"
BODY_FONT = "Aptos"
DISPLAY_FONT = "Aptos Display"

CORRECTION_ROWS = [
    ["Issue", "Correct Public Value", "Applied To"],
    ["Document ID", DOC_ID, "Metadata and footer"],
    ["Version", VERSION, "Revision history"],
    ["Effective date", EFFECTIVE_DATE, "Metadata"],
    ["Owner", OWNER, "Metadata"],
    ["Approver", APPROVER, "Approval record"],
    ["Training due", TRAINING_DUE, "Workflow"],
    ["Retention period", RETENTION, "Checklist"],
]
METADATA_ROWS = [
    ["Field", "Correct Public Value", "Status"],
    ["Document ID", DOC_ID, "Corrected"],
    ["Version", VERSION, "Corrected"],
    ["Effective date", EFFECTIVE_DATE, "Corrected"],
    ["Owner", OWNER, "Corrected"],
    ["Approver", APPROVER, "Corrected"],
]
REVISION_ROWS = [
    ["Version", "Date", "Public Change Summary"],
    ["4.0", "2025-04-15", "Baseline controlled release"],
    ["4.1", "2026-02-10", "Minor distribution update"],
    ["4.2", "2026-08-01", "Corrected approval workflow and obsolete copy controls"],
]
WORKFLOW_ROWS = [
    ["Step", "Owner", "Due Date", "Output"],
    ["Publish controlled copy", "Quality Systems Office", "2026-08-01",
     "Released controlled document"],
    ["Notify document users", "Quality Systems Office", "2026-08-03",
     "Distribution notice"],
    ["Complete training", "Department Leads", "2026-08-15", "Training completion record"],
    ["Archive release evidence", "Records Coordinator", "2026-08-20",
     "Release evidence packet"],
]
RETIREMENT_ROWS = [
    ["Control", "Required Result", "Status"],
    ["Obsolete copy retirement", "Complete by 2026-08-05", "Ready"],
    ["Retention period", "6 years", "Ready"],
    ["Approval record", "Compliance Director approval retained", "Ready"],
    ["Distribution list", "Current users notified", "Ready"],
]
AUTH_VALUES = [
    ("Document ID", DOC_ID),
    ("Document owner", OWNER),
    ("Approver", APPROVER),
    ("Release version", VERSION),
    ("Effective date", EFFECTIVE_DATE),
    ("Training due", TRAINING_DUE),
    ("Retention period", RETENTION),
    ("Obsolete copy retirement", RETIREMENT),
]
VERIFICATION_ITEMS = [
    ("01", "All spelling repairs are complete."),
    ("02", "All incorrect version and date values have been removed."),
    ("03", "All release metadata, revision history, training, and obsolete copy "
          "steps have been reconciled."),
]
REGISTER_HEADER = [
    "Record ID", "Document Name", "Version", "Effective Date",
    "Owner", "Training Due", "Retention", "Status",
]
REGISTER_WIDTHS = [0.95, 1.75, 0.55, 0.95, 1.05, 0.95, 0.55, 0.15]


def set_run_font(run, name=BODY_FONT, size=10.5, bold=None, color=None):
    run.font.name = name
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    for key in ("ascii", "hAnsi", "cs", "eastAsia"):
        rfonts.set(qn(f"w:{key}"), name)
    run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if color is not None:
        run.font.color.rgb = RGBColor.from_string(color)


def set_style_font(style, name=BODY_FONT, size=10.5, bold=None, color=None):
    style.font.name = name
    style._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), name)
    style._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), name)
    style._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), name)
    style.font.size = Pt(size)
    if bold is not None:
        style.font.bold = bold
    if color is not None:
        style.font.color.rgb = RGBColor.from_string(color)


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


def set_cell_margins(cell, top=50, start=105, bottom=50, end=105):
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for margin, value in (("top", top), ("start", start), ("bottom", bottom),
                          ("end", end)):
        node = tc_mar.find(qn(f"w:{margin}"))
        if node is None:
            node = OxmlElement(f"w:{margin}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_paragraph_border(paragraph, edge="bottom", color=TEAL, size=8, space=4):
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


def set_table_borders(table, color=RULE, size=4):
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


def set_repeat_table_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def prevent_row_split(row):
    tr_pr = row._tr.get_or_add_trPr()
    cant_split = OxmlElement("w:cantSplit")
    tr_pr.append(cant_split)


def add_page_field(paragraph, instruction):
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = instruction
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.append(begin)
    run._r.append(instr)
    run._r.append(end)
    set_run_font(run, BODY_FONT, 8.2, color=MUTED)


def add_heading(doc, text, page_break_before=False):
    p = doc.add_paragraph(style="Heading 1")
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.page_break_before = page_break_before
    run = p.add_run(text)
    set_run_font(run, DISPLAY_FONT, 14.5, bold=True, color=TEAL)
    return p


def add_body(doc, text, after=5, before=0):
    p = doc.add_paragraph(style="Normal")
    p.paragraph_format.space_before = Pt(before)
    p.paragraph_format.space_after = Pt(after)
    run = p.add_run(text)
    set_run_font(run, BODY_FONT, 10.5, color=SLATE)
    return p


def add_label(doc, text):
    p = doc.add_paragraph(style="Document Label")
    run = p.add_run(text.upper())
    set_run_font(run, BODY_FONT, 8.5, bold=True, color=TEAL)
    return p


def add_callout(doc, text, dark=False):
    p = doc.add_paragraph(style="Callout")
    shade_paragraph(p, TEAL if dark else TEAL_PALE)
    set_paragraph_border(p, "left", GOLD, size=18, space=8)
    run = p.add_run(text)
    set_run_font(run, BODY_FONT, 10.2, bold=True,
                 color=WHITE if dark else TEAL)
    return p


def add_table(doc, rows, widths):
    table = doc.add_table(rows=len(rows), cols=len(rows[0]))
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    table.autofit = False
    table.allow_autofit = False
    set_table_borders(table)
    for col_idx, width in enumerate(widths):
        table.columns[col_idx].width = Inches(width)
    for row_idx, values in enumerate(rows):
        row = table.rows[row_idx]
        prevent_row_split(row)
        if row_idx == 0:
            set_repeat_table_header(row)
        for col_idx, value in enumerate(values):
            cell = row.cells[col_idx]
            cell.width = Inches(widths[col_idx])
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_margins(cell)
            if row_idx == 0:
                shade_cell(cell, TEAL)
            elif row_idx % 2 == 0:
                shade_cell(cell, TEAL_PALE)
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.0
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            run = p.add_run(value)
            set_run_font(run, BODY_FONT, 9.0 if row_idx else 9.2,
                         bold=row_idx == 0,
                         color=WHITE if row_idx == 0
                         else SLATE)
    return table


def configure_document(doc, section):
    section.top_margin = Inches(0.8)
    section.bottom_margin = Inches(0.8)
    section.left_margin = Inches(0.8)
    section.right_margin = Inches(0.8)
    section.header_distance = Inches(0.35)
    section.footer_distance = Inches(0.35)

    normal = doc.styles["Normal"]
    set_style_font(normal, BODY_FONT, 10.5, color=SLATE)
    normal.paragraph_format.line_spacing = 1.08
    normal.paragraph_format.space_after = Pt(4)
    normal.paragraph_format.widow_control = True

    title_style = doc.styles["Title"]
    set_style_font(title_style, DISPLAY_FONT, 18, bold=True, color=TEAL)
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


def configure_header_footer(doc, section):
    header = section.header
    header.is_linked_to_previous = False
    hp = header.paragraphs[0]
    hp.paragraph_format.space_after = Pt(2)
    hp.paragraph_format.tab_stops.add_tab_stop(Inches(6.9), alignment=2)
    set_paragraph_border(hp, "bottom", TEAL, size=8, space=3)
    run = hp.add_run("QUALITY MANAGEMENT SYSTEM")
    set_run_font(run, BODY_FONT, 8.2, bold=True, color=TEAL)
    run = hp.add_run("\tCONTROLLED RELEASE RECORD")
    set_run_font(run, BODY_FONT, 8.2, bold=True, color=MUTED)

    footer = section.footer
    footer.is_linked_to_previous = False
    fp = footer.paragraphs[0]
    fp.paragraph_format.space_before = Pt(2)
    fp.paragraph_format.space_after = Pt(0)
    fp.paragraph_format.tab_stops.add_tab_stop(Inches(6.9), alignment=2)
    set_paragraph_border(fp, "top", RULE, size=4, space=4)
    run = fp.add_run(f"{DOC_ID} | Version {VERSION}")
    set_run_font(run, BODY_FONT, 8.2, bold=True, color=TEAL)
    run = fp.add_run(f"\t{PUBLIC_FOOTER}  |  Page ")
    set_run_font(run, BODY_FONT, 8.2, color=MUTED)
    add_page_field(fp, "PAGE")


def build_register_rows(data: dict) -> list[list[str]]:
    return [
        [r["id"], r["name"], r["version"], r["effective_date"],
         r["owner"], r["training_due"], r["retention"], r["status"]]
        for r in data["records"]
    ]


def build_packet(data: dict) -> Document:
    doc = Document()
    section = doc.sections[0]
    configure_document(doc, section)
    configure_header_footer(doc, section)

    title = doc.add_paragraph(style="Title")
    title.paragraph_format.keep_with_next = True
    set_paragraph_border(title, "bottom", GOLD, size=14, space=7)
    run = title.add_run(PUBLIC_TITLE)
    set_run_font(run, DISPLAY_FONT, 18, bold=True, color=TEAL)

    meta_line = doc.add_paragraph(style="Normal")
    meta_line.paragraph_format.space_after = Pt(9)
    run = meta_line.add_run(
        f"{DOC_ID}  /  VERSION {VERSION}  /  EFFECTIVE {EFFECTIVE_DATE}")
    set_run_font(run, BODY_FONT, 8.8, bold=True, color=MUTED)

    add_body(doc,
             "This repaired packet applies the correction register across the "
             "controlled document release record.", after=7)
    add_callout(doc, f"{DOC_ID} version {VERSION} is ready for controlled release.",
                dark=True)

    add_heading(doc, "Correction Register Applied")
    add_table(doc, CORRECTION_ROWS, [1.45, 2.35, 3.0])
    add_body(doc,
             "The obsolete copy retirement date is 2026-08-05. Corrected values "
             "replace prior release-record entries wherever they appear.",
             before=6, after=5)

    add_heading(doc, "Controlled Document Metadata")
    add_table(doc, METADATA_ROWS, [1.55, 3.45, 1.8])
    add_body(doc,
             "The effective date is 2026-08-01 and training is due by 2026-08-15.",
             before=7, after=4)
    add_body(doc,
             "Quality Systems Office owns the document and Compliance Director "
             "approves the release.", after=5)

    add_heading(doc, "Revision History")
    add_table(doc, REVISION_ROWS, [0.85, 1.35, 4.7])

    add_heading(doc, "Distribution and Training Workflow", page_break_before=True)
    add_body(doc,
             "The workflow establishes a single implementation path from release "
             "publication through evidence retention. Each step produces a record "
             "that can be verified against the controlled release file.", after=7)
    add_table(doc, WORKFLOW_ROWS, [1.85, 1.75, 0.95, 2.35])
    add_callout(doc,
                "Distribution control: users acknowledge the released version, and "
                "department leads return completion evidence by the training due date.")

    add_heading(doc, "Obsolete Copy Retirement Checklist")
    add_body(doc,
             "Removal of prior copies is verified before the release record is "
             "closed. Retired copies remain within the approved retention controls "
             "and are not available for active use.", after=7)
    add_table(doc, RETIREMENT_ROWS, [2.15, 3.35, 1.3])
    add_body(doc,
             "All release metadata, revision history, training, and obsolete copy "
             "steps have been reconciled.", before=8, after=5)

    add_heading(doc, "Final Release Appendix", page_break_before=True)
    add_label(doc, "Release Verification Summary")
    add_body(doc,
             "The repair packet consolidates the approved document identity, "
             "implementation workflow, and retirement controls into one traceable "
             "release record.", after=8)
    for number, text in VERIFICATION_ITEMS:
        p = doc.add_paragraph(style="Normal")
        p.paragraph_format.space_after = Pt(7)
        p.paragraph_format.keep_together = True
        run = p.add_run(f"{number}   ")
        set_run_font(run, DISPLAY_FONT, 11, bold=True, color=TEAL)
        run = p.add_run(text)
        set_run_font(run, BODY_FONT, 10.5, color=SLATE)

    add_label(doc, "Controlled Document Register")
    register_count = len(data["records"])
    add_body(doc,
             f"The controlled document register below lists {register_count} "
             "controlled documents released under this repair packet; each entry "
             "records the corrected version, effective date, owner, training due "
             "date, retention period, and release status.", after=6)
    add_table(doc, [REGISTER_HEADER] + build_register_rows(data), REGISTER_WIDTHS)

    add_label(doc, "Release Authorization")
    for key, value in AUTH_VALUES:
        p = doc.add_paragraph(style="Normal")
        p.paragraph_format.space_after = Pt(2.5)
        p.paragraph_format.keep_together = True
        run = p.add_run(f"{key}: ")
        set_run_font(run, BODY_FONT, 9.6, bold=True, color=TEAL)
        run = p.add_run(value)
        set_run_font(run, BODY_FONT, 9.6, color=SLATE)

    add_callout(doc, "Final review status: ready for controlled document release.",
                dark=True)

    closing = doc.add_paragraph(style="Normal")
    closing.paragraph_format.space_before = Pt(8)
    closing.paragraph_format.space_after = Pt(0)
    set_paragraph_border(closing, "top", RULE, size=4, space=8)
    run = closing.add_run("RELEASE RECORD  /  QUALITY SYSTEMS OFFICE  /  2026")
    set_run_font(run, BODY_FONT, 8.2, bold=True, color=MUTED)

    props = doc.core_properties
    props.author = PUBLIC_AUTHOR
    props.last_modified_by = PUBLIC_AUTHOR
    props.title = PUBLIC_TITLE
    props.subject = PUBLIC_SUBJECT
    props.keywords = PUBLIC_KEYWORDS
    props.category = PUBLIC_CATEGORY
    props.content_status = "Released"
    props.comments = PUBLIC_COMMENTS
    props.created = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)
    props.modified = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)
    props.revision = 2

    settings = doc.settings._element
    update_fields = settings.find(qn("w:updateFields"))
    if update_fields is None:
        update_fields = OxmlElement("w:updateFields")
        settings.append(update_fields)
    update_fields.set(qn("w:val"), "true")
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
    if "DRAFT" not in text:
        raise RuntimeError(f"source {source} does not carry the DRAFT marker")
    # The draft must still contain the frozen wrong values that the repair
    # workflow is required to remove.
    for marker in ("QMS-PR-700", "version 4.1", "2026-07-01", "5 years"):
        if marker not in text:
            raise RuntimeError(f"source {source} missing internal error marker {marker!r}")


def build(source: Path, records_path: Path, output: Path, stage_dir: Path | None = None):
    data = json.loads(Path(records_path).read_text(encoding="utf-8"))
    verify_draft_source(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    doc = build_packet(data)
    raw = output.parent / f".raw-{output.name}"
    doc.save(str(raw))
    deterministic_zip(raw, output)
    raw.unlink(missing_ok=True)
    return len(data["records"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records",
                        default=os.environ.get("VARIANT_RECORDS", "/root/tmp/docs/records.json"),
                        help="frozen records.json prepared material")
    parser.add_argument("--input", default=os.environ.get("VARIANT_INPUT"),
                        help="source DOCX path (default: /root input for this variant)")
    parser.add_argument("--output", default=os.environ.get("VARIANT_OUTPUT"),
                        help="output DOCX path")
    args = parser.parse_args(argv)
    if not args.output:
        parser.error("--output is required (or set VARIANT_OUTPUT)")
    records_path = Path(args.records)
    if not records_path.is_file():
        parser.error(f"records material missing: {records_path}")
    source = Path(args.input) if args.input else None
    if source is None:
        candidates = sorted(
            Path("/root").glob(
                "docops_v2_l3_001_docx_controlled_document_release_repair_input_*.docx"))
        if not candidates:
            parser.error("cannot locate the synthetic input DOCX under /root; pass --input")
        source = candidates[0]
    count = build(source, records_path, Path(args.output))
    print(args.output)
    print(f"Records: {count}")


if __name__ == "__main__":
    main()
