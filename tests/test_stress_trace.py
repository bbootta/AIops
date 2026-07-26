"""전 축 위기상황분석 추적 — 결과와의 동치성이 전부다.

추적표가 경로 결과와 조금이라도 다르면 그것은 설명이 아니라 두 번째 모형이다.
화면은 추적표를 그리고 보고서는 경로 결과를 쓰므로, 둘이 갈라지면 같은 은행에
대해 서로 다른 CET1 저점이 두 개 존재하게 된다.
"""

from __future__ import annotations

import pytest

from risk_lib.datamodel import catalog as cat
from risk_lib.stress.axes import AXES, RISK_TYPES, shocks_at
from risk_lib.stress.trace import BLOCKS, trace_from_result


@pytest.fixture(scope="module")
def trace(result, portfolio):
    return trace_from_result(result, portfolio)


# ----- 충격 축 ----------------------------------------------------------------

def test_every_risk_type_has_a_shock_axis():
    """신용만 충격하면 통합위기상황분석이 아니다."""
    covered = {a.risk_type for a in AXES}
    assert covered == set(RISK_TYPES)
    assert len(AXES) >= 12


def test_axis_keys_are_unique_and_documented():
    keys = [a.key for a in AXES]
    assert len(keys) == len(set(keys))
    for a in AXES:
        assert a.citation and a.korean and a.unit


def test_shocks_scale_linearly_with_severity():
    a, b = shocks_at(1.0), shocks_at(2.0)
    for k in a:
        assert b[k] == pytest.approx(2 * a[k], rel=1e-12)
    assert all(v == 0.0 for v in shocks_at(0.0).values())


def test_axis_table_matches_the_catalog_domain(result, portfolio):
    from risk_lib.ui_studio.studio import build_studio
    t = build_studio(result, portfolio).tables["st_shock_axis"]
    assert len(t) == len(AXES)
    assert set(t["risk_type"]) <= set(cat.SHOCK_RISK_TYPES)


# ----- 구조 -------------------------------------------------------------------

def test_every_scenario_and_quarter_is_traced(trace, result):
    sp = result.stress_path
    assert set(trace["scenario"]) == set(sp["scenario"])
    assert set(trace["quarter"]) == set(sp["quarter"])
    per_cell = trace.groupby(["scenario", "quarter"]).size()
    assert per_cell.nunique() == 1, "셀마다 단계 수가 다르면 비교가 불가능하다"


def test_all_thirteen_blocks_appear_in_order(trace):
    order = {b: i for i, b in enumerate(BLOCKS)}
    for (_, _), sub in trace.groupby(["scenario", "quarter"]):
        blocks = list(sub.sort_values("seq")["block"])
        assert set(blocks) == set(BLOCKS), set(BLOCKS) - set(blocks)
        idx = [order[b] for b in blocks]
        assert idx == sorted(idx), "블록 순서가 뒤섞이면 전이 경로가 읽히지 않는다"


def test_every_step_carries_formula_inputs_and_citation(trace):
    for col in ("formula", "inputs", "citation", "step"):
        assert trace[col].str.len().min() > 0, col


def test_units_are_declared_and_ratios_are_fractions(trace):
    assert set(trace["unit"]) <= set(cat.TRACE_UNITS)
    ratios = trace[(trace["unit"] == "ratio")]["value"]
    assert ratios.between(-5, 5).all(), "비율을 %로 담으면 화면이 100배로 표시된다"


def test_trace_satisfies_the_catalog_spec(trace):
    from risk_lib.datamodel.spec import validate
    spec = next(s for s in cat.ALL_TABLES if s.name == "st_calc_trace")
    bad = [v for v in validate(trace, spec) if v.severity == "FAIL"]
    assert bad == [], bad


def test_shock_axis_block_lists_every_axis(trace):
    for (_, _), sub in trace.groupby(["scenario", "quarter"]):
        axis_rows = sub[sub["block"] == "충격축"]
        assert len(axis_rows) == len(AXES)


# ----- 결과와의 동치성 (핵심) --------------------------------------------------

_STEP_TO_COL = {
    "보통주자본비율": "cet1_ratio",
    "기본자본비율": "tier1_ratio",
    "총자본비율": "total_ratio",
    "위험가중자산 합계": "rwa_total",
    "내부등급법 RWA": "rwa_irb",
    "표준방법 RWA": "rwa_sa",
    "시장리스크 RWA": "rwa_market",
    "운영리스크 RWA": "rwa_op",
    "충당금 전입": None,           # 부호 반전 — 아래에서 따로
    "트레이딩 손익 합계": "trading_pnl",
    "운영손실 (연간)": "op_loss",
    "당기순이익": "net_income",
    "유동성커버리지비율": "lcr",
    "ΔEVE": "delta_eve",
    "ΔNII (1년)": "delta_nii",
    "충격 심도 (severity)": "severity",
}


def test_trace_reconciles_with_the_path(trace, result):
    sp = result.stress_path
    for _, row in sp.iterrows():
        cell = trace[(trace["scenario"] == row["scenario"])
                     & (trace["quarter"] == row["quarter"])]
        for step, col in _STEP_TO_COL.items():
            if col is None:
                continue
            got = float(cell[cell["step"] == step]["value"].iloc[0])
            assert got == pytest.approx(float(row[col]), rel=1e-12,
                                        abs=1e-9), (row["scenario"],
                                                    row["quarter"], step)


def test_provision_sign_is_a_deduction_in_the_income_block(trace, result):
    sp = result.stress_path.set_index(["scenario", "quarter"])
    prov = trace[(trace["block"] == "손익") & (trace["step"] == "충당금 전입")]
    for _, r in prov.iterrows():
        expected = -float(sp.loc[(r["scenario"], r["quarter"]), "provision"])
        assert float(r["value"]) == pytest.approx(expected, rel=1e-12,
                                                  abs=1e-9)


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

def _cells(trace):
    for key, sub in trace.groupby(["scenario", "quarter"]):
        yield key, sub.set_index("step")["value"]


def test_internal_rwa_is_the_sum_of_its_components(trace):
    for _, v in _cells(trace):
        parts = (v["내부등급법 RWA"] + v["표준방법 RWA"] + v["시장리스크 RWA"]
                 + v["운영리스크 RWA"])
        assert v["내부모형 RWA"] == pytest.approx(parts, rel=1e-12)


def test_total_rwa_applies_the_output_floor(trace):
    for _, v in _cells(trace):
        assert v["위험가중자산 합계"] >= v["내부모형 RWA"] - 1e-6
        assert v["산출하한 증가분"] == pytest.approx(
            v["위험가중자산 합계"] - v["내부모형 RWA"], rel=1e-9, abs=1e-6)


def test_trading_pnl_is_the_sum_of_market_legs(trace):
    for _, v in _cells(trace):
        assert v["트레이딩 손익 합계"] == pytest.approx(
            v["금리 포지션 손익"] + v["신용스프레드 손익"]
            + v["주식 손익"] + v["외환 손익"], rel=1e-12, abs=1e-6)


def test_pre_tax_income_is_the_sum_of_its_legs(trace):
    for _, v in _cells(trace):
        parts = (v["이자수익"] + v["수수료수익"] + v["영업비용"]
                 + v["충당금 전입"] + v["운영손실"] + v["트레이딩 손익"])
        assert v["법인세차감전순이익"] == pytest.approx(parts, rel=1e-9,
                                                       abs=1e-3)


def test_capital_rolls_forward_on_earnings_not_on_ecl(trace):
    """충당금이 이익에 이미 있으므로 ECL을 따로 빼면 이중계상이다."""
    for _, v in _cells(trace):
        assert v["보통주자본 (충격 후)"] == pytest.approx(
            v["보통주자본 (기준)"] + v["이익 변화 (기준 대비)"], rel=1e-12)


def test_capital_total_is_the_sum_of_tiers(trace):
    for _, v in _cells(trace):
        assert v["자기자본 합계"] == pytest.approx(
            v["보통주자본 (충격 후)"] + v["기타기본자본"] + v["보완자본"],
            rel=1e-12)


def test_ratio_is_capital_over_rwa(trace):
    for _, v in _cells(trace):
        assert v["보통주자본비율"] == pytest.approx(
            v["보통주자본 (충격 후)"] / v["위험가중자산 합계"], rel=1e-12)
        assert v["총자본비율"] == pytest.approx(
            v["자기자본 합계"] / v["위험가중자산 합계"], rel=1e-12)


def test_surplus_is_actual_minus_required(trace):
    for _, v in _cells(trace):
        for label, ratio in (("보통주자본", "보통주자본비율"),
                             ("기본자본", "기본자본비율"),
                             ("총자본", "총자본비율")):
            assert v[f"{label} 잉여(+)·부족(−)"] == pytest.approx(
                v[ratio] - v[f"{label} 요구비율"], rel=1e-9)


def test_lcr_is_hqla_over_net_outflow(trace):
    for _, v in _cells(trace):
        assert v["유동성커버리지비율"] == pytest.approx(
            v["고유동성자산 (haircut 후)"] / v["순현금유출"], rel=1e-12)


# ----- 심도 단조성 ------------------------------------------------------------

def test_severity_moves_every_risk_type_the_right_way(trace):
    q = trace["quarter"].iloc[0]
    cell = trace[trace["quarter"] == q]
    by = {sc: sub.set_index("step")["value"]
          for sc, sub in cell.groupby("scenario")}
    order = ["baseline", "adverse", "severely_adverse"]
    for a, b in zip(order, order[1:]):
        x, y = by[a], by[b]
        assert x["충격 심도 (severity)"] <= y["충격 심도 (severity)"]
        # 신용
        assert x["PD (충격 후)"] <= y["PD (충격 후)"]
        assert x["LGD (충격 후)"] <= y["LGD (충격 후)"]
        assert x["EAD (충격 후)"] <= y["EAD (충격 후)"]
        assert x["내부등급법 RWA"] <= y["내부등급법 RWA"]
        assert x["표준방법 RWA"] <= y["표준방법 RWA"]
        # 시장 — 손익은 더 나빠진다
        assert x["트레이딩 손익 합계"] >= y["트레이딩 손익 합계"]
        assert x["시장리스크 RWA"] <= y["시장리스크 RWA"]
        # 운영
        assert x["운영손실 (연간)"] <= y["운영손실 (연간)"]
        assert x["운영리스크 RWA"] <= y["운영리스크 RWA"]
        # 유동성
        assert x["유동성커버리지비율"] >= y["유동성커버리지비율"]
        # 수익·자본
        assert x["이자수익"] >= y["이자수익"]
        assert x["당기순이익"] >= y["당기순이익"]
        assert x["보통주자본비율"] >= y["보통주자본비율"]


def test_baseline_reproduces_the_unstressed_state(trace, result):
    """심도 0에서 기준 상태가 정확히 재현되지 않으면 충격 크기를 믿을 수 없다."""
    base = trace[(trace["scenario"] == "baseline")].set_index("step")["value"]
    assert float(base["보통주자본비율"].iloc[0]) == pytest.approx(
        result.bis.cet1_ratio, rel=1e-12)
    assert float(base["위험가중자산 합계"].iloc[0]) == pytest.approx(
        result.rwa["final_total"], rel=1e-12)
    assert float(base["유동성커버리지비율"].iloc[0]) == pytest.approx(
        result.alm["lcr"].lcr, rel=1e-9)
    assert float(base["이익 변화 (기준 대비)"].iloc[0]) == pytest.approx(0.0,
                                                                        abs=1e-6)


def test_multi_axis_is_harsher_than_credit_only(result, portfolio):
    """전 축이 신용 단독보다 관대하면 축을 추가한 의미가 없다."""
    from risk_lib.datamodel.materialize import fitted_portfolio
    from risk_lib.pipeline import _stage_split_books
    from risk_lib.stress.path import run_stress_path
    from risk_lib.stress.scenario import StressAxis

    _, irb = _stage_split_books(fitted_portfolio(portfolio))
    rwa_other = float(result.rwa["final_total"]) - float(result.rwa["irb"])
    credit_only = run_stress_path(
        irb, result.meta["capital"], rwa_other,
        quarters=list(result.meta["quarters"]), axis=StressAxis(),
        buffers={"capital_conservation": 0.025, "countercyclical": 0.0,
                 "dsib": 0.01})
    sev_credit = float(
        credit_only[credit_only["scenario"] == "severely_adverse"]
        ["cet1_ratio"].min())
    sev_multi = float(
        result.stress_path[result.stress_path["scenario"] == "severely_adverse"]
        ["cet1_ratio"].min())
    assert sev_multi < sev_credit
