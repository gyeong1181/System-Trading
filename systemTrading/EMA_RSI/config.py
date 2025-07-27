# config.py

# --- 1. 글로벌 설정 ---
# API 키, 시크릿 키, 텔레그램 정보는 .env 파일에서 관리합니다.
# 따라서 이 파일에서는 삭제됩니다.

# 글로벌 리스크 관리 설정 (모든 티커 합산 기준)
MAX_CONSECUTIVE_LOSSES = 3
MAX_DAILY_TRADES = 20 # 5개 티커 운영을 고려하여 상향 조정

# --- 2. 티커별 개별 전략 설정 ---
# 거래할 티커 목록을 여기에 추가/삭제하여 관리합니다.
SYMBOLS = ["BTC/USDT", "ETH/USDT", "XRP/USDT", "SOL/USDT", "AVAX/USDT"]

# config.py

# 각 티커별 상세 파라미터 설정 (Pro 모드에서 제안된 최적화 값 포함)
SYMBOL_PARAMS = {
    "BTC/USDT": {
        "timeframe": "1h",
        "tp": 0.07,
        "sl": 0.02,
        "position_size": 0.001,
        "ema_fast": 5,
        "ema_slow": 20,
        "rsi_period": 14,
        "rsi_threshold": 56,
        "leverage": 5, # <--- 이 줄을 추가합니다.
    },
    "ETH/USDT": {
        "timeframe": "1h",
        "tp": 0.08,
        "sl": 0.03,
        "position_size": 0.01,
        "ema_fast": 6,
        "ema_slow": 22,
        "rsi_period": 14,
        "rsi_threshold": 55,
        "leverage": 5, # <--- 이 줄을 추가합니다.
    },
    "XRP/USDT": {
        "timeframe": "1h",
        "tp": 0.05,
        "sl": 0.025,
        "position_size": 10,
        "ema_fast": 7,
        "ema_slow": 25,
        "rsi_period": 14,
        "rsi_threshold": 60,
        "leverage": 5, # <--- 이 줄을 추가합니다.
    },
    "SOL/USDT": {
        "timeframe": "1h",
        "tp": 0.10,
        "sl": 0.04,
        "position_size": 0.5,
        "ema_fast": 5,
        "ema_slow": 20,
        "rsi_period": 14,
        "rsi_threshold": 58,
        "leverage": 5, # <--- 이 줄을 추가합니다.
    },
    "AVAX/USDT": {
        "timeframe": "1h",
        "tp": 0.09,
        "sl": 0.035,
        "position_size": 1,
        "ema_fast": 5,
        "ema_slow": 21,
        "rsi_period": 14,
        "rsi_threshold": 57,
        "leverage": 5, # <--- 이 줄을 추가합니다.
    },
}