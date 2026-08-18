"""Multi-target 역스트레스테스트.

기존 reverse_stress는 CET1 단일 metric에 대해 임계 심도를 산출했다.  본
모듈은 4개의 핵심 임계 — CET1 4.5% / Tier1 6.0% / LCR 100% / NSFR 100% — 에
대해 각각의 critical severity를 산출하고, 가장 먼저 도달하는 임계점
(binding constraint)을 식별한다.

LCR/NSFR은 시장충격 시 HQLA 가치 하락(L2A/L2B haircut 가산)과 funding
run-off 가속을 통해 stress severity에 반응한다 — 단순 비례 모델.

BCBS Stress testing principles §7: "reverse stress test should identify the
binding constraint and the macro trajectory that reaches it first."
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from risk_lib.capital.bis import CapitalStack
from risk_lib.alm.lcr import LCRResult
from risk_lib.alm.nsfr import NSFRResult
from risk_lib.references import BIS_MIN_CET1, BIS_MIN_TIER1, LCR_MIN, NSFR_MIN
from risk_lib.stress.reverse import reverse_stress, ReverseStressResult
from risk_lib.stress.scenario import StressAxis


# ---------------------------------------------------------------- liquidity stress

def stress_lcr(base_lcr: LCRResult, severity: float,
               *, l2a_haircut_per_unit: float = 0.05,
               l2b_haircut_per_unit: float = 0.10,
               runoff_acceleration_per_unit: float = 0.15) -> float:
    """severity 단위만큼 HQLA haircut 증가 + 비예금 funding runoff 가속.

    severity = 0 → base LCR 재현.  selectively scales the gross outflow and
    HQLA value to model market stress.
    """
    s = max(severity, 0.0)
    hd = base_lcr.hqla_detail
    # Map: increase post-haircut down-shift for L2A and L2B.
    l1 = float(hd[hd["component"] == "Level 1"]["included"].iloc[0])
    l2a = float(hd[hd["component"] == "Level 2A"]["included"].iloc[0])
    l2b = float(hd[hd["component"] == "Level 2B"]["included"].iloc[0])
    l2a_stressed = l2a * max(0.0, 1.0 - l2a_haircut_per_unit * s)
    l2b_stressed = l2b * max(0.0, 1.0 - l2b_haircut_per_unit * s)
    hqla_stressed = l1 + l2a_stressed + l2b_stressed

    # Funding runoff: corporate non-op + wholesale FI most reactive.
    out = base_lcr.outflows.copy()
    accel = 1.0 + runoff_acceleration_per_unit * s
    out["outflow"] = out.apply(
        lambda r: r["outflow"] * (
            accel if r["category"] in
            {"corporate_non_operational", "wholesale_fi_unsecured",
             "committed_facilities"}
            else 1.0
        ), axis=1,
    )
    gross = float(out["outflow"].sum())
    inflow_capped = min(base_lcr.inflow_capped, 0.75 * gross)
    net_out = gross - inflow_capped
    return hqla_stressed / net_out if net_out > 0 else float("inf")


def stress_nsfr(base_nsfr: NSFRResult, severity: float,
                *, asf_decay_per_unit: float = 0.03,
                rsf_growth_per_unit: float = 0.04) -> float:
    """ASF 감소 + RSF 증가로 NSFR 가속 악화."""
    s = max(severity, 0.0)
    asf = base_nsfr.asf_total * max(0.0, 1.0 - asf_decay_per_unit * s)
    rsf = base_nsfr.rsf_total * (1.0 + rsf_growth_per_unit * s)
    return asf / rsf if rsf > 0 else float("inf")


def _bisect_liquidity(base_ratio: float, target: float, evaluate,
                      *, max_severity: float = 10.0, tol: float = 1e-3,
                      max_iter: int = 60) -> tuple[float, float, bool, bool]:
    """target보다 base가 이미 낮으면 already_breached; max에서도 통과면 resilient."""
    if base_ratio <= target:
        return 0.0, base_ratio, False, True
    r_max = evaluate(max_severity)
    if r_max > target:
        return max_severity, r_max, True, False
    lo, hi = 0.0, max_severity
    converged = False
    for _ in range(max_iter):
        mid = (lo + hi) / 2
        if evaluate(mid) > target:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            converged = True
            break
    s = (lo + hi) / 2
    return s, evaluate(s), False, False


# ---------------------------------------------------------------- top-level


@dataclass
class MultiReverseResult:
    """4-target 역스트레스 종합.

    binding_constraint: 가장 먼저 도달하는 임계 (가장 작은 critical_severity).
    """
    targets: pd.DataFrame                      # metric, target, base, critical_severity, ...
    binding_constraint: str
    binding_severity: float
    critical_pathway: dict                     # binding constraint 도달 시 거시 충격
    cet1_result: ReverseStressResult
    tier1_result: ReverseStressResult


def run_multi_reverse(
    irb_portfolio: pd.DataFrame,
    capital: CapitalStack,
    rwa_other: float,
    base_lcr: LCRResult,
    base_nsfr: NSFRResult,
    *,
    axis: StressAxis | None = None,
    buffers: dict[str, float] | None = None,
    eir: float = 0.05,
    max_severity: float = 10.0,
) -> MultiReverseResult:
    """CET1 / Tier1 / LCR / NSFR 4-target reverse stress + binding constraint."""
    if axis is None:
        axis = StressAxis()

    cet1_res = reverse_stress(
        irb_portfolio, capital, rwa_other,
        metric="cet1", target_ratio=BIS_MIN_CET1, axis=axis,
        buffers=buffers, eir=eir, max_severity=max_severity,
    )
    tier1_res = reverse_stress(
        irb_portfolio, capital, rwa_other,
        metric="tier1", target_ratio=BIS_MIN_TIER1, axis=axis,
        buffers=buffers, eir=eir, max_severity=max_severity,
    )

    lcr_s, lcr_at, lcr_resilient, lcr_breached = _bisect_liquidity(
        base_lcr.lcr, LCR_MIN,
        lambda s: stress_lcr(base_lcr, s),
        max_severity=max_severity,
    )
    nsfr_s, nsfr_at, nsfr_resilient, nsfr_breached = _bisect_liquidity(
        base_nsfr.nsfr, NSFR_MIN,
        lambda s: stress_nsfr(base_nsfr, s),
        max_severity=max_severity,
    )

    rows = [
        {"metric": "CET1 (4.5%)", "target": BIS_MIN_CET1,
         "base": cet1_res.base_ratio,
         "critical_severity": cet1_res.critical_severity,
         "ratio_at_break": cet1_res.ratio_at_break,
         "resilient": cet1_res.resilient,
         "already_breached": cet1_res.already_breached,
         "implied_gdp_shock": cet1_res.implied_gdp_shock,
         "implied_lgd_addon": cet1_res.implied_lgd_addon},
        {"metric": "Tier1 (6.0%)", "target": BIS_MIN_TIER1,
         "base": tier1_res.base_ratio,
         "critical_severity": tier1_res.critical_severity,
         "ratio_at_break": tier1_res.ratio_at_break,
         "resilient": tier1_res.resilient,
         "already_breached": tier1_res.already_breached,
         "implied_gdp_shock": tier1_res.implied_gdp_shock,
         "implied_lgd_addon": tier1_res.implied_lgd_addon},
        {"metric": "LCR (100%)", "target": LCR_MIN,
         "base": base_lcr.lcr,
         "critical_severity": lcr_s,
         "ratio_at_break": lcr_at,
         "resilient": lcr_resilient,
         "already_breached": lcr_breached,
         "implied_gdp_shock": -axis.gdp_per_unit * lcr_s,
         "implied_lgd_addon": axis.lgd_addon_per_unit * lcr_s},
        {"metric": "NSFR (100%)", "target": NSFR_MIN,
         "base": base_nsfr.nsfr,
         "critical_severity": nsfr_s,
         "ratio_at_break": nsfr_at,
         "resilient": nsfr_resilient,
         "already_breached": nsfr_breached,
         "implied_gdp_shock": -axis.gdp_per_unit * nsfr_s,
         "implied_lgd_addon": axis.lgd_addon_per_unit * nsfr_s},
    ]
    df = pd.DataFrame(rows)

    # binding constraint = 가장 작은 (resilient/already_breached 제외) severity
    bindable = df[~df["resilient"] & ~df["already_breached"]]
    if len(bindable) == 0:
        binding = df.iloc[df["critical_severity"].idxmin()]["metric"]
        binding_sev = float(df["critical_severity"].min())
    else:
        idx = bindable["critical_severity"].idxmin()
        binding = bindable.loc[idx, "metric"]
        binding_sev = float(bindable.loc[idx, "critical_severity"])

    critical_pathway = {
        "binding_constraint": binding,
        "binding_severity": binding_sev,
        "implied_gdp_shock": -axis.gdp_per_unit * binding_sev,
        "implied_lgd_addon": axis.lgd_addon_per_unit * binding_sev,
        "narrative": _pathway_narrative(binding, binding_sev,
                                        axis.gdp_per_unit, axis.lgd_addon_per_unit),
    }
    return MultiReverseResult(
        targets=df, binding_constraint=binding, binding_severity=binding_sev,
        critical_pathway=critical_pathway,
        cet1_result=cet1_res, tier1_result=tier1_res,
    )


def _pathway_narrative(metric: str, s: float,
                       gdp_per_unit: float, lgd_per_unit: float) -> str:
    """binding constraint별 거시 narrative."""
    gdp_pct = -s * gdp_per_unit * 100
    lgd_pp = s * lgd_per_unit * 100
    if "LCR" in metric:
        return (f"단기 유동성 압력 — HQLA 가치 하락(시장 스트레스) + "
                f"비예금 funding {s*15:.0f}% runoff 가속이 LCR 100% 임계 견인. "
                f"동반되는 거시: GDP {gdp_pct:+.1f}%, LGD +{lgd_pp:.1f}%p")
    if "NSFR" in metric:
        return (f"중장기 funding 안정성 악화 — 도매자금 만기 단축 + "
                f"NPL 증가에 따른 RSF 가산. 거시: GDP {gdp_pct:+.1f}%")
    if "Tier1" in metric:
        return (f"AT1 trigger 직전 시나리오 — 신용 손실로 CET1 잠식, "
                f"AT1 쿠폰 중단 압력. GDP {gdp_pct:+.1f}%, LGD +{lgd_pp:.1f}%p")
    return (f"신용 손실로 CET1 4.5% Pillar-1 미달 직전 — "
            f"GDP {gdp_pct:+.1f}%, LGD +{lgd_pp:.1f}%p. "
            f"감독당국 PCA 발동 임계.")
