from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Inches, Pt


OUTPUT = Path(
    "/root/submission/"
    "docops_v2_l3_021_pptx_shelter_accessibility_public_remediation_output.pptx"
)

SLIDE_W = 13.333
SLIDE_H = 7.5

COLORS = {
    "title_bg": "102A43",
    "content_bg": "F7FBFF",
    "title_text": "FFFFFF",
    "content_title": "102A43",
    "accent": "F59E0B",
    "blue": "0B5CAD",
    "blue_dark": "0A4E90",
    "blue_soft": "DCEAF8",
    "blue_pale": "EAF3FB",
    "navy": "102A43",
    "navy_mid": "1E405F",
    "body": "243B53",
    "muted": "52667A",
    "line": "B7C9DB",
    "ice": "D8E5F0",
    "route_pale": "CFE1F1",
    "footer_dark": "B8C9DA",
    "white": "FFFFFF",
    "green": "2C7A5B",
    "green_soft": "E7F4EE",
    "orange_soft": "FFF2D9",
}


def rgb(name: str) -> RGBColor:
    return RGBColor.from_string(COLORS.get(name, name))


def set_fill(shape, color: str | RGBColor, transparency: int = 0) -> None:
    shape.fill.solid()
    shape.fill.fore_color.rgb = color if isinstance(color, RGBColor) else rgb(color)
    if transparency:
        shape.fill.transparency = transparency


def set_line(shape, color: str | RGBColor | None, width: float = 1.0) -> None:
    if color is None:
        shape.line.fill.background()
        return
    shape.line.color.rgb = color if isinstance(color, RGBColor) else rgb(color)
    shape.line.width = Pt(width)


def set_alt_text(shape, description: str, title: str | None = None) -> None:
    c_nv_pr = shape._element.xpath(".//p:cNvPr")[0]
    c_nv_pr.set("descr", description)
    if title:
        c_nv_pr.set("title", title)


def add_rect(
    slide,
    x: float,
    y: float,
    w: float,
    h: float,
    fill: str | RGBColor,
    radius: bool = False,
    line: str | RGBColor | None = None,
    line_width: float = 1.0,
):
    kind = MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE
    shape = slide.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
    set_fill(shape, fill)
    set_line(shape, line, line_width)
    if radius:
        try:
            shape.adjustments[0] = 0.18
        except (IndexError, ValueError):
            pass
    return shape


def add_oval(
    slide,
    x: float,
    y: float,
    w: float,
    h: float,
    fill: str | RGBColor,
    line: str | RGBColor | None = None,
    line_width: float = 1.0,
):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(w), Inches(h)
    )
    set_fill(shape, fill)
    set_line(shape, line, line_width)
    return shape


def add_line(
    slide,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    color: str | RGBColor,
    width: float = 2.0,
):
    line = slide.shapes.add_connector(
        MSO_CONNECTOR.STRAIGHT,
        Inches(x1),
        Inches(y1),
        Inches(x2),
        Inches(y2),
    )
    line.line.color.rgb = color if isinstance(color, RGBColor) else rgb(color)
    line.line.width = Pt(width)
    return line


def add_text(
    slide,
    text: str,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    size: float = 16,
    color: str | RGBColor = "body",
    font: str = "Aptos",
    bold: bool = False,
    align: PP_ALIGN = PP_ALIGN.LEFT,
    valign: MSO_ANCHOR = MSO_ANCHOR.TOP,
    margins: float = 0.0,
    line_spacing: float = 1.08,
    paragraph_space_after: float = 0,
    name: str | None = None,
):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        box.name = name
    frame = box.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.margin_left = Inches(margins)
    frame.margin_right = Inches(margins)
    frame.margin_top = Inches(margins)
    frame.margin_bottom = Inches(margins)
    frame.vertical_anchor = valign
    paragraph = frame.paragraphs[0]
    paragraph.alignment = align
    paragraph.line_spacing = line_spacing
    paragraph.space_after = Pt(paragraph_space_after)
    run = paragraph.add_run()
    run.text = text
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color if isinstance(color, RGBColor) else rgb(color)
    return box


def add_rich_text(
    slide,
    runs: list[dict],
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    size: float = 16,
    font: str = "Aptos",
    valign: MSO_ANCHOR = MSO_ANCHOR.TOP,
    margins: float = 0.0,
    name: str | None = None,
):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        box.name = name
    frame = box.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.margin_left = Inches(margins)
    frame.margin_right = Inches(margins)
    frame.margin_top = Inches(margins)
    frame.margin_bottom = Inches(margins)
    frame.vertical_anchor = valign
    paragraph = frame.paragraphs[0]
    for item in runs:
        run = paragraph.add_run()
        run.text = item["text"]
        run.font.name = font
        run.font.size = Pt(item.get("size", size))
        run.font.bold = item.get("bold", False)
        run.font.italic = item.get("italic", False)
        run.font.color.rgb = (
            item["color"]
            if isinstance(item.get("color", "body"), RGBColor)
            else rgb(item.get("color", "body"))
        )
        if item.get("hyperlink"):
            run.hyperlink.address = item["hyperlink"]
    return box


def add_accent(slide) -> None:
    accent = add_rect(slide, 0, 0, 0.14, SLIDE_H, "accent")
    accent.name = "Orange accent rectangle"
    set_alt_text(
        accent,
        "Decorative orange accent bar.",
        "Decorative accent",
    )


def add_footer(slide, index: int, dark: bool = False) -> None:
    add_text(
        slide,
        "Public Shelter Accessibility Briefing | 2026",
        0.72,
        7.08,
        7.5,
        0.22,
        size=9,
        color="B8C9DA" if dark else "52667A",
        font="Aptos",
        valign=MSO_ANCHOR.MIDDLE,
        name="Public footer",
    )
    add_text(
        slide,
        f"{index} / 8",
        12.05,
        7.08,
        0.58,
        0.22,
        size=9,
        color="B8C9DA" if dark else "52667A",
        font="Aptos",
        align=PP_ALIGN.RIGHT,
        valign=MSO_ANCHOR.MIDDLE,
        name="Slide number",
    )


def add_title(slide, title: str, *, dark: bool = False) -> None:
    add_text(
        slide,
        title,
        0.72,
        0.38,
        12.0,
        0.72,
        size=34,
        color="title_text" if dark else "content_title",
        font="Aptos Display",
        bold=True,
        valign=MSO_ANCHOR.MIDDLE,
        name="Slide title",
    )


def add_eyebrow(slide, text: str, dark: bool = False) -> None:
    add_text(
        slide,
        text.upper(),
        0.74,
        0.19,
        5.8,
        0.2,
        size=10,
        color="accent" if dark else "blue",
        font="Aptos",
        bold=True,
        name="Section label",
    )


def set_slide_bg(slide, color: str) -> None:
    background = slide.background.fill
    background.solid()
    background.fore_color.rgb = rgb(color)


def add_icon_badge(
    slide,
    label: str,
    x: float,
    y: float,
    *,
    fill: str = "blue",
    text_color: str = "white",
    diameter: float = 0.52,
    size: float = 15,
):
    badge = add_oval(slide, x, y, diameter, diameter, fill)
    add_text(
        slide,
        label,
        x,
        y - 0.01,
        diameter,
        diameter,
        size=size,
        color=text_color,
        font="Aptos",
        bold=True,
        align=PP_ALIGN.CENTER,
        valign=MSO_ANCHOR.MIDDLE,
    )
    return badge


def set_cell_border(cell, color: str, width: float = 0.8) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    for edge_tag in ("a:lnL", "a:lnR", "a:lnT", "a:lnB"):
        ln = tc_pr.find(edge_tag, tc_pr.nsmap)
        if ln is None:
            ln = OxmlElement(edge_tag)
            tc_pr.append(ln)
        ln.set("w", str(int(width * 12700)))
        ln.set("cap", "flat")
        ln.set("cmpd", "sng")
        ln.set("algn", "ctr")
        solid_fill = OxmlElement("a:solidFill")
        srgb = OxmlElement("a:srgbClr")
        srgb.set("val", color)
        solid_fill.append(srgb)
        ln.append(solid_fill)
        dash = OxmlElement("a:prstDash")
        dash.set("val", "solid")
        ln.append(dash)


def style_table(
    table,
    *,
    header_fill: str = "blue",
    header_color: str = "white",
    body_fills: tuple[str, ...] = ("FFFFFF", "blue_pale"),
    font_size: float = 13,
    header_size: float = 12,
    column_widths: tuple[float, ...] | None = None,
) -> None:
    if column_widths:
        for index, width in enumerate(column_widths):
            table.columns[index].width = Inches(width)
    for row_index, row in enumerate(table.rows):
        for cell in row.cells:
            cell.margin_left = Inches(0.12)
            cell.margin_right = Inches(0.10)
            cell.margin_top = Inches(0.07)
            cell.margin_bottom = Inches(0.06)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            if row_index == 0:
                set_fill(cell, header_fill)
                set_cell_border(cell, "FFFFFF", 0.6)
            else:
                set_fill(cell, body_fills[(row_index - 1) % len(body_fills)])
                set_cell_border(cell, "B7C9DB", 0.6)
            for paragraph in cell.text_frame.paragraphs:
                paragraph.space_before = Pt(0)
                paragraph.space_after = Pt(0)
                for run in paragraph.runs:
                    run.font.name = "Aptos"
                    run.font.size = Pt(header_size if row_index == 0 else font_size)
                    run.font.bold = row_index == 0
                    run.font.color.rgb = (
                        rgb(header_color)
                        if row_index == 0
                        else rgb("body")
                    )


def set_notes(slide, text: str) -> None:
    frame = slide.notes_slide.notes_text_frame
    frame.text = text
    for paragraph in frame.paragraphs:
        for run in paragraph.runs:
            run.font.name = "Aptos"


def build() -> Presentation:
    presentation = Presentation()
    presentation.slide_width = Inches(SLIDE_W)
    presentation.slide_height = Inches(SLIDE_H)
    presentation.core_properties.title = "Emergency Shelter Public Briefing"
    presentation.core_properties.subject = (
        "Public emergency shelter accessibility information, updated 2026-07-20"
    )
    presentation.core_properties.author = "Public Shelter Communications"
    presentation.core_properties.comments = "Approved public briefing."
    presentation.core_properties.keywords = (
        "emergency shelter; accessibility; public briefing; 2026-07-20"
    )

    blank = presentation.slide_layouts[6]

    # Slide 1 — title.
    slide = presentation.slides.add_slide(blank)
    set_slide_bg(slide, "title_bg")
    add_accent(slide)
    add_eyebrow(slide, "Public emergency information", dark=True)
    add_text(
        slide,
        "Emergency Shelter\nPublic Briefing",
        0.74,
        0.78,
        6.35,
        1.65,
        size=39,
        color="title_text",
        font="Aptos Display",
        bold=True,
        line_spacing=0.94,
        name="Slide title",
    )
    add_text(
        slide,
        "Clear access information for residents using public emergency shelters.",
        0.78,
        2.72,
        5.5,
        0.9,
        size=18,
        color="D8E5F0",
        font="Aptos",
        line_spacing=1.08,
    )
    for x, number, label in (
        (0.78, "18", "public shelters"),
        (3.25, "14", "wheelchair accessible"),
    ):
        card = add_rect(slide, x, 4.18, 2.1, 1.45, "navy_mid", radius=True)
        card.name = "Public shelter statistic"
        add_text(
            slide,
            number,
            x + 0.18,
            4.33,
            1.72,
            0.58,
            size=31,
            color="accent",
            font="Aptos Display",
            bold=True,
            valign=MSO_ANCHOR.MIDDLE,
        )
        add_text(
            slide,
            label,
            x + 0.19,
            4.98,
            1.73,
            0.44,
            size=12,
            color="white",
            font="Aptos",
            bold=True,
            valign=MSO_ANCHOR.MIDDLE,
        )
    add_text(
        slide,
        "PUBLIC UPDATE  •  2026-07-20",
        0.79,
        6.28,
        4.3,
        0.3,
        size=11,
        color="B8C9DA",
        font="Aptos",
        bold=True,
        name="Public update date",
    )

    network = add_rect(slide, 7.1, 0.88, 5.48, 5.62, "navy_mid", radius=True)
    network.name = "Shelter network key visual"
    set_alt_text(
        network,
        "Shelter network diagram with 18 public shelter markers; 14 orange markers "
        "represent wheelchair-accessible shelters.",
        "Shelter network diagram",
    )
    add_text(
        slide,
        "SHELTER NETWORK",
        7.45,
        1.17,
        4.7,
        0.26,
        size=11,
        color="F59E0B",
        font="Aptos",
        bold=True,
    )
    add_text(
        slide,
        "18 public locations",
        7.45,
        1.52,
        4.6,
        0.62,
        size=24,
        color="white",
        font="Aptos Display",
        bold=True,
        valign=MSO_ANCHOR.MIDDLE,
    )
    for row in range(3):
        for col in range(6):
            marker_index = row * 6 + col
            accessible = marker_index < 14
            marker = add_oval(
                slide,
                7.52 + col * 0.73,
                2.54 + row * 0.67,
                0.38,
                0.38,
                "accent" if accessible else "navy_mid",
                "D8E5F0" if not accessible else None,
                1.2,
            )
            marker.name = (
                f"Wheelchair-accessible shelter marker {marker_index + 1}"
                if accessible
                else f"Public shelter marker {marker_index + 1}"
            )
    add_oval(slide, 7.48, 4.96, 0.2, 0.2, "accent")
    add_text(
        slide,
        "14 wheelchair-accessible",
        7.78,
        4.91,
        3.95,
        0.3,
        size=12,
        color="white",
        font="Aptos",
        bold=True,
        valign=MSO_ANCHOR.MIDDLE,
    )
    add_oval(slide, 7.48, 5.42, 0.2, 0.2, "navy_mid", "D8E5F0", 1.2)
    add_text(
        slide,
        "4 additional public locations",
        7.78,
        5.37,
        4.0,
        0.3,
        size=12,
        color="D8E5F0",
        font="Aptos",
        valign=MSO_ANCHOR.MIDDLE,
    )
    add_text(
        slide,
        "Use the public shelter finder for current hours and facility details.",
        7.45,
        5.92,
        4.62,
        0.42,
        size=10,
        color="B8C9DA",
        font="Aptos",
        line_spacing=1.05,
    )
    add_footer(slide, 1, dark=True)
    set_notes(
        slide,
        "This public briefing confirms 18 public shelters and 14 "
        "wheelchair-accessible shelters as of July 20, 2026.",
    )

    # Slide 2 — corrected network.
    slide = presentation.slides.add_slide(blank)
    set_slide_bg(slide, "content_bg")
    add_accent(slide)
    add_eyebrow(slide, "Verified public totals")
    add_title(slide, "Corrected Shelter Network")
    add_text(
        slide,
        "Public figures reflect the correction memo and supersede earlier versions.",
        0.75,
        1.16,
        6.15,
        0.52,
        size=14,
        color="muted",
        font="Aptos",
    )

    for x, number, label, note in (
        (0.76, "18", "Public shelters", "All public locations"),
        (3.27, "14", "Wheelchair accessible", "Verified accessible locations"),
    ):
        card = add_rect(slide, x, 1.86, 2.22, 1.54, "white", radius=True, line="line")
        card.name = "Corrected public statistic"
        add_text(
            slide,
            number,
            x + 0.18,
            2.02,
            0.88,
            0.62,
            size=31,
            color="blue",
            font="Aptos Display",
            bold=True,
            valign=MSO_ANCHOR.MIDDLE,
        )
        add_text(
            slide,
            label,
            x + 1.04,
            1.98,
            1.0,
            0.62,
            size=12,
            color="content_title",
            font="Aptos",
            bold=True,
            valign=MSO_ANCHOR.MIDDLE,
        )
        add_text(
            slide,
            note,
            x + 0.19,
            2.78,
            1.85,
            0.35,
            size=10,
            color="muted",
            font="Aptos",
            valign=MSO_ANCHOR.MIDDLE,
        )

    visual = add_rect(slide, 0.76, 3.77, 5.72, 2.28, "white", radius=True, line="line")
    visual.name = "Accessible shelter share key visual"
    set_alt_text(
        visual,
        "Accessibility bar showing 14 of 18 public shelters, or 78 percent, "
        "are wheelchair accessible.",
        "Accessible shelter share",
    )
    add_text(
        slide,
        "ACCESSIBLE SHARE",
        1.02,
        4.02,
        2.6,
        0.26,
        size=10,
        color="blue",
        font="Aptos",
        bold=True,
    )
    add_text(
        slide,
        "78%",
        1.02,
        4.31,
        2.25,
        0.63,
        size=30,
        color="content_title",
        font="Aptos Display",
        bold=True,
        valign=MSO_ANCHOR.MIDDLE,
    )
    add_text(
        slide,
        "14 of 18 shelters",
        3.14,
        4.35,
        2.9,
        0.42,
        size=13,
        color="muted",
        font="Aptos",
        valign=MSO_ANCHOR.MIDDLE,
    )
    add_rect(slide, 1.02, 5.18, 5.18, 0.33, "blue_soft", radius=True)
    add_rect(slide, 1.02, 5.18, 5.18 * (14 / 18), 0.33, "blue", radius=True)
    add_text(
        slide,
        "14 accessible",
        1.02,
        5.62,
        1.8,
        0.24,
        size=9,
        color="blue",
        font="Aptos",
        bold=True,
    )
    add_text(
        slide,
        "4 additional public shelters",
        4.34,
        5.62,
        2.02,
        0.24,
        size=9,
        color="muted",
        font="Aptos",
        align=PP_ALIGN.RIGHT,
    )

    table_shape = slide.shapes.add_table(
        4, 3, Inches(6.88), Inches(1.73), Inches(5.68), Inches(3.96)
    )
    table = table_shape.table
    data = [
        ("Public measure", "Figure", "Status"),
        ("Public shelters", "18", "Active"),
        ("Wheelchair accessible", "14", "Verified"),
        ("Accessible share", "78%", "Current"),
    ]
    for r, row in enumerate(data):
        for c, value in enumerate(row):
            table.cell(r, c).text = value
    style_table(
        table,
        column_widths=(2.35, 1.3, 1.65),
        font_size=13,
        header_size=11,
    )
    table_shape.name = "Corrected shelter network table"
    set_alt_text(
        table_shape,
        "Table of corrected public shelter figures: 18 public shelters, "
        "14 wheelchair accessible, and a 78 percent accessible share.",
        "Corrected shelter table",
    )
    add_text(
        slide,
        "Public update date: 2026-07-20",
        7.0,
        5.98,
        4.7,
        0.28,
        size=11,
        color="muted",
        font="Aptos",
        align=PP_ALIGN.RIGHT,
    )
    add_footer(slide, 2)
    set_notes(
        slide,
        "Use these corrected figures for all public communication: "
        "18 public shelters, including 14 that are wheelchair accessible.",
    )

    # Slide 3 — accessibility map.
    slide = presentation.slides.add_slide(blank)
    set_slide_bg(slide, "content_bg")
    add_accent(slide)
    add_eyebrow(slide, "Public shelter overview")
    add_title(slide, "Accessibility Map")
    add_text(
        slide,
        "Schematic view of all public locations, with wheelchair-accessible sites highlighted.",
        0.75,
        1.16,
        9.7,
        0.4,
        size=14,
        color="muted",
        font="Aptos",
    )
    map_panel = add_rect(
        slide, 0.75, 1.67, 8.05, 4.77, "blue_pale", radius=True, line="line"
    )
    map_panel.name = "Accessibility map key visual"
    set_alt_text(
        map_panel,
        "Schematic accessibility map with 18 public shelter markers connected by "
        "routes; 14 highlighted markers are wheelchair accessible.",
        "Schematic accessibility map",
    )

    # Public schematic roads and route lines.
    for x1, y1, x2, y2, width in (
        (1.1, 3.15, 8.34, 3.15, 7),
        (4.55, 2.02, 4.55, 5.96, 7),
        (2.0, 5.23, 7.66, 2.35, 4),
        (1.55, 2.38, 7.8, 5.55, 3),
    ):
        add_line(slide, x1, y1, x2, y2, "FFFFFF", width)
    for x1, y1, x2, y2 in (
        (1.25, 3.15, 8.15, 3.15),
        (4.55, 2.15, 4.55, 5.75),
        (2.15, 5.05, 7.5, 2.53),
    ):
        add_line(slide, x1, y1, x2, y2, "CFE1F1", 1.6)

    map_points = [
        (1.34, 2.36, True),
        (2.35, 2.36, True),
        (3.35, 2.36, False),
        (5.35, 2.36, True),
        (6.48, 2.36, True),
        (7.52, 2.36, True),
        (1.34, 3.5, True),
        (2.35, 3.5, True),
        (3.35, 3.5, True),
        (5.35, 3.5, False),
        (6.48, 3.5, True),
        (7.52, 3.5, True),
        (1.34, 4.65, True),
        (2.35, 4.65, False),
        (3.35, 4.65, True),
        (5.35, 4.65, True),
        (6.48, 4.65, True),
        (7.52, 4.65, False),
    ]
    for index, (x, y, accessible) in enumerate(map_points, 1):
        if accessible:
            add_oval(slide, x - 0.18, y - 0.18, 0.47, 0.47, "white")
            add_oval(slide, x - 0.11, y - 0.11, 0.33, 0.33, "blue")
            add_text(
                slide,
                "✓",
                x - 0.11,
                y - 0.13,
                0.33,
                0.33,
                size=10,
                color="white",
                font="Aptos",
                bold=True,
                align=PP_ALIGN.CENTER,
                valign=MSO_ANCHOR.MIDDLE,
            )
        else:
            add_oval(slide, x - 0.11, y - 0.11, 0.32, 0.32, "white", "52667A", 1.2)
    add_text(
        slide,
        "N",
        8.08,
        1.94,
        0.35,
        0.36,
        size=14,
        color="content_title",
        font="Aptos",
        bold=True,
        align=PP_ALIGN.CENTER,
        valign=MSO_ANCHOR.MIDDLE,
    )
    add_line(slide, 8.25, 2.34, 8.25, 2.86, "content_title", 1.4)
    add_text(
        slide,
        "Schematic only. Use the public shelter finder for current details.",
        1.03,
        5.99,
        6.9,
        0.28,
        size=9,
        color="muted",
        font="Aptos",
    )

    key_card = add_rect(
        slide, 9.08, 1.67, 3.48, 4.77, "white", radius=True, line="line"
    )
    key_card.name = "Map key card"
    add_text(
        slide,
        "MAP KEY",
        9.38,
        1.97,
        2.65,
        0.28,
        size=10,
        color="blue",
        font="Aptos",
        bold=True,
    )
    add_text(
        slide,
        "18",
        9.38,
        2.39,
        1.0,
        0.58,
        size=28,
        color="content_title",
        font="Aptos Display",
        bold=True,
        valign=MSO_ANCHOR.MIDDLE,
    )
    add_text(
        slide,
        "public shelters",
        10.2,
        2.54,
        1.9,
        0.34,
        size=12,
        color="muted",
        font="Aptos",
        valign=MSO_ANCHOR.MIDDLE,
    )
    add_oval(slide, 9.39, 3.24, 0.28, 0.28, "blue")
    add_text(
        slide,
        "14 wheelchair accessible",
        9.83,
        3.18,
        2.38,
        0.4,
        size=12,
        color="body",
        font="Aptos",
        bold=True,
        valign=MSO_ANCHOR.MIDDLE,
    )
    add_oval(slide, 9.39, 3.83, 0.28, 0.28, "white", "52667A", 1.2)
    add_text(
        slide,
        "4 other public locations",
        9.83,
        3.77,
        2.28,
        0.4,
        size=12,
        color="body",
        font="Aptos",
        valign=MSO_ANCHOR.MIDDLE,
    )
    add_rect(slide, 9.38, 4.54, 2.86, 0.03, "accent")
    add_text(
        slide,
        "Call the public hotline if you need help identifying an accessible location.",
        9.38,
        4.79,
        2.75,
        0.9,
        size=12,
        color="body",
        font="Aptos",
        line_spacing=1.08,
    )
    add_footer(slide, 3)
    set_notes(
        slide,
        "The map is a public schematic showing 18 locations and 14 accessible "
        "shelters. Direct residents to the public website for current details.",
    )

    # Slide 4 — transit access.
    slide = presentation.slides.add_slide(blank)
    set_slide_bg(slide, "content_bg")
    add_accent(slide)
    add_eyebrow(slide, "Planning accessible travel")
    add_title(slide, "Transit Access Updates")
    add_text(
        slide,
        "Use public information to check service status and plan an accessible route.",
        0.75,
        1.16,
        8.6,
        0.4,
        size=14,
        color="muted",
        font="Aptos",
    )
    route_card = add_rect(
        slide, 0.75, 1.7, 11.82, 2.47, "white", radius=True, line="line"
    )
    route_card.name = "Transit route key visual"
    set_alt_text(
        route_card,
        "Three-step accessible transit route: check public service status, plan an "
        "accessible route, and confirm arrival at the shelter.",
        "Accessible transit route",
    )
    add_line(slide, 1.37, 2.75, 11.82, 2.75, "B7C9DB", 4)
    for x, num, heading, detail in (
        (1.03, "1", "Check status", "Review public service updates"),
        (4.85, "2", "Plan the route", "Confirm accessible options"),
        (8.67, "3", "Confirm arrival", "Ask for accessible entry"),
    ):
        add_icon_badge(slide, num, x, 2.5, diameter=0.5, size=14)
        add_text(
            slide,
            heading,
            x - 0.02,
            3.15,
            2.5,
            0.38,
            size=16,
            color="content_title",
            font="Aptos",
            bold=True,
            align=PP_ALIGN.CENTER,
            valign=MSO_ANCHOR.MIDDLE,
        )
        add_text(
            slide,
            detail,
            x - 0.02,
            3.57,
            2.5,
            0.35,
            size=11,
            color="muted",
            font="Aptos",
            align=PP_ALIGN.CENTER,
            valign=MSO_ANCHOR.MIDDLE,
        )

    for x, label, heading, detail, fill in (
        (
            0.75,
            "PUBLIC HOTLINE",
            "Ask about accessible travel",
            "Call for help identifying an accessible shelter and confirming public transit guidance.",
            "blue_pale",
        ),
        (
            4.77,
            "ACCESSIBLE OPTIONS",
            "Plan before leaving",
            "Confirm the accessible entrance, route, and arrival point before starting your trip.",
            "green_soft",
        ),
        (
            8.79,
            "AT ARRIVAL",
            "Request support",
            "Tell shelter staff what you need and ask for the accessible entry or waiting area.",
            "orange_soft",
        ),
    ):
        card = add_rect(slide, x, 4.48, 3.77, 1.62, fill, radius=True)
        card.name = "Transit guidance"
        add_text(
            slide,
            label,
            x + 0.25,
            4.7,
            3.1,
            0.22,
            size=9,
            color="blue" if fill == "blue_pale" else "content_title",
            font="Aptos",
            bold=True,
        )
        add_text(
            slide,
            heading,
            x + 0.25,
            4.99,
            3.15,
            0.36,
            size=14,
            color="content_title",
            font="Aptos",
            bold=True,
        )
        add_text(
            slide,
            detail,
            x + 0.25,
            5.37,
            3.12,
            0.55,
            size=10.5,
            color="body",
            font="Aptos",
            line_spacing=1.0,
        )
    add_footer(slide, 4)
    set_notes(
        slide,
        "Encourage residents to check public service status and confirm accessible "
        "routes before travel. Shelter staff can help with access needs on arrival.",
    )

    # Slide 5 — service animals and equipment.
    slide = presentation.slides.add_slide(blank)
    set_slide_bg(slide, "content_bg")
    add_accent(slide)
    add_eyebrow(slide, "Access and support")
    add_title(slide, "Service Animal and Medical Equipment")
    add_text(
        slide,
        "Access needs should be raised with shelter staff so the right support can be arranged.",
        0.75,
        1.16,
        10.9,
        0.4,
        size=14,
        color="muted",
        font="Aptos",
    )
    service_card = add_rect(
        slide, 0.75, 1.78, 5.73, 3.82, "white", radius=True, line="line"
    )
    service_card.name = "Service animal guidance key visual"
    set_alt_text(
        service_card,
        "Service animal guidance card explaining that service animals are welcome "
        "at public shelters and staff can help with entry and space.",
        "Service animal guidance",
    )
    add_icon_badge(slide, "SA", 1.08, 2.1, diameter=0.74, size=15)
    add_text(
        slide,
        "SERVICE ANIMALS",
        2.02,
        2.12,
        3.9,
        0.26,
        size=10,
        color="blue",
        font="Aptos",
        bold=True,
    )
    add_text(
        slide,
        "Welcome at public shelters",
        2.02,
        2.47,
        3.95,
        0.45,
        size=20,
        color="content_title",
        font="Aptos Display",
        bold=True,
        valign=MSO_ANCHOR.MIDDLE,
    )
    add_text(
        slide,
        "Bring your service animal with you. Ask shelter staff if you need help "
        "with entry, space, or other access support.",
        1.1,
        3.24,
        4.9,
        0.8,
        size=13,
        color="body",
        font="Aptos",
        line_spacing=1.12,
    )
    add_rect(slide, 1.1, 4.28, 4.78, 0.58, "blue_pale", radius=True)
    add_text(
        slide,
        "No personal medical details are required to request help.",
        1.31,
        4.4,
        4.35,
        0.3,
        size=10.5,
        color="blue_dark",
        font="Aptos",
        bold=True,
        valign=MSO_ANCHOR.MIDDLE,
    )

    equipment_card = add_rect(
        slide, 6.85, 1.78, 5.73, 3.82, "white", radius=True, line="line"
    )
    equipment_card.name = "Medical equipment guidance key visual"
    set_alt_text(
        equipment_card,
        "Medical equipment guidance card explaining that residents should bring "
        "essential equipment and ask about facility-specific power or refrigeration support.",
        "Medical equipment guidance",
    )
    add_icon_badge(slide, "ME", 7.18, 2.1, fill="green", diameter=0.74, size=15)
    add_text(
        slide,
        "MEDICAL EQUIPMENT",
        8.12,
        2.12,
        3.68,
        0.26,
        size=10,
        color="green",
        font="Aptos",
        bold=True,
    )
    add_text(
        slide,
        "Plan for essential needs",
        8.12,
        2.47,
        3.82,
        0.45,
        size=20,
        color="content_title",
        font="Aptos Display",
        bold=True,
        valign=MSO_ANCHOR.MIDDLE,
    )
    add_text(
        slide,
        "Bring essential medical equipment and supplies. Before travel, ask the "
        "public hotline about facility-specific power or refrigeration support.",
        7.2,
        3.24,
        4.93,
        0.9,
        size=13,
        color="body",
        font="Aptos",
        line_spacing=1.12,
    )
    add_rect(slide, 7.2, 4.28, 4.78, 0.58, "green_soft", radius=True)
    add_text(
        slide,
        "Share only the information needed to arrange support.",
        7.41,
        4.4,
        4.3,
        0.3,
        size=10.5,
        color="green",
        font="Aptos",
        bold=True,
        valign=MSO_ANCHOR.MIDDLE,
    )

    process = add_rect(slide, 0.75, 5.88, 11.83, 0.76, "title_bg", radius=True)
    process.name = "Access support process"
    add_text(
        slide,
        "PREPARE",
        1.08,
        6.1,
        1.35,
        0.24,
        size=10,
        color="accent",
        font="Aptos",
        bold=True,
        align=PP_ALIGN.CENTER,
        valign=MSO_ANCHOR.MIDDLE,
    )
    add_line(slide, 2.5, 6.24, 4.2, 6.24, "52667A", 2)
    add_text(
        slide,
        "ARRIVE",
        4.32,
        6.1,
        1.35,
        0.24,
        size=10,
        color="accent",
        font="Aptos",
        bold=True,
        align=PP_ALIGN.CENTER,
        valign=MSO_ANCHOR.MIDDLE,
    )
    add_line(slide, 5.77, 6.24, 7.16, 6.24, "52667A", 2)
    add_text(
        slide,
        "ASK STAFF",
        7.3,
        6.1,
        1.55,
        0.24,
        size=10,
        color="accent",
        font="Aptos",
        bold=True,
        align=PP_ALIGN.CENTER,
        valign=MSO_ANCHOR.MIDDLE,
    )
    add_line(slide, 8.96, 6.24, 10.4, 6.24, "52667A", 2)
    add_text(
        slide,
        "GET SUPPORT",
        10.52,
        6.1,
        1.65,
        0.24,
        size=10,
        color="accent",
        font="Aptos",
        bold=True,
        align=PP_ALIGN.CENTER,
        valign=MSO_ANCHOR.MIDDLE,
    )
    add_footer(slide, 5)
    set_notes(
        slide,
        "Service animals are welcome. Residents should bring essential equipment "
        "and ask the public hotline about facility-specific support before travel.",
    )

    # Slide 6 — hotline and links.
    slide = presentation.slides.add_slide(blank)
    set_slide_bg(slide, "content_bg")
    add_accent(slide)
    add_eyebrow(slide, "Approved public contacts")
    add_title(slide, "Hotline and Web Links")
    add_text(
        slide,
        "Use these public channels for shelter access questions and current information.",
        0.75,
        1.16,
        10.3,
        0.4,
        size=14,
        color="muted",
        font="Aptos",
    )
    path_visual = add_rect(
        slide, 0.75, 1.72, 4.7, 4.75, "title_bg", radius=True
    )
    path_visual.name = "Public contact pathway key visual"
    set_alt_text(
        path_visual,
        "Public contact pathway offering three options: call the shelter hotline, "
        "visit the public shelter website, or email the accessibility team.",
        "Public contact pathway",
    )
    add_text(
        slide,
        "CONTACT PATHWAY",
        1.1,
        2.02,
        3.7,
        0.25,
        size=10,
        color="accent",
        font="Aptos",
        bold=True,
    )
    add_line(slide, 1.66, 2.82, 1.66, 5.26, "52667A", 3)
    for y, number, label, color in (
        (2.58, "1", "Call", "blue"),
        (3.72, "2", "Visit", "green"),
        (4.86, "3", "Email", "accent"),
    ):
        add_oval(slide, 1.43, y, 0.48, 0.48, color)
        add_text(
            slide,
            number,
            1.43,
            y - 0.01,
            0.48,
            0.48,
            size=12,
            color="white" if color != "accent" else "content_title",
            font="Aptos",
            bold=True,
            align=PP_ALIGN.CENTER,
            valign=MSO_ANCHOR.MIDDLE,
        )
        add_text(
            slide,
            label,
            2.18,
            y + 0.02,
            1.55,
            0.42,
            size=18,
            color="white",
            font="Aptos Display",
            bold=True,
            valign=MSO_ANCHOR.MIDDLE,
        )
    add_text(
        slide,
        "Public information only",
        2.15,
        5.45,
        2.7,
        0.28,
        size=10,
        color="B8C9DA",
        font="Aptos",
        bold=True,
    )

    # Public hotline card.
    add_rect(slide, 5.76, 1.72, 6.82, 1.35, "white", radius=True, line="line")
    add_text(
        slide,
        "SHELTER HOTLINE",
        6.08,
        1.96,
        2.6,
        0.24,
        size=10,
        color="blue",
        font="Aptos",
        bold=True,
    )
    add_text(
        slide,
        "1-800-555-0148",
        6.08,
        2.27,
        4.1,
        0.55,
        size=26,
        color="content_title",
        font="Aptos Display",
        bold=True,
        valign=MSO_ANCHOR.MIDDLE,
        name="Public hotline number",
    )
    add_text(
        slide,
        "Call for shelter access and current availability questions.",
        10.18,
        2.18,
        1.93,
        0.55,
        size=10,
        color="muted",
        font="Aptos",
        align=PP_ALIGN.RIGHT,
        valign=MSO_ANCHOR.MIDDLE,
    )

    # Public website card with a functional hyperlink.
    add_rect(slide, 5.76, 3.31, 6.82, 1.35, "white", radius=True, line="line")
    add_text(
        slide,
        "PUBLIC SHELTER WEBSITE",
        6.08,
        3.53,
        2.8,
        0.24,
        size=10,
        color="blue",
        font="Aptos",
        bold=True,
    )
    add_rich_text(
        slide,
        [
            {
                "text": "https://city.example/shelters/public",
                "size": 17,
                "bold": True,
                "color": "blue",
                "hyperlink": "https://city.example/shelters/public",
            }
        ],
        6.08,
        3.84,
        6.12,
        0.48,
        font="Aptos",
        valign=MSO_ANCHOR.MIDDLE,
        name="Public website hyperlink",
    )
    add_text(
        slide,
        "View locations, hours, and accessibility details.",
        8.0,
        4.3,
        4.14,
        0.22,
        size=9,
        color="muted",
        font="Aptos",
        align=PP_ALIGN.RIGHT,
    )

    # Accessibility email card with a functional mailto hyperlink.
    add_rect(slide, 5.76, 4.9, 6.82, 1.35, "white", radius=True, line="line")
    add_text(
        slide,
        "ACCESSIBILITY EMAIL",
        6.08,
        5.12,
        3.2,
        0.24,
        size=10,
        color="blue",
        font="Aptos",
        bold=True,
    )
    add_rich_text(
        slide,
        [
            {
                "text": "accessibility@city.example",
                "size": 21,
                "bold": True,
                "color": "blue",
                "hyperlink": "mailto:accessibility@city.example",
            }
        ],
        6.08,
        5.44,
        5.5,
        0.46,
        font="Aptos",
        valign=MSO_ANCHOR.MIDDLE,
        name="Accessibility email hyperlink",
    )
    add_text(
        slide,
        "For an accessibility question or a support request.",
        6.08,
        5.92,
        5.25,
        0.22,
        size=9,
        color="muted",
        font="Aptos",
    )
    add_footer(slide, 6)
    set_notes(
        slide,
        "Share the public hotline, the public shelter website, and the accessibility "
        "email. All three channels are approved for public use.",
    )

    # Slide 7 — update log.
    slide = presentation.slides.add_slide(blank)
    set_slide_bg(slide, "content_bg")
    add_accent(slide)
    add_eyebrow(slide, "Public revision record")
    add_title(slide, "Update Log")
    add_text(
        slide,
        "Public corrections and checks applied to this briefing.",
        0.75,
        1.16,
        7.5,
        0.4,
        size=14,
        color="muted",
        font="Aptos",
    )
    log_shape = slide.shapes.add_table(
        4, 4, Inches(0.75), Inches(1.7), Inches(11.83), Inches(3.24)
    )
    log_table = log_shape.table
    log_rows = [
        ("Date", "Public update", "Corrected value", "Status"),
        (
            "2026-07-20",
            "Shelter network totals",
            "18 public shelters; 14 wheelchair accessible",
            "Verified",
        ),
        (
            "2026-07-20",
            "Public contact channels",
            "Public hotline, website, and accessibility email",
            "Verified",
        ),
        (
            "2026-07-20",
            "Accessibility content",
            "Public labels, alt text, and links reviewed",
            "Complete",
        ),
    ]
    for r, row in enumerate(log_rows):
        for c, value in enumerate(row):
            log_table.cell(r, c).text = value
    style_table(
        log_table,
        column_widths=(1.68, 2.55, 5.3, 2.3),
        font_size=12,
        header_size=11,
    )
    log_shape.name = "Public update log table"
    set_alt_text(
        log_shape,
        "Update log table dated July 20, 2026, recording verified public shelter "
        "totals, contact channels, and accessibility content review.",
        "Public update log",
    )

    timeline = add_rect(
        slide, 0.75, 5.33, 11.83, 1.27, "white", radius=True, line="line"
    )
    timeline.name = "Public update timeline key visual"
    set_alt_text(
        timeline,
        "Timeline showing three completed public update actions on July 20, 2026: "
        "correct counts, verify contacts, and complete accessibility review.",
        "Public update timeline",
    )
    add_line(slide, 1.37, 5.97, 11.78, 5.97, "B7C9DB", 3)
    for x, number, label in (
        (1.09, "1", "Correct counts"),
        (4.6, "2", "Verify contacts"),
        (8.08, "3", "Complete review"),
    ):
        add_icon_badge(slide, number, x, 5.72, fill="blue", diameter=0.5, size=12)
        add_text(
            slide,
            label,
            x - 0.12,
            6.28,
            1.95,
            0.25,
            size=10,
            color="content_title",
            font="Aptos",
            bold=True,
            align=PP_ALIGN.CENTER,
            valign=MSO_ANCHOR.MIDDLE,
        )
    add_text(
        slide,
        "PUBLIC UPDATE • 2026-07-20",
        9.46,
        5.45,
        2.5,
        0.2,
        size=9,
        color="accent",
        font="Aptos",
        bold=True,
        align=PP_ALIGN.RIGHT,
        valign=MSO_ANCHOR.MIDDLE,
    )
    add_footer(slide, 7)
    set_notes(
        slide,
        "This public log records the corrected counts, verified contact channels, "
        "and completed accessibility review for the July 20, 2026 update.",
    )

    # Slide 8 — accessibility checklist.
    slide = presentation.slides.add_slide(blank)
    set_slide_bg(slide, "content_bg")
    add_accent(slide)
    add_eyebrow(slide, "Before and during a visit")
    add_title(slide, "Accessibility Checklist")
    add_text(
        slide,
        "A simple public checklist for planning a safer and more accessible shelter visit.",
        0.75,
        1.16,
        10.3,
        0.4,
        size=14,
        color="muted",
        font="Aptos",
    )
    checklist = [
        ("1", "Confirm status", "Check current shelter hours and availability."),
        ("2", "Verify access", "Confirm the location is wheelchair accessible."),
        ("3", "Plan transit", "Identify an accessible route before leaving."),
        ("4", "Pack essentials", "Bring medications, equipment, and supplies."),
        ("5", "Ask on arrival", "Request accessible entry or other support."),
        ("6", "Protect privacy", "Share only what is needed to receive help."),
    ]
    for index, (num, heading, detail) in enumerate(checklist):
        col = index % 2
        row = index // 2
        x = 0.76 + col * 4.02
        y = 1.75 + row * 1.55
        card = add_rect(slide, x, y, 3.76, 1.25, "white", radius=True, line="line")
        card.name = f"Checklist item {index + 1}"
        add_rect(slide, x + 0.18, y + 0.2, 0.42, 0.42, "green", radius=True)
        add_text(
            slide,
            "✓",
            x + 0.18,
            y + 0.19,
            0.42,
            0.42,
            size=13,
            color="white",
            font="Aptos",
            bold=True,
            align=PP_ALIGN.CENTER,
            valign=MSO_ANCHOR.MIDDLE,
        )
        add_text(
            slide,
            heading,
            x + 0.75,
            y + 0.17,
            2.65,
            0.32,
            size=14,
            color="content_title",
            font="Aptos",
            bold=True,
            valign=MSO_ANCHOR.MIDDLE,
        )
        add_text(
            slide,
            detail,
            x + 0.75,
            y + 0.54,
            2.7,
            0.51,
            size=10.5,
            color="body",
            font="Aptos",
            line_spacing=1.0,
        )

    summary = add_rect(
        slide, 8.93, 1.75, 3.65, 4.35, "title_bg", radius=True
    )
    summary.name = "Visit preparation key visual"
    set_alt_text(
        summary,
        "Visit preparation guide organized into three stages: plan before travel, "
        "travel with access needs confirmed, and ask shelter staff for support on arrival.",
        "Visit preparation guide",
    )
    add_text(
        slide,
        "PLAN → TRAVEL → ASK",
        9.24,
        2.03,
        3.05,
        0.27,
        size=10,
        color="accent",
        font="Aptos",
        bold=True,
    )
    add_text(
        slide,
        "Know what to check",
        9.24,
        2.42,
        3.05,
        0.58,
        size=23,
        color="white",
        font="Aptos Display",
        bold=True,
        valign=MSO_ANCHOR.MIDDLE,
    )
    summary_steps = [
        ("PLAN", "Confirm shelter status and wheelchair access."),
        ("TRAVEL", "Use an accessible route and carry essentials."),
        ("ASK", "Tell staff what support you need on arrival."),
    ]
    for index, (label, text) in enumerate(summary_steps):
        y = 3.28 + index * 0.88
        add_oval(slide, 9.25, y, 0.3, 0.3, "accent")
        add_text(
            slide,
            label,
            9.73,
            y - 0.04,
            0.85,
            0.36,
            size=10,
            color="white",
            font="Aptos",
            bold=True,
            valign=MSO_ANCHOR.MIDDLE,
        )
        add_text(
            slide,
            text,
            10.57,
            y - 0.07,
            1.58,
            0.68,
            size=9.5,
            color="D8E5F0",
            font="Aptos",
            line_spacing=1.0,
        )
    add_text(
        slide,
        "Accessibility questions?",
        9.24,
        5.56,
        3.0,
        0.28,
        size=11,
        color="accent",
        font="Aptos",
        bold=True,
    )
    add_text(
        slide,
        "Use the public links on the prior slide.",
        9.24,
        5.86,
        2.9,
        0.25,
        size=9.5,
        color="D8E5F0",
        font="Aptos",
    )
    add_footer(slide, 8)
    set_notes(
        slide,
        "Use this checklist to help residents confirm shelter status, plan accessible "
        "travel, carry essentials, and ask for support on arrival.",
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    presentation.save(OUTPUT)
    return presentation


if __name__ == "__main__":
    result = build()
    print(f"Saved {OUTPUT}")
    print(f"Slides: {len(result.slides)}")
