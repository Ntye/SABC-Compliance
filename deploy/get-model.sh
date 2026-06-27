#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# SABC Compliance — Ollama model downloader
# ─────────────────────────────────────────────────────────────────────────────
#
# Run this script on any machine with Docker and internet access to download
# an Ollama model and pack it into a tar archive that can be transferred to
# the airgap server later.  The server itself needs no internet at all.
#
# Usage:
#   ./deploy/get-model.sh                          # llama3.2:3b → deploy/ollama-models.tar.gz
#   ./deploy/get-model.sh llama3.2:3b              # larger / better model
#   ./deploy/get-model.sh llama3.2:3b /tmp/ai.tar.gz  # custom output path
#
# After running, deploy the model to the server with:
#   ./deploy/ship.sh user@server --ai-models=./deploy/ollama-models.tar.gz
#
# Or transfer and load manually (useful for updates):
#   scp deploy/ollama-models.tar.gz user@server:/opt/sabc-compliance/
#   ssh user@server "sudo bash -s" <<'EOF'
#     docker volume create sabc-ollama-models
#     docker run --rm \
#       -v sabc-ollama-models:/dest \
#       -v /opt/sabc-compliance/ollama-models.tar.gz:/src/m.tar.gz \
#       alpine tar -xzf /src/m.tar.gz -C /dest
#   EOF
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

MODEL="${1:-llama3.2:3b}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT="${2:-$SCRIPT_DIR/ollama-models.tar.gz}"

info() { echo -e "\033[1;34m▸\033[0m $*"; }
ok()   { echo -e "\033[1;32m✓\033[0m $*"; }
fail() { echo -e "\033[1;31m✗\033[0m $*"; exit 1; }

command -v docker >/dev/null 2>&1 || fail "Docker is required but not found in PATH"

info "Pulling Ollama model '${MODEL}' (this may take several minutes) ..."

MODEL_DIR="$(mktemp -d)"
trap 'rm -rf "$MODEL_DIR"' EXIT

# 'ollama pull' talks to a running server, so start one in the background inside
# the container, wait until it answers, then pull. (Running 'ollama pull' alone
# fails with "could not connect to ollama server".)
docker run --rm \
  -v "${MODEL_DIR}:/root/.ollama" \
  --entrypoint /bin/sh ollama/ollama:latest -c \
  "ollama serve >/tmp/serve.log 2>&1 & for i in \$(seq 1 30); do ollama list >/dev/null 2>&1 && break; sleep 1; done; ollama pull '${MODEL}'"

info "Archiving model files → $OUTPUT ..."
tar -czf "$OUTPUT" -C "$MODEL_DIR" .

SIZE=$(du -h "$OUTPUT" | cut -f1)
ok "Model archive ready: $OUTPUT ($SIZE)"
echo ""
info "Deploy to server:"
info "  ./deploy/ship.sh user@your-server --ai-models=${OUTPUT}"
info ""
info "Or update the model on an already-running server:"
info "  scp ${OUTPUT} user@your-server:/opt/sabc-compliance/"
info "  ssh user@your-server sudo bash -s <<'EOF'"
info "    docker volume create sabc-ollama-models"
info "    docker run --rm -v sabc-ollama-models:/dest \\"
info "      -v /opt/sabc-compliance/ollama-models.tar.gz:/src/m.tar.gz \\"
info "      alpine tar -xzf /src/m.tar.gz -C /dest"
info "    docker restart sabc-ollama"
info "  EOF"
