"""금리 시나리오 원장 + 충격곡선 생성기 (설계 §2.4).

**왜 원장인가.** 현행 `irrbb.py:45-47`은 시나리오 계수 −0.65/0.90/0.80/−0.60을
함수 본문에 숫자로 박아 두고, 충격 bp 200/300/150은 `references.py`의 상수에서
가져온다. 박혀 있는 값은 화면에도 원장에도 나오지 않으므로 검증도 결재도 그
값을 보지 못한다. 이 모듈은 세 가지를 원장으로 옮긴다 — 통화별 충격 모수,
시나리오 구성식, 충격후 금리하한. 엔진 함수에는 계수가 한 개도 없다.

**프록시가 이 설계의 핵심 컬럼이다.** 현행 산출은 USD 계정의 200/300/150을
KRW 포트폴리오에 쓰는데, 그 사실이 주석에만 있다. `proxy_for_ccy` 컬럼을 두면
프록시 사용이 원장 → 서식 → 화면 → 독립검증으로 그대로 노출되고, 엔진은
프록시를 쓸 때마다 `ParamWarning`을 남긴다.

**충격 bp를 이번에 바꾸지 않는다.** 두 조사가 구 d368 KRW short조차 450 vs 400
으로 어긋나고 둘 다 bis.org 접속차단으로 1차자료를 읽지 못했다(설계 §0·§5.1).
따라서 KRW 행은 `shock_bp=NULL`로 **존재하되 비어 있고**, 엔진은 빈 칸을 만나면
조용히 기본값을 쓰지 않고 경고를 남긴 뒤 해당 통화를 건너뛴다. 현행 산출을
재현해야 하는 소비자는 `allow_proxy=True`로 USD 행을 **명시적으로** 빌려 쓴다.

공식 출처
  시나리오 구성   S_short(t) = e^{−t/x},  S_long(t) = 1 − e^{−t/x},  x = decay_x
                  steepener = −0.65·R_s·S_short + 0.90·R_l·S_long
                  flattener = +0.80·R_s·S_short − 0.60·R_l·S_long
                  (BCBS d368 Annex 2 §132 — 계수는 현행 코드 계승, 원문 미확인)
  충격후 하한     floor(t) = min(0, −0.01 + 0.0005·t), t ≥ 20 → 0
                  r_shocked(t) = max(r_base(t) + Δr(t), floor(t))
                  (BCBS d368 §132 / SRP31 — 현행 코드에는 하한 자체가 없다)
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
          citation="BCBS d368 Annex 2 — 통화별 금리충격. 부호 없는 크기이며 "
                   "방향은 alm_scenario_def의 계수가 준다"),
        C("floor_bp", "int", "모수 하한", nullable=True, unit="bp"),
        C("cap_bp", "int", "모수 상한", nullable=True, unit="bp",
          citation="parallel 400 / short 500 / long 300 — 두 조사 검색확인"),
        C("proxy_for_ccy", "text", "프록시 대상 통화", nullable=True,
          note="이 행을 어느 통화의 대용으로 쓰는지. 현행 산출은 USD 계정을 "
               "KRW에 쓴다 — 그 사실을 주석이 아니라 원장에 남긴다"),
        C("source_ref", "text", "출처", nullable=True),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("framework_version", "ccy", "shock_type"),
    note="KRW 행은 shock_bp=NULL이다. 두 조사가 구 d368 short를 450 vs 400으로 "
         "달리 보고했고 1차자료를 읽지 못했다 — 값을 지어내는 대신 비워 둔다.",
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
          citation="S_short(t)=e^{−t/x}, S_long(t)=1−e^{−t/x} — BCBS d368 x=4"),
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
        C("floor_on_bp", "int", "만기 0 하한", nullable=False, unit="bp"),
        C("slope_bp_per_year", "int", "연간 상승폭", nullable=False, unit="bp"),
        C("terminal_tenor_years", "float", "하한 소멸 만기", nullable=False,
          unit="years", min_value=0.0),
        C("citation", "text", "근거", nullable=True),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("framework_version",),
    note="floor(t) = min(0, floor_on + slope·t), t ≥ terminal → 0. "
         "현행 코드에는 하한이 자체가 없다 — 평면 3% 가정이 하한을 가렸을 뿐, "
         "실제 커브를 연결하면 단기구간이 음수로 내려간다.",
)

CURVE_TABLES: tuple[TableSpec, ...] = (
    RATE_SHOCK_PARAM, SCENARIO_DEF, POST_SHOCK_FLOOR)


# ---------------------------------------------------------------- 빌더

# 통화별 충격 모수 적재표. 규제표·승인값이 소스에 적히는 곳은 이 한 군데다.
# (framework, ccy, {shock_type: bp}, proxy_for_ccy, effective_from,
#  evidence_status, source_ref)
_SHOCK_ROWS: tuple[tuple, ...] = (
    (
        "d368_2016", "USD", {"parallel": 200, "short": 300, "long": 150},
        "KRW", None, "원문미확인·현행계승",
        "현행 references.py 상수를 그대로 계승한다. BCBS d368 원문(bis.org) "
        "접속차단으로 1차자료 미확인. 이 행은 KRW 산출의 프록시로 쓰이며, "
        "200/300/150은 알려진 어느 KRW 계정보다 모든 축에서 작으므로 "
        "보수적 기본값이 아니라 과소산출이다.",
    ),
    (
        "d368_2016", "KRW", {"parallel": None, "short": None, "long": None},
        None, None, "미확인",
        "조사 A 450 vs 조사 B 400 불일치 — bis.org 접속차단으로 1차자료 미확인. "
        "금감원 「은행업감독업무시행세칙」 [별표 9의1] 원문(law.go.kr)도 미열람. "
        "국내 시행일 미확인이므로 effective_from도 비운다.",
    ),
    (
        "d578_2024", "KRW", {"parallel": None, "short": None, "long": None},
        None, "2026-01-01", "미확인",
        "BCBS d578(2024 재조정) 시행일 2026-01-01은 2차자료. 충격폭은 "
        "조사 A 250/350?/225?(자체모순 인정) vs 조사 B 250/300/200으로 "
        "불일치. 금감원이 [별표 9의1]을 d578에 맞춰 개정했는지도 미확인이므로 "
        "모수 상·하한도 비워 둔다.",
    ),
)

# 모수 상·하한 (BCBS d368 Annex 2). 두 조사 모두 검색확인 — 원문 대조는 못 했다.
_BOUNDS_D368: dict[str, tuple[int, int]] = {      # shock_type: (floor, cap)
    "parallel": (100, 400),
    "short":    (100, 500),
    "long":     (100, 300),
}


def build_rate_shock_param() -> pd.DataFrame:
    """통화별 충격 모수 원장.

    KRW 행이 비어 있는 것이 이 표의 산출물이다. 채워 넣으려면 BCBS d578 원문과
    시행세칙 [별표 9의1] 대조가 필요하고, 그전까지 IRRBB **절대수준**은 결재
    대상이 아니다(설계 §0). 상·하한은 d368 계정에만 적재한다 — d578에서
    상·하한이 유지되는지 확인하지 못했다.
    """
    rows = []
    for fw, ccy, bps, proxy, eff_from, status, ref in _SHOCK_ROWS:
        for st in SHOCK_TYPES:
            floor_bp, cap_bp = (_BOUNDS_D368[st] if fw == "d368_2016"
                                else (None, None))
            rows.append({
                "framework_version": fw, "ccy": ccy, "shock_type": st,
                "effective_from": eff_from, "effective_to": None,
                "shock_bp": bps[st], "floor_bp": floor_bp, "cap_bp": cap_bp,
                "proxy_for_ccy": proxy, "source_ref": ref,
                "evidence_status": status,
            })
    return pd.DataFrame(rows).astype(
        {"shock_bp": "Int64", "floor_bp": "Int64", "cap_bp": "Int64"})


# 시나리오 구성 계수. 현행 irrbb.py:45-47이 함수 본문에 박고 있는 바로 그
# 숫자를 여기로 옮긴다 — 값이 바뀌는 것이 아니라 위치가 바뀐다.
# (scenario, parallel, short, long, applies_to_nii)
_SCENARIOS: tuple[tuple[str, float, float, float, bool], ...] = (
    ("parallel_up",   +1.0,  0.00,  0.00, True),
    ("parallel_down", -1.0,  0.00,  0.00, True),
    ("short_up",       0.0, +1.00,  0.00, False),
    ("short_down",     0.0, -1.00,  0.00, False),
    ("steepener",      0.0, -0.65, +0.90, False),
    ("flattener",      0.0, +0.80, -0.60, False),
)

_DECAY_X = 4.0          # S_short(t) = e^{−t/4} — BCBS d368 Annex 2


def build_scenario_def() -> pd.DataFrame:
    """시나리오 구성식 원장 (6개).

    `applies_to_nii`가 규칙을 데이터로 만든다 — ΔNII는 6개가 아니라 평행충격
    2개만이며, 현행은 이 규칙이 `irrbb.py:105`의 튜플 리터럴로만 존재한다.
    """
    return pd.DataFrame([{
        "scenario": sc, "parallel_coef": p, "short_coef": s, "long_coef": l,
        "decay_x": _DECAY_X,
        # 6개 전부 ΔEVE 대상 (BCBS d368 §132 표준체계 시나리오 집합).
        "applies_to_eve": True, "applies_to_nii": nii,
        "citation": "BCBS d368 Annex 2 §132",
        # 계수 자체는 현행 코드에서 계승했고 원문 대조는 하지 못했다.
        "evidence_status": "원문미확인·현행계승",
    } for sc, p, s, l, nii in _SCENARIOS])


def build_post_shock_floor() -> pd.DataFrame:
    """충격후 금리하한 원장. d368 계정만 적재한다.

    d578에서 하한 규정이 유지·변경됐는지 확인하지 못했으므로 `d578_2024` 행은
    만들지 않는다. 엔진은 해당 계정의 하한 행을 못 찾으면 하한을 적용하지 않고
    경고를 남긴다 — 하한 미적용 사실이 결과에 실려 나간다.
    """
    return pd.DataFrame([{
        "framework_version": "d368_2016",
        "floor_on_bp": -100, "slope_bp_per_year": 5,
        "terminal_tenor_years": 20.0,
        "citation": "BCBS d368 §132 / SRP31 — 즉시만기 −100bp, 연 +5bp, "
                    "20년 이상 0",
        "evidence_status": "원문미확인·현행계승",
    }])


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
    shock_bp: dict[str, int]      # clip 후 실제 사용 모수
    shock_source: str             # '직접' · '프록시(USD)'

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
    return int(min(max(int(value), int(floor_bp)), int(cap_bp)))


def _resolve_shock_bp(shock_param: pd.DataFrame, *, ccy: str,
                      framework_version: str, needed: tuple[str, ...],
                      scenario: str, allow_proxy: bool,
                      ) -> tuple[dict[str, int] | None, str, list[ParamWarning]]:
    """충격 모수 해석 — 비어 있으면 채우지 않고 건너뛴다.

    해석 순서는 두 단계뿐이다. (1) 해당 통화 행에 값이 있으면 그것을 쓴다.
    (2) 없고 `allow_proxy=True`이면 `proxy_for_ccy`가 이 통화를 가리키는
    다른 통화 행을 빌려 쓰고, 빌렸다는 사실을 경고로 남긴다. 두 경우 모두
    `clip(floor_bp, cap_bp)`를 적용하며, 상·하한이 비어 있으면 clip을 검증할
    수 없으므로 역시 건너뛴다.
    """
    warns: list[ParamWarning] = []
    fw = shock_param[shock_param["framework_version"] == framework_version]

    def _take(rows: pd.DataFrame, source: str) -> dict[str, int] | None:
        by_type = rows.set_index("shock_type")
        out: dict[str, int] = {}
        for st in needed:
            if st not in by_type.index:
                warns.append(ParamWarning(
                    "RATE_SHOCK", f"{framework_version}/{ccy}/{scenario}", st,
                    f"충격유형 행이 원장에 없다 ({source}) — 시나리오 미산출"))
                return None
            r = by_type.loc[st]
            if pd.isna(r["shock_bp"]):
                warns.append(ParamWarning(
                    "RATE_SHOCK", f"{framework_version}/{ccy}/{scenario}", st,
                    f"shock_bp가 비어 있다 ({r['evidence_status']}) — "
                    f"{r['source_ref']}"))
                return None
            if pd.isna(r["floor_bp"]) or pd.isna(r["cap_bp"]):
                warns.append(ParamWarning(
                    "RATE_SHOCK", f"{framework_version}/{ccy}/{scenario}", st,
                    "모수 상·하한이 비어 있어 clip을 검증할 수 없다 — 시나리오 미산출"))
                return None
            out[st] = _clip_bp(r["shock_bp"], r["floor_bp"], r["cap_bp"])
        return out

    direct = fw[fw["ccy"] == ccy]
    if not direct.empty and not direct["shock_bp"].isna().all():
        got = _take(direct, "직접")
        return (got, "직접", warns) if got is not None else (None, "미확인", warns)

    warns.append(ParamWarning(
        "RATE_SHOCK", f"{framework_version}/{ccy}/{scenario}", "shock_bp",
        ("해당 통화 모수가 전량 비어 있다 — " if not direct.empty
         else "해당 통화 행이 원장에 없다 — ")
        + ("프록시 행을 찾는다" if allow_proxy
           else "allow_proxy=False이므로 시나리오 미산출")))
    if not allow_proxy:
        return None, "미확인", warns

    proxy = fw[fw["proxy_for_ccy"] == ccy]
    if proxy.empty:
        warns.append(ParamWarning(
            "RATE_SHOCK", f"{framework_version}/{ccy}/{scenario}",
            "proxy_for_ccy", "프록시 행도 없다 — 시나리오 미산출"))
        return None, "미확인", warns
    src_ccy = sorted({str(x) for x in proxy["ccy"]})
    if len(src_ccy) > 1:
        warns.append(ParamWarning(
            "RATE_SHOCK", f"{framework_version}/{ccy}/{scenario}",
            "proxy_for_ccy",
            f"프록시 후보가 여럿이다 {src_ccy} — 어느 계정을 빌렸는지 남지 "
            "않으므로 미산출"))
        return None, "미확인", warns
    got = _take(proxy, f"프록시({src_ccy[0]})")
    if got is None:
        return None, "미확인", warns
    warns.append(ParamWarning(
        "RATE_SHOCK", f"{framework_version}/{ccy}/{scenario}", "proxy_for_ccy",
        f"{src_ccy[0]} 계정 모수를 {ccy} 산출에 프록시로 사용했다 — "
        "통화 고유 모수가 확정되기 전까지 절대수준은 결재 대상이 아니다"))
    return got, f"프록시({src_ccy[0]})", warns


def _floor_rates(floor: pd.DataFrame, *, framework_version: str,
                 tenors: np.ndarray, scenario: str,
                 ) -> tuple[np.ndarray, bool, list[ParamWarning]]:
    """floor(t) = min(0, floor_on + slope·t), t ≥ terminal → 0."""
    warns: list[ParamWarning] = []
    d = floor[floor["framework_version"] == framework_version]
    if d.empty:
        warns.append(ParamWarning(
            "POST_SHOCK_FLOOR", f"{framework_version}/{scenario}",
            "floor_on_bp",
            "해당 계정의 충격후 하한 행이 원장에 없다 — 하한 미적용. "
            "하한 없이 산출된 커브는 단기구간에서 음수로 내려갈 수 있다"))
        # 0으로 대신 막지 않는다. 0 하한은 −100bp 하한보다 강한 **다른 규제**이며,
        # 원장이 비었을 때 그것을 조용히 적용하면 없는 규정을 만들어 쓰는 것이 된다.
        return np.full_like(tenors, np.nan), False, warns
    r = d.iloc[0]
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

    순서가 규정이다. (1) 원장 모수를 `clip(floor_bp, cap_bp)` 한 뒤
    (2) `Δr(t) = parallel_coef·R_p + short_coef·R_s·e^{−t/x}
    + long_coef·R_l·(1 − e^{−t/x})`를 기저 노드 금리에 더하고
    (3) 충격후 하한 `max(·, floor(t))`를 적용한다. clip을 하한 뒤에 하면
    모수 상한이 무의미해지고, 하한을 clip 전에 걸면 모수가 아니라 결과 금리를
    자르게 된다.

    충격은 **기저 커브의 노드에서** 적용하고 노드 사이는 기저와 같은 보간
    규약(log(DF) 선형)을 따른다. 노드마다 다른 보간을 쓰면 같은 만기의
    base/shocked 할인계수가 다른 규약에서 나와 ΔEVE에 보간 오차가 섞인다.

    `allow_proxy=True`는 현행 산출 재현용이다 — USD 계정을 KRW에 빌려 쓰는
    경로이며, 쓸 때마다 경고가 결과에 실린다. 기본값은 False다(조용한 프록시
    사용 금지).
    """
    d = scenario_def[scenario_def["scenario"] == scenario]
    if d.empty:
        raise ValueError(f"alm_scenario_def에 없는 시나리오: {scenario}")
    row = d.iloc[0]

    needed = _needed_shock_types(row)
    bps, source, warns = _resolve_shock_bp(
        shock_param, ccy=ccy, framework_version=framework_version,
        needed=needed, scenario=scenario, allow_proxy=allow_proxy)
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
