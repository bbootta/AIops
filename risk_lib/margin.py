"""증거금·담보 관리 (SEC-CCR-003).

이 저장소는 SA-CCR EAD와 XVA를 산출하지만 그 앞의 운영 절차가 없었다.
**어떤 계약조건으로 얼마를 주고받아야 하는가**를 원장으로 두지 않으면,
담보 총액은 있는데 그 담보가 계약상 정당한 금액인지 확인할 방법이 없다.

원장 네 장이다.

  ccr_csa_term            네팅세트별 CSA 계약조건(기준금액·최소이전금액·개시증거금)
  ccr_collateral_position 보유 담보와 조정계수 적용 상태
  ccr_margin_call         일별 증거금 콜 산출 결과
  ccr_margin_dispute      평가 차이로 미결된 분쟁

**담보 조정계수(haircut)를 적용하지 않는다.** 감독조정계수를 정한 원문
(신용위험경감 표준방법의 조정계수표)을 열람하지 못했다. 조정계수 칸은 NULL이고
엔진은 임의값을 쓰지 않고 시가를 그대로 담보가치로 본다. 그 결과 담보가치가
과대평가되며 콜 금액이 과소산출된다. 이 방향까지 산출물에 남긴다.

계약조건은 거래상대와 맺은 계약의 내용이므로 원장에 값이 들어간다. 규제 근거가
필요한 값과 계약 사실은 같은 칸에 섞지 않는다.

이 모듈의 TableSpec은 아직 datamodel.catalog에 등재하지 않았다. 등재는 실체화
검증과 문서 수치 일치를 함께 만족해야 하므로 배선 단계에서 `SPECS`를 넘긴다.
스펙 품질 기준(입도·기본키·float 단위·FK 대상 존재)은 지금부터 지킨다.

참조: RYNTA BRD SEC-CCR-003(Margin·Collateral), ISDA CSA 표준조항,
Basel III CRE22(신용위험경감) · CRE52(SA-CCR).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from risk_lib.alm.params import EVIDENCE_STATUS
from risk_lib.datamodel.spec import ColumnSpec as C, ForeignKey as FK, TableSpec

CSA_TYPES = ("양방향", "일방향(수취)", "무담보")
CALL_FREQUENCIES = ("일별", "주별", "월별", "해당없음")
COLLATERAL_TYPES = ("현금", "국채", "통안채", "은행채", "회사채", "주식")
CALL_DIRECTIONS = ("수취", "지급", "해당없음")
CALL_STATUSES = ("충족", "콜발생", "미이행", "분쟁")
DISPUTE_STATUSES = ("접수", "협의중", "해소")


CSA_TERM = TableSpec(
    name="ccr_csa_term", korean="CSA 계약조건", product="PRD-MKT",
    grain="네팅세트 1건당 1행",
    columns=(
        C("netting_set_id", "string", "네팅세트 식별자", nullable=False),
        C("counterparty", "string", "거래상대", nullable=False),
        C("csa_type", "string", "담보약정 유형", nullable=False, allowed=CSA_TYPES),
        C("threshold", "float", "기준금액", nullable=False, unit="KRW",
          min_value=0.0, note="이 금액까지는 담보를 요구하지 않는다"),
        C("mta", "float", "최소이전금액", nullable=False, unit="KRW", min_value=0.0),
        C("independent_amount", "float", "개시증거금", nullable=False, unit="KRW",
          min_value=0.0),
        C("call_frequency", "string", "정산주기", nullable=False,
          allowed=CALL_FREQUENCIES),
        C("mpor_days", "float", "위험보유기간", nullable=True, unit="days",
          min_value=0.0,
          note="감독 최소기간 원문 미열람. 계약상 정산주기만 기록한다"),
        C("currency", "string", "적격담보 통화", nullable=False),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("netting_set_id",),
    note="계약조건은 거래상대와 맺은 사실이다. 규제 계수와 같은 칸에 두지 않는다.",
)

COLLATERAL_POSITION = TableSpec(
    name="ccr_collateral_position", korean="담보 보유 현황", product="PRD-MKT",
    grain="네팅세트 x 담보 종류 1건당 1행",
    columns=(
        C("position_id", "text", "담보 포지션 식별자", nullable=False),
        C("netting_set_id", "string", "네팅세트 식별자", nullable=False),
        C("collateral_type", "string", "담보 종류", nullable=False,
          allowed=COLLATERAL_TYPES),
        C("market_value", "float", "시가", nullable=False, unit="KRW",
          min_value=0.0),
        C("supervisory_haircut", "float", "감독조정계수", nullable=True,
          unit="ratio", min_value=0.0, max_value=1.0,
          note="조정계수표 원문 미열람이라 전건 NULL이다"),
        C("collateral_value", "float", "담보가치", nullable=False, unit="KRW",
          min_value=0.0),
        C("haircut_status", "text", "조정계수 적용 상태", nullable=False),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("position_id",),
    foreign_keys=(FK(("netting_set_id",), "ccr_csa_term", ("netting_set_id",)),),
)

MARGIN_CALL = TableSpec(
    name="ccr_margin_call", korean="증거금 콜", product="PRD-MKT",
    grain="네팅세트 x 산출일 1건당 1행",
    columns=(
        C("call_id", "text", "콜 식별자", nullable=False),
        C("netting_set_id", "string", "네팅세트 식별자", nullable=False),
        C("asof", "date", "산출 기준일", nullable=False),
        C("exposure", "float", "네팅 후 익스포저", nullable=False, unit="KRW"),
        C("independent_amount", "float", "개시증거금", nullable=False, unit="KRW",
          min_value=0.0),
        C("threshold", "float", "기준금액", nullable=False, unit="KRW",
          min_value=0.0),
        C("required_margin", "float", "소요 증거금", nullable=False, unit="KRW",
          min_value=0.0),
        C("collateral_value", "float", "보유 담보가치", nullable=False, unit="KRW",
          min_value=0.0),
        C("call_amount", "float", "콜 금액", nullable=False, unit="KRW"),
        C("direction", "string", "방향", nullable=False, allowed=CALL_DIRECTIONS),
        C("status", "string", "상태", nullable=False, allowed=CALL_STATUSES),
        C("reason", "text", "판정 사유", nullable=False),
    ),
    primary_key=("call_id",),
    foreign_keys=(FK(("netting_set_id",), "ccr_csa_term", ("netting_set_id",)),),
    note="콜 금액이 최소이전금액에 못 미치면 0으로 둔다. 계약상 이전 의무가 없기 때문이다.",
)

MARGIN_DISPUTE = TableSpec(
    name="ccr_margin_dispute", korean="증거금 분쟁", product="PRD-MKT",
    grain="분쟁 1건당 1행",
    columns=(
        C("dispute_id", "text", "분쟁 식별자", nullable=False),
        C("netting_set_id", "string", "네팅세트 식별자", nullable=False),
        C("raised_on", "date", "제기일", nullable=False),
        C("our_valuation", "float", "당행 평가액", nullable=False, unit="KRW"),
        C("their_valuation", "float", "상대 평가액", nullable=False, unit="KRW"),
        C("gap", "float", "평가 차이", nullable=False, unit="KRW"),
        C("gap_ratio", "float", "차이 비율", nullable=False, unit="ratio"),
        C("days_open", "int", "미결 일수", nullable=False, unit="days",
          min_value=0),
        C("status", "string", "상태", nullable=False, allowed=DISPUTE_STATUSES),
    ),
    primary_key=("dispute_id",),
    foreign_keys=(FK(("netting_set_id",), "ccr_csa_term", ("netting_set_id",)),),
)

SPECS: tuple[TableSpec, ...] = (CSA_TERM, COLLATERAL_POSITION, MARGIN_CALL,
                                MARGIN_DISPUTE)


# ---------------------------------------------------------------- 계약조건 적재
#
# CSA 계약조건 구간표. 거래상대 규모에 따라 어떤 조건을 맺는지를 원장 한 곳에
# 적는다. 산출 함수는 이 표를 참조하지 않고 인자로 받은 원장만 본다.
#
# (구간 상한 비중, csa_type, threshold 비율, mta 비율, ia 비율, 정산주기)
_CSA_TIERS = (
    (0.30, "양방향", 0.00, 0.0005, 0.010, "일별"),
    (0.70, "양방향", 0.02, 0.0010, 0.005, "일별"),
    (0.90, "일방향(수취)", 0.05, 0.0020, 0.000, "주별"),
    (1.01, "무담보", 1.00, 0.0000, 0.000, "해당없음"),
)

# 담보 구성 비중. 종류별 시가 배분에 쓴다.
_COLLATERAL_MIX = (("현금", 0.45), ("국채", 0.30), ("통안채", 0.10),
                   ("은행채", 0.10), ("회사채", 0.05))

# 감독조정계수는 원문을 열람하지 못했다. 종류별로 칸만 두고 값은 비운다.
_SUPERVISORY_HAIRCUT: dict[str, float | None] = {t: None for t, _w in _COLLATERAL_MIX}


def build_csa_terms(trades: pd.DataFrame) -> pd.DataFrame:
    """거래상대별 네팅세트와 CSA 조건을 만든다.

    구간 배정은 거래상대 식별자의 순위로 정한다. 난수로 배정하면 같은 거래상대가
    실행마다 다른 계약조건을 갖는다.
    """
    agg = (trades.groupby("counterparty")
           .agg(notional=("notional", "sum"), mtm=("mtm", "sum"))
           .reset_index().sort_values("counterparty").reset_index(drop=True))
    n = len(agg)
    rows = []
    for i, r in agg.iterrows():
        q = (i + 1) / max(n, 1)
        tier = next(t for t in _CSA_TIERS if q <= t[0])
        _cut, csa_type, thr_r, mta_r, ia_r, freq = tier
        notional = float(r["notional"])
        rows.append({
            "netting_set_id": f"NS-{r['counterparty']}",
            "counterparty": str(r["counterparty"]),
            "csa_type": csa_type,
            "threshold": round(notional * thr_r, 2) if csa_type != "무담보"
                         else round(notional, 2),
            "mta": round(notional * mta_r, 2),
            "independent_amount": round(notional * ia_r, 2),
            "call_frequency": freq,
            "mpor_days": None,
            "currency": "KRW",
            "evidence_status": "재량·미규정",
        })
    return pd.DataFrame(rows, columns=[c.name for c in CSA_TERM.columns]
                        ).astype({"mpor_days": "float64"})


def build_collateral_positions(csa: pd.DataFrame, trades: pd.DataFrame,
                               exposures: pd.DataFrame, *, seed: int = 42
                               ) -> tuple[pd.DataFrame, list[str]]:
    """보유 담보를 종류별로 나눠 원장에 싣는다. (원장, 경고)를 돌려준다.

    담보 총액에 두 가지 가정을 쓴다. 이 가정은 빌더에 있고 산출 함수에는 없다.

    1. 실제 보유 담보는 계약상 소요 증거금을 크게 넘지 않는다. 합성 파생원장의
       collateral 컬럼은 소요액과 무관하게 만들어져 있어 그대로 쓰면 전건이
       초과담보로 나온다. 거래원장 담보 합과 소요 증거금 x 이행률 중 작은 값을 쓴다.
    2. 이행률은 정산 지연을 반영해 네팅세트별로 결정론 난수 스트림에서 뽑는다.

    종류 배분은 고정 비중을 쓰고 조정계수는 비어 있으므로 담보가치가 시가 그대로 남는다.
    """
    held = (trades.groupby("counterparty")["collateral"].sum()
            if "collateral" in trades.columns
            else pd.Series(dtype="float64"))
    exp = exposures.set_index("netting_set_id")["exposure"]
    rng = np.random.default_rng(seed + 734)
    warnings: list[str] = []
    rows = []
    for _, c in csa.iterrows():
        ns = str(c["netting_set_id"])
        required = max(0.0, float(exp.get(ns, 0.0))
                       + float(c["independent_amount"]) - float(c["threshold"]))
        settlement_ratio = float(rng.uniform(0.6, 1.2))
        total = min(float(held.get(c["counterparty"], 0.0)),
                    required * settlement_ratio)
        if total <= 0:
            continue
        for kind, weight in _COLLATERAL_MIX:
            mv = round(total * weight, 2)
            hc = _SUPERVISORY_HAIRCUT.get(kind)
            if hc is None:
                value, status = mv, "미적용(감독조정계수 미확인)"
                evidence = "미확인"
            else:
                value, status = round(mv * (1 - hc), 2), "적용"
                evidence = "원문확인"
            rows.append({
                "position_id": f"{c['netting_set_id']}-{kind}",
                "netting_set_id": str(c["netting_set_id"]),
                "collateral_type": kind, "market_value": mv,
                "supervisory_haircut": hc, "collateral_value": value,
                "haircut_status": status, "evidence_status": evidence,
            })
    frame = pd.DataFrame(rows, columns=[c.name for c in COLLATERAL_POSITION.columns]
                         ).astype({"supervisory_haircut": "float64"})
    n_skipped = int(frame["supervisory_haircut"].isna().sum()) if len(frame) else 0
    if n_skipped:
        warnings.append(
            f"담보 조정계수 미확인으로 {n_skipped}건에 조정을 적용하지 않았다. "
            f"담보가치가 과대평가되고 콜 금액이 과소산출된다")
    return frame, warnings


# ---------------------------------------------------------------- 산출 엔진

def compute_margin_calls(csa: pd.DataFrame, collateral: pd.DataFrame,
                         exposures: pd.DataFrame, *, asof: str) -> pd.DataFrame:
    """네팅세트별 증거금 콜을 산출한다. 계수는 전부 인자로 받은 원장에서 온다.

    소요 증거금 = max(0, 익스포저 + 개시증거금 - 기준금액)
    콜 금액     = 소요 증거금 - 보유 담보가치
    콜 금액의 절대값이 최소이전금액에 못 미치면 이전 의무가 없으므로 0으로 둔다.
    """
    held = (collateral.groupby("netting_set_id")["collateral_value"].sum()
            if len(collateral) else pd.Series(dtype="float64"))
    exp = exposures.set_index("netting_set_id")["exposure"]
    rows = []
    for _, c in csa.iterrows():
        ns = str(c["netting_set_id"])
        exposure = float(exp.get(ns, 0.0))
        ia, thr, mta = (float(c["independent_amount"]), float(c["threshold"]),
                        float(c["mta"]))
        required = max(0.0, exposure + ia - thr)
        collateral_value = float(held.get(ns, 0.0))
        raw_call = required - collateral_value
        if abs(raw_call) < mta:
            call, direction = 0.0, "해당없음"
            status = "충족"
            reason = f"콜 금액 {raw_call:,.0f}이 최소이전금액 {mta:,.0f} 미만"
        else:
            call = raw_call
            direction = "수취" if call > 0 else "지급"
            status = "콜발생"
            reason = (f"소요 {required:,.0f} 대비 보유 {collateral_value:,.0f}, "
                      f"{direction} {abs(call):,.0f}")
        rows.append({
            "call_id": f"MC-{asof.replace('-', '')}-{ns}",
            "netting_set_id": ns, "asof": asof, "exposure": round(exposure, 2),
            "independent_amount": ia, "threshold": thr,
            "required_margin": round(required, 2),
            "collateral_value": round(collateral_value, 2),
            "call_amount": round(call, 2), "direction": direction,
            "status": status, "reason": reason,
        })
    return pd.DataFrame(rows, columns=[c.name for c in MARGIN_CALL.columns])


def build_disputes(calls: pd.DataFrame, *, asof: str, seed: int = 42,
                   gap_ratio: float = 0.03, n_disputes: int = 3
                   ) -> pd.DataFrame:
    """콜이 발생한 네팅세트 중 상위 몇 건에 평가 분쟁을 만든다.

    분쟁 대상은 콜 금액 순으로 고른다. 난수로 고르면 같은 원장이 실행마다
    다른 분쟁을 낸다. 평가 차이 비율과 미결 일수만 결정론 난수 스트림으로 준다.
    """
    empty = pd.DataFrame(columns=[c.name for c in MARGIN_DISPUTE.columns]).astype(
        {"our_valuation": "float64", "their_valuation": "float64",
         "gap": "float64", "gap_ratio": "float64", "days_open": "int64"})
    live = calls[calls["status"] == "콜발생"].copy()
    if live.empty:
        return empty
    live = live.reindex(live["call_amount"].abs().sort_values(ascending=False).index)
    rng = np.random.default_rng(seed + 733)
    rows = []
    for i, (_, r) in enumerate(live.head(n_disputes).iterrows(), start=1):
        ours = float(r["required_margin"])
        gap = ours * gap_ratio * float(rng.uniform(0.5, 1.5))
        days = int(rng.integers(1, 15))
        rows.append({
            "dispute_id": f"MD-{asof.replace('-', '')}-{i:03d}",
            "netting_set_id": str(r["netting_set_id"]), "raised_on": asof,
            "our_valuation": round(ours, 2),
            "their_valuation": round(ours - gap, 2),
            "gap": round(gap, 2),
            "gap_ratio": round(gap / ours, 6) if ours else 0.0,
            "days_open": days,
            "status": "협의중" if days >= 5 else "접수",
        })
    return pd.DataFrame(rows, columns=[c.name for c in MARGIN_DISPUTE.columns])


def mark_disputed(calls: pd.DataFrame, disputes: pd.DataFrame) -> pd.DataFrame:
    """분쟁이 걸린 콜의 상태를 갱신한다. 분쟁 중인 콜을 '충족'으로 두면 안 된다."""
    if disputes.empty:
        return calls
    out = calls.copy()
    hit = out["netting_set_id"].isin(set(disputes["netting_set_id"]))
    out.loc[hit, "status"] = "분쟁"
    out.loc[hit, "reason"] = out.loc[hit, "reason"] + " · 평가 분쟁 미결"
    return out


def netting_set_exposures(trades: pd.DataFrame) -> pd.DataFrame:
    """거래원장에서 네팅세트별 익스포저를 만든다.

    네팅 후 시가가 음수이면 익스포저는 0이다. 우리가 받을 것이 없기 때문이다.
    """
    agg = trades.groupby("counterparty")["mtm"].sum().reset_index()
    agg["netting_set_id"] = "NS-" + agg["counterparty"].astype(str)
    agg["exposure"] = agg["mtm"].clip(lower=0.0)
    return agg[["netting_set_id", "exposure"]]


def build_margin(trades: pd.DataFrame, *, asof: str, seed: int = 42
                 ) -> tuple[dict[str, pd.DataFrame], list[str]]:
    """증거금·담보 원장 4장을 만든다. (원장, 경고)를 돌려준다."""
    csa = build_csa_terms(trades)
    exposures = netting_set_exposures(trades)
    collateral, warnings = build_collateral_positions(csa, trades, exposures,
                                                      seed=seed)
    calls = compute_margin_calls(csa, collateral, exposures, asof=asof)
    disputes = build_disputes(calls, asof=asof, seed=seed)
    calls = mark_disputed(calls, disputes)
    return ({"ccr_csa_term": csa,
             "ccr_collateral_position": collateral,
             "ccr_margin_call": calls,
             "ccr_margin_dispute": disputes}, warnings)
