"""역스트레스테스트 (reverse stress testing).

Forward stress asks "given this scenario, what happens to capital?".  Reverse
stress inverts the question: "how severe a downturn drives a chosen capital
metric down to its breaking point?"  (BCBS 정상화·금감원 스트레스테스트 가이드라인.)

A scalar `severity` s ≥ 0 scales a stress axis into a `Scenario`:

    GDP shock   = -s · gdp_per_unit      (drives PD via the satellite elasticity)
    LGD add-on  =  s · lgd_addon_per_unit

The chosen BIS ratio is monotonically decreasing in s, so we bisection-solve for
the critical severity s* at which the ratio hits the target (e.g. the
buffer-inclusive CET1 requirement — the MDA/buffer-breach point — or the hard
Pillar-1 minimum).  We then translate s* back into an interpretable macro shock.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from risk_lib.capital.bis import CapitalStack, BIS_MINIMUMS
from risk_lib.provisioning.ecl import compute_ecl
from risk_lib.stress.scenario import Scenario, evaluate_scenario


@dataclass
class StressAxis:
    """Direction of the reverse-stress search: shocks per unit of severity."""
    gdp_per_unit: float = 0.03          # GDP drop per unit severity
    lgd_addon_per_unit: float = 0.05    # LGD add-on (pp) per unit severity
    pd_gdp_elasticity: float = -8.0     # logit-space PD sensitivity to GDP

    def scenario_at(self, severity: float) -> Scenario:
        return Scenario(
            name=f"reverse_s={severity:.4f}",
            pd_multiplier=1.0,
            lgd_addon=severity * self.lgd_addon_per_unit,
            gdp_shock=-severity * self.gdp_per_unit,
            pd_gdp_elasticity=self.pd_gdp_elasticity,
        )


@dataclass
class ReverseStressResult:
    metric: str                 # cet1 | tier1 | total
    target_ratio: float
    base_ratio: float
    critical_severity: float
    resilient: bool             # True if max_severity never reaches the target
    ratio_at_break: float
    rwa_total_at_break: float
    ecl_at_break: float
    implied_gdp_shock: float
    implied_lgd_addon: float
    scenario: Scenario


def reverse_stress(
    irb_portfolio: pd.DataFrame,
    capital: CapitalStack,
    rwa_other: float,
    *,
    metric: str = "cet1",
    target_ratio: float | None = None,
    axis: StressAxis | None = None,
    buffers: dict[str, float] | None = None,
    eir: float = 0.05,
    max_severity: float = 10.0,
    tol: float = 1e-4,
    max_iter: int = 80,
) -> ReverseStressResult:
    """Find the severity at which `metric` ratio falls to `target_ratio`.

    target_ratio defaults to the hard Pillar-1 minimum for the chosen metric
    (the regulatory failure point).  Pass the buffer-inclusive requirement to
    locate the buffer-breach (MDA) point instead.
    """
    if metric not in ("cet1", "tier1", "total"):
        raise ValueError(f"metric must be cet1|tier1|total, got {metric}")
    if axis is None:
        axis = StressAxis()
    if target_ratio is None:
        target_ratio = BIS_MINIMUMS[metric]

    base_ecl = compute_ecl(irb_portfolio, eir=eir)["ecl"].sum()
    ratio_key = f"{metric}_ratio"

    def ratio_at(s: float) -> dict:
        return evaluate_scenario(irb_portfolio, capital, rwa_other,
                                 axis.scenario_at(s), base_ecl=base_ecl,
                                 buffers=buffers, eir=eir)

    # severity 0 leaves PD/LGD unchanged ⇒ this is the unstressed base ratio.
    base_ratio = ratio_at(0.0)[ratio_key]

    def _result(s: float, resilient: bool) -> ReverseStressResult:
        ev = ratio_at(s)
        sc = axis.scenario_at(s)
        return ReverseStressResult(
            metric=metric, target_ratio=target_ratio, base_ratio=base_ratio,
            critical_severity=s, resilient=resilient,
            ratio_at_break=ev[ratio_key], rwa_total_at_break=ev["rwa_total"],
            ecl_at_break=ev["ecl"], implied_gdp_shock=sc.gdp_shock,
            implied_lgd_addon=sc.lgd_addon, scenario=sc,
        )

    # Already at/below the target with no stress.
    if ratio_at(0.0)[ratio_key] <= target_ratio:
        return _result(0.0, resilient=False)

    # Even maximum stress fails to reach the target ⇒ resilient.
    if ratio_at(max_severity)[ratio_key] > target_ratio:
        return _result(max_severity, resilient=True)

    lo, hi = 0.0, max_severity
    for _ in range(max_iter):
        mid = (lo + hi) / 2
        if ratio_at(mid)[ratio_key] > target_ratio:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    return _result((lo + hi) / 2, resilient=False)
