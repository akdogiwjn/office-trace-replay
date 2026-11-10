"""Synthetic PPTX 026 inputs: scaled climate disclosure chart-rebuild variants.

Produces the per-unit prepared material (units.json) and a messy internal source
presentation that contains, for every reporting unit, the to-be-fixed content
(wrong Scope 2 / renewable / base-year values, staff phone, confidential notes,
scratch markers). The public builder reads units.json, deletes the internal
slides and confidential notes, applies the corrected facts, and rebuilds the
frozen nine-page public disclosure set per unit with each unit's own native
3-year trend chart and per-unit tables.
"""
from __future__ import annotations

import random
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches

from .. import common

PAGES_PER_UNIT = 9
CHART_CATEGORIES = ["2024", "2025", "2026"]
SERIES_NAME = "Total emissions tCO2e"

PREFIXES = [
    "Arcadia", "Harbor", "Cascade", "Northgate", "Solstice", "Bridger",
    "Osprey", "Kestrel", "Willow", "Cinder", "Alden", "Stonegate",
    "Marigold", "Pinecrest", "Aurora", "Foxglove", "Ridgeway", "Ember",
    "Larkspur", "Westbrook",
]
SUFFIXES = [
    "Renewables", "Grid Services", "Energy Works", "Climate Co", "Power Systems",
    "Utilities", "Sustainable Holdings", "Clean Energy", "Carbon Partners",
    "Net Zero Labs",
]
OWNERS = [
    "Kara Saito", "Maya Chen", "Priya Rao", "Jon Bell", "Ana Torres",
    "Liam Novak", "Zoe Patel", "Omar Haddad",
]

# Generic public-release forbidden tokens (parent 026 verifier set, minus the
# parent-specific frozen numbers which vary per synthetic unit).
BANNED = [
    "draft", "private", "internal", "scratch", "unreleased forecast",
    "facility closure rumor", "supplier dispute", "personal phone",
    "legal hold", "do not publish", "private assurance finding",
    "555-0100",
]

NOTES = [
    "Open by framing {name}'s FY2026 climate disclosure as a concise public "
    "update on boundary, performance, assurance, and action.",
    "The {name} disclosure uses operational control and a 2024 base year, with "
    "Scope 1 and location-based Scope 2 reported annually.",
    "Highlight that {name} Scope 2 location-based emissions are {scope2} tCO2e "
    "and renewable electricity is {rp}%.",
    "Walk through the reported {name} total declining from {t1} tCO2e in 2024 "
    "to {t3} tCO2e in 2026.",
    "Summarize the completed submission and the assurance review status for "
    "{name} using the public disclosure record.",
    "Emphasize that {name} actions focus on energy, renewables, fleet, supplier "
    "data, and quarterly governance.",
    "Invite discussion on {name} supplier cohorts, data quality, and the next "
    "engagement cycle.",
    "Close with the three board decisions that support {name} public reporting "
    "and follow-through.",
    "Use the style tokens consistently across future public climate "
    "communications for {name}.",
]


def make_units(n: int, rng: random.Random) -> list[dict]:
    if n < 1:
        raise ValueError("reporting unit count must be >= 1")
    units = []
    used_t1 = set()
    for index in range(n):
        name = (
            f"{PREFIXES[index % len(PREFIXES)]} "
            f"{SUFFIXES[(index // len(PREFIXES)) % len(SUFFIXES)]}"
        )
        scope1 = rng.randint(7800, 9900)
        scope2 = rng.randint(11800, 16500)
        rp = rng.randint(38, 55)
        base_year = 2024
        cats = rng.randint(11, 15)
        owner = OWNERS[index % len(OWNERS)]
        t1 = rng.randint(42000, 45000)
        while t1 in used_t1:
            t1 = rng.randint(42000, 45000)
        used_t1.add(t1)
        t2 = rng.randint(37800, 41500)
        t3 = rng.randint(34000, 37200)
        t2 = min(t2, t1 - 2400)
        t3 = min(t3, t2 - 2200)
        units.append({
            "id": f"DSC-{index + 1:03d}",
            "name": name,
            "base_year": base_year,
            "scope_1": scope1,
            "scope_2_location_based": scope2,
            "renewable_electricity_pct": rp,
            "scope_3_categories": cats,
            "assurance_owner": owner,
            "submission_status": "Submitted",
            "trend_years": list(CHART_CATEGORIES),
            "trend_values": [t1, t2, t3],
            "transition_actions": [
                ["Energy productivity",
                 "Reduce site energy intensity through operating discipline and efficiency projects."],
                ["Renewable electricity",
                 f"Sustain the {rp}% share and assess additional contracted renewable supply."],
                ["Fleet and logistics",
                 "Improve route efficiency and transition priority fleet segments."],
                ["Supplier data",
                 "Expand activity-data requests for priority value-chain categories."],
                ["Quarterly governance",
                 f"Review {name} emissions performance, actions, and data quality with leadership."],
            ],
            "supplier_rows": [
                ["Strategic materials",
                 f"{name}: activity data and reduction roadmap", "Active", "Validate 2026 data"],
                ["Logistics", "Fuel use and route optimization", "Active", "Review coverage"],
                ["Packaging", "Material efficiency and recycled content", "In progress", "Close data gaps"],
                ["Facilities services", "Energy performance reporting", "Active", "Quarterly check-in"],
            ],
            "board_decisions": [
                ["Approve the baseline",
                 f"Confirm 2024 as the public base year for {name} annual emissions reporting."],
                ["Confirm corrected values",
                 f"Endorse Scope 2 location-based emissions of {scope2:,} tCO2e and "
                 f"renewable electricity at {rp}%."],
                ["Support follow-through",
                 f"Back the {name} supplier engagement plan and quarterly climate action reviews."],
            ],
            "notes": [
                template.format(
                    name=name,
                    scope2=f"{scope2:,}",
                    rp=rp,
                    t1=f"{t1:,}",
                    t3=f"{t3:,}",
                )
                for template in NOTES
            ],
        })
    assert len({u["id"] for u in units}) == n
    assert len({u["name"] for u in units}) == n
    assert len({u["trend_values"][0] for u in units}) == n
    for unit in units:
        assert unit["trend_values"][0] > unit["trend_values"][1] > unit["trend_values"][2]
        assert all(unit["name"] in note for note in unit["notes"])
    return units


def write_units_json(variant_id: str, units: list[dict],
                     input_name: str, out_dir: Path) -> Path:
    data = {
        "schema": "docops-scaling-units-v1",
        "variant_task_id": variant_id,
        "seed": common.VARIANTS[variant_id]["seed"],
        "input_path": f"/root/{input_name}",
        "slides_per_unit": PAGES_PER_UNIT,
        "chart_categories": CHART_CATEGORIES,
        "series_name": SERIES_NAME,
        "units": units,
    }
    common.write_json(out_dir / "units.json", data)
    return out_dir / "units.json"


def write_source_pptx(units: list[dict], out_dir: Path, output_name: str) -> Path:
    """Messy internal review deck: one draft slide per unit + fixed scratch
    slides, all carrying wrong facts and confidential notes."""
    import datetime as _dt
    import os as _os
    import tempfile

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    prs.core_properties.created = _dt.datetime(2026, 1, 1, 0, 0, 0)
    prs.core_properties.modified = _dt.datetime(2026, 1, 1, 0, 0, 0)
    blank = prs.slide_layouts[6]

    for unit in units:
        slide = prs.slides.add_slide(blank)
        title = slide.shapes.add_textbox(Inches(0.5), Inches(0.4), Inches(8), Inches(0.6))
        title.text_frame.text = f"{unit['name']} INTERNAL REVIEW DRAFT"
        facts = slide.shapes.add_textbox(Inches(0.5), Inches(1.2), Inches(9), Inches(3.0))
        facts.text_frame.text = (
            f"Scope 2 location-based {unit['scope_2_location_based'] + 1320:,} tCO2e "
            f"(PRIVATE draft value)\n"
            f"renewable electricity {unit['renewable_electricity_pct'] - 6}% (draft)\n"
            f"base year 2023\nassurance owner Kara Sato\nstatus Submittd\n"
            f"personal phone: 555-0100\nlegal hold review open\n"
            f"INTERNAL DRAFT - do not publish\n"
        )
        hidden = slide.shapes.add_textbox(Inches(20), Inches(20), Inches(2), Inches(2))
        hidden.text_frame.text = (
            f"off-slide: {unit['name']} staff-only raw scope values"
        )
        notes = slide.notes_slide
        notes.notes_text_frame.text = (
            f"PRIVATE speaker note: do not publish. {unit['name']} unreleased "
            "forecast and private assurance finding."
        )

    for heading, body, note in (
        ("PRIVATE Correction Log",
         "Correct Scope 2, renewable share, base year, owner, and status before rebuild.",
         "INTERNAL scratch note for analyst review."),
        ("INTERNAL Analyst Transcript",
         "scratch prompt transcript; do not publish transcript excerpts.",
         "PRIVATE speaker note: do not publish. Contains unreleased forecast."),
        ("PRIVATE Appendix",
         "facility closure rumor, supplier dispute, personal phone, private "
         "assurance finding, do not publish.",
         "INTERNAL scratch note for analyst review."),
    ):
        slide = prs.slides.add_slide(blank)
        slide.shapes.add_textbox(Inches(0.5), Inches(0.4), Inches(9), Inches(0.6)).text = heading
        slide.shapes.add_textbox(Inches(0.5), Inches(1.2), Inches(9), Inches(1.8)).text = body
        slide.notes_slide.notes_text_frame.text = note

    output = out_dir / output_name
    fd, temp_name = tempfile.mkstemp(suffix=".pptx", dir=out_dir)
    _os.close(fd)
    prs.save(temp_name)
    try:
        common.deterministic_zip(temp_name, output)
    finally:
        Path(temp_name).unlink(missing_ok=True)
    return output


def _unit_summary(unit: dict) -> dict:
    return {
        "id": unit["id"],
        "name": unit["name"],
        "base_year": unit["base_year"],
        "scope_1": unit["scope_1"],
        "scope_2_location_based": unit["scope_2_location_based"],
        "renewable_electricity_pct": unit["renewable_electricity_pct"],
        "assurance_owner": unit["assurance_owner"],
        "submission_status": unit["submission_status"],
        "trend_values": unit["trend_values"],
    }


def generate(variant_id: str, out_dir: Path, write_raw_records: bool = True) -> dict:
    v = common.VARIANTS[variant_id]
    n = v["scale"]["units"]
    rng = random.Random(v["seed"])
    units = make_units(n, rng)

    out_dir.mkdir(parents=True, exist_ok=True)
    input_name = (
        f"docops_v2_l3_026_pptx_climate_disclosure_chart_rebuild_input_"
        f"{v['output_suffix']}.pptx"
    )
    input_path = write_source_pptx(units, out_dir, input_name)
    units_path = write_units_json(variant_id, units, input_name, out_dir)

    if write_raw_records:
        common.write_json(
            out_dir / "raw_records.json",
            {"schema": "docops-scaling-raw-records-v1",
             "variant_task_id": variant_id,
             "records": units},
        )

    _prs = Presentation(str(input_path))
    input_slides = len(_prs.slides)
    output_slides = n * PAGES_PER_UNIT

    parameterized_ranges = [
        f"{n} reporting units x {PAGES_PER_UNIT} public slides per unit",
        f"per-unit native clustered-column trend chart (categories "
        f"{CHART_CATEGORIES}, series {SERIES_NAME!r}) with per-unit cached "
        f"3-year values from units.json",
        "per-unit corrected emissions inventory table (5 rows x 4 cols)",
        "per-unit supplier engagement register table (5 rows x 4 cols)",
        "per-unit transition action cards and board decision cards",
        "per-unit public speaker notes on all 9 pages",
    ]

    scale_metadata = {
        "units": n,
        "unit_ids": [u["id"] for u in units],
        "slides_per_unit": PAGES_PER_UNIT,
        "input_slides": input_slides,
        "output_slides": output_slides,
        "expected_output_slides": f"{n} x {PAGES_PER_UNIT} = {output_slides}",
        "render_scope": (
            f"all {output_slides} pages rendered "
            "(convert-to-pdf then pdftoppm -jpeg -r 150)"
        ),
        "expected_render_images": output_slides,
        "chart_categories": CHART_CATEGORIES,
        "series_name": SERIES_NAME,
        "first_unit": _unit_summary(units[0]),
        "middle_unit": _unit_summary(units[n // 2]),
        "last_unit": _unit_summary(units[-1]),
        "parameterized_ranges": parameterized_ranges,
        "preserved_parent_behavior": [
            "frozen 9-page public disclosure sequence and page titles",
            "native clustered-column trend chart with embedded per-unit data",
            "public style tokens (title/content background, Aptos Display bold "
            "titles, accent 22C55E, table header 166534 white bold)",
            "public speaker notes retained on every page",
            "correction-first workflow: internal slides and confidential notes "
            "removed before any rebuild",
            "footer 'Public Climate Disclosure | FY2026' on every page",
        ],
        "changed_parent_behavior": [
            "the parent's single-report deck becomes a per-unit iteration: "
            "units.json drives N x 9 pages, each with its own corrected facts",
            "trend chart data is per-unit (3-year cached values from units.json), "
            "not the frozen 42,800 / 39,750 / 36,220 series",
            "inventory and supplier tables carry per-unit facts",
            "all speaker notes are per-unit",
        ],
        "input_bytes": input_path.stat().st_size,
        "input_sha256": common.sha256_file(input_path),
        "units_json_sha256": common.sha256_file(units_path),
        "seed": v["seed"],
    }

    meta = common.default_task_metadata(variant_id)
    meta["scale_metadata"] = scale_metadata
    meta["input_path"] = f"/root/{input_name}"
    meta["output_path"] = (
        f"/root/submission/"
        f"docops_v2_l3_026_pptx_climate_disclosure_chart_rebuild_output_"
        f"{v['output_suffix']}.pptx"
    )
    meta["modified_workflow"] = [
        "01 build: builder reads units.json and iterates reporting units, "
        "deleting every internal slide/note and rebuilding the 9-page public "
        "disclosure set per unit with that unit's own facts",
        "02 convert_pdf: unchanged soffice convert-to-pdf",
        "03 render: unchanged pdftoppm -jpeg -r 150 over every page",
        "04 validate: dynamic validator checks every slide and every unit chart "
        "against the frozen expected.json",
    ]
    meta["measurement_scope"] = (
        "Measures per-reporting-unit document generation, validation, conversion "
        "and rendering scale: units -> 9 public slides each (5 -> 45, 10 -> 90). "
        "The synthetic source presentation's own page count is NOT what this "
        "variant parses or repairs; this variant does NOT measure a larger "
        "source-PPT parse/cleanup cost. Distinguish input PPTX pages vs unit "
        "count vs expected output pages."
    )
    common.write_json(out_dir / "task_metadata.json", meta)
    (out_dir / "instruction.md").write_text(instruction_md(meta), encoding="utf-8")
    (out_dir / "original_task_description.txt").write_text(
        original_description(meta), encoding="utf-8")

    return {
        "input": input_path,
        "units": units_path,
        "task_metadata": out_dir / "task_metadata.json",
        "scale_metadata": scale_metadata,
    }


def instruction_md(meta: dict) -> str:
    v = common.VARIANTS[meta["variant_task_id"]]
    sm = meta["scale_metadata"]
    return f"""# Task (synthetic scale variant)

This is a manually labelled synthetic scale variant of the frozen official task
`026`. It is NOT a historical benchmark task and has no official score of its own.

## Provenance

- `parent_task`: 026 (frozen `docops_v2_l3_026_pptx_climate_disclosure_chart_rebuild`)
- `synthetic`: true
- generator: {meta['generator']} (version {meta['generator_version']})
- seed: {meta['seed']}
- scale: {sm['units']} reporting units x {sm['slides_per_unit']} slides per unit
  = {sm['output_slides']} output pages

## Inputs

- Source presentation: `{meta['input_path']}`
- Frozen reporting-unit material: `/root/tmp/docs/units.json`
- Frozen expected oracle: `/root/tmp/docs/expected.json`
- Original benchmark seed description: `/root/original_task_description.txt`

## Goal

Rebuild a clean multi-unit public climate disclosure deck from a messy internal
review presentation using the same sequential workflow as parent task 026, with
one full nine-page disclosure set per reporting unit in `units.json`.

## Required Sequential Workflow

1. Remove internal-only slides, hidden off-slide content, confidential notes,
   and staff-only links.
2. Apply the correction memo before rebuilding any table or chart.
3. Iterate the reporting units from `units.json`; every unit produces the frozen
   nine public slides: Title, Disclosure Boundary, Corrected Emissions Inventory,
   Emissions Trend Chart, Assurance Status, Transition Action Plan, Supplier
   Engagement Register, Board Actions, Publication Style Guide.
4. Rebuild the emissions inventory table and the supplier engagement register
   table with each unit's own corrected facts.
5. Rebuild the native clustered-column trend chart from each unit's corrected
   annual totals (per-unit 3-year values).
6. Apply the required public visual style after content and chart data are final.
7. Preserve only concise public speaker notes (per unit, per page).
8. Save the clean deck without modifying the source in place.

## Output Requirements

- Save to `{meta['output_path']}`.
- Keep the output format the same as the input presentation (`.pptx`).
- Complete the full ordered workflow, not just local text replacement.
"""


def original_description(meta: dict) -> str:
    sm = meta["scale_metadata"]
    return (
        "Synthetic scale variant of frozen task 026: climate disclosure chart "
        "rebuild. Source contains internal draft slides, wrong Scope 2 / "
        "renewable / base-year values, staff phone, scratch markers, and "
        "confidential speaker notes. Scale is defined by the number of reporting "
        "units; each unit produces the nine public disclosure slides with its own "
        "native 3-year trend chart and per-unit tables. "
        f"Variant {meta['variant_task_id']}, seed {meta['seed']}, "
        f"{sm['units']} units -> {sm['output_slides']} pages. This is a synthetic "
        "input, not a historical benchmark task."
    )
