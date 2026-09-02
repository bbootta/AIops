"""결재 경로에 게이트 실장 (2026-09 검수 1단계).

검수에서 드러난 것: 3선 게이트(`check_gate().require()`)는 만들어졌지만 결재
경로의 어디도 그것을 부르지 않았다. gov_approval 은 서식 자체 검증만 보고
'승인' 을 찍었고, reg_submission 은 'approved' 였고, 마감 CL-11·CL-12 는 그
행수만 보고 완료였다. 게이트가 부적합이어도 결재가 끝난 것으로 읽혔다.

이제 (1) 서식 승인은 게이트와 2선 차단 사유가 비어야 '승인', (2) 제출 상태는
보류 사유가 있으면 'reviewed' 로 내려가며, (3) CL-11 은 서식 승인이 전부
'승인' 일 때, CL-12 는 제출이 전부 'submitted' 일 때만 완료다. (4) 패키징은
require_gate 로 게이트를 실제로 걸 수 있고, 걸지 않아도 보류 사유를 파일로
남긴다.
"""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from risk_lib import close_workflow as cw
from risk_lib.ui_studio.governance import approval_hold_reasons, build_approvals

RUN = "RUN-20260630-42"


def _gate(status: str) -> SimpleNamespace:
    return SimpleNamespace(status=status, approved=(status == "적합"))


def _val_check(*rows: tuple[str, str, bool]) -> pd.DataFrame:
    return pd.DataFrame(
        [{"check_name": n, "status": s, "blocks_approval": b} for n, s, b in rows]
        or [{"check_name": "x", "status": "PASS", "blocks_approval": False}])


def _submission(n: int = 2, failed: int = 0) -> pd.DataFrame:
    return pd.DataFrame({
        "form_id": [f"F{i}" for i in range(n)],
        "reviewed_by": "검토자", "approved_by": "승인자",
        "n_failed_checks": failed, "digest": "abcdef0123456789",
    })


# ----- approval_hold_reasons -------------------------------------------------

def test_unknown_gate_is_a_hold_reason():
    """게이트 객체가 없으면 통과가 아니다. 모르는 상태는 승인이 아니다."""
    assert approval_hold_reasons({"val_check": _val_check()}, None) == ["3선 게이트 미확인"]


@pytest.mark.parametrize("status", ["요청됨", "응답대기", "부적합", "조건부"])
def test_unapproved_gate_holds(status):
    """조건부도 여기서는 보류다. 조건부 통과는 ConditionalApproval 기록이 있어야
    하고, 그 기록은 사람이 require() 에 넘기는 것이라 원장 조립 단계엔 없다."""
    reasons = approval_hold_reasons({"val_check": _val_check()}, _gate(status))
    assert reasons == [f"3선 게이트 {status}"]


def test_second_line_fail_and_regulatory_shortfall_hold():
    vc = _val_check(("a", "FAIL", False), ("bis_buffer_requirement", "WARN", True))
    reasons = approval_hold_reasons({"val_check": vc}, _gate("적합"))
    assert reasons == ["자체검증 FAIL 1건", "규제 미달 bis_buffer_requirement"]


def test_clean_run_with_approved_gate_has_no_hold():
    assert approval_hold_reasons({"val_check": _val_check()}, _gate("적합")) == []


# ----- build_approvals -------------------------------------------------------

def test_form_approval_waits_while_gate_is_not_approved():
    t = {"val_check": _val_check(), "reg_submission": _submission()}
    ap = build_approvals(t, RUN, gate=_gate("부적합"))
    forms = ap[ap.subject_type == "업무보고서 서식"]
    assert len(forms) == 2
    assert (forms.decision == "대기").all()
    assert forms.evidence_ref.str.contains("보류: 3선 게이트 부적합").all()


def test_form_approval_waits_on_second_line_blocker_even_with_approved_gate():
    t = {"val_check": _val_check(("stress_trough_meets_requirement", "FAIL", True)),
         "reg_submission": _submission()}
    ap = build_approvals(t, RUN, gate=_gate("적합"))
    forms = ap[ap.subject_type == "업무보고서 서식"]
    assert (forms.decision == "대기").all()
    assert forms.evidence_ref.str.contains("규제 미달 stress_trough_meets_requirement").all()


def test_form_approval_is_granted_only_when_nothing_holds():
    t = {"val_check": _val_check(), "reg_submission": _submission()}
    ap = build_approvals(t, RUN, gate=_gate("적합"))
    forms = ap[ap.subject_type == "업무보고서 서식"]
    assert (forms.decision == "승인").all()
    assert not forms.evidence_ref.str.contains("보류").any()


def test_no_gate_argument_never_approves():
    """게이트를 넘기지 않은 호출부가 남아 있어도 '승인' 이 새지 않는다."""
    ap = build_approvals({"val_check": _val_check(),
                          "reg_submission": _submission()}, RUN)
    forms = ap[ap.subject_type == "업무보고서 서식"]
    assert (forms.decision == "대기").all()


# ----- 마감 CL-11 · CL-12 ------------------------------------------------------

def _close_tables(approvals: pd.DataFrame, submissions: pd.DataFrame) -> dict:
    one = pd.DataFrame({"a": [1]})
    t = {x: one for x in cw.build_close_tasks({})["evidence_table"]}
    t["val_independent_request"] = pd.DataFrame({"status": ["적합"]})
    t["gov_approval"] = approvals
    t["reg_submission"] = submissions
    return t


def _approvals(*decisions: str) -> pd.DataFrame:
    return pd.DataFrame({"subject_type": "업무보고서 서식",
                         "decision": list(decisions)})


def test_approval_submission_needs_every_form_approved():
    """'대기' 한 행이라도 있으면 결재 상신(CL-11)은 완료가 아니다. 행수로 보면
    보류 행도 결재로 읽힌다 (검수 상-1)."""
    led, _ = cw.build_close_workflow(
        _close_tables(_approvals("승인", "대기"),
                      pd.DataFrame({"status": ["submitted"]})), asof="2026-06-30")
    tk = led["opr_close_task"].set_index("task_id")
    assert tk.loc["CL-11", "status"] == "미완료"
    # 제출 증빙이 있어도 결재가 나지 않았으니 CL-12 는 순서위반으로 남는다
    assert led["opr_close_gate"].set_index("task_id").loc["CL-12", "decision"] == "순서위반"


def test_approval_submission_completes_when_all_forms_approved():
    led, issues = cw.build_close_workflow(
        _close_tables(_approvals("승인", "승인"),
                      pd.DataFrame({"status": ["submitted", "submitted"]})),
        asof="2026-06-30")
    tk = led["opr_close_task"].set_index("task_id")
    assert tk.loc["CL-11", "status"] == "완료"
    assert tk.loc["CL-12", "status"] == "완료"
    assert not issues


def test_report_submission_needs_every_form_submitted():
    led, _ = cw.build_close_workflow(
        _close_tables(_approvals("승인"),
                      pd.DataFrame({"status": ["submitted", "reviewed"]})),
        asof="2026-06-30")
    tk = led["opr_close_task"].set_index("task_id")
    assert tk.loc["CL-12", "status"] == "미완료"


def test_non_form_approval_rows_do_not_count_as_form_approval():
    """조정 승인 행만 '승인' 이고 서식 행이 없으면 결재 상신은 완료가 아니다."""
    ap = pd.DataFrame({"subject_type": ["조정"], "decision": ["승인"]})
    led, _ = cw.build_close_workflow(
        _close_tables(ap, pd.DataFrame({"status": ["submitted"]})),
        asof="2026-06-30")
    assert led["opr_close_task"].set_index("task_id").loc["CL-11", "status"] == "미완료"
