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

# The container MUST run rootful (prefix with sudo when we are not root):
# livemedia-creator --no-virt attaches the disk image with `losetup --find
# --show`, and losetup only works for callers with privileges in the INITIAL
# user namespace. Host /dev/loopN nodes are owned by real root:disk, which is
# unmapped inside a rootless podman user namespace, and --privileged cannot
# lift that without real root. This is what killed CI run 34311360230
# (losetup exit 1 after the full dnf install) when podman ran rootless.
if [[ ${EUID} -eq 0 ]]; then
  RUN_AS_ROOT=()
else
  RUN_AS_ROOT=(sudo)
fi

if [[ ! -f "$KICKSTART_FILE" ]]; then
  echo "Kickstart file not found: $KICKSTART_FILE" >&2
  exit 1
fi

TEMP_RESULT_ROOT="$(mktemp -d "$REPO_ROOT/.promethean-live-XXXXXX")"
# Root-owned files can appear inside the temp result root (created by the
# rootful container), so fall back to sudo for cleanup; best effort only.
trap 'rm -rf "$TEMP_RESULT_ROOT" 2>/dev/null || sudo -n rm -rf "$TEMP_RESULT_ROOT" 2>/dev/null || true' EXIT

"${RUN_AS_ROOT[@]}" podman run --rm \
  --privileged \
  -e KICKSTART_NAME="$(basename "$KICKSTART_FILE")" \
  -v "$REPO_ROOT:/workspace:Z" \
  -v "$TEMP_RESULT_ROOT:/tmp/live-root:Z" \
  -w /workspace \
  "$CONTAINER_IMAGE" \
  bash -lc '
    set -euo pipefail
    # Fail fast if loop devices are unusable in this container: livemedia-creator
    # --no-virt attaches the disk image with `losetup --find --show` and swallows
    # the losetup stderr, which made the CI failure in run 34311360230 opaque (it
    # logged only "exit status 1" after the whole dnf install). This probe costs
    # under a second and surfaces the real losetup error message.
    dd if=/dev/zero of=/tmp/loop-probe.img bs=1M count=8 status=none
    probe_loop="$(losetup --find --show /tmp/loop-probe.img)" || {
      echo "FATAL: losetup probe failed - loop devices are not usable in this container (see losetup stderr above)." >&2
      exit 1
    }
    echo "loop probe OK: attached ${probe_loop}"
    losetup -d "${probe_loop}"
    rm -f /tmp/loop-probe.img
    # anaconda + e2fsprogs are required by livemedia-creator --no-virt:
    # anaconda runs the kickstart install directly on the host container
    # ("no-virt requires anaconda to be installed.") and mkfs.ext4 builds
    # the rootfs image. qemu/ovmf are only needed by --virt installs.
    dnf -y install anaconda e2fsprogs lorax livemedia-creator isomd5sum pykickstart
    livemedia-creator \
      --make-iso \
      --no-virt \
      --nomacboot \
      --extra-boot-args="console=ttyS0,115200" \
      --ks=/workspace/kickstarts/$KICKSTART_NAME \
      --resultdir=/tmp/live-root/result \
      --volid="PROMETHEANOS" \
      --iso-name="PrometheanOS-KDE.iso" \
      --project="PrometheanOS" \
      --releasever="'"$FEDORA_RELEASE"'"
  '

iso_path="$(find "$TEMP_RESULT_ROOT" -maxdepth 3 -type f -iname '*.iso' -print -quit)"
if [[ -z "$iso_path" ]]; then
  echo "livemedia-creator completed without producing an ISO in $TEMP_RESULT_ROOT" >&2
  exit 1
fi
# The rootful container created root-owned files inside the temp result root;
# make sure the invoking user can read the ISO for the copy below.
chmod -R a+rX "$TEMP_RESULT_ROOT" 2>/dev/null \
  || sudo -n chmod -R a+rX "$TEMP_RESULT_ROOT" 2>/dev/null \
  || echo "warning: could not relax permissions on $TEMP_RESULT_ROOT; relying on ISO mode bits" >&2
mkdir -p "$OUTPUT_DIR"
cp -f "$iso_path" "$OUTPUT_DIR/PrometheanOS-KDE.iso"

echo "ISO build complete. Output directory: $OUTPUT_DIR"
