"""Round 85 — Golden Case 회귀검증 + 비의도 변경 차단 (VAL-010/012)."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

import tools.independent_recalc as ir
from tools.golden_regression import (
    GOLDEN_PATH,
    KINDS,
    classify_changes,
    load_cases,
    render,
    run_all,
    run_case,
)


@pytest.fixture(scope="module")
def cases():
    return load_cases()


def _broken_lcr(bias: float):
    orig = ir.recalc_lcr
    return lambda inputs: orig(inputs) + bias


# ---------- Golden Case 집합 ----------

def test_all_cases_pass_on_current_code(cases):
    """현행 코드에서 전량 통과해야 기준선이 성립한다."""
    report = run_all(cases)
    fails = [r for r in report["results"] if r["status"] == "fail"]
    assert not fails, fails
    assert report["deploy_allowed"]


def test_all_four_kinds_present(cases):
    """VAL-010 은 회귀·경계값·민감도·금지행위를 모두 요구한다."""
    kinds = {c["kind"] for c in cases["cases"]}
    assert kinds == set(KINDS)


def test_case_ids_unique_and_have_rationale(cases):
    ids = [c["case_id"] for c in cases["cases"]]
    assert len(ids) == len(set(ids))
    for c in cases["cases"]:
        assert c["rationale"].strip(), c["case_id"]


def test_prohibited_and_boundary_are_all_critical(cases):
    """통제의 마지막 방어선은 전부 차단 대상이어야 한다."""
    for c in cases["cases"]:
        if c["kind"] in ("prohibited", "boundary"):
            assert c["critical"] is True, c["case_id"]


def test_every_target_is_registered(cases):
    for c in cases["cases"]:
        assert c["target"] in ir.RECALCULATORS, c["case_id"]


def test_golden_file_is_valid_json():
    json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


# ---------- 회귀 탐지 (핵심) ----------

def test_detects_injected_regression(cases):
    """계산기에 편향을 주입하면 반드시 잡혀야 한다."""
    with patch.dict(ir.RECALCULATORS, {"lcr": (_broken_lcr(0.01), "x", "y")}):
        report = run_all(cases)
    failed = {r["case_id"] for r in report["results"] if r["status"] == "fail"}
    assert {"GC-001", "GC-007"} <= failed
    assert not report["deploy_allowed"]


def test_detects_disabled_prohibition(cases):
    """금지행위 통제를 없애면(분모 0 을 0.0 으로 반환) 잡혀야 한다."""
    def lax(inputs):
        d = inputs["net_outflow"]
        return inputs["hqla"] / d if d else 0.0

    with patch.dict(ir.RECALCULATORS, {"lcr": (lax, "x", "y")}):
        report = run_all(cases)
    gc13 = next(r for r in report["results"] if r["case_id"] == "GC-013")
    assert gc13["status"] == "fail"
    assert "거부되어야 할" in gc13["detail"]
    assert not report["deploy_allowed"]


def test_unexpected_exception_does_not_abort_run(cases):
    """계산기가 예상 밖 예외를 던져도 게이트 전체가 죽지 않아야 한다."""
    def explodes(inputs):
        raise TypeError("의도적 오류")

    with patch.dict(ir.RECALCULATORS, {"lcr": (explodes, "x", "y")}):
        report = run_all(cases)          # 크래시하면 여기서 실패
    assert report["n_total"] == len(cases["cases"])
    gc16 = next(r for r in report["results"] if r["case_id"] == "GC-016")
    assert gc16["status"] == "fail"
    assert "정의되지 않은 예외" in gc16["detail"]


def test_prohibited_rejected_with_wrong_reason_is_fail():
    case = {"case_id": "X", "kind": "prohibited", "critical": True,
            "target": "lcr", "inputs": {"hqla": 1.0, "net_outflow": 0.0},
            "expect_error": "전혀 다른 사유", "rationale": "r"}
    r = run_case(case)
    assert r["status"] == "fail"
    assert "사유가 다르다" in r["detail"]


def test_sensitivity_direction_violation_detected():
    case = {"case_id": "X", "kind": "sensitivity", "critical": False,
            "target": "lcr", "inputs": {"hqla": 100.0, "net_outflow": 100.0},
            "perturbed_inputs": {"hqla": 90.0, "net_outflow": 100.0},
            "expected_direction": "increase", "rationale": "r"}
    r = run_case(case)
    assert r["status"] == "fail" and "방향 불일치" in r["detail"]


def test_sensitivity_magnitude_violation_detected():
    case = {"case_id": "X", "kind": "sensitivity", "critical": False,
            "target": "lcr", "inputs": {"hqla": 100.0, "net_outflow": 100.0},
            "perturbed_inputs": {"hqla": 110.0, "net_outflow": 100.0},
            "expected_direction": "increase", "expected_delta": 0.50,
            "tolerance": 1e-9, "rationale": "r"}
    r = run_case(case)
    assert r["status"] == "fail" and "변화량 불일치" in r["detail"]


def test_unregistered_target_is_fail():
    r = run_case({"case_id": "X", "kind": "regression", "critical": True,
                  "target": "frtb_ima", "inputs": {}, "expected": 1.0,
                  "rationale": "r"})
    assert r["status"] == "fail" and "등록되지 않은" in r["detail"]


# ---------- 비의도 변경 판정 (VAL-012) ----------

def test_no_change_request_means_all_unintended(cases):
    with patch.dict(ir.RECALCULATORS, {"lcr": (_broken_lcr(0.01), "x", "y")}):
        report = run_all(cases)
    ch = report["changes"]
    assert ch["intended"] == []
    assert {r["case_id"] for r in ch["unintended"]} == {"GC-001", "GC-007"}
    assert not report["deploy_allowed"]


def test_declared_target_makes_change_intended(cases):
    cr = {"change_id": "CHG-9999", "scope": {"targets": ["lcr"]}}
    with patch.dict(ir.RECALCULATORS, {"lcr": (_broken_lcr(0.01), "x", "y")}):
        report = run_all(cases, change_request=cr)
    ch = report["changes"]
    assert {r["case_id"] for r in ch["intended"]} == {"GC-001", "GC-007"}
    assert ch["unintended"] == []
    assert report["deploy_allowed"]
    assert ch["change_id"] == "CHG-9999"


def test_declared_case_id_scope(cases):
    """대상 전체가 아니라 개별 사례만 선언할 수도 있다."""
    cr = {"change_id": "CHG-1", "scope": {"cases": ["GC-001"]}}
    with patch.dict(ir.RECALCULATORS, {"lcr": (_broken_lcr(0.01), "x", "y")}):
        report = run_all(cases, change_request=cr)
    ch = report["changes"]
    assert {r["case_id"] for r in ch["intended"]} == {"GC-001"}
    assert {r["case_id"] for r in ch["unintended"]} == {"GC-007"}
    assert not report["deploy_allowed"]


def test_unrelated_scope_still_blocks(cases):
    cr = {"change_id": "CHG-2", "scope": {"targets": ["nsfr"]}}
    with patch.dict(ir.RECALCULATORS, {"lcr": (_broken_lcr(0.01), "x", "y")}):
        report = run_all(cases, change_request=cr)
    assert not report["deploy_allowed"]
    assert {r["case_id"] for r in report["changes"]["blocking"]} == {
        "GC-001", "GC-007"}


def test_non_critical_unintended_does_not_block():
    """비critical 실패는 보고하되 배포를 막지는 않는다."""
    results = [{"case_id": "X", "target": "t", "status": "fail",
                "critical": False, "kind": "regression", "detail": "d"}]
    ch = classify_changes(results, None)
    assert ch["unintended"] and ch["blocking"] == []


def test_passing_cases_are_not_classified_as_changes():
    results = [{"case_id": "X", "target": "t", "status": "pass",
                "critical": True, "kind": "regression", "detail": "d"}]
    ch = classify_changes(results, None)
    assert ch["intended"] == [] and ch["unintended"] == []


# ---------- 보고 / CLI ----------

def test_render_marks_blocking(cases):
    with patch.dict(ir.RECALCULATORS, {"lcr": (_broken_lcr(0.01), "x", "y")}):
        text = render(run_all(cases))
    assert "비의도 변경" in text and "배포 차단" in text


def test_render_lists_intended_with_change_id(cases):
    cr = {"change_id": "CHG-7", "scope": {"targets": ["lcr"]}}
    with patch.dict(ir.RECALCULATORS, {"lcr": (_broken_lcr(0.01), "x", "y")}):
        text = render(run_all(cases, change_request=cr))
    assert "의도된 변경" in text and "CHG-7" in text


def test_cli_run_and_list():
    from tools.golden_regression import main

    assert main(["run"]) == 0
    assert main(["list"]) == 0


def test_cli_blocks_with_exit_1(cases, tmp_path, capsys):
    from tools.golden_regression import main

    with patch.dict(ir.RECALCULATORS, {"lcr": (_broken_lcr(0.01), "x", "y")}):
        assert main(["run"]) == 1


def test_cli_change_request_file(tmp_path):
    from tools.golden_regression import main

    cr = tmp_path / "cr.json"
    cr.write_text(json.dumps({"change_id": "CHG-3",
                              "scope": {"targets": ["lcr"]}}),
                  encoding="utf-8")
    with patch.dict(ir.RECALCULATORS, {"lcr": (_broken_lcr(0.01), "x", "y")}):
        assert main(["run", "--change-request", str(cr)]) == 0


def test_catalog_sync():
    from tools.cli_index import CLI_MODULES
    from vta.cli.__main__ import _DISPATCH

    assert "tools.golden_regression" in {m for m, _ in CLI_MODULES}
    assert ("golden",) in _DISPATCH
