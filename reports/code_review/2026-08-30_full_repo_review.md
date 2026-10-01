# 저장소 전수 코드 리뷰 (2026-08-30, 45주차)

**대상**: `bbootta/AIops` 전 저장소, 현재 브랜치 `claude/stoic-ride-3nlfb8`, HEAD `60bda57`
**직전 리뷰**: `reports/code_review/2026-08-14_full_repo_review.md` (43주차)
**리뷰 방식**: 8 개 서브에이전트 병렬. (A) `risk_lib/capital/`, (B) `risk_lib/alm/`, (C) `risk_lib/models/`, (D) `risk_lib/validation/`+`governance/`, (E) `risk_lib/regulatory/`, (F) `risk_lib/datamodel/`+파이프라인 접착, (G) `risk_lib/` 잔여, (H) `validation-team-agent/`. 자체 실행: `pytest` (2,187 케이스 수집).

## 0. 총평 (한 문장)

**결재로 넘어가는 경로가 3선 게이트를 우회한다.** 자체검증(2선)에 가짜 통과 지점이 있고, 3선 독립검증은 21개 headline 중 6개만 실제로 재계산되며, CLI 결재 경로 두 곳(`_cmd_run`, `_cmd_report_set`)은 3선 게이트 자체를 호출하지 않는다. CLAUDE.md §6 이 명시하는 "fail-closed·응답없으면 결재불가"의 실제 집행이, 서류상 존재하는 게이트와 어긋난다.

동시에 자본·유동성·CCR 계산 자체에서 **직접 자본비율을 왜곡하는 규정 공식 오류 6~7건**을 새로 확인했다. Tier 2 GP cap, LCR/NSFR RSF·유입, SA-CCR PFE 승수 누락, BA-CVA 공식 오적용 등이 있고, 이 중 어떤 것이라도 감독자 재계산과 대사가 어긋난다.

| 층위 | 이번 리뷰에서 확인 |
|---|---|
| BLOCKER (§1) | 3선 게이트 무결성 4건 + 자본·유동성 공식 오류 6건 = **10건** |
| MAJOR (§2) | 규제보고서/데이터모델/모델 백테스트 12건 |
| MINOR (§3) | HTML/DLP/보고서 렌더링 5건 |
| 이전 리뷰에서 잔존 (§4) | 43주차 §1 BLOCKER 중 최소 3건 LIVE |

## 1. BLOCKER (즉시 조치, 결재 상신 금지)

### 1-1. 3선 게이트 무결성 (fail-closed 계약 위반)

- **`risk_lib/cli.py:57-61 (`_cmd_run`) / :97 (`_cmd_report_set`) , CLI 결재 경로가 3선 게이트를 호출하지 않는다.**
  두 서브커맨드는 `result.validation.passes()`(2선)가 true 이면 exit 0 을 리턴한다. `check_gate(...).require()` 호출은 `_cmd_validation_request` 와 `_cmd_deliverables` 에서만 발생한다. `risk_lib.cli run` / `report-set` 를 통한 결재 상신 시퀀스에서, 상시 독립검증이 `응답대기` 여도 exit 0 이 나온다. CLAUDE.md §6 이 명시하는 "결재 상신 직전 게이트 확인" 계약이 CLI 경로에서 성립하지 않는다.

- **`risk_lib/validation/consistency.py:883-891 , `_check_alm.lcr_inflow_cap` 이 두 분기 모두 PASS 를 기록한다.**
  `if lcr.inflow_capped >= 0.75*gross_outflow` 분기와 `else` 분기가 동일한 `ConsistencyCheck("lcr_inflow_cap","PASS",...)` 를 `report.add` 한다. 어떤 입력이 와도 실패하지 않는 가짜 통제. 3선에 넘기는 "n건 PASS" 계수가 실제 검증 커버리지보다 과장된다.

- **`risk_lib/validation/consistency.py:41-42 , `ValidationReport.passes()` 가 빈 체크 리스트에 대해 True 를 리턴한다.**
  다수의 `_check_*` 함수(코드 라인 173, 212, 246, 325, 373, 428, 447, 514, 549, 573, 621, 640, 665, 694, 717, 736, 758-764)가 입력 None/미충족 시 아무 `add` 없이 early-return. 결과 report 의 `passes()` 가 True → "미실행" 과 "통과" 가 `.passes()` 경계에서 구별되지 않는다.

- **`validation-team-agent/tools/independent_recalc.py:140-153 , 3선 독립 재계산이 21개 headline 중 6개만 커버.**
  `RECALCULATORS = {lcr, nsfr, cet1_ratio, leverage_ratio, icaap_ratio, portfolio_default_rate}`. `risk_lib/validation/independent.py:44-103 RECALC_SCOPE` 는 21건 요구 (누락: `rwa_final_total`, `rwa_fund`, `rwa_securitisation`, `ecl_total`, `ecl_weighted_total`, `irrbb_worst_pct_tier1`, `irrbb_delta_nii_parallel`, `survival_days`, `stress_trough_cet1`, `reverse_critical_severity`, `reserve_shortfall`, `kr_irrbb_table6_max_delta_eve`, `kr_irrbb_table6_max_delta_nii`, `lgd_backtest_bias`, `lgd_backtest_n_censored`). 15건은 3선이 제출값을 그대로 수용한다. `docs/independent_validation/RUN-20260630-42.opinion.md:83` 에 `rwa_final_total` "recalc'd variance +0.003" 기록이 있으나 재계산 함수 자체가 없다. **43주차 리뷰 §1-3 에서 이미 지적, 미해결.**

- **`risk_lib/validation/independent.py:206-213 , `ConditionalApproval.require_complete()` 이 `findings_accepted` 를 검증하지 않는다.**
  `approver`·`residual_risk`·`due_date`·`scope`·비어있지 않은 `conditions` 만 확인. `findings_accepted=()` 로 조건부승인이 통과. 어떤 경부적합 finding 을 인수했는지 남지 않은 채 결재. CLAUDE.md §6 "잔여위험·후속조건·이행기한·배포 범위를 기록해야만" 원칙 위반.

### 1-2. 자본 규정 공식 오류

- **`risk_lib/capital/bis_deep.py:117 (반복 122, 791) , Tier 2 일반충당금 인정 cap 이 1.25% × IRB RWA.**
  Basel III CRE40.44 는 approach 별로 분리: **SA 신용 RWA × 1.25%** 또는 **IRB 신용 RWA × 0.6%**. 필드명이 `irb_rwa_for_gp_cap` 이고 docstring 이 "IRB RWA 의 1.25%" 라 쓰여 있지만 1.25% 는 SA cap. 같은 파일의 `expected_loss_vs_provisions` 는 올바르게 `IRB_PROVISION_SURPLUS_CAP = 0.006` 을 쓴다. Tier 2 최대 2배 과대계상 → Total 자본비율 과대계상.

- **`risk_lib/capital/rwa_sa.py:236-285 , `standardised_rwa_total` 이 past-due 150% 오버라이드를 무시.**
  `compute_rwa_sa` 는 past_due 를 150% 로 강제하지만, output-floor SA 분모를 만드는 `standardised_rwa_total` 은 `past_due` 를 아예 읽지 않는다. 예: 20% past-due BBB 회사대출 → 코드 75%, 정답 150%. **Output floor 가 실제보다 덜 구속** → 규제자본 안전여유 축소.

- **`risk_lib/capital/rwa_sa.py:236-285 , `standardised_rwa_total` 이 `crm_factor` 를 무시하여 `compute_rwa_sa` 와 비대칭.**
  `compute_rwa_sa` 는 `× crm_factor` 후 산출, `standardised_rwa_total` 은 pre-CRM. Output-floor 분모는 pre-CRM, 내부 비교치는 post-CRM. 담보 비중 큰 은행(`crm_factor≈0.5`)에서 SA 총액이 IRB 의 ~2배 → output floor 가 허위로 binding.

### 1-3. 유동성·거래상대방 규정 공식 오류

- **`risk_lib/alm/balance_sheet.py:166-168` + `nsfr.py:_BANDS` , NSFR: 잔존 ≥1Y 인 FI 대출이 100% RSF 대신 85% RSF 로 분류.**
  `maturity_band_of(...)` 가 `("loans_fi_lt6m","loans_fi_6to12m","other_loans_ge1y")` 를 넘김. `loans_fi_ge1y` 카테고리가 아예 없어 잔존 >1Y 은행대출은 `other_loans_ge1y`(85%) 로 떨어진다. BCBS d295 NSF30.16(a) 는 100% RSF 요구. 은행간 term-loan 이 있으면 NSFR 이 (해당 exposure × 15%) / 총 RSF 만큼 과대계상.

- **`risk_lib/alm/lcr.py:344, 360-361 , LCR ledger 경로가 상각형 자산의 30-일 유입을 원금 전액으로 인식.**
  `amount = float(r["notional"])` 를 `residual_days ≤ horizon` 이면 통째로 유입. 20년 상각 주택담보대출의 잔존 25일 시나리오에서 마지막 회차 원금만 30일 내인데 잔액 전체가 유입으로 잡힌다. LCR **과대계상**.

- **`risk_lib/alm/lcr.py:360-361 , LCR ledger 경로가 모든 자산 유입을 `wholesale_inflows` 로 라우팅.**
  은행간 예치금(100% 유입 대상) 과 주택담보 회차(50%) 모두 같은 버킷 50% 로 처리. 100% 유입률 도달 불가. balance-sheet 경로는 retail/wholesale/fi 를 분리 → 두 경로가 어긋난 결과.

- **`risk_lib/ccr.py:60-76 , SA-CCR PFE 에서 multiplier 누락.**
  `pfe = sum(add_on)` 만 계산, Basel III CRE52.61 이 요구하는 `PFE = multiplier × AddOn_agg`(multiplier ∈ (floor, 1], V-C<0 일 때 감소) 미적용. `synthesise_derivatives` 가 notional 의 50% 까지 담보를 태우므로 대부분 multiplier<1 → SA-CCR EAD 가 **전 counterparty 에서 systematic 과대계상**.

- **`risk_lib/ccr.py:94-102 , BA-CVA 공식이 BCBS d507 이 아니다.**
  `K = κ·√(Σ EAD²)`. 실제: `K = ρ·(Σ SCVA_i) + √(1-ρ²)·√(Σ SCVA_i²)`, `SCVA_i = (1/α)·RW_i·M_i·EAD_i·DF_i` (감독 RW, 만기 discount, systematic ρ=0.5). 상관 스트레스에서 CVA 자본 과소. (`cva_rwa` 의 K→RWA ×12.5 는 정상)

## 2. MAJOR (누적 미소화 · 이번 리뷰 신규 12건)

### 2-1. 규제보고서 (FSS 업무보고서)

- **`risk_lib/regulatory/cross_form.py:56 , 보통주자본비율 대사가 stress trough 라인을 가리킨다.** `("BR-14","2100")` 는 `forms.py:_br14:638` 의 `base(2000)+1×100` = 시나리오 1 의 `trough_cet1`. BR-14 에 `r.bis.cet1_ratio` 라인이 없다. `tolerance=1e-9` 라서 어떤 실질 shock 시나리오든 spurious FAIL 발생. **43주차 §1-2 지적 잔존.**

- **`risk_lib/regulatory/cross_form.py:51 , 위험가중자산 합계 대사 scope 불일치.** BR-01/2000 = `rwa["final_total"]`(credit+market+op+floor add-on), BR-20/5000 = `rwa_output_floor.floored_rwa`(credit 중심). 상류 aggregate 이 credit-only 이면 `market+op` 만큼 상시 미스매치. **43주차 §1-2 지적 잔존.**

- **`risk_lib/regulatory/forms.py:379-380 , BR-08 LCR 부호 확인 항등식.** `tol = float(lcr.inflow_capped)+1.0`. `|net−gross| = inflow_capped` 이므로 항상 통과, `inflow_capped` 부호 flip 도 통과. **43주차 §1-2 지적 잔존.**

- **`risk_lib/regulatory/excel.py:29, 184 , KRW 셀이 백만원 재척도 없이 raw 원으로 출력.** `_KRW_FMT="#,##0"` 만 지정. FSS 서식은 대개 백만원 단위. 제출 파일 그대로 사용 시 1e6 배 과대. 시트마다 수기 재척도 필요.

- **`risk_lib/regulatory/cross_form.py:60, 76 , CAMEL cross-form 불변식이 문서화되지 않은 행 순서에 의존.** `("BR-31","1110")`·`("BR-31","1510")` 는 `pru_camel` 의 자본→자산→경영→수익→유동→리스크 순서를 가정. `WEIGHTS` 재정렬 시 조용히 손상.

### 2-2. 모델 (PD/LGD 백테스트)

- **`risk_lib/models/rating.py:49 , `pd_to_rating` off-by-one, PD=0.0100 → BBB+ 반환 (정답 BBB).** `bisect_left(uppers, pd_value)` 로 경계에서 상위 등급 배정. logit-shift 재보정 후 또는 PD 하한(0.03% 등) 이 binding 하면 매우 흔한 경계값 → 해당 obligor 자본 저평가. Fix: `bisect_right`.

- **`risk_lib/models/pd_model.py:98-103 , `gini()` 가 score tie 를 무시, `discrimination.py:auc_roc` 와 불일치.** 원본 랭크 vs 평균 랭크. master-scale 매핑 후 midpoint 공유가 많아 tie 편재 → 같은 Basel 요구 지표가 argsort-순서 의존.

- **`risk_lib/models/estimation/lgd_est.py:394-400 , Downturn LGD 가 조용히 drop.** downturn 연도가 있지만 그 해에 종결된 workout 이 없으면 `downturn=None`, `raw = float(longrun)`, `dt_status="산출완료"`. 185.가(1) 요건 우회. Non-conservative for IRB.

### 2-3. 데이터모델·파이프라인

- **`risk_lib/datamodel/materialize.py:176-189 , `materialize_rwa` 가 pre-stage3 EAD 로 SA RWA 재계산.** `pipeline._branch_credit` 가 Stage-3 ECL 을 SA EAD 에서 차감한 후 `_stage_credit_rwa` 를 부르지만, `fitted_portfolio` 는 이 차감을 하지 않는다. 원장에 쓰이는 `rwa_result` 가 `bis` 분모의 SA RWA/EAD 와 다르다 (모듈 docstring 이 경계하는 "두 벌" 문제).

- **`risk_lib/datamodel/decompose.py:32-38 , `_fingerprint` 가 row-order 의존.** 상류 `groupby`/`merge`/병렬 branch 가 순서를 바꾸면 같은 데이터에서 fingerprint 가 달라진다. "same (asof, seed) → same fingerprint" 재현성 계약 파괴.

- **`risk_lib/api.py:32-56, 234, 276 , `_to_jsonable` 가 raw `NaN`/`Infinity` 를 JSON 에 방출.** Snowflake/Presto/jq/대부분 JS parser 가 거부. `endpoint_alm(res,"irrbb")` 와 `endpoint_headline` 이 분모 0 상황에서 NaN 을 냄.

### 2-4. 자본 시뮬레이션 · 거버넌스

- **`risk_lib/capital_simulation.py:85-97 , MDA default CBR 이 CCyB/DSIB 를 무시.** `_mda_quartile(cet1_ratio, cbr=0.025)` 만 사용. DSIB 는 실제 CBR ≥3.5% (CCB+CCyB+DSIB). 스트레스 경로에서 CET1 7~8% 구간의 배당 제한이 풀려 retained CET1 을 systematic 과대계상. `mda.py:45-58` 은 올바르게 버퍼 dict 를 합산 → 두 모듈 disagree.

## 3. MINOR (5건)

- **`risk_lib/report_chrome.py:159 , HTML escape bypass.** `f"<td{cls}>{v if isinstance(v,str) and ('<' in v) else _esc(v)}</td>"`. 문자열 셀에 `<` 만 있으면 raw insert. 외부 포트폴리오·시나리오 서술 로드 시 board_pack/html_exec/printable 에 **XSS**.

- **`risk_lib/aig/trace.py:137 , 주민번호 DLP 정규식이 외국인등록번호 미검출.** `\b\d{6}[-\s]?[1-4]\d{6}\b`. 7번째 자리가 5-8 (외국인) 인 케이스가 마스킹 없이 프롬프트·트레이스에 노출. 개인정보보호법 통제 실효 상실.

- **`risk_lib/monitoring/cure.py:99, 113 , 큐어 0건일 때 `avg_time_to_cure=0.0` 반환.** 대시보드에 "0.0 개월 즉시 큐어" 로 표시 → CRO 오해.

- **`risk_lib/attribution.py:159-163 , lcr_bridge dead branch.** `dnet = (lb.net_outflow - la.net_outflow) or 1.0` 로 truthy 강제 후 `if dnet else 0.5` else 분기 도달 불능. net_outflow 미변화 quarter 의 weight 가 raw absolute delta 로 튐 → 분기 재조정 파괴.

- **`risk_lib/datamodel/exposure_agg.py:39, 134-146 , `alm_aggregate` 가 NaN maturity 를 문자열 `"nan"` 버킷으로 캐스팅한 뒤 merge.** `.astype(str)` + `dropna=False` 조합. 실제 NaN 이 리터럴 문자열 `"nan"` 버킷으로 합쳐져 집계에 잔류.

## 4. 이전 리뷰 잔존 (43주차 → 45주차)

43주차 §1 6건 중 이번 세션 표본에서 재확인된 잔존 항목:

- §1-2 FSS cross-form (BR-14 대사, RWA scope 대사, LCR BR-08 항등식): **전건 LIVE** (§2-1 참조).
- §1-3 3선 독립검증 커버리지 6/21: **LIVE** (§1-1 4번째 항목 참조).
- §1-6 em/en dash 정책 위반: 별도 grep 미실시. 43주차 이후 추이 미확인.

## 5. 자동화 검증 상태

- **테스트**: `pytest tests/` 수집 2,187개, 백그라운드 실행 중 리뷰 종료 시점 진행률 30% 미만. `test_deliverables.py`(`@pytest.mark.slow` 미등록) 는 이번 실행에서 `--ignore` 로 제외. 실행 완료 결과는 별도 다음 회차에서 확인 필요.
- **CI**: `.github/workflows/` 에 `validation-team-agent-ci.yml` 만 존재. **`risk_lib/` (117K LOC 본체 + 30K LOC 테스트) 는 CI 게이트 자체가 없다.** 모든 회귀는 로컬 개발자 실행에만 의존.
- **의존성 lock**: `pyproject.toml` 이 `>=` 범위만 지정. `numpy>=1.24, pandas>=2.0` 등 재현성 lock 부재. 로컬·CI 환경 간 미세 수치 드리프트가 조용히 발생 가능.

## 6. 우선순위 요약

**즉시 (D+1) 결재 상신 전 해결**
1. `_check_alm.lcr_inflow_cap` 두 분기 PASS 제거 (§1-1 두 번째).
2. `ValidationReport.passes()` 빈 리스트 True 리턴 → "not run vs pass" 구분 도입 (§1-1 세 번째).
3. `_cmd_run`/`_cmd_report_set` 에 `check_gate(...).require()` 삽입 (§1-1 첫 번째).
4. `ConditionalApproval.require_complete()` 에 `findings_accepted` 커버리지 검증 (§1-1 다섯 번째).

**단주 (W+1) 자본·유동성 산출 정정**
5. `bis_deep.py` GP cap SA/IRB 분리 (§1-2 첫 번째).
6. `standardised_rwa_total` 에 past-due 150% + `crm_factor` 반영 (§1-2 두·세 번째).
7. NSFR `loans_fi_ge1y` 카테고리 추가 (§1-3 첫 번째).
8. LCR ledger 경로 상각·counterparty 세분 (§1-3 두·세 번째).
9. SA-CCR multiplier + BA-CVA d507 공식 (§1-3 네·다섯 번째).

**월내 (M+1) 커버리지 확대**
10. `validation-team-agent/tools/independent_recalc.py RECALCULATORS` 를 21건 전건으로 확대 (43주차부터 미해결).
11. `risk_lib/` 에 CI workflow 추가 , 최소 `pytest -q`, `ruff check`, `mypy --strict risk_lib/validation/ risk_lib/capital/`.
12. `pyproject.toml` 의존성 == 로 lock 하고 lock file 커밋.

**리뷰 산출 위치**
- 상세 항목별 근거: `/tmp/claude-0/-home-user-AIops/53e32728-9873-52a7-9829-86858850e7ae/scratchpad/findings/{02..09}_*.md` (본 리뷰 세션 내 서브에이전트 원본 산출)
- 이 문서: 취합·랭킹·43주차 대비 트래킹만 수행.

---

*자체검증(2선): 본 리뷰 자체는 코드 인스펙션 산출이며 리스크 계량 산출이 아니므로 CLAUDE.md §6 게이트 적용 대상이 아님을 명시. 상시 독립검증(3선) 요청 불필요.*
