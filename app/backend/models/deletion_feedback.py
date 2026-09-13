from datetime import datetime
from typing import List
from uuid import UUID, uuid4

from sqlalchemy import Column, JSON
from sqlmodel import SQLModel, Field


class DeletionFeedback(SQLModel, table=True):
    """탈퇴 사유 집계용 레코드.

    user_id는 참고용으로만 저장하고 FK를 걸지 않는다 — 유예 기간(기본 5일) 뒤
    user row가 실제로 삭제돼도(app/backend/services/account_deletion.py) 이
    레코드는 남아서 사유 집계가 가능해야 하기 때문이다.
    """

    __tablename__ = "deletionfeedback"

    feedback_id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(index=True)
    reason_codes: List[int] = Field(sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
