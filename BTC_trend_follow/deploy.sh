#!/bin/bash
# BTC 추세추종 전략 배포 스크립트 (초보자용)
# EC2 서버에서 실행하는 스크립트입니다

set -e  # 에러 발생 시 중단

echo "=========================================="
echo "BTC 추세추종 전략 배포 시작"
echo "=========================================="

# 작업 디렉토리 설정
WORK_DIR="/opt/btc_trend_follow"
VENV_DIR="$WORK_DIR/.venv"

# 1. 디렉토리 생성
echo "[1/6] 작업 디렉토리 생성 중..."
sudo mkdir -p "$WORK_DIR"
sudo chown $USER:$USER "$WORK_DIR"
cd "$WORK_DIR"

# 2. Python 및 필수 패키지 설치 확인
echo "[2/6] Python 환경 확인 중..."
if ! command -v python3 &> /dev/null; then
    echo "Python3가 설치되어 있지 않습니다. 설치 중..."
    sudo apt update
    sudo apt install -y python3 python3-pip python3-venv unzip
fi

# 3. 가상환경 생성 및 활성화
echo "[3/6] Python 가상환경 설정 중..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

# 4. 의존성 설치
echo "[4/6] Python 패키지 설치 중..."
pip install --upgrade pip
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo "경고: requirements.txt를 찾을 수 없습니다. 기본 패키지를 설치합니다."
    pip install pandas numpy httpx websockets python-dotenv
fi

# 5. .env 파일 확인
echo "[5/6] 환경변수 파일 확인 중..."
if [ ! -f "$WORK_DIR/.env" ]; then
    echo "경고: .env 파일이 없습니다!"
    echo "다음 명령어로 .env 파일을 생성하세요:"
    echo "  nano $WORK_DIR/.env"
    echo ""
    echo "최소한 다음 내용을 포함해야 합니다:"
    echo "  BTC_TREND_PAPER_MODE=true"
    echo "  (실거래 시: BINANCE_API_KEY, BINANCE_API_SECRET 추가)"
    read -p ".env 파일을 지금 생성하시겠습니까? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        nano "$WORK_DIR/.env"
    fi
fi

# 6. systemd 서비스 설정
echo "[6/6] systemd 서비스 설정 중..."
if [ -f "BTCTrendFollower.service" ]; then
    sudo cp BTCTrendFollower.service /etc/systemd/system/BTCTrendFollower.service
    sudo systemctl daemon-reload
    echo "systemd 서비스 파일이 복사되었습니다."
    echo ""
    echo "다음 명령어로 서비스를 시작하세요:"
    echo "  sudo systemctl enable BTCTrendFollower"
    echo "  sudo systemctl start BTCTrendFollower"
    echo "  sudo systemctl status BTCTrendFollower"
else
    echo "경고: BTCTrendFollower.service 파일을 찾을 수 없습니다."
fi

echo ""
echo "=========================================="
echo "배포 완료!"
echo "=========================================="
echo ""
echo "다음 단계:"
echo "1. .env 파일 확인 및 수정 (필요시)"
echo "2. 테스트 실행:"
echo "   cd $WORK_DIR"
echo "   source .venv/bin/activate"
echo "   python btc_trend_follow.py --paper --paper-bars 100"
echo "3. systemd 서비스 시작:"
echo "   sudo systemctl enable --now BTCTrendFollower"
echo "4. 로그 확인:"
echo "   journalctl -u BTCTrendFollower -f"
echo "   또는"
echo "   tail -f $WORK_DIR/logs/btc_trend_follow.log"



