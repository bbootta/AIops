"""정규 리스크 데이터모델 카탈로그 — 부문별 테이블 정의 (DAT-001).

평면 포트폴리오(28컬럼)를 업무 의미 단위로 정규화한다. 각 테이블은 입도가
한 문장으로 서술되며(못 쓰면 설계가 안 된 것), 키·단위·허용값·규정 출처를
스펙에 담아 DDL과 검증이 같은 소스에서 나온다.

라운드별로 부문 테이블이 추가된다 — R1 RDM 코어 · R2 CRM · R3 RWA · …
"""

from __future__ import annotations

from risk_lib.datamodel.spec import ColumnSpec as C, ForeignKey as FK, TableSpec

# ---------------------------------------------------------------- 공통 도메인
ASSET_CLASSES = ("sovereign", "bank", "corporate", "retail_other",
                 "residential_mortgage")
# 도메인은 **실제 원천 데이터에서 확인한 값**이다 — 추정으로 적으면 정상 데이터를
# 위반으로 잡거나(거짓 경보), 반대로 신규 값이 조용히 통과한다.
SECTORS = ("manufacturing", "real_estate", "retail_trade", "construction",
           "financial", "government", "household", "energy", "shipping", "tech")
COUNTRIES = ("KR", "US", "JP", "CN", "VN")
RATINGS = ("AAA-AA", "A", "BBB", "BB", "B", "CCC", "UNRATED")
CCF_TYPES = ("unconditionally_cancellable", "short_term_trade",
             "transaction_related", "commitment_le_1y", "commitment_gt_1y",
             "direct_credit_substitute")
COLLATERAL_TYPES = ("cash", "gold", "sovereign_aaa_le1y", "sovereign_aaa_gt1y",
                    "corporate_bond_ig", "equity_main_index", "real_estate")
SOURCE_SYSTEMS = ("core_banking", "loan_origination", "collateral_mgmt",
                  "general_ledger", "market_data", "synthetic")

# ---------------------------------------------------------------- R1 · RDM 코어

OBLIGOR = TableSpec(
    name="rdm_obligor", korean="차주 원장", product="PRD-RDM",
    grain="차주(그룹 차주 코드) 1명당 1행",
    columns=(
        C("obligor_id", "string", "차주 식별자", nullable=False,
          citation="BCBS 239 원칙3 — 단일 식별체계"),
        C("asset_class", "string", "자산군", nullable=False,
          allowed=ASSET_CLASSES, citation="Basel III CRE20 자산군 분류"),
        C("sector", "string", "업종", nullable=False, allowed=SECTORS),
        C("country", "string", "소재국", nullable=False, allowed=COUNTRIES,
          citation="ISO 3166-1 alpha-2"),
        C("group_id", "string", "그룹 차주 코드", nullable=True,
          note="동일차주 한도는 그룹 단위로 집계 — 미매핑 시 한도 과소산정"),
    ),
    primary_key=("obligor_id",),
    note="한도·집중도 집계의 기준 단위. 개별 차주 코드만 있으면 그룹 매핑이 필요하다.",
)

EXPOSURE = TableSpec(
    name="rdm_exposure", korean="익스포저 원장", product="PRD-RDM",
    grain="익스포저(계좌/약정) 1건당 1행",
    columns=(
        C("exposure_id", "string", "익스포저 식별자", nullable=False),
        C("obligor_id", "string", "차주 식별자", nullable=False),
        C("asset_class", "string", "자산군", nullable=False, allowed=ASSET_CLASSES),
        C("balance", "float", "잔액", nullable=False, unit="KRW", min_value=0.0),
        C("drawn", "float", "인출액", nullable=True, unit="KRW", min_value=0.0),
        C("undrawn", "float", "미인출 약정", nullable=True, unit="KRW",
          min_value=0.0),
        C("ccf_type", "string", "신용환산 구분", nullable=True, allowed=CCF_TYPES,
          citation="Basel III CRE20.94 CCF"),
        C("ead", "float", "익스포저(EAD)", nullable=False, unit="KRW",
          min_value=0.0, citation="CRE20 · CR-F001 EAD = 인출 + CCF×미인출"),
        C("maturity", "float", "잔존만기", nullable=False, unit="years",
          min_value=0.0, max_value=50.0,
          citation="CRE32 만기 조정 (1~5년 캡)"),
        C("ltv", "float", "담보인정비율", nullable=True, unit="ratio",
          min_value=0.0, max_value=5.0,
          citation="CRE20.82 주택담보 LTV 구간"),
        C("rating", "string", "외부등급", nullable=True, allowed=RATINGS,
          citation="CRE20.4 ECRA — 외부등급 기반 위험가중치",
          note="외부등급 미보유 시 UNRATED — SA 위험가중치에 직결"),
    ),
    primary_key=("exposure_id",),
    foreign_keys=(FK(("obligor_id",), "rdm_obligor", ("obligor_id",)),),
    note="EAD는 CRM 적용 전 총액. CRM 조정 후 값은 rwa_crm_allocation 참조.",
)

COLLATERAL = TableSpec(
    name="rdm_collateral", korean="담보 원장", product="PRD-RDM",
    grain="담보물 1건당 1행 (익스포저와 N:1)",
    columns=(
        C("collateral_id", "string", "담보 식별자", nullable=False),
        C("exposure_id", "string", "익스포저 식별자", nullable=False),
        C("collateral_type", "string", "담보 종류", nullable=False,
          allowed=COLLATERAL_TYPES, citation="CRE22.49 감독 haircut 표"),
        C("market_value", "float", "시가", nullable=False, unit="KRW",
          min_value=0.0),
        C("haircut", "float", "감독 haircut", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0, citation="CRE22.49"),
        C("seniority", "int", "배분 우선순위", nullable=False, min_value=1,
          note="복수 익스포저에 배분 시 순위 — 초과배분 방지의 기준"),
    ),
    primary_key=("collateral_id",),
    foreign_keys=(FK(("exposure_id",), "rdm_exposure", ("exposure_id",)),),
)

DELINQUENCY = TableSpec(
    name="rdm_delinquency", korean="연체·건전성 스냅샷", product="PRD-RDM",
    grain="익스포저 × 기준일 1행",
    columns=(
        C("exposure_id", "string", "익스포저 식별자", nullable=False),
        C("asof", "date", "기준일", nullable=False,
          citation="DAT-002 기준일·유효기간"),
        C("dpd", "int", "연체일수", nullable=False, unit="days", min_value=0,
          max_value=3650),
        C("past_due", "bool", "연체 여부", nullable=False),
        C("default_flag", "int", "부도 여부", nullable=False,
          min_value=0, max_value=1,
          citation="CRE36.69 — 90일 이상 연체 또는 상환불능"),
    ),
    primary_key=("exposure_id", "asof"),
    foreign_keys=(FK(("exposure_id",), "rdm_exposure", ("exposure_id",)),),
    note="부도 정의(>=90 DPD)를 바꾸면 PD·ECL·RWA가 모두 달라진다 — 정의 변경은 영향평가 대상.",
)

SNAPSHOT = TableSpec(
    name="rdm_snapshot", korean="스냅샷 원장", product="PRD-RDM",
    grain="원천 스냅샷 1건당 1행",
    columns=(
        C("snapshot_id", "string", "스냅샷 식별자", nullable=False),
        C("source_system", "string", "원천 시스템", nullable=False,
          allowed=SOURCE_SYSTEMS),
        C("table_name", "string", "대상 테이블", nullable=False),
        C("asof", "date", "기준일", nullable=False),
        C("row_count", "int", "행 수", nullable=False, min_value=0),
        C("fingerprint", "text", "SHA-256 지문", nullable=False,
          citation="DAT-004 · A.7.2 데이터 출처"),
    ),
    primary_key=("snapshot_id",),
    note="지문이 바뀌면 그 위의 모든 산출값이 달라진다 — 재현의 기준점.",
)

DQ_RESULT = TableSpec(
    name="rdm_dq_result", korean="데이터품질 검증 결과", product="PRD-RDM",
    grain="검증 규칙 × 테이블 × 기준일 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("table_name", "string", "대상 테이블", nullable=False),
        C("column_name", "string", "대상 컬럼", nullable=True),
        C("rule", "string", "규칙", nullable=False),
        C("severity", "string", "심각도", nullable=False,
          allowed=("FAIL", "WARN")),
        C("n_rows", "int", "위반 행 수", nullable=False, min_value=0),
        C("detail", "text", "상세", nullable=True),
    ),
    note="DQ 결과를 저장하지 않으면 '그때는 통과했다'를 증명할 수 없다 (RDM-004).",
)

RDM_TABLES: tuple[TableSpec, ...] = (
    OBLIGOR, EXPOSURE, COLLATERAL, DELINQUENCY, SNAPSHOT, DQ_RESULT)

# 라운드가 진행되며 부문 테이블이 추가된다.
ALL_TABLES: tuple[TableSpec, ...] = RDM_TABLES


def by_name(name: str) -> TableSpec:
    for t in ALL_TABLES:
        if t.name == name:
            return t
    raise KeyError(f"미등록 테이블: {name}")


def by_product(product: str) -> list[TableSpec]:
    return [t for t in ALL_TABLES if t.product == product]


# ---------------------------------------------------------------- R2 · CRM
APPROACHES = ("SA", "FIRB", "AIRB")
MODEL_STATUS = ("DEV", "UAT", "PROD", "RETIRED")
GRADES = tuple(f"{p}{s}" for p in ("AAA", "AA", "A", "BBB", "BB", "B", "CCC")
               for s in ("+", "", "-"))[:17] + ("D",)

MODEL_INVENTORY = TableSpec(
    name="crm_model", korean="모형 인벤토리", product="PRD-CRM",
    grain="모형 1개당 1행",
    columns=(
        C("model_id", "string", "모형 식별자", nullable=False),
        C("model_name", "text", "모형명", nullable=False),
        C("segment", "string", "적용 세그먼트", nullable=False,
          allowed=ASSET_CLASSES),
        C("tier", "int", "모형 등급", nullable=False, min_value=1, max_value=3,
          citation="SR 11-7 모형 중요도 등급"),
        C("status", "string", "운영 상태", nullable=False, allowed=MODEL_STATUS),
        C("last_validation", "date", "최근 검증일", nullable=True),
        C("next_due", "date", "차기 검증 기한", nullable=True),
        C("owner", "text", "모형 소유부서", nullable=False),
    ),
    primary_key=("model_id",),
    note="검증 기한 경과(overdue) 모형의 산출값은 사용 전 재검증 대상.",
)

RATING_HISTORY = TableSpec(
    name="crm_rating", korean="등급·PD 이력", product="PRD-CRM",
    grain="차주 × 기준일 1행",
    columns=(
        C("obligor_id", "string", "차주 식별자", nullable=False),
        C("asof", "date", "기준일", nullable=False),
        C("model_id", "string", "산출 모형", nullable=False),
        C("pd", "float", "부도확률", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0,
          citation="CRE32.5 PD 하한 5bp (BCBS d424)"),
        C("grade", "string", "내부등급", nullable=False,
          citation="Master scale 17등급"),
        C("override_flag", "int", "Override 여부", nullable=False,
          min_value=0, max_value=1,
          note="Override는 승인 원장과 대사돼야 한다 (BNK-CRM-009)"),
    ),
    primary_key=("obligor_id", "asof"),
    foreign_keys=(FK(("obligor_id",), "rdm_obligor", ("obligor_id",)),
                  FK(("model_id",), "crm_model", ("model_id",))),
)

MODEL_PERFORMANCE = TableSpec(
    name="crm_performance", korean="모형 성능 지표", product="PRD-CRM",
    grain="모형 × 세그먼트 × 기준일 1행",
    columns=(
        C("model_id", "string", "모형 식별자", nullable=False),
        C("segment", "string", "세그먼트", nullable=False),
        C("asof", "date", "기준일", nullable=False),
        C("gini", "float", "변별력 (Gini)", nullable=False, unit="ratio",
          min_value=-1.0, max_value=1.0, citation="BCBS WP14 변별력"),
        C("ks", "float", "KS 통계량", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("psi", "float", "안정성 (PSI)", nullable=True, unit="ratio",
          min_value=0.0, citation="PSI<0.10 안정 · 0.25 초과 불안정"),
        C("n_obs", "int", "관측 수", nullable=False, min_value=0),
    ),
    primary_key=("model_id", "segment", "asof"),
    foreign_keys=(FK(("model_id",), "crm_model", ("model_id",)),),
)

CRM_TABLES = (MODEL_INVENTORY, RATING_HISTORY, MODEL_PERFORMANCE)

# ---------------------------------------------------------------- R3 · RWA

RWA_RESULT = TableSpec(
    name="rwa_result", korean="RWA 산출 결과", product="PRD-RWA",
    grain="익스포저 × 기준일 1행",
    columns=(
        C("exposure_id", "string", "익스포저 식별자", nullable=False),
        C("asof", "date", "기준일", nullable=False),
        C("approach", "string", "산출 방법", nullable=False, allowed=APPROACHES,
          citation="CRE20(SA) · CRE31~32(IRB)"),
        C("ead_final", "float", "CRM 후 EAD", nullable=False, unit="KRW",
          min_value=0.0),
        C("pd", "float", "PD", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("lgd", "float", "LGD", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0, citation="CRE32.42 LGD 하한"),
        C("risk_weight", "float", "위험가중치", nullable=False, unit="ratio",
          min_value=0.0, max_value=15.0),
        C("rwa", "float", "위험가중자산", nullable=False, unit="KRW",
          min_value=0.0),
        C("expected_loss", "float", "기대손실(EL)", nullable=True, unit="KRW",
          min_value=0.0, citation="CRE31 EL = PD×LGD×EAD"),
    ),
    primary_key=("exposure_id", "asof"),
    foreign_keys=(FK(("exposure_id",), "rdm_exposure", ("exposure_id",)),),
    note="동일 exposure_id가 SA·IRB에 중복 산출되면 이중계상 — PK가 이를 막는다.",
)

CRM_ALLOCATION = TableSpec(
    name="rwa_crm_allocation", korean="신용위험경감 배분", product="PRD-RWA",
    grain="익스포저 × 담보 1행",
    columns=(
        C("exposure_id", "string", "익스포저 식별자", nullable=False),
        C("collateral_id", "string", "담보 식별자", nullable=False),
        C("asof", "date", "기준일", nullable=False),
        C("eligible_value", "float", "적격 담보가치", nullable=False, unit="KRW",
          min_value=0.0, citation="CRE22.49 haircut 적용 후"),
        C("allocated", "float", "배분액", nullable=False, unit="KRW",
          min_value=0.0, citation="CR-F008 초과배분 금지"),
        C("secured_ead", "float", "담보부 EAD", nullable=False, unit="KRW",
          min_value=0.0),
        C("unsecured_ead", "float", "무담보부 EAD", nullable=False, unit="KRW",
          min_value=0.0),
    ),
    primary_key=("exposure_id", "collateral_id", "asof"),
    foreign_keys=(FK(("exposure_id",), "rdm_exposure", ("exposure_id",)),
                  FK(("collateral_id",), "rdm_collateral", ("collateral_id",))),
    note="CR-F013: 담보배분은 PD를 바꾸지 않는다. LGD·EAD 경로 중복효과 금지(CR-F016).",
)

RWA_TABLES = (RWA_RESULT, CRM_ALLOCATION)

# ---------------------------------------------------------------- R4 · ECL

STAGES = (1, 2, 3)
SICR_TRIGGERS = ("none", "dpd30", "watchlist", "pd_ratio", "ext_rating",
                 "forbearance", "abs_pd")

ECL_RESULT = TableSpec(
    name="ecl_result", korean="IFRS9 ECL 산출", product="PRD-ECL",
    grain="익스포저 × 기준일 1행",
    columns=(
        C("exposure_id", "string", "익스포저 식별자", nullable=False),
        C("asof", "date", "기준일", nullable=False),
        C("stage", "int", "Stage", nullable=False, min_value=1, max_value=3,
          citation="IFRS 9 5.5.3(12M) · 5.5.5(lifetime) · 5.5.11"),
        C("sicr_trigger", "string", "SICR 트리거", nullable=False,
          allowed=SICR_TRIGGERS),
        C("pd_pit", "float", "PIT PD", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0,
          citation="B5.5.42 — TTC가 아닌 PIT를 쓴다"),
        C("lgd", "float", "LGD", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("ead", "float", "EAD", nullable=False, unit="KRW", min_value=0.0),
        C("ecl", "float", "기대신용손실", nullable=False, unit="KRW",
          min_value=0.0),
        C("coverage_ratio", "float", "커버리지", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0,
          note="Stage 1≤2≤3 단조 — 비단조는 스테이징 오류 신호"),
    ),
    primary_key=("exposure_id", "asof"),
    foreign_keys=(FK(("exposure_id",), "rdm_exposure", ("exposure_id",)),),
)

MACRO_SCENARIO = TableSpec(
    name="ecl_macro_scenario", korean="거시 시나리오", product="PRD-ECL",
    grain="시나리오 × 분기 1행",
    columns=(
        C("scenario", "string", "시나리오", nullable=False),
        C("quarter", "string", "분기", nullable=False),
        C("weight", "float", "확률가중치", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0,
          citation="IFRS 9 B5.5.42 다중 시나리오 확률가중"),
        C("gdp_growth", "float", "GDP 성장률", nullable=False, unit="ratio",
          min_value=-0.5, max_value=0.5),
        C("unemployment", "float", "실업률", nullable=True, unit="ratio",
          min_value=0.0, max_value=0.5),
        C("pd_multiplier", "float", "PD 배수", nullable=False, unit="ratio",
          min_value=0.0, citation="ST-F002 위성모형 대용치"),
    ),
    primary_key=("scenario", "quarter"),
    note="시나리오 가중치 합은 1이어야 한다 — 아니면 확률가중 ECL이 편향된다.",
)

ECL_TABLES = (ECL_RESULT, MACRO_SCENARIO)

# 누적 등록
ALL_TABLES = RDM_TABLES + CRM_TABLES + RWA_TABLES + ECL_TABLES


# ---------------------------------------------------------------- R5 · ST/CAP
SCENARIOS = ("baseline", "adverse", "severely_adverse")
CAPITAL_TIERS = ("CET1", "AT1", "T2")

STRESS_PATH = TableSpec(
    name="st_capital_path", korean="스트레스 자본경로", product="PRD-ST",
    grain="시나리오 × 분기 1행",
    columns=(
        C("scenario", "string", "시나리오", nullable=False, allowed=SCENARIOS),
        C("quarter", "string", "분기", nullable=False),
        C("severity", "float", "충격 심도", nullable=False, unit="ratio",
          min_value=0.0, citation="ST-F001 정점→감쇠 경로"),
        C("rwa_total", "float", "총 RWA", nullable=False, unit="KRW",
          min_value=0.0),
        C("ecl", "float", "ECL", nullable=False, unit="KRW", min_value=0.0),
        C("cet1_ratio", "float", "CET1 비율", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0, citation="ST-F004 CET1 roll-forward"),
        C("tier1_ratio", "float", "Tier1 비율", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("total_ratio", "float", "총자본 비율", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("binding", "string", "제약 비율", nullable=False,
          allowed=("cet1", "tier1", "total"),
          note="ST-F006 — 침범 시 어느 요구치인지 반드시 명시"),
        C("passes", "bool", "요구치 충족", nullable=False),
    ),
    primary_key=("scenario", "quarter"),
)

CAPITAL_STACK = TableSpec(
    name="cap_stack", korean="자본 스택", product="PRD-CAP",
    grain="자본 계층 × 기준일 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("tier", "string", "자본 계층", nullable=False, allowed=CAPITAL_TIERS),
        C("amount", "float", "금액", nullable=False, unit="KRW", min_value=0.0),
        C("ratio", "float", "비율", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("required", "float", "요구 비율", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0, citation="CRE10.4 + 버퍼"),
        C("surplus", "float", "잉여/부족", nullable=False, unit="ratio",
          citation="음수는 자본 부족 — 부호가 곧 판정"),
    ),
    primary_key=("asof", "tier"),
)

ST_TABLES = (STRESS_PATH, CAPITAL_STACK)

# ---------------------------------------------------------------- R6 · ALM
ALM_METRICS = ("LCR", "NSFR", "IRRBB_EVE", "IRRBB_NII")
IRRBB_SCENARIOS = ("parallel_up", "parallel_down", "steepener", "flattener",
                   "short_up", "short_down")

ALM_RESULT = TableSpec(
    name="alm_result", korean="ALM 지표 산출", product="PRD-ALM",
    grain="지표 × 기준일 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("metric", "string", "지표", nullable=False, allowed=ALM_METRICS),
        C("value", "float", "실측치", nullable=False, unit="ratio"),
        C("minimum", "float", "규제 최저", nullable=True, unit="ratio",
          citation="LCR20.1 / NSF20.1 각 100%"),
        C("numerator", "float", "분자", nullable=False, unit="KRW"),
        C("denominator", "float", "분모", nullable=False, unit="KRW",
          min_value=0.0, note="분모 0이면 비율 자체가 정의되지 않는다"),
        C("passes", "bool", "기준 충족", nullable=True),
    ),
    primary_key=("asof", "metric"),
)

IRRBB_SHOCK = TableSpec(
    name="alm_irrbb_shock", korean="IRRBB 충격 시나리오", product="PRD-ALM",
    grain="충격 시나리오 × 기준일 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("scenario", "string", "충격 시나리오", nullable=False,
          allowed=IRRBB_SCENARIOS, citation="SRP31.90 표준 6개 시나리오"),
        C("delta_eve", "float", "ΔEVE", nullable=False, unit="KRW"),
        C("pct_tier1", "float", "Tier1 대비", nullable=False, unit="ratio",
          citation="SRP31.92 outlier test — 15% 초과 시 이상치"),
    ),
    primary_key=("asof", "scenario"),
)

ALM_TABLES = (ALM_RESULT, IRRBB_SHOCK)

# ---------------------------------------------------------------- R7 · MKT/NCR
TRADE_KINDS = ("option", "swap", "cds")
PRICE_SOURCES = ("consensus", "exchange", "broker", "model", "front_office")

TRADE = TableSpec(
    name="mkt_trade", korean="트레이딩북 포지션", product="PRD-MKT",
    grain="거래 1건당 1행",
    columns=(
        C("trade_id", "string", "거래 식별자", nullable=False),
        C("counterparty", "string", "거래상대방", nullable=False),
        C("kind", "string", "상품 유형", nullable=False, allowed=TRADE_KINDS),
        C("notional", "float", "명목금액", nullable=False, unit="KRW",
          min_value=0.0),
        C("maturity", "float", "잔존만기", nullable=False, unit="years",
          min_value=0.0, max_value=50.0),
        C("fo_value", "float", "FO 평가액", nullable=False, unit="KRW"),
        C("delta", "float", "Δ", nullable=True, unit="KRW"),
        C("vega", "float", "Vega", nullable=True, unit="KRW"),
        C("dv01", "float", "dV01", nullable=True, unit="KRW",
          citation="1bp 평행이동 민감도"),
        C("cs01", "float", "CS01", nullable=True, unit="KRW"),
    ),
    primary_key=("trade_id",),
)

PRICE_VERIFICATION = TableSpec(
    name="mkt_ipv", korean="독립가격검증 결과", product="PRD-MKT",
    grain="거래 × 기준일 1행",
    columns=(
        C("trade_id", "string", "거래 식별자", nullable=False),
        C("asof", "date", "기준일", nullable=False),
        C("source", "string", "독립 소스", nullable=False, allowed=PRICE_SOURCES),
        C("fo_value", "float", "FO 평가액", nullable=False, unit="KRW"),
        C("benchmark_value", "float", "독립 평가액", nullable=False, unit="KRW"),
        C("diff", "float", "차이", nullable=False, unit="KRW"),
        C("limit", "float", "허용 한도", nullable=False, unit="KRW",
          min_value=0.0, citation="MR-F003 max(절대, |기준가|×상대)"),
        C("verified", "bool", "독립검증 여부", nullable=False,
          note="FO 자체 가격은 검증으로 인정하지 않는다"),
        C("is_break", "bool", "BREAK 여부", nullable=False),
        C("days_open", "int", "미해소 일수", nullable=False, min_value=0),
    ),
    primary_key=("trade_id", "asof"),
    foreign_keys=(FK(("trade_id",), "mkt_trade", ("trade_id",)),),
)

NCR_COMPONENT = TableSpec(
    name="ncr_component", korean="순자본비율 구성요소", product="PRD-NCR",
    grain="구성요소 × 기준일 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("component", "string", "구성요소", nullable=False),
        C("category", "string", "분류", nullable=False,
          allowed=("영업용순자본", "총위험액", "필요유지자기자본")),
        C("amount", "float", "금액", nullable=False, unit="KRW"),
        C("citation", "text", "근거 조항", nullable=True,
          citation="금융투자업규정 제3-6·11·21조"),
    ),
    primary_key=("asof", "component"),
)

MKT_TABLES = (TRADE, PRICE_VERIFICATION, NCR_COMPONENT)

ALL_TABLES = (RDM_TABLES + CRM_TABLES + RWA_TABLES + ECL_TABLES
              + ST_TABLES + ALM_TABLES + MKT_TABLES)


# ---------------------------------------------------------------- R8 · OPR
OP_EVENT_TYPES = ("internal_fraud", "external_fraud", "employment",
                  "clients_products", "physical_assets", "business_disruption",
                  "execution_delivery")

OP_LOSS_EVENT = TableSpec(
    name="opr_loss_event", korean="운영손실 사건", product="PRD-OPR",
    grain="손실사건 1건당 1행",
    columns=(
        C("event_id", "string", "사건 식별자", nullable=False),
        C("event_date", "date", "발생일", nullable=False),
        C("event_type", "string", "사건 유형", nullable=False,
          allowed=OP_EVENT_TYPES, citation="Basel III OPE25 7개 사건유형"),
        C("gross_loss", "float", "총손실", nullable=False, unit="KRW",
          min_value=0.0),
        C("recovery", "float", "회수액", nullable=False, unit="KRW",
          min_value=0.0, note="총손실 초과 불가 — 초과 시 순손실이 음수가 된다"),
        C("net_loss", "float", "순손실", nullable=False, unit="KRW",
          min_value=0.0, citation="OR-F001 max(0, 총손실 − 회수)"),
    ),
    primary_key=("event_id",),
)

OP_CAPITAL = TableSpec(
    name="opr_capital", korean="운영리스크 자본", product="PRD-OPR",
    grain="산출 방법 × 기준일 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("method", "string", "산출 방법", nullable=False,
          allowed=("SMA", "LDA"), citation="OPE25 신표준방법 / 내부 LDA"),
        C("capital", "float", "자본요구액", nullable=False, unit="KRW",
          min_value=0.0),
        C("rwa", "float", "RWA", nullable=False, unit="KRW", min_value=0.0,
          citation="RWA = 12.5 × 자본요구액 (CRE20.1)"),
        C("var_999", "float", "99.9% VaR", nullable=True, unit="KRW",
          min_value=0.0),
    ),
    primary_key=("asof", "method"),
)

OPR_TABLES = (OP_LOSS_EVENT, OP_CAPITAL)

# ---------------------------------------------------------------- R9 · AIG/VAL
VALIDATION_STATUS = ("PASS", "WARN", "FAIL")
ADJ_STATUS = ("pending", "applied", "rejected", "expired")

VALIDATION_RESULT = TableSpec(
    name="val_check", korean="자체검증 결과", product="PRD-VAL",
    grain="검증 체크 × 기준일 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("check_name", "string", "체크명", nullable=False),
        C("status", "string", "판정", nullable=False, allowed=VALIDATION_STATUS),
        C("detail", "text", "상세", nullable=True),
        C("domain", "string", "부문", nullable=True),
    ),
    primary_key=("asof", "check_name"),
    note="FAIL 1건이라도 있으면 결재 불가 (AIMS_POLICY §2-4).",
)

AUDIT_LEDGER = TableSpec(
    name="val_audit_ledger", korean="산출 근거 원장", product="PRD-VAL",
    grain="공표 수치 1건당 1행",
    columns=(
        C("figure_id", "string", "수치 식별자", nullable=False),
        C("label", "text", "수치명", nullable=False),
        C("value", "float", "값", nullable=True, unit="mixed",
          note="비율·금액·등급이 섞이므로 단위는 unit 컬럼이 아니라 label로 판별"),
        C("code_module", "text", "산출 모듈", nullable=False),
        C("code_function", "text", "산출 함수", nullable=False),
        C("citation", "text", "규정 근거", nullable=False,
          citation="BCBS 239 — 수치마다 근거가 있어야 한다"),
    ),
    primary_key=("figure_id",),
)

ADJUSTMENT = TableSpec(
    name="aig_adjustment", korean="수동조정 원장", product="PRD-AIG",
    grain="조정 1건당 1행",
    columns=(
        C("adjustment_id", "string", "조정 식별자", nullable=False),
        C("figure_id", "string", "대상 수치", nullable=False),
        C("base_value", "float", "조정 전", nullable=False, unit="mixed"),
        C("adjusted_value", "float", "조정 후", nullable=False, unit="mixed"),
        C("delta", "float", "증감", nullable=False, unit="mixed"),
        C("requester", "text", "요청자", nullable=False),
        C("approver", "text", "승인자", nullable=False,
          note="요청자와 같으면 직무분리 위반 — 적용 불가"),
        C("senior_approval", "text", "상위 승인자", nullable=True),
        C("status", "string", "상태", nullable=False, allowed=ADJ_STATUS),
        C("expires_on", "date", "유효기간", nullable=False),
        C("evidence_ref", "text", "증빙 참조", nullable=False),
    ),
    primary_key=("adjustment_id",),
)

VAL_TABLES = (VALIDATION_RESULT, AUDIT_LEDGER, ADJUSTMENT)

ALL_TABLES = (RDM_TABLES + CRM_TABLES + RWA_TABLES + ECL_TABLES
              + ST_TABLES + ALM_TABLES + MKT_TABLES + OPR_TABLES + VAL_TABLES)
