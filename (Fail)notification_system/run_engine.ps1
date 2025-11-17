# PowerShell helper to launch the reactive trading engine with one click.
Param(
    [switch]$Loop = $true,
    [string]$Config = "config.yaml"
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonFromVenv = Join-Path $projectRoot "venv\Scripts\python.exe"
$pythonCmd = if (Test-Path $pythonFromVenv) { $pythonFromVenv } else { "python" }

Write-Host "Using Python executable: $pythonCmd"

Push-Location $projectRoot
try {
    $argsList = @("-m", "project.main", "--config", $Config)
    if ($Loop) {
        $argsList += "--run-loop"
    }
    Write-Host "Starting trading engine..." -ForegroundColor Cyan
    & $pythonCmd @argsList
}
finally {
    Pop-Location
}
