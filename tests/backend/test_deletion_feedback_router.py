import importlib
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

os.environ.setdefault("JWT_SECRET_KEY", "test_secret")
os.environ.setdefault("JWT_REFRESH_SECRET", "test_refresh")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://user:pass@localhost/testdb")

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

deletion_feedback_router_module = importlib.import_module(
    "app.backend.routers.deletion_feedback"
)
deletion_feedback_model = importlib.import_module("app.backend.models.deletion_feedback")
db_session_module = importlib.import_module("app.db.session")


@pytest.fixture
def engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


ADMIN_SECRET = "test-admin-secret"


def _build_client(engine, admin_secret=ADMIN_SECRET):
    app = FastAPI()
    app.include_router(deletion_feedback_router_module.router)

    def _get_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[db_session_module.get_session] = _get_db
    client = TestClient(app)
    client.headers.update(
        {"X-Admin-Secret": admin_secret} if admin_secret else {}
    )
    return client


@pytest.fixture(autouse=True)
def _set_admin_secret(monkeypatch):
    monkeypatch.setattr(deletion_feedback_router_module, "ADMIN_API_SECRET", ADMIN_SECRET)


def _add_feedback(engine, reason_codes, created_at=None):
    with Session(engine) as db:
        db.add(
            deletion_feedback_model.DeletionFeedback(
                user_id=uuid4(),
                reason_codes=reason_codes,
                created_at=created_at or datetime.utcnow(),
            )
        )
        db.commit()


class TestAdminSecretAuth:
    def test_missing_header_is_rejected(self, engine):
        client = _build_client(engine, admin_secret=None)

        response = client.get("/admin/deletion-feedback/summary")

        assert response.status_code == 403

    def test_wrong_secret_is_rejected(self, engine):
        client = _build_client(engine, admin_secret="wrong-secret")

        response = client.get("/admin/deletion-feedback/export")

        assert response.status_code == 403

    def test_correct_secret_is_accepted(self, engine):
        client = _build_client(engine)

        response = client.get("/admin/deletion-feedback/summary")

        assert response.status_code == 200

    def test_fails_closed_when_secret_not_configured(self, engine, monkeypatch):
        monkeypatch.setattr(deletion_feedback_router_module, "ADMIN_API_SECRET", "")
        client = _build_client(engine, admin_secret="anything")

        response = client.get("/admin/deletion-feedback/summary")

        assert response.status_code == 403
        assert response.json()["detail"] == "admin_access_not_configured"


class TestDeletionFeedbackSummary:
    def test_returns_zero_counts_when_empty(self, engine):
        client = _build_client(engine)

        response = client.get("/admin/deletion-feedback/summary")

        assert response.status_code == 200
        assert response.json() == {
            "total": 0,
            "by_reason": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0},
        }

    def test_aggregates_counts_per_reason_code(self, engine):
        _add_feedback(engine, [1, 3])
        _add_feedback(engine, [3])
        _add_feedback(engine, [5])

        client = _build_client(engine)
        response = client.get("/admin/deletion-feedback/summary")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 3
        assert body["by_reason"] == {"1": 1, "2": 0, "3": 2, "4": 0, "5": 1}

    def test_survives_after_referenced_user_no_longer_exists(self, engine):
        """user row가 지워진 뒤에도(FK 없음) 집계가 그대로 유지되는지 확인."""
        _add_feedback(engine, [2])

        client = _build_client(engine)
        response = client.get("/admin/deletion-feedback/summary")

        assert response.json()["total"] == 1


class TestDeletionFeedbackExport:
    def test_export_excludes_identifying_fields(self, engine):
        older = datetime.utcnow() - timedelta(days=1)
        _add_feedback(engine, [2], created_at=older)
        _add_feedback(engine, [4])

        client = _build_client(engine)
        response = client.get("/admin/deletion-feedback/export")

        assert response.status_code == 200
        rows = response.json()
        assert len(rows) == 2
        for row in rows:
            assert set(row.keys()) == {"user_id", "reason_codes", "created_at"}
        # created_at 내림차순
        assert rows[0]["reason_codes"] == [4]
        assert rows[1]["reason_codes"] == [2]
