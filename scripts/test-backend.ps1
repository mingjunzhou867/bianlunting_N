param(
    [ValidateSet("unit", "api", "db", "all")]
    [string]$Mode = "unit"
)

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

$unitModules = @(
    "tests.test_agent_json_parsing",
    "tests.test_collector_registry",
    "tests.test_data_source_loader",
    "tests.test_data_source_session",
    "tests.test_evidence_planner",
    "tests.test_policy_pack_loader",
    "tests.test_question_templates",
    "tests.test_runtime_memory",
    "tests.test_runtime_trace",
    "tests.test_semantic_packet",
    "tests.test_slice1_regression",
    "tests.test_table_payload_collector",
    "tests.test_persistence_contract",
    "tests.test_pack_validator"
)

if ($Mode -eq "unit" -or $Mode -eq "all") {
    Write-Host "Running backend unit tests..." -ForegroundColor Cyan
    & $python -m unittest @unitModules
}

if ($Mode -eq "api" -or $Mode -eq "all") {
    Write-Host "Running API route tests..." -ForegroundColor Cyan
    & $python -m unittest tests.test_retrieval_api
}

if ($Mode -eq "db" -or $Mode -eq "all") {
    Write-Host "Running database-backed smoke checks..." -ForegroundColor Cyan
    & $python -m tests.test_evidence_collector
}
