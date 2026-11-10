"""Dynamic validator for synthetic scaled PPTX 021 variants.

Reads the frozen expected.json and the rebuilt presentation, then checks every
slide against the per-region expectations (page order, titles, region facts,
links, alt text, notes, style). No fixed "exactly eight pages" assertion is
used; the total page count comes from expected.json.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import zipfile
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor


def color_hex(fill):
    try:
        value = fill.fore_color.rgb
    except (AttributeError, TypeError):
        return None
    if isinstance(value, RGBColor):
        return str(value)
    return None


def shape_bounds(shape, slide_width, slide_height):
    return (
        shape.left / 914400, shape.top / 914400,
        (shape.left + shape.width) / 914400, (shape.top + shape.height) / 914400,
    )


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def check(output_path: Path, expected_path: Path) -> dict:
    expected = json.loads(Path(expected_path).read_text(encoding="utf-8"))
    banned = [term.casefold() for term in expected["banned_text"]]
    style = expected["style"]
    total = expected["total_pages"]
    pages_per_region = expected["pages_per_region"]
    min_alt = expected["minimum_alt_text_length"]

    presentation = Presentation(output_path)
    report = {"errors": [], "warnings": [], "slides": [], "regions": {}}

    def error(message):
        report["errors"].append(message)

    if len(presentation.slides) != total:
        error(f"Expected {total} slides, found {len(presentation.slides)}")

    region_by_page = {}
    for group in expected["regions"]:
        for page in range(group["page_start"], group["page_end"] + 1):
            region_by_page[page] = group

    all_text = []
    all_links = set()
    region_texts = {group["id"]: [] for group in expected["regions"]}
    region_links = {group["id"]: set() for group in expected["regions"]}

    for slide_index in range(1, total + 1):
        if slide_index > len(presentation.slides):
            error(f"slide {slide_index}: missing slide")
            continue
        slide = presentation.slides[slide_index - 1]
        group = region_by_page[slide_index]
        within = slide_index - group["page_start"]  # 0-based position within region
        expected_title = group["titles"][within]

        slide_texts = []
        notes_text = ""
        alt_texts = []
        off_slide = []
        hyperlink_addresses = []
        title_shape = None
        footer_found = False
        accent_found = False
        key_visual_count = 0
        slide_number_found = False
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
                if expected["footer"] in text:
                    footer_found = True
                if f"{slide_index} / {total}" in text:
                    slide_number_found = True
                for paragraph in shape.text_frame.paragraphs:
                    for run in paragraph.runs:
                        if run.hyperlink.address:
                            hyperlink_addresses.append(run.hyperlink.address)
                            all_links.add(run.hyperlink.address)
                            region_links[group["id"]].add(run.hyperlink.address)
            try:
                c_nv_pr = shape._element.xpath(".//p:cNvPr")[0]
                descr = c_nv_pr.get("descr", "").strip()
                if descr:
                    alt_texts.append(descr)
                    if len(descr) >= min_alt:
                        key_visual_count += 1
            except IndexError:
                pass
            left, top, right, bottom = shape_bounds(shape, presentation.slide_width,
                                                    presentation.slide_height)
            if left < -0.001 or top < -0.001 or right > 13.334 or bottom > 7.501:
                off_slide.append(shape.name)
            if shape.name == "Orange accent rectangle":
                try:
                    if str(shape.fill.fore_color.rgb) == style["accent_fill"]:
                        accent_found = True
                except (AttributeError, TypeError):
                    pass
            if shape.has_table:
                table = shape.table
                if len(table.rows) and len(table.columns):
                    header = []
                    for cell in table.rows[0].cells:
                        header.append(cell.text)
                        if color_hex(cell.fill) != style["table_header_fill"]:
                            error(f"slide {slide_index}: table header fill is not "
                                  f"{style['table_header_fill']}")
                        for paragraph in cell.text_frame.paragraphs:
                            for run in paragraph.runs:
                                if str(run.font.color.rgb) != style["table_header_font_color"] \
                                        or not run.font.bold:
                                    error(f"slide {slide_index}: table header text is not "
                                          "white bold")
                    table_headers.append(header)

        title_text = title_shape.text.strip() if title_shape is not None else ""
        title_font = title_bold = title_color = None
        if title_shape is not None:
            runs = [run for paragraph in title_shape.text_frame.paragraphs
                    for run in paragraph.runs]
            if runs:
                title_font = runs[0].font.name
                title_bold = runs[0].font.bold
                title_color = str(runs[0].font.color.rgb)

        if normalize(title_text) != expected_title:
            error(f"slide {slide_index} ({group['id']}): title mismatch, expected "
                  f"{expected_title!r}, found {normalize(title_text)!r}")
        if title_font != style["title_font"]:
            error(f"slide {slide_index}: title font is {title_font!r}")
        if title_bold is not True:
            error(f"slide {slide_index}: title is not bold")
        expected_title_color = style["title_slide_title_color"] if within == 0 else style["content_title_color"]
        if title_color != expected_title_color:
            error(f"slide {slide_index}: title color is {title_color!r}")
        if not footer_found:
            error(f"slide {slide_index}: required footer text not found")
        if not slide_number_found:
            error(f"slide {slide_index}: slide number '{slide_index} / {total}' not found")
        if not accent_found:
            error(f"slide {slide_index}: orange accent rectangle not found")
        if key_visual_count < 1:
            error(f"slide {slide_index}: no meaningful key visual alt text")
        if not notes_text:
            error(f"slide {slide_index}: speaker notes are missing")
        for term in banned:
            if term in "\n".join(slide_texts).casefold():
                error(f"slide {slide_index}: banned visible text {term!r}")
            if term in notes_text.casefold():
                error(f"slide {slide_index}: banned notes text {term!r}")
        if off_slide:
            error(f"slide {slide_index}: off-slide shapes: {off_slide}")

        bg = color_hex(slide.background.fill)
        expected_bg = style["title_slide_bg"] if within == 0 else style["content_bg"]
        if bg != expected_bg:
            error(f"slide {slide_index}: background {bg!r}, expected {expected_bg!r}")

        region_texts[group["id"]].extend(slide_texts)
        report["slides"].append({
            "slide": slide_index, "region": group["id"],
            "title": normalize(title_text), "background": bg,
            "title_font": title_font, "title_bold": title_bold,
            "title_color": title_color, "footer": footer_found,
            "slide_number": slide_number_found, "accent_rectangle": accent_found,
            "meaningful_alt_texts": alt_texts, "notes": notes_text,
            "hyperlinks": hyperlink_addresses, "table_headers": table_headers,
            "off_slide_shapes": off_slide,
        })

    for group in expected["regions"]:
        joined = "\n".join(region_texts[group["id"]])
        missing = [term for term in group["required_texts"] if term not in joined]
        if missing:
            error(f"region {group['id']}: required public facts missing from its pages: {missing}")
        missing_links = [link for link in group["links"] if link not in region_links[group["id"]]]
        if missing_links:
            error(f"region {group['id']}: required links missing: {missing_links}")
        report["regions"][group["id"]] = {
            "page_start": group["page_start"], "page_end": group["page_end"],
            "missing_required_texts": missing, "missing_links": missing_links,
        }

    allowed = set(expected["allowed_links"])
    disallowed = all_links - allowed
    if disallowed:
        error(f"Disallowed hyperlinks found: {sorted(disallowed)}")

    with zipfile.ZipFile(output_path) as archive:
        package_text = ""
        for name in archive.namelist():
            if name.endswith(".xml"):
                package_text += archive.read(name).decode("utf-8", errors="ignore")
        for term in banned:
            if term in package_text.casefold():
                error(f"Banned term remains anywhere in package XML: {term!r}")

    report["all_hyperlinks"] = sorted(all_links)
    report["slide_count"] = len(presentation.slides)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=os.environ.get("VARIANT_OUTPUT"))
    parser.add_argument("--expected", default=os.environ.get("VARIANT_EXPECTED", "/root/tmp/docs/expected.json"))
    parser.add_argument("--report", default=os.environ.get("VARIANT_REPORT", "/root/tmp/docs/output_validation.json"))
    args = parser.parse_args(argv)
    if not args.output:
        parser.error("--output is required (or set VARIANT_OUTPUT)")
    report = check(Path(args.output), Path(args.expected))
    Path(args.report).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if report["errors"]:
        raise SystemExit(f"Validation failed with {len(report['errors'])} error(s)")
    print("All structural, content, accessibility, and link checks passed.")


if __name__ == "__main__":
    main()
