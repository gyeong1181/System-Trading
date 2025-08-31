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

# 각 티커별 상세 파라미터 설정 (튜닝 중인 경우, 튜닝 결과를 여기에 반영합니다.)
SYMBOL_PARAMS = {
    "BTC/USDT": { # 초기에 트레이딩뷰로 튜닝한 결과
        "timeframe": "1h",
        "tp": 0.07,
        "sl": 0.02,
        "position_size": 0.0003, # 50달러 정도
        "ema_fast": 5,
        "ema_slow": 20,
        "rsi_period": 14,
        "rsi_threshold": 56,
        "leverage": 5, 
    },
    "ETH/USDT": { # 2025.07.30에 튜닝함.
        "timeframe": "1h", # 튜닝 테스트 기간 24.01.01~25.07.30 이며, 샤프지수 약 6으로 나옴.
        "tp": 0.03178,
        "sl": 0.02499,
        "position_size": 0.01,
        "ema_fast": 18,
        "ema_slow": 26,
        "rsi_period": 14,
        "rsi_threshold": 64,
        "leverage": 5, 
    },
    "XRP/USDT": { # 2025.07.31에 튜닝함.  
        "timeframe": "1h", # 튜닝 테스트 기간 24.01.01~25.07.30 이며, 샤프지수 약 16으로 아주 높게 나옴.
        "tp": 0.0488,
        "sl": 0.0111,
        "position_size": 10, # 약 20달러 정도
        "ema_fast": 16,
        "ema_slow": 66,
        "rsi_period": 14,
        "rsi_threshold": 65,
        "leverage": 5, 
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
        "leverage": 5, 
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
        "leverage": 5, 
    },
}