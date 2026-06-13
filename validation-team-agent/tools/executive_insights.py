"""경영진 보고서용 인사이트 추출기.

워크플로우 demo 결과(dict)에서 CRO·MRMC 가 의사결정에 사용하는 형태로
정보를 압축한다. 산출:

- 부문 × 상태 행 (히트맵용)
- 핵심 KPI 카드 (자본/유동성/내부자본/시장/IRRBB/집중)
- top-N risks: fail/warning 상위 위험 — detail 그대로 인용, 출처(step) 함께
- top-N actions: 위험별 표준 권고 (정책 SSoT 기반, 임의 완화 금지)

본 모듈은 어떤 판정도 임의로 변경하지 않는다 (CLAUDE.md §5). 단지
handler 결과를 경영진 시야로 재배열한다.
"""

from __future__ import annotations

_DOMAIN_ROWS: list[tuple[str, str, str]] = [
    # (sid, label, deep_link)
    ("3.disc", "신용 변별력 (KS/AUROC)", "credit.html"),
    ("3.psi", "신용 안정성 (PSI)", "credit.html"),
    ("3.cal", "신용 캘리브레이션 (등급별 PD)", "credit_calibration.html"),
    ("3.capital", "자본적정성 (CET1/Tier1/총자본/leverage)", "capital_icaap.html"),
    ("3.icaap", "내부자본 적정성 (ICAAP, Pillar 2)", "capital_icaap.html"),
    ("3.liquidity", "유동성 (LCR/NSFR)", "alm.html"),
    ("3.alm", "ALM (만기갭/조달집중/예대율)", "alm.html"),
    ("3.irrbb", "IRRBB (금리리스크 ΔEVE)", "alm_irrbb.html"),
    ("3.market", "시장리스크 (VaR backtest)", "market_ops.html"),
    ("3.operational", "운영리스크 (SMA)", "market_ops.html"),
    ("3.cva", "CVA", "market_ops.html"),
    ("3.ccr", "거래상대방 신용리스크 (SA-CCR)", "market_ops.html"),
    ("3.conc", "신용집중 (LEX + 은행법 35조)", "concentration.html"),
    ("3.macro", "거시 정상성", "credit.html"),
    ("3.weights", "IFRS 9 시나리오 가중치", "credit.html"),
]


def domain_rows(demo: dict) -> list[tuple[str, str, str, str | None]]:
    """경영진 히트맵용 (label, status, detail, deep_link) 행."""
    out: list[tuple[str, str, str, str | None]] = []
    for sid, label, link in _DOMAIN_ROWS:
        r = demo["results"].get(sid)
        if r is None:
            continue
        status = r["status"]
        detail = r.get("detail", "")
        out.append((label, status, detail, link))
    return out


# 임계값 인용 (정책 SSoT 한 곳에서 가져옴 — 임의 완화 금지)
_KPI_THRESHOLDS_REF = {
    "capital_cet1": "harness/capital_adequacy_thresholds.json (CET1 4.5% + 보전 2.5%)",
    "leverage": "harness/capital_adequacy_thresholds.json (≥ 3%)",
    "lcr": "harness/liquidity_risk_thresholds.json (≥ 100%)",
    "nsfr": "harness/liquidity_risk_thresholds.json (≥ 100%)",
    "icaap": "harness/icaap_thresholds.json (≥ 100%)",
    "irrbb": "harness/irrbb_thresholds.json (ΔEVE/Tier1 ≤ 15%)",
    "var": "harness/market_risk_thresholds.json (FRTB MAR99 traffic light)",
    "conc": "harness/concentration_thresholds.json (LEX 25% Tier1)",
}


def kpi_cards(demo: dict) -> list[tuple[str, str, str]]:
    """경영진 KPI 카드 — (label, value, status_key).

    값은 부문 handler outputs 에서 직접 인용한다. status_key 는 부문 step 의
    handler 판정 그대로 — KPI 카드가 판정을 다시 만들지 않는다.
    """
    cards: list[tuple[str, str, str]] = []
    cap = demo["results"].get("3.capital", {}).get("outputs", {})
    cap_status = demo["results"].get("3.capital", {}).get("status", "skipped")
    if cap:
        ratios = cap.get("ratios", {})
        lev = cap.get("leverage", {})
        if ratios:
            req = ratios.get("cet1_required", 0)
            cards.append(("CET1 요구 (buffer 포함)", f"{req:.2%}", cap_status))
        if lev:
            cards.append(("Leverage", f"{lev.get('ratio', 0):.2%}",
                          "ok" if lev.get("passed") else "fail"))

    icaap = demo["results"].get("3.icaap", {}).get("outputs", {})
    icaap_status = demo["results"].get("3.icaap", {}).get("status", "skipped")
    if icaap:
        cards.append((
            "내부자본비율 (ICAAP)",
            f"{icaap.get('ratio', 0):.2f}", icaap_status))
        if icaap.get("post_stress_ratio") is not None:
            ps_lvl = icaap.get("post_stress_level", "skipped")
            cards.append((
                "스트레스 후 ICAAP",
                f"{icaap.get('post_stress_ratio', 0):.2f}",
                ps_lvl if ps_lvl in ("ok", "warning") else "fail"))

    liq = demo["results"].get("3.liquidity", {}).get("outputs", {})
    if liq.get("lcr"):
        lcr = liq["lcr"]
        cards.append((
            "LCR (≥ 100%)", f"{lcr['ratio']:.2f}",
            "ok" if lcr["status"] == "ok"
            else "warning" if lcr["status"] == "warning" else "fail"))
    if liq.get("nsfr"):
        nsfr = liq["nsfr"]
        cards.append((
            "NSFR (≥ 100%)", f"{nsfr['ratio']:.2f}",
            "ok" if nsfr["status"] == "ok"
            else "warning" if nsfr["status"] == "warning" else "fail"))

    irrbb = demo["results"].get("3.irrbb", {}).get("outputs", {})
    if irrbb:
        out = ("fail" if irrbb.get("outlier") else "ok")
        cards.append((
            "ΔEVE/Tier1 (≤ 15%)",
            f"{irrbb.get('ratio', 0):.1%}", out))

    mkt = demo["results"].get("3.market", {}).get("outputs", {})
    if mkt:
        zone = mkt.get("zone", "-")
        cards.append((
            "VaR backtest zone",
            f"{zone} ({mkt.get('exceptions', 0)})",
            {"green": "ok", "yellow": "warning", "red": "fail"}.get(zone, "skipped")))

    conc = demo["results"].get("3.conc", {}).get("outputs", {})
    if conc:
        cards.append((
            "신용집중 HHI / band",
            f"{conc.get('hhi', 0):.3f} ({conc.get('hhi_band', '-')})",
            "fail" if conc.get("n_breaches", 0) > 0 else "ok"))

    return cards


# 권고는 정책 SSoT 와 1:1 매핑된 표준 문구 — 임계 임의 완화 금지
_STANDARD_ACTIONS: dict[str, str] = {
    "3.capital": ("자본확충 / 리스크자산(RWA) 축소 / 자본보전 buffer 활용 계획을 "
                  "MRMC 에 상정. 감독원 사전 협의 필요."),
    "3.icaap": ("내부자본 시나리오 재산정 + 자본계획 보완. 분산효과 가정 검증, "
                "스트레스 시나리오 강화 후 SREP 보고 검토."),
    "3.liquidity": ("HQLA 확충 / 만기 부채 차환 계획 / 외화LCR 행정지도 80% "
                    "유지 점검. 일중유동성 사후 보고."),
    "3.alm": ("만기 mismatch 축소를 위한 차환 계획 / 단일 조달처 의존 완화 / "
              "원화 예대율 100% 한도 내 관리. ALCO 안건 상정."),
    "3.irrbb": ("금리 시나리오별 헤지(파생) / 대출 만기 구조 조정. 모형 가정 "
                "(고정금리 비중·prepayment) 재검증."),
    "3.market": ("VaR 모형 재검증 / SVaR 추가 / red zone 시 multiplier 가산 "
                 "(FRTB MAR99). 트레이딩 한도 일시 축소 검토."),
    "3.operational": ("BI 구성 (이자/서비스/재무) 재검증. ILDC 사용 시 자체 "
                      "10년 손실 데이터 품질 점검."),
    "3.cva": ("거래상대방 헤지 효과 점검. SA-CVA 적용 임계 (트레이딩북 100bn) "
              "근접 시 모형 승인 절차 착수."),
    "3.ccr": ("SA-CCR α=1.4 가정 검토. wrong-way risk 식별 / 담보 management."),
    "3.conc": ("거액익스포저 부분상환 / 한도 재배분. 동일차주 (은행법 35조) "
               "한도 위반 시 즉시 시정 조치."),
    "3.disc": ("신용 변별력 저하 → 모형 재훈련 또는 챌린저 모형 도입. 표본 "
               "기간 재정의."),
    "3.psi": ("운영 표본 drift → bin 재정의 / 변수 재선정. PSI ≥ 0.25 시 "
              "재캘리브레이션 트리거."),
    "3.cal": ("등급별 binomial reject → 재캘리브레이션 / 등급 통합 검토 / "
              "확률 보정 모형 도입."),
    "3.macro": ("거시 변수 비정상성 → 차분 처리 또는 협응변수 검정. 시차 "
                "구조 재선정."),
    "3.weights": ("IFRS 9 시나리오 가중치 floor 위반 → MRMC 승인 후 조정. "
                  "감독원 사전 협의."),
}


def top_risks_and_actions(
    demo: dict, *, n: int = 3,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """fail → warning 순으로 상위 위험과 표준 권고를 추출."""
    order = {"fail": 0, "warning": 1, "skipped": 2, "ok": 3, "simulated": 4}
    items = []
    for sid, label, link in _DOMAIN_ROWS:
        r = demo["results"].get(sid)
        if r is None or r["status"] not in ("fail", "warning"):
            continue
        items.append({
            "sid": sid, "label": label, "status": r["status"],
            "detail": r.get("detail", ""), "link": link,
        })
    items.sort(key=lambda x: (order.get(x["status"], 99), x["sid"]))
    risks = items[:n]
    actions = [{
        "sid": r["sid"],
        "label": r["label"],
        "action": _STANDARD_ACTIONS.get(r["sid"], "표준 권고 미정 — MRMC 검토 필요."),
        "link": r["link"],
    } for r in risks]
    return risks, actions


__all__ = ["domain_rows", "kpi_cards", "top_risks_and_actions"]
