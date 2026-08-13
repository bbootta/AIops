"""거버넌스 통제 원장 (NFR-003 · NFR-004 · PLT-002 · PLT-014 · GOV-004 · DAT-008).

검사 원칙은 셋이다.

1. 통제는 **실패할 수 있어야** 통제다. 위반 사례를 만들어 판정이 실제로
   발동하는지 본다.
2. 근거 없는 값은 판정하지 않는다. 정책값이 NULL이면 '판정불가'가 나와야 하고
   기본값으로 메워지면 안 된다.
3. 같은 입력은 같은 출력을 낸다.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from risk_lib.datamodel.spec import TableSpec, check_refs, validate
from risk_lib.model_inventory import build_standard_inventory
from risk_lib.governance import (
    audit_chain as ac, model_lifecycle as ml, rbac, retention, unified_run as ur,
)

ASOF = "2026-06-11"

_MODULES = (rbac, ac, retention, ur, ml)


def _specs(module) -> dict[str, TableSpec]:
    return {s.name: s for s in module.SPECS}


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


# ----- NFR-003 RBAC -----------------------------------------------------------

@pytest.fixture(scope="module")
def rbac_tables():
    return rbac.build_rbac(asof=ASOF)


def test_rbac_ledgers_match_their_specs(rbac_tables):
    specs = _specs(rbac)
    for name, frame in rbac_tables.items():
        assert not validate(frame, specs[name]), f"{name} 스펙 위반"
    assert not check_refs(rbac_tables, specs)


def test_access_is_denied_when_no_permission_row_exists(rbac_tables):
    """권한 행이 없으면 거부한다. fail-closed가 아니면 통제가 아니다."""
    decision, role, reason = rbac.decide_access(
        rbac_tables["gov_role_permission"], rbac_tables["gov_user_role"],
        user_id="U-002", resource_kind="page", resource_id="없는화면.html",
        action="read", asof=ASOF)
    assert decision == "거부"
    assert role == ""
    assert "권한 행이 없다" in reason


def test_explicit_denial_beats_a_grant_from_another_role(rbac_tables):
    """겸직으로 명시적 거부를 우회하지 못한다."""
    perms = pd.concat([
        rbac_tables["gov_role_permission"],
        pd.DataFrame([{"role_id": "R-CRD", "resource_kind": "function",
                       "resource_id": "신용 산출 실행", "action": "write",
                       "granted": True, "citation": "시험용 부여"}]),
    ], ignore_index=True)
    users = pd.concat([
        rbac_tables["gov_user_role"],
        pd.DataFrame([{"user_id": "U-004", "user_name": "적합성검증팀 담당",
                       "role_id": "R-CRD", "valid_from": "2025-01-01",
                       "valid_to": "2027-12-31", "granted_by": "시험"}]),
    ], ignore_index=True)
    decision, _role, reason = rbac.decide_access(
        perms, users, user_id="U-004", resource_kind="function",
        resource_id="신용 산출 실행", action="write", asof=ASOF)
    assert decision == "거부"
    assert "명시적 거부" in reason


def test_expired_assignment_loses_access(rbac_tables):
    users = rbac_tables["gov_user_role"]
    assert rbac.active_roles(users, "U-005", ASOF) == []
    assert rbac.active_roles(users, "U-005", "2024-01-01") == ["R-DAT"]


def test_sod_violation_is_found_and_expired_pairs_are_not(rbac_tables):
    v = rbac.sod_violations(rbac_tables["gov_user_role"],
                            rbac_tables["gov_sod_conflict"], asof=ASOF)
    assert set(v["user_id"]) == {"U-006"}
    assert v.iloc[0]["conflict_id"] == "SOD-03"
    # 배정이 살아 있지 않은 기준일에는 상충도 없다.
    assert rbac.sod_violations(rbac_tables["gov_user_role"],
                               rbac_tables["gov_sod_conflict"],
                               asof="2020-01-01").empty


def test_page_permissions_track_the_page_registry():
    """화면 권한은 레지스트리에서 유도된다. 손으로 복사한 목록이 아니다."""
    from risk_lib.page_registry import PageSpec
    fake = (PageSpec("99_new.html", "새 화면",
                     "risk_lib.ops_pages.core_credit", "_page_pd"),)
    perms = rbac.build_role_permissions(fake)
    pages = perms[perms["resource_kind"] == "page"]
    assert set(pages["resource_id"]) == {"99_new.html"}
    assert "R-CRD" in set(pages["role_id"])


# ----- NFR-004 감사기록 불변성 -------------------------------------------------

@pytest.fixture(scope="module")
def chain(rbac_tables):
    frame, _skipped = ac.build_audit_chain(rbac_tables, asof=ASOF)
    return frame


def test_chain_matches_spec_and_verifies(chain):
    assert not validate(chain, ac.AUDIT_CHAIN)
    assert ac.verify_chain(chain) == []
    assert len(chain) > 0


def test_editing_any_field_breaks_the_chain(chain):
    """행 하나를 고치면 그 행의 해시가 어긋난다."""
    tampered = chain.copy()
    tampered.loc[0, "actor"] = "다른 사람"
    problems = ac.verify_chain(tampered)
    assert any("기록 해시 불일치" in p for p in problems)


def test_deleting_a_record_breaks_the_links(chain):
    """중간 기록을 지우면 연결과 일련번호가 함께 깨진다."""
    if len(chain) < 3:
        pytest.skip("체인이 짧아 삭제 시험을 할 수 없다")
    tampered = chain.drop(index=1).reset_index(drop=True)
    problems = ac.verify_chain(tampered)
    assert any("일련번호 불연속" in p for p in problems)
    assert any("prev_hash 불일치" in p for p in problems)


def test_chain_is_deterministic_across_builds(rbac_tables):
    a, _ = ac.build_audit_chain(rbac_tables, asof=ASOF)
    b, _ = ac.build_audit_chain(rbac_tables, asof=ASOF)
    assert ac.chain_head(a) == ac.chain_head(b)


def test_missing_source_ledgers_are_reported_not_hidden():
    _frame, skipped = ac.build_audit_chain({}, asof=ASOF)
    assert skipped, "원장이 하나도 없는데 건너뛴 사유가 비어 있다"


def test_engine_written_ledgers_get_a_default_actor_and_a_note():
    """사람이 없는 기록도 행위자를 비우지 않고, 대체했다는 사실을 남긴다."""
    tables = {"val_check": pd.DataFrame({"asof": [ASOF], "check_name": ["c1"],
                                         "status": ["PASS"]})}
    frame, notes = ac.build_audit_chain(tables, asof=ASOF)
    assert frame.iloc[0]["actor"] == "자체검증 엔진"
    assert ac.verify_chain(frame) == []
    assert notes


def test_missing_date_column_falls_back_to_asof_with_a_note():
    tables = {"gov_approval": pd.DataFrame({"approval_id": ["A1"],
                                            "approver": ["CRO"]})}
    frame, notes = ac.build_audit_chain(tables, asof=ASOF)
    assert frame.iloc[0]["occurred_asof"] == ASOF
    assert not any("기준일 컬럼" in n for n in notes)   # 이 원장은 기준일 컬럼을 선언하지 않는다


def test_unknown_event_type_is_rejected():
    with pytest.raises(ac.AuditChainError):
        ac.AuditChain().append(record_id="x", event_type="없는유형", actor="a",
                               occurred_asof=ASOF, source_ledger="t", payload={})


# ----- PLT-002 · DAT-008 적재와 보존 -------------------------------------------

@pytest.fixture(scope="module")
def retention_tables(rbac_tables):
    tables, skipped = retention.build_retention(
        rbac_tables, run_id="RUN-TEST", asof=ASOF, versions=[])
    return tables, skipped


def test_retention_ledgers_match_their_specs(retention_tables):
    tables, _ = retention_tables
    specs = _specs(retention)
    for name, frame in tables.items():
        assert not validate(frame, specs[name]), f"{name} 스펙 위반"


def test_every_loaded_table_is_recorded_including_empty_ones(rbac_tables):
    tables = dict(rbac_tables)
    tables["빈원장"] = pd.DataFrame(columns=["a"])
    loads = retention.build_mart_load(tables, run_id="RUN-TEST", asof=ASOF)
    assert len(loads) == len(tables)
    assert loads[loads["table_name"] == "빈원장"].iloc[0]["status"] == "행수0"


def test_disposal_is_not_decided_without_a_confirmed_retention_period():
    """법정 보존기간이 NULL이면 세대수를 넘겨도 폐기대상으로 판정하지 않는다."""
    policy = retention.build_retention_policy()
    assert policy["min_retention_years"].isna().all()
    artifacts = [(f"판-{i}", "산출물 판", f"20{10 + i}-01-01") for i in range(12)]
    actions, skipped = retention.plan_disposal(policy, artifacts,
                                               ref_date="2026-06-11")
    assert set(actions["decision"]) == {"판정불가"}
    assert len(skipped) == len(artifacts)


def test_disposal_decides_once_the_period_is_filled_in():
    """보존기간이 채워지면 같은 엔진이 폐기대상을 낸다. 판정 로직 자체는 살아 있다."""
    policy = retention.build_retention_policy()
    policy.loc[policy["data_class"] == "산출물 판", "min_retention_years"] = 5.0
    artifacts = [(f"판-{i}", "산출물 판", f"20{10 + i}-01-01") for i in range(12)]
    actions, _ = retention.plan_disposal(policy, artifacts, ref_date="2026-06-11")
    assert "폐기대상" in set(actions["decision"])
    assert "보관" in set(actions["decision"])


def test_observation_period_raises_the_disposal_floor():
    """법정 보존기간이 짧아도 규정상 최소 관측기간을 못 채우면 폐기하지 않는다."""
    policy = retention.build_retention_policy()
    policy.loc[policy["data_class"] == "정규 원장", "min_retention_years"] = 3.0
    obs = float(policy.loc[policy["data_class"] == "정규 원장",
                           "min_observation_years"].iloc[0])
    assert obs == 7.0
    artifacts = [(f"판-{i}", "정규 원장", f"20{16 + i}-01-01") for i in range(8)]
    actions, _ = retention.plan_disposal(policy, artifacts, ref_date="2026-06-11")
    for _, r in actions.iterrows():
        if r["decision"] == "폐기대상":
            assert r["age_years"] > obs


def test_future_dated_artifact_is_not_judged():
    policy = retention.build_retention_policy()
    actions, _ = retention.plan_disposal(
        policy, [("미래판", "산출물 판", "2030-01-01")], ref_date=ASOF)
    assert actions.iloc[0]["decision"] == "판정불가"
    assert actions.iloc[0]["age_years"] == 0.0


# ----- PLT-014 통합 런 ---------------------------------------------------------

def test_unified_run_flags_missing_domains(rbac_tables):
    tables, problems = ur.build_unified_run(
        rbac_tables, run_id="RUN-TEST", asof=ASOF, seed=42, code_revision="rev")
    assert not validate(tables["gov_unified_run"], ur.UNIFIED_RUN)
    assert not validate(tables["gov_run_domain"], ur.RUN_DOMAIN)
    assert not bool(tables["gov_unified_run"].iloc[0]["is_complete"])
    assert any("도메인 미산출" in p for p in problems)


def test_unified_run_detects_a_foreign_run_id():
    tables = {"rdm_x": pd.DataFrame({"run_id": ["RUN-A", "RUN-B"]})}
    _t, problems = ur.build_unified_run(tables, run_id="RUN-A", asof=ASOF,
                                        seed=42, code_revision="rev")
    assert any("다른 run_id 혼입" in p for p in problems)


def test_run_fingerprint_changes_with_content():
    a, _ = ur.build_unified_run({"rdm_x": pd.DataFrame({"v": [1]})},
                                run_id="R", asof=ASOF, seed=42, code_revision="r")
    b, _ = ur.build_unified_run({"rdm_x": pd.DataFrame({"v": [1, 2]})},
                                run_id="R", asof=ASOF, seed=42, code_revision="r")
    assert (a["gov_unified_run"].iloc[0]["run_fingerprint"]
            != b["gov_unified_run"].iloc[0]["run_fingerprint"])


# ----- GOV-004 모형 승인 생애주기 ----------------------------------------------

@pytest.fixture(scope="module")
def lifecycle():
    return ml.build_model_lifecycle(asof=ASOF)


def test_lifecycle_ledgers_match_their_specs(lifecycle):
    tables, _ = lifecycle
    specs = _specs(ml)
    for name, frame in tables.items():
        assert not validate(frame, specs[name]), f"{name} 스펙 위반"
    assert not check_refs(tables, specs)


def test_skipping_a_stage_is_rejected():
    with pytest.raises(ml.LifecycleError):
        ml.register_transition([], model_id="M", from_stage="개발",
                               to_stage="운영", decided_on=ASOF,
                               decided_by="누구", evidence_ref=None,
                               record_source="수기등록")


def test_production_models_without_approval_evidence_are_flagged(lifecycle):
    tables, breaches = lifecycle
    state = tables["gov_model_state"]
    assert (state["control_status"] != "적합").any()
    assert breaches
    # 승인 전이가 아예 없으면 판정이 '승인없이운영'이어야 한다.
    inv = build_standard_inventory(today=date.fromisoformat(ASOF))
    no_transitions = pd.DataFrame(
        columns=[c.name for c in ml.MODEL_TRANSITION.columns])
    judged = ml.judge(inv, no_transitions, asof=ASOF)
    prod = judged[judged["current_stage"] == "운영"]
    assert (prod["control_status"] == "승인없이운영").all()


# ----- 예외 조치 큐 (RDM-007) --------------------------------------------------

def test_a_dq_failure_reaches_the_exception_queue():
    """DQ 위반이 예외 큐에 올라야 한다.

    필터가 severity=='error' 로 걸려 있었는데 스펙 허용값은 FAIL·WARN 이라,
    어떤 DQ 위반도 큐에 오른 적이 없었다. 통과 이력(PASS)은 예외가 아니므로
    같이 올라오면 안 된다.
    """
    import pandas as pd
    from risk_lib.ui_studio.governance import build_exception_actions

    dq = pd.DataFrame([
        {"asof": "2026-06-30", "table_name": "rdm_exposure",
         "column_name": "ead", "rule": "range_min", "severity": "FAIL",
         "n_rows": 3, "detail": "최솟값 0.0 미만"},
        {"asof": "2026-06-30", "table_name": "rdm_exposure",
         "column_name": "ead", "rule": "range_max", "severity": "PASS",
         "n_rows": 0, "detail": "통과"},
    ])
    tables = {
        "rdm_dq_result": dq,
        "rdm_reconciliation": pd.DataFrame(
            columns=["recon_id", "status", "axis", "gap", "gap_ratio"]),
        "mkt_ipv": pd.DataFrame(
            columns=["trade_id", "is_break", "days_open"]),
    }
    q = build_exception_actions(tables)
    src = q[q["source_ledger"] == "rdm_dq_result"]
    assert len(src) == 1, "FAIL 하나만 올라와야 한다"
    assert "range_min" in src.iloc[0]["finding"]
