from enum import Enum
from typing import Dict


class NeedCode(str, Enum):
    CHOICE = "Choice"
    SAFE = "Safe"
    TOGETHER = "Together"
    FUN = "Fun"
    MEANING = "Meaning"
    TRUE = "True"
    PEACE = "Peace"
    GROW = "Grow"


# Metadata used for UI rendering.
NEEDS_METADATA: Dict[NeedCode, Dict[str, str]] = {
    NeedCode.CHOICE: {
        "label_ko": "자율",
        "label_en": "Choice",
        "description": "스스로 선택하고 결정하며 주도권을 갖고 싶어함.",
        "icon": "choice",
    },
    NeedCode.SAFE: {
        "label_ko": "안전",
        "label_en": "Safe",
        "description": "위험과 불확실성으로부터 보호받고 안정감과 예측 가능성을 추구함.",
        "icon": "safe",
    },
    NeedCode.TOGETHER: {
        "label_ko": "소속감",
        "label_en": "Together",
        "description": "함께하고 연결되고 싶어 하며 공동체 속에서 지지받고 싶어함.",
        "icon": "together",
    },
    NeedCode.FUN: {
        "label_ko": "재미",
        "label_en": "Fun",
        "description": "가볍고 유쾌한 즐거움, 놀이나 웃음을 통해 기쁨을 찾음.",
        "icon": "fun",
    },
    NeedCode.MEANING: {
        "label_ko": "의미",
        "label_en": "Meaning",
        "description": "행동과 노력이 가치 있고 의미 있다고 느끼고 싶음.",
        "icon": "meaning",
    },
    NeedCode.TRUE: {
        "label_ko": "진정성",
        "label_en": "True",
        "description": "솔직하고 꾸밈없는 사실과 진실을 드러내고 인정받고 싶음.",
        "icon": "true",
    },
    NeedCode.PEACE: {
        "label_ko": "평온",
        "label_en": "Peace",
        "description": "갈등과 긴장을 줄이고 휴식과 마음의 평화를 추구함.",
        "icon": "peace",
    },
    NeedCode.GROW: {
        "label_ko": "성장",
        "label_en": "Grow",
        "description": "도전과 배움을 통해 발전하고 잠재력을 실현하고 싶음.",
        "icon": "grow",
    },
}
