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
#   .\deploy\ship.ps1 -BuildOnly                                 # Build and save locally only
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
    [switch]$Bundle          # Use Dockerfile.bundle (airgap packages)
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# -- Paths --------------------------------------------------------------------
$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$Archive    = Join-Path $ScriptDir "sabc-images.tar"
$RemoteDir  = "/opt/sabc-compliance"

# -- Validate arguments -------------------------------------------------------
if ((-not $Target) -and (-not $BuildOnly) -and (-not $Bundle)) {
    Write-Host "Usage: .\deploy\ship.ps1 -Target user@server [-SshKey key.pem] [-Setup|-Update|-Start|-Restart|-BuildOnly]"
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
        $env:DOCKER_DEFAULT_PLATFORM = "linux/amd64"
        & docker compose build
        if ($LASTEXITCODE -ne 0) { Fail "docker compose build failed" }

        if ($Bundle) {
            Info "Building bundled image (airgap packages) ..."
            & docker build -f backend/Dockerfile.bundle -t sabc-compliance-backend:bundled backend/
            if ($LASTEXITCODE -ne 0) { Fail "Bundle build failed" }
        }
    } finally {
        Remove-Item Env:DOCKER_DEFAULT_PLATFORM -ErrorAction SilentlyContinue
        Pop-Location
    }
    Ok "Images built (linux/amd64)"
}

# -- Step 2: Save images to tar -----------------------------------------------
function Save-Images {
    Info "Saving images to $Archive ..."
    if ($Bundle) {
        $images = @("sabc-compliance-backend:bundled", "sabc-compliance-frontend:latest")
    } else {
        $images = @("sabc-compliance-backend:latest", "sabc-compliance-frontend:latest")
    }
    & docker save -o $Archive $images
    if ($LASTEXITCODE -ne 0) { Fail "docker save failed" }

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
        "echo `"Done: `$(docker --version) / `$(docker compose version)`""
    )
    # Feed the script to the remote over stdin. When a sudo password is set we
    # prepend it as the very first line: "sudo -S" reads exactly that one line
    # for authentication and leaves the remainder of stdin for "bash -s" to
    # execute. (Encoding is ASCII so PowerShell does not emit a UTF-8 BOM, which
    # would otherwise corrupt the first line of the script.)
    if ($SudoPassword -ne "") {
        $sudoSetup = "sudo -S bash -s"
        @($SudoPassword) + $lines | Set-Content -Path $tmpScript -Encoding ASCII
    } else {
        $sudoSetup = "sudo bash -s"
        $lines | Set-Content -Path $tmpScript -Encoding ASCII
    }
    if ($UsePlink) {
        if ($SshKey) {
            Get-Content $tmpScript | & $PlinkExe -ssh -i $SshKey -batch $Target $sudoSetup
        } else {
            Get-Content $tmpScript | & $PlinkExe -ssh -pw $SshPassword -batch $Target $sudoSetup
        }
    } else {
        if ($SshKey) {
            Get-Content $tmpScript | & ssh -o StrictHostKeyChecking=no -i $SshKey $Target $sudoSetup
        } else {
            Get-Content $tmpScript | & ssh -o StrictHostKeyChecking=no $Target $sudoSetup
        }
    }
    Remove-Item $tmpScript -ErrorAction SilentlyContinue
    if ($LASTEXITCODE -ne 0) { Fail "Docker installation failed on $Target" }
    Ok "Docker ready on $Target"
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
        Warn "No .env found -- writing default on server (HTTP_PORT=8443)"
        $tmpEnv = [System.IO.Path]::GetTempFileName()
        @(
            "HTTP_PORT=8443",
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
    $httpPort = "8443"
    $envFile = Join-Path $ProjectDir ".env"
    if (Test-Path $envFile) {
        $portLine = Get-Content $envFile | Where-Object { $_ -match "^HTTP_PORT=" }
        if ($portLine) { $httpPort = $portLine.Split("=")[1].Trim() }
    }
    Ok "Platform running!"
    Write-Host ""
    Write-Host "======================================================" -ForegroundColor Cyan
    Write-Host "  SABC Compliance Platform" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  UI:      http://${displayHost}:${httpPort}" -ForegroundColor White
    Write-Host "  API:     http://${displayHost}:${httpPort}/api" -ForegroundColor White
    Write-Host "  Swagger: http://${displayHost}:3000/docs" -ForegroundColor White
    Write-Host ""
    Write-Host "  Logs: ssh $Target sudo docker-compose -f $RemoteDir/docker-compose.yml logs -f" -ForegroundColor DarkGray
    Write-Host "  Stop: ssh $Target sudo docker-compose -f $RemoteDir/docker-compose.yml down" -ForegroundColor DarkGray
    Write-Host "======================================================" -ForegroundColor Cyan
    Write-Host ""
}

# Detect whether the server has the compose plugin (docker compose) or the
# standalone binary (docker-compose) and return the right invocation.
function Get-ComposeCmd {
    if ($UsePlink) {
        if ($SshKey) {
            $out = & $PlinkExe -ssh -i $SshKey -batch $Target "docker compose version >/dev/null 2>&1 && echo PLUGIN || echo STANDALONE" 2>&1
        } else {
            $out = & $PlinkExe -ssh -pw $SshPassword -batch $Target "docker compose version >/dev/null 2>&1 && echo PLUGIN || echo STANDALONE" 2>&1
        }
    } else {
        if ($SshKey) {
            $out = & ssh -o StrictHostKeyChecking=no -i $SshKey $Target "docker compose version >/dev/null 2>&1 && echo PLUGIN || echo STANDALONE"
        } else {
            $out = & ssh -o StrictHostKeyChecking=no $Target "docker compose version >/dev/null 2>&1 && echo PLUGIN || echo STANDALONE"
        }
    }
    if ("$out" -match "PLUGIN") {
        Ok "Docker Compose: plugin (docker compose)"
        return "docker compose"
    } else {
        Ok "Docker Compose: standalone (docker-compose)"
        return "docker-compose"
    }
}

# -- Step 5a: Start containers (compose up only -- images already loaded) -----
function Start-Containers {
    Info "Starting platform ..."
    $compose = Get-ComposeCmd
    # Wrap all operations in a single bash -c so they run under one sudo
    # invocation.  docker-compose 1.29.2 crashes with a ContainerConfig KeyError
    # when it tries to recreate a container whose image was built with a newer
    # Docker version.  "docker-compose down" finds containers by their compose
    # project labels (not by name), so it removes them cleanly regardless of
    # whatever prefixed name docker-compose assigned on the previous run.
    #
    # However "down" only removes containers belonging to THIS compose project.
    # A stale sabc-frontend/sabc-backend left by an earlier project context (or
    # the dev compose) keeps holding ports 443/80/3000 and the new container
    # then fails with "port is already allocated". Our compose files pin fixed
    # container_name values, so we additionally force-remove them by name — this
    # is reliable precisely because the names are fixed — plus --remove-orphans.
    $bashCmd = "$compose -f $RemoteDir/docker-compose.yml --project-directory $RemoteDir down --remove-orphans 2>/dev/null || true; docker rm -f sabc-frontend sabc-backend 2>/dev/null || true; $compose -f $RemoteDir/docker-compose.yml --project-directory $RemoteDir up -d --no-build"

    # Run compose; on failure print the backend log so the crash reason is
    # visible without needing a separate SSH session.
    Invoke-Sudo "bash -c '$bashCmd'" -AllowFail
    if ($LASTEXITCODE -ne 0) {
        Warn "docker-compose up failed -- showing backend logs for diagnosis:"
        Invoke-Sudo "docker logs --tail 60 sabc-backend 2>&1 || true" -AllowFail
        Fail "Containers failed to start (see backend logs above)"
    }

    Show-URLs
}

# -- Step 5b: Load images then start ------------------------------------------
function Deploy-Platform {
    Info "Loading Docker images on $Target ..."
    Invoke-Sudo "docker load -i $RemoteDir/sabc-images.tar"
    Start-Containers
}

# -- Main ---------------------------------------------------------------------
#
#  Flag summary:
#    (none)     Full deploy: build -> save -> transfer -> load -> start
#    -Setup     Install Docker on server first, then full deploy
#    -Update    Images already saved locally  -> transfer -> load -> start
#    -Start     Files already on server       -> load -> start
#    -Restart   Images already loaded         -> docker compose up -d only
#    -BuildOnly Build and save locally, print manual instructions
#

if ($BuildOnly -or $Bundle) {
    Build-Images
    Save-Images
    Write-Host ""
    Info "Archive at: $Archive"
    Info "Transfer manually (WinSCP or pscp), then on the server run:"
    Info "  .\deploy\ship.ps1 -Target user@server -Start"
    exit 0
}

if ($Restart) {
    Info "Restarting containers on $Target (images already loaded) ..."
    Start-Containers
    exit 0
}

if ($Start) {
    Info "Loading and starting on $Target (files already transferred) ..."
    Deploy-Platform
    exit 0
}

if ($Update) {
    if (-not (Test-Path $Archive)) {
        Fail "No archive at $Archive -- run without -Update first to build."
    }
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
