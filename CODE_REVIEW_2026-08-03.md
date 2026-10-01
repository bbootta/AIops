# 전체 저장소 코드 리뷰 — 35주차 (2026-08-03)

**직전 리뷰:** PR #54 (2026-08-02 21:11 UTC) 이후 ~24h.
**리뷰 시점:** 2026-08-03 21:xx UTC.
**결과 헤드라인:** **B9Kxm 대확장 delta (9커밋 · +5,312 / -113 LOC)** — 신용 파이프라인 재구조(ECL→EAD, 4-branch parallel), 신설 원장 4종(집합투자증권 CRE60 · 파생 SA-CCR · 유동화 CRE40~45 · 도메인집계), 콕핏 자본 KPI 제약 계층 시정(+4.13조 RWA · CET1 11.70%→8.12% 재고정). Pw9F5 HEAD 무커밋 24h. PR #46 dead-store **8주 확정**. **34주차 신규 P3×3 (P3-6/7/8) 전건 LIVE + 심화 검토로 P1×1 · P2×2 재분류.** 신규 P0×0 · P1×4 · P2×6 · P3×4.

---

## §1. 감시 활동 (24h)

| 브랜치 / PR | 직전 HEAD | 신규 HEAD | 신규 커밋 | LOC (add / del) |
|---|---|---|---|---|
| **B9Kxm** (PR #5) | `676b6531` | `d47f866e` | **9** | **+5,312 / -113** |
| Pw9F5 (PR #4) | `29eb4243` | `29eb4243` | **0** | — (24h 무커밋) |
| PR #38 (khpuk3) | `a9bbf3b5` | `a9bbf3b5` | 0 | — |
| PR #46 (i79qef) | `01fc7cb4` | `01fc7cb4` | **0** | — (**7일 무커밋 · blob `0e0288c9…` 불변**) |
| PR #10 (tqv3ii) | `844fb48b` | `844fb48b` | 0 | — (3일 무커밋) |
| 기타 표본 | (변동 없음) | — | 0 | — |
| `main` | `281d6017` | `281d6017` | 0 | — (33일 무변경) |

**핵심 판정:**

1. **B9Kxm — CRE60(집합투자증권)·CRE40~45(유동화)·CRE52(SA-CCR) 원장 3종 신설 + 파이프라인 재구조.** 5,312줄 delta. `_branch_credit`/`_branch_market_op`/`_branch_ccr`/`_branch_structured` 4-branch ThreadPool 병렬화(pipeline.py:822-827). ECL이 신용 EAD보다 선행하게 재정렬(CRE20 정합). 콕핏 자본 KPI가 CET1 단일 지표만 보고 초록 표시하던 문제 시정 — 총자본 −0.56%p 미달·기본자본 −0.34%p 미달을 최상단에 표시하며 판정을 KPI 원장에서 파생.
2. **34주차 신규 P3×3 심화 검토로 상향 재분류.** P3-6 → **P2** (market_scope FRTB 라벨 route 불일치), P3-7 → **P2** (LCR HQLA 회사채·주식 blanket 편입), P3-8 → **P1** (9300 차입약정 borrower 방향 오분류 → 우리 차입에 phantom EAD).
3. **신규 P0×0 · P1×4 · P2×6 · P3×4.** 신설 원장(funds/derivatives/exposure_agg/securitisation) 심층 검토 결과 4-4-4 배분. 규제 오산출 3건(fund SA-CCR PFE ~4.4× 과소 · SEC-SA K_A NaN 무방어 · retail_other 100% vs 75% 하드코딩 라벨), 데이터 함정 3건(NaN 만기 → 리터럴 "nan" 버킷 · ECL 미매칭 → Stage1 fillna · UNRATED > CCC- rank 트랩).
4. **PR #46 8주 확정.** blob `0e0288c9…` 7일 무커밋 유지. warden 격상 사이클 forcing 부재 8주 연속 실증. external escalation 검토 발동 후 4주 무액션.

---

## §2. 이번 라운드 카운트

| 항목 | 카운트 |
|---|---|
| 신규 P0 | **0** |
| 신규 P1 | **4** — 9300 방향(코드 스코프) · SA-CCR PFE 과소(funds) · NaN "nan" 버킷(exposure_agg) · SEC-SA K_A NaN 무방어(securitisation) |
| 신규 P2 | **6** — market risk_factor · LCR HQLA blanket · catalog FK 누락 · UNRATED worst-rating · ECL fillna(1) Stage1 · swaption DV01 δ 누락 + retail_other 라벨 하드코딩 · IRBA 채택 flag 원천 불일치 |
| 신규 P3 | **4** — pipeline ThreadPool 잠재적 CCR pre-fill · rw_before_floor 캡-후 라벨 · `_clip_mt` NaN 무가드 · `sec_erba_rwa` resec 인자 누락 |
| Regression | **0** |
| Escalation | **1** — PR #46 7주 확정 → **8주 확정** |
| Reclassification | **3** — 34주차 P3-6/7/8 → **P2/P2/P1** (심화 검토) |
| Tracked LIVE 재확인 | 34주차 58건 - 재분류 이동 3 + 신규 14 + 격상 유지 = **69** (P0×8 · P1×12 · P2×22 · P3×27) |

---

## §3. Pw9F5 (PR #4)

HEAD `29eb4243` 24h 무커밋. 34주차 CHG-0162 (`reg_rules.py`) · CHG-0163 (§2 8부문 재선언) 이후 활동 정지. 34주차 신규 P3×2 (`reg_rules.py` verify KeyError · replaced_by 체인) **여전 LIVE**. `conditional_approval.json` 회차 접미사 P1 **6일** 미이행 (34주차 5일 → +1).

이번 라운드 신규 finding 없음. 감시 유지.

---

## §4. B9Kxm 대확장 심층 — 신규 P1×4 · P2×6 · P3×4

### §4.1 9-커밋 요약

| SHA | 시각 (UTC) | 주제 | 대략 LOC |
|---|---|---|---|
| `1fa62ed9` | 08-02 23:10 | 코드 스코프 산출 엔진 직접 연계 (별사본 금지) | 중 |
| `87e6cf6b` | 08-03 00:28 | 산출 의존성 재구조 (ECL→EAD 선행 · 4-branch parallel) | 중 |
| `6dc7c419` | 08-03 05:07 | 익스포저 원장에 계정/상품 코드 · 도메인 집계 원장 · 코드마스터 2단 화면 | 중 |
| `6195703c` | 08-03 05:26 | 집합투자증권 CRE60(LTA/MBA) · 파생 CRE52(SA-CCR) 원장 신설 | +1,322 (funds+derivatives) |
| `92e71a8b` | 08-03 05:57 | 유동화 CRE40~45 원장 · 도메인 집계 · 산출 방법론 설정 화면 | +1,484 (securitisation+exposure_agg) |
| `c6c73c16` | 08-03 06:00 | 방법론 화면 전환 회귀 · 16차 재요청 지문 갱신 | 소 |
| `d0cb1f49` | 08-03 06:58 | '모형' 메뉴그룹 1레벨 신설 — 도메인 전 모형 거버넌스 | 중 |
| `89917dab` | 08-03 08:31 | 구조화 익스포저 자본비율 분모 통합 (+4.13조 RWA · CET1 재고정) | 중 |
| `d47f866e` | 08-03 08:38 | 콕핏 자본 KPI 제약 계층 표시 시정 | 소 |

두 재고정 (골든 5·CET1 8.12% / 골든 4·ECL→EAD 순서) 이 실행됐다 — 값이 바뀌었으므로 자기공시. 자체 적대적 검증이 29건을 잡아 시정했다고 커밋에 명시 (SEC-SA/ERBA/IRBA 재유동화 하한 100% · MBA break bug · SSFA 27트렌치 독립 재구현 대조 등).

### §4.2 신규 P1 — 4건

#### P1-9 (B9Kxm) 9300 차입약정 borrower 방향 오분류 · **34주차 P3-8 → P1 재분류**

**파일:** `risk_lib/datamodel/code_scope.py:103` (`_ACCT_CCF`) + `:133-135` (`credit_scope()`).

```python
_ACCT_CCF = {
    "9100": "direct_credit_substitute",
    "9200": "unconditionally_cancellable",
    "9300": "commitment_gt_1y",   # ← 방향 반대
}
```

9300 은 은행 자신이 **받은** 차입약정(우리가 차입 가능한 committed line) — borrower 측. `commitment_gt_1y` 는 lender 측 CCF (우리가 제공한 미사용약정). 9300 매핑 결과 `credit_scope()` 이 우리 차입 라인을 `in_scope=True` + `ccf_rate=CCF_BUCKETS["commitment_gt_1y"]=0.40` + `default_recognition="거래상대방 부도"` 로 처리 → 우리 자신의 차입 총한도가 우리 신용 EAD 로 위장. 코드 스코프 화면·RWA 화면 개발자가 이 매핑을 SoR 로 참조 시 신용 RWA 과대. **34주차엔 라벨 오분류(P3)로 판정했으나 재검토 결과 phantom EAD 를 실제 생성하므로 P1.**

**Failure scenario:** 9300 계정 잔액 = 5,000억원. `credit_scope()` 조인 결과 `ead_total ≠ 0` (익스포저 원장에 9300 계정 EAD 가 채워지면), `ccf_rate=0.40` 로 환산되어 `EAD_CCF=2,000억` 이 신용 익스포저로 표기. RWA 화면이 이를 corporate CCF EAD 로 통합 → 표준방법 신용 RWA 표시 왜곡.

**Fix (2줄):**
```python
# _ACCT_CCF 에서 9300 제거 (borrower-side)
# credit_scope() in_scope 규칙에 계정 방향(제공/수령) 컬럼 추가 또는 9300 명시 제외
```

#### P1-10 (B9Kxm) fund SA-CCR PFE add-on 과소 (~4.4×) — 감독기간·supervisory-delta 미적용

**파일:** `risk_lib/datamodel/funds.py:245-252` (`saccr_trade_view`).

동일 브랜치 `derivatives.py:501` (`saccr_input`) 는 `adjusted_notional × |δ|` pre-multiply 하는데, funds 경로는 raw `notional` 만 넘김. `ccr.saccr_ead` 는 `SF["ir"] × N × √min(T,1)` 만 계산 → 5년 IRS 100bn 명목의 add-on 이 `0.005 × 1e11 × 1 = 5.0e8` 로 산출됨. CRE22.51 상 correct 계산은 supervisory duration `SD(0,5)=4.42` + supervisory delta `|δ|=1` 반영해야 하며 `0.005 × 1e11 × 4.42 × 1 = 2.21e9` (약 4.4× 큼). **모든 fund IR/credit 파생의 PFE add-on 이 4.4× 과소** → CCR EAD 과소 → 신용 RWA 과소.

**Failure scenario:** 집합투자증권 편입자산에 5년 IRS 100bn 이 존재하는 펀드 → funds 경로가 `saccr_trade_view` 로 원본 명목 그대로 `ccr.saccr_ead` 전달 → add-on 5억 (correct 22억) → CCR EAD 5억 vs 실제 22억. RWA 3배 이상 저평가.

**Fix:** `saccr_trade_view` 에서 `_supervisory_duration` · `_adjusted_notional` (derivatives.py 참조) 적용 후 `|supervisory_delta|` 곱해 넘길 것. 또는 funds 경로를 derivatives 의 `saccr_input` 재사용.

#### P1-11 (B9Kxm) `_bucket()` NaN/inf 만기 → 리터럴 `"nan"` 그룹 생성

**파일:** `risk_lib/datamodel/exposure_agg.py:37-39` (동일 로직이 ALM `repricing_bucket` 에서도 재사용됨).

```python
def _bucket(series, edges, labels):
    return pd.cut(series, bins=edges, labels=labels, right=False).astype(str)
```

`pd.cut(..., right=False)` 은 반열림 구간이라 상한 초과값·NaN 을 NaN 으로 반환. `.astype(str)` 이 NaN → 리터럴 문자열 `"nan"` 로 강제. 하류 `groupby([..., "bucket"], dropna=False)` 는 `"nan"` 을 정상 label 로 처리 → 무만기 예금·영구채·상한 초과값이 `"nan"` 버킷에 조용히 모임. 하류 소비자가 `bucket in _TENOR_LABELS` 필터하면 조용히 사라짐 (기획된 `dropna=False` 를 astype 이 무력화).

**Failure scenario:** 요구불예금 잔액 3조 (만기 NaN) → `"nan"` 버킷 → 리프라이싱 갭·NSFR available stable funding 화면이 이 3조를 "5년 초과" 나 다른 정상 버킷 어느 쪽에도 잡지 않음. 회귀 테스트는 EAD 총합만 검사 (`exposure_agg.py` 총계 항등식) 이라 통과.

**Fix:** `.astype(str)` 제거 (Categorical 유지 → NaN 은 NaN 으로 남고 dropna=False 가 실제 작동). 문자열 dtype 필요 시 `.fillna("미분류")` 명시 후 label domain 에 추가.

#### P1-12 (B9Kxm) SEC-SA `k_sa` 세그먼트 `sa_risk_weight` NaN 무방어

**파일:** `risk_lib/datamodel/securitisation.py:381`.

```python
k_sa = float((g["balance"] * g["sa_risk_weight"]).sum() / bal) * BIS_MIN_TOTAL
```

바로 뒤 line 386 `k_irb` 은 `if g["irb_capital_requirement"].isna().any(): raise` 명시적 방어. SEC-SA 는 대응 방어 없음. 세그먼트 하나가 NaN 이면 `k_sa=NaN` → `k_a=(1-w)*NaN + w*0.5 = NaN` → `_ssfa_risk_weight(k=NaN)` → SSFA 지수 항 전부 NaN → 최종 `build_securitisation` assertion `if out["rw_sa"].isna().any(): raise` 에 도달해서야 크래시. 근본 원인이 SSFA-단계 실패로 위장되어 진단 왜곡. **SEC-SA 는 계층 하한(fallback floor)** 이라는 아키텍처 계약 위배.

**Failure scenario:** 외부에서 `rdm_sec_pool` 을 로드하거나 신규 seed 에서 세그먼트 하나의 SA 위험가중치 미기재 → `sec_sa_rwa` 크래시 원인이 "SSFA formula NaN" 로 보고됨 → 실제 원인(pool 원장의 SA input 결측)을 찾는 데 시간 낭비.

**Fix (line 386 대칭 방어):**
```python
if g["sa_risk_weight"].isna().any():
    raise ValueError(f"{deal_id}: 세그먼트 SA 위험가중치에 NaN — SEC-SA 산출 불가")
```

### §4.3 신규 P2 — 6건 + 재분류 2건

#### P2-17 (B9Kxm) `market_scope()` FRTB 라벨-risk_factor 라벨 불일치 · **34주차 P3-6 → P2 재분류**

**파일:** `risk_lib/datamodel/code_scope.py:193-195`.

```python
"risk_factor": ("금리" if grp in ("파생", "자금") or c == "P-BND"
                else "주가" if c == "P-EQT"
                else "환율" if cur == "외화" else "—") if in_scope else "—",
```

`P-FXS` (통화스왑, grp="파생", cur="외화") · `P-OPT` (옵션, grp="파생", cur="외화") 는 `grp in ("파생","자금")` 이 먼저 매치되어 `risk_factor="금리"` 로 확정. 그러나 같은 행의 `_PROD_FRTB` 매핑은 `P-FXS`/`P-OPT` → **FX**. 한 행에 `frtb_class=FX` / `risk_factor=금리` 로 상충 → FRTB-vs-scope 정합 대사 불가 · 시장 콕핏이 잘못된 스트레스 축으로 라우팅.

**Fix (우선순위 재정렬 · 3줄):**
```python
"환율" if cur == "외화" else "금리" if grp in ("파생","자금") or c == "P-BND"
    else "주가" if c == "P-EQT" else "—"
```

#### P2-18 (B9Kxm) `alm_scope()` LCR HQLA blanket 편입 (회사채→L2A, 주식→L2B) · **34주차 P3-7 → P2 재분류**

**파일:** `risk_lib/datamodel/code_scope.py:202-209` (`_ACCT_LCR`) → `:220-228` (`alm_scope()`).

```python
_ACCT_LCR = {
    "1210": "Level 1", "1220": "Level 2A", "1230": "Level 2B", ...
}
```

LCR30 은 Level 2A 회사채 = ≥AA-, Level 2B 주식 = 주요 지수 편입 + 50% haircut + 스트레스 가격 회복력 요건. `_ACCT_LCR` 은 등급 필터 없이 1220 전건 → L2A, 1230 전건 → L2B 로 편입 → `alm_scope()` 이 모든 회사채·주식에 `lcr_factor` 를 부여. `alm_lcr_item.factor` 조인 시 HQLA 총량 실제 대비 과다.

**Fix:** 1220/1230 은 `lcr_category="제한적 편입 — 요건 별도"` 로 표시하고 factor NaN 유지. 또는 exposure 행의 `rating`/index 회원 정보를 읽는 eligibility helper 로 분리.

#### P2-19 (B9Kxm) `catalog.py` 신규 테이블 7종에 `foreign_keys` 미선언

**파일:** `risk_lib/datamodel/catalog.py:83` (EXPOSURE) + R13 블록 (RDM_FUND_HOLDING/MANDATE, RWA_FUND_RESULT, RDM_DERIVATIVE_UNDERLYING, RDM_NETTING_SET, RDM_SEC_TRANCHE/POOL, RWA_SEC_RESULT).

EXPOSURE 에 `account_code`·`product_code` 추가하며 docstring 이 "`rdm_account_master`·`rdm_product_master` 참조" 라 명시했으나 `foreign_keys` 튜플 미확장. 신규 R13 테이블 각각도 부모 참조(fund_id · trade_id · deal_id · tranche_id · netting_set_id) 를 갖는데 FK 선언 없음. `spec.py:214` 는 `spec.foreign_keys` 순회로 참조무결성 검사 → 튜플 빈 상태로 orphan 행 통과. 화면이 `left_join` 하면 조용히 빈 자산군 breakdown 산출. **+4.13조 RWA 재고정 라운드에서 attribution 반증 불가**.

**Fix:** EXPOSURE 에 `FK(("account_code",), "rdm_account_master", ("account_code",))` · `FK(("product_code",), "rdm_product_master", ("product_code",))` 추가. R13 자녀 테이블 각각에 대응 FK.

#### P2-20 (B9Kxm) `worst_rating` UNRATED > CCC- 순서 트랩

**파일:** `risk_lib/datamodel/funds.py:590-591`.

```python
RATINGS = (..., "B", "CCC-", "UNRATED")
worst = RATINGS[max(RATINGS.index(r) for r in ...)]
```

`RATINGS.index("UNRATED") = 6 > RATINGS.index("CCC-") = 5`. 오늘은 `_RATING_POOL` 이 rated·UNRATED 를 disjoint asset class 로 유지해 발화하지 않으나, private-placement 회사채 등 UNRATED 가 corporate 자산군에 섞이는 즉시 발화 → `worst="UNRATED"` → `_notch_down("UNRATED")="UNRATED"` → `holding_risk_weight("corporate","UNRATED")=1.00` **vs 실제 최악 CCC- 1.50**. **MBA capital 이 ~⅓ 저평가.** 커밋이 `holding_risk_weight` 에서 silent fallback 을 제거했다고 명시했으나 aggregation 층에서 동일 유형 잔존.

**Fix:** `_QUALITY_ORDER` dict 별도 정의 (UNRATED 를 rated 등급과 fallback 사이 또는 worst 후보에서 제외). "worst rated" + "any UNRATED share" 분리 계산 권장.

#### P2-21 (B9Kxm) `credit_aggregate` 미매칭 익스포저 → Stage 1 조용 흡수

**파일:** `risk_lib/datamodel/exposure_agg.py:47-50`.

`ecl_result` 는 `rdm_exposure` 의 strict subset. 매칭 실패 행에 `ecl=0.0, stage=1` fillna → Stage 3 impaired 로 ECL 을 만들지 못한 exposure 가 Stage 1 로 위장, `n_stage3` 집계 감소, `coverage_ratio=0`. 총계 항등식 테스트 (EAD sum) 는 통과 → NPL/staging 모니터링이 false zero 를 봄.

**Fix:** 미매칭 ID `stage="unknown"` 별도 버킷 또는 `ValueError` 발생. `.fillna(1)` 금지.

#### P2-22 (B9Kxm) swaption GIRR/CSR delta 미스케일링 — `dv01 × 1e4` 직 emit

**파일:** `risk_lib/datamodel/derivatives.py:404-408` · `:557-560`.

`_synthesise` 는 swaption 다리에 `dv01 = leg_notional * dur * 1e-4 * sign` (dur = E-S · underlying swap 전체 DV01). `market_sensitivities` 가 `delta_krw = dv01 × 1e4` 로 emit → ATM 2×5 payer swaption 의 실측 GIRR delta 는 `Φ(d1)·N·dur ≈ 0.5·N·5` 인데 화면·MAR21.8 delta 는 `N·5` → **ATM 에서 ~2× 과대, OTM 에서 그 이상**. SA-CCR 은 `saccr_input:501` 이 `|δ|` 명시 곱셈으로 무영향. 시장 감도 경로만 skip.

**Fix:** option/swaption 다리에 `dv01/cs01` emit 시 `abs(supervisory_delta)` 곱하거나 `market_sensitivities` 에서 `product_type ∈ {"option","swaption"}` 스케일링.

#### P2-23 (B9Kxm) NEW P2 (retail_other rw_range 하드코딩) — engine constant vs 표시값 mismatch

**파일:** `risk_lib/datamodel/code_scope.py:138`.

```python
rw_range = (f"{min(rw.values())*100:.0f}~{max(rw.values())*100:.0f}%"
            if isinstance(rw, dict) else
            "LTV 구간별" if ac == "residential_mortgage" else
            "75%" if ac == "retail_other" else "—")
```

`retail_other` 는 `SA_RISK_WEIGHTS` dict 에 없고 `_RW_RETAIL_OTHER=1.00` (rwa_sa.py:52) — 100%. **화면 표시가 75% 로 하드코딩되어 실제 엔진 적용치 100% 와 불일치.** 1320 가계대출 · 1340 신용카드채권 계정이 75% 로 화면에 표기되나 실제 RWA 는 100%. `retail_regulatory` 는 별도 스칼라 `_RW_RETAIL_REGULATORY=0.75` 이므로 두 부류의 라벨 혼동. docstring 이 "화면에 따로 적으면 엔진이 바뀔 때 매핑만 낡는다" 라 명시했으면서 스스로 위반.

**Fix:** `_RW_RETAIL_OTHER` · `_RW_RETAIL_REGULATORY` 를 rwa_sa 에서 import 하고 `rw_range = f"{_RW_RETAIL_OTHER*100:.0f}%"` 로 파생. 라벨/코드 매핑을 나눠 소지.

#### P2-24 (B9Kxm) SEC-IRBA `applicable_approach` master vs tranche 채택 flag 원천 불일치

**파일:** `risk_lib/datamodel/securitisation.py:1189-1193` vs `:741-745`.

`applicable_approach` docstring (line 258-260) 이 "master 와 tranche 가 같은 함수로 divergence 방지" 라 주장하나, master 는 `irb_available=r["irb_data_available"]` (seed-time flag), tranche summary 는 `irb_available=r["irba_available"]` (per-tranche computed flag, K_IRB NaN 또는 ≤0 시 False). SYNTHETIC seed 에선 일치하나 K_IRB=0 (매우 낮은 PD × LGD 로 `irb_capital_requirement` 가 0 반환) 시나리오에서 master `applicable_approach="SEC-IRBA"` · 전 tranche 실제 SEC-SA 채택 → 라벨-실행 divergence. line 1240-1242 assertion 은 K_IRB=NaN 만 잡음.

**Fix:** `_finalise_master` 가 `stats["k_irb"]` availability (non-NaN AND >0) 로 파생, seed flag 사용 금지. `sec_irba_rwa:637-641` 조건과 미러링.

### §4.4 신규 P3 — 4건

- **P3-28 (B9Kxm) pipeline `_branch_ccr` pre-SA-fill portfolio 참조 잠재적 hazard** (`pipeline.py:777-808`). 오늘 `compute_ccr` 이 PD/LGD 를 소비하지 않아 무영향. PD 기반 EAD 조정 추가 시 NaN PD 로 CCR 결과 이탈 · 다른 domain 은 filled book. Fix: `book = _fill_sa_parameters(portfolio)` 를 pool submit 전에 한 번 계산 후 4개 branch closure 모두에 전달.
- **P3-29 (B9Kxm) `rw_sa_before_floor`/`rw_irba_before_floor` 라벨 mislead** (`securitisation.py:317-319, 503, 688`). `_ssfa_risk_weight` 이 `raw = min(raw, RW_CAP)` 로 캡 후 반환하나 caller 가 `rw_sa_before_floor: raw` 로 저장 → cap event 원장 부재. 감사가 "왜 정확히 12.5?" 추적 시 불투명. Fix: `cap_applied_*` 컬럼 추가 또는 라벨 rename.
- **P3-30 (B9Kxm) `_clip_mt(NaN)` 무가드 → `_irba_p` NaN 전파** (`securitisation.py:237-239`). `max(NaN,1)/min(NaN,5)` = NaN → `_irba_p` → `p=NaN` → SSFA 전 항 NaN. 최종 assertion 이 잡으나 trace 가 요약 지점을 가리켜 진단 왜곡. `__all__` 이 `sec_irba_rwa` export 하므로 외부 caller 노출. Fix: `if not math.isfinite(mt): raise ValueError`.
- **P3-31 (B9Kxm) `sec_erba_rwa` `tranche_rw_floor` 호출 시 `resecuritisation` kwarg 미명시** (`securitisation.py:555`). 오늘 line 545-548 resec-guard 로 실 도달 불가. 향후 누군가 guard 재편 시 ERBA 경로가 조용히 15% floor 를 재유동화에 적용 (CRE41.19 위반). `sec_sa_rwa:478` 은 `resecuritisation=resec` 명시. Fix: `floor = tranche_rw_floor(stc=stc, senior=senior, resecuritisation=False)` 로 defense-in-depth.

### §4.5 콕핏 자본 KPI 시정 · +4.13조 RWA 재고정 평가

**콕핏 KPI 시정 (`d47f866e`)** — CET1 8.12%/요구 8.00% 여유 +0.12%p 만 보고 초록이던 것을 총자본 -0.56%p / 기본자본 -0.34%p 완충자본 미달을 최상단에 표시. 판정을 KPI 원장에서 직접 파생, 별계산 경로 신설 안 함. **적정 시정** — 이전 배포는 배당·성과급 제한 상태를 초록으로 표시 (규제 리스크). test_capital_kpi_follows_the_binding_tier_not_just_cet1 로 고정. **신규 finding 없음.**

**구조화 익스포저 자본비율 통합 (`89917dab`)** — 집합투자증권(3.331조) · 유동화(0.797조) 를 자본비율 분모에 통합 (+4.13조 RWA). 재고정 사유가 명확 · 이중계상 근거(모집단 disjoint)를 test 로 고정. output floor 표준 총계에서 SEC-IRBA 제외 (RBC20.11 정합). 레버리지 장부 익스포저 2.190조 포함 (LEV20.1 정합). ICAAP 신용 경제자본에 구조화 × 8% 추가. `bis_buffer_requirement` 신규 통제로 이전 검사(Pillar 1 최저만)의 blind spot 노출. **매우 적정한 정합화 · 신규 finding 없음.**

### §4.6 병렬 실행 안전성 (pipeline.py `87e6cf6b`)

- **RNG state:** 각 `np.random.default_rng(seed + offset)` 개별 offset (7100 · 909 · 6100/6200/6300 · 7400/7410/7420). 공유 global RNG 없음. **안전.**
- **DataFrame mutation:** `_fill_sa_parameters` / `_stage_split_books` 는 `.copy()` 후 변경. `_branch_market_op`/`_branch_structured` 는 portfolio 미터치. `_branch_ccr` 은 fresh view boolean-index. **오늘 writer-reader collision 없음.**
- **잠재 hazard:** §4.4 P3-28 참조 — `_branch_ccr` 이 pre-SA-fill portfolio 를 슬라이스 · 다른 모든 downstream 은 filled `book` 참조. 오늘 무영향이나 계약이 invariant 미강제.

---

## §5. PR #38 (khpuk3, 3d-shooting) 델타

HEAD `a9bbf3b5` 24h 무커밋. 34주차 skinned mesh 커밋(`a9bbf3b5`) 이후 활동 정지. tracked LIVE (`build_content.py` P1×2 + hope-shooter dispose + Unreal C++ 미검증) 유지. 순수 렌더링 계층은 표본 감시 지속.

---

## §6. PR #46 격상 — dead-store **8주 확정**

**격상 이력 (연장):**

| 주차 | 판정 |
|---|---|
| 26주차 | P1 최초 (render.js dead-store × 3) |
| 28주차 | P0 검토 발동 |
| 29주차 | P0 격상 |
| 30주차 | warden 프로세스 실패 격상 |
| 31주차 | external escalation 검토 조건 발동 |
| 32~34주차 | 5→7주 미이행 |
| **35주차** | **8주 확정** — HEAD `01fc7cb4` 7일 무커밋, blob SHA `0e0288c9…` 유지 |

**판정:** warden 격상 사이클 자체가 forcing 함수 없음 **8주 연속** 실증. external escalation 검토 발동 4주째 무액션. warden 사이클이 non-forcing 임이 완전 확정 — 절차 자체 재설계 필요.

---

## §7. Tracked LIVE 총괄

| PR / 브랜치 | 항목 | 방치 |
|---|---|---|
| **PR #46** | **`render.js:597,601,606` dead-store (P0)** | **8주 확정** |
| PR #10 | 동물/마을주민 dispose 누수 R8 확장 (P1) | 7주 |
| PR #10 | 동물 재질 per-instance jitter (P2) · warden 벽투과 (P1) | 9일 / 13주 |
| PR #5 (B9Kxm) | Basel B RW · SRISK · CoVaR own-loss mask (P0×3) | **18주** |
| PR #5 (B9Kxm) | 29주차 P2×2 + P3×4 · 30주차 test_assumption grep (P1) + P2×4 + P3×4 | active |
| **PR #5 (B9Kxm)** | **34주차 P3-6/7/8 → 재분류 P2/P2/P1 (§4.2/§4.3)** | **~재분류** |
| **PR #5 (B9Kxm)** | **NEW P1×4 · P2×6 · P3×4 (§4.2/§4.3/§4.4)** | **~신규** |
| PR #4 (Pw9F5) | CHG-0143 + ERRATA (P0) | 14주 |
| PR #4 (Pw9F5) | conditional_approval 6차 canonical (P1) + P2×4 + P3×4 | 6일 |
| PR #4 (Pw9F5) | 33주차 P3×3 (validation_memory) · 34주차 P3×2 (reg_rules) | 24h~48h |
| PR #48 | hand3d.js P2×2 + P3×3 | 6주 |
| PR #38 | build_content.py · hope-shooter dispose · Unreal C++ 미검증 | 6주 |
| PR #43 | `.claude/settings.json` commit SHA 핀 (P1) | 10일 |

**합계:** P0=**8** · P1=**12** · P2=**22** · P3=**27** = **69건 LIVE** (34주차 58 + 신규 14 - 재분류 이동 3 → 68 + 격상 +1 유지).

---

## §8. 다음 라운드 (36주차) 즉시 항목

1. **B9Kxm P1-9 (9300 direction)** — 2줄 시정, `_ACCT_CCF` 에서 9300 제거 + `credit_scope()` in_scope 규칙에 방향 컬럼 추가.
2. **B9Kxm P1-10 (fund SA-CCR PFE)** — `saccr_trade_view` 를 `derivatives.saccr_input` 재사용 또는 supervisory-duration/delta 명시. 규제 오산출.
3. **B9Kxm P1-11 (NaN "nan" 버킷)** — `_bucket()` `.astype(str)` 제거, Categorical 유지. 리프라이싱·NSFR 화면 영향.
4. **B9Kxm P1-12 (SEC-SA K_A NaN 방어)** — line 386 대칭 방어 3줄.
5. **B9Kxm P2×6 + P3×4** — 시정 총 ~40줄. catalog FK 선언은 spec 재검증 후 회귀 다수 예상.
6. **PR #46 external escalation 실행** — 8주 확정 · 검토 발동 4주 무액션. warden 사이클 non-forcing 완전 확정 후 대안 필요.
7. **Pw9F5 `reg_rules.py` P3×2 + `conditional_approval.json` P1** — 6일 무커밋 지속. 활동 재개 시 우선.
8. **B9Kxm 17주 tracked P0×3 (Basel B RW · SRISK · CoVaR)** — 34주차 active 복귀 · 35주차 대확장 실증에도 미터치. tracked P0 최장 연령 갱신.

---

## §9. 리뷰 방법 · 재현

**감시 대상 (35주차):**
- `main` HEAD 확인, tracked-active 브랜치 4개 (Pw9F5 · B9Kxm · khpuk3 · i79qef) 최신 commit list 조회.
- 신규 커밋 발생 브랜치 (B9Kxm 만) 파일별 diff 확인 (`git diff --stat` + `git diff <path>`).
- PR #46 blob SHA (`get_file_contents fields=["sha"]`) 로 32~35주차 4주 연속 대조.

**심층 대상 결정:**
- 신설 원장 파일 4종 (`securitisation.py` 1,285 · `funds.py` 687 · `derivatives.py` 635 · `exposure_agg.py` 199) — 각 파일 3개 병렬 sub-agent (일반 목적) 로 심층. sub-agent 별 finding 5건 cap.
- `code_scope.py` diff (676b6531..d47f866e) 로 34주차 P3-6/7/8 잔존 여부 명시적 확인.
- `pipeline.py` ThreadPool 병렬화 부분 mutation-safety 심층. RNG offset · DataFrame copy 확인.
- 콕핏 · 구조화 통합 커밋은 회귀 test 존재 + 재고정 사유가 문서화되어 있어 표본 감시.

**신규 finding 판정 기준:**
- **P0:** 실행 시 반드시 관측되는 결함 + 산출값 최소 1자리 이동. 이번 라운드 0건.
- **P1:** 실행 시 관측되는 결함이거나 phantom 값 생성 · 규제 산출 오차 배수급. 4건.
- **P2:** 라벨 mismatch · 감사 추적 왜곡 · 감시 blind spot · 특정 시나리오 발화. 6건.
- **P3:** defense-in-depth, 오늘 미발화이나 계약/원장 무결성 저해 잠재.

**재현 절차:**
- P1-9: `python -c "from risk_lib.datamodel.code_scope import credit_scope; import pandas as pd; exp=pd.DataFrame({'exposure_id':[1],'account_code':['9300'],'ead':[5e11]}); print(credit_scope({'rdm_exposure':exp}).query(\"account_code=='9300'\"))"` → `in_scope=True`, `ccf_rate=0.40`, `default_recognition="거래상대방 부도"`.
- P1-10: `python -c "from risk_lib.datamodel.funds import saccr_trade_view; import pandas as pd; h=pd.DataFrame({'holding_id':[1],'fund_id':['F'],'instrument_type':['ir_swap'],'notional':[1e11],'maturity_years':[5],'market_value':[1e9],'asset_class':['ir']}); print(saccr_trade_view(h))"` — add-on 비교.
- P1-11: `python -c "import pandas as pd, numpy as np; from risk_lib.datamodel.exposure_agg import _bucket; s=pd.Series([np.nan, 1.5, 100]); print(_bucket(s, [0,1,3,10,30,1000], ['1이내','3이내','10이내','30이내','30초과']).tolist())"` — 첫 원소 `'nan'` 확인.
- P1-12: `rdm_sec_pool` 에 세그먼트 하나의 `sa_risk_weight=NaN` 삽입 후 `python -m risk_lib.datamodel.securitisation.build_securitisation` → 최종 assertion 크래시, 원인 진단 불명확.
- P3-6/7/8 잔존: `git -C /home/user/AIops diff 676b6531..d47f866e -- risk_lib/datamodel/code_scope.py | grep -A2 "risk_factor\\|lcr_category\\|9300"` — 매핑 표 변경 없음 확인.

---

## §10. 결론

**Δ:** 35주차 delta 는 B9Kxm 단독 · 5,312 LOC · 원장 4종 신설 + 파이프라인 재구조. 자체 적대적 검증이 29건 잡아 시정한 것은 눈에 띄는 문화 개선이나, **fresh-eyes 심층 검토에서 P1×4 · P2×6 · P3×4** 가 추가 도출. 규제 오산출 3건(9300 방향 · fund PFE 4.4× 과소 · SEC-SA K_A 무방어)은 커밋 저자가 자기 코드 대상으로 놓친 결함이며, "실패할 수 있는 검사여야 한다" 원칙이 신설 원장에서 부분적으로만 관철됐음을 실증.

**34주차 신규 P3×3 전건 LIVE + 3건 모두 심화 검토로 상향 재분류** — 최초 발견 시점의 P3 판정이 조기 판단이었음. 방어선 이슈로 보였던 것들이 실제로는 phantom EAD · 라벨/실행 divergence · HQLA 과다 편입을 즉시 야기. P3 → P1/P2 재분류 3건은 새 데이터가 아니라 재검토 결과다.

**Pw9F5 24h 무커밋** — 34주차 CHG-0162 카탈로그 신설 이후 활동 정지. `conditional_approval.json` P1 6일 미이행. Pw9F5 는 이번 라운드 감시만.

**PR #46 8주 확정.** warden 사이클 non-forcing 완전 확정. external escalation 절차 발동 4주 무액션 · 절차 자체가 forcing 이 아님. 다음 라운드에서 warden 사이클 재설계 여부 결정 필요.

**Tracked LIVE 69건.** 34주차 58 + 신규 14 - 재분류 이동 3 - 격상 유지 = 69. tracked P0 8건 중 5건(PR #46 dead-store + B9Kxm Basel B RW/SRISK/CoVaR ×3 + Pw9F5 CHG-0143 ERRATA)은 여전 미터치. **B9Kxm 대확장은 신규 기능 · 신규 원장 · 신규 화면 방향이며 tracked P0 해소 방향이 아니다** — 활동 재개 자체가 tracked 해소로 전환되지 않음을 재실증.

**머지 금지** — 리뷰 보고서 전달용 draft.
