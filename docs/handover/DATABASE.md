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
| `emotioncard` | 세션 종료 후 생성되는 분석카드 |
| `task` | 감정 세션 이후 추천된 실천 과제 |
| `refreshtoken` | JWT 리프레시 토큰 (rotation + 재사용 감지) |
| `need_card_result` | 욕구 분석 실행 단위 (session_id 연결) |
| `need_card_score` | 욕구 분석 8개 점수 행 (result_id 연결) |

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

### 3.4 `emotioncard`

LLM이 생성한 심리 분석 결과를 저장합니다.

```sql
card_id            UUID     PK
session_id         UUID     FK → emotionsession.session_id
created_at         TIMESTAMP

-- LLM 생성 필드 (전부 NULL 가능)
summary            VARCHAR
core_emotions      JSONB    -- 배열: [{"emotion": "불안", "quote": "...", "reasoning": "..."}]
situation_steps    JSONB    -- 배열: [{단계1}, {단계2}, ...], 1~4단계
emotion            VARCHAR
thoughts           VARCHAR
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
score_id   UUID     PK
result_id  UUID     FK → need_card_result.result_id  ON DELETE CASCADE
code       VARCHAR  -- NeedCode: Choice | Safe | Together | Fun | Meaning | True | Peace | Grow
score      INTEGER  -- 0~100
rank       INTEGER  -- 1(최우선) ~ 8(최하위)
```

---

## 4. 마이그레이션

### 4.1 파일 구조

```
alembic/
├── alembic.ini              # Alembic 설정
├── env.py                   # DB URL 주입, target_metadata 등록
└── versions/
    ├── 0001_base_schema.py                    # user, emotionsession, emotionstep, task, refreshtoken
    ├── 0002_add_emotioncard.py                # emotioncard 테이블 추가
    ├── 0003_physical_reactions_to_jsonb.py    # physical_reactions 컬럼 JSONB 변환
    ├── 0004_add_needcard_tables.py            # need_card_result, need_card_score 테이블 추가
    └── 0005_behavior_patterns.py              # behavior_patterns, situation_steps JSONB 추가
                                               # core_emotions quote/reasoning 필드 추가
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

**마이그레이션 0005 상세정보 (2026-05-05 추가):**
- `core_emotions` 배열 필드에 `quote`, `reasoning` 추가
- `situation` VARCHAR → `situation_steps` JSONB로 변경 (1~4단계 구조)
- `behavior_patterns` JSONB 컬럼 추가

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
 │        ├──< emotioncard (session_id)
 │        │
 │        └──< need_card_result (session_id, CASCADE DELETE)
 │                 │
 │                 └──< need_card_score (result_id, CASCADE DELETE)
 │
 ├──< task (user_id)
 │
 └──< refreshtoken (user_id)
```
