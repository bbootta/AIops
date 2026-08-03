"""전 축 동시 충격 위기상황분석 엔진.

한 (시나리오, 분기)에서 14개 축을 동시에 적용하고 **모든 중간값**을 남긴다.
신용만 충격하던 기존 경로와 달리, 시장·운영·유동성·수익이 함께 움직이며
자본은 증분 ECL이 아니라 **세후이익 변화**로 롤포워드된다 — 충당금 전입이
이익에 이미 들어 있으므로 ECL을 따로 빼면 이중계상이 된다.

전이 경로:

    거시·축 → 신용 파라미터(PD·LGD·EAD·LTV·등급) → 신용 RWA(IRB·SA)
            → 시장(포지션 손익·시장 RWA·ΔEVE·ΔNII)
            → 운영(손실·ILM·운영 RWA)
            → 유동성(HQLA·유출·LCR)
            → 손익(이자·수수료·비용·충당금·운영손실·시장손익·세금)
            → 자본(CET1 롤포워드) → RWA 합계·산출하한 → 비율 → 판정

모든 근사·가정은 상수로 뽑아 근거를 적었다. 근사인 것을 정밀한 척하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from risk_lib.capital.bis import CapitalStack, compute_bis_ratios
from risk_lib.capital.market_risk import compute_market_risk_rwa
from risk_lib.capital.op_risk import BusinessIndicator, compute_op_risk_rwa
from risk_lib.capital.output_floor import FULLY_LOADED_FLOOR, apply_output_floor
from risk_lib.capital.rwa_irb import compute_rwa_irb
from risk_lib.capital.rwa_sa import compute_rwa_sa, standardised_rwa_total
from risk_lib.provisioning.ecl import compute_ecl
from risk_lib.stress.axes import shocks_at
from risk_lib.stress.path import DEFAULT_STRESS_PATHS
from risk_lib.stress.scenario import Scenario

# 외부등급 하향 사다리 — 인접 등급으로만 내려간다.
RATING_LADDER = ("AAA-AA", "A", "BBB", "BB", "B", "CCC", "UNRATED")

# 트레이딩·은행계정 민감도 근사. 완전한 재평가는 범위 외이며, 듀레이션 근사임을
# 명시한다 (MAR21 SBM 재산출로 교체가 전제).
IR_DURATION_YEARS = 3.0          # 트레이딩북 금리 포지션 평균 듀레이션
CS_DURATION_YEARS = 4.0          # 신용물 스프레드 듀레이션
# 시장리스크 위험계수 스트레스 배수의 정규화 기준 — 이 크기 충격에서 배수 1.0 증가.
MKT_NORMALISER = {"interest_rate": 100.0, "credit_spread": 100.0,
                  "equity": 0.10, "fx": 0.10}
LCR_INFLOW_CAP = 0.75            # LCR40.61 총유출 대비 유입 인식 상한
TAX_RATE = 0.242                 # prudential.financials와 같은 실효세율
INTEREST_SHARE_OF_REVENUE = 0.80  # 영업수익 중 이자수익 비중 (나머지 수수료)


@dataclass(frozen=True)
class StressBooks:
    """전 축 충격에 필요한 기준 상태. 파이프라인이 한 번 만들어 넘긴다."""
    irb: pd.DataFrame                 # 내부등급법 대상 (pd/lgd/ead/maturity)
    sa: pd.DataFrame                  # 표준방법 대상 (rating/ltv/ead/past_due)
    full: pd.DataFrame                # 산출하한용 전체 포트폴리오
    capital: CapitalStack
    market_positions: pd.DataFrame    # risk_class, net_position
    bi: BusinessIndicator
    op_losses_10y: float
    op_loss_annual: float
    repricing: pd.DataFrame           # bucket, t_mid, assets, liabilities, gap
    hqla: dict[str, float]
    lcr_outflows: pd.DataFrame        # category, amount, runoff, outflow
    lcr_inflows: pd.DataFrame         # category, amount, rate, inflow
    revenue: float
    operating_cost: float
    credit_securities: float          # 스프레드 민감 보유물 (L2A + L2B)
    ccr_rwa: float = 0.0              # 거래상대방신용리스크 (SA-CCR + CVA)
    # 구조화(집합투자증권 CRE60 · 유동화 CRE40) — 분모에 들어간 값 그대로.
    # 충격은 받지 않지만(등급 하락에 따른 ERBA 위험가중치 상승 미모형화)
    # **합계에는 반드시 들어가야** 한다. 빼면 심도 0의 기준 상태가 실제
    # 기준 상태를 재현하지 못해 충격 크기 자체를 믿을 수 없게 된다.
    structured_rwa: float = 0.0
    structured_rwa_standardised: float = 0.0
    undrawn_share: float = 0.0        # EAD 대비 미인출 비율
    sa_bucket_by_grade: dict = field(default_factory=dict)


@dataclass(frozen=True)
class StressPoint:
    """한 (시나리오, 분기)의 전 중간값."""
    scenario: str
    quarter: str
    q_index: int
    severity: float
    shocks: dict[str, float]
    values: dict[str, float]

    def __getitem__(self, key: str) -> float:
        return self.values[key]


def _downgrade(ratings: np.ndarray, notches: float) -> np.ndarray:
    """등급을 정수 notch만큼 내린다. 소수 notch는 내림 — 반올림으로 올리면
    충격이 없는 분기에도 등급이 떨어진다."""
    n = int(np.floor(notches))
    if n <= 0:
        return ratings
    idx = {r: i for i, r in enumerate(RATING_LADDER)}
    last = len(RATING_LADDER) - 2      # UNRATED로는 강등하지 않는다
    return np.array([
        RATING_LADDER[min(idx.get(str(r), last) + n, last)] for r in ratings
    ], dtype=object)


def _stressed_full(books: StressBooks, sh: dict[str, float],
                   sc: Scenario) -> pd.DataFrame:
    """산출하한 분모용 — 전체 포트폴리오에 같은 충격을 적용한다.

    내부등급법 대상은 충격 PD로 등급을 다시 매기고(표준방법 버킷이 함께
    내려간다), 표준방법 대상은 등급 하향·LTV 상승을 적용한다.
    """
    from risk_lib.models.rating import pd_to_rating

    f = books.full.copy()
    irb_classes = set(books.irb["asset_class"].unique())
    m = f["asset_class"].isin(irb_classes).to_numpy()
    if m.any() and "pd" in f.columns:
        pd_str = sc.stress_pd(f.loc[m, "pd"].to_numpy(dtype=float))
        f.loc[m, "pd"] = pd_str
        if "grade" in f.columns:
            f.loc[m, "grade"] = [pd_to_rating(float(x)).grade for x in pd_str]
    if "rating" in f.columns:
        f.loc[~m, "rating"] = _downgrade(f.loc[~m, "rating"].to_numpy(),
                                         sh["migration"])
    if "ltv" in f.columns:
        f["ltv"] = f["ltv"] / max(1e-9, 1.0 - sh["collateral"])
    f["ead"] = f["ead"].to_numpy(dtype=float) * (
        1.0 + sh["ccf"] * books.undrawn_share)
    return f


def evaluate_point(books: StressBooks, severity: float, *,
                   scenario: str = "", quarter: str = "", q_index: int = 0,
                   base: dict[str, float] | None = None,
                   buffers: dict[str, float] | None = None,
                   eir: float = 0.05,
                   floor: float = FULLY_LOADED_FLOOR) -> StressPoint:
    """한 심도에서 전 축을 동시 적용하고 모든 중간값을 낸다.

    `base`는 심도 0 결과(values). 자본 롤포워드가 **이익 변화**를 쓰므로
    기준 이익이 필요하다. None이면 내부에서 심도 0을 먼저 푼다.
    """
    if base is None and severity != 0.0:
        base = evaluate_point(books, 0.0, buffers=buffers, eir=eir,
                              floor=floor).values

    sh = shocks_at(severity)
    v: dict[str, float] = {}

    # ---------------------------------------------------------- 신용 파라미터
    sc = Scenario(name=scenario or f"s={severity:.4f}", pd_multiplier=1.0,
                  lgd_addon=sh["lgd_addon"], gdp_shock=sh["gdp"])
    irb = books.irb.copy()
    ead0 = irb["ead"].to_numpy(dtype=float)
    w = ead0
    v["pd_base"] = float((irb["pd"].to_numpy(float) * w).sum() / w.sum())
    v["lgd_base"] = float((irb["lgd"].to_numpy(float) * w).sum() / w.sum())
    v["ead_base"] = float(ead0.sum())

    pd_str = sc.stress_pd(irb["pd"].to_numpy(dtype=float))
    lgd_after_addon = sc.stress_lgd(irb["lgd"].to_numpy(dtype=float))
    # 담보가치 h만큼 하락 → 회수분(1−LGD)의 h만큼이 손실로 넘어온다.
    lgd_str = np.clip(lgd_after_addon + sh["collateral"] * (1 - lgd_after_addon),
                      0.0, 1.0)
    # 미인출 약정 인출 — 미인출 잔액에만 적용한다.
    ead_uplift = 1.0 + sh["ccf"] * books.undrawn_share
    irb["pd"], irb["lgd"] = pd_str, lgd_str
    irb["ead"] = ead0 * ead_uplift

    v["pd_stressed"] = float((pd_str * w).sum() / w.sum())
    v["lgd_stressed"] = float((lgd_str * w).sum() / w.sum())
    v["ead_stressed"] = float(irb["ead"].sum())
    v["ead_uplift"] = ead_uplift

    # ---------------------------------------------------------- 신용 RWA
    v["rwa_irb"] = float(compute_rwa_irb(irb)["rwa"].sum())
    v["ecl"] = float(compute_ecl(irb, eir=eir)["ecl"].sum())

    sa = books.sa.copy()
    if len(sa):
        sa["rating"] = _downgrade(sa["rating"].to_numpy(), sh["migration"])
        if "ltv" in sa.columns:
            # 담보가치가 h 하락하면 LTV는 1/(1−h)배가 된다.
            sa["ltv"] = sa["ltv"] / max(1e-9, 1.0 - sh["collateral"])
        sa["ead"] = sa["ead"].to_numpy(dtype=float) * ead_uplift
        v["rwa_sa"] = float(compute_rwa_sa(sa)["rwa"].sum())
    else:
        v["rwa_sa"] = 0.0
    v["rating_notches"] = float(np.floor(sh["migration"]))

    # 거래상대방신용리스크 — 등급에 연동되므로 표준방법 신용 RWA 변화율을 대용
    # 배수로 쓴다. PFE 확대(변동성 상승에 따른 add-on 증가)는 별도 모형이 필요해
    # 반영하지 않으며, 그 사실을 근거에 남긴다. 심도 0에서는 배수가 정확히 1이라
    # 기준 상태가 재현된다.
    sa_base = (base or v).get("rwa_sa", v["rwa_sa"]) or 1.0
    v["ccr_multiplier"] = v["rwa_sa"] / sa_base if sa_base else 1.0
    v["rwa_ccr"] = books.ccr_rwa * v["ccr_multiplier"]

    # ---------------------------------------------------------- 시장
    pos = books.market_positions.copy()
    mkt_shock = {"interest_rate": sh["ir_parallel"],
                 "credit_spread": sh["credit_spread"],
                 "equity": sh["equity"], "fx": sh["fx"]}
    if len(pos):
        mult = pos["risk_class"].map(
            lambda rc: 1.0 + abs(mkt_shock.get(rc, 0.0))
            / MKT_NORMALISER.get(rc, 1.0)).astype(float)
        from risk_lib.capital.market_risk import DEFAULT_RISK_WEIGHTS
        pos["risk_weight"] = [DEFAULT_RISK_WEIGHTS[rc] * m
                              for rc, m in zip(pos["risk_class"], mult)]
        mres = compute_market_risk_rwa(pos)
        v["rwa_market"] = float(mres.rwa)
        p = dict(zip(pos["risk_class"], pos["net_position"].astype(float)))
    else:
        v["rwa_market"], p = 0.0, {}

    dy = sh["ir_parallel"] / 10_000.0
    ds = sh["credit_spread"] / 10_000.0
    v["pnl_ir"] = -abs(p.get("interest_rate", 0.0)) * dy * IR_DURATION_YEARS
    v["pnl_cs"] = -books.credit_securities * ds * CS_DURATION_YEARS
    v["pnl_equity"] = -abs(p.get("equity", 0.0)) * sh["equity"]
    v["pnl_fx"] = -abs(p.get("fx", 0.0)) * sh["fx"]
    v["trading_pnl"] = (v["pnl_ir"] + v["pnl_cs"] + v["pnl_equity"]
                        + v["pnl_fx"])

    # 은행계정 금리리스크 — 재설정 갭 사다리에 평행충격을 적용
    rep = books.repricing
    gap = rep["gap"].to_numpy(dtype=float)
    tmid = rep["t_mid"].to_numpy(dtype=float)
    v["delta_eve"] = float(-(gap * tmid * dy).sum())
    within_1y = tmid <= 1.0
    v["delta_nii"] = float((gap[within_1y] * dy).sum())

    # ---------------------------------------------------------- 운영
    op = compute_op_risk_rwa(books.bi,
                             books.op_losses_10y * (1.0 + sh["op_loss"]))
    v["op_ilm"] = float(op.ilm)
    v["rwa_op"] = float(op.rwa)
    v["op_loss_annual"] = books.op_loss_annual * (1.0 + sh["op_loss"])

    # ---------------------------------------------------------- 유동성
    hqla_l1 = books.hqla.get("level_1", 0.0)
    hqla_l2a = books.hqla.get("level_2a", 0.0) * 0.85
    hqla_l2b = books.hqla.get("level_2b", 0.0) * 0.50
    hqla = (hqla_l1 + hqla_l2a + hqla_l2b) * (1.0 - sh["hqla_haircut"])
    out = books.lcr_outflows
    runoff = np.clip(out["runoff"].to_numpy(dtype=float)
                     + sh["deposit_runoff"], 0.0, 1.0)
    gross_out = float((out["amount"].to_numpy(dtype=float) * runoff).sum())
    inflow = float(books.lcr_inflows["inflow"].sum())
    inflow_capped = min(inflow, gross_out * LCR_INFLOW_CAP)
    net_out = max(gross_out - inflow_capped, 1.0)
    v["hqla"] = hqla
    v["lcr_outflow"] = gross_out
    v["lcr_net_outflow"] = net_out
    v["lcr"] = hqla / net_out

    # ---------------------------------------------------------- 손익
    interest = books.revenue * INTEREST_SHARE_OF_REVENUE * (1.0 - sh["nii"])
    fee = books.revenue * (1 - INTEREST_SHARE_OF_REVENUE) * (1.0 - sh["fee"])
    v["interest_income"] = interest
    v["fee_income"] = fee
    v["operating_cost"] = books.operating_cost
    # 충당금 전입은 기준 ECL 대비 증분이다 — 잔액 전액을 전입하면 이중계상.
    base_ecl = base["ecl"] if base else v["ecl"]
    v["provision"] = max(v["ecl"] - base_ecl, 0.0)
    v["pre_tax_income"] = (interest + fee - books.operating_cost
                           - v["provision"] - v["op_loss_annual"]
                           + v["trading_pnl"])
    v["tax"] = -max(v["pre_tax_income"], 0.0) * TAX_RATE
    v["net_income"] = v["pre_tax_income"] + v["tax"]

    # ---------------------------------------------------------- 자본
    base_ni = base["net_income"] if base else v["net_income"]
    v["earnings_delta"] = v["net_income"] - base_ni
    cet1 = books.capital.cet1 + v["earnings_delta"]
    stack = CapitalStack(cet1=cet1,
                         additional_t1=books.capital.additional_t1,
                         tier2=books.capital.tier2)
    v["cet1_base"] = float(books.capital.cet1)
    v["cet1"] = float(cet1)
    v["at1"] = float(books.capital.additional_t1)
    v["tier2"] = float(books.capital.tier2)
    v["capital_total"] = float(stack.total)

    # ---------------------------------------------------------- RWA 합계·하한
    v["rwa_structured"] = float(books.structured_rwa)
    internal = (v["rwa_irb"] + v["rwa_sa"] + v["rwa_ccr"]
                + v["rwa_market"] + v["rwa_op"] + v["rwa_structured"])
    if books.sa_bucket_by_grade and len(books.full):
        # 산출하한 분모도 충격을 받아야 한다 — 기준 상태 분모를 그대로 쓰면
        # 스트레스에서 하한이 절대 구속되지 않는 착시가 생긴다.
        std_credit = standardised_rwa_total(_stressed_full(books, sh, sc),
                                            books.sa_bucket_by_grade)
    else:
        std_credit = (internal - v["rwa_market"] - v["rwa_op"] - v["rwa_ccr"]
                      - v["rwa_structured"])
    standardised = (std_credit + v["rwa_ccr"] + v["rwa_market"] + v["rwa_op"]
                    + float(books.structured_rwa_standardised))
    fl = apply_output_floor(internal, standardised, floor)
    v["rwa_internal"] = internal
    v["rwa_standardised"] = standardised
    v["rwa_total"] = float(fl.rwa_final)
    v["floor_addon"] = float(fl.add_on)
    v["floor_binding"] = 1.0 if fl.is_binding else 0.0

    # ---------------------------------------------------------- 비율·판정
    bis = compute_bis_ratios(stack, v["rwa_total"], buffers=buffers)
    v["cet1_ratio"] = bis.cet1_ratio
    v["tier1_ratio"] = bis.tier1_ratio
    v["total_ratio"] = bis.total_ratio
    for k in ("cet1", "tier1", "total"):
        v[f"{k}_required"] = bis.required[k]
        v[f"{k}_surplus"] = bis.surplus_shortfall[k]
    binding = min(bis.surplus_shortfall, key=bis.surplus_shortfall.get)
    v["binding_index"] = float(("cet1", "tier1", "total").index(binding))
    v["binding_surplus"] = float(bis.surplus_shortfall[binding])
    v["passes"] = 1.0 if bis.passes() else 0.0
    v["lcr_passes"] = 1.0 if v["lcr"] >= 1.0 else 0.0

    return StressPoint(scenario=scenario, quarter=quarter, q_index=q_index,
                       severity=float(severity), shocks=sh, values=v)


_BINDING = ("cet1", "tier1", "total")


def run_multi_axis_path(books: StressBooks, *, quarters: list[str],
                        paths=None, buffers: dict[str, float] | None = None,
                        eir: float = 0.05,
                        floor: float = FULLY_LOADED_FLOOR
                        ) -> tuple[pd.DataFrame, list[StressPoint]]:
    """시나리오 × 분기 경로. (요약 DataFrame, 전 중간값 포인트) 반환."""
    if paths is None:
        paths = DEFAULT_STRESS_PATHS
    base = evaluate_point(books, 0.0, buffers=buffers, eir=eir,
                          floor=floor).values
    rows, points = [], []
    n = len(quarters)
    for path in paths:
        for i, (q, s) in enumerate(zip(quarters, path.severities(n))):
            pt = evaluate_point(books, s, scenario=path.name, quarter=q,
                                q_index=i, base=base, buffers=buffers,
                                eir=eir, floor=floor)
            points.append(pt)
            v = pt.values
            rows.append({
                "scenario": path.name, "quarter": q, "q_index": i,
                "severity": s,
                "gdp_shock": pt.shocks["gdp"],
                "lgd_addon": pt.shocks["lgd_addon"],
                "rwa_total": v["rwa_total"],
                "rwa_irb": v["rwa_irb"], "rwa_sa": v["rwa_sa"],
                "rwa_ccr": v["rwa_ccr"],
                "rwa_market": v["rwa_market"], "rwa_op": v["rwa_op"],
                "floor_binding": bool(v["floor_binding"]),
                "ecl": v["ecl"], "provision": v["provision"],
                "trading_pnl": v["trading_pnl"],
                "op_loss": v["op_loss_annual"],
                "delta_eve": v["delta_eve"], "delta_nii": v["delta_nii"],
                "net_income": v["net_income"],
                "lcr": v["lcr"],
                "cet1_ratio": v["cet1_ratio"],
                "tier1_ratio": v["tier1_ratio"],
                "total_ratio": v["total_ratio"],
                "cet1_surplus": v["cet1_surplus"],
                "binding": _BINDING[int(v["binding_index"])],
                "binding_surplus": v["binding_surplus"],
                "passes": bool(v["passes"]),
            })
    return pd.DataFrame(rows), points


def solve_critical_severity(books: StressBooks, *, metric: str = "cet1",
                            target_ratio: float, buffers=None,
                            eir: float = 0.05,
                            floor: float = FULLY_LOADED_FLOOR,
                            max_severity: float = 10.0,
                            tol: float = 1e-4, max_iter: int = 60
                            ) -> tuple[float, bool]:
    """비율이 target으로 떨어지는 심도를 이분법으로 찾는다.

    전 축이 동시에 움직이므로 신용만 볼 때보다 임계 심도가 낮게 나온다 —
    그것이 통합위기상황분석의 요점이다.
    """
    base = evaluate_point(books, 0.0, buffers=buffers, eir=eir,
                          floor=floor).values
    key = f"{metric}_ratio"

    def ratio_at(s: float) -> float:
        return evaluate_point(books, s, base=base, buffers=buffers, eir=eir,
                              floor=floor).values[key]

    if ratio_at(max_severity) > target_ratio:
        return max_severity, True          # 최대 심도에서도 견딤
    lo, hi = 0.0, max_severity
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        if ratio_at(mid) > target_ratio:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    return 0.5 * (lo + hi), False
