"""정규 리스크 데이터모델 카탈로그 — 부문별 테이블 정의 (DAT-001).

평면 포트폴리오(28컬럼)를 업무 의미 단위로 정규화한다. 각 테이블은 입도가
한 문장으로 서술되며(못 쓰면 설계가 안 된 것), 키·단위·허용값·규정 출처를
스펙에 담아 DDL과 검증이 같은 소스에서 나온다.

라운드별로 부문 테이블이 추가된다 — R1 RDM 코어 · R2 CRM · R3 RWA · …
"""

from __future__ import annotations

from risk_lib.datamodel.spec import ColumnSpec as C, ForeignKey as FK, TableSpec
from risk_lib.models.rating import DEFAULT_MASTER_SCALE as _MASTER_SCALE

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
# 등급 도메인은 **실제 master scale**에서 가져온다. 문자열 조합을 잘라 쓰면
# 쓰이지 않는 등급(AAA+/AAA-)이 들어가고 실제로 나오는 등급(B-/CCC+)이 빠져
# 정상 산출이 도메인 위반으로 잡힌다.
GRADES = tuple(g.grade for g in _MASTER_SCALE) + ("D",)

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


# ================================================================ R11 · 세분화
# 「테이블이 너무 단순하다」는 지적에 대한 대응. R1~R9는 부문마다 결과 1~3장을
# 두는 수준이었다 — 그 입도로는 (a) 금감원 업무보고서 라인 항목을 채울 수 없고,
# (b) 에이전틱 UI가 관리할 대상(View·권한·에이전트·변경)이 데이터로 존재하지
# 않는다. 아래 섹션은 실제 요건(감독규정 라인 · Basel 산출 분해 · RYNTA BRD
# 플랫폼 요건)을 기준으로 기존 테이블을 쪼개고 누락된 원장을 신설한다.

# ---------------------------------------------------------------- R11-A · RDM
ASSET_QUALITY = ("정상", "요주의", "고정", "회수의문", "추정손실")
PROTECTION_TYPES = ("guarantee", "credit_derivative")
INTERFACE_STATUS = ("PASS", "WARN", "FAIL")
MAP_STATUS = ("mapped", "unmapped", "deprecated")
DQ_RULE_TYPES = ("not_null", "range", "allowed", "unique", "referential",
                 "reconciliation", "timeliness")

OBLIGOR_FINANCIAL = TableSpec(
    name="rdm_obligor_financial", korean="차주 재무·행동정보", product="PRD-RDM",
    grain="차주 × 기준일 1행",
    columns=(
        C("obligor_id", "string", "차주 식별자", nullable=False),
        C("asof", "date", "기준일", nullable=False),
        C("segment", "string", "모형 세그먼트", nullable=False,
          allowed=ASSET_CLASSES),
        C("leverage", "float", "부채비율", nullable=True, unit="ratio",
          min_value=0.0, max_value=50.0, note="기업 세그먼트 PD 모형 투입변수"),
        C("current_ratio", "float", "유동비율", nullable=True, unit="ratio",
          min_value=0.0, max_value=50.0),
        C("log_assets", "float", "자산규모(로그)", nullable=True, unit="log_KRW"),
        C("interest_coverage", "float", "이자보상배율", nullable=True,
          unit="ratio", min_value=-100.0, max_value=1000.0),
        C("dti", "float", "총부채원리금상환비율", nullable=True, unit="ratio",
          min_value=0.0, max_value=10.0),
        C("utilization", "float", "한도소진율", nullable=True, unit="ratio",
          min_value=0.0, max_value=2.0),
        C("income_log", "float", "소득(로그)", nullable=True, unit="log_KRW"),
        C("months_employed", "float", "재직개월", nullable=True, unit="months",
          min_value=0.0, max_value=720.0),
        C("credit_score", "float", "신용점수", nullable=True, unit="score",
          min_value=0.0, max_value=1200.0),
    ),
    primary_key=("obligor_id", "asof"),
    foreign_keys=(FK(("obligor_id",), "rdm_obligor", ("obligor_id",)),),
    note="PD 모형 투입변수를 차주 원장에서 분리한다 — 원장은 정적 속성, 재무는 시점 속성.",
)

EXPOSURE_BALANCE = TableSpec(
    name="rdm_exposure_balance", korean="익스포저 잔액 스냅샷", product="PRD-RDM",
    grain="익스포저 × 기준일 1행",
    columns=(
        C("exposure_id", "string", "익스포저 식별자", nullable=False),
        C("asof", "date", "기준일", nullable=False),
        C("balance", "float", "장부잔액", nullable=False, unit="KRW",
          min_value=0.0),
        C("drawn", "float", "인출액", nullable=False, unit="KRW", min_value=0.0),
        C("undrawn", "float", "미인출 약정", nullable=False, unit="KRW",
          min_value=0.0),
        C("ccf", "float", "적용 신용환산율", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0, citation="CRE20.94 CCF 표"),
        C("ead", "float", "EAD", nullable=False, unit="KRW", min_value=0.0,
          citation="CR-F001 EAD = 인출 + CCF × 미인출"),
        C("currency", "string", "통화", nullable=False, allowed=("KRW",),
          note="다통화 확장 시 환산일·환율 원장이 함께 필요하다"),
    ),
    primary_key=("exposure_id", "asof"),
    foreign_keys=(FK(("exposure_id",), "rdm_exposure", ("exposure_id",)),),
    note="계약 정적속성(rdm_exposure)과 시점 잔액을 분리해야 시계열 비교가 성립한다.",
)

ASSET_QUALITY_TABLE = TableSpec(
    name="rdm_asset_quality", korean="자산건전성 분류", product="PRD-RDM",
    grain="익스포저 × 기준일 1행",
    columns=(
        C("exposure_id", "string", "익스포저 식별자", nullable=False),
        C("asof", "date", "기준일", nullable=False),
        C("classification", "string", "건전성 분류", nullable=False,
          allowed=ASSET_QUALITY,
          citation="은행업감독규정 제27조 — 5단계 자산건전성 분류"),
        C("borrower_type", "string", "여신 구분", nullable=False,
          allowed=("기업여신", "가계여신"),
          note="최저적립률이 구분별로 다르다 — 잘못 분류하면 충당금이 과소적립된다"),
        C("dpd", "int", "연체일수", nullable=False, unit="days", min_value=0),
        C("balance", "float", "잔액", nullable=False, unit="KRW", min_value=0.0),
        C("min_provision_rate", "float", "최저적립률", nullable=False,
          unit="ratio", min_value=0.0, max_value=1.0,
          citation="은행업감독규정 제29조 제1항 대손충당금 최저적립률"),
        C("min_provision", "float", "최저적립액", nullable=False, unit="KRW",
          min_value=0.0),
        C("ifrs9_provision", "float", "IFRS9 충당금", nullable=False, unit="KRW",
          min_value=0.0),
        C("reserve_shortfall", "float", "대손준비금 소요액", nullable=False,
          unit="KRW", min_value=0.0,
          citation="은행업감독규정 제29조 제2항 — max(0, 최저적립액 − IFRS9 충당금)"),
    ),
    primary_key=("exposure_id", "asof"),
    foreign_keys=(FK(("exposure_id",), "rdm_exposure", ("exposure_id",)),),
    note="업무보고서 「자산건전성 분류 및 대손충당금」의 원천. 분류 규칙은 "
         "연체일수 대용 규칙이며 실제 규정은 채무상환능력 평가를 함께 요구한다.",
)

GUARANTEE = TableSpec(
    name="rdm_guarantee", korean="보증·신용보장 원장", product="PRD-RDM",
    grain="보장계약 1건당 1행",
    columns=(
        C("guarantee_id", "string", "보장 식별자", nullable=False),
        C("exposure_id", "string", "익스포저 식별자", nullable=False),
        C("guarantor_id", "string", "보장제공자", nullable=False),
        C("protection_type", "string", "보장 형태", nullable=False,
          allowed=PROTECTION_TYPES, citation="CRE22.70 unfunded protection"),
        C("guarantor_rating", "string", "보장제공자 등급", nullable=False,
          allowed=RATINGS,
          note="대체법(substitution)은 보장제공자 위험가중치를 쓴다"),
        C("guaranteed_amount", "float", "보장금액", nullable=False, unit="KRW",
          min_value=0.0),
        C("maturity_mismatch", "bool", "만기 불일치", nullable=False,
          citation="CRE22.85 — 만기 불일치 시 보장효과 축소"),
        C("currency_mismatch", "bool", "통화 불일치", nullable=False,
          citation="CRE22.84 — 8% haircut"),
        C("eligible", "bool", "적격 여부", nullable=False),
    ),
    primary_key=("guarantee_id",),
    foreign_keys=(FK(("exposure_id",), "rdm_exposure", ("exposure_id",)),),
)

SOURCE_CONTRACT = TableSpec(
    name="rdm_source_contract", korean="원천 인터페이스 계약", product="PRD-RDM",
    grain="원천 시스템 × 테이블 × 기준일 1행",
    columns=(
        C("source_system", "string", "원천 시스템", nullable=False,
          allowed=SOURCE_SYSTEMS),
        C("table_name", "string", "대상 테이블", nullable=False),
        C("asof", "date", "기준일", nullable=False),
        C("expected_rows", "int", "계약 건수", nullable=False, min_value=0),
        C("actual_rows", "int", "수신 건수", nullable=False, min_value=0),
        C("expected_sum", "float", "계약 합계", nullable=False, unit="KRW"),
        C("actual_sum", "float", "수신 합계", nullable=False, unit="KRW"),
        C("schema_hash", "text", "스키마 지문", nullable=False),
        C("status", "string", "판정", nullable=False, allowed=INTERFACE_STATUS,
          note="건수·합계·스키마 중 하나라도 어긋나면 하류 산출을 신뢰할 수 없다"),
    ),
    primary_key=("source_system", "table_name", "asof"),
    note="RYNTA Interface Watch의 데이터 근거 — 스키마·건수·합계·시점 4종 계약.",
)

CANONICAL_MAP = TableSpec(
    name="rdm_canonical_map", korean="표준코드 매핑", product="PRD-RDM",
    grain="원천 시스템 × 도메인 × 원천코드 1행",
    columns=(
        C("source_system", "string", "원천 시스템", nullable=False,
          allowed=SOURCE_SYSTEMS),
        C("domain", "string", "코드 도메인", nullable=False),
        C("source_code", "string", "원천 코드", nullable=False),
        C("canonical_code", "string", "표준 코드", nullable=True,
          note="미매핑(NULL)이면 그 상품은 산출에서 조용히 빠진다 — 차단 대상"),
        C("status", "string", "매핑 상태", nullable=False, allowed=MAP_STATUS),
        C("effective_from", "date", "적용 시작일", nullable=False),
    ),
    primary_key=("source_system", "domain", "source_code"),
    note="신상품 코드 미매핑은 RWA·시장리스크 누락으로 직결된다(RDM-003).",
)

RECONCILIATION = TableSpec(
    name="rdm_reconciliation", korean="집계 대사 결과", product="PRD-RDM",
    grain="대사 규칙 × 기준일 1행",
    columns=(
        C("recon_id", "string", "대사 식별자", nullable=False),
        C("asof", "date", "기준일", nullable=False),
        C("axis", "string", "집계축", nullable=False),
        C("source_total", "float", "원천 합계", nullable=False, unit="KRW"),
        C("target_total", "float", "대상 합계", nullable=False, unit="KRW"),
        C("gap", "float", "차이", nullable=False, unit="KRW"),
        C("gap_ratio", "float", "차이 비율", nullable=False, unit="ratio"),
        C("tolerance", "float", "허용 오차", nullable=False, unit="ratio",
          min_value=0.0),
        C("status", "string", "판정", nullable=False, allowed=INTERFACE_STATUS),
        C("downstream", "text", "하위 영향", nullable=True),
    ),
    primary_key=("recon_id", "asof"),
)

DQ_RULE = TableSpec(
    name="rdm_dq_rule", korean="데이터품질 규칙 마스터", product="PRD-RDM",
    grain="검증 규칙 1개당 1행",
    columns=(
        C("rule_id", "string", "규칙 식별자", nullable=False),
        C("table_name", "string", "대상 테이블", nullable=False),
        C("column_name", "string", "대상 컬럼", nullable=True),
        C("rule_type", "string", "규칙 유형", nullable=False,
          allowed=DQ_RULE_TYPES),
        C("severity", "string", "심각도", nullable=False,
          allowed=("FAIL", "WARN")),
        C("expression", "text", "규칙 표현", nullable=False),
        C("citation", "text", "근거", nullable=True),
    ),
    primary_key=("rule_id",),
    note="rdm_dq_result에 규칙 결과만 있고 규칙 정의가 없으면 "
         "'왜 이 규칙인가'를 증명할 수 없다 (BCBS 239 원칙3).",
)

RDM_DETAIL_TABLES = (OBLIGOR_FINANCIAL, EXPOSURE_BALANCE, ASSET_QUALITY_TABLE,
                     GUARANTEE, SOURCE_CONTRACT, CANONICAL_MAP, RECONCILIATION,
                     DQ_RULE)


# ---------------------------------------------------------------- R11-B · CRM
EWS_LEVELS = ("관찰", "주의", "경보")
LGD_COMPONENTS = ("gross_recovery", "direct_cost", "indirect_cost",
                  "discount_effect", "net_lgd")

PD_CALIBRATION = TableSpec(
    name="crm_pd_calibration", korean="PD 등급별 보정 검증", product="PRD-CRM",
    grain="세그먼트 × 등급 × 기준일 1행",
    columns=(
        C("segment", "string", "세그먼트", nullable=False, allowed=ASSET_CLASSES),
        C("grade", "string", "등급", nullable=False, allowed=GRADES),
        C("asof", "date", "기준일", nullable=False),
        C("n_obligors", "int", "차주 수", nullable=False, min_value=0),
        C("pd_predicted", "float", "예측 PD", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("dr_observed", "float", "관측 부도율", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("oe_ratio", "float", "관측/예측 비율", nullable=True, unit="ratio",
          min_value=0.0, citation="CR-F011 보정 O/E — 1 근방이 적정"),
        C("within_tolerance", "bool", "허용범위 내", nullable=False,
          note="등급별 O/E가 벗어나면 등급 재보정 대상"),
    ),
    primary_key=("segment", "grade", "asof"),
    note="모형 전체 Gini만으로는 등급별 과소·과대 추정을 볼 수 없다.",
)

RATING_MIGRATION = TableSpec(
    name="crm_rating_migration", korean="등급 전이행렬", product="PRD-CRM",
    grain="세그먼트 × 시작등급 × 도착등급 × 기준일 1행",
    columns=(
        C("segment", "string", "세그먼트", nullable=False, allowed=ASSET_CLASSES),
        C("asof", "date", "기준일", nullable=False),
        C("from_grade", "string", "시작 등급", nullable=False, allowed=GRADES),
        C("to_grade", "string", "도착 등급", nullable=False, allowed=GRADES),
        C("n_obligors", "int", "차주 수", nullable=False, min_value=0),
        C("share", "float", "전이 비율", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0,
          note="from_grade별 합이 1이어야 한다 — 아니면 관측치 누락"),
    ),
    primary_key=("segment", "asof", "from_grade", "to_grade"),
)

LGD_COMPONENT = TableSpec(
    name="crm_lgd_component", korean="LGD 구성요소 분해", product="PRD-CRM",
    grain="세그먼트 × 구성요소 × 기준일 1행",
    columns=(
        C("segment", "string", "세그먼트", nullable=False, allowed=ASSET_CLASSES),
        C("asof", "date", "기준일", nullable=False),
        C("component", "string", "구성요소", nullable=False,
          allowed=LGD_COMPONENTS,
          citation="CRE36.83 — 회수·직접비용·간접비용·할인 분리"),
        C("value", "float", "EAD 대비 비율", nullable=False, unit="ratio",
          min_value=-1.0, max_value=2.0),
        C("basis", "text", "산출 근거", nullable=False),
    ),
    primary_key=("segment", "asof", "component"),
    note="LGD를 단일 수치로만 두면 회수시점·비용 가정 변경의 영향을 추적할 수 없다.",
)

EWS_SIGNAL = TableSpec(
    name="crm_ews_signal", korean="조기경보 신호", product="PRD-CRM",
    grain="차주 × 기준일 × 신호 1행",
    columns=(
        C("obligor_id", "string", "차주 식별자", nullable=False),
        C("asof", "date", "기준일", nullable=False),
        C("signal", "string", "신호", nullable=False),
        C("level", "string", "경보 단계", nullable=False, allowed=EWS_LEVELS),
        C("score", "float", "신호 강도", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("ead", "float", "익스포저", nullable=False, unit="KRW", min_value=0.0),
        C("action", "text", "권고 조치", nullable=False,
          note="에이전트는 순위를 제안할 뿐 등급·여신 결정을 확정하지 않는다"),
    ),
    primary_key=("obligor_id", "asof", "signal"),
    foreign_keys=(FK(("obligor_id",), "rdm_obligor", ("obligor_id",)),),
)

CRM_DETAIL_TABLES = (PD_CALIBRATION, RATING_MIGRATION, LGD_COMPONENT,
                     EWS_SIGNAL)

# ---------------------------------------------------------------- R11-C · RWA
MARKET_RISK_CLASSES = ("interest_rate", "equity", "fx", "commodity",
                       "credit_spread")
BI_COMPONENTS = ("ILDC", "SC", "FC")

RWA_SA_BUCKET = TableSpec(
    name="rwa_sa_bucket", korean="표준방법 위험가중치 구간별 집계",
    product="PRD-RWA",
    grain="기준일 × 자산군 × 위험가중치 구간 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("asset_class", "string", "자산군", nullable=False,
          allowed=ASSET_CLASSES, citation="CRE20 자산군"),
        C("rating_bucket", "string", "등급 구간", nullable=False,
          allowed=RATINGS + ("PAST_DUE", "LTV_BAND")),
        C("risk_weight", "float", "위험가중치", nullable=False, unit="ratio",
          min_value=0.0, max_value=15.0),
        C("n_exposures", "int", "익스포저 수", nullable=False, min_value=0),
        C("ead", "float", "EAD", nullable=False, unit="KRW", min_value=0.0),
        C("rwa", "float", "위험가중자산", nullable=False, unit="KRW",
          min_value=0.0),
        C("capital_required", "float", "소요자기자본", nullable=False,
          unit="KRW", min_value=0.0, citation="RWA × 8% (CRE20.1)"),
    ),
    primary_key=("asof", "asset_class", "rating_bucket", "risk_weight"),
    note="업무보고서 「신용리스크 표준방법」 라인의 직접 원천.",
)

RWA_IRB_POOL = TableSpec(
    name="rwa_irb_pool", korean="내부등급법 PD 구간별 pool", product="PRD-RWA",
    grain="기준일 × 자산군 × PD 구간 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("asset_class", "string", "자산군", nullable=False,
          allowed=ASSET_CLASSES),
        C("pd_band", "string", "PD 구간", nullable=False,
          citation="CRE32 · Pillar 3 CR6 서식 PD 구간"),
        C("n_exposures", "int", "익스포저 수", nullable=False, min_value=0),
        C("ead", "float", "EAD", nullable=False, unit="KRW", min_value=0.0),
        C("pd_weighted", "float", "EAD 가중 PD", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("lgd_weighted", "float", "EAD 가중 LGD", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("maturity_weighted", "float", "EAD 가중 만기", nullable=False,
          unit="years", min_value=0.0, max_value=50.0),
        C("rwa", "float", "위험가중자산", nullable=False, unit="KRW",
          min_value=0.0),
        C("rw_average", "float", "평균 위험가중치", nullable=False, unit="ratio",
          min_value=0.0, max_value=15.0),
        C("expected_loss", "float", "기대손실", nullable=False, unit="KRW",
          min_value=0.0),
    ),
    primary_key=("asof", "asset_class", "pd_band"),
    note="Pillar 3 CR6(IRB — 자산군·PD 구간별 익스포저) 공시 서식과 같은 입도.",
)

RWA_MARKET_COMPONENT = TableSpec(
    name="rwa_market_component", korean="시장리스크 위험군별 소요자본",
    product="PRD-RWA",
    grain="기준일 × 위험군 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("risk_class", "string", "위험군", nullable=False,
          allowed=MARKET_RISK_CLASSES,
          citation="MAR40 간편표준방법 위험군"),
        C("position", "float", "포지션", nullable=False, unit="KRW"),
        C("capital", "float", "소요자기자본", nullable=False, unit="KRW",
          min_value=0.0),
        C("rwa", "float", "위험가중자산", nullable=False, unit="KRW",
          min_value=0.0, citation="RWA = 12.5 × 소요자기자본"),
    ),
    primary_key=("asof", "risk_class"),
)

RWA_OPERATIONAL_BI = TableSpec(
    name="rwa_operational_bi", korean="운영리스크 사업지표 구성", product="PRD-RWA",
    grain="기준일 × BI 구성요소 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("component", "string", "BI 구성요소", nullable=False,
          allowed=BI_COMPONENTS,
          citation="OPE25.3 — 이자·리스·배당(ILDC), 수수료(SC), 금융(FC)"),
        C("amount", "float", "금액", nullable=False, unit="KRW", min_value=0.0),
        C("share", "float", "구성비", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0),
    ),
    primary_key=("asof", "component"),
    note="BI 구간(bucket)과 한계계수는 opr_capital의 산출 근거이며 "
         "구성요소가 분리되어야 사업부문별 자본배분이 가능하다.",
)

RWA_OUTPUT_FLOOR = TableSpec(
    name="rwa_output_floor", korean="산출하한 적용내역", product="PRD-RWA",
    grain="기준일 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("internal_rwa", "float", "내부모형 RWA", nullable=False, unit="KRW",
          min_value=0.0),
        C("standardised_rwa", "float", "표준방법 RWA", nullable=False,
          unit="KRW", min_value=0.0),
        C("floor_pct", "float", "하한 비율", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0,
          citation="RBC20.11 — 최종 72.5%"),
        C("floored_rwa", "float", "하한 적용 RWA", nullable=False, unit="KRW",
          min_value=0.0),
        C("binding", "bool", "하한 구속 여부", nullable=False,
          note="구속되면 내부모형 개선이 자본에 반영되지 않는다"),
        C("uplift", "float", "하한 증가분", nullable=False, unit="KRW",
          min_value=0.0),
    ),
    primary_key=("asof",),
)

RWA_DETAIL_TABLES = (RWA_SA_BUCKET, RWA_IRB_POOL, RWA_MARKET_COMPONENT,
                     RWA_OPERATIONAL_BI, RWA_OUTPUT_FLOOR)

# ---------------------------------------------------------------- R11-D · ECL
# 단계는 ifrs9_deep.attribution이 실제로 산출하는 요인이다. IFRS 7 35H의
# 신규취득·제거 구분을 쓰려면 기초/기말 두 시점 원장이 필요한데 현재 엔진은
# 요인별 귀속(PD·LGD·EAD·이동)만 산출한다 — 있지도 않은 구분을 적지 않는다.
PROVISION_BRIDGE_STEPS = ("opening", "pd_effect", "lgd_effect", "ead_effect",
                          "migration_effect", "closing")

ECL_STAGE_TRANSITION = TableSpec(
    name="ecl_stage_transition", korean="Stage 전이", product="PRD-ECL",
    grain="기준일 × 시작 Stage × 도착 Stage 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("from_stage", "int", "시작 Stage", nullable=False,
          min_value=1, max_value=3),
        C("to_stage", "int", "도착 Stage", nullable=False,
          min_value=1, max_value=3),
        C("n_exposures", "int", "익스포저 수", nullable=False, min_value=0),
        C("ead", "float", "EAD", nullable=False, unit="KRW", min_value=0.0),
        C("ecl_delta", "float", "ECL 증감", nullable=False, unit="KRW",
          citation="IFRS 9 5.5.3↔5.5.5 전이 시 12M↔lifetime 전환"),
    ),
    primary_key=("asof", "from_stage", "to_stage"),
)

ECL_SICR_STAT = TableSpec(
    name="ecl_sicr_trigger_stat", korean="SICR 트리거별 통계", product="PRD-ECL",
    grain="기준일 × 트리거 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("trigger", "string", "SICR 트리거", nullable=False,
          allowed=SICR_TRIGGERS, citation="IFRS 9 5.5.9 · B5.5.17"),
        C("n_exposures", "int", "익스포저 수", nullable=False, min_value=0),
        C("ead", "float", "EAD", nullable=False, unit="KRW", min_value=0.0),
        C("ecl", "float", "ECL", nullable=False, unit="KRW", min_value=0.0),
        C("share_of_stage2", "float", "Stage2 내 비중", nullable=False,
          unit="ratio", min_value=0.0, max_value=1.0),
    ),
    primary_key=("asof", "trigger"),
    note="어느 트리거가 Stage2를 만들었는지 분해되지 않으면 "
         "'30일 연체 반증'(B5.5.20) 논거를 세울 수 없다.",
)

ECL_PROVISION_BRIDGE = TableSpec(
    name="ecl_provision_bridge", korean="충당금 증감 브리지", product="PRD-ECL",
    grain="기준일 × 단계 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("step", "string", "단계", nullable=False,
          allowed=PROVISION_BRIDGE_STEPS,
          citation="IFRS 7 35H — 손실충당금 조정표"),
        C("seq", "int", "순서", nullable=False, min_value=1),
        C("amount", "float", "금액", nullable=False, unit="KRW"),
        C("cumulative", "float", "누계", nullable=False, unit="KRW"),
    ),
    primary_key=("asof", "step"),
)

ECL_DETAIL_TABLES = (ECL_STAGE_TRANSITION, ECL_SICR_STAT, ECL_PROVISION_BRIDGE)


# ---------------------------------------------------------------- R11-E · ALM
LCR_SECTIONS = ("HQLA", "OUTFLOW", "INFLOW")
NSFR_SECTIONS = ("ASF", "RSF")
# 버킷 라벨은 alm.irrbb가 실제로 만드는 값이다 — 추정으로 적으면 정상 산출이
# 도메인 위반으로 잡힌다.
REPRICING_BUCKETS = ("0-1m", "1-3m", "3-6m", "6-12m", "1-2y", "2-3y", "3-5y",
                     "5-10y", "10y+")

LCR_ITEM = TableSpec(
    name="alm_lcr_item", korean="LCR 항목별 내역", product="PRD-ALM",
    grain="기준일 × 구분 × 항목 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("section", "string", "구분", nullable=False, allowed=LCR_SECTIONS,
          citation="LCR30(HQLA) · LCR40(유출·유입)"),
        C("category", "string", "항목", nullable=False),
        C("amount", "float", "잔액", nullable=False, unit="KRW", min_value=0.0),
        C("factor", "float", "적용률", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0,
          note="HQLA는 haircut, 유출은 이탈률, 유입은 인식률"),
        C("weighted", "float", "가중 후 금액", nullable=False, unit="KRW",
          min_value=0.0),
        C("citation", "text", "근거", nullable=True),
    ),
    primary_key=("asof", "section", "category"),
    note="LCR을 비율 한 줄로만 두면 업무보고서 라인도, 원인분석도 불가능하다.",
)

NSFR_ITEM = TableSpec(
    name="alm_nsfr_item", korean="NSFR 항목별 내역", product="PRD-ALM",
    grain="기준일 × 구분 × 항목 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("section", "string", "구분", nullable=False, allowed=NSFR_SECTIONS,
          citation="NSF20(ASF) · NSF30(RSF)"),
        C("category", "string", "항목", nullable=False),
        C("amount", "float", "잔액", nullable=False, unit="KRW", min_value=0.0),
        C("factor", "float", "인정률", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("weighted", "float", "가중 후 금액", nullable=False, unit="KRW",
          min_value=0.0),
    ),
    primary_key=("asof", "section", "category"),
)

REPRICING_GAP = TableSpec(
    name="alm_repricing_gap", korean="금리 재설정 갭", product="PRD-ALM",
    grain="기준일 × 만기 버킷 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("bucket", "string", "만기 버킷", nullable=False,
          allowed=REPRICING_BUCKETS, citation="SRP31.94 표준 만기 구간"),
        C("seq", "int", "순서", nullable=False, min_value=1),
        C("asset", "float", "자산", nullable=False, unit="KRW", min_value=0.0),
        C("liability", "float", "부채", nullable=False, unit="KRW",
          min_value=0.0),
        C("gap", "float", "갭", nullable=False, unit="KRW"),
        C("cumulative_gap", "float", "누적 갭", nullable=False, unit="KRW"),
    ),
    primary_key=("asof", "bucket"),
)

ALM_DETAIL_TABLES = (LCR_ITEM, NSFR_ITEM, REPRICING_GAP)

# ---------------------------------------------------------------- R11-F · MKT
BACKTEST_ZONES = ("green", "amber", "red")
RISK_MEASURES = ("VaR_99", "ES_97_5", "sVaR_99")

RISK_FACTOR = TableSpec(
    name="mkt_risk_factor", korean="위험요소 마스터", product="PRD-MKT",
    grain="위험요소 × 기준일 1행",
    columns=(
        C("factor_id", "string", "위험요소 식별자", nullable=False),
        C("asof", "date", "기준일", nullable=False),
        C("risk_class", "string", "위험군", nullable=False,
          allowed=MARKET_RISK_CLASSES),
        C("curve", "string", "커브·표면", nullable=False),
        C("tenor", "float", "만기", nullable=False, unit="years",
          min_value=0.0, max_value=50.0),
        C("value", "float", "관측값", nullable=False, unit="mixed"),
        C("source", "string", "소스", nullable=False, allowed=PRICE_SOURCES),
        C("staleness_days", "int", "경과일수", nullable=False, unit="days",
          min_value=0, note="MAR31 stale data — 한도 초과 시 산출 신뢰 불가"),
        C("modellable", "bool", "모형화 가능", nullable=False,
          citation="MAR31.12 RFET — 미충족 시 NMRF로 SES 부과"),
    ),
    primary_key=("factor_id", "asof"),
)

BACKTEST_EXCEPTION = TableSpec(
    name="mkt_backtest_exception", korean="백테스팅 예외", product="PRD-MKT",
    grain="관측일 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("obs_date", "date", "관측일", nullable=False),
        C("var_99", "float", "1일 99% VaR", nullable=False, unit="KRW",
          min_value=0.0),
        C("pnl", "float", "손익", nullable=False, unit="KRW"),
        C("exception", "bool", "예외 여부", nullable=False,
          citation="MAR99.5 — 손실이 VaR를 초과한 날"),
        C("zone", "string", "신호등", nullable=False, allowed=BACKTEST_ZONES,
          citation="MAR99.6 누적 예외 4/10 구간"),
        C("cause", "string", "원인 후보", nullable=True),
    ),
    primary_key=("asof", "obs_date"),
)

VAR_ES = TableSpec(
    name="mkt_var_es", korean="VaR·ES 산출", product="PRD-MKT",
    grain="기준일 × 측정치 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("measure", "string", "측정치", nullable=False, allowed=RISK_MEASURES),
        C("horizon_days", "int", "보유기간", nullable=False, unit="days",
          min_value=1),
        C("confidence", "float", "신뢰수준", nullable=False, unit="ratio",
          min_value=0.5, max_value=1.0),
        C("value", "float", "값", nullable=False, unit="KRW", min_value=0.0),
        C("method", "string", "산출방법", nullable=False,
          allowed=("historical", "parametric", "monte_carlo")),
    ),
    primary_key=("asof", "measure"),
)

MKT_DETAIL_TABLES = (RISK_FACTOR, BACKTEST_EXCEPTION, VAR_ES)

# ---------------------------------------------------------------- R11-G · OPR
RECOVERY_TYPES = ("insurance", "direct", "third_party")
KRI_STATUS = ("green", "amber", "red")

OP_RECOVERY = TableSpec(
    name="opr_recovery", korean="운영손실 회수 내역", product="PRD-OPR",
    grain="회수 1건당 1행",
    columns=(
        C("recovery_id", "string", "회수 식별자", nullable=False),
        C("event_id", "string", "사건 식별자", nullable=False),
        C("recovery_type", "string", "회수 유형", nullable=False,
          allowed=RECOVERY_TYPES,
          citation="OPE25.20 — 보험회수는 적격 요건 충족 시에만 인정"),
        C("amount", "float", "회수액", nullable=False, unit="KRW",
          min_value=0.0),
        C("eligible", "bool", "적격 여부", nullable=False),
    ),
    primary_key=("recovery_id",),
    foreign_keys=(FK(("event_id",), "opr_loss_event", ("event_id",)),),
    note="사건 단위 회수 합계는 opr_loss_event.recovery와 일치해야 한다.",
)

OP_KRI = TableSpec(
    name="opr_kri", korean="운영리스크 KRI", product="PRD-OPR",
    grain="기준일 × 지표 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("kri_id", "string", "지표 식별자", nullable=False),
        C("kri_name", "text", "지표명", nullable=False),
        C("value", "float", "실측치", nullable=False, unit="mixed"),
        C("threshold_amber", "float", "주의 임계", nullable=False, unit="mixed"),
        C("threshold_red", "float", "경보 임계", nullable=False, unit="mixed"),
        C("status", "string", "판정", nullable=False, allowed=KRI_STATUS),
    ),
    primary_key=("asof", "kri_id"),
)

OP_CONTROL = TableSpec(
    name="opr_control", korean="PSMOR 원칙·통제 매핑", product="PRD-OPR",
    grain="통제 1건당 1행",
    columns=(
        C("control_id", "string", "통제 식별자", nullable=False),
        C("principle", "int", "PSMOR 원칙", nullable=False,
          min_value=1, max_value=12,
          citation="BCBS Principles for the Sound Management of Operational "
                   "Risk — 12개 원칙 (매핑이며 준수 인증이 아님)"),
        C("description", "text", "통제 내용", nullable=False),
        C("evidence_status", "string", "증빙 상태", nullable=False,
          allowed=("완결", "검토", "누락")),
        C("owner", "text", "책임 부서", nullable=False),
    ),
    primary_key=("control_id",),
)

OPR_DETAIL_TABLES = (OP_RECOVERY, OP_KRI, OP_CONTROL)


# ------------------------------------------------------- R11-H · REG 업무보고서
# 금융감독원 배포 기준 업무보고서(감독규정·시행세칙 별지 서식)를 채우기 위한
# 원장. 서식 라인 하나하나가 어떤 산식·어떤 모듈에서 나왔는지 남지 않으면
# 제출본을 재현할 수 없다.
REPORT_FREQUENCY = ("월", "분기", "반기", "연")
FORM_UNITS = ("KRW", "ratio", "count", "text")
SUBMISSION_STATUS = ("draft", "reviewed", "approved", "submitted")

REG_FORM = TableSpec(
    name="reg_form", korean="업무보고서 서식 마스터", product="PRD-REG",
    grain="서식 1개당 1행",
    columns=(
        C("form_id", "string", "서식 식별자", nullable=False),
        C("form_name", "text", "서식명", nullable=False),
        C("frequency", "string", "제출 주기", nullable=False,
          allowed=REPORT_FREQUENCY),
        C("citation", "text", "근거 규정", nullable=False,
          citation="은행업감독규정·동 시행세칙 별지 서식"),
        C("sheet_order", "int", "시트 순서", nullable=False, min_value=1),
        C("source_domain", "string", "산출 부문", nullable=False),
    ),
    primary_key=("form_id",),
    note="서식번호는 기관 배포본과 매핑이 필요하다 — 본 카탈로그는 내부 식별자를 쓴다.",
)

REG_FORM_LINE = TableSpec(
    name="reg_form_line", korean="업무보고서 라인", product="PRD-REG",
    grain="서식 × 라인코드 1행",
    columns=(
        C("form_id", "string", "서식 식별자", nullable=False),
        C("line_code", "string", "라인 코드", nullable=False),
        C("line_name", "text", "항목명", nullable=False),
        C("level", "int", "들여쓰기 단계", nullable=False,
          min_value=0, max_value=4),
        C("unit", "string", "단위", nullable=False, allowed=FORM_UNITS),
        C("value", "float", "값", nullable=True, unit="mixed",
          note="text 단위 라인(구분·비고)은 값이 없다"),
        C("text_value", "text", "문자값", nullable=True),
        C("formula", "text", "산식", nullable=True),
        C("citation", "text", "규정 근거", nullable=True),
        C("source_module", "text", "산출 모듈", nullable=True),
        C("is_subtotal", "bool", "소계 여부", nullable=False),
    ),
    primary_key=("form_id", "line_code"),
    foreign_keys=(FK(("form_id",), "reg_form", ("form_id",)),),
)

REG_FORM_CHECK = TableSpec(
    name="reg_form_check", korean="업무보고서 내부 검증", product="PRD-REG",
    grain="서식 × 검증항목 1행",
    columns=(
        C("form_id", "string", "서식 식별자", nullable=False),
        C("check_name", "string", "검증 항목", nullable=False),
        C("expected", "float", "기대값", nullable=False, unit="mixed"),
        C("actual", "float", "실제값", nullable=False, unit="mixed"),
        C("diff", "float", "차이", nullable=False, unit="mixed"),
        C("tolerance", "float", "허용 오차", nullable=False, unit="mixed",
          min_value=0.0),
        C("status", "string", "판정", nullable=False,
          allowed=("PASS", "FAIL")),
    ),
    primary_key=("form_id", "check_name"),
    foreign_keys=(FK(("form_id",), "reg_form", ("form_id",)),),
    note="소계=구성요소 합, 비율=분자/분모 — 제출 전에 서식 스스로 대사한다.",
)

REG_SUBMISSION = TableSpec(
    name="reg_submission", korean="업무보고서 제출 이력", product="PRD-REG",
    grain="서식 × 기준일 1행",
    columns=(
        C("form_id", "string", "서식 식별자", nullable=False),
        C("asof", "date", "기준일", nullable=False),
        C("prepared_by", "text", "작성자", nullable=False),
        C("reviewed_by", "text", "검토자", nullable=False),
        C("approved_by", "text", "승인자", nullable=False,
          note="작성자와 동일하면 직무분리 위반"),
        C("digest", "text", "산출 지문", nullable=False,
          citation="DAT-004 재현성 — 같은 지문이면 같은 제출본"),
        C("n_lines", "int", "라인 수", nullable=False, min_value=0),
        C("n_failed_checks", "int", "검증 실패 수", nullable=False, min_value=0),
        C("status", "string", "상태", nullable=False,
          allowed=SUBMISSION_STATUS),
    ),
    primary_key=("form_id", "asof"),
    foreign_keys=(FK(("form_id",), "reg_form", ("form_id",)),),
)

REG_TABLES = (REG_FORM, REG_FORM_LINE, REG_FORM_CHECK, REG_SUBMISSION)

# ------------------------------------------------------ R11-I · UIX 에이전틱 UI
# 「모든 모듈을 관리하는 에이전틱 UI」가 화면 코드만으로 끝나면 그 UI가 무엇을
# 허용했는지 증명할 수 없다. View·필드권한·조회계획·레이아웃 제안·에이전트
# 권한·활동·비상정지를 원장으로 둔다 (PLT-009~013 · RDM-008).
UI_MODES = ("structured", "adaptive", "cockpit")
SCHEMA_STATUS = ("승인됨", "초안", "폐기")
MASKING = ("none", "mask", "deny")
PLAN_STATUS = ("draft", "validated", "blocked")
PROPOSAL_STATUS = ("draft", "previewed", "approved", "rolled_back", "rejected")
AGENT_MODES = ("조회전용", "제안전용", "승인우선")
GATE_STATUS = ("통과", "검토", "대기", "차단")
KILL_SCOPES = ("agent", "tool", "workflow", "tenant")

UI_VIEW = TableSpec(
    name="ui_view", korean="승인 View 마스터", product="PRD-UIX",
    grain="View 1개당 1행",
    columns=(
        C("view_id", "string", "View 식별자", nullable=False),
        C("view_name", "text", "View 명", nullable=False),
        C("domain", "string", "부문", nullable=False),
        C("ui_mode", "string", "지원 모드", nullable=False, allowed=UI_MODES,
          citation="PLT-010 정형 · PLT-011 비정형"),
        C("schema_status", "string", "스키마 상태", nullable=False,
          allowed=SCHEMA_STATUS),
        C("row_limit", "int", "최대 행", nullable=False, min_value=1,
          note="상한이 없으면 대량 추출이 통제 밖으로 나간다"),
        C("read_only", "bool", "조회 전용", nullable=False),
        C("page_ref", "text", "연결 보고서 페이지", nullable=True),
        C("table_ref", "text", "연결 정규 테이블", nullable=True),
    ),
    primary_key=("view_id",),
    note="UI가 조회할 수 있는 대상은 이 원장에 등록된 View로 한정된다.",
)

UI_FIELD_POLICY = TableSpec(
    name="ui_field_policy", korean="필드 권한·마스킹 정책", product="PRD-UIX",
    grain="View × 필드 1행",
    columns=(
        C("view_id", "string", "View 식별자", nullable=False),
        C("field_name", "string", "필드", nullable=False),
        C("korean", "text", "한글명", nullable=False),
        C("permitted", "bool", "조회 허용", nullable=False),
        C("masking", "string", "마스킹", nullable=False, allowed=MASKING,
          citation="PLT-013 미승인 필드 차단 · 개인정보 보호"),
        C("min_aggregation", "int", "최소 집계단위", nullable=False,
          min_value=1, note="1이면 행 단위 조회 허용 — 개인정보 필드는 금지"),
    ),
    primary_key=("view_id", "field_name"),
    foreign_keys=(FK(("view_id",), "ui_view", ("view_id",)),),
)

UI_QUERY_PLAN = TableSpec(
    name="ui_query_plan", korean="자연어 조회계획", product="PRD-UIX",
    grain="조회계획 1건당 1행",
    columns=(
        C("plan_id", "string", "계획 식별자", nullable=False),
        C("view_id", "string", "View 식별자", nullable=False),
        C("asof", "date", "기준일", nullable=False),
        C("utterance", "text", "사용자 문장", nullable=False),
        C("intent", "text", "의도", nullable=False),
        C("population", "text", "모집단", nullable=False),
        C("condition_ast", "text", "조건 AST", nullable=False,
          citation="PLT-009 자연어 → Filter AST → 정책 → 조회계획"),
        C("policy", "text", "적용 정책", nullable=False),
        C("query_hash", "text", "조회 지문", nullable=False,
          note="같은 문장이라도 정책·기준일이 다르면 다른 지문이어야 한다"),
        C("n_rows", "int", "결과 행 수", nullable=False, min_value=0),
        C("status", "string", "상태", nullable=False, allowed=PLAN_STATUS),
        C("block_reason", "text", "차단 사유", nullable=True),
    ),
    primary_key=("plan_id",),
    foreign_keys=(FK(("view_id",), "ui_view", ("view_id",)),),
)

UI_LAYOUT_PROPOSAL = TableSpec(
    name="ui_layout_proposal", korean="비정형 레이아웃 제안", product="PRD-UIX",
    grain="제안 1건당 1행",
    columns=(
        C("proposal_id", "string", "제안 식별자", nullable=False),
        C("view_id", "string", "View 식별자", nullable=False),
        C("prompt", "text", "사용자 프롬프트", nullable=False),
        C("layout", "text", "제안 레이아웃", nullable=False),
        C("field_policy_pass", "bool", "필드권한 통과", nullable=False),
        C("schema_pass", "bool", "스키마·단위 통과", nullable=False),
        C("aggregation_pass", "bool", "집계 최소단위 통과", nullable=False),
        C("human_approved", "bool", "사람 승인", nullable=False,
          citation="PLT-012 — 미리보기·승인·Rollback 없이 화면 반영 금지"),
        C("status", "string", "상태", nullable=False, allowed=PROPOSAL_STATUS),
        C("rollback_of", "string", "되돌림 대상", nullable=True),
    ),
    primary_key=("proposal_id",),
    foreign_keys=(FK(("view_id",), "ui_view", ("view_id",)),),
    note="세 검증 중 하나라도 실패하면 human_approved는 참이 될 수 없다.",
)

AGENT_REGISTRY = TableSpec(
    name="agent_registry", korean="에이전트 레지스트리", product="PRD-UIX",
    grain="에이전트 1개당 1행",
    columns=(
        C("agent_id", "string", "에이전트 식별자", nullable=False),
        C("agent_name", "text", "에이전트명", nullable=False),
        C("mode", "string", "권한 모드", nullable=False, allowed=AGENT_MODES),
        C("tools", "text", "허용 도구", nullable=False),
        C("scope", "text", "데이터 범위", nullable=False),
        C("write_allowed", "bool", "운영 반영 권한", nullable=False,
          note="NO AUTONOMOUS WRITE — 전 에이전트가 거짓이어야 한다"),
        C("owner", "text", "책임 부서", nullable=False),
        C("domain", "string", "담당 부문", nullable=False),
    ),
    primary_key=("agent_id",),
)

AGENT_ACTIVITY = TableSpec(
    name="agent_activity", korean="에이전트 활동 원장", product="PRD-UIX",
    grain="활동 1건당 1행",
    columns=(
        C("activity_id", "string", "활동 식별자", nullable=False),
        C("run_id", "string", "실행 식별자", nullable=False),
        C("seq", "int", "순서", nullable=False, min_value=1),
        C("actor", "text", "수행 주체", nullable=False),
        C("tool", "text", "사용 도구", nullable=False),
        C("output", "text", "결과", nullable=False),
        C("gate", "string", "게이트", nullable=False, allowed=GATE_STATUS),
    ),
    primary_key=("activity_id",),
    note="프롬프트·도구·출력·승인이 남지 않으면 AI 개입 정당성을 증명할 수 없다 "
         "(ISO/IEC 42001 A.6.2.8 · EU AI Act 제12조 기록).",
)

AGENT_KILLSWITCH = TableSpec(
    name="agent_killswitch", korean="범위형 비상정지 이력", product="PRD-UIX",
    grain="정지 이벤트 1건당 1행",
    columns=(
        C("event_id", "string", "이벤트 식별자", nullable=False),
        C("scope_type", "string", "정지 범위", nullable=False,
          allowed=KILL_SCOPES),
        C("scope_ref", "text", "대상", nullable=False),
        C("mode", "string", "정지 방식", nullable=False,
          allowed=("safe_stop", "immediate")),
        C("reason", "text", "사유", nullable=False),
        C("requested_by", "text", "요청자", nullable=False),
        C("confirmed_by", "text", "2차 확인자", nullable=True,
          note="중요 범위는 독립된 2차 확인이 필요하다"),
    ),
    primary_key=("event_id",),
)

UIX_TABLES = (UI_VIEW, UI_FIELD_POLICY, UI_QUERY_PLAN, UI_LAYOUT_PROPOSAL,
              AGENT_REGISTRY, AGENT_ACTIVITY, AGENT_KILLSWITCH)

# ---------------------------------------------------- R11-J · 변경·증빙 (GOV)
CHANGE_TYPES = ("new_exposure_type", "new_product", "regulatory_rule",
                "data_schema")
CHANGE_STATUS = ("draft", "branch", "tested", "reviewed", "blocked")
EVIDENCE_STAGES = ("출처", "변환", "계산", "검증", "증빙", "승인", "보고")

CHANGE_REQUEST = TableSpec(
    name="chg_change_request", korean="리스크 변경 요청", product="PRD-VAL",
    grain="변경 요청 1건당 1행",
    columns=(
        C("change_id", "string", "변경 식별자", nullable=False),
        C("change_type", "string", "변경 유형", nullable=False,
          allowed=CHANGE_TYPES),
        C("target_domain", "string", "대상 부문", nullable=False),
        C("branch", "text", "브랜치", nullable=False),
        C("requested_by", "text", "요청자", nullable=False),
        C("n_components", "int", "영향 구성요소 수", nullable=False,
          min_value=0),
        C("deploy_allowed", "bool", "배포 허용", nullable=False,
          note="테스트·검토가 끝나기 전에는 항상 거짓"),
        C("status", "string", "상태", nullable=False, allowed=CHANGE_STATUS),
    ),
    primary_key=("change_id",),
)

CHANGE_IMPACT = TableSpec(
    name="chg_impact_map", korean="변경 영향도 맵", product="PRD-VAL",
    grain="변경 × 계층 × 노드 1행",
    columns=(
        C("change_id", "string", "변경 식별자", nullable=False),
        C("layer", "string", "계층", nullable=False,
          allowed=("data", "formula", "report", "owner")),
        C("node", "text", "노드", nullable=False),
        C("impact", "text", "영향", nullable=False),
    ),
    primary_key=("change_id", "layer", "node"),
    foreign_keys=(FK(("change_id",), "chg_change_request", ("change_id",)),),
)

CHANGE_REGRESSION = TableSpec(
    name="chg_regression_test", korean="변경 회귀테스트", product="PRD-VAL",
    grain="변경 × 테스트 1행",
    columns=(
        C("change_id", "string", "변경 식별자", nullable=False),
        C("test_name", "string", "테스트", nullable=False),
        C("scope", "text", "범위", nullable=False),
        C("covers_calc", "bool", "산출 검증", nullable=False),
        C("covers_report", "bool", "보고서 검증", nullable=False),
        C("status", "string", "판정", nullable=False,
          allowed=("통과", "검토", "실패")),
    ),
    primary_key=("change_id", "test_name"),
    foreign_keys=(FK(("change_id",), "chg_change_request", ("change_id",)),),
)

EVIDENCE_NODE = TableSpec(
    name="gov_evidence_node", korean="증빙 계보 노드", product="PRD-VAL",
    grain="실행 × 노드 1행",
    columns=(
        C("run_id", "string", "실행 식별자", nullable=False),
        C("node_id", "string", "노드 식별자", nullable=False),
        C("stage", "string", "단계", nullable=False, allowed=EVIDENCE_STAGES,
          citation="RYNTA 7단계 증빙 그래프 — 출처→변환→계산→검증→증빙→승인→보고"),
        C("label", "text", "라벨", nullable=False),
        C("ref", "text", "참조", nullable=False),
        C("status", "string", "상태", nullable=False,
          allowed=("완결", "검토", "누락")),
    ),
    primary_key=("run_id", "node_id"),
)

EVIDENCE_EDGE = TableSpec(
    name="gov_evidence_edge", korean="증빙 계보 간선", product="PRD-VAL",
    grain="실행 × 시작노드 × 도착노드 1행",
    columns=(
        C("run_id", "string", "실행 식별자", nullable=False),
        C("from_node", "string", "시작 노드", nullable=False),
        C("to_node", "string", "도착 노드", nullable=False),
        C("relation", "string", "관계", nullable=False,
          allowed=("derives", "verifies", "approves", "reports")),
    ),
    primary_key=("run_id", "from_node", "to_node"),
    note="노드만 있고 간선이 없으면 '연결된 계보'가 아니라 목록일 뿐이다.",
)

APPROVAL = TableSpec(
    name="gov_approval", korean="4-Eyes 승인 기록", product="PRD-VAL",
    grain="승인 1건당 1행",
    columns=(
        C("approval_id", "string", "승인 식별자", nullable=False),
        C("subject_type", "string", "대상 유형", nullable=False),
        C("subject_id", "string", "대상 식별자", nullable=False),
        C("reviewer", "text", "검토자", nullable=False),
        C("approver", "text", "승인자", nullable=False),
        C("segregation_ok", "bool", "직무분리 충족", nullable=False,
          note="검토자 = 승인자면 거짓 — 승인 효력 없음"),
        C("decision", "string", "결정", nullable=False,
          allowed=("승인", "반려", "대기")),
        C("evidence_ref", "text", "증빙 참조", nullable=False),
    ),
    primary_key=("approval_id",),
)

GOV_DETAIL_TABLES = (CHANGE_REQUEST, CHANGE_IMPACT, CHANGE_REGRESSION,
                     EVIDENCE_NODE, EVIDENCE_EDGE, APPROVAL)

# ------------------------------------------------------------- 최종 누적 등록
DETAIL_TABLES = (RDM_DETAIL_TABLES + CRM_DETAIL_TABLES + RWA_DETAIL_TABLES
                 + ECL_DETAIL_TABLES + ALM_DETAIL_TABLES + MKT_DETAIL_TABLES
                 + OPR_DETAIL_TABLES + REG_TABLES + UIX_TABLES
                 + GOV_DETAIL_TABLES)

ALL_TABLES = (RDM_TABLES + CRM_TABLES + RWA_TABLES + ECL_TABLES
              + ST_TABLES + ALM_TABLES + MKT_TABLES + OPR_TABLES + VAL_TABLES
              + DETAIL_TABLES)
