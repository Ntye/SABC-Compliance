FROM python:3.12-slim

# System deps: SSH client (Ansible), curl (connectivity checks in playbooks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Chef InSpec — runs locally on the platform and connects to managed nodes
# over SSH (agentless). Used by the compliance engine to evaluate the InSpec
# controls defined on each rule. The omnitruck installer drops the binary at
# /usr/bin/inspec. If unavailable at build time (e.g. air-gapped build), the
# runtime status endpoint will report "not installed" and the operator can
# click "Install on platform" in the UI.
RUN set -e; \
    echo "── Installing Chef InSpec via omnitruck ──"; \
    if curl -fsSL https://omnitruck.chef.io/install.sh | bash -s -- -P inspec; then \
        /usr/bin/inspec version && echo "✓ InSpec installed at build time"; \
    else \
        echo "WARN: InSpec install failed at build time — install via UI at runtime"; \
    fi

WORKDIR /app

# Python deps first — layer cached unless requirements.txt changes.
# Cache mount keeps already-downloaded wheels between rebuilds, so when
# requirements.txt changes only the *new* packages are fetched.
# --retries/--timeout cope with slow mirrors. If a build is killed mid-
# download the cache may hold a partial file; `docker builder prune` resets it.
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    pip install --timeout=300 --retries=10 -r requirements.txt

# Application source, Ansible playbooks, and bundled InSpec profile
COPY src/              src/
COPY ansible/          ansible/
COPY inspec-profiles/  inspec-profiles/

# Persistent directories (overridden by volumes at runtime)
RUN mkdir -p data keys \
    packages/puppet-master packages/puppet-agent \
    packages/wazuh-manager packages/wazuh-agent

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

VOLUME ["/app/data", "/app/keys", "/app/packages"]

EXPOSE 3000

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["uvicorn", "main:app", "--app-dir", "/app/src", \
     "--host", "0.0.0.0", "--port", "3000"]
