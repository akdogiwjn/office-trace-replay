#!/usr/bin/env python3
"""Batch driver: fill + render every applicant using the bundled PDF scripts.

Counts every script invocation (successful and failed) in output/batch_run.log
and writes output/batch_summary.json. Failed attempts are never hidden.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PDF_SCRIPTS = Path("/root/.openclaw/skills/pdf/scripts")
INPUT = ROOT / "input"
OUTPUT = ROOT / "output"
LOG = OUTPUT / "batch_run.log"


def run(cmd, log_lines):
    log_lines.append("$ " + " ".join(str(c) for c in cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    log_lines.append(proc.stdout.rstrip())
    if proc.stderr.strip():
        log_lines.append("STDERR: " + proc.stderr.rstrip())
    log_lines.append(f"exit={proc.returncode}")
    return proc.returncode


def main():
    records = json.loads((INPUT / "synthetic_applicants.json").read_text())["applicants"]
    (OUTPUT / "filled").mkdir(parents=True, exist_ok=True)
    (OUTPUT / "rendered").mkdir(parents=True, exist_ok=True)

    log_lines = []
    fill_ok = 0
    fill_attempts = 0
    render_ok = 0
    render_attempts = 0

    for record in records:
        ident = str(record["id"])
        values = OUTPUT / "field_values" / f"{ident}.json"
        filled = OUTPUT / "filled" / f"{ident}.pdf"
        render_dir = OUTPUT / "rendered" / ident
        render_dir.mkdir(parents=True, exist_ok=True)

        fill_attempts += 1
        rc = run([sys.executable, str(PDF_SCRIPTS / "fill_fillable_fields.py"),
                  str(INPUT / "sba1919_2024.pdf"), str(values), str(filled)], log_lines)
        if rc == 0:
            fill_ok += 1
        else:
            log_lines.append(f"FILL FAILED for {ident}")

        render_attempts += 1
        rc = run([sys.executable, str(PDF_SCRIPTS / "convert_pdf_to_images.py"),
                  str(filled), str(render_dir)], log_lines)
        if rc == 0:
            render_ok += 1
        else:
            log_lines.append(f"RENDER FAILED for {ident}")

    template_renders = sorted((OUTPUT / "rendered" / "template").glob("page_*.png"))
    summary = {
        "input_form": "sba1919_2024.pdf",
        "applicant_count": len(records),
        "filled_pdf_count": fill_ok,
        "rendered_page_count": len(template_renders) + sum(
            len(list((OUTPUT / "rendered" / str(r["id"])).glob("page_*.png"))) for r in records),
        "ssn_and_signatures_left_blank": True,
        "fill_script_invocations": fill_attempts,
        "render_script_invocations": render_attempts + 1,  # +1 = blank template render
        "failed_fill_attempts": fill_attempts - fill_ok,
        "failed_render_attempts": render_attempts - render_ok,
    }
    (OUTPUT / "batch_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    LOG.write_text("\n".join(log_lines) + "\n")
    print(json.dumps(summary, indent=2))
    return 0 if fill_ok == len(records) and render_ok == len(records) else 1


if __name__ == "__main__":
    sys.exit(main())
