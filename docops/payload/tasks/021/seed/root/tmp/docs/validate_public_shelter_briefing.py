from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor


OUTPUT = Path(
    "/root/submission/"
    "docops_v2_l3_021_pptx_shelter_accessibility_public_remediation_output.pptx"
)
REPORT = Path("/root/tmp/docs/output_validation.json")

EXPECTED_TITLES = [
    "Emergency Shelter Public Briefing",
    "Corrected Shelter Network",
    "Accessibility Map",
    "Transit Access Updates",
    "Service Animal and Medical Equipment",
    "Hotline and Web Links",
    "Update Log",
    "Accessibility Checklist",
]
FOOTER = "Public Shelter Accessibility Briefing | 2026"
BANNED_TEXT = [
    "DRAFT",
    "PRIVATE",
    "INTERNAL",
    "staff-only",
    "personal phone",
    "555-0199",
    "emergency operations center",
    "do not publish",
    "internal.example",
    "eoc.internal",
]
ALLOWED_LINKS = {
    "https://city.example/shelters/public",
    "mailto:accessibility@city.example",
}


def color_hex(fill) -> str | None:
    try:
        value = fill.fore_color.rgb
    except (AttributeError, TypeError):
        return None
    if isinstance(value, RGBColor):
        return str(value)
    return None


def shape_bounds(shape, slide_width: int, slide_height: int) -> tuple[float, float, float, float]:
    return (
        shape.left / 914400,
        shape.top / 914400,
        (shape.left + shape.width) / 914400,
        (shape.top + shape.height) / 914400,
    )


presentation = Presentation(OUTPUT)
report: dict = {"path": str(OUTPUT), "slides": [], "errors": [], "warnings": []}


def error(message: str) -> None:
    report["errors"].append(message)


def warning(message: str) -> None:
    report["warnings"].append(message)


if len(presentation.slides) != 8:
    error(f"Expected 8 slides, found {len(presentation.slides)}")

all_text: list[str] = []
all_links: set[str] = set()

for index, slide in enumerate(presentation.slides, 1):
    slide_texts = []
    notes_text = ""
    alt_texts = []
    off_slide = []
    hyperlink_addresses = []
    title_shape = None
    footer_found = False
    accent_found = False
    key_visual_count = 0
    table_headers = []

    if slide.has_notes_slide:
        notes_text = slide.notes_slide.notes_text_frame.text.strip()

    for shape in slide.shapes:
        if shape.has_text_frame:
            text = shape.text.strip()
            if text:
                slide_texts.append(text)
                all_text.append(text)
            if shape.name == "Slide title":
                title_shape = shape
            if FOOTER in text:
                footer_found = True
            for paragraph in shape.text_frame.paragraphs:
                for run in paragraph.runs:
                    if run.hyperlink.address:
                        hyperlink_addresses.append(run.hyperlink.address)
                        all_links.add(run.hyperlink.address)

        try:
            c_nv_pr = shape._element.xpath(".//p:cNvPr")[0]
            descr = c_nv_pr.get("descr", "").strip()
            if descr:
                alt_texts.append(descr)
                if len(descr) >= 25:
                    key_visual_count += 1
        except IndexError:
            pass

        left, top, right, bottom = shape_bounds(
            shape, presentation.slide_width, presentation.slide_height
        )
        if left < -0.001 or top < -0.001 or right > 13.334 or bottom > 7.501:
            off_slide.append(
                {
                    "name": shape.name,
                    "bounds": [round(left, 3), round(top, 3), round(right, 3), round(bottom, 3)],
                }
            )

        if shape.name == "Orange accent rectangle":
            try:
                if str(shape.fill.fore_color.rgb) == "F59E0B":
                    accent_found = True
            except (AttributeError, TypeError):
                pass

        if shape.has_table:
            table = shape.table
            if len(table.rows) and len(table.columns):
                header = []
                for cell in table.rows[0].cells:
                    header.append(cell.text)
                    if color_hex(cell.fill) != "0B5CAD":
                        error(f"Slide {index}: table header fill is not 0B5CAD")
                    for paragraph in cell.text_frame.paragraphs:
                        for run in paragraph.runs:
                            if str(run.font.color.rgb) != "FFFFFF" or not run.font.bold:
                                error(
                                    f"Slide {index}: table header text is not white bold"
                                )
                table_headers.append(header)

    title_text = title_shape.text.strip() if title_shape is not None else ""
    title_font = None
    title_bold = None
    title_color = None
    if title_shape is not None:
        runs = [
            run
            for paragraph in title_shape.text_frame.paragraphs
            for run in paragraph.runs
        ]
        if runs:
            title_font = runs[0].font.name
            title_bold = runs[0].font.bold
            title_color = str(runs[0].font.color.rgb)

    expected_title = EXPECTED_TITLES[index - 1]
    # Slide 1 uses a line break in its two-line title; all title characters remain.
    normalized_title = re.sub(r"\s+", " ", title_text)
    if normalized_title != expected_title:
        error(
            f"Slide {index}: title mismatch, expected {expected_title!r}, "
            f"found {normalized_title!r}"
        )
    if title_font != "Aptos Display":
        error(f"Slide {index}: title font is {title_font!r}")
    if title_bold is not True:
        error(f"Slide {index}: title is not bold")
    expected_color = "FFFFFF" if index == 1 else "102A43"
    if title_color != expected_color:
        error(
            f"Slide {index}: title color is {title_color!r}, expected {expected_color}"
        )
    if not footer_found:
        error(f"Slide {index}: required footer text not found")
    if not accent_found:
        error(f"Slide {index}: orange accent rectangle not found")
    if key_visual_count < 1:
        error(f"Slide {index}: no meaningful key visual alt text")
    if not notes_text:
        error(f"Slide {index}: speaker notes are missing")
    for term in BANNED_TEXT:
        if term.casefold() in "\n".join(slide_texts).casefold():
            error(f"Slide {index}: banned visible text {term!r}")
        if term.casefold() in notes_text.casefold():
            error(f"Slide {index}: banned notes text {term!r}")
    if off_slide:
        error(f"Slide {index}: off-slide shapes: {off_slide}")

    bg = color_hex(slide.background.fill)
    expected_bg = "102A43" if index == 1 else "F7FBFF"
    if bg != expected_bg:
        error(f"Slide {index}: background {bg!r}, expected {expected_bg!r}")

    report["slides"].append(
        {
            "slide": index,
            "title": normalized_title,
            "background": bg,
            "title_font": title_font,
            "title_bold": title_bold,
            "title_color": title_color,
            "footer": footer_found,
            "accent_rectangle": accent_found,
            "meaningful_alt_texts": alt_texts,
            "notes": notes_text,
            "hyperlinks": hyperlink_addresses,
            "table_headers": table_headers,
            "off_slide_shapes": off_slide,
        }
    )

if not ALLOWED_LINKS.issubset(all_links):
    error(f"Missing required public links: {sorted(ALLOWED_LINKS - all_links)}")
disallowed = all_links - ALLOWED_LINKS
if disallowed:
    error(f"Disallowed hyperlinks found: {sorted(disallowed)}")

required_public_facts = [
    "18",
    "14",
    "1-800-555-0148",
    "https://city.example/shelters/public",
    "accessibility@city.example",
    "2026-07-20",
]
joined_text = "\n".join(all_text)
for fact in required_public_facts:
    if fact not in joined_text:
        error(f"Required public fact missing from slide text: {fact!r}")

with zipfile.ZipFile(OUTPUT) as archive:
    package_text = ""
    for name in archive.namelist():
        if name.endswith(".xml"):
            package_text += archive.read(name).decode("utf-8", errors="ignore")
    for term in BANNED_TEXT:
        if term.casefold() in package_text.casefold():
            error(f"Banned term remains anywhere in package XML: {term!r}")

report["all_hyperlinks"] = sorted(all_links)
report["slide_count"] = len(presentation.slides)
REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")

print(json.dumps(report, indent=2))
if report["errors"]:
    raise SystemExit(f"Validation failed with {len(report['errors'])} error(s)")
print("All structural, content, accessibility, and link checks passed.")
