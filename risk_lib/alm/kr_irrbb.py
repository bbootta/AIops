"""[별표 9-1] 국내 금리리스크 산출기준. 국내 고유 요건과 폐지된 2014년 체계.

이 모듈은 두 구역으로 나뉜다. 아래쪽 절반(금리 EaR·금리 VaR)은 **폐지된**
2014년 개정본의 산출체계이고, 위쪽 절반은 현행 별표(개정 2026.1.29)가 d578에
**더해** 국내에서만 정한 요건이다.

## 앞 회차의 전제가 틀렸다

이 모듈의 이전 판은 "별표 9의1이 정하는 표준방법은 ΔEVE·ΔNII가 아니라 금리
EaR·금리 VaR"이라고 적었다. 그 판단의 근거였던 HWP가 2014년 개정본이었다.
현행 별표는 **2019.11.29 개정으로 ΔEVE·ΔNII 체계로 전환**됐고 2022.1.27,
2026.1.29 개정을 거쳤다. 표제부 개정 연혁이 근거다(1차자료 §B 머리말).

  `<별표 9-1> <신설 2007.12.21, 2010.11.17, 2012.2.14, 2014.12.26.,
   2019.11.29., 2022.1.27., 개정 2026.1.29>`

현행 별표 <표5>의 통화별 금리충격은 d578 Table 2와 21개 통화 전건 동일하다.
**KRW는 평행 225 · 단기 350 · 장기 225** 이며, 2014년 체계가 쓰던
"과거 5년 실측 1%·99%"도 d368의 300/400/200도 현행이 아니다.

## 폐지된 2014년 체계를 지우지 않고 떼어낸다

`KR_FRAMEWORK_2014` 계정으로 못박고 결과 원장의 `framework_status`에 '폐지'를
싣는다. 시계열 단절을 설명하려면 폐지된 수치가 어떤 규정으로 산출됐는지가
남아 있어야 한다. 다만 **헤드라인 산출 경로에서는 뺀다**. `KR_IS_HEADLINE`이
그 사실을 코드로 들고 있고, 파이프라인은 이 모듈의 EaR·VaR을 부르지 않는다.
현행 헤드라인 ΔEVE·ΔNII는 `alm/irrbb.py`·`alm/nii.py`가 산출한다.

## 국내 고유 요건 (현행, `KR_FRAMEWORK_2026`)

d578이 정하지 않고 별표가 국내에서만 정한 것을 원장으로 만든다.

  §B-4  제8항 가   비만기성예금 범주 판정. 소매는 개인 예치분이고, 중소기업
                   예금은 소매계정 관리 + 자금조달총액 15억원(연결기준) 미만
                   일 때만 소매 유사로 본다.
  §B-5  제9·10항   행동옵션 적용 범위. 조기상환은 소매고객 고정금리대출 한정
                   이며 중소기업 여신은 총여신 10억원(연결기준) 이하일 때만
                   소매 유사다. 도매고객 행동옵션은 자동금리옵션으로 간주한다
                   (제7항 나(2) 단서).
  §B-7  제11항     자동금리옵션. 시나리오 수익률곡선에 내재변동성 25% 확대
                   가정 하 완전재평가. 매도 가치변동 합 − 매수 가치변동 합.
  §B-12 제15~20항  관리체계. 이사회·위험관리위원회 연 2회 이상 보고, 분기
                   1회 이상 측정, 제16항 라 독립 적합성검증, 제17항 한도
                   초과 시 원인분석·대응책.

판정 기준값(15억원·10억원)과 변동성 확대율(25%)은 전부 원장 컬럼이다. 엔진
함수 본문에는 그 숫자가 없고, 원장을 고치면 판정이 반드시 따라 움직인다.

**미등재.** 아래 TableSpec은 아직 `datamodel.catalog.ALL_TABLES`에 넣지 않았다.
카탈로그 등재는 실체화 검사·ARCHITECTURE.md 수치 검사와 함께 움직이므로 배선
단계에서 등재한다. 스펙 품질 기준(grain·PK·float unit·FK 대상 존재)은 지금부터
지킨다.

**남은 미확인** (1차자료 §C).
  · `CPR_0`·`TDRR_0` 기준율. 별표가 값을 주지 않고 은행이 과거자료로 통화별·
    포트폴리오별 산출한다.
  · 자동금리옵션의 평가모형. 별표는 "완전재평가"만 정하고 모형을 지정하지
    않는다. 이 모듈은 정규(Bachelier) 모형을 쓰고 그 사실을 `pricing_model`
    컬럼에 남긴다.
  · <별표3>(기본자본 정의)·<별표19>(위기상황분석)·<별표23>(공시 세부) 미확보.
  · 2014년 체계의 원화 금리변동 예상폭(5년 1%·99%). 체계 자체가 폐지됐으므로
    더 채우지 않는다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from risk_lib.alm.behaviour import ParamWarning
from risk_lib.alm.daycount import DAY_COUNTS, year_fraction
from risk_lib.alm.params import EVIDENCE_STATUS, IRRBB_SCENARIOS, RATE_TYPES, SIDES
from risk_lib.datamodel.spec import ColumnSpec as C, ForeignKey as FK, TableSpec

__all__ = [
    # 계정
    "KR_FRAMEWORK_2026", "KR_FRAMEWORK_2014", "KR_FRAMEWORK_STATUSES",
    "KR_IS_HEADLINE", "KR_LEGACY_REPEAL_NOTE",
    # 국내 고유 요건 어휘
    "KR_NMD_CATEGORIES", "KR_NMD_CATEGORY_TO_D368", "KR_DEPOSITOR_TYPES",
    "KR_THRESHOLD_COMPARISONS", "KR_BEHAVIOUR_CLASSES", "KR_BEHAVIOUR_TREATMENTS",
    "KR_OPTION_POSITIONS", "KR_OPTION_TYPES", "KR_VOL_EXPANSION_CODE",
    "KR_OPTION_WEIGHT_CODE",
    # 국내 고유 요건 스펙·빌더
    "KR_RETAIL_CRITERIA", "KR_NMD_CATEGORY", "KR_BEHAVIOURAL_SCOPE",
    "KR_AUTO_OPTION_PARAM", "KR_AUTO_OPTION", "KR_AUTO_OPTION_RISK",
    "KR_GOVERNANCE", "KR_NATIONAL_TABLES",
    "build_kr_retail_criteria", "classify_kr_nmd_category",
    "build_kr_retail_behavioural_scope", "build_kr_auto_option_param",
    "bachelier_value", "build_kr_auto_option", "build_kr_auto_option_risk",
    "build_kr_irrbb_governance", "KR_GOVERNANCE_REQUIREMENTS",
    # 폐지된 2014년 체계
    "KR_SHOCK_METHODS", "KR_ASSET_SHARE_BANDS",
    "KR_EXCLUDABLE_ITEMS", "TOTAL_LABEL",
    "KR_BUCKET", "KR_SHOCK_PARAM", "KR_CORE_DEPOSIT_WEIGHT", "KR_CORE_DEPOSIT",
    "KR_GAP", "KR_RESULT", "KR_IRRBB_TABLES",
    "build_kr_irrbb_bucket", "build_kr_irrbb_shock_param",
    "build_kr_core_deposit_weight", "build_kr_core_deposit",
    "build_kr_irrbb_gap", "build_kr_irrbb_result",
    "ear_horizon_years", "kr_ear", "kr_var",
    "KrIrrbbResult", "compute_kr_irrbb",
]

# 계정 식별자 두 개. 1차자료 §E의 이름을 그대로 쓴다.
#   2026 = 현행. ΔEVE·ΔNII 체계이며 <표5> 금리충격이 d578과 동일하다.
#   2014 = 폐지. 금리 EaR·금리 VaR 체계이며 2019.11.29 개정으로 대체됐다.
KR_FRAMEWORK_2026 = "별표9의1_2026"
KR_FRAMEWORK_2014 = "별표9의1_2014"

KR_FRAMEWORK_STATUSES: tuple[str, ...] = ("현행", "폐지")

# 헤드라인 산출에 쓸 수 있는 계정. 폐지된 계정이 헤드라인으로 올라가는 것을
# 코드가 막을 수는 없으므로, 최소한 어느 계정이 헤드라인인지를 원장·검사가
# 읽을 수 있는 자리에 둔다.
KR_IS_HEADLINE: dict[str, bool] = {
    KR_FRAMEWORK_2026: True, KR_FRAMEWORK_2014: False}

KR_LEGACY_REPEAL_NOTE = (
    "폐지된 체계, 이력 보존용. 2019.11.29 개정으로 ΔEVE·ΔNII 체계로 전환됐다. "
    "헤드라인 산출에 쓰지 않는다")

_CITE = "은행업감독업무시행세칙 [별표 9-1] 금리리스크 산출기준"
_CITE_2026 = f"{_CITE} <개정 2026.1.29>"

# 1bp = 0.0001. 단위 정의이며 규제 계수가 아니다. 원장 값은 bp로 담고 산식은
# 비율로 돌기 때문에 환산이 한 번 필요하다.
_BP = 1.0e-4

# ================================================================ 국내 고유 요건
#
# 현행 별표(개정 2026.1.29)가 d578에 **더해** 국내에서만 정한 것. ΔEVE·ΔNII
# 엔진 본체는 `alm/irrbb.py`·`alm/nii.py`에 있고, 여기는 그 엔진이 읽어야 할
# 국내 판정과 국내 모수를 원장으로 만든다.

# ---------------------------------------------------------------- 어휘

# 제8항 가의 범주 3종. 별표는 금융기관 예금을 별도 범주로 두지 않는다.
KR_NMD_CATEGORIES: tuple[str, ...] = ("소매/거래", "소매/비거래", "도매")

# d368 Annex 2 어휘(`params.NMD_CATEGORIES`)와의 대응. 핵심예금 비율·평균만기
# 상한 원장이 그 어휘로 되어 있으므로 조인 키가 있어야 판정이 상한에 닿는다.
KR_NMD_CATEGORY_TO_D368: dict[str, str] = {
    "소매/거래": "retail_transactional",
    "소매/비거래": "retail_non_transactional",
    "도매": "wholesale_nonfin",
}

# 예치인·차주 구분. 제8항 가는 개인과 개인사업자를 나누므로 어휘도 나눈다.
KR_DEPOSITOR_TYPES: tuple[str, ...] = (
    "개인", "개인사업자", "법인", "중소기업", "금융기관")

# 기준금액 비교 방향. 제8항은 '미만', 제9항은 '이하'다. 둘을 섞으면 경계에서
# 한 건씩 어긋난다.
KR_THRESHOLD_COMPARISONS: tuple[str, ...] = ("미만", "이하")

# 별표가 소매고객에 한정하는 행동옵션 2종(제9·10항). `params.BEHAVIOUR_CLASSES`
# 의 부분집합이며 같은 문자열을 쓴다.
KR_BEHAVIOUR_CLASSES: tuple[str, ...] = ("prepayment", "early_redemption")

# 제7항의 표준화 적합도 처리 3종.
KR_BEHAVIOUR_TREATMENTS: tuple[str, ...] = (
    "행동옵션", "자동금리옵션", "적합포지션")

KR_OPTION_POSITIONS: tuple[str, ...] = ("매도", "매수")
KR_OPTION_TYPES: tuple[str, ...] = ("금리캡", "금리플로어")

# 자동금리옵션 모수 코드. 엔진은 코드로 원장을 조회할 뿐 값을 모른다.
KR_VOL_EXPANSION_CODE = "내재변동성_확대율"
KR_OPTION_WEIGHT_CODE: dict[str, str] = {
    "매도": "가치변동_가중_매도", "매수": "가치변동_가중_매수"}

# 소매 유사 간주 규칙 코드.
KR_RULE_NMD_SME = "NMD_소매유사_중소기업"
KR_RULE_LOAN_SME = "여신_소매유사_중소기업"
KR_RULE_TD_SME = "예수금_소매유사_중소기업"

_D368_CATEGORY_VALUES: tuple[str, ...] = tuple(KR_NMD_CATEGORY_TO_D368.values())


# ---------------------------------------------------------------- 스펙

KR_RETAIL_CRITERIA = TableSpec(
    name="kr_retail_criteria", korean="소매 유사 간주 판정기준",
    product="PRD-ALM",
    grain="계정 × 판정규칙 1행",
    columns=(
        C("framework_version", "string", "계정", nullable=False),
        C("rule_code", "string", "규칙 코드", nullable=False),
        C("rule_name", "string", "규칙", nullable=False),
        C("applies_to", "string", "적용 대상", nullable=False),
        C("measure", "string", "판정 대상 금액", nullable=False,
          note="자금조달총액인지 총여신인지가 규칙마다 다르다. 같은 15억원이라도 "
               "무엇을 재는지가 다르면 걸리는 계좌가 달라진다"),
        C("threshold_amount", "float", "기준금액", nullable=True, unit="KRW",
          min_value=0.0,
          citation=f"{_CITE_2026} 제8항 가 15억원 · 제9항 10억원",
          note="엔진은 이 칸을 읽을 뿐 값을 모른다. 비어 있으면 소매 유사 "
               "간주를 적용하지 않고 경고를 남긴다"),
        C("comparison", "string", "비교 방향", nullable=False,
          allowed=KR_THRESHOLD_COMPARISONS),
        C("consolidation_basis", "string", "산정 기준", nullable=False,
          citation=f"{_CITE_2026} 제8항 가·제9항. 연결기준"),
        C("citation", "text", "근거", nullable=True),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("framework_version", "rule_code"),
    note="15억원·10억원이 소스가 아니라 원장 행으로 있어야 검증이 그 값을 본다. "
         "제8항(비만기성예금)과 제10항(기간부예수금)은 15억원 자금조달총액, "
         "제9항(조기상환 고정금리대출)은 10억원 총여신으로 기준이 다르다.",
)

KR_NMD_CATEGORY = TableSpec(
    name="kr_nmd_category", korean="비만기성예금 범주 판정", product="PRD-ALM",
    grain="기준일 × 예금계좌 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("account_id", "string", "예금계좌", nullable=False),
        C("framework_version", "string", "계정", nullable=False),
        C("ccy", "string", "통화", nullable=False),
        C("depositor_type", "string", "예치인 구분", nullable=False,
          allowed=KR_DEPOSITOR_TYPES),
        C("balance", "float", "잔액", nullable=False, unit="KRW",
          min_value=0.0),
        C("is_retail_managed", "bool", "소매계정 관리", nullable=True,
          citation=f"{_CITE_2026} 제8항 가. 중소기업 예금 중 소매계정으로 "
                   f"관리하는 것에 한한다"),
        C("funding_total_amount", "float", "자금조달총액", nullable=True,
          unit="KRW", min_value=0.0,
          citation=f"{_CITE_2026} 제8항 가. 해당 중소기업으로부터의 자금조달 "
                   f"총액(연결기준)"),
        C("has_regular_transaction", "bool", "정기적 거래", nullable=True,
          citation=f"{_CITE_2026} 제8항 가"),
        C("is_interest_free", "bool", "무이자", nullable=True,
          citation=f"{_CITE_2026} 제8항 가. 이자를 지급하지 않으면 거래예금"),
        C("is_retail", "bool", "소매 여부", nullable=True),
        C("is_retail_like", "bool", "소매 유사 간주 적용", nullable=False,
          note="중소기업 예금이 기준금액 판정을 통과해 소매로 들어온 경우만 "
               "True다. 개인 예치분은 원래 소매이므로 False다"),
        C("category", "string", "범주", nullable=True,
          allowed=KR_NMD_CATEGORIES,
          note="거래/비거래를 가르는 입력이 비면 NULL이다. 조용히 비거래로 "
               "떨어뜨리지 않는다"),
        C("d368_category", "string", "d368 범주", nullable=True,
          allowed=_D368_CATEGORY_VALUES,
          note="<표3> 상한 원장이 이 어휘로 되어 있어 조인 키가 필요하다"),
        C("rule_code", "string", "적용 규칙", nullable=True),
        C("threshold_amount", "float", "적용 기준금액", nullable=True,
          unit="KRW", min_value=0.0),
        C("rule_applied", "text", "판정 사유", nullable=False),
        C("citation", "text", "근거", nullable=True),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("asof", "account_id"),
    foreign_keys=(FK(("framework_version", "rule_code"), "kr_retail_criteria",
                     ("framework_version", "rule_code")),),
    note="제8항 가의 5단계 판정을 계좌 단위로 남긴다. 판정 사유가 행마다 있어야 "
         "어느 계좌가 왜 도매로 갔는지를 검증이 되짚을 수 있다.",
)

KR_BEHAVIOURAL_SCOPE = TableSpec(
    name="kr_retail_behavioural_scope", korean="행동옵션 적용 범위 판정",
    product="PRD-ALM",
    grain="기준일 × 계약 × 행동옵션 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("contract_id", "string", "계약", nullable=False),
        C("behaviour_class", "string", "행동옵션", nullable=False,
          allowed=KR_BEHAVIOUR_CLASSES),
        C("framework_version", "string", "계정", nullable=False),
        C("ccy", "string", "통화", nullable=False),
        C("notional", "float", "잔액", nullable=False, unit="KRW",
          min_value=0.0),
        C("customer_type", "string", "고객 구분", nullable=False,
          allowed=KR_DEPOSITOR_TYPES),
        C("rate_type", "string", "금리유형", nullable=True,
          allowed=RATE_TYPES,
          citation=f"{_CITE_2026} 제9항. 조기상환은 고정금리대출에 한한다"),
        C("is_retail_managed", "bool", "소매여신·소매계정 관리", nullable=True),
        C("exposure_amount", "float", "판정 금액", nullable=True, unit="KRW",
          min_value=0.0,
          note="조기상환은 총여신, 중도해지는 자금조달총액이다. 어느 쪽인지는 "
               "exposure_measure가 적는다"),
        C("exposure_measure", "string", "판정 금액 구분", nullable=True),
        C("prepay_fee_charged", "bool", "조기상환 비용 고객부과", nullable=True,
          citation=f"{_CITE_2026} 제9항. 경제적 비용이 고객에게 부과되면 "
                   f"제외한다"),
        C("has_legal_termination_right", "bool", "법적 해지권", nullable=True,
          citation=f"{_CITE_2026} 제10항. 해지할 법적 권한이 없으면 제외한다"),
        C("substantial_penalty", "bool", "상당한 위약금", nullable=True,
          citation=f"{_CITE_2026} 제10항. 상당한 위약금이 부과되면 제외한다"),
        C("is_retail", "bool", "소매고객", nullable=True),
        C("is_retail_like", "bool", "소매 유사 간주 적용", nullable=False),
        C("in_scope", "bool", "행동옵션 적용", nullable=True,
          note="판정에 필요한 입력이 비면 NULL이다. False(적용 안 함)와 다른 "
               "사건이므로 칸을 나눈다"),
        C("treatment", "string", "처리", nullable=True,
          allowed=KR_BEHAVIOUR_TREATMENTS,
          citation=f"{_CITE_2026} 제7항 나. 도매고객이 보유한 행동옵션은 "
                   f"자동금리옵션으로 간주한다(제7항 나(2) 단서)"),
        C("excluded_reason", "text", "제외 사유", nullable=True),
        C("rule_code", "string", "적용 규칙", nullable=True),
        C("threshold_amount", "float", "적용 기준금액", nullable=True,
          unit="KRW", min_value=0.0),
        C("citation", "text", "근거", nullable=True),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("asof", "contract_id", "behaviour_class"),
    foreign_keys=(FK(("framework_version", "rule_code"), "kr_retail_criteria",
                     ("framework_version", "rule_code")),),
    note="제9·10항의 적용 범위를 계약 단위로 남긴다. 범위 밖으로 나간 계약이 "
         "적합포지션인지 자동금리옵션인지가 treatment로 갈린다. 도매고객 "
         "행동옵션은 제7항 나(2) 단서에 따라 제11항으로 넘어간다.",
)

KR_AUTO_OPTION_PARAM = TableSpec(
    name="kr_auto_option_param", korean="자동금리옵션 모수", product="PRD-ALM",
    grain="계정 × 모수 1행",
    columns=(
        C("framework_version", "string", "계정", nullable=False),
        C("param_code", "string", "모수 코드", nullable=False),
        C("param_name", "string", "모수", nullable=False),
        C("value", "float", "값", nullable=True, unit="ratio",
          citation=f"{_CITE_2026} 제11항. 내재변동성 25% 확대 가정 하 "
                   f"완전재평가"),
        C("value_unit", "string", "값 단위", nullable=False),
        C("application", "text", "적용 방법", nullable=False),
        C("citation", "text", "근거", nullable=True),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("framework_version", "param_code"),
    note="25%와 매도·매수 합산부호가 원장 행이다. 엔진은 코드로 조회할 뿐 값을 "
         "모르므로, 이 원장을 고치면 산출이 반드시 따라 움직인다.",
)

KR_AUTO_OPTION = TableSpec(
    name="kr_auto_option", korean="자동금리옵션 재평가", product="PRD-ALM",
    grain="기준일 × 통화 × 시나리오 × 옵션 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("framework_version", "string", "계정", nullable=False),
        C("ccy", "string", "통화", nullable=False),
        C("scenario", "string", "시나리오", nullable=False,
          allowed=IRRBB_SCENARIOS),
        C("option_id", "string", "옵션", nullable=False),
        C("position", "string", "포지션", nullable=False,
          allowed=KR_OPTION_POSITIONS),
        C("option_type", "string", "옵션 유형", nullable=False,
          allowed=KR_OPTION_TYPES),
        C("notional", "float", "명목금액", nullable=False, unit="KRW",
          min_value=0.0),
        C("strike_rate", "float", "행사금리", nullable=False, unit="ratio"),
        C("expiry_years", "float", "잔존만기", nullable=False, unit="years",
          min_value=0.0),
        C("forward_rate_base", "float", "기준 선도금리", nullable=False,
          unit="ratio"),
        C("rate_shift", "float", "시나리오 금리충격", nullable=True,
          unit="ratio"),
        C("floor_rate", "float", "충격후 금리 하한", nullable=True, unit="ratio",
          citation=f"{_CITE_2026} 제12항 다. 충격후 금리의 하한은 0으로 한다"),
        C("forward_rate_shocked", "float", "충격후 선도금리", nullable=True,
          unit="ratio"),
        C("implied_vol_base", "float", "기준 내재변동성", nullable=True,
          unit="정규변동성",
          note="은행 자체추정값이다. 별표가 값을 주지 않으므로 비어 있으면 "
               "그 옵션의 재평가를 건너뛴다"),
        C("vol_expansion", "float", "내재변동성 확대율", nullable=True,
          unit="ratio"),
        C("implied_vol_shocked", "float", "확대 내재변동성", nullable=True,
          unit="정규변동성"),
        C("discount_factor_base", "float", "기준 할인계수", nullable=False,
          unit="ratio", min_value=0.0),
        C("discount_factor_shocked", "float", "충격후 할인계수", nullable=True,
          unit="ratio", min_value=0.0),
        C("value_base", "float", "평가기준일 가치", nullable=True, unit="KRW"),
        C("value_shocked", "float", "시나리오 가치", nullable=True, unit="KRW"),
        C("delta_value", "float", "가치변동", nullable=True, unit="KRW",
          citation=f"{_CITE_2026} 제11항. 시나리오 가치에서 평가기준일 현재 "
                   f"가치를 차감한다"),
        C("position_weight", "float", "합산 가중", nullable=True, unit="배",
          note="매도 +1 · 매수 −1. 원장 모수이며 엔진에 부호가 박혀 있지 않다"),
        C("weighted_delta_value", "float", "가중 가치변동", nullable=True,
          unit="KRW"),
        C("pricing_model", "string", "평가모형", nullable=False,
          note="별표는 '완전재평가'만 정하고 모형을 지정하지 않는다. 어느 "
               "모형으로 재평가했는지가 행마다 남아야 한다"),
        C("skip_reason", "text", "미산출 사유", nullable=True),
        C("citation", "text", "근거", nullable=True),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("asof", "ccy", "scenario", "option_id"),
    note="제11항은 시나리오 수익률곡선에 내재변동성이 25% 확대된다는 가정 하의 "
         "완전재평가를 요구한다. 곡선 이동만 반영하고 변동성을 그대로 두면 "
         "그것은 완전재평가가 아니다.",
)

KR_AUTO_OPTION_RISK = TableSpec(
    name="kr_auto_option_risk", korean="자동금리옵션 리스크",
    product="PRD-ALM",
    grain="기준일 × 통화 × 시나리오 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("framework_version", "string", "계정", nullable=False),
        C("ccy", "string", "통화", nullable=False),
        C("scenario", "string", "시나리오", nullable=False,
          allowed=IRRBB_SCENARIOS),
        C("n_options", "int", "옵션 건수", nullable=False, min_value=0),
        C("n_priced", "int", "재평가 건수", nullable=False, min_value=0),
        C("n_skipped", "int", "미산출 건수", nullable=False, min_value=0),
        C("sold_delta_sum", "float", "매도 가치변동 합", nullable=True,
          unit="KRW"),
        C("bought_delta_sum", "float", "매수 가치변동 합", nullable=True,
          unit="KRW"),
        C("auto_option_risk", "float", "자동금리옵션 리스크", nullable=True,
          unit="KRW",
          citation=f"{_CITE_2026} 제11항. 매도 옵션 가치변동치 합에서 매수 "
                   f"옵션 가치변동치 합을 차감한다"),
        C("is_complete", "bool", "전건 재평가 여부", nullable=False,
          note="한 건이라도 건너뛰었으면 False다. 그 상태의 합계를 제13항 "
               "ΔEVE에 그대로 더하면 리스크가 과소계상된다"),
        C("vol_expansion", "float", "내재변동성 확대율", nullable=True,
          unit="ratio"),
        C("citation", "text", "근거", nullable=True),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("asof", "ccy", "scenario"),
    foreign_keys=(FK(("asof", "ccy", "scenario"), "kr_auto_option",
                     ("asof", "ccy", "scenario")),),
    note="제13항 나가 시나리오별 EVE 리스크에 더하는 항이다. 통화별·시나리오별 "
         "1행이며 미산출 건수가 0이 아니면 합계를 신뢰할 수 없다.",
)

KR_GOVERNANCE = TableSpec(
    name="kr_irrbb_governance", korean="금리리스크 관리체계 요구사항 추적",
    product="PRD-ALM",
    grain="기준일 × 요구사항 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("requirement_code", "string", "요구사항 코드", nullable=False),
        C("framework_version", "string", "계정", nullable=False),
        C("clause", "string", "조항", nullable=False),
        C("requirement", "text", "요구사항", nullable=False),
        C("responsible_body", "string", "수행 주체", nullable=False),
        C("frequency_text", "string", "요구 주기", nullable=True,
          citation=f"{_CITE_2026} 제15항 연 2회 이상 · 제16항 나 분기 1회 이상"),
        C("min_count_per_year", "int", "연간 최소 횟수", nullable=True,
          min_value=1,
          note="주기가 횟수로 적힌 요구사항만 값이 있다. NULL이면 횟수로 "
               "판정하지 않고 입력된 이행 여부를 그대로 싣는다"),
        C("period_label", "text", "이행 실적 기간", nullable=True),
        C("count_in_period", "int", "기간 내 이행 횟수", nullable=True,
          min_value=0),
        C("is_annual_period", "bool", "연간 기간 여부", nullable=True),
        C("last_fulfilled_date", "date", "최근 이행일", nullable=True),
        C("evidence_ref", "text", "증적", nullable=True),
        C("is_fulfilled", "bool", "이행 여부", nullable=True,
          note="실적이 입력되지 않았으면 NULL이다. 미입력을 미이행(False)으로 "
               "적으면 없는 사실을 만드는 것이다"),
        C("verdict_reason", "text", "판정 사유", nullable=False),
        C("citation", "text", "근거", nullable=True),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("asof", "requirement_code"),
    note="제16항 라(독립적이면서 전문성을 갖춘 별도의 부서 또는 외부전문가의 "
         "정기 적합성검증)가 이 저장소 3선 상시 독립검증의 규정 근거다. "
         "GOV-16-02 행이 그 자리다.",
)

KR_NATIONAL_TABLES: tuple[TableSpec, ...] = (
    KR_RETAIL_CRITERIA, KR_NMD_CATEGORY, KR_BEHAVIOURAL_SCOPE,
    KR_AUTO_OPTION_PARAM, KR_AUTO_OPTION, KR_AUTO_OPTION_RISK, KR_GOVERNANCE,
)


# ---------------------------------------------------------------- 규제표 적재
#
# 아래 리터럴이 국내 고유 요건 구역에서 숫자가 있는 유일한 자리다. 판정·재평가
# 함수는 전부 원장을 인자로 받는다.

# 제8항 가 15억원(자금조달총액, 연결기준, 미만) · 제9항 10억원(총여신,
# 연결기준, 이하). 제10항은 제8항의 15억원 기준을 그대로 쓴다.
# (rule_code, rule_name, applies_to, measure, threshold, comparison, clause)
_RETAIL_CRITERIA_ROWS: tuple[
    tuple[str, str, str, str, float, str, str], ...] = (
    (KR_RULE_NMD_SME, "중소기업 예금의 소매 유사 간주", "비만기성예금",
     "자금조달총액", 1_500_000_000.0, "미만", "제8항 가"),
    (KR_RULE_LOAN_SME, "중소기업 여신의 소매 유사 간주", "고정금리대출",
     "총여신", 1_000_000_000.0, "이하", "제9항"),
    (KR_RULE_TD_SME, "중소기업 예수금의 소매 유사 간주", "기간부예수금",
     "자금조달총액", 1_500_000_000.0, "미만", "제10항"),
)

_CONSOLIDATION_BASIS = "연결기준"

# 제11항 내재변동성 25% 확대와 매도·매수 합산부호.
# (param_code, param_name, value, unit, application)
_AUTO_OPTION_PARAM_ROWS: tuple[
    tuple[str, str, float, str, str], ...] = (
    (KR_VOL_EXPANSION_CODE, "내재변동성 확대율", 0.25, "ratio",
     "시나리오 재평가 시 내재변동성에 (1 + 확대율)을 곱한다"),
    (KR_OPTION_WEIGHT_CODE["매도"], "매도 옵션 가치변동 합산 가중", 1.0, "배",
     "매도 옵션 가치변동치는 그대로 더한다"),
    (KR_OPTION_WEIGHT_CODE["매수"], "매수 옵션 가치변동 합산 가중", -1.0, "배",
     "매수 옵션 가치변동치는 차감한다"),
)

# 제15~20항 관리체계 요구사항.
# (code, clause, requirement, responsible_body, frequency_text, min_per_year)
KR_GOVERNANCE_REQUIREMENTS: tuple[
    tuple[str, str, str, str, str | None, int | None], ...] = (
    ("GOV-15-01", "제15항",
     "이사회 또는 위험관리위원회가 금리리스크 관리 전략과 정책을 승인한다",
     "이사회·위험관리위원회", None, None),
    ("GOV-15-02", "제15항",
     "이사회 또는 위험관리위원회가 금리리스크 보고서를 정기적으로 검토한다",
     "이사회·위험관리위원회", "연 2회 이상", 2),
    ("GOV-16-01", "제16항 나",
     "금리리스크를 측정한다. 금리변동이 심한 경우 측정주기를 단축한다",
     "리스크관리부서", "분기 1회 이상", 4),
    ("GOV-16-02", "제16항 라",
     "독립적이면서 전문성을 갖춘 별도의 부서 또는 외부전문가가 모형·가정·"
     "데이터와 측정시스템 관련 모든 절차·구조의 적합성검증을 실시한다",
     "독립 검증부서·외부전문가", "정기적", None),
    ("GOV-17-01", "제17항",
     "ΔEVE·ΔNII를 포함한 측정결과를 종합해 업무부문별(원화·외화·신탁) 한도를 "
     "설정하고 필요 시 부서·포트폴리오별로 배분한다",
     "이사회·위험관리위원회", None, None),
    ("GOV-17-02", "제17항",
     "한도 초과 시 원인분석과 대응책(포지션 축소·헤지거래 등)을 마련·운영한다",
     "리스크관리부서", None, None),
    ("GOV-18-01", "제18항",
     "금리리스크 내부자본을 내부자본적정성 평가에 포함한다",
     "리스크관리부서", None, None),
    ("GOV-19-01", "제19항",
     "위기상황분석과 역위기상황분석을 실시한다",
     "리스크관리부서", None, None),
    ("GOV-20-01", "제20항",
     "내부통제체계를 구축하고 내부감사 등 독립조직이 정기적으로 점검한다",
     "감사부서", None, None),
)

# 별표가 평가모형을 지정하지 않으므로 어느 모형을 썼는지를 행에 남긴다.
# 정규(Bachelier) 모형을 쓰는 이유는 제12항 다의 충격후 금리 하한이 0이어서
# 선도금리가 0에 닿을 수 있고, 로그정규 모형은 그 지점에서 정의되지 않기
# 때문이다.
_PRICING_MODEL = "정규(Bachelier) 완전재평가"


def build_kr_retail_criteria(
    *, framework_version: str = KR_FRAMEWORK_2026,
) -> pd.DataFrame:
    """제8~10항 소매 유사 간주 기준금액 원장.

    15억원·10억원이 나오는 유일한 자리다. 판정 함수는 이 원장을 인자로 받고
    기준금액을 컬럼에서 읽으므로, 여기를 고치면 경계 판정이 반드시 따라
    움직인다.
    """
    rows = []
    for code, name, applies, measure, thr, cmp_, clause in _RETAIL_CRITERIA_ROWS:
        rows.append({
            "framework_version": framework_version,
            "rule_code": code, "rule_name": name, "applies_to": applies,
            "measure": measure, "threshold_amount": float(thr),
            "comparison": cmp_, "consolidation_basis": _CONSOLIDATION_BASIS,
            "citation": f"{_CITE_2026} {clause}",
            "evidence_status": "원문확인",
        })
    return pd.DataFrame(rows).astype({"threshold_amount": "float64"})


def build_kr_auto_option_param(
    *, framework_version: str = KR_FRAMEWORK_2026,
) -> pd.DataFrame:
    """제11항 자동금리옵션 모수 원장. 확대율 25%와 매도·매수 합산부호."""
    rows = []
    for code, name, value, unit, application in _AUTO_OPTION_PARAM_ROWS:
        rows.append({
            "framework_version": framework_version,
            "param_code": code, "param_name": name, "value": float(value),
            "value_unit": unit, "application": application,
            "citation": f"{_CITE_2026} 제11항",
            "evidence_status": "원문확인",
        })
    return pd.DataFrame(rows).astype({"value": "float64"})


# ---------------------------------------------------------------- 판정 엔진
#
# 이 아래 함수 본문에는 규제 수치가 없다. 기준금액·비교방향·확대율·합산부호는
# 전부 원장 인자에서 온다.

def _tri(value) -> bool | None:
    """3값 논리로 읽는다. 결측은 False가 아니라 '모른다'이다."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return bool(value)


def _num(value) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return float(value)


def _criteria_row(criteria: pd.DataFrame, rule_code: str,
                  framework_version: str) -> pd.Series:
    hit = criteria[(criteria["framework_version"] == framework_version)
                   & (criteria["rule_code"] == rule_code)]
    if len(hit) != 1:
        raise KeyError(
            f"kr_retail_criteria에 {framework_version}/{rule_code} 행이 "
            f"{len(hit)}건이다. 판정 기준금액을 읽을 수 없다")
    return hit.iloc[0]


def _meets_threshold(amount: float | None, threshold: float | None,
                     comparison: str) -> bool | None:
    """기준금액 판정. 값이 없으면 판정하지 않고 None을 돌려준다.

    '미만'과 '이하'는 경계에서 결과가 갈린다. 제8항이 미만, 제9항이 이하이며
    비교 방향도 원장 컬럼에서 온다.
    """
    if amount is None or threshold is None:
        return None
    if comparison == KR_THRESHOLD_COMPARISONS[0]:
        return amount < threshold
    if comparison == KR_THRESHOLD_COMPARISONS[1]:
        return amount <= threshold
    raise ValueError(
        f"비교 방향 {comparison!r}은 {KR_THRESHOLD_COMPARISONS} 중 하나여야 한다")


def classify_kr_nmd_category(
    deposits: pd.DataFrame,
    criteria: pd.DataFrame,
    *,
    asof: str,
    framework_version: str = KR_FRAMEWORK_2026,
) -> tuple[pd.DataFrame, list[ParamWarning]]:
    """제8항 가 비만기성예금 범주 판정.

    판정 순서는 원문 순서를 그대로 따른다.

      1. 개인 예치분은 소매다. 법인·개인사업자·금융기관 예치분은 아니다.
      2. 중소기업 예금은 소매계정으로 관리하고 자금조달총액이 기준금액 미만일
         때만 소매 유사로 간주한다.
      3. 소매 중 정기적 거래가 있거나 무이자면 거래예금, 그 외는 비거래예금.
      4. 위에 해당하지 않으면 도매예금이다.

    `deposits` 컬럼: `account_id`·`ccy`·`balance`·`depositor_type`·
    `is_retail_managed`·`funding_total_amount`·`has_regular_transaction`·
    `is_interest_free`. `asof` 컬럼이 있으면 해당 기준일 행만 읽는다.

    자금조달총액이 비어 있으면 소매 유사 간주를 **적용하지 않고** 경고를
    남긴다. 그 계좌는 원문 4단계의 잔여규칙에 따라 도매가 되며, 그 사실이
    `rule_applied`에 적힌다. 거래/비거래를 가르는 두 입력이 모두 비면 범주를
    NULL로 남긴다.
    """
    warns: list[ParamWarning] = []
    rule = _criteria_row(criteria, KR_RULE_NMD_SME, framework_version)
    threshold = _num(rule["threshold_amount"])
    comparison = str(rule["comparison"])
    if threshold is None:
        warns.append(ParamWarning(
            "kr_nmd_category", KR_RULE_NMD_SME, "threshold_amount",
            "소매 유사 간주 기준금액이 비어 있다. 중소기업 예금을 소매로 "
            "올리지 않는다"))

    src = deposits[deposits["asof"] == asof] if "asof" in deposits.columns \
        else deposits
    bad = sorted({str(t) for t in src["depositor_type"]} - set(KR_DEPOSITOR_TYPES))
    if bad:
        raise ValueError(
            f"예치인 구분에 미지의 값 {bad}. {KR_DEPOSITOR_TYPES} 중 하나여야 한다")

    rows = []
    for r in src.itertuples():
        dtype = str(r.depositor_type)
        managed = _tri(getattr(r, "is_retail_managed", None))
        funding = _num(getattr(r, "funding_total_amount", None))
        rule_code = None
        retail_like = False
        evidence = "원문확인"

        if dtype == KR_DEPOSITOR_TYPES[0]:          # 개인
            is_retail: bool | None = True
            reason = "개인이 예치한 예금이므로 소매다"
        elif dtype == KR_DEPOSITOR_TYPES[3]:        # 중소기업
            rule_code = KR_RULE_NMD_SME
            if managed is not True:
                is_retail = False
                reason = ("중소기업 예금이나 소매계정으로 관리하지 않는다. "
                          "소매 유사 간주를 적용하지 않는다")
            else:
                meets = _meets_threshold(funding, threshold, comparison)
                if meets is None:
                    is_retail = False
                    evidence = "미확인"
                    reason = (f"자금조달총액이 비어 있어 기준금액 판정을 하지 "
                              f"못했다. 소매 유사 간주를 적용하지 않는다")
                    warns.append(ParamWarning(
                        "kr_nmd_category", str(r.account_id),
                        "funding_total_amount",
                        "자금조달총액(연결기준)이 비어 있다. 소매 유사 간주를 "
                        "건너뛰고 잔여규칙에 따라 도매로 둔다"))
                elif meets:
                    is_retail = True
                    retail_like = True
                    reason = (f"소매계정 관리 중이고 자금조달총액이 기준금액 "
                              f"{comparison}이므로 소매와 유사한 것으로 본다")
                else:
                    is_retail = False
                    reason = (f"자금조달총액이 기준금액 {comparison}이 아니므로 "
                              f"소매 유사 간주 대상이 아니다")
        else:                                        # 개인사업자·법인·금융기관
            is_retail = False
            reason = f"{dtype} 예치분은 소매예금에서 제외된다"

        category = None
        if is_retail:
            regular = _tri(getattr(r, "has_regular_transaction", None))
            free = _tri(getattr(r, "is_interest_free", None))
            if regular is True or free is True:
                category = KR_NMD_CATEGORIES[0]
                reason = f"{reason}. 정기적 거래 또는 무이자이므로 거래예금이다"
            elif regular is None and free is None:
                evidence = "미확인"
                reason = (f"{reason}. 정기적 거래·무이자 여부가 모두 비어 있어 "
                          f"거래/비거래를 가르지 못했다")
                warns.append(ParamWarning(
                    "kr_nmd_category", str(r.account_id),
                    "has_regular_transaction",
                    "정기적 거래·무이자 여부가 모두 비어 있다. 거래예금 여부를 "
                    "판정하지 않고 범주를 비운다"))
            else:
                category = KR_NMD_CATEGORIES[1]
                reason = (f"{reason}. 정기적 거래가 없고 이자를 지급하므로 "
                          f"비거래예금이다")
        else:
            category = KR_NMD_CATEGORIES[2]
            reason = f"{reason}. 잔여규칙에 따라 도매예금이다"

        rows.append({
            "asof": asof, "account_id": str(r.account_id),
            "framework_version": framework_version, "ccy": str(r.ccy),
            "depositor_type": dtype, "balance": float(r.balance),
            "is_retail_managed": managed, "funding_total_amount": funding,
            "has_regular_transaction": _tri(
                getattr(r, "has_regular_transaction", None)),
            "is_interest_free": _tri(getattr(r, "is_interest_free", None)),
            "is_retail": is_retail, "is_retail_like": retail_like,
            "category": category,
            "d368_category": (None if category is None
                              else KR_NMD_CATEGORY_TO_D368[category]),
            "rule_code": rule_code,
            "threshold_amount": threshold if rule_code else None,
            "rule_applied": reason,
            "citation": f"{_CITE_2026} 제8항 가",
            "evidence_status": evidence,
        })

    df = pd.DataFrame(rows, columns=[c.name for c in KR_NMD_CATEGORY.columns])
    return df.astype({"balance": "float64", "funding_total_amount": "float64",
                      "threshold_amount": "float64",
                      "is_retail_like": "bool"}), warns


def build_kr_retail_behavioural_scope(
    contracts: pd.DataFrame,
    criteria: pd.DataFrame,
    *,
    asof: str,
    framework_version: str = KR_FRAMEWORK_2026,
) -> tuple[pd.DataFrame, list[ParamWarning]]:
    """제9·10항 행동옵션 적용 범위 판정.

    조기상환(`prepayment`)은 고정금리대출이면서 소매고객이 보유하고 조기상환
    경제적 비용이 고객에게 부과되지 않을 때만 행동옵션으로 다룬다. 중소기업
    여신은 소매여신으로 관리 중이고 총여신이 기준금액 이하일 때 소매 유사다.

    중도해지(`early_redemption`)는 예금자에게 법적 해지권이 있고 상당한
    위약금이 부과되지 않을 때만 행동옵션이다. 중소기업 예수금은 제8항의
    자금조달총액 기준을 그대로 쓴다.

    **도매고객이 보유한 행동옵션은 자동금리옵션으로 간주한다**(제7항 나(2)
    단서). 범위 밖으로 나간다고 사라지는 것이 아니라 제11항으로 넘어가므로
    `treatment`가 그 사실을 적는다.

    `contracts` 컬럼: `contract_id`·`behaviour_class`·`ccy`·`notional`·
    `customer_type`·`rate_type`·`is_retail_managed`·`exposure_amount`·
    `prepay_fee_charged`·`has_legal_termination_right`·`substantial_penalty`.
    """
    warns: list[ParamWarning] = []
    rules = {
        KR_BEHAVIOUR_CLASSES[0]: _criteria_row(criteria, KR_RULE_LOAN_SME,
                                               framework_version),
        KR_BEHAVIOUR_CLASSES[1]: _criteria_row(criteria, KR_RULE_TD_SME,
                                               framework_version),
    }
    src = contracts[contracts["asof"] == asof] if "asof" in contracts.columns \
        else contracts
    bad = sorted({str(b) for b in src["behaviour_class"]}
                 - set(KR_BEHAVIOUR_CLASSES))
    if bad:
        raise ValueError(
            f"행동옵션 구분에 미지의 값 {bad}. 별표가 소매고객에 한정하는 것은 "
            f"{KR_BEHAVIOUR_CLASSES} 두 종이다")
    bad = sorted({str(t) for t in src["customer_type"]} - set(KR_DEPOSITOR_TYPES))
    if bad:
        raise ValueError(f"고객 구분에 미지의 값 {bad}. {KR_DEPOSITOR_TYPES}")

    rows = []
    for r in src.itertuples():
        cls = str(r.behaviour_class)
        rule = rules[cls]
        threshold = _num(rule["threshold_amount"])
        comparison = str(rule["comparison"])
        ctype = str(r.customer_type)
        managed = _tri(getattr(r, "is_retail_managed", None))
        exposure = _num(getattr(r, "exposure_amount", None))
        rate_type = getattr(r, "rate_type", None)
        rate_type = None if rate_type is None or pd.isna(rate_type) \
            else str(rate_type)

        rule_code: str | None = None
        retail_like = False
        in_scope: bool | None = None
        treatment: str | None = None
        excluded: str | None = None
        evidence = "원문확인"

        # 제9항은 고정금리대출에 한한다. 변동금리 대출에는 조기상환 행동옵션을
        # 걸 자리가 없으므로 표준화 적합 포지션이다.
        if cls == KR_BEHAVIOUR_CLASSES[0] and rate_type != RATE_TYPES[0]:
            is_retail: bool | None = None
            in_scope = False
            treatment = KR_BEHAVIOUR_TREATMENTS[2]
            excluded = (f"금리유형이 {rate_type!r}이다. 제9항은 고정금리대출에 "
                        f"한한다")
            rows.append(_scope_row(
                r, asof=asof, framework_version=framework_version, cls=cls,
                ctype=ctype, rate_type=rate_type, managed=managed,
                exposure=exposure, measure=str(rule["measure"]),
                is_retail=is_retail, retail_like=retail_like,
                in_scope=in_scope, treatment=treatment, excluded=excluded,
                rule_code=rule_code, threshold=None, evidence=evidence))
            continue

        if ctype == KR_DEPOSITOR_TYPES[0]:            # 개인
            is_retail = True
        elif ctype == KR_DEPOSITOR_TYPES[3]:          # 중소기업
            rule_code = rule["rule_code"]
            if managed is not True:
                is_retail = False
            else:
                meets = _meets_threshold(exposure, threshold, comparison)
                if meets is None:
                    is_retail = False
                    evidence = "미확인"
                    warns.append(ParamWarning(
                        "kr_behavioural_scope", str(r.contract_id),
                        "exposure_amount",
                        f"{rule['measure']}(연결기준)이 비어 있다. 소매 유사 "
                        f"간주를 건너뛰고 도매고객으로 둔다"))
                else:
                    is_retail = bool(meets)
                    retail_like = bool(meets)
        else:
            is_retail = False

        if not is_retail:
            # 제7항 나(2) 단서. 도매고객 행동옵션은 자동금리옵션이다.
            in_scope = False
            treatment = KR_BEHAVIOUR_TREATMENTS[1]
            excluded = ("소매고객 보유분이 아니다. 도매고객이 보유한 행동옵션은 "
                        "자동금리옵션으로 간주한다(제7항 나(2) 단서)")
        elif cls == KR_BEHAVIOUR_CLASSES[0]:
            fee = _tri(getattr(r, "prepay_fee_charged", None))
            if fee is None:
                evidence = "미확인"
                warns.append(ParamWarning(
                    "kr_behavioural_scope", str(r.contract_id),
                    "prepay_fee_charged",
                    "조기상환 경제적 비용의 고객부과 여부가 비어 있다. 적용 "
                    "여부를 판정하지 않는다"))
            elif fee:
                in_scope = False
                treatment = KR_BEHAVIOUR_TREATMENTS[2]
                excluded = ("조기상환 경제적 비용이 고객에게 부과된다. 제9항 "
                            "대상이 아니다")
            else:
                in_scope = True
                treatment = KR_BEHAVIOUR_TREATMENTS[0]
        else:
            right = _tri(getattr(r, "has_legal_termination_right", None))
            penalty = _tri(getattr(r, "substantial_penalty", None))
            if right is False:
                in_scope = False
                treatment = KR_BEHAVIOUR_TREATMENTS[2]
                excluded = "예금자에게 해지할 법적 권한이 없다. 제10항 대상이 아니다"
            elif penalty is True:
                in_scope = False
                treatment = KR_BEHAVIOUR_TREATMENTS[2]
                excluded = "중도해지 시 상당한 위약금이 부과된다. 제10항 대상이 아니다"
            elif right is None or penalty is None:
                evidence = "미확인"
                warns.append(ParamWarning(
                    "kr_behavioural_scope", str(r.contract_id),
                    "has_legal_termination_right",
                    "법적 해지권 또는 위약금 여부가 비어 있다. 적용 여부를 "
                    "판정하지 않는다"))
            else:
                in_scope = True
                treatment = KR_BEHAVIOUR_TREATMENTS[0]

        rows.append(_scope_row(
            r, asof=asof, framework_version=framework_version, cls=cls,
            ctype=ctype, rate_type=rate_type, managed=managed,
            exposure=exposure, measure=str(rule["measure"]),
            is_retail=is_retail, retail_like=retail_like, in_scope=in_scope,
            treatment=treatment, excluded=excluded, rule_code=rule_code,
            threshold=threshold if rule_code else None, evidence=evidence))

    df = pd.DataFrame(rows,
                      columns=[c.name for c in KR_BEHAVIOURAL_SCOPE.columns])
    return df.astype({"notional": "float64", "exposure_amount": "float64",
                      "threshold_amount": "float64",
                      "is_retail_like": "bool"}), warns


def _scope_row(r, *, asof: str, framework_version: str, cls: str, ctype: str,
               rate_type: str | None, managed: bool | None,
               exposure: float | None, measure: str, is_retail: bool | None,
               retail_like: bool, in_scope: bool | None,
               treatment: str | None, excluded: str | None,
               rule_code: str | None, threshold: float | None,
               evidence: str) -> dict:
    """판정 결과 1행. 컬럼 나열을 두 곳에 두지 않으려고 뽑아 둔다."""
    return {
        "asof": asof, "contract_id": str(r.contract_id),
        "behaviour_class": cls, "framework_version": framework_version,
        "ccy": str(r.ccy), "notional": float(r.notional),
        "customer_type": ctype, "rate_type": rate_type,
        "is_retail_managed": managed, "exposure_amount": exposure,
        "exposure_measure": measure,
        "prepay_fee_charged": _tri(getattr(r, "prepay_fee_charged", None)),
        "has_legal_termination_right": _tri(
            getattr(r, "has_legal_termination_right", None)),
        "substantial_penalty": _tri(getattr(r, "substantial_penalty", None)),
        "is_retail": is_retail, "is_retail_like": retail_like,
        "in_scope": in_scope, "treatment": treatment,
        "excluded_reason": excluded, "rule_code": rule_code,
        "threshold_amount": threshold,
        "citation": f"{_CITE_2026} 제9·10항 · 제7항 나(2) 단서",
        "evidence_status": evidence,
    }


# ---------------------------------------------------------------- 자동금리옵션

_SQRT_2PI = math.sqrt(2.0 * math.pi)


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / _SQRT_2PI


def bachelier_value(*, option_type: str, forward: float, strike: float,
                    vol: float, expiry_years: float, discount_factor: float,
                    notional: float) -> float:
    """정규(Bachelier) 모형 옵션가치.

    여기 있는 숫자(0.5·2·1)는 정규분포 밀도·누적분포의 정의이지 규제 계수가
    아니다. 규제가 정하는 값(확대율 25%, 합산부호)은 이 함수에 들어오지 않고
    호출부가 원장에서 읽어 인자로 넘긴다.

    로그정규 모형을 쓰지 않는 이유는 제12항 다가 충격후 금리 하한을 0으로
    정해서 선도금리가 0에 닿을 수 있기 때문이다.
    """
    intrinsic = (forward - strike if option_type == KR_OPTION_TYPES[0]
                 else strike - forward)
    if expiry_years <= 0.0 or vol <= 0.0:
        return notional * discount_factor * max(intrinsic, 0.0)
    s = vol * math.sqrt(expiry_years)
    d = (forward - strike) / s
    if option_type == KR_OPTION_TYPES[0]:
        v = (forward - strike) * _norm_cdf(d) + s * _norm_pdf(d)
    elif option_type == KR_OPTION_TYPES[1]:
        v = (strike - forward) * _norm_cdf(-d) + s * _norm_pdf(d)
    else:
        raise ValueError(
            f"옵션 유형 {option_type!r}은 {KR_OPTION_TYPES} 중 하나여야 한다")
    return notional * discount_factor * v


def _param_value(param: pd.DataFrame, code: str,
                 framework_version: str) -> float | None:
    hit = param[(param["framework_version"] == framework_version)
                & (param["param_code"] == code)]
    if len(hit) != 1:
        raise KeyError(
            f"kr_auto_option_param에 {framework_version}/{code} 행이 "
            f"{len(hit)}건이다. 모수를 읽을 수 없다")
    return _num(hit.iloc[0]["value"])


def build_kr_auto_option(
    options: pd.DataFrame,
    shifts: pd.DataFrame,
    param: pd.DataFrame,
    *,
    asof: str,
    framework_version: str = KR_FRAMEWORK_2026,
) -> tuple[pd.DataFrame, list[ParamWarning]]:
    """제11항 자동금리옵션 완전재평가.

    시나리오 수익률곡선에 **내재변동성이 25% 확대**된다는 가정 하에 재평가하고
    평가기준일 현재 가치를 차감한다. 확대율과 매도·매수 합산부호는 전부
    `param` 원장에서 읽는다. 이 함수 본문에는 그 숫자가 없다.

    `options` 컬럼: `option_id`·`ccy`·`position`·`option_type`·`notional`·
    `strike_rate`·`expiry_years`·`forward_rate_base`·`implied_vol_base`·
    `discount_factor_base`.

    `shifts` 컬럼: `ccy`·`scenario`·`expiry_years`·`rate_shift`·`floor_rate`·
    `discount_factor_shocked`. 시나리오 곡선에서 뽑은 값이며 `alm/curves.py`가
    만든다. 옵션 잔존만기와 정확히 맞는 행이 없으면 그 조합을 건너뛴다.

    내재변동성은 은행 자체추정값이고 별표가 값을 주지 않는다. 비어 있으면 그
    옵션의 재평가를 건너뛰고 경고를 남긴다. 곡선만 움직이고 변동성을 그대로
    두는 것은 제11항의 완전재평가가 아니다.
    """
    warns: list[ParamWarning] = []
    expansion = _param_value(param, KR_VOL_EXPANSION_CODE, framework_version)
    weights = {pos: _param_value(param, KR_OPTION_WEIGHT_CODE[pos],
                                 framework_version)
               for pos in KR_OPTION_POSITIONS}
    if expansion is None:
        warns.append(ParamWarning(
            "kr_auto_option", framework_version, KR_VOL_EXPANSION_CODE,
            "내재변동성 확대율이 비어 있다. 제11항의 완전재평가 가정을 세울 수 "
            "없으므로 재평가하지 않는다"))

    opt = options[options["asof"] == asof] if "asof" in options.columns \
        else options
    bad = sorted({str(p) for p in opt["position"]} - set(KR_OPTION_POSITIONS))
    if bad:
        raise ValueError(f"포지션에 미지의 값 {bad}. {KR_OPTION_POSITIONS}")

    shift_map = {
        (str(s.ccy), str(s.scenario), float(s.expiry_years)): s
        for s in shifts.itertuples()}

    rows = []
    for r in opt.itertuples():
        ccy, expiry = str(r.ccy), float(r.expiry_years)
        position = str(r.position)
        vol_base = _num(getattr(r, "implied_vol_base", None))
        weight = weights[position]
        for sc in IRRBB_SCENARIOS:
            s = shift_map.get((ccy, sc, expiry))
            skip: str | None = None
            if s is None:
                skip = (f"시나리오 곡선에 ({ccy}, {sc}, {expiry}년) 행이 없다. "
                        f"충격후 선도금리를 만들 수 없다")
            elif vol_base is None:
                skip = "내재변동성이 비어 있다. 은행 자체추정값이 필요하다"
            elif expansion is None:
                skip = "내재변동성 확대율이 비어 있다"
            elif weight is None:
                skip = f"{position} 합산 가중이 비어 있다"

            shift = None if s is None else _num(s.rate_shift)
            floor = None if s is None else _num(s.floor_rate)
            df_shocked = None if s is None else _num(s.discount_factor_shocked)
            fwd_base = float(r.forward_rate_base)
            fwd_shocked = vol_shocked = None
            value_base = value_shocked = delta = weighted = None

            if skip is None:
                fwd_shocked = fwd_base + shift
                if floor is not None:
                    # 제12항 다. 충격후 금리의 하한은 0으로 한다. 하한값 자체는
                    # 곡선 원장이 들고 오며 여기서 숫자로 적지 않는다.
                    fwd_shocked = max(fwd_shocked, floor)
                vol_shocked = vol_base * (1.0 + expansion)
                value_base = bachelier_value(
                    option_type=str(r.option_type), forward=fwd_base,
                    strike=float(r.strike_rate), vol=vol_base,
                    expiry_years=expiry,
                    discount_factor=float(r.discount_factor_base),
                    notional=float(r.notional))
                value_shocked = bachelier_value(
                    option_type=str(r.option_type), forward=fwd_shocked,
                    strike=float(r.strike_rate), vol=vol_shocked,
                    expiry_years=expiry, discount_factor=df_shocked,
                    notional=float(r.notional))
                delta = value_shocked - value_base
                weighted = weight * delta
            else:
                warns.append(ParamWarning(
                    "kr_auto_option", f"{ccy}/{sc}/{r.option_id}",
                    "value_shocked", skip))

            rows.append({
                "asof": asof, "framework_version": framework_version,
                "ccy": ccy, "scenario": sc, "option_id": str(r.option_id),
                "position": position, "option_type": str(r.option_type),
                "notional": float(r.notional),
                "strike_rate": float(r.strike_rate), "expiry_years": expiry,
                "forward_rate_base": fwd_base, "rate_shift": shift,
                "floor_rate": floor, "forward_rate_shocked": fwd_shocked,
                "implied_vol_base": vol_base, "vol_expansion": expansion,
                "implied_vol_shocked": vol_shocked,
                "discount_factor_base": float(r.discount_factor_base),
                "discount_factor_shocked": df_shocked,
                "value_base": value_base, "value_shocked": value_shocked,
                "delta_value": delta, "position_weight": weight,
                "weighted_delta_value": weighted,
                "pricing_model": _PRICING_MODEL, "skip_reason": skip,
                "citation": f"{_CITE_2026} 제11항 · 제12항 다",
                "evidence_status": "원문확인" if skip is None else "미확인",
            })

    df = pd.DataFrame(rows, columns=[c.name for c in KR_AUTO_OPTION.columns])
    floats = ["notional", "strike_rate", "expiry_years", "forward_rate_base",
              "rate_shift", "floor_rate", "forward_rate_shocked",
              "implied_vol_base", "vol_expansion", "implied_vol_shocked",
              "discount_factor_base", "discount_factor_shocked", "value_base",
              "value_shocked", "delta_value", "position_weight",
              "weighted_delta_value"]
    return df.astype({c: "float64" for c in floats}), warns


def build_kr_auto_option_risk(
    detail: pd.DataFrame, *, asof: str,
    framework_version: str = KR_FRAMEWORK_2026,
) -> pd.DataFrame:
    """제11항 총리스크. 매도 가치변동 합에서 매수 가치변동 합을 차감한다.

    차감은 `position_weight`(매도 +1 · 매수 −1)를 곱해 더하는 것으로 끝난다.
    부호가 원장에 있으므로 이 함수에는 +1도 −1도 없다.

    한 건이라도 재평가를 건너뛰었으면 `is_complete=False`다. 그 상태의 합계를
    제13항 ΔEVE에 더하면 옵션리스크가 과소계상된다.
    """
    rows = []
    sold, bought = KR_OPTION_POSITIONS
    for (ccy, sc), grp in detail.groupby(["ccy", "scenario"], sort=True):
        priced = grp[grp["skip_reason"].isna()]
        n_skip = len(grp) - len(priced)
        complete = n_skip == 0 and not grp.empty
        s_sum = b_sum = total = None
        if not priced.empty:
            s_sum = float(priced.loc[priced["position"] == sold,
                                     "delta_value"].sum())
            b_sum = float(priced.loc[priced["position"] == bought,
                                     "delta_value"].sum())
            total = float(priced["weighted_delta_value"].sum())
        rows.append({
            "asof": asof, "framework_version": framework_version,
            "ccy": str(ccy), "scenario": str(sc),
            "n_options": len(grp), "n_priced": len(priced),
            "n_skipped": n_skip,
            "sold_delta_sum": s_sum, "bought_delta_sum": b_sum,
            "auto_option_risk": total, "is_complete": complete,
            "vol_expansion": _num(grp["vol_expansion"].iloc[0]),
            "citation": f"{_CITE_2026} 제11항",
            "evidence_status": "원문확인" if complete else "미확인",
        })
    df = pd.DataFrame(rows, columns=[c.name for c in KR_AUTO_OPTION_RISK.columns])
    return df.astype({
        "n_options": "int64", "n_priced": "int64", "n_skipped": "int64",
        "sold_delta_sum": "float64", "bought_delta_sum": "float64",
        "auto_option_risk": "float64", "vol_expansion": "float64",
        "is_complete": "bool"})


# ---------------------------------------------------------------- 관리체계

def build_kr_irrbb_governance(
    records: pd.DataFrame | None = None,
    *,
    asof: str,
    framework_version: str = KR_FRAMEWORK_2026,
) -> tuple[pd.DataFrame, list[ParamWarning]]:
    """제15~20항 관리체계 요구사항 추적 원장.

    요구사항 9건은 규정에서 오고, 이행 실적은 수기입력(`records`)에서 온다.
    실적이 없는 요구사항은 `is_fulfilled`가 NULL이며 False가 아니다. 미입력을
    미이행으로 적으면 없는 사실을 만드는 것이고, 미이행을 미입력으로 적으면
    있는 사실을 지우는 것이다.

    주기가 횟수로 적힌 요구사항(제15항 연 2회 이상, 제16항 나 분기 1회 이상)은
    엔진이 횟수로 판정한다. 실적 기간이 연간이 아니면 판정을 보류하고 사유를
    남긴다.

    `records` 컬럼: `requirement_code`·`period_label`·`count_in_period`·
    `is_annual_period`·`last_fulfilled_date`·`evidence_ref`·`is_fulfilled`.
    """
    warns: list[ParamWarning] = []
    by_code: dict[str, object] = {}
    if records is not None and not records.empty:
        known = {code for code, *_ in KR_GOVERNANCE_REQUIREMENTS}
        unknown = sorted({str(c) for c in records["requirement_code"]} - known)
        if unknown:
            raise ValueError(
                f"이행 실적에 미지의 요구사항 코드 {unknown}. 규정 요구사항은 "
                f"{sorted(known)}이다")
        by_code = {str(r.requirement_code): r for r in records.itertuples()}

    rows = []
    for code, clause, requirement, body, freq, min_n in KR_GOVERNANCE_REQUIREMENTS:
        rec = by_code.get(code)
        period = count = annual = last = evidence_ref = None
        declared: bool | None = None
        if rec is not None:
            period = getattr(rec, "period_label", None)
            period = None if period is None or pd.isna(period) else str(period)
            c = _num(getattr(rec, "count_in_period", None))
            count = None if c is None else int(c)
            annual = _tri(getattr(rec, "is_annual_period", None))
            last = getattr(rec, "last_fulfilled_date", None)
            last = None if last is None or pd.isna(last) else str(last)
            evidence_ref = getattr(rec, "evidence_ref", None)
            evidence_ref = None if evidence_ref is None or pd.isna(evidence_ref) \
                else str(evidence_ref)
            declared = _tri(getattr(rec, "is_fulfilled", None))

        if rec is None:
            verdict, reason = None, "이행 실적이 입력되지 않았다"
            warns.append(ParamWarning(
                "kr_irrbb_governance", code, "records",
                "이행 실적이 입력되지 않았다. 이행 여부를 판정하지 않는다"))
        elif min_n is None:
            verdict = declared
            reason = ("입력된 이행 여부를 그대로 싣는다. 횟수로 판정하는 "
                      "요구사항이 아니다" if declared is not None
                      else "이행 여부가 입력되지 않았다")
            if declared is None:
                warns.append(ParamWarning(
                    "kr_irrbb_governance", code, "is_fulfilled",
                    "이행 여부가 입력되지 않았다"))
        elif count is None:
            verdict, reason = None, "기간 내 이행 횟수가 입력되지 않았다"
            warns.append(ParamWarning(
                "kr_irrbb_governance", code, "count_in_period",
                f"{freq} 요구사항인데 이행 횟수가 비어 있다. 판정하지 않는다"))
        elif annual is not True:
            verdict = None
            reason = (f"실적 기간이 연간이 아니어서 {freq} 판정을 보류한다")
            warns.append(ParamWarning(
                "kr_irrbb_governance", code, "is_annual_period",
                f"실적 기간이 연간이 아니다. {freq} 판정을 보류한다"))
        else:
            verdict = count >= min_n
            reason = (f"연간 이행 횟수 {count}회, 요구 {freq}")

        rows.append({
            "asof": asof, "requirement_code": code,
            "framework_version": framework_version, "clause": clause,
            "requirement": requirement, "responsible_body": body,
            "frequency_text": freq, "min_count_per_year": min_n,
            "period_label": period, "count_in_period": count,
            "is_annual_period": annual, "last_fulfilled_date": last,
            "evidence_ref": evidence_ref, "is_fulfilled": verdict,
            "verdict_reason": reason,
            "citation": f"{_CITE_2026} {clause}",
            "evidence_status": "원문확인" if verdict is not None else "미확인",
        })

    df = pd.DataFrame(rows, columns=[c.name for c in KR_GOVERNANCE.columns])
    return df.astype({"min_count_per_year": "Int64",
                      "count_in_period": "Int64"}), warns


# ================================================================ 폐지된 체계
#
# 아래는 2014년 개정본의 금리 EaR·금리 VaR 산출이다. 2019.11.29 개정으로
# 폐지됐고 헤드라인 산출 경로에서 빠져 있다. 시계열 단절 설명을 위해 남긴다.

KR_SHOCK_METHODS: tuple[str, ...] = ("고정200bp", "5년실측 1%·99%")
KR_ASSET_SHARE_BANDS: tuple[str, ...] = ("5%이상", "5%미만")

# §B-6 측정대상 제외 가능 항목. 이름만 어휘로 고정하고, 어떤 계약이 여기
# 해당하는지는 계약원장이 정한다. 상품코드를 이 모듈에 박으면 원장이 바뀔 때
# 제외가 조용히 어긋난다.
KR_EXCLUDABLE_ITEMS: tuple[str, ...] = (
    "지준예치금", "고정자산", "현금", "주식", "은행간조정자금",
    "자산차감항목", "자본총계", "부채성충당금")

# 통화 합산행의 ccy 표기. 제9항이 통화별 산출 후 합산을 요구하므로 합계가
# 원장의 한 행으로 남아야 한다.
TOTAL_LABEL = "합계"


# ---------------------------------------------------------------- 스펙

KR_BUCKET = TableSpec(
    name="kr_irrbb_bucket", korean="국내기준 만기구간", product="PRD-ALM",
    grain="계정(framework_version) × 만기구간 1행",
    columns=(
        C("framework_version", "string", "계정", nullable=False),
        C("seq", "int", "순서", nullable=False, min_value=1),
        C("label", "string", "만기구간", nullable=False),
        C("lower_years", "float", "하한", nullable=False, unit="years",
          min_value=0.0),
        C("upper_years", "float", "상한", nullable=False, unit="years",
          min_value=0.0),
        C("t_mid_years", "float", "금리개정 중간시점", nullable=False,
          unit="years", min_value=0.0,
          citation=f"{_CITE} <표 2>. 금리 EaR의 (T − t_i)에 쓰는 t_i"),
        C("modified_duration_years", "float", "수정듀레이션", nullable=False,
          unit="years", min_value=0.0,
          citation=f"{_CITE} <표 2>. 은행 자체산출값 사용 가능하나 "
                   f"감독원장 사전승인 필요"),
        C("is_ear_target", "bool", "금리 EaR 대상", nullable=False,
          citation=f"{_CITE} 제7항. 금리 EaR은 만기구간 1년 이하만 대상"),
        C("is_core_deposit_slot", "bool", "핵심예금 안분 대상", nullable=False,
          citation=f"{_CITE} <표 1>. 핵심예금은 5년 이내 8개 만기구간에 "
                   f"12.5%씩 균등 안분"),
        C("citation", "text", "근거", nullable=True),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("framework_version", "seq"),
    note="13구간이며 BCBS d368 Annex 2의 19구간과 다르다. 안분 비율 12.5%는 "
         "여기 숫자로 적지 않는다. is_core_deposit_slot이 8건이라는 사실에서 "
         "엔진이 1/8로 나눈다. 마지막 구간은 20년초과 개방구간이고 원문이 주는 "
         "것은 중간시점 22.5년뿐이므로 상한도 22.5년으로 적는다.",
)

KR_SHOCK_PARAM = TableSpec(
    name="kr_irrbb_shock_param", korean="국내기준 통화별 금리변동 예상폭",
    product="PRD-ALM",
    grain="계정 × 통화 1행",
    columns=(
        C("framework_version", "string", "계정", nullable=False),
        C("ccy", "string", "통화", nullable=False),
        C("asset_share", "float", "총자산 대비 비중", nullable=True,
          unit="ratio", min_value=0.0, max_value=1.0,
          note="은행의 사실이지 규정값이 아니다. 빌더 인자로 들어온다"),
        C("asset_share_band", "string", "총자산 비중 구간", nullable=False,
          allowed=KR_ASSET_SHARE_BANDS),
        C("is_g10", "bool", "G-10 국가통화", nullable=False,
          note="<표 3>은 'G-10 국가통화'라고만 적고 통화를 열거하지 않는다. "
               "5%미만 구간에서는 이 값이 방식을 결정하지 않는다"),
        C("method", "string", "금리변동 예상폭 결정방식", nullable=False,
          allowed=KR_SHOCK_METHODS,
          citation=f"{_CITE} <표 3>"),
        C("shock_bp", "float", "금리변동 예상폭", nullable=True, unit="bp",
          note="method='5년실측 1%·99%'인데 시계열 산출값이 없으면 NULL이다. "
               "다른 줄의 200bp를 끌어다 채우지 않는다"),
        C("citation", "text", "근거", nullable=True),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("framework_version", "ccy"),
    note="원화는 G-10 국가통화가 아니고 총자산 5% 이상이므로 <표 3> 둘째 줄에 "
         "걸린다. 즉 고정 bp가 없고 과거 5년 실제 금리변동폭 분포의 1%·99% "
         "값이며, 규정이 숫자를 주지 않으므로 shock_bp는 NULL로 남는다.",
)

KR_CORE_DEPOSIT_WEIGHT = TableSpec(
    name="kr_core_deposit_weight", korean="핵심예금 기간가중치",
    product="PRD-ALM",
    grain="계정 × 시차(월) 1행",
    columns=(
        C("framework_version", "string", "계정", nullable=False),
        C("lag_months", "int", "시차(월)", nullable=False, min_value=0),
        C("month_label", "string", "해당월", nullable=False),
        C("weight", "float", "기간가중치", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0,
          citation=f"{_CITE} <표 5>. t-11월 1/78 … t월 12/78, 가중치 계 1"),
        C("citation", "text", "근거", nullable=True),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("framework_version", "lag_months"),
    note="가중치를 산식 안에 두지 않고 원장 행으로 둔다. 12행의 합이 1이라는 "
         "것이 검증 대상이 되려면 값이 보여야 한다.",
)

KR_CORE_DEPOSIT = TableSpec(
    name="kr_core_deposit", korean="핵심예금 산출", product="PRD-ALM",
    grain="기준일 × 통화 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("ccy", "string", "통화", nullable=False),
        C("scope", "text", "대상 예금", nullable=False,
          citation=f"{_CITE} <표 5>. 요구불예금·자유저축예금·기업자유예금"
                   f"(MMDA 제외)·어음관리계좌수탁금"),
        C("n_months", "int", "투입 월수", nullable=False, min_value=1),
        C("latest_month_avg_balance", "float", "최근월 평잔", nullable=False,
          unit="KRW", min_value=0.0),
        C("weighted_mean", "float", "기간가중평균", nullable=False, unit="KRW",
          min_value=0.0),
        C("weighted_std", "float", "기간가중 표준편차", nullable=False,
          unit="KRW", min_value=0.0),
        C("multiplier", "float", "표준편차 배수", nullable=False, unit="배",
          min_value=0.0,
          citation=f"{_CITE} <표 5>. 최근월 평잔에서 연간 표준편차의 2.33배 차감"),
        C("core_amount", "float", "핵심예금", nullable=False, unit="KRW",
          min_value=0.0),
        C("non_core_amount", "float", "비핵심예금", nullable=False, unit="KRW",
          min_value=0.0),
        C("core_ratio", "float", "핵심예금 비율", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("is_floored", "bool", "0 절사 여부", nullable=False,
          note="산식이 음수를 낼 수 있다. 음수 핵심예금은 안분이 정의되지 "
               "않으므로 0으로 자르고 그 사실을 여기 남긴다"),
        C("std_formula", "text", "표준편차 산식", nullable=False,
          note="<표 5>의 기간가중표준편차 산식은 HWP 본문에 이미지로 들어 있어 "
               "추출되지 않았다. 원문이 준 기간가중평균과 정합한 형태를 쓴다"),
        C("citation", "text", "근거", nullable=True),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("asof", "ccy"),
    note="월중평잔 12개월치가 입력이다. 12개월이 차지 않은 통화는 행을 만들지 "
         "않고 경고를 남긴다. 모자란 개월수로 계산한 표준편차는 규정 산식이 "
         "아니다.",
)

KR_GAP = TableSpec(
    name="kr_irrbb_gap", korean="국내기준 만기구간별 금리갭", product="PRD-ALM",
    grain="기준일 × 계정 × 통화 × 만기구간 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("framework_version", "string", "계정", nullable=False),
        C("ccy", "string", "통화", nullable=False),
        C("seq", "int", "순서", nullable=False, min_value=1),
        C("label", "string", "만기구간", nullable=False),
        C("rate_sensitive_asset", "float", "금리민감자산", nullable=False,
          unit="KRW", min_value=0.0),
        C("rate_sensitive_liability", "float", "금리민감부채", nullable=False,
          unit="KRW", min_value=0.0),
        C("gap_amount", "float", "금리갭", nullable=False, unit="KRW",
          citation=f"{_CITE} 제7항. 금리갭 = 금리민감자산 − 금리민감부채"),
        C("citation", "text", "근거", nullable=True),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("asof", "framework_version", "ccy", "seq"),
    foreign_keys=(FK(("framework_version", "seq"), "kr_irrbb_bucket",
                     ("framework_version", "seq")),),
    note="통화별로 13구간 전건이 나온다. 잔액이 없는 구간도 0으로 채운다. "
         "사다리에 구멍이 있으면 합산이 조용히 달라진다.",
)

KR_RESULT = TableSpec(
    name="kr_irrbb_result", korean="국내기준 금리리스크 산출결과",
    product="PRD-ALM",
    grain="기준일 × 계정 × 통화 1행 (합계 1행 포함)",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("framework_version", "string", "계정", nullable=False),
        C("framework_status", "string", "계정 상태", nullable=False,
          allowed=KR_FRAMEWORK_STATUSES,
          citation=f"{_CITE} 표제부 개정 연혁. 2014년 체계는 2019.11.29 "
                   f"개정으로 폐지됐다",
          note="이 원장은 폐지된 계정의 산출물이다. 상태가 값과 같은 행에 "
               "실려야 시계열 단절을 설명할 수 있다"),
        C("is_headline", "bool", "헤드라인 산출 여부", nullable=False,
          note="폐지 계정은 항상 False다. 헤드라인 ΔEVE·ΔNII는 alm/irrbb.py와 "
               "alm/nii.py가 산출한다"),
        C("ccy", "string", "통화", nullable=False),
        C("is_total", "bool", "통화 합산행", nullable=False,
          citation=f"{_CITE} 제9항. 통화별로 산출해 합산한다"),
        C("shock_bp", "float", "금리변동 예상폭", nullable=True, unit="bp"),
        C("shock_method", "string", "예상폭 결정방식", nullable=True,
          allowed=KR_SHOCK_METHODS),
        C("horizon_years", "float", "목표 관리기간", nullable=True, unit="years",
          min_value=0.0,
          citation=f"{_CITE} 제7항. 금리 EaR의 T. 원칙 1년"),
        C("ear_amount", "float", "금리 EaR", nullable=True, unit="KRW",
          citation=f"{_CITE} 제7항. Σ 금리갭_i × (T − t_i) × Δr_i, "
                   f"만기구간 1년 이하"),
        C("var_amount", "float", "금리 VaR", nullable=True, unit="KRW",
          citation=f"{_CITE} 제8항. Σ 금리갭_i × 수정듀레이션_i × Δr_i, "
                   f"전 만기구간"),
        C("total_ir_risk", "float", "총 금리리스크", nullable=True, unit="KRW",
          min_value=0.0,
          citation=f"{_CITE} 제27항. 금리 VaR에 의하여 산출한 총 금리리스크"),
        C("own_capital", "float", "자기자본", nullable=True, unit="KRW",
          min_value=0.0,
          citation="세칙 <별표 3>의 자기자본. d368의 기본자본(Tier 1)이 아니다"),
        C("risk_to_own_capital", "float", "자기자본 대비 비율", nullable=True,
          unit="ratio"),
        C("outlier_threshold", "float", "아웃라이어 기준", nullable=True,
          unit="ratio", min_value=0.0,
          citation=f"{_CITE} 제27항. 자기자본의 20% 초과 시 outlier"),
        C("denominator_basis", "string", "판정 분모", nullable=False,
          note="국내기준은 '자기자본', d368은 '기본자본(Tier 1)'이다. 분모가 "
               "다르다는 사실이 컬럼으로 보여야 두 수치가 섞이지 않는다"),
        C("is_outlier", "bool", "아웃라이어", nullable=True,
          note="합계행에서만 판정한다. 통화행은 NULL이다"),
        C("excluded_amount", "float", "측정대상 제외액", nullable=False,
          unit="KRW", min_value=0.0,
          citation=f"{_CITE} 제외항목. 지준예치금·고정자산·현금·주식·"
                   f"은행간조정자금·자본총계·부채성충당금"),
        C("citation", "text", "근거", nullable=True),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("asof", "framework_version", "ccy"),
    note="폐지된 2014년 체계의 산출물이다. 금리 EaR·금리 VaR는 부호 있는 "
         "값이며 금리 상승(+shock_bp) 방향으로 산출한다. 총 금리리스크는 그 "
         "크기다. 세칙이 부호 규약을 정하지 않으므로 판정에 쓰이는 것이 "
         "크기라는 사실을 컬럼으로 나눠 둔다. shock_bp가 NULL인 통화는 행이 "
         "있으되 산출값이 비어 있다.",
)

KR_IRRBB_TABLES: tuple[TableSpec, ...] = (
    KR_BUCKET, KR_SHOCK_PARAM, KR_CORE_DEPOSIT_WEIGHT, KR_CORE_DEPOSIT,
    KR_GAP, KR_RESULT,
)


# ---------------------------------------------------------------- 규제표 적재
#
# 아래 리터럴이 이 모듈에서 숫자가 있는 유일한 구역이다. 엔진 함수는 전부
# 원장을 인자로 받는다.

# <표 2> 만기구간별 금리개정 중간시점 및 수정듀레이션 (13구간).
# (구간, 하한년, 상한년, 금리개정 중간시점, 수정듀레이션)
_M = 1.0 / 12.0
_KR_BUCKETS: tuple[tuple[str, float, float, float, float], ...] = (
    ("0~1월",    0.0,     1 * _M,  0.042,  0.04),
    ("1~3월",    1 * _M,  3 * _M,  0.167,  0.16),
    ("3~6월",    3 * _M,  6 * _M,  0.375,  0.36),
    ("6~12월",   6 * _M,  1.0,     0.75,   0.71),
    ("1~2년",    1.0,     2.0,     1.5,    1.38),
    ("2~3년",    2.0,     3.0,     2.5,    2.25),
    ("3~4년",    3.0,     4.0,     3.5,    3.07),
    ("4~5년",    4.0,     5.0,     4.5,    3.85),
    ("5~7년",    5.0,     7.0,     6.0,    5.08),
    ("7~10년",   7.0,     10.0,    8.5,    6.63),
    ("10~15년",  10.0,    15.0,    12.5,   8.92),
    ("15~20년",  15.0,    20.0,    17.5,   11.21),
    # 개방구간(20년 초과). 원문이 주는 것은 중간시점 22.5년뿐이므로 상한도
    # 같은 값으로 적는다. 임의로 늘리면 원문에 없는 경계를 만드는 것이다.
    ("20년초과", 20.0,    22.5,    22.5,   13.01),
)

# 제7항 T = 목표 관리기간, 원칙 1년. EaR 대상 구간의 경계이기도 하다.
_EAR_HORIZON_YEARS = 1.0
# <표 1> 핵심예금은 5년 이내 8개 만기구간에 균등 안분한다. 8이라는 개수는
# 아래 경계에서 나오고, 12.5%는 그 개수의 역수다.
_CORE_SLOT_LIMIT_YEARS = 5.0

# <표 3> 총자산 비중 경계와 5%미만 통화의 고정 충격폭.
_ASSET_SHARE_THRESHOLD = 0.05
_FIXED_SHOCK_BP = 200.0

# <표 5> 기간가중치와 표준편차 배수.
_CORE_WEIGHT_MONTHS = 12
_CORE_WEIGHT_DENOM = 78.0          # Σ_{k=1..12} k
_CORE_MULTIPLIER = 2.33

# 2014년 체계 제27항 아웃라이어 기준. 자기자본의 20%. 현행 제21항은 기본자본
# 15%이므로 두 값을 같은 칸에 넣지 않는다.
_OUTLIER_PCT_OWN_CAPITAL = 0.20
# 이 구역의 산출물은 전부 폐지 계정이다. 문자열을 행마다 다시 적지 않는다.
_LEGACY_STATUS = KR_FRAMEWORK_STATUSES[1]
_DENOMINATOR_BASIS = "자기자본(세칙 <별표 3>)"

_CORE_SCOPE = ("요구불예금·자유저축예금·기업자유예금(MMDA 제외)·"
               "어음관리계좌수탁금")
_STD_FORMULA = "sqrt(Σ w_i · (x_i − Σ w_j·x_j)^2), Σ w = 1"


def build_kr_irrbb_bucket() -> pd.DataFrame:
    """<표 2> 13개 만기구간 원장.

    금리개정 중간시점과 수정듀레이션이 여기서만 나온다. 엔진은 seq로 조인해
    읽을 뿐이므로 값을 고치면 산출이 반드시 따라 움직인다.
    """
    rows = []
    for seq, (label, lo, hi, t_mid, md) in enumerate(_KR_BUCKETS, start=1):
        rows.append({
            "framework_version": KR_FRAMEWORK_2014,
            "seq": seq,
            "label": label,
            "lower_years": float(lo),
            "upper_years": float(hi),
            "t_mid_years": float(t_mid),
            "modified_duration_years": float(md),
            "is_ear_target": float(hi) <= _EAR_HORIZON_YEARS,
            "is_core_deposit_slot": float(hi) <= _CORE_SLOT_LIMIT_YEARS,
            "citation": f"{_CITE} <표 2>",
            "evidence_status": "원문확인",
        })
    return pd.DataFrame(rows)


def build_kr_irrbb_shock_param(
    asset_share_by_ccy: Mapping[str, float],
    *,
    g10_ccys: Sequence[str] = (),
    measured_shock_bp: Mapping[str, float] | None = None,
) -> pd.DataFrame:
    """<표 3> 통화별 금리변동 예상폭 원장.

    총자산 대비 비중(`asset_share_by_ccy`)과 G-10 여부는 **은행의 사실**이므로
    인자로 받는다. 규정이 정하는 것은 그 사실에서 어느 방식이 걸리는지다.

      · 5% 미만                → 전 만기구간 ±200bp (셋째 줄)
      · 5% 이상 · G-10         → ±200bp 또는 5년 실측 1%·99% (첫째 줄, 선택)
      · 5% 이상 · G-10 이외    → 5년 실측 1%·99%만 (둘째 줄)

    셋째 줄만 규정이 숫자를 준다. 둘째 줄에 걸리는 통화(원화가 여기다)는
    `measured_shock_bp`로 산출값을 넘기지 않으면 `shock_bp`가 NULL로 남고,
    엔진은 그 통화를 비운다. `<표 3>`은 'G-10 국가통화'라고만 적고 통화를
    열거하지 않으므로 목록도 인자로 받는다. 열거는 원문에 없다.
    """
    measured = dict(measured_shock_bp or {})
    g10 = {str(c) for c in g10_ccys}
    rows = []
    for ccy in sorted(asset_share_by_ccy):
        share = float(asset_share_by_ccy[ccy])
        big = share >= _ASSET_SHARE_THRESHOLD
        band = "5%이상" if big else "5%미만"
        is_g10 = ccy in g10
        if not big:
            method, shock_bp = "고정200bp", _FIXED_SHOCK_BP
            cite = f"{_CITE} <표 3> 셋째 줄. 총자산 5% 미만 통화 ±200bp"
        elif is_g10:
            # 첫째 줄은 두 방식을 허용한다. 은행이 실측값을 넘겼으면 그것을,
            # 아니면 규정이 명시한 200bp를 쓴다. 어느 쪽인지 method가 남긴다.
            if ccy in measured:
                method, shock_bp = "5년실측 1%·99%", float(measured[ccy])
                cite = f"{_CITE} <표 3> 첫째 줄. 5년 실측 1%·99% 선택"
            else:
                method, shock_bp = "고정200bp", _FIXED_SHOCK_BP
                cite = f"{_CITE} <표 3> 첫째 줄. ±200bp 선택"
        else:
            method = "5년실측 1%·99%"
            shock_bp = float(measured[ccy]) if ccy in measured else None
            cite = (f"{_CITE} <표 3> 둘째 줄. 총자산 5% 이상 · G-10 이외 "
                    f"통화는 과거 5년 실제 금리변동폭(보유기간 1년) 분포의 "
                    f"1%·99% 값. 규정이 숫자를 주지 않는다")
        rows.append({
            "framework_version": KR_FRAMEWORK_2014,
            "ccy": ccy,
            "asset_share": share,
            "asset_share_band": band,
            "is_g10": is_g10,
            "method": method,
            "shock_bp": shock_bp,
            "citation": cite,
            "evidence_status": "원문확인" if shock_bp is not None else "미확인",
        })
    df = pd.DataFrame(rows)
    return df.astype({"asset_share": "float64", "shock_bp": "float64"})


def build_kr_core_deposit_weight() -> pd.DataFrame:
    """<표 5> 기간가중치 12행. t-11월 1/78 … t월 12/78, 합 1."""
    rows = []
    for lag in range(_CORE_WEIGHT_MONTHS):
        rows.append({
            "framework_version": KR_FRAMEWORK_2014,
            "lag_months": lag,
            "month_label": "t월" if lag == 0 else f"t-{lag}월",
            "weight": (_CORE_WEIGHT_MONTHS - lag) / _CORE_WEIGHT_DENOM,
            "citation": f"{_CITE} <표 5> 기간가중치 적용 방법",
            "evidence_status": "원문확인",
        })
    return pd.DataFrame(rows)


def build_kr_core_deposit(
    monthly_balance: pd.DataFrame,
    weights: pd.DataFrame,
    *,
    asof: str,
) -> tuple[pd.DataFrame, list[ParamWarning]]:
    """<표 5> 핵심예금 산출.

    `CORE = 최근월평잔 − 최근 12개월 월중평잔의 기간가중 표준편차 × 2.33`

    `monthly_balance`는 요구불성예금 월중평잔이며 컬럼은
    `ccy`·`lag_months`(0 = t월)·`avg_balance`다. 12개월이 차지 않은 통화는
    행을 만들지 않고 경고를 남긴다. 개월수를 줄여 계산한 표준편차는 규정
    산식이 아니다.

    배수 2.33과 가중치는 원장(`weights`)에서 오고, 이 함수는 산식만 돈다.
    """
    warns: list[ParamWarning] = []
    w = weights.sort_values("lag_months")
    w_map = {int(r.lag_months): float(r.weight) for r in w.itertuples()}
    w_sum = sum(w_map.values())
    if not math.isclose(w_sum, 1.0, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError(
            f"kr_core_deposit_weight의 가중치 합이 {w_sum!r}이다. <표 5>는 "
            "가중치 계 1을 명시한다")

    rows = []
    for ccy, grp in monthly_balance.groupby("ccy", sort=True):
        lags = {int(v) for v in grp["lag_months"]}
        if lags != set(w_map):
            warns.append(ParamWarning(
                "core_deposit", str(ccy), "monthly_balance",
                f"월중평잔이 {len(lags)}개월치다. <표 5>는 최근 12개월 전건을 "
                f"요구한다. 핵심예금을 산출하지 않는다"))
            continue
        bal = {int(r.lag_months): float(r.avg_balance) for r in grp.itertuples()}
        mean = sum(w_map[k] * bal[k] for k in w_map)
        var = sum(w_map[k] * (bal[k] - mean) ** 2 for k in w_map)
        std = math.sqrt(var)
        latest = bal[0]
        raw = latest - std * _CORE_MULTIPLIER
        floored = raw < 0.0
        if floored:
            warns.append(ParamWarning(
                "core_deposit", str(ccy), "core_amount",
                f"산식 결과가 음수({raw:,.0f})다. 음수 핵심예금은 안분이 "
                f"정의되지 않으므로 0으로 자른다"))
        core = max(raw, 0.0)
        rows.append({
            "asof": asof, "ccy": str(ccy), "scope": _CORE_SCOPE,
            "n_months": len(bal),
            "latest_month_avg_balance": latest,
            "weighted_mean": mean, "weighted_std": std,
            "multiplier": _CORE_MULTIPLIER,
            "core_amount": core, "non_core_amount": latest - core,
            "core_ratio": (core / latest) if latest > 0.0 else 0.0,
            "is_floored": floored,
            "std_formula": _STD_FORMULA,
            "citation": f"{_CITE} <표 5> 핵심예금 산출 기준 <신설 2014.12.26>",
            "evidence_status": "원문확인",
        })
    cols = [c.name for c in KR_CORE_DEPOSIT.columns]
    df = pd.DataFrame(rows, columns=cols)
    floats = ["latest_month_avg_balance", "weighted_mean", "weighted_std",
              "multiplier", "core_amount", "non_core_amount", "core_ratio"]
    return df.astype({c: "float64" for c in floats} | {"n_months": "int64",
                                                       "is_floored": "bool"}), warns


# ---------------------------------------------------------------- 갭 사다리

def _slot_index(uppers: np.ndarray, t_years: float) -> int:
    """금리개정 시점 → 만기구간 위치. 경계 규약은 (하한, 상한] 이다.

    상한을 넘어선 시점은 마지막(개방)구간으로 간다. 음수는 이미 개정시점이
    지난 것이므로 최단구간이다.
    """
    idx = int(np.searchsorted(uppers, t_years, side="left"))
    return min(max(idx, 0), len(uppers) - 1)


def build_kr_irrbb_gap(
    contracts: pd.DataFrame,
    buckets: pd.DataFrame,
    *,
    asof: str,
    core_deposit: pd.DataFrame,
    exclude_product_codes: Mapping[str, str] | None = None,
    core_scope_product_codes: Sequence[str] | None = None,
    day_count: str = "ACT/365F",
) -> tuple[pd.DataFrame, pd.DataFrame, list[ParamWarning]]:
    """계약원장 → 만기구간별 금리민감자산·부채·금리갭.

    슬로팅 규칙은 <표 1>을 따른다.
      · 차기 금리개정일이 있으면 그 시점, 없으면 만기일
      · 비만기예금은 핵심/비핵심으로 나눠 핵심은 5년 이내 8구간 균등 안분,
        비핵심은 최단구간

    제외항목(§B-6)은 갭에 들어가지 않고 두 번째 반환값에 금액으로 남는다.
    조용히 사라지면 사다리 합계가 대차대조표와 어긋난 이유를 찾을 수 없다.
    계약원장은 자기자본만 플래그로 들고 있으므로 나머지 제외항목은
    `exclude_product_codes`(상품코드 → 제외항목명)로 넘긴다.

    반환: (갭 원장, 제외액 프레임, 경고)
    """
    if day_count not in DAY_COUNTS:
        raise ValueError(f"미지원 이자계산 관행 {day_count!r}. {DAY_COUNTS}")
    warns: list[ParamWarning] = []
    b = buckets.sort_values("seq").reset_index(drop=True)
    uppers = b["upper_years"].to_numpy(dtype=float)
    seqs = b["seq"].to_numpy(dtype=int)
    labels = {int(r.seq): str(r.label) for r in b.itertuples()}
    core_seqs = [int(s) for s in b.loc[b["is_core_deposit_slot"].astype(bool),
                                       "seq"]]
    if not core_seqs:
        raise ValueError("kr_irrbb_bucket에 is_core_deposit_slot 행이 없다. "
                         "핵심예금 안분 대상 구간이 정해지지 않았다")
    core_share = 1.0 / len(core_seqs)
    shortest_seq = int(seqs[0])

    excl_map = dict(exclude_product_codes or {})
    core_scope = None if core_scope_product_codes is None else {
        str(c) for c in core_scope_product_codes}
    if core_scope is None:
        warns.append(ParamWarning(
            "kr_gap", "핵심예금 대상", "core_scope_product_codes",
            "<표 5> 대상 예금(요구불성예금) 상품코드를 받지 못했다. 비만기 "
            "부채 전부에 핵심예금 비율을 적용한다"))

    core_ratio = {str(r.ccy): float(r.core_ratio)
                  for r in core_deposit.itertuples()}

    asof_d = date.fromisoformat(asof)
    con = contracts[contracts["asof"] == asof]
    bad = sorted({str(s) for s in con["side"]} - set(SIDES))
    if bad:
        raise ValueError(f"alm_contract.side에 미지의 값 {bad}")
    if (con["side"] == "off_balance").any():
        raise ValueError(
            "부외(off_balance) 계약이 있다. <표 1>은 파생상품을 기초자산으로 "
            "분해한 뒤 분류하도록 정한다. 분해 없이 갭에 넣지 않는다")

    acc: dict[tuple[str, int, str], float] = {}
    excl: dict[tuple[str, str], list[float]] = {}
    ccys: set[str] = set()
    warned_ccy: set[str] = set()

    def _add(ccy: str, seq: int, side: str, amt: float) -> None:
        key = (ccy, seq, side)
        acc[key] = acc.get(key, 0.0) + amt

    for r in con.itertuples():
        ccy, side = str(r.ccy), str(r.side)
        notional = float(r.notional)
        ccys.add(ccy)
        item = "자본총계" if bool(r.is_own_equity) else excl_map.get(
            str(r.product_code))
        if item is not None:
            if item not in KR_EXCLUDABLE_ITEMS:
                raise ValueError(
                    f"제외항목 {item!r}은 [별표 9의1]의 제외 가능 항목이 "
                    f"아니다. {KR_EXCLUDABLE_ITEMS}")
            excl.setdefault((ccy, item), []).append(notional)
            continue

        reset = getattr(r, "next_reset_date", None)
        mat = getattr(r, "maturity_date", None)
        anchor = reset if (reset is not None and not pd.isna(reset)) else (
            mat if (mat is not None and not pd.isna(mat)) else None)
        if anchor is not None:
            t = year_fraction(asof_d, date.fromisoformat(str(anchor)), day_count)
            _add(ccy, int(seqs[_slot_index(uppers, t)]), side, notional)
            continue

        # 비만기 계약. 자산 쪽 비만기는 <표 1>에 핵심/비핵심 개념이 없으므로
        # 최단구간으로 둔다. 부채 쪽만 핵심예금 분해 대상이다.
        if side != "liability":
            _add(ccy, shortest_seq, side, notional)
            continue
        in_scope = core_scope is None or str(r.product_code) in core_scope
        ratio = core_ratio.get(ccy)
        if in_scope and ratio is None:
            if ccy not in warned_ccy:
                warns.append(ParamWarning(
                    "kr_gap", ccy, "core_ratio",
                    "kr_core_deposit에 해당 통화 행이 없다. 핵심예금을 "
                    "산출하지 못했으므로 전액 비핵심(최단구간)으로 분류한다"))
                warned_ccy.add(ccy)
            ratio = 0.0
        elif not in_scope:
            ratio = 0.0
        core_amt = notional * float(ratio)
        for s in core_seqs:
            _add(ccy, s, side, core_amt * core_share)
        _add(ccy, shortest_seq, side, notional - core_amt)

    rows = []
    for ccy in sorted(ccys):
        for seq in seqs:
            a = acc.get((ccy, int(seq), "asset"), 0.0)
            l = acc.get((ccy, int(seq), "liability"), 0.0)
            rows.append({
                "asof": asof, "framework_version": KR_FRAMEWORK_2014,
                "ccy": ccy, "seq": int(seq), "label": labels[int(seq)],
                "rate_sensitive_asset": a, "rate_sensitive_liability": l,
                "gap_amount": a - l,
                "citation": f"{_CITE} <표 1> 만기구분 · 제7항 금리갭",
                "evidence_status": "원문확인",
            })
    gap = pd.DataFrame(rows, columns=[c.name for c in KR_GAP.columns])
    gap = gap.astype({"rate_sensitive_asset": "float64",
                      "rate_sensitive_liability": "float64",
                      "gap_amount": "float64", "seq": "int64"})

    excl_rows = [{"asof": asof, "ccy": ccy, "item": item,
                  "amount": float(sum(v)), "n_contracts": len(v)}
                 for (ccy, item), v in sorted(excl.items())]
    excluded = pd.DataFrame(
        excl_rows, columns=["asof", "ccy", "item", "amount", "n_contracts"])
    return gap, excluded.astype({"amount": "float64"}), warns


# ---------------------------------------------------------------- 엔진
#
# 아래 세 함수에는 숫자가 없다. 중간시점·수정듀레이션·EaR 대상 여부는 전부
# 버킷 원장에서 오고, 충격폭과 관리기간은 인자다.

def ear_horizon_years(buckets: pd.DataFrame) -> float:
    """목표 관리기간 T를 원장에서 읽는다.

    제7항의 T(원칙 1년)는 EaR 대상 만기구간의 경계와 같은 값이다. 상수를
    다시 적으면 원장과 산식이 갈라질 수 있으므로 원장에서 파생시킨다.
    """
    tgt = buckets[buckets["is_ear_target"].astype(bool)]
    if tgt.empty:
        raise ValueError("kr_irrbb_bucket에 is_ear_target 행이 없다. "
                         "금리 EaR의 대상 구간이 정해지지 않았다")
    return float(tgt["upper_years"].max())


def _join(gap: pd.DataFrame, buckets: pd.DataFrame) -> pd.DataFrame:
    """갭 사다리에 버킷 계수를 붙인다. 단일 통화 사다리를 전제한다."""
    if gap["seq"].duplicated().any():
        raise ValueError("금리갭이 통화 하나의 사다리가 아니다. seq가 중복이다")
    cols = ["seq", "t_mid_years", "modified_duration_years", "is_ear_target"]
    d = gap.merge(buckets[cols], on="seq", how="left", validate="one_to_one")
    miss = d["t_mid_years"].isna()
    if miss.any():
        raise KeyError(
            f"kr_irrbb_bucket에 없는 만기구간 {sorted(d.loc[miss, 'seq'])}")
    return d


def kr_ear(gap: pd.DataFrame, buckets: pd.DataFrame, *,
           shock_bp: float, horizon_years: float) -> float:
    """금리 EaR = Σ 금리갭_i × (T − t_i) × Δr_i, 만기구간 1년 이하만.

    대상 구간은 버킷 원장의 `is_ear_target`이 정한다. 1년 초과 구간의 갭이
    아무리 커도 이 값은 움직이지 않는다.
    """
    d = _join(gap, buckets)
    d = d[d["is_ear_target"].astype(bool)]
    return float((d["gap_amount"]
                  * (horizon_years - d["t_mid_years"])
                  * (shock_bp * _BP)).sum())


def kr_var(gap: pd.DataFrame, buckets: pd.DataFrame, *,
           shock_bp: float) -> float:
    """금리 VaR = Σ 금리갭_i × 수정듀레이션_i × Δr_i, 전 만기구간."""
    d = _join(gap, buckets)
    return float((d["gap_amount"]
                  * d["modified_duration_years"]
                  * (shock_bp * _BP)).sum())


# ---------------------------------------------------------------- 결과 원장

def build_kr_irrbb_result(
    gap: pd.DataFrame,
    buckets: pd.DataFrame,
    shock_param: pd.DataFrame,
    *,
    asof: str,
    own_capital: float,
    excluded: pd.DataFrame | None = None,
    horizon_years: float | None = None,
    outlier_threshold: float | None = None,
) -> tuple[pd.DataFrame, list[ParamWarning]]:
    """통화별 금리 EaR·금리 VaR와 합계행, 자기자본 대비 아웃라이어 판정.

    **폐지된 체계다.** 2019.11.29 개정으로 ΔEVE·ΔNII 체계로 전환됐으므로
    산출물마다 `framework_status='폐지'`와 경고 한 건이 따라 나간다. 이 값을
    현행 규제수치로 보고하면 안 된다.

    `shock_bp`가 NULL인 통화는 행이 남되 산출값이 비고 경고가 붙는다. 다른
    통화의 200bp를 대입하지 않는다.

    아웃라이어 판정은 **합계행에서만** 한다. 2014년 체계 제27항의 기준은
    자기자본의 20%이며 현행 제21항의 기본자본 15%와 분모·비율이 모두 다르다.
    그 사실이 `denominator_basis`·`outlier_threshold` 컬럼으로 남는다.
    """
    if not own_capital > 0.0:
        raise ValueError(
            f"자기자본이 {own_capital!r}이다. 0 이하로는 자기자본 대비 비율이 "
            "정의되지 않는다")
    warns: list[ParamWarning] = [ParamWarning(
        "kr_irrbb", KR_FRAMEWORK_2014, "framework_version",
        KR_LEGACY_REPEAL_NOTE)]
    T = ear_horizon_years(buckets) if horizon_years is None else float(
        horizon_years)
    thr = (_OUTLIER_PCT_OWN_CAPITAL if outlier_threshold is None
           else float(outlier_threshold))

    sp = shock_param[shock_param["framework_version"] == KR_FRAMEWORK_2014]
    sp_by_ccy = {str(r.ccy): r for r in sp.itertuples()}
    excl_by_ccy: dict[str, float] = {}
    if excluded is not None and not excluded.empty:
        excl_by_ccy = {str(k): float(v) for k, v in
                       excluded.groupby("ccy")["amount"].sum().items()}

    rows = []
    tot_ear = tot_var = 0.0
    n_priced = 0
    for ccy in sorted({str(c) for c in gap["ccy"]}):
        sub = gap[gap["ccy"] == ccy]
        p = sp_by_ccy.get(ccy)
        ear = var = None
        shock_bp = method = None
        if p is None:
            warns.append(ParamWarning(
                "kr_irrbb", ccy, "shock_bp",
                "kr_irrbb_shock_param에 해당 통화 행이 없다. 산출하지 않는다"))
        else:
            method = str(p.method)
            if pd.isna(p.shock_bp):
                warns.append(ParamWarning(
                    "kr_irrbb", ccy, "shock_bp",
                    f"금리변동 예상폭이 비어 있다(method={method}). <표 3>이 "
                    f"숫자를 주지 않는 구간이다. 시계열 산출값 없이는 "
                    f"산출하지 않으며 다른 통화의 200bp를 대입하지 않는다"))
            else:
                shock_bp = float(p.shock_bp)
                ear = kr_ear(sub, buckets, shock_bp=shock_bp, horizon_years=T)
                var = kr_var(sub, buckets, shock_bp=shock_bp)
                tot_ear += ear
                tot_var += var
                n_priced += 1
        rows.append({
            "asof": asof, "framework_version": KR_FRAMEWORK_2014,
            "framework_status": _LEGACY_STATUS,
            "is_headline": KR_IS_HEADLINE[KR_FRAMEWORK_2014],
            "ccy": ccy, "is_total": False,
            "shock_bp": shock_bp, "shock_method": method,
            "horizon_years": T if ear is not None else None,
            "ear_amount": ear, "var_amount": var,
            "total_ir_risk": None if var is None else abs(var),
            "own_capital": None, "risk_to_own_capital": None,
            "outlier_threshold": None,
            "denominator_basis": _DENOMINATOR_BASIS,
            "is_outlier": None,
            "excluded_amount": excl_by_ccy.get(ccy, 0.0),
            "citation": f"{_CITE} 제7·8항",
            "evidence_status": "원문확인" if shock_bp is not None else "미확인",
        })

    total_risk = abs(tot_var) if n_priced else None
    ratio = None if total_risk is None else total_risk / own_capital
    rows.append({
        "asof": asof, "framework_version": KR_FRAMEWORK_2014,
        "framework_status": _LEGACY_STATUS,
        "is_headline": KR_IS_HEADLINE[KR_FRAMEWORK_2014],
        "ccy": TOTAL_LABEL, "is_total": True,
        "shock_bp": None, "shock_method": None,
        "horizon_years": T if n_priced else None,
        "ear_amount": tot_ear if n_priced else None,
        "var_amount": tot_var if n_priced else None,
        "total_ir_risk": total_risk,
        "own_capital": float(own_capital),
        "risk_to_own_capital": ratio,
        "outlier_threshold": thr,
        "denominator_basis": _DENOMINATOR_BASIS,
        # 제27항은 "초과하는 은행"이라고 적는다. 경계값은 아웃라이어가 아니다.
        "is_outlier": None if ratio is None else bool(ratio > thr),
        "excluded_amount": float(sum(excl_by_ccy.values())),
        "citation": f"{_CITE} 제9항 통화별 합산 · 제27항 아웃라이어",
        "evidence_status": "원문확인" if n_priced else "미확인",
    })
    if not n_priced:
        warns.append(ParamWarning(
            "kr_irrbb", TOTAL_LABEL, "total_ir_risk",
            "산출된 통화가 하나도 없다. 합계와 아웃라이어 판정을 비운다"))

    df = pd.DataFrame(rows, columns=[c.name for c in KR_RESULT.columns])
    floats = ["shock_bp", "horizon_years", "ear_amount", "var_amount",
              "total_ir_risk", "own_capital", "risk_to_own_capital",
              "outlier_threshold", "excluded_amount"]
    return df.astype({c: "float64" for c in floats} | {"is_headline": "bool"}), warns


# ---------------------------------------------------------------- 결과 객체

@dataclass
class KrIrrbbResult:
    """국내기준 산출 결과. 원장 두 장과 제외액, 그리고 경고."""
    gap: pd.DataFrame                    # kr_irrbb_gap
    result: pd.DataFrame                 # kr_irrbb_result
    excluded: pd.DataFrame               # 측정대상 제외액
    warnings: list[ParamWarning] = field(default_factory=list)

    @property
    def total_row(self) -> pd.Series:
        hit = self.result[self.result["is_total"].astype(bool)]
        if len(hit) != 1:
            raise ValueError(f"합계행이 {len(hit)}건이다. 정확히 1건이어야 한다")
        return hit.iloc[0]

    @property
    def total_ir_risk(self) -> float | None:
        v = self.total_row["total_ir_risk"]
        return None if pd.isna(v) else float(v)

    @property
    def risk_to_own_capital(self) -> float | None:
        v = self.total_row["risk_to_own_capital"]
        return None if pd.isna(v) else float(v)

    def outlier(self) -> bool | None:
        """제27항 판정. 산출된 통화가 없으면 None이며 False가 아니다."""
        v = self.total_row["is_outlier"]
        return None if pd.isna(v) else bool(v)

    def warning_frame(self) -> pd.DataFrame:
        return pd.DataFrame([{"model": w.model, "scope": w.scope,
                              "param": w.param, "reason": w.reason}
                             for w in self.warnings],
                            columns=["model", "scope", "param", "reason"])


def compute_kr_irrbb(
    contracts: pd.DataFrame,
    buckets: pd.DataFrame,
    shock_param: pd.DataFrame,
    *,
    asof: str,
    own_capital: float,
    core_deposit: pd.DataFrame,
    exclude_product_codes: Mapping[str, str] | None = None,
    core_scope_product_codes: Sequence[str] | None = None,
    horizon_years: float | None = None,
    outlier_threshold: float | None = None,
) -> KrIrrbbResult:
    """계약원장 → 갭 사다리 → 금리 EaR·금리 VaR·아웃라이어 판정.

    난수를 쓰지 않으므로 같은 입력이면 같은 출력이다. (asof, seed)는 계약원장을
    만드는 단계에서 고정되고 이 함수는 그 원장을 읽기만 한다.
    """
    gap, excluded, w1 = build_kr_irrbb_gap(
        contracts, buckets, asof=asof, core_deposit=core_deposit,
        exclude_product_codes=exclude_product_codes,
        core_scope_product_codes=core_scope_product_codes)
    result, w2 = build_kr_irrbb_result(
        gap, buckets, shock_param, asof=asof, own_capital=own_capital,
        excluded=excluded, horizon_years=horizon_years,
        outlier_threshold=outlier_threshold)
    return KrIrrbbResult(gap=gap, result=result, excluded=excluded,
                         warnings=w1 + w2)
