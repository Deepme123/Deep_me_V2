from __future__ import annotations

import pytest

from app.analyze.services import risk


def test_score_returns_none_for_empty_or_missing_text():
    assert risk.score("") == "NONE"
    assert risk.score(None) == "NONE"
    assert risk.score("오늘은 날씨가 좋았다") == "NONE"


def test_score_detects_low_risk_keywords():
    assert risk.score("요즘 너무 힘들었어요") == "LOW"
    assert risk.score("계속 불안한 느낌이 들어요") == "LOW"


def test_score_detects_medium_risk_keywords():
    assert risk.score("자해하고 싶다는 생각이 들었어요") == "MEDIUM"
    assert risk.score("죽고 싶다는 생각을 했어요") == "MEDIUM"


def test_score_detects_high_risk_keywords_without_internal_spaces():
    # 패턴 자체에 공백이 없는 두 항목은 정상적으로 매칭된다.
    assert risk.score("유서를 써놨어요") == "HIGH"
    assert risk.score("이제 뛰어내릴 거예요") == "HIGH"


@pytest.mark.parametrize(
    "text",
    [
        "나는 죽고 싶다는 생각뿐이에요",
        "곧 끝낼 생각이에요",
        "이미 방법을 찾았어요",
    ],
)
def test_score_detects_high_risk_phrases_containing_spaces(text):
    # P0-1 회귀 테스트: _HIGH 패턴 중 공백이 포함된 항목도 정상 매칭돼야 한다.
    assert risk.score(text) == "HIGH"


def test_score_is_robust_to_extra_whitespace_in_input_for_working_patterns():
    # 입력 쪽 공백 변형은 매칭에 영향을 주지 않아야 한다 (현재 동작하는 패턴 기준).
    assert risk.score("유  서  를   써놨어요") == "HIGH"


def test_score_low_keyword_can_false_positive_on_unrelated_context():
    # "포기"는 MEDIUM 키워드인데 자살/자해와 무관한 일상적 맥락에서도 매칭된다.
    # 버그라기보단 휴리스틱의 정밀도 문제 — 회귀 확인용으로 현재 동작을 고정해 둔다.
    assert risk.score("다이어트는 포기하고 그냥 먹기로 했어요") == "MEDIUM"


def test_risk_from_payload_detects_keyword_in_scanned_fields():
    payload = {"summary": "자해 충동이 들었다", "situation": None}
    risk_flag, risk_level = risk.risk_from_payload(payload)
    assert risk_flag is True
    assert risk_level == "MEDIUM"


def test_risk_from_payload_handles_missing_keys_gracefully():
    risk_flag, risk_level = risk.risk_from_payload({})
    assert risk_flag is False
    assert risk_level is None


def test_risk_from_payload_scans_thoughts_field():
    # P0-2 회귀 테스트: thoughts 필드도 risk 스캔 대상이어야 한다.
    payload = {
        "summary": "평범한 하루였다",
        "situation": "별일 없었다",
        "thoughts": "유서를 써야겠다는 생각이 계속 들었다",
    }
    risk_flag, risk_level = risk.risk_from_payload(payload)
    assert risk_flag is True
    assert risk_level == "HIGH"


def test_risk_from_payload_scans_insight_field():
    # P0-2 회귀 테스트: insight 필드도 risk 스캔 대상이어야 한다.
    payload = {
        "summary": "평범한 하루였다",
        "insight": "자해 충동을 스스로 인지하고 있다는 점이 의미 있다",
    }
    risk_flag, risk_level = risk.risk_from_payload(payload)
    assert risk_flag is True
