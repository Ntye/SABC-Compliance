# BdC Compliance Platform — Backend

FastAPI backend for the BdC Integrated Linux Compliance Platform.  
Manages Rocky Linux 9 and Ubuntu 22.04 servers across CIS, ISO 27001, and PCI-DSS frameworks.

---

## Quick Start

```bash
cd backend
bash launch.sh
```

That single command:
1. Checks Python 3.11+ is installed
2. Creates `.venv/` if it doesn't exist
3. Installs all dependencies from `requirements.txt`
4. Creates `keys/` and `data/` directories
5. Generates an SSH key pair at `keys/ansible_id_rsa` if missing
6. Loads `.env` if present
7. Kills any existing process on `PORT` (default 3000)
8. Starts uvicorn with `--reload` (development mode)

Server starts at **http://localhost:3000**

---

## Prerequisites

```bash
# Ubuntu / Debian
sudo apt-get install python3.11 python3.11-venv python3-pip lsof

# Verify
python3 --version   # must be 3.11 or higher
```

> **Tip:** `launch.sh` uses `python -m pip` internally (not the `pip` binary directly),
> so it works even on systems where the venv doesn't create a `pip` symlink.

---

## Manual Launch (without launch.sh)

```bash
cd backend

# Create venv
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create required directories
mkdir -p keys data

# Start the server
uvicorn src.main:app --host 0.0.0.0 --port 3000 --reload
```

---

## Configuration

Copy `.env.example` to `.env` and edit as needed:

```bash
cp .env.example .env
```

Key variables:

| Variable | Default | Description |
|---|---|---|
| `PORT` | `3000` | HTTP port |
| `DB_PATH` | `./data/platform.db` | SQLite database path |
| `JWT_SECRET` | `change-me-...` | **Change this in production** |
| `JWT_EXPIRE_HOURS` | `24` | JWT token lifetime |
| `PUPPET_MASTER_HOST` | _(empty)_ | Leave blank for stub mode |
| `WAZUH_MANAGER_HOST` | _(empty)_ | Leave blank for stub mode |

### Stub Mode

When `PUPPET_MASTER_HOST` and `WAZUH_MANAGER_HOST` are not set, all calls to those services return safe empty responses. Every endpoint works. **This is the expected state during development.**

---

## First Run — Credentials

On the very first start (empty database), the server prints an **admin user** and an **admin API key** to stdout:

```
============================================================
  FIRST-RUN: Admin user created
  Username : admin
  Password : <generated>
  Store these credentials securely!
============================================================

============================================================
  FIRST-RUN: Admin API key created
  API Key: bdc_<hex>
  Store this key securely — it will not be shown again!
============================================================
```

Save these — they are only shown once.

---

## API Endpoints (Feature 1 — Auth)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/auth/login` | None | Username + password → JWT token |
| `POST` | `/auth/init` | None | Bootstrap first admin API key |
| `GET` | `/auth/keys` | admin | List all API keys |
| `POST` | `/auth/keys` | admin | Create a new API key |
| `DELETE` | `/auth/keys/{id}` | admin | Revoke an API key |
| `GET` | `/auth/users` | admin | List all users |
| `POST` | `/auth/users` | admin | Create a new user |
| `POST` | `/auth/users/change-password` | any | Change own password |
| `GET` | `/health` | None | Platform health check |

### Authentication

Two methods accepted on all protected endpoints:

```bash
# JWT Bearer (from POST /auth/login)
curl -H "Authorization: Bearer <jwt>" http://localhost:3000/auth/keys

# API Key (machine-to-machine)
curl -H "X-API-Key: bdc_<hex>" http://localhost:3000/auth/keys
```

---

## Interactive API Docs

| URL | Description |
|-----|-------------|
| http://localhost:3000/docs | Swagger UI (try every endpoint) |
| http://localhost:3000/redoc | ReDoc (read-only reference) |
| http://localhost:3000/openapi.json | Raw OpenAPI 3.1 spec |

---

## Project Structure

```
backend/
  src/
    main.py              # Composition root — wires everything together
    config.py            # Pydantic settings from env vars
    core/
      domain/
        entities.py      # Pure dataclasses — no external deps
        interfaces.py    # Abstract base classes for all adapters
      errors.py          # Domain exception hierarchy
      events.py          # In-memory async event bus
    modules/
      auth/usecases.py   # API key + JWT login + user management
      nodes/             # (Feature 2)
      provisioning/      # (Feature 3)
      compliance/        # (Feature 4)
      rules/             # (Feature 5)
    infrastructure/
      database/adapter.py  # SQLAlchemy 2.0 async — all repositories
      ssh/               # (Feature 2)
      ansible/           # (Feature 3)
      puppet/            # (Feature 4)
      wazuh/             # (Feature 4)
    interface/
      http/routes/       # FastAPI route modules
      websocket/         # WebSocket manager (Feature 3)
  ansible/               # Ansible playbooks and roles (Feature 7)
  scripts/               # Install and test scripts (Feature 7)
  keys/                  # SSH keys — gitignored
  data/                  # SQLite DB — gitignored
```

---

## Architecture Rules

1. `core/domain/` — zero external dependencies, stdlib only
2. `modules/*/usecases.py` — depends only on domain, never on infra
3. `infrastructure/` — implements interfaces, never imports use cases
4. `interface/` — receives use cases via dependency injection
5. `main.py` — only file that wires use cases + infrastructure together

---

## Production Launch

```bash
ENVIRONMENT=production bash launch.sh
```

Starts uvicorn **without** `--reload`. Set `JWT_SECRET` to a strong random value:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

## Features Roadmap

| Feature | Status | What it adds |
|---------|--------|-------------|
| 0 — Scaffolding | ✅ Done | Project structure, config, tooling |
| 1 — Auth | ✅ Done | Login, API keys, users, JWT |
| 2 — Node Registry | 🔜 Next | Register servers, SSH ping, OS detection |
| 3 — Jobs | 🔜 | Ansible provisioning, WebSocket log stream |
| 4 — Compliance | 🔜 | Puppet/Wazuh integration, webhook, remediation |
| 5 — Rules | 🔜 | Puppet compliance rules library |
| 6 — Health & Audit | 🔜 | Health checks, HTTP audit log, overview |
| 7 — Scripts | 🔜 | Ansible playbooks, install scripts |
