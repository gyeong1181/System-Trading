import argparse
import ccxt
import pandas as pd
import pandas_ta as ta
import numpy as np
import optuna

# 0. 설정: 수수료, 슬리피지 등은 단순화를 위해 0으로 가정. 실전 적용 시 반드시 반영 필요.
FEE = 0.008 # 예: 0.8%

# ① 데이터 로드
def fetch_data(symbol, timeframe, start_date, end_date):
    """지정한 기간의 OHLCV 데이터를 CCXT를 통해 가져옵니다."""
    exchange = ccxt.binance()
    since = exchange.parse8601(start_date + 'T00:00:00Z')
    end = exchange.parse8601(end_date + 'T23:59:59Z')
    all_ohlcv = []
    
    while since < end:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since)
            if not ohlcv:
                break
            since = ohlcv[-1][0] + exchange.parse_timeframe(timeframe) * 1000
            all_ohlcv.extend(ohlcv)
        except Exception as e:
            print(f"An error occurred: {e}")
            break
            
    df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    return df

# ④ 백테스트 루프
def run_backtest(df, ema_fast, ema_slow, rsi_len, rsi_thr, tp_perc, sl_perc):
    """주어진 파라미터로 백테스트를 실행하고 Sharpe Ratio를 반환합니다."""
    # ② 지표 계산
    df.ta.ema(length=ema_fast, append=True, col_names=(f'EMA_{ema_fast}',))
    df.ta.ema(length=ema_slow, append=True, col_names=(f'EMA_{ema_slow}',))
    df.ta.rsi(length=rsi_len, append=True, col_names=(f'RSI_{rsi_len}',))
    df.dropna(inplace=True)

    position = None
    entry_price = 0
    returns = []

    # ③ 진입/청산 로직 (미래 데이터 누수 방지를 위해 한 칸씩 순회)
    for i in range(1, len(df)):
        if position is None:
            if df[f'EMA_{ema_fast}'].iloc[i-1] < df[f'EMA_{ema_slow}'].iloc[i-1] and \
               df[f'EMA_{ema_fast}'].iloc[i] > df[f'EMA_{ema_slow}'].iloc[i] and \
               df[f'RSI_{rsi_len}'].iloc[i] > rsi_thr:
                position = 'long'
                entry_price = df['close'].iloc[i]
        elif position == 'long':
            if df['high'].iloc[i] >= entry_price * (1 + tp_perc):
                exit_price = entry_price * (1 + tp_perc)
                returns.append((exit_price / entry_price - 1) - FEE)
                position = None
            elif df['low'].iloc[i] <= entry_price * (1 - sl_perc):
                exit_price = entry_price * (1 - sl_perc)
                returns.append((exit_price / entry_price - 1) - FEE)
                position = None

    if not returns:
        return 0.0

    returns_series = pd.Series(returns)
    sharpe_ratio = returns_series.mean() / returns_series.std() * np.sqrt(252 * 24) # 연율화
    return sharpe_ratio if np.isfinite(sharpe_ratio) else 0.0

# ⑤ Optuna 최적화 루프
def objective(trial, df):
    """Optuna가 호출할 목적 함수."""
    ema_fast = trial.suggest_int('ema_fast', 5, 20)
    ema_slow = trial.suggest_int('ema_slow', 25, 80)
    rsi_len = 14
    rsi_thr = trial.suggest_int('rsi_thr', 50, 70)
    tp_perc = trial.suggest_float('tp_perc', 0.01, 0.07)
    sl_perc = trial.suggest_float('sl_perc', 0.005, 0.025)

    if ema_fast >= ema_slow:
        return -1.0

    sharpe = run_backtest(df.copy(), ema_fast, ema_slow, rsi_len, rsi_thr, tp_perc, sl_perc)
    return sharpe

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--symbol', type=str, default='ETH/USDT', help='e.g., ETH/USDT')
    parser.add_argument('--tf', type=str, default='1h', help='e.g., 1h')
    parser.add_argument('--start', type=str, default='2024-01-01', help='e.g., 2024-01-01')
    parser.add_argument('--end', type=str, default='2025-07-14', help='e.g., 2025-07-14')
    args = parser.parse_args()

    df = fetch_data(args.symbol, args.tf, args.start, args.end)
    
    study = optuna.create_study(direction='maximize')
    study.optimize(lambda trial: objective(trial, df), n_trials=100)

    print("Best trial:")
    trial = study.best_trial
    print(f"  Value (Sharpe Ratio): {trial.value}")
    print("  Params: ")
    for key, value in trial.params.items():
        print(f"    {key}: {value}")

if __name__ == '__main__':
    main()