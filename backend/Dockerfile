FROM python:3.12-slim

# System deps: SSH client (Ansible), curl (connectivity checks in playbooks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# CINC Auditor — free, open-source InSpec distribution (no license required).
# Runs locally on the platform and connects to managed nodes over SSH (agentless).
# The CINC omnitruck installer drops the binary at /usr/bin/cinc-auditor.
# If unavailable at build time (e.g. air-gapped build), the runtime status
# endpoint will report "not installed" and the operator can click "Install" in the UI.
RUN set -e; \
    echo "── Installing CINC Auditor via omnitruck ──"; \
    if curl -fsSL https://omnitruck.cinc.sh/install.sh | bash -s -- -P cinc-auditor; then \
        /usr/bin/cinc-auditor version && echo "✓ CINC Auditor installed at build time"; \
    else \
        echo "WARN: CINC Auditor install failed at build time — install via UI at runtime"; \
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

# Application source, Ansible playbooks, and bundled CIS scan profile
COPY src/              src/
COPY ansible/          ansible/
COPY scan-profiles/    scan-profiles/

# One-shot SQLite → PostgreSQL migration helper (invoked by deploy/ship.sh).
COPY migrate_to_postgres.py .

# Persistent directories (overridden by volumes at runtime)
RUN mkdir -p data keys \
    packages/puppet-master packages/puppet-agent \
    packages/wazuh-manager packages/wazuh-agent

COPY docker-entrypoint.sh /docker-entrypoint.sh
# Strip any CR characters before making the script executable. When the repo is
# checked out on a Windows build host, git's autocrlf can rewrite the script
# with CRLF line endings; the kernel would then read the shebang as
# "#!/bin/bash\r" and fail with "exec /docker-entrypoint.sh: no such file or
# directory". Normalising to LF here makes the build host irrelevant.
RUN sed -i 's/\r$//' /docker-entrypoint.sh && chmod +x /docker-entrypoint.sh

VOLUME ["/app/data", "/app/keys", "/app/packages"]

EXPOSE 3000

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["uvicorn", "main:app", "--app-dir", "/app/src", \
     "--host", "0.0.0.0", "--port", "3000"]
