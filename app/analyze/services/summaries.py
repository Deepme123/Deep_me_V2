from __future__ import annotations

from uuid import UUID
from typing import Optional

from sqlmodel import Session, select

from app.analyze import models as m


def list_summaries(
    db: Session,
    *,
    session_id: Optional[UUID] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> list[m.AnalysisCard]:
    stmt = (
        select(m.AnalysisCard)
        .order_by(m.AnalysisCard.created_at.desc())
    )
    if session_id is not None:
        stmt = stmt.where(m.AnalysisCard.session_id == session_id)
    if offset is not None:
        stmt = stmt.offset(offset)
    if limit is not None:
        stmt = stmt.limit(limit)
    return db.exec(stmt).all()
