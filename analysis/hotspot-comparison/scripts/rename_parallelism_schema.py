#!/usr/bin/env python3
"""Relabel historic poll-counter metrics; no new collection or inference."""
import json
from pathlib import Path

from parse_native import rename_poll_metrics

ROOT = Path(__file__).resolve().parents[1]


def migrate_json(path, field=None):
    data = json.loads(path.read_text())
    if field is None:
        normalized = rename_poll_metrics(data)
    else:
        normalized = rename_poll_metrics(data.get(field, {}))
        data[field] = normalized
    if normalized != data if field is not None else normalized != json.loads(path.read_text()):
        path.write_text(json.dumps(data if field is not None else normalized, indent=2) + "\n")
        return True
    return False


def main():
    changed = 0
    raw = ROOT / "raw"
    for path in raw.glob("*/r*/out/parallelism.json"):
        changed += migrate_json(path)
    processed = ROOT / "processed"
    for path in [processed / "all-profiles.json", *processed.glob("*.json")]:
        if not path.is_file() or path.name in ("coverage.json", "new-hotspots.json",
                                                "claims-verification.json",
                                                "hotspot-threshold-summary.json",
                                                "legacy-slice-mapping.json",
                                                "monitor-cycles-crosscheck.json",
                                                "parser-correction-impact.json"):
            continue
        data = json.loads(path.read_text())
        dirty = False
        if "repeats" in data:
            for rep in data["repeats"].values():
                if "parallelism" in rep:
                    old = rep["parallelism"]
                    new = rename_poll_metrics(old)
                    dirty |= new != old
                    rep["parallelism"] = new
        else:
            for profile in data.values() if isinstance(data, dict) else []:
                if not isinstance(profile, dict):
                    continue
                for rep in profile.get("repeats", {}).values():
                    if "parallelism" in rep:
                        old = rep["parallelism"]
                        new = rename_poll_metrics(old)
                        dirty |= new != old
                        rep["parallelism"] = new
        if dirty:
            path.write_text(json.dumps(data, indent=2) + "\n")
            changed += 1
    print(f"renamed poll metric fields in {changed} existing derived files")


if __name__ == "__main__":
    main()
