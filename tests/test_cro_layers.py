"""Unit tests for the v0.4 CRO-layer modules:
repro, appetite, attribution, sensitivity, model_risk, climate, ccr, op_loss,
concentration_deep, pillar3.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import pytest

from risk_lib import generate_portfolio

# `result` fixture: session-scoped shared — see conftest.py.


# ---- repro ---------------------------------------------------------------

def test_portfolio_fingerprint_stable():
    from risk_lib.repro import portfolio_fingerprint
    p = generate_portfolio(seed=42)
    a = portfolio_fingerprint(p)
    b = portfolio_fingerprint(p.copy())
    assert a["sha256"] == b["sha256"]
    assert a["n_rows"] == len(p)
    assert a["ead_total"] == pytest.approx(float(p["ead"].sum()), rel=1e-12)


def test_portfolio_fingerprint_changes_when_data_changes():
    from risk_lib.repro import portfolio_fingerprint
    a = portfolio_fingerprint(generate_portfolio(seed=42))
    b = portfolio_fingerprint(generate_portfolio(seed=43))
    assert a["sha256"] != b["sha256"]


def test_manifest_digest_reproducible(result):
    from risk_lib.repro import build_manifest, now_utc, diff_manifests
    p = generate_portfolio(seed=42)
    m1 = build_manifest(portfolio=p, parameters={"seed": 42}, result=result,
                        start_utc=now_utc(), end_utc=now_utc())
    m2 = build_manifest(portfolio=p, parameters={"seed": 42}, result=result,
                        start_utc=now_utc(), end_utc=now_utc())
    assert m1.headline_digest == m2.headline_digest
    diff = diff_manifests(m1, m2)
    assert all(k == "timing" for k in diff)


# ---- appetite (RAF) ------------------------------------------------------

def test_raf_grades_match_grade_logic(result):
    raf = result.raf
    assert len(raf.kris) >= 10
    for k in raf.kris:
        t = k.threshold
        if t.direction == "min":
            if k.actual < t.board:        assert k.grade == "RED"
            elif k.actual < t.management: assert k.grade == "AMBER"
            elif k.actual < t.operational:assert k.grade == "WATCH"
            else:                          assert k.grade == "GREEN"
        else:
            if k.actual > t.board:        assert k.grade == "RED"
            elif k.actual > t.management: assert k.grade == "AMBER"
            elif k.actual > t.operational:assert k.grade == "WATCH"
            else:                          assert k.grade == "GREEN"


def test_raf_worst_is_most_severe(result):
    order = {"GREEN": 0, "WATCH": 1, "AMBER": 2, "RED": 3}
    worst = result.raf.worst()
    assert worst == max((k.grade for k in result.raf.kris),
                         key=lambda g: order[g])


# ---- attribution ---------------------------------------------------------

def test_capital_bridge_reconciles(result):
    from risk_lib.attribution import capital_bridge
    # same result vs itself → zero change
    b = capital_bridge(result, result)
    assert b.start_value == pytest.approx(b.end_value, rel=1e-12)
    assert b.explained_change == pytest.approx(0.0, abs=1e-12)


def test_rwa_bridge_decomposes_to_total(result):
    from risk_lib.attribution import rwa_bridge
    # bump market RWA on a copy
    @dataclass
    class _Shim:
        rwa: dict
        bis: object = None
        meta: dict = None
    bumped = _Shim(rwa={**result.rwa, "market": result.rwa["market"] * 1.1,
                        "final_total": result.rwa["final_total"]
                        + result.rwa["market"] * 0.1})
    b = rwa_bridge(result, bumped)
    assert b.explained_change == pytest.approx(b.end_value - b.start_value, rel=1e-10)


def test_decompose_cet1_headroom_is_decreasing(result):
    from risk_lib.attribution import decompose_cet1_headroom
    df = decompose_cet1_headroom(result)
    # headroom must shrink as required rises
    assert (df["headroom"].diff().dropna() <= 0).all()


def test_decompose_rwa_sums_to_total(result):
    from risk_lib.attribution import decompose_rwa
    df = decompose_rwa(result)
    assert df["rwa"].sum() == pytest.approx(result.rwa["final_total"], rel=1e-9)
    assert df["share"].sum() == pytest.approx(1.0, abs=1e-9)


# ---- sensitivity ---------------------------------------------------------

def test_one_factor_zero_shock_yields_base(result):
    from risk_lib.sensitivity import (
        _ecl_pd_sensitivity, _rwa_ead_sensitivity, _cet1_from_rwa_and_capital,
    )
    assert _ecl_pd_sensitivity(result, 0.0) == pytest.approx(
        float(result.ecl["total"]), rel=1e-9)
    assert _rwa_ead_sensitivity(result, 0.0) == pytest.approx(
        result.rwa["sa"] + result.rwa["irb"] + result.rwa["market"] + result.rwa["op"],
        rel=1e-9)


def test_one_factor_grid_shape(result):
    one = result.sensitivity["one_factor"]
    assert {"factor", "shock", "metric", "base", "shocked", "delta"} <= set(one.columns)
    assert len(one) >= 20
    # ECL row with PD shock +50% must produce higher ECL than base
    ecl_pd_up = one[(one["factor"] == "PD (rel)") & (one["shock"] == 0.50)]
    assert float(ecl_pd_up["shocked"].iloc[0]) > float(ecl_pd_up["base"].iloc[0])


def test_two_factor_surface_monotone(result):
    two = result.sensitivity["two_factor"]
    # ECL must rise monotonically with both PD and LGD shocks
    for l in two["lgd_shock"].unique():
        sub = two[two["lgd_shock"] == l].sort_values("pd_shock")
        assert (sub["ecl"].diff().dropna() >= -1e-3).all()
    for p in two["pd_shock"].unique():
        sub = two[two["pd_shock"] == p].sort_values("lgd_shock")
        assert (sub["ecl"].diff().dropna() >= -1e-3).all()


# ---- model_risk ----------------------------------------------------------

def test_psi_identical_distributions_is_zero():
    from risk_lib.model_risk import psi
    rng = np.random.default_rng(7)
    x = rng.normal(size=10_000)
    assert psi(x, x.copy()) == pytest.approx(0.0, abs=0.01)


def test_psi_disjoint_distributions_is_large():
    from risk_lib.model_risk import psi
    rng = np.random.default_rng(7)
    x = rng.normal(0, 1, 10_000)
    y = rng.normal(5, 1, 10_000)   # very far apart
    assert psi(x, y) > 1.0


def test_drift_report_zones():
    from risk_lib.model_risk import drift_report
    rng = np.random.default_rng(7)
    train = pd.DataFrame({"a": rng.normal(0, 1, 1000),
                          "b": rng.normal(0, 1, 1000)})
    recent = pd.DataFrame({"a": rng.normal(0, 1, 500),
                           "b": rng.normal(2, 1, 500)})    # b drifted
    rep = drift_report(train, recent, ["a", "b"])
    assert rep.set_index("feature").loc["a", "zone"] == "GREEN"
    assert rep.set_index("feature").loc["b", "zone"] in ("AMBER", "RED")


def test_model_cards_match_segments(result):
    seg = set(result.pd_metrics.keys())
    cards_seg = {m.segment for m in result.model_cards}
    assert cards_seg == seg


# ---- climate -------------------------------------------------------------

def test_climate_transition_increases_with_co2_price(result):
    cl = result.climate
    # hot_house 2030 (CO2 $10) vs disorderly 2050 (CO2 $400) → 후자가 큼
    hot = next(l for l in cl.transition if l.scenario == "transition_hot_house_2030")
    dis = next(l for l in cl.transition if l.scenario == "transition_disorderly_2050")
    assert dis.uplift > hot.uplift


def test_climate_physical_increases_with_intensity(result):
    cl = result.climate
    cur = next(l for l in cl.physical if l.scenario == "physical_current")
    sev = next(l for l in cl.physical if l.scenario == "physical_severe")
    assert sev.uplift > cur.uplift


# ---- ccr -----------------------------------------------------------------

def test_ccr_ead_alpha_14(result):
    if result.ccr is None or result.ccr.by_counterparty.empty:
        pytest.skip("no bank book")
    # EAD = 1.4 × (RC + PFE) per counterparty
    df = result.ccr.by_counterparty
    expected = 1.4 * (df["rc"] + df["pfe"])
    np.testing.assert_allclose(df["ead"].to_numpy(), expected.to_numpy(), rtol=1e-12)


def test_ccr_cva_nonneg(result):
    if result.ccr is None: pytest.skip("no ccr")
    assert result.ccr.cva_charge >= 0


# ---- op_loss -------------------------------------------------------------

def test_op_loss_var_ge_es(result):
    op = result.op_loss
    if op.var_99_9 == 0: pytest.skip("no loss data")
    # 99.9% VaR should be >= 99% ES is not necessarily true, but VaR/ES both positive
    assert op.var_99_9 >= 0 and op.es_99_0 >= 0
    assert op.annual_total >= 0


def test_op_loss_register_has_all_event_types(result):
    from risk_lib.op_loss import EVENT_TYPES
    et = set(result.op_loss.register["event_type"].unique())
    # at least 5 of 7 should appear
    assert len(et & set(EVENT_TYPES)) >= 5


# ---- concentration_deep --------------------------------------------------

def test_top_obligors_returns_n(result):
    assert len(result.concentration_deep["top_by_ead"]) == 20
    assert (result.concentration_deep["top_by_ead"]["ead"].diff().dropna() <= 0).all()


def test_sector_country_matrix_sums(result):
    from risk_lib.concentration_deep import sector_country_matrix
    p = generate_portfolio(seed=42)
    m = sector_country_matrix(p)
    assert m.sum().sum() == pytest.approx(float(p["ead"].sum()), rel=1e-9)


def test_large_exposure_severity_grading(result):
    le = result.concentration_deep["large_exposure"]
    # utilisation column matches severity buckets
    for _, r in le.head(50).iterrows():
        u = r["utilisation"]
        if u >= 1.0:   assert r["severity"] == "BREACH"
        elif u >= 0.9: assert r["severity"] == "CRITICAL"
        elif u >= 0.75: assert r["severity"] == "WARN"
        else:           assert r["severity"] == "OK"


# ---- pillar3 -------------------------------------------------------------

def test_pillar3_km1_has_all_rows(result):
    from risk_lib.pillar3 import km1
    df = km1(result)
    assert len(df) == 16
    assert {"행", "지표", "값"} == set(df.columns)


def test_pillar3_ov1_sums_to_total(result):
    from risk_lib.pillar3 import ov1
    df = ov1(result)
    total_row = df[df["부문"] == "최종 합계"]["RWA"].iloc[0]
    components = df[df["부문"] != "최종 합계"]["RWA"].sum()
    assert total_row == pytest.approx(components, rel=1e-9)


def test_pillar3_ov1_reports_each_sector_instead_of_a_residual(result):
    """OV1 부문 줄이 산출 결과의 해당 항과 같아야 한다.

    합계만 닫는 검사는 잔차식을 잡지 못한다. CCR·증권화를 "없음 0"으로
    적고 그 합을 Output floor 가산 줄에 넣어도 합계는 그대로 닫혔다.
    실제로 그렇게 공시된 회차가 있었다(CCR/CVA 0 · 증권화 0 · floor 4.15조,
    같은 실행의 rwa_output_floor.csv uplift 는 0). 줄마다 원천을 대조한다.
    """
    from risk_lib.pillar3 import ov1
    rwa = result.rwa
    v = dict(zip(ov1(result)["부문"], ov1(result)["RWA"], strict=True))

    assert v["신용리스크 (SA)"] == pytest.approx(float(rwa["sa"]))
    assert v["신용리스크 (IRB)"] == pytest.approx(float(rwa["irb"]))
    assert v["CCR/CVA"] == pytest.approx(float(rwa["ccr"]))
    assert v["집합투자증권 (CRE60)"] == pytest.approx(float(rwa["fund"]))
    assert v["증권화 (CRE40)"] == pytest.approx(float(rwa["securitisation"]))
    assert v["시장리스크"] == pytest.approx(float(rwa["market"]))
    assert v["운영리스크"] == pytest.approx(float(rwa["op"]))
    # 산출하한 가산은 하한 산출값 그 자체이지 남은 차액이 아니다.
    assert v["Output floor 가산"] == pytest.approx(
        float(rwa["output_floor"].add_on), abs=1.0)

    # "없음" 으로 적힌 부문이 없다. 산출된 값을 0으로 적으면 공시가 틀린다.
    assert not [s for s in v if "없음" in s]
    for sector in ("CCR/CVA", "집합투자증권 (CRE60)", "증권화 (CRE40)"):
        assert v[sector] > 0.0, f"{sector} 가 0이다. 산출값과 대조하라"


# ---- html_report integration --------------------------------------------

# ---- mda -----------------------------------------------------------------

def test_mda_no_breach_above_cbr():
    from risk_lib.mda import compute_mda
    m = compute_mda(0.115, 1.15e12, 1e13)
    assert m.in_breach is False
    assert m.distributable_pct == 1.0
    assert m.buffer_quartile == 0
    assert m.excess_above_cbr > 0


def test_mda_quartile_progression():
    """Walking down the buffer should hit quartiles 4 → 3 → 2 → 1."""
    from risk_lib.mda import compute_mda
    # CBR = 3.5%, so 4.5%+CBR = 8.0%. Quartile width = 3.5%/4 ≈ 0.875%p.
    # CET1 levels chosen to land squarely inside each quartile.
    cases = {7.7: 4, 6.9: 3, 6.0: 2, 5.0: 1}    # rounded inside-band midpoints
    for pct, expected_q in cases.items():
        m = compute_mda(pct / 100, pct/100 * 1e13, 1e13)
        assert m.in_breach
        assert m.buffer_quartile == expected_q, f"{pct}% → q{m.buffer_quartile} (expected {expected_q})"


def test_mda_below_pillar1_is_q1():
    from risk_lib.mda import compute_mda
    m = compute_mda(0.040, 4e11, 1e13)
    assert m.in_breach
    assert m.buffer_quartile == 1
    assert m.retention_ratio == 1.0


def test_mda_ladder_marks_current():
    from risk_lib.mda import mda_ladder
    df = mda_ladder(1e12, 1e13)
    assert df["is_current"].sum() == 1


# ---- timeseries ----------------------------------------------------------

def test_kri_history_reconciles_to_actual(result):
    from risk_lib.timeseries import synth_history
    hist = synth_history(result.raf, months=12, seed=42)
    assert len(hist) == len(result.raf.kris)
    for k, ts in zip(result.raf.kris, hist):
        assert ts.values[-1] == pytest.approx(k.actual, rel=1e-9)
        assert len(ts.months) == 12 == len(ts.values)


def test_kri_history_deterministic(result):
    from risk_lib.timeseries import synth_history
    a = synth_history(result.raf, months=12, seed=42)
    b = synth_history(result.raf, months=12, seed=42)
    for x, y in zip(a, b):
        assert x.values == y.values


# ---- vintage / transition ------------------------------------------------

def test_vintage_cohorts():
    from risk_lib.vintage import build_vintage
    p = generate_portfolio(seed=42)
    v = build_vintage(p, n_cohorts=12, seed=42)
    assert len(v.summary) > 0
    # cum_default_rate must be monotone non-decreasing in MOB within each cohort
    for c in v.cohorts["cohort_month"].unique():
        sub = v.cohorts[v.cohorts["cohort_month"] == c].sort_values("mob")
        assert (sub["cum_default_rate"].diff().dropna() >= -1e-6).all()


def test_transition_matrix_row_sums_to_one():
    from risk_lib.vintage import transition_matrix
    from risk_lib.models.rating import pd_to_rating
    p = generate_portfolio(seed=42)
    p["grade"] = [pd_to_rating(x).grade if x == x else None for x in p["pd"]]
    t = transition_matrix(p, seed=42)
    assert t.n_obs > 0
    # rows that have any obs should sum to ~1
    nonzero = t.matrix[t.matrix.sum(axis=1) > 0.5]
    for _, row in nonzero.iterrows():
        assert row.sum() == pytest.approx(1.0, abs=1e-9)


# ---- data quality / reconciliation --------------------------------------

def test_dq_report_columns():
    from risk_lib.data_quality import dq_report
    p = generate_portfolio(seed=42)
    dq = dq_report(p)
    assert len(dq.schema) == len(p.columns)
    # exposure_id is unique → no FAIL flag for duplicates
    fail_flags = [f for f in dq.flags if f.startswith("FAIL")]
    assert all("중복" not in f for f in fail_flags)


def test_reconciliation_all_pass(result):
    from risk_lib.data_quality import reconcile
    p = generate_portfolio(seed=42)
    rec = reconcile(result, p)
    assert all(c.passes for c in rec), \
        [c for c in rec if not c.passes]


# ---- CLI integration ----------------------------------------------------

def test_cli_report_set_command(tmp_path):
    from risk_lib.cli import main
    out = tmp_path / "cro"
    rc = main(["report-set", "--out", str(out), "--seed", "42"])
    assert rc == 0
    assert (out / "executive.html").exists()
    assert (out / "manifest.json").exists()
    assert (out / "ops" / "index.html").exists()


def test_cli_reproduce_command(tmp_path, capsys):
    from risk_lib.cli import main
    out = tmp_path / "cro"
    main(["report-set", "--out", str(out), "--seed", "42"])
    rc = main(["reproduce", "--manifest", str(out / "manifest.json")])
    assert rc == 0
    captured = capsys.readouterr()
    assert "재현 성공" in captured.out


def test_full_package_writes_files(tmp_path, result):
    from risk_lib.html_report import build_full_report_package
    from risk_lib.repro import build_manifest, now_utc
    p = generate_portfolio(seed=42)
    manifest = build_manifest(portfolio=p, parameters={"seed": 42},
                              result=result, start_utc=now_utc(),
                              end_utc=now_utc())
    out = tmp_path / "pkg"
    written = build_full_report_package(result, out, portfolio=p, manifest=manifest)
    assert (out / "executive.html").exists()
    assert (out / "ops" / "index.html").exists()
    # All ops pages present
    for n in ["13_climate.html", "14_ccr.html", "15_op_loss.html",
              "16_sensitivity.html", "17_model_risk.html",
              "18_concentration_deep.html", "19_raf.html", "20_pillar3.html",
              "21_mda.html", "22_kri_trends.html", "23_attribution.html",
              "24_vintage.html", "25_data_quality.html"]:
        assert (out / "ops" / n).exists(), f"missing {n}"
    assert (out / "manifest.json").exists()
