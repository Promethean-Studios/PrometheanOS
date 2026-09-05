# Fedora Kickstart for PrometheanOS V1
# Minimal Fedora KDE Plasma base tuned for local AI workloads.

url --mirrorlist="https://mirrors.fedoraproject.org/metalink" --proxy=""
repo --name=fedora --mirrorlist="https://mirrors.fedoraproject.org/metalink"
repo --name=updates --mirrorlist="https://mirrors.fedoraproject.org/metalink" --install

# Use standard Fedora install defaults
lang en_US.UTF-8
keyboard us
timezone UTC --utc

# Installation target and bootloader
zerombr
clearpart --all --initlabel
autopart --type=plain --fstype=xfs --nohome
bootloader --location=mbr --append="rhgb quiet"

# Network and authentication
network --bootproto=dhcp --device=link --activate
rootpw --lock
user --name=promethean --groups=wheel --password=promethean --plaintext

# Package selection
%packages
@core
@kde-desktop
@networkmanager-submodules
@printing
@base-x
@fonts
@gnome-software
@development-tools
git
gh
curl
wget
python3
python3-pip
python3-venv
podman
ollama
flatpak
firewalld
NetworkManager-wifi
xorg-x11-server-Xorg
nss-mdns
%end

# Configure default graphical session to use Wayland
# KDE defaults to X11 in some installers; this ensures Plasma runs under Wayland.
%post --log=/root/ks-post.log
mkdir -p /etc/sddm.conf.d
cat > /etc/sddm.conf.d/10-wayland.conf <<'EOF'
[General]
DisplayServer=wayland
EOF

# KDE session setup: prefer Wayland for user sessions when available.
mkdir -p /etc/profile.d
cat > /etc/profile.d/promethean-wayland.sh <<'EOF'
export XDG_SESSION_TYPE=wayland
export QT_QPA_PLATFORM=wayland
export GDK_BACKEND=wayland
EOF

# Ensure the default user has a working Plasma Wayland session.
mkdir -p /var/lib/AccountsService/users
cat > /var/lib/AccountsService/users/promethean <<'EOF'
[User]
Language=en_US.UTF-8
XSession=plasmawayland
EOF

# Install and enable required services
systemctl enable NetworkManager
systemctl enable firewalld
systemctl enable sddm
systemctl enable podman
systemctl enable ollama
%end

# Reboot after install
reboot
