$ErrorActionPreference = "Stop"
$services = @("user-service","product-service","order-service","payment-service","notification-service")
foreach ($s in $services) {
    Write-Host "==> building $s" -ForegroundColor Cyan
    docker build -t "msa/${s}:0.1.0" ".\services\$s"
    if ($LASTEXITCODE -ne 0) { Write-Host "BUILD FAILED: $s" -ForegroundColor Red; exit 1 }
}
Write-Host "`n==> done" -ForegroundColor Green
docker images --filter "reference=msa/*"
