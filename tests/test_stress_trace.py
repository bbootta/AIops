"""위기상황분석 산출과정 추적 — 결과와의 동치성이 전부다.

추적표가 스트레스 경로 결과와 조금이라도 다르면 그것은 설명이 아니라 두 번째
모형이다. 화면은 추적표를 그리고 보고서는 경로 결과를 쓰므로, 둘이 갈라지면
같은 은행에 대해 서로 다른 CET1 저점이 두 개 존재하게 된다.
"""

from __future__ import annotations

import numpy as np
import pytest

from risk_lib.datamodel import catalog as cat
from risk_lib.stress.trace import BLOCKS, build_stress_trace, trace_from_result


@pytest.fixture(scope="module")
def trace(result, portfolio):
    return trace_from_result(result, portfolio)


# ----- 구조 -------------------------------------------------------------------

def test_every_scenario_and_quarter_is_traced(trace, result):
    sp = result.stress_path
    assert set(trace["scenario"]) == set(sp["scenario"])
    assert set(trace["quarter"]) == set(sp["quarter"])
    per_cell = trace.groupby(["scenario", "quarter"]).size()
    assert per_cell.nunique() == 1, "셀마다 단계 수가 다르면 비교가 불가능하다"


def test_blocks_appear_in_order_within_each_cell(trace):
    order = {b: i for i, b in enumerate(BLOCKS)}
    for (_, _), sub in trace.groupby(["scenario", "quarter"]):
        idx = [order[b] for b in sub.sort_values("seq")["block"]]
        assert idx == sorted(idx), "블록 순서가 뒤섞이면 전이 경로가 읽히지 않는다"


def test_every_step_carries_formula_inputs_and_citation(trace):
    for col in ("formula", "inputs", "citation", "step"):
        assert trace[col].str.len().min() > 0, col


def test_units_are_declared_and_ratios_are_fractions(trace):
    assert set(trace["unit"]) <= {"KRW", "ratio", "count", "years"}
    ratios = trace[trace["unit"] == "ratio"]["value"]
    assert ratios.between(-5, 5).all(), "비율을 %로 담으면 화면이 100배로 표시된다"


def test_trace_satisfies_the_catalog_spec(trace):
    from risk_lib.datamodel.spec import validate
    spec = next(s for s in cat.ALL_TABLES if s.name == "st_calc_trace")
    bad = [v for v in validate(trace, spec) if v.severity == "FAIL"]
    assert bad == [], bad


# ----- 결과와의 동치성 (핵심) --------------------------------------------------

_STEP_TO_COL = {
    "보통주자본비율": "cet1_ratio",
    "기본자본비율": "tier1_ratio",
    "총자본비율": "total_ratio",
    "위험가중자산 합계": "rwa_total",
    "기대신용손실 (충격 후)": "ecl",
    "충격 심도 (severity)": "severity",
    "GDP 성장률 충격": "gdp_shock",
    "LGD 가산": "lgd_addon",
}


def test_trace_reconciles_with_the_stress_path(trace, result):
    sp = result.stress_path
    for _, row in sp.iterrows():
        cell = trace[(trace["scenario"] == row["scenario"])
                     & (trace["quarter"] == row["quarter"])]
        for step, col in _STEP_TO_COL.items():
            got = float(cell[cell["step"] == step]["value"].iloc[0])
            assert got == pytest.approx(float(row[col]), rel=1e-12), (
                row["scenario"], row["quarter"], step)


def test_trough_in_the_trace_matches_the_published_trough(trace, result):
    cet1 = trace[trace["step"] == "보통주자본비율"]
    for _, row in result.stress_path_trough.iterrows():
        sub = cet1[cet1["scenario"] == row["scenario"]]
        assert float(sub["value"].min()) == pytest.approx(
            float(row["trough_cet1"]), rel=1e-12)
        worst = sub.loc[sub["value"].idxmin()]
        assert str(worst["quarter"]) == str(row["trough_quarter"])


def test_pass_flag_matches_the_path(trace, result):
    sp = result.stress_path.set_index(["scenario", "quarter"])
    ok = trace[trace["step"] == "요구치 충족"]
    for _, r in ok.iterrows():
        assert bool(r["value"]) == bool(sp.loc[(r["scenario"], r["quarter"]),
                                               "passes"])


# ----- 내부 정합 --------------------------------------------------------------

def test_rwa_total_is_the_sum_of_its_components(trace):
    for (_, _), sub in trace.groupby(["scenario", "quarter"]):
        v = sub.set_index("step")["value"]
        parts = (v["신용 IRB (충격 후)"] + v["신용 표준방법 (불변)"]
                 + v["시장리스크 (불변)"] + v["운영리스크 (불변)"])
        assert v["위험가중자산 합계"] == pytest.approx(parts, rel=1e-12)


def test_stressed_cet1_is_base_less_incremental_ecl(trace):
    for (_, _), sub in trace.groupby(["scenario", "quarter"]):
        v = sub.set_index("step")["value"]
        assert v["보통주자본 (충격 후)"] == pytest.approx(
            v["보통주자본 (기준)"] - v["증분 ECL"], rel=1e-12)


def test_capital_total_is_the_sum_of_tiers(trace):
    for (_, _), sub in trace.groupby(["scenario", "quarter"]):
        v = sub.set_index("step")["value"]
        assert v["자기자본 합계"] == pytest.approx(
            v["보통주자본 (충격 후)"] + v["기타기본자본 (불변)"]
            + v["보완자본 (불변)"], rel=1e-12)


def test_ratio_is_capital_over_rwa(trace):
    for (_, _), sub in trace.groupby(["scenario", "quarter"]):
        v = sub.set_index("step")["value"]
        assert v["보통주자본비율"] == pytest.approx(
            v["보통주자본 (충격 후)"] / v["위험가중자산 합계"], rel=1e-12)
        assert v["총자본비율"] == pytest.approx(
            v["자기자본 합계"] / v["위험가중자산 합계"], rel=1e-12)


def test_surplus_is_actual_minus_required(trace):
    for (_, _), sub in trace.groupby(["scenario", "quarter"]):
        v = sub.set_index("step")["value"]
        for label, ratio in (("보통주자본", "보통주자본비율"),
                             ("기본자본", "기본자본비율"),
                             ("총자본", "총자본비율")):
            assert v[f"{label} 잉여(+)·부족(−)"] == pytest.approx(
                v[ratio] - v[f"{label} 요구비율"], rel=1e-9)


def test_incremental_ecl_is_never_negative(trace):
    assert (trace[trace["step"] == "증분 ECL"]["value"] >= 0).all()


def test_severity_increases_the_stressed_parameters(trace):
    """심도가 커지면 PD·LGD·ECL이 커지고 CET1이 낮아져야 한다."""
    q = trace["quarter"].iloc[0]
    cell = trace[trace["quarter"] == q]
    by = {sc: sub.set_index("step")["value"]
          for sc, sub in cell.groupby("scenario")}
    order = ["baseline", "adverse", "severely_adverse"]
    for a, b in zip(order, order[1:]):
        assert by[a]["충격 심도 (severity)"] <= by[b]["충격 심도 (severity)"]
        assert by[a]["PD (충격 후)"] <= by[b]["PD (충격 후)"]
        assert by[a]["LGD (충격 후)"] <= by[b]["LGD (충격 후)"]
        assert by[a]["기대신용손실 (충격 후)"] <= by[b]["기대신용손실 (충격 후)"]
        assert by[a]["보통주자본비율"] >= by[b]["보통주자본비율"]


def test_unchanged_blocks_are_labelled_as_such(trace):
    """시장·운영이 불변인 이유가 화면에 남아야 '왜 안 움직이나'에 답할 수 있다."""
    steps = set(trace["step"])
    assert "시장리스크 (불변)" in steps
    assert "운영리스크 (불변)" in steps
    assert "EAD (불변)" in steps
    row = trace[trace["step"] == "시장·운영 손익 (본 축 불변)"].iloc[0]
    assert "별도 축" in str(row["inputs"])


# ----- 방어 -------------------------------------------------------------------

def test_mismatched_rwa_components_raise(result, portfolio):
    """구성요소 합이 총계와 다르면 조용히 다른 총계를 그리지 않고 실패한다."""
    from risk_lib.datamodel.materialize import fitted_portfolio
    from risk_lib.pipeline import _stage_split_books
    _, irb = _stage_split_books(fitted_portfolio(portfolio))
    rwa = result.rwa
    with pytest.raises(ValueError, match="갈라진다"):
        build_stress_trace(
            irb, result.meta["capital"],
            float(rwa["sa"]) + float(rwa["market"]) + float(rwa["op"]),
            quarters=["2026Q3"], rwa_sa=float(rwa["sa"]),
            rwa_market=float(rwa["market"]), rwa_op=0.0)
