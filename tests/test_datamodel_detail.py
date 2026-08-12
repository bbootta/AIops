"""세분화 테이블(R11) — 입도·도메인·상위 테이블과의 대사.

세분화의 목적은 테이블 수가 아니라 **답할 수 있는 질문의 수**다. 각 테이블이
(a) 상위 산출 테이블과 정확히 대사되고, (b) 도메인이 실제 데이터에서 왔고,
(c) 규정 라인을 채울 수 있는 입도인지를 고정한다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from risk_lib.datamodel import catalog as cat
from risk_lib.datamodel.materialize_detail import (
    classify_asset_quality, _MIN_PROVISION_RATE,
)


@pytest.fixture(scope="module")
def tables(result, portfolio):
    from risk_lib.ui_studio.studio import build_studio
    return build_studio(result, portfolio).tables


# ----- 카탈로그 규모·규율 ------------------------------------------------------

def test_catalog_is_subdivided_across_every_domain():
    from collections import Counter
    n = Counter(s.product for s in cat.ALL_TABLES)
    # 부문마다 결과 1장짜리 입도로는 규제 라인을 채울 수 없다.
    for product in ("PRD-RDM", "PRD-CRM", "PRD-RWA", "PRD-ECL", "PRD-ALM",
                    "PRD-MKT", "PRD-OPR", "PRD-REG", "PRD-UIX", "PRD-VAL"):
        assert n[product] >= 3, f"{product} 세분화 부족: {n[product]}장"
    assert len(cat.ALL_TABLES) >= 60


def test_every_detail_table_declares_grain_and_keys():
    for spec in cat.DETAIL_TABLES:
        assert spec.grain and "1행" in spec.grain, spec.name
        assert spec.primary_key, f"{spec.name} 기본키 없음"


def test_grade_domain_comes_from_the_actual_master_scale():
    from risk_lib.models.rating import DEFAULT_MASTER_SCALE
    assert set(g.grade for g in DEFAULT_MASTER_SCALE) <= set(cat.GRADES)
    # 쓰이지 않는 조합 등급이 도메인에 남아 있으면 검증이 무의미해진다.
    assert "AAA+" not in cat.GRADES and "AAA-" not in cat.GRADES


def test_repricing_bucket_domain_matches_the_alm_engine(tables):
    assert set(tables["alm_repricing_gap"]["bucket"]) <= set(cat.REPRICING_BUCKETS)


# ----- RDM 세분화 -------------------------------------------------------------

def test_exposure_balance_reconciles_with_the_exposure_ledger(tables):
    bal, exp = tables["rdm_exposure_balance"], tables["rdm_exposure"]
    assert len(bal) == len(exp)
    assert float(bal["ead"].sum()) == pytest.approx(float(exp["ead"].sum()),
                                                    rel=1e-12)


def test_asset_quality_classification_is_monotone_in_dpd():
    order = {c: i for i, c in enumerate(cat.ASSET_QUALITY)}
    prev = -1
    for dpd in (0, 1, 89, 90, 364, 365, 729, 730, 5000):
        cur = order[classify_asset_quality(dpd)]
        assert cur >= prev, dpd
        prev = cur


def test_provision_rates_increase_with_severity():
    for bt, rates in _MIN_PROVISION_RATE.items():
        vals = [rates[c] for c in cat.ASSET_QUALITY]
        assert vals == sorted(vals), bt
        assert vals[-1] == 1.0, f"{bt} 추정손실은 100%여야 한다"


def test_asset_quality_balance_ties_to_the_portfolio(tables, portfolio):
    from risk_lib.datamodel.materialize import fitted_portfolio
    p = fitted_portfolio(portfolio)
    assert float(tables["rdm_asset_quality"]["balance"].sum()) == pytest.approx(
        float(p["balance"].sum()), rel=1e-12)


def test_reserve_shortfall_is_never_negative(tables):
    assert (tables["rdm_asset_quality"]["reserve_shortfall"] >= 0).all()


def test_canonical_map_source_codes_are_unique(tables):
    m = tables["rdm_canonical_map"]
    assert not m.duplicated(subset=["source_system", "domain", "source_code"]).any()


def test_dq_rules_cover_every_declared_constraint(tables):
    rules = tables["rdm_dq_rule"]
    for spec in cat.ALL_TABLES:
        sub = rules[rules["table_name"] == spec.name]
        n_expected = (sum(1 for c in spec.columns if not c.nullable)
                      + sum(1 for c in spec.columns if c.allowed)
                      + sum(1 for c in spec.columns
                            if c.min_value is not None or c.max_value is not None)
                      + (1 if spec.primary_key else 0)
                      + len(spec.foreign_keys))
        assert len(sub) == n_expected, spec.name


def test_reconciliation_gaps_are_within_tolerance(tables):
    rec = tables["rdm_reconciliation"]
    assert (rec["status"] == "PASS").all(), rec[rec["status"] != "PASS"].to_dict()


# ----- CRM 세분화 -------------------------------------------------------------

def test_rating_migration_rows_sum_to_one_per_from_grade(tables):
    m = tables["crm_rating_migration"]
    assert len(m) > 0
    s = m.groupby(["segment", "asof", "from_grade"])["share"].sum()
    assert np.allclose(s.to_numpy(), 1.0)


def test_lgd_components_reconstruct_the_segment_lgd(tables):
    c = tables["crm_lgd_component"]
    for (seg, asof), sub in c.groupby(["segment", "asof"]):
        d = dict(zip(sub["component"], sub["value"]))
        rebuilt = 1.0 - (d["gross_recovery"] + d["direct_cost"]
                         + d["indirect_cost"] + d["discount_effect"])
        assert rebuilt == pytest.approx(d["net_lgd"], abs=1e-9), seg


def test_pd_calibration_grades_are_in_the_master_scale(tables):
    assert set(tables["crm_pd_calibration"]["grade"]) <= set(cat.GRADES)


def test_ews_signals_are_proposal_only(tables):
    e = tables["crm_ews_signal"]
    assert len(e) > 0
    assert e["action"].str.contains("제안").all()


# ----- RWA 세분화 -------------------------------------------------------------

def test_sa_bucket_totals_match_the_published_sa_rwa(tables, result):
    assert float(tables["rwa_sa_bucket"]["rwa"].sum()) == pytest.approx(
        result.rwa["sa"], rel=1e-9)


def test_irb_pool_totals_match_the_published_irb_rwa(tables, result):
    assert float(tables["rwa_irb_pool"]["rwa"].sum()) == pytest.approx(
        result.rwa["irb"], rel=1e-9)


def test_irb_pool_weighted_parameters_are_ead_weighted(tables):
    """가중평균이 단순평균이면 큰 익스포저의 위험이 희석된다."""
    p = tables["rwa_irb_pool"]
    assert (p["pd_weighted"].between(0, 1)).all()
    assert (p["lgd_weighted"].between(0, 1)).all()
    assert (p["rw_average"] >= 0).all()
    recomputed = p["rwa"] / p["ead"].replace(0.0, np.nan)
    assert np.allclose(p["rw_average"], recomputed.fillna(0.0), atol=1e-9)


def test_market_components_sum_to_the_published_market_rwa(tables, result):
    assert float(tables["rwa_market_component"]["rwa"].sum()) == pytest.approx(
        result.rwa["market"], rel=1e-9)


def test_bi_components_sum_to_the_business_indicator(tables, result):
    bi = tables["rwa_operational_bi"]
    assert set(bi["component"]) == set(cat.BI_COMPONENTS)
    assert float(bi["amount"].sum()) == pytest.approx(
        float(result.rwa["op_detail"].bi), rel=1e-12)
    assert float(bi["share"].sum()) == pytest.approx(1.0, abs=1e-12)


def test_output_floor_row_matches_the_engine(tables, result):
    f = tables["rwa_output_floor"].iloc[0]
    fl = result.rwa["output_floor"]
    assert f["internal_rwa"] == pytest.approx(fl.rwa_internal, rel=1e-15)
    assert bool(f["binding"]) == bool(fl.is_binding)


# ----- ECL 세분화 -------------------------------------------------------------

def test_sicr_trigger_stats_cover_stage2_ecl(tables, result):
    s = tables["ecl_sicr_trigger_stat"]
    ecl = tables["ecl_result"]
    stage2 = float(ecl.loc[ecl["stage"] == 2, "ecl"].sum())
    assert float(s["ecl"].sum()) == pytest.approx(stage2, rel=1e-9)


def test_provision_bridge_closes_on_the_engine_value(tables, result):
    b = tables["ecl_provision_bridge"].sort_values("seq")
    assert list(b["step"])[0] == "opening" and list(b["step"])[-1] == "closing"
    # 누계는 단조 구성이 아니라 요인 합이어야 한다 — 마지막 누계가 기말이다.
    closing = float(b.iloc[-1]["cumulative"])
    interim = float(b.iloc[0]["amount"]) + float(
        b[~b["step"].isin(("opening", "closing"))]["amount"].sum())
    assert closing == pytest.approx(interim, rel=1e-9)


# ----- ALM 세분화 -------------------------------------------------------------

def test_lcr_items_reconstruct_the_ratio(tables, result):
    t = tables["alm_lcr_item"]
    lcr = result.alm["lcr"]
    assert float(t[t["section"] == "HQLA"]["weighted"].sum()) == pytest.approx(
        lcr.hqla_total, rel=1e-9)
    assert float(t[t["section"] == "OUTFLOW"]["weighted"].sum()) == pytest.approx(
        lcr.gross_outflow, rel=1e-9)


def test_nsfr_items_reconstruct_the_ratio(tables, result):
    t = tables["alm_nsfr_item"]
    n = result.alm["nsfr"]
    asf = float(t[t["section"] == "ASF"]["weighted"].sum())
    rsf = float(t[t["section"] == "RSF"]["weighted"].sum())
    assert asf / rsf == pytest.approx(n.nsfr, rel=1e-9)


def test_repricing_gap_cumulates(tables):
    g = tables["alm_repricing_gap"].sort_values("seq")
    assert np.allclose(g["cumulative_gap"].to_numpy(),
                       g["gap"].cumsum().to_numpy())
    assert np.allclose((g["asset"] - g["liability"]).to_numpy(),
                       g["gap"].to_numpy())


# ----- MKT / OPR 세분화 -------------------------------------------------------

def test_risk_factors_come_from_the_same_snapshot_as_the_market_page(tables, result):
    from risk_lib.market_data import demo_market_data
    snaps, _, _ = demo_market_data(asof=result.meta["asof"],
                                   seed=result.meta.get("seed", 42))
    expected = sum(len(s.quotes) for s in snaps)
    assert len(tables["mkt_risk_factor"]) == expected


def test_backtest_zone_escalates_with_cumulative_exceptions(tables):
    b = tables["mkt_backtest_exception"].sort_values("obs_date")
    cum = b["exception"].cumsum()
    for zone, c in zip(b["zone"], cum):
        assert zone == ("green" if c <= 4 else "amber" if c <= 9 else "red")


def test_op_recovery_ties_to_the_loss_register(tables):
    rec = tables["opr_recovery"]
    ev = tables["opr_loss_event"]
    assert set(rec["event_id"]) <= set(ev["event_id"]), "참조무결성 위반"
    merged = rec.groupby("event_id")["amount"].sum()
    ev_rec = ev.set_index("event_id")["recovery"]
    common = merged.index.intersection(ev_rec.index)
    assert np.allclose(merged.loc[common].to_numpy(),
                       ev_rec.loc[common].to_numpy())


def test_psmor_controls_cover_all_twelve_principles(tables):
    c = tables["opr_control"]
    assert sorted(c["principle"]) == list(range(1, 13))


def test_op_kri_status_follows_thresholds(tables):
    for _, r in tables["opr_kri"].iterrows():
        expected = ("red" if r["value"] >= r["threshold_red"]
                    else "amber" if r["value"] >= r["threshold_amber"]
                    else "green")
        assert r["status"] == expected, r["kri_id"]
