"""ALM 현금흐름 산출 엔진 — 계약원장에서 계약/행동조정 현금흐름 두 벌을 낸다.

**무엇을 고치는가.** 현행 ALM에는 현금흐름 산출 엔진이 없다. `irrbb.py`는
리프라이싱 *갭*을 버킷 중점에서 할인하는 근사이고, 그 갭은
`balance_sheet.py`의 상수 벡터에서 나온다. 갭에는 회차도 옵션성도 없으므로
다음이 **원리적으로** 표현되지 않는다.

  · 상환방식(원리금균등 vs 만기일시)이 듀레이션에 미치는 영향
  · 조기상환·중도해지의 비선형성 (음의 컨벡서티는 갭 근사에서 나올 수 없다)
  · 계약기준 vs 행동기준 — 감독당국이 비교하는 바로 그 차이
  · 통화 축

**경계.** 이 엔진은 `alm_contract` + `alm_product_terms` **만** 읽는다.
포트폴리오 DataFrame을 직접 읽지 않는다. 출력은 `alm_cashflow_*` 세 장까지이며
ΔEVE·ΔNII·LCR·NSFR·사다리는 전부 이 원장의 **소비자**다. 지금은
`compute_irrbb`가 슬로팅·할인·최악시나리오 선택을 한 함수에서 해치우므로
중간산출이 원장에 남지 않고, 그래서 `pv_effect_worst`가 화면에는 그려지는데
원장에는 없다.

**계약 CF에 시나리오 축이 없는 이유.** 표준체계에서 변동금리 상품은 명목
전액이 차기 리프라이싱일에 슬로팅되고(BCBS d368 Annex 2), 리프라이싱 *날짜*는
시나리오로 움직이지 않는다. 고정금리 이표는 계약으로 확정돼 있다. 따라서
계약 CF는 (asof) 하나에 대해 **1벌**이다. 반면 행동 CF는 CPR/TDRR 승수가
시나리오 함수이므로 시나리오별로 여러 벌이다.

**마진 분리.** ΔEVE는 상업마진을 **제외**하고(BCBS d368 §132(3)), ΔNII는
**포함**한다(EBA GL 2022-14). 두 지표가 같은 이름의 현금흐름을 반대로 쓰므로
`interest_cf_ex_margin`과 `margin_cf`를 나눠 저장한다 — 조용한 규약으로 두면
이 차이가 보이지 않는다. 국내 세칙이 어느 쪽을 요구하는지는 미확인(설계 §5.16).

**자기자본.** `is_own_equity=True` 행은 ΔEVE 현금흐름에서 제외한다(BCBS d368
§132, 자기자본 미투자 가정). 다만 계약 CF 원장에는 컬럼과 함께 **남긴다** —
업계가 이 제외에 반론 중이고 감독 재량 여지가 있어 포함/제외 대조가 가능해야
한다. 버킷 집계(`alm_cashflow_bucket`)에서는 제외하며, 제외 금액을
`CashflowResult.own_equity_excluded`로 돌려준다.

**결정론.** 이 모듈에는 난수가 없다. 계약원장 합성(`contracts.py`)만이
`default_rng(seed + 1101)`을 쓰고, 여기서는 원장을 결정론적으로 변환할 뿐이다.
`hash()`·`Date.now()`·전역 `np.random`을 쓰지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

from risk_lib.datamodel.spec import ColumnSpec as C, ForeignKey as FK, TableSpec
from risk_lib.alm.behaviour import (
    CashflowPoint, ParamWarning, apply_early_redemption, apply_prepayment,
    effective_prepay_fee_rate, nmd_slotting, psa_cpr, scenario_multiplier,
    scurve_ri,
)
from risk_lib.alm.daycount import year_fraction
from risk_lib.alm.params import IRRBB_SCENARIOS, SIDES
from risk_lib.alm.schedule import SCHEDULED_AMORT_TYPES, build_schedule

__all__ = [
    "BASES", "CF_SCENARIOS",
    "CASHFLOW_CONTRACT", "CASHFLOW_BEHAVIOURAL", "CASHFLOW_BUCKET",
    "CASHFLOW_TABLES", "CashflowResult",
    "build_contract_cashflows", "build_behavioural_cashflows", "build_cashflows",
]

# 산출기준 — 감독당국이 비교하는 두 축.
BASES: tuple[str, ...] = ("계약", "행동조정")
# 'base'는 무충격 상태다. ΔEVE = PV_shock(CF_shock) − PV_base(CF_base) 이므로
# 기준 다리에 쓸 행동 CF가 따로 필요하다 — 승수 1.0(=조정 없음)이 그 정의다.
CF_SCENARIOS: tuple[str, ...] = ("base",) + IRRBB_SCENARIOS
BEHAVIOUR_MODEL_LABELS: tuple[str, ...] = ("CPR", "TDRR", "NMD")


# ---------------------------------------------------------------- 스펙

_CF_COLS = (
    C("t_mid", "float", "버킷 중점", nullable=False, unit="years", min_value=0.0),
    C("principal_cf", "float", "원금 현금흐름", nullable=False, unit="KRW"),
    C("interest_cf_ex_margin", "float", "이자(마진 제외)", nullable=False,
      unit="KRW",
      citation="BCBS d368 §132(3) — ΔEVE 현금흐름에서 상업마진 제외"),
    C("margin_cf", "float", "상업마진 성분", nullable=False, unit="KRW",
      citation="EBA GL 2022-14 — ΔNII는 마진 포함"),
)

CASHFLOW_CONTRACT = TableSpec(
    name="alm_cashflow_contract", korean="계약현금흐름", product="PRD-ALM",
    grain="기준일 × 계약 × 시간버킷 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("contract_id", "string", "계약 식별자", nullable=False),
        C("ccy", "string", "통화", nullable=False),
        C("side", "string", "측", nullable=False, allowed=SIDES),
        C("bucket", "string", "시간버킷", nullable=False),
        C("seq", "int", "버킷 순서", nullable=False, min_value=1),
        *_CF_COLS,
        C("repricing_flag", "bool", "리프라이싱 슬로팅", nullable=False,
          citation="BCBS d368 Annex 2 — 변동금리는 명목 전액을 차기 "
                   "리프라이싱일에 슬로팅"),
        C("is_own_equity", "bool", "자기자본", nullable=False,
          note="버킷 집계에서 제외된다 — 포함/제외 대조를 위해 여기 남긴다"),
    ),
    primary_key=("asof", "contract_id", "bucket"),
    foreign_keys=(FK(("asof", "contract_id"), "alm_contract",
                     ("asof", "contract_id")),),
    note="행동가정 미적용 — 감독당국 대사 기준선. 시나리오 축이 없다(설계 §1.3).",
)

CASHFLOW_BEHAVIOURAL = TableSpec(
    name="alm_cashflow_behavioural", korean="행동조정후 현금흐름",
    product="PRD-ALM",
    grain="기준일 × 시나리오 × 계약 × 시간버킷 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("scenario", "string", "시나리오", nullable=False, allowed=CF_SCENARIOS),
        C("contract_id", "string", "계약 식별자", nullable=False),
        C("ccy", "string", "통화", nullable=False),
        C("side", "string", "측", nullable=False, allowed=SIDES),
        C("bucket", "string", "시간버킷", nullable=False),
        C("seq", "int", "버킷 순서", nullable=False, min_value=1),
        *_CF_COLS,
        C("behaviour_model", "string", "행동모형", nullable=False,
          allowed=BEHAVIOUR_MODEL_LABELS),
        C("adjustment_cf", "float", "행동 − 계약", nullable=False, unit="KRW",
          note="부호 있음. 어느 모형이 어느 파라미터셋으로 얼마를 움직였는지가 "
               "원장에서 조인 가능해야 감독 비교가 성립한다"),
        C("param_set_id", "string", "파라미터셋", nullable=False),
    ),
    primary_key=("asof", "scenario", "contract_id", "bucket"),
    foreign_keys=(FK(("asof", "contract_id"), "alm_contract",
                     ("asof", "contract_id")),),
    note="behaviour_class != 'none' 계약만 적재한다 — 나머지는 정의상 계약 CF와 같다.",
)

CASHFLOW_BUCKET = TableSpec(
    name="alm_cashflow_bucket", korean="버킷 집계 현금흐름", product="PRD-ALM",
    grain="기준일 × 시나리오 × 산출기준 × 통화 × 측 × 시간버킷 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("scenario", "string", "시나리오", nullable=False, allowed=CF_SCENARIOS),
        C("basis", "string", "산출기준", nullable=False, allowed=BASES),
        C("ccy", "string", "통화", nullable=False),
        C("side", "string", "측", nullable=False, allowed=SIDES),
        C("bucket", "string", "시간버킷", nullable=False),
        C("seq", "int", "버킷 순서", nullable=False, min_value=1),
        *_CF_COLS,
        C("total_cf", "float", "합계 현금흐름", nullable=False, unit="KRW"),
        C("n_contracts", "int", "계약 수", nullable=False, min_value=0),
    ),
    primary_key=("asof", "scenario", "basis", "ccy", "side", "bucket"),
    note="화면·서식이 실제로 그리는 장. 자기자본은 제외되어 있다(BCBS d368 §132).",
)

CASHFLOW_TABLES: tuple[TableSpec, ...] = (
    CASHFLOW_CONTRACT, CASHFLOW_BEHAVIOURAL, CASHFLOW_BUCKET)


@dataclass
class CashflowResult:
    contract: pd.DataFrame
    behavioural: pd.DataFrame
    bucket: pd.DataFrame
    warnings: list[ParamWarning] = field(default_factory=list)
    own_equity_excluded: float = 0.0
    n_beyond_last_bucket: int = 0        # 마지막 버킷에 흡수된 현금흐름 건수

    def warning_frame(self) -> pd.DataFrame:
        """경고를 표로 — 산출물에 실려 나가야 "비어 있음"이 보인다."""
        return pd.DataFrame([{"model": w.model, "scope": w.scope,
                              "param": w.param, "reason": w.reason}
                             for w in self.warnings],
                            columns=["model", "scope", "param", "reason"])


# ---------------------------------------------------------------- 버킷 배정

class _Buckets:
    """`alm_time_bucket` 원장을 배정 함수로 감싼다. 버킷 수 K는 원장이 정한다."""

    def __init__(self, buckets: pd.DataFrame):
        b = buckets.sort_values("seq").reset_index(drop=True)
        if b.empty:
            raise ValueError("alm_time_bucket이 비어 있다 — 버킷 없이는 슬로팅 불가")
        self.frame = b
        self.upper = b["upper_years"].to_numpy(dtype=float)
        self.label = b["label"].to_numpy()
        self.seq = b["seq"].to_numpy(dtype=int)
        self.t_mid = b["t_mid_years"].to_numpy(dtype=float)
        self.shortest_t = float(self.t_mid[0])
        self.n_beyond = 0

    def assign(self, t_years: float) -> tuple[str, int, float]:
        """t를 버킷에 배정 — [lower, upper) 규약.

        사다리의 **마지막 버킷은 개방구간**이다(라벨이 "10y+"인 이유). 따라서
        상한과 정확히 같은 t(예: 만기 20.0년 주담대의 최종 원금)는 범위 초과가
        아니라 마지막 버킷에 속한다. `side="right"`만 쓰면 경계값이 배열 밖으로
        나가 정상 현금흐름이 "범위 초과"로 계수된다.

        `n_beyond`는 **진짜 절단**(t > 최종 상한)만 센다. 다만 마지막 버킷에
        들어간 흐름은 실제 시점과 무관하게 t_mid로 할인된다는 점은 남는다 —
        house 9버킷 사다리에서 20년 원금이 12.5년으로 할인되는 것이 그 예이며,
        이것이 표준 19버킷을 적재해야 하는 이유다(설계 §2.2).
        """
        i = int(np.searchsorted(self.upper, t_years, side="right"))
        if i >= len(self.upper):
            if t_years > self.upper[-1]:
                self.n_beyond += 1
            i = len(self.upper) - 1
        return str(self.label[i]), int(self.seq[i]), float(self.t_mid[i])


# ---------------------------------------------------------------- 계약 CF

def _split_margin(interest: float, coupon_rate: float,
                  margin_bp: float) -> tuple[float, float]:
    """이자를 (마진제외, 마진)으로 나눈다.

    이자 = 잔액 × r × τ 이고 마진성분 = 잔액 × m × τ 이므로 비율은 m/r이다.
    r = 0이면 이자 자체가 0이므로 분기해도 정보를 잃지 않는다.
    """
    if coupon_rate == 0.0:
        return interest, 0.0
    margin_cf = interest * (margin_bp / 1e4) / coupon_rate
    return interest - margin_cf, margin_cf


def _contract_points(row: pd.Series, terms: pd.Series, asof_d: date,
                     shortest_t: float) -> tuple[list[CashflowPoint], bool]:
    """계약 1건의 계약현금흐름. 반환: (현금흐름점, 리프라이싱 슬로팅 여부)."""
    notional = float(row["notional"])
    rate = float(row["coupon_rate"])
    amort = str(terms["amort_type"])

    # (1) 비만기 — 계약상 만기가 없으므로 전액 최단 버킷. 계약기준의 정의다.
    if amort not in SCHEDULED_AMORT_TYPES:
        return [CashflowPoint(shortest_t, notional, 0.0)], False

    # (2) 변동금리 — 명목 전액을 차기 리프라이싱일에 슬로팅하고, 그날까지의
    #     경과이자를 함께 놓는다. 리프라이싱 후에는 par로 되돌아가므로 그
    #     이후 금리가 무관해진다 (BCBS d368 Annex 2).
    reset = row.get("next_reset_date")
    if str(terms["rate_type"]) == "floating" and reset is not None and not pd.isna(reset):
        reset_d = date.fromisoformat(str(reset))
        tau = year_fraction(asof_d, reset_d, str(terms["day_count"]))
        t = max((reset_d - asof_d).days / 365.25, 0.0)
        return [CashflowPoint(t, notional, notional * rate * tau)], True

    # (3) 고정금리 — 계약 상환스케줄 전량.
    mat = row["maturity_date"]
    if mat is None or pd.isna(mat):
        raise ValueError(
            f"{row['contract_id']}: 상환일정 상품인데 maturity_date가 NULL이다")
    sched = build_schedule(
        asof=asof_d, maturity=date.fromisoformat(str(mat)),
        opening_balance=notional, annual_rate=rate, amort_type=amort,
        pay_freq_per_year=int(terms["pay_freq_per_year"]),
        day_count=str(terms["day_count"]),
        grace_months=int(terms["grace_months"]),
        balloon_ratio=float(terms["balloon_ratio"]),
    )
    return ([CashflowPoint(i.t_years, i.principal, i.interest) for i in sched],
            False)


def _accumulate(points: list[CashflowPoint], bk: _Buckets, row: pd.Series,
                ) -> dict[tuple[str, int, float], list[float]]:
    """현금흐름점을 버킷별로 접는다. 키: (라벨, 순서, 중점)."""
    rate, margin_bp = float(row["coupon_rate"]), float(row["margin_bp"])
    acc: dict[tuple[str, int, float], list[float]] = {}
    for p in points:
        key = bk.assign(p.t_years)
        ex, mg = _split_margin(p.interest, rate, margin_bp)
        cur = acc.setdefault(key, [0.0, 0.0, 0.0])
        cur[0] += p.principal
        cur[1] += ex
        cur[2] += mg
    return acc


def build_contract_cashflows(
    contracts: pd.DataFrame, product_terms: pd.DataFrame,
    buckets: pd.DataFrame, *, asof: str,
) -> tuple[pd.DataFrame, _Buckets]:
    """`alm_cashflow_contract` — 행동가정 없는 감독 대사 기준선."""
    asof_d = date.fromisoformat(asof)
    bk = _Buckets(buckets)
    terms_by_code = product_terms.set_index("product_code")

    rows: list[dict] = []
    for _, row in contracts.iterrows():
        code = str(row["product_code"])
        if code not in terms_by_code.index:
            raise KeyError(
                f"{row['contract_id']}: 상품 {code!r}이 alm_product_terms에 없다 — "
                "관행을 모르는 계약의 현금흐름은 만들 수 없다")
        terms = terms_by_code.loc[code]
        points, repricing = _contract_points(row, terms, asof_d, bk.shortest_t)
        for (label, seq, t_mid), (prin, ex, mg) in _accumulate(
                points, bk, row).items():
            rows.append({
                "asof": asof, "contract_id": str(row["contract_id"]),
                "ccy": str(row["ccy"]), "side": str(row["side"]),
                "bucket": label, "seq": seq, "t_mid": t_mid,
                "principal_cf": prin, "interest_cf_ex_margin": ex,
                "margin_cf": mg, "repricing_flag": repricing,
                "is_own_equity": bool(row["is_own_equity"]),
            })
    return pd.DataFrame(rows, columns=list(CASHFLOW_CONTRACT.column_names)), bk


# ---------------------------------------------------------------- 행동 CF

def _cpr_path(sched, row: pd.Series, mult: float, scurve: pd.Series | None,
              asof_d: date) -> list[float]:
    """회차별 CPR. 기준율은 원장의 base_model이 정하고, 승수는 표준방법이다.

    CPR_i = min(1, γ_i · CPR₀)  (BCBS d368 Annex 2 Table 3)
    """
    age0 = (asof_d - date.fromisoformat(str(row["origination_date"]))).days / 30.44
    out = []
    for ins in sched:
        base = psa_cpr(age0 + ins.t_years * 12.0)
        if scurve is not None:
            # S-curve는 기준율을 **대체**한다 — 인센티브에서 직접 CPR을 만든다.
            # 주의: 이때도 표준방법 승수를 곱한다. 원래 S-curve의 시나리오
            # 반응은 refi_rate가 충격곡선을 따라 움직여서 나와야 하는데,
            # curve.py가 없어 refi_rate가 정적이다. 그대로 두면 S-curve가
            # 시나리오에 무반응이 되므로 잠정적으로 승수를 유지한다 —
            # curve.py 연결 시 이중계상 여부를 재검토해야 한다.
            inc = float(row["coupon_rate"]) - float(scurve["refi_rate"])
            if bool(scurve["deduct_prepay_fee"]) and not pd.isna(
                    row.get("prepay_fee_rate")):
                inc -= effective_prepay_fee_rate(
                    float(row["prepay_fee_rate"]),
                    float(row["prepay_fee_term_years"]), ins.t_years)
            base = scurve_ri(inc, float(scurve["coef_a"]), float(scurve["coef_b"]),
                             float(scurve["coef_c"]), float(scurve["coef_d"]))
        out.append(min(1.0, mult * base))
    return out


def _resolve_scurve(scurve_param: pd.DataFrame | None,
                    ) -> tuple[pd.Series | None, list[ParamWarning]]:
    """S-curve 계수 원장 해석. 비어 있거나 미사용이면 표준방법 승수로 간다."""
    warns: list[ParamWarning] = []
    if scurve_param is None or scurve_param.empty:
        return None, warns
    r = scurve_param.iloc[0]
    if not bool(r["enabled"]):
        return None, warns
    need = ["coef_a", "coef_b", "coef_c", "coef_d", "refi_rate"]
    missing = [c for c in need if c not in r.index or pd.isna(r[c])]
    if missing:
        warns.append(ParamWarning(
            "CPR", str(r["product_group"]), ",".join(missing),
            "S-curve가 enabled인데 계수가 비어 있다 — 표준방법 승수로 폴백"))
        return None, warns
    return r, warns


def build_behavioural_cashflows(
    contracts: pd.DataFrame, product_terms: pd.DataFrame, bk: _Buckets, *,
    asof: str, contract_cf: pd.DataFrame,
    behaviour_param: pd.DataFrame, scenario_mult: pd.DataFrame,
    nmd_param: pd.DataFrame, scurve_param: pd.DataFrame | None = None,
    scenarios: tuple[str, ...] = CF_SCENARIOS,
) -> tuple[pd.DataFrame, list[ParamWarning]]:
    """`alm_cashflow_behavioural` — 3종 행동모형 적용.

    행동모형은 계약별 `behaviour_class`가 정한다(`alm_product_terms`). 그리고
    **조기상환은 고정금리에만** 건다 — 변동금리는 리프라이싱으로 슬로팅되므로
    조기상환의 EVE 효과가 정의상 사라진다(BCBS d368 Annex 2).
    """
    asof_d = date.fromisoformat(asof)
    terms_by_code = product_terms.set_index("product_code")
    nmd_by_cat = nmd_param.set_index("nmd_category")
    param_set = (str(behaviour_param["param_set_id"].iloc[0])
                 if not behaviour_param.empty else "NONE")
    scurve, warns = _resolve_scurve(scurve_param)

    # TDRR 기준율 — 원장이 비어 있으면 조정을 건너뛴다.
    tdrr_rows = behaviour_param[behaviour_param["model"] == "TDRR"]
    tdrr0 = (float(tdrr_rows["base_rate_annual"].iloc[0])
             if not tdrr_rows.empty
             and not pd.isna(tdrr_rows["base_rate_annual"].iloc[0]) else None)
    if tdrr0 is None:
        warns.append(ParamWarning(
            "TDRR", "term_deposit", "base_rate_annual",
            "중도해지 기준율 미확정(NULL) — 정기예금 행동조정 미적용. "
            "BCBS d368은 TDRR₀을 주지 않으며 은행 자체추정 + 감독승인이 필요하다"))

    # 계약 CF 합계를 (계약, 버킷) → 총액 dict로 미리 접는다. MultiIndex .loc를
    # 3만 번 도는 것보다 빠르고, 무엇보다 키 부재를 예외가 아니라 값으로 다룬다.
    ccf_total: dict[tuple[str, str], float] = {
        (str(c), str(b)): float(p + e + m)
        for c, b, p, e, m in zip(
            contract_cf["contract_id"], contract_cf["bucket"],
            contract_cf["principal_cf"], contract_cf["interest_cf_ex_margin"],
            contract_cf["margin_cf"])}

    rows: list[dict] = []
    for _, row in contracts.iterrows():
        terms = terms_by_code.loc[str(row["product_code"])]
        bclass = str(terms["behaviour_class"])
        if bclass == "none":
            continue
        cid = str(row["contract_id"])

        for sc in scenarios:
            model, points = None, None
            if bclass == "nmd":
                cat = row.get("counterparty_type")
                if cat is None or pd.isna(cat) or cat not in nmd_by_cat.index:
                    warns.append(ParamWarning(
                        "NMD", cid, "counterparty_type",
                        "NMD 범주를 alm_nmd_param에서 찾지 못했다 — 슬로팅 미적용"))
                    continue
                p = nmd_by_cat.loc[cat]
                # 코어 분해는 시나리오 함수가 아니다(BCBS 표준방법) — 6벌이
                # 같은 값이지만 grain을 균일하게 두어 소비자가 조인만으로 쓴다.
                points, _achieved, w = nmd_slotting(
                    float(row["notional"]),
                    core_ratio=float(p["core_ratio"]),
                    core_ratio_cap=float(p["core_ratio_cap"]),
                    avg_maturity_years=float(p["avg_maturity_years"]),
                    avg_maturity_cap_years=float(p["avg_maturity_cap_years"]),
                    buckets=bk.frame, stable_ratio=p["stable_ratio"], scope=cid)
                model = "NMD"
                warns.extend(w)
            else:
                if str(terms["rate_type"]) != "fixed":
                    continue        # 변동금리는 리프라이싱 슬로팅이 이미 정답
                sched = build_schedule(
                    asof=asof_d,
                    maturity=date.fromisoformat(str(row["maturity_date"])),
                    opening_balance=float(row["notional"]),
                    annual_rate=float(row["coupon_rate"]),
                    amort_type=str(terms["amort_type"]),
                    pay_freq_per_year=int(terms["pay_freq_per_year"]),
                    day_count=str(terms["day_count"]),
                    grace_months=int(terms["grace_months"]),
                    balloon_ratio=float(terms["balloon_ratio"]))
                mdl = "CPR" if bclass == "prepayment" else "TDRR"
                mult = 1.0
                if sc != "base":
                    mult, mw = scenario_multiplier(scenario_mult, mdl, sc)
                    if mw is not None:
                        warns.append(mw)
                if bclass == "prepayment":
                    points = apply_prepayment(
                        sched, annual_rate=float(row["coupon_rate"]),
                        cpr_path=_cpr_path(sched, row, mult, scurve, asof_d))
                    model = "CPR"
                else:
                    if tdrr0 is None:
                        continue
                    points = apply_early_redemption(
                        sched, annual_rate=float(row["coupon_rate"]),
                        tdrr=min(1.0, mult * tdrr0),
                        shortest_t_years=bk.shortest_t)
                    model = "TDRR"

            for (label, seq, t_mid), (prin, ex, mg) in _accumulate(
                    points, bk, row).items():
                # 행동 − 계약 (총액 기준). 계약 CF가 그 버킷에 없으면 0에서 시작한
                # 것이므로 조정액은 행동 CF 전액이다.
                adj = (prin + ex + mg) - ccf_total.get((cid, label), 0.0)
                rows.append({
                    "asof": asof, "scenario": sc, "contract_id": cid,
                    "ccy": str(row["ccy"]), "side": str(row["side"]),
                    "bucket": label, "seq": seq, "t_mid": t_mid,
                    "principal_cf": prin, "interest_cf_ex_margin": ex,
                    "margin_cf": mg, "behaviour_model": model,
                    "adjustment_cf": adj, "param_set_id": param_set,
                })
    # 같은 원인의 경고가 계약·시나리오마다 반복된다 — 중복을 접어야 "무엇이
    # 비어 있는가"가 읽힌다. dataclass가 frozen이므로 집합으로 접을 수 있다.
    deduped = list(dict.fromkeys(warns))
    return (pd.DataFrame(rows, columns=list(CASHFLOW_BEHAVIOURAL.column_names)),
            deduped)


# ---------------------------------------------------------------- 버킷 집계

def _aggregate(df: pd.DataFrame, asof: str, scenario: str,
               basis: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=list(CASHFLOW_BUCKET.column_names))
    g = (df.groupby(["ccy", "side", "bucket", "seq", "t_mid"], as_index=False)
           .agg(principal_cf=("principal_cf", "sum"),
                interest_cf_ex_margin=("interest_cf_ex_margin", "sum"),
                margin_cf=("margin_cf", "sum"),
                n_contracts=("contract_id", "nunique")))
    g["asof"], g["scenario"], g["basis"] = asof, scenario, basis
    g["total_cf"] = (g["principal_cf"] + g["interest_cf_ex_margin"]
                     + g["margin_cf"])
    return g[list(CASHFLOW_BUCKET.column_names)]


def build_cashflows(
    contracts: pd.DataFrame, *, asof: str,
    product_terms: pd.DataFrame, buckets: pd.DataFrame,
    behaviour_param: pd.DataFrame, scenario_mult: pd.DataFrame,
    nmd_param: pd.DataFrame, scurve_param: pd.DataFrame | None = None,
    scenarios: tuple[str, ...] = CF_SCENARIOS,
) -> CashflowResult:
    """엔진 진입점 — 계약원장 + 계수원장 → 현금흐름 원장 3장.

    파라미터는 전부 원장 인자다. 함수 기본값에 계수가 하나도 없는 것이 이
    시그니처의 요점이다 — 숨은 기본값은 화면에도 검증에도 나타나지 않는다.
    """
    contract_cf, bk = build_contract_cashflows(
        contracts, product_terms, buckets, asof=asof)
    behavioural_cf, warns = build_behavioural_cashflows(
        contracts, product_terms, bk, asof=asof, contract_cf=contract_cf,
        behaviour_param=behaviour_param, scenario_mult=scenario_mult,
        nmd_param=nmd_param, scurve_param=scurve_param, scenarios=scenarios)

    # 자기자본 제외 (BCBS d368 §132). 제외액을 돌려주어 조용히 사라지지 않게 한다.
    eq = contract_cf[contract_cf["is_own_equity"]]
    cf_no_eq = contract_cf[~contract_cf["is_own_equity"]]
    eq_amount = float(eq["principal_cf"].sum())

    # 행동조정 기준 = 계약 CF에서 행동 대상 계약을 빼고 행동 CF를 얹은 것.
    behaved_ids = set(behavioural_cf["contract_id"].unique())
    kept = cf_no_eq[~cf_no_eq["contract_id"].isin(behaved_ids)]

    parts = [_aggregate(cf_no_eq, asof, sc, "계약") for sc in scenarios]
    for sc in scenarios:
        beh = behavioural_cf[behavioural_cf["scenario"] == sc]
        parts.append(_aggregate(pd.concat([kept, beh], ignore_index=True),
                                asof, sc, "행동조정"))
    bucket = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(
        columns=list(CASHFLOW_BUCKET.column_names))

    return CashflowResult(
        contract=contract_cf, behavioural=behavioural_cf, bucket=bucket,
        warnings=warns, own_equity_excluded=eq_amount,
        n_beyond_last_bucket=bk.n_beyond)
