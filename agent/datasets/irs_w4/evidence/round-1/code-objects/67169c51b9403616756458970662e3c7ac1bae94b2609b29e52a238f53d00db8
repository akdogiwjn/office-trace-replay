#!/usr/bin/env python3
"""Batch driver: fill + render every synthetic employee record once.

Uses only the bundled PDF-skill scripts (no custom PDF implementation).
Each bundled-script invocation is logged with its exit status so failed
attempts remain visible instead of being overwritten.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKILL = Path("/root/.openclaw/skills/pdf")
INPUT = ROOT / "input"
OUTPUT = ROOT / "output"
SOURCE_PDF = INPUT / "fw4_2026.pdf"
LOGS = OUTPUT / "logs"

FILL = SKILL / "scripts" / "fill_fillable_fields.py"
RENDER = SKILL / "scripts" / "convert_pdf_to_images.py"


def run(cmd, log_path):
    with log_path.open("a") as log:
        log.write("$ " + " ".join(cmd) + "\n")
        log.flush()
        proc = subprocess.run(cmd, cwd=SKILL, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True)
        log.write(proc.stdout)
        log.write(f"[exit {proc.returncode}]\n")
        log.flush()
    print(f"{'OK ' if proc.returncode == 0 else 'FAIL'} {log_path.name} (exit {proc.returncode})")
    return proc.returncode


def main():
    LOGS.mkdir(parents=True, exist_ok=True)
    records = json.loads((INPUT / "synthetic_employees.json").read_text())["employees"]
    ids = [r["id"] for r in records]

    mapping_files = sorted(p.stem for p in (OUTPUT / "field_values").glob("*.json"))
    if mapping_files != sorted(ids):
        sys.exit(f"field_values mismatch: {mapping_files} != {sorted(ids)}")

    counts = {"fill": 0, "render": 0, "failures": []}
    for ident in ids:
        out_pdf = OUTPUT / "filled" / f"{ident}.pdf"
        out_pdf.parent.mkdir(parents=True, exist_ok=True)
        rc = run(["python3", str(FILL), str(SOURCE_PDF),
                  str(OUTPUT / "field_values" / f"{ident}.json"), str(out_pdf)],
                 LOGS / f"fill_{ident}.log")
        counts["fill"] += 1
        if rc != 0:
            counts["failures"].append(f"fill:{ident}")
            break

        render_dir = OUTPUT / "rendered" / ident
        render_dir.mkdir(parents=True, exist_ok=True)
        rc = run(["python3", str(RENDER), str(out_pdf), str(render_dir)],
                 LOGS / f"render_{ident}.log")
        counts["render"] += 1
        if rc != 0:
            counts["failures"].append(f"render:{ident}")
            break

    (LOGS / "operation_counts.json").write_text(json.dumps(counts, indent=2) + "\n")
    print(json.dumps(counts, indent=2))
    return 0 if not counts["failures"] and counts["fill"] == 10 and counts["render"] == 10 else 1


if __name__ == "__main__":
    raise SystemExit(main())
