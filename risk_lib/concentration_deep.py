"""Concentration deep-dive — exposure-level drill-down.

Outputs:
  - top_n_obligors: top 20 by EAD with PD/LGD/EL/grade/sector/country
  - top_n_at_risk: top 20 by EAD × PD (potential default contribution)
  - sector_country_matrix: heatmap-ready cross-tab
  - large_exposure_test: 동일차주 한도(은행법 §35) 차주별 잉여/위반
  - granularity_adjustment: Gordy granularity addon estimate

v0.11.0 additions:
  - hierarchical_hhi: 차주/그룹/섹터/KSIC2/국가/상품/만기 HHI 계층
  - top_n_share_table: 상위 5/10/20 차주 비중
  - lorenz_curve / gini_coefficient: 노출집중도 비대칭성
  - wrong_way_correlation: 차주 × 담보 corr (시나리오)
  - sector_systemic_correlation: 섹터간 자산상관 (BIS-style)
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def top_obligors(portfolio: pd.DataFrame, n: int = 20,
                 by: str = "ead") -> pd.DataFrame:
    """Top-N obligors aggregated by chosen metric (ead | el | risk_score)."""
    work = portfolio.copy()
    if "pd" in work.columns and "lgd" in work.columns:
        work["el"] = work["pd"] * work["lgd"] * work["ead"]
        work["risk_score"] = work["pd"] * work["ead"]
    g = work.groupby("obligor_id").agg(
        ead=("ead", "sum"),
        pd_avg=("pd", "mean"),
        lgd_avg=("lgd", "mean"),
        el=("el", "sum") if "el" in work.columns else ("ead", lambda s: 0),
        risk_score=("risk_score", "sum") if "risk_score" in work.columns else ("ead", lambda s: 0),
        sector=("sector", lambda s: s.iloc[0]),
        country=("country", lambda s: s.iloc[0]),
        asset_class=("asset_class", lambda s: s.iloc[0]),
        n_exposures=("exposure_id", "count"),
    ).reset_index()
    return g.nlargest(n, by)


def sector_country_matrix(portfolio: pd.DataFrame) -> pd.DataFrame:
    """Cross-tab of EAD by (sector, country)."""
    return portfolio.pivot_table(
        index="sector", columns="country", values="ead",
        aggfunc="sum", fill_value=0,
    )


def large_exposure_test(portfolio: pd.DataFrame, tier1: float,
                        limit_pct: float = 0.25) -> pd.DataFrame:
    """동일차주 한도 (은행법 §35) 차주별 사용률.

    Returns: obligor_id, ead, threshold, utilisation, severity (1행/차주).
    """
    threshold = tier1 * limit_pct
    g = portfolio.groupby("obligor_id")["ead"].sum().reset_index()
    g["threshold"] = threshold
    g["utilisation"] = g["ead"] / threshold
    def sev(u):
        if u >= 1.0:      return "BREACH"
        if u >= 0.90:     return "CRITICAL"
        if u >= 0.75:     return "WARN"
        return "OK"
    g["severity"] = g["utilisation"].apply(sev)
    return g.sort_values("ead", ascending=False)


def granularity_addon(portfolio: pd.DataFrame) -> float:
    """Gordy-style single-obligor granularity addon (simplified).

    GA ≈ K · HHI(obligor)  (Gordy 2003; we use the obligor HHI as the
    granularity proxy.  At very high N this collapses to ~0 quickly.)
    """
    s = portfolio.groupby("obligor_id")["ead"].sum()
    w = s / s.sum()
    hhi = float((w ** 2).sum())
    # K depends on the Vasicek model parameters; we use a flat coefficient
    # calibrated so a single-obligor book (HHI=1) gets a ~5% addon.
    return float(0.05 * hhi)


# =========================================================================
# v0.11.0 — CRO-grade concentration deep-dive additions
# =========================================================================

# Synthetic KSIC 2-digit code mapping from sector (간이).  실 환경에서는
# 차주마스터의 KSIC 코드를 사용한다.
_KSIC2_MAP = {
    "manufacturing": "C10-33",
    "construction":  "F41-42",
    "shipping":      "H49-52",
    "tech":          "J58-63",
    "real_estate":   "L68",
    "energy":        "D35",
    "retail_trade":  "G45-47",
    "household":     "T97-98",
    "financial":     "K64-66",
    "government":    "O84",
}


def _hhi_value(series: pd.Series) -> tuple[float, float, int, float]:
    """Return (hhi, normalised_hhi, n_buckets, top1_share)."""
    s = pd.to_numeric(series, errors="coerce").fillna(0)
    s = s[s > 0]
    total = float(s.sum())
    if total <= 0 or len(s) == 0:
        return 0.0, 0.0, 0, 0.0
    n = int(len(s))
    w = s / total
    h = float((w * w).sum())
    n_hhi = (h - 1 / n) / (1 - 1 / n) if n > 1 else 1.0
    return h, float(n_hhi), n, float(w.max())


def hierarchical_hhi(
    portfolio: pd.DataFrame, *, exposure_col: str = "ead",
) -> pd.DataFrame:
    """차원 계층 HHI — 차주/그룹/섹터/KSIC2/국가/상품/만기 일괄.

    portfolio에 ``obligor_group_id``/``product_type``/``maturity_bucket``/
    ``ksic2``가 없으면 합성한다.
    """
    work = portfolio.copy()
    if "obligor_group_id" not in work.columns:
        from risk_lib.limits.limits_deep import group_obligor_id
        work["obligor_group_id"] = work["obligor_id"].map(group_obligor_id)
    if "ksic2" not in work.columns:
        work["ksic2"] = work["sector"].map(_KSIC2_MAP).fillna("기타")
    if "product_type" not in work.columns:
        from risk_lib.limits.limits_deep import attach_product_type
        work = attach_product_type(work)
    if "maturity_bucket" not in work.columns:
        from risk_lib.limits.limits_deep import attach_maturity_bucket
        work = attach_maturity_bucket(work)

    dims = [
        ("obligor_id", "차주"),
        ("obligor_group_id", "그룹차주"),
        ("sector", "섹터"),
        ("ksic2", "KSIC 2자리"),
        ("country", "국가"),
        ("product_type", "상품"),
        ("maturity_bucket", "만기"),
    ]
    rows = []
    for col, label in dims:
        if col not in work.columns:
            continue
        grp = work.groupby(col)[exposure_col].sum()
        h, n_h, n, top = _hhi_value(grp)
        rows.append({
            "dimension": col, "label": label,
            "n_buckets": n, "hhi": h, "normalised_hhi": n_h,
            "top1_share": top,
        })
    return pd.DataFrame(rows)


def top_n_share_table(
    portfolio: pd.DataFrame, *,
    keys: tuple[str, ...] = ("obligor_id", "obligor_group_id", "sector"),
    ns: tuple[int, ...] = (5, 10, 20),
    exposure_col: str = "ead",
) -> pd.DataFrame:
    """차원별 상위 N (5/10/20) 누적 비중.

    Returns: (dimension, top_5_share, top_10_share, top_20_share, n_total).
    """
    work = portfolio.copy()
    if "obligor_group_id" in keys and "obligor_group_id" not in work.columns:
        from risk_lib.limits.limits_deep import group_obligor_id
        work["obligor_group_id"] = work["obligor_id"].map(group_obligor_id)
    rows = []
    for key in keys:
        if key not in work.columns:
            continue
        s = work.groupby(key)[exposure_col].sum().sort_values(ascending=False)
        total = float(s.sum())
        row = {"dimension": key, "n_total": int(len(s))}
        for n in ns:
            row[f"top_{n}_share"] = (
                float(s.iloc[:n].sum() / total) if total > 0 else 0.0
            )
        rows.append(row)
    return pd.DataFrame(rows)


def gini_coefficient(values: np.ndarray | pd.Series) -> float:
    """Gini coefficient (0 = 완전분산, 1 = 단일집중).

    For an array of non-negative exposures.
    """
    v = np.asarray(pd.Series(values).dropna(), dtype=float)
    v = v[v >= 0]
    if v.size == 0 or v.sum() <= 0:
        return 0.0
    v = np.sort(v)
    n = v.size
    cum = np.cumsum(v)
    # standard formula: G = (2 Σ i x_i) / (n Σ x_i) - (n+1)/n
    idx = np.arange(1, n + 1)
    return float((2 * (idx * v).sum()) / (n * v.sum()) - (n + 1) / n)


def lorenz_curve(
    values: np.ndarray | pd.Series, *, n_points: int = 21,
) -> pd.DataFrame:
    """Lorenz curve points (cum_pop_share, cum_value_share).

    Used by viz to draw concentration curve vs 45° equality line.
    """
    v = np.asarray(pd.Series(values).dropna(), dtype=float)
    v = v[v >= 0]
    if v.size == 0 or v.sum() <= 0:
        return pd.DataFrame({"cum_pop": [0, 1], "cum_value": [0, 1]})
    v = np.sort(v)
    total = v.sum()
    cum = np.concatenate(([0], np.cumsum(v) / total))
    pop = np.linspace(0, 1, len(cum))
    # resample to n_points for stable plotting
    pts = np.linspace(0, 1, n_points)
    cum_val = np.interp(pts, pop, cum)
    return pd.DataFrame({"cum_pop": pts, "cum_value": cum_val})


def wrong_way_correlation(
    portfolio: pd.DataFrame, *, seed: int = 42,
) -> pd.DataFrame:
    """차주 부도와 담보가치 동시 하락 시나리오 (wrong-way risk).

    Synthetic: 섹터별로 가정된 자산-부도 상관계수 (ρ_PD,LGD)를 부여한 후,
    EAD-가중 wrong-way uplift를 LGD downturn으로 환산.

    Returns long-form: sector, rho_pd_lgd, ead, downturn_lgd_uplift,
    ead_weighted_uplift (조원).
    """
    rng = np.random.default_rng(seed)
    base_rho = {
        "real_estate":   0.55,   # 부동산 가격하락 ↔ 부동산PF 부도
        "construction":  0.45,
        "shipping":      0.40,   # 선박 담보가 sector cycle에 의존
        "manufacturing": 0.30,
        "energy":        0.35,
        "tech":          0.20,
        "retail_trade":  0.25,
        "household":     0.30,   # 주택가격 ↔ 모기지
        "financial":     0.35,
        "government":    0.10,
    }
    if "sector" not in portfolio.columns:
        return pd.DataFrame(columns=[
            "sector", "rho_pd_lgd", "ead",
            "downturn_lgd_uplift", "ead_weighted_uplift"])
    rows = []
    for sec, group in portfolio.groupby("sector"):
        rho = base_rho.get(sec, 0.25) + float(rng.normal(0, 0.03))
        rho = max(0.0, min(rho, 0.80))
        ead = float(group["ead"].sum())
        # downturn LGD uplift = ρ * 0.25 (BCBS LGD downturn floor 가정의 단순화)
        lgd_uplift = rho * 0.25
        rows.append({
            "sector": sec, "rho_pd_lgd": rho, "ead": ead,
            "downturn_lgd_uplift": lgd_uplift,
            "ead_weighted_uplift": ead * lgd_uplift,
        })
    out = pd.DataFrame(rows).sort_values("ead_weighted_uplift", ascending=False)
    return out.reset_index(drop=True)


# 섹터간 자산상관 (synthetic BIS-style asset correlation matrix).
# 같은 macro driver에 노출된 섹터는 높은 상관, 그 외는 낮은 상관.
_SECTOR_CORR_PAIRS = {
    ("real_estate", "construction"): 0.75,
    ("real_estate", "household"):    0.55,
    ("construction", "manufacturing"): 0.45,
    ("manufacturing", "shipping"):   0.55,
    ("shipping", "energy"):          0.50,
    ("manufacturing", "energy"):     0.45,
    ("tech", "manufacturing"):       0.40,
    ("retail_trade", "household"):   0.50,
    ("financial", "real_estate"):    0.55,
    ("financial", "construction"):   0.40,
    ("government", "financial"):     0.30,
}


def sector_systemic_correlation(
    portfolio: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """섹터간 자산상관 행렬 (synthetic) — wrong-way / 동조부도 분석용.

    Returns a square DataFrame indexed/columned by sector.
    """
    if portfolio is not None and "sector" in portfolio.columns:
        sectors = sorted(portfolio["sector"].dropna().unique().tolist())
    else:
        sectors = sorted(set(s for pair in _SECTOR_CORR_PAIRS for s in pair))
    n = len(sectors)
    mat = np.eye(n)
    idx = {s: i for i, s in enumerate(sectors)}
    for (a, b), rho in _SECTOR_CORR_PAIRS.items():
        if a in idx and b in idx:
            mat[idx[a], idx[b]] = rho
            mat[idx[b], idx[a]] = rho
    # weak baseline for any other pair
    for i in range(n):
        for j in range(n):
            if i != j and mat[i, j] == 0:
                mat[i, j] = 0.15
    return pd.DataFrame(mat, index=sectors, columns=sectors)
