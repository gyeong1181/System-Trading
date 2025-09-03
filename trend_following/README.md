# EMA+RSI+ATR+ADX Trend Bot

This folder contains a trend-following strategy for ETH/USDT futures using EMA crossover, RSI confirmation, ATR-based sizing, and ADX regime filtering.

## Setup

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in API and Telegram credentials
python main.py
```

The script reads configuration parameters from constants at the top of `main.py` and uses `USE_PAPER` to toggle paper trading.
