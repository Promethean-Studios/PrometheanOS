#!/usr/bin/env bash
set -euo pipefail

# Build a Fedora KDE Plasma live ISO in a disposable container. This never writes
# to host disks; it only reads the repo and emits an ISO under build/output.

IMAGE_NAME="${IMAGE_NAME:-fedora-kde-live}"
OUTPUT_DIR="${OUTPUT_DIR:-$(pwd)/build/output}"
KICKSTART_FILE="${KICKSTART_FILE:-$(pwd)/kickstarts/promethean-base.ks}"
FEDORA_RELEASE="${FEDORA_RELEASE:-40}"
CONTAINER_IMAGE="${CONTAINER_IMAGE:-quay.io/fedora/fedora:40}"

mkdir -p "$OUTPUT_DIR"

if ! command -v podman >/dev/null 2>&1; then
  echo "podman is required to build the ISO." >&2
  exit 1
fi

if [[ ! -f "$KICKSTART_FILE" ]]; then
  echo "Kickstart file not found: $KICKSTART_FILE" >&2
  exit 1
fi

podman run --rm \
  --privileged \
  -v "$PWD:/workspace:Z" \
  -v "$OUTPUT_DIR:/output:Z" \
  -w /workspace \
  "$CONTAINER_IMAGE" \
  bash -lc '
    set -euo pipefail
    dnf -y install lorax livemedia-creator isomd5sum pykickstart
    livemedia-creator \
      --make=live \
      --ks=/workspace/kickstarts/promethean-base.ks \
      --resultdir=/output \
      --title="PrometheanOS-KDE" \
      --volid="PROMETHEANOS"
  '

echo "ISO build complete. Output directory: $OUTPUT_DIR"
