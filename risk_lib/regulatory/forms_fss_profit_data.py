"""수익성 서식(FINES B25xx)의 파생 데이터.

**여기서 만드는 값 중 일부는 원장이 아니라 파생값이다.** FINES 수익성 서식은
이자/비이자 구분, 기중평잔, 기준금리 유형, 대출금리 구간, 월중 신규취급, 수수료
항목, 이익잉여금 처분처럼 이 저장소의 원장(`pru_*` · `rdm_*` · `portfolio`)에
열이 없는 축을 요구한다. 상수를 박으면 서식이 산출과 무관해지고, 실행마다 난수를
새로 뽑으면 제출본 지문(`forms.submission_digest`)이 흔들려 같은 제출본인지
판별할 수 없다. 그래서 난수가 꼭 필요한 곳만 **기준일 고정 시드**로 만든다 —
같은 시드면 언제나 같은 값이다.

앵커 원칙: **총계는 언제나 `pru_income_statement` · `pru_balance_sheet`에 묶는다.**
BR-16(B2110 손익계산서)·BR-15(B2101 대차대조표)가 같은 두 테이블을 쓰므로 수익성
서식이 손익계산서와 어긋날 수 없다. 어긋나면 그건 배분 산식이 틀린 것이다.

산출값에서 그대로 오는 것 (파생 아님)
  영업수익·영업비용·충당금·법인세  `pru_income_statement` 그대로.
  대손충당금·건전성분류            `rdm_asset_quality` · `ecl_provision_bridge`.
                                  B2402·B2403(자산건전성)과 **같은 원천**이다.
  금리감응 자산·부채 사다리        `alm_repricing_gap` (= REPRICING_BUCKETS).
                                  BR-13(IRRBB)과 같은 사다리를 쓴다.
  기준금리 수준                    `alm["irrbb"].base_rate` 산출값.
  유가증권 잔액                    대차대조표 HQLA Level 2A·2B 실측.
  유가증권 평가손익                `mkt_ipv.diff` 실측 (독립가격검증 결과).
  지급보증 잔액                    지급보증 성격 부외약정 미사용액 실측.
  여신종별                         `forms_fss_asset_data.loan_book` 재사용 —
                                  B2403과 다른 여신종별을 쓰면 안 된다.
  신용등급                         `crm_rating`의 SA 버킷. 은행·국가는 포트폴리오
                                  `rating` 실측. 난수가 끼지 않는다.
  자회사 출자 총액                 `pru_ownership_limit` 산출 사용액.

난수가 아니지만 실측도 아닌 것 (측정값의 결정론적 함수)
  대출금리                        금리 원장이 없다. `기준금리 + 실측 스프레드
                                  (revenue ÷ ead) + 신용원가(PD × LGD)`로
                                  재구성한다. 합성 포트폴리오의 revenue는 자산군별
                                  단일 스프레드(기업 2.5% · 가계일반 5.5% ·
                                  주택 1.8% · 기타 0.8%)라 그것만으로는 금리 분산이
                                  생기지 않아 차주별 신용원가를 더한다. 국가·은행은
                                  표준방법 대상이라 PD·LGD가 없어 신용원가가 0이다.
  월중 신규취급액                  취급일자 원장이 없다. 만기까지 균등 재취급을
                                  가정해 `잔액 ÷ (만기 × 12)`로 본다.
  기준금리 유형 구성비             자산군별·수신계정별 고정 가중치다. 잔액은 실측.
  지급보증충당금                   부외약정에는 ECL이 산출되지 않는다. 해당
                                  익스포저의 **실측 커버리지율**을 미사용액에 곱한다.

시드 고정으로 파생하는 것 (원장 부재)
  비이자수익 비중                 `revenue`는 스프레드 수익이라 이자/비이자 구분이
                                  없다. 자산군별 밴드는 BF503·BF507이 쓰는
                                  `_NONINT_BAND`를 **그대로 import**한다 — 서식이
                                  자기 사본을 들면 두 화면이 조용히 갈라진다.
                                  다만 그쪽은 해외분만, 이쪽은 총계 기준이라
                                  난수 추출은 별개다(합계는 각자 실측에 앵커된다).
  이자수익·이자비용 총액           순이자이익만 실측이다. 조달비용률을 뽑아
                                  이자비용 = 이자부부채 × 조달비용률로 열고,
                                  이자수익은 잔여로 둔다 — **총액 분해는 파생이고
                                  순액은 실측**이다.
  기중평잔                        일별·월별 잔액 원장이 없다. 계정별 기중 성장률을
                                  뽑아 기초를 역산하고 (기초 + 기말) ÷ 2로 본다.
  유가증권 종류 구성비             HQLA 등급(2A = 국공채성 · 2B = 회사채·주식)까지는
                                  실측이고, 그 안의 종류 구성만 파생이다.
  수수료수입 항목 구성             수수료이익 총액은 비이자이익에서 오고 항목
                                  구성비만 파생이다.
  월중 수수료 신설·조정            **앵커할 산출값이 없는 완전 파생이다.**
                                  수수료 원장이 아예 없다.
  배당성향                        배당 결의 원장이 없다. 미처분이익잉여금은 실측이다.

파생·배분이 들어간 서식 라인은 **그 라인 자체의** formula에 그 사실을 남긴다.
상위 소계에만 적어 두면 서식이 flat table로 실체화될 때 하위 셀이 실측으로 읽힌다.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

from risk_lib.regulatory.forms_fss_asset_data import loan_book
from risk_lib.regulatory.forms_fss_overseas_b_data import (   # noqa: F401
    NONINT_ITEMS, _NONINT_BAND,
)

_SEED_BASE = 20260630          # 파생 기준일 — 이 값을 바꾸면 파생값 전체가 바뀐다


def rng(key: str) -> np.random.Generator:
    """기준일+키에서 유도한 난수원 — 키가 같으면 언제 어디서 불러도 같은 수열이다."""
    h = hashlib.sha256(f"{_SEED_BASE}:{key}".encode()).hexdigest()[:8]
    return np.random.default_rng(int(h, 16))


def tol(total: float) -> float:
    """금액 대사 허용오차 — 1e13 규모에서 float64 반올림은 원 단위를 넘는다."""
    return max(1.0, abs(float(total)) * 1e-9)


def ratio(num: float, den: float) -> float:
    return float(num) / float(den) if den else 0.0


# ---------------------------------------------------------------- 계정 어휘

# NIM 분모(이자수익자산) 정의 — BF507과 **같은 계정 묶음**이다. 기타자산은 이자를
# 낳지 않는다고 보아 제외한다.
EARNING_ASSET_ITEMS = ("현금 및 예치금", "유가증권 (Level 2A)",
                       "유가증권 (Level 2B)", "대출채권 (총액)")
DEPOSIT_ITEMS = ("예수금 — 개인 안정", "예수금 — 개인 준안정",
                 "예수금 — 법인 결제성", "예수금 — 법인 비결제성")
BORROWING_ITEMS = ("차입금 — 금융기관 6개월 이내", "차입금 — 금융기관 6~12개월",
                   "사채 및 장기차입금")
INTEREST_LIAB_ITEMS = DEPOSIT_ITEMS + BORROWING_ITEMS
SECURITY_ITEMS = ("유가증권 (Level 2A)", "유가증권 (Level 2B)")

# 조달비용률 밴드 — 이 배수를 통해서만 이자수익·이자비용 **총액**이 열린다.
# 값이 바뀌면 B2501·B2510의 총액이 통째로 바뀌고 순이자이익은 불변이다.
_FUNDING_RATE_BAND = (0.020, 0.032)
# 기중 잔액 성장률 밴드 — 기초 = 기말 ÷ (1 + g)로 역산해 평잔을 만든다.
_AVG_GROWTH_BAND = (-0.06, 0.14)


# ---------------------------------------------------------------- 손익 앵커

def income(ctx) -> dict[str, float]:
    """손익계산서 항목 → 금액. BR-16(B2110)이 쓰는 바로 그 테이블이다."""
    t = ctx.tables["pru_income_statement"]
    return {str(k): float(v) for k, v in zip(t["item"], t["amount"])}


def balance(ctx) -> dict[str, float]:
    """대차대조표 계정과목 → 금액. BR-15(B2101)가 쓰는 바로 그 테이블이다."""
    t = ctx.tables["pru_balance_sheet"]
    return {str(k): float(v) for k, v in zip(t["item"], t["amount"])}


def pnl_split(ctx) -> pd.DataFrame:
    """익스포저별 이자/비이자 분해 — 합계는 실측 영업수익과 정확히 같다.

    `revenue = ead × 스프레드`라 원천에는 이자/비이자 구분이 아예 없다. 자산군별
    비이자 비중 밴드는 해외점포 서식이 쓰는 것을 그대로 가져와, 같은 가정이 두 곳에서
    갈라지지 않게 한다. 행 순서를 exposure_id로 고정해야 파생 열이 재현된다.
    """
    p = (ctx.portfolio[["exposure_id", "asset_class", "ead", "revenue",
                        "operating_cost", "pd", "lgd", "maturity"]]
         .sort_values("exposure_id").reset_index(drop=True))
    lo = np.array([_NONINT_BAND[a][0] for a in p["asset_class"]])
    hi = np.array([_NONINT_BAND[a][1] for a in p["asset_class"]])
    share = lo + (hi - lo) * rng("비이자비중-총계").random(len(p))
    p["noninterest"] = p["revenue"] * share
    p["net_interest"] = p["revenue"] - p["noninterest"]
    return p


def interest_flow(ctx) -> dict[str, float]:
    """이자수익·이자비용 총액 — 순이자이익은 실측이고 총액 분해만 파생이다.

    이자비용을 **이자부부채 실측 잔액 × 파생 조달비용률**로 열고 이자수익을 잔여로
    둔다. 양쪽을 따로 뽑으면 순이자이익이 실측에서 벗어난다.
    """
    ps = pnl_split(ctx)
    bal = balance(ctx)
    net = float(ps["net_interest"].sum())
    liab = sum(bal[i] for i in INTEREST_LIAB_ITEMS)
    rate = float(rng("조달비용률").uniform(*_FUNDING_RATE_BAND))
    expense = -liab * rate                     # 비용은 손익계산서와 같은 음수 부호
    return {
        "net_interest": net,
        "noninterest": float(ps["noninterest"].sum()),
        "interest_expense": expense,
        "interest_income": net - expense,
        "funding_rate": rate,
        "interest_liability": liab,
    }


def noninterest_mix(ctx) -> dict[str, float]:
    """비이자이익 항목 구성 — 합계는 실측에서 갈라 낸 비이자이익과 정확히 같다.

    항목 어휘와 구성 알파는 BF503(해외 비이자이익)과 같게 두어 같은 개념이 서식마다
    다른 이름을 갖지 않게 한다.
    """
    total = interest_flow(ctx)["noninterest"]
    sh = rng("비이자구성-총계").dirichlet(np.array([9.0, 4.0, 3.0, 2.0]))
    return {k: total * float(v) for k, v in zip(NONINT_ITEMS, sh)}


# ---------------------------------------------------------------- 기중평잔

def avg_balance(ctx, items: tuple[str, ...]) -> pd.DataFrame:
    """계정별 (기말, 기초, 기중평잔). 기말은 실측이고 기초·평잔이 파생이다.

    성장률 키를 계정과목으로 잡으므로 어느 서식에서 불러도 같은 계정은 같은 평잔이
    나온다 — B2510의 NIM 분모와 B2520의 ROA 분모가 갈라지면 안 된다.
    """
    bal = balance(ctx)
    rows = []
    for item in items:
        closing = bal[item]
        g = float(rng(f"기중성장률:{item}").uniform(*_AVG_GROWTH_BAND))
        opening = closing / (1.0 + g)
        rows.append({"item": item, "closing": closing, "opening": opening,
                     "average": (opening + closing) / 2.0, "growth": g})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- 대출금리

GRADE_ORDER = ("AAA-AA", "A", "BBB", "BB", "B", "CCC-")

# 대출금리 구간 — 상한은 구간에 포함한다(`band_of`). 경계는 감독 실무 구간이 아니라
# 이 포트폴리오의 재구성 금리 분포를 가르는 **가정**이며, 그 사실을 서식에 적는다.
RATE_BANDS: tuple[tuple[float, str], ...] = (
    (0.03, "3% 미만"), (0.04, "3~4%"), (0.05, "4~5%"), (0.06, "5~6%"),
    (0.08, "6~8%"), (0.10, "8~10%"), (float("inf"), "10% 이상"),
)
RATE_BAND_LABELS = tuple(lab for _, lab in RATE_BANDS)

# 월중 신규취급 비율의 상·하한. 만기까지 균등 재취급 가정의 꼬리를 자른다 —
# 초단기 여신이 월 잔액의 100%를 신규취급으로 잡으면 서식이 잔액을 넘는다.
_NEW_SHARE_CLIP = (0.005, 0.10)


def band_of(value: float, bands=RATE_BANDS) -> str:
    """구간 라벨. 경계값은 아래 구간에 포함한다."""
    for upper, label in bands:
        if value < upper:
            return label
    return bands[-1][1]


def _grade_map(ctx) -> dict[str, str]:
    """차주별 SA 신용등급 — 신용모형 등급이 우선이고 은행·국가는 원장 등급이다."""
    cr = ctx.tables["crm_rating"]
    out = {str(o): str(g.sa_bucket) for o, g in zip(cr["obligor_id"], cr["grade"])}
    p = ctx.portfolio
    for o, rt in zip(p["obligor_id"], p["rating"]):
        if str(o) not in out and str(rt) in GRADE_ORDER:
            out[str(o)] = str(rt)
    return out


def loan_rates(ctx) -> pd.DataFrame:
    """여신별 대출금리·가산금리·신규취급액.

    금리 원장이 없어 `기준금리 + 실측 스프레드 + 신용원가`로 재구성한다. 난수는
    쓰지 않는다 — 세 항이 전부 산출값(기준금리·revenue·PD·LGD)의 결정론적 함수다.
    다만 **재구성이지 원장이 아니다**.
    """
    book = loan_book(ctx)
    p = ctx.portfolio[["exposure_id", "revenue", "pd", "lgd", "maturity"]]
    df = book.merge(p, on="exposure_id").sort_values("exposure_id").reset_index(
        drop=True)
    base = float(ctx.result.alm["irrbb"].base_rate)

    df["base_rate"] = base
    df["product_spread"] = df["revenue"] / df["ead"].replace(0.0, np.nan)
    df["product_spread"] = df["product_spread"].fillna(0.0)
    # 국가·은행 익스포저는 표준방법 대상이라 포트폴리오에 PD·LGD가 없다. 신용원가를
    # 0으로 두어 실측 스프레드(0.8%)만 가산한다 — 비우면 금리가 NaN이 되고 구간
    # 배정과 가중평균이 조용히 어긋난다.
    df["credit_spread"] = (df["pd"] * df["lgd"]).fillna(0.0)
    df["add_on"] = df["product_spread"] + df["credit_spread"]
    df["rate"] = base + df["add_on"]
    df["rate_band"] = [band_of(v) for v in df["rate"]]
    df["grade"] = df["obligor_id"].map(_grade_map(ctx)).fillna("무등급")
    # 취급일자 원장이 없다 — 만기까지 균등 재취급을 가정한 월 취급비율이다.
    m = df["maturity"].clip(lower=1 / 12.0)
    df["new_amount"] = df["balance"] * np.clip(1.0 / (m * 12.0), *_NEW_SHARE_CLIP)
    return df


def weighted(df: pd.DataFrame, value: str, weight: str) -> float:
    w = float(df[weight].sum())
    return float((df[value] * df[weight]).sum()) / w if w else 0.0


# ---------------------------------------------------------------- 기준금리 유형

BENCHMARK_TYPES = ("고정금리", "COFIX 연동", "CD(91일) 연동", "금융채 연동",
                   "기타 시장금리 연동")

# 자산군별 기준금리 유형 구성비. **난수가 아니라 고정 가중치**이며 잔액은 실측이다.
# 주택담보는 고정·COFIX가 두텁고 기업·은행은 CD·금융채 연동이 두텁다는 관찰을 담았다.
_LOAN_BENCH_TILT = {
    "residential_mortgage": (0.42, 0.38, 0.05, 0.10, 0.05),
    "retail_other":         (0.30, 0.30, 0.15, 0.15, 0.10),
    "corporate":            (0.22, 0.18, 0.25, 0.25, 0.10),
    "bank":                 (0.15, 0.05, 0.40, 0.30, 0.10),
    "sovereign":            (0.55, 0.05, 0.20, 0.15, 0.05),
}
# 수신 계정별 구성비 — 정기성 예금은 고정, 결제성·시장성 조달은 시장금리 연동이다.
_DEPOSIT_BENCH_TILT = {
    "예수금 — 개인 안정":        (0.70, 0.15, 0.05, 0.05, 0.05),
    "예수금 — 개인 준안정":       (0.55, 0.20, 0.10, 0.10, 0.05),
    "예수금 — 법인 결제성":       (0.25, 0.20, 0.25, 0.20, 0.10),
    "예수금 — 법인 비결제성":      (0.35, 0.20, 0.20, 0.20, 0.05),
    "차입금 — 금융기관 6개월 이내": (0.10, 0.05, 0.45, 0.30, 0.10),
    "차입금 — 금융기관 6~12개월":  (0.15, 0.05, 0.40, 0.30, 0.10),
    "사채 및 장기차입금":          (0.45, 0.05, 0.10, 0.35, 0.05),
}


def benchmark_mix(ctx) -> pd.DataFrame:
    """기준금리 유형별 여신·수신 잔액 (type × loan · deposit).

    잔액은 실측이고 유형 구성비만 고정 가중치다. 유형 합계가 실측 총액과 정확히
    같아야 B2511-1이 대차대조표·여신원장과 어긋나지 않는다.
    """
    book = loan_book(ctx)
    by_ac = book.groupby("asset_class")["balance"].sum()
    loan = np.zeros(len(BENCHMARK_TYPES))
    for ac, bal in by_ac.items():
        w = np.array(_LOAN_BENCH_TILT.get(str(ac),
                                          (0.30, 0.20, 0.20, 0.20, 0.10)))
        loan += float(bal) * w

    bal_map = balance(ctx)
    dep = np.zeros(len(BENCHMARK_TYPES))
    for item in INTEREST_LIAB_ITEMS:
        dep += bal_map[item] * np.array(_DEPOSIT_BENCH_TILT[item])
    return pd.DataFrame({"type": list(BENCHMARK_TYPES), "loan": loan,
                         "deposit": dep})


def floating_share(ctx) -> tuple[float, float]:
    """(여신 변동금리 비중, 수신 변동금리 비중) — 고정금리 유형의 여집합이다.

    B2512의 금리구조갭이 B2511-1과 다른 고정·변동 구분을 쓰면 두 서식이 갈라진다.
    """
    m = benchmark_mix(ctx)
    fixed = m[m["type"] == "고정금리"]
    return (1.0 - ratio(float(fixed["loan"].iloc[0]), float(m["loan"].sum())),
            1.0 - ratio(float(fixed["deposit"].iloc[0]),
                        float(m["deposit"].sum())))


# ---------------------------------------------------------------- 유가증권

# HQLA 등급까지는 실측 분류다 — Level 2A는 국공채성, Level 2B는 회사채·주식성.
# 그 안의 종류 구성만 파생이며, 총액은 대차대조표 잔액에 정확히 앵커된다.
SECURITY_KINDS_2A = ("국채", "통화안정증권", "특수채·지방채", "금융채")
SECURITY_KINDS_2B = ("회사채", "주식", "수익증권·기타")
SECURITY_KINDS = SECURITY_KINDS_2A + SECURITY_KINDS_2B


def securities_book(ctx) -> pd.DataFrame:
    """유가증권 종류별 잔액 — 등급별 총액은 실측, 종류 구성비는 파생이다."""
    bal = balance(ctx)
    rows = []
    for level, kinds, alpha in (
            ("유가증권 (Level 2A)", SECURITY_KINDS_2A, 4.0),
            ("유가증권 (Level 2B)", SECURITY_KINDS_2B, 3.0)):
        total = bal[level]
        w = rng(f"유가증권종류:{level}").dirichlet(np.full(len(kinds), alpha))
        for kind, x in zip(kinds, w):
            rows.append({"kind": kind, "level": level, "balance": total * float(x)})
    return pd.DataFrame(rows)


def valuation_adjustment(ctx) -> dict[str, float]:
    """독립가격검증(IPV) 결과의 평가조정 — **실측이다.**

    채권평가충당금은 보수적 평가로 인한 하향조정 필요액이므로 음수 차이만 모은다.
    상향분을 상계하면 충당금이 아니라 순평가손익이 되어 성격이 달라진다.
    """
    ipv = ctx.tables["mkt_ipv"]
    diff = ipv["diff"].astype(float)
    return {
        "down": float(-diff[diff < 0].sum()),
        "up": float(diff[diff > 0].sum()),
        "net": float(diff.sum()),
        "n": float(len(ipv)),
        "n_down": float(int((diff < 0).sum())),
        "n_break": float(int(ipv["is_break"].sum())),
    }


# ---------------------------------------------------------------- 수수료

FEE_ITEMS = ("여신관련 수수료", "수신·전자금융 수수료", "외환·수출입 수수료",
             "수익증권·신탁 판매 수수료", "방카슈랑스 판매 수수료",
             "신용카드 관련 수수료", "기타 수수료")


def fee_mix(ctx) -> dict[str, float]:
    """수수료수입 항목 구성 — 합계는 비이자이익의 수수료이익과 정확히 같다."""
    total = noninterest_mix(ctx)["수수료이익"]
    sh = rng("수수료구성").dirichlet(np.array([8.0, 6.0, 4.0, 3.0, 2.0, 3.0, 2.0]))
    return {k: total * float(v) for k, v in zip(FEE_ITEMS, sh)}


FEE_ACTIONS = ("신설", "인상", "인하", "폐지")


def fee_changes(ctx) -> pd.DataFrame:
    """월중 수수료 신설·조정 내역 — **앵커할 산출값이 없는 완전 파생이다.**

    수수료 요율 원장이 이 저장소에 아예 없다. 건수·요율·조정폭 전부 파생이며
    B2522(수수료수입)와는 금액으로 연결되지 않는다 — 요율 변경은 당월 이후 수입에
    반영되므로 당기 수수료수입과 일치할 이유가 없다.
    """
    g = rng("수수료조정")
    n = int(g.integers(4, 9))
    idx = g.integers(0, len(FEE_ITEMS), n)
    act = g.integers(0, len(FEE_ACTIONS), n)
    before = g.uniform(0.0005, 0.0120, n)
    rows = []
    for i in range(n):
        action = FEE_ACTIONS[int(act[i])]
        b = 0.0 if action == "신설" else float(before[i])
        if action == "폐지":
            a = 0.0
        elif action == "신설":
            a = float(g.uniform(0.0005, 0.0120))
        elif action == "인상":
            a = b * float(g.uniform(1.05, 1.40))
        else:
            a = b * float(g.uniform(0.60, 0.95))
        rows.append({"item": FEE_ITEMS[int(idx[i])], "action": action,
                     "rate_before": b, "rate_after": a, "delta": a - b})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- 지급보증

GUARANTEE_CCF = ("direct_credit_substitute", "transaction_related")


def guarantee_book(ctx) -> pd.DataFrame:
    """지급보증 익스포저 — 잔액·건전성분류는 실측, 충당금만 커버리지 환산이다.

    부외약정에는 ECL이 산출되지 않는다(EAD가 인출액 기준이다). 같은 익스포저의
    **실측 커버리지율**을 미사용액에 곱해 지급보증충당금을 만든다 — 난수가 아니라
    산출 커버리지의 결정론적 함수이며, 그래도 원장이 아니라 환산값이다.
    """
    book = loan_book(ctx)
    g = book[book["ccf_type"].isin(GUARANTEE_CCF)].copy()
    g["guarantee"] = g["undrawn"].astype(float)
    g["provision"] = g["guarantee"] * g["coverage_ratio"].astype(float)
    return g


# ---------------------------------------------------------------- 이익잉여금

# 상법 제458조 — 이익준비금은 현금배당액의 10% 이상을 자본금의 1/2에 이를 때까지.
LEGAL_RESERVE_RATE = 0.10
_PAYOUT_BAND = (0.18, 0.30)      # 배당성향 밴드 — 배당 결의 원장이 없다


def appropriation(ctx) -> dict[str, float]:
    """이익잉여금 처분안 — 미처분이익잉여금은 실측이고 배당성향만 파생이다.

    전기이월액을 따로 뽑지 않고 `대차대조표 이익잉여금 − 당기순이익`으로 역산한다.
    양쪽을 따로 만들면 처분안 합계가 대차대조표와 어긋나고 그 차액을 메울 근거가 없다.
    """
    inc = income(ctx)
    bal = balance(ctx)
    net = inc["당기순이익"]
    unappropriated = bal["이익잉여금"]
    payout = float(rng("배당성향").uniform(*_PAYOUT_BAND))
    dividend = max(net, 0.0) * payout
    reserve = dividend * LEGAL_RESERVE_RATE
    return {
        "carried_in": unappropriated - net,
        "net_income": net,
        "unappropriated": unappropriated,
        "payout": payout,
        "dividend": dividend,
        "legal_reserve": reserve,
        "carried_out": unappropriated - dividend - reserve,
    }


# ---------------------------------------------------------------- 신탁계정

# 신탁계정 수지 항목. B2113(신탁계정 손익계산서)과 같은 어휘 위에 수입·지출 구분만
# 얹는다 — 두 서식이 다른 항목명을 쓰면 감독당국 집계에서 행이 어긋난다.
TRUST_REVENUE_ITEMS = ("신탁보수", "신탁관련 수수료수익", "신탁재산 운용수익",
                       "기타 신탁수입")
TRUST_EXPENSE_ITEMS = ("신탁재산 운용비용", "신탁관련 판매관리비",
                       "신탁계정 대손상각비", "기타 신탁지출")
