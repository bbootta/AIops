"""금감원 FINES 업무보고서 — 업무규제 준수 19건.

근거는 은행법 제35조(동일차주 신용공여 한도)·제35조의2(대주주 신용공여)·
제35조의3(대주주 발행주식 취득)·제37조(자회사 출자)·제38조(금지업무)와
Basel III LEX10(거액익스포저)이다.

**대주주 지정 원장이 없다.** 과거 독립검증에서 임의로 대주주를 지정했다가
실재하지 않는 한도 초과를 만들어 지적받았다. 그래서 대주주 신용공여는 파생하지
않고 0으로 두며(`prudential.ownership._MAJOR_SHAREHOLDER_IDENTIFIED = False`가
정본이다), B3000·B3103·B3104의 해당 라인에 "미확보"임을 남긴다. 0은 "없다"가
아니라 "확인해야 한다"는 뜻이고, 그 구분이 라인에 보여야 제출본이 성립한다.

**분모가 서식마다 다르다.** 은행법 제35조 한도는 자기자본(총자본)을 쓰고
Basel LEX10 거액익스포저는 기본자본(Tier 1)을 쓴다. `limits_deep`은 LEX 기준
이므로 은행법 기준 집계(B3103·B3104·B3221~B3223)는 이 모듈에서 자기자본 분모로
다시 묶는다. 다시 묶지 않으면 은행법 한도현황 서식에 LEX 숫자가 실린다.
B3121(면제대상)만 LEX 기준이므로 기본자본을 분모로 쓴다 — 짝인 B3120(규제대상)과
같은 분모여야 둘을 더해 전체가 된다. 다만 B3120은 이 그룹 소관이 아니고 현재
등록된 BR-33(부문별 집중도)에는 규제대상 익스포저 총액 라인이 없어 두 서식 간
대사는 **기계적으로 걸려 있지 않다** — B3121 안에서 총 = 규제대상 + 면제로만
닫는다.

원장이 없어 시드 고정으로 파생한 항목은 `forms_fss_compliance_data`에 모았다.
파생 라인은 formula에 파생임을 남긴다. 파생하지 않고 0으로 둔 것과 그 사유는
각 서식의 text 라인에 있다 — "없다"와 "안 봤다"는 다르다.

서식명·작성주기는 여기 적지 않는다 — FINES 마스터가 정본이고 forms.py가 붙인다.
"""

from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd

from risk_lib.limits.limits_deep import group_obligor_id
from risk_lib.regulatory.forms_base import (
    FormCheck, FormLine, _ratio_check, _sum_check, _val,
)
from risk_lib.regulatory.forms_fss_compliance_data import (
    DEBENTURE_BAND_MID, DEBENTURE_BANDS, STAFF_LOAN_BANDS, STAFF_LOAN_LIMIT,
    bank_share_book, debentures, loan_agent_book, prior_period,
    staff_loan_terms, staff_loans, subsidiary_book,
)

_M_CAP = "risk_lib.capital.bis · risk_lib.capital.bis_deep"
_M_OWN = "risk_lib.prudential.ownership"
_M_FIN = "risk_lib.prudential.financials"
_M_LIM = "risk_lib.limits.limits_deep"
_M_RDM = "risk_lib.datamodel.materialize_detail"
_M_ALM = "risk_lib.alm.nsfr"
_M_ATT = "risk_lib.attribution"
_M_DER = "risk_lib.regulatory.forms_fss_compliance_data"

_DERIVED = "원장 부재 — 기준일 고정 시드 파생값"
_C35 = "은행법 제35조 제1항 — 동일차주 신용공여 자기자본 25% 이내"
_C35_3 = "은행법 제35조 제3항 — 동일한 개인·법인 신용공여 자기자본 20% 이내"
_C35_4 = ("은행법 제35조 제4항 — 자기자본 10% 초과 거액신용공여 총합계액 "
          "자기자본 5배 이내")
_C_MS = "대주주 지정 원장 미확보 — 제출 전 반드시 확인해야 하는 칸이다"


# ---------------------------------------------------------------- 공용

def _own_capital(ctx) -> float:
    return float(ctx.result.meta["capital"].total)


def _bs(ctx, item: str) -> float:
    t = ctx.tables["pru_balance_sheet"]
    return float(t.loc[t["item"] == item, "amount"].iloc[0])


def _ownership(ctx, item: str) -> dict:
    t = ctx.tables["pru_ownership_limit"]
    return t[t["item"] == item].iloc[0].to_dict()


def _limit_block(base: int, item: str, used: float, own: float, pct: float,
                 citation: str, basis: str, module: str
                 ) -> tuple[list[FormLine], list[FormCheck]]:
    """한도 한 건 = 사용액·한도금액·소진율·한도내여부 4행 + 대사 2건.

    한도현황 서식은 같은 4행이 항목 수만큼 반복된다. 손으로 펼치면 한 항목만
    산식이 어긋나도 눈에 띄지 않는다.
    """
    limit = own * pct
    L = [
        FormLine(str(base), item, 0, "KRW", used, formula=basis,
                 citation=citation, source_module=module, is_subtotal=True),
        FormLine(str(base + 10), "한도금액", 1, "KRW", limit,
                 formula=f"자기자본 × {pct:.0%}", citation=citation,
                 source_module=module),
        FormLine(str(base + 20), "한도 소진율", 1, "ratio",
                 used / limit if limit else 0.0, formula="사용액 ÷ 한도금액",
                 source_module=module),
        FormLine(str(base + 30), "한도 내 여부", 1, "count",
                 1.0 if used <= limit + 1e-6 else 0.0,
                 formula="1 = 한도 내, 0 = 한도 초과", source_module=module),
    ]
    checks = [
        FormCheck(f"{item} 한도금액 = 자기자본 × {pct:.0%}", own * pct, limit, 1.0),
        _ratio_check(f"{item} 소진율 = 사용액 ÷ 한도금액", L, str(base + 20),
                     str(base), str(base + 10), 1e-9),
    ]
    return L, checks


def _large_credit(ctx) -> dict:
    """은행법 제35조 기준 동일차주·거액신용공여 집계 (분모 = 자기자본).

    `limits_deep.large_exposure_lex_group`은 BCBS LEX 기준(기본자본 10%/25%)
    이라 은행법 기준 대상 범위와 소진율이 다르다. 차주 그룹 정의는 같은 함수를
    쓴다 — 그룹 묶는 규칙이 서식마다 다르면 대사할 수 없다.
    """
    own = _own_capital(ctx)
    p = ctx.portfolio
    g = p.assign(_gid=p["obligor_id"].map(group_obligor_id))
    g["_sov"] = np.where(g["asset_class"] == "sovereign", g["ead"], 0.0)
    grp = (g.groupby("_gid", as_index=False)
           .agg(ead=("ead", "sum"), sov=("_sov", "sum"),
                n_obligor=("obligor_id", "nunique"),
                n_exposure=("exposure_id", "count"))
           .sort_values("ead", ascending=False).reset_index(drop=True))
    grp["pct_own"] = grp["ead"] / own
    grp["utilisation_25pct"] = grp["ead"] / (own * 0.25)
    # 한도 산정 제외는 익스포저 성격으로 갈린다 — 전액이 국가·중앙은행
    # 익스포저인 그룹만 제외대상이고, 섞여 있으면 관리대상으로 남긴다.
    grp["exempt"] = grp["sov"] >= grp["ead"] - 1.0
    grp["large"] = grp["ead"] > own * 0.10
    large = grp[grp["large"]]
    obl = (p.groupby("obligor_id", as_index=False)["ead"].sum()
           .sort_values("ead", ascending=False).reset_index(drop=True))
    return {"own": own, "group": grp, "large": large, "obligor": obl,
            "managed": large[~large["exempt"]],
            "exempt": large[large["exempt"]]}


# ---------------------------------------------------------------- B3000

def _b3000(ctx):
    """주주 및 임원과의 거래 내역 — 대주주 지정 원장이 없어 사용액을 0으로 둔다."""
    own = _own_capital(ctx)
    ms_credit = _ownership(ctx, "대주주 신용공여")
    ms_equity = _ownership(ctx, "대주주 발행주식 취득")
    L = [FormLine("1000", "자기자본", 0, "KRW", own,
                  formula="보통주자본 + 기타기본자본 + 보완자본",
                  citation="은행법 제2조 제1항 제5호", source_module=_M_CAP)]
    checks: list[FormCheck] = []
    for base, item, row, pct in (
            (2000, "대주주에 대한 신용공여", ms_credit, 0.25),
            (3000, "대주주 발행주식 취득", ms_equity, 0.01)):
        lines, ck = _limit_block(base, item, float(row["used"]), own, pct,
                                 str(row["citation"]), str(row["basis"]), _M_OWN)
        L += lines
        checks += ck
    L += [
        FormLine("4000", "임원에 대한 신용공여", 0, "KRW", 0.0,
                 formula=f"{_C_MS} — 파생하지 않고 0으로 둔다",
                 citation="은행법 제38조 제6호 — 임직원 대출 금지(소액대출 제외)",
                 source_module=_M_OWN, is_subtotal=True),
        FormLine("4100", "주주·임원과의 거래 건수", 0, "count", 0.0,
                 formula="대주주·임원 지정 원장 미확보 — 거래 식별 불가",
                 citation="은행법 제35조의2 제1항", source_module=_M_OWN),
        FormLine("9000", "식별 상태 비고", 0, "text", None,
                 text_value="대주주·임원 지정 원장이 원천 데이터에 없다. 임의로 "
                            "대주주를 지정하면 실재하지 않는 한도 초과가 보고되므로 "
                            "신용공여·거래건수를 0으로 두고 미확보임을 남긴다. "
                            "대주주 발행주식 취득액은 기타자산 중 지분증권 배분치라 "
                            "산출값이 있으나, 상대방이 대주주인지는 확인되지 않았다.",
                 citation="은행법 제35조의2·제35조의3"),
    ]
    return L, checks


# ---------------------------------------------------------------- B3101

def _b3101(ctx):
    """자기자본 산출근거(구 바젤 편제) — 기본자본·보완자본을 가산/차감으로 편제.

    바젤Ⅲ 편제(B3101-1 = 기존 BR-02)와 **같은 자본 스택**을 다르게 묶은 것이다.
    묶는 방식만 다르므로 총계는 반드시 일치해야 하고, 그것을 대사로 건다.
    """
    r = ctx.result
    cap = r.meta["capital"]
    bd = r.bis_deep
    # 가산/차감은 금액 부호가 아니라 명세표의 sign 열로 가른다 — 금액이 0인
    # 차감항목(당기 미해당)도 서식에는 칸이 있어야 "0"과 "미조회"가 구분된다.
    t1_tbl = list(bd.cet1_table.iterrows()) + list(bd.at1_table.iterrows())
    t1_add = sum(float(r["amount"]) for _, r in t1_tbl if r["sign"] == "+")
    t1_ded = -sum(float(r["amount"]) for _, r in t1_tbl if r["sign"] == "-")
    t2 = bd.tier2_table
    t2_add = float(t2[t2["sign"] == "+"]["amount"].sum())
    t2_ded = -float(t2[t2["sign"] == "-"]["amount"].sum())

    L = [
        FormLine("1000", "자기자본", 0, "KRW", float(cap.total),
                 formula="기본자본 + 보완자본",
                 citation="은행법 제2조 제1항 제5호 · 은행업감독규정 제26조",
                 source_module=_M_CAP, is_subtotal=True),
        FormLine("2000", "기본자본", 0, "KRW", float(cap.tier1),
                 formula="가산항목 − 차감항목", citation="CRE40.1~40.41",
                 source_module=_M_CAP, is_subtotal=True),
        FormLine("2100", "기본자본 가산항목 계", 1, "KRW", t1_add,
                 formula="sign = + 인 항목 합", citation="CRE40.1~40.30",
                 source_module=_M_CAP, is_subtotal=True),
    ]
    i = 0
    for _, row in t1_tbl:
        if row["sign"] != "+":
            continue
        i += 1
        L.append(FormLine(f"{2100 + i}", str(row["item"]), 2, "KRW",
                          float(row["amount"]), citation=str(row["ref"]),
                          source_module=_M_CAP))
    n_t1_add = i
    L.append(FormLine("2200", "기본자본 차감항목 계", 1, "KRW", t1_ded,
                      formula="차감액은 양수로 표시한다", source_module=_M_CAP,
                      is_subtotal=True))
    i = 0
    for _, row in t1_tbl:
        if row["sign"] != "-":
            continue
        i += 1
        L.append(FormLine(f"{2200 + i}", str(row["item"]), 2, "KRW",
                          -float(row["amount"]), citation=str(row["ref"]),
                          source_module=_M_CAP))
    n_t1_ded = i
    L += [
        FormLine("3000", "보완자본", 0, "KRW", float(cap.tier2),
                 formula="가산항목 − 차감항목", citation="CRE40.42~40.56",
                 source_module=_M_CAP, is_subtotal=True),
        FormLine("3100", "보완자본 가산항목 계", 1, "KRW", t2_add,
                 formula="sign = + 인 항목 합", citation="CRE40.42~40.45",
                 source_module=_M_CAP, is_subtotal=True),
    ]
    i = 0
    for _, row in t2.iterrows():
        if row["sign"] != "+":
            continue
        i += 1
        L.append(FormLine(f"{3100 + i}", str(row["item"]), 2, "KRW",
                          float(row["amount"]), citation=str(row["ref"]),
                          source_module=_M_CAP))
    n_t2_add = i
    L.append(FormLine("3200", "보완자본 차감항목 계", 1, "KRW", t2_ded,
                      formula="차감액은 양수로 표시한다", source_module=_M_CAP,
                      is_subtotal=True))
    i = 0
    for _, row in t2.iterrows():
        if row["sign"] != "-":
            continue
        i += 1
        L.append(FormLine(f"{3200 + i}", str(row["item"]), 2, "KRW",
                          -float(row["amount"]), citation=str(row["ref"]),
                          source_module=_M_CAP))
    n_t2_ded = i
    L += [
        FormLine("9000", "편제 비고", 0, "text", None,
                 text_value="본 서식은 구 바젤 편제(기본자본·보완자본의 가산/차감)이며 "
                            "바젤Ⅲ 편제는 B3101-1에 있다. 같은 자본 스택을 다르게 "
                            "묶은 것이므로 총계는 두 서식이 일치해야 한다.",
                 citation="Basel III CRE40 · 은행업감독규정 제26조"),
    ]
    checks = [
        _sum_check("자기자본 = 기본자본 + 보완자본", L, "1000", ("2000", "3000")),
        FormCheck("기본자본 = 가산 − 차감", float(cap.tier1),
                  t1_add - t1_ded, 1.0),
        FormCheck("보완자본 = 가산 − 차감", float(cap.tier2),
                  t2_add - t2_ded, 1.0),
        # 소계 4개가 각각 자기 명세 합과 맞는지 본다. 총계만 대사하면 가산과
        # 차감이 서로 상쇄돼 어긋난 편제를 놓친다.
        _sum_check("기본자본 가산항목 계 = 명세 합", L, "2100",
                   tuple(f"{2100 + k}" for k in range(1, n_t1_add + 1)), 1.0),
        _sum_check("기본자본 차감항목 계 = 명세 합", L, "2200",
                   tuple(f"{2200 + k}" for k in range(1, n_t1_ded + 1)), 1.0),
        _sum_check("보완자본 가산항목 계 = 명세 합", L, "3100",
                   tuple(f"{3100 + k}" for k in range(1, n_t2_add + 1)), 1.0),
        _sum_check("보완자본 차감항목 계 = 명세 합", L, "3200",
                   tuple(f"{3200 + k}" for k in range(1, n_t2_ded + 1)), 1.0),
        # B3101-1(바젤Ⅲ 편제, 기존 BR-02)과의 총계 대사 — 같은 명세표를
        # 다르게 묶었으므로 합계가 어긋나면 편제가 틀린 것이다.
        FormCheck("자기자본 = B3101-1 자본명세 합계", float(cap.total),
                  float(bd.cet1_table["amount"].sum())
                  + float(bd.at1_table["amount"].sum())
                  + float(bd.tier2_table["amount"].sum()), 1.0),
    ]
    return L, checks


# ---------------------------------------------------------------- B3103 / B3104

def _bank_act_limits(ctx, scope: str, scope_note: str):
    """은행법상 한도현황 — 동일차주·동일인·거액여신·자산운용 한도를 한 표에."""
    lc = _large_credit(ctx)
    own = lc["own"]
    grp, obl = lc["group"], lc["obligor"]
    top_grp = grp.iloc[0]
    top_obl = obl.iloc[0]
    L = [
        FormLine("1000", "자기자본", 0, "KRW", own,
                 formula="보통주자본 + 기타기본자본 + 보완자본",
                 citation="은행법 제2조 제1항 제5호", source_module=_M_CAP),
        FormLine("1010", "적용 대상 구분", 0, "text", None, text_value=scope,
                 formula=scope_note,
                 citation="은행업감독업무시행세칙 별지 서식 — 대상 은행 구분"),
    ]
    checks: list[FormCheck] = []
    blocks = (
        (2000, "동일차주(그룹) 신용공여 — 최대", float(top_grp["ead"]), 0.25, _C35,
         f"최대 그룹 {top_grp['_gid']} · 차주 {int(top_grp['n_obligor'])}인 "
         f"· 전체 {len(grp)}개 그룹 중", _M_LIM),
        (2100, "동일한 개인·법인 신용공여 — 최대", float(top_obl["ead"]), 0.20,
         _C35_3, f"최대 차주 {top_obl['obligor_id']} · 전체 {len(obl):,}인 중",
         _M_LIM),
        (2200, "거액신용공여 합계", float(lc["large"]["ead"].sum()), 5.00, _C35_4,
         f"자기자본 10% 초과 동일차주 {len(lc['large'])}개 합계", _M_LIM),
        (3000, "대주주에 대한 신용공여", 0.0, 0.25,
         "은행법 제35조의2 제1항 — 자기자본 25% 이내", _C_MS, _M_OWN),
        (3100, "대주주 발행주식 취득", float(_ownership(ctx, "대주주 발행주식 취득")["used"]),
         0.01, "은행법 제35조의3 제1항 — 자기자본 1% 이내", "기타자산 중 지분증권 배분치",
         _M_OWN),
        (4000, "자회사 출자", float(_ownership(ctx, "자회사 출자")["used"]), 0.20,
         "은행법 제37조 제2항 — 자기자본 20% 이내", "기타자산 중 출자금 배분치",
         _M_OWN),
        (4100, "유가증권 투자", float(_ownership(ctx, "유가증권 투자")["used"]), 1.00,
         "은행법 제38조 제1호 — 자기자본 100% 이내 (국채·통안증권 제외)",
         "HQLA Level 2A·2B 합계", _M_OWN),
        (4200, "업무용부동산 소유", float(_ownership(ctx, "업무용부동산 소유")["used"]),
         0.60, "은행법 제38조 제3호 — 자기자본 60% 이내", "기타자산 중 부동산 배분치",
         _M_OWN),
    )
    managed_total = float(lc["managed"]["ead"].sum())
    exempt_total = float(lc["exempt"]["ead"].sum())
    for base, item, used, pct, cite, basis, module in blocks:
        lines, ck = _limit_block(base, item, used, own, pct, cite, basis, module)
        L += lines
        checks += ck
        if base != 2200:
            continue
        # 2200 블록의 소진율·한도내여부는 **제외대상을 포함한 총계** 기준이다.
        # 은행법 제35조 제4항 한도 판정은 국가·중앙은행 등 한도 산정 제외분을
        # 뺀 금액으로 해야 하므로, 판정 라인을 따로 둔다. 총계만 실으면
        # 제외대상 규모만큼 소진율이 부풀어 실제와 다른 판정이 보고된다.
        L += [
            FormLine("2240", "한도 산정 제외대상 소계", 1, "KRW", exempt_total,
                     formula=f"국가·중앙은행 등 동일차주 {len(lc['exempt'])}개 "
                             f"· 명세는 B3223",
                     citation="은행법 시행령 제20조의5 — 한도 산정 제외",
                     source_module=_M_LIM),
            FormLine("2250", "한도 산정 대상 소계", 1, "KRW", managed_total,
                     formula=f"거액신용공여 합계 − 제외대상 · 동일차주 "
                             f"{len(lc['managed'])}개 · 명세는 B3222",
                     citation="은행법 제35조 제4항 — 한도 산정 대상",
                     source_module=_M_LIM, is_subtotal=True),
            FormLine("2260", "한도 산정 대상 소진율", 1, "ratio",
                     managed_total / (own * 5.0) if own else 0.0,
                     formula="한도 산정 대상 소계 ÷ 한도금액",
                     source_module=_M_LIM),
            FormLine("2270", "한도 산정 대상 기준 한도 내 여부", 1, "count",
                     1.0 if managed_total <= own * 5.0 + 1e-6 else 0.0,
                     formula="1 = 한도 내, 0 = 한도 초과 — 규정상 판정은 이 라인이다",
                     citation=_C35_4, source_module=_M_LIM),
        ]
        checks += [
            _sum_check("거액신용공여 합계 = 한도 산정 대상 + 제외대상", L,
                       "2200", ("2250", "2240"), 1.0),
            _ratio_check("한도 산정 대상 소진율 = 대상 소계 ÷ 한도금액", L,
                         "2260", "2250", "2210", 1e-9),
        ]
    L += [
        FormLine("5000", "한도 초과 항목 수", 0, "count",
                 float(sum(1 for base, *_ in blocks
                           if _val(L, str(base + 30)) == 0.0)),
                 formula="한도 내 여부 = 0 인 항목 수", source_module=_M_LIM,
                 is_subtotal=True),
        FormLine("5100", "동일차주 한도 초과 그룹 수", 0, "count",
                 float(int((grp["utilisation_25pct"] > 1.0).sum())),
                 formula=f"전체 {len(grp)}개 그룹 중", citation=_C35,
                 source_module=_M_LIM),
        FormLine("9000", "분모 비고", 0, "text", None,
                 text_value="본 서식의 한도 분모는 은행법상 자기자본(총자본)이다. "
                            "Basel LEX10 거액익스포저(B3120·B3121)는 기본자본을 "
                            "분모로 쓰므로 같은 차주라도 소진율이 다르다. "
                            "거액신용공여(2200)의 소진율·한도내여부는 제외대상을 "
                            "포함한 총계 기준이며, 규정상 한도 판정은 제외대상을 "
                            "뺀 2260·2270 라인이다.",
                 citation="은행법 제35조 · 은행법 시행령 제20조의5 · Basel III LEX10.9"),
    ]
    checks.append(FormCheck(
        "한도 초과 항목 수 = 한도내여부 0인 항목 수",
        float(sum(1 for base, *_ in blocks if _val(L, str(base + 30)) == 0.0)),
        _val(L, "5000"), 1e-9))
    return L, checks


def _b3103(ctx):
    return _bank_act_limits(
        ctx, "일반은행 (특수은행 제외)",
        "은행법이 직접 적용되는 은행 — 근거법상 별도 한도는 B3105·B3106에 있다. "
        "은행 유형 플래그가 원천 데이터에 없어 B3104와 같은 산식으로 채운다 — "
        "실제 제출은 해당 유형 한 서식만 한다")


def _b3104(ctx):
    return _bank_act_limits(
        ctx, "특수은행",
        "근거법이 은행법을 준용하는 범위에서 같은 산식을 적용한다 — "
        "근거법 고유 한도는 B3105·B3106 소관이다. 은행 유형 플래그가 원천 "
        "데이터에 없어 B3103과 같은 값이 실린다 — 두 서식은 대상 은행이 "
        "배타적이므로 실제 제출은 한 서식만 한다")


# ---------------------------------------------------------------- B3110

def _b3110(ctx):
    """자회사현황 — 출자 총액은 산출값, 개별 명세는 파생값."""
    own = _own_capital(ctx)
    row = _ownership(ctx, "자회사 출자")
    total = float(row["used"])
    sub = subsidiary_book(total)
    L, checks = _limit_block(1000, "자회사 출자 총액", total, own, 0.20,
                             str(row["citation"]), str(row["basis"]), _M_OWN)
    L = [FormLine("100", "자기자본", 0, "KRW", own,
                  citation="은행법 제2조 제1항 제5호", source_module=_M_CAP)] + L
    L.append(FormLine("2000", "자회사 수", 0, "count", float(len(sub)),
                      formula=_DERIVED, source_module=_M_DER, is_subtotal=True))
    for i, (_, s) in enumerate(sub.iterrows(), start=1):
        L.append(FormLine(f"{2000 + i * 10}", f"자회사 · {s['name']}", 1, "KRW",
                          float(s["investment"]),
                          formula=f"의결권 지분율 {float(s['stake']):.1%} · {_DERIVED}",
                          citation="은행법 제37조 제2항 — 의결권주식 15% 초과 소유 회사",
                          source_module=_M_DER))
    L.append(FormLine("3000", "의결권 지분율 15% 이하 건수", 0, "count",
                      float(int((sub["stake"] <= 0.15).sum())),
                      formula="0이어야 한다 — 15% 이하면 자회사 정의에 들지 않는다",
                      citation="은행법 제37조 제2항", source_module=_M_DER))
    checks += [
        FormCheck("자회사별 출자금액 합계 = 자회사 출자 산출액", total,
                  float(sub["investment"].sum()), 1.0),
        FormCheck("전 자회사가 의결권 지분율 15% 초과", 0.0,
                  float(int((sub["stake"] <= 0.15).sum())), 1e-9),
        FormCheck("자회사 수 = 명세 건수", float(len(sub)), _val(L, "2000"), 1e-9),
    ]
    return L, checks


# ---------------------------------------------------------------- B3111

def _b3111(ctx):
    """자회사에 대한 신용공여현황 — 개별 10% · 합계 20% 한도 (은행법 제37조 제3항)."""
    own = _own_capital(ctx)
    sub = subsidiary_book(float(_ownership(ctx, "자회사 출자")["used"]))
    total = float(sub["credit"].sum())
    L, checks = _limit_block(
        1000, "자회사에 대한 신용공여 합계", total, own, 0.20,
        "은행법 제37조 제3항 제2호 — 자회사 전체 신용공여 자기자본 20% 이내",
        f"자회사 {len(sub)}개 합계 · {_DERIVED}", _M_DER)
    L = [FormLine("100", "자기자본", 0, "KRW", own,
                  citation="은행법 제2조 제1항 제5호", source_module=_M_CAP),
         FormLine("200", "개별 자회사 신용공여 한도금액", 0, "KRW", own * 0.10,
                  formula="자기자본 × 10%",
                  citation="은행법 제37조 제3항 제1호 — 개별 자회사 자기자본 10% 이내",
                  source_module=_M_OWN)] + L
    for i, (_, s) in enumerate(sub.iterrows(), start=1):
        L.append(FormLine(f"{2000 + i * 10}", f"자회사 · {s['name']}", 1, "KRW",
                          float(s["credit"]),
                          formula=(f"출자금액 대비 {float(s['credit']) / float(s['investment']):.1%}"
                                   f" · 개별 한도 소진 "
                                   f"{float(s['credit']) / (own * 0.10):.2%} · {_DERIVED}"),
                          citation="은행법 제37조 제3항 제1호", source_module=_M_DER))
    L.append(FormLine("3000", "개별 한도 초과 자회사 수", 0, "count",
                      float(int((sub["credit"] > own * 0.10).sum())),
                      formula="신용공여 > 자기자본 × 10% 인 자회사 수",
                      citation="은행법 제37조 제3항 제1호", source_module=_M_DER))
    checks += [
        FormCheck("개별 자회사 한도금액 = 자기자본 × 10%", own * 0.10,
                  _val(L, "200"), 1.0),
        _sum_check("합계 = 자회사별 신용공여 합", L, "1000",
                   tuple(f"{2000 + i * 10}" for i in range(1, len(sub) + 1)), 1.0),
        FormCheck("개별 한도 초과 자회사 없음", 0.0,
                  float(int((sub["credit"] > own * 0.10).sum())), 1e-9),
    ]
    return L, checks


# ---------------------------------------------------------------- B3112

def _b3112(ctx):
    """자기주식 보유현황 — 파생하지 않는다. CET1 자기주식 차감이 실제로 0이다."""
    t = ctx.result.bis_deep.cet1_table
    deduction = -float(t.loc[t["item"] == "자기주식 차감", "amount"].iloc[0])
    retained = _bs(ctx, "이익잉여금")
    L = [
        FormLine("1000", "자기주식 취득가액", 0, "KRW", deduction,
                 formula="보통주자본 자기주식 차감액과 같은 금액이다",
                 citation="은행법 제38조 제2호 · 상법 제341조",
                 source_module=_M_CAP, is_subtotal=True),
        FormLine("2000", "보통주자본 자기주식 차감액", 0, "KRW", deduction,
                 citation="CRE40.20 — 자기주식은 보통주자본에서 전액 차감",
                 source_module=_M_CAP),
        FormLine("3000", "배당가능이익 (취득 재원)", 0, "KRW", retained,
                 formula="이익잉여금", citation="상법 제341조 제1항 — 취득가액 총액 한도",
                 source_module=_M_FIN, is_subtotal=True),
        FormLine("3100", "취득한도 소진율", 0, "ratio",
                 deduction / retained if retained else 0.0,
                 formula="취득가액 ÷ 배당가능이익", source_module=_M_FIN),
        FormLine("9000", "보유 상태 비고", 0, "text", None,
                 text_value="자기주식 보유액을 파생하지 않았다. 자본 산출이 이미 "
                            "자기주식 차감 0을 내고 있으므로 보유액을 난수로 만들면 "
                            "산출값과 모순된다. 0은 미조회가 아니라 미보유다.",
                 citation="CRE40.20"),
    ]
    checks = [
        FormCheck("자기주식 취득가액 = 보통주자본 차감액", deduction,
                  _val(L, "2000"), 1.0),
        _ratio_check("취득한도 소진율 = 취득가액 ÷ 배당가능이익", L, "3100",
                     "1000", "3000", 1e-9),
    ]
    return L, checks


# ---------------------------------------------------------------- B3113

def _b3113(ctx):
    """타은행주식 보유현황 — 발행은행은 실제 거래상대방, 보유액·지분율은 파생값."""
    own = _own_capital(ctx)
    sec = _ownership(ctx, "유가증권 투자")
    headroom = float(sec["limit_amount"]) - float(sec["used"])
    banks = bank_share_book(ctx.portfolio)
    total = float(banks["holding"].sum())
    L = [
        FormLine("1000", "타은행 주식 보유 총액", 0, "KRW", total,
                 formula=f"발행은행 {len(banks)}개 합계 · {_DERIVED}",
                 citation="은행법 제37조 제1항 — 다른 회사 의결권주식 15% 초과 소유 금지",
                 source_module=_M_DER, is_subtotal=True),
        FormLine("1100", "자기자본 대비 비중", 0, "ratio",
                 total / own if own else 0.0, formula="보유 총액 ÷ 자기자본",
                 source_module=_M_DER),
        FormLine("1200", "유가증권 투자한도 잔여여유", 0, "KRW", headroom,
                 formula="한도금액 − 사용액",
                 citation="은행법 제38조 제1호 — 자기자본 100% 이내",
                 source_module=_M_OWN),
        FormLine("2000", "보유 은행 수", 0, "count", float(len(banks)),
                 formula=f"신용공여 상위 은행 {len(banks)}개 · {_DERIVED}",
                 citation="은행법 제37조 제1항", source_module=_M_DER,
                 is_subtotal=True),
    ]
    for i, (_, b) in enumerate(banks.iterrows(), start=1):
        L.append(FormLine(f"{2000 + i * 10}", f"발행은행 · {b['obligor_id']}", 1,
                          "KRW", float(b["holding"]),
                          formula=(f"의결권 지분율 {float(b['stake']):.2%} · "
                                   f"신용공여 EAD {float(b['ead']):,.0f} · {_DERIVED}"),
                          citation="은행법 제37조 제1항", source_module=_M_DER))
    L.append(FormLine("3000", "의결권 지분율 15% 초과 건수", 0, "count",
                      float(int((banks["stake"] > 0.15).sum())),
                      formula="0이 아니면 은행법 제37조 제1항 위반이다",
                      citation="은행법 제37조 제1항", source_module=_M_DER))
    checks = [
        _sum_check("보유 총액 = 발행은행별 보유액 합", L, "1000",
                   tuple(f"{2000 + i * 10}" for i in range(1, len(banks) + 1)), 1.0),
        FormCheck("의결권 지분율 15% 초과 없음", 0.0,
                  float(int((banks["stake"] > 0.15).sum())), 1e-9),
        FormCheck("보유 총액이 유가증권 투자한도 잔여여유 이내", 0.0,
                  max(0.0, total - headroom), 1.0),
        FormCheck("자기자본 대비 비중 = 보유 총액 ÷ 자기자본",
                  total / own if own else 0.0, _val(L, "1100"), 1e-12),
        FormCheck("보유 은행 수 = 명세 건수", float(len(banks)),
                  _val(L, "2000"), 1e-9),
    ]
    return L, checks


# ---------------------------------------------------------------- B3114

def _b3114(ctx):
    """대출모집업무 위탁현황 — 대상 가계여신 잔액은 산출값, 위탁 비중은 파생값."""
    aq = ctx.tables["rdm_asset_quality"]
    base = float(aq[aq["borrower_type"] == "가계여신"]["balance"].sum())
    agents = loan_agent_book(base)
    total = float(agents["balance"].sum())
    L = [
        FormLine("1000", "위탁 대상 가계여신 잔액", 0, "KRW", base,
                 formula="가계여신 잔액 합계", citation="은행업감독규정 제27조",
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("2000", "대출모집인 취급 잔액", 0, "KRW", total,
                 formula=f"위탁 모집법인 {len(agents)}개 합계 · {_DERIVED}",
                 citation="은행업감독규정 제30조의2 · 금융회사의 업무위탁 등에 관한 규정",
                 source_module=_M_DER, is_subtotal=True),
        FormLine("2100", "모집 취급 비중", 0, "ratio",
                 total / base if base else 0.0,
                 formula="모집 취급 잔액 ÷ 위탁 대상 가계여신 잔액",
                 source_module=_M_DER),
        FormLine("3000", "위탁 모집법인 수", 0, "count", float(len(agents)),
                 formula=_DERIVED, citation="은행업감독규정 제30조의2",
                 source_module=_M_DER, is_subtotal=True),
        FormLine("3100", "등록 대출모집인 수", 0, "count",
                 float(agents["n_agent"].sum()), formula=_DERIVED,
                 citation="대출모집인 제도 모범규준", source_module=_M_DER),
    ]
    for i, (_, a) in enumerate(agents.iterrows(), start=1):
        L.append(FormLine(f"{4000 + i * 10}", f"위탁사 · {a['name']}", 1, "KRW",
                          float(a["balance"]),
                          formula=(f"모집인 {int(a['n_agent'])}인 · 취급 비중 "
                                   f"{float(a['balance']) / base:.2%} · {_DERIVED}"),
                          citation="은행업감독규정 제30조의2", source_module=_M_DER))
    checks = [
        _sum_check("모집 취급 잔액 = 위탁사별 취급 잔액 합", L, "2000",
                   tuple(f"{4000 + i * 10}" for i in range(1, len(agents) + 1)), 1.0),
        _ratio_check("모집 취급 비중 = 취급 잔액 ÷ 대상 잔액", L, "2100",
                     "2000", "1000", 1e-9),
        FormCheck("모집 취급 잔액이 대상 가계여신 잔액 이내", 0.0,
                  max(0.0, total - base), 1.0),
        FormCheck("위탁 모집법인 수 = 명세 건수", float(len(agents)),
                  _val(L, "3000"), 1e-9),
    ]
    return L, checks


# ---------------------------------------------------------------- 금융채권 공용

def _debenture_facts(ctx) -> dict:
    """금융채권 파생 묶음 — B3116·B3117·B3118이 같은 수치를 봐야 대사가 성립한다."""
    t2 = ctx.result.bis_deep.tier2_table
    sub = float(t2.loc[t2["item"].str.startswith("후순위채(잔존"), "amount"].iloc[0])
    return debentures(_bs(ctx, "사채 및 장기차입금"), sub)


def _nsfr_funding_gt1y(ctx) -> float:
    t = ctx.tables["alm_nsfr_item"]
    return float(t.loc[t["category"] == "funding_gt1y", "amount"].iloc[0])


# ---------------------------------------------------------------- B3116

def _b3116(ctx):
    """금융채권 발생·상환 현황 — 기말 잔액과 후순위채가 앵커, 흐름은 파생값."""
    d = _debenture_facts(ctx)
    L = [
        FormLine("1000", "금융채권 기말 잔액", 0, "KRW", d["closing"],
                 formula="재무상태표 사채 및 장기차입금",
                 citation="은행법 제33조 — 금융채 발행 · 은행업감독규정 제99조",
                 source_module=_M_FIN, is_subtotal=True),
    ]
    kind_codes = []
    for i, (kind, amt) in enumerate(d["kinds"].items(), start=1):
        code = f"{1000 + i * 10}"
        kind_codes.append(code)
        L.append(FormLine(code, f"종류 · {kind}", 1, "KRW", float(amt),
                          formula=("보완자본 인정 후순위채 산출액"
                                   if kind == "후순위 은행채" else _DERIVED),
                          citation=("CRE40.42" if kind == "후순위 은행채"
                                    else "은행법 제33조"),
                          source_module=(_M_CAP if kind == "후순위 은행채"
                                         else _M_DER)))
    L += [
        FormLine("2000", "금융채권 기초 잔액", 0, "KRW", d["opening"],
                 formula=f"{_DERIVED} (전기말 원장 미보유)", source_module=_M_DER,
                 is_subtotal=True),
        FormLine("3000", "당기 중 발행액", 0, "KRW", d["issued"],
                 formula=_DERIVED, citation="은행법 제33조", source_module=_M_DER,
                 is_subtotal=True),
        FormLine("4000", "당기 중 상환액", 0, "KRW", d["redeemed"],
                 formula="기초 + 발행 − 기말로 역산", source_module=_M_DER,
                 is_subtotal=True),
        FormLine("5000", "순증감액", 0, "KRW", d["closing"] - d["opening"],
                 formula="기말 − 기초", source_module=_M_DER),
    ]
    checks = [
        _sum_check("기말 잔액 = 종류별 합", L, "1000", tuple(kind_codes), 1.0),
        FormCheck("기말 = 기초 + 발행 − 상환", d["closing"],
                  d["opening"] + d["issued"] - d["redeemed"], 1.0),
        FormCheck("상환액 ≥ 0", 0.0, min(0.0, d["redeemed"]), 1.0),
        FormCheck("후순위 은행채 = 보완자본 인정 후순위채",
                  float(d["kinds"]["후순위 은행채"]), _val(L, "1020"), 1.0),
        # 재무상태표와 NSFR이 같은 조달을 각각 집계한다 — 어긋나면 둘 중 하나가 틀렸다.
        FormCheck("기말 잔액 = NSFR 1년 초과 조달", _nsfr_funding_gt1y(ctx),
                  d["closing"], 1.0),
        FormCheck("순증감액 = 기말 − 기초", d["closing"] - d["opening"],
                  _val(L, "5000"), 1.0),
    ]
    return L, checks


# ---------------------------------------------------------------- B3117

def _b3117(ctx):
    """금융채권 잔존만기별 현황 — 총액이 앵커, 구간 배분은 파생값."""
    d = _debenture_facts(ctx)
    L = [FormLine("1000", "금융채권 잔액 합계", 0, "KRW", d["closing"],
                  formula="재무상태표 사채 및 장기차입금",
                  citation="은행업감독규정 제99조 업무보고서", source_module=_M_FIN,
                  is_subtotal=True)]
    codes = []
    for i, band in enumerate(DEBENTURE_BANDS, start=1):
        code = f"{1000 + i * 10}"
        codes.append(code)
        # 은행업감독규정 제26조는 자기자본비율(경영지도비율) 조문이라 잔존만기
        # 구간 편제 근거가 아니다. 편제 근거는 업무보고서 조문과 NSFR 만기구간이다.
        L.append(FormLine(code, f"잔존만기 · {band}", 1, "KRW",
                          float(d["buckets"][band]), formula=_DERIVED,
                          citation="은행업감독규정 제99조 업무보고서 · NSF20 만기구간",
                          source_module=_M_DER))
    L += [
        FormLine("2000", "가중평균 잔존만기", 0, "count", d["wam"],
                 formula="Σ(구간 중값 × 잔액) ÷ 잔액 합계 (단위: 년)",
                 source_module=_M_DER),
        FormLine("2100", "1년 이하 비중", 0, "ratio",
                 float(d["buckets"]["1년 이하"]) / d["closing"],
                 formula="1년 이하 잔액 ÷ 잔액 합계",
                 citation="NSF20 — 1년 이내 조달은 안정자금 인정률이 떨어진다",
                 source_module=_M_DER),
    ]
    sub = float(d["kinds"]["후순위 은행채"])
    checks = [
        _sum_check("잔액 합계 = 잔존만기 구간별 합", L, "1000", tuple(codes), 1.0),
        _ratio_check("1년 이하 비중 = 1년 이하 잔액 ÷ 합계", L, "2100",
                     "1010", "1000", 1e-9),
        # 후순위채는 보완자본 인정 요건상 잔존 5년 이상이다.
        FormCheck("5년 이상 구간 ≥ 후순위 은행채", 0.0,
                  min(0.0, float(d["buckets"]["5년 이상"]) - sub), 1.0),
        # 가중평균 잔존만기는 구간 중값 가중이라 산식을 서식이 스스로 다시
        # 계산해 보지 않으면 구간 순서가 바뀌어도 아무도 모른다.
        FormCheck("가중평균 잔존만기 = Σ(구간 중값 × 잔액) ÷ 합계",
                  sum(DEBENTURE_BAND_MID[i] * _val(L, c)
                      for i, c in enumerate(codes)) / d["closing"],
                  _val(L, "2000"), 1e-9),
    ]
    return L, checks


# ---------------------------------------------------------------- B3118

def _b3118(ctx):
    """금융채권 월별 발행내역 — 반기 발행 총액이 B3116과 같아야 한다."""
    d = _debenture_facts(ctx)
    monthly = d["monthly"]
    end = pd.Period(str(ctx.result.meta.get("asof", "1970-01-01")), freq="M")
    L = [FormLine("1000", "보고기간 발행 총액", 0, "KRW", float(monthly.sum()),
                  formula=f"{len(monthly)}개월 합계 · {_DERIVED}",
                  citation="은행법 제33조 — 금융채 발행", source_module=_M_DER,
                  is_subtotal=True)]
    codes = []
    for i, amt in enumerate(monthly, start=1):
        code = f"{1000 + i * 10}"
        codes.append(code)
        L.append(FormLine(code, f"발행월 · {end - (len(monthly) - i)}", 1, "KRW",
                          float(amt), formula=_DERIVED, source_module=_M_DER))
    L.append(FormLine("2000", "월평균 발행액", 0, "KRW",
                      float(monthly.sum()) / len(monthly),
                      formula="발행 총액 ÷ 개월 수", source_module=_M_DER))
    checks = [
        _sum_check("발행 총액 = 월별 발행액 합", L, "1000", tuple(codes), 1.0),
        FormCheck("발행 총액 = B3116 당기 중 발행액", d["issued"],
                  float(monthly.sum()), 1.0),
        FormCheck("월평균 발행액 = 발행 총액 ÷ 개월 수",
                  float(monthly.sum()) / len(monthly), _val(L, "2000"), 1.0),
    ]
    return L, checks


# ---------------------------------------------------------------- B3119

def _b3119(ctx):
    """임직원에 대한 소액대출조건 — 금리·기간 원장이 없어 조건은 전부 파생값."""
    t = staff_loan_terms()
    L = [
        FormLine("1000", "1인당 소액대출 한도", 0, "KRW", t["limit"],
                 formula="감독규정 상한 그대로",
                 citation="은행법 제38조 제6호 · 은행업감독규정 제55조 — 2천만원 이내"),
        FormLine("2000", "임직원 적용금리", 0, "ratio", t["staff_rate"],
                 formula=_DERIVED, citation="은행업감독규정 제55조",
                 source_module=_M_DER),
        FormLine("2100", "일반 가계신용대출 금리", 0, "ratio", t["market_rate"],
                 formula=_DERIVED, source_module=_M_DER),
        FormLine("2200", "금리차 (임직원 − 일반)", 0, "ratio",
                 t["staff_rate"] - t["market_rate"],
                 formula="음수 = 임직원에게 유리한 조건",
                 citation="은행법 제38조 제6호 — 소액대출은 유리한 조건 허용 예외",
                 source_module=_M_DER),
        FormLine("3000", "최장 대출기간", 0, "count", t["tenor_years"],
                 formula=f"단위: 년 · {_DERIVED}", source_module=_M_DER),
        FormLine("4000", "담보조건", 0, "text", None,
                 text_value="무담보 신용 — 재직 중 상환 조건",
                 citation="은행업감독규정 제55조"),
        FormLine("9000", "조건 출처 비고", 0, "text", None,
                 text_value="금리·기간 원장이 원천 데이터에 없어 조건 수치는 기준일 "
                            "고정 시드 파생값이다. 1인당 한도만 감독규정 상한을 "
                            "그대로 쓴다.",
                 citation="은행업감독규정 제55조"),
    ]
    checks = [
        FormCheck("금리차 = 임직원 적용금리 − 일반 가계신용대출 금리",
                  t["staff_rate"] - t["market_rate"], _val(L, "2200"), 1e-12),
        FormCheck("1인당 한도가 감독규정 상한 이내", 0.0,
                  max(0.0, t["limit"] - STAFF_LOAN_LIMIT), 1.0),
        FormCheck("임직원 적용금리 ≥ 0", 0.0, min(0.0, t["staff_rate"]), 1e-12),
        # 파생 함수가 방향을 강제한다고 해도 서식이 스스로 확인하지 않으면
        # 파라미터가 바뀔 때 규정을 거꾸로 말하는 서식이 그대로 나간다.
        FormCheck("임직원 금리가 일반 금리보다 낮다 (금리차 < 0)", 0.0,
                  max(0.0, _val(L, "2200")), 1e-12),
        FormCheck("최장 대출기간 > 0", 0.0, min(0.0, t["tenor_years"]), 1e-12),
    ]
    return L, checks


# ---------------------------------------------------------------- B3220

def _b3220(ctx):
    """임직원에 대한 소액대출 취급실적 — 취급 원장이 없어 건수·금액이 파생값."""
    df = staff_loans()
    n_total = float(df["n"].sum())
    amt_total = float(df["amount"].sum())
    L = [
        FormLine("1000", "취급 건수", 0, "count", n_total, formula=_DERIVED,
                 citation="은행업감독규정 제55조", source_module=_M_DER,
                 is_subtotal=True),
        FormLine("1100", "취급 금액", 0, "KRW", amt_total, formula=_DERIVED,
                 source_module=_M_DER, is_subtotal=True),
        FormLine("1200", "1건당 평균 대출금액", 0, "KRW",
                 amt_total / n_total if n_total else 0.0,
                 formula="취급 금액 ÷ 취급 건수", source_module=_M_DER),
        FormLine("2000", "1인당 소액대출 한도", 0, "KRW", STAFF_LOAN_LIMIT,
                 citation="은행법 제38조 제6호 · 은행업감독규정 제55조"),
    ]
    n_codes, a_codes = [], []
    for i, (_, row) in enumerate(df.iterrows(), start=1):
        nc, ac = f"{3000 + i * 10}", f"{4000 + i * 10}"
        n_codes.append(nc)
        a_codes.append(ac)
        L.append(FormLine(nc, f"금액구간 · {row['band']} — 건수", 1, "count",
                          float(row["n"]), formula=_DERIVED,
                          source_module=_M_DER))
        L.append(FormLine(ac, f"금액구간 · {row['band']} — 금액", 2, "KRW",
                          float(row["amount"]),
                          formula=(f"평균 {float(row['avg_amount']):,.0f}원 · "
                                   f"{_DERIVED}"), source_module=_M_DER))
    checks = [
        _sum_check("취급 건수 = 구간별 건수 합", L, "1000", tuple(n_codes), 1e-9),
        _sum_check("취급 금액 = 구간별 금액 합", L, "1100", tuple(a_codes), 1.0),
        _ratio_check("평균 대출금액 = 금액 ÷ 건수", L, "1200", "1100", "1000", 1e-6),
        FormCheck("전 구간 상한이 1인당 한도 이내", 0.0,
                  max(0.0, float(df["band_cap"].max()) - STAFF_LOAN_LIMIT), 1.0),
    ]
    return L, checks


# ---------------------------------------------------------------- B3121

def _b3121(ctx):
    """거액익스포져비율 — 면제대상. B3120(규제대상, 기존 BR-33)의 짝이다.

    분모는 기본자본이다. LEX 기준이므로 은행법 자기자본 기준인 B3103과 다르다.
    """
    r = ctx.result
    tier1 = float(r.meta["capital"].tier1)
    p = ctx.portfolio
    total = float(p["ead"].sum())
    exempt_ead = float(p[p["asset_class"] == "sovereign"]["ead"].sum())
    lc = _large_credit(ctx)
    exempt_grp = lc["group"][lc["group"]["exempt"]]
    L = [
        FormLine("1000", "기본자본 (Tier 1)", 0, "KRW", tier1,
                 citation="LEX10.9 — 거액익스포저 산정은 기본자본 기준",
                 source_module=_M_CAP),
        FormLine("1100", "총 익스포저", 0, "KRW", total,
                 formula="포트폴리오 EAD 합계", citation="LEX20 익스포저 측정",
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("1200", "규제대상 익스포저", 0, "KRW", total - exempt_ead,
                 formula="총 익스포저 − 면제 익스포저",
                 citation="LEX10.10 — 규제대상 상세는 B3120", source_module=_M_RDM),
        FormLine("1300", "면제 익스포저 합계", 0, "KRW", exempt_ead,
                 citation="LEX30.2 — 한도 적용 제외 익스포저",
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("1310", "면제사유 · 국가 및 중앙은행", 1, "KRW", exempt_ead,
                 formula="자산군 sovereign 익스포저", citation="LEX30.2(1)",
                 source_module=_M_RDM),
        FormLine("1320", "면제사유 · 적격 중앙청산소(QCCP)", 1, "KRW", 0.0,
                 formula="거래상대방 원장이 전량 은행이다 — 청산 익스포저 미보유",
                 citation="LEX30.2(3)", source_module="risk_lib.ccr"),
        FormLine("1330", "면제사유 · 일중 은행간 익스포저", 1, "KRW", 0.0,
                 formula="일중 포지션 원장 미보유 — 파생하지 않는다",
                 citation="LEX30.4", source_module=_M_RDM),
        FormLine("1400", "면제 익스포저 비중", 0, "ratio",
                 exempt_ead / total if total else 0.0,
                 formula="면제 익스포저 ÷ 총 익스포저", source_module=_M_RDM),
        FormLine("2000", "면제대상 동일차주(그룹) 수", 0, "count",
                 float(len(exempt_grp)),
                 formula=f"전체 {len(lc['group'])}개 그룹 중",
                 citation="LEX30.2", source_module=_M_LIM, is_subtotal=True),
    ]
    codes = []
    for i, (_, row) in enumerate(exempt_grp.iterrows(), start=1):
        code = f"{2000 + i * 10}"
        codes.append(code)
        L.append(FormLine(code, f"면제 동일차주 · {row['_gid']}", 1, "KRW",
                          float(row["ead"]),
                          formula=(f"기본자본 대비 {float(row['ead']) / tier1:.2%} · "
                                   f"차주 {int(row['n_obligor'])}인"),
                          citation="LEX30.2(1)", source_module=_M_LIM))
    L.append(FormLine("9000", "면제 판정 비고", 0, "text", None,
                      text_value="전액이 국가·중앙은행 익스포저인 동일차주 그룹만 "
                                 "면제로 분류했다. 섞여 있으면 규제대상(B3120)에 "
                                 "남긴다 — 면제 범위를 넓게 잡으면 한도가 헐거워진다.",
                      citation="LEX30.2"))
    checks = [
        FormCheck("총 익스포저 = 규제대상 + 면제", total,
                  _val(L, "1200") + _val(L, "1300"), 1.0),
        _sum_check("면제 합계 = 면제사유별 합", L, "1300",
                   ("1310", "1320", "1330"), 1.0),
        _sum_check("면제 합계 = 면제 동일차주별 합", L, "1300", tuple(codes), 1.0),
        _ratio_check("면제 비중 = 면제 ÷ 총 익스포저", L, "1400", "1300", "1100",
                     1e-9),
        FormCheck("면제대상 동일차주 수 = 명세 건수", float(len(exempt_grp)),
                  _val(L, "2000"), 1e-9),
    ]
    return L, checks


# ---------------------------------------------------------------- B3122

def _b3122(ctx):
    """주요 변동원인 — 전기 대비 보통주자본비율 변동을 자본·RWA 요인으로 분해.

    당기 수치는 전부 산출값이고 전기 수치만 파생이다. 그래서 요인 합계 대사는
    파생 난수끼리의 자기충족이 아니라 분해 항등식 검증이 된다.
    """
    r = ctx.result
    comp = r.attribution["rwa_components"]
    head = r.attribution["cet1_headroom"]
    cet1 = float(r.meta["capital"].cet1)
    rwa = float(comp["rwa"].sum())
    prev = prior_period(cet1, comp)
    ratio, ratio_0 = cet1 / rwa, prev["cet1"] / prev["rwa"]
    d_cap = (cet1 - prev["cet1"]) / prev["rwa"]
    d_rwa = prev["cet1"] * (1.0 / rwa - 1.0 / prev["rwa"])
    d_cross = (cet1 - prev["cet1"]) * (1.0 / rwa - 1.0 / prev["rwa"])
    L = [
        FormLine("1000", "당기말 보통주자본비율", 0, "ratio", ratio,
                 formula="보통주자본 ÷ 위험가중자산",
                 citation="은행업감독규정 제26조", source_module=_M_CAP),
        FormLine("1010", "전기말 보통주자본비율", 0, "ratio", ratio_0,
                 formula=f"{_DERIVED} (전기말 원장 미보유)", source_module=_M_DER),
        FormLine("1020", "비율 변동폭", 0, "ratio", ratio - ratio_0,
                 formula="당기말 − 전기말", source_module=_M_DER,
                 is_subtotal=True),
        # 세 요인은 모두 전기말 파생값에 의존한다. source_module을 attribution
        # 으로 두면 산출 모듈이 낸 요인분해처럼 보인다 — 파생 의존을 라인에 남긴다.
        FormLine("1100", "변동원인 · 자본 요인", 1, "ratio", d_cap,
                 formula=f"보통주자본 증감 ÷ 전기말 위험가중자산 "
                         f"(전기말 값은 {_DERIVED})",
                 citation="자본비율 변동 요인분해", source_module=_M_DER),
        FormLine("1200", "변동원인 · 위험가중자산 요인", 1, "ratio", d_rwa,
                 formula=f"전기말 보통주자본 × (1/당기 RWA − 1/전기 RWA) "
                         f"(전기말 값은 {_DERIVED})",
                 source_module=_M_DER),
        FormLine("1300", "변동원인 · 교차항", 1, "ratio", d_cross,
                 formula=f"보통주자본 증감 × (1/당기 RWA − 1/전기 RWA) "
                         f"(전기말 값은 {_DERIVED})",
                 source_module=_M_DER),
        FormLine("2000", "당기말 보통주자본", 0, "KRW", cet1,
                 citation="CRE40.1~40.26", source_module=_M_CAP,
                 is_subtotal=True),
        FormLine("2010", "전기말 보통주자본", 0, "KRW", prev["cet1"],
                 formula=_DERIVED, source_module=_M_DER),
        FormLine("2020", "보통주자본 증감", 0, "KRW", cet1 - prev["cet1"],
                 formula="당기말 − 전기말", source_module=_M_DER),
        FormLine("3000", "당기말 위험가중자산", 0, "KRW", rwa,
                 formula="구성요소 합계", citation="CRE20.1 · RBC20",
                 source_module=_M_ATT, is_subtotal=True),
        FormLine("3010", "전기말 위험가중자산", 0, "KRW", prev["rwa"],
                 formula=_DERIVED, source_module=_M_DER),
        FormLine("3020", "위험가중자산 증감", 0, "KRW", rwa - prev["rwa"],
                 formula="당기말 − 전기말", source_module=_M_DER),
    ]
    delta_codes = []
    for i, ((_, row), p0) in enumerate(zip(comp.iterrows(), prev["components"]),
                                       start=1):
        base = 4000 + i * 100
        delta_codes.append(str(base + 20))
        L += [
            FormLine(str(base), f"구성 · {row['component']} — 당기말", 1, "KRW",
                     float(row["rwa"]),
                     formula=f"구성비 {float(row['share']):.2%}",
                     citation="CRE20 · CRE31 · MAR40 · OPE25",
                     source_module=_M_ATT),
            FormLine(str(base + 10), f"구성 · {row['component']} — 전기말", 2,
                     "KRW", float(p0), formula=_DERIVED, source_module=_M_DER),
            FormLine(str(base + 20), f"구성 · {row['component']} — 증감", 2, "KRW",
                     float(row["rwa"]) - float(p0), formula="당기말 − 전기말",
                     source_module=_M_DER),
        ]
    for i, (_, row) in enumerate(head.iterrows(), start=1):
        base = 5000 + i * 100
        L += [
            FormLine(str(base), f"규제요구 · {row['layer']}", 1, "ratio",
                     float(row["required"]),
                     citation="은행업감독규정 제26조·제26조의2~4",
                     source_module=_M_ATT),
            FormLine(str(base + 10), f"헤드룸 · {row['layer']}", 2, "ratio",
                     float(row["headroom"]), formula="실적 비율 − 요구 비율",
                     source_module=_M_ATT),
        ]
    checks = [
        FormCheck("비율 변동 = 자본요인 + RWA요인 + 교차항", ratio - ratio_0,
                  d_cap + d_rwa + d_cross, 1e-12),
        FormCheck("보통주자본 증감 = 당기 − 전기", cet1 - prev["cet1"],
                  _val(L, "2020"), 1.0),
        FormCheck("위험가중자산 증감 = 당기 − 전기", rwa - prev["rwa"],
                  _val(L, "3020"), 1.0),
        _sum_check("RWA 증감 = 구성요소별 증감 합", L, "3020",
                   tuple(delta_codes), 1.0),
        # 요인분해가 산출 RWA와 다른 총계를 쓰면 변동 설명이 통째로 어긋난다.
        FormCheck("당기말 RWA = 산출 위험가중자산 합계",
                  float(r.rwa["final_total"]), rwa, 1.0),
        _ratio_check("전기말 보통주자본비율 = 전기 자본 ÷ 전기 RWA", L, "1010",
                     "2010", "3010", 1e-12),
        FormCheck("비율 변동폭 = 당기말 − 전기말", ratio - ratio_0,
                  _val(L, "1020"), 1e-12),
    ]
    for i, (_, row) in enumerate(head.iterrows(), start=1):
        checks.append(FormCheck(
            f"헤드룸({row['layer']}) = 실적 − 요구",
            float(row["actual"]) - float(row["required"]),
            _val(L, str(5000 + i * 100 + 10)), 1e-12))
    return L, checks


# ---------------------------------------------------------------- B3221

def _b3221(ctx):
    """거액신용공여 현황요약표 — 명세표(B3222·B3223) 합계와 대사한다."""
    lc = _large_credit(ctx)
    own, large = lc["own"], lc["large"]
    managed, exempt = lc["managed"], lc["exempt"]
    total = float(large["ead"].sum())
    L = [
        FormLine("1000", "자기자본", 0, "KRW", own,
                 citation="은행법 제2조 제1항 제5호", source_module=_M_CAP),
        FormLine("1100", "거액신용공여 기준금액", 0, "KRW", own * 0.10,
                 formula="자기자본 × 10%", citation=_C35_4, source_module=_M_LIM),
    ]
    block, checks = _limit_block(
        2000, "거액신용공여 합계", total, own, 5.00, _C35_4,
        f"기준금액 초과 동일차주 {len(large)}개 합계", _M_LIM)
    L += block
    L += [
        FormLine("2100", "관리대상 소계", 1, "KRW", float(managed["ead"].sum()),
                 formula=f"동일차주 {len(managed)}개",
                 citation="은행법 제35조 제4항 — 한도 산정 대상",
                 source_module=_M_LIM, is_subtotal=True),
        FormLine("2200", "제외대상 소계", 1, "KRW", float(exempt["ead"].sum()),
                 formula=f"동일차주 {len(exempt)}개",
                 citation="은행법 시행령 제20조의5 — 국가·중앙은행 등 한도 산정 제외",
                 source_module=_M_LIM, is_subtotal=True),
        FormLine("2300", "관리대상 기준 소진율", 1, "ratio",
                 float(managed["ead"].sum()) / (own * 5.0),
                 formula="관리대상 소계 ÷ (자기자본 × 5배)", source_module=_M_LIM),
        # 2030(한도 내 여부)은 제외대상을 포함한 총계 기준이다. 규정상 판정은
        # 한도 산정 대상만으로 해야 하므로 판정 라인을 따로 남긴다.
        FormLine("2310", "관리대상 기준 한도 내 여부", 1, "count",
                 1.0 if float(managed["ead"].sum()) <= own * 5.0 + 1e-6 else 0.0,
                 formula="1 = 한도 내, 0 = 한도 초과 — 규정상 판정은 이 라인이다",
                 citation="은행법 제35조 제4항 · 은행법 시행령 제20조의5",
                 source_module=_M_LIM),
        FormLine("3000", "거액신용공여 대상 동일차주 수", 0, "count",
                 float(len(large)), formula="신용공여 > 자기자본 × 10% 인 그룹 수",
                 citation=_C35_4, source_module=_M_LIM, is_subtotal=True),
        FormLine("3100", "관리대상 동일차주 수", 1, "count", float(len(managed)),
                 formula="명세는 B3222", citation="은행법 제35조 제4항",
                 source_module=_M_LIM),
        FormLine("3200", "제외대상 동일차주 수", 1, "count", float(len(exempt)),
                 formula="명세는 B3223", citation="은행법 시행령 제20조의5",
                 source_module=_M_LIM),
        FormLine("4000", "동일차주 한도(자기자본 25%) 초과 그룹 수", 0, "count",
                 float(int((large["utilisation_25pct"] > 1.0).sum())),
                 citation=_C35, source_module=_M_LIM),
    ]
    checks += [
        _sum_check("거액신용공여 합계 = 관리대상 + 제외대상", L, "2000",
                   ("2100", "2200"), 1.0),
        _sum_check("대상 동일차주 수 = 관리 + 제외", L, "3000",
                   ("3100", "3200"), 1e-9),
        FormCheck("거액신용공여 기준금액 = 자기자본 × 10%", own * 0.10,
                  _val(L, "1100"), 1.0),
        _ratio_check("관리대상 소진율 = 관리대상 소계 ÷ 한도금액", L, "2300",
                     "2100", "2010", 1e-9),
        FormCheck("관리대상 기준 한도 내 여부 = 소진율 ≤ 1",
                  1.0 if _val(L, "2300") <= 1.0 + 1e-9 else 0.0,
                  _val(L, "2310"), 1e-9),
    ]
    return L, checks


# ---------------------------------------------------------------- B3222 / B3223

def _large_credit_detail(ctx, *, exempt: bool):
    """거액신용공여 현황명세표 — 관리대상/제외대상 공용 편제."""
    lc = _large_credit(ctx)
    own = lc["own"]
    sel = lc["exempt"] if exempt else lc["managed"]
    label = "제외대상" if exempt else "관리대상"
    cite = ("은행법 시행령 제20조의5 — 국가·중앙은행 등에 대한 신용공여는 "
            "한도 산정에서 제외" if exempt else
            "은행법 제35조 제4항 — 자기자본 10% 초과 신용공여 한도 산정 대상")
    total = float(sel["ead"].sum())
    L = [
        FormLine("1000", f"{label} 신용공여 합계", 0, "KRW", total,
                 formula=f"동일차주 {len(sel)}개", citation=cite,
                 source_module=_M_LIM, is_subtotal=True),
        FormLine("1100", f"{label} 동일차주 수", 0, "count", float(len(sel)),
                 formula="아래 명세 건수와 같아야 한다", citation=cite,
                 source_module=_M_LIM),
        # 거액신용공여 한도는 자기자본의 5"배"라 이 값은 비율이 아니라 배수다.
        # ratio로 담으면 엑셀이 553%로 표시하고 서식 단위 어휘와도 어긋난다.
        FormLine("1200", "자기자본 대비 배수", 0, "count",
                 total / own if own else 0.0,
                 formula="합계 ÷ 자기자본 (단위: 배)", citation=_C35_4,
                 source_module=_M_LIM),
    ]
    codes = []
    for i, (_, row) in enumerate(sel.iterrows(), start=1):
        code = f"{2000 + i * 10}"
        codes.append(code)
        L.append(FormLine(code, f"동일차주 · {row['_gid']}", 1, "KRW",
                          float(row["ead"]),
                          formula=(f"자기자본 대비 {float(row['pct_own']):.2%} · "
                                   f"25% 한도 소진 {float(row['utilisation_25pct']):.1%} · "
                                   f"차주 {int(row['n_obligor'])}인 · "
                                   f"익스포저 {int(row['n_exposure']):,}건"),
                          citation=cite, source_module=_M_LIM))
    L.append(FormLine("3000", "동일차주 한도(25%) 초과 건수", 0, "count",
                      float(int((sel["utilisation_25pct"] > 1.0).sum())),
                      citation=_C35, source_module=_M_LIM, is_subtotal=True))
    L.append(FormLine("9000", "구분 기준 비고", 0, "text", None,
                      text_value=("전액이 국가·중앙은행 익스포저인 동일차주 그룹만 "
                                  "제외대상으로 분류한다. 일부만 국가 익스포저인 "
                                  "그룹은 관리대상에 남긴다."),
                      citation=cite))
    checks = [
        _sum_check(f"{label} 합계 = 동일차주별 합", L, "1000", tuple(codes), 1.0),
        FormCheck("자기자본 대비 배수 = 합계 ÷ 자기자본", total / own,
                  _val(L, "1200"), 1e-12),
        FormCheck(f"{label} 동일차주 수 = 명세 건수", float(len(sel)),
                  _val(L, "1100"), 1e-9),
    ]
    return L, checks


def _b3222(ctx):
    return _large_credit_detail(ctx, exempt=False)


def _b3223(ctx):
    return _large_credit_detail(ctx, exempt=True)


# ---------------------------------------------------------------- 등록

BUILDERS: dict[str, tuple[str, str, Callable]] = {
    "B3000": ("은행법 제35조의2·제35조의3 · 제38조 제6호", "PRD-RDM", _b3000),
    "B3101": ("은행업감독규정 제26조 · Basel III CRE40 (구 바젤 편제)", "PRD-CAP",
              _b3101),
    "B3103": ("은행법 제35조·제35조의2·제35조의3·제37조·제38조", "PRD-RDM", _b3103),
    "B3104": ("은행법 제35조·제37조·제38조 (특수은행 근거법 준용)", "PRD-RDM",
              _b3104),
    "B3110": ("은행법 제37조 제2항 — 자회사 출자 한도", "PRD-RDM", _b3110),
    "B3111": ("은행법 제37조 제3항 — 자회사 신용공여 한도", "PRD-RDM", _b3111),
    "B3112": ("은행법 제38조 제2호 · 상법 제341조 · Basel III CRE40.20", "PRD-CAP",
              _b3112),
    "B3113": ("은행법 제37조 제1항 · 제38조 제1호", "PRD-RDM", _b3113),
    "B3114": ("은행업감독규정 제30조의2 · 금융회사의 업무위탁 등에 관한 규정",
              "PRD-RDM", _b3114),
    "B3116": ("은행법 제33조 — 금융채 발행 · 은행업감독규정 제99조", "PRD-ALM",
              _b3116),
    "B3117": ("은행법 제33조 · Basel III NSF20 잔존만기 편제", "PRD-ALM", _b3117),
    "B3118": ("은행법 제33조 — 금융채 발행", "PRD-ALM", _b3118),
    "B3119": ("은행법 제38조 제6호 · 은행업감독규정 제55조", "PRD-RDM", _b3119),
    "B3121": ("Basel III LEX30.2 — 거액익스포저 한도 적용 제외", "PRD-RDM", _b3121),
    "B3122": ("은행업감독규정 제26조 · 자본비율 변동 요인분해", "PRD-CAP", _b3122),
    "B3220": ("은행법 제38조 제6호 · 은행업감독규정 제55조", "PRD-RDM", _b3220),
    "B3221": ("은행법 제35조 제4항 · Basel III LEX10", "PRD-RDM", _b3221),
    "B3222": ("은행법 제35조 제4항 — 한도 산정 대상", "PRD-RDM", _b3222),
    "B3223": ("은행법 시행령 제20조의5 — 한도 산정 제외", "PRD-RDM", _b3223),
}
