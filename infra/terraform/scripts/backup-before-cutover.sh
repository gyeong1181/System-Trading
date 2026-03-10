#!/usr/bin/env bash
set -euo pipefail

# Backup script to run on the existing server before Terraform cutover.
# Usage:
#   bash backup-before-cutover.sh
#   BACKUP_DIR=/home/ec2-user/backups S3_URI=s3://my-bucket/trading-backups bash backup-before-cutover.sh

TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="${BACKUP_DIR:-/home/ec2-user/backups}"
WORK_DIR="${BACKUP_DIR}/trading_backup_${TS}"
ARCHIVE_PATH="${BACKUP_DIR}/trading_backup_${TS}.tar.gz"
S3_URI="${S3_URI:-}"

APP_ROOT="${APP_ROOT:-/home/ec2-user/systemTrading/psar_rsi_bot}"
MONITOR_ROOT="${MONITOR_ROOT:-${APP_ROOT}/deploy/monitoring}"
STACK_ROOT="${STACK_ROOT:-/opt/trading-stack}"

mkdir -p "${WORK_DIR}"
mkdir -p "${BACKUP_DIR}"

copy_if_exists() {
  local src="$1"
  local dst="$2"
  if [ -e "$src" ]; then
    mkdir -p "$(dirname "$dst")"
    cp -a "$src" "$dst"
    echo "[backup] copied: $src"
  else
    echo "[backup] skip (not found): $src"
  fi
}

# App data
copy_if_exists "${APP_ROOT}/logs" "${WORK_DIR}/app/logs"
copy_if_exists "${APP_ROOT}/data/bot.db" "${WORK_DIR}/app/data/bot.db"
copy_if_exists "${APP_ROOT}/.env" "${WORK_DIR}/app/env/.env"

# Monitoring config/data
copy_if_exists "${MONITOR_ROOT}/docker-compose.monitoring.yml" "${WORK_DIR}/monitoring/docker-compose.monitoring.yml"
copy_if_exists "${MONITOR_ROOT}/prometheus/prometheus.yml" "${WORK_DIR}/monitoring/prometheus/prometheus.yml"
copy_if_exists "${MONITOR_ROOT}/prometheus/data" "${WORK_DIR}/monitoring/prometheus/data"
copy_if_exists "${MONITOR_ROOT}/grafana/data" "${WORK_DIR}/monitoring/grafana/data"
copy_if_exists "${MONITOR_ROOT}/grafana/provisioning" "${WORK_DIR}/monitoring/grafana/provisioning"

# Strategy stack env/config
copy_if_exists "${STACK_ROOT}/docker-compose.yml" "${WORK_DIR}/stack/docker-compose.yml"
copy_if_exists "${STACK_ROOT}/env" "${WORK_DIR}/stack/env"

# Systemd units (may require sudo depending on file perms)
if [ -e "/etc/systemd/system/psar_rsi_bot.service" ]; then
  sudo cp -a /etc/systemd/system/psar_rsi_bot.service "${WORK_DIR}/systemd/psar_rsi_bot.service"
  echo "[backup] copied: /etc/systemd/system/psar_rsi_bot.service"
fi
if [ -e "/etc/systemd/system/trading-strategy-stack.service" ]; then
  sudo cp -a /etc/systemd/system/trading-strategy-stack.service "${WORK_DIR}/systemd/trading-strategy-stack.service"
  echo "[backup] copied: /etc/systemd/system/trading-strategy-stack.service"
fi
if [ -e "/etc/systemd/system/trading-env-sync.service" ]; then
  sudo cp -a /etc/systemd/system/trading-env-sync.service "${WORK_DIR}/systemd/trading-env-sync.service"
  echo "[backup] copied: /etc/systemd/system/trading-env-sync.service"
fi

tar -C "${BACKUP_DIR}" -czf "${ARCHIVE_PATH}" "trading_backup_${TS}"
echo "[backup] archive created: ${ARCHIVE_PATH}"

if [ -n "${S3_URI}" ]; then
  aws s3 cp "${ARCHIVE_PATH}" "${S3_URI%/}/"
  echo "[backup] uploaded to S3: ${S3_URI%/}/$(basename "${ARCHIVE_PATH}")"
fi

echo "[backup] done"
