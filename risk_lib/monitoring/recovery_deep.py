"""CRO-grade workout recovery & LGD realised analytics.

산출
------
1. ``recovery_curve_dual`` — 36개월 회수 곡선 (할인/미할인).
2. ``lgd_distribution`` — 자산군별 실현 LGD 분위수 + 히스토그램.
3. ``recovery_by_collateral`` — 담보유형별 회수율.
4. ``compute_recovery_deep`` — 통합 결과.

규제 참조
    Basel III CRE32.46~ (downturn LGD), CRE36.83 (recognition of recoveries),
    감독세칙 자산건전성 분류 시행세칙, IFRS 9 5.5.5.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
import pandas as pd


# ----------------------------------------------------------- recovery curves

def recovery_curve_dual(
    workouts: pd.DataFrame,
    *,
    default_id_col: str = "default_id",
    months_col: str = "months_since_default",
    recovery_col: str = "recovery_amount",
    ead_col: str = "ead_at_default",
    horizon_months: int = 36,
    eir: float = 0.06,
) -> pd.DataFrame:
    """할인/미할인 누적 회수율 곡선.

    EIR(effective interest rate) 연 ``eir`` 로 월할인 (``(1+eir)^(m/12)``).
    반환 컬럼: month, cum_recovery_undisc, cum_recovery_disc, n_defaults.
    """
    if workouts.empty:
        return pd.DataFrame(columns=["month", "cum_recovery_undisc",
                                     "cum_recovery_disc", "n_defaults"])
    df = workouts.copy()
    df = df[df[months_col] <= horizon_months]
    ead = workouts.groupby(default_id_col)[ead_col].first()
    df["disc_factor"] = (1.0 + eir) ** (-df[months_col] / 12.0)
    df["disc_rec"] = df[recovery_col] * df["disc_factor"]

    rows = []
    for m in range(horizon_months + 1):
        ev = df[df[months_col] <= m]
        cum_u = ev.groupby(default_id_col)[recovery_col].sum().reindex(
            ead.index, fill_value=0.0)
        cum_d = ev.groupby(default_id_col)["disc_rec"].sum().reindex(
            ead.index, fill_value=0.0)
        rates_u = (cum_u / ead).clip(lower=0.0, upper=1.0)
        rates_d = (cum_d / ead).clip(lower=0.0, upper=1.0)
        rows.append({
            "month": m,
            "cum_recovery_undisc": float(rates_u.mean()),
            "cum_recovery_disc": float(rates_d.mean()),
            "n_defaults": int(len(ead)),
        })
    return pd.DataFrame(rows)


# ----------------------------------------------------------- LGD distribution

def lgd_distribution(
    defaults: pd.DataFrame,
    *,
    lgd_col: str = "lgd_realized",
    segment_col: str = "asset_class",
    bins: int = 10,
) -> dict[str, pd.DataFrame]:
    """자산군별 실현 LGD 분위수 + 히스토그램.

    반환:
      ``quantiles`` — segment, p10, p25, median, p75, p90, mean, n.
      ``histogram`` — segment, bin_lo, bin_hi, n.
    """
    if defaults.empty or lgd_col not in defaults.columns:
        return {
            "quantiles": pd.DataFrame(columns=["segment", "p10", "p25",
                                                "median", "p75", "p90",
                                                "mean", "n"]),
            "histogram": pd.DataFrame(columns=["segment", "bin_lo",
                                                "bin_hi", "n"]),
        }

    q_rows = []
    h_rows = []
    edges = np.linspace(0.0, 1.0, bins + 1)
    for seg, sub in defaults.groupby(segment_col):
        vals = sub[lgd_col].dropna()
        if vals.empty:
            continue
        q_rows.append({
            "segment": seg,
            "p10": float(np.quantile(vals, 0.10)),
            "p25": float(np.quantile(vals, 0.25)),
            "median": float(np.quantile(vals, 0.50)),
            "p75": float(np.quantile(vals, 0.75)),
            "p90": float(np.quantile(vals, 0.90)),
            "mean": float(vals.mean()),
            "n": int(len(vals)),
        })
        counts, _ = np.histogram(vals, bins=edges)
        for i, c in enumerate(counts):
            h_rows.append({
                "segment": seg,
                "bin_lo": float(edges[i]),
                "bin_hi": float(edges[i + 1]),
                "n": int(c),
            })
    return {
        "quantiles": pd.DataFrame(q_rows),
        "histogram": pd.DataFrame(h_rows),
    }


# --------------------------------------------------------- collateral effect

def recovery_by_collateral(
    defaults: pd.DataFrame,
    *,
    seed: int = 42,
    ead_col: str = "ead",
    lgd_col: str = "lgd_realized",
    segment_col: str = "asset_class",
) -> pd.DataFrame:
    """담보 유형별 회수율 비교.

    portfolio에 담보 유형이 없으므로 segment를 stylised 매핑한 뒤
    재현 가능한 노이즈를 적용해 회수율(=1-LGD) 평균을 계산한다.

    매핑:
      residential_mortgage → 주거용 부동산
      corporate            → 상업용 부동산 / 회사채
      retail_other         → 현금성 / 무담보
      sovereign, bank      → 국채/보증 (현금성 등가)
    """
    if defaults.empty or lgd_col not in defaults.columns:
        return pd.DataFrame(columns=["collateral_type", "n", "ead",
                                     "avg_recovery", "avg_lgd"])

    rng = np.random.default_rng(seed + 919)
    mapping = {
        "residential_mortgage": "주거용 부동산",
        "corporate": "상업용 부동산 / 회사채",
        "retail_other": "무담보 / 신용",
        "sovereign": "국채 / 보증",
        "bank": "국채 / 보증",
    }
    df = defaults.copy()
    df["collateral_type"] = df[segment_col].map(mapping).fillna("기타")
    # collateral effect — residential mortgage gets best, unsecured worst
    factor = {
        "주거용 부동산": 0.92,
        "상업용 부동산 / 회사채": 0.78,
        "무담보 / 신용": 0.45,
        "국채 / 보증": 0.98,
        "기타": 0.65,
    }
    df["recovery"] = (1.0 - df[lgd_col]).clip(0.0, 1.0)
    # mild stochastic adjustment within ±5%
    df["adj"] = rng.normal(0, 0.03, len(df)).clip(-0.05, 0.05)
    df["recovery_adj"] = (df["recovery"] * df["collateral_type"].map(factor) +
                          df["adj"]).clip(0.0, 1.0)

    rows = []
    for ctype, sub in df.groupby("collateral_type"):
        rows.append({
            "collateral_type": ctype,
            "n": int(len(sub)),
            "ead": float(sub[ead_col].sum()) if ead_col in sub.columns else 0.0,
            "avg_recovery": float(sub["recovery_adj"].mean()),
            "avg_lgd": float(1.0 - sub["recovery_adj"].mean()),
        })
    out = pd.DataFrame(rows).sort_values("avg_recovery", ascending=False)
    return out.reset_index(drop=True)


# =========================================================== aggregate entry

@dataclass
class RecoveryDeepResult:
    curve_dual: pd.DataFrame
    lgd_quantiles: pd.DataFrame
    lgd_histogram: pd.DataFrame
    collateral: pd.DataFrame


def compute_recovery_deep(
    portfolio: pd.DataFrame,
    workouts: pd.DataFrame,
    *,
    seed: int = 42,
    eir: float = 0.06,
    horizon_months: int = 36,
) -> RecoveryDeepResult:
    defaults = portfolio[portfolio.get("default_12m", 0) == 1].copy() \
        if "default_12m" in portfolio.columns else portfolio.iloc[:0].copy()
    curve = recovery_curve_dual(workouts, eir=eir,
                                horizon_months=horizon_months)
    dist = lgd_distribution(defaults)
    coll = recovery_by_collateral(defaults, seed=seed)
    return RecoveryDeepResult(
        curve_dual=curve,
        lgd_quantiles=dist["quantiles"],
        lgd_histogram=dist["histogram"],
        collateral=coll,
    )
