"""금리 시나리오 원장 + 충격곡선 생성기 (설계 §2.4).

**왜 원장인가.** 현행 `irrbb.py:45-47`은 시나리오 계수 −0.65/0.90/0.80/−0.60을
함수 본문에 숫자로 박아 두고, 충격 bp 200/300/150은 `references.py`의 상수에서
가져온다. 박혀 있는 값은 화면에도 원장에도 나오지 않으므로 검증도 결재도 그
값을 보지 못한다. 이 모듈은 세 가지를 원장으로 옮긴다 — 통화별 충격 모수,
시나리오 구성식, 충격후 금리하한. 엔진 함수에는 계수가 한 개도 없다.

**충격폭은 1차자료에서 왔다.** BCBS d368(2016.4) Annex 2 Table 1 원문 발췌를
확보해(`docs/primary_sources/IRRBB_원문발췌.md` §A-1) 21개 통화 전건을 적재한다.
KRW는 parallel 300 · short 400 · long 200이다. 설계 단계에서 KRW short를 450으로
적은 조사가 있었는데 450은 AUD의 short 값이며 표를 옆줄로 읽은 결과다.

**프록시 경로는 없앴다.** 이전 회차는 KRW 행이 비어 있어 USD 계정(200/300/150)을
빌려 썼다. KRW 실값이 모든 축에서 USD보다 크므로 그 경로는 과소산출이었고,
1차자료로 KRW가 확정된 지금은 빌릴 이유가 없다. `proxy_for_ccy` 컬럼은 남기되
전 행이 NULL이다 — 컬럼을 지우면 원장 스키마와 화면이 함께 흔들리고, 남겨 두면
"프록시를 쓰지 않는다"는 사실이 원장에서 읽힌다. 원장에 없는 통화가 들어오면
엔진은 여전히 경고를 남기고 그 시나리오를 건너뛴다.

공식 출처
  시나리오 구성   S_short(t) = e^{−t/x},  S_long(t) = 1 − e^{−t/x},  x = 4
                  steepener = −0.65·R_s·S_short + 0.90·R_l·S_long
                  flattener = +0.80·R_s·S_short − 0.60·R_l·S_long
                  (BCBS d368 Annex 2 — 1차자료 §A-3 원문확인)
  충격후 하한     d368은 하한 **수치를 주지 않는다**. Annex 2는 각국 감독당국이
                  재량으로 정하되 0을 넘지 않아야 한다고만 적는다(1차자료 §A-4).
                  국내 [별표 9의1]도 하한을 규정하지 않는다. 따라서 d368 계정의
                  하한 행은 값이 비어 있고 엔진은 하한을 적용하지 않는다.
                  형식은 floor(t) = min(0, floor_on + slope·t), t ≥ terminal → 0
                  이며, 감독당국이 수치를 정하면 그 값이 원장에 들어온다.
  ΔNII 시나리오   평행충격 2개만 (applies_to_nii). 현행은 `irrbb.py:105`가
                  튜플로 박고 있다 — 규칙을 데이터로 옮긴다.

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
  · 어느 계정(d368_2016 / d578_2024)을 국내에 적용해야 하는지 미확인이므로
    `framework_version`에 기본값을 두지 않는다 — 호출자가 명시한다(§5.1-2).
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
    "SHOCK_TYPES", "FRAMEWORK_VERSIONS",
    "RATE_SHOCK_PARAM", "SCENARIO_DEF", "POST_SHOCK_FLOOR", "CURVE_TABLES",
    "build_rate_shock_param", "build_scenario_def", "build_post_shock_floor",
    "build_curve_ledgers",
    "Curve", "ShockedCurve",
    "base_curve", "shocked_curve", "discount_factors", "nii_scenarios",
]

# 충격유형 어휘. 시나리오(6개)와 다른 축이다 — 시나리오는 이 셋을 조합한다.
SHOCK_TYPES: tuple[str, ...] = ("parallel", "short", "long")
FRAMEWORK_VERSIONS: tuple[str, ...] = ("d368_2016", "d578_2024")

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
        C("effective_from", "date", "적용시작", nullable=True,
          note="국내 시행일이 확인되지 않은 계정은 NULL이다 — 날짜를 지어내면 "
               "과거 asof 산출이 조용히 틀린다"),
        C("effective_to", "date", "적용종료", nullable=True),
        C("shock_bp", "int", "충격폭", nullable=True, unit="bp",
          citation="BCBS d368 (2016.4) Annex 2 Table 1 — 통화별 금리충격. "
                   "부호 없는 크기이며 방향은 alm_scenario_def의 계수가 준다"),
        C("floor_bp", "int", "모수 하한", nullable=True, unit="bp",
          note="감독당국이 충격폭 자체에 하·상한을 두는 경우에만 채운다. "
               "d368 Annex 2 Table 1은 통화별 값을 직접 주고 별도의 모수 "
               "하·상한을 두지 않으므로 d368 계정에서는 NULL이다"),
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
    note="d368 계정은 Annex 2 Table 1의 21개 통화 × 3충격유형 63행이 전부 "
         "원문확인이다. d578(2026-01-01 시행) 계정은 원문을 확보하지 못해 "
         "행만 있고 값이 비어 있다.",
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
                   "BCBS d368 (2016.4) Annex 2 (1차자료 §A-3)"),
        C("applies_to_eve", "bool", "ΔEVE 대상", nullable=False),
        C("applies_to_nii", "bool", "ΔNII 대상", nullable=False,
          citation="ΔNII는 평행충격 2개만 (BCBS d368 / SRP31)"),
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
        # 세 칸이 nullable인 이유: d368은 하한을 각국 재량으로 넘기고 수치를
        # 주지 않는다. "규정을 읽었고 그 규정이 값을 정하지 않는다"는 상태를
        # 원장에 적으려면 값 칸이 비어 있을 수 있어야 한다.
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
         "d368 행은 세 칸이 비어 있고 엔진은 하한을 적용하지 않는다 — "
         "Annex 2가 하한을 각국 재량으로 두고 0 이하라는 상한만 적기 "
         "때문이다(1차자료 §A-4). 감독당국이 수치를 고시하면 그 값이 여기 "
         "들어오고 산출이 자동으로 하한을 물기 시작한다.",
)

CURVE_TABLES: tuple[TableSpec, ...] = (
    RATE_SHOCK_PARAM, SCENARIO_DEF, POST_SHOCK_FLOOR)


# ---------------------------------------------------------------- 빌더

# BCBS d368 (2016.4) Annex 2 Table 1 — 통화별 금리충격(bp) 21개 통화 전건.
# 1차자료 발췌는 docs/primary_sources/IRRBB_원문발췌.md §A-1이며 원문 PDF
# 텍스트 추출본이 같은 폴더에 있다. 규제표가 소스에 적히는 곳은 이 한 군데다.
# ccy: (parallel, short, long)
_D368_SHOCK_BP: dict[str, tuple[int, int, int]] = {
    "ARS": (400, 500, 300), "AUD": (300, 450, 200), "BRL": (400, 500, 300),
    "CAD": (200, 300, 150), "CHF": (100, 150, 100), "CNY": (250, 300, 150),
    "EUR": (200, 250, 100), "GBP": (250, 300, 150), "HKD": (200, 250, 100),
    "IDR": (400, 500, 350), "INR": (400, 500, 300), "JPY": (100, 100, 100),
    "KRW": (300, 400, 200), "MXN": (400, 500, 300), "RUB": (400, 500, 300),
    "SAR": (200, 300, 150), "SEK": (200, 300, 150), "SGD": (150, 200, 100),
    "TRY": (400, 500, 300), "USD": (200, 300, 150), "ZAR": (400, 500, 300),
}

_D368_SOURCE_REF = (
    "BCBS d368 «Interest rate risk in the banking book» (2016.4) Annex 2 "
    "Table 1 — 통화별 금리충격 21개 통화 전건. 원문 발췌 "
    "docs/primary_sources/IRRBB_원문발췌.md §A-1. 국내 [별표 9의1]은 이 표를 "
    "쓰지 않고 별개 체계(금리 EaR·VaR, 원화는 과거 5년 실측 분위수)를 두므로 "
    "effective_from은 비워 둔다 — 국내 적용 시행일을 확인하지 못했다.")

_D578_SOURCE_REF = (
    "BCBS d578(2024 재조정, 시행 2026-01-01)의 충격폭은 원문을 확보하지 "
    "못했다. 행만 두고 값은 비운다 — 부재와 공란은 다른 사건이다.")


def build_rate_shock_param() -> pd.DataFrame:
    """통화별 충격 모수 원장.

    d368 계정은 21개 통화 × 3충격유형 63행이 전부 원문확인이다. 프록시는 쓰지
    않으므로 `proxy_for_ccy`는 전 행 NULL이다.

    `floor_bp`·`cap_bp`는 비운다. Annex 2 Table 1은 통화별 충격폭을 직접 주고
    그 위에 별도의 모수 하·상한을 두지 않는다. 앞선 회차가 넣었던
    parallel 100~400 · short 100~500 · long 100~300은 표의 열별 최소·최대를
    규정처럼 적은 것이고, long 상한 300은 IDR의 350을 잘라 원문값을 훼손한다.
    엔진은 두 칸이 다 차 있을 때만 clip한다.
    """
    rows = []
    for ccy, bps in _D368_SHOCK_BP.items():
        for st, bp in zip(SHOCK_TYPES, bps):
            rows.append({
                "framework_version": "d368_2016", "ccy": ccy, "shock_type": st,
                "effective_from": None, "effective_to": None,
                "shock_bp": bp, "floor_bp": None, "cap_bp": None,
                "proxy_for_ccy": None, "source_ref": _D368_SOURCE_REF,
                "evidence_status": "원문확인",
            })
    for st in SHOCK_TYPES:
        rows.append({
            "framework_version": "d578_2024", "ccy": "KRW", "shock_type": st,
            "effective_from": "2026-01-01", "effective_to": None,
            "shock_bp": None, "floor_bp": None, "cap_bp": None,
            "proxy_for_ccy": None, "source_ref": _D578_SOURCE_REF,
            "evidence_status": "미확인",
        })
    return pd.DataFrame(rows).astype(
        {"shock_bp": "Int64", "floor_bp": "Int64", "cap_bp": "Int64"})


# 시나리오 구성 계수 (BCBS d368 Annex 2, 1차자료 §A-3).
#   Δsteepener(t) = −0.65·|Δshort(t)| + 0.90·|Δlong(t)|
#   Δflattener(t) = +0.80·|Δshort(t)| − 0.60·|Δlong(t)|
# (scenario, parallel, short, long, applies_to_nii)
_SCENARIOS: tuple[tuple[str, float, float, float, bool], ...] = (
    ("parallel_up",   +1.0,  0.00,  0.00, True),
    ("parallel_down", -1.0,  0.00,  0.00, True),
    ("short_up",       0.0, +1.00,  0.00, False),
    ("short_down",     0.0, -1.00,  0.00, False),
    ("steepener",      0.0, -0.65, +0.90, False),
    ("flattener",      0.0, +0.80, -0.60, False),
)

_DECAY_X = 4.0          # S_short(t) = e^{−t/4} — BCBS d368 Annex 2 (§A-3)

_SCENARIO_CITATION = (
    "BCBS d368 (2016.4) Annex 2 — 6개 표준 금리충격 시나리오 구성식. "
    "S_short(t)=e^{−t/4}, S_long(t)=1−S_short(t), "
    "steepener=−0.65·R_s·S_short+0.90·R_l·S_long, "
    "flattener=+0.80·R_s·S_short−0.60·R_l·S_long (1차자료 §A-3)")


def build_scenario_def() -> pd.DataFrame:
    """시나리오 구성식 원장 (6개).

    `applies_to_nii`가 규칙을 데이터로 만든다 — ΔNII는 6개가 아니라 평행충격
    2개만이며, 현행은 이 규칙이 `irrbb.py:105`의 튜플 리터럴로만 존재한다.

    계수 네 개(−0.65 / 0.90 / 0.80 / −0.60)와 감쇠 x=4는 원문 발췌로 확인했다.
    원문의 검산 예시(t=3.5Y, R_s=R_l=100bp → steepener +25.4bp,
    flattener −1.6bp)를 `tests/test_alm_curves.py`가 회귀시험으로 고정한다.
    """
    return pd.DataFrame([{
        "scenario": sc, "parallel_coef": p, "short_coef": s, "long_coef": l,
        "decay_x": _DECAY_X,
        # 6개 전부 ΔEVE 대상 (BCBS d368 Annex 2 표준체계 시나리오 집합).
        "applies_to_eve": True, "applies_to_nii": nii,
        "citation": _SCENARIO_CITATION,
        "evidence_status": "원문확인",
    } for sc, p, s, l, nii in _SCENARIOS])


_FLOOR_CITATION = (
    "BCBS d368 (2016.4) Annex 2 — \"National supervisors may, at their "
    "discretion, set floors for the post-shock interest rates …, provided the "
    "floors are not greater than zero.\" 하한 수치는 원문에 없다. 국내 "
    "「은행업감독업무시행세칙」 [별표 9의1]도 하한을 규정하지 않는다 "
    "(1차자료 §A-4). 앞선 회차의 −100bp + 5bp/년은 d368 원문에 없는 값이라 "
    "뺐다 — d578 또는 SRP31 값으로 추정되며 미확인이다.")


def build_post_shock_floor() -> pd.DataFrame:
    """충격후 금리하한 원장. d368 계정만 적재하고 **값은 비어 있다**.

    행을 지우지 않는 이유는 "규정을 읽었고 그 규정이 값을 정하지 않는다"와
    "규정을 못 읽었다"가 다른 사건이기 때문이다. 앞의 것이
    `evidence_status='재량·미규정'`이고, 이 상태에서 엔진은 하한을 적용하지
    않는다. 감독당국이 수치를 고시하면 이 세 칸을 채우는 것만으로 산출이
    하한을 물기 시작한다.

    d578에서 하한 규정이 유지·변경됐는지 확인하지 못했으므로 `d578_2024` 행은
    만들지 않는다.
    """
    return pd.DataFrame([{
        "framework_version": "d368_2016",
        "floor_on_bp": None, "slope_bp_per_year": None,
        "terminal_tenor_years": None,
        "citation": _FLOOR_CITATION,
        "evidence_status": "재량·미규정",
    }]).astype({"floor_on_bp": "Int64", "slope_bp_per_year": "Int64",
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

    d368 Annex 2 Table 1은 통화별 충격폭을 직접 주고 그 위에 하·상한을 두지
    않는다. 두 칸이 비었는데 임의의 경계로 자르면 원문값이 조용히 바뀐다.
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

    프록시(다른 통화 행 빌려쓰기)는 제거했다. d368 Annex 2 Table 1을 21개 통화
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
    d368 계정이 후자다 — 원문이 하한을 각국 재량으로 넘기고 수치를 주지 않으며
    국내도 규정하지 않았다.
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

    needed = _needed_shock_types(row)
    bps, source, warns = _resolve_shock_bp(
        shock_param, ccy=ccy, framework_version=framework_version,
        needed=needed, scenario=scenario)
    if allow_proxy:
        warns.append(ParamWarning(
            "RATE_SHOCK", framework_version, "allow_proxy",
            "allow_proxy=True로 호출됐으나 프록시 경로는 제거됐다 — "
            "BCBS d368 Annex 2 Table 1 원문으로 통화별 충격폭이 확정돼 다른 "
            "통화를 빌릴 이유가 없다. 이 인자는 무시된다"))
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
        shock_bp=dict(bps), shock_source=source,
    ), warns
