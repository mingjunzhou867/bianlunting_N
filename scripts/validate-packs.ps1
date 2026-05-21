param()

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (Test-Path $venvPython) {
    $python = $venvPython
} else {
    $pythonCmd = Get-Command "python" -ErrorAction SilentlyContinue
    if (-not $pythonCmd) {
        Write-Host "python was not found. Create .venv or add Python to PATH." -ForegroundColor Red
        exit 1
    }
    $python = $pythonCmd.Source
}

Set-Location $repoRoot
& $python -m tools.pack_validator
