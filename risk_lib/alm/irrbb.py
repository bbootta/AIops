"""IRRBB — ΔEVE를 **현금흐름 원장에서** 산출한다 (설계 §1.1·§2.6).

**무엇이 틀려 있었나.** 현행 `compute_irrbb`는 리프라이싱 *갭*을 버킷 중점에서
평면 3% 곡선으로 할인하는 근사였고, 슬로팅·할인·최악시나리오 선택을 한 함수
안에서 해치웠다. 그 결과 중간산출이 원장에 남지 않아, 화면
(`ops_pages/core_capital_alm.py:726`)이 파이프라인 메모리 객체에서 직접 읽는
`pv_effect_worst`에 대응하는 테이블이 아예 없었다. 갭에는 회차도 옵션성도
없으므로 상환방식·조기상환·계약/행동 분리가 **원리적으로** 표현되지 않았다.
시나리오 계수는 함수 본문에 숫자로 박혀 있었다.

이 모듈이 바꾸는 것은 세 가지다.

  · 입력이 `alm_cashflow_bucket` 원장 하나다. 포트폴리오 DataFrame도, 상수
    가중 벡터(`balance_sheet.py:93-98`)도 읽지 않는다 — 포트폴리오 만기
    분포가 바뀌면 현금흐름이 바뀌고 ΔEVE가 반드시 따라 움직인다.
  · 중간산출이 원장으로 나온다. `alm_irrbb_bucket_pv`가 버킷별 cf·DF·PV·
    ΔPV를 담고, 버킷 ΔPV의 합이 `alm_irrbb_result.delta_eve`와 대사된다.
  · 계수가 함수 본문에 없다. 충격 bp·시나리오 계수·충격후 하한은 전부
    `curves.py`의 원장에서 오고, 아웃라이어 기준은 인자다.

**마진 처리가 EVE와 NII에서 반대다.** ΔEVE 현금흐름은 원금 + `interest_cf_ex_margin`
이며 `margin_cf`를 **제외**한다(BCBS d368 §132(3)). ΔNII는 마진을 **포함**한다
(EBA GL 2022-14, `nii.py`). 두 지표가 같은 이름의 현금흐름을 반대로 쓰므로
`margin_treatment`를 두 원장의 컬럼으로 둔다 — 조용한 규약으로 두면 이 차이가
보이지 않는다.

**산출기준 두 벌.** `basis ∈ {계약, 행동조정}`을 모두 산출한다. 계약기준이면
비만기예금이 전액 최단 버킷(듀레이션 ≈ 0)이고 행동기준이면 4~5년에 퍼지므로
ΔEVE가 자릿수로 갈린다 — 감독당국이 비교하는 것이 정확히 이 차이다.

**부호 규약을 한 번만 정한다.** 현금흐름은 `SIDE_SIGN`으로 부호를 받아
(자산 +, 부채 −) 저장되고, `delta_eve`는 **부호 있는** 값이다(손실 = 음수).
`worst_eve_decline = max(−delta_eve, 0)`은 뷰에서 파생한다. 현행은 부호 있는
`pct_tier1`과 항상 양수인 `worst_pct_tier1`이 같은 이름으로 두 화면에 나가
반대 규약으로 그려지고 있었다.

**통화 간 상계를 허용하지 않는다.** [별표 9-1] 제13항 다는 "각 통화별로 EVE
리스크가 손실일 경우만 합산하여 금리충격 시나리오에 대한 EVE 리스크를
산출한다"고 적는다. 이익이 난 통화는 버린다. 직전 회차는
`groupby(['basis','scenario'])` 단순 합산이라 이익 통화가 손실 통화를 상계해
총리스크를 과소산출했다. 지금은 통화별로 먼저 접고 손실만 더하며, 상계 허용
시의 값을 `delta_eve_gross`에 남겨 두 값의 차이가 원장에서 읽히게 한다.

**아웃라이어 기준은 원문확인이다.** [별표 9-1] 제21항 나는 ΔEVE로 산출한 총
금리리스크가 **기본자본(Tier 1)의 15%**를 초과하면 금리리스크가 과도한 것으로
간주한다고 적는다. 분모는 총자기자본이 아니다. 제21항 다는 초과 시 원인과
대책을 감독원장에게 보고할 의무를 둔다 — 그 의무를 `outlier_duty` 컬럼으로
원장에 싣는다. 판정을 끄고 싶으면 호출부가 `outlier_threshold=None`을 명시해야
하며, 그때는 판정하지 않았다는 사실이 NULL로 남는다.

직전 회차가 "국내 [별표 9의1] 제27항은 자기자본의 20%이고 지표도 금리 VaR"
이라고 적어 둔 것은 2014년 개정본이며 2019.11.29. 개정으로 폐지됐다. 현행
국내기준과 BCBS 기준이 같은 15%·기본자본이다.

**계승 경로.** `compute_irrbb(repricing, tier1)`은 갭 사다리를 받는 기존
호출부(`pipeline.py:595`)를 위해 남긴다. 갭을 버킷 현금흐름 모양으로 옮겨
같은 엔진에 태우고, 원장 두 장과 `by_scenario`·`worst_eve`가 함께 나온다
(`materialize.py:327,342`의 폴백 결함 해소). 평면 곡선을 쓴다는 사실은 결과의
`warnings`에 실린다. 계승 경로의 계정도 현행 [별표 9-1] 2026이며, KRW 충격폭은
평행 225 · 단기 350 · 장기 225다. 직전 회차가 쓰던 300/400/200은 d578이 대체한
폐지값이다.

**미등재.** 아래 TableSpec 2장은 아직 `datamodel.catalog.ALL_TABLES`에 넣지
않았다 — 카탈로그 등재는 실체화·ARCHITECTURE.md 수치 검사와 함께 움직이므로
배선 단계에서 `params.PARAM_TABLES`·`curves.CURVE_TABLES`와 같이 등재한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from risk_lib.alm.behaviour import ParamWarning
from risk_lib.alm.cashflow import BASES
from risk_lib.alm.curves import (
    FRAMEWORK_STATUSES, HEADLINE_FRAMEWORK_VERSION, Curve, ShockedCurve,
    build_post_shock_floor, build_rate_shock_param, build_scenario_def,
    discount_factors, framework_status, nii_scenarios, shocked_curve,
)
from risk_lib.alm.params import EVIDENCE_STATUS, IRRBB_SCENARIOS, SIDES
from risk_lib.datamodel.spec import ColumnSpec as C, ForeignKey as FK, TableSpec
from risk_lib.references import (
    IRRBB_EARLY_WARNING_PCT_TIER1, IRRBB_OUTLIER_DUTY,
    IRRBB_OUTLIER_EVE_PCT_TIER1,
)

__all__ = [
    "SCENARIOS", "BASE_SCENARIO", "SIDE_SIGN",
    "MARGIN_EXCLUDED", "MARGIN_EVE_ONLY", "MARGIN_EVE_AND_NII",
    "IRRBB_BUCKET_PV", "IRRBB_RESULT", "IRRBB_TABLES",
    "IRRBBResult", "build_shocked_curves", "build_bucket_pv",
    "build_irrbb_result", "compute_irrbb_from_cashflows",
    "by_scenario", "worst_row", "worst_eve", "worst_eve_decline",
    "shock_curve", "compute_irrbb",
]

# 시나리오 순서 = 서식 라인 순서다. `forms.py:584`가 이 순서로 20xx 라인을
# 붙이므로 순서를 바꾸면 제출서식의 라인번호가 바뀐다.
SCENARIOS: list[str] = list(IRRBB_SCENARIOS)
BASE_SCENARIO = "base"

# 부호 규약. 현금흐름 원장은 금액을 양수로 담고 측(side)으로 방향을 표시하므로,
# PV를 합산하려면 여기서 한 번만 부호를 붙인다. 부외(off_balance)는 자체 부호를
# 계약원장이 들고 와야 하는데 그 원장이 아직 없다 — 그래서 +1로 두지 않고 막는다.
SIDE_SIGN: dict[str, float] = {"asset": 1.0, "liability": -1.0}

MARGIN_EXCLUDED = "제외"
MARGIN_EVE_ONLY = "ΔEVE 마진제외"
MARGIN_EVE_AND_NII = "ΔEVE 마진제외 · ΔNII 마진포함"
RESULT_MARGIN_TREATMENTS = (MARGIN_EVE_ONLY, MARGIN_EVE_AND_NII)

_EVE_CITATION = (
    "[별표 9-1] 제13항 (개정 2026.1.29) — 만기구간별 현금흐름을 충격후 금리로 "
    "연속복리 할인하고, 각 통화별 EVE 리스크가 손실일 경우만 합산하며(다), "
    "6개 시나리오 중 최대값이 최종 ΔEVE다(라). 현금흐름에서 상업마진 제외는 "
    "BCBS d368 §132(3). 아웃라이어 시험은 제21항 나(기본자본의 15%)")

# 계승 경로 전용 상수. 새 엔진은 커브를 인자로 받으므로 여기 말고는 쓰이지 않는다.
_LEGACY_FRAMEWORK = HEADLINE_FRAMEWORK_VERSION
_LEGACY_CCY = "KRW"
# 현행 `compute_irrbb(base_rate=0.03)`의 함수 기본값을 그대로 옮긴 값이다.
# 파이프라인이 `mkt_risk_factor` 커브를 넘기기 시작하면 이 상수는 사라진다.
_LEGACY_FLAT_BASE_RATE = 0.03


# ---------------------------------------------------------------- 스펙

IRRBB_BUCKET_PV = TableSpec(
    name="alm_irrbb_bucket_pv", korean="IRRBB 버킷별 현재가치 효과",
    product="PRD-ALM",
    grain="기준일 × 시나리오 × 산출기준 × 통화 × 측 × 시간버킷 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("scenario", "string", "시나리오", nullable=False,
          allowed=IRRBB_SCENARIOS),
        C("basis", "string", "산출기준", nullable=False, allowed=BASES),
        C("ccy", "string", "통화", nullable=False),
        C("side", "string", "측", nullable=False, allowed=SIDES),
        C("bucket", "string", "시간버킷", nullable=False),
        C("seq", "int", "버킷 순서", nullable=False, min_value=1),
        C("t_mid", "float", "버킷 중점", nullable=False, unit="years",
          min_value=0.0),
        C("cf", "float", "충격 시나리오 현금흐름", nullable=False, unit="KRW",
          note="부호 있음(자산 +, 부채 −). 원금 + 마진제외 이자이며 margin_cf는 "
               "빠져 있다"),
        C("cf_base", "float", "무충격 현금흐름", nullable=False, unit="KRW",
          note="행동조정 기준에서는 시나리오별 CF가 다르므로 기준 다리를 따로 "
               "담아야 pv_base가 원장에서 재현된다"),
        C("df_base", "float", "기저 할인계수", nullable=False, unit="ratio",
          min_value=0.0),
        C("df_shocked", "float", "충격후 할인계수", nullable=False, unit="ratio",
          min_value=0.0),
        C("pv_base", "float", "기저 현재가치", nullable=False, unit="KRW"),
        C("pv_shocked", "float", "충격후 현재가치", nullable=False, unit="KRW"),
        C("delta_pv", "float", "현재가치 효과", nullable=False, unit="KRW",
          note="pv_shocked − pv_base. 버킷 합계가 alm_irrbb_result.delta_eve와 "
               "일치해야 한다"),
        C("margin_treatment", "string", "마진 처리", nullable=False,
          allowed=(MARGIN_EXCLUDED,),
          citation="BCBS d368 §132(3) — ΔEVE 현금흐름에서 상업마진 제외"),
    ),
    primary_key=("asof", "scenario", "basis", "ccy", "side", "bucket"),
    foreign_keys=(FK(("asof", "scenario", "basis", "ccy", "side", "bucket"),
                     "alm_cashflow_bucket",
                     ("asof", "scenario", "basis", "ccy", "side", "bucket")),),
    note="화면의 pv_effect_worst가 대응하는 원장이다. 현행은 이 값이 파이프라인 "
         "메모리 객체에만 있고 원장에는 없었다.",
)

IRRBB_RESULT = TableSpec(
    name="alm_irrbb_result", korean="IRRBB 시나리오별 산출결과", product="PRD-ALM",
    grain="기준일 × 산출기준 × 시나리오 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("basis", "string", "산출기준", nullable=False, allowed=BASES,
          note="계약 vs 행동조정을 나란히 둔다 — 감독당국이 비교하는 차이다"),
        C("scenario", "string", "시나리오", nullable=False,
          allowed=IRRBB_SCENARIOS),
        C("delta_eve", "float", "ΔEVE", nullable=False, unit="KRW",
          citation="[별표 9-1] 제13항 다 — 각 통화별 EVE 리스크가 손실일 "
                   "경우만 합산한다. 통화 간 상계를 허용하지 않는다",
          note="부호 있음 — 손실이 음수다. 이익이 난 통화는 합산에서 빠지므로 "
               "전 통화가 이익인 시나리오는 0이다"),
        C("delta_eve_gross", "float", "ΔEVE (통화 상계 허용)", nullable=False,
          unit="KRW",
          note="통화별 값을 부호 그대로 더한 값. 규정 산출값이 아니라 대조용 "
               "이다. delta_eve − delta_eve_gross가 상계 금지로 버린 이익 "
               "금액이며, 이 두 칸이 같으면 이익 통화가 없었다는 뜻이다"),
        C("delta_eve_to_tier1", "float", "ΔEVE / 기본자본", nullable=False,
          unit="ratio", note="부호 있음. 감소율은 뷰에서 −값을 취해 만든다"),
        C("delta_nii", "float", "ΔNII (12개월)", nullable=True, unit="KRW",
          citation="평행충격 2개만 산출된다 (alm_scenario_def.applies_to_nii)"),
        C("tier1", "float", "기본자본", nullable=False, unit="KRW",
          min_value=0.0),
        C("is_worst", "bool", "최악 시나리오", nullable=False,
          note="산출기준별로 delta_eve 최솟값 1개. 부호 절단 전에 정한다"),
        C("outlier_test_pass", "bool", "아웃라이어 기준 충족", nullable=True,
          citation="[별표 9-1] 제21항 나 (개정 2026.1.29) — ΔEVE에 의하여 "
                   "산출한 총 금리리스크가 세칙 <별표3>에서 정하는 기본자본의 "
                   "15%를 초과하는 은행은 금리리스크가 과도한 것으로 간주",
          note="호출부가 outlier_threshold=None을 명시하면 판정하지 않고 "
               "NULL이 남는다"),
        C("outlier_duty", "text", "초과 시 조치의무", nullable=True,
          citation="[별표 9-1] 제21항 나·다 — 헤지·포지션 조정 또는 추가 "
                   "자기자본 보유, 그리고 초과 원인·대책의 감독원장 보고",
          note="기준을 넘긴 행에만 채운다. 판정만 남기고 의무를 남기지 않으면 "
               "결재선이 무엇을 해야 하는지가 산출물 밖에 있게 된다"),
        C("margin_treatment", "string", "마진 처리", nullable=False,
          allowed=RESULT_MARGIN_TREATMENTS,
          citation="BCBS d368 §132(3) 제외 / EBA GL 2022-14 포함 — 두 지표가 "
                   "반대로 취급한다"),
        C("framework_version", "string", "충격 모수 계정", nullable=False),
        C("framework_status", "string", "계정 시행 상태", nullable=False,
          allowed=FRAMEWORK_STATUSES,
          note="'현행'이 아닌 계정으로 낸 수치가 현행 수치와 같은 칸에 놓이면 "
               "구별되지 않는다. 폐지 계정(별표9의1_2014)을 고르면 이 칸이 "
               "'폐지'이고 산출 경고에 폐지 사유가 남는다"),
        C("shock_source", "string", "충격 모수 출처", nullable=False,
          note="'직접' — 통화 자기 행의 충격폭을 썼다는 뜻이다. 프록시 경로는 "
               "1차자료로 21개 통화 충격폭이 확정된 뒤 제거했다"),
        C("citation", "text", "근거", nullable=True),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("asof", "basis", "scenario"),
    note="ΔEVE는 무위험 할인 + 마진 제외, ΔNII는 마진 포함이다. 통화 간 합산은 "
         "제13항 다에 따라 손실 통화만 더하며 상계를 허용하지 않는다. 상계를 "
         "허용했을 때의 값은 delta_eve_gross에 남는다.",
)

IRRBB_TABLES: tuple[TableSpec, ...] = (IRRBB_BUCKET_PV, IRRBB_RESULT)


# ---------------------------------------------------------------- 결과 객체

@dataclass
class IRRBBResult:
    """산출 원장 두 장 + 계승 소비자가 읽는 뷰.

    `report`·`forms`·`api`·`materialize`·`consistency`가 이미 읽고 있는 이름
    (`delta_eve`·`worst_eve_decline`·`worst_pct_tier1`·`repricing`)을 속성으로
    유지한다. 새로 생긴 `by_scenario`·`worst_eve`는 `materialize.py:327,342`가
    `getattr`로 찾다가 못 찾아 `alm_irrbb_shock`을 6행이 아니라 1행
    (`delta_eve=0.0`)으로 만들던 폴백 결함을 닫는다.
    """
    result: pd.DataFrame                 # alm_irrbb_result (basis 두 벌)
    bucket_pv: pd.DataFrame              # alm_irrbb_bucket_pv
    tier1: float
    headline_basis: str                  # 헤드라인 스칼라를 뽑는 산출기준
    repricing: pd.DataFrame              # 사다리 뷰 + pv_effect_worst
    warnings: list[ParamWarning] = field(default_factory=list)
    base_rate: float | None = None       # 계승 경로의 평면 곡선 수준

    # ---- 계승 뷰 --------------------------------------------------------
    @property
    def delta_eve(self) -> pd.DataFrame:
        """시나리오 × (delta_eve, pct_tier1) — 헤드라인 산출기준."""
        return by_scenario(self.result, basis=self.headline_basis)

    @property
    def by_scenario(self) -> pd.DataFrame:
        """`delta_eve`와 같은 뷰. 실체화가 이 이름으로 찾는다."""
        return self.delta_eve

    @property
    def delta_nii(self) -> pd.DataFrame:
        d = self.result[(self.result["basis"] == self.headline_basis)
                        & self.result["delta_nii"].notna()]
        return d[["scenario", "delta_nii"]].reset_index(drop=True)

    @property
    def worst_eve_scenario(self) -> str:
        return str(worst_row(self.result, basis=self.headline_basis)["scenario"])

    @property
    def worst_eve(self) -> float:
        """최악 시나리오의 **부호 있는** ΔEVE. 손실이면 음수다."""
        return worst_eve(self.result, basis=self.headline_basis)

    @property
    def worst_eve_decline(self) -> float:
        """감소액(양수). 전 시나리오가 이익이면 0이다."""
        return worst_eve_decline(self.result, basis=self.headline_basis)

    @property
    def worst_pct_tier1(self) -> float:
        return self.worst_eve_decline / self.tier1

    def outlier(self) -> bool:
        """아웃라이어 여부 — 총 금리리스크가 기본자본의 15%를 넘는가
        ([별표 9-1] 제21항 나).

        원장의 `outlier_test_pass`가 같은 기준으로 판정하므로 두 자리가 하나다
        (기준이 원문확인이 되기 전에는 원장이 NULL이고 이 메서드만 판정했다).
        """
        return self.worst_pct_tier1 > IRRBB_OUTLIER_EVE_PCT_TIER1

    def early_warning(self) -> bool:
        return self.worst_pct_tier1 > IRRBB_EARLY_WARNING_PCT_TIER1

    def warning_frame(self) -> pd.DataFrame:
        return pd.DataFrame([{"model": w.model, "scope": w.scope,
                              "param": w.param, "reason": w.reason}
                             for w in self.warnings],
                            columns=["model", "scope", "param", "reason"])


# ---------------------------------------------------------------- 원장 조회

def _pick_basis(result: pd.DataFrame, basis: str | None) -> pd.DataFrame:
    if basis is not None:
        d = result[result["basis"] == basis]
        if d.empty:
            raise KeyError(f"alm_irrbb_result에 basis={basis!r} 행이 없다")
        return d
    kinds = sorted({str(b) for b in result["basis"]})
    if len(kinds) > 1:
        raise ValueError(
            f"산출기준이 여럿이다 {kinds} — basis를 명시해야 어느 기준의 "
            "수치인지가 남는다")
    return result


def by_scenario(result: pd.DataFrame, *, basis: str | None = None
                ) -> pd.DataFrame:
    """시나리오별 ΔEVE 뷰 — `scenario`, `delta_eve`, `pct_tier1`.

    컬럼명은 계승 소비자(`sensitivity.py:84`가 `.loc['parallel_up','delta_eve']`,
    서식이 `row['pct_tier1']`)를 그대로 살린다. 정렬은 표준 시나리오 순서이며
    이것이 제출서식의 라인 순서다.
    """
    d = _pick_basis(result, basis).copy()
    d["_order"] = d["scenario"].map({s: i for i, s in enumerate(SCENARIOS)})
    d = d.sort_values("_order")
    return (d.rename(columns={"delta_eve_to_tier1": "pct_tier1"})
             [["scenario", "delta_eve", "pct_tier1"]].reset_index(drop=True))


def worst_row(result: pd.DataFrame, *, basis: str | None = None) -> pd.Series:
    """`is_worst` 행. 원장 플래그를 읽을 뿐 여기서 다시 고르지 않는다 —
    다시 고르면 원장과 화면이 갈라질 수 있다."""
    d = _pick_basis(result, basis)
    hit = d[d["is_worst"].astype(bool)]
    if len(hit) != 1:
        raise ValueError(
            f"is_worst 행이 {len(hit)}건이다 — 산출기준별로 정확히 1건이어야 한다")
    return hit.iloc[0]


def worst_eve(result: pd.DataFrame, *, basis: str | None = None) -> float:
    """최악 시나리오의 부호 있는 ΔEVE (손실 = 음수)."""
    return float(worst_row(result, basis=basis)["delta_eve"])


def worst_eve_decline(result: pd.DataFrame, *, basis: str | None = None
                      ) -> float:
    """감소액(양수). 전 시나리오가 이익이면 0 — 뷰에서 파생하는 값이다."""
    return max(-worst_eve(result, basis=basis), 0.0)


# ---------------------------------------------------------------- 충격곡선

def build_shocked_curves(
    curves: dict[str, Curve], *, scenarios: tuple[str, ...] | list[str],
    shock_param: pd.DataFrame, scenario_def: pd.DataFrame,
    floor: pd.DataFrame, framework_version: str, allow_proxy: bool = False,
) -> tuple[dict[tuple[str, str], ShockedCurve], list[ParamWarning]]:
    """(통화, 시나리오) → 충격곡선. 모수가 비어 있는 조합은 **넣지 않는다**.

    ΔEVE와 ΔNII가 같은 곡선을 써야 두 지표가 갈라지지 않으므로 곡선 생성은
    여기 한 군데다. 모수가 NULL이면 `curves.shocked_curve`가 None을 돌려주고,
    그 시나리오는 결과 원장에서 아예 빠진다 — 조용히 0으로 채우지 않는다.

    `allow_proxy`는 `curves.shocked_curve`로 그대로 넘기며 거기서 무시된다.
    프록시 경로 제거의 잔재이고, 호출부가 인자를 떼면 함께 사라진다.
    """
    out: dict[tuple[str, str], ShockedCurve] = {}
    warns: list[ParamWarning] = []
    for ccy in sorted(curves):
        for sc in scenarios:
            shk, w = shocked_curve(
                curves[ccy], sc, ccy=ccy, framework_version=framework_version,
                shock_param=shock_param, scenario_def=scenario_def,
                floor=floor, allow_proxy=allow_proxy)
            warns.extend(w)
            if shk is not None:
                out[(ccy, sc)] = shk
    return out, list(dict.fromkeys(warns))


# ---------------------------------------------------------------- 버킷 PV

_MERGE_KEYS = ["basis", "ccy", "side", "bucket", "seq", "t_mid"]


def _eve_cashflow(df: pd.DataFrame) -> pd.Series:
    """ΔEVE 현금흐름 = (원금 + 마진제외 이자) × 측 부호.

    `margin_cf`를 더하지 않는 것이 BCBS d368 §132(3)이다. 더하면 ΔNII와 같은
    현금흐름을 쓰게 되어 두 지표의 정의 차이가 사라진다.
    """
    unknown = sorted(set(df["side"]) - set(SIDE_SIGN))
    if unknown:
        raise ValueError(
            f"부호 규약이 없는 측: {unknown} — 부외 현금흐름은 계약원장이 자체 "
            "부호를 들고 와야 하며, 임의로 +1을 붙이면 ΔEVE 부호가 조용히 "
            "틀린다")
    sign = df["side"].map(SIDE_SIGN).to_numpy(dtype=float)
    return (df["principal_cf"] + df["interest_cf_ex_margin"]) * sign


def build_bucket_pv(
    bucket_cf: pd.DataFrame, *, asof: str | None, curves: dict[str, Curve],
    shocked: dict[tuple[str, str], ShockedCurve],
) -> pd.DataFrame:
    """`alm_irrbb_bucket_pv` — 버킷별 현금흐름 → DF → PV → ΔPV.

    기준 다리는 무충격 시나리오(`base`)의 현금흐름을 기저 곡선으로, 충격 다리는
    해당 시나리오의 현금흐름을 충격곡선으로 할인한다. 행동조정 기준에서는 CPR·
    TDRR 승수가 시나리오 함수이므로 **두 다리의 현금흐름이 서로 다르다** —
    같은 CF를 두 곡선으로만 할인하면 행동 반응이 ΔEVE에서 사라진다.

    `asof=None`은 기준일이 아직 배선되지 않은 계승 경로(`compute_irrbb`) 전용
    이다. 그 산출물은 `asof`가 비어 있으므로 원장 스펙을 만족하지 않는다 —
    화면에 붙이려면 호출부가 기준일을 넘겨야 한다.
    """
    d = bucket_cf if asof is None else bucket_cf[bucket_cf["asof"] == asof]
    if d.empty:
        raise ValueError(f"alm_cashflow_bucket에 asof={asof} 행이 없다")
    base = d[d["scenario"] == BASE_SCENARIO].copy()
    if base.empty:
        raise ValueError(
            "무충격(base) 시나리오 현금흐름이 없다 — ΔEVE의 기준 다리를 만들 수 "
            "없다")
    base["cf_base"] = _eve_cashflow(base)
    base = base[_MERGE_KEYS + ["cf_base"]]

    parts: list[pd.DataFrame] = []
    for (ccy, sc), shk in sorted(shocked.items()):
        cur = d[(d["ccy"] == ccy) & (d["scenario"] == sc)].copy()
        if cur.empty:
            continue
        cur["cf"] = _eve_cashflow(cur)
        m = cur[_MERGE_KEYS + ["cf"]].merge(base, on=_MERGE_KEYS, how="outer")
        m[["cf", "cf_base"]] = m[["cf", "cf_base"]].fillna(0.0)
        t = m["t_mid"].to_numpy(dtype=float)
        m["asof"], m["scenario"] = asof, sc
        m["df_base"] = discount_factors(curves[ccy], t)
        m["df_shocked"] = discount_factors(shk.curve, t)
        m["pv_base"] = m["cf_base"] * m["df_base"]
        m["pv_shocked"] = m["cf"] * m["df_shocked"]
        m["delta_pv"] = m["pv_shocked"] - m["pv_base"]
        m["margin_treatment"] = MARGIN_EXCLUDED
        parts.append(m)

    if not parts:
        return pd.DataFrame(columns=list(IRRBB_BUCKET_PV.column_names))
    out = pd.concat(parts, ignore_index=True)
    out["_order"] = out["scenario"].map({s: i for i, s in enumerate(SCENARIOS)})
    out = out.sort_values(["basis", "ccy", "_order", "side", "seq"])
    return out[list(IRRBB_BUCKET_PV.column_names)].reset_index(drop=True)


# ---------------------------------------------------------------- 결과 원장

def _aggregate_across_currencies(bucket_pv: pd.DataFrame) -> pd.DataFrame:
    """통화별로 먼저 접고 **손실 통화만** 더한다 ([별표 9-1] 제13항 다).

    "각 통화별로 EVE 리스크가 손실일 경우만 합산"이므로 이익이 난 통화는
    버린다. 통화 축을 접기 전에 합산하면 이익 통화가 손실 통화를 상계해
    총 금리리스크가 과소산출되고, 아웃라이어 판정이 그만큼 느슨해진다.

    상계를 허용했을 때의 값(`delta_eve_gross`)을 함께 돌려준다. 두 값이 같으면
    이익 통화가 없었다는 뜻이고, 다르면 그 차이가 규정이 버리라고 한 금액이다.
    """
    per_ccy = (bucket_pv.groupby(["basis", "scenario", "ccy"],
                                 as_index=False)["delta_pv"].sum())
    # delta_pv는 충격후 PV − 기저 PV이므로 손실이 음수다. 손실 통화만 남기려면
    # 양수(이익)를 0으로 자른다.
    per_ccy["loss_only"] = per_ccy["delta_pv"].clip(upper=0.0)
    return (per_ccy.groupby(["basis", "scenario"], as_index=False)
            .agg(delta_eve=("loss_only", "sum"),
                 delta_eve_gross=("delta_pv", "sum")))


def build_irrbb_result(
    bucket_pv: pd.DataFrame, *, asof: str | None, tier1: float,
    framework_version: str, shock_source: dict[str, str],
    delta_nii: pd.DataFrame | None = None,
    outlier_threshold: float | None = IRRBB_OUTLIER_EVE_PCT_TIER1,
    outlier_evidence: str = "원문확인",
    framework_status: str = "현행",
) -> pd.DataFrame:
    """`alm_irrbb_result` — 버킷 ΔPV를 산출기준 × 시나리오로 접는다.

    `tier1 ≤ 0` 가드가 있다. 현행 `irrbb.py:119`는 방어 없이 나누므로 자본이
    소진된 스트레스 경로에서 0나눗셈이 난다.

    통화 간 합산은 제13항 다를 따른다 — 손실 통화만 더하고 이익 통화는 버린다.

    아웃라이어 판정 기본값은 [별표 9-1] 제21항 나의 기본자본 15%다.
    `outlier_threshold=None`을 명시하면 판정하지 않고 NULL이 남는다.
    """
    if not tier1 > 0:
        raise ValueError(
            f"기본자본이 {tier1}이다 — ΔEVE/Tier1은 정의되지 않는다. 자본이 "
            "소진된 경로는 비율이 아니라 그 사실을 보고해야 한다")
    if bucket_pv.empty:
        return pd.DataFrame(columns=list(IRRBB_RESULT.column_names))

    g = _aggregate_across_currencies(bucket_pv)
    g["_order"] = g["scenario"].map({s: i for i, s in enumerate(SCENARIOS)})
    g = g.sort_values(["basis", "_order"]).reset_index(drop=True)
    g["asof"], g["tier1"] = asof, float(tier1)
    g["delta_eve_to_tier1"] = g["delta_eve"] / float(tier1)
    # 최악은 산출기준별로 고른다. 부호 절단 전에 고르므로 전 시나리오가 이익인
    # 포트폴리오에서도 "최악"은 최소 ΔEVE 시나리오이지 0이 아니다. 동점(갭이
    # 0인 사다리에서는 6개가 전부 0이다)은 표준 시나리오 순서로 끊는다 —
    # 끊지 않으면 최악 시나리오가 6개가 되어 서식·화면이 무엇을 그릴지 모른다.
    g["is_worst"] = False
    g.loc[g.groupby("basis")["delta_eve"].idxmin(), "is_worst"] = True

    if delta_nii is not None and not delta_nii.empty:
        g = g.merge(delta_nii[["scenario", "delta_nii"]], on="scenario",
                    how="left")
    else:
        g["delta_nii"] = np.nan
    g["margin_treatment"] = np.where(g["delta_nii"].notna(),
                                     MARGIN_EVE_AND_NII, MARGIN_EVE_ONLY)

    if outlier_threshold is None:
        g["outlier_test_pass"] = pd.array([None] * len(g), dtype="boolean")
        g["outlier_duty"] = None
    else:
        g["outlier_test_pass"] = pd.array(
            -g["delta_eve_to_tier1"] <= float(outlier_threshold),
            dtype="boolean")
        # 의무는 초과한 행에만 붙인다. 전 행에 붙이면 어느 시나리오가 실제로
        # 보고 대상인지가 보이지 않는다.
        g["outlier_duty"] = np.where(
            g["outlier_test_pass"].to_numpy(dtype=bool),
            None, IRRBB_OUTLIER_DUTY)
    g["framework_version"] = framework_version
    g["framework_status"] = framework_status
    g["shock_source"] = g["scenario"].map(shock_source)
    g["citation"], g["evidence_status"] = _EVE_CITATION, outlier_evidence
    return g[list(IRRBB_RESULT.column_names)].reset_index(drop=True)


def _repricing_view(bucket_pv: pd.DataFrame, *, basis: str,
                    worst_scenario: str) -> pd.DataFrame:
    """사다리 뷰 — 계승 소비자(`prudential/liquidity.py:70`, 화면)가 읽는 모양.

    현행은 이 사다리를 `balance_sheet.py`의 상수 가중 벡터가 만들었다. 여기서는
    현금흐름 원장에서 접으므로 포트폴리오가 바뀌면 사다리도 바뀐다.
    """
    d = bucket_pv[(bucket_pv["basis"] == basis)
                  & (bucket_pv["scenario"] == worst_scenario)]
    if d.empty:
        return pd.DataFrame(columns=["bucket", "t_mid", "assets", "liabilities",
                                     "gap", "pv_effect_worst"])
    g = d.groupby(["bucket", "seq", "t_mid"], as_index=False).agg(
        gap=("cf_base", "sum"), pv_effect_worst=("delta_pv", "sum"))
    pos = (d[d["side"] == "asset"].groupby("bucket")["cf_base"].sum())
    neg = (-d[d["side"] == "liability"].groupby("bucket")["cf_base"].sum())
    g["assets"] = g["bucket"].map(pos).fillna(0.0)
    g["liabilities"] = g["bucket"].map(neg).fillna(0.0)
    return (g.sort_values("seq")
             [["bucket", "t_mid", "assets", "liabilities", "gap",
               "pv_effect_worst"]].reset_index(drop=True))


def compute_irrbb_from_cashflows(
    bucket_cf: pd.DataFrame, *, asof: str, tier1: float,
    curves: dict[str, Curve], shock_param: pd.DataFrame,
    scenario_def: pd.DataFrame, floor: pd.DataFrame,
    framework_version: str, headline_basis: str,
    allow_proxy: bool = False, delta_nii: pd.DataFrame | None = None,
    outlier_threshold: float | None = IRRBB_OUTLIER_EVE_PCT_TIER1,
    outlier_evidence: str = "원문확인",
) -> IRRBBResult:
    """엔진 진입점 — 현금흐름 원장 + 커브 원장 → IRRBB 원장 2장.

    `headline_basis`에 기본값을 두지 않는다. 계약기준과 행동조정기준은 ΔEVE가
    자릿수로 갈리므로, 어느 쪽이 헤드라인인지를 호출부가 명시하지 않으면 그
    선택이 산출물 어디에도 남지 않는다(§5.14 — 국내가 표준체계를 강제하는지도
    미확인이다).

    `delta_nii`는 `nii.py`가 만든 (scenario, delta_nii) 표다. EVE 현금흐름을
    재활용해 만들지 않는다 — 이자금액 자체가 시나리오 곡선의 함수이기 때문이다.
    """
    if headline_basis not in BASES:
        raise ValueError(f"산출기준은 {BASES} 중 하나여야 한다: {headline_basis!r}")
    status, _superseded = framework_status(shock_param, framework_version)
    shocked, warns = build_shocked_curves(
        curves, scenarios=SCENARIOS, shock_param=shock_param,
        scenario_def=scenario_def, floor=floor,
        framework_version=framework_version, allow_proxy=allow_proxy)
    if not shocked:
        # 전 시나리오의 모수가 비어 있으면 산출물이 아니라 공백이다. 빈 원장을
        # 돌려주면 그 공백이 화면에서 "ΔEVE 0"으로 읽힌다 — 현행 실체화 폴백이
        # 정확히 그렇게 동작했다.
        raise ValueError(
            f"{framework_version}/{sorted(curves)}의 충격 모수가 전부 비어 있다 "
            f"— 산출할 시나리오가 없다. 사유: "
            + " | ".join(w.reason for w in warns[:2]))
    bucket_pv = build_bucket_pv(bucket_cf, asof=asof, curves=curves,
                                shocked=shocked)
    source = {sc: shk.shock_source for (_ccy, sc), shk in shocked.items()}
    result = build_irrbb_result(
        bucket_pv, asof=asof, tier1=tier1,
        framework_version=framework_version, shock_source=source,
        delta_nii=delta_nii, outlier_threshold=outlier_threshold,
        outlier_evidence=outlier_evidence, framework_status=status)
    worst = str(worst_row(result, basis=headline_basis)["scenario"])
    return IRRBBResult(
        result=result, bucket_pv=bucket_pv, tier1=float(tier1),
        headline_basis=headline_basis,
        repricing=_repricing_view(bucket_pv, basis=headline_basis,
                                  worst_scenario=worst),
        warnings=warns)


# ---------------------------------------------------------------- 계승 경로

_LEDGER_CACHE: dict[str, pd.DataFrame] = {}


def _legacy_ledgers() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """계승 경로가 쓰는 커브 원장. 호출마다 다시 만들 이유가 없어 한 번만 만든다."""
    if not _LEDGER_CACHE:
        _LEDGER_CACHE["shock"] = build_rate_shock_param()
        _LEDGER_CACHE["scen"] = build_scenario_def()
        _LEDGER_CACHE["floor"] = build_post_shock_floor()
    return _LEDGER_CACHE["shock"], _LEDGER_CACHE["scen"], _LEDGER_CACHE["floor"]


def shock_curve(scenario: str, t, *, ccy: str = _LEGACY_CCY,
                framework_version: str = _LEGACY_FRAMEWORK) -> np.ndarray:
    """만기 t에서의 Δr(t) — 계승 호출부용.

    계수를 함수 본문에 두지 않는다. 0금리 커브에 `curves.shocked_curve`를 걸고
    그 `shift`(**하한 적용 전** Δr)를 돌려주므로, 충격 bp와 시나리오 계수는
    전부 `alm_rate_shock_param`·`alm_scenario_def`에서 온다. 기본 통화 KRW는
    원장에 자기 값(현행 225/350/225)이 있으므로 프록시 없이 해석된다.

    돌려주는 것이 Δr이라 충격후 하한 0(제12항 다)은 여기 반영되지 않는다.
    하한이 걸린 커브가 필요하면 `curves.shocked_curve`의 결과 커브를 써야 한다.
    """
    tt = np.atleast_1d(np.asarray(t, dtype=float))
    sp, sd, fl = _legacy_ledgers()
    zero = Curve(label="Δr 산출용 0커브", asof="", tenors=tt,
                 zero_rates=np.zeros_like(tt))
    shk, _w = shocked_curve(zero, scenario, ccy=ccy,
                            framework_version=framework_version,
                            shock_param=sp, scenario_def=sd, floor=fl)
    if shk is None:
        raise ValueError(
            f"{ccy}/{framework_version}의 충격 모수가 비어 있다 — Δr을 만들 수 "
            "없다")
    return shk.shift


def _ladder_to_bucket_cf(repricing: pd.DataFrame, *, asof: str | None,
                         ccy: str) -> pd.DataFrame:
    """갭 사다리를 버킷 현금흐름 원장 모양으로 옮긴다.

    현행 산출은 순갭만 할인했으므로 자산·부채로 되돌릴 정보가 없다. 순갭을
    자산 측 현금흐름 하나로 놓아 **산출값을 그대로 재현**하고, 측 분리는
    현금흐름 엔진(`cashflow.py`)을 연결한 경로에서만 나온다.
    """
    rows = []
    for seq, (_, r) in enumerate(repricing.iterrows(), start=1):
        for sc in [BASE_SCENARIO] + SCENARIOS:
            rows.append({
                "asof": asof, "scenario": sc, "basis": BASES[0], "ccy": ccy,
                "side": "asset", "bucket": str(r["bucket"]), "seq": seq,
                "t_mid": float(r["t_mid"]),
                "principal_cf": float(r["gap"]),
                "interest_cf_ex_margin": 0.0, "margin_cf": 0.0,
            })
    return pd.DataFrame(rows)


def compute_irrbb(repricing: pd.DataFrame, tier1: float, *,
                  base_rate: float = _LEGACY_FLAT_BASE_RATE,
                  asof: str | None = None) -> IRRBBResult:
    """갭 사다리 기반 ΔEVE — **계승 경로**.

    `pipeline.py:595`가 아직 이 시그니처로 부른다. 산출은 현행과 같다(평면
    곡선 `base_rate`, 순갭을 버킷 중점에서 할인). 달라지는 것은 결과의 모양
    뿐이다 — 같은 엔진을 타므로 `alm_irrbb_bucket_pv`·`alm_irrbb_result`가
    함께 나오고, `by_scenario`·`worst_eve`가 존재한다.

    **평면 곡선은 산출 가정이지 시장이 아니다.** 그 사실을 경고로 남긴다.
    `asof`를 넘기지 않으면 원장의 기준일이 비므로 실체화 대상이 아니다 —
    배선이 `asof`를 넘기면 그대로 원장이 된다.

    ΔNII도 계승 근사(1년 이내 갭 × Δr × 잔여기간)를 유지한다. 현금흐름 기반
    ΔNII는 계약원장이 필요하므로 `nii.py`에 있고, 갭 사다리로는 만들 수 없다.
    """
    sp, sd, fl = _legacy_ledgers()
    t = repricing["t_mid"].to_numpy(dtype=float)
    curve = Curve(label=f"평면 {base_rate:.4%} (계승)", asof=str(asof or ""),
                  tenors=t, zero_rates=np.full_like(t, float(base_rate)))
    curves = {_LEGACY_CCY: curve}

    shocked, warns = build_shocked_curves(
        curves, scenarios=SCENARIOS, shock_param=sp, scenario_def=sd, floor=fl,
        framework_version=_LEGACY_FRAMEWORK)
    warns.append(ParamWarning(
        "IRRBB", "compute_irrbb", "base_curve",
        f"평면 {base_rate:.4%} 곡선으로 할인했다 — mkt_risk_factor 제로커브가 "
        "연결되지 않은 계승 경로다. 갭 사다리 입력이라 계약/행동 산출기준 "
        "분리도 없다"))

    bucket_pv = build_bucket_pv(
        _ladder_to_bucket_cf(repricing, asof=asof, ccy=_LEGACY_CCY),
        asof=asof, curves=curves, shocked=shocked)

    # ΔNII 계승 근사. 대상 시나리오는 원장이 정한다 — 현행은 `for sc in
    # ("parallel_up","parallel_down")` 튜플이 소스에 박혀 있었다.
    gap = repricing["gap"].to_numpy(dtype=float)
    one_year = t <= 1.0
    nii = pd.DataFrame([
        {"scenario": sc,
         "delta_nii": float(np.sum(shock_curve(sc, t)[one_year]
                                   * gap[one_year] * (1.0 - t[one_year])))}
        for sc in nii_scenarios(sd)])

    status, _superseded = framework_status(sp, _LEGACY_FRAMEWORK)
    result = build_irrbb_result(
        bucket_pv, asof=asof, tier1=tier1,
        framework_version=_LEGACY_FRAMEWORK,
        shock_source={sc: shk.shock_source for (_c, sc), shk in shocked.items()},
        delta_nii=nii, framework_status=status)
    ladder = repricing.copy()
    worst = str(worst_row(result, basis=BASES[0])["scenario"])
    ladder["pv_effect_worst"] = (
        bucket_pv[bucket_pv["scenario"] == worst]
        .set_index("bucket")["delta_pv"].reindex(ladder["bucket"]).to_numpy())
    return IRRBBResult(
        result=result, bucket_pv=bucket_pv, tier1=float(tier1),
        headline_basis=BASES[0], repricing=ladder, warnings=warns,
        base_rate=float(base_rate))
