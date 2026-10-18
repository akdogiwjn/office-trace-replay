#!/usr/bin/env python3
"""Pack large derived profiles for Git; restore and verify their original bytes."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "metadata/profile-artifacts.json"


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def checked_path(relative):
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT.resolve() / "processed"):
        raise ValueError("profile path must remain under processed/")
    return path


def pack():
    plan = json.loads((ROOT / "config/run-plan.json").read_text())
    names = ["all-profiles"] + [c["config_id"] for c in plan["configs"]]
    entries = []
    for name in names:
        source = checked_path(f"processed/{name}.json")
        archive = checked_path(f"processed/packed/{name}.json.gz")
        archive.parent.mkdir(parents=True, exist_ok=True)
        with source.open("rb") as incoming, archive.open("wb") as output:
            with gzip.GzipFile(filename="", fileobj=output, mode="wb",
                               mtime=0, compresslevel=6) as compressed:
                shutil.copyfileobj(incoming, compressed)
        entries.append({"path": str(source.relative_to(ROOT)),
                        "sha256": digest(source), "size_bytes": source.stat().st_size,
                        "archive": str(archive.relative_to(ROOT)),
                        "archive_sha256": digest(archive),
                        "archive_size_bytes": archive.stat().st_size})
    manifest = {"schema_version": "derived-profile-artifacts-v1", "files": entries,
                "scope": "Derived profiles only; original perf/monitor data stays local."}
    (ROOT / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"packed {len(entries)} profiles")


def verify_archive(entry, output=None):
    archive = checked_path(entry["archive"])
    if digest(archive) != entry["archive_sha256"]:
        raise ValueError(f"compressed hash mismatch: {archive}")
    decoded_hash = hashlib.sha256()
    size = 0
    with gzip.open(archive, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            decoded_hash.update(chunk)
            size += len(chunk)
            if output is not None:
                output.write(chunk)
    if size != entry["size_bytes"] or decoded_hash.hexdigest() != entry["sha256"]:
        raise ValueError(f"decoded profile hash/size mismatch: {archive}")


def restore_entry(entry):
    destination = checked_path(entry["path"])
    if destination.exists():
        if digest(destination) != entry["sha256"]:
            raise ValueError(f"existing profile differs; preserve or move it first: {destination}")
        verify_archive(entry)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as output:
            temporary = Path(output.name)
            verify_archive(entry, output)
        os.replace(temporary, destination)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("pack", "restore", "verify"))
    action = parser.parse_args().action
    if action == "pack":
        pack()
        return
    entries = json.loads((ROOT / MANIFEST).read_text())["files"]
    for entry in entries:
        if action == "restore":
            restore_entry(entry)
        else:
            verify_archive(entry)
    print(f"{action}: {len(entries)} profiles verified")


if __name__ == "__main__":
    main()
