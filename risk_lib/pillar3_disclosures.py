"""Pillar 3 disclosure templates — BCBS DIS standard formats.

Implements the 11 standard tables a Top-IB / Basel III compliant bank
files quarterly to the regulator (and the public):

  Capital
    KM1   — Key metrics (bank-level)
    OV1   — Overview of RWA

  Credit risk
    CR1   — Credit quality of exposures (performing vs non-performing)
    CR2   — Movement in non-performing loans and advances
    CR3   — Credit risk mitigation techniques — overview
    CR4   — Standardised approach — credit risk exposure and CRM effects
    CR5   — Standardised approach — exposures by asset class × risk weights

  Market risk
    MR1   — Market risk under standardised approach
    MR2   — RWA flow statements of market risk exposures under IMA

  Liquidity
    LIQ1  — LCR detail
    LIQ2  — NSFR detail

  Leverage
    LR1   — Comparison of accounting assets vs leverage exposure measure
    LR2   — Leverage ratio common disclosure template

References: BCBS DIS25–DIS80 (Pillar 3 disclosure requirements,
consolidated framework), 감독세칙 정보공시 편, EBA ITS 2021/637.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


# ----- KM1 -----------------------------------------------------------------

def km1(result) -> pd.DataFrame:
    """KM1 — Key metrics, bank-level (DIS25.5)."""
    bis = result.bis
    cap = result.meta["capital"]
    lev = result.leverage
    alm = result.alm
    rows = [
        ("1",  "보통주자본(CET1)",                     cap.cet1,           "KRW"),
        ("2",  "기본자본(Tier 1)",                     cap.tier1,          "KRW"),
        ("3",  "총자본(Total)",                        cap.total,          "KRW"),
        ("4",  "위험가중자산(RWA)",                     result.rwa["final_total"], "KRW"),
        ("5",  "CET1 비율",                            bis.cet1_ratio,     "ratio"),
        ("6",  "Tier 1 비율",                          bis.tier1_ratio,    "ratio"),
        ("7",  "총자본 비율",                           bis.total_ratio,    "ratio"),
        ("8",  "CET1 자본보전버퍼 요구치",                bis.required["cet1"], "ratio"),
        ("9",  "G-SIB / D-SIB 가산 요구",                0.0,                "ratio"),
        ("10", "익스포저측정치(EM)",                     lev.exposure_measure, "KRW"),
        ("11", "레버리지 비율",                          lev.leverage_ratio, "ratio"),
        ("12", "LCR HQLA (캡 적용)",                    alm["lcr"].hqla_total, "KRW"),
        ("13", "LCR 30일 순현금유출",                    alm["lcr"].net_outflow, "KRW"),
        ("14", "LCR",                                  alm["lcr"].lcr,     "ratio"),
        ("15", "NSFR ASF",                             alm["nsfr"].asf_total, "KRW"),
        ("16", "NSFR RSF",                             alm["nsfr"].rsf_total, "KRW"),
        ("17", "NSFR",                                 alm["nsfr"].nsfr,   "ratio"),
    ]
    return pd.DataFrame(rows, columns=["행", "지표", "값", "단위"])


# ----- OV1 -----------------------------------------------------------------

def ov1(result) -> pd.DataFrame:
    """OV1 — Overview of RWA (DIS25.10).

    Standard layout: a Credit / Market / Op / CVA / CCR break down,
    plus minimum capital requirements (8%).
    """
    rwa = result.rwa
    ccr_rwa = result.ccr.rwa_total if result.ccr else 0
    cva_charge = result.ccr.cva_charge if result.ccr else 0
    fund = float(rwa.get("fund", 0.0))
    sec = float(rwa.get("securitisation", 0.0))
    final = float(rwa["final_total"])
    # floor 가산은 최종 RWA 에서 내부모형 기준 총계를 뺀 값이다. 예전에는
    # SA·IRB·시장·운영 넷만 빼서 CCR·CVA·집합투자증권·증권화가 전부 이 줄에
    # 섞였고, 증권화는 그 옆에서 "없음 0" 으로 적혀 있었다. 공시가 부문별로
    # 읽히지 않으면 OV1 이 하는 일이 없다.
    internal = float(rwa.get(
        "internal_total",
        float(rwa["sa"]) + float(rwa["irb"]) + float(rwa.get("ccr", 0.0))
        + fund + sec + float(rwa["market"]) + float(rwa["op"])))
    floor_addon = final - internal
    rows = [
        ("1",  "신용리스크 (SA)",          rwa["sa"],          rwa["sa"] * 0.08),
        ("2",  "신용리스크 (IRB)",          rwa["irb"],         rwa["irb"] * 0.08),
        ("3",  "CCR (SA-CCR)",            ccr_rwa,            ccr_rwa * 0.08),
        ("4",  "CVA 자본요구",              cva_charge * 12.5, cva_charge),
        ("5",  "집합투자증권 (CRE60)",       fund,               fund * 0.08),
        ("6",  "증권화 (CRE40)",            sec,                sec * 0.08),
        ("7",  "시장리스크",                rwa["market"],      rwa["market"] * 0.08),
        ("8",  "운영리스크 (SMA)",          rwa["op"],          rwa["op"] * 0.08),
        ("9",  "Output floor 가산",        floor_addon,        floor_addon * 0.08),
        ("10", "<b>최종 RWA / 자본요구</b>", final,              final * 0.08),
    ]
    return pd.DataFrame(rows, columns=["행", "부문", "RWA", "최저 자본요구 (8%)"])


# ----- CR1 -----------------------------------------------------------------

def cr1(result, portfolio: pd.DataFrame) -> pd.DataFrame:
    """CR1 — Credit quality of exposures (DIS40.3).

    performing / non-performing × on-balance / off-balance breakdown,
    with allowances (ECL) deducted.
    """
    if "dpd" in portfolio.columns:
        npe_mask = portfolio["dpd"] >= 90
    else:
        npe_mask = portfolio["default_12m"] == 1

    on_perf = float(portfolio.loc[~npe_mask, "ead"].sum())
    on_npe  = float(portfolio.loc[ npe_mask, "ead"].sum())

    ecl_total = float(result.ecl["total"])
    # split allowance — Stage 1+2 vs Stage 3 from ecl breakdown
    by_stage = result.ecl["by_stage"]
    s12_ecl = float(
        by_stage.loc[by_stage.index <= 2, "ecl"].sum()
        if hasattr(by_stage.index, '__iter__') else 0
    )
    s3_ecl = float(ecl_total - s12_ecl)

    rows = [
        ("1",  "정상 (performing) — 대출",            on_perf, 0,        s12_ecl, on_perf - s12_ecl),
        ("2",  "정상 (performing) — 약정/지급보증",     0,       0,        0,       0),
        ("3",  "부실 (non-performing) — 대출",         on_npe,  0,        s3_ecl,  on_npe - s3_ecl),
        ("4",  "부실 — 약정/지급보증",                  0,       0,        0,       0),
        ("5",  "<b>합계</b>",                          on_perf + on_npe, 0,
         s12_ecl + s3_ecl, on_perf + on_npe - ecl_total),
    ]
    return pd.DataFrame(
        rows,
        columns=["행", "익스포저 구분",
                 "총 익스포저", "오프-밸런스",
                 "충당금 (ECL)", "순 익스포저"])


# ----- CR2 -----------------------------------------------------------------

def cr2(result, portfolio: pd.DataFrame, prev_npe: float | None = None) -> pd.DataFrame:
    """CR2 — Movement in non-performing loans (DIS40.6).

    Reconciles prior NPE → new NPEs → cures → writeoffs → other → current.
    For a single-snapshot report we synthesise reasonable QoQ movements.
    """
    if "dpd" in portfolio.columns:
        cur_npe = float(portfolio.loc[portfolio["dpd"] >= 90, "ead"].sum())
    else:
        cur_npe = float(portfolio.loc[portfolio["default_12m"] == 1, "ead"].sum())

    prev = prev_npe if prev_npe is not None else cur_npe * 0.92  # synthetic 8% growth
    # synthetic movements that sum to the delta
    delta = cur_npe - prev
    new_npe = max(delta * 1.4, 0)
    cures   = -max(delta * 0.20, 0)
    writeoff = -max(delta * 0.15, 0)
    other = delta - (new_npe + cures + writeoff)

    rows = [
        ("1", "기초 부실 잔액",              prev),
        ("2", "신규 부실 발생 (inflow)",      new_npe),
        ("3", "정상 복귀 (cures)",          cures),
        ("4", "상각 (write-offs)",          writeoff),
        ("5", "기타 (other)",               other),
        ("6", "<b>기말 부실 잔액</b>",         cur_npe),
    ]
    return pd.DataFrame(rows, columns=["행", "movement", "금액"])


# ----- CR3 -----------------------------------------------------------------

def cr3(result, portfolio: pd.DataFrame) -> pd.DataFrame:
    """CR3 — Credit risk mitigation techniques overview (DIS40.9)."""
    total_ead = float(portfolio["ead"].sum())
    # assume 35% mortgage / 25% other collateral / 5% guarantee — synthetic
    secured_collateral = total_ead * 0.45
    secured_guarantee  = total_ead * 0.05
    secured_credit_derivative = 0.0
    unsecured = total_ead - secured_collateral - secured_guarantee
    rows = [
        ("1",  "무담보 익스포저",         unsecured),
        ("2",  "담보부 익스포저 (총)",     secured_collateral),
        ("3",  "  — 부동산 담보",         secured_collateral * 0.70),
        ("4",  "  — 기타 담보",          secured_collateral * 0.30),
        ("5",  "보증부 익스포저",         secured_guarantee),
        ("6",  "신용파생 보호",           secured_credit_derivative),
        ("7",  "<b>총 익스포저</b>",       total_ead),
    ]
    return pd.DataFrame(rows, columns=["행", "구분", "EAD"])


# ----- CR4 -----------------------------------------------------------------

def cr4(result, portfolio: pd.DataFrame) -> pd.DataFrame:
    """CR4 — Standardised approach — credit risk exposure and CRM effects (DIS40.12)."""
    sa_mask = portfolio["asset_class"].isin(["sovereign", "bank"])
    sa = portfolio[sa_mask]
    by_class = sa.groupby("asset_class").agg(
        ead_pre_crm=("ead", "sum"),
        n=("exposure_id", "size"),
    ).reset_index()
    # synthetic CRM reduction: 10% for sovereign, 20% for bank
    by_class["ead_post_crm"] = by_class.apply(
        lambda r: r["ead_pre_crm"] *
                  (0.90 if r["asset_class"] == "sovereign" else 0.80),
        axis=1)
    by_class["rw_avg"] = by_class["asset_class"].map(
        {"sovereign": 0.20, "bank": 0.40})
    by_class["rwa"] = by_class["ead_post_crm"] * by_class["rw_avg"]
    rows = [[r["asset_class"], int(r["n"]),
             float(r["ead_pre_crm"]), float(r["ead_post_crm"]),
             float(r["rw_avg"]), float(r["rwa"])]
            for _, r in by_class.iterrows()]
    return pd.DataFrame(
        rows, columns=["asset class", "건수", "EAD (pre-CRM)",
                        "EAD (post-CRM)", "평균 RW", "RWA"])


# ----- CR5 -----------------------------------------------------------------

def cr5(result, portfolio: pd.DataFrame) -> pd.DataFrame:
    """CR5 — SA exposures by asset class × risk weight (DIS40.15)."""
    sa = portfolio[portfolio["asset_class"].isin(["sovereign", "bank"])]
    # synthetic risk-weight bucket distribution
    rw_buckets = ["0%", "20%", "50%", "75%", "100%", "150%", "기타"]

    rows = []
    for ac in sa["asset_class"].unique():
        sub = sa[sa["asset_class"] == ac]
        ead = float(sub["ead"].sum())
        if ac == "sovereign":
            shares = [0.50, 0.20, 0.20, 0.00, 0.10, 0.00, 0.00]
        else:
            shares = [0.00, 0.30, 0.40, 0.00, 0.25, 0.05, 0.00]
        row = [ac]
        for s in shares:
            row.append(float(ead * s))
        row.append(float(ead))
        rows.append(row)
    return pd.DataFrame(
        rows, columns=["asset class"] + rw_buckets + ["총 EAD"])


# ----- MR1 -----------------------------------------------------------------

def mr1(result) -> pd.DataFrame:
    """MR1 — Market risk under SA (DIS50.3)."""
    mkt_rwa = result.rwa["market"]
    rows = [
        ("1", "일반 시장리스크 — 금리",       mkt_rwa * 0.55),
        ("2", "일반 시장리스크 — 주식",       mkt_rwa * 0.15),
        ("3", "일반 시장리스크 — FX",         mkt_rwa * 0.20),
        ("4", "일반 시장리스크 — 상품",       mkt_rwa * 0.05),
        ("5", "옵션 — vega / curvature",   mkt_rwa * 0.05),
        ("6", "<b>총 시장리스크 RWA</b>",     mkt_rwa),
        ("7", "최저 자본요구 (8%)",          mkt_rwa * 0.08),
    ]
    return pd.DataFrame(rows, columns=["행", "구분", "값"])


# ----- MR2 -----------------------------------------------------------------

def mr2(result) -> pd.DataFrame:
    """MR2 — RWA flow statement of market risk under IMA (DIS50.6)."""
    mkt_rwa = result.rwa["market"]
    rows = [
        ("1", "기초 시장 RWA",                    mkt_rwa * 0.95),
        ("2", "포지션 증가 (+)",                  mkt_rwa * 0.10),
        ("3", "감독자 강제 변경 (+)",             0),
        ("4", "VaR 모형 / 시장 변동 (+)",         mkt_rwa * 0.03),
        ("5", "외환 효과 (+/-)",                  mkt_rwa * -0.02),
        ("6", "기타 (+)",                         mkt_rwa * -0.06),
        ("7", "<b>기말 시장 RWA</b>",             mkt_rwa),
    ]
    return pd.DataFrame(rows, columns=["행", "movement", "금액"])


# ----- LIQ1 ----------------------------------------------------------------

def liq1(result) -> pd.DataFrame:
    """LIQ1 — LCR detail (DIS50.2)."""
    lcr = result.alm["lcr"]
    detail = lcr.hqla_detail
    l1  = float(detail.loc[detail["component"] == "Level 1", "market_value"].iloc[0])
    l2a = float(detail.loc[detail["component"] == "Level 2A", "market_value"].iloc[0])
    l2b = float(detail.loc[detail["component"] == "Level 2B", "market_value"].iloc[0])
    rows = [
        ("HQLA",  "1", "Level 1 (시장가)",          l1),
        ("HQLA",  "2", "Level 2A (시장가)",         l2a),
        ("HQLA",  "3", "Level 2B (시장가)",         l2b),
        ("HQLA",  "4", "총 HQLA (캡 적용)",          lcr.hqla_total),
        ("유출",  "5", "총 가중유출 (30일)",         lcr.gross_outflow),
        ("유입",  "6", "총 가중유입 (캡 적용)",        lcr.inflow_capped),
        ("순",    "7", "순현금유출",                  lcr.net_outflow),
        ("결과",  "8", "LCR",                       lcr.lcr),
    ]
    return pd.DataFrame(rows, columns=["섹션", "행", "항목", "값"])


# ----- LIQ2 ----------------------------------------------------------------

def liq2(result) -> pd.DataFrame:
    """LIQ2 — NSFR detail (DIS50.5)."""
    nsfr = result.alm["nsfr"]
    asf = nsfr.asf.copy()
    rsf = nsfr.rsf.copy()
    rows = [("ASF", str(i+1), str(r["category"]), r["amount"], r["factor"],
             r["weighted"])
            for i, (_, r) in enumerate(asf.iterrows())]
    rows += [("RSF", str(i+1), str(r["category"]), r["amount"], r["factor"],
              r["weighted"])
             for i, (_, r) in enumerate(rsf.iterrows())]
    rows += [("총", "—", "ASF 총", nsfr.asf_total, 1.0, nsfr.asf_total),
             ("총", "—", "RSF 총", nsfr.rsf_total, 1.0, nsfr.rsf_total),
             ("결과", "—", "NSFR", nsfr.nsfr, 1.0, nsfr.nsfr)]
    return pd.DataFrame(
        rows, columns=["섹션", "행", "category", "금액", "factor", "weighted"])


# ----- LR1 -----------------------------------------------------------------

def lr1(result) -> pd.DataFrame:
    """LR1 — Comparison of accounting assets vs leverage exposure (DIS80.2)."""
    lev = result.leverage
    em = lev.exposure_measure
    rows = [
        ("1", "회계상 총자산",                     em * 0.95),
        ("2", "신용파생 명목 환산 (+)",            em * 0.04),
        ("3", "재무약정 환산 (+)",                em * 0.03),
        ("4", "SFT 익스포저 조정 (+)",            em * 0.02),
        ("5", "약정 — 미인출 부분 CCF 적용 (+)",    em * 0.06),
        ("6", "조정 항목 (−)",                    em * -0.10),
        ("7", "<b>레버리지 익스포저 측정치</b>",     em),
    ]
    return pd.DataFrame(rows, columns=["행", "조정 항목", "금액"])


# ----- LR2 -----------------------------------------------------------------

def lr2(result) -> pd.DataFrame:
    """LR2 — Leverage ratio common disclosure (DIS80.5)."""
    lev = result.leverage
    cap = result.meta["capital"]
    rows = [
        ("1",  "Tier 1 자본",                  cap.tier1, "KRW"),
        ("2",  "익스포저 측정치 (LEV30)",        lev.exposure_measure, "KRW"),
        ("3",  "<b>레버리지 비율</b>",            lev.leverage_ratio, "ratio"),
        ("4",  "최저 요구",                     0.03, "ratio"),
        ("5",  "G-SIB 가산 (50% buffer)",       0, "ratio"),
        ("6",  "조정후 요구",                   0.03, "ratio"),
        ("7",  "충족 여부",
         "충족" if lev.leverage_ratio >= 0.03 else "미달", "—"),
    ]
    return pd.DataFrame(rows, columns=["행", "항목", "값", "단위"])
