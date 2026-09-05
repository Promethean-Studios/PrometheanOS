#!/usr/bin/env bash
set -euo pipefail

CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
mkdir -p "$CONFIG_HOME"
if command -v kwriteconfig6 >/dev/null 2>&1; then
  kwriteconfig6 --file "$CONFIG_HOME/kwinrc" --group Compositing --key Enabled false
  kwriteconfig6 --file "$CONFIG_HOME/kwinrc" --group Compositing --key AnimationSpeed 0
fi
echo "Promethean low-end desktop mode enabled: compositor and animation effects disabled."