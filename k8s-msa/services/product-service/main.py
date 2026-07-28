import json
import os
import time

import redis
from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator

SERVICE = "product-service"
REDIS_HOST = os.getenv("REDIS_HOST", "redis")   # -> K8s ConfigMap
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
CACHE_TTL = int(os.getenv("CACHE_TTL", "60"))
START = time.time()

app = FastAPI(title=SERVICE)
Instrumentator().instrument(app).expose(app)

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True,
                socket_connect_timeout=2, socket_timeout=2)

CATALOG = {
    "p1": {"id": "p1", "name": "Mechanical Keyboard", "price": 129000, "stock": 12},
    "p2": {"id": "p2", "name": "Noise Cancelling Headset", "price": 249000, "stock": 5},
    "p3": {"id": "p3", "name": "27in 4K Monitor", "price": 459000, "stock": 3},
}


@app.get("/healthz")
def healthz():
    # liveness: 프로세스 살아있나만 본다. Redis 죽어도 재시작하면 안 됨.
    return {"service": SERVICE, "status": "ok", "uptime_s": round(time.time() - START, 1)}


@app.get("/readyz")
def readyz():
    # readiness: 의존성(Redis) 죽으면 트래픽 빼라. 재시작은 아님.
    try:
        r.ping()
    except Exception:
        raise HTTPException(503, "redis unavailable")
    return {"service": SERVICE, "ready": True, "redis": "up"}


@app.get("/products")
def list_products():
    return {"items": list(CATALOG.values())}


@app.get("/products/{pid}")
def get_product(pid: str):
    key = f"product:{pid}"
    try:
        cached = r.get(key)
        if cached:
            return {**json.loads(cached), "cache": "HIT"}
    except Exception:
        pass  # 캐시 장애가 서비스 장애가 되면 안 된다

    p = CATALOG.get(pid)
    if not p:
        raise HTTPException(404, "product not found")
    try:
        r.setex(key, CACHE_TTL, json.dumps(p))
    except Exception:
        pass
    return {**p, "cache": "MISS"}
