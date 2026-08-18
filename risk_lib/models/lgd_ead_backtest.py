"""LGD·EAD(CCF) 실측 모니터링·검증 원장과 산출.

PD는 `risk_lib/validation/backtest.py`가 사후검증을 갖고 있으나 LGD와 EAD는
추정치만 있고 실측 대조가 없었다. 이 모듈이 그 두 축을 원장으로 만든다.

원장 넉 장
  ``crm_backtest_criteria``     판정기준(임계·유의수준·회수기간)과 승인 상태
  ``crm_default_observation``   부도 익스포저별 실측 관측치. 관측중단 판정 포함
  ``crm_lgd_backtest``          기준일 × 축(등급·담보유형·세그먼트) 집계·검정
  ``crm_ccf_backtest``          기준일 × ccf_type × 등급대 집계·검정

왜 판정기준을 원장으로 두는가
  LGD·CCF 사후검증의 합격 임계를 정한 규정 수치를 이 저장소는 아직 확인하지
  못했다([별표 3] 신용리스크 내부등급법과 EBA/GL/2017/16의 해당 절을 열람하지
  않았다). 확인되지 않은 임계를 엔진 본문에 적으면 그 숫자가 규정처럼 보인다.
  그래서 임계는 전건 ``basis='내부기준'``, ``evidence_status='미확인'``으로
  원장에 두고 승인자·승인일 컬럼을 비워 둔다. 승인 전에는 엔진이 PASS/FAIL을
  찍지 않고 ``judgment_status='기준미승인'``으로 남긴다.

왜 관측중단을 따로 다루는가
  회수는 부도 시점에 끝나지 않는다. 회수기간이 종료되지 않은 부도건의 잠정
  실현 LGD를 검정에 넣으면 앞으로 들어올 회수가 빠져 회수율이 과소평가되고
  실현 LGD가 과대평가된다. 그래서 관측중단(censoring) 건은 검정 표본에서
  빼고, 뺀 건수를 ``n_censored`` 컬럼으로 원장에 남긴다.

시간축과 부도시점 잔액은 합성이다
  원천 포트폴리오의 ``default_12m``은 12개월 부도 플래그이며 부도일자가 없다.
  부도시점 인출액 스냅샷도 없다. ``build_default_observation``이 전용 시드
  스트림으로 부도월과 부도시점 인출액을 만들고 그 행에 ``source_system=
  'synthetic'``을 적는다. 실계 연결 시 가장 먼저 교체해야 할 두 컬럼이다.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import t as _student_t

from risk_lib.capital.crm import CCF_BUCKETS
from risk_lib.datamodel import catalog as cat
from risk_lib.datamodel.spec import ColumnSpec as C, ForeignKey as FK, TableSpec
from risk_lib.models.rating import DEFAULT_MASTER_SCALE, pd_to_rating

__all__ = [
    "BACKTEST_TARGETS", "CRITERIA_BASES", "EVIDENCE_STATUS", "APPROVAL_BODIES",
    "JUDGMENT_STATUS", "CENSORING_STATUS", "LGD_SEGMENT_AXES", "GRADE_BANDS",
    "LGD_CRITERIA_SET", "CCF_CRITERIA_SET",
    "BACKTEST_CRITERIA", "DEFAULT_OBSERVATION", "LGD_BACKTEST", "CCF_BACKTEST",
    "BACKTEST_TABLES",
    "CriteriaWarning", "BacktestLedgerWarning",
    "build_backtest_criteria", "approve_criteria", "unapproved_criteria",
    "load_criteria",
    "build_default_observation", "build_lgd_backtest", "build_ccf_backtest",
    "build_lgd_ead_backtest_ledgers",
]


# ---------------------------------------------------------------- 어휘

BACKTEST_TARGETS: tuple[str, ...] = ("LGD", "CCF")
# 'basis'는 임계의 효력 근거다. '규정'은 법령·감독규정이 값을 정한 것이고
# '내부기준'은 내규가 정하며 승인기구 의결이 효력 요건이다.
CRITERIA_BASES: tuple[str, ...] = ("규정", "내부기준")
# limits_master·alm.params와 같은 어휘를 쓴다. 사본이 갈라지면 화면이 같은
# 근거상태를 다른 말로 표시한다.
EVIDENCE_STATUS: tuple[str, ...] = (
    "원문확인", "2차자료", "원문미확인·현행계승", "재량·미규정", "내부가정",
    "미확인")
APPROVAL_BODIES: tuple[str, ...] = (
    "이사회", "리스크관리위원회", "모형위원회", "법령")
# 판정 상태를 통과여부와 분리한다. 통과여부가 비어 있는 이유는 넷이고,
# 그 이유가 원장에 없으면 화면이 '판정 안 됨'을 '판정 통과'와 섞는다.
JUDGMENT_STATUS: tuple[str, ...] = (
    "판정완료", "기준미승인", "기준미정", "표본부족")
CENSORING_STATUS: tuple[str, ...] = ("회수종료", "관측중단", "판정불가")
# LGD 백테스트의 집계 축. 세 축을 교차하면 부도 484건이 셀당 한 자릿수로
# 흩어져 t검정에 검정력이 남지 않는다. 축별 주변집계 세 벌로 둔다.
LGD_SEGMENT_AXES: tuple[str, ...] = ("grade", "collateral_type", "segment")
# 등급대는 내부 마스터스케일의 SA 버킷에서 유도한다. 별도 목록을 적으면
# 마스터스케일이 바뀔 때 두 곳이 갈라진다.
GRADE_BANDS: tuple[str, ...] = tuple(
    dict.fromkeys(g.sa_bucket for g in DEFAULT_MASTER_SCALE)) + ("미부여",)
_GRADES: tuple[str, ...] = tuple(g.grade for g in DEFAULT_MASTER_SCALE) + ("미부여",)
_COLLATERAL_TYPES: tuple[str, ...] = tuple(cat.COLLATERAL_TYPES) + ("무담보",)

LGD_CRITERIA_SET: str = "LGD_BT_INTERNAL_v1"
CCF_CRITERIA_SET: str = "CCF_BT_INTERNAL_v1"

# 판정을 가르는 파라미터. 이 중 하나라도 원장에 값이 없으면 판정하지 않는다.
_LGD_GATING: tuple[str, ...] = (
    "significance_level", "mae_tolerance", "min_n_defaults",
    "workout_period_months")
_CCF_GATING: tuple[str, ...] = (
    "significance_level", "bias_tolerance", "min_n_facilities")
_OPTIONAL: tuple[str, ...] = ("ci_level",)

_LGD_METHOD = (
    "대응표본 t검정(양측). 부도건별 편의 d_i = 실현 LGD − 추정 LGD, "
    "귀무가설 E[d] = 0. 통과 조건은 p값 ≥ 유의수준 및 MAE ≤ 허용오차")
_CCF_METHOD = (
    "일표본 t검정(양측). 약정건별 실측 CCF에서 적용 CCF를 뺀 값의 평균이 "
    "0인지 검정한다. 통과 조건은 p값 ≥ 유의수준 및 |편의| ≤ 허용오차")
_CENSOR_RULE = (
    "부도 후 경과월 < 회수기간이면 관측중단으로 보고 검정 표본에서 제외한다. "
    "제외 건수는 n_censored에 남긴다. 미종료 건의 실현 LGD는 잠정치이며 "
    "이후 회수가 더 들어오면 낮아진다")
_CCF_CITATION = (
    "적용 CCF는 Basel III CRE20.94 표준방법 신용환산율이며 저장소의 "
    "risk_lib.capital.crm.CCF_BUCKETS 한 곳에서 온다. 국내 [별표 3]의 "
    "신용환산율 원문은 열람하지 않았다")
_CRITERIA_NOTE = (
    "LGD·CCF 사후검증의 합격 임계를 정한 규정 수치를 확인하지 못했다. "
    "[별표 3] 신용리스크 내부등급법과 EBA/GL/2017/16의 해당 절을 열람하지 "
    "않았으므로 규정 수치의 존재 여부 자체가 미확인이다. 아래 값은 승인 전 "
    "제안치이며 승인자·승인일이 비어 있는 동안 엔진은 통과여부를 찍지 않는다")

# 관측원장 합성 파라미터. 규제 계수가 아니라 원천에 없는 컬럼을 만드는
# 데이터 생성 계수이며, 관측원장 빌더 한 곳에서만 쓴다.
_DRAWDOWN_BETA_A: float = 2.0
_DRAWDOWN_BETA_B: float = 2.0
# 부도 직전 추가인출 비율의 범위를 [-0.1, 1.1]로 둔다. 음수 구간은 부도 전
# 일부 상환, 1 초과 구간은 한도 초과 인출을 나타낸다.
_DRAWDOWN_FLOOR: float = -0.1
_DRAWDOWN_SPAN: float = 1.2
# 부도월을 배정할 관측창. 회수기간보다 넓어야 회수종료와 관측중단이 함께
# 나온다. 원천에 부도일자가 생기면 이 값은 쓰이지 않는다.
_DEFAULT_LOOKBACK_MONTHS: int = 60
_RNG_OFFSET_DEFAULT_MONTH: int = 88101
_RNG_OFFSET_DRAWDOWN: int = 88102


@dataclass(frozen=True)
class CriteriaWarning:
    """판정기준 원장의 칸이 비어 판정을 못 실은 사건."""
    criteria_set_id: str
    param: str
    reason: str


class BacktestLedgerWarning(UserWarning):
    """판정기준 결측·미승인으로 통과여부를 남기지 못할 때 발생."""


# ---------------------------------------------------------------- 스펙

BACKTEST_CRITERIA = TableSpec(
    name="crm_backtest_criteria", korean="LGD·CCF 사후검증 판정기준",
    product="PRD-CRM",
    grain="판정기준셋 × 파라미터 1행",
    columns=(
        C("criteria_set_id", "string", "판정기준셋", nullable=False),
        C("param", "string", "파라미터", nullable=False),
        C("target", "string", "검증대상", nullable=False,
          allowed=BACKTEST_TARGETS),
        C("param_value", "float", "임계값", nullable=True, unit="가변",
          note="단위는 같은 행의 param_unit을 본다. NULL이면 엔진이 그 기준을 "
               "싣지 않고 경고를 남긴 뒤 판정을 보류한다"),
        C("param_unit", "string", "임계 단위", nullable=False,
          allowed=("ratio", "count", "months")),
        C("comparator", "string", "통과 방향", nullable=False,
          allowed=(">=", "<=", "n/a"),
          note="측정값을 임계와 어느 방향으로 비교해야 통과인지. 방향이 "
               "원장에 없으면 같은 숫자로 반대 판정이 나온다"),
        C("threshold_formula", "text", "판정 산식", nullable=False),
        C("basis", "string", "근거 구분", nullable=False, allowed=CRITERIA_BASES),
        C("citation", "text", "근거", nullable=True),
        C("approval_body", "string", "승인기구", nullable=True,
          allowed=APPROVAL_BODIES),
        C("approved_by", "string", "승인자", nullable=True),
        C("approved_on", "date", "승인일", nullable=True),
        C("note", "text", "비고", nullable=True),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("criteria_set_id", "param"),
    note="전건 basis='내부기준'이고 승인자·승인일이 비어 있다. 규정 수치를 "
         "확인하지 못한 상태에서 임계를 확정한 것처럼 두면 백테스트가 근거 "
         "없는 PASS를 만든다.",
)

DEFAULT_OBSERVATION = TableSpec(
    name="crm_default_observation", korean="부도 실측 관측원장",
    product="PRD-CRM",
    grain="기준일 × 부도 익스포저 1건당 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("exposure_id", "string", "익스포저 식별자", nullable=False),
        C("obligor_id", "string", "차주 식별자", nullable=False),
        C("segment", "string", "세그먼트", nullable=False,
          allowed=cat.ASSET_CLASSES),
        C("grade", "string", "부도전 등급", nullable=False, allowed=_GRADES),
        C("grade_band", "string", "등급대", nullable=False, allowed=GRADE_BANDS),
        C("collateral_type", "string", "담보유형", nullable=False,
          allowed=_COLLATERAL_TYPES,
          note="담보원장에 행이 없으면 '무담보'. 담보원장 미제공 시 전건 무담보"),
        C("default_month", "date", "부도월", nullable=False,
          note="원천에 부도일자가 없어 전용 시드 스트림으로 배정한 합성값"),
        C("months_since_default", "int", "부도후 경과월", nullable=False,
          unit="months", min_value=0),
        C("workout_period_months", "float", "적용 회수기간", nullable=True,
          unit="months", min_value=0.0,
          note="판정기준 원장의 workout_period_months. NULL이면 관측중단을 "
               "판정할 수 없다"),
        C("workout_complete", "bool", "회수종료", nullable=True,
          note="회수기간을 모르면 NULL. True/False 로 채우면 미판정이 판정으로 보인다"),
        C("censoring_status", "string", "관측상태", nullable=False,
          allowed=CENSORING_STATUS),
        C("ead_at_default", "float", "부도시 익스포저", nullable=False,
          unit="KRW", min_value=0.0),
        C("lgd_estimated", "float", "추정 LGD", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("lgd_realized", "float", "실현 LGD", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0,
          note="관측중단 건의 값은 잠정치다. 회수가 더 들어오면 낮아지므로 "
               "검정 표본에서 뺀다"),
        C("ccf_type", "string", "신용환산 구분", nullable=True,
          allowed=cat.CCF_TYPES),
        C("drawn_at_ref", "float", "기준시 인출액", nullable=False, unit="KRW",
          min_value=0.0),
        C("undrawn_at_ref", "float", "기준시 미인출액", nullable=False,
          unit="KRW", min_value=0.0),
        C("drawn_at_default", "float", "부도시 인출액", nullable=False,
          unit="KRW", min_value=0.0,
          note="원천에 부도시점 잔액 스냅샷이 없어 전용 시드 스트림으로 만든 합성값"),
        C("ccf_realized", "float", "실측 CCF", nullable=True, unit="ratio",
          note="(부도시 인출액 − 기준시 인출액) / 기준시 미인출액. 미인출액이 "
               "0이면 NULL. 부도 전 상환이 있으면 음수, 한도 초과 인출이 "
               "있으면 1 초과가 나올 수 있어 범위를 묶지 않는다"),
        C("ccf_applied", "float", "적용 CCF", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0, citation=_CCF_CITATION),
        C("source_system", "string", "원천 시스템", nullable=False,
          allowed=cat.SOURCE_SYSTEMS),
        C("note", "text", "비고", nullable=True),
    ),
    primary_key=("asof", "exposure_id"),
    foreign_keys=(
        FK(("exposure_id",), "rdm_exposure", ("exposure_id",)),
        FK(("obligor_id",), "rdm_obligor", ("obligor_id",)),
    ),
    note="LGD·CCF 백테스트 두 장의 유일한 입력이다. 집계표만 두면 어느 부도건이 "
         "관측중단으로 빠졌는지 화면에서 되짚을 수 없다.",
)

LGD_BACKTEST = TableSpec(
    name="crm_lgd_backtest", korean="LGD 사후검증", product="PRD-CRM",
    grain="기준일 × 집계축(등급·담보유형·세그먼트) × 축값 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("segment_axis", "string", "집계축", nullable=False,
          allowed=LGD_SEGMENT_AXES),
        C("segment_value", "string", "축값", nullable=False),
        C("n_defaults", "int", "검정 부도건수", nullable=False, unit="count",
          min_value=0, note="회수종료 건만 센다"),
        C("n_censored", "int", "관측중단 건수", nullable=False, unit="count",
          min_value=0),
        C("lgd_estimated_mean", "float", "추정 LGD 평균", nullable=True,
          unit="ratio", min_value=0.0, max_value=1.0),
        C("lgd_realized_mean", "float", "실현 LGD 평균", nullable=True,
          unit="ratio", min_value=0.0, max_value=1.0),
        C("bias", "float", "편의", nullable=True, unit="ratio",
          note="실현 − 추정. 양수면 추정 LGD가 실현보다 낮다"),
        C("mae", "float", "평균절대오차", nullable=True, unit="ratio",
          min_value=0.0),
        C("rmse", "float", "평균제곱근오차", nullable=True, unit="ratio",
          min_value=0.0),
        C("ci_level", "float", "신뢰수준", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("ci_low", "float", "편의 신뢰구간 하한", nullable=True, unit="ratio"),
        C("ci_high", "float", "편의 신뢰구간 상한", nullable=True, unit="ratio"),
        C("t_stat", "float", "t 통계량", nullable=True, unit="표준화값"),
        C("p_value", "float", "p값", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("pass_flag", "bool", "통과여부", nullable=True,
          note="판정기준이 미승인·미정이거나 표본이 부족하면 NULL"),
        C("judgment_status", "string", "판정상태", nullable=False,
          allowed=JUDGMENT_STATUS),
        C("method", "text", "검증방법", nullable=False),
        C("censoring_rule", "text", "관측중단 처리", nullable=False),
        C("criteria_set_id", "string", "판정기준셋", nullable=False),
        C("citation", "text", "근거", nullable=True),
        C("note", "text", "비고", nullable=True),
    ),
    primary_key=("asof", "segment_axis", "segment_value"),
    foreign_keys=(
        FK(("criteria_set_id",), "crm_backtest_criteria", ("criteria_set_id",)),
    ),
    note="세 축을 교차하지 않고 축별 주변집계로 둔다. 부도 484건을 등급 17 × "
         "담보 7 × 세그먼트 5로 나누면 셀당 표본이 한 자릿수가 되어 t검정에 "
         "검정력이 남지 않는다.",
)

CCF_BACKTEST = TableSpec(
    name="crm_ccf_backtest", korean="CCF 사후검증", product="PRD-CRM",
    grain="기준일 × ccf_type × 등급대 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("ccf_type", "string", "신용환산 구분", nullable=False,
          allowed=cat.CCF_TYPES),
        C("grade_band", "string", "등급대", nullable=False, allowed=GRADE_BANDS),
        C("n_facilities", "int", "약정 건수", nullable=False, unit="count",
          min_value=0),
        C("drawn_at_ref", "float", "기준시 인출액", nullable=False, unit="KRW",
          min_value=0.0),
        C("undrawn_at_ref", "float", "기준시 미인출액", nullable=False,
          unit="KRW", min_value=0.0),
        C("drawn_at_default", "float", "부도시 인출액", nullable=False,
          unit="KRW", min_value=0.0),
        C("ccf_realized", "float", "실측 CCF(금액가중)", nullable=True,
          unit="ratio",
          note="(부도시 인출액 합 − 기준시 인출액 합) / 기준시 미인출액 합"),
        C("ccf_realized_mean", "float", "실측 CCF(건별평균)", nullable=True,
          unit="ratio", note="t검정이 쓰는 값이다. 금액가중치와 다를 수 있다"),
        C("ccf_applied", "float", "적용 CCF", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0, citation=_CCF_CITATION),
        C("bias", "float", "편의", nullable=True, unit="ratio",
          note="건별평균 실측 CCF − 적용 CCF"),
        C("ci_level", "float", "신뢰수준", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("ci_low", "float", "편의 신뢰구간 하한", nullable=True, unit="ratio"),
        C("ci_high", "float", "편의 신뢰구간 상한", nullable=True, unit="ratio"),
        C("t_stat", "float", "t 통계량", nullable=True, unit="표준화값"),
        C("p_value", "float", "p값", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("pass_flag", "bool", "통과여부", nullable=True),
        C("judgment_status", "string", "판정상태", nullable=False,
          allowed=JUDGMENT_STATUS),
        C("method", "text", "검증방법", nullable=False),
        C("criteria_set_id", "string", "판정기준셋", nullable=False),
        C("citation", "text", "근거", nullable=True),
        C("note", "text", "비고", nullable=True),
    ),
    primary_key=("asof", "ccf_type", "grade_band"),
    foreign_keys=(
        FK(("criteria_set_id",), "crm_backtest_criteria", ("criteria_set_id",)),
    ),
    note="미인출 약정이 있는 부도건만 모집단이다. 미인출액이 0인 익스포저는 "
         "분모가 없어 실측 CCF가 정의되지 않는다.",
)

BACKTEST_TABLES: tuple[TableSpec, ...] = (
    BACKTEST_CRITERIA, DEFAULT_OBSERVATION, LGD_BACKTEST, CCF_BACKTEST)


# ---------------------------------------------------------------- 판정기준

def build_backtest_criteria() -> pd.DataFrame:
    """판정기준 원장. 이 함수가 곧 기준 등재·수기입력 프로세스다.

    임계값을 여기 한 곳에만 적재하고 엔진은 이 원장을 인자로 받는다. 값이
    엔진 본문이나 기본값에 있으면 화면에서 임계를 볼 수 없고, 임계가 바뀔 때
    코드 수정이 필요해진다.
    """
    _INT = ("규정 근거 미확인. 내규가 정하는 내부기준이며 승인기구 의결이 "
            "효력 요건이다")
    # (param, target, value, unit, comparator, formula)
    rows = (
        ("significance_level", "LGD", 0.05, "ratio", ">=",
         "편의 대응표본 t검정의 p값이 유의수준 이상이면 편의가 유의하지 않다고 본다"),
        ("mae_tolerance", "LGD", 0.10, "ratio", "<=",
         "|실현 LGD − 추정 LGD|의 평균이 허용오차 이하"),
        ("min_n_defaults", "LGD", 20.0, "count", ">=",
         "회수종료 부도건수가 최소표본 미만이면 표본부족으로 판정을 보류한다"),
        ("workout_period_months", "LGD", 36.0, "months", ">=",
         "부도후 경과월이 회수기간 이상이면 회수종료, 미만이면 관측중단"),
        ("ci_level", "LGD", 0.95, "ratio", "n/a",
         "편의 신뢰구간의 신뢰수준. 판정을 가르지 않고 보고에만 쓴다"),
        ("significance_level", "CCF", 0.05, "ratio", ">=",
         "편의 일표본 t검정의 p값이 유의수준 이상이면 편의가 유의하지 않다고 본다"),
        ("bias_tolerance", "CCF", 0.10, "ratio", "<=",
         "|건별평균 실측 CCF − 적용 CCF|가 허용오차 이하"),
        ("min_n_facilities", "CCF", 20.0, "count", ">=",
         "약정 건수가 최소표본 미만이면 표본부족으로 판정을 보류한다"),
        ("ci_level", "CCF", 0.95, "ratio", "n/a",
         "편의 신뢰구간의 신뢰수준. 판정을 가르지 않고 보고에만 쓴다"),
    )
    sets = {"LGD": LGD_CRITERIA_SET, "CCF": CCF_CRITERIA_SET}
    out = pd.DataFrame([
        {"criteria_set_id": sets[target], "param": param, "target": target,
         "param_value": float(value), "param_unit": unit,
         "comparator": comp, "threshold_formula": formula,
         "basis": "내부기준", "citation": None, "approval_body": None,
         "approved_by": None, "approved_on": None,
         "note": f"{_INT}. {_CRITERIA_NOTE}", "evidence_status": "미확인"}
        for (param, target, value, unit, comp, formula) in rows
    ])
    return out.astype({"param_value": "float64"}).reset_index(drop=True)


def approve_criteria(ledger: pd.DataFrame, *, approved_by: str,
                     approved_on: str, approval_body: str,
                     criteria_set_id: str | None = None,
                     params: tuple[str, ...] | None = None) -> pd.DataFrame:
    """판정기준 행에 승인자·승인일·승인기구를 기록한 사본을 돌려준다.

    승인은 수기 프로세스다. 이 함수는 그 프로세스가 원장에 남기는 형태를
    고정할 뿐 승인 자체를 만들지 않는다. 승인 기록이 있어야 엔진이 통과여부를
    찍는다.
    """
    if approval_body not in APPROVAL_BODIES:
        raise ValueError(f"미등록 승인기구: {approval_body!r}")
    out = ledger.copy()
    mask = pd.Series(True, index=out.index)
    if criteria_set_id is not None:
        mask &= out["criteria_set_id"] == criteria_set_id
    if params is not None:
        mask &= out["param"].isin(params)
    if not mask.any():
        raise ValueError("승인 대상 행이 없다")
    out.loc[mask, "approved_by"] = approved_by
    out.loc[mask, "approved_on"] = approved_on
    out.loc[mask, "approval_body"] = approval_body
    return out


def unapproved_criteria(ledger: pd.DataFrame | None = None) -> pd.DataFrame:
    """승인자·승인일·승인기구 중 하나라도 빈 내부기준 행.

    규정이 값을 정한 행은 법령이 효력 근거이므로 내부 의결일을 요구하지
    않는다. 내부기준은 의결이 효력 요건이라 승인이 비면 결재 근거가 없다.
    """
    if ledger is None:
        ledger = build_backtest_criteria()
    internal = ledger[ledger["basis"] == "내부기준"]
    return internal[internal["approved_by"].isna()
                    | internal["approved_on"].isna()
                    | internal["approval_body"].isna()].copy()


def load_criteria(ledger: pd.DataFrame, criteria_set_id: str, *,
                  gating: tuple[str, ...],
                  optional: tuple[str, ...] = (),
                  ) -> tuple[dict[str, float | None], str]:
    """판정기준셋을 엔진이 쓰는 형태로 옮기고 판정 가능 여부를 함께 돌려준다.

    반환 상태는 셋이다. ``기준미정``은 임계 자체가 비어 있는 경우,
    ``기준미승인``은 값은 있으나 승인 기록이 없는 경우, ``판정완료``는 둘 다
    갖춰진 경우다. 앞의 둘에서 임의의 기본값을 쓰면 미입력·미승인 기준이
    통과한 기준으로 보인다.
    """
    sub = ledger[ledger["criteria_set_id"] == criteria_set_id]
    values: dict[str, float | None] = {}
    skipped: list[CriteriaWarning] = []
    missing: list[str] = []
    unapproved: list[str] = []

    for param in tuple(gating) + tuple(optional):
        row = sub[sub["param"] == param]
        if row.empty or pd.isna(row["param_value"].iloc[0]):
            values[param] = None
            if param in gating:
                missing.append(param)
                skipped.append(CriteriaWarning(
                    criteria_set_id, param,
                    "임계 미입력. 이 기준으로는 판정하지 않는다"))
            continue
        values[param] = float(row["param_value"].iloc[0])
        if param in gating and (pd.isna(row["approved_by"].iloc[0])
                                or pd.isna(row["approved_on"].iloc[0])
                                or pd.isna(row["approval_body"].iloc[0])):
            unapproved.append(param)
            skipped.append(CriteriaWarning(
                criteria_set_id, param,
                f"승인 기록 없음(basis={row['basis'].iloc[0]}, "
                f"evidence_status={row['evidence_status'].iloc[0]}). "
                "통과여부를 찍지 않는다"))

    if missing:
        status = "기준미정"
    elif unapproved:
        status = "기준미승인"
    else:
        status = "판정완료"
    for w in skipped:
        warnings.warn(f"{w.criteria_set_id}.{w.param}: {w.reason}",
                      BacktestLedgerWarning, stacklevel=2)
    return values, status


# ---------------------------------------------------------------- 관측원장

def _month_shift(asof: str, months_back: int) -> str:
    """기준일에서 정수 개월 뒤로 간 달의 1일을 ISO 문자열로 돌려준다."""
    year, month = int(asof[:4]), int(asof[5:7])
    idx = year * 12 + (month - 1) - int(months_back)
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}-01"


def _grade_of(pd_value: float) -> tuple[str, str]:
    """PD에서 내부등급과 등급대를 얻는다. PD가 없으면 '미부여'."""
    if pd_value is None or not np.isfinite(pd_value):
        return "미부여", "미부여"
    g = pd_to_rating(float(np.clip(pd_value, 0.0, 1.0)))
    return g.grade, g.sa_bucket


def build_default_observation(
    portfolio: pd.DataFrame,
    exposure: pd.DataFrame,
    *,
    asof: str,
    criteria: pd.DataFrame | None = None,
    collateral: pd.DataFrame | None = None,
    seed: int = 42,
    lookback_months: int = _DEFAULT_LOOKBACK_MONTHS,
) -> pd.DataFrame:
    """부도 익스포저별 실측 관측원장을 만든다.

    ``portfolio``는 exposure_id·obligor_id·asset_class·pd·lgd·lgd_realized·
    ead·default_12m을 가져야 하고, ``exposure``는 RDM 익스포저 원장
    (exposure_id·drawn·undrawn·ccf_type)이어야 한다.

    부도월과 부도시점 인출액은 원천에 없어 여기서 만든다. 부도월은
    ``lookback_months`` 구간에 균등 배정하고, 부도시점 인출액은 기준시 인출액에
    미인출액의 일정 비율을 더해 만든다. 두 컬럼 모두 ``source_system=
    'synthetic'``으로 표시하며 실계 연결 시 첫 교체 대상이다.
    """
    need_p = {"exposure_id", "obligor_id", "asset_class", "pd", "lgd",
              "lgd_realized", "ead", "default_12m"}
    missing_p = need_p - set(portfolio.columns)
    if missing_p:
        raise ValueError(f"portfolio에 없는 컬럼: {sorted(missing_p)}")
    need_e = {"exposure_id", "drawn", "undrawn", "ccf_type"}
    missing_e = need_e - set(exposure.columns)
    if missing_e:
        raise ValueError(f"exposure에 없는 컬럼: {sorted(missing_e)}")
    if lookback_months < 1:
        raise ValueError("lookback_months는 1 이상이어야 한다")

    if criteria is None:
        criteria = build_backtest_criteria()
    values, _ = load_criteria(criteria, LGD_CRITERIA_SET,
                              gating=("workout_period_months",))
    workout = values.get("workout_period_months")

    cols = sorted(need_p)
    df = (portfolio.loc[portfolio["default_12m"] == 1, cols]
          .drop_duplicates(subset=["exposure_id"])
          .sort_values("exposure_id")
          .reset_index(drop=True))
    if df.empty:
        return _cast(pd.DataFrame(columns=DEFAULT_OBSERVATION.column_names),
                     DEFAULT_OBSERVATION)

    n = len(df)
    rng_month = np.random.default_rng(seed + _RNG_OFFSET_DEFAULT_MONTH)
    rng_draw = np.random.default_rng(seed + _RNG_OFFSET_DRAWDOWN)
    months = rng_month.integers(0, int(lookback_months), n).astype(int)
    uplift = _DRAWDOWN_FLOOR + _DRAWDOWN_SPAN * rng_draw.beta(
        _DRAWDOWN_BETA_A, _DRAWDOWN_BETA_B, n)

    exp = (exposure.drop_duplicates(subset=["exposure_id"])
           .set_index("exposure_id"))
    drawn = df["exposure_id"].map(exp["drawn"]).astype(float).fillna(0.0)
    undrawn = df["exposure_id"].map(exp["undrawn"]).astype(float).fillna(0.0)
    ccf_type = df["exposure_id"].map(exp["ccf_type"])
    limit = drawn + undrawn
    drawn_at_default = np.clip(drawn.to_numpy() + undrawn.to_numpy() * uplift,
                               0.0, limit.to_numpy())

    if collateral is not None and not collateral.empty:
        coll = (collateral.drop_duplicates(subset=["exposure_id"])
                .set_index("exposure_id")["collateral_type"])
        coll_type = df["exposure_id"].map(coll).fillna("무담보")
    else:
        coll_type = pd.Series("무담보", index=df.index)

    grades = [_grade_of(v) for v in df["pd"].to_numpy(dtype=float)]

    if workout is None:
        complete: list[bool | None] = [None] * n
        status = ["판정불가"] * n
    else:
        complete = [bool(m >= workout) for m in months]
        status = ["회수종료" if c else "관측중단" for c in complete]

    # 미인출액이 0이면 실측 CCF의 분모가 없다. 분모를 1로 바꿔 계산한 뒤
    # 그 자리를 NaN으로 덮어 0으로 나누는 일을 만들지 않는다.
    undrawn_arr = undrawn.to_numpy()
    has_commitment = undrawn_arr > 0.0
    ccf_realized = np.where(
        has_commitment,
        (drawn_at_default - drawn.to_numpy())
        / np.where(has_commitment, undrawn_arr, 1.0),
        np.nan)

    out = pd.DataFrame({
        "asof": asof,
        "exposure_id": df["exposure_id"].astype(str),
        "obligor_id": df["obligor_id"].astype(str),
        "segment": df["asset_class"].astype(str),
        "grade": [g for g, _ in grades],
        "grade_band": [b for _, b in grades],
        "collateral_type": coll_type.astype(str),
        "default_month": [_month_shift(asof, int(m)) for m in months],
        "months_since_default": months.astype("int64"),
        "workout_period_months": (float(workout) if workout is not None
                                  else np.nan),
        "workout_complete": complete,
        "censoring_status": status,
        "ead_at_default": df["ead"].astype(float),
        "lgd_estimated": df["lgd"].astype(float).clip(0.0, 1.0),
        "lgd_realized": df["lgd_realized"].astype(float).clip(0.0, 1.0),
        "ccf_type": ccf_type,
        "drawn_at_ref": drawn.to_numpy(),
        "undrawn_at_ref": undrawn_arr,
        "drawn_at_default": drawn_at_default,
        "ccf_realized": ccf_realized,
        "ccf_applied": ccf_type.map(CCF_BUCKETS).astype(float),
        "source_system": "synthetic",
        "note": ("부도월·부도시점 인출액은 원천에 없어 전용 시드 스트림으로 "
                 "만든 합성값이다"),
    })
    out["workout_period_months"] = out["workout_period_months"].astype("float64")
    return out[list(DEFAULT_OBSERVATION.column_names)].reset_index(drop=True)


# ---------------------------------------------------------------- 검정

def _paired_stats(diff: np.ndarray, ci_level: float | None
                  ) -> dict[str, float]:
    """편의 표본에서 t검정 통계량과 신뢰구간을 낸다.

    표본이 2건 미만이거나 분산이 0이면 t통계량이 정의되지 않는다. 그 경우
    NaN을 돌려주고 판정은 상위에서 표본부족으로 처리한다.
    """
    n = int(len(diff))
    nan = float("nan")
    if n == 0:
        return {"bias": nan, "mae": nan, "rmse": nan, "t_stat": nan,
                "p_value": nan, "ci_low": nan, "ci_high": nan}
    bias = float(np.mean(diff))
    mae = float(np.mean(np.abs(diff)))
    rmse = float(np.sqrt(np.mean(np.square(diff))))
    t_stat = p_value = ci_low = ci_high = nan
    if n >= 2:
        se = float(np.std(diff, ddof=1)) / np.sqrt(n)
        if se > 0.0:
            t_stat = bias / se
            p_value = float(2.0 * _student_t.sf(abs(t_stat), n - 1))
            if ci_level is not None and 0.0 < ci_level < 1.0:
                crit = float(_student_t.ppf(0.5 + ci_level / 2.0, n - 1))
                ci_low, ci_high = bias - crit * se, bias + crit * se
    return {"bias": bias, "mae": mae, "rmse": rmse, "t_stat": t_stat,
            "p_value": p_value, "ci_low": ci_low, "ci_high": ci_high}


def _judge(status: str, n: int, min_n: float | None,
           conditions: tuple[bool | None, ...]) -> tuple[bool | None, str]:
    """판정상태와 통과여부를 함께 정한다.

    기준이 미정·미승인이면 통과여부는 비운다. 기준이 갖춰져도 표본이 최소
    건수에 못 미치면 검정 결과를 신뢰할 수 없으므로 역시 비운다.
    """
    if status != "판정완료":
        return None, status
    if min_n is not None and n < int(min_n):
        return None, "표본부족"
    if any(c is None for c in conditions):
        return None, "표본부족"
    return bool(all(conditions)), "판정완료"


def build_lgd_backtest(observation: pd.DataFrame,
                       criteria: pd.DataFrame | None = None, *,
                       asof: str | None = None) -> pd.DataFrame:
    """LGD 사후검증 원장. 축별로 회수종료 부도건의 편의를 검정한다.

    관측중단 건은 검정 표본에서 빼고 건수만 ``n_censored``로 남긴다. 관측중단
    여부를 판정할 수 없는 건(회수기간 기준이 원장에 없는 경우)은 검정에도
    넣지 않고 관측중단으로도 세지 않으며, 판정상태가 ``기준미정``이 된다.
    """
    if criteria is None:
        criteria = build_backtest_criteria()
    values, status = load_criteria(criteria, LGD_CRITERIA_SET,
                                   gating=_LGD_GATING, optional=_OPTIONAL)
    alpha = values.get("significance_level")
    mae_tol = values.get("mae_tolerance")
    min_n = values.get("min_n_defaults")
    ci_level = values.get("ci_level")

    cols = list(LGD_BACKTEST.column_names)
    if observation.empty:
        return _cast(pd.DataFrame(columns=cols), LGD_BACKTEST)
    if asof is None:
        asof = str(observation["asof"].iloc[0])

    obs = observation[observation["asof"] == asof]
    rows = []
    # 축 이름이 곧 관측원장의 컬럼명이다.
    for axis in LGD_SEGMENT_AXES:
        for value, cell in obs.groupby(axis, sort=True):
            done = cell[cell["workout_complete"] == True]        # noqa: E712
            censored = cell[cell["workout_complete"] == False]   # noqa: E712
            # 실현 LGD가 비어 있는 건은 편의를 만들 수 없다. 평균과 검정이
            # 서로 다른 모집단을 보지 않도록 여기서 한 번에 걸러 낸다.
            diff = (done["lgd_realized"].astype(float)
                    - done["lgd_estimated"].astype(float))
            done = done[np.isfinite(diff)]
            d = diff[np.isfinite(diff)].to_numpy()
            st = _paired_stats(d, ci_level)
            n = int(len(d))
            cond_p = (None if not np.isfinite(st["p_value"]) or alpha is None
                      else st["p_value"] >= alpha)
            cond_mae = (None if not np.isfinite(st["mae"]) or mae_tol is None
                        else st["mae"] <= mae_tol)
            flag, judged = _judge(status, n, min_n, (cond_p, cond_mae))
            rows.append({
                "asof": asof, "segment_axis": axis,
                "segment_value": str(value),
                "n_defaults": n, "n_censored": int(len(censored)),
                "lgd_estimated_mean": (float(done["lgd_estimated"].mean())
                                       if n else float("nan")),
                "lgd_realized_mean": (float(done["lgd_realized"].mean())
                                      if n else float("nan")),
                "bias": st["bias"], "mae": st["mae"], "rmse": st["rmse"],
                "ci_level": (float(ci_level) if ci_level is not None
                             else float("nan")),
                "ci_low": st["ci_low"], "ci_high": st["ci_high"],
                "t_stat": st["t_stat"], "p_value": st["p_value"],
                "pass_flag": flag, "judgment_status": judged,
                "method": _LGD_METHOD, "censoring_rule": _CENSOR_RULE,
                "criteria_set_id": LGD_CRITERIA_SET,
                "citation": None,
                "note": ("판정기준이 내부기준이며 승인 전이다"
                         if judged == "기준미승인" else None),
            })
    out = pd.DataFrame(rows, columns=cols)
    return _cast(out, LGD_BACKTEST).sort_values(
        ["asof", "segment_axis", "segment_value"]).reset_index(drop=True)


def build_ccf_backtest(observation: pd.DataFrame,
                       criteria: pd.DataFrame | None = None, *,
                       asof: str | None = None) -> pd.DataFrame:
    """CCF 사후검증 원장. ccf_type × 등급대로 실측 CCF를 적용 CCF와 대조한다.

    실측 CCF는 (부도시 인출액 − 기준시 인출액) / 기준시 미인출액이다. 셀의
    대표값은 금액가중으로 내고, t검정은 약정건별 실측 CCF를 쓴다. 두 값이
    다를 수 있어 원장에 둘 다 남긴다.
    """
    if criteria is None:
        criteria = build_backtest_criteria()
    values, status = load_criteria(criteria, CCF_CRITERIA_SET,
                                   gating=_CCF_GATING, optional=_OPTIONAL)
    alpha = values.get("significance_level")
    bias_tol = values.get("bias_tolerance")
    min_n = values.get("min_n_facilities")
    ci_level = values.get("ci_level")

    cols = list(CCF_BACKTEST.column_names)
    if observation.empty:
        return _cast(pd.DataFrame(columns=cols), CCF_BACKTEST)
    if asof is None:
        asof = str(observation["asof"].iloc[0])

    obs = observation[(observation["asof"] == asof)
                      & observation["ccf_type"].notna()
                      & (observation["undrawn_at_ref"] > 0.0)]
    rows = []
    for (ccf_type, band), cell in obs.groupby(["ccf_type", "grade_band"],
                                              sort=True):
        applied = float(cell["ccf_applied"].iloc[0])
        # 실측 CCF를 못 만든 건은 금액 합계에서도 빼야 분자·분모가 같은
        # 모집단 위에 선다.
        cell = cell[np.isfinite(cell["ccf_realized"].astype(float))]
        realized = cell["ccf_realized"].astype(float).to_numpy()
        st = _paired_stats(realized - applied, ci_level)
        n = int(len(realized))
        undrawn_sum = float(cell["undrawn_at_ref"].sum())
        drawn_sum = float(cell["drawn_at_ref"].sum())
        dad_sum = float(cell["drawn_at_default"].sum())
        cond_p = (None if not np.isfinite(st["p_value"]) or alpha is None
                  else st["p_value"] >= alpha)
        cond_bias = (None if not np.isfinite(st["bias"]) or bias_tol is None
                     else abs(st["bias"]) <= bias_tol)
        flag, judged = _judge(status, n, min_n, (cond_p, cond_bias))
        rows.append({
            "asof": asof, "ccf_type": str(ccf_type), "grade_band": str(band),
            "n_facilities": n, "drawn_at_ref": drawn_sum,
            "undrawn_at_ref": undrawn_sum, "drawn_at_default": dad_sum,
            "ccf_realized": ((dad_sum - drawn_sum) / undrawn_sum
                             if undrawn_sum > 0.0 else float("nan")),
            "ccf_realized_mean": (float(np.mean(realized)) if n
                                  else float("nan")),
            "ccf_applied": applied, "bias": st["bias"],
            "ci_level": (float(ci_level) if ci_level is not None
                         else float("nan")),
            "ci_low": st["ci_low"], "ci_high": st["ci_high"],
            "t_stat": st["t_stat"], "p_value": st["p_value"],
            "pass_flag": flag, "judgment_status": judged,
            "method": _CCF_METHOD, "criteria_set_id": CCF_CRITERIA_SET,
            "citation": _CCF_CITATION,
            "note": ("판정기준이 내부기준이며 승인 전이다"
                     if judged == "기준미승인" else None),
        })
    out = pd.DataFrame(rows, columns=cols)
    return _cast(out, CCF_BACKTEST).sort_values(
        ["asof", "ccf_type", "grade_band"]).reset_index(drop=True)


def _cast(df: pd.DataFrame, spec: TableSpec) -> pd.DataFrame:
    """스펙의 int·float 컬럼 dtype을 맞춘다.

    빈 프레임이나 전건 NaN 컬럼은 pandas가 object로 두는데, 스펙 검증이
    dtype 위반으로 잡는다. 부도가 한 건도 없는 기준일에도 원장은 스펙을
    통과해야 화면과 검증이 같은 계약 위에 선다.
    """
    for col in spec.columns:
        if col.name not in df.columns:
            continue
        if col.dtype == "float":
            df[col.name] = pd.to_numeric(df[col.name], errors="coerce"
                                         ).astype("float64")
        elif col.dtype == "int":
            df[col.name] = df[col.name].astype("int64")
    return df


# ---------------------------------------------------------------- 묶음

def build_lgd_ead_backtest_ledgers(
    portfolio: pd.DataFrame,
    exposure: pd.DataFrame,
    *,
    asof: str,
    criteria: pd.DataFrame | None = None,
    collateral: pd.DataFrame | None = None,
    seed: int = 42,
    lookback_months: int = _DEFAULT_LOOKBACK_MONTHS,
) -> dict[str, pd.DataFrame]:
    """LGD·EAD 실측 모니터링 원장 넉 장을 한 번에 만든다."""
    if criteria is None:
        criteria = build_backtest_criteria()
    obs = build_default_observation(
        portfolio, exposure, asof=asof, criteria=criteria,
        collateral=collateral, seed=seed, lookback_months=lookback_months)
    return {
        "crm_backtest_criteria": criteria,
        "crm_default_observation": obs,
        "crm_lgd_backtest": build_lgd_backtest(obs, criteria, asof=asof),
        "crm_ccf_backtest": build_ccf_backtest(obs, criteria, asof=asof),
    }
