# SABC Compliance Platform

Integrated Linux compliance platform for Société Anonyme des Brasseries du Cameroun (SABC /
Boissons du Cameroun). Manages a fleet of Linux servers (Ubuntu 22.04 + Rocky/AlmaLinux/RHEL)
with automated compliance enforcement against **CIS Benchmarks**, **ISO/IEC 27001**, and **PCI-DSS**.

Ships as **two Docker images** (FastAPI backend + React frontend). The only requirement on the
host is Docker — nothing else is installed on your machine.

---

## Table of Contents

1. [Architecture](#1-architecture)
2. [Prerequisites](#2-prerequisites)
3. [First-time setup](#3-first-time-setup)
4. [Authentication](#4-authentication)
5. [Adding managed servers](#5-adding-managed-servers)
6. [Infrastructure (Puppet & Detection agent)](#6-infrastructure-puppet--detection-agent)
7. [Compliance](#7-compliance)
8. [Day-to-day operations](#8-day-to-day-operations)
9. [EC2 deployment](#9-ec2-deployment)
10. [Airgap / offline deployment](#10-airgap--offline-deployment)
11. [Building for a different platform (arm64 vs amd64)](#11-building-for-a-different-platform-arm64-vs-amd64)
12. [Configuration reference](#12-configuration-reference)

---

## 1. Architecture

```
Browser
  │
  └─▶ :80  frontend container (Nginx)
            ├── /           React SPA (static files)
            ├── /api/       → http://sabc-backend:3000/   (REST API, 900s timeout)
            └── /api/*/ws   → ws://sabc-backend:3000/*    (live job log streaming)

sabc-backend container (FastAPI + Ansible + OpenSSH client)
  Volumes:
    sabc_backend-data  →  /app/data            SQLite database (nodes, jobs, rules, audit)
    sabc_backend-keys  →  /app/keys            Ansible SSH key pair (generated once, persisted)
    ./backend/packages →  /app/packages        Airgap install files (.deb/.rpm/wheels)
    ./detection-agent  →  /app/detection-agent Agent sources shipped to managed nodes

Docker network: sabc-net (bridge, internal — backend is not exposed to LAN)

Managed node (each server in the fleet)
  ├── puppet-agent                 enforcement plane — applies the referential
  └── compliance-detection-agent  detection plane — SABC's own lightweight
        Python daemon (inotify via watchdog). Watches /etc/ssh/, /etc/pam.d/,
        /etc/sudoers*, /etc/passwd, /etc/group, /etc/shadow, snapshots every
        change as evidence (SHA-256 + metadata, content where policy allows)
        and POSTs it to the platform:

          POST /api/webhooks/detection   (X-API-Key + optional CIDR allowlist)
```

The browser talks to a **single origin** (port 80). Nginx proxies all `/api/` traffic and
WebSocket connections to the backend over the private Docker network. No CORS issues,
no hard-coded backend hostname in the browser.

The backend exposes port 3000 separately for direct API access and the Swagger docs
(`http://localhost:3000/docs`).

### Detection → scan (→ optional remediation) loop

The **detection plane is the custom SABC detection agent** (there is no
third-party SIEM). Each event the agent reports is stored as tamper-evident
evidence — `config_change_events` rows plus content-addressed `config_blobs`
(deduplicated by SHA-256) — and then run through the gateway's feedback-storm
guard, in this order:

1. **Active remediation window** — a remediation with `outcome=pending` exists
   for the node → the event is stored `suppressed` and linked to that
   remediation (it is our own Puppet run writing files).
2. **`puppet_running` flag** — the agent saw Puppet's catalog-run lock file →
   stored `suppressed` (scheduled converge).
3. **Genuine drift** — stored live, `compliance.violation_detected` is
   published, and a **compliance scan always runs** so the dashboard reflects
   the node's true posture. **Remediation is decoupled**: Puppet enforcement
   runs only when the **closed loop** is enabled — globally
   (`detection_closed_loop_enabled`, toggled on the Tiers page) or for a Puppet
   node group the node belongs to (`active_response_enabled`). With the loop
   off, the platform observes and scans but never auto-enforces.

Every event records **who** made the change: the agent enriches it from auditd
(`auid`/`uid`/`exe`/`comm`) and resolves the login uid to a username. The
**Detection Events** page shows the actor, and **view diff** opens a modal that
diffs the previous snapshot against the new one (by content hash).

The agent never suppresses locally — every change reaches the platform, so the
evidence trail is complete either way. Snapshots are evidence only; the platform
never rolls files back from blobs.

---

## 2. Prerequisites

Only **Docker Engine 24+** and the **Docker Compose v2 plugin** (`docker compose` with a space).

```bash
docker --version          # Docker version 24.x or higher
docker compose version    # Docker Compose version v2.x
```

| OS | Install |
|----|---------|
| **macOS** | [Docker Desktop](https://docs.docker.com/desktop/install/mac-install/) · or `brew install --cask docker` |
| **Ubuntu 22.04+** | `curl -fsSL https://get.docker.com \| sudo sh && sudo usermod -aG docker $USER` |
| **Rocky / AlmaLinux / RHEL** | `curl -fsSL https://get.docker.com \| sudo sh && sudo systemctl enable --now docker && sudo usermod -aG docker $USER` |

Re-login after adding yourself to the `docker` group.

---

## 3. First-time setup

```bash
# 1. Clone the repository
git clone <repo-url> SABC-Compliance
cd SABC-Compliance

# 2. Create your environment file
cp backend/.env.example .env
# Edit .env — at minimum change JWT_SECRET to a random 32-char string:
python3 -c "import secrets; print(secrets.token_hex(32))"

# 3. Build and start (production mode)
docker compose up -d

# 4. Watch the first-run output — it prints credentials
docker compose logs -f backend
```

### What the first run prints

```
============================================================
  FIRST-RUN: Admin user created
  Username : admin
  Password : <generated — store this securely>
============================================================
[entrypoint] Generating SSH key pair at /app/keys/ansible_id_rsa ...
ssh-rsa AAAA... sabc-ansible    ← the platform's public SSH key
============================================================
  SABC Compliance Platform  v1.0.0
  Société Anonyme des Brasseries du Cameroun
  API:   http://0.0.0.0:3000
  Docs:  http://localhost:3000/docs
============================================================
```

The **SSH key pair** is generated once and stored in the `backend-keys` Docker volume. It
survives container updates and rebuilds. This key is what the platform uses to connect to
all managed servers.

### URLs

| URL | Purpose |
|-----|---------|
| `http://localhost` | Main platform UI |
| `http://localhost:3000/docs` | Swagger / OpenAPI docs |
| `http://localhost:3000/redoc` | ReDoc API reference |

### Dev mode (live code reloading)

Use this when developing the platform itself. Source code is volume-mounted — changes
are live without rebuilding.

```bash
docker compose -f docker-compose.dev.yml up --build -d
```

- **Backend**: uvicorn `--reload` restarts automatically on any `.py` change.
- **Frontend**: Vite HMR pushes JS/CSS changes to the browser without a page reload.
- **Playbooks**: already live-mounted — edits take effect on the next job run.

After a `git pull` (no rebuild needed):

```bash
git pull
docker compose -f docker-compose.dev.yml up -d
```

Rebuild only when `requirements.txt` or `package.json` changes:

```bash
docker compose -f docker-compose.dev.yml up --build -d
```

---

## 4. Authentication

### Login

Log in at `http://localhost` with the admin credentials printed on first run. On every
login the server issues a **JWT session token** and a **personal API key** (matching your
role), both stored automatically in the browser.

### Roles

| Role | Permissions |
|------|-------------|
| `admin` | Full access — user management, delete nodes, all actions |
| `operator` | Read + write — register nodes, install services, trigger jobs |
| `readonly` | Read-only views across all pages |

### API keys

Every user gets a personal API key when they log in. This key is automatically applied
in the browser — you do not need to copy/paste it.

- **Operators and admins**: all actions work with the personal key.
- **Readonly users**: can temporarily activate a higher-level key (e.g. operator key) via the
  override button in the header. The personal readonly key is restored on next login.
- Keys are prefixed `sabc_` and visible under **Settings → API Keys**.

### Machine-to-machine access

For scripts or CI pipelines, create a named API key from the **API Keys** page and pass it
as a header:

```bash
curl -H "X-API-Key: sabc_<key>" http://localhost:3000/nodes
```

---

## 5. Adding managed servers

The platform connects to servers over SSH using the `ansible` OS user and key-based
authentication. Before registering a server you must run the **bootstrap script** on it
once — this creates the `ansible` user, installs the platform's public key, and grants
passwordless sudo. No manual SSH key copying needed.

### Option A — Server can reach the platform (online)

Open the **Add Server** page. Copy the one-liner and run it on the target server as root:

```bash
curl -sSL http://<platform-ip>/api/nodes/bootstrap | sudo bash
```

The script is served unauthenticated (it only contains the public key, which is not secret).

### Option B — Airgap (no network from server to platform)

1. Click **Download setup-node.sh** on the Add Server page.
   The platform's public key is embedded in the script at download time.
2. Transfer the script to the target server (USB, SCP, etc.).
3. On the target server:

```bash
sudo bash setup-node.sh
```

### Register the server

After the bootstrap script completes, fill in the **Add Server** form:

| Field | Notes |
|-------|-------|
| Hostname | Friendly name (e.g. `web-prod-01`) |
| IP Address | The server's IP that this platform can reach |
| SSH Port | Default 22 |
| SSH User | Leave as `ansible` (the user the bootstrap created) |
| SSH Key Path | Leave blank — uses the platform default key |

Click **Register server**. The platform will:
1. Test SSH connectivity
2. Detect OS (family, name, version)
3. Capture the server's FQDN
4. Check DNS resolution

### Cross-account and cross-provider servers

The platform is SSH-based and provider-agnostic. You can manage:
- EC2 instances in any AWS account (any region)
- On-premise Servers
- VPS on Hetzner, OVH, Azure, etc.

The only requirement is that **the platform can reach the server on port 22**. For EC2
instances in another account, simply add an inbound rule to their security group allowing
`TCP 22` from the platform server's IP.

---

## 6. Infrastructure (Puppet & Detection agent)

Before enrolling agents on nodes, set up the master services on the **Infrastructure** page.

### Puppet (configuration management & remediation)

Puppet enforces compliance rules and remediates drift. Connect to an existing Puppet
master or install one on a registered node:

1. **Infrastructure → Puppet Master → Install on a node**
   The platform runs an Ansible playbook that installs Puppet Enterprise, configures TLS,
   and sets up the console.
2. Or **Connect existing** if you already have a Puppet master.

Then **Install Puppet agent** on each managed node from the Infrastructure page.

### Detection agent (config-change detection & evidence)

The platform ships its own lightweight detection agent — a small Python daemon
(`detection-agent/agent.py`, inotify-based) that watches the compliance-critical
paths (`/etc/ssh/`, `/etc/pam.d/`, `/etc/sudoers*`, `/etc/passwd`, `/etc/group`,
`/etc/shadow`, …), snapshots every change as evidence (SHA-256 + metadata, file
content only where policy allows), and reports to the platform's detection
webhook. There is no separate manager service to install.

**Install detection agent** on each managed node from the Infrastructure page —
the platform injects the gateway URL and the shared API key automatically. The
agent needs only Python 3 and the `watchdog` library (installed by the playbook
from the distro repo or pip; drop a wheel into `backend/packages/detection-agent/`
for airgap installs).

---

## 7. Compliance

### The unified referential (profiles)

Compliance **profiles** are hardening referentials imported from the **unified
multi-OS referential** — one sheet/CSV in the structure of
`platform/seed/referentials/sabc_baseline/` = one profile. Each control row
carries:

- an internal **Control ID** (e.g. `JR2.C.1.1.1`) — *the* key; the Control Key is
  auto-derived from it, and imports never key on the CIS reference;
- **per-OS-family guidance**: separate Validate/Configure procedures for the
  **Debian family** (Ubuntu/Debian/Mint) and the **Red Hat family**
  (Alma/Rocky/RHEL/CentOS);
- a **CIS Level** (1 or 2; blank = 1).

Import is **UPSERT** (never wipe-and-rebuild): matched by Control ID, existing
controls are updated (with edit history), new ones inserted, and controls absent
from a re-import are **retired** (soft — kept so historical reports still read
them). The **SABC Baseline** ships built-in (system profile, undeletable), seeded
at first boot through the same importer, complete for **both families** out of
the box.

From each profile the platform generates, at seed time:

- a **Puppet module** (`sabc_hardening`) — one class per control, branching
  internally on `$facts['os']['family']`, filled from the two Configure columns;
- an **InSpec profile** — one control per referential control, guarded by
  `os.family`, from the two Validate columns.

A family with no runnable authored guidance for a control is reported as
*implementation pending* and never auto-generated (see
`backend/puppet/modules/sabc_hardening/IMPLEMENTATION_PENDING.txt`).

### Tiers — which CIS Levels apply

CIS Level is a **control** property; a node's **tier** decides which levels apply
to it:

- **Non-critical** (system tier): CIS Level 1 only.
- **Critical** (system tier): CIS Level 1 + 2.
- **Custom** tiers (e.g. "1.5", admin-only, audited): Level 1 plus a hand-picked
  set of real Level-2 controls.

Every node has exactly one tier (Non-critical on enrolment; reassignment is
audited). A tier can be assigned to a **single node** or, in one action, to
**every member of a Puppet node group** (Tiers page → *Apply a tier*). The
generated Puppet classes and InSpec controls exist for **all** levels/families —
the tier simply gates which ones a given node enforces and is scanned against.
Assigning a tier and then **enforcing** it fully solves the internal referential
on that target.

### Compliance node groups (distinct from Puppet node groups)

A **compliance group** is a platform-only concept — it binds a set of profiles
(the standards to scan against) to a set of member nodes, and **never** touches
the Puppet Node Classifier. A node may belong to several compliance groups.
Manage them under `/compliance-groups` (kept entirely separate from the Puppet
`/node-groups`).

### How a scan resolves

```
compliance group  →  its bound profiles  →  its member nodes
      per node:  tier decides CIS Levels  →  os.family decides which controls
                 →  run that subset of the profile's InSpec controls
```

Each report records the compliance group, profile + version, node, tier at scan
time, and OS family — so "which servers are scanned against standard X, at what
tier" is a query. On-demand single-node scans resolve the same way via the
node's group memberships (falling back to the built-in SABC Baseline when the
node is in no group); the auto-scan scheduler iterates compliance groups + their
members.

### Enforce the referential (make everything pass)

To bring a node — or a whole node group — into full compliance, click
**Enforce referential** (on the node's compliance page, the node group page, or
the Tiers page). This pushes the generated `sabc_hardening` module to the target
and runs `puppet apply`, scoped to exactly the controls the target's **tier** and
**OS family** make applicable — the same set the scan checks — so *enforce → scan*
converges on 100%. It works whether or not the node is classified on a Puppet
master, and is idempotent (each control is guarded by its own Validate check).

Enforcement is exposed as `POST /compliance/enforce` (`{node_id | group_id}`) and
runs as an Ansible job whose output streams in the **Jobs** page. The lighter
**Remediate** button still runs `puppet agent -t` against whatever catalog the
master assigns.

### Tiers page

The **Tiers** page (under *Manage*) lists every tier, lets admins create/edit/
delete custom tiers, assigns a tier to a **node or an entire node group**, and
enforces the referential on that target in one place. It also hosts the global
**closed-loop** switch.

### Closed feedback loop

```
Detection agent spots a config change (inotify)
        ↓
Event posted to the platform (evidence stored: hashes, metadata, content, actor)
        ↓
Suppression rules applied (active remediation window? scheduled Puppet run?)
        ↓
Genuine drift → compliance SCAN always runs (dashboard reflects true posture)
        ↓
Closed loop enabled? → Puppet enforcement job; otherwise scan only
        ↓
Compliance status updated; event + diff visible on the Detection Events page
```

---

## 8. Day-to-day operations

### Common commands

```bash
# Status of all containers
docker compose ps

# Follow backend logs
docker compose logs -f backend

# Follow frontend logs
docker compose logs -f frontend

# Restart backend only (after a config change)
docker compose restart backend

# Stop everything (data is preserved in volumes)
docker compose down

# Stop and wipe all data (clean slate)
docker compose down -v
```

### Pulling platform updates

```bash
git pull
docker compose build
docker compose up -d
```

The database volumes (`backend-data`, `backend-keys`) are preserved across rebuilds.
SSH keys and registered nodes survive updates.

### Accessing the database directly

```bash
docker compose exec backend sqlite3 /app/data/platform.db ".tables"
```

### Recovering from a broken build

```bash
docker compose down
docker builder prune -af     # clear corrupt build cache
docker compose build --no-cache
docker compose up -d
```

### Audit log

All authenticated API calls are logged. View under **Audit** in the UI, or query directly:

```bash
curl -H "X-API-Key: sabc_<key>" http://localhost:3000/audit?limit=50
```

---

## 9. EC2 deployment

The `deploy/ship.sh` script builds Docker images on your local machine, transfers them to
an EC2 instance via SCP, loads them, and starts the platform. No Docker Hub, no registry.

### First deployment

```bash
# Launch an EC2 (Ubuntu 22.04, t3.small+)
# Security group inbound rules:
#   TCP 22   from your IP       (SSH to platform)
#   TCP 80   from 0.0.0.0/0    (Platform UI)

# From your local machine (where the source code is):
chmod +x deploy/ship.sh
./deploy/ship.sh ubuntu@<ec2-public-ip> --setup
```

`--setup` installs Docker on the EC2 before deploying. Drop it if Docker is already there.

This single command:
1. Builds both Docker images locally (for the correct platform)
2. Compresses them to `deploy/sabc-images.tar.gz`
3. SCPs the archive + `docker-compose.yml` + `.env` to `/opt/sabc-compliance/` on the EC2
4. Loads the images and starts the platform with `docker compose up -d`
5. Prints the public URL when done

### Updating after code changes

```bash
# Full rebuild + redeploy:
./deploy/ship.sh ubuntu@<ec2-public-ip>

# Transfer only (skips build — uses last built archive):
./deploy/ship.sh ubuntu@<ec2-public-ip> --update
```

### Manual / step-by-step transfer

```bash
# 1. Build and save images locally:
./deploy/ship.sh --build-only
# Archive is at: deploy/sabc-images.tar.gz

# 2. Transfer to EC2:
scp deploy/sabc-images.tar.gz ubuntu@<ec2-ip>:/opt/sabc-compliance/
scp docker-compose.yml ubuntu@<ec2-ip>:/opt/sabc-compliance/
scp .env ubuntu@<ec2-ip>:/opt/sabc-compliance/

# 3. On the EC2:
cd /opt/sabc-compliance
docker load -i sabc-images.tar.gz
docker compose up -d
```

### Managing other EC2s from the platform

After deploying the platform to EC2, add other EC2 instances as managed nodes.
The bootstrap one-liner uses the platform's **private IP** (reachable within the VPC):

```bash
# On the target EC2 (in the same VPC):
curl -sSL http://<platform-private-ip>/api/nodes/bootstrap | sudo bash
```

For EC2s in a **different AWS account**, open TCP 22 inbound on their security group to
the platform EC2's public IP, then use the public IP in the bootstrap command.

### Recommended .env on EC2

```bash
HTTP_PORT=80
BACKEND_PORT=3000
JWT_SECRET=<random 32+ chars>
# Set to the EC2 private IP so the bootstrap curl command auto-populates in the UI:
HOST_IP=10.0.x.x
```

---

## 10. Airgap / offline deployment

For environments with no internet access, bundle the offline installers into the backend image:

```bash
# 1. Place offline installers into backend/packages/ (see backend/packages/README.md)

# 2. Build the bundled image (bakes packages/ into the image):
./deploy/ship.sh --bundle
# or manually:
docker compose build
docker build -f backend/Dockerfile.bundle -t sabc-compliance-backend:bundled ./backend

# 3. Transfer to the airgap machine:
docker save sabc-compliance-backend:bundled sabc-compliance-frontend \
  | gzip > sabc-bundle.tar.gz
# SCP / USB transfer sabc-bundle.tar.gz to the target machine

# 4. On the airgap machine:
docker load -i sabc-bundle.tar.gz
docker compose up -d
```

On first start, the entrypoint seeds `/app/packages/` from the bundled files inside the
image. Subsequent starts use the volume directly and the bundled copy is ignored.

---

## 11. Building for a different platform (arm64 vs amd64)

If you build on a **Mac (Apple Silicon / arm64)** and deploy to a **Linux server (amd64)**,
Docker images will refuse to start with a platform mismatch error.

**Always rebuild on the target machine** (recommended for EC2 deployments):
```bash
# The deploy/ship.sh script handles this automatically —
# it builds locally and transfers, so the build platform matches where you run it.
```

**Or cross-compile explicitly** on your Mac before transferring:
```bash
DOCKER_DEFAULT_PLATFORM=linux/amd64 docker compose build
```

**Or rebuild directly on the EC2** after transferring the source:
```bash
scp -r . ubuntu@<ec2-ip>:/opt/sabc-compliance/
ssh ubuntu@<ec2-ip> "cd /opt/sabc-compliance && docker compose build && docker compose up -d"
```

For local use (everything on the same Mac), no special flags are needed.

---

## 12. Configuration reference (`.env`)

Copy `backend/.env.example` to `.env` in the project root before starting.

| Variable | Default | Required | Purpose |
|----------|---------|----------|---------|
| `HTTP_PORT` | `80` | — | Host port for the UI |
| `BACKEND_PORT` | `3000` | — | Host port for the API + Swagger |
| `JWT_SECRET` | — | **Yes** | Session token signing key (32+ random chars) |
| `JWT_EXPIRE_HOURS` | `24` | — | How long a login session lasts |
| `DB_PATH` | `/app/data/platform.db` | — | SQLite database path inside container |
| `SSH_KEY_PATH` | `/app/keys/ansible_id_rsa` | — | Ansible SSH private key path inside container |
| `HOST_IP` | _(auto-detect)_ | — | Set to this machine's LAN/public IP for the bootstrap curl command |
| `HOST_ADMIN_USER` | _(auto-detect)_ | — | Your SSH admin user on this machine (used as a hint in the UI) |
| `PUPPET_MASTER_HOST` | — | — | Pre-configure Puppet master host (also settable from UI) |
| `PUPPET_MASTER_PORT` | `8143` | — | Puppet orchestrator port |
| `DETECTION_WEBHOOK_API_KEY` | — | — | Shared key detection agents present (auto-generated on first agent install) |
| `DETECTION_WEBHOOK_SOURCE_IP` | — | — | Optional CIDR allowlist for the detection webhook |
| `CORS_ORIGINS` | _(defaults)_ | — | Comma-separated list of allowed browser origins |

Generate a strong JWT secret:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### Volumes

| Volume name | Mounted at | Contents |
|-------------|-----------|---------|
| `sabc_backend-data` | `/app/data` | SQLite database — all nodes, jobs, rules, audit |
| `sabc_backend-keys` | `/app/keys` | Ansible SSH key pair — generated once on first start |
| `./backend/packages` | `/app/packages` | Airgap install archives (bind-mount — drop files here without rebuilding) |

These volumes survive `docker compose down` and `docker compose up --build`. Only
`docker compose down -v` removes them.

---

## Project structure

```
SABC-Compliance/
├── backend/
│   ├── src/
│   │   ├── core/          Domain entities, interfaces, errors, events
│   │   ├── modules/       Use-cases: auth, nodes, provisioning
│   │   ├── infrastructure/ DB adapter (SQLite), SSH adapter, Ansible adapter
│   │   └── interface/     FastAPI routes, WebSocket manager, middleware
│   ├── ansible/
│   │   ├── playbooks/     provision.yml, install_puppet_*.yml, install_detection_agent.yml
│   │   └── templates/     Jinja2 templates
│   ├── packages/          Drop airgap archives here (empty by default)
│   ├── Dockerfile
│   ├── Dockerfile.bundle  Builds backend image with packages/ baked in
│   └── docker-entrypoint.sh
├── frontend/
│   ├── src/
│   │   ├── assets/        sabc-logo.png
│   │   ├── components/    Layout, auth, common, settings UI components
│   │   ├── context/       ThemeContext, LangContext (EN + FR)
│   │   ├── i18n/          translations.js (English + French)
│   │   ├── lib/           api.js (all API calls), tw.js (Tailwind helpers)
│   │   └── pages/         One file per page (Overview, Nodes, AddServer, …)
│   └── Dockerfile
├── deploy/
│   └── ship.sh            EC2 build-transfer-deploy script
├── docker-compose.yml     Production compose
├── docker-compose.dev.yml Dev compose (live mounts, HMR)
└── .env.example           Copy to .env and edit
```
