"""추정 산출의 공통 어휘·산출이력 원장 (IRB-E000).

세 모수(PD·LGD·CCF)의 추정은 산식이 다르지만 감독당국이 묻는 것은 같다.
어느 기간을 봤나(180.·182.·186.·195.), 어떤 기준으로 평균했나(182.바·185.가·
195.다), 하한이 물었나(123.·131.·132.), 얼마를 보수적으로 더했나(181.),
언제 점검했나(179.나·193.마). 그 답을 담는 자리가 산출이력 원장이다.

**추정치와 적용치를 분리한다.** ``raw_estimate → after_floor → after_moc →
final_applied`` 네 단계를 각 추정 원장이 컬럼으로 들고 있고, 산출이력 원장은
그 단계에서 하한이 문 건수와 금액을 들고 있다. 최종치 한 칸만 있으면 그 값이
추정에서 나온 것인지 하한에서 나온 것인지 화면에서 구분되지 않는다.
"""

from __future__ import annotations

import hashlib

import pandas as pd

from risk_lib.datamodel.spec import ColumnSpec as C, TableSpec

__all__ = [
    "PARAMETERS", "ESTIMATION_BASES", "PD_METHODS", "RUN_STATUS",
    "MOC_STATUS", "MOC_DRIVERS", "CENSORING_TREATMENTS",
    "ESTIMATION_RUN", "MOC_COMPONENT",
    "EstimationWarning", "run_id", "cast_to_spec", "min_years_param_code",
]


class EstimationWarning(UserWarning):
    """모수가 없어 조정을 건너뛰거나 산출을 중단했다는 경고."""


PARAMETERS: tuple[str, ...] = ("PD", "LGD", "CCF")
# 182.바는 PD에 '차주수 기준 단순평균'을, 185.가(1)과 195.다는 LGD·EAD에
# '부도가중평균'을 요구한다. 어휘를 하나로 두고 모수별로 어느 값이 허용되는지
# 검사가 잡는다. PD 행에 부도가중평균이 적히면 조문 위반이다.
ESTIMATION_BASES: tuple[str, ...] = (
    "장기평균(연도동일가중)", "차주수가중평균", "부도가중평균", "경기침체")
# 182.가의 세 방법. 어느 방법을 썼는지가 원장에 남아야 한다.
PD_METHODS: tuple[str, ...] = ("내부부도경험", "외부등급매핑", "통계적부도예측모형")
RUN_STATUS: tuple[str, ...] = (
    "산출완료", "산출완료(요건미충족)", "표본부족", "산출불가",
    "자체추정불가(표준방법100%)")
MOC_STATUS: tuple[str, ...] = ("산출완료", "부분산출", "기준미승인", "해당없음")
MOC_DRIVERS: tuple[str, ...] = ("데이터품질", "모형품질", "대표성")
CENSORING_TREATMENTS: tuple[str, ...] = ("제외", "보수적포함")


def run_id(*, asof: str, parameter: str, segment: str, seed: int) -> str:
    """산출 식별자. 파이썬 내장 hash()는 프로세스마다 솔트가 달라 쓰지 않는다."""
    key = f"{asof}|{parameter}|{segment}|{seed}".encode()
    return f"EST_{parameter}_{hashlib.sha256(key).hexdigest()[:10]}"


def min_years_param_code(parameter: str, segment: str) -> str:
    """세그먼트별 최소 관측기간 모수 코드.

    기업과 소매의 최소 관측기간이 다르다(LGD·EAD는 7년 대 5년). 세그먼트를
    보지 않고 한 값을 쓰면 소매를 과도하게 막거나 기업을 통과시킨다.
    """
    kind = "corporate" if segment in ("corporate", "sovereign", "bank") else "retail"
    key = {"PD": "pd", "LGD": "lgd", "CCF": "ccf"}[parameter]
    return f"obs_years_min_{key}_{kind}"


ESTIMATION_RUN = TableSpec(
    name="crm_estimation_run", korean="추정 산출이력", product="PRD-RWA",
    grain="기준일 × 모수 × 세그먼트 1건당 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("parameter", "string", "모수", nullable=False, allowed=PARAMETERS),
        C("segment", "string", "세그먼트", nullable=False,
          note="CCF는 세그먼트와 신용환산 구분의 조합이 추정 단위이므로 "
               "'corporate/commitment_gt_1y' 형태로 적는다. 세그먼트만으로 "
               "묶으면 환산율이 다른 약정이 한 줄에 뭉쳐 하한 비교가 무의미해진다"),
        C("run_id", "string", "산출 식별자", nullable=False),
        C("exposure_class", "string", "자산군", nullable=False),
        C("method", "text", "추정방법", nullable=False,
          citation="[별표 3] 182.가 추정방법 3종"),
        C("estimation_basis", "string", "평균 기준", nullable=False,
          allowed=ESTIMATION_BASES,
          citation="[별표 3] 182.바 · 185.가(1) · 195.다"),
        C("observation_start", "date", "관측 시작", nullable=True),
        C("observation_end", "date", "관측 종료", nullable=True),
        C("observation_years", "float", "관측기간", nullable=True, unit="years",
          min_value=0.0),
        C("min_observation_years", "float", "최소 관측기간", nullable=True,
          unit="years", min_value=0.0,
          note="NULL이면 원장에 최소요건이 없다는 뜻이고 판정하지 않는다"),
        C("meets_minimum", "bool", "최소요건 충족", nullable=True,
          citation="[별표 3] 182.라·마 · 183.나 · 186. · 187.가 · 195. · 196.",
          note="최소요건이 NULL이면 이 컬럼도 NULL이다. 판정할 수 없는 것을 "
               "True로 두면 미달이 통과로 둔갑한다"),
        C("n_obligors", "int", "관측 차주수", nullable=True, min_value=0),
        C("n_defaults", "int", "관측 부도건수", nullable=True, min_value=0),
        C("n_observations", "int", "관측 건수", nullable=True, min_value=0),
        C("n_censored", "int", "관측중단 건수", nullable=True, min_value=0),
        C("estimation_window_end", "int", "추정 표본 마지막 연도", nullable=True,
          min_value=1900, max_value=2200),
        C("holdout_year", "int", "사후검증 유보연도", nullable=True,
          min_value=1900, max_value=2200,
          note="추정 표본에서 뺀 연도. 표본외 검증(203.)의 전제다"),
        C("moc_amount", "float", "MoC 합계", nullable=True, unit="ratio",
          citation="[별표 3] 181.",
          note="PD는 MoC가 등급 단위라 산출이력 한 줄에 담기지 않는다. PD 행은 "
               "NULL이고 등급별 값은 crm_pd_estimate와 crm_moc_component에 "
               "있다. 등급 평균 한 값을 여기 적으면 등급별 차이가 사라진다"),
        C("moc_status", "string", "MoC 상태", nullable=False,
          allowed=MOC_STATUS),
        C("moc_rationale", "text", "MoC 근거", nullable=True),
        C("moc_aggregation", "string", "MoC 합산방식", nullable=True),
        C("floor_applied", "bool", "하한 적용", nullable=False,
          note="하한값이 원장에 있고 실제로 비교에 쓰였는지. 하한이 미확인이면 "
               "False이고 status와 unresolved_inputs가 이유를 적는다"),
        C("n_floor_binding", "int", "하한이 문 건수", nullable=True,
          min_value=0),
        C("amount_floor_binding", "float", "하한이 문 익스포저", nullable=True,
          unit="KRW", min_value=0.0),
        C("default_definition", "text", "부도정의", nullable=True,
          citation="[별표 3] 178."),
        C("definition_adjustment", "text", "부도정의 조정", nullable=True,
          citation="[별표 3] 178. 부도정의가 다른 데이터의 조정"),
        C("population_alignment", "text", "대표성 판정", nullable=True,
          citation="[별표 3] 180."),
        C("last_review_date", "date", "최근 점검일", nullable=True,
          citation="[별표 3] 179.나 · 193.마"),
        C("next_review_due", "date", "다음 점검기한", nullable=True),
        C("review_interval_months", "float", "점검주기", nullable=True,
          unit="months", min_value=0.0),
        C("unresolved_inputs", "text", "미해결 입력", nullable=True,
          note="값이 없어 건너뛴 모수 목록. 비어 있지 않으면 산출물은 그 조정을 "
               "받지 않은 값이다"),
        C("status", "string", "산출 상태", nullable=False, allowed=RUN_STATUS),
        C("framework_version", "string", "규제판본", nullable=False),
        C("seed", "int", "난수 시드", nullable=False),
        C("source_system", "string", "원천", nullable=False),
    ),
    primary_key=("asof", "parameter", "segment"),
    note="이 원장 한 줄이 '무엇을 어느 기간 어떤 기준으로 추정했고 무엇을 "
         "못 했나'를 답한다.",
)

MOC_COMPONENT = TableSpec(
    name="crm_moc_component", korean="보수적 조정(MoC) 구성", product="PRD-RWA",
    grain="기준일 × 모수 × 세그먼트 × 등급 × MoC 원천 1건당 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("parameter", "string", "모수", nullable=False, allowed=PARAMETERS),
        C("segment", "string", "세그먼트", nullable=False),
        C("grade", "string", "등급 또는 자산군", nullable=False),
        C("moc_driver", "string", "MoC 원천", nullable=False,
          allowed=MOC_DRIVERS,
          citation="[별표 3] 181. 모형·데이터 품질과 180. 대표성"),
        C("point_estimate", "float", "원시추정치", nullable=True, unit="ratio"),
        C("moc_amount", "float", "조정폭", nullable=True, unit="ratio",
          note="절대 가산폭이다. 음수면 보수화가 아니라 완화이며 검사가 잡는다"),
        C("moc_formula", "text", "산식", nullable=False),
        C("moc_rationale", "text", "근거", nullable=False),
        C("param_code", "string", "사용 모수", nullable=True),
        C("param_available", "bool", "모수 존재", nullable=False,
          note="False면 조정폭이 NULL이고 그 원천의 MoC를 적용하지 않았다"),
    ),
    primary_key=("asof", "parameter", "segment", "grade", "moc_driver"),
    note="181.은 조정을 요구하되 크기를 주지 않는다. 세 원천을 나눠 두어야 "
         "어느 결함 때문에 얼마를 더했는지 감독당국이 본다.",
)


def cast_to_spec(df: pd.DataFrame, spec: TableSpec) -> pd.DataFrame:
    """스펙의 int·float·bool dtype을 맞춘다.

    전건 NaN 컬럼을 pandas가 object로 두면 스펙 검증이 dtype 위반으로 잡는다.
    산출이 비어 있는 기준일에도 원장은 스펙을 통과해야 화면과 검증이 같은 계약
    위에 선다. nullable한 int·bool 컬럼은 pandas 확장 타입으로 둔다.
    """
    out = df.copy()
    for col in spec.columns:
        if col.name not in out.columns:
            continue
        if col.dtype == "float":
            out[col.name] = pd.to_numeric(out[col.name],
                                          errors="coerce").astype("float64")
        elif col.dtype == "int":
            num = pd.to_numeric(out[col.name], errors="coerce")
            out[col.name] = (num.astype("Int64") if col.nullable
                             else num.astype("int64"))
        elif col.dtype == "bool" and not col.nullable:
            out[col.name] = out[col.name].astype(bool)
    return out.reset_index(drop=True)
