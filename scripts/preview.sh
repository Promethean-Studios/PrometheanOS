#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ISO="${ISO:-$ROOT/build/output/PrometheanOS-KDE.iso}"
RAM_MB="${RAM_MB:-4096}"
CPUS="${CPUS:-4}"
VNC_DISPLAY="${VNC_DISPLAY:-1}"
VNC_HOST="${VNC_HOST:-127.0.0.1}"
NOVNC_PORT="${NOVNC_PORT:-6080}"
SERIAL_LOG="${SERIAL_LOG:-$ROOT/build/preview-serial.log}"

if ! command -v qemu-system-x86_64 >/dev/null 2>&1; then
  echo "qemu-system-x86_64 is required." >&2
  exit 1
fi

if [[ ! -f "$ISO" ]]; then
  echo "ISO not found; running ./build.sh..."
  "$ROOT/build.sh"
fi
if [[ ! -f "$ISO" ]]; then
  echo "ISO build completed without producing: $ISO" >&2
  exit 1
fi

OVMF_CODE="${OVMF_CODE:-}"
if [[ -z "$OVMF_CODE" ]]; then
  for candidate in \
    /usr/share/edk2/ovmf/OVMF_CODE.fd \
    /usr/share/edk2/ovmf/OVMF_CODE_4M.fd \
    /usr/share/OVMF/OVMF_CODE.fd; do
    if [[ -f "$candidate" ]]; then
      OVMF_CODE="$candidate"
      break
    fi
  done
fi
if [[ -z "$OVMF_CODE" ]]; then
  echo "UEFI firmware not found. Set OVMF_CODE to an OVMF_CODE.fd file." >&2
  exit 1
fi

if ! [[ "$VNC_DISPLAY" =~ ^[0-9]+$ && "$NOVNC_PORT" =~ ^[0-9]+$ ]]; then
  echo "VNC_DISPLAY and NOVNC_PORT must be numeric." >&2
  exit 1
fi

mkdir -p "$(dirname "$SERIAL_LOG")"
: > "$SERIAL_LOG"
QEMU_PID=""
WEBSOCKIFY_PID=""

cleanup() {
  trap - EXIT INT TERM
  if [[ -n "$WEBSOCKIFY_PID" ]]; then
    kill "$WEBSOCKIFY_PID" 2>/dev/null || true
  fi
  if [[ -n "$QEMU_PID" ]]; then
    kill "$QEMU_PID" 2>/dev/null || true
    wait "$QEMU_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

qemu-system-x86_64 \
  -machine q35,accel=tcg \
  -cpu max \
  -m "$RAM_MB" \
  -smp "$CPUS" \
  -bios "$OVMF_CODE" \
  -cdrom "$ISO" \
  -boot d \
  -display none \
  -vnc "$VNC_HOST:$VNC_DISPLAY" \
  -vga virtio \
  -nic user,model=virtio \
  -serial file:"$SERIAL_LOG" \
  -no-reboot &
QEMU_PID=$!

WEBSOCKIFY="$(command -v websockify || true)"
NOVNC_WEB=""
for candidate in \
  /usr/share/novnc \
  /usr/share/noVNC \
  "$ROOT/.novnc"; do
  if [[ -f "$candidate/vnc.html" ]]; then
    NOVNC_WEB="$candidate"
    break
  fi
done

if [[ -n "$WEBSOCKIFY" && -n "$NOVNC_WEB" ]]; then
  "$WEBSOCKIFY" --web "$NOVNC_WEB" "$NOVNC_PORT" "$VNC_HOST:$((5900 + VNC_DISPLAY))" &
  WEBSOCKIFY_PID=$!
  echo "PrometheanOS QEMU preview is running."
  echo "Open: http://127.0.0.1:$NOVNC_PORT/vnc.html?host=127.0.0.1&port=$NOVNC_PORT"
else
  echo "PrometheanOS QEMU preview is running."
  echo "VNC is available at $VNC_HOST:$((5900 + VNC_DISPLAY))."
  echo "Install noVNC/websockify to use a browser, or connect with a VNC viewer."
fi
echo "Press Ctrl-C to stop the VM. Serial log: $SERIAL_LOG"

wait "$QEMU_PID"