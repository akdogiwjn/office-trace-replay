#!/usr/bin/env python3
"""Author per-record field_values JSON for the frozen 2026 IRS W-4 dataset.

Mapping is fixed by the task brief / dataset manifest (14 declared business
fields). Pages come from output/form_field_info.json produced by the bundled
extract_form_field_info.py (run exactly once).
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "input"
OUTPUT = ROOT / "output"

# (field_id, semantic, page) -- page numbers confirmed from form_field_info.json
TEXT_FIELDS = [
    ("topmostSubform[0].Page1[0].Step1a[0].f1_01[0]", "first_name", 1),
    ("topmostSubform[0].Page1[0].Step1a[0].f1_02[0]", "last_name", 1),
    ("topmostSubform[0].Page1[0].Step1a[0].f1_03[0]", "address", 1),
    ("topmostSubform[0].Page1[0].Step1a[0].f1_04[0]", "city_state_zip", 1),
    ("topmostSubform[0].Page1[0].Step3_ReadOrder[0].f1_06[0]", "children_credit", 1),
    ("topmostSubform[0].Page1[0].Step3_ReadOrder[0].f1_07[0]", "other_dependents_credit", 1),
    ("topmostSubform[0].Page1[0].f1_08[0]", "total_credit", 1),
    ("topmostSubform[0].Page1[0].f1_09[0]", "other_income", 1),
    ("topmostSubform[0].Page1[0].f1_10[0]", "deductions", 1),
    ("topmostSubform[0].Page1[0].f1_11[0]", "extra_withholding", 1),
]

# (field_id, semantic, page, checked_value) -> checkbox; false => /Off
CHECKBOX_FIELDS = [
    ("topmostSubform[0].Page1[0].c1_1[0]", "filing_flags.single", 1, "/1"),
    ("topmostSubform[0].Page1[0].c1_1[1]", "filing_flags.married", 1, "/2"),
    ("topmostSubform[0].Page1[0].c1_1[2]", "filing_flags.head_of_household", 1, "/3"),
    ("topmostSubform[0].Page1[0].c1_2[0]", "multiple_jobs", 1, "/1"),
]


def lookup(record, dotted):
    value = record
    for key in dotted.split("."):
        value = value[key]
    return value


def main():
    info = json.loads((OUTPUT / "form_field_info.json").read_text())
    pages = {f["field_id"]: f["page"] for f in info}
    types = {f["field_id"]: f["type"] for f in info}

    records = json.loads((INPUT / "synthetic_employees.json").read_text())["employees"]
    (OUTPUT / "field_values").mkdir(parents=True, exist_ok=True)

    for record in records:
        entries = []
        for field_id, semantic, page in TEXT_FIELDS:
            assert pages[field_id] == page, field_id
            assert types[field_id] == "text", field_id
            entries.append({
                "field_id": field_id,
                "description": f"{semantic} for {record['id']}",
                "page": page,
                "value": str(lookup(record, semantic)),
            })
        for field_id, semantic, page, checked in CHECKBOX_FIELDS:
            assert pages[field_id] == page, field_id
            assert types[field_id] == "checkbox", field_id
            flag = lookup(record, semantic)
            entries.append({
                "field_id": field_id,
                "description": f"{semantic} for {record['id']}",
                "page": page,
                "value": checked if flag else "/Off",
            })
        path = OUTPUT / "field_values" / f"{record['id']}.json"
        path.write_text(json.dumps(entries, indent=2) + "\n")
        print(f"wrote {path.relative_to(ROOT)} ({len(entries)} fields)")


if __name__ == "__main__":
    main()
