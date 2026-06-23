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
#   ./deploy/ship.sh user@ec2-ip --rollback     Roll back to the previous deployment
#   ./deploy/ship.sh --build-only               Build and save images locally
#   ./deploy/ship.sh --bundle                   Build bundled image (with airgap packages)
#
# What it does:
#   1. Builds Docker images on your local machine
#   2. Saves them to deploy/sabc-images.tar.gz (~200MB compressed)
#   3. Transfers the archive + compose file + .env to the EC2 instance
#   4. Loads images and starts the platform with docker compose
#   5. Auto-migrates a legacy SQLite database to PostgreSQL on first deploy
#      (runs once, before the backend boots; a marker file skips it thereafter)
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
DO_ROLLBACK=false

for arg in "$@"; do
  case "$arg" in
    --setup)       DO_SETUP=true ;;
    --update)      DO_UPDATE=true ;;
    --deploy-only) DEPLOY_ONLY=true ;;
    --build-only)  BUILD_ONLY=true ;;
    --bundle)      BUNDLE=true ;;
    --rollback)    DO_ROLLBACK=true ;;
    -*)            echo "Unknown flag: $arg"; exit 1 ;;
    *)             TARGET="$arg" ;;
  esac
done

if [[ -z "$TARGET" && "$BUILD_ONLY" == false && "$BUNDLE" == false ]]; then
  echo "Usage: ./deploy/ship.sh user@ec2-ip [--setup|--update|--deploy-only|--rollback|--build-only|--bundle]"
  exit 1
fi

# ── Helpers ──────────────────────────────────────────────────────────────────
info()  { echo -e "\033[1;34m▸\033[0m $*"; }
ok()    { echo -e "\033[1;32m✓\033[0m $*"; }
warn()  { echo -e "\033[1;33m⚠\033[0m $*"; }
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

  # Build directly — docker-compose.yml has no build: contexts (they belong
  # only in docker-compose.dev.yml for local dev), so we use docker build.
  # Use `docker buildx build --platform linux/amd64 --load` rather than
  # `DOCKER_DEFAULT_PLATFORM=… docker build` so the finished image is
  # explicitly loaded into the classic Docker daemon store that `docker save`
  # reads from.  Without --load, BuildKit on macOS stores layers only in its
  # own content store and docker save fails with "NotFound: content digest".
  docker buildx build --platform linux/amd64 --load \
    -t sabc-compliance-backend ./backend

  docker buildx build --platform linux/amd64 --load \
    --build-arg VITE_API_BASE=/api \
    -t sabc-compliance-frontend ./frontend

  if [[ "$BUNDLE" == true ]]; then
    info "Building bundled image (with airgap packages) ..."
    docker buildx build --platform linux/amd64 --load \
      -f backend/Dockerfile.bundle -t sabc-compliance-backend:bundled backend/
    # docker-compose.yml references sabc-compliance-backend:latest, so tag the
    # bundled image as :latest too — otherwise the loaded image never matches
    # the compose file and the backend fails to start with "image not found".
    docker tag sabc-compliance-backend:bundled sabc-compliance-backend:latest
  fi

  # postgres is not built from a Dockerfile — pull it for linux/amd64 so
  # it is included in the archive and never needs to be pulled on the server.
  # Remove the tag first: on macOS Docker Desktop the DOCKER_DEFAULT_PLATFORM
  # env var can leave a stale multi-arch manifest index tagged as :latest whose
  # layers are not fully present, causing `docker save` to fail with:
  #   unable to create manifests file: NotFound: content digest sha256:…
  # Using --platform directly writes a single-arch manifest that save handles
  # cleanly.
  info "Pulling postgres:16-alpine for linux/amd64 ..."
  docker image rm postgres:16-alpine 2>/dev/null || true
  docker pull --platform linux/amd64 postgres:16-alpine

  ok "Images built and pulled (linux/amd64)"
}

# ── Step 2: Save images to archive ──────────────────────────────────────────
save_images() {
  info "Saving images to $ARCHIVE ..."

  # postgres:16-alpine is included so the server never needs outbound Docker Hub
  # access — the image is loaded from the archive alongside backend and frontend.
  # Always save the :latest tag. For bundle builds the bundled image is also
  # tagged :latest in build_images, so the archive — and therefore the loaded
  # image — matches the compose file (which references :latest) in both modes.
  local images="sabc-compliance-backend:latest sabc-compliance-frontend:latest postgres:16-alpine"

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

if command -v docker &>/dev/null && docker compose version &>/dev/null 2>&1; then
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

# ── Step 5: Snapshot current deployment for rollback ────────────────────────
# Called before transferring new files so the previous compose, .env, and
# built images are preserved.  A no-op when nothing is deployed yet.
snapshot_for_rollback() {
  info "Snapshotting current deployment for rollback ..."
  ssh -o StrictHostKeyChecking=no "$TARGET" "sudo bash -s" << SNAP_EOF
set -e
rd="$REMOTE_DIR"
snapped=0
for img in sabc-compliance-backend:latest sabc-compliance-frontend:latest; do
  name="\${img%%:*}"
  if docker image inspect "\$img" >/dev/null 2>&1; then
    docker tag "\$img" "\${name}:rollback"
    echo "[snapshot] \$img → \${name}:rollback"
    snapped=\$((snapped + 1))
  fi
done
[ -f "\$rd/docker-compose.yml" ] && cp -f "\$rd/docker-compose.yml" "\$rd/docker-compose.yml.rollback"
[ -f "\$rd/.env" ]               && cp -f "\$rd/.env"               "\$rd/.env.rollback"
if [ "\$snapped" -gt 0 ]; then
  echo "[snapshot] Rollback snapshot ready (\${snapped} image(s) tagged)."
else
  echo "[snapshot] No previous images found — rollback will not be available after this deploy."
fi
SNAP_EOF
}

# ── Rollback to previous snapshot ───────────────────────────────────────────
# Restores :rollback images and the backed-up compose/.env, then restarts.
# Also exposed as --rollback for manual use after a bad deploy.
do_rollback() {
  warn "Rolling back to previous deployment ..."
  ssh -o StrictHostKeyChecking=no "$TARGET" "sudo bash -s" << ROLLBACK_EOF
set -e
rd="$REMOTE_DIR"

# Detect compose binary (v1 standalone vs v2 plugin)
if docker compose version >/dev/null 2>&1; then _bin="docker compose"; else _bin="docker-compose"; fi
COMPOSE="\$_bin -f \$rd/docker-compose.yml --project-directory \$rd"

# Stop the current (possibly broken) stack
\$COMPOSE down --remove-orphans 2>/dev/null || true
docker rm -f sabc-frontend sabc-backend sabc-postgres 2>/dev/null || true

# Restore backed-up compose and env
if [ -f "\$rd/docker-compose.yml.rollback" ]; then
  cp -f "\$rd/docker-compose.yml.rollback" "\$rd/docker-compose.yml"
  echo "[rollback] docker-compose.yml restored"
else
  echo "[rollback] WARNING: no docker-compose.yml.rollback — using current file"
fi
if [ -f "\$rd/.env.rollback" ]; then
  cp -f "\$rd/.env.rollback" "\$rd/.env"
  echo "[rollback] .env restored"
fi

# Promote :rollback images back to :latest
rolled=0
for name in sabc-compliance-backend sabc-compliance-frontend; do
  if docker image inspect "\${name}:rollback" >/dev/null 2>&1; then
    docker tag "\${name}:rollback" "\${name}:latest"
    echo "[rollback] Restored \${name}:latest from :rollback"
    rolled=\$((rolled + 1))
  fi
done

if [ "\$rolled" -eq 0 ]; then
  echo "[rollback] ERROR: no rollback images found — cannot restore previous version."
  exit 1
fi

\$COMPOSE up -d --no-build
echo "[rollback] Previous deployment successfully restored."
ROLLBACK_EOF

  ok "Rollback complete — previous version is running."
}

# ── Step 6: Load images and start ────────────────────────────────────────────
deploy() {
  info "Loading Docker images on $TARGET ..."
  if ! remote_docker "docker load -i $REMOTE_DIR/sabc-images.tar.gz"; then
    warn "Image load failed — initiating automatic rollback ..."
    do_rollback || true
    fail "Deployment failed during image load — automatically rolled back to previous version"
  fi

  info "Starting platform (PostgreSQL first, auto-migrating if needed) ..."
  # Tear down any previous stack first. "down" only clears THIS compose
  # project, so we also force-remove our own fixed-name containers (reliable
  # because docker-compose.yml pins container_name) to free their published
  # ports from a stale sabc-frontend/sabc-backend left by an earlier run.
  # Only our named containers are touched — never any other app's container.
  #
  # Use "sudo bash -s" with a heredoc so sudo covers EVERY command:
  # "sudo <compound>" only elevates up to the first semicolon; subsequent
  # commands in the same string revert to the unprivileged user.
  #
  # The start sequence brings PostgreSQL up on its own, runs the one-shot
  # SQLite → PostgreSQL migration BEFORE the backend boots (the backend seeds
  # default users/groups into an empty DB on first start, which would make the
  # idempotent migration skip those tables and strand the real SQLite data),
  # then starts the full stack. A marker file makes the migration a no-op on
  # every later deploy.  $REMOTE_DIR expands locally; \$ is evaluated remotely.
  # Disable errexit so we can capture the exit code and trigger rollback instead
  # of just aborting.  Re-enabled immediately after the heredoc.
  set +e
  ssh -o StrictHostKeyChecking=no "$TARGET" "sudo bash -s" << DEPLOY_EOF
set -e
if docker compose version >/dev/null 2>&1; then _bin="docker compose"; else _bin="docker-compose"; fi
COMPOSE="\$_bin -f $REMOTE_DIR/docker-compose.yml --project-directory $REMOTE_DIR"
COMPOSE_FILE="$REMOTE_DIR/docker-compose.yml"

# Guard: docker-compose v1 mis-handles image-only services when the file still
# declares build: contexts -- it silently skips them and STILL exits 0, so the
# deploy looks successful while only postgres actually starts. Abort early.
if grep -qE "^[[:space:]]*build:" "\$COMPOSE_FILE"; then
  echo "[ship.sh] FATAL: \$COMPOSE_FILE still contains build: directives."
  echo "[ship.sh] This server runs docker-compose v1, which cannot start the"
  echo "[ship.sh] pre-built image services from a file that has build: contexts."
  echo "[ship.sh] Re-run with --update so the corrected docker-compose.yml is"
  echo "[ship.sh] transferred to the server."
  exit 2
fi

\$COMPOSE down --remove-orphans 2>/dev/null || true
docker rm -f sabc-frontend sabc-backend sabc-postgres 2>/dev/null || true

# 1) Bring the WHOLE stack up in one shot — the exact single "up -d" the proven
#    manual deploy uses. Compose honours depends_on ordering (postgres →
#    backend → frontend). We deliberately drop the old "compose run --rm"
#    migration step: that ephemeral-container subcommand is the part that
#    misbehaves on docker-compose v1 and forced the manual fallback.
\$COMPOSE up -d

# 2) Wait for PostgreSQL to report healthy so the migration below can connect.
echo "[ship.sh] Waiting for PostgreSQL to become healthy ..."
for i in \$(seq 1 30); do
  s=\$(docker inspect -f '{{.State.Health.Status}}' sabc-postgres 2>/dev/null || echo starting)
  [ "\$s" = "healthy" ] && break
  sleep 2
done

# 3) One-shot SQLite → PostgreSQL migration, run as a follow-up against the
#    already-running backend via "docker exec" — reliable on every compose
#    version, unlike "compose run --rm". Marker-guarded so it runs at most once,
#    and non-fatal so a hiccup never blocks the deploy. The migration script
#    skips any table that already has rows, so it can never overwrite data.
#    NOTE: because the backend boots (and seeds default groups/profiles/admin
#    into an empty PostgreSQL) before this runs, a genuine SQLite→PostgreSQL
#    *upgrade* would find those tables already populated and skip them. That
#    matters only when importing a legacy SQLite database; fresh installs and
#    already-migrated servers are unaffected.
docker exec sabc-backend sh -c '
  if [ -f /app/data/.migrated-to-postgres ]; then
    echo "[ship.sh] Database already migrated to PostgreSQL — skipping."
  elif [ -f /app/data/platform.db ]; then
    echo "[ship.sh] Existing SQLite database found — migrating to PostgreSQL ..."
    python /app/migrate_to_postgres.py && touch /app/data/.migrated-to-postgres
  else
    echo "[ship.sh] Fresh install (no SQLite database) — no migration needed."
    touch /app/data/.migrated-to-postgres
  fi
' 2>&1 || echo "[ship.sh] Migration step skipped (non-fatal) — continuing."

# 4) Wait 15 s — same window the working manual script uses — so containers
#    that need a few seconds to transition from "created" to "running" are
#    already stable before we inspect them.
echo "=== Waiting 15s ==="
sleep 15

echo "=== Container status ==="
docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Image}}"

# 5) Verify the stack is REALLY up.  docker-compose v1 can return 0 without
#    creating a service, so check real container state, not the exit code.
missing=""
for c in sabc-postgres sabc-backend sabc-frontend; do
  st=\$(docker inspect -f '{{.State.Status}}' "\$c" 2>/dev/null || echo absent)
  [ "\$st" = "running" ] || missing="\$missing \$c"
done
if [ -n "\$missing" ]; then
  echo "[ship.sh] ERROR: these containers are not running:\$missing"
  docker ps -a
  for c in \$missing; do
    echo "[ship.sh] ---------- last 40 log lines: \$c ----------"
    docker logs --tail 40 "\$c" 2>&1 || echo "[ship.sh] (container \$c was never created)"
  done
  exit 1
fi
echo "[ship.sh] All containers running: postgres, backend, frontend."
DEPLOY_EOF
  _deploy_rc=$?
  set -e

  if [[ $_deploy_rc -ne 0 ]]; then
    warn "Deploy sequence failed (exit $_deploy_rc) — initiating automatic rollback ..."
    do_rollback || true
    fail "Deployment failed — automatically rolled back to previous version"
  fi

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
  echo "  Status:  ssh $TARGET sudo docker ps"
  echo "  Logs:    ssh $TARGET sudo docker logs -f sabc-backend   (or sabc-frontend)"
  echo "  Stop:    ssh $TARGET 'cd $REMOTE_DIR && docker compose down'"
  echo "  Note:    'docker-compose logs -f' may print a harmless KeyError: 'id' on v1;"
  echo "           per-container 'docker logs' above avoids it."
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

if [[ "$DO_ROLLBACK" == true ]]; then
  do_rollback
  exit 0
fi

if [[ "$DEPLOY_ONLY" == true ]]; then
  # Files already on the remote — skip build AND transfer, just load + restart.
  # Verify the archive and compose file are actually present remotely first so
  # we fail with a clear message instead of a confusing docker error.
  if ! remote "test -f $REMOTE_DIR/sabc-images.tar.gz && test -f $REMOTE_DIR/docker-compose.yml"; then
    fail "Remote files missing in $REMOTE_DIR (need sabc-images.tar.gz + docker-compose.yml) — run --update first to transfer them"
  fi
  snapshot_for_rollback
  deploy
  exit 0
fi

if [[ "$DO_UPDATE" == true ]]; then
  # Skip build — just transfer existing archive and restart
  if [ ! -f "$ARCHIVE" ]; then
    fail "No archive found at $ARCHIVE — run without --update first, or run --build-only"
  fi
  snapshot_for_rollback
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
snapshot_for_rollback
transfer
deploy
