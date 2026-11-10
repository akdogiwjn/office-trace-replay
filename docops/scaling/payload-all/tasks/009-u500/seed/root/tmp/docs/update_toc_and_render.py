#!/usr/bin/env python3
"""009 private step: render the built DOCX, measure real section pages, bake
the real page numbers into the document's TOC cache, confirm layout stability
(capped iterations), then render the final PDF/PNG from the delivered DOCX.

This adaptation lives in the 009 private step (in workflow ROI) so the final
delivered DOCX's cached TOC matches the final rendered result. It uses only the
existing LibreOffice environment (soffice) and Poppler (pdftotext/pdftoppm);
no Skill, no software version and no public tooling is modified.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from docx import Document

try:  # package import (tests) vs script import (payload /root/tmp/docs)
    from .build_incident_manual_variant import (
        extract_toc_entries, find_toc_paragraph, set_toc_pages, HEADINGS)
except ImportError:
    from build_incident_manual_variant import (
        extract_toc_entries, find_toc_paragraph, set_toc_pages, HEADINGS)

MAX_TOC_ITERATIONS = 3


def page_texts(pdf_path: Path) -> list[str]:
    """One string per PDF page via pdftotext."""
    pages = []
    page = 1
    while True:
        proc = subprocess.run(
            ["pdftotext", "-f", str(page), "-l", str(page), str(pdf_path), "-"],
            capture_output=True, text=True)
        if proc.returncode != 0 or not proc.stdout.strip():
            break
        pages.append(proc.stdout)
        page += 1
    return pages


def measure_heading_pages(pages: list[str], headings: list[str]):
    """Map each heading to the rendered page it starts on.

    The TOC page contains every heading title, so it is detected as the page
    with the most distinct headings and excluded; the section page is the
    smallest remaining page where the heading text appears.
    """
    counts = [
        sum(1 for h in headings if h in page_text)
        for page_text in pages
    ]
    toc_page = (counts.index(max(counts)) + 1) if counts else None
    result = {}
    for h in headings:
        candidates = [i + 1 for i, t in enumerate(pages)
                      if h in t and i + 1 != toc_page]
        result[h] = min(candidates) if candidates else None
    return result, toc_page


def convert_pdf(docx_path: Path, outdir: Path) -> Path:
    subprocess.run(
        ["soffice", "-env:UserInstallation=file:///tmp/lo_toc_render",
         "--headless", "--convert-to", "pdf", "--outdir", str(outdir),
         str(docx_path)],
        check=True, capture_output=True, timeout=1800)
    return outdir / (docx_path.stem + ".pdf")


def settle_toc(docx_path: Path, headings: list[str], initial: dict, toc_page,
                 tmp: Path, max_iterations: int):
    """Iteratively bake measured pages into the DOCX TOC cache until two
    consecutive layout passes agree (stable=True), or fail explicitly when the
    cap is reached without convergence. The final saved DOCX cache matches the
    returned page map, so the final PDF/PNG and the report correspond to one
    state."""
    current = dict(initial)
    iterations = 1
    converged = False
    last_diff = None
    while True:
        doc = Document(docx_path)
        set_toc_pages(doc, current)
        doc.save(docx_path)
        pdf2 = convert_pdf(docx_path, tmp)
        refreshed, _ = measure_heading_pages(page_texts(pdf2), headings)
        iterations += 1
        converged = refreshed == current
        if converged:
            current = refreshed
            break
        last_diff = {k: (current.get(k), refreshed.get(k)) for k in headings
                     if current.get(k) != refreshed.get(k)}
        current = refreshed
        if iterations >= max_iterations:
            break
    if not converged:
        raise RuntimeError(
            f"TOC did not converge within {max_iterations} layout passes; "
            f"last diff per heading: {last_diff}")
    return current, toc_page, iterations, converged


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="built DOCX path")
    parser.add_argument("--outdir", default="/root/tmp/docs/rendered_v2")
    args = parser.parse_args(argv)
    docx_path = Path(args.input).resolve()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="docops009_toc_") as tmp:
        tmp = Path(tmp)
        # Pass 1: measure real pages from the as-built document.
        pdf1 = convert_pdf(docx_path, tmp)
        pages1 = page_texts(pdf1)
        measured, toc_page = measure_heading_pages(pages1, HEADINGS)
        if toc_page is None or any(v is None for v in measured.values()):
            raise RuntimeError("could not locate every section page in the render")

        current, toc_page, iterations, converged = settle_toc(
            docx_path, HEADINGS, measured, toc_page, tmp, MAX_TOC_ITERATIONS)

        # Final PDF/PNG come from the delivered (TOC-updated) DOCX.
        final_pdf = convert_pdf(docx_path, outdir)
        subprocess.run(
            ["pdftoppm", "-png", "-r", "150", str(final_pdf),
             str(outdir / "page")],
            check=True, timeout=1800)
        sidecar = {
            "schema": "docops009-toc-pages-v1",
            "toc_page": toc_page,
            "iterations": iterations,
            "max_iterations": MAX_TOC_ITERATIONS,
            "stable": converged,
            "pages": current,
        }
        (outdir / "toc_pages.json").write_text(
            json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(sidecar, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
