"""리스크 인벤토리와 내부자본 매핑 (BNK-ST-001).

`icaap.economic_capital`은 신용·시장·운영·금리 네 유형의 경제자본을 통합한다.
그 네 유형이 은행이 지는 리스크의 전부라는 판단은 어디에도 기록돼 있지 않다.
유동성·집중·평판·전략·모형·기후 리스크를 자본으로 잡지 않기로 했다면 그
판단과 근거가 원장에 남아야 한다. 인벤토리가 없으면 통합액이 무엇을 뺀
값인지 감사에서 말할 수 없다.

원장 네 장으로 구성한다.

  icaap_risk_taxonomy       리스크 유형 정의와 Pillar 1 포섭 여부
  icaap_materiality_policy  중요성 판정 축과 기준값
  icaap_materiality         기준일 x 리스크 유형 중요성 평가
  icaap_capital_map         기준일 x 리스크 유형 내부자본 매핑

중요성 판정은 fail-closed다. 세 축 중 하나라도 관측이 없으면 '판정불가'로
남기고 중요하지 않다고 결론내지 않는다. 중요한데 경제자본이 비어 있으면
자본 매핑은 '확정'이 아니라 '잠정'이 되고 사유가 붙는다.

기준값은 내부 운영값이다. 감독규정이 중요성 임계를 수치로 정한 조문을 이
저장소는 확인하지 못했다. 그 사실을 `basis`와 `evidence_status`에 적어 두고
규제 근거인 것처럼 쓰지 않는다.

이 모듈의 TableSpec은 아직 datamodel.catalog에 등재하지 않았다. 등재는 실체화
검증과 문서 수치 일치를 함께 만족해야 하므로 배선 단계에서 `SPECS`를 넘긴다.

참조: RYNTA BRD BNK-ST-001(Risk inventory·내부자본) · BNK-ST-002(중요성 평가),
Basel SRP20(Pillar 2 내부자본 적정성 평가절차).
"""

from __future__ import annotations

import pandas as pd

from risk_lib.alm.params import EVIDENCE_STATUS
from risk_lib.datamodel.spec import ColumnSpec as C, ForeignKey as FK, TableSpec

CAPITAL_PILLARS = ("Pillar 1", "Pillar 2", "자본 미부과")
MATERIALITY_GRADES = ("중요", "보통", "낮음", "판정불가")
MATERIALITY_AXES = ("노출비중", "손실비중", "KRI위반")
MAP_STATUSES = ("확정", "잠정")
MEASURE_METHODS = ("정량모형", "감독표준방법", "전문가판단", "미측정")


# ---------------------------------------------------------------- 스펙

RISK_TAXONOMY = TableSpec(
    name="icaap_risk_taxonomy", korean="리스크 인벤토리", product="PRD-ICP",
    grain="리스크 유형 1개당 1행",
    columns=(
        C("risk_id", "string", "리스크 식별자", nullable=False),
        C("risk_name", "text", "리스크 유형", nullable=False),
        C("capital_pillar", "string", "자본 부과 구분", nullable=False,
          allowed=CAPITAL_PILLARS),
        C("measure_method", "string", "측정 방법", nullable=False,
          allowed=MEASURE_METHODS),
        C("ec_engine", "text", "경제자본 산출 주체", nullable=False,
          note="산출 모듈 경로. 미측정이면 사유를 적는다"),
        C("owner_role", "text", "리스크 소유 역할", nullable=False),
        C("citation", "text", "근거", nullable=False),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS,
          note="자본 부과 구분의 감독근거 상태다. 전건 미확인인 이유는 "
               "Pillar 1·2 구분을 정한 조문을 이 저장소가 원문으로 열람하지 못했기 때문이다"),
    ),
    primary_key=("risk_id",),
    note="자본을 부과하지 않기로 한 유형도 행으로 남긴다. 목록에서 빼면 "
         "판단한 적 없는 것과 판단해서 제외한 것이 같아진다.",
)

MATERIALITY_POLICY = TableSpec(
    name="icaap_materiality_policy", korean="중요성 판정 정책", product="PRD-ICP",
    grain="판정 축 1개당 1행",
    columns=(
        C("axis", "string", "판정 축", nullable=False, allowed=MATERIALITY_AXES),
        C("threshold", "float", "기준값", nullable=False, unit="ratio",
          min_value=0.0, note="노출·손실 축은 비중, KRI 축은 위반 건수 비율"),
        C("min_axes_for_material", "int", "중요 판정 최소 초과 축 수",
          nullable=False, unit="count", min_value=1,
          note="세 축에 같은 값이 반복된다. 판정 규칙을 원장에 두어야 화면에서 "
               "보이고, 엔진 본문에 숫자가 남지 않는다"),
        C("basis", "text", "기준값 성격", nullable=False),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("axis",),
    note="세 축 중 둘 이상이 기준값을 넘으면 '중요'다. 축 하나로 정하면 "
         "손실이력이 없는 신종 리스크가 전부 낮음으로 떨어진다.",
)

MATERIALITY = TableSpec(
    name="icaap_materiality", korean="리스크 중요성 평가", product="PRD-ICP",
    grain="기준일 x 리스크 유형 1건당 1행",
    columns=(
        C("asof", "date", "기준일자", nullable=False),
        C("risk_id", "string", "리스크 식별자", nullable=False),
        C("exposure_share", "float", "노출 비중", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("loss_share", "float", "손실 비중", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("kri_breach_share", "float", "KRI 위반 비율", nullable=True,
          unit="ratio", min_value=0.0, max_value=1.0),
        C("n_axes_over", "int", "기준 초과 축 수", nullable=False, unit="count",
          min_value=0),
        C("grade", "string", "중요성 등급", nullable=False,
          allowed=MATERIALITY_GRADES),
        C("reason", "text", "판정 사유", nullable=False),
    ),
    primary_key=("asof", "risk_id"),
    foreign_keys=(FK(("risk_id",), "icaap_risk_taxonomy", ("risk_id",)),),
)

CAPITAL_MAP = TableSpec(
    name="icaap_capital_map", korean="리스크·내부자본 매핑", product="PRD-ICP",
    grain="기준일 x 리스크 유형 1건당 1행",
    columns=(
        C("asof", "date", "기준일자", nullable=False),
        C("risk_id", "string", "리스크 식별자", nullable=False),
        C("grade", "string", "중요성 등급", nullable=False,
          allowed=MATERIALITY_GRADES),
        C("capital_pillar", "string", "자본 부과 구분", nullable=False,
          allowed=CAPITAL_PILLARS),
        C("ec_amount", "float", "경제자본", nullable=True, unit="KRW",
          min_value=0.0, note="산출되지 않은 유형은 NULL이다. 0으로 채우면 "
                              "산출하지 않은 것과 산출해서 0인 것이 같아진다"),
        C("ec_share", "float", "경제자본 비중", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("status", "string", "매핑 상태", nullable=False, allowed=MAP_STATUSES),
        C("issue", "text", "잠정 사유", nullable=False),
    ),
    primary_key=("asof", "risk_id"),
    foreign_keys=(FK(("risk_id",), "icaap_risk_taxonomy", ("risk_id",)),
                  FK(("asof", "risk_id"), "icaap_materiality",
                     ("asof", "risk_id"))),
)

SPECS: tuple[TableSpec, ...] = (
    RISK_TAXONOMY, MATERIALITY_POLICY, MATERIALITY, CAPITAL_MAP)


# ---------------------------------------------------------------- 정의 적재
#
# 이 두 표가 이 모듈의 유일한 적재 지점이다. 판정 함수는 표를 직접 읽지 않고
# 인자로 받은 DataFrame만 본다.

_CITE_P1 = "Basel 최저자본규제 대상. 해당 조문 원문 미열람"
_CITE_P2 = "Pillar 1이 포섭하지 않아 내부자본으로 평가. 해당 조문 원문 미열람"

# (리스크ID, 명칭, 자본구분, 측정방법, 산출주체, 소유역할, 근거)
_TAXONOMY = (
    ("R-CRD", "신용리스크", "Pillar 1", "정량모형",
     "risk_lib.icaap.economic_capital", "신용리스크관리자", _CITE_P1),
    ("R-MKT", "시장리스크", "Pillar 1", "정량모형",
     "risk_lib.icaap.economic_capital", "시장리스크관리자", _CITE_P1),
    ("R-OPR", "운영리스크", "Pillar 1", "감독표준방법",
     "risk_lib.icaap.economic_capital", "운영리스크관리자", _CITE_P1),
    ("R-IRB", "은행계정 금리리스크", "Pillar 2", "정량모형",
     "risk_lib.alm.kr_irrbb", "ALM담당", _CITE_P2),
    ("R-LIQ", "유동성리스크", "자본 미부과", "정량모형",
     "risk_lib.alm.lcr · risk_lib.alm.nsfr",
     "ALM담당",
     "유동성은 LCR·NSFR 비율규제로 통제하며 내부자본을 부과하지 않는다. "
     "그 판단의 조문 미열람"),
    ("R-CON", "집중리스크", "Pillar 2", "정량모형",
     "risk_lib.icaap.economic_capital 집중 add-on", "신용리스크관리자", _CITE_P2),
    ("R-MDL", "모형리스크", "Pillar 2", "전문가판단",
     "risk_lib.model_risk", "적합성검증담당", _CITE_P2),
    ("R-STR", "전략리스크", "Pillar 2", "전문가판단",
     "미측정. 정량 산출 방법 미정", "경영기획", _CITE_P2),
    ("R-REP", "평판리스크", "자본 미부과", "전문가판단",
     "미측정. 정량 산출 방법 미정", "준법감시", _CITE_P2),
    ("R-CLM", "기후리스크", "Pillar 2", "정량모형",
     "risk_lib.climate · risk_lib.stress.climate_capital",
     "리스크관리책임자", _CITE_P2),
    ("R-AIG", "AI·알고리즘 리스크", "자본 미부과", "전문가판단",
     "risk_lib.aig.trace 등록·통제 원장", "AI거버넌스담당",
     "자본 부과 대상으로 정한 조문이 없다. 등록·통제로 관리한다"),
)

# 중요성 기준값. **내부 운영값이다.** 감독규정이 중요성 임계를 수치로 정한
# 조문을 확인하지 못했으므로 evidence_status를 '미확인'으로 둔다.
_MATERIALITY_BASIS = "내부 운영값. 감독규정의 중요성 임계 조문 미열람"
_POLICY = (
    ("노출비중", 0.10),
    ("손실비중", 0.10),
    ("KRI위반", 0.20),
)
# 축 하나로 중요성을 정하면 손실이력이 없는 신종 리스크가 전부 낮음으로
# 떨어지고, 세 축 전부를 요구하면 어떤 리스크도 중요가 되지 않는다.
_MIN_AXES_FOR_MATERIAL = 2


def build_risk_taxonomy() -> pd.DataFrame:
    return pd.DataFrame([{
        "risk_id": t[0], "risk_name": t[1], "capital_pillar": t[2],
        "measure_method": t[3], "ec_engine": t[4], "owner_role": t[5],
        "citation": t[6], "evidence_status": "미확인",
    } for t in _TAXONOMY], columns=[c.name for c in RISK_TAXONOMY.columns])


def build_materiality_policy() -> pd.DataFrame:
    return pd.DataFrame([{
        "axis": a, "threshold": float(t),
        "min_axes_for_material": _MIN_AXES_FOR_MATERIAL,
        "basis": _MATERIALITY_BASIS, "evidence_status": "미확인",
    } for a, t in _POLICY],
        columns=[c.name for c in MATERIALITY_POLICY.columns]
    ).astype({"threshold": "float64", "min_axes_for_material": "int64"})


# ---------------------------------------------------------------- 판정

_AXIS_COLUMN = {"노출비중": "exposure_share", "손실비중": "loss_share",
                "KRI위반": "kri_breach_share"}


def assess_materiality(taxonomy: pd.DataFrame, policy: pd.DataFrame,
                       observations: pd.DataFrame, *, asof: str) -> pd.DataFrame:
    """리스크 유형별 중요성을 판정한다.

    observations는 (risk_id, exposure_share, loss_share, kri_breach_share)
    컬럼을 갖는다. 세 축 중 하나라도 없으면 '판정불가'다. 관측되지 않은 축을
    0으로 읽으면 측정하지 않은 리스크가 전부 '낮음'으로 떨어진다.

    등급은 기준 초과 축 수로 정한다. 정책 원장의 min_axes_for_material 이상이면
    '중요', 하나라도 초과했으면 '보통', 없으면 '낮음'이다.
    """
    thresholds = policy.set_index("axis")["threshold"].to_dict()
    missing_axes = [a for a in MATERIALITY_AXES if a not in thresholds]
    if missing_axes:
        raise ValueError(f"정책 원장에 판정 축이 없다: {missing_axes}")
    # 판정 규칙은 정책 원장이 정한다. 축마다 다른 값이 들어 있으면 어느 값을
    # 쓸지 정할 근거가 없으므로 판정하지 않는다.
    min_axes = set(int(v) for v in policy["min_axes_for_material"])
    if len(min_axes) != 1:
        raise ValueError(f"중요 판정 최소 축 수가 축마다 다르다: {sorted(min_axes)}")
    need = min_axes.pop()
    obs = {r["risk_id"]: r for r in observations.to_dict("records")}
    rows = []
    for risk_id in taxonomy["risk_id"]:
        hit = obs.get(risk_id)
        if hit is None:
            rows.append((asof, risk_id, None, None, None, 0, "판정불가",
                         "관측값이 없다"))
            continue
        values = {a: hit.get(_AXIS_COLUMN[a]) for a in MATERIALITY_AXES}
        absent = [a for a, v in values.items()
                  if v is None or (isinstance(v, float) and pd.isna(v))]
        if absent:
            rows.append((asof, risk_id, values["노출비중"], values["손실비중"],
                         values["KRI위반"], 0, "판정불가",
                         f"관측 없는 축: {', '.join(absent)}"))
            continue
        over = [a for a in MATERIALITY_AXES
                if float(values[a]) >= float(thresholds[a])]
        grade = ("중요" if len(over) >= need
                 else ("보통" if over else "낮음"))
        reason = (f"기준 초과 축 {len(over)}개" +
                  (f" ({', '.join(over)})" if over else ""))
        rows.append((asof, risk_id, values["노출비중"], values["손실비중"],
                     values["KRI위반"], len(over), grade, reason))
    return pd.DataFrame(rows, columns=[c.name for c in MATERIALITY.columns]
                        ).astype({"exposure_share": "float64",
                                  "loss_share": "float64",
                                  "kri_breach_share": "float64",
                                  "n_axes_over": "int64"})


def build_capital_map(taxonomy: pd.DataFrame, materiality: pd.DataFrame,
                      ec_by_risk: dict[str, float] | None = None, *, asof: str
                      ) -> pd.DataFrame:
    """중요성 평가와 경제자본 산출을 하나의 지도로 잇는다.

    ec_by_risk는 risk_id → 경제자본 금액이다. 산출되지 않은 유형은 넣지 않으며
    이 함수는 0으로 채우지 않는다. 비중은 산출된 금액의 합계를 분모로 한다.

    매핑 상태는 다음이면 '잠정'이다.
      1. 중요성이 '판정불가'다
      2. 중요성이 '중요'인데 자본 부과 구분이 Pillar 1·2이고 경제자본이 없다
    잠정 건은 이슈로 넘어가야 하며 그 사유를 issue 칸에 남긴다.
    """
    ec = dict(ec_by_risk or {})
    total = sum(v for v in ec.values() if v is not None)
    tax = taxonomy.set_index("risk_id")
    rows = []
    for m in materiality.to_dict("records"):
        risk_id = m["risk_id"]
        pillar = tax.loc[risk_id, "capital_pillar"]
        amount = ec.get(risk_id)
        share = (float(amount) / total) if (amount is not None and total > 0) else None
        issues = []
        if m["grade"] == "판정불가":
            issues.append(f"중요성 판정불가: {m['reason']}")
        if (m["grade"] == "중요" and pillar in ("Pillar 1", "Pillar 2")
                and amount is None):
            issues.append(f"중요 리스크인데 경제자본 미산출 "
                          f"(산출 주체: {tax.loc[risk_id, 'ec_engine']})")
        rows.append((asof, risk_id, m["grade"], pillar, amount, share,
                     "잠정" if issues else "확정",
                     "; ".join(issues) if issues else ""))
    return pd.DataFrame(rows, columns=[c.name for c in CAPITAL_MAP.columns]
                        ).astype({"ec_amount": "float64", "ec_share": "float64"})


def build_risk_inventory(observations, ec_by_risk=None, *, asof: str
                         ) -> dict[str, pd.DataFrame]:
    """리스크 인벤토리 원장 4장을 만든다.

    observations는 관측 dict의 열거다. 호출자가 실제 노출·손실·KRI 관측을
    넘기며 이 함수는 표본을 만들지 않는다.
    """
    taxonomy = build_risk_taxonomy()
    policy = build_materiality_policy()
    obs = pd.DataFrame(list(observations),
                       columns=["risk_id", "exposure_share", "loss_share",
                                "kri_breach_share"])
    mat = assess_materiality(taxonomy, policy, obs, asof=asof)
    cap = build_capital_map(taxonomy, mat, ec_by_risk, asof=asof)
    return {"icaap_risk_taxonomy": taxonomy,
            "icaap_materiality_policy": policy,
            "icaap_materiality": mat,
            "icaap_capital_map": cap}
