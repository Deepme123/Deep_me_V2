# app/models.py
from __future__ import annotations

from typing import Any, Optional, List
from uuid import UUID, uuid4
from datetime import datetime

from sqlmodel import SQLModel, Field
from sqlalchemy import Column, ForeignKey, JSON, UniqueConstraint

from app.backend.models.emotion import EmotionSession

class AnalysisCard(SQLModel, table=True):
    __tablename__ = "analysiscard"
    __table_args__ = (
        UniqueConstraint("session_id", name="uq_analysiscard_session_id"),
    )

    card_id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
    )
    session_id: UUID = Field(
        foreign_key="emotionsession.session_id",
        index=True,
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)

    summary: Optional[str] = None
    core_emotions: Optional[List[Any]] = Field(
        default=None,
        sa_column=Column(JSON),
    )
    situation: Optional[str] = None
    situation_steps: Optional[List[Any]] = Field(
        default=None,
        sa_column=Column(JSON),
    )
    emotion: Optional[str] = None
    thoughts: Optional[List[Any]] = Field(
        default=None,
        sa_column=Column(JSON),
    )
    physical_reactions: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(JSON),
    )
    behaviors: Optional[str] = None
    behavior_patterns: Optional[List[Any]] = Field(
        default=None,
        sa_column=Column(JSON),
    )
    coping_actions: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(JSON),
    )
    risk_flag: bool = Field(default=False)
    risk_level: Optional[str] = Field(
        default=None,
        description="LOW|MEDIUM|HIGH",
    )
    tags: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(JSON),
    )
    insight: Optional[str] = None
    exportable: bool = Field(default=True)


class SatisfactionRating(SQLModel, table=True):
    __tablename__ = "satisfactionrating"
    __table_args__ = (
        UniqueConstraint("session_id", name="uq_satisfactionrating_session_id"),
    )

    rating_id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
    )
    # 탈퇴 시 세션은 삭제되지만 만족도 평가는 보존 대상이라 nullable +
    # ON DELETE SET NULL로 둔다 (UserNeedSelection.session_id와 동일 패턴).
    session_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(
            ForeignKey("emotionsession.session_id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )
    rating: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
