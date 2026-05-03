from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


# ===== Session =====

class SessionCreate(BaseModel):
    user_id: UUID


class SessionOut(BaseModel):
    session_id: UUID
    user_id: UUID
    started_at: datetime
    ended_at: Optional[datetime] = None


# ===== Card (수동 생성/조회용) =====

class EmotionEntry(BaseModel):
    primary: str
    sub: List[str]


class CardCreate(BaseModel):
    summary: Optional[str] = None
    core_emotions: Optional[List[EmotionEntry]] = None
    situation: Optional[str] = None
    emotion: Optional[str] = None
    thoughts: Optional[str] = None
    physical_reactions: Optional[List[str]] = None
    behaviors: Optional[str] = None
    coping_actions: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    insight: Optional[str] = None


class CardOut(BaseModel):
    card_id: UUID
    session_id: UUID
    created_at: datetime

    summary: Optional[str] = None
    core_emotions: Optional[List[EmotionEntry]] = None
    situation: Optional[str] = None
    emotion: Optional[str] = None
    thoughts: Optional[str] = None
    physical_reactions: Optional[List[str]] = None
    behaviors: Optional[str] = None
    coping_actions: Optional[List[str]] = None
    risk_flag: bool
    risk_level: Optional[str] = None
    tags: Optional[List[str]] = None
    insight: Optional[str] = None
    exportable: bool = True


class SummaryOut(BaseModel):
    summary: Optional[str] = None
    core_emotions: Optional[List[EmotionEntry]] = None
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


class AutoCardRequestBase(BaseModel):
    title_hint: Optional[str] = Field(
        default=None,
        description="요약/제목 힌트(선택)",
    )


class AutoCardCreate(AutoCardRequestBase):
    conversation_log: List[ConversationTurn] = Field(
        default_factory=list,
        description="기존 방식: 호출자가 대화 로그를 직접 전달",
    )


class SessionAutoCardCreate(AutoCardRequestBase):
    session_id: UUID = Field(
        ...,
        description="세션 기반 방식: 서버가 session_id로 대화 로그를 조회",
    )


class AutoCardGenerateRequest(AutoCardRequestBase):
    session_id: Optional[UUID] = Field(
        default=None,
        description="권장 방식: 기존 세션을 참조해 서버가 대화 로그를 재구성",
    )
    conversation_log: Optional[List[ConversationTurn]] = Field(
        default=None,
        description="호환 방식: 기존 호출자는 대화 로그를 직접 전달 가능",
    )

    @model_validator(mode="after")
    def validate_input_source(self) -> "AutoCardGenerateRequest":
        if self.session_id is None and not self.conversation_log:
            raise ValueError("Either session_id or conversation_log must be provided.")
        return self
