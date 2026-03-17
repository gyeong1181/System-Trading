# Seoul Portfolio Recovery Checklist

이 문서는 서울 리전에서 포트폴리오용 PSAR 운영 시스템을 다시 살릴 때 필요한 최소 체크리스트다.

---

## 1. 목표 상태

- 서버: 서울 리전 EC2
- 역할: 포트폴리오용 PSAR 운영 시스템
- 핵심 기능:
  - TradingView Webhook 수신
  - Binance Futures 주문 실행
  - Telegram 알림
  - CloudWatch 로그
  - Prometheus / Grafana
  - GitHub Actions 기반 배포

---

## 2. env / 비밀값 확인

확인 대상:
- `TV_WEBHOOK_SECRET`
- `BINANCE_API_KEY`
- `BINANCE_API_SECRET`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `TV_ALLOWED_SYMBOLS`
- `TV_ALLOWED_TIMEFRAMES` 또는 `TV_ALLOWED_TIMEFRAMES_BY_SYMBOL`
- `EXECUTION_MODE`

기준:
- `TV_WEBHOOK_SECRET`는 URL이 아니라 랜덤 문자열이어야 함
- TradingView JSON의 `secret`과 서버 env의 `TV_WEBHOOK_SECRET`는 일치해야 함
- Binance 키는 서울 리전에서 정상 동작하는 계정 기준이어야 함

---

## 3. webhook endpoint 확인

확인 항목:
- TradingView Webhook URL이 서울 서버를 가리키는지
- 경로가 `/tv/webhook`인지
- 포트, reverse proxy, 보안그룹이 맞는지

예시:
- `http://<SEOUL_IP>/tv/webhook`

---

## 4. 애플리케이션 상태 점검

서울 서버에서:

```bash
cd /home/ec2-user/systemTrading/psar_rsi_bot
sudo systemctl status psar_rsi_bot --no-pager -l
sudo journalctl -u psar_rsi_bot -n 100 --no-pager
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/metrics | head
```

정상 기준:
- `active (running)`
- `/health` 응답 정상
- `/metrics` 응답 정상

---

## 5. Webhook 테스트

1. 서버 로그 tail
```bash
sudo journalctl -u psar_rsi_bot -f
```

2. 로컬에서 새 `signal_id`로 POST 테스트
3. 응답이 `duplicate`가 아닌지 확인
4. 로그에 `rejected_secret`, `rejected_symbol`, `rejected_timeframe`, `error`, `skip`, `ok` 중 어떤 상태가 나오는지 확인

---

## 6. 모니터링 복구

Prometheus / Grafana가 서울 서버 기준으로 필요하면:

```bash
cd /home/ec2-user/systemTrading/psar_rsi_bot/deploy/monitoring
docker compose -f docker-compose.monitoring.yml up -d
docker ps | grep -E "grafana|prometheus"
curl -s http://127.0.0.1:9090/-/healthy
curl -s http://127.0.0.1:3000/api/health
curl -s http://127.0.0.1:9090/api/v1/targets
```

확인 항목:
- target up
- dashboard 패널 갱신
- Telegram alert test 가능 여부

---

## 7. GitHub Actions / 배포 경로 확인

확인 항목:
- GitHub Actions가 서울 서버 SSH 대상 기준인지
- 배포 경로가 `/home/ec2-user/systemTrading/psar_rsi_bot` 기준인지
- 재시작 대상이 `psar_rsi_bot.service`인지

즉, 서울 서버를 포트폴리오용으로 유지하려면 CI/CD도 서울 기준으로 명확히 맞춰야 한다.

---

## 8. 재가동 최소 순서

1. 서울 서버 접속
2. env 값 검증
3. `psar_rsi_bot` 상태 확인 및 재시작
4. `/health`, `/metrics` 확인
5. TradingView webhook URL 및 secret 재확인
6. 수동 POST 테스트
7. Grafana / Prometheus 확인
8. 텔레그램 알림 확인

---

## 9. 판단 기준

아래가 충족되면 서울 포트폴리오 시스템 복구 완료로 본다.

- Webhook 요청이 실제로 도달
- `rejected_secret` 없이 정상 처리
- 텔레그램 알림 정상
- `/metrics` 수집 정상
- Grafana / Prometheus 패널 정상 갱신
