# First testable PrometheanOS Fedora KDE live image.
# This file is consumed by livemedia-creator --make-iso (virt install). It
# initializes lmc's disposable installer-VM disk (zerombr + clearpart --all,
# plus a 1MiB biosboot partition for BIOS boot from the resulting GPT label)
# and contains no bootloader, autopart, or reboot directives.

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
# 16384 MiB: anaconda requires the transaction to fit the / filesystem; run 34653122316 failed with "needs ~1477MB more space on the / filesystem" at 12288 because the network metalink payload (updates-released included) needs ~13.5 GB, up from ~8.9 GB at the release cut (run 34403642413). The ISO payload is squashfs-compressed, so this only affects build-time disk on a sparse image.
# The virt install runs anaconda against a blank virtual disk (auto-sized to
# 12290 MiB from the part line below). Without a disk-init directive anaconda
# refuses to initialize it (disk_initialization.can_initialize: "The disk
# cannot be initialized." unless format_unrecognized is set by clearpart/
# zerombr), so blivet's do_partitioning sees disks=[] (it only considers
# storage.partitioned, i.e. disks that already carry a disklabel) and fails
# with PartitioningError "Unable to allocate requested partition scheme"
# (run 34647960864). zerombr + clearpart --all is exactly what lorax's own
# docs prescribe for lmc kickstarts (docs/livemedia-creator.rst). Both act
# only on the throwaway VM disk; the final ISO is composed from the
# installed tree's squashfs, so nothing in the image changes.
zerombr
clearpart --all
part / --size=16384
# run 34649815500: anaconda initializes the blank lmc virt disk as GPT; the installer VM boots BIOS/SeaBIOS, and BIOS boot from GPT requires a 1MiB biosboot partition (verify_gpt_biosboot sanity check failed: "Your BIOS-based system needs a special partition to boot from a GPT disk label"). This partition exists only on the throwaway installer-VM disk; the ISO is composed from the installed tree's squashfs, so ISO content is unchanged.
part biosboot --fstype=biosboot --size=1
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
# Repo payload delivery into the installer VM's runtime:
# 1. lmc injects extra --ks files into the install initrd, but initrd-root
#    files do NOT survive dracut's switch_root into the stage2 runtime
#    (run 34655074847: /payload.tar.gz absent at %post). Local candidates
#    are kept as opportunistic fast paths in case injected files land in
#    /run/install.
# 2. A /workspace bind mount exists only in container-direct builds (retired).
# 3. Guaranteed channel: build.sh serves the temp result root on 127.0.0.1:8099
#    while lmc runs; the VM reaches it via qemu user networking at 10.0.2.2
#    (fixed slirp gateway, confirmed in the run's qemu cmdline). The anaconda
#    runtime ships curl (lorax runtime-install.tmpl) and the NIC is up - the
#    package transaction itself resolved from the network metalink.
ls -la / /run/install/ 2>/dev/null || true
payload=""
if [[ -s /payload.tar.gz ]]; then
    payload=/payload.tar.gz
elif [[ -s /run/install/payload.tar.gz ]]; then
    payload=/run/install/payload.tar.gz
elif [[ -d /workspace ]]; then
    cp -a /workspace/. /mnt/sysimage/srv/promethean/
else
    curl -fsSL --retry 5 --retry-delay 2 --connect-timeout 5 \
        -o /tmp/promethean-payload.tar.gz http://10.0.2.2:8099/payload.tar.gz \
        || { echo "FATAL: payload fetch from build host (10.0.2.2:8099) failed" >&2; exit 1; }
    payload=/tmp/promethean-payload.tar.gz
fi
if [[ -n "$payload" ]]; then
    tar -xzf "$payload" -C /mnt/sysimage/srv/promethean/
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