"""가계·주담대·부동산 서식의 파생 데이터.

**여기서 만드는 값 중 일부는 원장이 아니라 파생값이다.** FINES 가계여신 서식은
지역·자금용도·상환방식·신규취급 여부처럼 이 저장소의 포트폴리오에 열이 없는
항목을 요구한다. 상수를 박으면 서식이 산출과 무관해지고, 실행마다 난수를 새로
뽑으면 제출본 지문(`forms.submission_digest`)이 흔들려 같은 제출본인지 판별할 수
없다. 그래서 **기준일 고정 시드에서 유도한 결정론적 RNG**로 만든다 — 같은 시드면
언제나 같은 값이다.

원장에서 그대로 오는 것 (파생 아님)
  LTV · DTI        `portfolio.ltv` · `portfolio.dti` 실측값. 구간 경계만 감독기준.
  소득구간          `income_log`의 결정론적 역변환. 난수가 끼지 않는다.
                    다만 **단위는 가정이다** — `INCOME_UNIT_KRW` 주석을 보라.
  잔존만기 구간      `portfolio.maturity` 실측값.
  담보유형          `rdm_collateral.collateral_type` + `rdm_guarantee` 원장.
                    담보 원장이 있으므로 담보구분을 난수로 만들지 않는다.
  건전성분류·충당금  `rdm_asset_quality` · `ecl_result` 산출값.

시드 고정으로 파생하는 것 (원장 부재)
  지역             수도권/광역시/기타 지방. `income_log` z-점수로 수도권 가중을
                   올린다 — 소득이 높을수록 수도권 비중이 크다는 관찰을 담았다.
  자금용도          주택구입/생계자금/기타. 주담대는 LTV가 높을수록 주택구입,
                   기타가계는 `utilization`·`dti`가 높을수록 생계자금으로 기운다.
  상환방식          분할/일시/거치식. 주담대는 LTV가 높을수록 거치식, 기타가계는
                   한도소진율이 높을수록 일시상환(마이너스한도)으로 기운다.
  신규취급 여부      상품별 월중 신규취급 기준율에 소득 z-점수를 곱해 뽑되,
                   **연체 중인 여신은 당월 신규취급에서 제외**한다(실무 제약).
  연체·상각 추이     과거 11개월만 파생하고 **당월은 산출값을 그대로 쓴다**.

파생값이 들어간 서식 라인은 formula에 "파생"임을 남긴다.
"""

from __future__ import annotations

import hashlib
import math

import numpy as np
import pandas as pd

_SEED_BASE = 20260630          # 파생 기준일 — 이 값을 바꾸면 파생값 전체가 바뀐다

AQ_ORDER = ("정상", "요주의", "고정", "회수의문", "추정손실")
NPL_CLASSES = ("고정", "회수의문", "추정손실")
HOUSEHOLD_CLASSES = ("residential_mortgage", "retail_other")

REGIONS = ("수도권", "광역시", "기타 지방")
PURPOSES = ("주택구입", "생계자금", "기타")
REPAY_TYPES = ("분할상환", "일시상환", "거치식")

# 구간 경계는 국내 감독 실무 기준이다 — LTV 40/50/60/70/80%, DTI 30/40/50/60%
# (은행업감독규정 제29조의2 및 동 시행세칙 별표6 주택관련담보대출 한도 체계).
LTV_BANDS = ((0.40, "LTV 40% 이하"), (0.50, "LTV 40~50%"), (0.60, "LTV 50~60%"),
             (0.70, "LTV 60~70%"), (0.80, "LTV 70~80%"), (math.inf, "LTV 80% 초과"))
DTI_BANDS = ((0.30, "DTI 30% 이하"), (0.40, "DTI 30~40%"), (0.50, "DTI 40~50%"),
             (0.60, "DTI 50~60%"), (math.inf, "DTI 60% 초과"))
# `income_log` → 연소득(원) 환산배수. **이 값은 가정이며 원장 규약이 아니다.**
# `datamodel/catalog.py`는 `income_log`의 unit을 `log_KRW`로 적어 두었고
# `data_gen.py`는 단위를 말하지 않는다. catalog 규약을 그대로 쓰면
# exp(10.5) = 36,316원이 연소득이 되어 성립하지 않으므로, 이 서식은 천원 단위
# 로그소득으로 **가정**해 1,000을 곱한다. 가정이 틀리면 B2426-1의 소득구간
# 분포 전체가 한 구간으로 무너진다 — 원장에 단위가 확정되면 여기부터 고친다.
INCOME_UNIT_KRW = 1_000.0

# 소득구간은 연소득(원) 기준.
INCOME_BANDS = ((30e6, "3천만원 이하"), (50e6, "3천~5천만원"),
                (70e6, "5천~7천만원"), (100e6, "7천만~1억원"),
                (math.inf, "1억원 초과"))
MATURITY_BANDS = ((1.0, "1년 이하"), (3.0, "1~3년"), (5.0, "3~5년"),
                  (10.0, "5~10년"), (math.inf, "10년 초과"))

# 담보 원장 코드 → FINES 담보구분. 원장에 없는 익스포저만 보증/신용으로 떨어진다.
COLLATERAL_BUCKETS = ("부동산담보", "예금·적금담보", "유가증권담보",
                      "보증서담보", "신용(무담보)")
_COLL_BUCKET = {
    "real_estate": "부동산담보",
    "cash": "예금·적금담보",
    "gold": "유가증권담보",
    "corporate_bond_ig": "유가증권담보",
    "equity_main_index": "유가증권담보",
    "sovereign_aaa_le1y": "유가증권담보",
    "sovereign_aaa_gt1y": "유가증권담보",
}

# 월중 신규취급 기준율 — **가정치다. 관찰·추정 근거가 없다.**
# 원장에 취급일자가 없어 월중 신규취급을 판정할 수 없으므로 상품별 월 회전율을
# 가정으로 놓았다. 잔존만기만으로 역산하면 20년 주담대가 월 0.4%가 되어
# 신규취급 서식이 사실상 비므로 그 대신 쓴 값이며, 실무 관찰치가 아니다.
# 이 값을 바꾸면 B2419·B2426·B2426-1·B2430-1·B2433의 신규취급 라인이 전부 바뀐다.
NEW_RATE = {"residential_mortgage": 0.035, "retail_other": 0.060,
            "corporate": 0.035}


def rng(key: str) -> np.random.Generator:
    """기준일+키에서 유도한 난수원 — 키가 같으면 언제 어디서 불러도 같은 수열이다."""
    h = hashlib.sha256(f"{_SEED_BASE}:{key}".encode()).hexdigest()[:8]
    return np.random.default_rng(int(h, 16))


def band_of(value: float, bands: tuple[tuple[float, str], ...]) -> str:
    """구간 라벨. 경계값은 아래 구간에 포함한다 (LTV 40.0% → '40% 이하')."""
    for upper, label in bands:
        if value <= upper:
            return label
    return bands[-1][1]


def _pick(key: str, weights: np.ndarray, labels: tuple[str, ...]) -> list[str]:
    """행별 확률로 라벨을 하나씩 뽑는다 — 행 순서가 고정돼야 재현된다."""
    w = weights / weights.sum(axis=1, keepdims=True)
    u = rng(key).random(len(w))
    idx = (w.cumsum(axis=1) < u[:, None]).sum(axis=1).clip(0, w.shape[1] - 1)
    return [labels[int(i)] for i in idx]


def _z(s: pd.Series) -> np.ndarray:
    v = s.to_numpy(dtype=float)
    sd = float(np.nanstd(v))
    return (v - float(np.nanmean(v))) / (sd if sd else 1.0)


# ---------------------------------------------------------------- 가계여신 프레임

def household(ctx) -> pd.DataFrame:
    """가계여신(주담대 + 기타가계) 통합 프레임 — 산출값 + 파생 구분열."""
    p = ctx.portfolio[[
        "exposure_id", "obligor_id", "asset_class", "country", "ead", "maturity",
        "ltv", "dti", "utilization", "income_log", "months_employed",
        "credit_score", "dpd"]]
    aq = ctx.tables["rdm_asset_quality"][[
        "exposure_id", "classification", "borrower_type", "balance",
        "min_provision", "ifrs9_provision", "reserve_shortfall"]]
    ecl = ctx.tables["ecl_result"][["exposure_id", "stage", "coverage_ratio"]]
    # 파생 배정이 행 순서에 의존한다 — 정렬을 고정해야 재현된다.
    df = (p[p["asset_class"].isin(HOUSEHOLD_CLASSES)]
          .merge(aq, on="exposure_id")
          .merge(ecl, on="exposure_id", how="left")
          .sort_values("exposure_id").reset_index(drop=True))

    df["is_mortgage"] = df["asset_class"] == "residential_mortgage"
    df["npl"] = df["classification"].isin(NPL_CLASSES)
    # 소득구간은 난수가 아니라 income_log의 역변환이다. 단위배수는 가정이다
    # (INCOME_UNIT_KRW 주석 참조) — 난수가 아니라는 것과 실측이라는 것은 다르다.
    df["annual_income"] = (np.exp(df["income_log"].to_numpy(dtype=float))
                           * INCOME_UNIT_KRW)
    df["income_band"] = [band_of(v, INCOME_BANDS) for v in df["annual_income"]]
    df["dti_band"] = [band_of(v, DTI_BANDS) for v in df["dti"]]
    df["maturity_band"] = [band_of(v, MATURITY_BANDS) for v in df["maturity"]]
    df["ltv_band"] = [band_of(v, LTV_BANDS) if pd.notna(v) else None
                      for v in df["ltv"]]

    zi = _z(df["income_log"])
    ltv_f = df["ltv"].fillna(0.65).to_numpy(dtype=float)
    util_f = df["utilization"].fillna(0.0).to_numpy(dtype=float)
    dti_f = df["dti"].to_numpy(dtype=float)
    rm = df["is_mortgage"].to_numpy()

    # 지역 — 소득이 높을수록 수도권 비중이 커진다.
    df["region"] = _pick("지역", np.column_stack([
        np.clip(0.40 + 0.20 * zi, 0.05, 0.90),
        np.full(len(df), 0.30),
        np.clip(0.30 - 0.15 * zi, 0.05, 0.90)]), REGIONS)

    # 자금용도 — 주담대는 LTV가, 기타가계는 한도소진율·DTI가 용도를 가른다.
    df["purpose"] = _pick("자금용도", np.column_stack([
        np.where(rm, np.clip(0.70 + 0.60 * (ltv_f - 0.65), 0.30, 0.95), 0.05),
        np.where(rm, 0.10,
                 np.clip(0.35 + 0.60 * util_f + 0.30 * (dti_f - 0.35), 0.10, 0.90)),
        np.where(rm, 0.20, 0.35)]), PURPOSES)

    # 상환방식 — LTV가 높으면 거치식, 한도소진율이 높으면 일시상환으로 기운다.
    df["repay_type"] = _pick("상환방식", np.column_stack([
        np.where(rm, np.clip(0.75 - 0.70 * (ltv_f - 0.65), 0.20, 0.95),
                 np.clip(0.30 - 0.20 * util_f, 0.05, 0.90)),
        np.where(rm, 0.10, np.clip(0.50 + 0.30 * util_f, 0.10, 0.95)),
        np.where(rm, np.clip(0.15 + 0.90 * (ltv_f - 0.65), 0.05, 0.80), 0.15)]),
        REPAY_TYPES)

    df["is_new"] = _new_flag(df, zi)
    df["new_amount"] = np.where(df["is_new"], df["balance"], 0.0)
    return df


def corporate_book(ctx) -> pd.DataFrame:
    """기업여신 프레임 — 거액 신규여신·상업용부동산·대체투자 서식의 공용 모집단."""
    p = ctx.portfolio[["exposure_id", "obligor_id", "asset_class", "sector",
                       "country", "ead", "maturity", "log_assets", "dpd"]]
    aq = ctx.tables["rdm_asset_quality"][[
        "exposure_id", "classification", "balance", "min_provision",
        "ifrs9_provision"]]
    coll = ctx.tables["rdm_collateral"][["exposure_id", "market_value", "haircut"]]
    df = (p[p["asset_class"] == "corporate"]
          .merge(aq, on="exposure_id")
          .merge(coll, on="exposure_id", how="left")
          .sort_values("exposure_id").reset_index(drop=True))
    df["npl"] = df["classification"].isin(NPL_CLASSES)
    df["recognized"] = (df["market_value"].fillna(0.0)
                        * (1.0 - df["haircut"].fillna(0.0)))
    df["is_new"] = _new_flag(df, _z(df["log_assets"]))
    df["new_amount"] = np.where(df["is_new"], df["balance"], 0.0)
    return df


def _new_flag(df: pd.DataFrame, tilt: np.ndarray) -> np.ndarray:
    """월중 신규취급 여부. 연체 중인 여신은 당월 신규취급일 수 없다."""
    base = df["asset_class"].map(NEW_RATE).to_numpy(dtype=float)
    pr = np.clip(base * np.exp(0.25 * tilt), 0.0, 0.5)
    return (rng("신규취급").random(len(df)) < pr) & (df["dpd"].to_numpy() == 0)


# ---------------------------------------------------------------- 담보 원장

def collateral_book(ctx) -> pd.DataFrame:
    """전 익스포저 담보구분 — 담보 원장과 보증 원장에서 만든다 (파생 아님).

    담보 원장이 없는 익스포저만 보증 원장을 보고, 그것도 없으면 신용으로 떨어진다.
    익스포저당 담보·보증이 각각 최대 1건이므로 구분은 중복되지 않는다.
    """
    exp = ctx.tables["rdm_exposure"][["exposure_id", "obligor_id", "asset_class",
                                      "balance"]]
    coll = (ctx.tables["rdm_collateral"]
            .groupby("exposure_id", as_index=False)
            .agg(collateral_type=("collateral_type", "first"),
                 market_value=("market_value", "sum"),
                 haircut=("haircut", "first")))
    g = ctx.tables["rdm_guarantee"].copy()
    g["elig_amount"] = np.where(g["eligible"], g["guaranteed_amount"], 0.0)
    gte = g.groupby("exposure_id", as_index=False).agg(
        guaranteed=("guaranteed_amount", "sum"), elig=("elig_amount", "sum"))
    df = (exp.merge(coll, on="exposure_id", how="left")
             .merge(gte, on="exposure_id", how="left")
             .sort_values("exposure_id").reset_index(drop=True))
    df["guaranteed"] = df["guaranteed"].fillna(0.0)
    df["elig"] = df["elig"].fillna(0.0)
    has_coll = df["collateral_type"].notna()
    df["bucket"] = np.where(
        has_coll, df["collateral_type"].map(_COLL_BUCKET),
        np.where(df["guaranteed"] > 0.0, "보증서담보", "신용(무담보)"))
    # 담보평가액·인정액. 보증은 감독 haircut 대신 적격 여부로 인정액이 갈린다.
    df["appraised"] = np.where(has_coll, df["market_value"].fillna(0.0),
                               df["guaranteed"])
    df["recognized"] = np.where(
        has_coll, df["market_value"].fillna(0.0) * (1.0 - df["haircut"].fillna(0.0)),
        df["elig"])
    return df


# ---------------------------------------------------------------- 연체·상각 추이

def writeoff_rate() -> float:
    """당월 상각률 — 상각 원장이 없어 고정이하여신 대비 비율만 파생한다."""
    return float(rng("상각률").uniform(0.008, 0.020))


def arrears_history(asof: str, current_new: float, current_wo: float,
                    months: int = 12) -> list[tuple[str, float, float]]:
    """(월, 신규연체액, 상각액) 추이. **당월(마지막 원소)은 산출값 그대로다.**

    과거 배수만 파생하므로 추이 라인은 당월 실적에 앵커된다 — 서식의 시계열이
    당월 산출과 어긋나면 그건 산출 오류지 파생 난수 탓이 아니다.
    """
    end = pd.Period(asof, freq="M")
    fn = rng("신규연체추이").uniform(0.70, 1.35, months)
    fw = rng("상각추이").uniform(0.65, 1.40, months)
    fn[-1] = fw[-1] = 1.0
    return [(str(end - (months - 1 - i)), current_new * float(fn[i]),
             current_wo * float(fw[i])) for i in range(months)]
