from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.analyze.db import get_db
from app.analyze import schemas as sc
from app.analyze.services import summaries as summary_service


router = APIRouter(prefix="/api", tags=["summaries"])


def _serialize_cards(rows: list) -> list[sc.CardOut]:
    return [
        sc.CardOut.model_validate(row, from_attributes=True)
        for row in rows
    ]


@router.get("/summaries", response_model=list[sc.CardOut])
def list_summaries(
    limit: Optional[int] = Query(default=None, gt=0),
    offset: Optional[int] = Query(default=None, ge=0),
    db: Session = Depends(get_db),
):
    rows = summary_service.list_summaries(
        db,
        limit=limit,
        offset=offset,
    )
    return _serialize_cards(rows)


@router.get("/sessions/{session_id}/summaries", response_model=list[sc.CardOut])
def list_session_summaries(
    session_id: UUID,
    limit: Optional[int] = Query(default=None, gt=0),
    offset: Optional[int] = Query(default=None, ge=0),
    db: Session = Depends(get_db),
):
    rows = summary_service.list_summaries(
        db,
        session_id=session_id,
        limit=limit,
        offset=offset,
    )
    return _serialize_cards(rows)
