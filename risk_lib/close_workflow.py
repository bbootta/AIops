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
#
# 증빙 판정은 원장 이름별로 두 유형이다 (`_EVIDENCE_KIND`).
#   행수형   원장에 행이 있으면 완료. 산출 원장에 맞다.
#   게이트형 원장의 status 열이 승인 상태(적합·조건부)여야 완료. CL-10 (3선
#            게이트 확인)이 여기 해당한다. 행수로 보면
#            응답이 없어도 요청 1행이 있어 완료가 되고, 그 완료가 결재 상신을
#            진행가능으로 밀어 올렸다 (검수 상-2).
_TASKS = (
    # agent_ref 는 tests/risk_agents.py 명부의 이름이거나 사람·3선 팀이다.
    # 명부 밖 이름(data-pipeline·credit-risk-analyst·regulatory-reporter)을
    # 박아 두면 마감표가 존재하지 않는 담당을 가리킨다 (검수 상-3).
    ("CL-01", 1, "데이터", "원천 스냅샷 확정", (), "리스크데이터관리자",
     "risk-orchestrator", False, 1, "rdm_snapshot"),
    ("CL-02", 2, "데이터", "데이터품질 점검", ("CL-01",), "리스크데이터관리자",
     "risk-validator", False, 2, "rdm_dq_result"),
    ("CL-03", 3, "데이터", "원천 대사", ("CL-02",), "리스크데이터관리자",
     "risk-validator", False, 2, "rdm_reconciliation"),
    # 증빙은 rwa_result 다. rwa_sa_bucket 은 approach=="SA" 행만 담는 집계라
    # 국채·은행 익스포저가 없는 책에서는 0행이 되고, 그러면 신용 RWA 를 다
    # 산출하고도 이 단계가 미완료로 남는다. 다른 산출 단계와 마찬가지로 그
    # 리스크의 주 산출 원장을 본다.
    ("CL-04", 4, "산출", "신용 RWA 산출", ("CL-03",), "신용리스크관리자",
     "rwa-calculator", False, 3, "rwa_result"),
    ("CL-05", 5, "산출", "충당금 산출", ("CL-03",), "신용리스크관리자",
     "ifrs9-ecl-analyst", False, 3, "ecl_result"),
    ("CL-06", 6, "산출", "시장·평가 산출", ("CL-03",), "시장리스크관리자",
     "market-risk-analyst", False, 3, "mkt_var_es"),
    ("CL-07", 7, "산출", "유동성·금리리스크 산출", ("CL-03",), "자금·ALM담당",
     "alm-analyst", False, 3, "alm_irrbb_result"),
    ("CL-08", 8, "검증", "자체검증 수행", ("CL-04", "CL-05", "CL-06", "CL-07"),
     "리스크관리부장", "risk-validator", False, 4, "val_check"),
    ("CL-09", 9, "검증", "독립검증 요청 발신", ("CL-08",), "적합성검증담당",
     "validation-team-agent", False, 5, "val_independent_request"),
    ("CL-10", 10, "검증", "독립검증 게이트 확인", ("CL-09",), "적합성검증담당",
     "validation-team-agent", True, 7, "val_independent_request"),
    ("CL-11", 11, "보고", "결재 상신", ("CL-10",), "최고리스크책임자",
     "사람", True, 8, "gov_approval"),
    ("CL-12", 12, "보고", "감독 업무보고서 제출", ("CL-11",), "리스크관리부장",
     "risk-orchestrator", True, 10, "reg_submission"),
)

# 명부 밖이어도 되는 담당: 사람과 3선 팀에이전트(다른 브랜치의 하네스).
NON_ROSTER_AGENT_REFS = frozenset({"사람", "validation-team-agent"})


def task_agent_refs() -> set[str]:
    return {t[6] for t in _TASKS}


# 작업 ID 기준이다. CL-09(요청 발신)와 CL-10(게이트 확인)이 같은 원장을 증빙으로
# 쓰는데, 발신은 요청 행이 있으면 끝난 것이고 게이트 확인은 승인 상태여야 한다.
#   승인형   gov_approval 의 서식 행이 전부 '승인' 이어야 완료 (CL-11 결재 상신).
#            '대기' 행이 있으면 상신은 됐어도 결재가 난 것이 아니다.
#   제출형   reg_submission 의 status 가 전부 'submitted' 여야 완료 (CL-12).
_EVIDENCE_KIND = {"CL-10": "게이트", "CL-11": "승인", "CL-12": "제출"}
_GATE_APPROVED = ("적합", "조건부")


def _evidence_done(task_id: str, df) -> tuple[int, bool]:
    """(증빙 행수, 완료 여부). 유형별 판정식은 여기 한 곳에만 있다."""
    n = int(len(df)) if isinstance(df, pd.DataFrame) else 0
    kind = _EVIDENCE_KIND.get(task_id)
    if kind == "게이트":
        if n == 0 or "status" not in df.columns:
            return n, False
        return n, bool(df["status"].astype(str).isin(_GATE_APPROVED).all())
    if kind == "승인":
        if n == 0 or "decision" not in df.columns:
            return n, False
        forms = df[df["subject_type"] == "업무보고서 서식"] if "subject_type" in df.columns else df
        return n, bool(len(forms)) and bool((forms["decision"].astype(str) == "승인").all())
    if kind == "제출":
        if n == 0 or "status" not in df.columns:
            return n, False
        return n, bool((df["status"].astype(str) == "submitted").all())
    return n, n > 0


def build_close_tasks(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """마감 작업 원장. 상태는 증빙 유형별 판정식(`_evidence_done`)으로 정한다."""
    rows = []
    for (tid, seq, phase, name, preds, owner, agent, approval, due,
         evidence) in _TASKS:
        df = tables.get(evidence)
        n, done = _evidence_done(tid, df)
        rows.append({
            "task_id": tid, "sequence": seq, "phase": phase, "task_name": name,
            "predecessors": ",".join(preds), "owner_role": owner,
            "agent_ref": agent, "requires_approval": bool(approval),
            "due_business_days": due, "evidence_table": evidence,
            "status": "완료" if done else "미완료", "evidence_rows": n,
        })
    return pd.DataFrame(rows, columns=[c.name for c in CLOSE_TASK.columns])


def _all_predecessors(tasks: pd.DataFrame) -> dict[str, list[str]]:
    """작업 → 그 작업의 모든 선행(이행폐포).

    직속 선행만 보면 상류 위반이 아래로 내려가지 않는다. CL-02 가 미완인데
    CL-03 이 완료면 CL-03 만 순서위반으로 찍히고, CL-04 부터 CL-12 결재 상신·
    업무보고서 제출까지는 직속 선행이 완료라는 이유로 진행가능이 된다. 마감
    게이트가 결재를 막는 통제인 이상 그 통과는 사실과 다르다.
    """
    direct = {str(t): [p for p in str(v).split(",") if p]
              for t, v in zip(tasks["task_id"], tasks["predecessors"])}
    out: dict[str, list[str]] = {}
    for tid in direct:
        seen: set[str] = set()
        stack = list(direct.get(tid, ()))
        while stack:
            q = stack.pop()
            if q in seen:
                continue
            seen.add(q)
            stack.extend(direct.get(q, ()))
        out[tid] = sorted(seen)
    return out


def evaluate_gates(tasks: pd.DataFrame, *, asof: str) -> pd.DataFrame:
    """단계별 진행 가능 여부. 선행이 모두 완료여야 진행할 수 있다.

    '선행'은 직속이 아니라 이행폐포다. 앞 단계 하나가 미완이면 그 뒤 전부가
    막히거나 순서위반이 된다.

    선행이 미완인데 그 단계가 이미 완료로 판정된 경우는 '순서위반'이다.
    마감 절차가 지켜지지 않았다는 뜻이므로 차단과 구분해 남긴다.
    """
    status = dict(zip(tasks["task_id"], tasks["status"]))
    allp = _all_predecessors(tasks)
    rows = []
    for _, t in tasks.sort_values("sequence").iterrows():
        preds = allp.get(str(t["task_id"]), [])
        pending = [p for p in preds if status.get(p) != "완료"]
        if pending and str(t["status"]) == "완료":
            decision = "순서위반"
            reason = f"선행 {'·'.join(pending)} 미완료인데 이 단계가 완료 상태다"
        elif pending:
            decision = "차단"
            reason = f"선행 {'·'.join(pending)} 미완료"
        else:
            decision = "진행가능"
            # 이행폐포라 뒤 단계일수록 선행이 길다. 다 적으면 못 읽는다.
            reason = ("선행 없음" if not preds
                      else f"선행 {'·'.join(preds)} 완료" if len(preds) <= 3
                      else f"선행 {len(preds)}단계 완료 ({preds[0]}~{preds[-1]})")
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
