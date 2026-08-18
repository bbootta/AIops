"""모형 승인 생애주기 (GOV-004).

모형 인벤토리(risk_lib.model_inventory)는 모형이 무엇이고 언제 검증했는지를
적는다. 없던 것은 그 사이의 절차다. **개발한 모형이 어떤 단계를 거쳐 운영에
들어갔는가**가 기록되지 않으면, 운영 중인 모형과 승인된 모형이 같다는 것을
증명할 수 없다.

원장 세 장과 게이트 하나로 만든다.

  gov_model_stage       단계 정의와 그 단계를 넘기는 승인 주체
  gov_model_transition  모형 x 단계 전이 기록
  gov_model_state       모형별 현재 단계와 통제 판정

전이는 정의된 순서로만 간다. 개발에서 운영으로 건너뛰는 전이는 등록 자체가
거부된다. 판정은 네 가지다.

  적합         승인 기록이 있고 재검증 기한 안이다
  증빙미첨부   전이는 기록됐으나 승인 문서 참조가 비어 있다
  기한초과     재검증 기한이 지났다
  승인없이운영 운영 단계인데 승인 전이가 없다

이 저장소의 현재 상태에서는 승인 문서(위원회 의사록)를 보관하지 않으므로
evidence_ref가 비어 있고 판정이 '증빙미첨부'로 나온다. 그것이 사실이며,
빈 칸을 채워 '적합'으로 만들지 않는다.

이 모듈의 TableSpec은 아직 datamodel.catalog에 등재하지 않았다. 등재는 실체화
검증과 문서 수치 일치를 함께 만족해야 하므로 배선 단계에서 `SPECS`를 넘긴다.
스펙 품질 기준(입도·기본키·float 단위·FK 대상 존재)은 지금부터 지킨다.

참조: RYNTA BRD GOV-004(신용평가모형 통제) · BNK-CRM-002(CSS Life Cycle),
SR 11-7(모형위험관리), 별표 9-1 제16항 라(독립 부서의 적합성검증).
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from risk_lib.datamodel.spec import ColumnSpec as C, ForeignKey as FK, TableSpec

STAGES = ("개발", "내부검증", "승인", "운영", "재검증", "폐기")
CONTROL_STATUSES = ("적합", "증빙미첨부", "기한초과", "승인없이운영")
RECORD_SOURCES = ("인벤토리 유도", "수기등록")

# 허용 전이. 여기 없는 전이는 register_transition이 거부한다.
ALLOWED_TRANSITIONS = (
    ("개발", "내부검증"),
    ("내부검증", "개발"),          # 검증 부적정 시 되돌린다
    ("내부검증", "승인"),
    ("승인", "운영"),
    ("운영", "재검증"),
    ("재검증", "운영"),
    ("재검증", "개발"),            # 재검증에서 재개발 판정
    ("운영", "폐기"),
    ("재검증", "폐기"),
)


MODEL_STAGE = TableSpec(
    name="gov_model_stage", korean="모형 단계 정의", product="PRD-VAL",
    grain="생애주기 단계 1개당 1행",
    columns=(
        C("stage", "string", "단계", nullable=False, allowed=STAGES),
        C("stage_order", "int", "단계 순서", nullable=False, unit="count",
          min_value=1),
        C("required_output", "text", "그 단계의 필수 산출물", nullable=False),
        C("approver_role", "text", "다음 단계로 넘기는 주체", nullable=False),
        C("citation", "text", "근거"),
    ),
    primary_key=("stage",),
)

MODEL_TRANSITION = TableSpec(
    name="gov_model_transition", korean="모형 단계 전이", product="PRD-VAL",
    grain="모형 x 전이 1건당 1행",
    columns=(
        C("transition_id", "text", "전이 식별자", nullable=False),
        C("model_id", "string", "모형 식별자", nullable=False),
        C("from_stage", "string", "이전 단계", nullable=False, allowed=STAGES),
        C("to_stage", "string", "이후 단계", nullable=False, allowed=STAGES),
        C("decided_on", "date", "결정일", nullable=False),
        C("decided_by", "text", "결정 주체", nullable=False),
        C("evidence_ref", "text", "승인 문서 참조", nullable=True,
          note="비어 있으면 판정이 증빙미첨부가 된다"),
        C("record_source", "string", "기록 출처", nullable=False,
          allowed=RECORD_SOURCES),
    ),
    primary_key=("transition_id",),
    foreign_keys=(FK(("from_stage",), "gov_model_stage", ("stage",)),
                  FK(("to_stage",), "gov_model_stage", ("stage",))),
)

MODEL_STATE = TableSpec(
    name="gov_model_state", korean="모형 현재 단계", product="PRD-VAL",
    grain="모형 1개당 1행",
    columns=(
        C("model_id", "string", "모형 식별자", nullable=False),
        C("model_name", "text", "모형명", nullable=False),
        C("tier", "int", "모형 등급", nullable=False, unit="count", min_value=1,
          max_value=3),
        C("owner", "text", "소유 부서", nullable=False),
        C("current_stage", "string", "현재 단계", nullable=False, allowed=STAGES),
        C("last_validation", "date", "직전 검증일", nullable=False),
        C("next_due", "date", "재검증 기한", nullable=False),
        C("days_overdue", "int", "기한 초과 일수", nullable=False, unit="days",
          min_value=0),
        C("n_transitions", "int", "전이 기록 수", nullable=False, unit="count",
          min_value=0),
        C("control_status", "string", "통제 판정", nullable=False,
          allowed=CONTROL_STATUSES),
        C("reason", "text", "판정 사유", nullable=False),
    ),
    primary_key=("model_id",),
)

SPECS: tuple[TableSpec, ...] = (MODEL_STAGE, MODEL_TRANSITION, MODEL_STATE)


class LifecycleError(ValueError):
    """정의되지 않은 전이를 등록하려 할 때."""


# ---------------------------------------------------------------- 단계 적재

_STAGES = (
    ("개발", 1, "모형 개발문서·데이터 명세·표본 정의", "모형 개발부서장",
     "SR 11-7 III(모형 개발·구현)"),
    ("내부검증", 2, "검증보고서(개념 건전성·결과 분석·성과 모니터링)",
     "적합성검증담당", "SR 11-7 V(모형 검증)"),
    ("승인", 3, "승인 의사록과 사용 조건", "리스크관리위원회",
     "별표 9-1 제15항(위원회 승인)"),
    ("운영", 4, "운영 전환 확인서·모니터링 계획", "모형 소유부서장",
     "SR 11-7 IV(모형 사용)"),
    ("재검증", 5, "주기 재검증 보고서", "적합성검증담당",
     "별표 9-1 제16항 라(정기 적합성검증)"),
    ("폐기", 6, "폐기 사유서와 대체 모형 지정", "리스크관리위원회",
     "SR 11-7 VI(거버넌스)"),
)

# 인벤토리 상태 코드를 생애주기 단계로 옮기는 표.
_INVENTORY_STAGE = {"DEV": "개발", "UAT": "내부검증", "PROD": "운영",
                    "RETIRED": "폐기"}


def build_model_stages() -> pd.DataFrame:
    return pd.DataFrame([{
        "stage": s[0], "stage_order": s[1], "required_output": s[2],
        "approver_role": s[3], "citation": s[4],
    } for s in _STAGES])


def register_transition(transitions: list[dict], *, model_id: str,
                        from_stage: str, to_stage: str, decided_on: str,
                        decided_by: str, evidence_ref: str | None,
                        record_source: str) -> dict:
    """전이를 등록한다. 정의되지 않은 전이는 거부한다.

    단계를 건너뛴 전이를 받아 주면 상태기계가 상태를 보증하지 못한다.
    """
    if (from_stage, to_stage) not in ALLOWED_TRANSITIONS:
        raise LifecycleError(f"정의되지 않은 전이: {from_stage} → {to_stage}")
    if record_source not in RECORD_SOURCES:
        raise LifecycleError(f"알 수 없는 기록 출처: {record_source!r}")
    row = {
        "transition_id": f"MT-{model_id}-{len(transitions) + 1:03d}",
        "model_id": model_id, "from_stage": from_stage, "to_stage": to_stage,
        "decided_on": decided_on, "decided_by": decided_by,
        "evidence_ref": evidence_ref or None, "record_source": record_source,
    }
    transitions.append(row)
    return row


def build_transitions(inventory) -> pd.DataFrame:
    """인벤토리에서 전이를 유도한다.

    유도할 수 있는 것만 만든다. 검증일은 인벤토리에 실재하므로 검증 전이의
    결정일로 쓰고, 운영 상태인 모형에는 승인·운영 전이를 붙인다. 승인 문서
    참조는 이 저장소에 없으므로 비운다. 채우면 없는 의사록을 있다고 적는 것이다.
    """
    rows: list[dict] = []
    for m in inventory:
        stage = _INVENTORY_STAGE.get(m.status)
        if stage is None:
            continue
        register_transition(rows, model_id=m.model_id, from_stage="개발",
                            to_stage="내부검증", decided_on=m.last_validation,
                            decided_by="적합성검증담당", evidence_ref=None,
                            record_source="인벤토리 유도")
        if stage in ("운영", "폐기"):
            register_transition(rows, model_id=m.model_id, from_stage="내부검증",
                                to_stage="승인", decided_on=m.last_validation,
                                decided_by="리스크관리위원회", evidence_ref=None,
                                record_source="인벤토리 유도")
            register_transition(rows, model_id=m.model_id, from_stage="승인",
                                to_stage="운영", decided_on=m.last_validation,
                                decided_by="모형 소유부서장", evidence_ref=None,
                                record_source="인벤토리 유도")
    return pd.DataFrame(rows, columns=[c.name for c in MODEL_TRANSITION.columns])


def judge(inventory, transitions: pd.DataFrame, *, asof: str) -> pd.DataFrame:
    """모형별 현재 단계와 통제 판정.

    판정 순서가 곧 우선순위다. 승인 없이 운영 중인 상태가 가장 무겁고, 그
    다음이 기한 초과, 그 다음이 증빙 미첨부다.
    """
    ref = date.fromisoformat(asof)
    rows = []
    for m in inventory:
        stage = _INVENTORY_STAGE.get(m.status, "개발")
        mine = transitions[transitions["model_id"] == m.model_id]
        approved = len(mine[mine["to_stage"] == "승인"]) > 0
        overdue = max(0, (ref - date.fromisoformat(m.next_due)).days)
        with_evidence = mine["evidence_ref"].notna().all() if len(mine) else False

        if stage == "운영" and not approved:
            status, reason = "승인없이운영", "운영 단계인데 승인 전이 기록이 없다"
        elif stage in ("운영", "재검증") and overdue > 0:
            status, reason = "기한초과", f"재검증 기한 {m.next_due}에서 {overdue}일 경과"
        elif len(mine) and not with_evidence:
            status, reason = "증빙미첨부", "전이 기록은 있으나 승인 문서 참조가 비어 있다"
        elif not len(mine):
            status, reason = "증빙미첨부", "전이 기록 자체가 없다"
        else:
            status, reason = "적합", f"재검증 기한 {m.next_due} 이내"

        rows.append({
            "model_id": m.model_id, "model_name": m.name, "tier": int(m.tier),
            "owner": m.owner, "current_stage": stage,
            "last_validation": m.last_validation, "next_due": m.next_due,
            "days_overdue": int(overdue), "n_transitions": int(len(mine)),
            "control_status": status, "reason": reason,
        })
    return pd.DataFrame(rows, columns=[c.name for c in MODEL_STATE.columns])


def build_model_lifecycle(*, asof: str, inventory=None
                          ) -> tuple[dict[str, pd.DataFrame], list[str]]:
    """생애주기 원장 3장을 만든다. (원장, 통제 위반 목록)을 돌려준다."""
    if inventory is None:
        from risk_lib.model_inventory import build_standard_inventory
        inventory = build_standard_inventory(today=date.fromisoformat(asof))
    stages = build_model_stages()
    transitions = build_transitions(inventory)
    state = judge(inventory, transitions, asof=asof)
    breaches = [f"{r['model_id']}: {r['control_status']} ({r['reason']})"
                for _, r in state.iterrows() if r["control_status"] != "적합"]
    return ({"gov_model_stage": stages,
             "gov_model_transition": transitions,
             "gov_model_state": state}, breaches)
