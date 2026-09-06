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
user --name=promethean --groups=wheel --lock --shell=/bin/bash

%packages
@core
@^kde-desktop-environment
@kde-apps
@base-x
@fonts
@networkmanager-submodules
NetworkManager-wifi
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
%end

%post --nochroot --log=/mnt/sysimage/root/promethean-copy.log --erroronfail
set -eu
install -d -m 0755 /mnt/sysimage/srv/promethean
cp -a /workspace/. /mnt/sysimage/srv/promethean/
rm -rf /mnt/sysimage/srv/promethean/.git /mnt/sysimage/srv/promethean/.pytest_cache /mnt/sysimage/srv/promethean/__pycache__
%end

%post --log=/root/promethean-post.log --erroronfail
set -eu
install -d -m 0775 -o promethean -g promethean /data/models /data/models/ollama /data/models/huggingface /data/models/cache
install -d -m 0755 /usr/local/libexec/promethean /usr/share/promethean/desktop
install -m 0755 /srv/promethean/promethean-hardware-detect.sh /usr/local/libexec/promethean/hardware-detect.sh
cp -a /srv/promethean/desktop/. /usr/share/promethean/desktop/
install -m 0644 /srv/promethean/desktop/kde/promethean-control-center.desktop /usr/share/applications/promethean-control-center.desktop
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
Session=plasmawayland.desktop
Relogin=false
EOF
cat > /etc/profile.d/promethean.sh <<'EOF'
export HF_HOME=/data/models/huggingface
export HUGGINGFACE_HUB_CACHE=/data/models/huggingface
export OLLAMA_MODELS=/data/models/ollama
export XDG_CACHE_HOME=/data/models/cache
export PYTHONUNBUFFERED=1
EOF
systemctl enable NetworkManager firewalld sddm promethean-api.service promethean-hardware-detect.service promethean-ollama.service
systemctl set-default graphical.target
%end