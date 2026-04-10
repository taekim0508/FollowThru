#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# deploy/setup.sh
# One-time bootstrap for a fresh Amazon Linux 2023 / Ubuntu 22.04 EC2 instance.
# Run as: bash setup.sh
# -----------------------------------------------------------------------------
set -euo pipefail

APP_USER="followthru"
APP_DIR="/opt/followthru"
REPO_URL="https://github.com/YOUR_ORG/YOUR_REPO.git"   # <-- update this

echo "==> Installing system packages"
if command -v dnf &>/dev/null; then
  # Amazon Linux 2023
  sudo dnf update -y
  sudo dnf install -y python3.11 python3.11-pip python3.11-devel git nginx
else
  # Ubuntu 22.04
  sudo apt-get update -y
  sudo apt-get install -y python3.11 python3.11-venv python3-pip git nginx
fi

echo "==> Creating app user"
if ! id "$APP_USER" &>/dev/null; then
  sudo useradd --system --shell /bin/bash --create-home "$APP_USER"
fi

echo "==> Cloning repository"
sudo mkdir -p "$APP_DIR"
sudo chown "$APP_USER:$APP_USER" "$APP_DIR"
sudo -u "$APP_USER" git clone "$REPO_URL" "$APP_DIR"

echo "==> Creating Python virtualenv and installing dependencies"
sudo -u "$APP_USER" python3.11 -m venv "$APP_DIR/.venv"
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

echo "==> Installing systemd service"
sudo cp "$APP_DIR/deploy/followthru.service" /etc/systemd/system/followthru.service
sudo systemctl daemon-reload
sudo systemctl enable followthru
sudo systemctl start followthru

echo "==> Configuring nginx"
sudo cp "$APP_DIR/deploy/nginx.conf" /etc/nginx/conf.d/followthru.conf
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl restart nginx

echo "==> Done! Service status:"
sudo systemctl status followthru --no-pager
