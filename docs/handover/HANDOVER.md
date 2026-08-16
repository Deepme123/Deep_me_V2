# Deep_me V2 — 인수인계 문서

> 이 문서는 신규 담당자가 프로젝트를 빠르게 파악하고 이어받을 수 있도록 작성된 인수인계 메인 문서입니다.
> 최종 업데이트: 2026-08-16

---

## 1. 프로젝트 한 줄 요약

**Deep_me V2**는 사용자의 감정 대화를 실시간으로 분석하여 심리 인사이트 카드를 생성하고, 욕구/필요(Need) 분석까지 제공하는 AI 감정 상담 플랫폼입니다.

---

## 2. 핵심 기능

| 기능 | 설명 |
|------|------|
| 감정 대화 | WebSocket 연결 즉시 서버가 세션을 자동으로 열고 인사말을 먼저 보내는 실시간 LLM 스트리밍 대화 |
| 분석카드 생성 | 대화 종료 후 자동으로 심리 인사이트 카드(AnalysisCard) 생성 |
| 욕구/필요 분석 | 8가지 심리경제학적 욕구 분석 및 우선순위 도출, 세션 종료 시 분석카드와 함께 자동 생성 |
| 만족도 평가 | 세션별 만족도(SatisfactionRating) 저장/조회 |
| 태스크 추천 | 대화 중 액티비티 턴에서 자동으로, 또는 세션 기반으로 실천 가능한 행동 과제 추천 |
| 위험 감지 | 자해/자살 의향 등 위험 키워드 자동 플래그 처리 (LOW/MEDIUM/HIGH) |

---

## 3. 기술 스택 요약

```
Backend   : Python 3.x + FastAPI + SQLModel + PostgreSQL + Alembic
LLM       : OpenAI / Anthropic Claude (환경변수로 전환 가능)
Auth      : Google OAuth 2.0 + JWT (Access/Refresh Token 이중 구조)
Frontend  : Flutter (Dart) 모바일 앱 — Android/iOS/Web, 별도 레포(DeepMe-frontend)
Deploy    : Render (Web Service + PostgreSQL), GitHub 웹훅 기반 자동배포(운영/테스트 분리)
```

---

## 4. 모노레포 구조 개요

```
Deep_me_V2/
├── app/                  # Python 백엔드 (FastAPI)
│   ├── main.py           # FastAPI 앱 본체 + analyze/desire 라우터 include
│   ├── backend/          # 인증, 감정대화 WebSocket/REST, 태스크 API
│   ├── analyze/          # 분석카드/만족도 생성 라우터·서비스
│   ├── desire/            # 욕구/필요 분석 라우터·서비스
│   ├── core/               # LLM 추상화, 공통 설정
│   └── db/                 # DB 세션 관리
├── frontend/              # Flutter 앱 (별도 레포 클론, git 추적 제외)
├── alembic/                # DB 마이그레이션
├── tests/                  # 테스트 모음
└── docs/                   # 문서 (인수인계 포함)
```

---

## 5. 상세 문서 목록

| 문서 | 내용 |
|------|------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 서비스 아키텍처, 모듈 구조, WebSocket/인증 흐름 |
| [DATABASE.md](./DATABASE.md) | DB 스키마, 테이블 정의, 마이그레이션 가이드 |
| [API.md](./API.md) | 전체 REST API + WebSocket 프로토콜 레퍼런스 |
| [FRONTEND.md](./FRONTEND.md) | Flutter 프론트엔드 구조, 백엔드 연동 방식 |
| [DEPLOYMENT.md](./DEPLOYMENT.md) | 배포 방법, 환경변수 전체 목록, 주의사항 |
| [DEVELOPMENT_GUIDE.md](./DEVELOPMENT_GUIDE.md) | 로컬 개발환경 세팅, 테스트 실행 방법 |
| [CI_CD.md](./CI_CD.md) | CI 파이프라인, 배포 트리거(웹훅), 롤백 방법 |
| [COMMIT_HISTORY.md](./COMMIT_HISTORY.md) | 2026-05-10 시점 커밋 히스토리 스냅샷 (그 이후 변경 이력은 `git log` 참조) |

---

## 6. 로컬 빠른 시작

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 환경변수 설정
cp .env.example .env
# .env 파일에서 OPENAI_API_KEY, DATABASE_URL, JWT_SECRET_KEY, JWT_REFRESH_SECRET,
# GOOGLE_CLIENT_ID/SECRET 등 필수 값 입력 (DEPLOYMENT.md 2장 참조)

# 3. DB 마이그레이션
alembic upgrade head

# 4. 백엔드 실행
uvicorn app.main:app --reload
```

**접속 주소:**
- API 서버: http://localhost:8000
- Swagger UI: http://localhost:8000/docs

프론트엔드(Flutter)는 별도 레포를 `frontend/`에 클론한 뒤 `flutter pub get && flutter run`으로
실행합니다. 자세한 내용은 `FRONTEND.md` 참조.

---

## 7. 인수인계 체크리스트

- [ ] `.env` 파일의 운영 환경 키 전달 받기 (OPENAI_API_KEY, DATABASE_URL, JWT_SECRET_KEY, GOOGLE_CLIENT_ID/SECRET 등)
- [ ] Render 대시보드 계정 접근 권한 확인 (운영 `deep-me-v2`, 테스트 `deep-me-v2-test` 두 서비스)
- [ ] PostgreSQL DB 접속 정보 및 현재 마이그레이션 상태 확인 (`alembic current`)
- [ ] 현재 운영 중인 LLM 모델 및 비용 현황 확인
- [ ] Flutter 프론트엔드 개발 진행 상황 파악 (`FRONTEND.md` 6장 — API 엔드포인트가 코드에 하드코딩되어 있음에 유의)
- [ ] 위험 감지 플래그 대응 프로세스 확인
- [ ] GitHub 웹훅(`/webhook/github`) 및 관련 Render/Discord 환경변수 확인

---

## 8. 현재 개발 상황

| 항목 | 상태 |
|------|------|
| 백엔드 API | ✅ 완성 (인증, 감정대화, 분석, 욕구분석, 만족도, 태스크) |
| WebSocket 오프닝 인사 | ✅ 완성 (연결 즉시 세션 자동 오픈 + 서버 선(先) 인사 메시지) |
| 프론트엔드 (Flutter) | 🚧 진행 중 (로그인 + 실시간 채팅 화면 완성, 분석/욕구카드 화면 연동은 별도 확인 필요) |
| LLM 멀티 프로바이더 | ✅ OpenAI/Anthropic 전환 가능 |
| 테스트 커버리지 | ✅ 주요 서비스 단위 테스트 다수 (`tests/` 4개 서브패키지) |
| 욕구카드 DB 연동 | ✅ 완성 (`need_card_result`/`need_card_score`/`user_need_selection`, 세션 종료 시 자동 생성) |
| 만족도 평가 | ✅ 완성 (`PUT/GET /analyze/api/sessions/{id}/satisfaction`) |
| 배포 자동화 | ✅ 완성 (GitHub 웹훅 → 운영/테스트 Render 서비스 분리 배포 + Discord 알림) |
| 보안 정책 적용 | ✅ 완성 (프롬프트 API 제거, 테스트 계정 제거, JWT 기본값 제거, GitHub 웹훅 서명 검증) |

---

## 9. 알아야 할 중요 사항

1. **WebSocket 세션은 클라이언트가 열지 않습니다**: 연결 직후 서버가 인증
   토큰만으로 세션을 자동 생성하고, 랜덤 딜레이 후 인사 메시지를 먼저
   보냅니다. `[[CONFIRM_CLOSE]]` 마커는 대화 자동 종료 트리거이며, 이른
   턴(`user_order < MIN_CLOSE_ORDER`)에서 감지되면 무시됩니다.

2. **세션 종료 시 분석카드 + 욕구카드가 함께 생성됩니다**: 욕구카드 생성
   실패는 별도 WS 알림 없이 로그로만 남으므로, 문제 발생 시
   `GET /desire/need-cards/history`로 직접 확인해야 합니다.

3. **리프레시 토큰 재사용 감지**: 탈취된 토큰 재사용 시 해당 유저의 모든 세션이 무효화됩니다. 운영 중 갑작스러운 로그아웃 민원 발생 시 이 로직부터 확인하세요.

4. **기존 DB 마이그레이션 주의**: 이미 운영 중인 DB에 마이그레이션을 적용할 때는 반드시 `alembic stamp`로 현재 상태를 먼저 찍은 후 `upgrade head`를 실행해야 합니다.

5. **환경변수 `JWT_SECRET_KEY`/`JWT_REFRESH_SECRET`**: 미설정 시 서버 시작 자체가 실패합니다 (의도된 동작).

6. **LLM 기본 모델**: `LLM_MODEL` 환경변수를 설정하지 않으면 코드 기본값
   `gpt-5.4-mini-2026-03-17`로 폴백합니다. 욕구 분석(desire)은 레거시 이름
   `NEED_CARD_MODEL`로 별도 모델을 지정할 수 있습니다.

7. **프론트엔드는 Flutter 모바일 앱**입니다 (React/Vite 웹 UI 계획은 폐기됨).
   `frontend/lib/core/config/api_config.dart`에 백엔드 URL이 하드코딩되어
   있어, 로컬 백엔드로 붙이려면 직접 값을 바꿔야 합니다.

8. **과거 보안 수정 이력 (2026-05-06~05-10)**:
   - ✅ C-1: 프롬프트 수정/조회 API(`/prompts/*`) 전체 제거
   - ✅ C-2: JWT_SECRET_KEY 기본값 제거 → 미설정 시 서버 시작 실패
   - ✅ C-3: 하드코딩 테스트 계정 및 `/auth/token` 엔드포인트 제거
   - ✅ C-4: analyze 라우터 전 엔드포인트 인증 추가 + IDOR 방어
