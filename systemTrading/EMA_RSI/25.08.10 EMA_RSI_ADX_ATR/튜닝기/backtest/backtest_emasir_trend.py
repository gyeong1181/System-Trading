# file: backtest_emasir_trend.py
import ccxt, pandas as pd, numpy as np, math
from dataclasses import dataclass

@dataclass
class Params:
    ema_fast:int=18; ema_slow:int=26; rsi_len:int=14; rsi_thr:int=64
    adx_len:int=14; adx_thr:int=25; use_adx:bool=True
    sig_max_bars:int=2                      # 교차 후 n바 이내만 진입
    tp1_pct:float=0.02; tp1_part:float=0.5  # 부분익절
    be_buffer:float=0.001                   # 본절+버퍼(=+0.1%)
    atr_mult:float=2.5                      # 트레일링 강도 (None이면 미사용)
    fixed_sl_pct:float=None                 # 고정 SL(%), 예: 0.024
    fee_oneway:float=0.0004; slippage:float=0.0005

def fetch_ohlcv(symbol='ETH/USDT', timeframe='1h', start='2024-01-01', end='2025-07-31'):
    ex = ccxt.binance({'enableRateLimit':True})
    since = ex.parse8601(start+'T00:00:00Z'); end_ms = ex.parse8601(end+'T23:59:59Z')
    all=[]
    step = ex.parse_timeframe(timeframe)*1000*900  # 여유
    while since <= end_ms:
        o = ex.fetch_ohlcv(symbol, timeframe, since, limit=1000)
        if not o: break
        all += o
        since = o[-1][0] + 1
    df = pd.DataFrame(all, columns=['time','open','high','low','close','volume'])
    df['time']=pd.to_datetime(df['time'], unit='ms'); df.set_index('time', inplace=True)
    return df

def ema(s,n): return s.ewm(span=n, adjust=False).mean()
def rsi(s,n=14):
    d=s.diff(); up=d.clip(lower=0); dn=(-d).clip(lower=0)
    rs=up.ewm(alpha=1/n, adjust=False).mean()/dn.ewm(alpha=1/n, adjust=False).mean()
    return 100-100/(1+rs)
def atr(df,n=14):
    pc=df['close'].shift(1)
    tr=pd.concat([(df['high']-df['low']).abs(), (df['high']-pc).abs(), (df['low']-pc).abs()],axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False).mean()
def adx(df,n=14):
    up=df['high'].diff(); dn=-df['low'].diff()
    plusDM=np.where((up>0)&(up>dn), up, 0.0); minusDM=np.where((dn>0)&(dn>up), dn, 0.0)
    TR = atr(df, n)*(n/(n-1))
    pDI=100*pd.Series(plusDM,index=df.index).ewm(alpha=1/n, adjust=False).mean()/TR
    mDI=100*pd.Series(minusDM,index=df.index).ewm(alpha=1/n, adjust=False).mean()/TR
    DX=(abs(pDI-mDI)/(pDI+mDI))*100
    return pd.Series(DX, index=df.index).ewm(alpha=1/n, adjust=False).mean()

def prepare(df,p:Params):
    d=df.copy()
    d['ema_f']=ema(d['close'], p.ema_fast); d['ema_s']=ema(d['close'], p.ema_slow)
    d['rsi']=rsi(d['close'], p.rsi_len); d['atr']=atr(d, p.adx_len); d['adx']=adx(d, p.adx_len)
    return d.dropna()

def run_backtest(df,p=Params(), initial=10000):
    d=prepare(df,p); bal=initial; eq=[]; trades=[]
    pos=False; entry=None; tp1=None; hit1=False; trail=None; runner=0.0
    last_cross=None

    for i in range(1,len(d)):
        prev, cur = d.iloc[i-1], d.iloc[i]
        # 교차 체크
        if (prev.ema_f<=prev.ema_s) and (cur.ema_f>cur.ema_s):
            last_cross=i
        fresh = (last_cross is not None) and (i-last_cross<=p.sig_max_bars)
        adx_ok = (cur.adx>p.adx_thr) if p.use_adx else True
        rsi_ok = (cur.rsi>p.rsi_thr) or (p.use_adx and cur.adx>p.adx_thr)

        fee = p.fee_oneway
        # 진입
        if (not pos) and fresh and adx_ok and rsi_ok:
            entry = cur.close*(1+p.slippage); pos=True; hit1=False
            tp1 = entry*(1+p.tp1_pct); runner = (1-p.tp1_part)
            trail = entry - (p.atr_mult*cur.atr if p.atr_mult else 0)
            if p.fixed_sl_pct is not None:
                trail = min(trail, entry*(1-p.fixed_sl_pct)) if trail else entry*(1-p.fixed_sl_pct)
            bal *= (1-fee) # 진입 수수료

        if pos:
            # 트레일 업데이트
            if p.atr_mult: trail=max(trail, cur.close - p.atr_mult*cur.atr)
            # TP1
            if (not hit1) and (cur.high>=tp1):
                exitp = tp1*(1-p.slippage); pnl = (p.tp1_part)*((exitp/entry)-1)
                bal *= (1+pnl-fee); hit1=True; trail=max(trail, entry*(1+p.be_buffer))
            # Stop / Runner 청산
            stop_hit = trail is not None and cur.low<=trail
            if stop_hit:
                exitp = trail*(1-p.slippage); pnl = runner*((exitp/entry)-1)
                bal *= (1+pnl-fee); trades.append({'entry':entry,'exit':exitp,'tp1':hit1})
                pos=False; entry=None; trail=None; runner=0.0

        eq.append(bal)

    # 성과 지표
    ec=pd.Series(eq, index=d.index[:len(eq)])
    peak=ec.cummax(); mdd = ((ec-peak)/peak).min() if len(ec) else 0.0
    wins = sum(t['exit']>t['entry'] for t in trades); losses=len(trades)-wins
    avg_win=np.mean([(t['exit']/t['entry']-1) for t in trades if t['exit']>t['entry']]) if wins else 0
    avg_loss=np.mean([(t['exit']/t['entry']-1) for t in trades if t['exit']<=t['entry']]) if losses else 0
    pf=(avg_win*wins)/(abs(avg_loss)*losses) if losses and avg_loss!=0 else float('inf')
    wr=wins/len(trades) if trades else 0.0
    return {
        'trades':len(trades), 'win_rate':wr, 'profit_factor':pf,
        'mdd':float(mdd), 'final_balance': float(ec.iloc[-1]) if len(ec) else initial
    }, ec, pd.DataFrame(trades)

if __name__=='__main__':
    df = fetch_ohlcv('ETH/USDT','1h','2024-01-01','2025-08-05')
    stats, equity, trades = run_backtest(df, Params())
    print(stats)
