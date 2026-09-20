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
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

os.environ.setdefault("JWT_SECRET_KEY", "test-rate-limit-secret")
os.environ.setdefault("JWT_REFRESH_SECRET", "test-rate-limit-refresh-secret")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://user:pass@localhost/testdb")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def client_with_rate_limit(monkeypatch):
    """Rate Limiting과 관리자 시크릿이 모두 활성화된 상태에서, main.py를 건드리지
    않는 독립된 app으로 deletion_feedback 라우터만 검증한다.

    app.backend.main을 통째로 reload하면 이미 임포트된 다른 라우터 모듈들과
    router 객체가 꼬여 다른 테스트 파일에 부작용을 일으켜서(APIRouter.routes
    누락 등) main.py는 건드리지 않는다.
    """
    monkeypatch.setenv("RATELIMIT_ENABLED", "true")
    monkeypatch.setenv("ADMIN_API_SECRET", "test-admin-secret")

    import app.backend.core.rate_limit as rate_limit_module
    import app.backend.routers.deletion_feedback as deletion_feedback_module
    from app.db.session import get_session

    importlib.reload(rate_limit_module)
    importlib.reload(deletion_feedback_module)

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)

    app = FastAPI()
    app.state.limiter = rate_limit_module.limiter
    app.add_exception_handler(
        RateLimitExceeded,
        lambda request, exc: JSONResponse({"detail": "rate_limit_exceeded"}, status_code=429),
    )
    app.include_router(deletion_feedback_module.router)

    def _get_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _get_db

    client = TestClient(app)
    client.headers.update({"X-Admin-Secret": "test-admin-secret"})
    return client


def test_deletion_feedback_summary_rate_limit_exceeded(client_with_rate_limit):
    for i in range(10):
        response = client_with_rate_limit.get("/admin/deletion-feedback/summary")
        assert response.status_code == 200, f"Request {i+1} should succeed"

    response = client_with_rate_limit.get("/admin/deletion-feedback/summary")
    assert response.status_code == 429
