import os
import random
import time
import uuid

from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel

SERVICE = "payment-service"
FAILURE_RATE = float(os.getenv("FAILURE_RATE", "0.1"))  # 외부 PG 장애 시뮬레이션
LATENCY_MS = int(os.getenv("LATENCY_MS", "120"))
START = time.time()

app = FastAPI(title=SERVICE)
Instrumentator().instrument(app).expose(app)


class PayReq(BaseModel):
    order_id: str
    amount: int


@app.get("/healthz")
def healthz():
    return {"service": SERVICE, "status": "ok", "uptime_s": round(time.time() - START, 1)}


@app.get("/readyz")
def readyz():
    return {"service": SERVICE, "ready": True}


@app.post("/payments")
def pay(body: PayReq):
    time.sleep(LATENCY_MS / 1000)
    if random.random() < FAILURE_RATE:
        raise HTTPException(502, "payment gateway timeout")
    return {
        "payment_id": str(uuid.uuid4()),
        "order_id": body.order_id,
        "amount": body.amount,
        "status": "APPROVED",
    }


@app.get("/burn")
def burn(ms: int = 500):
    # HPA 데모용 CPU 부하 생성기. Week 3에서 이걸로 Pod 자동 증식 찍는다.
    end = time.time() + ms / 1000
    n = 0
    while time.time() < end:
        n += 1
    return {"iterations": n, "ms": ms}
