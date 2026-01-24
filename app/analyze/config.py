# app/config.py
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # 기본 앱 설정
    app_env: str = Field("local", alias="APP_ENV")

    # DB
    database_url: str = Field(..., alias="DATABASE_URL")

    # LLM / OpenAI 설정
    openai_api_key: str = Field("", alias="OPENAI_API_KEY")
    llm_model: str = Field("gpt-4o-mini", alias="LLM_MODEL")
    llm_temperature: float = Field(0.7, alias="LLM_TEMPERATURE")
    llm_max_tokens: int = Field(800, alias="LLM_MAX_TOKENS")

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
