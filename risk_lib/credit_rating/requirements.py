"""신용평가시스템 최소요건 원장과 생애주기 이행 판정 (BNK-CRM-002).

**왜 원장인가.** 모형 생애주기 통제는 "언제까지 무엇을 해야 하는가"를 규정에서
읽어 와야 성립한다. 그 주기가 코드 상수로 있으면 화면에도 결재 서류에도 근거가
나오지 않는다. 이 모듈은 [별표 3] 제4절의 조문을 행으로 적재하고
(`build_rating_requirements`), 판정 엔진(`assess_lifecycle`)은 주기를 원장에서만
읽는다. 엔진 본문에 개월 수가 없다.

**주기를 안 주는 조문은 비운다.** 156.과 158.(6)은 "정기적으로 점검"이라고만
적고 개월 수를 주지 않는다. 그 행의 `review_months`는 NULL이고, 판정 엔진은
기한을 만들어 내지 않고 상태를 `주기미규정`으로 남긴다. 저장소 규약("1차자료가
값을 주지 않으면 지어내지 않는다")이 걸리는 자리다.

원문: 은행업감독업무시행세칙 [별표 3] 「신용·운영리스크 위험가중자산에 대한
자기자본비율 산출기준(바젤Ⅲ 기준)」 최종 개정 2026.3.9.
추출본문 `docs/primary_sources/규정원문_20260809/02_별표3_바젤III_자기자본비율_산출기준.txt`.

**이행 이벤트는 합성이다.** 실제 은행은 모형 승인·검증 워크플로에서 이행일을
받는다. 이 하네스에는 그 워크플로가 없으므로 `build_lifecycle_events`가
결정론 난수로 이행일을 만든다. 그 사실은 원장의 `recorded_by='synthetic'`에
남으며, 규정 주기(`review_months`)와는 출처가 분리된다.

**미등재.** 아래 TableSpec은 아직 `datamodel.catalog.ALL_TABLES`에 없다.
카탈로그 등재는 실체화·ARCHITECTURE.md 수치 검사와 함께 움직이므로 배선
단계에서 등재한다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from risk_lib.datamodel.spec import ColumnSpec as C, ForeignKey as FK, TableSpec

__all__ = [
    "SOURCE_VERSION", "EVIDENCE_STATUS", "REQ_TOPICS", "REQ_SCOPES",
    "THRESHOLD_UNITS", "LIFECYCLE_STATUS", "SEGMENT_SCOPE",
    "RATING_REQUIREMENT", "LIFECYCLE_EVENT", "LIFECYCLE_COMPLIANCE",
    "REQUIREMENT_TABLES",
    "build_rating_requirements", "build_lifecycle_events",
    "assess_lifecycle", "check_grade_structure", "periodic_requirements",
]

# 이 모듈이 적재하는 조문의 판. 조문 번호만 적으면 어느 판의 148.인지 모른다.
SOURCE_VERSION = "별표3_2026-03-09"

# ALM 원장과 같은 어휘를 쓴다. 새 어휘를 만들면 화면이 두 벌의 근거 상태를
# 그려야 한다.
EVIDENCE_STATUS: tuple[str, ...] = (
    "원문확인", "2차자료", "원문미확인·현행계승", "재량·미규정", "미확인")
REQ_TOPICS: tuple[str, ...] = (
    "평가시스템", "등급구조", "평가기준", "모형", "문서화", "등급운영",
    "등급변경", "데이터보존", "추정", "검증")
REQ_SCOPES: tuple[str, ...] = ("기업", "소매", "공통")
THRESHOLD_UNITS: tuple[str, ...] = ("grades", "years")
LIFECYCLE_STATUS: tuple[str, ...] = ("이행", "기한초과", "증적없음", "주기미규정")

# crm_model.segment(자산군) → 요건 적용대상. 요건은 자산군이 아니라 기업·소매로
# 갈리므로 매핑을 원장 옆에 둔다.
SEGMENT_SCOPE: dict[str, str] = {
    "corporate": "기업",
    "bank": "기업",
    "sovereign": "기업",
    "retail_other": "소매",
    "residential_mortgage": "소매",
}


# ---------------------------------------------------------------- 스펙

RATING_REQUIREMENT = TableSpec(
    name="crm_rating_requirement", korean="신용평가시스템 최소요건",
    product="PRD-CRM",
    grain="[별표 3] 제4절 최소요건 항목 1건당 1행",
    columns=(
        C("requirement_code", "string", "요건코드", nullable=False),
        C("clause", "string", "조", nullable=False,
          note="[별표 3]의 조·목 번호. 판이 바뀌면 번호도 바뀌므로 "
               "source_version과 함께 읽는다"),
        C("topic", "string", "구분", nullable=False, allowed=REQ_TOPICS),
        C("scope", "string", "적용대상", nullable=False, allowed=REQ_SCOPES),
        C("obligation", "text", "요구사항", nullable=False),
        C("review_months", "int", "점검주기", nullable=True, min_value=1,
          note="단위는 개월. 원문이 '정기적'이라고만 하고 주기를 정하지 않으면 "
               "NULL이며 판정 엔진은 기한을 만들지 않는다"),
        C("threshold_value", "float", "요건 수치", nullable=True, unit="count",
          min_value=0.0,
          note="등급 수(grades)나 관측기간(years)처럼 원문이 숫자를 주는 요건만 "
               "채운다. 단위는 threshold_unit"),
        C("threshold_unit", "string", "요건 수치 단위", nullable=True,
          allowed=THRESHOLD_UNITS),
        C("ledger_ref", "string", "이행 원장", nullable=True,
          note="이 하네스에서 그 요건의 증적을 담는 정규 원장명. 비어 있으면 "
               "증적이 원장으로 없다는 뜻이고 그 사실이 보여야 한다"),
        C("citation", "text", "근거", nullable=False),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
        C("source_version", "string", "원문 판", nullable=False),
    ),
    primary_key=("requirement_code",),
    note="[별표 3] 제4절 제1관~제4관 및 제5관 추정·검증 조항에서 신용평가모형 "
         "운영에 직접 걸리는 요건을 옮긴 원장. 값은 전부 원문에서 읽었고 "
         "원문이 수치를 주지 않는 칸은 비어 있다.",
)

LIFECYCLE_EVENT = TableSpec(
    name="crm_lifecycle_event", korean="모형 생애주기 이행 이벤트",
    product="PRD-CRM",
    grain="모형 × 요건코드 × 이행일 1행",
    columns=(
        C("model_id", "string", "모형 식별자", nullable=False),
        C("requirement_code", "string", "요건코드", nullable=False),
        C("event_date", "date", "이행일", nullable=False),
        C("performed_by", "text", "수행 조직", nullable=False,
          note="163.다는 여신 확대에 이해관계가 없는 독립 조직의 수행·승인을 "
               "요구한다. 조직명이 없으면 그 요건을 판정할 수 없다"),
        C("recorded_by", "string", "기록 출처", nullable=False,
          allowed=("synthetic", "manual", "workflow"),
          note="synthetic은 이 하네스가 만든 값이며 실제 이행 증적이 아니다"),
        C("evidence_ref", "text", "증적 참조", nullable=True),
    ),
    primary_key=("model_id", "requirement_code", "event_date"),
    foreign_keys=(FK(("model_id",), "crm_model", ("model_id",)),
                  FK(("requirement_code",), "crm_rating_requirement",
                     ("requirement_code",))),
)

LIFECYCLE_COMPLIANCE = TableSpec(
    name="crm_lifecycle_compliance", korean="모형 생애주기 기한 판정",
    product="PRD-CRM",
    grain="모형 × 요건코드 × 기준일 1행",
    columns=(
        C("model_id", "string", "모형 식별자", nullable=False),
        C("requirement_code", "string", "요건코드", nullable=False),
        C("asof", "date", "기준일", nullable=False),
        C("scope", "string", "적용대상", nullable=False, allowed=REQ_SCOPES),
        C("review_months", "int", "점검주기", nullable=True, min_value=1),
        C("last_done", "date", "최근 이행일", nullable=True),
        C("next_due", "date", "차기 기한", nullable=True),
        C("days_overdue", "int", "기한 경과일", nullable=True, min_value=0,
          note="주기가 없거나 이행 증적이 없으면 NULL. 0으로 채우면 기한을 "
               "지킨 것과 판정하지 못한 것이 같은 값이 된다"),
        C("status", "string", "판정", nullable=False, allowed=LIFECYCLE_STATUS),
        C("citation", "text", "근거", nullable=False),
    ),
    primary_key=("model_id", "requirement_code", "asof"),
    foreign_keys=(FK(("model_id",), "crm_model", ("model_id",)),
                  FK(("requirement_code",), "crm_rating_requirement",
                     ("requirement_code",))),
    note="주기가 있는 요건만 기한이 생긴다. 주기미규정·증적없음은 통과가 아니라 "
         "판정하지 못한 상태이며 days_overdue가 NULL로 남는다.",
)

REQUIREMENT_TABLES = (RATING_REQUIREMENT, LIFECYCLE_EVENT, LIFECYCLE_COMPLIANCE)


# ---------------------------------------------------------------- 빌더

# (요건코드, 조, 구분, 적용대상, 요구사항, 주기(월), 수치, 수치단위, 이행원장)
# 조문 문언은 추출본문에서 옮긴 것이며 요약할 때도 수치·주기는 바꾸지 않는다.
_ROWS: tuple[tuple, ...] = (
    ("CRS-148-A", "148.가", "평가시스템", "공통",
     "신용리스크 평가·내부등급 부여·PD/LGD/EAD 계량화의 방법론, 업무절차, "
     "데이터 수집, 통제 및 전산시스템을 마련할 것",
     None, None, None, None),
    ("CRS-149-A", "149.가", "평가시스템", "기업",
     "차주의 부도위험(차주등급)과 거래 익스포져의 손실위험(여신등급)에 대하여 "
     "독립된 신용평가시스템을 마련할 것",
     None, None, None, None),
    ("CRS-150-B", "150.나", "평가시스템", "소매",
     "소매 자산군 간 리스크 특성이 충분히 차별화되고 각 자산군이 동질적인 "
     "리스크 특성으로 구성될 것",
     None, None, None, None),
    ("CRS-151-NB", "151.나", "등급구조", "기업",
     "부도가 아닌 차주에 대하여 최소 7개 이상의 차주등급으로 세분화할 것",
     None, 7.0, "grades", "crm_obligor_score"),
    ("CRS-151-D", "151.나", "등급구조", "기업",
     "부도 차주에 대하여 최소 1개 이상의 등급으로 세분화할 것",
     None, 1.0, "grades", "crm_obligor_score"),
    ("CRS-152-2", "152.(2)", "등급구조", "소매",
     "자산군에는 신뢰성 있는 PD·LGD·EAD 추정과 검증이 가능하도록 충분한 수의 "
     "익스포져가 포함될 것",
     None, None, None, "crm_dev_sample"),
    ("CRS-153-A", "153.가", "평가기준", "공통",
     "신용등급의 정의, 등급 부여 기준 및 절차를 갖출 것",
     None, None, None, "crm_qualitative_item"),
    ("CRS-153-D", "153.라", "평가기준", "공통",
     "제3자가 등급부여 절차를 재현하여 동일하게 적용할 수 있을 정도로 명확하고 "
     "상세하게 정의할 것",
     None, None, None, "crm_scorecard_bin"),
    ("CRS-154-B", "154.나", "평가기준", "공통",
     "관련 정보가 부족할수록 보수적으로 등급을 부여할 것",
     None, None, None, None),
    ("CRS-156", "156.", "평가기준", "공통",
     "신용등급 부여 및 자산군 할당 기준·절차의 적정성을 정기적으로 점검할 것",
     None, None, None, None),
    ("CRS-157-A", "157.가", "평가기준", "공통",
     "PD 추정은 1년 기준으로 산출하되 신용등급 부여는 보다 장기간을 기준으로 할 것",
     None, 1.0, "years", None),
    ("CRS-158-1", "158.(1)", "모형", "공통",
     "모형 입력변수가 합리적인 예측력을 갖고 산출물에 중대한 편의가 없을 것",
     None, None, None, "crm_scorecard_factor"),
    ("CRS-158-2", "158.(2)", "모형", "공통",
     "모형 입력 데이터의 정확성·완전성·적절성 평가를 포함하는 점검 절차를 마련할 것",
     None, None, None, "rdm_dq_result"),
    ("CRS-158-3", "158.(3)", "모형", "공통",
     "모형에 사용된 데이터가 은행의 실제 차주·익스포져 모집단을 대표할 것",
     None, None, None, "crm_sample_representativeness"),
    ("CRS-158-4", "158.(4)", "모형", "공통",
     "모형 결과와 인적 판단을 결합할 경우 결합 방법에 대한 문서화된 기준을 보유할 것",
     None, None, None, "crm_override_reason"),
    ("CRS-158-5", "158.(5)", "모형", "공통",
     "모형에 의한 신용평가의 적정성에 대한 인적 검증절차를 마련할 것",
     None, None, None, None),
    ("CRS-158-6", "158.(6)", "모형", "공통",
     "모형의 성과·안정성 평가, 모형 간 상호관련성 검토, 실제값과 예측치 비교 등 "
     "모형검증을 정기적으로 실시할 것",
     None, None, None, "crm_performance"),
    ("CRS-159-C", "159.다", "문서화", "공통",
     "대상 포트폴리오 구분, 등급부여 기준과 근거, 담당부서·예외적용·승인권자, "
     "감사절차, 변경 이력, 정기 점검 내용, 부도·손실 정의 정합성을 문서화할 것",
     None, None, None, None),
    ("CRS-160", "160.", "문서화", "공통",
     "통계모형 사용 시 모형 개요·이론적 배경·데이터 원천, 타당성 검증 절차, "
     "모형이 작동하지 않을 수 있는 예외 상황을 문서화할 것",
     None, None, None, "crm_scorecard_factor"),
    ("CRS-162-A", "162.가", "등급운영", "기업",
     "기업 등 익스포져의 차주 및 보증인에게 차주등급을, 모든 익스포져에 "
     "여신등급을 부여할 것",
     None, None, None, "crm_obligor_score"),
    ("CRS-163-A", "163.가", "등급운영", "기업",
     "차주등급 및 여신등급을 최소 1년 단위로 갱신하고 고위험 차주·문제여신은 "
     "수시로 재평가할 것",
     12, None, None, "crm_obligor_score"),
    ("CRS-163-C", "163.다", "등급운영", "기업",
     "신용등급 부여 및 정기 검토를 신용공여 확대에 직접적인 이해관계가 없는 "
     "독립된 조직이 수행하거나 승인할 것",
     None, None, None, "crm_lifecycle_event"),
    ("CRS-164-A", "164.가", "등급운영", "소매",
     "소매익스포져에 대하여 최소 1년 단위로 자산군별 손실특성 및 연체상황을 "
     "점검할 것",
     12, None, None, "crm_dev_sample"),
    ("CRS-165-A", "165.가", "등급변경", "공통",
     "전문가 판단으로 등급을 부여하는 경우 등급변경 방법, 변경 가능 범위, "
     "변경 책임자에 대한 명확한 기준을 마련할 것",
     None, None, None, "crm_override_reason"),
    ("CRS-165-B", "165.나", "등급변경", "공통",
     "모형 등급의 인적 판단 변경, 모형 제외 변수, 입력 데이터 변경을 "
     "모니터링하는 절차를 마련하고 책임자를 명시할 것",
     None, None, None, "crm_override"),
    ("CRS-165-C", "165.다", "등급변경", "공통",
     "등급 및 추정치를 변경한 경우 변경 후 성과를 평가할 것",
     None, None, None, "crm_override_performance"),
    ("CRS-166-A", "166.가", "데이터보존", "기업",
     "차주·보증인의 등급변동 이력, 등급부여일, 산출 방법론과 사용 데이터, 평가 "
     "담당자와 적용 모형, 부도 발생 차주·시기·사유, 등급별 실제 부도율과 전이현황을 "
     "보존할 것",
     None, None, None, "crm_rating"),
    ("CRS-167", "167.", "데이터보존", "소매",
     "자산군 할당에 사용된 차주·거래 특성 데이터, 연체 데이터, 자산군별 "
     "PD·LGD·EAD 추정치, 부도 익스포져의 전년도 자산군과 실현 LGD·EAD를 보존할 것",
     None, None, None, "crm_dev_sample"),
    ("CRS-174-A", "174.가", "추정", "공통",
     "상환청구 조치 없이는 채무 전액 상환이 어렵다고 판단되는 경우 또는 90일 "
     "이상 연체한 경우를 부도로 볼 것",
     None, None, None, "crm_dev_sample"),
    ("CRS-178", "178.", "추정", "공통",
     "174.의 부도정의로 실제 부도를 기록하고 이를 근거로 PD·LGD·EAD를 추정할 것",
     None, None, None, "crm_dev_sample"),
    ("CRS-179-B", "179.나", "추정", "공통",
     "PD·LGD·EAD 추정치의 적정 여부를 연 1회 이상 점검하고 여신 취급기준·회수절차 "
     "변경과 새로운 데이터의 영향을 신속하게 반영할 것",
     12, None, None, "crm_performance"),
    ("CRS-180-A", "180.가", "추정", "공통",
     "추정에 사용된 데이터 모집단과 데이터 생성 시점의 여신 취급기준·중요 특성이 "
     "은행의 익스포져 특성 및 여신 취급기준과 같거나 유사할 것",
     None, None, None, "crm_sample_representativeness"),
    ("CRS-181", "181.", "추정", "공통",
     "예상치 못한 오류에 대비하여 추정치를 보수적으로 조정하고, 모형·데이터 "
     "품질이 낮으면 조정폭을 확대할 것",
     None, None, None, None),
    ("CRS-182-D", "182.라", "추정", "기업",
     "기업 등 익스포져의 PD 추정에 최소 5년 이상의 관측기간을 사용할 것",
     None, 5.0, "years", "crm_dev_sample"),
    ("CRS-183-B", "183.나", "추정", "소매",
     "소매익스포져의 장기평균 PD 추정에 최소 5년 이상의 관측기간을 사용할 것",
     None, 5.0, "years", "crm_dev_sample"),
    ("CRS-202-A", "202.가", "검증", "공통",
     "신용평가시스템 및 절차, PD·LGD·EAD 추정치의 정확성 및 일관성을 검증할 수 "
     "있는 견실한 체계를 갖출 것",
     None, None, None, "crm_performance"),
    ("CRS-203-A", "203.가", "검증", "기업",
     "최소 연 1회 이상 신용등급별 실제 부도율과 추정 PD를 비교하고 실제 부도율이 "
     "해당 등급의 예상 부도율 범위 내에 있음을 검증할 것",
     12, None, None, "crm_pd_calibration"),
    ("CRS-203-C", "203.다", "검증", "소매",
     "소매익스포져에 대하여 자산군별로 연 1회 이상 PD·LGD·EAD 추정치를 비교·검증할 것",
     12, None, None, "crm_pd_calibration"),
)


def build_rating_requirements() -> pd.DataFrame:
    """[별표 3] 제4절 최소요건 원장을 만든다.

    조문에서 읽은 값만 적재한다. 원문이 주기나 수치를 주지 않는 칸은 NULL이며,
    그 NULL이 판정 엔진의 '주기미규정' 상태로 그대로 이어진다.
    """
    rows = []
    for (code, clause, topic, scope, obligation,
         months, thr, thr_unit, ledger) in _ROWS:
        rows.append({
            "requirement_code": code,
            "clause": clause,
            "topic": topic,
            "scope": scope,
            "obligation": obligation,
            "review_months": months,
            "threshold_value": thr,
            "threshold_unit": thr_unit,
            "ledger_ref": ledger,
            "citation": f"[별표 3] {clause}",
            "evidence_status": "원문확인",
            "source_version": SOURCE_VERSION,
        })
    df = pd.DataFrame(rows, columns=RATING_REQUIREMENT.column_names)
    # None이 섞이면 컬럼이 object가 되어 이후 비교가 조용히 어긋난다.
    df["review_months"] = pd.array(df["review_months"], dtype="Int64")
    df["threshold_value"] = pd.to_numeric(df["threshold_value"],
                                          errors="coerce").astype("float64")
    return df


def periodic_requirements(requirements: pd.DataFrame) -> pd.DataFrame:
    """주기가 명시된 요건만 추린다. 기한은 이 행들에서만 생긴다."""
    return requirements[requirements["review_months"].notna()].reset_index(drop=True)


def _applicable(models: pd.DataFrame, requirements: pd.DataFrame) -> pd.DataFrame:
    """모형 × 요건의 적용 조합. 세그먼트가 없는 모형은 조합을 만들지 않는다.

    crm_model에는 시장·ALM·기후 모형도 있다. 신용평가시스템 요건을 그 모형에
    걸면 이행률이 근거 없이 낮아지고, 반대로 신용 모형의 미이행이 희석된다.
    """
    m = models[models["domain"] == "신용"].copy()
    m = m[m["segment"].notna() & (m["segment"] != "")]
    m["scope"] = m["segment"].map(SEGMENT_SCOPE)
    m = m[m["scope"].notna()]
    out = []
    for _, mrow in m.iterrows():
        for _, rrow in requirements.iterrows():
            if rrow["scope"] not in ("공통", mrow["scope"]):
                continue
            out.append({"model_id": mrow["model_id"],
                        "scope": mrow["scope"],
                        "requirement_code": rrow["requirement_code"],
                        "review_months": rrow["review_months"],
                        "citation": rrow["citation"]})
    return pd.DataFrame(out, columns=["model_id", "scope", "requirement_code",
                                      "review_months", "citation"])


def build_lifecycle_events(models: pd.DataFrame, requirements: pd.DataFrame, *,
                           asof: str, seed: int) -> pd.DataFrame:
    """이행 이벤트 원장(합성)을 만든다.

    실제 이행일은 모형 승인·검증 워크플로에서 온다. 이 하네스에는 그 워크플로가
    없으므로 기준일에서 역산한 결정론 난수로 만들고 `recorded_by='synthetic'`을
    남긴다. 주기가 없는 요건에는 이벤트를 만들지 않는다. 만들면 기한을 판정할 수
    없는 요건이 이행된 것처럼 보인다.
    """
    per = periodic_requirements(requirements)
    pairs = _applicable(models, per)
    if pairs.empty:
        return pd.DataFrame(columns=LIFECYCLE_EVENT.column_names)
    rng = np.random.default_rng(seed + 8100)
    asof_ts = pd.Timestamp(asof)
    rows = []
    for _, r in pairs.iterrows():
        months = int(r["review_months"])
        # 주기의 0.3~1.4배 전에 이행한 것으로 둔다. 상단이 1을 넘으므로 일부는
        # 기한 초과로 판정되며, 그래야 판정 로직이 통과만 내지 않는다.
        elapsed = float(rng.uniform(0.3, 1.4)) * months
        done = asof_ts - pd.DateOffset(days=int(round(elapsed * 30.4375)))
        rows.append({
            "model_id": r["model_id"],
            "requirement_code": r["requirement_code"],
            "event_date": done.date().isoformat(),
            "performed_by": "모형검증부(여신 승인 라인과 분리)",
            "recorded_by": "synthetic",
            "evidence_ref": f"{r['model_id']}·{r['requirement_code']}",
        })
    return pd.DataFrame(rows, columns=LIFECYCLE_EVENT.column_names)


def assess_lifecycle(models: pd.DataFrame, requirements: pd.DataFrame,
                     events: pd.DataFrame, *, asof: str) -> pd.DataFrame:
    """모형 × 요건의 기한 판정을 낸다.

    주기는 요건 원장에서만 온다. 이 함수 본문에 개월 수가 없으므로 규정 판이
    바뀌면 원장만 갈아끼우면 된다. 판정은 네 가지다.

      이행        기한 내
      기한초과    next_due < asof
      증적없음    적용 대상인데 이벤트가 없다
      주기미규정  원문이 주기를 주지 않아 기한을 만들 수 없다
    """
    asof_ts = pd.Timestamp(asof)
    pairs = _applicable(models, requirements)
    if pairs.empty:
        return pd.DataFrame(columns=LIFECYCLE_COMPLIANCE.column_names)
    if events.empty:
        last = pd.DataFrame(columns=["model_id", "requirement_code", "last_done"])
    else:
        last = (events.groupby(["model_id", "requirement_code"], as_index=False)
                      .agg(last_done=("event_date", "max")))
    j = pairs.merge(last, on=["model_id", "requirement_code"], how="left")

    rows = []
    for _, r in j.iterrows():
        months = r["review_months"]
        has_period = not pd.isna(months)
        last_done = r["last_done"] if isinstance(r["last_done"], str) else None
        next_due = None
        overdue = None
        if not has_period:
            status = "주기미규정"
        elif last_done is None:
            status = "증적없음"
        else:
            due = pd.Timestamp(last_done) + pd.DateOffset(months=int(months))
            next_due = due.date().isoformat()
            gap = (asof_ts - due).days
            overdue = int(gap) if gap > 0 else 0
            status = "기한초과" if gap > 0 else "이행"
        rows.append({
            "model_id": r["model_id"],
            "requirement_code": r["requirement_code"],
            "asof": asof,
            "scope": r["scope"],
            "review_months": int(months) if has_period else None,
            "last_done": last_done,
            "next_due": next_due,
            "days_overdue": overdue,
            "status": status,
            "citation": r["citation"],
        })
    df = pd.DataFrame(rows, columns=LIFECYCLE_COMPLIANCE.column_names)
    df["review_months"] = pd.array(df["review_months"], dtype="Int64")
    df["days_overdue"] = pd.array(df["days_overdue"], dtype="Int64")
    return df.sort_values(["model_id", "requirement_code"]).reset_index(drop=True)


def check_grade_structure(grades: list[str], default_grades: list[str],
                          requirements: pd.DataFrame) -> list[dict]:
    """등급 세분화 요건(151.나)을 원장의 수치로 판정한다.

    최소 등급 수를 인자로 받지 않고 요건 원장에서 읽는다. 7과 1이 이 함수
    본문에 없으므로 규정이 바뀌면 원장만 고치면 된다. 요건 행이 없으면
    판정하지 않고 그 사실을 결과에 남긴다.
    """
    out = []
    for code, actual, label in (("CRS-151-NB", len(grades), "비부도 차주등급"),
                                ("CRS-151-D", len(default_grades), "부도 차주등급")):
        hit = requirements[requirements["requirement_code"] == code]
        if hit.empty or pd.isna(hit.iloc[0]["threshold_value"]):
            out.append({"requirement_code": code, "label": label,
                        "actual": actual, "required": None,
                        "meets": None, "citation": ""})
            continue
        row = hit.iloc[0]
        req = float(row["threshold_value"])
        out.append({"requirement_code": code, "label": label,
                    "actual": actual, "required": req,
                    "meets": bool(actual >= req),
                    "citation": row["citation"]})
    return out
