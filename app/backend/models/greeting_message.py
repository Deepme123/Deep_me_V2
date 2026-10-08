from sqlmodel import SQLModel, Field


class GreetingMessageStat(SQLModel, table=True):
    """app/backend/resources/greeting_messages.txt의 인사 문구별 선택 횟수 카운터.

    문구 본문은 저장하지 않는다 — message_index는 해당 파일의 순서(0-based)와 대응한다.
    """

    __tablename__ = "greetingmessagestat"

    message_index: int = Field(primary_key=True)
    selected_count: int = Field(default=0)
