import hashlib
import os
import time
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel

SERVICE = "user-service"
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")  # -> K8s Secret
START = time.time()

app = FastAPI(title=SERVICE)
Instrumentator().instrument(app).expose(app)  # -> GET /metrics (Prometheus)

USERS: dict = {}  # 메모리 저장. Pod 재시작하면 날아감 -> Week 2에서 StatefulSet/PVC로 해결


class SignUp(BaseModel):
    email: str
    password: str


def _hash(p: str) -> str:
    return hashlib.sha256(p.encode()).hexdigest()


@app.get("/healthz")
def healthz():
    return {"service": SERVICE, "status": "ok", "uptime_s": round(time.time() - START, 1)}


@app.get("/readyz")
def readyz():
    return {"service": SERVICE, "ready": True}


@app.post("/users", status_code=201)
def signup(body: SignUp):
    if body.email in USERS:
        raise HTTPException(409, "user already exists")
    USERS[body.email] = {"email": body.email, "pw": _hash(body.password)}
    return {"email": body.email}


@app.get("/users/{email}")
def get_user(email: str):
    u = USERS.get(email)
    if not u:
        raise HTTPException(404, "user not found")
    return {"email": u["email"]}


@app.post("/login")
def login(body: SignUp):
    u = USERS.get(body.email)
    if not u or u["pw"] != _hash(body.password):
        raise HTTPException(401, "invalid credentials")
    token = jwt.encode(
        {"sub": body.email, "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        JWT_SECRET,
        algorithm="HS256",
    )
    return {"access_token": token, "token_type": "bearer"}
