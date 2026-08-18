"""NSFR — 순안정자금조달비율 (Basel NSF20/30, 은행업감독규정 제26조).

NSFR = ASF(부채측 × 가용안정자금 인정률) / RSF(자산측 × 필요안정자금 소요율)
     ≥ 100%

**무엇을 고치는가.** 만기 분할이 산식 한가운데 박혀 있었다 —
`balance_sheet.py`가 은행 여신을 `×0.4`(6개월 이내) / `×0.6`(1년 이상)으로
나눴고 그 0.4/0.6에는 근거가 없다. 결과적으로 잔존 5년 은행 여신의 40%가
RSF 15% 가중을 받았다. 만기 구간 경계(6개월·1년)는 규제가 정하는 값이므로
`alm_nsfr_factor` 원장의 `band_lower_years`·`band_upper_years` 컬럼으로 옮기고,
분할은 계약·포트폴리오의 **실제 잔존만기**로 한다.

**국내 채택 미확인.** 총 파생부채에 대한 RSF(재량 5~20%)와 상호의존 자산·부채
예외(NSF30, 정책자금·주택금융공사 유동화 구조가 쟁점)는 국내 적용 여부를
확인하지 못했다. 계수를 NULL로 두고 엔진이 가중하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from risk_lib.alm.balance_sheet import BalanceSheet
from risk_lib.alm.params import EVIDENCE_STATUS
from risk_lib.datamodel.spec import ColumnSpec as C, ForeignKey as FK, TableSpec
from risk_lib.references import NSFR_MIN, NSFR_ASF_FACTORS, NSFR_RSF_FACTORS

__all__ = [
    "NSFR_SECTIONS", "NSFR_FACTOR", "NSFR_ITEM", "NSFR_TABLES",
    "NSFRResult", "NSFRItemResult",
    "build_nsfr_factor", "build_nsfr_item", "maturity_band_of",
    "nsfr_balances_from_balance_sheet", "compute_nsfr",
]

NSFR_SECTIONS: tuple[str, ...] = ("ASF", "RSF")


# ---------------------------------------------------------------- 스펙

NSFR_FACTOR = TableSpec(
    name="alm_nsfr_factor", korean="NSFR 계수 원장", product="PRD-ALM",
    grain="계정 × 구분 × 항목 1행",
    columns=(
        C("framework", "string", "계정", nullable=False),
        C("section", "string", "구분", nullable=False, allowed=NSFR_SECTIONS,
          citation="NSF20(ASF) · NSF30(RSF)"),
        C("category", "string", "항목", nullable=False),
        C("factor", "float", "인정률·소요율", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0,
          note="NULL이면 국내 채택 여부 미확인 — 엔진이 가중하지 않는다"),
        C("maturity_band", "string", "잔존만기 구간", nullable=True),
        C("band_lower_years", "float", "구간 하한", nullable=True,
          unit="years", min_value=0.0),
        C("band_upper_years", "float", "구간 상한", nullable=True,
          unit="years", min_value=0.0,
          note="만기 분할 경계는 규제가 정한다. 0.4/0.6 같은 임의 비율로 "
               "나누면 잔존 5년 여신이 6개월 소요율을 받는다"),
        C("interdependent_flag", "bool", "상호의존 예외", nullable=False,
          citation="BCBS d295 NSF30 — 상호의존 자산·부채는 ASF·RSF 0% 적용 "
                   "가능. 국내 승인사례·적용조건 미확인이므로 전 행 False"),
        C("citation", "text", "근거", nullable=True),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("framework", "section", "category"),
)

NSFR_ITEM = TableSpec(
    name="alm_nsfr_item", korean="NSFR 항목별 내역", product="PRD-ALM",
    grain="기준일 × 구분 × 항목 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("section", "string", "구분", nullable=False, allowed=NSFR_SECTIONS,
          citation="NSF20(ASF) · NSF30(RSF)"),
        C("category", "string", "항목", nullable=False),
        C("amount", "float", "잔액", nullable=False, unit="KRW",
          min_value=0.0),
        C("factor", "float", "인정률·소요율", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("weighted", "float", "가중 후 금액", nullable=False, unit="KRW",
          min_value=0.0),
        C("maturity_band", "string", "잔존만기 구간", nullable=True),
        C("citation", "text", "근거", nullable=True),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("asof", "section", "category"),
    foreign_keys=(FK(("section", "category"), "alm_nsfr_factor",
                     ("section", "category")),),
    note="계수가 비어 있는 항목은 이 장에 실리지 않는다 — 가중하지 못한 것을 "
         "0으로 실으면 비율이 실제보다 좋아진다. 공백은 alm_nsfr_factor에서 "
         "읽는다.",
)

NSFR_TABLES: tuple[TableSpec, ...] = (NSFR_FACTOR, NSFR_ITEM)


# ---------------------------------------------------------------- 계수 원장

# 만기 구간(년). 경계는 규제가 정하고 여기서 원장으로 나간다.
_BANDS: dict[str, tuple[str, float, float | None]] = {
    "capital":             ("1년 이상", 1.0, None),
    "retail_stable":       ("1년 미만(비만기 포함)", 0.0, 1.0),
    "retail_less_stable":  ("1년 미만(비만기 포함)", 0.0, 1.0),
    "corporate_lt1y":      ("1년 미만", 0.0, 1.0),
    "wholesale_fi_lt6m":   ("6개월 미만", 0.0, 0.5),
    "wholesale_fi_6to12m": ("6개월 이상 1년 미만", 0.5, 1.0),
    "funding_gt1y":        ("1년 이상", 1.0, None),
    "loans_fi_lt6m":       ("6개월 미만", 0.0, 0.5),
    "loans_fi_6to12m":     ("6개월 이상 1년 미만", 0.5, 1.0),
    "loans_lt1y":          ("1년 미만", 0.0, 1.0),
    "mortgages_ge1y":      ("1년 이상", 1.0, None),
    "other_loans_ge1y":    ("1년 이상", 1.0, None),
}

# 국내 채택 여부를 확인하지 못한 항목. 계수를 비워 두고 등재만 한다.
_UNCONFIRMED: tuple[tuple[str, str, str], ...] = (
    ("RSF", "derivative_liabilities_addon",
     "BCBS d295 NSF30 — 총 파생부채에 대한 RSF 5~20% 관할재량. 국내 채택값 미확인"),
    ("RSF", "interdependent_assets",
     "BCBS d295 NSF30 — 상호의존 자산·부채 예외. 국내 승인사례·적용조건 미확인"),
)


def build_nsfr_factor(*, framework: str = "BCBS_d295") -> pd.DataFrame:
    """NSFR 계수 원장. 규제표를 적재하는 자리는 여기 한 곳이다.

    이미 저장소에 있는 계수(`references.NSFR_*`)는 그대로 읽어 온다 — 별사본을
    만들면 규제 상수가 두 벌이 된다. 새로 넣는 것은 만기 구간 경계와,
    6개월~1년 금융기관 여신(50%) 항목, 그리고 미확인 항목이다.
    """
    rows: list[dict] = []

    def add(section, category, factor, cite, evidence):
        band, lo, hi = _BANDS.get(category, (None, None, None))
        rows.append({
            "framework": framework, "section": section, "category": category,
            "factor": None if factor is None else float(factor),
            "maturity_band": band,
            "band_lower_years": lo, "band_upper_years": hi,
            "interdependent_flag": False,
            "citation": cite, "evidence_status": evidence})

    for cat, f in NSFR_ASF_FACTORS.items():
        add("ASF", cat, f, "BCBS d295 NSF20.4~20.14 — 가용안정자금 인정률",
            "2차자료")
    for cat, f in NSFR_RSF_FACTORS.items():
        add("RSF", cat, f, "BCBS d295 NSF30.4~30.16 — 필요안정자금 소요율",
            "2차자료")
    # 6개월~1년 금융기관 여신. 기존 계수표에 이 구간이 없어 잔존 6~12개월
    # 여신이 6개월 미만(15%)이나 1년 이상(85%)으로 밀려 있었다.
    add("RSF", "loans_fi_6to12m", 0.50,
        "BCBS d295 NSF30.11 — 금융기관 여신 잔존 6개월~1년 50%", "2차자료")
    for section, cat, cite in _UNCONFIRMED:
        add(section, cat, None, cite, "미확인")

    return pd.DataFrame(rows).astype({
        "factor": "float64", "band_lower_years": "float64",
        "band_upper_years": "float64", "interdependent_flag": "bool"})


def maturity_band_of(residual_years, factor: pd.DataFrame,
                     categories: tuple[str, ...]) -> np.ndarray:
    """잔존만기를 원장의 구간 경계로 분류한다.

    `categories`는 후보 항목을 우선순위 순으로 준다. 경계는 `[lower, upper)`
    이며 상한이 NULL이면 개방구간이다. 어디에도 안 걸리면 마지막 후보로
    떨어뜨린다 — 조용히 버리면 자산이 RSF에서 사라진다.
    """
    t = np.asarray(residual_years, dtype=float)
    out = np.full(t.shape, categories[-1], dtype=object)
    assigned = np.zeros(t.shape, dtype=bool)
    fx = factor.set_index("category")
    for cat in categories:
        lo = fx.loc[cat, "band_lower_years"]
        hi = fx.loc[cat, "band_upper_years"]
        lo = 0.0 if pd.isna(lo) else float(lo)
        m = (~assigned) & (t >= lo)
        if not pd.isna(hi):
            m &= t < float(hi)
        out[m] = cat
        assigned |= m
    return out


# ---------------------------------------------------------------- 엔진

@dataclass
class NSFRItemResult:
    item: pd.DataFrame            # alm_nsfr_item
    asf_total: float
    rsf_total: float
    nsfr: float
    skipped: list[str] = field(default_factory=list)

    def passes(self) -> bool:
        return self.nsfr >= NSFR_MIN


def build_nsfr_item(balances: pd.DataFrame, factor: pd.DataFrame, *,
                    asof: str) -> NSFRItemResult:
    """`alm_nsfr_item` — 잔액(원장) × 계수(원장) → NSFR.

    `balances`: (section, category, amount). 계수가 NULL인 항목은 실리지 않고
    `skipped`에 남는다 — 0으로 가중하면 RSF가 줄어 비율이 좋아진다.
    """
    fx = factor.set_index(["section", "category"])
    rows: list[dict] = []
    skipped: list[str] = []
    for _, b in balances.iterrows():
        key = (str(b["section"]), str(b["category"]))
        if key not in fx.index:
            raise KeyError(
                f"alm_nsfr_factor에 {key} 항목이 없다 — 계수 없는 잔액은 "
                "가중할 수 없다")
        fr = fx.loc[key]
        if pd.isna(fr["factor"]):
            skipped.append(f"{key[0]}/{key[1]}")
            continue
        amt = float(b["amount"])
        rows.append({
            "asof": asof, "section": key[0], "category": key[1],
            "amount": amt, "factor": float(fr["factor"]),
            "weighted": amt * float(fr["factor"]),
            "maturity_band": (None if pd.isna(fr["maturity_band"])
                              else str(fr["maturity_band"])),
            "citation": str(fr["citation"]),
            "evidence_status": str(fr["evidence_status"])})

    item = pd.DataFrame(rows, columns=list(NSFR_ITEM.column_names))
    asf_total = float(item.loc[item["section"] == "ASF", "weighted"].sum())
    rsf_total = float(item.loc[item["section"] == "RSF", "weighted"].sum())
    nsfr = asf_total / rsf_total if rsf_total > 0 else float("inf")
    return NSFRItemResult(item=item, asf_total=asf_total, rsf_total=rsf_total,
                          nsfr=nsfr, skipped=skipped)


def nsfr_balances_from_balance_sheet(bs: BalanceSheet) -> pd.DataFrame:
    """합성 재무상태표에서 ASF·RSF 잔액을 뽑는다.

    자산측 분해(`bs.asset_split`)는 이미 포트폴리오 잔존만기로 나뉘어 있다 —
    임의 비율 분할은 `balance_sheet.py`에서 제거했다.
    """
    f = bs.funding
    asf = [
        ("capital", bs.equity),
        ("retail_stable", f["retail_stable"]),
        ("retail_less_stable", f["retail_less_stable"]),
        ("corporate_lt1y",
         f["corporate_operational"] + f["corporate_non_operational"]),
        ("wholesale_fi_lt6m", f["wholesale_fi_lt6m"]),
        ("wholesale_fi_6to12m", f["wholesale_fi_6to12m"]),
        ("funding_gt1y", f["funding_gt1y"]),
    ]
    rows = [{"section": "ASF", "category": c, "amount": float(a)}
            for c, a in asf]
    rows += [{"section": "RSF", "category": c, "amount": float(a)}
             for c, a in bs.asset_split.items()]
    return pd.DataFrame(rows, columns=["section", "category", "amount"])


# ------------------------------------------------- 기존 소비처 호환 래퍼

@dataclass
class NSFRResult:
    asf: pd.DataFrame           # category, amount, factor, weighted
    rsf: pd.DataFrame
    asf_total: float
    rsf_total: float
    nsfr: float
    item: pd.DataFrame = field(default_factory=pd.DataFrame)  # alm_nsfr_item
    skipped: list[str] = field(default_factory=list)

    def passes(self) -> bool:
        return self.nsfr >= NSFR_MIN


def compute_nsfr(bs: BalanceSheet, *, factor: pd.DataFrame | None = None,
                 asof: str = "") -> NSFRResult:
    """합성 재무상태표 기준 NSFR — 기존 시그니처를 유지한 원장 경로 래퍼."""
    fac = build_nsfr_factor() if factor is None else factor
    res = build_nsfr_item(nsfr_balances_from_balance_sheet(bs), fac, asof=asof)
    cols = ["category", "amount", "factor", "weighted"]
    it = res.item
    return NSFRResult(
        asf=it.loc[it["section"] == "ASF", cols].reset_index(drop=True),
        rsf=it.loc[it["section"] == "RSF", cols].reset_index(drop=True),
        asf_total=res.asf_total, rsf_total=res.rsf_total, nsfr=res.nsfr,
        item=it, skipped=res.skipped)
