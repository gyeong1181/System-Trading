# AWS EC2 배포 가이드 (초보자용)

이 가이드는 초보자를 위한 단계별 AWS 배포 가이드입니다. 처음엔 간단한 수동 배포로 시작하고, 점진적으로 자동화를 추가할 수 있습니다.

---

## 📋 목차

1. [준비 단계](#1-준비-단계)
2. [AWS EC2 인스턴스 생성](#2-aws-ec2-인스턴스-생성)
3. [서버 초기 설정](#3-서버-초기-설정)
4. [코드 배포](#4-코드-배포)
5. [환경변수 설정](#5-환경변수-설정)
6. [테스트 실행](#6-테스트-실행)
7. [24시간 자동 실행 설정](#7-24시간-자동-실행-설정)
8. [모니터링 및 관리](#8-모니터링-및-관리)
9. [문제 해결](#9-문제-해결)

---

## 1. 준비 단계

### 필요한 것들
- ✅ AWS 계정 (무료 체험 가능)
- ✅ Binance 계정 (API 키 생성 필요 - 페이퍼 모드는 선택사항)
- ✅ 프로젝트 코드 (현재 폴더)
- ✅ SSH 클라이언트 (Windows: PuTTY 또는 PowerShell)

### 프로젝트 파일 확인
다음 파일들이 있는지 확인하세요:
- `btc_trend_follow.py` (메인 파일)
- `exchange.py`, `risk.py`, `indicators.py`, `utils.py`, `reports.py`
- `requirements.txt` (의존성 목록)
- `BTCTrendFollower.service` (systemd 서비스 파일)
- `deploy.sh` (배포 스크립트)

---

## 2. AWS EC2 인스턴스 생성

### 2.1 AWS 콘솔 접속
1. [AWS 콘솔](https://console.aws.amazon.com)에 로그인
2. 상단 검색창에 "EC2" 입력 후 선택

### 2.2 인스턴스 시작
1. 왼쪽 메뉴에서 **"인스턴스"** 클릭
2. **"인스턴스 시작"** 버튼 클릭

### 2.3 인스턴스 설정

#### 이름 및 태그
- **이름**: `BTC-Trend-Follower` (원하는 이름)

#### 애플리케이션 및 OS 이미지
- **Amazon Linux 2023** 선택 (무료 티어 가능)

#### 인스턴스 유형
- **t3.micro** (무료 티어) 또는 **t3.small** (권장, 월 약 $15)
  - 초기 테스트: t3.micro
  - 실제 운용: t3.small 이상

#### 키 페어 (로그인)
- **"새 키 페어 생성"** 클릭
- 이름: `btc-trend-key`
- 키 페어 유형: **RSA**
- 프라이빗 키 파일 형식: **.pem** (Linux/Mac) 또는 **.ppk** (Windows PuTTY)
- **"키 페어 생성"** 클릭 → 자동으로 다운로드됨
- ⚠️ **중요**: 이 키 파일을 안전한 곳에 보관하세요! (다시 다운로드 불가)

#### 네트워크 설정
- **보안 그룹**: "새 보안 그룹 생성" 선택
- **이름**: `btc-trend-sg`
- **인바운드 규칙**:
  - SSH (포트 22): **내 IP** 선택 (또는 특정 IP)
  - 아웃바운드: 기본값 (모두 허용)

#### 스토리지
- **30GB gp3** (기본값 유지)

#### 고급 세부 정보 (선택사항)
- **사용자 데이터**에 다음 스크립트 붙여넣기 (자동 초기 설정):
```bash
#!/bin/bash
dnf update -y
dnf install -y python3 python3-pip python3-venv unzip git
```

### 2.4 인스턴스 시작
1. **"인스턴스 시작"** 버튼 클릭
2. 잠시 후 인스턴스가 **"실행 중"** 상태가 됨
3. **퍼블릭 IPv4 주소**를 복사해두세요 (예: `54.123.45.67`)

---

## 3. 서버 초기 설정

### 3.1 SSH 접속 (Windows PowerShell)

#### 방법 1: PowerShell (Windows 10/11)
```powershell
# 키 파일이 있는 폴더로 이동
cd C:\Users\YourName\Downloads

# 권한 설정 (처음 한 번만)
icacls btc-trend-key.pem /inheritance:r
icacls btc-trend-key.pem /grant:r "$env:USERNAME:R"

# SSH 접속
ssh -i btc-trend-key.pem ec2-user@YOUR_EC2_IP
# 예: ssh -i btc-trend-key.pem ec2-user@54.123.45.67
```

#### 방법 2: PuTTY (Windows)
1. PuTTYgen으로 `.pem` 파일을 `.ppk`로 변환
2. PuTTY에서 호스트 이름: `ec2-user@YOUR_EC2_IP`
3. Connection → SSH → Auth에서 변환한 `.ppk` 파일 선택

### 3.2 서버 업데이트
```bash
sudo dnf update -y
```

---

## 4. 코드 배포

### 방법 A: 간단한 방법 (초보자용) - SCP로 파일 전송

#### Windows PowerShell에서:
```powershell
# 프로젝트 폴더로 이동
cd "D:\코딩\자동매매\AI 자동매매 제작 프로젝트\BTC_trend_follow"

# 모든 파일을 ZIP으로 압축 (수동으로 또는)
# 또는 다음 명령어로 파일들을 개별 전송:

# 필수 파일들 전송
scp -i C:\Users\YourName\Downloads\btc-trend-key.pem *.py ec2-user@YOUR_EC2_IP:/tmp/
scp -i C:\Users\YourName\Downloads\btc-trend-key.pem requirements.txt ec2-user@YOUR_EC2_IP:/tmp/
scp -i C:\Users\YourName\Downloads\btc-trend-key.pem BTCTrendFollower.service ec2-user@YOUR_EC2_IP:/tmp/
scp -i C:\Users\YourName\Downloads\btc-trend-key.pem deploy.sh ec2-user@YOUR_EC2_IP:/tmp/
```

#### EC2 서버에서:
```bash
# 작업 디렉토리 생성
sudo mkdir -p /opt/btc_trend_follow
sudo chown ec2-user:ec2-user /opt/btc_trend_follow

# 파일 이동
mv /tmp/*.py /opt/btc_trend_follow/
mv /tmp/requirements.txt /opt/btc_trend_follow/
mv /tmp/BTCTrendFollower.service /opt/btc_trend_follow/
mv /tmp/deploy.sh /opt/btc_trend_follow/

# 실행 권한 부여
chmod +x /opt/btc_trend_follow/deploy.sh
```

### 방법 B: 배포 스크립트 사용 (권장)
```bash
cd /opt/btc_trend_follow
./deploy.sh
```

스크립트가 자동으로:
- Python 가상환경 생성
- 의존성 설치
- systemd 서비스 설정

---

## 5. 환경변수 설정

### 5.1 .env 파일 생성
```bash
cd /opt/btc_trend_follow
nano .env
```

### 5.2 최소 설정 (페이퍼 모드 - 가짜 돈)
```env
# 페이퍼 모드 (가짜 돈으로 테스트)
BTC_TREND_PAPER_MODE=true

# 전략 설정 (선택사항)
BTC_TREND_SYMBOL=BTCUSDT
BTC_TREND_INTERVAL=4h
BTC_TREND_RISK_PCT=1.0
BTC_TREND_LEVERAGE=1.0
```

**저장**: `Ctrl + O` → Enter → `Ctrl + X`

### 5.3 실거래 모드 설정 (나중에)
```env
# 실거래 모드
BTC_TREND_PAPER_MODE=false

# Binance API 키 (Binance Futures에서 생성)
BINANCE_API_KEY=your_actual_api_key
BINANCE_API_SECRET=your_actual_secret_key

# 전략 설정
BTC_TREND_SYMBOL=BTCUSDT
BTC_TREND_INTERVAL=4h
BTC_TREND_RISK_PCT=1.0
BTC_TREND_LEVERAGE=1.0
```

⚠️ **주의**: 실거래 전에 반드시 페이퍼 모드로 충분히 테스트하세요!

---

## 6. 테스트 실행

### 6.1 가상환경 활성화
```bash
cd /opt/btc_trend_follow
source .venv/bin/activate
```

### 6.2 페이퍼 백테스트 실행
```bash
# 400개 캔들로 백테스트
python btc_trend_follow.py --paper --paper-bars 400
```

정상 작동하면:
- 로그가 출력됨
- `reports/trade_log.csv` 파일 생성
- `reports/equity_curve.csv` 파일 생성

### 6.3 실시간 페이퍼 모드 테스트
```bash
# 실시간 WebSocket 연결 테스트 (가짜 돈)
python btc_trend_follow.py --live --paper
```

**중단**: `Ctrl + C`

정상 작동 확인:
- "Connected to Binance btcusdt stream" 메시지 확인
- 4시간마다 캔들이 업데이트됨

---

## 7. 24시간 자동 실행 설정

### 7.1 systemd 서비스 시작
```bash
# 서비스 활성화 및 시작
sudo systemctl enable BTCTrendFollower
sudo systemctl start BTCTrendFollower

# 상태 확인
sudo systemctl status BTCTrendFollower
```

정상 작동 시:
```
● BTCTrendFollower.service - BTC 추세추종 (AuraBot v1.6.1 Python Trader)
     Loaded: loaded (/etc/systemd/system/BTCTrendFollower.service)
     Active: active (running) since ...
```

### 7.2 자동 재시작 확인
서버 재부팅 시 자동 시작되도록 설정되어 있습니다.

테스트:
```bash
# 서비스 재시작
sudo systemctl restart BTCTrendFollower

# 로그 확인
journalctl -u BTCTrendFollower -n 50
```

---

## 8. 모니터링 및 관리

### 8.1 로그 확인

#### systemd 로그 (실시간)
```bash
# 실시간 로그 보기
journalctl -u BTCTrendFollower -f

# 최근 100줄 보기
journalctl -u BTCTrendFollower -n 100

# 오늘 로그만
journalctl -u BTCTrendFollower --since today
```

#### 파일 로그
```bash
tail -f /opt/btc_trend_follow/logs/btc_trend_follow.log
```

### 8.2 거래 리포트 확인
```bash
# 거래 내역
cat /opt/btc_trend_follow/reports/trade_log.csv

# 자산 곡선
cat /opt/btc_trend_follow/reports/equity_curve.csv
```

### 8.3 서비스 관리 명령어
```bash
# 서비스 시작
sudo systemctl start BTCTrendFollower

# 서비스 중지
sudo systemctl stop BTCTrendFollower

# 서비스 재시작
sudo systemctl restart BTCTrendFollower

# 서비스 상태 확인
sudo systemctl status BTCTrendFollower

# 서비스 비활성화 (재부팅 시 자동 시작 안 함)
sudo systemctl disable BTCTrendFollower
```

---

## 9. 문제 해결

### 문제 1: SSH 접속 안 됨
- **원인**: 보안 그룹에서 내 IP가 허용되지 않음
- **해결**: EC2 콘솔 → 보안 그룹 → 인바운드 규칙에 내 IP 추가

### 문제 2: Python 패키지 설치 실패
```bash
# pip 업그레이드
pip install --upgrade pip

# 개별 설치
pip install pandas numpy httpx websockets python-dotenv
```

### 문제 3: WebSocket 연결 실패
- **원인**: 네트워크 문제 또는 Binance API 장애
- **해결**: 
  - 인터넷 연결 확인: `ping google.com`
  - Binance 상태 확인: [Binance Status](https://www.binance.com/en/support/announcement)

### 문제 4: 서비스가 시작되지 않음
```bash
# 에러 확인
sudo journalctl -u BTCTrendFollower -n 50

# .env 파일 확인
cat /opt/btc_trend_follow/.env

# 수동 실행으로 에러 확인
cd /opt/btc_trend_follow
source .venv/bin/activate
python btc_trend_follow.py --live --paper
```

### 문제 5: 권한 오류
```bash
# 파일 소유권 확인 및 수정
sudo chown -R ec2-user:ec2-user /opt/btc_trend_follow
```

---

## 10. 다음 단계 (고급)

### 10.1 GitHub Actions 자동 배포 (추후)
- 코드 푸시 시 자동 배포
- `docs/CI_CD.md` 참고

### 10.2 CloudWatch 통합 (추후)
- 로그 자동 수집
- 알람 설정

### 10.3 Telegram 알림 (추후)
- 거래 알림
- 에러 알림

---

## 📞 도움말

문제가 발생하면:
1. 로그 확인: `journalctl -u BTCTrendFollower -n 100`
2. 수동 실행으로 에러 확인
3. `docs/OperationsRunbook.md` 참고

---

**축하합니다! 이제 BTC 추세추종 전략이 24시간 자동으로 실행됩니다! 🚀**



