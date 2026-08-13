"""결산 마감 워크플로 (SEC-OAI-003).

마감은 순서가 있는 절차다. 데이터가 확정되기 전에 산출하면 그 수치는 다시
만들어야 하고, 자체검증 전에 결재를 올리면 검증은 형식이 된다. 이 저장소는
각 단계를 수행하는 코드는 갖고 있었지만 **단계 사이의 선후와 그 이행 상태**를
원장으로 두지 않았다.

원장 두 장이다.

  opr_close_task  마감 단계와 선행조건, 담당, 기한, 증빙 원장
  opr_close_gate  단계별 진행 가능 여부 판정

상태는 선언하지 않고 **증빙 원장의 실재로 판정한다**. 단계마다 그 단계가
끝났으면 존재해야 할 원장을 적어 두고, 그 원장이 비어 있으면 미완료다.
사람이 상태를 손으로 바꿀 수 있으면 마감표는 실제 진행과 갈라진다.

게이트는 선행 단계가 모두 완료여야 통과한다. 선행이 미완인데 완료로 표시된
단계는 '순서위반'으로 남긴다. 조용히 통과시키면 마감표가 순서를 보증하지 못한다.

이 모듈의 TableSpec은 아직 datamodel.catalog에 등재하지 않았다. 등재는 실체화
검증과 문서 수치 일치를 함께 만족해야 하므로 배선 단계에서 `SPECS`를 넘긴다.
스펙 품질 기준(입도·기본키·float 단위·FK 대상 존재)은 지금부터 지킨다.

참조: RYNTA BRD SEC-OAI-003(Agentic Close Workflow) · AIG-012(Human-in-the-loop),
AIMS_POLICY.md §2-1(인적 감독).
"""

from __future__ import annotations

import pandas as pd

from risk_lib.datamodel.spec import ColumnSpec as C, ForeignKey as FK, TableSpec

PHASES = ("데이터", "산출", "검증", "보고")
TASK_STATUSES = ("완료", "미완료")
GATE_DECISIONS = ("진행가능", "차단", "순서위반")


CLOSE_TASK = TableSpec(
    name="opr_close_task", korean="마감 작업", product="PRD-OPR",
    grain="마감 단계 1건당 1행",
    columns=(
        C("task_id", "string", "작업 식별자", nullable=False),
        C("sequence", "int", "수행 순서", nullable=False, unit="count",
          min_value=1),
        C("phase", "string", "단계 구분", nullable=False, allowed=PHASES),
        C("task_name", "text", "작업명", nullable=False),
        C("predecessors", "text", "선행 작업", nullable=False,
          note="쉼표로 구분한다. 선행이 없으면 빈 문자열이다"),
        C("owner_role", "text", "담당 역할", nullable=False),
        C("agent_ref", "text", "수행 에이전트", nullable=False),
        C("requires_approval", "bool", "사람 승인 필요", nullable=False),
        C("due_business_days", "int", "마감 후 영업일 기한", nullable=False,
          unit="days", min_value=1),
        C("evidence_table", "text", "완료 증빙 원장", nullable=False),
        C("status", "string", "이행 상태", nullable=False, allowed=TASK_STATUSES),
        C("evidence_rows", "int", "증빙 원장 행수", nullable=False, unit="count",
          min_value=0),
    ),
    primary_key=("task_id",),
)

CLOSE_GATE = TableSpec(
    name="opr_close_gate", korean="마감 게이트", product="PRD-OPR",
    grain="마감 단계 1건당 1행",
    columns=(
        C("gate_id", "string", "게이트 식별자", nullable=False),
        C("task_id", "string", "작업 식별자", nullable=False),
        C("asof", "date", "판정 기준일", nullable=False),
        C("decision", "string", "판정", nullable=False, allowed=GATE_DECISIONS),
        C("blocked_by", "text", "미완료 선행", nullable=False),
        C("reason", "text", "판정 사유", nullable=False),
    ),
    primary_key=("gate_id",),
    foreign_keys=(FK(("task_id",), "opr_close_task", ("task_id",)),),
)

SPECS: tuple[TableSpec, ...] = (CLOSE_TASK, CLOSE_GATE)


# ---------------------------------------------------------------- 적재 표
#
# 마감 절차 정의. 이 표가 유일한 데이터 적재 지점이다.
#
# (작업ID, 순서, 단계, 작업명, 선행, 담당역할, 에이전트, 승인필요, 기한, 증빙원장)
_TASKS = (
    ("CL-01", 1, "데이터", "원천 스냅샷 확정", (), "리스크데이터관리자",
     "data-pipeline", False, 1, "rdm_snapshot"),
    ("CL-02", 2, "데이터", "데이터품질 점검", ("CL-01",), "리스크데이터관리자",
     "risk-validator", False, 2, "rdm_dq_result"),
    ("CL-03", 3, "데이터", "원천 대사", ("CL-02",), "리스크데이터관리자",
     "risk-validator", False, 2, "rdm_reconciliation"),
    # 증빙은 rwa_result 다. rwa_sa_bucket 은 approach=="SA" 행만 담는 집계라
    # 국채·은행 익스포저가 없는 책에서는 0행이 되고, 그러면 신용 RWA 를 다
    # 산출하고도 이 단계가 미완료로 남는다. 다른 산출 단계와 마찬가지로 그
    # 리스크의 주 산출 원장을 본다.
    ("CL-04", 4, "산출", "신용 RWA 산출", ("CL-03",), "신용리스크관리자",
     "credit-risk-analyst", False, 3, "rwa_result"),
    ("CL-05", 5, "산출", "충당금 산출", ("CL-03",), "신용리스크관리자",
     "credit-risk-analyst", False, 3, "ecl_result"),
    ("CL-06", 6, "산출", "시장·평가 산출", ("CL-03",), "시장리스크관리자",
     "market-risk-analyst", False, 3, "mkt_var_es"),
    ("CL-07", 7, "산출", "유동성·금리리스크 산출", ("CL-03",), "자금·ALM담당",
     "alm-analyst", False, 3, "alm_irrbb_result"),
    ("CL-08", 8, "검증", "자체검증 수행", ("CL-04", "CL-05", "CL-06", "CL-07"),
     "리스크관리부장", "risk-validator", False, 4, "val_check"),
    ("CL-09", 9, "검증", "독립검증 요청 발신", ("CL-08",), "적합성검증담당",
     "validation-team-agent", False, 5, "val_independent_request"),
    ("CL-10", 10, "검증", "독립검증 게이트 확인", ("CL-09",), "적합성검증담당",
     "validation-team-agent", True, 7, "val_independent_target"),
    ("CL-11", 11, "보고", "결재 상신", ("CL-10",), "최고리스크책임자",
     "사람", True, 8, "gov_approval"),
    ("CL-12", 12, "보고", "감독 업무보고서 제출", ("CL-11",), "리스크관리부장",
     "regulatory-reporter", True, 10, "reg_submission"),
)


def build_close_tasks(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """마감 작업 원장. 상태는 증빙 원장의 행수로 판정한다."""
    rows = []
    for (tid, seq, phase, name, preds, owner, agent, approval, due,
         evidence) in _TASKS:
        df = tables.get(evidence)
        n = int(len(df)) if isinstance(df, pd.DataFrame) else 0
        rows.append({
            "task_id": tid, "sequence": seq, "phase": phase, "task_name": name,
            "predecessors": ",".join(preds), "owner_role": owner,
            "agent_ref": agent, "requires_approval": bool(approval),
            "due_business_days": due, "evidence_table": evidence,
            "status": "완료" if n > 0 else "미완료", "evidence_rows": n,
        })
    return pd.DataFrame(rows, columns=[c.name for c in CLOSE_TASK.columns])


def evaluate_gates(tasks: pd.DataFrame, *, asof: str) -> pd.DataFrame:
    """단계별 진행 가능 여부. 선행이 모두 완료여야 진행할 수 있다.

    선행이 미완인데 그 단계가 이미 완료로 판정된 경우는 '순서위반'이다.
    마감 절차가 지켜지지 않았다는 뜻이므로 차단과 구분해 남긴다.
    """
    status = dict(zip(tasks["task_id"], tasks["status"]))
    rows = []
    for _, t in tasks.sort_values("sequence").iterrows():
        preds = [p for p in str(t["predecessors"]).split(",") if p]
        pending = [p for p in preds if status.get(p) != "완료"]
        if pending and str(t["status"]) == "완료":
            decision = "순서위반"
            reason = f"선행 {'·'.join(pending)} 미완료인데 이 단계가 완료 상태다"
        elif pending:
            decision = "차단"
            reason = f"선행 {'·'.join(pending)} 미완료"
        else:
            decision = "진행가능"
            reason = ("선행 없음" if not preds
                      else f"선행 {'·'.join(preds)} 완료")
        rows.append({
            "gate_id": f"CG-{asof.replace('-', '')}-{t['task_id']}",
            "task_id": str(t["task_id"]), "asof": asof, "decision": decision,
            "blocked_by": ",".join(pending), "reason": reason,
        })
    return pd.DataFrame(rows, columns=[c.name for c in CLOSE_GATE.columns])


def build_close_workflow(tables: dict[str, pd.DataFrame], *, asof: str
                         ) -> tuple[dict[str, pd.DataFrame], list[str]]:
    """마감 원장 2장을 만든다. (원장, 차단·순서위반 목록)을 돌려준다."""
    tasks = build_close_tasks(tables)
    gates = evaluate_gates(tasks, asof=asof)
    issues = [f"{r['task_id']}: {r['decision']} ({r['reason']})"
              for _, r in gates.iterrows() if r["decision"] != "진행가능"]
    return {"opr_close_task": tasks, "opr_close_gate": gates}, issues
