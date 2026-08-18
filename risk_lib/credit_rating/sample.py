"""개발표본·부도정의·대표성 원장 (BNK-CRM-003).

**무엇이 없었나.** 이 하네스의 PD 모형은 포트폴리오 전체를 훈련·검정으로 나눠
적합할 뿐, 그 표본이 어느 기간을 관측한 것인지, 목표변수(부도)를 무엇으로
정의했는지, 개발표본이 적용 모집단을 대표하는지를 어디에도 적지 않았다.
[별표 3] 174.(부도의 정의) · 178.(부도정의 준용) · 180.(데이터 추출) ·
182.라·183.나(최소 관측기간)가 요구하는 것이 정확히 그 세 가지다.

**관측기간은 계산해서 적는다.** 최소 관측기간 5년은 요건 원장
(`crm_rating_requirement`)에서 읽고, 실제 관측연수는 표본의 코호트 범위에서
계산한다. 이 저장소의 합성 포트폴리오는 24개월 코호트만 갖고 있으므로
`meets_minimum`은 False가 된다. 통과하지 못한다는 사실을 원장에 남기는 것이
이 원장의 목적이며, 통과시키려고 관측기간을 늘려 적지 않는다.

**대표성은 판정하지 않는다.** 180.가는 개발표본 모집단이 은행의 익스포져 특성과
"같거나 유사"할 것을 요구하지만 합격 임계를 주지 않는다. 1차자료 발췌
(`docs/primary_sources/IRB_최소요건_원문발췌.md` §H 말미)도 "규정이 수치를 주지
않는 것: 합격 임계(정확도·변별력·안정성) … 지어낸 임계로 통과 판정을 찍지
마라"라고 적는다. 따라서 이 모듈은 변수별 PSI와 평균 이동을 산출하고
`assessment='미판정'`, `threshold=NULL`로 둔다. 내부 승인 임계가 생기면 원장의
threshold 칸이 채워지고 그때 판정이 붙는다.

**미등재.** TableSpec은 배선 단계에서 카탈로그에 등재한다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from risk_lib.credit_rating.requirements import EVIDENCE_STATUS, SOURCE_VERSION
from risk_lib.datamodel.spec import ColumnSpec as C, ForeignKey as FK, TableSpec
from risk_lib.models.pd_model import psi as _psi

__all__ = [
    "TARGET_BASES", "ASSESSMENTS", "DEV_SAMPLE", "SAMPLE_REPRESENTATIVENESS",
    "SAMPLE_TABLES", "build_dev_sample", "build_representativeness",
]

# 174.나: 차주 기준 부도가 원칙이고 소매는 거래 기준으로 판단할 수 있다.
TARGET_BASES: tuple[str, ...] = ("차주기준", "거래기준")
ASSESSMENTS: tuple[str, ...] = ("적합", "부적합", "미판정")

# 174.가(2)의 연체일. 부도정의를 문장으로만 적으면 표본 산출이 그 정의를
# 실제로 썼는지 확인할 수 없으므로 일수를 컬럼으로 둔다.
_DPD_TRIGGER_DAYS = 90


DEV_SAMPLE = TableSpec(
    name="crm_dev_sample", korean="모형 개발표본·부도정의", product="PRD-CRM",
    grain="모형 × 세그먼트 1행",
    columns=(
        C("model_id", "string", "모형 식별자", nullable=False),
        C("segment", "string", "세그먼트", nullable=False),
        C("asof", "date", "기준일", nullable=False),
        C("observation_start", "date", "관측 시작", nullable=False),
        C("observation_end", "date", "관측 종료", nullable=False),
        C("observation_years", "float", "관측연수", nullable=False, unit="years",
          min_value=0.0),
        C("min_observation_years", "float", "최소 관측기간 요건", nullable=True,
          unit="years", min_value=0.0,
          citation="[별표 3] 182.라(기업 PD 5년) · 183.나(소매 PD 5년)",
          note="요건 원장에서 읽는다. 요건 행이 없으면 NULL이고 판정하지 않는다"),
        C("meets_minimum", "string", "관측기간 요건 충족", nullable=False,
          allowed=ASSESSMENTS),
        C("n_obs", "int", "표본 수", nullable=False, min_value=0),
        C("n_default", "int", "부도 건수", nullable=False, min_value=0),
        C("default_rate", "float", "표본 부도율", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("target_definition", "text", "목표변수 정의", nullable=False,
          citation="[별표 3] 174.가"),
        C("target_horizon_months", "int", "목표 관측지평", nullable=False,
          min_value=1, citation="[별표 3] 157.가 PD는 1년 기준"),
        C("target_basis", "string", "부도 판단 단위", nullable=False,
          allowed=TARGET_BASES, citation="[별표 3] 174.나"),
        C("dpd_trigger_days", "int", "연체 기준일수", nullable=False,
          min_value=1, citation="[별표 3] 174.가(2) 90일 이상 연체"),
        C("holdout_share", "float", "검정표본 비중", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("citation", "text", "근거", nullable=False),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
        C("source_version", "string", "원문 판", nullable=False),
    ),
    primary_key=("model_id", "segment"),
    foreign_keys=(FK(("model_id",), "crm_model", ("model_id",)),),
    note="부도정의와 관측기간을 산출물 옆에 두지 않으면 178.(부도정의 준용)과 "
         "182.라·183.나(최소 관측기간)를 사후에 확인할 방법이 없다.",
)

SAMPLE_REPRESENTATIVENESS = TableSpec(
    name="crm_sample_representativeness", korean="개발표본 대표성 점검",
    product="PRD-CRM",
    grain="모형 × 세그먼트 × 변수 × 기준일 1행",
    columns=(
        C("model_id", "string", "모형 식별자", nullable=False),
        C("segment", "string", "세그먼트", nullable=False),
        C("feature", "string", "변수", nullable=False),
        C("asof", "date", "기준일", nullable=False),
        C("n_dev", "int", "개발표본 수", nullable=False, min_value=0),
        C("n_current", "int", "적용 모집단 수", nullable=False, min_value=0),
        C("dev_mean", "float", "개발표본 평균", nullable=False, unit="mixed",
          note="변수마다 단위가 다르다(배수·비율·로그금액). 변수 간 비교는 "
               "mean_shift·psi로 하고 평균 자체는 같은 변수 안에서만 읽는다"),
        C("current_mean", "float", "적용 모집단 평균", nullable=False,
          unit="mixed"),
        C("mean_shift", "float", "평균 이동", nullable=False, unit="ratio",
          note="개발표본 표준편차 대비 평균 차이. 단위가 다른 변수를 한 표에서 "
               "비교하려면 표준화가 필요하다"),
        C("psi", "float", "분포 안정성 지표", nullable=False, unit="ratio",
          min_value=0.0, citation="PSI = Σ(a−e)·ln(a/e)"),
        C("threshold", "float", "합격 임계", nullable=True, unit="ratio",
          min_value=0.0,
          note="[별표 3] 180.가는 임계를 주지 않는다. 내부 승인 임계가 없는 "
               "동안은 NULL이며 판정하지 않는다"),
        C("assessment", "string", "판정", nullable=False, allowed=ASSESSMENTS),
        C("citation", "text", "근거", nullable=False),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("model_id", "segment", "feature", "asof"),
    foreign_keys=(FK(("model_id",), "crm_model", ("model_id",)),),
    note="180.가(데이터 추출)·158.(3)(모집단 대표성)의 증적. 임계가 없으므로 "
         "지표만 산출하고 판정 칸은 '미판정'으로 남는다.",
)

SAMPLE_TABLES = (DEV_SAMPLE, SAMPLE_REPRESENTATIVENESS)


def _min_observation_years(requirements: pd.DataFrame, scope: str) -> float | None:
    """관측기간 요건을 원장에서 읽는다. 5.0이 이 모듈 어디에도 없다."""
    code = "CRS-182-D" if scope == "기업" else "CRS-183-B"
    hit = requirements[requirements["requirement_code"] == code]
    if hit.empty or pd.isna(hit.iloc[0]["threshold_value"]):
        return None
    return float(hit.iloc[0]["threshold_value"])


def build_dev_sample(portfolio: pd.DataFrame, requirements: pd.DataFrame, *,
                     model_map: dict[str, str], asof: str,
                     observation_months: int, holdout_share: float,
                     scope_map: dict[str, str]) -> pd.DataFrame:
    """세그먼트별 개발표본 정의 원장을 만든다.

    observation_months는 이 저장소 합성 포트폴리오의 코호트 범위이며
    `risk_lib.vintage.synthesise_vintage`가 쓰는 값과 같은 뜻이다. 실제 은행은
    원천 데이터의 최초·최종 관측일에서 계산한다. 어느 쪽이든 관측연수는 표본에서
    나온 값이지 요건에서 베껴 온 값이 아니다.
    """
    end = pd.Timestamp(asof)
    start = end - pd.DateOffset(months=int(observation_months))
    years = round(observation_months / 12.0, 4)
    rows = []
    for segment, model_id in model_map.items():
        seg = portfolio[portfolio["asset_class"] == segment]
        if seg.empty:
            continue
        scope = scope_map.get(segment, "공통")
        req_years = _min_observation_years(requirements, scope)
        if req_years is None:
            meets = "미판정"
        else:
            meets = "적합" if years >= req_years else "부적합"
        n = int(len(seg))
        n_def = int(seg["default_12m"].sum())
        # 소매는 174.나 단서로 거래 기준 판단이 허용된다.
        basis = "거래기준" if scope == "소매" else "차주기준"
        rows.append({
            "model_id": model_id,
            "segment": segment,
            "asof": asof,
            "observation_start": start.date().isoformat(),
            "observation_end": end.date().isoformat(),
            "observation_years": float(years),
            "min_observation_years": req_years,
            "meets_minimum": meets,
            "n_obs": n,
            "n_default": n_def,
            "default_rate": float(n_def / n) if n else 0.0,
            "target_definition": (
                "상환청구 조치 없이는 채무를 일부라도 상환받지 못할 것으로 "
                "판단되거나 상당한 수준의 여신을 90일 이상 연체한 경우"),
            "target_horizon_months": 12,
            "target_basis": basis,
            "dpd_trigger_days": _DPD_TRIGGER_DAYS,
            "holdout_share": float(holdout_share),
            "citation": "[별표 3] 174.가 · 178. · 182.라 · 183.나",
            "evidence_status": "원문확인",
            "source_version": SOURCE_VERSION,
        })
    df = pd.DataFrame(rows, columns=DEV_SAMPLE.column_names)
    df["min_observation_years"] = pd.to_numeric(
        df["min_observation_years"], errors="coerce").astype("float64")
    return df


def build_representativeness(dev: pd.DataFrame, current: pd.DataFrame,
                             features: list[str], *, model_id: str,
                             segment: str, asof: str,
                             psi_bins: int) -> pd.DataFrame:
    """개발표본과 적용 모집단의 변수별 분포를 대조한다.

    합격 임계를 인자로도 받지 않는다. 임계를 받으면 호출부가 지어낸 숫자를
    넣게 되고, 그 숫자가 원장에 '판정'으로 남는다.
    """
    rows = []
    for f in features:
        d = pd.to_numeric(dev[f], errors="coerce").dropna().to_numpy(dtype=float)
        c = pd.to_numeric(current[f], errors="coerce").dropna().to_numpy(dtype=float)
        if len(d) == 0 or len(c) == 0:
            continue
        sd = float(np.std(d))
        rows.append({
            "model_id": model_id,
            "segment": segment,
            "feature": f,
            "asof": asof,
            "n_dev": int(len(d)),
            "n_current": int(len(c)),
            "dev_mean": float(np.mean(d)),
            "current_mean": float(np.mean(c)),
            "mean_shift": float((np.mean(c) - np.mean(d)) / sd) if sd > 0 else 0.0,
            "psi": float(_psi(d, c, bins=psi_bins)),
            "threshold": None,
            "assessment": "미판정",
            "citation": "[별표 3] 180.가 · 158.(3)",
            "evidence_status": "원문확인",
        })
    df = pd.DataFrame(rows, columns=SAMPLE_REPRESENTATIVENESS.column_names)
    df["threshold"] = pd.to_numeric(df["threshold"],
                                    errors="coerce").astype("float64")
    return df
