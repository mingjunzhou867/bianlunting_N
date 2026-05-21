param(
    [ValidateSet("test", "build", "all")]
    [string]$Mode = "all"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$frontendDir = Join-Path $repoRoot "frontend"
$nodeModules = Join-Path $frontendDir "node_modules"
$npm = Get-Command "npm.cmd" -ErrorAction SilentlyContinue

if (-not $npm) {
    Write-Host "npm.cmd was not found. Install Node.js and ensure npm is in PATH." -ForegroundColor Red
    exit 1
}

Set-Location $frontendDir

if (-not (Test-Path $nodeModules)) {
    Write-Host "Frontend dependencies are missing. Running npm install..." -ForegroundColor Yellow
    & "npm.cmd" "install"
}

if ($Mode -eq "test" -or $Mode -eq "all") {
    Write-Host "Running frontend smoke tests..." -ForegroundColor Cyan
    & "npm.cmd" "run" "test"
}

if ($Mode -eq "build" -or $Mode -eq "all") {
    Write-Host "Running frontend production build..." -ForegroundColor Cyan
    & "npm.cmd" "run" "build"
}
