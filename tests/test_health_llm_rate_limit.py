from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="function")
def client_with_rate_limit(monkeypatch):
    """Rate Limiting이 활성화된 상태에서 app 생성"""
    # app 모듈 import 전에 환경변수 설정
    monkeypatch.setenv("RATELIMIT_ENABLED", "true")

    # app을 새로 import해야 limiter가 활성화됨
    import importlib
    import app.backend.core.rate_limit
    import app.backend.routers.health_llm
    import app.backend.main

    importlib.reload(app.backend.core.rate_limit)
    importlib.reload(app.backend.routers.health_llm)
    importlib.reload(app.backend.main)

    from app.backend.main import app
    return TestClient(app)


def test_health_llm_ok(client_with_rate_limit):
    """정상 호출 - 200"""
    response = client_with_rate_limit.get("/health/llm")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_health_llm_with_query(client_with_rate_limit):
    """q 파라미터 포함 호출"""
    response = client_with_rate_limit.get("/health/llm?q=test")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_health_llm_query_too_long(client_with_rate_limit):
    """q 파라미터 길이 초과 (max_length=500) - 422"""
    long_query = "a" * 501
    response = client_with_rate_limit.get(f"/health/llm?q={long_query}")
    assert response.status_code == 422  # Pydantic validation error


def test_health_llm_rate_limit_exceeded(client_with_rate_limit):
    """5회 초과 호출 - 429 Too Many Requests"""
    # 처음 5회는 성공
    for i in range(5):
        response = client_with_rate_limit.get("/health/llm")
        assert response.status_code == 200, f"Request {i+1} should succeed"

    # 6번째 호출은 Rate Limit 초과
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
