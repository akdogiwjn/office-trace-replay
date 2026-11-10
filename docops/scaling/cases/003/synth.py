"""Synthetic Word 003 inputs: scaled water-main-break public release packets.

A business unit is one reimbursement claim that must go through the full frozen
003 workflow (tracked-change resolution, comment removal, metadata cleanup,
correction memo, working-content redaction, public-content rebuild, final OOXML
safety pass, audit and rendering). This generator produces:

- ``units.json``: the frozen business-unit declaration (unique ids, corrected
  facts, required/forbidden content) that drives the parameterized builder and
  the independent expected oracle.
- a synthetic source DOCX that actually contains, for every unit, the messy
  working content the frozen processing stages must handle: per-unit tracked
  changes, comments, correction-memo values and private working records.

OOXML identifiers (comment ids, bookmark ids, del/ins ids) are allocated with
distinct namespaces so no dangling relationship or duplicate id is produced.
Generation is byte-deterministic for a fixed seed/params.
"""
from __future__ import annotations

import datetime
import json
import random
import re
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from .. import common

CAP = 650  # reimbursable cap per eligible claim (frozen public policy fact)
INCIDENT_DATE = "2026-01-18"
DEADLINE = "2026-08-15"
CONTACT = "Public Records Desk"

CATEGORIES = [
    "Residential service line damage",
    "Interior property damage",
    "Emergency repair costs",
    "Documentation and administrative costs",
]

# Unique per-unit draft statuses (each appears exactly once, so a correction
# memo token like "Pending" -> "Approved" is globally unambiguous).
DRAFT_STATUSES = [
    "Pending", "Under review", "Awaiting verification", "Incomplete submission",
    "Reopened", "Queued", "On hold", "Review scheduled", "Scanned", "Logged",
    "Verified pending", "Awaiting docs", "Sent for review", "Correction queued",
    "In inspection", "Clarification", "Recheck", "Awaiting decision",
    "Forwarded", "Hold for review",
]
RIGHT_STATUSES = ["Approved", "Denied"]

FIRST_NAMES = ["Nora", "Leo", "Mia", "Noah", "Zoe", "Eli", "June", "Owen",
               "Ivy", "Kai", "Ruth", "Sam", "Wren", "Felix", "Vera", "Hugo",
               "Lena", "Omar", "Tess", "Axel"]
LAST_NAMES = ["Kim", "Cheng", "Patel", "Rossi", "Novak", "Ito", "Sato",
              "Larsen", "Mendes", "Fischer", "Owens", "Silva", "Thorne", "Wu",
              "Park", "Ali", "Bauer", "Reed", "Grant", "Perez",
              "Okafor", "Nguyen", "Romano", "Banks", "Holt", "Vega",
              "Quinn", "Sloan", "Mercer", "Doyle"]
STREETS = ["14 Pine Street", "88 Lake Avenue", "5 West Road", "22 Cedar Lane",
           "9 Birch Court", "71 Elm Drive", "3 Maple Street", "45 Oak Terrace"]
PRIVATE_NOTES = [
    "unverified hardship narrative", "PRIVATE intake note", "legal hold",
    "duplicate scratch row", "DRAFT review note", "appeal note",
    "attorney-client settlement note",
]

# Global correction memo (mirrors the frozen parent source values).
GLOBAL_CORRECTION_LINES = [
    "Incident date is currently listed as 2026-01-08 but should be 2026-01-18.",
    "Claim count says 34 claims but deduplicated public count should be 37.",
    "Reimbursable cap says $500 but corrected public cap is $650.",
    "Public contact should not name Marcus Vale or Eliza Park; use Public Records Desk.",
    "Response deadline currently says 2026-07-31 but should be 2026-08-15.",
]

HEADER_LINES = [
    "DRAFT Internal Water Main Break Claims Packet",
    "PRIVATE reviewer: Nora Chen. Personal phone 555-0174. Attorney-client "
    "legal strategy note: settlement exposure",
    "Correction Memo - INTERNAL",
]
BODY_BANNER_LINES = [
    "Raw Claimant Notes",
    "Draft Release Outline",
    "DRAFT public packet will be rebuilt after comments and tracked changes are resolved.",
    "INTERNAL tracked-change review block follows.",
]


def make_units(n: int, rng: random.Random) -> list[dict]:
    """Deterministic per-variant business units.

    Wrong amounts and wrong statuses are unique across the whole document so the
    correction memo keys are globally unambiguous (substring replacement is safe).

    For arbitrarily large unit counts the pools are widened without changing the
    business semantics:

    - wrong draft amounts are 4-digit values in [6500, 9999] (above the $650
      corrected cap, as draft errors may be), so no corrected right amount is a
      substring of any wrong amount and keys cannot cross-match;
    - corrected right amounts are unique values in [100, 649] (<= the $650 cap)
      with 500 excluded (the global memo source key), all same-width 3-digit so
      no right amount is a substring of another;
    - wrong statuses stay realistic for the first 20 and get a deterministic
      unique qualifier beyond that;
    - claimant names are unique via 20 x 30 name combinations;
    - addresses are unique via a deterministic per-unit numeric suffix.
    """
    if n < 1:
        raise ValueError("unit count must be >= 1")
    wrong_amounts = rng.sample(list(range(6500, 10000)), n)
    right_amounts = rng.sample(sorted(set(range(100, 650)) - {500}), n)
    assert len(wrong_amounts) == len(set(wrong_amounts)) == n
    assert len(right_amounts) == len(set(right_amounts)) == n
    assert all(100 <= r <= 649 and r != 500 for r in right_amounts)
    assert all(6500 <= w <= 9999 for w in wrong_amounts)
    assert not (set(map(str, right_amounts)) & set(map(str, wrong_amounts)))
    # wrong/right amounts can never collide as substrings: right amounts are
    # 3-digit [100,649], wrong amounts are 4-digit [6500,9999] whose leading
    # 3 digits are >= 650, so no "$right" is a prefix of any "$wrong".
    statuses = [
        DRAFT_STATUSES[i] if i < len(DRAFT_STATUSES)
        else f"{DRAFT_STATUSES[i % len(DRAFT_STATUSES)]} ({i + 1})"
        for i in range(n)
    ]
    assert len(statuses) == len(set(statuses)) == n
    if len(FIRST_NAMES) * len(LAST_NAMES) < n:
        raise ValueError("name pool too small for unit count")
    units = []
    for index in range(n):
        claimant = f"{FIRST_NAMES[index % len(FIRST_NAMES)]} " \
                   f"{LAST_NAMES[(index // len(FIRST_NAMES)) % len(LAST_NAMES)]}"
        units.append({
            "id": f"CLM-{index + 1:03d}",
            "claimant": claimant,
            "address": f"{STREETS[index % len(STREETS)]} {index + 1:03d}",
            "phone": f"555-{index + 10:02d}",
            "category": rng.choice(CATEGORIES),
            "wrong_amount": wrong_amounts[index],
            "right_amount": right_amounts[index],
            "wrong_status": statuses[index],
            "right_status": rng.choice(RIGHT_STATUSES),
            "note": rng.choice(PRIVATE_NOTES),
        })
    assert len({u["claimant"] for u in units}) == n
    assert len({u["address"] for u in units}) == n
    assert len({u["phone"] for u in units}) == n
    return units


def write_units_json(variant_id: str, units: list[dict], out_dir: Path) -> Path:
    data = {
        "schema": "docops-scaling-units-v1",
        "variant_task_id": variant_id,
        "seed": common.VARIANTS[variant_id]["seed"],
        "incident_date": INCIDENT_DATE,
        "deadline": DEADLINE,
        "contact": CONTACT,
        "cap": CAP,
        "categories": CATEGORIES,
        "units": units,
    }
    common.write_json(out_dir / "units.json", data)
    return out_dir / "units.json"


def _ins_del_pair(p, anchor_run, del_text, ins_text, cid):
    """Wrap a tracked deletion/insertion after ``anchor_run`` in paragraph ``p``."""
    anchor = anchor_run._r

    del_el = OxmlElement("w:del")
    del_el.set(qn("w:id"), str(cid))
    del_el.set(qn("w:author"), "Reviewer")
    del_el.set(qn("w:date"), "2026-11-02T00:00:00Z")
    del_run = OxmlElement("w:r")
    del_text_el = OxmlElement("w:delText")
    del_text_el.text = del_text
    del_run.append(del_text_el)
    del_el.append(del_run)

    ins_el = OxmlElement("w:ins")
    ins_el.set(qn("w:id"), str(cid + 1))
    ins_el.set(qn("w:author"), "Reviewer")
    ins_el.set(qn("w:date"), "2026-11-02T00:00:00Z")
    ins_run = OxmlElement("w:r")
    ins_text_el = OxmlElement("w:t")
    ins_text_el.text = ins_text
    ins_run.append(ins_text_el)
    ins_el.append(ins_run)

    anchor.addnext(ins_el)
    anchor.addnext(del_el)


def _add_bookmark(p, name, bid):
    bs = OxmlElement("w:bookmarkStart")
    bs.set(qn("w:id"), str(bid))
    bs.set(qn("w:name"), name)
    be = OxmlElement("w:bookmarkEnd")
    be.set(qn("w:id"), str(bid))
    runs = p._p.findall(qn("w:r"))
    if runs:
        runs[0].addprevious(bs)
        runs[-1].addnext(be)
    else:
        p._p.insert(0, bs)
        p._p.append(be)


def write_source_docx(units: list[dict], out_dir: Path, input_name: str) -> Path:
    doc = Document()
    doc.core_properties.author = "DocOps synthetic scale generator"
    doc.core_properties.last_modified_by = "DocOps synthetic scale generator"
    doc.core_properties.title = "DRAFT Internal Water Main Break Claims Packet"
    doc.core_properties.created = datetime.datetime(2026, 11, 2, 0, 0, 0)
    doc.core_properties.modified = datetime.datetime(2026, 11, 2, 0, 0, 0)

    next_manual_id = 1000  # distinct id space for bookmarks and tracked changes

    for line in HEADER_LINES:
        doc.add_paragraph(line)
    for line in GLOBAL_CORRECTION_LINES:
        doc.add_paragraph(line)
    for line in BODY_BANNER_LINES:
        doc.add_paragraph(line)

    # One global tracked-change block so stage-1 resolution has work to do
    # beyond the per-unit blocks.
    global_tc = doc.add_paragraph()
    g1 = global_tc.add_run("This internal block was ")
    _ins_del_pair(global_tc, g1, "DRAFT", "REVIEWED", next_manual_id)
    next_manual_id += 2
    global_tc.add_run(" for publication review.")

    for unit in units:
        heading = doc.add_paragraph(
            f"Unit {unit['id']} — Internal Working Record (DRAFT)",
            style="Heading 2",
        )
        _add_bookmark(heading, f"unit-{unit['id']}", next_manual_id)
        next_manual_id += 1

        private_line = doc.add_paragraph(
            f"Claimant: {unit['claimant']}. Address: {unit['address']}. "
            f"Phone: {unit['phone']}. PRIVATE reviewer note: {unit['note']}."
        )
        comment_run = private_line.add_run(" [review this record]")
        doc.add_comment(
            [comment_run],
            text=f"reviewer: verify the working values and private note for "
                 f"{unit['id']}; do not publish.",
            author="Internal Reviewer",
            initials="IR",
        )

        correction = doc.add_paragraph()
        c1 = correction.add_run(
            f"Claim {unit['id']} correction: draft amount listed as "
        )
        c2 = correction.add_run(f"${unit['wrong_amount']}")
        c3 = correction.add_run("; corrected public amount is ")
        c4 = correction.add_run(f"${unit['right_amount']}")
        c5 = correction.add_run(". Status marked ")
        c6 = correction.add_run(unit["wrong_status"])
        c7 = correction.add_run("; corrected status is ")
        c8 = correction.add_run(unit["right_status"])
        c9 = correction.add_run(".")
        _ins_del_pair(correction, c1, "DRAFT", "REVIEWED", next_manual_id)
        next_manual_id += 2
        _ins_del_pair(correction, c8, "old", "final", next_manual_id)
        next_manual_id += 2

        table = doc.add_table(rows=0, cols=2)
        table.style = "Table Grid"
        for field, value in [
            ("Business ID", unit["id"]),
            ("Claimant", unit["claimant"]),
            ("Home Address", unit["address"]),
            ("Phone", unit["phone"]),
            ("Claim category", unit["category"]),
            ("Amount listed", f"${unit['wrong_amount']}"),
            ("Status marked", unit["wrong_status"]),
            ("Private note", unit["note"]),
        ]:
            cells = table.add_row().cells
            cells[0].text = field
            cells[1].text = value

    output = out_dir / input_name
    tmp = output.parent / f".tmp-{input_name}"
    doc.save(str(tmp))
    fixed_date = b"2026-11-02T00:00:00Z"

    def comments_fix(data):
        # python-docx stamps comment w:date with the current time; pin it so the
        # same seed/params always produce identical bytes.
        return re.sub(rb'(w:date=")[^"]*(")',
                      rb"\g<1>" + fixed_date + rb"\g<2>", data)

    common.deterministic_zip(tmp, output, transform={"word/comments.xml": comments_fix})
    tmp.unlink(missing_ok=True)
    return output


def generate(variant_id: str, out_dir: Path, write_raw_records: bool = True) -> dict:
    v = common.VARIANTS[variant_id]
    n = v["scale"]["business_units"]
    seed = v["seed"]
    rng = random.Random(seed)
    units = make_units(n, rng)

    out_dir.mkdir(parents=True, exist_ok=True)
    units_path = write_units_json(variant_id, units, out_dir)
    input_name = (
        f"docops_v2_l3_003_docx_public_records_release_metadata_cleanup_input_"
        f"{v['output_suffix']}.docx"
    )
    input_path = write_source_docx(units, out_dir, input_name)

    # Measure the actual generated source structure (body paragraphs and tables).
    src_doc = Document(str(input_path))
    src_paragraphs = len(src_doc.paragraphs)
    src_tables = len(src_doc.tables)
    src_table_rows = sum(len(t.rows) for t in src_doc.tables)

    if write_raw_records:
        common.write_json(
            out_dir / "raw_records.json",
            {"schema": "docops-scaling-raw-records-v1",
             "variant_task_id": variant_id,
             "records": units},
        )

    scale_metadata = {
        "business_units": n,
        "unit_ids": [u["id"] for u in units],
        "cap": CAP,
        "incident_date": INCIDENT_DATE,
        "deadline": DEADLINE,
        "contact": CONTACT,
        "source_paragraphs": src_paragraphs,
        "source_tables": src_tables,
        "source_table_rows": src_table_rows,
        "comments": n,
        "tracked_changes": 2 * n + 1,   # per unit ins/del pairs + global block
        "bookmarks": n,
        "expected_output_tables": n + 3,  # aggregate + N units + category + checklist
        "expected_output_headings": 4 + n + 4,
        "category_counts": {
            cat: sum(1 for u in units if u["category"] == cat)
            for cat in CATEGORIES
        },
        "input_bytes": input_path.stat().st_size,
        "input_sha256": common.sha256_file(input_path),
        "units_json_sha256": common.sha256_file(units_path),
        "seed": seed,
    }

    meta = common.default_task_metadata(variant_id)
    meta["scale_metadata"] = scale_metadata
    meta["input_path"] = f"/root/{input_name}"
    meta["output_path"] = (
        f"/root/submission/"
        f"docops_v2_l3_003_docx_public_records_release_metadata_cleanup_output_"
        f"{v['output_suffix']}.docx"
    )
    meta["modified_workflow"] = [
        "01 build: stage order and processing tools unchanged; the correction "
        "memo is derived from the frozen units.json (global + per-unit tokens) "
        "and the public rebuild iterates all N units (one determination table "
        "per unit), so output size is driven by the actual unit count",
        "02 validate: dynamic validator reads frozen expected.json and covers "
        "every unit plus document-level controls (metadata/style checks run "
        "once, not repeated per unit)",
        "03 render: unchanged render_docx.py (LibreOffice -> PDF -> 150 DPI "
        "PNGs); page count is decided by real layout",
    ]
    meta["measurement_scope"] = (
        "Scales the number of reimbursement claim business units that must go "
        "through the full frozen 003 pipeline: tracked-change resolution, "
        "comment removal, metadata cleanup, correction memo, working-content "
        "redaction, per-unit public rebuild, final OOXML safety pass, audit and "
        "render. Both the source DOCX working content and the final public "
        "packet scale with the unit count. Page count is decided by real "
        "LibreOffice layout; no page count is forged here."
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
`003`. It is NOT a historical benchmark task and has no official score of its own.

## Provenance

- `parent_task`: 003 (frozen `docops_v2_l3_003_docx_public_records_release_metadata_cleanup`)
- `synthetic`: true
- generator: {meta['generator']} (version {meta['generator_version']})
- seed: {meta['seed']}
- scale: {sm['business_units']} business units (reimbursement claims)

## Inputs

- Source document: `{meta['input_path']}`
- Frozen business-unit declaration: `/root/tmp/docs/units.json`
- Frozen expected oracle: `/root/tmp/docs/expected.json`
- Original benchmark seed description: `/root/original_task_description.txt`

## Goal

Prepare a clean public records release packet from a messy internal Word
document about water main break reimbursement claims. Every declared business
unit in `units.json` must go through the same sequential workflow as parent task
003, and every unit's corrected public facts must appear in the final packet.

## Required Sequential Workflow

1. Accept or resolve tracked changes before rebuilding the public packet.
2. Delete all comments and comment references.
3. Remove private metadata from document properties.
4. Apply the correction memo (global facts plus every unit's corrected amount /
   status) before rebuilding the public facts, tables, workflow, and appendix.
5. Remove all PII, legal-strategy notes, draft-only content, and private staff
   names.
6. Rebuild the public release packet from `units.json`: one corrected
   determination table per unit, the aggregate determination/category tables,
   footer, page breaks, and styles.
7. Save the clean public document as a new `.docx` without modifying the source.

## Required Corrections

Global (from the frozen parent memo): incident date `2026-01-18`, claim count
`{sm['business_units']}`, cap `$650`, public contact `Public Records Desk`,
response deadline `2026-08-15`. Per-unit amount/status corrections are declared
in `units.json`.

## Required Style and Layout

- Use `Aptos Display` bold title text, 18 pt, color `1F4E79`.
- Use `Aptos` body text, 10.5 pt.
- Use heading text in color `1F4E79`.
- Use table header fill `1F4E79` with white bold text.
- Set all page margins to `0.75` inches.
- Add footer text `Public Records Release | Water Main Break Claims | 2026`.

## Output Requirements

- Save to `{meta['output_path']}`.
- Do not modify the source document in place.
- Keep the output format the same as the input document (`.docx`).
- Complete the full ordered workflow, not just local text replacement.
"""


def original_description(meta: dict) -> str:
    sm = meta["scale_metadata"]
    return (
        "Synthetic scale variant of frozen task 003: public records release "
        "packet for water main break reimbursement claims. The source contains "
        f"{sm['business_units']} business units, each with per-unit tracked "
        "changes, comments, correction-memo values and private working records. "
        "Scale is defined by the number of business units that must pass "
        "through the whole frozen pipeline and appear in the final packet. "
        f"Variant {meta['variant_task_id']}, seed {meta['seed']}. "
        "This is a synthetic input, not a historical benchmark task."
    )
