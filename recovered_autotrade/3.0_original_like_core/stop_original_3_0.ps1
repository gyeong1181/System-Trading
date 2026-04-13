$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$composeFile = Join-Path $root "docker-compose.original-preserve.yml"

docker compose -f $composeFile down
