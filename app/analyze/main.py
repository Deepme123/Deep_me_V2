# app/main.py
import logging

from fastapi import FastAPI, Depends, HTTPException, Request
from sqlmodel import Session, text

from app.analyze.db import get_db
from app.analyze.routers import cards as cards_router
from app.analyze.routers import summaries as summaries_router
from app.db.session import ANALYZE_REQUIRED_TABLES, ensure_required_tables

logger = logging.getLogger(__name__)

app = FastAPI(title="DeepMe Analyze Card API")
app.include_router(cards_router.router)
app.include_router(summaries_router.router)


@app.on_event("startup")
def validate_required_tables() -> None:
    ensure_required_tables(ANALYZE_REQUIRED_TABLES, schema="public")
    logger.info("Required analyze tables verified")

@app.middleware("http")
async def add_charset_for_json(request: Request, call_next):
    resp = await call_next(request)
    ct = resp.headers.get("content-type", "")
    if ct.startswith("application/json") and "charset" not in ct.lower():
        resp.headers["content-type"] = "application/json; charset=utf-8"
    return resp

@app.get("/health/db")
def health_db(db: Session = Depends(get_db)):
    try:
        db.exec(text("SELECT 1"))
        ensure_required_tables(ANALYZE_REQUIRED_TABLES, schema="public")
        return {"ok": True}
    except RuntimeError as exc:
        logger.exception("Required analyze table check failed")
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/")
def root():
    return {"service": "DeepMe Analyze Card API"}
