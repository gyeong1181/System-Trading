# file: work_forward_test.py
from backtest_emasir_trend import fetch_ohlcv, run_backtest, Params

# === 대표님이 쓰신 최적 파라미터 ===
best_params = {
    'ema_fast': 9,
    'ema_slow': 20,
    'rsi_len': 14,
    'rsi_thr': 60,
    'adx_len': 10,
    'adx_thr': 19,
    'sig_max_bars': 4,
    'tp1_pct': 0.0442,
    'tp1_part': 0.281,
    'be_buffer': 0.0011,
    'atr_mult': 3.256,
    'fixed_sl_pct': 0.0269625,
    'fee_oneway': 0.0004,
    'slippage': 0.0005
}

p = Params(**best_params)
INITIAL_BAL = 10000

# === 1. 훈련 구간 데이터 (2022-01 ~ 2023-03) ===
df_train = fetch_ohlcv('BTC/USDT', '1h', '2022-01-01', '2023-03-31')
stats_train, _, _ = run_backtest(df_train, p, initial=INITIAL_BAL)

# === 2. 검증 구간 데이터 (2025-04 ~ 2025-08) ===
df_test = fetch_ohlcv('BTC/USDT', '1h', '2025-04-01', '2025-08-31')
stats_test, _, _ = run_backtest(df_test, p, initial=INITIAL_BAL)

# === 결과 출력 ===
print("\n=== ETH 워크포워드 테스트 결과 ===")
print("[훈련 구간] 2022-01 ~ 2023-03")
print(stats_train)

print("\n[검증 구간] 2025-04 ~ 2025-08")
print(stats_test)

# 비교 평가
if stats_test['final_balance'] > INITIAL_BAL and stats_test['profit_factor'] > 1.2:
    print("\n✅ 검증 구간에서도 성과 유지 → 과최적화 가능성 낮음")
else:
    print("\n⚠️ 검증 구간에서 성과 하락 → 과최적화 가능성 있음")
