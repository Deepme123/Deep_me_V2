# app/services/risk.py
from __future__ import annotations

_LOW = ["힘들", "슬픔", "우울", "불안", "짜증"]
_MEDIUM = ["죽고", "자해", "해치", "절망", "포기"]
_HIGH = ["나는 죽", "곧 끝낼", "방법을 찾았", "유서", "뛰어내"]

def score(text: str) -> str:
    t = (text or "").replace(" ", "")
    if any(k in t for k in _HIGH): return "HIGH"
    if any(k in t for k in _MEDIUM): return "MEDIUM"
    if any(k in t for k in _LOW): return "LOW"
    return "NONE"

def risk_from_payload(payload: dict) -> tuple[bool, str]:
    def _to_str(v):
        if isinstance(v, list):
            return " ".join(str(i) for i in v)
        return str(v or "")

    bag = " ".join(
        _to_str(payload.get(k)) for k in
        ("summary","situation","core_emotions","physical_reactions","coping_actions")
    )
    level = score(bag)
    return (level in {"LOW","MEDIUM","HIGH"}, level if level!="NONE" else None)
