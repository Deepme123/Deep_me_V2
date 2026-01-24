# app/main.py
from fastapi import FastAPI, Depends, Request
from sqlmodel import Session, text

from app.analyze.db import get_db
from app.analyze.routers import cards as cards_router
from app.analyze.routers import summaries as summaries_router

app = FastAPI(title="DeepMe Analyze Card API")
app.include_router(cards_router.router)
app.include_router(summaries_router.router)

@app.middleware("http")
async def add_charset_for_json(request: Request, call_next):
    resp = await call_next(request)
    ct = resp.headers.get("content-type", "")
    if ct.startswith("application/json") and "charset" not in ct.lower():
        resp.headers["content-type"] = "application/json; charset=utf-8"
    return resp

@app.get("/health/db")
def health_db(db: Session = Depends(get_db)):
    db.exec(text("SELECT 1"))
    return {"ok": True}

@app.get("/")
def root():
    return {"service": "DeepMe Analyze Card API"}
