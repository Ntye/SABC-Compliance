#Requires -Version 5.1
# =============================================================================
# SABC Compliance -- Ollama model downloader (PowerShell)
# =============================================================================
#
# Run this script on any machine with Docker and internet access to download
# an Ollama model and pack it into a tar archive that can be transferred to
# the airgap server later.  The server itself needs no internet at all.
#
# Usage:
#   .\deploy\get-model.ps1                                # llama3.2:1b -> deploy\ollama-models.tar.gz
#   .\deploy\get-model.ps1 -Model llama3.2:3b             # larger / better model
#   .\deploy\get-model.ps1 -Model llama3.2:1b -Output C:\tmp\ai.tar.gz
#
# After running, deploy the model to the server with:
#   .\deploy\ship.ps1 -Target user@server -AiModels .\deploy\ollama-models.tar.gz
#
# Or transfer and load manually (useful for updates without a full redeploy):
#   pscp .\deploy\ollama-models.tar.gz user@server:/opt/sabc-compliance/
#   ssh user@server sudo bash -s  (then paste the commands shown at the end)
#
# Prerequisites:
#   Docker Desktop for Windows (Linux containers mode)
#   tar.exe  -- built into Windows 10 1803+ and Windows Server 2019+
#
# If blocked by execution policy, run once:
#   Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
# =============================================================================

param(
    [string]$Model  = "llama3.2:1b",
    [string]$Output = ""              # defaults to deploy\ollama-models.tar.gz
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $Output) {
    $Output = Join-Path $ScriptDir "ollama-models.tar.gz"
}

function Info { param($msg) Write-Host ">> $msg" -ForegroundColor Cyan  }
function Ok   { param($msg) Write-Host "OK $msg" -ForegroundColor Green }
function Fail { param($msg) Write-Host "!! $msg" -ForegroundColor Red; exit 1 }

# -- Verify Docker is available -----------------------------------------------
if ($null -eq (Get-Command "docker" -ErrorAction SilentlyContinue)) {
    Fail "Docker not found in PATH. Install Docker Desktop and make sure it is running."
}

# -- Verify tar is available (built into Windows 10 1803+) --------------------
if ($null -eq (Get-Command "tar" -ErrorAction SilentlyContinue)) {
    Fail "tar.exe not found. It ships with Windows 10 1803+ and Windows Server 2019+."
}

Info "Pulling Ollama model '$Model' using Docker (this may take several minutes) ..."

# Pull model into a temporary directory via Docker.
# Docker Desktop on Windows requires absolute paths for bind mounts; we use a
# temp directory under the user profile which is always accessible.
$ModelDir = Join-Path $env:TEMP "sabc-ollama-model-$(Get-Random)"
New-Item -ItemType Directory -Force -Path $ModelDir | Out-Null

try {
    # Convert Windows path to the /host_mnt/... form that Docker Desktop
    # bind-mounts understand, e.g. C:\Users\... -> /host_mnt/c/Users/...
    $modelDirFwd = $ModelDir -replace '\\', '/'
    # Docker Desktop translates drive letters automatically when the path uses
    # forward slashes, but we still normalise the colon away to be safe.
    $dockerMount = $modelDirFwd -replace '^([A-Za-z]):', { "/host_mnt/$($_.Groups[1].Value.ToLower())" }

    & docker run --rm `
        -v "${dockerMount}:/root/.ollama" `
        ollama/ollama:latest pull $Model
    if ($LASTEXITCODE -ne 0) { Fail "Docker pull failed (exit $LASTEXITCODE)" }

    Info "Archiving model files -> $Output ..."
    # tar -C changes into the directory so paths inside the archive are relative.
    & tar -czf $Output -C $ModelDir .
    if ($LASTEXITCODE -ne 0) { Fail "tar archive failed (exit $LASTEXITCODE)" }

    $sizeMB = [math]::Round((Get-Item $Output).Length / 1MB)
    Ok "Model archive ready: $Output (${sizeMB} MB)"

    Write-Host ""
    Info "Deploy to server:"
    Info "  .\deploy\ship.ps1 -Target user@your-server -AiModels '$Output'"
    Write-Host ""
    Info "Or update the model on an already-running server (no full redeploy needed):"
    Info "  1. Transfer the archive:"
    Info "       pscp -scp '$Output' user@your-server:/opt/sabc-compliance/ollama-models.tar.gz"
    Info "  2. On the server, run:"
    Info "       docker volume create sabc-ollama-models"
    Info "       docker run --rm \"
    Info "         -v sabc-ollama-models:/dest \"
    Info "         -v /opt/sabc-compliance/ollama-models.tar.gz:/src/m.tar.gz \"
    Info "         alpine tar -xzf /src/m.tar.gz -C /dest"
    Info "       docker restart sabc-ollama"

} finally {
    Remove-Item -Recurse -Force $ModelDir -ErrorAction SilentlyContinue
}
