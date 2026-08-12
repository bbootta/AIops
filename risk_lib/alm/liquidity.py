"""유동성 — 만기 사다리와 생존기간. 계약 현금흐름 원장에서 뽑는다.

**무엇을 고치는가.** `balance_sheet.py`가 사다리를 상수 가중 벡터
(`asset_w = [0.06, 0.08, …]`)로 만들면서 `portfolio['maturity']`를 쓰지
않았다. 포트폴리오의 만기 분포를 바꿔도 사다리가 미동하지 않으므로 그 사다리를
소비하는 IRRBB·유동성비율·업무보고서가 전부 포트폴리오와 무관한 값을
보고했다. 여기서는 사다리를 `alm_cashflow_bucket`(계약/행동조정 두 벌)에서
집계하거나, 계약원장이 아직 없는 경로에서는 포트폴리오 만기와 NMD 파라미터
원장에서 직접 슬로팅한다. 두 경로 모두 만기 분포의 함수다.

**시간축이 두 개이고 서로 다른 함수가 만든다.** `build_maturity_ladder`가
`alm_cashflow_bucket`에서 접는 사다리의 시간축은 **리프라이싱**이다 — 입력
원장이 변동금리 계약의 명목 전액을 차기 리프라이싱일에 놓기 때문이다(BCBS
d368 Annex 2). 잔존만기 축은 그것으로 만들 수 없다. 10년 변동금리 대출은
최단 버킷에서 금리가 재설정되지만 그 기간에 현금화되지 않는다. 잔존만기 축이
필요한 소비처(은행업감독규정 제26조·제63조 유동성비율, BCBS d238 ¶177~187
계약만기 불일치)는 `build_contractual_balance_ladder`를 쓴다 — 계약원장의
`maturity_date`에서 직접 접으므로 두 축이 갈라지지 않으면서 분리된다.

**계약 사다리와 행태 사다리를 나란히 둔다.** `basis` 축이 있어야 감독당국이
비교하는 차이 — 비만기예금이 계약기준에서는 전액 최단 버킷이고 행태기준에서는
4~5년에 퍼진다 — 가 원장에서 조인된다. 서식 각주
(`forms_fss_liquidity._LADDER_NOTE`, `forms_fss_profit`)가 "비만기성 예금은
행태만기로 슬로팅되어 있다"고 감독당국 제출문서에 적고 있으므로, 그 문장이
사실이 되려면 부채측 NMD가 실제로 행태 슬로팅되어야 한다.

**생존기간.** LCR 30일은 최소 시계이며 내부 스트레스테스트는 더 긴 시계를
포함해야 한다(BCBS d144 Principle 10). 다만 **유출률의 시나리오별 분해값도,
목표 생존기간도 규정값이 없다**(d144는 원칙만 제시하고 EWI·CFP 트리거는 은행이
정하고 이사회가 승인한다 — Principle 11). 그래서 유출률은 전부
`alm_liquidity_stress_param` 원장에서 오고, 값을 모르는 시나리오는 NULL로 두어
엔진이 조용히 대체값을 쓰는 대신 경고를 남기고 그 시나리오를 건너뛴다.

**결정론.** 이 모듈에는 난수가 없다. 원장을 결정론적으로 변환할 뿐이다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

from risk_lib.alm.behaviour import ParamWarning, nmd_slotting
from risk_lib.alm.cashflow import BASES, CF_SCENARIOS
from risk_lib.alm.params import EVIDENCE_STATUS
from risk_lib.datamodel.spec import ColumnSpec as C, ForeignKey as FK, TableSpec

__all__ = [
    "STRESS_SCENARIOS", "STRESS_EVIDENCE", "RUNOFF_PROFILES",
    "MATURITY_LADDER", "LIQUIDITY_STRESS_PARAM", "SURVIVAL_PATH",
    "LIQUIDITY_TABLES", "SurvivalResult",
    "build_maturity_ladder", "build_liquidity_stress_param",
    "build_survival_path", "build_repricing_ladder",
    "build_contractual_balance_ladder",
]

# 최소 3종. '정상'은 스트레스 미적용 기준선이고, '기관고유'·'시장전반'은
# BCBS d144 Principle 10이 요구하는 두 축이다.
STRESS_SCENARIOS: tuple[str, ...] = ("정상", "기관고유", "시장전반")

# 0% 유출은 규제에서 읽은 수치가 아니라 시나리오의 **정의**다. 근거 상태를
# '원문확인'으로 적으면 읽지도 않은 원문을 읽었다고 쓰는 것이 되고 '미확인'으로
# 적으면 비어 있지 않은 값을 비었다고 쓰는 것이 된다.
STRESS_EVIDENCE: tuple[str, ...] = EVIDENCE_STATUS + ("정의",)

# 누적 유출을 시계 안에서 어떻게 펴는가. 국내외 규정 어디에도 프로파일 형태에
# 대한 근거가 없으므로 선형만 적재하고, 컬럼으로 두어 가정이 보이게 한다.
RUNOFF_PROFILES: tuple[str, ...] = ("linear",)


# ---------------------------------------------------------------- 스펙

MATURITY_LADDER = TableSpec(
    name="alm_maturity_ladder", korean="만기 사다리", product="PRD-ALM",
    grain="기준일 × 시나리오 × 산출기준 × 통화 × 시간버킷 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("scenario", "string", "시나리오", nullable=False, allowed=CF_SCENARIOS),
        C("basis", "string", "산출기준", nullable=False, allowed=BASES,
          citation="계약 = 행동가정 배제, 행동조정 = CPR·TDRR·NMD 적용. "
                   "**시간축은 리프라이싱이다** — BCBS d238 ¶177~187의 계약만기 "
                   "불일치 사다리가 아니다",
          note="basis는 행동가정의 유무만 가른다. 시간축이 아니다"),
        C("ccy", "string", "통화", nullable=False),
        C("bucket", "string", "시간버킷", nullable=False),
        C("seq", "int", "버킷 순서", nullable=False, min_value=1),
        C("t_mid", "float", "버킷 중점", nullable=False, unit="years",
          min_value=0.0),
        C("inflow", "float", "유입", nullable=False, unit="KRW",
          note="자산측 현금흐름 합계"),
        C("outflow", "float", "유출", nullable=False, unit="KRW",
          note="부채·부외측 현금흐름 합계. 부호는 양수로 적고 갭에서 뺀다"),
        C("net_gap", "float", "순갭", nullable=False, unit="KRW"),
        C("cumulative_gap", "float", "누적갭", nullable=False, unit="KRW"),
        C("counterbalancing_capacity", "float", "반대매매가능자산",
          nullable=True, unit="KRW",
          note="헤어컷 후 미담보 HQLA 스톡. 최단 버킷에 놓는다 — 즉시 현금화가 "
               "가능하다는 것이 이 자산의 정의다. 미제공이면 NULL이며 사다리는 "
               "갭만 보고한다"),
    ),
    primary_key=("asof", "scenario", "basis", "ccy", "bucket"),
    note="alm_cashflow_bucket에서 집계한다. 상수 가중 벡터를 쓰지 않으므로 "
         "포트폴리오 만기 분포가 바뀌면 사다리가 반드시 따라 움직인다. "
         "**시간축은 잔존만기가 아니라 리프라이싱이다** — 입력인 "
         "alm_cashflow_bucket이 변동금리 계약의 명목 전액을 차기 리프라이싱일에 "
         "슬로팅한 IRRBB용 원장이고(BCBS d368 Annex 2), 이 장은 그것을 접기만 "
         "한다. 자산 원금의 상당 부분이 잔존만기 1년 초과인데도 1년 이내 "
         "버킷에 실린다. 잔존만기 축 잔액 사다리는 "
         "`build_contractual_balance_ladder`가 계약원장에서 따로 만든다.",
)

LIQUIDITY_STRESS_PARAM = TableSpec(
    name="alm_liquidity_stress_param", korean="유동성 스트레스 유출률",
    product="PRD-ALM",
    grain="스트레스 시나리오 × 항목 1행",
    columns=(
        C("stress_scenario", "string", "스트레스 시나리오", nullable=False,
          allowed=STRESS_SCENARIOS),
        C("category", "string", "항목", nullable=False),
        C("cum_runoff_rate", "float", "시계내 누적 유출률", nullable=True,
          unit="ratio", min_value=0.0, max_value=1.0,
          note="NULL이면 엔진이 그 시나리오를 산출하지 않고 경고를 남긴다"),
        C("horizon_days", "int", "시계", nullable=False, unit="days",
          min_value=1),
        C("runoff_profile", "string", "유출 프로파일", nullable=False,
          allowed=RUNOFF_PROFILES),
        C("citation", "text", "근거", nullable=True),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=STRESS_EVIDENCE),
    ),
    primary_key=("stress_scenario", "category"),
    note="유출률에 규정값이 없다(BCBS d144는 원칙만). LCR 유출률은 기관고유와 "
         "시장전반이 **복합된** 하나의 시나리오이며 분해 계수는 공표되지 "
         "않았다 — 그래서 시장전반 행은 비어 있다.",
)

SURVIVAL_PATH = TableSpec(
    name="alm_survival_path", korean="생존기간 경로", product="PRD-ALM",
    grain="기준일 × 스트레스 시나리오 × 일자 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("scenario", "string", "스트레스 시나리오", nullable=False,
          allowed=STRESS_SCENARIOS),
        C("day", "int", "경과일", nullable=False, unit="days", min_value=0),
        C("net_outflow_cum", "float", "누적 순유출", nullable=False, unit="KRW"),
        C("cbc_remaining", "float", "잔여 반대매매가능자산", nullable=False,
          unit="KRW"),
        C("survived", "bool", "생존", nullable=False,
          note="cbc_remaining >= 0. 최초 False인 날이 생존기간이다"),
    ),
    primary_key=("asof", "scenario", "day"),
    foreign_keys=(FK(("scenario",), "alm_liquidity_stress_param",
                     ("stress_scenario",)),),
    note="BCBS d144 Principle 10 — LCR 30일은 최소이며 내부 스트레스테스트는 "
         "더 긴 시계를 포함해야 한다. 목표 생존기간은 규정값이 없고 이사회 "
         "승인 대상이므로 이 장은 산출만 하고 판정하지 않는다.",
)

LIQUIDITY_TABLES: tuple[TableSpec, ...] = (
    MATURITY_LADDER, LIQUIDITY_STRESS_PARAM, SURVIVAL_PATH)


# ---------------------------------------------------------------- 만기 사다리

def build_maturity_ladder(
    cashflow_bucket: pd.DataFrame, *,
    counterbalancing_capacity: float | None = None,
) -> pd.DataFrame:
    """`alm_cashflow_bucket` → `alm_maturity_ladder`.

    자산측 현금흐름이 유입, 부채·부외측이 유출이다. 누적갭은 버킷 순서대로
    쌓으며, 시나리오·산출기준·통화가 다르면 다른 사다리이므로 누적을 섞지
    않는다 — 여기서 groupby를 빠뜨리면 통화 간 갭이 서로를 상쇄한다.

    반대매매가능자산은 **최단 버킷에만** 놓는다. 미담보 HQLA는 정의상 즉시
    현금화 가능하므로 시점 분산이 없고, 버킷마다 전액을 반복해 적으면 사다리를
    가로로 더할 때 같은 자산이 여러 번 세어진다.
    """
    cols = list(MATURITY_LADDER.column_names)
    if cashflow_bucket.empty:
        return pd.DataFrame(columns=cols)

    df = cashflow_bucket.copy()
    df["inflow"] = np.where(df["side"] == "asset", df["total_cf"], 0.0)
    df["outflow"] = np.where(df["side"] != "asset", df["total_cf"], 0.0)
    g = (df.groupby(["asof", "scenario", "basis", "ccy", "bucket", "seq",
                     "t_mid"], as_index=False)
           .agg(inflow=("inflow", "sum"), outflow=("outflow", "sum")))
    g["net_gap"] = g["inflow"] - g["outflow"]
    g = g.sort_values(["asof", "scenario", "basis", "ccy", "seq"]).reset_index(
        drop=True)
    key = ["asof", "scenario", "basis", "ccy"]
    g["cumulative_gap"] = g.groupby(key)["net_gap"].cumsum()

    if counterbalancing_capacity is None:
        g["counterbalancing_capacity"] = np.nan
    else:
        first = g.groupby(key)["seq"].transform("min")
        g["counterbalancing_capacity"] = np.where(
            g["seq"] == first, float(counterbalancing_capacity), 0.0)
    return g[cols]


# ------------------------------------------- 잔존만기 축 잔액 사다리

def build_contractual_balance_ladder(
    contracts: pd.DataFrame, buckets: pd.DataFrame, *, asof: str,
) -> pd.DataFrame:
    """계약원장 → **잔존만기 축** 잔액 사다리. 컬럼: bucket·seq·t_mid·assets·liabilities.

    `build_maturity_ladder`와 시간축이 다르다. 저쪽은 리프라이싱 축이고 여기는
    잔존만기 축이다. 은행업감독규정 제26조·제63조는 "잔존만기 n개월 이내"로
    분자·분모를 정의하고, BCBS d238 ¶177~187의 계약만기 불일치도 **행태가정
    배제 + 모든 유출이 최조기 지급가능일에 발생**이 정의다. 리프라이싱 사다리를
    그 자리에 넣으면 10년 변동금리 대출이 1개월 이내 유동성자산으로 계상된다.

    슬로팅 규약:
      · `maturity_date`가 있는 계약 → 그 날짜까지의 잔존기간
      · 만기가 NULL인 계약(비만기예금) → 최단 버킷. 요구불이므로 최조기
        지급가능일이 즉시다. 행태 코어예금 분산은 여기서 쓰지 않는다 —
        행태가정 배제가 이 축의 정의다
      · 자기자본 → 제외. 상환 의무가 없으므로 유동성 유출이 아니다

    **잔액 사다리다.** 유동성비율의 분자·분모는 현금흐름 현재가치가 아니라
    잔액이므로 `notional`을 놓는다. 이자는 넣지 않는다.
    """
    b = buckets.sort_values("seq").reset_index(drop=True)
    assets, liabs = np.zeros(len(b)), np.zeros(len(b))
    d = contracts
    if "asof" in d.columns:
        d = d[d["asof"] == asof]
    d = d[~d["is_own_equity"].astype(bool)]

    if not d.empty:
        asof_d = date.fromisoformat(asof)
        years = np.array([
            0.0 if m is None or pd.isna(m)
            else max((date.fromisoformat(str(m)) - asof_d).days / 365.25, 0.0)
            for m in d["maturity_date"]], dtype=float)
        idx = _slot(years, b)
        amt = d["notional"].to_numpy(dtype=float)
        is_asset = (d["side"].astype(str) == "asset").to_numpy()
        np.add.at(assets, idx[is_asset], amt[is_asset])
        np.add.at(liabs, idx[~is_asset], amt[~is_asset])

    return pd.DataFrame({
        "bucket": b["label"].astype(str), "seq": b["seq"].astype(int),
        "t_mid": b["t_mid_years"].astype(float),
        "assets": assets, "liabilities": liabs,
    })


# ------------------------------------------------------ 스트레스 유출률 원장

def build_liquidity_stress_param(
    lcr_factor: pd.DataFrame, *, horizon_days: int,
) -> pd.DataFrame:
    """스트레스 시나리오별 누적 유출률 원장.

    세 시나리오의 근거 상태가 서로 다르고, 그 차이가 이 표의 요점이다.

    · 정상    — 유출률 0%. 규제 수치가 아니라 기준선의 정의다.
    · 기관고유 — LCR 유출률을 준용한다. LCR 시나리오 자체가 기관고유 충격과
                 시장전반 충격의 **복합**이므로(BCBS d238 ¶19) 이를 기관고유에
                 배정하는 것은 보수적 준용이며 원문이 그렇게 나누라고 한 것이
                 아니다. 그 사실을 citation에 적는다.
    · 시장전반 — **NULL.** 복합 시나리오를 두 축으로 분해한 계수는 공표되지
                 않았고 국내 세칙 [별표 3-6] 원문도 미열람이다. 여기에 임의
                 승수를 넣으면 지어내기가 된다.

    `horizon_days`는 인자다. 함수 기본값으로 두면 시계가 소스에 숨는데, 목표
    생존기간에는 규정값이 없고 이사회 승인 대상이다(BCBS d144 Principle 11).
    """
    out = lcr_factor[lcr_factor["section"] == "유출"]
    rows: list[dict] = []
    for _, r in out.iterrows():
        cat = str(r["category"])
        rows.append({
            "stress_scenario": "정상", "category": cat,
            "cum_runoff_rate": 0.0, "horizon_days": int(horizon_days),
            "runoff_profile": "linear",
            "citation": "무스트레스 기준선 — 계약 현금흐름 외 유출 없음",
            "evidence_status": "정의",
        })
        rows.append({
            "stress_scenario": "기관고유", "category": cat,
            "cum_runoff_rate": (None if pd.isna(r["factor"])
                                else float(r["factor"])),
            "horizon_days": int(horizon_days), "runoff_profile": "linear",
            "citation": ("BCBS d238 LCR40 유출률 준용 — LCR 시나리오는 기관고유·"
                         "시장전반 복합이며 분해 계수는 공표되지 않았다"),
            "evidence_status": ("미확인" if pd.isna(r["factor"])
                                else str(r["evidence_status"])),
        })
        rows.append({
            "stress_scenario": "시장전반", "category": cat,
            "cum_runoff_rate": None, "horizon_days": int(horizon_days),
            "runoff_profile": "linear",
            "citation": ("시장전반 충격 단독 유출률 미공표 — 은행업감독업무"
                         "시행세칙 [별표 3-6] 원문 미열람"),
            "evidence_status": "미확인",
        })
    return pd.DataFrame(rows).astype({"cum_runoff_rate": "float64",
                                      "horizon_days": "int64"})


# ---------------------------------------------------------------- 생존기간

@dataclass
class SurvivalResult:
    path: pd.DataFrame
    survival_days: dict[str, int | None]     # None = 시계 안에서 미소진
    warnings: list[ParamWarning] = field(default_factory=list)

    def warning_frame(self) -> pd.DataFrame:
        return pd.DataFrame([{"model": w.model, "scope": w.scope,
                              "param": w.param, "reason": w.reason}
                             for w in self.warnings],
                            columns=["model", "scope", "param", "reason"])


def build_survival_path(
    balances: pd.DataFrame, stress_param: pd.DataFrame, *,
    asof: str, counterbalancing_capacity: float,
) -> SurvivalResult:
    """스트레스 시나리오별 생존기간 경로.

    `balances`: (category, balance). category 어휘는 `alm_lcr_factor`의 유출
    항목과 같아야 원장이 조인된다.

    누적 순유출은 시계 안에서 선형으로 편다. **프로파일 형태에 근거가 없다** —
    앞당겨 실현되는 유출(front-loaded)이 실제에 가깝다는 실무 통설이 있으나
    공표된 계수를 못 봤으므로 원장의 `runoff_profile`을 컬럼으로 두고 선형만
    적재했다. 프로파일을 바꾸면 생존일수가 바뀐다는 사실이 원장에서 보인다.

    유출률이 하나라도 NULL인 시나리오는 **산출하지 않는다.** 빠진 항목을 0으로
    두면 그 시나리오가 실제보다 오래 생존하는 것으로 나오고, 비어 있음이
    "안전함"으로 뒤집힌다.
    """
    warns: list[ParamWarning] = []
    bal = dict(zip(balances["category"].astype(str),
                   balances["balance"].astype(float)))
    rows: list[dict] = []
    survival: dict[str, int | None] = {}

    for sc in stress_param["stress_scenario"].drop_duplicates():
        p = stress_param[stress_param["stress_scenario"] == sc]
        used = p[p["category"].astype(str).isin(bal)]
        missing = used[used["cum_runoff_rate"].isna()]
        if not missing.empty:
            warns.append(ParamWarning(
                "생존기간", str(sc), "cum_runoff_rate",
                f"유출률이 비어 있는 항목 {len(missing)}건 "
                f"({', '.join(sorted(missing['category'].astype(str))[:3])} …) "
                "— 이 시나리오는 산출하지 않는다"))
            continue
        if used.empty:
            warns.append(ParamWarning(
                "생존기간", str(sc), "category",
                "잔액과 이름이 맞는 유출 항목이 없다 — 시나리오 미산출"))
            continue

        horizon = int(used["horizon_days"].iloc[0])
        total = float(sum(bal[str(c)] * float(r) for c, r in zip(
            used["category"], used["cum_runoff_rate"])))
        days = np.arange(0, horizon + 1, dtype=int)
        cum = total * days / horizon
        remaining = float(counterbalancing_capacity) - cum
        survived = remaining >= 0.0
        for d, cu, rm, sv in zip(days, cum, remaining, survived):
            rows.append({"asof": asof, "scenario": str(sc), "day": int(d),
                         "net_outflow_cum": float(cu),
                         "cbc_remaining": float(rm), "survived": bool(sv)})
        breach = days[~survived]
        survival[str(sc)] = int(breach[0]) if breach.size else None

    path = pd.DataFrame(rows, columns=list(SURVIVAL_PATH.column_names))
    if not path.empty:
        path = path.astype({"day": "int64", "survived": "bool"})
    return SurvivalResult(path=path, survival_days=survival, warnings=warns)


# ------------------------------------------- 계약원장 없는 경로의 사다리

def _slot(t_years, buckets: pd.DataFrame) -> np.ndarray:
    """연 단위 시점을 버킷 인덱스로 — `(lower, upper]` 규약.

    감독 사다리는 구간을 "n개월 이내"로 읽으므로 **상한이 포함된다**: 3개월
    재설정 대출은 `1-3m`이고 `3-6m`이 아니다. `side="right"`를 쓰면 경계에
    정확히 떨어지는 시점이 한 칸 위 버킷으로 올라가는데, 이 함수의 입력에는
    경계값이 실제로 들어온다 — 재설정 주기 3·6개월은 각각 0.25·0.5년이고
    조달 만기 구간의 끝도 1.0·5.0년이다. 그 결과 3개월 재설정 대출이 `3-6m`에
    앉아, 같은 계약을 실제 날짜 차이로 슬로팅하는 계약원장 경로
    (91/365.25 = 0.2491 → `1-3m`)와 다른 버킷에 놓였다.

    첫 버킷 하한 0은 따로 처리할 것이 없다 — 상한 배열만 보므로 t=0은 자연히
    첫 버킷이다. 마지막 버킷은 개방구간이므로 상한 초과는 마지막에 남긴다.
    """
    upper = buckets["upper_years"].to_numpy(dtype=float)
    idx = np.searchsorted(upper, np.asarray(t_years, dtype=float), side="left")
    return np.clip(idx, 0, len(upper) - 1)


def _range_weights(lower_years, upper_years, buckets: pd.DataFrame,
                   ) -> np.ndarray:
    """시점이 `(lo, hi]`에 고르게 퍼져 있을 때의 버킷별 금액 비중.

    반환 shape은 (n, len(buckets)) 이고 행 합은 1이다. `lo == hi`면 분산이
    아니라 한 점이므로 `_slot`과 같은 답을 낸다.

    **왜 한 점이 아니라 구간인가.** 재설정 주기가 3개월인 대출 포트폴리오는
    3개월마다 통째로 갈아타는 것이 아니라, 계약마다 주기 안의 서로 다른 지점에
    있다. 전량을 주기 끝(0.25년)에 놓으면 "오늘 전 계약이 동시에 재설정했다"고
    가정하는 것이 되어 최단 버킷이 구조적으로 비고, 그 사다리를 소비하는
    외화유동성비율 분자가 항상 0이 된다. 만기부 조달도 마찬가지로 카테고리가
    규정하는 만기 구간에 트랜치가 퍼져 있지 중점 한 점에 몰려 있지 않다 —
    중점 3.0년은 버킷 경계와 정확히 같아 슬로팅이 규약 하나로 뒤집혔다.

    계약원장 합성기(`contracts.build_contract_ledger`)도 차기 재설정일을 주기
    안에서, 조달 트랜치를 만기 구간 안에서 균등 추출한다. 여기서 균등 분산을
    쓰는 것이 두 사다리를 같은 가정 위에 놓는다.

    균등분포는 **정상상태 가정**이며 규정에서 읽은 값이 아니다. 계약원장이 있는
    경로(`build_maturity_ladder`)는 이 가정 없이 날짜에서 바로 슬로팅한다.
    """
    bl = buckets["lower_years"].to_numpy(dtype=float)[None, :]
    bu = buckets["upper_years"].to_numpy(dtype=float)[None, :]
    lo = np.atleast_1d(np.asarray(lower_years, dtype=float))[:, None]
    hi = np.atleast_1d(np.asarray(upper_years, dtype=float))[:, None]
    ov = np.clip(np.minimum(bu, hi) - np.maximum(bl, lo), 0.0, None)
    tot = ov.sum(axis=1, keepdims=True)
    out = np.divide(ov, tot, out=np.zeros_like(ov), where=tot > 0.0)
    point = np.flatnonzero(tot[:, 0] <= 0.0)
    if point.size:
        out[point, _slot(hi[point, 0], buckets)] = 1.0
    return out


def _reset_window(terms: pd.Series) -> float | None:
    """변동금리 재설정 주기(년). 고정금리이거나 주기를 모르면 None.

    BCBS d368 Annex 2: 변동금리 상품은 명목 전액이 **차기** 리프라이싱일에
    슬로팅된다. 잔존만기로 슬로팅하면 10년 변동금리 대출이 10년 버킷에 앉아
    자산 듀레이션이 통째로 부풀고 ΔEVE가 갭 방향으로 과대해진다. 주기를
    모르면 재설정 시점도 모르므로 만기에 그대로 둔다 — 0.25 같은 값을 끼워
    넣으면 원장에 없는 관행을 지어내는 것이 된다.
    """
    if str(terms["rate_type"]) != "floating":
        return None
    reset = terms.get("reset_freq_months")
    if reset is None or pd.isna(reset):
        return None
    return float(reset) / 12.0


def _allocate(out: np.ndarray, amounts, tenor_lo, tenor_hi,
              terms: pd.Series, buckets: pd.DataFrame) -> None:
    """`(tenor_lo, tenor_hi]`에 퍼진 잔액을 상품 금리유형에 따라 버킷에 더한다.

    변동금리는 재설정 주기가 시점을 앞당기므로 구간이 `(0, min(hi, 주기)]`로
    바뀐다. 고정금리는 만기 구간이 그대로 시점 구간이다.
    """
    lo = np.atleast_1d(np.asarray(tenor_lo, dtype=float))
    hi = np.atleast_1d(np.asarray(tenor_hi, dtype=float))
    win = _reset_window(terms)
    if win is not None:
        lo, hi = np.zeros_like(hi), np.minimum(hi, win)
    w = _range_weights(lo, hi, buckets)
    out += (w * np.atleast_1d(np.asarray(amounts, dtype=float))[:, None]
            ).sum(axis=0)


def build_repricing_ladder(
    portfolio: pd.DataFrame, *,
    funding: dict[str, float],
    hqla: dict[str, float],
    hqla_tenor_years: dict[str, float],
    asset_product_split: dict[str, tuple[str, str, float]],
    funding_product_of: dict[str, str],
    nmd_category_of: dict[str, str | None],
    funding_tenor_range: dict[str, tuple[float, float]],
    product_terms: pd.DataFrame,
    buckets: pd.DataFrame,
    nmd_param: pd.DataFrame,
    liability_scale: float = 1.0,
) -> tuple[pd.DataFrame, list[ParamWarning]]:
    """계약원장이 없는 경로에서 리프라이싱 사다리를 만든다.

    `alm_contract` + `alm_cashflow_bucket`이 갖춰지면 `build_maturity_ladder`가
    정본이다. 이 함수는 그 배선 전까지의 경로이며, 상수 가중 벡터와 다른 점은
    **모든 자리가 원장 또는 포트폴리오의 함수**라는 것이다.

    · 자산 — 자산군별 고정/변동 구성비(`asset_product_split`)로 나누고, 고정은
             `portfolio['maturity']`에, 변동은 재설정 주기 안에 퍼진 차기
             재설정일에 슬로팅한다. HQLA는 고정금리 만기일시이므로 등급별
             잔존만기로 간다.
    · 부채 — 비만기예금은 `alm_nmd_param`으로 **행태 슬로팅**하고(코어는 상한
             내 선형 분산, 논코어는 최단 버킷), 만기부 조달은 상품의 금리유형에
             따라 재설정 주기 또는 카테고리가 규정하는 만기 구간에 퍼뜨린다.

    `funding_tenor_range`는 중점이 아니라 **구간**이다. 중점 한 점으로 접으면
    `funding_gt1y`의 (1, 5]년이 3.0년이 되는데 이 값은 버킷 상한과 정확히 같아
    슬로팅이 경계 규약 하나로 뒤집힌다. 계약원장은 이 구간에 트랜치를 균등
    배치하므로 구간을 그대로 받는 것이 두 경로를 맞춘다.

    비만기예금을 행태로 펴는 것이 이 함수의 핵심이다. 서식 각주가 감독당국
    제출문서에 "비만기성 예금은 행태만기로 슬로팅되어 있다"고 적고 있으므로,
    상수 벡터를 쓰는 한 그 문장은 사실이 아니었다.

    고정/변동 구성비는 계약원장 합성기(`contracts._ASSET_PRODUCT`)가 쓰는 것과
    **같은 값**을 인자로 받는다. 여기 다시 적으면 같은 자산이 사다리와 계약
    원장에서 다른 버킷에 놓인다.

    `liability_scale`은 비금리민감 부채를 덜어내는 기존 규약을 그대로 옮긴
    것이다(사다리는 금리민감 자산·부채만 담는다).
    """
    b = buckets.sort_values("seq").reset_index(drop=True)
    n = len(b)
    assets = np.zeros(n)
    liabs = np.zeros(n)
    terms_by_code = product_terms.set_index("product_code")

    mat = portfolio["maturity"].to_numpy(dtype=float)
    ead = portfolio["ead"].to_numpy(dtype=float)
    ac = portfolio["asset_class"].astype(str).to_numpy()
    for cls, (fix_code, flt_code, fix_share) in asset_product_split.items():
        m = ac == cls
        if not m.any():
            continue
        for code, share in ((fix_code, fix_share), (flt_code, 1.0 - fix_share)):
            if share <= 0.0:
                continue
            _allocate(assets, ead[m] * share, mat[m], mat[m],
                      terms_by_code.loc[code], b)
    for lvl, amount in hqla.items():
        assets[int(_slot([hqla_tenor_years[lvl]], b)[0])] += float(amount)

    nmd_by_cat = nmd_param.set_index("nmd_category")
    warns: list[ParamWarning] = []
    for cat, amount in funding.items():
        if cat not in nmd_category_of:
            raise KeyError(
                f"조달 카테고리 {cat!r}의 슬로팅 규약이 없다 — 매핑 없이 "
                "떨어뜨리면 이 잔액이 사다리에서 조용히 사라진다")
        nmd_cat = nmd_category_of[cat]
        if nmd_cat is None:
            lo, hi = funding_tenor_range[cat]
            _allocate(liabs, [float(amount)], [lo], [hi],
                      terms_by_code.loc[funding_product_of[cat]], b)
            continue
        p = nmd_by_cat.loc[nmd_cat]
        points, _achieved, w = nmd_slotting(
            float(amount),
            core_ratio=float(p["core_ratio"]),
            core_ratio_cap=float(p["core_ratio_cap"]),
            avg_maturity_years=float(p["avg_maturity_years"]),
            avg_maturity_cap_years=float(p["avg_maturity_cap_years"]),
            buckets=b, stable_ratio=p["stable_ratio"], scope=f"funding:{cat}")
        warns.extend(w)
        for pt in points:
            liabs[int(_slot([pt.t_years], b)[0])] += pt.principal

    rep = pd.DataFrame({
        "bucket": b["label"].astype(str),
        "t_mid": b["t_mid_years"].astype(float),
        "assets": assets,
        "liabilities": liabs * float(liability_scale),
    }).assign(gap=lambda d: d["assets"] - d["liabilities"])
    # 경고를 반환값에 실어 보낸다 — NMD 상한 초과·stable_ratio 공백은 사다리를
    # 만든 가정의 결함이므로 사다리와 같은 곳에서 읽혀야 한다.
    return rep, list(dict.fromkeys(warns))
