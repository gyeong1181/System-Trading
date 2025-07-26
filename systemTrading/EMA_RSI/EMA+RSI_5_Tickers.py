import os
from dotenv import load_dotenv

load_dotenv() # .env 파일에서 환경 변수들을 로드합니다.

import ccxt
import pandas as pd
import time
import datetime
import requests
import logging

# API 키 및 민감 정보는 .env 파일에서 불러옵니다.
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

from config import MAX_CONSECUTIVE_LOSSES, MAX_DAILY_TRADES, SYMBOLS, SYMBOL_PARAMS

# --- 로깅 설정 ---
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(ticker)s] - %(message)s')

from logging.handlers import TimedRotatingFileHandler
file_handler = TimedRotatingFileHandler(f'trade_bot.log', when='midnight', interval=1, backupCount=30)
file_handler.setFormatter(formatter)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.addHandler(stream_handler)


# --- 1. 글로벌 상태 변수 ---
# 각 티커별 포지션 및 상태를 저장할 딕셔너리
# {'symbol': {'entry_price': price, 'tp_order_id': id, 'sl_order_id': id} or None}
positions = {symbol: None for symbol in SYMBOLS} 
# 전체 티커 합산 리스크 관리 변수
total_consecutive_losses = 0
total_daily_trades = 0
last_trade_date = datetime.date.today()


# --- 2. 핵심 기능 함수 ---
def get_exchange():
    """CCXT 거래소 객체 생성"""
    exchange = ccxt.binance({
        'apiKey': API_KEY, 'secret': SECRET_KEY,
        'enableRateLimit': True, 'options': {'defaultType': 'future'}
    })
    return exchange

def send_telegram(message, ticker="SYSTEM"):
    """텔레그램 메시지 전송 (티커 정보 포함)"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        formatted_message = f"[{ticker}] {message}" if ticker != "SYSTEM" else message
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": formatted_message})
    except Exception as e:
        logger.warning(f"Telegram 전송 실패: {e}", extra={"ticker": ticker})

def fetch_ohlcv(exchange, ticker, timeframe):
    """OHLCV 데이터 가져오기"""
    for attempt in range(3):
        try:
            df = pd.DataFrame(exchange.fetch_ohlcv(ticker, timeframe, limit=100),
                              columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            logger.warning(f"{ticker} 데이터 가져오기 실패 {attempt+1}/3: {e}", extra={"ticker": ticker})
            time.sleep(5)
    raise Exception(f"{ticker} OHLCV 데이터 3회 가져오기 실패")


def calculate_indicators(df, params):
    """기술적 지표 계산"""
    df['EMA_fast'] = df['close'].ewm(span=params['ema_fast'], adjust=False).mean()
    df['EMA_slow'] = df['close'].ewm(span=params['ema_slow'], adjust=False).mean()
    
    delta = df['close'].diff()
    gain = delta.clip(lower=0).ewm(com=params['rsi_period'] - 1, adjust=False).mean()
    loss = -delta.clip(upper=0).ewm(com=params['rsi_period'] - 1, adjust=False).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    return df

# --- 3. 메인 전략 로직 (티커별 실행) ---
def check_strategy_for_ticker(exchange, ticker):
    """개별 티커에 대한 매매 전략을 확인하고 실행합니다."""
    global positions, total_consecutive_losses, total_daily_trades

    params = SYMBOL_PARAMS[ticker]
    log_extra = {"ticker": ticker} # 로그 구분을 위한 추가 정보

    # 데이터 가져오기 및 지표 계산
    try:
        df = fetch_ohlcv(exchange, ticker, params['timeframe'])
        df = calculate_indicators(df, params)
        if df.empty or len(df) < 2 or pd.isna(df.iloc[-2][['EMA_fast', 'EMA_slow', 'RSI']]).any():
            logger.info(f"{ticker} 데이터 부족 또는 지표 결측으로 스킵", extra=log_extra)
            return
    except Exception as e:
        logger.error(f"{ticker} 데이터 처리 중 오류 발생: {e}", extra=log_extra)
        send_telegram(f"🚨 데이터 처리 실패: {e}", ticker=ticker)
        return

    prev_candle = df.iloc[-2]
    latest_candle = df.iloc[-1]
    current_price = latest_candle['close']
    
    # --- 3.1. 진입 로직 ---
    if positions[ticker] is None: # 현재 봇에 포지션이 없다고 판단될 때
        # 글로벌 리스크 관리 체크
        if total_consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
            logger.warning(f"전체 연속 손실 {total_consecutive_losses}회 도달. {ticker} 신규 진입 중단.", extra=log_extra)
            return
        if total_daily_trades >= MAX_DAILY_TRADES:
            logger.warning(f"일일 최대 거래 {total_daily_trades}회 도달. {ticker} 신규 진입 중단.", extra=log_extra)
            return

        # 진입 조건 확인
        if prev_candle['EMA_fast'] > prev_candle['EMA_slow'] and prev_candle['RSI'] > params['rsi_threshold']:
            entry_price = current_price
            tp_price = entry_price * (1 + params['tp'])
            sl_price = entry_price * (1 - params['sl'])
            
            try:
                # 1. 진입 주문 (시장가 매수)
                entry_order = exchange.create_order(
                    symbol=ticker,
                    type='market',
                    side='buy',
                    amount=params['position_size'],
                    params={'reduceOnly': False} # 반드시 새 포지션 생성 명시 (Binance Futures)
                )
                logger.info(f"실제 주문 실행: BUY {params['position_size']} {ticker} @ {entry_price:.4f}", extra=log_extra)
                
                # 2. 손절(SL) 주문 (STOP_MARKET) - 포지션 청산용
                sl_order = exchange.create_order(
                    symbol=ticker,
                    type='STOP_MARKET', # Stop Market order type
                    side='sell', # To close a long position
                    amount=params['position_size'],
                    params={'stopPrice': sl_price, 'closePosition': True} # Trigger price, 포지션 전체 청산 명시
                )
                logger.info(f"SL 주문 전송: {sl_order['id']} | StopPrice: {sl_price:.4f}", extra=log_extra)

                # 3. 익절(TP) 주문 (TAKE_PROFIT_MARKET) - 포지션 청산용
                tp_order = exchange.create_order(
                    symbol=ticker,
                    type='TAKE_PROFIT_MARKET', # Take Profit Market order type
                    side='sell', # To close a long position
                    amount=params['position_size'],
                    params={'stopPrice': tp_price, 'closePosition': True} # Trigger price, 포지션 전체 청산 명시
                )
                logger.info(f"TP 주문 전송: {tp_order['id']} | TriggerPrice: {tp_price:.4f}", extra=log_extra)

                # 봇의 내부 상태에 진입 정보 및 TP/SL 주문 ID 저장
                positions[ticker] = {
                    'entry_price': entry_price,
                    'tp_order_id': tp_order['id'],
                    'sl_order_id': sl_order['id']
                }
                total_daily_trades += 1
                
                msg = f"✅ [진입 및 TP/SL 주문 등록] {ticker} | 가격: {entry_price:.4f} | TP: {tp_price:.4f}, SL: {sl_price:.4f}"
                logger.info(msg, extra=log_extra)
                send_telegram(msg, ticker=ticker)

            except Exception as e:
                logger.error(f"주문 진입 또는 TP/SL 등록 실패: {e}", extra=log_extra)
                send_telegram(f"🚨 [오류] {ticker} 진입/TP/SL 등록 실패: {e}", ticker=ticker)
                
    # --- 3.2. 포지션 및 주문 상태 확인 (봇의 내부 상태 동기화) ---
    else: # 봇에 포지션이 있다고 판단될 때
        try:
            # 거래소에서 해당 티커의 실제 포지션 정보 가져오기
            # fetch_positions()는 모든 포지션을 반환하므로 해당 티커만 필터링
            open_positions = exchange.fetch_positions(symbols=[ticker]) 
            current_position_amount = 0.0
            
            for pos in open_positions:
                if pos['symbol'] == ticker and pos['side'] == 'long': # 진입이 롱(buy)이었음을 가정
                    current_position_amount = float(pos['info']['positionAmt']) # Binance Futures 'positionAmt'
                    break
            
            if current_position_amount == 0:
                # 거래소에 해당 포지션이 더 이상 없으면 (TP/SL 체결 또는 수동 청산)
                logger.info(f"{ticker} 포지션이 거래소에서 종료되었습니다.", extra=log_extra)
                send_telegram(f"✅ [알림] {ticker} 포지션이 거래소에서 종료되었습니다.", ticker=ticker)
                
                # 남아있는 TP/SL 주문 취소 (OCO와 유사하게 동작)
                if 'tp_order_id' in positions[ticker] and positions[ticker]['tp_order_id']:
                    try:
                        exchange.cancel_order(positions[ticker]['tp_order_id'], ticker)
                        logger.info(f"{ticker} TP 주문 {positions[ticker]['tp_order_id']} 취소 완료.", extra=log_extra)
                    except ccxt.OrderNotFound: # 이미 취소되었거나 체결된 경우
                        logger.info(f"{ticker} TP 주문 {positions[ticker]['tp_order_id']} 이미 처리됨.", extra=log_extra)
                    except Exception as cancel_e:
                        logger.warning(f"{ticker} TP 주문 취소 실패: {cancel_e}", extra=log_extra)
                
                if 'sl_order_id' in positions[ticker] and positions[ticker]['sl_order_id']:
                    try:
                        exchange.cancel_order(positions[ticker]['sl_order_id'], ticker)
                        logger.info(f"{ticker} SL 주문 {positions[ticker]['sl_order_id']} 취소 완료.", extra=log_extra)
                    except ccxt.OrderNotFound: # 이미 취소되었거나 체결된 경우
                        logger.info(f"{ticker} SL 주문 {positions[ticker]['sl_order_id']} 이미 처리됨.", extra=log_extra)
                    except Exception as cancel_e:
                        logger.warning(f"{ticker} SL 주문 취소 실패: {cancel_e}", extra=log_extra)

                positions[ticker] = None # 봇 내부 상태 리셋
                # total_daily_trades는 진입/청산 시에만 증가하도록 유지. (이미 청산되었으므로 여기서 다시 증가시키지 않음)
                # 연속 손실 카운팅은 실제 손실이 발생했는지 확인하는 별도 로직이 필요하지만, 여기서는 단순화.

            else:
                # 포지션이 아직 열려있음
                current_price = latest_candle['close']
                logger.info(f"포지션 유지. 현재가: {current_price:.4f}", extra=log_extra)

        except Exception as e:
            logger.error(f"{ticker} 포지션 상태 확인 중 오류 발생: {e}", extra=log_extra)
            send_telegram(f"🚨 [오류] {ticker} 포지션 확인 실패: {e}", ticker=ticker)


# --- 4. 메인 루프 ---
def main():
    """메인 실행 함수"""
    global last_trade_date, total_daily_trades, total_consecutive_losses
    
    log_extra = {"ticker": "SYSTEM"}
    logger.info("자동매매 시스템을 시작합니다.", extra=log_extra)
    send_telegram("🚀 자동매매 시스템이 시작되었습니다.", ticker="SYSTEM")
    exchange = get_exchange()

    while True:
        try:
            # 매시 정각 5초 후 실행
            now = datetime.datetime.now()
            next_hour = (now + datetime.timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            wait_seconds = (next_hour - now).total_seconds()
            
            if wait_seconds < 3600: # 대기 시간이 1시간 미만일 때만 대기
                logger.info(f"다음 실행까지 {wait_seconds:.0f}초 대기...", extra=log_extra)
                time.sleep(wait_seconds + 5)

            # 날짜 변경 시 글로벌 리스크 변수 리셋
            today = datetime.date.today()
            if today != last_trade_date:
                logger.info(f"날짜 변경: {today}. 일일 거래 횟수를 리셋합니다.", extra=log_extra)
                send_telegram(f"🗓️ 날짜 변경: {today}. 일일 거래 횟수를 리셋합니다.", ticker="SYSTEM")
                total_daily_trades = 0
                # 연속 손실은 날짜가 바뀌어도 유지되도록 주석 처리. 필요시 활성화.
                # total_consecutive_losses = 0 
                last_trade_date = today

            logger.info(f"====== {datetime.datetime.now()} 캔들 분석 시작 ======", extra=log_extra)
            # 설정된 모든 티커에 대해 전략 실행
            for symbol_item in SYMBOLS:
                check_strategy_for_ticker(exchange, symbol_item)
        
        except KeyboardInterrupt:
            logger.info("사용자에 의해 프로그램이 종료되었습니다.", extra=log_extra)
            send_telegram("🛑 사용자에 의해 프로그램이 종료되었습니다.", ticker="SYSTEM")
            break
        except Exception as e:
            logger.critical(f"메인 루프에서 예측 불가능한 오류 발생: {e}", extra=log_extra)
            send_telegram(f"🚨 [CRITICAL] 시스템 오류 발생: {e}", ticker="SYSTEM")
            time.sleep(60) # 심각한 오류 발생 시 1분 대기

if __name__ == "__main__":
    main()