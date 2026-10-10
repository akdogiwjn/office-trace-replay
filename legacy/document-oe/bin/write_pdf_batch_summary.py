#!/usr/bin/env python3
"""Write a PDF batch summary for the selected applicant-count mode."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path


ENV_NAME = "DOCUMENT_BENCH_PDF_APPLICANT_COUNT"


def applicant_count() -> int:
    value = int(os.environ.get(ENV_NAME, "1"))
    if value not in {1, 10}:
        raise ValueError(f"{ENV_NAME} must be 1 or 10, got {value}")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("summary_json", type=Path)
    return parser.parse_args()


def atomic_write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    args = parse_args()
    count = applicant_count()
    filled = sorted((args.output_dir / "filled").glob("applicant_*.pdf"))
    rendered = sorted((args.output_dir / "rendered").glob("**/page_*.png"))
    expected_rendered = 3 * (count + 1)  # Three template pages plus three pages per applicant.
    if len(filled) != count:
        raise RuntimeError(f"expected {count} filled PDFs, found {len(filled)}")
    if len(rendered) != expected_rendered:
        raise RuntimeError(f"expected {expected_rendered} rendered pages, found {len(rendered)}")
    summary = {
        "input_form": "of306_aug2023.pdf",
        "applicant_count": count,
        "filled_pdf_count": len(filled),
        "rendered_page_count": len(rendered),
        "fill_script_invocations": count,
        "render_script_invocations": count + 1,
        "ssn_and_signatures_left_blank": True,
    }
    atomic_write_json(args.summary_json, summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
