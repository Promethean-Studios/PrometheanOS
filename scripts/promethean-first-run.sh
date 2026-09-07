#!/usr/bin/env bash
set -eu

system_state=/var/lib/promethean/setup.json
user_state="${XDG_CONFIG_HOME:-$HOME/.config}/promethean/setup.json"
if { [[ -f "$system_state" ]] && grep -q '"completed": true' "$system_state"; } || { [[ -f "$user_state" ]] && grep -q '"completed": true' "$user_state"; }; then
    exit 0
fi
exec xdg-open http://127.0.0.1:8765/setup
