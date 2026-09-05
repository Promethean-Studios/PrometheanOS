# Fedora 40/41 KDE Plasma kickstart for PrometheanOS V1
# This image is intended for a disposable VM or a dedicated target disk
# chosen by the user during a real installation. It is not a host-destructive
# automation script and should not be used against an arbitrary local disk.

# Installation source
url --mirrorlist="https://mirrors.fedoraproject.org/metalink"
repo --name=fedora --mirrorlist="https://mirrors.fedoraproject.org/metalink"
repo --name=updates --mirrorlist="https://mirrors.fedoraproject.org/metalink"

# Localization
lang en_US.UTF-8
keyboard us
timezone UTC --utc

# Disk and boot
# These commands are intentionally kept for the installer stage only; the
# containerized build workflow in build.sh never writes to the host disk.
zerombr
clearpart --all --initlabel
autopart --type=lvm --fstype=xfs
bootloader --location=mbr --append="rhgb quiet"

# Network
network --bootproto=dhcp --device=link --activate

# Root locked by default; create a non-root user that must authenticate for sudo.
rootpw --lock
user --name=promethean --groups=wheel --lock --shell=/bin/bash

# KDE Plasma base + AI/development tools. No NVIDIA/CUDA packages are mandatory.
%packages
@core
@kde-desktop-environment
@kde-apps
@networkmanager-submodules
@fonts
@printing
@base-x
@development-tools
sudo
git
gh
curl
wget
gcc
g++
clang
cmake
make
ninja-build
pkgconf-pkg-config
python3
python3-devel
python3-pip
python3-virtualenv
kernel-devel
kernel-headers
dkms
podman
flatpak
firewalld
NetworkManager-wifi
pipewire
pipewire-alsa
pipewire-pulseaudio
wireplumber
nss-mdns
rpmfusion-free-release
rpmfusion-nonfree-release
%end

# Post-install configuration
%post --log=/root/ks-post.log --erroronfail
# RPM Fusion repos are enabled explicitly for the installed system.
cat > /etc/yum.repos.d/rpmfusion-free.repo <<'EOF'
[rpmfusion-free]
name=RPM Fusion for Fedora $releasever - Free
baseurl=https://download1.rpmfusion.org/free/fedora/releases/$releasever/Everything/$basearch/os/
enabled=1
metadata_expire=7d
gpgcheck=1
gpgkey=https://download1.rpmfusion.org/RPM-GPG-KEY-rpmfusion-free-fedora-$releasever

[rpmfusion-free-debuginfo]
name=RPM Fusion for Fedora $releasever - Free - Debug
baseurl=https://download1.rpmfusion.org/free/fedora/releases/$releasever/Everything/$basearch/debug/
enabled=0
metadata_expire=7d
gpgcheck=1
gpgkey=https://download1.rpmfusion.org/RPM-GPG-KEY-rpmfusion-free-fedora-$releasever
EOF

cat > /etc/yum.repos.d/rpmfusion-nonfree.repo <<'EOF'
[rpmfusion-nonfree]
name=RPM Fusion for Fedora $releasever - Nonfree
baseurl=https://download1.rpmfusion.org/nonfree/fedora/releases/$releasever/Everything/$basearch/os/
enabled=1
metadata_expire=7d
gpgcheck=1
gpgkey=https://download1.rpmfusion.org/RPM-GPG-KEY-rpmfusion-nonfree-fedora-$releasever

[rpmfusion-nonfree-debuginfo]
name=RPM Fusion for Fedora $releasever - Nonfree - Debug
baseurl=https://download1.rpmfusion.org/nonfree/fedora/releases/$releasever/Everything/$basearch/debug/
enabled=0
metadata_expire=7d
gpgcheck=1
gpgkey=https://download1.rpmfusion.org/RPM-GPG-KEY-rpmfusion-nonfree-fedora-$releasever
EOF

# Explicit NVIDIA/CUDA repo definitions are optional and disabled by default.
# Vendor-specific driver setup is handled by the Promethean hardware detection
# flow after an actual GPU is detected on the target machine.
cat > /etc/yum.repos.d/promethean-vendor-gpu.optional <<'EOF'
# NVIDIA / CUDA repo definitions can be added here only when a target machine
# has a supported NVIDIA GPU and the operator chooses to install the proprietary
# stack. They are intentionally not enabled in the base image.
EOF

# Allow the standard wheel group to use sudo using a password challenge.
# This keeps administrative access available to the human operator without
# shipping a known default password or granting unrestricted NOPASSWD access.
printf '%s\n' '%wheel ALL=(ALL) ALL' > /etc/sudoers.d/10-promethean-wheel
chmod 0440 /etc/sudoers.d/10-promethean-wheel

# KDE Plasma should default to Wayland and SDDM.
mkdir -p /etc/sddm.conf.d /etc/profile.d
cat > /etc/sddm.conf.d/10-wayland.conf <<'EOF'
[General]
DisplayServer=wayland
EOF

cat > /etc/profile.d/promethean-wayland.sh <<'EOF'
export XDG_SESSION_TYPE=wayland
export QT_QPA_PLATFORM=wayland
export GDK_BACKEND=wayland
EOF

# Standard services for the KDE desktop environment.
systemctl enable NetworkManager
systemctl enable firewalld
systemctl enable sddm
systemctl enable sshd
systemctl enable podman
systemctl set-default graphical.target
%end

# Finalize installation.
reboot
