"""금감원 FINES 업무보고서 — 자본적정성 편 19건.

서식명·작성주기는 여기 적지 않는다. FINES 마스터(`fss_master.py`)가 정본이고
forms.py가 붙인다. 이 모듈은 규정근거·산출도메인·라인만 제공한다.

**분모 기준이 서식마다 다르다.** B2301은 표준방법 전량 산출(구 바젤 기준),
BA2303-2는 내부등급법 + 산출하한 적용 후(바젤Ⅲ 개정)다. 같은 자기자본을
서로 다른 위험가중자산으로 나누므로 두 서식의 비율은 다르며, 그것이 정상이다.
`result.rwa`의 `standardised_total` / `final_total`이 각각의 분모다.

**원장이 없어 파생한 값** — 아래 두 건이다. 나머지 미보유 항목은 파생하지
않고 0으로 두되 사유를 라인에 남긴다("없다"와 "안 봤다"는 다르다).

  B2316 일별 트레이딩목적 자산 잔액
    일별 포지션 원장이 없다. 보고월 영업일별 잔액을 **시드 고정 RNG**로
    파생한다. 변동 폭은 지어내지 않고 `mkt_backtest_exception`의 실제 일별
    손익 표준편차에서 뽑으며, 마지막 영업일 잔액은 실제 산출된 월말 평가액에
    고정한다(B2315와 대사된다). 시드는 `result.meta["seed"]`이므로 같은
    파이프라인 실행이면 같은 경로가 나온다. 이 값은 원장이 아니라 파생값이다.

  B2308 부외자산 위험가중자산 (3000 라인, 참고 산출)
    부외 RWA를 파이프라인이 산출하지 않는다. 위험가중치를 새로 가정하지 않고
    같은 익스포저의 실측 RW(rwa ÷ ead_final)를 신용환산액에 적용한 **참고치**다.
    자본비율 분모 반영액은 0으로 따로 적었다.

**합계는 맞지만 분해가 정확하지 않은 곳** — B2312의 계정과목별 위험가중자산.
익스포저를 대차대조표 계정에 잇는 매핑 원장이 없어 신용RWA 전액을 대출채권
행에 모았다. 배분비율을 지어내지 않은 결과이며 9000 라인에 남겼다.

미산출로 남긴 것(사유는 각 서식의 text 라인에 있다):
  B2311·B2312  연결 자회사 원장 없음 → 연결 = 단독
  BA2320       기타의 자산 세부 원장 없음 → 위험가중 미산출
  BA2327       포트폴리오에 유동화 익스포저 없음 → SEC 방법론 미적용
  B2324        국가별 경기대응완충자본 적립률 고시 원장 없음 → 0
  B2329        SA-CVA 민감도 미산출 → 기초법(BA-CVA)이 정본

**모듈 파라미터를 감독 고시치처럼 읽으면 안 되는 곳** — B2318-1의 위험군별
위험가중치(`DEFAULT_RISK_WEIGHTS`)와 B2328의 κ. 둘 다 서식이 상수를 옮겨 적지
않고 모듈에서 직접 읽지만, 감독당국 고시 계수가 아니라 축약 파라미터다.
각 서식의 비고 라인에 그 사실을 적었다.
"""

from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd

from risk_lib.regulatory.forms_base import (
    FormCheck, FormLine, _ratio_check, _sum_check, _val, month_business_days,
)
from risk_lib.ccr import cva_rwa as _cva_rwa

_M_CAP = "risk_lib.capital.bis · risk_lib.capital.output_floor"
_M_RWA = "risk_lib.capital.rwa_sa · risk_lib.capital.rwa_irb"
_M_MKT = "risk_lib.capital.market_risk"
_M_CCR = "risk_lib.ccr"
_M_RDM = "risk_lib.datamodel.materialize_detail"
_M_PRU = "risk_lib.prudential.financials"

# MAR40 간편표준방법의 위험군 어휘. 파이프라인이 포지션을 만들지 않은 위험군도
# 서식에는 칸이 있다 — 0을 적되 "미보유"임을 산식에 남긴다.
_MKT_CLASSES = ("interest_rate", "equity", "fx", "commodity", "credit_spread")
_MKT_KO = {"interest_rate": "금리", "equity": "주식", "fx": "외환",
           "commodity": "상품", "credit_spread": "신용스프레드"}


def _capital_lines(cap) -> list[FormLine]:
    """자기자본 4행 — B2301·BA2303-2가 같은 자본을 서로 다른 분모로 나눈다."""
    return [
        FormLine("1000", "자기자본 (총자본)", 0, "KRW", float(cap.total),
                 formula="보통주자본 + 기타기본자본 + 보완자본",
                 citation="은행업감독규정 제26조 · Basel III CAP10 자본의 정의",
                 source_module=_M_CAP, is_subtotal=True),
        FormLine("1100", "보통주자본 (CET1)", 1, "KRW", float(cap.cet1),
                 citation="CAP10 보통주자본 요건 · CAP30 규제조정",
                 source_module=_M_CAP),
        FormLine("1200", "기타기본자본 (AT1)", 1, "KRW",
                 float(cap.additional_t1),
                 citation="CAP10 기타기본자본 요건 · CAP30 규제조정",
                 source_module=_M_CAP),
        FormLine("1300", "보완자본 (Tier 2)", 1, "KRW", float(cap.tier2),
                 citation="CAP10 보완자본 요건 · CAP30 규제조정",
                 source_module=_M_CAP),
        FormLine("1400", "기본자본 (Tier 1)", 1, "KRW", float(cap.tier1),
                 formula="보통주자본 + 기타기본자본", source_module=_M_CAP,
                 is_subtotal=True),
    ]


def _capital_checks(L: list[FormLine]) -> list[FormCheck]:
    return [
        _sum_check("자기자본 = CET1+AT1+T2", L, "1000", ("1100", "1200", "1300")),
        _sum_check("기본자본 = CET1+AT1", L, "1400", ("1100", "1200")),
    ]


# ---------------------------------------------------------------- B2301

def _b2301(ctx):
    """구 바젤 기준 BIS비율 — 분모는 표준방법 전량 산출치다."""
    from risk_lib.capital.bis import BIS_MINIMUMS
    min_total = float(BIS_MINIMUMS["total"])   # 8%를 옮겨 적지 않는다
    r = ctx.result
    rwa = r.rwa
    std = float(rwa["standardised_total"])
    ccr = float(rwa["ccr"])
    mkt = float(rwa["market"])
    op = float(rwa["op"])
    credit_std = std - ccr - mkt - op
    cap = r.meta["capital"]
    L = _capital_lines(cap) + [
        FormLine("2000", "위험가중자산 합계 (표준방법 전량 기준)", 0, "KRW", std,
                 formula="신용(표준) + CCR·CVA + 시장 + 운영 — 내부등급법·산출하한 미적용",
                 citation="구 바젤 기준 · CRE20", source_module=_M_CAP,
                 is_subtotal=True),
        FormLine("2100", "신용리스크 (표준방법)", 1, "KRW", credit_std,
                 formula="표준방법 전량 산출 − CCR·CVA − 시장 − 운영",
                 citation="CRE20", source_module="risk_lib.capital.rwa_sa"),
        FormLine("2200", "거래상대방신용리스크 (SA-CCR + CVA)", 1, "KRW", ccr,
                 citation="CRE52 · MAR50", source_module=_M_CCR),
        FormLine("2300", "시장리스크", 1, "KRW", mkt, citation="MAR40",
                 source_module=_M_MKT),
        FormLine("2400", "운영리스크", 1, "KRW", op, citation="OPE25",
                 source_module="risk_lib.capital.op_risk"),

        FormLine("3100", "보통주자본비율", 0, "ratio", float(cap.cet1) / std,
                 formula="보통주자본 ÷ 표준방법 위험가중자산",
                 citation="은행업감독규정 제26조 제1항 제1~3호 자기자본비율", source_module=_M_CAP),
        FormLine("3200", "기본자본비율", 0, "ratio", float(cap.tier1) / std,
                 formula="기본자본 ÷ 표준방법 위험가중자산", source_module=_M_CAP),
        FormLine("3300", "총자본비율", 0, "ratio", float(cap.total) / std,
                 formula="자기자본 ÷ 표준방법 위험가중자산", source_module=_M_CAP),
        FormLine("4300", "총자본비율 최저기준", 0, "ratio", min_total,
                 formula="risk_lib.capital.bis.BIS_MINIMUMS 참조",
                 citation="은행업감독규정 제26조 제1항 · CRE10.4",
                 source_module=_M_CAP),
        FormLine("5300", "총자본비율 잉여(+)·부족(−)", 0, "ratio",
                 float(cap.total) / std - min_total, formula="실측 − 최저기준",
                 source_module=_M_CAP),
        FormLine("9000", "분모 기준 비고", 0, "text", None,
                 text_value="본 서식의 분모는 표준방법 전량 산출치이며 "
                            "내부등급법·산출하한 적용 후 수치는 BA2303-2에 있다. "
                            "두 서식의 비율이 다른 것이 정상이다.",
                 citation="RBC20.11"),
    ]
    checks = _capital_checks(L) + [
        _sum_check("표준방법 RWA = 신용+CCR+시장+운영", L, "2000",
                   ("2100", "2200", "2300", "2400")),
        _ratio_check("총자본비율 = 자기자본/표준방법RWA", L, "3300", "1000", "2000"),
        _ratio_check("보통주자본비율 = CET1/표준방법RWA", L, "3100", "1100", "2000"),
        FormCheck("잉여 = 실측 − 최저", _val(L, "3300") - _val(L, "4300"),
                  _val(L, "5300"), 1e-12),
        # 2100은 잔차식이라 소계 대사가 항등식이 된다. 잔차가 음수로 돌아서면
        # 아무 검증도 걸리지 않으므로 부호만이라도 지킨다.
        FormCheck("표준방법 신용 RWA ≥ 0 (잔차 건전성)", 0.0,
                  min(0.0, credit_std), 1.0),
    ]
    return L, checks


# ---------------------------------------------------------------- BA2303-2

def _ba2303_2(ctx):
    """바젤Ⅲ 개정 내부등급법 기준 총자본비율 — 산출하한 적용 후가 분모다."""
    r = ctx.result
    rwa = r.rwa
    fl = rwa["output_floor"]
    cap = r.meta["capital"]
    L = _capital_lines(cap) + [
        FormLine("2000", "위험가중자산 합계 (산출하한 적용 후)", 0, "KRW",
                 float(rwa["final_total"]),
                 formula="내부등급법 + 표준방법 + CCR·CVA + 시장 + 운영 + 하한조정",
                 citation="CRE20.1 · RBC20.11", source_module=_M_CAP,
                 is_subtotal=True),
        FormLine("2100", "신용리스크 — 내부등급법 (IRB)", 1, "KRW",
                 float(rwa["irb"]), citation="CRE31 · CRE32",
                 source_module="risk_lib.capital.rwa_irb"),
        FormLine("2110", "신용리스크 — 표준방법 적용분 (SA)", 1, "KRW",
                 float(rwa["sa"]),
                 formula="내부등급법 승인 범위 밖 자산군 (국가·은행)",
                 citation="CRE20", source_module="risk_lib.capital.rwa_sa"),
        FormLine("2120", "거래상대방신용리스크 (SA-CCR + CVA)", 1, "KRW",
                 float(rwa["ccr"]), citation="CRE52 · MAR50", source_module=_M_CCR),
        FormLine("2200", "시장리스크", 1, "KRW", float(rwa["market"]),
                 citation="MAR40", source_module=_M_MKT),
        FormLine("2300", "운영리스크", 1, "KRW", float(rwa["op"]),
                 citation="OPE25 신표준방법",
                 source_module="risk_lib.capital.op_risk"),
        FormLine("2400", "산출하한 조정분", 1, "KRW", float(fl.add_on),
                 formula="max(0, 표준방법 RWA × 하한율 − 내부모형 RWA)",
                 citation="RBC20.11", source_module="risk_lib.capital.output_floor"),
        FormLine("2500", "산출하한 구속 여부", 1, "count",
                 1.0 if bool(fl.is_binding) else 0.0,
                 formula="1 = 구속 (내부모형 개선이 자본에 반영되지 않음)",
                 citation="RBC20.11", source_module="risk_lib.capital.output_floor"),

        FormLine("3100", "보통주자본비율", 0, "ratio", float(r.bis.cet1_ratio),
                 formula="보통주자본 ÷ 위험가중자산", source_module=_M_CAP),
        FormLine("3200", "기본자본비율", 0, "ratio", float(r.bis.tier1_ratio),
                 formula="기본자본 ÷ 위험가중자산", source_module=_M_CAP),
        FormLine("3300", "총자본비율", 0, "ratio", float(r.bis.total_ratio),
                 formula="자기자본 ÷ 위험가중자산",
                 citation="은행업감독규정 제26조 제1항 제1~3호 자기자본비율", source_module=_M_CAP),
        FormLine("4300", "요구 총자본비율 (완충자본 포함)", 0, "ratio",
                 float(r.bis.required["total"]),
                 formula="최저 8% + 완충자본 합계",
                 citation="은행업감독규정 제26조의2~4", source_module=_M_CAP),
        FormLine("5300", "총자본비율 잉여(+)·부족(−)", 0, "ratio",
                 float(r.bis.surplus_shortfall["total"]), source_module=_M_CAP),
    ]
    checks = _capital_checks(L) + [
        _sum_check("총RWA = IRB+SA+CCR+시장+운영+하한", L, "2000",
                   ("2100", "2110", "2120", "2200", "2300", "2400")),
        _ratio_check("총자본비율 = 자기자본/RWA", L, "3300", "1000", "2000"),
        _ratio_check("보통주자본비율 = CET1/RWA", L, "3100", "1100", "2000"),
        FormCheck("잉여 = 실측 − 요구", _val(L, "3300") - _val(L, "4300"),
                  _val(L, "5300"), 1e-12),
    ]
    return L, checks


# ---------------------------------------------------------------- B2304 / B2308

def _onbalance_frame(ctx) -> pd.DataFrame:
    """익스포저별 RWA에 자산군·적용방법을 붙인다 — 온밸런스 서식의 공통 원천."""
    rr = ctx.tables["rwa_result"][["exposure_id", "approach", "ead_final", "rwa"]]
    ex = ctx.tables["rdm_exposure"][["exposure_id", "asset_class"]]
    return rr.merge(ex, on="exposure_id", how="left")


def _b2304(ctx):
    """대차대조표 자산(온밸런스)의 위험가중자산 — 적용방법 × 자산군."""
    t = _onbalance_frame(ctx)
    total_rwa = float(t["rwa"].sum())
    total_ead = float(t["ead_final"].sum())
    L = [
        FormLine("1000", "대차대조표 자산 위험가중자산 합계", 0, "KRW", total_rwa,
                 formula="표준방법 + 내부등급법 (부외·CCR·시장·운영 제외)",
                 citation="CRE20 · CRE31", source_module=_M_RWA, is_subtotal=True),
        FormLine("1010", "대차대조표 자산 익스포저(EAD) 합계", 0, "KRW", total_ead,
                 formula="EAD = 기표잔액(drawn) 기준 — 미사용약정은 B2308",
                 source_module=_M_RWA, is_subtotal=True),
        FormLine("1020", "평균 위험가중치", 0, "ratio",
                 total_rwa / total_ead if total_ead else 0.0,
                 formula="위험가중자산 ÷ 익스포저", source_module=_M_RWA),
    ]
    ap_codes: list[str] = []
    for ai, (ap, ko) in enumerate((("SA", "표준방법"), ("AIRB", "내부등급법")),
                                  start=1):
        sub = t[t["approach"] == ap]
        base = 1000 + ai * 100
        ap_codes.append(str(base))
        L.append(FormLine(str(base), f"{ko} 소계", 1, "KRW",
                          float(sub["rwa"].sum()),
                          formula=f"{len(sub):,}건 · EAD {sub['ead_final'].sum():,.0f}",
                          citation="CRE20" if ap == "SA" else "CRE31·CRE32",
                          source_module=_M_RWA, is_subtotal=True))
        for ci, (ac, s) in enumerate(sub.groupby("asset_class"), start=1):
            ead = float(s["ead_final"].sum())
            L.append(FormLine(
                f"{base + ci}", f"자산군 · {ac}", 2, "KRW", float(s["rwa"].sum()),
                formula=(f"EAD {ead:,.0f} · 평균 RW "
                         f"{(float(s['rwa'].sum()) / ead if ead else 0.0):.2%} · "
                         f"{len(s):,}건"),
                citation="CRE20.4 · CRE32.2", source_module=_M_RWA))
    L.append(FormLine("9000", "산출 범위 비고", 0, "text", None,
                      text_value="EAD는 기표잔액 기준이며 미사용약정의 신용환산액은 "
                                 "본 산출의 자본비율 분모에 포함되지 않는다 — "
                                 "부외자산은 B2308에서 별도 산출한다.",
                      citation="CRE20.94 신용환산율"))
    checks = [
        FormCheck("적용방법 소계 합 = 온밸런스 RWA 합계", total_rwa,
                  sum(_val(L, c) for c in ap_codes), 1.0),
        # credit_internal에는 CCR·CVA가 들어 있다 — 온밸런스는 SA+IRB만이다.
        FormCheck("온밸런스 RWA = 표준방법 + 내부등급법",
                  float(ctx.result.rwa["sa"]) + float(ctx.result.rwa["irb"]),
                  total_rwa, 1.0),
        FormCheck("EAD 합계 = 익스포저 원장 EAD 합계",
                  float(ctx.tables["rdm_exposure"]["ead"].sum()), total_ead, 1.0),
        _ratio_check("평균 위험가중치 = RWA/EAD", L, "1020", "1000", "1010"),
    ]
    return L, checks


def _b2308(ctx):
    """부외자산 — 미사용약정의 명목·신용환산액. 자본비율 분모에는 미반영이다."""
    ex = ctx.tables["rdm_exposure"][["exposure_id", "ccf_type", "undrawn"]]
    bal = ctx.tables["rdm_exposure_balance"][["exposure_id", "ccf"]]
    t = ex.merge(bal, on="exposure_id", how="left")
    t = t[t["ccf_type"].notna() & (t["undrawn"] > 0)].copy()
    t["cea"] = t["undrawn"] * t["ccf"]

    # 부외 RWA는 파이프라인이 산출하지 않는다 — 같은 익스포저의 실측 위험가중치를
    # 신용환산액에 적용해 참고치만 만든다. 위험가중치를 새로 가정하지 않는 길이다.
    rr = _onbalance_frame(ctx)[["exposure_id", "ead_final", "rwa"]].copy()
    rr["rw"] = np.where(rr["ead_final"] > 0, rr["rwa"] / rr["ead_final"], 0.0)
    t = t.merge(rr[["exposure_id", "rw"]], on="exposure_id", how="left")
    t["rw"] = t["rw"].fillna(0.0)
    t["rwa_ref"] = t["cea"] * t["rw"]

    notional = float(t["undrawn"].sum())
    cea = float(t["cea"].sum())
    L = [
        FormLine("1000", "부외자산 명목금액 (미사용약정) 합계", 0, "KRW", notional,
                 citation="CRE20.94", source_module=_M_RDM, is_subtotal=True),
        FormLine("1010", "부외자산 계약 건수", 0, "count", float(len(t)),
                 source_module=_M_RDM),
        FormLine("2000", "신용환산액 (CEA) 합계", 0, "KRW", cea,
                 formula="Σ 미사용약정 × 신용환산율",
                 citation="CRE20.94 · 은행업감독업무시행세칙 별표", source_module=_M_RDM,
                 is_subtotal=True),
    ]
    n_codes, c_codes = [], []
    for i, (ct, sub) in enumerate(t.groupby("ccf_type"), start=1):
        ccf = float(sub["ccf"].iloc[0])
        L.append(FormLine(f"11{i:02d}", f"약정유형 · {ct} — 명목", 1, "KRW",
                          float(sub["undrawn"].sum()),
                          formula=f"신용환산율 {ccf:.0%} · {len(sub):,}건",
                          citation="CRE20.94", source_module=_M_RDM))
        L.append(FormLine(f"21{i:02d}", f"약정유형 · {ct} — 신용환산액", 1, "KRW",
                          float(sub["cea"].sum()),
                          formula=f"명목 {sub['undrawn'].sum():,.0f} × CCF {ccf:.0%}",
                          citation="CRE20.94", source_module=_M_RDM))
        n_codes.append(f"11{i:02d}")
        c_codes.append(f"21{i:02d}")
    L += [
        FormLine("3000", "부외자산 위험가중자산 (참고 산출)", 0, "KRW",
                 float(t["rwa_ref"].sum()),
                 formula="Σ 신용환산액 × 해당 익스포저의 실측 위험가중치",
                 citation="CRE20.94 — 위험가중치는 온밸런스와 동일 차주 기준",
                 source_module=_M_RWA, is_subtotal=True),
        FormLine("4000", "자본비율 분모 반영액", 0, "KRW", 0.0,
                 formula="현 산출의 EAD는 기표잔액 기준 — 부외 환산액 미반영 (0)",
                 citation="CRE20.94", source_module=_M_RWA),
        FormLine("9000", "미반영 사유", 0, "text", None,
                 text_value="부외자산의 명목·신용환산율은 익스포저 원장에 있으나 "
                            "파이프라인의 EAD는 기표잔액만 쓴다. 3000 라인은 참고 "
                            "산출이며 B2304·BA2303-2의 위험가중자산에는 포함되지 "
                            "않았다 — 제출 전 반영 여부를 확정해야 하는 칸이다.",
                 citation="CRE20.94"),
    ]
    checks = [
        FormCheck("약정유형별 명목 합 = 부외 명목 합계", notional,
                  sum(_val(L, c) for c in n_codes), 1.0),
        FormCheck("약정유형별 환산액 합 = 신용환산액 합계", cea,
                  sum(_val(L, c) for c in c_codes), 1.0),
        FormCheck("신용환산액 ≤ 명목금액 (CCF ≤ 100%)", 0.0,
                  max(0.0, cea - notional), 1.0),
    ]
    return L, checks


# ---------------------------------------------------------------- B2311 / B2312

def _b2311(ctx):
    """연결 자회사 내역 — 연결 대상 자회사 원장이 없다."""
    bs = ctx.tables["pru_balance_sheet"]
    assets = float(bs.loc[bs["item"] == "자산총계", "amount"].iloc[0])
    rwa = float(ctx.result.rwa["final_total"])
    L = [
        FormLine("1000", "연결 대상 자회사 수", 0, "count", 0.0,
                 formula="자회사 지분·연결범위 원장 미보유 → 연결 대상 없음",
                 citation="은행업감독규정 제26조 — 연결기준 자기자본비율",
                 source_module=_M_PRU, is_subtotal=True),
        FormLine("1100", "연결 총자산", 0, "KRW", assets,
                 formula="연결 대상 없음 → 단독 총자산과 동일",
                 source_module=_M_PRU),
        FormLine("1200", "단독 총자산", 0, "KRW", assets, source_module=_M_PRU),
        FormLine("2000", "연결 위험가중자산", 0, "KRW", rwa,
                 formula="연결 대상 없음 → 단독 위험가중자산과 동일",
                 citation="CRE20.1", source_module=_M_CAP, is_subtotal=True),
        FormLine("2100", "단독 위험가중자산", 0, "KRW", rwa, source_module=_M_CAP),
        FormLine("3000", "연결 총자본비율", 0, "ratio",
                 float(ctx.result.bis.total_ratio),
                 formula="연결 대상 없음 → 단독 총자본비율과 동일",
                 citation="은행업감독규정 제26조", source_module=_M_CAP),
        FormLine("9000", "연결범위 비고", 0, "text", None,
                 text_value="연결 자회사 원장(지분율·연결범위·소수주주지분)이 원천 "
                            "데이터에 없다. 자회사 수를 0으로 두고 연결 = 단독으로 "
                            "표시했으며, 자회사 수치를 지어내지 않았다. 실제 제출 시 "
                            "연결 대상 목록을 반드시 확인해야 한다.",
                 citation="은행업감독규정 제26조"),
    ]
    checks = [
        FormCheck("연결 총자산 = 단독 총자산", assets, _val(L, "1100"), 1.0),
        FormCheck("연결 RWA = 단독 RWA", rwa, _val(L, "2000"), 1.0),
    ]
    return L, checks


# 대차대조표 계정과목 → 위험가중 귀속. 여신만 신용RWA가 붙는다.
_BS_ACCOUNTS = ("현금 및 예치금", "유가증권 (Level 2A)", "유가증권 (Level 2B)",
                "대출채권 (순액)", "기타자산")


def _b2312(ctx):
    """연결대차대조표 계정과목별 위험가중자산 — 계정 귀속과 비귀속을 나눈다."""
    bs = ctx.tables["pru_balance_sheet"]
    amt = dict(zip(bs["item"], bs["amount"]))
    rwa = ctx.result.rwa
    # credit_internal은 CCR·CVA를 포함한다 — 계정과목에 귀속되는 것은 여신
    # 익스포저의 SA+IRB뿐이고 CCR은 아래 비귀속 소계로 뺀다.
    credit = float(rwa["sa"]) + float(rwa["irb"])
    total_assets = float(amt["자산총계"])
    L = [
        FormLine("1000", "자산총계 (연결 = 단독)", 0, "KRW", total_assets,
                 formula="연결 자회사 원장 없음 — B2311 참조",
                 citation="은행업감독규정 제99조 업무보고서", source_module=_M_PRU,
                 is_subtotal=True),
    ]
    acc_bal, acc_rwa = [], []
    for i, item in enumerate(_BS_ACCOUNTS, start=1):
        base = 1000 + i * 10
        is_loan = item == "대출채권 (순액)"
        L.append(FormLine(str(base), f"{item} — 잔액", 1, "KRW",
                          float(amt[item]), source_module=_M_PRU))
        L.append(FormLine(
            str(base + 1), f"{item} — 위험가중자산", 2, "KRW",
            credit if is_loan else 0.0,
            formula=("익스포저 원장의 신용RWA 전액을 이 계정에 귀속 "
                     "(EAD는 총액 기준이므로 순액 잔액과 금액이 다르다)"
                     if is_loan else
                     "익스포저 원장을 대차대조표 계정에 매핑하는 원장이 없어 "
                     "신용RWA 전액을 대출채권에 귀속시켰다 — 0은 미산출이 "
                     "아니라 이 계정 몫이 대출채권 행에 섞여 있다는 뜻이다"),
            citation="CRE20 · CRE31", source_module=_M_RWA))
        acc_bal.append(str(base))
        acc_rwa.append(str(base + 1))
    L += [
        FormLine("2000", "계정과목 귀속 위험가중자산 소계", 0, "KRW", credit,
                 source_module=_M_RWA, is_subtotal=True),
        FormLine("3000", "계정과목 비귀속 위험가중자산 소계", 0, "KRW",
                 float(rwa["ccr"]) + float(rwa["market"]) + float(rwa["op"])
                 + float(rwa["output_floor"].add_on),
                 formula="거래상대방·시장·운영·산출하한은 계정과목에 귀속되지 않는다",
                 source_module=_M_CAP, is_subtotal=True),
        FormLine("3100", "거래상대방신용리스크 (SA-CCR + CVA)", 1, "KRW",
                 float(rwa["ccr"]), citation="CRE52 · MAR50", source_module=_M_CCR),
        FormLine("3200", "시장리스크", 1, "KRW", float(rwa["market"]),
                 citation="MAR40", source_module=_M_MKT),
        FormLine("3300", "운영리스크", 1, "KRW", float(rwa["op"]),
                 citation="OPE25", source_module="risk_lib.capital.op_risk"),
        FormLine("3400", "산출하한 조정분", 1, "KRW",
                 float(rwa["output_floor"].add_on), citation="RBC20.11",
                 source_module="risk_lib.capital.output_floor"),
        FormLine("4000", "위험가중자산 합계", 0, "KRW", float(rwa["final_total"]),
                 formula="계정 귀속 + 계정 비귀속", citation="CRE20.1",
                 source_module=_M_CAP, is_subtotal=True),
        FormLine("9000", "계정 귀속 방식 비고", 0, "text", None,
                 text_value="익스포저 원장에는 국가·은행 자산군이 있어 실제로는 "
                            "유가증권 계정에 귀속될 몫이 있으나, 익스포저를 "
                            "대차대조표 계정으로 잇는 매핑 원장이 없다. 배분비율을 "
                            "지어내지 않고 신용RWA 전액을 대출채권 행에 모았다 — "
                            "합계는 맞으나 계정별 분해는 정확하지 않으며, 제출 전 "
                            "계정 매핑을 확보해야 하는 칸이다.",
                 citation="은행업감독규정 제99조 업무보고서"),
    ]
    checks = [
        FormCheck("계정과목 잔액 합 = 자산총계", total_assets,
                  sum(_val(L, c) for c in acc_bal), 1.0),
        FormCheck("계정과목 RWA 합 = 귀속 소계", _val(L, "2000"),
                  sum(_val(L, c) for c in acc_rwa), 1.0),
        _sum_check("비귀속 소계 = CCR+시장+운영+하한", L, "3000",
                   ("3100", "3200", "3300", "3400")),
        _sum_check("총 RWA = 귀속 + 비귀속", L, "4000", ("2000", "3000")),
    ]
    return L, checks


# ---------------------------------------------------------------- B2315 / B2316

_TRADE_KO = {"swap": "스왑", "option": "옵션", "cds": "신용부도스왑"}


def _trading_book(ctx) -> tuple[pd.DataFrame, float, float]:
    """트레이딩 계정 자산·부채 — 공정가치 부호로 가른다."""
    t = ctx.tables["mkt_trade"]
    assets = float(t["fo_value"].clip(lower=0).sum())
    liabs = float(-t["fo_value"].clip(upper=0).sum())
    return t, assets, liabs


def _b2315(ctx):
    """트레이딩목적 자산·부채현황 — 공정가치·명목·시장리스크 순포지션."""
    t, assets, liabs = _trading_book(ctx)
    pos = ctx.result.rwa["market_positions"]
    L = [
        FormLine("1000", "트레이딩목적 자산 (공정가치)", 0, "KRW", assets,
                 formula="Σ max(공정가치, 0)",
                 citation="은행업감독규정 제26조 · MAR10 트레이딩계정",
                 source_module="risk_lib.datamodel.materialize_detail",
                 is_subtotal=True),
        FormLine("1010", "트레이딩 계약 건수", 0, "count", float(len(t)),
                 source_module=_M_MKT),
        FormLine("2000", "트레이딩목적 부채 (공정가치)", 0, "KRW", liabs,
                 formula="Σ max(−공정가치, 0)", citation="MAR10",
                 source_module=_M_MKT, is_subtotal=True),
        FormLine("3000", "명목금액 합계", 0, "KRW", float(t["notional"].sum()),
                 citation="MAR10", source_module=_M_MKT, is_subtotal=True),
    ]
    a_codes, l_codes, n_codes = [], [], []
    for i, (kind, sub) in enumerate(t.groupby("kind"), start=1):
        ko = _TRADE_KO.get(kind, kind)
        L.append(FormLine(f"11{i:02d}", f"자산 · {ko}", 1, "KRW",
                          float(sub["fo_value"].clip(lower=0).sum()),
                          formula=f"{len(sub):,}건", source_module=_M_MKT))
        L.append(FormLine(f"21{i:02d}", f"부채 · {ko}", 1, "KRW",
                          float(-sub["fo_value"].clip(upper=0).sum()),
                          formula=f"{len(sub):,}건", source_module=_M_MKT))
        L.append(FormLine(f"31{i:02d}", f"명목 · {ko}", 1, "KRW",
                          float(sub["notional"].sum()), source_module=_M_MKT))
        a_codes.append(f"11{i:02d}")
        l_codes.append(f"21{i:02d}")
        n_codes.append(f"31{i:02d}")
    L.append(FormLine("4000", "순 트레이딩 포지션", 0, "KRW", assets - liabs,
                      formula="자산 − 부채", source_module=_M_MKT,
                      is_subtotal=True))
    for i, (_, row) in enumerate(pos.iterrows(), start=1):
        rc = str(row["risk_class"])
        L.append(FormLine(f"51{i:02d}", f"시장리스크 순포지션 · {_MKT_KO.get(rc, rc)}",
                          1, "KRW", float(row["net_position"]),
                          formula="MAR40 간편표준방법 산입 순포지션",
                          citation="MAR40", source_module=_M_MKT))
    L.append(FormLine("9000", "부채 계상 비고", 0, "text", None,
                      text_value=("트레이딩 원장의 공정가치가 전부 양(+)이어서 "
                                  "트레이딩목적 부채가 0이다 — 원장을 확인한 결과이며 "
                                  "부채 칸을 비운 것이 아니다."
                                  if liabs == 0.0 else
                                  "음(−)의 공정가치 계약을 트레이딩목적 부채로 계상했다."),
                      citation="MAR10"))
    checks = [
        FormCheck("상품유형별 자산 합 = 트레이딩 자산", assets,
                  sum(_val(L, c) for c in a_codes), 1.0),
        FormCheck("상품유형별 부채 합 = 트레이딩 부채", liabs,
                  sum(_val(L, c) for c in l_codes), 1.0),
        FormCheck("상품유형별 명목 합 = 명목 합계", float(t["notional"].sum()),
                  sum(_val(L, c) for c in n_codes), 1.0),
        # 부채액을 허용오차로 넘기면 부채가 클수록 검증이 느슨해져 정작 필요할 때
        # 통과한다. 자산−부채를 직접 대사한다.
        FormCheck("순 포지션 = 자산 − 부채", assets - liabs, _val(L, "4000"), 1.0),
    ]
    return L, checks


def _b2316_daily(ctx) -> tuple[pd.DatetimeIndex, np.ndarray, float]:
    """보고월 영업일별 트레이딩 자산 잔액을 파생한다.

    일별 포지션 원장이 없다. 변동 폭까지 지어내지 않도록 실제 일별 손익
    (`mkt_backtest_exception`)의 표준편차를 월말 잔액으로 나눠 상대 변동성을
    쓰고, 경로 모양만 시드 고정 RNG로 만든다. 마지막 영업일은 실제 월말
    평가액으로 고정해 B2315와 대사된다.
    """
    _, assets, _ = _trading_book(ctx)
    asof = pd.Timestamp(str(ctx.result.meta["asof"]))
    days = month_business_days(asof)

    bt = ctx.tables["mkt_backtest_exception"].copy()
    bt["obs"] = pd.to_datetime(bt["obs_date"])
    month = bt[bt["obs"].dt.to_period("M") == asof.to_period("M")]
    sigma = (float(month["pnl"].std()) / assets
             if len(month) > 1 and assets else 0.0)

    rng = np.random.default_rng(int(ctx.result.meta["seed"]) + 2316)
    z = rng.standard_normal(len(days))
    z[-1] = 0.0                     # 마지막 영업일 = 실제 월말 평가액
    return days, assets * np.exp(sigma * z), sigma


def _b2316(ctx):
    """일별 트레이딩목적 자산·부채현황 — 일별 잔액은 파생값이다."""
    days, path, sigma = _b2316_daily(ctx)
    _, assets, liabs = _trading_book(ctx)
    mean = float(path.mean())
    L = [
        FormLine("1000", "보고월 영업일수", 0, "count", float(len(days)),
                 formula=f"{days[0]:%Y-%m-%d}~{days[-1]:%Y-%m-%d} · 공휴일 달력 미적용",
                 citation="은행업감독규정 제99조 업무보고서", is_subtotal=True),
        FormLine("1100", "월말 트레이딩목적 자산", 0, "KRW", assets,
                 formula="B2315 자산 합계와 동일", citation="MAR10",
                 source_module=_M_MKT, is_subtotal=True),
        FormLine("1200", "월중 일평균 트레이딩목적 자산", 0, "KRW", mean,
                 formula="Σ 일별 잔액 ÷ 영업일수", source_module=_M_MKT),
        FormLine("1300", "월중 최고", 0, "KRW", float(path.max()),
                 source_module=_M_MKT),
        FormLine("1400", "월중 최저", 0, "KRW", float(path.min()),
                 source_module=_M_MKT),
        FormLine("2000", "월말 트레이딩목적 부채", 0, "KRW", liabs,
                 formula="Σ max(−공정가치, 0)", citation="MAR10",
                 source_module=_M_MKT, is_subtotal=True),
    ]
    day_codes = []
    for i, (d, v) in enumerate(zip(days, path), start=1):
        code = f"{3000 + i}"
        L.append(FormLine(code, f"{d:%Y-%m-%d} 트레이딩목적 자산", 1, "KRW",
                          float(v),
                          formula=f"월말 잔액 × exp({sigma:.6f} × z) — 파생값",
                          citation="파생 근거는 9000 라인",
                          source_module="risk_lib.regulatory.forms_fss_capital"))
        day_codes.append(code)
    L.append(FormLine("9000", "일별 값의 성격", 0, "text", None,
                      text_value=(f"일별 포지션 원장이 없다. 일별 잔액은 원장이 아니라 "
                                  f"파생값이며, 상대 변동성 {sigma:.4%}는 "
                                  f"백테스팅 일별 손익의 표준편차 ÷ 월말 잔액으로 "
                                  f"실제 산출에서 뽑았고, 경로는 seed="
                                  f"{int(ctx.result.meta['seed']) + 2316} 고정 RNG로 "
                                  f"만들었다. 마지막 영업일은 실제 월말 평가액으로 "
                                  f"고정했다 — 같은 seed면 같은 경로가 나온다."),
                      citation="MAR10"))
    # 요약(1200~1400)을 path에서 다시 계산해 맞춰 보면 서로 같은 배열이라 항상
    # 맞는다. 실제로 서식에 찍힌 일별 라인을 합산·비교해야 대사가 성립한다.
    daily = [_val(L, c) for c in day_codes]
    checks = [
        FormCheck("마지막 영업일 잔액 = 월말 평가액 (B2315 대사)", assets,
                  _val(L, day_codes[-1]), 1.0),
        FormCheck("일별 라인 수 = 영업일수", float(len(daily)),
                  _val(L, "1000"), 1e-9),
        FormCheck("일별 라인 합 = 일평균 × 영업일수",
                  _val(L, "1200") * _val(L, "1000"), sum(daily), 1.0),
        FormCheck("월중 최고 = 일별 라인 최대", max(daily), _val(L, "1300"), 1.0),
        FormCheck("월중 최저 = 일별 라인 최소", min(daily), _val(L, "1400"), 1.0),
        FormCheck("최고 ≥ 일평균", 0.0,
                  min(0.0, float(path.max()) - mean), 1.0),
        FormCheck("최저 ≤ 일평균", 0.0,
                  min(0.0, mean - float(path.min())), 1.0),
    ]
    return L, checks


# ---------------------------------------------------------------- B2317 / B2317-1

def _market_summary(ctx, *, rwa_total: float, basis: str, citation: str):
    """시장리스크 기준 자기자본비율 요약 — 분모만 다르고 산출 경로는 같다."""
    r = ctx.result
    cap = r.meta["capital"]
    mkt = float(r.rwa["market"])
    charge = float(r.rwa["market_detail"].capital_charge)
    L = [
        FormLine("1000", "자기자본 (총자본)", 0, "KRW", float(cap.total),
                 citation="CAP10 자본의 정의", source_module=_M_CAP,
                 is_subtotal=True),
        FormLine("2000", f"위험가중자산 합계 ({basis})", 0, "KRW", rwa_total,
                 citation=citation, source_module=_M_CAP, is_subtotal=True),
        FormLine("2100", "시장리스크 위험가중자산", 1, "KRW", mkt,
                 formula="시장리스크 소요자기자본 × 12.5", citation="CRE20.1",
                 source_module=_M_MKT),
        FormLine("2200", "시장리스크 외 위험가중자산", 1, "KRW", rwa_total - mkt,
                 formula="총 위험가중자산 − 시장리스크", source_module=_M_CAP),
        FormLine("3000", "시장리스크 소요자기자본", 0, "KRW", charge,
                 formula="MAR40 간편표준방법 위험군별 합계", citation="MAR40",
                 source_module=_M_MKT, is_subtotal=True),
        FormLine("3100", "시장리스크 부담률", 0, "ratio",
                 mkt / rwa_total if rwa_total else 0.0,
                 formula="시장리스크 RWA ÷ 총 위험가중자산", source_module=_M_MKT),
        FormLine("4000", "총자본비율 (시장리스크 포함)", 0, "ratio",
                 float(cap.total) / rwa_total if rwa_total else 0.0,
                 formula="자기자본 ÷ 총 위험가중자산",
                 citation="은행업감독규정 제26조", source_module=_M_CAP),
    ]
    checks = [
        _sum_check("총 RWA = 시장 + 시장 외", L, "2000", ("2100", "2200")),
        FormCheck("시장 RWA = 소요자기자본 × 12.5", charge * 12.5, mkt, 1.0),
        _ratio_check("총자본비율 = 자기자본/총RWA", L, "4000", "1000", "2000"),
        _ratio_check("시장리스크 부담률 = 시장RWA/총RWA", L, "3100", "2100", "2000"),
    ]
    return L, checks


def _b2317(ctx):
    """시장리스크 기준 자기자본비율 요약 — 구 바젤(표준방법 전량) 분모."""
    from risk_lib.capital.bis import BIS_MINIMUMS
    min_total = float(BIS_MINIMUMS["total"])   # 8%를 옮겨 적지 않는다
    L, checks = _market_summary(
        ctx, rwa_total=float(ctx.result.rwa["standardised_total"]),
        basis="표준방법 전량 기준", citation="구 바젤 기준 · CRE20")
    L += [
        FormLine("5000", "총자본비율 최저기준", 0, "ratio", min_total,
                 formula="risk_lib.capital.bis.BIS_MINIMUMS 참조",
                 citation="은행업감독규정 제26조 제1항 · CRE10.4",
                 source_module=_M_CAP),
        FormLine("5100", "잉여(+)·부족(−)", 0, "ratio",
                 _val(L, "4000") - min_total, formula="실측 − 최저기준",
                 source_module=_M_CAP),
        FormLine("9000", "산출방법 비고", 0, "text", None,
                 text_value="시장리스크는 MAR40 간편표준방법으로 산출했다. "
                            "민감도기반방법(SBM) 재산출이 아니며 분모는 표준방법 "
                            "전량 기준이다 — 바젤Ⅲ 기준은 B2317-1에 있다.",
                 citation="MAR40"),
    ]
    checks.append(FormCheck("잉여 = 실측 − 최저",
                            _val(L, "4000") - _val(L, "5000"),
                            _val(L, "5100"), 1e-12))
    return L, checks


def _b2317_1(ctx):
    """시장리스크 기준 자기자본비율 요약 (바젤Ⅲ) — 산출하한 적용 후 분모."""
    r = ctx.result
    L, checks = _market_summary(
        ctx, rwa_total=float(r.rwa["final_total"]),
        basis="바젤Ⅲ · 산출하한 적용 후", citation="CRE20.1 · RBC20.11")
    L += [
        FormLine("5000", "요구 총자본비율 (완충자본 포함)", 0, "ratio",
                 float(r.bis.required["total"]),
                 citation="은행업감독규정 제26조의2~4", source_module=_M_CAP),
        FormLine("5100", "잉여(+)·부족(−)", 0, "ratio",
                 float(r.bis.surplus_shortfall["total"]), source_module=_M_CAP),
        FormLine("6000", "산출하한 조정분", 0, "KRW",
                 float(r.rwa["output_floor"].add_on),
                 formula="max(0, 표준방법 RWA × 하한율 − 내부모형 RWA)",
                 citation="RBC20.11", source_module="risk_lib.capital.output_floor"),
        FormLine("9000", "산출방법 비고", 0, "text", None,
                 text_value="시장리스크는 MAR40 간편표준방법 산출치다. FRTB "
                            "민감도기반방법(MAR21)으로 재산출한 값이 아니며, "
                            "그 차이는 B2320-1·B2320-2에 남겼다.",
                 citation="MAR40 · MAR21"),
    ]
    checks.append(FormCheck("총자본비율 = 파이프라인 산출 비율",
                            float(r.bis.total_ratio), _val(L, "4000"), 1e-12))
    checks.append(FormCheck("잉여 = 실측 − 요구", _val(L, "4000") - _val(L, "5000"),
                            _val(L, "5100"), 1e-12))
    return L, checks


# ---------------------------------------------------------------- B2318-1 / B2320-x

def _market_by_class(ctx) -> dict[str, tuple[float, float]]:
    """위험군별 (순포지션, 소요자기자본). 포지션이 없는 위험군은 0으로 채운다."""
    pos = dict(zip(ctx.result.rwa["market_positions"]["risk_class"],
                   ctx.result.rwa["market_positions"]["net_position"]))
    cap = dict(ctx.result.rwa["market_detail"].by_class)
    return {rc: (float(pos.get(rc, 0.0)), float(cap.get(rc, 0.0)))
            for rc in _MKT_CLASSES}


def _b2318_1(ctx):
    """시장리스크 소요자기자본 — 간편법(MAR40). 현 산출의 정본이다."""
    from risk_lib.capital.market_risk import DEFAULT_RISK_WEIGHTS, SSA_SCALING
    md = ctx.result.rwa["market_detail"]
    by = _market_by_class(ctx)
    L = [
        FormLine("1000", "시장리스크 소요자기자본 합계", 0, "KRW",
                 float(md.capital_charge), citation="MAR40 간편표준방법",
                 source_module=_M_MKT, is_subtotal=True),
        FormLine("1010", "시장리스크 위험가중자산", 0, "KRW", float(md.rwa),
                 formula="소요자기자본 × 12.5", citation="CRE20.1",
                 source_module=_M_MKT, is_subtotal=True),
    ]
    cap_codes = []
    for i, rc in enumerate(_MKT_CLASSES, start=1):
        net, charge = by[rc]
        rw, sf = DEFAULT_RISK_WEIGHTS[rc], SSA_SCALING[rc]
        base = 1000 + i * 100
        L += [
            FormLine(str(base), f"위험군 · {_MKT_KO[rc]} — 순포지션", 1, "KRW", net,
                     formula=("포지션 미보유" if net == 0.0 else "절대값 기준 부과"),
                     citation="MAR40.1", source_module=_M_MKT),
            FormLine(str(base + 10), f"위험군 · {_MKT_KO[rc]} — 위험가중치", 2,
                     "ratio", rw,
                     formula="risk_lib.capital.market_risk"
                             ".DEFAULT_RISK_WEIGHTS — 모듈 기본값",
                     citation="MAR40 (축약 적용)", source_module=_M_MKT),
            FormLine(str(base + 20), f"위험군 · {_MKT_KO[rc]} — 조정계수", 2,
                     "ratio", sf, citation="MAR40.2 scaling factor",
                     source_module=_M_MKT),
            FormLine(str(base + 30), f"위험군 · {_MKT_KO[rc]} — 소요자기자본", 2,
                     "KRW", charge,
                     formula=f"|순포지션| × {rw:.3f} × {sf:.2f}",
                     citation="MAR40.2", source_module=_M_MKT),
        ]
        cap_codes.append(str(base + 30))
    L.append(FormLine("9000", "계수 출처 비고", 0, "text", None,
                      text_value="조정계수는 MAR40의 감독 조정계수를 그대로 쓴다. "
                                 "위험가중치는 감독당국 고시치가 아니라 "
                                 "risk_lib.capital.market_risk의 모듈 기본값이며, "
                                 "구 표준방법의 일반·개별위험 산식을 위험군당 단일 "
                                 "가중치로 축약한 것이다 — 서식은 이 값을 옮겨 적지 "
                                 "않고 모듈에서 직접 읽으므로 기본값이 바뀌면 "
                                 "서식도 따라 바뀐다.",
                      citation="MAR40"))
    checks = [
        FormCheck("위험군별 소요자본 합 = 합계", float(md.capital_charge),
                  sum(_val(L, c) for c in cap_codes), 1.0),
        FormCheck("RWA = 소요자기자본 × 12.5", float(md.capital_charge) * 12.5,
                  float(md.rwa), 1.0),
    ]
    for rc in _MKT_CLASSES:
        net, charge = by[rc]
        checks.append(FormCheck(
            f"{_MKT_KO[rc]} 소요자본 = |순포지션|×RW×조정계수",
            abs(net) * DEFAULT_RISK_WEIGHTS[rc] * SSA_SCALING[rc], charge, 1.0))
    return L, checks


def _b2320_1(ctx):
    """시장리스크 소요자기자본 — 표준방법. SBM 구성요소는 미산출이다."""
    md = ctx.result.rwa["market_detail"]
    by = _market_by_class(ctx)
    L = [
        FormLine("1000", "표준방법 소요자기자본 합계", 0, "KRW",
                 float(md.capital_charge),
                 formula="MAR40 간편표준방법 산출치를 위험군별로 분해한 것 — "
                         "MAR21 민감도기반방법 재산출이 아니다",
                 citation="MAR20 · MAR40", source_module=_M_MKT, is_subtotal=True),
    ]
    cap_codes = []
    for i, rc in enumerate(_MKT_CLASSES, start=1):
        net, charge = by[rc]
        code = f"11{i:02d}"
        L.append(FormLine(code, f"위험군 · {_MKT_KO[rc]}", 1, "KRW", charge,
                          formula=(f"순포지션 {net:,.0f}"
                                   if net else "포지션 미보유 (0)"),
                          citation="MAR40", source_module=_M_MKT))
        cap_codes.append(code)
    sbm_codes = []
    for i, (name, cite) in enumerate(
            (("델타 리스크", "MAR21.4"), ("베가 리스크", "MAR21.5"),
             ("커버쳐 리스크", "MAR21.5"), ("부도위험(DRC)", "MAR22"),
             ("잔여위험 부가(RRAO)", "MAR23")), start=1):
        code = f"21{i:02d}"
        L.append(FormLine(code, f"SBM 구성 · {name}", 1, "KRW", 0.0,
                          formula="민감도기반방법 미산출 — 간편법 적용으로 0",
                          citation=cite, source_module=_M_MKT))
        sbm_codes.append(code)
    L.append(FormLine("9000", "표준방법 적용 수준", 0, "text", None,
                      text_value="현 산출은 MAR40 간편표준방법이며 B2318-1이 정본이다. "
                                 "본 서식의 위험군별 금액은 그 값을 분해한 것이고, "
                                 "SBM 델타·베가·커버쳐·DRC·RRAO는 산출하지 않았다 — "
                                 "0은 '위험이 없다'가 아니라 '산출하지 않았다'이다.",
                      citation="MAR21 · MAR40"))
    checks = [
        FormCheck("위험군별 합 = 표준방법 합계", float(md.capital_charge),
                  sum(_val(L, c) for c in cap_codes), 1.0),
        FormCheck("SBM 구성요소 합 = 0 (미산출)", 0.0,
                  sum(_val(L, c) for c in sbm_codes), 1e-9),
        FormCheck("표준방법 합계 = 간편법 산출액", float(md.capital_charge),
                  _val(L, "1000"), 1.0),
    ]
    return L, checks


def _b2320_2(ctx):
    """표준방법 상세 — 위험요소 관측과 민감도. 자본은 B2320-1이 정본이다."""
    rf = ctx.tables["mkt_risk_factor"]
    tr = ctx.tables["mkt_trade"]
    L = [
        FormLine("1000", "위험요소 총수", 0, "count", float(len(rf)),
                 citation="MAR31 위험요소 관측", source_module="risk_lib.market_data",
                 is_subtotal=True),
        FormLine("1100", "모형화 가능 (MRF)", 1, "count",
                 float(int(rf["modellable"].sum())), citation="MAR31.12 RFET",
                 source_module="risk_lib.market_data"),
        FormLine("1200", "모형화 불가 (NMRF)", 1, "count",
                 float(int((~rf["modellable"]).sum())),
                 formula="RFET 미충족", citation="MAR31.12",
                 source_module="risk_lib.market_data"),
    ]
    rc_codes = []
    for i, (rc, sub) in enumerate(rf.groupby("risk_class"), start=1):
        code = f"21{i:02d}"
        L.append(FormLine(code, f"위험군 · {_MKT_KO.get(rc, rc)} — 위험요소 수", 1,
                          "count", float(len(sub)),
                          formula=" · ".join(sorted(set(sub["curve"]))),
                          citation="MAR31", source_module="risk_lib.market_data"))
        rc_codes.append(code)
    sens = (("dv01", "금리 민감도 DV01", "MAR21.4 GIRR 델타"),
            ("cs01", "신용스프레드 민감도 CS01", "MAR21.4 CSR 델타"),
            ("delta", "주식 델타", "MAR21.4 EQ 델타"),
            ("vega", "베가", "MAR21.5 베가"))
    for i, (col, name, cite) in enumerate(sens, start=1):
        L.append(FormLine(f"31{i:02d}", name, 1, "count", float(tr[col].sum()),
                          formula=f"트레이딩 원장 {col} 합계 — 자본 환산 전 원자료",
                          citation=cite, source_module=_M_MKT))
    kind_codes = []
    for i, (kind, sub) in enumerate(tr.groupby("kind"), start=1):
        code = f"41{i:02d}"
        L.append(FormLine(code, f"상품유형 · {_TRADE_KO.get(kind, kind)} — 건수", 1,
                          "count", float(len(sub)),
                          formula=f"명목 {sub['notional'].sum():,.0f}",
                          source_module=_M_MKT))
        kind_codes.append(code)
    L += [
        FormLine("5000", "거래 총건수", 0, "count", float(len(tr)),
                 source_module=_M_MKT, is_subtotal=True),
        FormLine("9000", "상세 산출 수준", 0, "text", None,
                 text_value="민감도는 트레이딩 원장의 실측값이나, 이를 MAR21 위험가중치·"
                            "상관행렬에 통과시킨 SBM 자본은 산출하지 않았다. "
                            "소요자기자본은 B2318-1(간편법)이 정본이다.",
                 citation="MAR21"),
    ]
    checks = [
        FormCheck("MRF + NMRF = 위험요소 총수", float(len(rf)),
                  _val(L, "1100") + _val(L, "1200"), 1e-9),
        FormCheck("위험군별 위험요소 합 = 총수", float(len(rf)),
                  sum(_val(L, c) for c in rc_codes), 1e-9),
        FormCheck("상품유형별 건수 합 = 거래 총건수", float(len(tr)),
                  sum(_val(L, c) for c in kind_codes), 1e-9),
    ]
    return L, checks


# ---------------------------------------------------------------- B2324

def _b2324(ctx):
    """경기대응완충자본 — 국가별 위험가중자산과 적립률."""
    from risk_lib.capital.bis import BIS_MINIMUMS
    from risk_lib.references import CAPITAL_CONSERVATION_BUFFER

    t = _onbalance_frame(ctx).merge(
        ctx.portfolio[["exposure_id", "country"]], on="exposure_id", how="left")
    credit = float(t["rwa"].sum())
    sov = float(t[t["asset_class"] == "sovereign"]["rwa"].sum())
    private = t[t["asset_class"] != "sovereign"]
    private_rwa = float(private["rwa"].sum())
    L = [
        FormLine("1000", "신용리스크 위험가중자산 합계", 0, "KRW", credit,
                 citation="CRE20 · CRE31", source_module=_M_RWA, is_subtotal=True),
        FormLine("1010", "국가·중앙은행 익스포저 (적용 제외)", 0, "KRW", sov,
                 formula="경기대응완충자본은 민간부문 신용익스포저에만 적용",
                 citation="RBC30.7", source_module=_M_RWA),
        FormLine("1100", "경기대응완충자본 적용대상 민간부문 RWA", 0, "KRW",
                 private_rwa, formula="신용 RWA − 국가·중앙은행 익스포저",
                 citation="RBC30.7", source_module=_M_RWA, is_subtotal=True),
    ]
    rwa_codes, share_codes = [], []
    for i, (ctry, sub) in enumerate(private.groupby("country"), start=1):
        base = 2000 + i * 10
        share = float(sub["rwa"].sum()) / private_rwa if private_rwa else 0.0
        L += [
            FormLine(str(base), f"국가 · {ctry} — 위험가중자산", 1, "KRW",
                     float(sub["rwa"].sum()),
                     formula=f"{len(sub):,}건 · EAD {sub['ead_final'].sum():,.0f}",
                     citation="RBC30.9 익스포저 소재국 기준", source_module=_M_RWA),
            FormLine(str(base + 1), f"국가 · {ctry} — 비중", 2, "ratio", share,
                     formula="국가별 RWA ÷ 민간부문 RWA", source_module=_M_RWA),
            FormLine(str(base + 2), f"국가 · {ctry} — 적립률", 2, "ratio", 0.0,
                     formula="각국 감독당국 고시 적립률 원장 미보유 → 0",
                     citation="RBC30.4", source_module=_M_CAP),
        ]
        rwa_codes.append(str(base))
        share_codes.append(str(base + 1))
    ccyb = 0.0     # Σ 비중 × 국가별 적립률. 적립률이 모두 0이므로 결과도 0이다.
    buffer_total = float(ctx.result.bis.required["cet1"]) - BIS_MINIMUMS["cet1"]
    L += [
        FormLine("3000", "은행 고유 경기대응완충자본 적립률", 0, "ratio", ccyb,
                 formula="Σ (국가별 민간부문 RWA 비중 × 국가별 적립률)",
                 citation="RBC30.5 · 은행업감독규정 제26조의3", source_module=_M_CAP,
                 is_subtotal=True),
        FormLine("3100", "경기대응완충자본 소요액", 0, "KRW",
                 ccyb * float(ctx.result.rwa["final_total"]),
                 formula="적립률 × 총 위험가중자산", source_module=_M_CAP),
        FormLine("4000", "완충자본 요구 합계", 0, "ratio", buffer_total,
                 formula="요구 보통주자본비율 − 최저 4.5%",
                 citation="은행업감독규정 제26조의2~4", source_module=_M_CAP,
                 is_subtotal=True),
        FormLine("4100", "자본보전완충자본", 1, "ratio",
                 CAPITAL_CONSERVATION_BUFFER, citation="RBC30.1 · 제26조의2"),
        FormLine("4200", "경기대응완충자본", 1, "ratio", ccyb,
                 citation="RBC30 · 제26조의3", source_module=_M_CAP),
        FormLine("4300", "시스템적 중요 은행 가산 (잔여)", 1, "ratio",
                 buffer_total - CAPITAL_CONSERVATION_BUFFER - ccyb,
                 formula="완충자본 요구 합계 − 자본보전 − 경기대응",
                 citation="RBC40 · 제26조의4", source_module=_M_CAP),
        FormLine("9000", "적립률 원장 비고", 0, "text", None,
                 text_value="국가별 경기대응완충자본 고시 적립률 원장이 없어 전 국가 "
                            "0으로 두었다. 국가별 위험가중자산 분해는 익스포저 원장의 "
                            "소재국으로 실제 산출한 값이며, 적립률만 미보유다.",
                 citation="RBC30.4"),
    ]
    checks = [
        # 국가익스포저액을 허용오차로 넘기면 항등식이 되어 아무것도 검증하지 못한다.
        # 차감이 실제로 성립하는지(merge 누락·자산군 결측 포함) 직접 대사한다.
        FormCheck("민간부문 RWA = 신용 RWA − 국가 익스포저", credit - sov,
                  _val(L, "1100"), 1.0),
        FormCheck("국가별 RWA 합 = 민간부문 RWA", private_rwa,
                  sum(_val(L, c) for c in rwa_codes), 1.0),
        FormCheck("국가별 비중 합 = 1", 1.0,
                  sum(_val(L, c) for c in share_codes), 1e-9),
        _sum_check("완충자본 요구 = 자본보전 + 경기대응 + D-SIB", L, "4000",
                   ("4100", "4200", "4300"), tol=1e-12),
        FormCheck("경기대응 소요액 = 적립률 × 총RWA",
                  ccyb * float(ctx.result.rwa["final_total"]),
                  _val(L, "3100"), 1.0),
    ]
    return L, checks


# ---------------------------------------------------------------- B2328 / B2328-1 / B2329

def _b2328(ctx):
    """CVA리스크 소요자기자본 — 기초법(BA-CVA) 축약형. 현 산출의 정본이다."""
    from risk_lib.ccr import cva_capital_charge
    c = ctx.result.ccr
    bc = c.by_counterparty
    ead_sq = float((bc["ead"] ** 2).sum()) if len(bc) else 0.0
    root = float(np.sqrt(ead_sq))
    # κ는 상수를 옮겨 적지 않고 산출 결과에서 역산한다 — 모듈 기본값이 바뀌면
    # 서식이 조용히 어긋나는 것을 막는다.
    kappa = float(c.cva_charge) / root if root else 0.0
    L = [
        FormLine("1000", "CVA 대상 거래상대방 수", 0, "count",
                 float(c.n_counterparties), citation="MAR50.2",
                 source_module=_M_CCR, is_subtotal=True),
        FormLine("1100", "CVA 대상 익스포저(EAD) 합계", 0, "KRW",
                 float(c.ead_total), formula="SA-CCR: α × (RC + PFE)",
                 citation="CRE52.1", source_module=_M_CCR, is_subtotal=True),
        FormLine("1200", "거래상대방별 EAD 제곱합의 제곱근", 0, "KRW", root,
                 formula="√(Σ EAD_i²) — 상계 미인정 축약형",
                 citation="MAR50.14 BA-CVA 축약형(reduced version)",
                 source_module=_M_CCR),
        FormLine("2000", "감독계수 κ (모듈 파라미터)", 0, "ratio", kappa,
                 formula="산출 결과에서 역산 (K_BA ÷ √(Σ EAD_i²)) — "
                         "감독당국 고시 계수가 아니라 risk_lib.ccr의 파라미터다",
                 citation="MAR50.14 (축약 적용)", source_module=_M_CCR),
        FormLine("3000", "CVA 소요자기자본 K_BA", 0, "KRW",
                 float(c.cva_charge),
                 formula="κ × √(Σ EAD_i²) — 자본 기준 산출액",
                 citation="MAR50.14", source_module=_M_CCR, is_subtotal=True),
        FormLine("3100", "CVA 위험가중자산", 0, "KRW", _cva_rwa(c.cva_charge),
                 formula="CVA 소요자기자본 × 12.5 (최저비율 8%의 역수)",
                 citation="MAR50.2 · RBC20.6", source_module=_M_CCR,
                 is_subtotal=True),
        FormLine("4000", "거래상대방신용리스크 위험가중자산 (SA-CCR)", 0, "KRW",
                 float(c.rwa_total), formula="Σ EAD × 위험가중치",
                 citation="CRE52", source_module=_M_CCR, is_subtotal=True),
        FormLine("5000", "CCR + CVA 합계", 0, "KRW", float(ctx.result.rwa["ccr"]),
                 formula="SA-CCR RWA + CVA RWA", citation="CRE52 · MAR50",
                 source_module=_M_CAP, is_subtotal=True),
        FormLine("9000", "적용 방법 비고", 0, "text", None,
                 text_value="현 산출은 BA-CVA 축약형(헤지 미인정)이다. 표준방법"
                            "(SA-CVA)은 산출하지 않았으며 그 사실은 B2329에 있다.",
                 citation="MAR50.14 · MAR50 SA-CVA"),
        FormLine("9100", "산식·단위 한계", 0, "text", None,
                 text_value="두 가지를 밝혀 둔다. (1) MAR50.14의 축약형은 "
                            "거래상대방별 독립 CVA자본(SCVA)을 상관계수 ρ로 "
                            "집계하는 식이나, risk_lib.ccr는 감독 위험가중치와 ρ를 "
                            "단일 계수 κ에 접어 넣고 EAD에 직접 적용한다 — 본 라인의 "
                            "산식은 MAR50.14의 대용치이지 그 자체가 아니다. "
                            "(2) 단위 기준은 확정됐다 — 산출값은 소요자기자본"
                            "(K_BA)이며 RWA는 12.5배 환산치다(MAR50.2·RBC20.6). "
                            "이전에는 K를 RWA로 그대로 합산해 CVA가 12.5배 과소"
                            "계상되고 있었고, 본 서식 저작 중 드러나 정정했다.",
                 citation="MAR50.14 · CRE20.1"),
    ]
    checks = [
        _sum_check("CCR+CVA 합계 = SA-CCR RWA + CVA RWA", L, "5000",
                   ("4000", "3100")),
        FormCheck("EAD 합계 = 거래상대방별 EAD 합",
                  float(bc["ead"].sum()) if len(bc) else 0.0,
                  float(c.ead_total), 1.0),
        FormCheck("K_BA = κ × √(Σ EAD²)", kappa * root,
                  float(c.cva_charge), 1.0),
        FormCheck("CVA 재계산 = 산출 결과",
                  float(cva_capital_charge(bc)) if len(bc) else 0.0,
                  float(c.cva_charge), 1.0),
        FormCheck("소요자기자본 = CVA RWA × 8%", _val(L, "3100") * 0.08,
                  _val(L, "3000"), 1.0),
    ]
    return L, checks


def _b2328_1(ctx):
    """CVA 기초법 상세 — 거래상대방별 EAD와 자본 기여도."""
    c = ctx.result.ccr
    bc = c.by_counterparty.sort_values("ead", ascending=False)
    ead_sq = float((bc["ead"] ** 2).sum()) if len(bc) else 0.0
    root = float(np.sqrt(ead_sq))
    L = [
        FormLine("1000", "거래상대방 수", 0, "count", float(len(bc)),
                 citation="MAR50.2", source_module=_M_CCR, is_subtotal=True),
        FormLine("1100", "EAD 합계", 0, "KRW", float(bc["ead"].sum()),
                 citation="CRE52.1", source_module=_M_CCR, is_subtotal=True),
        FormLine("1200", "√(Σ EAD_i²)", 0, "KRW", root,
                 formula="상계 미인정 축약형의 집계항", citation="MAR50.14",
                 source_module=_M_CCR),
        FormLine("2000", "CVA 소요자기자본 K_BA (기초법)", 0, "KRW",
                 float(c.cva_charge), citation="MAR50.14", source_module=_M_CCR,
                 is_subtotal=True),
        FormLine("2100", "CVA 위험가중자산", 0, "KRW", _cva_rwa(c.cva_charge),
                 formula="K_BA × 12.5", citation="MAR50.2 · RBC20.6",
                 source_module=_M_CCR, is_subtotal=True),
    ]
    ead_codes, w_codes = [], []
    for i, (_, row) in enumerate(bc.iterrows(), start=1):
        base = 3000 + i * 10
        w = float(row["ead"]) ** 2 / ead_sq if ead_sq else 0.0
        L += [
            FormLine(str(base), f"거래상대방 · {row['counterparty']} — EAD", 1,
                     "KRW", float(row["ead"]),
                     formula=(f"RC {row['rc']:,.0f} + PFE {row['pfe']:,.0f} "
                              f"→ α 1.4 적용"),
                     citation="CRE52.1", source_module=_M_CCR),
            FormLine(str(base + 1), f"거래상대방 · {row['counterparty']} — 기여도",
                     2, "ratio", w, formula="EAD_i² ÷ Σ EAD_i²",
                     citation="MAR50.14", source_module=_M_CCR),
        ]
        ead_codes.append(str(base))
        w_codes.append(str(base + 1))
    L.append(FormLine("9000", "헤지 인식 비고", 0, "text", None,
                      text_value="축약형이므로 CVA 헤지(단일·지수 CDS)는 인식하지 "
                                 "않았다. 헤지 원장이 없어 0으로 둔 것이 아니라 "
                                 "적용 방법상 인식 대상이 아니다.",
                      citation="MAR50.14"))
    checks = [
        FormCheck("거래상대방별 EAD 합 = EAD 합계", float(bc["ead"].sum()),
                  sum(_val(L, c_) for c_ in ead_codes), 1.0),
        FormCheck("기여도 합 = 1", 1.0,
                  sum(_val(L, c_) for c_ in w_codes), 1e-9),
        FormCheck("√(Σ EAD²) = 집계항", root, _val(L, "1200"), 1.0),
    ]
    return L, checks


def _b2329(ctx):
    """CVA리스크 소요자기자본 — 표준방법(SA-CVA). 현 산출은 미적용이다."""
    c = ctx.result.ccr
    tr = ctx.tables["mkt_trade"]
    L = [
        FormLine("1000", "표준방법(SA-CVA) 적용 승인 여부", 0, "count", 0.0,
                 formula="1 = 승인·적용, 0 = 미적용",
                 citation="MAR50 SA-CVA — 감독당국 사전승인 요건",
                 source_module=_M_CCR, is_subtotal=True),
        FormLine("1100", "SA-CVA 소요자기자본", 0, "KRW", 0.0,
                 formula="미산출 — CVA 델타·베가 민감도를 생성하지 않는다",
                 citation="MAR50 SA-CVA 민감도 요건", source_module=_M_CCR),
        FormLine("1200", "CVA 민감도 산출 대상 위험군 수", 0, "count", 0.0,
                 formula="SA-CVA가 요구하는 위험군별 CVA 민감도 미보유",
                 citation="MAR50 SA-CVA 민감도 요건", source_module=_M_CCR),
        FormLine("2000", "기초법(BA-CVA) 산출액", 0, "KRW", float(c.cva_charge),
                 formula="본 은행의 CVA 소요자본 정본 — B2328 참조",
                 citation="MAR50.14", source_module=_M_CCR, is_subtotal=True),
        FormLine("3000", "CVA 소요자본 총계", 0, "KRW", float(c.cva_charge),
                 formula="SA-CVA + BA-CVA", citation="MAR50",
                 source_module=_M_CCR, is_subtotal=True),
        FormLine("4000", "참고 · 트레이딩 민감도 보유 건수", 0, "count",
                 float(int((tr[["delta", "vega", "dv01", "cs01"]].abs().sum(axis=1)
                            > 0).sum())),
                 formula="시장리스크용 민감도는 있으나 CVA 민감도와 다르다",
                 citation="MAR21 · MAR50 SA-CVA", source_module=_M_MKT),
        FormLine("9000", "미산출 사유", 0, "text", None,
                 text_value="SA-CVA는 감독당국 사전승인과 CVA 민감도 산출 체계를 "
                            "전제한다. 본 파이프라인은 두 요건을 갖추지 않아 "
                            "0으로 두었다 — 위험이 없어서 0이 아니라 산출하지 "
                            "않아서 0이다. 정본은 B2328(기초법)이다.",
                 citation="MAR50 SA-CVA"),
    ]
    checks = [
        _sum_check("CVA 총계 = SA-CVA + BA-CVA", L, "3000", ("1100", "2000")),
        FormCheck("SA-CVA 미적용 시 소요자본 = 0", 0.0, _val(L, "1100"), 1e-9),
    ]
    return L, checks


# ---------------------------------------------------------------- BA2320 / BA2327

def _ba2320(ctx):
    """기타의 자산 — 세부 원장이 없어 위험가중을 산출하지 않았다."""
    bs = ctx.tables["pru_balance_sheet"]
    amt = dict(zip(bs["item"], bs["amount"]))
    other = float(amt["기타자산"])
    total = float(amt["자산총계"])
    L = [
        FormLine("1000", "기타의 자산 잔액", 0, "KRW", other,
                 formula="자산총계 − (현금·예치금 + 유가증권 + 대출채권 순액)",
                 citation="은행업감독규정 제99조 업무보고서", source_module=_M_PRU,
                 is_subtotal=True),
        FormLine("1100", "자산총계", 0, "KRW", total, source_module=_M_PRU),
        FormLine("1200", "총자산 대비 비중", 0, "ratio",
                 other / total if total else 0.0,
                 formula="기타의 자산 ÷ 자산총계", source_module=_M_PRU),
    ]
    for i, item in enumerate(("현금 및 예치금", "유가증권 (Level 2A)",
                              "유가증권 (Level 2B)", "대출채권 (순액)"), start=1):
        L.append(FormLine(f"20{i:02d}", f"차감 · {item}", 1, "KRW",
                          float(amt[item]), source_module=_M_PRU))
    L += [
        FormLine("3000", "기타의 자산 위험가중자산", 0, "KRW", 0.0,
                 formula="미산출 — 세부 구성(현금·유형자산·미수금·이연법인세) 원장 미보유",
                 citation="CRE20.101 기타자산 위험가중치", source_module=_M_RWA,
                 is_subtotal=True),
        FormLine("3100", "적용 위험가중치", 0, "ratio", 0.0,
                 formula="미산출 — 감독규정 기본 100%를 임의로 적용하지 않았다",
                 citation="CRE20.101"),
        FormLine("9000", "미산출 사유", 0, "text", None,
                 text_value="기타의 자산 잔액은 재무상태표에서 확인한 실제 산출값이나 "
                            "세부 구성 원장이 없어 위험가중치를 적용하지 않았다. "
                            "3000 라인의 0은 '위험가중자산이 없다'가 아니라 "
                            "'산출하지 않았다'이며, 그만큼 B2304·BA2303-2의 "
                            "위험가중자산이 과소계상돼 있다.",
                 citation="CRE20.101"),
    ]
    checks = [
        FormCheck("기타의 자산 = 자산총계 − 나머지 계정", other,
                  total - sum(_val(L, f"20{i:02d}") for i in range(1, 5)), 1.0),
        _ratio_check("비중 = 기타의 자산 ÷ 자산총계", L, "1200", "1000", "1100"),
    ]
    return L, checks


# 유동화 익스포저로 볼 수 있는 자산군 어휘 — 원장을 확인했다는 증거로 남긴다.
_SEC_CLASSES = ("securitisation", "resecuritisation", "abs", "mbs", "cdo")


def _ba2327(ctx):
    """유동화익스포져 — 포트폴리오에 해당 자산군이 없다."""
    ex = ctx.tables["rdm_exposure"]
    present = sorted(set(ex["asset_class"]))
    sec = ex[ex["asset_class"].isin(_SEC_CLASSES)]
    L = [
        FormLine("1000", "유동화 익스포저 건수", 0, "count", float(len(sec)),
                 formula=f"자산군 어휘 {' · '.join(_SEC_CLASSES)} 조회 결과",
                 citation="CRE40 유동화 프레임워크", source_module=_M_RDM,
                 is_subtotal=True),
        FormLine("1100", "유동화 익스포저 잔액", 0, "KRW",
                 float(sec["ead"].sum()), source_module=_M_RDM),
        FormLine("2000", "유동화 익스포저 위험가중자산", 0, "KRW", 0.0,
                 formula="대상 익스포저 없음 → SEC-IRBA·SEC-ERBA·SEC-SA 미적용",
                 citation="CRE44 SEC-IRBA · CRE42 SEC-ERBA · CRE41 SEC-SA",
                 source_module=_M_RWA, is_subtotal=True),
        FormLine("3000", "총 익스포저 건수 (참고)", 0, "count", float(len(ex)),
                 source_module=_M_RDM, is_subtotal=True),
    ]
    ac_codes = []
    for i, (ac, sub) in enumerate(ex.groupby("asset_class"), start=1):
        code = f"31{i:02d}"
        L.append(FormLine(code, f"자산군 · {ac} — 건수", 1, "count", float(len(sub)),
                          formula=f"EAD {sub['ead'].sum():,.0f}",
                          source_module=_M_RDM))
        ac_codes.append(code)
    L.append(FormLine("9000", "조회 결과 비고", 0, "text", None,
                      text_value=(f"익스포저 원장의 자산군은 {' · '.join(present)}이며 "
                                  f"유동화·재유동화 익스포저가 없다. 0은 원장을 조회한 "
                                  f"결과이며 미조회가 아니다. 유동화 익스포저가 생기면 "
                                  f"CRE41~44 위계에 따라 산출방법을 먼저 정해야 한다."),
                      citation="CRE40"))
    checks = [
        FormCheck("자산군별 건수 합 = 총 익스포저 건수", float(len(ex)),
                  sum(_val(L, c) for c in ac_codes), 1e-9),
        FormCheck("유동화 익스포저 없음 → RWA 0", 0.0, _val(L, "2000"), 1e-9),
        FormCheck("유동화 잔액 = 0", 0.0, _val(L, "1100"), 1.0),
    ]
    return L, checks


# ---------------------------------------------------------------- 등록

BUILDERS: dict[str, tuple[str, str, Callable]] = {
    "B2301": ("은행업감독규정 제26조 · Basel III CRE20·CAP10", "PRD-CAP", _b2301),
    "B2304": ("Basel III CRE20·CRE31 · 은행업감독규정 제26조", "PRD-RWA", _b2304),
    "B2308": ("Basel III CRE20.94 신용환산율 · 은행업감독업무시행세칙", "PRD-RWA",
              _b2308),
    "B2311": ("은행업감독규정 제26조 — 연결기준 자기자본비율", "PRD-CAP", _b2311),
    "B2312": ("은행업감독규정 제26조·제99조 · Basel III CRE20", "PRD-RWA", _b2312),
    "B2315": ("Basel III MAR10 트레이딩계정 · 은행업감독규정 제26조", "PRD-MKT",
              _b2315),
    "B2316": ("Basel III MAR10 · 은행업감독규정 제99조 업무보고서", "PRD-MKT",
              _b2316),
    "B2317": ("Basel III MAR40 · 은행업감독규정 제26조", "PRD-MKT", _b2317),
    "B2317-1": ("Basel III MAR20·MAR40 · 은행업감독규정 제26조", "PRD-MKT",
                _b2317_1),
    "B2318-1": ("Basel III MAR40 간편표준방법", "PRD-MKT", _b2318_1),
    "B2320-1": ("Basel III MAR20·MAR21 표준방법", "PRD-MKT", _b2320_1),
    "B2320-2": ("Basel III MAR21·MAR31 표준방법 상세", "PRD-MKT", _b2320_2),
    "B2324": ("Basel III RBC30 · 은행업감독규정 제26조의3", "PRD-CAP", _b2324),
    "B2328": ("Basel III MAR50.14 BA-CVA 축약형", "PRD-MKT", _b2328),
    "B2328-1": ("Basel III MAR50.14 BA-CVA 축약형 · CRE52 SA-CCR", "PRD-MKT", _b2328_1),
    "B2329": ("Basel III MAR50 SA-CVA", "PRD-MKT", _b2329),
    "BA2303-2": ("은행업감독규정 제26조 · Basel III CRE31·CRE32·RBC20.11",
                 "PRD-CAP", _ba2303_2),
    "BA2320": ("Basel III CRE20.101 · 은행업감독규정 제99조", "PRD-RWA", _ba2320),
    "BA2327": ("Basel III CRE40~CRE44 유동화 프레임워크", "PRD-RWA", _ba2327),
}
