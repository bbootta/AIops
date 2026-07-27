"""신용카드 서식(FINES B28xx)의 파생 데이터.

**이 저장소에는 카드 원장이 없다.** 합성 포트폴리오의 `asset_class`는
bank/corporate/residential_mortgage/retail_other/sovereign 뿐이고 회원·카드·
가맹점·이용실적·리볼빙·포인트 원장은 아예 존재하지 않는다. 상수를 박으면 서식이
산출과 무관해지고, 실행마다 난수를 새로 뽑으면 제출본 지문
(`forms.submission_digest`)이 흔들려 같은 제출본인지 판별할 수 없다. 그래서
**기준일 고정 시드에서 유도한 결정론적 RNG**로 만든다 — 같은 시드면 항상 같은 값이다.

앵커 원칙: **금액은 산출값에 묶고, 건수·구성비만 파생한다.**

산출값에서 그대로 오는 것 (파생 아님)
  카드채권 잔액      `retail_other` 중 카드로 배정한 익스포저의 `rdm_asset_quality.balance`
                     실측 합. 배정 여부는 파생이지만 잔액 자체는 원장값이다.
  건전성분류·충당금   `rdm_asset_quality`의 5단계 분류·최저적립률·`ifrs9_provision`.
                     카드 서식이 자기 나름의 분류를 쓰면 B2421·B4101과 대사되지 않는다.
  연체기간           `rdm_delinquency.dpd` 실측. 버킷 경계만 감독기준이다.
  회원수(개인)        카드채권 차주(`obligor_id`)의 실측 고유 건수.
  카드부문 수익·비용   `portfolio.revenue` · `portfolio.operating_cost` 실측 합.
                     구성항목 배분비만 파생이므로 **합계는 손익계산서와 어긋나지 않는다.**
                     **기간 기준은 연간이다** (`revenue = ead × 연간 스프레드`).
                     이용금액·매출액은 월 기준이므로 두 값을 나누는 라인
                     (B2824 수수료율)은 기간이 섞인다 — `_TURNOVER_BAND` 경고 참조.
  등급별 이자율       등급별 실측 이자수익 ÷ 등급별 실측 잔액. 요율 자체가 산출값이다.
  이용한도           `balance ÷ utilization` 역산 — 실측 두 열의 결정론적 함수다.
  신용등급           `portfolio.pd` 십분위. 난수가 끼지 않는다.

시드 고정으로 파생하는 것 (원장 부재)
  카드 배정 여부      `retail_other` 중 한도소진율이 높고 잔존만기가 짧은 계좌에
                     가중을 준다 — 카드채권이 한도성·단기 상품이라는 성질을 담았다.
  상품 구성          일시불·할부·현금서비스·카드론·리볼빙 배분. **난수가 아니라
                     실측 PD·한도소진율의 결정론적 함수**이며 행별 합은 잔액과 정확히 같다.
  회전율             월 이용금액 ÷ 잔액. **가정치다**(`_TURNOVER_BAND` 주석 참조).
  회원 세분          가족회원·법인회원·보유 카드수·무실적 여부·모집경로.
  가맹점             가맹점수·매출 구간 구성비. 매출액 총액은 신용판매 이용금액에 앵커한다.
  대환대출           연체 없이 정상 분류된 계좌 중 PD가 높은 쪽에서 뽑는다.
                     연체채권과 겹치지 않게 만들어 B2815의 중복계상을 막는다.
  선불·직불·체크카드   발행좌수·이용금액. **앵커할 산출값이 없는 완전 파생이다.**
  포인트·선지급       적립은 신용판매 이용금액에 앵커하고 잔액 항등식만 파생으로 닫는다.
  부정사용           이용금액 대비 bps. 운영손실 원장에 외부사기 사건유형이 없어
                     `opr_loss_event`로 앵커할 수 없다.

파생값이 들어간 서식 라인은 **그 라인 자체의** formula에 "파생"임을 남긴다.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

_SEED_BASE = 20260630          # 파생 기준일 — 이 값을 바꾸면 파생값 전체가 바뀐다

AQ_ORDER = ("정상", "요주의", "고정", "회수의문", "추정손실")
NPL_CLASSES = ("고정", "회수의문", "추정손실")

# 신용판매(일시불·할부)와 부대업무(현금서비스·카드론·리볼빙)의 구분은
# 여신전문금융업법 **제13조**(신용카드업자의 부대업무) 비중 산정(B2811)의 모집단
# 정의다. 제46조는 여신전문금융회사의 업무 범위 조항이라 근거가 아니다.
# 다만 제13조제1항제1호의 부대업무는 "신용카드회원에 대한 자금의 융통"
# (= 현금서비스·카드론)이고 **리볼빙은 신용판매 대금의 이월이라 자금융통에
# 해당하는지가 판단사항**이다. 여기서는 실무 관행대로 부대업무에 넣되
# B2811에 제1호 기준(현금서비스+카드론) 라인을 따로 두고 비고로 공시한다.
PRODUCTS = ("일시불", "할부", "현금서비스", "카드론", "리볼빙")
CREDIT_SALE = ("일시불", "할부")
ANCILLARY = ("현금서비스", "카드론", "리볼빙")

# 연체기간 구분은 rdm_delinquency.dpd 실측에 그대로 얹는다 — 서식이 자기 버킷을
# 쓰면 B2422(연체기간별)·B4101(건전성)과 대사되지 않는다.
# 상한은 구간에 포함된다(`band_of`) — 1개월 = 30일이 "1개월 이상"으로 가도록
# 경계를 29·89·179로 둔다. 30을 상한으로 쓰면 dpd=30이 "1개월 미만"에 들어가
# B2822의 "1개월 이상 연체(dpd ≥ 30)" 소계와 구간 합이 어긋난다.
DPD_BANDS = ((0, "정상 (연체 없음)"), (29, "1개월 미만"), (89, "1~3개월"),
             (179, "3~6개월"), (10 ** 9, "6개월 이상"))

# 이용한도 구간. **경계는 가정이다.** FINES B2814의 실제 구간표는 마스터 서식에
# 딸린 별지이고 이 저장소에 없다. 합성 포트폴리오의 계좌당 잔액이 실제 카드계좌
# 규모와 달라 감독 실무의 천만원대 구간을 그대로 쓰면 전 계좌가 최상단 한 구간에
# 몰린다. 그래서 이 포트폴리오의 한도 분포를 가르는 사다리를 쓰고 가정임을 밝힌다.
LIMIT_BANDS = ((3e7, "3천만원 이하"), (7e7, "3천만~7천만원"),
               (1.5e8, "7천만~1억5천만원"), (3e8, "1억5천만~3억원"),
               (6e8, "3억~6억원"), (float("inf"), "6억원 초과"))

# 가맹점 매출 구간 — 여신전문금융업법 제18조의3 및 동 시행령의 우대수수료율
# 적용대상(연매출 3억원 이하 영세, 3~30억원 중소)을 따른다.
MERCHANT_TIERS = ("영세 (연매출 3억원 이하)", "중소1 (3~5억원)", "중소2 (5~10억원)",
                  "중소3 (10~30억원)", "일반 (30억원 초과)")
# 우대수수료율은 규정으로 고정된 값이므로 파생하지 않는다. 일반가맹점 요율만
# 협상요율이어서 자유변수로 두고, 실측 수수료수익에서 역산한다(`merchant_book`).
#
# 요율값은 여전법 제18조의3에 근거해 **금융위원회가 적격비용 재산정 결과로 고시**한
# 값이다(조문 자체에 숫자가 있는 것이 아니다). 아래는 **2025.2.14 시행분**이며
# 기준일(2026-06-30)에 유효한 판이다. 직전 판(2022.1.31~2025.2.13)은
# 0.50 / 1.10 / 1.25 / 1.50 이었다 — 판을 섞으면 어느 시점 기준도 아닌 값이 된다.
PREF_FEE_RATE = {"영세 (연매출 3억원 이하)": 0.0040, "중소1 (3~5억원)": 0.0100,
                 "중소2 (5~10억원)": 0.0115, "중소3 (10~30억원)": 0.0145}

RECRUIT_CHANNELS = ("모집인", "영업점 창구", "인터넷·모바일", "제휴·기타")
CARD_TYPES = ("신용카드", "체크카드", "직불카드", "선불카드")
FRAUD_TYPES = ("위·변조", "도난·분실", "명의도용", "기타")
FRAUD_BEARERS = ("카드사 부담", "가맹점 부담", "회원 부담")
TAX_ITEMS = ("국세", "지방세", "4대 사회보험료", "기타 공과금")
POINT_STEPS = ("기초잔액", "적립", "사용", "소멸", "기말잔액")

_CARD_BASE_RATE = 0.45         # retail_other 중 카드채권 배정 기준율 — 가정치

# 월 회전율(이용금액 ÷ 잔액) 구간. **가정치다.** 이용실적 원장이 없어 잔액에서
# 이용금액을 만들 수밖에 없다.
#
# **경고 — 기간 기준이 맞지 않는다.** 이 구간은 역산되는 일반가맹점 협상요율이
# 우대수수료율 위·감독규정 상한(2.3%) 아래에 놓이도록 맞춘 값이다. 그런데 역산의
# 분자인 가맹점수수료수익은 `portfolio.revenue`(= ead × **연간** 스프레드)의 배분액이고
# 분모인 가맹점 매출액은 이 회전율로 만든 **당월** 신용판매액이다. 즉 B2824의 요율은
# 연간수익 ÷ 당월매출의 혼합기준이며 규정 요율과 직접 비교할 수 없다.
# 기간을 맞추면(매출 × 12) 이 합성 포트폴리오의 카드수익은 우대수수료율 적용액에도
# 못 미쳐 협상요율이 음수가 된다 — 이 포트폴리오에서는 기간정합적 요율 역산이
# 성립하지 않는다. 회전율을 낮춰 맞추는 것은 이용실적을 비현실적으로 만들 뿐이므로
# 요율을 맞추지 않고 **B2824 비고 라인에 이 사실을 공시**한다.
_TURNOVER_BAND = {"일시불": (1.30, 1.55), "할부": (0.14, 0.17),
                  "현금서비스": (0.38, 0.52), "카드론": (0.05, 0.08),
                  "리볼빙": (0.10, 0.18)}
# 건당 평균 이용금액(원) 구간 — 이용건수를 만들기 위한 가정치다.
_TICKET_BAND = {"일시불": (5.0e4, 8.0e4), "할부": (3.5e5, 6.0e5),
                "현금서비스": (2.5e5, 4.5e5), "카드론": (2.5e6, 4.5e6),
                "리볼빙": (2.0e5, 4.0e5)}

# 상품별 수익률 배수 — 잔액이 같아도 카드론·현금서비스가 일시불보다 수익률이
# 높다는 성질만 담은 **가정치**다. 총액은 실측 revenue이므로 배수는 구성비만 바꾼다.
_YIELD = {"일시불": 1.0, "할부": 2.2, "현금서비스": 3.2, "카드론": 3.6,
          "리볼빙": 3.4}
_REV_OF = {"일시불": "가맹점수수료수익", "할부": "할부수수료수익",
           "현금서비스": "현금서비스수수료수익", "카드론": "카드론이자수익",
           "리볼빙": "리볼빙수수료수익"}
REVENUE_ITEMS = tuple(_REV_OF[p] for p in PRODUCTS) + ("연회비수익", "기타수익")
# 잔액과 무관한 수익 몫 — 연회비는 카드수에, 기타는 부수거래에 따르므로 잔액
# 배분에서 떼어 낸다. 비율은 가정치다.
_REV_FLAT = {"연회비수익": 0.06, "기타수익": 0.04}

COST_ITEMS = ("자금조달비용", "회원모집비용", "마케팅·포인트비용", "전산·업무처리비용",
              "일반관리비", "기타 판매관리비")
_COST_BAND = {"자금조달비용": (0.30, 0.38), "회원모집비용": (0.07, 0.11),
              "마케팅·포인트비용": (0.14, 0.20), "전산·업무처리비용": (0.09, 0.13),
              "일반관리비": (0.16, 0.22), "기타 판매관리비": (0.04, 0.08)}


def rng(key: str) -> np.random.Generator:
    """기준일+키에서 유도한 난수원 — 키가 같으면 언제 어디서 불러도 같은 수열이다."""
    h = hashlib.sha256(f"{_SEED_BASE}:{key}".encode()).hexdigest()[:8]
    return np.random.default_rng(int(h, 16))


def band_of(value: float, bands) -> str:
    """구간 라벨. 경계값은 아래 구간에 포함한다."""
    for upper, label in bands:
        if value <= upper:
            return label
    return bands[-1][1]


def _z(s: pd.Series) -> np.ndarray:
    v = s.to_numpy(dtype=float)
    sd = float(np.nanstd(v))
    return (v - float(np.nanmean(v))) / (sd if sd else 1.0)


def _draw(band: dict[str, tuple[float, float]], key: str) -> dict[str, float]:
    """항목별 구간에서 값 하나씩 — 항목 키가 시드에 들어가야 항목 순서에 안 흔들린다."""
    return {k: float(rng(f"{key}:{k}").uniform(lo, hi)) for k, (lo, hi) in band.items()}


def turnover() -> dict[str, float]:
    return _draw(_TURNOVER_BAND, "회전율")


def ticket() -> dict[str, float]:
    return _draw(_TICKET_BAND, "건당이용액")


# ---------------------------------------------------------------- 카드채권

def card_book(ctx) -> pd.DataFrame:
    """카드채권 프레임 — retail_other의 부분집합. 잔액·분류·연체는 전부 실측이다."""
    p = ctx.portfolio[[
        "exposure_id", "obligor_id", "country", "ead", "maturity", "dti",
        "utilization", "income_log", "pd", "lgd", "revenue", "operating_cost",
        "dpd"]]
    aq = ctx.tables["rdm_asset_quality"][[
        "exposure_id", "classification", "borrower_type", "balance",
        "min_provision_rate", "min_provision", "ifrs9_provision",
        "reserve_shortfall"]]
    ecl = ctx.tables["ecl_result"][["exposure_id", "stage", "ecl"]]
    # 파생 배정이 행 순서에 의존한다 — 정렬을 고정해야 재현된다.
    df = (ctx.portfolio[ctx.portfolio["asset_class"] == "retail_other"][["exposure_id"]]
          .merge(p, on="exposure_id").merge(aq, on="exposure_id")
          .merge(ecl, on="exposure_id", how="left")
          .sort_values("exposure_id").reset_index(drop=True))

    # 카드채권은 한도성·단기 상품이다 — 소진율이 높고 만기가 짧은 계좌에 가중.
    pr = np.clip(_CARD_BASE_RATE * np.exp(0.45 * _z(df["utilization"])
                                          - 0.25 * _z(df["maturity"])), 0.05, 0.95)
    df = df[rng("카드배정").random(len(df)) < pr].reset_index(drop=True)

    df["npl"] = df["classification"].isin(NPL_CLASSES)
    df["dpd_band"] = [band_of(v, DPD_BANDS) for v in df["dpd"]]
    # 이용한도는 난수가 아니라 실측 두 열의 역산이다. 소진율이 0에 가까우면
    # 한도가 발산하므로 2%에서 자른다 — 자른 계좌는 한도가 과소평가된다.
    df["limit"] = df["balance"] / df["utilization"].clip(lower=0.02)
    df["limit_band"] = [band_of(v, LIMIT_BANDS) for v in df["limit"]]
    # 신용등급은 PD 십분위 — 1등급이 최우량이다.
    df["grade"] = pd.qcut(df["pd"], 10, labels=range(1, 11)).astype(int)

    # 상품 구성비는 난수가 아니라 실측 PD·소진율의 함수다. 행별 합 = 잔액.
    zp, zu = _z(df["pd"]), _z(df["utilization"])
    w = np.column_stack([
        0.42 * np.exp(-0.25 * zp), 0.18 * np.exp(-0.10 * zp),
        0.12 * np.exp(0.35 * zp), 0.18 * np.exp(0.30 * zp),
        0.10 * np.exp(0.20 * zp + 0.30 * zu)])
    w = w / w.sum(axis=1, keepdims=True)
    tv, tk = turnover(), ticket()
    for i, prod in enumerate(PRODUCTS):
        df[f"bal_{prod}"] = df["balance"].to_numpy(dtype=float) * w[:, i]
        df[f"use_{prod}"] = df[f"bal_{prod}"] * tv[prod]
        df[f"cnt_{prod}"] = df[f"use_{prod}"] / tk[prod]

    # 대환대출은 연체를 대환해 정상으로 재분류된 채권이다 — 연체채권과 겹치면
    # B2815에서 중복계상되므로 연체 없는 정상 계좌에서만 뽑는다.
    elig = (df["dpd"].to_numpy() == 0) & (df["classification"] == "정상").to_numpy()
    pr_r = np.clip(0.06 * np.exp(1.2 * _z(df["pd"])), 0.0, 0.40)
    df["is_rollover"] = elig & (rng("대환").random(len(df)) < pr_r)
    return df


def use_total(cb: pd.DataFrame, products=PRODUCTS) -> float:
    return float(sum(cb[f"use_{p}"].sum() for p in products))


# ---------------------------------------------------------------- 회원·카드

def member_book(ctx) -> pd.DataFrame:
    """회원 프레임 — 개인 본인회원 수는 실측 차주 수, 나머지 세분은 파생."""
    cb = card_book(ctx)
    m = (cb.groupby("obligor_id", as_index=False)
         .agg(balance=("balance", "sum"), limit=("limit", "sum"),
              use=("use_일시불", "sum"), pd_=("pd", "mean"), dpd=("dpd", "max"),
              grade=("grade", "min"))
         .sort_values("obligor_id").reset_index(drop=True))
    n = len(m)
    # 보유 카드수 — 1매 이상, 한도가 클수록 많다.
    m["n_card"] = 1 + rng("보유카드수").poisson(
        np.clip(0.8 + 0.5 * _z(m["limit"]), 0.2, 3.0), n)
    # 가족회원은 본인회원에 딸린다 — 한도가 큰 회원에 가중.
    m["n_family"] = rng("가족회원").binomial(
        2, np.clip(0.12 + 0.05 * _z(m["limit"]), 0.01, 0.45), n)
    m["channel"] = [RECRUIT_CHANNELS[int(i)] for i in rng("모집경로").choice(
        len(RECRUIT_CHANNELS), n, p=[0.34, 0.26, 0.28, 0.12])]
    m["is_new"] = rng("신규모집").random(n) < 0.055
    # 무실적은 카드 단위로 생긴다 — 한도소진이 낮은 회원의 카드가 잠든다.
    # 모수는 본인카드 + 가족카드 전부다. 여기서 빠지면 B2803의 무실적 카드수가
    # B2802의 발급매수보다 작은 모집단에서 나와 두 서식이 대사되지 않는다.
    held = (m["n_card"] + m["n_family"]).to_numpy()
    p_dorm = np.clip(0.22 - 0.07 * _z(m["use"]), 0.02, 0.75)
    m["n_held"] = held
    m["n_dormant"] = rng("무실적카드").binomial(held, p_dorm)
    m["dormant_member"] = m["n_dormant"] >= held
    return m


def corporate_member(ctx) -> dict[str, float]:
    """법인회원 — 카드채권 차주가 전부 개인이라 앵커할 원장이 없는 완전 파생.

    무실적 판정(B2803) 모집단에서는 뺀다 — 법인카드는 법인 단위 이용실적이라
    개인카드의 휴면 판정 기준을 그대로 적용할 수 없다.
    """
    m, r = member_book(ctx), rng("법인회원")
    n = int(len(m) * float(r.uniform(0.03, 0.06)))
    return {"members": float(n), "cards": float(int(n * float(r.uniform(2.5, 5.0))))}


def card_type_summary(ctx) -> pd.DataFrame:
    """카드종류별 회원수·발급매수·이용금액 — B2802·B2809·B2823·B2827·B2829의 공용 원천.

    신용카드만 채권 잔액에 앵커되고 체크·직불·선불은 앵커할 산출값이 없다.
    """
    cb, m, corp = card_book(ctx), member_book(ctx), corporate_member(ctx)
    credit_cards = int(m["n_held"].sum() + corp["cards"])
    credit_members = int(len(m) + m["n_family"].sum() + corp["members"])
    credit_use = use_total(cb)
    r = rng("카드종류")
    # 체크·직불·선불 보유율과 이용배수는 완전 파생이다.
    chk_rate, dbt_rate = float(r.uniform(0.55, 0.75)), float(r.uniform(0.10, 0.20))
    chk_mult, dbt_mult = float(r.uniform(0.16, 0.26)), float(r.uniform(0.02, 0.05))
    pre = prepaid_book(ctx)
    rows = [
        ("신용카드", credit_members, credit_cards, credit_use),
        ("체크카드", int(len(m) * chk_rate), int(len(m) * chk_rate * 1.2),
         credit_use * chk_mult),
        ("직불카드", int(len(m) * dbt_rate), int(len(m) * dbt_rate),
         credit_use * dbt_mult),
        ("선불카드", 0, int(pre["issued_cards"]), float(pre["used"])),
    ]
    return pd.DataFrame(rows, columns=["card_type", "members", "cards", "usage"])


# ---------------------------------------------------------------- 수익·비용

def revenue_mix(ctx) -> pd.DataFrame:
    """카드부문 수익 배분 — 합계는 실측 revenue 합과 정확히 같고 구성비만 파생."""
    cb = card_book(ctx)
    rev = cb["revenue"].to_numpy(dtype=float)
    w = np.column_stack([cb[f"bal_{p}"].to_numpy(dtype=float) * _YIELD[p]
                         for p in PRODUCTS])
    w = w / w.sum(axis=1, keepdims=True) * (1.0 - sum(_REV_FLAT.values()))
    out = {"exposure_id": cb["exposure_id"].to_numpy(),
           "grade": cb["grade"].to_numpy(), "balance": cb["balance"].to_numpy()}
    for i, prod in enumerate(PRODUCTS):
        out[_REV_OF[prod]] = rev * w[:, i]
    for item, sh in _REV_FLAT.items():
        out[item] = rev * sh
    return pd.DataFrame(out)


def cost_mix(ctx) -> dict[str, float]:
    """카드부문 판매관리비 배분 — 합계는 실측 operating_cost 합과 정확히 같다."""
    total = float(card_book(ctx)["operating_cost"].sum())
    sh = _draw(_COST_BAND, "비용구성")
    s = sum(sh.values())
    return {k: total * v / s for k, v in sh.items()}


def credit_cost(ctx) -> float:
    """카드부문 대손비용 — 은행 전체 충당금 전입액을 카드 ECL 비중으로 배분한다."""
    cb = card_book(ctx)
    ecl_all = float(ctx.tables["ecl_result"]["ecl"].sum())
    share = float(cb["ecl"].sum()) / ecl_all if ecl_all else 0.0
    inc = ctx.tables["pru_income_statement"]
    charge = float(inc.loc[inc["item"] == "충당금 전입액", "amount"].iloc[0])
    return abs(charge) * share


# ---------------------------------------------------------------- 가맹점

def merchant_book(ctx) -> pd.DataFrame:
    """가맹점 구간표 — 매출액 총액은 신용판매 이용금액에 앵커, 구성비는 파생.

    우대수수료율(영세·중소)은 규정 고정값이므로 파생하지 않는다. 일반가맹점
    요율만 협상요율이어서 실측 가맹점수수료수익에서 역산한다 — 그래야 구간별
    수수료수익 합계가 수익구조(B2816)와 어긋나지 않는다.
    """
    cb = card_book(ctx)
    sales_total = use_total(cb, CREDIT_SALE)
    fee_total = float(revenue_mix(ctx)["가맹점수수료수익"].sum())
    r = rng("가맹점구성")
    s_share = r.dirichlet(np.array([14.0, 9.0, 11.0, 22.0, 44.0]))
    sales = sales_total * s_share
    # 가맹점수는 구간 매출액에서 역산한다. 전체 평균 연매출로 나누면 구간별
    # 가맹점당 연매출이 그 구간의 정의 범위를 벗어난다 — 구간 안의 대표 연매출로
    # 나눠야 "연매출 3억원 이하 가맹점"이 실제로 3억원 이하가 된다.
    rep = np.array([float(r.uniform(lo, hi)) for lo, hi in
                    ((1.0e8, 2.4e8), (3.2e8, 4.6e8), (5.5e8, 9.0e8),
                     (1.2e9, 2.6e9), (4.0e9, 9.0e9))])
    df = pd.DataFrame({
        "tier": MERCHANT_TIERS,
        "merchants": np.maximum(1, (sales * 12.0 / rep).round().astype(int)),
        "annual_avg": rep, "sales": sales})
    pref = np.array([PREF_FEE_RATE.get(t, np.nan) for t in MERCHANT_TIERS])
    pref_fee = float(np.nansum(pref * df["sales"].to_numpy()))
    gen_sales = float(df.loc[df["tier"] == MERCHANT_TIERS[-1], "sales"].iloc[0])
    gen_rate = (fee_total - pref_fee) / gen_sales if gen_sales else 0.0
    df["fee_rate"] = np.where(np.isnan(pref), gen_rate, pref)
    df["fee"] = df["fee_rate"] * df["sales"]
    return df


# ---------------------------------------------------------------- 선불·포인트

def prepaid_book(ctx) -> dict[str, float]:
    """선불카드 원장 — 앵커할 산출값이 없는 완전 파생이다.

    발행액 − 사용액 = 미사용잔액 항등식만 파생 안에서 닫는다. 유효기간(통상 5년)
    경과분과 상법 제64조 상사소멸시효 경과분은 미사용잔액의 부분집합이다.
    """
    cb = card_book(ctx)
    r = rng("선불카드")
    # 발행규모는 신용판매 이용금액 대비 소액이다 — 배수 자체가 가정치다.
    issued = use_total(cb, CREDIT_SALE) * float(r.uniform(0.004, 0.009))
    used = issued * float(r.uniform(0.72, 0.86))
    unused = issued - used
    expired = unused * float(r.uniform(0.18, 0.30))          # 유효기간 경과
    prescribed = expired * float(r.uniform(0.25, 0.40))      # 소멸시효 경과
    cards = float(int(issued / float(r.uniform(3.0e4, 6.0e4))))
    return {
        "issued": issued, "used": used, "unused": unused,
        "unused_valid": unused - expired, "expired": expired,
        "prescribed": prescribed, "restored": prescribed * float(r.uniform(0.05, 0.15)),
        "donated": prescribed * float(r.uniform(0.10, 0.25)),
        "issued_cards": cards,
        "new_cards": float(int(cards * float(r.uniform(0.22, 0.34)))),
    }


def point_book(ctx) -> dict[str, float]:
    """포인트 운영 — 적립은 신용판매 이용금액에 앵커, 나머지는 항등식으로 닫는다."""
    cb = card_book(ctx)
    r = rng("포인트")
    sales = use_total(cb, CREDIT_SALE)
    earned = sales * float(r.uniform(0.006, 0.011))          # 적립률
    opening = earned * float(r.uniform(1.4, 2.2))
    used = earned * float(r.uniform(0.70, 0.88))
    lapsed = earned * float(r.uniform(0.04, 0.09))
    return {"기초잔액": opening, "적립": earned, "사용": used, "소멸": lapsed,
            "기말잔액": opening + earned - used - lapsed,
            "기부": used * float(r.uniform(0.004, 0.012))}


def prepay_service(ctx) -> dict[str, float]:
    """선지급서비스(포인트 선지급) — 완전 파생. 잔액 항등식만 닫는다."""
    cb = card_book(ctx)
    r = rng("선지급")
    granted = use_total(cb, CREDIT_SALE) * float(r.uniform(0.003, 0.007))
    opening = granted * float(r.uniform(1.1, 1.8))
    repaid = granted * float(r.uniform(0.78, 0.92))
    written_off = granted * float(r.uniform(0.01, 0.03))
    closing = opening + granted - repaid - written_off
    return {"기초잔액": opening, "선지급액": granted, "회수액": repaid,
            "상각액": written_off, "기말잔액": closing,
            "연체잔액": closing * float(r.uniform(0.05, 0.12)),
            "약정회원수": float(int(len(member_book(ctx)) * r.uniform(0.06, 0.14)))}


# ---------------------------------------------------------------- 부정사용·납세

def fraud_book(ctx) -> pd.DataFrame:
    """부정사용 유형 × 책임분담 — 완전 파생.

    `opr_loss_event`에 외부사기 사건유형이 없어 운영손실 원장으로 앵커할 수 없다.
    금액은 이용금액 대비 bps로만 만든다.
    """
    cb = card_book(ctx)
    r = rng("부정사용")
    total = use_total(cb) * float(r.uniform(2.0e-5, 4.5e-5))
    type_share = r.dirichlet(np.array([18.0, 46.0, 24.0, 12.0]))
    # 책임분담 비율은 여신전문금융업법 제16조의 원칙(원칙적 카드사 부담,
    # 회원 고의·중과실 시 회원 분담)을 반영한 파생 구성비다.
    bearer = np.array([[0.86, 0.09, 0.05], [0.72, 0.14, 0.14],
                       [0.80, 0.13, 0.07], [0.68, 0.20, 0.12]])
    amt = total * type_share
    df = pd.DataFrame(bearer * amt[:, None], columns=list(FRAUD_BEARERS))
    df.insert(0, "fraud_type", list(FRAUD_TYPES))
    df["amount"] = amt
    # 유형별 건수는 만들지 않는다. 이 포트폴리오 규모에서 부정사용 금액은
    # 건당 평균으로 나누면 유형별 0~2건이 되어 "금액은 있는데 건수는 0"인
    # 서식이 나온다 — 총 건수 한 줄만 두고 유형 분해는 금액으로만 한다.
    df.attrs["cases"] = max(1, int(round(total / float(r.uniform(4.0e5, 9.0e5)))))
    return df


def tax_payment(ctx) -> pd.DataFrame:
    """국세·지방세 등 카드 납부실적 — 이용금액 대비 비중이 파생이다."""
    cb = card_book(ctx)
    r = rng("납세")
    total = use_total(cb, CREDIT_SALE) * float(r.uniform(0.030, 0.055))
    share = r.dirichlet(np.array([44.0, 31.0, 15.0, 10.0]))
    tk = float(r.uniform(4.0e5, 8.0e5))
    return pd.DataFrame({"item": list(TAX_ITEMS), "amount": total * share,
                         "cases": (total * share / tk).round().astype(int)})


def overseas_use(ctx) -> pd.DataFrame:
    """해외회원의 국내 이용실적 — 완전 파생.

    카드채권 차주는 전부 국내(KR) 거주이고 해외 발행 카드 원장이 없다.
    발행국 구분만 포트폴리오의 국가 도메인에서 가져오고 금액은 파생이다.
    """
    cb = card_book(ctx)
    countries = sorted(c for c in ctx.portfolio["country"].unique() if c != "KR")
    r = rng("해외회원")
    total = use_total(cb, CREDIT_SALE) * float(r.uniform(0.015, 0.035))
    share = r.dirichlet(np.full(len(countries), 8.0))
    tk = float(r.uniform(1.2e5, 2.4e5))
    return pd.DataFrame({"country": countries, "amount": total * share,
                         "cases": (total * share / tk).round().astype(int)})
