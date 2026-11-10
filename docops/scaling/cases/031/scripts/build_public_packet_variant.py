#!/usr/bin/env python3
"""Parameterized builder for synthetic scaled PDF 031 variants.

Mirrors the frozen parent build_public_packet.py: ReportLab builds the pages
and pypdf finalizes bookmarks/metadata. Page sizes, portrait rules, fonts,
drawing helpers, pageCompression and the 144 DPI PNG render step are unchanged.

The only change is that the builder iterates every hearing group declared in
``notices.json`` and actually runs the five page-drawing functions per group
(cover, corrected hearing summary, comment category matrix, response workflow,
release controls and appendix index). Page numbers, "page / total" footers and
bookmark targets are computed over all groups. Pages are never duplicated from
a 5-page base; every group enters the drawing functions.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

PAGES_PER_GROUP = 5

HEADER_BLUE = HexColor("#0B3D91")
ACCENT_AMBER = HexColor("#F59E0B")
INK = HexColor("#182230")
MUTED = HexColor("#5B6778")
RULE = HexColor("#D7DFEA")
PANEL = HexColor("#F6F8FB")
AMBER_PANEL = HexColor("#FFF5DE")
BLUE_PANEL = HexColor("#EEF3FB")
WHITE = white

PAGE_TITLES = [
    "Public Hearing Packet: Zoning Amendment Comments",
    "Corrected Hearing Summary",
    "Comment Category Matrix",
    "Response Workflow",
    "Release Controls and Appendix Index",
]

PAGE_W, PAGE_H = LETTER


def wrap_text(text, font_name, font_size, max_width):
    lines = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if stringWidth(candidate, font_name, font_size) <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def draw_paragraph(c, text, x, y, max_width, font_name="Helvetica",
                   font_size=9.2, leading=13.2, color=INK, max_lines=None):
    lines = wrap_text(text, font_name, font_size, max_width)
    if max_lines is not None:
        lines = lines[:max_lines]
    c.setFont(font_name, font_size)
    c.setFillColor(color)
    for line in lines:
        c.drawString(x, y, line)
        y -= leading
    return y


def draw_header(c, group, rel_page):
    c.setFillColor(HEADER_BLUE)
    c.rect(0, 710, PAGE_W, 82, fill=1, stroke=0)
    c.setFillColor(ACCENT_AMBER)
    c.rect(0, 706, PAGE_W, 4, fill=1, stroke=0)

    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(52, 767, "PUBLIC HEARING RELEASE")
    c.setFont("Helvetica", 8)
    c.drawRightString(560, 767, group["id"])

    c.setFont("Helvetica-Bold", 18 if rel_page == 1 else 21)
    c.drawString(52, 733, PAGE_TITLES[rel_page - 1])


def draw_footer(c, page_number, total_pages, group):
    c.setStrokeColor(RULE)
    c.setLineWidth(0.7)
    c.line(52, 47, 560, 47)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 8)
    c.drawString(52, 29, f"Public Hearing Release | {group['id']} | 2026")
    c.drawRightString(560, 29, f"{page_number} / {total_pages}")


def draw_kicker(c, text, y):
    c.setFillColor(HEADER_BLUE)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(52, y, text.upper())


def draw_section_heading(c, text, y):
    c.setFillColor(ACCENT_AMBER)
    c.roundRect(52, y - 3, 4, 15, 2, fill=1, stroke=0)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(65, y, text)


def draw_status_box(c, label, title, detail, x, y, width, height):
    c.setFillColor(AMBER_PANEL)
    c.setStrokeColor(ACCENT_AMBER)
    c.setLineWidth(1)
    c.roundRect(x, y, width, height, 7, fill=1, stroke=1)
    c.setFillColor(ACCENT_AMBER)
    c.roundRect(x, y, 6, height, 3, fill=1, stroke=0)

    c.setFillColor(MUTED)
    c.setFont("Helvetica-Bold", 7.7)
    c.drawString(x + 20, y + height - 16, label.upper())
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(x + 20, y + height - 34, title)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 7.8)
    c.drawString(x + 20, y + 10, detail)


def draw_fact_card(c, x, y, width, label, value, detail):
    c.setFillColor(PANEL)
    c.setStrokeColor(RULE)
    c.setLineWidth(0.6)
    c.roundRect(x, y, width, 72, 6, fill=1, stroke=1)
    c.setFillColor(HEADER_BLUE)
    c.roundRect(x, y + 69, width, 3, 1.5, fill=1, stroke=0)

    c.setFillColor(MUTED)
    c.setFont("Helvetica-Bold", 7.5)
    c.drawString(x + 13, y + 55, label.upper())
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(x + 13, y + 34, value)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 7.6)
    c.drawString(x + 13, y + 18, detail)


def draw_content_item(c, x, y, number, title, page):
    c.setFillColor(WHITE)
    c.setStrokeColor(RULE)
    c.setLineWidth(0.65)
    c.roundRect(x, y, 248, 48, 5, fill=1, stroke=1)
    c.setFillColor(BLUE_PANEL)
    c.circle(x + 23, y + 24, 13, fill=1, stroke=0)
    c.setFillColor(HEADER_BLUE)
    c.setFont("Helvetica-Bold", 7.5)
    c.drawCentredString(x + 23, y + 21.4, number)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(x + 45, y + 28, title)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 7.5)
    c.drawString(x + 45, y + 13, f"Page {page}")


def draw_table(c, x, top, widths, header_height, rows, row_heights,
               aligns=None, total_row=False, font_sizes=None):
    aligns = aligns or ["left"] * len(widths)
    font_sizes = font_sizes or [8] * len(widths)

    c.setFillColor(HEADER_BLUE)
    c.rect(x, top - header_height, sum(widths), header_height, fill=1, stroke=0)
    cursor_x = x
    for i, text in enumerate(rows[0]):
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 7.8)
        if aligns[i] == "center":
            c.drawCentredString(cursor_x + widths[i] / 2, top - header_height + 9, text)
        elif aligns[i] == "right":
            c.drawRightString(cursor_x + widths[i] - 8, top - header_height + 9, text)
        else:
            c.drawString(cursor_x + 8, top - header_height + 9, text)
        cursor_x += widths[i]

    y = top - header_height
    for row_index, row in enumerate(rows[1:]):
        height = row_heights[row_index]
        is_total = total_row and row_index == len(rows[1:]) - 1
        if is_total:
            c.setFillColor(BLUE_PANEL)
        else:
            c.setFillColor(WHITE if row_index % 2 == 0 else PANEL)
        c.rect(x, y - height, sum(widths), height, fill=1, stroke=0)
        c.setStrokeColor(RULE)
        c.setLineWidth(0.45)
        c.line(x, y - height, x + sum(widths), y - height)
        cursor_x = x
        for col_index, text in enumerate(row):
            font_name = "Helvetica-Bold" if is_total else "Helvetica"
            font_size = font_sizes[col_index]
            lines = wrap_text(text, font_name, font_size, widths[col_index] - 16)
            available_lines = max(1, int((height - 8) / (font_size + 2)))
            lines = lines[:available_lines]
            c.setFillColor(INK)
            c.setFont(font_name, font_size)
            text_y = y - 13
            for line in lines:
                if aligns[col_index] == "center":
                    c.drawCentredString(cursor_x + widths[col_index] / 2, text_y, line)
                elif aligns[col_index] == "right":
                    c.drawRightString(cursor_x + widths[col_index] - 8, text_y, line)
                else:
                    c.drawString(cursor_x + 8, text_y, line)
                text_y -= font_size + 2
            cursor_x += widths[col_index]
        y -= height
    return y


def draw_workflow_step(c, y, number, title, description, highlight=False):
    card_x = 92
    card_w = 468
    card_h = 52
    if highlight:
        c.setFillColor(AMBER_PANEL)
        c.setStrokeColor(ACCENT_AMBER)
        c.setLineWidth(1)
    else:
        c.setFillColor(PANEL)
        c.setStrokeColor(RULE)
        c.setLineWidth(0.6)
    c.roundRect(card_x, y, card_w, card_h, 6, fill=1, stroke=1)

    c.setFillColor(ACCENT_AMBER if highlight else HEADER_BLUE)
    c.circle(72, y + card_h / 2, 15, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawCentredString(72, y + card_h / 2 - 3, number)

    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 9.5)
    c.drawString(card_x + 14, y + 33, title)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 8.1)
    c.drawString(card_x + 14, y + 17, description)


def draw_control_item(c, x, y, width, text):
    c.setFillColor(WHITE)
    c.setStrokeColor(RULE)
    c.setLineWidth(0.55)
    c.roundRect(x, y, width, 34, 5, fill=1, stroke=1)
    c.setFillColor(HEADER_BLUE)
    c.circle(x + 17, y + 17, 8, fill=1, stroke=0)
    c.setStrokeColor(WHITE)
    c.setLineWidth(1.2)
    c.line(x + 13.5, y + 17, x + 16.5, y + 14)
    c.line(x + 16.5, y + 14, x + 21, y + 21)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 7.9)
    c.drawString(x + 31, y + 13, text)


def draw_cover(c, group, page_number, total_pages):
    draw_header(c, group, 1)
    draw_kicker(c, "Public release snapshot", 676)
    draw_status_box(c, "Public release status", "Clean public copy",
                    "Corrected facts, page sequence, and publication controls verified.",
                    52, 607, 508, 54)

    draw_fact_card(c, 52, 519, 248, "Hearing date", group["hearing_date"],
                   "Public hearing record")
    draw_fact_card(c, 312, 519, 248, "Public comments",
                   str(group["comment_total"]), "Deduplicated submissions")
    draw_fact_card(c, 52, 435, 248, "Response deadline",
                   group["response_deadline"], "Public response date")
    draw_fact_card(c, 312, 435, 248, "Public contact", group["contact"],
                   "Consolidated public channel")

    draw_section_heading(c, "Packet contents", 401)
    for item in group["packet_contents"]:
        number = int(item["number"])
        x = 52 if number in (1, 3) else 312
        y = 342 if number in (1, 2) else 286
        draw_content_item(c, x, y, item["number"], item["title"], item["page"])

    c.setFillColor(BLUE_PANEL)
    c.roundRect(52, 178, 508, 82, 7, fill=1, stroke=0)
    c.setFillColor(HEADER_BLUE)
    c.setFont("Helvetica-Bold", 7.7)
    c.drawString(70, 239, "PUBLICATION NOTE")
    draw_paragraph(
        c,
        f"Use this packet as the public reference for {group['id']}. "
        f"Category figures apply to the {group['comment_total']} deduplicated "
        "comments documented in the public record.",
        70, 221, 470, font_size=9.2, leading=14, max_lines=3)
    draw_footer(c, page_number, total_pages, group)


def draw_summary(c, group, page_number, total_pages):
    draw_header(c, group, 2)
    draw_kicker(c, "Corrected public record", 676)
    draw_section_heading(c, "Final public record", 647)
    draw_paragraph(
        c,
        f"The public hearing record for {group['id']} is consolidated below. "
        "The corrected date, deduplicated comment total, response deadline, "
        "and public contact are used consistently throughout this packet.",
        52, 626, 508, font_size=9.3, leading=14, max_lines=3)

    draw_status_box(c, "Correction applied", "Final public facts",
                    "All summary values match the corrected public hearing record.",
                    52, 543, 508, 54)

    draw_section_heading(c, "Corrected facts", 508)
    table_rows = [
        ["Record element", "Final public value"],
        ["Hearing date", group["hearing_date"]],
        ["Docket ID", group["id"]],
        ["Public comment count", f"{group['comment_total']} deduplicated comments"],
        ["Response deadline", group["response_deadline"]],
        ["Public contact", group["contact"]],
    ]
    table_bottom = draw_table(c, 52, 486, [168, 340], 27, table_rows, [31] * 5,
                              aligns=["left", "left"], font_sizes=[8.3, 8.3])

    draw_section_heading(c, "Public feedback profile", table_bottom - 31)
    draw_paragraph(c, group["feedback_note"], 52, table_bottom - 53, 508,
                   font_size=9.1, leading=14, max_lines=4)
    draw_paragraph(
        c,
        "The complete category distribution, public response focus, and "
        "follow-up lane appear on the next page.",
        52, table_bottom - 108, 508, font_size=9.1, leading=14, max_lines=3)

    c.setFillColor(AMBER_PANEL)
    c.roundRect(52, 112, 508, 58, 7, fill=1, stroke=0)
    c.setFillColor(ACCENT_AMBER)
    c.rect(52, 112, 5, 58, fill=1, stroke=0)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(70, 151, "Record reading")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 8.5)
    c.drawString(70, 135, "Counts describe the deduplicated public comment set.")
    c.drawString(70, 121, "Percentages are rounded to one decimal place.")
    draw_footer(c, page_number, total_pages, group)


def draw_matrix(c, group, page_number, total_pages):
    draw_header(c, group, 3)
    draw_kicker(c, "Comment record", 676)
    draw_paragraph(
        c,
        f"The matrix assigns the {group['comment_total']} comments to six "
        "primary categories and identifies the public issue focus and "
        "follow-up lane for each group.",
        52, 653, 508, font_size=9.3, leading=14, max_lines=2)

    table_rows = [
        ["Category", "Comments", "Share", "Public response focus", "Follow-up lane"],
    ]
    for category in group["categories"]:
        table_rows.append([category["name"], str(category["count"]),
                           category["share"], category["focus"], category["lane"]])
    table_rows.append(["Total", str(group["comment_total"]), "100.0%",
                       "Deduplicated public comment set", ""])
    table_bottom = draw_table(
        c, 52, 606, [150, 58, 52, 138, 110], 29, table_rows,
        [44] * len(group["categories"]) + [34],
        aligns=["left", "center", "center", "left", "left"],
        total_row=True, font_sizes=[8.2, 8.1, 8.1, 7.6, 7.6])

    c.setFillColor(BLUE_PANEL)
    c.roundRect(52, table_bottom - 67, 508, 49, 7, fill=1, stroke=0)
    c.setFillColor(HEADER_BLUE)
    c.setFont("Helvetica-Bold", 8.2)
    c.drawString(70, table_bottom - 35, "MATRIX NOTE")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 8.1)
    c.drawString(70, table_bottom - 50,
                 "Each submission is assigned once by its primary issue. Percentages may not add due to rounding.")
    draw_footer(c, page_number, total_pages, group)


def draw_workflow(c, group, page_number, total_pages):
    draw_header(c, group, 4)
    draw_kicker(c, "Public response process", 676)
    draw_paragraph(
        c,
        "The response workflow keeps every public comment traceable from "
        "intake through the published follow-up.",
        52, 653, 508, font_size=9.3, leading=14, max_lines=2)
    draw_status_box(c, "Public response deadline", group["response_deadline"],
                    f"Final public update target for {group['id']}.",
                    52, 575, 508, 52)
    draw_section_heading(c, "Five-step public workflow", 548)

    c.setStrokeColor(RULE)
    c.setLineWidth(2)
    c.line(72, 505, 72, 258)

    steps = []
    for index, step in enumerate(group["workflow"]):
        steps.append((step["number"], step["step"], step["body"],
                      index == 3))
    y_positions = [478, 416, 354, 292, 230]
    for y, (number, title, description, highlight) in zip(y_positions, steps):
        draw_workflow_step(c, y, number, title, description, highlight)

    c.setFillColor(BLUE_PANEL)
    c.roundRect(52, 126, 508, 67, 7, fill=1, stroke=0)
    c.setFillColor(HEADER_BLUE)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(70, 169, "PUBLIC CONTACT")
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(70, 149, group["contact"])
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 8.2)
    c.drawString(260, 169, f"Use the docket ID for all written follow-up: {group['id']}.")
    c.drawString(260, 149, f"The public response deadline is {group['response_deadline']}.")
    draw_footer(c, page_number, total_pages, group)


def draw_release(c, group, page_number, total_pages):
    draw_header(c, group, 5)
    draw_kicker(c, "Release record", 676)
    draw_paragraph(
        c,
        "Publication controls are listed below with the appendix index for "
        "this five-page public release.",
        52, 653, 508, font_size=9.3, leading=14, max_lines=2)
    draw_status_box(c, "Public release status", "Release ready",
                    "Required package controls verified.",
                    52, 575, 508, 52)

    draw_section_heading(c, "Release controls", 540)
    controls = group["controls"]
    y_positions = [493, 457, 421, 385]
    for row, y in enumerate(y_positions):
        draw_control_item(c, 52, y, 248, controls[row * 2])
        draw_control_item(c, 312, y, 248, controls[row * 2 + 1])

    draw_section_heading(c, "Appendix index", 359)
    appendix_rows = [
        ["Index", "Public packet section", "Page"],
    ]
    for item in group["appendix"]:
        appendix_rows.append([item["index"], item["section"], str(item["page"])])
    table_bottom = draw_table(c, 52, 337, [72, 336, 100], 27, appendix_rows,
                              [31] * len(group["appendix"]),
                              aligns=["center", "left", "center"],
                              font_sizes=[8.2, 8.2, 8.2])

    doc_y = table_bottom - 60
    c.setFillColor(PANEL)
    c.roundRect(52, doc_y, 508, 48, 6, fill=1, stroke=0)
    control_data = [
        ("FORMAT", "PDF"),
        ("PAGES", str(total_pages)),
        ("DOCKET", group["id"]),
        ("CONTACT", group["contact"]),
    ]
    widths = [127, 127, 127, 127]
    cursor = 52
    for (label, value), width in zip(control_data, widths):
        c.setFillColor(MUTED)
        c.setFont("Helvetica-Bold", 7)
        c.drawString(cursor + 12, doc_y + 31, label)
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 8.8)
        c.drawString(cursor + 12, doc_y + 14, value)
        cursor += width
    draw_footer(c, page_number, total_pages, group)


def build_reportlab_pdf(groups, path):
    total_pages = len(groups) * PAGES_PER_GROUP
    c = canvas.Canvas(str(path), pagesize=LETTER, pageCompression=1)
    page_number = 0
    for group in groups:
        page_number += 1
        draw_cover(c, group, page_number, total_pages)
        c.showPage()
        page_number += 1
        draw_summary(c, group, page_number, total_pages)
        c.showPage()
        page_number += 1
        draw_matrix(c, group, page_number, total_pages)
        c.showPage()
        page_number += 1
        draw_workflow(c, group, page_number, total_pages)
        c.showPage()
        page_number += 1
        draw_release(c, group, page_number, total_pages)
        c.showPage()
    c.save()
    return total_pages


def finalize_pdf(source_path, output_path, groups):
    reader = PdfReader(str(source_path))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)

    writer.add_metadata(
        {
            "/Title": PAGE_TITLES[0],
            "/Author": "Public Hearing Desk",
            "/Subject": "Clean flattened public release packet",
            "/Keywords": "zoning; public hearing; public release",
            "/Creator": "Public Hearing Desk",
            "/Producer": "ReportLab",
        }
    )

    page_number = 0
    for group in groups:
        for offset, title in enumerate(PAGE_TITLES):
            writer.add_outline_item(f"{group['id']} | {title}", page_number)
            page_number += 1

    writer._root_object.update(
        {NameObject("/PageMode"): NameObject("/UseOutlines")}
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as handle:
        writer.write(handle)


def build(notices_path: Path, output_path: Path, work_dir: Path | None = None) -> int:
    data = json.loads(Path(notices_path).read_text(encoding="utf-8"))
    groups = data["groups"]
    work = work_dir or Path("/root/tmp/docs")
    work.mkdir(parents=True, exist_ok=True)
    raw_pdf = work / "public_hearing_release_raw.pdf"
    total = build_reportlab_pdf(groups, raw_pdf)
    finalize_pdf(raw_pdf, output_path, groups)
    return total


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--notices", default=os.environ.get("VARIANT_NOTICES", "/root/tmp/docs/notices.json"),
                        help="frozen notices.json prepared material")
    parser.add_argument("--output", default=os.environ.get("VARIANT_OUTPUT"),
                        help="output PDF path")
    parser.add_argument("--work-dir", default=os.environ.get("VARIANT_WORK_DIR"),
                        help="work directory (default /root/tmp/docs)")
    args = parser.parse_args(argv)
    if not args.output:
        parser.error("--output is required (or set VARIANT_OUTPUT)")
    total = build(Path(args.notices), Path(args.output),
                  Path(args.work_dir) if args.work_dir else None)
    print(args.output)
    print(f"Pages: {total}")


if __name__ == "__main__":
    main()
