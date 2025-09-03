# EMA+RSI+ATR+ADX Trend Bot
import os, time, math, logging, sys
from datetime import datetime, timedelta, UTC
from dotenv import load_dotenv
import ccxt
import pandas as pd
import numpy as np

# ========= 설정 =========
USE_PAPER = True                 # 모의 먼저
SYMBOL    = 'ETH/USDT'
TIMEFRAME = '1h'
LEVERAGE  = 2
RISK_PCT  = 0.01                 # 계좌 대비 1% 리스크

# === 전략 파라미터(최적 튜닝 반영) ===
PARAMS = dict(
    ema_fast=8, ema_slow=55,
    rsi_len=15, rsi_thr=59,
    adx_len=12, adx_thr=25,
    sig_max_bars=3,
    tp1_pct=0.027851078724166922,    # TP1: +2.785%
    tp1_part=0.6924556665352782,     # TP1에서 69.2% 청산
    be_buffer=0.0007970928699538671, # 본절 승격 버퍼 +0.0797%
    atr_mult=3.6319546462712573,     # 트레일 강도
    fixed_sl_pct=0.019583692356585625,# 초기 SL -1.958%
    fee_oneway=0.0004,
    slippage=0.0005
)

# === 추가 아이디어 반영 파라미터 ===
# 러너 분할매도(ATR 기준 단계익절)
SCALEOUT_USE = True
SCALEOUT_STEPS_ATR = [2.0, 3.5, 5.0]   # 엔트리 대비 +N*ATR에서 분할 익절(러너를 3등분)
# 피라미딩 (본절 이후만, 안전선 확보 후 증액)
PYRAMID_USE = False # Pyramid trading feature toggle
PYRAMID_MAX = 2                        # 최대 2회
PYRAMID_SIZE_FACTOR = 0.5              # 각 추가는 초기수량의 50%
PYRAMID_MIN_PULLBACK_ATR = 0.8         # 직전 고점에서 ATR*0.8 이내 되돌림 후 재돌파 시
# 과매매 방지
COOLDOWN_BARS = 2                      # 진입 후 최소 2봉 대기
# 일일 손실 캡 (모의 기준 단순 계산)
DAILY_LOSS_CAP_PCT = 0.03              # 하루 -3% 이하면 당일 중지

# ========= API/로그 =========
load_dotenv()
API_KEY = os.getenv('API_KEY', '')
SECRET  = os.getenv('SECRET_KEY', '')
TG_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
TG_CHAT  = os.getenv('TELEGRAM_CHAT_ID', '')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler('eth_bot.log', 'a', 'utf-8')]
)
log = logging.getLogger('ETHBOT')

def send_telegram(msg:str):
    if not TG_TOKEN or not TG_CHAT: 
        return
    import requests
    url=f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id":TG_CHAT,"text":msg})
    except Exception as e:
        log.warning(f"TG fail: {e}")

# ========= 거래소 =========
exchange = ccxt.binance({
    'apiKey': API_KEY,
    'secret': SECRET,
    'enableRateLimit': True,
    'options': {'defaultType':'future'}
})
exchange.set_sandbox_mode(USE_PAPER)

def set_leverage(symbol, lev):
    try:
        exchange.set_margin_mode('ISOLATED', symbol)
    except Exception: pass
    try:
        exchange.set_leverage(lev, symbol)
    except Exception as e:
        log.info(f"set_leverage warn: {e}")

# ========= 지표 =========
def ema(s, n): return s.ewm(span=n, adjust=False).mean()
def rsi(s, n=14):
    d=s.diff(); up=d.clip(lower=0); dn=(-d).clip(lower=0)
    rs=up.ewm(alpha=1/n, adjust=False).mean()/dn.ewm(alpha=1/n, adjust=False).mean()
    return 100-100/(1+rs)
def atr(df, n=14):
    pc=df['close'].shift(1)
    tr=pd.concat([(df['high']-df['low']).abs(), (df['high']-pc).abs(), (df['low']-pc).abs()],axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False).mean()
def adx(df, n=14):
    up=df['high'].diff(); dn=-df['low'].diff()
    plusDM=np.where((up>0)&(up>dn), up, 0.0); minusDM=np.where((dn>0)&(dn>up), dn, 0.0)
    TR = atr(df, n)*(n/(n-1))
    pDI=100*pd.Series(plusDM,index=df.index).ewm(alpha=1/n, adjust=False).mean()/TR
    mDI=100*pd.Series(minusDM,index=df.index).ewm(alpha=1/n, adjust=False).mean()/TR
    DX=(abs(pDI-mDI)/(pDI+mDI))*100
    return pd.Series(DX,index=df.index).ewm(alpha=1/n, adjust=False).mean()

def fetch_ohlcv(symbol, timeframe, limit=500):
    o = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(o, columns=['time','open','high','low','close','volume'])
    df['time']=pd.to_datetime(df['time'], unit='ms'); df.set_index('time', inplace=True)
    return df

def build_indicators(df):
    p=PARAMS
    d=df.copy()
    d['ema_f']=ema(d['close'], p['ema_fast'])
    d['ema_s']=ema(d['close'], p['ema_slow'])
    d['ema_200']=ema(d['close'], 200)
    d['rsi']=rsi(d['close'], p['rsi_len'])
    d['atr']=atr(d, p['adx_len'])
    d['adx']=adx(d, p['adx_len'])
    d['roll_high']=d['high'].rolling(10).max()
    return d.dropna()

# ========= 유틸 =========
def get_market_meta(symbol):
    m=exchange.market(symbol)
    amt_prec = m['precision'].get('amount', 3)
    px_prec  = m['precision'].get('price', 2)
    min_amt  = m['limits']['amount'].get('min', 0.001)
    return amt_prec, px_prec, min_amt

def round_amt(x, prec): 
    step = 10**(-prec)
    return math.floor(x/step)*step

def calc_position_size(entry, sl, equity_usdt):
    risk = equity_usdt * RISK_PCT
    risk_dist = max(entry - sl, entry*0.002)
    qty = risk / risk_dist
    return qty

def place_market_buy(symbol, qty):
    try:
        return exchange.create_market_buy_order(symbol, qty)
    except Exception as e:
        log.error(f"BUY fail: {e}"); send_telegram(f"🚨 BUY 실패: {e}")
        return None

def cancel_reduce_orders(symbol):
    try:
        open_orders = exchange.fetch_open_orders(symbol)
        for o in open_orders:
            if o.get('reduceOnly', False) or o['type'] in ['STOP_MARKET','TAKE_PROFIT_MARKET','TRAILING_STOP_MARKET','STOP','TAKE_PROFIT']:
                try: exchange.cancel_order(o['id'], symbol)
                except Exception as ce: log.info(f"cancel warn: {ce}")
    except Exception as e:
        log.info(f"fetch_open_orders warn: {e}")

def place_reduce_order(symbol, side, amount, stop_price=None, tp=False):
    sside = 'sell' if side=='buy' else 'buy'
    typ = 'TAKE_PROFIT_MARKET' if tp else 'STOP_MARKET'
    return exchange.create_order(
        symbol=symbol, type=typ, side=sside, amount=amount,
        params={'stopPrice': round(stop_price, 2) if stop_price else None, 'reduceOnly': True}
    )

# ========= 메인 =========
def run():
    exchange.load_markets()  # 마켓 정보 로드
    if not USE_PAPER:
        set_leverage(SYMBOL, LEVERAGE)

    amt_prec, px_prec, min_amt = get_market_meta(SYMBOL)
    state = {
        'in_pos': False, 'entry': None, 'qty':0.0, 'runner_qty':0.0,
        'tp1_hit': False, 'last_trail': None, 'last_entry_bar': -999,
        'scaleouts_done': 0, 'pyramids_done': 0, 'day_pnl': 0.0,
        'last_day': None
    }

    send_telegram("🚀 ETH 실매매 봇(v2) 시작")
    log.info("Start ETH bot v2")

    while True:
        try:
            now = datetime.now(UTC)
            # 일자 변경 시 데이리셋
            day = now.date()
            if state['last_day'] != day:
                state['day_pnl'] = 0.0
                state['last_day'] = day

            next_close = (now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
            time.sleep(max(5, (next_close - now).total_seconds() + 3))

            df = fetch_ohlcv(SYMBOL, TIMEFRAME, limit=500)
            d  = build_indicators(df)
            if len(d) < 20: 
                continue
            p=PARAMS
            prev, cur = d.iloc[-2], d.iloc[-1]
            bar_index = len(d) - 1

            # 신호 신선도
            last_cross_idx = None
            for j in range(2, p['sig_max_bars']+3):
                a, b = d['ema_f'].iloc[-j], d['ema_s'].iloc[-j]
                a1, b1= d['ema_f'].iloc[-j-1], d['ema_s'].iloc[-j-1]
                if a1<=b1 and a>b:
                    last_cross_idx = len(d)-j
                    break
            fresh = last_cross_idx is not None and (len(d)-1 - last_cross_idx) <= p['sig_max_bars']
            adx_ok = cur['adx'] > p['adx_thr']
            rsi_ok = (cur['rsi'] > p['rsi_thr']) or adx_ok
            trend_up = cur['close'] > cur['ema_200']

            # 일일 손실 캡 체크 (PAPER 간이)
            if state['day_pnl'] <= -DAILY_LOSS_CAP_PCT:
                log.info("Daily loss cap reached. Skip entries today.")
                continue

            # === 진입 ===
            can_enter = (bar_index - state['last_entry_bar'] >= COOLDOWN_BARS)
            if (not state['in_pos']) and fresh and adx_ok and rsi_ok and trend_up and can_enter:
                entry = float(cur['close'])*(1+p['slippage'])
                sl = entry*(1 - p['fixed_sl_pct'])
                tp1= entry*(1 + p['tp1_pct'])

                equity = 10000.0 if USE_PAPER else exchange.fetch_balance()['total'].get('USDT', 10000.0)
                qty = calc_position_size(entry, sl, equity) * LEVERAGE
                qty = max(round_amt(qty, amt_prec), min_amt)
                if qty <= 0: continue

                if USE_PAPER:
                    state.update({'in_pos':True,'entry':entry,'qty':qty,
                                  'runner_qty': qty*(1-p['tp1_part']),
                                  'tp1_hit':False, 'last_trail':None,
                                  'last_entry_bar': bar_index,
                                  'scaleouts_done':0, 'pyramids_done':0})
                    log.info(f"[PAPER] BUY px={entry:.2f}, qty={qty}")
                else:
                    o = place_market_buy(SYMBOL, qty)
                    if not o: continue
                    cancel_reduce_orders(SYMBOL)
                    try:
                        place_reduce_order(SYMBOL,'buy', amount=qty*p['tp1_part'], stop_price=tp1, tp=True)
                        place_reduce_order(SYMBOL,'buy', amount=qty, stop_price=sl, tp=False)
                    except Exception as e:
                        log.info(f"TP/SL place warn: {e}")
                    state.update({'in_pos':True,'entry':entry,'qty':qty,
                                  'runner_qty': qty*(1-p['tp1_part']),
                                  'tp1_hit':False, 'last_trail':None,
                                  'last_entry_bar': bar_index,
                                  'scaleouts_done':0, 'pyramids_done':0})
                send_telegram(f"✅ LONG 진입 | px {entry:.2f} | qty {qty}")

            # === 보유 중 관리 ===
            if state['in_pos']:
                entry = state['entry']; qty=state['qty']
                trail = cur['close'] - p['atr_mult']*cur['atr']
                be    = entry*(1 + p['be_buffer'])
                trail_final = max(trail, be) if state['tp1_hit'] else max(trail, entry*(1-p['fixed_sl_pct']))

                # 추세 유지 필터: ADX와 200EMA 조건 만족 못하면 즉시 청산
                if (cur['adx'] <= p['adx_thr']) or (cur['close'] <= cur['ema_200']):
                    exit_px = float(cur['close'])
                    leftover = state['runner_qty'] if state['tp1_hit'] else qty
                    state['day_pnl'] += ((exit_px/entry)-1)*(leftover/qty)
                    state['in_pos'] = False
                    send_telegram(f"⚠️ Trend filter exit @ {exit_px:.2f}")
                    continue

                # TP1 체결(PAPER 감지)
                tp1_hit = state['tp1_hit']
                if not tp1_hit and cur['high'] >= entry*(1+p['tp1_pct']):
                    tp1_hit = True
                    state['runner_qty'] = qty*(1-p['tp1_part'])
                    send_telegram("TP1 체결(PAPER)")
                    # 일일 PnL 간이 반영
                    state['day_pnl'] += p['tp1_part']*p['tp1_pct']

                # 러너 분할매도(스케일아웃)
                if SCALEOUT_USE and tp1_hit and state['runner_qty']>0:
                    steps = len(SCALEOUT_STEPS_ATR)
                    each  = state['runner_qty']/steps
                    # 각 단계 TP 가격
                    for k in range(state['scaleouts_done'], steps):
                        tp_px = entry + SCALEOUT_STEPS_ATR[k]*float(cur['atr'])
                        if cur['high'] >= tp_px:
                            state['runner_qty'] -= each
                            state['scaleouts_done'] += 1
                            state['day_pnl'] += (tp_px/entry - 1)*(each/qty)
                            send_telegram(f"러너 분할익절 {k+1}/{steps} @ {tp_px:.2f}")
                        else:
                            break

                # 피라미딩(본절 이후, ADX 유지, 되돌림 후 재돌파)
                if PYRAMID_USE and tp1_hit and state['pyramids_done']<PYRAMID_MAX and adx_ok:
                    # 최근 10봉 고점 돌파 + 되돌림폭 조건 충족
                    recent_high = float(d['roll_high'].iloc[-2])
                    pullback_ok = (recent_high - float(cur['low'])) <= (PYRAMID_MIN_PULLBACK_ATR*float(cur['atr']))
                    if (cur['close'] > recent_high) and pullback_ok:
                        add_qty = qty * PYRAMID_SIZE_FACTOR
                        add_qty = round_amt(add_qty, amt_prec)
                        if add_qty >= min_amt:
                            if USE_PAPER:
                                qty += add_qty
                                state['qty'] = qty
                                state['runner_qty'] += add_qty   # 추가 물량은 전부 러너에 합류
                                state['pyramids_done'] += 1
                                send_telegram(f"🔼 피라미딩 {state['pyramids_done']}/{PYRAMID_MAX} +{add_qty}")
                            else:
                                o = place_market_buy(SYMBOL, add_qty)
                                if o:
                                    state['pyramids_done'] += 1
                                    state['runner_qty'] += add_qty
                                    send_telegram(f"🔼 피라미딩 체결 {state['pyramids_done']}/{PYRAMID_MAX} +{add_qty}")

                # 트레일/스톱 처리 (PAPER 종가 비교)
                if cur['low'] <= trail_final:
                    # 최종 청산 가정
                    state['in_pos']=False
                    # 남은 러너 손익 간이 반영
                    leftover = max(state['runner_qty'], 0.0)
                    if leftover>0:
                        state['day_pnl'] += ((trail_final/entry)-1)*(leftover/qty)
                    send_telegram(f"🏁 STOP(PAPER) @ {trail_final:.2f}")
                else:
                    state['tp1_hit']=tp1_hit
                    state['last_trail']=trail_final

        except KeyboardInterrupt:
            log.info("user stop"); send_telegram("🛑 사용자 중지"); break
        except Exception as e:
            log.error(f"loop err: {e}")
            send_telegram(f"🚨 런타임 오류: {e}")
            time.sleep(10)

if __name__ == '__main__':
    run()
