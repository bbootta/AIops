"""계약 원장 `alm_contract` — 현금흐름 엔진의 **입력 경계**.

**왜 이 원장이 있어야 하는가.** 현행 `balance_sheet.generate_balance_sheet`는
리프라이싱 사다리를 `asset_w = [0.06, 0.08, …]` 상수 벡터로 만들고
`portfolio['maturity']`를 쓰지 않는다. 그래서 포트폴리오의 만기 분포를 바꿔도
IRRBB가 미동하지 않는다 — 사다리가 포트폴리오의 함수가 아니기 때문이다.
계약 원장을 경계로 두면 엔진은 `alm_contract` + `alm_product_terms`만 읽고,
만기·금리·상환방식이 바뀌면 현금흐름이 반드시 따라 움직인다.

**합성이지 실측이 아니다(§5.17).** 원천 포트폴리오 28컬럼에는
`product_code`·`rate_type`·`origination_date`·`coupon_rate`·`amort_type`·
`day_count`·`ccy`가 **하나도 없다**. 그래서 이 원장은 합성한다. 합성이지만
`default_rng(seed + 1101)` 하나로만 뽑으므로 (asof, seed)가 같으면 비트 단위로
같다. 모든 행에 `source='synthetic'`이 붙어 실측과 섞이지 않는다.

**시드 오프셋 1101은 신규 전용이다.** `balance_sheet`(seed+101)·
`_lcr_path`(seed+2602)와 겹치면 기존 난수 스트림이 밀려 **무관한 산출이**
바뀐다 — 결정론 규약은 "재현된다"만이 아니라 "남의 것을 흔들지 않는다"도
포함한다.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from risk_lib.datamodel.spec import ColumnSpec as C, ForeignKey as FK, TableSpec
from risk_lib.alm.params import COUNTERPARTY_TYPES, SIDES

__all__ = ["CONTRACT", "FUNDING_PRODUCT_MAP", "build_contract_ledger"]

_RNG_OFFSET = 1101          # 신규 전용 — 기존 스트림과 겹치지 않는다


CONTRACT = TableSpec(
    name="alm_contract", korean="ALM 계약 원장", product="PRD-ALM",
    grain="기준일 × 금리민감 계약 1건당 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("contract_id", "string", "계약 식별자", nullable=False),
        C("exposure_id", "string", "익스포저 식별자", nullable=True,
          note="여신계약만 rdm_exposure에 대응한다 — 조달·자기자본은 NULL"),
        C("product_code", "string", "상품코드", nullable=False),
        C("side", "string", "측", nullable=False, allowed=SIDES),
        C("ccy", "string", "통화", nullable=False),
        C("notional", "float", "기준일 잔액", nullable=False, unit="KRW",
          min_value=0.0,
          note="최초 원금이 아니라 asof 현재 잔액 — ALM은 현재 대차대조표를 굴린다"),
        C("coupon_rate", "float", "약정금리(전액)", nullable=False, unit="ratio",
          note="마진 포함 올인 금리. margin_bp는 그 안의 상업마진 성분이다"),
        C("margin_bp", "float", "상업마진", nullable=False, unit="bp",
          citation="BCBS d368 §132(3) — ΔEVE는 현금흐름에서 상업마진 제외, "
                   "ΔNII는 포함(EBA GL 2022-14). 분리 저장해야 두 지표가 "
                   "같은 이름의 현금흐름을 다르게 쓰는 것이 보인다"),
        C("reference_rate", "string", "지표금리", nullable=True),
        C("origination_date", "date", "실행일", nullable=False,
          note="PSA 조기상환은 상품연령의 함수 — 실행일이 없으면 CPR이 정의되지 않는다"),
        C("maturity_date", "date", "만기일", nullable=True,
          note="비만기예금·자기자본은 NULL — 계약상 만기가 없다"),
        C("next_reset_date", "date", "차기 리프라이싱일", nullable=True,
          citation="BCBS d368 Annex 2 — 변동금리는 명목 전액을 차기 "
                   "리프라이싱일에 슬로팅한다"),
        C("counterparty_type", "string", "거래상대 구분", nullable=True,
          allowed=COUNTERPARTY_TYPES,
          citation="BCBS d368 Annex 2 Table 2 NMD 범주와 같은 어휘"),
        C("is_own_equity", "bool", "자기자본", nullable=False,
          citation="BCBS d368 §132 — 자기자본 미투자 가정, ΔEVE 현금흐름에서 제외"),
        C("prepay_fee_rate", "float", "중도상환수수료율", nullable=True,
          unit="ratio", min_value=0.0, max_value=1.0,
          citation="수수료 = 중도상환원금 × 요율 × 잔존일수/약정일수 "
                   "(최장 3년 슬라이딩) — 국내 은행 공시 산식"),
        C("prepay_fee_term_years", "float", "수수료 부과기간", nullable=True,
          unit="years", min_value=0.0),
        C("source", "string", "원천", nullable=False,
          allowed=("synthetic", "core_banking", "general_ledger")),
    ),
    primary_key=("asof", "contract_id"),
    foreign_keys=(FK(("product_code",), "alm_product_terms", ("product_code",)),),
    note="엔진은 이 표와 alm_product_terms만 읽는다. 포트폴리오 DataFrame을 "
         "직접 읽지 않는 것이 경계의 요점이다.",
)


# 자산군 → 상품코드. 고정/변동 분리가 있는 자산군은 (고정, 변동, 고정비중).
# 비중 자체가 합성이다 — 원천에 rate_type이 없다(§5.17).
_ASSET_PRODUCT: dict[str, tuple[str, str, float]] = {
    "corporate":           ("LN_CORP_FIX", "LN_CORP_FLT", 0.35),
    "retail_other":        ("LN_RETAIL",   "LN_RETAIL",   0.00),
    "residential_mortgage": ("LN_MTG_FIX", "LN_MTG_FLT",  0.40),
    "bank":                ("LN_BANK",     "LN_BANK",     0.00),
    "sovereign":           ("LN_SOV",      "LN_SOV",      1.00),
}

_HQLA_PRODUCT = {"level_1": "SEC_HQLA_L1", "level_2a": "SEC_HQLA_L2A",
                 "level_2b": "SEC_HQLA_L2B"}

# 조달 카테고리 → 상품코드 **1:1**. 한 카테고리를 여러 상품으로 쪼개려면 분할
# 비율이 필요한데 그 비율의 근거가 없다 — 1:1로 두면 지어낼 것이 없다.
#
# 관찰: `balance_sheet.funding`에 **소매 정기예금 카테고리가 없다**. 그래서
# 상품 카탈로그의 DEP_TERM_RT는 잔액 0으로 남는다. 이것은 이 빌더의 결함이
# 아니라 조달 원장의 공백이며, 국내 은행 부채의 큰 축이 ALM 입력에서 빠져
# 있다는 뜻이다. 조달 원장이 생기면 여기 한 줄이 늘어난다.
FUNDING_PRODUCT_MAP: dict[str, tuple[str, str | None]] = {
    # 조달 카테고리: (상품코드, NMD 범주 or None=만기부)
    "retail_stable":             ("DEP_NMD_RT",   "retail_transactional"),
    "retail_less_stable":        ("DEP_NMD_RNT",  "retail_non_transactional"),
    "corporate_operational":     ("DEP_NMD_WNF",  "wholesale_nonfin"),
    "corporate_non_operational": ("DEP_TERM_CORP", None),
    "wholesale_fi_lt6m":         ("DEP_NMD_FI",   "financial"),
    "wholesale_fi_6to12m":       ("FUND_WS_ST",   None),
    "funding_gt1y":              ("FUND_WS_LT",   None),
}

# 만기부 조달의 잔존만기 범위(년). 카테고리 이름이 이미 만기를 규정하므로
# 범위는 그 정의에서 나온다 — 임의로 고른 값이 아니다.
_FUNDING_TENOR: dict[str, tuple[float, float]] = {
    "corporate_non_operational": (0.25, 1.00),
    "wholesale_fi_6to12m":       (0.50, 1.00),   # 정의상 6~12개월
    "funding_gt1y":              (1.00, 5.00),   # 정의상 1년 초과
}
_N_FUNDING_TRANCHES = 8      # 만기부 조달 1카테고리당 트랜치 수


def _iso(d: date) -> str:
    return d.isoformat()


def _years_to_date(base: date, years: float) -> date:
    """연 단위 잔존기간을 날짜로. 365.25일/년 — 산출 전반과 같은 환산."""
    return base + timedelta(days=int(round(max(years, 1 / 365.25) * 365.25)))


def build_contract_ledger(
    portfolio: pd.DataFrame,
    *,
    asof: str,
    funding: dict[str, float],
    hqla: dict[str, float],
    equity: float,
    base_rate: float,
    seed: int = 42,
) -> pd.DataFrame:
    """포트폴리오·조달구성에서 계약 원장을 합성한다.

    `base_rate`는 **필수 인자**다. 함수 기본값으로 숨기면 현행 `compute_irrbb`가
    `base_rate=0.03`을 기본값으로 갖고 파이프라인이 인자를 넘기지 않아 평면
    3% 곡선이 조용히 쓰이던 상황이 그대로 재현된다. `curve.py`가
    `mkt_risk_factor` 제로커브를 연결하면 이 인자는 커브로 대체된다.
    """
    rng = np.random.default_rng(seed + _RNG_OFFSET)
    asof_d = date.fromisoformat(asof)
    rows: list[dict] = []

    # ---- 1. 여신계약: 포트폴리오 1행 = 계약 1건 ----------------------------
    pf = portfolio.reset_index(drop=True)
    n = len(pf)
    u_fixed = rng.random(n)          # 고정/변동 배정
    u_orig = rng.random(n)           # 실행일(경과기간)
    u_spread = rng.random(n)         # 대출 스프레드
    u_reset = rng.random(n)          # 차기 리프라이싱 시점
    for i in range(n):
        ac = str(pf.at[i, "asset_class"])
        fix_code, flt_code, fix_share = _ASSET_PRODUCT[ac]
        is_fixed = u_fixed[i] < fix_share
        code = fix_code if is_fixed else flt_code
        mat_years = float(pf.at[i, "maturity"])
        # 실행일: 잔존만기가 짧을수록 이미 오래 굴러간 계약일 개연이 높다.
        # 경과기간을 잔존만기에 비례시키면 PSA 상품연령이 만기와 정합한다.
        age_years = float(u_orig[i]) * max(mat_years, 0.5)
        spread = 0.005 + 0.03 * float(u_spread[i])
        rows.append({
            "contract_id": f"LN{i + 1:06d}",
            "exposure_id": str(pf.at[i, "exposure_id"]),
            "product_code": code, "side": "asset", "ccy": "KRW",
            "notional": float(pf.at[i, "ead"]),
            "coupon_rate": base_rate + spread,
            "margin_bp": spread * 1e4,
            "reference_rate": None if is_fixed else "KORIBOR_3M",
            "origination_date": _iso(asof_d - timedelta(
                days=int(round(age_years * 365.25)))),
            "maturity_date": _iso(_years_to_date(asof_d, mat_years)),
            "next_reset_date": None if is_fixed else _iso(_years_to_date(
                asof_d, float(u_reset[i]) * 0.25 + 1 / 365.25)),
            "counterparty_type": None,
            "is_own_equity": False,
            # 중도상환수수료는 주담대에만 부과된다(국내 관행). 구조(3년 슬라이딩)는
            # 공시 산식이고 요율 1.2%는 합성값이다.
            "prepay_fee_rate": 0.012 if code.startswith("LN_MTG") else None,
            "prepay_fee_term_years": 3.0 if code.startswith("LN_MTG") else None,
        })

    # ---- 2. HQLA 채권: 등급별 트랜치 -------------------------------------
    for lvl, amount in hqla.items():
        code = _HQLA_PRODUCT[lvl]
        k = 4
        tenors = rng.uniform(0.5, 8.0, k)
        cps = rng.uniform(0.0, 0.010, k)
        for j in range(k):
            rows.append({
                "contract_id": f"SEC_{lvl.upper()}_{j + 1:02d}",
                "exposure_id": None, "product_code": code,
                "side": "asset", "ccy": "KRW",
                "notional": float(amount) / k,
                "coupon_rate": base_rate + float(cps[j]),
                "margin_bp": 0.0,          # 채권은 상업마진이 없다
                "reference_rate": None,
                "origination_date": _iso(asof_d - timedelta(days=365)),
                "maturity_date": _iso(_years_to_date(asof_d, float(tenors[j]))),
                "next_reset_date": None, "counterparty_type": None,
                "is_own_equity": False,
                "prepay_fee_rate": None, "prepay_fee_term_years": None,
            })

    # ---- 3. 조달: NMD는 1건, 만기부는 트랜치 ------------------------------
    for cat, amount in funding.items():
        if cat not in FUNDING_PRODUCT_MAP:
            raise KeyError(
                f"조달 카테고리 {cat!r}에 대응하는 ALM 상품이 없다. "
                "FUNDING_PRODUCT_MAP에 등재하지 않으면 이 잔액은 현금흐름에서 "
                "조용히 사라진다.")
        code, nmd_cat = FUNDING_PRODUCT_MAP[cat]
        if nmd_cat is not None:
            # 비만기예금 — 계약상 만기가 없으므로 maturity_date는 NULL이다.
            rows.append({
                "contract_id": f"DEP_{cat.upper()}",
                "exposure_id": None, "product_code": code,
                "side": "liability", "ccy": "KRW",
                "notional": float(amount),
                "coupon_rate": max(base_rate - 0.020, 0.0),
                "margin_bp": -200.0,       # 예금은 지표금리 아래로 조달한다
                "reference_rate": None,
                "origination_date": _iso(asof_d - timedelta(days=365)),
                "maturity_date": None, "next_reset_date": None,
                "counterparty_type": nmd_cat, "is_own_equity": False,
                "prepay_fee_rate": None, "prepay_fee_term_years": None,
            })
            continue
        lo, hi = _FUNDING_TENOR[cat]
        tenors = rng.uniform(lo, hi, _N_FUNDING_TRANCHES)
        for j in range(_N_FUNDING_TRANCHES):
            rows.append({
                "contract_id": f"FND_{cat.upper()}_{j + 1:02d}",
                "exposure_id": None, "product_code": code,
                "side": "liability", "ccy": "KRW",
                "notional": float(amount) / _N_FUNDING_TRANCHES,
                "coupon_rate": max(base_rate - 0.005, 0.0),
                "margin_bp": -50.0, "reference_rate": None,
                "origination_date": _iso(asof_d - timedelta(days=180)),
                "maturity_date": _iso(_years_to_date(asof_d, float(tenors[j]))),
                "next_reset_date": None, "counterparty_type": None,
                "is_own_equity": False,
                "prepay_fee_rate": None, "prepay_fee_term_years": None,
            })

    # ---- 4. 자기자본 -----------------------------------------------------
    # 컬럼으로 두는 이유: 제외에 대한 반론과 감독 재량 여지가 있어 포함/제외
    # 두 산출을 대조할 수 있어야 한다(설계 §1.5).
    rows.append({
        "contract_id": "OWN_EQUITY", "exposure_id": None,
        "product_code": "OWN_EQUITY", "side": "liability", "ccy": "KRW",
        "notional": float(equity), "coupon_rate": 0.0, "margin_bp": 0.0,
        "reference_rate": None,
        "origination_date": _iso(asof_d - timedelta(days=365)),
        "maturity_date": None, "next_reset_date": None,
        "counterparty_type": None, "is_own_equity": True,
        "prepay_fee_rate": None, "prepay_fee_term_years": None,
    })

    df = pd.DataFrame(rows)
    df.insert(0, "asof", asof)
    df["source"] = "synthetic"
    return df.astype({"prepay_fee_rate": "float64",
                      "prepay_fee_term_years": "float64"})
