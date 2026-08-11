"""Attribution / Bridge analyses.

Answers the CRO's "why did this number move?" question by decomposing the
change between two PipelineResults into additive drivers.

  - capital_bridge:    CET1 ratio change  → (capital effect) + (RWA effect)
  - rwa_bridge:        final RWA change   → SA / IRB / market / op / floor
  - ecl_bridge:        ECL change         → PD / LGD / EAD / mix
  - lcr_bridge:        LCR change         → HQLA / outflows / inflows

For single-snapshot use we also expose `decompose_*` helpers that explain
the *current* value in terms of underlying drivers (no second snapshot
needed): e.g. RWA decomposed into its identity components, CET1 surplus
decomposed into capital headroom vs RWA headroom vs buffer requirement.

All numbers carry units of the underlying metric (currency or ratio %),
not pp/%pp ambiguity, so callers can sum drivers and reconcile to the
total without sign confusion.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Any

import pandas as pd


class AttributionWarning(UserWarning):
    """귀속 분해가 산출 항등식이나 원장 합계와 어긋났을 때 남기는 경고."""


@dataclass
class BridgeStep:
    label: str
    value: float                 # signed contribution
    cumulative: float            # running total after this step
    note: str = ""


@dataclass
class Bridge:
    metric: str
    start_value: float
    end_value: float
    steps: list[BridgeStep] = field(default_factory=list)

    @property
    def explained_change(self) -> float:
        return sum(s.value for s in self.steps)

    @property
    def residual(self) -> float:
        return (self.end_value - self.start_value) - self.explained_change

    def to_frame(self) -> pd.DataFrame:
        rows = [{"label": "기초 " + self.metric, "value": self.start_value,
                 "cumulative": self.start_value, "note": ""}]
        for s in self.steps:
            rows.append({"label": s.label, "value": s.value,
                         "cumulative": s.cumulative, "note": s.note})
        rows.append({"label": "기말 " + self.metric, "value": self.end_value,
                     "cumulative": self.end_value, "note": "잔차 %+.4g" % self.residual})
        return pd.DataFrame(rows)


# ---------------------------------------------------------------- bridges

def capital_bridge(a: Any, b: Any) -> Bridge:
    """CET1 ratio change between snapshot A → B, split into capital and RWA effects.

    CET1_b - CET1_a
       = (CET1_b - CET1_a) / RWA_a                     # capital effect
       + CET1_b * (1/RWA_b - 1/RWA_a)                  # RWA effect
    plus a small cross-term we attribute proportionally.
    """
    Ka, Kb = a.meta["capital"].cet1, b.meta["capital"].cet1
    Ra, Rb = a.bis.rwa, b.bis.rwa
    cet1_a, cet1_b = Ka / Ra, Kb / Rb

    capital_eff = (Kb - Ka) / Ra
    rwa_eff = Kb * (1.0 / Rb - 1.0 / Ra)
    steps = [
        BridgeStep("자본 증감 효과", capital_eff, cet1_a + capital_eff,
                   note=f"CET1 자본 {Ka/1e9:+.0f}→{Kb/1e9:+.0f}십억"),
        BridgeStep("RWA 증감 효과", rwa_eff, cet1_a + capital_eff + rwa_eff,
                   note=f"RWA {Ra/1e12:.2f}→{Rb/1e12:.2f}조"),
    ]
    return Bridge(metric="CET1 비율", start_value=cet1_a, end_value=cet1_b,
                  steps=steps)


def rwa_bridge(a: Any, b: Any) -> Bridge:
    """최종 RWA 변화 A → B를 항등식 구성요소별 변화로 가른다.

    예전에는 SA·IRB·시장·운영 네 항만 직접 빼고 남는 차이를 전부
    "Output floor 가산 변화" 한 줄에 넣었다. 거래상대방신용과 구조화가 그 줄
    안으로 사라졌고, 한쪽 스냅샷에만 그 두 항이 있으면 산출하한이 움직인
    것처럼 보였다. 1단 분해(`decompose_rwa`)와 같은 항을 같은 순서로 읽고,
    남는 차이도 같은 방식으로 "미배분" 줄에 드러낸다.

    구성요소별 변화의 합은 언제나 `final_total` 변화와 같다(`residual == 0`).
    """
    da = decompose_rwa(a).set_index("component")["rwa"]
    db = decompose_rwa(b).set_index("component")["rwa"]
    labels = list(da.index) + [c for c in db.index if c not in set(da.index)]

    cum = float(a.rwa["final_total"])
    steps = []
    for label in labels:
        d = float(db.get(label, 0.0)) - float(da.get(label, 0.0))
        cum += d
        steps.append(BridgeStep(label, d, cum))
    return Bridge(metric="최종 RWA", start_value=float(a.rwa["final_total"]),
                  end_value=float(b.rwa["final_total"]), steps=steps)


def ecl_bridge(a: Any, b: Any) -> Bridge:
    """TTC ECL change A → B, decomposed into PD-effect, LGD-effect,
    EAD-effect using the IRB book mean PD, LGD, EAD on each side and the
    Marshall-Edgeworth attribution (avg of two-period weights).

    ECL ≈ PD · LGD · EAD (Stage-1 12M, dominant component).
    """
    da, db = a.ecl["by_stage"], b.ecl["by_stage"]
    ecl_a = float(a.ecl["total"]); ecl_b = float(b.ecl["total"])

    # Aggregate PD/LGD/EAD over Stage 1+2 EAD-weighted (use coverage as proxy).
    # We use total ECL / total EAD and assume PD·LGD = coverage; that lets us
    # decompose into a "rate" effect (coverage) and an "EAD" effect.
    ead_a = float(da["ead"].sum()); ead_b = float(db["ead"].sum())
    rate_a = ecl_a / ead_a if ead_a else 0.0
    rate_b = ecl_b / ead_b if ead_b else 0.0

    # Marshall-Edgeworth: Δ = Δrate · (EAD_a + EAD_b)/2 + Δead · (rate_a + rate_b)/2
    rate_eff = (rate_b - rate_a) * (ead_a + ead_b) / 2
    ead_eff  = (ead_b - ead_a) * (rate_a + rate_b) / 2
    steps = [
        BridgeStep("EAD 규모 효과", ead_eff, ecl_a + ead_eff,
                   note=f"EAD {ead_a/1e12:.2f}→{ead_b/1e12:.2f}조"),
        BridgeStep("PD·LGD(커버리지) 효과", rate_eff, ecl_a + ead_eff + rate_eff,
                   note=f"평균 커버리지 {rate_a*100:.2f}→{rate_b*100:.2f}%"),
    ]
    return Bridge(metric="TTC ECL", start_value=ecl_a, end_value=ecl_b,
                  steps=steps)


def lcr_bridge(a: Any, b: Any) -> Bridge:
    """LCR change A → B, attribution to HQLA, outflow, inflow legs."""
    la, lb = a.alm["lcr"], b.alm["lcr"]
    # LCR = HQLA / Net.  ΔLCR ≈ ΔHQLA/Net_a + HQLA_b·Δ(1/Net).
    h_eff = (lb.hqla_total - la.hqla_total) / la.net_outflow
    net_eff = lb.hqla_total * (1.0 / lb.net_outflow - 1.0 / la.net_outflow)
    # Further split net_eff into gross-outflow and inflow drivers.
    da_outflow = (lb.gross_outflow - la.gross_outflow)
    da_inflow  = (lb.inflow_capped - la.inflow_capped)
    # weight by share of the Δnet
    dnet = (lb.net_outflow - la.net_outflow) or 1.0
    w_out = da_outflow / dnet if dnet else 0.5
    w_in = (-da_inflow) / dnet if dnet else 0.5
    out_eff = net_eff * w_out
    in_eff  = net_eff * w_in
    cum = la.lcr
    steps = [
        BridgeStep("HQLA 증감", h_eff, (cum := cum + h_eff)),
        BridgeStep("총유출 증감", out_eff, (cum := cum + out_eff)),
        BridgeStep("유입 증감", in_eff, (cum := cum + in_eff)),
    ]
    return Bridge(metric="LCR", start_value=la.lcr, end_value=lb.lcr,
                  steps=steps)


# ---------------------------------------------------------------- single-snapshot

def decompose_cet1_headroom(result: Any) -> pd.DataFrame:
    """Explain the CET1 surplus as the gap between actual and three layers."""
    bis = result.bis
    layers = ["최저 (CRE10.4)", "+자본보전버퍼", "+CCyB+DSIB"]
    cet1_min = 0.045
    ccb = bis.required["cet1"] - cet1_min       # ccb + ccyb + dsib lumped
    rows = [
        {"layer": "최저", "required": cet1_min, "actual": bis.cet1_ratio,
         "headroom": bis.cet1_ratio - cet1_min},
        {"layer": "최저+CCB", "required": cet1_min + 0.025,
         "actual": bis.cet1_ratio,
         "headroom": bis.cet1_ratio - (cet1_min + 0.025)},
        {"layer": "최저+CCB+CCyB+DSIB (감독요구)", "required": bis.required["cet1"],
         "actual": bis.cet1_ratio,
         "headroom": bis.cet1_ratio - bis.required["cet1"]},
    ]
    return pd.DataFrame(rows)


# 최종 RWA 항등식의 구성요소. `pipeline._stage_capital`
#   rwa_internal_total = sa + irb + ccr + market + op + structured
# 와 `validation.cross_domain._rwa_vs_bis`
#   expected = sa + irb + ccr + market + op + structured + floor_add_on
# 가 같은 항등식을 쓴다. 여기도 같은 항으로 읽는다.
#
# 이 표는 예전에 네 항(SA·IRB·시장·운영)만 직접 읽고 나머지를 잔차로
# "Output floor 가산"에 몰아넣었다. 그래서 거래상대방신용(SA-CCR + CVA)과
# 구조화(집합투자증권·유동화)가 산출하한 가산으로 표시됐다. 잔차는 빠진
# 항목을 남은 항목 안에 숨긴다. 각 항을 직접 읽고, 남으면 남은 만큼을
# 별도 행으로 드러낸다.
_SA_LABEL = "신용 SA"
_IRB_LABEL = "신용 IRB"
_MARKET_LABEL = "시장리스크"
_OP_LABEL = "운영리스크"
_RWA_COMPONENT_KEYS: tuple[tuple[str, str], ...] = (
    ("sa", _SA_LABEL),
    ("irb", _IRB_LABEL),
    ("ccr", "거래상대방신용"),
    ("market", _MARKET_LABEL),
    ("op", _OP_LABEL),
    ("structured_total", "구조화"),
)
_FLOOR_LABEL = "Output floor 가산"
_UNALLOCATED_LABEL = "미배분"
_RWA_TOL = 1e-9      # final_total 대비 상대 허용오차


def _rwa_components(rwa: dict) -> list[tuple[str, float]]:
    """항등식 구성요소를 순서대로 직접 읽는다. 없는 키는 경고로 남긴다."""
    missing = [k for k, _ in _RWA_COMPONENT_KEYS if rwa.get(k) is None]
    rows = [(label, float(rwa.get(key) or 0.0))
            for key, label in _RWA_COMPONENT_KEYS]
    floor = rwa.get("output_floor")
    if floor is None:
        missing.append("output_floor")
    rows.append((_FLOOR_LABEL,
                 float(getattr(floor, "add_on", 0.0) or 0.0)))
    if missing:
        warnings.warn(
            "RWA 구성요소가 결과에 없다: " + ", ".join(missing)
            + ". 해당 항을 0으로 두므로 합계가 최종 RWA와 어긋난다",
            AttributionWarning, stacklevel=3)
    return rows


def decompose_rwa(result: Any) -> pd.DataFrame:
    """최종 RWA를 항등식 구성요소로 가른다 (1단).

    합이 `final_total`과 어긋나면 그 차이를 "미배분" 행으로 드러내고 경고를
    남긴다. 어느 항에도 흡수시키지 않는다.
    """
    rwa = result.rwa
    total = float(rwa["final_total"])
    rows = _rwa_components(rwa)
    residual = total - sum(v for _, v in rows)
    if abs(residual) > max(abs(total), 1.0) * _RWA_TOL:
        rows.append((_UNALLOCATED_LABEL, residual))
        warnings.warn(
            f"RWA 구성요소 합이 최종 RWA와 {residual:+,.0f} 어긋난다. "
            f"차이를 '{_UNALLOCATED_LABEL}' 행으로 남긴다",
            AttributionWarning, stacklevel=2)
    denom = total if total else 1.0
    return pd.DataFrame([{"component": k, "rwa": v, "share": v / denom}
                         for k, v in rows])


# ---------------------------------------------------------------- 2단 분해

# 1단 구성요소를 한 번 더 가르는 축과 그 원장. 값은 원장에서 굴리고 화면은
# 굴리지 않는다. 거래상대방신용·구조화·산출하한 가산은 여기에 없다.
# 산출하한 가산은 표준방법 총액 대비 집계 수준 max()라 자산분류별 정체성이
# 없다. 쪼개면 산출이 아니라 배분을 지어내는 것이 된다.
_RWA_DETAIL_AXIS: dict[str, tuple[str, str]] = {
    _SA_LABEL: ("rwa_sa_bucket", "asset_class"),
    _IRB_LABEL: ("rwa_irb_pool", "asset_class"),
    _MARKET_LABEL: ("rwa_market_component", "risk_class"),
}
_OP_LEDGER = "rwa_operational_bi"
_OP_NOTE = ("운영리스크는 BI 구성비로 배분한 값이다. BI에서 BIC로 가는 "
            "환산이 구간별 한계계수 합이라 비선형이므로(OPE25.5) 구성요소별 "
            "RWA는 관측값이 아니라 선택한 배분이다")


def _split_by_ledger(tbl: pd.DataFrame, axis: str, target: float,
                     group: str) -> list[tuple[str, float]] | None:
    """원장을 축으로 집계한다. 합이 1단 값과 다르면 가르지 않는다."""
    if tbl is None or not isinstance(tbl, pd.DataFrame) or tbl.empty:
        return None
    if axis not in tbl.columns or "rwa" not in tbl.columns:
        return None
    g = tbl.groupby(axis, as_index=False)["rwa"].sum()
    rows = [(str(r[axis]), float(r["rwa"])) for _, r in g.iterrows()]
    got = sum(v for _, v in rows)
    if abs(got - target) > max(abs(target), 1.0) * 1e-6:
        warnings.warn(
            f"{group} 2단 원장 합({got:,.0f})이 1단 값({target:,.0f})과 "
            "다르다. 가르지 않고 1단 잎으로 둔다",
            AttributionWarning, stacklevel=3)
        return None
    return rows


def _split_operational(tbl: pd.DataFrame, target: float
                       ) -> list[tuple[str, float]] | None:
    """BI 구성비로 운영리스크 RWA를 배분한다.

    `rwa_operational_bi`의 단위는 사업지표(BI) 원화이지 RWA가 아니다.
    share 컬럼으로 배분한다.
    """
    if tbl is None or not isinstance(tbl, pd.DataFrame) or tbl.empty:
        return None
    if "share" not in tbl.columns or "component" not in tbl.columns:
        return None
    shares = tbl["share"].astype(float)
    if abs(float(shares.sum()) - 1.0) > 1e-9:
        warnings.warn(
            f"{_OP_LEDGER}의 구성비 합이 1이 아니다"
            f"({float(shares.sum()):.6f}). 운영리스크를 가르지 않는다",
            AttributionWarning, stacklevel=3)
        return None
    rows = [(str(c), target * float(s))
            for c, s in zip(tbl["component"], shares, strict=True)]
    # 부동소수 오차를 마지막 행에 몰아 1단 값과 정확히 맞춘다.
    drift = target - sum(v for _, v in rows)
    if rows:
        rows[-1] = (rows[-1][0], rows[-1][1] + drift)
    return rows


def decompose_rwa_detail(result: Any,
                         tables: dict[str, pd.DataFrame] | None = None
                         ) -> pd.DataFrame:
    """최종 RWA를 1단 구성요소 + 2단 축으로 가른다.

    반환 프레임은 잎 행만 담는다. `group`이 1단 구성요소, `label`이 2단
    항목이고, 가르지 않는 구성요소는 `group == label`인 한 행으로 남는다.
    `value` 합은 언제나 `final_total`과 같다. 1단 프레임(`decompose_rwa`)과
    같은 값에서 나오므로 두 표가 갈라지지 않는다.

    2단 원장이 없으면 그 구성요소는 잎으로 남고 note에 사유가 적힌다.
    """
    tables = tables or {}
    total = float(result.rwa["final_total"])
    denom = total if total else 1.0
    out: list[dict[str, Any]] = []

    for _, row in decompose_rwa(result).iterrows():
        group, value = str(row["component"]), float(row["rwa"])
        kids: list[tuple[str, float]] | None = None
        source, note = "", ""
        if group in _RWA_DETAIL_AXIS:
            ledger, axis = _RWA_DETAIL_AXIS[group]
            kids = _split_by_ledger(tables.get(ledger), axis, value, group)
            source, note = f"{ledger}.{axis}", ""
            if kids is None:
                note = f"2단 원장({ledger})이 없거나 합이 맞지 않아 가르지 않았다"
        elif group == _OP_LABEL:
            kids = _split_operational(tables.get(_OP_LEDGER), value)
            source, note = f"{_OP_LEDGER}.component", _OP_NOTE
            if kids is None:
                note = (f"2단 원장({_OP_LEDGER})이 없거나 구성비 합이 1이 "
                        "아니어서 가르지 않았다")
        if kids is None:
            # 가르지 못했으면 원장 이름을 출처로 남기지 않는다. 쓰지 않은
            # 원장을 출처로 적으면 그 원장에서 나온 값처럼 읽힌다.
            out.append({"group": group, "label": group, "value": value,
                        "share": value / denom, "source": "", "note": note})
            continue
        for name, v in kids:
            out.append({"group": group, "label": name, "value": v,
                        "share": v / denom, "source": source, "note": note})
    return pd.DataFrame(out, columns=["group", "label", "value", "share",
                                      "source", "note"])
