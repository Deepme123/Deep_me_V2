# LLM Call Sites And Migration Constraints

## 목적
- 현재 OpenAI 직접 호출 지점과 호출 형태를 코드 기준으로 고정한다.
- 설정 분산 위치와 마이그레이션 제약을 먼저 문서화해 구현 범위를 잠근다.
- 이 문서는 동작 변경 없이 현 상태를 설명한다.

## 범위
- 대상 파일
  - `app/backend/services/llm_service.py`
  - `app/backend/services/task_recommend.py`
  - `app/backend/routers/task.py`
  - `app/analyze/services/llm_card.py`
  - `app/desire/services/need_analyzer.py`
- 보조 확인 파일
  - `app/desire/services/llm_client.py`
  - `app/analyze/config.py`
  - `app/desire/core/config.py`

## 현재 OpenAI 직접 호출 지점

| 파일 | OpenAI API 형태 | 입력 형태 | 출력 처리 | DB 영향 |
| --- | --- | --- | --- | --- |
| `app/backend/services/llm_service.py` | `responses.stream` 우선, 실패 시 `chat.completions.create(stream=True)` 폴백 | `system_prompt`, `task_prompt`, 대화 이력 튜플 리스트 | 스트리밍 델타를 이어 붙여 상위 계층이 최종 문자열 구성 | 없음 |
| `app/backend/services/task_recommend.py` | `chat.completions.create` | 세션 메타데이터 + 최근 대화 요약 + JSON 배열 강제 프롬프트 | JSON 배열 파싱 후 `Task` 생성 | `Task` insert |
| `app/backend/routers/task.py` | `chat.completions.create` | 단일 추천 프롬프트 또는 세션 기반 JSON 배열 프롬프트 | `/gpt`는 정규식 파싱, `/gpt/by-session`은 JSON 배열 파싱 | `Task` insert |
| `app/analyze/services/llm_card.py` | `chat.completions.create` | 대화 로그를 문자열로 합친 단일 프롬프트 | 단일 JSON 객체를 `CardCreate`로 변환 | 서비스 자체는 없음, 상위 라우터가 `EmotionCard` insert |
| `app/desire/services/need_analyzer.py` | `responses.create` | 시스템 프롬프트 + 대화 전문 + strict JSON schema | 응답 텍스트 추출 후 Pydantic 검증, 실패 시 기본값 폴백 | 없음 |

## 파일별 상세

### 1. `app/backend/services/llm_service.py`
- 역할
  - 감정 대화 응답 생성의 공용 서비스다.
  - 상위 호출자는 일반 REST 라우터와 WebSocket 라우터다.
- 호출 형태
  - 모델명이 `gpt-5*`, `o4*`, `o3*`로 시작하면 `client.responses.stream(...)`을 사용한다.
  - 그 외 또는 Responses 경로 실패 시 `client.chat.completions.create(..., stream=True)`로 폴백한다.
- 입력 계약
  - `system_prompt`
  - 선택적 `task_prompt`
  - `conversation: list[tuple[str, str]]`
  - 선택적 `temperature`, `max_tokens`, `model`
- 출력 계약
  - `stream_noa_response(...)`는 `Generator[str, None, None]`를 반환한다.
  - `generate_noa_response(...)`는 위 제너레이터를 모두 모아 최종 문자열을 반환한다.
- 설정 읽기 방식
  - 모듈 import 시점에 `os.getenv(...)`로 읽는다.
  - 사용 키
    - `LLM_MODEL` 기본값 `gpt-4o-mini`
    - `LLM_TIMEOUT_SEC` 기본값 `60`
    - `LLM_BACKUP_MODELS` 기본값 `gpt-4o-mini,gpt-4o`
- 특징
  - `OpenAI(timeout=TIMEOUT)`만 사용하며 `OPENAI_BASE_URL`, `OPENAI_ORG_ID`, `OPENAI_PROJECT`는 여기서 직접 반영하지 않는다.
  - 서비스 자체는 DB를 읽거나 쓰지 않는다.
- 상위 연결
  - `app/backend/routers/emotion.py`
  - `app/backend/routers/emotion_ws.py`

### 2. `app/backend/services/task_recommend.py`
- 역할
  - 감정 세션 대화 이력을 바탕으로 추천 할 일을 생성하고 즉시 DB에 저장한다.
- 호출 형태
  - `client.chat.completions.create(...)`
  - 비스트리밍 단건 호출이다.
- 입력 구성
  - `EmotionSession`의 `emotion_label`, `topic`
  - 최근 `EmotionStep` 이력
  - 시스템 프롬프트 `get_task_prompt()`
  - JSON 배열 강제 정책 문자열
- 출력 처리
  - 응답 본문을 JSON 배열로 파싱한다.
  - 코드 펜스 제거를 한 번 더 시도한다.
  - 각 항목의 `title`, `description`으로 `Task`를 생성한다.
- 설정 읽기 방식
  - 함수 호출 시점마다 `os.getenv(...)`로 읽는다.
  - 사용 키
    - `LLM_MODEL` 기본값 `gpt-3.5-turbo`
    - `LLM_TEMPERATURE` 기본값 `0.7`
    - `LLM_MAX_TOKENS` 기본값 `800`
    - `OPENAI_BASE_URL`
    - `OPENAI_ORG_ID`
    - `OPENAI_PROJECT`
- DB 영향
  - 읽기: `EmotionSession`, `EmotionStep`
  - 쓰기: `Task`
  - 저장 필드: `user_id`, `title`, `description`
- 상위 연결
  - `app/backend/routers/emotion_ws.py`에서 추천 액션이 필요할 때 호출한다.

### 3. `app/backend/routers/task.py`
- 역할
  - Task CRUD 라우터이면서 LLM 기반 추천 엔드포인트를 직접 보유한다.
- 직접 호출 지점
  - `/tasks/gpt`
  - `/tasks/gpt/by-session`
- 호출 형태
  - 두 엔드포인트 모두 `client.chat.completions.create(...)`를 직접 호출한다.
  - 클라이언트/모델/파라미터 조합은 내부 헬퍼 `_get_openai_client_and_params()`에 중복 구현되어 있다.
- 출력 처리 차이
  - `/tasks/gpt`
    - 자유 형식 텍스트를 받는다.
    - 정규식으로 `제목/설명` 패턴을 파싱한다.
  - `/tasks/gpt/by-session`
    - `task_recommend.py`와 유사한 JSON 배열 정책을 사용한다.
    - JSON 배열 파싱 후 `Task`를 저장한다.
- 설정 읽기 방식
  - 함수 호출 시점마다 `os.getenv(...)`로 읽는다.
  - 사용 키
    - `LLM_MODEL` 기본값 `gpt-3.5-turbo`
    - `LLM_TEMPERATURE` 기본값 `0.7`
    - `LLM_MAX_TOKENS` 기본값 `800`
    - `OPENAI_BASE_URL`
    - `OPENAI_ORG_ID`
    - `OPENAI_PROJECT`
- DB 영향
  - 읽기: `/gpt/by-session`에서 `EmotionSession`, `EmotionStep`
  - 쓰기: 두 엔드포인트 모두 `Task`
- 현재 상태 메모
  - 세션 기반 추천 로직이 `task_recommend.py`와 중복되어 있어 이후 마이그레이션 시 가장 먼저 범위 정리가 필요한 영역이다.

### 4. `app/analyze/services/llm_card.py`
- 역할
  - 대화 로그를 분석해 카드 생성용 `CardCreate` payload를 만든다.
- 호출 형태
  - `client.chat.completions.create(...)`
  - 비스트리밍 단건 호출이다.
- 입력 구성
  - 대화 로그를 `_format_dialogue(...)`로 문자열화한다.
  - 시스템 프롬프트 `_SYSTEM_PROMPT`
  - 사용자 프롬프트에 `title_hint`를 선택적으로 추가한다.
- 출력 처리
  - 응답 본문을 단일 JSON 객체로 바로 `json.loads(...)` 한다.
  - JSON 파싱 성공 후 `sc.CardCreate`로 매핑한다.
  - 코드 펜스 제거 같은 완충 로직은 없다.
- 설정 읽기 방식
  - `app/analyze/config.py`의 `settings`를 사용한다.
  - 사용 키
    - `OPENAI_API_KEY`
    - `LLM_MODEL` 기본값 `gpt-4o-mini`
    - `LLM_TEMPERATURE` 기본값 `0.7`
    - `LLM_MAX_TOKENS` 기본값 `800`
- DB 영향
  - 서비스 함수 자체는 DB를 건드리지 않는다.
  - 상위 `app/analyze/routers/cards.py`의 `/sessions/{session_id}/cards/auto`가 결과를 `EmotionCard`로 저장한다.

### 5. `app/desire/services/need_analyzer.py`
- 역할
  - 대화 전문에서 8개 need score를 추론한다.
- 호출 형태
  - `client.responses.create(...)`
  - 비스트리밍 단건 호출이다.
  - `response_format`에 strict JSON schema를 넘긴다.
- 입력 구성
  - `SYSTEM_PROMPT`
  - `USER_PROMPT_TEMPLATE.format(conversation_text=...)`
  - 고정 파라미터
    - `temperature=0.1`
    - `max_output_tokens=800`
    - `timeout=15`
- 출력 처리
  - `response.output_text` 우선
  - 없으면 `choices[0].message.content` 또는 `response.output[*].content[*].text`에서 텍스트를 추출한다.
  - 이후 JSON 파싱과 `LLMNeedResponse` 검증을 거친다.
  - 실패 시 예외를 올리고, 상위 `analyze_needs(...)`가 기본 점수로 폴백한다.
- 설정 읽기 방식
  - 실제 OpenAI client/model은 `app/desire/services/llm_client.py`를 통해 주입된다.
  - `llm_client.py`는 import 시점에 전역 `client = OpenAI(api_key=settings.openai_api_key)`를 만든다.
  - 모델명은 `get_model_name()`으로 조회한다.
- 관련 설정 키
  - `OPENAI_API_KEY`
  - `NEED_CARD_MODEL` 기본값 `gpt-4.1-mini`
- DB 영향
  - 없음
- 상위 연결
  - `app/desire/routers/need_card.py`의 `/need-cards/analyze`

## 설정 분산 위치

### 분산된 설정 소스
- `app/backend/services/llm_service.py`
  - `os.getenv(...)` 직접 사용
  - 모듈 import 시점 고정
- `app/backend/services/task_recommend.py`
  - `os.getenv(...)` 직접 사용
  - 함수 호출 시점 해석
- `app/backend/routers/task.py`
  - `os.getenv(...)` 직접 사용
  - 함수 호출 시점 해석
- `app/analyze/config.py`
  - `pydantic_settings.BaseSettings`
  - `.env` 기반 alias 매핑 사용
- `app/desire/core/config.py`
  - `dotenv + BaseModel`
  - 루트 `.env`와 `app/.env`를 둘 다 로드 시도
  - 모델 키가 `LLM_MODEL`이 아니라 `NEED_CARD_MODEL`

### 현재 분산으로 인해 고정해야 할 사실
- 동일한 OpenAI 연동이어도 설정 소스와 기본 모델이 다르다.
- `backend` 영역과 `analyze` 영역은 `LLM_MODEL` 계열을 사용한다.
- `desire` 영역은 `NEED_CARD_MODEL`을 사용한다.
- `OPENAI_BASE_URL`, `OPENAI_ORG_ID`, `OPENAI_PROJECT`는 현재 `task_recommend.py`, `task.py`에서만 반영된다.
- `llm_service.py`와 `desire/services/llm_client.py`는 import 시점에 클라이언트/설정이 고정되는 구조다.

## DB 비변경 원칙

### 원칙
- 이번 LLM 마이그레이션 범위에서는 DB 스키마를 변경하지 않는다.
- SQLModel 필드, 테이블명, 관계, 인덱스, Alembic revision 추가를 포함해 DB 계층은 비대상이다.

### 현재 코드 기준으로 유지해야 하는 DB 계약
- `Task` 생성 경로
  - `task_recommend.py`
  - `task.py`
  - 기존 `Task` 필드 `user_id`, `title`, `description`, `is_completed`, `created_at`, `completed_at`만 사용한다.
- 감정 대화 경로
  - `llm_service.py` 자체는 DB를 건드리지 않는다.
  - 상위 라우터가 기존 `EmotionSession`, `EmotionStep` 레코드만 읽고 쓴다.
- 카드 생성 경로
  - `llm_card.py`는 payload만 만든다.
  - 상위 라우터가 기존 `EmotionCard` 필드에 매핑해 저장한다.
- need 분석 경로
  - `need_analyzer.py`는 DB를 사용하지 않는다.

### 구현 전에 잠가야 하는 금지 사항
- 새 테이블 추가 금지
- 기존 테이블 컬럼 추가/삭제/타입 변경 금지
- Alembic migration 생성 금지
- LLM 전환을 이유로 저장 payload 구조를 DB 중심으로 재설계하는 작업 금지

## 마이그레이션 제약

### 1. 응답 계약 유지
- `llm_service.py`
  - 스트리밍 토큰 제너레이터 인터페이스를 유지해야 한다.
  - 상위 WebSocket 계층은 델타를 순차 수신하고 이어 붙이는 계약에 의존한다.
- `task_recommend.py`
  - `title`, `description` 배열 형태를 유지해야 한다.
- `task.py`
  - `/tasks/gpt`는 현재 자유 형식 텍스트를 정규식으로 파싱한다.
  - `/tasks/gpt/by-session`은 JSON 배열 응답을 전제로 한다.
- `llm_card.py`
  - 단일 JSON 객체가 `CardCreate` 필드와 바로 매핑되어야 한다.
- `need_analyzer.py`
  - 8개 need를 모두 포함하는 strict JSON 구조를 유지해야 한다.
  - 실패 시 기본 점수로 폴백하는 동작을 유지해야 한다.

### 2. 설정 호환성 유지
- 설정 통합을 하더라도 다음 키 호환 계층이 필요하다.
  - `LLM_MODEL`
  - `LLM_TEMPERATURE`
  - `LLM_MAX_TOKENS`
  - `LLM_TIMEOUT_SEC`
  - `LLM_BACKUP_MODELS`
  - `OPENAI_API_KEY`
  - `OPENAI_BASE_URL`
  - `OPENAI_ORG_ID`
  - `OPENAI_PROJECT`
  - `NEED_CARD_MODEL`
- 특히 `NEED_CARD_MODEL`은 현재 desire 서브시스템의 별도 계약이다.

### 3. 장애 처리 의미 유지
- `llm_service.py`
  - Responses 실패 시 Chat Completions 폴백이 존재한다.
- `task_recommend.py`, `task.py`
  - 파싱 실패 시 예외를 올려 호출자에게 실패를 전달한다.
- `llm_card.py`
  - API 키 누락, 응답 비어 있음, JSON 파싱 실패를 즉시 예외 처리한다.
- `need_analyzer.py`
  - LLM 실패를 로그로 남기고 API 응답은 기본값으로 유지한다.

### 4. 중복 로직 존재
- 세션 기반 Task 추천은 `task_recommend.py`와 `task.py`에 중복 구현되어 있다.
- 설정 해석도 `backend` 안에서 최소 두 군데로 분산되어 있다.
- 따라서 실제 마이그레이션 구현 시 기능 변경보다 먼저 호출 주체와 단일 진입점 정리가 필요하다.

## 영향 범위 고정
- OpenAI SDK 직접 의존 파일은 위 5개가 핵심이다.
- 다만 `need_analyzer.py`는 `llm_client.py`, `llm_service.py`는 상위 라우터 호출 계약과 함께 봐야 한다.
- 이번 문서 기준 구현 영향 범위는 서비스/라우터/설정 계층으로 한정한다.
- DB 모델과 Alembic은 영향 범위에서 제외한다.
