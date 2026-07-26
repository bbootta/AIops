"""원화유동성비율 · 외화유동성비율 · 원화예대율 (은행업감독규정 제26조·제30조).

LCR/NSFR만으로는 감독규정의 유동성 항목이 채워지지 않는다. 이 세 지표는
바젤이 아니라 **국내 감독규정 고유**이며 산식·분모가 서로 다르다.

  원화유동성비율 = 잔존만기 1개월 이내 원화유동성자산 ÷ 원화유동성부채 ≥ 100%
  외화유동성비율 = 잔존만기 3개월 이내 외화자산 ÷ 외화부채 ≥ 85%
  원화예대율     = 원화대출금 ÷ 원화예수금 ≤ 100%

만기 구간은 ALM 재설정 갭 사다리(alm.irrbb.repricing)에서 가져온다 — 별도
가정으로 만들면 IRRBB 화면과 유동성 화면이 서로 다른 만기 분포를 쓰게 된다.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

KRW_LIQUIDITY_MIN = 1.00      # 은행업감독규정 제26조 제1항 — 100% 이상
FX_LIQUIDITY_MIN = 0.85       # 외화유동성비율 85% 이상
LOAN_DEPOSIT_MAX = 1.00       # 원화예대율 100% 이하

# 외화 비중 — 합성 대차대조표에 통화 구분이 **없다**. 자산·부채에 서로 다른
# 비중을 가정하면 실제로는 존재하지 않는 통화 불일치가 비율에 섞여 들어가
# "가정이 만든 위반"을 보고하게 된다. 같은 비중을 쓰고, 이 비율이 드러내는
# 것은 오직 만기 불일치임을 명시한다. 실제 제출 시 통화별 원장으로 대체된다.
FX_SHARE = 0.13
FX_SHARE_ASSETS = FX_SHARE
FX_SHARE_LIABILITIES = FX_SHARE

# 1개월 이내 / 3개월 이내 버킷 (alm 재설정 사다리 라벨)
_KRW_BUCKETS = ("0-1m",)
_FX_BUCKETS = ("0-1m", "1-3m")

# 예수금으로 보는 조달 항목 — 차입금·사채는 예대율 분모에서 제외한다.
_DEPOSIT_KEYS = ("retail_stable", "retail_less_stable",
                 "corporate_operational", "corporate_non_operational")


@dataclass(frozen=True)
class LiquidityRatios:
    asof: str
    krw_liquid_assets: float
    krw_liquid_liabilities: float
    krw_ratio: float
    fx_assets: float
    fx_liabilities: float
    fx_ratio: float
    loans_krw: float
    deposits_krw: float
    loan_deposit_ratio: float
    detail: pd.DataFrame          # metric, numerator, denominator, value, minimum/maximum, passes

    def passes(self) -> bool:
        return (self.krw_ratio >= KRW_LIQUIDITY_MIN
                and self.fx_ratio >= FX_LIQUIDITY_MIN
                and self.loan_deposit_ratio <= LOAN_DEPOSIT_MAX)


def _bucket_sum(rep: pd.DataFrame, buckets: tuple[str, ...], col: str) -> float:
    hit = rep[rep["bucket"].isin(buckets)]
    return float(hit[col].sum())


def compute_liquidity_ratios(result) -> LiquidityRatios:
    """세 지표를 대차대조표·재설정 사다리에서 산출한다."""
    asof = result.meta.get("asof", "1970-01-01")
    bs = result.alm["balance_sheet"]
    rep = result.alm["irrbb"].repricing

    # ---- 원화유동성비율: 1개월 이내 자산 + HQLA(즉시 현금화 가능)
    hqla = float(sum(bs.hqla.values()))
    krw_assets = (_bucket_sum(rep, _KRW_BUCKETS, "assets") + hqla) * (1 - FX_SHARE_ASSETS)
    krw_liabs = _bucket_sum(rep, _KRW_BUCKETS, "liabilities") * (1 - FX_SHARE_LIABILITIES)
    krw_ratio = krw_assets / krw_liabs if krw_liabs > 0 else 0.0

    # ---- 외화유동성비율: 3개월 이내
    fx_assets = _bucket_sum(rep, _FX_BUCKETS, "assets") * FX_SHARE_ASSETS
    fx_liabs = _bucket_sum(rep, _FX_BUCKETS, "liabilities") * FX_SHARE_LIABILITIES
    fx_ratio = fx_assets / fx_liabs if fx_liabs > 0 else 0.0

    # ---- 원화예대율
    loans = float(bs.loans) * (1 - FX_SHARE_ASSETS)
    deposits = sum(float(bs.funding.get(k, 0.0)) for k in _DEPOSIT_KEYS) \
        * (1 - FX_SHARE_LIABILITIES)
    ldr = loans / deposits if deposits > 0 else 0.0

    detail = pd.DataFrame([
        {"metric": "원화유동성비율", "numerator": krw_assets,
         "denominator": krw_liabs, "value": krw_ratio,
         "threshold": KRW_LIQUIDITY_MIN, "direction": "min",
         "passes": krw_ratio >= KRW_LIQUIDITY_MIN,
         "citation": "은행업감독규정 제26조 제1항 — 잔존만기 1개월 이내"},
        {"metric": "외화유동성비율", "numerator": fx_assets,
         "denominator": fx_liabs, "value": fx_ratio,
         "threshold": FX_LIQUIDITY_MIN, "direction": "min",
         "passes": fx_ratio >= FX_LIQUIDITY_MIN,
         "citation": "은행업감독규정 제63조 — 잔존만기 3개월 이내"},
        {"metric": "원화예대율", "numerator": loans,
         "denominator": deposits, "value": ldr,
         "threshold": LOAN_DEPOSIT_MAX, "direction": "max",
         "passes": ldr <= LOAN_DEPOSIT_MAX,
         "citation": "은행업감독규정 제26조 제1항 — 원화대출금 ÷ 원화예수금"},
    ])
    return LiquidityRatios(
        asof=asof,
        krw_liquid_assets=krw_assets, krw_liquid_liabilities=krw_liabs,
        krw_ratio=krw_ratio,
        fx_assets=fx_assets, fx_liabilities=fx_liabs, fx_ratio=fx_ratio,
        loans_krw=loans, deposits_krw=deposits, loan_deposit_ratio=ldr,
        detail=detail,
    )
