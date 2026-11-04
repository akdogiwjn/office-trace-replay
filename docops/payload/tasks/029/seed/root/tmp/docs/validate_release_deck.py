from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

from pptx import Presentation


SOURCE = Path("/root/docops_v2_l3_029_pptx_qbr_release_deck_input.pptx")
OUTPUT = Path(
    "/root/submission/docops_v2_l3_029_pptx_qbr_release_deck_output.pptx"
)


def all_slide_text(slide) -> str:
    values = []
    for shape in slide.shapes:
        if getattr(shape, "has_text_frame", False):
            values.append(shape.text_frame.text)
        if getattr(shape, "has_table", False):
            for row in shape.table.rows:
                values.extend(cell.text for cell in row.cells)
    return "\n".join(values)


def find_table(slide, expected_headers: list[str]):
    for shape in slide.shapes:
        if not getattr(shape, "has_table", False):
            continue
        table = shape.table
        headers = [cell.text for cell in table.rows[0].cells]
        if headers == expected_headers:
            return table
    raise AssertionError(f"Table with headers {expected_headers!r} not found")


def table_values(table) -> list[list[str]]:
    return [[cell.text for cell in row.cells] for row in table.rows]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    require(SOURCE.exists(), f"Missing source: {SOURCE}")
    require(OUTPUT.exists(), f"Missing output: {OUTPUT}")

    source = Presentation(SOURCE)
    output = Presentation(OUTPUT)
    require(len(output.slides) == 9, f"Expected 9 slides, found {len(output.slides)}")

    expected_names = [
        "Title",
        "Agenda",
        "Market Context",
        "KPI Snapshot",
        "Customer Risks",
        "Mitigation Plan",
        "Decision Request",
        "Appendix - Data Notes",
        "Reference - Locked Legal",
    ]
    actual_names = [slide._element.cSld.get("name", "") for slide in output.slides]
    require(
        actual_names[:8] == expected_names[:8],
        f"Unexpected slide names: {actual_names!r}",
    )

    agenda = find_table(output.slides[1], ["Section", "Slide", "Owner"])
    expected_agenda = [
        ["Section", "Slide", "Owner"],
        ["Market Context", "3", "Maya Chen"],
        ["KPI Snapshot", "4", "Jon Bell"],
        ["Customer Risks", "5", "Priya Rao"],
        ["Mitigation Plan", "6", "Maya Chen"],
        ["Decision Request", "7", "Jon Bell"],
        ["Appendix - Data Notes", "8", "Priya Rao"],
    ]
    require(
        table_values(agenda) == expected_agenda,
        f"Agenda mismatch: {table_values(agenda)!r}",
    )

    kpi = find_table(output.slides[3], ["Metric", "Value", "QBR Readout"])
    expected_kpi = [
        ["Metric", "Value", "QBR Readout"],
        ["ARR", "3.2M", "Up 10% QoQ"],
        ["Churn risk", "4 accounts", "Requires executive review"],
        ["NRR", "94%", "Below target"],
        ["Expansion pipeline", "1.1M", "Two deals require support plan"],
    ]
    require(table_values(kpi) == expected_kpi, f"KPI mismatch: {table_values(kpi)!r}")

    risks = find_table(
        output.slides[4], ["Risk", "Account Count", "Owner", "Mitigation"]
    )
    expected_risks = [
        ["Risk", "Account Count", "Owner", "Mitigation"],
        [
            "Renewal delay",
            "2",
            "Maya Chen",
            "Executive outreach by 2026-06-10",
        ],
        [
            "Adoption gap",
            "1",
            "Priya Rao",
            "Enablement plan by 2026-06-12",
        ],
        ["Support escalation", "1", "Jon Bell", "Daily incident review"],
    ]
    require(
        table_values(risks) == expected_risks,
        f"Customer-risk table mismatch: {table_values(risks)!r}",
    )

    mitigation = find_table(
        output.slides[5], ["Action", "Owner", "Due Date", "Status"]
    )
    expected_mitigation = [
        ["Action", "Owner", "Due Date", "Status"],
        ["Confirm renewal-risk owners", "Maya Chen", "2026-06-07", "Open"],
        ["Publish enablement plan", "Priya Rao", "2026-06-12", "Open"],
        ["Start daily incident review", "Jon Bell", "2026-06-06", "Ready"],
    ]
    require(
        table_values(mitigation) == expected_mitigation,
        f"Mitigation table mismatch: {table_values(mitigation)!r}",
    )

    decisions = [
        "Approve executive outreach for 4 renewal-risk accounts.",
        "Authorize enablement plan for NRR recovery.",
        "Decision needed by 2026-06-07.",
    ]
    decision_text = all_slide_text(output.slides[6])
    for statement in decisions:
        require(statement in decision_text, f"Missing decision statement: {statement}")
    expected_note = (
        "Speaker note: ask for decision on renewal-risk outreach before reviewing appendix."
    )
    actual_note = output.slides[6].notes_slide.notes_text_frame.text
    require(actual_note == expected_note, f"Unexpected speaker note: {actual_note!r}")

    appendix_text = all_slide_text(output.slides[7])
    require(
        "Public source: QBR metrics workbook, 2026-06-05." in appendix_text,
        "Missing public source sentence",
    )

    for index in range(2, 8):
        text = all_slide_text(output.slides[index])
        require(
            "QBR Release | 2026-06-05" in text,
            f"Missing release footer on slide {index + 1}",
        )
        require(
            f"Slide {index + 1} of 9" in text,
            f"Missing slide-number footer on slide {index + 1}",
        )
    for index in [0, 1, 8]:
        text = all_slide_text(output.slides[index])
        require(
            "QBR Release | 2026-06-05" not in text,
            f"Unexpected release footer on slide {index + 1}",
        )
        require(
            f"Slide {index + 1} of 9" not in text,
            f"Unexpected slide-number footer on slide {index + 1}",
        )

    combined_visible_text = "\n".join(
        all_slide_text(slide) for slide in output.slides
    )
    forbidden = [
        r"\bDraft:",
        r"\bWorking Copy\b",
        r"\bInternal\b",
        r"\bstaging\b",
        r"\bScratch Backup\b",
        r"\bDeprecated Roadmap\b",
        r"\bOld agenda\b",
        r"\bdo not publish\b",
    ]
    for pattern in forbidden:
        require(
            re.search(pattern, combined_visible_text, flags=re.IGNORECASE) is None,
            f"Publishable text still contains forbidden pattern {pattern!r}",
        )

    source_legal = source.slides[9]
    output_legal = output.slides[8]
    source_legal_text = [
        shape.text if getattr(shape, "has_text_frame", False) else ""
        for shape in source_legal.shapes
    ]
    output_legal_text = [
        shape.text if getattr(shape, "has_text_frame", False) else ""
        for shape in output_legal.shapes
    ]
    require(
        len(source_legal.shapes) == len(output_legal.shapes) == 2,
        "Locked legal shape count changed",
    )
    require(
        source_legal_text == output_legal_text,
        "Locked legal slide text changed",
    )
    require(
        source_legal.notes_slide.notes_text_frame.text
        == output_legal.notes_slide.notes_text_frame.text,
        "Locked legal speaker note changed",
    )

    with zipfile.ZipFile(OUTPUT) as archive:
        slide_parts = sorted(
            name
            for name in archive.namelist()
            if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)
        )
    require(len(slide_parts) == 9, f"Unexpected slide parts in package: {slide_parts!r}")

    print("PASS")
    print(f"slides: {len(output.slides)}")
    print("agenda, KPI, risks, mitigation, decision, appendix, and footers verified")
    print("locked legal text, notes, and shape count match the source")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise
