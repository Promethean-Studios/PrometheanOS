#!/usr/bin/env bash
set -euo pipefail

ISO="${1:-$(pwd)/build/output/PrometheanOS-KDE.iso}"
RAM_MB="${RAM_MB:-4096}"
CPUS="${CPUS:-2}"
BOOT_SECONDS="${BOOT_SECONDS:-90}"
SERIAL_LOG="${SERIAL_LOG:-$(pwd)/build/qemu-serial.log}"
# Optional, comma-separated markers that must appear in the serial log for the
# boot to count as successful (e.g. PROMETHEAN_ASSERT_MARKER="Reached target
# Graphical Interface,SDDM"). Empty/unset = no assertion (plain smoke run).
ASSERT_MARKERS="${PROMETHEAN_ASSERT_MARKER:-}"

if [[ ! -f "$ISO" ]]; then
  echo "ISO not found: $ISO" >&2
  echo "Build it first with: ./build.sh" >&2
  exit 1
fi
if ! command -v qemu-system-x86_64 >/dev/null 2>&1; then
  echo "qemu-system-x86_64 is required for the smoke test." >&2
  exit 1
fi

OVMF_CODE="${OVMF_CODE:-}"
if [[ -z "$OVMF_CODE" ]]; then
  for candidate in /usr/share/edk2/ovmf/OVMF_CODE.fd /usr/share/OVMF/OVMF_CODE.fd /usr/share/edk2/ovmf/OVMF_CODE_4M.fd; do
    if [[ -f "$candidate" ]]; then OVMF_CODE="$candidate"; break; fi
  done
fi
if [[ -z "$OVMF_CODE" ]]; then
  echo "UEFI firmware not found. Set OVMF_CODE to an OVMF_CODE.fd file." >&2
  exit 1
fi

mkdir -p "$(dirname "$SERIAL_LOG")"
: > "$SERIAL_LOG"

echo "Starting ${BOOT_SECONDS}s headless UEFI smoke test for $ISO"
status=0
timeout --foreground "${BOOT_SECONDS}s" qemu-system-x86_64 \
  -machine q35,accel=tcg \
  -cpu max \
  -m "$RAM_MB" \
  -smp "$CPUS" \
  -bios "$OVMF_CODE" \
  -cdrom "$ISO" \
  -boot d \
  -display none \
  -vga virtio \
  -serial file:"$SERIAL_LOG" \
  -nic user,model=virtio \
  -no-reboot \
  -monitor none || status=$?

if [[ -f "$SERIAL_LOG" ]]; then
  echo '--- QEMU serial log ---'
  tail -80 "$SERIAL_LOG"
fi

if [[ $status -eq 124 ]]; then
  echo "QEMU remained running for ${BOOT_SECONDS}s; boot smoke test completed."
else
  exit "$status"
fi

# Boot evidence assertion: every marker must appear in the serial log.
if [[ -n "$ASSERT_MARKERS" ]]; then
  failed=0
  IFS=',' read -ra markers <<< "$ASSERT_MARKERS"
  for marker in "${markers[@]}"; do
    marker="$(echo "$marker" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    if [[ -z "$marker" ]]; then continue; fi
    if grep -q -- "$marker" "$SERIAL_LOG"; then
      echo "ASSERTION OK: serial log contains: $marker"
    else
      echo "ASSERTION FAILED: serial log does not contain: $marker" >&2
      failed=1
    fi
  done
  if [[ $failed -ne 0 ]]; then
    echo "Boot evidence assertion failed for ISO: $ISO" >&2
    exit 1
  fi
fi
exit 0