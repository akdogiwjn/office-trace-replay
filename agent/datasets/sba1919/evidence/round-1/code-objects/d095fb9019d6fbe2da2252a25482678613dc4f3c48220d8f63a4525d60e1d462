#!/usr/bin/env python3
"""Author the SBA 1919 field mapping from inspected schema + supplied records.

Generates output/field_values/<id>.json for every applicant. Every field id is
validated against output/form_field_info.json (existence, page, and checkbox
export state) before any file is written.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "input"
OUTPUT = ROOT / "output"

# (field_id, record key) - plain text fields, taken verbatim from the record.
TEXT_FIELDS = [
    ("applicantname", "business_name"),
    ("operatingnbusname", "operating_name"),
    ("dba", "trade_name"),
    ("PrimarIndustry", "industry_code"),
    ("busphone", "phone"),
    ("yearbeginoperations", "operation_year"),
    ("Business Address", "business_address"),
    ("Project Address", "project_address"),
    ("Primary Contact Name", "contact_name"),
    ("Primary Contact Email Address", "contact_email"),
    (" of existing employees including owners all parttime fulltime and all employees of domestic and foreign Affiliates  do not convert to FTE",
     "existing_employees"),
    (" of FTE jobs savedretained because of the loan including owners", "retained_jobs"),
    (" of new FTE jobs created because of the loan including owners", "new_jobs"),
    ("Owners Legal Name First name Last nameRow1", "owner_name"),
    ("TitleRow1", "owner_title"),
    ("Ownership Row1", "owner_percentage"),
    ("Home Address Street City State Zip Code No PO BoxRow1", "owner_address"),
    ("Working Capital amount", "working_capital_amount"),
]

# (field_id, record path, value when true, value when false)
CHECKBOX_FIELDS = [
    ("OC", "flags.OC", "/On", "/Off"),
    ("EPC", "flags.EPC", "/On", "/Off"),
    ("soleprop", "flags.soleprop", "/Yes", "/Off"),
    ("partnership", "flags.partnership", "/Yes", "/Off"),
    ("ccorp", "flags.ccorp", "/Yes", "/Off"),
    ("scorp", "flags.scorp", "/Yes", "/Off"),
    ("llc", "flags.llc", "/Yes", "/Off"),
    ("etother", "flags.etother", "/Yes", "/Off"),
    ("working capital", "flags.working capital", "/On", "/Off"),
]

for n in range(1, 14):
    CHECKBOX_FIELDS.append((f"{n}yes", f"answers.{n}yes", "/Yes", "/Off"))
    CHECKBOX_FIELDS.append((f"{n}no", f"answers.{n}no", "/No", "/Off"))

PROTECTED_BLANK = {
    "401k or ROBS 401k Trust",
    "5a Provide the estimated total export sales this loan will support",
    "5b List of principal countries of Export list at least 1",
    "5b2 List of principal countries of Export list at least 1",
    "5b3 List of principal countries of Export list at least 1",
    "5initials",
    "Acquisition of Inventory",
    "Acquisition of inventory amount",
    "Acquisition/installation of equipment amount",
    "Acquisitioninstallation of equipment",
    "American Indian or Alaska Native",
    "Asian",
    "Black or African American",
    "Business TIN EIN SSN",
    "Business acquisition (Change of Ownership) amount",
    "Business acquisition Change of Ownership",
    "Cooperative",
    "Date",
    "Debt Refinancing amount",
    "DebtRefi",
    "Employee Stock Ownership Plan ESOP",
    "GenderNotDisclosed",
    "Hispanic or Latino",
    "Home Address Street City State Zip Code No PO BoxRow2",
    "Home Address Street City State Zip Code No PO BoxRow3",
    "Home Address Street City State Zip Code No PO BoxRow4",
    "Home Address Street City State Zip Code No PO BoxRow5",
    "Native Hawaiian or Pacific Islander",
    "NativeAmerican TribalOwned Business",
    "NonVeteran",
    "Not Disclosed",
    "Not Disclosed_ethnicity",
    "Not Disclosed_race",
    "Not Hispanic or Latino",
    "Other",
    "Other amount",
    "Other amount2",
    "OtherPurpose",
    "OtherPurpose2",
    "Owners Legal Name First name Last name",
    "Owners Legal Name First name Last nameRow2",
    "Owners Legal Name First name Last nameRow3",
    "Owners Legal Name First name Last nameRow4",
    "Owners Legal Name First name Last nameRow5",
    "Owners Position",
    "Ownership Row2",
    "Ownership Row3",
    "Ownership Row4",
    "Ownership Row5",
    "Print Name",
    "Purchase/Construction of Commercial Real Estate amount",
    "PurchaseConstruction of Commercial Real Estate",
    "ServiceDisabled Veteran",
    "Signature of Authorized Representative of Applicant",
    "Spouse of Veteran",
    "TIN SSNEINRow1",
    "TIN SSNEINRow2",
    "TIN SSNEINRow3",
    "TIN SSNEINRow4",
    "TIN SSNEINRow5",
    "Title",
    "TitleRow2",
    "TitleRow3",
    "TitleRow4",
    "TitleRow5",
    "UniqueEntityID",
    "Veteran",
    "White",
    "entityother",
    "female",
    "male",
    "otherpurp1",
    "otherpurp2",
    "speowntypeother",
}


def dig(record, dotted):
    value = record
    for key in dotted.split("."):
        value = value[key]
    return value


def main():
    field_info = json.loads((OUTPUT / "form_field_info.json").read_text())
    by_id = {f["field_id"]: f for f in field_info}
    records = json.loads((INPUT / "synthetic_applicants.json").read_text())["applicants"]

    planned_ids = [fid for fid, _ in TEXT_FIELDS] + [f[0] for f in CHECKBOX_FIELDS]
    missing = [fid for fid in planned_ids if fid not in by_id]
    if missing:
        print("ERROR: field ids absent from inspected schema:", missing)
        return 1
    overlap = sorted(set(planned_ids) & PROTECTED_BLANK)
    if overlap:
        print("ERROR: mapped fields collide with protected blank list:", overlap)
        return 1

    outdir = OUTPUT / "field_values"
    outdir.mkdir(parents=True, exist_ok=True)

    for record in records:
        ident = str(record["id"])
        values = []
        for fid, key in TEXT_FIELDS:
            values.append({
                "field_id": fid,
                "description": f"SBA 1919 {fid.strip()}",
                "page": by_id[fid]["page"],
                "value": str(dig(record, key)),
            })
        for fid, key, on_val, off_val in CHECKBOX_FIELDS:
            info = by_id[fid]
            if info["type"] != "checkbox":
                print(f"ERROR: {fid} is {info['type']}, expected checkbox")
                return 1
            if on_val not in (info["checked_value"], info["unchecked_value"]):
                print(f"ERROR: {on_val} not a valid state for {fid} "
                      f"(checked={info['checked_value']}, unchecked={info['unchecked_value']})")
                return 1
            if off_val not in (info["checked_value"], info["unchecked_value"]):
                print(f"ERROR: {off_val} not a valid state for {fid}")
                return 1
            flag = dig(record, key)
            values.append({
                "field_id": fid,
                "description": f"SBA 1919 {fid} ({key})",
                "page": info["page"],
                "value": on_val if flag is True else off_val,
            })
        (outdir / f"{ident}.json").write_text(json.dumps(values, indent=2) + "\n")
        print(f"wrote {outdir / (ident + '.json')} ({len(values)} fields)")

    print(f"Generated {len(records)} field-values files with {len(planned_ids)} mapped fields each; "
          f"{len(field_info) - len(planned_ids)} fields intentionally left blank.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
