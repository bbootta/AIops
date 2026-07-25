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
