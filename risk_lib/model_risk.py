"""Model Risk Management — model cards, drift, challenger comparison.

Aligned with SR 11-7 / 감독원 「모형리스크관리 모범규준」 — every PD/LGD model
the harness produces gets:
  - a Model Card: purpose, segment, features, training window, performance,
    last validation date, owner, status (production / pending review)
  - a Drift report: PSI (population stability index) per feature comparing
    train vs. recent batch
  - a Challenger comparison: same-target retrain with a different feature
    set or a benchmark transformation; report ΔGini, ΔKS
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class ModelCard:
    """SR 11-7 style model card."""
    model_id: str
    purpose: str
    segment: str
    features: list[str]
    train_window: str
    n_train: int
    n_test: int
    performance: dict[str, float]    # gini, ks, hl_p, ks_p
    status: str = "PRODUCTION"        # PRODUCTION | PENDING | RETIRED
    owner: str = "Risk Modelling"
    last_validation: str = field(default_factory=lambda: date.today().isoformat())
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {**self.__dict__}


def psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    """Population Stability Index.

    PSI = Σ (a_i - e_i) · ln(a_i / e_i)
    Standard interpretation: <0.10 stable, 0.10–0.25 minor, >0.25 major.
    """
    expected = np.asarray(expected); actual = np.asarray(actual)
    expected = expected[~np.isnan(expected)]
    actual = actual[~np.isnan(actual)]
    if len(expected) == 0 or len(actual) == 0:
        return float("nan")
    edges = np.quantile(expected, np.linspace(0, 1, bins + 1))
    edges[0] = -np.inf; edges[-1] = np.inf
    e_hist, _ = np.histogram(expected, bins=edges)
    a_hist, _ = np.histogram(actual, bins=edges)
    e = np.clip(e_hist / e_hist.sum(), 1e-6, None)
    a = np.clip(a_hist / a_hist.sum(), 1e-6, None)
    return float(((a - e) * np.log(a / e)).sum())


def drift_report(train: pd.DataFrame, recent: pd.DataFrame,
                 features: list[str]) -> pd.DataFrame:
    """PSI drift across all listed features.

    Returns a frame with status GREEN/AMBER/RED matching industry tiers.
    """
    rows = []
    for f in features:
        if f not in train.columns or f not in recent.columns:
            continue
        val = psi(train[f].to_numpy(dtype=float), recent[f].to_numpy(dtype=float))
        zone = ("GREEN" if val < 0.10 else "AMBER" if val < 0.25 else "RED")
        rows.append({"feature": f, "psi": val, "zone": zone,
                     "n_train": int(train[f].notna().sum()),
                     "n_recent": int(recent[f].notna().sum())})
    return pd.DataFrame(rows)


def challenger_comparison(champion: dict, challenger: dict) -> dict[str, Any]:
    """Compare two performance dicts side by side."""
    keys = sorted(set(champion) | set(challenger))
    return {
        "rows": [{"metric": k,
                  "champion": champion.get(k),
                  "challenger": challenger.get(k),
                  "delta": (challenger.get(k, 0) - champion.get(k, 0))
                           if isinstance(champion.get(k), (int, float)) else None}
                 for k in keys],
        "verdict": ("CHALLENGER" if challenger.get("gini", 0) > champion.get("gini", 0) + 0.01
                    else "CHAMPION"),
    }


def build_model_cards(pd_metrics: dict[str, dict[str, float]],
                      hl: dict[str, float]) -> list[ModelCard]:
    """Promote the PD metrics dict + Hosmer-Lemeshow to a list of model cards."""
    out = []
    feat_map = {
        "corporate": ["leverage", "current_ratio", "log_assets",
                      "interest_coverage", "gdp_growth"],
        "retail_other": ["dti", "utilization", "income_log", "months_employed"],
        "residential_mortgage": ["ltv", "dti", "credit_score", "income_log"],
    }
    for seg, m in pd_metrics.items():
        perf = {"gini": m.get("gini"), "ks": m.get("ks")}
        if seg == "corporate":
            perf["hl_p"] = hl.get("p_value")
        status = "PRODUCTION"
        if (m.get("gini", 0) < 0.20):
            status = "PENDING"
        out.append(ModelCard(
            model_id=f"PD_{seg.upper()}",
            purpose=f"12개월 부도확률 — {seg}",
            segment=seg,
            features=feat_map.get(seg, []),
            train_window="합성 데이터 기준 단일 cohort",
            n_train=int(m.get("n_train", 0)),
            n_test=int(m.get("n_test", 0)),
            performance=perf,
            status=status,
        ))
    return out
