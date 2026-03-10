param(
    [string]$EnvFile = "scripts/ssm-secrets.local.env",
    [string]$AwsRegion = "us-west-2",
    [string]$SsmPrefix = "/trading/prod"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $EnvFile)) {
    throw "Env file not found: $EnvFile"
}

$kv = @{}
Get-Content $EnvFile | ForEach-Object {
    $line = $_.Trim()
    if ($line -eq "" -or $line.StartsWith("#")) { return }
    $idx = $line.IndexOf("=")
    if ($idx -lt 0) { return }
    $key = $line.Substring(0, $idx).Trim()
    $value = $line.Substring($idx + 1).Trim()
    $kv[$key] = $value
}

$required = @(
    "PSAR_EXECUTION_MODE",
    "PSAR_TV_WEBHOOK_SECRET",
    "PSAR_BINANCE_API_KEY",
    "PSAR_BINANCE_API_SECRET",
    "PSAR_TELEGRAM_BOT_TOKEN",
    "PSAR_TELEGRAM_CHAT_ID",
    "OKX_QQQ_API_KEY",
    "OKX_QQQ_API_SECRET",
    "OKX_QQQ_API_PASSPHRASE",
    "OKX_XAU_API_KEY",
    "OKX_XAU_API_SECRET",
    "OKX_XAU_API_PASSPHRASE"
)

foreach ($k in $required) {
    if (-not $kv.ContainsKey($k) -or [string]::IsNullOrWhiteSpace($kv[$k])) {
        throw "Missing required variable: $k"
    }
}

function Put-SecureParam {
    param(
        [string]$Name,
        [string]$Value
    )
    aws ssm put-parameter `
        --region $AwsRegion `
        --name $Name `
        --type SecureString `
        --value $Value `
        --overwrite | Out-Null
}

function Get-OptionalValue {
    param(
        [hashtable]$Map,
        [string]$Key
    )
    if ($Map.ContainsKey($Key) -and -not [string]::IsNullOrWhiteSpace($Map[$Key])) {
        return $Map[$Key]
    }
    return ""
}

Put-SecureParam "$SsmPrefix/psar_rsi/EXECUTION_MODE" $kv["PSAR_EXECUTION_MODE"]
Put-SecureParam "$SsmPrefix/psar_rsi/TV_WEBHOOK_SECRET" $kv["PSAR_TV_WEBHOOK_SECRET"]
Put-SecureParam "$SsmPrefix/psar_rsi/BINANCE_API_KEY" $kv["PSAR_BINANCE_API_KEY"]
Put-SecureParam "$SsmPrefix/psar_rsi/BINANCE_API_SECRET" $kv["PSAR_BINANCE_API_SECRET"]
Put-SecureParam "$SsmPrefix/psar_rsi/TELEGRAM_BOT_TOKEN" $kv["PSAR_TELEGRAM_BOT_TOKEN"]
Put-SecureParam "$SsmPrefix/psar_rsi/TELEGRAM_CHAT_ID" $kv["PSAR_TELEGRAM_CHAT_ID"]

Put-SecureParam "$SsmPrefix/okx_qqq/OKX_API_KEY" $kv["OKX_QQQ_API_KEY"]
Put-SecureParam "$SsmPrefix/okx_qqq/OKX_API_SECRET" $kv["OKX_QQQ_API_SECRET"]
Put-SecureParam "$SsmPrefix/okx_qqq/OKX_API_PASSPHRASE" $kv["OKX_QQQ_API_PASSPHRASE"]
Put-SecureParam "$SsmPrefix/okx_qqq/TELEGRAM_BOT_TOKEN" (Get-OptionalValue -Map $kv -Key "OKX_QQQ_TELEGRAM_BOT_TOKEN")
Put-SecureParam "$SsmPrefix/okx_qqq/TELEGRAM_CHAT_ID" (Get-OptionalValue -Map $kv -Key "OKX_QQQ_TELEGRAM_CHAT_ID")

Put-SecureParam "$SsmPrefix/okx_xau/OKX_API_KEY" $kv["OKX_XAU_API_KEY"]
Put-SecureParam "$SsmPrefix/okx_xau/OKX_API_SECRET" $kv["OKX_XAU_API_SECRET"]
Put-SecureParam "$SsmPrefix/okx_xau/OKX_API_PASSPHRASE" $kv["OKX_XAU_API_PASSPHRASE"]
Put-SecureParam "$SsmPrefix/okx_xau/TELEGRAM_BOT_TOKEN" (Get-OptionalValue -Map $kv -Key "OKX_XAU_TELEGRAM_BOT_TOKEN")
Put-SecureParam "$SsmPrefix/okx_xau/TELEGRAM_CHAT_ID" (Get-OptionalValue -Map $kv -Key "OKX_XAU_TELEGRAM_CHAT_ID")

Write-Host "SSM parameters created/updated successfully."
Write-Host "Region: $AwsRegion"
Write-Host "Prefix: $SsmPrefix"
