"""Vintage analysis and rating-grade transition matrices.

Standard credit-portfolio diagnostics:
  - vintage_default_curve: cumulative default rate by months-on-book per
    origination cohort
  - rating_transition_matrix: Markov-style 1-year grade migration matrix
    estimated from a snapshot (origination grade → current grade)
  - migration_summary: aggregated upgrade / downgrade / default / withdrawn

Synthesises monthly cohorts from the static portfolio for visualisation —
real implementations would plug actual origination month + grade history.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class VintageResult:
    cohorts: pd.DataFrame              # cohort_month, n, mob, cum_default_rate
    summary: pd.DataFrame              # cohort_month, n, peak_default_rate, peak_mob


@dataclass
class TransitionResult:
    matrix: pd.DataFrame                # square matrix: rows=from, cols=to
    n_obs: int
    summary: dict[str, float]           # upgrade%, downgrade%, default%, stable%


# ---------------------------------------------------------------- vintage

def synthesise_vintage(portfolio: pd.DataFrame, *, n_cohorts: int = 24,
                       seed: int = 42) -> pd.DataFrame:
    """Assign each exposure to a synthetic origination month, then build
    cohort-month × MOB cumulative default rate table.

    Cohorts have systematically different PD (older cohorts have seasoned out
    of early defaults; newer cohorts haven't yet revealed risk) so the curves
    are visually distinct.
    """
    rng = np.random.default_rng(seed + 401)
    n = len(portfolio)
    # uniform cohort assignment (latest cohort = 0 months ago, oldest = 24)
    cohort_idx = rng.integers(0, n_cohorts, n)
    # each cohort has a different baseline PD bump driven by latent macro
    cohort_factor = 0.85 + 0.4 * rng.beta(2, 2, n_cohorts)   # 0.85~1.25 mult
    pd_base = portfolio["pd"].fillna(0.01).to_numpy(dtype=float)
    pd_eff = pd_base * cohort_factor[cohort_idx]

    rows = []
    for c in range(n_cohorts):
        mask = cohort_idx == c
        n_c = int(mask.sum())
        if n_c == 0: continue
        for mob in range(1, n_cohorts - c + 1):
            # cumulative survival = (1 - PD_monthly)^mob; PD_monthly ≈ PD_12m / 12
            pd_m = np.clip(pd_eff[mask] / 12.0, 0, 0.99)
            cum_def_rate = float(np.mean(1 - (1 - pd_m) ** mob))
            rows.append({"cohort": c, "cohort_month": f"M-{c}",
                         "mob": mob, "n": n_c,
                         "cum_default_rate": cum_def_rate})
    return pd.DataFrame(rows)


def build_vintage(portfolio: pd.DataFrame, *, n_cohorts: int = 24,
                  seed: int = 42) -> VintageResult:
    co = synthesise_vintage(portfolio, n_cohorts=n_cohorts, seed=seed)
    if co.empty:
        return VintageResult(pd.DataFrame(), pd.DataFrame())
    summary = co.groupby("cohort_month").agg(
        n=("n", "first"),
        peak_default_rate=("cum_default_rate", "max"),
        peak_mob=("mob", "max"),
    ).reset_index().sort_values("cohort_month")
    return VintageResult(cohorts=co, summary=summary)


# ---------------------------------------------------------------- transitions

def synthesise_transitions(portfolio: pd.DataFrame, *,
                           grades: list[str] | None = None,
                           seed: int = 42) -> pd.DataFrame:
    """Build a from→to grade migration table over a 1-year horizon by
    re-rating each exposure with a noisy version of its PD and mapping back
    to the master scale.

    With no time-series data this is a stylised but reasonable proxy —
    obligors with PD near a grade boundary migrate stochastically.
    """
    if grades is None:
        # try to read default master scale
        from risk_lib.models.rating import DEFAULT_MASTER_SCALE
        grades = [g.grade for g in DEFAULT_MASTER_SCALE]

    # Restrict to rows with grade + pd
    df = portfolio[portfolio["grade"].notna() & portfolio["pd"].notna()].copy()
    if df.empty: return pd.DataFrame()
    rng = np.random.default_rng(seed + 555)
    # bump PD by a lognormal noise; re-rate
    log_pd = np.log(df["pd"].clip(1e-6, 0.99))
    new_log_pd = log_pd + rng.normal(0, 0.5, len(df))
    new_pd = np.clip(np.exp(new_log_pd), 1e-6, 0.99)

    from risk_lib.models.rating import pd_to_rating
    new_grades = [pd_to_rating(p).grade for p in new_pd]

    df["new_grade"] = new_grades
    # Add "D" (default) where new_pd exceeds a hard threshold
    df.loc[df["default_12m"] == 1, "new_grade"] = "D"
    return df[["grade", "new_grade"]]


def transition_matrix(portfolio: pd.DataFrame, *,
                      grades: list[str] | None = None,
                      seed: int = 42) -> TransitionResult:
    """Compute the row-normalised transition matrix."""
    if grades is None:
        from risk_lib.models.rating import DEFAULT_MASTER_SCALE
        grades = [g.grade for g in DEFAULT_MASTER_SCALE]
    all_grades = list(grades) + ["D"]
    pairs = synthesise_transitions(portfolio, grades=grades, seed=seed)
    if pairs.empty:
        return TransitionResult(pd.DataFrame(), 0, {})
    mat = pd.crosstab(pairs["grade"], pairs["new_grade"])
    # reindex to a stable grade order
    mat = mat.reindex(index=grades, columns=all_grades, fill_value=0)
    n_obs = int(mat.sum().sum())
    # row-normalise
    row_sums = mat.sum(axis=1).replace(0, 1)
    pct = mat.div(row_sums, axis=0)

    # summary
    diag = float(sum(pct.loc[g, g] for g in grades if g in pct.columns) / len(grades))
    upgrade = 0.0; downgrade = 0.0; default = 0.0
    for i, g in enumerate(grades):
        for j, g2 in enumerate(all_grades):
            v = float(pct.loc[g, g2])
            if g2 == "D": default += v / len(grades)
            elif j < i:    upgrade += v / len(grades)
            elif j > i:    downgrade += v / len(grades)
    summary = {"stable": diag, "upgrade": upgrade,
               "downgrade": downgrade, "default": default}
    return TransitionResult(matrix=pct, n_obs=n_obs, summary=summary)
