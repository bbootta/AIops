"""유동화 익스포저 원장 — 딜 마스터 · 트렌치 · 기초자산 풀 (Basel III CRE40~45).

무엇인가
--------
은행이 보유한 유동화 익스포저(ABS·RMBS·CLO·CDO 트렌치)를 세 개의 정규 원장으로
나눈 것이다.

  rdm_sec_master    유동화 거래(딜) 1건당 1행 — 거래 유형·기초자산군·재유동화·STC
  rdm_sec_tranche   딜 × 트렌치 1건당 1행 — A/D·두께·등급·만기·선순위·보유금액
  rdm_sec_pool      딜 × 기초자산 풀 세그먼트 1건당 1행 — PD·LGD·연체율·K_IRB·K_SA

왜 세 개인가
------------
유동화는 **같은 기초자산에서 트렌치마다 다른 자본**이 나오는 유일한 자산군이다.
같은 풀에 붙은 Equity는 1250%, Senior는 15%가 될 수 있다. 그 차이를 만드는 것은
(가) 풀의 자본요구율 K(딜 단위)와 (나) 트렌치의 A/D 위치(트렌치 단위)이므로,
두 입도를 한 평면 테이블에 담으면 풀 통계가 트렌치 수만큼 중복되고 그 순간부터
같은 딜의 K_SA가 행마다 달라질 수 있다. 세 방법(SEC-IRBA/ERBA/SA)이 요구하는
입력의 입도도 서로 다르다 — IRBA는 풀 단위 K_IRB, ERBA는 트렌치 단위 외부등급,
SA는 풀 단위 K_SA + 연체비율이다.

무엇을 가능하게 하는가
----------------------
  sec_sa_rwa()     CRE41 — K_A = (1−W)·K_SA + W·0.5 를 SSFA 에 넣어 트렌치별 RW
  sec_erba_rwa()   CRE42 — 외부등급 × 선순위 × 만기(1y/5y 보간) 표 조회
  sec_irba_rwa()   CRE43/44 — 풀 K_IRB 기반 SSFA, 감독 파라미터 p 는 CRE44.5 식
  sec_rwa_summary() 세 방법을 나란히 두고 CRE40.41 계층대로 채택 + 사유 기록
  sec_pool_stats()  딜 단위 풀 통계(K_SA·W·K_IRB·LGD·유효건수) — 위 셋의 공통 입력

계층 (CRE40.41)
---------------
  재유동화             → SEC-SA 강제 (CRE41.19). IRBA·ERBA 사용 불가.
  K_IRB 산출 가능      → SEC-IRBA
  외부등급 있음        → SEC-ERBA
  둘 다 불가           → SEC-SA

SEC-SA 는 항상 산출 가능하므로 계층의 바닥이며, 그래서 채택값에 NaN 이 남지
않는다. 반대로 ERBA·IRBA 는 **입력이 없으면 NaN 이 정답**이다 — 0 으로 채우면
"위험 없음"으로 읽히고, 1250%로 채우면 쓰지도 않을 방법 때문에 비교표가 왜곡된다.

범위 밖(명시)
-------------
* **STC 우대 ERBA 표(CRE42 대체표) 미반영.** STC 우대는 SEC-SA 의 p=0.5,
  SEC-IRBA 의 p 반감, 선순위 하한 10% 로만 반영한다. ERBA 는 일반표를 그대로
  쓰므로 STC 딜의 ERBA 위험가중치는 **보수적으로 과대**하다. 조용히 빠뜨린 것이
  아니라, 확인되지 않은 표를 규정 인용과 함께 코드에 적는 것보다 보수적 적용을
  택한 것이다.
* **선순위 look-through 상한(CRE40.50)과 최대자본요구(CRE40.51) 미반영.**
  기초자산을 직접 보유했을 때의 가중평균 위험가중치를 상한으로 두는 완화 규정이며,
  미적용은 자본을 줄이지 않는 방향(보수적)이다.
* **SA-CCR 미적용.** 기초자산이 대출채권이라 파생 거래상대방리스크가 없다.
  `risk_lib.ccr.saccr_ead` 는 이 원장의 대상이 아니다.

결정론
------
모든 합성은 `np.random.default_rng(seed + 고유오프셋)` 으로만 뽑는다. 같은
(asof, seed) 이면 비트 단위로 같은 산출이 나오며 시각 의존 코드는 없다.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

# SA 위험가중치 표와 IRB 자본요구식은 이미 자본 모듈이 갖고 있다. 여기에 다시
# 적으면 규제 개정 때 한쪽만 고쳐지므로 함수째로 import 해서 쓴다.
from risk_lib.capital.rwa_irb import irb_capital_requirement
from risk_lib.capital.rwa_sa import sa_risk_weight
from risk_lib.references import BIS_MIN_TOTAL

__all__ = [
    "APPROACHES",
    "POOL_ASSET_CLASSES",
    "RATINGS",
    "SEC_TYPES",
    "TRANCHE_TYPES",
    "RW_CAP",
    "RW_FLOOR",
    "RW_FLOOR_RESEC",
    "RW_FLOOR_STC_SENIOR",
    "applicable_approach",
    "erba_risk_weight",
    "build_securitisation",
    "sec_erba_rwa",
    "sec_irba_rwa",
    "sec_pool_stats",
    "sec_rwa_summary",
    "sec_sa_rwa",
    "tranche_rw_floor",
]


# ---------------------------------------------------------------- 어휘

SEC_TYPES: tuple[str, ...] = ("전통적", "합성")

# 기초자산군. 유동화 유형이 아니라 **풀의 성격**이며 K_IRB 상관계수와 SA
# 위험가중치가 여기서 갈린다.
POOL_ASSET_CLASSES: tuple[str, ...] = (
    "주택담보대출", "기업대출", "신용카드", "오토론", "CDO")

TRANCHE_TYPES: tuple[str, ...] = ("Senior", "Mezzanine", "Equity")

APPROACHES: tuple[str, ...] = ("SEC-IRBA", "SEC-ERBA", "SEC-SA")

# CRE42 장기 외부등급 버킷. "CCC" 는 CCC+/CCC/CCC− 를 묶은 감독 버킷이고
# "BELOW-CCC" 는 CCC− 미만, "NR" 은 무등급이다. NR 은 등급 부재를 **문자열로**
# 명시한다 — 등급 컬럼을 NaN 으로 두면 "값이 없다"와 "무등급 판정"이 구분되지
# 않는다. 위험가중치는 그때 NaN 이 된다.
RATINGS: tuple[str, ...] = (
    "AAA", "AA+", "AA", "AA-", "A+", "A", "A-",
    "BBB+", "BBB", "BBB-", "BB+", "BB", "BB-",
    "B+", "B", "B-", "CCC", "BELOW-CCC", "NR")


# ---------------------------------------------------------------- 감독 상수

# 위험가중치 상한 1250% (CRE40.2). 자기자본 8% 기준에서 익스포저 전액을 자본으로
# 덮는 수준(12.5 × 8% = 100%)이며 그 위는 의미가 없다.
RW_CAP = 12.5

# 위험가중치 하한 15% (CRE41.16 · CRE42.2 · CRE43.4). 트렌치가 아무리 두껍고
# 선순위여도 유동화 구조 자체의 모형위험·상관위험 때문에 0 으로 가지 못한다.
RW_FLOOR = 0.15

# STC(단순·투명·비교가능) 요건 충족 거래의 **선순위** 트렌치 하한 10%
# (CRE40.44 우대 적용). 비선순위는 STC 라도 15% 하한 그대로다.
RW_FLOOR_STC_SENIOR = 0.10

# 재유동화 익스포저의 위험가중치 하한 100% (CRE41.19). 15% 가 아니다 —
# p=1.5 만으로는 두껍고 붙임점이 높은 재유동화 선순위 트렌치의 SSFA 값이
# 일반 유동화 수준까지 내려가는데, 규정은 그 지점을 100% 로 막는다.
# 재유동화는 STC 요건을 충족할 수 없으므로 STC 하한과 겹치지 않는다.
RW_FLOOR_RESEC = 1.00

# SEC-SA 감독 파라미터 p (CRE41.14). 재유동화는 1.5 로 가중되고, STC 는 0.5 로
# 완화된다. p 가 커질수록 SSFA 곡선이 완만해져 자본이 늘어난다.
P_SA = 1.0
P_SA_RESEC = 1.5
P_SA_STC = 0.5

# SEC-IRBA p 하한 0.3 (CRE44.5). STC 우대로 p 를 반감해도 이 하한 아래로는
# 내려가지 않는다.
P_IRBA_FLOOR = 0.30

# 재유동화의 연체비율 W 는 0 으로 둔다 (CRE41.19(2)). 기초가 유동화 트렌치라
# 차주 연체 개념이 없고, 대신 p=1.5 로 벌칙을 준다.
W_RESEC = 0.0

# 트렌치 만기 MT 의 하한·상한 (CRE42.5). **CRE31.6 의 IRB 만기 하한·상한과는
# 다른 규정**이다 — 값이 우연히 같을 뿐이므로 references 의 IRB 상수를 끌어다
# 쓰지 않는다. 한쪽이 개정될 때 다른 쪽이 조용히 따라 움직이면 안 된다.
MT_FLOOR_YEARS = 1.0
MT_CAP_YEARS = 5.0

# SEC-IRBA 입도 기준 (CRE44.5). 유효 익스포저 건수 N 이 25 미만이면 비입도
# 계수표를 쓴다 — 소수 대형 차주 풀은 분산이 덜 되어 p 가 커진다.
GRANULARITY_THRESHOLD = 25.0

# SEC-IRBA 는 풀의 대부분에 대해 K_IRB 를 산출할 수 있어야 쓸 수 있다
# (CRE44.2 — 기초자산의 95% 이상). 본 원장은 딜 단위 승인 플래그로 다루되,
# 세그먼트 K_IRB 가 하나라도 비면 딜 전체를 산출 불가로 본다.
IRB_POOL_COVERAGE_MIN = 0.95


# CRE42.2 장기 외부등급 위험가중치 표 (십진).
#   등급 → (선순위 1년, 선순위 5년, 비선순위 1년, 비선순위 5년)
# 1년·5년 사이는 선형보간하고(CRE42.4), 비선순위는 두께 조정을 추가로 받는다
# (CRE42.3). 표를 손대면 두 축(선순위/만기)이 함께 움직이므로 원문 대조 필수.
_ERBA_LONG_TERM: dict[str, tuple[float, float, float, float]] = {
    "AAA":       (0.15, 0.20, 0.15, 0.70),
    "AA+":       (0.15, 0.30, 0.15, 0.90),
    "AA":        (0.25, 0.40, 0.30, 1.20),
    "AA-":       (0.30, 0.45, 0.40, 1.40),
    "A+":        (0.40, 0.50, 0.60, 1.60),
    "A":         (0.50, 0.65, 0.80, 1.80),
    "A-":        (0.60, 0.70, 1.20, 2.10),
    "BBB+":      (0.75, 0.90, 1.70, 2.60),
    "BBB":       (0.90, 1.05, 2.20, 3.10),
    "BBB-":      (1.20, 1.40, 3.30, 4.20),
    "BB+":       (1.40, 1.60, 4.70, 5.80),
    "BB":        (1.60, 1.80, 6.20, 7.60),
    "BB-":       (2.00, 2.25, 7.50, 8.60),
    "B+":        (2.50, 2.80, 9.00, 9.50),
    "B":         (3.10, 3.40, 10.50, 10.50),
    "B-":        (3.80, 4.20, 11.30, 11.30),
    "CCC":       (4.60, 5.05, 12.50, 12.50),
    "BELOW-CCC": (12.50, 12.50, 12.50, 12.50),
}

# 등급 어휘가 표와 어긋나면 조용히 NaN 이 늘어난다. import 시점에 막는다.
_RATING_GAP = (set(RATINGS) - {"NR"}) ^ set(_ERBA_LONG_TERM)
if _RATING_GAP:
    raise ImportError(f"등급 어휘가 CRE42 표와 어긋난다: {sorted(_RATING_GAP)}")


# CRE44.5 SEC-IRBA 감독 파라미터 p 의 계수.
#   p = max(0.3, A + B·(1/N) + C·K_IRB + D·LGD + E·MT)
# 키: (소매 여부, 선순위 여부, 입도 여부). 소매는 B=0 이라 입도가 p 에 영향을
# 주지 않으므로 입도 축을 두지 않는다.
_PCoef = tuple[float, float, float, float, float]
_P_COEFF_WHOLESALE: dict[tuple[bool, bool], _PCoef] = {
    # (선순위, 입도(N≥25))
    (True, True):   (0.00, 3.56, -1.85, 0.55, 0.07),
    (True, False):  (0.11, 2.61, -2.91, 0.68, 0.07),
    (False, True):  (0.16, 2.87, -1.03, 0.21, 0.07),
    (False, False): (0.22, 2.35, -2.46, 0.48, 0.07),
}
_P_COEFF_RETAIL: dict[bool, _PCoef] = {
    True:  (0.00, 0.00, -7.48, 0.71, 0.24),   # 선순위
    False: (0.00, 0.00, -5.78, 0.55, 0.27),   # 비선순위
}

# IRB 소매 자산군 (CRE30.24~30.27). p 계수표의 소매/도매 분기에 쓴다.
_IRB_RETAIL_CLASSES = frozenset(
    {"residential_mortgage", "retail_revolving", "retail_other"})


# ---------------------------------------------------------------- 공통 도우미

def _validate_asof(asof: str) -> str:
    # 기준일이 문자열 규격을 벗어나면 하류 조인이 조용히 어긋난다.
    datetime.strptime(asof, "%Y-%m-%d")
    return asof


def _require_columns(df: pd.DataFrame, cols: tuple[str, ...], name: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"{name}에 필수 컬럼이 없다: {missing}")


def _clip_mt(mt: float) -> float:
    """트렌치 만기 MT 를 1~5년으로 절단 (CRE42.5)."""
    return float(min(max(float(mt), MT_FLOOR_YEARS), MT_CAP_YEARS))


def tranche_rw_floor(*, stc: bool, senior: bool,
                     resecuritisation: bool = False) -> float:
    """트렌치에 적용할 위험가중치 하한.

    재유동화 100% (CRE41.19) > STC 선순위 10% (CRE40.44) > 일반 15% (CRE41.16).
    재유동화와 STC 는 동시에 성립하지 않으므로 순서 다툼은 없다.
    """
    if resecuritisation:
        return RW_FLOOR_RESEC
    return RW_FLOOR_STC_SENIOR if (stc and senior) else RW_FLOOR


def applicable_approach(*, resecuritisation: bool, irb_available: bool,
                        rated: bool) -> tuple[str, str]:
    """CRE40.41 계층에 따른 (적용방법, 사유).

    딜 단위(마스터)와 트렌치 단위(요약)가 **같은 함수**를 쓴다. 계층 규칙을 두
    곳에 적으면 둘 중 하나는 틀릴 준비가 된 것이다.
    """
    if resecuritisation:
        return ("SEC-SA",
                "CRE41.19 재유동화 — SEC-IRBA·SEC-ERBA 사용 불가, SEC-SA(p=1.5) 강제")
    if irb_available:
        return ("SEC-IRBA", "CRE40.41 1순위 — 기초자산 K_IRB 산출 가능")
    if rated:
        return ("SEC-ERBA", "CRE40.41 2순위 — K_IRB 산출 불가, 외부등급 이용 가능")
    return ("SEC-SA", "CRE40.41 3순위 — K_IRB·외부등급 모두 불가")


def _k_ssfa(*, attach: float, detach: float, k: float, p: float) -> float:
    """SSFA 의 K_SSFA (CRE41.15 · CRE43.4).

        a = −1/(p·K),  u = D − K,  l = max(A − K, 0)
        K_SSFA = (e^{au} − e^{al}) / (a·(u − l))

    a<0 이므로 지수는 항상 아래로 유계다(오버플로 없음). u≤l 은 D≤K 인 경우뿐이며
    호출부가 먼저 걸러낸다.
    """
    if k <= 0.0:
        raise ValueError(f"K가 0 이하다: {k} — SSFA 정의 불가")
    if p <= 0.0:
        raise ValueError(f"p가 0 이하다: {p}")
    a = -1.0 / (p * k)
    u = detach - k
    l = max(attach - k, 0.0)
    if u <= l:
        raise ValueError(f"u<=l (D={detach}, A={attach}, K={k}) — 호출부가 D<=K를 걸러야 한다")
    return float((math.exp(a * u) - math.exp(a * l)) / (a * (u - l)))


def _ssfa_risk_weight(*, attach: float, detach: float, k: float, p: float,
                      floor: float) -> tuple[float, float, float, bool]:
    """SSFA 위험가중치 (CRE41.16 · CRE43.4).

    반환: (K_SSFA, 하한 전 RW, 최종 RW, 하한적용여부).
    D≤K 구간은 K_SSFA 가 정의되지 않으므로 NaN 으로 남긴다 — 0 으로 채우면
    감사에서 "왜 1250%인가"를 설명할 수 없다.
    """
    if not (0.0 <= attach < detach <= 1.0):
        raise ValueError(f"A/D가 [0,1] 오름차순이 아니다: A={attach}, D={detach}")

    if detach <= k:
        # 트렌치 전체가 풀 자본요구 아래 — 손실을 먼저 다 맞는다 (CRE41.16(1)).
        kss = float("nan")
        raw = RW_CAP
    else:
        kss = _k_ssfa(attach=attach, detach=detach, k=k, p=p)
        if attach >= k:
            raw = kss * RW_CAP                                   # CRE41.16(2)
        else:
            # A < K < D — 트렌치가 K 선을 걸친다. K 아래 부분은 1250%,
            # 위 부분은 SSFA 로 가중평균한다 (CRE41.16(3)).
            below = (k - attach) / (detach - attach)
            raw = below * RW_CAP + (1.0 - below) * RW_CAP * kss

    raw = float(min(raw, RW_CAP))
    final = float(max(raw, floor))
    return kss, raw, final, bool(final > raw)


def erba_risk_weight(rating: str, *, senior: bool, mt: float,
                     thickness: float) -> tuple[float, str]:
    """CRE42 외부등급법 위험가중치 (하한 적용 전).

    반환: (위험가중치, 사유). 등급이 없으면 (NaN, 사유) — 0 으로 채우지 않는다.
    """
    if rating not in _ERBA_LONG_TERM:
        return (float("nan"),
                f"외부등급 없음({rating}) — CRE42 SEC-ERBA 산출 불가")

    mt_c = _clip_mt(mt)
    s1, s5, n1, n5 = _ERBA_LONG_TERM[rating]
    lo, hi = (s1, s5) if senior else (n1, n5)
    # 1년·5년 사이 선형보간 (CRE42.4). MT 는 이미 [1,5] 로 절단돼 있다.
    rw = lo + (hi - lo) * (mt_c - MT_FLOOR_YEARS) / (MT_CAP_YEARS - MT_FLOOR_YEARS)

    note = (f"CRE42.2 {rating}/{'선순위' if senior else '비선순위'}, "
            f"MT={mt_c:.2f}y 보간")
    if not senior:
        # 비선순위 두께 조정 (CRE42.3): 얇은 트렌치일수록 손실이 집중되므로
        # 두꺼운 트렌치의 위험가중치를 낮춰준다. 조정률 상한 50%.
        adj = 1.0 - min(thickness, 0.50)
        rw *= adj
        note += f" · 두께조정 ×{adj:.3f}(T={thickness:.4f})"

    return float(min(rw, RW_CAP)), note


# ---------------------------------------------------------------- 풀 통계

_POOL_REQUIRED = ("deal_id", "segment_id", "balance", "n_exposures",
                  "wa_lgd", "delinquency_rate", "k_irb", "sa_risk_weight",
                  "irb_asset_class")


def sec_pool_stats(pool: pd.DataFrame) -> pd.DataFrame:
    """딜 단위 기초자산 풀 통계 — 세 산출방법의 공통 입력.

    컬럼
      pool_balance    풀 잔액 합계
      k_sa            CRE41.13 — 8% × 잔액가중 SA 위험가중치
      w_delinquency   CRE41.13 — 연체 익스포저 잔액 비율
      k_irb           CRE44.2 — 잔액가중 IRB 자본요구율(EL 포함).
                      세그먼트가 하나라도 비면 NaN (풀 95% 커버리지 미충족)
      pool_lgd        CRE44.5 p 식의 LGD — 잔액가중 평균
      n_exposures     기초자산 건수 합계
      effective_n     CRE44.6 유효 건수 N = (ΣE)² / Σ(E_s²/n_s)
      is_retail       소매 풀 여부(잔액 과반) — p 계수표 분기
    """
    _require_columns(pool, _POOL_REQUIRED, "pool")
    if pool.empty:
        raise ValueError("pool이 비었다 — 풀 통계 산출 불가")

    rows: list[dict[str, Any]] = []
    for deal_id, g in pool.groupby("deal_id", sort=True):
        bal = float(g["balance"].sum())
        if bal <= 0.0:
            raise ValueError(f"{deal_id}: 풀 잔액 합계가 0 이하다")

        k_sa = float((g["balance"] * g["sa_risk_weight"]).sum() / bal) * BIS_MIN_TOTAL
        w = float((g["balance"] * g["delinquency_rate"]).sum() / bal)

        # K_IRB 는 풀 전체에 대해 나와야 쓸 수 있다 (CRE44.2). 일부만 있는 채로
        # 가중평균하면 IRB 미승인 부분이 조용히 빠져 자본이 과소산정된다.
        if g["k_irb"].isna().any():
            k_irb = float("nan")
            pool_lgd = float("nan")
        else:
            k_irb = float((g["balance"] * g["k_irb"]).sum() / bal)
            pool_lgd = float((g["balance"] * g["wa_lgd"]).sum() / bal)

        # 유효 건수: 세그먼트 내 익스포저가 균등하다고 보면
        # Σ E_i² = Σ_s (E_s²/n_s) 이므로 N = (ΣE_s)² / Σ(E_s²/n_s) (CRE44.6).
        # 건수 0 을 막지 않으면 분모가 inf 가 되어 N=0 으로 조용히 떨어지고,
        # 입도 판정(N≥25)이 뒤집혀 CRE44.5 의 p 가 통째로 틀린다.
        if (g["n_exposures"] <= 0).any() or g["n_exposures"].isna().any():
            raise ValueError(f"{deal_id}: 세그먼트 익스포저 건수가 0 이하이거나 비어 있다")
        denom = float(((g["balance"] ** 2) / g["n_exposures"]).sum())
        if denom <= 0.0:
            raise ValueError(f"{deal_id}: 유효 건수 분모가 0 이하다")
        effective_n = bal * bal / denom

        retail_bal = float(
            g.loc[g["irb_asset_class"].isin(_IRB_RETAIL_CLASSES), "balance"].sum())

        rows.append({
            "deal_id": deal_id,
            "pool_balance": bal,
            "k_sa": k_sa,
            "w_delinquency": w,
            "k_irb": k_irb,
            "pool_lgd": pool_lgd,
            "n_exposures": int(g["n_exposures"].sum()),
            "effective_n": float(effective_n),
            "retail_share": retail_bal / bal,
            "is_retail": bool(retail_bal / bal > 0.5),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- SEC-SA

_MASTER_REQUIRED = ("deal_id", "asof", "resecuritisation",
                    "simple_transparent_comparable")
_TRANCHE_REQUIRED = ("tranche_id", "deal_id", "asof", "attachment_point",
                     "detachment_point", "thickness", "holding_amount",
                     "external_rating", "residual_maturity_years", "senior")


def sec_sa_rwa(master: pd.DataFrame, tranche: pd.DataFrame,
               pool: pd.DataFrame) -> pd.DataFrame:
    """CRE41 표준방법(SEC-SA) 트렌치별 위험가중치·RWA.

        K_A = (1 − W)·K_SA + W·0.5      (CRE41.13)
        p   = 1 (비재유동화) / 1.5 (재유동화) / 0.5 (STC)   (CRE41.14)

    K_A 의 W·0.5 항은 연체 익스포저를 50% 자본요구로 간주하는 벌칙이다. 재유동화는
    W=0 으로 두는 대신 p 로 벌칙을 준다 (CRE41.19).

    SEC-SA 는 K_SA 만 있으면 항상 산출되므로 계층의 바닥이며, 결과에 NaN 이
    남으면 그것은 원장이 깨진 것이다.
    """
    _require_columns(master, _MASTER_REQUIRED, "master")
    _require_columns(tranche, _TRANCHE_REQUIRED, "tranche")

    stats = sec_pool_stats(pool).set_index("deal_id")
    m = master.set_index("deal_id")

    rows: list[dict[str, Any]] = []
    for t in tranche.to_dict("records"):
        deal_id = t["deal_id"]
        if deal_id not in m.index:
            raise ValueError(f"{t['tranche_id']}: 마스터에 없는 deal_id={deal_id}")
        if deal_id not in stats.index:
            raise ValueError(f"{t['tranche_id']}: 기초자산 풀이 없는 deal_id={deal_id}")
        d = m.loc[deal_id]
        s = stats.loc[deal_id]

        resec = bool(d["resecuritisation"])
        stc = bool(d["simple_transparent_comparable"])
        senior = bool(t["senior"])

        w = W_RESEC if resec else float(s["w_delinquency"])
        k_sa = float(s["k_sa"])
        k_a = (1.0 - w) * k_sa + w * 0.5

        if resec:
            p = P_SA_RESEC
            p_note = "CRE41.19 재유동화 p=1.5 · W=0"
        elif stc:
            p = P_SA_STC
            p_note = "CRE40.44 STC 우대 p=0.5"
        else:
            p = P_SA
            p_note = "CRE41.14 일반 p=1.0"

        floor = tranche_rw_floor(stc=stc, senior=senior, resecuritisation=resec)
        kss, raw, rw, floored = _ssfa_risk_weight(
            attach=float(t["attachment_point"]),
            detach=float(t["detachment_point"]),
            k=k_a, p=p, floor=floor)

        if math.isnan(kss):
            note = (f"D≤K_A({k_a:.4f}) — 트렌치 전액이 풀 자본요구 이하, "
                    f"1250% 적용(CRE41.16(1)) · {p_note}")
        else:
            note = (f"K_A={k_a:.4f}(K_SA={k_sa:.4f}, W={w:.4f}) · {p_note}"
                    + (f" · 하한 {floor:.0%} 적용" if floored else ""))

        rows.append({
            "tranche_id": t["tranche_id"],
            "deal_id": deal_id,
            "asof": t["asof"],
            "exposure_amount": float(t["holding_amount"]),
            "attachment_point": float(t["attachment_point"]),
            "detachment_point": float(t["detachment_point"]),
            "k_sa": k_sa,
            "w_delinquency": w,
            "k_a": k_a,
            "p_sa": p,
            "k_ssfa_sa": kss,
            "rw_sa_before_floor": raw,
            "rw_floor_sa": floor,
            "rw_sa": rw,
            "floor_applied_sa": floored,
            "rwa_sa": rw * float(t["holding_amount"]),
            "sa_note": note,
        })

    out = pd.DataFrame(rows)
    if out["rw_sa"].isna().any():
        bad = out.loc[out["rw_sa"].isna(), "tranche_id"].tolist()
        raise ValueError(f"SEC-SA 위험가중치가 NaN인 트렌치: {bad} — 계층의 바닥이 무너졌다")
    return out


# ---------------------------------------------------------------- SEC-ERBA

def sec_erba_rwa(master: pd.DataFrame, tranche: pd.DataFrame) -> pd.DataFrame:
    """CRE42 외부등급법(SEC-ERBA) 트렌치별 위험가중치·RWA.

    등급이 없거나 재유동화면 **산출 불가(NaN)** 로 두고 사유를 남긴다. 0 으로
    채우면 무등급 트렌치가 무위험으로 읽히고, 1250% 로 채우면 쓰지도 않을
    방법이 비교표에서 최악값처럼 보인다.

    STC 우대 ERBA 대체표는 미반영이다(모듈 docstring 「범위 밖」 참조) — 일반표를
    쓰므로 STC 딜의 ERBA 값은 보수적으로 과대하다.
    """
    _require_columns(master, _MASTER_REQUIRED, "master")
    _require_columns(tranche, _TRANCHE_REQUIRED, "tranche")

    m = master.set_index("deal_id")
    rows: list[dict[str, Any]] = []
    for t in tranche.to_dict("records"):
        deal_id = t["deal_id"]
        if deal_id not in m.index:
            raise ValueError(f"{t['tranche_id']}: 마스터에 없는 deal_id={deal_id}")
        d = m.loc[deal_id]
        stc = bool(d["simple_transparent_comparable"])
        senior = bool(t["senior"])
        rating = str(t["external_rating"])
        mt = float(t["residual_maturity_years"])

        if bool(d["resecuritisation"]):
            raw, rw, floored = float("nan"), float("nan"), False
            note = "CRE41.19 재유동화 — SEC-ERBA 사용 불가(SEC-SA 강제)"
            floor = float("nan")
        else:
            raw, note = erba_risk_weight(
                rating, senior=senior, mt=mt, thickness=float(t["thickness"]))
            if math.isnan(raw):
                rw, floored, floor = float("nan"), False, float("nan")
            else:
                floor = tranche_rw_floor(stc=stc, senior=senior)
                rw = float(max(min(raw, RW_CAP), floor))
                floored = bool(rw > raw)
                if floored:
                    note += f" · 하한 {floor:.0%} 적용"
                if stc:
                    note += " · STC 대체표 미반영(일반표 적용, 보수적)"

        exposure = float(t["holding_amount"])
        rows.append({
            "tranche_id": t["tranche_id"],
            "deal_id": deal_id,
            "asof": t["asof"],
            "exposure_amount": exposure,
            "external_rating": rating,
            "senior": senior,
            "mt_capped": _clip_mt(mt),
            "thickness": float(t["thickness"]),
            "rw_erba_before_floor": raw,
            "rw_floor_erba": floor,
            "rw_erba": rw,
            "floor_applied_erba": floored,
            "rwa_erba": rw * exposure,
            "erba_available": bool(not math.isnan(rw)),
            "erba_note": note,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- SEC-IRBA

def _irba_p(*, senior: bool, granular: bool, retail: bool, k_irb: float,
            lgd: float, mt: float, effective_n: float, stc: bool) -> float:
    """CRE44.5 감독 파라미터 p = max(0.3, A + B/N + C·K_IRB + D·LGD + E·MT).

    계수명은 pa~pe 로 쓴다 — A/D 는 이 모듈에서 attachment/detachment 이므로
    같은 글자를 쓰면 읽는 사람이 반드시 틀린다.
    """
    if retail:
        pa, pb, pc, pd_, pe = _P_COEFF_RETAIL[senior]
    else:
        pa, pb, pc, pd_, pe = _P_COEFF_WHOLESALE[(senior, granular)]

    p = (pa + pb * (1.0 / effective_n) + pc * k_irb + pd_ * lgd
         + pe * _clip_mt(mt))
    if stc:
        # STC 우대 — p 반감. 하한 0.3 은 반감 뒤에 적용한다 (CRE44.5 · CRE40.44).
        p *= 0.5
    return float(max(P_IRBA_FLOOR, p))


def sec_irba_rwa(master: pd.DataFrame, tranche: pd.DataFrame,
                 pool: pd.DataFrame) -> pd.DataFrame:
    """CRE43/44 내부등급법(SEC-IRBA) 트렌치별 위험가중치·RWA.

    K_IRB(EL 포함, CRE44.2)를 SSFA 에 넣되 p 는 CRE44.5 감독식으로 산출한다.
    K_IRB 를 풀 전체에 대해 낼 수 없거나 재유동화면 **산출 불가(NaN)** 다.
    """
    _require_columns(master, _MASTER_REQUIRED, "master")
    _require_columns(tranche, _TRANCHE_REQUIRED, "tranche")

    stats = sec_pool_stats(pool).set_index("deal_id")
    m = master.set_index("deal_id")

    rows: list[dict[str, Any]] = []
    for t in tranche.to_dict("records"):
        deal_id = t["deal_id"]
        if deal_id not in m.index:
            raise ValueError(f"{t['tranche_id']}: 마스터에 없는 deal_id={deal_id}")
        if deal_id not in stats.index:
            raise ValueError(f"{t['tranche_id']}: 기초자산 풀이 없는 deal_id={deal_id}")
        d = m.loc[deal_id]
        s = stats.loc[deal_id]

        stc = bool(d["simple_transparent_comparable"])
        senior = bool(t["senior"])
        k_irb = float(s["k_irb"])
        exposure = float(t["holding_amount"])

        blocked = ""
        if bool(d["resecuritisation"]):
            blocked = "CRE41.19 재유동화 — SEC-IRBA 사용 불가(SEC-SA 강제)"
        elif math.isnan(k_irb):
            blocked = (f"기초자산 K_IRB 산출 불가 — IRB 승인 커버리지 "
                       f"{IRB_POOL_COVERAGE_MIN:.0%} 미충족(CRE44.2)")
        elif k_irb <= 0.0:
            blocked = f"K_IRB={k_irb:.6f} ≤ 0 — SSFA 정의 불가"

        if blocked:
            rows.append({
                "tranche_id": t["tranche_id"], "deal_id": deal_id,
                "asof": t["asof"], "exposure_amount": exposure,
                "k_irb": k_irb, "pool_lgd": float(s["pool_lgd"]),
                "effective_n": float(s["effective_n"]),
                "granular": bool(float(s["effective_n"]) >= GRANULARITY_THRESHOLD),
                "is_retail_pool": bool(s["is_retail"]),
                "p_irba": float("nan"), "k_ssfa_irba": float("nan"),
                "rw_irba_before_floor": float("nan"),
                "rw_floor_irba": float("nan"), "rw_irba": float("nan"),
                "floor_applied_irba": False, "rwa_irba": float("nan"),
                "irba_available": False, "irba_note": blocked,
            })
            continue

        granular = bool(float(s["effective_n"]) >= GRANULARITY_THRESHOLD)
        p = _irba_p(senior=senior, granular=granular, retail=bool(s["is_retail"]),
                    k_irb=k_irb, lgd=float(s["pool_lgd"]),
                    mt=float(t["residual_maturity_years"]),
                    effective_n=float(s["effective_n"]), stc=stc)
        floor = tranche_rw_floor(stc=stc, senior=senior)
        kss, raw, rw, floored = _ssfa_risk_weight(
            attach=float(t["attachment_point"]),
            detach=float(t["detachment_point"]),
            k=k_irb, p=p, floor=floor)

        if math.isnan(kss):
            note = (f"D≤K_IRB({k_irb:.4f}) — 1250% 적용(CRE43.4) · "
                    f"p={p:.4f}(CRE44.5)")
        else:
            note = (f"K_IRB={k_irb:.4f} · p={p:.4f}(CRE44.5, "
                    f"{'소매' if bool(s['is_retail']) else '도매'}/"
                    f"{'선순위' if senior else '비선순위'}/"
                    f"{'입도' if granular else '비입도'}"
                    f"{', STC 반감' if stc else ''})"
                    + (f" · 하한 {floor:.0%} 적용" if floored else ""))

        rows.append({
            "tranche_id": t["tranche_id"], "deal_id": deal_id,
            "asof": t["asof"], "exposure_amount": exposure,
            "k_irb": k_irb, "pool_lgd": float(s["pool_lgd"]),
            "effective_n": float(s["effective_n"]), "granular": granular,
            "is_retail_pool": bool(s["is_retail"]),
            "p_irba": p, "k_ssfa_irba": kss,
            "rw_irba_before_floor": raw, "rw_floor_irba": floor,
            "rw_irba": rw, "floor_applied_irba": floored,
            "rwa_irba": rw * exposure,
            "irba_available": True, "irba_note": note,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- 계층 요약

def sec_rwa_summary(master: pd.DataFrame, tranche: pd.DataFrame,
                    pool: pd.DataFrame) -> pd.DataFrame:
    """세 방법을 나란히 두고 CRE40.41 계층대로 채택값·사유를 남긴다.

    채택은 **트렌치 단위**다 — 같은 딜이라도 등급이 붙은 선순위는 ERBA, 무등급
    Equity 는 SA 로 갈 수 있다. 마스터의 `applicable_approach` 는 딜 단위 최선
    방법이며 여기서 다시 계산하지 않고 같은 `applicable_approach()` 함수를 쓴다.
    """
    sa = sec_sa_rwa(master, tranche, pool)
    erba = sec_erba_rwa(master, tranche)
    irba = sec_irba_rwa(master, tranche, pool)

    base = tranche[["tranche_id", "deal_id", "asof", "tranche_name",
                    "tranche_type", "seniority", "senior", "attachment_point",
                    "detachment_point", "thickness", "external_rating",
                    "residual_maturity_years", "retained",
                    "holding_amount"]].copy()
    base = base.merge(
        master[["deal_id", "deal_name", "pool_asset_class", "securitisation_type",
                "resecuritisation", "simple_transparent_comparable"]],
        on="deal_id", how="left", validate="many_to_one")

    base = base.merge(
        sa[["tranche_id", "k_sa", "k_a", "p_sa", "rw_sa", "rwa_sa",
            "rw_floor_sa", "floor_applied_sa", "sa_note"]],
        on="tranche_id", how="left", validate="one_to_one")
    base = base.merge(
        erba[["tranche_id", "rw_erba", "rwa_erba", "rw_floor_erba",
              "floor_applied_erba", "erba_available", "erba_note"]],
        on="tranche_id", how="left", validate="one_to_one")
    base = base.merge(
        irba[["tranche_id", "k_irb", "p_irba", "rw_irba", "rwa_irba",
              "rw_floor_irba", "floor_applied_irba", "irba_available",
              "irba_note"]],
        on="tranche_id", how="left", validate="one_to_one")

    adopted_method: list[str] = []
    adopted_rw: list[float] = []
    adopted_rwa: list[float] = []
    adopted_floor: list[float] = []
    floor_applied: list[bool] = []
    reasons: list[str] = []

    for r in base.to_dict("records"):
        method, why = applicable_approach(
            resecuritisation=bool(r["resecuritisation"]),
            irb_available=bool(r["irba_available"]),
            rated=bool(r["erba_available"]))

        if method == "SEC-IRBA":
            rw, rwa = float(r["rw_irba"]), float(r["rwa_irba"])
            floor_v, fl = float(r["rw_floor_irba"]), bool(r["floor_applied_irba"])
            detail = r["irba_note"]
        elif method == "SEC-ERBA":
            rw, rwa = float(r["rw_erba"]), float(r["rwa_erba"])
            floor_v, fl = float(r["rw_floor_erba"]), bool(r["floor_applied_erba"])
            detail = r["erba_note"]
        else:
            rw, rwa = float(r["rw_sa"]), float(r["rwa_sa"])
            floor_v, fl = float(r["rw_floor_sa"]), bool(r["floor_applied_sa"])
            detail = r["sa_note"]

        # 상위 방법이 왜 막혔는지까지 남겨야 감사에서 계층 적용이 설명된다.
        blocked_notes = []
        if method != "SEC-IRBA" and not bool(r["irba_available"]):
            blocked_notes.append(f"IRBA 불가: {r['irba_note']}")
        if method == "SEC-SA" and not bool(r["erba_available"]):
            blocked_notes.append(f"ERBA 불가: {r['erba_note']}")

        adopted_method.append(method)
        adopted_rw.append(rw)
        adopted_rwa.append(rwa)
        adopted_floor.append(floor_v)
        floor_applied.append(fl)
        reasons.append(" | ".join([why, detail] + blocked_notes))

    base["adopted_method"] = adopted_method
    base["adopted_rw"] = adopted_rw
    base["adopted_rwa"] = adopted_rwa
    base["adopted_rw_floor"] = adopted_floor
    base["floor_applied"] = floor_applied
    base["adopted_capital_8pct"] = base["adopted_rwa"] * BIS_MIN_TOTAL
    base["adopted_reason"] = reasons

    if base["adopted_rwa"].isna().any():
        bad = base.loc[base["adopted_rwa"].isna(), "tranche_id"].tolist()
        raise ValueError(f"채택 RWA가 NaN인 트렌치: {bad} — CRE40.41 계층이 바닥까지 닿지 않았다")
    assert base["adopted_rw"].between(0.0, RW_CAP).all(), \
        "채택 위험가중치가 0~1250% 범위를 벗어났다"

    return base[[
        "tranche_id", "deal_id", "asof", "deal_name", "tranche_name",
        "tranche_type", "seniority", "senior", "retained", "pool_asset_class",
        "securitisation_type", "resecuritisation",
        "simple_transparent_comparable", "attachment_point",
        "detachment_point", "thickness", "external_rating",
        "residual_maturity_years", "holding_amount",
        "k_sa", "k_a", "p_sa", "rw_sa", "rwa_sa",
        "rw_erba", "rwa_erba", "erba_available",
        "k_irb", "p_irba", "rw_irba", "rwa_irba", "irba_available",
        "adopted_method", "adopted_rw", "adopted_rwa", "adopted_rw_floor",
        "floor_applied", "adopted_capital_8pct", "adopted_reason",
    ]]


# ---------------------------------------------------------------- 합성 원장

# 당행이 원 보유자인 딜은 위험보유(risk retention) 규정에 따라 **수직형 5%**를
# 보유한다 — 전 트렌치를 같은 비율로 남기는 방식이다. 후순위 전액 보유(수평형)를
# 택하면 유의적 위험이전(CRE40.24 SRT)이 부정되어 유동화 자체의 자본경감이
# 무너지므로, 자금조달형이 아닌 이 딜들에는 수직형이 맞다.
# 투자자로 참여한 딜은 트렌치별 일부만 취득한다.
_BANK_NAME = "당행"
_VERTICAL_RETENTION = 0.05

# 딜 정의. 세 산출경로(IRBA/ERBA/SA)가 모두 쓰이도록 등급·IRB 승인·재유동화를
# 의도적으로 흩어놓았다.
#   rating_profile: full(Equity 제외 전부 등급) / senior_only(최선순위만) / none
#   irb_available : 기초자산 IRB 승인 여부 → SEC-IRBA 가능 여부
#   n_scale       : 기초자산 건수 배율. 0.1 은 소수 대형차주 풀(비입도)을 만든다
_DEAL_SEEDS: tuple[dict[str, Any], ...] = (
    {"deal_id": "SEC-2301", "deal_name": "국민주택 RMBS 2023-1",
     "sec_type": "전통적", "pool_class": "주택담보대출", "resec": False,
     "stc": True, "originator": _BANK_NAME, "irb_available": True,
     "rating_profile": "full", "n_tranches": 4, "n_segments": 3,
     "pool_range": (1.8e12, 2.4e12), "maturity": 10.0, "n_scale": 1.0},
    {"deal_id": "SEC-2402", "deal_name": "주택금융공사 MBS 2024-2",
     "sec_type": "전통적", "pool_class": "주택담보대출", "resec": False,
     "stc": True, "originator": "한국주택금융공사", "irb_available": False,
     "rating_profile": "full", "n_tranches": 3, "n_segments": 2,
     "pool_range": (1.2e12, 1.8e12), "maturity": 9.0, "n_scale": 1.0},
    {"deal_id": "SEC-2303", "deal_name": "코리아 CLO 2023-A",
     "sec_type": "전통적", "pool_class": "기업대출", "resec": False,
     "stc": False, "originator": _BANK_NAME, "irb_available": True,
     "rating_profile": "full", "n_tranches": 4, "n_segments": 4,
     "pool_range": (1.0e12, 1.6e12), "maturity": 6.0, "n_scale": 1.0},
    {"deal_id": "SEC-2404", "deal_name": "합성 CLO 2024-B",
     "sec_type": "합성", "pool_class": "기업대출", "resec": False,
     "stc": False, "originator": _BANK_NAME, "irb_available": True,
     "rating_profile": "none", "n_tranches": 3, "n_segments": 3,
     "pool_range": (0.8e12, 1.2e12), "maturity": 5.0, "n_scale": 0.10},
    {"deal_id": "SEC-2405", "deal_name": "신한카드 ABS 2024-1",
     "sec_type": "전통적", "pool_class": "신용카드", "resec": False,
     "stc": True, "originator": "신한카드", "irb_available": False,
     "rating_profile": "full", "n_tranches": 3, "n_segments": 2,
     "pool_range": (0.7e12, 1.1e12), "maturity": 3.0, "n_scale": 1.0},
    {"deal_id": "SEC-2306", "deal_name": "현대캐피탈 오토 ABS 2023-1",
     "sec_type": "전통적", "pool_class": "오토론", "resec": False,
     "stc": False, "originator": "현대캐피탈", "irb_available": False,
     "rating_profile": "senior_only", "n_tranches": 4, "n_segments": 2,
     "pool_range": (0.6e12, 0.9e12), "maturity": 4.0, "n_scale": 1.0},
    {"deal_id": "SEC-2507", "deal_name": "롯데캐피탈 오토 ABS 2025-1",
     "sec_type": "전통적", "pool_class": "오토론", "resec": False,
     "stc": False, "originator": "롯데캐피탈", "irb_available": False,
     "rating_profile": "none", "n_tranches": 3, "n_segments": 2,
     "pool_range": (0.4e12, 0.7e12), "maturity": 4.0, "n_scale": 1.0},
    {"deal_id": "SEC-2208", "deal_name": "글로벌 ABS CDO 2022-R",
     "sec_type": "전통적", "pool_class": "CDO", "resec": True,
     "stc": False, "originator": "해외 SPC", "irb_available": False,
     "rating_profile": "full", "n_tranches": 3, "n_segments": 3,
     "pool_range": (0.3e12, 0.6e12), "maturity": 7.0, "n_scale": 1.0},
)

# 기초자산 풀 세그먼트 템플릿.
#   irb_class : risk_lib.capital.rwa_irb 의 자산군 어휘 (상관계수 R 분기)
#   sa        : risk_lib.capital.rwa_sa.sa_risk_weight() 인자 — SA 위험가중치를
#               표로 베끼지 않고 함수로 받는다
#   sa_sec    : 재유동화 세그먼트 전용. 기초가 유동화 트렌치라 SA 위험가중치를
#               유동화 프레임워크(CRE42)로 산출한다 (CRE41.19(1))
_SEGMENT_TEMPLATES: dict[str, tuple[dict[str, Any], ...]] = {
    "주택담보대출": (
        {"name": "LTV 60% 이하 주담대", "irb_class": "residential_mortgage",
         "pd": (0.003, 0.008), "lgd": (0.12, 0.20), "dq": (0.002, 0.010),
         "n": (9000, 15000),
         "sa": {"asset_class": "residential_mortgage", "ltv": 0.55}},
        {"name": "LTV 60~80% 주담대", "irb_class": "residential_mortgage",
         "pd": (0.006, 0.014), "lgd": (0.18, 0.28), "dq": (0.005, 0.018),
         "n": (6000, 11000),
         "sa": {"asset_class": "residential_mortgage", "ltv": 0.72}},
        {"name": "LTV 80% 초과 주담대", "irb_class": "residential_mortgage",
         "pd": (0.012, 0.025), "lgd": (0.25, 0.38), "dq": (0.010, 0.030),
         "n": (2000, 5000), "sa": {"asset_class": "residential_mortgage", "ltv": 0.88}},
    ),
    "기업대출": (
        {"name": "대기업 선순위 대출", "irb_class": "corporate",
         "pd": (0.004, 0.012), "lgd": (0.35, 0.45), "dq": (0.004, 0.015),
         "n": (30, 60), "sa": {"asset_class": "corporate", "rating": "A"}},
        {"name": "중견기업 대출", "irb_class": "corporate",
         "pd": (0.010, 0.025), "lgd": (0.40, 0.50), "dq": (0.010, 0.030),
         "n": (40, 90), "sa": {"asset_class": "corporate", "rating": "BBB"}},
        {"name": "중소기업 대출", "irb_class": "corporate",
         "pd": (0.020, 0.045), "lgd": (0.42, 0.55), "dq": (0.020, 0.050),
         "n": (60, 140), "sa": {"asset_class": "corporate", "rating": "BB"}},
        {"name": "해외법인 대출", "irb_class": "corporate",
         "pd": (0.015, 0.035), "lgd": (0.38, 0.52), "dq": (0.012, 0.035),
         "n": (20, 45), "sa": {"asset_class": "corporate", "rating": "BBB"}},
    ),
    "신용카드": (
        {"name": "일시불·할부 채권", "irb_class": "retail_revolving",
         "pd": (0.015, 0.030), "lgd": (0.55, 0.70), "dq": (0.015, 0.035),
         "n": (250000, 450000), "sa": {"asset_class": "retail_regulatory"}},
        {"name": "리볼빙 채권", "irb_class": "retail_revolving",
         "pd": (0.030, 0.060), "lgd": (0.62, 0.78), "dq": (0.035, 0.070),
         "n": (80000, 160000), "sa": {"asset_class": "retail_regulatory"}},
    ),
    "오토론": (
        {"name": "신차 오토론", "irb_class": "retail_other",
         "pd": (0.008, 0.018), "lgd": (0.30, 0.42), "dq": (0.008, 0.020),
         "n": (25000, 45000), "sa": {"asset_class": "retail_regulatory"}},
        {"name": "중고차 오토론", "irb_class": "retail_other",
         "pd": (0.020, 0.040), "lgd": (0.40, 0.55), "dq": (0.020, 0.045),
         "n": (12000, 25000), "sa": {"asset_class": "retail_other"}},
    ),
    "CDO": (
        {"name": "편입 RMBS 선순위 트렌치", "irb_class": "securitisation",
         "dq": (0.010, 0.025), "n": (6, 12),
         "sa_sec": {"rating": "AA", "senior": True, "mt": 4.0, "thickness": 0.80}},
        {"name": "편입 CLO 메자닌 트렌치", "irb_class": "securitisation",
         "dq": (0.020, 0.045), "n": (4, 9),
         "sa_sec": {"rating": "BBB", "senior": False, "mt": 4.5, "thickness": 0.08}},
        {"name": "편입 카드 ABS 선순위 트렌치", "irb_class": "securitisation",
         "dq": (0.015, 0.035), "n": (5, 10),
         "sa_sec": {"rating": "A", "senior": True, "mt": 3.0, "thickness": 0.85}},
    ),
}

# 트렌치 구조 — (명칭, 유형) 순서는 선순위→후순위. A/D 는 두께를 뽑아 쌓는다.
_TRANCHE_LAYOUT: dict[int, tuple[tuple[str, str], ...]] = {
    3: (("Class A", "Senior"), ("Class B", "Mezzanine"), ("Equity", "Equity")),
    4: (("Class A", "Senior"), ("Class B", "Mezzanine"),
        ("Class C", "Mezzanine"), ("Equity", "Equity")),
}

# 후순위부터 쌓는 두께 범위 (풀 잔액 대비). Equity → Mezz → Senior 잔여.
_THICKNESS_RANGE: dict[str, tuple[float, float]] = {
    "Equity": (0.030, 0.055),
    "Mezzanine": (0.040, 0.075),
}

# 등급 후보 — 선순위일수록 상위. rating_profile 이 full 일 때 쓴다.
_RATING_POOL: dict[str, tuple[str, ...]] = {
    "Senior": ("AAA", "AA+", "AA"),
    "Mezzanine": ("A", "A-", "BBB+", "BBB", "BBB-", "BB+"),
}


def _build_master_base(asof: str, seed: int, scale: float) -> pd.DataFrame:
    """딜 속성 + 풀 잔액. 풀·트렌치에서 파생되는 컬럼은 _finalise_master 가 붙인다."""
    rng = np.random.default_rng(seed + 7400)
    rows: list[dict[str, Any]] = []
    for s in _DEAL_SEEDS:
        lo, hi = s["pool_range"]
        rows.append({
            "deal_id": s["deal_id"],
            "asof": asof,
            "deal_name": s["deal_name"],
            "securitisation_type": s["sec_type"],
            "pool_asset_class": s["pool_class"],
            "resecuritisation": bool(s["resec"]),
            "simple_transparent_comparable": bool(s["stc"]),
            "originator": s["originator"],
            "originated_by_bank": bool(s["originator"] == _BANK_NAME),
            # 금액 배수는 기관 프로파일 원장에서 온다. 풀 잔액에만 곱하면
            # 트렌치 두께·발행액·보유액이 전부 비율로 파생되므로 원장 전체가
            # 같은 배수로 움직인다.
            "pool_balance": float(rng.uniform(lo, hi)) * scale,
            "deal_maturity_years": float(s["maturity"]),
            "irb_data_available": bool(s["irb_available"]),
            "rating_profile": s["rating_profile"],
            "n_tranches": int(s["n_tranches"]),
            "n_segments": int(s["n_segments"]),
            "n_scale": float(s["n_scale"]),
        })
    df = pd.DataFrame(rows)

    # 재유동화 + STC 는 동시에 성립할 수 없다 (CRE40.44 STC 요건은 재유동화를
    # 배제한다). 시드 표를 잘못 고치면 여기서 걸린다.
    bad = df[df["resecuritisation"] & df["simple_transparent_comparable"]]
    assert bad.empty, f"재유동화인데 STC로 표시된 딜: {bad['deal_id'].tolist()}"
    return df


def _build_tranche(base: pd.DataFrame, asof: str, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed + 7410)
    rows: list[dict[str, Any]] = []
    for d in base.to_dict("records"):
        layout = _TRANCHE_LAYOUT[int(d["n_tranches"])]
        n = len(layout)
        pool_balance = float(d["pool_balance"])

        # 후순위부터 두께를 쌓아 A/D 가 [0,1] 을 빈틈없이 덮게 한다. 빈틈이 생기면
        # 풀 손실의 일부가 어느 트렌치에도 귀속되지 않아 SSFA 가 의미를 잃는다.
        thick: list[float] = []
        for _, ttype in reversed(layout[1:]):     # Senior 제외, 후순위→상위
            lo, hi = _THICKNESS_RANGE[ttype]
            thick.append(float(rng.uniform(lo, hi)))
        senior_thickness = 1.0 - sum(thick)
        assert senior_thickness > 0.5, \
            f"{d['deal_id']}: 선순위 두께가 비정상({senior_thickness:.4f})"
        # thick 은 이미 최후순위→상위 순으로 뽑혔고 아래 루프도 같은 순서로
        # 소비한다. 여기서 뒤집으면 Equity 가 Mezzanine 범위의 두께를, 최상위
        # Mezzanine 이 Equity 범위의 두께를 받아 _THICKNESS_RANGE 선언과 어긋난다.
        thickness_by_index = thick + [senior_thickness]
        # thickness_by_index[0] = 최후순위 … [-1] = 최선순위

        attach = 0.0
        stack: list[dict[str, Any]] = []
        for k, th in enumerate(thickness_by_index):
            name, ttype = layout[n - 1 - k]
            detach = attach + th
            seniority = n - k              # 1 = 최선순위
            stack.append({"name": name, "ttype": ttype, "attach": attach,
                          "detach": detach, "thickness": th,
                          "seniority": seniority})
            attach = detach
        # 부동소수 누적오차를 최선순위 D 에서 정확히 1.0 으로 닫는다.
        stack[-1]["detach"] = 1.0
        stack[-1]["thickness"] = 1.0 - stack[-1]["attach"]

        # 두께가 선언 범위를 벗어나면 트렌치 유형과 두께 분포가 어긋난 것이다.
        # Equity 두께는 D≤K 판정(1250%)을, Mezzanine 두께는 CRE42.3 두께조정을
        # 직접 움직이므로 조용히 뒤바뀌면 자본이 통째로 틀린다.
        for item in stack[:-1]:
            lo, hi = _THICKNESS_RANGE[item["ttype"]]
            assert lo <= item["thickness"] <= hi, (
                f"{d['deal_id']} {item['name']}({item['ttype']}): 두께 "
                f"{item['thickness']:.4f}가 선언 범위 {lo}~{hi} 밖이다")

        for item in stack:
            senior = bool(item["seniority"] == 1)
            ttype = item["ttype"]

            # 등급. Equity(최후순위 손실흡수)는 실무상 등급을 받지 않는다.
            profile = d["rating_profile"]
            if ttype == "Equity" or profile == "none":
                rating = "NR"
            elif profile == "senior_only" and not senior:
                rating = "NR"
            else:
                rating = str(rng.choice(_RATING_POOL[ttype]))

            # 잔존만기 — 선순위가 길다. 딜 만기를 넘지 않는다.
            frac = rng.uniform(0.80, 0.98) if senior else rng.uniform(0.45, 0.80)
            mt = float(d["deal_maturity_years"]) * float(frac)

            notional = item["thickness"] * pool_balance
            if bool(d["originated_by_bank"]):
                hold = notional * _VERTICAL_RETENTION   # 수직형 위험보유
                retained = True
            else:
                # 투자자 취득비율. 하한 4%·상한 12%는 임의값이 아니라, 딜별
                # 풀 잔액 범위와 곱했을 때 보유 잔액 합계가 **어떤 seed에서도**
                # 상정 대역(3천억~1조 KRW) 안에 들도록 잡은 것이다. 범위를
                # 넓히면 build_securitisation의 규모 assert가 seed에 따라
                # 터진다.
                hold = notional * float(rng.uniform(0.04, 0.12))
                retained = False

            rows.append({
                "tranche_id": f"{d['deal_id']}-T{item['seniority']}",
                "deal_id": d["deal_id"],
                "asof": asof,
                "tranche_name": item["name"],
                "tranche_type": ttype,
                "seniority": int(item["seniority"]),
                "senior": senior,
                "attachment_point": float(item["attach"]),
                "detachment_point": float(item["detach"]),
                "thickness": float(item["thickness"]),
                "tranche_notional": float(notional),
                "holding_amount": float(hold),
                "external_rating": rating,
                "residual_maturity_years": mt,
                "retained": retained,
            })
    return pd.DataFrame(rows)


def _segment_sa_risk_weight(tpl: dict[str, Any]) -> tuple[float, str]:
    """세그먼트의 SA 위험가중치와 산출근거.

    일반 자산은 `rwa_sa.sa_risk_weight()` 를, 재유동화 기초(유동화 트렌치)는
    이 모듈의 CRE42 표를 쓴다 (CRE41.19(1) — 기초 유동화 익스포저의 자본요구는
    유동화 프레임워크로 산출). 어느 쪽도 표를 베끼지 않는다.
    """
    if "sa_sec" in tpl:
        a = tpl["sa_sec"]
        rw, note = erba_risk_weight(a["rating"], senior=a["senior"],
                                    mt=a["mt"], thickness=a["thickness"])
        rw = max(rw, tranche_rw_floor(stc=False, senior=a["senior"]))
        return float(rw), f"CRE41.19(1) 기초 유동화 트렌치 — {note}"

    a = dict(tpl["sa"])
    ac = a.pop("asset_class")
    rating = a.pop("rating", "UNRATED")
    ltv = a.pop("ltv", None)
    assert not a, f"미사용 SA 인자: {a}"
    rw = sa_risk_weight(ac, rating, ltv=ltv)
    detail = f"LTV {ltv:.0%}" if ltv is not None else f"등급 {rating}"
    return float(rw), f"CRE20 SA {ac} · {detail}"


def _build_pool(base: pd.DataFrame, asof: str, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed + 7420)
    rows: list[dict[str, Any]] = []
    for d in base.to_dict("records"):
        templates = _SEGMENT_TEMPLATES[d["pool_asset_class"]][: int(d["n_segments"])]
        assert len(templates) == int(d["n_segments"]), \
            f"{d['deal_id']}: 세그먼트 템플릿 부족"

        # 잔액 배분 — 합계가 pool_balance 와 정확히 일치해야 K_SA·W 의 분모가
        # 마스터와 어긋나지 않는다. 마지막 세그먼트에서 잔차를 닫는다.
        weights = rng.uniform(0.6, 1.4, size=len(templates))
        weights = weights / weights.sum()
        balances = [float(w) * float(d["pool_balance"]) for w in weights]
        balances[-1] = float(d["pool_balance"]) - sum(balances[:-1])

        for i, (tpl, bal) in enumerate(zip(templates, balances), start=1):
            dq = float(rng.uniform(*tpl["dq"]))
            n_lo, n_hi = tpl["n"]
            n_exp = max(1, int(round(float(rng.integers(n_lo, n_hi + 1))
                                     * float(d["n_scale"]))))
            sa_rw, sa_basis = _segment_sa_risk_weight(tpl)

            if tpl["irb_class"] == "securitisation":
                # 기초가 유동화 트렌치라 차주 PD/LGD 개념이 없다. 없는 값을
                # 지어내면 K_IRB 가 그럴듯하게 계산되어 재유동화에 금지된
                # SEC-IRBA 가 열린다 (CRE41.19). NaN 이 정답이다.
                wa_pd = float("nan")
                wa_lgd = float("nan")
                k_irb = float("nan")
                k_basis = "기초가 유동화 트렌치 — 차주 PD/LGD 없음, K_IRB 산출 불가"
            else:
                wa_pd = float(rng.uniform(*tpl["pd"]))
                wa_lgd = float(rng.uniform(*tpl["lgd"]))
                if bool(d["irb_data_available"]):
                    # K_IRB 는 UL 자본요구 + EL 이다 (CRE44.2). EL 을 빼면 K_IRB 가
                    # 과소해져 SSFA 곡선이 통째로 왼쪽으로 밀린다.
                    k_ul = irb_capital_requirement(
                        wa_pd, wa_lgd, tpl["irb_class"],
                        float(d["deal_maturity_years"]))
                    k_irb = float(k_ul + wa_pd * wa_lgd)
                    k_basis = (f"CRE44.2 K_IRB = UL {k_ul:.4f} + EL "
                               f"{wa_pd * wa_lgd:.4f} (IRB 승인 포트폴리오)")
                else:
                    k_irb = float("nan")
                    k_basis = ("IRB 미승인 기초자산 — CRE44.2 커버리지 "
                               f"{IRB_POOL_COVERAGE_MIN:.0%} 미충족, K_IRB 산출 불가")

            rows.append({
                "segment_id": f"{d['deal_id']}-S{i:02d}",
                "deal_id": d["deal_id"],
                "asof": asof,
                "segment_name": tpl["name"],
                "irb_asset_class": tpl["irb_class"],
                "balance": float(bal),
                "n_exposures": int(n_exp),
                "wa_pd": wa_pd,
                "wa_lgd": wa_lgd,
                "delinquency_rate": dq,
                "k_irb": k_irb,
                "k_irb_basis": k_basis,
                "sa_risk_weight": float(sa_rw),
                "sa_rw_basis": sa_basis,
            })
    return pd.DataFrame(rows)


def _finalise_master(base: pd.DataFrame, tranche: pd.DataFrame,
                     pool: pd.DataFrame) -> pd.DataFrame:
    """풀·트렌치에서 파생되는 마스터 컬럼(N·발행총액·적용계층)을 붙인다.

    건수·발행총액을 마스터에 따로 지어내지 않고 원장에서 집계한다 — 두 곳에
    적으면 둘 중 하나는 틀릴 준비가 된 것이다.
    """
    stats = sec_pool_stats(pool).set_index("deal_id")
    out = base.copy()

    out["pool_n_exposures"] = out["deal_id"].map(stats["n_exposures"]).astype(int)
    out["pool_effective_n"] = out["deal_id"].map(stats["effective_n"]).astype(float)

    # 발행총액: 전통적 유동화는 전 트렌치를 발행한다. 합성 유동화는 선순위를
    # 미발행(무담보 CDS)으로 두고 후순위만 자금화하므로 발행총액이 풀보다 작다.
    tn = tranche.copy()
    placed = tn["seniority"] > 1
    synth = tn["deal_id"].map(base.set_index("deal_id")["securitisation_type"]) == "합성"
    tn["issued"] = np.where(synth, placed, True)
    issue = tn.loc[tn["issued"]].groupby("deal_id")["tranche_notional"].sum()
    out["issue_amount"] = out["deal_id"].map(issue).astype(float)

    rated_any = tranche.assign(
        rated=tranche["external_rating"] != "NR").groupby("deal_id")["rated"].any()
    out["external_rating_available"] = out["deal_id"].map(rated_any).astype(bool)

    approach, reason = zip(*[
        applicable_approach(resecuritisation=bool(r["resecuritisation"]),
                            irb_available=bool(r["irb_data_available"]),
                            rated=bool(r["external_rating_available"]))
        for r in out.to_dict("records")])
    out["applicable_approach"] = list(approach)
    out["approach_reason"] = list(reason)

    return out[[
        "deal_id", "asof", "deal_name", "securitisation_type",
        "pool_asset_class", "resecuritisation", "simple_transparent_comparable",
        "originator", "originated_by_bank", "pool_balance", "issue_amount",
        "pool_n_exposures", "pool_effective_n", "deal_maturity_years",
        "irb_data_available", "external_rating_available",
        "applicable_approach", "approach_reason",
    ]]


def build_securitisation(*, asof: str, seed: int = 42,
                         scale: float = 1.0) -> dict[str, pd.DataFrame]:
    """유동화 익스포저 원장 3종과 CRE40~45 산출결과를 만든다.

    같은 (asof, seed, scale) 이면 비트 단위로 같은 결과가 나온다 — 난수는 모두
    default_rng(seed + 테이블 고유 오프셋) 에서만 나오고 시각 의존이 없다.

    `scale` 은 금액 배수다. 값은 이 모듈이 정하지 않고 기관 프로파일 원장
    (`inst_profile.sec_scale`) 에서 온다. 1.0 은 국내 표본 그대로다.
    """
    asof = _validate_asof(asof)
    if not scale > 0:
        raise ValueError(f"금액 배수는 양수여야 한다: {scale}")

    base = _build_master_base(asof, seed, scale)
    tranche = _build_tranche(base, asof, seed)
    pool = _build_pool(base, asof, seed)
    master = _finalise_master(base, tranche, pool)
    result = sec_rwa_summary(master, tranche, pool)

    # --- 생성 직후 자체 점검. 원장이 깨진 채로 하류에 흘러가면 자본이 틀린다.
    for nm, df in (("rdm_sec_master", master), ("rdm_sec_tranche", tranche),
                   ("rdm_sec_pool", pool), ("rwa_sec_result", result)):
        assert not df.empty, f"{nm}이 비었다"

    assert not master.isna().any().any(), "master에 NaN"
    assert not tranche.isna().any().any(), "tranche에 NaN"
    # 풀의 NaN 은 **재유동화 기초(PD/LGD/K_IRB)와 IRB 미승인 딜(K_IRB)** 에만
    # 허용된다. 그 밖의 NaN 은 생성 결함이므로 여기서 막는다.
    nan_ok = {"wa_pd", "wa_lgd", "k_irb"}
    other = [c for c in pool.columns if c not in nan_ok]
    assert not pool[other].isna().any().any(), \
        f"풀의 허용되지 않은 컬럼에 NaN: {pool[other].columns[pool[other].isna().any()].tolist()}"
    sec_seg = pool["irb_asset_class"] == "securitisation"
    assert pool.loc[~sec_seg, ["wa_pd", "wa_lgd"]].notna().all().all(), \
        "일반 세그먼트에 PD/LGD가 비었다"
    assert pool.loc[sec_seg, ["wa_pd", "wa_lgd", "k_irb"]].isna().all().all(), \
        "재유동화 기초 세그먼트에 있을 수 없는 PD/LGD/K_IRB가 있다"
    irb_deals = set(master.loc[master["irb_data_available"], "deal_id"])
    k_notna = pool.groupby("deal_id")["k_irb"].apply(lambda s: s.notna().all())
    assert set(k_notna[k_notna].index) == irb_deals, \
        "K_IRB 보유 딜과 irb_data_available 플래그가 어긋난다"

    # 트렌치 구조: A/D 가 [0,1] 을 빈틈없이 덮어야 SSFA 가 성립한다.
    for deal_id, g in tranche.groupby("deal_id"):
        g = g.sort_values("attachment_point")
        edges = np.concatenate([[0.0], g["detachment_point"].to_numpy()])
        assert np.allclose(edges[:-1], g["attachment_point"].to_numpy(), atol=1e-12), \
            f"{deal_id}: 트렌치 A/D에 빈틈 또는 중첩이 있다"
        assert abs(edges[-1] - 1.0) < 1e-12, f"{deal_id}: 최선순위 D가 1.0이 아니다"
        assert (g["thickness"] > 0).all(), f"{deal_id}: 두께 0 이하 트렌치"
        assert g["senior"].sum() == 1, f"{deal_id}: 선순위 트렌치가 정확히 1개가 아니다"

    # 풀 세그먼트 잔액 합계 = 마스터 풀 잔액 (K_SA·W 분모 정합성)
    seg = pool.groupby("deal_id")["balance"].sum()
    mb = master.set_index("deal_id")["pool_balance"]
    assert np.allclose(seg.to_numpy(), mb.loc[seg.index].to_numpy(), rtol=1e-9), \
        "세그먼트 잔액 합계가 풀 잔액과 불일치 — K_SA 분모가 왜곡된다"

    assert (tranche["holding_amount"] > 0).all(), "보유금액이 0 이하인 트렌치"
    over = tranche["holding_amount"] > tranche["tranche_notional"] * (1 + 1e-9)
    assert not over.any(), "보유금액이 트렌치 발행액을 초과한다"
    assert (master["issue_amount"] <= master["pool_balance"] * (1 + 1e-9)).all(), \
        "발행총액이 풀 잔액을 초과한다"
    assert pool["delinquency_rate"].between(0.0, 1.0).all(), "연체율 범위 초과"
    assert pool["sa_risk_weight"].between(0.0, RW_CAP).all(), "SA 위험가중치 범위 초과"
    assert result["adopted_rw"].between(0.0, RW_CAP).all(), "채택 위험가중치 범위 초과"
    assert (result["adopted_rwa"] >= 0).all(), "채택 RWA가 음수"

    # 세 산출경로가 모두 실제로 쓰이지 않으면 이 원장은 계층을 검증하지 못한다.
    used = set(result["adopted_method"])
    assert used == set(APPROACHES), f"채택되지 않은 산출방법이 있다: {set(APPROACHES) - used}"

    # 보유 잔액 규모 — 원장이 상정한 익스포저 대역(배수 1.0 에서 3천억~1조
    # KRW)을 벗어나면 하류 리포트의 비중이 통째로 어긋난다. 대역은 금액 배수를
    # 따라 움직인다. 배수를 고정 대역에 대보면 규모가 다른 기관이 전부 걸린다.
    total_hold = float(tranche["holding_amount"].sum())
    assert 3.0e11 * scale <= total_hold <= 1.0e12 * scale, \
        f"보유 잔액 합계가 상정 대역(배수 {scale})을 벗어났다: {total_hold:,.0f}"

    return {
        "rdm_sec_master": master,
        "rdm_sec_tranche": tranche,
        "rdm_sec_pool": pool,
        "rwa_sec_result": result,
    }
