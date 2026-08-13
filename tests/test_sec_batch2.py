"""증권 부문 미구현 요건 (SEC-CCR-003 · SEC-LIQ-001 · SEC-OAI-001 · SEC-OAI-003
· SEC-PRC-002 · INT-004).

원장이 스펙을 지키는지, 통제가 실제로 발동하는지, 근거가 없는 값을 조용히
채우지 않는지를 본다.
"""

from __future__ import annotations

import pandas as pd
import pytest

from risk_lib import close_workflow as cw
from risk_lib import funding, margin, market_feed as mf, product_master as pm, rcsa
from risk_lib.ccr import synthesise_derivatives
from risk_lib.datamodel.spec import TableSpec, check_refs, validate

ASOF = "2026-06-11"
SEED = 42

_MODULES = (margin, funding, rcsa, cw, pm, mf)


def _specs(module) -> dict[str, TableSpec]:
    return {s.name: s for s in module.SPECS}


@pytest.mark.parametrize("module", _MODULES, ids=lambda m: m.__name__)
def test_every_spec_declares_grain_key_and_units(module):
    for spec in module.SPECS:
        assert spec.grain.strip(), f"{spec.name}: 입도 미기재"
        assert spec.primary_key, f"{spec.name}: 기본키 미지정"
        for col in spec.columns:
            if col.dtype == "float":
                assert col.unit, f"{spec.name}.{col.name}: float 컬럼에 단위 없음"


# ----- SEC-CCR-003 증거금·담보 -------------------------------------------------

@pytest.fixture(scope="module")
def derivative_trades(portfolio):
    return synthesise_derivatives(portfolio[portfolio["asset_class"] == "bank"],
                                  seed=SEED)


@pytest.fixture(scope="module")
def margin_tables(derivative_trades):
    return margin.build_margin(derivative_trades, asof=ASOF, seed=SEED)


def test_margin_ledgers_match_specs_and_references(margin_tables):
    tables, _warnings = margin_tables
    specs = _specs(margin)
    for name, frame in tables.items():
        assert not validate(frame, specs[name]), f"{name} 스펙 위반"
    assert not check_refs(tables, specs)


def test_haircut_is_skipped_and_the_skip_is_reported(margin_tables):
    """감독조정계수를 못 봤으므로 적용하지 않고, 그 사실이 경고로 나온다."""
    tables, warnings = margin_tables
    coll = tables["ccr_collateral_position"]
    assert coll["supervisory_haircut"].isna().all()
    assert (coll["collateral_value"] == coll["market_value"]).all()
    assert any("조정계수" in w for w in warnings)


def test_call_below_minimum_transfer_amount_is_not_raised():
    """콜 금액이 최소이전금액에 못 미치면 이전 의무가 없다."""
    csa = pd.DataFrame([{
        "netting_set_id": "NS-1", "counterparty": "C1", "csa_type": "양방향",
        "threshold": 0.0, "mta": 1_000.0, "independent_amount": 0.0,
        "call_frequency": "일별", "mpor_days": None, "currency": "KRW",
        "evidence_status": "재량·미규정"}])
    collateral = pd.DataFrame([{
        "position_id": "P1", "netting_set_id": "NS-1", "collateral_type": "현금",
        "market_value": 9_500.0, "supervisory_haircut": None,
        "collateral_value": 9_500.0, "haircut_status": "미적용",
        "evidence_status": "미확인"}])
    exposures = pd.DataFrame([{"netting_set_id": "NS-1", "exposure": 10_000.0}])
    calls = margin.compute_margin_calls(csa, collateral, exposures, asof=ASOF)
    assert calls.iloc[0]["call_amount"] == 0.0
    assert calls.iloc[0]["status"] == "충족"

    exposures.loc[0, "exposure"] = 11_000.0
    calls = margin.compute_margin_calls(csa, collateral, exposures, asof=ASOF)
    assert calls.iloc[0]["direction"] == "수취"
    assert calls.iloc[0]["status"] == "콜발생"


def test_disputed_netting_sets_are_not_left_as_settled(margin_tables):
    tables, _ = margin_tables
    calls, disputes = tables["ccr_margin_call"], tables["ccr_margin_dispute"]
    for ns in disputes["netting_set_id"]:
        assert calls[calls["netting_set_id"] == ns].iloc[0]["status"] == "분쟁"


def test_margin_build_is_deterministic(derivative_trades):
    a, _ = margin.build_margin(derivative_trades, asof=ASOF, seed=SEED)
    b, _ = margin.build_margin(derivative_trades, asof=ASOF, seed=SEED)
    pd.testing.assert_frame_equal(a["ccr_margin_call"], b["ccr_margin_call"])


# ----- SEC-LIQ-001 단기조달 ----------------------------------------------------

@pytest.fixture(scope="module")
def funding_tables():
    return funding.build_funding(asof=ASOF, base_rate=0.032, seed=SEED)


def test_funding_ledgers_match_specs(funding_tables):
    tables, _ = funding_tables
    specs = _specs(funding)
    for name, frame in tables.items():
        assert not validate(frame, specs[name]), f"{name} 스펙 위반"


def test_ladder_covers_every_trade_exactly_once(funding_tables):
    tables, _ = funding_tables
    trades, ladder = tables["liq_funding_trade"], tables["liq_funding_ladder"]
    assert ladder["amount"].sum() == pytest.approx(trades["principal"].sum())
    assert ladder["cumulative_share"].iloc[-1] == pytest.approx(1.0)


def test_concentration_shares_sum_to_one_per_axis(funding_tables):
    tables, _ = funding_tables
    conc = tables["liq_funding_concentration"]
    for dim, part in conc.groupby("dimension"):
        # 비중은 6자리로 반올림해 싣는다. 항목 수만큼 반올림 오차가 쌓인다.
        assert part["share"].sum() == pytest.approx(1.0, abs=1e-4), dim
        assert part["hhi"].nunique() == 1


def test_funding_limits_are_not_judged_without_a_threshold(funding_tables):
    tables, skipped = funding_tables
    limits = tables["liq_funding_limit"]
    assert limits["threshold"].isna().all()
    assert set(limits["decision"]) == {"판정불가"}
    assert len(skipped) == len(limits)


def test_funding_build_is_deterministic():
    a, _ = funding.build_funding(asof=ASOF, base_rate=0.032, seed=SEED)
    b, _ = funding.build_funding(asof=ASOF, base_rate=0.032, seed=SEED)
    pd.testing.assert_frame_equal(a["liq_funding_trade"], b["liq_funding_trade"])


# ----- SEC-OAI-001 RCSA --------------------------------------------------------

@pytest.fixture(scope="module")
def rcsa_tables():
    return rcsa.build_rcsa(asof=ASOF)


def test_rcsa_ledgers_match_specs_and_references(rcsa_tables):
    specs = _specs(rcsa)
    for name, frame in rcsa_tables.items():
        assert not validate(frame, specs[name]), f"{name} 스펙 위반"
    assert not check_refs(rcsa_tables, specs)


def test_residual_risk_falls_as_control_effectiveness_rises(rcsa_tables):
    a = rcsa_tables["opr_rcsa_assessment"]
    assert (a["residual_score"] <= a["inherent_score"]).all()
    strong = a[a["effectiveness_factor"] >= 0.70]
    weak = a[a["effectiveness_factor"] <= 0.10]
    ratio_strong = (strong["residual_score"] / strong["inherent_score"]).max()
    ratio_weak = (weak["residual_score"] / weak["inherent_score"]).min()
    assert ratio_strong < ratio_weak


def test_grade_bands_do_not_overlap_at_the_boundary(rcsa_tables):
    """경계값은 한 등급에만 속한다. 6.0이 두 구간에 걸치면 등급이 둘이 된다."""
    scale = rcsa_tables["opr_rcsa_scale"]
    assert rcsa.grade_residual(scale, 6.0) == "낮음"
    assert rcsa.grade_residual(scale, 6.0001) == "중간"
    assert rcsa.grade_residual(scale, 0.0) == "낮음"


def test_every_non_low_assessment_gets_an_action(rcsa_tables):
    a, act = rcsa_tables["opr_rcsa_assessment"], rcsa_tables["opr_rcsa_action"]
    need = set(a[a["residual_grade"] != "낮음"]["assessment_id"])
    assert set(act["assessment_id"]) == need


def test_rcsa_uses_the_loss_event_vocabulary(rcsa_tables):
    from risk_lib.op_loss import EVENT_TYPES
    assert set(rcsa_tables["opr_rcsa_assessment"]["event_type"]) <= set(EVENT_TYPES)


def test_loss_comparison_is_empty_without_a_loss_ledger(rcsa_tables):
    out = rcsa.compare_with_losses(rcsa_tables["opr_rcsa_assessment"], None)
    assert out.empty


# ----- SEC-OAI-003 마감 워크플로 -----------------------------------------------

def test_close_gate_blocks_a_step_whose_predecessor_is_incomplete():
    tables, issues = cw.build_close_workflow({}, asof=ASOF)
    specs = _specs(cw)
    for name, frame in tables.items():
        assert not validate(frame, specs[name]), f"{name} 스펙 위반"
    assert not check_refs(tables, specs)
    gates = tables["opr_close_gate"]
    assert gates[gates["task_id"] == "CL-01"].iloc[0]["decision"] == "진행가능"
    assert gates[gates["task_id"] == "CL-11"].iloc[0]["decision"] == "차단"
    assert issues


def test_out_of_order_completion_is_reported_separately():
    """선행이 미완인데 완료된 단계는 차단이 아니라 순서위반이다."""
    tables, _ = cw.build_close_workflow(
        {"gov_approval": pd.DataFrame({"a": [1]})}, asof=ASOF)
    gates = tables["opr_close_gate"]
    assert gates[gates["task_id"] == "CL-11"].iloc[0]["decision"] == "순서위반"


def test_every_evidence_table_exists_in_the_catalog():
    """증빙 원장 이름이 틀리면 그 단계는 영원히 미완료로 남는다."""
    from risk_lib.datamodel import catalog as cat
    names = {s.name for s in cat.ALL_TABLES}
    tasks = cw.build_close_tasks({})
    missing = sorted(set(tasks["evidence_table"]) - names)
    assert not missing, f"카탈로그에 없는 증빙 원장 {missing}"


def test_credit_rwa_evidence_survives_an_all_irb_book():
    """CL-04 의 증빙은 산출법에 흔들리지 않아야 한다.

    rwa_sa_bucket 은 approach=="SA" 행만 담는다. 국채·은행 익스포저가 없는
    책이면 0행이고, 그걸 증빙으로 삼으면 신용 RWA 를 다 산출하고도 이 단계가
    미완료가 된다. 실제로 그렇게 돼 있었다.
    """
    irb_only = {
        "rwa_result": pd.DataFrame({"exposure_id": ["E1", "E2"],
                                    "approach": ["AIRB", "FIRB"],
                                    "rwa": [100.0, 200.0]}),
        "rwa_sa_bucket": pd.DataFrame(columns=["asof", "asset_class"]),
    }
    tasks = cw.build_close_tasks(irb_only).set_index("task_id")
    assert tasks.loc["CL-04", "status"] == "완료", (
        f"증빙 {tasks.loc['CL-04', 'evidence_table']} 이 산출법에 흔들린다")


def test_each_calculation_step_points_at_its_primary_ledger():
    """산출 단계의 증빙은 그 리스크의 주 산출 원장이다. 한 산출법의 집계가 아니다."""
    tasks = cw.build_close_tasks({}).set_index("task_id")
    assert tasks.loc["CL-04", "evidence_table"] == "rwa_result"
    assert tasks.loc["CL-05", "evidence_table"] == "ecl_result"
    assert tasks.loc["CL-06", "evidence_table"] == "mkt_var_es"
    assert tasks.loc["CL-07", "evidence_table"] == "alm_irrbb_result"


def test_task_status_comes_from_evidence_not_from_a_flag():
    tables, _ = cw.build_close_workflow(
        {"rdm_snapshot": pd.DataFrame({"a": [1, 2]})}, asof=ASOF)
    tasks = tables["opr_close_task"].set_index("task_id")
    assert tasks.loc["CL-01", "status"] == "완료"
    assert tasks.loc["CL-01", "evidence_rows"] == 2
    assert tasks.loc["CL-02", "status"] == "미완료"


# ----- SEC-PRC-002 상품·평가모형 -----------------------------------------------

@pytest.fixture(scope="module")
def product_tables():
    return pm.build_product_master(asof=ASOF)


def test_product_ledgers_match_specs_and_references(product_tables):
    tables, _ = product_tables
    specs = _specs(pm)
    for name, frame in tables.items():
        assert not validate(frame, specs[name]), f"{name} 스펙 위반"
    assert not check_refs(tables, specs)


def test_product_without_an_approved_official_model_cannot_be_priced(product_tables):
    tables, unpriced = product_tables
    judged = pm.judge_pricing(tables["mkt_product"], tables["mkt_pricing_model"],
                              tables["mkt_product_model_map"])
    assert "PRD-SWO" in set(judged[judged["decision"] == "평가불가"]["product_id"])
    assert unpriced


def test_approval_alone_is_not_enough_without_validation(product_tables):
    """승인만 있고 검증이 끝나지 않은 모형은 평가 근거가 되지 못한다."""
    tables, _ = product_tables
    mappings = tables["mkt_product_model_map"].copy()
    hit = ((mappings["product_id"] == "PRD-SWO")
           & (mappings["model_use"] == "공식평가"))
    mappings.loc[hit, "is_approved"] = True
    judged = pm.judge_pricing(tables["mkt_product"], tables["mkt_pricing_model"],
                              mappings)
    row = judged[judged["product_id"] == "PRD-SWO"].iloc[0]
    assert row["decision"] == "평가불가"
    assert "검증 상태가 검증중" in row["reason"]


# ----- INT-004 시장데이터 어댑터 -----------------------------------------------

def test_feed_ledgers_match_specs_and_report_unconnected():
    tables, unconnected = mf.build_market_feed(asof=ASOF)
    specs = _specs(mf)
    for name, frame in tables.items():
        assert not validate(frame, specs[name]), f"{name} 스펙 위반"
    assert not check_refs(tables, specs)
    assert (tables["int_market_feed"]["connection_status"] == "미연결").all()
    assert tables["int_market_feed"]["last_sync"].isna().all()
    assert len(unconnected) == len(tables["int_market_feed"])
    assert (tables["int_feed_health"]["received_factors"] == 0).all()


def test_synthetic_fallback_is_labelled_as_synthetic():
    def provider(*, asof, factors):
        return {f: 0.03 for f in factors}

    tables, _ = mf.build_market_feed(asof=ASOF, synthetic_provider=provider)
    health = tables["int_feed_health"]
    assert (health["data_source"] == "합성").all()
    assert (health["status"] != "정상").all()


def test_staleness_stays_null_when_nothing_was_ever_received():
    tables, _ = mf.build_market_feed(asof=ASOF)
    assert tables["int_feed_health"]["staleness_days"].isna().all()


def test_adapters_satisfy_the_protocol():
    assert isinstance(mf.UnconnectedFeedAdapter("F", "사유"), mf.MarketFeedAdapter)
    assert isinstance(mf.SyntheticFeedAdapter("F", lambda **k: {}),
                      mf.MarketFeedAdapter)
