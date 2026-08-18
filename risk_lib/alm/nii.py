"""ΔNII — 12개월 전방 순이자이익 민감도 (설계 §3).

**EVE 현금흐름을 재활용하지 않는다.** ΔEVE는 확정된 현금흐름을 시나리오 곡선
으로 다시 할인하는 문제이지만, ΔNII는 **이자금액 자체가 시나리오 곡선의
함수**다. 변동금리 계약은 차기 리프라이싱일에 새 지표금리로 갈아타고, 12개월
안에 만기가 오는 고정금리 계약은 그 시점의 금리로 재투자·재조달된다. 할인
문제와 발생 문제를 같은 현금흐름으로 풀면 리프라이싱이 소득에 미치는 효과가
사라진다.

**마진을 포함한다.** ΔEVE는 상업마진을 제외하지만(BCBS d368 §132(3)) ΔNII는
포함한다(EBA GL 2022-14). 두 지표가 반대로 취급한다는 사실이 원장에서 보여야
하므로 `margin_included` 금액을 컬럼으로 남긴다 — 마진은 리프라이싱에도
그대로 따라가므로 Δ에서는 상쇄되지만 **수준(nii_base)에는 들어가 있고**,
그 금액이 얼마인지가 원장에 없으면 포함 여부를 확인할 방법이 없다.

**평행충격 2개만.** 대상 시나리오는 `alm_scenario_def.applies_to_nii`가 정한다.
현행은 `irrbb.py:105`에 `for sc in ("parallel_up","parallel_down")`이 튜플
리터럴로 박혀 있었다 — 규칙을 데이터로 옮긴다.

**불변 대차대조표.** 상환·만기 도래분은 같은 조건(같은 마진·같은 잔액)으로
재투자된다고 본다. 따라서 잔액은 12개월 내내 `notional`이고, 시나리오가 바꾸는
것은 **리프라이싱 이후 구간의 금리**뿐이다:

    ΔNII = Σ_계약  부호 · 잔액 · β · Δr(t_r) · (H − t_r),   t_r ≤ H

t_r은 계약의 차기 리프라이싱 시점(변동금리) 또는 만기(고정금리, H 이내),
β는 지표금리 전가율이다. 만기부 계약의 β는 1이다(리프라이싱의 정의).
**비만기예금의 β는 은행 고유 추정치이며 `alm_nmd_param.pass_through_beta`가
비어 있다.**

**모수가 비어 다리가 결손이면 ΔNII를 싣지 않는다.** 건너뛰기는 중립이 아니다 —
관리금리 부채가 통째로 빠지면 남는 것은 자산 위주의 다리이고, 그것은 위 docstring
이 경계한 편향("부채가 따라 오르지 않으면 금리상승이 항상 이익이 된다")을 베타를
지어냈을 때와 **같은 방향으로** 만든다. 실제로 이 상태에서 부채 명목의 12.5%만
산출에 들어가고 ΔNII가 양수로 나왔다. `build_survival_path`(유출률 NULL이면
시나리오 미산출)·`build_nsfr_item`(계수 NULL이면 항목 미적재)과 같은 규약을
쓴다: **비어 있음은 원장의 공백으로 보여야 하며, 부분 산출로 채워지면 안 된다.**
결손 명세는 `ParamWarning`으로 나가고 자체검증이 WARN으로 승격한다.

알려진 한계
  · 12개월 시계·불변 대차대조표가 국내 세칙의 요구인지 미확인(설계 §5.15).
    시계를 인자로 받아 원장에 적는 이유가 이것이다 — 기본값으로 숨기면 어떤
    시계로 산출했는지가 남지 않는다.
  · 평행충격에서는 Δr이 만기에 무관하므로 첫 리프라이싱 이후의 재리프라이싱을
    따로 세지 않아도 결과가 같다. 비평행 시나리오까지 확장하려면 회차별
    리프라이싱 경로가 필요하다 — `applies_to_nii`가 평행 2개뿐이라 지금은
    닿지 않는다.
  · 자기자본은 제외한다(이자를 낳지 않으며 ΔEVE에서도 제외된다).
  · TableSpec은 아직 `datamodel.catalog.ALL_TABLES`에 등재하지 않았다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from risk_lib.alm.behaviour import ParamWarning
from risk_lib.alm.curves import Curve, ShockedCurve, nii_scenarios
from risk_lib.alm.irrbb import SIDE_SIGN
from risk_lib.alm.params import EVIDENCE_STATUS, IRRBB_SCENARIOS
from risk_lib.datamodel.spec import ColumnSpec as C, TableSpec

__all__ = [
    "MARGIN_INCLUDED", "BALANCE_SHEET_ASSUMPTION", "NII_RESULT",
    "NIIResult", "compute_delta_nii",
]

MARGIN_INCLUDED = "포함"
BALANCE_SHEET_ASSUMPTION = "불변(상환·만기 도래분을 동일조건 재투자)"

_NII_CITATION = (
    "EBA GL 2022-14 — ΔNII는 상업마진 포함 / BCBS d368 §132 · SRP31.34 — "
    "평행충격 2개, 불변 대차대조표. 국내 세칙의 시계·재투자 가정은 미대조"
    "(설계 §5.15·§5.16)")


NII_RESULT = TableSpec(
    name="alm_nii_result", korean="ΔNII 12개월 전방", product="PRD-ALM",
    grain="기준일 × 시나리오 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("scenario", "string", "시나리오", nullable=False,
          allowed=IRRBB_SCENARIOS,
          citation="alm_scenario_def.applies_to_nii = True인 시나리오만"),
        C("horizon_years", "float", "산출 시계", nullable=False, unit="years",
          min_value=0.0,
          note="인자로 받아 원장에 적는다 — 기본값으로 숨기면 어떤 시계로 "
               "산출했는지가 남지 않는다"),
        C("nii_base", "float", "기준 순이자이익", nullable=False, unit="KRW",
          note="상업마진 포함"),
        C("nii_shocked", "float", "충격후 순이자이익", nullable=False,
          unit="KRW"),
        C("delta_nii", "float", "ΔNII", nullable=False, unit="KRW",
          note="부호 있음 — 감소가 음수"),
        C("nii_base_ex_margin", "float", "마진 제외 기준 순이자이익",
          nullable=False, unit="KRW",
          note="ΔEVE가 쓰는 현금흐름 기준. 두 지표의 마진 취급 차이를 금액으로 "
               "대조하기 위한 컬럼이다"),
        C("margin_included", "float", "포함된 상업마진", nullable=False,
          unit="KRW", citation="nii_base − nii_base_ex_margin"),
        C("n_repricing_contracts", "int", "시계 내 리프라이싱 계약 수",
          nullable=False, min_value=0),
        C("n_excluded_contracts", "int", "모수 결손으로 제외된 계약 수",
          nullable=False, min_value=0,
          note="전가율(pass_through_beta)이 비어 산출에서 빠진 계약"),
        C("excluded_notional", "float", "제외 명목", nullable=False, unit="KRW",
          min_value=0.0),
        C("excluded_notional_ratio", "float", "제외 명목 비율", nullable=False,
          unit="ratio", min_value=0.0, max_value=1.0,
          note="제외 명목 ÷ 자기자본 제외 총명목. 0보다 크면 ΔNII는 부분 "
               "산출이며 남은 다리 쪽으로 편향된다 — 관리금리 부채가 빠지면 "
               "금리상승이 항상 이익으로 나온다"),
        C("balance_sheet_assumption", "string", "대차대조표 가정",
          nullable=False, allowed=(BALANCE_SHEET_ASSUMPTION,)),
        C("margin_treatment", "string", "마진 처리", nullable=False,
          allowed=(MARGIN_INCLUDED,)),
        C("citation", "text", "근거", nullable=True),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("asof", "scenario"),
    note="`catalog.ALM_METRICS`의 IRRBB_NII 행은 선언만 되어 있고 어디에서도 "
         "생성되지 않았다 — 이 원장이 그 자리를 채운다.",
)


@dataclass
class NIIResult:
    result: pd.DataFrame
    warnings: list[ParamWarning] = field(default_factory=list)

    @property
    def delta_nii(self) -> pd.DataFrame:
        """`alm_irrbb_result`에 붙일 (scenario, delta_nii) 표."""
        return self.result[["scenario", "delta_nii"]].reset_index(drop=True)

    def warning_frame(self) -> pd.DataFrame:
        return pd.DataFrame([{"model": w.model, "scope": w.scope,
                              "param": w.param, "reason": w.reason}
                             for w in self.warnings],
                            columns=["model", "scope", "param", "reason"])


# ---------------------------------------------------------------- 리프라이싱

def _years(asof_d: date, iso: object) -> float:
    """asof → 날짜까지의 연수. 산출 전반과 같은 365.25일 환산."""
    return max((date.fromisoformat(str(iso)) - asof_d).days / 365.25, 0.0)


def _repricing_time(row: pd.Series, terms: pd.Series, asof_d: date,
                    horizon: float) -> float | None:
    """시계 안에서 금리가 갈아타는 시점. 갈아타지 않으면 None.

    · 변동금리 — 차기 리프라이싱일. 계약원장에 그 날짜가 없으면 시점을 알 수
      없으므로 조정하지 않는다(0으로 놓으면 즉시 전가로 과대계상된다).
    · 관리금리(비만기) — 즉시 조정 대상이나 전가율은 호출부가 원장에서 찾는다.
    · 고정금리 — 시계 안에 만기가 오면 그때 재투자·재조달된다. 시계 밖이면
      12개월 순이자이익은 시나리오와 무관하다.
    """
    rate_type = str(terms["rate_type"])
    if rate_type == "floating":
        reset = row.get("next_reset_date")
        if reset is None or pd.isna(reset):
            return None
        t = _years(asof_d, reset)
        return t if t <= horizon else None
    if rate_type == "administered":
        return 0.0
    mat = row.get("maturity_date")
    if mat is None or pd.isna(mat):
        return None
    t = _years(asof_d, mat)
    return t if t <= horizon else None


def _pass_through(row: pd.Series, terms: pd.Series, nmd_param: pd.DataFrame | None,
                  ) -> tuple[float | None, ParamWarning | None]:
    """지표금리 전가율 β. 만기부 계약은 1(리프라이싱의 정의), 비만기는 원장값."""
    if str(terms["rate_type"]) != "administered":
        return 1.0, None
    cat = row.get("counterparty_type")
    scope = f"{row['contract_id']}/{cat}"
    if nmd_param is None or cat is None or pd.isna(cat):
        return None, ParamWarning(
            "NII", scope, "pass_through_beta",
            "관리금리 계약의 예금 범주를 찾지 못했다 — ΔNII 조정 미적용")
    hit = nmd_param[nmd_param["nmd_category"] == cat]
    if hit.empty or pd.isna(hit.iloc[0]["pass_through_beta"]):
        return None, ParamWarning(
            "NII", scope, "pass_through_beta",
            "예금베타가 비어 있다(은행 고유 추정 필요 — 설계 §5.21) — ΔNII "
            "조정 미적용. 베타를 지어내면 금리상승이 항상 이익으로 나온다")
    return float(hit.iloc[0]["pass_through_beta"]), None


# ---------------------------------------------------------------- 엔진

def compute_delta_nii(
    contracts: pd.DataFrame, product_terms: pd.DataFrame, *, asof: str,
    horizon_years: float, curves: dict[str, Curve],
    shocked: dict[tuple[str, str], ShockedCurve], scenario_def: pd.DataFrame,
    nmd_param: pd.DataFrame | None = None,
) -> NIIResult:
    """`alm_nii_result` — 계약원장 + 충격곡선 → 시나리오별 ΔNII.

    입력은 계약원장이다. 갭 사다리로는 만들 수 없다 — 리프라이싱 *시점*과
    마진이 계약 단위로 필요하기 때문이다.
    """
    asof_d = date.fromisoformat(asof)
    H = float(horizon_years)
    scenarios = nii_scenarios(scenario_def)
    terms_by_code = product_terms.set_index("product_code")
    warns: list[ParamWarning] = []

    d = contracts[contracts["asof"] == asof] if "asof" in contracts.columns \
        else contracts
    d = d[~d["is_own_equity"].astype(bool)]

    # 계약별로 한 번만 정리한다 — 시나리오마다 다시 파싱하면 같은 원장을 여러 번
    # 읽으면서 시나리오 사이의 차이가 파싱 차이일 여지가 생긴다.
    # (통화, 부호, 잔액, 전가율, 리프라이싱 시점, 잔여기간)
    legs: list[tuple[str, float, float, float, float, float]] = []
    nii_base = nii_base_ex_margin = 0.0
    # 모수가 없어 빠진 다리. 시계 밖이라 빠진 계약(t_r is None)과 구분한다 —
    # 앞은 원장의 공백이고 뒤는 모형의 사실이다.
    dropped_n, dropped_notional = 0, 0.0
    for _, row in d.iterrows():
        code = str(row["product_code"])
        if code not in terms_by_code.index:
            raise KeyError(
                f"{row['contract_id']}: 상품 {code!r}이 alm_product_terms에 없다 — "
                "관행을 모르는 계약의 이자는 계산할 수 없다")
        terms = terms_by_code.loc[code]
        side = str(row["side"])
        if side not in SIDE_SIGN:
            raise ValueError(f"{row['contract_id']}: 부호 규약이 없는 측 {side!r}")
        sign = SIDE_SIGN[side]
        bal, rate = float(row["notional"]), float(row["coupon_rate"])
        margin = float(row["margin_bp"]) / 1e4
        nii_base += sign * bal * rate * H
        nii_base_ex_margin += sign * bal * (rate - margin) * H

        t_r = _repricing_time(row, terms, asof_d, H)
        if t_r is None:
            continue
        beta, w = _pass_through(row, terms, nmd_param)
        if w is not None:
            warns.append(w)
        if beta is None:
            dropped_n += 1
            dropped_notional += bal
            continue
        legs.append((str(row["ccy"]), sign, bal, beta, t_r, H - t_r))

    # 결손 다리는 금액으로 원장에 남는다. 남은 다리만으로 계산한 ΔNII는 "덜
    # 정확한 값"이 아니라 **방향이 편향된 값**이다 — 관리금리 부채가 통째로
    # 빠지면 금리상승이 항상 이익으로 나오며, 그것은 베타를 지어냈을 때와 같은
    # 편향이다. 그래서 제외 명목·제외 비율을 컬럼으로 두고 근거 상태를
    # '미확인'으로 내린다. 이 두 컬럼이 없으면 산출이 나왔다는 사실만 보이고
    # 무엇이 빠졌는지는 보이지 않는다.
    total_notional = float(d["notional"].abs().sum())
    excluded_ratio = (dropped_notional / total_notional
                      if total_notional > 0 else 0.0)
    if dropped_n:
        warns.append(ParamWarning(
            "NII", asof, "pass_through_beta",
            f"전가율이 비어 산출 다리가 결손이다 — 계약 {dropped_n:,}건 · "
            f"명목 {dropped_notional:,.0f}원({excluded_ratio:.1%}) 제외. "
            "ΔNII는 부분 산출이며 근거 상태를 '미확인'으로 내린다"))

    rows = []
    for sc in scenarios:
        delta, missing = 0.0, False
        for ccy, sign, bal, beta, t_r, remaining in legs:
            key = (ccy, sc)
            if key not in shocked:
                warns.append(ParamWarning(
                    "NII", f"{ccy}/{sc}", "shocked_curve",
                    "충격곡선이 없다(모수 미확정) — 이 시나리오는 산출하지 않는다"))
                missing = True
                break
            dr = float(shocked[key].curve.rate(t_r)) - float(curves[ccy].rate(t_r))
            delta += sign * bal * beta * dr * remaining
        if missing:
            continue
        rows.append({
            "asof": asof, "scenario": sc, "horizon_years": H,
            "nii_base": nii_base, "nii_shocked": nii_base + delta,
            "delta_nii": delta, "nii_base_ex_margin": nii_base_ex_margin,
            "margin_included": nii_base - nii_base_ex_margin,
            "n_repricing_contracts": len(legs),
            "n_excluded_contracts": dropped_n,
            "excluded_notional": dropped_notional,
            "excluded_notional_ratio": excluded_ratio,
            "balance_sheet_assumption": BALANCE_SHEET_ASSUMPTION,
            "margin_treatment": MARGIN_INCLUDED,
            "citation": _NII_CITATION,
            "evidence_status": "미확인" if dropped_n else "2차자료",
        })
    result = pd.DataFrame(rows, columns=list(NII_RESULT.column_names))
    if not result.empty:
        result = result.astype({"n_repricing_contracts": "int64",
                                "n_excluded_contracts": "int64"})
    return NIIResult(result=result, warnings=list(dict.fromkeys(warns)))
