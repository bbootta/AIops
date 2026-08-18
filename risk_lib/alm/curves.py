"""금리 시나리오 원장 + 충격곡선 생성기 (설계 §2.4).

**왜 원장인가.** 현행 `irrbb.py:45-47`은 시나리오 계수 −0.65/0.90/0.80/−0.60을
함수 본문에 숫자로 박아 두고, 충격 bp는 `references.py`의 상수에서 가져온다.
박혀 있는 값은 화면에도 원장에도 나오지 않으므로 검증도 결재도 그 값을 보지
못한다. 이 모듈은 세 가지를 원장으로 옮긴다 — 통화별 충격 모수, 시나리오
구성식, 충격후 금리하한. 엔진 함수에는 계수가 한 개도 없다.

**현행 충격폭은 원문 두 종에서 왔다.** 은행업감독업무시행세칙 [별표 9-1]
<표5>(개정 2026.1.29)와 BCBS d578 «Recalibration of shocks in the IRRBB
standard»(2024.7) [SRP31.90] Table 2가 21개 통화 전건 동일하다. 국내가 d578을
수치 조정 없이 채택했다. 발췌는 `docs/primary_sources/IRRBB_원문발췌.md` §A이고
원문 PDF 텍스트 추출본이 같은 폴더에 있다. **KRW는 평행 225 · 단기 350 ·
장기 225다.**

**직전 회차가 적재한 KRW 300/400/200은 폐지된 값이다.** 그것은 d368(2016.4)
Annex 2 Table 1의 값이고 d578이 대체했다. d368 계정은 대비용으로 남기되
헤드라인이 아니다. KRW는 축마다 개정 방향이 다르다 — 평행 −75bp, 단기 −50bp,
**장기 +25bp**이므로 장기 듀레이션 갭이 큰 포지션에서는 ΔEVE가 오히려 커진다.

**계정이 네 벌이다.** `framework_version`으로 구분하고 `status`가 시행 상태를
적는다. `별표9의1_2014`는 2019.11.29 개정으로 폐지된 금리 EaR·VaR 체계이며
통화별 충격표 자체가 없다. 그 계정을 고르면 산출이 침묵하지 않고 폐지 사실을
경고와 결과 컬럼(`framework_status`)에 싣는다.

**프록시 경로는 없앴다.** 이전 회차는 KRW 행이 비어 있어 USD 계정을 빌려 썼다.
`proxy_for_ccy` 컬럼은 남기되 전 행이 NULL이다 — 컬럼을 지우면 원장 스키마와
화면이 함께 흔들리고, 남겨 두면 "프록시를 쓰지 않는다"는 사실이 원장에서
읽힌다. 원장에 없는 통화가 들어오면 엔진은 경고를 남기고 그 시나리오를
건너뛴다.

공식 출처
  시나리오 구성   S_short(t) = e^{−t/x},  S_long(t) = 1 − e^{−t/x},  x = 4
                  steepener = −0.65·R_s·S_short + 0.90·R_l·S_long
                  flattener = +0.80·R_s·S_short − 0.60·R_l·S_long
                  ([별표 9-1] 제12항 나 = d578 [SRP31.91], 1차자료 §B-6)
  충격후 하한     **[별표 9-1] 제12항 다 — "충격후 금리의 하한은 0으로 한다."**
                  d578 [SRP98.63]이 각국 재량으로 넘긴 것을 국내가 0으로
                  행사했다. 따라서 `별표9의1_2026` 계정의 하한은 0이고 엔진이
                  실제로 적용한다. 국제기준 계정(d368·d578)은 재량 조항만 있고
                  수치가 없으므로 `재량·미규정`이며 하한을 적용하지 않는다.
                  형식은 floor(t) = min(0, floor_on + slope·t), t ≥ terminal → 0
                  이고 세 칸이 모두 0이면 전 만기 하한 0이 된다.
  ΔNII 시나리오   평행충격 2개만 ([별표 9-1] 제14항 라, applies_to_nii).

복리 규약
  이 모듈의 금리는 전부 **연속복리 제로금리**이고 `DF(t) = exp(−z(t)·t)`다.
  기저커브는 `market_data.bootstrap_zero_curve`가 만든 것을 그대로 받는다
  (그쪽 `zero_rates`가 연속복리). 만기 사이는 **log(DF) 선형보간** — 구간별
  상수 선도금리이므로 무차익이고, 자연 큐빅스플라인의 선도금리 오버슛이
  시나리오 재평가에서 인공 손익을 만드는 것을 피한다.

알려진 한계
  · 아래 TableSpec 3장은 아직 `datamodel.catalog.ALL_TABLES`에 넣지 않았다.
    카탈로그 등재는 실체화·ARCHITECTURE.md 수치 검사와 함께 움직이므로
    파이프라인 배선 단계에서 `params.PARAM_TABLES`와 같이 등재한다.
  · `framework_version`에 함수 기본값을 두지 않는다 — 호출자가 명시한다.
    헤드라인 계정명은 `HEADLINE_FRAMEWORK_VERSION`이 한 곳에서 준다.
  · 커브 최종 노드(데모 30년) 이후는 log(DF) 평탄 외삽이며 선도금리가 0이 된다.
    `market_data._df_interp`와 같은 규약을 쓴 결과이고, 규약을 여기서 다시
    정하면 커브가 두 벌이 된다. 현행 버킷 상단은 20년이라 실제로 닿지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from risk_lib.alm.behaviour import ParamWarning
from risk_lib.alm.params import EVIDENCE_STATUS, IRRBB_SCENARIOS
from risk_lib.datamodel.spec import ColumnSpec as C, TableSpec
from risk_lib.market_data import bootstrap_zero_curve

__all__ = [
    "SHOCK_TYPES", "FRAMEWORK_VERSIONS", "FRAMEWORK_STATUSES",
    "HEADLINE_FRAMEWORK_VERSION",
    "RATE_SHOCK_PARAM", "SCENARIO_DEF", "POST_SHOCK_FLOOR", "CURVE_TABLES",
    "build_rate_shock_param", "build_scenario_def", "build_post_shock_floor",
    "build_curve_ledgers", "framework_status",
    "Curve", "ShockedCurve",
    "base_curve", "shocked_curve", "discount_factors", "nii_scenarios",
]

# 충격유형 어휘. 시나리오(6개)와 다른 축이다 — 시나리오는 이 셋을 조합한다.
SHOCK_TYPES: tuple[str, ...] = ("parallel", "short", "long")

# 계정 어휘. 국내기준 두 벌(현행·폐지)과 국제기준 두 벌(현행·직전)이다.
# 별표9의1_2026과 d578_2024는 21개 통화 전건 값이 같다.
FRAMEWORK_VERSIONS: tuple[str, ...] = (
    "별표9의1_2026", "d578_2024", "d368_2016", "별표9의1_2014")

# 시행 상태. '폐지'는 그 계정으로 산출하면 안 된다는 뜻이고, '직전'은 값이
# 유효했던 이력이라 대비용으로만 쓴다는 뜻이다.
FRAMEWORK_STATUSES: tuple[str, ...] = ("현행", "직전", "폐지")

# 헤드라인 계정. 국내 은행의 산출 근거는 [별표 9-1] 개정 2026.1.29이다.
# 소비처가 계정명을 소스에 박지 않도록 이름을 한 곳에서 준다.
HEADLINE_FRAMEWORK_VERSION: str = "별표9의1_2026"

_BP = 10_000.0


# ---------------------------------------------------------------- 스펙

RATE_SHOCK_PARAM = TableSpec(
    name="alm_rate_shock_param", korean="통화별 금리충격 모수", product="PRD-ALM",
    grain="계정(framework_version) × 통화 × 충격유형 1행",
    columns=(
        C("framework_version", "string", "계정", nullable=False,
          allowed=FRAMEWORK_VERSIONS),
        C("ccy", "string", "통화", nullable=False),
        C("shock_type", "string", "충격유형", nullable=False,
          allowed=SHOCK_TYPES),
        C("status", "string", "시행 상태", nullable=False,
          allowed=FRAMEWORK_STATUSES,
          note="'폐지' 계정으로 산출하면 엔진이 경고를 남기고 그 사실이 "
               "alm_irrbb_result.framework_status로 나간다"),
        C("superseded_by", "text", "대체 계정", nullable=True,
          note="이 계정을 무엇이 대체했는지. 현행 계정은 NULL이다"),
        C("effective_from", "date", "적용시작", nullable=True,
          note="국내 시행일이 확인되지 않은 계정은 NULL이다 — 날짜를 지어내면 "
               "과거 asof 산출이 조용히 틀린다"),
        C("effective_to", "date", "적용종료", nullable=True),
        C("shock_bp", "int", "충격폭", nullable=True, unit="bp",
          citation="[별표 9-1] <표5> 통화별 금리충격 규모 (개정 2026.1.29) "
                   "= BCBS d578 [SRP31.90] Table 2. 부호 없는 크기이며 방향은 "
                   "alm_scenario_def의 계수가 준다"),
        C("floor_bp", "int", "모수 하한", nullable=True, unit="bp",
          note="감독당국이 충격폭 자체에 하·상한을 두는 경우에만 채운다. "
               "<표5>·Table 2는 통화별 값을 직접 주고 별도의 모수 하·상한을 "
               "두지 않으므로 전 계정에서 NULL이다"),
        C("cap_bp", "int", "모수 상한", nullable=True, unit="bp",
          note="floor_bp와 같은 규약. 두 칸이 다 차 있을 때만 엔진이 clip한다"),
        C("proxy_for_ccy", "text", "프록시 대상 통화", nullable=True,
          note="이 행을 어느 통화의 대용으로 쓰는지. 1차자료로 KRW 실값이 "
               "확정된 뒤로 전 행이 NULL이며, 프록시를 쓰지 않는다는 사실이 "
               "이 컬럼에서 읽힌다"),
        C("source_ref", "text", "출처", nullable=True),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("framework_version", "ccy", "shock_type"),
    note="별표9의1_2026 · d578_2024 · d368_2016 세 계정이 각각 21개 통화 × "
         "3충격유형 63행이며 전부 원문확인이다. 앞의 두 계정은 21개 통화 전건 "
         "값이 같다 — 국내가 d578을 수치 조정 없이 채택했다. 별표9의1_2014는 "
         "폐지된 금리 EaR·VaR 체계라 통화별 충격표가 없고 값이 비어 있다.",
)

SCENARIO_DEF = TableSpec(
    name="alm_scenario_def", korean="금리 시나리오 구성식", product="PRD-ALM",
    grain="시나리오 1행",
    columns=(
        C("scenario", "string", "시나리오", nullable=False,
          allowed=IRRBB_SCENARIOS),
        C("parallel_coef", "float", "평행충격 계수", nullable=False, unit="배"),
        C("short_coef", "float", "단기충격 계수", nullable=False, unit="배"),
        C("long_coef", "float", "장기충격 계수", nullable=False, unit="배"),
        C("decay_x", "float", "감쇠 파라미터", nullable=False, unit="years",
          min_value=0.0,
          citation="S_short(t)=e^{−t/x}, S_long(t)=1−e^{−t/x}, x=4 — "
                   "[별표 9-1] 제12항 나 = BCBS d578 [SRP31.91] (1차자료 §B-6)"),
        C("applies_to_eve", "bool", "ΔEVE 대상", nullable=False),
        C("applies_to_nii", "bool", "ΔNII 대상", nullable=False,
          citation="[별표 9-1] 제14항 라 — ΔNII는 평행상승·평행하락 2개만 적용"),
        C("citation", "text", "근거", nullable=True),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("scenario",),
    note="Δr(t) = parallel_coef·R_p + short_coef·R_s·S_short(t) "
         "+ long_coef·R_l·S_long(t). 계수가 0인 충격유형은 그 시나리오가 "
         "요구하지 않는다 — 엔진은 필요한 모수만 원장에서 찾는다.",
)

POST_SHOCK_FLOOR = TableSpec(
    name="alm_post_shock_floor", korean="충격후 금리하한", product="PRD-ALM",
    grain="계정(framework_version) 1행",
    columns=(
        C("framework_version", "string", "계정", nullable=False,
          allowed=FRAMEWORK_VERSIONS),
        # 세 칸이 nullable인 이유: d368·d578은 하한을 각국 재량으로 넘기고
        # 수치를 주지 않는다. "규정을 읽었고 그 규정이 값을 정하지 않는다"는
        # 상태를 원장에 적으려면 값 칸이 비어 있을 수 있어야 한다.
        C("floor_on_bp", "int", "만기 0 하한", nullable=True, unit="bp"),
        C("slope_bp_per_year", "int", "연간 상승폭", nullable=True, unit="bp"),
        C("terminal_tenor_years", "float", "하한 소멸 만기", nullable=True,
          unit="years", min_value=0.0),
        C("citation", "text", "근거", nullable=True),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("framework_version",),
    note="floor(t) = min(0, floor_on + slope·t), t ≥ terminal → 0. "
         "별표9의1_2026 행은 세 칸이 모두 0이며 이것이 [별표 9-1] 제12항 다의 "
         "'충격후 금리의 하한은 0으로 한다'를 뜻한다. 국제기준 계정(d368·d578)은 "
         "하한을 각국 재량으로 두고 0 이하라는 상한만 적으므로 세 칸이 비어 "
         "있고 엔진이 하한을 적용하지 않는다.",
)

CURVE_TABLES: tuple[TableSpec, ...] = (
    RATE_SHOCK_PARAM, SCENARIO_DEF, POST_SHOCK_FLOOR)


# ---------------------------------------------------------------- 빌더

# 현행 통화별 금리충격(bp) 21개 통화 전건.
# [별표 9-1] <표5>(개정 2026.1.29) = BCBS d578 [SRP31.90] Table 2. 두 원문의
# 63칸이 전건 동일하다. 발췌는 docs/primary_sources/IRRBB_원문발췌.md §A이며
# 원문 PDF 텍스트 추출본이 같은 폴더에 있다.
# 규제표가 소스에 적히는 곳은 이 한 군데(원장 빌더)다.
# ccy: (parallel, short, long)
_CURRENT_SHOCK_BP: dict[str, tuple[int, int, int]] = {
    "ARS": (400, 500, 300), "AUD": (350, 425, 300), "BRL": (400, 500, 300),
    "CAD": (200, 275, 175), "CHF": (175, 250, 200), "CNY": (225, 300, 150),
    "EUR": (225, 350, 200), "GBP": (275, 425, 250), "HKD": (225, 375, 200),
    "IDR": (400, 500, 300), "INR": (325, 475, 225), "JPY": (100, 100, 100),
    "KRW": (225, 350, 225), "MXN": (400, 500, 200), "RUB": (400, 500, 300),
    "SAR": (275, 375, 250), "SEK": (275, 425, 200), "SGD": (175, 250, 225),
    "TRY": (400, 500, 300), "USD": (200, 300, 225), "ZAR": (325, 500, 300),
}

# 직전 값 — BCBS d368 (2016.4) Annex 2 Table 1. 대비용으로만 둔다.
# IDR 장기 350은 d368 원문 표의 값이다. d578의 개정 대비표는 IDR을 불변으로
# 인쇄했으나 <표5>·Table 2의 현행값은 300이므로 현행 계정은 300을 쓴다.
_D368_SHOCK_BP: dict[str, tuple[int, int, int]] = {
    "ARS": (400, 500, 300), "AUD": (300, 450, 200), "BRL": (400, 500, 300),
    "CAD": (200, 300, 150), "CHF": (100, 150, 100), "CNY": (250, 300, 150),
    "EUR": (200, 250, 100), "GBP": (250, 300, 150), "HKD": (200, 250, 100),
    "IDR": (400, 500, 350), "INR": (400, 500, 300), "JPY": (100, 100, 100),
    "KRW": (300, 400, 200), "MXN": (400, 500, 300), "RUB": (400, 500, 300),
    "SAR": (200, 300, 150), "SEK": (200, 300, 150), "SGD": (150, 200, 100),
    "TRY": (400, 500, 300), "USD": (200, 300, 150), "ZAR": (400, 500, 300),
}

_KR_SOURCE_REF = (
    "은행업감독업무시행세칙 [별표 9-1] 금리리스크 산출기준 <표5> 통화별 "
    "금리충격 규모 <개정 2026.1.29> — 21개 통화 전건. 원문 발췌 "
    "docs/primary_sources/IRRBB_원문발췌.md §A. BCBS d578 [SRP31.90] Table 2와 "
    "63칸이 전건 동일하며 국내가 수치 조정 없이 채택했다.")

_D578_SOURCE_REF = (
    "BCBS d578 «Recalibration of shocks in the interest rate risk in the "
    "banking book standard» (2024.7) [SRP31.90] Table 2, 시행 2026-01-01 — "
    "21개 통화 전건. 국내 [별표 9-1] <표5>(개정 2026.1.29)와 값이 같다. "
    "산출 도출은 2000-01-03~2023-12-29 일별 금리의 6개월 이동창 변화 "
    "99.9백분위에 플로어 100bp · 캡(평행 400 · 단기 500 · 장기 300)을 걸고 "
    "25bp 단위로 반올림한 것이다(SRP98.57~98.62).")

_D368_SOURCE_REF = (
    "BCBS d368 «Interest rate risk in the banking book» (2016.4) Annex 2 "
    "Table 1 — 통화별 금리충격 21개 통화 전건. **d578(2024.7)이 대체한 직전 "
    "값이며 산출에 쓰지 않는다.** KRW 300/400/200은 여기서 나온 값이고 현행은 "
    "225/350/225다. 대비용으로 남긴다.")

_KR2014_SOURCE_REF = (
    "은행업감독업무시행세칙 [별표 9의1] 2014.12.26. 개정본 — 금리 EaR·VaR "
    "체계. **2019.11.29. 개정으로 ΔEVE·ΔNII 체계로 전환되면서 폐지됐다.** "
    "그 체계에는 통화별 금리충격표가 존재하지 않으므로 shock_bp가 비어 있다. "
    "행을 남기는 것은 시계열 단절을 설명하기 위해서이며 산출에 쓰지 않는다.")

# (계정, 상태, 대체계정, 적용시작, 적용종료, 값표, 출처, 근거상태)
_SHOCK_ACCOUNTS: tuple[tuple, ...] = (
    (HEADLINE_FRAMEWORK_VERSION, "현행", None, "2026-01-29", None,
     _CURRENT_SHOCK_BP, _KR_SOURCE_REF, "원문확인"),
    ("d578_2024", "현행", None, "2026-01-01", None,
     _CURRENT_SHOCK_BP, _D578_SOURCE_REF, "원문확인"),
    ("d368_2016", "직전", "d578_2024", "2016-04-01", None,
     _D368_SHOCK_BP, _D368_SOURCE_REF, "원문확인"),
    # 폐지 계정은 값표가 없다 — 그 체계에 통화별 충격표가 존재하지 않는다.
    ("별표9의1_2014", "폐지", HEADLINE_FRAMEWORK_VERSION, "2007-12-21",
     "2019-11-29", None, _KR2014_SOURCE_REF, "원문확인"),
)


def build_rate_shock_param() -> pd.DataFrame:
    """통화별 충격 모수 원장 — 계정 네 벌.

    현행 두 계정(별표9의1_2026 · d578_2024)은 21개 통화 × 3충격유형 63행이
    전부 원문확인이고 값이 서로 같다. d368_2016은 직전값이며 대비용이다.
    별표9의1_2014는 폐지된 금리 EaR·VaR 체계라 통화별 충격표가 없고, 계정
    존재와 폐지 사실만 남긴다(KRW 3행, 값 NULL).

    프록시는 쓰지 않으므로 `proxy_for_ccy`는 전 행 NULL이다.

    `floor_bp`·`cap_bp`는 비운다. <표5>·Table 2는 통화별 충격폭을 직접 주고
    그 위에 별도의 모수 하·상한을 두지 않는다. 앞선 회차가 넣었던
    parallel 100~400 · short 100~500 · long 100~300은 표의 열별 최소·최대를
    규정처럼 적은 것이었다. 엔진은 두 칸이 다 차 있을 때만 clip한다.
    """
    rows = []
    for fw, status, superseded, eff_from, eff_to, table, ref, ev in _SHOCK_ACCOUNTS:
        # 값표가 없는 계정도 행은 만든다. 계정을 고른 산출이 "통화 행이 없다"가
        # 아니라 "폐지된 체계다"를 돌려주어야 사용자가 무엇을 고쳤는지 안다.
        items = table.items() if table is not None else [("KRW", (None,) * 3)]
        for ccy, bps in items:
            for st, bp in zip(SHOCK_TYPES, bps):
                rows.append({
                    "framework_version": fw, "ccy": ccy, "shock_type": st,
                    "status": status, "superseded_by": superseded,
                    "effective_from": eff_from, "effective_to": eff_to,
                    "shock_bp": bp, "floor_bp": None, "cap_bp": None,
                    "proxy_for_ccy": None, "source_ref": ref,
                    "evidence_status": ev,
                })
    return pd.DataFrame(rows).astype(
        {"shock_bp": "Int64", "floor_bp": "Int64", "cap_bp": "Int64"})


def framework_status(shock_param: pd.DataFrame, framework_version: str
                     ) -> tuple[str, str | None]:
    """계정의 시행 상태와 대체 계정. 원장에 없으면 ('미등재', None)이다.

    상태는 통화·충격유형과 무관한 계정 단위 사실이라 아무 행에서나 읽는다.
    통화별 행이 없는 폐지 계정에서도 상태를 읽을 수 있어야 하므로 충격폭
    해석(`_resolve_shock_bp`)보다 앞에 둔다.
    """
    d = shock_param[shock_param["framework_version"] == framework_version]
    if d.empty:
        return "미등재", None
    r = d.iloc[0]
    sup = r.get("superseded_by")
    return str(r["status"]), (None if pd.isna(sup) else str(sup))


# 시나리오 구성 계수 ([별표 9-1] 제12항 나 = d578 [SRP31.91], 1차자료 §B-6).
#   Δsteepener(t) = −0.65·|Δshort(t)| + 0.90·|Δlong(t)|
#   Δflattener(t) = +0.80·|Δshort(t)| − 0.60·|Δlong(t)|
# 계수와 감쇠 x는 d368 이래 바뀌지 않았다. d578이 재조정한 것은 통화별 충격폭
# (<표5>)뿐이고 시나리오 구성식·시간버킷·캡/플로어 체계는 그대로다.
# (scenario, parallel, short, long, applies_to_nii)
_SCENARIOS: tuple[tuple[str, float, float, float, bool], ...] = (
    ("parallel_up",   +1.0,  0.00,  0.00, True),
    ("parallel_down", -1.0,  0.00,  0.00, True),
    ("short_up",       0.0, +1.00,  0.00, False),
    ("short_down",     0.0, -1.00,  0.00, False),
    ("steepener",      0.0, -0.65, +0.90, False),
    ("flattener",      0.0, +0.80, -0.60, False),
)

_DECAY_X = 4.0          # S_short(t) = e^{−t/4} — [별표 9-1] 제12항 나

_SCENARIO_CITATION = (
    "[별표 9-1] 제12항 나 (개정 2026.1.29) = BCBS d578 [SRP31.91] — 6개 표준 "
    "금리충격 시나리오 구성식. S_short(t)=e^{−t/4}, S_long(t)=1−S_short(t), "
    "steepener=−0.65·R_s·S_short+0.90·R_l·S_long, "
    "flattener=+0.80·R_s·S_short−0.60·R_l·S_long (1차자료 §B-6)")


def build_scenario_def() -> pd.DataFrame:
    """시나리오 구성식 원장 (6개).

    `applies_to_nii`가 규칙을 데이터로 만든다 — ΔNII는 6개가 아니라 평행충격
    2개만이다([별표 9-1] 제14항 라).

    계수 네 개(−0.65 / 0.90 / 0.80 / −0.60)와 감쇠 x=4는 원문 두 종에서 같다.
    d578이 재조정한 것은 <표5>의 통화별 충격폭이고 구성식은 그대로다. 원문의
    검산 예시(t=3.5Y, R_s=R_l=100bp → steepener +25.4bp, flattener −1.6bp)를
    `tests/test_alm_curves.py`가 회귀시험으로 고정한다.
    """
    return pd.DataFrame([{
        "scenario": sc, "parallel_coef": p, "short_coef": s, "long_coef": l,
        "decay_x": _DECAY_X,
        # 6개 전부 ΔEVE 대상 ([별표 9-1] 제13항 라 — 6개 중 최대값이 최종 ΔEVE).
        "applies_to_eve": True, "applies_to_nii": nii,
        "citation": _SCENARIO_CITATION,
        "evidence_status": "원문확인",
    } for sc, p, s, l, nii in _SCENARIOS])


_KR_FLOOR_CITATION = (
    "[별표 9-1] 제12항 다 (개정 2026.1.29) — \"만기구간의 충격후 금리는 "
    "무위험금리에 금리충격 시나리오별 충격치를 합산하여 산출한다. 단, 충격후 "
    "금리의 하한은 0으로 한다.\" r_shocked = max(r_base + Δr, 0). "
    "d578 [SRP98.63]이 각국 재량으로 넘긴 하한을 국내가 0으로 행사한 것이다 "
    "(1차자료 §B-6). 세 칸이 모두 0인 것이 전 만기 하한 0을 뜻한다.")

_BCBS_FLOOR_CITATION = (
    "BCBS d368 Annex 2 / d578 [SRP98.63] — 각국 감독당국이 재량으로 충격후 "
    "금리 하한을 둘 수 있고 그 하한은 0을 넘지 않아야 한다고만 적는다. "
    "국제기준 자체는 수치를 주지 않으므로 이 계정에서는 하한을 적용하지 "
    "않는다. 국내가 행사한 값(하한 0)은 별표9의1_2026 행에 있다.")

# (계정, floor_on_bp, slope_bp_per_year, terminal_tenor_years, 근거, 근거상태)
_FLOOR_ROWS: tuple[tuple, ...] = (
    (HEADLINE_FRAMEWORK_VERSION, 0, 0, 0.0, _KR_FLOOR_CITATION, "원문확인"),
    ("d578_2024", None, None, None, _BCBS_FLOOR_CITATION, "재량·미규정"),
    ("d368_2016", None, None, None, _BCBS_FLOOR_CITATION, "재량·미규정"),
)


def build_post_shock_floor() -> pd.DataFrame:
    """충격후 금리하한 원장.

    **별표9의1_2026 행의 하한은 0이다.** 제12항 다가 명시하므로 재량이 아니라
    규정이고, 엔진이 실제로 적용한다. 직전 회차는 "국내도 하한을 규정하지
    않는다"고 적고 하한을 아예 적용하지 않게 두었는데 그것은 폐지된 2014년판을
    읽은 결과였다.

    국제기준 계정 두 벌은 `evidence_status='재량·미규정'`이다. 규정을 읽었고
    그 규정이 수치를 정하지 않는다는 상태이며, "규정을 못 읽었다"(미확인)와
    다른 사건이라 어휘를 나눈다. 이 상태에서 엔진은 하한을 적용하지 않는다.

    폐지 계정(별표9의1_2014)은 ΔEVE 체계가 아니어서 충격후 금리라는 개념이
    없다. 행을 만들지 않으며, 그 계정으로 산출하면 하한 원장 미조회 경고가
    충격 모수 부재 경고와 함께 나온다.
    """
    return pd.DataFrame([{
        "framework_version": fw,
        "floor_on_bp": on, "slope_bp_per_year": slope,
        "terminal_tenor_years": terminal,
        "citation": cite, "evidence_status": ev,
    } for fw, on, slope, terminal, cite, ev in _FLOOR_ROWS]).astype(
        {"floor_on_bp": "Int64", "slope_bp_per_year": "Int64",
         "terminal_tenor_years": "float64"})


def build_curve_ledgers() -> dict[str, pd.DataFrame]:
    """금리 시나리오 원장 3장. 키는 테이블명 — 검증·실체화가 그대로 받는다."""
    return {
        "alm_rate_shock_param": build_rate_shock_param(),
        "alm_scenario_def": build_scenario_def(),
        "alm_post_shock_floor": build_post_shock_floor(),
    }


def nii_scenarios(scenario_def: pd.DataFrame) -> tuple[str, ...]:
    """ΔNII 대상 시나리오. 소비자가 튜플을 다시 박지 않게 원장에서 읽는다."""
    d = scenario_def[scenario_def["applies_to_nii"].astype(bool)]
    return tuple(str(x) for x in d["scenario"])


# ---------------------------------------------------------------- 커브

@dataclass(frozen=True)
class Curve:
    """만기 노드별 **연속복리** 제로금리. 노드 사이는 log(DF) 선형보간."""
    label: str
    asof: str
    tenors: np.ndarray            # years, 증가순
    zero_rates: np.ndarray        # ratio, 연속복리

    def df(self, t) -> np.ndarray:
        return discount_factors(self, t)

    def rate(self, t) -> np.ndarray:
        """보간 만기의 연속복리 제로금리 z(t) = −ln DF(t) / t."""
        tt = np.asarray(t, dtype=float)
        with np.errstate(divide="ignore", invalid="ignore"):
            z = -np.log(discount_factors(self, tt)) / tt
        # t=0에서 z는 정의되지 않는다 — 최단 노드 금리로 잇는다(외삽 아님).
        return np.where(tt > 0.0, z, self.zero_rates[0])


@dataclass(frozen=True)
class ShockedCurve:
    """충격후 커브 + 적용 내역. 진단값을 함께 들고 다녀야 검증이 성립한다."""
    scenario: str
    ccy: str
    framework_version: str
    curve: Curve
    base_rates: np.ndarray        # 충격 전 노드 금리 (ratio)
    shift: np.ndarray             # Δr(t) (ratio, 부호 있음)
    floor_rates: np.ndarray       # floor(t) (ratio). 미적용이면 전량 NaN
    floor_binding: np.ndarray     # 하한이 실제로 문 노드 (bool)
    floor_applied: bool           # 하한 원장을 찾아 적용했는지
    shock_bp: dict[str, int]      # 실제 사용 모수 (하·상한이 있으면 clip 후)
    shock_source: str             # '직접' — 프록시 경로 제거 후 이 값만 나온다
    # 계정의 시행 상태. '현행'이 아니면 산출물이 그 사실을 실어야 한다 —
    # 폐지된 계정으로 낸 수치가 현행 수치와 같은 칸에 놓이면 구별되지 않는다.
    framework_status: str = "현행"

    @property
    def rates(self) -> np.ndarray:
        return self.curve.zero_rates


def discount_factors(curve: Curve, t) -> np.ndarray:
    """할인계수 — **연속복리** `DF(t) = exp(−z(t)·t)`, log(DF) 선형보간.

    보간을 금리가 아니라 log(DF)에 거는 이유: 구간별 상수 선도금리가 되어
    무차익이고, 부트스트랩(`market_data._df_interp`)과 같은 규약이므로 같은
    커브에서 시장리스크와 ALM이 다른 할인계수를 쓰는 일이 없다.
    """
    tt = np.asarray(t, dtype=float)
    xs = np.concatenate(([0.0], curve.tenors))
    ys = np.concatenate(([0.0], -curve.zero_rates * curve.tenors))
    return np.exp(np.interp(tt, xs, ys))


def base_curve(risk_factor: pd.DataFrame, *, asof: str,
               curve_name: str | None = None) -> Curve:
    """`mkt_risk_factor`의 금리 호가에서 기저 제로커브를 만든다.

    저장소에 이미 시장커브가 있으므로 새 원장을 만들지 않는다 — 커브를 여기서
    다시 정의하면 시장리스크(`market_data`)와 ALM이 서로 다른 커브를 쓰게 되고,
    그것이 이 회차가 고치려는 결함(산출 3벌)과 같은 종류의 부채가 된다.
    부트스트랩 관행(단리 예치 구간·쿠폰 스케줄·이분법)도 `bootstrap_zero_curve`
    의 것을 그대로 쓴다.

    `curve_name`을 비우면 해당 기준일의 금리커브가 하나일 때만 그것을 쓴다.
    둘 이상이면 무엇을 골랐는지 산출물에 남지 않으므로 예외를 낸다.
    """
    d = risk_factor[(risk_factor["asof"] == asof)
                    & (risk_factor["risk_class"] == "interest_rate")]
    if curve_name is not None:
        d = d[d["curve"] == curve_name]
    names = sorted({str(x) for x in d["curve"]})
    if not names:
        raise ValueError(
            f"기저커브 없음: asof={asof} curve={curve_name} — "
            "mkt_risk_factor에 interest_rate 행이 없다")
    if len(names) > 1:
        raise ValueError(
            f"금리커브가 여럿이다 {names} — curve_name으로 명시해야 "
            "어느 커브로 할인했는지가 산출물에 남는다")
    d = d.sort_values("tenor")
    zc = bootstrap_zero_curve(d["tenor"].to_numpy(dtype=float),
                              d["value"].to_numpy(dtype=float))
    return Curve(label=names[0], asof=str(asof),
                 tenors=np.asarray(zc.tenors, dtype=float),
                 zero_rates=np.asarray(zc.zero_rates, dtype=float))


# ---------------------------------------------------------------- 충격

def _needed_shock_types(row: pd.Series) -> tuple[str, ...]:
    """시나리오가 실제로 요구하는 충격유형. 계수 0인 축은 모수가 없어도 된다."""
    coefs = {"parallel": row["parallel_coef"], "short": row["short_coef"],
             "long": row["long_coef"]}
    return tuple(st for st in SHOCK_TYPES if float(coefs[st]) != 0.0)


def _clip_bp(value: int, floor_bp, cap_bp) -> int:
    """감독당국이 모수 하·상한을 둔 경우에만 자른다.

    <표5>·Table 2는 통화별 충격폭을 직접 주고 그 위에 하·상한을 두지 않는다.
    두 칸이 비었는데 임의의 경계로 자르면 원문값이 조용히 바뀐다.
    """
    if pd.isna(floor_bp) and pd.isna(cap_bp):
        return int(value)
    out = int(value)
    if not pd.isna(floor_bp):
        out = max(out, int(floor_bp))
    if not pd.isna(cap_bp):
        out = min(out, int(cap_bp))
    return out


def _resolve_shock_bp(shock_param: pd.DataFrame, *, ccy: str,
                      framework_version: str, needed: tuple[str, ...],
                      scenario: str,
                      ) -> tuple[dict[str, int] | None, str, list[ParamWarning]]:
    """충격 모수 해석 — 해당 통화 행만 본다. 비어 있으면 채우지 않고 건너뛴다.

    프록시(다른 통화 행 빌려쓰기)는 제거했다. [별표 9-1] <표5>를 21개 통화
    전건 적재했으므로 표에 있는 통화는 자기 값을 쓰고, 표에 없는 통화는 값이
    없다는 사실이 산출물에 남아야 한다 — 다른 통화 값을 대신 넣으면 그 통화의
    절대수준이 근거 없이 만들어진다.
    """
    warns: list[ParamWarning] = []
    fw = shock_param[shock_param["framework_version"] == framework_version]
    rows = fw[fw["ccy"] == ccy]
    if rows.empty:
        warns.append(ParamWarning(
            "RATE_SHOCK", f"{framework_version}/{ccy}/{scenario}", "shock_bp",
            "해당 통화 행이 원장에 없다 — 시나리오 미산출. 통화를 추가하려면 "
            "1차자료의 통화별 충격폭을 alm_rate_shock_param에 적재해야 한다"))
        return None, "미확인", warns

    by_type = rows.set_index("shock_type")
    out: dict[str, int] = {}
    for st in needed:
        if st not in by_type.index:
            warns.append(ParamWarning(
                "RATE_SHOCK", f"{framework_version}/{ccy}/{scenario}", st,
                "충격유형 행이 원장에 없다 — 시나리오 미산출"))
            return None, "미확인", warns
        r = by_type.loc[st]
        if pd.isna(r["shock_bp"]):
            warns.append(ParamWarning(
                "RATE_SHOCK", f"{framework_version}/{ccy}/{scenario}", st,
                f"shock_bp가 비어 있다 ({r['evidence_status']}) — "
                f"{r['source_ref']}"))
            return None, "미확인", warns
        out[st] = _clip_bp(r["shock_bp"], r["floor_bp"], r["cap_bp"])
    return out, "직접", warns


def _floor_rates(floor: pd.DataFrame, *, framework_version: str,
                 tenors: np.ndarray, scenario: str,
                 ) -> tuple[np.ndarray, bool, list[ParamWarning]]:
    """floor(t) = min(0, floor_on + slope·t), t ≥ terminal → 0.

    행이 없거나 세 칸이 비어 있으면 하한을 적용하지 않고 사유를 경고로 남긴다.
    국제기준 계정(d368·d578)이 후자다 — 원문이 하한을 각국 재량으로 넘기고
    수치를 주지 않는다. 국내 계정(별표9의1_2026)은 세 칸이 0이므로 전 만기에서
    하한 0이 적용된다([별표 9-1] 제12항 다).
    """
    warns: list[ParamWarning] = []
    d = floor[floor["framework_version"] == framework_version]
    if d.empty:
        warns.append(ParamWarning(
            "POST_SHOCK_FLOOR", f"{framework_version}/{scenario}",
            "floor_on_bp",
            "해당 계정의 충격후 하한 행이 원장에 없다 — 하한 미적용. "
            "하한 없이 산출된 커브는 단기구간에서 음수로 내려갈 수 있다"))
        # 0으로 대신 막지 않는다. 0 하한은 그 자체가 하나의 규제 선택이며,
        # 원장이 비었을 때 그것을 조용히 적용하면 없는 규정을 만들어 쓰는 것이 된다.
        return np.full_like(tenors, np.nan), False, warns
    r = d.iloc[0]
    if (pd.isna(r["floor_on_bp"]) or pd.isna(r["slope_bp_per_year"])
            or pd.isna(r["terminal_tenor_years"])):
        warns.append(ParamWarning(
            "POST_SHOCK_FLOOR", f"{framework_version}/{scenario}",
            "floor_on_bp",
            f"하한 수치가 비어 있다 ({r['evidence_status']}) — 하한 미적용. "
            f"{r['citation']}"))
        return np.full_like(tenors, np.nan), False, warns
    raw = (float(r["floor_on_bp"]) + float(r["slope_bp_per_year"]) * tenors) / _BP
    f = np.where(tenors >= float(r["terminal_tenor_years"]),
                 0.0, np.minimum(0.0, raw))
    return f, True, warns


def shocked_curve(base: Curve, scenario: str, *, ccy: str,
                  framework_version: str,
                  shock_param: pd.DataFrame, scenario_def: pd.DataFrame,
                  floor: pd.DataFrame, allow_proxy: bool = False,
                  ) -> tuple[ShockedCurve | None, list[ParamWarning]]:
    """시나리오 충격곡선. 모수가 비어 있으면 `None` + 경고를 돌려준다.

    계정이 '현행'이 아니면 그 사실을 경고로 남기고 결과 객체의
    `framework_status`에 싣는다. 폐지 계정(별표9의1_2014)은 통화별 충격표가
    없어 곡선이 만들어지지 않으며, 그때 산출은 침묵하지 않고 폐지 사유를 낸다.

    순서가 규정이다. (1) 원장 모수를 (하·상한이 있으면) clip 한 뒤
    (2) `Δr(t) = parallel_coef·R_p + short_coef·R_s·e^{−t/x}
    + long_coef·R_l·(1 − e^{−t/x})`를 기저 노드 금리에 더하고
    (3) 충격후 하한 `max(·, floor(t))`를 적용한다. clip을 하한 뒤에 하면
    모수 상한이 무의미해지고, 하한을 clip 전에 걸면 모수가 아니라 결과 금리를
    자르게 된다.

    충격은 **기저 커브의 노드에서** 적용하고 노드 사이는 기저와 같은 보간
    규약(log(DF) 선형)을 따른다. 노드마다 다른 보간을 쓰면 같은 만기의
    base/shocked 할인계수가 다른 규약에서 나와 ΔEVE에 보간 오차가 섞인다.

    `allow_proxy`는 **동작하지 않는다.** 1차자료로 21개 통화 충격폭이 확정된
    뒤 프록시 경로를 제거했으나, 이 인자를 넘기는 호출부(`pipeline.py`·
    `validation/consistency.py`)가 이 파일의 소유 범위 밖이라 인자 자체는
    남겨 둔다. True로 들어오면 무시했다는 사실을 경고로 남기며, 호출부가
    인자를 떼면 이 인자도 사라진다.
    """
    d = scenario_def[scenario_def["scenario"] == scenario]
    if d.empty:
        raise ValueError(f"alm_scenario_def에 없는 시나리오: {scenario}")
    row = d.iloc[0]

    # 상태 확인이 충격폭 해석보다 앞이다. 폐지 계정은 통화별 행 자체가 없어
    # 충격폭 단계에서 "통화 행이 없다"로 끝나는데, 그 문구로는 사용자가 계정을
    # 잘못 골랐다는 사실에 닿지 못한다.
    status, superseded = framework_status(shock_param, framework_version)
    warns: list[ParamWarning] = []
    if status == "폐지":
        warns.append(ParamWarning(
            "RATE_SHOCK", framework_version, "status",
            f"폐지된 계정이다 — 산출에 쓸 수 없다. 현행 계정은 "
            f"{superseded!r}이며, [별표 9의1]은 2019.11.29. 개정으로 금리 "
            f"EaR·VaR 체계에서 ΔEVE·ΔNII 체계로 전환됐다"))
    elif status == "직전":
        warns.append(ParamWarning(
            "RATE_SHOCK", framework_version, "status",
            f"직전 계정이다 — 현행이 아니며 대비 목적으로만 쓴다. 현행 계정은 "
            f"{superseded!r}이다"))

    needed = _needed_shock_types(row)
    bps, source, w = _resolve_shock_bp(
        shock_param, ccy=ccy, framework_version=framework_version,
        needed=needed, scenario=scenario)
    warns.extend(w)
    if allow_proxy:
        warns.append(ParamWarning(
            "RATE_SHOCK", framework_version, "allow_proxy",
            "allow_proxy=True로 호출됐으나 프록시 경로는 제거됐다 — "
            "[별표 9-1] <표5>(개정 2026.1.29) 원문으로 21개 통화 충격폭이 "
            "확정돼 다른 통화를 빌릴 이유가 없다. 이 인자는 무시된다"))
    if bps is None:
        return None, warns

    t = np.asarray(base.tenors, dtype=float)
    x = float(row["decay_x"])
    s_short = np.exp(-t / x)
    s_long = 1.0 - s_short
    r = {st: bps[st] / _BP for st in needed}
    shift = (float(row["parallel_coef"]) * r.get("parallel", 0.0)
             + float(row["short_coef"]) * r.get("short", 0.0) * s_short
             + float(row["long_coef"]) * r.get("long", 0.0) * s_long)

    f, floor_applied, fw_warns = _floor_rates(
        floor, framework_version=framework_version, tenors=t, scenario=scenario)
    warns.extend(fw_warns)

    raw = np.asarray(base.zero_rates, dtype=float) + shift
    shocked = np.maximum(raw, f) if floor_applied else raw
    binding = (raw < f) if floor_applied else np.zeros(len(t), dtype=bool)
    return ShockedCurve(
        scenario=scenario, ccy=ccy, framework_version=framework_version,
        curve=Curve(label=f"{base.label} · {scenario}", asof=base.asof,
                    tenors=t, zero_rates=shocked),
        base_rates=np.asarray(base.zero_rates, dtype=float), shift=shift,
        floor_rates=f, floor_binding=binding, floor_applied=floor_applied,
        shock_bp=dict(bps), shock_source=source, framework_status=status,
    ), warns
