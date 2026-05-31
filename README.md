# SABC-Compliance

Integrated Linux compliance platform for a fleet of servers (Ubuntu 22.04 +
AlmaLinux / Rocky / RHEL). It installs and wires together **Puppet** (config
management & remediation) and **Wazuh** (security monitoring), and tracks
compliance against **CIS**, **ISO/IEC 27001**, and **PCI-DSS**.

The whole stack ships as **two Docker images** (backend API + frontend UI) so
it runs identically on **macOS, Ubuntu, and AlmaLinux** — the only requirement
on the host is Docker. Nothing else is installed on your machine.

---

## 1. Prerequisites (any OS)

You only need **Docker Engine 20.10+** and the **Docker Compose v2** plugin
(`docker compose`, with a space — not the old `docker-compose`).

Check what you have:

```bash
docker --version
docker compose version
```

If either command is missing, install Docker for your OS:

| OS | Install |
|----|---------|
| **macOS** | [Docker Desktop](https://docs.docker.com/desktop/install/mac-install/) (includes Compose). Or: `brew install --cask docker` then launch Docker.app. |
| **Ubuntu** | `curl -fsSL https://get.docker.com \| sudo sh` then `sudo usermod -aG docker $USER` and re-login. |
| **AlmaLinux / Rocky / RHEL** | `curl -fsSL https://get.docker.com \| sudo sh` then `sudo systemctl enable --now docker` and `sudo usermod -aG docker $USER`. |

> The `get.docker.com` script installs Engine + Compose plugin on every major
> Linux distro, so the same one-liner works on Ubuntu and AlmaLinux alike.

---

## 2. Launch

There are two modes. Use **dev mode** while working on the platform (changes
are live without rebuilding). Use **production mode** to build images for
deployment to an airgapped machine.

### Dev mode (daily use)

```bash
# 1. Clone and enter the repo
git clone <repo-url> SABC-Compliance
cd SABC-Compliance

# 2. Create your environment file (edit JWT_SECRET at minimum)
cp .env.example .env

# 3. Build images once (installs all dependencies into the images)
docker compose -f docker-compose.dev.yml up --build -d

# 4. Save the first-run credentials and SSH public key printed here
docker compose -f docker-compose.dev.yml logs -f backend
```

After the first build, **a `git pull` is all you need**:

```bash
git pull
docker compose -f docker-compose.dev.yml up -d   # no --build
```

- **Backend**: uvicorn watches `/app/src` and restarts automatically on any
  `.py` change — changes are live within a second.
- **Frontend**: Vite HMR pushes JS/CSS changes to the browser without a page
  reload — changes are live instantly.
- **Ansible playbooks**: already live-mounted — edited playbooks take effect
  on the very next job run.

### Production / airgap mode

Build self-contained images, then ship the tarball to the target machine:

```bash
# Build production images (static, no volume mounts)
docker compose build

# Export to a tar file for airgap transfer
docker save bdc-compliance-backend bdc-compliance-frontend \
  | gzip > bdc-compliance.tar.gz

# On the airgapped machine:
docker load < bdc-compliance.tar.gz
docker compose up -d
```

### URLs

| URL | Purpose |
|-----|---------|
| `http://localhost` | Main application UI |
| `http://localhost:3000/docs` | FastAPI Swagger docs |

> **Note (Windows):** if Docker Desktop uses Hyper-V instead of WSL 2,
> volume-mount file-watching may be slow. Switch to WSL 2 backend in
> Docker Desktop → Settings → General for best performance.

### What you'll see in the backend logs on first run

```
============================================================
  FIRST-RUN: Admin user created
  Username : admin
  Password : <generated>
============================================================
[entrypoint] Generating SSH key pair at /app/keys/ansible_id_rsa ...
ssh-rsa AAAA... bdc-ansible        <-- copy this to your managed nodes
```

Copy that **public key** onto every server you want to manage (see
[Connecting nodes](#5-connecting-managed-nodes)).

---

## 3. Day-to-day commands

### Pulling updates (dev mode)

```bash
git pull
docker compose -f docker-compose.dev.yml up -d
```

No `--build` needed. The backend reloads itself; the Vite dev server pushes
frontend changes to the browser via HMR. Rebuild only when you add or remove
a dependency (`requirements.txt` or `package.json` changed):

```bash
docker compose -f docker-compose.dev.yml up --build -d
```

### Stopping, restarting, inspecting

```bash
# all commands below work in both modes; add -f docker-compose.dev.yml for dev
docker compose -f docker-compose.dev.yml ps                # status + health
docker compose -f docker-compose.dev.yml logs -f backend   # follow API logs
docker compose -f docker-compose.dev.yml logs -f frontend  # follow Vite logs
docker compose -f docker-compose.dev.yml restart backend   # restart API only
docker compose -f docker-compose.dev.yml down              # stop (data kept)
docker compose -f docker-compose.dev.yml down -v           # stop + wipe data
```

### Recovering from a broken build

Only needed if a build was killed mid-download and the cache holds a partial file:

```bash
docker compose -f docker-compose.dev.yml down
docker builder prune -af
docker compose -f docker-compose.dev.yml up --build -d
```

---

## 4. Architecture in Docker

```
Browser ──▶ :80  (frontend container — Nginx)
                 ├── /          ▶ React single-page app (static files)
                 ├── /api/      ▶ http://backend:3000/      (REST, 900s timeout)
                 └── /api/*/ws  ▶ ws://backend:3000/*        (job log streaming)

backend container  (NOT published to the host — internal network only)
   FastAPI + Ansible + OpenSSH client
   Volumes:
     backend-data        ▶ /app/data      SQLite database
     backend-keys        ▶ /app/keys      Ansible SSH key pair (persisted)
     ./backend/packages  ▶ /app/packages  airgap install files (.deb/.rpm/tarball)
```

The browser only ever talks to a **single origin** (the frontend), and Nginx
proxies API + WebSocket traffic to the backend over the private Docker network.
No CORS configuration, no hard-coded backend hostname.

---

## 5. Connecting managed nodes

Each server you manage must accept the platform's SSH key for the `ansible`
user. After first boot, grab the public key from the running container:

```bash
docker compose exec backend cat /app/keys/ansible_id_rsa.pub
```

On each target server, create the `ansible` user (with sudo) and add that key
to `~ansible/.ssh/authorized_keys`. Then register the node in the UI under
**Add VM**, and use the **DNS check** (⚠ in Node Registry) to confirm name
resolution before enrolling Puppet/Wazuh agents.

See [docs/INFRASTRUCTURE.md](docs/INFRASTRUCTURE.md) for the full install
lifecycle, the automatic preflight checks, and how each failure scenario is
handled.

---

## 6. Configuration reference (`.env`)

| Variable | Default | Purpose |
|----------|---------|---------|
| `HTTP_PORT` | `80` | Host port the UI is served on |
| `BACKEND_PORT` | `3000` | Host port the API + Swagger docs are exposed on |
| `JWT_SECRET` | — | **Change this.** Session-token signing key (32+ random chars) |
| `PUPPET_MASTER_HOST` | _(unset)_ | Optional; also settable from the UI |
| `WAZUH_MANAGER_HOST` | _(unset)_ | Optional; also settable from the UI |

Generate a strong secret:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```
