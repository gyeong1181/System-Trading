# file: tune_trend.py
import optuna
from backtest_emasir_trend import fetch_ohlcv, run_backtest, Params

df = fetch_ohlcv('ETH/USDT','1h','2023-01-01','2025-07-31')

def objective(trial):
    p = Params(
        ema_fast = trial.suggest_int('ema_fast', 8, 30),
        ema_slow = trial.suggest_int('ema_slow', 20, 80),
        rsi_len  = trial.suggest_int('rsi_len', 8, 21),
        rsi_thr  = trial.suggest_int('rsi_thr', 55, 75),
        adx_len  = trial.suggest_int('adx_len', 10, 20),
        adx_thr  = trial.suggest_int('adx_thr', 18, 35),
        sig_max_bars = trial.suggest_int('sig_max_bars', 1, 4),
        tp1_pct  = trial.suggest_float('tp1_pct', 0.01, 0.05),
        tp1_part = trial.suggest_float('tp1_part', 0.05, 0.3),
        be_buffer= trial.suggest_float('be_buffer', 0.0005, 0.002),
        atr_mult = trial.suggest_float('atr_mult', 1.5, 4.0),
        fixed_sl_pct = trial.suggest_float('fixed_sl_pct', 0.015, 0.035)
    )
    stats, _, _ = run_backtest(df, p)
    # 종합 점수: 최종잔고↑, MDD↓, PF↑ 균형
    score = (stats['final_balance']/10000) + 0.5*stats['profit_factor'] - 2.0*abs(stats['mdd'])
    return score

study = optuna.create_study(direction='maximize')
study.optimize(objective, n_trials=100)
print("Best params:", study.best_trial.params)
