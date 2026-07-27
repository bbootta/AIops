"""금감원 FINES 업무보고서 — 주요재무현황·생산성·은행유형별 22건.

근거는 은행업감독규정 제99조(업무보고서)·제27조(자산건전성 분류)와 은행법
제33조(금융채 발행)·제35조의2·제35조의3(대주주 거래)·제37조(자회사)이며,
B2214~B2217은 Basel III SCO40(G-SIB 평가방법론)이다.

**같은 수치가 두 서식에서 갈리지 않게 한 곳**
  금융채권(B2204~B2206)  `forms_fss_compliance_data.debentures`를 B3116~B3118과
                         **같은 앵커**(재무상태표 사채 및 장기차입금 · 보완자본
                         인정 후순위채)로 호출한다. 같은 채권이 두 서식에서 다른
                         금액이면 제출본이 성립하지 않는다.
  대주주 거래(B2211)      `pru_ownership_limit`에 그대로 앵커한다 — BR-27(B3115)·
                         B3000이 쓰는 바로 그 테이블이다. 대주주 지정 원장이 없어
                         신용공여는 0이며, 0은 "없다"가 아니라 "확인해야 한다"이다.
  자회사(B5102)          `forms_fss_compliance_data.subsidiary_book` 재사용.
                         B3110·B3111과 같은 자회사 목록·출자금액·지분율이다.
  임직원·점포(B2701·B5103) `forms_fss_keyfin_data.headcount` · `domestic_branches`.
                         인원 파생을 여기서 처음 만들었고, B1101(인원현황)을 만드는
                         `forms_fss_general_data`가 이 headcount를 그대로 import해
                         쓰고 있다 — B1101·B1104와 임직원 수·국내 점포 수가 같다.
                         새 서식이 인원·점포를 쓸 때도 여기를 그대로 불러야 한다.
  해외 점포(B5103)        `forms_fss_overseas_data.branch_master` — BF103과 같은 값.
  국내·해외 비중(B2217)   `forms_fss_financial_data.domestic_share` — 실측 EAD 비중.

**미해결 충돌 — 통합 시 조정 필요.** B2201의 기중평잔과 손익 그룹의
`forms_fss_profit_data.avg_balance`가 같은 개념을 다른 산식으로 파생한다.
사유와 합칠 때의 기준은 `forms_fss_keyfin_data` docstring에 적었다.

**연결은 단독과 같다(B5101).** 연결 대상 자회사의 재무제표·연결범위·소수주주
지분 원장이 없다. forms_fss_financial의 B2109·B2118과 forms_fss_capital의
B2311·B2312가 이미 같은 처리를 했으므로 문구를 맞췄다. 자회사 규모 자체는
B5102가 파생값으로 따로 보고한다 — 연결재무제표에 밀어 넣으면 B2109와 총자산이
갈린다.

**미영위로 0을 적은 것** — 신탁계정(B2203). forms_fss_financial의 B2104·B2105와
같은 판단이며 사유를 라인마다 남긴다.

원장이 없어 시드 고정으로 파생한 항목과 그 근거는 `forms_fss_keyfin_data`
docstring에 모았다. 파생 라인은 그 라인의 formula에 파생임을 남긴다.

서식명·작성주기는 여기 적지 않는다 — FINES 마스터가 정본이고 forms.py가 붙인다.
"""

from __future__ import annotations

from typing import Callable

import pandas as pd

from risk_lib.regulatory.forms_base import (
    FormCheck, FormLine, _ratio_check, _sum_check, _val,
)
from risk_lib.regulatory.forms_fss_compliance_data import (
    DEBENTURE_BAND_MID, DEBENTURE_BANDS, debentures,
)
from risk_lib.regulatory.forms_fss_financial_data import (
    CORP_DEPOSITS, RETAIL_DEPOSITS, bs_amounts, domestic_share, tol,
    trading_position,
)
from risk_lib.regulatory.forms_fss_keyfin_data import (
    LOAN_SIZE_BANDS, NPL_CLASSES, NPL_DPD, average_balance, band_of,
    domestic_branches, domestic_market_share, fi_liability_book, headcount,
    level3_assets, public_deposits, substitutability, subsidiary_performance,
)
from risk_lib.regulatory.forms_fss_overseas_data import (
    HOME_COUNTRY, branch_master,
)

_M_PRU = "risk_lib.prudential.financials"
_M_CAP = "risk_lib.capital.bis · risk_lib.capital.bis_deep"
_M_OWN = "risk_lib.prudential.ownership"
_M_LEV = "risk_lib.capital.leverage · risk_lib.capital.leverage_deep"
_M_RDM = "risk_lib.datamodel.materialize_detail"
_M_PTF = "risk_lib.data_gen.generate_portfolio"
_M_CCR = "risk_lib.ccr"
_M_ALM = "risk_lib.alm"
_M_DER = "risk_lib.regulatory.forms_fss_keyfin_data"
_M_DEB = "risk_lib.regulatory.forms_fss_compliance_data"
# 미영위 계정에는 산출 모듈이 없다. 빈 문자열은 "못 채웠다"로 읽힌다.
_M_NONE = "해당 계정 미영위 — 산출 모듈 없음"

_C99 = "은행업감독규정 제99조 업무보고서"
_C27 = "은행업감독규정 제27조 자산건전성 분류"
_C33 = "은행법 제33조 — 금융채 발행 · 은행업감독규정 제99조"
_C_TRUST = "은행법 제28조 겸영업무 · 자본시장과 금융투자업에 관한 법률 제103조"
_C_FUND = "국고금 관리법 제36조 · 지방회계법 제77조 — 금고 지정"
_C_SCO = "Basel III SCO40 — G-SIB 평가방법론"
# SCO40의 지표 범주별 문단 번호. Basel Framework SCO40 본문 기준이며
# .4 국가간 활동 · .5 규모 · .6 상호연계성 · .7 대체가능성 · .8 복잡성이다.
# 범주와 문단이 어긋나면 서식이 다른 지표의 근거를 달게 되므로 상수로 고정한다.
_C_SCO_SIZE = "Basel III SCO40.5 — 규모"
_C_SCO_INTER = "Basel III SCO40.6 — 상호연계성"
_C_SCO_SUBS = "Basel III SCO40.7 — 대체가능성"
_C_SCO_CPLX = "Basel III SCO40.8 — 복잡성"
# 지표 점수(bp) 산정 문단은 번호를 적지 않는다 — 확인하지 못한 문단 번호를 적는
# 것은 문단을 적지 않는 것보다 나쁘다. 산식(자행 지표 ÷ 표본 합계 × 10,000bp)만 남긴다.
_C_SCO_SCORE = f"{_C_SCO} — 지표 점수 = 자행 지표 ÷ 표본 은행 합계 × 10,000bp"

_DERIVED = "원장 부재 — 기준일 고정 시드 파생값"
_TRUST_REASON = "신탁계정 미영위 — 원천 데이터에 신탁 계정과목 없음"
_CONSOL = "연결 자회사 원장 없음 → 연결 = 단독"


# ---------------------------------------------------------------- 공용

def _remark(text: str, citation: str) -> FormLine:
    return FormLine("9000", "비고", 0, "text", None, text_value=text,
                    citation=citation)


def _income(ctx) -> dict[str, float]:
    t = ctx.tables["pru_income_statement"]
    return {str(k): float(v) for k, v in zip(t["item"], t["amount"])}


def _debenture_facts(ctx) -> dict:
    """금융채권 파생 묶음 — B3116~B3118과 **같은 앵커로 같은 함수**를 부른다.

    compliance 쪽 private 헬퍼를 import하지 않고 앵커 두 개를 여기서 다시
    읽는다. `debentures`가 입력에 대해 결정론적이므로 결과는 반드시 같다.
    """
    t2 = ctx.result.bis_deep.tier2_table
    sub = float(t2.loc[t2["item"].str.startswith("후순위채(잔존"), "amount"].iloc[0])
    return debentures(bs_amounts(ctx)["사채 및 장기차입금"], sub)


def _npl_book(ctx) -> pd.DataFrame:
    """무수익여신 산정대상 여신 — 고정이하 분류 또는 3개월 이상 연체. 전부 산출값이다."""
    aq = ctx.tables["rdm_asset_quality"][
        ["exposure_id", "classification", "borrower_type", "dpd", "balance"]]
    df = aq.merge(ctx.tables["rdm_exposure"][["exposure_id", "obligor_id"]],
                  on="exposure_id")
    df["npl_class"] = df["classification"].isin(NPL_CLASSES)
    df["npl_dpd"] = df["dpd"] >= NPL_DPD
    return df[df["npl_class"] | df["npl_dpd"]].reset_index(drop=True)


def _bank_book(ctx) -> pd.DataFrame:
    """타 금융회사(은행) 익스포저 — 여신·미사용약정·파생 EAD를 상대방별로 묶는다."""
    p = ctx.portfolio
    ex = ctx.tables["rdm_exposure"][["exposure_id", "obligor_id", "drawn",
                                     "undrawn"]]
    df = (p.loc[p["asset_class"] == "bank", ["exposure_id", "obligor_id", "ead"]]
          .merge(ex[["exposure_id", "drawn", "undrawn"]], on="exposure_id")
          .groupby("obligor_id", as_index=False)
          .agg(ead=("ead", "sum"), drawn=("drawn", "sum"),
               undrawn=("undrawn", "sum"), n=("exposure_id", "count")))
    ccr = (ctx.result.ccr.by_counterparty[["counterparty", "ead"]]
           .rename(columns={"counterparty": "obligor_id", "ead": "ccr_ead"}))
    df = df.merge(ccr, on="obligor_id", how="left")
    df["ccr_ead"] = df["ccr_ead"].fillna(0.0)
    df["total"] = df["ead"] + df["undrawn"] + df["ccr_ead"]
    return df.sort_values("total", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------- B2201

def _b2201(ctx):
    """은행계정 자금조달 및 운용(기중평잔) — 기말잔액이 앵커, 평잔계수가 파생이다."""
    df = average_balance(ctx)
    k = float(df.loc[df["section"] != "자산", "scale"].iloc[0])
    L = [FormLine("100", "평잔 산정기준", 0, "text", None,
                  text_value=f"일별 잔액 시계열 미보유 — 기말잔액 × 계정별 평잔계수. "
                             f"조달측은 운용측 평잔 총계에 맞춰 {k:.6f}배 비례 조정한다.",
                  citation=_C99, source_module=_M_DER)]
    use_codes, fund_codes, dep_codes = [], [], []
    use_i, fund_i = 0, 0
    for _, r in df.iterrows():
        if str(r["section"]) == "자산":
            use_i += 1
            code = str(1000 + use_i * 10)
            if bool(r["in_total"]):
                use_codes.append(code)
        else:
            fund_i += 1
            code = str(2000 + fund_i * 10)
            if bool(r["in_total"]):
                fund_codes.append(code)
        if str(r["item"]) in RETAIL_DEPOSITS + CORP_DEPOSITS:
            dep_codes.append(code)
        L.append(FormLine(
            code, str(r["item"]), 1 if bool(r["in_total"]) else 2, "KRW",
            float(r["average"]),
            formula=(f"기말잔액 {float(r['closing']):,.0f}원 × 평잔계수 "
                     f"{float(r['average']) / float(r['closing']):.6f} · {_DERIVED}"
                     if float(r["closing"]) else _DERIVED),
            citation=_C99, source_module=_M_DER))
    use_total = float(df[(df["section"] == "자산") & df["in_total"]]["average"].sum())
    fund_total = float(df[(df["section"] != "자산") & df["in_total"]]["average"].sum())
    deposit = float(df[df["item"].isin(RETAIL_DEPOSITS + CORP_DEPOSITS)]["average"].sum())
    L += [
        FormLine("1000", "자금운용 평잔 계", 0, "KRW", use_total,
                 formula="자산 계정 평잔 합 (대출채권은 순액 기준)",
                 citation=_C99, source_module=_M_DER, is_subtotal=True),
        FormLine("2000", "자금조달 평잔 계", 0, "KRW", fund_total,
                 formula="부채·자본 계정 평잔 합", citation=_C99,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("3000", "조달 − 운용 차액", 0, "KRW", fund_total - use_total,
                 formula="0이어야 한다 — 조달과 운용은 같은 자금의 양면이다",
                 citation=_C99, source_module=_M_DER),
        FormLine("3100", "예수금 평잔", 0, "KRW", deposit,
                 formula="개인·법인 예수금 4개 계정 평잔 합", citation=_C99,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("3200", "조달 대비 예수금 비중", 0, "ratio",
                 deposit / fund_total if fund_total else 0.0,
                 formula="예수금 평잔 ÷ 자금조달 평잔 계", source_module=_M_DER),
        _remark("일별·월별 잔액 시계열이 원천 데이터에 없어 기중평잔을 기말잔액에서 "
                "파생했다. 계정별 평잔계수는 기준일 고정 시드 파생값이고 기말잔액은 "
                "산출값이다. 조달측 평잔은 계정별로 뽑은 뒤 운용측 총계에 맞춰 한 "
                "배수로 조정했으므로 계정 간 구성비는 뽑은 값 그대로 남는다.", _C99),
    ]
    t = tol(use_total)
    checks = [
        _sum_check("자금운용 평잔 계 = 자산 계정 평잔 합", L, "1000",
                   tuple(use_codes), t),
        _sum_check("자금조달 평잔 계 = 부채·자본 계정 평잔 합", L, "2000",
                   tuple(fund_codes), t),
        FormCheck("자금조달 평잔 계 = 자금운용 평잔 계", use_total, fund_total, t),
        FormCheck("조달 − 운용 차액 = 0", 0.0, _val(L, "3000"), t),
        # 순액을 따로 뽑지 않았다는 것을 서식이 스스로 확인한다.
        FormCheck("대출채권 순액 평잔 = 총액 + 대손충당금(차감)",
                  float(df.loc[df["item"] == "대출채권 (총액)", "average"].iloc[0]
                        + df.loc[df["item"] == "대손충당금 (차감)", "average"].iloc[0]),
                  float(df.loc[df["item"] == "대출채권 (순액)", "average"].iloc[0]), t),
        # 예수금 평잔도 소계다 — 계정 라인과 대사하지 않으면 4개 계정이 바뀌어도
        # 소계가 따라가는지 아무도 확인하지 못한다.
        _sum_check("예수금 평잔 = 개인·법인 예수금 4개 계정 평잔 합", L, "3100",
                   tuple(dep_codes), t),
        _ratio_check("예수금 비중 = 예수금 평잔 ÷ 조달 평잔 계", L, "3200",
                     "3100", "2000", 1e-9),
    ]
    return L, checks


# ---------------------------------------------------------------- B2203

_TRUST_USE = ("현금 및 예치금", "유가증권", "대출금", "부동산", "기타 신탁자산")
_TRUST_FUND = ("금전신탁 수탁고", "재산신탁 수탁고", "신탁계정 차입금", "기타 신탁부채")


def _b2203(ctx):
    """신탁계정 자금조달 및 운용(기중평잔) — 신탁업 미영위. 0과 사유를 함께 적는다."""
    L: list[FormLine] = []
    checks: list[FormCheck] = []
    for base, title, items in ((1000, "신탁 자금운용 평잔 계", _TRUST_USE),
                               (2000, "신탁 자금조달 평잔 계", _TRUST_FUND)):
        codes = []
        L.append(FormLine(str(base), title, 0, "KRW", 0.0,
                          formula=_TRUST_REASON, citation=_C_TRUST,
                          source_module=_M_NONE, is_subtotal=True))
        for i, item in enumerate(items, start=1):
            code = str(base + i * 10)
            codes.append(code)
            L.append(FormLine(code, item, 1, "KRW", 0.0, formula=_TRUST_REASON,
                              citation=_C_TRUST, source_module=_M_NONE))
        checks.append(_sum_check(f"{title} = 세부항목 합", L, str(base),
                                 tuple(codes), 1e-9))
    L.append(_remark(
        "이 저장소의 원천 데이터(rdm_* · pru_*)에 신탁 계정과목이 존재하지 않는다. "
        "신탁업 미영위로 보아 전 계정을 0으로 적었으며, 0은 '미조회'가 아니라 "
        "'해당 계정 없음'이다. B2104·B2105(신탁계정 대차대조표)와 같은 판단이므로 "
        "세 서식의 합계는 모두 0으로 일치한다. 평잔 기준이지만 잔액 자체가 없어 "
        "평잔 파생을 적용하지 않았다.", _C_TRUST))
    checks.append(FormCheck("신탁 자금조달 평잔 계 = 신탁 자금운용 평잔 계",
                            _val(L, "1000"), _val(L, "2000"), 1e-9))
    return L, checks


# ---------------------------------------------------------------- B2204

def _b2204(ctx):
    """금융채권현황 — 기말 잔액과 보완자본 인정 후순위채가 앵커다."""
    d = _debenture_facts(ctx)
    L = [FormLine("1000", "금융채권 잔액 (기말)", 0, "KRW", d["closing"],
                  formula="재무상태표 사채 및 장기차입금",
                  citation=_C33, source_module=_M_PRU, is_subtotal=True)]
    kind_codes = []
    for i, (kind, amt) in enumerate(d["kinds"].items(), start=1):
        code = str(1000 + i * 10)
        kind_codes.append(code)
        sub = kind == "후순위 은행채"
        L.append(FormLine(code, f"종류 · {kind}", 1, "KRW", float(amt),
                          formula=("보완자본 인정 후순위채 산출액" if sub
                                   else _DERIVED),
                          citation="CRE40.42" if sub else "은행법 제33조",
                          source_module=_M_CAP if sub else _M_DEB))
    L.append(FormLine("2000", "잔존만기별 잔액 계", 0, "KRW",
                      float(sum(d["buckets"].values())),
                      formula="잔존만기 구간 합 — 기말 잔액과 같아야 한다",
                      citation="Basel III NSF20 만기구간", source_module=_M_DEB,
                      is_subtotal=True))
    band_codes = []
    for i, band in enumerate(DEBENTURE_BANDS, start=1):
        code = str(2000 + i * 10)
        band_codes.append(code)
        L.append(FormLine(code, f"잔존만기 · {band}", 1, "KRW",
                          float(d["buckets"][band]), formula=_DERIVED,
                          citation="은행업감독규정 제99조 · NSF20 만기구간",
                          source_module=_M_DEB))
    L += [
        FormLine("3000", "가중평균 잔존만기", 0, "count", d["wam"],
                 formula="Σ(구간 중값 × 잔액) ÷ 잔액 합계 (단위: 년)",
                 source_module=_M_DEB),
        FormLine("3100", "1년 이하 비중", 0, "ratio",
                 float(d["buckets"]["1년 이하"]) / d["closing"],
                 formula="1년 이하 잔액 ÷ 기말 잔액",
                 citation="NSF20 — 1년 이내 조달은 안정자금 인정률이 떨어진다",
                 source_module=_M_DEB),
        _remark("금융채권 종류·잔존만기 배분은 기준일 고정 시드 파생값이고, 기말 "
                "잔액(재무상태표 사채 및 장기차입금)과 후순위 은행채(보완자본 인정액)는 "
                "산출값이다. B3116·B3117과 같은 앵커로 같은 파생 함수를 호출하므로 "
                "두 서식의 금액은 갈릴 수 없다.", _C33),
    ]
    checks = [
        _sum_check("기말 잔액 = 종류별 잔액 합", L, "1000", tuple(kind_codes), 1.0),
        _sum_check("잔존만기별 잔액 계 = 구간별 합", L, "2000",
                   tuple(band_codes), 1.0),
        FormCheck("잔존만기별 잔액 계 = 기말 잔액", d["closing"],
                  _val(L, "2000"), 1.0),
        FormCheck("가중평균 잔존만기 = Σ(구간 중값 × 잔액) ÷ 기말 잔액",
                  sum(DEBENTURE_BAND_MID[i] * _val(L, c)
                      for i, c in enumerate(band_codes)) / d["closing"],
                  _val(L, "3000"), 1e-9),
        _ratio_check("1년 이하 비중 = 1년 이하 잔액 ÷ 기말 잔액", L, "3100",
                     "2010", "1000", 1e-9),
    ]
    return L, checks


# ---------------------------------------------------------------- B2205

def _b2205(ctx):
    """금융채권 신규발행 및 상환현황 — 상환액은 뽑지 않고 잔액식으로 역산한다."""
    d = _debenture_facts(ctx)
    L = [
        FormLine("1000", "기초 잔액", 0, "KRW", d["opening"],
                 formula=f"{_DERIVED} (전기말 원장 미보유)", citation=_C33,
                 source_module=_M_DEB, is_subtotal=True),
        FormLine("1100", "당기 중 신규발행액", 0, "KRW", d["issued"],
                 formula=_DERIVED, citation="은행법 제33조", source_module=_M_DEB),
        FormLine("1200", "당기 중 상환액", 0, "KRW", d["redeemed"],
                 formula="기초 + 발행 − 기말 (역산 — 상환 원장 미보유)",
                 citation="은행법 제33조", source_module=_M_DEB),
        FormLine("1300", "기말 잔액", 0, "KRW", d["closing"],
                 formula="재무상태표 사채 및 장기차입금", citation=_C33,
                 source_module=_M_PRU, is_subtotal=True),
        FormLine("2000", "당기 중 순증감", 0, "KRW", d["issued"] - d["redeemed"],
                 formula="신규발행액 − 상환액", source_module=_M_DEB),
        FormLine("2100", "발행 대비 상환 비율", 0, "ratio",
                 d["redeemed"] / d["issued"] if d["issued"] else 0.0,
                 formula="상환액 ÷ 신규발행액", source_module=_M_DEB),
        _remark("기말 잔액만 산출값이고 기초 잔액·신규발행액은 파생값이다. 상환액은 "
                "따로 뽑지 않고 '기초 + 발행 − 기말'로 역산하므로 잔액식이 항상 "
                "닫힌다. B3116과 같은 파생 묶음을 쓴다.", _C33),
    ]
    checks = [
        FormCheck("기말 잔액 = 기초 + 발행 − 상환",
                  _val(L, "1000") + _val(L, "1100") - _val(L, "1200"),
                  _val(L, "1300"), 1.0),
        FormCheck("순증감 = 기말 − 기초", _val(L, "1300") - _val(L, "1000"),
                  _val(L, "2000"), 1.0),
        FormCheck("상환액 ≥ 0", 0.0, min(0.0, _val(L, "1200")), 1.0),
        _ratio_check("발행 대비 상환 비율 = 상환 ÷ 발행", L, "2100",
                     "1200", "1100", 1e-9),
    ]
    return L, checks


# ---------------------------------------------------------------- B2206

def _b2206(ctx):
    """금융채권 신규발행 명세 — 월별 발행액. 합계는 B2205 발행액과 같아야 한다."""
    d = _debenture_facts(ctx)
    monthly = d["monthly"]
    end = pd.Period(str(ctx.result.meta.get("asof", "1970-01-01")), freq="M")
    L = [FormLine("1000", "보고기간 신규발행 총액", 0, "KRW", float(monthly.sum()),
                  formula=f"{len(monthly)}개월 합계 · {_DERIVED}", citation=_C33,
                  source_module=_M_DEB, is_subtotal=True)]
    codes = []
    for i, amt in enumerate(monthly, start=1):
        code = str(1000 + i * 10)
        codes.append(code)
        L.append(FormLine(code, f"발행월 · {end - (len(monthly) - i)}", 1, "KRW",
                          float(amt), formula=_DERIVED,
                          citation="은행법 제33조", source_module=_M_DEB))
    L += [
        FormLine("2000", "발행 개월 수", 0, "count", float(len(monthly)),
                 formula="명세 행 수", source_module=_M_DEB),
        FormLine("2100", "월평균 발행액", 0, "KRW",
                 float(monthly.sum()) / len(monthly),
                 formula="신규발행 총액 ÷ 발행 개월 수", source_module=_M_DEB),
        FormLine("2200", "최대 월 발행액", 0, "KRW", float(monthly.max()),
                 formula="월별 발행액 최대치", source_module=_M_DEB),
        _remark("발행 건별 원장(발행일·표면금리·만기)이 없어 명세를 월 단위로 낸다. "
                "월별 배분은 파생값이고 총액은 B2205의 당기 중 신규발행액과 같다 — "
                "B3118과 같은 파생 묶음을 쓴다.", _C33),
    ]
    checks = [
        _sum_check("신규발행 총액 = 월별 발행액 합", L, "1000", tuple(codes), 1.0),
        FormCheck("신규발행 총액 = B2205 당기 중 신규발행액", d["issued"],
                  _val(L, "1000"), 1.0),
        _ratio_check("월평균 = 총액 ÷ 개월 수", L, "2100", "1000", "2000", 1e-6),
        FormCheck("최대 월 발행액 ≤ 총액", 0.0,
                  max(0.0, _val(L, "2200") - _val(L, "1000")), 1.0),
    ]
    return L, checks


# ---------------------------------------------------------------- B2207

def _b2207(ctx):
    """공공금고 예수금 취급현황 — 법인 예수금 총액만 실측이고 금고 배분이 파생이다."""
    df = public_deposits(ctx)
    corp = float(df["corp_deposit_total"].iloc[0])
    total = float(df["balance"].sum())
    br = domestic_branches(ctx)
    L = [
        FormLine("100", "법인 예수금 총액", 0, "KRW", corp,
                 formula="재무상태표 법인 결제성 + 법인 비결제성 예수금",
                 citation=_C99, source_module=_M_PRU),
        FormLine("1000", "공공금고 예수금 계", 0, "KRW", total,
                 formula=f"법인 예수금 × 파생비중 {float(df['share'].iloc[0]):.4f} · "
                         f"{_DERIVED}",
                 citation=_C_FUND, source_module=_M_DER, is_subtotal=True),
    ]
    bal_codes, acc_codes = [], []
    for i, (_, r) in enumerate(df.iterrows(), start=1):
        bc, ac = str(1000 + i * 10), str(2000 + i * 10)
        bal_codes.append(bc)
        acc_codes.append(ac)
        L.append(FormLine(bc, f"금고 · {r['kind']}", 1, "KRW",
                          float(r["balance"]), formula=_DERIVED,
                          citation=_C_FUND, source_module=_M_DER))
        L.append(FormLine(ac, f"금고 · {r['kind']} — 취급 계좌 수", 2, "count",
                          float(r["n_account"]), formula=_DERIVED,
                          citation=_C_FUND, source_module=_M_DER))
    L += [
        FormLine("2000", "취급 계좌 수 계", 0, "count",
                 float(df["n_account"].sum()), formula=_DERIVED,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("3000", "취급 점포 수", 0, "count", br["total"],
                 formula="국내 점포 전체가 공공금고 수납을 취급한다고 본다 · "
                         f"{_DERIVED}",
                 citation=_C_FUND, source_module=_M_DER),
        FormLine("3100", "법인 예수금 대비 공공금고 비중", 0, "ratio",
                 total / corp if corp else 0.0,
                 formula="공공금고 예수금 계 ÷ 법인 예수금 총액",
                 source_module=_M_DER),
        _remark("금고 지정 원장(지정 기관·계약기간·약정이율)이 원천 데이터에 없다. "
                "법인 예수금 총액(산출값)에 파생 비중을 곱하고 금고 유형별로 갈랐다. "
                "금고 유형 어휘는 국고금 관리법·지방회계법의 금고 구분을 따른 편제이며 "
                "실제 지정 현황이 아니다.", _C_FUND),
    ]
    checks = [
        _sum_check("공공금고 예수금 계 = 금고유형별 합", L, "1000",
                   tuple(bal_codes), 1.0),
        _sum_check("취급 계좌 수 계 = 금고유형별 계좌 수 합", L, "2000",
                   tuple(acc_codes), 1e-9),
        _ratio_check("공공금고 비중 = 공공금고 ÷ 법인 예수금", L, "3100",
                     "1000", "100", 1e-9),
        FormCheck("공공금고 예수금 ≤ 법인 예수금 총액", 0.0,
                  max(0.0, total - corp), 1.0),
    ]
    return L, checks


# ---------------------------------------------------------------- B2208

def _b2208(ctx):
    """원화대출약정 및 신용카드 미사용한도 — 약정은 rdm_exposure, 카드는 utilization."""
    ex = ctx.tables["rdm_exposure"]
    com = ex[ex["ccf_type"].notna()]
    drawn = float(com["drawn"].sum())
    undrawn = float(com["undrawn"].sum())
    p = ctx.portfolio
    card = p[p["asset_class"] == "retail_other"]
    card_used = float(card["balance"].sum())
    # 한도 = 실행액 ÷ 한도소진율. utilization은 실측 열이므로 파생이 아니다.
    card_limit = float((card["balance"] / card["utilization"]).sum())
    dom = p.loc[p["country"] == HOME_COUNTRY, "exposure_id"]
    dom_undrawn = float(com.loc[com["exposure_id"].isin(dom), "undrawn"].sum())
    L = [
        FormLine("1000", "대출약정 한도 계", 0, "KRW", drawn + undrawn,
                 formula="실행액 + 미사용한도",
                 citation="은행업감독규정 제99조 · CRE20.94 부외항목 신용환산",
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("1100", "실행액 (기표액)", 1, "KRW", drawn,
                 formula="rdm_exposure.drawn 실측 합", citation=_C99,
                 source_module=_M_RDM),
        FormLine("1200", "미사용한도 계", 1, "KRW", undrawn,
                 formula="rdm_exposure.undrawn 실측 합", citation=_C99,
                 source_module=_M_RDM, is_subtotal=True),
    ]
    ccf_codes = []
    for i, (kind, sub) in enumerate(com.groupby("ccf_type"), start=1):
        code = str(1200 + i)
        ccf_codes.append(code)
        L.append(FormLine(code, f"신용환산유형 · {kind}", 2, "KRW",
                          float(sub["undrawn"].sum()),
                          formula=f"{len(sub):,}건", citation="CRE20.94",
                          source_module=_M_RDM))
    L += [
        FormLine("2000", "신용카드 총한도", 0, "KRW", card_limit,
                 formula="Σ(잔액 ÷ 한도소진율) — 소진율은 포트폴리오 실측 열",
                 citation=_C99, source_module=_M_PTF, is_subtotal=True),
        FormLine("2100", "신용카드 사용액", 1, "KRW", card_used,
                 formula=f"기타소매 익스포저 잔액 실측 합 · {len(card):,}좌",
                 citation=_C99, source_module=_M_PTF),
        FormLine("2200", "신용카드 미사용한도", 1, "KRW", card_limit - card_used,
                 formula="총한도 − 사용액", citation=_C99, source_module=_M_PTF),
        FormLine("2300", "신용카드 한도소진율", 1, "ratio",
                 card_used / card_limit if card_limit else 0.0,
                 formula="사용액 ÷ 총한도", source_module=_M_PTF),
        FormLine("3000", "원화(국내) 미사용한도", 0, "KRW", dom_undrawn,
                 formula=f"country={HOME_COUNTRY} 익스포저의 미사용한도 실측 합 — "
                         f"원장에 통화 열이 없어 소재국을 원화 프록시로 쓴다",
                 citation=_C99, source_module=_M_RDM),
        FormLine("3100", "미사용한도 중 원화 비중", 0, "ratio",
                 dom_undrawn / undrawn if undrawn else 0.0,
                 formula="원화(국내) 미사용한도 ÷ 미사용한도 계",
                 source_module=_M_RDM),
        _remark("약정·미사용한도는 전부 산출값이다. 다만 원장에 익스포저 통화 열이 "
                "없어 '원화'는 소재국(country=KR)을 프록시로 썼다 — 통화 열이 "
                "확보되면 여기부터 고친다. 신용카드는 별도 카드 원장이 없어 기타소매 "
                "익스포저의 한도소진율(실측 열)로 한도를 역산한다.", _C99),
    ]
    checks = [
        _sum_check("대출약정 한도 계 = 실행액 + 미사용한도", L, "1000",
                   ("1100", "1200"), 1.0),
        _sum_check("미사용한도 계 = 신용환산유형별 합", L, "1200",
                   tuple(ccf_codes), 1.0),
        _sum_check("신용카드 총한도 = 사용액 + 미사용한도", L, "2000",
                   ("2100", "2200"), tol(card_limit)),
        _ratio_check("카드 한도소진율 = 사용액 ÷ 총한도", L, "2300",
                     "2100", "2000", 1e-9),
        _ratio_check("원화 비중 = 원화 미사용한도 ÷ 미사용한도 계", L, "3100",
                     "3000", "1200", 1e-9),
        FormCheck("원화 미사용한도 ≤ 미사용한도 계", 0.0,
                  max(0.0, dom_undrawn - undrawn), 1.0),
    ]
    return L, checks


# ---------------------------------------------------------------- B2209

def _b2209(ctx):
    """차주별 무수익여신 산정대상 여신 현황 — rdm_asset_quality·rdm_delinquency 집계."""
    npl = _npl_book(ctx)
    aq = ctx.tables["rdm_asset_quality"]
    total_loan = float(aq["balance"].sum())
    cls_only = float(npl.loc[npl["npl_class"], "balance"].sum())
    dpd_only = float(npl.loc[~npl["npl_class"] & npl["npl_dpd"], "balance"].sum())
    total = float(npl["balance"].sum())
    obl = (npl.groupby("obligor_id", as_index=False)
           .agg(balance=("balance", "sum"), n=("exposure_id", "count"))
           .sort_values("balance", ascending=False).reset_index(drop=True))
    L = [
        FormLine("1000", "무수익여신 산정대상 잔액 계", 0, "KRW", total,
                 formula="고정이하 분류 또는 3개월 이상 연체 여신",
                 citation=f"{_C27} · 동 시행세칙 무수익여신 산정기준",
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("1010", "고정이하 분류 여신", 1, "KRW", cls_only,
                 formula="classification ∈ (고정, 회수의문, 추정손실)",
                 citation=_C27, source_module=_M_RDM),
        FormLine("1020", f"{NPL_DPD}일 이상 연체 (고정이하 외)", 1, "KRW", dpd_only,
                 formula=f"dpd ≥ {NPL_DPD} 이면서 고정이하로 분류되지 않은 여신",
                 citation=_C27, source_module=_M_RDM),
        FormLine("1100", "산정대상 차주 수", 0, "count", float(len(obl)),
                 formula="무수익여신 보유 차주 수", source_module=_M_RDM,
                 is_subtotal=True),
        FormLine("1110", "산정대상 여신 건수", 0, "count", float(len(npl)),
                 source_module=_M_RDM),
        FormLine("1200", "총여신 잔액", 0, "KRW", total_loan,
                 formula="rdm_asset_quality 잔액 실측 합", citation=_C27,
                 source_module=_M_RDM),
        FormLine("1300", "무수익여신비율", 0, "ratio",
                 total / total_loan if total_loan else 0.0,
                 formula="무수익여신 ÷ 총여신", citation=_C27,
                 source_module=_M_RDM),
    ]
    bt_codes = []
    for i, (bt, sub) in enumerate(npl.groupby("borrower_type"), start=1):
        code = str(2000 + i * 10)
        bt_codes.append(code)
        L.append(FormLine(code, f"차주유형 · {bt}", 1, "KRW",
                          float(sub["balance"].sum()),
                          formula=f"{sub['obligor_id'].nunique():,}차주 · "
                                  f"{len(sub):,}건",
                          citation=_C27, source_module=_M_RDM))
    cls_codes = []
    for i, (cls, sub) in enumerate(
            npl[npl["npl_class"]].groupby("classification"), start=1):
        code = str(3000 + i * 10)
        cls_codes.append(code)
        L.append(FormLine(code, f"건전성분류 · {cls}", 1, "KRW",
                          float(sub["balance"].sum()),
                          formula=f"{len(sub):,}건", citation=_C27,
                          source_module=_M_RDM))
    for i, (_, r) in enumerate(obl.head(10).iterrows(), start=1):
        L.append(FormLine(str(4000 + i * 10), f"상위 차주 · {r['obligor_id']}", 1,
                          "KRW", float(r["balance"]),
                          formula=f"{int(r['n'])}건 · 무수익여신 계 대비 "
                                  f"{float(r['balance']) / total:.2%}",
                          citation=_C27, source_module=_M_RDM))
    L.append(_remark(
        "무수익여신 산정대상은 전부 산출값이다(건전성분류·연체일수 원장). 차주 단위 "
        "합산은 rdm_exposure.obligor_id 기준이며, 상위 차주는 잔액 순 10개만 낸다 "
        "— 전 차주 명세는 B2210(대출금액대별)이 금액 구간으로 대신한다.", _C27))
    checks = [
        _sum_check("무수익여신 계 = 고정이하 + 연체(고정이하 외)", L, "1000",
                   ("1010", "1020"), 1.0),
        _sum_check("무수익여신 계 = 차주유형별 합", L, "1000",
                   tuple(bt_codes), 1.0),
        _sum_check("고정이하 분류 여신 = 분류별 합", L, "1010",
                   tuple(cls_codes), 1.0),
        _ratio_check("무수익여신비율 = 무수익여신 ÷ 총여신", L, "1300",
                     "1000", "1200", 1e-9),
        FormCheck("무수익여신 ≤ 총여신", 0.0, max(0.0, total - total_loan), 1.0),
    ]
    return L, checks


# ---------------------------------------------------------------- B2210

def _b2210(ctx):
    """대출금액대별 대출현황 — 차주 단위 합산잔액으로 금액구간을 가른다."""
    aq = ctx.tables["rdm_asset_quality"][["exposure_id", "balance"]]
    df = (aq.merge(ctx.tables["rdm_exposure"][["exposure_id", "obligor_id"]],
                   on="exposure_id")
          .groupby("obligor_id", as_index=False)
          .agg(balance=("balance", "sum"), n=("exposure_id", "count")))
    df["band"] = [band_of(v, LOAN_SIZE_BANDS) for v in df["balance"]]
    total = float(df["balance"].sum())
    L = [
        FormLine("1000", "대출 잔액 계", 0, "KRW", total,
                 formula="차주 단위 합산잔액의 합", citation=_C99,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("1100", "차주 수 계", 0, "count", float(len(df)),
                 citation=_C99, source_module=_M_RDM, is_subtotal=True),
        FormLine("1200", "1차주당 평균 잔액", 0, "KRW",
                 total / len(df) if len(df) else 0.0,
                 formula="대출 잔액 계 ÷ 차주 수 계", source_module=_M_RDM),
    ]
    bal_codes, cnt_codes = [], []
    for i, (_, label) in enumerate(LOAN_SIZE_BANDS, start=1):
        sub = df[df["band"] == label]
        bc, cc = str(2000 + i * 10), str(3000 + i * 10)
        bal_codes.append(bc)
        cnt_codes.append(cc)
        L.append(FormLine(bc, f"금액대 · {label} — 잔액", 1, "KRW",
                          float(sub["balance"].sum()),
                          formula=f"차주 {len(sub):,}인 · 여신 {int(sub['n'].sum()):,}건",
                          citation=_C99, source_module=_M_RDM))
        L.append(FormLine(cc, f"금액대 · {label} — 차주 수", 2, "count",
                          float(len(sub)), citation=_C99, source_module=_M_RDM))
    L.append(_remark(
        "금액구간은 감독규정이 정한 구간이 아니라 FINES 대출금액대별 서식의 편제 "
        "구간이며, 차주 단위 합산잔액 기준이다. 잔액·차주 수 모두 산출값이고 파생이 "
        "없다.", _C99))
    checks = [
        _sum_check("대출 잔액 계 = 금액대별 잔액 합", L, "1000",
                   tuple(bal_codes), 1.0),
        _sum_check("차주 수 계 = 금액대별 차주 수 합", L, "1100",
                   tuple(cnt_codes), 1e-9),
        _ratio_check("1차주당 평균 = 잔액 계 ÷ 차주 수 계", L, "1200",
                     "1000", "1100", 1e-6),
    ]
    return L, checks


# ---------------------------------------------------------------- B2211

def _b2211(ctx):
    """대주주와의 금융거래현황 — BR-27(B3115)·B3000과 **같은 테이블**에 앵커한다.

    대주주 지정 원장이 없어 신용공여 사용액은 0이다. 임의로 대주주를 지정하면
    실재하지 않는 한도 초과가 보고된다 — 0은 "없다"가 아니라 "확인해야 한다"이다.
    """
    own = float(ctx.result.meta["capital"].total)
    t = ctx.tables["pru_ownership_limit"]
    L = [FormLine("1000", "자기자본", 0, "KRW", own,
                  formula="보통주자본 + 기타기본자본 + 보완자본",
                  citation="은행법 제2조 제1항 제5호", source_module=_M_CAP)]
    checks: list[FormCheck] = []
    for i, item in enumerate(("대주주 신용공여", "대주주 발행주식 취득"), start=1):
        r = t[t["item"] == item].iloc[0]
        base = 1000 + i * 100
        L += [
            FormLine(str(base), item, 0, "KRW", float(r["used"]),
                     formula=str(r["basis"]), citation=str(r["citation"]),
                     source_module=_M_OWN, is_subtotal=True),
            FormLine(str(base + 10), "한도 금액", 1, "KRW",
                     float(r["limit_amount"]),
                     formula=f"자기자본 × {float(r['limit_pct']):.0%}",
                     citation=str(r["citation"]), source_module=_M_OWN),
            FormLine(str(base + 20), "한도 소진율", 1, "ratio",
                     float(r["utilisation"]), formula="사용액 ÷ 한도금액",
                     source_module=_M_OWN),
            FormLine(str(base + 30), "한도 내 여부", 1, "count",
                     1.0 if bool(r["passes"]) else 0.0,
                     formula="1 = 한도 내, 0 = 한도 초과", source_module=_M_OWN),
        ]
        checks += [
            FormCheck(f"{item} 한도금액 = 자기자본 × 한도율",
                      own * float(r["limit_pct"]), float(r["limit_amount"]), 1.0),
            _ratio_check(f"{item} 소진율 = 사용액 ÷ 한도금액", L, str(base + 20),
                         str(base), str(base + 10), 1e-9),
        ]
    L += [
        FormLine("3000", "대주주와의 금융거래 건수", 0, "count", 0.0,
                 formula="대주주 지정 원장 미확보 — 거래 식별 불가",
                 citation="은행법 제35조의2 제1항", source_module=_M_OWN),
        FormLine("3100", "대주주 발행 유가증권 보유액", 0, "KRW",
                 float(t.loc[t["item"] == "대주주 발행주식 취득", "used"].iloc[0]),
                 formula="기타자산 중 지분증권 배분치 — 상대방이 대주주인지는 미확인",
                 citation="은행법 제35조의3 제1항", source_module=_M_OWN),
        _remark("대주주 지정 원장이 원천 데이터에 없다. 임의로 대주주를 지정하면 "
                "실재하지 않는 한도 초과가 보고되므로 신용공여와 거래건수를 0으로 두고 "
                "미확보임을 남긴다. 값은 pru_ownership_limit에 그대로 앵커하므로 "
                "BR-27(B3115 대주주 신용공여 및 주식취득 한도)·B3000(주주 및 임원과의 "
                "거래 내역)과 어긋날 수 없다.", "은행법 제35조의2 · 제35조의3"),
    ]
    checks.append(FormCheck("대주주 발행 유가증권 보유액 = 대주주 발행주식 취득 사용액",
                            _val(L, "1200"), _val(L, "3100"), 1.0))
    return L, checks


# ---------------------------------------------------------------- B2212

def _b2212(ctx):
    """타 금융회사에 대한 자산 — asset_class=='bank' 익스포저와 CCR 산출값이다."""
    bb = _bank_book(ctx)
    ta = bs_amounts(ctx)["자산총계"]
    ead = float(bb["ead"].sum())
    undrawn = float(bb["undrawn"].sum())
    ccr = float(bb["ccr_ead"].sum())
    total = ead + undrawn + ccr
    mkt = ctx.tables["mkt_trade"]
    L = [
        FormLine("100", "자산총계", 0, "KRW", ta,
                 formula="재무상태표 자산총계", citation=_C99,
                 source_module=_M_PRU),
        FormLine("1000", "타 금융회사에 대한 자산 계", 0, "KRW", total,
                 formula="여신 + 미사용약정 + 파생상품 익스포저",
                 citation=f"{_C_SCO_INTER} — 금융시스템 내 자산 · {_C99}",
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("1100", "여신 (대출·예치)", 1, "KRW", ead,
                 formula="asset_class=bank 익스포저 EAD 실측 합",
                 citation=_C_SCO_INTER, source_module=_M_PTF),
        FormLine("1200", "미사용약정", 1, "KRW", undrawn,
                 formula="asset_class=bank 익스포저 undrawn 실측 합",
                 citation=_C_SCO_INTER, source_module=_M_RDM),
        FormLine("1300", "파생상품 익스포저 (SA-CCR EAD)", 1, "KRW", ccr,
                 formula="거래상대방별 SA-CCR EAD 합",
                 citation="CRE52 SA-CCR", source_module=_M_CCR),
        FormLine("2000", "거래 금융회사 수", 0, "count", float(len(bb)),
                 formula="은행 차주 수", source_module=_M_PTF, is_subtotal=True),
        FormLine("2100", "파생 거래상대방 수", 1, "count",
                 float(int((bb["ccr_ead"] > 0).sum())),
                 citation="CRE52", source_module=_M_CCR),
        FormLine("3000", "파생상품 명목금액 (참고)", 0, "KRW",
                 float(mkt["notional"].sum()),
                 formula=f"장외파생 {len(mkt):,}건 명목금액 합 — 익스포저가 아니라 "
                         f"규모 참고치다",
                 citation=_C_SCO_CPLX, source_module="risk_lib.market_data"),
        FormLine("4000", "자산총계 대비 비중", 0, "ratio",
                 total / ta if ta else 0.0,
                 formula="타 금융회사 자산 계 ÷ 자산총계", source_module=_M_RDM),
        _remark("전부 산출값이다. 여신·미사용약정은 asset_class=bank 익스포저 실측이고 "
                "파생 익스포저는 SA-CCR 산출값이다. 명목금액은 익스포저가 아니므로 "
                "합계(1000)에 넣지 않고 참고로만 낸다 — 넣으면 상호연계성 지표가 "
                "명목금액만큼 부풀려진다.", _C_SCO_INTER),
    ]
    checks = [
        _sum_check("타 금융회사 자산 계 = 여신 + 미사용약정 + 파생", L, "1000",
                   ("1100", "1200", "1300"), 1.0),
        _ratio_check("자산총계 대비 비중", L, "4000", "1000", "100", 1e-9),
        FormCheck("파생 거래상대방 수 ≤ 거래 금융회사 수", 0.0,
                  max(0.0, _val(L, "2100") - _val(L, "2000")), 1e-9),
    ]
    return L, checks


def _b2212_1(ctx):
    """타 금융회사에 대한 자산(세부내역) — 상대방별 명세. 합계는 B2212와 같다."""
    bb = _bank_book(ctx)
    total = float(bb["total"].sum())
    L = [FormLine("1000", "타 금융회사에 대한 자산 계", 0, "KRW", total,
                  formula="상대방별 명세 합 — B2212 합계와 같아야 한다",
                  citation=f"{_C_SCO_INTER} · {_C99}",
                  source_module=_M_RDM, is_subtotal=True)]
    codes = []
    for i, (_, r) in enumerate(bb.iterrows(), start=1):
        code = str(1000 + i * 10)
        codes.append(code)
        L.append(FormLine(code, f"금융회사 · {r['obligor_id']}", 1, "KRW",
                          float(r["total"]),
                          formula=(f"여신 {float(r['ead']):,.0f} + 미사용약정 "
                                   f"{float(r['undrawn']):,.0f} + 파생 EAD "
                                   f"{float(r['ccr_ead']):,.0f} · 여신 "
                                   f"{int(r['n'])}건"),
                          citation=_C_SCO_INTER, source_module=_M_RDM))
    L += [
        FormLine("2000", "명세 건수", 0, "count", float(len(bb)),
                 source_module=_M_RDM),
        FormLine("2100", "최대 상대방 익스포저", 0, "KRW",
                 float(bb["total"].max()),
                 formula=f"{bb['obligor_id'].iloc[0]} · 계 대비 "
                         f"{float(bb['total'].max()) / total:.2%}",
                 source_module=_M_RDM),
        _remark("거래상대방은 실재하는 은행 차주(obligor_id)이며 금액은 전부 산출값이다. "
                "상대방 명칭 마스터가 없어 차주 식별자를 그대로 적는다 — 실제 제출 시 "
                "금융회사 명칭·기관코드로 대체된다.", _C_SCO_INTER),
    ]
    checks = [
        _sum_check("자산 계 = 상대방별 명세 합", L, "1000", tuple(codes), 1.0),
        # 세부내역 합계는 B2212의 합계와 같아야 한다. 같은 식을 양변에 넣으면
        # 대사가 아니라 항등식이 되므로 **B2212를 실제로 만들어** 그 라인과 맞댄다.
        FormCheck("자산 계 = B2212 타 금융회사에 대한 자산 계",
                  _val(_b2212(ctx)[0], "1000"), _val(L, "1000"), 1.0),
        FormCheck("명세 건수 = 거래 금융회사 수", float(len(bb)),
                  _val(L, "2000"), 1e-9),
        FormCheck("최대 상대방 익스포저 ≤ 자산 계", 0.0,
                  max(0.0, _val(L, "2100") - total), 1.0),
    ]
    return L, checks


# ---------------------------------------------------------------- B2213

_FI_BORROWING = ("차입금 — 금융기관 6개월 이내", "차입금 — 금융기관 6~12개월")


def _b2213(ctx):
    """타 금융회사에 대한 부채 — 재무상태표 차입금·사채 계정이다."""
    amt = bs_amounts(ctx)
    items = _FI_BORROWING + ("사채 및 장기차입금",)
    total = sum(amt[i] for i in items)
    liab = amt["부채총계"]
    L = [
        FormLine("100", "부채총계", 0, "KRW", liab,
                 formula="재무상태표 부채총계", citation=_C99,
                 source_module=_M_PRU),
        FormLine("1000", "타 금융회사에 대한 부채 계", 0, "KRW", total,
                 formula="금융기관 차입금 + 사채 및 장기차입금",
                 citation=f"{_C_SCO_INTER} — 금융시스템 내 부채 · {_C99}",
                 source_module=_M_PRU, is_subtotal=True),
    ]
    codes = []
    for i, item in enumerate(items, start=1):
        code = str(1000 + i * 10)
        codes.append(code)
        L.append(FormLine(code, item, 1, "KRW", amt[item],
                          formula="재무상태표 계정 잔액", citation=_C99,
                          source_module=_M_PRU))
    L += [
        FormLine("2000", "상대방 특정 가능 차입금", 0, "KRW",
                 sum(amt[i] for i in _FI_BORROWING),
                 formula="금융기관 차입금 2개 계정 — 세부내역은 B2213-1",
                 citation=_C99, source_module=_M_PRU, is_subtotal=True),
        FormLine("2100", "상대방 미특정 (사채)", 0, "KRW",
                 amt["사채 및 장기차입금"],
                 formula="불특정 다수 투자자 보유 — 상대방별 배분 대상이 아니다",
                 citation="은행법 제33조", source_module=_M_PRU),
        FormLine("3000", "부채총계 대비 비중", 0, "ratio",
                 total / liab if liab else 0.0,
                 formula="타 금융회사 부채 계 ÷ 부채총계", source_module=_M_PRU),
        _remark("전부 산출값이다. 사채는 불특정 다수 투자자가 보유하므로 상대방별 "
                "명세(B2213-1) 대상에서 빼고 별도 라인으로 남긴다 — 배분하면 실재하지 "
                "않는 채권자가 서식에 실린다.", _C_SCO_INTER),
    ]
    checks = [
        _sum_check("부채 계 = 계정별 합", L, "1000", tuple(codes), 1.0),
        _sum_check("부채 계 = 특정가능 차입금 + 사채", L, "1000",
                   ("2000", "2100"), 1.0),
        _ratio_check("부채총계 대비 비중", L, "3000", "1000", "100", 1e-9),
    ]
    return L, checks


def _b2213_1(ctx):
    """타 금융회사에 대한 부채(세부내역) — 상대방은 실재 은행, 배분만 파생이다."""
    amt = bs_amounts(ctx)
    book = fi_liability_book(ctx)
    borrow = sum(amt[i] for i in _FI_BORROWING)
    bond = amt["사채 및 장기차입금"]
    L = [FormLine("1000", "상대방 특정 차입금 계", 0, "KRW", borrow,
                  formula="재무상태표 금융기관 차입금 2개 계정 — B2213의 2000과 같다",
                  citation=_C99, source_module=_M_PRU, is_subtotal=True)]
    codes = []
    for i, (_, r) in enumerate(book.iterrows(), start=1):
        code = str(1000 + i * 10)
        codes.append(code)
        L.append(FormLine(code, f"금융회사 · {r['obligor_id']}", 1, "KRW",
                          float(r["borrowing"]),
                          formula=f"차입금 총액 배분 · {_DERIVED}",
                          citation=_C99, source_module=_M_DER))
    L += [
        FormLine("2000", "상대방 미특정 (사채)", 0, "KRW", bond,
                 formula="불특정 다수 투자자 보유 — 배분하지 않는다",
                 citation="은행법 제33조", source_module=_M_PRU),
        FormLine("3000", "타 금융회사에 대한 부채 계", 0, "KRW", borrow + bond,
                 formula="특정 차입금 계 + 사채 — B2213의 1000과 같아야 한다",
                 citation=_C_SCO_INTER, source_module=_M_PRU, is_subtotal=True),
        FormLine("4000", "명세 건수", 0, "count", float(len(book)),
                 source_module=_M_DER),
        _remark("차입 상대방 원장이 원천 데이터에 없다. 상대방은 실재하는 은행 "
                "거래상대방(상위 익스포저 순)이고 개별 차입금액만 기준일 고정 시드 "
                "파생값이며, 합계는 재무상태표 차입금 그 자체다. 실재하지 않는 "
                "금융회사를 지어내지 않았다.", _C99),
    ]
    checks = [
        _sum_check("특정 차입금 계 = 상대방별 명세 합", L, "1000",
                   tuple(codes), 1.0),
        _sum_check("부채 계 = 특정 차입금 + 사채", L, "3000",
                   ("1000", "2000"), 1.0),
        # `borrow + bond`를 양변에 넣으면 항등식이라 아무것도 대사하지 못한다.
        # **B2213을 실제로 만들어** 그 서식의 합계·차입금 라인과 맞댄다.
        FormCheck("부채 계 = B2213 타 금융회사에 대한 부채 계",
                  _val(_b2213(ctx)[0], "1000"), _val(L, "3000"), 1.0),
        FormCheck("특정 차입금 계 = B2213 상대방 특정 가능 차입금",
                  _val(_b2213(ctx)[0], "2000"), _val(L, "1000"), 1.0),
    ]
    return L, checks


# ---------------------------------------------------------------- B2214

def _b2214(ctx):
    """증권발행규모 및 총익스포저 — 전부 산출값이다.

    **한 서식이지만 SCO40의 범주는 둘이다.** 총익스포저는 규모 지표(SCO40.5)이고
    증권발행규모(securities outstanding)는 상호연계성 지표(SCO40.6)다. 둘을 한
    범주로 인용하면 지표 근거가 틀어지므로 라인마다 다른 범주를 단다.
    """
    lev = ctx.result.leverage
    deep = ctx.result.leverage_deep.breakdown
    amt = bs_amounts(ctx)
    sec_items = ("사채 및 장기차입금", "신종자본증권 (AT1)", "자본금 및 자본잉여금")
    sec_total = sum(amt[i] for i in sec_items)
    L = [
        FormLine("1000", "총익스포저 (익스포저 측정치)", 0, "KRW",
                 float(lev.exposure_measure),
                 formula="온밸런스 + 파생 + SFT + 부외 환산 — BR-07과 같은 값",
                 citation=f"{_C_SCO_SIZE} · LEV30", source_module=_M_LEV,
                 is_subtotal=True),
        FormLine("1100", "참고 · 익스포저 측정치 상세 재계산", 0, "KRW",
                 float(deep.total_exposure),
                 formula="leverage_deep 구성요소 합 — 헤드라인과 산정 세부가 다르다",
                 citation="LEV30", source_module=_M_LEV, is_subtotal=True),
    ]
    comp_codes = []
    for i, c in enumerate(deep.components, start=1):
        code = str(1100 + i)
        comp_codes.append(code)
        L.append(FormLine(code, f"구성 · {c.name}", 1, "KRW", float(c.exposure),
                          formula=f"명목 {float(c.notional):,.0f} × 계수 "
                                  f"{float(c.factor):.2f}",
                          citation="LEV30", source_module=_M_LEV))
    L += [
        FormLine("1190", "상세 재계산 − 헤드라인 차이", 0, "KRW",
                 float(deep.total_exposure - lev.exposure_measure),
                 formula="두 산출 경로의 차이 — 제출값은 헤드라인(1000)이다",
                 citation="LEV30", source_module=_M_LEV),
        FormLine("2000", "증권발행규모 계", 0, "KRW", sec_total,
                 formula="발행 채무증권 + 자본증권 잔액 — 규모가 아니라 상호연계성 지표다",
                 citation=f"{_C_SCO_INTER} — 발행 증권 잔액", source_module=_M_PRU,
                 is_subtotal=True),
    ]
    sec_codes = []
    for i, item in enumerate(sec_items, start=1):
        code = str(2000 + i * 10)
        sec_codes.append(code)
        L.append(FormLine(code, f"발행 · {item}", 1, "KRW", amt[item],
                          formula="재무상태표 계정 잔액",
                          citation=_C_SCO_INTER, source_module=_M_PRU))
    L += [
        FormLine("3000", "대차대조표 자산총계 (참고)", 0, "KRW", amt["자산총계"],
                 formula="총익스포저와의 차이는 부외·파생 환산분이다",
                 citation=_C_SCO_SIZE, source_module=_M_PRU),
        FormLine("3100", "증권발행규모 ÷ 총익스포저", 0, "ratio",
                 sec_total / float(lev.exposure_measure)
                 if lev.exposure_measure else 0.0,
                 formula="증권발행규모 계 ÷ 총익스포저", source_module=_M_LEV),
        _remark("전부 산출값이며 파생이 없다. 다만 두 수치의 SCO40 범주가 다르다 — "
                "총익스포저는 규모 지표(SCO40.5), 증권발행규모는 상호연계성 지표"
                "(SCO40.6, securities outstanding)다. 지표 점수(bp)는 내지 않는다 — "
                "SCO40 점수는 표본 은행 전체의 지표 합계를 분모로 쓰는데 업권 집계가 "
                "이 저장소에 없다. 분모를 지어내면 있지도 않은 G-SIB 점수를 "
                "보고하게 된다.", _C_SCO),
    ]
    checks = [
        _sum_check("상세 재계산 = 구성요소 합", L, "1100", tuple(comp_codes),
                   tol(float(deep.total_exposure))),
        FormCheck("차이 = 상세 재계산 − 헤드라인",
                  _val(L, "1100") - _val(L, "1000"), _val(L, "1190"), 1.0),
        _sum_check("증권발행규모 계 = 발행 계정 합", L, "2000",
                   tuple(sec_codes), 1.0),
        _ratio_check("증권발행규모 ÷ 총익스포저", L, "3100", "2000", "1000", 1e-9),
    ]
    return L, checks


# ---------------------------------------------------------------- B2215

def _b2215(ctx):
    """대체가능성 — G-SIB 지표. 지급결제·보관·인수 원장이 없어 전부 파생값이다."""
    s = substitutability(ctx)
    ta = bs_amounts(ctx)["자산총계"]
    total = sum(s.values())
    L = [
        FormLine("100", "자산총계 (파생 모수)", 0, "KRW", ta,
                 formula="재무상태표 자산총계 — 파생 배수의 모수", citation=_C_SCO,
                 source_module=_M_PRU),
        FormLine("1000", "지급결제금액 (연간)", 0, "KRW", s["payments"],
                 formula=f"자산총계 × {s['payments'] / ta:.4f} · {_DERIVED}",
                 citation=f"{_C_SCO_SUBS} — 지급결제 활동", source_module=_M_DER),
        FormLine("2000", "보관자산", 0, "KRW", s["custody"],
                 formula=f"자산총계 × {s['custody'] / ta:.6f} · {_DERIVED}",
                 citation=f"{_C_SCO_SUBS} — 보관자산", source_module=_M_DER),
        FormLine("3000", "인수 주선 금액", 0, "KRW", s["underwriting"],
                 formula=f"자산총계 × {s['underwriting'] / ta:.6f} · {_DERIVED}",
                 citation=f"{_C_SCO_SUBS} — 인수업무", source_module=_M_DER),
        FormLine("4000", "세 지표 단순 합 (서식 내부 대사용 — 규정상 지표 아님)", 0,
                 "KRW", total,
                 formula="지급결제 + 보관자산 + 인수금액. SCO40은 지표를 더하지 "
                         "않는다 — 각 지표를 표본 합계로 나눠 점수화한 뒤 평균한다. "
                         "게다가 지급결제금액은 연간 흐름이고 보관자산은 잔액이라 "
                         "더한 값에는 경제적 의미가 없다. 라인 합계 대사용으로만 쓴다",
                 citation=f"{_C99} — 서식 내부 소계", source_module=_M_DER,
                 is_subtotal=True),
        FormLine("5000", "지급결제금액 ÷ 자산총계 (회전율)", 0, "multiple",
                 s["payments"] / ta if ta else 0.0,
                 formula="연간 지급결제 처리액 ÷ 자산총계", source_module=_M_DER),
        FormLine("6000", "지표 점수 (bp)", 0, "count", 0.0,
                 formula="산출하지 않는다 — 표본 은행 전체 지표 합계(분모) 미보유",
                 citation=_C_SCO_SCORE, source_module=_M_DER),
        _remark("지급결제 처리액·보관자산·인수 주선 금액 원장이 원천 데이터에 전혀 "
                "없다. 자산총계(산출값)에 기준일 고정 시드 파생 배수를 곱했으며 세 "
                "금액 모두 파생값이다. **배수 자체에 관찰·추정 근거가 없다** — "
                "지급결제 12~20배·보관 0.10~0.30·인수 0.01~0.03은 자릿수만 맞춘 "
                "가정이므로 이 세 금액을 실적 수치로 인용하면 안 된다. 지표 점수는 "
                "표본 은행 전체 합계가 있어야 산정할 수 있어 0으로 두고 사유를 "
                "남긴다 — 0은 '지표가 0'이 아니라 '산정 불가'다. 4000은 SCO40의 "
                "지표가 아니라 서식 내부 소계다.", _C_SCO),
    ]
    checks = [
        _sum_check("세 지표 단순 합 = 지급결제 + 보관 + 인수", L, "4000",
                   ("1000", "2000", "3000"), 1.0),
        # 세 지표 모두 파생값이지만 음수가 나오면 배수 범위가 잘못 걸린 것이다.
        FormCheck("세 지표 모두 ≥ 0", 0.0,
                  min(0.0, _val(L, "1000"), _val(L, "2000"), _val(L, "3000")),
                  1.0),
        _ratio_check("회전율 = 지급결제금액 ÷ 자산총계", L, "5000",
                     "1000", "100", 1e-9),
    ]
    return L, checks


# ---------------------------------------------------------------- B2216

def _b2216(ctx):
    """복잡성 — G-SIB 지표. 파생 명목금액·트레이딩 포지션은 산출값이다."""
    mkt = ctx.tables["mkt_trade"]
    notional = float(mkt["notional"].sum())
    trading = trading_position(ctx)
    l3 = level3_assets(ctx)
    L = [
        FormLine("1000", "장외파생상품 명목금액 계", 0, "KRW", notional,
                 formula=f"장외파생 {len(mkt):,}건 명목금액 실측 합",
                 citation=f"{_C_SCO_CPLX} — 장외파생상품",
                 source_module="risk_lib.market_data"),
    ]
    kind_codes = []
    for i, (kind, sub) in enumerate(mkt.groupby("kind"), start=1):
        code = str(1000 + i * 10)
        kind_codes.append(code)
        L.append(FormLine(code, f"상품유형 · {kind}", 1, "KRW",
                          float(sub["notional"].sum()),
                          formula=f"{len(sub):,}건",
                          citation=_C_SCO_CPLX,
                          source_module="risk_lib.market_data"))
    L += [
        FormLine("1100", "파생 거래상대방 수", 0, "count",
                 float(mkt["counterparty"].nunique()),
                 citation="CRE52", source_module=_M_CCR),
        FormLine("2000", "거래목적 유가증권", 0, "KRW", trading,
                 formula="시장리스크 산출 트레이딩 포지션 합 — 산출값이다",
                 citation=f"{_C_SCO_CPLX} — 거래목적·매도가능 증권",
                 source_module="risk_lib.capital.market_risk"),
        FormLine("3000", "Level 3 자산", 0, "KRW", l3,
                 formula=f"기타자산 × 파생비율 · {_DERIVED} (공정가치 서열 원장 미보유)",
                 citation=f"{_C_SCO_CPLX} — Level 3 자산", source_module=_M_DER),
        FormLine("4000", "세 지표 단순 합 (서식 내부 대사용 — 규정상 지표 아님)", 0,
                 "KRW", notional + trading + l3,
                 formula="장외파생 명목금액 + 거래목적 유가증권 + Level 3 자산. "
                         "SCO40은 지표를 더하지 않는다 — 각 지표를 표본 합계로 "
                         "나눠 점수화한다. 명목금액은 익스포저가 아니므로 재무제표 "
                         "자산과 더한 값에는 경제적 의미가 없다. 라인 합계 대사용이다",
                 citation=f"{_C99} — 서식 내부 소계", source_module=_M_DER,
                 is_subtotal=True),
        FormLine("5000", "지표 점수 (bp)", 0, "count", 0.0,
                 formula="산출하지 않는다 — 표본 은행 전체 지표 합계(분모) 미보유",
                 citation=_C_SCO_SCORE, source_module=_M_DER),
        _remark("세 지표 중 둘은 산출값이다 — 장외파생 명목금액은 mkt_trade 실측이고 "
                "거래목적 유가증권은 시장리스크 트레이딩 포지션(B2126과 같은 앵커)이다. "
                "Level 3 자산만 공정가치 서열 원장이 없어 파생했고, 그 비율"
                "(기타자산의 2~8%)에는 관찰·추정 근거가 없는 가정이다. 지표 점수는 "
                "업권 합계가 없어 산정하지 않는다. 4000은 SCO40의 지표가 아니라 "
                "서식 내부 소계다.", _C_SCO),
    ]
    checks = [
        _sum_check("장외파생 명목금액 계 = 상품유형별 합", L, "1000",
                   tuple(kind_codes), 1.0),
        _sum_check("세 지표 단순 합 = 장외파생 + 거래목적 유가증권 + Level 3", L,
                   "4000", ("1000", "2000", "3000"), 1.0),
        FormCheck("Level 3 자산 ≤ 기타자산", 0.0,
                  max(0.0, l3 - bs_amounts(ctx)["기타자산"]), 1.0),
    ]
    return L, checks


# ---------------------------------------------------------------- B2217

def _b2217(ctx):
    """국내특수요인 — D-SIB 국내 평가축. 국내 비중은 실측, 시장점유율이 파생이다."""
    p = ctx.portfolio
    amt = bs_amounts(ctx)
    w = domestic_share(ctx)
    dom_ead = float(p.loc[p["country"] == HOME_COUNTRY, "ead"].sum())
    ov_ead = float(p.loc[p["country"] != HOME_COUNTRY, "ead"].sum())
    deposit = sum(amt[i] for i in RETAIL_DEPOSITS + CORP_DEPOSITS)
    dom_deposit = deposit * w
    share = domestic_market_share(ctx)
    ta = amt["자산총계"]
    L = [
        FormLine("1000", "국내 익스포저", 0, "KRW", dom_ead,
                 formula=f"country={HOME_COUNTRY} 익스포저 EAD 실측 합",
                 citation=f"{_C_SCO} — 국내 시스템적 중요도 평가축",
                 source_module=_M_PTF, is_subtotal=True),
        FormLine("1100", "해외 익스포저", 0, "KRW", ov_ead,
                 formula=f"country≠{HOME_COUNTRY} 익스포저 EAD 실측 합",
                 citation=_C_SCO, source_module=_M_PTF),
        FormLine("1200", "총 익스포저 (EAD 기준)", 0, "KRW", dom_ead + ov_ead,
                 formula="국내 + 해외", citation=_C_SCO, source_module=_M_PTF,
                 is_subtotal=True),
        FormLine("1300", "국내 익스포저 비중", 0, "ratio", w,
                 formula="국내 EAD ÷ 총 EAD — BF201·B2102와 같은 실측 비율",
                 citation=_C_SCO,
                 source_module="risk_lib.regulatory.forms_fss_financial_data"),
        FormLine("2000", "예수금 총액", 0, "KRW", deposit,
                 formula="재무상태표 개인·법인 예수금 4개 계정 합", citation=_C99,
                 source_module=_M_PRU),
        FormLine("2100", "국내 예수금", 0, "KRW", dom_deposit,
                 formula="예수금 총액 × 국내 비중 — 수신 소재지 원장 없음(배분)",
                 citation=_C_SCO, source_module=_M_PRU),
        FormLine("3000", "국내 은행권 총자산 (역산 — 실제 업권 규모 아님)", 0, "KRW",
                 ta / share["asset"],
                 formula=f"자사 자산총계 ÷ 파생 점유율 {share['asset']:.4f} · "
                         f"{_DERIVED} (업권 집계 미보유). 점유율이 관찰 근거 없는 "
                         f"가정이므로 이 값도 실제 국내 은행권 총자산이 아니며 "
                         f"자릿수가 다를 수 있다 — 업권 통계로 인용하면 안 된다",
                 citation=_C_SCO, source_module=_M_DER),
        FormLine("3100", "국내 총자산 점유율", 0, "ratio", share["asset"],
                 formula=f"{_DERIVED} — 업권 총계를 이 값에서 역산한다",
                 citation=_C_SCO, source_module=_M_DER),
        FormLine("3200", "국내 예수금 점유율", 0, "ratio", share["deposit"],
                 formula=_DERIVED, citation=_C_SCO, source_module=_M_DER),
        FormLine("3300", "국내 지급결제 점유율", 0, "ratio", share["payment"],
                 formula=_DERIVED, citation=_C_SCO, source_module=_M_DER),
        FormLine("4000", "자산총계", 0, "KRW", ta,
                 formula="재무상태표 자산총계 — 점유율 역산의 분자", citation=_C99,
                 source_module=_M_PRU),
        _remark("국내·해외 익스포저와 예수금 총액은 산출값이고, 국내 비중은 "
                "forms_fss_financial_data.domestic_share(실측 EAD 비중)를 그대로 "
                "쓴다 — B2102·BF201과 같은 비율이다. 국내 시장점유율은 업권 집계가 "
                "없어 점유율을 먼저 파생하고 업권 총계를 역산했다. 반대로 하면 자사 "
                "규모에 따라 점유율이 100%를 넘을 수 있다. 다만 점유율 자체가 관찰 "
                "근거 없는 가정이므로 역산한 '국내 은행권 총자산'(3000)은 실제 업권 "
                "규모가 아니다 — 업권 통계로 인용하면 안 되고, 업권 집계가 확보되면 "
                "점유율과 함께 한 번에 고쳐야 한다.", _C_SCO),
    ]
    checks = [
        _sum_check("총 익스포저 = 국내 + 해외", L, "1200", ("1000", "1100"), 1.0),
        _ratio_check("국내 비중 = 국내 EAD ÷ 총 EAD", L, "1300",
                     "1000", "1200", 1e-9),
        FormCheck("국내 예수금 = 예수금 총액 × 국내 비중", deposit * w,
                  _val(L, "2100"), tol(deposit)),
        FormCheck("국내 예수금 ≤ 예수금 총액", 0.0,
                  max(0.0, _val(L, "2100") - _val(L, "2000")), tol(deposit)),
        _ratio_check("총자산 점유율 = 자산총계 ÷ 국내 은행권 총자산", L, "3100",
                     "4000", "3000", 1e-9),
        # 점유율은 셋 다 1을 넘을 수 없다. 자산 점유율만 걸면 예수금·지급결제
        # 점유율이 1을 넘어도 서식이 통과한다.
        FormCheck("총자산 점유율 ≤ 1", 0.0,
                  max(0.0, _val(L, "3100") - 1.0), 1e-12),
        FormCheck("예수금 점유율 ≤ 1", 0.0,
                  max(0.0, _val(L, "3200") - 1.0), 1e-12),
        FormCheck("지급결제 점유율 ≤ 1", 0.0,
                  max(0.0, _val(L, "3300") - 1.0), 1e-12),
    ]
    return L, checks


# ---------------------------------------------------------------- B2701

def _b2701(ctx):
    """생산성관련 지표 — 인원·점포가 파생이고 재무수치는 전부 산출값이다."""
    h = headcount(ctx)
    br = domestic_branches(ctx)
    amt = bs_amounts(ctx)
    inc = _income(ctx)
    ta = amt["자산총계"]
    deposit = sum(amt[i] for i in RETAIL_DEPOSITS + CORP_DEPOSITS)
    loan = amt["대출채권 (총액)"]
    # 충당금적립전이익 = 세전이익 − 충당금 전입액. 손익표에서 충당금은 음수다.
    pre_provision = inc["법인세차감전순이익"] - inc["충당금 전입액"]
    L = [
        FormLine("1000", "임직원 수", 0, "count", h["total"],
                 formula=f"자산총계 ÷ 1인당 총자산 {h['assets_per_staff']:,.0f}원 · "
                         f"{_DERIVED} (인사 원장 미보유)",
                 citation=f"{_C99} — 생산성 지표", source_module=_M_DER,
                 is_subtotal=True),
        FormLine("1010", "임원", 1, "count", h["officer"], formula=_DERIVED,
                 source_module=_M_DER),
        FormLine("1020", "정규직", 1, "count", h["regular"], formula=_DERIVED,
                 source_module=_M_DER),
        FormLine("1030", "기간제 근로자", 1, "count", h["temporary"],
                 formula=_DERIVED, source_module=_M_DER),
        FormLine("1100", "점포 수 (본점 포함)", 0, "count", br["total"],
                 formula=f"임직원 수 ÷ 점포당 임직원 {br['staff_per_branch']:.2f}인 · "
                         f"{_DERIVED} (점포 원장 미보유)",
                 citation=_C99, source_module=_M_DER, is_subtotal=True),
        FormLine("2000", "총자산", 0, "KRW", ta,
                 formula="재무상태표 자산총계", citation=_C99,
                 source_module=_M_PRU),
        FormLine("2010", "예수금", 0, "KRW", deposit,
                 formula="개인·법인 예수금 4개 계정 합", citation=_C99,
                 source_module=_M_PRU),
        FormLine("2020", "대출금 (총액)", 0, "KRW", loan,
                 formula="재무상태표 대출채권(총액)", citation=_C99,
                 source_module=_M_PRU),
        FormLine("2100", "영업수익", 0, "KRW", inc["영업수익"],
                 formula="손익계산서 영업수익", citation=_C99,
                 source_module=_M_PRU),
        FormLine("2110", "충당금적립전이익", 0, "KRW", pre_provision,
                 formula="법인세차감전순이익 − 충당금 전입액", citation=_C99,
                 source_module=_M_PRU, is_subtotal=True),
        FormLine("2120", "당기순이익", 0, "KRW", inc["당기순이익"],
                 formula="손익계산서 당기순이익", citation=_C99,
                 source_module=_M_PRU),
        FormLine("3000", "1인당 총자산", 0, "KRW", ta / h["total"],
                 formula="총자산 ÷ 임직원 수", source_module=_M_DER),
        FormLine("3010", "1인당 예수금", 0, "KRW", deposit / h["total"],
                 formula="예수금 ÷ 임직원 수", source_module=_M_DER),
        FormLine("3020", "1인당 대출금", 0, "KRW", loan / h["total"],
                 formula="대출금 ÷ 임직원 수", source_module=_M_DER),
        FormLine("3030", "1인당 영업수익", 0, "KRW", inc["영업수익"] / h["total"],
                 formula="영업수익 ÷ 임직원 수", source_module=_M_DER),
        FormLine("3040", "1인당 충당금적립전이익", 0, "KRW",
                 pre_provision / h["total"],
                 formula="충당금적립전이익 ÷ 임직원 수", source_module=_M_DER),
        FormLine("3050", "1인당 당기순이익", 0, "KRW",
                 inc["당기순이익"] / h["total"],
                 formula="당기순이익 ÷ 임직원 수", source_module=_M_DER),
        FormLine("4000", "점포당 총자산", 0, "KRW", ta / br["total"],
                 formula="총자산 ÷ 점포 수", source_module=_M_DER),
        FormLine("4010", "점포당 예수금", 0, "KRW", deposit / br["total"],
                 formula="예수금 ÷ 점포 수", source_module=_M_DER),
        FormLine("4020", "점포당 당기순이익", 0, "KRW",
                 inc["당기순이익"] / br["total"],
                 formula="당기순이익 ÷ 점포 수", source_module=_M_DER),
        FormLine("4100", "점포당 임직원 수", 0, "count", h["total"] / br["total"],
                 formula="임직원 수 ÷ 점포 수", source_module=_M_DER),
        _remark("재무수치는 전부 산출값이고 분모인 임직원 수·점포 수만 파생값이다. "
                "인사·점포 원장이 원천 데이터에 없어 자산총계에서 1인당 총자산으로 "
                "역산했다. B1101(인원현황)·B1104(기구현황)도 같은 "
                "forms_fss_keyfin_data.headcount·domestic_branches를 import하므로 "
                "임직원 수·점포 수가 서식마다 갈리지 않는다. 점포 수는 "
                "B5103(자지점)과도 같은 domestic_branches를 쓴다.", _C99),
    ]
    checks = [
        _sum_check("임직원 수 = 임원 + 정규직 + 기간제", L, "1000",
                   ("1010", "1020", "1030"), 1e-9),
        _ratio_check("1인당 총자산 = 총자산 ÷ 임직원 수", L, "3000",
                     "2000", "1000", 1e-6),
        _ratio_check("1인당 예수금 = 예수금 ÷ 임직원 수", L, "3010",
                     "2010", "1000", 1e-6),
        _ratio_check("1인당 대출금 = 대출금 ÷ 임직원 수", L, "3020",
                     "2020", "1000", 1e-6),
        _ratio_check("1인당 영업수익 = 영업수익 ÷ 임직원 수", L, "3030",
                     "2100", "1000", 1e-6),
        _ratio_check("1인당 충당금적립전이익", L, "3040", "2110", "1000", 1e-6),
        _ratio_check("1인당 당기순이익", L, "3050", "2120", "1000", 1e-6),
        _ratio_check("점포당 총자산 = 총자산 ÷ 점포 수", L, "4000",
                     "2000", "1100", 1e-6),
        _ratio_check("점포당 예수금", L, "4010", "2010", "1100", 1e-6),
        _ratio_check("점포당 당기순이익", L, "4020", "2120", "1100", 1e-6),
        _ratio_check("점포당 임직원 수 = 임직원 수 ÷ 점포 수", L, "4100",
                     "1000", "1100", 1e-9),
        FormCheck("충당금적립전이익 = 세전이익 − 충당금 전입액",
                  inc["법인세차감전순이익"] - inc["충당금 전입액"],
                  _val(L, "2110"), 1.0),
    ]
    return L, checks


# ---------------------------------------------------------------- B5101

def _b5101(ctx):
    """연결기준 경영지표 — 연결 자회사 원장이 없어 연결 = 단독이다."""
    r = ctx.result
    amt = bs_amounts(ctx)
    inc = _income(ctx)
    aq = ctx.tables["rdm_asset_quality"]
    liq = ctx.tables["pru_liquidity_ratio"].set_index("metric")
    ta = amt["자산총계"]
    eq = amt["자본총계 (회계)"]
    npl = float(aq.loc[aq["classification"].isin(NPL_CLASSES), "balance"].sum())
    loan = float(aq["balance"].sum())
    L = [
        FormLine("100", "연결 범위", 0, "text", None,
                 text_value=f"{_CONSOL} — 자회사 재무제표·연결범위·소수주주지분 원장이 "
                            f"원천 데이터에 없다. B2109·B2118(연결 재무제표)·B2311·"
                            f"B2312(연결 자기자본)와 같은 처리이며, 자회사 규모는 "
                            f"B5102가 파생값으로 따로 보고한다.",
                 citation="K-IFRS 제1110호 연결재무제표"),
        FormLine("1000", "총자산", 0, "KRW", ta, formula=_CONSOL, citation=_C99,
                 source_module=_M_PRU, is_subtotal=True),
        FormLine("1010", "자기자본 (규제자본)", 0, "KRW",
                 float(r.meta["capital"].total), formula=_CONSOL,
                 citation="은행업감독규정 제26조", source_module=_M_CAP),
        FormLine("1020", "자본총계 (회계)", 0, "KRW", eq, formula=_CONSOL,
                 citation=_C99, source_module=_M_PRU),
        FormLine("1100", "영업수익", 0, "KRW", inc["영업수익"], formula=_CONSOL,
                 citation=_C99, source_module=_M_PRU),
        FormLine("1110", "당기순이익", 0, "KRW", inc["당기순이익"],
                 formula=_CONSOL, citation=_C99, source_module=_M_PRU),
        FormLine("2000", "총자산이익률 (ROA)", 0, "ratio",
                 inc["당기순이익"] / ta if ta else 0.0,
                 formula="당기순이익 ÷ 총자산", citation=_C99,
                 source_module=_M_PRU),
        FormLine("2010", "자기자본이익률 (ROE)", 0, "ratio",
                 inc["당기순이익"] / eq if eq else 0.0,
                 formula="당기순이익 ÷ 자본총계 (회계)", citation=_C99,
                 source_module=_M_PRU),
        FormLine("3000", "위험가중자산", 0, "KRW", float(r.bis.rwa),
                 citation="은행업감독규정 제26조 · CRE20.1",
                 source_module=_M_CAP, is_subtotal=True),
        FormLine("3010", "총자본비율", 0, "ratio", float(r.bis.total_ratio),
                 formula="자기자본 ÷ 위험가중자산",
                 citation="은행업감독규정 제26조", source_module=_M_CAP),
        FormLine("3020", "기본자본비율", 0, "ratio", float(r.bis.tier1_ratio),
                 citation="은행업감독규정 제26조", source_module=_M_CAP),
        FormLine("3030", "보통주자본비율", 0, "ratio", float(r.bis.cet1_ratio),
                 citation="은행업감독규정 제26조", source_module=_M_CAP),
        FormLine("3040", "레버리지비율", 0, "ratio",
                 float(r.leverage.leverage_ratio),
                 formula="기본자본 ÷ 총익스포저", citation="LEV20.1",
                 source_module="risk_lib.capital.leverage"),
        FormLine("4000", "총여신", 0, "KRW", loan,
                 formula="rdm_asset_quality 잔액 실측 합", citation=_C27,
                 source_module=_M_RDM),
        FormLine("4010", "고정이하여신", 0, "KRW", npl,
                 formula="classification ∈ (고정, 회수의문, 추정손실)",
                 citation=_C27, source_module=_M_RDM),
        FormLine("4020", "고정이하여신비율", 0, "ratio",
                 npl / loan if loan else 0.0,
                 formula="고정이하여신 ÷ 총여신", citation=_C27,
                 source_module=_M_RDM),
        FormLine("5000", "원화유동성비율", 0, "ratio",
                 float(liq.loc["원화유동성비율", "value"]),
                 formula="잔존만기 1개월 이내 유동성자산 ÷ 유동성부채",
                 citation="은행업감독규정 제26조 제1항", source_module=_M_ALM),
        FormLine("5010", "원화예대율", 0, "ratio",
                 float(liq.loc["원화예대율", "value"]),
                 formula="원화대출금 ÷ 원화예수금",
                 citation="은행업감독규정 제26조 제1항", source_module=_M_ALM),
        FormLine("5020", "유동성커버리지비율 (LCR)", 0, "ratio",
                 float(r.alm["lcr"].lcr), citation="LCR20.1",
                 source_module=_M_ALM),
        _remark("연결 대상 자회사의 재무제표가 원천 데이터에 없어 연결 = 단독으로 "
                "적었다. 지표는 전부 산출값이며 파생이 없다. 연결 범위가 확보되면 "
                "B2109·B2311과 함께 한 번에 고쳐야 한다 — 한 서식만 연결로 바꾸면 "
                "연결 총자산이 서식마다 달라진다.", "K-IFRS 제1110호 연결재무제표"),
    ]
    checks = [
        _ratio_check("ROA = 당기순이익 ÷ 총자산", L, "2000", "1110", "1000", 1e-12),
        _ratio_check("ROE = 당기순이익 ÷ 자본총계", L, "2010", "1110", "1020", 1e-12),
        _ratio_check("총자본비율 = 자기자본 ÷ 위험가중자산", L, "3010",
                     "1010", "3000", 1e-9),
        _ratio_check("고정이하여신비율 = 고정이하 ÷ 총여신", L, "4020",
                     "4010", "4000", 1e-12),
        FormCheck("고정이하여신 ≤ 총여신", 0.0, max(0.0, npl - loan), 1.0),
    ]
    return L, checks


# ---------------------------------------------------------------- B5102

def _b5102(ctx):
    """자회사 경영평가 — 출자금액·지분율은 B3110과 같고 경영실적이 파생이다."""
    df = subsidiary_performance(ctx)
    t = ctx.tables["pru_ownership_limit"]
    invested = float(t.loc[t["item"] == "자회사 출자", "used"].iloc[0])
    L = [
        FormLine("1000", "자회사 출자 총액", 0, "KRW", invested,
                 formula="pru_ownership_limit 자회사 출자 사용액 — 산출값",
                 citation="은행법 제37조 제2항", source_module=_M_OWN,
                 is_subtotal=True),
        FormLine("1100", "자회사 수", 0, "count", float(len(df)),
                 formula=f"{_DERIVED} — B3110·B3111과 같은 자회사 목록",
                 citation="은행법 제37조 제2항", source_module=_M_DER),
    ]
    inv_codes, ta_codes, ni_codes = [], [], []
    checks: list[FormCheck] = []
    for i, (_, r) in enumerate(df.iterrows(), start=1):
        base = 2000 + i * 100
        inv_codes.append(str(base))
        ta_codes.append(str(base + 20))
        ni_codes.append(str(base + 30))
        L += [
            FormLine(str(base), f"자회사 · {r['name']} — 출자금액", 1, "KRW",
                     float(r["investment"]),
                     formula=f"의결권 지분율 {float(r['stake']):.1%} · {_DERIVED}",
                     citation="은행법 제37조 제2항", source_module=_M_DER,
                     is_subtotal=True),
            FormLine(str(base + 10), "자기자본", 2, "KRW", float(r["equity"]),
                     formula="출자금액 ÷ 지분율 (역산)", source_module=_M_DER),
            FormLine(str(base + 20), "총자산", 2, "KRW", float(r["total_assets"]),
                     formula=f"자기자본 × 파생 배수 · {_DERIVED}",
                     source_module=_M_DER),
            FormLine(str(base + 30), "당기순이익", 2, "KRW",
                     float(r["net_income"]), formula=_DERIVED,
                     source_module=_M_DER),
            FormLine(str(base + 40), "총자산이익률 (ROA)", 2, "ratio",
                     float(r["roa"]), formula="당기순이익 ÷ 총자산",
                     source_module=_M_DER),
            FormLine(str(base + 50), "경영평가 등급", 2, "count",
                     float(r["grade"]),
                     formula="1(우수)~5(위험) — ROA의 결정론적 구간 함수",
                     source_module=_M_DER),
            FormLine(str(base + 60), "신용공여", 2, "KRW", float(r["credit"]),
                     formula=f"{_DERIVED} — B3111과 같은 값",
                     citation="은행법 제37조 제3항", source_module=_M_DER),
        ]
        checks += [
            _ratio_check(f"{r['name']} ROA = 당기순이익 ÷ 총자산", L,
                         str(base + 40), str(base + 30), str(base + 20), 1e-12),
            FormCheck(f"{r['name']} 출자금액 = 자기자본 × 지분율",
                      float(r["equity"]) * float(r["stake"]),
                      float(r["investment"]), 1.0),
        ]
    L += [
        FormLine("5000", "자회사 총자산 계", 0, "KRW",
                 float(df["total_assets"].sum()), formula=_DERIVED,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("5100", "자회사 당기순이익 계", 0, "KRW",
                 float(df["net_income"].sum()), formula=_DERIVED,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("5200", "자회사 신용공여 계", 0, "KRW",
                 float(df["credit"].sum()),
                 formula=f"{_DERIVED} — B3111 합계와 같다",
                 citation="은행법 제37조 제3항 제2호", source_module=_M_DER),
        FormLine("6000", "적자 자회사 수", 0, "count",
                 float(int((df["net_income"] < 0).sum())),
                 formula="당기순이익 < 0 인 자회사 수", source_module=_M_DER),
        FormLine("6100", "취약(4~5등급) 자회사 수", 0, "count",
                 float(int((df["grade"] >= 4).sum())),
                 formula="경영평가 등급 4 이상", source_module=_M_DER),
        _remark("자회사 목록·출자금액·지분율·신용공여는 B3110·B3111과 **같은 파생 "
                "함수**(forms_fss_compliance_data.subsidiary_book)에서 오므로 세 "
                "서식이 갈리지 않는다. 출자 총액만 산출값이다. 자회사 재무제표가 없어 "
                "자기자본은 출자금액 ÷ 지분율로 역산하고 총자산·당기순이익만 파생했다. "
                "평가등급은 난수가 아니라 ROA의 결정론적 함수다.",
                "은행법 제37조 · 은행업감독규정 제99조"),
    ]
    checks += [
        _sum_check("자회사별 출자금액 합 = 자회사 출자 총액", L, "1000",
                   tuple(inv_codes), 1.0),
        _sum_check("자회사 총자산 계 = 자회사별 총자산 합", L, "5000",
                   tuple(ta_codes), 1.0),
        _sum_check("자회사 당기순이익 계 = 자회사별 순이익 합", L, "5100",
                   tuple(ni_codes), 1.0),
        FormCheck("자회사 수 = 명세 건수", float(len(df)), _val(L, "1100"), 1e-9),
    ]
    return L, checks


# ---------------------------------------------------------------- B5103

def _b5103(ctx):
    """자지점 — 국내 점포는 파생, 해외 자지점은 BF103과 같은 마스터에서 온다."""
    br = domestic_branches(ctx)
    bm = branch_master(ctx)
    ov_sub = float(bm["sub_branch"].sum())
    ov_office = float(bm["sub_office"].sum())
    ov_rep = float(bm["rep_office"].sum())
    ov_kind = bm["kind"].value_counts()
    ov_branch = float(int(ov_kind.get("지점", 0)))
    ov_local = float(int(ov_kind.get("현지법인", 0)))
    L = [
        FormLine("1000", "국내 점포 수 계", 0, "count", br["total"],
                 formula=f"임직원 수 ÷ 점포당 임직원 · {_DERIVED} — B2701과 같은 값",
                 citation="은행법 제13조 지점의 설치 · 은행업감독규정 제99조",
                 source_module=_M_DER, is_subtotal=True),
        FormLine("1010", "본점", 1, "count", br["head_office"],
                 formula="본점은 언제나 1개다", source_module=_M_DER),
        FormLine("1020", "지점", 1, "count", br["branch"], formula=_DERIVED,
                 source_module=_M_DER),
        FormLine("1100", "국내 자지점 수", 0, "count", br["sub_branch"],
                 formula=f"국내 점포 수 × 파생비율 · {_DERIVED}",
                 citation="은행법 제13조", source_module=_M_DER),
        FormLine("1110", "국내 출장소 수", 0, "count", br["sub_office"],
                 formula=_DERIVED, citation="은행법 제13조", source_module=_M_DER),
        FormLine("2000", "해외 점포 수", 0, "count", float(len(bm)),
                 formula="해외점포 마스터 행 수 — BF101·B1104와 같은 마스터",
                 citation="은행법 제13조 제2항 — 국외 지점 설치",
                 source_module="risk_lib.regulatory.forms_fss_overseas_data",
                 is_subtotal=True),
        # 해외 점포 수의 구성요소는 점포 종류(지점·현지법인)다. 자지점·출장소·
        # 사무소는 이 점포들에 **부속된** 조직이라 합이 점포 수를 넘는다 —
        # 하위 레벨로 달면 엑셀에서 구성요소로 읽혀 10 < 6+8+8이 된다.
        FormLine("2010", "해외 지점", 1, "count", ov_branch,
                 formula="해외점포 마스터 kind='지점' — B1104와 같은 값",
                 source_module="risk_lib.regulatory.forms_fss_overseas_data"),
        FormLine("2020", "해외 현지법인", 1, "count", ov_local,
                 formula="해외점포 마스터 kind='현지법인' — B1104와 같은 값",
                 source_module="risk_lib.regulatory.forms_fss_overseas_data"),
        FormLine("2100", "해외 점포 부속 자지점 수", 0, "count", ov_sub,
                 formula="해외점포 마스터 sub_branch 합 — BF103과 같은 값. "
                         "해외 점포 수(2000)의 구성요소가 아니라 그 점포에 부속된 수다",
                 source_module="risk_lib.regulatory.forms_fss_overseas_data"),
        FormLine("2110", "해외 점포 부속 출장소 수", 0, "count", ov_office,
                 formula="해외점포 마스터 sub_office 합 — 부속 조직 수다",
                 source_module="risk_lib.regulatory.forms_fss_overseas_data"),
        # 라벨을 '해외 사무소'로 두면 B1104의 '해외 사무소'(kind='사무소'인 독립
        # 점포 수)와 같은 이름에 다른 값이 된다. 부속 사무소임을 라벨에 남긴다.
        FormLine("2120", "해외 점포 부속 사무소 수", 0, "count", ov_rep,
                 formula="해외점포 마스터 rep_office 합 — B1104의 '해외 사무소'"
                         "(kind='사무소'인 독립 점포)와는 다른 개념이다",
                 source_module="risk_lib.regulatory.forms_fss_overseas_data"),
        FormLine("3000", "자지점 총계 (국내 + 해외)", 0, "count",
                 br["sub_branch"] + ov_sub, formula="국내 자지점 + 해외 자지점",
                 citation="은행법 제13조", source_module=_M_DER, is_subtotal=True),
        FormLine("3100", "출장소 총계 (국내 + 해외)", 0, "count",
                 br["sub_office"] + ov_office, formula="국내 출장소 + 해외 출장소",
                 source_module=_M_DER, is_subtotal=True),
        FormLine("4000", "점포당 임직원 수", 0, "count",
                 headcount(ctx)["total"] / br["total"],
                 formula="임직원 수 ÷ 국내 점포 수 — B2701과 같은 값",
                 source_module=_M_DER),
        _remark("국내 점포·자지점·출장소 수는 점포 원장이 없어 파생했고 B2701(생산성)과 "
                "같은 domestic_branches를 쓴다. 해외분은 새로 파생하지 않고 "
                "forms_fss_overseas_data.branch_master를 그대로 읽으므로 BF101·BF103과 "
                "갈리지 않는다. 해외 점포 수(2000)의 구성요소는 점포 종류(지점·"
                "현지법인)이고, 자지점·출장소·사무소(2100~2120)는 그 점포에 부속된 "
                "조직이라 점포 수보다 클 수 있다 — 구성요소가 아니다.",
                "은행법 제13조 · 은행업감독규정 제99조"),
    ]
    checks = [
        _sum_check("국내 점포 수 계 = 본점 + 지점", L, "1000",
                   ("1010", "1020"), 1e-9),
        _sum_check("해외 점포 수 = 지점 + 현지법인", L, "2000",
                   ("2010", "2020"), 1e-9),
        _sum_check("자지점 총계 = 국내 + 해외", L, "3000",
                   ("1100", "2100"), 1e-9),
        _sum_check("출장소 총계 = 국내 + 해외", L, "3100",
                   ("1110", "2110"), 1e-9),
        FormCheck("해외 자지점 수 = 해외점포 마스터 합", ov_sub,
                  _val(L, "2100"), 1e-9),
        FormCheck("점포당 임직원 수 = 임직원 수 ÷ 국내 점포 수",
                  headcount(ctx)["total"] / br["total"], _val(L, "4000"), 1e-9),
    ]
    return L, checks


# ---------------------------------------------------------------- 등록

BUILDERS: dict[str, tuple[str, str, Callable]] = {
    "B2201": ("은행업감독규정 제99조 업무보고서 — 기중평잔 기준 자금조달·운용",
              "PRD-ALM", _b2201),
    "B2203": ("은행법 제28조 겸영업무 · 자본시장법 제103조 신탁재산", "PRD-ALM",
              _b2203),
    "B2204": ("은행법 제33조 — 금융채 발행 · 은행업감독규정 제99조", "PRD-ALM",
              _b2204),
    "B2205": ("은행법 제33조 — 금융채 발행 · 은행업감독규정 제99조", "PRD-ALM",
              _b2205),
    "B2206": ("은행법 제33조 — 금융채 발행 · 은행업감독규정 제99조", "PRD-ALM",
              _b2206),
    "B2207": ("국고금 관리법 제36조 · 지방회계법 제77조 — 금고 지정", "PRD-ALM",
              _b2207),
    "B2208": ("은행업감독규정 제99조 · Basel III CRE20.94 부외항목 신용환산",
              "PRD-RDM", _b2208),
    "B2209": ("은행업감독규정 제27조 자산건전성 분류 — 무수익여신 산정기준",
              "PRD-RDM", _b2209),
    "B2210": ("은행업감독규정 제99조 업무보고서 — 대출금액대별 편제", "PRD-RDM",
              _b2210),
    "B2211": ("은행법 제35조의2 · 제35조의3 — 대주주와의 거래", "PRD-RDM", _b2211),
    "B2212": ("Basel III SCO40.6 상호연계성 · 은행업감독규정 제99조", "PRD-RDM",
              _b2212),
    "B2212-1": ("Basel III SCO40.6 상호연계성 · 은행업감독규정 제99조", "PRD-RDM",
                _b2212_1),
    "B2213": ("Basel III SCO40.6 상호연계성 · 은행업감독규정 제99조", "PRD-ALM",
              _b2213),
    "B2213-1": ("Basel III SCO40.6 상호연계성 · 은행업감독규정 제99조", "PRD-ALM",
                _b2213_1),
    "B2214": ("Basel III SCO40.5 규모 · SCO40.6 상호연계성(발행 증권 잔액)",
              "PRD-CAP", _b2214),
    "B2215": ("Basel III SCO40.7 — G-SIB 대체가능성 지표", "PRD-RDM", _b2215),
    "B2216": ("Basel III SCO40.8 — G-SIB 복잡성 지표", "PRD-MKT", _b2216),
    "B2217": ("Basel III SCO40 — 국내 시스템적 중요도 평가축", "PRD-RDM", _b2217),
    "B2701": ("은행업감독규정 제99조 업무보고서 — 생산성 지표", "PRD-RDM", _b2701),
    "B5101": ("은행업감독규정 제26조 · K-IFRS 제1110호 연결재무제표", "PRD-CAP",
              _b5101),
    "B5102": ("은행법 제37조 — 자회사 출자·신용공여 · 은행업감독규정 제99조",
              "PRD-RDM", _b5102),
    "B5103": ("은행법 제13조 지점의 설치 · 은행업감독규정 제99조", "PRD-RDM",
              _b5103),
}
