$ErrorActionPreference = "Stop"
$H = @{ "Content-Type" = "application/json" }

Write-Host "`n[1] health check (5 services)" -ForegroundColor Cyan
foreach ($p in 8001,8002,8003,8004,8005) {
    $r = Invoke-RestMethod "http://localhost:$p/healthz"
    Write-Host ("  {0,-24} {1}" -f $r.service, $r.status)
}

Write-Host "`n[2] signup" -ForegroundColor Cyan
Invoke-RestMethod -Method Post "http://localhost:8001/users" -Headers $H `
    -Body '{"email":"kh@example.com","password":"pw1234"}' | ConvertTo-Json -Compress

Write-Host "`n[3] login (JWT)" -ForegroundColor Cyan
$tok = (Invoke-RestMethod -Method Post "http://localhost:8001/login" -Headers $H `
    -Body '{"email":"kh@example.com","password":"pw1234"}').access_token
Write-Host "  token: $($tok.Substring(0,25))..."

Write-Host "`n[4] product cache (MISS -> HIT)" -ForegroundColor Cyan
(Invoke-RestMethod "http://localhost:8002/products/p1").cache
(Invoke-RestMethod "http://localhost:8002/products/p1").cache

Write-Host "`n[5] create order (4-service chain)" -ForegroundColor Cyan
$o = Invoke-RestMethod -Method Post "http://localhost:8003/orders" -Headers $H `
    -Body '{"email":"kh@example.com","product_id":"p1","qty":2}'
$o | ConvertTo-Json -Compress

Write-Host "`n[6] notification delivered?" -ForegroundColor Cyan
(Invoke-RestMethod "http://localhost:8005/notifications").items[0] | ConvertTo-Json -Compress

Write-Host "`nSMOKE TEST PASSED" -ForegroundColor Green
