"""주요재무현황·생산성·은행유형별 서식(FINES B22xx·B2701·B51xx)의 파생 데이터.

**여기서 만드는 값 중 일부는 원장이 아니라 파생값이다.** 이 그룹의 서식은
기중평잔·공공금고 예수금·임직원 수·국내 점포 수·자회사 경영실적·G-SIB 평가지표
처럼 이 저장소의 원장(`pru_*` · `rdm_*` · 포트폴리오)에 열이 아예 없는 항목을
요구한다. 상수를 박으면 서식이 산출과 무관해지고, 실행마다 난수를 새로 뽑으면
제출본 지문(`forms.submission_digest`)이 흔들려 같은 제출본인지 판별할 수 없다.
그래서 **기준일 고정 시드에서 유도한 결정론적 RNG**로 만든다 — 같은 시드면
언제나 같은 값이다. 시드 기반은 `forms_fss_compliance_data.rng`를 그대로 쓴다.
같은 저장소 안에 시드 기반이 여럿이면 "어느 파생이 어느 기준일 것인지"를
말할 수 없기 때문이다.

**새로 파생하지 않고 재사용하는 것** (같은 개념을 두 번 파생하면 값이 갈린다)
  금융채권 발행·상환·잔존만기  `forms_fss_compliance_data.debentures`.
                               B2204~B2206은 B3116~B3118과 **같은 채권**이다.
  자회사 명세                  `forms_fss_compliance_data.subsidiary_book`.
                               B5102는 B3110·B3111과 같은 자회사 목록이어야 한다.
  국내·해외 배분비율           `forms_fss_financial_data.domestic_share` (실측 EAD 비중).
  해외 자지점 수               `forms_fss_overseas_data.branch_master`.
                               B5103의 해외분은 BF103과 같은 값이어야 한다.
  트레이딩 포지션              `forms_fss_financial_data.trading_position` (산출값).

원장·산출에서 그대로 오는 것 (파생 아님)
  기말 잔액·손익      `pru_balance_sheet` · `pru_income_statement`.
  약정·미사용한도      `rdm_exposure.drawn` · `undrawn` · `portfolio.utilization`.
  무수익여신          `rdm_asset_quality.classification` · `rdm_delinquency.dpd`.
  타 금융회사 자산     `asset_class == "bank"` 익스포저 · `ccr` · `mkt_trade`.
  총익스포저          `leverage` · `leverage_deep` 산출값.

시드 고정으로 파생하는 것 (원장 부재)
  기중평잔            일별·월별 잔액 시계열이 없다. 기말잔액에 계정별 평잔계수를
                      곱하고, **조달측은 운용측 평잔 총계에 맞춰 비례 조정**한다.
                      조달과 운용은 같은 자금의 양면이라 총계가 갈리면 서식이
                      성립하지 않는다.

                      **미해결 — 통합 시 조정 필요.** `forms_fss_profit_data.
                      avg_balance`가 같은 기중평잔 개념을 다르게(기초 = 기말 ÷
                      (1+g), 평잔 = (기초+기말)/2) 파생한다. 두 산식은 계정별
                      평잔이 다르고, 그쪽은 계정마다 성장률을 독립으로 뽑으므로
                      조달계 = 운용계가 성립하지 않는다 — NIM 분모로는 문제가
                      없지만 자금조달·운용표는 그 항등식이 있어야 한다. 여기서
                      임의로 한쪽에 맞추면 다른 그룹의 서식이 조용히 틀어지므로
                      **양쪽 산식을 그대로 두고 통합 단계에서 한 산식으로
                      합쳐야 한다.** 합칠 때는 항등식이 필요한 쪽(B2201)을
                      기준으로 잡아야 한다.
  공공금고 예수금      금고 지정 원장이 없다. 법인 예수금 총액(실측)에 파생 비중을
                      곱하고 금고 유형별로 가른다.
  임직원 수·점포 수    인사·점포 원장이 없다. 1인당 총자산·점포당 임직원 수를 뽑아
                      총자산(실측)에서 역산한다. B1101(인원현황)을 만드는
                      `forms_fss_general_data`가 이 `headcount`·`domestic_branches`를
                      그대로 import해 쓰고 있다 — 같은 은행의 임직원 수가 서식마다
                      다르면 제출본이 성립하지 않으므로 여기 말고 다른 데서
                      인원·점포를 새로 뽑으면 안 된다.
  자회사 경영실적      자회사 재무제표가 없다. 자기자본은 출자금액 ÷ 지분율로
                      역산하고 총자산·순이익만 뽑는다. 평가등급은 난수가 아니라
                      ROA의 결정론적 함수다.
  타 금융회사 차입 상대방  차입 상대방 원장이 없다. 실재 은행 거래상대방에 배분하되
                      합계는 재무상태표 차입금이다. 사채는 상대방을 특정할 수 없어
                      배분하지 않는다.
  G-SIB 대체가능성·복잡성  지급결제금액·보관자산·인수금액·Level 3 자산 원장이 없다.
                      총자산·기타자산에 파생 배수를 곱한다.
  국내 시장점유율      업권 총계 원장이 없다. 점유율을 뽑고 업권 총계를 역산한다.

파생값이 들어간 서식 라인은 **그 라인 자체의** formula에 그 사실을 남긴다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from risk_lib.regulatory.forms_fss_compliance_data import rng, subsidiary_book
from risk_lib.regulatory.forms_fss_financial_data import (
    BS_SKIP, BS_TOTALS, CORP_DEPOSITS, bs_amounts,
)

# 은행계정 자금조달·운용표의 편제 — 대차대조표 자산이 운용, 부채·자본이 조달이다.
FUNDING_SECTIONS = ("부채", "자본")
USE_SECTION = "자산"

# 공공금고 유형. 국고금 관리법 제36조(국고금 취급)·지방회계법 제77조(금고 지정)·
# 지방교육자치에 관한 법률의 교육비특별회계 금고를 따른 편제 어휘다.
PUBLIC_TREASURY_KINDS: tuple[str, ...] = (
    "국고금", "지방자치단체금고", "시·도교육청금고", "공공기금·기타",
)

# 대출금액대 구간. 감독규정이 정한 구간이 아니라 FINES 대출금액대별 서식이
# 관행적으로 쓰는 금액 구간이며, 차주 단위 합산잔액 기준이다.
LOAN_SIZE_BANDS: tuple[tuple[float, str], ...] = (
    (10e6, "1천만원 이하"), (50e6, "1천만~5천만원"), (100e6, "5천만~1억원"),
    (500e6, "1억~5억원"), (1e9, "5억~10억원"), (5e9, "10억~50억원"),
    (10e9, "50억~100억원"), (float("inf"), "100억원 초과"),
)

# 은행업감독규정 제27조 자산건전성 분류의 고정이하 구분 — 무수익여신 산정대상이다.
NPL_CLASSES: tuple[str, ...] = ("고정", "회수의문", "추정손실")
NPL_DPD = 90            # 무수익여신 산정 연체일수 기준 (3개월)


def band_of(value: float, bands: tuple[tuple[float, str], ...]) -> str:
    """구간 라벨. 경계값은 아래 구간에 포함한다 (1천만원 → '1천만원 이하')."""
    for upper, label in bands:
        if value <= upper:
            return label
    return bands[-1][1]


# ---------------------------------------------------------------- 기중평잔

def average_balance(ctx) -> pd.DataFrame:
    """기중평잔 대차대조표 — 기말잔액이 앵커이고 평잔계수만 파생이다.

    일별·월별 잔액 시계열이 원천 데이터에 없다. 계정마다 평잔계수를 뽑되
    **조달측은 운용측 평잔 총계에 맞춰 한 번에 비례 조정**한다. 조달과 운용은
    같은 자금의 양면이므로 총계가 갈리면 "자금조달 및 운용" 서식 자체가
    성립하지 않는다. 계정별로 조정하지 않고 한 배수를 곱하므로 조달측 구성비는
    뽑은 계수 그대로 남는다.

    대출채권 순액은 따로 뽑지 않고 총액 + 대손충당금(차감)으로 맞춘다 — 셋을
    독립으로 뽑으면 순액 정의가 깨진다.
    """
    t = ctx.tables["pru_balance_sheet"]
    item = t[~t["item"].isin(BS_TOTALS)].reset_index(drop=True)
    closing = dict(zip(item["item"].astype(str), item["amount"].astype(float)))
    # 계수 범위는 반기 중 잔액 변동폭 **가정**이며 관찰·추정 근거가 없다.
    # 중앙값이 0.99라 평잔은 기말잔액보다 평균 1% 낮게 나온다 — 잔액이 기중
    # 증가해 기말이 반기 평균보다 높다는 방향만 담은 것이고, 1을 중심에 둔
    # 대칭 분포가 아니다. 이 범위를 바꾸면 B2201 전 라인이 바뀐다.
    factor = dict(zip(item["item"].astype(str),
                      rng("기중평잔계수").uniform(0.94, 1.04, len(item))))
    avg = {k: closing[k] * factor[k] for k in closing}
    avg["대출채권 (순액)"] = avg["대출채권 (총액)"] + avg["대손충당금 (차감)"]

    rows = []
    for _, r in item.iterrows():
        name = str(r["item"])
        rows.append({"section": str(r["section"]), "item": name,
                     "closing": closing[name], "average": avg[name],
                     "in_total": name not in BS_SKIP})
    df = pd.DataFrame(rows)

    use = df[(df["section"] == USE_SECTION) & df["in_total"]]["average"].sum()
    fund_mask = df["section"].isin(FUNDING_SECTIONS) & df["in_total"]
    raw = float(df.loc[fund_mask, "average"].sum())
    k = float(use) / raw if raw else 1.0
    df.loc[df["section"].isin(FUNDING_SECTIONS), "average"] *= k
    df["scale"] = np.where(df["section"].isin(FUNDING_SECTIONS), k, 1.0)
    return df


# ---------------------------------------------------------------- 공공금고

def public_deposits(ctx) -> pd.DataFrame:
    """공공금고 예수금 — 법인 예수금 총액만 실측이고 금고 비중·유형 배분이 파생이다.

    금고 비중(법인 예수금의 3~9%)·유형 배분·계좌 수는 관찰 근거 없는 가정이며,
    금고 유형 어휘도 실제 지정 현황이 아니라 법령상 금고 구분을 따른 편제다.
    """
    amt = bs_amounts(ctx)
    corp = sum(amt[i] for i in CORP_DEPOSITS)
    share = float(rng("공공금고비중").uniform(0.03, 0.09))
    w = rng("공공금고배분").dirichlet(np.full(len(PUBLIC_TREASURY_KINDS), 2.0))
    n = rng("공공금고계좌수").integers(3, 40, len(PUBLIC_TREASURY_KINDS))
    return pd.DataFrame({
        "kind": list(PUBLIC_TREASURY_KINDS),
        "balance": corp * share * w,
        "n_account": n.astype(float),
        "corp_deposit_total": corp,
        "share": share,
    })


# ---------------------------------------------------------------- 인원·점포

def headcount(ctx) -> dict:
    """임직원 수 — 인사 원장이 없어 1인당 총자산에서 역산한다.

    **B1101(인원현황)을 만드는 모듈은 이 함수를 그대로 써야 한다.** 같은 은행의
    임직원 수가 생산성 서식과 인원현황 서식에서 다르면 제출본이 성립하지 않는다.
    현재 `forms_fss_general_data`가 이 함수를 import해 쓰고 있다.

    1인당 총자산 범위는 국내은행 실무 관찰치(대략 250~350억원)를 가정으로 쓴다.
    구성(임원·정규직·기간제)은 합이 총원이 되도록 잔여로 맞춘다. 임원 수와
    기간제 비중 범위는 관찰 근거 없는 가정이다.
    """
    total_assets = bs_amounts(ctx)["자산총계"]
    per_staff = float(rng("1인당총자산").uniform(2.6e10, 3.4e10))
    total = int(round(total_assets / per_staff))
    officer = int(rng("임원수").integers(8, 16))
    temporary = int(round((total - officer)
                          * float(rng("기간제비중").uniform(0.06, 0.14))))
    return {
        "total": float(total),
        "officer": float(officer),
        "temporary": float(temporary),
        "regular": float(total - officer - temporary),
        "assets_per_staff": per_staff,
    }


def domestic_branches(ctx) -> dict:
    """국내 점포 수 — 점포 원장이 없어 점포당 임직원 수에서 역산한다.

    B2701(점포당 생산성)과 B5103(자지점)이 같은 점포 수를 봐야 하므로 한 곳에서
    만든다. 본점은 언제나 1개이며 나머지가 지점이다.

    점포당 임직원 8~13인, 자지점·출장소 비율은 관찰 근거 없는 가정이다.
    """
    h = headcount(ctx)
    per_branch = float(rng("점포당임직원").uniform(8.0, 13.0))
    total = max(1, int(round(h["total"] / per_branch)))
    return {
        "head_office": 1.0,
        "branch": float(total - 1),
        "total": float(total),
        "sub_branch": float(round(total * float(rng("국내자지점비중")
                                                .uniform(0.05, 0.15)))),
        "sub_office": float(round(total * float(rng("국내출장소비중")
                                                .uniform(0.03, 0.10)))),
        "staff_per_branch": per_branch,
    }


# ---------------------------------------------------------------- 자회사 실적

def subsidiary_performance(ctx) -> pd.DataFrame:
    """자회사 경영실적 — 출자금액·지분율은 B3110과 같은 값, 재무·등급이 파생이다.

    자기자본은 난수로 뽑지 않고 **출자금액 ÷ 지분율**로 역산한다. 출자금액이
    자회사 순자산 중 은행 지분에 해당한다는 관계를 쓰면 세 값이 서로 대사된다.
    평가등급도 난수가 아니라 ROA의 결정론적 함수다 — 등급을 따로 뽑으면 실적이
    나쁜 자회사가 우수 등급을 받는 서식이 나온다.

    자산배수(4~12배)·ROA 범위는 관찰 근거 없는 가정이다. 자회사 총자산 계는
    B5101(연결 = 단독)의 연결 총자산에 들어가지 않는다 — 넣으면 B2109와 갈린다.
    """
    t = ctx.tables["pru_ownership_limit"]
    invested = float(t.loc[t["item"] == "자회사 출자", "used"].iloc[0])
    df = subsidiary_book(invested)
    df["equity"] = df["investment"] / df["stake"]
    df["total_assets"] = df["equity"] * rng("자회사자산배수").uniform(
        4.0, 12.0, len(df))
    df["net_income"] = df["total_assets"] * rng("자회사ROA").uniform(
        -0.005, 0.020, len(df))
    df["roa"] = df["net_income"] / df["total_assets"]
    df["grade"] = [_subsidiary_grade(v) for v in df["roa"]]
    return df


def _subsidiary_grade(roa: float) -> float:
    """경영평가 등급 1(우수)~5(위험) — ROA의 결정론적 구간 함수."""
    for cut, grade in ((0.015, 1.0), (0.010, 2.0), (0.005, 3.0), (0.0, 4.0)):
        if roa >= cut:
            return grade
    return 5.0


# ---------------------------------------------------------------- 금융회사 부채

def fi_liability_book(ctx, *, top_n: int = 12) -> pd.DataFrame:
    """타 금융회사 차입금의 상대방별 배분 — 상대방은 실재 은행, 배분만 파생이다.

    상대방을 지어내지 않는 것이 중요하다. 실재하지 않는 금융회사가 서식에 실리면
    제출 단계에서 대사할 상대가 없다. 사채는 불특정 다수 투자자가 보유하므로
    여기서 배분하지 않는다 — 합계는 차입금 두 계정뿐이다.
    """
    amt = bs_amounts(ctx)
    total = (amt["차입금 — 금융기관 6개월 이내"]
             + amt["차입금 — 금융기관 6~12개월"])
    p = ctx.portfolio
    banks = (p[p["asset_class"] == "bank"]
             .groupby("obligor_id", as_index=False)["ead"].sum()
             .sort_values("ead", ascending=False).head(top_n)
             .reset_index(drop=True))
    w = rng("금융회사차입배분").dirichlet(np.full(len(banks), 2.0))
    banks["borrowing"] = total * w
    return banks


# ---------------------------------------------------------------- G-SIB 지표

def substitutability(ctx) -> dict:
    """SCO40.7 대체가능성 지표 — 지급결제·보관·인수 원장이 없어 총자산에서 파생한다.

    **배수 세 개는 관찰·추정 근거가 없는 가정이다.** 자릿수만 맞춘 값이며
    실적 수치가 아니다. 특히 지급결제 배수는 결과가 자산총계의 10배를 넘어
    서식에서 가장 큰 금액이 되므로, 이 값을 활동량 실적으로 인용하면 안 된다.

    **지표 점수(bp)는 내지 않는다.** SCO40 점수는 표본 은행 전체의 지표 합계를
    분모로 쓰는데 업권 집계가 없다. 분모를 지어내면 있지도 않은 G-SIB 점수를
    보고하게 된다. 세 지표를 더한 값도 SCO40의 지표가 아니다 — 지급결제는 연간
    흐름이고 보관자산은 잔액이라 합계에 경제적 의미가 없다.
    """
    ta = bs_amounts(ctx)["자산총계"]
    g = rng("대체가능성")
    return {
        "payments": ta * float(g.uniform(12.0, 20.0)),      # 연간 지급결제 처리액
        "custody": ta * float(g.uniform(0.10, 0.30)),       # 보관자산
        "underwriting": ta * float(g.uniform(0.01, 0.03)),  # 인수 주선 금액
    }


def level3_assets(ctx) -> float:
    """SCO40.8 복잡성 — Level 3 공정가치 자산.

    공정가치 서열 원장이 없다. 기타자산의 2~8%라는 비율은 관찰·추정 근거가
    없는 가정이며, 실제 공정가치 서열 분류 결과가 아니다.
    """
    return bs_amounts(ctx)["기타자산"] * float(
        rng("Level3자산").uniform(0.02, 0.08))


def domestic_market_share(ctx) -> dict:
    """국내 시장점유율 — 업권 총계 원장이 없어 점유율을 뽑고 총계를 역산한다.

    반대로 업권 총계를 뽑아 점유율을 계산하면 자사 규모에 따라 점유율이 100%를
    넘을 수 있다. 점유율을 먼저 뽑으면 그런 값이 나오지 않는다.

    **점유율 범위 자체에 관찰·추정 근거가 없다.** 이 포트폴리오의 자산 규모와
    맞춰 잡은 값이 아니므로, B2217이 이 값에서 역산하는 "국내 은행권 총자산"은
    실제 업권 규모와 자릿수가 다를 수 있다 — 업권 통계로 인용하면 안 된다.
    """
    g = rng("국내점유율")
    return {
        "asset": float(g.uniform(0.03, 0.09)),
        "deposit": float(g.uniform(0.03, 0.09)),
        "payment": float(g.uniform(0.02, 0.08)),
    }
