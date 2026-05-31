# syntax=docker/dockerfile:1
FROM python:3.12-slim

# System deps: SSH client (Ansible), curl (connectivity checks in playbooks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps first — layer cached unless requirements.txt changes.
# Cache mount keeps already-downloaded wheels between rebuilds, so when
# requirements.txt changes only the *new* packages are fetched.
# --retries/--timeout cope with slow mirrors. If a build is killed mid-
# download the cache may hold a partial file; `docker builder prune` resets it.
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    pip install --timeout=300 --retries=10 -r requirements.txt

# Application source and Ansible playbooks
COPY src/     src/
COPY ansible/ ansible/

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
     "--host", "0.0.0.0", "--port", "3000", \
     "--root-path", "/api"]
