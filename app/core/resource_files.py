from __future__ import annotations

import logging
from pathlib import Path

_APP_DIR = Path(__file__).resolve().parent.parent  # app/


def resolve_resource_path(package: str, filename: str) -> Path:
    """app/<package>/resources/<filename> 경로를 돌려준다.

    설치 위치 기준 경로에 파일이 없으면 현재 작업 디렉터리 기준 경로로 폴백한다.
    """
    default_path = _APP_DIR / package / "resources" / filename
    if default_path.exists():
        return default_path
    return Path.cwd() / "app" / package / "resources" / filename


def read_prompt(path: Path, fallback: str) -> str:
    """프롬프트 파일을 읽어 앞뒤 공백을 제거해 돌려준다. 파일이 없으면 fallback."""
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        logging.warning("[PromptLoader] %s not found. Using fallback.", path.name)
        return fallback
