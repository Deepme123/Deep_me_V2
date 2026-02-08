# app/db/session.py
import logging
import os
from contextlib import contextmanager

from sqlalchemy.engine import url as sa_url
from sqlmodel import SQLModel, create_engine

log = logging.getLogger(__name__)

_ALLOWED_ENVS = {"dev", "prod", "test"}


def _get_env() -> str:
    env = os.getenv("ENV", "dev").strip().lower()
    if env not in _ALLOWED_ENVS:
        allowed = "|".join(sorted(_ALLOWED_ENVS))
        raise RuntimeError(f"ENV must be one of {allowed}")
    return env


def _mask(url: str) -> str:
    if "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    if "@" in rest and ":" in rest.split("@", 1)[0]:
        creds, tail = rest.split("@", 1)
        user = creds.split(":", 1)[0]
        return f"{scheme}://{user}:***@{tail}"
    return url


def _strip_outer_quotes(s: str) -> str:
    if not s:
        return s
    if (s[0] == s[-1]) and s[0] in ("'", '"', "`"):
        return s[1:-1].strip()
    return s


def _build_db_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    url = _strip_outer_quotes(url)

    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)

    if not url:
        raise RuntimeError(
            "DATABASE_URL is required (Postgres only). "
            "Example: postgresql+psycopg2://user:pass@host:5432/dbname"
        )

    if not (url.startswith("postgresql+psycopg2://") or url.startswith("postgresql+psycopg://")):
        raise RuntimeError(
            "Only Postgres DSNs are supported. "
            "Use postgresql+psycopg2://user:pass@host:5432/dbname "
            "or postgresql+psycopg://user:pass@host:5432/dbname"
        )

    if any(dom in url for dom in ("render.com", "neon.tech")) and "sslmode=" not in url and url:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}sslmode=require"

    try:
        sa_url.make_url(url)
    except Exception as exc:
        raise RuntimeError(f"Invalid DATABASE_URL: {repr(url)} ({exc})")

    log.info("DB URL: %s", _mask(url))
    return url


_get_env()
DATABASE_URL = _build_db_url()
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=5,
    max_overflow=5,
)


def get_session():
    """FastAPI Depends(get_session) generator."""
    from sqlmodel import Session

    with Session(engine) as s:
        yield s


def create_all_tables() -> None:
    SQLModel.metadata.create_all(engine)


@contextmanager
def session_scope():
    """Context-managed session for non-Depends use (eg. websockets)."""
    from sqlmodel import Session

    s = Session(engine)
    try:
        yield s
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
