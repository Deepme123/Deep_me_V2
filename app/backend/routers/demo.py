from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

router = APIRouter(tags=["demo"])

RESOURCE_DIR = Path(__file__).resolve().parents[1] / "resources"
DEMO_PAGE_PATH = RESOURCE_DIR / "emotion_analysis_demo.html"
DEMO_CSS_PATH = RESOURCE_DIR / "emotion_analysis_demo.css"
DEMO_JS_PATH = RESOURCE_DIR / "emotion_analysis_demo.js"


def _ensure_demo_asset(path: Path) -> Path:
    if not path.exists():
        raise HTTPException(status_code=500, detail="demo_page_missing")
    return path


@router.get("/demo/emotion-analysis", response_class=HTMLResponse)
def emotion_analysis_demo() -> HTMLResponse:
    page_path = _ensure_demo_asset(DEMO_PAGE_PATH)
    return HTMLResponse(page_path.read_text(encoding="utf-8"))


@router.get("/demo/assets/emotion-analysis-demo.css")
def emotion_analysis_demo_css() -> FileResponse:
    return FileResponse(_ensure_demo_asset(DEMO_CSS_PATH), media_type="text/css; charset=utf-8")


@router.get("/demo/assets/emotion-analysis-demo.js")
def emotion_analysis_demo_js() -> FileResponse:
    return FileResponse(
        _ensure_demo_asset(DEMO_JS_PATH),
        media_type="application/javascript; charset=utf-8",
    )
