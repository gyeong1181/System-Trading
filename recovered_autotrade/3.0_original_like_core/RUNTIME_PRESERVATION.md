# 3.0 Original Runtime Preservation

## Goal

This folder is for preserving the original `3.0` runtime behavior as closely as practical by running the vendor image directly instead of reimplementing the strategy.

## High-confidence runtime facts

- Image: `exitant/exitant-okx-3.0:latest`
- Working directory: `/app`
- Startup command: `./autotrade`
- Python runtime inside image: `3.9.25`
- Files baked into `/app` at image build time:
  - `/app/autotrade`

## Observed startup behavior

When the original image starts without credentials, it:

- prints the `ExitAnt Trading PRO` banner
- reads environment variables first
- warns if `API_KEY`, `SECRET_KEY`, `PASSPHRASE` are missing
- warns if `TELEGRAM_BOT_TOKEN` is missing
- creates `/app/logs/autotrade.log`
- extracts its PyInstaller runtime under `/tmp/_MEI*`

## Runtime state paths found in the binary

- `auth/api_key.dat`
- `auth/last_strategy.json`
- `logs/autotrade.log`

These are the important paths to preserve on the host.

## Required environment variables

- `API_KEY`
- `SECRET_KEY`
- `PASSPHRASE`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

## Files in this folder

- `docker-compose.original-preserve.yml`
  - runs the original vendor image directly
- `.env.example`
  - fill this into a real `.env`
- `run_original_3_0.ps1`
  - creates runtime directories and starts the original image
- `stop_original_3_0.ps1`
  - stops the preserved original container

## Host persistence layout

- `runtime_state/auth` -> `/app/auth`
- `runtime_state/logs` -> `/app/logs`

This keeps Telegram/setup state and logs outside the container while leaving the strategy binary itself untouched.

## Start

1. Copy `.env.example` to `.env`
2. Fill the real credentials
3. Run:

```powershell
.\run_original_3_0.ps1
```

## Stop

```powershell
.\stop_original_3_0.ps1
```

## Why this is the right path

If the target is `behavior parity`, the safest approach is not to rewrite the strategy yet.
It is to keep using the original image and preserve only the runtime inputs and state around it.
