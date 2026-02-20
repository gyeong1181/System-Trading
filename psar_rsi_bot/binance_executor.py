from __future__ import annotations

import asyncio
import hashlib
import hmac
import time
import urllib.parse
from typing import Any, Dict, Optional

import httpx

from risk_manager import compute_required_margin, normalize_qty_price
from utils import get_logger, get_app_logger


class BinanceFuturesExecutor:
    BASE_URL = "https://fapi.binance.com"
    PAPI_URL = "https://papi.binance.com"

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        alert_cb=None,
        api_error_cb=None,
    ):
        self.api_key = api_key
        self.api_secret = api_secret.encode()
        self.logger = get_logger("BinanceExecutor")
        self.app_logger = get_app_logger()
        self.alert_cb = alert_cb
        self.api_error_cb = api_error_cb
        self._session = httpx.AsyncClient(base_url=self.BASE_URL, timeout=15)

    async def close(self):
        await self._session.aclose()

    async def _signed_request(self, method: str, path: str, params: Dict[str, Any]):
        return await self._signed_request_to(self.BASE_URL, method, path, params)

    async def _signed_request_to(self, base_url: str, method: str, path: str, params: Dict[str, Any]):
        params = {k: str(v) for k, v in params.items()}
        params["timestamp"] = str(int(time.time() * 1000))
        query = urllib.parse.urlencode(params, doseq=True)
        signature = hmac.new(self.api_secret, query.encode(), hashlib.sha256).hexdigest()
        url = f"{base_url}{path}?{query}&signature={signature}"
        headers = {"X-MBX-APIKEY": self.api_key}
        response = await self._session.request(method, url, headers=headers)
        if response.status_code >= 400:
            msg = f"Binance error {response.status_code}: {response.text}"
            self.logger.error(msg)
            self.app_logger.error(msg)
            if self.api_error_cb:
                try:
                    self.api_error_cb(path=path, status_code=response.status_code)
                except Exception:
                    pass
            if self.alert_cb:
                self.alert_cb(
                    f"[API ERROR] status={response.status_code}\nendpoint={path}\ndetail={response.text}"
                )
            response.raise_for_status()
        return response.json()

    async def get_available_balance(self) -> float:
        data = await self._signed_request("GET", "/fapi/v2/balance", {})
        usdt = next((item for item in data if item.get("asset") == "USDT"), None)
        if usdt:
            return float(usdt.get("availableBalance", usdt.get("balance", 0.0)))
        return 0.0

    async def get_total_balance(self) -> float:
        data = await self._signed_request("GET", "/fapi/v2/balance", {})
        usdt = next((item for item in data if item.get("asset") == "USDT"), None)
        if usdt:
            return float(usdt.get("balance", 0.0))
        return 0.0

    async def get_mark_price(self, symbol: str) -> float:
        params = {"symbol": symbol.upper()}
        resp = await self._session.get("/fapi/v1/premiumIndex", params=params)
        resp.raise_for_status()
        data = resp.json()
        return float(data.get("markPrice", data.get("indexPrice", 0.0)))

    async def get_last_price(self, symbol: str) -> float:
        params = {"symbol": symbol.upper()}
        resp = await self._session.get("/fapi/v1/ticker/price", params=params)
        resp.raise_for_status()
        data = resp.json()
        return float(data["price"])

    async def get_position(self, symbol: str) -> Dict[str, Any]:
        data = await self._signed_request("GET", "/fapi/v2/positionRisk", {"symbol": symbol.upper()})
        if isinstance(data, list) and data:
            data = data[0]
        pos_amt = float(data.get("positionAmt", 0.0))
        entry_price = float(data.get("entryPrice", 0.0))
        if pos_amt > 0:
            side = "LONG"
        elif pos_amt < 0:
            side = "SHORT"
        else:
            side = "FLAT"
        return {"side": side, "amt": abs(pos_amt), "entry_price": entry_price}

    async def place_market_order(self, symbol: str, side: str, qty: float, reduce_only: bool):
        params = {
            "symbol": symbol.upper(),
            "side": side,
            "type": "MARKET",
            "quantity": f"{qty:.6f}",
            "reduceOnly": "true" if reduce_only else "false",
        }
        return await self._signed_request("POST", "/fapi/v1/order", params)

    async def set_leverage(self, symbol: str, leverage: int):
        params = {
            "symbol": symbol.upper(),
            "leverage": int(leverage),
        }
        return await self._signed_request("POST", "/fapi/v1/leverage", params)

    async def place_stop_market(
        self,
        symbol: str,
        side: str,
        qty: float,
        stop_price: float,
        reduce_only: bool = True,
    ):
        params = {
            "symbol": symbol.upper(),
            "side": side,
            "type": "STOP_MARKET",
            "stopPrice": f"{stop_price:.6f}",
            "quantity": f"{qty:.6f}",
            "reduceOnly": "true" if reduce_only else "false",
            "workingType": "MARK_PRICE",
        }
        try:
            return await self._signed_request("POST", "/fapi/v1/order", params)
        except httpx.HTTPStatusError as exc:
            text = exc.response.text if exc.response else str(exc)
            # Some accounts require conditional (algo) endpoint for stop orders.
            if "Order type not supported" in text or "\"code\":-4120" in text:
                self.logger.warning(
                    "STOP_MARKET not supported on /fapi/v1/order, retrying conditional endpoint"
                )
                self.app_logger.warning(
                    "STOP_MARKET not supported on /fapi/v1/order, retrying conditional endpoint: %s",
                    text,
                )
                return await self._signed_request_to(
                    self.PAPI_URL, "POST", "/papi/v1/um/conditional/order", params
                )
            raise

    async def ensure_oneway_mode(self):
        try:
            data = await self._signed_request("GET", "/fapi/v1/positionSide/dual", {})
            if data.get("dualSidePosition") is True:
                self.logger.warning("Account is in hedge mode. Oneway mode is recommended.")
        except Exception as exc:  # pragma: no cover - non-critical
            self.logger.debug("Position mode check failed: %s", exc)

    async def compute_qty(
        self,
        symbol: str,
        order_usdt: float,
        price: float,
        filters,
    ) -> tuple[float, Optional[str]]:
        raw_qty = order_usdt / price if price > 0 else 0.0
        qty, norm_price, err = normalize_qty_price(raw_qty, price, filters)
        if err:
            return 0.0, err
        return qty, None

    async def has_balance_for(self, notional: float, leverage: float, buffer: float, reserve: float) -> bool:
        available = await self.get_available_balance()
        required = compute_required_margin(notional, leverage, buffer)
        return available >= (required + reserve)

    async def wait(self, sec: float = 0.1):
        await asyncio.sleep(sec)
