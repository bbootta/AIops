"""신용위험경감(CRM) 계수 원장. 배분 엔진이 읽는 규제계수의 유일한 출처.

**왜 원장인가.** 통화불일치 차감률 8%와 만기불일치 산식의 상수 0.25·5년은
규제표의 값이다. 엔진 함수 본문이나 기본값에 박아 두면 화면에 나오지 않고,
화면에 없으면 검증도 결재도 그 값을 보지 못한다. 이 저장소 규약은 규제표를
적재하는 곳을 원장 빌더 한 군데로 못박는다. 여기가 그 자리다.

**담보 차감률(Hc)은 여기 없다.** [별표 3] 65.가의 담보차감률 표는 이미
`rdm_collateral.haircut` 컬럼과 `risk_lib.capital.crm._SUPERVISORY_HAIRCUTS`가
갖고 있다. 여기 다시 적으면 규제표가 두 벌이 되고, 두 벌은 언젠가 갈라진다.
배분 엔진은 담보 원장이 들고 있는 차감률을 그대로 쓴다.

**배분규칙 기본값은 비어 있다.** [별표 3] 제2장 제6절(신용위험경감기법)은
익스포저 1건에 여러 경감기법이 걸린 경우의 처리(102.가)만 정하고, 담보 1건을
여러 익스포저에 나누는 순서는 정하지 않는다. 원문을 읽고 규정이 없음을 확인한
상태이므로 `evidence_status='재량·미규정'`이고 값은 NULL이다. 엔진은 배분규칙을
필수 인자로 받으며 기본값을 갖지 않는다.

출처 표기 규칙은 `risk_lib.alm.params`와 같다.
"""

from __future__ import annotations

import pandas as pd

from risk_lib.alm.params import EVIDENCE_STATUS
from risk_lib.datamodel.spec import ColumnSpec as C, TableSpec

__all__ = [
    "MITIGATION_PARAM", "PARAM_CODES", "build_crm_mitigation_param",
    "param_value",
]

# 원문 파일: docs/primary_sources/규정원문_20260809/
#             02_별표3_바젤III_자기자본비율_산출기준.txt
_BASE = "은행업감독업무시행세칙 [별표 3] 신용·운영리스크 자기자본비율 산출기준"

PARAM_CODES: tuple[str, ...] = (
    "ccy_mismatch_haircut",
    "maturity_min_original_years",
    "maturity_min_residual_years",
    "maturity_offset_years",
    "maturity_cap_years",
    "alloc_rule_default",
)


MITIGATION_PARAM = TableSpec(
    name="crm_mitigation_param", korean="신용위험경감 계수", product="PRD-RWA",
    grain="계수 1건당 1행",
    columns=(
        C("param_code", "string", "계수 코드", nullable=False,
          allowed=PARAM_CODES),
        C("param_value", "float", "값", nullable=True,
          unit="param_unit 컬럼 참조",
          note="NULL은 '규정이 값을 정하지 않았다' 또는 '원문 미확인'이다. "
               "엔진은 NULL을 만나면 조용히 기본값을 쓰지 않고 경고를 남기고 "
               "해당 조정을 건너뛴다"),
        C("param_unit", "string", "단위", nullable=False,
          allowed=("ratio", "years", "code")),
        C("scope", "text", "적용 범위", nullable=False),
        C("citation", "text", "근거", nullable=False),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("param_code",),
    note="배분 엔진에는 규제 상수가 한 개도 없다. 전부 이 원장에서 읽는다.",
)


def build_crm_mitigation_param() -> pd.DataFrame:
    """계수 원장을 적재한다. 이 함수가 곧 수기입력 프로세스다."""
    rows = [
        {
            "param_code": "ccy_mismatch_haircut",
            "param_value": 0.08, "param_unit": "ratio",
            "scope": "담보통화와 익스포저 통화가 다를 때 담보가치에 적용하는 차감률",
            "citation": f"{_BASE} 65.나 (개정 2020.4.8). 일별 시가평가·"
                        "10영업일 보유기간 가정, Hfx = 8%",
            "evidence_status": "원문확인",
        },
        {
            "param_code": "maturity_min_original_years",
            "param_value": 1.0, "param_unit": "years",
            "scope": "경감기법 원(original)만기 하한. 미달이면 경감효과 불인정",
            "citation": f"{_BASE} 100.(1). 원만기 1년 미만이면 적용 불가",
            "evidence_status": "원문확인",
        },
        {
            "param_code": "maturity_min_residual_years",
            "param_value": 0.25, "param_unit": "years",
            "scope": "경감기법 잔존만기 하한. 이하이면 경감효과 불인정",
            "citation": f"{_BASE} 100.(2). 잔존만기 3개월 이하이면 적용 불가",
            "evidence_status": "원문확인",
        },
        {
            "param_code": "maturity_offset_years",
            "param_value": 0.25, "param_unit": "years",
            "scope": "만기불일치 조정식 Pa = P × (t-0.25)/(T-0.25) 의 차감항",
            "citation": f"{_BASE} 101. (계산방법)",
            "evidence_status": "원문확인",
        },
        {
            "param_code": "maturity_cap_years",
            "param_value": 5.0, "param_unit": "years",
            "scope": "만기불일치 조정식의 T = Min[5, 익스포저 잔존만기] 상한",
            "citation": f"{_BASE} 101.의 T(연단위) : Min[5, 익스포져의 잔존만기]",
            "evidence_status": "원문확인",
        },
        {
            # 값이 비어 있는 것 자체가 산출물이다. 규정이 정하지 않았다는 사실을
            # 원장에 남겨야 "왜 규칙을 인자로 받는가"에 근거가 붙는다.
            "param_code": "alloc_rule_default",
            "param_value": None, "param_unit": "code",
            "scope": "담보 1건을 여러 익스포저에 나눌 때의 배분 순서",
            "citation": f"{_BASE} 제2장 제6절. 102.가는 익스포저 1건에 여러 "
                        "경감기법이 걸린 경우 '각 경감기법이 적용되는 부분으로 "
                        "구분'하라고만 정하고, 담보 1건을 여러 익스포저에 나누는 "
                        "순서는 정하지 않는다",
            "evidence_status": "재량·미규정",
        },
    ]
    return pd.DataFrame(rows).astype({"param_value": "float64"})


def param_value(param: pd.DataFrame, code: str) -> float | None:
    """계수 조회.

    행 자체가 없으면 원장 결함이므로 `KeyError`로 멈춘다. 행은 있고 값이 NULL이면
    "규정이 정하지 않았다"이므로 `None`을 돌려주고, 호출자가 경고를 남기고 그
    조정을 건너뛴다. 두 사건을 같은 방식으로 처리하면 원장 누락이 조용히
    "조정 생략"으로 둔갑한다.
    """
    hit = param.loc[param["param_code"] == code, "param_value"]
    if hit.empty:
        raise KeyError(f"crm_mitigation_param에 {code!r} 행이 없다")
    v = hit.iloc[0]
    return None if pd.isna(v) else float(v)
