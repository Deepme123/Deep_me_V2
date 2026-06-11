# 📋 Deep_me_V2 전체 커밋 히스토리

**최종 생성일**: 2026-05-10  
**총 커밋 수**: 214개  
**저자**: Adios159, imadios  
**활동 기간**: 2026-01-24 ~ 2026-05-10 (약 107일)

---

## 📊 통계 요약

| 항목 | 값 |
|------|-----|
| 총 커밋 수 | 214 |
| 로컬 브랜치 | 15개 |
| 리모트 브랜치 | 20개+ |
| 활성 브랜치 | main, develop, security |
| 최근 활동 | 2026-05-10 (보안 수정 사항 4개 커밋 병합) |

---

## 🌳 브랜치 구조 및 파생 관계

### 🎯 메인 브랜치

#### **main** (PRIMARY)
운영 브랜치. PR 병합을 통해서만 업데이트됨.

**최근 5개 커밋:**
1. (2026-05-10) - 보안 수정 사항 병합 (security → main)
2. `d26f2b5` (2026-05-10) - fix(security): C-3 하드코딩 테스트 계정 및 /auth/token 엔드포인트 제거
3. `5119a3a` (2026-05-10) - fix(security): C-1 프롬프트 수정 API 전체 제거
4. `53f7122` (2026-05-10) - fix(security): C-4 analyze 서브앱 전 엔드포인트 인증 추가 및 IDOR 방어
5. `6812ae1` (2026-05-10) - fix(security): C-2 JWT 시크릿 기본값 제거 — 미설정 시 서버 시작 실패

#### **develop** (INTEGRATION)
기능별 브랜치를 통합하는 중간 브랜치.

**최근 5개 커밋:**
1. `2b53e7c` (2026-05-05) - Merge branch 'main' into develop
2. `e9a653a` (2026-05-05) - Merge pull request #28 from Deepme123/feat/behavior-patterns
3. `7db7bb7` (2026-05-05) - feat: behavior_patterns LLM 생성 로직 추가
4. `ad67029` (2026-05-05) - feat: BehaviorPattern 스키마 추가 및 모델/라우터 반영
5. `22c238b` (2026-05-05) - DB: behavior_patterns JSONB 컬럼 추가 마이그레이션

### ✨ 활성 기능 브랜치 (feat/*)

#### **feat/behavior-patterns** 
동작 패턴 분석 기능 추가 (최신 병합)
- 커밋 수: 3개
- 상태: ✅ main에 병합됨 (2026-05-05)

**커밋:**
- `7db7bb7` - feat: behavior_patterns LLM 생성 로직 추가
- `ad67029` - feat: BehaviorPattern 스키마 추가 및 모델/라우터 반영
- `22c238b` - DB: behavior_patterns JSONB 컬럼 추가 마이그레이션

#### **feat/emotion-evidence**
감정 증거/인용구 필드 추가
- 커밋 수: 3개
- 상태: ✅ main에 병합됨 (2026-05-05)

**커밋:**
- `1394dc0` - fix: 마이그레이션 테스트 테이블 목록 및 버전 최신화
- `8e37713` - feat: core_emotions에 quote, reasoning LLM 생성 추가
- `b54fffc` - feat: EmotionEntry에 quote, reasoning 필드 추가

#### **feat/situation-steps**
상황 분석을 단계별 구조로 변경
- 커밋 수: 4개
- 상태: 🔄 진행 중

**커밋:**
- `b0aebd4` - fix: situation_steps 관련 누락 수정 및 테스트 업데이트
- `4334915` - feat: situation_steps LLM 생성 로직 적용
- `b8751f2` - feat: situation → situation_steps 모델 및 스키마 변경
- `bbc45eb` - DB: situation String → situation_steps JSONB 마이그레이션 추가

#### **feat/add_analyze_card_table**
분석 카드 테이블 추가 (완료)
- 커밋 수: 5개
- 상태: ✅ main에 병합됨

**커밋:**
- `7143cb1` - docs(deploy): add render migration rollout guide
- `69bc36f` - test(db): add schema migration coverage
- `cfb13f3` - feat(app): fail fast on missing required tables
- `0a4798b` - feat(alembic): add emotioncard migration
- `9faea8e` - chore(alembic): add baseline migration history

#### **feat/confirm-close**
세션 종료 확인 플로우 (완료)
- 커밋 수: 10개
- 상태: ✅ main에 병합됨

**주요 커밋:**
- `777a940` - Clarify guided and automatic close behavior
- `4a9de59` - Add auto-close token regression coverage
- `e27be0a` - Tighten STEP 12 close token contract

#### **feat/emotion-evidence**
감정 근거 데이터 추가
- 상태: ✅ main에 병합됨 (2026-05-05)

#### **feat/front-basic-set**
프론트엔드 기본 설정
- 커밋 수: 4개
- 상태: 🔄 진행 중

**커밋:**
- `2f9ea79` - Document frontend development setup
- `5c6c411` - Add beta and admin route skeletons
- `f98e1de` - Add shared frontend config and clients
- `e03fa43` - Initialize frontend workspace

#### **feat/improve_web_env**
웹 환경 개선
- 커밋 수: 11개
- 상태: ✅ main에 병합됨

**주요 커밋:**
- `93635ae` - Cover updated web test demo layout assets
- `cdb944a` - Hide message generation entries in web test log
- `a42c7cc` - Constrain web test feeds with internal scrolling
- `01f8f27` - Move web test composer into center column

#### **feat/renew-teat-page** (오타: test-page)
테스트 페이지 재구성
- 커밋 수: 2개
- 상태: ✅ main에 병합됨

#### **feat)emofield** (브랜치명 오타)
감정 필드 구조화
- 커밋 수: 3개
- 상태: 🔄 진행 중

**커밋:**
- `96cf059` - feat: physical_reactions 하위 코드 배열 타입 적용 및 DB 마이그레이션
- `dbb7d79` - feat: physical_reactions 타입 string → array로 변경 (스키마/모델)
- `51bf114` - feat: physical_reactions LLM 프롬프트 출력 범위 1~4개로 제한

#### **feat)conversation-to-analyze-card** (브랜치명 오타)
대화를 분석 카드로 변환
- 커밋 수: 5개+
- 상태: 🔄 진행 중

**주요 커밋:**
- `732dd27` - refactor: update config to use SettingsConfigDict for model configuration
- `edae18c` - docs: document websocket close flow and card trigger path
- `8da2ba6` - test: cover analysis card trigger after confirm close
- `fbcfccc` - feat: trigger analysis card generation after close confirmation

### 🔧 리팩토링 브랜치 (refactor/*)

#### **refactor/rename-emotion-to-analysis**
EmotionCard → AnalysisCard 전체 리네이밍
- 커밋 수: 6개
- 상태: ✅ main에 병합됨 (2026-05-03)

**커밋:**
- `a688192` - Merge pull request #24
- `cbf8028` - fix: analyze_needs 시그니처 변경에 맞게 테스트 업데이트
- `9b3c576` - fix: 마이그레이션 테스트를 0004 head 버전 기준으로 업데이트
- `2a08d7f` - refactor: 테스트 코드 EmotionCard/emotion_card 참조 업데이트
- `3c5900a` - refactor: LLM 툴명 emotion_card → analysis_card 통일
- `68957c3` - refactor: EmotionCard 클래스명을 AnalysisCard로 리네임

#### **refactor/delete_step_tracker**
Step Manager 삭제 및 transcript 기반 분석으로 전환
- 커밋 수: 14개
- 상태: ✅ main에 병합됨

**주요 커밋:**
- `b8da4b5` - test: add regression coverage for transcript-first card extraction
- `163f577` - docs: rewrite demo and llm flow docs around transcript-based analysis
- `6949528` - chore: delete step manager and remove dead imports
- `8bfeb19` - refactor: rename local helpers from steps to transcript where possible

#### **refactor/emotion_ws**
WebSocket 라우팅 정리 및 추상화
- 커밋 수: 12개
- 상태: ✅ main에 병합됨

**주요 커밋:**
- `9d0e57a` - Slim websocket router orchestration
- `8633cb1` - Extract websocket post-close actions
- `363068734` - Extract websocket streaming channel
- `ce55e90` - Extract websocket session DB helpers
- `48321521` - Extract websocket protocol helpers

#### **refactor/DB_import**
DB 및 설정 지연 초기화 (Lazy initialization)
- 커밋 수: 5개
- 상태: ✅ main에 병합됨

**커밋:**
- `cd8d86c` - Add import smoke coverage for lazy initialization
- `c41a450` - Validate DB connectivity at app startup
- `6e4469c` - Defer auth env validation to request time
- `108c2fe` - Make shared DB engine initialization lazy
- `ea33bcf` - Make analyze settings lazy

### 🔒 보안 브랜치

#### **security**
보안 정책 적용 및 수정 (최신)
- 커밋 수: 4개
- 상태: 🚀 2026-05-10 main에 병합됨

**보안 수정 사항:**
- `d26f2b5` - C-3: 하드코딩 테스트 계정 및 `/auth/token` 엔드포인트 제거
- `5119a3a` - C-1: 프롬프트 수정 API(`PUT /prompts/system`) 전체 제거
- `53f7122` - C-4: analyze 서브앱 전 엔드포인트 인증 추가 + IDOR 방어
- `6812ae1` - C-2: JWT_SECRET_KEY 기본값 제거 → 미설정 시 서버 시작 실패

### 🛠️ 기타 브랜치

#### **fix**
버그 수정 브랜치
- 상태: ✅ 최근 병합 (2026-05-05)

**최근 커밋:**
- `b851076` - 클로드이그노어 업데이트
- `5f1b2ef` - 테스트: fake_prepare_message_context에 **kwargs 추가
- `0b40e32` - perf: activity_fired 매 턴 DB 쿼리 인메모리 캐싱으로 대체
- `0b296ae` - perf: prepare_message_context 쿼리 ORDER BY + LIMIT 최적화

#### **desire-DB**
욕구/니즈 분석 DB 기능
- 커밋 수: 5개
- 상태: ✅ main에 병합됨 (2026-05-03)

**커밋:**
- `f668cff` - update gitignore
- `d4cf452` - feat: persist need analysis results to DB
- `1453ed4` - feat: add DB session dependency and need card CRUD helpers
- `415453b` - feat: add migration for need_card_result and need_card_score tables
- `df36b73` - feat: add NeedCardResult and NeedCardScore SQLModel models

---

## 📈 커밋 활동 타임라인

### 최근 활동 (2026-05-06 ~ 2026-05-10)

| 날짜 | 커밋 수 | 주요 활동 |
|------|--------|---------|
| 2026-05-10 | 4개 | 보안 정책 적용 (security 브랜치 → main 병합) |
| 2026-05-06 | 0개 | 보안 수정 준비 |
| 2026-05-05 | 13개 | feat/behavior-patterns, feat/emotion-evidence, feat/situation-steps 병합 |
| 2026-05-04 | 5개 | fix 브랜치 병합, 성능 최적화 |
| 2026-05-03 | 22개 | 리네이밍 완료, 여러 feature 병합 |

### 과거 주요 마일스톤

| 날짜 | 이벤트 | 설명 |
|------|--------|------|
| 2026-04-12 | 프론트엔드 초기화 | feat/front-basic-set, feat/improve_web_env 병합 |
| 2026-04-05 | 종료 정책 확립 | feat/confirm-close 병합 |
| 2026-03-31 | WebSocket 리팩토링 | refactor/emotion_ws, refactor/DB_import 병합 |
| 2026-03-23 | Step 제거 | refactor/delete_step_tracker 병합 |
| 2026-03-22 | 분석카드 자동화 | feat)conversation-to-analyze-card 활성화 |
| 2026-03-15 | LLM 추상화 | OpenAI/Anthropic 공통 레이어 구축 |
| 2026-01-24 | 초기 커밋 | 프로젝트 시작, Alembic 마이그레이션 시스템 추가 |

---

## 🔀 병합 전략

### PR 병합 통계

**총 29개의 PR 병합 기록:**
- PR #29: develop → main (2026-05-05)
- PR #28: feat/behavior-patterns → main (2026-05-05)
- PR #27: feat/emotion-evidence → main (2026-05-05)
- PR #26: fix → main (2026-05-05)
- PR #25: fix → main (2026-05-03)
- PR #24: refactor/rename-emotion-to-analysis → main (2026-05-03)
- PR #23: develop → main (2026-05-03)
- PR #22: desire-DB → main (2026-05-03)
- ...이하 20개

### 브랜칭 패턴

```
main (운영)
  ↑
develop (통합)
  ↑
├─ feat/* (기능)
├─ fix/* (버그 수정)
├─ refactor/* (리팩토링)
└─ hotfix/* (긴급)
```

---

## 💡 주요 변경점 요약

### 🔒 최근 보안 수정 (2026-05-10)

**4가지 보안 취약점 해결:**

1. **C-1: 프롬프트 수정 API 제거**
   - 삭제: `PUT /prompts/system` 엔드포인트
   - 이유: 운영 중 시스템 프롬프트 무단 변경 방지

2. **C-2: JWT_SECRET_KEY 기본값 제거**
   - 변경: `.env` 기본값 제거 → 필수 입력
   - 동작: 미설정 시 서버 시작 실패
   - 효과: 운영 환경에서 강력한 키 강제

3. **C-3: 테스트 계정 및 토큰 엔드포인트 제거**
   - 삭제: 하드코딩된 테스트 계정 (test_user, demo_user 등)
   - 삭제: `/auth/token` 엔드포인트
   - 이유: 운영 배포 후 테스트용 백도어 방지

4. **C-4: analyze 서브앱 인증 강화**
   - 추가: 모든 `/analyze/api/*` 엔드포인트 JWT 인증 필수
   - 추가: 사용자 리소스 접근 권한 검증 (IDOR 방어)
   - 효과: 다른 사용자 분석카드/점수 조회 불가

### 🎯 최근 완료된 작업 (2026-05-05)

#### 1. BehaviorPattern 모듈 추가
- **목적**: 사용자 행동 패턴 분석 기능
- **커밋**: `ad67029`, `7db7bb7`, `22c238b`
- **변경 사항**:
  - BehaviorPattern 스키마 및 SQLModel 추가
  - behavior_patterns JSONB 컬럼 마이그레이션
  - LLM 생성 로직 구현

#### 2. EmotionEntry 확장
- **목적**: 감정 근거 및 추론 저장
- **커밋**: `b54fffc`, `8e37713`, `1394dc0`
- **변경 사항**:
  - quote, reasoning 필드 추가
  - 마이그레이션 테스트 최신화

#### 3. Situation → SituationSteps 마이그레이션
- **목적**: 상황 분석을 단계별로 구조화
- **커밋**: `bbc45eb`, `b8751f2`, `4334915`, `b0aebd4`
- **변경 사항**:
  - String → JSONB 배열 구조 변경
  - LLM 생성 로직 적용
  - DB 마이그레이션 0005 추가

### 이전 주요 프로젝트

#### EmotionCard → AnalysisCard 리네이밍 (2026-05-03)
- **규모**: 6개 커밋
- **영향**: 클래스명, DB 테이블명, LLM 도구명 통일

#### Step Manager 제거 (2026-03-23)
- **규모**: 14개 커밋
- **목표**: Transcript 기반 분석으로 단순화
- **결과**: 코드 복잡도 감소, 성능 개선

#### WebSocket 리팩토링 (2026-03-31)
- **규모**: 12개 커밋
- **목표**: 관심사의 분리 및 유지보수성 개선
- **결과**: 
  - ws_protocol.py - 메시지 파싱
  - ws_session_service.py - DB 작업
  - ws_streaming.py - LLM 스트리밍
  - ws_post_actions.py - 종료 후 작업

#### DB 지연 초기화 (2026-03-31)
- **규모**: 5개 커밋
- **목표**: 애플리케이션 시작 성능 개선
- **변경**:
  - 공유 DB 엔진 지연 초기화
  - Analyze 설정 지연 로드
  - Auth 검증을 요청 시간으로 연기

#### LLM 추상화 (2026-03-15)
- **규모**: 16개 커밋
- **목표**: OpenAI ↔ Anthropic 공급자 전환 지원
- **구조**:
  - `app/core/llm/` - 공통 인터페이스
  - `LLM_PROVIDER` 환경 변수로 선택
  - 각 서비스별 독립적인 설정

---

## 📊 커밋 통계

### 타입별 분류

| 타입 | 개수 | 설명 |
|------|------|------|
| feat | ~70개 | 새 기능 추가 |
| refactor | ~50개 | 코드 정리 및 구조 개선 |
| fix | ~20개 | 버그 수정 |
| perf | ~8개 | 성능 최적화 |
| chore | ~20개 | 설정, .gitignore 등 |
| docs | ~15개 | 문서 작성/수정 |
| test | ~10개 | 테스트 추가/수정 |
| merge | ~20개 | PR 병합 |

### 저자별 기여도

| 저자 | 커밋 수 | 활동 기간 |
|------|--------|---------|
| Adios159 | ~190개 | 2026-01-24 ~ 2026-05-05 |
| imadios | ~20개 | 2026-01-24 ~ 2026-03-09 |

---

## 🔍 주요 파일 변경 패턴

### 빈번히 수정된 파일

1. **.gitignore** - 22개+ 커밋
   - 프로젝트 설정 파일 제외
   - pytest 캐시 제외
   - 문서 파일 관리

2. **app/analyze/llm_card.py** - 16개+ 커밋
   - 분석카드 LLM 생성 로직
   - 스키마 검증
   - 리네이밍 및 기능 추가

3. **app/backend/ws/** - 20개+ 커밋
   - WebSocket 리팩토링
   - 메시지 처리 개선
   - 종료 정책 구현

4. **alembic/versions/** - 5개 마이그레이션
   - 0001: 기본 스키마
   - 0002: EmotionCard 추가
   - 0003: 마이그레이션 관계 수정
   - 0004: 리네이밍 반영
   - 0005: behavior_patterns, situation_steps JSONB 추가

### DB 마이그레이션 히스토리

```
0001_base_schema (2026-01-24)
├─ emotion_session, emotion_step, emotion_card 테이블

0002_add_analyze_card_table (2026-03-23)
├─ emotioncard 테이블 추가

0003_adjust_migration_schema (2026-03-23)
├─ 마이그레이션 관계 수정

0004_rename_emotioncard_analysis (2026-05-03)
├─ emotioncard → (리네이밍 준비)
└─ LLM 도구명 emotion_card → analysis_card

0005_add_behavior_and_situation (2026-05-05)
├─ behavior_patterns JSONB 추가
└─ situation String → situation_steps JSONB 변경
```

---

## 🚀 향후 예상 브랜치

### 진행 중인 작업
- `feat/situation-steps` - 병합 대기 중
- `feat)emofield` - physical_reactions 개선
- `feat/front-basic-set` - 프론트엔드 기본 설정

### 완료된 작업 (최근)
- ✅ feat/behavior-patterns (2026-05-05)
- ✅ feat/emotion-evidence (2026-05-05)
- ✅ desire-DB (2026-05-03)
- ✅ refactor/rename-emotion-to-analysis (2026-05-03)

---

## 📝 커밋 메시지 규칙

프로젝트에서 사용된 메시지 패턴:

```
[type]: [subject] (주로 한글)

feat:     새 기능 추가
fix:      버그 수정
refactor: 코드 정리
perf:     성능 개선
test:     테스트 추가/수정
docs:     문서 작성
chore:    환경 설정, .gitignore 등
DB:       데이터베이스 관련 (마이그레이션 등)
```

**예시:**
- `feat: BehaviorPattern 스키마 추가 및 모델/라우터 반영`
- `refactor: EmotionCard 클래스명을 AnalysisCard로 리네임`
- `perf: activity_fired 매 턴 DB 쿼리 인메모리 캐싱으로 대체`
- `DB: situation String → situation_steps JSONB 마이그레이션 추가`

---

## 🔗 관련 링크

- **GitHub Repository**: https://github.com/Deepme123/Deep_me_V2
- **PR 목록**: #29, #28, #27, #26, #25, #24 등

---

## 📅 현재 상태 (2026-05-10)

| 항목 | 상태 |
|------|------|
| **HEAD** | main |
| **Working Tree** | Clean ✅ |
| **최근 병합** | security → main (보안 수정 4개 커밋) |
| **최신 마이그레이션** | 0005 (behavior_patterns + situation_steps) |
| **마지막 활동** | 2026-05-10 (보안 정책 적용) |
| **주요 변경** | C-1, C-2, C-3, C-4 보안 취약점 해결 ✅ |

