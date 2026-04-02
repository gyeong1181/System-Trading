#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_NAME="bybit-paper-trader.service"

echo "[1/7] t2.micro 계열에서도 빌드가 버티도록 swap 을 점검합니다."
if ! sudo swapon --show | grep -q '^/swapfile'; then
  sudo fallocate -l 2G /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=2048
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  if ! grep -q '^/swapfile ' /etc/fstab; then
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab > /dev/null
  fi
fi

echo "[2/7] apt 패키지 목록을 갱신합니다."
sudo apt-get update

echo "[3/7] Docker와 필수 도구를 설치합니다."
sudo apt-get install -y docker.io docker-compose-plugin git make curl

echo "[4/7] Docker 서비스를 활성화합니다."
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER" || true

echo "[5/7] .env 파일이 없으면 기본값으로 생성합니다."
if [ ! -f "$REPO_DIR/.env" ]; then
  cp "$REPO_DIR/.env.example" "$REPO_DIR/.env"
fi

echo "[6/7] systemd 서비스를 설치합니다."
sudo tee "/etc/systemd/system/${SERVICE_NAME}" > /dev/null <<EOF
[Unit]
Description=Bybit Paper Trader
After=network-online.target docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=${REPO_DIR}
Environment=TRADER_COMMAND=paper-start
ExecStart=/usr/bin/docker compose up -d --build
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

echo "[7/7] 서비스를 활성화하고 시작합니다."
sudo systemctl daemon-reload
sudo systemctl enable --now "${SERVICE_NAME}"

echo "설치가 끝났습니다."
echo "상태 확인: sudo systemctl status ${SERVICE_NAME}"
echo "로그 확인: cd ${REPO_DIR} && docker compose logs -f"
