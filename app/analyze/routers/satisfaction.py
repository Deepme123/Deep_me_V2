from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.analyze import models as m
from app.analyze import schemas as sc
from app.analyze.routers.cards import _get_session_or_404
from app.backend.dependencies.auth import get_current_user
from app.db.session import get_session as get_db

router = APIRouter(prefix="/api", tags=["satisfaction"])


@router.put("/sessions/{session_id}/satisfaction", response_model=sc.SatisfactionRatingOut)
def upsert_satisfaction(
    session_id: UUID,
    body: sc.SatisfactionRatingCreate,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
):
    _get_session_or_404(db, session_id, current_user_id)

    existing = db.exec(
        select(m.SatisfactionRating).where(m.SatisfactionRating.session_id == session_id)
    ).first()

    if existing:
        existing.rating = body.rating
        existing.updated_at = datetime.utcnow()
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return sc.SatisfactionRatingOut.model_validate(existing, from_attributes=True)

    rating = m.SatisfactionRating(session_id=session_id, rating=body.rating)
    db.add(rating)
    db.commit()
    db.refresh(rating)
    return sc.SatisfactionRatingOut.model_validate(rating, from_attributes=True)


@router.get("/sessions/{session_id}/satisfaction", response_model=sc.SatisfactionRatingOut)
def get_satisfaction(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
):
    _get_session_or_404(db, session_id, current_user_id)

    rating = db.exec(
        select(m.SatisfactionRating).where(m.SatisfactionRating.session_id == session_id)
    ).first()
    if not rating:
        raise HTTPException(status_code=404, detail="satisfaction rating not found")
    return sc.SatisfactionRatingOut.model_validate(rating, from_attributes=True)
