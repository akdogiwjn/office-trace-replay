#!/usr/bin/env bash
# Build the DocOps replay candidate image offline (no downloads during build;
# all vendor debs/fonttools are frozen and copied). Never overwrites the base
# image, existing seven-case images, or any earlier replay candidate.
set -euo pipefail
BASE="$(cd "$(dirname "$0")/.." && pwd)"   # office-trace-replay/docops
REPO="$(cd "$BASE/.." && pwd)"             # office-trace-replay
TAG="${1:?usage: build.sh <unused-candidate-tag>}"
EXPECTED_BASE="sha256:b0d0e6038597b41c08f7fbba8d3e5cb2ff515e0e2602c31528c9e3fe80a90106"
BASE_REF=docops-l3-shared-tools:arm64-v3
BASE_ID="$(docker image inspect "$BASE_REF" --format '{{.Id}}')"
ARCH="$(docker image inspect "$BASE_ID" --format '{{.Os}}/{{.Architecture}}')"
if [ "$BASE_ID" != "$EXPECTED_BASE" ] || [ "$ARCH" != linux/arm64 ]; then
  echo "FATAL: base image identity/architecture mismatch: $BASE_ID $ARCH" >&2
  exit 2
fi

if docker image inspect "$TAG" >/dev/null 2>&1; then
  echo "FATAL: candidate tag already exists (refusing to overwrite): $TAG" >&2
  exit 2
fi
if [ ! -f "$BASE/vendor/debs/linux-perf_6.1.190-1_arm64.deb" ] || \
   [ ! -d "$BASE/vendor/fonttools/fontTools" ]; then
  echo "FATAL: vendor material missing (perf debs / fonttools)" >&2
  exit 2
fi

CTX="$(mktemp -d "${TMPDIR:-/tmp}/docops-ctx-XXXXXX")"
trap 'rm -rf "$CTX"' EXIT
mkdir -p "$CTX/vendor" "$CTX/devkit"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)-$(basename "$CTX")"
RECORD="$BASE/docker/records/$STAMP"
mkdir "$RECORD"
DK="$REPO/analysis/topdown/tools/DevKit-Tuner-CLI-26.0.RC1-Linux-aarch64"
python3 -B "$BASE/docker/verify_build_inputs.py" --devkit "$DK" > "$RECORD/build-inputs.json"

cp "$BASE/docker/Dockerfile" "$CTX/Dockerfile"
cp "$BASE/replay.py" "$BASE/compile.py" "$CTX/"
cp "$BASE/docker/install_state_check.py" "$CTX/install_state_check.py"
cp "$BASE/docker/devkit.sh" "$CTX/devkit.sh"
cp -a "$BASE/vendor/debs" "$CTX/vendor/debs"
cp -a "$BASE/vendor/fonttools" "$CTX/vendor/fonttools"
cp -a "$BASE/payload" "$CTX/payload"

cp -a "$DK" "$CTX/devkit/"

echo "building candidate $TAG from offline context (base docops-l3-shared-tools:arm64-v3)"
# BuildKit treats a bare config ID as a repository named "sha256". Use the
# verified local tag, disable forced pulls, and verify its ID again afterwards.
docker build --pull=false --network none --build-arg "BASE_IMAGE=$BASE_REF" \
  --iidfile "$RECORD/image-id.txt" "$CTX" 2>&1 | tee "$RECORD/build.log"
if [ "$(docker image inspect "$BASE_REF" --format '{{.Id}}')" != "$EXPECTED_BASE" ]; then
  echo "FATAL: base tag changed during build; candidate will not be published" >&2
  exit 2
fi
ID="$(cat "$RECORD/image-id.txt")"
if docker image inspect "$TAG" >/dev/null 2>&1; then
  echo "FATAL: candidate tag appeared during build; refusing to replace it" >&2
  exit 2
fi
docker tag "$ID" "$TAG"
docker image inspect "$TAG" > "$RECORD/image-inspect.json"
echo "candidate image ID: $ID"
mkdir -p "$BASE/docker/records"
{
  echo "candidate_tag=$TAG"
  echo "candidate_id=$ID"
  echo "built_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "base_id=$BASE_ID"
  echo "base_arch=$ARCH"
} > "$RECORD/candidate-image.txt"
echo "record written: $RECORD"
