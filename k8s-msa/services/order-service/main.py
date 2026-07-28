import os
import time
import uuid

import httpx
from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel

SERVICE = "order-service"
# K8s에서는 이 URL이 그대로 Service 이름으로 해석된다 (내장 DNS = Service Discovery)
USER_URL = os.getenv("USER_SERVICE_URL", "http://user-service:8000")
PRODUCT_URL = os.getenv("PRODUCT_SERVICE_URL", "http://product-service:8000")
PAYMENT_URL = os.getenv("PAYMENT_SERVICE_URL", "http://payment-service:8000")
NOTIFY_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://notification-service:8000")
START = time.time()

app = FastAPI(title=SERVICE)
Instrumentator().instrument(app).expose(app)

ORDERS: dict = {}


class OrderReq(BaseModel):
    email: str
    product_id: str
    qty: int = 1


@app.get("/healthz")
def healthz():
    return {"service": SERVICE, "status": "ok", "uptime_s": round(time.time() - START, 1)}


@app.get("/readyz")
def readyz():
    return {"service": SERVICE, "ready": True}


@app.get("/orders")
def list_orders():
    return {"count": len(ORDERS), "items": list(ORDERS.values())}


@app.get("/orders/{oid}")
def get_order(oid: str):
    o = ORDERS.get(oid)
    if not o:
        raise HTTPException(404, "order not found")
    return o


@app.post("/orders", status_code=201)
async def create_order(body: OrderReq):
    oid = uuid.uuid4().hex[:8]

    async with httpx.AsyncClient(timeout=10.0) as c:
        u = await c.get(f"{USER_URL}/users/{body.email}")
        if u.status_code != 200:
            raise HTTPException(400, f"user lookup failed ({u.status_code})")

        p = await c.get(f"{PRODUCT_URL}/products/{body.product_id}")
        if p.status_code != 200:
            raise HTTPException(400, f"product lookup failed ({p.status_code})")

        amount = p.json()["price"] * body.qty
        order = {
            "order_id": oid,
            "email": body.email,
            "product_id": body.product_id,
            "qty": body.qty,
            "amount": amount,
            "status": "PENDING",
        }
        ORDERS[oid] = order

        pay = await c.post(f"{PAYMENT_URL}/payments",
                           json={"order_id": oid, "amount": amount})
        if pay.status_code != 200:
            order["status"] = "PAYMENT_FAILED"
            raise HTTPException(502, f"payment failed for order {oid}")

        order["status"] = "PAID"
        order["payment_id"] = pay.json()["payment_id"]

        try:
            await c.post(f"{NOTIFY_URL}/notify", json={
                "email": body.email,
                "order_id": oid,
                "message": f"order {oid} paid: {amount} KRW",
            })
        except Exception as e:
            print(f"[WARN] notify failed: {e}", flush=True)  # 알림 실패로 주문을 깨지 않는다

    return order
