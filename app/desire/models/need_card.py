from uuid import UUID, uuid4
from datetime import datetime
from typing import List, Optional

from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, ForeignKey, Index


class NeedCardResult(SQLModel, table=True):
    __tablename__ = "need_card_result"

    result_id: UUID = Field(default_factory=uuid4, primary_key=True)
    session_id: UUID = Field(
        sa_column=Column(
            ForeignKey("emotionsession.session_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)

    scores: List["NeedCardScore"] = Relationship(back_populates="result")


class NeedCardScore(SQLModel, table=True):
    __tablename__ = "need_card_score"

    score_id: UUID = Field(default_factory=uuid4, primary_key=True)
    result_id: UUID = Field(
        sa_column=Column(
            ForeignKey("need_card_result.result_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    code: str = Field(nullable=False)
    score: int = Field(nullable=False)
    rank: int = Field(nullable=False)

    result: Optional[NeedCardResult] = Relationship(back_populates="scores")
