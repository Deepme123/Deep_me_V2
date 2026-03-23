# app/config.py
from pydantic import Field
from pydantic_settings import BaseSettings

from app.core.llm_settings import get_llm_settings


class Settings(BaseSettings):
    app_env: str = Field("local", alias="APP_ENV")
    database_url: str = Field(..., alias="DATABASE_URL")
    llm_provider: str = "openai"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 800
    llm_timeout_sec: float = 60.0

    class Config:
        env_file = ".env"
        extra = "ignore"


def _build_settings() -> Settings:
    base = Settings()
    llm = get_llm_settings(
        model_default=base.llm_model,
        temperature_default=base.llm_temperature,
        max_tokens_default=base.llm_max_tokens,
        timeout_default=base.llm_timeout_sec,
    )
    return base.model_copy(
        update={
            "llm_provider": llm.provider,
            "openai_api_key": llm.openai_api_key,
            "anthropic_api_key": llm.anthropic_api_key,
            "llm_model": llm.model,
            "llm_temperature": llm.temperature,
            "llm_max_tokens": llm.max_tokens,
            "llm_timeout_sec": llm.timeout_sec,
        }
    )


settings = _build_settings()
