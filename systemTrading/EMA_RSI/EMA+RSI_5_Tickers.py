# 2025.07.10 - 로그 파일 저장 추가 및 안정성 강화
# 2025.07.26 - .env 연동, 로깅 인코딩 수정 (StreamHandler 오류 수정), 마진/레버리지 설정 추가
# 2025.07.26 - 새로운 config.py (SYMBOL_PARAMS) 구조에 맞춰 코드 수정
# 2025.07.26 - 'logger' is not defined 오류 해결
# 2025.07.27 - 서버 측 TP/SL 주문 기능 추가 및 포지션 상태 관리 로직 개선

import os
import sys
from dotenv import load_dotenv
import ccxt, pandas as pd, time, datetime, requests, logging

# .env 파일 로드 (가장 먼저 실행)
load_dotenv()

# config.py에서 설정 불러오기 (새로운 구조에 맞게 변경)
from config import (
    MAX_CONSECUTIVE_LOSSES,
    MAX_DAILY_TRADES,
    SYMBOLS,       # SYMBOLS 리스트를 불러옴
    SYMBOL_PARAMS  # SYMBOL_PARAMS 딕셔너리를 불러옴
)

# .env 파일에서 민감 정보 불러오기
api_key = os.getenv("API_KEY")
secret = os.getenv("SECRET_KEY")
telegram_token = os.getenv("TELEGRAM_TOKEN")
telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")

# 로그 설정: 터미널 + bot.log 파일에 출력 (StreamHandler encoding 오류 수정)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', mode='a', encoding='utf-8'), # 파일 핸들러는 encoding='utf-8' 유지
        logging.StreamHandler(stream=sys.stdout) # StreamHandler에서 encoding='utf-8' 제거 (오류 해결)
    ]
)

# ── 모드 스위치 ───────────────────────────────
use_paper = False  # 페이퍼 모드: True면 가상 매매, False면 실제 거래

# ── CCXT 설정 ────────────────────────────────
exchange = ccxt.binance({
    'apiKey': api_key, 'secret': secret,
    'enableRateLimit': True, 'options': {'defaultType': 'future'}
})
exchange.set_sandbox_mode(False) # 실제 거래 시 False, 테스트 시 True

# ── Telegram 메시지 함수 ───────────────────────
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    try:
        requests.post(url, json={"chat_id": telegram_chat_id, "text": msg})
        logging.info(f"Telegram 전송: {msg}")
    except Exception as e:
        logging.warning(f"Telegram 전송 실패: {e}")

# ── 주문 함수 ───────────────────────────────────
def paper_order(side, price, amt, symbol_name):
    logging.info(f"[PAPER] {symbol_name} {side}@{price:.2f} x{amt}")
    return {"status": "ok", "id": "paper_order_id"} # paper_order도 리턴값을 주도록 변경

def real_order(side, amt, symbol_name):
    try:
        o = exchange.create_market_order(symbol_name, side, amt)
        logging.info(f"[REAL] {symbol_name} {side} executed: {o}")
        return o # 실제 주문 객체 반환
    except Exception as e:
        logging.error(f"[REAL] {symbol_name} {side} 주문 실패: {e}")
        send_telegram(f"🚨 주문 실패 ({symbol_name}): {e}")
        return None

def place_order(side, price, amt, symbol_name):
    # 이제 place_order는 진입 주문만 담당하고, 성공 시 주문 객체를 반환합니다.
    return paper_order(side, price, amt, symbol_name) if use_paper else real_order(side, amt, symbol_name)

# ── 서버 측 TP/SL 주문 함수 추가 ────────────────
def place_tpsl_orders(side, amount, symbol_name, tp_price, sl_price, logger):
    """
    거래소에 Take Profit Market 및 Stop Market 주문을 제출합니다.
    주의: 이 함수는 진입 포지션이 성공적으로 열린 후에 호출되어야 합니다.
    """
    try:
        # 기존에 열려있는 TP/SL 주문이 있다면 먼저 취소 (중복 방지)
        open_orders = exchange.fetch_open_orders(symbol_name)
        for order in open_orders:
            # TP/SL 목적의 주문만 취소 (유형, 리듀스온리 등 확인 필요)
            # 여기서는 간단히 포지션 종료 목적의 주문이라고 가정하고 취소
            if order['reduceOnly'] or order['type'] in ['STOP_MARKET', 'TAKE_PROFIT_MARKET', 'STOP_LIMIT', 'TAKE_PROFIT_LIMIT']:
                try:
                    exchange.cancel_order(order['id'], symbol_name)
                    logger.info(f"[{symbol_name}] 기존 TP/SL 주문 (ID: {order['id']}) 취소 완료.")
                except Exception as cancel_e:
                    logger.warning(f"[{symbol_name}] 기존 TP/SL 주문 취소 실패 (ID: {order['id']}): {cancel_e}")

        # TP (Take Profit Market) Order
        # 매수 진입 시에는 매도(sell) TP, 매도 진입 시에는 매수(buy) TP
        tp_side = 'sell' if side == 'buy' else 'buy'
        
        # Binance Futures API에서 take_profit_market은 price 인자를 사용하지 않고 stopPrice로 트리거 가격을 설정합니다.
        # price는 limit order에서만 사용됩니다.
        tp_order = exchange.create_order(
            symbol=symbol_name,
            type='TAKE_PROFIT_MARKET', 
            side=tp_side,
            amount=amount, # 포지션 전체 수량
            params={'stopPrice': tp_price, 'reduceOnly': True} # stopPrice는 트리거 가격
        )
        logger.info(f"[{symbol_name}] TP 주문 ({tp_side} {amount} @ 트리거 가격:{tp_price:.4f}) 등록 완료: {tp_order['id']}")
        
        # SL (Stop Market) Order
        # 매수 진입 시에는 매도(sell) SL, 매도 진입 시에는 매수(buy) SL
        sl_side = 'sell' if side == 'buy' else 'buy'
        sl_order = exchange.create_order(
            symbol=symbol_name,
            type='STOP_MARKET', 
            side=sl_side,
            amount=amount, # 포지션 전체 수량
            params={'stopPrice': sl_price, 'reduceOnly': True} # stopPrice는 트리거 가격
        )
        logger.info(f"[{symbol_name}] SL 주문 ({sl_side} {amount} @ 트리거 가격:{sl_price:.4f}) 등록 완료: {sl_order['id']}")
        return True

    except ccxt.ExchangeError as e:
        logger.error(f"[{symbol_name}] TP/SL 주문 등록 실패 (거래소 오류): {e}")
        send_telegram(f"🚨 TP/SL 주문 실패 ({symbol_name}): {e}")
        return False
    except Exception as e:
        logger.error(f"[{symbol_name}] 알 수 없는 오류로 TP/SL 주문 등록 실패: {e}")
        send_telegram(f"🚨 TP/SL 주문 실패 ({symbol_name}): {e}")
        return False

# ── 변수 통일 & 리셋용 ──────────────────────────
# 각 심볼별로 별도의 상태를 관리하기 위한 딕셔너리
ticker_states = {}
for s in SYMBOLS: # config.SYMBOLS 사용
    ticker_states[s] = {
        'position': None, # 포지션 상태 (봇 내부 관리)
        'consec_losses': 0,
        'daily_trades': 0,
        'last_day': datetime.datetime.now().date()
    }

# ── 데이터 처리 ─────────────────────────────────
def fetch_ohlcv(sym, tf): # timeframe 인자 추가
    df = pd.DataFrame(exchange.fetch_ohlcv(sym, tf, limit=100), # tf 사용
                      columns=['timestamp','open','high','low','close','volume'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

def calc_indicators(df, rsi_p, ema_f, ema_s): # 지표 파라미터 인자로 받도록 수정
    df['EMA_fast'] = df['close'].ewm(span=ema_f, adjust=False).mean()
    df['EMA_slow'] = df['close'].ewm(span=ema_s, adjust=False).mean()
    delta = df['close'].diff()
    gain, loss = delta.clip(lower=0), -delta.clip(upper=0)
    avg_g = gain.ewm(com=rsi_p - 1, adjust=False).mean()
    avg_l = loss.ewm(com=rsi_p - 1, adjust=False).mean()
    rs = avg_g / avg_l
    df['RSI'] = 100 - (100 / (1 + rs))
    return df

# ── 전략 + 방어 코드 + 리스크 체크 ────────────────
def check_strategy_for_ticker(exchange_obj, current_symbol):
    # 각 티커별 상태 로드
    state = ticker_states[current_symbol]
    position = state['position'] # 봇 내부의 포지션 상태
    consec_losses = state['consec_losses']
    daily_trades = state['daily_trades']
    last_day = state['last_day']
    
    # 해당 티커의 파라미터 불러오기 (SYMBOL_PARAMS에서)
    params = SYMBOL_PARAMS.get(current_symbol)
    if not params:
        logging.error(f"[{current_symbol}] config.SYMBOL_PARAMS에 해당 티커 설정이 없습니다. 스킵합니다.")
        return

    # 티커별 파라미터 할당 (leverage 파라미터 추가)
    timeframe = params['timeframe']
    tp = params['tp']
    sl = params['sl']
    position_size = params['position_size'] # 진입 수량 (코인 기준)
    ema_fast_period = params['ema_fast']
    ema_slow_period = params['ema_slow']
    rsi_period = params['rsi_period']
    rsi_threshold = params['rsi_threshold']
    leverage = params['leverage']

    # ----------------------------------------------------
    # logger 변수 정의를 마진/레버리지 설정 등 logger를 사용하기 전에 위치시킵니다.
    logger = logging.getLogger(current_symbol) # <--- 'logger' 정의 위치 수정됨
    # ----------------------------------------------------

    today = datetime.datetime.now().date()
    if today != last_day:
        daily_trades, consec_losses = 0, 0
        state['last_day'] = today
        logger.info(f"{today}로 날짜 변경, 거래/손실 횟수 리셋")

    # ----------------------------------------------------
    # 포지션 상태 최신화 (매번 점검 시)
    # 실제 거래소의 포지션 정보를 가져와 봇 내부 상태와 동기화
    try:
        # Binance Futures는 fetch_positions에 symbol 필터링을 지원합니다.
        current_positions = exchange_obj.fetch_positions([current_symbol])
        
        exchange_position = None
        for p in current_positions:
            if p['symbol'] == current_symbol and float(p['positionAmt']) != 0:
                exchange_position = p
                break # 해당 심볼의 포지션을 찾으면 루프 종료

        if exchange_position:
            # 거래소에 포지션이 열려있음
            position_amt = float(exchange_position['positionAmt'])
            exchange_entry_price = float(exchange_position['entryPrice'])
            
            # 봇 내부 상태가 포지션이 없다고 판단했지만 거래소에 있다면 복구
            if position is None:
                # 봇의 TP/SL 목표 가격을 거래소 포지션 기준으로 재설정
                recovered_tp = exchange_entry_price * (1 + tp)
                recovered_sl = exchange_entry_price * (1 - sl)
                # 'amount' 키를 추가하여 TP/SL 주문 시 사용될 수량을 저장
                position = {'entry': exchange_entry_price, 'tp': recovered_tp, 'sl': recovered_sl, 'amount': abs(position_amt)}
                logger.info(f"[{current_symbol}] 거래소에서 포지션 감지 및 상태 복구. Size: {position_amt}, Entry: {exchange_entry_price:.4f}")
                
                # 복구된 포지션에 TP/SL 주문이 없으면 다시 제출 시도 (선택 사항, 중복 방지 로직 필요)
                # 여기서는 fetch_open_orders로 기존 TP/SL이 있는지 확인하는 로직을 추가하는 것이 좋지만,
                # place_tpsl_orders 함수 내에서 기존 주문 취소 로직이 있으므로 일단은 이대로 진행.
                if not use_paper: # 실거래 모드에서만 TP/SL 재설정 시도
                    # 기존 TP/SL이 없는 경우에만 새롭게 설정하도록 로직 추가 필요
                    # 지금은 단순히 logger.info만 함. 더 정교한 처리를 위해 fetch_open_orders 확인 필요
                    logger.info(f"[{current_symbol}] 복구된 포지션의 TP/SL 주문 상태 확인 필요.")
            else:
                # 봇 내부 상태와 거래소 상태가 일치함 (포지션 있음)
                logger.info(f"[{current_symbol}] 거래소 포지션 확인: {position_amt} @ {exchange_entry_price:.4f}")
        else:
            # 거래소에 포지션이 열려있지 않음
            if position is not None:
                # 봇 내부 상태는 포지션이 있다고 판단했지만 거래소에 없다면 초기화
                logger.info(f"[{current_symbol}] 거래소에 포지션 없음. 내부 상태 초기화 (TP/SL 또는 수동 종료 추정).")
                position = None # 봇의 포지션 상태 초기화
                consec_losses = 0 # 포지션 종료 시 손실 횟수 리셋 (정확한 손실/익절 판단은 별도 로직 필요)
                                  # 이 부분은 서버 측 TP/SL 체결 시 실제 익절/손절 여부를 확인하여 더 정확히 업데이트 필요
            # 포지션이 없으므로, 해당 심볼의 미체결 TP/SL 주문이 있다면 취소
            open_orders = exchange_obj.fetch_open_orders(current_symbol)
            for order in open_orders:
                # TP/SL 주문으로 추정되는 주문들 취소
                if order['reduceOnly'] or order['type'] in ['STOP_MARKET', 'TAKE_PROFIT_MARKET', 'STOP_LIMIT', 'TAKE_PROFIT_LIMIT']:
                    try:
                        exchange_obj.cancel_order(order['id'], symbol_name)
                        logger.info(f"[{current_symbol}] 잔여 TP/SL 주문 (ID: {order['id']}) 취소 완료 (포지션 없음).")
                    except Exception as cancel_e:
                        logger.warning(f"[{current_symbol}] 잔여 TP/SL 주문 취소 실패 (ID: {order['id']}): {cancel_e}")
            
    except ccxt.ExchangeError as e:
        logger.error(f"[{current_symbol}] 포지션 정보 가져오기 실패 (거래소 오류): {e}")
        send_telegram(f"🚨 포지션 정보 오류 ({current_symbol}): {e}")
        return # 심각한 오류이므로 해당 심볼 점검 중단
    except Exception as e:
        logger.error(f"[{current_symbol}] 포지션 정보 가져오기 중 알 수 없는 오류 발생: {e}")
        send_telegram(f"🚨 포지션 정보 오류 ({current_symbol}): {e}")
        return # 심각한 오류이므로 해당 심볼 점검 중단
    # ----------------------------------------------------


    # 글로벌 리스크 관리 설정 사용
    if consec_losses >= MAX_CONSECUTIVE_LOSSES:
        msg = f"연속 손실 {consec_losses}회 → 진입 스킵"
        logger.info(msg); send_telegram(f"🚨 {current_symbol}: " + msg); return
    if daily_trades >= MAX_DAILY_TRADES:
        msg = f"일일 거래 {daily_trades}회 → 진입 스킵"
        logger.info(msg); send_telegram(f"🚨 {current_symbol}: " + msg); return

    for attempt in range(3):
        try:
            df = calc_indicators(fetch_ohlcv(current_symbol, timeframe), rsi_period, ema_fast_period, ema_slow_period)
            break
        except Exception as e:
            logger.warning(f"[{current_symbol}] 데이터 가져오기 실패 {attempt+1}/3: {e}")
            time.sleep(5)
    else:
        msg = "OHLCV 가져오기 3회 실패, 스킵"
        logger.error(msg); send_telegram(f"❌ {current_symbol}: " + msg); return

    if df.empty or len(df) < max(rsi_period, ema_slow_period) + 2: # 충분한 데이터가 있는지 확인
        logger.info(f"[{current_symbol}] 데이터 부족 → 스킵"); return

    prev = df.iloc[-2]
    latest = df.iloc[-1]

    if pd.isna(prev[['EMA_fast','EMA_slow','RSI']]).any():
        logger.info(f"[{current_symbol}] 지표 결측 → 스킵"); return

    if position is None: # 포지션이 없을 때만 진입 시도
        if (prev['EMA_fast'] > prev['EMA_slow'] and
            prev['RSI'] > rsi_threshold):
            entry_price = latest['close']
            order_amount = position_size 
            
            # 진입 주문 실행
            entry_order_result = place_order('buy', entry_price, order_amount, current_symbol)
            
            if entry_order_result and entry_order_result['status'] == 'ok': # 진입 주문 성공 시
                # 봇의 내부 포지션 상태 업데이트
                # entry_order_result의 'filled' 양을 사용하거나, 간단히 order_amount를 사용
                position_filled_amount = float(entry_order_result.get('filled', order_amount)) 
                position = {'entry': entry_price, 'tp': entry_price * (1 + tp), 'sl': entry_price * (1 - sl), 'amount': position_filled_amount}
                daily_trades += 1
                msg = f"✅ [진입] {current_symbol} | 가격: {entry_price:.4f} | 수량: {position_filled_amount}"
                logger.info(msg); send_telegram(msg)
                
                # 서버 측 TP/SL 주문 제출 (실제 거래 모드에서만)
                if not use_paper:
                    place_tpsl_orders('buy', position_filled_amount, current_symbol, position['tp'], position['sl'], logger)
            else: # 진입 주문 실패 시 (place_order에서 이미 로그/텔레그램 전송)
                logger.error(f"[{current_symbol}] 진입 주문 실패로 TP/SL 미등록.")
        else:
            logger.info(f"[{current_symbol}] 진입 조건 불충족: EMA_F({prev.EMA_fast:.2f}), EMA_S({prev.EMA_slow:.2f}), RSI({prev.RSI:.2f})")
    else: # 포지션이 열려있을 때
        # 서버 측 TP/SL을 사용하므로, 가격 체크로 수동 종료하는 로직은 더 이상 필요 없습니다.
        # 포지션 종료는 거래소에서 자동으로 처리합니다.
        # 여기서는 단순히 포지션 홀드 상태를 로그로 남깁니다.
        current_price = latest['close']
        logger.info(f"[{current_symbol}] [홀드] 현재가 {current_price:.4f} (TP:{position['tp']:.4f}, SL:{position['sl']:.4f})")
        
        # 만약 TP/SL이 체결되었음에도 봇 내부 position이 남아있는 경우를 대비한 추가 로직 (상단에서 이미 처리)
        # 즉, 상단의 fetch_positions() 로직이 포지션 상태를 업데이트하는 핵심입니다.

    # 각 심볼별 상태 업데이트
    state['position'] = position
    state['consec_losses'] = consec_losses
    state['daily_trades'] = daily_trades
    ticker_states[current_symbol] = state

# ── 메인 루프: 1시간봉 캔들 마감에 맞춰 실행 ───────
def main():
    # 프로그램 시작 알림 추가
    send_telegram("🚀 자동매매 봇이 시작되었습니다!")
    logging.info("[SYSTEM] 자동매매 봇 시작.")
    
    while True:
        try:
            now = datetime.datetime.now()
            # 다음 정시까지 남은 시간 계산 (1분 0초까지 대기)
            next_hour = (now.replace(minute=0, second=0, microsecond=0) +
                         datetime.timedelta(hours=1))
            wait_seconds = (next_hour - now).total_seconds()

            if wait_seconds < 0: # 이미 시간이 지났다면 다음 시간으로
                next_hour = next_hour + datetime.timedelta(hours=1)
                wait_seconds = (next_hour - now).total_seconds()

            logging.info(f"[SYSTEM] 다음 캔들까지 {int(wait_seconds)}초 대기...")
            time.sleep(wait_seconds + 5) # 5초 여유 추가

            logging.info(f"------ {datetime.datetime.now()} 점검 시작 ------")
            for symbol_name in SYMBOLS: # config.SYMBOLS 사용
                check_strategy_for_ticker(exchange, symbol_name)

        except KeyboardInterrupt:
            logging.info("[SYSTEM] 프로그램 종료: 사용자 중단")
            send_telegram("프로그램 종료: 사용자 중단")
            break
        except Exception as e:
            logging.error(f"[ERROR] {e}")
            send_telegram(f"🚨 [CRITICAL ERROR] 프로그램 오류: {e}")
            time.sleep(60) # 오류 발생 시 1분 대기 후 재시도

if __name__ == "__main__":
    main()