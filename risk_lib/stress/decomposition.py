"""Factor-by-factor 스트레스 분해.

전체 시나리오의 영향이 어떤 충격 요소(PD / LGD / GDP)에서 주로 발생하는지
분해한다.  BCBS Stress testing principles §6 "sensitivity analysis": 결합
충격을 단일 충격으로 분리해야 자본흡수력의 marginal contribution을 파악할 수
있다.

각 factor를 단독으로 적용한 CET1 비율의 하락폭 = 단독 기여도.  factors의
합이 결합 충격과 다른 경우 잔여항(interaction)으로 표기한다.

자산군(corporate / retail_other / residential_mortgage)별로도 동일한 분해를
수행하여 어느 자산군이 시나리오 stress에 가장 취약한지 확인한다.
"""

from __future__ import annotations

import pandas as pd

from risk_lib.capital.bis import CapitalStack
from risk_lib.provisioning.ecl import compute_ecl
from risk_lib.stress.scenario import Scenario, evaluate_scenario


def _solo_factor_scenario(full: Scenario, factor: str) -> Scenario:
    """결합 시나리오에서 해당 factor만 살린 단독 시나리오."""
    base_kwargs = dict(
        name=f"{full.name}_{factor}_only",
        pd_multiplier=1.0,
        lgd_addon=0.0,
        gdp_shock=0.0,
        pd_gdp_elasticity=full.pd_gdp_elasticity,
    )
    if factor == "pd":
        base_kwargs["pd_multiplier"] = full.pd_multiplier
    elif factor == "lgd":
        base_kwargs["lgd_addon"] = full.lgd_addon
    elif factor == "gdp":
        base_kwargs["gdp_shock"] = full.gdp_shock
    else:
        raise ValueError(f"factor must be pd|lgd|gdp, got {factor}")
    return Scenario(**base_kwargs)


def factor_decomposition(
    irb_portfolio: pd.DataFrame,
    capital: CapitalStack,
    rwa_other: float,
    scenario: Scenario,
    *,
    buffers: dict[str, float] | None = None,
    eir: float = 0.05,
) -> pd.DataFrame:
    """각 factor 단독 적용 → 결합 적용 → 잔여항(interaction).

    Returns: factor, cet1_ratio, delta_cet1_pp, ecl_uplift, rwa_total
    """
    base_ecl = compute_ecl(irb_portfolio, eir=eir)["ecl"].sum()
    base_ev = evaluate_scenario(irb_portfolio, capital, rwa_other,
                                Scenario("base"), base_ecl=base_ecl,
                                buffers=buffers, eir=eir)
    base_ratio = base_ev["cet1_ratio"]

    rows = [{
        "factor": "base",
        "cet1_ratio": base_ratio,
        "delta_cet1_pp": 0.0,
        "ecl_uplift": 0.0,
        "rwa_total": base_ev["rwa_total"],
    }]
    sum_delta = 0.0
    sum_ecl_uplift = 0.0
    for f in ["pd", "lgd", "gdp"]:
        sc = _solo_factor_scenario(scenario, f)
        ev = evaluate_scenario(irb_portfolio, capital, rwa_other, sc,
                               base_ecl=base_ecl, buffers=buffers, eir=eir)
        delta_pp = (ev["cet1_ratio"] - base_ratio) * 100
        rows.append({
            "factor": f,
            "cet1_ratio": ev["cet1_ratio"],
            "delta_cet1_pp": delta_pp,
            "ecl_uplift": ev["incremental_ecl"],
            "rwa_total": ev["rwa_total"],
        })
        sum_delta += delta_pp
        sum_ecl_uplift += ev["incremental_ecl"]

    full_ev = evaluate_scenario(irb_portfolio, capital, rwa_other, scenario,
                                base_ecl=base_ecl, buffers=buffers, eir=eir)
    full_delta = (full_ev["cet1_ratio"] - base_ratio) * 100
    rows.append({
        "factor": "combined",
        "cet1_ratio": full_ev["cet1_ratio"],
        "delta_cet1_pp": full_delta,
        "ecl_uplift": full_ev["incremental_ecl"],
        "rwa_total": full_ev["rwa_total"],
    })
    rows.append({
        "factor": "interaction",
        "cet1_ratio": float("nan"),
        "delta_cet1_pp": full_delta - sum_delta,
        "ecl_uplift": full_ev["incremental_ecl"] - sum_ecl_uplift,
        "rwa_total": float("nan"),
    })
    return pd.DataFrame(rows)


def asset_class_sensitivity(
    irb_portfolio: pd.DataFrame,
    capital: CapitalStack,
    rwa_other: float,
    scenario: Scenario,
    *,
    buffers: dict[str, float] | None = None,
    eir: float = 0.05,
) -> pd.DataFrame:
    """자산군별 시나리오 충격 응답.

    각 asset_class만 시나리오 충격을 적용하고 나머지는 base 상태로 둔 뒤
    포트폴리오 전체의 CET1 영향을 측정한다.  자산군 단독 기여도.
    """
    base_ecl = compute_ecl(irb_portfolio, eir=eir)["ecl"].sum()
    base_ev = evaluate_scenario(irb_portfolio, capital, rwa_other,
                                Scenario("base"), base_ecl=base_ecl,
                                buffers=buffers, eir=eir)
    base_ratio = base_ev["cet1_ratio"]

    rows = []
    for cls in sorted(irb_portfolio["asset_class"].unique()):
        df = irb_portfolio.copy()
        mask = df["asset_class"] == cls
        df.loc[mask, "pd"] = scenario.stress_pd(df.loc[mask, "pd"].values)
        df.loc[mask, "lgd"] = scenario.stress_lgd(df.loc[mask, "lgd"].values)
        # Build a "scenario" that's already-applied at row level by passing
        # the modified frame to evaluate_scenario with an identity scenario.
        ev = evaluate_scenario(df, capital, rwa_other, Scenario("identity"),
                               base_ecl=base_ecl, buffers=buffers, eir=eir)
        rows.append({
            "asset_class": cls,
            "ead": float(df.loc[mask, "ead"].sum()),
            "cet1_ratio": ev["cet1_ratio"],
            "delta_cet1_pp": (ev["cet1_ratio"] - base_ratio) * 100,
            "ecl_uplift": ev["incremental_ecl"],
            "rwa_total": ev["rwa_total"],
        })
    out = pd.DataFrame(rows)
    out["share_of_total_drop_pp"] = (
        out["delta_cet1_pp"] / out["delta_cet1_pp"].sum() if out["delta_cet1_pp"].sum() != 0 else 0.0
    )
    return out
