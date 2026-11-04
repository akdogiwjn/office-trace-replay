#!/usr/bin/env bash
# Keep DevKit's private libraries out of the document workload environment.
set -euo pipefail
DOCOPS_DEVKIT_ROOT=/opt/devkit/DevKit-Tuner-CLI-26.0.RC1-Linux-aarch64
export LD_LIBRARY_PATH="$DOCOPS_DEVKIT_ROOT/tuner/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$DOCOPS_DEVKIT_ROOT/devkit" "$@"
