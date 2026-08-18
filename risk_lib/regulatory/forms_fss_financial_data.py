"""재무제표 서식(FINES B21xx)의 파생·배분 데이터.

**여기서 만드는 값 중 일부는 원장이 아니라 파생값이다.** FINES 재무제표 서식은
국내분·해외분, 지역, IFRS 9 범주처럼 이 저장소의 원장(`pru_*` · `rdm_*`)에 열이
없는 축을 요구한다. 상수를 박으면 서식이 산출과 무관해지고, 실행마다 난수를 새로
뽑으면 제출본 지문(`forms.submission_digest`)이 흔들려 같은 제출본인지 판별할 수
없다. 그래서 난수가 꼭 필요한 한 곳만 **기준일 고정 시드**로 만든다 — 같은 시드면
언제나 같은 값이다. 시드 기반은 `forms_fss_retail_data.rng`를 그대로 쓴다.
지역이라는 **같은 개념을 두 번 파생하면 값이 갈리기 때문**이다.

앵커 원칙: **총계는 언제나 `pru_balance_sheet` · `pru_income_statement`에 묶는다.**
BR-15(B2101)·BR-16(B2110)이 같은 두 테이블을 쓰므로 계정별·계정과목별 변형이
총괄분과 어긋날 수 없다. 어긋나면 그건 배분 산식이 틀린 것이다.

산출값에서 그대로 오는 것 (파생 아님)
  국내·해외 배분비율   `forms_fss_overseas_data.overseas_share` — 실측 EAD 비중.
                       BF201이 쓰는 바로 그 비율이라 해외분 대차대조표가 갈리지 않는다.
  국내분 손익의 수익·비용  `portfolio.revenue` · `operating_cost`를 country로 가른
                       **실측 합**이다. 배분이 아니다.
  충당금 전입액 배분비  국내 익스포저의 `ecl_result.ecl` 실측 비중.
  가계 지역            `forms_fss_retail_data.household(ctx)["region"]` 그대로.
                       B2127이 B2426 계열과 다른 지역분포를 쓰면 안 된다.
  트레이딩 포지션      `rwa_market_component.position` 산출값. FVTPL의 앵커다.
  건전성분류·잔액      `rdm_asset_quality` 산출값.

시드 고정으로 파생하는 것 (원장 부재)
  비가계 지역          기업·은행·국가 익스포저의 소재 지역. 규모(`log_assets`)가
                       클수록 수도권 비중을 올린다. 가계는 파생하지 않고 위 값을
                       재사용한다. 가중치 `NONRETAIL_REGION_W`는 **가정치이며
                       관찰 근거가 없다** — 방향만 담았고 분포는 실무 관찰치가
                       아니다.

배분(원장 부재 — 난수는 아니지만 실측도 아닌 것)
  해외분 계정별 금액    계정별 해외 원장이 없어 전 계정에 같은 실측 비중을 곱한다.
                       한 비율을 전 계정에 곱하므로 대차 항등식이 배분 후에도 성립한다.
  운영손실 국내·해외    `opr_loss_event`에 국가 열이 없어 영업수익 비중으로 가른다.
  법인세비용 국내·해외  세전이익 비중으로 가른다(부문별 세액 배분). 실효세율을
                       부문별로 다시 계산하면 국내+해외가 총괄분과 어긋난다.
  IFRS 9 범주          범주 열이 원장에 없어 자산 유형에서 배분하되, FVTPL은
                       난수가 아니라 **트레이딩 포지션 산출값에 앵커**한다.
  지역별 수신          수신 원장이 아예 없다. 예수금 총액(실측)을 개인은 가계
                       차주 수, 법인은 기업여신 잔액의 지역분포로 가른다.

파생·배분이 들어간 서식 라인은 **그 라인 자체의** formula에 그 사실을 남긴다.
상위 소계에만 적어 두면 서식이 flat table로 실체화될 때 하위 셀이 실측으로 읽힌다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from risk_lib.regulatory.forms_fss_overseas_data import (
    HOME_COUNTRY, overseas_share,
)
from risk_lib.regulatory.forms_fss_retail_data import (
    HOUSEHOLD_CLASSES, NPL_CLASSES, REGIONS, household, rng,
)

# 대차대조표 소계 행 — 구성계정 합계 검증에서 빼야 이중계상되지 않는다.
BS_TOTALS = ("자산총계", "부채총계", "자본총계 (회계)", "규제자본 합계 (참고)")
# 대출채권은 총액·차감·순액 세 줄이라 순액만 구성계정으로 센다.
BS_SKIP = ("대출채권 (총액)", "대손충당금 (차감)")

# 금융자산으로 보는 대차대조표 계정. 기타자산은 세부 원장이 없어 비금융자산으로
# 둔다 — 파생상품자산·미수수익이 섞여 있을 수 있으나 가르는 근거가 없다.
FIN_ASSET_ITEMS = ("현금 및 예치금", "유가증권 (Level 2A)", "유가증권 (Level 2B)",
                   "대출채권 (순액)")
SECURITY_ITEMS = ("유가증권 (Level 2A)", "유가증권 (Level 2B)")
ASSET_CATEGORIES = ("상각후원가 (AC)", "기타포괄손익-공정가치 (FVOCI)",
                    "당기손익-공정가치 (FVTPL)")
LIAB_CATEGORIES = ("상각후원가 (AC)", "당기손익-공정가치 (FVTPL)")

# 예수금 계정의 개인·법인 구분 — B2128의 지역 배분 모수를 가른다.
RETAIL_DEPOSITS = ("예수금 — 개인 안정", "예수금 — 개인 준안정")
CORP_DEPOSITS = ("예수금 — 법인 결제성", "예수금 — 법인 비결제성")

# 비가계(기업·은행·국가) 지역 배정 가중치 — **가정치다. 관찰·추정 근거가 없다.**
# (수도권 절편, 수도권 규모기울기, 광역시 고정, 기타지방 절편, 기타지방 규모기울기)
# 원장에 소재지 열이 없어 "규모가 클수록 본사가 수도권일 확률이 높다"는 방향만
# 가정으로 놓은 것이며, 실무 관찰 분포가 아니다. 이 값을 바꾸면 B2127의
# 지역별 여신·B2128의 법인 예수금 지역분포가 전부 바뀐다. 반대로 지역별
# 합계·차주 수·건전성분류는 이 값과 무관하게 실측 총계에 묶여 있다.
NONRETAIL_REGION_W = (0.45, 0.18, 0.30, 0.25, 0.13)


def tol(total: float) -> float:
    """금액 대사 허용오차 — 1e13 규모에서 float64 반올림은 원 단위를 넘는다."""
    return max(1.0, abs(float(total)) * 1e-9)


def _z(s: pd.Series) -> np.ndarray:
    v = s.to_numpy(dtype=float)
    sd = float(np.nanstd(v))
    return (v - float(np.nanmean(v))) / (sd if sd else 1.0)


def _pick(key: str, weights: np.ndarray, labels: tuple[str, ...]) -> list[str]:
    """행별 확률로 라벨을 하나씩 뽑는다 — 행 순서가 고정돼야 재현된다."""
    w = weights / weights.sum(axis=1, keepdims=True)
    u = rng(key).random(len(w))
    idx = (w.cumsum(axis=1) < u[:, None]).sum(axis=1).clip(0, w.shape[1] - 1)
    return [labels[int(i)] for i in idx]


# ---------------------------------------------------------------- 대차대조표

def bs_amounts(ctx) -> dict[str, float]:
    """계정과목 → 금액. BR-15(B2101)가 쓰는 바로 그 테이블이다."""
    t = ctx.tables["pru_balance_sheet"]
    return {str(k): float(v) for k, v in zip(t["item"], t["amount"])}


def domestic_share(ctx) -> float:
    """국내분 배분비율 — 해외분의 여집합이다.

    `overseas_share`를 그대로 뒤집어 쓴다. 국내분을 따로 정의하면 국내+해외가
    1을 벗어나 B2102+B2103 ≠ B2101이 된다.
    """
    return 1.0 - overseas_share(ctx)


# ---------------------------------------------------------------- 손익 배분

def income_split(ctx) -> pd.DataFrame:
    """손익계산서 국내·해외 배분 — 항목마다 배분근거가 다르다.

    수익·비용은 country별 **실측 합**이고, 충당금은 실측 ECL 비중, 운영손실과
    법인세만 배분이다. 어느 항목이든 국내+해외 = 총괄분이 되도록 해외분을
    총계에서 빼는 방식으로 만든다 — 양쪽을 따로 계산하면 잔차가 생기고 그
    잔차를 메울 근거가 없다.
    """
    inc = ctx.tables["pru_income_statement"].sort_values("seq")
    total = {str(k): float(v) for k, v in zip(inc["item"], inc["amount"])}
    p = ctx.portfolio
    dom = p["country"] == HOME_COUNTRY

    rev_d = float(p.loc[dom, "revenue"].sum())
    cost_d = -float(p.loc[dom, "operating_cost"].sum())
    # 영업수익 비중은 운영손실·법인세 배분의 모수로도 쓴다.
    rev_share = rev_d / total["영업수익"] if total["영업수익"] else 0.0

    ecl = ctx.tables["ecl_result"][["exposure_id", "ecl"]]
    e = p[["exposure_id", "country"]].merge(ecl, on="exposure_id", how="left")
    ecl_all = float(e["ecl"].sum())
    ecl_share = (float(e.loc[e["country"] == HOME_COUNTRY, "ecl"].sum()) / ecl_all
                 if ecl_all else 0.0)
    prov_d = total["충당금 전입액"] * ecl_share
    oprisk_d = total["운영손실"] * rev_share

    pre_d = rev_d + cost_d + prov_d + oprisk_d
    pre_t = total["법인세차감전순이익"]
    tax_share = pre_d / pre_t if pre_t else 0.0
    tax_d = total["법인세비용"] * tax_share
    net_d = pre_d + tax_d

    rows = [
        ("영업수익", rev_d, f"country={HOME_COUNTRY} 익스포저 revenue 실측 합"),
        ("영업비용", cost_d, f"country={HOME_COUNTRY} 익스포저 operating_cost 실측 합"),
        # 전입액은 유량(기말−기초)인데 배분키는 기말 ECL **잔액** 비중이다.
        # 국가별 기초 ECL을 복원할 원장이 없어 잔량 비중으로 대신한 것이므로
        # 그 사실을 근거 문구에 그대로 남긴다.
        ("충당금 전입액", prov_d,
         f"총계 × 국내 ECL 잔액 비중 {ecl_share:.6f} — 비중은 실측이나 유량(전입액)을 "
         f"잔액 비중으로 가른 배분이다"),
        ("운영손실", oprisk_d,
         f"총계 × 국내 영업수익 비중 {rev_share:.6f} — 운영손실 원장에 국가 없음"),
        ("법인세차감전순이익", pre_d, "① + ② + ③ + ④"),
        ("법인세비용", tax_d,
         f"총계 × 국내 세전이익 비중 {tax_share:.6f} — 부문별 세액 배분"),
        ("당기순이익", net_d, "⑤ + ⑥"),
    ]
    out = pd.DataFrame(rows, columns=["item", "domestic", "basis"])
    out["total"] = [total[i] for i in out["item"]]
    out["overseas"] = out["total"] - out["domestic"]
    return out[["item", "total", "domestic", "overseas", "basis"]]


# ---------------------------------------------------------------- IFRS 9 범주

def trading_position(ctx) -> float:
    """트레이딩 포지션 합계 — FVTPL 금융자산의 앵커. 산출값이며 파생이 아니다."""
    return float(ctx.tables["rwa_market_component"]["position"].sum())


def asset_categories(ctx) -> pd.DataFrame:
    """금융자산 IFRS 9 범주 배분 (item × AC/FVOCI/FVTPL).

    원장에 범주 열이 없다. 상수 비율을 박는 대신 **사업모형에서 유도**한다 —
    현금성자산과 대출채권은 원리금 수취 목적이므로 전액 AC이고, 유가증권 중
    트레이딩 포지션(시장리스크 산출값)만큼이 FVTPL, 나머지가 FVOCI다.
    Level 2B(저유동성)를 먼저 FVTPL로 채우고 남는 만큼만 Level 2A로 넘긴다 —
    트레이딩 성격이 더 강한 자산부터 채우는 것이 사업모형 판단에 가깝다.
    """
    amt = bs_amounts(ctx)
    remain = min(trading_position(ctx),
                 sum(amt[i] for i in SECURITY_ITEMS))   # 유가증권 잔액을 넘길 수 없다
    fvtpl = {}
    for item in ("유가증권 (Level 2B)", "유가증권 (Level 2A)"):
        take = min(remain, amt[item])
        fvtpl[item] = take
        remain -= take
    rows = []
    for item in FIN_ASSET_ITEMS:
        f = fvtpl.get(item, 0.0)
        is_sec = item in SECURITY_ITEMS
        rows.append({
            "item": item, "balance": amt[item],
            "상각후원가 (AC)": 0.0 if is_sec else amt[item],
            "기타포괄손익-공정가치 (FVOCI)": amt[item] - f if is_sec else 0.0,
            "당기손익-공정가치 (FVTPL)": f,
        })
    return pd.DataFrame(rows)


def liability_categories(ctx) -> pd.DataFrame:
    """금융부채 IFRS 9 범주 배분 (item × AC/FVTPL).

    예수금·차입금·사채는 전부 상각후원가다. FVTPL 지정 부채와 파생상품부채는
    대차대조표에 계정이 없어 0으로 둔다 — 파생 평가액은 `derivative_liability`가
    참고로 따로 낸다.
    """
    t = ctx.tables["pru_balance_sheet"]
    sub = t[(t["section"] == "부채") & (~t["item"].isin(BS_TOTALS))]
    return pd.DataFrame({
        "item": sub["item"].astype(str).to_numpy(),
        "balance": sub["amount"].astype(float).to_numpy(),
        "상각후원가 (AC)": sub["amount"].astype(float).to_numpy(),
        "당기손익-공정가치 (FVTPL)": np.zeros(len(sub)),
    })


def derivative_values(ctx) -> tuple[float, float]:
    """파생상품 평가액 (자산, 부채) — `mkt_trade.fo_value` 실측 합.

    대차대조표에 파생상품 계정이 없어 범주표 본문에 넣지 않고 참고로만 낸다.
    본문에 넣으면 금융자산 합계가 자산총계를 넘는다.
    """
    v = ctx.tables["mkt_trade"]["fo_value"].astype(float)
    # abs()가 없으면 음수 포지션이 하나도 없을 때 -0.0이 나가 서식에 "-0"으로
    # 찍힌다 — 0과 부호 있는 0은 제출본에서 다른 말로 읽힌다.
    return float(v[v > 0].sum()), abs(float(v[v < 0].sum()))


# ---------------------------------------------------------------- 지역

def region_book(ctx) -> pd.DataFrame:
    """국내 익스포저의 지역 귀속 — 가계는 재사용, 비가계만 파생한다.

    가계 지역은 `forms_fss_retail_data.household`가 이미 만든 값을 그대로 쓴다.
    같은 개념을 여기서 다시 뽑으면 B2127의 지역분포가 가계여신 서식과 갈린다.
    """
    aq = ctx.tables["rdm_asset_quality"][["exposure_id", "classification",
                                          "balance"]]
    p = ctx.portfolio[["exposure_id", "obligor_id", "asset_class", "country",
                       "log_assets"]]
    # 파생 배정이 행 순서에 의존한다 — 정렬을 고정해야 재현된다.
    df = (p[p["country"] == HOME_COUNTRY].merge(aq, on="exposure_id")
          .sort_values("exposure_id").reset_index(drop=True))
    df = df.merge(household(ctx)[["exposure_id", "region"]], on="exposure_id",
                  how="left")

    rest = df.index[df["region"].isna()]
    if len(rest):
        za = _z(df.loc[rest, "log_assets"].fillna(
            df["log_assets"].mean()))
        df.loc[rest, "region"] = _pick("지역-비가계", np.column_stack([
            np.clip(NONRETAIL_REGION_W[0] + NONRETAIL_REGION_W[1] * za,
                    0.05, 0.90),
            np.full(len(rest), NONRETAIL_REGION_W[2]),
            np.clip(NONRETAIL_REGION_W[3] - NONRETAIL_REGION_W[4] * za,
                    0.05, 0.90)]), REGIONS)

    df["is_household"] = df["asset_class"].isin(HOUSEHOLD_CLASSES)
    df["npl"] = df["classification"].isin(NPL_CLASSES)
    return df


def deposit_regions(ctx) -> pd.DataFrame:
    """지역별 수신(예수금) — **수신 원장이 아예 없다.**

    예수금 계정별 총액(실측)에 국내분 배분비율을 곱한 뒤, 개인은 가계 차주 수,
    법인은 기업여신 잔액의 지역분포로 가른다. 지역분포는 `region_book`을 그대로
    쓰므로 B2127(여신)과 같은 지역 개념 위에 선다.
    """
    amt = bs_amounts(ctx)
    w = domestic_share(ctx)
    retail_total = sum(amt[i] for i in RETAIL_DEPOSITS) * w
    corp_total = sum(amt[i] for i in CORP_DEPOSITS) * w

    rb = region_book(ctx)
    hh = (rb[rb["is_household"]].groupby("region")["obligor_id"].nunique()
          .reindex(REGIONS).fillna(0.0))
    co = (rb[~rb["is_household"]].groupby("region")["balance"].sum()
          .reindex(REGIONS).fillna(0.0))
    hw = hh / hh.sum() if hh.sum() else hh
    cw = co / co.sum() if co.sum() else co
    return pd.DataFrame({
        "region": list(REGIONS),
        "retail": (retail_total * hw).to_numpy(dtype=float),
        "corporate": (corp_total * cw).to_numpy(dtype=float),
    })
