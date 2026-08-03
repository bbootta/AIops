"""집합투자증권(CIU) 원장 — 펀드 마스터 · 편입자산 · 운용지침 (Basel III CRE60).

무엇인가
--------
은행이 보유한 집합투자기구(펀드) 지분투자를 세 개의 정규 원장으로 나눈 것이다.

  rdm_fund_master   펀드 1건당 1행 — 투자금액·지분율·레버리지·산정방법
  rdm_fund_holding  펀드 × 편입자산 1건당 1행 — LTA(look-through) 산출의 기초
  rdm_fund_mandate  펀드 × 운용지침 한도 1건당 1행 — MBA(mandate) 산출의 기초

왜 세 개인가
------------
CRE60은 **하나의 펀드에 세 가지 산정방법**을 규정한다. 방법마다 필요한 데이터의
입도가 다르다 — LTA는 편입자산 단위, MBA는 운용지침 한도 단위, fallback은 펀드
단위다. 이를 한 평면 테이블에 담으면 (가) 편입자산 없는 펀드가 NULL 덩어리로
남고 (나) 방법 간 비교(왜 MBA를 썼는가)가 불가능해진다. 방법이 바뀌면 자본이
수십 배 움직이므로(0% ~ 1250%), 채택 사유가 데이터로 남아야 감사에서 설명된다.

무엇을 가능하게 하는가
----------------------
  lta_rwa()          CRE60.5 — 편입자산을 직접 보유한 것처럼 위험가중
  mba_rwa()          CRE60.7 — 운용지침 한도까지 투자했다고 가정 (보수적 충전)
  fallback_rwa()     CRE60.9 — 1250%
  fund_rwa_summary() 세 방법을 나란히 두고 master의 산정방법대로 채택 + 사유

산정 식 (CRE60.10)
------------------
  RWA = min(평균위험가중치 × 레버리지, 1250%) × 투자 시가

  평균위험가중치 = Σ(편입자산 시가 × 위험가중치) / Σ(편입자산 시가)
  레버리지       = 펀드 총자산 / 펀드 순자산(NAV)

  편입자산 시가 합계 = 펀드 총자산이고 투자 시가 = 지분율 × NAV 이므로,
  위 식은 "편입자산 위험가중 합 × 은행 지분율"과 항등이다(상한 미도달 시).
  상한 1250%는 레버리지가 큰 펀드에서 자본이 익스포저를 초과하지 않게 막는다.

범위 밖(명시)
-------------
펀드 내 파생상품의 **거래상대방 신용리스크(CCR)**는 CRE60.6에 따라 별도로
가산해야 하나 본 모듈의 RWA 산출에는 포함하지 않는다. 대신 편입자산 원장이
SA-CCR 입력 형태를 그대로 담고 있어 `saccr_trade_view()` → `risk_lib.ccr.saccr_ead()`
로 곧바로 산출할 수 있다. 조용히 빠뜨린 것이 아니라 경계를 그은 것이다.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from risk_lib.capital.rwa_sa import SA_RISK_WEIGHTS
from risk_lib.ccr import SF
from risk_lib.references import BIS_MIN_TOTAL

# ---------------------------------------------------------------- 도메인 상수

FUND_TYPES = ("주식형", "채권형", "혼합형", "부동산", "MMF", "재간접")

# CRE60의 세 가지 산정방법. 우선순위는 look_through > mandate > fallback이며,
# 은행이 선택하는 것이 아니라 **정보 가용성이 결정**한다 (CRE60.2).
APPROACHES = ("look_through", "mandate", "fallback")

HOLDING_ASSET_CLASSES = ("sovereign", "bank", "corporate", "equity",
                         "securitisation", "real_estate", "fund", "cash")

# 등급 버킷은 SA_RISK_WEIGHTS(rwa_sa)의 키와 같아야 한다 — 다르면 조용히
# UNRATED로 떨어져 위험가중치가 과소·과대 산정된다.
RATINGS = ("AAA-AA", "A", "BBB", "BB", "B", "CCC-", "UNRATED")

# 편입자산 정보의 제공 빈도. CRE60.5(1)은 "은행의 보고 주기 이상"을 요구한다 —
# 은행 자본보고가 분기이므로 분기 이상이면 요건 충족으로 본다.
INFO_FREQUENCIES = ("daily", "monthly", "quarterly", "annual", "none")
_LTA_SUFFICIENT_FREQUENCIES = frozenset({"daily", "monthly", "quarterly"})

# 파생 편입자산의 SA-CCR 자산군. risk_lib.ccr.SF의 키를 그대로 쓴다 —
# 여기서 별도 문자열을 정의하면 saccr_ead가 KeyError로 죽는다.
CCR_ASSET_CLASSES = tuple(SF) + ("none",)

# CRE60.9 fallback 위험가중치 1250%. 자기자본 8% 기준에서 익스포저 전액을
# 자본으로 덮는 수준(= 12.5 × 8% = 100%)이며, 정보가 없다는 사실 자체에 대한
# 벌칙이다.
FALLBACK_RW = 12.5

# CRE60.10 — 레버리지 조정 후 위험가중치 상한. 상한이 없으면 레버리지가 큰
# 펀드에서 소요자본이 투자원금을 넘어선다.
RW_CAP = 12.5

# SA_RISK_WEIGHTS(sovereign/bank/corporate)에 없는 자산군의 위험가중치.
# 있는 것은 import해서 쓰고, 없는 것만 여기서 정의한다.
_RW_SECURITISATION = {
    # SEC-ERBA 선순위 트란셰, 잔존 1년 기준 (CRE41.13). 미등급은 look-through
    # 불가 시 1250% (CRE40.42) — 등급이 없으면 자본이 폭증하는 것이 정상이다.
    "AAA-AA": 0.15, "A": 0.30, "BBB": 0.60, "BB": 1.20, "B": 2.50,
    "CCC-": 12.5, "UNRATED": 12.5,
}

_RW_FLAT = {
    "equity": 2.50,       # CRE20.57 — 상장 지분투자 250%
    "real_estate": 1.00,  # CRE20.109 — 직접 보유 부동산은 기타자산 100%
    "fund": 2.50,         # CRE60.8 — 2단계 look-through 불가 시 지분투자로 간주
    "cash": 0.00,         # CRE20.16 — 현금·중앙은행 예치금
}

# 위 주석("같아야 한다")을 코드가 실제로 강제한다. rwa_sa가 버킷을 바꾸면
# 여기서 즉시 죽어야지, 조용히 UNRATED로 떨어져 위험가중치가 틀리면 안 된다.
assert all(set(t) == set(RATINGS) for t in SA_RISK_WEIGHTS.values()), \
    "SA_RISK_WEIGHTS의 등급 버킷이 RATINGS와 다르다"
assert set(_RW_SECURITISATION) == set(RATINGS), \
    "_RW_SECURITISATION의 등급 버킷이 RATINGS와 다르다"

_DEALER_POOL = ("DLR-KB", "DLR-SHINHAN", "DLR-NH", "DLR-MIRAE", "DLR-SAMSUNG")

# 편입자산 자산군 → SA-CCR 자산군 (CRE52.11 자산군 구분)
_CCR_CLASS_MAP = {"equity": "equity", "sovereign": "ir", "bank": "ir",
                  "corporate": "credit_ig"}

# 펀드 유형별 편입자산 구성 확률. 합이 1이 아니면 rng.choice가 죽는다.
_HOLDING_MIX: dict[str, tuple[tuple[str, float], ...]] = {
    "주식형": (("equity", 0.85), ("cash", 0.10), ("corporate", 0.05)),
    "채권형": (("sovereign", 0.35), ("corporate", 0.40), ("bank", 0.15),
             ("cash", 0.10)),
    "혼합형": (("equity", 0.40), ("corporate", 0.25), ("sovereign", 0.20),
             ("bank", 0.10), ("cash", 0.05)),
    "부동산": (("real_estate", 0.70), ("securitisation", 0.20), ("cash", 0.10)),
    "MMF": (("sovereign", 0.40), ("bank", 0.45), ("cash", 0.15)),
    "재간접": (("fund", 0.80), ("equity", 0.10), ("cash", 0.10)),
}

_RATING_POOL: dict[str, tuple[str, ...]] = {
    "sovereign": ("AAA-AA", "A", "BBB"),
    "bank": ("AAA-AA", "A", "BBB"),
    "corporate": ("A", "BBB", "BB", "B"),
    "securitisation": ("AAA-AA", "A", "BBB"),
    "equity": ("UNRATED",),
    "real_estate": ("UNRATED",),
    "fund": ("UNRATED",),
    "cash": ("UNRATED",),
}

# 펀드 유형별 실제 레버리지(총자산/NAV) 범위. 부동산 펀드만 차입이 의미 있다.
_LEVERAGE_RANGE: dict[str, tuple[float, float]] = {
    "주식형": (1.00, 1.10), "채권형": (1.00, 1.15), "혼합형": (1.00, 1.20),
    "부동산": (1.30, 1.80), "MMF": (1.00, 1.02), "재간접": (1.00, 1.10),
}

# 합성 펀드 12건. (펀드명, 유형, 운용사, 신탁여부, 정보제공빈도, 제3자검증,
# 운용지침 입수) — 산정방법은 이 정보에서 **파생**한다. 방법을 직접 적어두면
# 정보와 방법이 어긋나도 아무도 모른다.
_FUND_SEEDS: tuple[tuple[str, str, str, bool, str, bool, bool], ...] = (
    ("코리아대표주식 모펀드",   "주식형", "한국투자신탁운용", False, "daily",     True,  True),
    ("국공채플러스 모펀드",     "채권형", "삼성자산운용",     False, "daily",     True,  True),
    ("글로벌밸런스 혼합",       "혼합형", "미래에셋자산운용", False, "monthly",   True,  True),
    ("단기국공채 MMF",          "MMF",   "KB자산운용",       False, "daily",     True,  True),
    ("법인전용 MMF 제2호",      "MMF",   "신한자산운용",     True,  "daily",     True,  True),
    ("우량회사채 채권형",       "채권형", "NH아문디자산운용", False, "monthly",   True,  True),
    ("배당가치 주식형",         "주식형", "신영자산운용",     False, "quarterly", True,  True),
    ("코어오피스 부동산 1호",   "부동산", "이지스자산운용",   True,  "quarterly", False, True),
    ("물류인프라 부동산 3호",   "부동산", "마스턴투자운용",   True,  "annual",    False, True),
    ("해외리츠 재간접",         "재간접", "한화자산운용",     False, "monthly",   False, True),
    ("글로벌헤지 재간접 2호",   "재간접", "키움투자자산운용", False, "quarterly", False, True),
    ("사모 특별자산 4호",       "부동산", "이지스자산운용",   True,  "none",      False, False),
)

# 검증용 필수 컬럼 — 함수가 조용히 KeyError로 죽는 대신 무엇이 없는지 말한다.
_MASTER_REQUIRED = ("fund_id", "asof", "fair_value", "bank_share", "leverage",
                    "approach")
_HOLDING_REQUIRED = ("holding_id", "fund_id", "market_value", "risk_weight")
_MANDATE_REQUIRED = ("mandate_id", "fund_id", "asset_class", "max_weight",
                     "max_leverage", "risk_weight")
_SUMMARY_MASTER_REQUIRED = _MASTER_REQUIRED + ("fund_name", "fund_type",
                                               "lta_reason")

# mba_rwa 의 출력 컬럼. 빈 결과일 때도 같은 스키마를 내야 하류 조인이 깨지지
# 않으므로 한 곳에서만 정의한다.
_MBA_COLUMNS = ["fund_id", "asof", "method", "n_mandate_lines",
                "allocated_weight", "unallocated_weight", "avg_rw",
                "max_leverage", "investment", "effective_rw", "rwa",
                "capital_8pct"]


# ---------------------------------------------------------------- 공통 유틸

def _require_columns(df: pd.DataFrame, cols: tuple[str, ...], name: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"{name}에 필수 컬럼 없음: {missing}")


def _require_no_nan(df: pd.DataFrame, cols: tuple[str, ...], name: str) -> None:
    """NaN을 조용히 0으로 취급하면 위험가중자산이 과소계상된다."""
    bad = [c for c in cols if df[c].isna().any()]
    if bad:
        raise ValueError(f"{name} 컬럼에 NaN 존재: {bad}")


def _validate_asof(asof: str) -> str:
    # 기준일이 문자열 규격을 벗어나면 하류 조인이 조용히 어긋난다.
    datetime.strptime(asof, "%Y-%m-%d")
    return asof


def holding_risk_weight(asset_class: str, rating: str = "UNRATED") -> float:
    """편입자산 1건의 SA 위험가중치 (0~12.5).

    sovereign/bank/corporate는 `risk_lib.capital.rwa_sa.SA_RISK_WEIGHTS`를
    그대로 쓴다 — 여기에 표를 다시 적으면 두 표가 갈라지는 순간 어느 쪽이
    맞는지 알 수 없게 된다.

    모르는 등급은 UNRATED로 흡수하지 않고 **거부한다**. 흡수하면 오타 하나가
    회사채 CCC-(150%)를 UNRATED(100%)로 떨어뜨려 자본이 3분의 1 줄어드는데
    아무 신호도 남지 않는다.
    """
    ac = asset_class.lower()
    if rating not in RATINGS:
        raise ValueError(f"미지원 등급: {rating!r} (허용: {RATINGS})")
    if ac in SA_RISK_WEIGHTS:
        return float(SA_RISK_WEIGHTS[ac][rating])
    if ac == "securitisation":
        return float(_RW_SECURITISATION[rating])
    if ac in _RW_FLAT:
        return float(_RW_FLAT[ac])
    raise ValueError(f"미지원 자산군: {asset_class!r}")


def _notch_down(rating: str) -> str:
    """등급을 한 단계 낮춘다 — MBA는 지침이 허용하는 **최악 등급**을 가정한다."""
    if rating == "UNRATED":
        return "UNRATED"
    i = RATINGS.index(rating)
    return RATINGS[min(i + 1, RATINGS.index("CCC-"))]


def saccr_trade_view(holding: pd.DataFrame) -> pd.DataFrame:
    """파생 편입자산을 `risk_lib.ccr.saccr_ead()` 입력 형태로 투영한다 (CRE60.6).

    펀드 내 파생의 거래상대방 신용리스크는 CRE60.6상 별도 가산 대상이다.
    원장이 SA-CCR 입력을 이미 담고 있으므로 재계산·재입력 없이 넘긴다.
    시가(market_value)가 곧 파생의 MTM이다 — 자산 측 계상분만 담기 때문이다.
    """
    _require_columns(holding, ("is_derivative", "ccr_counterparty",
                               "ccr_asset_class", "notional", "market_value",
                               "maturity_years", "collateral"), "holding")
    d = holding.loc[holding["is_derivative"].astype(bool)]
    return pd.DataFrame({
        "counterparty": d["ccr_counterparty"].to_numpy(),
        "asset_class": d["ccr_asset_class"].to_numpy(),
        "notional": d["notional"].to_numpy(dtype=float),
        "mtm": d["market_value"].to_numpy(dtype=float),
        "maturity": d["maturity_years"].to_numpy(dtype=float),
        "collateral": d["collateral"].to_numpy(dtype=float),
    })


# ---------------------------------------------------------------- 산출 함수

def lta_rwa(master: pd.DataFrame, holding: pd.DataFrame) -> pd.DataFrame:
    """Look-through approach — 편입자산을 직접 보유한 것처럼 위험가중 (CRE60.5).

    RWA = min(평균위험가중치 × 레버리지, 1250%) × 투자 시가  (CRE60.10)

    편입자산이 없는 펀드는 **행이 나오지 않는다**. 0으로 채우면 정보가 없는
    펀드와 위험이 없는 펀드가 구분되지 않는다.
    """
    _require_columns(master, _MASTER_REQUIRED, "master")
    _require_columns(holding, _HOLDING_REQUIRED, "holding")
    _require_no_nan(holding, ("market_value", "risk_weight"), "holding")
    # master 쪽 NaN을 막지 않으면 effective_rw·rwa가 통째로 NaN이 되어
    # 합계에서 조용히 빠진다 — 소요자본이 그만큼 과소계상된다.
    _require_no_nan(master, ("fair_value", "leverage"), "master")

    unknown = sorted(set(holding["fund_id"]) - set(master["fund_id"]))
    if unknown:
        raise ValueError(f"master에 없는 fund_id의 편입자산: {unknown}")

    h = holding.copy()
    h["_rwa_contrib"] = h["market_value"] * h["risk_weight"]
    g = h.groupby("fund_id", as_index=False).agg(
        holding_mv_total=("market_value", "sum"),
        holding_rwa_total=("_rwa_contrib", "sum"),
        n_holdings=("holding_id", "count"))

    nonpositive = g.loc[g["holding_mv_total"] <= 0, "fund_id"].tolist()
    if nonpositive:
        raise ValueError(f"편입자산 시가 합계가 0 이하인 펀드: {nonpositive}")

    out = g.merge(
        master[["fund_id", "asof", "fair_value", "bank_share", "leverage"]],
        on="fund_id", how="left", validate="one_to_one")
    out["avg_rw"] = out["holding_rwa_total"] / out["holding_mv_total"]
    out["investment"] = out["fair_value"].astype(float)
    out["effective_rw"] = np.minimum(out["avg_rw"] * out["leverage"], RW_CAP)
    out["rwa"] = out["effective_rw"] * out["investment"]
    out["capital_8pct"] = out["rwa"] * BIS_MIN_TOTAL
    out["method"] = "look_through"
    out["n_holdings"] = out["n_holdings"].astype("int64")
    return out[["fund_id", "asof", "method", "n_holdings", "holding_mv_total",
                "holding_rwa_total", "avg_rw", "bank_share", "leverage",
                "investment", "effective_rw", "rwa", "capital_8pct"]]


def mba_rwa(master: pd.DataFrame, mandate: pd.DataFrame) -> pd.DataFrame:
    """Mandate-based approach — 운용지침 한도까지 투자했다고 가정 (CRE60.7).

    보수적 충전: **위험가중치가 높은 자산군부터** 한도를 채우고, 총자산 100%에
    도달하면 멈춘다. 한도 합이 100%에 미달하면 잔여는 현금(RW 0%)으로 보되
    그 크기를 `unallocated_weight`로 드러낸다 — 잔여를 조용히 0%로 흡수하면
    지침이 부실한 펀드일수록 자본이 가벼워지는 역전이 생긴다.

    레버리지도 **지침상 허용 최대치**를 쓴다 (CRE60.7 후단).
    """
    _require_columns(master, _MASTER_REQUIRED, "master")
    _require_columns(mandate, _MANDATE_REQUIRED, "mandate")
    _require_no_nan(mandate, ("max_weight", "max_leverage", "risk_weight"),
                    "mandate")
    _require_no_nan(master, ("fair_value",), "master")

    unknown = sorted(set(mandate["fund_id"]) - set(master["fund_id"]))
    if unknown:
        raise ValueError(f"master에 없는 fund_id의 운용지침: {unknown}")

    rows: list[dict[str, object]] = []
    # fund_id 정렬 고정 — 같은 입력이면 같은 행 순서여야 결과가 재현된다.
    for fund_id, g in mandate.groupby("fund_id", sort=True):
        # 동률 위험가중치는 자산군 이름으로 결정론적으로 정렬한다.
        g = g.sort_values(["risk_weight", "asset_class"],
                          ascending=[False, True])
        remaining = 1.0
        weighted_rw = 0.0
        for _, r in g.iterrows():
            if remaining <= 0.0:
                break            # 총자산 100% 충전 완료 — 남은 라인은 볼 필요 없다
            w = min(float(r["max_weight"]), remaining)
            if w <= 0.0:
                # 한도 0%(= 해당 자산군 투자 금지) 라인이다. 여기서 중단하면
                # 위험가중치가 더 낮은 뒤쪽 라인이 통째로 누락되어 충전이
                # 조기 종료되고, 지침이 금지한 자산군 하나 때문에 avg_rw가
                # 0으로 떨어진다. 건너뛰고 다음 라인을 채운다 (CRE60.7).
                continue
            weighted_rw += w * float(r["risk_weight"])
            remaining -= w
        unallocated = max(remaining, 0.0)
        rows.append({
            "fund_id": fund_id,
            "n_mandate_lines": int(len(g)),
            "allocated_weight": 1.0 - unallocated,
            "unallocated_weight": unallocated,
            "avg_rw": weighted_rw,   # 잔여분은 현금 가정(RW 0%)이라 가산 없음
            "max_leverage": float(g["max_leverage"].max()),
        })

    if not rows:
        # 운용지침이 한 건도 없으면 MBA 대상이 없다. 컬럼 없는 빈 프레임을
        # 그대로 넘기면 아래 merge가 KeyError('fund_id')로 죽어 원인이 가려진다.
        return pd.DataFrame(columns=_MBA_COLUMNS)

    out = pd.DataFrame(rows)
    out = out.merge(master[["fund_id", "asof", "fair_value"]],
                    on="fund_id", how="left", validate="one_to_one")
    out["investment"] = out["fair_value"].astype(float)
    out["effective_rw"] = np.minimum(out["avg_rw"] * out["max_leverage"], RW_CAP)
    out["rwa"] = out["effective_rw"] * out["investment"]
    out["capital_8pct"] = out["rwa"] * BIS_MIN_TOTAL
    out["method"] = "mandate"
    return out[_MBA_COLUMNS]


def fallback_rwa(master: pd.DataFrame) -> pd.DataFrame:
    """Fall-back approach — 1250% (CRE60.9). 모든 펀드에 대해 산출 가능하다."""
    _require_columns(master, _MASTER_REQUIRED, "master")
    _require_no_nan(master, ("fair_value",), "master")

    out = master[["fund_id", "asof"]].copy()
    out["method"] = "fallback"
    out["investment"] = master["fair_value"].astype(float).to_numpy()
    out["effective_rw"] = FALLBACK_RW
    out["rwa"] = out["effective_rw"] * out["investment"]
    out["capital_8pct"] = out["rwa"] * BIS_MIN_TOTAL
    return out.reset_index(drop=True)


def fund_rwa_summary(master: pd.DataFrame, holding: pd.DataFrame,
                     mandate: pd.DataFrame) -> pd.DataFrame:
    """세 방법의 결과를 나란히 두고 master의 산정방법대로 채택값을 고른다.

    산출 불가한 방법은 NaN으로 남는다 (편입자산·운용지침이 없는 경우).
    NaN 자체가 정보다 — 0으로 채우면 "위험 없음"으로 읽힌다. 채택값은 NaN이
    될 수 없으며 assert로 막는다.
    """
    _require_columns(master, _SUMMARY_MASTER_REQUIRED, "master")

    bad_approach = sorted(set(master["approach"]) - set(APPROACHES))
    if bad_approach:
        raise ValueError(f"미지원 산정방법: {bad_approach}")

    lta = lta_rwa(master, holding)[["fund_id", "effective_rw", "rwa"]].rename(
        columns={"effective_rw": "rw_lta", "rwa": "rwa_lta"})
    mba = mba_rwa(master, mandate)[["fund_id", "effective_rw", "rwa"]].rename(
        columns={"effective_rw": "rw_mba", "rwa": "rwa_mba"})
    fbk = fallback_rwa(master)[["fund_id", "effective_rw", "rwa"]].rename(
        columns={"effective_rw": "rw_fallback", "rwa": "rwa_fallback"})

    out = master[["fund_id", "asof", "fund_name", "fund_type", "approach",
                  "lta_reason"]].copy()
    out["investment"] = master["fair_value"].astype(float).to_numpy()
    for part in (lta, mba, fbk):
        out = out.merge(part, on="fund_id", how="left", validate="one_to_one")

    # 채택: 산정방법은 정보 가용성이 정한 것이므로 여기서 다시 고르지 않는다.
    col_order = {"look_through": 0, "mandate": 1, "fallback": 2}
    pick = out["approach"].map(col_order).to_numpy()
    row = np.arange(len(out))
    out["adopted_method"] = out["approach"]
    out["adopted_rwa"] = out[["rwa_lta", "rwa_mba", "rwa_fallback"]].to_numpy(
        dtype=float)[row, pick]
    out["adopted_rw"] = out[["rw_lta", "rw_mba", "rw_fallback"]].to_numpy(
        dtype=float)[row, pick]

    # 사유는 "왜 이 방법인가" — LTA 요건 판정 결과와 상위 방법이 막힌 이유를
    # 함께 남겨야 감사에서 방법 선택이 설명된다 (CRE60.2 우선순위).
    reason_fmt = {
        "look_through": "CRE60.5 LTA 적용 — {r}",
        "mandate": "CRE60.7 MBA 적용 — LTA 불가({r}), 운용지침 입수",
        "fallback": "CRE60.9 fallback 1250% 적용 — LTA 불가({r}), 운용지침 미입수",
    }
    out["adopted_reason"] = [reason_fmt[a].format(r=r)
                             for a, r in zip(out["approach"], out["lta_reason"])]
    out["adopted_capital_8pct"] = out["adopted_rwa"] * BIS_MIN_TOTAL

    if out["adopted_rwa"].isna().any():
        missing = out.loc[out["adopted_rwa"].isna(), "fund_id"].tolist()
        raise ValueError(
            f"채택 산정방법의 산출근거가 없는 펀드: {missing} — "
            "master.approach와 원장(편입자산·운용지침)이 어긋났다")
    assert (out["adopted_rw"] >= 0).all() and (out["adopted_rw"] <= RW_CAP).all(), \
        "채택 위험가중치가 0~1250% 범위를 벗어났다"

    return out[["fund_id", "asof", "fund_name", "fund_type", "approach",
                "investment", "rwa_lta", "rw_lta", "rwa_mba", "rw_mba",
                "rwa_fallback", "rw_fallback", "adopted_method", "adopted_rw",
                "adopted_rwa", "adopted_capital_8pct", "adopted_reason"]]


# ---------------------------------------------------------------- 합성 원장

def _build_master(asof: str, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed + 6100)
    rows: list[dict[str, object]] = []
    for i, (name, ftype, mgr, trust, freq, audited,
            has_mandate) in enumerate(_FUND_SEEDS, start=1):
        # LTA 요건: (1) 충분한 빈도의 정보 (2) 제3자 독립 검증 — CRE60.5
        freq_ok = freq in _LTA_SUFFICIENT_FREQUENCIES
        lta_eligible = bool(freq_ok and audited)
        # lta_reason은 **LTA 적용가능 여부의 사유만** 담는다. 운용지침 입수
        # 여부는 MBA 요건이므로 mandate_available 컬럼이 따로 말한다.
        if lta_eligible:
            reason = f"정보 제공 빈도 {freq}(분기 이상) · 제3자 독립 검증 완료"
        else:
            gaps = []
            if not freq_ok:
                gaps.append(f"CRE60.5(1) 정보 빈도 {freq} — 분기 미만")
            if not audited:
                gaps.append("CRE60.5(2) 제3자 독립 검증 부재")
            reason = " · ".join(gaps)

        if lta_eligible:
            approach = "look_through"
        elif has_mandate:
            approach = "mandate"
        else:
            approach = "fallback"

        fair_value = float(rng.uniform(3.0e10, 2.4e11))
        if approach == "fallback":
            # 1250%는 투자원금 전액을 자본으로 덮는 것과 같다. 실무상 이 대상은
            # 소액 잔여 포지션으로 관리하므로 규모를 축소해 반영한다.
            fair_value *= 0.20
        # 장부가는 취득원가 기준 — 평가손익만큼 시가와 벌어진다.
        carrying = fair_value / (1.0 + float(rng.uniform(-0.08, 0.14)))
        share = float(rng.uniform(0.02, 0.55))
        nav = fair_value / share
        lo, hi = _LEVERAGE_RANGE[ftype]
        lev = float(rng.uniform(lo, hi))

        rows.append({
            "fund_id": f"FND{i:03d}",
            "asof": asof,
            "fund_name": name,
            "fund_type": ftype,
            "manager": mgr,
            "is_trust": bool(trust),
            "carrying_amount": carrying,
            "fair_value": fair_value,
            "fund_nav": nav,
            "fund_total_assets": nav * lev,
            "bank_share": share,
            "leverage": lev,
            "info_frequency": freq,
            "third_party_audited": bool(audited),
            "mandate_available": bool(has_mandate),
            "lta_eligible": lta_eligible,
            "lta_reason": reason,
            "approach": approach,
        })
    return pd.DataFrame(rows)


def _build_holding(master: pd.DataFrame, asof: str, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed + 6200)
    rows: list[dict[str, object]] = []
    for _, f in master.iterrows():
        if f["info_frequency"] == "none":
            # 편입자산 정보를 아예 제공받지 못한 펀드다. 그런데도 편입자산
            # 원장에 행을 만들면 "정보 없음"을 사유로 1250%(CRE60.9)를
            # 적용하면서 동시에 총자산과 정확히 일치하는 완전한 look-through
            # 자료를 보유한 모순이 된다 — fallback 적용 근거가 감사에서
            # 무너지고, 하류에서 그 rwa_lta(=1250%의 10분의 1 수준)를 쓸 수
            # 있게 된다. 정보가 없다는 사실은 행의 부재로 드러나야 한다.
            continue
        mix = _HOLDING_MIX[f["fund_type"]]
        classes = [c for c, _ in mix]
        probs = np.array([p for _, p in mix], dtype=float)
        n = int(rng.integers(8, 21))
        # Dirichlet — 비중 합이 정확히 1이 되어 Σ시가 = 총자산이 성립한다.
        weights = rng.dirichlet(np.full(n, 3.0))
        total_assets = float(f["fund_total_assets"])
        for k in range(n):
            ac = str(rng.choice(classes, p=probs))
            rating = str(rng.choice(_RATING_POOL[ac]))
            w = float(weights[k])
            mv = w * total_assets
            mat = (0.0 if ac in ("equity", "real_estate", "fund", "cash")
                   else float(rng.uniform(0.25, 10.0)))
            is_deriv = bool(ac in _CCR_CLASS_MAP and rng.random() < 0.08)
            if is_deriv:
                ccr_cp = str(rng.choice(_DEALER_POOL))
                ccr_ac = _CCR_CLASS_MAP[ac]
                # 명목금액은 자산 계상액(MTM)의 배수다. 배수를 크게 잡으면
                # 명목이 펀드 총자산을 넘어서는 비현실적 오버레이가 된다 —
                # 선물 오버레이 수준(총자산의 수십 % 이내)으로 묶는다.
                notional = mv * float(rng.uniform(1.5, 5.0))
                collateral = notional * float(rng.uniform(0.0, 0.4))
                # 파생의 잔존만기는 SA-CCR 만기요소에 쓰이므로 0이면 안 된다.
                if mat <= 0.0:
                    mat = float(rng.uniform(0.25, 3.0))
            else:
                # 비파생은 SA-CCR 대상이 아니다. NaN 대신 'none'/0으로 채워
                # 하류에서 결측과 구분되게 한다.
                ccr_cp, ccr_ac, notional, collateral = "none", "none", 0.0, 0.0
            rows.append({
                "holding_id": f"{f['fund_id']}-H{k + 1:02d}",
                "fund_id": f["fund_id"],
                "asof": asof,
                "issuer": f"{f['fund_id']}-{ac.upper()}-{k + 1:02d}",
                "asset_class": ac,
                "rating": rating,
                "market_value": mv,
                "weight": w,
                "maturity_years": mat,
                "risk_weight": holding_risk_weight(ac, rating),
                "is_derivative": is_deriv,
                "ccr_counterparty": ccr_cp,
                "ccr_asset_class": ccr_ac,
                "notional": notional,
                "collateral": collateral,
            })
    return pd.DataFrame(rows)


def _build_mandate(master: pd.DataFrame, holding: pd.DataFrame, asof: str,
                   seed: int) -> pd.DataFrame:
    """운용지침 한도를 편입자산 실적에서 파생한다.

    한도는 **실제 보유 비중보다 넓다** — 그래야 원장이 서로 모순되지 않고
    (지침을 위반한 보유가 생기지 않고), MBA가 LTA보다 보수적이라는 CRE60의
    설계 의도가 데이터에서 실제로 관찰된다.
    """
    rng = np.random.default_rng(seed + 6300)
    rows: list[dict[str, object]] = []
    for _, f in master.iterrows():
        if not bool(f["mandate_available"]):
            # 운용지침을 입수하지 못한 펀드는 행이 없다 → MBA 산출 불가 →
            # fallback. 빈 행을 만들어두면 MBA가 계산돼버린다.
            continue
        fid = f["fund_id"]
        h = holding.loc[holding["fund_id"] == fid]
        agg = (h.loc[h["asset_class"] != "cash"]
               .groupby("asset_class")
               .agg(actual_weight=("weight", "sum"),
                    worst_rating=("rating", lambda s: max(
                        s, key=lambda r: RATINGS.index(r))))
               .reset_index()
               .sort_values("actual_weight", ascending=False))

        lines = [(str(r["asset_class"]), str(r["worst_rating"]),
                  float(r["actual_weight"]))
                 for _, r in agg.iterrows()]
        # 지침 라인은 3~5건 — 비현금 2건 미만이면 보유는 없으나 허용된 자산군을
        # 채워 넣는다(지침은 보유보다 넓다).
        if len(lines) < 2:
            held = {ac for ac, _, _ in lines}
            for ac, _p in _HOLDING_MIX[f["fund_type"]]:
                if ac != "cash" and ac not in held:
                    lines.append((ac, _RATING_POOL[ac][-1], 0.0))
                    if len(lines) >= 2:
                        break
        lines = lines[:4]

        max_lev = round(float(f["leverage"]) * float(rng.uniform(1.05, 1.35)), 2)
        for j, (ac, worst, actual_w) in enumerate(lines, start=1):
            assumed = _notch_down(worst)
            max_w = float(min(1.0, max(0.15, actual_w * rng.uniform(1.15, 1.50))))
            rows.append({
                "mandate_id": f"{fid}-M{j:02d}",
                "fund_id": fid,
                "asof": asof,
                "asset_class": ac,
                "rating_assumed": assumed,
                "max_weight": max_w,
                "max_leverage": max_lev,
                "risk_weight": holding_risk_weight(ac, assumed),
            })
        # 현금성 자산 한도 100% — 지침의 잔여 수용 라인. 이것이 있어야 MBA의
        # 충전이 항상 총자산 100%에서 종료된다(미충전 잔여 없음).
        rows.append({
            "mandate_id": f"{fid}-M{len(lines) + 1:02d}",
            "fund_id": fid,
            "asof": asof,
            "asset_class": "cash",
            "rating_assumed": "UNRATED",
            "max_weight": 1.0,
            "max_leverage": max_lev,
            "risk_weight": holding_risk_weight("cash"),
        })
    return pd.DataFrame(rows)


def build_funds(*, asof: str, seed: int = 42) -> dict[str, pd.DataFrame]:
    """집합투자증권 원장 3종과 CRE60 산출결과를 만든다.

    같은 (asof, seed)이면 비트 단위로 같은 결과가 나온다 — 난수는 모두
    default_rng(seed + 테이블 고유 오프셋)에서만 나오고 시각 의존이 없다.
    """
    asof = _validate_asof(asof)

    master = _build_master(asof, seed)
    holding = _build_holding(master, asof, seed)
    mandate = _build_mandate(master, holding, asof, seed)
    result = fund_rwa_summary(master, holding, mandate)

    # --- 생성 직후 자체 점검. 원장이 깨진 채로 하류에 흘러가면 자본이 틀린다.
    for nm, df in (("rdm_fund_master", master), ("rdm_fund_holding", holding),
                   ("rdm_fund_mandate", mandate), ("rwa_fund_result", result)):
        assert not df.empty, f"{nm}이 비었다"
    assert not master.isna().any().any(), "master에 NaN"
    assert not holding.isna().any().any(), "holding에 NaN"
    assert not mandate.isna().any().any(), "mandate에 NaN"

    # 편입자산 원장에 있어야 할 펀드 집합을 먼저 못박는다. groupby 결과만 놓고
    # 대사하면 편입자산이 통째로 빠진 펀드는 대사 대상에서도 사라져 조용히
    # 넘어간다 — 정보를 제공받은 펀드는 반드시 편입자산이 있어야 한다.
    expect_holding = set(master.loc[master["info_frequency"] != "none", "fund_id"])
    assert set(holding["fund_id"]) == expect_holding, \
        "편입자산 원장의 펀드 집합이 master의 정보제공 여부와 불일치"

    # 편입자산 시가 합계 = 펀드 총자산 (LTA 평균위험가중치의 분모 정합성)
    mv = holding.groupby("fund_id")["market_value"].sum()
    ta = master.set_index("fund_id")["fund_total_assets"]
    assert np.allclose(mv.to_numpy(), ta.loc[mv.index].to_numpy(), rtol=1e-9), \
        "편입자산 시가 합계가 펀드 총자산과 불일치 — LTA 평균위험가중치가 왜곡된다"

    assert holding["risk_weight"].between(0.0, RW_CAP).all(), "위험가중치 범위 초과"
    assert mandate["risk_weight"].between(0.0, RW_CAP).all(), "지침 위험가중치 범위 초과"
    assert master["bank_share"].between(0.0, 1.0).all(), "지분율 범위 초과"
    assert (master["leverage"] >= 1.0).all(), "레버리지가 1 미만 — 총자산 < 순자산"
    assert (master["fair_value"] > 0).all(), "투자 시가가 0 이하"
    assert set(master["approach"]) <= set(APPROACHES), "미지원 산정방법"
    # 세 방법이 모두 실제로 쓰이지 않으면 이 원장은 경로를 검증하지 못한다.
    assert set(master["approach"]) == set(APPROACHES), \
        "세 산정방법(LTA·MBA·fallback)이 모두 나타나지 않는다"

    return {
        "rdm_fund_master": master,
        "rdm_fund_holding": holding,
        "rdm_fund_mandate": mandate,
        "rwa_fund_result": result,
    }
