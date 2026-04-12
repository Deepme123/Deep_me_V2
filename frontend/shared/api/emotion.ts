import { apiRequest } from "./http";
import type { EmotionSessionRead, EmotionStepRead } from "../types/emotion";

export function listEmotionSessions(limit = 20, offset = 0) {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });

  return apiRequest<EmotionSessionRead[]>(`/emotion/sessions?${params.toString()}`);
}

export function listEmotionSteps(sessionId: string, limit = 50, offset = 0) {
  const params = new URLSearchParams({
    session_id: sessionId,
    limit: String(limit),
    offset: String(offset),
  });

  return apiRequest<EmotionStepRead[]>(`/emotion/steps?${params.toString()}`);
}

export function fetchHealth() {
  return apiRequest<{ ok: boolean }>("/health");
}
