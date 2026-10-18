#!/usr/bin/env bash
# py-spy variant: root must be python3 for --subprocesses tracking, so the ROI
# marker is skipped; the workload is pinned by taskset before exec.
set -euo pipefail
exec taskset -c "${HOTSPOT_WORKCPUS:-0-7}" python3 /opt/document-bench/bin/run_document_scene_loop.py "$@"
