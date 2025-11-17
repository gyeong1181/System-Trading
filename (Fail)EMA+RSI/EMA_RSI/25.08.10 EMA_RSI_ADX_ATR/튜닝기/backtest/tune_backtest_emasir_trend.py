# file: tune_backtest_emasir_trend.py
import optuna
from backtest_emasir_trend import fetch_ohlcv, run_backtest, Params

# === 데이터 로드 설정 ===
SYMBOL = 'BTC/USDT'
TIMEFRAME = '1h'
START = '2023-01-01'
END = '2024-08-30'
INITIAL_BAL = 10000

print(f"데이터 로드: {SYMBOL} {TIMEFRAME} {START} ~ {END}")
df = fetch_ohlcv(SYMBOL, TIMEFRAME, START, END)

# === 목적 함수 ===
def objective(trial):
    p = Params(
        ema_fast = trial.suggest_int('ema_fast', 5, 30),
        ema_slow = trial.suggest_int('ema_slow', 20, 80),
        rsi_len  = 14,
        rsi_thr  = 60,
        adx_len  = trial.suggest_int('adx_len', 10, 20),
        adx_thr  = trial.suggest_int('adx_thr', 18, 35),
        sig_max_bars = trial.suggest_int('sig_max_bars', 1, 4),
        tp1_pct  = trial.suggest_float('tp1_pct', 0.01, 0.05),
        tp1_part = trial.suggest_float('tp1_part', 0.05, 0.3),
        be_buffer= trial.suggest_float('be_buffer', 0.0005, 0.002),
        atr_mult = trial.suggest_float('atr_mult', 1.5, 4.0),
        fixed_sl_pct = trial.suggest_float('fixed_sl_pct', 0.015, 0.035),
        fee_oneway = 0.0004,
        slippage = 0.0005
    )
    stats, _, _ = run_backtest(df, p, initial=INITIAL_BAL)

    win_rate = stats['win_rate']
    pf = stats['profit_factor']
    trades = stats['trades']
    mdd = stats['mdd']
    final_bal = stats['final_balance']

    # 🎯 점수 계산: 수익률↑, PF↑, 거래수↑, MDD↓
    score = (final_bal / INITIAL_BAL) \
            + (0.5 * pf) \
            + (0.2 * trades / 100) \
            - (2.0 * abs(mdd))

    # 극단적으로 거래 수가 적은 경우(연간 30회 미만) 패널티
    if trades < 30:
        score -= 1.0
    # PF가 1.5 미만이면 패널티
    if pf < 1.5:
        score -= 0.5
    # 승률이 60% 미만이면 패널티
    if win_rate < 0.6:
        score -= 0.5

    return score

# === 최적화 실행 ===
if __name__ == "__main__":
    study = optuna.create_study(direction='maximize')
    study.optimize(objective, n_trials=50) 

    print("\n=== 최적화 완료 ===")
    best_params = study.best_trial.params
    for k, v in best_params.items():
        print(f"{k}: {v}")

    # 최적 파라미터로 백테스트 실행
    p = Params(**best_params)
    stats, equity, trades = run_backtest(df, p, initial=INITIAL_BAL)
    print("\n=== 최적 파라미터 성과 ===")
    print(stats)
