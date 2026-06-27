# ═══════════════════════════════════════════════════════════════════════════════
# SABC Offline AI Assistant — Ollama image with the model BAKED IN
# ═══════════════════════════════════════════════════════════════════════════════
#
# This image embeds the LLM weights directly in an image layer, so the airgapped
# server never needs internet — it only `docker load`s the tarball that
# deploy/ship.sh already produces for every other service.
#
# Build this on a machine WITH internet (the same machine that builds the other
# images). The model is downloaded once at build time and committed into the
# image; at runtime Ollama serves it entirely offline.
#
#   # default small model (≈1.3 GB on disk):
#   docker build -t sabc-ollama deploy/ollama
#
#   # pick a different / larger model:
#   docker build --build-arg OLLAMA_MODEL=llama3.1:8b -t sabc-ollama deploy/ollama
#
# ship.sh builds, saves and ships this exactly like backend/frontend/postgres —
# there is NO separate command to run on the server.
# ═══════════════════════════════════════════════════════════════════════════════
FROM ollama/ollama:latest

# Which model to embed. Small models keep the shipped archive manageable:
#   llama3.2:3b   ≈ 1.3 GB   (default — fast, decent EN, basic FR)
#   llama3.2:3b   ≈ 2.0 GB   (better French)
#   qwen2.5:3b    ≈ 1.9 GB   (strong multilingual)
#   llama3.1:8b   ≈ 4.7 GB   (best quality, heavier to ship)
ARG OLLAMA_MODEL=llama3.2:3b
ENV OLLAMA_MODEL=${OLLAMA_MODEL}

# Store weights in a plain image directory rather than the default
# /root/.ollama — a compose volume could otherwise shadow that path and hide
# the baked-in model. With OLLAMA_MODELS=/models the weights live in a regular
# image layer and need no bind mount or volume at runtime.
ENV OLLAMA_MODELS=/models

# Pull the model during the build: start the server in the background, wait for
# it to accept requests, pull, then shut it down. The downloaded blobs are
# committed into this RUN layer, so the finished image is fully self-contained.
RUN ollama serve & \
    pid=$! ; \
    until ollama list >/dev/null 2>&1 ; do sleep 1 ; done ; \
    echo "Pulling ${OLLAMA_MODEL} ..." ; \
    ollama pull "${OLLAMA_MODEL}" ; \
    kill "$pid" 2>/dev/null || true ; \
    wait "$pid" 2>/dev/null || true

# The base image's ENTRYPOINT already runs `ollama serve`; just document the port.
EXPOSE 11434
