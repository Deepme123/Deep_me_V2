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
from sqlmodel import Session, SQLModel, create_engine, select

os.environ.setdefault("JWT_SECRET_KEY", "test_secret")
os.environ.setdefault("JWT_REFRESH_SECRET", "test_refresh")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://user:pass@localhost/testdb")

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

auth_router_module = importlib.import_module("app.backend.routers.auth")
user_model = importlib.import_module("app.backend.models.user")
refresh_token_model = importlib.import_module("app.backend.models.refresh_token")
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


def _make_user_with_refresh_token(db: Session):
    user = user_model.User(name="로그아웃테스트", email=f"{uuid4()}@example.com")
    db.add(user)
    db.commit()
    db.refresh(user)

    token = refresh_token_model.RefreshToken(
        jti=str(uuid4()),
        user_id=user.user_id,
        token_hash="hash",
        expires_at=datetime.utcnow() + timedelta(days=1),
    )
    db.add(token)
    db.commit()
    return user, token


def _client(engine, *, authenticated_user_id=None):
    app = FastAPI()
    app.include_router(auth_router_module.auth_router)

    def _get_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[db_session_module.get_session] = _get_db
    if authenticated_user_id is not None:
        app.dependency_overrides[auth_router_module.get_current_user] = (
            lambda: str(authenticated_user_id)
        )
    return TestClient(app)


def test_logout_without_auth_is_rejected(engine):
    client = _client(engine)
    resp = client.get("/auth/logout")
    assert resp.status_code in (401, 403)


def test_logout_revokes_refresh_tokens_and_clears_cookies(engine):
    with Session(engine) as db:
        user, token = _make_user_with_refresh_token(db)
        user_id = user.user_id
        jti = token.jti

    client = _client(engine, authenticated_user_id=user_id)
    resp = client.get("/auth/logout")

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    with Session(engine) as db:
        row = db.exec(
            select(refresh_token_model.RefreshToken).where(
                refresh_token_model.RefreshToken.jti == jti
            )
        ).first()
        assert row.revoked_at is not None
