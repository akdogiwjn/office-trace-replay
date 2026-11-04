from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE


OUTPUT = Path(
    "/root/submission/"
    "docops_v2_l3_026_pptx_climate_disclosure_chart_rebuild_output.pptx"
)
EXPECTED_TITLES = [
    "Northline Climate Disclosure Briefing",
    "Disclosure Boundary",
    "Corrected Emissions Inventory",
    "Emissions Trend Chart",
    "Assurance Status",
    "Transition Action Plan",
    "Supplier Engagement Register",
    "Board Actions",
    "Publication Style Guide",
]
FORBIDDEN = [
    "draft",
    "private",
    "internal",
    "scratch",
    "confidential",
    "14,800",
    "42%",
    "2023",
    "kara sato",
    "submittd",
    "555-0100",
    "legal hold",
    "facility closure",
    "supplier dispute",
    "do not publish",
]


def rgb(slide):
    return slide.background.fill.fore_color.rgb


def main():
    prs = Presentation(OUTPUT)
    assert len(prs.slides) == 9

    for index, (slide, expected_title) in enumerate(zip(prs.slides, EXPECTED_TITLES)):
        expected_background = RGBColor(0x0F, 0x17, 0x2A) if index == 0 else RGBColor(0xF8, 0xFA, 0xFC)
        assert rgb(slide) == expected_background

        title_shape = next(
            shape
            for shape in slide.shapes
            if getattr(shape, "has_text_frame", False)
            and shape.text_frame.text == expected_title
        )
        title_runs = [
            run
            for paragraph in title_shape.text_frame.paragraphs
            for run in paragraph.runs
        ]
        assert title_runs
        assert all(run.font.name == "Aptos Display" for run in title_runs)
        assert all(run.font.bold for run in title_runs)
        expected_title_color = RGBColor(0xFF, 0xFF, 0xFF) if index == 0 else RGBColor(0x0F, 0x17, 0x2A)
        assert all(run.font.color.rgb == expected_title_color for run in title_runs)

        accent_shapes = [
            shape
            for shape in slide.shapes
            if shape.name == "Public Green Accent Rectangle"
        ]
        assert len(accent_shapes) == 1
        assert accent_shapes[0].fill.fore_color.rgb == RGBColor(0x22, 0xC5, 0x5E)

        footer_shapes = [
            shape
            for shape in slide.shapes
            if getattr(shape, "has_text_frame", False)
            and shape.text_frame.text == "Northline Public Climate Disclosure | FY2026"
        ]
        assert footer_shapes
        assert slide.notes_slide.notes_text_frame.text.strip()

    for slide_index in (2, 6):
        for shape in prs.slides[slide_index].shapes:
            if not getattr(shape, "has_table", False):
                continue
            table = shape.table
            for c_idx in range(len(table.columns)):
                header = table.cell(0, c_idx)
                assert header.fill.fore_color.rgb == RGBColor(0x16, 0x65, 0x34)
                for paragraph in header.text_frame.paragraphs:
                    for run in paragraph.runs:
                        assert run.font.bold
                        assert run.font.color.rgb == RGBColor(0xFF, 0xFF, 0xFF)

    chart_shapes = [
        shape for shape in prs.slides[3].shapes if getattr(shape, "has_chart", False)
    ]
    assert len(chart_shapes) == 1
    chart = chart_shapes[0].chart
    assert chart.chart_type == XL_CHART_TYPE.COLUMN_CLUSTERED
    assert list(chart.plots[0].categories) == ["2024", "2025", "2026"]
    assert len(chart.series) == 1
    assert chart.series[0].name == "Total emissions tCO2e"
    assert list(chart.series[0].values) == [42800.0, 39750.0, 36220.0]

    public_text = "\n".join(
        [
            shape.text_frame.text
            for slide in prs.slides
            for shape in slide.shapes
            if getattr(shape, "has_text_frame", False)
        ]
        + [slide.notes_slide.notes_text_frame.text for slide in prs.slides]
    ).lower()
    for phrase in FORBIDDEN:
        assert phrase not in public_text, f"Forbidden phrase remains: {phrase}"

    print("QA passed: 9 slides, style tokens, tables, chart, notes, and public-content checks.")


if __name__ == "__main__":
    main()
