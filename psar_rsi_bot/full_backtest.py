#!/usr/bin/env python3
import pandas as pd
import requests
import numpy as np
from ta.trend import PSARIndicator
from ta.momentum import RSIIndicator

print("📥 바이낸스 BTC/USDT 1개월 1H 데이터 다운로드...")

# 1. 바이낸스 데이터 (최근 720시간 = 1개월)
url = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=720"
data = requests.get(url).json()

# 2. 올바른 데이터프레임 변환
columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 
           'close_time', 'quote_volume', 'count', 'taker_buy_base', 
           'taker_buy_quote', 'ignore']
df = pd.DataFrame(data, columns=columns)

# 3. 숫자형 변환 (에러 원인 해결!)
for col in ['open', 'high', 'low', 'close', 'volume']:
    df[col] = pd.to_numeric(df[col])

df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
df.set_index('timestamp', inplace=True)

print(f"✅ {len(df)} 캔들 로드 완료")
print(df[['open','high','low','close']].tail())

# 4. 기술지표 계산
df['rsi'] = RSIIndicator(df['close'], window=14).rsi()
df['psar'] = PSARIndicator(df['high'], df['low'], df['close']).psar()

# 5. 신호 생성 (라이브 봇과 동일 로직)
df['signal'] = 'HOLD'
df.loc[(df['psar'] > df['close']) & (df['rsi'] < 30), 'signal'] = 'BUY'   # PSAR 상향 + RSI 과매도
df.loc[(df['psar'] < df['close']) & (df['rsi'] > 70), 'signal'] = 'SELL'  # PSAR 하향 + RSI 과매수

# 6. 결과 분석
trades = df[df['signal'] != 'HOLD'].copy()
print(f"\n🎯 1개월 백테스트 결과: {len(trades)} 신호 발생")
print(trades[['close', 'rsi', 'psar', 'signal']].tail(10))

print("\n📊 신호 분포:")
print(trades['signal'].value_counts())

# 7. 간단 수익 시뮬레이션
trades['next_close'] = df['close'].shift(-1)
trades['pnl'] = np.where(trades['signal']=='BUY', 
                        (trades['next_close']/trades['close']-1),
                        (1-trades['next_close']/trades['close']))

avg_pnl = trades['pnl'].mean()
win_rate = (trades['pnl'] > 0).mean()
print(f"\n💰 평균 수익률: {avg_pnl:.2%}")
print(f"✅ 승률: {win_rate:.1%}")
print(f"📈 총 거래 횟수: {len(trades)}")

# 8. 차트 저장
import matplotlib.pyplot as plt
plt.figure(figsize=(15,8))
plt.subplot(2,1,1)
plt.plot(df.index, df['close'])
plt.scatter(trades.index, trades['close'], c=['g' if s=='BUY' else 'r' for s in trades['signal']], marker='^', s=100)
plt.title('BTC/USDT + PSAR/RSI 신호')

plt.subplot(2,1,2)
plt.plot(trades.index, trades['pnl'], marker='o')
plt.title('각 거래 수익률')
plt.savefig('backtest_results.png')
print("\n📈 backtest_results.png 저장 완료!")
