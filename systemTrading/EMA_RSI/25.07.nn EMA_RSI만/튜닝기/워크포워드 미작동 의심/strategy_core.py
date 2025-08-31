import numpy as np
import pandas as pd

def enhanced_backtest_strategy(df, ema_fast, ema_slow):
    df = df.copy()
    df['ema_fast'] = df['close'].ewm(span=ema_fast, adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=ema_slow, adjust=False).mean()

    position = None
    entry_price = None
    returns = []
    win_losses = []

    for i in range(1, len(df)):
        # 진입: EMA 골든크로스
        if position is None:
            if (df['ema_fast'].iloc[i-1] <= df['ema_slow'].iloc[i-1]) and (df['ema_fast'].iloc[i] > df['ema_slow'].iloc[i]):
                position = 'long'
                entry_price = df['close'].iloc[i]

        # 청산: EMA 데드크로스
        elif position == 'long':
            if (df['ema_fast'].iloc[i-1] >= df['ema_slow'].iloc[i-1]) and (df['ema_fast'].iloc[i] < df['ema_slow'].iloc[i]):
                ret = (df['close'].iloc[i] - entry_price) / entry_price
                returns.append(ret)
                win_losses.append(1 if ret > 0 else 0)
                position = None

    if not returns:
        return {
            "profit": 0,
            "sharpe": 0,
            "win_rate": 0,
            "trades": 0
        }

    ret_arr = np.array(returns)
    profit = np.sum(ret_arr) * 100
    win_rate = np.mean(win_losses)
    sharpe = np.mean(ret_arr) / (np.std(ret_arr) + 1e-8) * np.sqrt(len(ret_arr))

    return {
        "profit": round(profit, 2),
        "sharpe": round(sharpe, 2),
        "win_rate": round(win_rate, 2),
        "trades": len(returns)
    }
