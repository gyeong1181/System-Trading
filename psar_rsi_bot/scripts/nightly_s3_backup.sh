#!/usr/bin/env bash
set -euo pipefail

# Nightly backup script for source code and trading logs.
# Intended for Linux servers such as the Seoul EC2 instance.
#
# Example:
#   export S3_URI="s3://my-backup-bucket/systemTrading"
#   bash /home/ec2-user/systemTrading/psar_rsi_bot/scripts/nightly_s3_backup.sh
#
# Optional environment variables:
#   PROJECT_ROOT       Default: /home/ec2-user/systemTrading
#   LOG_ROOT           Default: ${PROJECT_ROOT}/psar_rsi_bot/logs
#   LOCAL_BACKUP_DIR   Default: /home/ec2-user/backups/nightly
#   AWS_CLI_BIN        Default: aws
#   S3_URI             Required. Example: s3://my-bucket/trading-backups

PROJECT_ROOT="${PROJECT_ROOT:-/home/ec2-user/systemTrading}"
LOG_ROOT="${LOG_ROOT:-${PROJECT_ROOT}/psar_rsi_bot/logs}"
LOCAL_BACKUP_DIR="${LOCAL_BACKUP_DIR:-/home/ec2-user/backups/nightly}"
AWS_CLI_BIN="${AWS_CLI_BIN:-aws}"
S3_URI="${S3_URI:-}"

if [[ -z "${S3_URI}" ]]; then
  echo "[backup] S3_URI is required. Example: s3://my-bucket/trading-backups" >&2
  exit 1
fi

if ! command -v "${AWS_CLI_BIN}" >/dev/null 2>&1; then
  echo "[backup] aws CLI not found: ${AWS_CLI_BIN}" >&2
  exit 1
fi

if [[ ! -d "${PROJECT_ROOT}" ]]; then
  echo "[backup] project root not found: ${PROJECT_ROOT}" >&2
  exit 1
fi

if [[ ! -d "${LOG_ROOT}" ]]; then
  echo "[backup] log root not found: ${LOG_ROOT}" >&2
  exit 1
fi

TS="$(TZ=Asia/Seoul date +%Y%m%d_%H%M%S)"
HOST_TAG="$(hostname -s)"
mkdir -p "${LOCAL_BACKUP_DIR}"
WORK_DIR="$(mktemp -d "${LOCAL_BACKUP_DIR}/nightly_${TS}_XXXX")"
ARCHIVE_NAME="${HOST_TAG}_source_logs_${TS}.tar.gz"
ARCHIVE_PATH="${LOCAL_BACKUP_DIR}/${ARCHIVE_NAME}"
S3_OBJECT_URI="${S3_URI%/}/${HOST_TAG}/${ARCHIVE_NAME}"
mkdir -p "${WORK_DIR}/source" "${WORK_DIR}/logs"

echo "[backup] collecting source from ${PROJECT_ROOT}"
rsync -a \
  --exclude ".git/" \
  --exclude ".github/" \
  --exclude ".venv/" \
  --exclude "venv/" \
  --exclude "__pycache__/" \
  --exclude ".pytest_cache/" \
  --exclude ".mypy_cache/" \
  --exclude "node_modules/" \
  --exclude "*.pyc" \
  --exclude ".env" \
  --exclude ".env.*" \
  --exclude "infra/terraform/terraform.tfvars" \
  --exclude "infra/terraform/scripts/ssm-secrets.local.env" \
  --exclude "psar_rsi_bot/logs/" \
  "${PROJECT_ROOT}/" "${WORK_DIR}/source/"

echo "[backup] collecting logs from ${LOG_ROOT}"
rsync -a "${LOG_ROOT}/" "${WORK_DIR}/logs/"

echo "[backup] creating archive ${ARCHIVE_PATH}"
tar -C "${WORK_DIR}" -czf "${ARCHIVE_PATH}" source logs

echo "[backup] uploading to ${S3_OBJECT_URI}"
"${AWS_CLI_BIN}" s3 cp "${ARCHIVE_PATH}" "${S3_OBJECT_URI}"

rm -rf "${WORK_DIR}"

echo "[backup] completed successfully"
echo "[backup] archive: ${ARCHIVE_PATH}"
echo "[backup] s3: ${S3_OBJECT_URI}"
