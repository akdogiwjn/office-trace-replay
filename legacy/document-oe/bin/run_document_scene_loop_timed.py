#!/usr/bin/env python3
"""Compatibility timing entry: forwards --timed to the unified runner.

The per-call and nested timing hooks now live inside
run_document_scene_loop.py (applied when `--timed` is present), so this wrapper
only ensures `--timed` is set and delegates to the runner's main(). This keeps
the original phase/call/nested process logging without double-patching or
recursive execution, and the timing boundaries are unchanged.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_document_scene_loop as core

if __name__ == "__main__":
    if "--timed" not in sys.argv:
        sys.argv.append("--timed")
    raise SystemExit(core.main())
