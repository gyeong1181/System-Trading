# 🐳 Docker 기반 BTC 추세추종 자동매매 시스템

## 📚 전체 문서 목록

1. **[아키텍처 설계도](docs/Docker_Architecture.md)** - 전체 시스템 구조 이해
2. **[Docker 배포 가이드](docs/Docker_배포_가이드.md)** - 상세한 배포 절차
3. **[/var에서 /opt로 이동 가이드](docs/var_to_opt_이동_가이드.md)** - 경로 변경 방법

---

## 🚀 빠른 시작 (5분)

### 1. 필수 파일 확인

다음 파일들이 있어야 합니다:
- ✅ `main.py` - Docker용 메인 파일
- ✅ `Dockerfile` - Docker 이미지 빌드 파일
- ✅ `docker-compose.yml` - Docker Compose 설정
- ✅ `requirements.txt` - Python 패키지 목록
- ✅ `.env` - 환경변수 파일

### 2. 환경변수 설정

`.env` 파일 생성:
```env
BTC_TREND_PAPER_MODE=true
BTC_TREND_SYMBOL=BTCUSDT
BTC_TREND_INTERVAL=4h
BTC_TREND_LEVERAGE=3.0
```

### 3. Docker 실행

```bash
# 이미지 빌드
docker-compose build

# 백그라운드 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f
```

---

## 📦 주요 기능

### ✅ Docker 컨테이너 실행
- 격리된 환경에서 실행
- 쉽게 배포 및 관리
- 자동 재시작

### ✅ Telegram 실시간 알림
- 매수/매도 알림
- 손익 알림
- 에러 알림

### ✅ CloudWatch 로그 연동
- 모든 로그 자동 전송
- AWS 콘솔에서 확인

### ✅ S3 자동 백업
- 거래 로그 CSV 백업
- 자산 곡선 CSV 백업
- 주기적 자동 업로드

---

## 📖 상세 가이드

자세한 내용은 [Docker 배포 가이드](docs/Docker_배포_가이드.md)를 참고하세요.

---

## 🔧 주요 명령어

```bash
# 컨테이너 상태 확인
docker-compose ps

# 로그 확인
docker-compose logs -f

# 재시작
docker-compose restart

# 중지
docker-compose stop

# 시작
docker-compose start

# 중지 및 삭제
docker-compose down
```

---

## 📞 지원

문제가 발생하면:
1. 로그 확인: `docker-compose logs -f`
2. [문제 해결 섹션](docs/Docker_배포_가이드.md#13-문제-해결) 참고

---

**축하합니다! Docker 기반 자동매매 시스템이 준비되었습니다! 🎉**

