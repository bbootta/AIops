# v2 Refactor Plan (결정 완료 — 진행 중)

본 문서는 차세대 업그레이드 리팩토링 계획서다. 결정 항목 Q1~Q4 는 2026-06-10
사용자 확정 완료 (아래 4절). Q5 (추가 항목) 는 미정.

**확정된 결정 (2026-06-10)**

| 항목 | 결정 |
|---|---|
| Q1 패키지명 | (a) `vta` |
| Q2 v1 호환 shim | (a) 1개 분기 유지 후 제거 — 제거 목표 2026-Q4 |
| Q3 Pydantic v2 | (a) Request/Step/Result + 정책 로더 |
| Q4 비동기 | (a) Phase 3 에 포함, `--sync` fallback 유지 |
| Q5 추가 항목 | 미정 (보류) |

---

## 1. 현재 상태 (Round 19 시점)

| 영역 | 수치 |
|---|---|
| Python 모듈 | tools/ 24+ middleware/ 6 + risk_checks/ 7 + handlers/ 1 |
| 매트릭스 step | 25 (등록 25, simulated 0) |
| 정책 SSoT | JSON 12 / schema 8 / 정책 .md 8 |
| 테스트 | 424 통과 |
| 매니페스트 | CHG-0001 ~ CHG-0080 (proposed) |
| CLI 진입점 | 17개 (`tools.*` 산재) |

## 2. v2 목표 / 비목표

**목표**
1. 단일 import 루트 (`import vta`)
2. Pydantic v2 데이터 계약 (Request / Step / Result)
3. 비동기 워크플로우 (독립 step 병렬 실행)
4. 단일 CLI (`vta <subcommand>`)
5. mypy --strict + ruff gate
6. v1 API 는 deprecation shim 으로 1개 분기 유지

**비목표**
- 정책 SSoT JSON 의미 변경
- 매니페스트 80건 의미 변경
- 검증 의견 자동 확정 (HITL 유지)
- 외부 라이브러리 fundamental 교체

## 3. 단계별 로드맵 (Phase 0~5)

| Phase | 목표 | 상태 |
|---|---|---|
| **0. 계획 승인** | 본 문서 + 비목표 확정 | ✅ Q1~Q4 확정 (2026-06-10) |
| **1. 패키지 셸** | `src/vta/` skeleton + v1 shim | ✅ R20 |
| **2. core 이전** | workflow → `vta.core.workflow` + Pydantic 계약 + 정책 로더 | ✅ R27 (run_logger 는 middleware 잔류) |
| **3. domain 이전** | async 엔진 (R28) + risk_checks→`vta.domains` / handlers→`vta.handlers.registry` (R29) | ✅ R28–29 |
| **4. CLI 통합** | `vta` 단일 entry | ✅ R21 |
| **5. 정책 + 마무리** | SSoT 디렉터리 재구조화 + 문서 | 인덱스만 완료 — 파일 물리 이동은 별도 사용자 확인 필요 |

총 7 라운드 / CHG-0081 ~ CHG-0095 추정.

## 4. 사용자 결정 항목 (Q1~Q5)

### Q1. 패키지명
- (a) `vta` (3자, 권장)
- (b) `validation_team_agent`
- (c) 사용자 지정

### Q2. v1 호환성 유지 기간
- (a) 1개 분기 후 shim 제거
- (b) 2개 분기 유지
- (c) 영구 유지

### Q3. Pydantic v2 도입 범위
- (a) Request/Step/Result + 정책 로더 (권장)
- (b) Request/Step/Result 만
- (c) dataclass 유지, mypy 만 강화

### Q4. 비동기 워크플로우 우선순위
- (a) Phase 3 에 포함 (권장)
- (b) Phase 6 로 분리
- (c) v2 범위 외

### Q5. (선택) 추가 항목
보고서 PDF / web UI / 추가 부문 / LLM 통합 등.

## 5. 위험 / 롤백

| 위험 | 대응 |
|---|---|
| Pydantic v2 도입으로 호출 깨짐 | v1 shim 이 dict→Model 변환 |
| 비동기 디버깅 난이도 | `--sync` flag fallback |
| `src/` layout 으로 import 변경 | redirect shim |
| mypy strict 의 막대한 변경 요구 | v2 만 strict, v1 ignore |

각 Phase 종료 시: pytest 통과 + schema 통과 + 매니페스트 무결성 통과.
미통과 시 Phase commit revert.

## 6. 본 문서의 위치

- 본 문서는 **계획 초안**이며, 사용자 결정 후에만 실제 리팩토링 시작.
- v1 의 모든 동작은 본 문서 작성 시점에서 보존된다 (Round 19 = 424 tests).
- 사용자가 답변하지 않는 한 본 문서 자체가 코드를 변경하지 않는다.
