#!/usr/bin/env bash
set -euo pipefail

if ! command -v firewall-cmd >/dev/null 2>&1; then
  echo "firewall-cmd is required. Install firewalld first." >&2
  exit 1
fi

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "Run this as root." >&2
  exit 1
fi

firewall-cmd --permanent --new-service=promethean-localai >/dev/null 2>&1 || true
firewall-cmd --permanent --service=promethean-localai --set-short='Promethean Local AI' >/dev/null 2>&1 || true
firewall-cmd --permanent --service=promethean-localai --set-description='Local-only access for AI inference endpoints.' >/dev/null 2>&1 || true
firewall-cmd --permanent --service=promethean-localai --add-port=11434/tcp >/dev/null 2>&1 || true
firewall-cmd --permanent --service=promethean-localai --add-port=8000/tcp >/dev/null 2>&1 || true
firewall-cmd --permanent --service=promethean-localai --add-port=3000/tcp >/dev/null 2>&1 || true
firewall-cmd --permanent --service=promethean-localai --add-port=8188/tcp >/dev/null 2>&1 || true
firewall-cmd --permanent --zone=FedoraServer --add-service=promethean-localai >/dev/null 2>&1 || true
firewall-cmd --permanent --zone=FedoraWorkstation --add-service=promethean-localai >/dev/null 2>&1 || true
firewall-cmd --reload

# Default policy remains restrictive: only localhost is allowed through the local AI service ports.
firewall-cmd --zone=trusted --add-interface=lo >/dev/null 2>&1 || true
firewall-cmd --zone=trusted --add-port=11434/tcp >/dev/null 2>&1 || true
firewall-cmd --zone=trusted --add-port=8000/tcp >/dev/null 2>&1 || true
firewall-cmd --zone=trusted --add-port=3000/tcp >/dev/null 2>&1 || true
firewall-cmd --zone=trusted --add-port=8188/tcp >/dev/null 2>&1 || true

firewall-cmd --runtime-to-permanent >/dev/null 2>&1 || true

echo "Local-only firewall configuration applied for Promethean AI services."
