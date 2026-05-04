from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.analyze import models as m
from app.analyze import schemas as sc
from app.analyze.db import get_db
from app.analyze.services import risk as risk_service
from app.analyze.services.llm_card import analyze_dialogue_to_card
from app.backend.models.emotion import EmotionStep

router = APIRouter(prefix="/api", tags=["cards"])


def _get_session_or_404(db: Session, session_id: UUID) -> m.EmotionSession:
    session = db.get(m.EmotionSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
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

    card = m.EmotionCard(
        session_id=session_id,
        summary=payload.summary,
        core_emotions=payload.core_emotions,
        situation=payload.situation,
        emotion=payload.emotion,
        thoughts=payload.thoughts,
        physical_reactions=payload.physical_reactions,
        behaviors=payload.behaviors,
        behavior_patterns=payload.behavior_patterns,
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
def create_session(body: sc.SessionCreate, db: Session = Depends(get_db)):
    session = m.EmotionSession(user_id=body.user_id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return sc.SessionOut.model_validate(session, from_attributes=True)


@router.post("/sessions/{session_id}/cards", response_model=sc.CardOut)
def create_card(
    session_id: UUID,
    body: sc.CardCreate,
    db: Session = Depends(get_db),
):
    _get_session_or_404(db, session_id)
    return _store_card(db=db, session_id=session_id, payload=body)


@router.post("/sessions/{session_id}/cards/auto", response_model=sc.CardOut)
def create_card_auto(
    session_id: UUID,
    body: sc.AutoCardCreate,
    db: Session = Depends(get_db),
):
    _get_session_or_404(db, session_id)
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
):
    _get_session_or_404(db, session_id)
    turns = _load_session_conversation_turns(db, session_id)
    title_hint = body.title_hint if body else None
    return _analyze_and_store_card(
        db=db,
        session_id=session_id,
        turns=turns,
        title_hint=title_hint,
    )


@router.get("/sessions/{session_id}/cards", response_model=list[sc.CardOut])
def list_cards(session_id: UUID, db: Session = Depends(get_db)):
    stmt = (
        select(m.EmotionCard)
        .where(m.EmotionCard.session_id == session_id)
        .order_by(m.EmotionCard.created_at.desc())
    )
    rows = db.exec(stmt).all()
    return [sc.CardOut.model_validate(row, from_attributes=True) for row in rows]


@router.get("/cards/{card_id}", response_model=sc.CardOut)
def get_card(card_id: UUID, db: Session = Depends(get_db)):
    card = db.get(m.EmotionCard, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="card not found")
    return sc.CardOut.model_validate(card, from_attributes=True)
