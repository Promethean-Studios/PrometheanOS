#!/usr/bin/env bash
set -u

LOG_FILE="/var/log/promethean-hardware.log"
mkdir -p "$(dirname "$LOG_FILE")"
exec >>"$LOG_FILE" 2>&1

log() {
  echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] $*"
}

require_root() {
  if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    log "This script must run as root."
    exit 1
  fi
}

has_cmd() {
  command -v "$1" >/dev/null 2>&1
}

install_akmods() {
  local driver_pkg=""
  if has_cmd dnf; then
    driver_pkg="akmod-nvidia"
  else
    log "No supported package manager found for akmods installation."
    return 1
  fi

  log "Installing NVIDIA akmods: $driver_pkg"
  dnf install -y "$driver_pkg" kernel-devel kernel-headers
  akmods --force
  depmod -a
  modprobe nvidia
  if has_cmd nvidia-smi; then
    log "NVIDIA proprietary stack appears loaded."
  else
    log "nvidia-smi is still unavailable after akmods install; manual NVIDIA driver troubleshooting may be required."
  fi
}

ensure_cuda() {
  if has_cmd dnf; then
    dnf install -y cuda-toolkit cuda-nsight-systems
  else
    log "No supported package manager found for CUDA installation."
  fi
}

install_rocm_runtime() {
  log "Installing ROCm runtime packages."
  if has_cmd dnf; then
    dnf install -y rocm-runtime rocm-opencl pciutils
  else
    log "No supported package manager found for ROCm installation."
  fi

  # Ensure render and KFD devices are readable by the logged-in user session.
  usermod -a -G render,video "$(logname 2>/dev/null || echo promethean)" 2>/dev/null || true
  chmod 0666 /dev/dri/* 2>/dev/null || true
  chmod 0666 /dev/kfd 2>/dev/null || true
}

configure_rocm_defaults() {
  local gpu_name="${1:-}"
  if [[ "$gpu_name" == *"Radeon"* || "$gpu_name" == *"RX 7"* || "$gpu_name" == *"RX 8"* || "$gpu_name" == *"Radeon RX"* ]]; then
    log "Detected a standard RDNA2/3 AMD card; setting HSA_OVERRIDE_GFX_VERSION defaults."
    mkdir -p /etc/profile.d
    cat > /etc/profile.d/promethean-rocm.sh <<'EOF'
export HSA_OVERRIDE_GFX_VERSION=10.3.0
EOF
    chmod 0644 /etc/profile.d/promethean-rocm.sh
  else
    log "AMD GPU detected but no standard RDNA2/3 default override was applied."
  fi
}

detect_gpu() {
  if has_cmd nvidia-smi; then
    echo "nvidia"
    return 0
  fi

  if [[ -e /sys/class/drm ]]; then
    for d in /sys/class/drm/*; do
      if [[ -f "$d/device/vendor" ]]; then
        vendor=$(tr -d '\n' < "$d/device/vendor" 2>/dev/null || true)
        if [[ "$vendor" == "0x10de" ]]; then
          echo "nvidia"
          return 0
        fi
        if [[ "$vendor" == "0x1002" ]]; then
          echo "amd"
          return 0
        fi
        if [[ "$vendor" == "0x8086" ]]; then
          echo "intel"
          return 0
        fi
      fi
    done
  fi

  if has_cmd lspci; then
    if lspci 2>/dev/null | grep -qi 'nvidia'; then echo "nvidia"; return 0; fi
    if lspci 2>/dev/null | grep -qi 'amd\|radeon'; then echo "amd"; return 0; fi
    if lspci 2>/dev/null | grep -qi 'intel'; then echo "intel"; return 0; fi
  fi

  echo "cpu"
}

check_nvidia_stack() {
  local nvidia_mod_loaded=0
  local cuda_loaded=0

  if lsmod 2>/dev/null | grep -qi '^nvidia'; then
    nvidia_mod_loaded=1
  fi
  if has_cmd nvcc; then
    cuda_loaded=1
  fi

  if [[ $nvidia_mod_loaded -eq 0 || $cuda_loaded -eq 0 ]]; then
    log "NVIDIA stack incomplete: mod_loaded=$nvidia_mod_loaded cuda_loaded=$cuda_loaded"
    install_akmods
    ensure_cuda
  else
    log "NVIDIA driver and CUDA stack are present."
  fi
}

check_amd_stack() {
  local gpu_name="$(lspci 2>/dev/null | grep -i 'vga\|3d\|display' | head -n 1 || true)"
  log "AMD GPU detected: ${gpu_name:-unknown}"

  for path in /dev/kfd /dev/dri; do
    if [[ -e "$path" ]]; then
      chmod 0666 "$path" 2>/dev/null || true
      log "Permissions normalized on $path"
    fi
  done

  install_rocm_runtime
  configure_rocm_defaults "$gpu_name"
}

check_intel_stack() {
  log "Intel GPU detected; no special ROCm workflow required."
  if has_cmd intel_gpu_top; then
    log "Intel GPU tools are present."
  fi
}

main() {
  require_root
  log "Promethean hardware detection started."

  local gpu
  gpu="$(detect_gpu)"
  log "Detected GPU family: $gpu"

  case "$gpu" in
    nvidia)
      check_nvidia_stack
      ;;
    amd)
      check_amd_stack
      ;;
    intel)
      check_intel_stack
      ;;
    cpu)
      log "CPU-only system detected; no GPU runtime configuration required."
      ;;
    *)
      log "Unknown GPU profile: $gpu"
      ;;
  esac

  log "Promethean hardware detection completed."
}

main "$@"
