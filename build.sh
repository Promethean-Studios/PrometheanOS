#!/usr/bin/env bash
set -euo pipefail

# Build a Fedora KDE Plasma live ISO in a disposable container. This never writes
# to host disks; it only reads the repo and emits an ISO under build/output.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${OUTPUT_DIR:-$REPO_ROOT/build/output}"
KICKSTART_FILE="${KICKSTART_FILE:-$REPO_ROOT/kickstarts/promethean-live.ks}"
FEDORA_RELEASE="${FEDORA_RELEASE:-44}"
CONTAINER_IMAGE="${CONTAINER_IMAGE:-quay.io/fedora/fedora:${FEDORA_RELEASE}}"

mkdir -p "$(dirname "$OUTPUT_DIR")"
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

if ! command -v podman >/dev/null 2>&1; then
  echo "podman is required to build the ISO. Docker is not supported because the build needs privileged mounts and loop devices." >&2
  exit 1
fi

if [[ ! -f "$KICKSTART_FILE" ]]; then
  echo "Kickstart file not found: $KICKSTART_FILE" >&2
  exit 1
fi

TEMP_RESULT_ROOT="$(mktemp -d "$REPO_ROOT/.promethean-live-XXXXXX")"
trap 'rm -rf "$TEMP_RESULT_ROOT"' EXIT

podman run --rm \
  --privileged \
  -e KICKSTART_NAME="$(basename "$KICKSTART_FILE")" \
  -v "$REPO_ROOT:/workspace:Z" \
  -v "$TEMP_RESULT_ROOT:/tmp/live-root:Z" \
  -w /workspace \
  "$CONTAINER_IMAGE" \
  bash -lc '
    set -euo pipefail
    dnf -y install qemu-system-x86-core qemu-img edk2-ovmf lorax livemedia-creator isomd5sum pykickstart
    livemedia-creator \
      --make-iso \
      --ks=/workspace/kickstarts/$KICKSTART_NAME \
      --resultdir=/tmp/live-root/result \
      --volid="PROMETHEANOS" \
      --iso-name="PrometheanOS-KDE.iso" \
      --project="PrometheanOS" \
      --releasever="44"
  '

iso_path="$(find "$TEMP_RESULT_ROOT" -maxdepth 3 -type f -iname '*.iso' -print -quit)"
if [[ -z "$iso_path" ]]; then
  echo "livemedia-creator completed without producing an ISO in $TEMP_RESULT_ROOT" >&2
  exit 1
fi
mkdir -p "$OUTPUT_DIR"
cp -f "$iso_path" "$OUTPUT_DIR/PrometheanOS-KDE.iso"

echo "ISO build complete. Output directory: $OUTPUT_DIR"
