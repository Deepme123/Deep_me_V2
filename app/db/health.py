from __future__ import annotations

import logging

from fastapi import HTTPException
from sqlmodel import text

from app.db.session import ensure_required_tables

logger = logging.getLogger(__name__)


def check_db_tables(
    engine,
    required_tables: tuple[str, ...] | list[str],
    label: str,
) -> None:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    ensure_required_tables(required_tables, schema="public")
    logger.info("%s tables verified", label)


def health_db_response(
    engine,
    required_tables: tuple[str, ...] | list[str],
    label: str,
) -> dict:
    try:
        check_db_tables(engine, required_tables, label)
        return {"ok": True}
    except RuntimeError as exc:
        logger.exception("Required %s table check failed", label)
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=500, detail="Database connection failed")
