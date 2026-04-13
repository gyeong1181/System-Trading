$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$authDir = Join-Path $root "runtime_state\\auth"
$logsDir = Join-Path $root "runtime_state\\logs"
$envFile = Join-Path $root ".env"
$envExample = Join-Path $root ".env.example"
$composeFile = Join-Path $root "docker-compose.original-preserve.yml"

New-Item -ItemType Directory -Force $authDir | Out-Null
New-Item -ItemType Directory -Force $logsDir | Out-Null

if (-not (Test-Path -LiteralPath $envFile)) {
    Copy-Item -LiteralPath $envExample -Destination $envFile
    Write-Host "Created .env from .env.example. Fill in your real values before starting."
    exit 1
}

docker compose -f $composeFile up -d
