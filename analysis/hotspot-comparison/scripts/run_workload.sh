#!/usr/bin/env bash
# In-container workload launcher used by every collection mode.
# Runs the ROI marker (calibrating perf-clock to CLOCK_MONOTONIC), then execs
# the unified runner pinned to the fixed CPU budget. Everything after exec is
# the workload; the marker runs before the runner starts.
set -euo pipefail

SCRIPTS="$(cd "$(dirname "$0")" && pwd)"
RUNNER=/opt/document-bench/bin/run_document_scene_loop.py
WORKCPUS="${HOTSPOT_WORKCPUS:-0-7}"

python3 "$SCRIPTS/roi_marker.py"
exec taskset -c "$WORKCPUS" python3 "$RUNNER" "$@"
