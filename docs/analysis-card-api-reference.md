# 분석카드 관련 API

## 분석카드 REST API

### `POST /analyze/api/sessions`

분석카드용 세션을 생성한다.

### `POST /analyze/api/sessions/{session_id}/cards`

분석카드를 직접 생성한다.

클라이언트가 카드 내용을 직접 만들어 서버에 저장하는 방식이다.

### `POST /analyze/api/sessions/{session_id}/cards/auto`

대화 로그를 직접 넘겨서 분석카드를 자동 생성한다.

클라이언트가 `conversation_log` 를 보내면 서버가 이를 바탕으로 카드를 생성해
저장한다.

### `POST /analyze/api/sessions/{session_id}/cards/auto-from-session`

저장된 세션 transcript를 읽어서 분석카드를 자동 생성한다.

현재 분석카드 자동 생성의 핵심 API이며, 서버가 `EmotionStep` 기록을 읽어
분석카드를 생성하고 저장한다.

### `GET /analyze/api/sessions/{session_id}/cards`

해당 세션의 분석카드 목록을 조회한다.

### `GET /analyze/api/cards/{card_id}`

분석카드 한 건을 조회한다.

## 분석카드 생성과 연결되는 WebSocket API

### `WS /ws/emotion`

감정 대화용 WebSocket 경로다.

이 경로에서는 대화를 통해 transcript를 쌓고, 세션 종료 시점에 분석카드 생성이
연결된다.

### `type: "message"`

유저 메시지를 보내는 이벤트다.

서버는 유저/어시스턴트 대화를 transcript로 저장하고, 이 기록이 이후
분석카드 생성 입력으로 사용된다.

### `type: "close"`

세션을 수동 종료하는 이벤트다.

현재 구현에서는 세션만 종료하고, 분석카드 자동 생성은 트리거하지 않는다.

### `type: "confirm_close"`

세션 종료를 확정하는 이벤트다.

현재 구현에서는 세션 종료 후 분석카드 자동 생성을 함께 트리거한다.

## 분석카드 관련 WebSocket 응답 이벤트

### `type: "close_ok"`

세션 종료가 정상 반영되었음을 의미한다.

### `type: "analysis_card_ready"`

분석카드 생성이 완료되었음을 의미한다.

응답 payload 안에 생성된 카드 데이터가 함께 포함된다.

### `type: "analysis_card_failed"`

세션 종료 후 분석카드 생성에 실패했음을 의미한다.
