from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

import httpx
from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
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
    action: Optional[Literal["OPEN", "CLOSE"]] = None
    side: Optional[Literal["LONG", "SHORT"]] = None
    order_action: Optional[str] = Field(default=None)
    position_size: Optional[float] = None
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
        self.allowed_timeframes_by_symbol = {}
        per_symbol_raw = (env.get("TV_ALLOWED_TIMEFRAMES_BY_SYMBOL") or "").strip()
        if per_symbol_raw:
            for item in per_symbol_raw.split(","):
                pair = item.strip()
                if not pair or ":" not in pair:
                    continue
                symbol, tf = pair.split(":", 1)
                self.allowed_timeframes_by_symbol[symbol.strip().upper()] = tf.strip().lower()
        self.execution_mode = env.get("EXECUTION_MODE", "RECEIVE_ONLY").upper()
        self.leverage = float(env.get("LEVERAGE_DEFAULT", 1))
        self.order_sizing_mode = (env.get("ORDER_SIZING_MODE") or "FIXED").strip().upper()
        self.order_usdt = {
            "BTCUSDT": float(env.get("BTC_ORDER_USDT", 60)),
            "SOLUSDT": float(env.get("SOL_ORDER_USDT", 40)),
        }
        self.order_equity_pct = {
            "BTCUSDT": float(env.get("BTC_ORDER_EQUITY_PCT", 0.2)),
            "SOLUSDT": float(env.get("SOL_ORDER_EQUITY_PCT", 0.2)),
        }
        self.total_target_leverage = float(env.get("TOTAL_TARGET_LEVERAGE", 1.5))
        self.operating_capital_ratio = float(env.get("OPERATING_CAPITAL_RATIO", 0.8))
        self.symbol_weights = self._parse_symbol_weights(env.get("SYMBOL_WEIGHTS"))
        self.preset_symbol_leverage = int(float(env.get("PRESET_SYMBOL_LEVERAGE", 5)))
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

    @staticmethod
    def _parse_symbol_weights(raw: Optional[str]) -> dict[str, float]:
        defaults = {"BTCUSDT": 0.6, "SOLUSDT": 0.4}
        if not raw:
            return defaults
        value = raw.strip()
        parsed: dict[str, float] = {}
        if value.startswith("{"):
            try:
                obj = json.loads(value)
                for symbol, weight in obj.items():
                    parsed[str(symbol).upper()] = float(weight)
            except Exception:
                parsed = {}
        else:
            for part in value.split(","):
                if ":" not in part:
                    continue
                symbol, weight = part.split(":", 1)
                try:
                    parsed[symbol.strip().upper()] = float(weight)
                except ValueError:
                    continue
        return parsed or defaults


env = load_env()
config = AppConfig(env)
logger = get_logger("WebhookServer")
app_logger = get_app_logger()
notifier = TelegramNotifier(env.get("TELEGRAM_BOT_TOKEN"), env.get("TELEGRAM_CHAT_ID"))
db = BotDatabase(config.db_path)
rest_client = BinanceRestClient()
filter_store = SymbolFilterStore(rest_client)
APP_START_TS = time.time()

WEBHOOK_RECEIVED_TOTAL = Counter(
    "webhook_received_total",
    "Total webhook requests received",
    ["symbol"],
)
WEBHOOK_RESULT_TOTAL = Counter(
    "webhook_result_total",
    "Webhook processing result count",
    ["status", "symbol", "action"],
)
WEBHOOK_PROCESS_SECONDS = Histogram(
    "webhook_process_seconds",
    "Webhook processing latency in seconds",
    buckets=(0.01, 0.03, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0),
)
ORDER_RESULT_TOTAL = Counter(
    "order_result_total",
    "Order result count",
    ["status", "symbol", "action", "side"],
)
ORDER_SKIP_TOTAL = Counter(
    "order_skip_total",
    "Order skip count",
    ["symbol", "reason"],
)
BINANCE_API_ERROR_TOTAL = Counter(
    "binance_api_error_total",
    "Binance API error count",
    ["endpoint", "status_code"],
)
APP_UPTIME_SECONDS = Gauge(
    "app_uptime_seconds",
    "Application uptime in seconds",
)
EXECUTION_MODE_INFO = Gauge(
    "execution_mode_info",
    "Current execution mode info gauge",
    ["mode"],
)


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


def _on_binance_api_error(path: str, status_code: int):
    BINANCE_API_ERROR_TOTAL.labels(path, str(status_code)).inc()


executor: Optional[BinanceFuturesExecutor]
if config.execution_mode == "LIVE":
    api_key = env.get("BINANCE_API_KEY")
    api_secret = env.get("BINANCE_API_SECRET")
    if not api_key or not api_secret:
        raise RuntimeError("BINANCE_API_KEY and BINANCE_API_SECRET are required for LIVE mode")
    executor = BinanceFuturesExecutor(
        api_key,
        api_secret,
        alert_cb=_alert,
        api_error_cb=_on_binance_api_error,
    )
else:
    executor = None

app = FastAPI()
EXECUTION_MODE_INFO.labels(config.execution_mode).set(1)
APP_UPTIME_SECONDS.set_function(lambda: time.time() - APP_START_TS)


async def _notify(message: str):
    await notifier.send(message)


def _log_event(event: str, **fields):
    payload = {"event": event, "ts": datetime.utcnow().isoformat(), **fields}
    app_logger.info(json.dumps(payload, ensure_ascii=False))


def _track_order_result(
    status: str,
    symbol: str,
    action: str,
    side: str,
    reason: Optional[str] = None,
):
    ORDER_RESULT_TOTAL.labels(status, symbol, action, side).inc()
    if status == "skip" and reason:
        ORDER_SKIP_TOTAL.labels(symbol, reason).inc()


def _track_webhook_result(status: str, symbol: str, action: Optional[str]):
    action_label = action or "UNKNOWN"
    WEBHOOK_RESULT_TOTAL.labels(status, symbol.upper(), action_label).inc()


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


def _resolve_action_side(signal: WebhookSignal) -> tuple[str, str]:
    if signal.action and signal.side:
        return signal.action, signal.side
    if not signal.order_action or signal.position_size is None:
        raise ValueError("action/side missing and order_action/position_size not provided")
    order_action = signal.order_action.upper()
    if order_action not in ("BUY", "SELL"):
        raise ValueError(f"invalid order_action: {signal.order_action}")
    pos_size = float(signal.position_size)
    if abs(pos_size) < 1e-12:
        action = "CLOSE"
        side = "SHORT" if order_action == "BUY" else "LONG"
    else:
        action = "OPEN"
        side = "LONG" if pos_size > 0 else "SHORT"
    return action, side


def _is_timeframe_allowed(symbol: str, timeframe: str) -> bool:
    symbol_upper = symbol.upper()
    timeframe_lower = timeframe.lower()
    required = config.allowed_timeframes_by_symbol.get(symbol_upper)
    if required:
        return timeframe_lower == required
    return timeframe_lower in config.allowed_timeframes


async def _handle_open(signal: WebhookSignal):
    symbol = signal.symbol.upper()
    mode = config.order_sizing_mode
    sizing_meta: dict[str, float | str] = {"mode": mode, "symbol": symbol}

    if mode == "EQUITY_PCT":
        if executor is None:
            _track_order_result("skip", symbol, "OPEN", signal.side, "equity_mode_requires_live_executor")
            return {"status": "skip", "reason": "equity_mode_requires_live_executor"}
        equity = await executor.get_total_balance()
        pct = config.order_equity_pct.get(symbol, 0.0)
        order_usdt = equity * pct
        sizing_meta.update({"equity": equity, "pct": pct, "order_usdt": order_usdt})
    elif mode == "EFFECTIVE_LEVERAGE":
        if executor is None:
            _track_order_result(
                "skip",
                symbol,
                "OPEN",
                signal.side,
                "effective_leverage_requires_live_executor",
            )
            return {"status": "skip", "reason": "effective_leverage_requires_live_executor"}
        equity = await executor.get_total_balance()
        operating_capital = equity * config.operating_capital_ratio
        weight = config.symbol_weights.get(symbol, 0.0)
        target_notional = operating_capital * config.total_target_leverage * weight
        order_usdt = target_notional
        sizing_meta.update(
            {
                "equity": equity,
                "operating_capital": operating_capital,
                "operating_ratio": config.operating_capital_ratio,
                "target_total_leverage": config.total_target_leverage,
                "symbol_weight": weight,
                "order_usdt": order_usdt,
                "applied_leverage": float(config.preset_symbol_leverage),
            }
        )
    else:
        order_usdt = config.order_usdt.get(symbol, 0.0)
        sizing_meta.update({"order_usdt": order_usdt})

    _log_event("order_sizing", **sizing_meta)
    if order_usdt <= 0:
        await _notify(f"[SKIP] {symbol} reason=order_sizing_missing")
        _track_order_result("skip", symbol, "OPEN", signal.side, "order_sizing_missing")
        return {"status": "skip", "reason": "order_sizing_missing"}

    price = signal.price or await _get_mark_price(symbol)
    if price <= 0:
        _log_event("order_skip", symbol=symbol, reason="invalid_price", price=price)
        _track_order_result("skip", symbol, "OPEN", signal.side, "invalid_price")
        return {"status": "skip", "reason": "invalid_price"}

    filters = await filter_store.get(symbol)
    qty, _, err = normalize_qty_price(order_usdt / price, price, filters)
    if err:
        _log_event("order_skip", symbol=symbol, reason=err, qty=qty, price=price)
        extra = ""
        if "equity" in sizing_meta:
            extra = (
                f"\nwallet={float(sizing_meta['equity']):.2f}"
                f"\ntarget_lev={float(sizing_meta.get('target_total_leverage', 0.0)):.2f}"
                f"\ntarget_notional={order_usdt:.2f}"
            )
        await _notify(f"[SKIP] {symbol} reason={err} qty={qty:.6f}{extra}")
        _track_order_result("skip", symbol, "OPEN", signal.side, err)
        return {"status": "skip", "reason": err}

    notional = qty * price
    if config.execution_mode == "DRY_RUN":
        _log_event("dryrun_calc", symbol=symbol, qty=qty, price=price, notional=notional)
        _track_order_result("dry_run", symbol, "OPEN", signal.side)
        return {"status": "dry_run", "qty": qty, "price": price, "notional": notional}

    if executor is None:
        _track_order_result("skip", symbol, "OPEN", signal.side, "live_executor_missing")
        return {"status": "skip", "reason": "live_executor_missing"}

    if mode == "EFFECTIVE_LEVERAGE":
        await executor.set_leverage(symbol, config.preset_symbol_leverage)

    await executor.ensure_oneway_mode()
    position = await executor.get_position(symbol)
    _log_event("position_state", symbol=symbol, side=position["side"], qty=position["amt"])
    if position["side"] == signal.side:
        _track_order_result("skip", symbol, "OPEN", signal.side, "already_in_position")
        return {"status": "skip", "reason": "already_in_position"}
    if position["side"] in ("LONG", "SHORT") and position["side"] != signal.side:
        if config.close_before_reverse:
            close_side = "SELL" if position["side"] == "LONG" else "BUY"
            _log_event("order_submit", symbol=symbol, action="CLOSE_BEFORE_REVERSE", side=close_side)
            await executor.place_market_order(symbol, close_side, position["amt"], reduce_only=True)
            await executor.wait(0.2)
        else:
            _track_order_result("skip", symbol, "OPEN", signal.side, "opposite_position_exists")
            return {"status": "skip", "reason": "opposite_position_exists"}

    margin_check_leverage = (
        float(config.preset_symbol_leverage)
        if mode == "EFFECTIVE_LEVERAGE"
        else float(config.leverage)
    )
    has_balance = await executor.has_balance_for(
        notional=notional,
        leverage=margin_check_leverage,
        buffer=config.margin_buffer,
        reserve=config.reserve,
    )
    if not has_balance:
        _log_event(
            "balance_state",
            symbol=symbol,
            notional=notional,
            reserve=config.reserve,
            leverage=margin_check_leverage,
            wallet=sizing_meta.get("equity"),
        )
        await _notify(
            f"[BALANCE_SKIP] {symbol} notional={notional:.2f} reserve={config.reserve:.2f} "
            f"lev={margin_check_leverage:.2f}"
        )
        _track_order_result("skip", symbol, "OPEN", signal.side, "insufficient_balance")
        return {"status": "skip", "reason": "insufficient_balance"}

    side = "BUY" if signal.side == "LONG" else "SELL"
    _log_event("order_submit", symbol=symbol, action="OPEN", side=side, qty=qty)
    order_resp = await executor.place_market_order(symbol, side, qty, reduce_only=False)
    _log_event("stop_skipped", symbol=symbol, reason="stop_disabled")

    notify_lines = [f"[OPEN] {signal.side} {symbol}", f"qty={qty:.6f}", f"price={price:.2f}"]
    if "equity" in sizing_meta:
        notify_lines.append(f"wallet={float(sizing_meta['equity']):.2f}")
    if "target_total_leverage" in sizing_meta:
        notify_lines.append(f"target_lev={float(sizing_meta['target_total_leverage']):.2f}")
    if "order_usdt" in sizing_meta:
        notify_lines.append(f"target_notional={float(sizing_meta['order_usdt']):.2f}")
    if "applied_leverage" in sizing_meta:
        notify_lines.append(f"applied_lev={float(sizing_meta['applied_leverage']):.2f}")
    await _notify("\n".join(notify_lines))

    _log_event(
        "order_ok",
        symbol=symbol,
        action="OPEN",
        qty=qty,
        price=price,
        wallet=sizing_meta.get("equity"),
        target_notional=sizing_meta.get("order_usdt"),
        target_lev=sizing_meta.get("target_total_leverage"),
        applied_lev=sizing_meta.get("applied_leverage"),
    )
    _track_order_result("ok", symbol, "OPEN", signal.side)
    return {"status": "ok", "order": order_resp, "qty": qty, "price": price}


async def _handle_close(signal: WebhookSignal):
    symbol = signal.symbol.upper()
    if config.execution_mode == "DRY_RUN":
        _log_event("dryrun_calc", symbol=symbol, action="CLOSE")
        _track_order_result("dry_run", symbol, "CLOSE", signal.side)
        return {"status": "dry_run", "reason": "close"}
    if executor is None:
        _track_order_result("skip", symbol, "CLOSE", signal.side, "live_executor_missing")
        return {"status": "skip", "reason": "live_executor_missing"}

    position = await executor.get_position(symbol)
    _log_event("position_state", symbol=symbol, side=position["side"], qty=position["amt"])
    if position["side"] == "FLAT":
        _track_order_result("skip", symbol, "CLOSE", signal.side, "no_position")
        return {"status": "skip", "reason": "no_position"}
    if position["side"] != signal.side:
        _track_order_result("skip", symbol, "CLOSE", signal.side, "position_side_mismatch")
        return {"status": "skip", "reason": "position_side_mismatch"}

    side = "SELL" if signal.side == "LONG" else "BUY"
    _log_event("order_submit", symbol=symbol, action="CLOSE", side=side, qty=position["amt"])
    resp = await executor.place_market_order(symbol, side, position["amt"], reduce_only=True)
    await _notify(f"[CLOSE] {signal.side} {symbol}\nqty={position['amt']:.6f}")
    _log_event("order_ok", symbol=symbol, action="CLOSE", qty=position["amt"])
    _track_order_result("ok", symbol, "CLOSE", signal.side)
    return {"status": "ok", "order": resp, "qty": position["amt"]}


@app.get("/health")
async def health():
    return {"status": "ok", "mode": config.execution_mode}


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/tv/webhook")
async def tv_webhook(signal: WebhookSignal):
    started = time.perf_counter()

    def _final(status: str, action: Optional[str] = None):
        _track_webhook_result(status, signal.symbol, action or signal.action)
        WEBHOOK_PROCESS_SECONDS.observe(time.perf_counter() - started)
        return {"status": status}

    WEBHOOK_RECEIVED_TOTAL.labels(signal.symbol.upper()).inc()
    payload = signal.dict()
    inserted = db.insert_signal(signal.signal_id, payload, "received")
    _log_event(
        "webhook_received",
        signal_id=signal.signal_id,
        symbol=signal.symbol,
        action=signal.action,
    )
    if not inserted:
        db.update_signal_status(signal.signal_id, "dedup_hit")
        _log_event("dedup_hit", signal_id=signal.signal_id)
        return _final("duplicate")

    if signal.secret != config.secret:
        _reject(signal, "rejected_secret")
        _log_event("rejected", reason="secret", signal_id=signal.signal_id)
        return _final("rejected_secret")
    if signal.symbol.upper() not in config.allowed_symbols:
        _reject(signal, "rejected_symbol")
        _log_event("rejected", reason="symbol", signal_id=signal.signal_id)
        return _final("rejected_symbol")
    if not _is_timeframe_allowed(signal.symbol, signal.timeframe):
        _reject(signal, "rejected_timeframe")
        _log_event("rejected", reason="timeframe", signal_id=signal.signal_id)
        return _final("rejected_timeframe")

    if config.execution_mode == "RECEIVE_ONLY":
        db.update_signal_status(signal.signal_id, "received_only")
        try:
            action, side = _resolve_action_side(signal)
        except Exception:
            action, side = signal.action, signal.side
        await _notify(f"[WEBHOOK] received {signal.symbol} {action} {side}")
        _log_event("validated", mode="RECEIVE_ONLY", signal_id=signal.signal_id)
        return _final("received_only", action)

    try:
        action, side = _resolve_action_side(signal)
    except Exception as exc:
        _reject(signal, f"rejected_action_side: {exc}")
        _log_event("rejected", reason="action_side", signal_id=signal.signal_id)
        return _final("rejected_action_side")

    signal = signal.copy(update={"action": action, "side": side})
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
        return _final(status, signal.action)
    except Exception as exc:
        err_msg = str(exc)
        _log_event("order_fail", signal_id=signal.signal_id, error=err_msg)
        _track_order_result(
            "error",
            signal.symbol.upper(),
            signal.action or "UNKNOWN",
            signal.side or "UNKNOWN",
        )
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
        await _notify(f"[WEBHOOK_ERROR] {err_msg}")
        return _final("error", signal.action)
