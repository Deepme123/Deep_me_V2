from pydantic import BaseModel

from app.core.llm_settings import get_llm_settings


class Settings(BaseModel):
    llm_provider: str = "openai"
    openai_api_key: str = "dummy-key"
    anthropic_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 800
    llm_timeout_sec: float = 15.0

    @classmethod
    def from_env(cls) -> "Settings":
        llm = get_llm_settings(
            model_default="gpt-4.1-mini",
            model_legacy_names=("NEED_CARD_MODEL",),
            timeout_default=15.0,
        )
        return cls(
            llm_provider=llm.provider,
            openai_api_key=llm.openai_api_key or "dummy-key",
            anthropic_api_key=llm.anthropic_api_key,
            openai_model=llm.model,
            llm_temperature=llm.temperature,
            llm_max_tokens=llm.max_tokens,
            llm_timeout_sec=llm.timeout_sec,
        )


settings = Settings.from_env()
