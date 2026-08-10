"""내부등급법 관측이력 원장 (IRB-H001) — 합성, 결정론.

추정하려면 규정이 요구하는 기간만큼 과거 관측이 있어야 한다. 저장소의
``risk_lib/data_gen.py``는 단일 시점 스냅샷과 ``default_12m`` 한 컬럼만 만들고
다년 부도이력이 없다. 관측이력이 없으면 182.·183.의 장기평균, 185.의 경기침체
LGD, 193.의 CCF 실측을 아예 계산할 수 없다.

원장 세 장

  ``crm_default_history``            기준일 × 관측연도 × 차주 1행
  ``crm_recovery_history``           부도건 × 회수시점 1행
  ``crm_facility_drawdown_history``  한도거래 1건당 1행

**전건 합성이다.** ``source_system='synthetic'``이며 실계 연결 시 이 세 장을
원천 데이터로 갈아끼운다. 스펙과 추정 엔진은 그대로 쓴다.

**생성 모수는 추정 엔진에 넘기지 않는다.** 이 모듈의 ``_TRUE_*`` 상수는
합성 데이터를 만드는 데만 쓰이고 ``pd_est``·``lgd_est``·``ccf_est``는 이
모듈에서 아무 상수도 읽지 않는다. 추정기가 생성 모수를 허용오차 안에서
되찾는지가 ``tests/test_irb_estimation.py``의 시험이다.

**결정론.** 원장마다 전용 난수 스트림 ``default_rng(seed + offset)``을 쓴다.
전역 ``np.random``과 파이썬 내장 ``hash()``, 벽시계 시각은 쓰지 않는다.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from risk_lib.datamodel.spec import ColumnSpec as C, ForeignKey as FK, TableSpec

__all__ = [
    "CYCLE_PHASES", "RECOVERY_TYPES", "CCF_OBSERVATION_DESIGNS",
    "POST_DEFAULT_TREATMENTS", "HISTORY_SEGMENTS",
    "DEFAULT_HISTORY", "RECOVERY_HISTORY", "FACILITY_DRAWDOWN_HISTORY",
    "HISTORY_TABLES",
    "build_crm_default_history", "build_crm_recovery_history",
    "build_crm_facility_drawdown_history", "build_history_ledgers",
]

# ---------------------------------------------------------------- 어휘

CYCLE_PHASES: tuple[str, ...] = ("정상", "침체")
RECOVERY_TYPES: tuple[str, ...] = ("담보처분", "보증이행", "자체회수")
# 관측설계는 데이터의 성질이지 산출 시점의 선택이 아니다. 어느 설계로 뽑은
# 표본인지가 원장에 없으면 코호트 표본에 고정시계 산식을 얹어도 드러나지 않는다.
CCF_OBSERVATION_DESIGNS: tuple[str, ...] = ("코호트", "고정시계")
# 193.나(1)은 부도 후 추가인출을 EAD와 LGD 중 어디에 반영했는지를 요구한다.
# 둘 다 반영하면 이중계상, 둘 다 빠지면 과소계상이다.
POST_DEFAULT_TREATMENTS: tuple[str, ...] = ("EAD반영", "LGD반영")
HISTORY_SEGMENTS: tuple[str, ...] = (
    "corporate", "retail_other", "residential_mortgage")

# ---------------------------------------------------------------- 생성 모수
# 아래는 규제표가 아니라 합성 데이터 생성 모수다. 추정 엔진은 이 값을 읽지
# 않으며, 추정기가 이 값을 되찾는지가 시험이다.

_SEED_OFF_DEFAULT = 90_101
_SEED_OFF_RECOVERY = 90_202
_SEED_OFF_FACILITY = 90_303

# (세그먼트, 등급/자산군) → 사이클 평균 부도율, 코호트 인원
_TRUE_PD: dict[tuple[str, str], tuple[float, int]] = {
    ("corporate", "BBB"): (0.014, 1000),
    ("corporate", "BB"): (0.067, 1000),
    ("corporate", "BB-"): (0.112, 900),
    ("corporate", "B+"): (0.180, 800),
    ("retail_other", "POOL_R1"): (0.035, 1200),
    ("retail_other", "POOL_R2"): (0.060, 1200),
    ("residential_mortgage", "POOL_M1"): (0.008, 1000),
    ("residential_mortgage", "POOL_M2"): (0.015, 1000),
}
# 경기 국면 배수. 합이 정확히 연수와 같아 평균이 1.0이다. 그래야 연도동일가중
# 단순평균이 기저 부도율을 되찾는다. 침체기가 표본에 없으면 185.의 경기침체
# LGD를 추정할 수 없으므로 두 해를 침체로 넣는다.
_CYCLE_MULT: tuple[float, ...] = (0.7, 0.8, 1.0, 1.7, 1.4, 0.9, 0.8, 0.7)
_DOWNTURN_MULT_MIN = 1.2   # 이 배수 이상인 해를 침체로 표시한다

_TRUE_LGD: dict[str, float] = {
    "corporate": 0.42, "retail_other": 0.55, "residential_mortgage": 0.22}
_LGD_DOWNTURN_UPLIFT = 0.12      # 침체 연도 부도건의 LGD 가산 (절대)
_LGD_OPEN_UPLIFT = 0.25          # 회수 미종료 건은 회수가 어려운 건이다
_LGD_NOISE_SD = 0.10
_OPEN_WORKOUT_SHARE = 0.18       # 회수 미종료 비중
_DIRECT_COST_RATE = 0.010        # 부도시 익스포저 대비 직접비
_INDIRECT_COST_RATE = 0.005      # 간접비
# 회수 현금흐름을 만들 때 쓰는 할인율. 이것은 은행의 내부기준 할인율이 아니라
# 합성 데이터를 특정 실현 LGD에 맞추기 위한 생성 모수다. 추정 엔진은 원장의
# 할인율을 쓰며 그 값이 이 값과 다르면 추정 LGD도 달라지는 것이 정상이다.
_GEN_DISCOUNT_RATE = 0.11

_TRUE_CCF: dict[str, float] = {
    "commitment_gt_1y": 0.45, "commitment_le_1y": 0.45,
    "transaction_related": 0.55, "short_term_trade": 0.35,
    "unconditionally_cancellable": 0.25}
_CCF_DOWNTURN_UPLIFT = 0.10
_CCF_NOISE_SD = 0.08
_FACILITY_SHARE = 0.45           # 부도건 중 한도거래 보유 비중
_ZERO_UNDRAWN_SHARE = 0.08       # 기준시 한도 소진 (분모 0)
_NEG_UNDRAWN_SHARE = 0.05        # 기준시 이후 한도 축소 (분모 음수)


# ---------------------------------------------------------------- 스펙

DEFAULT_HISTORY = TableSpec(
    name="crm_default_history", korean="부도 관측이력", product="PRD-RWA",
    grain="기준일 × 관측연도 × 차주 1건당 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("cohort_year", "int", "관측연도", nullable=False,
          min_value=1900, max_value=2200,
          note="연초 코호트를 구성한 해. 이 해 안의 부도를 1년 부도로 센다"),
        C("obligor_id", "string", "차주 식별자", nullable=False),
        C("segment", "string", "세그먼트", nullable=False,
          allowed=HISTORY_SEGMENTS),
        C("exposure_class", "string", "자산군", nullable=False),
        C("grade", "string", "등급 또는 자산군(pool)", nullable=False,
          note="기업은 차주등급, 소매는 자산군 식별자. 추정 단위가 다르다"),
        C("rating_assigned_date", "date", "등급부여일", nullable=False,
          note="코호트 구성일보다 뒤면 생존편의다. 정합성 검사가 잡는다"),
        C("cohort_start_date", "date", "코호트 구성일", nullable=False),
        C("default_flag", "int", "부도 여부", nullable=False,
          min_value=0, max_value=1,
          citation="[별표 3] 174. 부도정의"),
        C("default_date", "date", "부도일", nullable=True,
          note="default_flag=1이면 반드시 있어야 한다"),
        C("exposure_amount", "float", "코호트 시점 익스포저", nullable=False,
          unit="KRW", min_value=0.0),
        C("cycle_phase", "string", "경기 국면", nullable=False,
          allowed=CYCLE_PHASES,
          note="185.의 경기침체 LGD와 193.다(4)의 경기침체 EAD가 이 표시를 "
               "쓴다. 침체 정의는 내부기준이며 이 컬럼은 합성 생성값이다"),
        C("default_definition", "text", "부도정의", nullable=False),
        C("source_system", "string", "원천", nullable=False,
          allowed=("core_banking", "synthetic")),
    ),
    primary_key=("asof", "cohort_year", "obligor_id"),
    note="182.·183.의 장기평균 PD는 이 원장의 연도별 코호트에서만 나온다. "
         "단일 시점 스냅샷으로는 연도동일가중 단순평균 자체가 정의되지 않는다.",
)

RECOVERY_HISTORY = TableSpec(
    name="crm_recovery_history", korean="회수 관측이력", product="PRD-RWA",
    grain="부도건 × 회수시점 1건당 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("default_id", "string", "부도건 식별자", nullable=False),
        C("obligor_id", "string", "차주 식별자", nullable=False),
        C("segment", "string", "세그먼트", nullable=False,
          allowed=HISTORY_SEGMENTS),
        C("default_date", "date", "부도일", nullable=False),
        C("default_year", "int", "부도연도", nullable=False,
          min_value=1900, max_value=2200),
        C("cycle_phase", "string", "부도연도 경기 국면", nullable=False,
          allowed=CYCLE_PHASES),
        C("ead_at_default", "float", "부도시 익스포저", nullable=False,
          unit="KRW", min_value=0.0,
          citation="[별표 3] 184. 경제적 손실의 분모"),
        C("recovery_seq", "int", "회수 순번", nullable=False, min_value=1),
        C("recovery_date", "date", "회수일", nullable=False),
        C("recovery_years", "float", "부도일로부터 경과연수", nullable=False,
          unit="years", min_value=0.0,
          note="할인 지수. (회수일 - 부도일)/365"),
        C("recovery_amount", "float", "회수액", nullable=False, unit="KRW",
          note="추가인출·역거래는 음(-)의 회수로 같은 컬럼에 넣는다. 별도 "
               "컬럼으로 빼면 부호 실수가 난다"),
        C("recovery_type", "string", "회수유형", nullable=False,
          allowed=RECOVERY_TYPES),
        C("direct_cost", "float", "직접비", nullable=False, unit="KRW",
          min_value=0.0, citation="[별표 3] 184.(1) 직·간접 비용"),
        C("indirect_cost", "float", "간접비", nullable=False, unit="KRW",
          min_value=0.0, citation="[별표 3] 184.(1) 직·간접 비용"),
        C("collateral_appraisal_value", "float", "담보평가액", nullable=True,
          unit="KRW", min_value=0.0,
          citation="[별표 3] 185.라 담보의 추정시가·회수율 시계열"),
        C("collateral_appraisal_date", "date", "담보평가일", nullable=True),
        C("workout_open", "bool", "회수 미종료", nullable=False,
          note="True면 관측중단(censoring). 이 건을 빼고 추정하면 회수율이 "
               "과대평가되고 LGD가 낙관적으로 나온다"),
        C("months_since_default", "int", "부도후 경과월", nullable=False,
          min_value=0),
        C("source_system", "string", "원천", nullable=False,
          allowed=("core_banking", "synthetic")),
    ),
    primary_key=("asof", "default_id", "recovery_seq"),
    foreign_keys=(FK(("asof", "obligor_id"),
                     "crm_default_history", ("asof", "obligor_id")),),
    note="184.의 경제적 손실은 이 원장의 현금흐름과 원장 할인율에서만 나온다.",
)

FACILITY_DRAWDOWN_HISTORY = TableSpec(
    name="crm_facility_drawdown_history", korean="한도거래 인출이력",
    product="PRD-RWA",
    grain="한도거래 1건당 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("facility_id", "string", "한도거래 식별자", nullable=False),
        C("obligor_id", "string", "차주 식별자", nullable=False),
        C("segment", "string", "세그먼트", nullable=False,
          allowed=HISTORY_SEGMENTS),
        C("exposure_class", "string", "자산군", nullable=False),
        C("grade", "string", "등급 또는 자산군(pool)", nullable=False),
        C("ccf_type", "string", "신용환산 구분", nullable=False),
        C("observation_design", "string", "관측설계", nullable=False,
          allowed=CCF_OBSERVATION_DESIGNS),
        C("reference_date", "date", "기준시점", nullable=False),
        C("drawn_at_reference", "float", "기준시 인출액", nullable=False,
          unit="KRW", min_value=0.0),
        C("undrawn_at_reference", "float", "기준시 미인출액", nullable=False,
          unit="KRW",
          note="음수를 허용한다. 한도 축소로 인출액이 한도를 넘은 상태를 "
               "0으로 뭉개면 CCF 분모가 조용히 바뀐다"),
        C("limit_at_reference", "float", "기준시 한도", nullable=False,
          unit="KRW", min_value=0.0),
        C("default_date", "date", "부도일", nullable=False),
        C("default_year", "int", "부도연도", nullable=False,
          min_value=1900, max_value=2200),
        C("cycle_phase", "string", "부도연도 경기 국면", nullable=False,
          allowed=CYCLE_PHASES),
        C("drawn_at_default", "float", "부도시 인출액", nullable=False,
          unit="KRW", min_value=0.0),
        C("limit_at_default", "float", "부도시 한도", nullable=False,
          unit="KRW", min_value=0.0),
        C("cancellable", "bool", "취소가능 약정", nullable=False),
        C("post_default_drawdown_treatment", "string", "부도후 추가인출 반영처",
          nullable=False, allowed=POST_DEFAULT_TREATMENTS,
          citation="[별표 3] 193.나(1)"),
        C("source_system", "string", "원천", nullable=False,
          allowed=("core_banking", "synthetic")),
    ),
    primary_key=("asof", "facility_id"),
    note="193.의 CCF 실측은 기준시점 스냅샷과 부도시점 잔액이 같은 행에 "
         "있어야 산출된다.",
)

HISTORY_TABLES: dict[str, TableSpec] = {
    DEFAULT_HISTORY.name: DEFAULT_HISTORY,
    RECOVERY_HISTORY.name: RECOVERY_HISTORY,
    FACILITY_DRAWDOWN_HISTORY.name: FACILITY_DRAWDOWN_HISTORY,
}

_DEFAULT_DEFINITION = (
    "[별표 3] 174. 원리금 90일 이상 연체 또는 채무상환능력 악화로 전액 상환이 "
    "어렵다고 판단되는 경우. 합성 이력이므로 174.의 정성요건은 반영하지 않았다")


# ---------------------------------------------------------------- 보조

def _iso(d: date) -> str:
    return d.isoformat()


def _cast(df: pd.DataFrame, spec: TableSpec) -> pd.DataFrame:
    """스펙의 int·float dtype을 맞춘다. 빈 프레임도 스펙을 통과해야 한다."""
    for col in spec.columns:
        if col.name not in df.columns:
            continue
        if col.dtype == "float":
            df[col.name] = pd.to_numeric(df[col.name],
                                         errors="coerce").astype("float64")
        elif col.dtype == "int":
            df[col.name] = pd.to_numeric(df[col.name],
                                         errors="coerce").astype("int64")
        elif col.dtype == "bool":
            df[col.name] = df[col.name].astype(bool)
    return df.reset_index(drop=True)


def _observation_years(asof: str, years: int) -> list[int]:
    """관측연도 목록. 기준일 연도의 직전 연도까지를 완결 관측연도로 본다."""
    last = int(asof[:4]) - 1
    return list(range(last - years + 1, last + 1))


# ---------------------------------------------------------------- 부도이력

def build_crm_default_history(*, asof: str, seed: int = 42,
                              years: int = 8) -> pd.DataFrame:
    """연도별 코호트 부도 관측이력을 만든다.

    ``years``는 관측연도 수다. 기본 8년은 기업 LGD·EAD의 최소 관측기간 7년
    (186.·195.)을 넘긴다. 최소요건 경계 시험은 ``years``를 6·7로 낮춰 돌린다.

    경기 국면 배수의 평균이 1.0이므로, 연도동일가중 단순평균(182.바)은 기저
    부도율을 되찾는다. 차주수 가중 풀링평균은 코호트 크기가 연도마다 같으면
    같은 값이 나오지만, 침체기에 코호트가 줄면 갈라진다. 그 차이를 보이기 위해
    침체 연도의 코호트를 축소한다.
    """
    if years < 1:
        raise ValueError("years는 1 이상이어야 한다")
    rng = np.random.default_rng(seed + _SEED_OFF_DEFAULT)
    obs_years = _observation_years(asof, years)
    frames: list[pd.DataFrame] = []

    for yi, year in enumerate(obs_years):
        mult = _CYCLE_MULT[yi % len(_CYCLE_MULT)]
        phase = "침체" if mult >= _DOWNTURN_MULT_MIN else "정상"
        # 침체기에는 신규 취급이 줄어 코호트가 작아진다. S2가 지적한 대로
        # 차주수 가중평균이 침체 효과를 희석시키는 조건이 이때 생긴다.
        size_scale = 0.75 if phase == "침체" else 1.0
        for (segment, grade), (base_pd, n_base) in _TRUE_PD.items():
            n = int(round(n_base * size_scale))
            p = float(min(base_pd * mult, 0.999))
            hit = rng.random(n) < p
            day_of_year = rng.integers(1, 366, n)
            start = date(year, 1, 1)
            default_dates = [
                _iso(start + timedelta(days=int(d) - 1)) if h else None
                for d, h in zip(day_of_year, hit)]
            # 등급은 코호트 구성일 이전에 부여돼야 한다. 부여일이 구성일보다
            # 뒤면 그 해의 부도 정보를 등급이 이미 알고 있는 셈이 된다.
            assigned = _iso(date(year - 1, 12, 1))
            amount = rng.lognormal(mean=np.log(3.0e8), sigma=0.6, size=n)
            frames.append(pd.DataFrame({
                "asof": asof,
                "cohort_year": year,
                "obligor_id": [f"OBL_{segment[:4].upper()}_{grade}_{year}_{i:05d}"
                               for i in range(n)],
                "segment": segment,
                "exposure_class": segment,
                "grade": grade,
                "rating_assigned_date": assigned,
                "cohort_start_date": _iso(start),
                "default_flag": hit.astype(int),
                "default_date": default_dates,
                "exposure_amount": amount,
                "cycle_phase": phase,
                "default_definition": _DEFAULT_DEFINITION,
                "source_system": "synthetic",
            }))
    out = pd.concat(frames, ignore_index=True)
    return _cast(out, DEFAULT_HISTORY)


# ---------------------------------------------------------------- 회수이력

def build_crm_recovery_history(default_history: pd.DataFrame, *, asof: str,
                               seed: int = 42) -> pd.DataFrame:
    """부도건별 회수 현금흐름을 만든다.

    회수 시점과 금액은 목표 실현 LGD에서 역산한다. 생성 할인율
    ``_GEN_DISCOUNT_RATE``로 할인했을 때 목표 LGD가 나오도록 총 회수액을 맞추고,
    추정 엔진은 원장의 승인된 할인율로 다시 할인한다. 두 값이 다르면 추정 LGD도
    달라지는 것이 정상이며, 그 민감도가 할인율 승인이 필요한 이유다.

    회수 미종료(open workout) 건은 부도일이 기준일에 가까운 건 중에서 고르고,
    기준일 이후 회수는 원장에 넣지 않는다. 이 건을 빼고 추정하면 회수가 잘 된
    건만 남아 LGD가 낙관적으로 나온다.
    """
    rng = np.random.default_rng(seed + _SEED_OFF_RECOVERY)
    d = default_history[default_history["default_flag"] == 1]
    if d.empty:
        return _cast(pd.DataFrame(columns=[c.name for c in
                                           RECOVERY_HISTORY.columns]),
                     RECOVERY_HISTORY)
    asof_d = date.fromisoformat(asof)
    rows: list[dict] = []

    n = len(d)
    open_draw = rng.random(n) < _OPEN_WORKOUT_SHARE
    noise = rng.normal(0.0, _LGD_NOISE_SD, n)
    n_flows = rng.integers(1, 4, n)
    type_draw = rng.integers(0, 3, n)
    lag_u = rng.random((n, 3))

    for i, (_, row) in enumerate(d.iterrows()):
        seg = row["segment"]
        ead = float(row["exposure_amount"])
        ddate = date.fromisoformat(row["default_date"])
        months_elapsed = max(
            0, (asof_d.year - ddate.year) * 12 + asof_d.month - ddate.month)
        target = _TRUE_LGD[seg] + noise[i]
        if row["cycle_phase"] == "침체":
            target += _LGD_DOWNTURN_UPLIFT
        # 회수 미종료는 부도후 경과가 짧은 건에서만 성립한다. 경과 24개월이
        # 넘었는데 미종료로 두면 그 건의 잠정 LGD가 과도하게 높아진다.
        is_open = bool(open_draw[i]) and months_elapsed <= 24
        if is_open:
            target += _LGD_OPEN_UPLIFT
        target = float(np.clip(target, 0.01, 0.99))

        k = int(n_flows[i])
        lags = np.sort(0.25 + lag_u[i, :k] * 2.25)          # 0.25~2.5년
        weights = np.full(k, 1.0 / k)
        df_factors = (1.0 + _GEN_DISCOUNT_RATE) ** (-lags)
        direct = ead * _DIRECT_COST_RATE / k
        indirect = ead * _INDIRECT_COST_RATE / k
        pv_cost = float(np.sum((direct + indirect) * df_factors))
        denom = float(np.sum(weights * df_factors))
        total_recovery = ((1.0 - target) * ead + pv_cost) / denom

        n_written = 0
        for j in range(k):
            rdate = ddate + timedelta(days=int(round(float(lags[j]) * 365)))
            if is_open and rdate > asof_d:
                # 기준일 이후의 회수는 아직 관측되지 않았다. 넣으면 미래를
                # 앞당겨 쓰는 것이고 관측중단 자체가 사라진다.
                continue
            rows.append({
                "asof": asof,
                "default_id": f"DEF_{row['obligor_id']}",
                "obligor_id": row["obligor_id"],
                "segment": seg,
                "default_date": row["default_date"],
                "default_year": int(row["cohort_year"]),
                "cycle_phase": row["cycle_phase"],
                "ead_at_default": ead,
                "recovery_seq": j + 1,
                "recovery_date": _iso(rdate),
                "recovery_years": float(lags[j]),
                "recovery_amount": float(total_recovery * weights[j]),
                "recovery_type": RECOVERY_TYPES[int(type_draw[i])],
                "direct_cost": float(direct),
                "indirect_cost": float(indirect),
                "collateral_appraisal_value": (
                    float(ead * 0.7) if RECOVERY_TYPES[int(type_draw[i])]
                    == "담보처분" else None),
                "collateral_appraisal_date": (
                    _iso(ddate) if RECOVERY_TYPES[int(type_draw[i])]
                    == "담보처분" else None),
                "workout_open": is_open,
                "months_since_default": int(months_elapsed),
                "source_system": "synthetic",
            })
            n_written += 1
        if is_open and n_written == 0:
            # 관측 회수가 한 건도 없는 미종료 건. 회수 0으로 한 행을 남긴다.
            # 행을 지우면 그 부도건이 표본에서 통째로 사라져 관측중단 건수가
            # 과소 집계된다.
            rows.append({
                "asof": asof, "default_id": f"DEF_{row['obligor_id']}",
                "obligor_id": row["obligor_id"], "segment": seg,
                "default_date": row["default_date"],
                "default_year": int(row["cohort_year"]),
                "cycle_phase": row["cycle_phase"], "ead_at_default": ead,
                "recovery_seq": 1, "recovery_date": asof,
                "recovery_years": months_elapsed / 12.0,
                "recovery_amount": 0.0,
                "recovery_type": RECOVERY_TYPES[int(type_draw[i])],
                "direct_cost": float(ead * _DIRECT_COST_RATE),
                "indirect_cost": float(ead * _INDIRECT_COST_RATE),
                "collateral_appraisal_value": None,
                "collateral_appraisal_date": None,
                "workout_open": True,
                "months_since_default": int(months_elapsed),
                "source_system": "synthetic"})
    return _cast(pd.DataFrame(rows), RECOVERY_HISTORY)


# ---------------------------------------------------------------- 한도이력

def build_crm_facility_drawdown_history(default_history: pd.DataFrame, *,
                                        asof: str, seed: int = 42
                                        ) -> pd.DataFrame:
    """부도 한도거래의 기준시점·부도시점 스냅샷을 만든다.

    관측설계는 고정시계다. 기준시점을 부도일 12개월 전으로 고정하고 그 시점의
    한도·인출액을 남긴다. 코호트 설계로 바꾸면 기준시점이 달력 고정일이 되고
    평균 시계가 6개월 수준으로 짧아져 추가인출을 덜 관측한다.

    분모가 0이거나 음수인 건을 일부러 만든다. 기준시 한도가 이미 소진된 건
    (미인출 0)과 부도 전에 한도가 축소되어 인출액이 한도를 넘은 건(미인출 음수)
    이다. 이 건들을 조용히 잘라내면 CCF가 낙관적으로 나온다.
    """
    rng = np.random.default_rng(seed + _SEED_OFF_FACILITY)
    d = default_history[(default_history["default_flag"] == 1)
                        & (default_history["segment"] != "residential_mortgage")]
    if d.empty:
        return _cast(pd.DataFrame(columns=[c.name for c in
                                           FACILITY_DRAWDOWN_HISTORY.columns]),
                     FACILITY_DRAWDOWN_HISTORY)
    ccf_types = list(_TRUE_CCF)
    n = len(d)
    has_fac = rng.random(n) < _FACILITY_SHARE
    type_idx = rng.integers(0, len(ccf_types), n)
    util = rng.uniform(0.30, 0.75, n)
    noise = rng.normal(0.0, _CCF_NOISE_SD, n)
    degen = rng.random(n)

    rows: list[dict] = []
    for i, (_, row) in enumerate(d.iterrows()):
        if not has_fac[i]:
            continue
        ctype = ccf_types[int(type_idx[i])]
        limit = float(row["exposure_amount"]) * 1.6
        drawn0 = limit * float(util[i])
        undrawn0 = limit - drawn0
        ddate = date.fromisoformat(row["default_date"])
        rdate = date(ddate.year - 1, ddate.month,
                     min(ddate.day, 28))
        true_ccf = _TRUE_CCF[ctype] + (
            _CCF_DOWNTURN_UPLIFT if row["cycle_phase"] == "침체" else 0.0)
        drawn_d = drawn0 + max(0.0, min(1.0, true_ccf + noise[i])) * undrawn0
        limit_d = limit

        u = float(degen[i])
        if u < _ZERO_UNDRAWN_SHARE:
            drawn0, undrawn0 = limit, 0.0
            drawn_d = limit
        elif u < _ZERO_UNDRAWN_SHARE + _NEG_UNDRAWN_SHARE:
            # 부도 전에 한도가 축소됐다. 기준시 한도를 인출액 아래로 내린다.
            limit = drawn0 * 0.9
            undrawn0 = limit - drawn0
            limit_d = limit
            drawn_d = drawn0
        rows.append({
            "asof": asof,
            "facility_id": f"FAC_{row['obligor_id']}",
            "obligor_id": row["obligor_id"],
            "segment": row["segment"],
            "exposure_class": row["exposure_class"],
            "grade": row["grade"],
            "ccf_type": ctype,
            "observation_design": "고정시계",
            "reference_date": _iso(rdate),
            "drawn_at_reference": float(drawn0),
            "undrawn_at_reference": float(undrawn0),
            "limit_at_reference": float(max(limit, 0.0)),
            "default_date": row["default_date"],
            "default_year": int(row["cohort_year"]),
            "cycle_phase": row["cycle_phase"],
            "drawn_at_default": float(drawn_d),
            "limit_at_default": float(max(limit_d, 0.0)),
            "cancellable": ctype == "unconditionally_cancellable",
            # 이 합성 이력의 부도시 인출액은 부도 시점 잔액이며 부도 이후의
            # 추가인출은 담기지 않는다. 부도 후 추가인출은 LGD 쪽에서 회수
            # 음수로 잡는 설계이므로 'LGD반영'으로 표시한다.
            "post_default_drawdown_treatment": "LGD반영",
            "source_system": "synthetic",
        })
    return _cast(pd.DataFrame(rows), FACILITY_DRAWDOWN_HISTORY)


def build_history_ledgers(*, asof: str, seed: int = 42,
                          years: int = 8) -> dict[str, pd.DataFrame]:
    """관측이력 원장 세 장을 한 번에 만든다."""
    dh = build_crm_default_history(asof=asof, seed=seed, years=years)
    return {
        "crm_default_history": dh,
        "crm_recovery_history": build_crm_recovery_history(
            dh, asof=asof, seed=seed),
        "crm_facility_drawdown_history": build_crm_facility_drawdown_history(
            dh, asof=asof, seed=seed),
    }
