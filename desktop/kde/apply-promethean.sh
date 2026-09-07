#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
mkdir -p "$DATA_HOME/color-schemes" "$DATA_HOME/wallpapers/Promethean" "$DATA_HOME/applications"
cp "$ROOT/desktop/kde/Promethean.colors" "$DATA_HOME/color-schemes/Promethean.colors"
cp "$ROOT/desktop/wallpaper/promethean-wallpaper.svg" "$DATA_HOME/wallpapers/Promethean/promethean-wallpaper.svg"
cp "$ROOT/desktop/kde/promethean-control-center.desktop" "$DATA_HOME/applications/promethean-control-center.desktop"
mkdir -p "$DATA_HOME/plasma/layout-templates/promethean/contents"
cp "$ROOT/desktop/kde/layout-template/metadata.desktop" "$DATA_HOME/plasma/layout-templates/promethean/metadata.desktop"
cp "$ROOT/desktop/kde/layout-template/contents/layout.js" "$DATA_HOME/plasma/layout-templates/promethean/contents/layout.js"

if command -v kwriteconfig6 >/dev/null 2>&1; then
  kwriteconfig6 --file "$CONFIG_HOME/kdeglobals" --group KDE --key ColorScheme Promethean
  kwriteconfig6 --file "$CONFIG_HOME/kdeglobals" --group KDE --key LookAndFeelPackage org.kde.breeze.desktop
  kwriteconfig6 --file "$CONFIG_HOME/kdeglobals" --group Icons --key Theme breeze-dark
  kwriteconfig6 --file "$CONFIG_HOME/kdeglobals" --group General --key widgetStyle Breeze
  kwriteconfig6 --file "$CONFIG_HOME/kdeglobals" --group WM --key activeBackground 25,35,31
  kwriteconfig6 --file "$CONFIG_HOME/kdeglobals" --group WM --key inactiveBackground 24,30,29
  kwriteconfig6 --file "$CONFIG_HOME/kwinrc" --group org.kde.kdecoration2 --key library org.kde.breeze
  kwriteconfig6 --file "$CONFIG_HOME/kwinrc" --group org.kde.kdecoration2 --key theme Breeze
  kwriteconfig6 --file "$CONFIG_HOME/kwinrc" --group Compositing --key Enabled true
  kwriteconfig6 --file "$CONFIG_HOME/kwinrc" --group Compositing --key AnimationSpeed 1
  kwriteconfig6 --file "$CONFIG_HOME/plasmarc" --group Theme --key name default
fi

if command -v plasma-apply-wallpaperimage >/dev/null 2>&1; then
  plasma-apply-wallpaperimage "$DATA_HOME/wallpapers/Promethean/promethean-wallpaper.svg" || true
fi

if [[ "${PROMETHEAN_APPLY_LAYOUT:-0}" == "1" ]] && command -v plasma-apply-layout-template >/dev/null 2>&1; then
  plasma-apply-layout-template "$DATA_HOME/plasma/layout-templates/promethean" || true
fi

echo "Promethean KDE defaults installed for the current user. Log out and in if Plasma does not refresh immediately."