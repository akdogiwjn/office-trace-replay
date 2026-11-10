"""Parameterized builder for synthetic scaled PPTX 026 variants.

Mirrors the frozen parent builder (build_climate_disclosure.py) but reads the
prepared reporting-unit material (units.json) and iterates units, rebuilding the
same nine public disclosure slides per unit with each unit's own corrected
facts: a native clustered-column trend chart with per-unit 3-year cached data
and per-unit inventory / supplier tables. Output size is driven by the unit
count read from the synthetic source deck's material, not by appending
unprocessed pages.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from pptx import Presentation
from pptx.chart.data import ChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

SLIDE_W = 13.333
SLIDE_H = 7.5
MARGIN = 0.68
PAGES_PER_UNIT = 9
SERIES_NAME = "Total emissions tCO2e"

COLORS = {
    "title_bg": RGBColor(0x0F, 0x17, 0x2A),
    "content_bg": RGBColor(0xF8, 0xFA, 0xFC),
    "title_text": RGBColor(0x0F, 0x17, 0x2A),
    "white": RGBColor(0xFF, 0xFF, 0xFF),
    "accent": RGBColor(0x22, 0xC5, 0x5E),
    "table_header": RGBColor(0x16, 0x65, 0x34),
    "forest": RGBColor(0x16, 0x65, 0x34),
    "slate_900": RGBColor(0x0F, 0x17, 0x2A),
    "slate_700": RGBColor(0x33, 0x41, 0x55),
    "slate_600": RGBColor(0x47, 0x55, 0x69),
    "slate_500": RGBColor(0x64, 0x74, 0x8B),
    "slate_300": RGBColor(0xCB, 0xD5, 0xE1),
    "slate_200": RGBColor(0xE2, 0xE8, 0xF0),
    "slate_100": RGBColor(0xF1, 0xF5, 0xF9),
    "lime_100": RGBColor(0xDC, 0xFC, 0xE7),
    "lime_200": RGBColor(0xBB, 0xF7, 0xD0),
    "lime_900": RGBColor(0x14, 0x53, 0x2D),
}

FOOTER_TEXT = "Public Climate Disclosure | FY2026"


def remove_source_slides(prs) -> None:
    """Workflow step 1: remove all internal-only slides and their note material."""
    sld_id_list = prs.slides._sldIdLst
    for sld_id in list(sld_id_list):
        rel_id = sld_id.rId
        sld_id_list.remove(sld_id)
        prs.part.drop_rel(rel_id)


def add_text(slide, text, x, y, w, h, *, size=16, color=None, bold=False,
             font="Aptos", align=PP_ALIGN.LEFT, valign=MSO_ANCHOR.TOP, margin=0):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = Inches(margin)
    tf.margin_right = Inches(margin)
    tf.margin_top = Inches(margin)
    tf.margin_bottom = Inches(margin)
    tf.vertical_anchor = valign
    p = tf.paragraphs[0]
    p.alignment = align
    p.space_before = Pt(0)
    p.space_after = Pt(0)
    run = p.add_run()
    run.text = text
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color or COLORS["slate_900"]
    return box


def add_rect(slide, x, y, w, h, *, fill, line=None,
             shape=MSO_SHAPE.RECTANGLE, radius=None):
    rect = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    rect.fill.solid()
    rect.fill.fore_color.rgb = fill
    if line is None:
        rect.line.fill.background()
    else:
        rect.line.color.rgb = line
        rect.line.width = Pt(0.8)
    if radius is not None and shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        rect.adjustments[0] = radius
    return rect


def add_card(slide, x, y, w, h, fill=None, line=None):
    return add_rect(slide, x, y, w, h, fill=fill or COLORS["white"],
                    line=line or COLORS["slate_200"],
                    shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08)


def add_number_badge(slide, number, x, y, *, light=False):
    fill = COLORS["white"] if light else COLORS["accent"]
    color = COLORS["forest"] if light else COLORS["slate_900"]
    add_rect(slide, x, y, 0.42, 0.42, fill=fill, shape=MSO_SHAPE.OVAL)
    add_text(slide, str(number), x, y + 0.015, 0.42, 0.36, size=12, bold=True,
             color=color, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)


def build_boundary_slide(slide, unit):
    cards = [
        ("Reporting entity", unit["name"], "Consolidated public climate disclosure"),
        ("Reporting period", "FY2026", "Annual reporting cycle"),
        ("Base year", str(unit["base_year"]), "Corrected baseline for trend reporting"),
        ("Boundary", "Operational control", "Scope 1 and location-based Scope 2"),
    ]
    positions = [(0.82, 1.40), (6.76, 1.40), (0.82, 3.38), (6.76, 3.38)]
    for (heading, value, detail), (x, y) in zip(cards, positions):
        add_card(slide, x, y, 5.78, 1.64)
        add_text(slide, heading, x + 0.28, y + 0.22, 2.50, 0.28, size=11,
                 color=COLORS["slate_500"], bold=True)
        add_text(slide, value, x + 0.28, y + 0.55, 4.95, 0.50, size=24,
                 color=COLORS["slate_900"], bold=True)
        add_text(slide, detail, x + 0.28, y + 1.14, 5.10, 0.27, size=13,
                 color=COLORS["slate_600"])
    add_rect(slide, 0.82, 5.36, 11.72, 1.02, fill=COLORS["lime_100"],
             shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08)
    add_text(slide, "Disclosure approach", 1.08, 5.58, 2.25, 0.28, size=12,
             color=COLORS["forest"], bold=True)
    add_text(slide, "Annual inventory • GHG Protocol methodology • Public "
                    "reporting with concise evidence references",
             1.08, 5.91, 10.85, 0.30, size=14, color=COLORS["slate_700"])


def rebuild_inventory_table(slide, unit):
    facts = {
        "base_year": unit["base_year"],
        "scope_1": unit["scope_1"],
        "scope_2_location_based": unit["scope_2_location_based"],
        "renewable_electricity_pct": unit["renewable_electricity_pct"],
        "submission_status": unit["submission_status"],
    }
    rows = [
        ("Metric", "Public value", "Reporting basis", "Status"),
        ("Base year", str(facts["base_year"]), "Annual trend baseline",
         facts["submission_status"]),
        ("Scope 1 emissions", f"{facts['scope_1']:,} tCO2e", "Operational control",
         facts["submission_status"]),
        ("Scope 2 emissions", f"{facts['scope_2_location_based']:,} tCO2e",
         "Location-based", facts["submission_status"]),
        ("Renewable electricity", f"{facts['renewable_electricity_pct']}%",
         "Share of electricity use", facts["submission_status"]),
    ]
    table_shape = slide.shapes.add_table(5, 4, Inches(0.82), Inches(1.54),
                                         Inches(8.52), Inches(3.96))
    table = table_shape.table
    table.first_row = True
    table.horz_banding = False
    for idx, width in enumerate([2.20, 1.92, 2.52, 1.88]):
        table.columns[idx].width = Inches(width)
    table.rows[0].height = Inches(0.58)
    for row_index in range(1, len(table.rows)):
        table.rows[row_index].height = Inches(0.75)
    for r_idx, row in enumerate(rows):
        for c_idx, value in enumerate(row):
            cell = table.cell(r_idx, c_idx)
            cell.margin_left = Inches(0.16)
            cell.margin_right = Inches(0.12)
            cell.margin_top = Inches(0.06)
            cell.margin_bottom = Inches(0.06)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf = cell.text_frame
            tf.clear()
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT
            run = p.add_run()
            run.text = value
            run.font.name = "Aptos"
            run.font.size = Pt(12.5 if r_idx else 11.5)
            run.font.bold = r_idx == 0 or c_idx == 0 or (c_idx == 3 and r_idx > 0)
            run.font.color.rgb = COLORS["slate_900"]

    add_card(slide, 9.64, 1.54, 2.88, 1.85, fill=COLORS["title_bg"], line=COLORS["title_bg"])
    add_text(slide, "2024 BASE YEAR", 9.92, 1.82, 2.20, 0.28, size=11,
             color=COLORS["accent"], bold=True)
    add_text(slide, str(facts["base_year"]), 9.92, 2.17, 2.18, 0.66, size=36,
             color=COLORS["white"], bold=True)
    add_text(slide, "Corrected baseline", 9.92, 2.91, 2.18, 0.27, size=12,
             color=COLORS["slate_300"])

    add_card(slide, 9.64, 3.65, 2.88, 1.85, fill=COLORS["lime_100"], line=COLORS["lime_200"])
    add_text(slide, "SCOPE 2 LOCATION-BASED", 9.92, 3.93, 2.24, 0.28, size=10.5,
             color=COLORS["forest"], bold=True)
    add_text(slide, f"{facts['scope_2_location_based']:,}", 9.92, 4.28, 2.18, 0.56,
             size=30, color=COLORS["forest"], bold=True)
    add_text(slide, "tCO2e • corrected value", 9.92, 4.95, 2.20, 0.27, size=11.5,
             color=COLORS["slate_600"])

    add_text(slide, "Key inventory inputs shown for public review; the trend "
                    "chart reports annual totals.",
             0.84, 5.72, 11.45, 0.34, size=11.5, color=COLORS["slate_500"])


def rebuild_trend_chart(slide, unit):
    chart_data = ChartData()
    chart_data.categories = unit["trend_years"]
    chart_data.add_series(SERIES_NAME, tuple(unit["trend_values"]))
    chart_shape = slide.shapes.add_chart(
        XL_CHART_TYPE.COLUMN_CLUSTERED,
        Inches(0.82), Inches(1.48), Inches(8.72), Inches(4.92),
        chart_data,
    )
    chart = chart_shape.chart
    chart.has_title = True
    chart.chart_title.text_frame.text = "Annual reported total emissions"
    chart.has_legend = True
    chart.legend.position = XL_LEGEND_POSITION.BOTTOM
    chart.legend.include_in_layout = False
    chart.legend.font.name = "Aptos"
    chart.legend.font.size = Pt(11)
    chart.legend.font.color.rgb = COLORS["slate_600"]
    plot = chart.plots[0]
    plot.gap_width = 48
    plot.has_data_labels = True
    labels = plot.data_labels
    labels.position = XL_LABEL_POSITION.OUTSIDE_END
    labels.font.name = "Aptos"
    labels.font.size = Pt(11)
    labels.font.bold = True
    labels.font.color.rgb = COLORS["slate_700"]
    labels.number_format = '#,##0'
    chart.value_axis.minimum_scale = 0
    chart.value_axis.maximum_scale = 50000
    chart.value_axis.major_unit = 10000
    chart.value_axis.has_major_gridlines = True
    chart.value_axis.tick_labels.font.name = "Aptos"
    chart.value_axis.tick_labels.font.size = Pt(10)
    chart.value_axis.tick_labels.font.color.rgb = COLORS["slate_500"]
    chart.category_axis.tick_labels.font.name = "Aptos"
    chart.category_axis.tick_labels.font.size = Pt(12)
    chart.category_axis.tick_labels.font.bold = True
    chart.category_axis.tick_labels.font.color.rgb = COLORS["slate_700"]
    series = chart.series[0]
    series.format.fill.solid()
    series.format.fill.fore_color.rgb = COLORS["accent"]
    series.format.line.fill.background()

    t1, _, t3 = unit["trend_values"]
    change = round((t3 - t1) / t1 * 100, 1)
    add_card(slide, 9.82, 1.48, 2.70, 1.34)
    add_text(slide, "2024 TOTAL", 10.08, 1.72, 2.16, 0.26, size=10.5,
             color=COLORS["slate_500"], bold=True)
    add_text(slide, f"{t1:,}", 10.08, 2.02, 2.16, 0.54, size=27,
             color=COLORS["slate_900"], bold=True)

    add_card(slide, 9.82, 3.04, 2.70, 1.34)
    add_text(slide, "2026 TOTAL", 10.08, 3.28, 2.16, 0.26, size=10.5,
             color=COLORS["slate_500"], bold=True)
    add_text(slide, f"{t3:,}", 10.08, 3.58, 2.16, 0.54, size=27,
             color=COLORS["forest"], bold=True)

    add_rect(slide, 9.82, 4.60, 2.70, 1.80, fill=COLORS["title_bg"],
             shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08)
    add_text(slide, "3-YEAR CHANGE", 10.08, 4.88, 2.08, 0.26, size=10.5,
             color=COLORS["accent"], bold=True)
    add_text(slide, f"{change:+.1f}%", 10.08, 5.20, 2.12, 0.58, size=29,
             color=COLORS["white"], bold=True)
    add_text(slide, "Reported annual totals", 10.08, 5.91, 1.98, 0.27, size=10.8,
             color=COLORS["slate_300"])


def build_assurance_slide(slide, unit):
    facts = {
        "submission_status": unit["submission_status"],
        "assurance_owner": unit["assurance_owner"],
        "base_year": unit["base_year"],
    }
    add_rect(slide, 0.82, 1.46, 11.72, 1.16, fill=COLORS["title_bg"],
             shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08)
    add_text(slide, "SUBMISSION STATUS", 1.10, 1.73, 2.05, 0.28, size=11,
             color=COLORS["accent"], bold=True)
    add_text(slide, facts["submission_status"], 1.10, 2.02, 3.10, 0.42, size=26,
             color=COLORS["white"], bold=True)
    add_text(slide, "Public disclosure record", 9.17, 1.82, 2.82, 0.28, size=13,
             color=COLORS["slate_300"], align=PP_ALIGN.RIGHT)
    add_text(slide, "Status updated after correction review", 8.10, 2.15, 3.90, 0.25,
             size=10.8, color=COLORS["slate_300"], align=PP_ALIGN.RIGHT)

    add_card(slide, 0.82, 2.96, 5.58, 1.62)
    add_text(slide, "Assurance owner", 1.08, 3.23, 2.32, 0.28, size=11,
             color=COLORS["slate_500"], bold=True)
    add_text(slide, facts["assurance_owner"], 1.08, 3.57, 4.58, 0.50, size=25,
             color=COLORS["slate_900"], bold=True)
    add_text(slide, "Accountable for public disclosure review", 1.08, 4.08, 4.75, 0.28,
             size=12, color=COLORS["slate_600"])

    add_card(slide, 6.69, 2.96, 5.85, 1.62)
    add_text(slide, "Reporting basis", 6.96, 3.23, 2.32, 0.28, size=11,
             color=COLORS["slate_500"], bold=True)
    add_text(slide, f"{facts['base_year']} baseline", 6.96, 3.57, 4.78, 0.50, size=25,
             color=COLORS["slate_900"], bold=True)
    add_text(slide, "Scope 1 and location-based Scope 2", 6.96, 4.08, 4.98, 0.28,
             size=12, color=COLORS["slate_600"])

    steps = [
        ("01", "Inventory checked", "Corrected Scope 2 and renewable-energy values applied"),
        ("02", "Owner review", "Public disclosure record reviewed"),
        ("03", "Submitted", "Current submission status confirmed"),
    ]
    for i, (number, heading, description) in enumerate(steps):
        x = 0.82 + i * 3.98
        add_card(slide, x, 4.88, 3.72, 1.42, fill=COLORS["lime_100"], line=COLORS["lime_200"])
        add_number_badge(slide, number, x + 0.24, 5.10, light=True)
        add_text(slide, heading, x + 0.82, 5.08, 2.55, 0.30, size=14,
                 color=COLORS["forest"], bold=True)
        add_text(slide, description, x + 0.82, 5.43, 2.56, 0.52, size=10.8,
                 color=COLORS["slate_600"])


def build_transition_slide(slide, unit):
    add_text(slide, "A focused five-workstream plan converts the corrected "
                    "inventory into operational follow-through.",
             0.82, 1.41, 11.60, 0.50, size=15, color=COLORS["slate_600"])
    coords = [
        (0.82, 2.16, 3.72, 1.84),
        (4.80, 2.16, 3.72, 1.84),
        (8.78, 2.16, 3.72, 1.84),
        (0.82, 4.29, 5.78, 1.66),
        (6.88, 4.29, 5.62, 1.66),
    ]
    for number, (heading, body) in enumerate(unit["transition_actions"], 1):
        (x, y, w, h) = coords[number - 1]
        add_card(slide, x, y, w, h)
        add_number_badge(slide, f"{number:02d}", x + 0.25, y + 0.28)
        add_text(slide, heading, x + 0.82, y + 0.27, w - 1.06, 0.31, size=16,
                 color=COLORS["slate_900"], bold=True)
        add_text(slide, body, x + 0.82, y + 0.72, w - 1.06, 0.78, size=12,
                 color=COLORS["slate_600"])


def rebuild_supplier_table(slide, unit):
    rows = [["Supplier segment", "Engagement focus", "Evidence status", "Next step"]]
    rows.extend(unit["supplier_rows"])
    add_text(slide, "A public register of supplier engagement priorities supports "
                    "transparent value-chain follow-through.",
             0.82, 1.39, 11.60, 0.38, size=15, color=COLORS["slate_600"])
    table_shape = slide.shapes.add_table(5, 4, Inches(0.82), Inches(1.88),
                                         Inches(11.72), Inches(3.84))
    table = table_shape.table
    table.first_row = True
    table.horz_banding = False
    for idx, width in enumerate([2.70, 4.42, 2.10, 2.50]):
        table.columns[idx].width = Inches(width)
    table.rows[0].height = Inches(0.58)
    for row_index in range(1, len(table.rows)):
        table.rows[row_index].height = Inches(0.80)
    for r_idx, row in enumerate(rows):
        for c_idx, value in enumerate(row):
            cell = table.cell(r_idx, c_idx)
            cell.margin_left = Inches(0.18)
            cell.margin_right = Inches(0.12)
            cell.margin_top = Inches(0.05)
            cell.margin_bottom = Inches(0.05)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf = cell.text_frame
            tf.clear()
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT
            run = p.add_run()
            run.text = value
            run.font.name = "Aptos"
            run.font.size = Pt(12.2 if r_idx else 11.5)
            run.font.bold = r_idx == 0 or c_idx in (0, 2)
            run.font.color.rgb = COLORS["slate_900"]
    add_rect(slide, 0.82, 6.02, 11.72, 0.58, fill=COLORS["lime_100"],
             shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.12)
    add_text(slide, "Public principle: engage priority suppliers with clear data "
                    "expectations, consistent cadence, and documented progress.",
             1.04, 6.16, 11.16, 0.28, size=11.5, color=COLORS["forest"], bold=True)


def build_board_slide(slide, unit):
    for i, (heading, body) in enumerate(unit["board_decisions"]):
        x = 0.82 + i * 3.98
        add_card(slide, x, 1.58, 3.72, 3.56)
        add_number_badge(slide, f"{i + 1:02d}", x + 0.27, 1.89)
        add_text(slide, heading, x + 0.27, 2.50, 3.16, 0.64, size=19,
                 color=COLORS["slate_900"], bold=True)
        add_text(slide, body, x + 0.27, 3.34, 3.10, 1.22, size=13,
                 color=COLORS["slate_600"])
        add_text(slide, "BOARD ACTION", x + 0.27, 4.72, 2.64, 0.24, size=10.5,
                 color=COLORS["forest"], bold=True)

    add_rect(slide, 0.82, 5.58, 11.72, 0.96, fill=COLORS["title_bg"],
             shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08)
    add_text(slide, "PUBLIC DISCLOSURE POSITION", 1.08, 5.78, 3.12, 0.24, size=10.8,
             color=COLORS["accent"], bold=True)
    add_text(slide, "Corrected inventory • Submitted • 2024 baseline",
             1.08, 6.08, 10.85, 0.28, size=15, color=COLORS["white"], bold=True)


def build_style_slide(slide, unit):
    add_text(slide, "The public system uses a restrained palette, strong type "
                    "hierarchy, and consistent disclosure elements.",
             0.82, 1.41, 11.60, 0.42, size=15, color=COLORS["slate_600"])
    swatches = [
        ("TITLE", "0F172A", COLORS["title_bg"], COLORS["white"]),
        ("CONTENT", "F8FAFC", COLORS["content_bg"], COLORS["slate_900"]),
        ("ACCENT", "22C55E", COLORS["accent"], COLORS["slate_900"]),
        ("TABLE", "166534", COLORS["table_header"], COLORS["white"]),
    ]
    for i, (label, hex_value, fill, text_color) in enumerate(swatches):
        x = 0.82 + i * 2.22
        add_rect(slide, x, 2.00, 1.95, 1.40, fill=fill, line=COLORS["slate_200"],
                 shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08)
        add_text(slide, label, x + 0.18, 2.20, 1.58, 0.24, size=10.5, color=text_color, bold=True)
        add_text(slide, hex_value, x + 0.18, 2.67, 1.58, 0.36, size=20, color=text_color, bold=True)

    add_card(slide, 0.82, 3.72, 5.68, 2.34)
    add_text(slide, "TYPE SYSTEM", 1.08, 3.98, 2.30, 0.26, size=10.8,
             color=COLORS["forest"], bold=True)
    add_text(slide, "Aptos Display", 1.08, 4.32, 4.84, 0.58, size=29,
             color=COLORS["slate_900"], bold=True, font="Aptos Display")
    add_text(slide, "Bold titles • clear hierarchy • plain-language body copy",
             1.08, 5.08, 4.94, 0.54, size=14, color=COLORS["slate_600"])

    add_card(slide, 6.78, 3.72, 5.76, 2.34)
    add_text(slide, "PUBLICATION ELEMENT", 7.04, 3.98, 2.62, 0.26, size=10.8,
             color=COLORS["forest"], bold=True)
    add_text(slide, "Footer", 7.04, 4.34, 4.76, 0.32, size=13,
             color=COLORS["slate_500"], bold=True)
    add_text(slide, FOOTER_TEXT, 7.04, 4.75, 4.94, 0.32, size=15,
             color=COLORS["slate_900"], bold=True)
    add_text(slide, "Every slide • exact wording • consistent placement",
             7.04, 5.28, 4.86, 0.28, size=11.5, color=COLORS["slate_600"])

    add_rect(slide, 0.82, 6.31, 11.72, 0.16, fill=COLORS["accent"],
             shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.50)


def add_titles(slide, index, unit):
    if index == 0:
        add_text(slide, "FY2026 PUBLIC CLIMATE DISCLOSURE", 0.96, 1.26, 5.65, 0.30,
                 size=11.5, color=COLORS["accent"], bold=True)
        add_text(slide, f"{unit['name']} Climate Disclosure Briefing",
                 0.96, 1.72, 10.98, 1.72, size=40, color=COLORS["white"],
                 bold=True, font="Aptos Display")
        add_text(slide, "A concise public briefing on boundary, emissions, "
                        "assurance, and action.",
                 0.96, 3.65, 8.50, 0.64, size=19, color=COLORS["slate_300"])
        chips = [
            ("Boundary", "Operational control"),
            ("Baseline", str(unit["base_year"])),
            ("Status", unit["submission_status"]),
        ]
        for i, (label, value) in enumerate(chips):
            x = 0.96 + i * 3.55
            add_card(slide, x, 4.86, 3.16, 1.14, fill=RGBColor(0x1E, 0x29, 0x3B),
                     line=RGBColor(0x33, 0x41, 0x55))
            add_text(slide, label.upper(), x + 0.24, 5.08, 2.62, 0.24, size=9.8,
                     color=COLORS["accent"], bold=True)
            add_text(slide, value, x + 0.24, 5.44, 2.62, 0.34, size=17,
                     color=COLORS["white"], bold=True)
    else:
        add_text(slide, _TITLE_BASE[index], 0.96, 0.45, 11.55, 0.62, size=31,
                 color=COLORS["title_text"], bold=True, font="Aptos Display")


_TITLE_BASE = [
    "Climate Disclosure Briefing",
    "Disclosure Boundary",
    "Corrected Emissions Inventory",
    "Emissions Trend Chart",
    "Assurance Status",
    "Transition Action Plan",
    "Supplier Engagement Register",
    "Board Actions",
    "Publication Style Guide",
]


def apply_public_style(prs, table_slides, is_title_flags):
    """Workflow step 6: apply the final public visual system after content rebuilds."""
    for index, slide in enumerate(prs.slides):
        is_title = is_title_flags[index]
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = (
            COLORS["title_bg"] if is_title else COLORS["content_bg"]
        )
        accent = add_rect(
            slide, 0.38, 1.33 if is_title else 0.48, 0.12,
            0.56 if is_title else 1.32,
            fill=COLORS["accent"],
        )
        accent.name = "Public Green Accent Rectangle"
        add_text(
            slide, FOOTER_TEXT, MARGIN, 7.05, 8.60, 0.24, size=9.2,
            color=COLORS["slate_300"] if is_title else COLORS["slate_500"],
            bold=False,
        )

    for slide in table_slides:
        for shape in slide.shapes:
            if not getattr(shape, "has_table", False):
                continue
            table = shape.table
            for c_idx in range(len(table.columns)):
                cell = table.cell(0, c_idx)
                cell.fill.solid()
                cell.fill.fore_color.rgb = COLORS["table_header"]
                for p in cell.text_frame.paragraphs:
                    for run in p.runs:
                        run.font.name = "Aptos"
                        run.font.bold = True
                        run.font.color.rgb = COLORS["white"]
            for r_idx in range(1, len(table.rows)):
                for c_idx in range(len(table.columns)):
                    cell = table.cell(r_idx, c_idx)
                    cell.fill.solid()
                    cell.fill.fore_color.rgb = (
                        COLORS["white"] if r_idx % 2 else COLORS["slate_100"]
                    )

    for slide in prs.slides:
        for shape in slide.shapes:
            if getattr(shape, "has_chart", False):
                chart = shape.chart
                chart.font.name = "Aptos"
                chart.font.size = Pt(10.5)
                chart.font.color.rgb = COLORS["slate_600"]
                chart.chart_title.text_frame.paragraphs[0].runs[0].font.name = "Aptos Display"
                chart.chart_title.text_frame.paragraphs[0].runs[0].font.size = Pt(17)
                chart.chart_title.text_frame.paragraphs[0].runs[0].font.bold = True
                chart.chart_title.text_frame.paragraphs[0].runs[0].font.color.rgb = COLORS["slate_900"]


def add_public_notes(prs, units):
    """Workflow step 7: retain only concise per-unit public speaker notes."""
    notes = []
    for unit in units:
        notes.extend(unit["notes"])
    for slide, note in zip(prs.slides, notes):
        notes_tf = slide.notes_slide.notes_text_frame
        notes_tf.clear()
        p = notes_tf.paragraphs[0]
        run = p.add_run()
        run.text = note
        run.font.name = "Aptos"
        run.font.size = Pt(12)


def build(units_path: Path, output_path: Path) -> int:
    data = json.loads(Path(units_path).read_text(encoding="utf-8"))
    units = data["units"]
    source_path = Path(data["input_path"])
    total = len(units) * PAGES_PER_UNIT

    presentation = Presentation(str(source_path))
    presentation.slide_width = Inches(SLIDE_W)
    presentation.slide_height = Inches(SLIDE_H)
    presentation.core_properties.title = "Climate Disclosure Rebuild"
    presentation.core_properties.subject = "Public climate disclosure per reporting unit (synthetic scale variant)"
    presentation.core_properties.author = "Sustainability Reporting"
    presentation.core_properties.comments = "Approved public climate disclosure."
    presentation.core_properties.keywords = "climate disclosure; emissions; trend; assurance; 2026"

    # 1. Remove internal-only slides and confidential note material.
    remove_source_slides(presentation)

    # 2/3. Rebuild the required public slide structure from the blank layout.
    blank_layout = presentation.slide_layouts[6]
    for _ in range(total):
        presentation.slides.add_slide(blank_layout)

    for index, slide in enumerate(presentation.slides):
        unit = units[index // PAGES_PER_UNIT]
        add_titles(slide, index % PAGES_PER_UNIT, unit)

    table_slides = []
    index = 0
    for unit in units:
        index += 1  # skip the unit title slide (content added by add_titles)
        build_boundary_slide(presentation.slides[index], unit)
        index += 1
        rebuild_inventory_table(presentation.slides[index], unit)
        table_slides.append(presentation.slides[index])
        index += 1
        rebuild_trend_chart(presentation.slides[index], unit)
        index += 1
        build_assurance_slide(presentation.slides[index], unit)
        index += 1
        build_transition_slide(presentation.slides[index], unit)
        index += 1
        rebuild_supplier_table(presentation.slides[index], unit)
        table_slides.append(presentation.slides[index])
        index += 1
        build_board_slide(presentation.slides[index], unit)
        index += 1
        build_style_slide(presentation.slides[index], unit)
        index += 1

    # 6. Apply the required public visual style after content and chart data are final.
    is_title_flags = [
        (index % PAGES_PER_UNIT) == 0 for index in range(total)
    ]
    apply_public_style(presentation, table_slides, is_title_flags)

    # 7. Preserve only concise public speaker notes.
    add_public_notes(presentation, units)

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
