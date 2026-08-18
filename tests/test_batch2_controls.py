"""변경·가격 통제 · 리스크 인벤토리 · 외부 연계 원장
(GOV-006 · GOV-008 · BNK-ST-001 · INT-001 · INT-002 · INT-003 · INT-008).

검사 원칙은 넷이다.

1. 통제는 **실패할 수 있어야** 통제다. 위반 사례를 만들어 판정이 실제로
   발동하는지 본다.
2. 근거 없는 값은 판정하지 않는다. 임계값이 NULL이면 '판정불가'가 나와야 하고
   기본값으로 메워지면 안 된다.
3. 기록이 없는 것은 통과가 아니다. 실행 기록 없는 통제는 '미실시'다.
4. 같은 입력은 같은 출력을 낸다.
"""

from __future__ import annotations

import pandas as pd
import pytest

from risk_lib.datamodel.spec import TableSpec, check_refs, validate
from risk_lib.governance import change_control as cc, pricing_control as pc
from risk_lib.icaap import risk_inventory as ri
from risk_lib.integration import (
    connector, engine_adapter, inbound, resilience,
)

ASOF = "2026-06-30"

_MODULES = (cc, pc, ri, connector, inbound, engine_adapter, resilience)


def _specs(*modules) -> dict[str, TableSpec]:
    out: dict[str, TableSpec] = {}
    for module in modules:
        out.update({s.name: s for s in module.SPECS})
    return out


# ----- 스펙 품질 --------------------------------------------------------------

@pytest.mark.parametrize("module", _MODULES, ids=lambda m: m.__name__)
def test_every_spec_declares_grain_key_and_units(module):
    """입도·기본키가 있어야 하고 float 컬럼은 단위를 적어야 한다."""
    for spec in module.SPECS:
        assert spec.grain.strip(), f"{spec.name}: 입도 미기재"
        assert spec.primary_key, f"{spec.name}: 기본키 미지정"
        for col in spec.columns:
            if col.dtype == "float":
                assert col.unit, f"{spec.name}.{col.name}: float 컬럼에 단위 없음"


def test_foreign_keys_point_at_specs_that_exist():
    """FK 대상 테이블은 이 배치의 스펙 집합 안에 있어야 한다.

    int_inbound_contract는 int_connector를 가리킨다. 모듈이 갈라져 있어도
    배선 시점에는 한 카탈로그에 함께 들어가야 참조가 성립한다.
    """
    known = set(_specs(*_MODULES))
    for module in _MODULES:
        for spec in module.SPECS:
            for fk in spec.foreign_keys:
                assert fk.ref_table in known, (
                    f"{spec.name}: FK 대상 {fk.ref_table} 스펙 없음")


# ----- GOV-008 변경통제 -------------------------------------------------------

def _change(**over) -> dict:
    base = dict(change_id="CH-001", change_class="규정", risk_tier="상",
                title="금리충격 개정 반영", target_ref="[별표 9-1] <표5>",
                requested_on="2026-02-02", requester_role="ALM담당",
                state="심의중", rollback_ref="2026-03-31/v01",
                citation="시행세칙 [별표 9-1] 개정 2026.1.29")
    base.update(over)
    return base


def _controls(change_id: str, steps, status: str = "완료") -> list[dict]:
    return [dict(change_id=change_id, control_step=s, status=status,
                 performed_on="2026-02-03", performer_role="ALM담당",
                 evidence_ref=f"evidence/{s}") for s in steps]


def _impact(change_id: str) -> dict:
    return dict(change_id=change_id, impact_kind="원장",
                impact_ref="irrbb_shock", regression_required=True,
                note="통화별 금리충격표가 통째로 바뀐다")


@pytest.fixture(scope="module")
def change_tables():
    return cc.build_change_control(
        [_change()], [_impact("CH-001")],
        _controls("CH-001", cc.CONTROL_STEPS))


def test_change_ledgers_match_their_specs(change_tables):
    specs = _specs(cc)
    for name, frame in change_tables.items():
        assert not validate(frame, specs[name]), f"{name} 스펙 위반"
    assert not check_refs(change_tables, specs)


def test_change_policy_covers_every_class_tier_step():
    """정책 원장에 빈 조합이 있으면 그 조합의 게이트가 근거를 잃는다."""
    policy = cc.build_change_policy()
    expected = len(cc.CHANGE_CLASSES) * len(cc.RISK_TIERS) * len(cc.CONTROL_STEPS)
    assert len(policy) == expected
    assert not policy.duplicated(
        subset=["change_class", "risk_tier", "control_step"]).any()


def test_top_tier_regulation_change_requires_all_five_steps():
    policy = cc.build_change_policy()
    assert set(cc.required_steps(policy, "규정", "상")) == set(cc.CONTROL_STEPS)


def test_gate_passes_only_when_every_required_step_is_complete(change_tables):
    gate = change_tables["gov_change_gate"]
    row = gate.iloc[0]
    assert row["decision"] == "배포가능"
    assert row["n_required"] == row["n_satisfied"] == len(cc.CONTROL_STEPS)
    assert row["blocking_steps"] == ""


def test_missing_control_record_blocks_deployment():
    """실행 기록이 없는 필수 단계는 '미실시'이고 배포불가다."""
    partial = [s for s in cc.CONTROL_STEPS if s != "독립검증"]
    tables = cc.build_change_control(
        [_change()], [_impact("CH-001")], _controls("CH-001", partial))
    row = tables["gov_change_gate"].iloc[0]
    assert row["decision"] == "배포불가"
    assert "독립검증" in row["blocking_steps"]
    assert "독립검증=미실시" in row["reason"]


def test_failed_regression_blocks_even_when_step_is_not_required():
    """필수가 아닌 단계라도 실행해서 실패했으면 게이트가 잡는다."""
    steps = _controls("CH-002", ("영향평가",))
    steps += _controls("CH-002", ("독립검증",), status="실패")
    tables = cc.build_change_control(
        [_change(change_id="CH-002", change_class="데이터", risk_tier="하")],
        [_impact("CH-002")], steps)
    row = tables["gov_change_gate"].iloc[0]
    assert row["decision"] == "배포불가"
    assert "독립검증" in row["blocking_steps"]


def test_impact_assessment_without_any_impact_row_is_blocked():
    tables = cc.build_change_control(
        [_change()], [], _controls("CH-001", cc.CONTROL_STEPS))
    row = tables["gov_change_gate"].iloc[0]
    assert row["decision"] == "배포불가"
    assert "영향대상 0건" in row["reason"]


def test_missing_rollback_target_is_blocked():
    tables = cc.build_change_control(
        [_change(rollback_ref=None)], [_impact("CH-001")],
        _controls("CH-001", cc.CONTROL_STEPS))
    row = tables["gov_change_gate"].iloc[0]
    assert row["decision"] == "배포불가"
    assert "롤백 대상 판 미지정" in row["reason"]


def test_unknown_class_tier_combination_is_fail_closed():
    """정책에 없는 조합은 통과시키지 않는다."""
    policy = cc.build_change_policy()
    policy = policy[policy["change_class"] != "규정"]
    req = pd.DataFrame([_change()])
    gate = cc.evaluate_change_gate(
        req, policy, pd.DataFrame(_controls("CH-001", cc.CONTROL_STEPS)),
        pd.DataFrame([_impact("CH-001")]))
    row = gate.iloc[0]
    assert row["decision"] == "배포불가"
    assert "판정 근거가 없으므로" in row["reason"]


def test_empty_ledgers_still_match_their_specs():
    """비었을 때만 스펙 검증이 실패하는 유형을 막는다."""
    tables = cc.build_change_control([], [], [])
    specs = _specs(cc)
    for name, frame in tables.items():
        assert not validate(frame, specs[name]), f"{name} 스펙 위반"
    empty = resilience.build_resilience([])
    rspecs = _specs(resilience)
    for name, frame in empty.items():
        assert not validate(frame, rspecs[name]), f"{name} 스펙 위반"


def test_change_gate_is_deterministic():
    args = ([_change()], [_impact("CH-001")],
            _controls("CH-001", cc.CONTROL_STEPS))
    a = cc.build_change_control(*args)["gov_change_gate"]
    b = cc.build_change_control(*args)["gov_change_gate"]
    pd.testing.assert_frame_equal(a, b)


# ----- GOV-006 시장·가격 통제 -------------------------------------------------

@pytest.fixture(scope="module")
def pricing_tables():
    obs = [{"desk": "금리", "control_id": "PC-PLA", "verdict": "green",
            "metric_value": 0.91, "evidence_ref": "frtb/plat"},
           {"desk": "금리", "control_id": "PC-RBK", "verdict": "가능",
            "metric_value": None, "evidence_ref": "archive/scan"}]
    return pc.build_pricing_control(obs, asof=ASOF, desks=["금리", "외환"])


def test_pricing_ledgers_match_their_specs(pricing_tables):
    specs = _specs(pc)
    for name, frame in pricing_tables.items():
        assert not validate(frame, specs[name]), f"{name} 스펙 위반"
    assert not check_refs(pricing_tables, specs)


def test_source_rank_marks_front_office_as_not_independent():
    """자기 가격을 자기가 확인하는 것은 독립검증이 아니다."""
    rank = pc.build_source_rank()
    fo = rank[rank["price_source"] == "front_office"].iloc[0]
    assert not bool(fo["independent"])
    assert bool(rank[rank["price_source"] == "consensus"].iloc[0]["independent"])


def test_source_rank_follows_the_ipv_module_not_a_second_copy():
    """위계를 두 곳에 적으면 갈라진다. ipv 모듈이 유일한 정의다."""
    from risk_lib import ipv
    rank = pc.build_source_rank().set_index("price_source")["rank"].to_dict()
    assert rank == {k: int(v) for k, v in ipv.SOURCE_RANK.items()}


def test_every_threshold_is_null_and_marked_unconfirmed():
    """임계값을 지어내지 않았음을 원장이 스스로 증명해야 한다."""
    controls = pc.build_pricing_controls()
    assert controls["threshold_value"].isna().all()
    assert (controls["evidence_status"] == "미확인").all()


def test_control_without_threshold_or_verdict_is_undecidable():
    """임계값도 허용 판정값도 없으면 '판정불가'다. 유효로 넘기지 않는다."""
    controls = pc.build_pricing_controls()
    obs = pd.DataFrame([{"desk": "금리", "control_id": "PC-IPV",
                         "verdict": None, "metric_value": 0.99,
                         "evidence_ref": "ipv/run"}])
    out = pc.evaluate_pricing_controls(controls, obs, asof=ASOF, desks=["금리"])
    row = out[out["control_id"] == "PC-IPV"].iloc[0]
    assert row["status"] == "판정불가"
    assert "임계값 미확정" in row["reason"]


def test_control_without_observation_is_not_run(pricing_tables):
    results = pricing_tables["gov_pricing_result"]
    fx = results[(results["desk"] == "외환")]
    assert (fx["status"] == "미실시").all()


def test_red_pla_zone_is_deficient(pricing_tables):
    controls = pc.build_pricing_controls()
    obs = pd.DataFrame([{"desk": "금리", "control_id": "PC-PLA",
                         "verdict": "red", "metric_value": 0.4,
                         "evidence_ref": "frtb/plat"}])
    out = pc.evaluate_pricing_controls(controls, obs, asof=ASOF, desks=["금리"])
    row = out[out["control_id"] == "PC-PLA"].iloc[0]
    assert row["status"] == "미흡"


def test_threshold_comparison_fires_when_a_threshold_is_supplied():
    """임계값이 승인되면 비교 판정이 실제로 돈다. 방향도 지켜져야 한다."""
    controls = pc.build_pricing_controls()
    controls.loc[controls["control_id"] == "PC-IPV", "threshold_value"] = 0.90
    controls.loc[controls["control_id"] == "PC-IPV", "threshold_direction"] = "min"
    obs = pd.DataFrame([
        {"desk": "금리", "control_id": "PC-IPV", "verdict": None,
         "metric_value": 0.95, "evidence_ref": "ipv/run"},
        {"desk": "외환", "control_id": "PC-IPV", "verdict": None,
         "metric_value": 0.80, "evidence_ref": "ipv/run"}])
    out = pc.evaluate_pricing_controls(controls, obs, asof=ASOF,
                                       desks=["금리", "외환"])
    hit = out.set_index(["desk", "control_id"])["status"]
    assert hit[("금리", "PC-IPV")] == "유효"
    assert hit[("외환", "PC-IPV")] == "미흡"


def test_gap_ledger_carries_every_non_effective_result(pricing_tables):
    results = pricing_tables["gov_pricing_result"]
    gaps = pricing_tables["gov_pricing_gap"]
    assert len(gaps) == int((results["status"] != "유효").sum())
    assert set(gaps["severity"]) <= set(pc.GAP_SEVERITIES)


def test_ipv_adapter_uses_notional_coverage():
    """건수 커버리지만 보면 대형 포지션 누락이 묻힌다."""
    class _Stub:
        coverage = 0.99
        coverage_by_notional = 0.42
    obs = pc.observation_from_ipv(_Stub(), desk="금리", evidence_ref="e")
    assert obs["metric_value"] == pytest.approx(0.42)


# ----- BNK-ST-001 리스크 인벤토리 ---------------------------------------------

def _obs(risk_id, exposure, loss, kri) -> dict:
    return {"risk_id": risk_id, "exposure_share": exposure,
            "loss_share": loss, "kri_breach_share": kri}


@pytest.fixture(scope="module")
def inventory_tables():
    obs = [_obs("R-CRD", 0.62, 0.55, 0.30), _obs("R-MKT", 0.11, 0.08, 0.05),
           _obs("R-OPR", 0.04, 0.20, 0.35), _obs("R-IRB", 0.02, 0.01, 0.05)]
    return ri.build_risk_inventory(
        obs, {"R-CRD": 4.0e12, "R-MKT": 6.0e11, "R-OPR": 5.0e11},
        asof=ASOF)


def test_inventory_ledgers_match_their_specs(inventory_tables):
    specs = _specs(ri)
    for name, frame in inventory_tables.items():
        assert not validate(frame, specs[name]), f"{name} 스펙 위반"
    assert not check_refs(inventory_tables, specs)


def test_taxonomy_keeps_risks_that_carry_no_capital():
    """자본을 부과하지 않기로 한 유형도 목록에 남아야 한다."""
    tax = ri.build_risk_taxonomy()
    assert (tax["capital_pillar"] == "자본 미부과").any()
    assert set(tax["risk_id"]) >= {"R-LIQ", "R-REP", "R-CLM", "R-AIG"}


def test_materiality_needs_two_axes_over_threshold(inventory_tables):
    mat = inventory_tables["icaap_materiality"].set_index("risk_id")
    assert mat.loc["R-CRD", "grade"] == "중요"       # 세 축 전부 초과
    assert mat.loc["R-MKT", "grade"] == "보통"       # 노출만 초과
    assert mat.loc["R-IRB", "grade"] == "낮음"       # 초과 없음


def test_two_of_three_axes_is_material():
    tax = ri.build_risk_taxonomy()
    policy = ri.build_materiality_policy()
    obs = pd.DataFrame([_obs("R-OPR", 0.04, 0.20, 0.35)])
    out = ri.assess_materiality(tax, policy, obs, asof=ASOF)
    assert out.set_index("risk_id").loc["R-OPR", "grade"] == "중요"


def test_missing_axis_is_undecidable_not_immaterial():
    """관측 없는 축을 0으로 읽으면 측정 안 한 리스크가 전부 낮음이 된다."""
    tax = ri.build_risk_taxonomy()
    policy = ri.build_materiality_policy()
    obs = pd.DataFrame([_obs("R-STR", 0.30, None, 0.40)])
    out = ri.assess_materiality(tax, policy, obs, asof=ASOF)
    row = out.set_index("risk_id").loc["R-STR"]
    assert row["grade"] == "판정불가"
    assert "손실비중" in row["reason"]


def test_risk_with_no_observation_at_all_is_undecidable(inventory_tables):
    mat = inventory_tables["icaap_materiality"].set_index("risk_id")
    assert mat.loc["R-CLM", "grade"] == "판정불가"


def test_material_risk_without_economic_capital_stays_provisional():
    """통제 실패 시 결과는 확정이 아니라 잠정으로 남아야 한다."""
    tables = ri.build_risk_inventory(
        [_obs("R-CLM", 0.30, 0.25, 0.40)], {}, asof=ASOF)
    row = tables["icaap_capital_map"].set_index("risk_id").loc["R-CLM"]
    assert row["status"] == "잠정"
    assert "경제자본 미산출" in row["issue"]


def test_unmeasured_capital_stays_null_not_zero(inventory_tables):
    cap = inventory_tables["icaap_capital_map"].set_index("risk_id")
    assert pd.isna(cap.loc["R-STR", "ec_amount"])
    assert cap.loc["R-CRD", "ec_amount"] > 0


def test_capital_shares_sum_to_one_over_measured_risks(inventory_tables):
    cap = inventory_tables["icaap_capital_map"]
    assert cap["ec_share"].sum() == pytest.approx(1.0)


def test_materiality_policy_is_marked_as_internal_not_regulatory():
    policy = ri.build_materiality_policy()
    assert (policy["evidence_status"] == "미확인").all()
    assert policy["basis"].str.contains("내부 운영값").all()


def test_material_grade_rule_comes_from_the_policy_ledger():
    """판정 규칙을 원장에서 바꾸면 판정도 바뀐다. 엔진 본문에 숫자가 없다."""
    tax = ri.build_risk_taxonomy()
    obs = pd.DataFrame([_obs("R-MKT", 0.11, 0.08, 0.05)])   # 초과 1개
    policy = ri.build_materiality_policy()
    assert ri.assess_materiality(tax, policy, obs, asof=ASOF
                                 ).set_index("risk_id").loc["R-MKT", "grade"] == "보통"
    strict = policy.copy()
    strict["min_axes_for_material"] = 1
    assert ri.assess_materiality(tax, strict, obs, asof=ASOF
                                 ).set_index("risk_id").loc["R-MKT", "grade"] == "중요"


def test_inconsistent_grade_rule_is_refused():
    tax = ri.build_risk_taxonomy()
    policy = ri.build_materiality_policy()
    policy.loc[0, "min_axes_for_material"] = 3
    with pytest.raises(ValueError, match="축마다 다르다"):
        ri.assess_materiality(tax, policy,
                              pd.DataFrame([_obs("R-CRD", .1, .1, .1)]), asof=ASOF)


def test_missing_policy_axis_raises_rather_than_defaulting():
    tax = ri.build_risk_taxonomy()
    policy = ri.build_materiality_policy()
    policy = policy[policy["axis"] != "KRI위반"]
    with pytest.raises(ValueError, match="판정 축"):
        ri.assess_materiality(tax, policy, pd.DataFrame([_obs("R-CRD", .1, .1, .1)]),
                              asof=ASOF)


def test_inventory_is_deterministic():
    obs = [_obs("R-CRD", 0.62, 0.55, 0.30)]
    a = ri.build_risk_inventory(obs, {"R-CRD": 1.0e12}, asof=ASOF)
    b = ri.build_risk_inventory(obs, {"R-CRD": 1.0e12}, asof=ASOF)
    for name in a:
        pd.testing.assert_frame_equal(a[name], b[name])


# ----- INT-001 조회 전용 커넥터 -----------------------------------------------

@pytest.fixture(scope="module")
def connector_tables():
    return connector.build_connector_control()


def test_connector_ledgers_match_their_specs(connector_tables):
    specs = _specs(connector)
    for name, frame in connector_tables.items():
        assert not validate(frame, specs[name]), f"{name} 스펙 위반"
    assert not check_refs(connector_tables, specs)


def test_every_registered_connector_is_read_only(connector_tables):
    assert (connector_tables["int_connector"]["access_mode"] == "조회전용").all()
    assert (connector_tables["int_connector_operation"]["verb"] == "read").all()
    assert connector_tables["int_connector_violation"].empty


def test_connection_status_says_unconnected(connector_tables):
    """연결하지 않았다는 사실을 원장이 말해야 합성 데이터가 원천으로 안 읽힌다."""
    conns = connector_tables["int_connector"]
    assert (conns["connection_status"] == "미연결").all()
    assert conns["fallback"].str.strip().ne("").all()


def test_write_verb_on_read_only_connector_is_a_violation():
    conns = connector.build_connectors()
    ops = connector.build_connector_operations()
    ops = pd.concat([ops, pd.DataFrame([{
        "connector_id": "CN-COR", "operation": "update_balance",
        "verb": "write", "target_object": "여수신 계좌",
        "purpose": "조정 반영"}])], ignore_index=True)
    out = connector.check_read_only(conns, ops)
    assert len(out) == 1
    assert out.iloc[0]["violation_kind"] == "조회전용 위반"


def test_operation_on_unregistered_connector_is_a_violation():
    conns = connector.build_connectors()
    ops = pd.DataFrame([{"connector_id": "CN-XXX", "operation": "read_all",
                         "verb": "read", "target_object": "미상",
                         "purpose": "미상"}])
    out = connector.check_read_only(conns, ops)
    assert out.iloc[0]["violation_kind"] == "미등록 커넥터"


def test_write_capable_connector_needs_explicit_approval():
    """승인 목록이 비어 있는 상태가 통과로 읽히면 안 된다."""
    conns = connector.build_connectors()
    conns.loc[conns["connector_id"] == "CN-FIN", "access_mode"] = "쓰기포함"
    ops = connector.build_connector_operations()
    assert (connector.check_read_only(conns, ops)["violation_kind"]
            == "접근모드 미승인").any()
    assert connector.check_read_only(conns, ops,
                                     approved_write=("CN-FIN",)).empty


# ----- INT-002 수신 표준화 ----------------------------------------------------

def _gl(asof: str = ASOF) -> pd.DataFrame:
    return pd.DataFrame({"account_code": ["1010", "2010"],
                         "balance": [1.0e9, 2.0e9], "asof": [asof, asof]})


def test_inbound_ledgers_match_their_specs():
    tables = inbound.build_inbound({"FD-GL": _gl()}, asof=ASOF,
                                   received_on="2026-07-01")
    specs = _specs(inbound, connector)
    for name, frame in tables.items():
        assert not validate(frame, specs[name]), f"{name} 스펙 위반"


def test_conforming_payload_is_accepted():
    contracts = inbound.build_inbound_contracts()
    out = inbound.verify_delivery(contracts, "FD-GL", _gl(), asof=ASOF)
    assert out["status"] == "정상"
    assert out["n_rows"] == 2


def test_missing_required_column_is_a_schema_break():
    contracts = inbound.build_inbound_contracts()
    payload = _gl().drop(columns=["balance"])
    out = inbound.verify_delivery(contracts, "FD-GL", payload, asof=ASOF)
    assert out["status"] == "스키마불일치"
    assert "balance" in out["detail"]


def test_wrong_asof_is_reported_separately_from_schema():
    contracts = inbound.build_inbound_contracts()
    out = inbound.verify_delivery(contracts, "FD-GL", _gl("2026-03-31"),
                                  asof=ASOF)
    assert out["status"] == "기준일불일치"


def test_empty_payload_is_distinguished_from_no_payload():
    """'안 왔다'와 '왔는데 비었다'는 다른 사건이다."""
    contracts = inbound.build_inbound_contracts()
    empty = _gl().iloc[0:0]
    assert inbound.verify_delivery(contracts, "FD-GL", empty,
                                   asof=ASOF)["status"] == "행수0"
    assert inbound.verify_delivery(contracts, "FD-GL", None,
                                   asof=ASOF)["status"] == "미수신"


def test_feed_without_a_contract_is_not_passed_through():
    contracts = inbound.build_inbound_contracts()
    out = inbound.verify_delivery(contracts, "FD-UNKNOWN", _gl(), asof=ASOF)
    assert out["status"] == "계약없음"


def test_feed_without_asof_column_skips_the_asof_check():
    contracts = inbound.build_inbound_contracts()
    payload = pd.DataFrame({"document_id": ["d1"], "clause": ["<표5>"],
                            "text": ["통화별 금리충격 규모"]})
    out = inbound.verify_delivery(contracts, "FD-DOC", payload, asof=ASOF)
    assert out["status"] == "정상"


def test_checksum_ignores_column_order_but_not_content():
    payload = _gl()
    reordered = payload[["asof", "balance", "account_code"]]
    assert (inbound.payload_checksum(payload)
            == inbound.payload_checksum(reordered))
    changed = payload.copy()
    changed.loc[0, "balance"] = 9.9e9
    assert (inbound.payload_checksum(payload)
            != inbound.payload_checksum(changed))


def test_checksum_is_stable_across_calls():
    """파이썬 내장 hash()는 솔트되므로 쓰지 않았다는 것을 값으로 확인한다."""
    payload = _gl()
    assert inbound.payload_checksum(payload) == inbound.payload_checksum(payload)
    assert len(inbound.payload_checksum(payload)) == 64


def test_unlisted_payload_is_still_recorded():
    contracts = inbound.build_inbound_contracts()
    out = inbound.build_inbound_deliveries(
        contracts, {"FD-GL": _gl(), "FD-GHOST": _gl()}, asof=ASOF)
    ghost = out[out["feed_id"] == "FD-GHOST"].iloc[0]
    assert ghost["status"] == "계약없음"


# ----- INT-003 계산엔진 어댑터 ------------------------------------------------

@pytest.fixture(scope="module")
def engine_tables():
    return engine_adapter.build_engine_adapter()


def test_engine_ledgers_match_their_specs(engine_tables):
    specs = _specs(engine_adapter)
    for name, frame in engine_tables.items():
        assert not validate(frame, specs[name]), f"{name} 스펙 위반"
    assert not check_refs(engine_tables, specs)


def test_engine_version_is_null_until_a_module_declares_one(engine_tables):
    """판본을 지어내지 않는다. 비어 있음이 화면에 드러나야 한다."""
    assert engine_tables["int_engine_adapter"]["engine_version"].isna().all()


def test_every_engine_declares_at_least_one_input_and_output(engine_tables):
    io = engine_tables["int_engine_io"]
    for engine_id in engine_tables["int_engine_adapter"]["engine_id"]:
        decl = io[io["engine_id"] == engine_id]
        assert (decl["direction"] == "입력").any(), engine_id
        assert (decl["direction"] == "출력").any(), engine_id


def test_missing_required_input_makes_the_engine_unrunnable(engine_tables):
    out = engine_adapter.check_engine_io(
        engine_tables["int_engine_adapter"], engine_tables["int_engine_io"],
        ["exposure", "rwa_detail"]).set_index("engine_id")
    assert out.loc["EN-RWA", "status"] == "실행불가"
    assert "counterparty" in out.loc["EN-RWA", "detail"]


def test_declared_output_that_never_appears_is_reported(engine_tables):
    out = engine_adapter.check_engine_io(
        engine_tables["int_engine_adapter"], engine_tables["int_engine_io"],
        ["exposure", "counterparty"]).set_index("engine_id")
    assert out.loc["EN-RWA", "status"] == "출력누락"
    assert out.loc["EN-RWA", "n_missing_output"] == 1


def test_engine_is_runnable_when_all_declared_tables_exist(engine_tables):
    io = engine_tables["int_engine_io"]
    every = sorted(set(io["table_name"]))
    out = engine_adapter.check_engine_io(
        engine_tables["int_engine_adapter"], io, every)
    assert (out["status"] == "실행가능").all()


# ----- INT-008 멱등성·재시도·격리 ---------------------------------------------

def _delivery(**over) -> dict:
    base = dict(feed_id="FD-GL", asof=ASOF, batch_seq=1, channel_kind="파일",
                content_fingerprint="fp-a", ok=True, reason="수신 성공")
    base.update(over)
    return base


def test_resilience_ledgers_match_their_specs():
    tables = resilience.build_resilience([_delivery()])
    specs = _specs(resilience)
    for name, frame in tables.items():
        assert not validate(frame, specs[name]), f"{name} 스펙 위반"


def test_idempotency_key_is_stable_and_content_sensitive():
    a = resilience.idempotency_key("FD-GL", ASOF, 1, "fp-a")
    assert a == resilience.idempotency_key("FD-GL", ASOF, 1, "fp-a")
    assert a != resilience.idempotency_key("FD-GL", ASOF, 1, "fp-b")
    assert a != resilience.idempotency_key("FD-GL", ASOF, 2, "fp-a")
    assert a != resilience.idempotency_key("FD-EXP", ASOF, 1, "fp-a")


def test_same_payload_twice_is_blocked_not_loaded_twice():
    tables = resilience.build_resilience([_delivery(), _delivery()])
    outcomes = tables["int_delivery_attempt"]["outcome"].tolist()
    assert outcomes == ["성공", "중복차단"]


def test_corrected_file_with_the_same_batch_number_is_not_blocked():
    """같은 회차 번호로 내용이 바뀐 파일은 교체이지 중복이 아니다."""
    tables = resilience.build_resilience(
        [_delivery(), _delivery(content_fingerprint="fp-b")])
    assert tables["int_delivery_attempt"]["outcome"].tolist() == ["성공", "성공"]


def test_retries_use_exponential_backoff_without_a_clock():
    policy = resilience.build_retry_policy().set_index("channel_kind")
    row = policy.loc["파일"]
    assert resilience.wait_seconds(row, 1) == pytest.approx(300.0)
    assert resilience.wait_seconds(row, 2) == pytest.approx(600.0)
    fixed = policy.loc["DB batch"]
    assert resilience.wait_seconds(fixed, 3) == pytest.approx(600.0)


def test_attempts_beyond_the_policy_limit_are_quarantined():
    fails = [_delivery(ok=False, reason="타임아웃")] * 3
    tables = resilience.build_resilience(fails)
    attempts = tables["int_delivery_attempt"]
    assert attempts["outcome"].tolist() == ["실패", "실패", "격리"]
    quarantine = tables["int_quarantine"]
    assert len(quarantine) == 1
    assert quarantine.iloc[0]["n_attempts"] == 3
    assert not bool(quarantine.iloc[0]["released"])


def test_repeated_quarantine_of_one_key_stays_one_row():
    """격리 원장의 입도는 수신분 1건이다. 같은 키가 두 행이면 기본키가 깨진다."""
    tables = resilience.build_resilience(
        [_delivery(ok=False, reason="타임아웃")] * 5)
    quarantine = tables["int_quarantine"]
    assert len(quarantine) == 1
    specs = _specs(resilience)
    assert not validate(quarantine, specs["int_quarantine"])


def test_quarantine_names_a_role_to_notify():
    """격리 사실을 통지하지 않으면 데이터가 조용히 빠진 채 산출이 끝난다."""
    tables = resilience.build_resilience(
        [_delivery(ok=False, reason="체크섬 불일치")] * 3)
    assert tables["int_quarantine"].iloc[0]["notified_role"].strip()


def test_unknown_channel_is_quarantined_immediately():
    tables = resilience.build_resilience(
        [_delivery(ok=False, channel_kind="메시지큐", reason="연결 거부")])
    attempt = tables["int_delivery_attempt"].iloc[0]
    assert attempt["outcome"] == "격리"
    assert "정책에 연계 유형" in attempt["reason"]


def test_previously_seen_keys_are_honoured_across_runs():
    key = resilience.idempotency_key("FD-GL", ASOF, 1, "fp-a")
    tables = resilience.build_resilience([_delivery()], seen_keys={key})
    assert tables["int_delivery_attempt"].iloc[0]["outcome"] == "중복차단"


def test_resilience_is_deterministic():
    fails = [_delivery(ok=False, reason="타임아웃")] * 3
    a = resilience.build_resilience(fails)
    b = resilience.build_resilience(fails)
    for name in a:
        pd.testing.assert_frame_equal(a[name], b[name])
