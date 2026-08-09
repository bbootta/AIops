"""위기상황 경영조치 (BNK-ST-005).

위기상황분석은 자본경로(st_capital_path)를 산출하고 한도 엔진은 위반을
경보한다. 둘 사이가 비어 있었다. **경로가 요구비율을 침범했을 때 무엇을
발동하고 누가 승인하며 그 효과가 얼마인가**가 원장에 없으면, 위기상황분석은
경고까지만 하고 끝난다.

원장 두 장이다.

  st_action_playbook   발동 조건과 조치, 승인 주체, 소요 기간
  st_management_action 시나리오 x 분기별 발동 기록

**자본효과를 산출하지 않는다.** [별표 19] 제26항 라는 비상계획의 완화 효과를
"실현 가능한 가정에 기초한 경우" 고려한다고 정한다. 조치별 자본 개선폭은
이사회가 승인한 가정이 있어야 그 요건을 만족하며 이 저장소에 그 원장이 없다.
효과 칸은 NULL이고 발동 기록은 남기되 경로에 반영하지 않는다.

발동 임계는 인자로 받는다. 규제 요구비율은 자본 산출 쪽에 이미 있고, 이
모듈이 다시 적으면 같은 값이 두 벌이 된다. 내부 조기경보 임계는 승인 원장이
없으므로 NULL이고 그 조치는 '판정불가'로 남는다.

이 모듈의 TableSpec은 아직 datamodel.catalog에 등재하지 않았다. 등재는 실체화
검증과 문서 수치 일치를 함께 만족해야 하므로 배선 단계에서 `SPECS`를 넘긴다.
스펙 품질 기준(입도·기본키·float 단위·FK 대상 존재)은 지금부터 지킨다.

참조: RYNTA BRD BNK-ST-005(한도·경영조치) · BNK-ST-004(손익·RWA·자본),
은행업감독업무시행세칙 [별표 19] 위기상황분석 실시기준 제7항 다 · 제26항 라
(원문: docs/primary_sources/규정원문_20260809/03_별표19_위기상황분석_실시기준.txt),
BCBS d450(스트레스테스트 원칙).
"""

from __future__ import annotations

import pandas as pd

from risk_lib.alm.params import EVIDENCE_STATUS
from risk_lib.datamodel.spec import ColumnSpec as C, ForeignKey as FK, TableSpec

METRICS = ("cet1_ratio", "tier1_ratio", "total_ratio")
ACTION_TYPES = ("배당 유보", "자사주 매입 중단", "위험가중자산 감축",
                "자본 확충", "비용 절감", "사업부문 축소")
APPROVAL_BODIES = ("이사회", "리스크관리위원회", "경영위원회")
ACTION_STATUSES = ("발동", "판정불가", "미발동")


ACTION_PLAYBOOK = TableSpec(
    name="st_action_playbook", korean="경영조치 발동표", product="PRD-ST",
    grain="조치 1건당 1행",
    columns=(
        C("action_id", "string", "조치 식별자", nullable=False),
        C("trigger_metric", "string", "발동 지표", nullable=False,
          allowed=METRICS),
        C("trigger_level", "float", "발동 임계", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0,
          note="승인 원장이 없는 내부 임계는 NULL이며 판정하지 않는다"),
        C("trigger_basis", "text", "임계 근거", nullable=False),
        C("action_type", "string", "조치 유형", nullable=False,
          allowed=ACTION_TYPES),
        C("capital_effect_bp", "float", "자본 개선폭", nullable=True, unit="bp",
          min_value=0.0,
          note="이사회 승인 가정이 없어 전건 NULL이다"),
        C("lead_time_days", "int", "소요 기간", nullable=False, unit="days",
          min_value=1),
        C("approval_body", "string", "승인 주체", nullable=False,
          allowed=APPROVAL_BODIES),
        C("owner_role", "text", "이행 책임", nullable=False),
        C("citation", "text", "근거 조항", nullable=False),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("action_id",),
)

MANAGEMENT_ACTION = TableSpec(
    name="st_management_action", korean="경영조치 발동 기록", product="PRD-ST",
    grain="시나리오 x 분기 x 조치 1건당 1행",
    columns=(
        C("record_id", "text", "발동 기록 식별자", nullable=False),
        C("scenario", "string", "시나리오", nullable=False),
        C("quarter", "string", "분기", nullable=False),
        C("action_id", "string", "조치 식별자", nullable=False),
        C("trigger_metric", "string", "발동 지표", nullable=False,
          allowed=METRICS),
        C("actual_value", "float", "실적 비율", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("trigger_level", "float", "발동 임계", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("shortfall_bp", "float", "임계 미달폭", nullable=True, unit="bp"),
        C("capital_effect_bp", "float", "반영 자본효과", nullable=True, unit="bp",
          note="효과 가정이 없으므로 NULL이며 자본경로에 반영하지 않는다"),
        C("status", "string", "판정", nullable=False, allowed=ACTION_STATUSES),
        C("reason", "text", "사유", nullable=False),
    ),
    primary_key=("record_id",),
    foreign_keys=(FK(("action_id",), "st_action_playbook", ("action_id",)),),
)

SPECS: tuple[TableSpec, ...] = (ACTION_PLAYBOOK, MANAGEMENT_ACTION)


# ---------------------------------------------------------------- 적재 표
#
# (조치ID, 발동지표, 임계 출처키, 임계 근거, 조치유형, 소요기간, 승인주체, 이행책임)
# 임계 출처키가 'required.<지표>'면 인자로 받은 규제 요구비율을 쓰고,
# None이면 내부 승인값이 없다는 뜻이라 NULL로 남는다.
_PLAYBOOK = (
    ("MA-01", "cet1_ratio", "cet1", "규제 요구 CET1 비율(자본 산출 원장에서 인용)",
     "배당 유보", 30, "이사회", "재무기획부"),
    ("MA-02", "cet1_ratio", None, "내부 조기경보 임계. 이사회 승인 원장 부재",
     "위험가중자산 감축", 90, "리스크관리위원회", "자본관리부"),
    ("MA-03", "tier1_ratio", "tier1", "규제 요구 Tier1 비율(자본 산출 원장에서 인용)",
     "자사주 매입 중단", 15, "경영위원회", "재무기획부"),
    ("MA-04", "total_ratio", "total", "규제 요구 총자본 비율(자본 산출 원장에서 인용)",
     "자본 확충", 180, "이사회", "재무기획부"),
    ("MA-05", "cet1_ratio", None, "내부 조기경보 임계. 이사회 승인 원장 부재",
     "비용 절감", 60, "경영위원회", "경영지원부"),
    ("MA-06", "cet1_ratio", None, "내부 조기경보 임계. 이사회 승인 원장 부재",
     "사업부문 축소", 270, "이사회", "전략기획부"),
)


# 발동표가 존재해야 하는 근거. 원문을 열람하고 옮긴 조항이다.
_USE_CITATION = ("[별표 19] 위기상황분석 실시기준 제7항 다 (개정 2022.1.27.) "
                 "위기상황분석 결과는 리스크성향 결정·익스포져 한도 설정·"
                 "자본관리계획(배당 등)·비상계획 수립에 활용되어야 한다")
# 완화 효과를 반영하려면 실현 가능한 가정이 있어야 한다는 근거.
MITIGATION_CITATION = ("[별표 19] 제26항 라 (시장리스크 절) 비상계획 등의 완화 "
                       "효과는 실현 가능한 가정에 기초할 때 고려한다")


def build_action_playbook(required: dict[str, float]) -> pd.DataFrame:
    """발동표를 만든다. 규제 임계는 인자로 받은 요구비율에서 온다.

    required는 자본 산출 결과의 요구비율 사전이며 키는 cet1·tier1·total이다.
    """
    rows = []
    for aid, metric, key, basis, action, lead, body, owner in _PLAYBOOK:
        level = None if key is None else required.get(key)
        rows.append({
            "action_id": aid, "trigger_metric": metric,
            "trigger_level": None if level is None else float(level),
            "trigger_basis": basis, "action_type": action,
            "capital_effect_bp": None, "lead_time_days": lead,
            "approval_body": body, "owner_role": owner,
            "citation": _USE_CITATION,
            # 조항은 원문으로 확인했다. 임계값 자체는 자본 산출 원장에서 인용하거나
            # (규제 요구비율) 승인 원장이 없어 비어 있다(내부 임계).
            "evidence_status": "미확인" if level is None else "원문확인",
        })
    return pd.DataFrame(rows, columns=[c.name for c in ACTION_PLAYBOOK.columns]
                        ).astype({"trigger_level": "float64",
                                  "capital_effect_bp": "float64"})


def evaluate_actions(playbook: pd.DataFrame, capital_path: pd.DataFrame
                     ) -> tuple[pd.DataFrame, list[str]]:
    """자본경로를 발동표와 대조한다. (발동 기록, 판정을 건너뛴 사유)를 돌려준다.

    임계가 NULL인 조치는 발동 여부를 판정하지 않는다. 판정하지 않았다는 행을
    남기는 이유는, 행이 없으면 '임계를 넘지 않았다'로 읽히기 때문이다.
    """
    skipped: list[str] = []
    rows = []
    for _, a in playbook.iterrows():
        aid, metric = str(a["action_id"]), str(a["trigger_metric"])
        level = a["trigger_level"]
        if pd.isna(level):
            worst = capital_path.loc[capital_path[metric].idxmin()]
            rows.append({
                "record_id": f"MAR-{aid}-판정불가",
                "scenario": str(worst["scenario"]), "quarter": str(worst["quarter"]),
                "action_id": aid, "trigger_metric": metric,
                "actual_value": float(worst[metric]), "trigger_level": None,
                "shortfall_bp": None, "capital_effect_bp": None,
                "status": "판정불가",
                "reason": f"발동 임계 미정 ({a['trigger_basis']})",
            })
            skipped.append(f"{aid}: 임계 NULL ({a['trigger_basis']})")
            continue
        hit = capital_path[capital_path[metric] < float(level)]
        if hit.empty:
            worst = capital_path.loc[capital_path[metric].idxmin()]
            rows.append({
                "record_id": f"MAR-{aid}-미발동",
                "scenario": str(worst["scenario"]), "quarter": str(worst["quarter"]),
                "action_id": aid, "trigger_metric": metric,
                "actual_value": float(worst[metric]),
                "trigger_level": float(level), "shortfall_bp": None,
                "capital_effect_bp": None, "status": "미발동",
                "reason": f"최저 {float(worst[metric]):.4f}가 임계 {float(level):.4f} 이상",
            })
            continue
        for _, r in hit.iterrows():
            shortfall = (float(level) - float(r[metric])) * 10_000
            rows.append({
                "record_id": f"MAR-{aid}-{r['scenario']}-{r['quarter']}",
                "scenario": str(r["scenario"]), "quarter": str(r["quarter"]),
                "action_id": aid, "trigger_metric": metric,
                "actual_value": float(r[metric]), "trigger_level": float(level),
                "shortfall_bp": round(shortfall, 2), "capital_effect_bp": None,
                "status": "발동",
                "reason": (f"{metric} {float(r[metric]):.4f} < 임계 "
                           f"{float(level):.4f}, 미달 {shortfall:.0f}bp. "
                           f"자본효과 가정이 없어 경로에 반영하지 않는다"),
            })
    frame = pd.DataFrame(rows, columns=[c.name for c in MANAGEMENT_ACTION.columns]
                         ).astype({"trigger_level": "float64",
                                   "shortfall_bp": "float64",
                                   "capital_effect_bp": "float64"})
    if len(frame) and frame["capital_effect_bp"].isna().all():
        skipped.append("조치별 자본 개선폭 가정이 없어 자본경로에 반영하지 않았다")
    return frame, skipped


def build_management_actions(capital_path: pd.DataFrame, required: dict[str, float]
                             ) -> tuple[dict[str, pd.DataFrame], list[str]]:
    """경영조치 원장 2장을 만든다. (원장, 건너뛴 사유)를 돌려준다."""
    playbook = build_action_playbook(required)
    actions, skipped = evaluate_actions(playbook, capital_path)
    return ({"st_action_playbook": playbook,
             "st_management_action": actions}, skipped)
