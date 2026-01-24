# app/models.py
from __future__ import annotations

from typing import Optional, List
from uuid import UUID, uuid4
from datetime import datetime

from sqlmodel import SQLModel, Field
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB


class EmotionSession(SQLModel, table=True):
    __tablename__ = "emotionsession"

    session_id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        index=True,
    )
    user_id: UUID = Field(index=True)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None


class EmotionCard(SQLModel, table=True):
    __tablename__ = "emotioncard"

    card_id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        index=True,
    )
    session_id: UUID = Field(
        foreign_key="emotionsession.session_id",
        index=True,
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)

    summary: Optional[str] = None
    core_emotions: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(JSONB),
    )
    situation: Optional[str] = None
    emotion: Optional[str] = None
    thoughts: Optional[str] = None
    physical_reactions: Optional[str] = None
    behaviors: Optional[str] = None
    coping_actions: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(JSONB),
    )
    risk_flag: bool = Field(default=False)
    risk_level: Optional[str] = Field(
        default=None,
        description="LOW|MEDIUM|HIGH",
    )
    tags: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(JSONB),
    )
    insight: Optional[str] = None
    exportable: bool = Field(default=True)
