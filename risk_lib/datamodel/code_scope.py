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

def credit_scope() -> pd.DataFrame:
    """신용리스크 — 여신성·채권성 자산과 부외 약정이 대상이다."""
    rows = []
    for c, name, grp, st, onb, _ in ACCOUNTS:
        in_scope = grp in ("대출채권", "유가증권", "예치금", "파생") or onb == "부외"
        rows.append({
            "account_code": c, "in_scope": in_scope,
            "reason": ("여신·채권·거래상대방 익스포저" if in_scope
                       else f"{grp} — 신용 익스포저 아님"),
            "ead_basis": ("CCF 환산" if onb == "부외"
                          else "장부가" if in_scope else "—"),
            "default_recognition": "90일 연체" if grp == "대출채권" else
                                   ("거래상대방 부도" if in_scope else "—"),
        })
    return pd.DataFrame(rows)


def market_scope() -> pd.DataFrame:
    """시장리스크 — 트레이딩 북 상품이 대상이다 (경계는 MAR 규정)."""
    rows = []
    for c, name, grp, book, cur, _ in PRODUCTS:
        in_scope = book == "트레이딩"
        rows.append({
            "product_code": c, "in_scope": in_scope,
            "reason": ("트레이딩 북" if in_scope else "뱅킹 북 — IRRBB 소관"),
            "risk_factor": ("금리" if grp in ("파생", "자금") or c == "P-BND"
                            else "주가" if c == "P-EQT"
                            else "환율" if cur == "외화" else "—") if in_scope else "—",
            "fx_exposed": cur == "외화",
        })
    return pd.DataFrame(rows)


def alm_scope() -> pd.DataFrame:
    """ALM — 금리부 계정이 IRRBB 대상, 전 부내 계정이 유동성 대상이다."""
    rows = []
    for c, name, grp, st, onb, rate in ACCOUNTS:
        rows.append({
            "account_code": c, "irrbb_scope": bool(rate),
            "liquidity_scope": onb == "부내" and st in ("자산", "부채"),
            "repricing_bucket": ("3개월 이내" if grp in ("예치금", "자금", "예수금")
                                 else "1년 이내" if rate else "—"),
            "lcr_category": ("HQLA" if grp == "유가증권" and c == "1210"
                             else "유출" if st == "부채"
                             else "유입" if st == "자산" else "—"),
        })
    return pd.DataFrame(rows)


def op_scope() -> pd.DataFrame:
    """운영리스크 — 전 상품이 손실사건 매핑 대상이다 (제외는 없다)."""
    rows = []
    for c, name, grp, book, _, _ in PRODUCTS:
        rows.append({
            "product_code": c, "in_scope": True,
            "event_mapping": ("실행·전달·프로세스" if grp in ("여신", "수신")
                              else "시장 실무" if book == "트레이딩"
                              else "실행·전달·프로세스"),
            "bia_line": "은행업무" if book == "뱅킹" else "트레이딩·판매",
        })
    return pd.DataFrame(rows)
