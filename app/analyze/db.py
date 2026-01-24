# app/db.py
from __future__ import annotations

from typing import Iterator

from sqlmodel import SQLModel, Session, create_engine

from app.analyze.config import settings

# DATABASE_URL은 .env 또는 환경변수에서 설정
DATABASE_URL = settings.database_url
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not configured")

# SQLModel 엔진 생성
engine = create_engine(
    DATABASE_URL,
    echo=(settings.app_env == "local"),
    pool_pre_ping=True,
)


def init_db() -> None:
    """모델 테이블 생성이 필요할 때 사용(알렘빅 없이 쓸 때)."""
    SQLModel.metadata.create_all(engine)


def get_db() -> Iterator[Session]:
    """FastAPI 의존성 주입용 DB 세션."""
    with Session(engine) as session:
        yield session


# backward-compat for old imports
def get_session():
    yield from get_db()
