"""노아 답 다듬기(데모 1.2 ⑤) — 스트리밍 청크 단위로 안전하게 적용되는 규칙만.

노아 답은 클라이언트로 바로 스트리밍되므로, 이미 보낸 문장을 다시 쓰는 처리
("~해서가 아니라 ~야" 고쳐 말하기, 둘 중 고르기 질문 고쳐 쓰기)는 여기서 하지 않는다.
여기서는 앞 글자만 기억하면 되는 정리만 한다.
- 이모지: 메모가 권한 만큼만 남긴다(기본 0개, "이모지 하나" 턴엔 1개).
- 쉼표: 연달아 찍힌 쉼표(",," / ", ,")를 하나로, 쉼표 앞 공백 제거.
"""
from __future__ import annotations

import re

# 이모지 본체 + 뒤따르는 변이 선택자/ZWJ 결합 시퀀스.
_EMOJI = (
    r"(?:[\U0001F000-\U0001FAFF☀-➿⬀-⯿㊗㊙]"
    r"️?(?:‍[\U0001F000-\U0001FAFF☀-➿]️?)*)"
)
_EMOJI_RE = re.compile(_EMOJI)
_SPACE_BEFORE_COMMA_RE = re.compile(r"[ \t]+,")
_MULTI_COMMA_RE = re.compile(r",(?:[ \t]*,)+")
_MULTI_SPACE_RE = re.compile(r"[ \t]{2,}")


class ReplyPolisher:
    def __init__(self, *, max_emoji: int = 0) -> None:
        self._max_emoji = max(0, max_emoji)
        self._emoji_seen = 0
        self._last = ""  # 직전에 내보낸 마지막 글자(청크 경계 처리용)

    def _emoji_sub(self, match: re.Match[str]) -> str:
        self._emoji_seen += 1
        return match.group(0) if self._emoji_seen <= self._max_emoji else ""

    def feed(self, text: str) -> str:
        if not text:
            return ""
        out = _EMOJI_RE.sub(self._emoji_sub, text)
        out = _MULTI_COMMA_RE.sub(",", out)
        out = _SPACE_BEFORE_COMMA_RE.sub(",", out)
        out = _MULTI_SPACE_RE.sub(" ", out)
        # 청크 경계: 앞 청크가 쉼표/공백으로 끝났으면 이어지는 쉼표/공백 하나를 정리
        if self._last == "," and out.lstrip(" \t").startswith(","):
            out = out.lstrip(" \t")[1:]
        elif self._last in (" ", "\t") and out[:1] in (" ", "\t"):
            out = out.lstrip(" \t")
        if out:
            self._last = out[-1]
        return out
