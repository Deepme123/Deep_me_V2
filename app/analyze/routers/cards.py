# app/routers/cards.py
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.analyze.db import get_db
from app.analyze import models as m
from app.analyze import schemas as sc
from app.analyze.services import risk as risk_service
from app.analyze.services.llm_card import analyze_dialogue_to_card

router = APIRouter(prefix="/api", tags=["cards"])


# ===== 세션 생성 =====
@router.post("/sessions", response_model=sc.SessionOut)
def create_session(body: sc.SessionCreate, db: Session = Depends(get_db)):
    ses = m.EmotionSession(user_id=body.user_id)
    db.add(ses)
    db.commit()
    db.refresh(ses)
    return sc.SessionOut.model_validate(ses, from_attributes=True)


# ===== 카드 수동 생성 =====
@router.post("/sessions/{session_id}/cards", response_model=sc.CardOut)
def create_card(
    session_id: UUID,
    body: sc.CardCreate,
    db: Session = Depends(get_db),
):
    ses = db.get(m.EmotionSession, session_id)
    if not ses:
        raise HTTPException(status_code=404, detail="session not found")

    # 위험도 계산 (텍스트 기반 단순 스코어링)
    risk_flag, risk_level = risk_service.risk_from_payload(body.model_dump())

    card = m.EmotionCard(
        session_id=session_id,
        summary=body.summary,
        core_emotions=body.core_emotions,
        situation=body.situation,
        emotion=body.emotion,
        thoughts=body.thoughts,
        physical_reactions=body.physical_reactions,
        behaviors=body.behaviors,
        coping_actions=body.coping_actions,
        tags=body.tags,
        insight=body.insight,
        exportable=True,
        risk_flag=risk_flag,
        risk_level=risk_level,
    )
    db.add(card)
    db.commit()
    db.refresh(card)

    return sc.CardOut.model_validate(card, from_attributes=True)


# ===== 카드 자동 생성 (GPT 분석) =====
@router.post("/sessions/{session_id}/cards/auto", response_model=sc.CardOut)
def create_card_auto(
    session_id: UUID,
    body: sc.AutoCardCreate,
    db: Session = Depends(get_db),
):
    ses = db.get(m.EmotionSession, session_id)
    if not ses:
        raise HTTPException(status_code=404, detail="session not found")

    # LLM을 사용해 대화 → CardCreate 스키마로 변환
    card_payload = analyze_dialogue_to_card(
        turns=body.conversation_log,
        title_hint=body.title_hint,
    )

    # 위험도 스코어링
    risk_flag, risk_level = risk_service.risk_from_payload(
        card_payload.model_dump()
    )

    card = m.EmotionCard(
        session_id=session_id,
        summary=card_payload.summary,
        core_emotions=card_payload.core_emotions,
        situation=card_payload.situation,
        emotion=card_payload.emotion,
        thoughts=card_payload.thoughts,
        physical_reactions=card_payload.physical_reactions,
        behaviors=card_payload.behaviors,
        coping_actions=card_payload.coping_actions,
        tags=card_payload.tags,
        insight=card_payload.insight,
        exportable=True,
        risk_flag=risk_flag,
        risk_level=risk_level,
    )
    db.add(card)
    db.commit()
    db.refresh(card)

    return sc.CardOut.model_validate(card, from_attributes=True)


# ===== 세션별 카드 목록 조회 =====
@router.get("/sessions/{session_id}/cards", response_model=list[sc.CardOut])
def list_cards(session_id: UUID, db: Session = Depends(get_db)):
    stmt = (
        select(m.EmotionCard)
        .where(m.EmotionCard.session_id == session_id)
        .order_by(m.EmotionCard.created_at.desc())
    )
    rows = db.exec(stmt).all()
    return [sc.CardOut.model_validate(r, from_attributes=True) for r in rows]


# ===== 단건 조회 =====
@router.get("/cards/{card_id}", response_model=sc.CardOut)
def get_card(card_id: UUID, db: Session = Depends(get_db)):
    card = db.get(m.EmotionCard, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="card not found")
    return sc.CardOut.model_validate(card, from_attributes=True)
