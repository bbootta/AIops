"""Agent 위험도 등급 기준과 결정론 산식 (제품요건정의서 v0.94 4.9).

요건: CP-MSR-18 (등급 산정) · CP-MSR-19 (운영 재측정) · CP-VRF-47 (등급 확정) ·
CP-VRF-48 (등급 봉투 집행) · RL-17 (등급 기준).

**무엇이 있었고 무엇이 없었나.** `agent_registry.risk_tier` 는 에이전트 이름에 든
낱말로 상·중·하를 붙였다 (AIG-001). 이름은 그 Agent 가 무엇을 할 수 있는지
(행동의 효과, 접근 정보, 자율성, 외부 입력)를 말해 주지 않으므로, 기획 심사와
개발 검증과 운영 통제와 한도를 한 기준으로 이을 수 없었다.

이 모듈이 두는 것은 네 가지다.

  등급 항목. 영향 네 항목(A1~A4)과 노출 네 항목(B1~B4), 수준은 1~3 이다.
  영향은 피해의 크기이고 노출은 피해가 발생하기 쉬운 구조 요인이다.

  산식. 영향 수준 I = min(3, 기본 수준 + g), 기본 수준 = max(A1, A2, min(A3, 2)),
  g 는 A4 = 3 이고 기본 수준이 2 이상일 때 1 이다. 노출 점수 S = 2·B1 + B2 + B3 + B4
  (5~15), 노출 수준 E 는 S <= 7 이면 1, 8~11 이면 2, 12 이상이면 3 이다. 고유 등급은
  행렬(I, E)이다. 높은 영향은 다른 항목의 낮은 값으로 상쇄되지 않도록 최댓값으로,
  노출은 요인이 겹칠수록 커지도록 가중 합으로 묶는다.

  고정·불허·보류. F1~F3 은 점수와 무관하게 '고', X1~X3 은 접수 반려(불허), 필수
  입력이 비면 등급을 붙이지 않는다(미확정, fail-closed). F2(Rule of Two)는 세 조건
  (비신뢰 입력 B2, 민감 정보 A3, 외부 효과 A2)이 모두 수준 3 일 때 성립한다고 읽는다.
  이 읽기는 이 저장소의 가정이며 기관이 조건 문구를 강화할 수 있다.

  잔여 등급. 통제 가능성 세 항목(C1 사전 차단, C2 탐지, C3 정지·복구)의 증거가 모두
  있고 2인 승인이 있으면 한 단계 내린다. 고정 조건에 해당하면 내리지 않는다.
  통제 강도(승인, 차단장치)는 고유 등급을, 위험량(한도, 가산)은 잔여 등급을 쓴다.
  통제가 있다는 이유로 통제를 줄이는 순환을 막기 위해서다.

**가중치와 구간 경계는 예시 설정값이다.** (2, 1, 1, 1)과 (7, 11), 행렬은 요건정의서의
가정 예시이고 기관이 승인해 등록할 값이다. 값을 바꾸면 등급이 바뀌므로 방법론 변경
결재 대상이다. `aig_tier_param` 이 근거 상태를 '재량·미규정'으로 싣는다.

**등급은 판단을 대신하지 않는다.** 산정은 결정론이고 확정과 하향은 사람이 한다.
업무 중대성(A1)과 영향 규모(A4)는 평가자 입력이므로 평가자 사이 편차가 생길 수
있다. 독립 재확인과 사후 검증(`aig_tier_backcheck`)이 그 편차를 본다.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Sequence

import pandas as pd

from risk_lib.datamodel.spec import ColumnSpec as C, ForeignKey as FK, TableSpec

__all__ = [
    "TIERS", "BANNED", "HOLD", "TIER_STATES", "STAGES", "STAGE_SOURCE",
    "ITEM_CODES", "ITEMS", "TierParams", "DEFAULT_PARAMS", "TierOutcome",
    "assess", "rule_of_two", "fixed_flags", "union_levels", "near_boundary",
    "breaker_start", "monotonicity_violations", "uniform_distribution",
    "criteria_frame", "rule_frame", "policy_frame", "ROUTE", "BREAKER_ADD",
    "TIER_CRITERIA", "TIER_RULE", "TIER_POLICY", "TIER_INPUT", "TIER_ASSESSMENT",
    "TIER_ENVELOPE", "TIER_MIGRATION", "TIER_SPECS",
]

TIERS: tuple[str, ...] = ("저", "중", "고")
BANNED = "불허"
HOLD = "미확정"
TIER_STATES: tuple[str, ...] = TIERS + (BANNED, HOLD)
_RANK = {t: i for i, t in enumerate(TIERS)}

# 같은 항목과 같은 산식을 세 시점에 쓴다. 시점마다 항목이 다르면 예정·확정·운영
# 등급을 서로 견줄 수 없다. 다른 것은 입력의 원천뿐이다.
STAGES: tuple[str, ...] = ("예정", "확정", "운영")
STAGE_SOURCE = {"예정": "기획서 선언 값",
                "확정": "매니페스트 등록값과 시험 실측 값",
                "운영": "RYNTA Bifrost 관측 기록"}

ITEM_CODES: tuple[str, ...] = ("A1", "A2", "A3", "A4", "B1", "B2", "B3", "B4")
AXES: tuple[str, ...] = ("영향", "노출")
UNIT_TYPES: tuple[str, ...] = ("Agent", "Agent 시스템", "설계안")

# 등급별 결정 권한과 차단장치 가산. 결재자와 기구명은 기관이 정하고, 여기 있는
# 것은 패키지 구조 기본값이다 (4.11 표 42, 4.12).
ROUTE = {"저": "지정 통제 기능 담당자 확인", "중": "지정 통제 기능 장 승인",
         "고": "합의제 의결 기구 의결", BANNED: "접수 반려", HOLD: "관문 통과 불가"}
BREAKER_ADD = {"저": 0, "중": 1, "고": 2, HOLD: 2}


# ---------------------------------------------------------------- 등급 항목
@dataclass(frozen=True)
class TierItem:
    code: str
    axis: str
    name: str
    definition: str
    levels: tuple[str, str, str]
    source: str


ITEMS: tuple[TierItem, ...] = (
    TierItem("A1", "영향", "업무 중대성",
             "연결 사용 사례가 고객, 회사, 시장에 미치는 결과의 무게",
             ("내부 생산성 보조, 참고 자료 작성",
              "고객 응대 지원 / 의사결정 지원 / 보고의 중간 산출물",
              "자동확정 금지 영역 접촉 / 법령상 고영향 영역 / 고객 자산·권리에 직접 영향"),
             "기획서(평가자 입력) / 사용 사례 인벤토리"),
    TierItem("A2", "영향", "행동 효과·가역성",
             "Agent 가 실행할 수 있는 행동이 외부 상태를 바꾸는 정도와 되돌릴 수 있는 정도",
             ("조회, 초안 작성(READ)",
              "내부 상태 변경이며 보상 행동 등록 / 내부 전송",
              "대외 효과(주문, 이체, 고객 발송) / 되돌릴 수 없는 변경 / 보상 행동 미등록"),
             "도구 선언의 효과 종류 / 관측된 효과 종류"),
    TierItem("A3", "영향", "데이터 민감도",
             "Agent 가 접근하는 정보의 등급",
             ("공개 정보, 내부 일반 정보",
              "내부 기밀 / 비식별 고객 정보",
              "개인신용정보 / 고객 식별정보 / 미공개중요정보 / 인증정보"),
             "도구·자원의 정보 등급 / 관측된 접근 등급"),
    TierItem("A4", "영향", "영향 규모",
             "한 번의 오류·오용이 미치는 대상 수와 금액의 상한",
             ("단일 건, 단일 부서",
              "복수 고객·부서 / 건당·일 누적 한도 설정",
              "전 고객·전사·시장 / 한도 미설정"),
             "기획서(평가자 입력) / 한도 원장"),
    TierItem("B1", "노출", "자율성",
             "사람 개입 없이 진행하는 범위(위임 수준)",
             ("L0~L1(보조, 도구 사용)",
              "L2~L3(작업 흐름, 자율 수행)",
              "L4~L5(역할 위임, 자율 역할)"),
             "매니페스트 위임 수준 / 관측된 승인 경로"),
    TierItem("B2", "노출", "비신뢰 입력 노출",
             "검증되지 않은 외부 내용이 Agent 판단에 들어오는 정도",
             ("내부 검증 원천만 사용",
              "인증 사용자의 자유 입력 / 내부 문서 업로드",
              "외부 웹, 이메일 / 외부 기관 Agent 메시지 / 제3자 문서"),
             "입력 원천 선언 / 비신뢰 입력 표지 관측"),
    TierItem("B3", "노출", "구성 복잡성",
             "구성과 실행 경로의 복잡도",
             ("단일 Agent, 도구 소수, 단일 단계",
              "다단계 수행 / 도구 다수 / 메모리 사용",
              "다중 Agent 위임(깊이 2 이상) / 실행 중 계획 변경 / 장기 실행, 공유 메모리"),
             "Agent 시스템 등록 / 프로세스 정의 / 체인 관측"),
    TierItem("B4", "노출", "모델·제3자 불확실성",
             "모델과 제3자 구성요소의 확인 가능성, 변경 통제 가능성",
             ("자체 호스팅 / 정확한 스냅샷 확인(EXACT_SNAPSHOT)",
              "외부 API 이며 판본 식별 / 변경 통지 계약",
              "확인 불가(UNKNOWN) / 자동 갱신 / 제3자 Agent, SaaS 내장 AI"),
             "모델 등록의 확인 수준 / 공급자 공시"),
)
_ITEM = {i.code: i for i in ITEMS}

# 등급 봉투의 구성과 항목의 대응. 봉투는 확정 등급의 근거가 된 항목별 상한이다.
ENVELOPE_DIMENSION = {
    "A1": "사용 범위(업무, 사용자)", "A2": "허용 도구와 효과 종류",
    "A3": "정보 등급 상한", "A4": "건수·금액 한도", "B1": "위임 수준",
    "B2": "입력 원천 범위", "B3": "위임 깊이와 구성원", "B4": "모델 판본 범위"}


# ---------------------------------------------------------------- 산식
@dataclass(frozen=True)
class TierParams:
    """등급 산식의 기관 설정 수치. 기본값은 요건정의서의 가정 예시다."""
    w_b: tuple[int, int, int, int] = (2, 1, 1, 1)
    cuts: tuple[int, int] = (7, 11)
    matrix: tuple[tuple[str, str, str], ...] = (
        ("저", "저", "중"),      # 영향 1 × 노출 1·2·3
        ("저", "중", "고"),      # 영향 2
        ("중", "고", "고"))      # 영향 3

    def cell(self, impact: int, exposure: int) -> str:
        return self.matrix[impact - 1][exposure - 1]


DEFAULT_PARAMS = TierParams()


@dataclass(frozen=True)
class TierOutcome:
    impact_base: int | None
    scale_add: int | None        # g
    impact: int | None           # I
    score: int | None            # S
    exposure: int | None         # E
    matrix_tier: str | None      # 행렬(I, E). 고정 조건 적용 전
    fixed: tuple[str, ...]
    banned: tuple[str, ...]
    hold: str | None
    inherent: str
    residual: str
    downgraded: bool


def _levels_ok(levels: Sequence) -> bool:
    return all(v is not None and not pd.isna(v) and int(v) in (1, 2, 3) for v in levels)


def rule_of_two(a: Sequence[int], b: Sequence[int]) -> bool:
    """F2. 비신뢰 입력(B2), 민감 정보(A3), 외부 효과(A2)가 함께 성립할 수 있는 설계."""
    return int(b[1]) >= 3 and int(a[2]) >= 3 and int(a[1]) >= 3


def fixed_flags(a: Sequence[int], b: Sequence[int], *, f1: bool = False,
                f3: bool = False) -> tuple[str, ...]:
    """고정 '고' 조건. F1·F3 은 선언(사람 판정·설계 선언), F2 는 항목 수준에서 판정한다."""
    out = []
    if f1:
        out.append("F1")
    if rule_of_two(a, b):
        out.append("F2")
    if f3:
        out.append("F3")
    return tuple(out)


def assess(a: Sequence, b: Sequence, *, fixed: Sequence[str] = (),
           banned: Sequence[str] = (), controls: Sequence[bool] = (False,) * 3,
           approved: bool = False, params: TierParams = DEFAULT_PARAMS) -> TierOutcome:
    """항목 수준에서 고유·잔여 등급을 낸다. 불허, 보류, 고정, 행렬 순으로 본다."""
    fixed, banned = tuple(fixed), tuple(banned)
    if banned:
        return TierOutcome(None, None, None, None, None, None, fixed, banned, None,
                           BANNED, BANNED, False)
    if not (_levels_ok(a) and _levels_ok(b)):
        return TierOutcome(None, None, None, None, None, None, fixed, banned,
                           "H1 필수 입력 미등록", HOLD, HOLD, False)
    a, b = [int(v) for v in a], [int(v) for v in b]
    base = max(a[0], a[1], min(a[2], 2))            # 데이터 민감도는 단독으로 2 까지
    g = 1 if a[3] == 3 and base >= 2 else 0
    impact = min(3, base + g)
    score = sum(w * x for w, x in zip(params.w_b, b))
    exposure = 1 if score <= params.cuts[0] else 2 if score <= params.cuts[1] else 3
    cell = params.cell(impact, exposure)
    inherent = "고" if fixed else cell
    residual, down = inherent, False
    if not fixed and inherent != "저" and all(controls) and approved:
        residual, down = TIERS[_RANK[inherent] - 1], True     # 하향은 한 단계
    return TierOutcome(base, g, impact, score, exposure, cell, fixed, banned, None,
                       inherent, residual, down)


def union_levels(members: Sequence[tuple[Sequence[int], Sequence[int]]]
                 ) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Agent 시스템의 항목 수준. 구성원 능력의 합집합(항목별 최댓값)이다.

    구성원이 둘 이상이면 구성원 사이 위임이 있으므로 B3 은 수준 3 이다. 업무를
    여러 Agent 로 나누어 등급을 낮추는 분할 회피를 막는 규칙이다.
    """
    a = tuple(max(int(m[0][k]) for m in members) for k in range(4))
    b = [max(int(m[1][k]) for m in members) for k in range(4)]
    if len(members) >= 2:
        b[2] = 3
    return a, tuple(b)


def near_boundary(score: int | None, params: TierParams = DEFAULT_PARAMS) -> bool:
    """노출 점수가 구간 경계에 붙어 있는가 (경계 양쪽 한 점).

    경계 바로 아래에 건이 몰리면 평가자가 등급을 피해 수준을 고른 흔적일 수 있다.
    """
    if score is None:
        return False
    lo, hi = params.cuts
    return int(score) in (lo, lo + 1, hi, hi + 1)


def breaker_start(severity: int, tier: str) -> int:
    """차단장치 시작 단계 = min(5, 조건 심각도 + 등급 가산). 등급은 운영 등급(고유)."""
    return min(5, int(severity) + BREAKER_ADD[tier])


def _tier_of(a: Sequence[int], b: Sequence[int], params: TierParams) -> int:
    return _RANK[assess(a, b, fixed=fixed_flags(a, b), params=params).inherent]


def monotonicity_violations(params: TierParams = DEFAULT_PARAMS) -> int:
    """항목 수준 전체 조합 6,561개에서 어느 항목이 올라 등급이 내려가는 경우의 수."""
    bad = 0
    for combo in product((1, 2, 3), repeat=8):
        base = _tier_of(combo[:4], combo[4:], params)
        for k in range(8):
            if combo[k] == 3:
                continue
            up = list(combo)
            up[k] += 1
            if _tier_of(up[:4], up[4:], params) < base:
                bad += 1
    return bad


def uniform_distribution(params: TierParams = DEFAULT_PARAMS) -> dict[str, float]:
    """균등 조합 기준 등급 분포. F2 판정을 뺀 행렬 등급이다 (요건정의서 수치와 같은 기준).

    실제 Agent 분포와 다르다. 기관이 보유한 Agent 표본으로 분포를 따로 확인해야 한다.
    """
    n = {t: 0 for t in TIERS}
    for combo in product((1, 2, 3), repeat=8):
        n[assess(combo[:4], combo[4:], params=params).inherent] += 1
    return {t: n[t] / 6561 for t in TIERS}


# ---------------------------------------------------------------- 기준 원장 프레임
def criteria_frame(params: TierParams = DEFAULT_PARAMS) -> pd.DataFrame:
    rows = []
    for it in ITEMS:
        w = params.w_b[int(it.code[1]) - 1] if it.axis == "노출" else None
        for lv, text in enumerate(it.levels, start=1):
            rows.append({"item_code": it.code, "axis": it.axis, "item_name": it.name,
                         "definition": it.definition, "level": lv, "level_text": text,
                         "weight": w, "input_source": it.source,
                         "envelope_dimension": ENVELOPE_DIMENSION[it.code]})
    return pd.DataFrame(rows)


# (규칙 ID, 구분, 조건, 판정, 해제, 판정 주체, 요건)
_RULES: tuple[tuple[str, str, str, str, str | None, str, str], ...] = (
    ("R-I", "산식", "기본 수준 = max(A1, A2, min(A3, 2)), A4 = 3 이고 기본 수준 2 이상이면 1 가산",
     "영향 수준 I (상한 3)", None, "결정론", "CP-MSR-18"),
    ("R-S", "산식", "노출 점수 S = 2 × B1 + B2 + B3 + B4 (범위 5~15)",
     "노출 수준 E: S 7 이하 1, 8~11 은 2, 12 이상 3", None, "결정론", "CP-MSR-18"),
    ("R-SYS", "산식", "Agent 시스템은 구성원 능력의 합집합 (항목별 구성원 최댓값, B3 은 다중 Agent 위임 기준)",
     "구성원 등급 최댓값 이상", None, "결정론", "CP-IDN-17 · CP-MSR-18"),
    ("R-RES", "산식", "통제 가능성 C1~C3 증거 충족과 2인 승인",
     "잔여 등급 한 단계 하향 (고정 조건 해당 건은 불가)",
     "근거 통제가 해제되거나 실패하면 고유 등급으로 복귀", "사람(2인)", "CP-VRF-47 · CP-MSR-19"),
    ("R-UP", "산식", "운영 재측정에서 등급 상승", "상향 즉시 적용, 하향은 증거와 2인 승인",
     None, "결정론", "CP-MSR-19"),
    ("F1", "고정", "법령·감독 기준상 고영향·고위험으로 판정된 사용 사례에 연결",
     "고유 등급 고", "사용 사례 판정 변경", "사람", "CP-IDN-07 · CP-IDN-16"),
    ("F2", "고정", "비신뢰 입력 처리, 민감 정보·시스템 접근, 외부 상태 변경·통신이 한 Agent 또는 Agent 시스템 설계에서 동시에 성립 가능",
     "고유 등급 고", "세 조건 중 하나를 설계에서 제거", "결정론", "CP-MSR-18"),
    ("F3", "고정", "되돌릴 수 없는 대외 효과 행동을 건별 사람 승인 없이 실행하는 설계",
     "고유 등급 고", "건별 사람 승인 또는 보상 행동 등록", "결정론", "CP-MSR-18"),
    ("X1", "불허", "자동확정 금지 영역의 결정을 사람 확정 없이 확정·집행하는 설계",
     "접수 반려", "해제 없음 (설계 변경 후 재접수)", "결정론", "CP-VRF-17 · CP-VRF-45"),
    ("X2", "불허", "금융 핵심 판단 영역에 위임 수준 L5(자율 역할) 적용",
     "접수 반려", "해제 없음", "결정론", "CP-VRF-45"),
    ("X3", "불허", "법령상 금지 용도 또는 기관이 금지한 사용 범주",
     "접수 반려", "해제 없음", "사람", "RL-09 · CP-VRF-45"),
    ("H1", "보류", "필수 입력 미등록 또는 기관 설정 수치 미설정",
     "등급 미부여, 관문 통과 불가", "입력 등록, 설정 승인", "결정론", "RL-16"),
    ("C1", "통제 가능성", "사전 차단: 효과 행동 전건의 강제 경유, 등급 봉투 집행, 승인 정족수 설정",
     "잔여 등급 하향의 증거 1", None, "사람", "CP-VRF-03 · CP-VRF-48 · CP-VRF-18"),
    ("C2", "통제 가능성", "탐지: 실행 전건의 원장 기록과 추적, 결과 대조, 감시 지표와 임계치",
     "잔여 등급 하향의 증거 2", None, "사람", "CM-01 · CM-02 · CP-VRF-09"),
    ("C3", "통제 가능성", "정지·복구: 긴급정지 시험 통과와 소요 시간 기록, 보상 행동 등록, 비상 계획",
     "잔여 등급 하향의 증거 3", None, "사람", "CP-VRF-21 · CP-VRF-49 · CP-VRF-44"),
)


def rule_frame(params: TierParams = DEFAULT_PARAMS) -> pd.DataFrame:
    rows = [{"rule_id": r[0], "rule_type": r[1], "condition": r[2], "outcome": r[3],
             "release": r[4], "judged_by": r[5], "requirement_refs": r[6]}
            for r in _RULES]
    for i in (3, 2, 1):
        for e in (1, 2, 3):
            rows.append({"rule_id": f"M-{i}{e}", "rule_type": "행렬",
                         "condition": f"영향 {i} × 노출 {e}",
                         "outcome": "고유 등급 " + params.cell(i, e), "release": None,
                         "judged_by": "결정론", "requirement_refs": "CP-MSR-18"})
    return pd.DataFrame(rows)


# (관리 영역, 저, 중, 고, 미확정, 요건). 미확정이 None 이면 그 영역에 미확정 행을 두지 않는다.
_POLICY: tuple[tuple[str, str, str, str, str | None, str], ...] = (
    ("개발 승인 (기획 심사)", "간이 경로 / 지정 통제 기능 담당자 확인",
     "표준 경로 / 지정 통제 기능 장 승인", "정밀 경로 / 합의제 의결 기구 의결",
     "관문 통과 불가", "CP-VRF-45"),
    ("개발 검증", "필수 시험 / 동료 검토",
     "저 등급 항목 / 보안 시험(주입, 권한 우회) / 선언 대 실측 대사 / 2선 검토",
     "중 등급 항목 / 개발 조직과 분리된 독립검증 / 레드팀 시험 / 긴급정지·비상 계획 시험",
     None, "CP-VRF-46"),
    ("운영 승인", "지정 통제 기능 담당자 확인", "지정 통제 기능 장 승인",
     "합의제 의결 기구 의결 / 독립검증 결과 보고", "관문 통과 불가", "CP-VRF-45 · CP-VRF-13"),
    ("등급 확정", "지정 통제 기능 담당자", "지정 통제 기능 담당자와 검토자(2인)",
     "지정 통제 기능 2인 / 독립 재확인", None, "CP-VRF-47"),
    ("잔여 등급 하향", "해당 없음", "중에서 저: 지정 통제 기능 장 승인(2인) / 독립 재확인",
     "고에서 중: 합의제 의결 기구 의결 / 고정 조건 해당 건은 불가", None, "CP-VRF-47"),
    ("실행 통제 (RYNTA Bifrost)", "승인된 규칙 범위 안 자동 허용 / 관찰 연결 허용",
     "강제 경유 필수 / 행동 위험등급에 따른 승인",
     "강제 경유 필수 / 효과 행동 전건 2인 승인(완화 불가) / 조회 행동은 정책 판정",
     "고 등급과 동일", "CP-VRF-03 · CP-VRF-18"),
    ("실행 중 차단장치", "조건 심각도 단계에서 시작", "한 단계 가산",
     "두 단계 가산 / 중대 조건은 격리", "고 등급과 동일", "CP-VRF-49"),
    ("차단장치 해제와 운영 재개", "운영 책임자와 지정 통제 기능 담당자", "지정 통제 기능 장",
     "지정 통제 기능 장 / 중대 조건은 합의제 의결 기구 보고", None, "CP-VRF-49 · CP-VRF-22"),
    ("정기 점검", "기관 설정 주기 (예: 연 1회)", "기관 설정 주기 (예: 반기 1회)",
     "기관 설정 주기 (예: 분기 1회) / 정기 독립 재검증", None, "CP-RPT-14"),
    ("위험량 관리 (RYNTA Heimdall)", "위험가중치 기본 / 등급별 총량 한도",
     "위험가중치 가산 / 내부 관리 가산 승수 1 / 전이 심도 2단계",
     "위험가중치 최고 / 내부 관리 가산 승수 2 / 전이 심도 3단계 / 전이 평가 필수 대상",
     "최고 가중치 적용 / 신규 한도 부여 보류", "HM-06 · HM-07 · HM-08 · HM-09"),
    ("한도 상향과 예외", "지정 통제 기능 장", "위험관리 책임자",
     "합의제 의결 기구 / 전사 총량 초과는 이사회 또는 위임받은 위원회", None, "HM-07"),
    ("변경 관리", "봉투 안 변경은 재검증", "봉투 안 변경은 재검증",
     "봉투 안 변경도 지정 통제 기능 확인", None, "CP-VRF-14"),
)


def policy_frame() -> pd.DataFrame:
    rows = []
    for seq, (area, low, mid, high, hold, refs) in enumerate(_POLICY, start=1):
        for tier, text in (("저", low), ("중", mid), ("고", high), (HOLD, hold)):
            if text is not None:
                rows.append({"area_seq": seq, "area": area, "tier": tier,
                             "requirement": text, "requirement_refs": refs})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- 원장 스펙
_LEVEL = dict(min_value=1, max_value=3)
_NOTE_EXAMPLE = ("수준 기준 문구는 패키지 구조 기본값이며 기관이 강화할 수 있다 (RL-17)")

TIER_CRITERIA = TableSpec(
    name="aig_tier_criteria", korean="Agent 위험도 등급 항목과 수준 기준",
    product="PRD-AIG", grain="등급 항목 × 수준 1행",
    columns=(
        C("item_code", "string", "항목 코드", nullable=False, allowed=ITEM_CODES),
        C("axis", "string", "축", nullable=False, allowed=AXES,
          note="영향은 항목 최댓값으로, 노출은 가중 합 구간으로 수준을 낸다"),
        C("item_name", "text", "항목명", nullable=False),
        C("definition", "text", "정의", nullable=False),
        C("level", "int", "수준", nullable=False, **_LEVEL),
        C("level_text", "text", "수준 기준", nullable=False),
        C("weight", "float", "노출 가중치", nullable=True, unit="배수", min_value=0,
          note="노출 항목만 가진다. 예시 설정값이며 기관 승인 대상이다 (aig_tier_param)"),
        C("input_source", "text", "입력 원천", nullable=False),
        C("envelope_dimension", "text", "등급 봉투 구성", nullable=False,
          note="확정 등급의 근거가 된 항목 수준이 운영 승인 때 이 구성의 상한이 된다"),
    ),
    primary_key=("item_code", "level"),
    note=_NOTE_EXAMPLE + ". 영향 = A1~A4, 노출 = B1~B4, 수준 1~3.",
)

TIER_RULE = TableSpec(
    name="aig_tier_rule", korean="Agent 위험도 등급 판정 규칙",
    product="PRD-AIG", grain="판정 규칙 1건당 1행",
    columns=(
        C("rule_id", "string", "규칙 ID", nullable=False),
        C("rule_type", "string", "구분", nullable=False,
          allowed=("산식", "행렬", "고정", "불허", "보류", "통제 가능성")),
        C("condition", "text", "조건", nullable=False),
        C("outcome", "text", "판정", nullable=False),
        C("release", "text", "해제", nullable=True),
        C("judged_by", "string", "판정 주체", nullable=False,
          allowed=("결정론", "사람", "사람(2인)"),
          note="사람 판정 조건(F1, X3)은 입력이 빠지면 등급이 낮게 나온다. "
               "입력 누락은 등급 확정 절차(독립 재확인)가 잡는다"),
        C("requirement_refs", "text", "요건", nullable=False),
    ),
    primary_key=("rule_id",),
    note="산식, 행렬(영향 × 노출), 고정 '고' 조건, 불허 조건, 산정 보류, 통제 가능성. "
         "행렬 값은 예시 설정값이다.",
)

TIER_POLICY = TableSpec(
    name="aig_tier_policy", korean="등급별 관리 기준 (결정 권한·필수 통제)",
    product="PRD-AIG", grain="관리 영역 × 등급 1행",
    columns=(
        C("area_seq", "int", "영역 순번", nullable=False, min_value=1),
        C("area", "text", "관리 영역", nullable=False),
        C("tier", "string", "등급", nullable=False, allowed=TIERS + (HOLD,)),
        C("requirement", "text", "관리 기준", nullable=False),
        C("requirement_refs", "text", "요건", nullable=False),
    ),
    primary_key=("area_seq", "tier"),
    note="패키지 구조 기본값이다. 결재자, 의결 기구명, 주기와 표본 비율은 기관 설정이다. "
         "의결과 결재는 사람과 기구가 하고 원장은 그 결과 기록을 받는다.",
)

TIER_INPUT = TableSpec(
    name="aig_tier_input", korean="Agent 등급 항목 수준 입력",
    product="PRD-AIG", grain="산정 단위 × 시점 1행",
    columns=(
        C("unit_id", "string", "산정 단위 ID", nullable=False),
        C("stage", "string", "산정 시점", nullable=False, allowed=STAGES),
        C("input_source", "text", "입력 원천", nullable=False),
        C("a1", "int", "A1 업무 중대성", nullable=True, **_LEVEL),
        C("a2", "int", "A2 행동 효과·가역성", nullable=True, **_LEVEL),
        C("a3", "int", "A3 데이터 민감도", nullable=True, **_LEVEL),
        C("a4", "int", "A4 영향 규모", nullable=True, **_LEVEL),
        C("b1", "int", "B1 자율성", nullable=True, **_LEVEL),
        C("b2", "int", "B2 비신뢰 입력 노출", nullable=True, **_LEVEL),
        C("b3", "int", "B3 구성 복잡성", nullable=True, **_LEVEL),
        C("b4", "int", "B4 모델·제3자 불확실성", nullable=True, **_LEVEL,
          note="비어 있으면 산정 보류(H1)다. 0 이나 1 로 채우지 않는다"),
        C("f1_high_impact", "bool", "F1 고영향 판정", nullable=False,
          note="사람 판정 입력"),
        C("f3_no_per_action_approval", "bool", "F3 건별 승인 없는 비가역 대외 행동",
          nullable=False),
        C("x1_auto_decision", "bool", "X1 자동확정 금지 영역 자동 확정", nullable=False),
        C("x2_core_judgment_l5", "bool", "X2 핵심 판단 영역 자율 역할", nullable=False),
        C("x3_prohibited_use", "bool", "X3 금지 용도", nullable=False,
          note="사람 판정 입력"),
        C("c1_prevent", "bool", "C1 사전 차단 증거", nullable=False),
        C("c2_detect", "bool", "C2 탐지 증거", nullable=False),
        C("c3_stop_recover", "bool", "C3 정지·복구 증거", nullable=False),
        C("dual_approval", "bool", "하향 2인 승인", nullable=False),
        C("derived_from_members", "bool", "구성원 합집합 산출", nullable=False,
          note="Agent 시스템 행은 입력이 아니라 구성원 행에서 낸 값이다"),
    ),
    primary_key=("unit_id", "stage"),
    foreign_keys=(FK(("unit_id",), "aig_agent_unit", ("unit_id",)),),
    note="세 시점에 같은 항목을 쓴다. 예정은 선언, 확정은 등록값과 실측, 운영은 관측이다.",
)

TIER_ASSESSMENT = TableSpec(
    name="aig_tier_assessment", korean="Agent 위험도 등급 산정 결과",
    product="PRD-AIG", grain="산정 단위 × 시점 1행",
    columns=(
        C("unit_id", "string", "산정 단위 ID", nullable=False),
        C("stage", "string", "산정 시점", nullable=False, allowed=STAGES),
        C("impact_base", "int", "영향 기본 수준", nullable=True, **_LEVEL),
        C("scale_add", "int", "영향 규모 가산 g", nullable=True, min_value=0, max_value=1),
        C("impact_level", "int", "영향 수준 I", nullable=True, **_LEVEL),
        C("exposure_score", "int", "노출 점수 S", nullable=True, min_value=5, max_value=15),
        C("exposure_level", "int", "노출 수준 E", nullable=True, **_LEVEL),
        C("matrix_tier", "string", "행렬 등급", nullable=True, allowed=TIERS,
          note="고정 조건을 적용하기 전의 행렬(I, E) 값"),
        C("fixed_flags", "text", "고정 조건", nullable=True),
        C("banned_flags", "text", "불허 조건", nullable=True),
        C("hold_reason", "text", "보류 사유", nullable=True),
        C("inherent_tier", "string", "고유 등급", nullable=False, allowed=TIER_STATES,
          note="승인 요건과 차단장치는 이 등급을 쓴다"),
        C("controls_met", "bool", "통제 가능성 충족", nullable=False),
        C("downgraded", "bool", "잔여 하향 여부", nullable=False),
        C("residual_tier", "string", "잔여 등급", nullable=False, allowed=TIER_STATES,
          note="감내수준, 한도, 가산은 이 등급을 쓴다"),
        C("quantity_tier", "string", "위험량 적용 등급", nullable=True, allowed=TIERS,
          note="잔여 등급. 미확정은 최고 등급으로 본다. 불허는 운영하지 않으므로 비운다"),
        C("decision_route", "text", "결정 권한", nullable=False,
          note="고유 등급 기준 (패키지 구조 기본값)"),
        C("breaker_add", "int", "차단장치 등급 가산", nullable=True, min_value=0,
          max_value=2),
        C("near_boundary", "bool", "구간 경계 근처", nullable=False),
        C("criteria_version", "string", "기준 판본", nullable=False),
    ),
    primary_key=("unit_id", "stage"),
    foreign_keys=(FK(("unit_id", "stage"), "aig_tier_input", ("unit_id", "stage")),),
    note="결정론 산정 결과다. 확정과 하향은 사람이 하며 이 원장은 그 입력(통제 증거, "
         "2인 승인)을 받아 계산만 한다.",
)

TIER_ENVELOPE = TableSpec(
    name="aig_tier_envelope", korean="등급 봉투와 항목별 대사",
    product="PRD-AIG", grain="산정 단위 × 등급 항목 1행",
    columns=(
        C("unit_id", "string", "산정 단위 ID", nullable=False),
        C("item_code", "string", "항목 코드", nullable=False, allowed=ITEM_CODES),
        C("envelope_dimension", "text", "등급 봉투 구성", nullable=False),
        C("declared_level", "int", "예정 수준 (선언)", nullable=True, **_LEVEL),
        C("confirmed_level", "int", "확정 수준 (봉투 상한)", nullable=True, **_LEVEL),
        C("observed_level", "int", "운영 수준 (관측)", nullable=True, **_LEVEL),
        C("declared_gap", "string", "선언 대 실측", nullable=False,
          allowed=("일치", "실측 상향", "실측 하향", "대사 불가")),
        C("envelope_breach", "bool", "봉투 이탈", nullable=False,
          note="관측 수준이 봉투 상한을 넘었다. 실행 전 차단과 재등급 사유다"),
        C("observation_missing", "bool", "관측 결손", nullable=False),
    ),
    primary_key=("unit_id", "item_code"),
    foreign_keys=(FK(("unit_id",), "aig_agent_unit", ("unit_id",)),),
    note="봉투는 확정 등급의 근거가 된 항목별 상한이다. 봉투 밖 행동은 실행 전에 "
         "막히고 재등급 사유로 남는다.",
)

TIER_MIGRATION = TableSpec(
    name="aig_tier_migration", korean="Agent 등급 이행",
    product="PRD-AIG", grain="기간 초 등급 × 기간 말 등급 1행",
    columns=(
        C("from_tier", "string", "기간 초 등급 (확정)", nullable=False, allowed=TIERS),
        C("to_tier", "string", "기간 말 등급 (운영)", nullable=False,
          allowed=TIERS + (HOLD,)),
        C("n_units", "int", "산정 단위 수", nullable=False, min_value=0),
        C("direction", "string", "방향", nullable=False,
          allowed=("유지", "상향", "하향", "보류")),
        C("unit_ids", "text", "해당 단위", nullable=True),
    ),
    primary_key=("from_tier", "to_tier"),
    note="등급 사이 이동 건수다. 사고 발생을 전제로 한 전이 계수(aig_contagion)와 "
         "다른 것이다. 위험량 등급(잔여) 기준이며 집계 단위만 센다.",
)

TIER_SPECS: tuple[TableSpec, ...] = (
    TIER_CRITERIA, TIER_RULE, TIER_POLICY, TIER_INPUT, TIER_ASSESSMENT,
    TIER_ENVELOPE, TIER_MIGRATION)
