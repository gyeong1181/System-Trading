# 무신사 AI Native Engineer 지원용 요약

이 문서는 **무신사 AI Native Engineer 지원용**으로 운영 경험과 자동화 파이프라인을 강조하기 위해 별도로 작성한 요약본입니다.

## 1. 프로젝트 개요
- **프로젝트**: PSAR + EMA200 + RSI 자동매매 봇 (Binance Futures)
- **형태**: 실시간 WebSocket 기반 신호 처리 + REST 워밍업
- **운영 방식**: AWS EC2 상시 구동(systemd), GitHub Actions로 자동 배포

## 2. 운영/실무 관점 핵심 포인트
- **상시 운영**: EC2에서 24시간 실행, systemd 기반 재시작/상태 관리
- **운영 증빙**:
  - CloudWatch Logs Insights로 로그 분석
  - GitHub Actions 배포 기록으로 변경 추적
  - Telegram 알림으로 장애/이상상황 즉시 대응

## 3. 기술 스택
- **Python** (실시간 캔들 처리, 지표 계산, 거래 로직)
- **AWS EC2 / systemd** (운영)
- **GitHub Actions + rsync** (CI/CD)
- **CloudWatch Logs** (관측/로그)
- **Binance Futures API** (실거래 연동)

## 4. 운영 중 트러블슈팅 예시
- **실시간 거래 0건 문제**: WebSocket 수신/콜백 로깅 추가로 원인 파악
- **주문 실패(400 Bad Request)**: 최소 주문 수량/스텝 사이즈 검증 필요
- **API 인증 오류(401)**: 키/권한 및 환경 변수 경로 점검

## 5. 무신사에 어필 가능한 포인트
- **개발 → 운영 전환 경험**: 단순 구현이 아니라 운영 안정화와 관측까지 수행
- **AI Native 지향**: 자동화 파이프라인과 모니터링을 함께 구축
- **실전 대응**: 문제 발생 시 로그 기반 진단 및 개선 사례 보유

## 6. 확장 계획
- Grafana/Prometheus 기반 실시간 시각화
- 오류/타임아웃/잔고 부족 시나리오 방어 로직 강화
- 자산 리밸런싱 및 복리 로직 추가

---

### 첨부(운영 증빙 이미지)
- CloudWatch: `../cloudwatch_insights.png`
- GitHub Actions: `../Github_Actions_CICD_capture.png`
