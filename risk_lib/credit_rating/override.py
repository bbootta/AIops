"""등급변경(Override) 원장과 사후성과 평가 (BNK-CRM-009).

**무엇이 없었나.** `crm_rating.override_flag`는 컬럼만 있고 값이 항상 0이며,
"Override는 승인 원장과 대사돼야 한다"는 주석만 달려 있었다. 대사할 원장이
없었다. [별표 3] 165.가는 등급변경의 **방법·가능 범위·책임자**에 대한 명확한
기준을, 165.나는 모형등급의 인적 변경을 모니터링하는 절차와 책임자 명시를,
165.다는 변경 후 성과 평가를 요구한다. 세 가지 모두 원장이 있어야 확인된다.

**조정 범위는 비워 둔다.** 165.가(2)는 "등급변경의 가능한 범위"에 대한 기준을
갖추라고만 하고 몇 단계까지인지 정하지 않는다. 이 하네스에는 이사회·리스크
관리위원회가 승인한 내부기준 원장이 없으므로 `crm_override_reason.max_notch`는
NULL이고 `evidence_status='재량·미규정'`이다. 판정 엔진은 NULL을 만나면 조용히
통과시키지 않고 `within_policy_range='미판정'`으로 남기고 경고를 반환한다.
승인된 내부기준이 생기면 그 원장의 값만 채우면 판정이 붙는다.

**사후성과는 계산한다.** 165.다의 성과 평가는 관측 부도율과 모형등급 예상
부도율의 대조로 계산할 수 있다. 다만 "성과가 양호한가"의 합격 임계는 규정에도
1차자료에도 없으므로 지표만 내고 판정 칸은 '미판정'으로 둔다.

**미등재.** TableSpec은 배선 단계에서 카탈로그에 등재한다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from risk_lib.credit_rating.requirements import EVIDENCE_STATUS
from risk_lib.credit_rating.sample import ASSESSMENTS
from risk_lib.datamodel.spec import ColumnSpec as C, ForeignKey as FK, TableSpec
from risk_lib.models.rating import DEFAULT_MASTER_SCALE, rating_to_pd_midpoint

__all__ = [
    "OVERRIDE_DIRECTIONS", "RANGE_VERDICTS", "OVERRIDE_REASON", "OVERRIDE",
    "OVERRIDE_PERFORMANCE", "OVERRIDE_TABLES", "OverrideWarning",
    "build_override_reasons", "build_overrides", "assess_override_range",
    "build_override_performance", "reconcile_override_flag",
]

OVERRIDE_DIRECTIONS: tuple[str, ...] = ("상향", "하향", "양방향")
RANGE_VERDICTS: tuple[str, ...] = ("적합", "초과", "미판정")


class OverrideWarning(UserWarning):
    """조정 범위 기준이 없어 판정하지 못했다는 신호."""


OVERRIDE_REASON = TableSpec(
    name="crm_override_reason", korean="등급변경 사유·범위 기준",
    product="PRD-CRM",
    grain="등급변경 사유코드 1개당 1행",
    columns=(
        C("reason_code", "string", "사유코드", nullable=False),
        C("korean", "text", "사유", nullable=False),
        C("direction", "string", "조정 방향", nullable=False,
          allowed=OVERRIDE_DIRECTIONS),
        C("max_notch", "float", "최대 조정 단계", nullable=True, unit="notches",
          min_value=0.0,
          citation="[별표 3] 165.가(2) 등급변경의 가능한 범위",
          note="원문은 범위 기준을 갖추라고만 하고 단계 수를 정하지 않는다. "
               "승인된 내부기준이 없는 동안은 NULL이며 범위를 판정하지 않는다"),
        C("approver_role", "text", "변경 책임자", nullable=True,
          citation="[별표 3] 165.가(3) 등급변경의 책임자"),
        C("monitoring_required", "bool", "모니터링 대상", nullable=False,
          citation="[별표 3] 165.나"),
        C("citation", "text", "근거", nullable=False),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("reason_code",),
    note="165.가의 세 가지(방법·범위·책임자) 중 방법과 책임자는 적을 수 있고 "
         "범위는 승인값이 없어 비어 있다. 비어 있음이 보이는 것이 목적이다.",
)

OVERRIDE = TableSpec(
    name="crm_override", korean="등급변경 원장", product="PRD-CRM",
    grain="차주 × 기준일 1행 (변경이 있는 차주만)",
    columns=(
        C("obligor_id", "string", "차주 식별자", nullable=False),
        C("asof", "date", "기준일", nullable=False),
        C("model_id", "string", "모형 식별자", nullable=False),
        C("model_grade", "string", "모형등급", nullable=False),
        C("final_grade", "string", "최종등급", nullable=False),
        C("notch_delta", "int", "조정 단계", nullable=False,
          note="양수는 등급 상향(리스크 하향), 음수는 하향. 부호 규약을 원장에 "
               "적지 않으면 화면마다 반대로 그려진다"),
        C("reason_code", "string", "사유코드", nullable=False),
        C("requested_by", "text", "신청 조직", nullable=False),
        C("approved_by", "text", "승인자", nullable=True,
          note="NULL이면 165.가(3) 책임자 요건을 만족하지 못한 변경이다"),
        C("approval_date", "date", "승인일", nullable=True),
        C("within_policy_range", "string", "범위 판정", nullable=False,
          allowed=RANGE_VERDICTS),
        C("model_pd", "float", "모형 PD", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("final_pd", "float", "최종 PD", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0,
          note="최종등급의 master scale 중앙값. 등급을 바꾸면 PD도 바뀐다는 "
               "사실이 원장에 남아야 RWA 영향이 추적된다"),
        C("citation", "text", "근거", nullable=False),
    ),
    primary_key=("obligor_id", "asof"),
    foreign_keys=(FK(("obligor_id",), "rdm_obligor", ("obligor_id",)),
                  FK(("model_id",), "crm_model", ("model_id",)),
                  FK(("reason_code",), "crm_override_reason", ("reason_code",))),
)

OVERRIDE_PERFORMANCE = TableSpec(
    name="crm_override_performance", korean="등급변경 사후성과",
    product="PRD-CRM",
    grain="사유코드 × 기준일 1행",
    columns=(
        C("reason_code", "string", "사유코드", nullable=False),
        C("asof", "date", "기준일", nullable=False),
        C("n_overrides", "int", "변경 건수", nullable=False, min_value=0),
        C("n_default", "int", "관측 부도 건수", nullable=False, min_value=0),
        C("dr_observed", "float", "관측 부도율", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("pd_model_mean", "float", "모형등급 평균 PD", nullable=False,
          unit="ratio", min_value=0.0, max_value=1.0),
        C("pd_final_mean", "float", "최종등급 평균 PD", nullable=False,
          unit="ratio", min_value=0.0, max_value=1.0),
        C("model_gap", "float", "관측 − 모형등급 PD", nullable=False,
          unit="ratio"),
        C("final_gap", "float", "관측 − 최종등급 PD", nullable=False,
          unit="ratio",
          note="최종등급 격차가 모형등급 격차보다 작으면 그 사유의 변경이 "
               "예측을 개선했다는 뜻이다. 개선 여부의 합격 임계는 규정에 없다"),
        C("n_unapproved", "int", "승인자 없는 변경", nullable=False, min_value=0,
          citation="[별표 3] 165.가(3)"),
        C("assessment", "string", "판정", nullable=False, allowed=ASSESSMENTS),
        C("citation", "text", "근거", nullable=False),
    ),
    primary_key=("reason_code", "asof"),
    foreign_keys=(FK(("reason_code",), "crm_override_reason", ("reason_code",)),),
    note="165.다(변경 후 성과 평가)의 증적.",
)

OVERRIDE_TABLES = (OVERRIDE_REASON, OVERRIDE, OVERRIDE_PERFORMANCE)


# (사유코드, 사유, 방향, 책임자)
_REASONS: tuple[tuple[str, str, str, str | None], ...] = (
    ("OVR-FIN", "최근 재무제표 반영(모형 기준일 이후 결산)", "양방향",
     "여신심사부장"),
    ("OVR-GRP", "계열·모기업 지원 가능성", "상향", "여신심사부장"),
    ("OVR-EVT", "소송·제재 등 중요 사건", "하향", "리스크관리부장"),
    ("OVR-IND", "업황 급변", "양방향", "리스크관리부장"),
    ("OVR-DAT", "모형 입력 데이터 오류", "양방향", "모형검증부장"),
)


def build_override_reasons() -> pd.DataFrame:
    """등급변경 사유·범위 기준 원장 (165.가).

    최대 조정 단계는 채우지 않는다. 원문이 수치를 주지 않고 승인된 내부기준도
    없다. 여기서 임의의 숫자를 넣으면 그 숫자가 범위 판정의 근거로 쓰인다.
    """
    rows = [{
        "reason_code": code,
        "korean": korean,
        "direction": direction,
        "max_notch": None,
        "approver_role": approver,
        "monitoring_required": True,
        "citation": "[별표 3] 165.가 · 165.나",
        "evidence_status": "재량·미규정",
    } for code, korean, direction, approver in _REASONS]
    df = pd.DataFrame(rows, columns=OVERRIDE_REASON.column_names)
    df["max_notch"] = pd.to_numeric(df["max_notch"],
                                    errors="coerce").astype("float64")
    return df


def _grade_index() -> dict[str, int]:
    return {g.grade: i for i, g in enumerate(DEFAULT_MASTER_SCALE)}


def build_overrides(scores: pd.DataFrame, reasons: pd.DataFrame, *,
                    asof: str, seed: int, override_share: float,
                    unapproved_share: float) -> pd.DataFrame:
    """등급변경 원장(합성)을 만든다.

    실제 은행은 심사역 신청과 책임자 승인 워크플로에서 받는다. 이 하네스에는
    그 워크플로가 없으므로 결정론 난수로 만든다. 승인자가 빠진 건을 일부러
    섞어 둔다. 전건 승인된 원장만 만들면 165.가(3) 점검이 어떤 입력에서도
    통과하므로 점검이 발동하는지 확인할 수 없다.
    """
    if scores.empty or reasons.empty:
        return pd.DataFrame(columns=OVERRIDE.column_names)
    rng = np.random.default_rng(seed + 8300)
    idx = _grade_index()
    n = len(scores)
    pick = rng.random(n) < override_share
    sel = scores[pick].copy()
    if sel.empty:
        return pd.DataFrame(columns=OVERRIDE.column_names)

    codes = reasons["reason_code"].to_numpy()
    dirs = dict(zip(reasons["reason_code"], reasons["direction"]))
    approvers = dict(zip(reasons["reason_code"], reasons["approver_role"]))
    m = len(sel)
    chosen = codes[rng.integers(0, len(codes), m)]
    steps = rng.integers(1, 4, m)          # 1~3 단계
    unapproved = rng.random(m) < unapproved_share

    rows = []
    for (_, r), code, step, no_appr in zip(sel.iterrows(), chosen, steps,
                                           unapproved):
        direction = dirs[code]
        if direction == "상향":
            delta = int(step)
        elif direction == "하향":
            delta = -int(step)
        else:
            delta = int(step) * (1 if rng.random() < 0.5 else -1)
        cur = idx.get(str(r["model_grade"]))
        if cur is None:
            continue
        # 등급 상향은 master scale에서 인덱스가 작아지는 방향이다.
        new_i = int(np.clip(cur - delta, 0, len(DEFAULT_MASTER_SCALE) - 1))
        if new_i == cur:
            # 최상·최하 등급에서 상한에 걸린 경우다. 등급이 움직이지 않은 건을
            # 등급변경으로 적으면 165.다의 성과 평가 모집단이 부풀어 오른다.
            continue
        final_grade = DEFAULT_MASTER_SCALE[new_i].grade
        rows.append({
            "obligor_id": r["obligor_id"],
            "asof": asof,
            "model_id": r["model_id"],
            "model_grade": r["model_grade"],
            "final_grade": final_grade,
            "notch_delta": int(cur - new_i),
            "reason_code": code,
            "requested_by": "여신심사부",
            "approved_by": None if no_appr else approvers[code],
            "approval_date": None if no_appr else asof,
            "within_policy_range": "미판정",
            "model_pd": float(r["model_pd"]),
            "final_pd": float(rating_to_pd_midpoint(final_grade)),
            "citation": "[별표 3] 165.가 · 165.나",
        })
    return pd.DataFrame(rows, columns=OVERRIDE.column_names)


def assess_override_range(overrides: pd.DataFrame,
                          reasons: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """조정 단계가 사유별 허용 범위 안인지 판정한다.

    허용 범위가 NULL이면 판정하지 않고 경고를 낸다. 범위 기준이 없다는 것과
    범위를 지켰다는 것은 다른 사건이므로 같은 값('적합')으로 접지 않는다.
    """
    if overrides.empty:
        return overrides, []
    limits = dict(zip(reasons["reason_code"], reasons["max_notch"]))
    out = overrides.copy()
    verdicts = []
    missing: set[str] = set()
    for code, delta in zip(out["reason_code"], out["notch_delta"]):
        cap = limits.get(code)
        if cap is None or pd.isna(cap):
            missing.add(str(code))
            verdicts.append("미판정")
        else:
            verdicts.append("적합" if abs(int(delta)) <= float(cap) else "초과")
    out["within_policy_range"] = verdicts
    warns = []
    if missing:
        warns.append(
            "등급변경 허용 범위(max_notch)가 비어 있어 범위를 판정하지 않았다: "
            + ", ".join(sorted(missing))
            + ". [별표 3] 165.가(2)는 범위 기준 보유를 요구하나 단계 수를 "
              "정하지 않으므로 승인된 내부기준이 필요하다")
    return out, warns


def build_override_performance(overrides: pd.DataFrame,
                               outcomes: pd.DataFrame, *,
                               asof: str) -> pd.DataFrame:
    """사유별 사후성과 원장 (165.다).

    outcomes는 차주별 실제 부도(`obligor_id`, `default_12m`)다. 관측 부도율을
    모형등급 PD와 최종등급 PD 각각에 대조해 변경이 예측을 개선했는지 본다.
    개선 여부의 합격 임계는 규정에 없으므로 판정 칸은 '미판정'이다.
    """
    if overrides.empty:
        return pd.DataFrame(columns=OVERRIDE_PERFORMANCE.column_names)
    j = overrides.merge(outcomes[["obligor_id", "default_12m"]],
                        on="obligor_id", how="left")
    j["default_12m"] = pd.to_numeric(j["default_12m"], errors="coerce").fillna(0)
    rows = []
    for code, g in j.groupby("reason_code", sort=True):
        n = int(len(g))
        n_def = int(g["default_12m"].sum())
        dr = float(n_def / n) if n else 0.0
        pd_model = float(g["model_pd"].mean())
        pd_final = float(g["final_pd"].mean())
        rows.append({
            "reason_code": code, "asof": asof,
            "n_overrides": n, "n_default": n_def, "dr_observed": dr,
            "pd_model_mean": pd_model, "pd_final_mean": pd_final,
            "model_gap": float(dr - pd_model),
            "final_gap": float(dr - pd_final),
            "n_unapproved": int(g["approved_by"].isna().sum()),
            "assessment": "미판정",
            "citation": "[별표 3] 165.다",
        })
    return pd.DataFrame(rows, columns=OVERRIDE_PERFORMANCE.column_names)


def reconcile_override_flag(rating: pd.DataFrame,
                            overrides: pd.DataFrame) -> pd.DataFrame:
    """등급 이력의 override_flag와 등급변경 원장을 대사한다.

    `crm_rating.override_flag`가 전건 0인데 등급변경 원장에 건이 있으면 두 원장이
    갈라진 것이다. 불일치 행만 돌려주므로 빈 결과가 곧 일치다.
    """
    if rating.empty:
        return pd.DataFrame(columns=["obligor_id", "asof", "flag_in_rating",
                                     "in_override_ledger"])
    flags = rating[["obligor_id", "asof", "override_flag"]].copy()
    flags["override_flag"] = pd.to_numeric(flags["override_flag"],
                                           errors="coerce").fillna(0).astype(int)
    ov = set(zip(overrides.get("obligor_id", pd.Series(dtype=str)),
                 overrides.get("asof", pd.Series(dtype=str))))
    flags["in_override_ledger"] = [
        int((o, a) in ov) for o, a in zip(flags["obligor_id"], flags["asof"])]
    bad = flags[flags["override_flag"] != flags["in_override_ledger"]]
    return bad.rename(columns={"override_flag": "flag_in_rating"}).reset_index(
        drop=True)
