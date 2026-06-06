# app/main.py
import os
import logging
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded

from app.backend.core.logging_config import setup_logging
from app.db.session import get_engine, CORE_REQUIRED_TABLES
from app.db.health import check_db_tables, health_db_response
from app.backend.core.rate_limit import limiter as rate_limiter, RATELIMIT_ENABLED

# 모델 모듈 임포트(테이블 등록 보장용)
from app.backend.models import emotion as _m_emotion  # noqa: F401
from app.backend.models import task as _m_task  # noqa: F401
from app.backend.models import refresh_token as _m_refresh  # noqa: F401

# 라우터
from app.backend.routers import emotion, auth, user, task, demo
from app.backend.routers.emotion_ws import ws_router as emotion_ws_router
from app.backend.routers import health_llm 
from app.backend.routers import deploy_webhook

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="DEEPME Backend",
    version=os.getenv("APP_VERSION", "0.1.0"),
)

# Rate Limiting
app.state.limiter = rate_limiter
if RATELIMIT_ENABLED:
    app.add_exception_handler(RateLimitExceeded, lambda request, exc: HTTPException(status_code=429, detail="rate_limit_exceeded"))

# CORS
_default_origins = "https://deep-me-v1.onrender.com,http://localhost:3000,http://localhost:5173"
origins = [
    o.strip()
    for o in os.getenv("CORS_ALLOW_ORIGINS", _default_origins).split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 라우터 등록
app.include_router(health_llm.router)
app.include_router(emotion.router)
app.include_router(emotion_ws_router)
app.include_router(auth.auth_router)
app.include_router(user.user_router)
app.include_router(task.router)
app.include_router(demo.router)
app.include_router(deploy_webhook.router)


@app.middleware("http")
async def add_charset_for_json(request: Request, call_next) -> Response:
    resp = await call_next(request)
    ct = resp.headers.get("content-type", "")
    if ct.startswith("application/json") and "charset" not in ct.lower():
        resp.headers["content-type"] = "application/json; charset=utf-8"
    return resp


@app.on_event("startup")
def validate_required_tables() -> None:
    check_db_tables(get_engine(), CORE_REQUIRED_TABLES, "core")



@app.get("/health")
def health_app():
    return {"ok": True}


@app.get("/health/db")
def health_db():
    return health_db_response(get_engine(), CORE_REQUIRED_TABLES, "core")
