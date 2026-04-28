"""
main.py — FastAPI 백엔드 진입점
"""

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext

from core.schemas import ChatRequest, ChatResponse, LoginRequest, LoginResponse

SECRET_KEY  = os.environ.get("JWT_SECRET_KEY", "change-me-in-production")
ALGORITHM   = "HS256"
TOKEN_EXPIRE_MINUTES = int(os.environ.get("TOKEN_EXPIRE_MINUTES", "1440"))

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin1234")

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
_bearer  = HTTPBearer()

app = FastAPI(title="Single Agent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── JWT 헬퍼 ─────────────────────────────────────────────────────────────────

def _create_token(username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": username, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def _verify_token(credentials: HTTPAuthorizationCredentials = Depends(_bearer)) -> str:
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if not username:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return username
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


# ── 라우터 ───────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.post("/auth/login", response_model=LoginResponse)
def login(req: LoginRequest):
    if req.username != ADMIN_USERNAME or req.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return LoginResponse(access_token=_create_token(req.username))


@app.get("/auth/verify")
def verify_token(username: str = Depends(_verify_token)):
    return {"valid": True, "username": username}


@app.get("/calendar/month")
def get_calendar_month(year: int, month: int, username: str = Depends(_verify_token)):
    from tools.calendar_tools import get_month_calendar_events
    return get_month_calendar_events(year, month)


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, username: str = Depends(_verify_token)):
    from agent import run_agent

    ctx = dict(req.context)
    if "session_id" not in ctx:
        ctx["session_id"] = str(uuid.uuid4())

    try:
        return run_agent(req.message, req.history, ctx)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
