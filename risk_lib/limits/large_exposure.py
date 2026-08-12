"""거액익스포져(Large Exposures) 산출 엔진과 원장.

**두 체계가 있고 분모가 다르다.** 감독규정 제26조제1항제6호의 거액익스포져비율은
분모가 **기본자본(Tier 1)** 이고, 은행법 제35조의 신용공여한도는 분모가 **자기자본**
이다. 같은 익스포져에 두 비율이 동시에 걸리며 한도율도 다르다. 이 모듈은 두 체계를
`lex_setting` 원장의 별도 계정으로 두고 나란히 산출한다. 섞으면 어느 쪽 위반인지
말할 수 없게 된다.

**규제값은 전부 `build_lex_setting`에만 있다.** 엔진 함수 본문과 기본값에 숫자가
없다. 한도율·보고기준·look-through 기준·신용환산율 하한을 바꾸려면 원장 행을
바꿔야 하고, 바뀐 행은 화면에 보이고 승인자가 붙는다. 원장에 값이 NULL이면
(`evidence_status='미확인'` 또는 `'재량·미규정'`) 엔진은 조용히 기본값을 쓰지 않고
`ParamWarning`을 남기고 그 산출을 건너뛴다.

**대체(substitution)가 이 규제의 요점이다.** 별표 3-12 23.은 적격 경감기법으로
원 거래상대방의 익스포져를 차감하면 **그 금액을 보장제공자에 대한 익스포져로
인식하도록** 강제한다. 차주 A의 리스크를 줄인 보장이 보장제공자 B를 한도 밖으로
밀어낼 수 있고, 그것을 보이게 하는 것이 규제의 목적이다. 그래서 대체 전과 후를
둘 다 원장에 남긴다. 별표 3-12 7.가(1)·(2)가 CRM 미적용분과 적용분을 각각
보고하도록 한 것도 같은 이유다.

**면제액을 조용히 빼지 않는다.** 38.은 면제대상도 보고대상에 포함시킨다
(은행 간 일중 거래만 제외). 면제액과 근거가 원장에 남아야 감독당국이 면제 판단을
검증할 수 있다.

근거 원문과 조문 인용은 `docs/primary_sources/거액익스포저_원문발췌.md`에 있다.
추출본문은 `docs/primary_sources/규정원문_20260809/` 아래에 있다.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np
import pandas as pd

from risk_lib.alm.behaviour import ParamWarning
from risk_lib.alm.params import EVIDENCE_STATUS
from risk_lib.datamodel.spec import ColumnSpec as C, ForeignKey as FK, TableSpec
from risk_lib.validation.consistency import ConsistencyCheck, ValidationReport

__all__ = [
    "LEX_FRAMEWORKS", "MEASURE_FRAMEWORK", "DENOMINATOR_BASES",
    "AGGREGATION_UNITS", "EXPOSURE_TYPES", "PROTECTION_TYPES",
    "CONNECTION_BASES", "EXEMPTION_TYPES", "ATTRIBUTION_TYPES",
    "COUNTERPARTY_CLASSES", "PARAM_CODES", "UNKNOWN_CLIENT_ID",
    "SETTING", "EXPOSURE_MEASURE", "SUBSTITUTION", "CONNECTED_GROUP",
    "EXEMPTION", "LOOKTHROUGH", "POSITION", "AGGREGATE", "LEX_TABLES",
    "build_lex_setting", "setting_value", "denominator_basis",
    "measure_exposures", "apply_lookthrough", "apply_substitution",
    "apply_exemptions", "resolve_connected_groups",
    "compute_positions", "compute_aggregate",
    "check_substitution_conservation", "check_exemption_conservation",
    "check_lookthrough_conservation", "check_group_additivity",
    "check_reporting_completeness", "check_aggregate_numerator",
    "check_group_ratio_dominance", "run_lex_checks",
    "LexInputs", "LexResult", "compute_large_exposure",
    "build_lex_inputs", "large_exposure_lex",
]


# ---------------------------------------------------------------- 어휘

# 체계 계정. 분모가 다르므로 한 원장 안에 두되 절대 섞지 않는다.
LEX_FRAMEWORKS: tuple[str, ...] = (
    "감독규정26조_기본자본",
    "은행법35조_동일차주",
    "은행법35조_동일인",
    "BCBS_d283_2014",
)

# 익스포져 측정 규칙(별표 3-12 제3절)을 정의한 체계. 은행법 §35의 "신용공여" 범위는
# 시행령이 정하는데 원문을 확보하지 못했다. 그 사실은 lex_setting의
# credit_extension_scope 행에 evidence_status='미확인'으로 적혀 있고, 은행법 계정은
# 이 체계의 측정액을 대용한다.
MEASURE_FRAMEWORK = "감독규정26조_기본자본"

DENOMINATOR_BASES: tuple[str, ...] = ("tier1", "own_funds")
AGGREGATION_UNITS: tuple[str, ...] = ("거래상대방그룹", "개별차주")

EXPOSURE_TYPES: tuple[str, ...] = (
    "은행계정_난내",            # 14.
    "부외",                    # 17.
    "장외파생_SACCR",           # 15.
    "증권금융거래",             # 16.
    "트레이딩_채권주식",         # 26.
    "이중상환청구권부채권",       # 41.·42.
    "중앙청산소_청산관련",        # 51.
    "구조화상품",               # 30.·43. 관통 전 원시 보유
    "구조화상품_관통",           # 46.가·나 기초자산 귀속분
    "구조화상품_자체",           # 44.가·44.나 단서·44.다 전단
    "무명고객",                 # 44.다 후단
    "구조화상품_제3자추가리스크",  # 47.
    "신용위험경감_대체분",        # 23. 보장제공자에게 가산된 분
)

# 19.은 적격 경감기법을 무담보신용보장(보증·신용파생)과 금융자산담보로 한정하고,
# 내부등급법 전용 담보(매출채권·부동산·기타)의 경감효과를 인정하지 않는다.
PROTECTION_TYPES: tuple[str, ...] = (
    "보증", "신용파생상품", "신용부도스왑", "금융자산담보", "자행예금상계")

CONNECTION_BASES: tuple[str, ...] = ("지배관계", "경제적상호의존", "단독")

EXEMPTION_TYPES: tuple[str, ...] = (
    "국가등",              # 37.가(1)
    "국가등_보증담보",       # 37.가(2)
    "은행간_일중",          # 37.가(3)
    "적격CCP_청산관련",      # 37.가(4)
    "은행그룹내부",          # 37.가(5)
    "정부현물출자주식",       # 37.나 (규정 §26①6 나목)
    "농협중앙회_국가위탁",    # 37.나 (다목)
    "가계자금보증",          # 37.나 (라목)
    "금융위인정_공익목적",     # 37.나 (마목)
    "자본차감",             # 13.
)

ATTRIBUTION_TYPES: tuple[str, ...] = (
    "기초자산", "구조화상품자체", "무명고객", "제3자추가리스크")

COUNTERPARTY_CLASSES: tuple[str, ...] = (
    "일반", "D-SIB", "G-SIB", "국가등", "적격CCP", "비적격CCP", "은행그룹내부",
    "무명고객")

PARAM_CODES: tuple[str, ...] = (
    "limit_general",                   # 일반 한도율
    "limit_sib",                       # 상대방이 D-SIB·G-SIB인 경우
    "limit_gsib_to_gsib",              # 본 은행이 G-SIB이고 상대방도 G-SIB
    "bank_is_gsib",                    # 본 은행의 G-SIB 지정 여부 (0/1)
    "reporting_threshold",             # 보고기준 / 거액 판정기준
    "aggregate_limit",                 # 거액신용공여 총액한도
    "econ_interdep_review_threshold",  # 경제적 상호의존성 평가 의무 대상 기준
    "lookthrough_threshold",           # 기초자산접근법 적용 기준
    "lookthrough_small_to_structure",  # 44.나 단서 재량 행사 여부 (0/1)
    "ccf_floor",                       # 부외 신용환산율 하한
    "covered_bond_floor",              # 이중상환청구권부채권 최저 인식률
    "nonqualifying_ccp_limit",         # 비적격 중앙청산소 한도
    "control_voting_threshold",        # 지배관계 자동인정 의결권 비율
    "interdep_revenue_ratio",          # 경제적 상호의존 수입·지출 의존도 기준
    "credit_extension_scope",          # 은행법 §35 "신용공여" 범위 (미확인)
)

# 44.다 후단은 무명고객 익스포져를 전부 합산해 하나의 거래상대방으로 본다.
# 가상 차주 식별자를 고정해 둬야 여러 구조화상품의 관통 불가분이 한 곳에 모인다.
UNKNOWN_CLIENT_ID = "CP_UNKNOWN_CLIENT"

_BASE = "은행업감독업무시행세칙 [별표 3-12] 거액익스포져비율 산출기준"
_REG = "은행업감독규정"
_ACT = "은행법"

_ATOL = 1e-6
_RTOL = 1e-9


def _tol(scale):
    """규모 비례 허용오차. 원화 잔액은 1e12 규모라 절대오차만으로는 부동소수
    잔차가 위반으로 잡힌다."""
    return _ATOL + _RTOL * np.abs(scale)


# ---------------------------------------------------------------- 설정 원장

SETTING = TableSpec(
    name="lex_setting", korean="거액익스포져 설정", product="PRD-LIMIT",
    grain="기준일 × 체계 × 설정항목 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("framework", "string", "체계", nullable=False, allowed=LEX_FRAMEWORKS),
        C("param_code", "string", "설정항목", nullable=False, allowed=PARAM_CODES),
        C("param_value", "float", "값", nullable=True, unit="param_unit 컬럼 참조",
          note="NULL은 '규정이 값을 정하지 않았다' 또는 '원문 미확인'이다. "
               "엔진은 NULL을 만나면 기본값을 쓰지 않고 ParamWarning을 남기고 "
               "해당 산출을 건너뛴다"),
        C("param_unit", "string", "단위", nullable=False,
          allowed=("ratio", "multiple", "flag", "code")),
        C("denominator_basis", "string", "분모 기준", nullable=False,
          allowed=DENOMINATOR_BASES,
          note="감독규정 §26은 기본자본, 은행법 §35는 자기자본이다. 두 분모를 "
               "섞으면 어느 체계의 위반인지 말할 수 없다"),
        C("aggregation_unit", "string", "집계 단위", nullable=False,
          allowed=AGGREGATION_UNITS),
        C("citation", "text", "근거", nullable=False),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
        C("is_overridden", "bool", "수기조정 여부", nullable=False,
          note="화면에서 값을 바꾸면 True가 되고 산출이 따라간다. 규정값과 다른 "
               "값으로 돌린 사실이 원장에 남아야 결재에서 보인다"),
        C("override_reason", "text", "수기조정 사유", nullable=True),
        C("input_by", "string", "입력자", nullable=False),
        C("approved_by", "string", "승인자", nullable=False),
        C("approved_at", "date", "승인일", nullable=False),
        C("note", "text", "비고", nullable=True),
    ),
    primary_key=("asof", "framework", "param_code"),
    note="거액익스포져 산출이 읽는 규제계수의 유일한 출처. 엔진 함수 본문과 "
         "기본값에는 숫자가 없다.",
)


def build_lex_setting(
    asof: str, *,
    bank_is_gsib: bool,
    lookthrough_small_to_structure: bool,
    input_by: str,
    approved_by: str,
    approved_at: str,
    overrides: dict[tuple[str, str], float] | None = None,
    override_reason: str = "",
) -> pd.DataFrame:
    """거액익스포져 설정 원장을 만든다. 규제표를 적재하는 유일한 자리다.

    `bank_is_gsib`와 `lookthrough_small_to_structure`는 규정이 값을 주는 항목이
    아니다. 앞의 것은 본 은행의 G-SIB 지정 사실(감독규정 §26의2⑩이 15% 한도를
    거기에 건다), 뒤의 것은 별표 3-12 44.나 단서가 은행에 준 재량의 행사 여부다.
    둘 다 승인자가 기록해야 하는 값이므로 인자로 받는다.

    `overrides`는 화면에서 바꾼 값이다. `{(체계, 항목): 값}` 형태이며 해당 행의
    `is_overridden`이 True가 되고 산출이 그 값을 따라간다.
    """
    ovr = dict(overrides or {})
    rows: list[dict] = []

    def add(framework, code, value, unit, denom, agg, citation, evidence,
            note=""):
        key = (framework, code)
        overridden = key in ovr
        rows.append({
            "asof": asof, "framework": framework, "param_code": code,
            "param_value": float(ovr[key]) if overridden else (
                np.nan if value is None else float(value)),
            "param_unit": unit, "denominator_basis": denom,
            "aggregation_unit": agg, "citation": citation,
            "evidence_status": evidence, "is_overridden": overridden,
            "override_reason": override_reason if overridden else None,
            "input_by": input_by, "approved_by": approved_by,
            "approved_at": approved_at, "note": note or None,
        })

    # ---- 감독규정 제26조 체계 (분모 = 기본자본)
    fw, dn, ag = "감독규정26조_기본자본", "tier1", "거래상대방그룹"
    add(fw, "limit_general", 0.25, "ratio", dn, ag,
        f"{_REG} 제26조제1항제6호 '100분의 25 이하'", "원문확인")
    add(fw, "limit_sib", 0.20, "ratio", dn, ag,
        f"{_REG} 제26조제1항제6호 단서 '거래상대방이 금융체계상 중요한 은행 또는 "
        f"글로벌 금융체계상 중요한 은행인 경우 100분의 20 이하'", "원문확인")
    add(fw, "limit_gsib_to_gsib", 0.15, "ratio", dn, ag,
        f"{_REG} 제26조의2제10항 '금융체계상 중요한 은행이 글로벌 금융체계상 "
        f"중요한 은행인 경우 다른 글로벌 금융체계상 중요한 은행에 대하여 "
        f"100분의 15 이하'", "원문확인")
    add(fw, "bank_is_gsib", 1.0 if bank_is_gsib else 0.0, "flag", dn, ag,
        f"{_REG} 제26조의2제10항이 15% 한도를 본 은행의 G-SIB 지정 여부에 건다",
        "원문확인",
        note="규정이 주는 값이 아니라 본 은행의 지정 사실이다. 승인자가 기록한다")
    add(fw, "reporting_threshold", 0.10, "ratio", dn, ag,
        f"{_BASE} 2.라 '거액익스포져'는 합계가 기본자본의 100분의 10 이상인 경우 "
        f"· 7.가(1)(2)(4) 보고대상", "원문확인")
    add(fw, "aggregate_limit", None, "multiple", dn, ag,
        f"{_REG} 제26조는 거액익스포져의 총액한도를 두지 않는다", "재량·미규정",
        note="총액한도는 은행법 §35④에만 있다. 이 계정에서는 산출하지 않는다")
    add(fw, "econ_interdep_review_threshold", 0.05, "ratio", dn, ag,
        f"{_BASE} 10. '익스포져가 기본자본의 100분의 5를 초과하는 모든 단일 "
        f"거래상대방에 대해서는 경제적 상호의존성 평가가 포함되도록 기준을 수립'",
        "원문확인")
    add(fw, "lookthrough_threshold", 0.0025, "ratio", dn, ag,
        f"{_BASE} 44.가·나·다 '기본자본의 0.25%'", "원문확인")
    add(fw, "lookthrough_small_to_structure",
        1.0 if lookthrough_small_to_structure else 0.0, "flag", dn, ag,
        f"{_BASE} 44.나 단서 '0.25% 미만이 투자된 기초자산에 대해서는 구조화상품 "
        f"자체에 대한 익스포져로 인식할 수 있다'", "원문확인",
        note="단서가 '할 수 있다'이므로 은행 선택이다. 승인자가 기록한다")
    add(fw, "ccf_floor", 0.10, "ratio", dn, ag,
        f"{_BASE} 17. '신용환산율의 하한은 10%로 한다'", "원문확인")
    add(fw, "covered_bond_floor", 0.20, "ratio", dn, ag,
        f"{_BASE} 42. 단서 '차감 후 익스포져 금액은 채권 명목가액의 20%를 "
        f"하회할 수 없다'", "원문확인")
    add(fw, "nonqualifying_ccp_limit", 0.25, "ratio", dn, ag,
        f"{_BASE} 49. '비적격 중앙청산소 익스포져는 기본자본의 100분의 25 이내'",
        "원문확인")
    add(fw, "control_voting_threshold", 0.50, "ratio", dn, ag,
        f"{_BASE} 9. 단서 '과반수 의결권을 보유하는 경우 자동으로 통제관계가 "
        f"존재하는 것으로 간주'", "원문확인",
        note="과반수이므로 초과(>) 판정이다. 정확히 50%는 자동인정이 아니다")
    add(fw, "interdep_revenue_ratio", 0.50, "ratio", dn, ag,
        f"{_BASE} 10.가 '연간 총수입 또는 총지출의 50% 이상이 다른 거래상대방과의 "
        f"거래에서 발생하는 경우'", "원문확인",
        note="'이상'이므로 >= 판정이다")

    # ---- 은행법 제35조 체계 (분모 = 자기자본)
    for fw, agg_unit, limit, limit_cite in (
        ("은행법35조_동일차주", "거래상대방그룹", 0.25,
         f"{_ACT} 제35조제1항 '동일차주에 대하여 그 은행의 자기자본의 100분의 25를 "
         f"초과하는 신용공여를 할 수 없다'"),
        ("은행법35조_동일인", "개별차주", 0.20,
         f"{_ACT} 제35조제3항 '동일한 개인이나 법인 각각에 대하여 그 은행의 "
         f"자기자본의 100분의 20을 초과하는 신용공여를 할 수 없다'"),
    ):
        dn = "own_funds"
        add(fw, "limit_general", limit, "ratio", dn, agg_unit, limit_cite,
            "원문확인")
        add(fw, "reporting_threshold", 0.10, "ratio", dn, agg_unit,
            f"{_ACT} 제35조제4항 '자기자본의 100분의 10을 초과하는 거액 신용공여'",
            "원문확인",
            note="이 체계에서는 보고기준이 아니라 총액한도 산입 기준이다")
        add(fw, "aggregate_limit", 5.0, "multiple", dn, agg_unit,
            f"{_ACT} 제35조제4항 '그 총합계액은 그 은행의 자기자본의 5배를 "
            f"초과할 수 없다'", "원문확인",
            note="분자는 전체 합이 아니라 자기자본 10% 초과 건들의 합이다")
        add(fw, "credit_extension_scope", None, "code", dn, agg_unit,
            f"{_ACT} 제35조의 '신용공여' 범위는 같은 법 시행령이 정한다. "
            f"시행령 원문 미확보", "미확인",
            note="별표 3-12 제3절의 익스포져 측정액을 대용한다. 대용 사실이 "
                 "lex_position.measure_evidence_status에 실린다")

    # ---- BCBS d283 계정 (원문 미확보)
    fw, dn, ag = "BCBS_d283_2014", "tier1", "거래상대방그룹"
    for code, unit in (("limit_general", "ratio"),
                       ("limit_gsib_to_gsib", "ratio"),
                       ("reporting_threshold", "ratio")):
        add(fw, code, None, unit, dn, ag,
            "BCBS d283 Supervisory framework for measuring and controlling "
            "large exposures (2014) 원문 미확보 (bis.org egress 차단)", "미확인",
            note="국내 이행분인 감독규정 §26 계정이 원문확인이며 그쪽을 쓴다. "
                 "이 계정은 값이 비어 있어 산출되지 않는다")

    return pd.DataFrame(rows)


def setting_value(
    setting: pd.DataFrame, framework: str, code: str, *, required: bool = True,
) -> float | None:
    """설정 조회.

    행 자체가 없으면 원장 결함이므로 `required=True`일 때 KeyError로 멈춘다.
    행은 있고 값이 NULL이면 "규정이 정하지 않았다" 또는 "원문 미확인"이므로
    None을 돌려주고, 호출자가 경고를 남기고 그 산출을 건너뛴다. 두 사건을 같은
    방식으로 처리하면 원장 누락이 조용히 "산출 생략"으로 둔갑한다.
    """
    hit = setting.loc[
        (setting["framework"] == framework) & (setting["param_code"] == code),
        "param_value"]
    if hit.empty:
        if required:
            raise KeyError(f"lex_setting에 ({framework}, {code}) 행이 없다")
        return None
    v = hit.iloc[0]
    return None if pd.isna(v) else float(v)


def denominator_basis(setting: pd.DataFrame, framework: str) -> str:
    """체계의 분모 기준을 원장에서 읽는다. 엔진이 분모를 고르지 않는다."""
    hit = setting.loc[setting["framework"] == framework, "denominator_basis"]
    if hit.empty:
        raise KeyError(f"lex_setting에 체계 {framework!r} 행이 없다")
    return str(hit.iloc[0])


def _aggregation_unit(setting: pd.DataFrame, framework: str) -> str:
    hit = setting.loc[setting["framework"] == framework, "aggregation_unit"]
    if hit.empty:
        raise KeyError(f"lex_setting에 체계 {framework!r} 행이 없다")
    return str(hit.iloc[0])


# ---------------------------------------------------------------- 측정 원장

EXPOSURE_MEASURE = TableSpec(
    name="lex_exposure_measure", korean="거액익스포져 측정", product="PRD-LIMIT",
    grain="기준일 × 거래상대방 × 익스포져유형 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("counterparty_id", "string", "거래상대방", nullable=False),
        C("exposure_type", "string", "익스포져유형", nullable=False,
          allowed=EXPOSURE_TYPES),
        C("gross_amount", "float", "측정 전 금액", nullable=False, unit="KRW",
          min_value=0.0,
          note="난내는 장부가액, 부외는 계약금액, 커버드본드는 명목가액이다"),
        C("deduction_amount", "float", "차감액", nullable=False, unit="KRW",
          min_value=0.0,
          note="난내는 고정이하 대손충당금(14.), 증권금융거래는 표준차감률 조정 "
               "담보가치(16.), 커버드본드는 기초자산 명목금액(42.)"),
        C("conversion_factor", "float", "적용 신용환산율", nullable=True,
          unit="ratio", min_value=0.0, max_value=1.0,
          note="부외항목만. 원장 하한(17. 10%)을 적용한 뒤의 값이다"),
        C("measured_amount", "float", "측정액", nullable=True, unit="KRW",
          note="NULL은 측정 불가다. 조용히 0으로 만들지 않는다"),
        C("measure_basis", "text", "측정근거", nullable=False),
        C("measure_status", "string", "측정 상태", nullable=False,
          allowed=("측정", "측정불가")),
        C("n_exposures", "int", "건수", nullable=False, unit="count",
          min_value=0),
    ),
    primary_key=("asof", "counterparty_id", "exposure_type"),
    note="유형별로 측정방법이 다르므로 유형이 입도에 들어간다. 측정근거 컬럼이 "
         "어느 조문으로 잰 금액인지 말한다.",
)


def _as_measure(df: pd.DataFrame) -> pd.DataFrame:
    """측정 원장 프레임을 스펙 컬럼 순서·정렬로 맞춘다.

    groupby.agg는 집계 인자를 준 순서로 컬럼을 놓으므로 경로마다 순서가 갈린다.
    원장은 스펙이 정한 순서 하나여야 화면·DDL·검증이 같은 표를 본다.
    """
    return df[list(EXPOSURE_MEASURE.column_names)].sort_values(
        ["asof", "counterparty_id", "exposure_type"]).reset_index(drop=True)


def measure_exposures(
    universe: pd.DataFrame, setting: pd.DataFrame, *,
    framework: str = MEASURE_FRAMEWORK,
) -> tuple[pd.DataFrame, list[ParamWarning]]:
    """익스포져 유형별 측정 (별표 3-12 제3절).

    입력 `universe`는 익스포져 1건 1행이며 다음 컬럼을 쓴다.
      asof · exposure_id · counterparty_id · exposure_type
      gross_amount        난내 장부가액 / 부외 계약금액 / 명목가액
      deduction_amount    고정이하 대손충당금 · 조정 담보가치 · 기초자산 명목금액
      conversion_factor   부외 신용환산율 (세칙 <별표3> 제2장 제4절 값)
      measured_override   외부 엔진 산출액 (장외파생의 SA-CCR EAD 등)

    유형별 규칙은 아래와 같고 어느 조문으로 쟀는지가 `measure_basis`로 남는다.
    측정에 필요한 입력이 비어 있으면 0으로 만들지 않고 `measure_status='측정불가'`,
    `measured_amount=NULL`로 두고 경고를 남긴다. 0으로 만들면 한도 소진율이
    과소계상되고 그 사실이 어디에도 보이지 않는다.
    """
    warns: list[ParamWarning] = []
    ccf_floor = setting_value(setting, framework, "ccf_floor")
    cb_floor = setting_value(setting, framework, "covered_bond_floor")
    if ccf_floor is None:
        warns.append(ParamWarning(
            "lex_measure", "부외", "ccf_floor",
            "신용환산율 하한이 원장에 비어 있다. 부외 익스포져를 측정하지 않는다"))
    if cb_floor is None:
        warns.append(ParamWarning(
            "lex_measure", "이중상환청구권부채권", "covered_bond_floor",
            "최저 인식률이 원장에 비어 있다. 커버드본드를 측정하지 않는다"))

    u = universe.copy()
    for col in ("deduction_amount", "conversion_factor", "measured_override"):
        if col not in u.columns:
            u[col] = np.nan
    u["deduction_amount"] = u["deduction_amount"].fillna(0.0)

    gross = u["gross_amount"].to_numpy(dtype=float)
    deduct = u["deduction_amount"].to_numpy(dtype=float)
    ccf_in = u["conversion_factor"].to_numpy(dtype=float)
    override = u["measured_override"].to_numpy(dtype=float)
    kind = u["exposure_type"].to_numpy()

    measured = np.full(len(u), np.nan)
    basis = np.array([""] * len(u), dtype=object)
    ccf_applied = np.full(len(u), np.nan)

    def _set(mask, values, text):
        measured[mask] = values
        basis[mask] = text

    m = kind == "은행계정_난내"
    _set(m, np.maximum(gross[m] - deduct[m], 0.0),
         f"{_BASE} 14. 재무상태표상 자산 − 고정이하 대손충당금")

    m = kind == "부외"
    if ccf_floor is not None:
        eff = np.maximum(ccf_in[m], ccf_floor)
        ccf_applied[m] = eff
        _set(m, gross[m] * eff,
             f"{_BASE} 17. 계약금액 × max(세칙 <별표3> 제2장 제4절 신용환산율, "
             f"하한 {ccf_floor:.0%})")
    else:
        basis[m] = f"{_BASE} 17. 하한 미적재로 측정 불가"

    m = kind == "장외파생_SACCR"
    _set(m, override[m],
         f"{_BASE} 15. 세칙 <별표3> 제7장 제3절 제2관의2 거래상대방신용위험 "
         f"표준방식(SA-CCR)")

    m = kind == "증권금융거래"
    _set(m, np.maximum(gross[m] - deduct[m], 0.0),
         f"{_BASE} 16. 세칙 <별표3> 제2장 제6절 제3관 표준차감률 포괄법")

    m = kind == "트레이딩_채권주식"
    _set(m, gross[m], f"{_BASE} 26. 재무상태표상 금액")

    m = kind == "이중상환청구권부채권"
    if cb_floor is not None:
        _set(m, np.maximum(gross[m] - deduct[m], gross[m] * cb_floor),
             f"{_BASE} 42. 명목가액 − 기초자산 명목금액, 명목가액의 "
             f"{cb_floor:.0%} 하한")
    else:
        basis[m] = f"{_BASE} 42. 하한 미적재로 측정 불가"

    m = kind == "중앙청산소_청산관련"
    _set(m, gross[m],
         f"{_BASE} 51. 거래익스포져·비절연 개시증거금·기납입 공동기금 출연금")

    m = kind == "구조화상품"
    _set(m, gross[m], f"{_BASE} 46.다 구조화상품에 투자된 명목금액 (관통 전)")

    u["measured_amount"] = measured
    u["measure_basis"] = basis
    u["conversion_factor"] = ccf_applied

    unknown = u[u["measure_basis"] == ""]
    if len(unknown):
        for kind_name in sorted(set(unknown["exposure_type"])):
            warns.append(ParamWarning(
                "lex_measure", str(kind_name), "measure_rule",
                "측정규칙이 정의되지 않은 익스포져유형이다. 측정을 건너뛴다"))
    bad = u["measured_amount"].isna()
    for kind_name in sorted(set(u.loc[bad, "exposure_type"])):
        n = int((bad & (u["exposure_type"] == kind_name)).sum())
        warns.append(ParamWarning(
            "lex_measure", str(kind_name), "measured_amount",
            f"{n}건의 측정 입력이 비어 있다. 0으로 만들지 않고 측정불가로 둔다"))

    u["measure_status"] = np.where(bad, "측정불가", "측정")
    agg = u.groupby(["asof", "counterparty_id", "exposure_type"],
                    as_index=False, dropna=False).agg(
        gross_amount=("gross_amount", "sum"),
        deduction_amount=("deduction_amount", "sum"),
        conversion_factor=("conversion_factor", "mean"),
        measured_amount=("measured_amount", "sum"),
        measure_basis=("measure_basis", "first"),
        n_exposures=("exposure_id", "size"),
    )
    # 유형 안에 측정불가가 하나라도 있으면 그 유형 전체를 측정불가로 표시한다.
    status = u.groupby(["asof", "counterparty_id", "exposure_type"],
                       dropna=False)["measure_status"].apply(
        lambda s: "측정불가" if (s == "측정불가").any() else "측정").reset_index(
        name="measure_status")
    agg = agg.merge(status, on=["asof", "counterparty_id", "exposure_type"],
                    how="left")
    agg.loc[agg["measure_status"] == "측정불가", "measured_amount"] = np.nan
    agg["n_exposures"] = agg["n_exposures"].astype("int64")
    return _as_measure(agg), warns


# ---------------------------------------------------------------- look-through

LOOKTHROUGH = TableSpec(
    name="lex_lookthrough", korean="구조화상품 기초자산 관통", product="PRD-LIMIT",
    grain="기준일 × 구조화상품 × 귀속대상 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("structure_id", "string", "구조화상품", nullable=False),
        C("attributed_to", "string", "귀속 거래상대방", nullable=False),
        C("attribution_type", "string", "귀속 구분", nullable=False,
          allowed=ATTRIBUTION_TYPES),
        C("holding_amount", "float", "구조화상품 보유액", nullable=False,
          unit="KRW", min_value=0.0,
          note="구조화상품 단위 값이 귀속행마다 반복된다. 합산하면 중복이다"),
        C("attributed_amount", "float", "귀속액", nullable=False, unit="KRW",
          min_value=0.0),
        C("threshold_amount", "float", "관통 기준금액", nullable=False,
          unit="KRW", min_value=0.0,
          note="기본자본 × lookthrough_threshold (44.)"),
        C("method", "text", "귀속방법", nullable=False),
        C("is_additional_risk", "bool", "제3자 추가리스크 여부", nullable=False,
          note="47.은 구조화상품 익스포져와 '별도로' 산출하라고 정한다. "
               "따라서 보유액 보존식에 들어가지 않는다"),
        C("attribution_additive", "bool", "보유액 보존 여부", nullable=False,
          note="46.나 트렌치 산식은 (투자금액/트렌치)×min(기초자산, 트렌치)이며 "
               "합이 보유액을 넘을 수 있다. 선순위 트렌치가 어느 기초자산에서도 "
               "트렌치 규모까지 손실을 볼 수 있다는 가정에서 나온 보수적 과다 "
               "귀속이다. 그 행은 보존식 대상이 아니다"),
        C("citation", "text", "근거", nullable=False),
    ),
    primary_key=("asof", "structure_id", "attributed_to", "attribution_type"),
    note="관통 가능분은 실질 거래상대방에, 관통 불가분은 무명고객 버킷에 모인다. "
         "무명고객은 44.다 후단에 따라 전부 합산해 하나의 거래상대방으로 본다.",
)


def apply_lookthrough(
    measure: pd.DataFrame, structure_underlying: pd.DataFrame,
    structure_third_party: pd.DataFrame, setting: pd.DataFrame, *,
    tier1: float, framework: str = MEASURE_FRAMEWORK,
) -> tuple[pd.DataFrame, pd.DataFrame, list[ParamWarning]]:
    """집합투자·유동화·구조화상품의 기초자산 관통 (별표 3-12 제6절 제3목).

    `measure`에서 `exposure_type='구조화상품'` 행을 걷어내고 귀속 결과로 바꾼다.
    반환값은 (lex_lookthrough, 재구성된 lex_exposure_measure, 경고)다.

    `structure_underlying` 컬럼
      asof · structure_id · underlying_counterparty_id · underlying_notional
      structure_total       구조화상품 전체 규모 (46.가의 분모)
      can_look_through      관통 가능 여부 (44.다)
      seniority_equal       투자자 우선순위 동일 여부 (46.가 / 46.나)
      tranche_amount        은행이 투자한 트렌치의 총 금액 (46.나)

    **귀속 산식.** 46.가는 "은행이 보유한 구조화상품 비율 × 기초자산 가치"다.
    보유비율을 `holding / structure_total`로 두면 귀속액 합은
    `holding × (Σ 기초자산 / structure_total)`이 된다. 식별된 기초자산이 상품
    전체를 덮지 못하면 그 잔여는 관통되지 않은 부분이므로 무명고객으로 보낸다.
    이렇게 두면 귀속액 합이 항상 보유액과 같아지고, 보존식 검사가 실제로 위반을
    잡을 수 있다. 잔여를 버리면 익스포져가 소멸하고 검사도 통과해 버린다.
    """
    warns: list[ParamWarning] = []
    thr_pct = setting_value(setting, framework, "lookthrough_threshold")
    small_to_structure = setting_value(
        setting, framework, "lookthrough_small_to_structure")
    struct_rows = measure[measure["exposure_type"] == "구조화상품"]

    if thr_pct is None or small_to_structure is None:
        if len(struct_rows):
            warns.append(ParamWarning(
                "lex_lookthrough", "구조화상품",
                "lookthrough_threshold" if thr_pct is None
                else "lookthrough_small_to_structure",
                "관통 기준이 원장에 비어 있다. 관통하지 않고 46.다에 따라 "
                "명목금액을 구조화상품 자체 익스포져로 둔다"))
        return pd.DataFrame(columns=LOOKTHROUGH.column_names), measure, warns

    threshold = float(tier1) * thr_pct
    rows: list[dict] = []
    under = structure_underlying

    for _, s in struct_rows.iterrows():
        sid = str(s["counterparty_id"])
        holding = float(s["measured_amount"]) if pd.notna(
            s["measured_amount"]) else 0.0
        asof = s["asof"]
        parts = under[under["structure_id"] == sid]
        if parts.empty:
            warns.append(ParamWarning(
                "lex_lookthrough", sid, "structure_underlying",
                "기초자산 명세가 없다. 관통 가능 여부를 판단할 수 없어 44.다에 "
                "따라 처리한다"))
        can_lt = bool(parts["can_look_through"].iloc[0]) if len(parts) else False
        equal_sen = bool(parts["seniority_equal"].iloc[0]) if len(parts) else True
        total = float(parts["structure_total"].iloc[0]) if len(parts) else holding
        tranche = float(parts["tranche_amount"].iloc[0]) if len(parts) else 0.0

        base = dict(asof=asof, structure_id=sid, holding_amount=holding,
                    threshold_amount=threshold, is_additional_risk=False,
                    attribution_additive=True)

        if not can_lt:
            # 44.다 — 관통 불가. 0.25% 미만이면 상품 자체, 이상이면 무명고객.
            if holding < threshold:
                rows.append({**base, "attributed_to": sid,
                             "attribution_type": "구조화상품자체",
                             "attributed_amount": holding,
                             "method": "44.다 전단 관통 불가·기준 미만",
                             "citation": f"{_BASE} 44.다"})
            else:
                rows.append({**base, "attributed_to": UNKNOWN_CLIENT_ID,
                             "attribution_type": "무명고객",
                             "attributed_amount": holding,
                             "method": "44.다 후단 관통 불가·기준 이상",
                             "citation": f"{_BASE} 44.다"})
        elif holding < threshold:
            # 44.가 — 투자 총액이 기준 미만이면 상품 자체를 단일 거래상대방으로.
            rows.append({**base, "attributed_to": sid,
                         "attribution_type": "구조화상품자체",
                         "attributed_amount": holding,
                         "method": "44.가 투자총액 기준 미만",
                         "citation": f"{_BASE} 44.가 주6)"})
        else:
            share = holding / total if total > 0 else 0.0
            residual = holding
            small_bucket = 0.0
            for _, p in parts.sort_values("underlying_counterparty_id").iterrows():
                notional = float(p["underlying_notional"])
                if equal_sen:
                    # 46.가 — 보유비율 × 기초자산가치. 귀속액 합은 보유액을 넘지
                    # 않으며 식별되지 않은 부분이 잔여로 남는다.
                    amt = min(share * notional, residual)
                    residual -= amt
                    method = "46.가 보유비율 × 기초자산가치"
                else:
                    # 46.나 주7) — (투자금액/트렌치 합계) × min(기초자산, 트렌치).
                    # **이 산식은 합이 보유액을 넘을 수 있다.** 선순위 트렌치는
                    # 어느 기초자산이 부실해져도 트렌치 규모까지 손실을 볼 수
                    # 있다는 손실배분 가정에서 나온 식이므로 보수적으로 과다
                    # 귀속된다. 합을 보유액에 맞춰 깎으면 원문에 없는 상한을
                    # 만드는 것이고 감독 방향과 반대다. 깎지 않는다.
                    tr_share = holding / tranche if tranche > 0 else 0.0
                    amt = tr_share * min(notional, tranche)
                    base = {**base, "attribution_additive": False}
                    method = "46.나 주7) 트렌치 내 투자비율 × min(기초자산, 트렌치)"
                if amt <= 0:
                    continue
                if amt < threshold and small_to_structure >= 1.0:
                    # 44.나 단서 재량 — 소액 기초자산은 상품 자체로 인식한다.
                    small_bucket += amt
                    continue
                rows.append({**base, "attributed_to": str(
                    p["underlying_counterparty_id"]),
                    "attribution_type": "기초자산",
                    "attributed_amount": amt, "method": method,
                    "citation": f"{_BASE} 46."})
            if small_bucket > 0:
                rows.append({**base, "attributed_to": sid,
                             "attribution_type": "구조화상품자체",
                             "attributed_amount": small_bucket,
                             "method": "44.나 단서 기준 미만 기초자산 합산",
                             "citation": f"{_BASE} 44.나 단서"})
            if equal_sen and residual > _tol(holding):
                # 식별되지 않은 잔여는 관통되지 않은 부분이다. 버리지 않는다.
                rows.append({**base, "attributed_to": UNKNOWN_CLIENT_ID,
                             "attribution_type": "무명고객",
                             "attributed_amount": residual,
                             "method": "44.다 후단 기초자산 미식별 잔여",
                             "citation": f"{_BASE} 44.다"})

        # 47. — 제3자 추가리스크는 구조화상품 익스포져와 '별도로' 산출한다.
        tp = structure_third_party[structure_third_party["structure_id"] == sid]
        for _, t in tp.sort_values("third_party_id").iterrows():
            rows.append({**base, "is_additional_risk": True,
                         "attributed_to": str(t["third_party_id"]),
                         "attribution_type": "제3자추가리스크",
                         "attributed_amount": holding,
                         "method": f"47.다 제3자({t['role']})에게 각각 할당",
                         "citation": f"{_BASE} 47."})

    lt = pd.DataFrame(rows, columns=LOOKTHROUGH.column_names)
    if not lt.empty:
        # 같은 거래상대방이 한 구조화상품의 기초자산에 두 번 이상 들어올 수 있다.
        # 44.나는 그 익스포져를 "해당 거래상대방의 다른 직간접 익스포져와 합산"
        # 하라고 정하므로 원장 입도에서 합쳐야 한다. 합치지 않으면 기본키가
        # 깨지고 한도 판정이 같은 차주를 두 건으로 센다.
        lt = lt.groupby(
            ["asof", "structure_id", "attributed_to", "attribution_type"],
            as_index=False).agg(
            holding_amount=("holding_amount", "max"),
            attributed_amount=("attributed_amount", "sum"),
            threshold_amount=("threshold_amount", "max"),
            method=("method", "first"),
            is_additional_risk=("is_additional_risk", "any"),
            attribution_additive=("attribution_additive", "all"),
            citation=("citation", "first"))[list(LOOKTHROUGH.column_names)]

    # 측정 원장 재구성 — 구조화상품 원시 행을 귀속 결과로 대체한다.
    kept = measure[measure["exposure_type"] != "구조화상품"].copy()
    if lt.empty:
        return lt, _as_measure(kept), warns
    type_map = {"기초자산": "구조화상품_관통",
                "구조화상품자체": "구조화상품_자체",
                "무명고객": "무명고객",
                "제3자추가리스크": "구조화상품_제3자추가리스크"}
    new = lt.copy()
    new["exposure_type"] = new["attribution_type"].map(type_map)
    new = new.groupby(["asof", "attributed_to", "exposure_type"],
                      as_index=False).agg(
        measured_amount=("attributed_amount", "sum"),
        n_exposures=("structure_id", "nunique"),
        measure_basis=("citation", "first"))
    new = new.rename(columns={"attributed_to": "counterparty_id"})
    new["gross_amount"] = new["measured_amount"]
    new["deduction_amount"] = 0.0
    new["conversion_factor"] = np.nan
    new["measure_status"] = "측정"
    new["n_exposures"] = new["n_exposures"].astype("int64")
    out = pd.concat([kept, new[kept.columns]], ignore_index=True)
    out = out.groupby(["asof", "counterparty_id", "exposure_type"],
                      as_index=False).agg(
        gross_amount=("gross_amount", "sum"),
        deduction_amount=("deduction_amount", "sum"),
        conversion_factor=("conversion_factor", "mean"),
        measured_amount=("measured_amount", "sum"),
        measure_basis=("measure_basis", "first"),
        n_exposures=("n_exposures", "sum"),
        measure_status=("measure_status", "min"))
    return lt, _as_measure(out), warns


# ---------------------------------------------------------------- 대체 원장

SUBSTITUTION = TableSpec(
    name="lex_substitution", korean="신용위험경감 대체", product="PRD-LIMIT",
    grain="기준일 × 원 거래상대방 × 보장제공자 × 보장유형 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("original_counterparty_id", "string", "원 거래상대방", nullable=False),
        C("protection_provider_id", "string", "보장제공자", nullable=False),
        C("protection_type", "string", "보장유형", nullable=False,
          allowed=PROTECTION_TYPES),
        C("exposure_before", "float", "대체 전 익스포져", nullable=False,
          unit="KRW", min_value=0.0,
          note="7.가(1) CRM 미적용 기준 보고의 근거값"),
        C("covered_amount", "float", "보장 신청액", nullable=False, unit="KRW",
          min_value=0.0),
        C("substituted_amount", "float", "실제 차감액", nullable=False,
          unit="KRW", min_value=0.0,
          note="원 거래상대방 익스포져 잔액을 상한으로 한다. 초과 차감은 "
               "익스포져를 소멸시킨다"),
        C("provider_recognised_amount", "float", "보장제공자 인식액",
          nullable=True, unit="KRW",
          note="원칙은 차감액과 같다(23.). 34. 신용부도스왑 예외에서는 SA-CCR "
               "거래상대방신용위험 익스포져 금액이며 차감액과 다를 수 있다"),
        C("exposure_after", "float", "대체 후 익스포져", nullable=False,
          unit="KRW", min_value=0.0),
        C("maturity_mismatch_eligible", "bool", "만기불일치 적격", nullable=False,
          note="20.가 원만기 1년 이상 · 잔존만기 3개월 이상"),
        C("cds_exception_applied", "bool", "34. 신용부도스왑 예외 적용",
          nullable=False),
        C("eligibility_reason", "text", "적격성 판정 사유", nullable=False),
        C("citation", "text", "근거", nullable=False),
    ),
    primary_key=("asof", "original_counterparty_id", "protection_provider_id",
                 "protection_type"),
    note="23.은 대체를 강제한다. 대체로 보장제공자가 새로 한도를 넘길 수 있고 "
         "그것이 이 규제가 보려는 것이다. 대체 전후를 둘 다 남긴다.",
)


def apply_substitution(
    measure: pd.DataFrame, guarantee: pd.DataFrame, setting: pd.DataFrame, *,
    framework: str = MEASURE_FRAMEWORK,
) -> tuple[pd.DataFrame, pd.DataFrame, list[ParamWarning]]:
    """신용위험경감 대체 (별표 3-12 제4절).

    `guarantee` 컬럼
      asof · original_counterparty_id · exposure_type · protection_provider_id
      protection_type · covered_amount
      original_maturity_years · residual_maturity_years   (20.가 판정)
      provider_is_financial · reference_is_financial      (34. 판정)
      ccr_exposure_amount                                 (34. 적용 시 인식액)

    반환값은 (lex_substitution, 대체 후 측정 원장, 경고)다. 대체 후 원장에는
    보장제공자 쪽에 `신용위험경감_대체분` 유형 행이 새로 생긴다.

    **19. 적격 범위.** 무담보신용보장(보증·신용파생)과 금융자산담보만 인정한다.
    내부등급법 전용 담보는 이 프레임에 들어와도 인정하지 않는다.

    **20.가 만기불일치.** 경감요인의 원만기가 1년 미만이거나 잔존만기가 3개월
    미만이면 경감기법 자체를 적용할 수 없다. 차감액을 0으로 두고 사유를 남긴다.

    **34. 신용부도스왑 예외.** 보장제공자 또는 준거기업이 금융기관이 아니면
    보장제공자에게 할당하는 금액은 차감액이 아니라 SA-CCR 거래상대방신용위험
    익스포져 금액이다. 그 값이 비어 있으면 0으로 만들지 않고 인식액을 NULL로 두고
    경고를 남긴다. 0으로 만들면 보장제공자 쪽 익스포져가 사라진다.
    """
    warns: list[ParamWarning] = []
    del framework  # 대체 규칙은 별표 3-12가 정하며 체계별 계수를 쓰지 않는다

    # 원 거래상대방 × 유형별 잔액. 차감은 이 잔액을 상한으로 한다.
    remaining: dict[tuple, float] = {}
    for _, r in measure.iterrows():
        if r["measure_status"] != "측정":
            continue
        remaining[(r["asof"], r["counterparty_id"], r["exposure_type"])] = float(
            r["measured_amount"])
    before = dict(remaining)

    rows: list[dict] = []
    g = guarantee.copy()
    for col in ("provider_is_financial", "reference_is_financial"):
        if col not in g.columns:
            g[col] = True
    if "ccr_exposure_amount" not in g.columns:
        g["ccr_exposure_amount"] = np.nan
    # 결정론 — 처리 순서가 잔액 소진 결과를 바꾸므로 키로 정렬한다.
    g = g.sort_values(["asof", "original_counterparty_id", "exposure_type",
                       "protection_provider_id", "protection_type"])

    for _, q in g.iterrows():
        key = (q["asof"], q["original_counterparty_id"], q["exposure_type"])
        avail = remaining.get(key, 0.0)
        ptype = str(q["protection_type"])
        cover = float(q["covered_amount"])
        om = float(q["original_maturity_years"])
        rm = float(q["residual_maturity_years"])

        if ptype not in PROTECTION_TYPES:
            reason = f"19. 적격 경감기법이 아니다 ({ptype})"
            eligible = False
        elif om < 1.0 or rm < 0.25:
            reason = (f"20.가 미충족 — 원만기 {om:.2f}년(1년 이상 필요), "
                      f"잔존만기 {rm:.2f}년(3개월 이상 필요)")
            eligible = False
        elif avail <= 0:
            reason = "원 거래상대방의 해당 유형 익스포져 잔액이 없다"
            eligible = False
        else:
            reason = "19. 적격 · 20.가 만기요건 충족"
            eligible = True

        sub = min(cover, avail) if eligible else 0.0
        remaining[key] = avail - sub

        cds_exc = (ptype == "신용부도스왑"
                   and not bool(q["provider_is_financial"])
                   and not bool(q["reference_is_financial"]))
        if not eligible:
            provider_amt = 0.0
        elif cds_exc:
            ccr = q["ccr_exposure_amount"]
            if pd.isna(ccr):
                provider_amt = np.nan
                warns.append(ParamWarning(
                    "lex_substitution", str(q["protection_provider_id"]),
                    "ccr_exposure_amount",
                    "34. 신용부도스왑 예외 대상인데 SA-CCR 익스포져가 비어 있다. "
                    "0으로 만들지 않고 보장제공자 인식액을 비워 둔다"))
            else:
                provider_amt = float(ccr)
        else:
            provider_amt = sub

        rows.append({
            "asof": q["asof"],
            "original_counterparty_id": q["original_counterparty_id"],
            "protection_provider_id": q["protection_provider_id"],
            "protection_type": ptype,
            "exposure_before": before.get(key, 0.0),
            "covered_amount": cover,
            "substituted_amount": sub,
            "provider_recognised_amount": provider_amt,
            "exposure_after": remaining[key],
            "maturity_mismatch_eligible": bool(om >= 1.0 and rm >= 0.25),
            "cds_exception_applied": bool(cds_exc and eligible),
            "eligibility_reason": reason,
            "citation": (f"{_BASE} 19.·20.가·22.·23."
                         + (" · 34. 예외" if cds_exc else "")),
        })

    sub_df = pd.DataFrame(rows, columns=SUBSTITUTION.column_names)
    if not sub_df.empty:
        sub_df = sub_df.groupby(
            ["asof", "original_counterparty_id", "protection_provider_id",
             "protection_type"], as_index=False).agg(
            exposure_before=("exposure_before", "sum"),
            covered_amount=("covered_amount", "sum"),
            substituted_amount=("substituted_amount", "sum"),
            # 합계는 NaN을 건너뛴다. 인식액 미상이 0으로 둔갑하면 34. 예외에서
            # 보장제공자 익스포져가 조용히 사라진다. 하나라도 미상이면 미상이다.
            provider_recognised_amount=(
                "provider_recognised_amount",
                lambda s: np.nan if s.isna().any() else s.sum()),
            exposure_after=("exposure_after", "sum"),
            maturity_mismatch_eligible=("maturity_mismatch_eligible", "all"),
            cds_exception_applied=("cds_exception_applied", "any"),
            eligibility_reason=("eligibility_reason", "first"),
            citation=("citation", "first"))

    # 대체 후 측정 원장 재구성
    out = measure.copy()
    idx = {(r["asof"], r["counterparty_id"], r["exposure_type"]): i
           for i, r in out.iterrows()}
    for key, left in remaining.items():
        if key in idx:
            out.at[idx[key], "measured_amount"] = left
    if not sub_df.empty:
        add = sub_df.dropna(subset=["provider_recognised_amount"]).groupby(
            ["asof", "protection_provider_id"], as_index=False).agg(
            measured_amount=("provider_recognised_amount", "sum"),
            n_exposures=("protection_type", "size"))
        add = add.rename(columns={"protection_provider_id": "counterparty_id"})
        add = add[add["measured_amount"] > 0]
        if len(add):
            add["exposure_type"] = "신용위험경감_대체분"
            add["gross_amount"] = add["measured_amount"]
            add["deduction_amount"] = 0.0
            add["conversion_factor"] = np.nan
            add["measure_basis"] = (
                f"{_BASE} 23. 적격 경감기법 차감액을 경감기법 제공자에 대한 "
                f"익스포져로 인식")
            add["measure_status"] = "측정"
            add["n_exposures"] = add["n_exposures"].astype("int64")
            out = pd.concat([out, add[out.columns]], ignore_index=True)
            out = out.groupby(["asof", "counterparty_id", "exposure_type"],
                              as_index=False).agg(
                gross_amount=("gross_amount", "sum"),
                deduction_amount=("deduction_amount", "sum"),
                conversion_factor=("conversion_factor", "mean"),
                measured_amount=("measured_amount", "sum"),
                measure_basis=("measure_basis", "first"),
                n_exposures=("n_exposures", "sum"),
                measure_status=("measure_status", "min"))
    return sub_df, _as_measure(out), warns


# ---------------------------------------------------------------- 연결차주

CONNECTED_GROUP = TableSpec(
    name="lex_connected_group", korean="연계 거래상대방그룹", product="PRD-LIMIT",
    grain="기준일 × 그룹 × 거래상대방 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("group_id", "string", "그룹", nullable=False),
        C("counterparty_id", "string", "거래상대방", nullable=False),
        C("connection_basis", "string", "판정기준", nullable=False,
          allowed=CONNECTION_BASES),
        C("basis_detail", "text", "판정 근거", nullable=False),
        C("basis_metric", "float", "판정 지표값", nullable=True, unit="ratio",
          note="지배관계는 의결권 비율, 경제적 상호의존은 수입·지출 의존도"),
        C("linked_to", "string", "연결 상대", nullable=True),
        C("n_members", "int", "그룹 구성원 수", nullable=False, unit="count",
          min_value=1),
        C("interdep_review_required", "bool", "상호의존성 평가 의무 대상",
          nullable=False,
          note="10. 익스포져가 기본자본의 5%를 초과하는 단일 거래상대방"),
        C("citation", "text", "근거", nullable=False),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("asof", "group_id", "counterparty_id"),
    note="판정 결과는 그래프이므로 연결 성분 단위로 묶는다. 지배관계와 경제적 "
         "상호의존이 한 성분 안에서 섞일 수 있다.",
)


def _group_id(members: list[str]) -> str:
    """구성원 집합에서 결정론적 그룹 식별자를 만든다.

    파이썬 내장 hash()는 실행마다 솔트되므로 쓸 수 없다. 구성원 집합이 같으면
    언제 돌려도 같은 식별자가 나와야 시계열 비교가 성립한다.
    """
    key = "|".join(sorted(members))
    return "LEXG_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:12].upper()


def resolve_connected_groups(
    counterparty: pd.DataFrame, control_link: pd.DataFrame,
    interdep_link: pd.DataFrame, setting: pd.DataFrame, *,
    asof: str, exposure_by_counterparty: pd.Series, tier1: float,
    framework: str = MEASURE_FRAMEWORK,
) -> tuple[pd.DataFrame, list[ParamWarning]]:
    """연계 거래상대방그룹 판정 (별표 3-12 제2절).

    `control_link` 컬럼: parent_id · child_id · voting_share · control_basis ·
      excluded · exclusion_approved_by
    `interdep_link` 컬럼: counterparty_a · counterparty_b · criterion ·
      metric_value · excluded · exclusion_approved_by

    9. 단서는 **과반수 의결권 보유 시 자동으로 통제관계**로 본다. 그 외 기준은
    은행 평가이므로 `control_basis`가 무엇이었는지를 원장에 남긴다.
    11.은 기준에 해당해도 은행이 그룹이 아니라고 평가하면 제외할 수 있게 한다.
    판단이 개입하므로 `excluded=True` 행은 승인자 없이는 반영하지 않는다.
    50.은 청산 관련 중앙청산소 익스포져에 연계 개념을 적용하지 않으므로 적격·비적격
    중앙청산소는 항상 단독 그룹으로 둔다.
    """
    warns: list[ParamWarning] = []
    vote_thr = setting_value(setting, framework, "control_voting_threshold")
    rev_thr = setting_value(setting, framework, "interdep_revenue_ratio")
    review_thr = setting_value(
        setting, framework, "econ_interdep_review_threshold")
    if vote_thr is None:
        warns.append(ParamWarning(
            "lex_group", "지배관계", "control_voting_threshold",
            "자동인정 의결권 비율이 비어 있다. 자동인정 판정을 건너뛴다"))
    if rev_thr is None:
        warns.append(ParamWarning(
            "lex_group", "경제적상호의존", "interdep_revenue_ratio",
            "수입·지출 의존도 기준이 비어 있다. 해당 기준 판정을 건너뛴다"))

    nodes = sorted(set(counterparty["counterparty_id"].astype(str)))
    # 50. — 중앙청산소는 청산 관련 익스포져에 연계 개념을 적용하지 않는다.
    no_group = set(counterparty.loc[
        counterparty["counterparty_class"].isin(("적격CCP", "비적격CCP")),
        "counterparty_id"].astype(str))

    edges: list[tuple[str, str]] = []
    detail: dict[str, dict] = {}

    def _record(cp, basis, text, metric, other):
        if cp not in detail:
            detail[cp] = {"connection_basis": basis, "basis_detail": text,
                          "basis_metric": metric, "linked_to": other}

    cl = control_link.copy()
    for col in ("excluded", "exclusion_approved_by"):
        if col not in cl.columns:
            cl[col] = False if col == "excluded" else None
    for _, r in cl.sort_values(["parent_id", "child_id"]).iterrows():
        p, ch = str(r["parent_id"]), str(r["child_id"])
        if p in no_group or ch in no_group:
            continue
        if bool(r["excluded"]):
            if not r.get("exclusion_approved_by"):
                warns.append(ParamWarning(
                    "lex_group", f"{p}→{ch}", "exclusion_approved_by",
                    "11. 그룹 제외 판단에 승인자가 없다. 제외를 반영하지 않는다"))
            else:
                continue
        share = float(r["voting_share"]) if pd.notna(r["voting_share"]) else np.nan
        auto = (vote_thr is not None and pd.notna(share) and share > vote_thr)
        basis_name = str(r["control_basis"])
        text = (f"9. 단서 과반수 의결권 {share:.1%} 자동인정" if auto
                else f"9. {basis_name} (의결권 {share:.1%})"
                if pd.notna(share) else f"9. {basis_name}")
        edges.append((p, ch))
        _record(ch, "지배관계", text, share, p)
        _record(p, "지배관계", text, share, ch)

    il = interdep_link.copy()
    for col in ("excluded", "exclusion_approved_by"):
        if col not in il.columns:
            il[col] = False if col == "excluded" else None
    for _, r in il.sort_values(["counterparty_a", "counterparty_b"]).iterrows():
        a, b = str(r["counterparty_a"]), str(r["counterparty_b"])
        if a in no_group or b in no_group:
            continue
        if bool(r["excluded"]):
            if not r.get("exclusion_approved_by"):
                warns.append(ParamWarning(
                    "lex_group", f"{a}~{b}", "exclusion_approved_by",
                    "11. 그룹 제외 판단에 승인자가 없다. 제외를 반영하지 않는다"))
            else:
                continue
        metric = float(r["metric_value"]) if pd.notna(r["metric_value"]) else np.nan
        crit = str(r["criterion"])
        if crit == "수입지출50%":
            if rev_thr is None or pd.isna(metric) or metric < rev_thr:
                continue
            text = f"10.가 수입·지출 의존도 {metric:.1%} (기준 {rev_thr:.0%} 이상)"
        else:
            text = f"10. {crit}"
        edges.append((a, b))
        _record(a, "경제적상호의존", text, metric, b)
        _record(b, "경제적상호의존", text, metric, a)

    parent = {n: n for n in nodes}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in edges:
        if a not in parent or b not in parent:
            continue
        ra, rb = find(a), find(b)
        if ra != rb:
            # 사전순으로 작은 쪽을 뿌리로 — 병합 순서가 결과를 바꾸지 않게 한다.
            if rb < ra:
                ra, rb = rb, ra
            parent[rb] = ra

    comp: dict[str, list[str]] = {}
    for n in nodes:
        comp.setdefault(find(n), []).append(n)

    exp = exposure_by_counterparty
    review_amt = None if review_thr is None else float(tier1) * review_thr
    rows: list[dict] = []
    for members in comp.values():
        gid = _group_id(members)
        for cp in sorted(members):
            d = detail.get(cp, {"connection_basis": "단독",
                                "basis_detail": "연계 관계 없음",
                                "basis_metric": np.nan, "linked_to": None})
            e = float(exp.get(cp, 0.0))
            rows.append({
                "asof": asof, "group_id": gid, "counterparty_id": cp,
                "connection_basis": d["connection_basis"],
                "basis_detail": d["basis_detail"],
                "basis_metric": d["basis_metric"],
                "linked_to": d["linked_to"], "n_members": len(members),
                "interdep_review_required": bool(
                    review_amt is not None and e > review_amt),
                "citation": f"{_BASE} 8.·9.·10.·11.·50.",
                "evidence_status": "원문확인",
            })
    return pd.DataFrame(rows, columns=CONNECTED_GROUP.column_names), warns


# ---------------------------------------------------------------- 면제 원장

EXEMPTION = TableSpec(
    name="lex_exemption", korean="거액익스포져 면제", product="PRD-LIMIT",
    grain="기준일 × 거래상대방 × 면제유형 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("counterparty_id", "string", "거래상대방", nullable=False),
        C("exemption_type", "string", "면제유형", nullable=False,
          allowed=EXEMPTION_TYPES),
        C("measured_amount", "float", "차주 측정 총액", nullable=False,
          unit="KRW", min_value=0.0,
          note="차주 단위 값이 면제유형마다 반복된다. 합산하면 중복이다"),
        C("exempt_amount", "float", "면제액", nullable=False, unit="KRW",
          min_value=0.0),
        C("included_amount", "float", "산입액", nullable=False, unit="KRW",
          min_value=0.0, note="차주 단위 값이 반복된다"),
        C("reportable", "bool", "보고대상 여부", nullable=False,
          note="38. 면제해도 보고대상이다. 은행 간 일중 거래만 제외한다"),
        C("basis", "text", "면제 근거", nullable=False),
        C("citation", "text", "조문", nullable=False),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("asof", "counterparty_id", "exemption_type"),
    note="면제액을 조용히 빼면 7.가(4) '면제대상 중 기본자본 10% 이상 전건' 보고를 "
         "만들 수 없다. 면제한 금액과 근거가 보여야 감독당국이 검증한다.",
)

_EXEMPTION_CITATION = {
    "국가등": (f"{_BASE} 37.가(1) 위험가중치 0% 국가·중앙은행·지방자치단체·"
              f"공공기관·국제결제은행·국제개발은행", "원문확인"),
    "국가등_보증담보": (f"{_BASE} 37.가(2) 국가 등이 보증하거나 국가 등이 발행한 "
                    f"금융상품으로 담보된 익스포져", "원문확인"),
    "은행간_일중": (f"{_BASE} 37.가(3) 은행 간 지급결제 일중 거래", "원문확인"),
    "적격CCP_청산관련": (f"{_BASE} 37.가(4)·48. 적격 중앙청산소 청산관련 익스포져",
                     "원문확인"),
    "은행그룹내부": (f"{_BASE} 37.가(5) 주5) 금융지주회사(모은행 포함) 및 연결범위 "
                 f"내 금융회사", "원문확인"),
    "정부현물출자주식": (f"{_REG} 제26조제1항제6호 나목", "원문확인"),
    "농협중앙회_국가위탁": (f"{_REG} 제26조제1항제6호 다목", "원문확인"),
    "가계자금보증": (f"{_REG} 제26조제1항제6호 라목", "원문확인"),
    "금융위인정_공익목적": (f"{_REG} 제26조제1항제6호 마목", "원문확인"),
    "자본차감": (f"{_BASE} 13. 기본자본에서 공제된 익스포져는 다른 익스포져에 "
              f"가산하지 않는다", "원문확인"),
}


def apply_exemptions(
    measure: pd.DataFrame, exemption_rule: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series, list[ParamWarning]]:
    """면제·제외 적용 (별표 3-12 제6절 제1목 · 13.).

    `exemption_rule` 컬럼: asof · counterparty_id · exemption_type ·
      exempt_ratio (차주 측정액 대비 면제 비율) · basis

    반환값은 (lex_exemption, 차주별 산입액 Series, 경고)다.
    면제액은 차주 측정 총액을 상한으로 하며, 여러 면제유형이 겹치면 순차로
    남은 금액에서 뺀다. 면제액이 측정액을 넘어 익스포져가 음수가 되면 안 된다.
    """
    warns: list[ParamWarning] = []
    m = measure[measure["measure_status"] == "측정"]
    total = m.groupby(["asof", "counterparty_id"])["measured_amount"].sum()

    remaining = {k: float(v) for k, v in total.items()}
    rows: list[dict] = []
    er = exemption_rule.sort_values(
        ["asof", "counterparty_id", "exemption_type"])
    for _, r in er.iterrows():
        key = (r["asof"], str(r["counterparty_id"]))
        if key not in remaining:
            warns.append(ParamWarning(
                "lex_exemption", str(r["counterparty_id"]), "measured_amount",
                "면제규칙은 있는데 측정된 익스포져가 없다. 면제를 적용하지 않는다"))
            continue
        etype = str(r["exemption_type"])
        if etype not in EXEMPTION_TYPES:
            warns.append(ParamWarning(
                "lex_exemption", str(r["counterparty_id"]), "exemption_type",
                f"어휘에 없는 면제유형 {etype!r}. 면제를 적용하지 않는다"))
            continue
        amt = min(float(r["exempt_ratio"]) * float(total[key]), remaining[key])
        remaining[key] -= amt
        cite, ev = _EXEMPTION_CITATION[etype]
        rows.append({
            "asof": r["asof"], "counterparty_id": str(r["counterparty_id"]),
            "exemption_type": etype, "measured_amount": float(total[key]),
            "exempt_amount": amt, "included_amount": np.nan,
            # 38. — 면제해도 보고대상이며 은행 간 일중 거래만 제외한다.
            "reportable": etype != "은행간_일중",
            "basis": str(r.get("basis", "")) or cite,
            "citation": cite, "evidence_status": ev,
        })

    ex = pd.DataFrame(rows, columns=EXEMPTION.column_names)
    if not ex.empty:
        ex["included_amount"] = [
            remaining[(a, c)] for a, c in
            zip(ex["asof"], ex["counterparty_id"])]
    included = pd.Series(
        {k[1]: v for k, v in remaining.items()}, dtype=float, name="included")
    included.index.name = "counterparty_id"
    return ex, included, warns


# ---------------------------------------------------------------- 포지션 원장

POSITION = TableSpec(
    name="lex_position", korean="거액익스포져 한도 포지션", product="PRD-LIMIT",
    grain="기준일 × 체계 × 집계단위(그룹 또는 개별차주) 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("framework", "string", "체계", nullable=False, allowed=LEX_FRAMEWORKS),
        C("group_id", "string", "집계 키", nullable=False,
          note="거래상대방그룹 체계에서는 그룹, 개별차주 체계에서는 차주 식별자"),
        C("aggregation_unit", "string", "집계 단위", nullable=False,
          allowed=AGGREGATION_UNITS),
        C("n_members", "int", "구성원 수", nullable=False, unit="count",
          min_value=1),
        C("denominator_basis", "string", "분모 기준", nullable=False,
          allowed=DENOMINATOR_BASES),
        C("denominator_amount", "float", "분모", nullable=False, unit="KRW",
          min_value=0.0),
        C("exposure_pre_crm", "float", "CRM 미적용 익스포져", nullable=False,
          unit="KRW", min_value=0.0, note="7.가(1) 보고 근거값"),
        C("exposure_measured", "float", "CRM 적용 측정액", nullable=False,
          unit="KRW", min_value=0.0),
        C("exposure_exempt", "float", "면제액", nullable=False, unit="KRW",
          min_value=0.0),
        C("exposure_included", "float", "산입 익스포져", nullable=False,
          unit="KRW", min_value=0.0, note="7.가(2) 보고 근거값. 비율의 분자"),
        C("ratio", "float", "비율", nullable=False, unit="ratio", min_value=0.0),
        C("counterparty_class", "string", "상대방 구분", nullable=False,
          allowed=COUNTERPARTY_CLASSES),
        C("limit_pct", "float", "한도율", nullable=False, unit="ratio",
          min_value=0.0),
        C("limit_amount", "float", "한도금액", nullable=False, unit="KRW",
          min_value=0.0),
        C("utilisation", "float", "소진율", nullable=False, unit="ratio",
          min_value=0.0),
        C("headroom", "float", "잔여한도", nullable=False, unit="KRW"),
        C("reportable", "bool", "보고대상", nullable=False),
        C("reportable_pre_crm", "bool", "CRM 미적용 기준 보고대상", nullable=False),
        C("breach", "bool", "한도 위반", nullable=False),
        C("limit_citation", "text", "한도 근거", nullable=False),
        C("measure_evidence_status", "string", "측정근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS,
          note="은행법 §35의 '신용공여' 범위는 시행령이 정하는데 원문을 확보하지 "
               "못했다. 별표 3-12 측정액을 대용한 계정은 '미확인'이다"),
    ),
    primary_key=("asof", "framework", "group_id"),
    foreign_keys=(FK(("asof", "framework"), "lex_setting", ("asof", "framework")),),
    note="체계마다 분모와 집계단위가 다르므로 체계가 입도에 들어간다. 값이 비어 "
         "있는 체계(BCBS_d283_2014)는 행이 생기지 않는다.",
)


def compute_positions(
    included: pd.Series, pre_crm: pd.Series, measured: pd.Series,
    exempt: pd.Series, group: pd.DataFrame, counterparty: pd.DataFrame,
    setting: pd.DataFrame, *, asof: str, tier1: float, own_funds: float,
    frameworks: tuple[str, ...] = LEX_FRAMEWORKS,
) -> tuple[pd.DataFrame, list[ParamWarning]]:
    """체계별 한도 판정. 분모·한도율·집계단위를 전부 원장에서 읽는다."""
    warns: list[ParamWarning] = []
    cls = dict(zip(counterparty["counterparty_id"].astype(str),
                   counterparty["counterparty_class"].astype(str)))
    members = group.groupby("group_id")["counterparty_id"].apply(
        lambda s: sorted(set(s.astype(str)))).to_dict()

    rows: list[dict] = []
    for fw in frameworks:
        limit_general = setting_value(setting, fw, "limit_general")
        if limit_general is None:
            warns.append(ParamWarning(
                "lex_position", fw, "limit_general",
                "한도율이 원장에 비어 있다. 이 체계는 산출하지 않는다"))
            continue
        rep_thr = setting_value(setting, fw, "reporting_threshold")
        if rep_thr is None:
            warns.append(ParamWarning(
                "lex_position", fw, "reporting_threshold",
                "보고기준이 원장에 비어 있다. 이 체계는 산출하지 않는다"))
            continue
        limit_sib = setting_value(setting, fw, "limit_sib", required=False)
        limit_gg = setting_value(setting, fw, "limit_gsib_to_gsib",
                                 required=False)
        is_gsib = setting_value(setting, fw, "bank_is_gsib", required=False)
        basis = denominator_basis(setting, fw)
        unit = _aggregation_unit(setting, fw)
        denom = float(tier1) if basis == "tier1" else float(own_funds)
        if denom <= 0:
            warns.append(ParamWarning(
                "lex_position", fw, basis,
                "분모가 0 이하다. 비율을 산출하지 않는다"))
            continue
        # 은행법 §35의 신용공여 범위는 시행령이 정하는데 원문을 확보하지 못했다.
        scope_row = setting[(setting["framework"] == fw)
                            & (setting["param_code"] == "credit_extension_scope")]
        measure_ev = (str(scope_row["evidence_status"].iloc[0])
                      if len(scope_row) else "원문확인")

        if unit == "개별차주":
            units = {cp: [cp] for cp in included.index.astype(str)}
        else:
            units = members

        for key, mem in units.items():
            inc = float(sum(included.get(c, 0.0) for c in mem))
            pre = float(sum(pre_crm.get(c, 0.0) for c in mem))
            mea = float(sum(measured.get(c, 0.0) for c in mem))
            exm = float(sum(exempt.get(c, 0.0) for c in mem))
            classes = {cls.get(c, "일반") for c in mem}
            if "무명고객" in classes:
                cp_class = "무명고객"
            elif "G-SIB" in classes:
                cp_class = "G-SIB"
            elif "D-SIB" in classes:
                cp_class = "D-SIB"
            else:
                cp_class = sorted(classes)[0] if classes else "일반"

            limit = limit_general
            cite = f"{_REG}·{_ACT} 일반 한도율"
            if cp_class == "G-SIB" and limit_gg is not None and (
                    is_gsib is not None and is_gsib >= 1.0):
                limit = limit_gg
                cite = f"{_REG} 제26조의2제10항 G-SIB 간 한도"
            elif cp_class in ("G-SIB", "D-SIB") and limit_sib is not None:
                limit = limit_sib
                cite = f"{_REG} 제26조제1항제6호 단서 D-SIB·G-SIB 한도"

            ratio = inc / denom
            limit_amt = limit * denom
            rows.append({
                "asof": asof, "framework": fw, "group_id": str(key),
                "aggregation_unit": unit, "n_members": len(mem),
                "denominator_basis": basis, "denominator_amount": denom,
                "exposure_pre_crm": pre, "exposure_measured": mea,
                "exposure_exempt": exm, "exposure_included": inc,
                "ratio": ratio, "counterparty_class": cp_class,
                "limit_pct": limit, "limit_amount": limit_amt,
                "utilisation": inc / limit_amt if limit_amt > 0 else np.inf,
                "headroom": limit_amt - inc,
                "reportable": bool(ratio >= rep_thr),
                "reportable_pre_crm": bool(pre / denom >= rep_thr),
                "breach": bool(inc > limit_amt),
                "limit_citation": cite,
                "measure_evidence_status": measure_ev,
            })
    out = pd.DataFrame(rows, columns=POSITION.column_names)
    if not out.empty:
        out["n_members"] = out["n_members"].astype("int64")
    return out.reset_index(drop=True), warns


# ---------------------------------------------------------------- 총액 원장

AGGREGATE = TableSpec(
    name="lex_aggregate", korean="거액신용공여 총액", product="PRD-LIMIT",
    grain="기준일 × 체계 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("framework", "string", "체계", nullable=False, allowed=LEX_FRAMEWORKS),
        C("denominator_basis", "string", "분모 기준", nullable=False,
          allowed=DENOMINATOR_BASES),
        C("denominator_amount", "float", "분모", nullable=False, unit="KRW",
          min_value=0.0),
        C("large_credit_threshold_pct", "float", "거액 판정기준", nullable=False,
          unit="ratio", min_value=0.0),
        C("n_large_credits", "int", "거액 건수", nullable=False, unit="count",
          min_value=0),
        C("aggregate_numerator", "float", "총액 분자", nullable=False, unit="KRW",
          min_value=0.0,
          note="전체 합이 아니라 분모의 10%를 초과하는 건들의 합이다 (은행법 §35④)"),
        C("aggregate_ratio", "float", "분모 대비 비율", nullable=False,
          unit="ratio", min_value=0.0),
        C("aggregate_limit_pct", "float", "총액한도", nullable=True,
          unit="multiple",
          note="NULL은 그 체계에 총액한도가 없다는 뜻이다 (감독규정 §26)"),
        C("aggregate_limit_amount", "float", "총액한도 금액", nullable=True,
          unit="KRW"),
        C("aggregate_utilisation", "float", "총액한도 소진율", nullable=True,
          unit="ratio"),
        C("breach", "bool", "총액한도 위반", nullable=False),
        C("citation", "text", "근거", nullable=False),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("asof", "framework"),
    note="은행법 §35④의 총액한도. 감독규정 §26에는 총액한도가 없으므로 그 계정은 "
         "한도 컬럼이 NULL이고 위반 판정을 하지 않는다.",
)


def compute_aggregate(
    positions: pd.DataFrame, setting: pd.DataFrame, *, asof: str,
) -> tuple[pd.DataFrame, list[ParamWarning]]:
    """거액신용공여 총액한도 (은행법 §35④).

    **분자는 전체 합이 아니다.** "자기자본의 100분의 10을 초과하는 거액 신용공여인
    경우 그 총합계액"이므로 기준 초과 건들만 더한다. 전체 합을 쓰면 소진율이
    과대계상되고 한도가 실제보다 빡빡해 보인다.
    """
    warns: list[ParamWarning] = []
    rows: list[dict] = []
    for fw in sorted(set(positions["framework"])) if len(positions) else []:
        p = positions[positions["framework"] == fw]
        thr = setting_value(setting, fw, "reporting_threshold")
        if thr is None:
            warns.append(ParamWarning(
                "lex_aggregate", fw, "reporting_threshold",
                "거액 판정기준이 비어 있다. 총액을 산출하지 않는다"))
            continue
        agg_limit = setting_value(setting, fw, "aggregate_limit", required=False)
        denom = float(p["denominator_amount"].iloc[0])
        basis = str(p["denominator_basis"].iloc[0])
        large = p[p["ratio"] > thr]
        numer = float(large["exposure_included"].sum())
        limit_amt = None if agg_limit is None else agg_limit * denom
        rows.append({
            "asof": asof, "framework": fw, "denominator_basis": basis,
            "denominator_amount": denom, "large_credit_threshold_pct": thr,
            "n_large_credits": int(len(large)), "aggregate_numerator": numer,
            "aggregate_ratio": numer / denom if denom > 0 else np.inf,
            "aggregate_limit_pct": np.nan if agg_limit is None else agg_limit,
            "aggregate_limit_amount": np.nan if limit_amt is None else limit_amt,
            "aggregate_utilisation": (
                np.nan if limit_amt is None else numer / limit_amt),
            "breach": bool(limit_amt is not None and numer > limit_amt),
            "citation": (f"{_ACT} 제35조제4항 '자기자본의 100분의 10을 초과하는 "
                         f"거액 신용공여인 경우 그 총합계액은 자기자본의 5배를 "
                         f"초과할 수 없다'" if agg_limit is not None
                         else f"{_REG} 제26조는 총액한도를 두지 않는다"),
            "evidence_status": "원문확인" if agg_limit is not None
                               else "재량·미규정",
        })
    out = pd.DataFrame(rows, columns=AGGREGATE.column_names)
    if not out.empty:
        out["n_large_credits"] = out["n_large_credits"].astype("int64")
    return out, warns


LEX_TABLES = (SETTING, EXPOSURE_MEASURE, LOOKTHROUGH, SUBSTITUTION,
              CONNECTED_GROUP, EXEMPTION, POSITION, AGGREGATE)


# ---------------------------------------------------------------- 자체 검사

def _pass(report, name, detail, metric=0.0):
    report.add(ConsistencyCheck(name, "PASS", detail, metric=float(metric)))


def _fail(report, name, detail, metric):
    report.add(ConsistencyCheck(name, "FAIL", detail, metric=float(metric)))


def check_substitution_conservation(
    measure_pre: pd.DataFrame, measure_post: pd.DataFrame,
    substitution: pd.DataFrame, report: ValidationReport,
) -> None:
    """대체 전후 총 익스포져 보존. 대체는 이전이지 소멸이 아니다.

    Σ(대체 후) = Σ(대체 전) + Σ(보장제공자 인식액 − 차감액)
    괄호 안은 34. 신용부도스왑 예외에서만 0이 아니다.

    FAIL 조건: 엔진이 원 거래상대방에서 차감만 하고 23.에 따른 보장제공자 가산을
    빠뜨리면 좌변이 우변보다 차감액만큼 작아진다. 대체를 "익스포져 감소"로 잘못
    구현하면 정확히 이 형태로 드러난다.
    """
    pre = float(measure_pre.loc[measure_pre["measure_status"] == "측정",
                                "measured_amount"].sum())
    post = float(measure_post.loc[measure_post["measure_status"] == "측정",
                                  "measured_amount"].sum())
    if substitution.empty:
        delta = 0.0
    else:
        s = substitution
        delta = float((s["provider_recognised_amount"].fillna(0.0)
                       - s["substituted_amount"]).sum())
    gap = post - (pre + delta)
    if abs(gap) > _tol(pre):
        _fail(report, "lex_substitution_conservation",
              f"대체 전후 총 익스포져가 보존되지 않는다. 대체 전 {pre:,.0f} "
              f"+ 예외조정 {delta:,.0f} ≠ 대체 후 {post:,.0f} (차 {gap:,.0f} KRW)",
              abs(gap))
    else:
        _pass(report, "lex_substitution_conservation",
              f"대체 전 {pre:,.0f} KRW = 대체 후 {post:,.0f} KRW "
              f"(34. 예외조정 {delta:,.0f})")


def check_exemption_conservation(
    exemption: pd.DataFrame, measure_post: pd.DataFrame,
    report: ValidationReport,
) -> None:
    """면제액 + 산입액 = 측정 총액. 그리고 측정 총액이 측정 원장과 일치하는가.

    FAIL 조건: 면제를 차주 측정액보다 크게 잡아 산입액이 음수가 되거나, 여러
    면제유형이 겹칠 때 순차 차감을 하지 않아 같은 금액을 두 번 빼면 좌변이
    측정 총액을 넘는다.
    """
    if exemption.empty:
        _pass(report, "lex_exemption_conservation", "면제 행이 없다")
        return
    g = exemption.groupby(["asof", "counterparty_id"], as_index=False).agg(
        exempt=("exempt_amount", "sum"),
        measured=("measured_amount", "max"),
        included=("included_amount", "max"))
    g["gap"] = g["exempt"] + g["included"] - g["measured"]
    bad = g[g["gap"].abs() > _tol(g["measured"])]
    if len(bad):
        worst = float(bad["gap"].abs().max())
        _fail(report, "lex_exemption_conservation",
              f"차주 {len(bad)}건에서 면제액 + 산입액 ≠ 측정 총액 "
              f"(최대 {worst:,.0f} KRW)", worst)
        return
    # 원장 간 대사 — 면제 원장의 측정 총액이 측정 원장 합계와 같아야 한다.
    m = measure_post[measure_post["measure_status"] == "측정"].groupby(
        ["asof", "counterparty_id"])["measured_amount"].sum()
    joined = g.set_index(["asof", "counterparty_id"]).join(
        m.rename("ledger"), how="left")
    joined["ledger"] = joined["ledger"].fillna(0.0)
    off = joined[(joined["measured"] - joined["ledger"]).abs()
                 > _tol(joined["ledger"])]
    if len(off):
        worst = float((off["measured"] - off["ledger"]).abs().max())
        _fail(report, "lex_exemption_conservation",
              f"면제 원장의 측정 총액이 측정 원장과 다르다 {len(off)}건 "
              f"(최대 {worst:,.0f} KRW)", worst)
    else:
        _pass(report, "lex_exemption_conservation",
              f"차주 {len(g)}건 전건 면제액 + 산입액 = 측정 총액이고 "
              f"측정 원장과 대사된다")


def check_lookthrough_conservation(
    lookthrough: pd.DataFrame, report: ValidationReport,
) -> None:
    """look-through 귀속액 합 = 관통 대상 총액 (미상 버킷 포함).

    두 부류를 보존식에서 뺀다. 47. 제3자 추가리스크는 원문이 "별도로" 산출하라고
    정하고, 46.나 트렌치 산식은 합이 보유액을 넘도록 설계돼 있다. 둘 다 등식이
    성립하지 않는 것이 정상이므로 등식으로 재면 상시 FAIL이 나서 검사가 죽는다.
    제외한 건수를 detail에 적어 무엇을 재지 않았는지 보이게 한다.

    FAIL 조건: 기초자산이 상품 전체를 덮지 못할 때 잔여를 무명고객으로 보내지
    않고 버리면 귀속합이 보유액보다 작아진다. 익스포져가 조용히 소멸하는 결함이며
    관통 가능하고 기초자산이 전부 식별된 상품만 있는 표본에서는 드러나지 않는다.
    """
    if lookthrough.empty:
        _pass(report, "lex_lookthrough_conservation", "관통 대상 구조화상품이 없다")
        return
    lt = lookthrough[~lookthrough["is_additional_risk"]]
    n_all = int(lt["structure_id"].nunique())
    lt = lt[lt["attribution_additive"]]
    if lt.empty:
        _pass(report, "lex_lookthrough_conservation",
              f"보존식 대상 구조화상품이 없다 (전건 46.나 트렌치, {n_all}건)")
        return
    g = lt.groupby(["asof", "structure_id"], as_index=False).agg(
        attributed=("attributed_amount", "sum"),
        holding=("holding_amount", "max"))
    g["gap"] = g["attributed"] - g["holding"]
    bad = g[g["gap"].abs() > _tol(g["holding"])]
    if len(bad):
        worst = float(bad["gap"].abs().max())
        _fail(report, "lex_lookthrough_conservation",
              f"구조화상품 {len(bad)}건에서 귀속액 합 ≠ 보유액 "
              f"(최대 {worst:,.0f} KRW)", worst)
    else:
        _pass(report, "lex_lookthrough_conservation",
              f"구조화상품 {len(g)}건 전건 귀속액 합 = 보유액 "
              f"(46.나 트렌치 {n_all - len(g)}건은 산식상 비가산이라 제외)")


def check_group_additivity(
    positions: pd.DataFrame, group: pd.DataFrame, included: pd.Series,
    report: ValidationReport,
) -> None:
    """연결그룹 익스포져 합 = 소속 차주 익스포져 합.

    FAIL 조건: 그룹 판정에서 한 차주가 두 그룹에 들어가거나(연결 성분 계산 오류)
    어느 그룹에도 안 들어가면 그룹 합계와 차주 합계가 어긋난다.
    """
    grp = positions[positions["aggregation_unit"] == "거래상대방그룹"]
    if grp.empty:
        _pass(report, "lex_group_additivity", "그룹 단위 체계가 없다")
        return
    member_sum = group.assign(
        amt=group["counterparty_id"].astype(str).map(
            lambda c: float(included.get(c, 0.0)))).groupby(
        "group_id")["amt"].sum()
    bad_rows = 0
    worst = 0.0
    for fw in sorted(set(grp["framework"])):
        p = grp[grp["framework"] == fw].set_index("group_id")
        joined = p[["exposure_included"]].join(member_sum.rename("members"),
                                               how="outer").fillna(0.0)
        d = (joined["exposure_included"] - joined["members"]).abs()
        over = d[d > _tol(joined["members"])]
        bad_rows += len(over)
        if len(over):
            worst = max(worst, float(over.max()))
    if bad_rows:
        _fail(report, "lex_group_additivity",
              f"그룹 {bad_rows}건에서 그룹 익스포져 ≠ 소속 차주 합 "
              f"(최대 {worst:,.0f} KRW)", worst)
    else:
        _pass(report, "lex_group_additivity",
              f"그룹 {member_sum.size}건 전건 그룹 익스포져 = 소속 차주 합")


def check_reporting_completeness(
    positions: pd.DataFrame, setting: pd.DataFrame, report: ValidationReport,
) -> None:
    """보고기준(기본자본 10%) 이상 건이 전부 lex_position에 있고 보고대상으로
    표시돼 있는가 (별표 3-12 7.가(1)(2)).

    비율을 원장에서 다시 계산해 보고대상 집합과 대조한다.

    FAIL 조건: 보고 플래그를 '>' 로 잘못 써서 정확히 10%인 건을 빠뜨리거나,
    보고대상만 필터해 원장에 담아 기준 이상인 건이 원장에서 사라지면 잡힌다.
    """
    if positions.empty:
        _pass(report, "lex_reporting_completeness", "포지션 행이 없다")
        return
    missing = 0
    detail = []
    for fw in sorted(set(positions["framework"])):
        thr = setting_value(setting, fw, "reporting_threshold")
        if thr is None:
            continue
        p = positions[positions["framework"] == fw]
        expect = p[p["ratio"] >= thr - _tol(thr)]
        flagged = expect[~expect["reportable"]]
        missing += len(flagged)
        if len(flagged):
            detail.append(f"{fw} {len(flagged)}건")
        # CRM 미적용 기준 보고(7.가(1))도 같은 방식으로 표시돼야 한다.
        denom = p["denominator_amount"].iloc[0]
        pre_ratio = p["exposure_pre_crm"] / denom if denom > 0 else p["ratio"] * 0
        pre_missing = p[(pre_ratio >= thr - _tol(thr)) & ~p["reportable_pre_crm"]]
        missing += len(pre_missing)
        if len(pre_missing):
            detail.append(f"{fw} CRM미적용 {len(pre_missing)}건")
    if missing:
        _fail(report, "lex_reporting_completeness",
              f"보고기준 이상인데 보고대상으로 표시되지 않은 건이 있다 "
              f"({', '.join(detail)})", missing)
    else:
        _pass(report, "lex_reporting_completeness",
              f"포지션 {len(positions)}행 전건 보고대상 표시가 기준과 일치한다")


def check_aggregate_numerator(
    aggregate: pd.DataFrame, positions: pd.DataFrame, report: ValidationReport,
) -> None:
    """총액한도 분자가 "분모의 10%를 초과하는 건들의 합"인가 (은행법 §35④).

    FAIL 조건: 분자에 전체 포지션 합을 넣으면 기준 이하 건까지 들어가 분자가
    커진다. 흔한 오독이고 총액 소진율을 과대계상한다.
    """
    if aggregate.empty:
        _pass(report, "lex_aggregate_numerator", "총액 행이 없다")
        return
    bad = []
    for _, a in aggregate.iterrows():
        p = positions[positions["framework"] == a["framework"]]
        thr = float(a["large_credit_threshold_pct"])
        expect = float(p.loc[p["ratio"] > thr, "exposure_included"].sum())
        got = float(a["aggregate_numerator"])
        if abs(got - expect) > _tol(expect):
            bad.append((a["framework"], got, expect))
    if bad:
        worst = max(abs(g - e) for _, g, e in bad)
        names = ", ".join(f"{f} 분자 {g:,.0f} ≠ {e:,.0f}" for f, g, e in bad)
        _fail(report, "lex_aggregate_numerator",
              f"총액 분자가 기준 초과 건들의 합이 아니다 ({names})", worst)
    else:
        _pass(report, "lex_aggregate_numerator",
              f"체계 {len(aggregate)}건 전건 분자 = 기준 초과 건들의 합")


def check_group_ratio_dominance(
    positions: pd.DataFrame, group: pd.DataFrame, report: ValidationReport,
) -> None:
    """그룹 비율이 소속 개별차주 비율의 최대값 이상인가.

    같은 분모를 쓰는 그룹 체계와 개별차주 체계를 짝지어 본다. 국내에서는
    은행법 §35① 동일차주(그룹)와 §35③ 동일인(개별)이 둘 다 자기자본 분모다.

    FAIL 조건: 그룹 집계에서 구성원을 빠뜨리거나 그룹 단계에서 상계·차감을
    한 번 더 하면 그룹 비율이 최대 구성원 비율보다 작아진다. 익스포져는 음수가
    될 수 없으므로 정상 산출에서는 일어날 수 없는 관계다.
    """
    grp = positions[positions["aggregation_unit"] == "거래상대방그룹"]
    ind = positions[positions["aggregation_unit"] == "개별차주"]
    if grp.empty or ind.empty:
        _pass(report, "lex_group_ratio_dominance",
              "그룹·개별 체계 짝이 없어 비교하지 않는다")
        return
    membership = group.groupby("group_id")["counterparty_id"].apply(
        lambda s: sorted(set(s.astype(str)))).to_dict()
    bad = 0
    worst = 0.0
    for basis in sorted(set(grp["denominator_basis"])):
        gp = grp[grp["denominator_basis"] == basis]
        ip = ind[ind["denominator_basis"] == basis]
        if ip.empty:
            continue
        ratio = dict(zip(ip["group_id"].astype(str), ip["ratio"]))
        for _, r in gp.iterrows():
            mem = membership.get(str(r["group_id"]), [])
            mx = max((ratio.get(c, 0.0) for c in mem), default=0.0)
            if float(r["ratio"]) < mx - _tol(mx):
                bad += 1
                worst = max(worst, mx - float(r["ratio"]))
    if bad:
        _fail(report, "lex_group_ratio_dominance",
              f"그룹 {bad}건에서 그룹 비율이 개별차주 비율 최대값보다 작다 "
              f"(최대 차 {worst:.4%})", worst)
    else:
        _pass(report, "lex_group_ratio_dominance",
              "전건 그룹 비율 ≥ 소속 개별차주 비율 최대값")


def run_lex_checks(
    measure_pre: pd.DataFrame, measure_post: pd.DataFrame,
    substitution: pd.DataFrame, exemption: pd.DataFrame,
    lookthrough: pd.DataFrame, group: pd.DataFrame, positions: pd.DataFrame,
    aggregate: pd.DataFrame, included: pd.Series, setting: pd.DataFrame,
    report: ValidationReport | None = None,
) -> ValidationReport:
    """거액익스포져 자체 정합성 검사 7종 (2선)."""
    rep = report or ValidationReport()
    check_substitution_conservation(measure_pre, measure_post, substitution, rep)
    check_exemption_conservation(exemption, measure_post, rep)
    check_lookthrough_conservation(lookthrough, rep)
    check_group_additivity(positions, group, included, rep)
    check_reporting_completeness(positions, setting, rep)
    check_aggregate_numerator(aggregate, positions, rep)
    check_group_ratio_dominance(positions, group, rep)
    return rep


# ---------------------------------------------------------------- 진입점

@dataclass
class LexInputs:
    """거액익스포져 산출 입력 묶음."""
    counterparty: pd.DataFrame
    universe: pd.DataFrame
    guarantee: pd.DataFrame
    control_link: pd.DataFrame
    interdep_link: pd.DataFrame
    exemption_rule: pd.DataFrame
    structure_underlying: pd.DataFrame
    structure_third_party: pd.DataFrame


@dataclass
class LexResult:
    setting: pd.DataFrame
    exposure_measure: pd.DataFrame          # 대체·면제 반영 후 (헤드라인)
    exposure_measure_pre_crm: pd.DataFrame  # 대체 전 (7.가(1) 보고 근거)
    lookthrough: pd.DataFrame
    substitution: pd.DataFrame
    connected_group: pd.DataFrame
    exemption: pd.DataFrame
    position: pd.DataFrame
    aggregate: pd.DataFrame
    warnings: list[ParamWarning]
    report: ValidationReport
    summary: dict


def compute_large_exposure(
    inputs: LexInputs, setting: pd.DataFrame, *, asof: str,
    tier1: float, own_funds: float,
    measure_framework: str = MEASURE_FRAMEWORK,
) -> LexResult:
    """거액익스포져 전체 산출. 측정 → 관통 → 대체 → 면제 → 그룹 → 한도 → 총액."""
    warns: list[ParamWarning] = []

    measure, w = measure_exposures(inputs.universe, setting,
                                   framework=measure_framework)
    warns += w
    lookthrough, measure, w = apply_lookthrough(
        measure, inputs.structure_underlying, inputs.structure_third_party,
        setting, tier1=tier1, framework=measure_framework)
    warns += w
    measure_pre = measure.copy()

    substitution, measure_post, w = apply_substitution(
        measure, inputs.guarantee, setting, framework=measure_framework)
    warns += w
    exemption, included, w = apply_exemptions(measure_post, inputs.exemption_rule)
    warns += w

    ok = measure_post["measure_status"] == "측정"
    measured = measure_post[ok].groupby("counterparty_id")[
        "measured_amount"].sum()
    pre_ok = measure_pre["measure_status"] == "측정"
    pre_crm = measure_pre[pre_ok].groupby("counterparty_id")[
        "measured_amount"].sum()
    exempt = (exemption.groupby("counterparty_id")["exempt_amount"].sum()
              if not exemption.empty
              else pd.Series(dtype=float, name="exempt_amount"))
    # apply_exemptions는 측정된 모든 차주를 담아 돌려준다. 면제규칙이 없는 차주는
    # 측정액이 그대로 산입액이므로 별도 채움이 필요 없다.

    group, w = resolve_connected_groups(
        inputs.counterparty, inputs.control_link, inputs.interdep_link,
        setting, asof=asof, exposure_by_counterparty=measured, tier1=tier1,
        framework=measure_framework)
    warns += w

    position, w = compute_positions(
        included, pre_crm, measured, exempt, group, inputs.counterparty,
        setting, asof=asof, tier1=tier1, own_funds=own_funds)
    warns += w
    aggregate, w = compute_aggregate(position, setting, asof=asof)
    warns += w

    report = run_lex_checks(
        measure_pre, measure_post, substitution, exemption, lookthrough,
        group, position, aggregate, included, setting)

    head = position[position["framework"] == "감독규정26조_기본자본"]
    summary = {
        "n_counterparties": int(measured.size),
        "n_groups": int(group["group_id"].nunique()) if len(group) else 0,
        "n_multi_member_groups": int(
            (group.drop_duplicates("group_id")["n_members"] > 1).sum())
        if len(group) else 0,
        "n_reportable": int(head["reportable"].sum()) if len(head) else 0,
        "n_breach": int(head["breach"].sum()) if len(head) else 0,
        "max_ratio": float(head["ratio"].max()) if len(head) else 0.0,
        "total_exempt": float(exemption["exempt_amount"].sum())
        if len(exemption) else 0.0,
        "total_substituted": float(substitution["substituted_amount"].sum())
        if len(substitution) else 0.0,
        "n_warnings": len(warns),
        "checks": report.summary(),
    }
    return LexResult(
        setting=setting, exposure_measure=measure_post,
        exposure_measure_pre_crm=measure_pre, lookthrough=lookthrough,
        substitution=substitution, connected_group=group, exemption=exemption,
        position=position, aggregate=aggregate, warnings=warns, report=report,
        summary=summary)


# ---------------------------------------------------------------- 합성 입력

def build_lex_inputs(
    portfolio: pd.DataFrame, *, asof: str, tier1: float, seed: int = 42,
) -> LexInputs:
    """합성 입력 묶음. 지배관계·상호의존 관계를 실제로 만들어 1:1이 아닌 군집이
    나오게 하고, 대체로 보장제공자가 한도를 넘길 수 있게 보장을 집중시킨다.

    난수는 전용 스트림(`default_rng(seed + offset)`)만 쓴다. 전역 `np.random`을
    쓰면 다른 모듈의 호출 순서가 이 데이터를 바꾼다.
    """
    from risk_lib.ccr import saccr_ead, synthesise_derivatives

    rng = np.random.default_rng(seed + 3100)
    obligors = sorted(set(portfolio["obligor_id"].astype(str)))
    asset = dict(zip(portfolio["obligor_id"].astype(str),
                     portfolio["asset_class"].astype(str)))

    # ---- 거래상대방 마스터
    cp_rows = []
    banks = [o for o in obligors if asset.get(o) == "bank"]
    sib = set(banks[:4])
    gsib = set(banks[4:7])
    for o in obligors:
        a = asset.get(o, "corporate")
        if o in gsib:
            klass = "G-SIB"
        elif o in sib:
            klass = "D-SIB"
        elif a == "sovereign":
            klass = "국가등"
        else:
            klass = "일반"
        cp_rows.append({"counterparty_id": o, "counterparty_class": klass,
                        "is_financial": a == "bank"})
    for cid, klass in (("CP_CCP_QUALIFYING", "적격CCP"),
                       ("CP_CCP_NONQUALIFYING", "비적격CCP"),
                       ("CP_GROUP_HOLDCO", "은행그룹내부"),
                       (UNKNOWN_CLIENT_ID, "무명고객")):
        cp_rows.append({"counterparty_id": cid, "counterparty_class": klass,
                        "is_financial": True})
    structures = [f"CP_FUND_{i:03d}" for i in range(12)]
    for s in structures:
        cp_rows.append({"counterparty_id": s, "counterparty_class": "일반",
                        "is_financial": True})
    counterparty = pd.DataFrame(cp_rows)

    # ---- 익스포져 유니버스
    rows = []
    for i, o in enumerate(obligors):
        ead = float(portfolio.loc[portfolio["obligor_id"] == o, "ead"].sum())
        prov = ead * float(rng.beta(1.2, 40))
        rows.append({"asof": asof, "exposure_id": f"LEXE_ONB_{i:05d}",
                     "counterparty_id": o, "exposure_type": "은행계정_난내",
                     "gross_amount": ead, "deduction_amount": prov,
                     "conversion_factor": np.nan, "measured_override": np.nan})
    # 부외 — 신용환산율은 세칙 <별표3> 값이 들어오는 자리이며, 하한 미만 값을
    # 일부러 섞어 17.의 10% 하한이 실제로 작동하는지 보이게 한다.
    off_pool = obligors[:400]
    for i, o in enumerate(off_pool):
        base = float(portfolio.loc[portfolio["obligor_id"] == o, "ead"].sum())
        rows.append({"asof": asof, "exposure_id": f"LEXE_OFF_{i:05d}",
                     "counterparty_id": o, "exposure_type": "부외",
                     "gross_amount": base * float(rng.uniform(0.05, 0.4)),
                     "deduction_amount": 0.0,
                     "conversion_factor": float(rng.choice([0.0, 0.05, 0.2,
                                                            0.5, 1.0])),
                     "measured_override": np.nan})
    # 파생 — SA-CCR (별표 3-12 15.). 기존 CCR 엔진을 재사용한다.
    bank_book = portfolio[portfolio["asset_class"] == "bank"]
    if len(bank_book):
        trades = synthesise_derivatives(bank_book, seed=seed)
        if len(trades):
            ead_df = saccr_ead(trades)
            for i, r in enumerate(ead_df.itertuples()):
                rows.append({"asof": asof, "exposure_id": f"LEXE_DRV_{i:05d}",
                             "counterparty_id": str(r.counterparty),
                             "exposure_type": "장외파생_SACCR",
                             "gross_amount": float(r.ead),
                             "deduction_amount": 0.0,
                             "conversion_factor": np.nan,
                             "measured_override": float(r.ead)})
    # 증권금융거래 · 트레이딩 · 커버드본드 · 중앙청산소
    sft_pool = banks[:20]
    for i, o in enumerate(sft_pool):
        gross = float(rng.uniform(2e11, 1.2e12))
        rows.append({"asof": asof, "exposure_id": f"LEXE_SFT_{i:05d}",
                     "counterparty_id": o, "exposure_type": "증권금융거래",
                     "gross_amount": gross,
                     # 포괄법 차감 후 순액은 통상 총액의 일부만 남는다.
                     "deduction_amount": gross * float(rng.uniform(0.85, 0.99)),
                     "conversion_factor": np.nan, "measured_override": np.nan})
    for i, o in enumerate(obligors[:150]):
        rows.append({"asof": asof, "exposure_id": f"LEXE_TRD_{i:05d}",
                     "counterparty_id": o, "exposure_type": "트레이딩_채권주식",
                     "gross_amount": float(rng.uniform(1e9, 2e10)),
                     "deduction_amount": 0.0, "conversion_factor": np.nan,
                     "measured_override": np.nan})
    for i, o in enumerate(banks[:10]):
        notional = float(rng.uniform(1e11, 5e11))
        rows.append({"asof": asof, "exposure_id": f"LEXE_CVB_{i:05d}",
                     "counterparty_id": o,
                     "exposure_type": "이중상환청구권부채권",
                     "gross_amount": notional,
                     # 기초자산이 명목을 거의 다 덮어 42. 단서 20% 하한이 걸린다.
                     "deduction_amount": notional * float(rng.uniform(0.85, 0.99)),
                     "conversion_factor": np.nan, "measured_override": np.nan})
    for i, cid in enumerate(("CP_CCP_QUALIFYING", "CP_CCP_NONQUALIFYING")):
        rows.append({"asof": asof, "exposure_id": f"LEXE_CCP_{i:05d}",
                     "counterparty_id": cid,
                     "exposure_type": "중앙청산소_청산관련",
                     "gross_amount": float(rng.uniform(5e11, 2e12)),
                     "deduction_amount": 0.0, "conversion_factor": np.nan,
                     "measured_override": np.nan})
    rows.append({"asof": asof, "exposure_id": "LEXE_GRP_00000",
                 "counterparty_id": "CP_GROUP_HOLDCO",
                 "exposure_type": "은행계정_난내",
                 "gross_amount": float(rng.uniform(1e12, 3e12)),
                 "deduction_amount": 0.0, "conversion_factor": np.nan,
                 "measured_override": np.nan})
    # 구조화상품 — 관통 가능·불가를 섞어 무명고객 버킷이 실제로 차게 한다.
    for i, s in enumerate(structures):
        rows.append({"asof": asof, "exposure_id": f"LEXE_STR_{i:05d}",
                     "counterparty_id": s, "exposure_type": "구조화상품",
                     "gross_amount": float(rng.uniform(2e11, 1.5e12)),
                     "deduction_amount": 0.0, "conversion_factor": np.nan,
                     "measured_override": np.nan})
    universe = pd.DataFrame(rows)

    # ---- 구조화상품 기초자산
    corp = [o for o in obligors if asset.get(o) == "corporate"]
    urows, trows = [], []
    for i, s in enumerate(structures):
        holding = float(universe.loc[universe["counterparty_id"] == s,
                                     "gross_amount"].iloc[0])
        total = holding * float(rng.uniform(1.5, 6.0))
        can_lt = bool(i % 4 != 3)          # 4개 중 1개는 관통 불가
        equal = bool(i % 3 != 2)           # 3개 중 1개는 트렌치 구조
        n_under = int(rng.integers(4, 10))
        picks = [corp[int(rng.integers(0, len(corp)))] for _ in range(n_under)]
        # 식별분이 상품 전체를 덮지 않게 해 미식별 잔여가 무명고객으로 가게 한다.
        covered = total * float(rng.uniform(0.6, 0.95))
        weights = rng.dirichlet(np.ones(n_under))
        for cp, wgt in zip(picks, weights):
            # 같은 차주가 한 풀에 두 번 들어오게 둔다. 44.나가 요구하는 합산이
            # 실제로 일어나는지 이 표본에서 확인된다.
            urows.append({
                "asof": asof, "structure_id": s,
                "underlying_counterparty_id": cp,
                "underlying_notional": float(covered * wgt),
                "structure_total": total, "can_look_through": can_lt,
                "seniority_equal": equal,
                "tranche_amount": holding * float(rng.uniform(1.0, 2.5)),
            })
        if i % 5 == 0:
            trows.append({"asof": asof, "structure_id": s,
                          "third_party_id": "CP_FUND_MANAGER_A",
                          "role": "펀드매니저"})
    structure_underlying = pd.DataFrame(urows)
    # 기초자산 차주 중 포트폴리오에 없는 합성 식별자를 마스터에 추가한다.
    extra = sorted(set(structure_underlying["underlying_counterparty_id"])
                   - set(counterparty["counterparty_id"]))
    if extra:
        counterparty = pd.concat([counterparty, pd.DataFrame({
            "counterparty_id": extra, "counterparty_class": "일반",
            "is_financial": False})], ignore_index=True)
    structure_third_party = pd.DataFrame(
        trows or [], columns=["asof", "structure_id", "third_party_id", "role"])
    if len(trows):
        counterparty = pd.concat([counterparty, pd.DataFrame([{
            "counterparty_id": "CP_FUND_MANAGER_A",
            "counterparty_class": "일반", "is_financial": True}])],
            ignore_index=True)

    # ---- 지배관계 · 경제적 상호의존 (군집이 나오도록 사슬로 잇는다)
    rng_g = np.random.default_rng(seed + 3200)
    ctrl, inter = [], []
    pool = corp[:240]
    for k in range(0, len(pool) - 4, 6):
        chain = pool[k:k + 4]
        # 사슬 구조 — a→b→c 로 이으면 3개가 한 성분이 된다.
        ctrl.append({"asof": asof, "parent_id": chain[0], "child_id": chain[1],
                     "voting_share": float(rng_g.uniform(0.51, 0.95)),
                     "control_basis": "과반수의결권", "excluded": False,
                     "exclusion_approved_by": None})
        ctrl.append({"asof": asof, "parent_id": chain[1], "child_id": chain[2],
                     "voting_share": float(rng_g.uniform(0.30, 0.49)),
                     "control_basis": "이사회임면", "excluded": False,
                     "exclusion_approved_by": None})
        inter.append({"asof": asof, "counterparty_a": chain[2],
                      "counterparty_b": chain[3], "criterion": "수입지출50%",
                      "metric_value": float(rng_g.uniform(0.5, 0.9)),
                      "excluded": False, "exclusion_approved_by": None})
    # 기준 미달로 그룹을 만들지 않는 관계도 넣어 임계 판정이 작동하는지 보인다.
    for k in range(0, 40, 4):
        inter.append({"asof": asof, "counterparty_a": pool[k],
                      "counterparty_b": pool[k + 1], "criterion": "수입지출50%",
                      "metric_value": float(rng_g.uniform(0.2, 0.45)),
                      "excluded": False, "exclusion_approved_by": None})
    control_link = pd.DataFrame(ctrl)
    interdep_link = pd.DataFrame(inter)

    # ---- 보장 (대체로 보장제공자가 한도를 넘길 수 있게 소수에 집중시킨다)
    rng_p = np.random.default_rng(seed + 3300)
    providers = (banks[:3] or obligors[:3])
    grows = []
    for i, o in enumerate(corp[:300]):
        prov = providers[i % len(providers)]
        if prov == o:
            continue
        base = float(portfolio.loc[portfolio["obligor_id"] == o, "ead"].sum())
        om = float(rng_p.choice([0.5, 1.5, 3.0, 5.0], p=[0.1, 0.3, 0.3, 0.3]))
        grows.append({
            "asof": asof, "original_counterparty_id": o,
            "exposure_type": "은행계정_난내", "protection_provider_id": prov,
            "protection_type": str(rng_p.choice(
                ["보증", "신용파생상품", "금융자산담보"], p=[0.6, 0.15, 0.25])),
            "covered_amount": base * float(rng_p.uniform(0.2, 0.8)),
            "original_maturity_years": om,
            "residual_maturity_years": float(rng_p.uniform(0.1, om)),
            "provider_is_financial": True, "reference_is_financial": True,
            "ccr_exposure_amount": np.nan,
        })
    guarantee = pd.DataFrame(grows)

    # ---- 면제규칙
    erows = []
    for o in obligors:
        if asset.get(o) == "sovereign":
            erows.append({"asof": asof, "counterparty_id": o,
                          "exemption_type": "국가등", "exempt_ratio": 1.0,
                          "basis": "위험가중치 0% 중앙정부"})
    erows.append({"asof": asof, "counterparty_id": "CP_CCP_QUALIFYING",
                  "exemption_type": "적격CCP_청산관련", "exempt_ratio": 1.0,
                  "basis": "적격 중앙청산소 청산관련"})
    erows.append({"asof": asof, "counterparty_id": "CP_GROUP_HOLDCO",
                  "exemption_type": "은행그룹내부", "exempt_ratio": 1.0,
                  "basis": "금융지주회사 연결범위 내"})
    for o in banks[:2]:
        erows.append({"asof": asof, "counterparty_id": o,
                      "exemption_type": "은행간_일중", "exempt_ratio": 0.05,
                      "basis": "은행 간 지급결제 일중 거래"})
    exemption_rule = pd.DataFrame(erows)

    return LexInputs(
        counterparty=counterparty, universe=universe, guarantee=guarantee,
        control_link=control_link, interdep_link=interdep_link,
        exemption_rule=exemption_rule,
        structure_underlying=structure_underlying,
        structure_third_party=structure_third_party)


# ---------------------------------------------------------------- 구형 함수

def large_exposure_lex(
    portfolio: pd.DataFrame, tier1: float,
    *, exposure_col: str = "ead", group: bool = False,
) -> pd.DataFrame:
    """구형 간이 산출. `risk_lib.limits.limits_deep`에서 옮겨 왔다.

    원시 EAD를 그대로 쓰고 대체·면제·관통·연결차주 판정을 하지 않는다. 기존
    호출부(`compute_limits_deep`)를 깨지 않기 위해 동작을 바꾸지 않고 그대로
    둔다. 규제 판정에는 `compute_large_exposure`를 쓴다.

    `attach_group_id`는 함수 안에서 임포트한다. `limits_deep`이 이 모듈을
    임포트하므로 모듈 수준에서 반대로 걸면 순환이 된다.
    """
    from risk_lib.limits.limits_deep import attach_group_id

    key = "obligor_group_id" if group else "obligor_id"
    if key not in portfolio.columns:
        portfolio = attach_group_id(portfolio) if group else portfolio
    g = portfolio.groupby(key)[exposure_col].sum().reset_index()
    g = g.rename(columns={exposure_col: "ead"})
    g["pct_tier1"] = g["ead"] / tier1 if tier1 > 0 else 0.0
    g["reportable"] = g["pct_tier1"] >= 0.10
    g["limit_25pct"] = tier1 * 0.25
    g["utilisation_25pct"] = g["ead"] / g["limit_25pct"]

    def _sev(u: float) -> str:
        if u >= 1.0:
            return "BREACH"
        if u >= 0.9:
            return "CRITICAL"
        if u >= 0.75:
            return "WARN"
        return "OK"

    g["severity"] = g["utilisation_25pct"].map(_sev)
    g = g[g["reportable"]].sort_values("ead", ascending=False).reset_index(drop=True)
    return g
