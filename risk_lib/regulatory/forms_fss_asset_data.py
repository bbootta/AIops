"""자산건전성 서식(기업·일반여신)의 파생 데이터.

**여기서 만드는 값은 원장이 아니라 파생값이다.** FINES 자산건전성 서식은
여신종별(자금용도)·채권재조정 방식·전기말 잔액·사유별 증감 같은 원장 항목을
요구하는데, 이 저장소의 포트폴리오에는 해당 열이 없다. 상수를 박으면 서식이
산출과 무관해지고, 매 실행마다 난수를 새로 뽑으면 제출본 지문
(`forms.submission_digest`)이 흔들려 같은 제출본인지 판별할 수 없다. 그래서
**기준일 고정 시드에서 유도한 결정론적 RNG**로 만든다 — 같은 시드면 항상 같은 값이다.

파생 항목과 근거
  여신종별        asset_class로 고정 매핑하고, 기업여신만 sector 가중치로 4개
                  자금용도에 배분한다 (`loan_book`). 업종이 자금용도를 좌우한다는
                  관찰(건설·부동산 → 시설자금, 도소매 → 운전자금)을 가중치에 담았다.
  채권재조정 여신  요주의이하 익스포저 중 일부를 재조정 대상으로 고르고 방식을
                  부여한다 (`restructured`).
  변동표 기초잔액  **기말은 산출값을 앵커로 쓰고** 기초와 사유별 증감만 파생한다
                  (`derive_flow`). 그래서 "기초 + 증가 − 감소 = 기말" 항등식이
                  파생값끼리의 자기충족이 아니라 산출값에 묶인다.
  지급보증 대지급  지급보증성 미사용약정 잔액은 원장값이고, 그중 대지급으로
                  전이된 비율만 파생한다 (`guarantee_frame`).

파생값이 들어간 서식 라인은 formula에 "파생"임을 남긴다.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

_SEED_BASE = 20260630          # 파생 기준일 — 이 값을 바꾸면 파생값 전체가 바뀐다

AQ_ORDER = ("정상", "요주의", "고정", "회수의문", "추정손실")
NPL_CLASSES = ("고정", "회수의문", "추정손실")

CORP_PRODUCTS = ("기업운전자금대출", "기업시설자금대출", "상업어음할인", "무역금융")
PRODUCTS = CORP_PRODUCTS + ("금융기관대출", "공공자금대출",
                            "가계주택자금대출", "가계일반자금대출")

# 자산군이 자금용도를 결정하는 구간은 배분할 여지가 없다 — 고정 매핑한다.
_FIXED_PRODUCT = {
    "bank": "금융기관대출", "sovereign": "공공자금대출",
    "residential_mortgage": "가계주택자금대출", "retail_other": "가계일반자금대출",
}

# 기업여신 자금용도 가중치 (운전 · 시설 · 어음할인 · 무역금융).
_SECTOR_TILT = {
    "construction":  (0.25, 0.55, 0.10, 0.10),
    "real_estate":   (0.25, 0.55, 0.10, 0.10),
    "manufacturing": (0.45, 0.25, 0.20, 0.10),
    "retail_trade":  (0.55, 0.10, 0.25, 0.10),
    "shipping":      (0.25, 0.25, 0.10, 0.40),
    "energy":        (0.30, 0.30, 0.10, 0.30),
    "tech":          (0.50, 0.30, 0.15, 0.05),
    "financial":     (0.50, 0.20, 0.20, 0.10),
}
_DEFAULT_TILT = (0.40, 0.30, 0.18, 0.12)

GUARANTEE_CCF = ("direct_credit_substitute", "transaction_related")

_SUBRO_RATE_BAND = (0.008, 0.015)   # 대지급 전이율 가정 구간 — 관측 근거 없음


def rng(key: str) -> np.random.Generator:
    """기준일+키에서 유도한 난수원 — 키가 같으면 언제 어디서 불러도 같은 수열이다."""
    h = hashlib.sha256(f"{_SEED_BASE}:{key}".encode()).hexdigest()[:8]
    return np.random.default_rng(int(h, 16))


# ---------------------------------------------------------------- 여신 원장 결합

def loan_book(ctx) -> pd.DataFrame:
    """건전성분류 · 익스포저 · 차주를 한 장으로 묶고 여신종별을 파생한다."""
    aq = ctx.tables["rdm_asset_quality"]
    exp = ctx.tables["rdm_exposure"][
        ["exposure_id", "obligor_id", "asset_class", "undrawn", "ccf_type", "ead"]]
    ob = ctx.tables["rdm_obligor"][["obligor_id", "sector", "country"]]
    ecl = ctx.tables["ecl_result"][["exposure_id", "stage", "coverage_ratio"]]
    df = (aq.merge(exp, on="exposure_id")
            .merge(ob, on="obligor_id", how="left")
            .merge(ecl, on="exposure_id", how="left"))
    # 여신종별 배분은 행 순서에 의존한다 — 정렬을 고정해야 재현된다.
    df = df.sort_values("exposure_id").reset_index(drop=True)
    df["coverage_ratio"] = df["coverage_ratio"].fillna(0.0).astype(float)
    df["product"] = _assign_product(df)
    # 무수익여신 = 이자 미계상 여신. 여기서는 3개월 이상 연체 또는 고정이하 분류.
    df["npl"] = (df["dpd"] >= 90) | df["classification"].isin(NPL_CLASSES)
    return df


def _assign_product(df: pd.DataFrame) -> list[str]:
    g = rng("여신종별")
    out: list[str] = []
    for ac, sec in zip(df["asset_class"], df["sector"]):
        fixed = _FIXED_PRODUCT.get(str(ac))
        if fixed is not None:
            out.append(fixed)
            continue
        w = _SECTOR_TILT.get(str(sec), _DEFAULT_TILT)
        out.append(CORP_PRODUCTS[int(g.choice(len(CORP_PRODUCTS), p=w))])
    return out


# ---------------------------------------------------------------- 채권재조정

RESTRUCT_METHODS = ("만기연장", "이자율 조정", "원금상환 유예", "출자전환")

# 요주의이하 중 재조정 대상 비중. 원장·통계 근거가 있는 값이 아니라 **가정**이다 —
# 이 값을 바꾸면 B2407 규모가 통째로 바뀐다. 실제 TDR 원장이 붙으면 삭제한다.
_RESTRUCT_PICK = 0.28


def restructured(ctx) -> pd.DataFrame:
    """채권재조정 대상 — 요주의이하 익스포저 중에서 고른다.

    정상여신은 조건변경 사유가 약해 대상에서 뺀다. 잔액·충당금은 파생이 아니라
    선택된 익스포저의 실제 산출값을 그대로 쓴다.
    """
    book = loan_book(ctx)
    sub = book[book["classification"] != "정상"].reset_index(drop=True)
    if not len(sub):
        return sub.assign(method=pd.Series(dtype=object))
    picked = sub[rng("채권재조정선정").random(len(sub))
                 < _RESTRUCT_PICK].reset_index(drop=True)
    idx = rng("채권재조정방식").integers(0, len(RESTRUCT_METHODS), len(picked))
    picked["method"] = [RESTRUCT_METHODS[int(i)] for i in idx]
    return picked


# ---------------------------------------------------------------- 변동표

def _split(g: np.random.Generator, total: float, n: int) -> list[float]:
    """총액을 n개 사유로 쪼갠다. 마지막 항목에 잔차를 몰아 합계를 정확히 맞춘다."""
    w = g.dirichlet(np.full(n, 3.0))
    parts = [total * float(x) for x in w]
    parts[-1] = total - sum(parts[:-1])
    return parts


def derive_flow(key: str, closing: float,
                inc_labels: tuple[str, ...], dec_labels: tuple[str, ...],
                *, dec_total: float | None = None, gross: float = 0.35,
                open_band: tuple[float, float] = (0.85, 1.15)
                ) -> tuple[float, dict[str, float], dict[str, float]]:
    """기말(산출값)을 앵커로 기초·사유별 증감을 파생한다.

    증가 총액은 `기말 − 기초 + 감소 총액`으로 역산한다 — 이렇게 해야 항등식이
    파생 난수와 무관하게 성립하고, FormCheck가 서식 자체의 오류만 잡아낸다.

    `gross`(기말 대비 감소 총액 비율 35%)와 `open_band`(기초 = 기말 ±15%)는 관측
    근거가 없는 가정치다 — 총량 규모를 정하는 손잡이이지 측정값이 아니다.

    `dec_total`을 주면 감소 총액은 산출값이며 **고정 불변**이다. 이때 증가가 음수가
    되면 감소가 아니라 기초를 당긴다 — 감소를 손대면 "감소 계 = 산출 회수액" 대사가
    소리 없이 깨진다.
    """
    g = rng(key)
    opening = closing * float(g.uniform(*open_band))
    pinned = dec_total is not None
    dec = (float(dec_total) if pinned
           else abs(closing) * gross * float(g.uniform(0.8, 1.2)))
    inc = dec + (closing - opening)
    if inc < 0.0:                 # 순감소가 감소 총액보다 크면 음수 증가가 된다
        if pinned:
            opening, inc = closing + dec, 0.0
        else:
            dec, inc = dec - inc, 0.0
    return (opening, dict(zip(inc_labels, _split(g, inc, len(inc_labels)))),
            dict(zip(dec_labels, _split(g, dec, len(dec_labels)))))


# ---------------------------------------------------------------- 지급보증

def guarantee_frame(ctx) -> tuple[float, float]:
    """(지급보증 잔액, 지급보증대지급금 잔액).

    지급보증 잔액은 지급보증 성격 부외약정의 미사용액 — 원장값이다.
    대지급 전이율만 파생한다. 전이율 구간(0.8~1.5%)은 관측치가 아니라 **가정**이며,
    따라서 대지급금 잔액은 실측이 아니라 파생 규모다. 대지급 원장이 붙으면 삭제한다.
    """
    book = loan_book(ctx)
    base = float(book[book["ccf_type"].isin(GUARANTEE_CCF)]["undrawn"].sum())
    rate = float(rng("대지급전이율").uniform(*_SUBRO_RATE_BAND))
    return base, base * rate
