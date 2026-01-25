# Operations Runbook

## 1. Routine Health Checks
- `systemctl status BTCTrendFollower` → ensure service `active (running)`.
- `journalctl -u BTCTrendFollower -n 50` → review latest entries for WARN/ERROR.
- `tail -f logs/btc_trend_follow.log` (via tmux) → confirm candle ingest cadence (~60s).
- Equity drift → run `python btc_trend_follow.py --paper-bars 50` in dry-run mode for sanity.

## 2. Common Alerts & Response
| Alert | Detection | Immediate Action |
|-------|-----------|------------------|
| WebSocket disconnect | WARN in log “Stream error” repeating | `sudo systemctl restart BTCTrendFollower`; if persists, test outbound 443 reachability |
| Binance REST 4xx | Log shows `HTTPError` | Check API keys / symbol; confirm market not in maintenance. |
| Equity unexpected drop | Compare `PaperExchange` log vs Binance chart | Pause bot (`systemctl stop`), export logs, replay with `--paper-bars` for forensic |
| Telegram silent | Bot no new alerts | Use `curl https://api.telegram.org/bot$TOKEN/getMe`; renew token if fails |

## 3. Hotfix Workflow
1. `tmux attach -t btc_trend` to observe runtime.
2. Pull patch from Git main or upload ZIP.
3. `sudo systemctl stop BTCTrendFollower`.
4. Apply code fix, run `python btc_trend_follow.py --paper-bars 100`.
5. `sudo systemctl start BTCTrendFollower`.
6. Document incident in `logs/btc_trend_follow_<date>.md` (future).

## 4. Disaster Recovery
- **Server failure**: launch new EC2 via Deployment Checklist, restore `.env` from SSM, sync latest `BTCTrendFollower_package.zip`.
- **Key compromise**: rotate API keys, update `.env`, redeploy, revoke old keys on Binance/Telegram.

## 5. Portfolio Notes
- This runbook showcases operational awareness: log triage, restart procedures, and DR steps valued for cloud support roles.
