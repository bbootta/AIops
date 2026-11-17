"""Agent 등급별 위험 관리 (제품요건정의서 v0.94 4.13, HM-05~10).

Agent 위험(오작동, 오용, 통제 실패에서 생기는 손실 가능성)을 운영리스크의 하위
범주로 두고 감내수준 지표, 한도 계층, 위험가중 사용량, 타 리스크 전이 평가, 내부
관리 가산, 사후 검증으로 관리한다. 입력은 Agent 위험도 등급(`agent_tier`)과 실행
통제 쪽의 관측 기록이고, 계산은 전부 결정론이다.

설계 원칙

1. 규제자본은 바꾸지 않는다. 가산은 내부 관리 목적(내부자본 평가, 위기상황분석,
   한도 관리, 위험조정 성과 평가)에만 쓰고 규제 수치와 따로 싣는다. `aig_internal_addon`
   의 규제 위험가중자산 칸은 파이프라인 공표값 그대로다.
2. 위험량은 잔여 등급을 쓴다. 등급 미확정 단위는 최고 등급으로 본다. 통제 강도
   (승인, 차단장치 시작 단계)는 고유 등급을 쓴다.
3. 전이 평가는 사고가 났다는 전제의 조건부 크기다. 사고 발생 확률은 추정하지 않는다.
   크기는 AI 사고 시나리오 스트레스(`st_ai_impact`)의 값을 그대로 읽고 다시 계산하지
   않는다. 심도는 잔여 등급에 대응한다 (저 1, 중 2, 고 3).
4. 실행 통제와 양방향으로 잇는다. 등급 봉투, 차단장치, 한도, 승인, 사건 기록이 지표의
   입력이고, 한도 소진율과 감내수준 초과는 차단장치 조건 T2·T10 으로 되돌아간다
   (`aig_control_link`).
5. 수치 기본값은 없다. 가중치, 가산율, 임계치, 한도는 기관 설정이며 여기 있는 값은
   구조를 보이기 위한 예시 설정값이다 (`aig_tier_param`, 근거 상태 '재량·미규정').
   임계치가 비어 있는 지표는 '미설정'이라 적고 '범위 내'라 적지 않는다.
6. 같은 익스포저와 같은 사고 경로에는 가산을 한 가지만 쓴다 (큰 값). 운영리스크
   내부자본 가산은 시나리오의 1차 운영손실만 쓰고 신용 경로 몫은 (a)·(b)에 맡긴다.
7. 금액은 자기자본에 비례한다. 원화 절대액 상수를 두지 않는다. 기관마다 통화와
   규모가 달라 절대액으로는 견줄 수 없다.

**업무 Agent 포트폴리오는 합성 참조 자료다.** 이 저장소에는 업무 Agent 를 운영하는
실행 통제 계층이 없으므로, 등급과 관측 기록은 아래 고정 참조 포트폴리오에서 나온다.
난수를 쓰지 않아 실행마다 같다. 요건정의서의 적용 예시 여섯 건과 한도 예시를 그대로
재현하도록 골랐고, 실제 기관의 등급 분포나 통제 효과의 추정치로 쓸 수 없다.

**Agent 관여 익스포저도 합성 배정이다.** 심사 건 ID 로 잇는 실행 원장이 없어 익스포저
식별자의 지문으로 고정 비율을 고른다. 실제 연결이 붙으면 그 원장으로 바꿀 자리다.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd

from risk_lib.aig import agent_tier as tier
from risk_lib.aig.agent_tier import BANNED, HOLD, STAGES, TIERS, TierParams
from risk_lib.alm.params import EVIDENCE_STATUS
from risk_lib.capital.rwa_irb import compute_rwa_irb
from risk_lib.datamodel.spec import ColumnSpec as C, ForeignKey as FK, TableSpec

__all__ = [
    "RiskParams", "DEFAULT_RISK_PARAMS", "AgentUnit", "UNITS", "OBSERVATIONS",
    "INCIDENT_TYPES", "INVOLVEMENT", "AgentRiskResult", "run_agent_risk",
    "tier_inputs", "tier_assessments", "appetite_status", "RISK_SPECS", "SPECS",
    "CRITERIA_VERSION", "STATUS_UNSET", "STATUS_OK",
]

CRITERIA_VERSION = "RL-17 v0.94 (예시 설정값)"
SET_EXAMPLE = "예시 설정값 (기관 승인 전)"
SET_STRUCT = "구조 기본값"
SET_UNSET = "미설정"
_EV = "재량·미규정"
assert _EV in EVIDENCE_STATUS

STATUS_UNSET = "미설정"
STATUS_OK = "범위 내"
STATUS_LEVELS = ("조기경보 초과", "경영진 상향 기준 초과", "이사회 한도 초과")
DEPTH = {"저": 1, "중": 2, "고": 3}
SEVERITY_BY_DEPTH = {1: "baseline", 2: "adverse", 3: "severely_adverse"}
SELF_HOSTED = "자체 호스팅"

T2_SEVERITY = 1                  # 한도 소진율 임계 초과의 조건 심각도 (예시)
T10_INDICATORS = ("K2", "K3")    # 초과가 차단장치 조건 T10 으로 넘어가는 지표
T10_MAX_STAGE = 4                # T10 은 신규 한도 사용 행동의 보류까지다. 격리는 하지 않는다
TO_HEIMDALL = "RYNTA Bifrost → RYNTA Heimdall"
TO_BIFROST = "RYNTA Heimdall → RYNTA Bifrost"

ADDON_A = "(a) 내부 위험가중 가산"
ADDON_B = "(b) 자본 산출용 부도율 보수성 가산"
ADDON_APPLIED = "적용 (같은 익스포저는 큰 값)"
ADDON_C = "(c) 운영리스크 내부자본 가산"
ADDON_TOTAL = "합계"


# ---------------------------------------------------------------- 기관 설정 수치
@dataclass(frozen=True)
class RiskParams:
    """4.13 의 기관 설정 수치. 기본값은 전부 예시 설정값이다.

    None 은 미설정이다. 가중치가 비면 최고 가중치를 쓰고, 가산 계수가 비면 그 가산을
    산출하지 않으며, 임계치가 비면 지표 상태를 '미설정'으로 둔다.
    """
    risk_weight: dict = field(default_factory=lambda: {"저": 1.0, "중": 1.5, "고": 2.5})
    addon_rate: float | None = 0.05
    addon_mult: dict = field(default_factory=lambda: {"저": 0.0, "중": 1.0, "고": 2.0})
    pd_addon: dict | None = field(
        default_factory=lambda: {"저": 0.0, "중": 0.10, "고": 0.20})
    capital_factor: float = 0.08
    loss_tolerance_bp: float | None = 2.0          # 연간 사고 손실 감내 한도 (자기자본 대비)
    tier_cap_bp: dict = field(default_factory=lambda: {"저": 180.0, "중": 70.0, "고": 20.0})
    t2_utilisation: float | None = 0.85            # 한도 소진율 임계 (차단장치 조건 T2)
    min_incidents: int = 30                        # 이보다 적으면 사건율 결론을 유보한다
    thresholds: dict = field(default_factory=lambda: {
        "K1": (0.25, 0.35, 0.45), "K2": (0.025, 0.030, 0.035),
        "K3": (0.50, 0.75, 1.00), "K4": (0.0, 0.0, 0.0),
        "K5-1": (0.0005, 0.0010, 0.0020), "K5-2": (1.0, 3.0, 5.0),
        "K6": (0.10, 0.20, 0.30), "K7": (0.50, 0.65, 0.80),
        "K8-1": None, "K8-2": None,
        "K9-1": (0.15, 0.25, 0.35), "K9-2": (0.40, 0.55, 0.70)})

    def weight(self, t: str) -> float:
        """등급별 위험가중치. 그 등급의 값이 없으면 설정된 값 가운데 최고를 쓴다."""
        w = self.risk_weight.get(t)
        if w is not None:
            return float(w)
        known = [v for v in self.risk_weight.values() if v is not None]
        return float(max(known)) if known else float("nan")


DEFAULT_RISK_PARAMS = RiskParams()


# ---------------------------------------------------------------- 참조 포트폴리오
_Levels = tuple[tuple, tuple]


@dataclass(frozen=True)
class AgentUnit:
    unit_id: str
    name: str
    use_case: str
    planned: _Levels | None = None        # 예정: 기획서 선언 (A1~A4, B1~B4)
    confirmed: _Levels | None = None      # 확정: 비우면 예정과 같다
    observed: _Levels | None = None       # 운영: 비우면 확정과 같다. 칸이 None 이면 관측 결손
    unit_type: str = "Agent"
    parent: str | None = None
    provider: str = SELF_HOSTED
    model_id: str = "SLM-INT-01"
    credit_role: bool = False             # 신용평가·심사 보조
    f1: bool = False
    f3: bool = False
    banned: tuple[str, ...] = ()
    controls: tuple[bool, bool, bool] = (False, False, False)
    dual_approval: bool = False
    limit_bp: float | None = None         # 일 누적 금액 한도 (자기자본 대비 bp)
    per_action_bp: float | None = None    # 건당 금액 한도
    used_share: float = 0.0               # 한도 소진율
    limit_count: int = 0                  # 일 건수 한도 (비금액 행동)
    status: str = "운영 중"


_A, _B = "공급자 A", "공급자 B"
_MA, _MB = "LLM-A-2026-05", "LLM-B-2026-03"
_OK3 = (True, True, True)

UNITS: tuple[AgentUnit, ...] = (
    AgentUnit("AGT-0102", "사내 규정 질의", "내부 규정 문서 조회와 답변 초안",
              ((1, 1, 1, 1), (1, 2, 1, 2)), provider=_B, model_id=_MB, limit_count=2000),
    AgentUnit("AGT-0233", "투자광고 문구 점검", "심의 의견 초안, 확정은 준법감시 담당자",
              ((2, 1, 2, 2), (2, 2, 1, 2)), provider=_A, model_id=_MA,
              controls=_OK3, dual_approval=True, limit_count=300),
    AgentUnit("AGT-0305", "시장 조사 자동화", "외부 웹 수집과 조사 보고서 초안",
              ((2, 1, 2, 1), (2, 3, 2, 2)), confirmed=((2, 1, 2, 1), (3, 3, 2, 2)),
              provider=_A, model_id=_MA, controls=_OK3, dual_approval=True,
              limit_count=500),
    AgentUnit("AGT-0417", "고객 환불 처리", "고객 이메일 접수, 고객 정보 조회, 환불 실행",
              ((3, 3, 3, 2), (2, 3, 2, 2)), provider=_A, model_id=_MA,
              controls=_OK3, dual_approval=True, limit_bp=5.0, per_action_bp=0.5,
              used_share=0.54, limit_count=200),
    AgentUnit("SYS-0009", "신용 이벤트 대응", "접수, 조회, 실행 Agent 의 위임 구성",
              unit_type="Agent 시스템", provider=_A, model_id=_MA, controls=_OK3,
              limit_bp=10.0, per_action_bp=2.0, used_share=0.40, limit_count=100),
    AgentUnit("AGT-0911", "신용 이벤트 접수", "외부 이메일 수신과 분류",
              ((1, 1, 1, 1), (1, 3, 1, 2)), parent="SYS-0009", provider=_A, model_id=_MA),
    AgentUnit("AGT-0912", "고객 정보 조회", "고객 정보와 거래 내역 조회",
              ((2, 1, 3, 2), (2, 1, 1, 2)), parent="SYS-0009", provider=_A, model_id=_MA),
    AgentUnit("AGT-0913", "주문·환불 실행", "승인된 주문과 환불의 실행",
              ((3, 3, 2, 2), (1, 1, 1, 2)), parent="SYS-0009", provider=_A, model_id=_MA),
    AgentUnit("AGT-0521", "여신 심사 보조", "개인 여신 심사 의견 초안, 확정은 심사역",
              ((3, 1, 3, 2), (2, 2, 2, 2)), provider=_B, model_id=_MB, credit_role=True,
              f1=True, controls=_OK3, limit_count=400),
    AgentUnit("AGT-0522", "기업 신용평가 보조", "기업 신용평가 의견 초안, 확정은 평가역",
              ((3, 1, 2, 2), (2, 2, 2, 2)), provider=_B, model_id=_MB, credit_role=True,
              controls=_OK3, dual_approval=True, limit_count=150),
    AgentUnit("AGT-0610", "자금 이체 대사", "이체 내역 대사와 불일치 정정",
              ((2, 2, 2, 2), (2, 1, 2, 1)), observed=((2, 3, 2, 2), (2, 1, 2, 1)),
              controls=_OK3, limit_bp=25.0, per_action_bp=5.0, used_share=0.88,
              limit_count=600),
    AgentUnit("AGT-0641", "내부 계정 간 자금 대체", "승인된 내부 계정 대체 실행",
              ((2, 2, 2, 2), (1, 1, 1, 1)), limit_bp=100.0, per_action_bp=10.0,
              used_share=0.62, limit_count=1500),
    AgentUnit("AGT-0642", "지급 스케줄 등록", "지급 일정 등록과 변경",
              ((2, 2, 2, 2), (1, 1, 2, 1)), limit_bp=50.0, per_action_bp=5.0,
              used_share=0.48, limit_count=800),
    AgentUnit("AGT-0650", "수수료 환급 정산", "수수료 환급 내역 산정과 내부 정산",
              ((2, 2, 2, 2), (2, 2, 2, 1)), controls=(True, True, False),
              limit_bp=20.0, per_action_bp=2.0, used_share=0.71, limit_count=400),
    AgentUnit("AGT-0660", "외화 송금 사전 점검", "송금 서류 사전 점검과 내부 전송",
              ((2, 2, 3, 2), (2, 2, 1, 2)), provider=_A, model_id=_MA,
              controls=(True, True, False), limit_bp=15.0, per_action_bp=3.0,
              used_share=0.35, limit_count=250),
    AgentUnit("AGT-0705", "이상거래 탐지 보조", "이상거래 후보 요약과 담당자 통지",
              ((2, 1, 3, 2), (2, 1, 2, 2)), provider=_B, model_id=_MB,
              controls=(True, True, False), limit_count=3000),
    AgentUnit("AGT-0811", "고객 상담 요약", "상담 기록 요약과 후속 조치 초안",
              ((2, 1, 3, 2), (1, 2, 1, 2)), provider=_A, model_id=_MA, limit_count=2500),
    AgentUnit("AGT-1004", "문서 분류", "내부 문서 분류와 보존 기간 표시",
              ((1, 1, 2, 1), (1, 2, 1, 1)), observed=((1, 1, 2, 1), (1, 2, 1, None)),
              limit_count=2000),
    AgentUnit("INT-2026-0027", "여신 승인 자동 확정 설계", "여신 승인을 사람 확정 없이 확정하는 설계안",
              ((3, 3, 3, 3), (3, 2, 2, 2)), unit_type="설계안", banned=("X1",),
              status="접수 반려"),
)
_UNIT = {u.unit_id: u for u in UNITS}

# 관측 기록 요약 (집계 단위별, 당해 연도 누계). 순서:
# 실행, 효과 행동, 봉투 이탈 시도, 차단장치 4·5단계 발동, 사건, 중대 사건,
# 사고 손실(자기자본 대비 bp), 승인, 무수정 승인, 점검 기한 경과, 긴급정지 소요(초), 탐지 소요(시간)
OBSERVATIONS: dict[str, tuple] = {
    "AGT-0102": (48200, 0, 0, 0, 0, 0, 0.00, 0, 0, False, 20, 24),
    "AGT-0233": (6400, 0, 2, 0, 0, 0, 0.00, 310, 262, False, 20, 24),
    "AGT-0305": (9100, 0, 14, 1, 1, 0, 0.05, 120, 96, False, 45, 12),
    "AGT-0417": (3250, 2980, 6, 0, 1, 0, 0.20, 5960, 5480, False, 8, 4),
    "SYS-0009": (1840, 1210, 9, 1, 1, 0, 0.35, 2420, 2105, False, 15, 4),
    "AGT-0521": (12600, 0, 3, 0, 0, 0, 0.00, 1260, 1134, False, 20, 8),
    "AGT-0522": (2150, 0, 1, 0, 0, 0, 0.00, 430, 365, False, 20, 8),
    "AGT-0610": (7300, 640, 11, 0, 1, 0, 0.30, 640, 589, False, 42, 6),
    "AGT-0641": (15800, 15800, 0, 0, 0, 0, 0.00, 158, 150, False, 10, 6),
    "AGT-0642": (4900, 4900, 1, 0, 0, 0, 0.00, 49, 44, False, 10, 6),
    "AGT-0650": (2700, 2700, 2, 0, 0, 0, 0.00, 810, 713, False, 12, 6),
    "AGT-0660": (1950, 0, 0, 0, 0, 0, 0.00, 390, 312, False, 18, 8),
    "AGT-0705": (31000, 0, 4, 0, 0, 0, 0.00, 620, 558, True, 25, 2),
    "AGT-0811": (22400, 0, 0, 0, 0, 0, 0.00, 0, 0, False, 20, 24),
    "AGT-1004": (18300, 0, 5, 0, 0, 0, 0.00, 0, 0, False, 20, 24),
}
OBS_BUSINESS_DAYS = 120       # 관측 기간 영업일수
OBS_APPROVERS = 8             # 승인자 수

# Agent 관여 익스포저의 합성 배정: 단위 → (자산군, 지문 백분위 상한)
INVOLVEMENT: dict[str, tuple[tuple[str, ...], int]] = {
    "AGT-0521": (("residential_mortgage", "retail_other"), 20),
    "AGT-0522": (("corporate",), 15),
}

# 사고 유형 7종: (순번, 시나리오, 이름, 1차 손실, 전이 경로, 적용 대상, 통제 연결 모수)
INCIDENT_TYPES: tuple[tuple[int, str, str, str, str, str, str], ...] = (
    (1, "AI-01", "권한 초과 실행", "오실행 손실 / 제재", "유동성: 자금 이탈",
     "효과 행동(주문, 이체) 보유", "차단 지연 시간 / 건당·일 누적 한도"),
    (2, "AI-02", "모형 공통 실패", "재산출·정정 비용",
     "신용: 부도율·손실률 가산 / 자본: 표준방법 회귀",
     "신용평가·심사 보조", "독립 재계산 범위 / 탐지 소요 시간"),
    (3, "AI-03", "개인신용정보 유출", "과징금, 고객 배상",
     "수익: 영업 중단 / 유동성: 예수금 이탈 / 평판",
     "정보 등급 상위 접근(A3 수준 3)", "정보 등급 상한 / 반출 통제"),
    (4, "AI-04", "소비자 피해", "환급, 제재", "자본: 표준방법 회귀 / 평판, 법률",
     "고영향 영역 연결(F1)", "사람 확정 단계 / 표본 점검"),
    (5, "AI-05", "외부 공급자 장애", "복구·보상 비용, 제재",
     "수익: 수수료 감소 / 유동성: 자금 이탈",
     "외부 모델·제3자 의존(B4 수준 2 이상)", "공급자 집중도 / 비상 계획"),
    (6, "AI-06", "공급망 공통모델 실패", "사기 손실, 무과실 책임 / 운영비 증가",
     "신용: 손실 증가", "공통 모델·도구 사용", "모델 판본 통제 / 변경 재검증"),
    (7, "AI-07", "증빙 손상", "재검증·재작성 비용", "자본: 자본 산출용 부도율 가산",
     "전체 Agent", "원장 무결성 검증 주기"),
)


# ---------------------------------------------------------------- 등급 산정 (원장)
def _stage_levels(u: AgentUnit, stage: str) -> _Levels | None:
    conf = u.confirmed or u.planned
    return {"예정": u.planned, "확정": conf, "운영": u.observed or conf}[stage]


def _members(system_id: str) -> list[AgentUnit]:
    return [u for u in UNITS if u.parent == system_id]


def tier_inputs() -> pd.DataFrame:
    """항목 수준 입력. Agent 시스템 행은 구성원 행의 합집합으로 낸다."""
    rows = []
    for u in UNITS:
        for stage in STAGES:
            if u.unit_type == "설계안" and stage != "예정":
                continue
            derived = u.unit_type == "Agent 시스템"
            if derived:
                a, b = tier.union_levels([_stage_levels(m, stage) for m in _members(u.unit_id)])
                f1 = any(m.f1 for m in _members(u.unit_id)) or u.f1
                f3 = any(m.f3 for m in _members(u.unit_id)) or u.f3
            else:
                a, b = _stage_levels(u, stage)
                f1, f3 = u.f1, u.f3
            evidenced = stage != "예정"         # 통제 증거와 하향 승인은 확정 시점부터
            c = u.controls if evidenced else (False, False, False)
            rows.append({
                "unit_id": u.unit_id, "stage": stage,
                "input_source": tier.STAGE_SOURCE[stage],
                **{f"a{k + 1}": a[k] for k in range(4)},
                **{f"b{k + 1}": b[k] for k in range(4)},
                "f1_high_impact": bool(f1), "f3_no_per_action_approval": bool(f3),
                "x1_auto_decision": "X1" in u.banned,
                "x2_core_judgment_l5": "X2" in u.banned,
                "x3_prohibited_use": "X3" in u.banned,
                "c1_prevent": c[0], "c2_detect": c[1], "c3_stop_recover": c[2],
                "dual_approval": bool(u.dual_approval and evidenced),
                "derived_from_members": derived})
    df = pd.DataFrame(rows)
    for col in ("a1", "a2", "a3", "a4", "b1", "b2", "b3", "b4"):
        df[col] = df[col].astype("Int64")
    return df


_A_COLS, _B_COLS = ("a1", "a2", "a3", "a4"), ("b1", "b2", "b3", "b4")
_X_COLS = (("x1_auto_decision", "X1"), ("x2_core_judgment_l5", "X2"),
           ("x3_prohibited_use", "X3"))


def _row_levels(r) -> tuple[tuple, tuple]:
    def get(cols):
        return tuple(None if pd.isna(r[c]) else int(r[c]) for c in cols)
    return get(_A_COLS), get(_B_COLS)


def assess_row(r, params: TierParams = tier.DEFAULT_PARAMS) -> tier.TierOutcome:
    """입력 원장 한 행에서 등급을 낸다. 자체검증도 이 함수로 다시 계산한다."""
    a, b = _row_levels(r)
    banned = tuple(x for col, x in _X_COLS if bool(r[col]))
    complete = all(v is not None for v in a + b)
    fixed = (tier.fixed_flags(a, b, f1=bool(r["f1_high_impact"]),
                              f3=bool(r["f3_no_per_action_approval"]))
             if complete else ())
    return tier.assess(a, b, fixed=fixed, banned=banned,
                       controls=(bool(r["c1_prevent"]), bool(r["c2_detect"]),
                                 bool(r["c3_stop_recover"])),
                       approved=bool(r["dual_approval"]), params=params)


def tier_assessments(inputs: pd.DataFrame,
                     params: TierParams = tier.DEFAULT_PARAMS) -> pd.DataFrame:
    rows = []
    for r in inputs.to_dict("records"):
        o = assess_row(r, params)
        quantity = ("고" if o.residual == HOLD
                    else None if o.residual == BANNED else o.residual)
        rows.append({
            "unit_id": r["unit_id"], "stage": r["stage"],
            "impact_base": o.impact_base, "scale_add": o.scale_add,
            "impact_level": o.impact, "exposure_score": o.score,
            "exposure_level": o.exposure, "matrix_tier": o.matrix_tier,
            "fixed_flags": "·".join(o.fixed) or None,
            "banned_flags": "·".join(o.banned) or None,
            "hold_reason": o.hold, "inherent_tier": o.inherent,
            "controls_met": bool(r["c1_prevent"] and r["c2_detect"]
                                 and r["c3_stop_recover"]),
            "downgraded": o.downgraded, "residual_tier": o.residual,
            "quantity_tier": quantity,
            "decision_route": tier.ROUTE[o.inherent],
            "breaker_add": tier.BREAKER_ADD.get(o.inherent),
            "near_boundary": tier.near_boundary(o.score, params),
            "criteria_version": CRITERIA_VERSION})
    df = pd.DataFrame(rows)
    for col in ("impact_base", "scale_add", "impact_level", "exposure_score",
                "exposure_level", "breaker_add"):
        df[col] = df[col].astype("Int64")
    return df


def _unit_frame() -> pd.DataFrame:
    return pd.DataFrame([{
        "unit_id": u.unit_id, "unit_name": u.name, "unit_type": u.unit_type,
        "parent_unit_id": u.parent, "use_case": u.use_case,
        "model_provider": u.provider, "model_id": u.model_id,
        "credit_model_role": u.credit_role, "status": u.status,
        "counted": _counted(u), "data_origin": "합성 참조 포트폴리오",
    } for u in UNITS])


def _counted(u: AgentUnit) -> bool:
    """집계 단위인가. 단독 Agent 와 Agent 시스템을 세고 시스템 구성원은 시스템에 포함한다.

    구성원을 따로 세면 업무를 여러 Agent 로 나눌수록 고 등급 비중이 낮아진다.
    """
    return u.status == "운영 중" and u.parent is None and u.unit_type != "설계안"


def _envelope(inputs: pd.DataFrame) -> pd.DataFrame:
    by = {(r["unit_id"], r["stage"]): r for r in inputs.to_dict("records")}
    rows = []
    for u in UNITS:
        if u.unit_type == "설계안":
            continue
        for code in tier.ITEM_CODES:
            col = code.lower()
            d, c, o = (by[(u.unit_id, s)][col] for s in STAGES)
            d, c, o = (None if pd.isna(v) else int(v) for v in (d, c, o))
            gap = ("대사 불가" if d is None or c is None else "일치" if d == c
                   else "실측 상향" if c > d else "실측 하향")
            rows.append({
                "unit_id": u.unit_id, "item_code": code,
                "envelope_dimension": tier.ENVELOPE_DIMENSION[code],
                "declared_level": d, "confirmed_level": c, "observed_level": o,
                "declared_gap": gap,
                "envelope_breach": bool(o is not None and c is not None and o > c),
                "observation_missing": o is None})
    df = pd.DataFrame(rows)
    for col in ("declared_level", "confirmed_level", "observed_level"):
        df[col] = df[col].astype("Int64")
    return df


def _migration(q_conf: dict[str, str], q_oper: dict[str, str]) -> pd.DataFrame:
    """확정 등급에서 운영 등급으로의 이동. 운영이 미확정이면 '보류'로 따로 센다."""
    rows = []
    for a in TIERS:
        for b in TIERS + (HOLD,):
            ids = sorted(k for k in q_conf if q_conf[k] == a and q_oper[k] == b)
            direction = ("보류" if b == HOLD else "유지" if a == b
                         else "상향" if DEPTH[b] > DEPTH[a] else "하향")
            rows.append({"from_tier": a, "to_tier": b, "n_units": len(ids),
                         "direction": direction,
                         "unit_ids": ", ".join(ids) or None})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- 4.13 산출
def appetite_status(value: float | None, thr: tuple | None) -> tuple[str, int | None]:
    """지표 상태와 초과 단계(0~3). 임계치가 하나라도 비면 '미설정'이다."""
    if value is None or thr is None or any(t is None for t in thr):
        return STATUS_UNSET, None
    level = sum(1 for t in thr if value > t)
    return (STATUS_OK if level == 0 else STATUS_LEVELS[level - 1]), level


def _bucket(exposure_id: object) -> int:
    """익스포저 식별자의 지문 백분위. 내장 hash() 는 실행마다 달라 쓰지 않는다."""
    return int(hashlib.sha256(str(exposure_id).encode("utf-8")).hexdigest()[:8], 16) % 100


@dataclass
class AgentRiskResult:
    frames: dict[str, pd.DataFrame]
    headline: dict[str, float | None]
    capital_total: float
    rwa_regulatory: float
    institution_code: str = ""

    def tables(self) -> dict[str, pd.DataFrame]:
        return dict(self.frames)


def run_agent_risk(*, capital_total: float, rwa_regulatory: float,
                   irb_results: pd.DataFrame, ai_impact: pd.DataFrame | None,
                   ai_base: dict | None, bi: float, institution_code: str = "",
                   tier_params: TierParams = tier.DEFAULT_PARAMS,
                   params: RiskParams = DEFAULT_RISK_PARAMS) -> AgentRiskResult:
    """등급 원장 7장과 위험 관리 원장 11장을 낸다.

    `capital_total` 은 규제 총자본(자기자본), `rwa_regulatory` 는 공표 위험가중자산
    합계, `irb_results` 는 내부등급법 익스포저별 산출 결과, `ai_impact`·`ai_base` 는
    AI 사고 시나리오 스트레스의 영향 요약과 기준점, `bi` 는 영업지표다.
    """
    cap = float(capital_total)

    def amt(bp: float | None) -> float | None:
        return None if bp is None else float(bp) * cap / 1e4

    inputs = tier_inputs()
    assess = tier_assessments(inputs, tier_params)
    units = _unit_frame()
    envelope = _envelope(inputs)
    counted = [u for u in UNITS if _counted(u)]
    ids = [u.unit_id for u in counted]
    at = {(r["unit_id"], r["stage"]): r for r in assess.to_dict("records")}
    q_conf = {i: at[(i, "확정")]["residual_tier"] for i in ids}
    q_oper = {i: at[(i, "운영")]["residual_tier"] for i in ids}
    q_use = {i: at[(i, "운영")]["quantity_tier"] for i in ids}      # 미확정은 고
    migration = _migration(q_conf, q_oper)

    # ---- 관측 기록
    obs_rows = []
    for i in ids:
        (ex, eff, brc, brk, inc, major, loss_bp, appr, unmod, overdue,
         stop_s, detect_h) = OBSERVATIONS[i]
        obs_rows.append({
            "unit_id": i, "executions": ex, "effect_actions": eff,
            "envelope_breach_attempts": brc, "breaker_stage45": brk,
            "incidents": inc, "major_incidents": major,
            "incident_loss": amt(loss_bp), "approvals": appr,
            "approvals_unmodified": unmod, "check_overdue": bool(overdue),
            "stop_seconds": float(stop_s), "detect_hours": float(detect_h),
            "data_origin": "합성 참조 포트폴리오"})
    obs = pd.DataFrame(obs_rows)

    # ---- 한도 (계층 3·4)와 위험가중 사용량
    lim_rows = []
    for u in counted:
        t_use = q_use[u.unit_id]
        w = params.weight(t_use)
        limit = amt(u.limit_bp)
        used = None if limit is None else limit * u.used_share
        t2 = bool(limit is not None and params.t2_utilisation is not None
                  and u.used_share > params.t2_utilisation)
        inh = at[(u.unit_id, "운영")]["inherent_tier"]
        lim_rows.append({
            "unit_id": u.unit_id, "confirmed_tier": q_conf[u.unit_id],
            "quantity_tier": t_use, "risk_weight": w,
            "limit_amount": limit, "per_action_limit": amt(u.per_action_bp),
            "limit_count": int(u.limit_count), "used_amount": used,
            "utilisation": None if limit is None else float(u.used_share),
            "weighted_granted": None if limit is None else limit * w,
            "weighted_used": None if used is None else used * w,
            "t2_triggered": t2,
            "t2_start_stage": tier.breaker_start(T2_SEVERITY, inh) if t2 else None,
            "new_limit_hold": q_oper[u.unit_id] == HOLD})
    limits = pd.DataFrame(lim_rows)

    usage_rows = []
    totals: dict[tuple[str, str], float] = {}
    for basis, qmap in (("확정 등급", {i: q_conf[i] for i in ids}),
                        ("운영 등급", q_use)):
        for amount_basis, share in (("부여 한도", None), ("실제 사용", "used")):
            total = 0.0
            for t in TIERS:
                a = sum((amt(u.limit_bp) or 0.0) * (u.used_share if share else 1.0)
                        for u in counted if qmap[u.unit_id] == t)
                w = params.weight(t)
                usage_rows.append({"tier_basis": basis, "amount_basis": amount_basis,
                                   "tier": t, "amount": a, "risk_weight": w,
                                   "weighted_amount": a * w,
                                   "ratio_to_capital": a * w / cap})
                total += a * w
            raw = sum((amt(u.limit_bp) or 0.0) * (u.used_share if share else 1.0)
                      for u in counted)
            usage_rows.append({"tier_basis": basis, "amount_basis": amount_basis,
                               "tier": "합계", "amount": raw, "risk_weight": None,
                               "weighted_amount": total,
                               "ratio_to_capital": total / cap})
            totals[(basis, amount_basis)] = total
    usage = pd.DataFrame(usage_rows)
    u_granted = totals[("운영 등급", "부여 한도")]
    u_used = totals[("운영 등급", "실제 사용")]

    # ---- 한도 계층 (계층 1·2 점검과 3·4 요약)
    k2_thr = params.thresholds.get("K2")
    board = None if k2_thr is None or k2_thr[2] is None else k2_thr[2] * cap
    layer_rows = [{
        "layer": 1, "scope": "전사", "content": "전체 Agent 위험가중 금액의 상한",
        "approver": "이사회 또는 위임받은 위원회",
        "enforcement": "RYNTA Heimdall 총량 점검", "weighted": True,
        "limit_amount": board, "granted_amount": u_granted, "used_amount": u_used,
        "utilisation": None if not board else u_granted / board,
        "excess_amount": None if board is None else max(0.0, u_granted - board),
        "status": (STATUS_UNSET if board is None
                   else "한도 초과" if u_granted > board else "한도 내"),
        "requirement_refs": "HM-06 · HM-07"}]
    for t in TIERS:
        capv = amt(params.tier_cap_bp.get(t))
        granted = sum(amt(u.limit_bp) or 0.0 for u in counted if q_use[u.unit_id] == t)
        used = sum((amt(u.limit_bp) or 0.0) * u.used_share
                   for u in counted if q_use[u.unit_id] == t)
        layer_rows.append({
            "layer": 2, "scope": t, "content": "등급별 부여 한도 합계의 상한",
            "approver": "위험관리 책임 조직",
            "enforcement": "RYNTA Heimdall 부여 시 점검", "weighted": False,
            "limit_amount": capv, "granted_amount": granted, "used_amount": used,
            "utilisation": None if not capv else granted / capv,
            "excess_amount": None if capv is None else max(0.0, granted - capv),
            "status": (STATUS_UNSET if capv is None
                       else "조정 대상" if granted > capv else "한도 내"),
            "requirement_refs": "HM-07"})
    with_limit = limits[limits["limit_amount"].notna()]
    over3 = int((with_limit["used_amount"] > with_limit["limit_amount"]).sum())
    over4 = int((with_limit["per_action_limit"] > with_limit["limit_amount"]).sum())
    # 계층 3·4 는 실행 통제 계층이 집행한다. 여기서는 합계와 위반 여부만 싣는다.
    # 건당 한도의 합은 뜻이 없어 계층 4 의 금액 칸은 비운다.
    for layer, scope, content, approver, enforcement, granted, used, n_over, refs in (
            (3, "Agent별", "Agent별 일 누적 금액, 건수, 대상 수",
             "등급별 승인 권한", "RYNTA Bifrost 예약·누적",
             float(with_limit["limit_amount"].sum()),
             float(with_limit["used_amount"].sum()), over3, "CP-MSR-16 · HM-07"),
            (4, "건당", "행동 1건의 금액, 대상 수", "등급 봉투 (운영 승인 시 확정)",
             "RYNTA Bifrost 건별 판정", None, None, over4, "CP-VRF-48 · CP-MSR-16")):
        layer_rows.append({
            "layer": layer, "scope": scope, "content": content, "approver": approver,
            "enforcement": enforcement, "weighted": False, "limit_amount": None,
            "granted_amount": granted, "used_amount": used,
            "utilisation": None, "excess_amount": None,
            "status": "한도 초과" if n_over else "한도 내", "requirement_refs": refs})
    layers = pd.DataFrame(layer_rows)
    for col in ("limit_amount", "granted_amount", "used_amount", "utilisation",
                "excess_amount"):
        layers[col] = layers[col].astype("float64")

    # ---- 감내수준 지표 K1~K9
    n = len(ids)
    conf_rows = [at[(i, "확정")] for i in ids]
    mid_high = [i for i in ids if q_use[i] in ("중", "고")]
    by_provider: dict[str, int] = {}
    for i in mid_high:
        p = _UNIT[i].provider
        if p != SELF_HOSTED:
            by_provider[p] = by_provider.get(p, 0) + 1
    loss_total = float(obs["incident_loss"].sum())
    loss_limit = amt(params.loss_tolerance_bp)
    approvals = int(obs["approvals"].sum())
    executions = int(obs["executions"].sum())
    k_def = (
        ("K1", 1, "고 등급 Agent 비중", "운영 중 고 등급(잔여) Agent 수 ÷ 운영 중 전체 Agent 수",
         sum(1 for i in ids if q_use[i] == "고"), n, "비율",
         "Agent 등급 (aig_tier_assessment)", "신규 고 등급 운영 승인의 심사 강화"),
        ("K2", 1, "위험가중 한도 사용률", "위험가중 사용량(부여 한도 기준) ÷ 자기자본",
         u_granted, cap, "비율", "한도 원장, Agent 등급 (aig_agent_limit)",
         "한도 상향 보류 / 차단장치 조건 T10"),
        ("K3", 1, "사고 손실 사용률", "당해 연도 Agent 사고 손실 누계 ÷ 연간 감내 한도",
         loss_total, loss_limit, "비율", "사건·조치 기록 (aig_agent_observation)",
         "상향보고와 조치 계획 / 차단장치 조건 T10"),
        ("K4", 1, "중대 사건 건수", "기간 중 중대 Agent 사건 건수 (한도 0건)",
         int(obs["major_incidents"].sum()), None, "건",
         "사건 기록 (aig_agent_observation)", "즉시 상향보고 / 해당 Agent 의 격리 검토"),
        ("K5", 1, "통제 이탈 지표: 봉투 이탈 시도율", "봉투 이탈 시도 건수 ÷ 실행 건수",
         int(obs["envelope_breach_attempts"].sum()), executions, "비율",
         "봉투 집행 기록 (aig_agent_observation)", "재등급 대상 지정"),
        ("K5", 2, "통제 이탈 지표: 차단장치 4·5단계 발동", "차단장치 4·5단계 발동 건수",
         int(obs["breaker_stage45"].sum()), None, "건",
         "차단장치 기록 (aig_agent_observation)", "재등급 대상 지정"),
        ("K6", 1, "검증·점검 미이행 비율",
         "독립검증 미완료 또는 점검 기한 경과 Agent 수 ÷ 대상 Agent 수",
         int(obs["check_overdue"].sum()), n, "비율",
         "통제 요건, 점검 일정 (aig_agent_observation)", "상위 책임자 상향 / 운영 승인 보류"),
        ("K7", 1, "모델 공급자 집중도",
         "최대 단일 공급자에 의존하는 중·고 등급 Agent 수 ÷ 중·고 등급 Agent 수",
         max(by_provider.values()) if by_provider else 0, len(mid_high), "비율",
         "모델 등록 (aig_agent_unit)", "공급자 장애 시나리오 재평가"),
        ("K8", 1, "승인 부하: 승인자 1인당 일 승인 건수", "승인 건수 ÷ (승인자 수 × 영업일수)",
         approvals, OBS_APPROVERS * OBS_BUSINESS_DAYS, "건",
         "승인 기록 (aig_agent_observation)", "승인 체계 보강 조치 요구"),
        ("K8", 2, "승인 부하: 무수정 승인 비율", "무수정 승인 건수 ÷ 승인 건수",
         int(obs["approvals_unmodified"].sum()), approvals, "비율",
         "승인 기록 (aig_agent_observation)", "승인 체계 보강 조치 요구"),
        ("K9", 1, "등급 조정 지표: 하향 비율", "등급 하향 건수 ÷ 등급 확정 건수",
         sum(1 for r in conf_rows if r["downgraded"]), n, "비율",
         "등급 확정 기록 (aig_tier_assessment)", "독립 재확인 표본 확대"),
        ("K9", 2, "등급 조정 지표: 경계 근처 비중", "경계 근처 건수 ÷ 전체 건수",
         sum(1 for r in conf_rows if r["near_boundary"]), n, "비율",
         "등급 확정 기록 (aig_tier_assessment)", "독립 재확인 표본 확대"),
    )
    multi = {"K5", "K8", "K9"}
    app_rows = []
    for kid, seq, name, definition, num, den, unit, source, on_breach in k_def:
        key = f"{kid}-{seq}" if kid in multi else kid
        thr = params.thresholds.get(key)
        if den is None:
            value = float(num)
        elif not den:
            value = None                      # 분모가 없으면 값을 만들지 않는다
        else:
            value = float(num) / float(den)
        status, level = appetite_status(value, thr)
        app_rows.append({
            "indicator_id": kid, "measure_seq": seq, "indicator_name": name,
            "definition": definition, "numerator": float(num),
            "denominator": None if den is None else float(den), "value": value,
            "value_unit": unit,
            "threshold_early": None if thr is None else thr[0],
            "threshold_mgmt": None if thr is None else thr[1],
            "threshold_board": None if thr is None else thr[2],
            "status": status, "breach_level": level,
            "threshold_setting": SET_UNSET if status == STATUS_UNSET else SET_EXAMPLE,
            "input_source": source, "on_breach": on_breach})
    appetite = pd.DataFrame(app_rows)
    appetite["breach_level"] = appetite["breach_level"].astype("Int64")

    # ---- 차단장치 조건 T10: 한도 지표(K2·K3)의 초과 단계가 조건 심각도로 넘어간다.
    # 그 한도를 쓰는 단위 전체에 적용하고 격리(5단계)까지는 가지 않는다.
    t10_severity = max((r["breach_level"] or 0) for r in app_rows
                       if r["indicator_id"] in T10_INDICATORS)
    t10, applied_stage = [], []
    for r in lim_rows:
        inh = at[(r["unit_id"], "운영")]["inherent_tier"]
        s10 = (min(T10_MAX_STAGE, tier.breaker_start(t10_severity, inh))
               if t10_severity and r["limit_amount"] is not None else None)
        t10.append(s10)
        both = [x for x in (r["t2_start_stage"], s10) if x is not None]
        applied_stage.append(max(both) if both else None)   # 여러 조건이면 가장 높은 단계
    limits["t10_start_stage"] = t10
    limits["breaker_start_stage"] = applied_stage
    for col in ("t2_start_stage", "t10_start_stage", "breaker_start_stage"):
        limits[col] = limits[col].astype("Int64")
    limits = limits[[c.name for c in AGENT_LIMIT.columns]]

    # ---- 타 리스크 전이 평가
    cap_levels = {}
    for u in counted:
        (a_c, b_c), (a_o, b_o) = (_row_levels(inputs[(inputs["unit_id"] == u.unit_id)
                                                    & (inputs["stage"] == s)].iloc[0])
                                  for s in ("확정", "운영"))
        cap_levels[u.unit_id] = (
            tuple(o if o is not None else c for o, c in zip(a_o, a_c)),
            tuple(o if o is not None else c for o, c in zip(b_o, b_c)))
    shared = {}
    for u in counted:
        if u.provider != SELF_HOSTED:
            shared[u.model_id] = shared.get(u.model_id, 0) + 1
    f1_now = {r["unit_id"]: bool(r["f1_high_impact"])
              for r in inputs[inputs["stage"] == "운영"].to_dict("records")}
    applies = {
        1: lambda u: cap_levels[u.unit_id][0][1] == 3,
        2: lambda u: u.credit_role,
        3: lambda u: cap_levels[u.unit_id][0][2] == 3,
        4: lambda u: f1_now[u.unit_id],
        5: lambda u: cap_levels[u.unit_id][1][3] >= 2,
        6: lambda u: u.provider != SELF_HOSTED and shared.get(u.model_id, 0) >= 2,
        7: lambda u: True,
    }
    con_rows = []
    imp = None
    if ai_impact is not None and len(ai_impact) and ai_base:
        imp = ai_impact.set_index(["scenario_id", "severity_key"])
    for seq, sid, name, first, path, target, control in INCIDENT_TYPES:
        hit = [u for u in counted if applies[seq](u)]
        worst = max((DEPTH[q_use[u.unit_id]] for u in hit), default=0)
        for t in TIERS:
            depth = DEPTH[t]
            sev = SEVERITY_BY_DEPTH[depth]
            at_depth = sorted(u.unit_id for u in hit if q_use[u.unit_id] == t)
            row = {"incident_type": seq, "scenario_id": sid, "incident_name": name,
                   "depth": depth, "tier": t, "severity_key": sev,
                   "first_order_loss": first, "transmission": path,
                   "applicable_rule": target, "control_param": control,
                   "n_units": len(at_depth), "unit_ids": ", ".join(at_depth) or None,
                   "applied": bool(depth == worst and worst > 0)}
            if imp is not None and (sid, sev) in imp.index:
                r = imp.loc[(sid, sev)]
                loss = float(r["loss_op_total"] + r["loss_op_out_of_horizon"]
                             + r["fine_total"] + r["fine_out_of_horizon"])
                lcr0 = float(ai_base["lcr"])
                row.update({
                    "loss_first_order": loss,
                    "tau_op": loss / bi if bi else None,
                    "tau_credit": (float(r["delta_ecl_max"]) / float(ai_base["ecl"])
                                   if ai_base.get("ecl") else None),
                    "tau_capital": (-float(r["delta_cet1_bp"]) / 1e4
                                    / float(r["cet1_ratio_reference"])),
                    "tau_liquidity": max(0.0, lcr0 - float(r["lcr_min"])) / lcr0,
                    "tau_revenue": float(r["revenue_lost_to_rev"]),
                    "delta_cet1_bp": float(r["delta_cet1_bp"])})
            else:                                      # 계수가 없으면 미산출로 둔다
                row.update({k: None for k in (
                    "loss_first_order", "tau_op", "tau_credit", "tau_capital",
                    "tau_liquidity", "tau_revenue", "delta_cet1_bp")})
            con_rows.append(row)
    contagion = pd.DataFrame(con_rows)
    for col in ("loss_first_order", "tau_op", "tau_credit", "tau_capital",
                "tau_liquidity", "tau_revenue", "delta_cet1_bp"):
        contagion[col] = contagion[col].astype("float64")

    # ---- 내부 관리 가산
    add_rows = []
    applied_total, n_b_binding = 0.0, 0
    for uid, (classes, cut) in INVOLVEMENT.items():
        t = q_use[uid]
        book = irb_results[irb_results["asset_class"].isin(classes)]
        book = book[book["exposure_id"].map(_bucket) < cut]
        rwa = book["rwa"].to_numpy(dtype=float)
        coef_a = (None if params.addon_rate is None
                  else params.addon_rate * params.addon_mult[t])
        coef_b = None if params.pd_addon is None else params.pd_addon[t]
        add_a = None if coef_a is None else rwa * coef_a
        add_b = None
        if coef_b is not None:
            bumped = book.assign(pd=np.minimum(book["pd"].to_numpy(dtype=float)
                                               * (1.0 + coef_b), 1.0))
            add_b = compute_rwa_irb(bumped)["rwa"].to_numpy(dtype=float) - rwa
        base = {"scope_id": uid, "tier": t, "n_exposures": int(len(book)),
                "ead": float(book["ead"].sum()), "rwa_regulatory": float(rwa.sum()),
                "rwa_internal": None}
        for kind, coef, add in ((ADDON_A, coef_a, add_a), (ADDON_B, coef_b, add_b)):
            add_rows.append({"addon_kind": kind, **base, "coefficient": coef,
                             "addon_rwa": None if add is None else float(add.sum()),
                             "addon_capital": (None if add is None else
                                               float(add.sum()) * params.capital_factor),
                             "applied": False})
        parts = [x for x in (add_a, add_b) if x is not None]
        if parts:
            best = np.maximum.reduce(parts)
            applied_total += float(best.sum())
            if add_a is not None and add_b is not None:
                n_b_binding += int((add_b > add_a).sum())
            add_rows.append({"addon_kind": ADDON_APPLIED, **base, "coefficient": None,
                             "addon_rwa": float(best.sum()),
                             "addon_capital": float(best.sum()) * params.capital_factor,
                             "applied": True})
    worst_c = contagion[contagion["applied"] & contagion["loss_first_order"].notna()]
    op_addon, op_sid = None, None
    if len(worst_c):
        top = worst_c.loc[worst_c["loss_first_order"].idxmax()]
        op_addon, op_sid = float(top["loss_first_order"]), str(top["scenario_id"])
        add_rows.append({"addon_kind": ADDON_C, "scope_id": op_sid, "tier": top["tier"],
                         "n_exposures": 0, "ead": 0.0, "rwa_regulatory": 0.0,
                         "rwa_internal": None, "coefficient": None, "addon_rwa": None,
                         "addon_capital": op_addon, "applied": True})
    add_rows.append({
        "addon_kind": ADDON_TOTAL, "scope_id": "ALL", "tier": None, "n_exposures": 0,
        "ead": 0.0, "rwa_regulatory": float(rwa_regulatory),
        "rwa_internal": float(rwa_regulatory) + applied_total, "coefficient": None,
        "addon_rwa": applied_total,
        "addon_capital": applied_total * params.capital_factor + (op_addon or 0.0),
        "applied": True})
    addon = pd.DataFrame(add_rows)

    # ---- 사후 검증
    def rate(col: str, t: str) -> float | None:
        sub = obs[obs["unit_id"].map(q_use) == t]
        return float(sub[col].sum() / sub["executions"].sum()) if sub["executions"].sum() else None

    incidents = int(obs["incidents"].sum())
    inc = [rate("incidents", t) for t in TIERS]
    if incidents < params.min_incidents:
        j1 = "결론 유보"
    else:
        j1 = "기준 충족" if inc[2] >= inc[1] >= inc[0] else "점검 필요"
    declared_diff = sum(1 for i in ids
                        if at[(i, "예정")]["inherent_tier"] != at[(i, "확정")]["inherent_tier"])
    k = {(r["indicator_id"], r["measure_seq"]): r for r in app_rows}

    def by_threshold(row) -> str:
        return ("기준 미설정" if row["status"] == STATUS_UNSET
                else "기준 충족" if row["status"] == STATUS_OK else "점검 필요")

    up = int(migration.loc[migration["direction"] == "상향", "n_units"].sum())
    alts = [replace(tier_params, w_b=(w,) + tier_params.w_b[1:],
                    cuts=(tier_params.cuts[0] + d, tier_params.cuts[1] + d))
            for w in (1, 2, 3) for d in (-1, 0, 1)
            if (w, d) != (tier_params.w_b[0], 0)]
    conf_in = inputs[(inputs["stage"] == "확정") & inputs["unit_id"].isin(ids)]
    base_tier = {r["unit_id"]: assess_row(r, tier_params).inherent
                 for r in conf_in.to_dict("records")}
    changed = max(sum(1 for r in conf_in.to_dict("records")
                      if assess_row(r, p).inherent != base_tier[r["unit_id"]])
                  for p in alts)
    brc = [rate("envelope_breach_attempts", t) for t in TIERS]
    bt_rows = [
        (1, "등급별 사건율의 순서", "등급별 사건 건수 ÷ 실행 건수의 비교",
         incidents / executions if executions else None, inc, incidents,
         "고 ≥ 중 ≥ 저 순서 유지", j1, "순서 역전 시 항목과 가중치 재검토"),
        (2, "선언 대 실측 차이율", "예정 등급과 확정 등급이 다른 건수 ÷ 심사 건수",
         declared_diff / n, None, n, "기관 설정 임계치", "기준 미설정",
         "기획서 양식과 인식 규칙 보완"),
        (3, "등급 하향 조정 비율", "하향 조정 건수 ÷ 등급 확정 건수",
         k[("K9", 1)]["value"], None, n, "기관 설정 임계치",
         by_threshold(k[("K9", 1)]), "독립 재확인 표본 확대"),
        (4, "경계 근처 건 비중", "노출 점수가 구간 경계에 붙은 건수 ÷ 전체 건수",
         k[("K9", 2)]["value"], None, n, "특정 경계 바로 아래의 집중 여부",
         by_threshold(k[("K9", 2)]), "평가자 간 편차 점검"),
        (5, "봉투 이탈 시도율", "봉투 이탈 시도 건수 ÷ 실행 건수",
         k[("K5", 1)]["value"], brc, executions, "등급별 추이",
         by_threshold(k[("K5", 1)]), "봉투 재설계 또는 재등급"),
        (6, "등급 이행 행렬", "기간 초 등급 대비 기간 말 등급의 이동 건수",
         up / n, None, n, "상향 이동의 집중 여부",
         "점검 필요" if up else "기준 충족", "원인 분석(변경, 관측, 외부)"),
        (7, "방법론 변경 영향", "가중치와 구간 경계를 바꿨을 때 등급이 달라지는 단위의 최대 비중",
         changed / n, None, len(alts), "변경 사유와 분포 변화의 일치", "해당 없음",
         "의결 자료 첨부"),
    ]
    backcheck = pd.DataFrame([{
        "item_seq": s, "item": item, "method": method, "value": value,
        "value_low": None if by is None else by[0],
        "value_mid": None if by is None else by[1],
        "value_high": None if by is None else by[2],
        "sample_n": int(sn), "criterion": crit, "judgement": judge, "action": action,
    } for s, item, method, value, by, sn, crit, judge, action in bt_rows])
    for col in ("value", "value_low", "value_mid", "value_high"):
        backcheck[col] = backcheck[col].astype("float64")

    # ---- 실행 통제(RYNTA Bifrost)와의 연결. 값은 위 원장에서 그대로 옮긴다.
    def kv(kid: str, seq: int = 1):
        row = k[(kid, seq)]
        return row["value"], row["value_unit"], row["status"]

    n_t2 = int(limits["t2_triggered"].sum())
    n_retier = int(migration.loc[migration["direction"].isin(("상향", "보류")),
                                 "n_units"].sum())
    l2 = layers[layers["layer"] == 2]
    excess2 = float(l2["excess_amount"].fillna(0.0).sum())
    params_frame = _param_frame(tier_params, params)
    n_pending = int((params_frame["setting_status"] != SET_STRUCT).sum())
    link_rows = [
        ("BH-01", TO_HEIMDALL, "등급 봉투 집행", "CP-VRF-48",
         "감내수준 지표 K5: 봉투 이탈 시도율", "HM-06",
         "봉투 이탈 시도 건수와 실행 건수", *kv("K5", 1), "aig_risk_appetite"),
        ("BH-02", TO_HEIMDALL, "실행 중 차단장치", "CP-VRF-49",
         "감내수준 지표 K5: 차단장치 4·5단계 발동", "HM-06",
         "차단장치 발동 건수와 단계", *kv("K5", 2), "aig_risk_appetite"),
        ("BH-03", TO_HEIMDALL, "한도 예약·누적", "CP-MSR-16",
         "위험가중 사용량과 감내수준 지표 K2", "HM-07",
         "Agent별 부여 한도와 실제 사용 금액", *kv("K2"), "aig_weighted_usage"),
        ("BH-04", TO_HEIMDALL, "승인 라우팅과 승인함", "CP-VRF-18 · CP-MSR-20",
         "감내수준 지표 K8: 무수정 승인 비율", "HM-06",
         "승인 건수와 무수정 승인 건수", *kv("K8", 2), "aig_risk_appetite"),
        ("BH-05", TO_HEIMDALL, "사건·조치 기록", "CP-RPT-05 · CP-RPT-06",
         "감내수준 지표 K3: 사고 손실 사용률", "HM-06",
         "당해 연도 Agent 사고 손실 누계", *kv("K3"), "aig_risk_appetite"),
        ("BH-06", TO_HEIMDALL, "사건 기록", "CP-RPT-05",
         "감내수준 지표 K4: 중대 사건 건수", "HM-06",
         "중대 Agent 사건 건수", *kv("K4"), "aig_risk_appetite"),
        ("BH-07", TO_HEIMDALL, "Agent 등급 산정과 재측정", "CP-MSR-18 · CP-MSR-19",
         "감내수준 지표 K1: 고 등급 Agent 비중", "HM-06",
         "운영 등급(잔여)과 등급 미확정 여부", *kv("K1"), "aig_tier_assessment"),
        ("BH-08", TO_HEIMDALL, "등급 확정과 독립 재확인", "CP-VRF-47",
         "감내수준 지표 K9: 하향 비율 / 사후 검증", "HM-06 · HM-10",
         "등급 하향 건수와 등급 확정 건수", *kv("K9", 1), "aig_tier_assessment"),
        ("BH-09", TO_HEIMDALL, "통제 요건 점검과 정기 점검", "CP-VRF-46 · CP-RPT-14",
         "감내수준 지표 K6: 검증·점검 미이행 비율", "HM-06",
         "독립검증 미완료 또는 점검 기한 경과 Agent 수", *kv("K6"),
         "aig_agent_observation"),
        ("BH-10", TO_HEIMDALL, "모델 등록", "CP-IDN-09",
         "감내수준 지표 K7: 모델 공급자 집중도", "HM-06",
         "Agent별 모델 공급자와 모델 판본", *kv("K7"), "aig_agent_unit"),
        ("BH-11", TO_HEIMDALL, "긴급정지 시험", "CP-VRF-49 · CP-VRF-46",
         "전이 평가의 통제 연결 모수: 차단 지연 시간", "HM-08",
         "긴급정지 소요 시간 (가장 느린 단위)", float(obs["stop_seconds"].max()), "초",
         "기록", "aig_agent_observation"),
        ("HB-01", TO_BIFROST, "실행 중 차단장치 조건 T2", "CP-VRF-49",
         "Agent별 한도 소진율", "HM-07", "한도 소진율의 임계 초과 단위 수",
         float(n_t2), "건", "발동" if n_t2 else "발동 없음", "aig_agent_limit"),
        ("HB-02", TO_BIFROST, "실행 중 차단장치 조건 T10", "CP-VRF-49",
         "감내수준 지표 K2·K3 의 초과 단계", "HM-06",
         "초과 단계가 조건 심각도가 된다 (조기경보 1, 경영진 상향 기준 2, 이사회 한도 3)",
         float(t10_severity), "단계", "발동" if t10_severity else "발동 없음",
         "aig_risk_appetite"),
        ("HB-03", TO_BIFROST, "등급 봉투와 승인 요건", "CP-VRF-48 · CP-VRF-18",
         "운영 등급의 상향과 등급 미확정", "HM-10",
         "재등급 대상 단위 수 (고 등급과 미확정은 효과 행동 전건 2인 승인)",
         float(n_retier), "건", "대상 있음" if n_retier else "대상 없음",
         "aig_tier_migration"),
        ("HB-04", TO_BIFROST, "Agent별 한도의 기관 설정", "CP-MSR-16",
         "등급별 총량 한도 점검", "HM-07",
         "등급별 총량을 넘은 초과분 (한도 축소 또는 예외 승인)", excess2, "KRW",
         "조정 대상" if excess2 > 0 else "한도 내", "aig_limit_layer"),
        ("HB-05", TO_BIFROST, "차단장치 임계값과 한도의 기관 설정", "CP-VRF-49 · CP-MSR-16",
         "임계치와 한도의 승인 결과", "HM-06 · HM-07",
         "기관 승인을 거치지 않은 설정 수치 수 (반영은 2인 승인)", float(n_pending),
         "건", "기관 승인 전" if n_pending else "기록", "aig_tier_param"),
    ]
    links = pd.DataFrame([dict(zip(
        ("link_id", "direction", "bifrost_control", "bifrost_requirement",
         "heimdall_item", "heimdall_requirement", "signal", "current_value",
         "value_unit", "state", "source_table"), r)) for r in link_rows])
    links["current_value"] = links["current_value"].astype("float64")

    k1 = k[("K1", 1)]["value"]
    k2 = k[("K2", 1)]["value"]
    frames = {
        "aig_tier_criteria": tier.criteria_frame(tier_params),
        "aig_tier_rule": tier.rule_frame(tier_params),
        "aig_tier_policy": tier.policy_frame(),
        "aig_tier_param": params_frame,
        "aig_agent_unit": units,
        "aig_tier_input": inputs,
        "aig_tier_assessment": assess,
        "aig_tier_envelope": envelope,
        "aig_tier_migration": migration,
        "aig_agent_observation": obs,
        "aig_agent_limit": limits,
        "aig_limit_layer": layers,
        "aig_weighted_usage": usage,
        "aig_risk_appetite": appetite,
        "aig_contagion": contagion,
        "aig_internal_addon": addon,
        "aig_tier_backcheck": backcheck,
        "aig_control_link": links,
    }
    headline = {"agent_high_tier_share": k1, "agent_weighted_limit_usage": k2,
                "agent_internal_rwa_addon": applied_total if INVOLVEMENT else None,
                "agent_op_internal_capital_addon": op_addon}
    return AgentRiskResult(frames=frames, headline=headline, capital_total=cap,
                           rwa_regulatory=float(rwa_regulatory),
                           institution_code=institution_code)


# ---------------------------------------------------------------- 기관 설정 수치 원장
_AP_TIER = "합의제 의결 기구"
_AP_RISK = "위험관리 책임 조직"
_AP_RISK2 = "위험관리 책임 조직 (2인 승인)"
_AP_BOARD = "이사회 또는 위임받은 위원회"
_AP_CTRL = "지정 통제 기능 장 (2인 승인)"
_UN_TIER = "등급 산정 보류"
_UN_WEIGHT = "최고 가중치 적용"
_UN_ADDON = "해당 평가 미산출 표시"
_UN_APPETITE = "미설정 표시, 신규 고 등급 운영 승인과 한도 상향 보류"
_UN_BREAKER = "수동 발동만 작동, 중·고 등급 운영 승인 관문 미통과"
_B_PRD = "요건정의서 v0.94 가정 예시"
_B_REPO = "이 저장소의 예시값 (요건정의서에 수치 없음)"


def _param_frame(tp: TierParams, rp: RiskParams) -> pd.DataFrame:
    rows: list[dict] = []

    def add(pid, group, name, value, unit, basis, approver, unset, status=None):
        rows.append({
            "param_id": pid, "param_group": group, "param_name": name,
            "value": None if value is None else float(value), "unit": unit,
            "basis": basis, "evidence_status": _EV,
            "setting_status": status or (SET_UNSET if value is None else SET_EXAMPLE),
            "approver": approver, "unset_handling": unset})

    for i, w in enumerate(tp.w_b, start=1):
        add(f"TIER-W-B{i}", "등급 산식", f"노출 가중치 B{i}", w, "배수", _B_PRD,
            _AP_TIER, _UN_TIER)
    add("TIER-CUT-1", "등급 산식", "노출 수준 1 상한 점수", tp.cuts[0], "점", _B_PRD,
        _AP_TIER, _UN_TIER)
    add("TIER-CUT-2", "등급 산식", "노출 수준 2 상한 점수", tp.cuts[1], "점", _B_PRD,
        _AP_TIER, _UN_TIER)
    for t in TIERS:
        add(f"RW-{DEPTH[t]}", "위험가중 사용량", f"위험가중치 {t}", rp.risk_weight.get(t),
            "배수", _B_PRD, _AP_RISK, _UN_WEIGHT)
    for t in TIERS:
        add(f"BRK-ADD-{DEPTH[t]}", "차단장치", f"차단장치 등급 가산 {t}",
            tier.BREAKER_ADD[t], "단계", _B_PRD, _AP_CTRL, _UN_BREAKER, SET_STRUCT)
    add("T2-UTIL", "차단장치", "한도 소진율 임계 (조건 T2)", rp.t2_utilisation, "ratio",
        _B_REPO, _AP_CTRL, _UN_BREAKER)
    add("ADD-A", "내부 관리 가산", "기본 가산율 a", rp.addon_rate, "ratio", _B_PRD,
        _AP_RISK2, _UN_ADDON)
    for t in TIERS:
        add(f"ADD-M-{DEPTH[t]}", "내부 관리 가산", f"등급 승수 m {t}", rp.addon_mult.get(t),
            "배수", _B_PRD, _AP_RISK2, _UN_ADDON)
    for t in TIERS:
        add(f"ADD-B-{DEPTH[t]}", "내부 관리 가산", f"부도율 보수성 가산 b {t}",
            None if rp.pd_addon is None else rp.pd_addon.get(t), "ratio", _B_REPO,
            _AP_RISK2, _UN_ADDON)
    add("ADD-CAP", "내부 관리 가산", "내부자본 환산율", rp.capital_factor, "ratio", _B_PRD,
        _AP_RISK2, _UN_ADDON)
    add("K3-LIMIT", "감내수준", "연간 사고 손실 감내 한도 (자기자본 대비)",
        None if rp.loss_tolerance_bp is None else rp.loss_tolerance_bp / 1e4, "ratio",
        _B_REPO, _AP_BOARD, _UN_APPETITE)
    for key, thr in rp.thresholds.items():
        basis = _B_PRD if key == "K2" else _B_REPO
        for label, idx in (("조기경보 임계치", 0), ("경영진 상향 기준", 1), ("이사회 한도", 2)):
            add(f"{key}-T{idx + 1}", "감내수준", f"{key} {label}",
                None if thr is None else thr[idx], "가변", basis, _AP_BOARD, _UN_APPETITE)
    for t in TIERS:
        add(f"LIM-L2-{DEPTH[t]}", "한도", f"등급별 총량 한도 {t} (자기자본 대비)",
            None if rp.tier_cap_bp.get(t) is None else rp.tier_cap_bp[t] / 1e4, "ratio",
            _B_REPO, _AP_RISK, _UN_WEIGHT)
    add("BT-MIN", "사후 검증", "사건율 판단 최소 사건 수", rp.min_incidents, "건", _B_REPO,
        _AP_RISK, "결론 유보")
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- 원장 스펙
_KRW = dict(unit="KRW")
_RATIO = dict(unit="ratio")

TIER_PARAM = TableSpec(
    name="aig_tier_param", korean="Agent 위험 기관 설정 수치", product="PRD-AIG",
    grain="설정 수치 1건당 1행",
    columns=(
        C("param_id", "string", "수치 ID", nullable=False),
        C("param_group", "string", "구분", nullable=False,
          allowed=("등급 산식", "위험가중 사용량", "차단장치", "내부 관리 가산",
                   "감내수준", "한도", "사후 검증")),
        C("param_name", "text", "수치명", nullable=False),
        C("value", "float", "값", nullable=True, unit="가변",
          note="단위는 같은 행의 unit 열에 있다. 비어 있으면 미설정이다"),
        C("unit", "string", "단위", nullable=False),
        C("basis", "text", "근거", nullable=False),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
        C("setting_status", "string", "설정 상태", nullable=False,
          allowed=(SET_EXAMPLE, SET_STRUCT, SET_UNSET),
          note="패키지는 수치 기본값을 주지 않는다. 예시 설정값은 기관이 승인해 "
               "등록하기 전의 값이다"),
        C("approver", "text", "승인 주체", nullable=False),
        C("unset_handling", "text", "미설정 시 처리", nullable=False),
    ),
    primary_key=("param_id",),
    note="가중치, 구간 경계, 위험가중치, 가산율, 임계치, 한도. 값을 바꾸면 등급과 위험량이 "
         "바뀌므로 변경은 2인 승인 대상이고 Agent 의 변경 경로는 막혀 있어야 한다.",
)

AGENT_UNIT = TableSpec(
    name="aig_agent_unit", korean="Agent 산정 단위 등록부", product="PRD-AIG",
    grain="산정 단위(Agent 판본 × 사용 사례 또는 Agent 시스템) 1건당 1행",
    columns=(
        C("unit_id", "string", "산정 단위 ID", nullable=False),
        C("unit_name", "text", "이름", nullable=False),
        C("unit_type", "string", "단위 유형", nullable=False, allowed=tier.UNIT_TYPES),
        C("parent_unit_id", "string", "소속 Agent 시스템", nullable=True),
        C("use_case", "text", "연결 사용 사례", nullable=False),
        C("model_provider", "string", "모델 공급자", nullable=False),
        C("model_id", "string", "모델 판본", nullable=False),
        C("credit_model_role", "bool", "신용평가·심사 보조", nullable=False),
        C("status", "string", "상태", nullable=False, allowed=("운영 중", "접수 반려")),
        C("counted", "bool", "집계 단위", nullable=False,
          note="단독 Agent 와 Agent 시스템만 센다. 구성원은 시스템에 포함한다"),
        C("data_origin", "string", "자료 성격", nullable=False,
          allowed=("합성 참조 포트폴리오",)),
    ),
    primary_key=("unit_id",),
    note="업무 Agent 의 합성 참조 포트폴리오다. 산출 하네스의 에이전트 목록"
         "(agent_registry)과 다른 원장이다.",
)

AGENT_OBSERVATION = TableSpec(
    name="aig_agent_observation", korean="Agent 관측 기록 요약", product="PRD-AIG",
    grain="집계 단위 1건당 1행 (당해 연도 누계)",
    columns=(
        C("unit_id", "string", "산정 단위 ID", nullable=False),
        C("executions", "int", "실행 건수", nullable=False, min_value=0),
        C("effect_actions", "int", "효과 행동 건수", nullable=False, min_value=0),
        C("envelope_breach_attempts", "int", "봉투 이탈 시도 건수", nullable=False,
          min_value=0),
        C("breaker_stage45", "int", "차단장치 4·5단계 발동 건수", nullable=False,
          min_value=0),
        C("incidents", "int", "사건 건수", nullable=False, min_value=0),
        C("major_incidents", "int", "중대 사건 건수", nullable=False, min_value=0),
        C("incident_loss", "float", "사고 손실 누계", nullable=False, min_value=0, **_KRW),
        C("approvals", "int", "승인 건수", nullable=False, min_value=0),
        C("approvals_unmodified", "int", "무수정 승인 건수", nullable=False, min_value=0),
        C("check_overdue", "bool", "검증·점검 기한 경과", nullable=False),
        C("stop_seconds", "float", "긴급정지 소요 시간", nullable=False, unit="seconds",
          min_value=0, note="전이 평가의 통제 연결 모수. 기록만 하고 손실 크기에는 "
                            "아직 잇지 않았다"),
        C("detect_hours", "float", "탐지 소요 시간", nullable=False, unit="hours",
          min_value=0),
        C("data_origin", "string", "자료 성격", nullable=False,
          allowed=("합성 참조 포트폴리오",)),
    ),
    primary_key=("unit_id",),
    foreign_keys=(FK(("unit_id",), "aig_agent_unit", ("unit_id",)),),
    note="실행 통제 계층(RYNTA Bifrost)이 만드는 기록의 요약 자리다. 이 저장소에는 그 "
         "계층이 없어 고정 합성값이 들어 있다.",
)

AGENT_LIMIT = TableSpec(
    name="aig_agent_limit", korean="Agent별 한도와 사용", product="PRD-AIG",
    grain="집계 단위 1건당 1행",
    columns=(
        C("unit_id", "string", "산정 단위 ID", nullable=False),
        C("confirmed_tier", "string", "확정 등급 (잔여)", nullable=False, allowed=TIERS),
        C("quantity_tier", "string", "위험량 적용 등급", nullable=False, allowed=TIERS),
        C("risk_weight", "float", "위험가중치", nullable=False, unit="배수", min_value=0),
        C("limit_amount", "float", "일 누적 금액 한도", nullable=True, min_value=0, **_KRW,
          note="금액으로 표시할 수 없는 행동만 하는 단위는 비어 있고 건수 한도로 관리한다"),
        C("per_action_limit", "float", "건당 금액 한도", nullable=True, min_value=0, **_KRW),
        C("limit_count", "int", "일 건수 한도", nullable=False, min_value=0),
        C("used_amount", "float", "실제 사용 금액", nullable=True, min_value=0, **_KRW),
        C("utilisation", "float", "한도 소진율", nullable=True, min_value=0, **_RATIO),
        C("weighted_granted", "float", "위험가중 부여 한도", nullable=True, min_value=0,
          **_KRW),
        C("weighted_used", "float", "위험가중 실제 사용", nullable=True, min_value=0, **_KRW),
        C("t2_triggered", "bool", "한도 소진율 임계 초과 (T2)", nullable=False),
        C("t2_start_stage", "int", "T2 시작 단계", nullable=True, min_value=1,
          max_value=5, note="min(5, 조건 심각도 1 + 등급 가산). 등급은 운영 등급(고유)"),
        C("t10_start_stage", "int", "T10 시작 단계", nullable=True, min_value=1,
          max_value=4, note="감내수준 지표 K2·K3 의 초과 단계가 조건 심각도다. 금액 한도를 "
                            "쓰는 단위 전체에 적용하고 격리(5단계)는 하지 않는다"),
        C("breaker_start_stage", "int", "차단장치 시작 단계", nullable=True, min_value=1,
          max_value=5, note="여러 조건이 함께 성립하면 가장 높은 단계"),
        C("new_limit_hold", "bool", "신규 한도 부여 보류", nullable=False,
          note="등급 미확정 단위"),
    ),
    primary_key=("unit_id",),
    foreign_keys=(FK(("unit_id",), "aig_agent_unit", ("unit_id",)),),
    note="한도 계층 3(Agent별)과 4(건당). 집행은 실행 통제 계층이 한다.",
)

LIMIT_LAYER = TableSpec(
    name="aig_limit_layer", korean="Agent 한도 계층 점검", product="PRD-AIG",
    grain="한도 계층 × 범위 1행",
    columns=(
        C("layer", "int", "한도 계층", nullable=False, min_value=1, max_value=4),
        C("scope", "string", "범위", nullable=False,
          allowed=("전사",) + TIERS + ("Agent별", "건당")),
        C("content", "text", "내용", nullable=False),
        C("approver", "text", "승인 주체", nullable=False),
        C("enforcement", "text", "집행과 점검", nullable=False),
        C("weighted", "bool", "위험가중 금액", nullable=False,
          note="계층 1 은 위험가중 금액, 나머지는 가중 전 금액이다"),
        C("limit_amount", "float", "한도", nullable=True, min_value=0, **_KRW,
          note="계층 3·4 는 단위마다 한도가 달라 합계 한도가 없다"),
        C("granted_amount", "float", "부여 합계", nullable=True, min_value=0, **_KRW,
          note="계층 4 는 건당 한도라 합계를 내지 않는다"),
        C("used_amount", "float", "사용 합계", nullable=True, min_value=0, **_KRW),
        C("utilisation", "float", "부여 ÷ 한도", nullable=True, min_value=0, **_RATIO),
        C("excess_amount", "float", "초과분", nullable=True, min_value=0, **_KRW),
        C("status", "string", "상태", nullable=False,
          allowed=("한도 내", "조정 대상", "한도 초과", STATUS_UNSET)),
        C("requirement_refs", "text", "요건", nullable=False),
    ),
    primary_key=("layer", "scope"),
    note="하위 한도 합계는 상위 한도 이내여야 한다. 등급 상향으로 등급별 총량을 넘으면 "
         "초과분이 조정 대상(한도 축소 또는 예외 승인)이 된다. 계층 3·4 의 상태는 사용이 "
         "한도를 넘은 단위, 건당 한도가 일 누적 한도보다 큰 단위가 있는지를 뜻한다.",
)

WEIGHTED_USAGE = TableSpec(
    name="aig_weighted_usage", korean="Agent 위험가중 사용량", product="PRD-AIG",
    grain="등급 기준 × 금액 기준 × 등급 1행",
    columns=(
        C("tier_basis", "string", "등급 기준", nullable=False,
          allowed=("확정 등급", "운영 등급"),
          note="운영 등급은 상향을 즉시 반영하고 미확정을 최고 등급으로 본다"),
        C("amount_basis", "string", "금액 기준", nullable=False,
          allowed=("부여 한도", "실제 사용")),
        C("tier", "string", "등급", nullable=False, allowed=TIERS + ("합계",)),
        C("amount", "float", "금액", nullable=False, min_value=0, **_KRW),
        C("risk_weight", "float", "위험가중치", nullable=True, unit="배수", min_value=0),
        C("weighted_amount", "float", "위험가중 금액", nullable=False, min_value=0, **_KRW),
        C("ratio_to_capital", "float", "자기자본 대비", nullable=False, min_value=0,
          **_RATIO),
    ),
    primary_key=("tier_basis", "amount_basis", "tier"),
    note="U = Σ(Agent별 금액 × 등급별 위험가중치). 같은 금액 한도라도 고 등급에 주면 총량을 "
         "더 차지한다.",
)

RISK_APPETITE = TableSpec(
    name="aig_risk_appetite", korean="Agent 위험 감내수준 지표", product="PRD-AIG",
    grain="지표 × 측정값 1행",
    columns=(
        C("indicator_id", "string", "지표 ID", nullable=False,
          allowed=tuple(f"K{i}" for i in range(1, 10))),
        C("measure_seq", "int", "측정값 순번", nullable=False, min_value=1, max_value=2),
        C("indicator_name", "text", "지표", nullable=False),
        C("definition", "text", "정의", nullable=False),
        C("numerator", "float", "분자", nullable=False, unit="가변"),
        C("denominator", "float", "분모", nullable=True, unit="가변",
          note="건수 지표는 분모가 없다"),
        C("value", "float", "값", nullable=True, unit="가변",
          note="단위는 value_unit 열. 분모가 0 이면 값을 만들지 않는다"),
        C("value_unit", "string", "단위", nullable=False, allowed=("비율", "건")),
        C("threshold_early", "float", "조기경보 임계치", nullable=True, unit="가변"),
        C("threshold_mgmt", "float", "경영진 상향 기준", nullable=True, unit="가변"),
        C("threshold_board", "float", "이사회 한도", nullable=True, unit="가변"),
        C("status", "string", "상태", nullable=False,
          allowed=(STATUS_OK,) + STATUS_LEVELS + (STATUS_UNSET,),
          note="임계치가 비어 있으면 '미설정'이다. '범위 내'로 적지 않는다"),
        C("breach_level", "int", "초과 단계", nullable=True, min_value=0, max_value=3,
          note="1 조기경보, 2 경영진 상향 기준, 3 이사회 한도. 차단장치 조건 T10 의 "
               "심각도로 넘어간다"),
        C("threshold_setting", "string", "임계치 설정 상태", nullable=False,
          allowed=(SET_EXAMPLE, SET_UNSET)),
        C("input_source", "text", "입력 원천", nullable=False),
        C("on_breach", "text", "초과 시 연결", nullable=False),
    ),
    primary_key=("indicator_id", "measure_seq"),
    note="지표 9종, 3단 임계치(운영 조기경보, 경영진 상향 기준, 이사회 한도). 임계치는 "
         "이사회 또는 위임받은 위원회가 승인하는 기관 설정이다.",
)

CONTAGION = TableSpec(
    name="aig_contagion", korean="Agent 사고의 타 리스크 전이 평가", product="PRD-AIG",
    grain="사고 유형 × 심도 1행",
    columns=(
        C("incident_type", "int", "사고 유형", nullable=False, min_value=1, max_value=7),
        C("scenario_id", "string", "시나리오", nullable=False),
        C("incident_name", "text", "사고 유형명", nullable=False),
        C("depth", "int", "심도", nullable=False, min_value=1, max_value=3),
        C("tier", "string", "대응 잔여 등급", nullable=False, allowed=TIERS),
        C("severity_key", "string", "시나리오 심도", nullable=False,
          allowed=tuple(SEVERITY_BY_DEPTH.values())),
        C("first_order_loss", "text", "1차 손실 (운영리스크)", nullable=False),
        C("transmission", "text", "전이 경로", nullable=False),
        C("applicable_rule", "text", "적용 대상 Agent", nullable=False),
        C("control_param", "text", "통제 연결 모수", nullable=False),
        C("n_units", "int", "이 심도의 적용 단위 수", nullable=False, min_value=0),
        C("unit_ids", "text", "적용 단위", nullable=True),
        C("applied", "bool", "적용 심도", nullable=False,
          note="적용 단위가 있는 가장 깊은 심도"),
        C("loss_first_order", "float", "1차 운영손실", nullable=True, min_value=0, **_KRW,
          note="운영손실과 제재금, 시계 밖 몫 포함. 계수가 없으면 비어 있다(미산출)"),
        C("tau_op", "float", "전이 계수: 운영 (1차 손실 ÷ 영업지표)", nullable=True,
          **_RATIO),
        C("tau_credit", "float", "전이 계수: 신용 (충당금 증가 ÷ 기준 충당금)",
          nullable=True, **_RATIO),
        C("tau_capital", "float", "전이 계수: 자본 (보통주자본비율 하락 ÷ 기준 비율)",
          nullable=True, **_RATIO),
        C("tau_liquidity", "float", "전이 계수: 유동성 (LCR 하락 ÷ 기준 LCR)",
          nullable=True, min_value=0, **_RATIO),
        C("tau_revenue", "float", "전이 계수: 수익 (일실 수익 ÷ 영업수익)", nullable=True,
          min_value=0, **_RATIO),
        C("delta_cet1_bp", "float", "보통주자본비율 변화", nullable=True, unit="bp"),
    ),
    primary_key=("incident_type", "depth"),
    foreign_keys=(FK(("scenario_id",), "st_ai_scenario", ("scenario_id",)),),
    note="전이 계수는 사고가 났다는 전제의 기준 금액 대비 영향 비율이다. 사고 발생 확률도, "
         "등급 이행 행렬도 아니다. 값은 st_ai_impact 에서 읽는다.",
)

INTERNAL_ADDON = TableSpec(
    name="aig_internal_addon", korean="Agent 내부 관리 가산", product="PRD-AIG",
    grain="가산 종류 × 대상 1행",
    columns=(
        C("addon_kind", "string", "가산", nullable=False,
          allowed=(ADDON_A, ADDON_B, ADDON_APPLIED, ADDON_C, ADDON_TOTAL)),
        C("scope_id", "string", "대상", nullable=False,
          note="Agent 단위, 시나리오, 또는 ALL"),
        C("tier", "string", "위험량 적용 등급", nullable=True, allowed=TIERS),
        C("n_exposures", "int", "관여 익스포저 수", nullable=False, min_value=0),
        C("ead", "float", "관여 익스포저 금액", nullable=False, min_value=0, **_KRW),
        C("rwa_regulatory", "float", "규제 위험가중자산", nullable=False, min_value=0,
          **_KRW, note="공표값 그대로다. 가산은 이 칸을 바꾸지 않는다"),
        C("rwa_internal", "float", "내부 관리 위험가중자산", nullable=True, min_value=0,
          **_KRW),
        C("coefficient", "float", "적용 계수", nullable=True, **_RATIO,
          note="(a) 는 a × m(등급), (b) 는 b(등급)"),
        C("addon_rwa", "float", "가산 위험가중자산", nullable=True, **_KRW),
        C("addon_capital", "float", "내부자본 가산", nullable=True, **_KRW),
        C("applied", "bool", "합계 반영", nullable=False,
          note="(a)·(b) 행은 비교용이고 합계에는 익스포저별 큰 값만 들어간다"),
    ),
    primary_key=("addon_kind", "scope_id"),
    note="내부자본 평가, 한도 관리, 위험조정 성과 평가에만 쓴다. 규제 보고 수치가 아니다.",
)

TIER_BACKCHECK = TableSpec(
    name="aig_tier_backcheck", korean="Agent 등급 체계 사후 검증", product="PRD-AIG",
    grain="사후 검증 항목 1건당 1행",
    columns=(
        C("item_seq", "int", "순번", nullable=False, min_value=1),
        C("item", "text", "항목", nullable=False),
        C("method", "text", "방법", nullable=False),
        C("value", "float", "값", nullable=True, **_RATIO),
        C("value_low", "float", "저 등급 값", nullable=True, **_RATIO),
        C("value_mid", "float", "중 등급 값", nullable=True, **_RATIO),
        C("value_high", "float", "고 등급 값", nullable=True, **_RATIO),
        C("sample_n", "int", "표본 수", nullable=False, min_value=0),
        C("criterion", "text", "판단 기준", nullable=False),
        C("judgement", "string", "판단", nullable=False,
          allowed=("기준 충족", "점검 필요", "결론 유보", "기준 미설정", "해당 없음"),
          note="사건 수가 적으면 사건율 순서의 결론을 유보한다"),
        C("action", "text", "조치", nullable=False),
    ),
    primary_key=("item_seq",),
    note="등급 체계와 계수가 실제 사건과 맞는지 본다. 사건 자료가 쌓이기 전에는 등급의 "
         "예측력을 확인할 수 없다.",
)

CONTROL_LINK = TableSpec(
    name="aig_control_link", korean="실행 통제와 위험 관리의 연결", product="PRD-AIG",
    grain="연결 1건당 1행",
    columns=(
        C("link_id", "string", "연결 ID", nullable=False),
        C("direction", "string", "방향", nullable=False,
          allowed=(TO_HEIMDALL, TO_BIFROST)),
        C("bifrost_control", "text", "실행 통제 (RYNTA Bifrost)", nullable=False),
        C("bifrost_requirement", "string", "실행 통제 요건", nullable=False),
        C("heimdall_item", "text", "위험 관리 항목 (RYNTA Heimdall)", nullable=False),
        C("heimdall_requirement", "string", "위험 관리 요건", nullable=False),
        C("signal", "text", "넘어가는 값", nullable=False),
        C("current_value", "float", "현재 값", nullable=True, unit="가변",
          note="단위는 value_unit 열. 임계치가 없어도 값은 싣는다"),
        C("value_unit", "string", "단위", nullable=False,
          allowed=("비율", "건", "단계", "초", "KRW")),
        C("state", "string", "현재 상태", nullable=False,
          allowed=(STATUS_OK,) + STATUS_LEVELS + (
              STATUS_UNSET, "발동", "발동 없음", "대상 있음", "대상 없음", "조정 대상",
              "한도 내", "기록", "기관 승인 전")),
        C("source_table", "string", "값의 원장", nullable=False),
    ),
    primary_key=("link_id",),
    note="RYNTA Bifrost 는 실행 건별 통제와 관측 기록을 만들고, RYNTA Heimdall 은 그 기록과 "
         "Agent 등급으로 위험량을 재고 임계치와 한도의 승인 결과를 기관 설정으로 되돌린다. "
         "값은 다른 원장에서 옮긴 것이고 여기서 새로 계산하지 않는다.",
)

RISK_SPECS: tuple[TableSpec, ...] = (
    TIER_PARAM, AGENT_UNIT, AGENT_OBSERVATION, AGENT_LIMIT, LIMIT_LAYER,
    WEIGHTED_USAGE, RISK_APPETITE, CONTAGION, INTERNAL_ADDON, TIER_BACKCHECK,
    CONTROL_LINK)

# 카탈로그 등재 순서. 참조 대상(단위 등록부)이 참조하는 쪽보다 앞에 온다.
SPECS: tuple[TableSpec, ...] = (
    tier.TIER_CRITERIA, tier.TIER_RULE, tier.TIER_POLICY, TIER_PARAM, AGENT_UNIT,
    tier.TIER_INPUT, tier.TIER_ASSESSMENT, tier.TIER_ENVELOPE, tier.TIER_MIGRATION,
    AGENT_OBSERVATION, AGENT_LIMIT, LIMIT_LAYER, WEIGHTED_USAGE, RISK_APPETITE,
    CONTAGION, INTERNAL_ADDON, TIER_BACKCHECK, CONTROL_LINK)
