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
# The temp result root MUST live OUTSIDE $REPO_ROOT: with --no-virt the
# container's /workspace IS the repo dir, and the kickstart %post --nochroot
# `cp -a /workspace/.` would otherwise pull this directory (including lmc's
# multi-GB disk image and result files) into the image, exhausting the target
# filesystem ("No space left on device", CI run 34522793350).
TEMP_RESULT_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/promethean-live-XXXXXX")"
# Root-owned files can appear inside the temp result root (created by the
# rootful container), so fall back to sudo for cleanup; best effort only.
trap 'rm -rf "$TEMP_RESULT_ROOT" 2>/dev/null || sudo -n rm -rf "$TEMP_RESULT_ROOT" 2>/dev/null || true' EXIT

# The container script lives in a quoted heredoc: nothing is expanded on the
# host; everything it needs is passed in via podman -e (KICKSTART_NAME,
# FEDORA_RELEASE). This keeps the quoting trivial and shellcheck clean.
CONTAINER_SCRIPT="$(cat <<'PROMETHEAN_CONTAINER_SCRIPT_EOF'
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
# policycoreutils (/usr/sbin/load_policy): anaconda invokes it while shutting
# down after a failed transaction; without it the real failure is masked by
# "AnacondaError: [Errno 2] No such file or directory: /usr/sbin/load_policy"
# (CI run 34399471667).
dnf -y install anaconda e2fsprogs lorax livemedia-creator isomd5sum pykickstart policycoreutils
lmc_rc=0
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
  --releasever="$FEDORA_RELEASE" || lmc_rc=$?
if [[ $lmc_rc -ne 0 ]]; then
  # On failure anaconda prints only a generic message to stdout; the
  # per-package/scriptlet error detail exists ONLY in log files (somewhere
  # under /var/log, /tmp or /workspace - run 34399471667 + 34402353556 were
  # undiagnosable). This container runs with --rm, so capture before exit:
  # 1. inventory of every log-ish file (printed to stdout - the CI console
  #    log is the one channel proven to survive);
  # 2. a tar of the known log locations, with tar's complaints captured
  #    instead of silenced so a wrong path is visible;
  # 3. tails of every inventory hit straight to stdout, bounded per file.
  dest=/tmp/live-root/build-logs
  mkdir -p "$dest"
  find /var/log /tmp /root /workspace -maxdepth 3 -type f \
       \( -name '*.log' -o -name '*anaconda*' -o -name 'lmc*' \
          -o -name 'syslog' -o -name 'journal*' -o -name 'dnf*' \) \
       -printf '%s\t%p\n' 2>/dev/null | sort -rn > "$dest/inventory.txt" || true
  echo "==== build log inventory (bytes, path) ===="
  cat "$dest/inventory.txt" || true
  # Capture with cp -a and container-ABSOLUTE paths instead of `tar -C /` with
  # relative members: the old tar produced an EMPTY logs.tar ("var/log/anaconda:
  # Cannot stat" in tar-errors.txt, run 34402353556) because the anaconda logs
  # actually land under /workspace/anaconda (the bind-mounted repo root), not
  # /var/log/anaconda. /tmp/live-root is bind-mounted to the host's temp result
  # dir, so everything staged here survives the --rm container.
  cp -a /workspace/anaconda "$dest/anaconda" \
    || echo "warning: /workspace/anaconda not found (anaconda may not have started)" >&2
  shopt -s nullglob
  workspace_logs=(/workspace/*.log)
  shopt -u nullglob
  if (( ${#workspace_logs[@]} > 0 )); then
    cp -a "${workspace_logs[@]}" "$dest/" \
      || echo "warning: failed to copy /workspace/*.log build logs" >&2
  else
    echo "note: no *.log files in /workspace (repo root)" >&2
  fi
  awk '{print $2}' "$dest/inventory.txt" 2>/dev/null | while IFS= read -r f; do
    case "$f" in "$dest"/*|*build-lmc.log|*.tar) continue;; esac
    echo "===== tail of $f ====="
    tail -c 200000 "$f" 2>/dev/null
    echo
  done
  echo "livemedia-creator failed (rc=$lmc_rc); logs preserved in $dest" >&2
  exit "$lmc_rc"
fi
PROMETHEAN_CONTAINER_SCRIPT_EOF
)"

podman_rc=0
"${RUN_AS_ROOT[@]}" podman run --rm \
  --privileged \
  -e KICKSTART_NAME="$(basename "$KICKSTART_FILE")" \
  -e FEDORA_RELEASE="$FEDORA_RELEASE" \
  -v "$REPO_ROOT:/workspace:Z" \
  -v "$TEMP_RESULT_ROOT:/tmp/live-root:Z" \
  -w /workspace \
  "$CONTAINER_IMAGE" \
  bash -lc "$CONTAINER_SCRIPT" || podman_rc=$?
if [[ $podman_rc -ne 0 ]]; then
  # Failure-log capture, host side, ALL paths absolute/anchored so the
  # wrong-cwd bug that produced an empty logs.tar (run 34402353556) cannot
  # recur. The container's /workspace is the bind mount of $REPO_ROOT, so
  # anaconda's logs (packaging.log, program.log, ...) written to
  # /workspace/anaconda in the container are already on the host at
  # "$REPO_ROOT/anaconda" the moment the container exits. Copy them into the
  # output dir BEFORE the EXIT trap deletes the temp result root. This handler
  # only runs on failure, so every step is guarded and what was captured is
  # echoed explicitly - it must never fail silently.
  mkdir -p "$OUTPUT_DIR/build-logs/anaconda"
  if [[ -d "$REPO_ROOT/anaconda" ]]; then
    # Anaconda logs in the bind view are root-owned (rootful container wrote
    # them through the mount); retry with sudo so this cp never fails noisy.
    cp -a "$REPO_ROOT/anaconda/." "$OUTPUT_DIR/build-logs/anaconda/" \
      || "${RUN_AS_ROOT[@]}" cp -a "$REPO_ROOT/anaconda/." "$OUTPUT_DIR/build-logs/anaconda/" \
      || echo "warning: cp of $REPO_ROOT/anaconda failed (plain and sudo)" >&2
  else
    echo "note: no anaconda logs at $REPO_ROOT/anaconda (anaconda may not have started)" >&2
  fi
  shopt -s nullglob
  repo_logs=("$REPO_ROOT"/*.log)
  shopt -u nullglob
  if (( ${#repo_logs[@]} > 0 )); then
    cp -a "${repo_logs[@]}" "$OUTPUT_DIR/build-logs/" \
      || "${RUN_AS_ROOT[@]}" cp -a "${repo_logs[@]}" "$OUTPUT_DIR/build-logs/" \
      || echo "warning: cp of repo-side build logs failed (plain and sudo)" >&2
  else
    echo "note: no repo-side build logs (*.log) in $REPO_ROOT" >&2
  fi
  # Whatever the container staged into the mounted result dir (inventory.txt,
  # its own cp of /workspace/anaconda). Root-owned by the rootful container,
  # so the copy needs the same sudo fallback as the cleanup trap.
  if [[ -d "$TEMP_RESULT_ROOT/build-logs" ]]; then
    "${RUN_AS_ROOT[@]}" cp -a "$TEMP_RESULT_ROOT/build-logs/." "$OUTPUT_DIR/build-logs/" \
      || echo "warning: could not copy staged logs from $TEMP_RESULT_ROOT/build-logs" >&2
  else
    echo "note: container staged nothing into $TEMP_RESULT_ROOT/build-logs" >&2
  fi
  "${RUN_AS_ROOT[@]}" chmod -R a+rX "$OUTPUT_DIR/build-logs" 2>/dev/null || true
  echo "ISO build failed (container exit $podman_rc). Captured failure logs:" >&2
  find "$OUTPUT_DIR/build-logs" -type f -printf '%s\t%p\n' 2>/dev/null | sort -rn >&2
  echo "==== captured build-log inventory (bytes, path) ====" >&2
  cat "$OUTPUT_DIR/build-logs/inventory.txt" >&2 \
    || echo "(no inventory.txt captured; rely on the console output above)" >&2
  exit "$podman_rc"
fi

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
