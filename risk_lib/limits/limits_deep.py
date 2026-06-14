"""CRO-grade 한도/집중리스크 deep-dive (v0.11.0).

다음을 제공한다.

- ``build_default_limit_set`` — 은행법 §35 / 감독세칙 / BCBS LEX / 내부 한도를
  포함한 표준 LimitDefinition 묶음.
- ``limit_dashboard`` — 모든 한도(OK 포함)의 사용률 grid (CRO dashboard).
- ``large_exposure_lex`` — BCBS LEX framework (Tier1 10%+) 별도 보고.
- ``escalation_matrix`` — severity별 보고/승인 라인.
- ``action_recommendations`` — 사용률 기반 권고 조치 + 추가가능 노출액.
- ``quarterly_utilisation_trend`` — 합성 분기별 사용률 (시계열).
- ``historical_breach_log`` — 분기별 위반 건수 추이 (합성 시계열).
- ``stress_adjusted_utilisation`` — adverse/severely_adverse 적용 사용률.
- ``group_obligor_id`` — 차주ID → 그룹코드 매핑 helper (간이).

규제 근거:
  「은행법」 제35조, 「은행업감독규정」 제29조,
  BCBS 283 (Supervisory framework for measuring and controlling
  large exposures, 2014).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd

from risk_lib.limits.limit_engine import LimitDefinition, LimitEngine


# ---------------------------------------------------------------- helpers

def _severity(util: float) -> str:
    if util >= 1.00:
        return "BREACH"
    if util >= 0.90:
        return "CRITICAL"
    if util >= 0.75:
        return "WARN"
    return "OK"


SEVERITY_ORDER = ["OK", "WARN", "CRITICAL", "BREACH"]


def group_obligor_id(obligor_id: str) -> str:
    """간이 그룹 코드 합성 — 차주ID 접두부를 그룹 식별자로 사용.

    예: ``OBL_CORP_00012`` → ``GRP_CORP_001`` (앞 3자리 묶음).
    실제 환경에서는 차주 마스터의 ``parent_group_id``를 사용해야 한다.
    """
    if not isinstance(obligor_id, str) or "_" not in obligor_id:
        return f"GRP_{obligor_id}"
    parts = obligor_id.split("_")
    if len(parts) < 3:
        return f"GRP_{obligor_id}"
    # 'OBL_CORP_00012' → 'GRP_CORP_000' (앞 3자리)
    tail = parts[-1]
    bucket = tail[:3] if len(tail) >= 3 else tail
    return f"GRP_{parts[1]}_{bucket}"


def attach_group_id(portfolio: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with ``obligor_group_id`` column added (idempotent)."""
    out = portfolio.copy()
    if "obligor_group_id" not in out.columns:
        out["obligor_group_id"] = out["obligor_id"].map(group_obligor_id)
    return out


def attach_product_type(portfolio: pd.DataFrame) -> pd.DataFrame:
    """상품유형(product_type) 컬럼 합성.

    자산군 + ltv 보유 여부를 사용해 ``unsecured / mortgage_backed /
    fx_loan / sovereign / bank``으로 분류.
    """
    out = portfolio.copy()
    if "product_type" in out.columns:
        return out
    ltv = out.get("ltv", pd.Series([np.nan] * len(out), index=out.index))
    country = out.get("country", pd.Series(["KR"] * len(out), index=out.index))
    asset = out["asset_class"]
    product = np.where(
        asset.eq("residential_mortgage"), "mortgage_backed",
        np.where(asset.eq("sovereign"), "sovereign",
        np.where(asset.eq("bank"), "bank",
        np.where(country.ne("KR"), "fx_loan",
        np.where(ltv.notna() & (ltv > 0), "secured_corporate", "unsecured")))))
    out["product_type"] = product
    return out


def attach_maturity_bucket(portfolio: pd.DataFrame) -> pd.DataFrame:
    """만기 버킷(maturity_bucket): ≤1Y / 1-3Y / 3-5Y / 5-10Y / 10Y+."""
    out = portfolio.copy()
    if "maturity_bucket" in out.columns:
        return out
    m = pd.to_numeric(out.get("maturity", 1.0), errors="coerce").fillna(1.0)
    out["maturity_bucket"] = pd.cut(
        m, bins=[-0.01, 1, 3, 5, 10, 1e6],
        labels=["≤1Y", "1-3Y", "3-5Y", "5-10Y", "10Y+"],
    ).astype(str)
    return out


def enrich_portfolio(portfolio: pd.DataFrame) -> pd.DataFrame:
    """``obligor_group_id`` / ``product_type`` / ``maturity_bucket`` 일괄 부여."""
    return attach_maturity_bucket(attach_product_type(attach_group_id(portfolio)))


# ---------------------------------------------------------------- limit set

def build_default_limit_set(tier1: float) -> list[LimitDefinition]:
    """은행법 §35 + 감독세칙 + 내부 한도를 모두 포함한 표준 한도 묶음.

    Notes
    -----
    - 동일차주 25% / 동일인 20% (은행법 §35).
    - 그룹 차주 30% (내부 한도; 동일차주와 별도로 그룹 단위 집계).
    - 섹터별 한도 (% of Tier1): 부동산 30, 건설 20, 제조 25,
      shipping 15, 그 외 30.
    - 국가별 한도 (% of Tier1): KR 무제한이지만 기록 목적 200%,
      신흥국 (CN/VN) 15-20%, 선진국 (US/JP) 25-30%.
    - 상품별 한도 (% of Tier1): 무담보 40%, fx_loan 20%.
    - 만기별 한도 (% of Tier1): 10Y+ 25%.
    """
    lims: list[LimitDefinition] = [
        # 은행법 §35
        LimitDefinition("동일차주_Tier1_25pct", "obligor_id", None,
                        0.25, basis="pct_tier1"),
        LimitDefinition("그룹차주_Tier1_30pct", "obligor_group_id", None,
                        0.30, basis="pct_tier1"),
    ]
    # 섹터별 한도 (% of Tier1)
    sector_caps = {
        "real_estate": 0.30,
        "construction": 0.20,
        "manufacturing": 0.25,
        "shipping": 0.15,
        "energy": 0.20,
        "tech": 0.25,
        "retail_trade": 0.20,
        "household": 1.00,
        "financial": 0.30,
        "government": 2.00,
    }
    for sec, cap in sector_caps.items():
        lims.append(LimitDefinition(
            f"섹터_{sec}_Tier1_{int(cap*100)}pct",
            "sector", sec, cap, basis="pct_tier1",
        ))
    # 국가별 한도
    country_caps = {
        "KR": 2.00, "US": 0.30, "JP": 0.30, "CN": 0.20, "VN": 0.15,
    }
    for c, cap in country_caps.items():
        lims.append(LimitDefinition(
            f"국가_{c}_Tier1_{int(cap*100)}pct",
            "country", c, cap, basis="pct_tier1",
        ))
    # 상품별 한도
    product_caps = {
        "unsecured": 0.40,
        "secured_corporate": 0.80,
        "mortgage_backed": 1.20,
        "fx_loan": 0.20,
        "bank": 0.30,
        "sovereign": 2.00,
    }
    for p, cap in product_caps.items():
        lims.append(LimitDefinition(
            f"상품_{p}_Tier1_{int(cap*100)}pct",
            "product_type", p, cap, basis="pct_tier1",
        ))
    # 만기별 한도 (장기집중 억제)
    maturity_caps = {"10Y+": 0.25, "5-10Y": 0.40}
    for m, cap in maturity_caps.items():
        lims.append(LimitDefinition(
            f"만기_{m}_Tier1_{int(cap*100)}pct",
            "maturity_bucket", m, cap, basis="pct_tier1",
        ))
    return lims


# ---------------------------------------------------------------- dashboard

def limit_dashboard(
    portfolio: pd.DataFrame,
    limits: list[LimitDefinition],
    tier1: float,
    *,
    exposure_col: str = "ead",
) -> pd.DataFrame:
    """OK 포함 모든 한도의 사용률 표 (CRO dashboard).

    한 행 = (limit, bucket).  value=None인 한도는 차원의 모든 버킷에 대해 펼친다.
    """
    rows = []
    for lim in limits:
        if lim.dimension not in portfolio.columns:
            continue
        if lim.basis == "pct_tier1":
            threshold = lim.threshold * tier1
        else:
            threshold = float(lim.threshold)
        if lim.value is not None:
            df = portfolio[portfolio[lim.dimension] == lim.value]
            exp = float(df[exposure_col].sum())
            util = exp / threshold if threshold > 0 else float("inf")
            rows.append({
                "limit": lim.name, "dimension": lim.dimension,
                "bucket": lim.value, "exposure": exp, "threshold": threshold,
                "utilisation": util, "severity": _severity(util),
                "headroom": max(threshold - exp, 0.0),
                "basis": lim.basis, "threshold_pct": (
                    lim.threshold if lim.basis == "pct_tier1" else float("nan")),
            })
        else:
            grp = portfolio.groupby(lim.dimension)[exposure_col].sum()
            for bucket, exp in grp.items():
                util = float(exp) / threshold if threshold > 0 else float("inf")
                rows.append({
                    "limit": lim.name, "dimension": lim.dimension,
                    "bucket": bucket, "exposure": float(exp),
                    "threshold": threshold, "utilisation": util,
                    "severity": _severity(util),
                    "headroom": max(threshold - float(exp), 0.0),
                    "basis": lim.basis, "threshold_pct": (
                        lim.threshold if lim.basis == "pct_tier1" else float("nan")),
                })
    return pd.DataFrame(rows).sort_values(
        "utilisation", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------- BCBS LEX

def large_exposure_lex(
    portfolio: pd.DataFrame, tier1: float,
    *, exposure_col: str = "ead", group: bool = False,
) -> pd.DataFrame:
    """BCBS LEX framework (BCBS 283, 2014) — Tier1의 10% 이상 차주 별도 보고.

    Reporting threshold (LEX §14) = 10% of Tier1.
    Hard limit (LEX §16) = 25% of Tier1 (G-SIB 간 15%).
    """
    key = "obligor_group_id" if group else "obligor_id"
    if key not in portfolio.columns:
        portfolio = attach_group_id(portfolio) if group else portfolio
    g = portfolio.groupby(key)[exposure_col].sum().reset_index()
    g = g.rename(columns={exposure_col: "ead"})
    g["pct_tier1"] = g["ead"] / tier1 if tier1 > 0 else 0.0
    g["reportable"] = g["pct_tier1"] >= 0.10
    g["limit_25pct"] = tier1 * 0.25
    g["utilisation_25pct"] = g["ead"] / g["limit_25pct"]
    def _sev(u: float) -> str:
        if u >= 1.0:  return "BREACH"
        if u >= 0.9:  return "CRITICAL"
        if u >= 0.75: return "WARN"
        return "OK"
    g["severity"] = g["utilisation_25pct"].map(_sev)
    g = g[g["reportable"]].sort_values("ead", ascending=False).reset_index(drop=True)
    return g


# ---------------------------------------------------------------- escalation

def escalation_matrix() -> pd.DataFrame:
    """severity별 보고/승인 라인 (감독세칙 운영지침 + 내규 표준).

    실제 라인은 각 사 내규(준법감시인 + 신용리스크관리정책)에 따른다.
    """
    rows = [
        {"severity": "OK", "action": "정상 모니터링",
         "owner": "한도관리담당자", "report_cycle": "월간",
         "approval_required": "없음"},
        {"severity": "WARN", "action": "사전 경보 — 영업본부 통지, 신규증액 자제",
         "owner": "신용리스크관리부장", "report_cycle": "주간",
         "approval_required": "리스크관리부장 승인 (증액 시)"},
        {"severity": "CRITICAL", "action": "긴급 — 신규거래 보류, 헤지/매각 검토",
         "owner": "리스크관리본부장", "report_cycle": "일일",
         "approval_required": "CRO + 리스크관리위원회 승인"},
        {"severity": "BREACH", "action": "한도위반 — 즉시 보고, 시정조치(매각/헤지) 또는 이사회 한도증액 결의",
         "owner": "CRO → 이사회", "report_cycle": "즉시",
         "approval_required": "이사회 결의 (한도증액 또는 시정조치 추인)"},
    ]
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- actions

def action_recommendations(
    dashboard: pd.DataFrame, *, top_n: int = 25,
) -> pd.DataFrame:
    """사용률 기반 권고 조치.

    OK이면 추가 가능 노출액(headroom)을 제시, CRITICAL/BREACH이면 감축 권고.
    """
    rows = []
    for _, r in dashboard.iterrows():
        sev = r["severity"]
        u = float(r["utilisation"])
        thr = float(r["threshold"])
        exp = float(r["exposure"])
        if sev == "BREACH":
            reduce_amt = exp - thr
            rows.append({
                "limit": r["limit"], "bucket": r["bucket"],
                "severity": sev, "utilisation": u,
                "action": "즉시 감축",
                "amount": reduce_amt,
                "narrative": (f"한도 초과 {reduce_amt/1e12:.2f}조원 — "
                              f"매각·헤지·신디케이션으로 즉시 시정"),
            })
        elif sev == "CRITICAL":
            rows.append({
                "limit": r["limit"], "bucket": r["bucket"],
                "severity": sev, "utilisation": u,
                "action": "신규 보류 + 감축 검토",
                "amount": exp - thr * 0.90,
                "narrative": (f"사용률 {u*100:.1f}% — 신규거래 중단, "
                              f"한도 90% 이하로 축소 권고"),
            })
        elif sev == "WARN":
            rows.append({
                "limit": r["limit"], "bucket": r["bucket"],
                "severity": sev, "utilisation": u,
                "action": "사전경보 — 영업본부 통지",
                "amount": thr - exp,
                "narrative": (f"사용률 {u*100:.1f}% — 추가증액 시 "
                              f"리스크관리부장 사전승인 필요"),
            })
        else:  # OK
            rows.append({
                "limit": r["limit"], "bucket": r["bucket"],
                "severity": sev, "utilisation": u,
                "action": "추가 가능",
                "amount": thr - exp,
                "narrative": f"추가 가능 노출액 {(thr-exp)/1e12:.2f}조원",
            })
    out = pd.DataFrame(rows)
    # severity-priority sort (BREACH 최우선) 후 사용률 내림차순
    sev_rank = {"BREACH": 0, "CRITICAL": 1, "WARN": 2, "OK": 3}
    out["_rank"] = out["severity"].map(sev_rank).fillna(9).astype(int)
    out = out.sort_values(
        ["_rank", "utilisation"], ascending=[True, False]
    ).drop(columns="_rank").reset_index(drop=True)
    return out.head(top_n)


# ---------------------------------------------------------------- trend

def quarterly_utilisation_trend(
    portfolio: pd.DataFrame, limits: list[LimitDefinition],
    tier1: float, *, n_quarters: int = 8, seed: int = 42,
) -> pd.DataFrame:
    """분기별 사용률 합성 시계열 — 현재 사용률에 ±15% 노이즈 + 완만한 트렌드.

    Returns: long-form (quarter, limit, bucket, utilisation, severity).
    """
    rng = np.random.default_rng(seed)
    today = pd.Timestamp.today().to_period("Q")
    quarters = [(today - n_quarters + 1 + i).strftime("%YQ%q")
                for i in range(n_quarters)]
    snap = limit_dashboard(portfolio, limits, tier1)
    rows = []
    for _, lim_row in snap.iterrows():
        u_now = float(lim_row["utilisation"])
        # 완만한 상승 트렌드 + 분기별 잡음
        trend = np.linspace(u_now * 0.85, u_now, n_quarters)
        noise = rng.normal(0, u_now * 0.05, n_quarters)
        path = np.clip(trend + noise, 0, None)
        for q, u in zip(quarters, path):
            rows.append({
                "quarter": q, "limit": lim_row["limit"],
                "bucket": str(lim_row["bucket"]),
                "utilisation": float(u), "severity": _severity(float(u)),
            })
    return pd.DataFrame(rows)


def historical_breach_log(
    *, n_quarters: int = 8, seed: int = 42,
) -> pd.DataFrame:
    """분기별 (WARN/CRITICAL/BREACH) 건수 합성 시계열."""
    rng = np.random.default_rng(seed + 7)
    today = pd.Timestamp.today().to_period("Q")
    quarters = [(today - n_quarters + 1 + i).strftime("%YQ%q")
                for i in range(n_quarters)]
    rows = []
    for q in quarters:
        # 평균 발생 강도 — 분기별 변동
        warn = int(max(0, rng.normal(8, 2)))
        critical = int(max(0, rng.normal(3, 1.2)))
        breach = int(max(0, rng.normal(1, 0.8)))
        rows.append({
            "quarter": q, "WARN": warn, "CRITICAL": critical,
            "BREACH": breach, "total": warn + critical + breach,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- stress

# Stress 시 EAD multiplier (PD 상승 → CCF 증가 → drawn balance↑ + LGD↑)
STRESS_EAD_MULTIPLIER = {
    "baseline": 1.00,
    "adverse": 1.10,
    "severely_adverse": 1.25,
}


def stress_adjusted_utilisation(
    portfolio: pd.DataFrame, limits: list[LimitDefinition], tier1: float,
    *, scenario: str = "severely_adverse", exposure_col: str = "ead",
) -> pd.DataFrame:
    """스트레스 시 사용률 — EAD multiplier 적용 후 한도 재평가.

    Tier1은 동일 가정 (스트레스 시 capital depletion은 BIS 모듈에서 처리).
    """
    mult = STRESS_EAD_MULTIPLIER.get(scenario, 1.0)
    work = portfolio.copy()
    work[exposure_col] = work[exposure_col] * mult
    dash = limit_dashboard(work, limits, tier1, exposure_col=exposure_col)
    dash["scenario"] = scenario
    dash["multiplier"] = mult
    return dash


def stress_utilisation_compare(
    portfolio: pd.DataFrame, limits: list[LimitDefinition], tier1: float,
    *, exposure_col: str = "ead",
) -> pd.DataFrame:
    """3-시나리오 (baseline/adverse/severely_adverse) 한도 사용률 비교.

    long-form: limit, bucket, scenario, utilisation, severity, exposure.
    """
    out = []
    for s in ("baseline", "adverse", "severely_adverse"):
        d = stress_adjusted_utilisation(
            portfolio, limits, tier1, scenario=s, exposure_col=exposure_col
        )
        out.append(d[["limit", "bucket", "scenario", "utilisation",
                      "severity", "exposure", "threshold"]])
    return pd.concat(out, ignore_index=True)


# ---------------------------------------------------------------- entry

@dataclass
class LimitsDeepResult:
    dashboard: pd.DataFrame
    large_exposure_lex: pd.DataFrame
    large_exposure_lex_group: pd.DataFrame
    escalation: pd.DataFrame
    actions: pd.DataFrame
    utilisation_trend: pd.DataFrame
    breach_log: pd.DataFrame
    stress_utilisation: pd.DataFrame
    summary: dict


def compute_limits_deep(
    portfolio: pd.DataFrame, tier1: float, *, seed: int = 42,
) -> LimitsDeepResult:
    """모든 한도 deep-dive 산출물을 하나의 객체로 묶어 반환."""
    work = enrich_portfolio(portfolio)
    lims = build_default_limit_set(tier1)
    dash = limit_dashboard(work, lims, tier1)
    lex = large_exposure_lex(work, tier1, group=False)
    lex_g = large_exposure_lex(work, tier1, group=True)
    esc = escalation_matrix()
    actions = action_recommendations(dash)
    trend = quarterly_utilisation_trend(work, lims, tier1, seed=seed)
    breach_log = historical_breach_log(seed=seed)
    stress = stress_utilisation_compare(work, lims, tier1)
    summary = {
        "n_limits": int(dash["limit"].nunique()),
        "n_rows": int(len(dash)),
        "n_warn": int((dash["severity"] == "WARN").sum()),
        "n_critical": int((dash["severity"] == "CRITICAL").sum()),
        "n_breach": int((dash["severity"] == "BREACH").sum()),
        "n_lex_reportable": int(len(lex)),
        "max_utilisation": float(dash["utilisation"].max() if not dash.empty else 0.0),
    }
    return LimitsDeepResult(
        dashboard=dash, large_exposure_lex=lex,
        large_exposure_lex_group=lex_g, escalation=esc,
        actions=actions, utilisation_trend=trend, breach_log=breach_log,
        stress_utilisation=stress, summary=summary,
    )
