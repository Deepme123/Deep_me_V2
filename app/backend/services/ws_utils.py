from __future__ import annotations

import os
import re
from typing import Iterable
from uuid import UUID

from app.backend.models.emotion import EmotionStep


def safe_str(value: object) -> str:
    try:
        return str(value)
    except Exception:
        return repr(value)


def mask_preview(text: str, limit: int = 80) -> str:
    flattened = text.replace("\n", " ")
    if len(flattened) > limit:
        return f"{flattened[:limit]}.."
    return flattened


def ensure_uuid(value: str | UUID | None) -> UUID | None:
    if value is None:
        return None
    return UUID(str(value))


def transcript_rows_to_conversation(
    transcript_rows: Iterable[EmotionStep],
) -> list[tuple[str, str]]:
    conversation: list[tuple[str, str]] = []
    for row in transcript_rows:
        if row.step_type == "user" and row.user_input:
            conversation.append(("user", row.user_input))
        elif row.step_type == "assistant" and row.gpt_response:
            conversation.append(("assistant", row.gpt_response))
    return conversation


class LeakGuard:
    _DEFAULT_MARKERS = [
        r"<<SYS>>",
        r"\bBEGIN SYSTEM PROMPT\b",
        r"\[\s*SYSTEM\s*\]",
        r"\bDO NOT DISCLOSE\b",
        r"\bdeveloper prompt\b",
    ]

    def __init__(self) -> None:
        self.markers: list[str] = list(self._DEFAULT_MARKERS)
        self.ngram: int = int(os.getenv("LEAK_GUARD_NGRAM", "20"))
        self.min_match: int = int(os.getenv("LEAK_GUARD_MIN_MATCH", "3"))
        self.mode: str = os.getenv("LEAK_GUARD_MODE", "mask")

    def fingerprint(self, text: str, n: int | None = None) -> set[int]:
        n = self.ngram if n is None else n
        if not text:
            return set()
        step = max(3, n // 2)
        return {hash(text[i : i + n]) for i in range(0, max(0, len(text) - n + 1), step)}

    def _might_leak(self, text: str, sys_fp: set[int], n: int | None = None) -> bool:
        n = self.ngram if n is None else n
        if not text or not sys_fp:
            return False
        step = max(3, n // 2)
        fp = {hash(text[i : i + n]) for i in range(0, max(0, len(text) - n + 1), step)}
        return len(sys_fp & fp) >= self.min_match

    def _redact(self, text: str) -> str:
        output = text
        for pattern in self.markers:
            output = re.sub(pattern, "[redacted]", output, flags=re.I)
        return output

    def sanitize_out(self, piece: str, sys_fp: set[int]) -> str:
        if not isinstance(piece, str) or not piece:
            return ""
        if self._might_leak(piece, sys_fp):
            if self.mode == "drop":
                return ""
            return self._redact(piece)
        return self._redact(piece)
