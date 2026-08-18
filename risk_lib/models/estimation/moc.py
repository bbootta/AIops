"""추정오차에 대한 보수적 조정, MoC ([별표 3] 181.).

> 은행은 예상치 못한 오류에 대비하여 PD, LGD, EAD의 추정치를 보수적으로
> 조정하여야 한다. 특히 모형 및 데이터 품질이 낮고 오류의 범위가 커질 가능성이
> 있는 경우 보수적 조정폭을 확대해야 한다.

조문은 조정을 **요구**하되 크기를 주지 않는다. 그래서 세 원천을 나누고 각
원천의 크기 모수를 원장에 두며, 모수가 승인 전이면 그 원천의 조정을 하지 않고
그 사실을 원장에 남긴다. 크기를 지어내 채우면 그 숫자가 규정처럼 보인다.

세 원천

  데이터품질  자료 결함의 크기 모수 × 원시추정치. 크기는 내부기준
  모형품질    통계적 추정오차. 연도별 추정치의 표본평균 신뢰상한 − 점추정치.
              **표본이 작은 등급일수록 자동으로 커진다.** 신뢰수준은 내부기준
  대표성      180. 대표성 판정이 경고·불합격일 때만 붙는다. 크기는 내부기준

합산 방식(단순합·제곱합)도 조문이 정하지 않으므로 원장 모수다. 방식이 승인
전이면 합산하지 않고 ``moc_status='기준미승인'``으로 둔다. 세 원천을 임의로
더해 한 숫자로 만들면 어느 결함 때문에 얼마가 붙었는지 사라진다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.stats import t as _student_t

from risk_lib.models.estimation.common import MOC_DRIVERS
from risk_lib.models.estimation.params import param_value, param_text

__all__ = ["MocResult", "compute_moc", "moc_component_rows"]

_AGGREGATIONS: tuple[str, ...] = ("단순합", "제곱합")


@dataclass
class MocResult:
    """MoC 산출 결과. 원천별 조정폭과 상태를 함께 들고 있다."""
    total: float | None
    components: dict[str, float | None]
    available: dict[str, bool]
    formulas: dict[str, str]
    rationales: dict[str, str]
    param_codes: dict[str, str | None]
    aggregation: str | None
    status: str
    rationale: str
    unresolved: list[str] = field(default_factory=list)


def _statistical_upper(series: np.ndarray, level: float) -> float | None:
    """연도별 추정치 표본평균의 단측 신뢰상한.

    연도가 2개 미만이면 표본분산이 정의되지 않으므로 상한을 내지 않는다.
    이 경우 통계적 MoC는 산출하지 않고 상태에 남긴다. 0으로 두면 표본이 없어
    불확실한 등급의 MoC가 가장 작아지는 뒤집힌 결과가 된다.
    """
    x = np.asarray(series, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 2:
        return None
    se = float(np.std(x, ddof=1) / np.sqrt(n))
    if se == 0.0:
        return float(x.mean())
    return float(x.mean() + _student_t.ppf(level, df=n - 1) * se)


def compute_moc(*, param: pd.DataFrame, point_estimate: float,
                yearly_estimates: np.ndarray | list[float] | None = None,
                representativeness_flagged: bool | None = None) -> MocResult:
    """세 원천의 MoC를 산출한다.

    ``yearly_estimates``는 연도별 추정치(PD면 연도별 부도율, LGD·CCF면 연도별
    평균)다. 이것이 없으면 모형품질 MoC를 내지 않는다.

    ``representativeness_flagged``가 None이면 대표성 판정이 아직 없다는 뜻이며
    대표성 MoC를 붙이지 않고 그 사실을 남긴다. False로 두면 '대표성에 문제가
    없음을 확인했다'가 되어 판정하지 않은 것과 구분되지 않는다.
    """
    comp: dict[str, float | None] = {}
    avail: dict[str, bool] = {}
    formulas: dict[str, str] = {}
    rationales: dict[str, str] = {}
    codes: dict[str, str | None] = {}
    unresolved: list[str] = []

    # ---- 데이터품질 ----
    dq = param_value(param, "moc_data_quality_addon")
    codes["데이터품질"] = "moc_data_quality_addon"
    formulas["데이터품질"] = "MoC = moc_data_quality_addon × 원시추정치"
    if dq is None:
        comp["데이터품질"], avail["데이터품질"] = None, False
        rationales["데이터품질"] = (
            "181.은 데이터 품질이 낮으면 조정폭을 확대하라고만 정한다. 크기가 "
            "승인 전이므로 이 원천의 조정을 적용하지 않았다")
        unresolved.append("moc_data_quality_addon")
    else:
        comp["데이터품질"], avail["데이터품질"] = dq * point_estimate, True
        rationales["데이터품질"] = (
            f"승인된 내부기준 가산율 {dq:.4g}를 원시추정치에 곱했다 (181.)")

    # ---- 모형품질(통계적 추정오차) ----
    lvl = param_value(param, "moc_confidence_level")
    codes["모형품질"] = "moc_confidence_level"
    formulas["모형품질"] = (
        "MoC = max(0, 연도별 추정치 표본평균의 단측 신뢰상한 − 점추정치). "
        "t분포, 자유도 = 연수 − 1")
    upper = None
    if lvl is not None and yearly_estimates is not None:
        upper = _statistical_upper(np.asarray(yearly_estimates, dtype=float), lvl)
    if lvl is None:
        comp["모형품질"], avail["모형품질"] = None, False
        rationales["모형품질"] = (
            "신뢰수준이 승인 전이라 추정오차 구간을 내지 않았다 (181.)")
        unresolved.append("moc_confidence_level")
    elif upper is None:
        comp["모형품질"], avail["모형품질"] = None, False
        rationales["모형품질"] = (
            "연도별 추정치가 2개 미만이라 표본분산이 정의되지 않는다. "
            "구간을 내지 않고 0으로도 두지 않는다")
        unresolved.append("yearly_estimates<2")
    else:
        comp["모형품질"] = float(max(0.0, upper - point_estimate))
        avail["모형품질"] = True
        rationales["모형품질"] = (
            f"신뢰수준 {lvl:.4g}의 단측 상한 {upper:.6g}에서 점추정치를 뺐다. "
            "표본이 작은 등급일수록 구간이 넓어 조정폭이 커진다 (181.)")

    # ---- 대표성 ----
    rep = param_value(param, "moc_representativeness_addon")
    codes["대표성"] = "moc_representativeness_addon"
    formulas["대표성"] = (
        "MoC = moc_representativeness_addon × 원시추정치, "
        "대표성 판정이 경고·불합격일 때만 적용")
    if representativeness_flagged is None:
        comp["대표성"], avail["대표성"] = None, False
        rationales["대표성"] = (
            "180. 대표성 판정 결과가 없다. 판정하지 않은 것을 '문제 없음'으로 "
            "두지 않는다")
        unresolved.append("representativeness_judgment")
    elif rep is None:
        comp["대표성"], avail["대표성"] = None, False
        rationales["대표성"] = "대표성 MoC 가산율이 승인 전이다 (180.·181.)"
        unresolved.append("moc_representativeness_addon")
    else:
        comp["대표성"] = float(rep * point_estimate
                               if representativeness_flagged else 0.0)
        avail["대표성"] = True
        rationales["대표성"] = (
            f"대표성 판정 {'경고·불합격' if representativeness_flagged else '적합'}. "
            f"가산율 {rep:.4g} 적용" if representativeness_flagged
            else "대표성 판정이 적합이므로 가산하지 않았다 (180.)")

    # ---- 합산 ----
    agg = param_text(param, "moc_aggregation")
    if agg is not None and agg not in _AGGREGATIONS:
        raise ValueError(f"moc_aggregation은 {_AGGREGATIONS} 중 하나여야 한다: {agg}")
    have = [v for v in comp.values() if v is not None]
    if agg is None:
        total, status = None, "기준미승인"
        unresolved.append("moc_aggregation")
        rationale = ("합산 방식이 승인 전이라 세 원천을 합치지 않았다. "
                     "원천별 조정폭은 crm_moc_component에 남아 있다")
    elif not have:
        total, status = None, "기준미승인"
        rationale = "세 원천 모두 크기 모수가 승인 전이다. MoC를 적용하지 않았다"
    else:
        total = (float(sum(have)) if agg == "단순합"
                 else float(np.sqrt(sum(v ** 2 for v in have))))
        status = "산출완료" if all(avail.values()) else "부분산출"
        missing = [k for k, ok in avail.items() if not ok]
        rationale = (f"{agg} 합산. 적용 원천 "
                     f"{[k for k, ok in avail.items() if ok]}")
        if missing:
            rationale += f". 미적용 원천 {missing} (크기 모수 승인 전)"
    return MocResult(total=total, components=comp, available=avail,
                     formulas=formulas, rationales=rationales,
                     param_codes=codes, aggregation=agg, status=status,
                     rationale=rationale, unresolved=unresolved)


def moc_component_rows(result: MocResult, *, asof: str, parameter: str,
                       segment: str, grade: str,
                       point_estimate: float) -> list[dict]:
    """MoC 결과를 ``crm_moc_component`` 행으로 편다."""
    return [{
        "asof": asof, "parameter": parameter, "segment": segment,
        "grade": grade, "moc_driver": driver,
        "point_estimate": float(point_estimate),
        "moc_amount": result.components[driver],
        "moc_formula": result.formulas[driver],
        "moc_rationale": result.rationales[driver],
        "param_code": result.param_codes[driver],
        "param_available": bool(result.available[driver]),
    } for driver in MOC_DRIVERS]
