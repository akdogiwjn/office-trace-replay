"""Per-region contact-sheet generation for scaled PPTX 021 variants.

The frozen parent render step used a fixed `slide-{1..8}.jpg` brace expansion.
Scaled variants have 40/80 pages, so this helper discovers the real rendered
files, sorts them by numeric page number (zero-padded names included), and
verifies against the frozen expected.json that:

- the rendered images exactly cover pages 1..total_pages (missing, duplicate,
  extra and missing-trailing-group pages are all rejected);
- the group count equals the expected region count;
- every contact sheet covers exactly pages_per_region pages.

Each group is montaged with the original options (thumbnail size, tile layout,
geometry, background). Fixtures test the grouping logic with fake filenames and
a mocked montage; nothing here performs real rendering.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_PER_GROUP = 8
MONTAGE_ARGS = ["-thumbnail", "720x405", "-tile", "2x4", "-geometry", "+18+18",
                "-background", "#D9E2EC"]


def load_expectation(expected_path: Path) -> dict:
    data = json.loads(Path(expected_path).read_text(encoding="utf-8"))
    if data.get("kind") != "pptx" or "total_pages" not in data:
        raise ValueError(f"not a PPTX expectation file: {expected_path}")
    total = int(data["total_pages"])
    per_group = int(data.get("pages_per_region", DEFAULT_PER_GROUP))
    region_count = len(data.get("regions", []))
    if region_count < 1 or total != per_group * region_count:
        raise ValueError(
            f"inconsistent expectation: total_pages={total} "
            f"pages_per_region={per_group} regions={region_count}"
        )
    return {"total_pages": total, "pages_per_region": per_group, "region_count": region_count}


def parse_page(path: Path) -> int:
    match = re.search(r"(\d+)\.jpg$", path.name)
    if not match:
        raise ValueError(f"not a slide page image: {path.name}")
    return int(match.group(1))


def discover_sorted(directory: Path, prefix: str = "slide") -> list[Path]:
    return sorted(directory.glob(f"{prefix}-*.jpg"), key=parse_page)


def group_pages(files: list[Path], per_group: int = DEFAULT_PER_GROUP,
                total_pages: int | None = None,
                region_count: int | None = None) -> list[list[Path]]:
    if per_group < 1:
        raise ValueError("per_group must be >= 1")
    if not files:
        if total_pages is not None:
            raise ValueError(f"no page images found; expected pages 1..{total_pages}")
        return []
    pages = [parse_page(f) for f in files]
    if len(set(pages)) != len(pages):
        duplicated = sorted({p for p in pages if pages.count(p) > 1})
        raise ValueError(f"duplicate page numbers: {duplicated}")
    expected = list(range(1, (total_pages if total_pages is not None else len(files)) + 1))
    if pages != expected:
        missing = sorted(set(expected) - set(pages))
        extra = sorted(set(pages) - set(expected))
        raise ValueError(
            f"page images must exactly cover pages 1..{expected[-1]}; "
            f"found {pages} (missing={missing}, extra={extra})"
        )
    groups = [files[i:i + per_group] for i in range(0, len(files), per_group)]
    if any(len(group) != per_group for group in groups):
        raise ValueError(f"groups do not split evenly into {per_group}-page blocks")
    if region_count is not None and len(groups) != region_count:
        raise ValueError(f"expected {region_count} contact sheets, got {len(groups)}")
    return groups


def montage_group(files: list[Path], output: Path, montage_bin: str = "montage") -> None:
    argv = [montage_bin] + [str(f) for f in files] + MONTAGE_ARGS + [str(output)]
    subprocess.run(argv, check=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("render_dir", type=Path, help="directory containing slide-*.jpg")
    parser.add_argument("--expected", type=Path, required=True,
                        help="frozen expected.json defining total_pages/pages_per_region/regions")
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="directory for contact sheets (defaults to render_dir)")
    args = parser.parse_args(argv)
    expectation = load_expectation(args.expected)
    output_dir = args.output_dir or args.render_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    files = discover_sorted(args.render_dir)
    if not files:
        print("No slide-*.jpg files found", file=sys.stderr)
        return 1
    groups = group_pages(files, expectation["pages_per_region"],
                         total_pages=expectation["total_pages"],
                         region_count=expectation["region_count"])
    rendered = []
    for index, group in enumerate(groups, 1):
        out = output_dir / f"contact_sheet_region_{index:02d}.jpg"
        montage_group(group, out)
        rendered.append(str(out))
    print(f"Contact sheets: {len(rendered)}")
    for path in rendered:
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
