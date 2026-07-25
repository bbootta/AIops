"""부문별 정규 테이블·엔진 (R2 CRM · R3 RWA · R4 ECL).

핵심 명제: 테이블 합계는 **공표 수치와 정확히 대사**돼야 한다. 어긋나면
보고서에 서로 다른 값이 둘 존재하게 되고, 그 순간 데이터모델은 통제가 아니라
또 하나의 오류 원천이 된다 (RDM-005).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from risk_lib import datamodel as dm
from risk_lib.datamodel import catalog as cat
from risk_lib.datamodel.materialize import (
    materialize_all, materialize_crm, materialize_rwa, materialize_ecl,
    fitted_portfolio,
)


@pytest.fixture(scope="module")
def tables(result, portfolio):
    return materialize_all(result, portfolio)


# ----- 전체 정합 --------------------------------------------------------------

def test_all_domain_tables_validate(tables):
    v = dm.validate_all(tables)
    assert v == [], "\n".join(str(x) for x in v)


def test_every_catalog_table_is_materialized_or_declared(tables):
    """카탈로그에 있으나 실체화되지 않는 테이블은 그 사실이 드러나야 한다."""
    declared = {s.name for s in cat.ALL_TABLES}
    built = set(tables)
    # 산출 엔진이 아직 없는 테이블 (라운드 진행 중) — 명시적으로 나열
    pending = declared - built
    assert pending <= {"rdm_dq_result"}, f"미실체화 테이블: {sorted(pending)}"


# ----- 대사 (RDM-005) ---------------------------------------------------------

def test_rwa_table_reconciles_with_published_totals(tables, result):
    """SA·IRB RWA 합계가 파이프라인 공표값과 정확히 일치해야 한다."""
    r = tables["rwa_result"]
    sa = float(r[r["approach"] == "SA"]["rwa"].sum())
    irb = float(r[r["approach"] == "AIRB"]["rwa"].sum())
    assert sa == pytest.approx(result.rwa["sa"], rel=1e-12)
    assert irb == pytest.approx(result.rwa["irb"], rel=1e-12)


def test_ecl_table_reconciles_with_published_total(tables, result):
    total = float(tables["ecl_result"]["ecl"].sum())
    assert total == pytest.approx(result.ecl["total"], rel=1e-12)


def test_fitted_portfolio_is_what_the_pipeline_actually_used(portfolio, result):
    """입력 포트폴리오로 직접 재계산하면 공표값과 어긋난다 — PD가 재적합되기 때문.

    이 차이를 모르면 대사가 영원히 맞지 않는다.
    """
    from risk_lib.provisioning.ecl import compute_ecl
    classes = ["corporate", "retail_other", "residential_mortgage"]

    raw = portfolio[portfolio["asset_class"].isin(classes)]
    raw_ecl = float(compute_ecl(raw)["ecl"].sum())
    fit = fitted_portfolio(portfolio)
    fit_ecl = float(compute_ecl(fit[fit["asset_class"].isin(classes)])["ecl"].sum())

    assert fit_ecl == pytest.approx(result.ecl["total"], rel=1e-12)
    assert raw_ecl != pytest.approx(result.ecl["total"], rel=1e-6), (
        "입력 포트폴리오로도 값이 같다면 재적합 전제가 바뀐 것 — 문서 갱신 필요")


def test_fitted_portfolio_is_deterministic(portfolio):
    a, b = fitted_portfolio(portfolio), fitted_portfolio(portfolio)
    pd.testing.assert_frame_equal(a, b)


# ----- R2 · CRM ---------------------------------------------------------------

def test_crm_model_inventory_matches_source(tables):
    from risk_lib.model_inventory import build_standard_inventory
    m = tables["crm_model"]
    src = {e.model_id for e in build_standard_inventory()}
    assert set(m["model_id"]) <= src
    assert m["tier"].between(1, 3).all()
    assert not m["model_id"].duplicated().any()


def test_crm_rating_grades_come_from_master_scale(tables):
    from risk_lib.models.rating import pd_to_rating
    r = tables["crm_rating"]
    assert (r["pd"].between(0, 1)).all()
    sample = r.head(50)
    for _, row in sample.iterrows():
        assert row["grade"] == pd_to_rating(float(row["pd"]))


def test_crm_rating_is_one_row_per_obligor(tables):
    r = tables["crm_rating"]
    assert not r.duplicated(subset=["obligor_id", "asof"]).any()


def test_crm_performance_ties_to_pipeline_metrics(tables, result):
    perf = tables["crm_performance"].set_index("segment")
    for seg, m in (result.pd_metrics or {}).items():
        if seg in perf.index:
            assert perf.loc[seg, "gini"] == pytest.approx(m["gini"], rel=1e-12)


# ----- R3 · RWA ---------------------------------------------------------------

def test_no_exposure_is_double_counted_across_approaches(tables):
    """동일 익스포저가 SA·IRB에 중복 산출되면 이중계상 — PK가 이를 막는다."""
    r = tables["rwa_result"]
    assert not r.duplicated(subset=["exposure_id", "asof"]).any()
    assert set(r["approach"]) <= set(cat.APPROACHES)


def test_rwa_equals_risk_weight_times_ead(tables):
    r = tables["rwa_result"]
    expected = r["risk_weight"] * r["ead_final"]
    np.testing.assert_allclose(r["rwa"], expected, rtol=1e-9)


def test_expected_loss_only_on_irb(tables):
    """EL은 IRB 산출에서만 정의된다 (CRE31) — SA에 EL을 채우면 이중계상."""
    r = tables["rwa_result"]
    assert r[r["approach"] == "SA"]["expected_loss"].isna().all()
    assert r[r["approach"] == "AIRB"]["expected_loss"].notna().all()


def test_crm_allocation_never_over_allocates(tables):
    """CR-F008 — 배분액이 적격가치와 총 EAD를 모두 넘지 않아야 한다."""
    a = tables["rwa_crm_allocation"]
    assert (a["allocated"] <= a["eligible_value"] + 1e-6).all()
    assert (a["secured_ead"] + a["unsecured_ead"] >= a["allocated"] - 1e-6).all()
    assert (a["allocated"] >= 0).all()


def test_crm_allocation_is_not_applied_to_published_rwa(tables, result):
    """파이프라인이 CRM을 배선하지 않았다는 사실이 데이터로 확인돼야 한다.

    담보 배분이 존재하는데 RWA가 CRM 전 EAD로 산출되고 있으면, 그 격차를
    보고서가 숨기지 않고 드러내야 한다 (BNK-CRE-003 gap).
    """
    alloc = tables["rwa_crm_allocation"]
    assert alloc["allocated"].sum() > 0, "담보 배분이 전혀 없다면 전제가 다르다"
    rwa = tables["rwa_result"].set_index("exposure_id")["ead_final"]
    ex = tables["rdm_exposure"].set_index("exposure_id")["ead"]
    common = rwa.index.intersection(ex.index)
    np.testing.assert_allclose(rwa.loc[common], ex.loc[common], rtol=1e-9,
                               err_msg="RWA EAD가 원장 EAD와 다르다 — CRM이 적용됐다면 문서 갱신 필요")


# ----- R4 · ECL ---------------------------------------------------------------

def test_ecl_stage_coverage_is_monotone(tables):
    """Stage 1 ≤ 2 ≤ 3 커버리지 단조 — 비단조는 스테이징 오류 신호."""
    e = tables["ecl_result"]
    cov = e.groupby("stage").apply(
        lambda g: g["ecl"].sum() / g["ead"].sum(), include_groups=False)
    stages = sorted(cov.index)
    for a, b in zip(stages, stages[1:]):
        assert cov[a] <= cov[b] + 1e-9, f"Stage {a}→{b} 커버리지 역전"


def test_ecl_never_exceeds_ead(tables):
    e = tables["ecl_result"]
    assert (e["ecl"] <= e["ead"] + 1e-6).all()
    assert (e["coverage_ratio"].between(0, 1)).all()


def test_sicr_triggers_are_from_the_declared_set(tables):
    e = tables["ecl_result"]
    assert set(e["sicr_trigger"]) <= set(cat.SICR_TRIGGERS)
    # Stage 1은 트리거가 없어야 한다
    assert (e[e["stage"] == 1]["sicr_trigger"] == "none").all()


def test_macro_scenario_weights_sum_to_one(tables):
    """가중치 합이 1이 아니면 확률가중 ECL이 편향된다."""
    m = tables["ecl_macro_scenario"]
    by_q = m.groupby("quarter")["weight"].sum()
    np.testing.assert_allclose(by_q.to_numpy(), 1.0, atol=1e-12)


def test_macro_scenario_covers_the_forecast_axis(tables, result):
    m = tables["ecl_macro_scenario"]
    assert set(m["quarter"]) == set(result.meta["quarters"])
    assert m["pd_multiplier"].min() >= 1.0 - 1e-12   # 악화 시나리오는 배수 ≥ 1


# ----- 참조무결성 -------------------------------------------------------------

def test_domain_tables_reference_existing_entities(tables):
    from risk_lib.datamodel.spec import check_refs
    specs = {s.name: s for s in cat.ALL_TABLES if s.name in tables}
    assert check_refs(tables, specs) == []


def test_orphan_injection_is_caught(tables):
    bad = {k: v.copy() for k, v in tables.items()}
    bad["rwa_result"].loc[0, "exposure_id"] = "GHOST"
    v = dm.validate_all(bad)
    assert any(x.rule == "fk_orphan" and x.table == "rwa_result" for x in v)
