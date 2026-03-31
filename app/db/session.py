# app/db/session.py
import logging
import os
from contextlib import contextmanager
from functools import lru_cache
from urllib.parse import quote_plus

import sqlalchemy as sa
from sqlalchemy.engine import url as sa_url
from sqlmodel import SQLModel, create_engine

log = logging.getLogger(__name__)

CORE_REQUIRED_TABLES = (
    "user",
    "emotionsession",
    "emotionstep",
)
ANALYZE_REQUIRED_TABLES = CORE_REQUIRED_TABLES + ("emotioncard",)


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

    if any(dom in url for dom in ("render.com", "neon.tech")) and "sslmode=" not in url and url:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}sslmode=require"

    if not url:
        host = os.getenv("POSTGRES_HOST", "").strip()
        port = os.getenv("POSTGRES_PORT", "5432").strip()
        db = os.getenv("POSTGRES_DB", "").strip()
        user = os.getenv("POSTGRES_USER", "").strip()
        pwd = os.getenv("POSTGRES_PASSWORD", "").strip()

        if not (host and db and user):
            raise RuntimeError("DATABASE_URL is empty and POSTGRES_* is incomplete")

        if any(ch in pwd for ch in "@:/?#"):
            pwd = quote_plus(pwd)

        url = f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{db}"

        if any(dom in host for dom in ("render.com", "neon.tech")):
            url += "?sslmode=require"

    try:
        sa_url.make_url(url)
    except Exception as exc:
        raise RuntimeError(f"Invalid DATABASE_URL: {repr(url)} ({exc})")

    log.info("DB URL: %s", _mask(url))
    return url

@lru_cache(maxsize=1)
def get_database_url() -> str:
    return _build_db_url()


@lru_cache(maxsize=1)
def get_engine():
    return create_engine(
        get_database_url(),
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_size=5,
        max_overflow=5,
    )


def get_session():
    """FastAPI Depends(get_session) generator."""
    from sqlmodel import Session

    with Session(get_engine()) as s:
        yield s


def create_all_tables() -> None:
    SQLModel.metadata.create_all(get_engine())


def get_existing_tables(*, schema: str | None = None) -> set[str]:
    engine = get_engine()
    if schema and engine.dialect.name != "postgresql":
        schema = None
    inspector = sa.inspect(engine)
    return set(inspector.get_table_names(schema=schema))


def missing_required_tables(
    required_tables: tuple[str, ...] | list[str],
    *,
    schema: str | None = None,
) -> list[str]:
    existing = get_existing_tables(schema=schema)
    return [table for table in required_tables if table not in existing]


def ensure_required_tables(
    required_tables: tuple[str, ...] | list[str],
    *,
    schema: str | None = None,
) -> None:
    missing = missing_required_tables(required_tables, schema=schema)
    if missing:
        missing_csv = ", ".join(missing)
        schema_name = schema or "default search_path"
        raise RuntimeError(
            f"Missing required tables in schema {schema_name}: {missing_csv}"
        )


@contextmanager
def session_scope():
    """Context-managed session for non-Depends use (eg. websockets)."""
    from sqlmodel import Session

    s = Session(get_engine())
    try:
        yield s
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
