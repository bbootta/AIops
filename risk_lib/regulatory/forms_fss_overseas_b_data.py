"""해외점포 수익성·자본적정성·현지화 서식의 파생 데이터.

`forms_fss_overseas_data`(점포 마스터·해외 여신 원장)를 그대로 재사용하고, 그
모듈에 없는 것만 여기서 만든다. **점포 마스터·익스포저 귀속·해외 여신 집계는
여기서 다시 만들지 않는다** — 두 벌이 되면 BF1xx~BF4xx와 BF5xx~BF7xx의 숫자가
갈라진다.

원장·산출에서 그대로 오는 것 (파생 아님)
  영업수익·영업비용      `portfolio.revenue` · `operating_cost` 익스포저별 실측.
                        해외분은 소재국으로 거른 합이므로 배분이 아니다.
  해외 신용 위험가중자산  `rwa_result` 익스포저별 실측 합.
  CCR 위험가중자산 비중   `ccr.by_counterparty` × `rdm_obligor.country` 실측.
  유가증권 운용손익 총액   유가증권 프록시 익스포저의 revenue 실측 합.
  손실위험도가중여신      `rdm_asset_quality` 건전성분류 실측 × **원장의** 제29조
                        최저적립률(`min_provision_rate`). 서식이 가중치 사본을
                        들지 않는다 — 그룹 서식 B2902와 같은 원천이어야 같은
                        지표가 두 값을 갖지 않는다.

배분 (비율은 실측, 배분 결과는 파생)
  대차대조표 계정         `overseas_share`(해외 EAD 실측 비중)로 배분한다.
                        BF201이 쓰는 비율과 **같은 비율**이어야 두 서식이
                        어긋나지 않는다.
  충당금 전입액          해외 ECL 비중으로 배분. 기간 손익의 국가 원장이 없다.
  운영손실·운영리스크 RWA  영업수익 비중으로 배분. OPE25 사업지표가 수익 기반이다.
  시장리스크 RWA         트레이딩계정에 소재국 귀속이 없어 EAD 비중으로 배분한다.
  배분 자기자본          해외 익스포저 비중 × 본점 자기자본. **본점 자본을 그대로
                        쓰지 않는다.**

시드 고정으로 파생하는 것 (원장 부재)
  이자·비이자 분해        `revenue`는 스프레드 수익(순액)이라 이자/비이자 구분이
                        없다. 자산군별 밴드에서 비이자 비중을 뽑는다.
  이자수익·이자비용 총액   순이자이익만 실측이다. 손익계산서 부호(비용은 음수)를
                        쓰므로 국가별 조달배수를 뽑아 이자비용 = −순이자이익 ×
                        배수, 이자수익 = 순이자이익 − 이자비용으로 편다. 둘을
                        더하면 순이자이익으로 되돌아온다 — **총액 분해는 파생이고
                        순액은 실측**이다.
  전기(직전 반기) 실적    기간 원장이 없다. 항목별 증감률을 뽑아 역산한다.
  유가증권 손익 구성비     이자·평가·처분 구분 원장이 없다. 총액은 실측이다.
  점포별 직원수·현지채용   인사 원장이 없다.
  점포별 현지조달·현지운용  자금 원장에 조달처·운용처 구분이 없다.
  차주의 현지고객 여부     차주 국적·진출기업 구분 원장이 없다.

같은 시드면 같은 값이다 — 제출본 지문(`forms.submission_digest`)이 흔들리지
않아야 같은 제출본인지 판별할 수 있다. 파생값이 들어간 서식 라인은 **그 라인의**
formula에 파생임을 남긴다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from risk_lib.prudential.financials import CORPORATE_TAX_RATE
from risk_lib.regulatory.forms_fss_overseas_data import (
    AQ_ORDER, HOME_COUNTRY, branch_master, overseas_book, overseas_countries,
    overseas_securities, overseas_share, rng,
)

# 비이자수익 비중 밴드 — 자산군 성격을 따른다. 기업·은행 거래는 수수료·외환
# 수익이 붙고 주택담보는 거의 이자수익뿐이다. **원장이 아니라 파생 밴드다.**
_NONINT_BAND = {
    "corporate": (0.15, 0.30),
    "bank": (0.20, 0.40),
    "sovereign": (0.05, 0.15),
    "residential_mortgage": (0.03, 0.10),
    "retail_other": (0.10, 0.25),
}
# 조달배수 = 이자비용 ÷ 순이자이익. 이 배수를 통해서만 총액이 열리므로 값이
# 바뀌면 BF502·BF507의 이자수익·이자비용이 통째로 바뀐다 (순이자이익은 불변).
_FUNDING_MULTIPLE = (0.8, 1.6)
# 전기(직전 반기) 대비 증감률 밴드 — 전기 = 당기 ÷ (1 + g)로 역산한다.
_GROWTH_BAND = (-0.12, 0.20)
# 점포 인당 관리자산 — 직원수를 여신잔액에서 역산하는 계수다. 해외점포는 기업금융
# 위주라 인당 자산이 크고, 본점은 소매 비중이 커 작다. 이 밴드가 곧 직원수의
# 자릿수를 정하므로 BF701·BF705가 여기에 직접 걸린다.
_ASSET_PER_STAFF = (1.5e10, 4.0e10)
_HQ_ASSET_PER_STAFF = (4.0e9, 8.0e9)
_MIN_STAFF = 3                       # 사무소도 최소 인원은 둔다
_LOCAL_HIRE = {"지점": (0.60, 0.85), "현지법인": (0.85, 0.97),
               "사무소": (0.30, 0.60)}
_LOCAL_FUNDING = {"지점": (0.35, 0.65), "현지법인": (0.55, 0.85),
                  "사무소": (0.0, 0.0)}
_LOCAL_USAGE = {"지점": (0.45, 0.75), "현지법인": (0.65, 0.90),
                "사무소": (0.0, 0.0)}
_LOCAL_CUSTOMER_P = (0.55, 0.85)     # 소재국별 현지고객 비율 밴드

NONINT_ITEMS = ("수수료이익", "외환매매이익", "유가증권관련이익", "기타비이자이익")
SEC_PNL_ITEMS = ("이자수익", "평가손익", "처분손익")
# 평가·처분손익은 음수가 될 수 있다. 이자수익을 잔여로 두어 합계가 실측 총액과
# 정확히 같게 만든다 — 구성비만 파생이고 총액은 실측이어야 한다.
_SEC_SIGNED_BAND = {"평가손익": (-0.15, 0.25), "처분손익": (-0.10, 0.20)}

# ------------------------------------------------- 손실위험도가중여신 (BF606)
#
# **가중치 사본을 두지 않는다.** 손실위험도 가중치는 은행업감독규정 제29조 제1항
# 대손충당금 최저적립률이며, 익스포저 원장(`rdm_asset_quality.min_provision_rate`)
# 에 이미 실려 있다. 그룹 서식 B2902(`forms_fss_indicator._aq_weighted`)가 바로
# 그 열을 읽는다 — 해외분 서식이 자기 상수표를 들면 같은 지표가 두 값을 갖고,
# 규정이 개정돼도 한쪽만 조용히 갈라진다. 적립률은 기업여신·가계여신이 다르므로
# (회수의문 50% vs 55% 등) 분류 단위 단일 계수로 접지 않고 익스포저 단위로 곱한다.

def loss_weighted(ctx) -> tuple[dict[str, float], dict[str, float],
                                dict[str, str]]:
    """분류별 (잔액, 손실위험도가중여신, 적용 최저적립률 설명).

    가중액 = Σ(익스포저 잔액 × 원장 min_provision_rate). 서식 상수가 아니다.
    """
    ob = overseas_book(ctx)
    bal, wtd, note = {}, {}, {}
    for cls in AQ_ORDER:
        s = ob[ob["classification"] == cls]
        bal[cls] = float(s["balance"].sum())
        wtd[cls] = float((s["balance"] * s["min_provision_rate"]).sum())
        rates = sorted({float(x) for x in s["min_provision_rate"]})
        note[cls] = (" · ".join(f"{x:.2%}" for x in rates) +
                     " (제29조 제1항 최저적립률 · 원장)" if rates
                     else "해당 분류 잔액 없음")
    return bal, wtd, note


def loss_weighted_amount(frame) -> float:
    """임의 부분집합(소재국 등)의 손실위험도가중여신 — 같은 산식을 한 곳에서 쓴다."""
    return float((frame["balance"] * frame["min_provision_rate"]).sum())


# ---------------------------------------------------------------- 손익

def pnl_book(ctx) -> pd.DataFrame:
    """해외 익스포저별 손익 프레임 — 실측 손익 + 파생 이자/비이자 분해.

    행 순서를 exposure_id로 고정해야 파생 열이 재현된다.
    """
    ob = overseas_book(ctx)
    pl = ctx.portfolio[["exposure_id", "revenue", "operating_cost"]]
    df = (ob.merge(pl, on="exposure_id")
          .sort_values("exposure_id").reset_index(drop=True))

    lo = np.array([_NONINT_BAND[a][0] for a in df["asset_class"]])
    hi = np.array([_NONINT_BAND[a][1] for a in df["asset_class"]])
    share = lo + (hi - lo) * rng("비이자비중").random(len(df))
    df["noninterest"] = df["revenue"] * share
    df["net_interest"] = df["revenue"] - df["noninterest"]

    ctry = overseas_countries(ctx)
    mult = dict(zip(ctry, rng("조달배수").uniform(*_FUNDING_MULTIPLE,
                                               size=len(ctry))))
    m = df["country"].map(mult).to_numpy(dtype=float)
    # 순이자이익만 실측이다. 총액은 조달배수로 열되 차액은 순액 그대로 남긴다.
    df["interest_expense"] = -df["net_interest"] * m
    df["interest_income"] = df["net_interest"] - df["interest_expense"]

    ids = sorted(df["obligor_id"].unique())
    u = dict(zip(ids, rng("현지고객").random(len(ids))))
    p = dict(zip(ctry, rng("현지고객확률").uniform(*_LOCAL_CUSTOMER_P,
                                              size=len(ctry))))
    df["local_customer"] = (df["obligor_id"].map(u).to_numpy(dtype=float)
                            < df["country"].map(p).to_numpy(dtype=float))
    return df


def overseas_income(ctx) -> dict[str, float]:
    """해외 손익계산서 — 손익계산서 편제와 같은 부호(비용은 음수)를 쓴다."""
    df = pnl_book(ctx)
    inc = ctx.tables["pru_income_statement"]
    m = dict(zip(inc["item"], inc["amount"]))
    revenue = float(df["revenue"].sum())
    opex = float(df["operating_cost"].sum())

    ecl_all = float(ctx.tables["ecl_result"]["ecl"].sum())
    prov = float(m["충당금 전입액"]) * (float(df["ecl"].sum()) / ecl_all
                                   if ecl_all else 0.0)
    rev_all = float(ctx.portfolio["revenue"].sum())
    op_loss = float(m["운영손실"]) * (revenue / rev_all if rev_all else 0.0)

    pre_tax = revenue - opex + prov + op_loss
    tax = -max(pre_tax, 0.0) * CORPORATE_TAX_RATE
    return {"영업수익": revenue, "영업비용": -opex, "충당금 전입액": prov,
            "운영손실": op_loss, "법인세차감전순이익": pre_tax,
            "법인세비용": tax, "당기순이익": pre_tax + tax}


def noninterest_mix(ctx) -> dict[str, float]:
    """비이자이익 항목 구성 — 합계는 실측 비이자이익과 정확히 같다."""
    total = float(pnl_book(ctx)["noninterest"].sum())
    sh = rng("비이자구성").dirichlet(np.array([9.0, 4.0, 3.0, 2.0]))
    return {k: total * float(v) for k, v in zip(NONINT_ITEMS, sh)}


def security_pnl(ctx) -> dict[str, float]:
    """유가증권 운용손익 구성 — 총액은 실측, 구분은 파생이다."""
    sec = overseas_securities(ctx)[["exposure_id"]]
    total = float(sec.merge(ctx.portfolio[["exposure_id", "revenue"]],
                            on="exposure_id")["revenue"].sum())
    g = rng("유가증권손익")
    out, rest = {}, 1.0
    for item, (lo, hi) in _SEC_SIGNED_BAND.items():
        s = float(g.uniform(lo, hi))
        out[item] = total * s
        rest -= s
    out["이자수익"] = total * rest
    return {k: out[k] for k in SEC_PNL_ITEMS}


def prior_amount(label: str, current: float) -> float:
    """전기(직전 반기) 실적 — 기간 원장이 없어 증감률을 뽑아 역산한다."""
    g = float(rng(f"전기:{label}").uniform(*_GROWTH_BAND))
    return current / (1.0 + g)


def interest_prior(ctx) -> pd.DataFrame:
    """국가별 이자수익·이자비용의 당기·전기 — 전기는 국가×항목 단위 파생이다.

    전기를 총계에서 한 번 뽑고 국가별로 또 뽑으면 두 합이 어긋난다. 가장 잘게
    뽑고 위로 더하는 쪽만 합계 항등식이 성립한다.
    """
    df = pnl_book(ctx)
    rows = []
    for country in overseas_countries(ctx):
        s = df[df["country"] == country]
        inc = float(s["interest_income"].sum())
        exp = float(s["interest_expense"].sum())
        rows.append({
            "country": country,
            "interest_income": inc, "interest_expense": exp,
            "prior_income": prior_amount(f"이자수익:{country}", inc),
            "prior_expense": prior_amount(f"이자비용:{country}", exp),
        })
    out = pd.DataFrame(rows)
    out["net_interest"] = out["interest_income"] + out["interest_expense"]
    out["prior_net"] = out["prior_income"] + out["prior_expense"]
    return out


# ---------------------------------------------------------------- 배분

def allocated_balance(ctx) -> dict[str, float]:
    """해외 배분 대차대조표 — BF201과 **같은** 실측 비중을 쓴다."""
    w = overseas_share(ctx)
    bs = ctx.tables["pru_balance_sheet"]
    return {str(r["item"]): float(r["amount"]) * w for _, r in bs.iterrows()}


def overseas_rwa(ctx) -> dict[str, float]:
    """해외 귀속 위험가중자산 — 신용은 실측, 나머지는 근거 있는 비중 배분이다."""
    ob = overseas_book(ctx)
    rr = ctx.tables["rwa_result"]
    credit = float(rr.loc[rr["exposure_id"].isin(set(ob["exposure_id"])),
                          "rwa"].sum())

    r = ctx.result
    cc = r.ccr.by_counterparty.merge(
        ctx.tables["rdm_obligor"][["obligor_id", "country"]],
        left_on="counterparty", right_on="obligor_id", how="left")
    tot_ccr = float(cc["rwa"].sum())
    ov_ccr = float(cc.loc[cc["country"].fillna(HOME_COUNTRY) != HOME_COUNTRY,
                          "rwa"].sum())
    ccr_share = ov_ccr / tot_ccr if tot_ccr else 0.0

    w = overseas_share(ctx)
    rev_all = float(ctx.portfolio["revenue"].sum())
    rev_share = (float(pnl_book(ctx)["revenue"].sum()) / rev_all
                 if rev_all else 0.0)
    # 분자 `credit`은 rwa_result의 온밸런스 신용 RWA 합이다. 분모에 `credit_internal`
    # 을 쓰면 안 된다 — 거기에는 CCR·CVA가 들어 있어(pipeline.py) 분자·분모의
    # 기준이 달라지고 해외 몫이 그만큼 과소 배분된다. 같은 기준인 SA+IRB를 쓴다.
    credit_all = float(r.rwa["sa"]) + float(r.rwa["irb"])
    # 산출하한 가산은 표준방법 총액 대비 집계 수준 max()라 자산분류별로도
    # 지역별로도 정체성이 없다. `attribution._RWA_DETAIL_AXIS` 주석이 같은
    # 이유로 자산분류 축의 쪼개기를 거부한다. 여기서 지역 축으로 배분하는
    # 것은 이 서식이 제출본이고 분자인 배분자기자본이 `w`로 전액 배분되기
    # 때문이다 — 분모에서만 빼면 해외 자본비율이 본점보다 구조적으로 높게
    # 나온다. 그래서 배분하되 이것이 산출이 아니라 배분임을 서식에 적는다
    # (`forms_fss_overseas_b._rwa_block`의 basis=혼합, BF602 9000 비고).
    floor_share = credit / credit_all if credit_all else 0.0

    out = {
        "credit": credit,
        "ccr": float(r.rwa["ccr"]) * ccr_share,
        "market": float(r.rwa["market"]) * w,
        "op": float(r.rwa["op"]) * rev_share,
        "floor": float(r.rwa["output_floor"].add_on) * floor_share,
        # 구조화(집합투자증권·유동화)는 두 원장에 소재국 축이 없다. 배분하지 않고
        # 두면 분모에서만 빠지는데 분자인 배분자본은 `w`로 전액 배분되므로,
        # 해외 자본비율이 본점보다 구조적으로 높게 나온다 — 트레이딩계정과 같은
        # 상황이므로 같은 근거(EAD 비중 `w`)로 배분한다. 배분값이지 실측이 아니다.
        "structured": float(r.rwa.get("structured_total", 0.0)) * w,
        "ccr_share": ccr_share, "market_share": w, "op_share": rev_share,
        "structured_share": w,
        "group_total": float(r.rwa["final_total"]),
    }
    out["total"] = out["credit"] + out["ccr"] + out["market"] + out["op"] \
        + out["floor"] + out["structured"]
    return out


# ---------------------------------------------------------------- 현지화

def _branch_frame(ctx) -> pd.DataFrame:
    """점포 마스터 + 점포별 여신잔액 — 현지화 서식 셋의 공통 뼈대."""
    bm = branch_master(ctx)
    bal = overseas_book(ctx).groupby("branch_code")["balance"].sum()
    out = bm.copy()
    out["balance"] = out["branch_code"].map(bal).fillna(0.0)
    return out


def staff_book(ctx) -> pd.DataFrame:
    """점포별 직원수·현지채용 — **인사 원장이 없어 전부 파생값이다.**"""
    df = _branch_frame(ctx)
    per = rng("점포직원수").uniform(*_ASSET_PER_STAFF, size=len(df))
    u = rng("현지채용").random(len(df))
    total = np.maximum(_MIN_STAFF,
                       np.round(df["balance"].to_numpy() / per)).astype(int)
    lo = np.array([_LOCAL_HIRE[k][0] for k in df["kind"]])
    hi = np.array([_LOCAL_HIRE[k][1] for k in df["kind"]])
    local = np.round(total * (lo + (hi - lo) * u)).astype(int)
    df["staff_total"] = total
    df["staff_local"] = local
    df["staff_expat"] = total - local
    return df


def hq_staff(ctx) -> float:
    """본점(국내) 직원수 — 파생. 초국적화지수의 인력 분모다."""
    p = ctx.portfolio
    home = float(p.loc[p["country"] == HOME_COUNTRY, "ead"].sum())
    per = float(rng("본점직원수").uniform(*_HQ_ASSET_PER_STAFF))
    return float(max(1, round(home / per)))


def funding_book(ctx) -> pd.DataFrame:
    """점포별 조달 — 총조달은 배분 부채총계, 현지조달 비중은 파생이다."""
    df = _branch_frame(ctx)
    liab = allocated_balance(ctx)["부채총계"]
    tot_bal = float(df["balance"].sum())
    df["funding_total"] = (df["balance"] / tot_bal * liab) if tot_bal else 0.0
    u = rng("현지조달").random(len(df))
    lo = np.array([_LOCAL_FUNDING[k][0] for k in df["kind"]])
    hi = np.array([_LOCAL_FUNDING[k][1] for k in df["kind"]])
    df["funding_local"] = df["funding_total"] * (lo + (hi - lo) * u)
    df["funding_hq"] = df["funding_total"] - df["funding_local"]
    return df


def usage_book(ctx) -> pd.DataFrame:
    """점포별 운용 — 총운용은 여신잔액 실측, 현지운용 비중은 파생이다."""
    df = _branch_frame(ctx)
    u = rng("현지운용").random(len(df))
    lo = np.array([_LOCAL_USAGE[k][0] for k in df["kind"]])
    hi = np.array([_LOCAL_USAGE[k][1] for k in df["kind"]])
    df["usage_total"] = df["balance"]
    df["usage_local"] = df["usage_total"] * (lo + (hi - lo) * u)
    df["usage_offshore"] = df["usage_total"] - df["usage_local"]
    return df


# ---------------------------------------------------------------- 자체평가

# BF706 자체평가 점수체계. **난수가 아니라 공표된 자체평가 기준이다.** 부문마다
# 20점을 배정하고, 산출 지표를 구간표로 환산한다. 구간 경계는 감독기준(최저
# 자본비율 8%·자산건전성 지표)과 국내은행 해외점포 평균을 기준으로 잡았다.
SECTION_POINTS = 20.0
TOTAL_POINTS = 100.0
SCORE_SECTIONS = (
    ("해외 네트워크", "해외점포 수", "count", False,
     ((10.0, 20.0), (7.0, 16.0), (5.0, 12.0), (3.0, 8.0))),
    ("현지화 수준", "초국적화지수 (TNI)", "ratio", False,
     ((0.40, 20.0), (0.30, 16.0), (0.20, 12.0), (0.10, 8.0))),
    ("자산건전성", "해외 고정이하여신비율", "ratio", True,
     ((0.010, 20.0), (0.020, 16.0), (0.030, 12.0), (0.050, 8.0))),
    ("자본적정성", "해외영업점 총자본비율", "ratio", False,
     ((0.140, 20.0), (0.120, 16.0), (0.105, 12.0), (0.080, 8.0))),
    ("수익성", "해외 총자산순이익률", "ratio", False,
     ((0.010, 20.0), (0.007, 16.0), (0.005, 12.0), (0.003, 8.0))),
)
_FLOOR_POINTS = 4.0                  # 최하 구간도 0점은 주지 않는다
GRADE_CUTS = ((90.0, "1등급 (우수)"), (75.0, "2등급 (양호)"),
              (60.0, "3등급 (보통)"), (45.0, "4등급 (미흡)"))


def score_of(value: float, lower_is_better: bool,
             cuts: tuple[tuple[float, float], ...]) -> float:
    """구간표 환산 — 경계값은 상위 구간에 포함한다."""
    for bound, point in cuts:
        if (value <= bound) if lower_is_better else (value >= bound):
            return point
    return _FLOOR_POINTS


def grade_of(total: float) -> str:
    for bound, label in GRADE_CUTS:
        if total >= bound:
            return label
    return "5등급 (취약)"
