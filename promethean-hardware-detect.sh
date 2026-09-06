#!/usr/bin/env bash
set -u

# Read-only hardware probe. Driver installation belongs to an explicit,
# user-confirmed administrative workflow and never runs at boot.
LOG_FILE="${PROMETHEAN_HARDWARE_LOG:-/var/log/promethean-hardware.log}"
if ! mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || ! touch "$LOG_FILE" 2>/dev/null; then
  LOG_FILE="/tmp/promethean-hardware.log"
fi
exec >>"$LOG_FILE" 2>&1

log() {
  echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] $*"
}

detect_gpu() {
  if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1; then
    echo "nvidia"
    return
  fi
  if [[ -d /sys/class/drm ]]; then
    for device in /sys/class/drm/*/device/vendor; do
      [[ -r "$device" ]] || continue
      case "$(<"$device")" in
        0x10de) echo "nvidia"; return ;;
        0x1002) echo "amd"; return ;;
        0x8086) echo "intel"; return ;;
      esac
    done
  fi
  if command -v lspci >/dev/null 2>&1; then
    if lspci 2>/dev/null | grep -Eqi 'nvidia'; then echo "nvidia"; return; fi
    if lspci 2>/dev/null | grep -Eqi 'amd|radeon'; then echo "amd"; return; fi
    if lspci 2>/dev/null | grep -Eqi 'intel'; then echo "intel"; return; fi
  fi
  echo "cpu"
}

gpu="$(detect_gpu)"
log "Promethean hardware detection started. GPU family: ${gpu}"
case "$gpu" in
  nvidia) log "NVIDIA detected; driver state is reported, not changed at boot." ;;
  amd) log "AMD detected; ROCm state is reported by the capability engine." ;;
  intel) log "Intel graphics detected; no vendor runtime changes required." ;;
  cpu) log "CPU-only or GPU telemetry unavailable; continuing without GPU setup." ;;
esac
log "Promethean hardware detection completed."
