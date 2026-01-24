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
    bag = " ".join(
        str(payload.get(k) or "") for k in
        ("summary","emotion","thoughts","physical_reactions","behaviors")
    )
    level = score(bag)
    return (level in {"LOW","MEDIUM","HIGH"}, level if level!="NONE" else None)
