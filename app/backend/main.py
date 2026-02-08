# app/main.py
import os
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlmodel import text

from app.backend.core.logging_config import setup_logging
from app.backend.db.session import engine

# 모델 모듈 임포트(테이블 등록 보장용)
from app.backend.models import emotion as _m_emotion  # noqa: F401
from app.backend.models import task as _m_task  # noqa: F401
from app.backend.models import refresh_token as _m_refresh  # noqa: F401

# 라우터
from app.backend.routers import emotion, auth, user, task, prompts
from app.backend.routers.emotion_ws import ws_router as emotion_ws_router
from app.backend.routers import health_llm

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="DEEPME Backend",
    version=os.getenv("APP_VERSION", "0.1.0"),
)

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


@app.middleware("http")
async def prompts_cors_middleware(request: Request, call_next):
    if not request.url.path.startswith("/prompts"):
        return await call_next(request)
    if request.method == "OPTIONS":
        response = Response(status_code=204)
    else:
        response = await call_next(request)
    origin = request.headers.get("origin")
    response.headers["Access-Control-Allow-Origin"] = origin or "*"
    response.headers["Vary"] = "Origin"
    response.headers["Access-Control-Allow-Methods"] = "GET,PUT,OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = request.headers.get(
        "access-control-request-headers", "*"
    )
    response.headers["Access-Control-Max-Age"] = "600"
    return response

# 라우터 등록
app.include_router(health_llm.router)
app.include_router(emotion.router)
app.include_router(emotion_ws_router)
app.include_router(auth.auth_router)
app.include_router(user.user_router)
app.include_router(task.router)
app.include_router(prompts.router)

@app.get("/health")
def health_app():
    return {"ok": True}


@app.get("/health/db")
def health_db():
    # Migration is a deployment concern. Runtime only verifies DB connectivity.
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"ok": True}
    except Exception:
        raise HTTPException(status_code=500, detail="Database connection failed")
