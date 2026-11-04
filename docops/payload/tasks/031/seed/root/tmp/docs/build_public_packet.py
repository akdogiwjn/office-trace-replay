#!/usr/bin/env python3
"""Build the clean, five-page public hearing release packet."""

from pathlib import Path

from reportlab.lib.colors import HexColor, Color, white
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


OUTPUT = Path(
    "/root/submission/"
    "docops_v2_l3_031_pdf_public_hearing_packet_flatten_release_output.pdf"
)

PAGE_W, PAGE_H = LETTER
HEADER_BLUE = HexColor("#0B3D91")
ACCENT_AMBER = HexColor("#F59E0B")
INK = HexColor("#182230")
MUTED = HexColor("#5B6778")
LIGHT_MUTED = HexColor("#E8EDF4")
RULE = HexColor("#D7DFEA")
PANEL = HexColor("#F6F8FB")
AMBER_PANEL = HexColor("#FFF5DE")
BLUE_PANEL = HexColor("#EEF3FB")
WHITE = white

TITLES = [
    "Public Hearing Packet: Zoning Amendment Comments",
    "Corrected Hearing Summary",
    "Comment Category Matrix",
    "Response Workflow",
    "Release Controls and Appendix Index",
]


def wrap_text(text, font_name, font_size, max_width):
    """Wrap a string to a pixel width using the active reportlab font."""
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


def draw_paragraph(
    c,
    text,
    x,
    y,
    max_width,
    font_name="Helvetica",
    font_size=9.2,
    leading=13.2,
    color=INK,
    max_lines=None,
):
    lines = wrap_text(text, font_name, font_size, max_width)
    if max_lines is not None:
        lines = lines[:max_lines]
    c.setFont(font_name, font_size)
    c.setFillColor(color)
    for line in lines:
        c.drawString(x, y, line)
        y -= leading
    return y


def draw_header(c, page_number):
    c.setFillColor(HEADER_BLUE)
    c.rect(0, 710, PAGE_W, 82, fill=1, stroke=0)
    c.setFillColor(ACCENT_AMBER)
    c.rect(0, 706, PAGE_W, 4, fill=1, stroke=0)

    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(52, 767, "PUBLIC HEARING RELEASE")
    c.setFont("Helvetica", 8)
    c.drawRightString(560, 767, "ZA-2026-041")

    c.setFont("Helvetica-Bold", 18 if page_number == 1 else 21)
    title_y = 733
    c.drawString(52, title_y, TITLES[page_number - 1])

    c.bookmarkPage(f"page-{page_number}", fit="Fit")
    c.addOutlineEntry(TITLES[page_number - 1], f"page-{page_number}", level=0)


def draw_footer(c, page_number):
    c.setStrokeColor(RULE)
    c.setLineWidth(0.7)
    c.line(52, 47, 560, 47)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 8)
    c.drawString(52, 29, "Public Hearing Release | ZA-2026-041 | 2026")
    c.drawRightString(560, 29, f"{page_number} / 5")


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


def draw_table(
    c,
    x,
    top,
    widths,
    header_height,
    rows,
    row_heights,
    aligns=None,
    total_row=False,
    font_sizes=None,
):
    aligns = aligns or ["left"] * len(widths)
    font_sizes = font_sizes or [8] * len(widths)

    # Header
    c.setFillColor(HEADER_BLUE)
    c.rect(x, top - header_height, sum(widths), header_height, fill=1, stroke=0)
    cursor_x = x
    for i, text in enumerate(rows[0]):
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 7.8)
        if aligns[i] == "center":
            c.drawCentredString(
                cursor_x + widths[i] / 2, top - header_height + 9, text
            )
        elif aligns[i] == "right":
            c.drawRightString(
                cursor_x + widths[i] - 8, top - header_height + 9, text
            )
        else:
            c.drawString(cursor_x + 8, top - header_height + 9, text)
        cursor_x += widths[i]

    # Body
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
            lines = wrap_text(
                text, font_name, font_size, widths[col_index] - 16
            )
            available_lines = max(1, int((height - 8) / (font_size + 2)))
            lines = lines[:available_lines]
            c.setFillColor(INK)
            c.setFont(font_name, font_size)
            text_y = y - 13
            for line in lines:
                if aligns[col_index] == "center":
                    c.drawCentredString(
                        cursor_x + widths[col_index] / 2, text_y, line
                    )
                elif aligns[col_index] == "right":
                    c.drawRightString(
                        cursor_x + widths[col_index] - 8, text_y, line
                    )
                else:
                    c.drawString(cursor_x + 8, text_y, line)
                text_y -= font_size + 2
            cursor_x += widths[col_index]
        y -= height
    return y


def page_one(c):
    draw_header(c, 1)
    draw_kicker(c, "Public release snapshot", 676)
    draw_status_box(
        c,
        "Public release status",
        "Clean public copy",
        "Corrected facts, page sequence, and publication controls verified.",
        52,
        607,
        508,
        54,
    )

    draw_fact_card(
        c, 52, 519, 248, "Hearing date", "2026-03-14", "Public hearing record"
    )
    draw_fact_card(
        c,
        312,
        519,
        248,
        "Public comments",
        "128",
        "Deduplicated submissions",
    )
    draw_fact_card(
        c,
        52,
        435,
        248,
        "Response deadline",
        "2026-09-15",
        "Public response date",
    )
    draw_fact_card(
        c,
        312,
        435,
        248,
        "Public contact",
        "Public Hearing Desk",
        "Consolidated public channel",
    )

    draw_section_heading(c, "Packet contents", 401)
    draw_content_item(c, 52, 342, "01", "Corrected Hearing Summary", 2)
    draw_content_item(c, 312, 342, "02", "Comment Category Matrix", 3)
    draw_content_item(c, 52, 286, "03", "Response Workflow", 4)
    draw_content_item(
        c, 312, 286, "04", "Release Controls and Appendix Index", 5
    )

    c.setFillColor(BLUE_PANEL)
    c.roundRect(52, 178, 508, 82, 7, fill=1, stroke=0)
    c.setFillColor(HEADER_BLUE)
    c.setFont("Helvetica-Bold", 7.7)
    c.drawString(70, 239, "PUBLICATION NOTE")
    draw_paragraph(
        c,
        "Use this packet as the public reference for ZA-2026-041. "
        "Category figures apply to the 128 deduplicated comments documented "
        "in the public record.",
        70,
        221,
        470,
        font_size=9.2,
        leading=14,
        max_lines=3,
    )
    draw_footer(c, 1)


def page_two(c):
    draw_header(c, 2)
    draw_kicker(c, "Corrected public record", 676)
    draw_section_heading(c, "Final public record", 647)
    draw_paragraph(
        c,
        "The public hearing record for ZA-2026-041 is consolidated below. "
        "The corrected date, deduplicated comment total, response deadline, "
        "and public contact are used consistently throughout this packet.",
        52,
        626,
        508,
        font_size=9.3,
        leading=14,
        max_lines=3,
    )

    draw_status_box(
        c,
        "Correction applied",
        "Final public facts",
        "All summary values match the corrected public hearing record.",
        52,
        543,
        508,
        54,
    )

    draw_section_heading(c, "Corrected facts", 508)
    table_rows = [
        ["Record element", "Final public value"],
        ["Hearing date", "2026-03-14"],
        ["Docket ID", "ZA-2026-041"],
        ["Public comment count", "128 deduplicated comments"],
        ["Response deadline", "2026-09-15"],
        ["Public contact", "Public Hearing Desk"],
    ]
    table_bottom = draw_table(
        c,
        52,
        486,
        [168, 340],
        27,
        table_rows,
        [31] * 5,
        aligns=["left", "left"],
        font_sizes=[8.3, 8.3],
    )

    draw_section_heading(c, "Public feedback profile", table_bottom - 31)
    draw_paragraph(
        c,
        "Each of the 128 comments is assigned to one primary category. "
        "Land use and density is the largest group (35; 27.3%), followed by "
        "transportation and access (28; 21.9%). Housing supply accounts for "
        "21 comments, while environment and stormwater accounts for 18.",
        52,
        table_bottom - 53,
        508,
        font_size=9.1,
        leading=14,
        max_lines=4,
    )
    draw_paragraph(
        c,
        "Infrastructure and services contributes 15 comments and process and "
        "notification contributes 11. The complete category distribution, "
        "public response focus, and follow-up lane appear on page 3.",
        52,
        table_bottom - 108,
        508,
        font_size=9.1,
        leading=14,
        max_lines=3,
    )

    c.setFillColor(AMBER_PANEL)
    c.roundRect(52, 112, 508, 58, 7, fill=1, stroke=0)
    c.setFillColor(ACCENT_AMBER)
    c.rect(52, 112, 5, 58, fill=1, stroke=0)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(70, 151, "Record reading")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 8.5)
    c.drawString(
        70, 135, "Counts describe the deduplicated public comment set."
    )
    c.drawString(
        70, 121, "Percentages are rounded to one decimal place."
    )
    draw_footer(c, 2)


def page_three(c):
    draw_header(c, 3)
    draw_kicker(c, "Comment record", 676)
    draw_paragraph(
        c,
        "The matrix assigns the 128 comments to six primary categories and "
        "identifies the public issue focus and follow-up lane for each group.",
        52,
        653,
        508,
        font_size=9.3,
        leading=14,
        max_lines=2,
    )

    table_rows = [
        ["Category", "Comments", "Share", "Public response focus", "Follow-up lane"],
        [
            "Land use and density",
            "35",
            "27.3%",
            "Building form, height, and site transitions",
            "Planning review",
        ],
        [
            "Transportation and access",
            "28",
            "21.9%",
            "Access, parking, circulation, and transit",
            "Mobility review",
        ],
        [
            "Housing supply",
            "21",
            "16.4%",
            "Housing type, supply, and affordability",
            "Housing review",
        ],
        [
            "Environment and stormwater",
            "18",
            "14.1%",
            "Stormwater, tree canopy, and site impacts",
            "Environmental review",
        ],
        [
            "Infrastructure and services",
            "15",
            "11.7%",
            "Utilities, schools, and community services",
            "Infrastructure review",
        ],
        [
            "Process and notification",
            "11",
            "8.6%",
            "Notice, meeting access, and comment submission",
            "Public engagement",
        ],
        ["Total", "128", "100.0%", "Deduplicated public comment set", ""],
    ]
    table_bottom = draw_table(
        c,
        52,
        606,
        [150, 58, 52, 138, 110],
        29,
        table_rows,
        [44, 44, 44, 44, 44, 44, 34],
        aligns=["left", "center", "center", "left", "left"],
        total_row=True,
        font_sizes=[8.2, 8.1, 8.1, 7.6, 7.6],
    )

    c.setFillColor(BLUE_PANEL)
    c.roundRect(52, table_bottom - 67, 508, 49, 7, fill=1, stroke=0)
    c.setFillColor(HEADER_BLUE)
    c.setFont("Helvetica-Bold", 8.2)
    c.drawString(70, table_bottom - 35, "MATRIX NOTE")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 8.1)
    c.drawString(
        70,
        table_bottom - 50,
        "Each submission is assigned once by its primary issue. Percentages may not add due to rounding.",
    )
    draw_footer(c, 3)


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


def page_four(c):
    draw_header(c, 4)
    draw_kicker(c, "Public response process", 676)
    draw_paragraph(
        c,
        "The response workflow keeps every public comment traceable from "
        "intake through the published follow-up.",
        52,
        653,
        508,
        font_size=9.3,
        leading=14,
        max_lines=2,
    )
    draw_status_box(
        c,
        "Public response deadline",
        "2026-09-15",
        "Final public update target for ZA-2026-041.",
        52,
        575,
        508,
        52,
    )
    draw_section_heading(c, "Five-step public workflow", 548)

    c.setStrokeColor(RULE)
    c.setLineWidth(2)
    c.line(72, 505, 72, 258)

    steps = [
        (
            "01",
            "Comment intake",
            "Log each submission under ZA-2026-041 with a receipt reference.",
            False,
        ),
        (
            "02",
            "Category assignment",
            "Assign one primary category from the public matrix on page 3.",
            False,
        ),
        (
            "03",
            "Issue review",
            "Route the issue to the relevant review lane for a factual response.",
            False,
        ),
        (
            "04",
            "Public update",
            "Publish a consolidated response through the public hearing channel.",
            True,
        ),
        (
            "05",
            "Record close",
            "Index the final response package and confirm the public deadline.",
            False,
        ),
    ]
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
    c.drawString(70, 149, "Public Hearing Desk")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 8.2)
    c.drawString(
        260, 169, "Use the docket ID for all written follow-up: ZA-2026-041."
    )
    c.drawString(
        260, 149, "The public response deadline is 2026-09-15."
    )
    draw_footer(c, 4)


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


def page_five(c):
    draw_header(c, 5)
    draw_kicker(c, "Release record", 676)
    draw_paragraph(
        c,
        "Publication controls are listed below with the appendix index for "
        "this five-page public release.",
        52,
        653,
        508,
        font_size=9.3,
        leading=14,
        max_lines=2,
    )
    draw_status_box(
        c,
        "Public release status",
        "Release ready",
        "Required package controls verified.",
        52,
        575,
        508,
        52,
    )

    draw_section_heading(c, "Release controls", 540)
    controls = [
        "No active form fields",
        "No annotations or attachments",
        "No script actions",
        "Public-only metadata",
        "Five-page sequence verified",
        "Outline and page numbers verified",
        "Restricted identifiers excluded",
        "Public contact consolidated",
    ]
    y_positions = [493, 457, 421, 385]
    for row, y in enumerate(y_positions):
        draw_control_item(c, 52, y, 248, controls[row * 2])
        draw_control_item(c, 312, y, 248, controls[row * 2 + 1])

    draw_section_heading(c, "Appendix index", 359)
    appendix_rows = [
        ["Index", "Public packet section", "Page"],
        ["A", "Hearing particulars", "2"],
        ["B", "Comment category matrix", "3"],
        ["C", "Response workflow", "4"],
        ["D", "Release record", "5"],
    ]
    table_bottom = draw_table(
        c,
        52,
        337,
        [72, 336, 100],
        27,
        appendix_rows,
        [31, 31, 31, 31],
        aligns=["center", "left", "center"],
        font_sizes=[8.2, 8.2, 8.2],
    )

    doc_y = table_bottom - 60
    c.setFillColor(PANEL)
    c.roundRect(52, doc_y, 508, 48, 6, fill=1, stroke=0)
    control_data = [
        ("FORMAT", "PDF"),
        ("PAGES", "5"),
        ("DOCKET", "ZA-2026-041"),
        ("CONTACT", "Public Hearing Desk"),
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

    draw_footer(c, 5)


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(
        str(OUTPUT),
        pagesize=LETTER,
        pageCompression=1,
        invariant=1,
    )
    c.setTitle(TITLES[0])
    c.setAuthor("Public Hearing Desk")
    c.setSubject("Clean flattened public release packet")
    c.setKeywords("zoning; public hearing; ZA-2026-041")
    c.setCreator("Public Hearing Desk")
    c.setProducer("Public Hearing Desk Publishing")

    for build_page in (page_one, page_two, page_three, page_four, page_five):
        build_page(c)
        c.showPage()
    c.save()
    print(OUTPUT)


if __name__ == "__main__":
    main()
