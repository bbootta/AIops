"""Pillar 3 disclosure templates (BCBS DIS) — legacy summary cut.

.. deprecated::
    Superseded by :mod:`risk_lib.pillar3_disclosures`, which implements the
    full 13-template set (KM1/OV1/CR1-5/MR1-2/LIQ1-2/LR1-2) with 행/지표/값/
    단위 columns and backs ops page 59 (Pillar 3 Full). This module remains
    only for ops page 20 (summary view); add new templates to
    pillar3_disclosures, not here.

Implemented:
  - KM1  : Key metrics
  - OV1  : Overview of RWA
  - CR1  : Credit quality of exposures (performing / non-performing)
  - LIQ1 : LCR (already covered in ALM module; this is the disclosure cut)
  - LR1  : Leverage ratio common disclosure
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def km1(result: Any) -> pd.DataFrame:
    """KM1 — Key metrics (DIS25.5)."""
    bis = result.bis; rwa = result.rwa; lev = result.leverage
    alm = result.alm; cap = result.meta["capital"]
    rows = [
        ("1",  "보통주자본(CET1)",                            cap.cet1),
        ("2",  "기본자본(Tier 1)",                            cap.tier1),
        ("3",  "총자본(Total)",                               cap.total),
        ("4",  "위험가중자산(RWA)",                            rwa["final_total"]),
        ("5",  "CET1 비율",                                   bis.cet1_ratio),
        ("6",  "Tier 1 비율",                                 bis.tier1_ratio),
        ("7",  "총자본 비율",                                  bis.total_ratio),
        ("8",  "CET1 자본보전버퍼 요구치",                       bis.required["cet1"]),
        ("9",  "익스포저측정치(EM)",                            lev.exposure_measure),
        ("10", "레버리지 비율",                                lev.leverage_ratio),
        ("11", "LCR HQLA",                                    alm["lcr"].hqla_total),
        ("12", "LCR 순현금유출",                               alm["lcr"].net_outflow),
        ("13", "LCR",                                         alm["lcr"].lcr),
        ("14", "NSFR ASF",                                    alm["nsfr"].asf_total),
        ("15", "NSFR RSF",                                    alm["nsfr"].rsf_total),
        ("16", "NSFR",                                        alm["nsfr"].nsfr),
    ]
    return pd.DataFrame(rows, columns=["행", "지표", "값"])


def ov1(result: Any) -> pd.DataFrame:
    """OV1 — Overview of RWA (DIS25.10).

    부문은 산출 결과의 구성요소를 그대로 적는다. 예전에는 CCR/CVA 와 증권화를
    "없음 0" 으로 적고 남는 차액을 전부 Output floor 가산 줄에 넣었다. 두 부문은
    산출되고 자본비율 분모에도 들어가 있었으므로 그 줄은 공시에서만 0이었고,
    floor 가산 줄은 두 부문의 합을 삼킨 잔차였다. 잔차를 한 줄에 몰아넣으면
    어느 부문이 얼마인지 공시가 말하지 못한다.

    floor 가산은 최종 RWA 에서 내부모형 기준 총계를 뺀 값이다. 그 총계를 결과가
    가지고 있지 않으면(구형 result) 부문 합으로 대신하며, 둘은 같은 정의다.
    부문 줄의 합은 최종 합계와 같다. 소계 줄을 따로 두지 않는 이유는 그 줄이
    합에 두 번 들어가기 때문이다.
    """
    rwa = result.rwa
    sa = float(rwa["sa"])
    irb = float(rwa["irb"])
    ccr = float(rwa.get("ccr", 0.0))
    fund = float(rwa.get("fund", 0.0))
    sec = float(rwa.get("securitisation", 0.0))
    market = float(rwa["market"])
    op = float(rwa["op"])
    final = float(rwa["final_total"])
    internal = float(rwa.get("internal_total",
                             sa + irb + ccr + fund + sec + market + op))
    rows = [
        ("신용리스크 (SA)",       sa),
        ("신용리스크 (IRB)",       irb),
        ("CCR/CVA",               ccr),
        ("집합투자증권 (CRE60)",   fund),
        ("증권화 (CRE40)",         sec),
        ("시장리스크",            market),
        ("운영리스크",            op),
        ("Output floor 가산",     final - internal),
        ("최종 합계",             final),
    ]
    return pd.DataFrame(rows, columns=["부문", "RWA"])


def cr1(result: Any, portfolio: pd.DataFrame) -> pd.DataFrame:
    """CR1 — Credit quality of exposures, performing vs non-performing
    (Basel DIS40.3)."""
    npe_mask = portfolio["dpd"] >= 90 if "dpd" in portfolio.columns else \
               portfolio["default_12m"] == 1
    perf = portfolio.loc[~npe_mask, "ead"].sum() if "ead" in portfolio.columns else 0
    npl  = portfolio.loc[npe_mask, "ead"].sum() if "ead" in portfolio.columns else 0
    coverage = result.ecl["total"] / (perf + npl) if (perf + npl) else 0
    rows = [
        ("performing exposures",      perf),
        ("non-performing exposures",  npl),
        ("총 익스포저",                perf + npl),
        ("ECL (커버리지 측정)",         result.ecl["total"]),
        ("커버리지율",                 coverage),
        ("NPL 비율",                  npl / (perf + npl) if (perf + npl) else 0),
    ]
    return pd.DataFrame(rows, columns=["항목", "값"])


def liq1(result: Any) -> pd.DataFrame:
    """LIQ1 — LCR common disclosure (DIS50.2)."""
    lcr = result.alm["lcr"]
    rows = [
        ("Level 1 HQLA (시장가)", lcr.hqla_detail.loc[0, "market_value"]),
        ("Level 2A HQLA (시장가)", lcr.hqla_detail.loc[1, "market_value"]),
        ("Level 2B HQLA (시장가)", lcr.hqla_detail.loc[2, "market_value"]),
        ("총 HQLA (캡 적용)", lcr.hqla_total),
        ("총 가중유출 (30일)", lcr.gross_outflow),
        ("총 가중유입 (캡 적용)", lcr.inflow_capped),
        ("순현금유출", lcr.net_outflow),
        ("LCR", lcr.lcr),
    ]
    return pd.DataFrame(rows, columns=["항목", "값"])


def lr1(result: Any) -> pd.DataFrame:
    """LR1 — Leverage common disclosure (DIS80.2)."""
    lev = result.leverage
    rows = [
        ("Tier 1 자본",      lev.tier1_capital
                              if hasattr(lev, "tier1_capital") else
                              result.meta["capital"].tier1),
        ("익스포저측정치",    lev.exposure_measure),
        ("레버리지 비율",     lev.leverage_ratio),
        ("최저 요구",        lev.required),
    ]
    return pd.DataFrame(rows, columns=["항목", "값"])
