"""Parameterized builder for synthetic scaled PPTX 029 variants.

Restores the FROZEN parent builder's eight public release slide types
(title, agenda, market_context, kpi, risks, mitigation, decision, appendix)
and parameterizes them per business unit from the prepared units.json material.
It cleans internal draft/scratch and placeholder slides, rebuilds the eight
public pages per unit with each unit's own facts (KPI table, customer-risk
table, mitigation plan with colored status, decision request cards, market
context callouts, appendix data notes), numbers footers "Slide i of <total>"
across the whole deck, and preserves the source's trailing "Reference - Locked
Legal" page exactly (never rebuilt or cleared) in the final position. Output
size is driven by the unit count (8N + 1 slides).
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Iterable

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

PAGES_PER_UNIT = 8
SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)

NAVY = RGBColor(0x11, 0x28, 0x46)
NAVY_2 = RGBColor(0x1B, 0x3A, 0x5C)
INK = RGBColor(0x20, 0x2D, 0x3A)
SLATE = RGBColor(0x5E, 0x6F, 0x80)
MUTED = RGBColor(0x8A, 0x98, 0xA5)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
OFFWHITE = RGBColor(0xF6, 0xF8, 0xFA)
PALE = RGBColor(0xEB, 0xF1, 0xF4)
PALE_BLUE = RGBColor(0xE5, 0xEF, 0xF7)
TEAL = RGBColor(0x0C, 0x84, 0x84)
TEAL_PALE = RGBColor(0xDC, 0xF0, 0xEE)
AMBER = RGBColor(0xDB, 0x91, 0x2F)
AMBER_PALE = RGBColor(0xFB, 0xEE, 0xD6)

HEAD_FONT = "Aptos Display"
BODY_FONT = "Aptos"

FOOTER_TEXT = "QBR Release | 2026-06-05"
AGENDA_OWNERS = ["Maya Chen", "Jon Bell", "Priya Rao"]

KPI_HEADER = ["Metric", "Value", "QBR Readout"]
RISK_HEADER = ["Risk", "Account Count", "Owner", "Mitigation"]
MITIGATION_HEADER = ["Action", "Owner", "Due Date", "Status"]
AGENDA_HEADER = ["Section", "Slide", "Owner"]


def remove_all_shapes(slide) -> None:
    for shape in list(slide.shapes):
        shape._element.getparent().remove(shape._element)


def set_background(slide, color: RGBColor) -> None:
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color


def add_rect(slide, x, y, w, h, fill, *, radius=False, line=None, line_width=0.75):
    shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE
    shape = slide.shapes.add_shape(shape_type, Inches(x), Inches(y), Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    if line is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = line
        shape.line.width = Pt(line_width)
    if radius:
        shape.adjustments[0] = 0.08
    return shape


def add_circle(slide, x, y, d, fill, *, transparency=0):
    shape = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y),
                                   Inches(d), Inches(d))
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.fill.transparency = transparency
    shape.line.fill.background()
    return shape


def add_text(slide, text, x, y, w, h, *, size=16, color=INK, font=BODY_FONT,
             bold=False, italic=False, align=PP_ALIGN.LEFT, valign=MSO_ANCHOR.TOP,
             margin=0, line_spacing=1.0):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    box.text_frame.clear()
    box.text_frame.word_wrap = True
    box.text_frame.margin_left = Inches(margin)
    box.text_frame.margin_right = Inches(margin)
    box.text_frame.margin_top = Inches(margin)
    box.text_frame.margin_bottom = Inches(margin)
    box.text_frame.vertical_anchor = valign
    paragraph = box.text_frame.paragraphs[0]
    paragraph.alignment = align
    paragraph.line_spacing = line_spacing
    run = paragraph.add_run()
    run.text = text
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    return box


def add_header(slide, title: str, kicker: str, slide_no: int) -> None:
    set_background(slide, OFFWHITE)
    add_rect(slide, 0, 0, 13.333, 0.12, TEAL)
    add_rect(slide, 0.55, 0.38, 0.09, 0.86, TEAL)
    add_text(slide, kicker.upper(), 0.82, 0.34, 7.8, 0.28, size=10, color=TEAL, bold=True)
    add_text(slide, title, 0.80, 0.59, 9.5, 0.55, size=29, color=NAVY,
             font=HEAD_FONT, bold=True)
    add_text(slide, f"{slide_no:02d}", 11.95, 0.44, 0.72, 0.46, size=19,
             color=RGBColor(0xA4, 0xB5, 0xC2), font=HEAD_FONT, bold=True,
             align=PP_ALIGN.RIGHT)


def add_footer(slide, slide_no: int, total: int) -> None:
    add_rect(slide, 0.56, 6.98, 12.20, 0.012, PALE_BLUE)
    add_text(slide, FOOTER_TEXT, 0.58, 7.08, 4.2, 0.22, size=9, color=SLATE)
    add_text(slide, f"Slide {slide_no} of {total}", 10.97, 7.08, 1.76, 0.22,
             size=9, color=SLATE, align=PP_ALIGN.RIGHT)


def add_callout(slide, x, y, w, h, *, label, body, fill, accent, body_color=INK):
    add_rect(slide, x, y, w, h, fill, radius=True)
    add_rect(slide, x, y, 0.09, h, accent)
    add_text(slide, label.upper(), x + 0.27, y + 0.22, w - 0.48, 0.25, size=10,
             color=accent, bold=True)
    add_text(slide, body, x + 0.27, y + 0.57, w - 0.48, h - 0.73, size=17,
             color=body_color, bold=True)


def style_cell(cell, text, *, fill, color, size, bold=False,
               align=PP_ALIGN.LEFT, margin=0.12) -> None:
    cell.fill.solid()
    cell.fill.fore_color.rgb = fill
    cell.margin_left = Inches(margin)
    cell.margin_right = Inches(margin)
    cell.margin_top = Inches(0.08)
    cell.margin_bottom = Inches(0.08)
    cell.vertical_anchor = MSO_ANCHOR.MIDDLE
    frame = cell.text_frame
    frame.clear()
    frame.word_wrap = True
    paragraph = frame.paragraphs[0]
    paragraph.alignment = align
    run = paragraph.add_run()
    run.text = text
    run.font.name = BODY_FONT
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color


def add_table(slide, x, y, w, h, headers, rows, col_widths=None, *,
              font_size=13, header_size=12):
    table_shape = slide.shapes.add_table(len(rows) + 1, len(headers),
                                         Inches(x), Inches(y), Inches(w), Inches(h))
    table = table_shape.table
    table.first_row = True
    table.horz_banding = False
    table.vert_banding = False
    if col_widths is not None:
        if len(col_widths) != len(headers) or abs(sum(col_widths) - w) > 0.02:
            raise ValueError("Column widths must match headers and table width")
        for index, width in enumerate(col_widths):
            table.columns[index].width = Inches(width)
    table.rows[0].height = Inches(0.54)
    remaining = h - 0.54
    row_height = remaining / len(rows)
    for row_index in range(1, len(table.rows)):
        table.rows[row_index].height = Inches(row_height)
    for col_index, header in enumerate(headers):
        style_cell(table.cell(0, col_index), header, fill=NAVY, color=WHITE,
                   size=header_size, bold=True)
    for row_index, row in enumerate(rows, 1):
        fill = WHITE if row_index % 2 else PALE
        for col_index, value in enumerate(row):
            style_cell(table.cell(row_index, col_index), value, fill=fill,
                       color=INK, size=font_size, bold=(col_index == 0))
    return table_shape


def status_badge(slide, x, y, status):
    fill = AMBER_PALE if status == "Open" else TEAL_PALE
    color = AMBER if status == "Open" else TEAL
    add_rect(slide, x, y, 1.10, 0.42, fill, radius=True)
    add_text(slide, status, x, y + 0.01, 1.10, 0.34, size=10, color=color,
             bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)


def find_legal_slide(prs):
    for slide in prs.slides:
        if slide._element.cSld.get("name") == "Reference - Locked Legal":
            return slide
    raise RuntimeError("Locked legal slide not found in source deck")


def remove_internal_slides(prs) -> None:
    sld_id_list = prs.slides._sldIdLst
    for sld_id in list(sld_id_list):
        r_id = sld_id.get(qn("r:id"))
        slide = prs.part.related_part(r_id).slide
        name = slide._element.cSld.get("name", "")
        if name in ("Placeholder", "Reference - Locked Legal"):
            continue
        sld_id_list.remove(sld_id)
        prs.part.drop_rel(r_id)


def move_legal_last(prs, legal_part_name: str) -> None:
    sld_id_list = prs.slides._sldIdLst
    elements = list(sld_id_list)
    legal_element = None
    for sld_id in elements:
        r_id = sld_id.get(qn("r:id"))
        name = Path(str(prs.part.related_part(r_id).partname)).name
        if name == legal_part_name:
            legal_element = sld_id
            break
    for sld_id in elements:
        sld_id_list.remove(sld_id)
    for sld_id in elements:
        if sld_id is not legal_element:
            sld_id_list.append(sld_id)
    if legal_element is not None:
        sld_id_list.append(legal_element)


# ---- Frozen parent slide types, parameterized per business unit -------------

def build_title(slide, unit, slide_no, total):
    remove_all_shapes(slide)
    set_background(slide, NAVY)
    slide._element.cSld.set("name", "Title")
    add_circle(slide, 9.74, -1.28, 5.1, TEAL, transparency=32)
    add_circle(slide, 11.01, 3.87, 3.5, AMBER, transparency=38)
    add_circle(slide, 8.88, 4.96, 1.28, WHITE, transparency=87)
    add_rect(slide, 0.76, 0.72, 0.11, 2.62, TEAL)
    add_text(slide, "Title", 1.08, 0.73, 1.5, 0.3, size=11,
             color=RGBColor(0xA9, 0xE1, 0xDD), bold=True)
    add_text(slide, f"QBR Release - {unit['name']}", 1.03, 1.13, 9.2, 0.72,
             size=43, color=WHITE, font=HEAD_FONT, bold=True)
    add_text(slide, "Quarterly Business Review", 1.06, 1.96, 7.4, 0.5, size=23,
             color=RGBColor(0xD5, 0xE3, 0xEE), font=HEAD_FONT)
    add_text(slide, f"{unit['id']} | June 5, 2026", 1.06, 2.53, 4.0, 0.35,
             size=14, color=RGBColor(0xA9, 0xE1, 0xDD), bold=True)
    add_rect(slide, 1.06, 3.75, 5.45, 0.035, RGBColor(0x72, 0xC7, 0xC0))
    add_text(slide,
             f"A decision-focused readout on {unit['name']} market context, "
             "account risk, and the path to NRR recovery.",
             1.06, 4.05, 6.45, 1.05, size=18, color=RGBColor(0xE8, 0xEF, 0xF5),
             line_spacing=1.15)
    add_text(slide, "PREPARED FOR EXECUTIVE REVIEW", 8.64, 6.72, 2.76, 0.25,
             size=9, color=RGBColor(0xDA, 0xE6, 0xEE), bold=True,
             align=PP_ALIGN.RIGHT)


def build_agenda(slide, unit, unit_index, slide_no, total):
    remove_all_shapes(slide)
    set_background(slide, OFFWHITE)
    slide._element.cSld.set("name", "Agenda")
    add_rect(slide, 0, 0, 0.18, 7.5, NAVY)
    add_rect(slide, 0.63, 0.54, 0.09, 0.80, TEAL)
    add_text(slide, "MEETING FLOW", 0.95, 0.49, 5.0, 0.28, size=10, color=TEAL, bold=True)
    add_text(slide, "Agenda", 0.92, 0.75, 6.0, 0.64, size=34, color=NAVY,
             font=HEAD_FONT, bold=True)
    add_text(slide, "Six sections aligned to the final release sequence.",
             7.10, 0.93, 5.40, 0.38, size=14, color=SLATE, align=PP_ALIGN.RIGHT)
    base = unit_index * PAGES_PER_UNIT
    owners = unit.get("owners", AGENDA_OWNERS)
    rows = [
        ["Market Context", str(base + 3), owners[0]],
        ["KPI Snapshot", str(base + 4), owners[1]],
        ["Customer Risks", str(base + 5), owners[2]],
        ["Mitigation Plan", str(base + 6), owners[0]],
        ["Decision Request", str(base + 7), owners[1]],
        ["Appendix - Data Notes", str(base + 8), owners[2]],
    ]
    add_table(slide, 0.92, 1.76, 11.72, 4.68, AGENDA_HEADER, rows,
              [5.30, 1.48, 4.94], font_size=15, header_size=12)
    add_text(slide, f"Final deck: {total} slides, including the locked legal reference.",
             0.93, 6.67, 7.4, 0.25, size=10, color=MUTED, italic=True)


def build_market_context(slide, unit, slide_no, total):
    remove_all_shapes(slide)
    slide._element.cSld.set("name", "Market Context")
    add_header(slide, "Market Context", "Demand signal", slide_no)
    add_text(slide, unit["market_headline"], 0.82, 1.30, 11.8, 0.52, size=23,
             color=INK, font=HEAD_FONT, bold=True)
    add_callout(slide, 0.82, 2.18, 3.70, 2.70, label=unit["market_callouts"][0][0],
                body=unit["market_callouts"][0][1], fill=WHITE, accent=TEAL)
    add_callout(slide, 4.80, 2.18, 3.70, 2.70, label=unit["market_callouts"][1][0],
                body=unit["market_callouts"][1][1], fill=WHITE, accent=AMBER)
    add_callout(slide, 8.78, 2.18, 3.72, 2.70, label=unit["market_callouts"][2][0],
                body=unit["market_callouts"][2][1], fill=NAVY, accent=TEAL,
                body_color=WHITE)
    add_rect(slide, 0.82, 5.36, 11.68, 0.86, PALE_BLUE, radius=True)
    add_text(slide, "QBR lens", 1.12, 5.60, 1.10, 0.25, size=10, color=TEAL, bold=True)
    add_text(slide, unit["market_lens"], 2.15, 5.53, 9.78, 0.34, size=15,
             color=NAVY, bold=True)
    add_footer(slide, slide_no, total)


def build_kpi(slide, unit, slide_no, total):
    remove_all_shapes(slide)
    slide._element.cSld.set("name", "KPI Snapshot")
    add_header(slide, "KPI Snapshot", "Performance readout", slide_no)
    add_text(slide, "Revenue is growing, but retention and expansion need intervention.",
             0.82, 1.30, 11.7, 0.50, size=21, color=INK, font=HEAD_FONT, bold=True)
    add_table(slide, 0.82, 2.00, 9.18, 4.42, KPI_HEADER, unit["kpi_rows"],
              [2.70, 2.12, 4.36], font_size=14, header_size=12)
    add_rect(slide, 10.34, 2.00, 2.15, 4.42, NAVY, radius=True)
    add_rect(slide, 10.62, 2.31, 0.60, 0.08, TEAL)
    add_text(slide, "EXECUTIVE\nSIGNAL", 10.61, 2.52, 1.45, 0.76, size=13,
             color=RGBColor(0xB6, 0xDA, 0xD8), bold=True, line_spacing=1.08)
    add_text(slide, str(unit["churn_accounts"]), 10.59, 3.41, 1.50, 0.98, size=54,
             color=WHITE, font=HEAD_FONT, bold=True)
    add_text(slide, "accounts need executive review", 10.61, 4.37, 1.50, 1.10,
             size=14, color=RGBColor(0xE3, 0xEC, 0xF3), bold=True)
    add_text(slide, f"NRR {unit['nrr']}%", 10.61, 5.62, 1.48, 0.30, size=12,
             color=RGBColor(0xF2, 0xCA, 0x8D), bold=True)
    add_footer(slide, slide_no, total)


def build_risks(slide, unit, slide_no, total):
    remove_all_shapes(slide)
    slide._element.cSld.set("name", "Customer Risks")
    add_header(slide, "Customer Risks", "Account exposure", slide_no)
    add_text(slide, "Named account risks with owners and dated mitigations.",
             0.82, 1.30, 11.0, 0.50, size=22, color=INK, font=HEAD_FONT, bold=True)
    add_table(slide, 0.82, 2.02, 11.66, 4.38, RISK_HEADER, unit["risk_rows"],
              [2.44, 1.58, 1.78, 5.86], font_size=14, header_size=11.5)
    add_text(slide, "OWNERSHIP", 0.85, 6.58, 1.20, 0.22, size=9, color=TEAL, bold=True)
    add_text(slide, "Each risk has a named owner and a dated mitigation.",
             1.95, 6.54, 8.90, 0.26, size=11, color=SLATE)
    add_footer(slide, slide_no, total)


def build_mitigation(slide, unit, slide_no, total):
    remove_all_shapes(slide)
    slide._element.cSld.set("name", "Mitigation Plan")
    add_header(slide, "Mitigation Plan", "Execution plan", slide_no)
    add_text(slide, "Three actions move the risk response into execution this week.",
             0.82, 1.30, 11.6, 0.50, size=22, color=INK, font=HEAD_FONT, bold=True)
    table_shape = add_table(slide, 0.82, 2.02, 11.66, 3.58, MITIGATION_HEADER,
                            unit["mitigation_rows"], [5.24, 2.20, 2.22, 2.00],
                            font_size=14, header_size=12)
    status_table = table_shape.table
    for row_index in range(1, len(unit["mitigation_rows"]) + 1):
        status = unit["mitigation_rows"][row_index - 1][3]
        cell = status_table.cell(row_index, 3)
        cell.fill.solid()
        cell.fill.fore_color.rgb = AMBER_PALE if status == "Open" else TEAL_PALE
        for paragraph in cell.text_frame.paragraphs:
            for run in paragraph.runs:
                run.font.bold = True
                run.font.color.rgb = AMBER if status == "Open" else TEAL
    add_rect(slide, 0.82, 5.98, 11.66, 0.72, NAVY, radius=True)
    add_text(slide, "EXECUTION WINDOW", 1.10, 6.20, 1.90, 0.20, size=9,
             color=RGBColor(0x9F, 0xD5, 0xD1), bold=True)
    add_text(slide, "2026-06-06  →  2026-06-12", 3.20, 6.11, 3.50, 0.30, size=15,
             color=WHITE, bold=True)
    add_footer(slide, slide_no, total)


def build_decision(slide, unit, slide_no, total):
    remove_all_shapes(slide)
    slide._element.cSld.set("name", "Decision Request")
    add_header(slide, "Decision Request", "Required approvals", slide_no)
    add_text(slide, "Three approvals unlock outreach, enablement, and the decision deadline.",
             0.82, 1.28, 11.9, 0.50, size=21, color=INK, font=HEAD_FONT, bold=True)
    statements = [row[0] for row in unit["decision_rows"]]
    for index, statement in enumerate(statements):
        y = 1.99 + index * 1.41
        add_rect(slide, 0.82, y, 8.46, 1.16, WHITE, radius=True)
        add_circle(slide, 1.10, y + 0.31, 0.52, NAVY)
        add_text(slide, f"0{index + 1}", 1.10, y + 0.32, 0.52, 0.28, size=11,
                 color=WHITE, bold=True, align=PP_ALIGN.CENTER,
                 valign=MSO_ANCHOR.MIDDLE)
        add_text(slide, statement, 1.88, y + 0.26, 7.02, 0.54, size=17,
                 color=NAVY, font=HEAD_FONT, bold=True, valign=MSO_ANCHOR.MIDDLE)
    add_rect(slide, 9.62, 1.99, 2.88, 3.96, NAVY, radius=True)
    add_text(slide, "DECISION DATE", 9.98, 2.27, 1.90, 0.24, size=9,
             color=RGBColor(0xA9, 0xE1, 0xDD), bold=True)
    add_text(slide, "06.07", 9.94, 2.72, 2.20, 0.76, size=38, color=WHITE,
             font=HEAD_FONT, bold=True)
    add_text(slide, "2026", 9.98, 3.49, 1.65, 0.30, size=14,
             color=RGBColor(0xD4, 0xE5, 0xEF), bold=True)
    add_rect(slide, 9.98, 4.05, 1.58, 0.06, TEAL)
    add_text(slide, "Approvals are required before the mitigation review closes.",
             9.98, 4.44, 1.88, 1.02, size=13, color=RGBColor(0xE5, 0xED, 0xF4),
             line_spacing=1.08)
    add_footer(slide, slide_no, total)


def build_appendix(slide, unit, slide_no, total):
    remove_all_shapes(slide)
    slide._element.cSld.set("name", "Appendix - Data Notes")
    add_header(slide, "Appendix - Data Notes", "Traceability", slide_no)
    add_text(slide, "The published readout is tied to a single public source.",
             0.82, 1.28, 11.8, 0.50, size=22, color=INK, font=HEAD_FONT, bold=True)
    add_rect(slide, 0.82, 2.12, 8.14, 3.56, WHITE, radius=True)
    add_rect(slide, 0.82, 2.12, 0.11, 3.56, TEAL)
    add_text(slide, "PUBLIC SOURCE", 1.22, 2.50, 2.20, 0.28, size=10, color=TEAL, bold=True)
    add_text(slide, "“", 1.18, 2.88, 1.00, 0.85, size=58, color=PALE_BLUE,
             font=HEAD_FONT, bold=True)
    add_text(slide, unit["data_notes"], 1.82, 3.12, 6.46, 1.18, size=24, color=NAVY,
             font=HEAD_FONT, bold=True, line_spacing=1.04)
    add_text(slide, "Use this citation for the KPI and customer-risk figures in the release deck.",
             1.84, 4.64, 6.35, 0.56, size=13, color=SLATE)
    add_rect(slide, 9.34, 2.12, 3.15, 1.62, NAVY, radius=True)
    add_text(slide, "DATA CURRENCY", 9.65, 2.42, 2.25, 0.24, size=9,
             color=RGBColor(0xA9, 0xE1, 0xDD), bold=True)
    add_text(slide, unit["data_currency"], 9.63, 2.79, 2.40, 0.44, size=23,
             color=WHITE, font=HEAD_FONT, bold=True)
    add_rect(slide, 9.34, 4.02, 3.15, 1.66, TEAL_PALE, radius=True)
    add_text(slide, "SOURCE STANDARD", 9.65, 4.33, 2.25, 0.24, size=9, color=TEAL, bold=True)
    add_text(slide, "Public-safe language only.", 9.64, 4.78, 2.34, 0.54, size=17,
             color=NAVY, font=HEAD_FONT, bold=True)
    add_footer(slide, slide_no, total)


BUILDERS = [
    build_title, build_agenda, build_market_context, build_kpi,
    build_risks, build_mitigation, build_decision, build_appendix,
]


def build(units_path: Path, output_path: Path) -> int:
    data = json.loads(Path(units_path).read_text(encoding="utf-8"))
    units = data["units"]
    source_path = Path(data["input_path"])
    total = len(units) * PAGES_PER_UNIT + 1

    presentation = Presentation(str(source_path))
    presentation.slide_width = SLIDE_W
    presentation.slide_height = SLIDE_H

    legal = find_legal_slide(presentation)
    legal_part_name = Path(str(legal.part.partname)).name

    remove_internal_slides(presentation)

    slide_no = 0
    for slide in list(presentation.slides):
        name = slide._element.cSld.get("name", "")
        if name == "Reference - Locked Legal":
            continue
        unit_index, kind = divmod(slide_no, PAGES_PER_UNIT)
        unit = units[unit_index]
        slide_no += 1
        if kind == 1:
            BUILDERS[kind](slide, unit, unit_index, slide_no, total)
        else:
            BUILDERS[kind](slide, unit, slide_no, total)
        note_text = (unit["decision_note"] if kind == 6
                     else unit["page_notes"][kind])
        notes_tf = slide.notes_slide.notes_text_frame
        notes_tf.clear()
        p = notes_tf.paragraphs[0]
        run = p.add_run()
        run.text = note_text
        run.font.name = BODY_FONT
        run.font.size = Pt(12)
    assert slide_no == len(units) * PAGES_PER_UNIT

    move_legal_last(presentation, legal_part_name)
    if Path(str(presentation.slides[-1].part.partname)).name != legal_part_name:
        raise RuntimeError("Locked legal slide did not land in final position")

    presentation.core_properties.title = "QBR Release"
    presentation.core_properties.subject = (
        "Quarterly Business Review release deck (synthetic scale variant)")
    presentation.core_properties.author = "QBR Release Workflow"
    presentation.core_properties.keywords = (
        "QBR, release, KPI, customer risk, mitigation, decision request"
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    presentation.save(output_path)
    return len(presentation.slides)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--units", default=os.environ.get("VARIANT_UNITS", "/root/tmp/docs/units.json"))
    parser.add_argument("--output", default=os.environ.get("VARIANT_OUTPUT"))
    args = parser.parse_args(argv)
    if not args.output:
        parser.error("--output is required (or set VARIANT_OUTPUT)")
    count = build(Path(args.units), Path(args.output))
    print(args.output)
    print(f"Slides: {count}")


if __name__ == "__main__":
    main()
