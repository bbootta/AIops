"""업무규제 준수 서식의 파생 데이터.

**여기서 만드는 값은 원장이 아니라 파생값이다.** FINES 업무규제 준수 서식은
자회사 명세·금융채권 발행이력·타은행주식 보유·대출모집 위탁사·임직원 소액대출
처럼 이 저장소의 포트폴리오·정규테이블에 열이 없는 항목을 요구한다. 상수를
박으면 서식이 산출과 무관해지고, 실행마다 난수를 새로 뽑으면 제출본 지문
(`forms.submission_digest`)이 흔들려 같은 제출본인지 판별할 수 없다. 그래서
**기준일 고정 시드에서 유도한 결정론적 RNG**로 만든다 — 같은 시드면 언제나
같은 값이다.

파생하되 **총액은 산출값에 앵커**한다. 자회사 출자 배분은 개별 비율만 파생하고
합계는 `pru_ownership_limit`의 산출 사용액이며, 금융채권 종류·잔존만기 배분은
합계가 재무상태표의 "사채 및 장기차입금"이고 후순위 은행채는 보완자본
인정액 그 자체다. 그래서 "명세 합계 = 산출 총액" FormCheck는 파생 난수끼리의
자기충족이 아니라 산출값과의 대사가 된다.

파생하지 않은 것(0으로 두고 사유를 서식 라인에 남긴다)
  대주주 신용공여 · 임원과의 거래   대주주 지정 원장 미확보
  자기주식 보유                   CET1 자기주식 차감이 실제로 0이다
  적격 CCP 익스포저                거래상대방 원장이 전량 은행이다
"""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

_SEED_BASE = 20260630          # 파생 기준일 — 이 값을 바꾸면 파생값 전체가 바뀐다


def rng(key: str) -> np.random.Generator:
    """기준일+키에서 유도한 난수원 — 키가 같으면 언제 어디서 불러도 같은 수열이다."""
    h = hashlib.sha256(f"{_SEED_BASE}:{key}".encode()).hexdigest()[:8]
    return np.random.default_rng(int(h, 16))


# ---------------------------------------------------------------- 자회사

# 자회사 명칭 어휘. 은행법 제37조 제2항은 업종을 열거하지 않으므로 이 목록은
# 규정 인용이 아니라 **편제용 예시 어휘**다 — 업종 구성·출자금액·지분율 모두
# 파생이며, 실제 제출 시 자회사 마스터로 대체된다.
SUBSIDIARY_LINES: tuple[str, ...] = (
    "신용카드업", "시설대여·할부금융업", "집합투자업", "상호저축은행업",
    "부동산신탁업", "해외현지법인(베트남)", "해외현지법인(미국)", "핀테크(전자금융업)",
)


def subsidiary_book(total_investment: float) -> pd.DataFrame:
    """자회사 명세 — 출자 **총액만** 산출값이고 개별 배분·지분율·신용공여는 파생이다.

    지분율은 51% 이상으로 뽑는다. 은행법상 자회사 요건은 의결권주식 15% 초과지만
    15~50% 구간을 섞으면 "자회사인지 출자회사인지" 서식 대상 범위가 흔들린다.
    """
    n = len(SUBSIDIARY_LINES)
    w = rng("자회사출자배분").dirichlet(np.full(n, 2.5))
    inv = total_investment * w
    return pd.DataFrame({
        "name": SUBSIDIARY_LINES,
        "investment": inv,
        "stake": rng("자회사지분율").uniform(0.51, 1.00, n),
        # 자회사 신용공여는 출자금액에 비례해 뽑는다 — 규모가 큰 자회사에
        # 여신도 크다는 관찰을 담되, 개별 10%·합계 20% 한도 안에 들어온다.
        "credit": inv * rng("자회사신용공여").uniform(0.02, 0.30, n),
    })


# ---------------------------------------------------------------- 타은행주식

def bank_share_book(portfolio: pd.DataFrame, *, top_n: int = 10) -> pd.DataFrame:
    """타은행주식 보유 — 발행은행은 **실제 거래상대방**이고 보유액·지분율이 파생이다.

    발행은행을 지어내지 않는 것이 중요하다. 실재하지 않는 은행이 서식에 실리면
    제출 단계에서 대사할 상대가 없다.
    """
    banks = (portfolio[portfolio["asset_class"] == "bank"]
             .groupby("obligor_id", as_index=False)["ead"].sum()
             .sort_values("ead", ascending=False).head(top_n)
             .reset_index(drop=True))
    n = len(banks)
    banks["holding"] = banks["ead"] * rng("타은행주식보유").uniform(0.004, 0.020, n)
    # 지분율은 9% 이하로 뽑는다 — 은행법 제37조 제1항 15% 한도를 파생값이
    # 스스로 넘으면 있지도 않은 위반을 보고하게 된다.
    banks["stake"] = rng("타은행지분율").uniform(0.005, 0.090, n)
    return banks


# ---------------------------------------------------------------- 대출모집 위탁

def loan_agent_book(household_balance: float, *, n_firm: int = 6
                    ) -> pd.DataFrame:
    """대출모집 위탁 현황 — 대상 가계여신 잔액만 산출값이고 위탁 비중이 파생이다."""
    share = float(rng("모집위탁비중").uniform(0.15, 0.35))
    w = rng("모집위탁배분").dirichlet(np.full(n_firm, 2.0))
    return pd.DataFrame({
        "name": [f"대출모집법인 {i:02d}" for i in range(1, n_firm + 1)],
        "balance": household_balance * share * w,
        "n_agent": rng("모집인수").integers(40, 260, n_firm).astype(float),
    })


# ---------------------------------------------------------------- 금융채권

DEBENTURE_BANDS: tuple[str, ...] = ("1년 이하", "1~2년", "2~3년", "3~5년", "5년 이상")
DEBENTURE_BAND_MID: tuple[float, ...] = (0.5, 1.5, 2.5, 4.0, 7.0)
"""가중평균 잔존만기 산정용 구간 중값 — 서식이 wam을 재계산해 대사한다."""


def debentures(closing: float, subordinated: float, *, months: int = 6) -> dict:
    """금융채권 발행·상환·잔존만기.

    산출값 앵커 두 개 — 기말 잔액은 재무상태표의 "사채 및 장기차입금"이고,
    후순위 은행채는 보완자본 인정 후순위채 그 자체다. 나머지(기초잔액·발행액·
    종류 배분·잔존만기 배분·월별 발행)가 파생이다.

    상환액은 뽑지 않고 `기초 + 발행 − 기말`로 역산한다. 기초를 기말의 88% 아래로
    뽑지 않고 발행을 기말의 15% 이상으로 뽑으므로 역산 상환액은 항상 양수다.
    """
    rest = closing - subordinated
    senior = float(rng("은행채구성").uniform(0.60, 0.80))
    kinds = {
        "일반 은행채(선순위)": rest * senior,
        "후순위 은행채": subordinated,
        "기타 장기차입금": rest * (1.0 - senior),
    }
    opening = closing * float(rng("은행채기초").uniform(0.88, 1.08))
    issued = closing * float(rng("은행채발행").uniform(0.15, 0.30))

    w = rng("은행채잔존만기").dirichlet(np.full(len(DEBENTURE_BANDS), 2.0))
    buckets = dict(zip(DEBENTURE_BANDS, rest * w))
    # 후순위채는 자본인정 요건이 잔존만기라 5년 이상 구간에 고정한다.
    buckets["5년 이상"] += subordinated
    wam = sum(m * buckets[b] for m, b in zip(DEBENTURE_BAND_MID, DEBENTURE_BANDS)) / closing

    return {
        "closing": closing, "opening": opening, "issued": issued,
        "redeemed": opening + issued - closing,
        "kinds": kinds, "buckets": buckets, "wam": wam,
        "monthly": issued * rng("은행채월별발행").dirichlet(np.full(months, 3.0)),
    }


# ---------------------------------------------------------------- 임직원 소액대출

# 은행법 제38조 제6호는 임직원 대출을 금지하고, 은행업감독규정 제55조가
# 소액대출을 예외로 두면서 1인당 2천만원 한도를 정한다.
STAFF_LOAN_LIMIT = 20_000_000.0
STAFF_LOAN_BANDS: tuple[tuple[float, float, str], ...] = (
    (0.0, 5_000_000.0, "500만원 이하"),
    (5_000_000.0, 10_000_000.0, "500만~1,000만원"),
    (10_000_000.0, 15_000_000.0, "1,000만~1,500만원"),
    (15_000_000.0, 20_000_000.0, "1,500만~2,000만원"),
)


def staff_loan_terms() -> dict:
    """임직원 소액대출 조건 — 원장에 금리 열이 없어 전부 파생이다.

    임직원 금리를 일반 가계신용대출 금리 **아래**로 뽑는다. 소액대출은 유리한
    조건이 허용되는 예외이므로 방향이 반대면 서식이 규정을 거꾸로 말하게 된다.
    """
    g = rng("임직원소액대출조건")
    market = float(g.uniform(0.055, 0.075))
    return {
        "market_rate": market,
        "staff_rate": market - float(g.uniform(0.010, 0.025)),
        "tenor_years": float(g.uniform(3.0, 5.0)),
        "limit": STAFF_LOAN_LIMIT,
    }


def staff_loans() -> pd.DataFrame:
    """임직원 소액대출 취급실적 — 건수·금액 모두 파생이다 (취급 원장 미보유).

    구간별 평균 대출금액을 구간 안에서 뽑으므로 어떤 건도 1인당 한도를 넘지 않는다.
    """
    n_total = int(rng("임직원소액대출건수").integers(1_800, 3_200))
    w = rng("임직원소액대출구간").dirichlet(np.full(len(STAFF_LOAN_BANDS), 2.0))
    counts = np.floor(n_total * w).astype(int)
    counts[-1] += n_total - int(counts.sum())      # 내림 잔여는 마지막 구간에
    pos = rng("임직원소액대출평균").uniform(0.45, 0.85, len(STAFF_LOAN_BANDS))
    avg = np.array([lo + (hi - lo) * p
                    for (lo, hi, _), p in zip(STAFF_LOAN_BANDS, pos)])
    return pd.DataFrame({
        "band": [b for _, _, b in STAFF_LOAN_BANDS],
        "band_cap": [hi for _, hi, _ in STAFF_LOAN_BANDS],
        "n": counts.astype(float), "avg_amount": avg,
        "amount": counts * avg,
    })


# ---------------------------------------------------------------- 전기말 대비

def prior_period(cet1: float, components: pd.DataFrame) -> dict:
    """전기말 자본·RWA — 전기 원장이 없어 당기 산출값에서 파생한다.

    당기 수치는 전부 산출값이고 전기 수치만 파생이므로, 변동요인 분해식
    (자본효과 + RWA효과 + 교차항 = 비율 변동)은 파생 난수끼리의 자기충족이
    아니라 항등식 검증이 된다.
    """
    prev_comp = (components["rwa"].to_numpy(dtype=float)
                 * rng("전기말RWA구성").uniform(0.92, 1.08, len(components)))
    return {
        "cet1": cet1 * float(rng("전기말자본").uniform(0.94, 1.02)),
        "components": prev_comp,
        "rwa": float(prev_comp.sum()),
    }
