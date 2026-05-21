param(
    [string]$FrontendEnvPath = ""
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$frontendDir = Join-Path $repoRoot "frontend"
$packageLock = Join-Path $frontendDir "package-lock.json"
$nodeModules = Join-Path $frontendDir "node_modules"
$viteCmd = Join-Path $nodeModules ".bin\vite.cmd"

$npm = Get-Command "npm.cmd" -ErrorAction SilentlyContinue
if (-not $npm) {
    Write-Host "npm.cmd was not found. Install Node.js and ensure npm is in PATH." -ForegroundColor Yellow
    exit 1
}

if ($FrontendEnvPath) {
    if (-not (Test-Path $FrontendEnvPath)) {
        Write-Host "Frontend environment bootstrap script was not found: $FrontendEnvPath" -ForegroundColor Yellow
        exit 1
    }
    . $FrontendEnvPath
}

Write-Host "Starting frontend from $frontendDir" -ForegroundColor Cyan
Set-Location $frontendDir

if (-not (Test-Path $viteCmd)) {
    Write-Host "Frontend dependencies are missing. Running npm install..." -ForegroundColor Yellow
    if (Test-Path $packageLock) {
        & "npm.cmd" "install"
    } else {
        & "npm.cmd" "install"
    }
}

& "npm.cmd" "run" "dev"
