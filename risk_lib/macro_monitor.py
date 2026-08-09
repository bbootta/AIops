"""거시·금융지표 모니터링. 지표 마스터·시나리오 충격 원장과 그 소비 엔진.

## 왜 원장으로 옮겼나

이 모듈은 지표 12종의 정의와 시나리오별 충격 배수를 **모듈 상수**로 들고 있었다.
상수는 화면에 나오지 않고, 화면에 없으면 검증도 결재도 그 값을 보지 못한다.
"어느 통계에서 왔나", "누가 승인했나", "규정 근거가 있나"에 답할 자리가 없었다.
사용자 지시 - 화면은 반드시 연결되는 원장이 있어야 하고 그 원장은 산출·수기
프로세스가 만들어야 한다 - 가 걸리는 자리가 정확히 여기다.

두 원장으로 나눈다.

  `rdm_macro_indicator_master`  지표 정의. **수기입력 마스터**이며 빌더가 곧
                                수기입력 프로세스다. 출처 기관·통계표 코드가
                                컬럼이므로 실 피드가 붙으면 이 원장만 갈아끼운다.
  `st_macro_scenario_shock`     시나리오 × 지표 충격 배수(표준편차 단위).
                                **규정 근거가 없는 내부가정**이다. 그렇게 적는다.

엔진 함수(`observations`·`scenario_links`·`alerts`)는 원장을 인자로 받는다.
함수 본문에 지표 식별자도 배수도 없다.

## 값은 아직 합성이다, 그렇게 말한다

외부 통계 API를 붙이지 않았다. 그러므로 관측치는 전건 `basis="파생"`이고
실측이라고 말하지 않는다. 마스터의 `level`·`vol`은 합성 계열의 기준점이며
1차자료로 확인한 값이 아니다. ECOS 통계표코드·KOSIS 표ID도 공표 카탈로그와
대조하지 않았다. 그래서 마스터 12행 전건이 `evidence_status='미확인'`이고
`입력자·승인자·승인일`이 비어 있다. 비어 있음이 화면·검증에 드러나는 것이
이 설계의 목적이다.

계열 생성에 필요한 칸(`level`·`vol`·`mean_reversion`·`noise_scale`) 중 하나라도
NULL이면 엔진이 조용히 기본값을 쓰지 않는다. 경고를 남기고 그 지표를 건너뛴다.

생성은 `(asof, seed)` 고정이다. 같은 기준일·시드면 같은 계열이 나온다.
"""

from __future__ import annotations

import hashlib
import warnings
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from risk_lib.datamodel.spec import ColumnSpec as C, TableSpec, ForeignKey as FK

__all__ = [
    "EVIDENCE_STATUS", "INPUT_SOURCES", "MACRO_SOURCES", "MACRO_CATEGORIES",
    "MACRO_FREQ", "SCENARIOS", "IndicatorSpec", "MacroWarning",
    "MacroLedgerWarning",
    "INDICATOR_MASTER", "SCENARIO_SHOCK_LEDGER", "MACRO_MASTER_TABLES",
    "build_macro_indicator_master", "build_macro_scenario_shock",
    "build_macro_master_ledgers", "indicator_specs", "scenario_shock_map",
    "unapproved_indicators", "unapproved_scenario_shocks",
    "observations", "latest_observations", "scenario_links", "alerts",
    "by_id_drives",
]


# ---------------------------------------------------------------- 어휘

# '재량·미규정'은 원문을 읽었고 그 원문이 값을 정하지 않는다는 것까지 확인한
# 상태다. '내부가정'은 규정이 값을 다루지 않아 은행이 스스로 정한 값이고,
# '미확인'은 근거 문서를 아직 못 본 상태다. 셋은 다른 사건이라 어휘를 나눈다.
EVIDENCE_STATUS: tuple[str, ...] = (
    "원문확인", "2차자료", "원문미확인·현행계승", "재량·미규정", "내부가정",
    "미확인")
INPUT_SOURCES: tuple[str, ...] = (
    "공표통계", "자체추정", "합성기준점", "미확정")

# 아래 세 어휘는 `datamodel.catalog`의 `macro_indicator` 관측치 스펙과 같아야
# 한다. 사본이 두 벌이 되면 마스터와 관측치의 허용값이 조용히 갈라진다.
# tests/test_macro_ledger.py가 두 곳의 일치를 확인한다.
MACRO_SOURCES: tuple[str, ...] = (
    "한국은행", "통계청", "금융감독원", "KOFIA", "BIS", "IMF")
MACRO_CATEGORIES: tuple[str, ...] = (
    "성장", "물가", "금리", "환율", "고용", "가계부채", "부동산", "금융시장",
    "대외")
MACRO_FREQ: tuple[str, ...] = ("월", "분기", "연")
SCENARIOS: tuple[str, ...] = ("baseline", "adverse", "severely_adverse")


@dataclass(frozen=True)
class IndicatorSpec:
    """마스터 1행을 엔진이 쓰는 형태로 옮긴 값 객체.

    원장 행에서 만들어지며 정의를 스스로 갖지 않는다. 소비처가 컬럼명을
    직접 다루지 않도록 두는 얇은 뷰다.
    """
    indicator_id: str
    name: str
    category: str
    source: str
    code: str
    unit: str
    freq: str
    level: float | None      # 합성 계열의 기준점. 미입력이면 None
    vol: float | None        # 주기 변동성. 미입력이면 None
    mean_reversion: float | None   # 평균회귀 속도. 미입력이면 None
    noise_scale: float | None      # 잡음 표준편차 = vol × 이 값. 미입력이면 None
    drives: str              # 이 지표가 스트레스 축 중 무엇을 움직이는가


@dataclass(frozen=True)
class MacroWarning:
    """원장 칸이 비어 엔진이 건너뛴 사건. 조용한 기본값 대신 남기는 기록."""
    indicator_id: str
    field: str
    reason: str


class MacroLedgerWarning(UserWarning):
    """원장 결측으로 산출을 건너뛸 때 발생. 경고를 끄면 결측이 안 보인다."""


# ---------------------------------------------------------------- 스펙

INDICATOR_MASTER = TableSpec(
    name="rdm_macro_indicator_master", korean="거시·금융지표 마스터",
    product="PRD-RDM",
    grain="지표 1개당 1행",
    columns=(
        C("indicator_id", "string", "지표 식별자", nullable=False),
        C("name", "string", "지표명", nullable=False),
        C("category", "string", "부문", nullable=False,
          allowed=MACRO_CATEGORIES),
        C("source", "string", "출처 기관", nullable=False,
          allowed=MACRO_SOURCES),
        C("source_code", "string", "출처 통계표·계열 코드", nullable=False,
          note="한국은행 ECOS 통계표코드 / 통계청 KOSIS 표ID. 실 피드 연결 "
               "지점이며 공표 카탈로그와 아직 대조하지 않았다"),
        C("unit", "string", "단위", nullable=False,
          note="지표마다 다르다(%, 원, 지수, bp). 관측치 원장의 unit이 이 값이다"),
        C("freq", "string", "주기", nullable=False, allowed=MACRO_FREQ),
        C("level", "float", "기준 수준", nullable=True, unit="가변",
          note="합성 계열의 평균회귀 목표. 단위는 같은 행의 unit을 본다. "
               "NULL이면 엔진이 그 지표의 계열 생성을 건너뛴다"),
        C("vol", "float", "주기 변동성", nullable=True, unit="가변",
          min_value=0.0,
          note="표준편차. 시나리오 충격 배수가 곱해지는 대상이다"),
        C("mean_reversion", "float", "평균회귀 속도", nullable=True,
          unit="ratio", min_value=0.0, max_value=1.0,
          note="합성 계열이 매 기 level 쪽으로 좁히는 비율. 엔진에 두면 계열의 "
               "모양을 정하는 값이 화면에 보이지 않는다"),
        C("noise_scale", "float", "잡음 배율", nullable=True, unit="배",
          min_value=0.0,
          note="매 기 잡음의 표준편차 = vol × 이 값"),
        C("drives", "text", "이 지표가 움직이는 축", nullable=False),
        C("input_source", "string", "입력출처", nullable=False,
          allowed=INPUT_SOURCES),
        C("entered_by", "string", "입력자", nullable=True),
        C("approved_by", "string", "승인자", nullable=True),
        C("approved_on", "date", "승인일", nullable=True),
        C("citation", "text", "근거", nullable=True),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("indicator_id",),
    note="지표 정의는 산출물이 아니라 수기입력 마스터다. 12행 전건이 "
         "승인자·승인일 미기재이며 evidence_status='미확인'이다. 통계표 코드를 "
         "공표 카탈로그와 대조하고 승인을 받아야 '공표통계'로 바뀐다.",
)

SCENARIO_SHOCK_LEDGER = TableSpec(
    name="st_macro_scenario_shock", korean="시나리오별 지표 충격 배수",
    product="PRD-ST",
    grain="시나리오 × 지표 1행",
    columns=(
        C("scenario", "string", "시나리오", nullable=False, allowed=SCENARIOS),
        C("indicator_id", "string", "지표 식별자", nullable=False),
        C("multiplier", "float", "충격 배수", nullable=True, unit="표준편차",
          note="지표의 vol에 곱한다. 수준·단위가 다른 지표를 같은 %로 때리면 "
               "환율과 실업률이 같은 충격을 받는 셈이 되므로 표준편차 단위다. "
               "NULL이면 엔진이 그 (시나리오, 지표) 조정을 건너뛴다"),
        C("direction_rule", "text", "방향성", nullable=False),
        C("citation", "text", "근거", nullable=True),
        C("approved_by", "string", "승인자", nullable=True),
        C("approved_on", "date", "승인일", nullable=True),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("scenario", "indicator_id"),
    foreign_keys=(FK(("indicator_id",), "rdm_macro_indicator_master",
                     ("indicator_id",)),),
    note="배수는 규정이 정하는 값이 아니다. 감독당국·BCBS 어느 문서도 지표별 "
         "표준편차 배수를 주지 않으므로 전건 evidence_status='내부가정'이며 "
         "승인 대상이다. 충격이 없는 조합도 배수 0.0으로 명시해 둔다. "
         "행이 없는 것과 충격이 0인 것은 다른 사건이다.",
)

MACRO_MASTER_TABLES: tuple[TableSpec, ...] = (
    INDICATOR_MASTER, SCENARIO_SHOCK_LEDGER)


# ---------------------------------------------------------------- 빌더

def build_macro_indicator_master() -> pd.DataFrame:
    """지표 마스터 원장. 이 함수가 곧 수기입력 프로세스다.

    통합위기상황분석이 쓰는 축을 덮는 최소 집합이다. 축마다 최소 1개 지표가
    있어야 시나리오 가정이 관측치에 걸린다.

    12행 전건이 미승인·미확인이다. 지어낸 값이 아니라 **아직 확인·승인되지
    않은 값**이며, 그 사실이 컬럼으로 드러난다. `input_source='합성기준점'`은
    level·vol이 공표통계에서 온 값이 아니라는 표시다.
    `mean_reversion`·`noise_scale`은 합성 계열의 모양을 정하는 값이다. 엔진
    함수 본문에 있던 것을 원장으로 옮겼다. 지표별로 다르게 잡을 수 있으나
    현재는 전건 같은 값이고 보정 근거가 없어 역시 미확인이다.
    """
    # 평균회귀 속도·잡음 배율은 전 지표 공통이다. 난수 걷기로 두면 마지막 값이
    # 수준에서 멀어져 "최근 관측치"라는 이름이 무의미해지므로 회귀를 건다.
    _REVERSION, _NOISE = 0.45, 0.5
    # (id, 지표명, 부문, 출처, 출처코드, 단위, 주기, level, vol, drives)
    rows = (
        ("GDP_YOY", "실질 GDP 성장률", "성장", "한국은행", "200Y001",
         "%", "분기", 2.0, 1.1, "PD 시스템요인 (z)"),
        ("CPI_YOY", "소비자물가 상승률", "물가", "통계청", "DT_1DA7001S",
         "%", "월", 2.3, 0.7, "정책금리 경로"),
        ("BASE_RATE", "한국은행 기준금리", "금리", "한국은행", "722Y001",
         "%", "월", 3.0, 0.4, "IRRBB 금리충격"),
        ("KTB3Y", "국고채 3년 금리", "금리", "한국은행", "817Y002",
         "%", "월", 3.2, 0.5, "IRRBB · 시장 VaR"),
        ("USDKRW", "원/달러 환율", "환율", "한국은행", "731Y001",
         "원", "월", 1340.0, 55.0, "외화 익스포저 · 시장 VaR"),
        ("UNEMP", "실업률", "고용", "통계청", "DT_1DA7104S",
         "%", "월", 3.0, 0.4, "리테일 PD"),
        ("HH_DEBT_GDP", "가계부채/GDP", "가계부채", "한국은행", "151Y005",
         "%", "분기", 92.0, 2.0, "리테일 LGD · 담보"),
        ("HOUSE_PRICE", "주택매매가격지수", "부동산", "한국은행", "901Y062",
         "지수", "월", 100.0, 3.5, "주담대 LGD (담보가치)"),
        ("KOSPI", "KOSPI", "금융시장", "한국은행", "802Y001",
         "지수", "월", 2600.0, 190.0, "시장 VaR · 지분증권"),
        ("CDS_5Y", "국가 CDS 프리미엄 5년", "대외", "한국은행", "902Y001",
         "bp", "월", 35.0, 9.0, "조달 스프레드 · 유동성"),
        ("BANK_NPL", "국내은행 고정이하여신비율", "가계부채", "금융감독원",
         "FSS-NPL", "%", "분기", 0.45, 0.09, "부도율 벤치마크"),
        ("TERM_SPREAD", "장단기 금리차 (10y−3y)", "금리", "한국은행",
         "817Y002", "%p", "월", 0.35, 0.22, "경기 선행 · z 보정"),
    )
    _CIT = ("출처 기관·통계표 코드는 실 피드 연결 지점으로 적어 둔 것이며 "
            "ECOS·KOSIS 공표 카탈로그와 대조하지 않았다. level·vol은 합성 "
            "계열의 기준점이고 공표치가 아니다")
    out = pd.DataFrame([
        {"indicator_id": iid, "name": name, "category": cat, "source": src,
         "source_code": code, "unit": unit, "freq": freq,
         "level": float(level), "vol": float(vol),
         "mean_reversion": _REVERSION, "noise_scale": _NOISE,
         "drives": drives,
         "input_source": "합성기준점",
         "entered_by": None, "approved_by": None, "approved_on": None,
         "citation": _CIT, "evidence_status": "미확인"}
        for iid, name, cat, src, code, unit, freq, level, vol, drives in rows
    ])
    return out.astype({"level": "float64", "vol": "float64",
                       "mean_reversion": "float64", "noise_scale": "float64"})


def build_macro_scenario_shock(master: pd.DataFrame | None = None
                               ) -> pd.DataFrame:
    """시나리오 × 지표 충격 배수 원장. 전건 내부가정이다.

    마스터에 있는 모든 지표에 대해 시나리오마다 1행을 낸다. 충격을 주지
    않는 조합도 배수 0.0으로 남긴다. 행을 비워 두면 "이 지표는 이 시나리오에서
    움직이지 않는다고 가정했다"는 판단이 원장에서 사라진다.

    배수는 규정 근거가 없다. 감독규정·BCBS 어느 문서도 지표별 표준편차 배수를
    주지 않는다. 그래서 전건 `evidence_status='내부가정'`이고 승인자가 비어 있다.
    """
    # (시나리오, 지표, 배수). 배수를 적지 않은 조합은 0.0으로 채운다.
    shocks: dict[str, dict[str, float]] = {
        "baseline": {},
        "adverse": {"GDP_YOY": -1.6, "UNEMP": +1.4, "HOUSE_PRICE": -1.5,
                    "KOSPI": -1.5, "CDS_5Y": +1.4, "BANK_NPL": +1.5,
                    "USDKRW": +1.2, "TERM_SPREAD": -1.2},
        "severely_adverse": {"GDP_YOY": -3.2, "UNEMP": +2.8,
                             "HOUSE_PRICE": -3.0, "KOSPI": -3.0,
                             "CDS_5Y": +3.2, "BANK_NPL": +3.4,
                             "USDKRW": +2.6, "TERM_SPREAD": -2.4},
    }
    _CIT = ("규정 근거 없음. 감독규정·BCBS 문서는 지표별 표준편차 배수를 "
            "정하지 않는다. 심도 구분은 내부 시나리오 설계 판단이다")
    if master is None:
        master = build_macro_indicator_master()
    rows = []
    for scen in SCENARIOS:
        table = shocks.get(scen, {})
        for iid in master["indicator_id"]:
            mult = float(table.get(str(iid), 0.0))
            if mult > 0:
                rule = "상승 충격 (배수 × 지표 표준편차)"
            elif mult < 0:
                rule = "하락 충격 (배수 × 지표 표준편차)"
            else:
                rule = "충격 없음. 이 시나리오에서 움직이지 않는다고 가정"
            rows.append({
                "scenario": scen, "indicator_id": str(iid),
                "multiplier": mult, "direction_rule": rule,
                "citation": _CIT, "approved_by": None, "approved_on": None,
                "evidence_status": "내부가정",
            })
    return pd.DataFrame(rows).astype({"multiplier": "float64"})


def build_macro_master_ledgers() -> dict[str, pd.DataFrame]:
    """두 마스터 원장을 테이블명으로 돌려준다. 배선이 이 dict를 그대로 싣는다."""
    master = build_macro_indicator_master()
    return {INDICATOR_MASTER.name: master,
            SCENARIO_SHOCK_LEDGER.name: build_macro_scenario_shock(master)}


# ---------------------------------------------------------------- 원장 뷰

def indicator_specs(master: pd.DataFrame | None = None
                    ) -> tuple[IndicatorSpec, ...]:
    """마스터 원장을 엔진용 값 객체로 옮긴다. 원장 행 순서를 유지한다."""
    if master is None:
        master = build_macro_indicator_master()
    return tuple(
        IndicatorSpec(
            indicator_id=str(r["indicator_id"]), name=str(r["name"]),
            category=str(r["category"]), source=str(r["source"]),
            code=str(r["source_code"]), unit=str(r["unit"]),
            freq=str(r["freq"]),
            level=None if pd.isna(r["level"]) else float(r["level"]),
            vol=None if pd.isna(r["vol"]) else float(r["vol"]),
            mean_reversion=(None if pd.isna(r["mean_reversion"])
                            else float(r["mean_reversion"])),
            noise_scale=(None if pd.isna(r["noise_scale"])
                         else float(r["noise_scale"])),
            drives=str(r["drives"]))
        for _, r in master.iterrows())


def scenario_shock_map(shock_ledger: pd.DataFrame | None = None
                       ) -> dict[str, dict[str, float]]:
    """충격 원장을 시나리오 → 지표 → 배수 조회표로 옮긴다.

    NULL 배수는 조회표에 넣지 않는다. 소비처가 "0으로 조정"과 "값을 모른다"를
    구분할 수 있어야 한다.
    """
    if shock_ledger is None:
        shock_ledger = build_macro_scenario_shock()
    out: dict[str, dict[str, float]] = {}
    for _, r in shock_ledger.iterrows():
        if pd.isna(r["multiplier"]):
            continue
        out.setdefault(str(r["scenario"]), {})[str(r["indicator_id"])] = \
            float(r["multiplier"])
    return out


def unapproved_indicators(master: pd.DataFrame | None = None) -> pd.DataFrame:
    """승인자 또는 승인일이 빈 지표 마스터 행.

    수기입력 원장은 입력자·승인자·승인일이 채워져야 결재 대상이다. 이 함수가
    돌려주는 행은 화면과 검증에 그대로 실려야 한다.
    """
    if master is None:
        master = build_macro_indicator_master()
    return master[master["approved_by"].isna()
                  | master["approved_on"].isna()].copy()


def unapproved_scenario_shocks(shock_ledger: pd.DataFrame | None = None
                               ) -> pd.DataFrame:
    """승인자 또는 승인일이 빈 충격 배수 행. 내부가정이므로 승인이 필요하다."""
    if shock_ledger is None:
        shock_ledger = build_macro_scenario_shock()
    return shock_ledger[shock_ledger["approved_by"].isna()
                        | shock_ledger["approved_on"].isna()].copy()


# ---------------------------------------------------------------- 엔진

def _rng(seed: int, key: str) -> np.random.Generator:
    """지표별 전용 스트림. 지표를 추가해도 기존 계열이 흔들리지 않는다."""
    off = int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16) % 100_000
    return np.random.default_rng(seed + off)


def _periods(asof: date, n: int, freq: str) -> list[str]:
    if freq == "분기":
        out, y, q = [], asof.year, (asof.month - 1) // 3 + 1
        for _ in range(n):
            out.append(f"{y}Q{q}")
            q -= 1
            if q == 0:
                q, y = 4, y - 1
        return list(reversed(out))
    out, y, m = [], asof.year, asof.month
    for _ in range(n):
        out.append(f"{y}-{m:02d}")
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return list(reversed(out))


def observations(asof: date | str, *, seed: int = 42, n_periods: int = 12,
                 master: pd.DataFrame | None = None) -> pd.DataFrame:
    """지표별 관측 계열. `basis`는 전건 '파생'이다. 외부 피드가 없다.

    `master`를 주지 않으면 빌더가 만든 기본 원장을 쓴다. 계열의 모양을 정하는
    값(level·vol)은 전부 원장에서 오며 이 함수에는 없다.

    계열 생성에 필요한 칸(level·vol·mean_reversion·noise_scale) 중 하나라도
    NULL인 지표는 **건너뛰고 경고를 남긴다**. 임의의 기본값을 넣으면 미입력이
    산출물에서 사라진다.
    """
    if isinstance(asof, str):
        asof = date.fromisoformat(asof)
    specs = indicator_specs(master)
    rows: list[dict] = []
    skipped: list[MacroWarning] = []
    for sp in specs:
        if None in (sp.level, sp.vol, sp.mean_reversion, sp.noise_scale):
            skipped.append(MacroWarning(
                sp.indicator_id, "level·vol·mean_reversion·noise_scale",
                "마스터에 계열 생성에 필요한 칸이 비어 있어 만들지 않는다"))
            continue
        g = _rng(seed, sp.indicator_id)
        # 경로의 모양(회귀 속도·잡음 배율)은 전부 원장에서 온다.
        vals, v = [], sp.level
        for _ in range(n_periods):
            v = (v + sp.mean_reversion * (sp.level - v)
                 + g.normal(0, sp.vol * sp.noise_scale))
            vals.append(v)
        pers = _periods(asof, n_periods, sp.freq)
        for i, (p, v) in enumerate(zip(pers, vals)):
            prior = vals[i - 4] if i >= 4 else None
            rows.append({
                "indicator_id": sp.indicator_id, "name": sp.name,
                "category": sp.category, "source": sp.source,
                "source_code": sp.code, "period": p, "freq": sp.freq,
                "value": round(float(v), 4), "unit": sp.unit,
                "yoy": (None if prior in (None, 0) else
                        round(float(v / prior - 1), 6)),
                "basis": "파생",
            })
    for w in skipped:
        warnings.warn(f"{w.indicator_id}: {w.reason}", MacroLedgerWarning,
                      stacklevel=2)
    return pd.DataFrame(rows)


def latest_observations(obs: pd.DataFrame) -> pd.DataFrame:
    """지표별 최근 관측 1행.

    시나리오 연결과 모니터링 화면이 같은 "최근값"을 봐야 한다. 두 곳에서
    각자 뽑으면 어느 쪽이 그 지표의 현재값인지 사후에 물어야 한다.
    """
    return obs.sort_values("period").groupby("indicator_id").tail(1)


def scenario_links(obs: pd.DataFrame, *, master: pd.DataFrame | None = None,
                   shock_ledger: pd.DataFrame | None = None) -> pd.DataFrame:
    """시나리오 가정이 어느 지표의 어떤 값에서 나왔는지 남긴다.

    충격폭 = 원장의 배수 × 마스터의 vol. 두 값 모두 인자로 받은 원장에서
    오므로, 원장을 바꾸면 이 함수의 산출이 따라 바뀐다.

    배수가 NULL인 조합은 조정 없이 최근값을 그대로 두고 경고를 남긴다.
    """
    if master is None:
        master = build_macro_indicator_master()
    if shock_ledger is None:
        shock_ledger = build_macro_scenario_shock(master)
    latest = latest_observations(obs).set_index("indicator_id")
    by_id = {s.indicator_id: s for s in indicator_specs(master)}
    rows, missing = [], []
    for _, sr in shock_ledger.iterrows():
        iid = str(sr["indicator_id"])
        if iid not in latest.index or iid not in by_id:
            continue
        sp = by_id[iid]
        base = float(latest.loc[iid, "value"])
        if pd.isna(sr["multiplier"]) or sp.vol is None:
            missing.append(MacroWarning(
                iid, "multiplier",
                f"시나리오 {sr['scenario']}의 배수 또는 vol이 없어 조정하지 "
                "않는다"))
            val = base
        else:
            val = base + float(sr["multiplier"]) * sp.vol
        rows.append({
            "scenario": str(sr["scenario"]), "indicator_id": iid,
            "name": sp.name, "latest": round(base, 4),
            "scenario_value": round(float(val), 4),
            "shock": round(float(val - base), 4), "drives": sp.drives,
        })
    for w in missing:
        warnings.warn(f"{w.indicator_id}: {w.reason}", MacroLedgerWarning,
                      stacklevel=2)
    return pd.DataFrame(rows)


def alerts(obs: pd.DataFrame, *, z_threshold: float,
           master: pd.DataFrame | None = None) -> list[dict]:
    """최근 관측이 자기 계열의 평소 범위를 벗어난 지표.

    임계는 계열 자신의 표준편차로 잡는다. 지표마다 수준·단위가 달라 절대값
    임계를 두면 환율만 계속 걸린다. `drives`는 마스터에서 읽는다.

    `z_threshold`에 기본값을 두지 않는다. 기본값을 두면 임계가 엔진 소스에
    박히고, 호출자가 무엇을 임계로 썼는지가 산출물에서 사라진다.
    """
    if master is None:
        master = build_macro_indicator_master()
    out = []
    for iid, g in obs.groupby("indicator_id"):
        g = g.sort_values("period")
        v = g["value"].to_numpy()
        if len(v) < 4:
            continue
        mu, sd = float(v[:-1].mean()), float(v[:-1].std(ddof=1))
        if sd <= 0:
            continue
        z = (float(v[-1]) - mu) / sd
        if abs(z) >= z_threshold:
            r = g.iloc[-1]
            out.append({
                "indicator_id": iid, "name": str(r["name"]),
                "category": str(r["category"]), "period": str(r["period"]),
                "value": float(r["value"]), "unit": str(r["unit"]),
                "z": round(z, 2), "drives": by_id_drives(iid, master),
            })
    return sorted(out, key=lambda x: -abs(x["z"]))


def by_id_drives(indicator_id: str, master: pd.DataFrame | None = None) -> str:
    """지표가 움직이는 축. 마스터에 없으면 빈 문자열이다."""
    if master is None:
        master = build_macro_indicator_master()
    hit = master[master["indicator_id"] == indicator_id]
    return "" if hit.empty else str(hit["drives"].iloc[0])


# 구 모듈 상수 `INDICATORS`·`SCENARIO_SHOCK`은 삭제했다. 데이터를 소스에 두는
# 자리였고, 화면·검증이 그 값을 볼 수 없었기 때문이다. 아직 옛 이름으로 읽는
# 소비처(ui_studio/app.py)가 남아 있어 원장에서 만든 파생 뷰로 응답하되
# DeprecationWarning을 남긴다. 소비처가 `s.tables['rdm_macro_indicator_master']`
# 와 `s.tables['st_macro_scenario_shock']`을 읽도록 옮기면 이 블록을 지운다.
_DEPRECATED = {
    "INDICATORS": (indicator_specs,
                   "rdm_macro_indicator_master 원장 또는 indicator_specs()"),
    "SCENARIO_SHOCK": (scenario_shock_map,
                       "st_macro_scenario_shock 원장 또는 scenario_shock_map()"),
}


def __getattr__(name: str):
    if name in _DEPRECATED:
        build, replacement = _DEPRECATED[name]
        warnings.warn(
            f"macro_monitor.{name}은(는) 원장으로 옮겼다. {replacement}을(를) "
            "읽어라. 이 파생 뷰는 원장이 바뀌어도 호출 시점에 다시 만들어진다.",
            DeprecationWarning, stacklevel=2)
        return build()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
