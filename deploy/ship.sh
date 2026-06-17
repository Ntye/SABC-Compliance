#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
# SABC Compliance Platform — EC2 Deployment Script
# ═══════════════════════════════════════════════════════════════════════════════
#
# Usage:
#   ./deploy/ship.sh user@ec2-ip                Build, transfer, and deploy
#   ./deploy/ship.sh user@ec2-ip --setup        First time: install Docker + deploy
#   ./deploy/ship.sh user@ec2-ip --update       Transfer and restart (skip build)
#   ./deploy/ship.sh user@ec2-ip --deploy-only  Load + restart only (skip build & transfer)
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
DEPLOY_ONLY=false
BUILD_ONLY=false
BUNDLE=false

for arg in "$@"; do
  case "$arg" in
    --setup)       DO_SETUP=true ;;
    --update)      DO_UPDATE=true ;;
    --deploy-only) DEPLOY_ONLY=true ;;
    --build-only)  BUILD_ONLY=true ;;
    --bundle)      BUNDLE=true ;;
    -*)            echo "Unknown flag: $arg"; exit 1 ;;
    *)             TARGET="$arg" ;;
  esac
done

if [[ -z "$TARGET" && "$BUILD_ONLY" == false && "$BUNDLE" == false ]]; then
  echo "Usage: ./deploy/ship.sh user@ec2-ip [--setup|--update|--deploy-only|--build-only|--bundle]"
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
HTTPS_PORT=8443
BACKEND_PORT=3000
# Set to the EC2 private IP so the bootstrap curl command works
# HOST_IP=10.0.x.x
ENV_EOF
  fi

  # Create packages directory (bind mount target)
  remote "sudo mkdir -p $REMOTE_DIR/backend/packages && sudo chown -R \$(whoami):\$(whoami) $REMOTE_DIR"

  # Auto-detect the server's public IP and write PLATFORM_PUBLIC_HOST into the
  # remote .env so docker compose picks it up automatically — no manual editing
  # required. Only writes/updates the value when it is currently unset; an
  # existing non-empty value (e.g. a domain name) is always left untouched.
  info "Auto-detecting server public IP for PLATFORM_PUBLIC_HOST ..."
  remote "bash -s -- '$REMOTE_DIR'" << 'PUBIP_EOF'
rd="$1"
ip=""
# IMDSv2 (preferred on instances with metadata token enforcement)
token=$(curl -sf --connect-timeout 2 -X PUT \
    "http://169.254.169.254/latest/api/token" \
    -H "X-aws-ec2-metadata-token-ttl-seconds: 10" 2>/dev/null || true)
if [ -n "$token" ]; then
    ip=$(curl -sf --connect-timeout 2 \
        -H "X-aws-ec2-metadata-token: $token" \
        "http://169.254.169.254/latest/meta-data/public-ipv4" 2>/dev/null || true)
fi
# IMDSv1 fallback
if [ -z "$ip" ]; then
    ip=$(curl -sf --connect-timeout 2 \
        "http://169.254.169.254/latest/meta-data/public-ipv4" 2>/dev/null || true)
fi
# hostname -I fallback (non-EC2 hosts)
if [ -z "$ip" ]; then
    ip=$(hostname -I 2>/dev/null | awk '{print $1}' || true)
fi
envfile="$rd/.env"
if [ -n "$ip" ]; then
    existing=$(grep "^PLATFORM_PUBLIC_HOST=" "$envfile" 2>/dev/null | cut -d= -f2 | head -1 | tr -d '[:space:]')
    if [ -z "$existing" ]; then
        if grep -q "^PLATFORM_PUBLIC_HOST=" "$envfile" 2>/dev/null; then
            sed -i "s|^PLATFORM_PUBLIC_HOST=.*|PLATFORM_PUBLIC_HOST=$ip|" "$envfile"
        else
            printf '\nPLATFORM_PUBLIC_HOST=%s\n' "$ip" >> "$envfile"
        fi
        echo "[ship.sh] PLATFORM_PUBLIC_HOST=$ip → $envfile"
    else
        echo "[ship.sh] PLATFORM_PUBLIC_HOST already set to '$existing' — leaving it unchanged"
    fi
else
    echo "[ship.sh] Warning: could not detect public IP — PLATFORM_PUBLIC_HOST not set"
fi
PUBIP_EOF

  ok "Files transferred"
}

# ── Step 5: Load images and start ────────────────────────────────────────────
deploy() {
  info "Loading Docker images on $TARGET ..."
  remote_docker "docker load -i $REMOTE_DIR/sabc-images.tar.gz"

  info "Starting platform ..."
  # Tear down any previous stack first. "down" only clears THIS compose
  # project, so we also force-remove our own fixed-name containers (reliable
  # because docker-compose.yml pins container_name) to free their published
  # ports from a stale sabc-frontend/sabc-backend left by an earlier run.
  # Only our named containers are touched — never any other app's container.
  #
  # Use "sudo bash -s" with a heredoc so sudo covers ALL three commands:
  # "sudo <compound>" only elevates up to the first semicolon; subsequent
  # commands in the same string revert to the unprivileged user.
  ssh -o StrictHostKeyChecking=no "$TARGET" "sudo bash -s" << DEPLOY_EOF
docker compose -f $REMOTE_DIR/docker-compose.yml --project-directory $REMOTE_DIR down --remove-orphans 2>/dev/null || true
docker rm -f sabc-frontend sabc-backend 2>/dev/null || true
docker compose -f $REMOTE_DIR/docker-compose.yml --project-directory $REMOTE_DIR up -d
DEPLOY_EOF

  ok "Platform deployed!"

  # Everything below is purely informational (URL banner). It must NEVER abort
  # the script — under `set -euo pipefail` a no-match grep or a failed IP probe
  # returns non-zero and would otherwise kill the run right before the URL is
  # printed. Disable errexit for the remainder of the function (deploy() is the
  # last thing the script does, so this never masks a later failure).
  set +e

  echo ""
  echo "══════════════════════════════════════════════════════"
  echo "  SABC Compliance Platform is running on:"
  echo ""

  # Detect the public IP of the EC2 instance.
  # Modern EC2 instances require IMDSv2 (token-based); a plain IMDSv1 curl
  # returns a 401 with an empty body which leaves pub_ip blank.
  local pub_ip
  pub_ip=$(remote 'bash -s' << 'IPEOF' 2>/dev/null
set -e
ip=""
# 1) IMDSv2 — get a short-lived token, then request the public IPv4
token=$(curl -sf --connect-timeout 2 -X PUT \
  "http://169.254.169.254/latest/api/token" \
  -H "X-aws-ec2-metadata-token-ttl-seconds: 10" 2>/dev/null || true)
if [ -n "$token" ]; then
  ip=$(curl -sf --connect-timeout 2 \
    -H "X-aws-ec2-metadata-token: $token" \
    "http://169.254.169.254/latest/meta-data/public-ipv4" 2>/dev/null || true)
fi
# 2) IMDSv1 fallback
if [ -z "$ip" ]; then
  ip=$(curl -sf --connect-timeout 2 \
    "http://169.254.169.254/latest/meta-data/public-ipv4" 2>/dev/null || true)
fi
# 3) hostname fallback
if [ -z "$ip" ]; then
  ip=$(hostname -I 2>/dev/null | awk '{print $1}')
fi
printf "%s" "$ip"
IPEOF
  ) || pub_ip=""

  # Strip stray whitespace/newlines from the captured output
  pub_ip=$(printf "%s" "${pub_ip}" | tr -d '[:space:]')

  # Final fallback: extract the host from the SSH target (user@host → host)
  if [ -z "$pub_ip" ]; then
    pub_ip="${TARGET#*@}"
  fi

  # Published HTTPS host port (defaults to 8443; read from local .env if set).
  local https_port="8443"
  if [ -f "$PROJECT_DIR/.env" ]; then
    local p
    p=$(grep -E '^HTTPS_PORT=' "$PROJECT_DIR/.env" | head -1 | cut -d= -f2 | tr -d '[:space:]' || true)
    [ -n "$p" ] && https_port="$p"
  fi

  echo "  UI:      https://${pub_ip}:${https_port}"
  echo "  API:     https://${pub_ip}:${https_port}/api"
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

if [[ "$DEPLOY_ONLY" == true ]]; then
  # Files already on the remote — skip build AND transfer, just load + restart.
  # Verify the archive and compose file are actually present remotely first so
  # we fail with a clear message instead of a confusing docker error.
  if ! remote "test -f $REMOTE_DIR/sabc-images.tar.gz && test -f $REMOTE_DIR/docker-compose.yml"; then
    fail "Remote files missing in $REMOTE_DIR (need sabc-images.tar.gz + docker-compose.yml) — run --update first to transfer them"
  fi
  deploy
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
