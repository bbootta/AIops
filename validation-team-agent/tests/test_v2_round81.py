"""Round 81 — 검증 트리거 평가 + 검증 사례 생성 (VAL-001/002/003)."""

from __future__ import annotations

import json
from datetime import date

import pytest

from tools.validation_trigger import (
    STATUS_BREACH,
    STATUS_NOT_EVALUATED,
    STATUS_OK,
    TRIGGERS_PATH,
    build_cases,
    emit_cases,
    evaluate,
    evaluate_trigger,
    load_cases,
    load_triggers,
    queue,
    render_evaluation,
    render_queue,
)

AS_OF = date(2026, 7, 25)


@pytest.fixture(scope="module")
def triggers():
    return load_triggers()


@pytest.fixture(scope="module")
def normal_demo(tmp_path_factory):
    from tools.run_workflow_demo import run_demo

    return run_demo(2_000, False, 42, tmp_path_factory.mktemp("logs"))


@pytest.fixture(scope="module")
def stress_demo(tmp_path_factory):
    from tools.run_workflow_demo import run_demo

    return run_demo(2_000, True, 42, tmp_path_factory.mktemp("logs"))


# ---------- 트리거 원장 ----------

def test_trigger_ledger_shape(triggers):
    assert triggers["triggers"]
    for t in triggers["triggers"]:
        assert t["trigger_id"].startswith("TRG-")
        assert t["direction"] in ("lower", "upper")
        assert t["severity"] in triggers["sla_days_by_severity"]
        assert t["evaluation_cycle"]
        assert t["owner_role"]
        assert t["threshold_ref"].strip()


def test_trigger_ids_unique(triggers):
    ids = [t["trigger_id"] for t in triggers["triggers"]]
    assert len(ids) == len(set(ids))


def test_thresholds_match_policy_ssot(triggers):
    """임계치를 임의로 만들지 않는다 — policy_key 가 있으면 정책 파일 값과 일치."""
    from tools.validation_trigger import ROOT

    checked = 0
    for t in triggers["triggers"]:
        key = t.get("policy_key")
        if not key:
            continue
        fname, field = key.split(".", 1)
        policy = json.loads(
            (ROOT / "harness" / f"{fname}.json").read_text(encoding="utf-8"))
        assert float(policy[field]) == float(t["expected"]), (
            f"{t['trigger_id']}: expected={t['expected']} vs "
            f"{key}={policy[field]}")
        checked += 1
    assert checked >= 5, f"정책 대조된 트리거가 너무 적다 ({checked})"


def test_zero_tolerance_for_limit_triggers(triggers):
    """한도형(정책 최소·상한 인용) 트리거는 허용오차 0 — 기준 완화 금지."""
    for t in triggers["triggers"]:
        if t.get("policy_key"):
            assert float(t["tolerance"]) == 0.0, t["trigger_id"]


# ---------- 4요소 평가 ----------

def test_normal_mode_has_no_breach(normal_demo, triggers):
    ev = evaluate(normal_demo, triggers=triggers)
    assert ev["breaches"] == [], ev["breaches"]
    assert ev["not_evaluated"] == []
    assert ev["n_total"] == len(triggers["triggers"])


def test_stress_mode_detects_breaches(stress_demo, triggers):
    ev = evaluate(stress_demo, triggers=triggers)
    ids = {b["trigger_id"] for b in ev["breaches"]}
    # 스트레스 시나리오에서 반드시 잡혀야 하는 항목
    assert {"TRG-LIQ-LCR", "TRG-IRRBB-DELTAEVE",
            "TRG-MKT-VAR-EXCEPTIONS"} <= ids, ids


def test_four_element_structure_present(normal_demo, triggers):
    """Observed/Expected/Variance/Tolerance 4요소 — VAL-002 gap 해소 조건."""
    ev = evaluate(normal_demo, triggers=triggers)
    for r in ev["results"]:
        for k in ("observed", "expected", "variance", "tolerance"):
            assert k in r
        assert r["variance"] == pytest.approx(r["observed"] - r["expected"])


def test_variance_definition_matches_val_f001():
    """variance = observed - expected (수식랩 VAL-F001)."""
    t = {"trigger_id": "T", "domain": "d", "step_id": "s", "output_path": "v",
         "metric": "m", "expected": 1.0, "tolerance": 0.0, "direction": "lower",
         "severity": "high", "owner_role": "o", "evaluation_cycle": "q",
         "threshold_ref": "r"}
    demo = {"results": {"s": {"outputs": {"v": 0.75}, "status": "ok"}}}
    r = evaluate_trigger(t, demo)
    assert r["variance"] == pytest.approx(-0.25)
    assert r["status"] == STATUS_BREACH


def test_direction_upper_and_lower():
    base = {"trigger_id": "T", "domain": "d", "step_id": "s",
            "output_path": "v", "metric": "m", "tolerance": 0.10,
            "severity": "high", "owner_role": "o", "evaluation_cycle": "q",
            "threshold_ref": "r", "expected": 0.0}
    demo = {"results": {"s": {"outputs": {"v": 0.15}, "status": "ok"}}}
    assert evaluate_trigger({**base, "direction": "upper"},
                            demo)["status"] == STATUS_BREACH
    assert evaluate_trigger({**base, "direction": "lower"},
                            demo)["status"] == STATUS_OK


def test_tolerance_boundary_is_not_a_breach():
    """경계값(variance == tolerance)은 위반이 아니다."""
    t = {"trigger_id": "T", "domain": "d", "step_id": "s", "output_path": "v",
         "metric": "m", "expected": 0.0, "tolerance": 0.10,
         "direction": "upper", "severity": "high", "owner_role": "o",
         "evaluation_cycle": "q", "threshold_ref": "r"}
    demo = {"results": {"s": {"outputs": {"v": 0.10}, "status": "ok"}}}
    assert evaluate_trigger(t, demo)["status"] == STATUS_OK


def test_missing_metric_is_not_silently_passed():
    """미산출은 통과가 아니다 — not_evaluated 로 남아야 한다."""
    t = {"trigger_id": "T", "domain": "d", "step_id": "3.none",
         "output_path": "v", "metric": "m", "expected": 1.0, "tolerance": 0.0,
         "direction": "lower", "severity": "high", "owner_role": "o",
         "evaluation_cycle": "q", "threshold_ref": "r"}
    r = evaluate_trigger(t, {"results": {}})
    assert r["status"] == STATUS_NOT_EVALUATED
    assert r["observed"] is None
    assert "미산출" in r["detail"]


def test_boolean_output_is_not_treated_as_number():
    """bool 은 지표가 아니다 (outlier=False 를 0.0 으로 읽으면 오판)."""
    t = {"trigger_id": "T", "domain": "d", "step_id": "s", "output_path": "v",
         "metric": "m", "expected": 1.0, "tolerance": 0.0, "direction": "lower",
         "severity": "high", "owner_role": "o", "evaluation_cycle": "q",
         "threshold_ref": "r"}
    demo = {"results": {"s": {"outputs": {"v": False}, "status": "ok"}}}
    assert evaluate_trigger(t, demo)["status"] == STATUS_NOT_EVALUATED


def test_nested_output_path(normal_demo, triggers):
    """'lcr.ratio' 같은 중첩 경로가 읽힌다."""
    ev = evaluate(normal_demo, triggers=triggers)
    lcr = next(r for r in ev["results"] if r["trigger_id"] == "TRG-LIQ-LCR")
    assert lcr["observed"] == pytest.approx(1.3)


# ---------- 검증 사례 ----------

def test_cases_built_from_breaches(stress_demo, triggers):
    ev = evaluate(stress_demo, triggers=triggers)
    cases = build_cases(ev["breaches"], as_of=AS_OF,
                        sla_days=triggers["sla_days_by_severity"], existing=[])
    assert len(cases) == len(ev["breaches"])
    for c in cases:
        assert c["status"] == "open"
        assert c["case_id"].startswith("VC-20260725-")
        assert c["owner_role"] and c["severity"]
        assert c["opened_at"] == "2026-07-25"


def test_sla_due_date_by_severity(triggers):
    breaches = [
        {"trigger_id": "A", "domain": "d", "metric": "m", "observed": 0.5,
         "expected": 1.0, "variance": -0.5, "tolerance": 0.0,
         "severity": "critical", "owner_role": "o", "threshold_ref": "r"},
        {"trigger_id": "B", "domain": "d", "metric": "m", "observed": 0.5,
         "expected": 1.0, "variance": -0.5, "tolerance": 0.0,
         "severity": "medium", "owner_role": "o", "threshold_ref": "r"},
    ]
    cases = build_cases(breaches, as_of=AS_OF,
                        sla_days=triggers["sla_days_by_severity"], existing=[])
    by_id = {c["trigger_id"]: c for c in cases}
    assert by_id["A"]["due_at"] == "2026-07-30"   # critical 5일
    assert by_id["B"]["due_at"] == "2026-08-14"   # medium 20일


def test_case_ids_deterministic(stress_demo, triggers):
    ev = evaluate(stress_demo, triggers=triggers)
    kw = dict(as_of=AS_OF, sla_days=triggers["sla_days_by_severity"],
              existing=[])
    a = build_cases(ev["breaches"], **kw)
    b = build_cases(ev["breaches"], **kw)
    assert [c["case_id"] for c in a] == [c["case_id"] for c in b]


def test_case_ids_continue_after_existing(triggers):
    breach = {"trigger_id": "A", "domain": "d", "metric": "m", "observed": 0.5,
              "expected": 1.0, "variance": -0.5, "tolerance": 0.0,
              "severity": "high", "owner_role": "o", "threshold_ref": "r"}
    existing = [{"case_id": "VC-20260725-0001"}, {"case_id": "VC-20260725-0002"}]
    cases = build_cases([breach], as_of=AS_OF,
                        sla_days=triggers["sla_days_by_severity"],
                        existing=existing)
    assert cases[0]["case_id"] == "VC-20260725-0003"


def test_ledger_is_append_only(tmp_path, triggers):
    ledger = tmp_path / "cases.jsonl"
    breach = {"trigger_id": "A", "domain": "d", "metric": "m", "observed": 0.5,
              "expected": 1.0, "variance": -0.5, "tolerance": 0.0,
              "severity": "high", "owner_role": "o", "threshold_ref": "r"}
    kw = dict(as_of=AS_OF, sla_days=triggers["sla_days_by_severity"])
    emit_cases(build_cases([breach], existing=[], **kw), ledger)
    emit_cases(build_cases([breach], existing=load_cases(ledger), **kw), ledger)
    rows = load_cases(ledger)
    assert len(rows) == 2
    assert [r["case_id"] for r in rows] == ["VC-20260725-0001",
                                            "VC-20260725-0002"]


# ---------- 검토 큐 ----------

def test_queue_sorted_by_due_and_flags_overdue(stress_demo, triggers,
                                               tmp_path):
    ev = evaluate(stress_demo, triggers=triggers)
    ledger = tmp_path / "q.jsonl"
    emit_cases(build_cases(ev["breaches"], as_of=AS_OF,
                           sla_days=triggers["sla_days_by_severity"],
                           existing=[]), ledger)
    rows = queue(load_cases(ledger), as_of=AS_OF)
    assert [r["due_at"] for r in rows] == sorted(r["due_at"] for r in rows)
    assert all(not r["overdue"] for r in rows)
    later = queue(load_cases(ledger), as_of=date(2026, 8, 10))
    assert any(r["overdue"] for r in later)


def test_queue_filters(stress_demo, triggers, tmp_path):
    ev = evaluate(stress_demo, triggers=triggers)
    ledger = tmp_path / "q2.jsonl"
    emit_cases(build_cases(ev["breaches"], as_of=AS_OF,
                           sla_days=triggers["sla_days_by_severity"],
                           existing=[]), ledger)
    cases = load_cases(ledger)
    crit = queue(cases, severity="critical", as_of=AS_OF)
    assert crit and all(c["severity"] == "critical" for c in crit)
    alm = queue(cases, owner_role="alm_owner", as_of=AS_OF)
    assert alm and all(c["owner_role"] == "alm_owner" for c in alm)


def test_queue_excludes_non_open(triggers, tmp_path):
    ledger = tmp_path / "q3.jsonl"
    breach = {"trigger_id": "A", "domain": "d", "metric": "m", "observed": 0.5,
              "expected": 1.0, "variance": -0.5, "tolerance": 0.0,
              "severity": "high", "owner_role": "o", "threshold_ref": "r"}
    cases = build_cases([breach], as_of=AS_OF,
                        sla_days=triggers["sla_days_by_severity"], existing=[])
    cases[0]["status"] = "closed"
    emit_cases(cases, ledger)
    assert queue(load_cases(ledger), as_of=AS_OF) == []


# ---------- 보고 / CLI ----------

def test_render_shows_threshold_ref_on_breach(stress_demo, triggers):
    text = render_evaluation(evaluate(stress_demo, triggers=triggers))
    assert "[위반]" in text and "근거:" in text


def test_render_queue_empty():
    assert "없음" in render_queue([])


def test_cli_evaluate_exit_codes(tmp_path):
    from tools.validation_trigger import main

    assert main(["evaluate", "--n", "2000", "--seed", "42",
                 "--log-dir", str(tmp_path / "l1")]) == 0
    assert main(["evaluate", "--n", "2000", "--seed", "42", "--stress",
                 "--log-dir", str(tmp_path / "l2")]) == 1


def test_cli_triggers_lists_ledger(capsys):
    from tools.validation_trigger import main

    assert main(["triggers"]) == 0
    out = capsys.readouterr().out
    assert "TRG-LIQ-LCR" in out


def test_triggers_file_is_valid_json():
    json.loads(TRIGGERS_PATH.read_text(encoding="utf-8"))


def test_catalog_sync():
    from tools.cli_index import CLI_MODULES
    from vta.cli.__main__ import _DISPATCH

    assert "tools.validation_trigger" in {m for m, _ in CLI_MODULES}
    assert ("trigger",) in _DISPATCH
