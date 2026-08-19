# 저장소 전수 코드 리뷰 (2026-08-19)

**대상**: `bbootta/AIops` 전 저장소, HEAD `60bda57` (branch `claude/stoic-ride-kn3cyh`)
**직전 코드 리뷰**: `reports/code_review/2026-08-14_full_repo_review.md` (43주차)
**리뷰 범위**: `risk_lib/` 전 268 Python 파일 (약 111K LOC), `tests/` 40개 파일 (약 99개 테스트 스위트), `tools/`
**리뷰 방식**: 10개 서브에이전트 병렬 (`capital`, `alm`, `models+credit_rating`, `validation+governance`, `regulatory`, `stress+provisioning+icaap+prudential`, `monitoring+limits+performance`, `root+tools`, `ui_studio+integration+ops_pages+datamodel`, `tests`)

## 0. 총평

리스크 라이브러리는 원장 우선 구조, 페일-클로즈드 게이트, 재현성 매니페스트라는 세 축을
일관되게 세우고 있다 (references.py 인용, ParamWarning/EVIDENCE_STATUS로 "비어 있음"이 산출물에
드러남, `check_gate`가 진짜 fail-closed로 작동, `audit_chain`이 tamper-evident). 리뷰가
확인한 것은 "이 구조가 지켜지는 곳에서는 실제로 안전하다"는 사실이다.

그러나 이번 리뷰에서 드러난 **43주차 이후 남아 있는 결함**은 다섯 가지 반복 패턴으로
수렴한다.

| 패턴 | 사례 | 성격 |
|---|---|---|
| 벽시계 리크 (재현성 위반) | `timeseries.py:62`, `report.py:43`, `report_chrome.py:144`, `pipeline.py:1500-1503` | ARCHITECTURE 조항 정면 위반 |
| 이중 엔진 병존 | multi_axis (신규 14축) vs evaluate_scenario (legacy ECL 기반), CCAR/climate/reverse 가 legacy 를 사용 | 같은 은행 같은 보고서 안에서 두 개의 CET1 궤적 |
| 항등식·조용한 폴백으로 검증이 실제로 검증하지 않음 | BR-08 tol swallow, `_check_stress_trough` required=0.0, `_headline` NaN→0.0, `_check_ec_covers_rwa` WARN 자기무력화 | "PASS n · FAIL 0" 이 사실이 아님 |
| 규제 상수 매직넘버 3중 복제 | BIS min 4.5%/2.5% 가 `attribution.py`, `mda.py`, `html_exec.py` 각각 복제 | 규제 변동 시 세 곳 중 한 곳이 남는다 |
| 보고서 계층이 도메인 엔진을 재호출 | `html_exec.py:405` MDA 재계산, `ops_pages/credit.py:999` CECL 재계산, `ops_pages/market_trading.py` XVA·intraday·IMA·NCR 재계산 | ARCHITECTURE 의 단방향 파이프라인 원칙 위반 |

가장 큰 시스템적 위험은 다섯 번째다: **6개 페이지(53·56·61·62·64)의 헤드라인 숫자가
`PipelineResult`를 통과하지 않고 렌더 시점에 즉석 계산된다**. `data_gen.generate_portfolio`
까지 페이지 안에서 부르는 경우가 있어 원 실행과 다른 시나리오의 값이 나올 수 있다. 43주차
리뷰가 지적한 6개 BLOCKER 는 이번 리뷰에서 5개가 다른 각도로 재발견됐다 (§1 참고).

이번 리뷰의 CRITICAL 15건 · HIGH 45건 · MEDIUM 51건 · LOW 20건은 전 도메인에 분산돼
있다. 우선 조치 순서는 §7.

## 1. CRITICAL 우선 조치 (15건)

각 항목: `[영역] file:line, 한 줄 요약` + 실패 시나리오 · 최소 수정. 상세 근거는 §2~§5.

### 1-1. 자체 검증 게이트 우회 가능

```
[validation] risk_lib/validation/independent.py:691, recalc_matches가 truthiness로 판정
```
`mismatched = [k for k, ok in resp.recalc_matches.items() if not ok]`. JSON `false` 는
`False` 로 파싱되지만, 3선 응답 파일은 사람이 편집 가능하므로 `"false"` (문자열) 이
들어오면 `not "false"` 는 `False` → 불일치가 필터에서 빠지고 게이트가 "독립 재계산 일치"
로 통과한다. **fail-closed 게이트가 실제로 열림**.
**수정**: `read_response` 진입점에서 `bool(v)` 강제 형변환하되, 원 값이 `bool`이 아니면
응답 자체를 `부적합`으로 거부한다.

### 1-2. Basel III 상수 위반 (수치 잘못 산출)

```
[models] risk_lib/models/pd_model.py:29, Basel III 0.03% PD 하한 미강제
```
`predict_pd` 는 `[1e-6, 1-1e-6]` 로만 클리핑. `DEFAULT_MASTER_SCALE[0].pd_midpoint = 0.00015`
(=1.5bp) 이므로 AAA 차주의 PD 는 CRE32.11 (0.03%) 보다 5배 낮게 나온다. RWA·EL 이 최고
등급에서 조직적으로 과소산정.
**수정**: `PD_REGULATORY_FLOOR = 0.0003` 를 도입하고 `predict_pd` 에서 클립. AAA 하한을
0.0003 로 올리거나 sovereign 을 별도 등급으로 분리.

```
[models] risk_lib/models/lgd_model.py:42-57, segment=None 시 5% 하한이 조용히 적용
```
`lgd_floor_for_segment(None)` = 0.05. `fit_lgd_model` 의 기본 `segment=None` 이라서
호출자가 segment 인자를 잊으면 CRE32.42 (retail_other 10%, 무담보 corporate 25%) 위반이
경고 없이 발생.
**수정**: `segment` 를 required kwarg 로. 미지원 segment 는 raise. sentinel 은 가장 보수적인
25% 로 바꾸거나 제거.

```
[capital] risk_lib/capital/rwa_sa.py:44, 회사채 "B" 등급이 100% RW (150%가 맞음)
```
`_RW_CORPORATE["B"] = 1.00`. CRE20.36 회사채 ECRA 표에서 "BB+ to BB-" 는 100%, "Below BB-"
가 150%. 코드가 "BB" 라벨로 BB+~BB- 를 담고 있으므로 "B" 는 B+ 이하 (150%) 여야 한다.
KRW 1조 B등급 회사채 RWA 가 1.0조 대신 1.5조여야 한다.
**수정**: `_RW_CORPORATE["B"] = 1.50`.

### 1-3. 스트레스 이중 엔진 (multi_axis vs legacy), 같은 은행에 두 개의 궤적

```
[stress] risk_lib/stress/multi_reverse.py:134-143, CET1/Tier1 역스트레스가 credit-only 엔진 사용
```
`run_multi_reverse` 가 `reverse_stress(..., axis=StressAxis())` 를 호출 → GDP/LGD 만 충격.
시장·운영·CCR RWA·수익 축이 정지 → 임계 심도가 실제보다 훨씬 위에서 잡힘. ARCHITECTURE
가 명시한 "2.35 vs 0.94" 버그 아키타입. `solve_critical_severity` 는 이미 존재.
**수정**: `reverse_stress` 호출 두 곳을 `solve_critical_severity(books, metric=…)` 로 교체.

```
[stress] risk_lib/stress/ccar.py:163-186, CCAR가 ECL을 CET1에서 직접 차감 (이중계상) 및 max 축적
```
`cum_ecl_uplift = max(cum_ecl_uplift, ev["incremental_ecl"])`; `cet1 = base.cet1 -
cumulative_ecl_uplift`. 충당금 전입이 세금 방패·수익 상쇄 없이 CET1 총액을 직격 →
multi_axis 가 방지하려던 이중계상. "cumulative" 가 러닝 맥스라 정점 이후 감쇠구간에서
정점 ECL 이 CET1 에 얼어붙는다.
**수정**: `run_ccar` 를 `StressBooks` 로 리라이어링해 `evaluate_point` 를 통과시키거나,
최소한 세후 이익 델타로 롤포워드. `max` 제거.

```
[stress] risk_lib/stress/climate_capital.py:120-125, NGFS 기후 시나리오도 ECL 기반 CET1 차감
```
동일한 이중계상 패러다임. 30Y 기후 CET1 궤적이 14축 발표치와 비교 불가.
**수정**: 기후 충격을 `StressBooks`/severity 로 접고 `evaluate_point` 통과시키거나, 최소한
세후 이익 델타로 롤포워드.

### 1-4. 이중 severity 사다리, 같은 이벤트가 서로 다른 기관에 에스컬레이션

```
[limits] risk_lib/limits/limit_engine.py:39-47 vs limits_deep.py:55-62
```
LimitEngine: OK<0.90 / WARN 0.90-1.00 / BREACH 1.00-1.20 / CRITICAL≥1.20.
limits_deep: OK<0.75 / WARN 0.75-0.90 / CRITICAL 0.90-1.00 / BREACH≥1.00.
유틸 0.95 가 대시보드는 CRITICAL, 운영 화면은 WARN. `escalation_matrix` 가 CRITICAL 을
CRO+위원회로 라우팅하므로 **같은 이벤트가 진입점에 따라 다른 기관에 상신**.
**수정**: 하나로 통합 (권장 `limits_deep` 사다리, 에스컬레이션 매트릭스와 일치).
`LimitBreach.severity` 도 공유 `_severity` 호출.

### 1-5. NPL·부도 정의가 UTP 배제 (헤드라인 과소보고)

```
[monitoring] risk_lib/monitoring/delinquency.py:80-95, deep.py:98-128, is_npl이 UTP arm 무시
```
헤더에는 "DPD>=90 OR default_12m==1 (UTP 포함)"이라 명시. 구현은
`is_npl = df[dpd_col] >= threshold` 만. Basel CRE36.68 와 감독세칙이 OR 을 요구.
Forbearance/UTP 플래그가 있는 dpd<90 차주 (리스케줄, 조기위험) 가 NPL 에서 빠진다.
**NPL 비율·부도율·IFRS9 Stage 3 카운트 모두 과소보고**.
**수정**: `is_npl = (df[dpd_col] >= threshold) | (df.get("default_12m", 0) == 1)`.

### 1-6. 보고서 계층에서 도메인 엔진 재호출 (아키텍처 위반 + 헤드라인 흐트러짐)

```
[ops_pages] risk_lib/ops_pages/credit.py:999, page_cecl_ifrs9가 CECL 재계산 (portfolio 없으면 합성)
[ops_pages] risk_lib/ops_pages/market_trading.py:585, page_intraday가 tick VaR 즉석 생성
[ops_pages] risk_lib/ops_pages/market_trading.py:183, page_xva_full이 compute_xva_portfolio 호출 (maturity=3.0 하드코딩)
[ops_pages] risk_lib/ops_pages/market_trading.py:471, page_frtb_ima가 HPL/RTPL 합성, ES=5e9·SA=8e9 리터럴로 IMA 자본 발표
[ops_pages] risk_lib/ops_pages/market_trading.py:682, page_ncr가 "전월" NCR을 합성 회사로 재산정
```
**리포트 페이지 5장의 헤드라인 숫자가 `PipelineResult` 를 통과하지 않는다**. IFRS9-CECL
브릿지가 두 개의 서로 다른 실행에서 뽑힌다. XVA 만기 3.0 이 렌더러 안에서 하드코딩.
IMA 자본 이 파이프라인 출력과 무관한 리터럴 위에 서 있다.
**수정**: 각 도메인을 파이프라인 stage 로 옮겨 `PipelineResult.{cecl,xva,intraday,ima,ncr_history}`
에 pin. 페이지는 `r.*` 만 읽음.

### 1-7. 벽시계 리크 (43주차 리뷰가 이미 지적, 여전히 LIVE)

```
[root] risk_lib/timeseries.py:62, pd.Timestamp.now()가 KRI back-history의 월 라벨을 생성
[root] risk_lib/report.py:43 + report_chrome.py:144, date.today()가 모든 보고서 푸터에
[root] risk_lib/pipeline.py:1500-1503, pipeline entry가 caller가 asof 생략 시 date.today() 사용
```
CLAUDE.md 의 "identical (seed, asof) → identical outputs" 불변식을 정면 위반. 같은
seed, 같은 pipeline 실행이라도 렌더링 날짜가 달라지면 report HTML 바이트가 달라진다.
CLI subcommand 8개 (`run`, `report-set`, `notify`, `serve`, `export-json`, `printable`,
`dispatch`, `api-spec`) 가 `--asof` 를 노출하지 않아 **벽시계 branch 가 사실상 기본값**.
**수정**: (a) `timeseries.py` 는 `raf.asof` 를 인자로 받음, (b) `report.py`/`report_chrome.py`
는 `result.meta['asof']` 를 읽음, (c) `pipeline.py` 는 `asof` 필수화 또는 `strict=True`
때 raise, (d) 모든 CLI subcommand 에 `--asof` 노출.

### 1-8. Score card 학습/스코어링 median imputation 불일치

```
[credit_rating] risk_lib/credit_rating/scorecard.py:519 vs 623
```
`fit_scorecard` 는 dev frame 의 `nanmedian` 으로 impute, `score_obligors` 는 scoring frame
의 `nanmedian` 으로 impute. **같은 원시 입력이 시간에 따라 다른 스코어를 만든다**, 조용한
학습/서빙 skew + 현재 book 에서 스코어로의 미약한 데이터 리크.
**수정**: fit 시점 median 을 `ScorecardFit` 에 저장, `score_obligors` 에서 재사용. imputation
행 수 카운터/경고 노출.

### 1-9. 크로스 등록 무결성 파괴

```
[models] risk_lib/models/explain.py:114-118, grade_transition_matrix가 obligor_id로 아닌 위치로 절단
```
`g0 = grades_t0.iloc[:n]; g1 = grades_t1.iloc[:n]`. 호출자가 t0/t1 을 따로 필터해서 넘기면
서로 관련 없는 차주끼리 pairs 되어 그럴싸한 (그러나 사실 아닌) 전이행렬이 나온다. 모니터링·
감사에서 사용.
**수정**: obligor_id 를 공동 인덱스로 요구. `pd.DataFrame({"g0":..., "g1":...}).dropna()`.

---

## 2. HIGH, 도메인 정확성 (45건 요약; 세부는 `scratchpad/reviews/`)

### 2-1. 자본 (capital), 6건
- **`rwa_sa.py:270-283`** `standardised_rwa_total` 이 mortgage LTV NaN 을 조용히 0.8 로
  채워 **output floor 분모에 그대로 흘러감**. 실제 LTV=0.95 (→50%) 인데 30% 로 잡혀 floor
  이 40% 과소. → `raise ValueError`.
- **`rwa_sa.py:56,126-127`** past-due 150% 를 residential mortgage 포함 자산군 전체에 적용.
  CRE20.75-76 은 provision ≥ 20% 시 100%, CRE20.86 은 mortgage 별도 처리. → 자산군별 분리.
- **`leverage_deep.py:69,73-82`** SA-CCR α (1.4) 가 PFE 에만 적용, RC 에는 미적용. SA-CCR
  (CRE52) 도 LR (LEV30) 도 모두 RC+PFE 양측에 같은 배수. **레버리지 분모 과소, LR 비율 과대**.
- **`bis_deep.py:243-267`** 존재하지 않는 AT1/T2 상한 (`at1_cap_ratio=1.5/4.5`) 을 조작.
  Basel III finalisation (CRE10.4) 은 이 상한을 폐지. AT1 이 많은 은행에 대해 잘못된
  "at1_excess" 절단.
- **`bis_deep.py:637-641`** DTA 가 이중 차감 가능. `total_deductions` 에 이미 `dta_excess` 가
  포함돼 있는데 caller 가 `threshold_inputs["dta_temporary_diff"]` 도 넣으면 같은 DTA 가
  두 번 CET1 을 깎는다.
- **`bis.py:127-147`** `synthesise_capital` 이 정당한 규제 근거 없이 (`PAID_IN_CAPITAL=5e11`
  등) 발행액을 조작. capital 원장 없이 pipeline 이 호출되면 픽션 값으로 발표 가능. →
  `allow_fallback=True` 뒤로 이동, 결과에 "SYNTHETIC" 라벨.

### 2-2. ALM (자산부채), 8건
- **`cashflow.py:206`** `[lower, upper)` 슬로팅. 규정과 다른 모듈들 (`liquidity.py`,
  `kr_irrbb.py`, `nsfr.py`) 은 `(lower, upper]`. **경계 만기가 `alm_cashflow_bucket` 과
  `alm_maturity_ladder` 에서 다른 버킷으로 들어감**. 3M 정각 리셋 부동금리 대출이 3M-6M vs
  1M-3M 로 분리. → `side="left"`.
- **`cashflow.py:244`** 부동금리 + `next_reset_date=NULL` 이면 고정금리 브랜치로 흘러가
  자산 duration 을 과대. synthetic contracts 가 reset 을 늘 채워 테스트 미검출. → NULL
  reset 은 raise (또는 최단 버킷 슬로팅 + warning).
- **`nsfr.py:181-183`** `maturity_band_of` 도 `[lower, upper)`, 6M 정각 잔액이 6to12m
  (RSF 50%) 로, 1Y 정각이 mortgages_ge1y 로 밀림 → NSFR 조직적 과소보고.
- **`lcr.py:361`** 계약원장 경로에서 asset side 30일 인플로우 전체를 `wholesale_inflows`
  (50%) 로. Interbank 는 100% 여야 함. product_code 에 정보 있는데 미사용. → 계약자
  분류로 라우팅.
- **`irrbb.py:580, 593`** `warnings.warn` (stdlib) 사용 → ParamWarning 흐름 우회. auto-option
  건너뜀이 결과 객체에 남지 않아 3선/validator 가 이유를 알 수 없다.
- **`irrbb.py:720-729`** `_LEDGER_CACHE` 가 모듈 전역 mutable dict. caller 가 반환 프레임을
  변경하면 이후 legacy 호출 모두 오염. defensive copy 없음.
- **`balance_sheet.py:114-119`** jitter 로 `other_assets` 가 음수 가능. NSFR RSF 에 흘러감.
- **`curves.py:453`** `Curve.rate` 가 첫 노드 미만 t 에서 z(first_tenor) 를 강제 → 시나리오
  형태 (short_up/steepener) 를 sub-node 구간에서 상실.

### 2-3. 검증 · 거버넌스, 7건
- **`independent.py:337-363`** `_headline` 이 누락된 subdomain 을 0.0 으로 치환. 파이프라인이
  subdomain 을 건너뛰면 request 가 0.0 을 실제 값처럼 실음, 3선 재계산도 0.0 → 매칭 통과.
  fail-closed 가 사실상 fail-open. → 누락 시 None 반환 (스키마에 이미 지원됨).
- **`unified_run.py:105-110`** `_fingerprint` 가 shape 만 (`table_name, n_rows, n_cols`) 해시.
  두 실행이 shape 만 같으면 identical run_fingerprint. docstring 자체가 "두 실행이 같은지
  한 값으로 대조" 를 약속. `retention._fingerprint` 는 CSV 내용을 올바르게 해시하는데
  대조가 되어 있다.
- **`audit_chain.py:118-147`** `verify_chain` 은 존재하는데 승인 게이트에서 호출하지 않는다.
  기록 후 위조된 행이 여전히 옛 해시로 통과 (누군가 검증을 명령으로 부르지 않으면).
- **`consistency.py:56-82`** `_check_pd_bounds` 가 `pd == 0` 을 통과. Basel IRB 는 PD=0 불가
  (CRE31.7). 등급 전체가 실수로 0 이 되면 sanity 통과, K=0, RWA=0.
- **`consistency.py:459-479`** `_check_market_op_rwa` 가 `total_ead` 미전달 시 `op_rwa=0`
  을 PASS. 라이브 은행에서 op_rwa=0 은 있을 수 없음.
- **`consistency.py:1281-1301`** `_check_stress_trough` 가 required CET1 을 0.0 으로 폴백.
  Pillar 2 미배선 시 임계선이 조용히 0 이 되어 모든 스트레스 CET1≥0 이 통과.
- **`consistency.py:1424-1436`** `_check_pillar2_evidence` 가 `meta["pillar2"]` 없으면 아무
  것도 emit 하지 않고 return. "안 돌았다" 와 "통과했다" 가 구분되지 않는다.
- **`independent.py:44-103`** RECALC_SCOPE 누락 항목 6종: `output_floor_add_on`, `tier1_ratio`,
  `bis_buffer_shortfall`, `hhi_max`, `icaap_utilisation`, `alm_bs_equity`. 이 헤드라인들은
  3선이 다시 계산하지 않는다.

### 2-4. 규제 서식 (regulatory), 6건
- **`forms.py:379`** BR-08 순현금유출 대사가 `tol=float(lcr.inflow_capped) + 1.0` 로
  구조적으로 통과. line 4000 에 gross_outflow 를 잘못 넣어도 diff=0 이라 pass.
- **`cross_form.py:56`** 보통주자본비율 invariant 이 as-of vs stress trough (baseline scenario)
  를 비교. 현재만 우연히 일치, iteration order 나 baseline 재계산 rounding 에 취약.
- **`cross_form.py:98`** `cross_form_checks()` 테스트 커버리지 0 (grep tests/ = 0 hits).
  studio.py 만 호출. F-701 remediation 의 취지 자체가 무효.
- **`forms.py:519, 512`** BR-11 primary reconciliation 이 자기참조 (`대손준비금 = 최저적립액 −
  충당금` 양변이 같은 dict 에서). docstring 이 "자료로는 틀릴 수 없다" 를 인정 (F-602/F-702).
- **`forms_fss_liquidity.py:433-475`** B2602-2 일별 LCR 앵커 체크가 tautological. `path[-1] =
  lcr.lcr` 이므로 양변이 같은 소스. B2602-1/2/3 세 곳 모두.
- **`forms.py:895-917`** `submission_digest` 가 검증 시트 (checks) 를 해시에 포함하지 않음.
  FormCheck 추가/삭제해도 digest 불변 → digest 로 verify 하는 리뷰 경로가 check regression
  을 놓친다.

### 2-5. 스트레스 · 충당, 4건
- **`multi_axis.py:326-334`** output floor 분모가 `books.sa_bucket_by_grade` 미채움 시
  조용히 `internal RWA` 로 폴백 → **floor 가 절대 구속되지 않는 착시**. 파이프라인은
  채우지만 임의 호출 (테스트, 노트북) 이 빠뜨림.
- **`multi_axis.py:208`** ECL 가 IRB-only. SA book 이 stress 로 rating migration/LTV lift/
  EAD uplift 되어도 ECL 에 안 잡힘 → provision 과소, net_income 과대, CET1 과대.
- **`multi_axis.py:227`** `sa_base = ... or 1.0`, sa_base 가 진짜 0 (전량 IRB book) 이면
  `ccr_multiplier` 가 KRW 원자 값이 되어 CCR RWA 와 곱해짐. base 재현 파괴.
- **`provisioning/ecl.py:155-177` + `macro.py:326`** SICR 역방향 이행 즉시 반영, cure 기간
  없음. IFRS 9.5.5.7 은 SICR 미충족 지속 후 이행 요구, BCBS 는 3~6개월 관찰 기간 권고.
- **`stress/reverse.py:78-84`** reverse-stress 분모가 market/op/CCR RWA 를 정지. 임계 심도
  underestimate (§1-3 의 multi_reverse 문제와 같은 뿌리).

### 2-6. Models · Credit rating, 4건
- **`lgd_model.py:88-101`** `LGDModel.predict_lgd` 가 downturn LGD 없음. CRE32.7 위반.
  현재의 반환값을 `predict_central_lgd` 로 개명하고 `predict_downturn_lgd` 를 추가.
- **`lgd_model.py:43-50`** segment floor 표가 자기 코멘트에서 이미 "2018-04-12 FSS
  workshop 표와 불일치" 를 인정하는데 그대로 export. 테스트가 잘못된 값을 pin 함.
- **`pd_model.py:90-103`** `gini()` 가 tied score 를 argsort 로 처리해 midranks 없음 →
  `discrimination.auc_roc` 와 결과 불일치. → `2*auc_roc - 1` 로 통합.
- **`rating.py:41-52`** `pd_to_rating` 이 upper-exclusive/inclusive 규약 혼동. bisect_left 로
  boundary 값에서 off-by-one 등급 이동.
- **`credit_rating/sample.py:207-211`** `build_representativeness` 가 컬럼별 `.dropna()`
  개별 적용 → dev/current NaN 패턴 차이 (PSI 가 잡아야 할 그 자체) 를 놓친다.

### 2-7. Monitoring · Limits · Performance, 4건
- **`monitoring/deep.py:191-239`** roll_rate_matrix 의 base prior `[0.02,0.02,0.03,0.05,0.88]`
  로 90+ 에서 ~12% mass 매월 유출 (2% Current 복귀 = "spontaneous cure"). "흡수" 주장 위반.
- **`monitoring/recovery.py:37-51` + `recovery_deep.py:50-65`** right-censoring 미보정.
  M=60 개월 커브에 3개월 전 부도가 0 회수로 포함되어 곡선이 인위적 평탄화.
- **`monitoring/delinquency.py:16-23`** DPD 90-179 를 하나로 접음 (90-119/120-149/150-179
  분해 없음) → Stage 3 sub-strata / 추정손실 escalation 재구성 불가.
- **`performance/rapm_deep.py:296-303`** obligor_ranking 의 "ead" 컬럼이 실제로 EC. spread
  bp 계산이 크게 뒤틀림.
- **`performance/rapm.py:71-116`** EC=0 → RAROC=inf → pass_hurdle=True. sovereign 다수 book
  이 pass_hurdle_pct 를 과대. → `(ec > 0) & (raroc >= hurdle)`.

### 2-8. 아키텍처 계층 위반, 4건
- **`governance/rbac.py:34`** 최상위 `from risk_lib.page_registry import PAGES`, delivery
  심볼을 governance domain 이 top-level import. page_registry 가 governance SPECS 를
  참조하는 미래 어느 순간 진짜 circular.
- **`datamodel/lineage.py:555, 1079`** datamodel 이 `page_registry.PAGES` 와
  `ui_studio.studio.build_studio` 를 lazy import. "delivery MAY NOT be imported by domain
  engines" 를 우연에 의존.
- **`ops_pages/{credit, governance, nonfinancial, capital_stress, market_trading,
  concentration_limits, performance}.py` + `_shared.py`** chrome 을 `html_report` 를 통해
  import. 실제 흐름은 `ops_pages → report_chrome → page_registry`. 순환은 lazy resolve
  덕에 살아있지만 언제 깨질지 모름. → `report_chrome` 로 통일.
- **`ui_studio/nl_query.py:102-119`** field-mask 차단이 `masking=="deny"` 만 봄. `masking=
  "mask"` + `min_aggregation==1` 필드가 필터로 허용 → `SSN == 'X'` 로 마스킹된 값 확인 가능.
  현재는 `_MIN_AGG_MASKED=5` 관행에 의존. → `str(r["masking"]) != "none"` 도 차단 (파이썬·JS 둘 다).

## 3. MEDIUM, 51건 (요약)

전 도메인에 걸친 대표 패턴:

- **매직넘버 세 곳 복제**: BIS min/버퍼 (attribution + mda + html_exec), CECL/climate
  calibration (cecl + climate 각 파일에 pd/lgd 리터럴), pipeline deep-dive assumptions
  (15+ 숫자가 `_stage_capital` 안에 하드코딩).
- **파이프라인 stage 누락 시 조용한 NaN passthrough**: `pipeline.py:1961-1962` `lcr =
  getattr(..., "lcr", float("nan"))` 이 multi-institution 행에 NaN 삽입. `attribution.decompose_rwa`
  는 `rwa.get(key) or 0.0` 로 0 과 미제공을 구분 못 함.
- **테스트 커버리지 부재로 규정 위반이 통과**: 10개 core 모듈 (`appetite`, `climate`,
  `close_workflow`, `funding`, `margin`, `market_feed`, `product_master`, `rcsa`,
  `scenario_library`, `viz_advanced`, 총 ~2,700 LOC) 이 전용 테스트 파일 없음. 20+
  모듈이 pipeline smoke test 만 통과.

전체 51건 목록은 `scratchpad/reviews/` 의 각 파일 참조 (아래 §6 매핑).

## 4. LOW, 20건 (요약)

주로 style/naming, 컴포넌트 정확성엔 영향 없음. 대표:
- `abbreviations.py:69` "PD 하한 3bp" 툴팁이 BCBS d424 이후 stale (실제 5bp).
- `rwa_deep.py:154` 만기 clip 리터럴 (1.0/5.0) 이 `MATURITY_FLOOR_YEARS`/`MATURITY_CAP_YEARS`
  대신 하드코딩.
- `rwa_sa.py:161` unknown rating 이 `dict.get(r, 1.00)` 로 조용히 UNRATED (100%) 로.
  데이터 오류 (예: "AA+") 가 신호 없이 RWA 를 shift.
- `ui_studio/app.py:8801, 8809`, 하드코딩된 한글 문자열이 i18n sweep 우회 (dark mode
  toggle title, killreason default value).

## 5. 테스트 스위트, 구조·커버리지·건강도

### 5-1. 강한 곳

- `tests/test_independent_validation.py`, 3선 게이트 fail-closed 매트릭스가 정면·측면
  20+ 시나리오로 완결. gaps 없음.
- `tests/test_alm_wiring.py:153, :165`, `alm_repricing_gap` vs `alm_maturity_ladder`
  축 혼동 (ARCHITECTURE 명시 archetype) 이 확실히 잡힌다.
- `tests/test_stress_trace.py:205`, capital roll-forward 가 세후 이익 델타 (ECL 아님)
  로 진행되는지 검증.
- `tests/test_pipeline_e2e.py:22-84`, GOLDEN dict 이 규제 근거 (CRE20/CRE32/CRE40/CRE60/
  CRE52/MAR50/LEV20.1) 로 문서화되어 있어 재-pin 이 감사 가능.

### 5-2. 약한 곳

- **CRITICAL 커버리지 공백**: `output_floor_add_on` 이 stress 심도에 반응하는지 검증
  없음 (`test_stress_trace.py:183` 은 identity 만 확인). 4개 CCAR/climate 페이지 대해
  earnings-based roll-forward 테스트 없음 (`multi_axis` 만 fence 됨).
- **HIGH, "파일 사이즈 > 5000 bytes" 로만 페이지 확인**: 9개 테스트가 렌더된 HTML 이
  5KB 초과인지만 검증. 에러 배너로 채워도 통과.
- **HIGH, session fixture 위반**: 20+ 개 테스트가 `run_pipeline(...)` 또는
  `generate_portfolio(...)` 를 자체 호출. conftest.py 는 "session-scoped `portfolio`/`result`
  공유" 규칙을 명시. **테스트 스위트가 파이프라인을 20회 이상 중복 실행**.
- **HIGH, 벽시계 asof**: `test_stress_deep.py`, `test_monitoring_deep.py`,
  `test_timeseries.py` 등이 `run_pipeline()` 에 asof 미전달 → 캘린더 경계 근처에서
  drift 가능.
- **HIGH, GOLDEN_VALIDATION 카운트 pin**: `{"PASS":71, "WARN":15}`, 3개월간 10+ 회
  재-pin. 이름 집합이 아닌 총 카운트를 pin 하고 있어, 새 FAIL 체크 추가와 무관한
  bug fix 가 counter 를 흔들면 무의미한 재-pin.
- **HIGH, 아키텍처 불변식 grep 없음**: `test_architecture.py` 가 (i) 벽시계 심볼
  (`date.today`, `datetime.now`, `time.time`) 을 15개 명명된 모듈에서 grep 으로 금지,
  (ii) 보고서 계층이 도메인 엔진을 import 하는지, (iii) 규제 임계값 리터럴이
  `references.py` 외부에 있는지, **세 가지 grep 불변식이 모두 없음**. 이 세 항목이
  있었다면 §1-6/1-7 의 CRITICAL 은 PR 단계에서 발견됐다.

### 5-3. 커버리지 없는 상위 core 모듈

전용 테스트 파일이 없는 모듈:
`appetite.py, climate.py, close_workflow.py, funding.py, margin.py, market_feed.py,
product_master.py, rcsa.py, scenario_library.py, viz_advanced.py`

한 importer 뿐인 모듈 (실질 단일 e2e):
`adjustments, ccr, mda, notifications, pillar3, systemic, vintage, xva, report,
report_chrome, attribution, concentration_deep, sensitivity, data_quality,
html_exec, work_report, timeseries, cecl, model_risk, archive, api, macro_monitor,
market_portfolio`

## 6. 도메인별 상세 리뷰 링크

각 도메인 리뷰는 이 리뷰 세션의 서브에이전트 출력이며 `scratchpad/reviews/` 에 저장됨:

| 파일 | 도메인 | 발견 |
|---|---|---|
| `02-capital.md` | RWA(SA/IRB)/BIS/CRM/leverage/output floor/market/op | HIGH ×5, MEDIUM ×6, LOW ×3 |
| `03-alm.md` | IRRBB/LCR/NSFR/NII/cashflow/curves/behaviour | CRITICAL ×2, HIGH ×6, MEDIUM ×6, LOW ×1 |
| `04-models-credit-rating.md` | PD/LGD/rating/discrimination/scorecard | CRITICAL ×4, HIGH ×7, MEDIUM ×3 |
| `05-validation-governance.md` | 2선 consistency + 3선 independent + audit_chain/rbac | CRITICAL ×1, HIGH ×10, MEDIUM ×3 |
| `06-regulatory.md` | 34개 FSS 서식 + FINES + cross_form | HIGH ×4, MEDIUM ×9, LOW ×2 |
| `07-stress-provisioning-icaap-prudential.md` | 14축 stress + IFRS9 + ICAAP + PCA | CRITICAL ×3, HIGH ×5, MEDIUM ×5, LOW ×2 |
| `08-monitoring-limits-performance.md` | delinquency/cure/recovery/vintage + limits + RAPM | CRITICAL ×2, HIGH ×4, MEDIUM ×5 |
| `09-root-and-tools.md` | cli/pipeline/references/repro/timeseries/report/cecl/xva/mda/etc. | CRITICAL ×3, HIGH ×5, MEDIUM ×4 |
| `10-ui-studio-integration-ops-pages-datamodel.md` | 8856-line app.py/ops_pages/datamodel/integration | CRITICAL ×5, HIGH ×4, MEDIUM ×5, LOW ×1 |
| `11-tests.md` | tests/ 40 개 파일 | 커버리지 공백 CRITICAL ×1, HIGH ×2 + 20+ 개선 |

## 7. 권장 조치 순서

**Phase 1, fail-closed 무결성 회복 (즉시)**

1. **§1-1** `independent.py:691`, recalc_matches truthiness 수정 + bool 강제
2. **§1-7** wall-clock 3곳 (`timeseries.py:62`, `report.py:43`, `report_chrome.py:144`) 및
   pipeline entry (`pipeline.py:1500-1503`) 수정
3. **§2-3** `_check_stress_trough`/`_check_pillar2_evidence`/`_check_market_op_rwa` 의
   "미주입 = PASS" → "미주입 = WARN"
4. **§2-3** `_headline` 의 subdomain 0.0 폴백 → None 반환
5. **§2-3** RECALC_SCOPE 6개 추가 항목
6. **§2-3** `audit_chain.verify_chain` 을 manifest sealing 에 wire

**Phase 2, 규제 정확성 (1-2주 내)**

7. **§1-2** PD 하한 0.03%, LGD 하한 segment 강제, corporate B 등급 150%
8. **§1-3** CCAR/climate/reverse 를 `multi_axis` 로 통합; legacy `evaluate_scenario` 유지
   자체가 아니라 headline 산출 경로에서만 제거
9. **§1-4** limit severity 사다리 통합 (권장 `limits_deep` 사다리)
10. **§1-5** NPL·부도 정의에 UTP arm 추가
11. **§2-1** SA-CCR α 양측 적용, AT1/T2 상한 표 제거, past-due 자산군별 분리
12. **§2-2** ALM 버킷 규약을 `(lower, upper]` 로 통일

**Phase 3, 아키텍처 무결성 (2-4주)**

13. **§1-6** ops_pages 5개 페이지 (`cecl_ifrs9`, `intraday`, `xva_full`, `frtb_ima`, `ncr`)
    를 파이프라인 stage 로 승격
14. **§5-2** `test_architecture.py` 에 3개 grep 불변식 추가:
    - `date.today`/`datetime.now`/`time.time` 를 15개 명명된 파일에서 금지
    - `report.py`/`report_chrome.py`/`html_exec.py`/`ops_pages/*` 가 엔진 모듈을 import 하면 실패
    - `references.py` 밖의 `0.045`/`0.025`/`0.06`/`0.08`/`0.03` 등 규제 임계값 리터럴 grep
15. **§2-8** `governance/rbac.py` 와 `datamodel/lineage.py` 의 delivery-layer import 제거
16. **§2-8** `nl_query.py` + `engine.js` 의 mask 필드 차단 강화

**Phase 4, 유지보수성 (4-8주)**

17. `validation/consistency.py` (1774 라인) 을 도메인별 파일로 분할
18. `ui_studio/app.py` (8856 라인) 의 `_payload`/`_kpis`/`_JS` blob 분해
19. Session fixture 위반 20개 테스트 리팩토링
20. GOLDEN_VALIDATION 을 name set 로 전환
21. 10개 core 모듈에 최소 boundary 테스트 추가 (`appetite`, `climate`, ... `viz_advanced`)

---

*본 리뷰는 read-only. 서브에이전트 10개 병렬 실행. 원본 도메인별 리뷰는 저장소에 커밋되지
않고 세션 스크래치패드에만 있음 (전량 이 요약에 반영).*
