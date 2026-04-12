export type EmotionSocketOutboundType =
  | "open"
  | "message"
  | "close"
  | "confirm_close"
  | "cancel_close"
  | "task_recommend";

export type EmotionSocketInboundType =
  | "open_ok"
  | "message_start"
  | "message_delta"
  | "message_end"
  | "message"
  | "suggest_close"
  | "close_ok"
  | "cancel_close_ok"
  | "analysis_card_status"
  | "analysis_card_ready"
  | "analysis_card_failed"
  | "task_recommend_ok"
  | "limit"
  | "error"
  | "ping"
  | "pong";

export interface EmotionSocketBaseMessage {
  type: string;
}

export interface EmotionSocketOpenMessage extends EmotionSocketBaseMessage {
  type: "open";
  access_token?: string;
}

export interface EmotionSocketTextMessage extends EmotionSocketBaseMessage {
  type: "message";
  text: string;
}

export interface EmotionSocketCloseMessage extends EmotionSocketBaseMessage {
  type: "close";
  emotion_label?: string;
  topic?: string;
  trigger_summary?: string;
  insight_summary?: string;
}

export interface EmotionSocketConfirmCloseMessage
  extends EmotionSocketBaseMessage {
  type: "confirm_close";
}

export interface EmotionSocketCancelCloseMessage
  extends EmotionSocketBaseMessage {
  type: "cancel_close";
}

export interface EmotionSocketTaskRecommendMessage
  extends EmotionSocketBaseMessage {
  type: "task_recommend";
  max_items?: number;
}

export type EmotionSocketOutboundMessage =
  | EmotionSocketOpenMessage
  | EmotionSocketTextMessage
  | EmotionSocketCloseMessage
  | EmotionSocketConfirmCloseMessage
  | EmotionSocketCancelCloseMessage
  | EmotionSocketTaskRecommendMessage;

export interface EmotionSocketInboundMessage extends EmotionSocketBaseMessage {
  type: EmotionSocketInboundType;
  session_id?: string;
  delta?: string;
  message?: string;
  status?: "pending" | "ready" | "failed";
  items?: Array<Record<string, unknown>>;
  [key: string]: unknown;
}

export interface EmotionSessionRead {
  session_id: string;
  user_id: string;
  started_at: string;
  ended_at: string | null;
  emotion_label: string | null;
  topic: string | null;
  trigger_summary: string | null;
  insight_summary: string | null;
}

export interface EmotionStepRead {
  step_id: string;
  session_id: string;
  step_order: number;
  step_type: string;
  user_input: string;
  gpt_response: string;
  created_at: string;
  insight_tag: string | null;
}
