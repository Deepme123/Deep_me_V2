from __future__ import annotations

from uuid import UUID
from typing import Optional

from sqlmodel import Session, select

from app.analyze import models as m
from app.backend.models.emotion import EmotionSession


def list_summaries(
    db: Session,
    *,
    user_id: UUID,
    session_id: Optional[UUID] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> list[m.AnalysisCard]:
    stmt = (
        select(m.AnalysisCard)
        .join(EmotionSession, EmotionSession.session_id == m.AnalysisCard.session_id)
        .where(EmotionSession.user_id == user_id)
        .order_by(m.AnalysisCard.created_at.desc())
    )
    if session_id is not None:
        stmt = stmt.where(m.AnalysisCard.session_id == session_id)
    if offset is not None:
        stmt = stmt.offset(offset)
    if limit is not None:
        stmt = stmt.limit(limit)
    return db.exec(stmt).all()
