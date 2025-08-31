import pandas as pd
import numpy as np
import ta

# 데이터프레임: df (index: datetime, columns: ['open','high','low','close','volume'])

# EMA/ATR 계산
df['ema10'] = ta.trend.ema_indicator(df['close'], window=10)
df['ema30'] = ta.trend.ema_indicator(df['close'], window=30)
df['atr']   = ta.volatility.average_true_range(df['high'], df['low'], df['close'], window=14)
df['atr_mean'] = df['atr'].rolling(window=20).mean()
df['atr_std']  = df['atr'].rolling(window=20).std()

# 조건: 이평 크로스 + 고변동성(ATR)
df['long_signal']  = (df['ema10'] > df['ema30']) & (df['ema10'].shift(1) <= df['ema30'].shift(1)) & (df['atr'] > df['atr_mean'] + df['atr_std'])
df['short_signal'] = (df['ema10'] < df['ema30']) & (df['ema10'].shift(1) >= df['ema30'].shift(1)) & (df['atr'] > df['atr_mean'] + df['atr_std'])

# 포지션 및 동적 stop-loss/take-profit 로직
entries = []
for i, row in df.iterrows():
    if row['long_signal']:
        entry = row['close']
        sl = entry - 2 * row['atr']
        tp = entry + 4 * row['atr']
        entries.append({'datetime': i, 'side': 'long', 'entry': entry, 'sl': sl, 'tp': tp}) # 기록
    elif row['short_signal']:
        entry = row['close']
        sl = entry + 2 * row['atr']
        tp = entry - 4 * row['atr']
        entries.append({'datetime': i, 'side': 'short', 'entry': entry, 'sl': sl, 'tp': tp})

signals = pd.DataFrame(entries)
print(signals.head())
