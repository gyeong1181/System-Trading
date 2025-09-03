# BTC–ETH Pair Trading Bot

This package implements a mean reversion strategy for Binance USDT-M futures using BTC and ETH. The bot can run a quick backtest or live trading (dry-run by default).

## Files

- `main.py` – backtest and live trading entry point
- `config.yaml` – strategy parameters
- `requirements.txt` – Python dependencies
- `.env.example` – environment variables template
- `Dockerfile` – container spec (optional for deployment)

## Setup

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # add your API keys and telegram info
python main.py --mode backtest
```

To start live trading (begins in dry-run):

```bash
python main.py --mode live
```

Toggle `dry_run` to `false` in `config.yaml` for real orders. Review the code and use at your own risk.

## AWS/Docker

A simple Dockerfile is included. Build and run:

```bash
docker build -t pairtrading .
docker run -d pairtrading
```

## Disclaimer

This code is provided for educational purposes. Trading carries risk.
