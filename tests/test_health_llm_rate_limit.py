from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from slowapi.errors import RateLimitExceeded

os.environ.setdefault("JWT_SECRET_KEY", "test-rate-limit-secret")
os.environ.setdefault("JWT_REFRESH_SECRET", "test-rate-limit-refresh-secret")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_rate_limit.db")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="function")
def client_with_rate_limit(monkeypatch):
    """Rate Limiting이 활성화된 상태에서, main.py를 건드리지 않는 독립된 app으로
    health_llm 라우터만 검증한다.

    app.backend.main을 통째로 reload하면 이미 임포트된 다른 라우터 모듈들과
    router 객체가 꼬여 다른 테스트 파일에 부작용을 일으키므로(참고:
    test_deletion_feedback_rate_limit.py) main.py는 건드리지 않는다.

    rate_limit/health_llm 모듈 reload는 sys.modules에 캐싱된 같은 모듈 객체를
    다시 실행하는 방식이라, 테스트가 끝난 뒤 RATELIMIT_ENABLED=false로 되돌려
    다시 reload해두지 않으면 진짜(slowapi) 리미터가 프로세스가 끝날 때까지
    health_llm 모듈에 남아있게 된다. 그러면 health_llm 함수를 TestClient 없이
    직접 호출하는 다른 테스트 파일(test_health_llm_router.py 등)이 request=None
    때문에 깨진다 — 실제로 이 teardown이 빠져 있던 버전에서 재현 및 확인됨.
    """
    monkeypatch.setenv("RATELIMIT_ENABLED", "true")

    import app.backend.core.rate_limit as rate_limit_module
    import app.backend.routers.health_llm as health_llm_module

    importlib.reload(rate_limit_module)
    importlib.reload(health_llm_module)

    def _fake_generate(**kwargs):
        return "pong"

    def _fake_stream(**kwargs):
        yield "pong"

    monkeypatch.setattr(health_llm_module, "generate_noa_response", _fake_generate)
    monkeypatch.setattr(health_llm_module, "stream_noa_response", _fake_stream)

    app = FastAPI()
    app.state.limiter = rate_limit_module.limiter
    app.add_exception_handler(
        RateLimitExceeded,
        lambda request, exc: JSONResponse({"detail": "rate_limit_exceeded"}, status_code=429),
    )
    app.include_router(health_llm_module.router)

    yield TestClient(app)

    os.environ["RATELIMIT_ENABLED"] = "false"
    importlib.reload(rate_limit_module)
    importlib.reload(health_llm_module)


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
