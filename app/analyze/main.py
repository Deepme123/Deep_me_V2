# app/main.py
import logging

from fastapi import FastAPI, Request

from app.analyze.routers import cards as cards_router
from app.analyze.routers import summaries as summaries_router
from app.db.session import ANALYZE_REQUIRED_TABLES, get_engine
from app.db.health import check_db_tables, health_db_response
from app.backend.routers import deploy_webhook

logger = logging.getLogger(__name__)

app = FastAPI(title="DeepMe Analyze Card API")
app.include_router(cards_router.router)
app.include_router(summaries_router.router)
app.include_router(deploy_webhook.router)  


@app.on_event("startup")
def validate_required_tables() -> None:
    check_db_tables(get_engine(), ANALYZE_REQUIRED_TABLES, "analyze")

@app.middleware("http")
async def add_charset_for_json(request: Request, call_next):
    resp = await call_next(request)
    ct = resp.headers.get("content-type", "")
    if ct.startswith("application/json") and "charset" not in ct.lower():
        resp.headers["content-type"] = "application/json; charset=utf-8"
    return resp

@app.get("/health/db")
def health_db():
    return health_db_response(get_engine(), ANALYZE_REQUIRED_TABLES, "analyze")

@app.get("/")
def root():
    return {"service": "DeepMe Analyze Card API"}
