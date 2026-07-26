# Deep_me V2 — 인수인계 문서

> 이 문서는 신규 담당자가 프로젝트를 빠르게 파악하고 이어받을 수 있도록 작성된 인수인계 메인 문서입니다.  
> 최종 업데이트: 2026-07-26

---

## 1. 프로젝트 한 줄 요약

**Deep_me V2**는 사용자의 감정 대화를 실시간으로 분석하여 심리 인사이트 카드를 생성하고, 욕구/필요(Need) 분석까지 제공하는 AI 감정 상담 플랫폼입니다.

---

## 2. 핵심 기능

| 기능 | 설명 |
|------|------|
| 감정 대화 | WebSocket 기반 실시간 LLM 스트리밍 대화 |
| 분석카드 생성 | 대화 종료 후 자동으로 심리 인사이트 카드 생성 |
| 욕구/필요 분석 | 8가지 심리경제학적 욕구 분석 및 우선순위 도출, top4 욕구별 개인화 reflection 문단 |
| 욕구 선택 이력 | 유저가 선택한 욕구를 저장하고 히스토리/마지막 선택 조회 |
| 만족도 평가 | 세션별 사용자 만족도 평가 저장/조회 |
| 태스크 추천 | 감정 세션 후 실천 가능한 행동 과제 추천 |
| 위험 감지 | 자해/자살 의향 등 위험 키워드 자동 플래그 처리 |

---

## 3. 기술 스택 요약

```
Backend   : Python 3.x + FastAPI + SQLModel + PostgreSQL + Alembic
LLM       : OpenAI (gpt-4o-mini 기본) / Anthropic Claude (전환 가능)
Auth      : Google OAuth 2.0 + JWT (Access/Refresh Token 이중 구조)
Frontend  : Flutter 모바일 앱 (별도 레포 DeepMe-frontend, frontend/에 클론해서 사용)
Deploy    : Render (Web Service + PostgreSQL)
```

---

## 4. 모노레포 구조 개요

```
Deep_me_V2/
├── app/                  # Python 백엔드 (FastAPI, 단일 앱 + 라우터 조립)
│   ├── main.py           # app.backend.main:app에 analyze/desire 라우터 include_router
│   ├── backend/          # 인증, 감정대화, 태스크 API (실제 FastAPI() 인스턴스가 여기 있음)
│   ├── analyze/          # 분석카드 생성 서비스 (라우터만, /analyze 프리픽스로 부착)
│   ├── desire/           # 욕구/필요 분석 서비스 (라우터만, /desire 프리픽스로 부착)
│   ├── core/             # LLM 추상화 (llm_settings.py, llm/)
│   └── db/               # 세 서비스가 공유하는 단일 DB 엔진/세션
├── frontend/             # Flutter 모바일 앱 (별도 레포 클론, .gitignore 대상 — 이 레포 이력에는 없음)
├── alembic/              # DB 마이그레이션
├── tests/                # 테스트 모음
└── docs/                 # 문서 모음
```

---

## 5. 상세 문서 목록

| 문서 | 내용 |
|------|------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 서비스 아키텍처, 모듈 구조, 핵심 서비스 로직 |
| [DATABASE.md](./DATABASE.md) | DB 스키마, 테이블 정의, 마이그레이션 가이드 |
| [API.md](./API.md) | 전체 REST API + WebSocket 프로토콜 레퍼런스 |
| [FRONTEND.md](./FRONTEND.md) | 프론트엔드 구조, 라우팅, 환경설정 |
| [DEPLOYMENT.md](./DEPLOYMENT.md) | 배포 방법, 환경변수 전체 목록, 주의사항 |
| [DEVELOPMENT_GUIDE.md](./DEVELOPMENT_GUIDE.md) | 로컬 개발환경 세팅, 테스트 실행 방법 |

---

## 6. 로컬 빠른 시작

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 환경변수 설정
cp .env.example .env
# .env 파일에서 OPENAI_API_KEY, DATABASE_URL 등 필수 값 입력

# 3. DB 마이그레이션
alembic upgrade head

# 4. 백엔드 실행
uvicorn app.main:app --reload

# 5. 프론트엔드 실행 (별도 터미널, Flutter — frontend/는 DeepMe-frontend 레포를 클론해야 함)
cd frontend
flutter pub get
flutter run
```

**접속 주소:**
- API 서버: http://localhost:8000
- Flutter 앱: 별도 기기/에뮬레이터에서 `flutter run` (웹 URL 없음)

---

## 7. 인수인계 체크리스트

- [ ] `.env` 파일의 운영 환경 키 전달 받기 (OPENAI_API_KEY, DATABASE_URL, JWT_SECRET_KEY, GOOGLE_CLIENT_ID/SECRET 등)
- [ ] Render 대시보드 계정 접근 권한 확인
- [ ] PostgreSQL DB 접속 정보 및 현재 마이그레이션 상태 확인 (`alembic current`, 최신은 0014)
- [ ] 현재 운영 중인 LLM 모델 및 비용 현황 확인
- [ ] [DeepMe-frontend](https://github.com/Deepme123/DeepMe-frontend) Flutter 앱 접근 권한 및 개발 진행 상황 파악
- [ ] 위험 감지 플래그 대응 프로세스 확인
- [ ] [docs/SECURITY_AUDIT.md](../SECURITY_AUDIT.md)의 미해결 P0/P1 이슈 확인

---

## 8. 현재 개발 상황

| 항목 | 상태 |
|------|------|
| 백엔드 API | ✅ 완성 (인증, 감정대화, 분석, 욕구분석, 만족도평가, 태스크) |
| 프론트엔드 (Flutter) | 🚧 진행 중 (로그인 + 감정 대화 화면 구현, 분석/욕구 카드 화면 통합 진행 중) — 별도 레포, 최신 상태는 그 레포에서 확인 |
| LLM 멀티 프로바이더 | ✅ OpenAI/Anthropic 전환 가능 |
| 테스트 커버리지 | ✅ 주요 서비스 단위 테스트 완성 (backend/analyze/desire/core, 30개+ 파일) |
| 욕구카드 DB 연동 | ✅ 완성 (need_card_result, need_card_score, user_need_selection) |
| 욕구카드 개인화 | ✅ 완성 (과거 선택 이력 기반 프롬프트 힌트, top4 reflection 문단 생성) |
| 만족도 평가 | ✅ 완성 (세션당 1건, PUT/GET) |
| 보안 정책 적용 | ✅ Critical 4건 완료, 이후 재감사에서 발견된 항목은 SECURITY_AUDIT.md에서 진행 상황 추적 중 |

> QA Demo UI(`app/backend/demo_ui/`, `/demo/emotion-analysis`)는 제거되었습니다.

---

## 9. 알아야 할 중요 사항

1. **`[[CONFIRM_CLOSE]]` 마커**: 대화 자동 종료는 모델 응답 끝에 이 문자열이 있을 때만 트리거됩니다. 자연어 마무리 문구만으로는 분석카드 생성이 보장되지 않습니다.

2. **세션 종료 시 3가지 비동기 작업**: 분석카드 생성, 욕구(need-card) 분석, 태스크 추천이 모두 `ws_post_actions.py`에서 비동기로 실행됩니다.

3. **리프레시 토큰 재사용 감지**: 탈취된 토큰 재사용 시 해당 유저의 모든 세션이 무효화됩니다. 운영 중 갑작스러운 로그아웃 민원 발생 시 이 로직부터 확인하세요.

4. **기존 DB 마이그레이션 주의**: 이미 운영 중인 DB에 마이그레이션을 적용할 때는 반드시 `alembic stamp`로 현재 상태를 먼저 찍은 후 `upgrade head`를 실행해야 합니다.

5. **환경변수 `JWT_SECRET_KEY`**: `.env.example`의 기본값은 개발용입니다. 운영 환경에서는 반드시 강력한 랜덤 키로 교체해야 합니다. 또한 쿠키 보안 플래그는 `SECURE_COOKIE`와 `COOKIE_SECURE` **두 개의 별도 변수**로 나뉘어 있으니 둘 다 확인하세요 ([DEPLOYMENT.md](./DEPLOYMENT.md) §2.4 참고).

6. **LLM 비용**: 기본 모델은 `gpt-4o-mini`이며, 욕구 분석(desire)은 별도 `NEED_CARD_MODEL` 환경변수로 다른 모델을 지정할 수 있습니다.

7. **보안 현황**: Critical 4건(프롬프트 API 제거, JWT 기본값 제거, 테스트 계정 제거, analyze/desire 인증 추가)은 2026-05-09에 완료되었습니다. 이후 정기 재감사가 진행 중이므로 최신 미해결 이슈는 문서에 날짜를 박아두는 대신 [docs/SECURITY_AUDIT.md](../SECURITY_AUDIT.md)를 직접 확인하세요.
