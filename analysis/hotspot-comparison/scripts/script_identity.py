"""Resolve script roles from the executed Python script operand.

Command arguments such as workbook paths, shell prose, and embedded ``-c``
text are deliberately not searched for script names.
"""
from __future__ import annotations

import re
import shlex
from pathlib import Path


ROLE_BY_SCRIPT = {
    "run_document_scene_loop.py": "runner",
    "entry.py": "runner",
    "check_fillable_fields.py": "pdf-check-fillable",
    "extract_form_field_info.py": "pdf-extract-fields",
    "convert_pdf_to_images.py": "pdf-convert",
    "fill_fillable_fields.py": "pdf-fill",
    "verify_pdf_batch.py": "pdf-verify",
    "verify_office.py": "pdf-verify",  # caller refines by scene
    "generate_and_run_batch.py": "pdf-mapping-driver",
    "build_field_values.py": "pdf-mapping-driver",
    "run_batch_fill_render.py": "pdf-mapping-driver",
    "pdf_batch.py": "pdf-mapping-driver",
    "write_pdf_batch_summary.py": "pdf-summary-writer",
    "inspect_xlsx_structure.py": "xlsx-inspect-structure",
    "inspect_xlsx_features.py": "xlsx-inspect-features",
    "enhance_workbook.py": "xlsx-enhance",
    "hr_metro_build.py": "xlsx-enhance",
    ".hr_metro_build.runtime.py": "xlsx-enhance",
    "retail_online_build.py": "xlsx-enhance",
    ".retail_online_build.runtime.py": "xlsx-enhance",
    "industry_productivity_build.py": "xlsx-enhance",
    ".industry_productivity_build.runtime.py": "xlsx-enhance",
    "retail_build_enhance.py": "xlsx-enhance",
    "hr_build.py": "xlsx-enhance",
    "run_xlsx_helper_atomic.py": "xlsx-atomic-helper",
    "recalc.py": "xlsx-recalc",
    "inspect_xlsx_formulas.py": "xlsx-inspect-formulas",
    "inspect_xlsx_cached_values.py": "xlsx-inspect-cached",
    "verify_xlsx_enhanced.py": "xlsx-verify",
    "write_xlsx_summary.py": "xlsx-summary-export",
    "export_xlsx_csv.py": "xlsx-csv-export",
    "export_xlsx.py": "xlsx-summary-export",
    "inspect_xlsx.py": "xlsx-inspect-tool",
    "roi_marker.py": "roi-marker",
    "monitor_procs.py": "monitor",
    "tstamp_pipe.py": "stdout-timestamper",
}


def python_script_operand(command: str) -> str | None:
    """Return the actual script operand, or ``None`` for non-script Python.

    Handles direct Python invocation and common exec wrappers. It does not
    search arbitrary argument text and treats ``python -c`` as inline code.
    """
    if not command:
        return None
    try:
        argv = shlex.split(command, posix=True)
    except ValueError:
        return None
    i = 0
    while i < len(argv):
        exe = Path(argv[i]).name
        if exe in {"env", "taskset", "timeout", "nice", "stdbuf"}:
            i += 1
            while i < len(argv) and argv[i].startswith("-"):
                option = argv[i]
                i += 1
                if option in {"-c", "-k", "--kill-after", "-o", "-e"} and i < len(argv):
                    i += 1
            if exe == "timeout" and i < len(argv) and re.fullmatch(r"\d+(?:\.\d+)?[smhd]?", argv[i]):
                i += 1
            continue
        if re.fullmatch(r"python(?:\d+(?:\.\d+)*)?", exe):
            i += 1
            while i < len(argv) and argv[i].startswith("-"):
                option = argv[i]
                i += 1
                if option in {"-c", "-m"}:
                    return None
                if option in {"-W", "-X"} and i < len(argv):
                    i += 1
            if i < len(argv) and not argv[i].startswith("-") and argv[i] != "-":
                return Path(argv[i]).name
            return None
        # The process itself can be the executed .py operand from py-spy
        # module frames. Only accept a whole filename token.
        if len(argv) == 1 and exe.endswith(".py"):
            return exe
        return None
    return None


def role_for_script(script: str | None, scene: str) -> str | None:
    if not script:
        return None
    name = Path(script).name
    role = ROLE_BY_SCRIPT.get(name)
    if name == "verify_office.py":
        return "pdf-verify" if scene == "pdf" else "xlsx-verify"
    if name == "summary.py":
        return "pdf-summary-writer" if scene == "pdf" else "xlsx-summary-export"
    return role


def role_for_command(command: str, scene: str) -> str | None:
    process = re.fullmatch(r'process\s+\d+:"(.*)"', command or '')
    if process:
        command = process.group(1)
    return role_for_script(python_script_operand(command), scene)
