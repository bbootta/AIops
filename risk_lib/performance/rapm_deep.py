"""CRO-grade RAPM (RAROC) deep-dive (v0.12.0).

Adds the following on top of :mod:`risk_lib.performance.rapm`:

- ``raroc_dupont`` — Du Pont-style decomposition of RAROC into four drivers:
  asset yield, capital velocity (EAD/EC), efficiency (1 - cost/revenue) and
  expected loss ratio (EL/EC) plus the risk-free capital benefit.
- ``compute_eva_sva`` — Economic Value Added per exposure + portfolio EVA and
  per-asset-class / per-obligor aggregation.
- ``breakeven_pricing`` — minimum revenue spread (bp) required to clear the
  hurdle rate, per exposure and per asset class; current spread vs breakeven.
- ``risk_adjusted_pricing_premium`` — cost stack (cost of risk + cost of
  capital + operating cost + margin) translated into a target spread (bp).
- ``rapm_scenario`` — stressed RAROC under policy-rate +Δ scenarios (NIM
  uplift) and PD-shock scenarios (EL uplift).
- ``obligor_ranking`` — Top-N value-creating / value-destroying obligors with
  an automated action recommendation (가격 재협상 / 거래 축소 / 한도 조정).
- ``adjusted_raroc_npv`` — multi-year time-value adjusted RAROC using a flat
  NPV cash-flow approach.
- ``industry_benchmark`` — RAROC vs simulated Korean major-bank peer median.
- ``compute_rapm_deep`` — orchestrator returning :class:`RapmDeepResult`.

References
----------
- BCBS Range of Practice in Banks' Internal Ratings Systems (RAPM appendix)
- Basel III Pillar 2 (ICAAP) economic-capital approach
- 금감원 「내부자본적정성평가절차(ICAAP) 운영기준」
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from risk_lib.performance.rapm import rapm_report


HURDLE_DEFAULT = 0.10
RISK_FREE_DEFAULT = 0.03


# ---------------------------------------------------------------- Du Pont

def raroc_dupont(rapm: pd.DataFrame, *, asset_class: pd.Series,
                 ead: pd.Series, risk_free_rate: float = RISK_FREE_DEFAULT,
                 ) -> pd.DataFrame:
    """Du Pont-style decomposition per asset class.

    RAROC = (revenue/EAD) * (EAD/EC) * (1 - cost/revenue)
            - (EL/EC) + rf
          = asset_yield * capital_velocity * efficiency - loss_ratio + rf

    The four-driver identity holds at exposure level; we aggregate by
    asset class using EAD-weighted means for the ratios and totals for
    sums, then reconstruct the identity from the aggregated drivers.
    """
    df = rapm.copy()
    df["asset_class"] = asset_class.to_numpy()
    df["ead"] = ead.to_numpy()
    grp = df.groupby("asset_class")
    agg = grp.agg(
        n=("exposure_id", "size"),
        ead=("ead", "sum"),
        revenue=("revenue", "sum"),
        op_cost=("operating_cost", "sum"),
        el=("expected_loss", "sum"),
        ec=("economic_capital", "sum"),
        cap_benefit=("capital_benefit", "sum"),
    ).reset_index()
    # Drivers
    agg["asset_yield"] = np.where(agg["ead"] > 0,
                                   agg["revenue"] / agg["ead"], 0.0)
    agg["capital_velocity"] = np.where(agg["ec"] > 0,
                                       agg["ead"] / agg["ec"], 0.0)
    agg["efficiency"] = np.where(agg["revenue"] > 0,
                                  1.0 - agg["op_cost"] / agg["revenue"], 0.0)
    agg["loss_ratio"] = np.where(agg["ec"] > 0,
                                  agg["el"] / agg["ec"], 0.0)
    agg["rf_benefit"] = risk_free_rate
    # Reconstructed RAROC from the identity (sanity-checkable)
    agg["raroc_identity"] = (agg["asset_yield"]
                              * agg["capital_velocity"]
                              * agg["efficiency"]
                              - agg["loss_ratio"]
                              + agg["rf_benefit"])
    # Direct RAROC from accounting numerator
    net = (agg["revenue"] - agg["op_cost"] - agg["el"] + agg["cap_benefit"])
    agg["raroc_direct"] = np.where(agg["ec"] > 0, net / agg["ec"], 0.0)
    return agg


def waterfall_components(dupont_row: pd.Series) -> list[tuple[str, float]]:
    """Return ordered (label, contribution) tuples that sum to RAROC.

    Used by the report renderer to draw a horizontal waterfall:
      yield × velocity × efficiency → gross spread contribution
      − loss_ratio                  → expected-loss drag
      + rf                          → capital benefit
      ⇒ RAROC
    """
    gross = (dupont_row["asset_yield"]
             * dupont_row["capital_velocity"]
             * dupont_row["efficiency"])
    return [
        ("자산수익률(yield)×속도×효율", float(gross)),
        ("기대손실(-EL/EC)", -float(dupont_row["loss_ratio"])),
        ("자본운용수익(+rf)", float(dupont_row["rf_benefit"])),
        ("RAROC", float(dupont_row["raroc_identity"])),
    ]


# ---------------------------------------------------------------- EVA / SVA

def compute_eva_sva(rapm: pd.DataFrame, *, hurdle_rate: float = HURDLE_DEFAULT,
                    ) -> pd.DataFrame:
    """Per-exposure EVA = (RAROC - hurdle) * EC.

    SVA (Shareholder Value Added) is the same identity expressed as a
    spread over hurdle multiplied by economic capital — we expose both
    for clarity.
    """
    out = rapm.copy()
    out["eva"] = (out["raroc"] - hurdle_rate) * out["economic_capital"]
    out["sva_spread"] = out["raroc"] - hurdle_rate
    return out


def eva_by_dimension(eva_df: pd.DataFrame, dim: pd.Series,
                     dim_name: str = "dimension") -> pd.DataFrame:
    """Aggregate EVA by an arbitrary grouping dimension."""
    tmp = eva_df.copy()
    tmp[dim_name] = dim.to_numpy()
    agg = tmp.groupby(dim_name).agg(
        n=("exposure_id", "size"),
        ec=("economic_capital", "sum"),
        eva=("eva", "sum"),
        raroc_ead_weighted=("raroc",
                            lambda s: np.average(s, weights=tmp.loc[s.index,
                                                                    "economic_capital"])
                            if tmp.loc[s.index, "economic_capital"].sum() > 0
                            else float("nan")),
    ).reset_index()
    return agg.sort_values("eva", ascending=False)


# ---------------------------------------------------------------- Breakeven

def breakeven_pricing(rapm: pd.DataFrame, *, ead: pd.Series,
                      hurdle_rate: float = HURDLE_DEFAULT,
                      risk_free_rate: float = RISK_FREE_DEFAULT,
                      ) -> pd.DataFrame:
    """Per-exposure breakeven revenue and revenue spread.

    Required net income to clear hurdle:
        net_target = hurdle * EC
        net = revenue - op_cost - EL + EC * rf
        ⇒ revenue_breakeven = hurdle * EC + op_cost + EL - EC * rf
        ⇒ spread_breakeven_bp = revenue_breakeven / EAD * 10_000
    """
    out = rapm[["exposure_id", "revenue", "operating_cost",
                 "expected_loss", "economic_capital", "raroc"]].copy()
    out["ead"] = ead.to_numpy()
    out["revenue_breakeven"] = (hurdle_rate * out["economic_capital"]
                                 + out["operating_cost"]
                                 + out["expected_loss"]
                                 - risk_free_rate * out["economic_capital"])
    out["current_spread_bp"] = np.where(out["ead"] > 0,
                                         out["revenue"] / out["ead"] * 10_000,
                                         0.0)
    out["breakeven_spread_bp"] = np.where(out["ead"] > 0,
                                           out["revenue_breakeven"] / out["ead"]
                                           * 10_000, 0.0)
    out["spread_gap_bp"] = out["current_spread_bp"] - out["breakeven_spread_bp"]
    out["meets_hurdle"] = out["spread_gap_bp"] >= 0.0
    return out


def risk_adjusted_pricing_premium(rapm: pd.DataFrame, *, ead: pd.Series,
                                  asset_class: pd.Series,
                                  hurdle_rate: float = HURDLE_DEFAULT,
                                  target_margin_bp: float = 50.0,
                                  ) -> pd.DataFrame:
    """Decompose target pricing spread into cost components per asset class.

    Target spread (bp) = cost_of_risk + cost_of_capital + operating_cost
                         + target_margin
    """
    tmp = rapm[["expected_loss", "operating_cost",
                "economic_capital"]].copy()
    tmp["ead"] = ead.to_numpy()
    tmp["asset_class"] = asset_class.to_numpy()
    grp = tmp.groupby("asset_class").agg(
        ead=("ead", "sum"),
        el=("expected_loss", "sum"),
        op_cost=("operating_cost", "sum"),
        ec=("economic_capital", "sum"),
    ).reset_index()
    grp["cost_of_risk_bp"] = np.where(grp["ead"] > 0,
                                       grp["el"] / grp["ead"] * 10_000, 0.0)
    grp["cost_of_capital_bp"] = np.where(grp["ead"] > 0,
                                          grp["ec"] * hurdle_rate
                                          / grp["ead"] * 10_000, 0.0)
    grp["operating_cost_bp"] = np.where(grp["ead"] > 0,
                                         grp["op_cost"] / grp["ead"] * 10_000,
                                         0.0)
    grp["target_margin_bp"] = target_margin_bp
    grp["target_spread_bp"] = (grp["cost_of_risk_bp"]
                                + grp["cost_of_capital_bp"]
                                + grp["operating_cost_bp"]
                                + grp["target_margin_bp"])
    return grp


# ---------------------------------------------------------------- Scenarios

@dataclass
class RarocScenario:
    name: str
    rate_shock_bp: float = 0.0    # policy-rate change in bp (NIM uplift)
    pd_uplift: float = 0.0        # multiplicative PD shock (e.g. 0.5 = +50%)
    rate_passthrough: float = 0.5  # share of policy-rate change reaching NIM


DEFAULT_SCENARIOS: list[RarocScenario] = [
    RarocScenario("base", rate_shock_bp=0.0, pd_uplift=0.0),
    RarocScenario("rate_+100bp", rate_shock_bp=100.0, pd_uplift=0.0),
    RarocScenario("rate_-100bp", rate_shock_bp=-100.0, pd_uplift=0.0),
    RarocScenario("pd_+50%", rate_shock_bp=0.0, pd_uplift=0.50),
    RarocScenario("combo_-50bp_pd_+25%", rate_shock_bp=-50.0, pd_uplift=0.25),
]


def rapm_scenario(rapm: pd.DataFrame, *, ead: pd.Series,
                  scenarios: list[RarocScenario] | None = None,
                  hurdle_rate: float = HURDLE_DEFAULT,
                  risk_free_rate: float = RISK_FREE_DEFAULT,
                  ) -> pd.DataFrame:
    """Stress RAROC under policy-rate / PD-shock scenarios.

    Approximation:
      • Policy-rate +Δbp uplifts revenue by ``EAD * Δbp * passthrough``.
      • PD +x% uplifts expected loss by ``EL * x`` (linear in PD).
        EC is held constant — supervisors treat capital as point-in-time
        and a PD shock without re-rating the book is the most defensive
        interpretation; this matches Basel Pillar 2 stress practice.
    """
    if scenarios is None:
        scenarios = DEFAULT_SCENARIOS
    base_rev = rapm["revenue"].to_numpy(dtype=float)
    base_el = rapm["expected_loss"].to_numpy(dtype=float)
    op = rapm["operating_cost"].to_numpy(dtype=float)
    ec = rapm["economic_capital"].to_numpy(dtype=float)
    ead_v = ead.to_numpy(dtype=float)
    cap_benefit = ec * risk_free_rate
    rows: list[dict[str, Any]] = []
    for sc in scenarios:
        rev = base_rev + ead_v * sc.rate_shock_bp / 10_000 * sc.rate_passthrough
        el = base_el * (1.0 + sc.pd_uplift)
        net = rev - op - el + cap_benefit
        raroc = np.where(ec > 0, net / ec, 0.0)
        eva = (raroc - hurdle_rate) * ec
        pass_hurdle = raroc >= hurdle_rate
        rows.append({
            "scenario": sc.name,
            "rate_shock_bp": sc.rate_shock_bp,
            "pd_uplift": sc.pd_uplift,
            "revenue": float(rev.sum()),
            "expected_loss": float(el.sum()),
            "economic_capital": float(ec.sum()),
            "raroc_weighted": float(np.average(raroc,
                                                weights=np.maximum(ec, 1e-9))),
            "eva": float(eva.sum()),
            "pass_hurdle_pct": float(pass_hurdle.mean()),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- Obligor rank

def obligor_ranking(rapm: pd.DataFrame, *, obligor_id: pd.Series,
                    hurdle_rate: float = HURDLE_DEFAULT, n: int = 20,
                    ) -> dict[str, pd.DataFrame]:
    """Top/Bottom obligor ranking by EVA + an action recommendation.

    The recommendation maps to one of:
      • ``OK``                — RAROC ≥ hurdle (no action).
      • ``가격 재협상``         — RAROC in [0, hurdle): repricing required.
      • ``거래 축소``           — RAROC in [-0.10, 0): negative carry, shrink.
      • ``한도 조정 / 종결``     — RAROC < -0.10: terminate / reset limit.
    """
    eva_df = compute_eva_sva(rapm, hurdle_rate=hurdle_rate)
    eva_df = eva_df.assign(obligor_id=obligor_id.to_numpy())
    grp = eva_df.groupby("obligor_id").agg(
        n_exposures=("exposure_id", "size"),
        ead=("economic_capital", "sum"),  # proxy if EAD unavailable; replaced below
        ec=("economic_capital", "sum"),
        revenue=("revenue", "sum"),
        expected_loss=("expected_loss", "sum"),
        eva=("eva", "sum"),
    ).reset_index()
    # Approximate RAROC from aggregated EVA: raroc = eva/ec + hurdle.
    grp["raroc"] = np.where(grp["ec"] > 0,
                             grp["eva"] / grp["ec"] + hurdle_rate, 0.0)
    grp["recommendation"] = grp["raroc"].map(_recommend)
    top = grp.sort_values("eva", ascending=False).head(n).reset_index(drop=True)
    bottom = grp.sort_values("eva", ascending=True).head(n).reset_index(drop=True)
    return {"top": top, "bottom": bottom, "all": grp}


def _recommend(raroc_value: float) -> str:
    if raroc_value >= HURDLE_DEFAULT:
        return "OK"
    if raroc_value >= 0.0:
        return "가격 재협상"
    if raroc_value >= -0.10:
        return "거래 축소"
    return "한도 조정 / 종결"


# ---------------------------------------------------------------- NPV-adjusted

def adjusted_raroc_npv(rapm: pd.DataFrame, *, maturity: pd.Series,
                       discount_rate: float = 0.08,
                       hurdle_rate: float = HURDLE_DEFAULT,
                       ) -> pd.DataFrame:
    """NPV-adjusted RAROC: discount per-period net income over the
    contractual maturity at ``discount_rate`` and normalise by EC.

    A constant-cash-flow approximation is used — production should
    replace with an actual amortisation schedule.
    """
    out = rapm[["exposure_id", "revenue", "operating_cost",
                 "expected_loss", "capital_benefit",
                 "economic_capital", "raroc"]].copy()
    out["maturity"] = np.clip(maturity.to_numpy(dtype=float), 0.5, 30.0)
    net_per_period = (out["revenue"] - out["operating_cost"]
                       - out["expected_loss"] + out["capital_benefit"])
    # Annuity factor a = (1 - (1+r)^-n) / r
    r = discount_rate
    a = (1.0 - (1.0 + r) ** (-out["maturity"])) / r
    out["npv_net"] = net_per_period * a
    out["raroc_npv"] = np.where(out["economic_capital"] > 0,
                                  out["npv_net"] / out["economic_capital"]
                                  / out["maturity"], 0.0)
    out["meets_hurdle_npv"] = out["raroc_npv"] >= hurdle_rate
    return out


# ---------------------------------------------------------------- Benchmark

def industry_benchmark(rapm: pd.DataFrame, *,
                       peer_median: float = 0.095,
                       peer_top_quartile: float = 0.135,
                       hurdle_rate: float = HURDLE_DEFAULT,
                       ) -> dict[str, float]:
    """RAROC positioning vs simulated KR major-bank peer set.

    Peer values are illustrative defaults (4대 시중은행 평균 RAROC
    가정) and should be replaced with periodic industry surveys.
    """
    weights = np.maximum(rapm["economic_capital"].to_numpy(dtype=float), 1e-9)
    own = float(np.average(rapm["raroc"].to_numpy(dtype=float), weights=weights))
    return {
        "own_raroc": own,
        "peer_median": peer_median,
        "peer_top_quartile": peer_top_quartile,
        "gap_to_median": own - peer_median,
        "gap_to_top_quartile": own - peer_top_quartile,
        "gap_to_hurdle": own - hurdle_rate,
        "position": (
            "top-quartile" if own >= peer_top_quartile
            else ("above-median" if own >= peer_median
                  else ("below-median" if own >= hurdle_rate
                        else "below-hurdle"))
        ),
    }


# ---------------------------------------------------------------- Orchestrator

@dataclass
class RapmDeepResult:
    rapm_exposure: pd.DataFrame          # per-exposure RAPM table with EVA
    dupont: pd.DataFrame                 # Du Pont decomp by asset class
    pricing_premium: pd.DataFrame        # target spread decomposition
    breakeven: pd.DataFrame              # per-exposure breakeven spread
    breakeven_by_class: pd.DataFrame     # asset class roll-up
    scenarios: pd.DataFrame              # stress RAROC scenarios
    obligor_top: pd.DataFrame            # value-creating obligors
    obligor_bottom: pd.DataFrame         # value-destroying obligors
    eva_by_class: pd.DataFrame           # EVA by asset class
    npv_adjusted: pd.DataFrame           # NPV-adjusted RAROC per exposure
    benchmark: dict[str, float]          # peer comparison
    summary: dict[str, Any] = field(default_factory=dict)


def compute_rapm_deep(irb_book: pd.DataFrame, *,
                      hurdle_rate: float = HURDLE_DEFAULT,
                      risk_free_rate: float = RISK_FREE_DEFAULT,
                      ) -> RapmDeepResult:
    """End-to-end CRO-grade RAPM deep-dive over ``irb_book``."""
    needed = ["exposure_id", "obligor_id", "asset_class", "ead",
              "pd", "lgd", "maturity", "revenue", "operating_cost"]
    df = irb_book[needed].copy()
    rapm = rapm_report(df, hurdle_rate=hurdle_rate,
                       risk_free_rate=risk_free_rate)
    # attach asset_class / ead for downstream merges
    rapm = rapm.merge(df[["exposure_id", "asset_class", "obligor_id",
                          "maturity", "ead", "pd", "lgd"]],
                       on="exposure_id")
    # EVA
    eva_df = compute_eva_sva(rapm, hurdle_rate=hurdle_rate)
    # Du Pont
    dupont = raroc_dupont(rapm, asset_class=rapm["asset_class"],
                          ead=rapm["ead"], risk_free_rate=risk_free_rate)
    # Pricing
    bep = breakeven_pricing(rapm, ead=rapm["ead"],
                            hurdle_rate=hurdle_rate,
                            risk_free_rate=risk_free_rate)
    bep = bep.merge(rapm[["exposure_id", "asset_class"]], on="exposure_id")
    bep_class = bep.groupby("asset_class").agg(
        n=("exposure_id", "size"),
        current_spread_bp_avg=("current_spread_bp", "mean"),
        breakeven_spread_bp_avg=("breakeven_spread_bp", "mean"),
        spread_gap_bp_avg=("spread_gap_bp", "mean"),
        n_below_breakeven=("meets_hurdle", lambda s: int((~s).sum())),
    ).reset_index()
    pricing_p = risk_adjusted_pricing_premium(
        rapm, ead=rapm["ead"], asset_class=rapm["asset_class"],
        hurdle_rate=hurdle_rate,
    )
    # Scenarios
    scen = rapm_scenario(rapm, ead=rapm["ead"],
                         hurdle_rate=hurdle_rate,
                         risk_free_rate=risk_free_rate)
    # Obligor ranking
    obligor = obligor_ranking(rapm, obligor_id=rapm["obligor_id"],
                              hurdle_rate=hurdle_rate)
    # EVA by class
    eva_class = eva_by_dimension(eva_df, rapm["asset_class"], "asset_class")
    # NPV-adjusted RAROC
    npv = adjusted_raroc_npv(rapm, maturity=rapm["maturity"],
                              hurdle_rate=hurdle_rate)
    # Benchmark
    bench = industry_benchmark(rapm, hurdle_rate=hurdle_rate)
    # Summary
    weights = np.maximum(rapm["economic_capital"].to_numpy(dtype=float), 1e-9)
    raroc_w = float(np.average(rapm["raroc"].to_numpy(dtype=float),
                                weights=weights))
    summary = {
        "n_exposures": int(len(rapm)),
        "ec_total": float(rapm["economic_capital"].sum()),
        "el_total": float(rapm["expected_loss"].sum()),
        "revenue_total": float(rapm["revenue"].sum()),
        "raroc_weighted": raroc_w,
        "eva_total": float(eva_df["eva"].sum()),
        "pass_hurdle_pct": float(rapm["pass_hurdle"].mean()),
        "value_creating_pct": float((eva_df["eva"] > 0).mean()),
        "n_repricing": int(((rapm["raroc"] >= 0)
                            & (rapm["raroc"] < hurdle_rate)).sum()),
        "n_terminate": int((rapm["raroc"] < -0.10).sum()),
        "hurdle_rate": hurdle_rate,
        "risk_free_rate": risk_free_rate,
    }
    return RapmDeepResult(
        rapm_exposure=eva_df,
        dupont=dupont,
        pricing_premium=pricing_p,
        breakeven=bep,
        breakeven_by_class=bep_class,
        scenarios=scen,
        obligor_top=obligor["top"],
        obligor_bottom=obligor["bottom"],
        eva_by_class=eva_class,
        npv_adjusted=npv,
        benchmark=bench,
        summary=summary,
    )
