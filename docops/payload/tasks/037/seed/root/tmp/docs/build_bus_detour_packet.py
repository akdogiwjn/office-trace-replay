#!/usr/bin/env python3
"""Build the corrected Route 12 public bus detour notice packet."""

from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import letter, landscape
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


OUTPUT = Path(
    "/root/submission/"
    "docops_v2_l3_037_pdf_bus_detour_notice_layout_repair_output.pdf"
)
WORK = Path("/root/tmp/docs")

NAVY = HexColor("#0B2D4D")
BLUE = HexColor("#0D5C8C")
TEAL = HexColor("#0F7C7A")
GOLD = HexColor("#F2B544")
MIST = HexColor("#EAF2F6")
PALE = HexColor("#F7F9FA")
INK = HexColor("#152734")
SLATE = HexColor("#536773")
LINE = HexColor("#C9D6DD")
CORAL = HexColor("#C95C47")
WHITE = white

PAGE_TITLES = [
    "Public Bus Detour Notice Packet",
    "Corrected Detour Summary",
    "Stop Closure and Shuttle Matrix",
    "Rider Communication Timeline",
    "Release Checklist",
]


def set_fill(c, color):
    c.setFillColor(color)


def set_stroke(c, color):
    c.setStrokeColor(color)


def draw_text(c, text, x, y, font="Helvetica", size=10, color=INK):
    c.setFont(font, size)
    set_fill(c, color)
    c.drawString(x, y, text)


def draw_text_right(c, text, x, y, font="Helvetica", size=10, color=INK):
    c.setFont(font, size)
    set_fill(c, color)
    c.drawRightString(x, y, text)


def draw_text_center(c, text, x, y, font="Helvetica", size=10, color=INK):
    c.setFont(font, size)
    set_fill(c, color)
    c.drawCentredString(x, y, text)


def wrap_lines(text, width, font, size):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if stringWidth(candidate, font, size) <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_wrapped(c, text, x, top_y, width, font="Helvetica", size=10,
                 leading=13, color=INK, max_lines=None):
    lines = wrap_lines(text, width, font, size)
    if max_lines is not None:
        lines = lines[:max_lines]
    y = top_y
    for line in lines:
        draw_text(c, line, x, y, font, size, color)
        y -= leading
    return y


def draw_rule(c, x1, y1, x2, y2, color=LINE, width=1):
    set_stroke(c, color)
    c.setLineWidth(width)
    c.line(x1, y1, x2, y2)


def draw_card(c, x, y, w, h, fill=PALE, border=LINE, radius=5):
    set_fill(c, fill)
    set_stroke(c, border)
    c.setLineWidth(0.7)
    c.roundRect(x, y, w, h, radius, stroke=1, fill=1)


def draw_accent_card(c, x, y, w, h, accent=TEAL):
    draw_card(c, x, y, w, h)
    set_fill(c, accent)
    c.rect(x, y + h - 4, w, 4, stroke=0, fill=1)


def draw_bullet(c, text, x, top_y, width, color=INK):
    set_fill(c, TEAL)
    c.circle(x + 3, top_y + 3, 2.4, stroke=0, fill=1)
    return draw_wrapped(c, text, x + 15, top_y, width - 15, size=9.7,
                        leading=13, color=color)


def draw_check(c, x, y, size=18, color=TEAL):
    set_stroke(c, color)
    c.setLineWidth(1.5)
    c.roundRect(x, y, size, size, 3, stroke=1, fill=0)
    c.setLineWidth(2)
    c.line(x + 4, y + 9, x + 8, y + 5)
    c.line(x + 8, y + 5, x + 15, y + 14)


def draw_footer(c, page_number, width):
    draw_rule(c, 36 if width > 700 else 42, 42,
              width - (36 if width > 700 else 42), 42, LINE, 0.7)
    y = 27
    draw_text(c, "ROUTE 12  |  BRIDGE DETOUR", 36 if width > 700 else 42, y,
              "Helvetica-Bold", 7.2, SLATE)
    draw_text_center(c, "Public information  |  311 Transit Desk", width / 2,
                     y, "Helvetica", 7.2, SLATE)
    draw_text_right(c, f"PAGE {page_number} OF 5",
                    width - (36 if width > 700 else 42), y,
                    "Helvetica-Bold", 7.2, SLATE)


def draw_standard_header(c, page_number, title, subtitle, width, height):
    set_fill(c, NAVY)
    c.rect(0, height - 14, width, 14, stroke=0, fill=1)

    draw_text(c, "PUBLIC TRANSIT SERVICE NOTICE  |  ROUTE 12", 42,
              height - 47, "Helvetica-Bold", 8.2, TEAL)
    draw_text(c, title, 42, height - 89, "Helvetica-Bold", 28, NAVY)
    draw_text(c, subtitle, 42, height - 111, "Helvetica", 10.2, SLATE)
    draw_rule(c, 42, height - 127, width - 42, height - 127, LINE, 1)

    # Compact route tag at upper right.
    tag_w, tag_h = 86, 46
    tag_x, tag_y = width - 42 - tag_w, height - 91
    set_fill(c, BLUE)
    c.roundRect(tag_x, tag_y, tag_w, tag_h, 4, stroke=0, fill=1)
    draw_text_center(c, "ROUTE", tag_x + tag_w / 2, tag_y + 28,
                     "Helvetica-Bold", 7.2, WHITE)
    draw_text_center(c, "12", tag_x + tag_w / 2, tag_y + 11,
                     "Helvetica-Bold", 18, WHITE)


def draw_cover(c):
    width, height = letter
    set_fill(c, NAVY)
    c.rect(0, height - 135, width, 135, stroke=0, fill=1)
    set_fill(c, TEAL)
    c.rect(0, height - 139, width, 4, stroke=0, fill=1)

    draw_text(c, "PUBLIC TRANSIT SERVICE NOTICE", 42, height - 36,
              "Helvetica-Bold", 8.5, HexColor("#A9D6D2"))
    draw_text(c, "Public Bus Detour", 42, height - 77,
              "Helvetica-Bold", 30, WHITE)
    draw_text(c, "Notice Packet", 42, height - 107,
              "Helvetica-Bold", 30, WHITE)
    draw_text(c, "Route 12  |  Bridge closure and replacement shuttle",
              42, height - 126, "Helvetica", 10.5, HexColor("#D8E7EF"))

    draw_text(c, "A five-page public packet for riders, stations, and"
              " customer information teams.", 42, 629,
              "Helvetica", 10.2, SLATE)

    draw_text(c, "SERVICE AT A GLANCE", 42, 594,
              "Helvetica-Bold", 8.4, TEAL)
    card_w, gap = 168, 12
    xs = [42, 42 + card_w + gap, 42 + 2 * (card_w + gap)]
    row_one_y, row_two_y, card_h = 514, 422, 78

    facts = [
        ("OFFICIAL ROUTE", "Route 12", BLUE),
        ("CLOSURE BEGINS", "2026-10-03", TEAL),
        ("REOPENING TARGET", "2026-10-17", BLUE),
        ("CLOSED STOPS", "9", TEAL),
        ("SHUTTLE HEADWAY", "15 minutes", BLUE),
        ("PUBLIC CONTACT", "311 Transit Desk", TEAL),
    ]

    for index, (label, value, accent) in enumerate(facts):
        row_y = row_one_y if index < 3 else row_two_y
        x = xs[index % 3]
        draw_accent_card(c, x, row_y, card_w, card_h, accent)
        draw_text(c, label, x + 13, row_y + 56, "Helvetica-Bold", 7.2, SLATE)
        value_size = 15 if label not in ("INTERNAL NOTE",) else 12
        if label == "PUBLIC CONTACT":
            value_size = 12
        draw_text(c, value, x + 13, row_y + 27, "Helvetica-Bold",
                  value_size, NAVY)

    draw_text(c, "RIDER GUIDANCE", 42, 390,
              "Helvetica-Bold", 8.4, TEAL)
    draw_card(c, 42, 194, 528, 182, WHITE, LINE)
    set_fill(c, MIST)
    c.roundRect(56, 326, 500, 36, 3, stroke=0, fill=1)
    draw_text(c, "Plan ahead and use the signed replacement shuttle.",
              70, 338, "Helvetica-Bold", 12.2, NAVY)
    guidance = [
        "Follow the posted detour signs and allow additional travel time.",
        "Replacement shuttles serve the closed-stop corridor every 15 minutes.",
        "Board at a marked shuttle location shown in the page 3 matrix.",
        "Contact 311 Transit Desk for trip planning or accessibility help.",
    ]
    y = 307
    for item in guidance:
        y = draw_bullet(c, item, 62, y, 484) - 7

    draw_card(c, 42, 113, 528, 63, MIST, LINE)
    draw_text(c, "INSIDE THIS PACKET", 57, 153,
              "Helvetica-Bold", 7.3, TEAL)
    draw_text(c, "2 Summary   |   3 Stop and shuttle matrix   |   "
              "4 Rider timeline   |   5 Release checklist",
              57, 132, "Helvetica", 8.7, NAVY)
    draw_footer(c, 1, width)


def draw_summary(c):
    width, height = letter
    draw_standard_header(
        c,
        2,
        "Corrected Detour Summary",
        "The public service facts for the Route 12 bridge detour",
        width,
        height,
    )

    draw_text(c, "This packet reflects the corrected public service details"
              " for riders and customer information teams.",
              42, 648, "Helvetica", 9.8, SLATE)

    draw_card(c, 42, 605, 528, 34, MIST, LINE)
    set_fill(c, TEAL)
    c.rect(42, 605, 5, 34, stroke=0, fill=1)
    draw_text(c, "Use the values in this summary as the source for all"
              " rider-facing notices.", 58, 617,
              "Helvetica-Bold", 9.5, NAVY)

    draw_text(c, "CORRECTED SERVICE DETAILS", 42, 582,
              "Helvetica-Bold", 8.4, TEAL)

    table_x, table_top = 42, 553
    col_w = [156, 372]
    header_h, row_h = 27, 27
    rows = [
        ("Official route", "Route 12"),
        ("Bridge closure begins", "2026-10-03"),
        ("Reopening target", "2026-10-17 (target date)"),
        ("Closed stops", "9"),
        ("Replacement shuttle", "Every 15 minutes"),
        ("Public contact", "311 Transit Desk"),
    ]

    set_fill(c, NAVY)
    c.rect(table_x, table_top - header_h, sum(col_w), header_h,
           stroke=0, fill=1)
    draw_text(c, "SERVICE DETAIL", table_x + 10, table_top - 18,
              "Helvetica-Bold", 7.6, WHITE)
    draw_text(c, "CORRECTED PUBLIC INFORMATION", table_x + col_w[0] + 10,
              table_top - 18, "Helvetica-Bold", 7.6, WHITE)

    y = table_top - header_h
    for index, (label, value) in enumerate(rows):
        y -= row_h
        set_fill(c, WHITE if index % 2 == 0 else PALE)
        c.rect(table_x, y, sum(col_w), row_h, stroke=0, fill=1)
        draw_rule(c, table_x, y, table_x + sum(col_w), y, LINE, 0.55)
        draw_text(c, label, table_x + 10, y + 9,
                  "Helvetica-Bold", 8.7, NAVY)
        draw_text(c, value, table_x + col_w[0] + 10, y + 9,
                  "Helvetica-Bold", 9.1, INK)

    set_stroke(c, LINE)
    c.setLineWidth(0.7)
    c.rect(table_x, y, sum(col_w), table_top - y, stroke=1, fill=0)
    c.line(table_x + col_w[0], y, table_x + col_w[0], table_top)

    draw_text(c, "TRAVEL GUIDANCE", 42, 343,
              "Helvetica-Bold", 8.4, TEAL)
    card_w, gap = 168, 12
    xs = [42, 222, 402]
    cards = [
        ("PLAN AHEAD", "Allow additional travel time and follow the signed"
         " detour route.", BLUE),
        ("USE THE SHUTTLE", "Replacement shuttles serve closed stop areas"
         " every 15 minutes.", TEAL),
        ("GET HELP", "Contact 311 Transit Desk for trip planning and"
         " accessibility support.", GOLD),
    ]
    for x, (label, body, accent) in zip(xs, cards):
        draw_accent_card(c, x, 220, card_w, 103, accent)
        draw_text(c, label, x + 14, 299, "Helvetica-Bold", 7.5, accent)
        draw_wrapped(c, body, x + 14, 277, card_w - 28,
                     "Helvetica", 9.2, 12.7, INK)

    draw_card(c, 42, 132, 528, 65, MIST, LINE)
    draw_text(c, "ACCESSIBLE BOARDING", 57, 176,
              "Helvetica-Bold", 7.6, TEAL)
    draw_wrapped(c, "The shuttle boarding points in the page 3 matrix are"
                 " step-free. Ask 311 Transit Desk for assistance before"
                 " travel if needed.",
                 57, 156, 496, "Helvetica", 9.1, 12.4, INK)
    draw_footer(c, 2, width)


def draw_matrix(c):
    width, height = landscape(letter)
    draw_standard_header(
        c,
        3,
        "Stop Closure and Shuttle Matrix",
        "Nine closed Route 12 stops and their signed replacement-shuttle"
        " boarding points",
        width,
        height,
    )

    rows = [
        ("12-01", "Northbank / Library", "Northbank Ave and Harbor St",
         "Northbank Ave - south curb", "Step-free"),
        ("12-02", "Market Square / 4th Ave", "Market St at 4th Ave",
         "Market Square - west entrance", "Step-free"),
        ("12-03", "Civic Center / East Gate", "Civic Center east entrance",
         "East Gate - signed shuttle bay", "Step-free"),
        ("12-04", "Riverfront / Pier Loop", "Riverfront promenade",
         "Riverfront promenade - signed bay", "Step-free"),
        ("12-05", "Harbor Exchange / Bay St", "Bay St at Harbor Exchange",
         "Bay St - north curb", "Step-free"),
        ("12-06", "Central Station / North Plaza", "Central Station north side",
         "North Plaza - shuttle bay B", "Step-free"),
        ("12-07", "University / West Gate", "University west entrance",
         "West Gate - signed shuttle bay", "Step-free"),
        ("12-08", "Parkway / Medical Campus", "Medical Campus main entrance",
         "Medical Campus - main curb", "Step-free"),
        ("12-09", "Southbank / Terminal", "Southbank transit terminal",
         "Terminal - shuttle bay 3", "Step-free"),
    ]

    draw_text(c, "CLOSED STOP  |  BOARDING POINT", 36, 480,
              "Helvetica-Bold", 8.4, TEAL)

    x = 36
    top = 456
    widths = [65, 160, 174, 221, 100]
    headers = [
        "STOP ID",
        "CLOSED STOP",
        "LOCATION CONTEXT",
        "SHUTTLE BOARDING POINT",
        "ACCESS",
    ]
    header_h, row_h = 27, 25
    set_fill(c, NAVY)
    c.rect(x, top - header_h, sum(widths), header_h, stroke=0, fill=1)
    cursor = x
    for label, col_width in zip(headers, widths):
        draw_text(c, label, cursor + 7, top - 18,
                  "Helvetica-Bold", 7.3, WHITE)
        cursor += col_width

    y = top - header_h
    for index, row in enumerate(rows):
        y -= row_h
        set_fill(c, WHITE if index % 2 == 0 else PALE)
        c.rect(x, y, sum(widths), row_h, stroke=0, fill=1)
        draw_rule(c, x, y, x + sum(widths), y, LINE, 0.5)
        cursor = x
        for value, col_width in zip(row, widths):
            font = "Helvetica-Bold" if col_width in (65, 100) else "Helvetica"
            color = NAVY if col_width == 65 else INK
            if col_width == 100:
                color = TEAL
            draw_text(c, value, cursor + 7, y + 8, font, 8.0, color)
            cursor += col_width

    set_stroke(c, LINE)
    c.setLineWidth(0.7)
    c.rect(x, y, sum(widths), top - y, stroke=1, fill=0)
    cursor = x
    for col_width in widths[:-1]:
        cursor += col_width
        c.line(cursor, y, cursor, top)

    draw_card(c, 36, 112, 720, 67, MIST, LINE)
    set_fill(c, TEAL)
    c.rect(36, 112, 5, 67, stroke=0, fill=1)
    draw_text(c, "BOARD AT THE SIGNED LOCATION", 54, 158,
              "Helvetica-Bold", 8.1, TEAL)
    draw_wrapped(c, "Replacement shuttles run every 15 minutes. Follow"
                 " station and curbside signs to the nearest marked boarding"
                 " point. Contact 311 Transit Desk for trip planning or"
                 " accessibility assistance.",
                 54, 139, 678, "Helvetica", 9.0, 12.2, INK)
    draw_footer(c, 3, width)


def draw_timeline(c):
    width, height = letter
    draw_standard_header(
        c,
        4,
        "Rider Communication Timeline",
        "Consistent updates from advance notice through the reopening target",
        width,
        height,
    )

    draw_wrapped(c, "Riders will see the same route, dates, closed-stop count,"
                 " shuttle frequency, and contact across every channel.",
                 42, 648, 528, "Helvetica", 9.8, 13.2, SLATE)

    draw_text(c, "PUBLIC INFORMATION STAGES", 42, 630,
              "Helvetica-Bold", 8.4, TEAL)

    stages = [
        ("2026-09-26", "Advance notice",
         "Post stop notices and publish digital travel guidance."),
        ("2026-10-03", "Closure begins",
         "Detour signs active; replacement shuttles run every 15 minutes."),
        ("2026-10-10", "Mid-window check",
         "Confirm stop conditions and refresh rider-facing service details."),
        ("2026-10-17", "Reopening target",
         "Restore regular routing when bridge work is cleared and confirmed."),
    ]

    line_x = 145
    centers = [586, 505, 424, 343]
    draw_rule(c, line_x, centers[-1], line_x, centers[0], BLUE, 2)

    for index, ((date, label, body), center_y) in enumerate(zip(stages,
                                                               centers)):
        accent = TEAL if index in (0, 2) else BLUE
        draw_card(c, 42, center_y - 25, 91, 50, MIST, LINE)
        draw_text_center(c, date, 87.5, center_y + 4,
                         "Helvetica-Bold", 8.3, NAVY)
        set_fill(c, accent)
        c.circle(line_x, center_y, 6, stroke=0, fill=1)
        set_fill(c, WHITE)
        c.circle(line_x, center_y, 2.1, stroke=0, fill=1)

        draw_card(c, 166, center_y - 31, 404, 62, WHITE, LINE)
        draw_text(c, label, 180, center_y + 14,
                  "Helvetica-Bold", 10.0, NAVY)
        draw_wrapped(c, body, 180, center_y - 2, 374,
                     "Helvetica", 8.5, 11.5, INK)

    draw_text(c, "RIDER TOUCHPOINTS", 42, 291,
              "Helvetica-Bold", 8.4, TEAL)
    card_w, gap = 168, 12
    xs = [42, 222, 402]
    touchpoints = [
        ("AT CLOSED STOPS", "Closure notice and shuttle boarding sign", TEAL),
        ("ON BOARD", "Detour and replacement-service announcements", BLUE),
        ("DIGITAL ALERTS", "Current rider-facing service information", TEAL),
    ]
    for x, (label, body, accent) in zip(xs, touchpoints):
        draw_accent_card(c, x, 202, card_w, 75, accent)
        draw_text(c, label, x + 13, 255, "Helvetica-Bold", 7.4, accent)
        draw_wrapped(c, body, x + 13, 237, card_w - 26,
                     "Helvetica", 8.9, 11.7, INK)

    draw_card(c, 42, 122, 528, 66, MIST, LINE)
    draw_text(c, "SERVICE UPDATES", 57, 165,
              "Helvetica-Bold", 7.6, TEAL)
    draw_wrapped(c, "The reopening date is a target. For current service,"
                 " boarding help, or accessibility assistance, contact"
                 " 311 Transit Desk.",
                 57, 145, 496, "Helvetica", 9.1, 12.4, INK)
    draw_footer(c, 4, width)


def draw_checklist(c):
    width, height = letter
    draw_standard_header(
        c,
        5,
        "Release Checklist",
        "Final public-information checks before distribution",
        width,
        height,
    )

    draw_wrapped(c, "Confirm the five-page packet is complete, internally"
                 " consistent, and ready for rider-facing channels.",
                 42, 648, 528, "Helvetica", 9.8, 13.2, SLATE)

    draw_text(c, "FINAL ISSUE CHECKS", 42, 615,
              "Helvetica-Bold", 8.4, TEAL)
    checks = [
        ("SERVICE FACTS", "Route 12, the closure window, 9 closed stops,"
         " and 15-minute shuttle headway match the corrected notice."),
        ("STOP MATRIX", "All 9 closed stops and their signed shuttle boarding"
         " points are shown on the landscape matrix."),
        ("RIDER GUIDANCE", "Detour instructions, travel-time guidance, and"
         " the rider communication timeline are published."),
        ("ACCESSIBILITY", "Step-free boarding and 311 Transit Desk assistance"
         " are clearly stated for riders."),
        ("SIGNAGE AND ALERTS", "Stop notices, boarding signs, onboard messages,"
         " and digital alerts are scheduled."),
        ("PUBLIC CONTACT", "Every public-facing route to assistance points to"
         " 311 Transit Desk."),
    ]

    row_y = 558
    for label, body in checks:
        draw_card(c, 42, row_y, 528, 47, WHITE, LINE)
        draw_check(c, 56, row_y + 14, 18, TEAL)
        draw_text(c, label, 88, row_y + 28,
                  "Helvetica-Bold", 7.6, TEAL)
        draw_wrapped(c, body, 88, row_y + 16, 464,
                     "Helvetica", 8.6, 11.0, INK, max_lines=2)
        row_y -= 56

    draw_text(c, "RELEASE OWNERS", 42, 235,
              "Helvetica-Bold", 8.4, TEAL)
    card_w, gap = 168, 12
    xs = [42, 222, 402]
    owners = [
        ("OPERATIONS", "Service and shuttle readiness", BLUE),
        ("CUSTOMER INFORMATION", "Rider channels and stop materials", TEAL),
        ("TRANSIT COMMUNICATIONS", "Final packet and public contact", GOLD),
    ]
    for x, (label, body, accent) in zip(xs, owners):
        draw_accent_card(c, x, 143, card_w, 77, accent)
        draw_text(c, label, x + 13, 196, "Helvetica-Bold", 7.2, accent)
        draw_wrapped(c, body, x + 13, 177, card_w - 26,
                     "Helvetica", 8.8, 11.5, INK)

    draw_card(c, 42, 101, 528, 31, MIST, LINE)
    draw_text_center(c, "PUBLIC BUS DETOUR NOTICE PACKET  |  ROUTE 12  |"
                     "  5 PAGES", width / 2, 112,
                     "Helvetica-Bold", 8.0, NAVY)
    draw_footer(c, 5, width)


def build_reportlab_pdf(path):
    c = canvas.Canvas(str(path), pagesize=letter, pageCompression=1)
    draw_cover(c)
    c.showPage()

    c.setPageSize(letter)
    draw_summary(c)
    c.showPage()

    c.setPageSize(landscape(letter))
    draw_matrix(c)
    c.showPage()

    c.setPageSize(letter)
    draw_timeline(c)
    c.showPage()

    c.setPageSize(letter)
    draw_checklist(c)
    c.showPage()
    c.save()


def finalize_pdf(source_path, output_path):
    reader = PdfReader(str(source_path))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)

    writer.add_metadata(
        {
            "/Title": "Public Bus Detour Notice Packet",
            "/Author": "Transit Communications",
            "/Subject": "Route 12 bridge detour, shuttle service, and rider"
            " communication packet",
            "/Keywords": "Route 12, bridge detour, shuttle, rider notice,"
            " public transit",
            "/Creator": "Transit Communications",
            "/Producer": "ReportLab",
        }
    )

    for index, title in enumerate(PAGE_TITLES):
        writer.add_outline_item(title, index)

    writer._root_object.update(
        {NameObject("/PageMode"): NameObject("/UseOutlines")}
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as handle:
        writer.write(handle)


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    raw_pdf = WORK / "route12_public_notice_raw.pdf"
    build_reportlab_pdf(raw_pdf)
    finalize_pdf(raw_pdf, OUTPUT)
    print(OUTPUT)
    print(f"{OUTPUT.stat().st_size} bytes")


if __name__ == "__main__":
    main()
