from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

import httpx
from fastapi import FastAPI
from pydantic import BaseModel, Field

from binance_executor import BinanceFuturesExecutor
from db import BotDatabase
from exchange import BinanceRestClient
from notify import TelegramNotifier
from risk_manager import SymbolFilterStore, normalize_qty_price
from utils import get_app_logger, get_logger, load_env


class WebhookSignal(BaseModel):
    secret: str
    strategy_id: str
    symbol: str
    timeframe: str
    action: Literal["OPEN", "CLOSE"]
    side: Literal["LONG", "SHORT"]
    signal_time: str
    signal_id: str
    price: Optional[float] = None


class AppConfig:
    def __init__(self, env: dict):
        self.secret = env.get("TV_WEBHOOK_SECRET", "")
        self.allowed_symbols = {
            s.strip().upper()
            for s in (env.get("TV_ALLOWED_SYMBOLS") or "BTCUSDT,SOLUSDT").split(",")
            if s.strip()
        }
        self.allowed_timeframes = {
            t.strip().lower()
            for t in (env.get("TV_ALLOWED_TIMEFRAMES") or "1h").split(",")
            if t.strip()
        }
        self.execution_mode = env.get("EXECUTION_MODE", "RECEIVE_ONLY").upper()
        self.leverage = float(env.get("LEVERAGE_DEFAULT", 1))
        self.order_usdt = {
            "BTCUSDT": float(env.get("BTC_ORDER_USDT", 60)),
            "SOLUSDT": float(env.get("SOL_ORDER_USDT", 40)),
        }
        self.sl_pct = {
            "BTCUSDT": float(env.get("SL_PCT_BTC", 0.02)),
            "SOLUSDT": float(env.get("SL_PCT_SOL", 0.025)),
        }
        self.reserve = float(env.get("RESERVE_USDT", 0))
        self.margin_buffer = float(env.get("MARGIN_BUFFER", 0.05))
        self.close_before_reverse = env.get("CLOSE_BEFORE_REVERSE", "true").lower() not in (
            "0",
            "false",
            "no",
            "off",
        )
        self.db_path = Path(env.get("DB_PATH") or Path(__file__).resolve().parent / "data" / "bot.db")


env = load_env()
config = AppConfig(env)
logger = get_logger("WebhookServer")
app_logger = get_app_logger()
notifier = TelegramNotifier(env.get("TELEGRAM_BOT_TOKEN"), env.get("TELEGRAM_CHAT_ID"))
db = BotDatabase(config.db_path)
rest_client = BinanceRestClient()
filter_store = SymbolFilterStore(rest_client)


def _alert(message: str):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(notifier.send(message))
        else:
            loop.run_until_complete(notifier.send(message))
    except RuntimeError:
        # fallback if no loop available
        asyncio.run(notifier.send(message))


executor: Optional[BinanceFuturesExecutor]
if config.execution_mode == "LIVE":
    api_key = env.get("BINANCE_API_KEY")
    api_secret = env.get("BINANCE_API_SECRET")
    if not api_key or not api_secret:
        raise RuntimeError("BINANCE_API_KEY and BINANCE_API_SECRET are required for LIVE mode")
    executor = BinanceFuturesExecutor(api_key, api_secret, alert_cb=_alert)
else:
    executor = None

app = FastAPI()


async def _notify(message: str):
    await notifier.send(message)


def _log_event(event: str, **fields):
    payload = {"event": event, "ts": datetime.utcnow().isoformat(), **fields}
    app_logger.info(json.dumps(payload, ensure_ascii=False))


async def _get_mark_price(symbol: str) -> float:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://fapi.binance.com/fapi/v1/premiumIndex", params={"symbol": symbol.upper()}
        )
        resp.raise_for_status()
        data = resp.json()
        return float(data.get("markPrice", data.get("indexPrice", 0.0)))


def _reject(signal: WebhookSignal, reason: str):
    db.update_signal_status(signal.signal_id, reason)
    logger.warning("Rejected %s: %s", signal.signal_id, reason)


def _make_order_key(signal: WebhookSignal) -> str:
    return f"{signal.signal_id}_{signal.action}_{signal.side}"


async def _handle_open(signal: WebhookSignal):
    symbol = signal.symbol.upper()
    order_usdt = config.order_usdt.get(symbol, 0.0)
    if order_usdt <= 0:
        return {"status": "skip", "reason": "order_usdt_missing"}

    price = signal.price or await _get_mark_price(symbol)
    if price <= 0:
        _log_event("order_skip", symbol=symbol, reason="invalid_price", price=price)
        return {"status": "skip", "reason": "invalid_price"}
    filters = await filter_store.get(symbol)
    qty, _, err = normalize_qty_price(order_usdt / price, price, filters)
    if err:
        _log_event("order_skip", symbol=symbol, reason=err, qty=qty, price=price)
        await _notify(f"❌ {symbol} 주문 스킵: {err} (qty={qty:.6f})")
        return {"status": "skip", "reason": err}

    notional = qty * price
    if config.execution_mode == "DRY_RUN":
        _log_event("dryrun_calc", symbol=symbol, qty=qty, price=price, notional=notional)
        return {"status": "dry_run", "qty": qty, "price": price, "notional": notional}

    if executor is None:
        return {"status": "skip", "reason": "live_executor_missing"}

    await executor.ensure_oneway_mode()
    position = await executor.get_position(symbol)
    _log_event("position_state", symbol=symbol, side=position["side"], qty=position["amt"])
    if position["side"] == signal.side:
        return {"status": "skip", "reason": "already_in_position"}
    if position["side"] in ("LONG", "SHORT") and position["side"] != signal.side:
        if config.close_before_reverse:
            close_side = "SELL" if position["side"] == "LONG" else "BUY"
            _log_event("order_submit", symbol=symbol, action="CLOSE_BEFORE_REVERSE", side=close_side)
            await executor.place_market_order(symbol, close_side, position["amt"], reduce_only=True)
            await executor.wait(0.2)
        else:
            return {"status": "skip", "reason": "opposite_position_exists"}

    has_balance = await executor.has_balance_for(
        notional=notional,
        leverage=config.leverage,
        buffer=config.margin_buffer,
        reserve=config.reserve,
    )
    if not has_balance:
        _log_event("balance_state", symbol=symbol, notional=notional, reserve=config.reserve)
        await _notify(
            f"⚠️ 잔고 부족: {symbol} notional={notional:.2f} reserve={config.reserve:.2f}"
        )
        return {"status": "skip", "reason": "insufficient_balance"}

    side = "BUY" if signal.side == "LONG" else "SELL"
    _log_event("order_submit", symbol=symbol, action="OPEN", side=side, qty=qty)
    order_resp = await executor.place_market_order(symbol, side, qty, reduce_only=False)
    sl_pct = config.sl_pct.get(symbol, 0.02)
    if signal.side == "LONG":
        stop_price = price * (1 - sl_pct)
        stop_side = "SELL"
    else:
        stop_price = price * (1 + sl_pct)
        stop_side = "BUY"
    if filters.tick_size > 0:
        stop_price = (stop_price // filters.tick_size) * filters.tick_size
    _log_event("order_submit", symbol=symbol, action="STOP", side=stop_side, qty=qty, stop_price=stop_price)
    stop_resp = await executor.place_stop_market(symbol, stop_side, qty, stop_price, reduce_only=True)
    await _notify(
        f"✅ OPEN {signal.side} {symbol}\nqty={qty:.6f}\nprice={price:.2f}\nSL={stop_price:.2f}"
    )
    _log_event("order_ok", symbol=symbol, action="OPEN", qty=qty, price=price)
    return {"status": "ok", "order": order_resp, "stop": stop_resp, "qty": qty, "price": price}


async def _handle_close(signal: WebhookSignal):
    symbol = signal.symbol.upper()
    if config.execution_mode == "DRY_RUN":
        _log_event("dryrun_calc", symbol=symbol, action="CLOSE")
        return {"status": "dry_run", "reason": "close"}
    if executor is None:
        return {"status": "skip", "reason": "live_executor_missing"}

    position = await executor.get_position(symbol)
    _log_event("position_state", symbol=symbol, side=position["side"], qty=position["amt"])
    if position["side"] == "FLAT":
        return {"status": "skip", "reason": "no_position"}
    if position["side"] != signal.side:
        return {"status": "skip", "reason": "position_side_mismatch"}

    side = "SELL" if signal.side == "LONG" else "BUY"
    _log_event("order_submit", symbol=symbol, action="CLOSE", side=side, qty=position["amt"])
    resp = await executor.place_market_order(symbol, side, position["amt"], reduce_only=True)
    await _notify(f"✅ CLOSE {signal.side} {symbol}\nqty={position['amt']:.6f}")
    _log_event("order_ok", symbol=symbol, action="CLOSE", qty=position["amt"])
    return {"status": "ok", "order": resp, "qty": position["amt"]}


@app.get("/health")
async def health():
    return {"status": "ok", "mode": config.execution_mode}


@app.post("/tv/webhook")
async def tv_webhook(signal: WebhookSignal):
    payload = signal.dict()
    inserted = db.insert_signal(signal.signal_id, payload, "received")
    _log_event("webhook_received", signal_id=signal.signal_id, symbol=signal.symbol, action=signal.action)
    if not inserted:
        db.update_signal_status(signal.signal_id, "dedup_hit")
        _log_event("dedup_hit", signal_id=signal.signal_id)
        return {"status": "duplicate"}

    if signal.secret != config.secret:
        _reject(signal, "rejected_secret")
        _log_event("rejected", reason="secret", signal_id=signal.signal_id)
        return {"status": "rejected_secret"}
    if signal.symbol.upper() not in config.allowed_symbols:
        _reject(signal, "rejected_symbol")
        _log_event("rejected", reason="symbol", signal_id=signal.signal_id)
        return {"status": "rejected_symbol"}
    if signal.timeframe.lower() not in config.allowed_timeframes:
        _reject(signal, "rejected_timeframe")
        _log_event("rejected", reason="timeframe", signal_id=signal.signal_id)
        return {"status": "rejected_timeframe"}

    if config.execution_mode == "RECEIVE_ONLY":
        db.update_signal_status(signal.signal_id, "received_only")
        await _notify(f"📩 Webhook received: {signal.symbol} {signal.action} {signal.side}")
        _log_event("validated", mode="RECEIVE_ONLY", signal_id=signal.signal_id)
        return {"status": "received_only"}

    order_key = _make_order_key(signal)
    try:
        if signal.action == "OPEN":
            result = await _handle_open(signal)
        else:
            result = await _handle_close(signal)
        status = result.get("status", "unknown")
        db.insert_order(
            order_key=order_key,
            signal_id=signal.signal_id,
            symbol=signal.symbol,
            action=signal.action,
            side=signal.side,
            qty=float(result.get("qty", 0.0)),
            request=payload,
            response=result,
            status=status,
        )
        db.update_signal_status(signal.signal_id, status)
        return {"status": status}
    except Exception as exc:
        err_msg = str(exc)
        _log_event("order_fail", signal_id=signal.signal_id, error=err_msg)
        db.insert_order(
            order_key=order_key,
            signal_id=signal.signal_id,
            symbol=signal.symbol,
            action=signal.action,
            side=signal.side,
            qty=0.0,
            request=payload,
            response=None,
            status="error",
            error=err_msg,
        )
        db.update_signal_status(signal.signal_id, "error")
        app_logger.error("webhook_error=%s signal_id=%s", err_msg, signal.signal_id)
        await _notify(f"🚨 Webhook 처리 실패: {err_msg}")
        return {"status": "error"}
