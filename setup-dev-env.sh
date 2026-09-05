#!/usr/bin/env bash
set -euo pipefail

TARGET_BIN="/usr/local/bin"
mkdir -p "$TARGET_BIN"

log() {
  echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] $*"
}

require_root() {
  if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    echo "This script must be run as root." >&2
    exit 1
  fi
}

install_uv() {
  if command -v uv >/dev/null 2>&1; then
    log "uv already installed: $(command -v uv)"
    return 0
  fi

  curl -LsSf https://astral.sh/uv/install.sh | sh
  ln -sf "$HOME/.local/bin/uv" "$TARGET_BIN/uv" 2>/dev/null || true
  if ! command -v uv >/dev/null 2>&1; then
    log "uv not found in PATH after install; attempting fallback installation."
    mkdir -p /usr/local/bin
    curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh
  fi

  log "uv installed to $(command -v uv || echo /usr/local/bin/uv)"
}

install_pixi() {
  if command -v pixi >/dev/null 2>&1; then
    log "pixi already installed: $(command -v pixi)"
    return 0
  fi

  curl -fsSL https://pixi.sh/install.sh | sh
  ln -sf "$HOME/.pixi/bin/pixi" "$TARGET_BIN/pixi" 2>/dev/null || true
  if ! command -v pixi >/dev/null 2>&1; then
    log "pixi not found in PATH after install; attempting fallback installation."
    curl -fsSL https://pixi.sh/install.sh | env PIXI_HOME="/usr/local/share/pixi" PREFIX="/usr/local" sh
  fi

  log "pixi installed to $(command -v pixi || echo /usr/local/bin/pixi)"
}

detect_gpu() {
  if command -v nvidia-smi >/dev/null 2>&1; then
    echo "nvidia"
    return 0
  fi

  if lspci 2>/dev/null | grep -qi 'amd\|radeon'; then
    echo "amd"
    return 0
  fi

  if lspci 2>/dev/null | grep -qi 'intel'; then
    echo "intel"
    return 0
  fi

  echo "cpu"
}

ensure_cache_dir() {
  mkdir -p /data/models/huggingface /data/models/ollama /data/models/cache
  chmod -R 0775 /data/models
}

precache_pytorch() {
  local gpu
  gpu="$(detect_gpu)"
  local torch_cmd

  ensure_cache_dir

  case "$gpu" in
    nvidia)
      torch_cmd="uv pip install --system --cache-dir /data/models/cache torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121"
      ;;
    amd)
      torch_cmd="uv pip install --system --cache-dir /data/models/cache torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm5.7"
      ;;
    *)
      torch_cmd="uv pip install --system --cache-dir /data/models/cache torch torchvision torchaudio"
      ;;
  esac

  log "Pre-caching PyTorch for ${gpu} environment."
  bash -lc "$torch_cmd" || log "PyTorch pre-cache command failed; continuing with environment setup."
}

install_profile_defaults() {
  cat > /etc/profile.d/promethean.sh <<'EOF'
export HF_HOME=/data/models/huggingface
export HUGGINGFACE_HUB_CACHE=/data/models/huggingface
export OLLAMA_MODELS=/data/models/ollama
export TRANSFORMERS_CACHE=/data/models/huggingface
export XDG_CACHE_HOME=/data/models/cache
export UV_CACHE_DIR=/data/models/cache
export PIXI_CACHE_DIR=/data/models/cache
export PIP_CACHE_DIR=/data/models/cache
export CMAKE_BUILD_PARALLEL_LEVEL=4
export PYTHONUNBUFFERED=1
EOF
  chmod 0644 /etc/profile.d/promethean.sh

  log "Installed Promethean global shell defaults in /etc/profile.d/promethean.sh"
}

main() {
  require_root
  install_uv
  install_pixi
  precache_pytorch
  install_profile_defaults
  log "Promethean development environment bootstrap complete."
}

main "$@"
