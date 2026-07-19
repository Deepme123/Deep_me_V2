from pathlib import Path
import logging
from functools import lru_cache

BASE_DIR = Path(__file__).resolve().parent.parent
_CWD_BASE_DIR = Path.cwd() / "app" / "desire"

_DEFAULT_SYSTEM_PROMPT_PATH = BASE_DIR / "resources" / "reflection_system_prompt.txt"
_CWD_SYSTEM_PROMPT_PATH = _CWD_BASE_DIR / "resources" / "reflection_system_prompt.txt"
SYSTEM_PROMPT_PATH = (
    _DEFAULT_SYSTEM_PROMPT_PATH if _DEFAULT_SYSTEM_PROMPT_PATH.exists() else _CWD_SYSTEM_PROMPT_PATH
)

_DEFAULT_USER_PROMPT_PATH = BASE_DIR / "resources" / "reflection_user_prompt.txt"
_CWD_USER_PROMPT_PATH = _CWD_BASE_DIR / "resources" / "reflection_user_prompt.txt"
USER_PROMPT_PATH = (
    _DEFAULT_USER_PROMPT_PATH if _DEFAULT_USER_PROMPT_PATH.exists() else _CWD_USER_PROMPT_PATH
)

FALLBACK_SYSTEM_PROMPT = (
    "사용자에게 2인칭 반말, 추측형 어미로 위로하듯 이야기하며, 이번 대화에서 드러난 "
    "상황과 감정에 근거해 욕구마다 2개 단락으로 서술한다."
)
FALLBACK_USER_PROMPT_TEMPLATE = (
    "욕구 후보: {desire_list}\n이번 대화 요약: {conversation_summary}\n감정 키워드: {emotion_keywords}"
)


def _load_prompt(path: Path, fallback: str, label: str) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        logging.warning("[PromptLoader] %s not found. Using fallback.", label)
        return fallback


@lru_cache(maxsize=1)
def get_reflection_system_prompt() -> str:
    return _load_prompt(SYSTEM_PROMPT_PATH, FALLBACK_SYSTEM_PROMPT, "reflection_system_prompt.txt")


@lru_cache(maxsize=1)
def get_reflection_user_prompt_template() -> str:
    return _load_prompt(USER_PROMPT_PATH, FALLBACK_USER_PROMPT_TEMPLATE, "reflection_user_prompt.txt")
