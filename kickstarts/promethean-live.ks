# First testable PrometheanOS Fedora KDE live image.
# This file is consumed by livemedia-creator --make=live. It intentionally
# contains no disk, bootloader, clearpart, or reboot directives.

url --mirrorlist="https://mirrors.fedoraproject.org/metalink?repo=fedora-${releasever}&arch=$basearch"
repo --name=fedora --mirrorlist="https://mirrors.fedoraproject.org/metalink?repo=fedora-${releasever}&arch=$basearch"
repo --name=updates --mirrorlist="https://mirrors.fedoraproject.org/metalink?repo=updates-released-f${releasever}&arch=$basearch"

lang en_US.UTF-8
keyboard us
timezone UTC --utc
network --bootproto=dhcp --device=link --activate

rootpw --lock
# livemedia-creator sizes the build disk image from this partition
# (calculate_disk_size raises "No / partition in the kickstart" without it)
# and anaconda creates it inside the installer VM. Same pattern as lorax's
# own fedora-livemedia.ks example.
# 12288 MiB: anaconda requires the transaction to fit the / filesystem and the full KDE live set installs ~8.9 GB (run 34403642413: dnf "needs 720MB more space" at 8192); the ISO payload is squashfs-compressed, so this only affects build-time disk on a sparse image.
part / --size=12288
# livemedia-creator's virt install only sees qemu exit when anaconda powers
# the VM off; without `shutdown` the VM resets and lmc waits forever
# (pylorax LogMonitor has no completion signal without it). Same directive as
# lorax's own fedora-livemedia.ks; it affects nothing in the built image.
shutdown
user --name=promethean --groups=wheel --shell=/bin/bash

%packages
@core
@^kde-desktop-environment
@kde-apps
@base-x
@fonts
@networkmanager-submodules
NetworkManager-wifi
# SDDM is the configured display manager (see /etc/sddm.conf.d autologin) and is not implied by the KDE environment group on F44.
sddm
sddm-wayland-plasma
pciutils
firewalld
git
curl
wget
python3
python3-pip
python3-psutil
podman
sudo
pipewire
pipewire-alsa
pipewire-pulseaudio
wireplumber
nss-mdns
# Required for the live ISO to boot: livemedia-creator rebuilds the initramfs
# with --add dmsquash-live and hard-fails --make-iso without dracut-live;
# dracut-config-generic matches its --no-hostonly rebuild. Fedora's own
# livemedia kickstart ships all three.
dracut-live
dracut-config-generic
kernel-modules
# lorax's x86.tmpl builds the BIOS El Torito image from <installed-root>/usr/lib/grub/i386-pc; anaconda --dirinstall doesn't install BIOS modules, so grub2-pc-modules must be listed here (run 34535387943 moddep.lst evidence)
grub2-pc-modules
# lorax's live x86.tmpl only builds the ISO's EFI/BOOT tree if
# boot/efi/EFI/*/gcdx64.efi exists in the installed root, yet grafts
# EFI/BOOT= unconditionally into xorrisofs - without these packages the
# whole build dies there (run 34546284062: "xorriso : FAILURE : Cannot
# determine attributes of source file '.../EFI/BOOT'"). Same set lorax's
# own fedora-livemedia.ks adds for x86_64. The %post below copies the
# staged binaries into boot/efi/EFI/fedora: F44 ships them under
# /usr/lib/efi/... and a BIOS-booted build VM never creates the ESP.
shim-x64
grub2-efi-x64
grub2-efi-x64-cdboot
efibootmgr
%end

%post --nochroot --log=/mnt/sysimage/root/promethean-copy.log --erroronfail
set -eu
install -d -m 0755 /mnt/sysimage/srv/promethean
# The virt install VM has no /workspace (lmc injects only the kickstart and
# the extra --ks files into the VM's initrd). The repo payload arrives as
# payload.tar.gz at the initrd root; the anaconda installer runtime ships
# tar (lorax runtime-install.tmpl: installpkg tar xz curl bzip2).
# A /workspace bind mount only exists in container-direct builds, which are
# kept as a fallback.
if [[ -s /payload.tar.gz ]]; then
    tar -xzf /payload.tar.gz -C /mnt/sysimage/srv/promethean/
elif [[ -d /workspace ]]; then
    cp -a /workspace/. /mnt/sysimage/srv/promethean/
else
    echo "FATAL: no repo payload found (expected /payload.tar.gz or /workspace)" >&2
    exit 1
fi
# The rm also sweeps build debris: build.sh's temp result root was once inside
# the repo (now /tmp), and any future in-repo output dir (build/) must never be
# baked into the image (CI run 34522793350: 12 GB disk image copied into target).
rm -rf /mnt/sysimage/srv/promethean/.git /mnt/sysimage/srv/promethean/.pytest_cache /mnt/sysimage/srv/promethean/__pycache__ /mnt/sysimage/srv/promethean/.promethean-live-* /mnt/sysimage/srv/promethean/build
%end

%post --log=/root/promethean-post.log --erroronfail
set -eu
# lorax's live x86.tmpl sources the ISO's EFI/BOOT tree from
# boot/efi/EFI/*/gcdx64.efi (+shimx64/mm). On F44 the EFI packages stage
# those binaries under /usr/lib/efi/<ver>/EFI/fedora, and the build VM boots
# BIOS so anaconda never creates the ESP vendor dir - copy them where the
# template looks. No-op if something already populated it.
efi_vendor=/boot/efi/EFI/fedora
if [[ ! -e "$efi_vendor/gcdx64.efi" && -d /usr/lib/efi ]]; then
    install -d -m 0755 "$efi_vendor"
    cp -a /usr/lib/efi/grub2/*/EFI/fedora/gcdx64.efi "$efi_vendor/" 2>/dev/null || true
    cp -a /usr/lib/efi/shim/*/EFI/fedora/shimx64.efi "$efi_vendor/" 2>/dev/null || true
    cp -a /usr/lib/efi/shim/*/EFI/fedora/mmx64.efi "$efi_vendor/" 2>/dev/null || true
fi
# Mirror Fedora's liveuser pattern (livesys-scripts): the autologin user gets
# an EMPTY password, not a locked one. SDDM's sddm-autologin PAM stack uses
# pam_permit for auth, but a locked password field is the known cause of
# autologin bouncing back to the greeter.
passwd -d promethean
install -d -m 0775 -o promethean -g promethean /data/models /data/models/ollama /data/models/huggingface /data/models/cache
install -d -m 0755 /usr/local/libexec/promethean /usr/share/promethean/desktop /etc/xdg/autostart
install -m 0755 /srv/promethean/promethean-hardware-detect.sh /usr/local/libexec/promethean/hardware-detect.sh
install -m 0755 /srv/promethean/scripts/promethean-first-run.sh /usr/local/libexec/promethean/first-run.sh
cp -a /srv/promethean/desktop/. /usr/share/promethean/desktop/
install -m 0644 /srv/promethean/desktop/kde/promethean-control-center.desktop /usr/share/applications/promethean-control-center.desktop
install -m 0644 /srv/promethean/desktop/kde/promethean-first-run.desktop /etc/xdg/autostart/promethean-first-run.desktop
install -d -m 0755 /etc/systemd/system
install -m 0644 /srv/promethean/systemd/promethean-api.service /etc/systemd/system/promethean-api.service
install -m 0644 /srv/promethean/systemd/promethean-hardware-detect.service /etc/systemd/system/promethean-hardware-detect.service
install -m 0644 /srv/promethean/systemd/promethean-ollama.service /etc/systemd/system/promethean-ollama.service
printf '%s\n' '%wheel ALL=(ALL) ALL' > /etc/sudoers.d/10-promethean-wheel
chmod 0440 /etc/sudoers.d/10-promethean-wheel
mkdir -p /etc/sddm.conf.d /etc/profile.d
cat > /etc/sddm.conf.d/10-promethean-live.conf <<'EOF'
[Autologin]
User=promethean
Session=plasma.desktop
Relogin=false
EOF
cat > /etc/profile.d/promethean.sh <<'EOF'
export HF_HOME=/data/models/huggingface
export HUGGINGFACE_HUB_CACHE=/data/models/huggingface
export OLLAMA_MODELS=/data/models/ollama
export XDG_CACHE_HOME=/data/models/cache
export PYTHONUNBUFFERED=1
EOF
# F44's KDE stack ships display-manager.service as a symlink to plasmalogin.service; systemctl enable sddm will not clobber an existing alias, so remove the symlink first and let `systemctl enable sddm` re-point it (run 34527416500 evidence)
rm -f /etc/systemd/system/display-manager.service
systemctl enable NetworkManager firewalld sddm promethean-api.service promethean-hardware-detect.service promethean-ollama.service
systemctl set-default graphical.target
%end