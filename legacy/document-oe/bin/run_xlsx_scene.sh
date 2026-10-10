#!/usr/bin/env bash
set -euo pipefail

exec python3 /opt/document-bench/bin/run_document_scene_loop.py --scene xlsx "$@"
