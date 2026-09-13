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
OVMF_VARS="${OVMF_VARS:-}"
if [[ -z "$OVMF_CODE" ]]; then
  # Discovery order: pflash code-image PAIRS first (a matching VARS store is
  # resolved below), then combined code+vars images, then qemu's standalone
  # blob. qemu's x86 -bios loader only accepts firmware whose size is a
  # multiple of 64 KiB: Ubuntu 24.04's OVMF_CODE_4M.fd is 3,653,632 bytes
  # (0x37C000) - NOT 64 KiB aligned - so -bios fails with "could not load
  # PC BIOS" (run 34701616631). Code-only images must use pflash.
  for candidate in \
    /usr/share/OVMF/OVMF_CODE_4M.fd \
    /usr/share/OVMF/OVMF_CODE.fd \
    /usr/share/ovmf/OVMF.fd \
    /usr/share/qemu/OVMF.fd \
    /usr/share/edk2/ovmf/OVMF_CODE.fd \
    /usr/share/edk2/ovmf/OVMF_CODE_4M.fd \
    /usr/share/edk2-ovmf/x64/OVMF_CODE.fd \
    /usr/share/qemu/edk2-x86_64-code.fd; do
    if [[ -f "$candidate" ]]; then OVMF_CODE="$candidate"; break; fi
  done
fi
# Last resort: search the standard firmware trees so a renamed/republished
# package layout cannot break discovery again.
if [[ -z "$OVMF_CODE" ]]; then
  OVMF_CODE="$(find /usr/share/OVMF /usr/share/ovmf /usr/share/edk2 /usr/share/edk2-ovmf /usr/share/qemu \
      -maxdepth 3 \( -name 'OVMF_CODE*.fd' -o -name 'OVMF.fd' -o -name 'edk2-x86_64-code.fd' \) -print 2>/dev/null \
      | sort | head -n 1 || true)"
fi
if [[ -z "$OVMF_CODE" ]]; then
  echo "UEFI firmware not found. Set OVMF_CODE to an OVMF_CODE.fd file" >&2
  echo "(searched: /usr/share/OVMF /usr/share/ovmf /usr/share/edk2 /usr/share/edk2-ovmf /usr/share/qemu)." >&2
  exit 1
fi

# Firmware invocation by image type:
# - OVMF_CODE*.fd are code-only pflash images: pair with a WRITABLE copy of
#   the matching OVMF_VARS*.fd store (vars must be writable at runtime).
# - combined images (OVMF.fd, code+vars in one) and qemu's standalone
#   edk2-x86_64-code.fd load via plain -bios.
FIRMWARE_ARGS=()
if [[ "$(basename "$OVMF_CODE")" == OVMF_CODE*.fd ]]; then
  if [[ -z "$OVMF_VARS" ]]; then
    variant="$(basename "$OVMF_CODE" | sed 's/^OVMF_CODE/OVMF_VARS/')"
    for vcand in "$(dirname "$OVMF_CODE")/$variant" \
                 "$(dirname "$OVMF_CODE")"/OVMF_VARS*.fd \
                 /usr/share/OVMF/OVMF_VARS_4M.fd \
                 /usr/share/OVMF/OVMF_VARS.fd; do
      if [[ -f "$vcand" ]]; then OVMF_VARS="$vcand"; break; fi
    done
  fi
  if [[ -z "$OVMF_VARS" ]]; then
    OVMF_VARS="$(find /usr/share/OVMF /usr/share/ovmf /usr/share/edk2 /usr/share/edk2-ovmf \
        -maxdepth 3 -name 'OVMF_VARS*.fd' -print 2>/dev/null | sort | head -n 1 || true)"
  fi
  if [[ -z "$OVMF_VARS" ]]; then
    echo "OVMF VARS store not found for $OVMF_CODE (set OVMF_VARS)." >&2
    exit 1
  fi
  VARS_COPY="$(mktemp "${TMPDIR:-/tmp}/ovmf-vars.XXXXXX.fd")"
  cp "$OVMF_VARS" "$VARS_COPY"
  trap 'rm -f "$VARS_COPY"' EXIT
  FIRMWARE_ARGS=(-drive "if=pflash,format=raw,readonly=on,file=$OVMF_CODE" \
                 -drive "if=pflash,format=raw,file=$VARS_COPY")
  echo "Using OVMF firmware: $OVMF_CODE + VARS $OVMF_VARS (pflash)"
else
  FIRMWARE_ARGS=(-bios "$OVMF_CODE")
  echo "Using OVMF firmware: $OVMF_CODE (-bios)"
fi

mkdir -p "$(dirname "$SERIAL_LOG")"
: > "$SERIAL_LOG"

# Live boot entry selection: GRUB's default entry on lorax live media is
# "Test this media & start ..." which adds rd.live.check, and checkisomd5
# always fails on CI-built ISOs: livemedia-creator --make-iso does NOT run
# implantisomd5, so there is no embedded checksum and checkisomd5 exits
# ISOMD5SUM_CHECK_NOT_FOUND (2) - dracut then reports "Media check failed!"
# and halts the boot (run 34776376447). The ISO build is out of scope, so
# the smoke test boots the equivalent plain "Start <product>" path directly:
# extract the live kernel + initrd from the ISO and pass the "Start" entry's
# kernel args (identical, minus rd.live.check) via -kernel/-initrd. Falls
# back to GRUB's default menu entry if extraction fails.
KERNEL_ARGS=""
KERN_FILE=""
INITRD_FILE=""
EXTRACT_DIR="$(mktemp -d "${TMPDIR:-/tmp}/promethean-iso.XXXXXX")"
extract_iso_files() {
  if command -v bsdtar >/dev/null 2>&1; then
    bsdtar -x -f "$ISO" -C "$EXTRACT_DIR" \
      images/pxeboot/vmlinuz images/pxeboot/initrd.img \
      boot/grub2/grub.cfg EFI/BOOT/grub.cfg 2>/dev/null
  else
    sudo mkdir -p /mnt/promethean-iso && \
    sudo mount -o loop,ro "$ISO" /mnt/promethean-iso && {
      for f in images/pxeboot/vmlinuz images/pxeboot/initrd.img \
               boot/grub2/grub.cfg EFI/BOOT/grub.cfg; do
        mkdir -p "$EXTRACT_DIR/$(dirname "$f")"
        cp "/mnt/promethean-iso/$f" "$EXTRACT_DIR/$f" || return 1
      done
      sudo umount /mnt/promethean-iso
    }
  fi
}
extract_iso_files || true
if [[ -f "$EXTRACT_DIR/images/pxeboot/vmlinuz" && -f "$EXTRACT_DIR/images/pxeboot/initrd.img" ]]; then
  grub_cfg="$EXTRACT_DIR/boot/grub2/grub.cfg"
  [[ -f "$grub_cfg" ]] || grub_cfg="$EXTRACT_DIR/EFI/BOOT/grub.cfg"
  if [[ -f "$grub_cfg" ]]; then
    # Kernel args of the plain "Start <product>" entry: the linux line
    # WITHOUT rd.live.check.
    line="$(grep -hE '^[[:space:]]*linux(efi)?[[:space:]]' "$grub_cfg" \
            | grep -v 'rd\.live\.check' | head -n1 || true)"
    if [[ -n "$line" ]]; then
      KERNEL_ARGS="$(printf '%s\n' "$line" | awk '{ $1=""; $2=""; sub(/^[ \t]+/, ""); print }')"
      [[ "$KERNEL_ARGS" == *console=ttyS0* ]] || KERNEL_ARGS="$KERNEL_ARGS console=ttyS0,115200"
      KERN_FILE="$EXTRACT_DIR/images/pxeboot/vmlinuz"
      INITRD_FILE="$EXTRACT_DIR/images/pxeboot/initrd.img"
    fi
  fi
fi

echo "Starting ${BOOT_SECONDS}s headless UEFI smoke test for $ISO"
status=0
BOOT_CMD=(timeout --foreground "${BOOT_SECONDS}s" qemu-system-x86_64
  "-machine" "q35,accel=tcg"
  -cpu max
  -m "$RAM_MB"
  -smp "$CPUS"
  "${FIRMWARE_ARGS[@]}")
if [[ -n "$KERN_FILE" && -n "$KERNEL_ARGS" ]]; then
  echo "Booting live kernel directly with the plain-start args (media check skipped)"
  BOOT_CMD+=(-kernel "$KERN_FILE" -initrd "$INITRD_FILE" -append "$KERNEL_ARGS" -cdrom "$ISO")
else
  echo "WARNING: could not extract live kernel/args from ISO; booting via GRUB menu" >&2
  BOOT_CMD+=(-cdrom "$ISO" -boot d)
fi
"${BOOT_CMD[@]}" \
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