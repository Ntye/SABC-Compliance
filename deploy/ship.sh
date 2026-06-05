#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
# SABC Compliance Platform — EC2 Deployment Script
# ═══════════════════════════════════════════════════════════════════════════════
#
# Usage:
#   ./deploy/ship.sh user@ec2-ip                Build, transfer, and deploy
#   ./deploy/ship.sh user@ec2-ip --setup        First time: install Docker + deploy
#   ./deploy/ship.sh user@ec2-ip --update       Transfer and restart (skip build)
#   ./deploy/ship.sh --build-only               Build and save images locally
#   ./deploy/ship.sh --bundle                   Build bundled image (with airgap packages)
#
# What it does:
#   1. Builds Docker images on your local machine
#   2. Saves them to deploy/sabc-images.tar.gz (~200MB compressed)
#   3. Transfers the archive + compose file + .env to the EC2 instance
#   4. Loads images and starts the platform with docker compose
#
# Prerequisites:
#   - Docker + Docker Compose on your local machine
#   - SSH access to the EC2 instance (key-based recommended)
#   - EC2 security group: inbound port 80 (HTTP), port 22 (SSH)
#
# ═══════════════════════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ARCHIVE="$SCRIPT_DIR/sabc-images.tar.gz"
REMOTE_DIR="/opt/sabc-compliance"

# ── Parse arguments ──────────────────────────────────────────────────────────
TARGET=""
DO_SETUP=false
DO_UPDATE=false
BUILD_ONLY=false
BUNDLE=false

for arg in "$@"; do
  case "$arg" in
    --setup)     DO_SETUP=true ;;
    --update)    DO_UPDATE=true ;;
    --build-only) BUILD_ONLY=true ;;
    --bundle)    BUNDLE=true ;;
    -*)          echo "Unknown flag: $arg"; exit 1 ;;
    *)           TARGET="$arg" ;;
  esac
done

if [[ -z "$TARGET" && "$BUILD_ONLY" == false && "$BUNDLE" == false ]]; then
  echo "Usage: ./deploy/ship.sh user@ec2-ip [--setup|--update|--build-only|--bundle]"
  exit 1
fi

# ── Helpers ──────────────────────────────────────────────────────────────────
info()  { echo -e "\033[1;34m▸\033[0m $*"; }
ok()    { echo -e "\033[1;32m✓\033[0m $*"; }
fail()  { echo -e "\033[1;31m✗\033[0m $*"; exit 1; }

remote() {
  ssh -o StrictHostKeyChecking=no "$TARGET" "$@"
}

# docker on the remote may require sudo (user not yet in docker group)
remote_docker() {
  ssh -o StrictHostKeyChecking=no "$TARGET" "sudo $*"
}

# ── Step 1: Build images ────────────────────────────────────────────────────
build_images() {
  info "Building Docker images for linux/amd64 ..."
  cd "$PROJECT_DIR"
  DOCKER_DEFAULT_PLATFORM=linux/amd64 docker compose build

  if [[ "$BUNDLE" == true ]]; then
    info "Building bundled image (with airgap packages) ..."
    DOCKER_DEFAULT_PLATFORM=linux/amd64 docker build \
      -f backend/Dockerfile.bundle -t sabc-compliance-backend:bundled backend/
  fi

  ok "Images built (linux/amd64)"
}

# ── Step 2: Save images to archive ──────────────────────────────────────────
save_images() {
  info "Saving images to $ARCHIVE ..."

  local images="sabc-compliance-backend:latest sabc-compliance-frontend:latest"
  if [[ "$BUNDLE" == true ]]; then
    images="sabc-compliance-backend:bundled sabc-compliance-frontend:latest"
  fi

  docker save $images | gzip > "$ARCHIVE"

  local size
  size=$(du -h "$ARCHIVE" | cut -f1)
  ok "Archive ready: $ARCHIVE ($size)"
}

# ── Step 3: Install Docker on EC2 (first time only) ─────────────────────────
setup_ec2() {
  info "Installing Docker on $TARGET ..."
  remote "sudo bash -s" << 'SETUP_EOF'
set -e

if command -v docker &>/dev/null && command -v docker compose &>/dev/null; then
  echo "Docker already installed: $(docker --version)"
  echo "Compose: $(docker compose version)"
  exit 0
fi

echo "Installing Docker ..."

# Detect OS
if [ -f /etc/os-release ]; then
  . /etc/os-release
  OS=$ID
else
  echo "Cannot detect OS" && exit 1
fi

case "$OS" in
  ubuntu|debian)
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq ca-certificates curl gnupg lsb-release
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL "https://download.docker.com/linux/$OS/gpg" | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
      https://download.docker.com/linux/$OS $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
    ;;
  amzn|rhel|centos|fedora)
    yum install -y docker
    systemctl enable docker
    systemctl start docker
    # Install compose plugin
    COMPOSE_VERSION=$(curl -sSL https://api.github.com/repos/docker/compose/releases/latest | grep tag_name | cut -d '"' -f4)
    mkdir -p /usr/local/lib/docker/cli-plugins
    curl -sSL "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" \
      -o /usr/local/lib/docker/cli-plugins/docker-compose
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
    ;;
  *)
    echo "Unsupported OS: $OS" && exit 1
    ;;
esac

systemctl enable docker
systemctl start docker

# Allow current user to use docker without sudo
if [ -n "${SUDO_USER:-}" ]; then
  usermod -aG docker "$SUDO_USER"
fi

echo "Docker installed: $(docker --version)"
echo "Compose: $(docker compose version)"
SETUP_EOF

  ok "Docker ready on $TARGET"
}

# ── Step 4: Transfer files to EC2 ───────────────────────────────────────────
transfer() {
  info "Creating remote directory $REMOTE_DIR ..."
  remote "sudo mkdir -p $REMOTE_DIR && sudo chown \$(whoami):\$(whoami) $REMOTE_DIR"

  info "Transferring images archive (this may take a few minutes) ..."
  scp -o StrictHostKeyChecking=no "$ARCHIVE" "$TARGET:$REMOTE_DIR/sabc-images.tar.gz"

  info "Transferring compose file and env ..."
  scp -o StrictHostKeyChecking=no "$PROJECT_DIR/docker-compose.yml" "$TARGET:$REMOTE_DIR/"

  # Transfer .env if it exists, otherwise create a default
  if [ -f "$PROJECT_DIR/.env" ]; then
    scp -o StrictHostKeyChecking=no "$PROJECT_DIR/.env" "$TARGET:$REMOTE_DIR/"
  else
    info "No .env found locally — creating default on EC2 ..."
    remote "cat > $REMOTE_DIR/.env" << 'ENV_EOF'
HTTP_PORT=80
BACKEND_PORT=3000
# Set to the EC2 private IP so the bootstrap curl command works
# HOST_IP=10.0.x.x
ENV_EOF
  fi

  # Create packages directory (bind mount target)
  remote "sudo mkdir -p $REMOTE_DIR/backend/packages && sudo chown -R \$(whoami):\$(whoami) $REMOTE_DIR"

  ok "Files transferred"
}

# ── Step 5: Load images and start ────────────────────────────────────────────
deploy() {
  info "Loading Docker images on $TARGET ..."
  remote_docker "docker load -i $REMOTE_DIR/sabc-images.tar.gz"

  info "Starting platform ..."
  remote_docker "docker compose -f $REMOTE_DIR/docker-compose.yml --project-directory $REMOTE_DIR up -d"

  ok "Platform deployed!"
  echo ""
  echo "══════════════════════════════════════════════════════"
  echo "  SABC Compliance Platform is running on:"
  echo ""

  # Try to get the public IP
  local pub_ip
  pub_ip=$(remote "curl -s --connect-timeout 3 http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || hostname -I | awk '{print \$1}'" 2>/dev/null || echo "<ec2-public-ip>")
  echo "  UI:      http://${pub_ip}"
  echo "  API:     http://${pub_ip}/api"
  echo "  Swagger: http://${pub_ip}:3000/docs"
  echo ""
  echo "  Logs:    ssh $TARGET 'cd $REMOTE_DIR && docker compose logs -f'"
  echo "  Stop:    ssh $TARGET 'cd $REMOTE_DIR && docker compose down'"
  echo "══════════════════════════════════════════════════════"
  echo ""
}

# ── Main ─────────────────────────────────────────────────────────────────────

if [[ "$BUILD_ONLY" == true || "$BUNDLE" == true ]]; then
  build_images
  save_images
  echo ""
  info "Archive at: $ARCHIVE"
  info "Transfer manually:  scp $ARCHIVE user@ec2-ip:$REMOTE_DIR/"
  exit 0
fi

if [[ "$DO_UPDATE" == true ]]; then
  # Skip build — just transfer existing archive and restart
  if [ ! -f "$ARCHIVE" ]; then
    fail "No archive found at $ARCHIVE — run without --update first, or run --build-only"
  fi
  transfer
  deploy
  exit 0
fi

# Full deploy
if [[ "$DO_SETUP" == true ]]; then
  setup_ec2
fi

build_images
save_images
transfer
deploy
