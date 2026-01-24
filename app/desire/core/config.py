import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

# 현재 파일: app/core/config.py
BASE_DIR = Path(__file__).resolve().parent.parent  # .../app
ROOT_DIR = BASE_DIR.parent                         # .../deepme_desire 또는 DEEPME_DESIRE

# 두 위치 모두에서 .env 로드 시도
load_dotenv(ROOT_DIR / ".env")
load_dotenv(BASE_DIR / ".env")


class Settings(BaseModel):
    """
    👉 지금은 서버를 빨리 띄우는 게 목표라서
    OPENAI_API_KEY가 비어 있어도 그냥 넘어가도록 한다.
    나중에 LLM 실제 연동할 때 다시 검증 로직 넣으면 됨.
    """
    openai_api_key: str = "dummy-key"
    openai_model: str = "gpt-4.1-mini"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY", "dummy-key"),
            openai_model=os.getenv("NEED_CARD_MODEL", "gpt-4.1-mini"),
        )


settings = Settings.from_env()
