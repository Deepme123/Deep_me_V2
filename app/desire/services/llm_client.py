from openai import OpenAI

from app.desire.core.config import settings

# 전역 OpenAI 클라이언트 (기존 프로젝트에 합칠 때도 그대로 재사용 가능)
client = OpenAI(api_key=settings.openai_api_key)


def get_model_name() -> str:
    return settings.openai_model
