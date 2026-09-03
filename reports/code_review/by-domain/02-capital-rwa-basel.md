# 02. 자본·RWA·Basel III 코드 리뷰

**리뷰 범위:** `risk_lib/capital/`, `risk_lib/pillar3*.py`, `risk_lib/frtb.py`, `risk_lib/capital_simulation.py`, `risk_lib/ncr.py`, `risk_lib/icaap/`, `risk_lib/prudential/`.

## HIGH

### 1. `risk_lib/capital/rwa_sa.py:44` (24, 34), 기업 SA 테이블 `"B"` 등급 100%
- CRE20.44 Table 4는 BB- 이하(B+/B-) 150%. `"BB"`가 이미 100%, `"CCC-"`는 150%. `"B"` 슬롯이 100%로 잘못.
- 실패 시나리오: KRW 1tn 무등급 B 기업대출 RWA 1.0tn, 자본 80bn (정답 1.5tn / 120bn). 자본 부족 40bn/1tn.

### 2. `risk_lib/capital/crm.py` (전 모듈) + `capital/crm.py:77~96`
- `crm_adjusted_ead`, `guarantee_substitution` 모두 CRE22.35~36의 만기 불일치 할인(Pa = P·(t-0.25)/(T-0.25))과 CRE22.55~58의 최소 보유기간 haircut scaling 미구현. Docstring(33)은 "10영업일, 일일 재마진" 고정, override 없음. 주간 재마진·20일 보유는 haircut 1.4~3배 과소.
- 실패 시나리오: 5년 100bn 기업대출, 담보 2년 국채 100bn(Hc=2%). 코드 인식 98bn → EAD 2bn. 정답 Pa = 98 × (2-0.25)/(5-0.25) = 36.1bn → EAD 63.9bn. RWA ~62bn 과소.

### 3. `risk_lib/capital_simulation.py:217~219`, AT1 트리거 시 Tier1 자기소각
- 라인 218에서 `conversion`을 CET1에 더하고, 219에서 `tier1 = cet1 + (tier1 - cet1 - conversion)`. 대수적으로 `tier1_old - conversion`. AT1→CET1 전환은 Tier1 불변이어야 함(AT1 -X, CET1 +X). 코드는 Tier1 -X. `total`도 미조정.
- 실패 시나리오: CET1=6, AT1=1, RWA=100, 트리거 conversion=0.3 → 보고 Tier1=6.7(6.70%), 정답 7.0(7.00%). 트리거 이벤트마다 최대 30bp Tier1 과소, 버퍼 breach 오판.

## MEDIUM

### 4. `risk_lib/capital/rwa_deep.py:262~289` (`FIRB_LGD`, `firb_simulation`)
- Corporate senior-unsecured LGD 45% 고정. Basel III finalisation(CRE32.11, 2023 발효, KR 적용)은 비금융 corp senior-unsecured 40%로 하향. Bank/sovereign은 45%. 또한 FIRB는 retail 미적용인데 `retail_other`/`retail_revolving` 45%로 등록.
- 실패 시나리오: FIRB vs AIRB 시뮬레이션이 FIRB corp RWA를 ~11% 과대(0.45/0.40 - 1).

### 5. `risk_lib/capital/op_risk.py:54~67`, ILM 기본값과 Bucket-1 재량 상충
- `use_ilm=True` + `avg_annual_losses_10y=0.0` → ILM = ln(e-1) ≈ 0.541. OPE25.24 재량은 Bucket-1 은행·10년 손실사 부재 시 ILM=1. 자동 override 없음.
- 실패 시나리오: 콜러 미지정 시 감독 ILM=1 대비 46% 자본 과소(BIC=120bn → ORC 65bn 대신 120bn, RWA_op 812bn vs 1,500bn).

### 6. CLAUDE.md §5 위반 (범위 전체), 182건
- bis_deep 31, pillar3_disclosures 46, ncr 17, rwa_deep 15, liquidity 14, financials 10, ownership 9, bis 8, pillar3 6, capital_simulation 5, frtb 4, 기타 17건. `ncr.py:144`는 DataFrame 값(`"method": [methods.get(k, ",")...]`)에 em dash 삽입 → 리포트로 유출.

## LOW
- `risk_lib/capital/rwa_irb.py:38`, `# 3 bp` 코멘트가 실제 5 bp 상수와 상충. 수치 영향 없음.
- `risk_lib/capital/bis_deep.py:243~267`, `at1_t2_recognition_limits`가 Basel II 유산 캡(AT1≤CET1/3, T2≤Tier1/3) 적용. Basel III(CRE40)에는 없음. 표시 전용.
- `risk_lib/capital/rwa_deep.py:220~231`, LGD downturn "1.06 anchor multiplier" docstring이 CRE32.41 인용, 실제는 CRE32.71(1.06은 SA-CCR alpha). 인용 오류.

## 클린
`capital/bis.py`(수식), `capital/leverage.py`, `capital/leverage_deep.py`, `capital/output_floor.py`, `icaap/economic_capital.py`, `icaap/risk_inventory.py`, `prudential/pca.py`, `prudential/camel.py`, `prudential/ownership.py`, `prudential/liquidity.py`, `prudential/financials.py`, `frtb.py`(공식·backtest zone·multiplier MAR99 일치), `pillar3.py`, `pillar3_disclosures.py`(구조).
