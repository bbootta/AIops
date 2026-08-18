"""변경·Lifecycle 통제 (GOV-008).

이 저장소에는 모형 승인 생애주기(`model_lifecycle`)와 4-Eyes 결재(`gov_approval`)가
있다. 없던 것은 그 둘이 다루지 않는 변경이다. 규정 개정, 원장 스키마 변경, 프롬프트
개정은 모형 승인 절차를 타지 않으면서도 산출 수치를 바꾼다. 2026.1.29 개정으로
KRW 금리충격이 300/400/200에서 225/350/225로 바뀐 것이 그 예다. 규정 변경 한 건이
ΔEVE 전건을 바꾸는데 그 변경을 어느 원장도 기록하지 않았다.

원장 다섯 장과 게이트 한 개로 구성한다.

  gov_change_policy   변경 유형 x 위험등급별 필수 통제단계
  gov_change_request  변경요청 1건
  gov_change_impact   변경 x 영향대상(원장·화면·서식·모형)
  gov_change_control  변경 x 통제단계 실행 결과
  gov_change_gate     배포 게이트 판정

게이트는 fail-closed다. 필수 단계의 실행 기록이 없으면 '미실시'이며 배포불가다.
정책 원장에 없는 변경 유형도 배포불가로 판정하고 사유를 남긴다. 통제 기록이
없다는 사실을 통과로 읽으면 게이트가 없는 것과 같아진다.

판정 함수는 정책·실행기록 DataFrame만 보고, 자체 기본값을 갖지 않는다. 필수
단계 표는 `build_change_policy` 안에 한 번만 적재한다.

이 모듈의 TableSpec은 아직 datamodel.catalog에 등재하지 않았다. 등재는 실체화
검증과 문서 수치 일치를 함께 만족해야 하므로 배선 단계에서 `SPECS`를 넘긴다.

참조: RYNTA BRD GOV-008(변경·Lifecycle 통제) · PLT-012(회귀·Rollback),
BCBS 239 원칙 3(정확성·무결성), SR 11-7 모형 변경관리.
"""

from __future__ import annotations

import pandas as pd

from risk_lib.datamodel.spec import ColumnSpec as C, ForeignKey as FK, TableSpec

# 변경 유형. 모형만 통제하면 규정·데이터·프롬프트 변경이 통제를 우회한다.
CHANGE_CLASSES = ("규정", "모형", "데이터", "프롬프트", "코드")
RISK_TIERS = ("상", "중", "하")
CONTROL_STEPS = ("영향평가", "회귀시험", "독립검증", "CAB승인", "롤백계획")
CONTROL_STATUSES = ("완료", "실패", "미실시", "해당없음")
IMPACT_KINDS = ("원장", "화면", "서식", "모형", "문서")
GATE_DECISIONS = ("배포가능", "배포불가")
REQUEST_STATES = ("접수", "평가중", "심의중", "승인", "반려", "배포", "롤백")


# ---------------------------------------------------------------- 스펙

CHANGE_POLICY = TableSpec(
    name="gov_change_policy", korean="변경통제 정책", product="PRD-VAL",
    grain="변경 유형 x 위험등급 x 통제단계 1건당 1행",
    columns=(
        C("change_class", "string", "변경 유형", nullable=False,
          allowed=CHANGE_CLASSES),
        C("risk_tier", "string", "위험등급", nullable=False, allowed=RISK_TIERS),
        C("control_step", "string", "통제단계", nullable=False,
          allowed=CONTROL_STEPS),
        C("required", "bool", "필수 여부", nullable=False),
        C("rationale", "text", "필수로 둔 이유", nullable=False),
    ),
    primary_key=("change_class", "risk_tier", "control_step"),
    note="필수 여부를 원장에 두면, 건너뛴 단계가 건너뛰어도 되는 단계였는지를 "
         "감사에서 되짚을 수 있다.",
)

CHANGE_REQUEST = TableSpec(
    name="gov_change_request", korean="변경요청 원장", product="PRD-VAL",
    grain="변경요청 1건당 1행",
    columns=(
        C("change_id", "string", "변경 식별자", nullable=False),
        C("change_class", "string", "변경 유형", nullable=False,
          allowed=CHANGE_CLASSES),
        C("risk_tier", "string", "위험등급", nullable=False, allowed=RISK_TIERS),
        C("title", "text", "변경 제목", nullable=False),
        C("target_ref", "text", "변경 대상 참조", nullable=False,
          note="규정 조문·원장명·모형ID 등 변경이 닿는 실체"),
        C("requested_on", "date", "요청일", nullable=False),
        C("requester_role", "text", "요청 역할", nullable=False),
        C("state", "string", "진행 상태", nullable=False, allowed=REQUEST_STATES),
        C("rollback_ref", "text", "롤백 대상 판", nullable=True,
          note="되돌아갈 직전 판. 없으면 NULL이고 게이트가 사유로 쓴다"),
        C("citation", "text", "근거", nullable=False),
    ),
    primary_key=("change_id",),
)

CHANGE_IMPACT = TableSpec(
    name="gov_change_impact", korean="변경 영향대상", product="PRD-VAL",
    grain="변경 x 영향대상 1건당 1행",
    columns=(
        C("change_id", "string", "변경 식별자", nullable=False),
        C("impact_kind", "string", "영향대상 구분", nullable=False,
          allowed=IMPACT_KINDS),
        C("impact_ref", "text", "영향대상 참조", nullable=False),
        C("regression_required", "bool", "회귀시험 대상", nullable=False),
        C("note", "text", "영향 서술", nullable=False),
    ),
    primary_key=("change_id", "impact_kind", "impact_ref"),
    foreign_keys=(FK(("change_id",), "gov_change_request", ("change_id",)),),
    note="영향대상이 한 건도 없으면 영향평가를 한 것이 아니다. 게이트가 그것을 본다.",
)

CHANGE_CONTROL = TableSpec(
    name="gov_change_control", korean="변경통제 실행기록", product="PRD-VAL",
    grain="변경 x 통제단계 1건당 1행",
    columns=(
        C("change_id", "string", "변경 식별자", nullable=False),
        C("control_step", "string", "통제단계", nullable=False,
          allowed=CONTROL_STEPS),
        C("status", "string", "실행 결과", nullable=False,
          allowed=CONTROL_STATUSES),
        C("performed_on", "date", "실행일", nullable=True),
        C("performer_role", "text", "실행 역할", nullable=False),
        C("evidence_ref", "text", "증빙 참조", nullable=False),
    ),
    primary_key=("change_id", "control_step"),
    foreign_keys=(FK(("change_id",), "gov_change_request", ("change_id",)),),
)

CHANGE_GATE = TableSpec(
    name="gov_change_gate", korean="변경 배포 게이트", product="PRD-VAL",
    grain="변경 1건당 1행",
    columns=(
        C("change_id", "string", "변경 식별자", nullable=False),
        C("decision", "string", "판정", nullable=False, allowed=GATE_DECISIONS),
        C("n_required", "int", "필수 단계 수", nullable=False, unit="count",
          min_value=0),
        C("n_satisfied", "int", "충족 단계 수", nullable=False, unit="count",
          min_value=0),
        C("blocking_steps", "text", "미충족 단계", nullable=False),
        C("reason", "text", "판정 사유", nullable=False),
    ),
    primary_key=("change_id",),
    foreign_keys=(FK(("change_id",), "gov_change_request", ("change_id",)),),
)

SPECS: tuple[TableSpec, ...] = (
    CHANGE_POLICY, CHANGE_REQUEST, CHANGE_IMPACT, CHANGE_CONTROL, CHANGE_GATE)


# ---------------------------------------------------------------- 정책 적재
#
# 이 표가 이 모듈의 유일한 정책 적재 지점이다. 판정 함수는 이 표를 직접 읽지
# 않고 인자로 받은 정책 DataFrame만 본다.
#
# 등급별로 다르게 두는 이유. 위험등급 '하'까지 독립검증과 CAB을 요구하면
# 절차가 지켜지지 않고 우회 경로가 생긴다. 반대로 '상'에서 한 단계라도 빼면
# 산출 수치를 바꾸는 변경이 통제 밖에서 반영된다.
_STEP_RATIONALE = {
    "영향평가": "변경이 닿는 원장·화면·서식을 먼저 열거하지 않으면 회귀 범위를 정할 수 없다",
    "회귀시험": "기존 산출이 그대로인지 확인하지 않으면 의도하지 않은 수치 변동을 놓친다",
    "독립검증": "개발조직과 분리된 기준으로 재계산해야 가정 오류가 걸린다",
    "CAB승인": "배포 여부는 요청자가 아닌 별도 심의체가 정한다",
    "롤백계획": "되돌아갈 판을 정하지 않은 배포는 실패했을 때 멈출 방법이 없다",
}

# (변경유형, 위험등급, 필수 단계 집합)
# 명시하지 않은 단계는 required=False로 채운다.
_REQUIRED = {
    ("규정", "상"): CONTROL_STEPS,
    ("규정", "중"): ("영향평가", "회귀시험", "CAB승인", "롤백계획"),
    ("규정", "하"): ("영향평가", "회귀시험"),
    ("모형", "상"): CONTROL_STEPS,
    ("모형", "중"): ("영향평가", "회귀시험", "독립검증", "롤백계획"),
    ("모형", "하"): ("영향평가", "회귀시험"),
    ("데이터", "상"): ("영향평가", "회귀시험", "독립검증", "CAB승인", "롤백계획"),
    ("데이터", "중"): ("영향평가", "회귀시험", "롤백계획"),
    ("데이터", "하"): ("영향평가",),
    ("프롬프트", "상"): ("영향평가", "회귀시험", "독립검증", "CAB승인", "롤백계획"),
    ("프롬프트", "중"): ("영향평가", "회귀시험", "롤백계획"),
    ("프롬프트", "하"): ("영향평가", "회귀시험"),
    ("코드", "상"): ("영향평가", "회귀시험", "CAB승인", "롤백계획"),
    ("코드", "중"): ("영향평가", "회귀시험", "롤백계획"),
    ("코드", "하"): ("영향평가", "회귀시험"),
}


def build_change_policy() -> pd.DataFrame:
    """변경 유형 x 위험등급 x 통제단계 정책을 만든다."""
    rows = []
    for change_class in CHANGE_CLASSES:
        for tier in RISK_TIERS:
            required = _REQUIRED[(change_class, tier)]
            for step in CONTROL_STEPS:
                rows.append({
                    "change_class": change_class, "risk_tier": tier,
                    "control_step": step, "required": step in required,
                    "rationale": _STEP_RATIONALE[step],
                })
    return pd.DataFrame(rows, columns=[c.name for c in CHANGE_POLICY.columns])


# ---------------------------------------------------------------- 게이트

def required_steps(policy: pd.DataFrame, change_class: str, risk_tier: str
                   ) -> tuple[str, ...]:
    """정책 원장에서 필수 단계를 뽑는다. 해당 조합이 없으면 빈 튜플이다.

    빈 튜플과 '필수 단계 없음'은 게이트에서 다르게 다룬다. 조합 자체가 정책에
    없으면 판정 근거가 없는 것이므로 배포불가다.
    """
    hit = policy[(policy["change_class"] == change_class)
                 & (policy["risk_tier"] == risk_tier)]
    return tuple(hit[hit["required"]]["control_step"].tolist())


def evaluate_change_gate(request: pd.DataFrame, policy: pd.DataFrame,
                         controls: pd.DataFrame, impacts: pd.DataFrame
                         ) -> pd.DataFrame:
    """변경별 배포 게이트를 판정한다.

    배포가능 조건은 넷을 모두 만족해야 한다.
      1. 정책 원장에 해당 (변경유형, 위험등급) 조합이 있다
      2. 필수 단계가 전부 status='완료'다
      3. 어떤 단계도 status='실패'가 아니다
      4. 영향평가가 필수이면 영향대상이 1건 이상 있고, 롤백계획이 필수이면
         rollback_ref가 채워져 있다

    실행기록이 없는 필수 단계는 '미실시'로 세고 배포불가로 간다.
    """
    known = set(zip(policy["change_class"], policy["risk_tier"]))
    by_change: dict[str, dict[str, str]] = {}
    for row in controls.itertuples(index=False):
        by_change.setdefault(row.change_id, {})[row.control_step] = row.status
    impact_count = impacts.groupby("change_id").size().to_dict()

    rows = []
    for req in request.itertuples(index=False):
        combo = (req.change_class, req.risk_tier)
        if combo not in known:
            rows.append((req.change_id, "배포불가", 0, 0, "",
                         f"정책 원장에 {req.change_class}·{req.risk_tier} 조합이 없다. "
                         f"판정 근거가 없으므로 통과시키지 않는다"))
            continue
        need = required_steps(policy, req.change_class, req.risk_tier)
        done = by_change.get(req.change_id, {})
        blocking: list[str] = []
        reasons: list[str] = []
        for step in need:
            status = done.get(step, "미실시")
            if status == "완료":
                continue
            blocking.append(step)
            reasons.append(f"{step}={status}")
        # 실패는 필수 여부와 무관하게 막는다. 필수가 아닌 단계라도 실행해서
        # 실패했다면 그 사실을 알고 배포하는 것이므로 게이트가 잡아야 한다.
        for step, status in sorted(done.items()):
            if status == "실패" and step not in blocking:
                blocking.append(step)
                reasons.append(f"{step}=실패")
        if "영향평가" in need and impact_count.get(req.change_id, 0) == 0:
            blocking.append("영향평가")
            reasons.append("영향대상 0건")
        rollback_missing = (
            "롤백계획" in need
            and (req.rollback_ref is None or pd.isna(req.rollback_ref)
                 or not str(req.rollback_ref).strip()))
        if rollback_missing:
            if "롤백계획" not in blocking:
                blocking.append("롤백계획")
            reasons.append("롤백 대상 판 미지정")
        blocking = sorted(set(blocking))
        n_satisfied = len([s for s in need if done.get(s) == "완료"])
        decision = "배포불가" if blocking else "배포가능"
        reason = ("; ".join(sorted(set(reasons))) if reasons
                  else f"필수 {len(need)}단계 전건 완료")
        rows.append((req.change_id, decision, len(need), n_satisfied,
                     ", ".join(blocking), reason))
    return pd.DataFrame(rows, columns=[c.name for c in CHANGE_GATE.columns]
                        ).astype({"n_required": "int64", "n_satisfied": "int64"})


def build_change_control(requests, impacts, controls, *, policy=None
                         ) -> dict[str, pd.DataFrame]:
    """변경통제 원장 5장을 만든다.

    requests·impacts·controls는 dict 열거이며 각각 요청·영향대상·실행기록이다.
    호출자가 실제 변경 이력을 넘긴다. 이 함수는 표본 데이터를 만들지 않는다.
    """
    if policy is None:
        policy = build_change_policy()
    req = pd.DataFrame(list(requests),
                       columns=[c.name for c in CHANGE_REQUEST.columns])
    # 빈 결과에서도 컬럼 타입을 스펙과 맞춘다. object로 남으면 영향대상이
    # 하나도 없을 때만 스펙 검증이 실패한다.
    imp = pd.DataFrame(list(impacts),
                       columns=[c.name for c in CHANGE_IMPACT.columns]
                       ).astype({"regression_required": "bool"})
    ctl = pd.DataFrame(list(controls),
                       columns=[c.name for c in CHANGE_CONTROL.columns])
    gate = evaluate_change_gate(req, policy, ctl, imp)
    return {"gov_change_policy": policy, "gov_change_request": req,
            "gov_change_impact": imp, "gov_change_control": ctl,
            "gov_change_gate": gate}
