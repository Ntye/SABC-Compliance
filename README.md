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

## 2. Launch (identical on every OS)

```bash
# 1. Clone and enter the repo
git clone <repo-url> SABC-Compliance
cd SABC-Compliance

# 2. Create your environment file (then edit JWT_SECRET at minimum)
cp .env.example .env

# 3. Build and start both containers
docker compose up --build -d

# 4. Watch the backend logs — the first-run admin credentials and the
#    Ansible SSH public key are printed here. SAVE THEM.
docker compose logs -f backend
```

Open the UI at **http://localhost** (or `http://localhost:<HTTP_PORT>` if you
changed the port in `.env`).

That's it — the same three commands work on macOS, Ubuntu, and AlmaLinux.

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

### Pulling updates

```bash
git pull
docker compose up --build -d
```

`--build` re-checks every Dockerfile layer and only rebuilds what changed.
Code-only changes finish in seconds; if dependencies changed the BuildKit
cache mounts (`/root/.cache/pip`, `/root/.npm`) reuse already-downloaded
packages and fetch only the new ones.

### Stopping, restarting, inspecting

```bash
docker compose ps                 # status + health of both services
docker compose logs -f backend    # follow API logs
docker compose logs -f frontend   # follow Nginx logs
docker compose restart backend    # restart just the API (no rebuild)
docker compose down               # stop (data + keys persist in volumes)
docker compose up -d              # start again (no rebuild)
docker compose down -v            # stop AND wipe data + keys (full reset)
```

### Updating one image without touching the other

The two images are independent — rebuild and roll only what changed:

```bash
# Backend only (API change, playbook fix)
docker compose build backend && docker compose up -d --no-deps backend

# Frontend only (UI change)
docker compose build frontend && docker compose up -d --no-deps frontend
```

Persistent data (`backend-data`), the SSH key (`backend-keys`), and your
airgap packages (`./backend/packages`) all survive image rebuilds.

### Recovering from a broken build

Only needed if a build was killed mid-download (Ctrl-C, machine shutdown)
and the cache holds a partial file:

```bash
docker compose down
docker builder prune -af          # clear all BuildKit caches
docker compose build --no-cache   # force a clean rebuild
docker compose up -d
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
| `JWT_SECRET` | — | **Change this.** Session-token signing key (32+ random chars) |
| `PUPPET_MASTER_HOST` | _(unset)_ | Optional; also settable from the UI |
| `WAZUH_MANAGER_HOST` | _(unset)_ | Optional; also settable from the UI |

Generate a strong secret:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```
