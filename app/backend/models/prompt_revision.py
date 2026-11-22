from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Text
from sqlmodel import SQLModel, Field


class PromptRevision(SQLModel, table=True):
    """테스트 서버 프롬프트 연구용 수정 이력 (append-only).

    prompt_type('system'/'task')별 가장 최근 행이 현재 적용 중인 프롬프트다.
    content가 NULL인 행은 "파일 기본값으로 초기화"를 뜻한다. 이 오버라이드는
    테스트 런타임에서만 읽힌다(app/backend/core/runtime_env.py 참조) — 운영 서버는
    DB를 공유하더라도 항상 resources/*.txt 파일 프롬프트를 쓴다.
    """

    __tablename__ = "promptrevision"

    revision_id: Optional[int] = Field(default=None, primary_key=True)
    prompt_type: str = Field(max_length=16, index=True)
    content: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(default_factory=datetime.utcnow)
