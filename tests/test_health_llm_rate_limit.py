from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET_KEY", "test-rate-limit-secret")
os.environ.setdefault("JWT_REFRESH_SECRET", "test-rate-limit-refresh-secret")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_rate_limit.db")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="function")
def client_with_rate_limit(monkeypatch):
    """Rate Limiting이 활성화된 상태에서 app 생성"""
    monkeypatch.setenv("RATELIMIT_ENABLED", "true")

    import importlib
    import app.backend.core.rate_limit
    import app.backend.routers.health_llm
    import app.backend.main

    importlib.reload(app.backend.core.rate_limit)
    importlib.reload(app.backend.routers.health_llm)
    importlib.reload(app.backend.main)

    # LLM 호출 없이 테스트할 수 있도록 health_llm 모듈의 LLM 함수 교체
    import app.backend.routers.health_llm as hlm

    def _fake_generate(**kwargs):
        return "pong"

    def _fake_stream(**kwargs):
        yield "pong"

    monkeypatch.setattr(hlm, "generate_noa_response", _fake_generate)
    monkeypatch.setattr(hlm, "stream_noa_response", _fake_stream)

    from app.backend.main import app
    return TestClient(app)


def test_health_llm_ok(client_with_rate_limit):
    """정상 호출 - 200"""
    response = client_with_rate_limit.get("/health/llm")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_health_llm_with_query(client_with_rate_limit):
    """q 파라미터 포함 호출"""
    response = client_with_rate_limit.get("/health/llm?q=pong")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_health_llm_query_too_long(client_with_rate_limit):
    """q 파라미터 길이 초과 (max_length=500) - 422"""
    long_query = "a" * 501
    response = client_with_rate_limit.get(f"/health/llm?q={long_query}")
    assert response.status_code == 422


def test_health_llm_rate_limit_exceeded(client_with_rate_limit):
    """5회 초과 호출 - 429 Too Many Requests"""
    for i in range(5):
        response = client_with_rate_limit.get("/health/llm")
        assert response.status_code == 200, f"Request {i+1} should succeed"

    response = client_with_rate_limit.get("/health/llm")
    assert response.status_code == 429
    assert "rate_limit_exceeded" in response.json()["detail"]


def test_health_llm_stream_ok(client_with_rate_limit):
    """스트림 엔드포인트 정상 호출"""
    response = client_with_rate_limit.get("/health/llm/stream")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_health_llm_stream_rate_limit_exceeded(client_with_rate_limit):
    """스트림 엔드포인트 Rate Limit 초과"""
    for i in range(5):
        response = client_with_rate_limit.get("/health/llm/stream")
        assert response.status_code == 200

    response = client_with_rate_limit.get("/health/llm/stream")
    assert response.status_code == 429
