# app/schemas/emotion.py
from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EmotionSessionCreate(BaseModel):
    user_id: Optional[UUID] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    emotion_label: Optional[str] = None
    topic: Optional[str] = None
    trigger_summary: Optional[str] = None
    insight_summary: Optional[str] = None


class EmotionSessionRead(BaseModel):
    session_id: UUID
    user_id: UUID
    started_at: datetime
    ended_at: Optional[datetime]
    emotion_label: Optional[str]
    topic: Optional[str]
    trigger_summary: Optional[str]
    insight_summary: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class EmotionStepCreate(BaseModel):
    session_id: UUID
    step_order: int
    step_type: str
    user_input: str
    gpt_response: str
    created_at: Optional[datetime] = None
    insight_tag: Optional[str] = None


class EmotionStepRead(BaseModel):
    step_id: UUID
    session_id: UUID
    step_order: int
    step_type: str
    user_input: str
    gpt_response: str
    created_at: datetime
    insight_tag: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class EmotionStepGenerateInput(BaseModel):
    session_id: Optional[UUID] = None      # ?ЖьЬ╝ый??РыПЩ ?ЭьД▒
    user_id: Optional[UUID] = None         # ???╕ьЕШ???ДьИШ
    step_type: str
    user_input: str
    temperature: Optional[float] = 0.72
    max_completion_tokens: Optional[int] = 500
    insight_tag: Optional[str] = None
    system_prompt: Optional[str] = None


class EmotionOpenRequest(BaseModel):
    type: Literal["open"] = "open"
    access_token: Optional[str] = None


class EmotionMessageRequest(BaseModel):
    type: Literal["message"] = "message"
    text: str


class EmotionCloseRequest(BaseModel):
    # Legacy/session-finalize payload. Do not use for yes/no close intent.
    type: Literal["close"] = "close"
    emotion_label: Optional[str] = None
    topic: Optional[str] = None
    trigger_summary: Optional[str] = None
    insight_summary: Optional[str] = None


class ConfirmCloseRequest(BaseModel):
    # Explicit user confirmation for the server's close suggestion.
    type: Literal["confirm_close"] = "confirm_close"


class CancelCloseRequest(BaseModel):
    # User declines the current close suggestion and keeps the session open.
    type: Literal["cancel_close"] = "cancel_close"


class TaskRecommendRequest(BaseModel):
    type: Literal["task_recommend"] = "task_recommend"
    max_items: Optional[int] = 5


class EmotionOpenResponse(BaseModel):
    type: Literal["open_ok"] = "open_ok"
    session_id: UUID
    turns: int


class EmotionMessageResponse(BaseModel):
    type: str
    delta: Optional[str] = None
    message: Optional[str] = None


class EmotionCloseResponse(BaseModel):
    # Final close acknowledgement after the session close has been persisted.
    type: Literal["close_ok"] = "close_ok"


class SuggestCloseResponse(BaseModel):
    # Server asks the client to confirm whether the session should close now.
    type: Literal["suggest_close"] = "suggest_close"


class AnalysisCardStatusResponse(BaseModel):
    type: Literal["analysis_card_status"] = "analysis_card_status"
    session_id: UUID
    status: Literal["pending", "ready", "failed"]
    card_id: Optional[UUID] = None
    message: Optional[str] = None


class TaskRecommendResponse(BaseModel):
    type: Literal["task_recommend_ok"] = "task_recommend_ok"
    items: List[dict]
