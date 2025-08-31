import numpy as np
import pandas as pd
from ta.trend import ema_indicator
from ta.volatility import average_true_range
from ta.momentum import rsi

def enhanced_backtest_strategy(df, ema_fast, ema_slow, atr_len, atr_mult_sl, atr_mult_tp):
    df = df.copy()
    df['ema_fast'] = ema_indicator(df['close'], window=ema_fast)
    df['ema_slow'] = ema_indicator(df['close'], window=ema_slow)
    df['atr'] = average_true_range(df['high'], df['low'], df['close'], window=atr_len)
    df['rsi'] = rsi(df['close'], window=14)
    df['volume_ma'] = df['volume'].rolling(window=20).mean()

    in_position = False
    entry_price = None
    sl = None
    tp = None
    entry_index = None

    returns = []
    win_losses = []
    durations = []

    max_holding_bars = 48  # 최대 보유 봉 수 (ex: 48시간)

    for i in range(ema_slow, len(df)):
        # 진입 조건: EMA 골든크로스 + 변동성 충분 + RSI 30~70 + 거래량 충분
        if not in_position:
            cond1 = df['ema_fast'].iloc[i] > df['ema_slow'].iloc[i]
            cond2 = df['ema_fast'].iloc[i-1] <= df['ema_slow'].iloc[i-1]
            cond3 = df['atr'].iloc[i] > df['atr'].rolling(20).mean().iloc[i]
            cond4 = 30 < df['rsi'].iloc[i] < 70
            cond5 = df['volume'].iloc[i] > 0.8 * df['volume_ma'].iloc[i]

            if cond1 and cond2 and cond3 and cond4 and cond5:
                entry_price = df['close'].iloc[i]
                sl = entry_price - atr_mult_sl * df['atr'].iloc[i]
                tp = entry_price + atr_mult_tp * df['atr'].iloc[i]
                entry_index = i
                in_position = True

        else:
            price = df['close'].iloc[i]
            holding_period = i - entry_index
            # 손절/익절 또는 최대 보유 기간 도달 시 청산
            if price <= sl or price >= tp or holding_period >= max_holding_bars:
                ret = (price - entry_price) / entry_price
                returns.append(ret)
                win_losses.append(1 if ret > 0 else 0)
                durations.append(holding_period)
                in_position = False

            else:
                # 트렌드 역전시 조기 청산 (EMA 빠른선이 느린선 밑으로 떨어짐)
                if df['ema_fast'].iloc[i] < df['ema_slow'].iloc[i]:
                    ret = (price - entry_price) / entry_price
                    returns.append(ret)
                    win_losses.append(1 if ret > 0 else 0)
                    durations.append(holding_period)
                    in_position = False

    if len(returns) == 0:
        # 거래가 없으면 0 반환
        return {
            "profit": 0,
            "sharpe": 0,
            "sortino": 0,
            "profit_factor": 0,
            "mdd": 0,
            "win_rate": 0,
            "trades": 0,
            "avg_duration": 0
        }

    returns = np.array(returns)
    profit = np.sum(returns) * 100
    win_rate = np.mean(win_losses)
    avg_duration = np.mean(durations)

    # 샤프 비율
    sharpe = np.mean(returns) / np.std(returns) * np.sqrt(len(returns)) if np.std(returns) > 0 else 0

   # 예를 들어 소티노 부분만 보완
    negative_returns = returns[returns < 0]
    if len(negative_returns) == 0:
        downside_std = 1e-8  # 소량의 작은 수로 대체하여 0 나누기 방지
    else:
        downside_std = np.std(negative_returns)
    sortino = np.mean(returns) / downside_std * np.sqrt(len(returns)) if downside_std > 0 else 0

    # 수익지수 (Profit Factor)
    gross_profit = np.sum(returns[returns > 0])
    gross_loss = -np.sum(returns[returns < 0])
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else np.inf

    # 최대 낙폭 MDD 계산
    cum_returns = np.cumprod(1 + returns) - 1
    peak = np.maximum.accumulate(cum_returns)
    drawdowns = peak - cum_returns
    mdd = np.max(drawdowns) * 100

    return {
        "profit": round(profit, 2),
        "sharpe": round(sharpe, 2),
        "sortino": round(sortino, 2),
        "profit_factor": round(profit_factor, 2),
        "mdd": round(mdd, 2),
        "win_rate": round(win_rate, 2),
        "trades": len(returns),
        "avg_duration": round(avg_duration, 2)
    }
