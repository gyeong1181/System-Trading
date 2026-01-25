# 🐳 Docker 기반 AWS 자동매매 시스템 배포 가이드

## 📋 목차

1. [전체 시스템 개요](#1-전체-시스템-개요)
2. [필요한 준비물](#2-필요한-준비물)
3. [AWS EC2 인스턴스 생성](#3-aws-ec2-인스턴스-생성)
4. [Amazon Linux 2023 초기 설정](#4-amazon-linux-2023-초기-설정)
5. [Docker 설치](#5-docker-설치)
6. [코드 배포](#6-코드-배포)
7. [환경변수 설정](#7-환경변수-설정)
8. [Docker 실행](#8-docker-실행)
9. [CloudWatch 설정](#9-cloudwatch-설정)
10. [S3 버킷 생성](#10-s3-버킷-생성)
11. [Telegram 봇 설정](#11-telegram-봇-설정)
12. [모니터링 및 관리](#12-모니터링-및-관리)
13. [문제 해결](#13-문제-해결)

---

## 1. 전체 시스템 개요

이 시스템은 Docker 컨테이너에서 실행되는 자동매매 봇입니다.

**주요 기능:**
- ✅ Docker 컨테이너에서 격리 실행
- ✅ Telegram 실시간 알림
- ✅ CloudWatch 로그 자동 전송
- ✅ S3 자동 백업
- ✅ 24시간 자동 재시작

---

## 2. 필요한 준비물

### 필수
- ✅ AWS 계정
- ✅ Binance 계정 (API 키)
- ✅ Telegram 계정 (봇 토큰)

### 선택사항
- CloudWatch Logs (무료 티어 있음)
- S3 버킷 (무료 티어 있음)

---

## 3. AWS EC2 인스턴스 생성

### 3.1 EC2 콘솔 접속
1. [AWS 콘솔](https://console.aws.amazon.com) 로그인
2. "EC2" 검색 후 선택

### 3.2 인스턴스 시작
1. "인스턴스 시작" 클릭
2. 설정:
   - **이름**: `btc-trend-docker`
   - **OS**: **Amazon Linux 2023** 선택
   - **인스턴스 타입**: t3.small (또는 t3.micro)
   - **키 페어**: 새로 생성 (`.pem` 파일 다운로드 필수!)
   - **보안 그룹**: SSH (포트 22) - 내 IP만 허용
   - **스토리지**: 30GB gp3

3. "인스턴스 시작" 클릭
4. **퍼블릭 IPv4 주소** 복사 (예: `54.123.45.67`)

---

## 4. Amazon Linux 2023 초기 설정

### 4.1 SSH 접속

**Windows PowerShell:**
```powershell
# 키 파일 폴더로 이동
cd C:\Users\YourName\Downloads

# 권한 설정 (처음 한 번만)
icacls your-key.pem /inheritance:r
icacls your-key.pem /grant:r "$env:USERNAME:R"

# SSH 접속
ssh -i your-key.pem ec2-user@YOUR_EC2_IP
```

### 4.2 시스템 업데이트

```bash
# 시스템 업데이트
sudo dnf update -y

# 필수 도구 설치
sudo dnf install -y git unzip
```

---

## 5. Docker 설치

### 5.1 Docker 설치

```bash
# Docker 설치
sudo dnf install -y docker

# Docker 서비스 시작
sudo systemctl start docker
sudo systemctl enable docker

# 현재 사용자를 docker 그룹에 추가 (sudo 없이 사용하기)
sudo usermod -aG docker ec2-user

# 설치 확인
docker --version
```

**중요**: 그룹 추가 후 **로그아웃 후 다시 로그인**해야 적용됩니다.

```bash
# 로그아웃
exit

# 다시 SSH 접속
ssh -i your-key.pem ec2-user@YOUR_EC2_IP
```

### 5.2 Docker Compose 설치

```bash
# Docker Compose 설치
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose

# 실행 권한 부여
sudo chmod +x /usr/local/bin/docker-compose

# 설치 확인
docker-compose --version
```

---

## 6. 코드 배포

### 6.1 작업 디렉토리 생성

```bash
# 작업 디렉토리 생성
sudo mkdir -p /opt/btc_trend_follow
sudo chown ec2-user:ec2-user /opt/btc_trend_follow
cd /opt/btc_trend_follow
```

### 6.2 파일 업로드 (FileZilla 사용)

**FileZilla 설정:**
1. 호스트: `sftp://YOUR_EC2_IP`
2. 사용자명: `ec2-user`
3. 포트: `22`
4. 키 파일: `.pem` 파일 선택 (편집 → 설정 → SFTP)

**전송할 파일들:**
- 모든 `.py` 파일
- `requirements.txt`
- `Dockerfile`
- `docker-compose.yml`
- `.env` 파일 (또는 나중에 생성)

**전송 위치:** `/opt/btc_trend_follow/`

### 6.3 디렉토리 구조 확인

```bash
cd /opt/btc_trend_follow
ls -la

# 다음 파일들이 있어야 함:
# - main.py
# - btc_trend_follow.py
# - exchange.py
# - indicators.py
# - risk.py
# - utils.py
# - reports.py
# - notifier.py
# - storage.py
# - logger.py
# - requirements.txt
# - Dockerfile
# - docker-compose.yml
```

---

## 7. 환경변수 설정

### 7.1 .env 파일 생성

```bash
cd /opt/btc_trend_follow
nano .env
```

### 7.2 최소 설정 (페이퍼 모드)

```env
# 거래 모드
BTC_TREND_PAPER_MODE=true

# 전략 설정
BTC_TREND_SYMBOL=BTCUSDT
BTC_TREND_INTERVAL=4h
BTC_TREND_RISK_PCT=1.0
BTC_TREND_LEVERAGE=3.0

# 페이퍼 모드 초기 자산
PAPER_STARTING_EQUITY=10000.0

# Telegram 알림 (선택사항)
# TELEGRAM_BOT_TOKEN=your_bot_token
# TELEGRAM_CHAT_ID=your_chat_id

# CloudWatch 로그 (선택사항)
# CLOUDWATCH_LOG_GROUP=btc-trend-logs

# S3 백업 (선택사항)
# S3_BUCKET_NAME=btc-trend-backup
```

**저장**: `Ctrl + O` → Enter → `Ctrl + X`

### 7.3 실거래 모드 설정 (나중에)

```env
# 실거래 모드
BTC_TREND_PAPER_MODE=false

# Binance API 키
BINANCE_API_KEY=your_actual_api_key
BINANCE_API_SECRET=your_actual_secret_key

# 나머지 설정은 동일
```

---

## 8. Docker 실행

### 8.1 Docker 이미지 빌드

```bash
cd /opt/btc_trend_follow

# Docker 이미지 빌드
docker-compose build
```

**빌드 시간**: 약 2-5분 소요

### 8.2 Docker 컨테이너 실행

```bash
# 백그라운드에서 실행
docker-compose up -d

# 실행 상태 확인
docker-compose ps

# 로그 확인
docker-compose logs -f
```

**정상 작동 시:**
```
btc-trend-follower | 2025-11-18 02:17:09 | INFO | BTCTrendFollower | Bootstrapped 500 candles via REST
btc-trend-follower | 2025-11-18 02:17:09 | INFO | BTCTrendFollower | Connected to Binance btcusdt stream
```

### 8.3 자동 재시작 설정

`docker-compose.yml`에 이미 `restart: unless-stopped`가 설정되어 있어서, 서버 재부팅 시 자동으로 시작됩니다.

---

## 9. CloudWatch 설정

### 9.1 IAM 역할 설정 (EC2에서 자동 인식)

1. EC2 콘솔 → 인스턴스 선택 → "보안" 탭
2. "IAM 역할" 클릭 → "역할 수정"
3. 새 역할 생성 또는 기존 역할 선택

**필요한 권한:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
```

### 9.2 .env 파일에 추가

```env
CLOUDWATCH_LOG_GROUP=btc-trend-logs
```

### 9.3 로그 확인

**AWS 콘솔:**
1. CloudWatch → Logs → Log groups
2. `btc-trend-logs` 선택
3. 실시간 로그 확인

**또는 Docker 로그:**
```bash
docker-compose logs -f
```

---

## 10. S3 버킷 생성

### 10.1 S3 버킷 생성

1. AWS 콘솔 → S3
2. "버킷 만들기" 클릭
3. 설정:
   - **버킷 이름**: `btc-trend-backup-YYYYMMDD` (고유한 이름)
   - **리전**: ap-northeast-2 (서울)
   - **퍼블릭 액세스**: 모두 차단
4. "버킷 만들기" 클릭

### 10.2 IAM 권한 추가

EC2 IAM 역할에 S3 권한 추가:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::btc-trend-backup-*",
        "arn:aws:s3:::btc-trend-backup-*/*"
      ]
    }
  ]
}
```

### 10.3 .env 파일에 추가

```env
S3_BUCKET_NAME=btc-trend-backup-YYYYMMDD
```

### 10.4 백업 확인

```bash
# 수동 백업 테스트
docker-compose exec btc-trend-bot python -c "from storage import S3Storage; s = S3Storage(); s.backup_reports()"
```

---

## 11. Telegram 봇 설정

### 11.1 Telegram 봇 생성

1. Telegram 앱에서 `@BotFather` 검색
2. `/newbot` 명령어 입력
3. 봇 이름 입력 (예: `My Trading Bot`)
4. 봇 사용자명 입력 (예: `my_trading_bot`)
5. **토큰 복사** (예: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 11.2 Chat ID 확인

1. 생성한 봇에게 메시지 보내기 (아무 메시지나)
2. 브라우저에서 다음 URL 접속:
   ```
   https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
   ```
3. JSON 응답에서 `"chat":{"id":123456789}` 찾기
4. **Chat ID 복사**

### 11.3 .env 파일에 추가

```env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789
```

### 11.4 알림 테스트

```bash
# 컨테이너 재시작 (환경변수 적용)
docker-compose restart

# 로그 확인
docker-compose logs -f
```

거래 발생 시 Telegram으로 알림이 전송됩니다!

---

## 12. 모니터링 및 관리

### 12.1 Docker 명령어

```bash
# 컨테이너 상태 확인
docker-compose ps

# 로그 확인 (실시간)
docker-compose logs -f

# 로그 확인 (최근 100줄)
docker-compose logs --tail=100

# 컨테이너 재시작
docker-compose restart

# 컨테이너 중지
docker-compose stop

# 컨테이너 시작
docker-compose start

# 컨테이너 중지 및 삭제
docker-compose down
```

### 12.2 리포트 확인

```bash
# 거래 로그 확인
cat /opt/btc_trend_follow/reports/trade_log.csv

# 자산 곡선 확인
cat /opt/btc_trend_follow/reports/equity_curve.csv
```

### 12.3 CloudWatch 로그 확인

AWS 콘솔 → CloudWatch → Logs → `btc-trend-logs`

### 12.4 S3 백업 확인

AWS 콘솔 → S3 → 버킷 → `reports/` 폴더

---

## 13. 문제 해결

### 문제 1: Docker 빌드 실패

```bash
# 에러 로그 확인
docker-compose build --no-cache

# Python 패키지 문제인 경우
# requirements.txt 확인
cat requirements.txt
```

### 문제 2: 컨테이너가 시작되지 않음

```bash
# 상세 로그 확인
docker-compose logs

# 컨테이너 내부 접속
docker-compose exec btc-trend-bot /bin/bash

# 수동 실행 테스트
docker-compose run --rm btc-trend-bot python main.py
```

### 문제 3: Telegram 알림이 안 옴

```bash
# .env 파일 확인
cat .env | grep TELEGRAM

# 토큰 테스트
curl "https://api.telegram.org/bot<YOUR_TOKEN>/getMe"
```

### 문제 4: CloudWatch 로그가 안 보임

```bash
# IAM 역할 확인
aws sts get-caller-identity

# CloudWatch 권한 확인
aws logs describe-log-groups
```

### 문제 5: S3 백업 실패

```bash
# S3 권한 확인
aws s3 ls s3://your-bucket-name/

# 수동 백업 테스트
docker-compose exec btc-trend-bot python -c "from storage import S3Storage; s = S3Storage(); print(s.enabled)"
```

---

## ✅ 완료!

이제 Docker 기반 자동매매 시스템이 24시간 실행됩니다! 🚀

**다음 단계:**
1. 페이퍼 모드로 충분히 테스트
2. 실거래 모드로 전환 (신중하게!)
3. 정기적으로 리포트 확인
4. CloudWatch에서 모니터링

---

**문제가 있으면 로그를 확인하세요:**
```bash
docker-compose logs -f
```

