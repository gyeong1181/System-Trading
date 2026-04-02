#!/usr/bin/env bash
set -euo pipefail

echo "[1/5] 패키지 목록을 갱신합니다."
sudo apt-get update

echo "[2/5] 필수 패키지를 설치합니다."
sudo apt-get install -y docker.io docker-compose-plugin make python3 python3-pip python3-venv curl

echo "[3/5] Docker 서비스를 활성화합니다."
sudo systemctl enable --now docker

echo "[4/5] 현재 사용자를 docker 그룹에 추가합니다."
sudo usermod -aG docker "$USER" || true

echo "[5/5] Python 의존성을 설치합니다."
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

echo "설치가 끝났습니다. 다음 순서로 진행하세요."
echo "1. cp .env.example .env"
echo "2. .env 값 입력"
echo "3. make bootstrap"
echo "4. make research-all"
echo "5. make paper-start"
