import time
from collections import deque
from datetime import datetime, timezone

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel

SERVICE = "notification-service"
START = time.time()

app = FastAPI(title=SERVICE)
Instrumentator().instrument(app).expose(app)

NOTES = deque(maxlen=50)


class Note(BaseModel):
    email: str
    order_id: str
    message: str


@app.get("/healthz")
def healthz():
    return {"service": SERVICE, "status": "ok", "uptime_s": round(time.time() - START, 1)}


@app.get("/readyz")
def readyz():
    return {"service": SERVICE, "ready": True}


@app.post("/notify")
def notify(body: Note):
    item = {"ts": datetime.now(timezone.utc).isoformat(), **body.model_dump()}
    NOTES.appendleft(item)
    print(f"[NOTIFY] {item}", flush=True)  # stdout -> kubectl logs / Loki
    return {"delivered": True}


@app.get("/notifications")
def list_notes():
    return {"count": len(NOTES), "items": list(NOTES)}
