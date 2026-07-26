"""금감원 업무보고서 서식 정의와 값 채움.

**서식번호에 관한 전제** — 금융감독원이 배포하는 업무보고서 서식 파일이
입력으로 주어지지 않았다. 따라서 이 모듈은 은행업감독규정·동 시행세칙과
Basel 기준에서 각 서식이 요구하는 **항목 구조**를 재구성하고 내부 식별자
(BR-01 …)를 쓴다. 배포본과 연결할 때는 `reg_form.form_id ↔ 배포 서식번호`
매핑 한 장만 추가하면 되고, 라인 코드·산식·규정근거는 그대로 쓸 수 있다.
없는 서식번호를 지어내지 않는 것이 매핑을 나중에 틀리게 하지 않는 길이다.

각 라인은 값뿐 아니라 **산식·규정근거·산출 모듈**을 함께 남긴다. 감독당국
질의에 "이 숫자는 어디서 나왔는가"로 답할 수 있어야 제출본이 성립한다.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import pandas as pd

from risk_lib.regulatory.form_ids import form_id


# 자료구조는 forms_base로 옮겼다 — 빌더 모듈이 forms.py를 import하면 순환이
# 되기 때문이다. 기존 호출부가 forms.FormLine 을 쓰므로 여기서 다시 내보낸다.
from risk_lib.regulatory.forms_base import (      # noqa: E402,F401
    BuiltForm, FormCheck, FormLine, FormSpec, _ratio_check, _sum_check, _val,
)


# ---------------------------------------------------------------- BR-01

def _br01(ctx) -> BuiltForm:
    r = ctx.result
    cap = r.meta["capital"]
    rwa = r.rwa
    fl = rwa["output_floor"]
    M = "risk_lib.capital.bis · risk_lib.capital.output_floor"
    L = [
        FormLine("1000", "자기자본 (총자본)", 0, "KRW", cap.total,
                 formula="보통주자본 + 기타기본자본 + 보완자본",
                 citation="은행업감독규정 제26조 · Basel III CRE40",
                 source_module=M, is_subtotal=True),
        FormLine("1100", "보통주자본 (CET1)", 1, "KRW", cap.cet1,
                 citation="CRE40.1~40.26", source_module=M),
        FormLine("1200", "기타기본자본 (AT1)", 1, "KRW", cap.additional_t1,
                 citation="CRE40.27~40.41", source_module=M),
        FormLine("1300", "보완자본 (Tier 2)", 1, "KRW", cap.tier2,
                 citation="CRE40.42~40.56", source_module=M),
        FormLine("1400", "기본자본 (Tier 1)", 1, "KRW", cap.tier1,
                 formula="보통주자본 + 기타기본자본", source_module=M,
                 is_subtotal=True),

        FormLine("2000", "위험가중자산 합계", 0, "KRW", rwa["final_total"],
                 formula="신용 + 시장 + 운영 + 산출하한 조정",
                 citation="CRE20.1 · RBC20", source_module=M, is_subtotal=True),
        FormLine("2100", "신용리스크", 1, "KRW", rwa["credit_internal"],
                 source_module="risk_lib.capital.rwa_sa · rwa_irb",
                 is_subtotal=True),
        FormLine("2110", "표준방법 (SA)", 2, "KRW", rwa["sa"],
                 citation="CRE20", source_module="risk_lib.capital.rwa_sa"),
        FormLine("2120", "내부등급법 (IRB)", 2, "KRW", rwa["irb"],
                 citation="CRE31 · CRE32",
                 source_module="risk_lib.capital.rwa_irb"),
        FormLine("2130", "거래상대방신용리스크 (SA-CCR + CVA)", 2, "KRW",
                 float(rwa.get("ccr", 0.0)),
                 formula="SA-CCR RWA + CVA 소요자본",
                 citation="CRE52 · MAR50", source_module="risk_lib.ccr"),
        FormLine("2200", "시장리스크", 1, "KRW", rwa["market"],
                 citation="MAR40", source_module="risk_lib.capital.market_risk"),
        FormLine("2300", "운영리스크", 1, "KRW", rwa["op"],
                 citation="OPE25 신표준방법",
                 source_module="risk_lib.capital.op_risk"),
        FormLine("2400", "산출하한 조정분", 1, "KRW", float(fl.add_on),
                 formula="max(0, 표준방법 RWA × 하한율 − 내부모형 RWA)",
                 citation="RBC20.11",
                 source_module="risk_lib.capital.output_floor"),

        FormLine("3100", "보통주자본비율", 0, "ratio", r.bis.cet1_ratio,
                 formula="보통주자본 ÷ 위험가중자산", citation="은행업감독규정 제26조",
                 source_module=M),
        FormLine("3200", "기본자본비율", 0, "ratio", r.bis.tier1_ratio,
                 formula="기본자본 ÷ 위험가중자산", source_module=M),
        FormLine("3300", "총자본비율", 0, "ratio", r.bis.total_ratio,
                 formula="자기자본 ÷ 위험가중자산", source_module=M),

        FormLine("4100", "보통주자본비율 최저기준", 1, "ratio", 0.045,
                 citation="은행업감독규정 제26조 제1항"),
        FormLine("4200", "기본자본비율 최저기준", 1, "ratio", 0.06,
                 citation="은행업감독규정 제26조 제1항"),
        FormLine("4300", "총자본비율 최저기준", 1, "ratio", 0.08,
                 citation="은행업감독규정 제26조 제1항"),
        FormLine("4400", "자본보전완충자본", 1, "ratio", 0.025,
                 citation="은행업감독규정 제26조의2"),
        FormLine("4500", "경기대응완충자본", 1, "ratio", 0.0,
                 citation="은행업감독규정 제26조의3"),
        FormLine("4600", "시스템적 중요 은행 추가자본", 1, "ratio", 0.01,
                 citation="은행업감독규정 제26조의4"),
        FormLine("4700", "요구 총자본비율 (버퍼 포함)", 0, "ratio",
                 r.bis.required["total"], formula="최저기준 + 완충자본 합계",
                 source_module=M, is_subtotal=True),

        FormLine("5100", "보통주자본비율 잉여(+)·부족(−)", 0, "ratio",
                 r.bis.surplus_shortfall["cet1"], source_module=M),
        FormLine("5200", "기본자본비율 잉여(+)·부족(−)", 0, "ratio",
                 r.bis.surplus_shortfall["tier1"], source_module=M),
        FormLine("5300", "총자본비율 잉여(+)·부족(−)", 0, "ratio",
                 r.bis.surplus_shortfall["total"], source_module=M),
    ]
    checks = [
        _sum_check("자기자본 = CET1+AT1+T2", L, "1000", ("1100", "1200", "1300")),
        _sum_check("기본자본 = CET1+AT1", L, "1400", ("1100", "1200")),
        _sum_check("신용RWA = SA+IRB+CCR", L, "2100",
                   ("2110", "2120", "2130")),
        _sum_check("총RWA = 신용+시장+운영+하한", L, "2000",
                   ("2100", "2200", "2300", "2400")),
        _ratio_check("보통주자본비율 = CET1/RWA", L, "3100", "1100", "2000", 1e-9),
        _ratio_check("총자본비율 = 자기자본/RWA", L, "3300", "1000", "2000", 1e-9),
        FormCheck("요구비율 = 최저 + 완충", _val(L, "4700"),
                  _val(L, "4300") + _val(L, "4400") + _val(L, "4500")
                  + _val(L, "4600"), 1e-9),
    ]
    return BuiltForm(FORMS_BY_ID["BR-01"], L, checks)


# ---------------------------------------------------------------- BR-02

def _capital_detail_lines(tbl: pd.DataFrame, prefix: str, title: str,
                          level0_code: str, total: float) -> list[FormLine]:
    lines = [FormLine(level0_code, title, 0, "KRW", total,
                      formula="가산항목 − 차감항목", is_subtotal=True,
                      source_module="risk_lib.capital.bis_deep")]
    for i, (_, row) in enumerate(tbl.iterrows(), start=1):
        lines.append(FormLine(
            f"{prefix}{i:02d}", str(row["item"]), 1, "KRW", float(row["amount"]),
            formula=f"{row['sign']} 부호 적용", citation=str(row["ref"]),
            source_module="risk_lib.capital.bis_deep"))
    return lines


def _br02(ctx) -> BuiltForm:
    r = ctx.result
    cap = r.meta["capital"]
    bd = r.bis_deep
    L = (_capital_detail_lines(bd.cet1_table, "11", "보통주자본 (CET1) 명세",
                               "1100", cap.cet1)
         + _capital_detail_lines(bd.at1_table, "12", "기타기본자본 (AT1) 명세",
                                 "1200", cap.additional_t1)
         + _capital_detail_lines(bd.tier2_table, "13", "보완자본 (Tier 2) 명세",
                                 "1300", cap.tier2))
    # 명세 합계는 총괄서식(BR-01)의 자본금액과 일치해야 한다.
    checks = []
    for code, tbl, amount in (("1100", bd.cet1_table, cap.cet1),
                              ("1200", bd.at1_table, cap.additional_t1),
                              ("1300", bd.tier2_table, cap.tier2)):
        checks.append(FormCheck(f"{code} 명세 합계 = 자본금액",
                                float(amount), float(tbl["amount"].sum()), 1.0))
    return BuiltForm(FORMS_BY_ID["BR-02"], L, checks)


# ---------------------------------------------------------------- BR-03 / 04

def _br03(ctx) -> BuiltForm:
    t = ctx.tables["rwa_sa_bucket"].sort_values(
        ["asset_class", "rating_bucket", "risk_weight"])
    L: list[FormLine] = []
    M = "risk_lib.datamodel.materialize_detail.materialize_rwa_detail"
    total_ead = float(t["ead"].sum())
    total_rwa = float(t["rwa"].sum())
    L.append(FormLine("1000", "표준방법 합계 — 위험가중자산", 0, "KRW", total_rwa,
                      citation="CRE20", source_module=M, is_subtotal=True))
    L.append(FormLine("1010", "표준방법 합계 — 익스포저(EAD)", 0, "KRW", total_ead,
                      source_module=M, is_subtotal=True))
    L.append(FormLine("1020", "표준방법 합계 — 소요자기자본", 0, "KRW",
                      total_rwa * 0.08, formula="위험가중자산 × 8%",
                      citation="CRE20.1", source_module=M, is_subtotal=True))
    ac_codes, i = {}, 0
    for ac, sub in t.groupby("asset_class"):
        i += 1
        ac_code = f"{1000 + i * 100}"
        ac_codes[ac] = ac_code
        L.append(FormLine(ac_code, f"자산군 · {ac}", 1, "KRW",
                          float(sub["rwa"].sum()), source_module=M,
                          is_subtotal=True))
        for j, (_, row) in enumerate(sub.iterrows(), start=1):
            L.append(FormLine(
                f"{ac_code}{j:02d}",
                f"{row['rating_bucket']} · 위험가중치 {row['risk_weight']:.0%}",
                2, "KRW", float(row["rwa"]),
                formula=f"EAD {row['ead']:,.0f} × RW {row['risk_weight']:.4f}",
                citation="CRE20.4 ECRA · CRE20.82 LTV 구간", source_module=M))
    checks = [
        FormCheck("자산군 소계 합 = 표준방법 합계", total_rwa,
                  sum(_val(L, c) for c in ac_codes.values()), 1.0),
        FormCheck("소요자기자본 = RWA × 8%", total_rwa * 0.08,
                  _val(L, "1020"), 1.0),
    ]
    return BuiltForm(FORMS_BY_ID["BR-03"], L, checks)


def _br04(ctx) -> BuiltForm:
    t = ctx.tables["rwa_irb_pool"].sort_values(["asset_class", "pd_band"])
    M = "risk_lib.datamodel.materialize_detail.materialize_rwa_detail"
    L = [
        FormLine("1000", "내부등급법 합계 — 위험가중자산", 0, "KRW",
                 float(t["rwa"].sum()), citation="CRE31 · CRE32",
                 source_module=M, is_subtotal=True),
        FormLine("1010", "내부등급법 합계 — 익스포저(EAD)", 0, "KRW",
                 float(t["ead"].sum()), source_module=M, is_subtotal=True),
        FormLine("1020", "내부등급법 합계 — 기대손실(EL)", 0, "KRW",
                 float(t["expected_loss"].sum()),
                 formula="Σ PD × LGD × EAD", citation="CRE31.4",
                 source_module=M, is_subtotal=True),
    ]
    ac_codes, i = {}, 0
    for ac, sub in t.groupby("asset_class"):
        i += 1
        ac_code = f"{1000 + i * 100}"
        ac_codes[ac] = ac_code
        L.append(FormLine(ac_code, f"자산군 · {ac}", 1, "KRW",
                          float(sub["rwa"].sum()), source_module=M,
                          is_subtotal=True))
        for j, (_, row) in enumerate(sub.iterrows(), start=1):
            L.append(FormLine(
                f"{ac_code}{j:02d}", f"PD 구간 {row['pd_band']}", 2, "KRW",
                float(row["rwa"]),
                formula=(f"EAD {row['ead']:,.0f} · PD {row['pd_weighted']:.4%} · "
                         f"LGD {row['lgd_weighted']:.2%} · M {row['maturity_weighted']:.2f}y"),
                citation="CRE32.2 위험가중함수 · Pillar 3 CR6",
                source_module=M))
    checks = [FormCheck("자산군 소계 합 = 내부등급법 합계",
                        float(t["rwa"].sum()),
                        sum(_val(L, c) for c in ac_codes.values()), 1.0)]
    return BuiltForm(FORMS_BY_ID["BR-04"], L, checks)


# ---------------------------------------------------------------- BR-05 / 06

def _br05(ctx) -> BuiltForm:
    t = ctx.tables["rwa_market_component"].sort_values("risk_class")
    M = "risk_lib.capital.market_risk"
    L = [FormLine("1000", "시장리스크 소요자기자본 합계", 0, "KRW",
                  float(t["capital"].sum()), citation="MAR40 간편표준방법",
                  source_module=M, is_subtotal=True),
         FormLine("1010", "시장리스크 위험가중자산", 0, "KRW",
                  float(t["rwa"].sum()), formula="소요자기자본 × 12.5",
                  citation="CRE20.1", source_module=M, is_subtotal=True)]
    for i, (_, row) in enumerate(t.iterrows(), start=1):
        L.append(FormLine(f"11{i:02d}", f"위험군 · {row['risk_class']}", 1, "KRW",
                          float(row["capital"]),
                          formula=f"순포지션 {row['position']:,.0f} × 위험계수",
                          citation="MAR40", source_module=M))
    checks = [
        FormCheck("위험군 합 = 소요자기자본 합계", float(t["capital"].sum()),
                  sum(float(x) for x in t["capital"]), 1.0),
        FormCheck("RWA = 소요자기자본 × 12.5", float(t["capital"].sum()) * 12.5,
                  float(t["rwa"].sum()), 1.0),
    ]
    return BuiltForm(FORMS_BY_ID["BR-05"], L, checks)


def _br06(ctx) -> BuiltForm:
    od = ctx.result.rwa["op_detail"]
    bi_t = ctx.tables["rwa_operational_bi"].sort_values("component")
    M = "risk_lib.capital.op_risk"
    L = [FormLine("1000", "사업지표 (BI)", 0, "KRW", float(od.bi),
                  formula="ILDC + SC + FC", citation="OPE25.3",
                  source_module=M, is_subtotal=True)]
    for i, (_, row) in enumerate(bi_t.iterrows(), start=1):
        L.append(FormLine(f"10{i:02d}", f"BI 구성 · {row['component']}", 1, "KRW",
                          float(row["amount"]),
                          formula=f"구성비 {row['share']:.1%}",
                          citation="OPE25.3", source_module=M))
    L += [
        FormLine("2000", "사업지표요소 (BIC)", 0, "KRW", float(od.bic),
                 formula="BI 구간별 한계계수 적용 합", citation="OPE25.5",
                 source_module=M, is_subtotal=True),
        FormLine("3000", "내부손실승수 (ILM)", 0, "ratio", float(od.ilm),
                 formula="ln(e−1 + (LC/BIC)^0.8)", citation="OPE25.9",
                 source_module=M),
        FormLine("4000", "운영리스크 소요자기자본 (ORC)", 0, "KRW", float(od.orc),
                 formula="BIC × ILM", citation="OPE25.2", source_module=M,
                 is_subtotal=True),
        FormLine("5000", "운영리스크 위험가중자산", 0, "KRW", float(od.rwa),
                 formula="ORC × 12.5", citation="CRE20.1", source_module=M,
                 is_subtotal=True),
    ]
    checks = [
        FormCheck("BI = 구성요소 합", float(od.bi),
                  float(bi_t["amount"].sum()), 1.0),
        FormCheck("ORC = BIC × ILM", float(od.bic) * float(od.ilm),
                  float(od.orc), 1.0),
        FormCheck("RWA = ORC × 12.5", float(od.orc) * 12.5, float(od.rwa), 1.0),
    ]
    return BuiltForm(FORMS_BY_ID["BR-06"], L, checks)


# ---------------------------------------------------------------- BR-07

def _br07(ctx) -> BuiltForm:
    lev = ctx.result.leverage
    M = "risk_lib.capital.leverage"
    L = [
        FormLine("1000", "기본자본 (Tier 1)", 0, "KRW", float(lev.tier1),
                 citation="LEV20.5", source_module=M),
        FormLine("2000", "총익스포저 (익스포저 측정치)", 0, "KRW",
                 float(lev.exposure_measure),
                 formula="온밸런스 + 파생 + SFT + 부외 환산",
                 citation="LEV30", source_module=M, is_subtotal=True),
        FormLine("3000", "레버리지비율", 0, "ratio", float(lev.leverage_ratio),
                 formula="기본자본 ÷ 총익스포저", citation="LEV20.1",
                 source_module=M),
        FormLine("4000", "최저 레버리지비율", 0, "ratio", float(lev.required),
                 citation="LEV20.2 · 은행업감독규정 제26조 제1항 제4호"),
        FormLine("5000", "잉여(+)·부족(−)", 0, "ratio",
                 float(lev.surplus_shortfall), source_module=M),
    ]
    checks = [
        _ratio_check("레버리지비율 = Tier1/총익스포저", L, "3000", "1000", "2000"),
        FormCheck("잉여 = 실측 − 최저", float(lev.leverage_ratio - lev.required),
                  float(lev.surplus_shortfall), 1e-12),
    ]
    return BuiltForm(FORMS_BY_ID["BR-07"], L, checks)


# ---------------------------------------------------------------- BR-08 / 09

def _br08(ctx) -> BuiltForm:
    lcr = ctx.result.alm["lcr"]
    t = ctx.tables["alm_lcr_item"]
    M = "risk_lib.alm.lcr"
    L = [FormLine("1000", "고유동성자산 (HQLA) 합계", 0, "KRW",
                  float(lcr.hqla_total), citation="LCR30", source_module=M,
                  is_subtotal=True)]
    for i, (_, row) in enumerate(t[t["section"] == "HQLA"].iterrows(), start=1):
        L.append(FormLine(f"10{i:02d}", str(row["category"]), 1, "KRW",
                          float(row["weighted"]),
                          formula=f"시가 {row['amount']:,.0f} × (1 − haircut {row['factor']:.0%})",
                          citation=str(row["citation"]), source_module=M))
    L.append(FormLine("2000", "총 현금유출액", 0, "KRW", float(lcr.gross_outflow),
                      citation="LCR40", source_module=M, is_subtotal=True))
    for i, (_, row) in enumerate(t[t["section"] == "OUTFLOW"].iterrows(), start=1):
        L.append(FormLine(f"20{i:02d}", str(row["category"]), 1, "KRW",
                          float(row["weighted"]),
                          formula=f"잔액 {row['amount']:,.0f} × 이탈률 {row['factor']:.0%}",
                          citation=str(row["citation"]), source_module=M))
    L.append(FormLine("3000", "인정 현금유입액", 0, "KRW",
                      float(lcr.inflow_capped),
                      formula="min(총유입, 총유출 × 75%)", citation="LCR40.61",
                      source_module=M, is_subtotal=True))
    for i, (_, row) in enumerate(t[t["section"] == "INFLOW"].iterrows(), start=1):
        L.append(FormLine(f"30{i:02d}", str(row["category"]), 1, "KRW",
                          float(row["weighted"]),
                          formula=f"잔액 {row['amount']:,.0f} × 인식률 {row['factor']:.0%}",
                          citation=str(row["citation"]), source_module=M))
    L += [
        FormLine("4000", "순현금유출액", 0, "KRW", float(lcr.net_outflow),
                 formula="총유출 − 인정유입", citation="LCR40.1",
                 source_module=M, is_subtotal=True),
        FormLine("5000", "유동성커버리지비율 (LCR)", 0, "ratio", float(lcr.lcr),
                 formula="HQLA ÷ 순현금유출액", citation="LCR20.1",
                 source_module=M),
        FormLine("6000", "규제 최저비율", 0, "ratio", 1.0,
                 citation="은행업감독규정 제26조 제1항 · LCR20.1"),
    ]
    checks = [
        _sum_check("순현금유출 = 총유출 − 인정유입 (부호 확인)", L, "4000",
                   ("2000",), tol=float(lcr.inflow_capped) + 1.0),
        _ratio_check("LCR = HQLA/순현금유출", L, "5000", "1000", "4000", 1e-9),
        FormCheck("HQLA 합계 = 항목별 인정액 합", float(lcr.hqla_total),
                  float(t[t["section"] == "HQLA"]["weighted"].sum()), 1.0),
        FormCheck("총유출 = 항목별 유출 합", float(lcr.gross_outflow),
                  float(t[t["section"] == "OUTFLOW"]["weighted"].sum()), 1.0),
    ]
    return BuiltForm(FORMS_BY_ID["BR-08"], L, checks)


def _br09(ctx) -> BuiltForm:
    n = ctx.result.alm["nsfr"]
    t = ctx.tables["alm_nsfr_item"]
    M = "risk_lib.alm.nsfr"
    L = [FormLine("1000", "가용안정자금 (ASF) 합계", 0, "KRW",
                  float(n.asf_total), citation="NSF20", source_module=M,
                  is_subtotal=True)]
    for i, (_, row) in enumerate(t[t["section"] == "ASF"].iterrows(), start=1):
        L.append(FormLine(f"10{i:02d}", str(row["category"]), 1, "KRW",
                          float(row["weighted"]),
                          formula=f"잔액 {row['amount']:,.0f} × 인정률 {row['factor']:.0%}",
                          citation="NSF20.4~20.14", source_module=M))
    L.append(FormLine("2000", "필요안정자금 (RSF) 합계", 0, "KRW",
                      float(n.rsf_total), citation="NSF30", source_module=M,
                      is_subtotal=True))
    for i, (_, row) in enumerate(t[t["section"] == "RSF"].iterrows(), start=1):
        L.append(FormLine(f"20{i:02d}", str(row["category"]), 1, "KRW",
                          float(row["weighted"]),
                          formula=f"잔액 {row['amount']:,.0f} × 소요율 {row['factor']:.0%}",
                          citation="NSF30.4~30.16", source_module=M))
    L += [
        FormLine("3000", "순안정자금조달비율 (NSFR)", 0, "ratio", float(n.nsfr),
                 formula="ASF ÷ RSF", citation="NSF20.1", source_module=M),
        FormLine("4000", "규제 최저비율", 0, "ratio", 1.0,
                 citation="은행업감독규정 제26조 · NSF20.1"),
    ]
    checks = [
        FormCheck("ASF 합계 = 항목 합", float(n.asf_total),
                  float(t[t["section"] == "ASF"]["weighted"].sum()), 1.0),
        FormCheck("RSF 합계 = 항목 합", float(n.rsf_total),
                  float(t[t["section"] == "RSF"]["weighted"].sum()), 1.0),
        _ratio_check("NSFR = ASF/RSF", L, "3000", "1000", "2000", 1e-9),
    ]
    return BuiltForm(FORMS_BY_ID["BR-09"], L, checks)


# ---------------------------------------------------------------- BR-10 / 11

_AQ_ORDER = ("정상", "요주의", "고정", "회수의문", "추정손실")


def _br10(ctx) -> BuiltForm:
    t = ctx.tables["rdm_asset_quality"]
    M = "risk_lib.datamodel.materialize_detail.materialize_rdm_detail"
    L = [
        FormLine("1000", "총 여신 잔액", 0, "KRW", float(t["balance"].sum()),
                 citation="은행업감독규정 제27조", source_module=M,
                 is_subtotal=True),
        FormLine("1010", "총 여신 건수", 0, "count", float(len(t)),
                 source_module=M, is_subtotal=True),
    ]
    for bi, bt in enumerate(("기업여신", "가계여신"), start=1):
        sub = t[t["borrower_type"] == bt]
        base = 2000 + (bi - 1) * 1000
        L.append(FormLine(f"{base}", f"{bt} 소계", 0, "KRW",
                          float(sub["balance"].sum()), source_module=M,
                          is_subtotal=True))
        for ci, cls in enumerate(_AQ_ORDER, start=1):
            s = sub[sub["classification"] == cls]
            rate = (float(s["min_provision_rate"].iloc[0]) if len(s)
                    else 0.0)
            L.append(FormLine(
                f"{base + ci * 10}", f"{cls} — 잔액", 1, "KRW",
                float(s["balance"].sum()),
                formula=f"건수 {len(s):,}건",
                citation="은행업감독규정 제27조 자산건전성 5단계",
                source_module=M))
            L.append(FormLine(
                f"{base + ci * 10 + 1}", f"{cls} — 최저적립액", 2, "KRW",
                float(s["min_provision"].sum()),
                formula=f"잔액 × 최저적립률 {rate:.2%}",
                citation="은행업감독규정 제29조 제1항", source_module=M))
    L += [
        FormLine("4000", "고정이하여신 (고정+회수의문+추정손실)", 0, "KRW",
                 float(t[t["classification"].isin(
                     ("고정", "회수의문", "추정손실"))]["balance"].sum()),
                 citation="은행업감독규정 제27조", source_module=M,
                 is_subtotal=True),
        FormLine("4100", "고정이하여신비율", 0, "ratio",
                 float(t[t["classification"].isin(
                     ("고정", "회수의문", "추정손실"))]["balance"].sum())
                 / float(t["balance"].sum()) if float(t["balance"].sum()) else 0.0,
                 formula="고정이하여신 ÷ 총여신", source_module=M),
        FormLine("9000", "분류 기준 비고", 0, "text", None,
                 text_value="본 산출의 건전성 분류는 연체일수 기준 대용 규칙이며, "
                            "감독규정은 채무상환능력 평가를 함께 요구한다.",
                 citation="은행업감독규정 제27조"),
    ]
    checks = [
        FormCheck("여신 소계 합 = 총 여신", float(t["balance"].sum()),
                  _val(L, "2000") + _val(L, "3000"), 1.0),
    ]
    return BuiltForm(FORMS_BY_ID["BR-10"], L, checks)


def _br11(ctx) -> BuiltForm:
    t = ctx.tables["rdm_asset_quality"]
    M = "risk_lib.datamodel.materialize_detail.materialize_rdm_detail"
    min_p = float(t["min_provision"].sum())
    ifrs = float(t["ifrs9_provision"].sum())
    short = float(t["reserve_shortfall"].sum())
    L = [
        FormLine("1000", "감독규정 최저적립액 합계", 0, "KRW", min_p,
                 formula="Σ 잔액 × 분류별 최저적립률",
                 citation="은행업감독규정 제29조 제1항", source_module=M,
                 is_subtotal=True),
        FormLine("2000", "회계기준 대손충당금 (IFRS 9 ECL)", 0, "KRW", ifrs,
                 citation="IFRS 9 5.5", source_module="risk_lib.provisioning.ecl",
                 is_subtotal=True),
        FormLine("3000", "대손준비금 소요액", 0, "KRW", short,
                 formula="Σ max(0, 최저적립액 − 충당금)  ※ 익스포저 단위 적용",
                 citation="은행업감독규정 제29조 제2항", source_module=M,
                 is_subtotal=True),
        FormLine("4000", "총액 기준 차액 (참고)", 0, "KRW", max(0.0, min_p - ifrs),
                 formula="max(0, 최저적립액 합계 − 충당금 합계)",
                 citation="익스포저 단위 합계와 다르다 — 상계 여부가 쟁점",
                 source_module=M),
    ]
    checks = [
        FormCheck("대손준비금 ≥ 총액 기준 차액", 0.0,
                  min(0.0, short - max(0.0, min_p - ifrs)), 1.0),
    ]
    return BuiltForm(FORMS_BY_ID["BR-11"], L, checks)


# ---------------------------------------------------------------- BR-12

def _br12(ctx) -> BuiltForm:
    r = ctx.result
    lex = r.limits_deep.large_exposure_lex
    grp = r.limits_deep.large_exposure_lex_group
    own = float(r.meta["capital"].tier1)
    M = "risk_lib.limits.limits_deep"
    reportable = lex[lex["reportable"]]
    breach_grp = grp[grp["severity"] == "BREACH"]
    total_large = float(reportable["ead"].sum())
    L = [
        FormLine("1000", "자기자본 (기본자본 기준)", 0, "KRW", own,
                 citation="LEX10.9 — 거액익스포저는 Tier 1 기준", source_module=M),
        FormLine("2000", "거액여신 건수 (자기자본 10% 이상)", 0, "count",
                 float(len(reportable)),
                 citation="LEX10.10 보고기준 · 은행법 제35조",
                 source_module=M, is_subtotal=True),
        FormLine("2100", "거액여신 합계액", 0, "KRW", total_large,
                 source_module=M, is_subtotal=True),
        FormLine("2200", "거액여신 합계액 ÷ 자기자본", 0, "ratio",
                 total_large / own if own else 0.0,
                 formula="거액여신 합계 ÷ 기본자본",
                 citation="은행법 제35조 제1항 — 거액신용공여 총액 한도",
                 source_module=M),
        FormLine("3000", "동일차주 한도(자기자본 25%)", 0, "KRW", own * 0.25,
                 citation="LEX10.5 · 은행법 제35조", source_module=M),
        FormLine("3100", "동일차주 한도 초과 그룹 수", 0, "count",
                 float(len(breach_grp)), source_module=M, is_subtotal=True),
        FormLine("3200", "최대 동일차주 익스포저", 0, "KRW",
                 float(grp["ead"].max()) if len(grp) else 0.0,
                 source_module=M),
        FormLine("3300", "최대 동일차주 한도 소진율", 0, "ratio",
                 float(grp["utilisation_25pct"].max()) if len(grp) else 0.0,
                 formula="익스포저 ÷ (자기자본 × 25%)", source_module=M),
    ]
    for i, (_, row) in enumerate(grp.head(10).iterrows(), start=1):
        L.append(FormLine(
            f"41{i:02d}", f"상위 동일차주 · {row['obligor_group_id']}", 1, "KRW",
            float(row["ead"]),
            formula=f"자기자본 대비 {row['pct_tier1']:.2%} · 한도소진 {row['utilisation_25pct']:.1%}",
            citation="LEX10.5", source_module=M))
    checks = [
        FormCheck("동일차주 한도 = 자기자본 × 25%", own * 0.25,
                  _val(L, "3000"), 1.0),
    ]
    return BuiltForm(FORMS_BY_ID["BR-12"], L, checks)


# ---------------------------------------------------------------- BR-13

def _br13(ctx) -> BuiltForm:
    irr = ctx.result.alm["irrbb"]
    M = "risk_lib.alm.irrbb"
    L = [FormLine("1000", "기본자본 (Tier 1)", 0, "KRW", float(irr.tier1),
                  citation="SRP31.92 outlier test 기준", source_module=M)]
    for i, (_, row) in enumerate(irr.delta_eve.iterrows(), start=1):
        L.append(FormLine(f"20{i:02d}", f"ΔEVE · {row['scenario']}", 1, "KRW",
                          float(row["delta_eve"]),
                          formula=f"기본자본 대비 {row['pct_tier1']:.2%}",
                          citation="SRP31.90 표준 6개 금리충격 시나리오",
                          source_module=M))
    L += [
        FormLine("3000", "최대 EVE 감소액", 0, "KRW",
                 float(irr.worst_eve_decline),
                 formula=f"최악 시나리오 = {irr.worst_eve_scenario}",
                 citation="SRP31.92", source_module=M, is_subtotal=True),
        FormLine("3100", "최대 EVE 감소 / 기본자본", 0, "ratio",
                 float(irr.worst_pct_tier1),
                 citation="SRP31.92 — 15% 초과 시 이상치 은행", source_module=M),
        FormLine("3200", "이상치 판정 기준", 0, "ratio", 0.15,
                 citation="SRP31.92"),
        FormLine("3300", "이상치 해당 여부", 0, "count",
                 1.0 if irr.outlier() else 0.0,
                 formula="1 = 해당, 0 = 미해당", source_module=M),
    ]
    # ΔNII는 시나리오별 표다 — 최악(최대 감소) 시나리오를 서식 라인으로 올린다.
    nii = irr.delta_nii
    worst_nii = nii.loc[nii["delta_nii"].idxmin()]
    L.append(FormLine("4000", "ΔNII (1년) — 최악 시나리오", 0, "KRW",
                      float(worst_nii["delta_nii"]),
                      formula=f"시나리오 = {worst_nii['scenario']}",
                      citation="SRP31.34 순이자이익 관점", source_module=M,
                      is_subtotal=True))
    for i, (_, row) in enumerate(nii.iterrows(), start=1):
        L.append(FormLine(f"41{i:02d}", f"ΔNII · {row['scenario']}", 1, "KRW",
                          float(row["delta_nii"]), citation="SRP31.34",
                          source_module=M))
    worst = float(irr.delta_eve["delta_eve"].min())
    checks = [
        FormCheck("최대 EVE 감소 = 시나리오 최솟값의 절대값",
                  abs(worst), float(irr.worst_eve_decline), 1.0),
        FormCheck("이상치 판정 = (최대감소/Tier1 > 15%)",
                  1.0 if float(irr.worst_pct_tier1) > 0.15 else 0.0,
                  1.0 if irr.outlier() else 0.0, 1e-9),
    ]
    return BuiltForm(FORMS_BY_ID["BR-13"], L, checks)


# ---------------------------------------------------------------- BR-14

def _br14(ctx) -> BuiltForm:
    r = ctx.result
    tr = r.stress_path_trough
    M = "risk_lib.stress.path"
    L = [FormLine("1000", "규제 최저 보통주자본비율 (버퍼 포함)", 0, "ratio",
                  float(r.bis.required["cet1"]),
                  citation="은행업감독규정 제26조 · 제26조의2",
                  source_module="risk_lib.capital.bis")]
    for i, (_, row) in enumerate(tr.iterrows(), start=1):
        base = 2000 + i * 100
        L.append(FormLine(f"{base}", f"시나리오 · {row['scenario']}", 0, "ratio",
                          float(row["trough_cet1"]),
                          formula=f"저점 분기 {row['trough_quarter']}",
                          citation="ST-F004 CET1 roll-forward",
                          source_module=M, is_subtotal=True))
        L.append(FormLine(f"{base + 10}", "기말 보통주자본비율", 1, "ratio",
                          float(row["end_cet1"]), source_module=M))
        L.append(FormLine(f"{base + 20}", "요구치 충족 여부", 1, "count",
                          1.0 if bool(row["passes_all"]) else 0.0,
                          formula="1 = 전 분기 충족, 0 = 침범",
                          source_module=M))
        breach = row["first_breach"]
        L.append(FormLine(f"{base + 30}", "최초 침범 분기", 1, "text", None,
                          text_value=(str(breach) if isinstance(breach, str)
                                      else "해당 없음"),
                          formula=f"제약 비율 = {row['breach_ratio']}",
                          citation="ST-F006 — 침범 시 제약 비율 명시",
                          source_module=M))
    sev = tr[tr["scenario"] == "severely_adverse"]
    checks = []
    if len(sev):
        s = sev.iloc[0]
        checks.append(FormCheck(
            "심각 시나리오 저점 ≤ 기말",
            0.0, min(0.0, float(s["end_cet1"]) - float(s["trough_cet1"])), 1e-9))
    return BuiltForm(FORMS_BY_ID["BR-14"], L, checks)


# ---------------------------------------------------------------- 서식 등록

def _ext(form_id: str, builder_name: str):
    """forms_ext의 (lines, checks) 빌더를 BuiltForm으로 감싼다.

    확장 빌더가 FORMS_BY_ID를 직접 참조하면 순환 import가 된다 — 서식 등록은
    이 파일에만 두고, 확장 모듈은 순수하게 라인·검증만 만든다.
    """
    def _run(ctx):
        from risk_lib.regulatory import forms_ext
        lines, checks = getattr(forms_ext, builder_name)(ctx)
        return BuiltForm(FORMS_BY_ID[form_id], lines, checks)
    _run.__name__ = f"_run_{form_id.replace('-', '_')}"
    return _run


FORMS: tuple[FormSpec, ...] = (
    FormSpec("BR-01", "자기자본비율 산출 총괄", "분기",
             "은행업감독규정 제26조 · Basel III CRE20·CRE40·RBC20", 1,
             "PRD-CAP", _br01),
    FormSpec("BR-02", "자기자본 구성 명세", "분기",
             "Basel III CRE40 자본의 정의", 2, "PRD-CAP", _br02),
    FormSpec("BR-03", "신용리스크 위험가중자산 — 표준방법", "분기",
             "Basel III CRE20", 3, "PRD-RWA", _br03),
    FormSpec("BR-04", "신용리스크 위험가중자산 — 내부등급법", "분기",
             "Basel III CRE31·CRE32 · Pillar 3 CR6", 4, "PRD-RWA", _br04),
    FormSpec("BR-05", "시장리스크 소요자기자본", "분기",
             "Basel III MAR40", 5, "PRD-RWA", _br05),
    FormSpec("BR-06", "운영리스크 소요자기자본", "분기",
             "Basel III OPE25 신표준방법", 6, "PRD-RWA", _br06),
    FormSpec("BR-07", "레버리지비율", "분기",
             "Basel III LEV20·LEV30 · 은행업감독규정 제26조", 7, "PRD-CAP", _br07),
    FormSpec("BR-08", "유동성커버리지비율 (LCR)", "월",
             "Basel III LCR20·LCR30·LCR40 · 은행업감독규정 제26조", 8,
             "PRD-ALM", _br08),
    FormSpec("BR-09", "순안정자금조달비율 (NSFR)", "분기",
             "Basel III NSF20·NSF30", 9, "PRD-ALM", _br09),
    FormSpec("BR-10", "자산건전성 분류 및 대손충당금", "분기",
             "은행업감독규정 제27조·제29조", 10, "PRD-RDM", _br10),
    FormSpec("BR-11", "대손준비금 적립", "분기",
             "은행업감독규정 제29조 제2항", 11, "PRD-ECL", _br11),
    FormSpec("BR-12", "거액여신 및 동일차주 신용공여", "분기",
             "은행법 제35조 · Basel III LEX10", 12, "PRD-RDM", _br12),
    FormSpec("BR-13", "은행계정 금리리스크 (IRRBB)", "반기",
             "Basel III SRP31", 13, "PRD-ALM", _br13),
    FormSpec("BR-14", "스트레스테스트 결과", "연",
             "Basel III SRP20 ICAAP · 스트레스 완충자본", 14, "PRD-ST", _br14),

    # ---- 제1편 재무·손익 (제99조 업무보고서 기본)
    FormSpec("BR-15", "재무상태표", "분기",
             "은행업감독규정 제99조 업무보고서", 15, "PRD-PRU",
             _ext("BR-15", "br_balance_sheet")),
    FormSpec("BR-16", "손익계산서", "분기",
             "은행업감독규정 제99조 업무보고서", 16, "PRD-PRU",
             _ext("BR-16", "br_income_statement")),

    # ---- 제2편 자본적정성 (나머지)
    FormSpec("BR-17", "신용위험경감 (담보·보증)", "분기",
             "Basel III CRE22", 17, "PRD-RWA", _ext("BR-17", "br_crm")),
    FormSpec("BR-18", "시장리스크 위험요소 및 백테스팅", "분기",
             "Basel III MAR31·MAR33·MAR99", 18, "PRD-MKT",
             _ext("BR-18", "br_market_factors")),
    FormSpec("BR-19", "운영손실 사건 및 회수", "분기",
             "Basel III OPE25 · BCBS PSMOR", 19, "PRD-OPR",
             _ext("BR-19", "br_op_loss")),
    FormSpec("BR-20", "산출하한 적용내역", "분기",
             "Basel III RBC20.11", 20, "PRD-RWA",
             _ext("BR-20", "br_output_floor")),
    FormSpec("BR-21", "완충자본 및 배당가능액 (MDA)", "분기",
             "은행업감독규정 제26조의2~4 · CRE10.4", 21, "PRD-CAP",
             _ext("BR-21", "br_buffer_mda")),

    # ---- 제3편 유동성 (국내 고유 지표)
    FormSpec("BR-22", "원화유동성비율", "월",
             "은행업감독규정 제26조 제1항", 22, "PRD-PRU",
             _ext("BR-22", "br_krw_liquidity")),
    FormSpec("BR-23", "외화유동성비율", "월",
             "은행업감독규정 제63조", 23, "PRD-PRU",
             _ext("BR-23", "br_fx_liquidity")),
    FormSpec("BR-24", "원화예대율", "월",
             "은행업감독규정 제26조 제1항", 24, "PRD-PRU",
             _ext("BR-24", "br_loan_deposit")),

    # ---- 제4편 자산건전성 (나머지)
    FormSpec("BR-25", "자산건전성 분류 — 자산군별", "분기",
             "은행업감독규정 제27조", 25, "PRD-RDM",
             _ext("BR-25", "br_asset_quality_by_class")),
    FormSpec("BR-26", "부실채권 및 연체 현황", "월",
             "은행업감독규정 제27조 · Basel III CRE36.69", 26, "PRD-RDM",
             _ext("BR-26", "br_npl")),

    # ---- 제5편 자산운용 한도
    FormSpec("BR-27", "대주주 신용공여 및 주식취득 한도", "분기",
             "은행법 제35조의2·제35조의3", 27, "PRD-PRU",
             _ext("BR-27", "br_major_shareholder")),
    FormSpec("BR-28", "유가증권·자회사·부동산 한도", "분기",
             "은행법 제37조·제38조", 28, "PRD-PRU",
             _ext("BR-28", "br_investment_limits")),

    # ---- 제7편 내부자본·위기상황분석
    FormSpec("BR-29", "내부자본적정성 (ICAAP)", "연",
             "Basel III SRP20", 29, "PRD-CAP", _ext("BR-29", "br_icaap")),
    FormSpec("BR-30", "위기상황분석 산출과정", "연",
             "Basel III SRP20 · ST-F001~F006", 30, "PRD-ST",
             _ext("BR-30", "br_stress_trace")),

    # ---- 제8편 경영실태평가·적기시정조치
    FormSpec("BR-31", "경영실태평가", "반기",
             "은행업감독규정 제31조~제33조", 31, "PRD-PRU",
             _ext("BR-31", "br_camel")),
    FormSpec("BR-32", "적기시정조치 판정", "분기",
             "은행업감독규정 제34조~제36조", 32, "PRD-PRU",
             _ext("BR-32", "br_prompt_action")),

    # ---- 제9편 집중도·거래상대방
    FormSpec("BR-33", "부문별 집중도 및 거액익스포저", "분기",
             "Basel III SRP30 · LEX10 · 은행법 제35조", 33, "PRD-RDM",
             _ext("BR-33", "br_concentration")),
    FormSpec("BR-34", "파생상품 및 거래상대방 신용위험", "분기",
             "Basel III CRE52 SA-CCR · MAR50 CVA", 34, "PRD-MKT",
             _ext("BR-34", "br_ccr")),
)

# ---------------------------------------------------------------- 금감원 서식 자동 등록
#
# 신설 서식 93건은 서식명·작성주기를 손으로 적지 않는다 — FINES 마스터가 정본이고
# 빌더 모듈은 규정근거·산출도메인·라인만 제공한다. 서식명을 손으로 옮겨 적으면
# 마스터가 개정될 때 조용히 어긋난다.

_FSS_BUILDER_MODULES: tuple[str, ...] = (
    "forms_fss_capital",      # 자본적정성
    "forms_fss_asset",        # 자산건전성
    "forms_fss_liquidity",    # 유동성
    "forms_fss_indicator",    # 리스크 지표
    "forms_fss_compliance",   # 업무규제 준수
)


def _fss_runner(module: str, code: str):
    """빌더 모듈을 지연 import한다 — 모듈이 forms.py를 참조해도 순환이 안 난다."""
    def _run(ctx):
        import importlib
        mod = importlib.import_module(f"risk_lib.regulatory.{module}")
        lines, checks = mod.BUILDERS[code][2](ctx)
        return BuiltForm(FORMS_BY_ID[code], lines, checks)
    _run.__name__ = f"_run_{code.replace('-', '_')}"
    return _run


def _fss_specs() -> tuple[FormSpec, ...]:
    import importlib
    from risk_lib.regulatory.fss_master import BY_CODE
    out: list[FormSpec] = []
    for i, module in enumerate(_FSS_BUILDER_MODULES):
        try:
            mod = importlib.import_module(f"risk_lib.regulatory.{module}")
        except ModuleNotFoundError:            # 아직 저작 전인 그룹은 건너뛴다
            continue
        for j, (code, (citation, domain, _)) in enumerate(
                sorted(mod.BUILDERS.items())):
            f = BY_CODE[code]
            out.append(FormSpec(code, f.name, f.frequency, citation,
                                (i + 1) * 1000 + j, domain,
                                _fss_runner(module, code)))
    return tuple(out)


FORMS = FORMS + _fss_specs()
FORMS_BY_ID = {f.form_id: f for f in FORMS}


# ---------------------------------------------------------------- 빌드

@dataclass(frozen=True)
class _Ctx:
    result: object
    portfolio: pd.DataFrame
    tables: dict[str, pd.DataFrame]


def build_forms(result, portfolio, tables: dict[str, pd.DataFrame]
                ) -> list[BuiltForm]:
    """전 서식을 산출값으로 채운다. 서식 순서는 sheet_order를 따른다."""
    ctx = _Ctx(result, portfolio, tables)
    # 편제 순서가 제출 순서다. sheet_order는 편제 안에서의 순번으로만 쓴다.
    from risk_lib.regulatory.form_ids import SECTIONS
    order = {fid: i for i, (_, ids) in enumerate(SECTIONS)
             for fid in ids}
    ordered = sorted(FORMS, key=lambda s: (order.get(s.form_id, 99),
                                           s.sheet_order))
    return [f.builder(ctx) for f in ordered]


def submission_digest(built: list[BuiltForm]) -> str:
    """제출본 지문 — 같은 지문이면 같은 제출본이다."""
    h = hashlib.sha256()
    for b in built:
        h.update(b.spec.form_id.encode())
        for ln in b.lines:
            h.update(f"{ln.line_code}|{ln.value}|{ln.text_value}".encode())
    return h.hexdigest()


def form_frames(built: list[BuiltForm], asof: str, *,
                prepared_by: str = "리스크관리부 실무자",
                reviewed_by: str = "리스크관리부장",
                approved_by: str = "리스크담당임원(CRO)",
                ) -> dict[str, pd.DataFrame]:
    """PRD-REG 정규 테이블 4장으로 실체화한다."""
    digest = submission_digest(built)
    forms = pd.DataFrame([{
        "form_id": b.spec.form_id,
        "form_no": b.spec.form_no.internal_code,
        "official_form_no": b.spec.form_no.official_code,
        "form_name": b.spec.form_name, "section": b.spec.section,
        "frequency": b.spec.frequency, "citation": b.spec.citation,
        "sheet_order": b.spec.sheet_order,
        "source_domain": b.spec.source_domain,
    } for b in built])
    lines = pd.DataFrame([{
        "form_id": b.spec.form_id, "line_code": ln.line_code,
        "line_name": ln.line_name, "level": ln.level, "unit": ln.unit,
        "value": ln.value, "text_value": ln.text_value,
        "formula": ln.formula, "citation": ln.citation,
        "source_module": ln.source_module, "is_subtotal": ln.is_subtotal,
    } for b in built for ln in b.lines])
    checks = pd.DataFrame([{
        "form_id": b.spec.form_id, "check_name": c.check_name,
        "expected": c.expected, "actual": c.actual, "diff": c.diff,
        "tolerance": c.tolerance, "status": c.status,
    } for b in built for c in b.checks])
    subs = pd.DataFrame([{
        "form_id": b.spec.form_id, "asof": asof,
        "prepared_by": prepared_by, "reviewed_by": reviewed_by,
        "approved_by": approved_by, "digest": digest,
        "n_lines": len(b.lines), "n_failed_checks": b.n_failed,
        # 검증 실패가 남아 있으면 승인 상태로 올릴 수 없다.
        "status": "draft" if b.n_failed else "approved",
    } for b in built])
    return {"reg_form": forms, "reg_form_line": lines,
            "reg_form_check": checks, "reg_submission": subs}
