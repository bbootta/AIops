# 저장소 전수 코드 리뷰 (2026-08-27, 45주차)

- **대상**: `bbootta/AIops` 전 저장소, 브랜치 `claude/stoic-ride-nbxjhq`
- **직전 리뷰**: `reports/code_review/2026-08-14_full_repo_review.md` (43주차)
- **리뷰 방식**: 8개 병렬 서브에이전트가 영역별로 코드를 직접 읽고 결함을 재현 시나리오까지 확인
- **범위**: risk_lib (~117k LOC, 268 파일) + validation-team-agent (~39k LOC, 262 파일) + tools + examples
- **총 결함**: 106건 (**critical 9 · high 22 · medium 40 · low 33** · 기타 2)

> 이 리뷰는 정적 코드 감사다. `risk-validator` 자체검증도, `claude/validation-team-agent-Pw9F5` 상시 독립검증도 아니다. 아래 발견 사항은 두 검증 경로가 지금 사용하고 있는 코드 자체의 결함을 가리키며, **특히 §7 validation-team-agent 절의 critical 4건은 3선 게이트를 fail-open으로 만든다**. 그 결함이 있는 한 3선 통과는 "적합"의 근거가 되지 못한다.

## 0. 총평 (한 문장)

**결재 게이트 위쪽 세 층 (2선 리포트, 마감 워크플로, 3선 독립검증) 이 각 층에서 별개의 fail-open 결함을 안고 있어, 어떤 조합으로도 AIMS_POLICY.md 가 약속하는 fail-closed 를 실현하지 못한다.** 결함은 모두 정지된 표면 (테이블 존재 여부, 자릿수 존재 여부) 로 진짜 판정을 대신하고 있으며, 서로 다른 팀이 서로 다른 시간에 넣은 것이라 우연한 상호작용이 아니라 조직적으로 반복된 실수의 패턴이다.

## 1. Critical 요약 (9건)

| # | 파일:라인 | 증상 | 심각도 |
|---|---|---|---|
| C1 | risk_lib/board_pack.py:78-82 | 위원회 부의서 표지가 3선 게이트를 무시하고 2선 결과만으로 "결재 가능 (PASS)" 인쇄 | critical |
| C2 | risk_lib/close_workflow.py:109-110 | CL-10 "독립검증 게이트 확인" 이 결과가 아닌 대상 목록의 존재만으로 완료 판정 | critical |
| C3 | risk_lib/close_workflow.py:111-113 | CL-11 결재 상신이 `gov_approval` 행 수 > 0 로 완료 판정 (이전 분기 승인이 재사용됨) | critical |
| C4 | risk_lib/credit_rating/build.py:157-158 | 151.나 부도등급 세분화 검사가 존재하지 않는 "D" 등급 사용 → 항상 PASS | critical |
| C5 | risk_lib/limits_master.py:140 & limits/limits_deep.py:151 | 은행법 §35 동일차주 25% 한도가 obligor_id 단위, 연결차주 그룹 단위 아님 | critical |
| C6 | validation-team-agent/tools/validation_finding.py:269 | SoD `NOT_EVALUATED` fail-open → actor 없이도 finding 종결 → `approval_blockers()` 무력화 | critical |
| C7 | validation-team-agent/tools/provenance.py:71-92 | 비원시형 값이 재현성 해시에서 조용히 탈락 → numpy 배열 payload 가 다르면서도 같은 digest | critical |
| C8 | validation-team-agent/src/vta/handlers/registry.py:198-322 | NaN/Inf 입력이 `skipped` 상태를 만들어 Basel 검증 7개 도메인이 조용히 우회 | critical |
| C9 | validation-team-agent/tools/independent_recalc.py:196-233 | `--validation-inputs` 없이도 `SURVIVED` 판정 → 3선 독립성 실질 미수립 | critical |

## 2. High 요약 (영역별, 22건)

**Capital & RWA (4)**: B등급 회사채 RW=100% (Basel 요구 150%) · SA-CCR 승수항 누락 · BA-CVA 최대 7배 과소 · Mortgage NaN LTV 가 output floor 완화

**Governance & audit (8)**: RBAC 날짜 파싱 실패 SOD 누락 · archive 손상 JSON 스킵 → 이력 소실 · audit_chain actor NaN 충돌 · aig/trace 체인 해시 payload 미포함 · audit_chain occurred_asof 10 vs 19자 round-trip 전 행 실패 · aig/trace None vs NaN 문자열화 불일치 · audit_trail approval_dt 임의 문자열 → "결재원장" 증승 · model_lifecycle 알 수 없는 상태 "개발" 매핑

**Credit & ECL (6)**: 채점 시 NaN 대입이 배치 중앙값 · 적합 시 imputation 미저장 · model_pd 하한 1e-6 (Basel 3bp 위배) · 정성 특성이 target 을 누출 · 세그먼트 IFRS9 를 EAD 비례 배분 · 12M PD 를 잔존기간 hazard 로 사용 · PD .clip(1e-4, 0.99) 로 Stage-3 부도 상한 99%

**Monitoring & limits (2)**: LimitBreach.severity 가 다른 경로와 CRITICAL/BREACH 뒤바뀜 · 은행법 §35 검정이 obligor 단위

**validation-team-agent (4)**: 손상 정책 파일 "(unreadable)" 통과 · git rev "unknown"="unknown" fail-open · critical 미태그된 회귀는 배포 차단 안 함 · CLI exit code 가 weight_violations · PII · watermark 무시

**Regulatory forms (1)**: CET1 이질 비교 (current vs stressed trough) → 스트레스 실행마다 위반

**ALM (1)**: 버킷 경계 규약 반전, 계약 기반 NMD ΔEVE 수백억 KRW 과대

**Orchestration (2)**: HTML 인젝션 sink (`<`가 raw 렌더) · `reproduce` 가 manifest 의 asof 를 재전달 안 함

## 3. 패턴 관찰

3.1. **"존재 = 통과"** 결함이 반복된다. C2, C3, C6 셋 모두 게이트를 결과가 아니라 표면 존재로 판정한다. 이 패턴은 새 검사가 추가될 때 자동으로 되풀이될 위험이 있다.

3.2. **"모른다 = 통과"** 결함이 반복된다. C6 (SoD NOT_EVALUATED), C8 (NaN → skipped), G-high (unknown status → 개발), CR-high (nanmedian 재계산) 모두 정보 부재를 통과로 해석한다. CLAUDE.md §6 이 명시적으로 금지한 패턴이다.

3.3. **Round-trip 불일치가 audit chain 을 실질적으로 무력화한다**. G-high 3건 (occurred_asof, None/NaN 문자열화, canonical_digest default=str) 모두 parquet/CSV 왕복만으로 체인 검증이 노이즈가 된다. 진짜 위변조가 그 노이즈에 숨는다.

3.4. **Basel III 표준 자체가 여러 지점에서 어긋난다**. 회사채 B RW · SA-CCR multiplier · BA-CVA · AT1/T2 인정한도 · 만기 조정 · SME size adjustment · large-FI 1.25배. 개별 오차는 작지만 방향이 대체로 CET1 ratio 를 과대 표시하는 쪽으로 정렬되어 있어 합산 편향은 크다.

3.5. **동일차주 그룹 인식이 두 곳에서 같은 방식으로 실패한다** (limits_master + limits_deep + concentration_deep). 은행법 §35 위반이 세 경로 모두에서 보이지 않는다.

## 4. 우선순위 처리 권고

**P0 (즉시)**: C1, C2, C3, C6, C9: 이 다섯 개가 살아있는 한 어떤 결재 상신도 실제 fail-closed 를 통과했다고 볼 수 없다. C6 은 별도의 hot-fix 로도 30분 안에 고칠 수 있다 (`if enforce_sod and not sod["passed"] and sod["violations"]` → `if enforce_sod and sod["status"] != "PASS"`).

**P1 (이번 스프린트)**: C4, C5, C7, C8 · 그리고 §2 high 중 Basel 표준 위배 4건 (rwa_sa.py:45, ccr.py:75, ccr.py:102, rwa_sa.py:280). 이들은 규제 기준선 자체를 흔든다.

**P2 (다음 스프린트)**: 나머지 high 18건과 medium 40건. 대부분 데이터-품질/재현성 결함이며 개별로는 심각도가 낮지만, 3.1~3.4 패턴을 만드는 원료이므로 방치하면 다음 리뷰에 다시 등장한다.

**Low 33건**: 배치성 정리로 처리. 별도 티켓 불필요.

## 5. 검증 결과 표기

이 리뷰 자체에는 다음 두 줄이 붙지 않는다: 이것은 검증 산출이 아니라 감사이기 때문이다. 이 리뷰가 지적한 결함이 반영된 다음 결재 산출에는 CLAUDE.md §6 규칙에 따라 아래와 같이 붙어야 한다.

```
자체검증 (2선)      PASS n · WARN n · FAIL 0
상시 독립검증 (3선)  응답대기 (IVR-…)  또는  적합 (IVR-…)
```

---

## 상세 결함 목록

이하 각 영역별 상세 발견 사항은 리뷰 에이전트가 직접 코드를 읽고 실패 시나리오까지 확인한 원본이다. 코드 변경 시 이 파일을 우선 참조하라.

# Capital & RWA: 20 findings (0 critical, 4 high, 5 medium, 11 low)

## High
- **risk_lib/capital/rwa_sa.py:45**: `_RW_CORPORATE["B"] = 1.00`. Per CRE20.44 (ECRA), corporate "Below BB-" (including B+/B/B-) gets 150%, not 100%. 1T KRW B-rated senior unsecured corporate: understated by 500B RWA; overstates CET1 ratio.
- **risk_lib/capital/ccr.py:75 (saccr_ead)**: SA-CCR EAD omits the netting-set multiplier `min(1, F+(1-F)·exp((V-C)/(2·(1-F)·AddOn)))` from CRE52.20 (F=0.05). Any V<C portfolio is over-charged; EAD ~28% too high in the reviewer's example (V=-100, C=0, ΣAddOn=200).
- **risk_lib/capital/ccr.py:102 (cva_capital_charge)**: BA-CVA reduced to `κ·√(Σ EAD²)`, κ=0.05. Ignores CRE50.6 supervisory RW·M weights and ρ/(1-ρ²) systemic/idio split. Long-dated / high-spread portfolios can be understated ~7× (500B EAD × 2 → κ√·≈35B vs Basel BA-CVA ≈250B).
- **risk_lib/capital/rwa_sa.py:280 (standardised_rwa_total)**: Mortgage rows with NaN LTV silently fill to 0.8 → 30% RW, which is the output-floor denominator. If LTV column exists but NaN'd for some rows, `rwa_standardised` is understated; floor becomes less binding; headline RWA silently lower.

## Medium
- **risk_lib/capital/rwa_sa.py:97 (mortgage_rw_vector)**: `np.searchsorted(side="left")` returns len(edges)=5 for NaN LTV (NaN sorts high) → maps to 70% RW silently, unlike the scalar variant that would raise.
- **risk_lib/frtb.py:122 (rfet_test)**: Iterates `price_history.columns` without excluding the "date" column that the function reads on line 125. `date` becomes an extra "modellable" risk factor; inflates n_factors and distorts NMRF add-on.
- **risk_lib/capital/bis.py:145 (synthesise_capital)**: `retained = max(annual_profit, 0) * years` floors negative earnings at zero. A loss-making bank shows the same synthetic CET1 as a break-even bank; ratio overstated by up to loss×years/RWA (hundreds of bp on stress runs).
- **risk_lib/xva.py:129 (mva)**: `im_t = im_initial*(1 - t/t.max())` with t starting at 0.25 (from `synthesise_xva_portfolio:167`) starts amortisation from 0.25; short-dated / few-point grids understate MVA ~5%.
- **risk_lib/capital/bis_deep.py:253-267 (at1_t2_recognition_limits)**: Non-Basel "AT1 cap = CET1·1.5/4.5, T2 cap = Tier1·2/6" formulation. Basel imposes no such caps on AT1/T2 amounts for ratio computation. Any consumer reading `at1_recognised`/`t2_recognised` underreports Tier1/Total by ~15%+.
- **risk_lib/capital/bis_deep.py:637-642 (compute_bis_deep)**: Passes cet1.net (already deducted for dta_excess) as pre-threshold base, then recomputes a fresh 10/15% threshold from raw DTA/MSR/significant investments. Double-counts DTA when both are supplied.

## Low
- **risk_lib/capital/rwa_deep.py:154 (irb_decomposition)**: `m_eff = clip(maturity, 1, 5)` applied to all asset classes including retail; CRE31.6 maturity floor/cap is wholesale-only. Hard-codes 1/5 instead of MATURITY_FLOOR_YEARS/MATURITY_CAP_YEARS.
- **risk_lib/capital/rwa_deep.py:212-231 (lgd_downturn_scenario "max" method)**: Docstring cites "CRE32.41 anchor multiplier", but no such 1.06 anchor exists. Downturn LGD uplift materially smaller than typical supervisory add-ons.
- **risk_lib/capital/rwa_irb.py:89 (irb_capital_requirement)**: Case-sensitive `"retail" in asset_class` vs vector-path lowering; latent parity gap once retail/corporate PD floors diverge.
- **risk_lib/xva.py:78-82 (_hazard_curve)**: Name/type says hazard curve, returns cumulative PD (`1-exp(-s·t)`). Current callers use it correctly via `np.diff`; latent trap for future callers.
- **risk_lib/capital/leverage.py:33-41 (exposure_measure)**: derivatives / SFT accepted as opaque scalars; LEV30.20 α·(RC+PFE) and LEV30.15 SFT netting are the caller's problem, no validation.
- **risk_lib/capital/bis.py:64-91 (compute_bis_ratios)**: Validates rwa>0 but not that rwa is the aggregate credit+market+op RWA; passing credit-only inflates CET1 ratio silently.
- **risk_lib/capital/rwa_sa.py:173, 187**: `table.get(r, 1.00)` maps unknown ratings to 100% RW; "BBB+" / "BB-" subgrades not in bucket keys silently degrade to 100%.
- **risk_lib/capital/rwa_irb.py:46-60 + irb_k_vector:161**: Missing SME size adjustment (CRE31.5) and large-regulated-FI 1.25× multiplier. IRB RWA on those segments off by non-trivial amounts vs Basel.
- **risk_lib/capital/crm.py:57-74 (crm_adjusted_ead)**: No invariant `1 - hc - hfx ≥ 0`; miconfigured haircut can produce negative collateral that ADDS to exposure.
- **risk_lib/capital/leverage_deep.py:174-178 & risk_lib/mda.py:77 (leverage_mda)**: Off-by-one at exact quartile boundaries: `int(shortfall/qw)+1 = k+1` pushes the exact boundary case into the worse quartile.
# ALM: 6 findings (0 critical, 1 high, 3 medium, 2 low)

Reviewer verified positive: LCR/NSFR factor tables, ΔEVE loss-only aggregation, ACT/ACT-ISDA and 30/360 day counts, HQLA caps, LCR inflow 75% cap, post-shock floor, auto-option risk in per-currency loss, references.py regulatory tables.

## High
- **risk_lib/alm/cashflow.py:206 (_Buckets.assign)**: Bucket boundary convention inverted vs codebase. Uses `np.searchsorted(self.upper, t, side="right")` with `[lower, upper)`, while alm/params.py:339 documents BCBS convention `(하한, 상한]` and alm/liquidity.py:402 + alm/kr_irrbb.py:1775 both use `side="left"`. Every NMD contract-basis CF (t=0.0028 shortest) is placed in seq 2 (t_mid=0.0417) instead of seq 1 (O/N); discount-factor sensitivity is ~15× larger there. ΔEVE on 계약 basis inflated by hundreds of billions KRW on a NMD-heavy portfolio.

## Medium
- **risk_lib/alm/nii.py:190 (_pass_through)**: NMD parameter lookup filters on category only, no ccy filter. Once alm_nmd_param carries KRW and USD rows, a USD retail NMD may be priced with KRW β. Latent (build_nmd_param currently KRW-only) but multi-ccy path is exposed by `compute_delta_nii`.
- **risk_lib/alm/nii.py:264-266 (compute_delta_nii)**: `excluded_notional_ratio` denominator is |assets|+|liabilities|; numerator only tracks dropped liability NMDs. Ratio bounded to ~0.5 even when 100% of the funding side is dropped; evidence_status='미확인' understated.
- **risk_lib/alm/kr_irrbb.py:1005-1018 (bachelier_value)**: Unknown option_type (typo, new type) with vol/expiry=0 falls through to the floor payoff branch before the guard. `option_type="금리스왑션"` with expired option prices as a floor and flows into ΔEVE via `_aggregate_across_currencies`.

## Low
- **risk_lib/funding.py:203 (build_ladder)**: tenor_days=0 trades excluded from all buckets but stay in principal.sum(); share.sum() < 1; O/N intra-day RPs disappear.
- **risk_lib/alm/behaviour.py:83-89 (smm_from_cpr)**: cpr≥1 returns 1.0 silently while numerical noise (cpr=-1e-17) raises. Asymmetric guard.
# Credit rating & IFRS9 ECL: 17 findings (1 critical, 6 high, 8 medium, 2 low)

## Critical
- **risk_lib/credit_rating/build.py:157-158**: 151.나 (부도 차주 등급 세분화) check uses a fictional "D" grade. `DEFAULT_MASTER_SCALE` contains no D; `pd_to_rating(1.0)` maps every defaulted obligor to CCC+. The 부도 1/요건 1 check PASSes regardless of the scored population: 부도·비부도 등급이 한 버킷에 뒤섞여도 규정 만족으로 보고.

## High
- **risk_lib/credit_rating/scorecard.py:621-624 (score_obligors)**: NaN imputation at scoring uses the scoring population's median (`np.nanmedian(x)`), not the dev-time median. Two different scoring populations impute different values for the same obligor; if a feature is all-NaN, every model_pd becomes NaN. Breaks 153.라 재현성.
- **risk_lib/credit_rating/scorecard.py:519**: Same nanmedian issue at fit time; no imputation policy stored on ScorecardFit, so score_obligors cannot re-apply the dev-time value even if we wanted to.
- **risk_lib/credit_rating/scorecard.py:636**: `model_pd` floored at 1e-6, violating Basel/IRB non-sovereign 3bp PD floor. Sub-floor PDs propagate to AAA (midpoint 1.5bp: the master scale itself under-floors AAA) and downstream ECL/RWA.
- **risk_lib/credit_rating/scorecard.py:352-382 + build.py:112-114**: Target leakage: `build_qualitative_assessment` builds qualitative scores from `obligors["pd"]`, then those scores are fed as features to `fit_scorecard(target="default_12m")` where `default_12m` is generated from the same `pd` column. Inflated IV, weights, Gini; 크리에이션 지표가 실질 예측력이 아님.
- **risk_lib/cecl.py:107-117**: Per-segment IFRS9 in DualReportBridge is allocated by EAD share; IFRS9 is Stage-3 driven, so segment gaps are dominated by allocation artefact, not real dual-report differences.
- **risk_lib/cecl.py:56-66 (_lifetime_ecl)**: 12M PD used as annual hazard for every year of remaining life. ASC 326 CECL needs lifetime PD term structures; the reported "CECL" total is IFRS9-style, so the dual-report gap is systematically off.
- **risk_lib/cecl.py:52-53**: Silent floor/cap: PD `.clip(1e-4, 0.99)` caps a Stage-3 defaulted account (should be PD=1.0) at 99%, understating lifetime ECL. LGD `.clip(0.05, 0.95)` overrides regulatory LGD floors (e.g., residential mortgage 10%).

## Medium
- **risk_lib/cecl.py:82**: Division-by-zero on `weighted_life_years` when total EAD is 0.
- **risk_lib/cecl.py:109**: `gap_pct` falls back to 0 when IFRS9 total is zero, hiding an infinite relative gap.
- **risk_lib/cecl.py:60**: `n = max(int(np.ceil(life)), 1)` uses a full-year loss on a 3-month exposure; systematic over-estimate on short-life books.
- **risk_lib/models/pd_model.py:117-128 (`psi`) via risk_lib/credit_rating/sample.py:223**: `np.quantile` with tied data (discrete QL-* features with 5 levels) produces duplicate histogram edges and inflated/deflated PSI; `crm_sample_representativeness.psi` unreliable on qualitative items.
- **risk_lib/credit_rating/build.py:127-131**: Random 70/30 row split (no temporal separation) and then scoring the full corp (dev∪holdout). Reported discriminant metrics include training error; 174/178/180.가 하한 시나리오가 무너짐.
- **risk_lib/credit_rating/scorecard.py:461-480 (_direction)**: The "혼재" branch fires only if weighted covariance is exactly 0; for real data always outputs 증가/감소. `sign_observed="혼재"` unreachable: 158.(1) 부호일치 경고가 진짜 비단조 요인에서 꺼지지 않음.
- **risk_lib/credit_rating/override.py:240**: `final_pd = rating_to_pd_midpoint(new_rating)` discards `model_pd`. Two obligors with identical final risk profile can carry different `final_pd` depending on whether they were overridden, biasing ECL/RWA when overrides are common.
- **risk_lib/credit_rating/scorecard.py:503**: `dev[target].astype(int)` crashes on NaN in default_12m; no validation.

## Low
- **risk_lib/attribution.py:151-163 (lcr_bridge)**: `dnet or 1.0` denominator combined with `w_out/w_in` split can produce non-additive contributions when HQLA-weight adjustments carry into net.
- **risk_lib/credit_rating/override.py:311-330 (reconcile_override_flag)**: `pd.to_numeric(errors="coerce").fillna(0).astype(int)` silently zeroes fractional or multi-flag values; should validate domain.
# Monitoring & limits: 14 findings (1 critical, 2 high, 6 medium, 5 low)

## Critical
- **risk_lib/limits_master.py:140 & risk_lib/limits/limits_deep.py:151**: Regulatory 동일차주 25% limit applied at obligor_id granularity, not group-of-connected-borrowers. Three obligors at 12/10/8% of Tier1 (aggregate 30%) pass individually. 은행법 §35 breach is invisible.

## High
- **risk_lib/limits/limit_engine.py:41-47 (LimitBreach.severity)**: Inverts CRITICAL vs BREACH: LimitBreach treats CRITICAL (util≥1.20) as worst; every other path (limits_deep._severity, large_exposure._sev, concentration_deep.sev, escalation_matrix) treats BREACH (util≥1.00) as worst. Dashboards diverge on identical inputs; action recommendations mis-route.
- **risk_lib/concentration_deep.py:53-89**: `large_exposure_test` aggregates by obligor_id only; same class of miss as the critical finding above, plus emits severity keyed to 은행법 §35.

## Medium
- **risk_lib/monitoring/delinquency.py:28-32 (_bucket) & risk_lib/monitoring/deep.py:42-49 (_bucketise)**: Negative DPD falls through to worst bucket ("180+" / "90+"). `dpd=-3` classified as 90+ while `is_default` (dpd≥90) says no; bucket table and NPL ratio disagree on the same loan.
- **risk_lib/monitoring/recovery.py:44-45 & recovery_deep.py:57-58**: Zero-EAD default: `(cum/ead).clip(upper=1.0)` pins inf to 1.0; the default contributes 100% recovery to the mean, biasing curve upward.
- **risk_lib/monitoring/vintage_deep.py:42-58**: cohort label `f"M-{c}"` is inverted vs the code's cohort ordering (c=0 is oldest); readers see "M-0 = current month" and misread the seasoning curve.
- **risk_lib/monitoring/deep.py:210-215**: Base roll matrix has 90+ → performing transitions summing to 0.12/mo despite docstring claim of absorbing state; `markov_projection` "cures" NPL into Current over the horizon.
- **risk_lib/limits/large_exposure.py:629-632**: Structure attributes (can_lt, equal_sen, total, tranche_amount) read from `parts.iloc[0]` only; heterogeneous underlyings silently attribute under the first row's regime.
- **risk_lib/limits/limit_engine.py:79-80 vs risk_lib/limits/limits_deep.py:222-223**: Missing dimension raises ValueError in evaluate() but silently `continue`s in limit_dashboard(); the two reports on the same run disagree.

## Low
- **risk_lib/monitoring/recovery.py:33 & recovery_deep.py:46**: `groupby(default_id)[ead_col].first()` picks arbitrary row when EAD differs across rows for the same default.
- **risk_lib/monitoring/delinquency.py:63-66**: Segment groupby uses default `dropna=True` while the outer uses `dropna=False`; NaN-segment rows come out with NaN share/rate.
- **risk_lib/monitoring/vintage_deep.py:115-116**: `vintage_drift` silently skips segments with exactly `recent_n` cohorts (short-history segments missing from RAG grid).
- **risk_lib/limits/large_exposure.py:1467-1478**: `compute_aggregate` reads denom/basis from `p.iloc[0]` per framework, no invariant check.
- **risk_lib/monitoring/delinquency.py:98-124**: `transition_matrix` returns non-square matrix by dropping empty rows; iterating `grades` for `mat @ mat` breaks.

## Simplification win (worth noting)
- **risk_lib/monitoring/recovery.py:37-50 & recovery_deep.py:51-64**: Inner loop rebuilds `groupby(...).sum()` per month; a single `cumsum()` after sort would replace O(horizon×N) with O(N) work. ~60× speedup at horizon=60.
# Governance & audit: 19 findings (3 critical, 8 high, 5 medium, 1 low)

## Critical
- **risk_lib/board_pack.py:78-82**: Committee-dossier cover verdict is derived from 2선 self-validation only, ignoring the 3선 independent-validation gate that AIMS_POLICY.md declares fail-closed. Renders "결재 가능 (PASS)" while independent gate is 응답대기.
- **risk_lib/close_workflow.py:109-110, 122-131**: CL-10 "독립검증 게이트 확인" completion is judged solely by len(val_independent_target) > 0 (presence of the target list, not the verdict).
- **risk_lib/close_workflow.py:111-113, 122-131**: CL-11 결재 상신 judged by len(gov_approval) > 0 with no filter on asof/run_id. Stale approvals from a prior close satisfy the gate.

## High
- **risk_lib/governance/rbac.py:279-287, 341-360**: active_roles silently drops assignments whose valid_from/valid_to fail parsing; SOD detection then misses conflicting roles with malformed dates (fail-open).
- **risk_lib/archive.py:169-173**: scan() swallows every exception per 버전정보.json; corrupt file makes a version invisible in the ledger and retention audit.
- **risk_lib/governance/audit_chain.py:197-207**: collect_events uses str(r[use_actor]) with no NaN guard; 'nan' becomes a truthy actor and collides on record_id.
- **risk_lib/aig/trace.py:246-251, 261-275**: Chain hash omits prompt_text, payload_text, redaction_hits/rules; verify_chain never rehashes those bodies, so tampering the raw text alone leaves the chain "intact".
- **risk_lib/governance/audit_chain.py:139-142, 199**: occurred_asof stored as 10-char string, verified via str() on the reloaded DataFrame value (Timestamp → 19 chars); every row fails verify after parquet round-trip.
- **risk_lib/aig/trace.py:246-251, 269-272**: Same round-trip issue: str(None)='None' vs str(nan)='nan' breaks hash equality on reload.
- **risk_lib/audit_trail.py:111-113**: approval_evidence_status="결재원장" if approval_dt else "미확인"; any truthy string (placeholder "pending") upgrades evidence claim.
- **risk_lib/governance/model_lifecycle.py:212, 218-227**: Unknown inventory status silently maps to "개발", so a live production model without an approval is judged "증빙미첨부" (mild) instead of "승인없이운영" (heavy).

## Medium
- **risk_lib/governance/unified_run.py:105-110, 148-160**: _fingerprint hashes only (table_name, n_rows, n_cols); two different portfolios with same shapes collide.
- **risk_lib/governance/retention.py:187-195**: _fingerprint(df) sorts columns but not rows; reloader-driven row-order changes look like drift.
- **risk_lib/governance/retention.py:211-213**: status = "성공" if len(df) else "행수0"; the defined "미적재" enum is never assigned, hiding pipeline failures.
- **risk_lib/governance/audit_chain.py:62-66, 197-207**: canonical_digest uses json.dumps(default=str) on arbitrary pandas dtypes; same conceptual data yields different chain heads after dtype round-trips.
- **risk_lib/archive.py:97-109, 119-158**: TOCTOU: next_version scans then archive writes with no atomic reserve; two concurrent callers clobber v02.
- **risk_lib/board_pack.py:394-406**: Sign-off certificate hardcodes generic names with empty signature lines instead of reading gov_approval / gov_user_role.

## Low
- **risk_lib/governance/change_control.py:207-270**: evaluate_change_gate doesn't validate req.change_class / req.risk_tier against enums; malformed values slip through with no data-quality flag (fail-closed path is preserved, but signal is lost).
# Regulatory forms: 5 findings (0 critical, 1 high, 2 medium, 2 low)

Positive coverage: cross-form invariants for 위험가중자산 합계, 레버리지비율, 총자본비율, 대손준비금 소요액; Excel column mapping widths; KRW unit consistency (no 백만원/억원 mis-scaling); IRRBB Table 6 fail-loud on missing scenarios; frequency mapping complete.

## High
- **risk_lib/regulatory/cross_form.py:54-58**: `CrossFormInvariant("보통주자본비율")` registers ("BR-14","2100"): but `_br14` in `forms.py:637-643` emits `trough_cet1` (stressed low-water mark of whichever scenario iterates first), not current CET1. Under any real adverse scenario the invariant fails on every run; also fragile to `groupby(sort=False)` ordering in `stress/path.py:146-166`.

## Medium
- **risk_lib/regulatory/cross_form.py:59-68, 75-79**: Uses position-derived line codes on BR-31 (`1110` for 총자본비율, `1510` for LCR). `_camel_row` builds those codes from `t.iterrows()` order. Any reorder in `prudential/camel.py` silently makes 1110 point to a non-capital component. No name-based safeguard; sibling in `forms_fss_indicator.py` uses `_camel_row(rating, "자산건전성")` by name.
- **risk_lib/regulatory/forms.py:482 (BR-10 check)**: `_val(L, "2000") + _val(L, "3000")` treats `borrower_type ∈ {기업여신, 가계여신}` as exhaustive. A third bucket (공공여신, 외국인) would drop from the reconciliation with no failure.

## Low
- **risk_lib/regulatory/forms_fss_asset.py:970-973**: B2431 line 1030 citation `제29조 제1항`; the "충당금 합계 < 최저적립액이면 부족분은 대손준비금" semantic is 제29조 **제2항**. The module even defines `_C29_2` for this and doesn't use it.
- **risk_lib/regulatory/forms_base.py:109-113 (`_val`)**: Returns first line matching `line_code` silently. A future code-duplication (e.g. copy-paste in per-borrower blocks) resolves to whichever line was appended first; every `_sum_check` / `_ratio_check` relies on this.
# Orchestration & CLI: 8 findings (0 critical, 2 high, 4 medium, 2 low)

## High
- **risk_lib/report_chrome.py:159**: `_table` unconditionally emits any cell string containing `<` as raw HTML. HTML injection sink for any user-supplied portfolio field (asset_class, sector, country, rating, label) that flows into HTML reports (portfolio, printable, board_pack, executive, English board pack).
- **risk_lib/cli.py:365:393 (_cmd_reproduce)**: `reproduce` never re-passes the saved `asof` from the manifest to `run_pipeline`, so digest comparison silently uses a different reference date across day boundaries. Breaks the CLI's core promise of reproducibility.

## Medium
- **risk_lib/cli.py:493:499 + risk_lib/archive.py:93:139**: `deliverables --asof / --run-date` are joined into filesystem paths and zip names with no validation; user string can escape ARCHIVE_ROOT. `asof.replace('-', '')` doesn't strip slashes; `make_zip(root, root.parent / zip_name)` places the zip anywhere.
- **risk_lib/deliverables.py:178:181**: `build_deliverables` unconditionally `shutil.rmtree(out_root)` before writing. Combined with the path-traversal finding above, this is a "wipe attacker-chosen directory" primitive.
- **risk_lib/deliverables.py:96:98 + 150:157**: `write_manifest` excludes ANY file named `MANIFEST.txt` at any depth; `verify_zip.ok = not (mismatched or missing)` returns True even when files are unlisted. Nested MANIFEST files escape integrity attestation while the self-check passes.
- **risk_lib/cli.py:501:507 (validation-request subparser)**: subparser does NOT add `--institution`, so `_build_studio` falls through to `"(기관명)"` placeholder. Every standalone IV request is filed under a fake institution name.
- **risk_lib/api.py:266:281 + _cmd_serve**: Stdlib HTTP server accepts `--host 0.0.0.0` with no auth, exposing `/manifest`, `/headline`, deep-dives, and portfolio SHA to the LAN.

## Low
- **risk_lib/integrations.py:302:314 (IsolatingDispatcher.send_with_isolation)**: Retry helper is dead-on-arrival: `req.kind` doesn't exist on WebhookRequest, `send(payload)` expects dict but gets a dataclass, `hashlib.sha256(req.body)` gets str where bytes are required.
- **risk_lib/cli.py:257:262 (_cmd_ui_studio)**: `if codes == ["all"]:` strict-equality check misfires on `--institutions all,APAC_BANK_01`, raising instead of expanding. Fails loud (not silent), but the flag docs read as if 'all' were a list member.

## Positive signal
Reviewer verified no `shell=True`, `os.system`, `pickle.load`, or `eval/exec` reach user input. Templating uses `html.escape` at every site except the one `_table` bypass, which is the single verified XSS sink.
# validation-team-agent: 18 findings (4 critical, 4 high, 6 medium, 3 low, 1 architectural)

Independent-validation (3선) engine. Fail-open gates here directly defeat the AIMS Article 6 promise.

## Critical
- **validation-team-agent/tools/validation_finding.py:269 (close_finding)**: SoD "NOT_EVALUATED" treated as pass because the guard is `if enforce_sod and not sod["passed"] and sod["violations"]`: empty violations short-circuits the raise. A finding closed with no `--actor` becomes `status="closed"` and `approval_blockers()` no longer blocks `manifest promote --to applied`. Directly bypasses VAL-006 SoD and VAL-016 finding-gate.
- **validation-team-agent/tools/provenance.py:71-92 (request_fingerprint)**: `_scalar_fingerprint` returns None for numpy arrays / DataFrames / custom objects; the guard `if coerced is not None or v is None` drops those keys silently, so two requests differing only in array payloads produce identical scalar_sha256. Reproducibility hash is defeated.
- **validation-team-agent/src/vta/handlers/registry.py:198-322 (all Basel handlers)**: NaN/Inf/missing inputs return `StepResult(status="skipped")`. WorkflowEngine.run only activates `on_fail_activate` on status="fail", and `audit_handler` counts only fail+warning. Every Basel domain (capital, LCR, IRRBB, market, CVA, CCR, op) can be silently bypassed by NaN in the payload.
- **validation-team-agent/tools/independent_recalc.py:196-233 + tools/adversarial_review.py:98-115**: When `--validation-inputs` is omitted, `val_inputs = inputs_operational`; recomputation trivially equals `claimed`, `status="ok"`, verdict `SURVIVED`. The 3선 pipeline reads verdict, not the "note" about missed independence: CLAUDE.md §6 independence violated.

## High
- **validation-team-agent/tools/provenance.py:110-114 + tools/pack_verify.py:146-153**: Corrupted policy files silently become `"(unreadable)"`; two "unreadable" strings compare equal in the drift check, so junk policies pass verify.
- **validation-team-agent/tools/pack_verify.py:157-160 (git_info)**: When git errors at build and verify, both return `rev="unknown", dirty="no"`; `"unknown"=="unknown"` passes and code identity is never proven. `dirty` derived from `bool(_run(...))` also silently reports "no" if the subprocess errors on a dirty tree.
- **validation-team-agent/tools/golden_regression.py:161-178 (classify_changes / run_all)**: `deploy_allowed` blocks only on `critical` unintended failures; medium/high unintended regressions pass. VAL-012 promises "비의도 변경 → 배포 차단" without severity qualifier.
- **validation-team-agent/tools/run_ifrs9_validation.py:361 & tools/run_validation.py:405**: CLI exit codes reflect only `completeness` and `citations`; `weight_violations`, `scenario_order`, PII findings, sample-size passed, watermark passed are all ignored. CI reading exit codes accepts substantively broken reports as PASS.

## Medium
- **validation-team-agent/src/vta/core/workflow.py:269-275 (_classify)**: All exceptions from `classify_error.classify` swallowed and mapped to `category="code"`; wrong root-cause routing with no signal.
- **validation-team-agent/middleware/permission_guard.py:73-79 (load_patterns)**: Broken permission_matrix.json silently falls back to smaller `_FALLBACK_PATTERNS`; org-specific patterns disappear and `check_commands.clean=True` for commands the org would flag.
- **validation-team-agent/middleware/schema_guard.py:47-52 (_dtype_check for "date")**: Only first 20 non-null rows are parsed as datetime; rest accepted. 999,980 "N/A" rows after 20 valid dates pass the check.
- **validation-team-agent/middleware/draft_watermark_guard.py:35-36**: Watermark verification is substring search over the entire document; a mention in a footnote counts as a header.
- **validation-team-agent/tools/manifest.py:113-149 + tools/conditional_approval.py:112-114**: TOCTOU on verdict-adjacent JSON stores: concurrent `manifest promote` or `conditional_approval grant` clobber each other with no lock / no version check.
- **validation-team-agent/src/vta/handlers/registry.py:125-155 (credit_calibration_handler)**: Binomial calibration rejects → status="warning" (not "fail"), so on_fail_activate doesn't fire and no `9.escalate` step runs. Severe miscalibration produces a warning that never escalates.
- **validation-team-agent/src/vta/handlers/registry.py:641-645 + audit_handler**: The mandated "자체검증 (2선) / 상시 독립검증 (3선)" two-line report format is enforced nowhere in the runtime; runner reports can omit the 3선 line and still say "검증 완료".

## Low
- **validation-team-agent/src/vta/handlers/registry.py:509-568 (report_handler)**: `dict.keys()` iteration is completion order under `run_async`; report_md digest is non-deterministic across identical runs.
- **validation-team-agent/tools/independent_recalc.py:62-71 (within_tolerance)**: `math.isclose(rel_tol=1e-9, abs_tol=1e-12)` silently widens `tolerance=0.0`.
- **validation-team-agent/tools/manifest.py:65**: `datetime.now()` naive local wall-clock; cross-region audit trails not monotone.
