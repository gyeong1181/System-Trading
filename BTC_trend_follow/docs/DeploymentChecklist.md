# Deployment Checklist (AWS EC2)

## Pre-flight
- [ ] Confirm Binance API keys + Telegram tokens exist in `.env`.
- [ ] Verify Python 3.10+ and pip on target host.
- [ ] Ensure IAM role for EC2 allows `ssm:GetParameter`, `logs:PutLogEvents`, `cloudwatch:PutMetricData`.

## Provision
1. Launch Ubuntu 22.04 EC2 (t3.small, 30GB gp3).  
2. Attach IAM role + security group (SSH from office IP, outbound 443).  
3. SSH in and run:
   ```bash
   sudo apt update && sudo apt install -y python3-pip python3-venv unzip
   python3 -m venv /opt/btc_trend_follow/.venv
   source /opt/btc_trend_follow/.venv/bin/activate
   pip install --upgrade pip
   pip install pandas numpy httpx websockets python-dotenv
   ```

## Deploy Code
1. Copy `BTCTrendFollower_package.zip` to server (`scp` or S3).  
2. On EC2:
   ```bash
   cd /opt/btc_trend_follow
   unzip -o BTCTrendFollower_package.zip
   ```
3. Populate `.env` (either copy or pull from SSM).

## Configure Service
1. `sudo cp BTCTrendFollower.service /etc/systemd/system/`.  
2. `sudo systemctl daemon-reload`.  
3. `sudo systemctl enable --now BTCTrendFollower`.  
4. Confirm status: `sudo systemctl status BTCTrendFollower`.

## Observability
- [ ] Install/enable CloudWatch Agent or `journalctl -u BTCTrendFollower -f` for manual tail.
- [ ] Test Telegram alert (send dummy notification).
- [ ] Document log rotation: `/opt/btc_trend_follow/logs/btc_trend_follow.log`.

## Validation
- [ ] Run `python btc_trend_follow.py --paper-bars 300` once to ensure dependencies OK.  
- [ ] Switch to live mode, verify first WebSocket candle processed.  
- [ ] Checklist sign-off stored in `docs/DeploymentChecklist.md` for portfolio evidence.
