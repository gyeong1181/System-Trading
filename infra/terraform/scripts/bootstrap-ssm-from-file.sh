#!/bin/bash
set -euo pipefail

# Usage:
#   chmod +x scripts/bootstrap-ssm-from-file.sh
#   AWS_REGION=us-west-2 SSM_PREFIX=/trading/prod ./scripts/bootstrap-ssm-from-file.sh scripts/ssm-secrets.local.env

AWS_REGION="${AWS_REGION:-us-west-2}"
SSM_PREFIX="${SSM_PREFIX:-/trading/prod}"
INPUT_FILE="${1:-scripts/ssm-secrets.local.env}"

if [ ! -f "$INPUT_FILE" ]; then
  echo "Input file not found: $INPUT_FILE"
  exit 1
fi

# shellcheck disable=SC1090
set -a
source "$INPUT_FILE"
set +a

required_vars=(
  PSAR_EXECUTION_MODE
  PSAR_TV_WEBHOOK_SECRET
  PSAR_BINANCE_API_KEY
  PSAR_BINANCE_API_SECRET
  PSAR_TELEGRAM_BOT_TOKEN
  PSAR_TELEGRAM_CHAT_ID
  OKX_QQQ_API_KEY
  OKX_QQQ_API_SECRET
  OKX_QQQ_API_PASSPHRASE
  OKX_XAU_API_KEY
  OKX_XAU_API_SECRET
  OKX_XAU_API_PASSPHRASE
)

for var_name in "${required_vars[@]}"; do
  if [ -z "${!var_name:-}" ]; then
    echo "Missing required variable: $var_name"
    exit 1
  fi
done

put_secure() {
  local name="$1"
  local value="$2"
  aws ssm put-parameter \
    --region "$AWS_REGION" \
    --name "$name" \
    --type SecureString \
    --value "$value" \
    --overwrite >/dev/null
}

put_secure "$SSM_PREFIX/registry/GHCR_USERNAME" "${GHCR_USERNAME:-}"
put_secure "$SSM_PREFIX/registry/GHCR_TOKEN" "${GHCR_TOKEN:-}"

put_secure "$SSM_PREFIX/psar_rsi/EXECUTION_MODE" "$PSAR_EXECUTION_MODE"
put_secure "$SSM_PREFIX/psar_rsi/TV_WEBHOOK_SECRET" "$PSAR_TV_WEBHOOK_SECRET"
put_secure "$SSM_PREFIX/psar_rsi/BINANCE_API_KEY" "$PSAR_BINANCE_API_KEY"
put_secure "$SSM_PREFIX/psar_rsi/BINANCE_API_SECRET" "$PSAR_BINANCE_API_SECRET"
put_secure "$SSM_PREFIX/psar_rsi/TELEGRAM_BOT_TOKEN" "$PSAR_TELEGRAM_BOT_TOKEN"
put_secure "$SSM_PREFIX/psar_rsi/TELEGRAM_CHAT_ID" "$PSAR_TELEGRAM_CHAT_ID"

put_secure "$SSM_PREFIX/okx_qqq/OKX_API_KEY" "$OKX_QQQ_API_KEY"
put_secure "$SSM_PREFIX/okx_qqq/OKX_API_SECRET" "$OKX_QQQ_API_SECRET"
put_secure "$SSM_PREFIX/okx_qqq/OKX_API_PASSPHRASE" "$OKX_QQQ_API_PASSPHRASE"
put_secure "$SSM_PREFIX/okx_qqq/TELEGRAM_BOT_TOKEN" "${OKX_QQQ_TELEGRAM_BOT_TOKEN:-}"
put_secure "$SSM_PREFIX/okx_qqq/TELEGRAM_CHAT_ID" "${OKX_QQQ_TELEGRAM_CHAT_ID:-}"

put_secure "$SSM_PREFIX/okx_xau/OKX_API_KEY" "$OKX_XAU_API_KEY"
put_secure "$SSM_PREFIX/okx_xau/OKX_API_SECRET" "$OKX_XAU_API_SECRET"
put_secure "$SSM_PREFIX/okx_xau/OKX_API_PASSPHRASE" "$OKX_XAU_API_PASSPHRASE"
put_secure "$SSM_PREFIX/okx_xau/TELEGRAM_BOT_TOKEN" "${OKX_XAU_TELEGRAM_BOT_TOKEN:-}"
put_secure "$SSM_PREFIX/okx_xau/TELEGRAM_CHAT_ID" "${OKX_XAU_TELEGRAM_CHAT_ID:-}"

echo "SSM parameters created/updated successfully."
echo "Region: $AWS_REGION"
echo "Prefix: $SSM_PREFIX"
