"""프롬프트 조회/수정 API (테스트 런타임 전용, 프롬프트 연구용).

C-1(2026-05-09)에서 무인증 프롬프트 덮어쓰기 취약점 때문에 전체 제거했던 API를
테스트 서버 한정으로 복원한 것이다. 연구 편의상 인증은 없고, 대신:
- 테스트 런타임(runtime_env.is_test_runtime)이 아니면 모든 경로가 404 — 운영 서버에는
  사실상 존재하지 않는 라우터다.
- 저장된 프롬프트도 테스트 런타임에서만 적용된다(prompt_loader.get_db_override).
- 파일을 덮어쓰지 않고 promptrevision에 append-only로 쌓아 재배포 후에도 유지되고
  이력이 남는다.
연구가 끝나면 이 라우터 등록을 다시 제거할 것 (docs/SECURITY_AUDIT.md C-1 참조).
"""

import hashlib
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlmodel import Session, select

from app.backend.core import prompt_loader
from app.backend.core.rate_limit import limiter
from app.backend.core.runtime_env import is_test_runtime
from app.backend.models.prompt_revision import PromptRevision
from app.db.session import get_session

MAX_PROMPT_BYTES = 50 * 1024  # 50KB safety cap

PromptType = Literal["system", "task"]


def _require_test_runtime() -> None:
    if not is_test_runtime():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")


router = APIRouter(
    prefix="/prompts",
    tags=["prompts"],
    dependencies=[Depends(_require_test_runtime)],
)


class PromptUpdate(BaseModel):
    content: str


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _iso(dt: datetime) -> str:
    return dt.replace(tzinfo=timezone.utc).isoformat()


def _file_updated_at(prompt_type: str) -> Optional[str]:
    path = prompt_loader.TASK_PROMPT_PATH if prompt_type == "task" else prompt_loader.PROMPT_PATH
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    except FileNotFoundError:
        return None


def _latest_revision(db: Session, prompt_type: str) -> Optional[PromptRevision]:
    return db.exec(
        select(PromptRevision)
        .where(PromptRevision.prompt_type == prompt_type)
        .order_by(PromptRevision.revision_id.desc())
        .limit(1)
    ).first()


def _current_prompt_response(db: Session, prompt_type: str) -> dict:
    row = _latest_revision(db, prompt_type)
    if row is not None and row.content:
        content, source, updated_at = row.content, "db", _iso(row.created_at)
    else:
        content = prompt_loader.get_file_prompt(prompt_type)
        source, updated_at = "file", _file_updated_at(prompt_type)
    return {
        "type": prompt_type,
        "content": content,
        "sha256": _sha256(content),
        "updated_at": updated_at,
        "source": source,
    }


def _validate_content(content: str) -> str:
    trimmed = (content or "").strip()
    if not trimmed:
        raise HTTPException(status_code=400, detail="content_empty")
    if len(trimmed.encode("utf-8")) > MAX_PROMPT_BYTES:
        raise HTTPException(status_code=400, detail="content_too_large")
    return trimmed


def _save_revision(db: Session, prompt_type: str, content: Optional[str]) -> None:
    db.add(PromptRevision(prompt_type=prompt_type, content=content))
    db.commit()
    if prompt_type == "system":
        prompt_loader.get_system_prompt.cache_clear()
    else:
        prompt_loader.get_task_prompt.cache_clear()


@router.get("/{prompt_type}")
def read_prompt(prompt_type: PromptType, db: Session = Depends(get_session)):
    return _current_prompt_response(db, prompt_type)


@router.put("/{prompt_type}")
@limiter.limit("20/minute")
def update_prompt(
    request: Request,
    prompt_type: PromptType,
    payload: PromptUpdate,
    db: Session = Depends(get_session),
):
    _save_revision(db, prompt_type, _validate_content(payload.content))
    return _current_prompt_response(db, prompt_type)


@router.delete("/{prompt_type}")
@limiter.limit("20/minute")
def reset_prompt(request: Request, prompt_type: PromptType, db: Session = Depends(get_session)):
    """파일 기본값(resources/*.txt)으로 되돌린다. 초기화도 이력에 NULL 행으로 남긴다."""
    _save_revision(db, prompt_type, None)
    return _current_prompt_response(db, prompt_type)


@router.get("/{prompt_type}/history")
def read_prompt_history(
    prompt_type: PromptType,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_session),
):
    rows = db.exec(
        select(PromptRevision)
        .where(PromptRevision.prompt_type == prompt_type)
        .order_by(PromptRevision.revision_id.desc())
        .limit(limit)
    ).all()
    return [
        {
            "revision_id": row.revision_id,
            "content": row.content,
            "sha256": _sha256(row.content) if row.content else None,
            "created_at": _iso(row.created_at),
            "is_reset": row.content is None,
        }
        for row in rows
    ]
