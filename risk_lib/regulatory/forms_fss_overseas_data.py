"""해외점포 서식의 파생 데이터 — 점포 마스터와 점포 귀속.

**해외점포 원장이 없다.** 이 저장소의 포트폴리오는 익스포저의 소재국(`country`)만
알 뿐 어느 해외점포가 취급했는지, 그 점포가 지점인지 현지법인인지, 언제 세워졌는지
모른다. FINES 해외점포 서식(BF1xx~BF4xx)은 그것을 요구한다. 상수를 박으면 서식이
산출과 무관해지고, 실행마다 난수를 새로 뽑으면 제출본 지문
(`forms.submission_digest`)이 흔들려 같은 제출본인지 판별할 수 없다. 그래서
**기준일 고정 시드에서 유도한 결정론적 RNG**로 만든다 — 같은 시드면 같은 값이다.

원장·산출에서 그대로 오는 것 (파생 아님)
  국가별 익스포저     `portfolio.country` 실측 집계. **점포 배분만 파생이고
                     국가 합계는 실측이다** — BF304가 이것을 FormCheck로 건다.
  건전성분류·연체     `rdm_asset_quality` · `rdm_delinquency` 산출값.
  충당금·ECL          `rdm_asset_quality` · `ecl_result` 산출값.
  담보·보증           `rdm_collateral` · `rdm_guarantee` 원장.
  만기구조            `alm_repricing_gap` 산출값(해외분은 비중 배분).
  대차대조표          `pru_balance_sheet` 산출값(해외분은 비중 배분).

시드 고정으로 파생하는 것 (원장 부재)
  점포 마스터        소재국별 점포 수·점포명(도시명)·형태(지점/현지법인/사무소)·
                     설립연도. 국가마다 최소 1개는 영업점포(지점)가 되도록 강제한다
                     — 영업점포가 없으면 그 나라 익스포저를 귀속시킬 곳이 없다.
  부속점포 수        자지점·출장소·사무소 설치 수(BF103). 사무소 형태 점포는 0.
  익스포저 점포 배분  **같은 나라 안에서만** 배분한다. 국가별 합계는 실측 그대로다.

가정 (파생도 원장도 아닌 것)
  적용 환율          `USD_KRW`. BF406의 100만달러 기준 환산에 쓴다. 원장에 통화·
                     환율이 없어 단일 환율을 가정한다 — 이 값을 바꾸면 BF406의
                     기준 이상/미만 구분이 바뀐다.

파생값이 들어간 서식 라인은 그 라인의 formula에 "파생"임을 남긴다.
"""

from __future__ import annotations

import hashlib
import math

import numpy as np
import pandas as pd

from risk_lib.regulatory.forms_fss_retail_data import collateral_book

_SEED_BASE = 20260630          # 파생 기준일 — 이 값을 바꾸면 파생값 전체가 바뀐다

HOME_COUNTRY = "KR"            # 본점 소재국. 그 외가 해외점포 귀속이다.
BRANCH_KINDS = ("지점", "현지법인", "사무소")
# 사무소는 여신·수신을 취급할 수 없다 — 익스포저 배분 대상에서 뺀다.
OPERATING_KINDS = ("지점", "현지법인")

AQ_ORDER = ("정상", "요주의", "고정", "회수의문", "추정손실")
NPL_CLASSES = ("고정", "회수의문", "추정손실")

# **적용 환율은 가정이다.** 원장에 익스포저 통화가 없어 해외분 전체를 단일 환율로
# 환산한다. BF406의 거액 기준(100만달러)이 이 값에 직접 걸린다.
USD_KRW = 1_350.0
LARGE_NPL_USD = 1_000_000.0    # BF406 기재 기준 — 서식명이 정한 금액이다

# 연체구간은 은행업감독규정 제27조의 연체기간 구분(1개월·3개월)을 따른다.
DPD_BANDS = ((30, "1~30일"), (60, "31~60일"), (90, "61~90일"),
             (math.inf, "91일 이상"))
MATURITY_BANDS = ((1.0, "1년 이하"), (3.0, "1~3년"), (5.0, "3~5년"),
                  (math.inf, "5년 초과"))
# 유가증권 원장이 없다. 은행·국가 익스포저를 채권 보유로 보는 프록시 매핑이다.
SECURITY_TYPES = {"sovereign": "국공채", "bank": "금융채"}
RATING_ORDER = ("AAA-AA", "A", "BBB", "BB", "UNRATED")
INVESTMENT_GRADE = ("AAA-AA", "A", "BBB")

# 점포명은 소재 도시명에서 만든다. 여기 없는 나라는 `_fallback_cities`가 국가코드
# 기반 이름을 만든다 — 도시명이 1개뿐이면 점포 수 추첨(2~4개)이 성립하지 않는다.
_CITIES = {
    "CN": ("상해", "북경", "심천", "청도", "대련"),
    "JP": ("도쿄", "오사카", "후쿠오카"),
    "US": ("뉴욕", "로스앤젤레스", "시카고"),
    "VN": ("하노이", "호치민", "하이퐁", "다낭"),
}


def _fallback_cities(country: str) -> tuple[str, ...]:
    """`_CITIES` 미등록 국가의 점포명 후보 — 도시명 대신 국가코드 일련번호를 쓴다.

    후보가 1개면 `integers(2, 2)`가 ValueError로 죽어 서식 19건이 통째로 빌드
    실패한다. 등록국(CN·JP·US·VN)은 이 경로를 타지 않으므로 기존 파생값은 불변이다.
    """
    return tuple(f"{country}{i}" for i in range(1, 5))


def rng(key: str) -> np.random.Generator:
    """기준일+키에서 유도한 난수원 — 키가 같으면 언제 어디서 불러도 같은 수열이다."""
    h = hashlib.sha256(f"{_SEED_BASE}:{key}".encode()).hexdigest()[:8]
    return np.random.default_rng(int(h, 16))


def band_of(value: float, bands: tuple[tuple[float, str], ...]) -> str:
    """구간 라벨. 경계값은 아래 구간에 포함한다 (30일 → '1~30일')."""
    for upper, label in bands:
        if value <= upper:
            return label
    return bands[-1][1]


def _assign(key: str, n: int, weights: np.ndarray) -> np.ndarray:
    """가중치대로 n개 행에 인덱스를 배정한다 — 행 순서가 고정돼야 재현된다."""
    w = np.asarray(weights, dtype=float)
    w = w / w.sum()
    u = rng(key).random(n)
    return (w.cumsum()[None, :] < u[:, None]).sum(axis=1).clip(0, len(w) - 1)


def _tol(total: float) -> float:
    return max(1.0, abs(float(total)) * 1e-9)


# ---------------------------------------------------------------- 점포 마스터

def overseas_countries(ctx) -> tuple[str, ...]:
    """해외점포 소재국 — 포트폴리오 실측 국가에서 본점 소재국을 뺀 것."""
    return tuple(sorted(set(ctx.portfolio["country"].unique()) - {HOME_COUNTRY}))


def branch_master(ctx) -> pd.DataFrame:
    """해외점포 마스터 — **원장이 아니라 기준일 고정 시드 파생값이다.**

    나라마다 첫 점포는 반드시 지점으로 둔다. 그 나라 익스포저를 귀속시킬 영업점포가
    하나도 없으면 국가별 실측 합계를 점포별로 대사할 수 없기 때문이다.
    """
    rows = []
    for country in overseas_countries(ctx):
        cities = _CITIES.get(country) or _fallback_cities(country)
        g = rng(f"점포:{country}")
        n = int(g.integers(2, min(4, len(cities)) + 1))
        picked = list(g.choice(np.array(cities), size=n, replace=False))
        # 첫 점포는 지점 고정, 나머지는 형태를 뽑는다.
        kinds = ["지점"] + [BRANCH_KINDS[int(i)] for i in
                           _assign(f"점포형태:{country}", n - 1,
                                   np.array([0.45, 0.30, 0.25]))]
        years = g.integers(1992, 2019, size=n)
        scales = g.uniform(0.5, 1.5, size=n)
        subs = rng(f"부속점포:{country}").integers(0, 3, size=(n, 3))
        for i, (city, kind) in enumerate(zip(picked, kinds)):
            suffix = {"지점": "지점", "현지법인": "현지법인", "사무소": "사무소"}[kind]
            operating = kind in OPERATING_KINDS
            rows.append({
                "branch_code": f"{country}-{i + 1:02d}",
                "branch_name": f"{city}{suffix}",
                "country": country,
                "kind": kind,
                "established_year": int(years[i]),
                # 사무소는 영업을 하지 않으므로 부속점포도 두지 않는다.
                "sub_branch": int(subs[i, 0]) if operating else 0,
                "sub_office": int(subs[i, 1]) if operating else 0,
                "rep_office": int(subs[i, 2]) if operating else 0,
                "scale": float(scales[i]) if operating else 0.0,
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- 해외 여신 원장

def overseas_book(ctx) -> pd.DataFrame:
    """해외 익스포저 통합 프레임 — 산출값 + 파생 점포 귀속열.

    금액·건전성분류·연체·충당금은 전부 산출값이다. 파생은 `branch_code`·
    `branch_name`·`branch_kind` 세 열뿐이며, 배분이 **국가 안에서만** 일어나므로
    국가별 집계는 실측 그대로 남는다.
    """
    p = ctx.portfolio[["exposure_id", "obligor_id", "asset_class", "sector",
                       "country", "ead", "maturity", "pd", "lgd", "gdp_growth"]]
    aq = ctx.tables["rdm_asset_quality"][[
        "exposure_id", "classification", "borrower_type", "dpd", "balance",
        "min_provision_rate", "min_provision", "ifrs9_provision",
        "reserve_shortfall"]]
    ex = ctx.tables["rdm_exposure"][["exposure_id", "drawn", "undrawn",
                                    "ccf_type", "rating"]]
    ecl = ctx.tables["ecl_result"][["exposure_id", "stage", "ecl"]]
    # 점포 배분이 행 순서에 의존한다 — 정렬을 고정해야 재현된다.
    df = (p[p["country"] != HOME_COUNTRY]
          .merge(aq, on="exposure_id")
          .merge(ex, on="exposure_id")
          .merge(ecl, on="exposure_id", how="left")
          .sort_values("exposure_id").reset_index(drop=True))
    df["ecl"] = df["ecl"].fillna(0.0)
    df["npl"] = df["classification"].isin(NPL_CLASSES)
    # 연체가 없는 익스포저(dpd=0)는 구간 라벨을 붙이지 않는다. band_of는 경계값을
    # 아래 구간에 넣으므로 0을 그대로 넣으면 정상여신이 "1~30일"로 집계된다.
    df["dpd_band"] = [band_of(v, DPD_BANDS) if v > 0 else "연체 없음"
                      for v in df["dpd"]]
    df["maturity_band"] = [band_of(v, MATURITY_BANDS) for v in df["maturity"]]

    bm = branch_master(ctx)
    op = bm[bm["kind"].isin(OPERATING_KINDS)]
    code = pd.Series(index=df.index, dtype=object)
    for country, sub in df.groupby("country", sort=True):
        b = op[op["country"] == country]
        idx = _assign(f"점포배분:{country}", len(sub), b["scale"].to_numpy())
        code.loc[sub.index] = b["branch_code"].to_numpy()[idx]
    df["branch_code"] = code
    meta = bm.set_index("branch_code")
    df["branch_name"] = df["branch_code"].map(meta["branch_name"])
    df["branch_kind"] = df["branch_code"].map(meta["kind"])
    return df


def country_exposure(ctx) -> pd.DataFrame:
    """국가별 익스포저 — **전 국가 실측 집계다(본점 소재국 포함).**

    BF304가 이 값과 포트폴리오 집계의 일치를 FormCheck로 건다. 파생이 끼면 안 된다.
    """
    aq = ctx.tables["rdm_asset_quality"][["exposure_id", "classification",
                                          "balance", "ifrs9_provision"]]
    df = ctx.portfolio[["exposure_id", "country", "ead"]].merge(aq,
                                                               on="exposure_id")
    df["npl_balance"] = np.where(df["classification"].isin(NPL_CLASSES),
                                 df["balance"], 0.0)
    return (df.groupby("country", as_index=False)
            .agg(ead=("ead", "sum"), balance=("balance", "sum"),
                 n=("exposure_id", "count"), npl=("npl_balance", "sum"),
                 provision=("ifrs9_provision", "sum"))
            .sort_values("country").reset_index(drop=True))


def overseas_share(ctx) -> float:
    """해외분 배분비율 — 실측 익스포저 비중이다.

    BF201·BF202·BF301은 계정별 해외 원장이 없어 이 비율로 배분한다. 비율 자체는
    실측이지만 **계정별 배분 결과는 파생값이다.**
    """
    total = float(ctx.portfolio["ead"].sum())
    ov = float(ctx.portfolio.loc[ctx.portfolio["country"] != HOME_COUNTRY,
                                 "ead"].sum())
    return ov / total if total else 0.0


# ---------------------------------------------------------------- 파생 원장 보조

def overseas_collateral(ctx) -> pd.DataFrame:
    """해외 익스포저의 담보구분 — 담보·보증 원장에서 온다 (파생 아님)."""
    cb = collateral_book(ctx)
    ctry = ctx.portfolio[["exposure_id", "country"]]
    df = cb.merge(ctry, on="exposure_id")
    return df[df["country"] != HOME_COUNTRY].reset_index(drop=True)


def overseas_securities(ctx) -> pd.DataFrame:
    """해외점포 유가증권 — **유가증권 원장이 없어 은행·국가 익스포저를 프록시로 쓴다.**

    금액·등급·잔존만기는 실측이고, '유가증권으로 본다'는 판단만 프록시다.
    """
    ob = overseas_book(ctx)
    df = ob[ob["asset_class"].isin(SECURITY_TYPES)].copy()
    df["security_type"] = df["asset_class"].map(SECURITY_TYPES)
    return df.reset_index(drop=True)


def overseas_derivatives(ctx) -> pd.DataFrame:
    """해외 거래상대방 파생거래 — `mkt_trade`를 거래상대방 소재국으로 거른다."""
    ob = ctx.tables["rdm_obligor"][["obligor_id", "country"]]
    df = ctx.tables["mkt_trade"].merge(ob, left_on="counterparty",
                                       right_on="obligor_id", how="left")
    return df[df["country"].fillna(HOME_COUNTRY) != HOME_COUNTRY].reset_index(
        drop=True)


def overseas_guarantee(ctx) -> pd.DataFrame:
    """해외 익스포저에 붙은 보증·신용파생 — 보증 원장 그대로다."""
    ctry = ctx.portfolio[["exposure_id", "country"]]
    df = ctx.tables["rdm_guarantee"].merge(ctry, on="exposure_id", how="left")
    return df[df["country"].fillna(HOME_COUNTRY) != HOME_COUNTRY].reset_index(
        drop=True)
