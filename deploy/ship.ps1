#Requires -Version 5.1
# =============================================================================
# SABC Compliance Platform -- Windows Deployment Script (PowerShell)
# =============================================================================
#
# Usage:
#   .\deploy\ship.ps1 -Target ubuntu@192.168.1.50
#   .\deploy\ship.ps1 -Target ubuntu@192.168.1.50 -SshKey .\keys\id_rsa
#   .\deploy\ship.ps1 -Target ubuntu@192.168.1.50 -Setup        # First time: installs Docker
#   .\deploy\ship.ps1 -Target ubuntu@192.168.1.50 -Update       # Skip rebuild: transfer existing archive + load + start
#   .\deploy\ship.ps1 -Target ubuntu@192.168.1.50 -Start        # Skip build/transfer: load already-transferred archive + start
#   .\deploy\ship.ps1 -Target ubuntu@192.168.1.50 -Restart      # Skip build/transfer/load: just docker compose up -d
#   .\deploy\ship.ps1 -Target ubuntu@192.168.1.50 -Rollback     # Roll back to the previous deployment
#   .\deploy\ship.ps1 -BuildOnly                                 # Build and save locally only
#
# Partial service updates (faster — only rebuilds and restarts one container):
#   .\deploy\ship.ps1 -Target ubuntu@192.168.1.50 -BackendOnly          Rebuild and redeploy only the backend
#   .\deploy\ship.ps1 -Target ubuntu@192.168.1.50 -FrontendOnly         Rebuild and redeploy only the frontend
#   .\deploy\ship.ps1 -Target ubuntu@192.168.1.50 -Update -BackendOnly  Transfer existing archive, restart backend
#   .\deploy\ship.ps1 -Target ubuntu@192.168.1.50 -Update -FrontendOnly Transfer existing archive, restart frontend
#
# Offline AI assistant (Ollama):
#   Add -WithAI to bake the LLM model into the archive. The model is downloaded
#   ONCE on this (internet-connected) build machine; the server needs no internet.
#
#   .\deploy\ship.ps1 -Target ubuntu@192.168.1.50 -WithAI
#   $env:OLLAMA_MODEL="llama3.2:3b"; .\deploy\ship.ps1 -Target ubuntu@192.168.1.50 -WithAI
#
#   Without -WithAI the assistant is not built/shipped; the chat widget shows
#   "offline" and everything else works normally.
#
# On first deploy a legacy SQLite database is auto-migrated to PostgreSQL
# (runs once, before the backend boots; a marker file skips it thereafter).
#
# Authentication (choose one):
#   SSH key (recommended): -SshKey .\path\to\private_key.pem
#   Password auth:         omit -SshKey -- you will be prompted per step
#   PuTTY + password:      place plink.exe + pscp.exe next to this script or
#                          in PATH; use -SshKey for a .ppk key path
#
# Prerequisites:
#   Docker Desktop for Windows (Linux containers)
#     https://docs.docker.com/desktop/install/windows-install/
#   OpenSSH Client (built into Windows 10/11)
#     Settings -> Apps -> Optional Features -> OpenSSH Client
#   OR PuTTY (plink.exe + pscp.exe) for password auth without prompts
#
# If blocked by execution policy, run once:
#   Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
#
# =============================================================================

param(
    [Parameter(Position = 0)]
    [string]$Target = "",

    [string]$SshKey  = "",   # Path to private key (.pem or .ppk for PuTTY)
    [switch]$Setup,          # First time: install Docker on the server
    [switch]$Update,         # Skip rebuild: transfer existing archive + load + start
    [switch]$Start,          # Skip build/transfer: load already-transferred archive + start
    [switch]$Restart,        # Skip build/transfer/load: just docker compose up -d
    [switch]$BuildOnly,      # Build and save images locally, no transfer
    [switch]$Bundle,         # Use Dockerfile.bundle (airgap packages)
    [switch]$Rollback,       # Roll back to the previous deployment
    [switch]$WithAI,         # Embed the offline Ollama AI model in the archive
    [switch]$BackendOnly,    # Rebuild/transfer/restart only the backend service
    [switch]$FrontendOnly    # Rebuild/transfer/restart only the frontend service
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($BackendOnly -and $FrontendOnly) {
    Write-Host "!! -BackendOnly and -FrontendOnly cannot be used together" -ForegroundColor Red
    exit 1
}

# -- Paths --------------------------------------------------------------------
$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$Archive    = Join-Path $ScriptDir "sabc-images.tar"
$RemoteDir  = "/opt/sabc-compliance"

# -- Validate arguments -------------------------------------------------------
if ((-not $Target) -and (-not $BuildOnly) -and (-not $Bundle)) {
    Write-Host "Usage: .\deploy\ship.ps1 -Target user@server [-SshKey key.pem] [-Setup|-Update|-Start|-Restart|-BuildOnly] [-WithAI]"
    exit 1
}

# -- Colour helpers -----------------------------------------------------------
function Info { param($msg) Write-Host ">> $msg" -ForegroundColor Cyan  }
function Ok   { param($msg) Write-Host "OK $msg" -ForegroundColor Green }
function Fail { param($msg) Write-Host "!! $msg" -ForegroundColor Red; exit 1 }
function Warn { param($msg) Write-Host "** $msg" -ForegroundColor Yellow }

# -- Detect SSH/SCP tool ------------------------------------------------------
$UsePlink = $false
$PlinkExe = ""
$PscpExe  = ""

foreach ($p in @($ScriptDir, "C:\Program Files\PuTTY", "C:\PuTTY", "$env:USERPROFILE\Downloads")) {
    $candidate = Join-Path $p "plink.exe"
    if (Test-Path $candidate) {
        $PlinkExe = $candidate
        $candidate2 = Join-Path $p "pscp.exe"
        if (Test-Path $candidate2) { $PscpExe = $candidate2 }
        $UsePlink = $true
        break
    }
}

if (-not $UsePlink) {
    $found = Get-Command "plink.exe" -ErrorAction SilentlyContinue
    if ($null -ne $found) {
        $PlinkExe = $found.Source
        $found2   = Get-Command "pscp.exe" -ErrorAction SilentlyContinue
        if ($null -ne $found2) { $PscpExe = $found2.Source }
        $UsePlink = $true
    }
}

if ($UsePlink) {
    Ok "Using PuTTY: $PlinkExe"
} else {
    if ($null -eq (Get-Command "ssh" -ErrorAction SilentlyContinue)) {
        Fail "No SSH client found. Enable OpenSSH Client in Windows Settings -> Optional Features, or install PuTTY."
    }
    if ($SshKey) {
        Ok "Using OpenSSH with key: $SshKey"
    } else {
        Ok "Using OpenSSH (you will be prompted for the password on each step)"
    }
}

# -- Collect password for PuTTY password-mode ---------------------------------
$SshPassword = ""
if ($Target -and $UsePlink -and (-not $SshKey)) {
    $SecurePass  = Read-Host "SSH password for $Target" -AsSecureString
    $SshPassword = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
                       [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecurePass))
}

# -- Collect sudo password (if the remote user needs one for sudo) -------------
# Leave blank and press Enter if the account has passwordless sudo (NOPASSWD).
$SudoPassword = ""
if ($Target) {
    $SecureSudo  = Read-Host "sudo password for $Target (Enter to skip if NOPASSWD)" -AsSecureString
    $SudoPassword = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
                        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureSudo))
}

# -- SSH helpers --------------------------------------------------------------
function Invoke-Remote {
    param([string]$Cmd)
    if ($UsePlink) {
        if ($SshKey) {
            & $PlinkExe -ssh -i $SshKey -batch -no-antispoof $Target $Cmd
        } else {
            & $PlinkExe -ssh -pw $SshPassword -batch -no-antispoof $Target $Cmd
        }
    } else {
        if ($SshKey) {
            & ssh -o StrictHostKeyChecking=no -i $SshKey $Target $Cmd
        } else {
            & ssh -o StrictHostKeyChecking=no $Target $Cmd
        }
    }
    if ($LASTEXITCODE -ne 0) { Fail "Remote command failed: $Cmd" }
}

# Invoke-Sudo pipes the sudo password via stdin so no TTY is required.
# If SudoPassword is empty (NOPASSWD account) it falls back to plain sudo.
# Pass -AllowFail to return without terminating; caller checks $LASTEXITCODE.
function Invoke-Sudo {
    param([string]$Cmd, [switch]$AllowFail)
    if ($SudoPassword -ne "") {
        $sudoCmd = "echo '$SudoPassword' | sudo -S $Cmd"
    } else {
        $sudoCmd = "sudo $Cmd"
    }
    if ($UsePlink) {
        if ($SshKey) {
            & $PlinkExe -ssh -i $SshKey -batch -no-antispoof $Target $sudoCmd
        } else {
            & $PlinkExe -ssh -pw $SshPassword -batch -no-antispoof $Target $sudoCmd
        }
    } else {
        if ($SshKey) {
            & ssh -o StrictHostKeyChecking=no -i $SshKey $Target $sudoCmd
        } else {
            & ssh -o StrictHostKeyChecking=no $Target $sudoCmd
        }
    }
    if ((-not $AllowFail) -and ($LASTEXITCODE -ne 0)) { Fail "Remote sudo command failed: $Cmd" }
}

function Send-File {
    param([string]$LocalPath, [string]$RemotePath)
    Info "Transferring $(Split-Path -Leaf $LocalPath) ..."
    if ($UsePlink -and $PscpExe) {
        if ($SshKey) {
            & $PscpExe -i $SshKey -batch "$LocalPath" "${Target}:${RemotePath}"
        } else {
            & $PscpExe -pw $SshPassword -batch "$LocalPath" "${Target}:${RemotePath}"
        }
    } else {
        if ($SshKey) {
            & scp -o StrictHostKeyChecking=no -i $SshKey -C "$LocalPath" "${Target}:${RemotePath}"
        } else {
            & scp -o StrictHostKeyChecking=no -C "$LocalPath" "${Target}:${RemotePath}"
        }
    }
    if ($LASTEXITCODE -ne 0) { Fail "Transfer failed: $LocalPath" }
}

# -- Step 1: Build images -----------------------------------------------------
function Build-Images {
    Info "Building Docker images for linux/amd64 ..."
    Push-Location $ProjectDir
    try {
        # Write each image straight to a docker-archive tar with
        # `docker buildx build --output type=docker,dest=...` instead of building
        # into the local image store and then running `docker save`.
        #
        # Why: on Docker Desktop the containerd image store keeps the layers of a
        # buildx cross-platform (--platform linux/amd64) build out of the classic
        # store, so `docker save` -- and even `--load` followed by `docker save` --
        # fails with:
        #   unable to create manifests file: NotFound: content digest sha256:...: not found
        # --output type=docker,dest=FILE exports the finished image as a fully
        # self-contained, `docker load`-able archive directly from the build, so we
        # never touch the broken save path at all.  docker-compose.yml has no build:
        # contexts (those live only in docker-compose.dev.yml for local dev).
        $stage = Join-Path $ScriptDir ".images"
        if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
        New-Item -ItemType Directory -Force -Path $stage | Out-Null

        if (-not $FrontendOnly) {
            if ($Bundle) {
                # docker-compose.yml references :latest, so tag the bundled (airgap-
                # packages) image :latest -- otherwise the loaded image never matches
                # the compose file and the backend fails with "image not found".
                Info "Building bundled backend image (airgap packages) ..."
                & docker buildx build --platform linux/amd64 -f backend/Dockerfile.bundle -t sabc-compliance-backend:latest --output "type=docker,dest=$stage\backend.tar" backend/
                if ($LASTEXITCODE -ne 0) { Fail "Bundle build failed" }
            } else {
                Info "Building backend image ..."
                & docker buildx build --platform linux/amd64 -t sabc-compliance-backend:latest --output "type=docker,dest=$stage\backend.tar" ./backend
                if ($LASTEXITCODE -ne 0) { Fail "Backend build failed" }
            }
        }

        if (-not $BackendOnly) {
            Info "Building frontend image ..."
            & docker buildx build --platform linux/amd64 --build-arg "VITE_API_BASE=/api" -t sabc-compliance-frontend:latest --output "type=docker,dest=$stage\frontend.tar" ./frontend
            if ($LASTEXITCODE -ne 0) { Fail "Frontend build failed" }
        }

        # Ollama image with the LLM model baked in — only when -WithAI was passed
        # and this is not a frontend-only update (Ollama is used by the backend).
        if ($WithAI -and (-not $FrontendOnly)) {
            $ollamaModel = if ($env:OLLAMA_MODEL) { $env:OLLAMA_MODEL } else { "llama3.2:1b" }
            Info "Building Ollama image with embedded model '$ollamaModel' (downloading on this build machine) ..."
            & docker buildx build --platform linux/amd64 `
                --build-arg "OLLAMA_MODEL=$ollamaModel" `
                -t sabc-ollama:latest `
                --output "type=docker,dest=$stage\ollama.tar" deploy/ollama
            if ($LASTEXITCODE -ne 0) { Fail "Ollama image build failed" }
        } elseif (-not $FrontendOnly) {
            Info "Skipping offline AI assistant (pass -WithAI to embed it)."
        }

        # postgres is only needed for full deploys — for partial updates the
        # database container is already running and must not be replaced.
        if ((-not $BackendOnly) -and (-not $FrontendOnly)) {
            Info "Packaging postgres:16-alpine for linux/amd64 ..."
            $pgctx = Join-Path $stage "pgctx"
            New-Item -ItemType Directory -Force -Path $pgctx | Out-Null
            Set-Content -Path (Join-Path $pgctx "Dockerfile") -Value "FROM postgres:16-alpine" -Encoding ASCII
            & docker buildx build --platform linux/amd64 -t postgres:16-alpine --output "type=docker,dest=$stage\postgres.tar" $pgctx
            if ($LASTEXITCODE -ne 0) { Fail "postgres packaging failed" }
            Remove-Item -Recurse -Force $pgctx -ErrorAction SilentlyContinue
        }
    } finally {
        Pop-Location
    }
    Ok "Image archives built (linux/amd64)"
}

# -- Step 2: Save images to tar -----------------------------------------------
function Save-Images {
    Info "Saving images to $Archive ..."
    # Build-Images already exported each image as a self-contained, loadable
    # docker-archive tar under .images.  Bundle the relevant per-image tars into
    # the single archive the pipeline ships.  For partial deploys only the
    # updated image is included — postgres is omitted to avoid reloading it.
    $stage = Join-Path $ScriptDir ".images"
    $imageTars = @()
    if (-not $FrontendOnly) { $imageTars += "backend.tar" }
    if (-not $BackendOnly)  { $imageTars += "frontend.tar" }
    if ((-not $BackendOnly) -and (-not $FrontendOnly)) {
        $imageTars += "postgres.tar"
        if (Test-Path (Join-Path $stage "ollama.tar")) { $imageTars += "ollama.tar" }
    }
    & tar -cf $Archive -C $stage @imageTars
    if ($LASTEXITCODE -ne 0) { Fail "Bundling image archive failed" }
    Remove-Item -Recurse -Force $stage -ErrorAction SilentlyContinue

    $sizeMB = [math]::Round((Get-Item $Archive).Length / 1MB)
    Ok "Archive ready: $Archive (${sizeMB} MB)"
    Warn "Tip: scp -C will compress during transfer -- no gzip needed on Windows."
}

# -- Step 3: Install Docker on server (first time only) -----------------------
function Setup-Server {
    Info "Installing Docker on $Target ..."

    # Write the setup script to a temp file and pipe it over SSH
    $tmpScript = [System.IO.Path]::GetTempFileName() + ".sh"
    $lines = @(
        "set -e",
        "if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then",
        "  echo 'Docker already installed:' `$(docker --version)",
        "  exit 0",
        "fi",
        ". /etc/os-release",
        "case `"`$ID`" in",
        "  ubuntu|debian)",
        "    export DEBIAN_FRONTEND=noninteractive",
        "    apt-get update -qq",
        "    apt-get install -y -qq ca-certificates curl gnupg lsb-release",
        "    install -m 0755 -d /etc/apt/keyrings",
        "    curl -fsSL `"https://download.docker.com/linux/`$ID/gpg`" | gpg --dearmor -o /etc/apt/keyrings/docker.gpg",
        "    chmod a+r /etc/apt/keyrings/docker.gpg",
        "    echo `"deb [arch=`$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/`$ID `$(lsb_release -cs) stable`" > /etc/apt/sources.list.d/docker.list",
        "    apt-get update -qq",
        "    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin",
        "    ;;",
        "  rhel|centos|fedora|amzn)",
        "    yum install -y docker",
        "    systemctl enable docker",
        "    systemctl start docker",
        "    COMPOSE_VER=`$(curl -sSL https://api.github.com/repos/docker/compose/releases/latest | grep tag_name | cut -d'`"' -f4)",
        "    mkdir -p /usr/local/lib/docker/cli-plugins",
        "    curl -sSL `"https://github.com/docker/compose/releases/download/`${COMPOSE_VER}/docker-compose-`$(uname -s)-`$(uname -m)`" -o /usr/local/lib/docker/cli-plugins/docker-compose",
        "    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose",
        "    ;;",
        "  *) echo `"Unsupported OS: `$ID`"; exit 1 ;;",
        "esac",
        "systemctl enable docker",
        "systemctl start docker",
        "echo `"Done: `$(docker --version) / `$(docker compose version)`"",
        'exit 0'
    )
    # Feed the script to the remote over stdin. When a sudo password is set we
    # prepend it as the very first line: "sudo -S" reads exactly that one line
    # for authentication and leaves the remainder of stdin for "bash -s" to
    # execute.
    #
    # WriteAllText with explicit LF (\n) separators writes a LF-only file --
    # Set-Content -Encoding ASCII on Windows produces CRLF which bash rejects
    # with "set: -" / "syntax error near unexpected token 'do\r'".
    # Get-Content -Raw reads the whole file as ONE string so PowerShell does NOT
    # re-add \r\n between lines when writing to the SSH stdin pipe.
    if ($SudoPassword -ne "") {
        $sudoSetup = "sudo -S bash -s"
        $scriptContent = ((@($SudoPassword) + $lines) -join "`n") + "`n"
    } else {
        $sudoSetup = "sudo bash -s"
        $scriptContent = ($lines -join "`n") + "`n"
    }
    [System.IO.File]::WriteAllText($tmpScript, $scriptContent.Replace("`r", ""), [System.Text.Encoding]::ASCII)
    if ($UsePlink) {
        if ($SshKey) {
            Get-Content -Raw $tmpScript | & $PlinkExe -ssh -i $SshKey -batch $Target $sudoSetup
        } else {
            Get-Content -Raw $tmpScript | & $PlinkExe -ssh -pw $SshPassword -batch $Target $sudoSetup
        }
    } else {
        if ($SshKey) {
            Get-Content -Raw $tmpScript | & ssh -o StrictHostKeyChecking=no -i $SshKey $Target $sudoSetup
        } else {
            Get-Content -Raw $tmpScript | & ssh -o StrictHostKeyChecking=no $Target $sudoSetup
        }
    }
    Remove-Item $tmpScript -ErrorAction SilentlyContinue
    if ($LASTEXITCODE -ne 0) { Fail "Docker installation failed on $Target" }
    Ok "Docker ready on $Target"
}

# -- Step 3b: Snapshot current deployment for rollback -----------------------
# Tags existing backend/frontend images as :rollback and backs up the remote
# compose + .env files before new files are transferred.  No-op on first deploy.
function Invoke-Snapshot {
    Info "Snapshotting current deployment for rollback ..."
    $lines = @(
        'set -e',
        "rd=`"$RemoteDir`"",
        'snapped=0',
        'for img in sabc-compliance-backend:latest sabc-compliance-frontend:latest; do',
        '  name="${img%%:*}"',
        '  if docker image inspect "$img" >/dev/null 2>&1; then',
        '    docker tag "$img" "${name}:rollback"',
        '    echo "[snapshot] $img -> ${name}:rollback"',
        '    snapped=$((snapped + 1))',
        '  fi',
        'done',
        '[ -f "$rd/docker-compose.yml" ] && cp -f "$rd/docker-compose.yml" "$rd/docker-compose.yml.rollback"',
        '[ -f "$rd/.env" ]               && cp -f "$rd/.env"               "$rd/.env.rollback"',
        'if [ "$snapped" -gt 0 ]; then',
        '  echo "[snapshot] Rollback snapshot ready (${snapped} image(s) tagged)."',
        'else',
        '  echo "[snapshot] No previous images found -- rollback will not be available after this deploy."',
        'fi',
        'exit 0'
    )
    $tmpScript = [System.IO.Path]::GetTempFileName() + ".sh"
    if ($SudoPassword -ne "") {
        $sudoCmd = "sudo -S bash -s"
        $scriptContent = ((@($SudoPassword) + $lines) -join "`n") + "`n"
    } else {
        $sudoCmd = "sudo bash -s"
        $scriptContent = ($lines -join "`n") + "`n"
    }
    [System.IO.File]::WriteAllText($tmpScript, $scriptContent.Replace("`r", ""), [System.Text.Encoding]::ASCII)
    if ($UsePlink) {
        if ($SshKey) { Get-Content -Raw $tmpScript | & $PlinkExe -ssh -i $SshKey -batch $Target $sudoCmd }
        else         { Get-Content -Raw $tmpScript | & $PlinkExe -ssh -pw $SshPassword -batch $Target $sudoCmd }
    } else {
        if ($SshKey) { Get-Content -Raw $tmpScript | & ssh -o StrictHostKeyChecking=no -i $SshKey $Target $sudoCmd }
        else         { Get-Content -Raw $tmpScript | & ssh -o StrictHostKeyChecking=no $Target $sudoCmd }
    }
    Remove-Item $tmpScript -ErrorAction SilentlyContinue
    # Snapshot failures are non-fatal: the deploy can proceed without a rollback baseline.
    if ($LASTEXITCODE -ne 0) { Warn "Snapshot step returned non-zero -- rollback may not be available." }
}

# -- Step 3c: Rollback to previous snapshot -----------------------------------
# Restores :rollback images and the backed-up compose/.env, then restarts.
# Pass -AllowFail to suppress the terminal Fail call (used inside Start-Containers).
function Invoke-Rollback {
    param([switch]$AllowFail)
    Warn "Rolling back to previous deployment ..."
    $lines = @(
        'set -e',
        "rd=`"$RemoteDir`"",
        'if docker compose version >/dev/null 2>&1; then _bin="docker compose"; else _bin="docker-compose"; fi',
        'COMPOSE="$_bin -f $rd/docker-compose.yml --project-directory $rd"',
        '$COMPOSE down --remove-orphans 2>/dev/null || true',
        'docker rm -f sabc-frontend sabc-backend sabc-postgres 2>/dev/null || true',
        'if [ -f "$rd/docker-compose.yml.rollback" ]; then',
        '  cp -f "$rd/docker-compose.yml.rollback" "$rd/docker-compose.yml"',
        '  echo "[rollback] docker-compose.yml restored"',
        'else',
        '  echo "[rollback] WARNING: no docker-compose.yml.rollback -- using current file"',
        'fi',
        'if [ -f "$rd/.env.rollback" ]; then',
        '  cp -f "$rd/.env.rollback" "$rd/.env"',
        '  echo "[rollback] .env restored"',
        'fi',
        'rolled=0',
        'for name in sabc-compliance-backend sabc-compliance-frontend; do',
        '  if docker image inspect "${name}:rollback" >/dev/null 2>&1; then',
        '    docker tag "${name}:rollback" "${name}:latest"',
        '    echo "[rollback] Restored ${name}:latest from :rollback"',
        '    rolled=$((rolled + 1))',
        '  fi',
        'done',
        'if [ "$rolled" -eq 0 ]; then',
        '  echo "[rollback] ERROR: no rollback images found -- cannot restore previous version."',
        '  exit 1',
        'fi',
        '$COMPOSE up -d --no-build',
        'echo "[rollback] Previous deployment successfully restored."',
        'exit 0'
    )
    $tmpScript = [System.IO.Path]::GetTempFileName() + ".sh"
    if ($SudoPassword -ne "") {
        $sudoCmd = "sudo -S bash -s"
        $scriptContent = ((@($SudoPassword) + $lines) -join "`n") + "`n"
    } else {
        $sudoCmd = "sudo bash -s"
        $scriptContent = ($lines -join "`n") + "`n"
    }
    [System.IO.File]::WriteAllText($tmpScript, $scriptContent.Replace("`r", ""), [System.Text.Encoding]::ASCII)
    if ($UsePlink) {
        if ($SshKey) { Get-Content -Raw $tmpScript | & $PlinkExe -ssh -i $SshKey -batch $Target $sudoCmd }
        else         { Get-Content -Raw $tmpScript | & $PlinkExe -ssh -pw $SshPassword -batch $Target $sudoCmd }
    } else {
        if ($SshKey) { Get-Content -Raw $tmpScript | & ssh -o StrictHostKeyChecking=no -i $SshKey $Target $sudoCmd }
        else         { Get-Content -Raw $tmpScript | & ssh -o StrictHostKeyChecking=no $Target $sudoCmd }
    }
    $rbExit = $LASTEXITCODE
    Remove-Item $tmpScript -ErrorAction SilentlyContinue
    if ($rbExit -ne 0) {
        if (-not $AllowFail) { Fail "Rollback failed -- manual intervention required (check docker logs on $Target)" }
        Warn "Rollback failed -- manual intervention may be required."
    } else {
        Ok "Rollback complete -- previous version is running."
    }
}

# -- Step 4: Transfer files ---------------------------------------------------
function Transfer-Files {
    Info "Creating remote directory $RemoteDir ..."
    Invoke-Sudo "mkdir -p $RemoteDir"
    # Use id -un/-gn (resolved on the remote, as the login user) so this works
    # even when the primary group name differs from the username -- common on
    # AD-joined or corporate Linux hosts where chown user:user would fail.
    Invoke-Sudo "chown `$(id -un):`$(id -gn) $RemoteDir"

    Send-File $Archive "$RemoteDir/sabc-images.tar"
    Send-File (Join-Path $ProjectDir "docker-compose.yml") "$RemoteDir/docker-compose.yml"

    $envFile = Join-Path $ProjectDir ".env"
    if (Test-Path $envFile) {
        Send-File $envFile "$RemoteDir/.env"
    } else {
        # Write a minimal default .env locally, ship it, then delete the temp
        Warn "No .env found -- writing default on server (HTTPS_PORT=8443)"
        $tmpEnv = [System.IO.Path]::GetTempFileName()
        @(
            "HTTPS_PORT=8443",
            "BACKEND_PORT=3000",
            "HOST_IP=",
            "HOST_ADMIN_USER="
        ) | Set-Content -Path $tmpEnv -Encoding ASCII
        Send-File $tmpEnv "$RemoteDir/.env"
        Remove-Item $tmpEnv -ErrorAction SilentlyContinue
    }

    Invoke-Sudo "mkdir -p $RemoteDir/backend/packages"
    Invoke-Sudo "chown -R `$(id -un):`$(id -gn) $RemoteDir"
    Ok "Files transferred"
}

# -- Helpers: display the URL after any successful deploy ---------------------
function Show-URLs {
    if ($Target -match "@") { $displayHost = $Target.Split("@")[1] } else { $displayHost = $Target }
    $httpsPort = "8443"
    $envFile = Join-Path $ProjectDir ".env"
    if (Test-Path $envFile) {
        $portLine = Get-Content $envFile | Where-Object { $_ -match "^HTTPS_PORT=" }
        if ($portLine) { $httpsPort = $portLine.Split("=")[1].Trim() }
    }
    Ok "Platform running!"
    Write-Host ""
    Write-Host "======================================================" -ForegroundColor Cyan
    Write-Host "  SABC Compliance Platform" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  UI:      https://${displayHost}:${httpsPort}" -ForegroundColor White
    Write-Host "  API:     https://${displayHost}:${httpsPort}/api" -ForegroundColor White
    Write-Host "  Swagger: http://${displayHost}:3000/docs" -ForegroundColor White
    Write-Host ""
    Write-Host "  Status: ssh $Target sudo docker ps" -ForegroundColor DarkGray
    Write-Host "  Logs:   ssh $Target sudo docker logs -f sabc-backend   (or sabc-frontend)" -ForegroundColor DarkGray
    Write-Host "  Stop:   ssh $Target sudo docker-compose -f $RemoteDir/docker-compose.yml down" -ForegroundColor DarkGray
    Write-Host "  Note:   'docker-compose logs -f' may print a harmless KeyError: 'id' on v1;" -ForegroundColor DarkGray
    Write-Host "          per-container 'docker logs' above avoids it." -ForegroundColor DarkGray
    Write-Host "======================================================" -ForegroundColor Cyan
    Write-Host ""
}

# Detect whether the server has the compose plugin (docker compose) or the
# standalone binary (docker-compose) and return the right invocation.
# Run "docker compose version" and check $LASTEXITCODE (0 = plugin).
# ErrorActionPreference is set to Stop globally, so we suppress it here:
# a non-zero exit from the probe is expected when only v1 is installed.
function Get-ComposeCmd {
    $savedEap = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try {
        $null = if ($UsePlink) {
            if ($SshKey) { & $PlinkExe -ssh -i $SshKey -batch $Target "docker compose version" 2>&1 }
            else         { & $PlinkExe -ssh -pw $SshPassword -batch $Target "docker compose version" 2>&1 }
        } else {
            if ($SshKey) { & ssh -o StrictHostKeyChecking=no -i $SshKey $Target "docker compose version" 2>&1 }
            else         { & ssh -o StrictHostKeyChecking=no $Target "docker compose version" 2>&1 }
        }
    } catch { }
    $ErrorActionPreference = $savedEap
    if ($LASTEXITCODE -eq 0) {
        Ok "Docker Compose: plugin (docker compose)"
        return "docker compose"
    } else {
        Ok "Docker Compose: standalone (docker-compose)"
        return "docker-compose"
    }
}

# -- Step 5a: Start containers (compose up only -- images already loaded) -----
function Start-Containers {
    Info "Starting platform (PostgreSQL first, auto-migrating if needed) ..."
    $compose = Get-ComposeCmd

    # The start sequence is written to a temp .sh and piped over SSH under ONE
    # sudo invocation (same proven pattern as Setup-Server). We use a script
    # file rather than inlining bash -c '...' because the migration step needs
    # its own nested single quotes, which would collide with PowerShell/SSH
    # quoting if inlined.
    #
    # "down" removes this compose project's containers by their project labels
    # (reliable even when docker-compose 1.29.2 assigned a prefixed name), and
    # we also force-remove our fixed-name sabc-frontend/sabc-backend so a stale
    # container from an earlier run can't keep holding its published ports.
    # Only our own named containers are ever touched.
    #
    # Order matters: PostgreSQL comes up ALONE and the one-shot SQLite ->
    # PostgreSQL migration runs BEFORE the backend boots. The backend seeds
    # default users/groups into an empty DB on first start, which would
    # otherwise make the idempotent migration skip those tables and strand the
    # real SQLite data. A marker file makes the migration a no-op on later runs.
    $composePrefix = "$compose -f $RemoteDir/docker-compose.yml --project-directory $RemoteDir"
    $lines = @(
        'set -e',
        '# Enable the "ai" profile only when the Ollama image is actually loaded.',
        'PROFILE=""',
        'if docker image inspect sabc-ollama:latest >/dev/null 2>&1; then',
        '  PROFILE="--profile ai"',
        '  echo "[ship] sabc-ollama image present -- enabling offline AI assistant."',
        'fi',
        "COMPOSE=`"$composePrefix `$PROFILE`"",
        "COMPOSE_FILE=`"$RemoteDir/docker-compose.yml`"",
        '# Guard: docker-compose v1 mis-handles image-only services when the file',
        '# still declares build: contexts -- it silently skips them and STILL exits 0,',
        '# so the deploy looks successful while only postgres actually starts.',
        '# Abort early with an actionable message instead of a false success.',
        'if grep -qE "^[[:space:]]*build:" "$COMPOSE_FILE"; then',
        '  echo "[ship] FATAL: $COMPOSE_FILE still contains build: directives."',
        '  echo "[ship] This server runs docker-compose v1, which cannot start the"',
        '  echo "[ship] pre-built image services from a file that has build: contexts."',
        '  echo "[ship] Re-run with -Update (Windows) / --update (Linux) so the"',
        '  echo "[ship] corrected docker-compose.yml is transferred to the server."',
        '  exit 2',
        'fi',
        '$COMPOSE down --remove-orphans 2>/dev/null || true',
        'docker rm -f sabc-frontend sabc-backend sabc-postgres 2>/dev/null || true',
        '# 1) Bring the WHOLE stack up in one shot -- the same single "up -d" the',
        '#    proven manual deploy uses. Drops the old "compose run --rm" migration',
        '#    step, the ephemeral-container subcommand that misbehaves on v1.',
        '$COMPOSE up -d',
        '# 2) Wait for PostgreSQL to report healthy so the migration can connect.',
        'echo "Waiting for PostgreSQL to become healthy ..."',
        'for i in $(seq 1 30); do',
        '  s=$(docker inspect -f "{{.State.Health.Status}}" sabc-postgres 2>/dev/null || echo starting)',
        '  [ "$s" = "healthy" ] && break',
        '  sleep 2',
        'done',
        '# 3) Verify the stack is REALLY up. docker-compose v1 can return 0 without',
        '#    creating a service, so check real container state, not the exit code.',
        'sleep 15',
        'missing=""',
        'for c in sabc-postgres sabc-backend sabc-frontend; do',
        '  st=$(docker inspect -f "{{.State.Status}}" "$c" 2>/dev/null || echo absent)',
        '  echo "[ship] container $c: $st"',
        '  [ "$st" = "running" ] || missing="$missing $c"',
        'done',
        'if [ -n "$missing" ]; then',
        '  echo "[ship] ERROR: these containers are not running:$missing"',
        '  echo "[ship] ---------- docker ps -a ----------"',
        '  docker ps -a',
        '  for c in $missing; do',
        '    echo "[ship] ---------- last 40 log lines: $c ----------"',
        '    docker logs --tail 40 "$c" 2>&1 || echo "[ship] (container $c was never created)"',
        '  done',
        '  exit 1',
        'fi',
        'echo "[ship] All containers running: postgres, backend, frontend."',
        'exit 0'
    )

    # Pipe the script to the server. When a sudo password is set, prepend it as
    # the first stdin line: "sudo -S" consumes exactly that line for auth and
    # leaves the rest for "bash -s".
    #
    # WriteAllText with explicit LF (\n) separators writes a LF-only file --
    # Set-Content -Encoding ASCII on Windows produces CRLF which bash rejects
    # with "set: -" / "syntax error near unexpected token 'do\r'".
    # Get-Content -Raw reads the whole file as ONE string so PowerShell does NOT
    # re-add \r\n between lines when writing to the SSH stdin pipe.
    $tmpScript = [System.IO.Path]::GetTempFileName() + ".sh"
    if ($SudoPassword -ne "") {
        $sudoStart = "sudo -S bash -s"
        $scriptContent = ((@($SudoPassword) + $lines) -join "`n") + "`n"
    } else {
        $sudoStart = "sudo bash -s"
        $scriptContent = ($lines -join "`n") + "`n"
    }
    [System.IO.File]::WriteAllText($tmpScript, $scriptContent.Replace("`r", ""), [System.Text.Encoding]::ASCII)

    if ($UsePlink) {
        if ($SshKey) {
            Get-Content -Raw $tmpScript | & $PlinkExe -ssh -i $SshKey -batch $Target $sudoStart
        } else {
            Get-Content -Raw $tmpScript | & $PlinkExe -ssh -pw $SshPassword -batch $Target $sudoStart
        }
    } else {
        if ($SshKey) {
            Get-Content -Raw $tmpScript | & ssh -o StrictHostKeyChecking=no -i $SshKey $Target $sudoStart
        } else {
            Get-Content -Raw $tmpScript | & ssh -o StrictHostKeyChecking=no $Target $sudoStart
        }
    }
    $startExit = $LASTEXITCODE
    Remove-Item $tmpScript -ErrorAction SilentlyContinue

    # On failure print the backend log, then roll back automatically.
    if ($startExit -ne 0) {
        Warn "Startup/migration failed -- showing backend logs for diagnosis:"
        Invoke-Sudo "docker logs --tail 60 sabc-backend 2>&1 || true" -AllowFail
        Warn "Initiating automatic rollback to previous version ..."
        Invoke-Rollback -AllowFail
        Fail "Deployment failed -- automatically rolled back to previous version (see logs above)"
    }

    Show-URLs
}

# -- Step 5b: Load images then start ------------------------------------------
function Deploy-Platform {
    Info "Loading Docker images on $Target ..."
    # sabc-images.tar bundles per-image docker-archive tars (backend.tar,
    # frontend.tar, postgres.tar -- see Build-Images). Extract to a temp dir and
    # load each. No single/double-quote nesting in the bash body so it survives
    # PowerShell -> plink/ssh argument quoting; backtick-$ passes vars to the
    # remote shell, $RemoteDir expands locally.
    $loadCmd = "bash -c 'set -e; d=`$(mktemp -d); tar -xf $RemoteDir/sabc-images.tar -C `$d; for f in `$d/*.tar; do docker load -i `$f; done; rm -rf `$d'"
    Invoke-Sudo $loadCmd -AllowFail
    if ($LASTEXITCODE -ne 0) {
        Warn "Image load failed -- initiating automatic rollback ..."
        Invoke-Rollback -AllowFail
        Fail "Deployment failed during image load -- automatically rolled back to previous version"
    }
    Start-Containers
}

# -- Partial service deploy ---------------------------------------------------
# Loads the transferred image archive and restarts ONE compose service without
# touching postgres or any other running container.
function Deploy-Service {
    param([string]$Svc)   # compose service name: "backend" or "frontend"
    $Ctr = "sabc-$Svc"

    Info "Loading $Svc image on $Target ..."
    $loadCmd = "bash -c 'set -e; d=`$(mktemp -d); tar -xf $RemoteDir/sabc-images.tar -C `$d; for f in `$d/*.tar; do docker load -i `$f; done; rm -rf `$d'"
    Invoke-Sudo $loadCmd -AllowFail
    if ($LASTEXITCODE -ne 0) { Fail "$Svc image load failed" }

    Info "Restarting $Svc container (keeping all other services running) ..."
    $compose = Get-ComposeCmd
    $composePrefix = "$compose -f $RemoteDir/docker-compose.yml --project-directory $RemoteDir"
    $lines = @(
        'set -e',
        'PROFILE=""',
        'if docker image inspect sabc-ollama:latest >/dev/null 2>&1; then PROFILE="--profile ai"; fi',
        "COMPOSE=`"$composePrefix `$PROFILE`"",
        "`$COMPOSE up -d --no-deps $Svc",
        'sleep 8',
        "st=`$(docker inspect -f '{{.State.Status}}' $Ctr 2>/dev/null || echo absent)",
        "if [ `"`$st`" != `"running`" ]; then",
        "  echo `"[ship] ERROR: $Ctr is not running (status: `$st)`"",
        "  docker logs --tail 40 $Ctr 2>&1 || true",
        '  exit 1',
        'fi',
        "echo `"[ship] $Ctr is running.`"",
        'exit 0'
    )
    $tmpScript = [System.IO.Path]::GetTempFileName() + ".sh"
    if ($SudoPassword -ne "") {
        $sudoCmd = "sudo -S bash -s"
        $scriptContent = ((@($SudoPassword) + $lines) -join "`n") + "`n"
    } else {
        $sudoCmd = "sudo bash -s"
        $scriptContent = ($lines -join "`n") + "`n"
    }
    [System.IO.File]::WriteAllText($tmpScript, $scriptContent.Replace("`r", ""), [System.Text.Encoding]::ASCII)
    if ($UsePlink) {
        if ($SshKey) { Get-Content -Raw $tmpScript | & $PlinkExe -ssh -i $SshKey -batch $Target $sudoCmd }
        else         { Get-Content -Raw $tmpScript | & $PlinkExe -ssh -pw $SshPassword -batch $Target $sudoCmd }
    } else {
        if ($SshKey) { Get-Content -Raw $tmpScript | & ssh -o StrictHostKeyChecking=no -i $SshKey $Target $sudoCmd }
        else         { Get-Content -Raw $tmpScript | & ssh -o StrictHostKeyChecking=no $Target $sudoCmd }
    }
    $svcExit = $LASTEXITCODE
    Remove-Item $tmpScript -ErrorAction SilentlyContinue
    if ($svcExit -ne 0) { Fail "$Svc deployment failed -- check logs above" }
    Ok "$Svc updated and running!"
    Show-URLs
}

# -- Main ---------------------------------------------------------------------
#
#  Flag summary:
#    (none)       Full deploy: build -> save -> transfer -> load -> start
#    -Setup       Install Docker on server first, then full deploy
#    -Update      Images already saved locally  -> transfer -> load -> start
#    -Start       Files already on server       -> load -> start
#    -Restart     Images already loaded         -> docker compose up -d only
#    -BuildOnly   Build and save locally, print manual instructions
#    -BackendOnly Build/transfer/restart only the backend
#    -FrontendOnly Build/transfer/restart only the frontend
#

# -- Partial deploy: -BackendOnly / -FrontendOnly -----------------------------
if ($BackendOnly -or $FrontendOnly) {
    $svc = if ($BackendOnly) { "backend" } else { "frontend" }

    if ($Rollback) { Invoke-Rollback; exit 0 }

    if ($Restart) {
        Info "Restarting $svc on $Target (image already loaded) ..."
        Deploy-Service $svc
        exit 0
    }

    if ($Start) {
        Info "Loading and starting $svc on $Target (archive already transferred) ..."
        Deploy-Service $svc
        exit 0
    }

    if ($Update) {
        if (-not (Test-Path $Archive)) { Fail "No archive at $Archive -- run without -Update first to build." }
        Transfer-Files
        Deploy-Service $svc
        exit 0
    }

    if ($Setup) { Setup-Server }
    Build-Images
    Save-Images
    Transfer-Files
    Deploy-Service $svc
    exit 0
}

if ($BuildOnly -or $Bundle) {
    Build-Images
    Save-Images
    Write-Host ""
    Info "Archive at: $Archive"
    Info "Transfer manually (WinSCP or pscp), then on the server run:"
    Info "  .\deploy\ship.ps1 -Target user@server -Start"
    exit 0
}

if ($Rollback) {
    Invoke-Rollback
    exit 0
}

if ($Restart) {
    Info "Restarting containers on $Target (images already loaded) ..."
    Invoke-Snapshot
    Start-Containers
    exit 0
}

if ($Start) {
    Info "Loading and starting on $Target (files already transferred) ..."
    Invoke-Snapshot
    Deploy-Platform
    exit 0
}

if ($Update) {
    if (-not (Test-Path $Archive)) {
        Fail "No archive at $Archive -- run without -Update first to build."
    }
    Invoke-Snapshot
    Transfer-Files
    Deploy-Platform
    exit 0
}

# Full deploy
if ($Setup) { Setup-Server }
Build-Images
Save-Images
Invoke-Snapshot
Transfer-Files
Deploy-Platform
