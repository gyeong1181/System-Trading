# Strategy/System Recovery

## Recovery status
- Main recovered strategy entrypoint: `recovered_autotrade/carchive/autotrade2.pyc`.
- Original `.py` files for the proprietary strategy were not present in the Docker image.
- Analysis is based on extracted `.pyc` files and `xdis` disassembly.
- Supporting custom/runtime packages were also recovered from the PyInstaller `PYZ` archive.

## High-confidence strategy picture
- Market source: OKX public candles endpoint.
- Symbol and bar: `XAU-USDT-SWAP`, `5m`, candle limit `50`.
- Indicator engine: RSI/Bollinger state, Fibonacci anchor levels, swap-threshold logic, trend-only no-entry gates.
- Decision outputs: `open long rotate`, `open short rotate`, `stay`.
- Execution style: OKX `limit` orders in `cross` mode with attached take-profit algo orders.

## Execution flow
`main` -> `start_telegram_bot` -> `validate_keys_logic` -> `start_auto_trading_after_mode_check` -> `auto_trading_loop` -> `make_decision_and_execute` -> `fetch_and_prepare_data` -> `add_indicators_rotate` -> `analyze_data` -> `open_long_rotate` or `open_short_rotate`

## Runtime system
- Telegram is not optional in the runtime design; the bot UI is used for setup, state display, and alerts.
- Imported Telegram framework components: `Application`, `CommandHandler`, `CallbackQueryHandler`, `MessageHandler`, `filters`, `ContextTypes`.
- The program starts watchdog/background threads for OKX refresh, process-health monitoring, Telegram-health monitoring, and the auto-trading loop.
- Visible runtime thread names / supervisors: `AutoTradingLoop`, `refresh_okx_client_periodically`, `monitor_process_health`, `telegram_health_monitor_thread`, `start_telegram_bot`.
- `auto_trading_loop` uses both a boolean flag and a lock to enforce a single active trading loop instance.
- When the loop stops unexpectedly, the program attempts automatic recovery by spawning `AutoTradingLoop-Recovery`.

## Recovered custom/runtime modules
- `candlelite`: 21 modules. Samples: candlelite, candlelite.calculate, candlelite.calculate.bar, candlelite.calculate.interval, candlelite.calculate.technical, candlelite.calculate.transform
- `okx`: 9 modules. Samples: okx, okx.Account, okx.MarketData, okx.PublicData, okx.Trade, okx.consts
- `paux`: 15 modules. Samples: paux, paux.date, paux.digit, paux.exception, paux.exception._base, paux.exception.execute
- `telegram`: 189 modules. Samples: telegram, telegram._bot, telegram._botcommand, telegram._botcommandscope, telegram._botdescription, telegram._botname
- `pandas_ta_classic`: 162 modules. Samples: pandas_ta_classic, pandas_ta_classic.candles, pandas_ta_classic.candles.cdl_doji, pandas_ta_classic.candles.cdl_inside, pandas_ta_classic.candles.cdl_pattern, pandas_ta_classic.candles.cdl_z
- `apscheduler`: 39 modules. Samples: apscheduler, apscheduler.events, apscheduler.executors, apscheduler.executors.asyncio, apscheduler.executors.base, apscheduler.executors.debug
- `httpx`: 24 modules. Samples: httpx, httpx.__version__, httpx._api, httpx._auth, httpx._client, httpx._compat

## Key method map
| Method | Source Line | Role | Evidence |
| --- | ---: | --- | --- |
| `main` | 13812 | Program bootstrap and supervisor | 'API_KEY' | 'SECRET_KEY' | 'PASSPHRASE' | 'TELEGRAM_BOT_TOKEN' | 'TELEGRAM_CHAT_ID' | '⚠️ API_KEY, SECRET_KEY, PASSPHRASE are not present in environment variables.' | 'TELEGRAM_BOT_TOKEN is not configured. Set all environment variables in the Render Environment tab.' | 'TELEGRAM_BOT_TOKEN is not configured. Edit the .env file manually or set the token.' | '/server/okx' | '❌ Telegram bot token is not set. Please set TELEGRAM_BOT_TOKEN in .env and restart.' |
| `validate_keys_logic` | 1674 | OKX/API credential gate | 'https://www.okx.com/api/v5/public/time' | 'uid' | 'hedge' | '/okx/validate_uid/' | 'ExitAnt University student identity verified\nUID:' | '50101' | '⚠️ OKX Error 50101: API Key is incorrect.' | '50103' | '⚠️ OKX Error 50103: Passphrase is incorrect.' | '50104' |
| `check_okx_account_modes` | 1747 | Runtime preflight for OKX account configuration | "OKX 거래소 Position Mode와 Account Mode 체크\n    \n    Returns:\n        dict: {\n            'position_mode': 'long_short_mode' or 'net_mode' or None,\n            'acct_lv': 1~4 (1=Spot, 2=Single-currency margin, 3=Multi-currency margin, 4=Portfolio margin) or None,\n            'position_mode_ok': bool,\n            'acct_mode_ok': bool\n        }\n    " | 'posMode' | 'acctLv' | 'long_short_mode' | (2, 3, 4) |
| `fetch_and_prepare_data` | 2238 | Market data ingest | 'https://www.okx.com/api/v5/market/candles' | 'XAU-USDT-SWAP' | '5m' | '50' | ('timestamp', 'open', 'high', 'low', 'close', 'volume', 'volume_currency', 'volume_usdt', 'volume_contracts') | 'timestamp' | add_indicators_rotate |
| `add_indicators_rotate` | 2343 | Indicator and strategy-state builder | 'RSI_14' | 'Middle_Band' | 'Upper_Band' | 'Lower_Band' | 'Candle_break_Upperband' | 'Candle_break_Lowerband' | 'Nth entry reset triggered' | 'AI: Long Nth entry reset triggered due to Bollinger Band upper break during long entry, Fibonacci and entry size reset' | 0.764 | 0.618 |
| `analyze_data` | 3577 | Decision engine | 'long' | 'short' | 'ExitAnt AI: Current position is in progress. Judgment will proceed after position is closed.' | 'open long rotate' | 'open short rotate' | 'stay' | excute_only_long | excute_only_short |
| `open_long_rotate` | 3835 | Long-side order execution | 'trade_duplicate_prevention' | 'trade_order_locked' | 'trade_order_in_progress' | 'trade_setting_change_active' | 'trade_open_orders_exist' | 'Invalid trade size from USDT_to_Contracts' | 'botbuy' | ('attachAlgoClOrdId', 'tpTriggerPx', 'sz', 'tpOrdPx') | 'cross' | 'buy' |
| `open_short_rotate` | 4186 | Short-side order execution | 'trade_duplicate_prevention' | 'trade_order_locked' | 'trade_order_in_progress' | 'trade_setting_change_active' | 'Invalid trade size from USDT_to_Contracts' | 'botsell' | ('attachAlgoClOrdId', 'tpTriggerPx', 'sz', 'tpOrdPx') | 'cross' | 'sell' | 'limit' |
| `make_decision_and_execute` | 4510 | Single-cycle orchestrator | 'Leverage Setting' | 'Position Inquiry' | 'Account Check' | '⚠️ Account check failed, using default value' | 'open long rotate' | 'XAU balance is insufficient' | 'open short rotate' | fetch_and_prepare_data | analyze_data |
| `auto_trading_loop` | 13132 | 10-second execution loop | '⚠️ [Auto Trading Loop] Failed to acquire lock. Another thread is already running. This thread will exit.' | '🔄 [Auto Recovery] Unexpected loop termination detected - attempting auto recovery...' | 'AutoTradingLoop-Recovery' | '✅ [Auto Recovery] New trading loop started successfully (Thread ID: ' | '❌ [Auto Recovery] Failed to restart trading loop: ' | '✅ [Auto Trading Loop] Running smoothly (Iteration #' | 'cross' | '⚠️ [Auto Trading] make_decision_and_execute error (continuing): ' | ' seconds (Target: 10 seconds)' | make_decision_and_execute |
| `start_auto_trading_after_mode_check` | 12119 | User-triggered start handler | 'AutoTradingLoop' | 'btn_check_status' | 'btn_stop_trading' | 'btn_change_settings' | check_version_and_notify |
| `check_swap_strategy_change` | 223 | Swap-threshold change detector | 'None' | '1%' | '2%' | '3%' | '🔄 [Swap Strategy Change Detected] ' | '🔄 **Swap Strategy Change**\n\n📊 **Change:** ' | '\n✅ **Status:** Applied Immediately\n\n🚀 Orders are executed immediately with the new swap strategy.' | '⚠️ [Telegram Notification] Failed to send swap strategy change alert: ' | None | '✅ Swap strategy change applied immediately' |
| `estimate_rotate_count` | 2176 | Split-entry capacity estimator | '  - trade_size is missing, exiting function' | 0.01 | '→ Estimated number of possible divided entries: ' |
| `validate_settings_and_notify` | 1185 | Safety check for user configuration | 'validation_entry_size_zero' | 'validation_leverage_zero' | 'validation_loss_limit_zero' | 'settings_error_detected' | 'settings_review_required' |

## External systems and endpoints
- `https://exitant-ai-server.onrender.com/register`
- `https://raw.githubusercontent.com/kikima159/ExitAnt_version/main/server_version`
- `https://www.okx.com/api/v5/public/time`
- `https://www.okx.com/api/v5/market/candles`
- `https://www.okx.com/account/balance`
- `https://t.me/exitant_engineer`
- `https://dashboard.render.com/`
- `https://exitant.ai/`

## Credential/config handling
- Environment variables used at startup:
- `API_KEY`
- `SECRET_KEY`
- `PASSPHRASE`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- Local encrypted credential file path: `auth/api_key.dat`.
- Local strategy/state file path: `auth/last_strategy.json`.
- Embedded Fernet key found in bytecode: `b'kL8LwVXPaF7nTxSjbVvhO5tST1V8_LdZlnZkRBbDiyc='`.
- Telegram access is gated by `TELEGRAM_CHAT_ID` and owner-chat checks.

## Security and control observations
- The binary contains an embedded symmetric encryption key while also persisting API credentials locally.
- The program contacts ExitAnt infrastructure for registration and UID validation, so execution depends on vendor-controlled remote services.
- Startup logic attempts to cancel existing OKX open orders before starting a new strategy cycle.
- The OKX account is explicitly pushed toward hedge mode and margin-account checks are enforced.

## Analyst notes
- The trading loop explicitly targets a 10-second execution cadence.
- Original `.py` sources are still not recovered; the current result is bytecode-level reconstruction.

## Next practical step
- If full source-like recovery is required, the next step is targeted decompilation or manual pseudo-source reconstruction of `autotrade2.pyc`, starting with the methods in the table above.
