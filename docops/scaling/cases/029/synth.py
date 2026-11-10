"""Synthetic PPTX 029 inputs: scaled QBR release-deck variants.

Produces the per-unit prepared material (units.json) and a synthetic source
presentation that contains messy internal draft slides, per-unit placeholder
slides, and a single trailing "Reference - Locked Legal" locked legal page.
The builder removes the internal/placeholder slides, rebuilds the eight public
release pages per unit with each unit's own KPI / risk / measure / decision
facts, and preserves the locked legal page from the source exactly at the last
position. The source legal page's text, shape count and speaker note are frozen
in units.json so the validator can compare them.
"""
from __future__ import annotations

import random
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches

from .. import common

PAGES_PER_UNIT = 8
RELEASE_DATE = "2026-06-05"

PREFIXES = [
    "Acme", "Northwind", "Harbor", "Summit", "Meridian", "Cobalt", "Evergreen",
    "Ironclad", "Bluefin", "Crestline", "Lumen", "Redwood", "Silverline",
    "Vantage", "Westfield", "Orchid", "Granite", "Pioneer", "Brighton",
    "Sequoia",
]
SUFFIXES = [
    "Retail Group", "Logistics", "Health Systems", "Financial", "Manufacturing",
    "Media", "Energy", "Software", "Hospitality", "Pharma",
]
OWNERS = [
    "Maya Chen", "Jon Bell", "Priya Rao", "Ana Torres", "Liam Novak",
    "Zoe Patel", "Omar Haddad", "Nina Kapoor",
]

# Token-boundary forbidden patterns mirrored from parent 029 validate.
FORBIDDEN_PATTERNS = [
    r"\bDraft:",
    r"\bWorking Copy\b",
    r"\bInternal\b",
    r"\bstaging\b",
    r"\bScratch Backup\b",
    r"\bDeprecated Roadmap\b",
    r"\bOld agenda\b",
    r"\bdo not publish\b",
]

TITLES = [
    "Title",
    "Agenda",
    "Market Context",
    "KPI Snapshot",
    "Customer Risks",
    "Mitigation Plan",
    "Decision Request",
    "Appendix - Data Notes",
]

KPI_HEADER = ["Metric", "Value", "QBR Readout"]
RISK_HEADER = ["Risk", "Account Count", "Owner", "Mitigation"]
MITIGATION_HEADER = ["Action", "Owner", "Due Date", "Status"]
ACTION_HEADER = ["Measure", "Target", "Owner", "Status"]
DECISION_HEADER = ["Decision", "Due", "Status"]
AGENDA_HEADER = ["Section", "Slide", "Owner"]
AGENDA_OWNERS = ["Maya Chen", "Jon Bell", "Priya Rao"]


def legal_slide_content(variant_id: str, seed: int) -> dict:
    release_id = f"QBR-{variant_id}-{seed}"
    return {
        "shape_count": 2,
        "texts": [
            "Reference - Locked Legal",
            "Confidentiality language approved by Legal. Do not alter this "
            f"slide. Release {release_id} | {RELEASE_DATE}",
        ],
        "notes": (
            "Locked legal note: preserve exact language for release "
            f"{release_id}."
        ),
    }


def make_units(n: int, rng: random.Random) -> list[dict]:
    if n < 1:
        raise ValueError("business unit count must be >= 1")
    units = []
    for index in range(n):
        name = (
            f"{PREFIXES[index % len(PREFIXES)]} "
            f"{SUFFIXES[(index // len(PREFIXES)) % len(SUFFIXES)]}"
        )
        owners = [OWNERS[(index + offset) % len(OWNERS)] for offset in range(3)]
        arr = rng.randint(28, 96)
        arr_growth = rng.randint(6, 14)
        nrr = rng.randint(88, 99)
        churn = rng.randint(2, 6)
        expansion = rng.randint(8, 18)
        renewal = rng.randint(1, 3)
        adoption = rng.randint(1, 2)
        support = rng.randint(1, 2)
        n_risk = renewal + adoption + support
        arr_text = f"{arr / 10:.1f}M"
        exp_text = f"{expansion / 10:.1f}M"
        units.append({
            "id": f"BU-{index + 1:03d}",
            "name": name,
            "owners": owners,
            "arr_text": arr_text,
            "arr_growth": arr_growth,
            "nrr": nrr,
            "churn_accounts": churn,
            "expansion_text": exp_text,
            "risk_counts": {"renewal": renewal, "adoption": adoption,
                            "support": support},
            "market_headline": (
                f"{name}: demand stable; enterprise support load is rising."
            ),
            "market_callouts": [
                ["01  Demand",
                 f"Market demand remains stable across the {name} enterprise segment."],
                ["02  Pressure",
                 f"Support volume is rising in {name} enterprise accounts."],
                ["03  Implication",
                 f"Prioritize renewal confidence and focused support coverage for {name}."],
            ],
            "market_lens": (
                f"Treat the {n_risk} at-risk {name} accounts as the bridge "
                "between a stable market and a below-target NRR."
            ),
            "kpi_rows": [
                ["ARR", arr_text, f"Up {arr_growth}% QoQ"],
                ["Churn risk", f"{churn} accounts", "Requires executive review"],
                ["NRR", f"{nrr}%", "Below target" if nrr < 100 else "On target"],
                ["Expansion pipeline", exp_text, "Two deals require support plan"],
            ],
            "risk_rows": [
                ["Renewal delay", str(renewal), owners[0],
                 "Executive outreach by 2026-06-10"],
                ["Adoption gap", str(adoption), owners[1],
                 "Enablement plan by 2026-06-12"],
                ["Support escalation", str(support), owners[2],
                 "Daily incident review"],
            ],
            "mitigation_rows": [
                ["Confirm renewal-risk owners", owners[0], "2026-06-07", "Open"],
                ["Publish enablement plan", owners[1], "2026-06-12", "Open"],
                ["Start daily incident review", owners[2], "2026-06-06", "Ready"],
            ],
            "action_rows": [
                ["Executive outreach plan",
                 f"{renewal} renewal-risk accounts", owners[0], "On track"],
                ["Enablement rollout", "All at-risk segments", owners[1], "Scheduled"],
                ["Daily incident review", "24h turnaround", owners[2], "Active"],
            ],
            "decision_rows": [
                [f"Approve executive outreach for {renewal} renewal-risk accounts.",
                 "2026-06-07", "Open"],
                ["Authorize enablement plan for NRR recovery.", "2026-06-07", "Open"],
                [f"Decision needed by 2026-06-07 for {name}.", "2026-06-07", "Required"],
            ],
            "decision_date": "2026-06-07",
            "decision_note": (
                f"Speaker note: ask for decision on renewal-risk outreach for "
                f"{name} before reviewing appendix."
            ),
            "data_notes": "Public source: QBR metrics workbook, 2026-06-05.",
            "data_currency": RELEASE_DATE,
            "summary": (
                f"{name} (BU-{index + 1:03d}) closes the "
                f"quarter with ARR {arr_text}, NRR {nrr}%, and {n_risk} at-risk "
                f"accounts. The release deck documents {renewal} renewal delays, "
                f"{adoption} adoption gaps, and {support} support escalations "
                "with named owners and dated mitigations."
            ),
            "page_notes": [
                f"Title for {name}: QBR Release, Quarterly Business Review, prepared for executive review.",
                f"Agenda for {name}: six sections aligned to the release sequence.",
                f"Market context for {name}: demand is stable while support load rises.",
                f"KPI snapshot for {name}: ARR {arr_text}, NRR {nrr}%, and "
                f"{churn} churn-risk accounts.",
                f"Customer risks for {name}: {n_risk} accounts across renewal, "
                "adoption, and support patterns.",
                f"Mitigation plan for {name}: three owned actions with dated due dates.",
                f"Decision request for {name}: approve outreach and enablement by 2026-06-07.",
                f"Appendix data notes for {name}: cite the public QBR metrics workbook "
                f"dated {RELEASE_DATE}.",
            ],
        })
    assert len({u["id"] for u in units}) == n
    assert len({u["name"] for u in units}) == n
    assert len({tuple(u["kpi_rows"][0]) for u in units}) == n
    for unit in units:
        assert all(unit["name"] in note for note in unit["page_notes"])
    return units


def _rgb_or_none(color) -> str | None:
    try:
        if color is not None and color.type is not None:
            return str(color.rgb) if color.rgb is not None else None
    except Exception:
        return None
    return None


def legal_semantic_snapshot(prs, slide_name: str = "Reference - Locked Legal") -> dict:
    """Normalized semantic snapshot of the frozen source legal slide.

    Includes only business-relevant semantics: slide background, ordered shapes
    (type, geometry, fill, line, text runs and fonts) and the speaker note.
    ZIP timestamps, relationship ids and part-name renumbering are NOT part of
    the snapshot, so unrelated repackaging cannot cause a false change.
    """
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    legal = next(s for s in prs.slides if s._element.cSld.get("name") == slide_name)
    bg_fill = legal.background.fill
    bg_type = str(bg_fill.type) if bg_fill.type is not None else None
    bg_rgb = _rgb_or_none(bg_fill.fore_color) if bg_fill.type == 1 else None
    shapes = []
    media = 0
    for sh in legal.shapes:
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
    notes = (legal.notes_slide.notes_text_frame.text if legal.has_notes_slide else "")
    return {"background": {"type": bg_type, "rgb": bg_rgb},
            "shapes": shapes, "media_count": media, "notes": notes}


def write_units_json(variant_id: str, units: list[dict], input_name: str,
                     out_dir: Path, legal_slide: dict) -> Path:
    data = {
        "schema": "docops-scaling-units-v1",
        "variant_task_id": variant_id,
        "seed": common.VARIANTS[variant_id]["seed"],
        "input_path": f"/root/{input_name}",
        "slides_per_unit": PAGES_PER_UNIT,
        "release_date": RELEASE_DATE,
        "titles": TITLES,
        "legal_slide": legal_slide,
        "units": units,
    }
    common.write_json(out_dir / "units.json", data)
    return out_dir / "units.json"


def write_source_pptx(units: list[dict], out_dir: Path, output_name: str,
                      legal_slide: dict) -> Path:
    """Messy internal source: fixed draft slides + per-unit placeholders +
    one trailing locked legal page."""
    import datetime as _dt
    import os as _os
    import tempfile

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    prs.core_properties.created = _dt.datetime(2026, 1, 1, 0, 0, 0)
    prs.core_properties.modified = _dt.datetime(2026, 1, 1, 0, 0, 0)
    blank = prs.slide_layouts[6]

    for heading, body, note in (
        ("Draft: QBR Release Deck - Working Copy",
         "Internal staging deck; remove draft labels.\n"
         "Old quarter narrative | Agenda not synced | Do not publish scratch metrics.",
         "Draft note: staging content, do not publish."),
        ("Scratch Backup",
         "Delete before release.\nOutdated logo test | Deprecated roadmap graphic.",
         "Draft note: backup slide, delete before publish."),
        ("Draft: Old Agenda",
         "Old agenda: metrics are on slide 5.",
         "Draft note: agenda out of sync."),
        ("Deprecated Roadmap",
         "Old feature timing, delete before publish.",
         "Draft note: deprecated content."),
    ):
        slide = prs.slides.add_slide(blank)
        slide.shapes.add_textbox(Inches(0.5), Inches(0.4), Inches(9), Inches(0.6)).text = heading
        slide.shapes.add_textbox(Inches(0.5), Inches(1.2), Inches(10), Inches(1.8)).text = body
        slide.notes_slide.notes_text_frame.text = note

    for unit in units:
        for page_index in range(PAGES_PER_UNIT):
            slide = prs.slides.add_slide(blank)
            slide._element.cSld.set("name", "Placeholder")
            slide.shapes.add_textbox(Inches(0.5), Inches(0.4), Inches(9), Inches(0.6)).text = (
                f"Placeholder - {unit['name']} ({unit['id']})"
            )
            slide.shapes.add_textbox(Inches(0.5), Inches(1.2), Inches(10), Inches(1.2)).text = (
                "Internal placeholder; rebuild public release pages."
            )
            slide.notes_slide.notes_text_frame.text = "Draft note: placeholder, do not publish."

    legal = prs.slides.add_slide(blank)
    legal._element.cSld.set("name", "Reference - Locked Legal")
    for index, text in enumerate(legal_slide["texts"]):
        box = legal.shapes.add_textbox(Inches(0.6), Inches(0.5 + index * 0.7),
                                       Inches(11.5), Inches(0.7))
        box.text_frame.text = text
    legal.notes_slide.notes_text_frame.text = legal_slide["notes"]
    assert len(legal.shapes) == legal_slide["shape_count"] == 2

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
        "arr_text": unit["arr_text"],
        "nrr": unit["nrr"],
        "churn_accounts": unit["churn_accounts"],
        "risk_counts": unit["risk_counts"],
        "decision_rows": unit["decision_rows"],
    }


def generate(variant_id: str, out_dir: Path, write_raw_records: bool = True) -> dict:
    v = common.VARIANTS[variant_id]
    n = v["scale"]["units"]
    rng = random.Random(v["seed"])
    units = make_units(n, rng)
    legal_slide = legal_slide_content(variant_id, v["seed"])

    out_dir.mkdir(parents=True, exist_ok=True)
    input_name = (
        f"docops_v2_l3_029_pptx_qbr_release_deck_input_"
        f"{v['output_suffix']}.pptx"
    )
    input_path = write_source_pptx(units, out_dir, input_name, legal_slide)
    _prs = Presentation(str(input_path))
    legal_slide = dict(legal_slide)
    legal_slide["semantic_snapshot"] = legal_semantic_snapshot(_prs)
    units_path = write_units_json(variant_id, units, input_name, out_dir, legal_slide)

    if write_raw_records:
        common.write_json(
            out_dir / "raw_records.json",
            {"schema": "docops-scaling-raw-records-v1",
             "variant_task_id": variant_id,
             "records": units},
        )

    input_slides = len(_prs.slides)
    output_slides = n * PAGES_PER_UNIT + 1

    parameterized_ranges = [
        f"{n} business units x {PAGES_PER_UNIT} public release slides per unit "
        "+ 1 preserved locked legal page",
        "per-unit KPI snapshot table (4 rows x 3 cols)",
        "per-unit customer-risk table (3 rows x 4 cols)",
        "per-unit mitigation plan table (3 rows x 4 cols)",
        "per-unit title and agenda slides (agenda lists the six sections "
        "with per-unit absolute slide numbers and owners)",
        "per-unit market-context callout cards (3)",
        "per-unit decision request cards (3 statements) and speaker note",
        "per-unit public page footers 'Slide i of <total>'",
        "single preserved source locked legal page (never rebuilt)",
    ]

    scale_metadata = {
        "units": n,
        "unit_ids": [u["id"] for u in units],
        "slides_per_unit": PAGES_PER_UNIT,
        "input_slides": input_slides,
        "output_slides": output_slides,
        "expected_output_slides": f"{n} x {PAGES_PER_UNIT} + 1 = {output_slides}",
        "render_scope": (
            "first page only (pdftoppm -jpeg -r 150 -f 1 -l 1); the release "
            "deck is validated structurally before rendering"
        ),
        "expected_render_images": 1,
        "locked_legal_slide": {
            "preserved_from_source": True,
            "shape_count": legal_slide["shape_count"],
            "texts": legal_slide["texts"],
            "notes": legal_slide["notes"],
        },
        "first_unit": _unit_summary(units[0]),
        "middle_unit": _unit_summary(units[n // 2]),
        "last_unit": _unit_summary(units[-1]),
        "parameterized_ranges": parameterized_ranges,
        "preserved_parent_behavior": [
            "locked legal reference page preserved exactly from the source "
            "(text, shape count and speaker note) and kept in the final position",
            "token-boundary forbidden draft terms removed from all visible text",
            "QBR table headers, style_cell coloring and callout layout reused",
            "decision speaker note retained verbatim per unit",
            "release footer format 'QBR Release | 2026-06-05' with "
            "'Slide i of <total>' on public pages",
        ],
        "changed_parent_behavior": [
            "the parent's single fixed 9-slide deck becomes a per-unit "
            "iteration: units.json drives N x 8 public release pages",
            "KPI / risk / mitigation / decision / market-context / appendix "
            "facts are per-unit, not the frozen parent rows",
            "slide-number footer total becomes 8N+1 instead of 9",
            "rendering scope restricted to the first page only "
            "(pdftoppm -f 1 -l 1)",
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
        f"docops_v2_l3_029_pptx_qbr_release_deck_output_"
        f"{v['output_suffix']}.pptx"
    )
    meta["modified_workflow"] = [
        "01 build_validate_render: builder reads units.json, cleans internal "
        "draft/placeholder slides, rebuilds 8 public release pages per unit "
        "(KPI/risk/mitigation/measure/decision tables with per-unit facts), "
        "preserves the locked legal page from the source in the final position "
        "and renders only the first page (pdftoppm -f 1 -l 1); dynamic "
        "validator checks every unit table and the locked legal page against "
        "the frozen expected.json",
    ]
    meta["measurement_scope"] = (
        "Measures per-business-unit document generation, validation, conversion "
        "and rendering scale: units -> 8 public release slides each plus one "
        "preserved locked legal page (5 -> 41, 10 -> 81). The synthetic source "
        "presentation's own page count is NOT what this variant parses or "
        "repairs; only the first page is rendered while every unit's tables, "
        "notes and the locked legal page are validated. Distinguish input PPTX "
        "pages vs unit count vs expected output pages."
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
`029`. It is NOT a historical benchmark task and has no official score of its own.

## Provenance

- `parent_task`: 029 (frozen `docops_v2_l3_029_pptx_qbr_release_deck`)
- `synthetic`: true
- generator: {meta['generator']} (version {meta['generator_version']})
- seed: {meta['seed']}
- scale: {sm['units']} business units x {sm['slides_per_unit']} public slides
  per unit + 1 locked legal page = {sm['output_slides']} output pages

## Inputs

- Source presentation: `{meta['input_path']}`
- Frozen business-unit material: `/root/tmp/docs/units.json`
- Frozen expected oracle: `/root/tmp/docs/expected.json`
- Original benchmark seed description: `/root/original_task_description.txt`

## Goal

Convert a messy synthetic QBR release deck from draft staging state into a
release-ready presentation using the same ordered workflow as parent task 029,
with a full eight-page public release set per business unit in `units.json` and
the shared locked legal reference page preserved exactly from the source.

## Required Sequential Workflow

1. Delete scratch/deprecated internal slides and per-unit placeholders; remove
   draft labels and stale content.
2. For every business unit in `units.json` build the eight public release
   pages: Market Context, KPI Snapshot, Customer Risks, Mitigation Plan,
   Decision Request, Action Register, Data Notes, Unit Summary.
3. Generate real per-unit KPI / risk / measure / decision tables with each
   unit's own facts.
4. Add the release footer `QBR Release | 2026-06-05` and `Slide i of <total>`
   on every public page.
5. Preserve the trailing `Reference - Locked Legal` page from the source
   exactly (text, shapes and speaker note unchanged) and keep it in the final
   position.
6. Save the release deck without modifying the source in place.

## Output Requirements

- Save to `{meta['output_path']}`.
- Keep the output format the same as the input presentation (`.pptx`).
- Complete the full ordered workflow, not just local text replacement.
"""


def original_description(meta: dict) -> str:
    sm = meta["scale_metadata"]
    return (
        "Synthetic scale variant of frozen task 029: QBR release deck. Source "
        "contains draft/scratch internal slides, per-unit placeholders, stale "
        "agenda and a locked legal reference page that must be preserved "
        "exactly. Scale is defined by the number of business units; each unit "
        "produces eight public release pages with its own KPI / risk / measure / "
        "decision facts, plus one shared locked legal page. "
        f"Variant {meta['variant_task_id']}, seed {meta['seed']}, "
        f"{sm['units']} units -> {sm['output_slides']} pages. This is a "
        "synthetic input, not a historical benchmark task."
    )
