"""원화유동성비율 · 외화유동성비율 · 원화예대율 (은행업감독규정 제26조·제30조).

LCR/NSFR만으로는 감독규정의 유동성 항목이 채워지지 않는다. 이 세 지표는
바젤이 아니라 **국내 감독규정 고유**이며 산식·분모가 서로 다르다.

  원화유동성비율 = 잔존만기 1개월 이내 원화유동성자산 ÷ 원화유동성부채 ≥ 100%
  외화유동성비율 = 잔존만기 3개월 이내 외화자산 ÷ 외화부채 ≥ 85%
  원화예대율     = 원화대출금 ÷ 원화예수금 ≤ 100%

세 산식이 전부 **잔존만기** 기준이므로 사다리도 잔존만기 축을 쓴다
(`alm.liquidity.build_contractual_balance_ladder` — 계약원장의 maturity_date에서
접는다). 재설정 갭 사다리(`alm.balance_sheet.repricing`)를 쓰던 자리를 옮긴
것이다: 그 사다리는 시간축이 리프라이싱이고 비만기예금이 행태 코어로 4~5년까지
퍼져 있어, 10년 변동금리 대출이 1개월 이내 유동성자산으로 계상되는 한편 요구불
예금은 1개월 유출에서 빠졌다. 축이 다른 사다리를 분모에 넣으면 비율이 규정
문언과 다른 것을 측정한다(BCBS d238 ¶177~187도 계약만기 불일치는 행태가정
배제가 정의라고 적는다).

별도 가정으로 만들지 않는다 — 사다리는 ALM 계약원장 한 곳에서 나오므로 IRRBB
화면과 유동성 화면이 같은 원장을 서로 다른 축으로 볼 뿐 갈라지지 않는다.
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

# 1개월 이내 / 3개월 이내 — **경계를 연 단위로 둔다.**
#
# 여기 버킷 라벨("0-1m", "1-3m")을 문자열로 적어 두고 있었다. 만기 사다리가
# [별표 9-1] <표2>의 19구간으로 바뀌면서 그 라벨이 사라졌고, 조회가 빈 결과를
# 내 분모가 0이 됐다. 그러면 두 비율이 0%가 되고 "충족여부 0"으로 서식
# BR-23에 그대로 나간다 — 값 오류가 아니라 조용한 0이라 더 나쁘다.
# 라벨은 사다리가 바뀔 때마다 바뀌지만 1개월·3개월 경계는 바뀌지 않는다.
_KRW_HORIZON_YEARS = 1 / 12
_FX_HORIZON_YEARS = 0.25

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


def _horizon_labels(horizon_years: float) -> set[str]:
    """만기구간 원장에서 상한이 시계 이내인 구간 라벨을 고른다.

    경계 규약은 (하한, 상한]이므로 상한이 시계 이하인 구간까지가 '시계 이내'다.
    """
    from risk_lib.alm.params import build_time_buckets
    bk = build_time_buckets()
    return set(bk.loc[bk["upper_years"] <= horizon_years + 1e-12, "label"])


def _bucket_sum(rep: pd.DataFrame, buckets, col: str) -> float:
    hit = rep[rep["bucket"].isin(set(buckets))]
    return float(hit[col].sum())


def compute_liquidity_ratios(result) -> LiquidityRatios:
    """세 지표를 대차대조표 + **잔존만기 축** 잔액 사다리에서 산출한다."""
    from risk_lib.alm.liquidity import build_contractual_balance_ladder

    asof = result.meta.get("asof", "1970-01-01")
    bs = result.alm["balance_sheet"]
    tables = result.alm.get("tables") or {}
    for name in ("alm_contract", "alm_time_bucket"):
        if name not in tables:
            raise KeyError(
                f"{name}이 없다 — 잔존만기 사다리를 만들 수 없다. 재설정 갭 "
                "사다리로 대체하면 제26조·제63조가 요구하는 축이 아닌 것을 "
                "측정하게 되므로 조용히 대체하지 않는다")
    # 잔액 기준 사다리를 쓴다. `irrbb.repricing`은 현금흐름(원금+이자)을 접은
    # PV 뷰이며, 유동성비율 분자·분모는 잔액이다.
    rep = build_contractual_balance_ladder(
        tables["alm_contract"], tables["alm_time_bucket"], asof=asof)

    # ---- 원화유동성비율: 1개월 이내 자산 + HQLA(즉시 현금화 가능)
    # HQLA는 잔존만기가 길어도 분자에 넣는다. 유동성자산의 요건이 만기도래가
    # 아니라 즉시 현금화 가능성이기 때문이다. 이 규약을 원화에만 적용하면
    # 외화 분자가 구조적으로 0이 된다 — 합성 계약원장에 잔존만기 3개월 이내
    # 자산이 한 건도 없기 때문이며, 그 0이 서식 BR-23으로 그대로 나갔다.
    hqla = float(sum(bs.hqla.values()))
    krw_assets = (_bucket_sum(rep, _horizon_labels(_KRW_HORIZON_YEARS), "assets") + hqla) * (1 - FX_SHARE_ASSETS)
    krw_liabs = _bucket_sum(rep, _horizon_labels(_KRW_HORIZON_YEARS), "liabilities") * (1 - FX_SHARE_LIABILITIES)
    krw_ratio = krw_assets / krw_liabs if krw_liabs > 0 else 0.0

    # ---- 외화유동성비율: 3개월 이내
    fx_assets = (_bucket_sum(rep, _horizon_labels(_FX_HORIZON_YEARS), "assets") + hqla) * FX_SHARE_ASSETS
    fx_liabs = _bucket_sum(rep, _horizon_labels(_FX_HORIZON_YEARS), "liabilities") * FX_SHARE_LIABILITIES
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
         "citation": "은행업감독규정 제26조 제1항 — 잔존만기 1개월 이내. "
                     "잔존만기 축 사다리(alm_contract.maturity_date)에서 접는다. "
                     "유동성부채의 정의는 시행세칙 원문 미열람이며 여기서는 "
                     "계약상 최조기 지급가능일(요구불예금 전액 1개월 이내)로 "
                     "둔다 — 실제 세칙이 좁게 정의하면 분모가 줄어든다"},
        {"metric": "외화유동성비율", "numerator": fx_assets,
         "denominator": fx_liabs, "value": fx_ratio,
         "threshold": FX_LIQUIDITY_MIN, "direction": "min",
         "passes": fx_ratio >= FX_LIQUIDITY_MIN,
         "citation": "은행업감독규정 제63조 — 잔존만기 3개월 이내. 분자에 HQLA "
                     "스톡을 더한다(즉시 현금화 가능). 통화 구분이 원장에 "
                     "없으므로 자산·부채에 같은 외화비중을 적용한다 — 이 비율이 "
                     "드러내는 것은 만기 불일치뿐이다"},
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
