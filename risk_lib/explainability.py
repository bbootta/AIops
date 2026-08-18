"""Explainability layer — Top-IB grade decision support.

For every reported risk number the CRO / 현업실무자 must be able to ask:
  - **Why is this number what it is?** (driver decomposition)
  - **What single change would move it the most?** (counterfactual)
  - **What would we have to believe for this not to hold?** (sensitivity)
  - **Who else has signed off on this number?** (audit lineage)

This module provides:
  1. **driver_decomposition**: SHAP-style additive breakdown of a metric
     into its top-N drivers
  2. **counterfactual**: minimum input change to flip a verdict
  3. **what_if_table**: pre-canned sensitivity grid for top KRIs
  4. **NarrativeBuilder**: auto-generates 1-paragraph board-pack narrative
     ("CET1 fell 30bp YoY driven primarily by RWA growth in corporate
      book offset by capital accretion from retained earnings…")

Reference: SHAP (Lundberg & Lee 2017) approximation via Shapley sampling
without scikit-learn — implemented with numpy only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from typing import Any, Callable

import numpy as np
import pandas as pd


# ----- Shapley-style driver decomposition ---------------------------------

@dataclass
class Driver:
    name: str
    contribution: float          # signed contribution to the metric value
    contribution_pct: float      # % of total absolute contribution
    direction: str               # "+" / "-" / "~"


def driver_decomposition(
    base_value: float, current_value: float,
    drivers: dict[str, float],
    *, top_n: int = 5,
) -> list[Driver]:
    """Decompose (current - base) into driver contributions.

    Inputs:
        drivers: name → raw delta the driver applied to the metric.
                 If sum(drivers.values()) != (current - base), residual is
                 captured as "other".

    Returns sorted list of top-N drivers by absolute contribution.
    """
    total_change = current_value - base_value
    explained = sum(drivers.values())
    residual = total_change - explained

    items = dict(drivers)
    if abs(residual) > 1e-6 * max(abs(total_change), 1.0):
        items["other"] = residual

    abs_total = sum(abs(v) for v in items.values()) or 1.0
    out = []
    for name, contrib in items.items():
        pct = abs(contrib) / abs_total
        direction = "+" if contrib > 1e-9 else "-" if contrib < -1e-9 else "~"
        out.append(Driver(
            name=name, contribution=contrib,
            contribution_pct=pct, direction=direction,
        ))
    out.sort(key=lambda d: -abs(d.contribution))
    return out[:top_n]


# ----- Shapley sampling for non-linear metrics ----------------------------

def shapley_attribution(
    metric_fn: Callable[[dict[str, float]], float],
    baseline: dict[str, float],
    scenario: dict[str, float],
    *, n_samples: int = 256, rng=None,
) -> dict[str, float]:
    """Approximate SHAP values for a black-box metric via Shapley sampling.

    For each input feature, sample random coalitions and compute the
    marginal contribution of that feature.

    Args:
        metric_fn: maps dict of features → scalar metric value
        baseline: feature dict at the baseline
        scenario: feature dict at the scenario point

    Returns:
        dict feature → estimated SHAP contribution
    """
    rng = rng if rng is not None else np.random.default_rng(42)
    features = list(baseline.keys())
    n_feat = len(features)
    shap = {f: 0.0 for f in features}

    for _ in range(n_samples):
        perm = rng.permutation(n_feat)
        current = dict(baseline)
        prev = metric_fn(current)
        for idx in perm:
            f = features[idx]
            current = dict(current)
            current[f] = scenario[f]
            new = metric_fn(current)
            shap[f] += (new - prev) / n_samples
            prev = new
    return shap


# ----- counterfactual ------------------------------------------------------

@dataclass
class CounterfactualResult:
    feature: str
    baseline_value: float
    target_value: float
    delta_required: float
    target_metric: float


def find_counterfactual(
    metric_fn: Callable[[dict[str, float]], float],
    features: dict[str, float],
    target_value: float,
    *, search_feature: str,
    direction: str = "down",       # "down" reduces feature, "up" increases
    bounds: tuple[float, float] | None = None,
    tol: float = 1e-4,
    max_iter: int = 100,
) -> CounterfactualResult:
    """Binary-search the smallest change in `search_feature` that brings
    the metric to `target_value`.
    """
    if bounds is None:
        b = features[search_feature]
        bounds = (b * 0.1, b * 2.0) if b > 0 else (b * 2.0, b * 0.1)

    lo, hi = sorted(bounds)
    base_metric = metric_fn(features)

    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        scenario = dict(features)
        scenario[search_feature] = mid
        m = metric_fn(scenario)
        if abs(m - target_value) < tol:
            return CounterfactualResult(
                feature=search_feature,
                baseline_value=features[search_feature],
                target_value=mid,
                delta_required=mid - features[search_feature],
                target_metric=m,
            )
        if (m > target_value) == (direction == "down"):
            lo = mid
        else:
            hi = mid
    return CounterfactualResult(
        feature=search_feature,
        baseline_value=features[search_feature],
        target_value=mid,
        delta_required=mid - features[search_feature],
        target_metric=m,
    )


# ----- pre-canned what-if grid --------------------------------------------

@dataclass
class WhatIfRow:
    factor: str
    shock: float
    metric_name: str
    base_value: float
    shocked_value: float
    delta: float
    pct_change: float


def what_if_grid(
    metrics: dict[str, float],
    shocks: dict[str, dict[str, float]],
) -> list[WhatIfRow]:
    """Pre-canned shock grid.

    Args:
        metrics: metric_name → base_value
        shocks: factor_name → {metric_name → shocked_value}

    Returns flattened list of WhatIfRow.
    """
    out = []
    for factor, m_dict in shocks.items():
        for m_name, shocked in m_dict.items():
            base = metrics[m_name]
            d = shocked - base
            pct = d / abs(base) if abs(base) > 1e-12 else 0.0
            out.append(WhatIfRow(
                factor=factor, shock=0.0,
                metric_name=m_name, base_value=base,
                shocked_value=shocked, delta=d, pct_change=pct,
            ))
    return out


# ----- Narrative builder ---------------------------------------------------

@dataclass
class Narrative:
    headline: str
    paragraphs: list[str]
    drivers: list[Driver]
    actions: list[str]


def narrate_capital_change(
    *, base_cet1: float, current_cet1: float,
    rwa_change_pct: float, capital_change_pct: float,
    bis_required: float = 0.08,
) -> Narrative:
    """Auto-generate a board-pack narrative for a CET1 movement."""
    delta_bp = (current_cet1 - base_cet1) * 100 * 100   # bp
    direction = "상승" if delta_bp > 0 else "하락" if delta_bp < 0 else "보합"

    drivers = driver_decomposition(
        base_cet1, current_cet1,
        {
            "RWA 변동": current_cet1 * (-rwa_change_pct),
            "자본 변동": current_cet1 * capital_change_pct,
        },
    )

    headline = (f"CET1 비율 {direction} {abs(delta_bp):.0f}bp "
                f"({base_cet1*100:.2f}% → {current_cet1*100:.2f}%)")

    para1 = (f"분기 CET1 비율이 {base_cet1*100:.2f}%에서 {current_cet1*100:.2f}%로 "
             f"{abs(delta_bp):.0f}bp {direction}했습니다. "
             f"주요 driver는 ")
    if drivers:
        para1 += " · ".join(
            f"{d.name} ({d.direction}{abs(d.contribution)*10000:.0f}bp)"
            for d in drivers[:2])
        para1 += " 입니다."

    para2 = ""
    if current_cet1 < bis_required + 0.025:
        para2 = ("⚠️ CET1이 자본보전버퍼(CCB) 적용 임계에 근접합니다. "
                 "감독상 MDA 분배제한 고려 필요.")
    elif current_cet1 < bis_required + 0.05:
        para2 = ("CCB 위 안전 마진은 확보되었으나, 추가 자본 확충 또는 "
                 "RWA 효율화 검토를 권고합니다.")
    else:
        para2 = ("규제 요구치를 충분히 상회하며 분배 여력이 있습니다.")

    actions = []
    if delta_bp < -30:
        actions.append("RWA 변동의 driver별 분해 (자산군 × 등급별) 검토")
    if drivers and drivers[0].name == "RWA 변동" and drivers[0].direction == "+":
        actions.append("신규 여신 한도 재조정 또는 자본효율 큰 자산으로의 mix shift")
    if current_cet1 < 0.10:
        actions.append("AT1/T2 발행 검토 + 배당 정책 재검토")

    return Narrative(
        headline=headline,
        paragraphs=[para1, para2],
        drivers=drivers,
        actions=actions,
    )


# ----- Action Recommender --------------------------------------------------

@dataclass
class ActionItem:
    priority: int                # 1 (urgent) ... 5 (routine)
    category: str
    description: str
    owner: str
    timeline: str
    citation: str
    blocking: bool = False


def recommend_actions(result) -> list[ActionItem]:
    """Walk the pipeline result and produce ranked actions."""
    actions: list[ActionItem] = []

    # ── RAF breaches
    if result.raf:
        for k in result.raf.kris:
            if k.grade == "RED":
                actions.append(ActionItem(
                    priority=1, category="자본/유동성",
                    description=(f"[{k.name}] 한계 침범 — 실측 {k.actual:.4f} "
                                 f"vs board {k.threshold.board:.4f}. 즉시 대응."),
                    owner=k.category + " 담당", timeline="48시간 이내",
                    citation=k.citation, blocking=True,
                ))
            elif k.grade == "AMBER":
                actions.append(ActionItem(
                    priority=2, category="자본/유동성",
                    description=f"[{k.name}] mgmt 한계 침범 — 에스컬레이션 절차 개시.",
                    owner=k.category + " 담당", timeline="2주 이내",
                    citation=k.citation,
                ))

    # ── Validation failures
    for c in result.validation.checks:
        if c.status == "FAIL":
            actions.append(ActionItem(
                priority=1, category="검증",
                description=f"[{c.name}] {c.detail}",
                owner="산출 담당", timeline="즉시", citation="감독세칙 자체검증",
                blocking=True,
            ))
        elif c.status == "WARN":
            actions.append(ActionItem(
                priority=3, category="검증",
                description=f"[{c.name}] {c.detail}",
                owner="산출 담당", timeline="다음 산출 주기",
                citation="감독세칙 자체검증",
            ))

    # ── Reverse stress
    rs = result.reverse_stress
    if rs.critical_severity < 1.5:
        actions.append(ActionItem(
            priority=2, category="스트레스",
            description=(f"역스트레스 임계 심도 s={rs.critical_severity:.2f} "
                         f"(GDP {rs.implied_gdp_shock*100:+.1f}%). 자본 확충 검토."),
            owner="CRO", timeline="1개월 이내",
            citation="감독세칙 스트레스테스트",
        ))

    # ── Stress severe path failures
    sev = result.stress[result.stress["scenario"] == "severely_adverse"]
    if len(sev) and not bool(sev["passes"].iloc[0]):
        actions.append(ActionItem(
            priority=2, category="스트레스",
            description=("severely adverse 시나리오에서 CET1 임계 미달. "
                         "AT1/T2 발행 또는 RWA 축소 계획 수립."),
            owner="ALM + Capital Planning", timeline="2개월 이내",
            citation="Basel III RBC20.1",
        ))

    # sort priority asc (1 = most urgent)
    actions.sort(key=lambda a: a.priority)
    return actions
