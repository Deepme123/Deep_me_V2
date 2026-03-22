from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["demo"])

DEMO_PAGE_PATH = Path(__file__).resolve().parents[1] / "resources" / "emotion_analysis_demo.html"


@router.get("/demo/emotion-analysis", response_class=HTMLResponse)
def emotion_analysis_demo() -> HTMLResponse:
    if not DEMO_PAGE_PATH.exists():
        raise HTTPException(status_code=500, detail="demo_page_missing")
    return HTMLResponse(DEMO_PAGE_PATH.read_text(encoding="utf-8"))
