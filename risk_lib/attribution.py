"""Attribution / Bridge analyses.

Answers the CRO's "why did this number move?" question by decomposing the
change between two PipelineResults into additive drivers.

  - capital_bridge:    CET1 ratio change  → (capital effect) + (RWA effect)
  - rwa_bridge:        final RWA change   → SA / IRB / market / op / floor
  - ecl_bridge:        ECL change         → PD / LGD / EAD / mix
  - lcr_bridge:        LCR change         → HQLA / outflows / inflows

For single-snapshot use we also expose `decompose_*` helpers that explain
the *current* value in terms of underlying drivers (no second snapshot
needed): e.g. RWA decomposed into the four risk types, CET1 surplus
decomposed into capital headroom vs RWA headroom vs buffer requirement.

All numbers carry units of the underlying metric (currency or ratio %),
not pp/%pp ambiguity, so callers can sum drivers and reconcile to the
total without sign confusion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class BridgeStep:
    label: str
    value: float                 # signed contribution
    cumulative: float            # running total after this step
    note: str = ""


@dataclass
class Bridge:
    metric: str
    start_value: float
    end_value: float
    steps: list[BridgeStep] = field(default_factory=list)

    @property
    def explained_change(self) -> float:
        return sum(s.value for s in self.steps)

    @property
    def residual(self) -> float:
        return (self.end_value - self.start_value) - self.explained_change

    def to_frame(self) -> pd.DataFrame:
        rows = [{"label": "기초 " + self.metric, "value": self.start_value,
                 "cumulative": self.start_value, "note": ""}]
        for s in self.steps:
            rows.append({"label": s.label, "value": s.value,
                         "cumulative": s.cumulative, "note": s.note})
        rows.append({"label": "기말 " + self.metric, "value": self.end_value,
                     "cumulative": self.end_value, "note": "잔차 %+.4g" % self.residual})
        return pd.DataFrame(rows)


# ---------------------------------------------------------------- bridges

def capital_bridge(a: Any, b: Any) -> Bridge:
    """CET1 ratio change between snapshot A → B, split into capital and RWA effects.

    CET1_b - CET1_a
       = (CET1_b - CET1_a) / RWA_a                     # capital effect
       + CET1_b * (1/RWA_b - 1/RWA_a)                  # RWA effect
    plus a small cross-term we attribute proportionally.
    """
    Ka, Kb = a.meta["capital"].cet1, b.meta["capital"].cet1
    Ra, Rb = a.bis.rwa, b.bis.rwa
    cet1_a, cet1_b = Ka / Ra, Kb / Rb

    capital_eff = (Kb - Ka) / Ra
    rwa_eff = Kb * (1.0 / Rb - 1.0 / Ra)
    steps = [
        BridgeStep("자본 증감 효과", capital_eff, cet1_a + capital_eff,
                   note=f"CET1 자본 {Ka/1e9:+.0f}→{Kb/1e9:+.0f}십억"),
        BridgeStep("RWA 증감 효과", rwa_eff, cet1_a + capital_eff + rwa_eff,
                   note=f"RWA {Ra/1e12:.2f}→{Rb/1e12:.2f}조"),
    ]
    return Bridge(metric="CET1 비율", start_value=cet1_a, end_value=cet1_b,
                  steps=steps)


def rwa_bridge(a: Any, b: Any) -> Bridge:
    """Final RWA change A → B, decomposed into the four risk-type buckets
    plus the residual that the output-floor add-on contributes."""
    components = ["sa", "irb", "market", "op"]
    labels = {"sa": "신용 SA", "irb": "신용 IRB",
              "market": "시장리스크", "op": "운영리스크"}
    cum = a.rwa["final_total"]
    steps = []
    for k in components:
        d = b.rwa[k] - a.rwa[k]
        cum += d
        steps.append(BridgeStep(labels[k], d, cum))

    # Output-floor add-on residual: (final - sum_of_components) for each side.
    floor_a = a.rwa["final_total"] - sum(a.rwa[k] for k in components)
    floor_b = b.rwa["final_total"] - sum(b.rwa[k] for k in components)
    d_floor = floor_b - floor_a
    cum += d_floor
    steps.append(BridgeStep("Output floor 가산 변화", d_floor, cum))
    return Bridge(metric="최종 RWA", start_value=a.rwa["final_total"],
                  end_value=b.rwa["final_total"], steps=steps)


def ecl_bridge(a: Any, b: Any) -> Bridge:
    """TTC ECL change A → B, decomposed into PD-effect, LGD-effect,
    EAD-effect using the IRB book mean PD, LGD, EAD on each side and the
    Marshall-Edgeworth attribution (avg of two-period weights).

    ECL ≈ PD · LGD · EAD (Stage-1 12M, dominant component).
    """
    da, db = a.ecl["by_stage"], b.ecl["by_stage"]
    ecl_a = float(a.ecl["total"]); ecl_b = float(b.ecl["total"])

    # Aggregate PD/LGD/EAD over Stage 1+2 EAD-weighted (use coverage as proxy).
    # We use total ECL / total EAD and assume PD·LGD = coverage; that lets us
    # decompose into a "rate" effect (coverage) and an "EAD" effect.
    ead_a = float(da["ead"].sum()); ead_b = float(db["ead"].sum())
    rate_a = ecl_a / ead_a if ead_a else 0.0
    rate_b = ecl_b / ead_b if ead_b else 0.0

    # Marshall-Edgeworth: Δ = Δrate · (EAD_a + EAD_b)/2 + Δead · (rate_a + rate_b)/2
    rate_eff = (rate_b - rate_a) * (ead_a + ead_b) / 2
    ead_eff  = (ead_b - ead_a) * (rate_a + rate_b) / 2
    steps = [
        BridgeStep("EAD 규모 효과", ead_eff, ecl_a + ead_eff,
                   note=f"EAD {ead_a/1e12:.2f}→{ead_b/1e12:.2f}조"),
        BridgeStep("PD·LGD(커버리지) 효과", rate_eff, ecl_a + ead_eff + rate_eff,
                   note=f"평균 커버리지 {rate_a*100:.2f}→{rate_b*100:.2f}%"),
    ]
    return Bridge(metric="TTC ECL", start_value=ecl_a, end_value=ecl_b,
                  steps=steps)


def lcr_bridge(a: Any, b: Any) -> Bridge:
    """LCR change A → B, attribution to HQLA, outflow, inflow legs."""
    la, lb = a.alm["lcr"], b.alm["lcr"]
    # LCR = HQLA / Net.  ΔLCR ≈ ΔHQLA/Net_a + HQLA_b·Δ(1/Net).
    h_eff = (lb.hqla_total - la.hqla_total) / la.net_outflow
    net_eff = lb.hqla_total * (1.0 / lb.net_outflow - 1.0 / la.net_outflow)
    # Further split net_eff into gross-outflow and inflow drivers.
    da_outflow = (lb.gross_outflow - la.gross_outflow)
    da_inflow  = (lb.inflow_capped - la.inflow_capped)
    # weight by share of the Δnet
    dnet = (lb.net_outflow - la.net_outflow) or 1.0
    w_out = da_outflow / dnet if dnet else 0.5
    w_in = (-da_inflow) / dnet if dnet else 0.5
    out_eff = net_eff * w_out
    in_eff  = net_eff * w_in
    cum = la.lcr
    steps = [
        BridgeStep("HQLA 증감", h_eff, (cum := cum + h_eff)),
        BridgeStep("총유출 증감", out_eff, (cum := cum + out_eff)),
        BridgeStep("유입 증감", in_eff, (cum := cum + in_eff)),
    ]
    return Bridge(metric="LCR", start_value=la.lcr, end_value=lb.lcr,
                  steps=steps)


# ---------------------------------------------------------------- single-snapshot

def decompose_cet1_headroom(result: Any) -> pd.DataFrame:
    """Explain the CET1 surplus as the gap between actual and three layers."""
    bis = result.bis
    layers = ["최저 (CRE10.4)", "+자본보전버퍼", "+CCyB+DSIB"]
    cet1_min = 0.045
    ccb = bis.required["cet1"] - cet1_min       # ccb + ccyb + dsib lumped
    rows = [
        {"layer": "최저", "required": cet1_min, "actual": bis.cet1_ratio,
         "headroom": bis.cet1_ratio - cet1_min},
        {"layer": "최저+CCB", "required": cet1_min + 0.025,
         "actual": bis.cet1_ratio,
         "headroom": bis.cet1_ratio - (cet1_min + 0.025)},
        {"layer": "최저+CCB+CCyB+DSIB (감독요구)", "required": bis.required["cet1"],
         "actual": bis.cet1_ratio,
         "headroom": bis.cet1_ratio - bis.required["cet1"]},
    ]
    return pd.DataFrame(rows)


def decompose_rwa(result: Any) -> pd.DataFrame:
    rwa = result.rwa
    total = rwa["final_total"]
    rows = [
        ("신용 SA", rwa["sa"]), ("신용 IRB", rwa["irb"]),
        ("시장리스크", rwa["market"]), ("운영리스크", rwa["op"]),
    ]
    rows.append(("Output floor 가산",
                 total - sum(v for _, v in rows)))
    return pd.DataFrame([{"component": k, "rwa": v, "share": v / total}
                         for k, v in rows])
