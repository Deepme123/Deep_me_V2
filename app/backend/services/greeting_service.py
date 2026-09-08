from __future__ import annotations

import random

from sqlmodel import Session, select

from app.backend.core.greeting_loader import get_greeting_messages
from app.backend.models.greeting_message import GreetingMessageStat


def _pick_index(db: Session, candidate_indices: list[int]) -> int:
    if len(candidate_indices) == 1:
        return candidate_indices[0]

    i, j = random.sample(candidate_indices, 2)
    counts = {
        stat.message_index: stat.selected_count
        for stat in db.exec(
            select(GreetingMessageStat).where(GreetingMessageStat.message_index.in_([i, j]))
        )
    }
    count_i = counts.get(i, 0)
    count_j = counts.get(j, 0)

    if count_i == count_j:
        return random.choice([i, j])
    return i if count_i < count_j else j


def _increment_count(db: Session, index: int) -> None:
    stat = db.get(GreetingMessageStat, index)
    if stat is None:
        stat = GreetingMessageStat(message_index=index, selected_count=0)
    stat.selected_count += 1
    db.add(stat)
    db.commit()


def pick_greeting_message(db: Session) -> tuple[int, str]:
    """두 개를 무작위로 뽑아 선택 횟수가 적은 쪽을 고르는 방식(power-of-two-choices)으로
    인사 문구 하나를 선택하고, 선택된 문구의 카운터를 1 증가시킨다.
    """
    messages = get_greeting_messages()
    index = _pick_index(db, list(range(len(messages))))
    _increment_count(db, index)
    return index, messages[index]
