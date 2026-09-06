#!/usr/bin/env bash
set -euo pipefail

ISO="${1:-$(pwd)/build/output/PrometheanOS-KDE.iso}"
RAM_MB="${RAM_MB:-4096}"
CPUS="${CPUS:-2}"
BOOT_SECONDS="${BOOT_SECONDS:-90}"

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

echo "Starting ${BOOT_SECONDS}s headless UEFI smoke test for $ISO"
timeout --foreground "${BOOT_SECONDS}s" qemu-system-x86_64 \
  -machine q35,accel=kvm:tcg \
  -cpu max \
  -m "$RAM_MB" \
  -smp "$CPUS" \
  -bios "$OVMF_CODE" \
  -cdrom "$ISO" \
  -boot d \
  -display none \
  -serial stdio \
  -nic user,model=virtio \
  -no-reboot \
  -monitor none

status=$?
if [[ $status -eq 124 ]]; then
  echo "QEMU remained running for ${BOOT_SECONDS}s; boot smoke test completed." 
  exit 0
fi
exit "$status"