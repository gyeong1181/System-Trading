# EC2 페이퍼 트레이딩 운영 가이드

이 문서는 `S1 ETHUSDT 4시간` 후보를 EC2에서 상시 페이퍼 트레이딩으로 검증할 때만 씁니다.

## 목적

- Bybit API 키 없이 공개 시세만으로 실시간 검증
- 실제 주문 없이 가상 체결, 포지션, 손익, 복구 기록
- EC2 재부팅 후에도 자동 재시작

## 기본 실행 모드

- 기본 명령: `paper-start`
- 기본 전략: `S1`
- 기본 심볼: `ETHUSDT`
- 기본 타임프레임: `4시간`

## 필요한 것

- Ubuntu EC2 1대
- SSH 접속 가능 상태
- GitHub Actions 자동 배포를 쓸 경우:
  - `BYBIT_PAPER_EC2_HOST`
  - `BYBIT_PAPER_EC2_USER`
  - `BYBIT_PAPER_EC2_SSH_KEY`

## 수동 설치

```bash
cd ~/bybit_personal_trading_system
chmod +x scripts/install_ec2_paper.sh
./scripts/install_ec2_paper.sh
```

설치 스크립트가 하는 일:

- swap 2GB 생성
- Docker / docker compose 설치
- `.env` 자동 생성
- `bybit-paper-trader.service` 등록
- 컨테이너 자동 시작

## 상태 확인

```bash
sudo systemctl status bybit-paper-trader.service
cd ~/bybit_personal_trading_system && docker compose logs -f
cd ~/bybit_personal_trading_system && docker compose ps
```

## 결과 확인

- DB: `data/trading.db`
- 로그: `logs/`
- 리포트: `reports/`

## 중지 / 재시작

```bash
sudo systemctl stop bybit-paper-trader.service
sudo systemctl start bybit-paper-trader.service
sudo systemctl restart bybit-paper-trader.service
```

## 메모

- `paper-start`는 Bybit API 키가 없어도 됩니다.
- Telegram 값도 비워둘 수 있습니다.
- 추후 `demo-start` 또는 `live-start`로 바꿀 때만 API 키를 넣으면 됩니다.
