#!/usr/bin/env bash
# First-time VPS bootstrap — Ubuntu 22.04/24.04
# Run as root: curl -fsSL ... | bash   OR   bash deploy/vps-bootstrap.sh
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Run as root: sudo bash deploy/vps-bootstrap.sh"
  exit 1
fi

apt-get update
apt-get install -y ca-certificates curl git ufw

# Docker Engine
if ! command -v docker &>/dev/null; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
    $(. /etc/os-release && echo "${VERSION_CODENAME:-$VERSION_ID}") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
fi

systemctl enable docker
systemctl start docker

# Firewall — SSH + HTTP/S only
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo ""
echo "VPS ready. Next steps:"
echo "  1. Clone repo:  git clone <your-repo-url> /opt/scalp-desk && cd /opt/scalp-desk"
echo "  2. Configure:   cp .env.production.example .env && nano .env"
echo "  3. Deploy:      bash deploy/deploy.sh"
echo "  4. DNS A record: scalping.optionperks.com -> $(curl -4 -s ifconfig.me 2>/dev/null || echo 'YOUR_VPS_IP')"
