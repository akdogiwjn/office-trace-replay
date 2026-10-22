#!/usr/bin/env python3
"""Generic atomic XLSX helper runner for the versioned datasets.

The helper script must define exactly one module-level target workbook:
    TARGET = "/path/to/final/output.xlsx"

This runner redirects TARGET to a same-directory temporary file, executes the
helper against that copy, and publishes the finished workbook atomically only
after the helper succeeded and produced a valid file. Any failure propagates
and all temporary artifacts are removed. Unlike the byte-frozen legacy
run_xlsx_helper_atomic.py (which recognizes only monthly_operations_report.xlsx),
the target is passed explicitly so new datasets never rely on fixed filenames.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

MIN_VALID_BYTES = 1024


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("helper", type=Path, help="enhancement helper to execute")
    parser.add_argument("report", type=Path, help="final workbook to publish atomically")
    return parser.parse_args()


def redirect_target(source: str, temporary_report: Path) -> str:
    """Redirect the single TARGET workbook assignment to a same-directory temp file."""
    replacement = repr(str(temporary_report))
    transformed, count = re.subn(
        r'(?m)^TARGET\s*=\s*["\'][^"\']+["\']\s*$',
        f"TARGET = {replacement}",
        source,
        count=1,
    )
    if count != 1:
        raise ValueError("helper must define exactly one TARGET = \"...\" workbook path")
    return transformed


def main() -> int:
    args = parse_args()
    helper = args.helper.resolve(strict=True)
    report = args.report.resolve()
    if helper.suffix != ".py":
        raise ValueError(f"helper is not a Python file: {helper}")
    if not report.is_file():
        raise FileNotFoundError(f"input report does not exist: {report}")

    report.parent.mkdir(parents=True, exist_ok=True)
    temporary_report = report.with_name(f".{report.stem}.runtime{report.suffix}")
    temporary_helper = helper.with_name(f".{helper.stem}.runtime.py")
    report_created = False
    helper_created = False
    try:
        report_fd = os.open(temporary_report, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(report_fd)
        report_created = True
        shutil.copy2(report, temporary_report)
        transformed = redirect_target(helper.read_text(encoding="utf-8"), temporary_report)
        helper_fd = os.open(temporary_helper, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        helper_created = True
        with os.fdopen(helper_fd, mode="w", encoding="utf-8") as handle:
            handle.write(transformed)

        subprocess.run(
            [sys.executable, str(temporary_helper)],
            cwd=helper.parent,
            check=True,
        )
        if not temporary_report.is_file() or temporary_report.stat().st_size < MIN_VALID_BYTES:
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
