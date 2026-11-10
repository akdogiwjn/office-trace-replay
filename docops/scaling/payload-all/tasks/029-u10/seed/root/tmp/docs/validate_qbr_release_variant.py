"""Dynamic validator for synthetic scaled PPTX 029 variants.

Reads the frozen expected.json and the rebuilt release deck, then checks every
public page and unit: total page count (8N+1), the FROZEN parent's eight slide
types per unit (Title, Agenda, Market Context, KPI Snapshot, Customer Risks,
Mitigation Plan, Decision Request, Appendix - Data Notes) with per-unit facts,
the public footer ("Slide i of total"), the speaker notes, the token-boundary
forbidden draft terms, and the trailing locked legal page which must match the
material-recorded source text, shape count and speaker note exactly. Every
unit (especially the last) is fully validated; per-unit slide indices are used
(never a global lookup by name that would only update the first group).
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

from pptx import Presentation


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _rgb_or_none(color) -> str | None:
    try:
        if color is not None and color.type is not None:
            return str(color.rgb) if color.rgb is not None else None
    except Exception:
        return None
    return None


def semantic_legal_snapshot(slide) -> dict:
    """Normalized semantic snapshot of a locked legal slide (same rules as the
    prepare-time oracle): background, ordered shapes with type/geometry/fill/
    line/text runs and fonts, media count and the speaker note. ZIP timestamps,
    relationship ids and part-name renumbering are intentionally excluded."""
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    bg_fill = slide.background.fill
    bg_type = str(bg_fill.type) if bg_fill.type is not None else None
    bg_rgb = _rgb_or_none(bg_fill.fore_color) if bg_fill.type == 1 else None
    shapes = []
    media = 0
    for sh in slide.shapes:
        if sh.shape_type in (MSO_SHAPE_TYPE.PICTURE, MSO_SHAPE_TYPE.MEDIA,
                             MSO_SHAPE_TYPE.CHART, MSO_SHAPE_TYPE.TABLE):
            media += 1
        fill_type = fill_rgb = None
        try:
            if sh.fill.type is not None:
                fill_type = str(sh.fill.type)
                if sh.fill.type == 1:
                    fill_rgb = _rgb_or_none(sh.fill.fore_color)
        except Exception:
            pass
        line = None
        try:
            if sh.line.color is not None and sh.line.color.type is not None:
                line = {"rgb": _rgb_or_none(sh.line.color),
                        "width_pt": sh.line.width.pt if sh.line.width is not None else None}
        except Exception:
            pass
        paragraphs = []
        if sh.has_text_frame:
            for para in sh.text_frame.paragraphs:
                runs = []
                for run in para.runs:
                    font = run.font
                    color = None
                    try:
                        if font.color.type is not None:
                            color = _rgb_or_none(font.color)
                    except Exception:
                        color = None
                    runs.append({
                        "text": run.text, "name": font.name,
                        "size_pt": font.size.pt if font.size is not None else None,
                        "bold": font.bold, "italic": font.italic, "color": color,
                    })
                paragraphs.append(runs)
        shapes.append({
            "type": str(sh.shape_type), "left": sh.left, "top": sh.top,
            "width": sh.width, "height": sh.height,
            "fill_type": fill_type, "fill_rgb": fill_rgb, "line": line,
            "paragraphs": paragraphs,
        })
    notes = (slide.notes_slide.notes_text_frame.text if slide.has_notes_slide else "")
    return {"background": {"type": bg_type, "rgb": bg_rgb},
            "shapes": shapes, "media_count": media, "notes": notes}


def table_values(table) -> list[list[str]]:
    return [[cell.text for cell in row.cells] for row in table.rows]


def find_table(slide, header: list[str]):
    for shape in slide.shapes:
        if not getattr(shape, "has_table", False):
            continue
        table = shape.table
        if [cell.text for cell in table.rows[0].cells] == header:
            return table
    return None


def slide_text(slide) -> str:
    values = []
    for shape in slide.shapes:
        if getattr(shape, "has_text_frame", False):
            values.append(shape.text_frame.text)
        if getattr(shape, "has_table", False):
            for row in shape.table.rows:
                values.extend(cell.text for cell in row.cells)
    return "\n".join(values)


def check_table(report, error, slide_index, slide, header, expected_rows, label):
    table = find_table(slide, header)
    if table is None:
        error(f"slide {slide_index}: {label} table with header {header!r} not found")
        return
    if table_values(table) != expected_rows:
        error(f"slide {slide_index}: {label} table mismatch")


def check(output_path: Path, expected_path: Path) -> dict:
    expected = json.loads(Path(expected_path).read_text(encoding="utf-8"))
    total = expected["total_pages"]
    pages_per_unit = expected["pages_per_unit"]
    footer = expected["footer"]
    forbidden = expected["forbidden_patterns"]
    legal_expected = expected["legal_slide"]

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

    for slide_index in range(1, total):
        if slide_index > len(presentation.slides):
            error(f"slide {slide_index}: missing slide")
            continue
        slide = presentation.slides[slide_index - 1]
        group = unit_by_page[slide_index]
        within = slide_index - group["page_start"]
        text = slide_text(slide)
        notes = (slide.notes_slide.notes_text_frame.text.strip()
                 if slide.has_notes_slide else "")

        expected_title = group["titles"][within]
        if expected_title not in text:
            error(f"slide {slide_index} ({group['id']}): title "
                  f"{expected_title!r} not found")
        if not notes:
            error(f"slide {slide_index}: speaker notes are missing")
        elif normalize(notes) != normalize(
                group["decision_note"] if within == 6
                else group["page_notes"][within]):
            error(f"slide {slide_index}: speaker notes mismatch")
        if group["name"] not in text and within == 0:
            error(f"slide {slide_index}: unit name {group['name']!r} not found")

        requires_footer = within in (2, 3, 4, 5, 6, 7)
        if requires_footer:
            if footer not in text:
                error(f"slide {slide_index}: release footer not found")
            if f"Slide {slide_index} of {total}" not in text:
                error(f"slide {slide_index}: slide-number footer "
                      f"'Slide {slide_index} of {total}' not found")
        elif footer in text:
            error(f"slide {slide_index}: unexpected release footer on title/agenda")

        if within == 1:
            # Agenda: six sections with per-unit absolute slide numbers/owners.
            check_table(report, error, slide_index, slide,
                        ["Section", "Slide", "Owner"], group["agenda_table"], "agenda")
        elif within == 2:
            for callout in group["market_callouts"]:
                if callout[1] not in text:
                    error(f"slide {slide_index}: market-context callout missing: "
                          f"{callout[0]!r}")
            if group["market_lens"] not in text:
                error(f"slide {slide_index}: market lens missing")
        elif within == 3:
            check_table(report, error, slide_index, slide,
                        ["Metric", "Value", "QBR Readout"],
                        group["kpi_table"], "KPI")
        elif within == 4:
            check_table(report, error, slide_index, slide,
                        ["Risk", "Account Count", "Owner", "Mitigation"],
                        group["risk_table"], "customer-risk")
        elif within == 5:
            check_table(report, error, slide_index, slide,
                        ["Action", "Owner", "Due Date", "Status"],
                        group["mitigation_table"], "mitigation")
        elif within == 6:
            if normalize(notes) != normalize(group["decision_note"]):
                error(f"slide {slide_index}: decision speaker note mismatch")
            for statement in group["decision_statements"]:
                if statement not in text:
                    error(f"slide {slide_index}: decision statement missing: "
                          f"{statement!r}")
        elif within == 7:
            if group["data_notes"] not in text:
                error(f"slide {slide_index}: appendix data-notes citation missing")
            if group["data_currency"] not in text:
                error(f"slide {slide_index}: appendix data-currency missing")

        report["slides"].append({
            "slide": slide_index, "unit": group["id"],
            "title": expected_title, "notes": notes,
        })

    # Locked legal page (always last and preserved from the source).
    if len(presentation.slides) >= total:
        legal = presentation.slides[total - 1]
        legal_texts = [
            shape.text if getattr(shape, "has_text_frame", False) else ""
            for shape in legal.shapes
        ]
        if len(legal.shapes) != legal_expected["shape_count"]:
            error(f"locked legal slide shape count changed: "
                  f"{len(legal.shapes)} != {legal_expected['shape_count']}")
        if [normalize(t) for t in legal_texts] != [
                normalize(t) for t in legal_expected["texts"]]:
            error("locked legal slide text changed")
        legal_notes = (legal.notes_slide.notes_text_frame.text.strip()
                       if legal.has_notes_slide else "")
        if normalize(legal_notes) != normalize(legal_expected["notes"]):
            error("locked legal speaker note changed")
        # Semantic snapshot (background, shape types/geometry/fill/line/fonts,
        # media refs) must match the prepare-time frozen snapshot.
        snapshot = legal_expected.get("semantic_snapshot")
        if snapshot is not None:
            actual = semantic_legal_snapshot(legal)
            if actual != snapshot:
                error(f"locked legal semantic snapshot changed: "
                      f"expected {json.dumps(snapshot, sort_keys=True)} "
                      f"actual {json.dumps(actual, sort_keys=True)}")
        legal_visible = slide_text(legal)
        if footer in legal_visible:
            error("release footer must not be added to the locked legal page")
        report["legal_slide"] = {
            "shape_count": len(legal.shapes),
            "texts": [normalize(t) for t in legal_texts],
            "notes": normalize(legal_notes),
        }

    combined = "\n".join(slide_text(s) for s in presentation.slides)
    for pattern in forbidden:
        if re.search(pattern, combined, flags=re.IGNORECASE) is not None:
            error(f"publishable text still contains forbidden pattern {pattern!r}")

    for group in expected["units"]:
        report["units"][group["id"]] = {
            "page_start": group["page_start"],
            "page_end": group["page_end"],
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
    print("All structural, table, note, footer, forbidden-text and locked-legal checks passed.")


if __name__ == "__main__":
    main()
