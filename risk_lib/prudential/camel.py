"""경영실태평가 (은행업감독규정 제31조~제33조).

자본적정성·자산건전성·경영관리·수익성·유동성·리스크관리 6개 부문을 1~5등급으로
평가하고 가중평균으로 종합등급을 낸다. 종합 3등급 이하이거나 특정 부문이
4등급 이하면 적기시정조치 검토 대상이 된다(pca.py).

**경영관리 부문은 계량화되지 않는다** — 이사회·내부통제·준법감시 평가는 정성
심사다. 여기서는 자체검증 통과율·증빙 완결도를 대용지표로 쓰고 그 사실을
등급 근거에 남긴다. 정성평가를 계량값인 척 포장하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

# 부문 가중치 — 자본·자산건전성에 무게를 둔다.
WEIGHTS = {
    "자본적정성": 0.25, "자산건전성": 0.20, "경영관리": 0.15,
    "수익성": 0.15, "유동성": 0.15, "리스크관리": 0.10,
}

GRADE_LABEL = {1: "우수", 2: "양호", 3: "보통", 4: "취약", 5: "위험"}


def _grade(value: float, thresholds: tuple[float, ...], higher_is_better=True) -> int:
    """thresholds는 1→2, 2→3, 3→4, 4→5 경계 4개."""
    if higher_is_better:
        for i, t in enumerate(thresholds, start=1):
            if value >= t:
                return i
        return 5
    for i, t in enumerate(thresholds, start=1):
        if value <= t:
            return i
    return 5


@dataclass(frozen=True)
class CamelRating:
    asof: str
    detail: pd.DataFrame        # component, indicator, value, grade, weight, basis
    composite: float
    composite_grade: int

    @property
    def composite_label(self) -> str:
        return GRADE_LABEL[self.composite_grade]

    def weakest(self) -> str:
        row = self.detail.loc[self.detail["grade"].idxmax()]
        return str(row["component"])

    def passes(self) -> bool:
        """종합 2등급 이내이고 4등급 이하 부문이 없어야 정상으로 본다."""
        return self.composite_grade <= 2 and int(self.detail["grade"].max()) <= 3


def evaluate_camel(result, tables: dict[str, pd.DataFrame]) -> CamelRating:
    asof = result.meta.get("asof", "1970-01-01")

    # ---- 자본적정성: 총자본비율
    total_ratio = float(result.bis.total_ratio)
    g_cap = _grade(total_ratio, (0.14, 0.12, 0.105, 0.08))

    # ---- 자산건전성: 고정이하여신비율 (낮을수록 우수)
    aq = tables.get("rdm_asset_quality")
    if aq is not None and len(aq):
        bad = float(aq[aq["classification"].isin(("고정", "회수의문", "추정손실"))]
                    ["balance"].sum())
        npl_ratio = bad / float(aq["balance"].sum())
    else:
        npl_ratio = 0.0
    g_asset = _grade(npl_ratio, (0.005, 0.01, 0.02, 0.04), higher_is_better=False)

    # ---- 경영관리: 자체검증 통과율 (정성평가 대용치)
    checks = tables.get("val_check")
    if checks is not None and len(checks):
        pass_rate = float((checks["status"] == "PASS").mean())
    else:
        pass_rate = 1.0
    g_mgmt = _grade(pass_rate, (0.98, 0.95, 0.90, 0.80))

    # ---- 수익성: ROA
    fin_assets = float(result.alm["balance_sheet"].total_assets)
    rev = float(result.rapm["revenue"].sum()) if len(result.rapm) else 0.0
    el = float(result.rapm["el"].sum()) if len(result.rapm) else 0.0
    roa = (rev - el) / fin_assets if fin_assets > 0 else 0.0
    g_profit = _grade(roa, (0.010, 0.007, 0.004, 0.0))

    # ---- 유동성: LCR + 국내 유동성 지표. LCR만 보면 예대율·원화유동성 위반이
    # 경영실태평가 어디에도 남지 않는다.
    lcr = float(result.alm["lcr"].lcr)
    g_liq = _grade(lcr, (1.30, 1.15, 1.05, 1.00))
    dom = tables.get("pru_liquidity_ratio")
    n_breach = int((~dom["passes"]).sum()) if dom is not None and len(dom) else 0
    g_liq = min(5, g_liq + n_breach)      # 국내 지표 위반 1건당 1등급 하향

    # ---- 리스크관리: 스트레스 심각 시나리오 CET1 저점 대비 요구치 여유
    tr = result.stress_path_trough
    sev = tr[tr["scenario"] == "severely_adverse"]
    headroom = (float(sev["trough_cet1"].iloc[0]) - float(result.bis.required["cet1"])
                if len(sev) else 0.0)
    g_risk = _grade(headroom, (0.02, 0.01, 0.0, -0.01))

    rows = [
        ("자본적정성", "총자본비율", total_ratio, g_cap,
         "은행업감독규정 제26조 대비 여유"),
        ("자산건전성", "고정이하여신비율", npl_ratio, g_asset,
         "제27조 분류 기준 고정·회수의문·추정손실 합계 비중"),
        ("경영관리", "자체검증 통과율", pass_rate, g_mgmt,
         "정성평가 대용치 — 이사회·내부통제 심사가 별도로 필요하다"),
        ("수익성", "ROA (EL 차감 후)", roa, g_profit, "수익 − 기대손실 ÷ 총자산"),
        ("유동성", "유동성커버리지비율", lcr, g_liq,
         f"LCR20.1 · 국내 유동성 지표 위반 {n_breach}건 반영"),
        ("리스크관리", "심각 시나리오 CET1 여유", headroom, g_risk,
         "위기상황 저점 − 요구 보통주자본비율"),
    ]
    detail = pd.DataFrame([{
        "component": c, "indicator": ind, "value": v, "grade": g,
        "grade_label": GRADE_LABEL[g], "weight": WEIGHTS[c], "basis": basis,
    } for c, ind, v, g, basis in rows])
    composite = float((detail["grade"] * detail["weight"]).sum())
    return CamelRating(asof=asof, detail=detail, composite=composite,
                       composite_grade=int(round(composite)))
