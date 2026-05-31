from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _disable_rate_limit_by_default(monkeypatch):
    # 테스트 환경에서는 기본적으로 Rate Limiting 비활성화
    # rate_limit.py를 import하기 전에 설정해야 함
    monkeypatch.setenv("RATELIMIT_ENABLED", "false")


@pytest.fixture
def client():
    from app.backend.main import app
    return TestClient(app)
