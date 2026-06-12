#Requires -Version 5.1
# ═══════════════════════════════════════════════════════════════════════════════
# SABC Compliance Platform — Windows Deployment Script (PowerShell)
# ═══════════════════════════════════════════════════════════════════════════════
#
# Usage:
#   .\deploy\ship.ps1 -Target ubuntu@<server-ip>
#   .\deploy\ship.ps1 -Target ubuntu@<server-ip> -SshKey .\keys\id_rsa
#   .\deploy\ship.ps1 -Target ubuntu@<server-ip> -Setup        # First time: installs Docker
#   .\deploy\ship.ps1 -Target ubuntu@<server-ip> -Update       # Re-transfer without rebuild
#   .\deploy\ship.ps1 -BuildOnly                               # Build & save locally only
#
# Authentication (choose one):
#   SSH key (recommended):  -SshKey .\path\to\private_key
#   Password (interactive): omit -SshKey — the system will prompt per command
#   PuTTY + password:       place plink.exe + pscp.exe next to this script or
#                           in PATH and use -SshKey for the .ppk path
#
# Prerequisites:
#   - Docker Desktop for Windows (Linux containers)  https://docs.docker.com/desktop/install/windows-install/
#   - OpenSSH Client (Windows 10/11: Settings → Apps → Optional Features)
#     OR PuTTY (plink.exe + pscp.exe) for password auth without prompts
#
# Run policy — if blocked, run once:
#   Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
#
# ═══════════════════════════════════════════════════════════════════════════════

param(
    [Parameter(Position = 0)]
    [string]$Target = "",

    [string]$SshKey = "",      # Path to private key (.pem or .ppk for PuTTY)
    [switch]$Setup,            # First-time: install Docker on the server
    [switch]$Update,           # Skip build, just transfer the existing archive
    [switch]$BuildOnly,        # Build and save images locally only (no transfer)
    [switch]$Bundle            # Include airgap packages (Dockerfile.bundle)
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Paths ─────────────────────────────────────────────────────────────────────
$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$Archive    = Join-Path $ScriptDir "sabc-images.tar"
$RemoteDir  = "/opt/sabc-compliance"

# ── Validate arguments ─────────────────────────────────────────────────────────
if (-not $Target -and -not $BuildOnly -and -not $Bundle) {
    Write-Host "Usage: .\deploy\ship.ps1 -Target user@server-ip [-SshKey key.pem] [-Setup|-Update|-BuildOnly]"
    exit 1
}

# ── Colour helpers ─────────────────────────────────────────────────────────────
function Info { param($msg) Write-Host ">> $msg" -ForegroundColor Cyan    }
function Ok   { param($msg) Write-Host "OK $msg" -ForegroundColor Green   }
function Fail { param($msg) Write-Host "!! $msg" -ForegroundColor Red; exit 1 }
function Warn { param($msg) Write-Host "** $msg" -ForegroundColor Yellow  }

# ── Detect SSH/SCP tool ────────────────────────────────────────────────────────
$UsePlink = $false
$PlinkExe = ""
$PscpExe  = ""

foreach ($p in @($ScriptDir, "C:\Program Files\PuTTY", "C:\PuTTY", "$env:USERPROFILE\Downloads")) {
    if (Test-Path (Join-Path $p "plink.exe")) {
        $PlinkExe = Join-Path $p "plink.exe"
        $PscpExe  = Join-Path $p "pscp.exe"
        $UsePlink = $true
        break
    }
}
if (-not $UsePlink) {
    $found = Get-Command "plink.exe" -ErrorAction SilentlyContinue
    if ($found) {
        $PlinkExe = $found.Source
        $PscpExe  = (Get-Command "pscp.exe" -ErrorAction SilentlyContinue)?.Source
        $UsePlink = $true
    }
}

if ($UsePlink) {
    Ok "Using PuTTY: $PlinkExe"
} else {
    if (-not (Get-Command "ssh" -ErrorAction SilentlyContinue)) {
        Fail "No SSH client found. Enable OpenSSH Client in Windows Settings → Optional Features, or install PuTTY."
    }
    if ($SshKey) { Ok "Using OpenSSH with key: $SshKey" } else { Ok "Using OpenSSH (will prompt for password each step)" }
}

# ── Collect password for PuTTY password-mode ───────────────────────────────────
$SshPassword = ""
if ($Target -and $UsePlink -and -not $SshKey) {
    $SecurePass  = Read-Host "SSH password for $Target" -AsSecureString
    $SshPassword = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
                       [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecurePass))
}

# ── SSH helpers ────────────────────────────────────────────────────────────────
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

# scp -C enables SSH-level compression, no gzip needed on Windows

# ── Step 1: Build images ───────────────────────────────────────────────────────
function Build-Images {
    Info "Building Docker images for linux/amd64 ..."
    Push-Location $ProjectDir
    try {
        $env:DOCKER_DEFAULT_PLATFORM = "linux/amd64"
        & docker compose build
        if ($LASTEXITCODE -ne 0) { Fail "docker compose build failed" }

        if ($Bundle) {
            Info "Building bundled image (with airgap packages) ..."
            & docker build -f backend/Dockerfile.bundle -t sabc-compliance-backend:bundled backend/
            if ($LASTEXITCODE -ne 0) { Fail "Bundle build failed" }
        }
    } finally {
        Remove-Item Env:DOCKER_DEFAULT_PLATFORM -ErrorAction SilentlyContinue
        Pop-Location
    }
    Ok "Images built (linux/amd64)"
}

# ── Step 2: Save images to tar ─────────────────────────────────────────────────
function Save-Images {
    Info "Saving images to $Archive ..."
    $images = if ($Bundle) {
        "sabc-compliance-backend:bundled", "sabc-compliance-frontend:latest"
    } else {
        "sabc-compliance-backend:latest", "sabc-compliance-frontend:latest"
    }
    & docker save -o $Archive @images
    if ($LASTEXITCODE -ne 0) { Fail "docker save failed" }

    $sizeMB = [math]::Round((Get-Item $Archive).Length / 1MB)
    Ok "Archive ready: $Archive (${sizeMB} MB uncompressed; scp -C compresses during transfer)"
}

# ── Step 3: Install Docker on server (first time only) ────────────────────────
function Setup-Server {
    Info "Installing Docker on $Target ..."
    $setupScript = @'
set -e
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  echo "Docker already installed: $(docker --version) / $(docker compose version)"
  exit 0
fi
. /etc/os-release
case "$ID" in
  ubuntu|debian)
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq ca-certificates curl gnupg lsb-release
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL "https://download.docker.com/linux/$ID/gpg" | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/$ID $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
    ;;
  rhel|centos|fedora|amzn)
    yum install -y docker
    systemctl enable docker && systemctl start docker
    COMPOSE_VER=$(curl -sSL https://api.github.com/repos/docker/compose/releases/latest | grep tag_name | cut -d'"' -f4)
    mkdir -p /usr/local/lib/docker/cli-plugins
    curl -sSL "https://github.com/docker/compose/releases/download/${COMPOSE_VER}/docker-compose-$(uname -s)-$(uname -m)" \
      -o /usr/local/lib/docker/cli-plugins/docker-compose
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
    ;;
  *) echo "Unsupported OS: $ID" && exit 1 ;;
esac
systemctl enable docker && systemctl start docker
[ -n "${SUDO_USER:-}" ] && usermod -aG docker "$SUDO_USER" || true
echo "Done: $(docker --version) / $(docker compose version)"
'@

    $tmpScript = [System.IO.Path]::GetTempFileName() + ".sh"
    $setupScript | Set-Content -Path $tmpScript -Encoding UTF8
    Get-Content $tmpScript | & $(if ($UsePlink) { $PlinkExe } else { "ssh" }) `
        $(if ($SshKey) { if ($UsePlink) { "-i"; $SshKey } else { "-i"; $SshKey } }) `
        $(if (-not $UsePlink) { "-o"; "StrictHostKeyChecking=no" }) `
        $Target "sudo bash -s"
    Remove-Item $tmpScript -ErrorAction SilentlyContinue
    Ok "Docker ready on $Target"
}

# ── Step 4: Transfer files ─────────────────────────────────────────────────────
function Transfer-Files {
    Info "Creating remote directory $RemoteDir ..."
    Invoke-Remote "sudo mkdir -p $RemoteDir && sudo chown `$(whoami):`$(whoami) $RemoteDir"

    Send-File $Archive "$RemoteDir/sabc-images.tar"
    Send-File (Join-Path $ProjectDir "docker-compose.yml") "$RemoteDir/docker-compose.yml"

    $envFile = Join-Path $ProjectDir ".env"
    if (Test-Path $envFile) {
        Send-File $envFile "$RemoteDir/.env"
    } else {
        Warn "No .env found locally — writing default on server (HTTP_PORT=8443)"
        Invoke-Remote @"
cat > $RemoteDir/.env << 'EOF'
HTTP_PORT=8443
BACKEND_PORT=3000
EOF
"@
    }

    Invoke-Remote "sudo mkdir -p $RemoteDir/backend/packages && sudo chown -R `$(whoami):`$(whoami) $RemoteDir"
    Ok "Files transferred"
}

# ── Step 5: Load and start ─────────────────────────────────────────────────────
function Deploy-Platform {
    Info "Loading Docker images on $Target ..."
    Invoke-Remote "sudo docker load -i $RemoteDir/sabc-images.tar"

    Info "Starting platform ..."
    Invoke-Remote "sudo docker compose -f $RemoteDir/docker-compose.yml --project-directory $RemoteDir up -d"

    # Resolve display host from the SSH target (strip user@)
    $displayHost = if ($Target -match "@") { $Target.Split("@")[1] } else { $Target }

    # Read the actual HTTP port from the .env we shipped (or default 8443)
    $httpPort = "8443"
    $envFile = Join-Path $ProjectDir ".env"
    if (Test-Path $envFile) {
        $portLine = Get-Content $envFile | Where-Object { $_ -match "^HTTP_PORT=" }
        if ($portLine) { $httpPort = $portLine.Split("=")[1].Trim() }
    }

    Ok "Platform deployed!"
    Write-Host ""
    Write-Host "══════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host "  SABC Compliance Platform" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  UI:      http://${displayHost}:${httpPort}" -ForegroundColor White
    Write-Host "  API:     http://${displayHost}:${httpPort}/api" -ForegroundColor White
    Write-Host "  Swagger: http://${displayHost}:3000/docs" -ForegroundColor White
    Write-Host ""
    Write-Host "  Logs:  ssh $Target 'sudo docker compose -f $RemoteDir/docker-compose.yml logs -f'" -ForegroundColor DarkGray
    Write-Host "  Stop:  ssh $Target 'sudo docker compose -f $RemoteDir/docker-compose.yml down'" -ForegroundColor DarkGray
    Write-Host "══════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host ""
}

# ── Main ───────────────────────────────────────────────────────────────────────

if ($BuildOnly -or $Bundle) {
    Build-Images
    Save-Images
    Write-Host ""
    Info "Archive at: $Archive"
    Info "Transfer manually (WinSCP or pscp), then on the server:"
    Info "  sudo docker load -i $RemoteDir/sabc-images.tar"
    Info "  sudo docker compose -f $RemoteDir/docker-compose.yml --project-directory $RemoteDir up -d"
    exit 0
}

if ($Update) {
    if (-not (Test-Path $Archive)) { Fail "No archive at $Archive — run without -Update first." }
    Transfer-Files
    Deploy-Platform
    exit 0
}

# Full deploy
if ($Setup) { Setup-Server }
Build-Images
Save-Images
Transfer-Files
Deploy-Platform
