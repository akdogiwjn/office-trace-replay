#!/usr/bin/env bash
# In-container workload launcher used by every collection mode.
# Runs the ROI marker (calibrating perf-clock to CLOCK_MONOTONIC), then execs
# the unified runner pinned to the fixed CPU budget. Everything after exec is
# the workload; the marker runs before the runner starts.
set -euo pipefail

SCRIPTS="$(cd "$(dirname "$0")" && pwd)"
ENTRY=${HOTSPOT_ENTRY:-/opt/office-trace-replay/replay/entry.py}
PYTHON=${HOTSPOT_PYTHON:-/opt/document-bench/.venv/bin/python}
WORKCPUS="${HOTSPOT_WORKCPUS:-0-7}"

python3 "$SCRIPTS/roi_marker.py"
exec taskset -c "$WORKCPUS" "$PYTHON" "$ENTRY" "$@"
