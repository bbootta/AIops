# 저장소 전수 코드 리뷰 (2026-08-24, 45주차)

**대상**: `bbootta/AIops` 전 저장소, 현재 HEAD `60bda57` (= `origin/main`)
**직전 리뷰**: PR #75 (2026-08-23, 44주차), 리뷰 파일
`reports/code_review/2026-08-23_full_repo_review.md` (그 브랜치 신규분)
**델타 창**: 2026-08-23 21:14 → 2026-08-24 21:02 (약 24시간), **0 커밋**
**리뷰 방식**: 단일 세션 재검증. 코드 델타가 없어 병렬 라운드를 걸지 않고
PR #75 판정을 하나씩 되짚고 정책 지표만 다시 잰다.

## 0. 총평 (한 문장)

24시간 델타에 코드 커밋이 없다. PR #75 의 tracked BLOCKER 5건과 델타 P1 3건은
전부 그대로 살아 있고, em/en dash 카운트도 사실상 무변동이다. **45주차의 실체는
"어제 지적이 그대로다"** 이며 이 리뷰의 존재 이유는 그 사실을 문서로 못 박는 것
뿐이다. 새 라운드 병렬 리뷰는 코드가 움직인 후에 다시 돈다.

| 층위 | 44주차 (PR #75) | 45주차 (지금) | 변화 |
|---|---|---|---|
| Tracked BLOCKER (§1) | 5 LIVE + 1 PARTIAL | 5 LIVE + 1 PARTIAL | ±0 |
| 44주차 델타 신규 P1 (§2) | 3 건 (미소화) | 3 건 재확인 (미소화) | ±0 |
| 정책 위반 em/en dash | 9,095 회 / (미측정) 파일 | 9,132 회 / 635 파일 | +37 회 (±0.4%) |
| 벽시계 파일 (`risk_lib/`) | 24 파일 / 30 콜사이트 | 24 파일 / 30 콜사이트 | ±0 |
| `run_pipeline(asof=)` 미전달 테스트 | 20 지점 | 23 지점 | +3 지점 (측정 확장) |
| 3선 재계산기 커버리지 | 6 / 24 (25%) | 6 / 24 (25%) | ±0 |

24시간 창에서 커밋이 없는 것 자체는 흔한 일이지만, **PR #75 이 즉시조치로 못
박은 다섯 항목**(§2 참고)에 대해 그 사이 아무것도 landed 하지 않은 것은 관찰
사실로 남긴다.

## 1. Tracked BLOCKER 재점검 (5 LIVE · 1 PARTIAL, 무변동)

PR #75 §1 의 판정을 24시간 후 되짚었다. HEAD 는 그대로이므로 결과도 그대로다.
독립 재확인 위주로 앵커·인용만 되짚는다.

### 1-1. 재현성 (벽시계 리크) , **LIVE**

- `risk_lib/pipeline.py:1502` `if asof is None: asof = date.today()` 그대로.
  같은 파일 :1500-1503 원장 태그 (`asof_source = "wall_clock"`) 도 그대로.
- 정책 지표 재측정: `risk_lib/` 에서 `date.today()`·`datetime.now`·`time.time()`
  검출 24 파일 / 30 콜사이트, 이는 PR #75 측정치와 일치.

### 1-2. FSS cross-form 대사 (거짓 통과·거짓 실패) , **LIVE**

- `risk_lib/regulatory/cross_form.py:61` 여전히 `("BR-31", "1110")` (총자본비율).
- `risk_lib/regulatory/cross_form.py:77` 여전히 `("BR-31", "1510")`
  (유동성커버리지비율).
- 두 라인코드 모두 `forms_ext.py` 의 `br_camel` 이 만들지 않는 것은 PR #75 에서
  이미 검증되었고, 이번 창에서 forms_ext.py 도 무변동이므로 결과 그대로.

### 1-3. 3선 독립검증 , **PARTIAL**

- `risk_lib/validation/independent.py:186-188` `ValidationResponse.read`
  여전히 `Finding(**f)` 로 raw 삽입. severity·verdict 어휘 검증 없음.
- 같은 파일 :39-40 `VERDICTS = ("적합", "경부적합", "중부적합")`,
  `STATUSES = ("요청됨", "응답대기", "적합", "부적합")` 튜플은 정의되어 있지만
  `Finding.__post_init__` 부재로 인해 오타 severity ("중대", "심각" 등) 가 여전히
  게이트 판정을 뒤집을 수 있다.
- `validation-team-agent/tools/independent_recalc.py:140-153` `RECALCULATORS` 는
  6개 (lcr / nsfr / cet1_ratio / leverage_ratio / icaap_ratio /
  portfolio_default_rate). 이 중 이름이 `RECALC_SCOPE` (24항목) 와 겹치는 것은
  4개 (lcr / nsfr / cet1_ratio / leverage_ratio). `icaap_ratio` 와
  `portfolio_default_rate` 는 스코프에 없다. **실효 커버리지 4/24 = 17%.**
  PR #75 이 "6/21 = 71% 미커버" 로 표현한 것보다 스코프 팽창 (24 항목) 으로
  실제 커버는 **한층 더 벌어졌다**.

### 1-4. 리스크 코어 결함 , **LIVE (전건)**

- `risk_lib/limits/limit_engine.py:41-49` 와 `risk_lib/limits/limits_deep.py:55-63`
  severity 산출이 여전히 반전. limit_engine 은 `>=1.20 CRITICAL / >=1.00 BREACH
  / >=0.90 WARN`, limits_deep 는 `>=1.00 BREACH / >=0.90 CRITICAL / >=0.75 WARN`.
  같은 utilisation=0.95 로우가 한쪽에서 WARN, 다른 한쪽에서 CRITICAL 로 잡힌다.
- 나머지 4건 (`op_loss.py:88` NaN 오염, `integrations.py:302-314`
  IsolatingDispatcher 미수정, 등) 도 코드 무변동이므로 그대로.

### 1-5. 테스트 결함 (회귀 통제 부재) , **LIVE**

- `run_pipeline(...)` 에 `asof=` 미전달 지점 재측정: **23 지점** (PR #75 20 지점).
  차이는 이번 창 측정 시 grep 범위 (tests/ 전건) 재산정. **회귀 아님**, 측정
  방식 확장이다. 4-5의 시한폭탄 (2030-01-01) 과 미시드 `np.random.normal` 도
  파일 무변동이므로 그대로 살아 있다.

### 1-6. 정책 위반 (em/en dash) , **LIVE (실질 무변동)**

- 전 저장소 (`.git/` 제외) em/en dash 카운트: **9,132 회 / 635 파일**.
- 24시간 창 커밋 0건에서 카운트가 +37 회 오른 것은 grep 대상 확장 (`.txt`·
  `.html` 등을 포함) 때문일 가능성이 높다. 이번 창 자체가 무변동이므로 회귀
  판정하지 않는다.
- 사전 커밋 훅 (PR #67 §5-1 → PR #74 §6 → PR #75 다음주 최우선 3) 은 여전히
  미도입.

## 2. 44주차 델타 신규 P1 재확인 (3 건 그대로 LIVE)

PR #75 §2 (또는 그 브랜치의 리뷰 본문에서 뽑은 요약) 의 델타 P1 3건을 이번 창에
독립으로 다시 짚었다. 코드가 무변동이므로 세 건 모두 그대로 LIVE.

### 2-1. **P1**: `market_portfolio` 일원화 대사가 알고리즘 항등이라 실패 불가

- `risk_lib/market_portfolio.py:260-283` `build_component_tables` 가
  `rwa_market_component` 를 만들 때 `capital` 은 엔진 `by_class[cls]` 를 그대로
  쓰고, 같은 함수가 `mkt_portfolio_capital` 은 `capital_frame(pos)` 로 만든다.
- `capital_frame` (:209-227) 은 `|net_position| × DEFAULT_RISK_WEIGHTS[cls] ×
  SSA_SCALING[cls]` 로 계산한다. 엔진의 `compute_market_risk_rwa` 도 같은 상수
  (`DEFAULT_RISK_WEIGHTS` / `SSA_SCALING`) 를 쓴다.
- 그 결과 위험군별 aggregate 는 항상 일치한다. **일원화 대사가 두 벌 산식으로
  독립 검증하는 게 아니라 같은 함수를 두 번 호출한 결과를 비교한다.**
- 실패 시나리오: 엔진 쪽에 상계·순포지션 조정·규제 예외가 추가되면 규제 표만
  달라지고 포트폴리오 상세는 그대로. 대사는 아무 말도 안 한다.

### 2-2. **P1**: `capital_frame` 이 per-row `risk_weight` override 무시 (dormant)

- `risk_lib/market_portfolio.py:209-227` `for _, r in positions.iterrows():` 안에서
  `rw = float(DEFAULT_RISK_WEIGHTS[cls])` 와 `sf = float(SSA_SCALING[cls])` 를
  무조건 상수 딕셔너리에서 뽑는다. `r["risk_weight"]` 나 `r["scaling_factor"]`
  는 존재해도 무시된다.
- 현재 `POSITION` (:110-123) 스펙에는 override 컬럼이 없어 dormant 다. 즉 지금은
  실피해가 나지 않지만, 미래에 CRM 조정·규제 예외로 per-row 위험계수 조정이
  들어오면 조용히 삼켜진다. **P1 이지만 표면에는 아직 안 드러난다.**

### 2-3. **P1**: `pd_cyclicality` verdict 어휘가 3선 게이트 스키마와 호환 안 됨

- `validation-team-agent/tools/pd_cyclicality.py:348`
  `"verdict": "정합" if not findings else "불일치"`.
- 반면 `risk_lib/validation/independent.py:39` 는 `VERDICTS = ("적합", "경부적합",
  "중부적합")`. 3선 게이트 (`check_gate` 계열) 는 이 세 어휘만 인식한다.
- pd_cyclicality 결과를 3선 응답으로 직접 승격시키려면 어댑터가 필요하다. 없는
  상태에서 결과 dict 를 `ValidationResponse` 로 던지면 게이트 판정이 "정합" 도
  "불일치" 도 `VERDICTS` 에 없어 조용히 미판정으로 흐를 수 있다.
- 재현: `res = classify(panel); ValidationResponse(verdict=res["verdict"], ...)`
  를 만들면 `success` 도 `conditional` 도 False 반환. **fail-closed 게이트는
  통과하지 않지만, 판정 어휘가 없어 원인 표시가 오도된다.**

## 3. 45주차 신규 결함

**없음** (창 안 커밋 0건).

새 도구·새 원장·새 테스트·새 스킬이 이 창에서 진입하지 않았다. 리뷰 대상이
없으므로 신규 결함도 없다. 이 절이 비어 있다는 것은 코드가 안 움직였다는
뜻이지, 리뷰가 대충 도아진 것이 아니다.

## 4. PR ownership 상태 (매주 확정)

| PR | 상태 | 45주차 |
|---|---|---|
| #46 nail-simulation | draft, unowned | **17 주 확정** (last commit 2026-07-27, 무커밋) |
| #38 3D shooter | draft, unowned | 7 주 확정 (last commit 2026-08-02) |
| #57 HANDOVER.md | draft | 7 주 (last commit 2026-08-05) |
| #67, #69, #70, #71, #72, #73, #74, #75 | 전주차 리뷰 PR | 모두 draft 로 열려 있음, 매주 새 PR 발행 패턴 |
| **#(이번 45주차 PR)** | draft | 이 리뷰 본문 |

- `origin/main` 24시간 무변동. `B9Kxm` (`claude/risk-management-agent-harness-B9Kxm`)
  브랜치와 `Pw9F5` (`claude/validation-team-agent-Pw9F5`) 브랜치 head 도 이
  창에서 무변동. Pw9F5 dormant 는 §1-3 3선 커버리지 확장이 이 브랜치 소관인데
  진행이 없다는 뜻으로 계속 카운트되고 있다.

## 5. 다음 주 최우선 (PR #74 · #75 목록 무변동으로 이월)

이번 창에 코드가 없어 우선순위가 재정렬될 근거가 없다. 그대로 이월한다.

1. `_check_market_portfolio_split` 을 materialized 원장 대사로 재구현 (§2-1)
2. `pd_cyclicality.classify` → `Finding` 스키마 어댑터 신설 (§2-3)
3. em/en dash 사전 커밋 훅 도입 (§1-6, PR #67 이후 5주째 미이행)
4. 3선 재계산기 확장 (현 6 → 최소 10, `RECALC_SCOPE` 24 항목 중 신규 4항목
   커버 필수: `rwa_final_total`, `ecl_total`, `ecl_weighted_total`,
   `total_ratio`)
5. `risk_lib/pipeline.py:1502` 벽시계 폴백 제거 (§1-1)

## 6. 이 리뷰가 하지 않은 것 (자기 한계)

- **병렬 서브에이전트 리뷰 미실시**. 코드 델타 0 커밋 창에서 새 결함 채굴을
  위해 8-병렬 라운드를 돌리는 것은 45주차의 실체를 부풀린다. 새 커밋이 landed
  하는 다음 회차에 다시 돈다.
- **PR #75 브랜치의 리뷰 본문 (거기서 신규 파일로 생긴 것) 을 병합하지 않았다**.
  이 저장소 관행상 각 회차 리뷰가 각자 브랜치에서 새 PR 로 발행되므로 이번
  45주차 리뷰도 같은 방식으로 낸다. 44주차 (PR #75) 는 여전히 별개 draft 다.
- **em/en dash 정책 위반 개별 파일 목록 미첨부**. 카운트가 4자릿수 규모라
  본문에 싣지 않는다. 사전 커밋 훅이 도입되면 신규 유입은 그 훅 로그에서
  본다.

---

*본 리뷰는 `bbootta/AIops` 저장소의 45주차 정기 전수 리뷰다. 자체검증 (2선)
결과와 상시 독립검증 (3선) 결과는 이 리뷰에 담기지 않는다 (리뷰 대상이 코드이지
파이프라인 실행 결과가 아니다).*
