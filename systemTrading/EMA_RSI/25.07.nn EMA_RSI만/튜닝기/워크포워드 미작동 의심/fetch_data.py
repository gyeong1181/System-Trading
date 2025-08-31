import ccxt
import pandas as pd

def fetch_ohlcv(symbol='BTC/USDT', timeframe='1h', since_days=500):
    exchange = ccxt.binance()
    since = exchange.milliseconds() - since_days * 24 * 60 * 60 * 1000
    ohlcv = []
    limit = 500
    while True:
        chunk = exchange.fetch_ohlcv(symbol, timeframe, since, limit)
        if not chunk:
            break
        ohlcv += chunk
        since = chunk[-1][0] + 1
        if len(chunk) < limit:
            break
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('datetime', inplace=True)
    return df
