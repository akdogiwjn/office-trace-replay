#!/usr/bin/env python3
"""Execute one representative fill and render for applicant_01."""

import os
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path("/root/.openclaw/skills/pdf")
INPUT_PDF = Path("/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-01/input/of306_aug2023.pdf")
OUTPUT = Path("/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-01/output")
FIELD_VALUES_DIR = OUTPUT / "field_values"
FILLED_DIR = OUTPUT / "filled"

FILL_SCRIPT = SKILL_DIR / "scripts/fill_fillable_fields.py"
RENDER_SCRIPT = SKILL_DIR / "scripts/convert_pdf_to_images.py"

applicant_count = int(os.environ.get("DOCUMENT_BENCH_PDF_APPLICANT_COUNT", "1"))
if applicant_count not in {1, 10}:
    raise ValueError("DOCUMENT_BENCH_PDF_APPLICANT_COUNT must be 1 or 10")
applicant_ids = [f"applicant_{index:02d}" for index in range(1, applicant_count + 1)]
fill_count = 0
render_count = 0

for aid in applicant_ids:
    values_json = FIELD_VALUES_DIR / f"{aid}.json"
    out_pdf = FILLED_DIR / f"{aid}.pdf"
    
    # Fill
    cmd_fill = [
        "python3", str(FILL_SCRIPT),
        str(INPUT_PDF), str(values_json), str(out_pdf)
    ]
    result = subprocess.run(cmd_fill, capture_output=True, text=True, cwd=str(SKILL_DIR))
    fill_count += 1
    if result.returncode != 0:
        print(f"FAIL fill {aid}: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    print(f"Filled {aid} -> {out_pdf}")

    # Render
    render_dir = OUTPUT / "rendered" / aid
    render_dir.mkdir(parents=True, exist_ok=True)
    cmd_render = [
        "python3", str(RENDER_SCRIPT),
        str(out_pdf), str(render_dir)
    ]
    result = subprocess.run(cmd_render, capture_output=True, text=True, cwd=str(SKILL_DIR))
    render_count += 1
    if result.returncode != 0:
        print(f"FAIL render {aid}: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    print(f"Rendered {aid} -> {render_dir}")

print(f"\nDone. Fills: {fill_count}, Renders: {render_count}")
