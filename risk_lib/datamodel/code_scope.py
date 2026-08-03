"""계정·상품 코드 마스터와 리스크별 대상·특성 매핑.

계정코드·상품코드가 **어느 리스크의 모집단에 들어가는가**는 산출의 첫 관문이다.
매핑이 없으면 코드 하나가 조용히 모든 산출에서 빠지고, 그 누락은 어떤 대사도
잡지 못한다 — 대사는 들어온 것끼리 비교하기 때문이다.

배치 원칙(사용자 지정): **공통 특성은 RDM**(rdm_account_master ·
rdm_product_master), **리스크별 대상·특성은 각 리스크 스키마**(crm_code_scope ·
mkt_code_scope · alm_code_scope · opr_code_scope).

대상여부는 특성에서 **규칙으로 파생**한다 — 코드별로 손으로 적으면 신규 코드가
기본값 없이 들어와 조용히 제외된다. 규칙은 이 파일에 열거돼 있고, 예외는
매핑 화면에서 제안으로만 만든다. 전부 합성 마스터다(SYNTHETIC).
"""

from __future__ import annotations

import pandas as pd

# ---------------------------------------------------------------- 공통 마스터

# (계정코드, 명칭, 계정군, 재무제표, 부내/부외, 금리부 여부)
ACCOUNTS = (
    ("1100", "현금 및 예치금", "예치금", "자산", "부내", True),
    ("1210", "국공채", "유가증권", "자산", "부내", True),
    ("1220", "회사채", "유가증권", "자산", "부내", True),
    ("1230", "주식", "유가증권", "자산", "부내", False),
    ("1240", "파생상품자산", "파생", "자산", "부내", True),
    ("1310", "기업대출", "대출채권", "자산", "부내", True),
    ("1320", "가계대출", "대출채권", "자산", "부내", True),
    ("1330", "주택담보대출", "대출채권", "자산", "부내", True),
    ("1340", "신용카드채권", "대출채권", "자산", "부내", False),
    ("1400", "대손충당금", "충당금", "자산차감", "부내", False),
    ("1500", "유형자산", "고정자산", "자산", "부내", False),
    ("2100", "요구불예금", "예수금", "부채", "부내", True),
    ("2110", "저축성예금", "예수금", "부채", "부내", True),
    ("2200", "차입금", "차입", "부채", "부내", True),
    ("2300", "사채", "발행채", "부채", "부내", True),
    ("2400", "파생상품부채", "파생", "부채", "부내", True),
    ("3100", "자본금", "자본", "자본", "부내", False),
    ("9100", "지급보증", "우발", "부외", "부외", False),
    ("9200", "미사용약정", "우발", "부외", "부외", False),
    ("9300", "차입약정", "우발", "부외", "부외", False),
)

# (상품코드, 명칭, 상품군, 트레이딩/뱅킹, 통화성, 담보성)
PRODUCTS = (
    ("P-DEP", "예금", "수신", "뱅킹", "원화", False),
    ("P-FXD", "외화예금", "수신", "뱅킹", "외화", False),
    ("P-LNC", "기업여신", "여신", "뱅킹", "원화", True),
    ("P-LNR", "가계여신", "여신", "뱅킹", "원화", True),
    ("P-MTG", "주택담보여신", "여신", "뱅킹", "원화", True),
    ("P-CRD", "신용카드", "여신", "뱅킹", "원화", False),
    ("P-BND", "채권운용", "운용", "트레이딩", "원화", False),
    ("P-EQT", "주식운용", "운용", "트레이딩", "원화", False),
    ("P-IRS", "금리스왑", "파생", "트레이딩", "원화", False),
    ("P-FXS", "통화스왑", "파생", "트레이딩", "외화", False),
    ("P-OPT", "옵션", "파생", "트레이딩", "외화", False),
    ("P-GUA", "지급보증", "보증", "뱅킹", "원화", False),
    ("P-CMT", "한도약정", "약정", "뱅킹", "원화", False),
    ("P-REPO", "환매조건부매매", "자금", "트레이딩", "원화", False),
    ("P-CALL", "콜론·콜머니", "자금", "뱅킹", "원화", False),
)


def account_master() -> pd.DataFrame:
    return pd.DataFrame(ACCOUNTS, columns=[
        "account_code", "account_name", "account_group", "statement",
        "on_balance", "rate_bearing"])


def product_master() -> pd.DataFrame:
    return pd.DataFrame(PRODUCTS, columns=[
        "product_code", "product_name", "product_group", "book",
        "currency_type", "collateralised"])


# ------------------------------------------------------- 리스크별 대상 규칙
# 규칙이 정본이다 — 코드별 예외는 매핑 화면의 제안으로만 만든다.

# 계정군 → 바젤 자산군 — SA 위험가중 곡선·IRB 상관계수의 입력이 된다.
_ACCT_ASSET_CLASS = {
    "1100": "bank", "1210": "sovereign", "1220": "corporate",
    "1240": "corporate", "1310": "corporate", "1320": "retail_other",
    "1330": "residential_mortgage", "1340": "retail_other",
}
# 부외 계정 → CCF 유형 — 요율은 엔진(capital.crm.CCF_BUCKETS)에서 읽는다.
_ACCT_CCF = {
    "9100": "direct_credit_substitute",
    "9200": "unconditionally_cancellable",
    "9300": "commitment_gt_1y",
}


def credit_scope(tables: dict | None = None) -> pd.DataFrame:
    """신용리스크 — 대상·특성이 산출 엔진과 같은 상수·같은 모집단을 본다.

    CCF 요율은 `capital.crm.CCF_BUCKETS`, 위험가중 범위는
    `capital.rwa_sa.SA_RISK_WEIGHTS`에서 직접 읽는다 — 화면에 따로 적으면
    엔진이 바뀔 때 매핑만 낡는다. tables 를 주면 자산군 매핑을 통해 실제
    포트폴리오 모집단(익스포저 건수·EAD 합)을 실측으로 붙인다.
    """
    from risk_lib.capital.crm import CCF_BUCKETS
    from risk_lib.capital.rwa_sa import SA_RISK_WEIGHTS

    pop = None
    if tables is not None and "rdm_exposure" in tables:
        exp = tables["rdm_exposure"]
        pop = exp.groupby("asset_class").agg(
            n=("exposure_id", "count"), ead=("ead", "sum"))

    rows = []
    for c, name, grp, st, onb, _ in ACCOUNTS:
        in_scope = grp in ("대출채권", "유가증권", "예치금", "파생") or onb == "부외"
        ac = _ACCT_ASSET_CLASS.get(c)
        ccf_t = _ACCT_CCF.get(c)
        rw = SA_RISK_WEIGHTS.get(ac) if ac else None
        rw_range = (f"{min(rw.values())*100:.0f}~{max(rw.values())*100:.0f}%"
                    if isinstance(rw, dict) else
                    "LTV 구간별" if ac == "residential_mortgage" else
                    "75%" if ac == "retail_other" else "—")
        n_exp, ead = 0, 0.0
        if pop is not None and ac in pop.index:
            n_exp, ead = int(pop.loc[ac, "n"]), float(pop.loc[ac, "ead"])
        rows.append({
            "account_code": c, "in_scope": in_scope,
            "asset_class": ac or "—",
            "approach": "SA+IRB" if in_scope and ac else ("SA" if in_scope else "—"),
            "ccf_type": ccf_t or "—",
            "ccf_rate": CCF_BUCKETS[ccf_t] if ccf_t else None,
            "rw_range": rw_range if in_scope else "—",
            "n_exposures": n_exp, "ead_total": ead,
            "reason": ("여신·채권·거래상대방 익스포저" if in_scope
                       else f"{grp} — 신용 익스포저 아님"),
            "ead_basis": ("CCF 환산" if onb == "부외"
                          else "장부가" if in_scope else "—"),
            "default_recognition": "90일 연체" if grp == "대출채권" else
                                   ("거래상대방 부도" if in_scope else "—"),
        })
    return pd.DataFrame(rows)


# 상품 → 트레이딩 거래 유형 — mkt_trade.kind 와 같은 어휘라 실측 조인이 된다.
_PROD_TRADE_KIND = {"P-IRS": "swap", "P-FXS": "swap", "P-OPT": "option"}
_PROD_FRTB = {"P-BND": "GIRR", "P-EQT": "EQ", "P-IRS": "GIRR",
              "P-FXS": "FX", "P-OPT": "FX", "P-REPO": "GIRR"}


def market_scope(tables: dict | None = None) -> pd.DataFrame:
    """시장리스크 — FRTB 위험군과 실제 거래 원장 건수를 붙인다."""
    kinds = None
    if tables is not None and "mkt_trade" in tables:
        kinds = tables["mkt_trade"].groupby("kind")["trade_id"].count()
    rows = []
    for c, name, grp, book, cur, _ in PRODUCTS:
        in_scope = book == "트레이딩"
        tk = _PROD_TRADE_KIND.get(c)
        n_tr = int(kinds.get(tk, 0)) if (kinds is not None and tk) else 0
        rows.append({
            "product_code": c, "in_scope": in_scope,
            "frtb_class": _PROD_FRTB.get(c, "—") if in_scope else "—",
            "trade_kind": tk or "—",
            "n_trades": n_tr,
            "reason": ("트레이딩 북" if in_scope else "뱅킹 북 — IRRBB 소관"),
            "risk_factor": ("금리" if grp in ("파생", "자금") or c == "P-BND"
                            else "주가" if c == "P-EQT"
                            else "환율" if cur == "외화" else "—") if in_scope else "—",
            "fx_exposed": cur == "외화",
        })
    return pd.DataFrame(rows)


# 계정 → LCR 원장 category — alm_lcr_item 과 같은 어휘라 적용률을 실측 조인.
_ACCT_LCR = {
    "1210": "Level 1", "1220": "Level 2A", "1230": "Level 2B",
    "2100": "retail_less_stable", "2110": "retail_stable",
    "2200": "wholesale_fi_unsecured", "2300": "corporate_non_operational",
    "9200": "committed_facilities",
    "1310": "wholesale_inflows", "1320": "retail_inflows",
    "1330": "retail_inflows", "1100": "fi_inflows",
}


def alm_scope(tables: dict | None = None) -> pd.DataFrame:
    """ALM — LCR 적용률을 산출 원장(alm_lcr_item)에서 직접 읽는다."""
    fac = None
    if tables is not None and "alm_lcr_item" in tables:
        li = tables["alm_lcr_item"]
        fac = dict(zip(li["category"], li["factor"]))
    rows = []
    for c, name, grp, st, onb, rate in ACCOUNTS:
        cat_lcr = _ACCT_LCR.get(c, "—")
        rows.append({
            "account_code": c, "irrbb_scope": bool(rate),
            "liquidity_scope": onb == "부내" and st in ("자산", "부채"),
            "repricing_bucket": ("3개월 이내" if grp in ("예치금", "자금", "예수금")
                                 else "1년 이내" if rate else "—"),
            "lcr_category": cat_lcr,
            "lcr_factor": (float(fac[cat_lcr]) if fac and cat_lcr in fac
                           else float("nan")),
        })
    return pd.DataFrame(rows)


def op_scope(tables: dict | None = None) -> pd.DataFrame:
    """운영리스크 — 산출방법과 손실사건 실측 건수를 붙인다. 제외는 없다."""
    method, n_by_type = "—", None
    if tables is not None:
        if "opr_capital" in tables and len(tables["opr_capital"]):
            method = str(tables["opr_capital"]["method"].iloc[0])
        if "opr_loss_event" in tables:
            n_by_type = tables["opr_loss_event"].groupby(
                "event_type")["event_id"].count()
    rows = []
    for c, name, grp, book, _, _ in PRODUCTS:
        ev = ("execution_delivery" if grp in ("여신", "수신", "약정", "보증")
              else "execution_delivery")
        rows.append({
            "product_code": c, "in_scope": True,
            "event_mapping": ev,
            "n_events": int(n_by_type.get(ev, 0)) if n_by_type is not None else 0,
            "capital_method": method,
            "bia_line": "은행업무" if book == "뱅킹" else "트레이딩·판매",
        })
    return pd.DataFrame(rows)
