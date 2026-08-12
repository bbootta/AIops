"""한도 정의 원장. `LimitEngine`이 읽는 한도의 유일한 출처.

## 왜 원장인가

한도 5종(동일차주·섹터·국가·자산군·등급)의 정의가 `pipeline.py`의
`_stage_limits_concentration` 안에 리스트 리터럴로 박혀 있었다. 박혀 있으면
화면에 나오지 않고, 화면에 없으면 "이 2조는 누가 언제 승인한 값인가"에 답할
자리가 없다. 한도관리는 승인 이력이 통제의 전부인 영역이므로 그 자리가 비면
한도표가 아니라 숫자 목록이 된다.

## 규정 한도와 내부한도를 컬럼으로 나눈다

동일차주 25%만 법령 근거가 있다(은행법 제35조 제1항). 나머지 4종은 내규가
정하는 내부한도이며 승인기구와 승인일이 있어야 효력이 있다. `basis` 컬럼이
그 둘을 구분하고, `evidence_status`가 근거를 어디까지 확인했는지 적는다.

**분모 주의.** 은행법 제35조 제1항의 한도 분모는 **자기자본(총자본)**이다
(`regulatory/forms_fss_compliance.py` 참조). 이 원장과 `LimitEngine`은
기본자본(Tier1)을 분모로 쓴다. Tier1 ≤ 자기자본이므로 결과는 보수적이나
규정 산식과 같지 않다. 그 사실을 `note` 컬럼에 남긴다.

## 승인은 아직 없다

5행 전건이 `approved_on` 미기재다. 실제 이사회·리스크관리위원회 의결 회차를
확인하지 않았고 지어내지 않는다. `unapproved_limits()`가 그 행을 돌려주며
화면·검증이 그대로 실어야 한다.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import pandas as pd

from risk_lib.datamodel.spec import ColumnSpec as C, TableSpec
from risk_lib.limits.limit_engine import LimitDefinition

__all__ = [
    "LIMIT_BASES", "LIMIT_TYPES", "THRESHOLD_UNITS", "APPROVAL_BODIES",
    "EVIDENCE_STATUS", "LIMIT_DEFINITION", "LIMIT_TABLES", "LimitWarning",
    "LimitLedgerWarning",
    "build_limit_definitions", "limit_definitions", "unapproved_limits",
]


# ---------------------------------------------------------------- 어휘

LIMIT_BASES: tuple[str, ...] = ("규정", "내부한도")
LIMIT_TYPES: tuple[str, ...] = ("동일차주", "섹터", "국가", "자산군", "등급")
# 임계의 단위가 곧 산식 유형이다. KRW는 절대금액, ratio_tier1은 기본자본 비율.
THRESHOLD_UNITS: tuple[str, ...] = ("KRW", "ratio_tier1")
APPROVAL_BODIES: tuple[str, ...] = ("이사회", "리스크관리위원회", "법령")
EVIDENCE_STATUS: tuple[str, ...] = (
    "원문확인", "2차자료", "원문미확인·현행계승", "재량·미규정", "내부가정",
    "미확인")

# 원장의 단위 → 엔진의 산식 유형. 소비처가 두 어휘를 각자 매핑하면 원장에
# 단위를 추가할 때 어디를 고쳐야 하는지가 흩어진다.
_ENGINE_BASIS_BY_UNIT: dict[str, str] = {
    "KRW": "absolute", "ratio_tier1": "pct_tier1"}


@dataclass(frozen=True)
class LimitWarning:
    """원장 칸이 비어 한도를 엔진에 싣지 못한 사건."""
    limit_id: str
    field: str
    reason: str


class LimitLedgerWarning(UserWarning):
    """한도 원장 결측으로 한도를 건너뛸 때 발생."""


# ---------------------------------------------------------------- 스펙

LIMIT_DEFINITION = TableSpec(
    name="lim_limit_definition", korean="한도 정의 원장", product="PRD-RDM",
    grain="한도 1건당 1행",
    columns=(
        C("limit_id", "string", "한도 식별자", nullable=False),
        C("limit_type", "string", "한도 유형", nullable=False,
          allowed=LIMIT_TYPES),
        C("scope_key", "string", "적용 축", nullable=False,
          note="포트폴리오 원장의 컬럼명. 이 축의 값마다 한도가 걸린다"),
        C("basis", "string", "근거 구분", nullable=False, allowed=LIMIT_BASES,
          note="'규정'은 법령·감독규정이 정한 한도, '내부한도'는 내규가 정하고 "
               "승인기구 의결로 효력이 생기는 한도"),
        C("threshold_value", "float", "한도 임계", nullable=True, unit="가변",
          min_value=0.0,
          note="단위는 같은 행의 threshold_unit을 본다. NULL이면 엔진이 그 "
               "한도를 싣지 않고 경고를 남긴다"),
        C("threshold_unit", "string", "임계 단위", nullable=False,
          allowed=THRESHOLD_UNITS),
        C("threshold_formula", "text", "임계 산식", nullable=False,
          note="상대기준의 분모를 문장으로 남긴다. 비율만 있으면 무엇의 "
               "비율인지가 원장에서 사라진다"),
        C("citation", "text", "근거", nullable=True),
        C("approval_body", "string", "승인기구", nullable=True,
          allowed=APPROVAL_BODIES),
        C("approved_on", "date", "승인일", nullable=True),
        C("note", "text", "비고", nullable=True),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("limit_id",),
    note="한도 5종 전건이 승인일 미기재다. 실제 이사회·리스크관리위원회 의결 "
         "회차를 확인하지 않았고 지어내지 않는다. 동일차주 한도는 법령 근거가 "
         "있으나 원문을 직접 열람하지 않아 '원문미확인·현행계승'이다.",
)

LIMIT_TABLES: tuple[TableSpec, ...] = (LIMIT_DEFINITION,)


# ---------------------------------------------------------------- 빌더

def build_limit_definitions() -> pd.DataFrame:
    """한도 정의 원장. 이 함수가 곧 한도 등재·수기입력 프로세스다.

    한도 체계는 차원 하나로 서지 않는다. 동일차주·섹터·국가만 두면 화면이
    한도관리가 아니라 국가 한도 한 줄이 된다. 감독규정·내규가 실제로 두는 축을
    덮되, 각 축의 근거 구분과 승인기구를 함께 적는다.

    임계값은 `pipeline._stage_limits_concentration`에 박혀 있던 값을 그대로
    옮긴 것이다. 값을 바꾸지 않았으므로 산출은 이전과 같고, 달라진 것은 그
    값이 원장에 있어 화면·검증에 보인다는 점이다.
    """
    _C35 = ("은행법 제35조 제1항 (동일차주 신용공여 한도). 저장소 현행 표기를 "
            "계승했으며 법령 원문을 직접 열람하지 않았다")
    _NOTE35 = ("규정의 한도 분모는 자기자본(총자본)이다. 이 원장과 LimitEngine은 "
               "기본자본(Tier1)을 분모로 쓴다. Tier1 ≤ 자기자본이므로 결과는 "
               "보수적이나 규정 산식과 같지 않다")
    _INT = ("규정 근거 없음. 포트폴리오 집중을 억제하기 위해 내규가 정하는 "
            "내부한도이며 승인기구 의결이 효력 요건이다")
    _NOTE_INT = "실제 의결 회차·승인일을 확인하지 않았다. 승인 전에는 결재 근거가 없다"
    # (limit_id, limit_type, scope_key, basis, value, unit, formula,
    #  citation, approval_body, note, evidence_status)
    rows = (
        ("동일차주_Tier1_25pct", "동일차주", "obligor_id", "규정",
         0.25, "ratio_tier1", "기본자본(Tier1) × 25%",
         _C35, "법령", _NOTE35, "원문미확인·현행계승"),
        ("섹터_총노출_2조", "섹터", "sector", "내부한도",
         2.0e12, "KRW", "절대금액 2조원",
         _INT, "리스크관리위원회", _NOTE_INT, "내부가정"),
        ("국가_총노출_5조", "국가", "country", "내부한도",
         5.0e12, "KRW", "절대금액 5조원",
         _INT, "리스크관리위원회", _NOTE_INT, "내부가정"),
        ("자산군_총노출_7조", "자산군", "asset_class", "내부한도",
         7.0e12, "KRW", "절대금액 7조원",
         _INT, "리스크관리위원회", _NOTE_INT, "내부가정"),
        ("등급_총노출_6조", "등급", "rating", "내부한도",
         6.0e12, "KRW", "절대금액 6조원",
         _INT, "리스크관리위원회", _NOTE_INT, "내부가정"),
    )
    out = pd.DataFrame([
        {"limit_id": lid, "limit_type": ltype, "scope_key": scope,
         "basis": basis, "threshold_value": float(val),
         "threshold_unit": unit, "threshold_formula": formula,
         "citation": cit, "approval_body": body, "approved_on": None,
         "note": note, "evidence_status": ev}
        for (lid, ltype, scope, basis, val, unit, formula, cit, body, note,
             ev) in rows
    ])
    return out.astype({"threshold_value": "float64"})


# ---------------------------------------------------------------- 소비

def limit_definitions(ledger: pd.DataFrame | None = None
                      ) -> list[LimitDefinition]:
    """원장 행을 `LimitEngine`이 받는 정의 객체로 옮긴다.

    임계가 NULL이거나 단위를 해석할 수 없는 행은 **싣지 않고 경고를 남긴다**.
    임의의 기본값을 넣으면 미입력 한도가 통과한 한도로 보인다.

    다섯 행 모두 `value=None`이다. 축의 값마다 한도가 걸리는 형태이며, 특정
    버킷만 다른 한도를 두는 행은 아직 없다.
    """
    if ledger is None:
        ledger = build_limit_definitions()
    out: list[LimitDefinition] = []
    skipped: list[LimitWarning] = []
    for _, r in ledger.iterrows():
        lid = str(r["limit_id"])
        if pd.isna(r["threshold_value"]):
            skipped.append(LimitWarning(
                lid, "threshold_value",
                f"임계 미입력(evidence_status={r['evidence_status']}). "
                "한도를 싣지 않는다"))
            continue
        unit = str(r["threshold_unit"])
        if unit not in _ENGINE_BASIS_BY_UNIT:
            skipped.append(LimitWarning(
                lid, "threshold_unit", f"해석할 수 없는 단위 {unit!r}"))
            continue
        out.append(LimitDefinition(
            lid, str(r["scope_key"]), None, float(r["threshold_value"]),
            basis=_ENGINE_BASIS_BY_UNIT[unit]))
    for w in skipped:
        warnings.warn(f"{w.limit_id}: {w.reason}", LimitLedgerWarning,
                      stacklevel=2)
    return out


def unapproved_limits(ledger: pd.DataFrame | None = None) -> pd.DataFrame:
    """승인기구 또는 승인일이 빈 **내부한도** 행.

    규정 한도의 효력 근거는 법령이므로 내부 의결일을 요구하지 않는다. 내부한도는
    승인기구 의결이 효력 요건이라 승인일이 비면 결재 근거가 없다. 이 함수가
    돌려주는 행은 화면과 검증에 그대로 실려야 한다.
    """
    if ledger is None:
        ledger = build_limit_definitions()
    internal = ledger[ledger["basis"] == "내부한도"]
    return internal[internal["approval_body"].isna()
                    | internal["approved_on"].isna()].copy()
