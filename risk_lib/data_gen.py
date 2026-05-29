"""Synthetic portfolio generator for demo / tests.

Deterministic with seed.  Generates obligor-level data with realistic feature
distributions and a default flag whose rate increases monotonically with risk
features — so the PD model has signal to learn.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def generate_portfolio(
    n_corporate: int = 800,
    n_retail: int = 1500,
    n_mortgage: int = 600,
    n_sovereign: int = 30,
    n_bank: int = 50,
    seed: int = 42,
) -> pd.DataFrame:
    """Return obligor/exposure level dataframe used across modules.

    Columns:
      exposure_id, obligor_id, asset_class, sector, country, ead, maturity,
      rating, pd, lgd, ltv, past_due, dpd, balance,
      leverage, current_ratio, log_assets, interest_coverage, gdp_growth,
      default_12m, lgd_realized, revenue, operating_cost
    """
    rng = np.random.default_rng(seed)
    parts: list[pd.DataFrame] = []

    sectors_corp = ["manufacturing", "construction", "shipping", "tech",
                    "real_estate", "energy", "retail_trade"]
    countries = ["KR", "KR", "KR", "US", "JP", "CN", "VN"]
    ratings_sov = ["AAA-AA", "A", "BBB", "BB"]
    ratings_bank = ["AAA-AA", "A", "BBB", "BB"]

    # --- corporate (IRB)
    if n_corporate:
        leverage = rng.normal(2.0, 1.2, n_corporate).clip(0.1, 8)
        current = rng.normal(1.4, 0.5, n_corporate).clip(0.3, 3.5)
        log_assets = rng.normal(11.0, 1.5, n_corporate)
        icr = rng.normal(3.5, 2.0, n_corporate).clip(-2, 15)
        gdp = rng.normal(0.025, 0.01, n_corporate)
        latent = (-3.0 + 0.45 * leverage - 0.6 * current - 0.15 * log_assets
                  - 0.12 * icr - 8 * gdp + rng.normal(0, 0.6, n_corporate))
        pd_true = _sigmoid(latent).clip(0.0005, 0.9)
        default = (rng.random(n_corporate) < pd_true).astype(int)
        lgd_real = np.clip(rng.beta(2, 3, n_corporate) + 0.05, 0.05, 0.95)
        ead = rng.lognormal(mean=np.log(5_000_000_000 / 1e9), sigma=1.0, size=n_corporate) * 1e9
        mat = rng.uniform(1.0, 5.0, n_corporate)
        df = pd.DataFrame({
            "exposure_id": [f"CORP_{i:05d}" for i in range(n_corporate)],
            "obligor_id":  [f"OBL_CORP_{i:05d}" for i in range(n_corporate)],
            "asset_class": "corporate",
            "sector": rng.choice(sectors_corp, n_corporate),
            "country": rng.choice(countries, n_corporate),
            "ead": ead,
            "maturity": mat,
            "leverage": leverage,
            "current_ratio": current,
            "log_assets": log_assets,
            "interest_coverage": icr,
            "gdp_growth": gdp,
            "pd": pd_true,
            "lgd": lgd_real * 0.9 + 0.05,   # modelled LGD
            "ltv": np.nan,
            "default_12m": default,
            "lgd_realized": lgd_real,
        })
        parts.append(df)

    # --- retail regulatory
    if n_retail:
        dti = rng.normal(0.35, 0.15, n_retail).clip(0.05, 1.2)
        utilization = rng.beta(2, 5, n_retail)
        income_log = rng.normal(10.5, 0.6, n_retail)
        months_employed = rng.normal(60, 36, n_retail).clip(0, 480)
        latent = (-2.5 + 3.0 * dti + 2.5 * utilization - 0.4 * (income_log - 10)
                  - 0.005 * months_employed + rng.normal(0, 0.6, n_retail))
        pd_true = _sigmoid(latent).clip(0.001, 0.6)
        default = (rng.random(n_retail) < pd_true).astype(int)
        lgd_real = np.clip(rng.beta(3, 2, n_retail), 0.2, 0.95)
        ead = rng.lognormal(mean=np.log(30_000_000 / 1e6), sigma=0.7, size=n_retail) * 1e6
        df = pd.DataFrame({
            "exposure_id": [f"RTL_{i:05d}" for i in range(n_retail)],
            "obligor_id":  [f"OBL_RTL_{i:05d}" for i in range(n_retail)],
            "asset_class": "retail_other",
            "sector": "household",
            "country": "KR",
            "ead": ead,
            "maturity": 1.0,
            "leverage": np.nan, "current_ratio": np.nan, "log_assets": np.nan,
            "interest_coverage": np.nan, "gdp_growth": np.nan,
            "dti": dti, "utilization": utilization, "income_log": income_log,
            "months_employed": months_employed,
            "pd": pd_true,
            "lgd": lgd_real * 0.9 + 0.05,
            "ltv": np.nan,
            "default_12m": default,
            "lgd_realized": lgd_real,
        })
        parts.append(df)

    # --- residential mortgage
    if n_mortgage:
        ltv = rng.normal(0.65, 0.15, n_mortgage).clip(0.2, 1.05)
        dti = rng.normal(0.30, 0.10, n_mortgage).clip(0.05, 0.8)
        latent = -4.0 + 2.5 * ltv + 2.0 * dti + rng.normal(0, 0.5, n_mortgage)
        pd_true = _sigmoid(latent).clip(0.0005, 0.3)
        default = (rng.random(n_mortgage) < pd_true).astype(int)
        ead = rng.lognormal(mean=np.log(250_000_000 / 1e6), sigma=0.5, size=n_mortgage) * 1e6
        lgd_real = np.clip(rng.beta(2, 6, n_mortgage), 0.05, 0.6)
        df = pd.DataFrame({
            "exposure_id": [f"MTG_{i:05d}" for i in range(n_mortgage)],
            "obligor_id":  [f"OBL_MTG_{i:05d}" for i in range(n_mortgage)],
            "asset_class": "residential_mortgage",
            "sector": "household",
            "country": "KR",
            "ead": ead,
            "maturity": 20.0,
            "leverage": np.nan, "current_ratio": np.nan, "log_assets": np.nan,
            "interest_coverage": np.nan, "gdp_growth": np.nan,
            "ltv": ltv, "dti": dti,
            "pd": pd_true,
            "lgd": lgd_real * 0.9 + 0.05,
            "default_12m": default,
            "lgd_realized": lgd_real,
        })
        parts.append(df)

    # --- sovereign (SA only)
    if n_sovereign:
        df = pd.DataFrame({
            "exposure_id": [f"SOV_{i:04d}" for i in range(n_sovereign)],
            "obligor_id":  [f"OBL_SOV_{i:04d}" for i in range(n_sovereign)],
            "asset_class": "sovereign",
            "sector": "government",
            "country": rng.choice(countries, n_sovereign),
            "ead": rng.lognormal(mean=np.log(50_000_000_000 / 1e9), sigma=0.7,
                                 size=n_sovereign) * 1e9,
            "maturity": rng.uniform(1, 10, n_sovereign),
            "rating": rng.choice(ratings_sov, n_sovereign, p=[0.5, 0.3, 0.15, 0.05]),
            "pd": np.nan, "lgd": np.nan, "ltv": np.nan,
            "default_12m": 0, "lgd_realized": 0.0,
        })
        parts.append(df)

    # --- bank (SA only here)
    if n_bank:
        df = pd.DataFrame({
            "exposure_id": [f"BNK_{i:04d}" for i in range(n_bank)],
            "obligor_id":  [f"OBL_BNK_{i:04d}" for i in range(n_bank)],
            "asset_class": "bank",
            "sector": "financial",
            "country": rng.choice(countries, n_bank),
            "ead": rng.lognormal(mean=np.log(20_000_000_000 / 1e9), sigma=0.8,
                                 size=n_bank) * 1e9,
            "maturity": rng.uniform(0.5, 5.0, n_bank),
            "rating": rng.choice(ratings_bank, n_bank, p=[0.35, 0.4, 0.2, 0.05]),
            "pd": np.nan, "lgd": np.nan, "ltv": np.nan,
            "default_12m": 0, "lgd_realized": 0.0,
        })
        parts.append(df)

    full = pd.concat(parts, ignore_index=True, sort=False)

    # Derived ops columns
    rng2 = np.random.default_rng(seed + 1)
    n = len(full)
    full["past_due"] = False
    # mark some past_due based on default flag with noise
    full.loc[(full["default_12m"] == 1) & (rng2.random(n) < 0.7), "past_due"] = True
    full["dpd"] = 0
    dlq_mask = rng2.random(n) < 0.05
    full.loc[dlq_mask, "dpd"] = rng2.integers(1, 89, dlq_mask.sum())
    full.loc[full["past_due"], "dpd"] = rng2.integers(90, 360, full["past_due"].sum())
    full["balance"] = full["ead"]
    # P&L for RAPM (only for credit-bearing classes with pd)
    spread = np.where(full["asset_class"] == "corporate", 0.025,
              np.where(full["asset_class"] == "retail_other", 0.055,
              np.where(full["asset_class"] == "residential_mortgage", 0.018, 0.008)))
    full["revenue"] = full["ead"] * spread
    full["operating_cost"] = full["ead"] * 0.005

    # SA rating fallback for non-rated SA classes (corp/retail/mortgage use IRB)
    if "rating" not in full.columns:
        full["rating"] = "UNRATED"
    full["rating"] = full["rating"].fillna("UNRATED")
    return full


def split_train_test(
    df: pd.DataFrame, test_frac: float = 0.3, seed: int = 7,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    mask = rng.random(len(df)) < (1.0 - test_frac)
    return df[mask].reset_index(drop=True), df[~mask].reset_index(drop=True)


def generate_workout_cashflows(
    portfolio: pd.DataFrame, seed: int = 11,
) -> pd.DataFrame:
    """Generate per-default monthly recovery cashflows for the recovery module."""
    rng = np.random.default_rng(seed)
    defaults = portfolio[portfolio["default_12m"] == 1].copy()
    rows = []
    for _, r in defaults.iterrows():
        lgd = r["lgd_realized"]
        total_rec = r["ead"] * (1 - lgd)
        # spread over 36 months following decaying pattern
        weights = rng.dirichlet(np.ones(36) * 0.8)
        for m, w in enumerate(weights, start=1):
            rows.append({
                "default_id": r["exposure_id"],
                "months_since_default": m,
                "recovery_amount": float(total_rec * w),
                "ead_at_default": float(r["ead"]),
            })
    return pd.DataFrame(rows)
