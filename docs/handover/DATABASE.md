# 데이터베이스

---

## 1. 개요

- **DBMS**: PostgreSQL
- **ORM**: SQLModel (SQLAlchemy 2.x + Pydantic 통합)
- **마이그레이션**: Alembic
- **JSONB 컬럼**: PostgreSQL에서만 JSONB 사용, 다른 DB는 JSON으로 폴백

---

## 2. 테이블 목록

| 테이블 | 설명 |
|--------|------|
| `user` | 서비스 사용자 |
| `emotionsession` | 감정 대화 세션 |
| `emotionstep` | 대화 transcript (개별 발화 단위) |
| `analysiscard` | 세션 종료 후 생성되는 분석카드 (구 `emotioncard`, 마이그레이션 0008에서 개명) |
| `satisfactionrating` | 세션별 만족도 평가 (1건, session_id UNIQUE) |
| `task` | 감정 세션 이후 추천된 실천 과제 |
| `refreshtoken` | JWT 리프레시 토큰 (rotation + 재사용 감지) |
| `need_card_result` | 욕구 분석 실행 단위 (session_id 연결) |
| `need_card_score` | 욕구 분석 8개 점수 행 (result_id 연결) |
| `user_need_selection` | 유저가 선택한 욕구 코드 이력 (session_id 연결, 마이그레이션 0007/0014) |

---

## 3. 테이블 상세

### 3.1 `user`

```sql
user_id    UUID        PK  DEFAULT gen_random_uuid()
name       VARCHAR
email      VARCHAR     UNIQUE INDEX
created_at TIMESTAMP   DEFAULT now()
```

### 3.2 `emotionsession`

```sql
session_id        UUID     PK
user_id           UUID     FK → user.user_id
started_at        TIMESTAMP
ended_at          TIMESTAMP   NULL  -- NULL이면 진행 중
emotion_label     VARCHAR     NULL  -- 분석 결과 감정 레이블
topic             VARCHAR     NULL
trigger_summary   VARCHAR     NULL
insight_summary   VARCHAR     NULL
```

### 3.3 `emotionstep`

대화의 개별 발화를 저장합니다. 분석카드 생성의 입력 소스입니다.

```sql
step_id     UUID     PK
session_id  UUID     FK → emotionsession.session_id  ON DELETE CASCADE
step_order  INTEGER               -- 발화 순서 (0부터 시작)
step_type   VARCHAR               -- "user" | "assistant" | "activity" | "cancel_close"
user_input  VARCHAR               -- 사용자 발화 원문
gpt_response VARCHAR             -- AI 응답 원문
created_at  TIMESTAMP
insight_tag VARCHAR  NULL

UNIQUE(session_id, step_order)   -- 순서 중복 방지
```

### 3.4 `analysiscard` (구 `emotioncard`)

LLM이 생성한 심리 분석 결과를 저장합니다. 마이그레이션 0008에서 테이블명이
`emotioncard` → `analysiscard`로 바뀌었습니다. `session_id`는 UNIQUE(0009) —
세션당 카드 1건.

```sql
card_id            UUID     PK
session_id         UUID     FK → emotionsession.session_id  UNIQUE
created_at         TIMESTAMP

-- LLM 생성 필드 (전부 NULL 가능)
summary            VARCHAR
core_emotions      JSONB    -- 배열: [{"emotion": "불안", "quote": "...", "reasoning": "..."}]
situation          VARCHAR
situation_steps    JSONB    -- 배열: [{단계1}, {단계2}, ...], 1~4단계
emotion            VARCHAR
thoughts           JSONB    -- 배열 (0010에서 VARCHAR → JSONB 변환)
physical_reactions JSONB    -- 배열: ["신체반응1", ...]  최대 4개
behaviors          VARCHAR
behavior_patterns  JSONB    -- 배열: [{"pattern": "...", "frequency": "..."}]
coping_actions     JSONB    -- 배열: [{...}]
tags               JSONB    -- 배열: ["직장스트레스", "관계"]
insight            VARCHAR

-- 위험 평가
risk_flag          BOOLEAN  DEFAULT false
risk_level         VARCHAR  NULL   -- "LOW" | "MEDIUM" | "HIGH"

exportable         BOOLEAN  DEFAULT true
```

### 3.4b `satisfactionrating`

세션에 대한 사용자 만족도 평가 1건을 저장합니다 (마이그레이션 0011).

```sql
rating_id   UUID      PK
session_id  UUID      FK → emotionsession.session_id  UNIQUE
rating      INTEGER
created_at  TIMESTAMP
updated_at  TIMESTAMP
```

### 3.5 `task`

```sql
task_id       UUID     PK
user_id       UUID     FK → user.user_id
title         VARCHAR
description   VARCHAR  NULL
is_completed  BOOLEAN  DEFAULT false
created_at    TIMESTAMP
completed_at  TIMESTAMP NULL
```

### 3.6 `refreshtoken`

```sql
jti          VARCHAR  PK           -- JWT ID (고유 식별자)
user_id      UUID     FK → user.user_id
token_hash   VARCHAR               -- SHA-256 해시 (salted)
created_at   TIMESTAMP
expires_at   TIMESTAMP
revoked_at   TIMESTAMP  NULL       -- NULL이면 유효
replaced_by  VARCHAR    NULL       -- rotation chain 추적
ip           VARCHAR    NULL
user_agent   VARCHAR    NULL
```

### 3.7 `need_card_result`

욕구 분석 1회 실행 단위입니다. `emotionsession`과 1:1 또는 1:N 관계입니다.

```sql
result_id   UUID      PK
session_id  UUID      FK → emotionsession.session_id  ON DELETE CASCADE
created_at  TIMESTAMP
```

### 3.8 `need_card_score`

욕구 분석 결과의 8개 욕구 점수를 행 단위로 저장합니다.

```sql
score_id            UUID     PK
result_id           UUID     FK → need_card_result.result_id  ON DELETE CASCADE
code                VARCHAR  -- NeedCode: Choice | Safe | Together | Fun | Meaning | True | Peace | Grow
score               INTEGER  -- 0~100
rank                INTEGER  -- 1(최우선) ~ 8(최하위)
rationale           VARCHAR  DEFAULT ''   -- 점수 근거 설명 (0012)
reflection_message  VARCHAR  DEFAULT ''   -- top4 욕구에 한해 생성되는 개인화 서술 (0013)
```

### 3.9 `user_need_selection`

사용자가 홈 화면에서 선택한 욕구 코드 이력을 저장합니다 (마이그레이션 0007, `session_id`는 0014에서 추가).

```sql
selection_id    UUID     PK
user_id         UUID     FK → user.user_id  ON DELETE CASCADE
selected_codes  JSONB    -- 배열: ["Meaning"]
session_id      UUID     FK → emotionsession.session_id  ON DELETE SET NULL  NULL
created_at      TIMESTAMP
```

---

## 4. 마이그레이션

### 4.1 파일 구조

```
alembic/
├── alembic.ini              # Alembic 설정
├── env.py                   # DB URL 주입, target_metadata 등록
└── versions/
    ├── 0001_base_schema.py                          # user, emotionsession, emotionstep, task, refreshtoken
    ├── 0002_add_emotioncard.py                      # emotioncard 테이블 추가
    ├── 0003_physical_reactions_to_jsonb.py          # physical_reactions 컬럼 JSONB 변환
    ├── 0004_add_needcard_tables.py                  # need_card_result, need_card_score 테이블 추가
    ├── 0005_behavior_patterns.py                    # behavior_patterns, situation_steps JSONB, core_emotions quote/reasoning 추가
    ├── 0006_situation_steps.py                      # situation_steps 관련 후속 정리
    ├── 0007_user_need_selection.py                  # user_need_selection 테이블 추가
    ├── 0008_rename_emotioncard_to_analysiscard.py   # emotioncard → analysiscard 테이블명 변경
    ├── 0009_unique_analysiscard_session.py          # analysiscard.session_id UNIQUE 제약 추가
    ├── 0010_thoughts_to_jsonb.py                    # thoughts 컬럼 VARCHAR → JSONB 변환
    ├── 0011_satisfaction_rating.py                  # satisfactionrating 테이블 추가
    ├── 0012_need_card_score_rationale.py            # need_card_score.rationale 컬럼 추가
    ├── 0013_need_card_score_reflection_message.py   # need_card_score.reflection_message 컬럼 추가
    └── 0014_user_need_selection_session_id.py       # user_need_selection.session_id 컬럼 추가
```

### 4.2 마이그레이션 명령어

**신규 DB (처음 세팅):**
```bash
alembic upgrade head
```

**이미 운영 중인 DB에 적용 (중요!):**
```bash
# 1. 현재 상태 확인
alembic current

# 2. 현재 상태를 기준 마이그레이션으로 인식하도록 스탬프
alembic stamp 0001_base_schema  # 예: 0001 버전까지 적용된 경우

# 3. 이후 버전으로 업그레이드
alembic upgrade head
```

**최신 마이그레이션(0014)까지 반영된 상태 기준으로 최소 필요 테이블**은
`app/db/session.py`의 `ANALYZE_REQUIRED_TABLES`에 정의되어 있으며
(`user`, `emotionsession`, `emotionstep`, `analysiscard`), 시작 시 헬스체크가 이
목록을 기준으로 검사합니다. `satisfactionrating`, `need_card_result`,
`need_card_score`, `user_need_selection`은 이 필수 목록에는 포함되지 않지만
해당 기능을 쓰려면 마찬가지로 마이그레이션이 적용되어 있어야 합니다.

> ⚠️ 이미 테이블이 존재하는 DB에서 `alembic upgrade head`를 바로 실행하면  
> "table already exists" 오류가 발생합니다. 반드시 `stamp` 먼저 실행하세요.

**새 마이그레이션 파일 생성:**
```bash
alembic revision --autogenerate -m "설명"
```

**롤백:**
```bash
alembic downgrade -1
```

### 4.3 `alembic/env.py` 주요 동작

- `DATABASE_URL` 환경변수가 없으면 `POSTGRES_*` 환경변수로 조합
- Render/Neon 호스트 감지 시 자동으로 `?sslmode=require` 추가
- `postgresql://` 스킴을 `postgresql+psycopg2://`로 자동 변환

---

## 5. DB 연결 설정

파일: `app/db/session.py`

```python
# 동기 세션 사용 (FastAPI Depends)
engine = create_engine(DATABASE_URL)

def get_session():
    with Session(engine) as session:
        yield session

# WebSocket 등 Depends 불가 컨텍스트에서 사용
@contextmanager
def session_scope():
    s = Session(engine)
    try:
        yield s
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
```

환경변수 우선순위:
1. `DATABASE_URL` (전체 URL)
2. `POSTGRES_HOST` + `POSTGRES_USER` + `POSTGRES_PASSWORD` + `POSTGRES_DB` 조합

---

## 6. 관계 다이어그램

```
user
 │
 ├──< emotionsession (user_id)
 │        │
 │        ├──< emotionstep (session_id, CASCADE DELETE)
 │        │
 │        ├──< analysiscard (session_id, UNIQUE)
 │        │
 │        ├──< satisfactionrating (session_id, UNIQUE)
 │        │
 │        ├──< need_card_result (session_id, CASCADE DELETE)
 │        │        │
 │        │        └──< need_card_score (result_id, CASCADE DELETE)
 │        │
 │        └──< user_need_selection (session_id, SET NULL)
 │
 ├──< task (user_id)
 │
 ├──< refreshtoken (user_id)
 │
 └──< user_need_selection (user_id, CASCADE DELETE)
```
