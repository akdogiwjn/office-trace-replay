#!/usr/bin/env python3
"""Parse py-spy raw (--subprocesses) output into per-role Python-stack tables
and per-role mechanism composition (used by the native classifier rule R6).

py-spy caches a process cmdline at first sight, which can be the pre-exec
(forked-from-runner) command line. Role resolution therefore uses BOTH the
process-prefix cmdline and, when that is stale or empty, the `<module>
(script.py:N)` root frame of the stack. verify_office.py / summary.py are
disambiguated by the scene read from the run metadata.
"""
import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
from script_identity import role_for_command, role_for_script

PROC = re.compile(r'^process (\d+):"(.*)"$')
MODULE_FRAME = re.compile(r'<module> \(([^)(]+\.py):\d+\)')

ROLE_RULES = [
    (r"run_document_scene_loop\.py", "runner"),
    (r"replay/entry\.py", "runner"),
    (r"check_fillable_fields\.py", "pdf-check-fillable"),
    (r"extract_form_field_info\.py", "pdf-extract-fields"),
    (r"convert_pdf_to_images\.py", "pdf-convert"),
    (r"fill_fillable_fields\.py", "pdf-fill"),
    (r"verify_pdf_batch\.py", "pdf-verify"),
    (r"generate_and_run_batch\.py|build_field_values\.py|"
     r"run_batch_fill_render\.py|pdf_batch\.py", "pdf-mapping-driver"),
    (r"write_pdf_batch_summary\.py", "pdf-summary-writer"),
    (r"inspect_xlsx_structure\.py", "xlsx-inspect-structure"),
    (r"inspect_xlsx_features\.py", "xlsx-inspect-features"),
    (r"enhance_workbook\.py|build_enhance|build_enhanced", "xlsx-enhance"),
    (r"[/ ]\.?build(\.runtime)?\.py", "xlsx-enhance"),
    (r"run_xlsx_helper_atomic\.py", "xlsx-atomic-helper"),
    (r"recalc\.py", "xlsx-recalc"),
    (r"inspect_xlsx_formulas\.py", "xlsx-inspect-formulas"),
    (r"inspect_xlsx_cached_values\.py", "xlsx-inspect-cached"),
    (r"verify_xlsx_enhanced\.py", "xlsx-verify"),
    (r"write_xlsx_summary\.py|export_xlsx\.py", "xlsx-summary-export"),
    (r"inspect_xlsx\.py", "xlsx-inspect-tool"),
    (r"\s-c\s|python3\s+-c", "python-inline"),
]

LEAF_RULES = [
    (r"\(openpyxl/(reader|packaging|worksheet/_reader|utils/datetime|styles/stylesheet)",
     "M-XLSX-LOAD"),
    (r"load_workbook|read_workbook|find_sheet", "M-XLSX-LOAD"),
    (r"\(xml/(parsers/expat|etree)", "M-XLSX-LOAD"),
    (r"\(pyexpat", "M-XLSX-LOAD"),
    (r"Parse \(openpyxl", "M-XLSX-LOAD"),
    (r"\(openpyxl/(writer|worksheet/_writer|worksheet/_write_only)", "M-XLSX-SAVE"),
    (r"\(et_xmlfile", "M-XLSX-SAVE"),
    (r"save_workbook|write_workbook", "M-XLSX-SAVE"),
    (r"\(pypdf/", None),
    (r"\(PIL/|pdf2image", "M-PILLOW-IMG"),
    (r"\(json/(encoder|decoder|__init__|scanner)", "M-JSON-MAPPING"),
    (r"dumps \(json|loads \(json", "M-JSON-MAPPING"),
    (r"\(subprocess\.py|\(genericpath|os\.scandir|\(shutil\.py", "M-ORCH"),
    (r"\(gzip|zipfile", "M-XLSX-LOAD"),
]

ROLE_DEFAULT_MECH = {
    "pdf-check-fillable": "M-PDF-QPDF-PARSE",
    "pdf-extract-fields": "M-PDF-QPDF-PARSE",
    "pdf-verify": "M-PDF-QPDF-PARSE",
    "pdf-fill": "M-PDF-FORMFILL",
    "pdf-convert": "M-PILLOW-IMG",
    "pdf-mapping-driver": "M-JSON-MAPPING",
    "pdf-summary-writer": "M-JSON-MAPPING",
    "xlsx-inspect-structure": "M-XLSX-TRAVERSE",
    "xlsx-inspect-features": "M-XLSX-TRAVERSE",
    "xlsx-enhance": "M-XLSX-SAVE",
    "xlsx-atomic-helper": "M-ORCH",
    "xlsx-recalc": "M-ORCH",
    "xlsx-inspect-formulas": "M-XLSX-TRAVERSE",
    "xlsx-inspect-cached": "M-XLSX-TRAVERSE",
    "xlsx-verify": "M-XLSX-TRAVERSE",
    "xlsx-summary-export": "M-XLSX-TRAVERSE",
    "xlsx-inspect-tool": "M-XLSX-TRAVERSE",
    "python-inline": "M-JSON-MAPPING",
    "runner": "M-ORCH",
}

PRELOOP_FRAMES = re.compile(
    r"validate_project|validate_dataset|\bdigest\b|sha256|_hashopenssl|"
    r"replay/|probe_environment|importlib\.metadata")


def script_role(name, scene):
    """Resolve exact script operand or the basename-only module frame."""
    return role_for_command(name, scene) or role_for_script(name, scene)


def classify(leaf, role):
    for pattern, mech in LEAF_RULES:
        if re.search(pattern, leaf):
            if mech is None:  # pypdf: role decides parse vs fill
                return ("M-PDF-FORMFILL" if role == "pdf-fill"
                        else "M-PDF-QPDF-PARSE")
            return mech
    return ROLE_DEFAULT_MECH.get(role, "M-UNCLASSIFIED")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw_file")
    ap.add_argument("out_dir")
    args = ap.parse_args()
    out_dir = Path(args.out_dir)
    # scene from the run metadata (written by the collector into out_dir)
    scene = "pdf"
    meta_path = out_dir / "metadata.json"
    if not meta_path.is_file():
        meta_path = out_dir.parent / "metadata.json"
    if meta_path.is_file():
        try:
            scene = json.load(open(meta_path)).get("runner_summary", {}).get(
                "scene", "pdf")
        except Exception:
            pass

    roles = defaultdict(lambda: {"samples": 0, "mech": Counter(),
                                 "functions": Counter(), "cmdlines": Counter()})
    dropped_preloop = 0
    stale_cmdline_samples = 0
    integrity = {
        "raw_nonempty_line_count": 0,
        "parsed_stack_line_count": 0,
        "raw_positive_count_sum": 0,
        "parsed_count_sum": 0,
        "malformed_line_count": 0,
        "missing_process_identity_count": 0,
        "nonpositive_count_line_count": 0,
    }
    out_path = out_dir / "pyspy-samples.jsonl"
    with open(args.raw_file) as fh, open(out_path, "w") as out:
        for line in fh:
            line = line.rstrip("\n")
            if not line:
                continue
            integrity["raw_nonempty_line_count"] += 1
            if " " not in line:
                integrity["malformed_line_count"] += 1
                continue
            stack_part, _, count_s = line.rpartition(" ")
            try:
                count = int(count_s)
            except ValueError:
                integrity["malformed_line_count"] += 1
                continue
            if count > 0:
                integrity["raw_positive_count_sum"] += count
            segments = stack_part.split(";")
            proc_chain = []
            frames = []
            for seg in segments:
                m = PROC.match(seg)
                if m:
                    proc_chain.append((m.group(1), m.group(2)))
                else:
                    frames.append(seg)
            if not proc_chain or count <= 0:
                if not proc_chain:
                    integrity["missing_process_identity_count"] += 1
                if count <= 0:
                    integrity["nonpositive_count_line_count"] += 1
                continue
            integrity["parsed_stack_line_count"] += 1
            integrity["parsed_count_sum"] += count
            sampled_pid, sampled_cmd = proc_chain[-1]
            role = script_role(sampled_cmd, scene)
            if role is None or (role == "runner" and len(proc_chain) > 1
                                and sampled_cmd == proc_chain[0][1]):
                # stale pre-exec cmdline: recover the script from the root
                # <module> frame
                for frame in frames:
                    m = MODULE_FRAME.search(frame)
                    if m:
                        recovered = script_role(m.group(1), scene)
                        if recovered and recovered != "runner":
                            role = recovered
                            stale_cmdline_samples += count
                            break
            if role is None:
                if not sampled_cmd.strip() and len(proc_chain) == 1:
                    role = "runner"
                else:
                    role = "other"
            if role == "runner" and any(PRELOOP_FRAMES.search(f) for f in frames):
                dropped_preloop += count
                continue
            leaf = frames[-1] if frames else '[no-python-frame]'
            mech = classify(leaf, role) if frames else 'M-UNCLASSIFIED'
            entry = roles[role]
            entry["samples"] += count
            entry["mech"][mech] += count
            entry["functions"][leaf] += count
            entry["cmdlines"][sampled_cmd[:120]] += count
            out.write(json.dumps({"role": role, "mech": mech, "count": count,
                                  "leaf": leaf, "frames": frames}) + "\n")
    result = {}
    for role, entry in roles.items():
        total = entry["samples"]
        result[role] = {
            "samples": total,
            "mechanism_composition": {m: c / total
                                      for m, c in entry["mech"].most_common()},
            "mechanism_counts": dict(entry["mech"]),
            "top_functions": entry["functions"].most_common(25),
            "cmdlines": entry["cmdlines"].most_common(4),
        }
    integrity["status"] = (
        "complete" if integrity["raw_nonempty_line_count"] == integrity["parsed_stack_line_count"]
        and integrity["malformed_line_count"] == 0
        and integrity["missing_process_identity_count"] == 0
        and integrity["nonpositive_count_line_count"] == 0
        and integrity["raw_positive_count_sum"] == integrity["parsed_count_sum"]
        else "incomplete")
    summary = {"roles": result, "parse_integrity": integrity,
               "dropped_preloop_runner_samples": dropped_preloop,
               "recovered_from_stale_cmdline_samples": stale_cmdline_samples,
               "scene": scene}
    with open(out_dir / "pyspy-roles.json", "w") as fh:
        json.dump(summary, fh, indent=2)
    print(json.dumps({r: v["samples"] for r, v in result.items()}, indent=2))
    print("dropped pre-loop:", dropped_preloop,
          "recovered stale-cmdline samples:", stale_cmdline_samples)


if __name__ == "__main__":
    main()
