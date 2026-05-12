#!/usr/bin/env bash
# oracle_bootstrap.sh — provision an Oracle Cloud Always Free VM for EDE.
#
# Target shape: VM.Standard.A1.Flex (Ampere ARM)
#   - 4 OCPU / 24 GB RAM / 200 GB block storage (Always Free max)
#   - Ubuntu 22.04 LTS for ARM64
#
# Run on the VM (not your laptop) as the default `ubuntu` user, AFTER:
#   1) you provisioned the VM via Oracle console or `oci compute instance launch`
#   2) you opened ingress on 22/tcp from your IP and (optionally) 8000/tcp
#   3) you SSH'd in: `ssh -i ~/.ssh/id_ed25519 ubuntu@<public-ip>`
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/<user>/ede-platform/main/scripts/oracle_bootstrap.sh | bash
#   # or
#   bash scripts/oracle_bootstrap.sh

set -euo pipefail

GREEN=$(tput setaf 2 || true)
YELLOW=$(tput setaf 3 || true)
RED=$(tput setaf 1 || true)
RESET=$(tput sgr0 || true)

log()  { printf '%s[bootstrap]%s %s\n' "$GREEN"  "$RESET" "$*"; }
warn() { printf '%s[bootstrap]%s %s\n' "$YELLOW" "$RESET" "$*"; }
err()  { printf '%s[bootstrap]%s %s\n' "$RED"    "$RESET" "$*" >&2; }

require_ubuntu() {
  if ! grep -qi ubuntu /etc/os-release; then
    err "This script targets Ubuntu 22.04. Detected: $(. /etc/os-release && echo "$PRETTY_NAME")"
    exit 1
  fi
}

require_arm64() {
  local arch
  arch=$(uname -m)
  if [[ "$arch" != "aarch64" && "$arch" != "arm64" ]]; then
    warn "Expected aarch64 (Ampere). Detected: $arch — continuing but watch for image arch mismatch."
  fi
}

apt_update() {
  log "Updating apt cache and upgrading base system."
  sudo DEBIAN_FRONTEND=noninteractive apt-get update -y
  sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -y
}

install_base_packages() {
  log "Installing base packages."
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    ca-certificates \
    curl \
    git \
    gnupg \
    htop \
    jq \
    lsb-release \
    ufw \
    unzip
}

install_docker() {
  if command -v docker >/dev/null 2>&1; then
    log "Docker already installed: $(docker --version)"
    return
  fi
  log "Installing Docker Engine + compose plugin."
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  sudo chmod a+r /etc/apt/keyrings/docker.gpg

  local codename
  codename=$(. /etc/os-release && echo "$VERSION_CODENAME")
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
     https://download.docker.com/linux/ubuntu $codename stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null

  sudo apt-get update -y
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

  sudo usermod -aG docker "$USER"
  sudo systemctl enable --now docker
}

configure_ufw() {
  log "Configuring ufw (allow 22, 8000; deny everything else inbound)."
  sudo ufw --force reset
  sudo ufw default deny incoming
  sudo ufw default allow outgoing
  sudo ufw allow 22/tcp
  sudo ufw allow 8000/tcp
  sudo ufw --force enable
}

configure_fail2ban() {
  log "Installing fail2ban for SSH brute-force protection."
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y fail2ban
  sudo systemctl enable --now fail2ban
}

configure_unattended_upgrades() {
  log "Enabling unattended security upgrades."
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y unattended-upgrades
  echo 'APT::Periodic::Update-Package-Lists "1";' \
    | sudo tee /etc/apt/apt.conf.d/20auto-upgrades
  echo 'APT::Periodic::Unattended-Upgrade "1";' \
    | sudo tee -a /etc/apt/apt.conf.d/20auto-upgrades
}

install_keep_alive_cron() {
  log "Installing Oracle anti-reclaim healthcheck cron (every 6h)."
  local repo_root
  repo_root="$(cd "$(dirname "$0")/.." && pwd)"
  ( crontab -l 2>/dev/null | grep -v 'ede_keep_alive' ; \
    echo "0 */6 * * * $repo_root/scripts/healthcheck_keep_alive.sh # ede_keep_alive" \
  ) | crontab -
}

clone_repo() {
  if [[ -d "$HOME/ede-platform/.git" ]]; then
    log "Repo already cloned at \$HOME/ede-platform."
    return
  fi
  warn "Clone the repo manually with your preferred method, e.g.:"
  warn "  git clone git@github.com:<user>/ede-platform.git \$HOME/ede-platform"
}

main() {
  require_ubuntu
  require_arm64
  apt_update
  install_base_packages
  install_docker
  configure_ufw
  configure_fail2ban
  configure_unattended_upgrades
  install_keep_alive_cron
  clone_repo
  log "Bootstrap complete."
  log "Next: log out and back in (or 'newgrp docker'), then:"
  log "  cd \$HOME/ede-platform && cp .env.example .env && docker compose up -d"
}

main "$@"
