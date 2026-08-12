"""LCR — 유동성커버리지비율 (Basel LCR20/30/40, 은행업감독규정 제26조).

LCR = HQLA(헤어컷·2B 15% 상한·L2 40% 상한 적용 후)
      / 30일 순현금유출(유입은 유출의 75% 상한) ≥ 100%

**무엇을 고치는가.**

1. `LCR_HAIRCUT_L2B = 0.50` 단일 상수가 Level 2B의 25% 버킷을 소실시켰다.
   2B는 단일 헤어컷이 아니다 — RMBS(AA− 이상) 25%, 회사채 A+~BBB− 50%,
   주요지수 보통주 50%, 국가·PSE BBB+~BBB− 50%(BCBS d238 ¶54 / LCR30.42).
   `alm_lcr_factor` 원장에 4행으로 분리해 적재한다. 보유 채권의 세부 구분
   원장이 없으므로 산출은 `level_2b_unclassified`(2B 중 **최대** 헤어컷)로
   가며, 25% 버킷이 원장에 존재하되 미산출임이 `source` 컬럼에 남는다.
2. 상한(2B 15% · L2 40% · 유입 75%)이 산식 한가운데 있었다. 원장 `한도`
   구분의 행으로 옮기고 엔진이 읽어 적용한다.
3. 담보부조달·파생 유출·등급하락 트리거·만기도래 채무증권이 분모에 **아예
   없어서 부재가 보이지 않았다.** 원장에 등재하되 `source='미산출'`로 둔다.
4. 국내 정본은 은행업감독업무시행세칙 [별표 3-6]이다. `citation_kr`을 따로
   두어 BCBS 근거와 국내 근거를 두 줄로 단다. 별표 3-6 원문을 열람하지
   못했으므로 관할재량 항목(무역금융 0~5% 등)은 `factor=NULL`이다.

**남는 한계.** 운영예금 판정 로직이 없다(청산·수탁·현금관리 활동 원장 부재).
유출률을 25%와 100%로 가르는 최대 분기점이므로 LCR은 구조적으로 과대계상된다.
`corporate_operational` 행의 note에 그 사실을 적는다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

from risk_lib.alm.balance_sheet import BalanceSheet
from risk_lib.alm.params import EVIDENCE_STATUS
from risk_lib.datamodel.spec import ColumnSpec as C, ForeignKey as FK, TableSpec
from risk_lib.references import (
    LCR_MIN, LCR_L2_CAP, LCR_L2B_CAP, LCR_HAIRCUT_L2A, LCR_HAIRCUT_L2B,
    LCR_INFLOW_CAP, LCR_RUNOFF, LCR_INFLOW_RATES,
)

__all__ = [
    "LCR_SECTIONS", "LCR_SOURCES", "LCR_FACTOR", "LCR_FLOW", "LCR_TABLES",
    "LCRResult", "LCRFlowResult", "HQLACaps",
    "build_lcr_factor", "build_lcr_flow", "lcr_balances_from_ledgers",
    "lcr_balances_from_balance_sheet", "resolve_caps", "apply_hqla_caps",
    "compute_lcr",
]

LCR_SECTIONS: tuple[str, ...] = ("HQLA", "유출", "유입", "한도")
LCR_SOURCES: tuple[str, ...] = ("산출", "미산출")

# 미인출 약정 잔액의 대체 비율. `rdm_exposure.undrawn`이 실측으로 존재하는데
# 이 모듈이 연결되지 않아 대출 대비 비율로 대체한다. 같은 산출 안에서 LCR
# 0.10 · 스트레스 엔진 0.18 · 서식 실측 세 값이 동시에 통용되고 있으므로,
# 상수를 함수 본문에서 꺼내 이름을 붙이고 `undrawn` 인자로 덮어쓸 수 있게 한다.
UNDRAWN_TO_LOANS_PROXY = 0.10


# ---------------------------------------------------------------- 스펙

LCR_FACTOR = TableSpec(
    name="alm_lcr_factor", korean="LCR 계수 원장", product="PRD-ALM",
    grain="계정 × 구분 × 항목 1행",
    columns=(
        C("framework", "string", "계정", nullable=False),
        C("section", "string", "구분", nullable=False, allowed=LCR_SECTIONS,
          citation="LCR30(HQLA) · LCR40(유출·유입)"),
        C("category", "string", "항목", nullable=False),
        C("factor", "float", "적용률", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0,
          note="HQLA는 인정률(1−헤어컷), 유출은 이탈률, 유입은 인식률, "
               "한도는 상한 자체. NULL이면 엔진이 그 항목을 가중하지 않고 "
               "경고를 남긴다"),
        C("citation_bcbs", "text", "BCBS 근거", nullable=True),
        C("citation_kr", "text", "국내 근거", nullable=True,
          note="정본은 은행업감독업무시행세칙 [별표 3-6]이다. BCBS와 국내가 "
               "다를 수 있으므로 한 줄로 합치지 않는다"),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
        C("source", "string", "산출 여부", nullable=False, allowed=LCR_SOURCES,
          note="'미산출'은 원장이 없어 분모·분자에 들어가지 못한 항목이다 — "
               "등재하지 않으면 부재 자체가 보이지 않는다"),
    ),
    primary_key=("framework", "section", "category"),
    note="상한(2B 15% · L2 40% · 유입 75%)도 '한도' 구분의 행이다. 산식 안에 "
         "숫자로 두면 화면·검증·서식 어디에도 나타나지 않는다.",
)

LCR_FLOW = TableSpec(
    name="alm_lcr_flow", korean="LCR 유출입", product="PRD-ALM",
    grain="기준일 × 시나리오 × 구분 × 항목 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("scenario", "string", "시나리오", nullable=False),
        C("section", "string", "구분", nullable=False, allowed=LCR_SECTIONS),
        C("category", "string", "항목", nullable=False),
        C("balance", "float", "잔액", nullable=True, unit="KRW"),
        C("factor", "float", "적용률", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("weighted", "float", "가중 후 금액", nullable=True, unit="KRW"),
        C("factor_source", "string", "계수 출처", nullable=False,
          note="원장에서 읽었는지, 세부구분 부재로 보수적 대체를 했는지, "
               "계수가 비어 산출을 건너뛰었는지"),
        C("citation", "text", "근거", nullable=True),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("asof", "scenario", "section", "category"),
    foreign_keys=(FK(("section", "category"), "alm_lcr_factor",
                     ("section", "category")),),
    note="잔액은 계약원장·현금흐름원장에서 오고 계수는 alm_lcr_factor에서 "
         "온다. 산식에 박힌 숫자가 없는 것이 이 장의 요점이다.",
)

LCR_TABLES: tuple[TableSpec, ...] = (LCR_FACTOR, LCR_FLOW)


# ---------------------------------------------------------------- 계수 원장

_KR_UNREAD = "은행업감독업무시행세칙 [별표 3-6] 원문 미열람"

# Level 2B 세부 구분. 단일 헤어컷 상수가 지우고 있던 것이 바로 이 표다.
_L2B_ROWS: tuple[tuple[str, float, str], ...] = (
    ("level_2b_rmbs", 0.75,
     "BCBS d238 ¶54(a) / LCR30.42 — RMBS(AA− 이상) 헤어컷 25%"),
    ("level_2b_corporate_bbb", 0.50,
     "BCBS d238 ¶54(b) / LCR30.42 — 회사채 A+~BBB− 헤어컷 50%"),
    ("level_2b_equity", 0.50,
     "BCBS d238 ¶54(c) / LCR30.42 — 주요지수 보통주 헤어컷 50%"),
    ("level_2b_sovereign_bbb", 0.50,
     "BCBS d238 ¶54(d) / LCR30.42 — 국가·PSE BBB+~BBB− 헤어컷 50%"),
)

# 원장이 없어 산출에 들어가지 못하는 유출 항목. 계수는 알려진 값이지만 잔액이
# 없다 — 둘을 구분해 적어야 "무엇이 왜 빠졌는가"가 읽힌다.
_UNBUILT_OUTFLOWS: tuple[tuple[str, float | None, str, str], ...] = (
    ("derivatives_net_payable", 1.00,
     "BCBS d238 ¶116 — 30일 순계약지급액 100%", "2차자료"),
    ("derivatives_collateral_hlba", 1.00,
     "BCBS d238 ¶119 — HLBA(24개월 최대 30일 순담보변동) 100%", "2차자료"),
    ("derivatives_non_l1_collateral", 0.20,
     "BCBS d238 ¶120 — 비Level1 담보 20%", "2차자료"),
    ("rating_downgrade_trigger", 1.00,
     "BCBS d238 ¶118 — 신용등급 3단계 하락 트리거 100%", "2차자료"),
    ("maturing_debt_securities", 1.00,
     "BCBS d238 ¶124 — 만기도래 자기발행 채무증권 100%", "2차자료"),
    ("trade_finance", None,
     "BCBS d238 ¶138 — 무역금융 0~5% 관할재량", "미확인"),
)


def build_lcr_factor(*, framework: str = "BCBS_d238") -> pd.DataFrame:
    """LCR 계수 원장. 규제표를 적재하는 자리는 여기 한 곳이다.

    이미 저장소에 있는 계수(`references.LCR_*`)는 그대로 읽어 온다 — 별사본을
    만들면 규제 상수가 두 벌이 된다. 새로 넣는 것은 Level 2B 세부 구분과
    미산출 항목, 그리고 상한 3종이다.

    근거 상태는 전부 `2차자료`다. bis.org·law.go.kr egress 차단으로 이 회차에
    1차자료를 한 건도 열람하지 못했다. '원문확인'으로 적을 근거가 없다.
    """
    rows: list[dict] = []

    def add(section, category, factor, cite_bcbs, evidence, source,
            cite_kr=_KR_UNREAD):
        rows.append({"framework": framework, "section": section,
                     "category": category,
                     "factor": None if factor is None else float(factor),
                     "citation_bcbs": cite_bcbs, "citation_kr": cite_kr,
                     "evidence_status": evidence, "source": source})

    # --- HQLA: 인정률 = 1 − 헤어컷 ---
    add("HQLA", "level_1", 1.0,
        "BCBS d238 ¶50 / LCR30.41 — Level 1 헤어컷 0%", "2차자료", "산출")
    add("HQLA", "level_2a", 1.0 - LCR_HAIRCUT_L2A,
        "BCBS d238 ¶52 / LCR30.42 — Level 2A 헤어컷 15%", "2차자료", "산출")
    for cat, f, cite in _L2B_ROWS:
        add("HQLA", cat, f, cite, "2차자료", "미산출")
    add("HQLA", "level_2b_unclassified", 1.0 - LCR_HAIRCUT_L2B,
        "세부 구분 원장 부재 — 2B 중 최대 헤어컷(50%)을 보수적으로 적용. "
        "RMBS 25% 버킷은 위 4행에 등재되어 있으나 산출에 쓰이지 않는다",
        "2차자료", "산출")

    # --- 유출 ---
    _kr_operational = (f"{_KR_UNREAD}. 운영예금 판정 원장(청산·수탁·현금관리 "
                       "활동, 운영한도 초과분)이 없어 25%/100% 구분이 "
                       "불가능하다 — LCR 과대계상 방향이다")
    for cat, f in LCR_RUNOFF.items():
        src = "산출" if cat in (
            "retail_stable", "retail_less_stable", "corporate_operational",
            "corporate_non_operational", "wholesale_fi_unsecured",
            "committed_facilities") else "미산출"
        add("유출", cat, f, "BCBS d238 LCR40 — 자금조달 이탈률", "2차자료", src,
            cite_kr=_kr_operational if cat == "corporate_operational"
            else _KR_UNREAD)
    for cat, f, cite, ev in _UNBUILT_OUTFLOWS:
        add("유출", cat, f, cite, ev, "미산출")

    # --- 유입 ---
    for cat, f in LCR_INFLOW_RATES.items():
        add("유입", cat, f, "BCBS d238 LCR40 — 계약상 유입 인식률", "2차자료",
            "산출")
    add("유입", "securities_inflows", 1.0,
        "BCBS d238 ¶155 — 만기도래 유가증권(HQLA 제외) 100%", "2차자료",
        "미산출")

    # --- 한도: 산식이 아니라 원장에 둔다 ---
    add("한도", "cap_l2b", LCR_L2B_CAP,
        "BCBS d238 ¶47 / LCR30.45 — Level 2B ≤ HQLA의 15%", "2차자료", "산출")
    add("한도", "cap_l2", LCR_L2_CAP,
        "BCBS d238 ¶46 / LCR30.44 — Level 2 ≤ HQLA의 40%", "2차자료", "산출")
    add("한도", "cap_inflow", LCR_INFLOW_CAP,
        "BCBS d238 ¶69 / LCR40.61 — 인정유입 ≤ 총유출의 75%", "2차자료", "산출")

    return pd.DataFrame(rows).astype({"factor": "float64"})


# ---------------------------------------------------------------- 상한 적용

@dataclass(frozen=True)
class HQLACaps:
    l2b: float
    l2: float
    inflow: float


def resolve_caps(factor: pd.DataFrame) -> HQLACaps:
    """'한도' 구분에서 상한 3종을 읽는다. 없으면 산출을 멈춘다."""
    cap = factor[factor["section"] == "한도"].set_index("category")["factor"]
    missing = [k for k in ("cap_l2b", "cap_l2", "cap_inflow")
               if k not in cap.index or pd.isna(cap[k])]
    if missing:
        raise ValueError(
            f"alm_lcr_factor '한도' 항목이 비어 있다: {missing}. 상한을 코드 "
            "기본값으로 대체하면 원장에 없는 규제 수치가 산출에 들어간다")
    return HQLACaps(l2b=float(cap["cap_l2b"]), l2=float(cap["cap_l2"]),
                    inflow=float(cap["cap_inflow"]))


def apply_hqla_caps(l1: float, l2a: float, l2b: float, caps: HQLACaps,
                    ) -> tuple[float, float, float]:
    """헤어컷 후 금액에 2B·L2 상한을 적용한다 (BCBS d238 Annex 1).

        adj15 = max(L2B − c/(1−c)·(L1+L2A), L2B − c/(1−C)·L1, 0)
        adj40 = max((L2A + L2B − adj15) − C/(1−C)·L1, 0)

    c = 2B 상한, C = L2 상한. 계수 15/85·15/60·2/3은 상한에서 유도되며 원장의
    상한을 바꾸면 함께 움직인다 — 그래서 여기 숫자가 없다.

    반환: (HQLA 합계, 인정 L2A, 인정 L2B). 40% 조정은 표시용으로 L2A·L2B에
    비례 배분한다 — 비율 자체는 합계에만 의존한다.

    **입력이 정의를 만족하지 않는다.** '조정금액'은 30일 이내 만기도래
    담보부조달·담보부대출·담보스왑 중 HQLA를 교환하는 거래를 되감기(unwind)한
    뒤의 금액인데(BCBS d238 Annex 1), SFT 원장이 없어 되감기를 적용하지 못한다.
    상한 공식은 맞고 입력이 정의 미달이다(설계 §5.22).
    """
    k15 = caps.l2b / (1.0 - caps.l2b)
    k15_on_l1 = caps.l2b / (1.0 - caps.l2)
    k40 = caps.l2 / (1.0 - caps.l2)
    adj15 = max(l2b - k15 * (l1 + l2a), l2b - k15_on_l1 * l1, 0.0)
    l2b_after15 = l2b - adj15
    adj40 = max((l2a + l2b_after15) - k40 * l1, 0.0)
    hqla_total = l1 + l2a + l2b_after15 - adj40
    l2_after15 = l2a + l2b_after15
    scale40 = (l2_after15 - adj40) / l2_after15 if l2_after15 > 0 else 0.0
    return hqla_total, l2a * scale40, l2b_after15 * scale40


# ---------------------------------------------------------------- 잔액 도출

_BALANCE_COLS = ["section", "category", "balance"]


def lcr_balances_from_balance_sheet(
    bs: BalanceSheet, *, seed_inflow_frac: float,
    undrawn: float | None = None,
) -> pd.DataFrame:
    """합성 재무상태표에서 LCR 잔액을 뽑는다 (계약원장 배선 전 경로).

    조달 카테고리 이름이 곧 LCR 유출 항목이므로 매핑이 필요 없다. 만기 30일
    판정은 하지 못한다 — 조달 dict에 만기가 없다. `lcr_balances_from_ledgers`가
    계약원장에서 그 판정을 한다.
    """
    f = bs.funding
    und = (float(bs.loans) * UNDRAWN_TO_LOANS_PROXY if undrawn is None
           else float(undrawn))
    base = float(bs.loans) * seed_inflow_frac
    rows = [
        ("HQLA", "level_1", bs.hqla["level_1"]),
        ("HQLA", "level_2a", bs.hqla["level_2a"]),
        ("HQLA", "level_2b_unclassified", bs.hqla["level_2b"]),
        ("유출", "retail_stable", f["retail_stable"]),
        ("유출", "retail_less_stable", f["retail_less_stable"]),
        ("유출", "corporate_operational", f["corporate_operational"]),
        ("유출", "corporate_non_operational", f["corporate_non_operational"]),
        ("유출", "wholesale_fi_unsecured", f["wholesale_fi_lt6m"]),
        ("유출", "committed_facilities", und),
        # 소매/도매/FI 40/40/20 분할은 대체값이다 — 이 경로에는 유입의 상대방
        # 구분이 없다. 계약원장 경로가 상품·측으로 판정한다.
        ("유입", "retail_inflows", base * 0.4),
        ("유입", "wholesale_inflows", base * 0.4),
        ("유입", "fi_inflows", base * 0.2),
    ]
    return pd.DataFrame(rows, columns=_BALANCE_COLS)


def lcr_balances_from_ledgers(
    contracts: pd.DataFrame, product_terms: pd.DataFrame, *,
    asof: str, horizon_days: int,
    funding_category_of: dict[str, str],
    hqla_category_of: dict[str, str],
    undrawn: float | None = None,
) -> pd.DataFrame:
    """계약원장에서 LCR 잔액을 뽑는다.

    `alm_contract`가 만기를 들고 있으므로 **30일 판정이 실제로 가능하다.**
    만기부 조달은 시계 안에 만기가 오는 것만 유출이고, 자산은 시계 안에
    만기도래하는 계약이 유입이다. 조달 dict에서 뽑던 기존 경로는 이 판정을
    하지 못해 잔존 5년 조달까지 유출로 세었다.

    상품코드 → LCR 항목 매핑은 인자다. 여기에 dict를 박으면 상품 카탈로그와
    LCR 어휘가 두 곳에서 갈라진다.
    """
    asof_d = date.fromisoformat(asof)
    terms = product_terms.set_index("product_code")

    def residual_days(v) -> float:
        if v is None or pd.isna(v):
            return float("inf")     # 비만기 — 계약상 만기가 없다
        return float((date.fromisoformat(str(v)) - asof_d).days)

    agg: dict[tuple[str, str], float] = {}

    def bump(section, category, amount):
        agg[(section, category)] = agg.get((section, category), 0.0) + float(
            amount)

    for _, r in contracts.iterrows():
        code = str(r["product_code"])
        amount = float(r["notional"])
        rd = residual_days(r.get("maturity_date"))
        if bool(r["is_own_equity"]):
            continue
        if code in hqla_category_of:
            bump("HQLA", hqla_category_of[code], amount)
            continue
        side = str(r["side"])
        if side == "liability":
            cat = funding_category_of.get(code)
            if cat is None:
                continue
            is_nmd = str(terms.loc[code, "amort_type"]) == "non_maturity"
            # 비만기예금은 만기가 없으므로 전액이 30일 유출 대상이고,
            # 만기부 조달은 시계 안에 만기가 와야 유출이다.
            if is_nmd or rd <= horizon_days:
                bump("유출", cat, amount)
        elif side == "asset" and rd <= horizon_days:
            bump("유입", "wholesale_inflows", amount)

    und = undrawn
    if und is None:
        loans = float(contracts.loc[
            contracts["product_code"].astype(str).str.startswith("LN_"),
            "notional"].sum())
        und = loans * UNDRAWN_TO_LOANS_PROXY
    bump("유출", "committed_facilities", und)

    return pd.DataFrame([{"section": s, "category": c, "balance": v}
                         for (s, c), v in agg.items()],
                        columns=_BALANCE_COLS)


# ---------------------------------------------------------------- 엔진

@dataclass
class LCRFlowResult:
    flow: pd.DataFrame            # alm_lcr_flow
    hqla_total: float
    gross_outflow: float
    inflow_total: float
    inflow_capped: float
    net_outflow: float
    lcr: float
    caps: HQLACaps
    skipped: list[str] = field(default_factory=list)   # 계수가 비어 건너뛴 항목

    def passes(self) -> bool:
        return self.lcr >= LCR_MIN


def build_lcr_flow(balances: pd.DataFrame, factor: pd.DataFrame, *,
                   asof: str, scenario: str = "base") -> LCRFlowResult:
    """`alm_lcr_flow` — 잔액(원장) × 계수(원장) → LCR.

    계수가 NULL인 항목은 **가중하지 않고** `factor_source='계수 미확인·미가중'`
    으로 남긴다. 0으로 가중하면 유출 항목이 조용히 사라져 LCR이 과대해지고,
    임의 대체값을 쓰면 지어내기가 된다. 어느 쪽도 하지 않는다.
    """
    caps = resolve_caps(factor)
    fx = factor.set_index(["section", "category"])
    rows: list[dict] = []
    skipped: list[str] = []
    weighted: dict[tuple[str, str], float] = {}

    for _, b in balances.iterrows():
        key = (str(b["section"]), str(b["category"]))
        if key not in fx.index:
            raise KeyError(
                f"alm_lcr_factor에 {key} 항목이 없다 — 계수 없는 잔액은 "
                "가중할 수 없다")
        fr = fx.loc[key]
        f = fr["factor"]
        if pd.isna(f):
            rows.append({
                "asof": asof, "scenario": scenario, "section": key[0],
                "category": key[1], "balance": float(b["balance"]),
                "factor": np.nan, "weighted": np.nan,
                "factor_source": "계수 미확인·미가중",
                "citation": str(fr["citation_bcbs"]),
                "evidence_status": str(fr["evidence_status"])})
            skipped.append(f"{key[0]}/{key[1]}")
            continue
        w = float(b["balance"]) * float(f)
        weighted[key] = weighted.get(key, 0.0) + w
        src = ("세부구분 부재·보수적 대체"
               if key[1] == "level_2b_unclassified" else "원장")
        rows.append({
            "asof": asof, "scenario": scenario, "section": key[0],
            "category": key[1], "balance": float(b["balance"]),
            "factor": float(f), "weighted": w, "factor_source": src,
            "citation": str(fr["citation_bcbs"]),
            "evidence_status": str(fr["evidence_status"])})

    l1 = sum(v for k, v in weighted.items()
             if k[0] == "HQLA" and k[1] == "level_1")
    l2a = sum(v for k, v in weighted.items()
              if k[0] == "HQLA" and k[1] == "level_2a")
    l2b = sum(v for k, v in weighted.items()
              if k[0] == "HQLA" and k[1].startswith("level_2b"))
    hqla_total, _l2a_inc, _l2b_inc = apply_hqla_caps(l1, l2a, l2b, caps)

    gross_outflow = sum(v for k, v in weighted.items() if k[0] == "유출")
    inflow_total = sum(v for k, v in weighted.items() if k[0] == "유입")
    inflow_capped = min(inflow_total, caps.inflow * gross_outflow)
    net_outflow = gross_outflow - inflow_capped
    lcr = hqla_total / net_outflow if net_outflow > 0 else float("inf")

    flow = pd.DataFrame(rows, columns=list(LCR_FLOW.column_names))
    return LCRFlowResult(
        flow=flow, hqla_total=hqla_total, gross_outflow=gross_outflow,
        inflow_total=inflow_total, inflow_capped=inflow_capped,
        net_outflow=net_outflow, lcr=lcr, caps=caps, skipped=skipped)


# ------------------------------------------------- 기존 소비처 호환 래퍼

@dataclass
class LCRResult:
    hqla_total: float
    hqla_detail: pd.DataFrame     # component, market_value, haircut, post_haircut, included
    outflows: pd.DataFrame        # category, amount, runoff, outflow
    inflows: pd.DataFrame         # category, amount, rate, inflow
    gross_outflow: float
    inflow_capped: float
    net_outflow: float
    lcr: float
    flow: pd.DataFrame = field(default_factory=pd.DataFrame)   # alm_lcr_flow

    def passes(self) -> bool:
        return self.lcr >= LCR_MIN


def compute_lcr(bs: BalanceSheet, *, seed_inflow_frac: float = 0.04,
                undrawn: float | None = None,
                factor: pd.DataFrame | None = None,
                asof: str = "") -> LCRResult:
    """합성 재무상태표 기준 LCR — 기존 시그니처를 유지한 원장 경로 래퍼.

    산출은 `build_lcr_flow` **한 벌**로 통일되어 있고, 이 함수는 반환 모양만
    기존 소비처(서식 BR-08·BF-*, 스트레스, 보고서)에 맞춰 되돌린다. 엔진을
    따로 두면 같은 이사회 팩에 두 개의 LCR이 실린다.

    seed_inflow_frac: 30일 계약상 유입을 대출 대비 비율로 대체한 값.
    소매/도매/FI 40/40/20 분할 역시 대체다 — 계약원장 경로
    (`lcr_balances_from_ledgers`)가 만기로 판정한다.
    """
    fac = build_lcr_factor() if factor is None else factor
    bal = lcr_balances_from_balance_sheet(
        bs, seed_inflow_frac=seed_inflow_frac, undrawn=undrawn)
    res = build_lcr_flow(bal, fac, asof=asof, scenario="base")

    fl = res.flow
    # 등급별 인정액은 flow 원장에서 되읽는다 — 여기서 다시 계산하면 화면과
    # 원장이 갈라질 수 있다.
    h = fl[fl["section"] == "HQLA"].set_index("category")
    l1 = float(h.loc["level_1", "weighted"])
    l2a = float(h.loc["level_2a", "weighted"])
    l2b = float(h.loc["level_2b_unclassified", "weighted"])
    _total, l2a_inc, l2b_inc = apply_hqla_caps(l1, l2a, l2b, res.caps)
    hqla_detail = pd.DataFrame([
        {"component": "Level 1", "market_value": bs.hqla["level_1"],
         "haircut": 0.0, "post_haircut": l1, "included": l1},
        {"component": "Level 2A", "market_value": bs.hqla["level_2a"],
         "haircut": LCR_HAIRCUT_L2A, "post_haircut": l2a, "included": l2a_inc},
        {"component": "Level 2B", "market_value": bs.hqla["level_2b"],
         "haircut": LCR_HAIRCUT_L2B, "post_haircut": l2b, "included": l2b_inc},
    ])

    out = fl[fl["section"] == "유출"]
    outflows = pd.DataFrame({
        "category": out["category"].to_numpy(),
        "amount": out["balance"].to_numpy(dtype=float),
        "runoff": out["factor"].to_numpy(dtype=float),
        "outflow": out["weighted"].to_numpy(dtype=float)})
    inf = fl[fl["section"] == "유입"]
    inflows = pd.DataFrame({
        "category": inf["category"].to_numpy(),
        "amount": inf["balance"].to_numpy(dtype=float),
        "rate": inf["factor"].to_numpy(dtype=float),
        "inflow": inf["weighted"].to_numpy(dtype=float)})

    return LCRResult(
        hqla_total=res.hqla_total, hqla_detail=hqla_detail,
        outflows=outflows, inflows=inflows,
        gross_outflow=res.gross_outflow, inflow_capped=res.inflow_capped,
        net_outflow=res.net_outflow, lcr=res.lcr, flow=fl)
