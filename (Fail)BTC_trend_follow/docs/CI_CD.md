# CI/CD & 서버 반영 가이드

## 수동 배포 루틴
1. 로컬에서 코드 수정 후 `BTCTrendFollower_package.zip` 재생성  
   `Compress-Archive -Path BTC_trend_follow\* -DestinationPath BTC_trend_follow\BTCTrendFollower_package.zip -Force`
2. AWS EC2로 ZIP 전송  
   `scp BTC_trend_follow/BTCTrendFollower_package.zip ubuntu@<EC2_IP>:/tmp/`
3. 서버에서 `/opt/btc_trend_follow`로 이동해 `unzip -o /tmp/BTCTrendFollower_package.zip`
4. `sudo systemctl restart BTCTrendFollower`

## GitHub Actions 예시 (S3 업로드 + 서버 스크립트)

```yaml
name: btc-trend-follow
on:
  push:
    paths:
      - 'BTC_trend_follow/**'
jobs:
  package:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Zip artifact
        run: |
          cd BTC_trend_follow
          zip -r BTCTrendFollower_package.zip .
      - name: Upload to S3
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          AWS_DEFAULT_REGION: ap-northeast-2
        run: |
          aws s3 cp BTC_trend_follow/BTCTrendFollower_package.zip s3://my-bot-deploy/
```

EC2에서는 cron이나 systemd 타이머로 아래 스크립트를 돌려 최신 ZIP을 받습니다:

```bash
#!/bin/bash
set -e
cd /opt/btc_trend_follow
aws s3 cp s3://my-bot-deploy/BTCTrendFollower_package.zip /tmp/pkg.zip
unzip -o /tmp/pkg.zip
sudo systemctl restart BTCTrendFollower
```

## systemd 역할 요약
- 서비스 등록(`enable`) → 부팅 시 자동 실행
- `systemctl daemon-reload` → 유닛 파일 변경 인식
- `systemctl restart BTCTrendFollower` → 새 코드 적용
- `journalctl -u BTCTrendFollower -f` → 실시간 로그 추적

이 문서를 Cursor/다른 AI에게 전달하면 서버 반영 절차와 CI/CD 파이프라인 의도를 바로 이해할 수 있습니다.
