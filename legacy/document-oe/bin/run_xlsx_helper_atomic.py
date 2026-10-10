#!/usr/bin/env python3
"""Run a recorded XLSX helper without exposing a partially written report."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("helper", type=Path, help="recorded helper source to preserve")
    parser.add_argument("executable_helper", type=Path, help="static helper to execute")
    parser.add_argument("report", type=Path)
    return parser.parse_args()


def redirect_report(source: str, temporary_report: Path) -> str:
    """Redirect either recorded helper variant to a same-directory temp file."""
    replacement = repr(str(temporary_report))
    source, main_count = re.subn(
        r'(?m)^SRC\s*=\s*["\'][^"\']*monthly_operations_report\.xlsx["\']\s*$',
        f"SRC = {replacement}",
        source,
        count=1,
    )
    source, repair_count = re.subn(
        r'(?m)^REPORT\s*=\s*OUTPUT\s*/\s*["\']monthly_operations_report\.xlsx["\']\s*$',
        f"REPORT = Path({replacement})",
        source,
        count=1,
    )
    if main_count + repair_count != 1:
        raise ValueError("helper must define exactly one recognized XLSX report target")
    return source


def main() -> int:
    args = parse_args()
    helper = args.helper.resolve(strict=True)
    executable_helper = args.executable_helper.resolve(strict=True)
    report = args.report.resolve()
    if helper.suffix != ".py":
        raise ValueError(f"helper is not a Python file: {helper}")
    if executable_helper.suffix != ".py":
        raise ValueError(f"executable helper is not a Python file: {executable_helper}")
    if not report.is_file():
        raise FileNotFoundError(f"input report does not exist: {report}")

    report.parent.mkdir(parents=True, exist_ok=True)
    temporary_report = report.with_name(f".{report.stem}.runtime{report.suffix}")
    temporary_helper = executable_helper.with_name(f".{executable_helper.stem}.runtime.py")
    report_created = False
    helper_created = False
    try:
        report_fd = os.open(
            temporary_report,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        os.close(report_fd)
        report_created = True
        shutil.copy2(report, temporary_report)
        transformed = redirect_report(helper.read_text(encoding="utf-8"), temporary_report)
        # Keep the runtime helper name stable so process-based tracing can
        # identify this child reliably. O_EXCL prevents two concurrent
        # invocations from overwriting the same runtime script.
        helper_fd = os.open(
            temporary_helper,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        helper_created = True
        with os.fdopen(helper_fd, mode="w", encoding="utf-8") as handle:
            handle.write(transformed)

        subprocess.run(
            [sys.executable, str(executable_helper)],
            cwd=executable_helper.parent,
            check=True,
        )
        if not temporary_report.is_file() or temporary_report.stat().st_size < 1024:
            raise RuntimeError("helper did not produce a valid temporary workbook")
        os.replace(temporary_report, report)
        print(f"Atomically published workbook: {report}")
        return 0
    finally:
        if helper_created:
            temporary_helper.unlink(missing_ok=True)
        if report_created:
            temporary_report.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
