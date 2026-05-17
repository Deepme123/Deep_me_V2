# app/models.py
from __future__ import annotations

from typing import Any, Optional, List
from uuid import UUID, uuid4
from datetime import datetime

from sqlmodel import SQLModel, Field
from sqlalchemy import Column, JSON

from app.backend.models.emotion import EmotionSession

class AnalysisCard(SQLModel, table=True):
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
    thoughts: Optional[str] = None
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
