"""금감원 FINES 업무보고서 — 해외점포 일반·재무·유동성·자산건전성 19건.

근거는 은행업감독규정 제27조(자산건전성 분류)·제29조(대손충당금)·제53조(거액여신)·
제63조(외화유동성)·제99조(업무보고서)와 Basel 기준이다.

**해외점포 원장이 없다.** 이 저장소는 익스포저의 소재국(`country`)만 알 뿐 어느
점포가 취급했는지 모른다. 점포 마스터(점포명·소재국·형태·설립연도)와 익스포저의
점포 귀속은 `forms_fss_overseas_data`가 기준일 고정 시드로 만드는 **파생값**이다.
배분은 **같은 나라 안에서만** 일어나므로 **국가별 합계는 실측 그대로**이며, BF304가
포트폴리오 country 집계와의 일치를 FormCheck로 건다.

파생·가정이 아닌 것 — 금액·건전성분류·연체·충당금·담보·보증·만기구조는 전부
파이프라인 산출값이다. 파생이 들어간 라인은 **그 라인 자체의** formula에 파생임을
남긴다. 상위 소계에만 적어 두면 서식이 flat table로 실체화될 때 하위 셀이 실측으로
읽힌다.

계정별 해외 원장이 없어 BF201·BF301은 `overseas_share`(해외 익스포저 실측 비중)로
배분한다 — **비율은 실측이고 배분 결과는 파생**이다. 전 계정에 같은 비율을 곱하므로
대차 항등식(자산 = 부채 + 자본)은 배분 후에도 성립한다. BF202는 배분을 쓰지 않는다
— 약정·보증·파생·충당금·담보는 익스포저 소재국으로 직접 걸러 전부 실측이다.

BF406의 100만달러 환산에 쓰는 환율은 **가정**이며 `overseas_data.USD_KRW` 한 곳에
모아 두었다 — 원장에 통화·환율이 없다.

서식명·작성주기는 여기 적지 않는다 — FINES 마스터가 정본이고 forms.py가 붙인다.
"""

from __future__ import annotations

from typing import Callable

import pandas as pd

from risk_lib.regulatory.forms_base import (
    FormCheck, FormLine, _ratio_check, _sum_check, _val,
)
from risk_lib.regulatory.forms_fss_overseas_data import (
    AQ_ORDER, BRANCH_KINDS, DPD_BANDS, HOME_COUNTRY, INVESTMENT_GRADE,
    LARGE_NPL_USD, MATURITY_BANDS, NPL_CLASSES, RATING_ORDER, USD_KRW, _tol,
    branch_master, country_exposure, overseas_book, overseas_collateral,
    overseas_countries, overseas_derivatives, overseas_guarantee,
    overseas_securities, overseas_share,
)
from risk_lib.regulatory.forms_fss_retail_data import COLLATERAL_BUCKETS

_M_DER = "risk_lib.regulatory.forms_fss_overseas_data"
_M_RDM = "risk_lib.datamodel.materialize_detail.materialize_rdm_detail"
_M_ECL = "risk_lib.provisioning.ecl"
_M_ALM = "risk_lib.alm"
_M_PRU = "risk_lib.prudential.financials"
_M_PTF = "risk_lib.data_gen.generate_portfolio"
_M_CON = "risk_lib.concentration"
_M_MKT = "risk_lib.market_data"

_C27 = "은행업감독규정 제27조 자산건전성 5단계 분류"
_C29 = "은행업감독규정 제29조 제1항 최저적립률"
_C53 = "은행업감독규정 제53조 거액여신(자기자본 10% 초과)"
_C63 = "은행업감독규정 제63조 외화유동성"
_C99 = "은행업감독규정 제99조 업무보고서"
_CRE22 = "Basel III CRE22 적격 담보 · 감독 haircut"
_SRP31 = "Basel SRP31 IRRBB 재가격 갭"

_DERIVED = "원장 부재 — 기준일 고정 시드 파생값"
_DERIVED_ALLOC = "해외 익스포저 실측 비중으로 배분 — 계정별 해외 원장 없음"
_MEASURED = "포트폴리오 country 실측 집계 — 파생 아님"

_TOP_N = 20                    # 명세 서식에 개별 기재하는 상한 (나머지는 '기타')


def _grade(rating: str) -> str:
    return rating if rating in RATING_ORDER else "UNRATED"


def _class_block(df: pd.DataFrame, base: int, *, value_col: str = "balance",
                 note: str | None = None) -> tuple[list[FormLine], tuple[str, ...]]:
    """건전성분류 5단계 잔액 라인 한 벌 — 해당 익스포저가 없는 단계도 0으로 낸다.

    분류 단계가 빠지면 감독당국 집계와 행 수가 어긋나 대사가 안 된다.
    """
    L, codes = [], []
    for i, cls in enumerate(AQ_ORDER, start=1):
        s = df[df["classification"] == cls]
        code = str(base + i * 10)
        codes.append(code)
        L.append(FormLine(code, cls, 2, "KRW", float(s[value_col].sum()),
                          formula=f"{len(s):,}건" + (f" · {note}" if note else ""),
                          citation=_C27, source_module=_M_RDM))
    return L, tuple(codes)


# ---------------------------------------------------------------- BF101

def _bf101(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """점포개요 — 점포 마스터는 파생, 국가별 잔액은 실측이다."""
    bm = branch_master(ctx)
    ob = overseas_book(ctx)
    total = float(ob["balance"].sum())
    L = [
        FormLine("1000", "해외점포 총수", 0, "count", float(len(bm)),
                 formula=f"소재국 {bm['country'].nunique()}개국 · {_DERIVED}",
                 citation=_C99, source_module=_M_DER, is_subtotal=True),
    ]
    kind_codes = []
    for i, kind in enumerate(BRANCH_KINDS, start=1):
        code = str(1000 + i * 10)
        kind_codes.append(code)
        L.append(FormLine(code, f"형태 · {kind}", 1, "count",
                          float((bm["kind"] == kind).sum()),
                          formula=_DERIVED, citation=_C99, source_module=_M_DER))
    L += [
        FormLine("2000", "해외점포 귀속 여신잔액", 0, "KRW", total,
                 formula=f"익스포저 {len(ob):,}건 · {_MEASURED}",
                 citation=_C99, source_module=_M_RDM, is_subtotal=True),
        FormLine("2010", "해외점포 귀속 EAD", 0, "KRW", float(ob["ead"].sum()),
                 formula=_MEASURED, citation="Basel III CRE20 익스포저 측정",
                 source_module=_M_PTF),
    ]
    ctry_bal, ctry_cnt, ratios = [], [], []
    for i, country in enumerate(overseas_countries(ctx), start=1):
        base = 3000 + i * 100
        sub = ob[ob["country"] == country]
        bsub = bm[bm["country"] == country]
        ctry_cnt.append(str(base))
        ctry_bal.append(str(base + 10))
        ratios.append((country, str(base + 20), str(base + 10), "2000"))
        L += [
            FormLine(str(base), f"소재국 · {country} 점포수", 1, "count",
                     float(len(bsub)), formula=_DERIVED, citation=_C99,
                     source_module=_M_DER, is_subtotal=True),
            FormLine(str(base + 10), "여신잔액", 2, "KRW",
                     float(sub["balance"].sum()),
                     formula=f"{len(sub):,}건 · {_MEASURED}", citation=_C99,
                     source_module=_M_RDM),
            FormLine(str(base + 20), "해외 여신잔액 대비 비중", 2, "ratio",
                     float(sub["balance"].sum()) / total if total else 0.0,
                     formula="국가별 여신잔액 ÷ 해외 여신잔액", citation=_C99,
                     source_module=_M_RDM),
        ]
    br_codes = []
    for i, (_, b) in enumerate(bm.iterrows(), start=1):
        sub = ob[ob["branch_code"] == b["branch_code"]]
        code = str(5000 + i * 10)
        br_codes.append(code)
        L.append(FormLine(
            code, f"{b['branch_code']} {b['branch_name']}", 1, "KRW",
            float(sub["balance"].sum()),
            formula=(f"{b['country']} · {b['kind']} · {b['established_year']}년 "
                     f"설립 · {len(sub):,}건 · 점포 귀속은 {_DERIVED}"),
            citation=_C99, source_module=_M_DER))
    L.append(FormLine("9000", "적용 범위 비고", 0, "text", None,
                      text_value=("해외점포 원장이 없어 점포 마스터와 익스포저 귀속을 "
                                  "기준일 고정 시드로 파생한다. 배분은 같은 나라 "
                                  "안에서만 일어나므로 국가별 합계는 실측이다. "
                                  "사무소는 영업을 하지 않아 여신잔액이 0이다."),
                      citation=_C99, source_module=_M_DER))
    t = _tol(total)
    checks = [
        _sum_check("형태별 점포수 합 = 해외점포 총수", L, "1000", tuple(kind_codes),
                   1e-9),
        _sum_check("소재국별 점포수 합 = 해외점포 총수", L, "1000", tuple(ctry_cnt),
                   1e-9),
        _sum_check("소재국별 여신잔액 합 = 해외 여신잔액", L, "2000",
                   tuple(ctry_bal), t),
        _sum_check("점포별 여신잔액 합 = 해외 여신잔액", L, "2000", tuple(br_codes), t),
    ] + [
        _ratio_check(f"{c} 비중 = 국가별 ÷ 해외 합계", L, rc, nc, dc)
        for c, rc, nc, dc in ratios
    ]
    return L, checks


# ---------------------------------------------------------------- BF103

def _bf103(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """자지점·출장소·사무소 설치현황 — 부속점포 수는 전부 파생값이다."""
    bm = branch_master(ctx)
    cols = (("sub_branch", "자지점"), ("sub_office", "출장소"),
            ("rep_office", "사무소"))
    total = float(sum(bm[c].sum() for c, _ in cols))
    L = [
        FormLine("1000", "부속점포 총수", 0, "count", total,
                 formula=f"본점포 {len(bm)}개 기준 · {_DERIVED}", citation=_C99,
                 source_module=_M_DER, is_subtotal=True),
    ]
    top_codes = []
    for i, (col, label) in enumerate(cols, start=1):
        code = str(1000 + i * 10)
        top_codes.append(code)
        L.append(FormLine(code, f"구분 · {label}", 1, "count",
                          float(bm[col].sum()), formula=_DERIVED, citation=_C99,
                          source_module=_M_DER))
    per_branch, checks = [], []
    for i, (_, b) in enumerate(bm.iterrows(), start=1):
        base = 2000 + i * 100
        per_branch.append(str(base))
        kids = []
        L.append(FormLine(
            str(base), f"{b['branch_code']} {b['branch_name']}", 1, "count",
            float(b["sub_branch"] + b["sub_office"] + b["rep_office"]),
            formula=(f"{b['country']} · {b['kind']} · {b['established_year']}년 "
                     f"설립 · {_DERIVED}"),
            citation=_C99, source_module=_M_DER, is_subtotal=True))
        for j, (col, label) in enumerate(cols, start=1):
            code = str(base + j * 10)
            kids.append(code)
            L.append(FormLine(code, label, 2, "count", float(b[col]),
                              formula=_DERIVED, citation=_C99,
                              source_module=_M_DER))
        checks.append(_sum_check(f"{b['branch_code']} 부속점포 소계", L, str(base),
                                 tuple(kids), 1e-9))
    L.append(FormLine("9000", "적용 범위 비고", 0, "text", None,
                      text_value=("부속점포 설치 원장이 없어 본점포별 설치 수를 "
                                  "기준일 고정 시드로 파생한다. 사무소 형태 점포는 "
                                  "영업을 하지 않아 부속점포를 두지 않는다."),
                      citation=_C99, source_module=_M_DER))
    checks += [
        _sum_check("구분별 합 = 부속점포 총수", L, "1000", tuple(top_codes), 1e-9),
        _sum_check("본점포별 합 = 부속점포 총수", L, "1000", tuple(per_branch), 1e-9),
    ]
    return L, checks


# ---------------------------------------------------------------- BF104

def _bf104(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """현지금융시장동향 — 정성 서술 원장이 없어 소재국별 산출 지표로 대체한다."""
    ob = overseas_book(ctx)
    total = float(ob["balance"].sum())
    L = [
        FormLine("1000", "해외 여신잔액 합계", 0, "KRW", total,
                 formula=f"{_MEASURED} · 익스포저 {len(ob):,}건", citation=_C99,
                 source_module=_M_RDM, is_subtotal=True),
    ]
    bal_codes, ratios = [], []
    for i, country in enumerate(overseas_countries(ctx), start=1):
        base = 2000 + i * 100
        sub = ob[ob["country"] == country]
        bal = float(sub["balance"].sum())
        bal_codes.append(str(base + 10))
        ratios.append((country, str(base + 20), str(base + 10), "1000"))
        # 실질GDP성장률은 기업 차주에만 관측된다 — 모수를 formula에 남긴다.
        gsub = sub[sub["gdp_growth"].notna()]
        gw = float(gsub["balance"].sum())
        gdp = (float((gsub["gdp_growth"] * gsub["balance"]).sum() / gw)
               if gw else 0.0)
        pd_avg = float((sub["pd"] * sub["balance"]).sum() / bal) if bal else 0.0
        npl = float(sub[sub["npl"]]["balance"].sum())
        L += [
            FormLine(str(base), f"소재국 · {country}", 0, "text", None,
                     text_value=(f"{country} 소재 익스포저 {len(sub):,}건 · "
                                 f"여신잔액 {bal:,.0f}원. 현지 감독정책 변동사항은 "
                                 f"외부 자료이므로 산출 파이프라인이 담지 못한다 "
                                 f"— 아래 지표는 산출값 기준 시장 익스포저 요약이다."),
                     citation=_C99, source_module=_M_RDM),
            FormLine(str(base + 10), "여신잔액", 1, "KRW", bal,
                     formula=f"{len(sub):,}건 · {_MEASURED}", citation=_C99,
                     source_module=_M_RDM),
            FormLine(str(base + 20), "해외 합계 대비 비중", 1, "ratio",
                     bal / total if total else 0.0,
                     formula="국가별 여신잔액 ÷ 해외 합계", citation=_C99,
                     source_module=_M_RDM),
            FormLine(str(base + 30), "실질GDP성장률 (잔액가중)", 1, "ratio", gdp,
                     formula=f"기업 차주 {len(gsub):,}건 관측 가중평균 — 그 외 "
                             f"자산군은 관측치 없음", citation=_C99,
                     source_module=_M_PTF),
            FormLine(str(base + 40), "가중평균 PD", 1, "ratio", pd_avg,
                     formula="Σ(PD × 잔액) ÷ Σ잔액",
                     citation="Basel III CRE36 PD 추정", source_module=_M_PTF),
            FormLine(str(base + 50), "고정이하여신비율", 1, "ratio",
                     npl / bal if bal else 0.0,
                     formula="고정이하여신 ÷ 여신잔액", citation=_C27,
                     source_module=_M_RDM),
        ]
    L.append(FormLine("9000", "주요감독정책 변동사항", 0, "text", None,
                      text_value=("현지 감독정책 변동은 산출 원장에 없는 정성 항목이다. "
                                  "본 서식은 그것을 지어내지 않고 소재국별 익스포저·"
                                  "건전성 지표로 대체하며, 정성 서술은 별도 첨부로 "
                                  "제출한다."),
                      citation=_C99))
    t = _tol(total)
    checks = [
        _sum_check("소재국별 여신잔액 합 = 해외 합계", L, "1000", tuple(bal_codes), t),
    ] + [
        _ratio_check(f"{c} 비중 = 국가별 ÷ 해외 합계", L, rc, nc, dc)
        for c, rc, nc, dc in ratios
    ]
    return L, checks


# ---------------------------------------------------------------- BF201

_BS_TOTALS = ("자산총계", "부채총계", "자본총계 (회계)", "규제자본 합계 (참고)")
# 대출채권은 총액·차감·순액이 함께 실린다. 순액만 합계에 넣어야 이중계상이 없다.
_BS_SKIP = ("대출채권 (총액)", "대손충당금 (차감)")


def _bf201(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """자산과 부채 — 계정별 해외 원장이 없어 전 계정에 같은 실측 비중을 곱한다.

    한 비율을 전 계정에 곱하므로 대차 항등식이 배분 후에도 성립한다. 계정별로
    다른 비율을 쓰면 항등식이 깨지고 그 차액을 메울 근거가 없다.
    """
    bs = ctx.tables["pru_balance_sheet"]
    w = overseas_share(ctx)
    ob = overseas_book(ctx)
    L = [
        FormLine("100", "해외분 배분비율", 0, "ratio", w,
                 formula="해외 EAD ÷ 전체 EAD — 비율은 실측, 계정별 배분은 파생",
                 citation=_C99, source_module=_M_DER),
    ]
    code_of, comp = {}, {"자산": [], "부채": [], "자본": []}
    for si, section in enumerate(("자산", "부채", "자본"), start=1):
        sub = bs[bs["section"] == section]
        base = si * 1000
        L.append(FormLine(str(base), f"{section} 구분", 0, "text", None,
                          text_value=f"{len(sub)}개 계정 · 해외분",
                          citation=_C99, source_module=_M_PRU))
        for j, (_, r) in enumerate(sub.iterrows(), start=1):
            code = str(base + j * 10)
            item = str(r["item"])
            code_of[item] = code
            is_total = item in _BS_TOTALS
            L.append(FormLine(
                code, item, 1, "KRW", float(r["amount"]) * w,
                formula=f"본지점 합산 {float(r['amount']):,.0f}원 × {w:.6f} "
                        f"— {_DERIVED_ALLOC}",
                citation=_C99, source_module=_M_PRU, is_subtotal=is_total))
            if not is_total and item not in _BS_SKIP:
                comp[section].append(code)

    ov_loan = float(ob["balance"].sum())
    L.append(FormLine("4000", "해외 여신잔액 (원장 실측)", 0, "KRW", ov_loan,
                      formula=f"{_MEASURED} · 익스포저 {len(ob):,}건",
                      citation=_C99, source_module=_M_RDM, is_subtotal=True))
    assets = _val(L, code_of["자산총계"])
    checks = [
        _sum_check("자산 구성계정 합 = 자산총계", L, code_of["자산총계"],
                   tuple(comp["자산"]), _tol(assets)),
        _sum_check("부채 구성계정 합 = 부채총계", L, code_of["부채총계"],
                   tuple(comp["부채"]), _tol(assets)),
        _sum_check("자본 구성계정 합 = 자본총계 (회계)", L, code_of["자본총계 (회계)"],
                   tuple(comp["자본"]), _tol(assets)),
        _sum_check("자산총계 = 부채총계 + 자본총계", L, code_of["자산총계"],
                   (code_of["부채총계"], code_of["자본총계 (회계)"]), _tol(assets)),
        _sum_check("대출채권 순액 = 총액 + 대손충당금(차감)", L,
                   code_of["대출채권 (순액)"],
                   (code_of["대출채권 (총액)"], code_of["대손충당금 (차감)"]),
                   _tol(assets)),
        # 배분비율이 EAD 비중이고 대출채권(총액)이 전체 EAD이므로 이 둘은 같아야
        # 한다 — 어긋나면 배분비율의 모수가 대차대조표와 다른 것이다.
        FormCheck("배분 대출채권(총액) = 해외 여신잔액 실측",
                  ov_loan, _val(L, code_of["대출채권 (총액)"]), _tol(ov_loan)),
    ]
    return L, checks


# ---------------------------------------------------------------- BF202

def _bf202(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """대차대조표 각주계정 — 미사용약정·보증·파생·충당금은 전부 실측이다."""
    ob = overseas_book(ctx)
    gte = overseas_guarantee(ctx)
    drv = overseas_derivatives(ctx)
    coll = overseas_collateral(ctx)
    undrawn = float(ob["undrawn"].sum())
    L = [
        FormLine("1000", "미사용 약정 합계", 0, "KRW", undrawn,
                 formula=f"{_MEASURED} · 익스포저 {len(ob):,}건",
                 citation="Basel III CRE20.94 신용환산율", source_module=_M_RDM,
                 is_subtotal=True),
    ]
    ccf_codes = []
    ccf = (ob.assign(ccf_type=ob["ccf_type"].fillna("약정 없음"))
           .groupby("ccf_type", as_index=False)
           .agg(undrawn=("undrawn", "sum"), n=("exposure_id", "count"))
           .sort_values("ccf_type"))
    for i, (_, r) in enumerate(ccf.iterrows(), start=1):
        code = str(1000 + i * 10)
        ccf_codes.append(code)
        L.append(FormLine(code, f"약정유형 · {r['ccf_type']}", 1, "KRW",
                          float(r["undrawn"]), formula=f"{int(r['n']):,}건",
                          citation="Basel III CRE20.94", source_module=_M_RDM))

    g_total = float(gte["guaranteed_amount"].sum())
    g_elig = float(gte.loc[gte["eligible"], "guaranteed_amount"].sum())
    L += [
        FormLine("2000", "지급보증·신용파생 보장금액", 0, "KRW", g_total,
                 formula=f"보증 원장 {len(gte):,}건", citation=_CRE22,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("2010", "적격 보장금액", 1, "KRW", g_elig,
                 formula="만기·통화 불일치 없는 적격 보장", citation=_CRE22,
                 source_module=_M_RDM),
        FormLine("2020", "비적격 보장금액", 1, "KRW", g_total - g_elig,
                 formula="적격요건 미충족 — 위험경감 인식 불가", citation=_CRE22,
                 source_module=_M_RDM),
    ]
    d_total = float(drv["notional"].sum())
    L.append(FormLine("3000", "파생상품 명목금액", 0, "KRW", d_total,
                      formula=f"해외 거래상대방 {len(drv):,}거래",
                      citation="Basel III CRE52 SA-CCR", source_module=_M_MKT,
                      is_subtotal=True))
    kind_codes = []
    for i, (kind, sub) in enumerate(drv.groupby("kind"), start=1):
        code = str(3000 + i * 10)
        kind_codes.append(code)
        L.append(FormLine(code, f"거래유형 · {kind}", 1, "KRW",
                          float(sub["notional"].sum()),
                          formula=f"{len(sub):,}거래",
                          citation="Basel III CRE52", source_module=_M_MKT))

    min_p = float(ob["min_provision"].sum())
    ifrs_p = float(ob["ifrs9_provision"].sum())
    L += [
        FormLine("4000", "감독 최저적립액", 0, "KRW", min_p,
                 formula="분류단계별 최저적립률 × 잔액", citation=_C29,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("4010", "IFRS 9 대손충당금", 0, "KRW", ifrs_p,
                 formula="기대신용손실 모형 적립액", citation="IFRS 9 5.5",
                 source_module=_M_ECL, is_subtotal=True),
        FormLine("4020", "대손준비금 적립부족액", 0, "KRW",
                 float(ob["reserve_shortfall"].sum()),
                 formula="max(0, 최저적립액 − IFRS 9 충당금)", citation=_C29,
                 source_module=_M_RDM),
        FormLine("5000", "담보평가액", 0, "KRW", float(coll["appraised"].sum()),
                 formula="담보는 시가, 보증은 보장금액", citation=_CRE22,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("5010", "담보인정액", 1, "KRW", float(coll["recognized"].sum()),
                 formula="담보 = 시가 × (1 − 감독 haircut) · 보증 = 적격 보장금액",
                 citation=_CRE22, source_module=_M_RDM),
    ]
    t = _tol(max(undrawn, d_total, 1.0))
    checks = [
        _sum_check("약정유형별 합 = 미사용 약정 합계", L, "1000", tuple(ccf_codes), t),
        _sum_check("적격 + 비적격 = 보장금액", L, "2000", ("2010", "2020"), t),
        _sum_check("거래유형별 합 = 파생상품 명목금액", L, "3000", tuple(kind_codes), t),
        FormCheck("담보인정액 ≤ 담보평가액", 0.0,
                  max(0.0, float(coll["recognized"].sum())
                      - float(coll["appraised"].sum())), t),
    ]
    return L, checks


# ---------------------------------------------------------------- BF203

def _bf203(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """차주별 총여신 현황 — 차주 식별은 obligor_id로만 남긴다."""
    ob = overseas_book(ctx)
    total = float(ob["balance"].sum())
    by = (ob.groupby("obligor_id")
          .agg(balance=("balance", "sum"), n=("exposure_id", "count"),
               country=("country", "first"), sector=("sector", "first"),
               asset_class=("asset_class", "first"),
               npl=("npl", "any"))
          .reset_index().sort_values(["balance", "obligor_id"],
                                     ascending=[False, True]))
    top = by.head(_TOP_N)
    top_sum = float(top["balance"].sum())
    L = [
        FormLine("1000", "해외 총여신", 0, "KRW", total,
                 formula=f"차주 {len(by):,}개 · 익스포저 {len(ob):,}건 · {_MEASURED}",
                 citation=_C99, source_module=_M_RDM, is_subtotal=True),
        FormLine("1010", "차주 수", 0, "count", float(len(by)),
                 citation=_C99, source_module=_M_RDM),
        FormLine("2000", f"상위 {_TOP_N}개 차주 소계", 0, "KRW", top_sum,
                 formula="총여신 기준 내림차순", citation=_C99,
                 source_module=_M_RDM, is_subtotal=True),
    ]
    codes = []
    for i, (_, r) in enumerate(top.iterrows(), start=1):
        code = str(2000 + i * 10)
        codes.append(code)
        L.append(FormLine(code, str(r["obligor_id"]), 1, "KRW",
                          float(r["balance"]),
                          formula=(f"{r['country']} · {r['sector']} · "
                                   f"{r['asset_class']} · {int(r['n'])}건"
                                   + (" · 고정이하 포함" if bool(r["npl"]) else "")),
                          citation=_C99, source_module=_M_RDM))
    L += [
        FormLine("4000", "기타 차주 소계", 0, "KRW", total - top_sum,
                 formula=f"차주 {max(len(by) - len(top), 0):,}개",
                 citation=_C99, source_module=_M_RDM, is_subtotal=True),
        FormLine("4010", "상위 차주 집중도", 0, "ratio",
                 top_sum / total if total else 0.0,
                 formula=f"상위 {_TOP_N}개 소계 ÷ 해외 총여신",
                 citation="Basel SRP30 집중위험", source_module=_M_CON),
    ]
    t = _tol(total)
    return L, [
        _sum_check(f"상위 {_TOP_N}개 차주 합 = 소계", L, "2000", tuple(codes), t),
        _sum_check("상위 소계 + 기타 = 해외 총여신", L, "1000", ("2000", "4000"), t),
        _ratio_check("상위 차주 집중도 = 소계 ÷ 총여신", L, "4010", "2000", "1000"),
    ]


# ---------------------------------------------------------------- BF204

def _bf204(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """유가증권 종류별 명세 — 유가증권 원장이 없어 은행·국가 익스포저를 프록시로 쓴다."""
    sec = overseas_securities(ctx)
    total = float(sec["balance"].sum())
    L = [
        FormLine("1000", "유가증권 합계", 0, "KRW", total,
                 formula=f"{len(sec):,}종목 프록시 · 금액은 실측", citation=_C99,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("1010", "종목 수", 0, "count", float(len(sec)),
                 citation=_C99, source_module=_M_RDM),
    ]
    type_codes, type_cnt = [], []
    for i, (stype, sub) in enumerate(sec.groupby("security_type"), start=1):
        base = 2000 + i * 100
        type_codes.append(str(base))
        type_cnt.append(str(base + 10))
        w = float(sub["balance"].sum())
        L += [
            FormLine(str(base), f"종류 · {stype}", 1, "KRW", w,
                     formula=f"{len(sub):,}종목 · asset_class 프록시 매핑",
                     citation=_C99, source_module=_M_RDM, is_subtotal=True),
            FormLine(str(base + 10), "종목 수", 2, "count", float(len(sub)),
                     citation=_C99, source_module=_M_RDM),
            FormLine(str(base + 20), "잔존만기 가중평균", 2, "count",
                     float((sub["maturity"] * sub["balance"]).sum() / w)
                     if w else 0.0, formula="Σ(만기 × 잔액) ÷ Σ잔액",
                     citation=_C63, source_module=_M_PTF),
        ]
    mat_codes = []
    for i, (_, label) in enumerate(MATURITY_BANDS, start=1):
        code = str(3000 + i * 10)
        mat_codes.append(code)
        s = sec[sec["maturity_band"] == label]
        L.append(FormLine(code, f"잔존만기 · {label}", 1, "KRW",
                          float(s["balance"].sum()),
                          formula=f"{len(s):,}종목", citation=_C63,
                          source_module=_M_PTF))
    ctry_codes = []
    for i, country in enumerate(overseas_countries(ctx), start=1):
        code = str(4000 + i * 10)
        ctry_codes.append(code)
        s = sec[sec["country"] == country]
        L.append(FormLine(code, f"발행국 · {country}", 1, "KRW",
                          float(s["balance"].sum()),
                          formula=f"{len(s):,}종목 · {_MEASURED}", citation=_C99,
                          source_module=_M_RDM))
    L.append(FormLine("9000", "적용 범위 비고", 0, "text", None,
                      text_value=("유가증권 원장이 없어 국가(sovereign)·은행(bank) "
                                  "익스포저를 각각 국공채·금융채 보유로 보는 프록시를 "
                                  "쓴다. 금액·등급·잔존만기는 실측이며 '유가증권으로 "
                                  "본다'는 판단만 프록시다."),
                      citation=_C99, source_module=_M_DER))
    t = _tol(total)
    return L, [
        _sum_check("종류별 합 = 유가증권 합계", L, "1000", tuple(type_codes), t),
        _sum_check("잔존만기 구간별 합 = 유가증권 합계", L, "1000", tuple(mat_codes), t),
        _sum_check("발행국별 합 = 유가증권 합계", L, "1000", tuple(ctry_codes), t),
        # 금액 3축만 대사하고 건수를 빼면 프록시 매핑이 종목을 빠뜨려도 안 잡힌다.
        _sum_check("종류별 종목 수 합 = 종목 수", L, "1010", tuple(type_cnt), 1e-9),
    ]


# ---------------------------------------------------------------- BF301

def _bf301(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """자금조달·운용의 만기구조 — 재가격 갭을 해외 비중으로 배분한다."""
    gap = ctx.tables["alm_repricing_gap"].sort_values("seq")
    w = overseas_share(ctx)
    L = [
        FormLine("100", "해외분 배분비율", 0, "ratio", w,
                 formula="해외 EAD ÷ 전체 EAD — 비율은 실측, 구간별 배분은 파생",
                 citation=_C63, source_module=_M_DER),
    ]
    a_codes, l_codes, g_codes, checks = [], [], [], []
    prev_cum = None
    for i, (_, r) in enumerate(gap.iterrows(), start=1):
        base = 1000 + i * 100
        asset = float(r["asset"]) * w
        liab = float(r["liability"]) * w
        a_codes.append(str(base + 10))
        l_codes.append(str(base + 20))
        g_codes.append(str(base + 30))
        L += [
            FormLine(str(base), f"만기구간 · {r['bucket']}", 0, "text", None,
                     text_value=f"재가격 구간 {r['bucket']}",
                     citation=_SRP31, source_module=_M_ALM),
            FormLine(str(base + 10), "운용 (자산)", 1, "KRW", asset,
                     formula=f"본지점 합산 {float(r['asset']):,.0f}원 × {w:.6f} "
                             f"— {_DERIVED_ALLOC}",
                     citation=_SRP31, source_module=_M_ALM),
            FormLine(str(base + 20), "조달 (부채)", 1, "KRW", liab,
                     formula=f"본지점 합산 {float(r['liability']):,.0f}원 × {w:.6f} "
                             f"— {_DERIVED_ALLOC}",
                     citation=_SRP31, source_module=_M_ALM),
            FormLine(str(base + 30), "갭", 1, "KRW", asset - liab,
                     formula="운용 − 조달", citation=_SRP31, source_module=_M_ALM),
            FormLine(str(base + 40), "누적갭", 1, "KRW",
                     float(r["cumulative_gap"]) * w,
                     formula="직전 누적갭 + 당기 갭", citation=_SRP31,
                     source_module=_M_ALM),
        ]
        checks.append(_sum_check(f"{r['bucket']} 갭 = 운용 − 조달", L, str(base + 10),
                                 (str(base + 20), str(base + 30)),
                                 _tol(asset)))
        if prev_cum is None:
            checks.append(_sum_check(f"{r['bucket']} 누적갭 = 당기 갭", L,
                                     str(base + 40), (str(base + 30),),
                                     _tol(asset)))
        else:
            checks.append(_sum_check(f"{r['bucket']} 누적갭 = 직전 누적 + 당기 갭", L,
                                     str(base + 40), (prev_cum, str(base + 30)),
                                     _tol(asset)))
        prev_cum = str(base + 40)
    L += [
        FormLine("9000", "운용 합계", 0, "KRW", sum(_val(L, c) for c in a_codes),
                 formula="구간별 운용 합", citation=_SRP31, source_module=_M_ALM,
                 is_subtotal=True),
        FormLine("9010", "조달 합계", 0, "KRW", sum(_val(L, c) for c in l_codes),
                 formula="구간별 조달 합", citation=_SRP31, source_module=_M_ALM,
                 is_subtotal=True),
        FormLine("9020", "순갭", 0, "KRW",
                 sum(_val(L, c) for c in a_codes) - sum(_val(L, c) for c in l_codes),
                 formula="운용 합계 − 조달 합계", citation=_SRP31,
                 source_module=_M_ALM, is_subtotal=True),
    ]
    t = _tol(_val(L, "9000"))
    checks += [
        _sum_check("구간별 운용 합 = 운용 합계", L, "9000", tuple(a_codes), t),
        _sum_check("구간별 조달 합 = 조달 합계", L, "9010", tuple(l_codes), t),
        _sum_check("구간별 갭 합 = 순갭", L, "9020", tuple(g_codes), t),
        _sum_check("최종 누적갭 = 순갭", L, "9020", (prev_cum,), t),
    ]
    return L, checks


# ---------------------------------------------------------------- BF303

def _bf303(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """거액거래처별 Exposure 현황 — 거액 기준은 제53조의 자기자본 10%다."""
    ob = overseas_book(ctx)
    cap = ctx.result.meta["capital"]
    own_funds = float(cap.total)
    threshold = own_funds * 0.10
    total = float(ob["ead"].sum())
    by = (ob.groupby("obligor_id")
          .agg(ead=("ead", "sum"), n=("exposure_id", "count"),
               country=("country", "first"), sector=("sector", "first"),
               asset_class=("asset_class", "first"))
          .reset_index().sort_values(["ead", "obligor_id"],
                                     ascending=[False, True]))
    large = by[by["ead"] > threshold]
    top = by.head(_TOP_N)
    top_sum = float(top["ead"].sum())
    L = [
        FormLine("1000", "해외 총 Exposure", 0, "KRW", total,
                 formula=f"거래처 {len(by):,}개 · {_MEASURED}", citation=_C99,
                 source_module=_M_PTF, is_subtotal=True),
        FormLine("1010", "자기자본 (규제자본 합계)", 0, "KRW", own_funds,
                 formula="CET1 + AT1 + Tier2", citation=_C53,
                 source_module="risk_lib.capital.bis"),
        FormLine("1020", "거액여신 기준금액", 0, "KRW", threshold,
                 formula="자기자본 × 10%", citation=_C53,
                 source_module="risk_lib.capital.bis"),
        FormLine("2000", "거액거래처 수", 0, "count", float(len(large)),
                 formula="기준금액 초과 거래처", citation=_C53,
                 source_module=_M_CON, is_subtotal=True),
        FormLine("2010", "거액 Exposure 합계", 0, "KRW",
                 float(large["ead"].sum()), citation=_C53, source_module=_M_CON),
        FormLine("2020", "해외 총 Exposure 대비 비중", 0, "ratio",
                 float(large["ead"].sum()) / total if total else 0.0,
                 formula="거액 Exposure ÷ 해외 총 Exposure", citation=_C53,
                 source_module=_M_CON),
        FormLine("3000", f"상위 {_TOP_N}개 거래처 소계", 0, "KRW", top_sum,
                 formula="Exposure 기준 내림차순", citation=_C99,
                 source_module=_M_CON, is_subtotal=True),
    ]
    codes = []
    for i, (_, r) in enumerate(top.iterrows(), start=1):
        code = str(3000 + i * 10)
        codes.append(code)
        ratio = float(r["ead"]) / own_funds if own_funds else 0.0
        L.append(FormLine(code, str(r["obligor_id"]), 1, "KRW", float(r["ead"]),
                          formula=(f"{r['country']} · {r['sector']} · "
                                   f"{r['asset_class']} · {int(r['n'])}건 · "
                                   f"자기자본 대비 {ratio:.2%}"
                                   + (" · 거액" if float(r["ead"]) > threshold
                                      else "")),
                          citation=_C53, source_module=_M_CON))
    L.append(FormLine("4000", "기타 거래처 소계", 0, "KRW", total - top_sum,
                      formula=f"거래처 {max(len(by) - len(top), 0):,}개",
                      citation=_C99, source_module=_M_CON, is_subtotal=True))
    t = _tol(total)
    return L, [
        _sum_check(f"상위 {_TOP_N}개 거래처 합 = 소계", L, "3000", tuple(codes), t),
        _sum_check("상위 소계 + 기타 = 해외 총 Exposure", L, "1000",
                   ("3000", "4000"), t),
        _ratio_check("거액 비중 = 거액 Exposure ÷ 총 Exposure", L, "2020",
                     "2010", "1000"),
        FormCheck("거액 Exposure ≤ 해외 총 Exposure", 0.0,
                  max(0.0, float(large["ead"].sum()) - total), t),
    ]


# ---------------------------------------------------------------- BF304

def _bf304(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """국가별 Exposure 현황 — **국가별 합계는 포트폴리오 집계와 정확히 일치해야 한다.**

    점포 배분은 파생이지만 국가 집계는 실측이다. 이 서식이 그 경계를 지키는지
    검증하는 자리이므로 파생 프레임이 아니라 포트폴리오에서 직접 집계한다.
    """
    ce = country_exposure(ctx)
    total = float(ctx.portfolio["ead"].sum())
    home = float(ce.loc[ce["country"] == HOME_COUNTRY, "ead"].sum())
    L = [
        FormLine("1000", "총 Exposure", 0, "KRW", total,
                 formula=f"익스포저 {len(ctx.portfolio):,}건 · {_MEASURED}",
                 citation=_C99, source_module=_M_PTF, is_subtotal=True),
        FormLine("1010", f"국내 ({HOME_COUNTRY})", 1, "KRW", home,
                 formula=_MEASURED, citation=_C99, source_module=_M_PTF),
        FormLine("1020", "해외 소계", 1, "KRW", total - home,
                 formula="총 Exposure − 국내", citation=_C99,
                 source_module=_M_PTF, is_subtotal=True),
    ]
    all_codes, ov_codes, ratios = [], [], []
    for i, (_, r) in enumerate(ce.iterrows(), start=1):
        base = 2000 + i * 100
        country = str(r["country"])
        all_codes.append(str(base))
        if country != HOME_COUNTRY:
            ov_codes.append(str(base))
        ratios.append((country, str(base + 20), str(base), "1000"))
        L += [
            FormLine(str(base), f"국가 · {country}", 1, "KRW", float(r["ead"]),
                     formula=f"{int(r['n']):,}건 · {_MEASURED}", citation=_C99,
                     source_module=_M_PTF, is_subtotal=True),
            FormLine(str(base + 10), "익스포저 건수", 2, "count", float(r["n"]),
                     citation=_C99, source_module=_M_PTF),
            FormLine(str(base + 20), "총 Exposure 대비 비중", 2, "ratio",
                     float(r["ead"]) / total if total else 0.0,
                     formula="국가별 Exposure ÷ 총 Exposure", citation=_C99,
                     source_module=_M_PTF),
            FormLine(str(base + 30), "고정이하여신", 2, "KRW", float(r["npl"]),
                     formula="고정·회수의문·추정손실 잔액", citation=_C27,
                     source_module=_M_RDM),
            FormLine(str(base + 40), "대손충당금", 2, "KRW",
                     float(r["provision"]), citation="IFRS 9 5.5",
                     source_module=_M_ECL),
        ]
    L.append(FormLine("9000", "국가 집중도 (HHI)", 0, "ratio",
                      float(ctx.result.concentration.set_index("dimension")
                            .loc["country", "hhi"]),
                      formula="Σ(국가별 비중²)", citation="Basel SRP30 집중위험",
                      source_module=_M_CON))
    t = _tol(total)
    return L, [
        _sum_check("국가별 Exposure 합 = 총 Exposure (포트폴리오 집계 일치)", L,
                   "1000", tuple(all_codes), t),
        _sum_check("국내 + 해외 소계 = 총 Exposure", L, "1000", ("1010", "1020"), t),
        _sum_check("해외 국가별 합 = 해외 소계", L, "1020", tuple(ov_codes), t),
        # HHI는 `result.concentration`에서 그대로 끌어온다. 서식의 국가별 비중과
        # 어긋나면 이 서식과 산출 집계가 다른 모수를 본 것이다.
        FormCheck("국가 집중도 HHI = Σ(국가별 비중²)",
                  sum(_val(L, rc) ** 2 for _, rc, _, _ in ratios),
                  _val(L, "9000"), 1e-9),
    ] + [
        _ratio_check(f"{c} 비중 = 국가별 ÷ 총계", L, rc, nc, dc)
        for c, rc, nc, dc in ratios
    ]


# ---------------------------------------------------------------- BF306

def _bf306(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """신용등급별 유가증권 투자현황 — 등급은 원장 rating, 유가증권 판단만 프록시다."""
    sec = overseas_securities(ctx).copy()
    sec["grade"] = [_grade(str(v)) for v in sec["rating"]]
    total = float(sec["balance"].sum())
    ig = float(sec.loc[sec["grade"].isin(INVESTMENT_GRADE), "balance"].sum())
    L = [
        FormLine("1000", "유가증권 투자 합계", 0, "KRW", total,
                 formula=f"{len(sec):,}종목 프록시 · 금액·등급은 실측",
                 citation=_C99, source_module=_M_RDM, is_subtotal=True),
        FormLine("1010", "투자등급 (BBB 이상)", 1, "KRW", ig,
                 formula="AAA-AA · A · BBB", citation="Basel III CRE20 외부등급",
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("1020", "투자등급 미만·무등급", 1, "KRW", total - ig,
                 formula="BB 이하 및 무등급", citation="Basel III CRE20",
                 source_module=_M_RDM, is_subtotal=True),
    ]
    codes, ratios = [], []
    for i, grade in enumerate(RATING_ORDER, start=1):
        base = 2000 + i * 100
        s = sec[sec["grade"] == grade]
        bal = float(s["balance"].sum())
        codes.append(str(base))
        ratios.append((grade, str(base + 20), str(base), "1000"))
        L += [
            FormLine(str(base), f"신용등급 · {grade}", 1, "KRW", bal,
                     formula=f"{len(s):,}종목", citation="Basel III CRE20 외부등급",
                     source_module=_M_RDM, is_subtotal=True),
            FormLine(str(base + 10), "종목 수", 2, "count", float(len(s)),
                     citation=_C99, source_module=_M_RDM),
            FormLine(str(base + 20), "합계 대비 비중", 2, "ratio",
                     bal / total if total else 0.0,
                     formula="등급별 잔액 ÷ 유가증권 합계", citation=_C99,
                     source_module=_M_RDM),
        ]
    L.append(FormLine("9000", "적용 범위 비고", 0, "text", None,
                      text_value=("유가증권 원장이 없어 국가·은행 익스포저를 프록시로 "
                                  "쓴다. 신용등급은 `rdm_exposure.rating` 원장값이며 "
                                  "파생이 아니다."),
                      citation=_C99, source_module=_M_DER))
    t = _tol(total)
    return L, [
        _sum_check("등급별 합 = 유가증권 투자 합계", L, "1000", tuple(codes), t),
        _sum_check("투자등급 + 투자등급 미만 = 합계", L, "1000", ("1010", "1020"), t),
    ] + [
        _ratio_check(f"{g} 비중 = 등급별 ÷ 합계", L, rc, nc, dc)
        for g, rc, nc, dc in ratios
    ]


# ---------------------------------------------------------------- BF401

def _bf401(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """여신건전성 분류 현황 — 해외 익스포저로 거른 `rdm_asset_quality`다."""
    ob = overseas_book(ctx)
    total = float(ob["balance"].sum())
    npl = float(ob[ob["npl"]]["balance"].sum())
    L = [
        FormLine("1000", "해외 총여신", 0, "KRW", total,
                 formula=f"익스포저 {len(ob):,}건 · {_MEASURED}", citation=_C27,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("1010", "익스포저 건수", 0, "count", float(len(ob)),
                 citation=_C99, source_module=_M_RDM),
    ]
    cls_lines, cls_codes = _class_block(ob, 2000)
    L += cls_lines
    npl_codes = tuple(cls_codes[AQ_ORDER.index(c)] for c in NPL_CLASSES)
    for i, cls in enumerate(AQ_ORDER, start=1):
        s = ob[ob["classification"] == cls]
        base = 3000 + i * 100
        rate = (float(s["min_provision_rate"].max()) if len(s) else 0.0)
        L += [
            FormLine(str(base), f"{cls} · 건수", 1, "count", float(len(s)),
                     citation=_C27, source_module=_M_RDM),
            FormLine(str(base + 10), f"{cls} · 최저적립률", 1, "ratio", rate,
                     formula="분류단계별 감독 최저적립률 (해당 없으면 0)",
                     citation=_C29, source_module=_M_RDM),
            FormLine(str(base + 20), f"{cls} · 최저적립액", 1, "KRW",
                     float(s["min_provision"].sum()), citation=_C29,
                     source_module=_M_RDM),
            FormLine(str(base + 30), f"{cls} · IFRS 9 충당금", 1, "KRW",
                     float(s["ifrs9_provision"].sum()), citation="IFRS 9 5.5",
                     source_module=_M_ECL),
        ]
    L += [
        FormLine("8000", "고정이하여신", 0, "KRW", npl,
                 formula="고정 + 회수의문 + 추정손실", citation=_C27,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("8010", "고정이하여신비율", 0, "ratio",
                 npl / total if total else 0.0,
                 formula="고정이하여신 ÷ 해외 총여신", citation=_C27,
                 source_module=_M_RDM),
    ]
    t = _tol(total)
    return L, [
        _sum_check("분류단계별 합 = 해외 총여신", L, "1000", cls_codes, t),
        _sum_check("고정이하여신 = 고정 + 회수의문 + 추정손실", L, "8000", npl_codes, t),
        _ratio_check("고정이하여신비율 = 고정이하 ÷ 총여신", L, "8010", "8000", "1000"),
    ]


# ---------------------------------------------------------------- BF404

def _bf404(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """연체대출채권현황 — 연체일수는 `rdm_delinquency` 산출값이다."""
    ob = overseas_book(ctx)
    total = float(ob["balance"].sum())
    od = ob[ob["dpd"] > 0]
    od_bal = float(od["balance"].sum())
    L = [
        FormLine("1000", "해외 총여신", 0, "KRW", total,
                 formula=f"익스포저 {len(ob):,}건 · {_MEASURED}", citation=_C99,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("1010", "연체대출채권", 0, "KRW", od_bal,
                 formula=f"연체일수 1일 이상 {len(od):,}건", citation=_C27,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("1020", "연체비율", 0, "ratio", od_bal / total if total else 0.0,
                 formula="연체대출채권 ÷ 해외 총여신", citation=_C27,
                 source_module=_M_RDM),
    ]
    codes = []
    for i, (_, label) in enumerate(DPD_BANDS, start=1):
        base = 2000 + i * 100
        s = od[od["dpd_band"] == label]
        codes.append(str(base))
        L += [
            FormLine(str(base), f"연체기간 · {label}", 1, "KRW",
                     float(s["balance"].sum()), formula=f"{len(s):,}건",
                     citation=_C27, source_module=_M_RDM, is_subtotal=True),
            FormLine(str(base + 10), "건수", 2, "count", float(len(s)),
                     citation=_C99, source_module=_M_RDM),
            FormLine(str(base + 20), "대손충당금", 2, "KRW",
                     float(s["ifrs9_provision"].sum()), citation="IFRS 9 5.5",
                     source_module=_M_ECL),
        ]
    over90 = od[od["dpd"] > 90]
    L += [
        FormLine("8000", "90일 초과 연체채권", 0, "KRW",
                 float(over90["balance"].sum()),
                 formula=f"{len(over90):,}건 — 채무불이행 판정 기준",
                 citation="Basel III CRE36.69 채무불이행 정의",
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("8010", "90일 초과 연체비율", 0, "ratio",
                 float(over90["balance"].sum()) / total if total else 0.0,
                 formula="90일 초과 연체채권 ÷ 해외 총여신",
                 citation="Basel III CRE36.69", source_module=_M_RDM),
    ]
    ctry_codes = []
    for i, country in enumerate(overseas_countries(ctx), start=1):
        code = str(9000 + i * 10)
        ctry_codes.append(code)
        s = od[od["country"] == country]
        L.append(FormLine(code, f"소재국 · {country} 연체채권", 1, "KRW",
                          float(s["balance"].sum()),
                          formula=f"{len(s):,}건 · {_MEASURED}", citation=_C27,
                          source_module=_M_RDM))
    t = _tol(max(od_bal, 1.0))
    return L, [
        _sum_check("연체기간 구간별 합 = 연체대출채권", L, "1010", tuple(codes), t),
        _sum_check("소재국별 연체채권 합 = 연체대출채권", L, "1010",
                   tuple(ctry_codes), t),
        _ratio_check("연체비율 = 연체채권 ÷ 총여신", L, "1020", "1010", "1000"),
        _ratio_check("90일 초과 연체비율", L, "8010", "8000", "1000"),
        FormCheck("90일 초과 연체채권 ≤ 연체대출채권", 0.0,
                  max(0.0, float(over90["balance"].sum()) - od_bal), t),
    ]


# ---------------------------------------------------------------- BF405

def _bf405(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """대손충당금 적립현황 — 감독 최저적립액과 IFRS 9 충당금을 나란히 낸다."""
    ob = overseas_book(ctx)
    total = float(ob["balance"].sum())
    min_p = float(ob["min_provision"].sum())
    ifrs_p = float(ob["ifrs9_provision"].sum())
    L = [
        FormLine("1000", "해외 총여신", 0, "KRW", total,
                 formula=f"익스포저 {len(ob):,}건 · {_MEASURED}", citation=_C99,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("1010", "감독 최저적립액", 0, "KRW", min_p,
                 formula="Σ(분류단계 최저적립률 × 잔액)", citation=_C29,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("1020", "IFRS 9 대손충당금", 0, "KRW", ifrs_p,
                 formula="기대신용손실 모형 적립액", citation="IFRS 9 5.5",
                 source_module=_M_ECL, is_subtotal=True),
        FormLine("1030", "대손준비금 적립부족액", 0, "KRW",
                 float(ob["reserve_shortfall"].sum()),
                 formula="Σ max(0, 최저적립액 − IFRS 9 충당금) — 익스포저별 산출",
                 citation=_C29, source_module=_M_RDM, is_subtotal=True),
        FormLine("1040", "ECL 산출액 (참고)", 0, "KRW", float(ob["ecl"].sum()),
                 formula="`ecl_result` 기준 — 은행·국가 익스포저는 ECL 모형 "
                         "대상이 아니어서 IFRS 9 충당금 합계와 모수가 다르다",
                 citation="IFRS 9 5.5", source_module=_M_ECL),
    ]
    bal_codes, min_codes, ifrs_codes, sf_codes = [], [], [], []
    for i, cls in enumerate(AQ_ORDER, start=1):
        base = 2000 + i * 100
        s = ob[ob["classification"] == cls]
        bal_codes.append(str(base))
        min_codes.append(str(base + 10))
        ifrs_codes.append(str(base + 20))
        sf_codes.append(str(base + 30))
        bal = float(s["balance"].sum())
        L += [
            FormLine(str(base), f"분류 · {cls} 잔액", 1, "KRW", bal,
                     formula=f"{len(s):,}건", citation=_C27, source_module=_M_RDM,
                     is_subtotal=True),
            FormLine(str(base + 10), "감독 최저적립액", 2, "KRW",
                     float(s["min_provision"].sum()), citation=_C29,
                     source_module=_M_RDM),
            FormLine(str(base + 20), "IFRS 9 충당금", 2, "KRW",
                     float(s["ifrs9_provision"].sum()), citation="IFRS 9 5.5",
                     source_module=_M_ECL),
            FormLine(str(base + 30), "적립부족액", 2, "KRW",
                     float(s["reserve_shortfall"].sum()), citation=_C29,
                     source_module=_M_RDM),
            FormLine(str(base + 40), "잔액 대비 적립률", 2, "ratio",
                     float(s["ifrs9_provision"].sum()) / bal if bal else 0.0,
                     formula="IFRS 9 충당금 ÷ 분류별 잔액", citation="IFRS 9 5.5",
                     source_module=_M_ECL),
        ]
    L.append(FormLine("8000", "총여신 대비 적립률", 0, "ratio",
                      ifrs_p / total if total else 0.0,
                      formula="IFRS 9 충당금 ÷ 해외 총여신", citation="IFRS 9 5.5",
                      source_module=_M_ECL))
    t = _tol(max(min_p, ifrs_p, 1.0))
    return L, [
        # 적립액 3열의 모수인 잔액 열을 대사하지 않으면 분류 필터가 익스포저를
        # 빠뜨려도 적립률(base+40) 분모만 조용히 작아진다.
        _sum_check("분류별 잔액 합 = 해외 총여신", L, "1000", tuple(bal_codes),
                   _tol(total)),
        _sum_check("분류별 최저적립액 합 = 합계", L, "1010", tuple(min_codes), t),
        _sum_check("분류별 IFRS 9 충당금 합 = 합계", L, "1020", tuple(ifrs_codes), t),
        _sum_check("분류별 적립부족액 합 = 합계", L, "1030", tuple(sf_codes), t),
        _ratio_check("총여신 대비 적립률", L, "8000", "1020", "1000"),
    ]


# ---------------------------------------------------------------- BF406

def _bf406(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """거액고정이하 분류여신(100만달러이상) — **달러 환산은 환율 가정에 걸린다.**

    원장에 익스포저 통화가 없어 `overseas_data.USD_KRW` 단일 환율을 가정한다.
    이 값이 바뀌면 기준 이상/미만 구분이 통째로 바뀐다.
    """
    ob = overseas_book(ctx)
    npl = ob[ob["npl"]]
    npl_total = float(npl["balance"].sum())
    threshold = LARGE_NPL_USD * USD_KRW
    big = npl[npl["balance"] >= threshold].sort_values(
        ["balance", "exposure_id"], ascending=[False, True])
    big_sum = float(big["balance"].sum())
    L = [
        FormLine("1000", "해외 고정이하여신 합계", 0, "KRW", npl_total,
                 formula=f"고정·회수의문·추정손실 {len(npl):,}건", citation=_C27,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("1010", "적용 환율 (KRW/USD)", 0, "count", USD_KRW,
                 formula="**가정치** — 원장에 통화·환율이 없어 단일 환율을 쓴다",
                 citation=_C99, source_module=_M_DER),
        FormLine("1020", "기재 기준금액", 0, "KRW", threshold,
                 formula=f"USD {LARGE_NPL_USD:,.0f} × {USD_KRW:,.0f}",
                 citation=_C99, source_module=_M_DER),
        FormLine("2000", "기준 이상 건수", 0, "count", float(len(big)),
                 citation=_C99, source_module=_M_RDM, is_subtotal=True),
        FormLine("2010", "기준 이상 잔액", 0, "KRW", big_sum,
                 citation=_C27, source_module=_M_RDM, is_subtotal=True),
        FormLine("2020", "기준 미만 잔액", 0, "KRW", npl_total - big_sum,
                 formula=f"{len(npl) - len(big):,}건", citation=_C27,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("2030", "기준 이상 비중", 0, "ratio",
                 big_sum / npl_total if npl_total else 0.0,
                 formula="기준 이상 잔액 ÷ 고정이하여신 합계", citation=_C99,
                 source_module=_M_RDM),
    ]
    codes = []
    for i, (_, r) in enumerate(big.head(_TOP_N).iterrows(), start=1):
        code = str(3000 + i * 10)
        codes.append(code)
        L.append(FormLine(
            code, f"{r['obligor_id']} / {r['exposure_id']}", 1, "KRW",
            float(r["balance"]),
            formula=(f"{r['country']} · {r['branch_name']}(점포 귀속은 {_DERIVED}) "
                     f"· {r['sector']} · {r['classification']} · 연체 "
                     f"{int(r['dpd'])}일 · USD {float(r['balance']) / USD_KRW:,.0f}"),
            citation=_C27, source_module=_M_RDM))
    listed = sum(_val(L, c) for c in codes)
    L.append(FormLine("4000", f"기재분({len(codes)}건) 외 기준 이상 잔액", 0, "KRW",
                      big_sum - listed,
                      formula=f"기준 이상 {len(big):,}건 중 상위 {len(codes):,}건만 "
                              f"개별 기재", citation=_C99, source_module=_M_RDM,
                      is_subtotal=True))
    t = _tol(max(npl_total, 1.0))
    return L, [
        _sum_check("기준 이상 + 기준 미만 = 고정이하여신 합계", L, "1000",
                   ("2010", "2020"), t),
        _sum_check("개별 기재분 + 잔여 = 기준 이상 잔액", L, "2010",
                   tuple(codes) + ("4000",), t),
        _ratio_check("기준 이상 비중", L, "2030", "2010", "1000"),
    ]


# ---------------------------------------------------------------- BF408

def _bf408(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """고정이하여신비율 — 소재국별·점포형태별로 나눈다."""
    ob = overseas_book(ctx)
    total = float(ob["balance"].sum())
    npl = float(ob[ob["npl"]]["balance"].sum())
    L = [
        FormLine("1000", "해외 총여신", 0, "KRW", total,
                 formula=f"익스포저 {len(ob):,}건 · {_MEASURED}", citation=_C27,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("1010", "고정이하여신", 0, "KRW", npl,
                 formula="고정 + 회수의문 + 추정손실", citation=_C27,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("1020", "고정이하여신비율", 0, "ratio",
                 npl / total if total else 0.0,
                 formula="고정이하여신 ÷ 해외 총여신", citation=_C27,
                 source_module=_M_RDM),
    ]
    checks, bal_c, npl_c = [], [], []
    for i, country in enumerate(overseas_countries(ctx), start=1):
        base = 2000 + i * 100
        s = ob[ob["country"] == country]
        b, n = float(s["balance"].sum()), float(s[s["npl"]]["balance"].sum())
        bal_c.append(str(base))
        npl_c.append(str(base + 10))
        L += [
            FormLine(str(base), f"소재국 · {country} 총여신", 1, "KRW", b,
                     formula=f"{len(s):,}건 · {_MEASURED}", citation=_C99,
                     source_module=_M_RDM, is_subtotal=True),
            FormLine(str(base + 10), "고정이하여신", 2, "KRW", n,
                     citation=_C27, source_module=_M_RDM),
            FormLine(str(base + 20), "고정이하여신비율", 2, "ratio",
                     n / b if b else 0.0, formula="고정이하 ÷ 총여신",
                     citation=_C27, source_module=_M_RDM),
        ]
        checks.append(_ratio_check(f"{country} 고정이하여신비율", L,
                                   str(base + 20), str(base + 10), str(base)))
    kbal_c, knpl_c = [], []
    for i, kind in enumerate(BRANCH_KINDS, start=1):
        base = 3000 + i * 100
        s = ob[ob["branch_kind"] == kind]
        b, n = float(s["balance"].sum()), float(s[s["npl"]]["balance"].sum())
        kbal_c.append(str(base))
        knpl_c.append(str(base + 10))
        L += [
            FormLine(str(base), f"점포형태 · {kind} 총여신", 1, "KRW", b,
                     formula=f"{len(s):,}건 · 점포 귀속은 {_DERIVED}",
                     citation=_C99, source_module=_M_DER, is_subtotal=True),
            FormLine(str(base + 10), "고정이하여신", 2, "KRW", n,
                     formula=f"금액은 실측 · 형태 분할은 {_DERIVED}",
                     citation=_C27, source_module=_M_DER),
            FormLine(str(base + 20), "고정이하여신비율", 2, "ratio",
                     n / b if b else 0.0,
                     formula=f"고정이하 ÷ 총여신 · 형태 분할은 {_DERIVED}",
                     citation=_C27, source_module=_M_DER),
        ]
        checks.append(_ratio_check(f"{kind} 고정이하여신비율", L, str(base + 20),
                                   str(base + 10), str(base)))
    t = _tol(total)
    checks += [
        _sum_check("소재국별 총여신 합 = 해외 총여신", L, "1000", tuple(bal_c), t),
        _sum_check("소재국별 고정이하 합 = 고정이하여신", L, "1010", tuple(npl_c), t),
        _sum_check("점포형태별 총여신 합 = 해외 총여신", L, "1000", tuple(kbal_c), t),
        _sum_check("점포형태별 고정이하 합 = 고정이하여신", L, "1010", tuple(knpl_c), t),
        _ratio_check("고정이하여신비율 = 고정이하 ÷ 총여신", L, "1020", "1010", "1000"),
    ]
    return L, checks


# ---------------------------------------------------------------- BF409

def _bf409(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """대손충당금적립률 — 총여신 대비·고정이하 대비·감독 최저 대비 셋을 낸다."""
    ob = overseas_book(ctx)
    total = float(ob["balance"].sum())
    npl = float(ob[ob["npl"]]["balance"].sum())
    ifrs_p = float(ob["ifrs9_provision"].sum())
    min_p = float(ob["min_provision"].sum())
    L = [
        FormLine("1000", "해외 총여신", 0, "KRW", total,
                 formula=f"익스포저 {len(ob):,}건 · {_MEASURED}", citation=_C99,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("1010", "IFRS 9 대손충당금", 0, "KRW", ifrs_p,
                 citation="IFRS 9 5.5", source_module=_M_ECL, is_subtotal=True),
        FormLine("1020", "총여신 대비 적립률", 0, "ratio",
                 ifrs_p / total if total else 0.0,
                 formula="대손충당금 ÷ 해외 총여신", citation="IFRS 9 5.5",
                 source_module=_M_ECL),
        FormLine("2000", "고정이하여신", 0, "KRW", npl,
                 formula="고정 + 회수의문 + 추정손실", citation=_C27,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("2010", "고정이하여신 대비 적립률", 0, "ratio",
                 ifrs_p / npl if npl else 0.0,
                 formula="대손충당금 ÷ 고정이하여신 (NPL 커버리지)",
                 citation=_C29, source_module=_M_ECL),
        FormLine("3000", "감독 최저적립액", 0, "KRW", min_p,
                 formula="Σ(분류단계 최저적립률 × 잔액)", citation=_C29,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("3010", "감독 최저 대비 이행률", 0, "ratio",
                 ifrs_p / min_p if min_p else 0.0,
                 formula="대손충당금 ÷ 감독 최저적립액 — 1 미만이면 대손준비금 적립",
                 citation=_C29, source_module=_M_RDM),
    ]
    ratios, bal_c, prov_c = [], [], []
    for i, country in enumerate(overseas_countries(ctx), start=1):
        base = 4000 + i * 100
        s = ob[ob["country"] == country]
        b = float(s["balance"].sum())
        p = float(s["ifrs9_provision"].sum())
        bal_c.append(str(base))
        prov_c.append(str(base + 10))
        L += [
            FormLine(str(base), f"소재국 · {country} 총여신", 1, "KRW", b,
                     formula=f"{len(s):,}건 · {_MEASURED}", citation=_C99,
                     source_module=_M_RDM, is_subtotal=True),
            FormLine(str(base + 10), "대손충당금", 2, "KRW", p,
                     citation="IFRS 9 5.5", source_module=_M_ECL),
            FormLine(str(base + 20), "적립률", 2, "ratio", p / b if b else 0.0,
                     formula="대손충당금 ÷ 총여신", citation="IFRS 9 5.5",
                     source_module=_M_ECL),
        ]
        ratios.append((country, str(base + 20), str(base + 10), str(base)))
    t = _tol(total)
    checks = [
        _ratio_check("총여신 대비 적립률", L, "1020", "1010", "1000"),
        _ratio_check("고정이하여신 대비 적립률", L, "2010", "1010", "2000"),
        _ratio_check("감독 최저 대비 이행률", L, "3010", "1010", "3000"),
        # 국가 루프의 모수가 상단 합계와 같은지 대사한다 — 비율만 걸어 두면
        # 국가별 분모·분자가 함께 빠져도 비율은 맞아 보인다.
        _sum_check("소재국별 총여신 합 = 해외 총여신", L, "1000", tuple(bal_c), t),
        _sum_check("소재국별 대손충당금 합 = IFRS 9 대손충당금", L, "1010",
                   tuple(prov_c), t),
    ] + [
        _ratio_check(f"{c} 적립률", L, rc, nc, dc) for c, rc, nc, dc in ratios
    ]
    return L, checks


# ---------------------------------------------------------------- BF410

def _bf410(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """업종별 대출금의 건전성 분류 현황 — 업종은 원장 sector다."""
    ob = overseas_book(ctx)
    total = float(ob["balance"].sum())
    npl = float(ob[ob["npl"]]["balance"].sum())
    L = [
        FormLine("1000", "해외 총여신", 0, "KRW", total,
                 formula=f"익스포저 {len(ob):,}건 · {_MEASURED}", citation=_C27,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("1010", "고정이하여신", 0, "KRW", npl,
                 formula="고정 + 회수의문 + 추정손실", citation=_C27,
                 source_module=_M_RDM, is_subtotal=True),
    ]
    sectors = tuple(sorted(ob["sector"].unique()))
    checks, bal_c, npl_c = [], [], []
    for i, sector in enumerate(sectors, start=1):
        base = 2000 + i * 100
        s = ob[ob["sector"] == sector]
        b = float(s["balance"].sum())
        n = float(s[s["npl"]]["balance"].sum())
        normal = float(s[s["classification"] == "정상"]["balance"].sum())
        watch = float(s[s["classification"] == "요주의"]["balance"].sum())
        bal_c.append(str(base))
        npl_c.append(str(base + 30))
        L += [
            FormLine(str(base), f"업종 · {sector}", 1, "KRW", b,
                     formula=f"{len(s):,}건 · {_MEASURED}", citation=_C99,
                     source_module=_M_RDM, is_subtotal=True),
            FormLine(str(base + 10), "정상", 2, "KRW", normal, citation=_C27,
                     source_module=_M_RDM),
            FormLine(str(base + 20), "요주의", 2, "KRW", watch, citation=_C27,
                     source_module=_M_RDM),
            FormLine(str(base + 30), "고정이하", 2, "KRW", n, citation=_C27,
                     source_module=_M_RDM),
            FormLine(str(base + 40), "고정이하여신비율", 2, "ratio",
                     n / b if b else 0.0, formula="고정이하 ÷ 업종별 잔액",
                     citation=_C27, source_module=_M_RDM),
            FormLine(str(base + 50), "대손충당금", 2, "KRW",
                     float(s["ifrs9_provision"].sum()), citation="IFRS 9 5.5",
                     source_module=_M_ECL),
        ]
        checks += [
            _sum_check(f"{sector} 정상+요주의+고정이하 = 업종 잔액", L, str(base),
                       (str(base + 10), str(base + 20), str(base + 30)),
                       _tol(max(b, 1.0))),
            _ratio_check(f"{sector} 고정이하여신비율", L, str(base + 40),
                         str(base + 30), str(base)),
        ]
    t = _tol(total)
    checks += [
        _sum_check("업종별 잔액 합 = 해외 총여신", L, "1000", tuple(bal_c), t),
        _sum_check("업종별 고정이하 합 = 고정이하여신", L, "1010", tuple(npl_c), t),
    ]
    return L, checks


# ---------------------------------------------------------------- BF412

def _bf412(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """담보별 대출금 현황 — 담보구분은 담보·보증 원장에서 온다 (파생 아님)."""
    cb = overseas_collateral(ctx)
    total = float(cb["balance"].sum())
    app = float(cb["appraised"].sum())
    rec = float(cb["recognized"].sum())
    unsec = float(cb[cb["bucket"] == "신용(무담보)"]["balance"].sum())
    L = [
        FormLine("1000", "해외 총 대출금", 0, "KRW", total,
                 formula=f"익스포저 {len(cb):,}건 · {_MEASURED}", citation=_C99,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("1010", "담보·보증부 대출금", 1, "KRW", total - unsec,
                 formula="담보 원장 또는 보증 원장이 있는 익스포저", citation=_CRE22,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("1020", "신용(무담보) 대출금", 1, "KRW", unsec, citation=_CRE22,
                 source_module=_M_RDM),
        FormLine("1100", "담보평가액 합계", 0, "KRW", app,
                 formula="담보는 시가, 보증은 보장금액", citation=_CRE22,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("1110", "담보인정액 합계", 0, "KRW", rec,
                 formula="담보 = 시가 × (1 − 감독 haircut) · 보증 = 적격 보장금액",
                 citation=_CRE22, source_module=_M_RDM, is_subtotal=True),
        FormLine("1120", "담보인정비율", 0, "ratio", rec / total if total else 0.0,
                 formula="담보인정액 ÷ 해외 총 대출금", citation=_CRE22,
                 source_module=_M_RDM),
    ]
    bal, apps, recs, sec, ratios = [], [], [], [], []
    for i, b in enumerate(COLLATERAL_BUCKETS, start=1):
        base = 2000 + i * 100
        s = cb[cb["bucket"] == b]
        bal.append(str(base))
        apps.append(str(base + 20))
        recs.append(str(base + 30))
        ratios.append((b, str(base + 40), str(base + 20), str(base)))
        if b != "신용(무담보)":
            sec.append(str(base))
        sb = float(s["balance"].sum())
        sa = float(s["appraised"].sum())
        L += [
            FormLine(str(base), f"담보구분 · {b}", 1, "KRW", sb,
                     formula=f"{len(s):,}건", citation=_CRE22,
                     source_module=_M_RDM, is_subtotal=True),
            FormLine(str(base + 10), "건수", 2, "count", float(len(s)),
                     citation=_C99, source_module=_M_RDM),
            FormLine(str(base + 20), "담보평가액", 2, "KRW", sa, citation=_CRE22,
                     source_module=_M_RDM),
            FormLine(str(base + 30), "담보인정액", 2, "KRW",
                     float(s["recognized"].sum()), citation=_CRE22,
                     source_module=_M_RDM),
            FormLine(str(base + 40), "잔액 대비 담보평가액", 2, "ratio",
                     sa / sb if sb else 0.0, formula="담보평가액 ÷ 잔액",
                     citation=_CRE22, source_module=_M_RDM),
        ]
    ctry_codes = []
    for i, country in enumerate(overseas_countries(ctx), start=1):
        code = str(4000 + i * 10)
        ctry_codes.append(code)
        s = cb[cb["country"] == country]
        L.append(FormLine(code, f"소재국 · {country} 대출금", 1, "KRW",
                          float(s["balance"].sum()),
                          formula=f"{len(s):,}건 · {_MEASURED}", citation=_C99,
                          source_module=_M_RDM))
    t = _tol(total)
    return L, [
        _sum_check("담보구분별 잔액 합 = 해외 총 대출금", L, "1000", tuple(bal), t),
        _sum_check("담보·보증부 = 신용 외 담보구분 합", L, "1010", tuple(sec), t),
        _sum_check("담보·보증부 + 신용 = 총 대출금", L, "1000", ("1010", "1020"), t),
        _sum_check("담보구분별 평가액 합 = 합계", L, "1100", tuple(apps), t),
        _sum_check("담보구분별 인정액 합 = 합계", L, "1110", tuple(recs), t),
        _sum_check("소재국별 대출금 합 = 해외 총 대출금", L, "1000",
                   tuple(ctry_codes), t),
        _ratio_check("담보인정비율 = 인정액 ÷ 총 대출금", L, "1120", "1110", "1000"),
        FormCheck("담보인정액 ≤ 담보평가액", 0.0, max(0.0, rec - app), t),
    ] + [
        _ratio_check(f"{b} 잔액 대비 담보평가액", L, rc, ac, bc)
        for b, rc, ac, bc in ratios
    ]


# ---------------------------------------------------------------- 등록

BUILDERS: dict[str, tuple[str, str, Callable]] = {
    "BF101": ("은행업감독규정 제99조 업무보고서", "PRD-RDM", _bf101),
    "BF103": ("은행업감독규정 제99조 업무보고서", "PRD-RDM", _bf103),
    "BF104": ("은행업감독규정 제99조 업무보고서", "PRD-RDM", _bf104),
    "BF201": ("은행업감독규정 제99조 업무보고서", "PRD-RDM", _bf201),
    "BF202": ("은행업감독규정 제29조 · Basel III CRE20.94 · CRE22", "PRD-RDM",
              _bf202),
    "BF203": ("은행업감독규정 제99조 · 제53조 거액여신", "PRD-RDM", _bf203),
    "BF204": ("은행업감독규정 제63조 외화유동성 · Basel III CRE20", "PRD-RDM",
              _bf204),
    "BF301": ("은행업감독규정 제63조 외화유동성 · Basel SRP31 IRRBB", "PRD-ALM",
              _bf301),
    "BF303": ("은행업감독규정 제53조 거액여신 · Basel SRP30 집중위험", "PRD-RDM",
              _bf303),
    "BF304": ("은행업감독규정 제53조 · Basel SRP30 집중위험", "PRD-RDM", _bf304),
    "BF306": ("은행업감독규정 제63조 · Basel III CRE20 외부등급", "PRD-RDM", _bf306),
    "BF401": ("은행업감독규정 제27조 자산건전성 분류 · 제29조", "PRD-RDM", _bf401),
    "BF404": ("은행업감독규정 제27조 · Basel III CRE36.69 채무불이행 정의",
              "PRD-RDM", _bf404),
    "BF405": ("은행업감독규정 제29조 대손충당금 · IFRS 9 5.5", "PRD-ECL", _bf405),
    "BF406": ("은행업감독규정 제27조 · 제99조 업무보고서", "PRD-RDM", _bf406),
    "BF408": ("은행업감독규정 제27조 자산건전성 분류", "PRD-RDM", _bf408),
    "BF409": ("은행업감독규정 제29조 대손충당금 · IFRS 9 5.5", "PRD-ECL", _bf409),
    "BF410": ("은행업감독규정 제27조 자산건전성 분류", "PRD-RDM", _bf410),
    "BF412": ("은행업감독규정 제27조 · Basel III CRE22 적격 담보", "PRD-RDM",
              _bf412),
}
