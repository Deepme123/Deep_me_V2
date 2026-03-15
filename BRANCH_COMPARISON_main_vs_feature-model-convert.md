# Branch Comparison: `main` vs `feature-model-convert`

기준 시각: 2026-03-15

비교 기준 브랜치:
- `origin/main`
- `origin/feature-model-convert`

비교 전 확인:
- `git fetch origin main feature-model-convert --prune`

## Latest Commit

### `origin/main`
- Commit: `e445a518c7c64cac2c852613cb4d955938739889`
- Date: `2026-03-09 00:21:19 +0900`
- Message: `260309)프롬포트 업데이트`

### `origin/feature-model-convert`
- Commit: `bafac9c48bead53198d6f747e18c5a5e1cbe583e`
- Date: `2026-03-15 20:04:53 +0900`
- Message: `docs(env): add .env migration guide and rollback instructions`

## Branch Relationship

- 공통 조상: `3ea8d442c0d957b064a37908d4c85c7e99ec4845`
- `main` 전용 커밋 수: `6`
- `feature-model-convert` 전용 커밋 수: `10`

즉, `feature-model-convert`는 `main`의 단순 상위 브랜치가 아니라, 공통 조상 이후 별도로 진화한 분기 상태다.

## Commits Only In `feature-model-convert`

1. `bafac9c` `docs(env): add .env migration guide and rollback instructions`
2. `3d55def` `test(llm): 실제 API 없이도 provider 전환 안정성 확인.`
3. `c41c5eb` `feat(llm): add Anthropic provider behind opt-in environment switch`
4. `8f48184` `test(llm): add provider-selection and regression tests for text stream and json flows`
5. `26f2155` `refactor(structured-output): move analyze/desire JSON flows to common generate_json contract`
6. `1a6b8e0` `refactor(tasks): provider 전환 시 task 경로가 엇갈리지 않게 함`
7. `e4d25bb` `refactor(backend): 일반 응답/스트리밍 경로 안정화`
8. `dec3871` `Claude 추가 전에 OpenAI를 공통 레이어 뒤에 숨길 준비.`
9. `c467765` `refactor(llm): ANTHROPIC_API_KEY를 읽는 공용 설정 계층 추가`
10. `1a56aae` `docs(llm): 오늘 작업 정리`

## Commits Only In `main`

1. `e445a51` `260309)프롬포트 업데이트`
2. `b8d81c7` `시스템 프롬포트 업데이트`
3. `d9db8fb` `requirements.txt 업데이트`
4. `c3cb23e` `hot-fix) health_llm 치명 오류 수정: LLM 호출 시그니처 불일치로 인한 런타임 크래시 해결`
5. `b2ac1f6` `DeepMe 2.0`
6. `6484d16` `Merge pull request #1 from Deepme123/develop`

## High-Level Summary

### `feature-model-convert` 쪽 핵심 변화
- LLM 공통 추상화 레이어 추가
- OpenAI provider / Anthropic provider 도입
- backend / analyze / desire 경로의 LLM 호출 방식 정리
- task 추천 경로 분리 및 공통화
- stream bridge 추가
- provider 계약 테스트, health 테스트, task 테스트 등 대규모 테스트 추가
- `.env.example` 및 운영 문서 추가

### `main` 쪽 핵심 변화
- 시스템 프롬프트 업데이트
- `health_llm` 라우터 hotfix 반영
- `requirements.txt` 조정
- `tests/test_health_llm_router.py` 추가

## File-Level Difference Summary

`origin/main...origin/feature-model-convert` 기준:
- 변경 파일 수: `36`
- 추가/수정 규모: `+3202 / -724`

주요 변경 파일:
- `.env.example`
- `RUN.md`
- `app/analyze/config.py`
- `app/analyze/services/llm_card.py`
- `app/backend/routers/emotion_ws.py`
- `app/backend/routers/health_llm.py`
- `app/backend/routers/task.py`
- `app/backend/services/llm_service.py`
- `app/backend/services/stream_bridge.py`
- `app/backend/services/task_llm_service.py`
- `app/backend/services/task_recommend.py`
- `app/core/llm/*`
- `app/core/llm_settings.py`
- `app/desire/core/config.py`
- `app/desire/services/llm_client.py`
- `app/desire/services/need_analyzer.py`
- `docs/env-provider-migration.md`
- `docs/llm-call-sites.md`
- `tests/backend/*`
- `tests/core/*`
- `tests/analyze/test_llm_card.py`
- `tests/desire/test_need_analyzer.py`

## Files Changed Only On `main` Side Relative To `feature-model-convert`

`origin/feature-model-convert...origin/main` 기준:

- `app/backend/resources/system_prompt.txt`
- `app/backend/routers/health_llm.py`
- `requirements.txt`
- `tests/test_health_llm_router.py`

이 네 파일은 `main`에서 추가로 반영된 차이이며, `feature-model-convert`를 `main`에 맞추려면 별도 확인이 필요하다.

## Likely Merge Conflict Areas

충돌 가능성이 높은 파일:
- `app/backend/routers/health_llm.py`
- `requirements.txt`

충돌은 아니더라도 머지 후 동작 확인이 필요한 파일:
- `app/backend/resources/system_prompt.txt`
- `app/backend/services/llm_service.py`
- `app/backend/routers/task.py`
- `app/backend/services/task_recommend.py`
- `app/analyze/services/llm_card.py`
- `app/desire/services/need_analyzer.py`

## Practical Interpretation

- `feature-model-convert`는 LLM 아키텍처 변경이 중심인 대규모 브랜치다.
- `main`은 그와 별개로 프롬프트와 `health_llm` hotfix를 추가 반영한 상태다.
- 따라서 `feature-model-convert`를 병합할 때는 단순 fast-forward가 아니라, `main`의 최근 수정사항을 흡수하는 정리 작업이 필요하다.

## Recommended Next Step

권장 순서:

1. `feature-model-convert`에 `main`을 먼저 병합하거나 rebase 한다.
2. `app/backend/routers/health_llm.py`와 `requirements.txt` 충돌을 먼저 해결한다.
3. `system_prompt.txt`의 최신 내용이 유지되는지 확인한다.
4. provider 관련 테스트와 `health_llm` 테스트를 함께 재실행한다.

