"""파생상품 원장 — SA-CCR(CRE52) EAD와 FRTB 민감도(MAR21)를 한 벌의 원장에서 낸다.

**이 원장이 왜 필요한가.** 기존 `risk_lib.ccr.synthesise_derivatives`는 은행
차주의 신용 익스포저에서 파생 거래를 즉석으로 지어낸다. 그 방식은 CCR 숫자를
화면에 띄우는 데는 충분하지만 원장이 아니다 — 거래 식별자가 없어 대사가 안 되고,
넷팅집합·담보약정이 없어 증거금 효과를 설명할 수 없으며, 다리(leg)가 없어
같은 거래에서 시장리스크 민감도를 뽑을 수 없다. 그 결과 CCR 담당과 시장리스크
담당이 **서로 다른 파생 포지션**을 들고 회의에 들어온다.

**무엇을 담는가.** 거래 마스터 / 기초자산(다리) / 넷팅집합의 3층 구조다.
마스터는 거래 조건(명목·만기·시가·증거금·MPOR·북), 다리는 위험요인(자산군·
헤징집합·감독델타·조정명목·민감도), 넷팅집합은 담보약정(CSA·threshold·MTA·
IM·VM)을 갖는다. 담보는 넷팅집합에만 원본이 있고 거래 담보는 그 배분값이다 —
두 곳에 따로 적으면 둘 중 하나는 틀릴 준비가 된 것이다.

**무엇을 가능하게 하는가.**
  * `saccr_input()`  → `risk_lib.ccr.saccr_ead`가 그대로 받는 다리 단위 입력
    (CRE52.19-52.24). 감독요율 표는 `ccr.SF`를 import 해서 쓰며 여기에 복사하지
    않는다.
  * `market_sensitivities()` → FRTB 표준방법 위험군(GIRR/CSR/EQ/FX/COMM)별
    델타·베가·커버처 입력 집계 (MAR21).

**결정론.** 모든 합성은 `np.random.default_rng(seed + 고유오프셋)`으로만 뽑는다.
같은 seed·asof면 비트 단위로 같은 산출이 나온다. 시각 의존 코드는 없다.
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd

# 감독요율(supervisory factor)은 CCR 엔진이 이미 갖고 있다. 별사본을 두면
# 규제 개정 때 한쪽만 고쳐지므로 import 해서 쓴다 (CRE52.72 표).
from risk_lib.ccr import SF

__all__ = [
    "ASSET_CLASSES",
    "FRTB_RISK_CLASS",
    "PRODUCT_TYPES",
    "build_derivatives",
    "saccr_input",
    "market_sensitivities",
]


# ---------------------------------------------------------------- 어휘

# 자산군 어휘는 ccr.SF 의 키와 **정확히 같아야** 한다. 다르면 saccr_ead가
# KeyError로 죽거나(운이 좋은 경우) 조용히 다른 요율을 쓴다. import 시점에
# 대칭차집합으로 양방향을 막는다 — 새 자산군이 SF에 생겨도 여기서 걸린다.
ASSET_CLASSES: tuple[str, ...] = ("ir", "fx", "credit_ig", "equity", "commodity")
_VOCAB_GAP = set(ASSET_CLASSES) ^ set(SF)
if _VOCAB_GAP:
    raise ImportError(
        f"자산군 어휘가 risk_lib.ccr.SF와 어긋난다: {sorted(_VOCAB_GAP)}. "
        "SF 키를 바꿨다면 ASSET_CLASSES와 FRTB_RISK_CLASS도 함께 고쳐야 한다.")

PRODUCT_TYPES: tuple[str, ...] = ("swap", "forward", "option", "swaption", "cds")

# SA-CCR 자산군 → FRTB 표준방법 위험군 (MAR21.1). 두 규제의 분류 축이 달라
# 1:1 대응이 아니지만(예: CSR은 신용스프레드 전반), 파생 원장 수준에서는
# 자산군이 곧 주위험요인이므로 이 사상으로 충분하다.
FRTB_RISK_CLASS: dict[str, str] = {
    "ir": "GIRR",
    "credit_ig": "CSR",
    "equity": "EQ",
    "fx": "FX",
    "commodity": "COMM",
}

BOOKS: tuple[str, ...] = ("trading", "banking")

# 만기 하한 10영업일 = 0.04년 (CRE52.22). 초단기 거래의 조정명목이 0으로
# 수렴해 add-on이 사라지는 것을 막는 규정상 바닥이다.
_MATURITY_FLOOR_YEARS = 10.0 / 250.0

# MPOR(증거금위험기간). 중앙청산 5영업일, 양자간 일일증거금 10영업일
# (CRE52.51-52.54). 무증거금 거래는 MPOR 개념 자체가 없으므로 0을 쓰고
# margined 플래그로 구분한다 — NaN을 두면 집계에서 조용히 사라진다.
_MPOR_CLEARED = 5
_MPOR_MARGINED = 10
_MPOR_UNMARGINED = 0

# 기초자산 사전 — (자산군, 코드, 통화, 헤징집합, 기준가격/기준금리).
# 헤징집합 규칙: 이자율은 통화별(CRE52.32), FX는 통화쌍별(CRE52.34),
# 신용·주식은 자산군당 하나(CRE52.36), 상품은 에너지/금속/농산물/기타
# 그룹별(CRE52.37). 규칙을 코드로 계산하지 않고 표에 박아 둔 이유는
# 코드→헤징집합 대응이 감사 대상이라 눈으로 확인 가능해야 하기 때문이다.
_UNDERLYINGS: tuple[tuple[str, str, str, str, float], ...] = (
    ("ir", "IRS_KRW_CD3M", "KRW", "IR_KRW", 0.0350),
    ("ir", "IRS_USD_SOFR3M", "USD", "IR_USD", 0.0430),
    ("ir", "IRS_EUR_ESTR6M", "EUR", "IR_EUR", 0.0270),
    ("ir", "IRS_JPY_TONA6M", "JPY", "IR_JPY", 0.0090),
    ("ir", "IRS_CNY_FR007", "CNY", "IR_CNY", 0.0210),
    ("fx", "FX_USDKRW", "USD", "FX_KRW_USD", 1330.0),
    ("fx", "FX_EURKRW", "EUR", "FX_EUR_KRW", 1440.0),
    ("fx", "FX_JPYKRW", "JPY", "FX_JPY_KRW", 9.10),
    ("fx", "FX_CNYKRW", "CNY", "FX_CNY_KRW", 185.0),
    ("credit_ig", "CDS_KR_SOV_5Y", "USD", "CREDIT", 0.0035),
    ("credit_ig", "CDS_KR_CORP_IG_5Y", "KRW", "CREDIT", 0.0080),
    ("credit_ig", "CDS_ITRAXX_ASIA_IG", "USD", "CREDIT", 0.0090),
    ("equity", "EQ_KOSPI200", "KRW", "EQUITY", 350.0),
    ("equity", "EQ_SAMSUNG_ELEC", "KRW", "EQUITY", 78000.0),
    ("equity", "EQ_SPX", "USD", "EQUITY", 5200.0),
    ("commodity", "COMM_WTI", "USD", "COMM_ENERGY", 78.0),
    ("commodity", "COMM_GOLD", "USD", "COMM_METALS", 2350.0),
    ("commodity", "COMM_COPPER", "USD", "COMM_METALS", 9200.0),
)

# 옵션 감독변동성 — 감독델타 산출용 (CRE52.41의 σ). 자산군별 관행적 수준.
_SUPERVISORY_VOL: dict[str, float] = {
    "ir": 0.50, "fx": 0.10, "credit_ig": 0.50, "equity": 0.25, "commodity": 0.30,
}

# 합성 규모 — 과제 요구 범위. 명목 총액은 이 범위 안으로 스케일한다.
_N_TRADES_RANGE = (60, 121)          # 60~120건
_N_COUNTERPARTY_RANGE = (10, 21)     # 10~20개
_NOTIONAL_TOTAL_RANGE = (3.0e12, 8.0e12)   # 3~8조 KRW


# ---------------------------------------------------------------- 수학 보조

def _norm_cdf(x: float) -> float:
    """표준정규 누적분포. scipy 의존을 피하려고 erf로 직접 쓴다."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _supervisory_duration(start_years: float, end_years: float) -> float:
    """감독듀레이션 SD = (e^{-0.05·S} − e^{-0.05·E}) / 0.05 (CRE52.20).

    이자율·신용 자산군의 **조정명목** = 명목 × SD 이다. 총명목을 그대로 쓰면
    5년 스왑의 add-on이 4배 넘게 과소계상된다.
    """
    s = max(float(start_years), 0.0)
    e = max(float(end_years), s + _MATURITY_FLOOR_YEARS)
    return (math.exp(-0.05 * s) - math.exp(-0.05 * e)) / 0.05


def _adjusted_notional(asset_class: str, notional: float,
                       start_years: float, end_years: float) -> float:
    """조정명목 (CRE52.19-52.22).

    이자율·신용: 명목 × 감독듀레이션. FX·주식·상품: 명목 그대로(거래통화 환산).
    """
    if asset_class in ("ir", "credit_ig"):
        return notional * _supervisory_duration(start_years, end_years)
    return notional


def _supervisory_delta(*, sign: int, is_option: bool, ref_level: float,
                       strike: float, vol: float, expiry_years: float) -> float:
    """감독델타 δ (CRE52.38-52.41).

    선형 상품은 ±1. 옵션은 δ = ±Φ(±(ln(P/K) + 0.5σ²T) / (σ√T)) 이며, MVP에서는
    모든 옵션을 콜로 본다(매도는 부호 반전) — 풋/콜 구분 필드가 원장 요구사항에
    없으므로 없는 정보를 지어내지 않는다.
    """
    if not is_option:
        return float(sign)
    t = max(float(expiry_years), _MATURITY_FLOOR_YEARS)
    denom = vol * math.sqrt(t)
    d1 = (math.log(ref_level / strike) + 0.5 * vol * vol * t) / denom
    return float(sign) * _norm_cdf(d1)


def _assert_clean(df: pd.DataFrame, name: str) -> None:
    """빈 테이블·결측을 조용히 통과시키지 않는다 (원장 규율 4)."""
    if df.empty:
        raise AssertionError(f"{name}: 빈 테이블 — 원장이 비면 하위 산출이 조용히 0이 된다")
    na = df.columns[df.isna().any()].tolist()
    if na:
        raise AssertionError(f"{name}: 결측 컬럼 {na} — 사유 없는 NaN은 허용하지 않는다")


# ---------------------------------------------------------------- 합성

def _synthesise_netting_sets(rng: np.random.Generator, asof: str
                             ) -> list[dict[str, Any]]:
    """거래상대방 10~20, 상대방당 넷팅집합 1~2를 만든다 (담보약정 조건 포함)."""
    n_cp = int(rng.integers(*_N_COUNTERPARTY_RANGE))
    sets: list[dict[str, Any]] = []
    for i in range(n_cp):
        cp = f"CPTY{i + 1:04d}"
        for k in range(int(rng.integers(1, 3))):
            csa = bool(rng.random() < 0.75)
            # CSA가 없으면 threshold·MTA는 개념이 성립하지 않는다 → 0.0 + csa 플래그.
            threshold = float(rng.choice([0.0, 1.0e9, 5.0e9])) if csa else 0.0
            mta = float(rng.choice([1.0e8, 5.0e8])) if csa else 0.0
            sets.append({
                "netting_set_id": f"NS{i + 1:04d}{k + 1}",
                "asof": asof,
                "counterparty": cp,
                "csa": csa,
                "threshold": threshold,
                "mta": mta,
                # IM 요율은 거래 후 총명목에 곱한다 (아래 2차 패스).
                "_im_rate": float(rng.uniform(0.005, 0.020)) if csa else 0.0,
            })
    return sets


def _leg_plan(product_type: str, currency: str,
              rng: np.random.Generator) -> list[tuple[str, float]]:
    """상품유형 → [(자산군, 명목배분비)] . 배분비 합은 1이다.

    같은 명목을 다리마다 **전액 반복하면** add-on이 다리 수만큼 부풀어 오른다.
    ccr.saccr_ead는 헤징집합 내 상계를 하지 않으므로(단순 합산), 거래 명목을
    다리에 배분하는 쪽이 무중복과 보수성의 균형점이다. 헤징집합 상계를 하는
    완전한 CRE52 엔진으로 갈 때는 이 배분비만 1.0으로 바꾸면 된다.
    """
    if product_type == "swap":
        if currency != "KRW" and rng.random() < 0.35:
            return [("ir", 0.35), ("ir", 0.35), ("fx", 0.30)]   # 통화스왑
        return [("ir", 0.5), ("ir", 0.5)]                        # 고정/변동 다리
    if product_type == "forward":
        if currency != "KRW":
            return [("fx", 1.0)]
        return [(str(rng.choice(["commodity", "equity"], p=[0.6, 0.4])), 1.0)]
    if product_type == "option":
        return [(str(rng.choice(["equity", "fx", "commodity"], p=[0.5, 0.3, 0.2])), 1.0)]
    if product_type == "swaption":
        return [("ir", 1.0)]
    if product_type == "cds":
        return [("credit_ig", 1.0)]
    raise ValueError(f"미지원 상품유형: {product_type}")


def _pick_underlying(asset_class: str, currency: str,
                     rng: np.random.Generator) -> tuple[str, str, str, str, float]:
    """자산군·거래통화에 맞는 기초자산을 고른다. 통화가 맞는 것이 있으면 우선."""
    pool = [u for u in _UNDERLYINGS if u[0] == asset_class]
    matched = [u for u in pool if u[2] == currency]
    candidates = matched if matched else pool
    return candidates[int(rng.integers(0, len(candidates)))]


def _synthesise(*, asof: str, seed: int
                ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """마스터·다리·넷팅집합 3표를 결정론적으로 합성한다."""
    asof_date = date.fromisoformat(asof)
    rng_ns = np.random.default_rng(seed + 7101)
    rng_tr = np.random.default_rng(seed + 7102)
    rng_leg = np.random.default_rng(seed + 7103)

    sets = _synthesise_netting_sets(rng_ns, asof)
    set_ids = [s["netting_set_id"] for s in sets]
    set_of = {s["netting_set_id"]: s for s in sets}

    # ---- 거래 마스터 (담보 제외 1차 패스) ----
    n_trades = int(rng_tr.integers(*_N_TRADES_RANGE))
    # 넷팅집합이 하나도 비지 않도록 앞부분은 라운드로빈으로 채운다 —
    # 거래 0건인 넷팅집합은 담보만 있고 익스포저가 없는 유령 행이 된다.
    assigned = [set_ids[i % len(set_ids)] for i in range(len(set_ids))]
    assigned += [set_ids[int(rng_tr.integers(0, len(set_ids)))]
                 for _ in range(n_trades - len(set_ids))]

    raw_notional = rng_tr.lognormal(mean=0.0, sigma=0.7, size=n_trades)
    target_total = float(rng_tr.uniform(*_NOTIONAL_TOTAL_RANGE))
    # 백만원 단위로 반올림 — 원 단위 소수는 원장에서 의미가 없다.
    notionals = np.round(raw_notional / raw_notional.sum() * target_total, -6)

    trades: list[dict[str, Any]] = []
    for i in range(n_trades):
        ns_id = assigned[i]
        ns = set_of[ns_id]
        product = str(rng_tr.choice(PRODUCT_TYPES, p=[0.45, 0.20, 0.15, 0.10, 0.10]))
        direction = str(rng_tr.choice(["buy", "sell"]))
        currency = str(rng_tr.choice(["KRW", "USD", "EUR", "JPY", "CNY"],
                                     p=[0.55, 0.25, 0.10, 0.06, 0.04]))
        residual_years = float(rng_tr.uniform(0.25, 10.0))
        maturity_date = asof_date + timedelta(days=int(round(residual_years * 365.25)))
        trade_date = asof_date - timedelta(days=int(rng_tr.integers(30, 1800)))
        # 중앙청산 거래는 CCP가 일일 증거금을 강제하므로 담보약정 없는
        # 넷팅집합에는 존재할 수 없다 — csa 조건을 빼면 cleared=True인데
        # margined=False인 모순 행이 생긴다.
        cleared = bool(ns["csa"] and product in ("swap", "swaption")
                       and currency in ("KRW", "USD") and rng_tr.random() < 0.50)
        margined = bool(ns["csa"] and (cleared or rng_tr.random() < 0.85))
        mpor = (_MPOR_CLEARED if cleared else
                _MPOR_MARGINED if margined else _MPOR_UNMARGINED)
        notional = float(notionals[i])
        mtm = notional * float(rng_tr.normal(0.005, 0.02))
        # 옵션 매수자의 시가는 음수가 될 수 없다(프리미엄 지급 후 권리 보유).
        if product in ("option", "swaption"):
            mtm = abs(mtm) if direction == "buy" else -abs(mtm)
        trades.append({
            "trade_id": f"DRV{i + 1:05d}",
            "asof": asof,
            "counterparty": ns["counterparty"],
            "netting_set_id": ns_id,
            "product_type": product,
            "direction": direction,
            "notional": notional,
            "currency": currency,
            # NDF 등은 원화로 차액결제한다 — 결제통화가 거래통화와 다를 수 있다.
            "settlement_currency": ("KRW" if currency != "KRW"
                                    and product == "forward"
                                    and rng_tr.random() < 0.5 else currency),
            "trade_date": trade_date.isoformat(),
            "maturity_date": maturity_date.isoformat(),
            "residual_maturity_years": float((maturity_date - asof_date).days / 365.25),
            "mtm": mtm,
            "margined": margined,
            "mpor_days": int(mpor),
            "book": str(rng_tr.choice(BOOKS, p=[0.75, 0.25])),
            "cleared": cleared,
        })
    master = pd.DataFrame(trades)

    # ---- 넷팅집합 2차 패스: 순시가·IM·VM ----
    agg = master.groupby("netting_set_id").agg(
        net_mtm=("mtm", "sum"),
        gross_notional=("notional", "sum"),
        n_trades=("trade_id", "size"),
        n_margined=("margined", "sum"),
    )
    ns_rows: list[dict[str, Any]] = []
    for s in sets:
        a = agg.loc[s["netting_set_id"]]
        net_mtm = float(a["net_mtm"])
        margined_any = bool(a["n_margined"] > 0)
        # VM: 익스포저가 threshold를 넘고 그 초과분이 MTA 이상일 때만 수수한다
        # (ISDA CSA 관행 · CRE52.44의 담보 인식 전제).
        call = max(net_mtm - s["threshold"], 0.0) if (s["csa"] and margined_any) else 0.0
        vm = call if call >= s["mta"] else 0.0
        im = float(a["gross_notional"]) * s["_im_rate"] if margined_any else 0.0
        ns_rows.append({
            "netting_set_id": s["netting_set_id"],
            "asof": s["asof"],
            "counterparty": s["counterparty"],
            "csa": s["csa"],
            "threshold": s["threshold"],
            "mta": s["mta"],
            "im": float(im),
            "vm": float(vm),
            "net_mtm": net_mtm,
            "gross_notional": float(a["gross_notional"]),
            "n_trades": int(a["n_trades"]),
        })
    netting = pd.DataFrame(ns_rows)

    # ---- 거래 담보 = 넷팅집합 담보(IM+VM)의 명목 비례 배분 ----
    # 담보의 원본은 넷팅집합이다. 거래별 담보를 따로 뽑으면 두 표의 합이
    # 어긋나고, 그 순간부터 어느 쪽이 맞는지 아무도 모른다.
    coll_total = netting.set_index("netting_set_id")[["im", "vm"]].sum(axis=1)
    ns_gross = master.groupby("netting_set_id")["notional"].transform("sum")
    master["collateral"] = (master["netting_set_id"].map(coll_total).astype(float)
                            * master["notional"] / ns_gross)
    master = master[[
        "trade_id", "asof", "counterparty", "netting_set_id", "product_type",
        "direction", "notional", "currency", "settlement_currency", "trade_date",
        "maturity_date", "residual_maturity_years", "mtm", "collateral",
        "margined", "mpor_days", "book", "cleared"]]

    # ---- 기초자산(다리) ----
    legs: list[dict[str, Any]] = []
    for t in master.itertuples(index=False):
        plan = _leg_plan(t.product_type, t.currency, rng_leg)
        shares = np.array([p[1] for p in plan], dtype=float)
        shares = shares / shares.sum()   # 부동소수 합 오차 제거
        sign = 1 if t.direction == "buy" else -1
        is_option = t.product_type in ("option", "swaption")
        for j, ((asset_class, _), share) in enumerate(zip(plan, shares), start=1):
            ac, code, ccy, hedging_set, ref_level = _pick_underlying(
                asset_class, t.currency, rng_leg)
            # 스왑션은 옵션 만기 이후에 스왑이 시작한다 → S > 0 (CRE52.21).
            start_years = (float(t.residual_maturity_years) * float(rng_leg.uniform(0.15, 0.40))
                           if t.product_type == "swaption" else 0.0)
            end_years = float(t.residual_maturity_years)
            leg_notional = float(t.notional) * float(share)
            vol = _SUPERVISORY_VOL[ac] if is_option else 0.0
            strike = (ref_level * float(rng_leg.uniform(0.85, 1.15))) if is_option else 0.0
            delta = _supervisory_delta(
                sign=sign, is_option=is_option, ref_level=ref_level,
                strike=strike if is_option else ref_level, vol=vol,
                expiry_years=(start_years if t.product_type == "swaption" else end_years))
            adj_notional = _adjusted_notional(ac, leg_notional, start_years, end_years)

            # 민감도. 해당 없는 위험군은 0.0 — NaN을 두면 집계에서 조용히 사라진다.
            dur = max(end_years - start_years, _MATURITY_FLOOR_YEARS)
            dv01 = cs01 = delta_eq = delta_fx = delta_comm = 0.0
            if ac == "ir":
                # 고정지급(buy) 포지션은 금리 상승 시 이익 → dv01 > 0.
                # 다리별 dv01은 거래 순 dv01을 명목 배분비로 나눈 값이다 —
                # 고정·변동 다리를 총액으로 잡으면 상계 전 금액이 두 배가 된다.
                dv01 = leg_notional * dur * 1e-4 * sign
            elif ac == "credit_ig":
                # 보장매수(buy)는 스프레드 확대 시 이익 → cs01 > 0.
                cs01 = leg_notional * dur * 1e-4 * sign
            elif ac == "equity":
                delta_eq = leg_notional * abs(delta) * 0.01 * sign
            elif ac == "fx":
                delta_fx = leg_notional * abs(delta) * 0.01 * sign
            elif ac == "commodity":
                delta_comm = leg_notional * abs(delta) * 0.01 * sign
            # 베가는 옵션성 다리에만 존재한다 (1 vol point = 0.01 변동 기준).
            vega = (leg_notional * 0.004 * math.sqrt(max(end_years, 0.1)) * sign
                    if is_option else 0.0)

            legs.append({
                "underlying_id": f"{t.trade_id}-L{j}",
                "trade_id": t.trade_id,
                "leg_id": int(j),
                "asof": asof,
                "asset_class": ac,
                "underlying_code": code,
                "hedging_set": hedging_set,
                "currency": ccy,
                "notional_share": float(share),
                "leg_notional": leg_notional,
                "adjusted_notional": float(adj_notional),
                "supervisory_delta": float(delta),
                # 스왑션은 옵션 만기(S) 이후 스왑이 시작하므로 start_date ≠ asof.
                "start_date": (asof_date + timedelta(
                    days=int(round(start_years * 365.25)))).isoformat(),
                "end_date": (asof_date + timedelta(
                    days=int(round(end_years * 365.25)))).isoformat(),
                "start_years": float(start_years),
                "end_years": end_years,
                "volatility": float(vol),
                "strike": float(strike),
                "frtb_risk_class": FRTB_RISK_CLASS[ac],
                "dv01": float(dv01),
                "cs01": float(cs01),
                "vega": float(vega),
                "delta_eq": float(delta_eq),
                "delta_fx": float(delta_fx),
                "delta_comm": float(delta_comm),
            })
    underlying = pd.DataFrame(legs)
    return master, underlying, netting


# ---------------------------------------------------------------- 산출 함수

def saccr_input(master: pd.DataFrame, underlying: pd.DataFrame) -> pd.DataFrame:
    """`risk_lib.ccr.saccr_ead`가 그대로 받는 다리 단위 입력표 (CRE52.19-52.24).

    saccr_ead가 요구하는 컬럼은 counterparty/asset_class/notional/mtm/maturity/
    collateral 이다. 여기서 **notional 자리에는 총명목이 아니라 조정명목**을
    넣는다 — saccr_ead의 add-on은 SF × notional × MF 이므로, 총명목을 넣으면
    이자율 add-on이 감독듀레이션(5년 스왑 기준 약 4.4배)만큼 과소계상된다
    (CRE52.20). 감독델타는 절댓값으로 곱한다: saccr_ead는 헤징집합 내 부호
    상계를 하지 않으므로 부호를 살리면 매도가 매수를 잘못 상계한다(CRE52.30).

    시가·담보는 거래 단위 값이므로 명목 배분비로 다리에 나눠 담는다.
    saccr_ead가 거래상대방별로 합산하므로 배분 후 합계가 원본과 같아야 하며,
    아래에서 그것을 검증한다.

    한계(의도적): saccr_ead의 만기계수는 √min(M,1)로 **무증거금 기준**이다
    (CRE52.48). 증거금 거래의 1.5·√(MPOR) 계수는 적용되지 않으므로 증거금
    거래 EAD는 보수적으로 나온다. MPOR은 마스터에 보존되어 있어 완전한
    CRE52 엔진이 붙으면 그대로 쓸 수 있다.
    """
    m = master[["trade_id", "counterparty", "netting_set_id", "mtm", "collateral"]]
    u = underlying[["underlying_id", "trade_id", "leg_id", "asset_class",
                    "notional_share", "adjusted_notional", "supervisory_delta",
                    "end_years"]]
    df = u.merge(m, on="trade_id", how="left", validate="many_to_one")
    orphan = int(df["counterparty"].isna().sum())
    if orphan:
        raise ValueError(f"마스터에 없는 다리 {orphan}건 — 고아 레코드는 EAD에서 "
                         "조용히 누락된다")

    df["notional"] = df["adjusted_notional"] * df["supervisory_delta"].abs()
    df["mtm"] = df["mtm"] * df["notional_share"]
    df["collateral"] = df["collateral"] * df["notional_share"]
    df["maturity"] = df["end_years"].clip(lower=_MATURITY_FLOOR_YEARS)

    out = df[["underlying_id", "trade_id", "leg_id", "netting_set_id",
              "counterparty", "asset_class", "notional", "mtm", "maturity",
              "collateral"]].copy()

    unknown = set(out["asset_class"]) - set(SF)
    if unknown:
        raise ValueError(f"ccr.SF에 없는 자산군 {sorted(unknown)} — saccr_ead가 "
                         "KeyError로 죽는다")
    _assert_clean(out, "saccr_input")
    for col in ("mtm", "collateral"):
        got, want = float(out[col].sum()), float(master[col].sum())
        if not math.isclose(got, want, rel_tol=1e-9, abs_tol=1.0):
            raise AssertionError(f"{col} 배분 합계 불일치: {got:,.0f} ≠ {want:,.0f}")
    return out


def market_sensitivities(master: pd.DataFrame,
                         underlying: pd.DataFrame) -> pd.DataFrame:
    """FRTB 표준방법 위험군별 민감도 집계 — 델타·베가·커버처 입력 (MAR21).

    MAR21의 민감도 정의에 맞춰 단위를 환산한다:
      * GIRR 델타 = dv01 × 10,000 (금리 1.00 변동 기준, MAR21.8)
      * CSR  델타 = cs01 × 10,000 (MAR21.13)
      * EQ·FX·COMM 델타 = 1% 변동 민감도 × 100 (상대변동 기준, MAR21.9/14/15)
      * 베가 = (∂V/∂σ) × σ (MAR21.19). 원장의 vega는 1 vol point 기준이므로
        ×100×σ 한다.
      * 커버처 입력 = 옵션성 다리의 1% 기초자산 변동에 대한 2차 항.
        Black-Scholes 관계 Γ = (∂V/∂σ)/(P²στ) 에서 ½Γ(0.01P)² = vega·5e-3/(στ)
        로 역산한다. MAR21.5(b)의 CVR은 감독 위험가중 충격 하 **재평가**를
        요구하므로, 재평가기가 붙기 전까지는 1% 단위로 제공해 소비자가 위험가중
        충격 배수를 곱해 쓰게 한다.

    위험가중을 여기서 곱하지 않는 이유: MAR21 표준방법 위험가중표는 이 저장소에
    없고, `risk_lib.capital.market_risk.DEFAULT_RISK_WEIGHTS`는 **MAR40 간편법**
    계수라 SbM에 쓰면 틀린다. 없는 규제표를 지어내는 대신 민감도까지만 낸다.

    적용범위(mar_in_scope): 시장리스크 자본은 트레이딩북 전체와 뱅킹북의
    FX·상품 리스크에 적용된다 (MAR11.1). 범위 밖 행을 지우지 않고 플래그로
    남기는 이유는, 지우면 뱅킹북 파생 포지션이 어느 보고서에도 나타나지 않기
    때문이다.
    """
    df = underlying.merge(
        master[["trade_id", "book", "product_type"]],
        on="trade_id", how="left", validate="many_to_one")
    orphan = int(df["book"].isna().sum())
    if orphan:
        raise ValueError(f"마스터에 없는 다리 {orphan}건 — 민감도가 조용히 누락된다")

    rc = df["frtb_risk_class"]
    # 위험군별로 해당 민감도만 골라 MAR21 단위로 환산한다.
    delta = np.select(
        [rc == "GIRR", rc == "CSR", rc == "EQ", rc == "FX", rc == "COMM"],
        [df["dv01"] * 1e4, df["cs01"] * 1e4,
         df["delta_eq"] * 100.0, df["delta_fx"] * 100.0, df["delta_comm"] * 100.0],
        default=np.nan)
    if np.isnan(delta).any():
        raise ValueError("FRTB 위험군 사상 누락 — FRTB_RISK_CLASS 밖의 값이 있다")
    df["delta_krw"] = delta
    df["vega_krw"] = df["vega"] * 100.0 * df["volatility"]

    # 커버처: 옵션성 다리에만 존재한다 (MAR21.5(b)). σ·τ가 0인 선형 다리는 0.
    tau = np.maximum(df["end_years"].to_numpy(dtype=float), _MATURITY_FLOOR_YEARS)
    sigma = df["volatility"].to_numpy(dtype=float)
    is_opt = df["product_type"].isin(["option", "swaption"]).to_numpy() & (sigma > 0)
    df["curvature_krw"] = np.where(
        is_opt, df["vega"].to_numpy(dtype=float) * 5e-3 / np.maximum(sigma * tau, 1e-9),
        0.0)

    df["delta_abs_krw"] = df["delta_krw"].abs()
    grouped = (df.groupby(["asof", "frtb_risk_class", "book", "currency"],
                          as_index=False)
               .agg(n_trades=("trade_id", "nunique"),
                    n_legs=("underlying_id", "size"),
                    notional=("leg_notional", "sum"),
                    delta_krw=("delta_krw", "sum"),
                    delta_abs_krw=("delta_abs_krw", "sum"),
                    vega_krw=("vega_krw", "sum"),
                    curvature_krw=("curvature_krw", "sum")))

    grouped["sensitivity_id"] = (grouped["frtb_risk_class"] + "|"
                                 + grouped["book"] + "|" + grouped["currency"])
    grouped["mar_in_scope"] = ((grouped["book"] == "trading")
                               | grouped["frtb_risk_class"].isin(["FX", "COMM"]))
    out = grouped[["sensitivity_id", "asof", "frtb_risk_class", "book", "currency",
                   "mar_in_scope", "n_trades", "n_legs", "notional", "delta_krw",
                   "delta_abs_krw", "vega_krw", "curvature_krw"]].copy()
    out["n_trades"] = out["n_trades"].astype("int64")
    out["n_legs"] = out["n_legs"].astype("int64")
    _assert_clean(out, "mkt_derivative_sensitivity")
    return out.sort_values(["frtb_risk_class", "book", "currency"]).reset_index(drop=True)


# ---------------------------------------------------------------- 생성

def build_derivatives(*, asof: str, seed: int = 42) -> dict[str, pd.DataFrame]:
    """파생 원장 4표를 만든다. 키가 곧 테이블명이다.

    rdm_derivative_master      거래 1건 = 1행
    rdm_derivative_underlying  거래 × 다리 1건 = 1행
    rdm_netting_set            넷팅집합 1건 = 1행
    mkt_derivative_sensitivity FRTB 위험군 × 북 × 통화 1건 = 1행
    """
    master, underlying, netting = _synthesise(asof=asof, seed=seed)

    for name, df in (("rdm_derivative_master", master),
                     ("rdm_derivative_underlying", underlying),
                     ("rdm_netting_set", netting)):
        _assert_clean(df, name)

    # 규율 검증 — 합성 파라미터가 요구 범위를 벗어나면 조용히 넘기지 않는다.
    total_notional = float(master["notional"].sum())
    lo, hi = _NOTIONAL_TOTAL_RANGE
    if not lo <= total_notional <= hi:
        raise AssertionError(f"명목 총액 {total_notional:,.0f} KRW가 요구범위 밖")
    if not set(master["netting_set_id"]) <= set(netting["netting_set_id"]):
        raise AssertionError("마스터가 참조하는 넷팅집합이 원장에 없다")
    share_sum = underlying.groupby("trade_id")["notional_share"].sum()
    if not np.allclose(share_sum.to_numpy(), 1.0, atol=1e-9):
        raise AssertionError("다리 명목 배분비 합이 1이 아니다 — 명목이 새거나 부풀었다")

    sens = market_sensitivities(master, underlying)
    return {
        "rdm_derivative_master": master,
        "rdm_derivative_underlying": underlying,
        "rdm_netting_set": netting,
        "mkt_derivative_sensitivity": sens,
    }
