"""[별표 9의1] 국내 금리리스크 산출기준 — 금리 EaR · 금리 VaR.

**왜 별도 모듈인가.** 이 저장소의 `alm/irrbb.py`는 BCBS d368 체계의 ΔEVE·ΔNII를
산출한다. 은행업감독업무시행세칙 [별표 9의1]이 정하는 표준방법은 그 두 지표가
아니라 **금리 EaR·금리 VaR** 이고, 만기구간(13개)·충격폭 결정방식·아웃라이어
분모와 비율이 전부 다르다. 두 체계를 한 산출로 합치면 어느 규정의 수치인지가
사라지므로 나란히 놓는다. `irrbb.py`는 건드리지 않는다.

  | | d368 (irrbb.py) | 별표 9의1 (이 모듈) |
  |---|---|---|
  | 지표 | ΔEVE · ΔNII | 금리 EaR · 금리 VaR |
  | 만기구간 | 19개 | 13개 |
  | 충격폭 | 통화별 고정 bp 표 | 통화별 규칙(고정 200bp 또는 5년 실측 1%·99%) |
  | 아웃라이어 | 기본자본(Tier 1)의 15% | **자기자본의 20%** |

**원화 충격폭은 규정이 숫자를 주지 않는다.** <표 3>에서 원화는 "총자산 5% 이상 ·
G-10 이외 통화"에 걸리므로 과거 5년 실제 금리변동폭(보유기간 1년) 분포의
1%·99% 값을 써야 한다. 시계열 산출값이 없으면 `shock_bp`는 NULL이고, 엔진은
±200bp를 조용히 대입하지 않고 경고를 남긴 뒤 그 통화의 산출을 비운다. 다른
통화의 200bp를 원화에 끌어다 쓰면 규정이 아니라 다른 줄의 값이 된다.

**계수는 전부 원장에서 온다.** 13개 만기구간의 금리개정 중간시점·수정듀레이션,
핵심예금 기간가중치와 2.33배, 아웃라이어 20% 기준은 `build_*` 빌더가 적재하고
엔진 함수(`kr_ear`·`kr_var`)의 본문에는 숫자가 한 개도 없다. 버킷을 바꾸면
산출이 반드시 따라 움직인다.

**미등재.** 아래 TableSpec은 아직 `datamodel.catalog.ALL_TABLES`에 넣지 않았다.
카탈로그 등재는 실체화 검사·ARCHITECTURE.md 수치 검사와 함께 움직이므로 배선
단계에서 등재한다. 스펙 품질 기준(grain·PK·float unit·FK 대상 존재)은 지금부터
지킨다.

**남은 미확인** (1차자료 §C).
  · 원화 금리변동 예상폭(5년 1%·99%) — 시계열 원본이 있어야 산출된다.
  · 기간가중 표준편차의 산식 이미지는 HWP에서 추출되지 않았다. 원문이 준
    기간가중평균과 정합한 형태를 쓰며 그 사실을 `std_formula` 컬럼에 남긴다.
  · 2018-11-13 이후 개정 여부.
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
from risk_lib.alm.params import EVIDENCE_STATUS, SIDES
from risk_lib.datamodel.spec import ColumnSpec as C, ForeignKey as FK, TableSpec

__all__ = [
    "KR_FRAMEWORK_VERSION", "KR_SHOCK_METHODS", "KR_ASSET_SHARE_BANDS",
    "KR_EXCLUDABLE_ITEMS", "TOTAL_LABEL",
    "KR_BUCKET", "KR_SHOCK_PARAM", "KR_CORE_DEPOSIT_WEIGHT", "KR_CORE_DEPOSIT",
    "KR_GAP", "KR_RESULT", "KR_IRRBB_TABLES",
    "build_kr_irrbb_bucket", "build_kr_irrbb_shock_param",
    "build_kr_core_deposit_weight", "build_kr_core_deposit",
    "build_kr_irrbb_gap", "build_kr_irrbb_result",
    "ear_horizon_years", "kr_ear", "kr_var",
    "KrIrrbbResult", "compute_kr_irrbb",
]

# 계정 식별자. [별표 9의1]은 <신설 2007.12.21, 개정 2010.11.17, 2012.2.14,
# 2014.12.26>이 마지막으로 확인된 개정이다(1차자료 §B 머리말).
KR_FRAMEWORK_VERSION = "kr_9_1_2014"

_CITE = "은행업감독업무시행세칙 [별표 9의1] 금리리스크 산출기준"

# 1bp = 0.0001. 단위 정의이며 규제 계수가 아니다 — 원장 값은 bp로 담고 산식은
# 비율로 돌기 때문에 환산이 한 번 필요하다.
_BP = 1.0e-4

KR_SHOCK_METHODS: tuple[str, ...] = ("고정200bp", "5년실측 1%·99%")
KR_ASSET_SHARE_BANDS: tuple[str, ...] = ("5%이상", "5%미만")

# §B-6 측정대상 제외 가능 항목. 이름만 어휘로 고정하고, 어떤 계약이 여기
# 해당하는지는 계약원장이 정한다 — 상품코드를 이 모듈에 박으면 원장이 바뀔 때
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
          citation=f"{_CITE} <표 2> — 금리 EaR의 (T − t_i)에 쓰는 t_i"),
        C("modified_duration_years", "float", "수정듀레이션", nullable=False,
          unit="years", min_value=0.0,
          citation=f"{_CITE} <표 2> — 은행 자체산출값 사용 가능하나 "
                   f"감독원장 사전승인 필요"),
        C("is_ear_target", "bool", "금리 EaR 대상", nullable=False,
          citation=f"{_CITE} 제7항 — 금리 EaR은 만기구간 1년 이하만 대상"),
        C("is_core_deposit_slot", "bool", "핵심예금 안분 대상", nullable=False,
          citation=f"{_CITE} <표 1> — 핵심예금은 5년 이내 8개 만기구간에 "
                   f"12.5%씩 균등 안분"),
        C("citation", "text", "근거", nullable=True),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("framework_version", "seq"),
    note="13구간이며 BCBS d368 Annex 2의 19구간과 다르다. 안분 비율 12.5%는 "
         "여기 숫자로 적지 않는다 — is_core_deposit_slot이 8건이라는 사실에서 "
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
          note="은행의 사실이지 규정값이 아니다 — 빌더 인자로 들어온다"),
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
          citation=f"{_CITE} <표 5> — t-11월 1/78 … t월 12/78, 가중치 계 1"),
        C("citation", "text", "근거", nullable=True),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("framework_version", "lag_months"),
    note="가중치를 산식 안에 두지 않고 원장 행으로 둔다 — 12행의 합이 1이라는 "
         "것이 검증 대상이 되려면 값이 보여야 한다.",
)

KR_CORE_DEPOSIT = TableSpec(
    name="kr_core_deposit", korean="핵심예금 산출", product="PRD-ALM",
    grain="기준일 × 통화 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("ccy", "string", "통화", nullable=False),
        C("scope", "text", "대상 예금", nullable=False,
          citation=f"{_CITE} <표 5> — 요구불예금·자유저축예금·기업자유예금"
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
          citation=f"{_CITE} <표 5> — 최근월 평잔에서 연간 표준편차의 2.33배 차감"),
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
         "않고 경고를 남긴다 — 모자란 개월수로 계산한 표준편차는 규정 산식이 "
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
          citation=f"{_CITE} 제7항 — 금리갭 = 금리민감자산 − 금리민감부채"),
        C("citation", "text", "근거", nullable=True),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("asof", "framework_version", "ccy", "seq"),
    foreign_keys=(FK(("framework_version", "seq"), "kr_irrbb_bucket",
                     ("framework_version", "seq")),),
    note="통화별로 13구간 전건이 나온다 — 잔액이 없는 구간도 0으로 채운다. "
         "사다리에 구멍이 있으면 합산이 조용히 달라진다.",
)

KR_RESULT = TableSpec(
    name="kr_irrbb_result", korean="국내기준 금리리스크 산출결과",
    product="PRD-ALM",
    grain="기준일 × 계정 × 통화 1행 (합계 1행 포함)",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("framework_version", "string", "계정", nullable=False),
        C("ccy", "string", "통화", nullable=False),
        C("is_total", "bool", "통화 합산행", nullable=False,
          citation=f"{_CITE} 제9항 — 통화별로 산출해 합산한다"),
        C("shock_bp", "float", "금리변동 예상폭", nullable=True, unit="bp"),
        C("shock_method", "string", "예상폭 결정방식", nullable=True,
          allowed=KR_SHOCK_METHODS),
        C("horizon_years", "float", "목표 관리기간", nullable=True, unit="years",
          min_value=0.0,
          citation=f"{_CITE} 제7항 — 금리 EaR의 T. 원칙 1년"),
        C("ear_amount", "float", "금리 EaR", nullable=True, unit="KRW",
          citation=f"{_CITE} 제7항 — Σ 금리갭_i × (T − t_i) × Δr_i, "
                   f"만기구간 1년 이하"),
        C("var_amount", "float", "금리 VaR", nullable=True, unit="KRW",
          citation=f"{_CITE} 제8항 — Σ 금리갭_i × 수정듀레이션_i × Δr_i, "
                   f"전 만기구간"),
        C("total_ir_risk", "float", "총 금리리스크", nullable=True, unit="KRW",
          min_value=0.0,
          citation=f"{_CITE} 제27항 — 금리 VaR에 의하여 산출한 총 금리리스크"),
        C("own_capital", "float", "자기자본", nullable=True, unit="KRW",
          min_value=0.0,
          citation="세칙 <별표 3>의 자기자본. d368의 기본자본(Tier 1)이 아니다"),
        C("risk_to_own_capital", "float", "자기자본 대비 비율", nullable=True,
          unit="ratio"),
        C("outlier_threshold", "float", "아웃라이어 기준", nullable=True,
          unit="ratio", min_value=0.0,
          citation=f"{_CITE} 제27항 — 자기자본의 20% 초과 시 outlier"),
        C("denominator_basis", "string", "판정 분모", nullable=False,
          note="국내기준은 '자기자본', d368은 '기본자본(Tier 1)'이다. 분모가 "
               "다르다는 사실이 컬럼으로 보여야 두 수치가 섞이지 않는다"),
        C("is_outlier", "bool", "아웃라이어", nullable=True,
          note="합계행에서만 판정한다. 통화행은 NULL이다"),
        C("excluded_amount", "float", "측정대상 제외액", nullable=False,
          unit="KRW", min_value=0.0,
          citation=f"{_CITE} 제외항목 — 지준예치금·고정자산·현금·주식·"
                   f"은행간조정자금·자본총계·부채성충당금"),
        C("citation", "text", "근거", nullable=True),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("asof", "framework_version", "ccy"),
    note="금리 EaR·금리 VaR는 부호 있는 값이며 금리 상승(+shock_bp) 방향으로 "
         "산출한다. 총 금리리스크는 그 크기다 — 세칙이 부호 규약을 정하지 "
         "않으므로 판정에 쓰이는 것이 크기라는 사실을 컬럼으로 나눠 둔다. "
         "shock_bp가 NULL인 통화는 행이 있으되 산출값이 비어 있다.",
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

# 제27항 아웃라이어 기준 — 자기자본의 20%.
_OUTLIER_PCT_OWN_CAPITAL = 0.20
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
            "framework_version": KR_FRAMEWORK_VERSION,
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
    열거하지 않으므로 목록도 인자로 받는다 — 열거는 원문에 없다.
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
            cite = f"{_CITE} <표 3> 셋째 줄 — 총자산 5% 미만 통화 ±200bp"
        elif is_g10:
            # 첫째 줄은 두 방식을 허용한다. 은행이 실측값을 넘겼으면 그것을,
            # 아니면 규정이 명시한 200bp를 쓴다. 어느 쪽인지 method가 남긴다.
            if ccy in measured:
                method, shock_bp = "5년실측 1%·99%", float(measured[ccy])
                cite = f"{_CITE} <표 3> 첫째 줄 — 5년 실측 1%·99% 선택"
            else:
                method, shock_bp = "고정200bp", _FIXED_SHOCK_BP
                cite = f"{_CITE} <표 3> 첫째 줄 — ±200bp 선택"
        else:
            method = "5년실측 1%·99%"
            shock_bp = float(measured[ccy]) if ccy in measured else None
            cite = (f"{_CITE} <표 3> 둘째 줄 — 총자산 5% 이상 · G-10 이외 "
                    f"통화는 과거 5년 실제 금리변동폭(보유기간 1년) 분포의 "
                    f"1%·99% 값. 규정이 숫자를 주지 않는다")
        rows.append({
            "framework_version": KR_FRAMEWORK_VERSION,
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
            "framework_version": KR_FRAMEWORK_VERSION,
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
    행을 만들지 않고 경고를 남긴다 — 개월수를 줄여 계산한 표준편차는 규정
    산식이 아니다.

    배수 2.33과 가중치는 원장(`weights`)에서 오고, 이 함수는 산식만 돈다.
    """
    warns: list[ParamWarning] = []
    w = weights.sort_values("lag_months")
    w_map = {int(r.lag_months): float(r.weight) for r in w.itertuples()}
    w_sum = sum(w_map.values())
    if not math.isclose(w_sum, 1.0, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError(
            f"kr_core_deposit_weight의 가중치 합이 {w_sum!r}이다 — <표 5>는 "
            "가중치 계 1을 명시한다")

    rows = []
    for ccy, grp in monthly_balance.groupby("ccy", sort=True):
        lags = {int(v) for v in grp["lag_months"]}
        if lags != set(w_map):
            warns.append(ParamWarning(
                "core_deposit", str(ccy), "monthly_balance",
                f"월중평잔이 {len(lags)}개월치다 — <표 5>는 최근 12개월 전건을 "
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
                f"산식 결과가 음수({raw:,.0f})다 — 음수 핵심예금은 안분이 "
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

    제외항목(§B-6)은 갭에 들어가지 않고 두 번째 반환값에 금액으로 남는다 —
    조용히 사라지면 사다리 합계가 대차대조표와 어긋난 이유를 찾을 수 없다.
    계약원장은 자기자본만 플래그로 들고 있으므로 나머지 제외항목은
    `exclude_product_codes`(상품코드 → 제외항목명)로 넘긴다.

    반환: (갭 원장, 제외액 프레임, 경고)
    """
    if day_count not in DAY_COUNTS:
        raise ValueError(f"미지원 이자계산 관행 {day_count!r} — {DAY_COUNTS}")
    warns: list[ParamWarning] = []
    b = buckets.sort_values("seq").reset_index(drop=True)
    uppers = b["upper_years"].to_numpy(dtype=float)
    seqs = b["seq"].to_numpy(dtype=int)
    labels = {int(r.seq): str(r.label) for r in b.itertuples()}
    core_seqs = [int(s) for s in b.loc[b["is_core_deposit_slot"].astype(bool),
                                       "seq"]]
    if not core_seqs:
        raise ValueError("kr_irrbb_bucket에 is_core_deposit_slot 행이 없다 — "
                         "핵심예금 안분 대상 구간이 정해지지 않았다")
    core_share = 1.0 / len(core_seqs)
    shortest_seq = int(seqs[0])

    excl_map = dict(exclude_product_codes or {})
    core_scope = None if core_scope_product_codes is None else {
        str(c) for c in core_scope_product_codes}
    if core_scope is None:
        warns.append(ParamWarning(
            "kr_gap", "핵심예금 대상", "core_scope_product_codes",
            "<표 5> 대상 예금(요구불성예금) 상품코드를 받지 못했다 — 비만기 "
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
            "부외(off_balance) 계약이 있다 — <표 1>은 파생상품을 기초자산으로 "
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
                    f"아니다 — {KR_EXCLUDABLE_ITEMS}")
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
                    "kr_core_deposit에 해당 통화 행이 없다 — 핵심예금을 "
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
                "asof": asof, "framework_version": KR_FRAMEWORK_VERSION,
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
        raise ValueError("kr_irrbb_bucket에 is_ear_target 행이 없다 — "
                         "금리 EaR의 대상 구간이 정해지지 않았다")
    return float(tgt["upper_years"].max())


def _join(gap: pd.DataFrame, buckets: pd.DataFrame) -> pd.DataFrame:
    """갭 사다리에 버킷 계수를 붙인다. 단일 통화 사다리를 전제한다."""
    if gap["seq"].duplicated().any():
        raise ValueError("금리갭이 통화 하나의 사다리가 아니다 — seq가 중복이다")
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

    `shock_bp`가 NULL인 통화는 행이 남되 산출값이 비고 경고가 붙는다. 다른
    통화의 200bp를 대입하지 않는다.

    아웃라이어 판정은 **합계행에서만** 한다. 제27항의 기준은 자기자본의 20%이며
    d368의 기본자본 15%와 분모·비율이 모두 다르다 — 그 사실이
    `denominator_basis`·`outlier_threshold` 컬럼으로 남는다.
    """
    if not own_capital > 0.0:
        raise ValueError(
            f"자기자본이 {own_capital!r}이다 — 0 이하로는 자기자본 대비 비율이 "
            "정의되지 않는다")
    warns: list[ParamWarning] = []
    T = ear_horizon_years(buckets) if horizon_years is None else float(
        horizon_years)
    thr = (_OUTLIER_PCT_OWN_CAPITAL if outlier_threshold is None
           else float(outlier_threshold))

    sp = shock_param[shock_param["framework_version"] == KR_FRAMEWORK_VERSION]
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
                "kr_irrbb_shock_param에 해당 통화 행이 없다 — 산출하지 않는다"))
        else:
            method = str(p.method)
            if pd.isna(p.shock_bp):
                warns.append(ParamWarning(
                    "kr_irrbb", ccy, "shock_bp",
                    f"금리변동 예상폭이 비어 있다(method={method}) — <표 3>이 "
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
            "asof": asof, "framework_version": KR_FRAMEWORK_VERSION,
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
        "asof": asof, "framework_version": KR_FRAMEWORK_VERSION,
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
        # 제27항은 "초과하는 은행"이라고 적는다 — 경계값은 아웃라이어가 아니다.
        "is_outlier": None if ratio is None else bool(ratio > thr),
        "excluded_amount": float(sum(excl_by_ccy.values())),
        "citation": f"{_CITE} 제9항 통화별 합산 · 제27항 아웃라이어",
        "evidence_status": "원문확인" if n_priced else "미확인",
    })
    if not n_priced:
        warns.append(ParamWarning(
            "kr_irrbb", TOTAL_LABEL, "total_ir_risk",
            "산출된 통화가 하나도 없다 — 합계와 아웃라이어 판정을 비운다"))

    df = pd.DataFrame(rows, columns=[c.name for c in KR_RESULT.columns])
    floats = ["shock_bp", "horizon_years", "ear_amount", "var_amount",
              "total_ir_risk", "own_capital", "risk_to_own_capital",
              "outlier_threshold", "excluded_amount"]
    return df.astype({c: "float64" for c in floats}), warns


# ---------------------------------------------------------------- 결과 객체

@dataclass
class KrIrrbbResult:
    """국내기준 산출 결과 — 원장 두 장과 제외액, 그리고 경고."""
    gap: pd.DataFrame                    # kr_irrbb_gap
    result: pd.DataFrame                 # kr_irrbb_result
    excluded: pd.DataFrame               # 측정대상 제외액
    warnings: list[ParamWarning] = field(default_factory=list)

    @property
    def total_row(self) -> pd.Series:
        hit = self.result[self.result["is_total"].astype(bool)]
        if len(hit) != 1:
            raise ValueError(f"합계행이 {len(hit)}건이다 — 정확히 1건이어야 한다")
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
