#Requires -Version 5.1
# ═══════════════════════════════════════════════════════════════════════════════
# SABC Compliance Platform — Windows Deployment Script (PowerShell)
# ═══════════════════════════════════════════════════════════════════════════════
#
# Usage:
#   .\deploy\ship.ps1 -Target ubuntu@<ec2-ip>
#   .\deploy\ship.ps1 -Target ubuntu@<ec2-ip> -Setup        # First time: installs Docker
#   .\deploy\ship.ps1 -Target ubuntu@<ec2-ip> -Update       # Re-transfer without rebuild
#   .\deploy\ship.ps1 -BuildOnly                             # Build & save locally only
#   .\deploy\ship.ps1 -Target ubuntu@<ec2-ip> -Bundle       # Include airgap packages
#
# Authentication:
#   The script prompts for your SSH password once and reuses it for all
#   remote commands. No root access required on your Windows machine.
#
# Prerequisites (install ONE of these for SSH/SCP):
#   Option A — PuTTY (recommended for password auth, no admin needed):
#     https://www.putty.org  →  download plink.exe + pscp.exe
#     Add their folder to PATH or place them alongside this script.
#   Option B — Windows OpenSSH (built into Windows 10/11):
#     Settings → Apps → Optional Features → OpenSSH Client
#     Note: will prompt for password interactively on each command.
#   Option C — Git for Windows (https://git-scm.com):
#     Includes ssh, scp, and gzip. Run this script from Git Bash instead.
#
# Prerequisites (Docker):
#   Docker Desktop for Windows with Linux containers enabled.
#   https://docs.docker.com/desktop/install/windows-install/
#
# Run policy — if blocked by execution policy, run once:
#   Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
#
# ═══════════════════════════════════════════════════════════════════════════════

param(
    [Parameter(Position = 0)]
    [string]$Target = "",

    [switch]$Setup,
    [switch]$Update,
    [switch]$BuildOnly,
    [switch]$Bundle
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Paths ─────────────────────────────────────────────────────────────────────
$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$Archive    = Join-Path $ScriptDir "sabc-images.tar"   # .tar (no gzip needed on Windows)
$RemoteDir  = "/opt/sabc-compliance"

# ── Validate arguments ────────────────────────────────────────────────────────
if (-not $Target -and -not $BuildOnly -and -not $Bundle) {
    Write-Host "Usage: .\deploy\ship.ps1 -Target user@ec2-ip [-Setup|-Update|-BuildOnly|-Bundle]"
    exit 1
}

# ── Colour helpers ────────────────────────────────────────────────────────────
function Info  { param($msg) Write-Host ">> $msg" -ForegroundColor Cyan }
function Ok    { param($msg) Write-Host "OK $msg" -ForegroundColor Green }
function Fail  { param($msg) Write-Host "!! $msg" -ForegroundColor Red; exit 1 }
function Warn  { param($msg) Write-Host "** $msg" -ForegroundColor Yellow }

# ── Detect SSH/SCP tool ───────────────────────────────────────────────────────
$UsePlink = $false
$PlinkExe = ""
$PscpExe  = ""

# Search for plink/pscp alongside this script, then in PATH
$SearchPaths = @($ScriptDir, (Join-Path $env:USERPROFILE "Downloads"), "C:\Program Files\PuTTY", "C:\PuTTY")
foreach ($p in $SearchPaths) {
    if (Test-Path (Join-Path $p "plink.exe")) {
        $PlinkExe = Join-Path $p "plink.exe"
        $PscpExe  = Join-Path $p "pscp.exe"
        $UsePlink = $true
        break
    }
}
if (-not $UsePlink) {
    $found = Get-Command "plink.exe" -ErrorAction SilentlyContinue
    if ($found) { $PlinkExe = $found.Source; $PscpExe = (Get-Command "pscp.exe" -ErrorAction SilentlyContinue)?.Source; $UsePlink = $true }
}

if ($UsePlink) {
    Ok "Found PuTTY tools: $PlinkExe"
} else {
    $sshFound = Get-Command "ssh" -ErrorAction SilentlyContinue
    if (-not $sshFound) {
        Fail "No SSH client found. Install PuTTY (plink.exe + pscp.exe) or enable OpenSSH Client in Windows Settings -> Optional Features."
    }
    Warn "PuTTY not found — using built-in ssh/scp. You will be prompted for the password on each step."
}

# ── Collect SSH credentials ───────────────────────────────────────────────────
$SshPassword = ""
if ($Target -and $UsePlink) {
    $SecurePass  = Read-Host "SSH password for $Target" -AsSecureString
    $SshPassword = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
                       [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecurePass))
}

# ── SSH helpers ───────────────────────────────────────────────────────────────
function Invoke-Remote {
    param([string]$Cmd)
    if ($UsePlink) {
        & $PlinkExe -ssh -pw $SshPassword -batch -no-antispoof $Target $Cmd
        if ($LASTEXITCODE -ne 0) { Fail "Remote command failed: $Cmd" }
    } else {
        & ssh -o StrictHostKeyChecking=no $Target $Cmd
        if ($LASTEXITCODE -ne 0) { Fail "Remote command failed: $Cmd" }
    }
}

function Invoke-RemoteSudo {
    param([string]$Cmd)
    Invoke-Remote "sudo $Cmd"
}

function Send-File {
    param([string]$LocalPath, [string]$RemotePath)
    Info "Transferring $(Split-Path -Leaf $LocalPath) ..."
    if ($UsePlink -and $PscpExe) {
        & $PscpExe -pw $SshPassword -batch "$LocalPath" "${Target}:${RemotePath}"
        if ($LASTEXITCODE -ne 0) { Fail "Transfer failed: $LocalPath" }
    } else {
        & scp -o StrictHostKeyChecking=no "$LocalPath" "${Target}:${RemotePath}"
        if ($LASTEXITCODE -ne 0) { Fail "Transfer failed: $LocalPath" }
    }
}

# ── Step 1: Build images ──────────────────────────────────────────────────────
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
        $env:DOCKER_DEFAULT_PLATFORM = ""
        Pop-Location
    }
    Ok "Images built (linux/amd64)"
}

# ── Step 2: Save images to tar ────────────────────────────────────────────────
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
    Ok "Archive ready: $Archive (${sizeMB} MB)"
    Warn "Tip: the .tar is uncompressed. Transfer may take a few minutes on a slow connection."
}

# ── Step 3: Install Docker on EC2 (first time only) ───────────────────────────
function Setup-EC2 {
    Info "Installing Docker on $Target ..."
    $setupScript = @'
set -e
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  echo "Docker already installed: $(docker --version)"
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
  amzn|rhel|centos|fedora)
    yum install -y docker
    systemctl enable docker && systemctl start docker
    COMPOSE_VER=$(curl -sSL https://api.github.com/repos/docker/compose/releases/latest | grep tag_name | cut -d'"' -f4)
    mkdir -p /usr/local/lib/docker/cli-plugins
    curl -sSL "https://github.com/docker/compose/releases/download/${COMPOSE_VER}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/lib/docker/cli-plugins/docker-compose
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
    ;;
  *) echo "Unsupported OS: $ID"; exit 1 ;;
esac
systemctl enable docker && systemctl start docker
echo "Docker installed: $(docker --version)"
'@

    # Write the setup script to a temp file and pipe it via SSH
    $tmpScript = [System.IO.Path]::GetTempFileName() + ".sh"
    $setupScript | Set-Content -Path $tmpScript -Encoding UTF8

    if ($UsePlink) {
        Get-Content $tmpScript | & $PlinkExe -ssh -pw $SshPassword -batch $Target "sudo bash -s"
    } else {
        Get-Content $tmpScript | & ssh -o StrictHostKeyChecking=no $Target "sudo bash -s"
    }
    Remove-Item $tmpScript -ErrorAction SilentlyContinue

    Ok "Docker ready on $Target"
}

# ── Step 4: Transfer files ────────────────────────────────────────────────────
function Transfer-Files {
    Info "Creating remote directory $RemoteDir ..."
    Invoke-Remote "sudo mkdir -p $RemoteDir && sudo chown `$(whoami):`$(whoami) $RemoteDir"

    Send-File $Archive "$RemoteDir/sabc-images.tar"

    $composeFile = Join-Path $ProjectDir "docker-compose.yml"
    Send-File $composeFile "$RemoteDir/docker-compose.yml"

    $envFile = Join-Path $ProjectDir ".env"
    if (Test-Path $envFile) {
        Send-File $envFile "$RemoteDir/.env"
    } else {
        Warn "No .env found locally — creating minimal default on EC2"
        Invoke-Remote "cat > $RemoteDir/.env << 'EOF'`nHTTP_PORT=80`nBACKEND_PORT=3000`nEOF"
    }

    Invoke-Remote "sudo mkdir -p $RemoteDir/backend/packages && sudo chown -R `$(whoami):`$(whoami) $RemoteDir"
    Ok "Files transferred"
}

# ── Step 5: Load and start ────────────────────────────────────────────────────
function Deploy-Platform {
    Info "Loading Docker images on $Target ..."
    Invoke-RemoteSudo "docker load -i $RemoteDir/sabc-images.tar"

    Info "Starting platform ..."
    Invoke-RemoteSudo "docker compose -f $RemoteDir/docker-compose.yml --project-directory $RemoteDir up -d"

    Ok "Platform deployed!"
    Write-Host ""
    Write-Host "══════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host "  SABC Compliance Platform is running on:" -ForegroundColor Cyan
    Write-Host ""

    try {
        $pubIp = Invoke-Remote "curl -s --connect-timeout 3 http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || hostname -I | awk '{print `$1}'"
        Write-Host "  UI:      http://$pubIp" -ForegroundColor White
        Write-Host "  API:     http://$pubIp/api" -ForegroundColor White
        Write-Host "  Swagger: http://$pubIp`:3000/docs" -ForegroundColor White
    } catch {
        Write-Host "  Connect to: http://<ec2-public-ip>" -ForegroundColor White
    }

    Write-Host ""
    Write-Host "  Logs: ssh $Target 'sudo docker compose -f $RemoteDir/docker-compose.yml logs -f'" -ForegroundColor DarkGray
    Write-Host "══════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host ""
}

# ── Main ──────────────────────────────────────────────────────────────────────

if ($BuildOnly -or $Bundle) {
    Build-Images
    Save-Images
    Write-Host ""
    Info "Archive ready at: $Archive"
    Info "Transfer manually via WinSCP or pscp, then on the server:"
    Info "  sudo docker load -i $RemoteDir/sabc-images.tar"
    Info "  sudo docker compose -f $RemoteDir/docker-compose.yml --project-directory $RemoteDir up -d"
    exit 0
}

if ($Update) {
    if (-not (Test-Path $Archive)) {
        Fail "No archive found at $Archive — run without -Update first to build."
    }
    Transfer-Files
    Deploy-Platform
    exit 0
}

# Full deploy
if ($Setup) { Setup-EC2 }
Build-Images
Save-Images
Transfer-Files
Deploy-Platform
