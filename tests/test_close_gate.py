"""마감 CL-10 판정과 실행 통제 이슈 원장 (2026-09 검수 2단계).

CL-10 「독립검증 게이트 확인」이 val_independent_target 의 행수로 완료가 됐다.
그 원장은 응답이 없어도 재계산 대상 수만큼 채워지므로, 응답대기·부적합에도
CL-10 완료 → CL-11 결재 상신 진행가능이 됐다. 이제 CL-10 은 게이트 상태(적합·
조건부)로만 완료다. 그리고 각 단계 빌더가 돌려주던 이슈 목록 4종은
gov_run_issue 원장에 실린다.
"""

from __future__ import annotations

import pandas as pd

from risk_lib import close_workflow as cw
from risk_lib.governance.run_issue import build_run_issue

ASOF = "2026-06-30"
ONE = pd.DataFrame({"a": [1]})


def _all_done(gate_status: str) -> dict:
    t = {x: ONE for x in cw.build_close_tasks({})["evidence_table"]}
    t["val_independent_request"] = pd.DataFrame({"status": [gate_status]})
    # CL-11·CL-12 는 행수가 아니라 승인·제출 상태로 판정한다 (검수 1단계)
    t["gov_approval"] = pd.DataFrame({"subject_type": ["업무보고서 서식"], "decision": ["승인"]})
    t["reg_submission"] = pd.DataFrame({"status": ["submitted"]})
    return t


def test_request_sent_is_complete_even_while_waiting():
    """CL-09 발신은 요청 행이 있으면 끝난 것이다. 게이트 상태와 무관하다."""
    led, _ = cw.build_close_workflow(_all_done("응답대기"), asof=ASOF)
    tk = led["opr_close_task"].set_index("task_id")
    assert tk.loc["CL-09", "status"] == "완료"


def test_gate_check_is_incomplete_until_the_gate_approves():
    for st in ("응답대기", "부적합", "요청됨"):
        led, issues = cw.build_close_workflow(_all_done(st), asof=ASOF)
        tk = led["opr_close_task"].set_index("task_id")
        g = led["opr_close_gate"].set_index("task_id")
        assert tk.loc["CL-10", "status"] == "미완료", st
        # 결재 상신·보고서 제출은 증빙이 있어도 순서위반으로 남는다
        assert g.loc["CL-11", "decision"] == "순서위반", st
        assert g.loc["CL-12", "decision"] == "순서위반", st
        assert any("CL-11" in i for i in issues)


def test_gate_check_completes_on_approval_or_conditional():
    for st in ("적합", "조건부"):
        led, issues = cw.build_close_workflow(_all_done(st), asof=ASOF)
        tk = led["opr_close_task"].set_index("task_id")
        assert tk.loc["CL-10", "status"] == "완료", st
        assert not issues


def test_gate_check_without_status_column_is_not_complete():
    t = _all_done("적합")
    t["val_independent_request"] = pd.DataFrame({"request_id": ["X"]})
    led, _ = cw.build_close_workflow(t, asof=ASOF)
    assert led["opr_close_task"].set_index("task_id").loc["CL-10", "status"] == "미완료"


def test_run_issue_ledger_carries_all_four_lists():
    df = build_run_issue(asof=ASOF, run_id="RUN-X",
                         close_issues=["CL-11: 순서위반 (…)", "CL-10: 차단 (…)"],
                         chain_notes=["gov_x: 원장 없음"],
                         retention_skipped=["rdm_y: 판 없음"],
                         run_problems=["일련번호 불연속"])
    assert len(df) == 5
    assert set(df["stage"]) == {"마감", "감사체인", "보존", "통합실행"}
    kinds = dict(zip(df["detail"], df["kind"]))
    assert kinds["CL-11: 순서위반 (…)"] == "순서위반"
    assert kinds["CL-10: 차단 (…)"] == "차단"
    assert not df.duplicated(subset=["asof", "stage", "seq"]).any()


def test_run_issue_ledger_exists_even_when_empty():
    """비어 있음(이슈 없음)과 없음(수집 안 함)은 다르다."""
    df = build_run_issue(asof=ASOF, run_id="RUN-X", close_issues=[],
                         chain_notes=[], retention_skipped=[], run_problems=[])
    assert len(df) == 0 and list(df.columns)[:3] == ["asof", "run_id", "stage"]
