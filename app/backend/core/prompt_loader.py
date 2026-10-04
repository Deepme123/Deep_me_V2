from functools import lru_cache

from app.core.resource_files import read_prompt, resolve_resource_path

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


@lru_cache(maxsize=1)
def get_system_prompt() -> str:
    return read_prompt(PROMPT_PATH, FALLBACK_PROMPT)


@lru_cache(maxsize=1)
def get_task_prompt() -> str:
    return read_prompt(TASK_PROMPT_PATH, FALLBACK_TASK_PROMPT)


SYSTEM_PROMPT = get_system_prompt()
