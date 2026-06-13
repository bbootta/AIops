"""Risk Appetite Framework (RAF) + KRI scorecard.

RAF turns the harness's raw numbers into a board-level traffic-light grid.
Each KRI has three thresholds — board (hard limit), management (escalation),
operational (early warning) — and is graded against actual.

Output is intentionally machine-readable (`KRIResult`) so the HTML report can
render colored badges and the CLI can grep for breaches.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import pandas as pd

from risk_lib.references import (
    BIS_MIN_CET1, BIS_MIN_TIER1, BIS_MIN_TOTAL, CAPITAL_CONSERVATION_BUFFER,
    LEVERAGE_MIN_RATIO, LCR_MIN, NSFR_MIN, HHI_HIGH, GINI_MIN_GOOD,
    IRRBB_OUTLIER_EVE_PCT_TIER1, IRRBB_EARLY_WARNING_PCT_TIER1,
    ICAAP_GREEN_UTILISATION, ICAAP_AMBER_UTILISATION,
    SINGLE_OBLIGOR_LIMIT_PCT_TIER1,
)


@dataclass
class KRIThreshold:
    """Three-tier threshold for one KRI.

    `direction` is "min" (actual must stay ≥ threshold) or "max" (≤).
    `board` is the hard limit (board-approved); breach = RED.
    `management` is the escalation level; breach = AMBER.
    `operational` is the early-warning level; breach = WATCH.
    """
    board: float
    management: float
    operational: float
    direction: str = "min"      # "min" or "max"


@dataclass
class KRIResult:
    name: str
    category: str               # capital / liquidity / credit / market / ops
    actual: float
    threshold: KRIThreshold
    grade: str                  # GREEN | WATCH | AMBER | RED
    distance_to_board: float    # signed slack to the hard limit
    fmt: str = "pct"            # "pct" | "ratio" | "money"
    citation: str = ""          # short string e.g. "CRE10.4"


@dataclass
class RAFReport:
    kris: list[KRIResult] = field(default_factory=list)

    def summary(self) -> dict[str, int]:
        from collections import Counter
        return dict(Counter(k.grade for k in self.kris))

    def worst(self) -> str:
        order = {"GREEN": 0, "WATCH": 1, "AMBER": 2, "RED": 3}
        return max((k.grade for k in self.kris), key=lambda g: order[g],
                   default="GREEN")

    def to_frame(self) -> pd.DataFrame:
        rows = []
        for k in self.kris:
            rows.append({
                "category": k.category, "name": k.name,
                "actual": k.actual,
                "operational": k.threshold.operational,
                "management": k.threshold.management,
                "board": k.threshold.board,
                "direction": k.threshold.direction,
                "grade": k.grade, "distance_to_board": k.distance_to_board,
                "fmt": k.fmt, "citation": k.citation,
            })
        return pd.DataFrame(rows)


def _grade(actual: float, t: KRIThreshold) -> tuple[str, float]:
    if t.direction == "min":
        if actual < t.board:        g = "RED"
        elif actual < t.management: g = "AMBER"
        elif actual < t.operational:g = "WATCH"
        else:                       g = "GREEN"
        dist = actual - t.board
    else:                           # "max"
        if actual > t.board:        g = "RED"
        elif actual > t.management: g = "AMBER"
        elif actual > t.operational:g = "WATCH"
        else:                       g = "GREEN"
        dist = t.board - actual
    return g, dist


def _kri(name, category, actual, t, *, fmt="pct", citation=""):
    g, d = _grade(actual, t)
    return KRIResult(name=name, category=category, actual=actual, threshold=t,
                     grade=g, distance_to_board=d, fmt=fmt, citation=citation)


# ---------------------------------------------------------------- defaults

def default_thresholds() -> dict[str, KRIThreshold]:
    """Internal RAF ladder layered on top of regulatory minima.

    Convention: management = regulatory + management buffer; operational =
    regulatory + larger early-warning buffer. Numbers are the harness's
    default risk appetite — overrideable per-institution via build_raf().
    """
    cet1_req = BIS_MIN_CET1 + CAPITAL_CONSERVATION_BUFFER         # 7.0%
    tier1_req = BIS_MIN_TIER1 + CAPITAL_CONSERVATION_BUFFER       # 8.5%
    total_req = BIS_MIN_TOTAL + CAPITAL_CONSERVATION_BUFFER       # 10.5%
    return {
        # capital
        "CET1 비율":      KRIThreshold(cet1_req, cet1_req + 0.015, cet1_req + 0.030, "min"),
        "Tier1 비율":     KRIThreshold(tier1_req, tier1_req + 0.015, tier1_req + 0.030, "min"),
        "총자본 비율":     KRIThreshold(total_req, total_req + 0.015, total_req + 0.030, "min"),
        "레버리지 비율":   KRIThreshold(LEVERAGE_MIN_RATIO,
                                       LEVERAGE_MIN_RATIO + 0.01,
                                       LEVERAGE_MIN_RATIO + 0.02, "min"),
        "ICAAP 사용률":   KRIThreshold(ICAAP_AMBER_UTILISATION,
                                       ICAAP_GREEN_UTILISATION,
                                       ICAAP_GREEN_UTILISATION - 0.10, "max"),
        # liquidity
        "LCR":            KRIThreshold(LCR_MIN, LCR_MIN + 0.10, LCR_MIN + 0.20, "min"),
        "NSFR":           KRIThreshold(NSFR_MIN, NSFR_MIN + 0.05, NSFR_MIN + 0.10, "min"),
        # market / IRRBB
        "IRRBB ΔEVE/Tier1": KRIThreshold(IRRBB_OUTLIER_EVE_PCT_TIER1,
                                          IRRBB_EARLY_WARNING_PCT_TIER1,
                                          IRRBB_EARLY_WARNING_PCT_TIER1 - 0.02, "max"),
        # credit / concentration
        "국가 HHI":       KRIThreshold(0.25, HHI_HIGH, HHI_HIGH - 0.03, "max"),
        "섹터 HHI":       KRIThreshold(0.25, HHI_HIGH, HHI_HIGH - 0.03, "max"),
        "PD모형 최저 Gini": KRIThreshold(0.20, GINI_MIN_GOOD - 0.05, GINI_MIN_GOOD, "min"),
        # earnings/credit
        "스트레스 CET1 (severe)": KRIThreshold(cet1_req - 0.03, cet1_req, cet1_req + 0.01, "min"),
    }


def build_raf(result: Any, *, thresholds: dict[str, KRIThreshold] | None = None) -> RAFReport:
    """Compute KRI grades from a PipelineResult."""
    t = thresholds or default_thresholds()
    bis = result.bis; lev = result.leverage; alm = result.alm; icaap = result.icaap
    conc = result.concentration.set_index("dimension")["hhi"]
    seg_gini = min(m["gini"] for m in result.pd_metrics.values()) \
        if result.pd_metrics else 0.0
    stress_severe = result.stress[result.stress["scenario"] == "severely_adverse"]
    cet1_severe = float(stress_severe["cet1_ratio"].iloc[0]) if len(stress_severe) else 0.0

    kris = [
        _kri("CET1 비율", "capital", bis.cet1_ratio, t["CET1 비율"], citation="CRE10.4"),
        _kri("Tier1 비율", "capital", bis.tier1_ratio, t["Tier1 비율"], citation="CRE10.4"),
        _kri("총자본 비율", "capital", bis.total_ratio, t["총자본 비율"], citation="CRE10.4"),
        _kri("레버리지 비율", "capital", lev.leverage_ratio, t["레버리지 비율"], citation="LEV10.6"),
        _kri("ICAAP 사용률", "capital", icaap.utilisation, t["ICAAP 사용률"], citation="SRP20"),
        _kri("LCR", "liquidity", alm["lcr"].lcr, t["LCR"], citation="LCR20.1"),
        _kri("NSFR", "liquidity", alm["nsfr"].nsfr, t["NSFR"], citation="NSF20.1"),
        _kri("IRRBB ΔEVE/Tier1", "market", alm["irrbb"].worst_pct_tier1,
             t["IRRBB ΔEVE/Tier1"], citation="SRP31.92"),
        _kri("국가 HHI", "concentration", float(conc.get("country", 0.0)),
             t["국가 HHI"], fmt="ratio", citation="DOJ/FTC"),
        _kri("섹터 HHI", "concentration", float(conc.get("sector", 0.0)),
             t["섹터 HHI"], fmt="ratio", citation="DOJ/FTC"),
        _kri("PD모형 최저 Gini", "model", seg_gini, t["PD모형 최저 Gini"],
             fmt="ratio", citation="BCBS WP14"),
        _kri("스트레스 CET1 (severe)", "stress", cet1_severe,
             t["스트레스 CET1 (severe)"], citation="감독세칙 ST"),
    ]
    return RAFReport(kris=kris)
