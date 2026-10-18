#!/usr/bin/env python3
"""Build raw/README.md — an index of every raw collection artifact with
SHA256, size and config binding. Raw files themselves stay gitignored; this
index plus the committed processed/ tables are the reproducible record.

Local-reproducible scope: raw perf.data / pyspy / monitor files live only on
the collection machine (gitignored). Everything committed (metadata, processed
tables, index) can be re-derived from raw locally with the recorded commands.
"""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main():
    entries = []
    for path in sorted(RAW.rglob("*")):
        if not path.is_file() or path.name in (".gitignore", "README.md", "plan.tsv",
                                               "syscalls-plan.tsv",
                                               "collection.log", "index.json"):
            continue
        rel = path.relative_to(RAW)
        parts = rel.parts
        config = parts[0] if parts else "?"
        run = parts[1] if len(parts) > 1 else "?"
        entries.append({
            "path": str(rel), "config": config, "run": run,
            "sha256": sha256(path), "size_bytes": path.stat().st_size,
        })
    index = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "file_count": len(entries),
        "total_bytes": sum(e["size_bytes"] for e in entries),
        "files": entries,
    }
    (RAW / "index.json").write_text(json.dumps(index, indent=2) + "\n")
    print(f"indexed {len(entries)} raw files, "
          f"{index['total_bytes'] / 1e9:.2f} GB -> raw/index.json")


if __name__ == "__main__":
    main()
