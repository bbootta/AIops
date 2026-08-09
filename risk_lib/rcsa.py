"""통제 자가진단 (SEC-OAI-001 RCSA).

운영손실 원장(opr_loss_event)은 이미 일어난 손실을 적고, KRI 원장(opr_kri)은
지표가 임계를 넘었는지 본다. 둘 다 사후다. 아직 손실로 나타나지 않은 통제
미비를 찾는 절차가 RCSA이며 이 저장소에 없었다.

원장 네 장이다.

  opr_rcsa_scale       빈도·영향 척도 정의와 등급 구간
  opr_rcsa_control     프로세스별 통제와 설계·운영 효과성
  opr_rcsa_assessment  고유위험 · 통제효과성 · 잔여위험 판정
  opr_rcsa_action      잔여위험이 수용범위를 넘은 건의 조치

척도와 등급 구간은 전부 원장에 있다. 판정 함수는 원장을 인자로 받고 숫자를
본문에 두지 않는다. 척도값은 기관이 정하는 내부 기준이므로 근거 상태를
'재량·미규정'으로 적는다.

사건 유형 어휘는 운영손실 원장과 같은 것을 쓴다. 어휘가 갈라지면 RCSA에서
높게 평가한 유형과 실제 손실이 많은 유형을 대조할 수 없다.

이 모듈의 TableSpec은 아직 datamodel.catalog에 등재하지 않았다. 등재는 실체화
검증과 문서 수치 일치를 함께 만족해야 하므로 배선 단계에서 `SPECS`를 넘긴다.
스펙 품질 기준(입도·기본키·float 단위·FK 대상 존재)은 지금부터 지킨다.

참조: RYNTA BRD SEC-OAI-001(운영손실·RCSA/KRI), Basel III OPE10(운영리스크
관리) · PSMOR 원칙 6(위험 식별·평가).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from risk_lib.alm.params import EVIDENCE_STATUS
from risk_lib.datamodel.spec import ColumnSpec as C, ForeignKey as FK, TableSpec
from risk_lib.op_loss import EVENT_TYPES

SCALE_KINDS = ("빈도", "영향", "잔여등급")
CONTROL_TYPES = ("예방", "적발", "시정")
EFFECTIVENESS = ("효과적", "부분효과", "미흡", "미설계")
RESIDUAL_GRADES = ("높음", "중간", "낮음")
ACTION_STATUSES = ("계획", "이행중", "완료")


RCSA_SCALE = TableSpec(
    name="opr_rcsa_scale", korean="RCSA 척도", product="PRD-OPR",
    grain="척도 종류 x 등급 1건당 1행",
    columns=(
        C("scale_kind", "string", "척도 종류", nullable=False, allowed=SCALE_KINDS),
        C("level", "int", "등급", nullable=False, unit="count", min_value=1,
          max_value=5),
        C("label", "text", "등급 명칭", nullable=False),
        C("bound_unit", "string", "구간 단위", nullable=False,
          allowed=("연간건수", "KRW", "점수"),
          note="척도 종류마다 구간의 단위가 다르므로 컬럼으로 적는다"),
        C("lower_bound", "float", "구간 하한", nullable=True,
          unit="bound_unit 참조"),
        C("upper_bound", "float", "구간 상한", nullable=True,
          unit="bound_unit 참조"),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("scale_kind", "level"),
    note="척도를 원장에 두어야 화면에서 그 척도가 무엇인지 볼 수 있다.",
)

RCSA_CONTROL = TableSpec(
    name="opr_rcsa_control", korean="RCSA 통제", product="PRD-OPR",
    grain="통제 1건당 1행",
    columns=(
        C("control_id", "string", "통제 식별자", nullable=False),
        C("process", "text", "대상 프로세스", nullable=False),
        C("control_name", "text", "통제 명칭", nullable=False),
        C("control_type", "string", "통제 유형", nullable=False,
          allowed=CONTROL_TYPES),
        C("is_automated", "bool", "자동화 여부", nullable=False),
        C("design_effectiveness", "string", "설계 효과성", nullable=False,
          allowed=EFFECTIVENESS),
        C("operating_effectiveness", "string", "운영 효과성", nullable=False,
          allowed=EFFECTIVENESS),
        C("effectiveness_factor", "float", "효과성 계수", nullable=False,
          unit="ratio", min_value=0.0, max_value=1.0),
        C("owner_role", "text", "통제 담당", nullable=False),
    ),
    primary_key=("control_id",),
)

RCSA_ASSESSMENT = TableSpec(
    name="opr_rcsa_assessment", korean="RCSA 평가", product="PRD-OPR",
    grain="프로세스 x 사건유형 1건당 1행",
    columns=(
        C("assessment_id", "string", "평가 식별자", nullable=False),
        C("process", "text", "대상 프로세스", nullable=False),
        C("event_type", "string", "손실 사건유형", nullable=False,
          allowed=tuple(EVENT_TYPES),
          note="opr_loss_event.event_type 과 같은 어휘"),
        C("control_id", "string", "적용 통제", nullable=False),
        C("inherent_frequency", "int", "고유 빈도등급", nullable=False,
          unit="count", min_value=1, max_value=5),
        C("inherent_impact", "int", "고유 영향등급", nullable=False, unit="count",
          min_value=1, max_value=5),
        C("inherent_score", "int", "고유위험 점수", nullable=False, unit="count",
          min_value=1, max_value=25),
        C("effectiveness_factor", "float", "통제 효과성 계수", nullable=False,
          unit="ratio", min_value=0.0, max_value=1.0),
        C("residual_score", "float", "잔여위험 점수", nullable=False, unit="count",
          min_value=0.0, max_value=25.0),
        C("residual_grade", "string", "잔여위험 등급", nullable=False,
          allowed=RESIDUAL_GRADES),
        C("assessed_on", "date", "평가일", nullable=False),
        C("assessor_role", "text", "평가 주체", nullable=False),
    ),
    primary_key=("assessment_id",),
    foreign_keys=(FK(("control_id",), "opr_rcsa_control", ("control_id",)),),
)

RCSA_ACTION = TableSpec(
    name="opr_rcsa_action", korean="RCSA 조치", product="PRD-OPR",
    grain="조치 1건당 1행",
    columns=(
        C("action_id", "string", "조치 식별자", nullable=False),
        C("assessment_id", "string", "평가 식별자", nullable=False),
        C("finding", "text", "미비 내용", nullable=False),
        C("action", "text", "조치 내용", nullable=False),
        C("owner_role", "text", "조치 책임", nullable=False),
        C("due_days", "int", "기한(일)", nullable=False, unit="days",
          min_value=1),
        C("status", "string", "이행 상태", nullable=False, allowed=ACTION_STATUSES),
    ),
    primary_key=("action_id",),
    foreign_keys=(FK(("assessment_id",), "opr_rcsa_assessment",
                     ("assessment_id",)),),
)

SPECS: tuple[TableSpec, ...] = (RCSA_SCALE, RCSA_CONTROL, RCSA_ASSESSMENT,
                                RCSA_ACTION)


# ---------------------------------------------------------------- 적재 표
#
# 아래 표들이 이 모듈의 유일한 데이터 적재 지점이다.

# (척도종류, 등급, 명칭, 하한, 상한)
_SCALES = (
    ("빈도", 1, "10년에 1회 미만", 0.0, 0.1),
    ("빈도", 2, "수년에 1회", 0.1, 1.0),
    ("빈도", 3, "연 1회 내외", 1.0, 6.0),
    ("빈도", 4, "월 1회 내외", 6.0, 52.0),
    ("빈도", 5, "주 1회 이상", 52.0, None),
    ("영향", 1, "1억원 미만", 0.0, 1e8),
    ("영향", 2, "1억~10억원", 1e8, 1e9),
    ("영향", 3, "10억~50억원", 1e9, 5e9),
    ("영향", 4, "50억~200억원", 5e9, 2e10),
    ("영향", 5, "200억원 초과", 2e10, None),
    ("잔여등급", 1, "낮음", 0.0, 6.0),
    ("잔여등급", 2, "중간", 6.0, 12.0),
    ("잔여등급", 3, "높음", 12.0, 25.0),
)

# 효과성 조합별 계수. 잔여위험 = 고유위험 x (1 - 계수) 에 쓰인다.
_EFFECTIVENESS_FACTOR = {
    ("효과적", "효과적"): 0.70,
    ("효과적", "부분효과"): 0.50,
    ("효과적", "미흡"): 0.25,
    ("부분효과", "효과적"): 0.50,
    ("부분효과", "부분효과"): 0.35,
    ("부분효과", "미흡"): 0.20,
    ("미흡", "효과적"): 0.25,
    ("미흡", "부분효과"): 0.20,
    ("미흡", "미흡"): 0.10,
    ("미설계", "미설계"): 0.00,
}

# (통제ID, 프로세스, 통제명, 유형, 자동화, 설계, 운영, 담당)
_CONTROLS = (
    ("CTL-01", "여신 실행", "약정서 필수항목 시스템 검증", "예방", True,
     "효과적", "효과적", "여신관리부"),
    ("CTL-02", "여신 실행", "실행 전 이중 승인", "예방", False,
     "효과적", "부분효과", "영업점"),
    ("CTL-03", "주문 집행", "주문 한도 사전 차단", "예방", True,
     "효과적", "효과적", "트레이딩데스크"),
    ("CTL-04", "주문 집행", "미체결·오류주문 일일 점검", "적발", False,
     "부분효과", "부분효과", "미들오피스"),
    ("CTL-05", "결제·정산", "결제 전 대사", "적발", True,
     "효과적", "부분효과", "결제팀"),
    ("CTL-06", "고객 응대", "불완전판매 모니터링", "적발", False,
     "부분효과", "미흡", "준법감시부"),
    ("CTL-07", "전산 운영", "변경 이관 승인 절차", "예방", False,
     "효과적", "부분효과", "IT운영팀"),
    ("CTL-08", "전산 운영", "재해복구 훈련", "시정", False,
     "부분효과", "미흡", "IT운영팀"),
    ("CTL-09", "인사·보안", "권한 정기 재승인", "예방", False,
     "미흡", "미흡", "인사부"),
    ("CTL-10", "외주 관리", "외주사 통제 점검", "적발", False,
     "미설계", "미설계", "총무부"),
)

# (프로세스, 사건유형, 통제ID, 고유 빈도등급, 고유 영향등급)
_ASSESSMENTS = (
    ("여신 실행", "처리·집행 오류", "CTL-01", 4, 2),
    ("여신 실행", "내부사기", "CTL-02", 2, 4),
    ("주문 집행", "처리·집행 오류", "CTL-03", 4, 3),
    ("주문 집행", "시스템·IT 장애", "CTL-04", 3, 4),
    ("결제·정산", "처리·집행 오류", "CTL-05", 4, 3),
    ("고객 응대", "고객·상품·영업관행", "CTL-06", 3, 4),
    ("전산 운영", "시스템·IT 장애", "CTL-07", 3, 5),
    ("전산 운영", "물리적 자산 손실", "CTL-08", 1, 5),
    ("인사·보안", "고용 / 직장 안전", "CTL-09", 2, 3),
    ("외주 관리", "외부사기", "CTL-10", 2, 4),
)

# 잔여위험 등급별 조치. 등급이 '높음'인 건에만 조치가 생긴다.
_ACTION_TEMPLATE = {
    "높음": ("통제 재설계와 이행 점검", "운영리스크관리자", 60, "계획"),
    "중간": ("통제 운영 증적 보완", "통제 담당부서", 90, "계획"),
}


_BOUND_UNITS = {"빈도": "연간건수", "영향": "KRW", "잔여등급": "점수"}


def build_rcsa_scale() -> pd.DataFrame:
    return pd.DataFrame([{
        "scale_kind": s[0], "level": s[1], "label": s[2],
        "bound_unit": _BOUND_UNITS[s[0]],
        "lower_bound": s[3], "upper_bound": s[4],
        "evidence_status": "재량·미규정",
    } for s in _SCALES], columns=[c.name for c in RCSA_SCALE.columns]
    ).astype({"lower_bound": "float64", "upper_bound": "float64"})


def build_rcsa_controls() -> pd.DataFrame:
    rows = []
    for cid, process, name, kind, auto, design, operating, owner in _CONTROLS:
        factor = _EFFECTIVENESS_FACTOR.get((design, operating))
        if factor is None:
            raise ValueError(f"{cid}: 효과성 조합 {design}/{operating}에 계수가 없다")
        rows.append({
            "control_id": cid, "process": process, "control_name": name,
            "control_type": kind, "is_automated": bool(auto),
            "design_effectiveness": design, "operating_effectiveness": operating,
            "effectiveness_factor": factor, "owner_role": owner,
        })
    return pd.DataFrame(rows, columns=[c.name for c in RCSA_CONTROL.columns])


def grade_residual(scale: pd.DataFrame, score: float) -> str:
    """잔여위험 점수를 등급으로 옮긴다. 구간은 인자로 받은 척도 원장에서 온다.

    경계 규약은 (하한, 상한]이다. 최하위 구간만 하한을 포함한다. 경계값이
    두 구간에 걸치면 같은 점수가 등급 두 개를 갖는다.
    """
    bands = scale[scale["scale_kind"] == "잔여등급"].sort_values("level")
    for i, (_, b) in enumerate(bands.iterrows()):
        lo, hi = float(b["lower_bound"]), b["upper_bound"]
        lower_ok = score >= lo if i == 0 else score > lo
        if lower_ok and (pd.isna(hi) or score <= float(hi)):
            return str(b["label"])
    raise ValueError(f"잔여위험 점수 {score}가 척도 구간 밖이다")


def assess(scale: pd.DataFrame, controls: pd.DataFrame, *, asof: str
           ) -> pd.DataFrame:
    """고유위험과 통제 효과성으로 잔여위험을 산출한다.

    잔여위험 = 고유위험 점수 x (1 - 통제 효과성 계수).
    계수는 통제 원장에서 오고 등급 구간은 척도 원장에서 온다.
    """
    ctl = controls.set_index("control_id")
    rows = []
    for i, (process, event_type, cid, freq, impact) in enumerate(_ASSESSMENTS,
                                                                 start=1):
        if cid not in ctl.index:
            raise ValueError(f"{cid}: 통제 원장에 없는 통제를 참조한다")
        factor = float(ctl.loc[cid, "effectiveness_factor"])
        inherent = int(freq) * int(impact)
        residual = round(inherent * (1.0 - factor), 4)
        rows.append({
            "assessment_id": f"RCSA-{i:03d}", "process": process,
            "event_type": event_type, "control_id": cid,
            "inherent_frequency": int(freq), "inherent_impact": int(impact),
            "inherent_score": inherent, "effectiveness_factor": factor,
            "residual_score": residual,
            "residual_grade": grade_residual(scale, residual),
            "assessed_on": asof, "assessor_role": "운영리스크관리자",
        })
    return pd.DataFrame(rows, columns=[c.name for c in RCSA_ASSESSMENT.columns])


def build_actions(assessments: pd.DataFrame, controls: pd.DataFrame
                  ) -> pd.DataFrame:
    """잔여위험이 낮음이 아닌 건에 조치를 붙인다.

    잔여위험을 높게 판정하고도 조치를 붙이지 않으면 그 판정은 후속 절차로
    이어지지 않는다. 등급별 표준 조치를 붙이고 통제 담당을 조치 책임으로 옮긴다.
    """
    ctl = controls.set_index("control_id")
    rows = []
    for i, (_, a) in enumerate(assessments.iterrows(), start=1):
        template = _ACTION_TEMPLATE.get(str(a["residual_grade"]))
        if template is None:
            continue
        action, owner_role, due, status = template
        cid = str(a["control_id"])
        owner = (str(ctl.loc[cid, "owner_role"])
                 if str(a["residual_grade"]) == "중간" else owner_role)
        rows.append({
            "action_id": f"RCA-{i:03d}",
            "assessment_id": str(a["assessment_id"]),
            "finding": (f"{a['process']} / {a['event_type']} 잔여위험 "
                        f"{a['residual_score']} ({a['residual_grade']}), "
                        f"통제 {cid} 효과성 계수 {a['effectiveness_factor']}"),
            "action": action, "owner_role": owner, "due_days": int(due),
            "status": status,
        })
    return pd.DataFrame(rows, columns=[c.name for c in RCSA_ACTION.columns])


def compare_with_losses(assessments: pd.DataFrame, loss_events: pd.DataFrame
                        ) -> pd.DataFrame:
    """RCSA 평가와 실제 손실 분포를 사건유형으로 대조한다.

    자가진단이 낮게 본 유형에서 손실이 많이 났다면 진단 자체를 다시 봐야 한다.
    손실 원장이 없으면 빈 표를 돌려주고 대조했다고 적지 않는다.
    """
    cols = ["event_type", "max_residual_score", "n_loss_events", "loss_amount",
            "flag"]
    if loss_events is None or len(loss_events) == 0:
        return pd.DataFrame(columns=cols)
    amount_col = next((c for c in ("gross_loss", "loss_amount", "amount")
                       if c in loss_events.columns), None)
    if amount_col is None:
        return pd.DataFrame(columns=cols)
    agg = (loss_events.groupby("event_type")[amount_col]
           .agg(["count", "sum"]).reset_index())
    top = float(agg["sum"].max()) if len(agg) else 0.0
    res = assessments.groupby("event_type")["residual_score"].max()
    rows = []
    for _, r in agg.iterrows():
        et = str(r["event_type"])
        score = float(res.get(et, np.nan))
        heavy = float(r["sum"]) >= 0.5 * top
        rows.append({
            "event_type": et, "max_residual_score": score,
            "n_loss_events": int(r["count"]), "loss_amount": float(r["sum"]),
            "flag": ("손실 상위인데 잔여위험 낮음"
                     if heavy and not np.isnan(score) and score < 6.0
                     else ""),
        })
    return pd.DataFrame(rows, columns=cols)


def build_rcsa(*, asof: str) -> dict[str, pd.DataFrame]:
    """RCSA 원장 4장을 만든다."""
    scale = build_rcsa_scale()
    controls = build_rcsa_controls()
    assessments = assess(scale, controls, asof=asof)
    actions = build_actions(assessments, controls)
    return {"opr_rcsa_scale": scale,
            "opr_rcsa_control": controls,
            "opr_rcsa_assessment": assessments,
            "opr_rcsa_action": actions}
