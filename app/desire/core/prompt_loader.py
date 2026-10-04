from functools import lru_cache

from app.core.resource_files import read_prompt, resolve_resource_path

SYSTEM_PROMPT_PATH = resolve_resource_path("desire", "reflection_system_prompt.txt")
USER_PROMPT_PATH = resolve_resource_path("desire", "reflection_user_prompt.txt")

FALLBACK_SYSTEM_PROMPT = (
    "사용자에게 2인칭 반말, 추측형 어미로 위로하듯 이야기하며, 이번 대화에서 드러난 "
    "상황과 감정에 근거해 욕구마다 2개 단락으로 서술한다."
)
FALLBACK_USER_PROMPT_TEMPLATE = (
    "욕구 후보: {desire_list}\n이번 대화 요약: {conversation_summary}\n감정 키워드: {emotion_keywords}"
)


@lru_cache(maxsize=1)
def get_reflection_system_prompt() -> str:
    return read_prompt(SYSTEM_PROMPT_PATH, FALLBACK_SYSTEM_PROMPT)


@lru_cache(maxsize=1)
def get_reflection_user_prompt_template() -> str:
    return read_prompt(USER_PROMPT_PATH, FALLBACK_USER_PROMPT_TEMPLATE)
