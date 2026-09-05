# Fedora 40/41 Workstation-based PrometheanOS V1 kickstart
# Produces a Fedora Workstation install with the Promethean AI desktop baseline.

# Installation source
url --mirrorlist="https://mirrors.fedoraproject.org/metalink"
repo --name=fedora --mirrorlist="https://mirrors.fedoraproject.org/metalink"
repo --name=updates --mirrorlist="https://mirrors.fedoraproject.org/metalink"

# Localization
lang en_US.UTF-8
keyboard us
timezone UTC --utc

# Disk and boot
zerombr
clearpart --all --initlabel
autopart --type=lvm --fstype=xfs
bootloader --location=mbr --append="rhgb quiet"

# Network
network --bootproto=dhcp --device=link --activate

# Root lockout; create a standard user for daily operation
rootpw --lock
user --name=promethean --groups=wheel --password=promethean --plaintext

# Core packages: workstation + build tooling + AI/desktop prerequisites
%packages
@core
@workstation-product-environment
@standard
@development-tools
@networkmanager-submodules
@fonts
@multimedia
@admin-tools
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
nss-mdns
rpmfusion-free-release
rpmfusion-nonfree-release
nvidia-driver
nvidia-settings
cuda
cuda-toolkit
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

# NVIDIA and CUDA repositories: official NVIDIA RPM repo and negativo17 fallback.
cat > /etc/yum.repos.d/nvidia-official.repo <<'EOF'
[nvidia-official]
name=NVIDIA Official RPMs
baseurl=https://developer.download.nvidia.com/compute/cuda/repos/fedora$releasever/$basearch/
enabled=1
gpgcheck=1
gpgkey=https://developer.download.nvidia.com/compute/cuda/repos/fedora$releasever/$basearch/D42D0685.pub
EOF

cat > /etc/yum.repos.d/negativo17-fedora-nvidia.repo <<'EOF'
[negativo17-fedora-nvidia]
name=Negativo17 - Fedora NVIDIA driver repository
baseurl=https://negativo17.org/repos/fedora-nvidia.repo/fedora-$releasever/$basearch/
enabled=1
skip_if_unavailable=1
gpgcheck=1
gpgkey=https://negativo17.org/RPM-GPG-KEY-negativo17
EOF

# Passwordless sudo for the default non-root user
printf '%s\n' 'promethean ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/promethean
chmod 0440 /etc/sudoers.d/promethean

# Default to Wayland for Workstation sessions
mkdir -p /etc/profile.d
cat > /etc/profile.d/promethean-wayland.sh <<'EOF'
export XDG_SESSION_TYPE=wayland
export QT_QPA_PLATFORM=wayland
export GDK_BACKEND=wayland
EOF

# Enable standard services
systemctl enable NetworkManager
systemctl enable firewalld
systemctl enable sshd
systemctl enable podman
%end

# Finalize installation
reboot
