"""단기조달·환매조건부매매 원장 (SEC-LIQ-001).

이 저장소의 유동성 산출(LCR·NSFR·생존기간)은 조달을 총액으로만 본다. 조달
건별 원장이 없으면 만기 집중과 거래상대 집중을 볼 수 없다.

원장 네 장이다.

  liq_funding_trade         조달 거래 1건씩(RP매도·콜머니·CP·전단채·차입)
  liq_funding_ladder        만기구간별 도래액과 누적 비중
  liq_funding_concentration 거래상대·상품·담보유형별 집중도
  liq_funding_limit         조달 한도와 그 근거

**한도 판정을 하지 않는다.** 콜차입 한도 같은 감독 한도의 원문을 열람하지
못했다. 한도 원장의 임계 칸은 NULL이고 판정은 '판정불가'로 남는다. 내부한도는
이사회 승인 원장이 있어야 채울 수 있으며 이 저장소에는 없다.

이 모듈의 TableSpec은 아직 datamodel.catalog에 등재하지 않았다. 등재는 실체화
검증과 문서 수치 일치를 함께 만족해야 하므로 배선 단계에서 `SPECS`를 넘긴다.
스펙 품질 기준(입도·기본키·float 단위·FK 대상 존재)은 지금부터 지킨다.

참조: RYNTA BRD SEC-LIQ-001(Repo·단기조달) · SEC-LIQ-002(Liquidity Stress·CFP),
Basel III LCR20·NSF20(조달 안정성), BCBS 144(유동성리스크 관리원칙).
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from risk_lib.alm.params import EVIDENCE_STATUS
from risk_lib.datamodel.spec import ColumnSpec as C, TableSpec

INSTRUMENTS = ("RP매도", "콜머니", "CP발행", "전자단기사채", "은행차입", "기타차입")
COUNTERPARTY_TYPES = ("은행", "자산운용", "보험", "연기금", "일반법인", "증권")
COLLATERAL_KINDS = ("국채", "통안채", "은행채", "회사채", "무담보")
LIMIT_DECISIONS = ("준수", "초과", "판정불가")


FUNDING_TRADE = TableSpec(
    name="liq_funding_trade", korean="조달 거래 원장", product="PRD-ALM",
    grain="조달 거래 1건당 1행",
    columns=(
        C("trade_id", "string", "거래 식별자", nullable=False),
        C("instrument", "string", "조달 수단", nullable=False, allowed=INSTRUMENTS),
        C("counterparty_type", "string", "자금 공급자 구분", nullable=False,
          allowed=COUNTERPARTY_TYPES),
        C("counterparty_id", "string", "자금 공급자 식별자", nullable=False),
        C("principal", "float", "조달 원금", nullable=False, unit="KRW",
          min_value=0.0),
        C("trade_date", "date", "거래일", nullable=False),
        C("maturity_date", "date", "만기일", nullable=False),
        C("tenor_days", "int", "잔존일수", nullable=False, unit="days",
          min_value=0),
        C("rate", "float", "조달금리", nullable=False, unit="ratio",
          min_value=0.0),
        C("is_secured", "bool", "담보부 여부", nullable=False),
        C("collateral_kind", "string", "담보 종류", nullable=False,
          allowed=COLLATERAL_KINDS),
        C("collateral_value", "float", "담보 시가", nullable=False, unit="KRW",
          min_value=0.0),
    ),
    primary_key=("trade_id",),
    note="담보부 조달은 담보 종류를 함께 적는다. 담보 가치가 흔들리면 조달이 먼저 끊긴다.",
)

FUNDING_LADDER = TableSpec(
    name="liq_funding_ladder", korean="조달 만기 사다리", product="PRD-ALM",
    grain="만기구간 1개당 1행",
    columns=(
        C("bucket", "string", "만기구간", nullable=False),
        C("bucket_order", "int", "구간 순서", nullable=False, unit="count",
          min_value=1),
        C("upper_days", "int", "구간 상한 일수", nullable=False, unit="days",
          min_value=1),
        C("amount", "float", "도래액", nullable=False, unit="KRW", min_value=0.0),
        C("share", "float", "비중", nullable=False, unit="ratio", min_value=0.0,
          max_value=1.0),
        C("cumulative_share", "float", "누적 비중", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("secured_amount", "float", "담보부 도래액", nullable=False, unit="KRW",
          min_value=0.0),
    ),
    primary_key=("bucket",),
)

FUNDING_CONCENTRATION = TableSpec(
    name="liq_funding_concentration", korean="조달 집중도", product="PRD-ALM",
    grain="집중 축 x 항목 1건당 1행",
    columns=(
        C("dimension", "string", "집중 축", nullable=False,
          allowed=("거래상대", "상품", "담보종류")),
        C("key", "text", "항목", nullable=False),
        C("amount", "float", "조달액", nullable=False, unit="KRW", min_value=0.0),
        C("share", "float", "비중", nullable=False, unit="ratio", min_value=0.0,
          max_value=1.0),
        C("rank", "int", "축 내 순위", nullable=False, unit="count", min_value=1),
        C("hhi", "float", "축 전체 HHI", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0),
    ),
    primary_key=("dimension", "key"),
)

FUNDING_LIMIT = TableSpec(
    name="liq_funding_limit", korean="조달 한도", product="PRD-ALM",
    grain="한도 1건당 1행",
    columns=(
        C("limit_id", "string", "한도 식별자", nullable=False),
        C("metric", "text", "지표", nullable=False),
        C("threshold", "float", "임계값", nullable=True, unit="ratio",
          min_value=0.0, note="원문 미열람 구간은 NULL이며 판정하지 않는다"),
        C("actual", "float", "실적", nullable=False, unit="ratio", min_value=0.0),
        C("decision", "string", "판정", nullable=False, allowed=LIMIT_DECISIONS),
        C("basis", "text", "근거", nullable=False),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("limit_id",),
)

SPECS: tuple[TableSpec, ...] = (FUNDING_TRADE, FUNDING_LADDER,
                                FUNDING_CONCENTRATION, FUNDING_LIMIT)


# ---------------------------------------------------------------- 적재 표
#
# 조달 구성과 만기 사다리 구간. 이 표가 유일한 데이터 적재 지점이다.
#
# (수단, 건수, 1건 평균 원금, 최소 잔존일, 최대 잔존일, 담보부, 담보종류, 가산금리)
_FUNDING_MIX = (
    ("RP매도", 40, 30_000_000_000.0, 1, 7, True, "국채", 0.0002),
    ("RP매도", 15, 20_000_000_000.0, 8, 90, True, "통안채", 0.0006),
    ("콜머니", 20, 10_000_000_000.0, 1, 1, False, "무담보", 0.0004),
    ("CP발행", 12, 25_000_000_000.0, 30, 180, False, "무담보", 0.0025),
    ("전자단기사채", 18, 15_000_000_000.0, 7, 90, False, "무담보", 0.0018),
    ("은행차입", 8, 50_000_000_000.0, 90, 365, False, "무담보", 0.0035),
    ("기타차입", 5, 20_000_000_000.0, 180, 730, True, "회사채", 0.0050),
)

_COUNTERPARTY_MIX = (("은행", 0.35), ("자산운용", 0.30), ("보험", 0.12),
                     ("연기금", 0.10), ("일반법인", 0.08), ("증권", 0.05))

# 만기 사다리 구간. 운영 관리용 구분이며 감독 규정이 정한 구간은 아니다.
_LADDER = (("익일", 1), ("2~7일", 7), ("8일~1개월", 30), ("1~3개월", 90),
           ("3~6개월", 180), ("6개월~1년", 365), ("1년 초과", 3650))

# 한도 지표. 임계값은 원문 미열람이라 비운다.
_LIMITS = (
    ("FL-CALL", "콜머니 의존도(조달 대비)", None,
     "콜차입 한도 조문 미열람", "미확인"),
    ("FL-ON", "익일물 만기집중도", None,
     "감독 기준 없음. 이사회 승인 내부한도 원장 부재", "미확인"),
    ("FL-CPTY", "단일 자금공급자 집중도", None,
     "감독 기준 없음. 이사회 승인 내부한도 원장 부재", "미확인"),
    ("FL-UNSEC", "무담보 조달 비중", None,
     "감독 기준 없음. 이사회 승인 내부한도 원장 부재", "미확인"),
)

def build_funding_trades(*, asof: str, base_rate: float, seed: int = 42
                         ) -> pd.DataFrame:
    """조달 거래 원장을 만든다.

    base_rate를 인자로 받는다. 무위험금리를 이 모듈이 정하면 같은 금리가
    저장소 안에 두 벌 생긴다.
    """
    rng = np.random.default_rng(seed + 811)
    a = date.fromisoformat(asof)
    cp_kinds = [k for k, _w in _COUNTERPARTY_MIX]
    cp_weights = [w for _k, w in _COUNTERPARTY_MIX]
    rows = []
    n = 0
    for instrument, count, avg, lo, hi, secured, coll, spread in _FUNDING_MIX:
        for _ in range(count):
            n += 1
            principal = float(avg * rng.uniform(0.5, 1.6))
            tenor = int(rng.integers(lo, hi + 1))
            cp_type = str(rng.choice(cp_kinds, p=cp_weights))
            cp_idx = int(rng.integers(1, 13))
            rows.append({
                "trade_id": f"FND-{n:05d}",
                "instrument": instrument,
                "counterparty_type": cp_type,
                "counterparty_id": f"CP-{cp_type}-{cp_idx:02d}",
                "principal": round(principal, 2),
                "trade_date": (a - timedelta(days=int(rng.integers(0, 30)))).isoformat(),
                "maturity_date": (a + timedelta(days=tenor)).isoformat(),
                "tenor_days": tenor,
                "rate": round(base_rate + spread, 6),
                "is_secured": bool(secured),
                "collateral_kind": coll,
                "collateral_value": round(principal * float(rng.uniform(1.01, 1.08)), 2)
                                    if secured else 0.0,
            })
    return pd.DataFrame(rows, columns=[c.name for c in FUNDING_TRADE.columns])


def build_ladder(trades: pd.DataFrame) -> pd.DataFrame:
    """만기 사다리. 구간 경계는 (직전 상한, 상한] 규약을 쓴다."""
    total = float(trades["principal"].sum())
    rows, cum, lower = [], 0.0, 0
    for order, (label, upper) in enumerate(_LADDER, start=1):
        sel = trades[(trades["tenor_days"] > lower) & (trades["tenor_days"] <= upper)]
        amount = float(sel["principal"].sum())
        share = amount / total if total else 0.0
        cum += share
        rows.append({
            "bucket": label, "bucket_order": order, "upper_days": upper,
            "amount": round(amount, 2), "share": round(share, 6),
            "cumulative_share": round(min(cum, 1.0), 6),
            "secured_amount": round(float(sel[sel["is_secured"]]["principal"].sum()), 2),
        })
        lower = upper
    return pd.DataFrame(rows, columns=[c.name for c in FUNDING_LADDER.columns])


def _hhi(shares: pd.Series) -> float:
    return float((shares ** 2).sum())


def build_concentration(trades: pd.DataFrame) -> pd.DataFrame:
    """세 축의 집중도. HHI는 축 전체 값이므로 축 안의 모든 행에 같은 값이 들어간다."""
    total = float(trades["principal"].sum())
    axes = (("거래상대", "counterparty_id"), ("상품", "instrument"),
            ("담보종류", "collateral_kind"))
    rows = []
    for dim, col in axes:
        agg = trades.groupby(col)["principal"].sum().sort_values(ascending=False)
        shares = agg / total if total else agg * 0.0
        h = _hhi(shares)
        for rank, (key, amount) in enumerate(agg.items(), start=1):
            rows.append({
                "dimension": dim, "key": str(key), "amount": round(float(amount), 2),
                "share": round(float(shares[key]), 6), "rank": rank,
                "hhi": round(h, 6),
            })
    return pd.DataFrame(rows, columns=[c.name for c in FUNDING_CONCENTRATION.columns])


def build_limits(trades: pd.DataFrame, ladder: pd.DataFrame,
                 concentration: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """한도 원장. 임계값이 NULL이면 판정하지 않는다. (원장, 건너뛴 사유)를 돌려준다."""
    total = float(trades["principal"].sum())
    call_share = (float(trades[trades["instrument"] == "콜머니"]["principal"].sum())
                  / total if total else 0.0)
    on_share = float(ladder[ladder["bucket"] == "익일"]["share"].iloc[0])
    cpty = concentration[concentration["dimension"] == "거래상대"]
    top_cpty = float(cpty["share"].max()) if len(cpty) else 0.0
    unsecured = (float(trades[~trades["is_secured"]]["principal"].sum()) / total
                 if total else 0.0)
    actual = {"FL-CALL": call_share, "FL-ON": on_share,
              "FL-CPTY": top_cpty, "FL-UNSEC": unsecured}

    skipped, rows = [], []
    for limit_id, metric, threshold, basis, evidence in _LIMITS:
        value = actual[limit_id]
        if threshold is None:
            decision = "판정불가"
            skipped.append(f"{limit_id}: 임계값 NULL ({basis})")
        else:
            decision = "초과" if value > threshold else "준수"
        rows.append({
            "limit_id": limit_id, "metric": metric, "threshold": threshold,
            "actual": round(value, 6), "decision": decision, "basis": basis,
            "evidence_status": evidence,
        })
    frame = pd.DataFrame(rows, columns=[c.name for c in FUNDING_LIMIT.columns]
                         ).astype({"threshold": "float64"})
    return frame, skipped


def build_funding(*, asof: str, base_rate: float, seed: int = 42
                  ) -> tuple[dict[str, pd.DataFrame], list[str]]:
    """조달 원장 4장을 만든다. (원장, 한도 판정을 건너뛴 사유)를 돌려준다."""
    trades = build_funding_trades(asof=asof, base_rate=base_rate, seed=seed)
    ladder = build_ladder(trades)
    conc = build_concentration(trades)
    limits, skipped = build_limits(trades, ladder, conc)
    return ({"liq_funding_trade": trades,
             "liq_funding_ladder": ladder,
             "liq_funding_concentration": conc,
             "liq_funding_limit": limits}, skipped)
