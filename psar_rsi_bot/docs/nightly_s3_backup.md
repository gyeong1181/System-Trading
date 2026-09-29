# Nightly S3 Backup

서울 서버에서 매일 밤 12시에 소스 코드와 매매 로그를 S3로 백업할 수 있도록 작성한 스크립트와 crontab 예시다. 이 저장소에는 실제 서버의 cron 등록·실행 로그 증빙이 없으므로, 운영 완료가 아닌 자동화 구성으로 설명한다.

## Included
- Source code under `/home/ec2-user/systemTrading`
- Trading logs under `/home/ec2-user/systemTrading/psar_rsi_bot/logs`

## Excluded
- `.env`
- `.env.*`
- `.git`
- `terraform.tfvars`
- `infra/terraform/scripts/ssm-secrets.local.env`
- Python cache and virtual environment directories

## Files
- Script: [nightly_s3_backup.sh](../scripts/nightly_s3_backup.sh)
- Crontab example: [nightly_s3_backup.crontab.example](../scripts/nightly_s3_backup.crontab.example)

## Registration Order
1. Create the local backup directory.
2. Make the shell script executable.
3. Run the script once manually with the real S3 bucket path.
4. Copy and edit the crontab example.
5. Register the crontab.
6. Verify cron registration and log output.

## Commands
```bash
mkdir -p /home/ec2-user/backups/nightly
chmod +x /home/ec2-user/systemTrading/psar_rsi_bot/scripts/nightly_s3_backup.sh
```

Manual test:
```bash
S3_URI=s3://YOUR-BUCKET-NAME/systemTrading-backups \
/usr/bin/env bash /home/ec2-user/systemTrading/psar_rsi_bot/scripts/nightly_s3_backup.sh
```

Crontab registration:
```bash
cp /home/ec2-user/systemTrading/psar_rsi_bot/scripts/nightly_s3_backup.crontab.example /tmp/nightly_backup.cron
vi /tmp/nightly_backup.cron
crontab /tmp/nightly_backup.cron
crontab -l
```

Cron log:
```bash
tail -f /home/ec2-user/backups/nightly/cron.log
```

## IAM / AWS CLI Requirement
- The server must have `aws` CLI installed.
- The EC2 instance role, or local AWS credentials, must allow `s3:PutObject`.

## Portfolio Note
이 구성은 운영 환경에 적용할 수 있는 정기 보존 자동화 스크립트와 등록 절차를 문서화한 것이다.
