"""Data quality + reconciliation diagnostics.

The CRO's "where did this number come from?" question splits into two:
  - DQ: is the input data clean? — missing values, outliers, schema gaps
  - Reconciliation: does the aggregate tie back to the raw rows?

Both are surfaced as auditable tables in the 실무진 report.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class DQReport:
    schema: pd.DataFrame                 # column, dtype, n_null, pct_null
    numeric: pd.DataFrame                # column, min, p5, median, p95, max, n_outliers
    categorical: pd.DataFrame            # column, n_unique, top, top_count
    flags: list[str] = field(default_factory=list)


def _outlier_count(s: pd.Series, k: float = 3.0) -> int:
    """Count of values beyond mean ± k·std (robust enough for skewed credit data
    when paired with the percentile table)."""
    s = s.dropna()
    if len(s) < 30: return 0
    mu, sigma = float(s.mean()), float(s.std())
    if sigma == 0: return 0
    return int(((s < mu - k * sigma) | (s > mu + k * sigma)).sum())


def dq_report(portfolio: pd.DataFrame) -> DQReport:
    schema_rows = []
    for c in portfolio.columns:
        n_null = int(portfolio[c].isna().sum())
        schema_rows.append({"column": c, "dtype": str(portfolio[c].dtype),
                            "n_null": n_null,
                            "pct_null": n_null / len(portfolio)})
    schema = pd.DataFrame(schema_rows)

    num_rows = []
    for c in portfolio.select_dtypes(include=["float", "int"]).columns:
        s = portfolio[c].dropna()
        if len(s) == 0: continue
        num_rows.append({
            "column": c, "min": float(s.min()),
            "p5": float(s.quantile(0.05)),
            "median": float(s.median()),
            "p95": float(s.quantile(0.95)),
            "max": float(s.max()),
            "n_outliers": _outlier_count(s),
        })
    numeric = pd.DataFrame(num_rows)

    cat_rows = []
    for c in portfolio.select_dtypes(include=["object", "bool"]).columns:
        s = portfolio[c].dropna()
        if len(s) == 0: continue
        vc = s.value_counts()
        cat_rows.append({"column": c, "n_unique": len(vc),
                         "top": str(vc.index[0]), "top_count": int(vc.iloc[0])})
    categorical = pd.DataFrame(cat_rows)

    flags = []
    # core checks
    for col, msg in [("exposure_id", "exposure_id 중복"),
                     ("ead", "EAD 음수"),
                     ("pd", "PD가 [0,1] 밖")]:
        if col not in portfolio.columns: continue
        if col == "exposure_id" and portfolio[col].duplicated().any():
            flags.append(f"FAIL: {msg}")
        if col == "ead" and (portfolio[col] < 0).any():
            flags.append(f"FAIL: {msg}")
        if col == "pd":
            s = portfolio[col].dropna()
            if ((s < 0) | (s > 1)).any():
                flags.append(f"FAIL: {msg}")

    # any column with >50% missingness flags WARN
    miss = schema[schema["pct_null"] > 0.5]
    for _, r in miss.iterrows():
        flags.append(f"WARN: {r['column']} 결측 {r['pct_null']*100:.0f}%")

    return DQReport(schema=schema, numeric=numeric, categorical=categorical, flags=flags)


# ---------------------------------------------------------------- reconciliation

@dataclass
class ReconCheck:
    item: str
    source: str             # which raw frame / column
    computed: float
    reported: float
    diff: float
    tolerance: float
    passes: bool


def reconcile(result, portfolio: pd.DataFrame) -> list[ReconCheck]:
    """Tie reported headline numbers back to portfolio aggregates."""
    out: list[ReconCheck] = []

    ead_total = float(portfolio["ead"].sum())
    ead_irb_book = float(portfolio.loc[portfolio["asset_class"].isin(
        ["corporate", "retail_other", "residential_mortgage"]), "ead"].sum())
    ead_sa_book = float(portfolio.loc[portfolio["asset_class"].isin(
        ["sovereign", "bank"]), "ead"].sum())

    out.append(ReconCheck(
        "총 EAD = SA책 + IRB책", "portfolio['ead'] sum by asset_class",
        ead_sa_book + ead_irb_book, ead_total,
        diff=(ead_sa_book + ead_irb_book) - ead_total,
        tolerance=1e-6 * ead_total,
        passes=abs((ead_sa_book + ead_irb_book) - ead_total) < 1e-6 * ead_total,
    ))

    # floor 가산분을 `final − sum`으로 만든 뒤 `sum + addon == final`을 검사하면
    # 항상 참이다 — 게다가 `passes=True`가 박혀 있었고 ccr·구조화가 부문 합에서
    # 빠져 파이프라인 실제 구성과도 달랐다. 잔차로 항목을 만드는 것은 이 저장소가
    # 이미 데인 유형이다(구 바젤 서식). 가산분을 **엔진에서 받아** 대사한다.
    floor = result.rwa.get("output_floor")
    floor_addon = float(getattr(floor, "add_on", 0.0) or 0.0)
    rwa_sum = float(result.rwa["sa"] + result.rwa["irb"]
                    + result.rwa.get("ccr", 0.0)
                    + result.rwa.get("structured_total", 0.0)
                    + result.rwa["market"] + result.rwa["op"])
    final = float(result.rwa["final_total"])
    tol = max(1.0, 1e-9 * max(final, 1.0))
    out.append(ReconCheck(
        "최종 RWA = 6부문 합 + floor 가산",
        "sa + irb + ccr + structured + market + op + output_floor.add_on",
        rwa_sum + floor_addon, final,
        diff=(rwa_sum + floor_addon) - final, tolerance=tol,
        passes=abs((rwa_sum + floor_addon) - final) <= tol,
    ))

    # CET1 ratio reconciliation
    cap = result.meta["capital"].cet1
    expected_cet1 = cap / result.bis.rwa
    out.append(ReconCheck(
        "CET1 비율 = CET1자본 / RWA", "BIS 산식",
        expected_cet1, result.bis.cet1_ratio,
        diff=expected_cet1 - result.bis.cet1_ratio,
        tolerance=1e-12,
        passes=abs(expected_cet1 - result.bis.cet1_ratio) < 1e-9,
    ))

    # ECL = sum of stage-level ECL
    if "by_stage" in result.ecl:
        stage_sum = float(result.ecl["by_stage"]["ecl"].sum())
        out.append(ReconCheck(
            "총 ECL = Σ Stage1/2/3 ECL", "ecl.by_stage sum",
            stage_sum, result.ecl["total"],
            diff=stage_sum - result.ecl["total"],
            tolerance=1.0,
            passes=abs(stage_sum - result.ecl["total"]) < 1.0,
        ))

    # LCR = HQLA / net_outflow
    lcr = result.alm["lcr"]
    if lcr.net_outflow > 0:
        expected = lcr.hqla_total / lcr.net_outflow
        out.append(ReconCheck(
            "LCR = HQLA / 순현금유출", "LCR20.1",
            expected, lcr.lcr, diff=expected - lcr.lcr,
            tolerance=1e-9,
            passes=abs(expected - lcr.lcr) < 1e-9,
        ))

    # NSFR = ASF / RSF
    nsfr = result.alm["nsfr"]
    if nsfr.rsf_total > 0:
        expected = nsfr.asf_total / nsfr.rsf_total
        out.append(ReconCheck(
            "NSFR = ASF / RSF", "NSF20.1",
            expected, nsfr.nsfr, diff=expected - nsfr.nsfr,
            tolerance=1e-9,
            passes=abs(expected - nsfr.nsfr) < 1e-9,
        ))

    return out
