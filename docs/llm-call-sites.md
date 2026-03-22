# WebSocket Close Flow And Analysis Card Trigger Path

이 문서는 `app/backend/routers/emotion_ws.py` 기준으로, 감정 대화 WebSocket의 종료 확인 흐름과 종료 후 분석 카드 생성 경로를 코드 추적 없이 이해할 수 있도록 정리한 운영/유지보수 메모다.

## 1. 관련 진입점

- WebSocket 진입점: `app/backend/routers/emotion_ws.py`
- 종료 판단 규칙: `app/backend/services/step_manager.py`
- 세션 기반 카드 생성 API 로직: `app/analyze/routers/cards.py`
- 실제 카드 분석 LLM 호출: `app/analyze/services/llm_card.py`

핵심은 다음 두 갈래다.

1. 대화 중 종료를 권유할지 판단하는 흐름
2. 사용자가 종료를 확정했을 때 세션 종료와 분석 카드 생성을 연결하는 흐름

## 2. 종료 확인 플로우 개요

기본 원칙:

- `soft close`는 권유 상태다. 세션을 실제로 끝내지 않는다.
- 세션 종료는 `close` 또는 `confirm_close`를 받았을 때만 확정된다.
- `confirm_close`는 `close_ok` 이후 분석 카드 생성까지 이어진다.

고수준 순서:

1. 사용자가 `message`를 보낸다.
2. 서버가 대화 단계와 응답 내용을 바탕으로 종료 권유 여부를 계산한다.
3. 종료 권유 조건이면 `suggest_close` 이벤트를 보낸다.
4. 사용자가 `confirm_close`를 보내면 세션 종료를 DB에 반영한다.
5. 서버가 `close_ok`를 보낸다.
6. 같은 세션 ID로 분석 카드 자동 생성을 호출한다.
7. 성공 시 `analysis_card_ready`, 실패 시 `analysis_card_failed`를 추가로 보낸다.

## 3. Soft Trigger / Hard Trigger 설명

### Soft trigger

`soft trigger`는 "이제 마무리를 제안할 수 있다"는 의미다. 즉시 종료가 아니라 종료 확인 단계 진입이다.

발생 조건:

- `step_manager.is_soft_close_trigger(current_step, end_by_token)`가 `True`
- 내부적으로는 아래 둘 중 하나다.
  - 현재 대화 단계가 최대 단계 이상
  - LLM 응답에 종료 토큰이 포함되어 `end_by_token=True`

동작:

- `emotion_ws.py`에서 `soft_close_triggered`를 계산한다.
- true이면 assistant 메시지를 고정 작별문(`build_fixed_farewell()`)으로 치환한다.
- 이후 `suggest_close` 이벤트를 보낸다.
- `awaiting_close_confirmation = True`로 바꿔 다음 입력을 종료 확인 모드로 받는다.

의미:

- 사용자는 아직 세션 안에 있다.
- 이 시점에서는 카드 생성도, 세션 종료도 아직 일어나지 않는다.

### Hard trigger

운영 문서 관점에서의 `hard trigger`는 실제 종료를 확정하는 클라이언트 액션이다.

해당 입력:

- `confirm_close`
- `close`

차이:

- `close`: 세션 종료만 수행한다.
- `confirm_close`: 세션 종료 후 분석 카드 생성까지 이어진다.

즉, 현재 구현에서 카드 생성 트리거는 `confirm_close` 경로에만 연결되어 있다.

## 4. 상세 흐름: 대화 중 종료 제안

`message` 처리 중 관련 순서는 다음과 같다.

1. `_prepare_message_context(...)`
   - 현재 step, 이전 steps, prompt context를 계산한다.
2. `stream_noa_response(...)`
   - 실제 대화 LLM 스트리밍 호출
3. `extract_end_session_marker(...)`
   - 응답 안의 종료 토큰을 제거하고 종료 의도를 추출한다.
4. `is_soft_close_trigger(...)`
   - soft trigger 여부를 판정한다.
5. `should_suggest_close(...)`
   - cooldown 상태까지 반영해 실제 권유 이벤트를 보낼지 최종 결정한다.

중요 상태 변수:

- `awaiting_close_confirmation`
  - 종료 권유를 이미 보낸 뒤, 다음 사용자 액션이 `confirm_close` / `cancel_close` / 일반 `message` 중 무엇인지 구분하는 플래그
- `CANCEL_CLOSE_STEP_TYPE`
  - 사용자가 종료를 취소했을 때 step marker로 남는다.
- `is_close_suggestion_cooldown(...)`
  - 방금 취소한 직후 연속으로 다시 종료 권유하지 않도록 막는다.

## 5. 상세 흐름: confirm_close 이후 카드 생성

`emotion_ws.py`에서 `MSG_CONFIRM_CLOSE`를 받으면 다음 순서로 진행된다.

1. `EmotionCloseRequest(**msg)`로 payload 검증
2. `finalize_close(payload, trigger_analysis_card=True)` 호출
3. `_close_session_record(...)`
   - `EmotionSession.ended_at` 및 종료 관련 summary 필드 반영
4. `close_ok` 전송
5. `_generate_analysis_card_async(session_id)` 호출
6. 결과에 따라 후속 이벤트 전송

### `_generate_analysis_card_async(session_id)` 내부 경로

1. `session_scope()`로 DB 세션 오픈
2. `app.analyze.routers.cards.create_card_auto_from_session(...)` 호출
3. `create_card_auto_from_session(...)` 내부에서 세션 대화 이력 로드
4. `_analyze_and_store_card(...)` 호출
5. `analyze_dialogue_to_card(...)`에서 카드 분석용 LLM 호출
6. `_store_card(...)`로 카드 저장
7. 저장된 카드 내용을 JSON 직렬화해 WebSocket 후속 이벤트에 싣는다.

정리하면:

- 대화 LLM 호출은 `stream_noa_response(...)`
- 종료 후 카드 LLM 호출은 `analyze_dialogue_to_card(...)`
- 두 호출은 서로 다른 목적과 타이밍을 가진다.

## 6. 새 이벤트 타입 정리

현재 종료 관련 이벤트는 아래와 같다.

- `suggest_close`
  - soft trigger 후, 사용자의 종료 확정을 요청하는 안내 이벤트
- `cancel_close_ok`
  - 사용자가 종료를 취소했고 cooldown marker 저장도 성공했음을 의미
- `close_ok`
  - 세션 종료가 DB에 반영되었음을 의미
- `analysis_card_ready`
  - `confirm_close` 이후 세션 기반 분석 카드 생성이 성공했음을 의미
  - payload에 `session_id`와 `card`가 포함된다.
- `analysis_card_failed`
  - 세션 종료는 성공했지만 카드 생성 후처리가 실패했음을 의미
  - payload에 `session_id`와 실패 메시지가 포함된다.

운영 해석 기준:

- `close_ok`를 받았으면 종료는 이미 성공이다.
- 그 뒤 `analysis_card_failed`가 와도 세션 종료를 롤백하지 않는다.
- 카드 생성 실패는 후처리 실패로 분리 취급한다.

## 7. 실패 시 동작

`confirm_close` 경로에서 장애가 날 수 있는 지점은 두 개다.

### 1) 세션 종료 저장 실패

- `_close_session_record(...)`에서 예외 발생
- 서버는 `error: close_failed`를 보낸다.
- `close_ok`는 보내지지 않는다.
- 카드 생성도 시작하지 않는다.

### 2) 카드 생성 실패

- `_generate_analysis_card_async(...)` 또는 그 하위 경로에서 예외 발생
- 서버는 로그를 남긴다.
- 이미 보낸 `close_ok`는 유지된다.
- 추가로 `analysis_card_failed`를 보낸다.

이 구분이 중요한 이유는, 운영 시 "대화 종료는 성공했는데 분석 카드만 실패했다"는 상태를 별도로 판단해야 하기 때문이다.

## 8. 권장 구현 순서 요약

종료/카드 플로우를 다시 수정할 때는 아래 순서를 권장한다.

1. `step_manager.py`에서 종료 판단 규칙을 먼저 정리한다.
2. `emotion_ws.py`에서 `message -> suggest_close -> confirm_close/cancel_close` 상태 전이를 맞춘다.
3. `finalize_close(...)`에서 종료 성공과 후처리 실패를 분리된 상태로 다루도록 유지한다.
4. 카드 생성 로직은 세션 ID만 넘기고, 실제 대화 이력 조회와 분석은 `app.analyze` 쪽에 맡긴다.
5. 새 이벤트를 추가하면 WS 문서와 테스트를 동시에 갱신한다.
6. 최소한 아래 테스트는 항상 같이 본다.
   - 종료 확정 후 `close_ok`
   - 종료 확정 후 `analysis_card_ready`
   - 종료 확정 후 `analysis_card_failed`
   - `cancel_close` 이후 cooldown 동작

## 9. 운영 체크포인트

- 사용자가 종료를 확정했는데 카드가 안 보인다면:
  - 먼저 `close_ok`가 왔는지 확인
  - 이후 `analysis_card_ready` 또는 `analysis_card_failed`가 왔는지 확인
- `suggest_close`가 너무 자주 뜨면:
  - `is_soft_close_trigger(...)`
  - `is_close_suggestion_cooldown(...)`
  - `CANCEL_CLOSE_STEP_TYPE` 저장 여부를 확인
- 카드 생성이 느리면:
  - `ANALYSIS_CARD_TIMEOUT`
  - `app.analyze.services.llm_card.analyze_dialogue_to_card(...)`
  - 외부 LLM 응답 시간과 DB 저장 시간을 같이 본다.

## 10. 한 줄 요약

현재 WebSocket 종료 흐름은 `suggest_close`로 종료를 권유하고, `confirm_close`가 들어오면 `close_ok`로 세션 종료를 확정한 뒤, 같은 세션 기준으로 분석 카드를 생성해서 `analysis_card_ready` 또는 `analysis_card_failed`로 후속 상태를 알려주는 구조다.
