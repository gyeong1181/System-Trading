#!/bin/bash
set -euo pipefail

# Usage:
#   chmod +x scripts/bootstrap-ssm-parameters.sh
#   AWS_REGION=us-west-2 SSM_PREFIX=/trading/prod ./scripts/bootstrap-ssm-parameters.sh
#
# This script prompts for values and stores them as SecureString in SSM Parameter Store.

AWS_REGION="${AWS_REGION:-us-west-2}"
SSM_PREFIX="${SSM_PREFIX:-/trading/prod}"

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

read -rp "PSAR EXECUTION_MODE (LIVE/RECEIVE_ONLY): " PSAR_EXECUTION_MODE
read -rp "PSAR TV_WEBHOOK_SECRET: " PSAR_TV_WEBHOOK_SECRET
read -rp "PSAR BINANCE_API_KEY: " PSAR_BINANCE_API_KEY
read -rsp "PSAR BINANCE_API_SECRET: " PSAR_BINANCE_API_SECRET; echo
read -rp "PSAR TELEGRAM_BOT_TOKEN: " PSAR_TELEGRAM_BOT_TOKEN
read -rp "PSAR TELEGRAM_CHAT_ID: " PSAR_TELEGRAM_CHAT_ID

read -rp "OKX QQQ API KEY: " OKX_QQQ_API_KEY
read -rsp "OKX QQQ API SECRET: " OKX_QQQ_API_SECRET; echo
read -rsp "OKX QQQ API PASSPHRASE: " OKX_QQQ_API_PASSPHRASE; echo
read -rp "OKX QQQ TELEGRAM_BOT_TOKEN (optional): " OKX_QQQ_TELEGRAM_BOT_TOKEN
read -rp "OKX QQQ TELEGRAM_CHAT_ID (optional): " OKX_QQQ_TELEGRAM_CHAT_ID

read -rp "OKX XAU API KEY: " OKX_XAU_API_KEY
read -rsp "OKX XAU API SECRET: " OKX_XAU_API_SECRET; echo
read -rsp "OKX XAU API PASSPHRASE: " OKX_XAU_API_PASSPHRASE; echo
read -rp "OKX XAU TELEGRAM_BOT_TOKEN (optional): " OKX_XAU_TELEGRAM_BOT_TOKEN
read -rp "OKX XAU TELEGRAM_CHAT_ID (optional): " OKX_XAU_TELEGRAM_CHAT_ID

put_secure "${SSM_PREFIX}/psar_rsi/EXECUTION_MODE" "${PSAR_EXECUTION_MODE}"
put_secure "${SSM_PREFIX}/psar_rsi/TV_WEBHOOK_SECRET" "${PSAR_TV_WEBHOOK_SECRET}"
put_secure "${SSM_PREFIX}/psar_rsi/BINANCE_API_KEY" "${PSAR_BINANCE_API_KEY}"
put_secure "${SSM_PREFIX}/psar_rsi/BINANCE_API_SECRET" "${PSAR_BINANCE_API_SECRET}"
put_secure "${SSM_PREFIX}/psar_rsi/TELEGRAM_BOT_TOKEN" "${PSAR_TELEGRAM_BOT_TOKEN}"
put_secure "${SSM_PREFIX}/psar_rsi/TELEGRAM_CHAT_ID" "${PSAR_TELEGRAM_CHAT_ID}"

put_secure "${SSM_PREFIX}/okx_qqq/OKX_API_KEY" "${OKX_QQQ_API_KEY}"
put_secure "${SSM_PREFIX}/okx_qqq/OKX_API_SECRET" "${OKX_QQQ_API_SECRET}"
put_secure "${SSM_PREFIX}/okx_qqq/OKX_API_PASSPHRASE" "${OKX_QQQ_API_PASSPHRASE}"
put_secure "${SSM_PREFIX}/okx_qqq/TELEGRAM_BOT_TOKEN" "${OKX_QQQ_TELEGRAM_BOT_TOKEN}"
put_secure "${SSM_PREFIX}/okx_qqq/TELEGRAM_CHAT_ID" "${OKX_QQQ_TELEGRAM_CHAT_ID}"

put_secure "${SSM_PREFIX}/okx_xau/OKX_API_KEY" "${OKX_XAU_API_KEY}"
put_secure "${SSM_PREFIX}/okx_xau/OKX_API_SECRET" "${OKX_XAU_API_SECRET}"
put_secure "${SSM_PREFIX}/okx_xau/OKX_API_PASSPHRASE" "${OKX_XAU_API_PASSPHRASE}"
put_secure "${SSM_PREFIX}/okx_xau/TELEGRAM_BOT_TOKEN" "${OKX_XAU_TELEGRAM_BOT_TOKEN}"
put_secure "${SSM_PREFIX}/okx_xau/TELEGRAM_CHAT_ID" "${OKX_XAU_TELEGRAM_CHAT_ID}"

echo "SSM parameters created/updated successfully."
echo "Region: $AWS_REGION"
echo "Prefix: $SSM_PREFIX"
