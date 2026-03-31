import importlib
import os
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_demo.db")

demo_router = importlib.import_module("app.backend.routers.demo").router


def test_emotion_analysis_demo_page_serves_html():
    app = FastAPI()
    app.include_router(demo_router)
    client = TestClient(app)

    response = client.get("/demo/emotion-analysis")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert '<div class="shell">' in response.text
    assert '/demo/assets/emotion-analysis-demo.css' in response.text
    assert '/demo/assets/emotion-analysis-demo.js' in response.text


def test_emotion_analysis_demo_assets_serve_static_files():
    app = FastAPI()
    app.include_router(demo_router)
    client = TestClient(app)

    css_response = client.get("/demo/assets/emotion-analysis-demo.css")
    js_response = client.get("/demo/assets/emotion-analysis-demo.js")

    assert css_response.status_code == 200
    assert "text/css" in css_response.headers["content-type"]
    assert ".hero-card" in css_response.text

    assert js_response.status_code == 200
    assert "application/javascript" in js_response.headers["content-type"]
    assert "function connect()" in js_response.text
