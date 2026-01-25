# 📁 /var에서 /opt로 이동 가이드

현재 `/var/btc_trend_follow`에 설치되어 있는 경우, 권장 경로인 `/opt/btc_trend_follow`로 이동하는 방법입니다.

---

## ⚠️ 주의사항

- **서비스 중지**: 이동 전에 반드시 서비스를 중지해야 합니다.
- **백업**: 중요한 데이터가 있으면 백업하세요.
- **시간**: 약 5-10분 소요

---

## 📋 이동 절차

### 1단계: 서비스 중지

```bash
# systemd 서비스 중지 (기존 방식)
sudo systemctl stop BTCTrendFollower

# 또는 Docker 사용 중이면
cd /var/btc_trend_follow
docker-compose down
```

### 2단계: 현재 상태 확인

```bash
# 현재 위치 확인
ls -la /var/btc_trend_follow

# 파일 목록 확인
du -sh /var/btc_trend_follow
```

### 3단계: 새 디렉토리 생성

```bash
# /opt에 새 디렉토리 생성
sudo mkdir -p /opt/btc_trend_follow
sudo chown ec2-user:ec2-user /opt/btc_trend_follow
```

### 4단계: 파일 복사

```bash
# 모든 파일 복사
sudo cp -r /var/btc_trend_follow/* /opt/btc_trend_follow/

# 권한 설정
sudo chown -R ec2-user:ec2-user /opt/btc_trend_follow
```

### 5단계: 파일 확인

```bash
# 복사 확인
ls -la /opt/btc_trend_follow

# 주요 파일 확인
ls -la /opt/btc_trend_follow/*.py
ls -la /opt/btc_trend_follow/.env
```

### 6단계: 설정 파일 수정

#### systemd 사용 시

```bash
# 서비스 파일 수정
sudo nano /etc/systemd/system/BTCTrendFollower.service
```

다음 내용으로 수정:
```ini
[Service]
WorkingDirectory=/opt/btc_trend_follow
EnvironmentFile=/opt/btc_trend_follow/.env
ExecStart=/opt/btc_trend_follow/.venv/bin/python3 btc_trend_follow.py --live --paper
```

저장: `Ctrl + O` → Enter → `Ctrl + X`

```bash
# systemd 재로드
sudo systemctl daemon-reload
```

#### Docker 사용 시

```bash
# docker-compose.yml 확인
cd /opt/btc_trend_follow
cat docker-compose.yml

# 경로는 상대 경로이므로 수정 불필요 (현재 디렉토리 기준)
```

### 7단계: 테스트 실행

#### systemd 사용 시

```bash
# 가상환경 활성화
cd /opt/btc_trend_follow
source .venv/bin/activate

# 수동 실행 테스트
python btc_trend_follow.py --paper --paper-bars 10
```

#### Docker 사용 시

```bash
cd /opt/btc_trend_follow

# Docker 빌드 (필요시)
docker-compose build

# 테스트 실행
docker-compose up
```

**중단**: `Ctrl + C`

### 8단계: 서비스 시작

#### systemd 사용 시

```bash
# 서비스 시작
sudo systemctl start BTCTrendFollower

# 상태 확인
sudo systemctl status BTCTrendFollower

# 로그 확인
journalctl -u BTCTrendFollower -f
```

#### Docker 사용 시

```bash
# 백그라운드 실행
docker-compose up -d

# 상태 확인
docker-compose ps

# 로그 확인
docker-compose logs -f
```

### 9단계: 기존 디렉토리 정리 (선택사항)

**⚠️ 중요**: 서비스가 정상 작동하는지 최소 1일 이상 확인한 후에 기존 디렉토리를 삭제하세요.

```bash
# 1일 후 실행 (서비스 정상 작동 확인 후)
# 기존 디렉토리 백업 (선택사항)
sudo mv /var/btc_trend_follow /var/btc_trend_follow.backup

# 또는 삭제
sudo rm -rf /var/btc_trend_follow
```

---

## 🔄 빠른 이동 스크립트

전체 과정을 한 번에 실행하는 스크립트:

```bash
#!/bin/bash
# /var에서 /opt로 이동 스크립트

set -e  # 에러 발생 시 중단

echo "=========================================="
echo "/var에서 /opt로 이동 시작"
echo "=========================================="

# 1. 서비스 중지
echo "[1/8] 서비스 중지 중..."
sudo systemctl stop BTCTrendFollower 2>/dev/null || true
cd /var/btc_trend_follow 2>/dev/null && docker-compose down 2>/dev/null || true

# 2. 새 디렉토리 생성
echo "[2/8] 새 디렉토리 생성 중..."
sudo mkdir -p /opt/btc_trend_follow
sudo chown ec2-user:ec2-user /opt/btc_trend_follow

# 3. 파일 복사
echo "[3/8] 파일 복사 중..."
sudo cp -r /var/btc_trend_follow/* /opt/btc_trend_follow/ 2>/dev/null || true
sudo chown -R ec2-user:ec2-user /opt/btc_trend_follow

# 4. systemd 서비스 파일 수정
echo "[4/8] systemd 서비스 파일 수정 중..."
if [ -f /etc/systemd/system/BTCTrendFollower.service ]; then
    sudo sed -i 's|/var/btc_trend_follow|/opt/btc_trend_follow|g' /etc/systemd/system/BTCTrendFollower.service
    sudo systemctl daemon-reload
fi

# 5. 테스트
echo "[5/8] 테스트 실행 중..."
cd /opt/btc_trend_follow
if [ -d .venv ]; then
    source .venv/bin/activate
    python btc_trend_follow.py --paper --paper-bars 5 > /dev/null 2>&1 || echo "테스트 경고: 수동 확인 필요"
fi

# 6. 서비스 시작
echo "[6/8] 서비스 시작 중..."
sudo systemctl start BTCTrendFollower 2>/dev/null || true
cd /opt/btc_trend_follow && docker-compose up -d 2>/dev/null || true

# 7. 상태 확인
echo "[7/8] 상태 확인 중..."
sleep 3
sudo systemctl status BTCTrendFollower --no-pager || docker-compose ps || true

# 8. 완료
echo "[8/8] 완료!"
echo ""
echo "=========================================="
echo "이동 완료!"
echo "=========================================="
echo ""
echo "새 위치: /opt/btc_trend_follow"
echo ""
echo "다음 단계:"
echo "1. 서비스 상태 확인:"
echo "   sudo systemctl status BTCTrendFollower"
echo "   또는"
echo "   docker-compose ps"
echo ""
echo "2. 로그 확인:"
echo "   journalctl -u BTCTrendFollower -f"
echo "   또는"
echo "   docker-compose logs -f"
echo ""
echo "3. 1일 후 기존 디렉토리 삭제 (선택사항):"
echo "   sudo rm -rf /var/btc_trend_follow"
```

**사용 방법:**
```bash
# 스크립트 저장
nano /tmp/move_to_opt.sh
# (위 내용 붙여넣기)
# Ctrl+O, Enter, Ctrl+X

# 실행 권한 부여
chmod +x /tmp/move_to_opt.sh

# 실행
/tmp/move_to_opt.sh
```

---

## ✅ 이동 완료 체크리스트

- [ ] 파일이 `/opt/btc_trend_follow`에 복사됨
- [ ] 서비스 파일 경로가 수정됨
- [ ] 테스트 실행 성공
- [ ] 서비스가 정상 시작됨
- [ ] 로그가 정상 출력됨
- [ ] 1일 후 기존 디렉토리 삭제 (선택사항)

---

## 🆘 문제 해결

### 문제 1: 권한 오류

```bash
# 소유권 재설정
sudo chown -R ec2-user:ec2-user /opt/btc_trend_follow
```

### 문제 2: 서비스가 시작되지 않음

```bash
# 로그 확인
sudo journalctl -u BTCTrendFollower -n 50

# 수동 실행으로 에러 확인
cd /opt/btc_trend_follow
source .venv/bin/activate
python btc_trend_follow.py --live --paper
```

### 문제 3: 파일이 없음

```bash
# 복사 재시도
sudo cp -r /var/btc_trend_follow/* /opt/btc_trend_follow/
```

---

**이동 완료 후 기존 디렉토리는 최소 1일 이상 보관한 후 삭제하세요!** 🎯

