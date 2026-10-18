import logging
from functools import lru_cache
from typing import Optional

from sqlmodel import select

from app.backend.core.runtime_env import is_test_runtime
from app.backend.models.prompt_revision import PromptRevision
from app.core.resource_files import read_prompt, resolve_resource_path
from app.db.session import session_scope

logger = logging.getLogger(__name__)

PROMPT_PATH = resolve_resource_path("backend", "system_prompt.txt")
TASK_PROMPT_PATH = resolve_resource_path("backend", "task_prompt.txt")

FALLBACK_PROMPT = (
    "너는 감정 기반 챗봇이야. 사용자의 감정을 존중하고, 공감적 질문을 통해 "
    "사용자가 스스로 감정을 탐색하도록 돕는다."
)
FALLBACK_TASK_PROMPT = (
    "You recommend 1-5 small, concrete tasks that fit the user's current emotional context. "
    "Keep each task gentle, specific, realistic, and safe to start immediately. "
    "Avoid anything medical, dangerous, shaming, or overly demanding."
)


def get_file_prompt(prompt_type: str) -> str:
    if prompt_type == "task":
        return read_prompt(TASK_PROMPT_PATH, FALLBACK_TASK_PROMPT)
    return read_prompt(PROMPT_PATH, FALLBACK_PROMPT)


def get_db_override(prompt_type: str) -> Optional[str]:
    """테스트 런타임에서만 /prompts API로 저장한 최신 프롬프트를 돌려준다.

    운영 서버는 DB를 공유하더라도 항상 None — 파일 프롬프트만 쓴다.
    최신 revision이 초기화(content=NULL)이거나 DB 조회가 실패하면 None.
    """
    if not is_test_runtime():
        return None
    try:
        with session_scope() as db:
            row = db.exec(
                select(PromptRevision)
                .where(PromptRevision.prompt_type == prompt_type)
                .order_by(PromptRevision.revision_id.desc())
                .limit(1)
            ).first()
            return row.content if row else None
    except Exception:
        logger.exception("[PromptLoader] %s prompt override load failed. Using file.", prompt_type)
        return None


# 프롬프트 저장 시 /prompts 라우터가 cache_clear()로 즉시 반영한다.
@lru_cache(maxsize=1)
def get_system_prompt() -> str:
    return get_db_override("system") or get_file_prompt("system")


@lru_cache(maxsize=1)
def get_task_prompt() -> str:
    return get_db_override("task") or get_file_prompt("task")
