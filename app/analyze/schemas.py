# app/schemas.py
from __future__ import annotations

from typing import List, Optional
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, Field


# ===== Session =====

class SessionCreate(BaseModel):
    user_id: UUID


class SessionOut(BaseModel):
    session_id: UUID
    user_id: UUID
    started_at: datetime
    ended_at: Optional[datetime] = None


# ===== Card (수동 생성/조회용) =====

class CardCreate(BaseModel):
    summary: Optional[str] = None
    core_emotions: Optional[List[str]] = None
    situation: Optional[str] = None
    emotion: Optional[str] = None
    thoughts: Optional[str] = None
    physical_reactions: Optional[str] = None
    behaviors: Optional[str] = None
    coping_actions: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    insight: Optional[str] = None


class CardOut(BaseModel):
    card_id: UUID
    session_id: UUID
    created_at: datetime

    summary: Optional[str] = None
    core_emotions: Optional[List[str]] = None
    situation: Optional[str] = None
    emotion: Optional[str] = None
    thoughts: Optional[str] = None
    physical_reactions: Optional[str] = None
    behaviors: Optional[str] = None
    coping_actions: Optional[List[str]] = None
    risk_flag: bool
    risk_level: Optional[str] = None
    tags: Optional[List[str]] = None
    insight: Optional[str] = None
    exportable: bool = True


class SummaryOut(BaseModel):
    summary: Optional[str] = None
    core_emotions: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    created_at: datetime
    risk_level: Optional[str] = None


# ===== Auto Analyze용 스키마 =====

class ConversationTurn(BaseModel):
    role: str = Field(
        ...,
        description="대화 역할: user / assistant / system 등",
    )
    speaker: str = Field(
        ...,
        description="표시용 화자: 예) USER / NOA",
    )
    text: str = Field(..., description="대화 내용")
    timestamp: Optional[datetime] = Field(
        default=None,
        description="선택: 타임스탬프",
    )


class AutoCardCreate(BaseModel):
    conversation_log: List[ConversationTurn] = Field(
        default_factory=list,
        description="노아-사용자 대화 로그",
    )
    title_hint: Optional[str] = Field(
        default=None,
        description="요약/제목 힌트(선택)",
    )
