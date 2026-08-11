"""RWA 귀속 분해 (1단 항등식 · 2단 원장 축).

이 시험이 고정하는 것은 두 가지다.

1. 1단은 최종 RWA 항등식의 **각 항을 직접 읽는다**. 예전에는 SA·IRB·시장·
   운영 네 항만 읽고 나머지를 잔차로 "Output floor 가산"에 몰아넣어,
   거래상대방신용(SA-CCR + CVA)과 구조화(집합투자증권·유동화)가 산출하한
   가산 안에 숨어 있었다. 잔차가 남으면 "미배분" 행으로 드러나야 한다.
2. 2단 합은 그 1단 값과 정확히 같다. 원장이 어긋나면 가르지 않고 경고를
   남긴다. 어긋난 채로 그리면 화면이 틀린 값을 말한다.

항등식 위반을 실제로 주입해 시험이 실패하는지도 함께 고정한다.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
import pytest

from risk_lib.attribution import (
    AttributionWarning, decompose_rwa, decompose_rwa_detail,
)


# ---------------------------------------------------------------- 합성 입력
# 파이프라인을 돌리지 않고 항등식만 시험하는 최소 입력. 값은 자릿수만 다르게
# 둔 임의의 숫자이고 규제 의미가 없다.

@dataclass
class _Floor:
    add_on: float


@dataclass
class _Shim:
    rwa: dict[str, Any] = field(default_factory=dict)


_SA, _IRB, _CCR = 1_000.0, 6_000.0, 20.0
_MKT, _OP, _STR, _ADD = 700.0, 1_000.0, 4_100.0, 180.0
_TOTAL = _SA + _IRB + _CCR + _MKT + _OP + _STR + _ADD


def _synthetic(**override) -> _Shim:
    rwa = {
        "sa": _SA, "irb": _IRB, "ccr": _CCR, "market": _MKT, "op": _OP,
        "structured_total": _STR, "output_floor": _Floor(_ADD),
        "final_total": _TOTAL,
    }
    rwa.update(override)
    return _Shim(rwa=rwa)


def _synthetic_tables() -> dict[str, pd.DataFrame]:
    """2단 원장의 최소 형태. 각 원장 합은 1단 값과 정확히 같다."""
    return {
        "rwa_sa_bucket": pd.DataFrame({
            "asset_class": ["corporate", "corporate", "retail_other"],
            "rating_bucket": ["A", "BBB", "UNRATED"],
            "rwa": [400.0, 350.0, 250.0]}),
        "rwa_irb_pool": pd.DataFrame({
            "asset_class": ["corporate", "residential_mortgage"],
            "pd_band": ["0.15~0.25", "0.00~0.15"],
            "rwa": [4_000.0, 2_000.0]}),
        "rwa_market_component": pd.DataFrame({
            "risk_class": ["interest_rate", "equity", "fx"],
            "rwa": [400.0, 200.0, 100.0]}),
        "rwa_operational_bi": pd.DataFrame({
            "component": ["ILDC", "SC", "FC"],
            # BI는 사업지표 원화다. RWA와 자릿수가 다르다.
            "amount": [6_000.0, 3_000.0, 1_000.0],
            "share": [0.6, 0.3, 0.1]}),
    }


def _row(df: pd.DataFrame, component: str) -> float:
    hit = df[df["component"] == component]
    assert len(hit) == 1, f"{component} 행이 {len(hit)}개다"
    return float(hit["rwa"].iloc[0])


# ---------------------------------------------------------------- 1단

def test_l1_reads_every_identity_term_directly():
    """7개 구성요소를 각각 직접 읽는다. 잔차로 만든 항이 없다."""
    df = decompose_rwa(_synthetic())
    assert list(df["component"]) == [
        "신용 SA", "신용 IRB", "거래상대방신용", "시장리스크", "운영리스크",
        "구조화", "Output floor 가산"]
    assert _row(df, "거래상대방신용") == pytest.approx(_CCR)
    assert _row(df, "구조화") == pytest.approx(_STR)
    assert _row(df, "Output floor 가산") == pytest.approx(_ADD)
    assert float(df["rwa"].sum()) == pytest.approx(_TOTAL, rel=1e-12)
    assert float(df["share"].sum()) == pytest.approx(1.0, abs=1e-12)


def test_l1_floor_row_no_longer_absorbs_ccr_and_structured():
    """예전 버그의 재발 방지. 잔차식이면 이 행이 CCR·구조화를 삼킨다."""
    df = decompose_rwa(_synthetic())
    old_residual = _TOTAL - (_SA + _IRB + _MKT + _OP)
    assert _row(df, "Output floor 가산") == pytest.approx(_ADD)
    assert _row(df, "Output floor 가산") != pytest.approx(old_residual)


def test_l1_surfaces_unallocated_row_when_identity_breaks():
    """위반 주입: 항등식보다 작은 final_total. 차이가 미배분으로 드러난다."""
    broken = _synthetic(final_total=_TOTAL + 555.0)
    with pytest.warns(AttributionWarning, match="미배분"):
        df = decompose_rwa(broken)
    assert _row(df, "미배분") == pytest.approx(555.0)
    assert float(df["rwa"].sum()) == pytest.approx(_TOTAL + 555.0, rel=1e-12)


def test_l1_warns_when_a_component_key_is_missing():
    """위반 주입: ccr 키 삭제. 조용히 0으로 두지 않고 경고를 남긴다."""
    rwa = _synthetic().rwa
    del rwa["ccr"]
    with pytest.warns(AttributionWarning) as rec:
        df = decompose_rwa(_Shim(rwa=rwa))
    msgs = " ".join(str(w.message) for w in rec)
    assert "ccr" in msgs
    assert _row(df, "거래상대방신용") == 0.0
    assert _row(df, "미배분") == pytest.approx(_CCR)


def test_l1_frame_keeps_the_columns_existing_consumers_read():
    """html_exec·ops_pages/performance·forms_fss_compliance 가 읽는 프레임."""
    df = decompose_rwa(_synthetic())
    assert list(df.columns) == ["component", "rwa", "share"]


# ---------------------------------------------------------------- 2단

def test_l2_total_equals_final_total():
    d = decompose_rwa_detail(_synthetic(), _synthetic_tables())
    assert float(d["value"].sum()) == pytest.approx(_TOTAL, rel=1e-12)


def test_each_l2_group_sums_to_its_l1_value():
    shim = _synthetic()
    l1 = decompose_rwa(shim).set_index("component")["rwa"]
    d = decompose_rwa_detail(shim, _synthetic_tables())
    for group, sub in d.groupby("group"):
        assert float(sub["value"].sum()) == pytest.approx(
            float(l1[group]), rel=1e-9), group
    assert set(d["group"]) == set(l1.index)


def test_credit_and_market_split_on_the_ledger_axis():
    d = decompose_rwa_detail(_synthetic(), _synthetic_tables())
    sa = d[d["group"] == "신용 SA"]
    assert set(sa["label"]) == {"corporate", "retail_other"}
    assert float(sa[sa["label"] == "corporate"]["value"].iloc[0]) == \
        pytest.approx(750.0)
    mkt = d[d["group"] == "시장리스크"]
    assert set(mkt["label"]) == {"interest_rate", "equity", "fx"}
    assert set(sa["source"]) == {"rwa_sa_bucket.asset_class"}


def test_operational_is_allocated_by_bi_share_not_by_bi_amount():
    """BI 원화를 RWA 자리에 그대로 쓰면 안 된다. 구성비로 배분한다."""
    d = decompose_rwa_detail(_synthetic(), _synthetic_tables())
    op = d[d["group"] == "운영리스크"].set_index("label")["value"]
    assert float(op.sum()) == pytest.approx(_OP, rel=1e-12)
    assert float(op["ILDC"]) == pytest.approx(_OP * 0.6)
    assert float(op["SC"]) == pytest.approx(_OP * 0.3)
    # BI 금액을 그대로 쓰면 합이 운영 RWA의 몇 배가 된다.
    bi = _synthetic_tables()["rwa_operational_bi"].set_index("component")
    assert float(op["ILDC"]) != pytest.approx(float(bi.loc["ILDC", "amount"]))


def test_operational_note_records_that_the_allocation_is_a_choice():
    d = decompose_rwa_detail(_synthetic(), _synthetic_tables())
    note = d[d["group"] == "운영리스크"]["note"].iloc[0]
    assert "배분" in note and "OPE25.5" in note


def test_floor_ccr_and_structured_stay_leaves():
    """산출하한 가산은 집계 수준 max()라 자산분류별 정체성이 없다."""
    d = decompose_rwa_detail(_synthetic(), _synthetic_tables())
    for leaf in ("거래상대방신용", "구조화", "Output floor 가산"):
        sub = d[d["group"] == leaf]
        assert len(sub) == 1, leaf
        assert sub["label"].iloc[0] == leaf


def test_l2_falls_back_to_a_leaf_when_the_ledger_disagrees():
    """위반 주입: SA 원장 합을 흔든다. 가르지 않고 경고를 남긴다."""
    tabs = _synthetic_tables()
    tabs["rwa_sa_bucket"].loc[0, "rwa"] = 401.0
    with pytest.warns(AttributionWarning, match="신용 SA"):
        d = decompose_rwa_detail(_synthetic(), tabs)
    sa = d[d["group"] == "신용 SA"]
    assert len(sa) == 1 and sa["label"].iloc[0] == "신용 SA"
    assert float(sa["value"].iloc[0]) == pytest.approx(_SA)
    assert float(d["value"].sum()) == pytest.approx(_TOTAL, rel=1e-12)


def test_l2_falls_back_when_bi_shares_do_not_close():
    """위반 주입: BI 구성비 합을 1에서 떼어놓는다."""
    tabs = _synthetic_tables()
    tabs["rwa_operational_bi"].loc[0, "share"] = 0.5
    with pytest.warns(AttributionWarning, match="구성비"):
        d = decompose_rwa_detail(_synthetic(), tabs)
    op = d[d["group"] == "운영리스크"]
    assert len(op) == 1 and float(op["value"].iloc[0]) == pytest.approx(_OP)


def test_l2_without_ledgers_degenerates_to_l1():
    d = decompose_rwa_detail(_synthetic(), None)
    assert len(d) == 7
    assert (d["group"] == d["label"]).all()
    assert float(d["value"].sum()) == pytest.approx(_TOTAL, rel=1e-12)
    assert d[d["group"] == "신용 SA"]["note"].iloc[0]


# ---------------------------------------------------------------- 실제 산출

@pytest.fixture(scope="module")
def rwa_ledgers(result, portfolio):
    """실체화 엔진이 만든 RWA 세분화 원장. 화면이 읽는 바로 그 프레임이다."""
    from risk_lib.datamodel.materialize import materialize_all
    from risk_lib.datamodel.materialize_detail import materialize_rwa_detail
    return materialize_rwa_detail(result, portfolio,
                                  materialize_all(result, portfolio))


def test_pipeline_l1_matches_the_cross_domain_identity(result):
    """`validation.cross_domain` 이 쓰는 항등식과 같은 값이어야 한다."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", AttributionWarning)
        df = decompose_rwa(result)
    assert float(df["rwa"].sum()) == pytest.approx(
        result.rwa["final_total"], rel=1e-12)
    assert _row(df, "거래상대방신용") == pytest.approx(result.rwa["ccr"])
    assert _row(df, "구조화") == pytest.approx(result.rwa["structured_total"])
    assert _row(df, "Output floor 가산") == pytest.approx(
        result.rwa["output_floor"].add_on)


def test_pipeline_stored_attribution_is_the_seven_way_split(result):
    """파이프라인이 저장한 프레임도 같아야 한다 (리포트 ops/23 의 원천)."""
    stored = result.attribution["rwa_components"]
    assert len(stored) == 7
    assert float(stored["rwa"].sum()) == pytest.approx(
        result.rwa["final_total"], rel=1e-12)
    assert "미배분" not in set(stored["component"])
    assert float(stored[stored["component"] == "구조화"]["rwa"].iloc[0]) == \
        pytest.approx(result.rwa["structured_total"])


def test_pipeline_l2_reconciles_to_l1_on_real_ledgers(result, rwa_ledgers):
    with warnings.catch_warnings():
        warnings.simplefilter("error", AttributionWarning)
        l1 = decompose_rwa(result).set_index("component")["rwa"]
        d = decompose_rwa_detail(result, rwa_ledgers)
    assert float(d["value"].sum()) == pytest.approx(
        result.rwa["final_total"], rel=1e-12)
    for group, sub in d.groupby("group"):
        assert float(sub["value"].sum()) == pytest.approx(
            float(l1[group]), rel=1e-9), group
    # SA·IRB·시장·운영은 실제로 갈렸다 (잎으로 주저앉지 않았다).
    for group in ("신용 SA", "신용 IRB", "시장리스크", "운영리스크"):
        assert len(d[d["group"] == group]) > 1, group


def test_pipeline_operational_split_sums_to_the_op_rwa(result, rwa_ledgers):
    d = decompose_rwa_detail(result, rwa_ledgers)
    op = d[d["group"] == "운영리스크"]
    assert set(op["label"]) == set(rwa_ledgers["rwa_operational_bi"]["component"])
    assert float(op["value"].sum()) == pytest.approx(result.rwa["op"], rel=1e-12)
    # 운영 RWA는 BI 총액과 다르다. 원장 금액을 그대로 쓰면 여기서 걸린다.
    assert float(rwa_ledgers["rwa_operational_bi"]["amount"].sum()) != \
        pytest.approx(result.rwa["op"], rel=1e-6)
