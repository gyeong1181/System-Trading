# Operations Checklist (Post-Deploy / Post-Change)

배포 직후 또는 설정 변경 직후 매번 같은 순서로 점검하기 위한 Runbook입니다.  
기본 원칙은 `코드 반영 -> 서비스 상태 -> 애플리케이션 상태 -> 모니터링 상태 -> 웹훅 경로` 순서입니다.

## 0) 작업 디렉터리
```bash
cd /home/ec2-user/systemTrading/psar_rsi_bot
```

## 1) 코드/의존성 반영
```bash
git pull origin main
pip install -r requirements.txt
```

주의:
- `requirements.txt` 변경이 없으면 `pip install`은 생략 가능
- `.env` 변경이 있었다면 서비스 재시작은 필수

## 2) 서비스 재시작
```bash
sudo systemctl daemon-reload
sudo systemctl restart psar_rsi_bot
```

## 3) 서비스 상태 확인 (필수)
```bash
sudo systemctl status psar_rsi_bot --no-pager -l
sudo journalctl -u psar_rsi_bot -n 100 --no-pager
```

정상 기준:
- `Active: active (running)`
- Traceback / ModuleNotFoundError / ImportError 없음

## 4) 앱 헬스 확인 (필수)
```bash
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/metrics | head
```

정상 기준:
- `/health` 응답 JSON 반환
- `/metrics`에 Prometheus 포맷 텍스트 출력

## 5) Prometheus 연동 확인 (모니터링 사용 시)
```bash
curl -s http://127.0.0.1:9090/api/v1/targets | grep -E '"health"|"lastError"' -n
```

정상 기준:
- 대상 `health`가 `up`
- `lastError`가 빈 문자열

## 6) Nginx/Webhook 경로 확인 (문제 발생 시)
```bash
sudo tail -n 50 /var/log/nginx/access.log | grep /tv/webhook
sudo tail -n 50 /var/log/nginx/error.log
```

사용 목적:
- TradingView 또는 수동 테스트 요청이 서버까지 도달했는지 확인
- 리버스 프록시/라우팅 문제 분리

## 7) 실운용 설정 확인 (중요)
```bash
sudo grep -E "EXECUTION_MODE|TV_ALLOWED_SYMBOLS|ORDER_SIZING_MODE|SOL_ORDER_EQUITY_PCT|BTC_ORDER_EQUITY_PCT|LEVERAGE_DEFAULT" /etc/psar_rsi_bot/.env
```

확인 포인트:
- 의도한 모드(`LIVE`/`RECEIVE_ONLY`)인지
- 허용 심볼이 현재 전략과 일치하는지
- 포지션 사이징 설정이 의도와 일치하는지

## 8) 최종 운영 체크
- 텔레그램 테스트 알림 1회
- `webhook_received`, `order_ok/order_fail/order_skip` 로그 확인
- 변경사항과 점검 결과를 데일리 리포트에 기록

## 9) 다중 컨테이너 스택 점검 (사용 시)
```bash
sudo systemctl status trading-env-sync.service --no-pager -l
sudo systemctl status trading-strategy-stack.service --no-pager -l
cd /opt/trading-stack
docker compose ps
docker compose logs --tail 100
```

SSM 키 변경 후 반영:
```bash
sudo systemctl restart trading-env-sync.service
sudo systemctl restart trading-strategy-stack.service
```

## 장애 시 빠른 분기
- `health` 실패: 앱 프로세스/의존성/환경변수 우선 확인
- `targets down`: Prometheus scrape 대상 주소/포트 확인
- Webhook 미도달: 보안그룹/Nginx/access.log 순서로 확인
- 주문 실패 급증: Binance API 응답 코드(400/401/404) 분류 후 원인 분리
