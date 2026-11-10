"""Dynamic validator for synthetic scaled PPTX 026 variants.

Reads the frozen expected.json and the rebuilt presentation, then checks every
slide and every unit: total page count, per-unit titles and title-page unit
name, per-unit native trend chart data (never pointing at the first unit),
per-unit inventory / supplier tables, speaker notes, banned terms, and the
required public style tokens. No fixed "exactly nine pages" assertion is used;
totals come from expected.json.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE


def color_hex(fill):
    try:
        value = fill.fore_color.rgb
    except (AttributeError, TypeError):
        return None
    if isinstance(value, RGBColor):
        return str(value)
    return None


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def table_values(table) -> list[list[str]]:
    return [[cell.text for cell in row.cells] for row in table.rows]


def check(output_path: Path, expected_path: Path) -> dict:
    expected = json.loads(Path(expected_path).read_text(encoding="utf-8"))
    banned = [term.casefold() for term in expected["banned_text"]]
    style = expected["style"]
    total = expected["total_pages"]
    expected_chart_type = getattr(XL_CHART_TYPE, style["chart_type"])

    presentation = Presentation(str(output_path))
    report = {"errors": [], "slides": [], "units": {}}

    def error(message):
        report["errors"].append(message)

    if len(presentation.slides) != total:
        error(f"Expected {total} slides, found {len(presentation.slides)}")

    unit_by_page = {}
    for group in expected["units"]:
        for page in range(group["page_start"], group["page_end"] + 1):
            unit_by_page[page] = group

    all_text = []
    for slide_index in range(1, total + 1):
        if slide_index > len(presentation.slides):
            error(f"slide {slide_index}: missing slide")
            continue
        slide = presentation.slides[slide_index - 1]
        group = unit_by_page[slide_index]
        within = slide_index - group["page_start"]
        expected_title = group["titles"][within]

        slide_texts = [normalize(sh.text) for sh in slide.shapes
                       if getattr(sh, "has_text_frame", False) and sh.text.strip()]
        notes_text = (slide.notes_slide.notes_text_frame.text.strip()
                      if slide.has_notes_slide else "")

        title_shape = None
        for sh in slide.shapes:
            if getattr(sh, "has_text_frame", False):
                candidate = normalize(sh.text)
                if candidate == normalize(expected_title):
                    title_shape = sh
                    break
        if title_shape is None:
            for sh in slide.shapes:
                if getattr(sh, "has_text_frame", False):
                    candidate = normalize(sh.text)
                    if normalize(expected_title) in candidate:
                        title_shape = sh
                        break
        if title_shape is None:
            error(f"slide {slide_index} ({group['id']}): title "
                  f"{expected_title!r} not found")
        else:
            runs = [run for paragraph in title_shape.text_frame.paragraphs
                    for run in paragraph.runs]
            if not runs:
                error(f"slide {slide_index}: title shape has no runs")
            else:
                if runs[0].font.name != style["title_font"]:
                    error(f"slide {slide_index}: title font is {runs[0].font.name!r}")
                if runs[0].font.bold is not True:
                    error(f"slide {slide_index}: title is not bold")
                expected_title_color = (
                    style["title_slide_title_color"] if within == 0
                    else style["content_title_color"])
                if str(runs[0].font.color.rgb) != expected_title_color:
                    error(f"slide {slide_index}: title color is "
                          f"{runs[0].font.color.rgb!r}")

        joined = "\n".join(slide_texts)
        all_text.append(joined)
        if within == 0 and group["name"] not in joined:
            error(f"slide {slide_index}: title page does not contain unit name "
                  f"{group['name']!r}")

        bg = color_hex(slide.background.fill)
        expected_bg = style["title_slide_bg"] if within == 0 else style["content_bg"]
        if bg != expected_bg:
            error(f"slide {slide_index}: background {bg!r}, expected {expected_bg!r}")

        accents = [sh for sh in slide.shapes
                   if sh.name == "Public Green Accent Rectangle"]
        if not accents:
            error(f"slide {slide_index}: public green accent rectangle not found")
        elif color_hex(accents[0].fill) != style["accent_fill"]:
            error(f"slide {slide_index}: accent fill is {color_hex(accents[0].fill)!r}")

        if not notes_text:
            error(f"slide {slide_index}: speaker notes are missing")
        elif group["name"] not in notes_text:
            error(f"slide {slide_index}: speaker notes do not contain unit name "
                  f"{group['name']!r}")
        elif normalize(notes_text) != normalize(group["notes"][within]):
            error(f"slide {slide_index}: speaker notes mismatch")

        for term in banned:
            if term in joined.casefold():
                error(f"slide {slide_index}: banned visible text {term!r}")
            if term in notes_text.casefold():
                error(f"slide {slide_index}: banned notes text {term!r}")

        report["slides"].append({
            "slide": slide_index, "unit": group["id"],
            "title": normalize(title_shape.text) if title_shape is not None else "",
            "notes": notes_text,
        })

    for group in expected["units"]:
        slide_count = len(presentation.slides)

        def slide_at(page):
            return presentation.slides[page - 1] if page <= slide_count else None

        chart_slide = slide_at(group["chart_page"])
        if chart_slide is None:
            error(f"unit {group['id']}: chart page {group['chart_page']} is missing")
        else:
            charts = [shape.chart for shape in chart_slide.shapes
                      if getattr(shape, "has_chart", False)]
            if len(charts) != 1:
                error(f"unit {group['id']}: expected exactly one native chart on "
                      f"slide {group['chart_page']}, found {len(charts)}")
            else:
                chart = charts[0]
                if chart.chart_type != expected_chart_type:
                    error(f"unit {group['id']}: chart type is {chart.chart_type!r}, "
                          f"expected {expected_chart_type!r}")
                categories = list(chart.plots[0].categories)
                values = [round(float(v), 4) for v in chart.series[0].values]
                if categories != group["chart"]["categories"]:
                    error(f"unit {group['id']}: chart categories {categories!r}, "
                          f"expected {group['chart']['categories']!r}")
                if values != [round(float(v), 4) for v in group["chart"]["values"]]:
                    error(f"unit {group['id']}: chart values {values!r}, expected "
                          f"{group['chart']['values']!r}")
                if chart.series[0].name != group["chart"]["series_name"]:
                    error(f"unit {group['id']}: chart series name "
                          f"{chart.series[0].name!r}")

        inv_slide = slide_at(group["inventory_page"])
        if inv_slide is None:
            error(f"unit {group['id']}: inventory page {group['inventory_page']} "
                  "is missing")
        else:
            inv_tables = [shape.table for shape in inv_slide.shapes
                          if getattr(shape, "has_table", False)]
            if not inv_tables:
                error(f"unit {group['id']}: no inventory table on "
                      f"slide {group['inventory_page']}")
            else:
                table = inv_tables[0]
                if table_values(table) != group["inventory_rows"]:
                    error(f"unit {group['id']}: inventory table mismatch on "
                          f"slide {group['inventory_page']}")
                for cell in table.rows[0].cells:
                    if color_hex(cell.fill) != style["table_header_fill"]:
                        error(f"unit {group['id']}: inventory table header fill is "
                              f"{color_hex(cell.fill)!r}")

        sup_slide = slide_at(group["supplier_page"])
        if sup_slide is None:
            error(f"unit {group['id']}: supplier page {group['supplier_page']} "
                  "is missing")
        else:
            sup_tables = [shape.table for shape in sup_slide.shapes
                          if getattr(shape, "has_table", False)]
            if not sup_tables:
                error(f"unit {group['id']}: no supplier register table on "
                      f"slide {group['supplier_page']}")
            elif table_values(sup_tables[0]) != group["supplier_rows"]:
                error(f"unit {group['id']}: supplier register table mismatch on "
                      f"slide {group['supplier_page']}")

        report["units"][group["id"]] = {
            "page_start": group["page_start"], "page_end": group["page_end"],
            "chart_page": group["chart_page"],
        }

    report["slide_count"] = len(presentation.slides)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=os.environ.get("VARIANT_OUTPUT"))
    parser.add_argument("--expected", default=os.environ.get("VARIANT_EXPECTED",
                                                             "/root/tmp/docs/expected.json"))
    parser.add_argument("--report", default=os.environ.get("VARIANT_REPORT",
                                                           "/root/tmp/docs/output_validation.json"))
    args = parser.parse_args(argv)
    if not args.output:
        parser.error("--output is required (or set VARIANT_OUTPUT)")
    report = check(Path(args.output), Path(args.expected))
    Path(args.report).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if report["errors"]:
        raise SystemExit(f"Validation failed with {len(report['errors'])} error(s)")
    print("All structural, content, chart, table, note, and style checks passed.")


if __name__ == "__main__":
    main()
