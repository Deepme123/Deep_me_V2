from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _disable_rate_limit_by_default(monkeypatch):
    # 테스트 환경에서는 기본적으로 Rate Limiting 비활성화
    # rate_limit.py를 import하기 전에 설정해야 함
    monkeypatch.setenv("RATELIMIT_ENABLED", "false")


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


@pytest.fixture
def add_analysis_card():
    """AnalysisCard row를 만들어 커밋하는 팩토리. fields를 안 넘기면
    콘텐츠 필드가 모두 None인 빈 카드가 생성된다."""

    def _add(db, session_id, **fields):
        from app.analyze.models import AnalysisCard

        card = AnalysisCard(session_id=session_id, **fields)
        db.add(card)
        db.commit()
        db.refresh(card)
        return card

    return _add
