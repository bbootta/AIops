# AIops 저장소 종합 코드 리뷰

**일시:** 2026-06-19
**리뷰 대상:** `bbootta/AIops` 저장소의 열린 PR 10건 (main 브랜치는 `CLAUDE.md` + `.gitkeep`만 존재)
**리뷰 방식:** PR별 병렬 리뷰 → 통합 리포트
**리뷰 누락:** PR #11/#12 (`.gitignore`에 `.claude/worktrees/` 추가하는 동일 1-line 변경 — trivial)

---

## 우선순위 요약 (Top Findings)

| 순위 | PR | 영역 | 핵심 결함 |
|---|---|---|---|
| **P0** | #5 | Basel 규제 수치 | SA 기업·은행 RW 표에서 **"B" 등급이 100% (정상 150%)** — 규제 자본 과소 산정 |
| **P0** | #2 | 실행 가능성 | 존재하지 않는 SDK API (`anthropic.beta_tool`, `messages.tool_runner`)와 발명된 모델 ID로 **하네스 자체가 import 불가** |
| **P0** | #7/#8 | CI/매니페스트 | 두 PR 모두 base 브랜치에 이미 적용된 변경을 재적용 + **`change_id` 중복(`CHG-0078/79/80/81`)** 으로 매니페스트 손상 |
| **P1** | #4 | 데이터 안전 | `data_safety_guard.scan_dataframe`이 `df.index`를 그대로 노출 → 인덱스가 고객번호면 **PII 유출** |
| **P1** | #5 | 검증자 정합성 | `risk_lib`는 PD 하한 **5bp**, `risk-validator.md`는 **3bp** — 검증자가 사일런트 패스 |
| **P1** | #3 | 범위/중복 | "docs-only" 라고 했으나 220 파일/+9213 줄 (pyproject, scripts, tests, 0-byte 바이너리 출력물). PR #4·#5 와 어휘 중복 (Action Notice, Gray taxonomy) |
| **P1** | #10 | 메모리/그래픽스 | `InstancedMesh.dispose()` 오용 — 블록 편집 시마다 GPU 버퍼 유출, 장시간 플레이 시 성능 저하 |
| **P1** | #6 | 트레이딩 안전 | 거래 의사결정 템플릿인데 LLM이 `entry_price`/`stop_loss`를 **계산 없이 환각하는 것을 막는 가드 0** |
| **P2** | #9 | 핸드오프 | "Handoff contract" 가 사실은 산문 체크리스트 — 기계 검증 불가 |
| **P2** | #4 | 메트릭 편향 | PSI 산출 시 양쪽 `pct`를 1e-4로 clip → 규제용 지표가 비대칭 왜곡 |

---

## PR #2 — 주식 트레이딩 에이전트 하네스 (`claude/stock-trading-agent-harness-ZuSJc`)

### 요약
4-에이전트 트레이딩 데모. 안전 가드(DRY_RUN 기본, `STOCK_TRADING_LIVE=1` opt-in, 3중 승인, iter cap) 설계 자체는 좋음. 그러나 코드가 **실행 불가** 상태.

### Critical
1. **존재하지 않는 SDK 사용** — `from anthropic import beta_tool` (`market_analyst.py:5`), `_client.beta.messages.tool_runner(...)` — `anthropic>=0.40.0`에서 이런 공개 API가 없음. 하네스 import 시점에 실패.
2. **발명된 모델 ID** — `claude-sonnet-4-6`, `claude-opus-4-7` (`harness.py:170` 등). 실제 호출 시 404.
3. **승인 게이트가 prompt-injection 으로 우회 가능** — `harness.py:114-117` 에서 analyst 파싱 결과의 `verdict=="APPROVED"` 만 검사. 신뢰 불가 뉴스 본문에 `"verdict":"approved"` JSON 객체가 들어오면 게이트 해제.

### Major
- `except (anthropic.APIError, Exception)` 패턴 (`market_analyst.py:121` 등) — `Exception`이 모든 것을 삼킴, 디버깅 불가.
- `compute_var` (`tools.py:170`)와 `get_price` (`tools.py:36`)가 호출마다 `random.uniform` 으로 다른 값 반환 — 같은 평가 안에서도 risk 수치 비결정.
- Trader 시스템 프롬프트가 "Risk Manager 와 Portfolio Manager 의 승인" (`trader.py:23`) 만 명시 — Market Analyst 누락 (오케스트레이터의 3중 게이트와 모순).
- `last_text`가 마지막 메시지의 끝 블록만 캡처 (`harness.py:194-196`) — 분석이 그 이전 턴에 있으면 빈 리포트.

### Strengths
- 다단계 안전 사고(DRY_RUN + opt-in env + 게이트 + iter cap) 디자인.
- `_PORTFOLIO_LOCK` 으로 10 concurrent buys 현금 보존 테스트 — 좋은 발상.
- `<untrusted_news_item>` 봉투 + 시스템 프롬프트 정렬 — prompt-injection 하든닝 패턴 정공.

---

## PR #3 — 양적검증 팀 에이전트 운영 패키지 (`codex/improve-operational-package-for-agent-team`)

### 요약
한국어 은행 양적검증 팀 운영 문서 세트. 14개 마크다운 + 인프라/스크립트/테스트/0-byte 출력 바이너리 포함 (실제 220 파일, +9213 줄). 무계산 / 인간 승인 가드 규율은 매우 우수.

### Critical/Major
- **스코프 미스매치**: "docs-only" 가 아님. `pyproject.toml`, `.editorconfig`, `scripts/`, `tests/`, `outputs/*.pdf|.xlsx|.hwpx` (0 byte) 포함.
- **PR #4·#5 와 어휘 중복** — Action Notice / Gray taxonomy / validation_object_type 가 다른 경로에서 다른 의도로 정의됨. 통합/명시 cross-ref 필요.
- **`provisional_judgement` enum 불일치** — `ROLE_MAP.md`는 `"Not assessed"` 허용, `REPORT_TEMPLATE.md`/`JUDGEMENT_POLICY_TEMPLATE.md` 는 `Green|Yellow|Red|Gray` 만 허용.
- **YAML 핸드오프 스키마 비공식** — 필수/옵션 미표시, enum 미지정, `audit_trail_items: []` 항목 스키마 없음.
- **재현성 루프 미완결** — 동일 fingerprint 의 과거 결과 조회처 미지정 (`result_store_reference` 부재).
- **`required_action_notice: true` 가 기본** — Green 조건 위반.

### Minor
- `.editorconfig` 가 `*.md` 에 BOM 강제 — 다른 PR 과 churn.
- `ACTION_NOTICE_TEMPLATE.md` §5 가 체크 마크 (`✓`)를 템플릿에 하드코딩 — 입증 필드의 의미 무력화.
- 공통 가정 블록이 6개 파일에 verbatim 복제.

### Strengths
- 무계산/인간 승인 가드의 일관성 — SYSTEM_PROMPT, WORKFLOW, ROLE_MAP, JUDGEMENT, METHOD_GUIDE, NOTICE 모두 동일 금지 반복. UAT-02/06/10 가 직접계산 거부 케이스 명시 검증.
- Gray taxonomy 6 코드 (`POLICY_UNDEFINED`, `DATA_INSUFFICIENT` 등) — 구체적이고 체크 가능.

---

## PR #4 — Validation Team Agent 하니스 스캐폴드 (`claude/validation-team-agent-Pw9F5`)

### 요약
~298 파일, ~110 테스트 파일 (description 27건과 불일치). 핵심 메트릭 (KS/AUC/CDR) 공식은 textbook-correct. 그러나 over-engineered + 규제용 PSI 편향 + PII 누수 위험.

### Critical
1. **PSI epsilon floor 가 지표를 왜곡** — `tools/metric_psi.py:55-62`. `e_pct`·`a_pct` 양쪽을 1e-4 로 clip → 양쪽 인구가 있을 때도 clipped 값으로 log·diff 산출, 비표준. 표준은 0 카운트 셀에만 Laplace smoothing. 규제 노출 지표가 사일런트 변형.
2. **`check_residual_basic`이 excess kurtosis 를 `kurtosis` 로 명명** — `tools/regression_diagnostics.py:88`. 정규 잔차에서 ~0 을 반환 (사람은 ~3 기대).
3. **`scan_dataframe` PII 누수** — `middleware/data_safety_guard.py:108`. `df.index` 가 고객 ID 면 `int(idx)` 가 그대로 라벨에 노출. positional row 번호로 한정해야 함.
4. **`run_logger` 회전 race** — `:35-49`. size check → rename → 별도 프로세스가 그 사이 회전하면 회전된 새 파일에 append. `logging.handlers.RotatingFileHandler` 사용 또는 single-writer 가정 명시.
5. **`permission_guard` 가 enforcement 가 아닌 reporting** — `middleware/permission_guard.py:9-12` docstring 이 자인. CI 가 `clean: false` 에서 실패하도록 와이어링 필요. 카드번호 정규식 `(?:\d[ -]*?){13,19}` 가 전화번호도 매칭.

### Major
6. PR 설명 "27 pytest tests" vs 실제 110 테스트 파일 — `test_v2_round22..64.py` 같은 iteration artifacts 다수. 정리 필요.
7. `change_manifest.json` 1940줄 시드 — 관측 로그의 의미 상실. 빈 배열로 출발.
8. `handlers/registry.py` 905줄 god-object — 도메인별 분리.
9. `leakage_guard` 의 `^_after$` 패턴이 합법 feature (`payment_after_grace_period`) 까지 차단.
10. KS docstring 방향성 (`높을수록 위험`) vs 구현 — 결과 자체는 대칭이라 OK 지만 반환된 `threshold` 의 임계 해석 방향이 사용자 기대와 다를 가능성.

### Strengths
- KS/AUC/Gini/CDR 공식 textbook-correct.
- 결정적 메트릭 테스트 (`test_metrics_are_deterministic`) 의 의미.
- `scan_text` 가 원본 매치 미반환 — span 만.
- `change_manifest.schema.json` 잘 구조화 (evidence/root_cause/rollback_rule).

---

## PR #5 — Basel III / FSS 리스크관리 하니스 (`claude/risk-management-agent-harness-B9Kxm`)

### 요약
10 specialist subagents (description 8) + ~95 파일 `risk_lib` (SA/IRB RWA, BIS, PD/LGD, IFRS9 ECL, ALM, ICAAP). 핵심 공식은 대체로 정확하나 **Basel SA 매핑 테이블에 명백한 오류** — 규제 자본 과소 산정.

### Critical
1. **SA 기업 RW 표가 CRE20.41 위반** — `risk_lib/capital/rwa_sa.py:42-50`:
   ```python
   _RW_CORPORATE = {"AAA-AA":0.20, "A":0.50, "BBB":0.75,
                    "BB":1.00, "B":1.00, "CCC-":1.50, ...}
   ```
   개정 SA(2023)는 B등급 = **150%**. 같은 결함이 `_RW_BANK_ECRA`(CRE21.10) — 은행 B는 **150%** 여야 함. 규제용 RW 가 50pp 과소.
2. **PD 하한 불일치** — 코드 `references.py:97` 는 `PD_FLOOR_BPS=5` (Basel III finalisation 기준 정확). 그러나 `.claude/agents/risk-validator.md` 체크리스트는 `pd_floor_3bp` (3bp). 검증자가 stale threshold 로 사일런트 PASS.
3. **Past-due 단순화** — `rwa_sa.py:138-139` 가 provision 무관 150%. CRE20.45 는 (a) provision ≥ 20% 면 100% / 50% (주택담보), (b) 그 외 150%. 인라인 코멘트가 자인. 최소 WARN 필요.
4. **Maturity adjustment PD→1 회귀 미검증** — `rwa_irb.py:73`. PD=0/1 경계는 `test_capital.py` 에서 한 번도 실행 안 됨 (PD ∈ {0.005..0.10}).

### Major
5. `fit_lgd_model` 의 LGD floor 가 예측에서만 적용 — 학습 데이터는 미바닥. AIRB segment floor (25%/10%/5%) 가 예측에서 cliff 생성.
6. `compute_rwa_irb` 가 LGD floor 미적용 — 사용자가 prompt만 따라가면 FIRB/AIRB 미준수.
7. Hosmer-Lemeshow `max(dof-2, 1)` — degenerate edge 에서 `nan` 대신 강제 dof=1, 기각률 inflate.
8. `pd_model.py:121` PSI 의 비대칭 clip (PR #4 와 같은 패턴).
9. `compute_rwa_sa` 가 CRM 을 RWA 에 곱셈으로 처리 — CRE22 의 E* 식이 아님.

### Strengths
- 스칼라/벡터 parity (`irb_capital_requirement` vs `irb_k_vector`) — `tests/test_vector_parity.py` 로 강제.
- `references.py`: 모든 상수가 `Citation(standard, section, note)` 반환. 감사 가능.
- IRB 자산 상관 R (corp/retail/mortgage R=0.15, revolving R=0.04) — CRE31 정확.
- Gini = 2·AUC-1 항등식 테스트.
- risk-validator 체크리스트 + FAIL ⇒ no submission 게이팅.

---

## PR #6 — TradingAgents 한국어 컴팩트 템플릿 (`codex/create-trading-agent-from-tradingagents-github`)

### 요약
133줄 단일 마크다운. TradingAgents 멀티에이전트 프레임워크의 컴팩트 요약 + JSON 스키마 + 역할 프롬프트. 거래 의사결정 문서인데 **안전 가드 0**.

### Critical/Major
- **무계산 가드 부재** — Analyst 프롬프트는 "근거 3개 이내 + action/confidence". LLM 이 `entry_price`/`stop_loss` 를 데이터 없이 환각.
- **스키마/프롬프트 불일치** — 공통 스키마는 `agent, ticker, action, confidence, rationale, size, entry_price, stop_loss, time_horizon, thesis, risks, invalidators, evidence` 요구. 그러나 역할 프롬프트는 이 필드 계약을 강제 안 함.
- **소유권 규칙 불완전** — `size`/`stop_loss` 는 Risk Manager 소유라 하나 Analyst 도 같은 스키마 사용. Analyst 의 `size` 출력 규칙 미정의.
- **`NEEDS_REVIEW` 라우팅 정의 안 됨** — HOLD with confidence<0.5 → `NEEDS_REVIEW` 라우팅 명시하나 `action` enum 에 없음.
- **`bias_resolution` 필드 미정의** — 라운드 4에서 참조하나 Risk Manager 출력 스키마 부재.
- **JSON-only enforcement 가 산문** — 파싱 실패 시 행동, retry, validator 미정의.

### Minor
- commit pin (`7c37249...`) 있으나 `as_of_date` 없음.
- Research Manager 가 라운드에 등장하나 §4 역할 프롬프트 미정의.
- 한국어 프롬프트가 Python 도크스트링 `"""` delimiter 사용 → 마크다운에서 literal 텍스트로 렌더.

### Strengths
- 매우 컴팩트 (133줄). 빠른 컨섬션.
- pinned commit SHA — 추적성.
- HOLD-as-default 안전 룰.

---

## PR #7 + #8 — Validation Team CI 경로 필터 수정 (`codex/fix-validation-team-agent-ci-workflow-issues[-uaix1g]`)

### 결론: **두 PR 모두 그대로는 머지하지 말 것. 둘 다 stale.**

- Base 브랜치 `claude/validation-team-agent-Pw9F5` 의 현재 `.github/workflows/validation-team-agent-ci.yml` 는 **이미 negated path 패턴 적용** + 설명 코멘트 포함. 두 PR diff 는 동일 변경을 stale base 위에 재적용 — 머지 시 기존 설명 코멘트 손실.
- **`change_id` 중복** — base 가 이미 `CHG-0078/79/80/81` 을 다른 변경에 사용 중. 머지 시 매니페스트에 중복 ID 생성, `tools.manifest validate` 시 실패 또는 의미론 손상. 다음 free ID 는 **CHG-0130**.

### PR #8 의 부가 가치 (`tools/ci_workflow_filters.py`)
- 좋음: idempotency, single-quote handling, reversed-order refusal 테스트 추가.
- 나쁨: `_event_block` 가 리터럴 `"  push:"` / `"\n\nconcurrency:"` 슬라이싱 — 세 번째 이벤트 (예: `workflow_dispatch`) 추가 시 `ValueError`. `_negate_path_line` 의 `strip('"').strip("'")` 가 따옴표 양식 단일화. 코멘트가 `paths-ignore` 사이에 끼면 `startswith("-")` 필터로 제거됨.
- 더 견고한 fix: `ruamel.yaml` 의 round-trip 보존 사용.

### 권고
- **PR #7 close** (PR #8 에 흡수됨, 테스트 더 약함).
- **PR #8 rebase** onto current base, YAML 변경 hunk 제거 + 매니페스트 entry 4건 제거 + CHG-0130 부터 신규 ID로 tool/test만 기록. checker/fixer 는 `_event_block` 견고화 후 보존.

### Strengths
- GitHub Actions 의미적 fix 자체는 정확 (`paths` 안 negated `!` 패턴).
- PR #8 의 idempotency 테스트 디자인.
- CI 가 PR 분기에서 통과한 것은 `tools.manifest validate` 가 `change_id` 유일성 미강제 — **이게 별도 잠재 버그.**

---

## PR #9 — 전역 리스크 리서치 하니스 (`claude/global-harness-enhancement-1v9b78`)

### 요약
8개 `.claude/agents/*.md` + `AGENTS.md` 포인터 (도구 중립 단일 소스) + 런북 (G1-G5 게이트) + `team.yaml` + source-map + HTML 템플릿 + 샘플 보고서. 내부 일관성과 게이트 디자인은 강함. 그러나 "handoff contract" 가 사실은 체크리스트.

### Critical
1. **핸드오프 "계약" 이 구조화 스키마 없음** — `.claude/agents/academic-literature-analyst.md:42-49`, `bank-case-study-analyst.md:97-106`, `quant-risk-methodology-analyst.md:395-402` 모두 산문 + `(G3-1)/(G3-2)` 태그. 머신 검증 불가. 명시 필드 스키마 (마크다운 헤딩 또는 YAML 블록) 추가 또는 "체크리스트"로 리네임.
2. **G2 vs 충돌해소 Step 0 모순** — 런북 Step 3 은 T1-less 클레임에 (a) 범위 제외 또는 (b) open questions 강등을 명시. Step 0 충돌 프로토콜은 G2 로 반려. 다른 처치. 샘플 보고서는 demote+conflict log 하이브리드 — 어느 조항도 명시 안 함.

### Major
- **리뷰어 verdict 가 샘플에서 미사용** — `evidence-quality-reviewer.md:236-242` 가 `VERDICT: pass | pass-with-edits | revise` 첫 줄을 의무화하나 샘플은 `rapid-scan 리드 자체 점검 ...` — VERDICT 토큰 없음.
- **Evidence-tier 정의가 3개 파일에서 분기** — `source-map.md` vs `team.yaml` vs 리뷰어 체크리스트. 단일 정전 (probably `source-map.md`) 지정.
- **Spot-check 룰 under-specified** — "material" 정의 부재. Executive Summary 인용 클레임 등 구체화.
- **Freshness 규칙 fail criterion 부재** — 라이브 소스 차단(샘플의 403) 시 명시 fallback 없음. 샘플은 자발적으로 강등했지만 룰이 인가 안 함.
- **`team.yaml` 의 G2/G3 ownership 누락** — lead 가 G1/G4, reviewer 가 G5 만 소유.

### Minor
- AGENTS.md 가 codex 등에 frontmatter `tools:` 라인을 그대로 산문으로 노출하는 위험 미경고.
- 런북 게이트의 한/영 혼용 일관성 결여.
- `templates/report.html` 에 `.contested` 클래스 미정의 — 향후 충돌 보고서가 사일런트 스타일 손실.
- 샘플의 locator 가 `TBD (원문 403)` — G3 의 글자에는 부합하나 정신에는 미달.

### Strengths
- 단일 소스 레이아웃 — 드리프트 방지 효과.
- 충돌 해소 프로토콜 (tier → 최신성 → contested + log) 가 샘플에서 3 케이스 (X-001/002/003) 모두 실행됨.
- T1-less 의 C-007 강등이 런북 그대로 동작 — gate 가 e2e 작동 입증.
- rapid-scan 자체 점검 체크리스트 (`evidence-quality-reviewer.md:217-228`) 가 구체적이고 강제 가능.
- `team.yaml` 유효 YAML.

---

## PR #10 — 브라우저 마인크래프트 게임 (`claude/minecraft-game-tqv3ii`)

### 요약
단일 `minecraft/index.html` (2291줄) Three.js 복셀 게임. 섹션 코멘트로 잘 정리됨. AABB 충돌·DDA 레이캐스트·세이브 검증은 견고. 그러나 `InstancedMesh.dispose()` 오용으로 장시간 GPU 메모리 누수.

### Critical
1. **`InstancedMesh.dispose()` 오용** — `:576`, `:2096`. r160 의 `InstancedMesh.dispose()` 는 instance 버퍼만 해제 — geometry/materials (공유 싱글톤이므로 dispose 금지) 미해제. 블록 편집마다 최대 5 청크 리빌드 (`:629`) — 장시간 메모리 증가. `m.dispose()` 제거 후 `scene.remove(m)` 만 호출.
2. **Y 천장 충돌 stick** — `:1443-1445`. 위쪽 충돌 시 `p.y = prevY` 만 — `prevY` 도 침투면 `vel.y=0` 이라 중력 풀림까지 1프레임 stuck. 드물지만 낮은 천장에서 발생.
3. **`inv[type] <= 0` 가 undefined 슬롯에서 false** — `:1834`. 부분 저장 로드 시 `inv[type]` 이 `undefined` → `(inv[type] || 0) <= 0` 으로 수정.

### Major
- `pickMob`/collision 의 프레임당 6-element 배열 할당 — GC 압박.
- creeper 폭발의 5×5 청크 리빌드 — 100ms+ 프레임 스파이크.
- `makeTexture` 의 16×16 fillRect 256회 — `ImageData` 로 10× 가속 가능.
- `pickBlock` 레이캐스트가 water surface 에서 안 멈춤 — 물 위에 놓으려다 해저에 배치되는 UX 버그.

### Minor
- `dayTime` 이 오버레이 열려 있어도 진행.
- `saveGame` 의 silent catch (quota exceeded 무경고).
- `HARDNESS` 가 `BLOCK.LAVA` (15) 누락 — 도달 불가지만 fragile.
- `spawnY()` 이 dead assignment.

### Strengths
- 섹션 헤더 + 한국어 코멘트 구조.
- 세이브 로드 방어 검증 (`:2183-2212`) — seed/version 미스매치 시 그레이스풀 리셋.
- 몹 메시의 공유 geometry/material.
- Torch 라이팅이 fixed pool 5 PointLight + nearest pick — 좋은 FPS 관행.
- DDA 복셀 레이캐스트 (`:1719-1748`) — 텍스트북 정확.
- 액시스별 AABB resolve (`:1426-1449`) — 코너 snag 회피.
- Pointer-lock + touch + joystick + on-screen 버튼 + focus-blur key reset — 사려깊음.

---

## 권고 액션 매트릭스

| PR | 권고 |
|---|---|
| #2 | **Block-merge.** SDK API + 모델 ID 부터 실제 호환되는 것으로 교체. analyst verdict 추출 경로에 prompt-injection 가드 추가. |
| #3 | **Re-scope.** "docs-only" 표시 정정. PR #4/#5 와의 어휘 통합 결정. 0-byte 출력 바이너리 제거. enum 정합화. |
| #4 | **Request changes.** PSI 비대칭 clip 수정, `scan_dataframe` PII 누수 패치, run_logger 회전 단일 writer 강제, permission_guard CI 게이트 와이어링, 110개 테스트 파일 정리. |
| #5 | **Block-merge until Critical fixed.** SA "B" 등급 RW 표 수정, validator 의 PD floor 3→5bp 정합화, past-due 처리에 provision-aware 룰 또는 WARN, PD=0/1 회귀 테스트 추가. |
| #6 | **Defer or Block.** 트레이딩 결정 LLM 에서 가격/스톱로스 환각 방지 가드 필수. 스키마/프롬프트 계약 결합. |
| #7 | **Close.** PR #8 에 흡수됨. |
| #8 | **Rebase + revise.** YAML hunk 제거, manifest 신규 ID 할당 (CHG-0130+), checker fixer 의 `_event_block` 견고화. |
| #9 | **Iterate.** Handoff contract 를 구조화 (YAML/JSON 블록). G2/G3 ownership 명시. Tier 정전 단일화. Freshness fallback 명시. |
| #10 | **Iterate.** `InstancedMesh.dispose()` 제거, Y 천장 충돌 패치, `inv[type]` defensive init. 메모리 누수 패치 후 long-session 부하 테스트. |
| #11/#12 | **머지 1건만, 다른 1건 close.** 동일 1줄 변경 중복. |

---

## 교차 PR 관찰

- **PR #3, #4, #5** 가 모두 한국어 은행 리스크/검증 도메인을 다루지만 경로가 다름 (`quant_validation_team_agent/`, `validation-team-agent/`, `.claude/agents/`). 머지 전에 단일 패키지로 통합할지 명시 결정 필요. 그렇지 않으면 long-term 유지보수 부담.
- **PR #4 와 #5** 모두 같은 PSI 비대칭 clip 패턴을 가지고 있음 — 공통 metric lib 로 추출하면 한 번에 수정.
- **PR #4 의 `change_manifest.json` 시드 + PR #7/#8 의 change_id 충돌** — manifest 라이프사이클 정책(시드 vs 점진) 부재가 근본 원인.

---

_본 리뷰는 PR 단위 병렬 에이전트 7건 (총 ~500K 토큰 소비) 으로 수행되었으며, 각 PR 의 diff 와 핵심 파일 본문을 직접 읽고 작성됨. 머지 결정 전 각 PR 의 책임자가 위 Critical 항목을 우선 점검할 것을 권고함._
