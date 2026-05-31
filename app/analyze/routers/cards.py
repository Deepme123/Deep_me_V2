from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.analyze import models as m
from app.analyze import schemas as sc
from app.analyze.db import get_db
from app.analyze.services import risk as risk_service
from app.analyze.services.llm_card import analyze_dialogue_to_card
from app.backend.dependencies.auth import get_current_user
from app.backend.models.emotion import EmotionStep

router = APIRouter(prefix="/api", tags=["cards"])


def _get_session_or_404(
    db: Session,
    session_id: UUID,
    current_user_id: str | None = None,
) -> m.EmotionSession:
    session = db.get(m.EmotionSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    if current_user_id is not None and str(session.user_id) != current_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    return session


def _has_meaningful_card_content(payload: sc.CardCreate) -> bool:
    for value in payload.model_dump().values():
        if isinstance(value, str) and value.strip():
            return True
        if isinstance(value, list) and value:
            return True
    return False


def _store_card(db: Session, session_id: UUID, payload: sc.CardCreate) -> sc.CardOut:
    risk_flag, risk_level = risk_service.risk_from_payload(payload.model_dump())

    card = m.AnalysisCard(
        session_id=session_id,
        summary=payload.summary,
        core_emotions=[e.model_dump() for e in payload.core_emotions] if payload.core_emotions else None,
        situation=payload.situation,
        situation_steps=[s.model_dump() for s in payload.situation_steps] if payload.situation_steps else None,
        physical_reactions=[r.model_dump() for r in payload.physical_reactions] if payload.physical_reactions else None,
        behavior_patterns=[b.model_dump() for b in payload.behavior_patterns] if payload.behavior_patterns else None,
        coping_actions=payload.coping_actions,
        tags=payload.tags,
        insight=payload.insight,
        exportable=True,
        risk_flag=risk_flag,
        risk_level=risk_level,
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    return sc.CardOut.model_validate(card, from_attributes=True)


def _analyze_and_store_card(
    db: Session,
    session_id: UUID,
    turns: list[sc.ConversationTurn],
    title_hint: str | None = None,
) -> sc.CardOut:
    if not turns:
        raise HTTPException(status_code=400, detail="conversation history is empty")

    payload = analyze_dialogue_to_card(turns=turns, title_hint=title_hint)
    if not _has_meaningful_card_content(payload):
        raise HTTPException(status_code=502, detail="card generation failed")
    return _store_card(db=db, session_id=session_id, payload=payload)


def _transcript_rows_to_conversation_turns(
    transcript_rows: list[EmotionStep],
) -> list[sc.ConversationTurn]:
    turns: list[sc.ConversationTurn] = []
    for row in transcript_rows:
        if row.step_type not in {"user", "assistant"}:
            continue
        if row.user_input:
            turns.append(
                sc.ConversationTurn(
                    role="user",
                    speaker="USER",
                    text=row.user_input,
                    timestamp=row.created_at,
                )
            )
        if row.gpt_response:
            turns.append(
                sc.ConversationTurn(
                    role="assistant",
                    speaker="NOA",
                    text=row.gpt_response,
                    timestamp=row.created_at,
                )
            )
    return turns


def _load_session_conversation_turns(
    db: Session,
    session_id: UUID,
) -> list[sc.ConversationTurn]:
    transcript_rows = db.exec(
        select(EmotionStep)
        .where(EmotionStep.session_id == session_id)
        .order_by(EmotionStep.step_order)
    ).all()
    return _transcript_rows_to_conversation_turns(transcript_rows)


@router.post("/sessions", response_model=sc.SessionOut)
def create_session(
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
):
    session = m.EmotionSession(user_id=UUID(current_user_id))
    db.add(session)
    db.commit()
    db.refresh(session)
    return sc.SessionOut.model_validate(session, from_attributes=True)


@router.post("/sessions/{session_id}/cards", response_model=sc.CardOut)
def create_card(
    session_id: UUID,
    body: sc.CardCreate,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
):
    _get_session_or_404(db, session_id, current_user_id)
    return _store_card(db=db, session_id=session_id, payload=body)


@router.post("/sessions/{session_id}/cards/auto", response_model=sc.CardOut)
def create_card_auto(
    session_id: UUID,
    body: sc.AutoCardCreate,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
):
    _get_session_or_404(db, session_id, current_user_id)
    return _analyze_and_store_card(
        db=db,
        session_id=session_id,
        turns=body.conversation_log,
        title_hint=body.title_hint,
    )


@router.post("/sessions/{session_id}/cards/auto-from-session", response_model=sc.CardOut)
def create_card_auto_from_session(
    session_id: UUID,
    body: sc.AutoCardRequestBase | None = None,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
):
    _get_session_or_404(db, session_id, current_user_id)
    turns = _load_session_conversation_turns(db, session_id)
    title_hint = body.title_hint if body else None
    return _analyze_and_store_card(
        db=db,
        session_id=session_id,
        turns=turns,
        title_hint=title_hint,
    )


@router.get("/sessions/{session_id}/cards", response_model=list[sc.CardOut])
def list_cards(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
):
    _get_session_or_404(db, session_id, current_user_id)
    stmt = (
        select(m.AnalysisCard)
        .where(m.AnalysisCard.session_id == session_id)
        .order_by(m.AnalysisCard.created_at.desc())
    )
    rows = db.exec(stmt).all()
    return [sc.CardOut.model_validate(row, from_attributes=True) for row in rows]


@router.get("/cards/{card_id}", response_model=sc.CardOut)
def get_card(
    card_id: UUID,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user),
):
    card = db.get(m.AnalysisCard, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="card not found")
    _get_session_or_404(db, card.session_id, current_user_id)
    return sc.CardOut.model_validate(card, from_attributes=True)
