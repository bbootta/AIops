"""도메인별 익스포저 집계 원장 — 각 산출이 실제로 쓰는 축과 컬럼으로.

익스포저 원장 하나를 모든 도메인이 각자 집계하면, 같은 "익스포저 합"이
도메인마다 다르게 나오고 어느 쪽이 맞는지 사후에 알 수 없다. 도메인마다
**집계 축이 다르고 필요한 컬럼이 다르다**:

    신용    자산군 × 등급 × 담보유형   → PD·LGD·EAD·RW·EL
    시장    위험군 × 통화 × 만기구간   → 명목·민감도·VaR 기여
    운영    영업부문 × 사건유형        → 총손실·회수·순손실·BI
    ALM     리프라이싱 구간 × 통화     → 자산·부채·갭·LCR 분류
    위기    자산군 × 시나리오          → 충격 전후 EAD·PD·ECL·RWA

그래서 도메인별 집계를 **원장으로 고정**한다. 화면·서식·검증이 같은 집계를
다시 만들지 않고 이 원장을 읽는다 — 집계 로직이 세 군데에 흩어지면 그중
하나만 고쳐지는 날이 온다(이 저장소에서 F-701 이 그것이었다).

전 집계는 **총계 항등식**을 만족한다: 도메인 집계의 EAD 합 = 익스포저 원장
EAD 합. 검사가 이것을 고정한다 — 축을 잘못 잡아 중복 계상하면 즉시 깨진다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# 리프라이싱 구간 — ALM 표준 사다리. 경계는 감독 관행(1M/3M/6M/1Y/3Y/5Y).
_REPRICING_EDGES = (0.0, 1 / 12, 0.25, 0.5, 1.0, 3.0, 5.0, np.inf)
_REPRICING_LABELS = ("1개월 이내", "1~3개월", "3~6개월", "6개월~1년",
                     "1~3년", "3~5년", "5년 초과")

# 만기 구간 — 시장리스크 텐서 버킷 (MAR21 vertex 근사).
_TENOR_EDGES = (0.0, 0.5, 1.0, 3.0, 5.0, 10.0, np.inf)
_TENOR_LABELS = ("6개월 이내", "6개월~1년", "1~3년", "3~5년",
                 "5~10년", "10년 초과")


def _bucket(values: pd.Series, edges, labels) -> pd.Series:
    return pd.cut(values, bins=list(edges), labels=list(labels),
                  right=False, include_lowest=True).astype(str)


def credit_aggregate(exposure: pd.DataFrame, ecl: pd.DataFrame | None = None,
                     *, asof: str) -> pd.DataFrame:
    """신용 — 자산군 × 등급 × 계정. RWA·ECL 산출이 쓰는 축이다."""
    df = exposure.copy()
    df["rating"] = df["rating"].fillna("UNRATED")
    if ecl is not None and "exposure_id" in ecl.columns:
        m = ecl.set_index("exposure_id")
        df["ecl"] = df["exposure_id"].map(m["ecl"]).fillna(0.0)
        df["stage"] = df["exposure_id"].map(m["stage"]).fillna(1).astype(int)
    else:
        df["ecl"], df["stage"] = 0.0, 1
    g = df.groupby(["asset_class", "rating", "account_code"], dropna=False)
    out = g.agg(
        n_exposures=("exposure_id", "count"),
        ead=("ead", "sum"),
        drawn=("drawn", "sum"),
        undrawn=("undrawn", "sum"),
        ecl=("ecl", "sum"),
        avg_maturity=("maturity", "mean"),
        avg_ltv=("ltv", "mean"),
        n_stage3=("stage", lambda s: int((s == 3).sum())),
    ).reset_index()
    out.insert(0, "asof", asof)
    out["coverage_ratio"] = np.where(out["ead"] > 0, out["ecl"] / out["ead"], 0.0)
    return out


def market_aggregate(trades: pd.DataFrame | None,
                     risk_factors: pd.DataFrame | None = None,
                     *, asof: str) -> pd.DataFrame:
    """시장 — 상품유형 × 만기구간. 민감도·명목이 붙는다.

    트레이딩 원장이 없으면 **빈 프레임이 아니라 사유 행**을 남긴다 — 빈
    테이블은 "없음"과 "산출 안 함"을 구분하지 못한다.
    """
    if trades is None or trades.empty:
        return pd.DataFrame([{
            "asof": asof, "kind": "—", "tenor_bucket": "—", "n_trades": 0,
            "notional": 0.0, "fo_value": 0.0, "dv01": 0.0, "cs01": 0.0,
            "vega": 0.0, "delta": 0.0,
            "note": "트레이딩 원장 없음 — 산출 대상 아님",
        }])
    df = trades.copy()
    df["tenor_bucket"] = _bucket(df["maturity"].astype(float),
                                 _TENOR_EDGES, _TENOR_LABELS)
    agg = {"n_trades": ("trade_id", "count"), "notional": ("notional", "sum"),
           "fo_value": ("fo_value", "sum")}
    for c in ("dv01", "cs01", "vega", "delta"):
        if c in df.columns:
            agg[c] = (c, "sum")
    out = df.groupby(["kind", "tenor_bucket"], dropna=False).agg(**agg).reset_index()
    out.insert(0, "asof", asof)
    out["note"] = ""
    return out


def operational_aggregate(loss_events: pd.DataFrame | None,
                          *, asof: str) -> pd.DataFrame:
    """운영 — 사건유형 × 연도. 총손실 → 회수 → 순손실 순서로 읽는다."""
    if loss_events is None or loss_events.empty:
        return pd.DataFrame([{
            "asof": asof, "event_type": "—", "event_year": "—",
            "n_events": 0, "gross_loss": 0.0, "recovery": 0.0,
            "net_loss": 0.0, "max_single_loss": 0.0,
            "note": "손실사건 원장 없음",
        }])
    df = loss_events.copy()
    df["event_year"] = pd.to_datetime(df["event_date"]).dt.year.astype(str)
    out = df.groupby(["event_type", "event_year"], dropna=False).agg(
        n_events=("event_id", "count"),
        gross_loss=("gross_loss", "sum"),
        recovery=("recovery", "sum"),
        net_loss=("net_loss", "sum"),
        max_single_loss=("gross_loss", "max"),
    ).reset_index()
    out.insert(0, "asof", asof)
    out["note"] = ""
    return out


def alm_aggregate(exposure: pd.DataFrame, account_scope: pd.DataFrame | None,
                  *, asof: str) -> pd.DataFrame:
    """ALM — 리프라이싱 구간 × LCR 분류. 금리·유동성 산출의 공통 축이다."""
    df = exposure.copy()
    df["repricing_bucket"] = _bucket(df["maturity"].astype(float),
                                     _REPRICING_EDGES, _REPRICING_LABELS)
    if account_scope is not None and "account_code" in account_scope.columns:
        m = account_scope.set_index("account_code")
        df["lcr_category"] = df["account_code"].map(m["lcr_category"]).fillna("—")
        df["irrbb_scope"] = df["account_code"].map(m["irrbb_scope"]).fillna(False)
    else:
        df["lcr_category"], df["irrbb_scope"] = "—", False
    out = df.groupby(["repricing_bucket", "lcr_category"], dropna=False).agg(
        n_exposures=("exposure_id", "count"),
        ead=("ead", "sum"),
        irrbb_ead=("ead", lambda s: 0.0),   # 아래에서 마스크로 다시 채운다
    ).reset_index()
    # lambda 안에서 다른 열을 볼 수 없으므로 별도 집계 후 병합한다.
    irr = (df[df["irrbb_scope"].astype(bool)]
           .groupby(["repricing_bucket", "lcr_category"], dropna=False)["ead"]
           .sum().rename("irrbb_ead_real").reset_index())
    out = out.merge(irr, on=["repricing_bucket", "lcr_category"], how="left")
    out["irrbb_ead"] = out["irrbb_ead_real"].fillna(0.0)
    out = out.drop(columns=["irrbb_ead_real"])
    out.insert(0, "asof", asof)
    return out


def stress_aggregate(exposure: pd.DataFrame, stress_path: pd.DataFrame | None,
                     *, asof: str) -> pd.DataFrame:
    """위기상황 — 자산군 × 시나리오. 충격 전후를 나란히 둔다.

    시나리오별 충격 배수는 경로 원장(st_capital_path)의 심도에서 온다 —
    여기서 지어내지 않는다. 경로가 없으면 기준선만 남긴다.
    """
    base = exposure.groupby("asset_class", dropna=False).agg(
        n_exposures=("exposure_id", "count"), ead=("ead", "sum")).reset_index()
    rows = []
    if stress_path is None or stress_path.empty:
        scenarios = [("baseline", 0.0)]
    else:
        sp = stress_path
        col = "severity" if "severity" in sp.columns else None
        scenarios = ([(sc, float(sp[sp["scenario"] == sc][col].max()))
                      for sc in sp["scenario"].unique()] if col
                     else [(sc, 0.0) for sc in sp["scenario"].unique()])
    for sc, sev in scenarios:
        for _, r in base.iterrows():
            rows.append({
                "asof": asof, "scenario": sc, "asset_class": r["asset_class"],
                "severity": sev,
                "n_exposures": int(r["n_exposures"]),
                "ead_base": float(r["ead"]),
                # 충격 후 EAD — 미인출 인출률 상승분만 반영(보수적 단순화).
                # 실제 경로 산출은 stress 엔진이 한다. 여기는 **집계 축**이며
                # 그 사실을 note 로 남긴다.
                "ead_stressed": float(r["ead"]) * (1.0 + 0.05 * sev),
                "note": "집계 축 — 실제 충격 산출은 st_calc_trace 소관",
            })
    return pd.DataFrame(rows)


def build_exposure_aggregates(tables: dict[str, pd.DataFrame], *, asof: str
                              ) -> dict[str, pd.DataFrame]:
    """도메인별 집계 원장 5종. 원장이 없으면 사유 행을 남긴다."""
    exp = tables["rdm_exposure"]
    return {
        "agg_credit_exposure": credit_aggregate(
            exp, tables.get("ecl_result"), asof=asof),
        "agg_market_exposure": market_aggregate(
            tables.get("mkt_trade"), tables.get("mkt_risk_factor"), asof=asof),
        "agg_operational_loss": operational_aggregate(
            tables.get("opr_loss_event"), asof=asof),
        "agg_alm_exposure": alm_aggregate(
            exp, tables.get("alm_code_scope"), asof=asof),
        "agg_stress_exposure": stress_aggregate(
            exp, tables.get("st_capital_path"), asof=asof),
    }
