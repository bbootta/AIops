"""순자본비율(NCR) — 금융투자업자 건전성자본 산출 (RYNTA PRD-NCR).

    순자본비율 = (영업용순자본 − 총위험액) / 필요유지자기자본 × 100%

2016년 개편된 신 NCR 체계다. 舊 NCR(영업용순자본/총위험액)과 분모·의미가
다르므로 시계열 비교 시 체계를 반드시 명시해야 한다.

구성:
  영업용순자본 = 자산총액 − 부채총액 − 차감항목 + 가산항목
    - 차감: 고정자산·특수관계인채권·임차보증금 등 즉시 현금화 곤란 자산
    - 가산: 후순위차입금·대손충당금 등 손실흡수 가능 항목
  총위험액   = 시장위험액 + 신용위험액 + 운영위험액
  필요유지자기자본 = 인가업무 단위별 법정 필요자기자본의 합

적기시정조치(금융투자업규정 제3-26조): 100% 미만 경영개선권고 · 50% 미만
경영개선요구 · 0% 미만 경영개선명령.

**주의**: 본 모듈은 승인된 산출 사양이 아니라 구조를 구현한 것이다. 인가업무
단위별 필요자기자본, 차감·가산 항목의 세부 인정범위, 위험액 산출방법은 기관
승인 사양과 독립검증으로 교체가 전제다 (RYNTA 통제원칙).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from risk_lib.references import (
    NCR_MIN, NCR_PROMPT_ACTION, NCR_EARLY_WARNING,
    NCR_DEDUCTION_ITEMS, NCR_ADDITION_ITEMS,
)


# 인가업무 단위별 **법정 최저자기자본** (진입요건, 원 단위).
# 필요유지자기자본은 이 값의 100분의 70이다 — 두 개념을 혼동하면 분모가
# 43% 과대되어 순자본비율이 그만큼 낮게 나온다.
MAINTENANCE_FACTOR = 0.70          # 금융투자업규정 제3-6조

LICENSE_MINIMUM_CAPITAL: dict[str, float] = {
    "투자매매업(인수)":       50_000_000_000.0,
    "투자매매업(자기매매)":   20_000_000_000.0,
    "투자중개업":             3_000_000_000.0,
    "집합투자업":             8_000_000_000.0,
    "신탁업":                25_000_000_000.0,
    "투자자문업":               250_000_000.0,
}


@dataclass
class NetOperatingCapital:
    """영업용순자본 — 자산 − 부채 − 차감 + 가산."""
    total_assets: float
    total_liabilities: float
    deductions: pd.DataFrame        # item, amount
    additions: pd.DataFrame         # item, amount
    net_worth: float                # 자산 − 부채
    total_deduction: float
    total_addition: float
    net_operating_capital: float


@dataclass
class TotalRisk:
    """총위험액 — 시장 + 신용 + 운영."""
    by_component: pd.DataFrame      # component, amount, method
    market_risk: float
    credit_risk: float
    operational_risk: float
    total: float


@dataclass
class NCRResult:
    noc: NetOperatingCapital
    risk: TotalRisk
    required_capital: float             # 필요유지자기자본
    licenses: pd.DataFrame              # license, requirement
    surplus: float                      # 영업용순자본 − 총위험액
    ncr: float                          # 순자본비율 (배수 — 1.00 = 100%)
    action: str                         # 적기시정조치 등급 또는 "해당없음"
    early_warning: bool
    legacy_ncr: float = field(default=0.0)   # 舊 NCR (영업용순자본/총위험액)

    def passes(self) -> bool:
        return self.ncr >= NCR_MIN


# ---------------------------------------------------------------- 구성요소

def compute_net_operating_capital(
    total_assets: float,
    total_liabilities: float,
    *,
    deductions: dict[str, float] | None = None,
    additions: dict[str, float] | None = None,
) -> NetOperatingCapital:
    """영업용순자본 = (자산 − 부채) − 차감항목 + 가산항목.

    미기재 차감·가산 항목은 0으로 두되, 표에는 전 항목을 남겨 무엇이
    반영되지 않았는지 보이게 한다 (누락과 0원을 구분할 수 있어야 한다).
    """
    if total_assets < 0 or total_liabilities < 0:
        raise ValueError("자산·부채는 음수일 수 없다")
    deductions = deductions or {}
    additions = additions or {}
    unknown = (set(deductions) - set(NCR_DEDUCTION_ITEMS)) | \
              (set(additions) - set(NCR_ADDITION_ITEMS))
    if unknown:
        raise ValueError(f"규정 외 차감·가산 항목: {sorted(unknown)}")

    ded = pd.DataFrame({"item": list(NCR_DEDUCTION_ITEMS),
                        "amount": [float(deductions.get(i, 0.0))
                                   for i in NCR_DEDUCTION_ITEMS]})
    add = pd.DataFrame({"item": list(NCR_ADDITION_ITEMS),
                        "amount": [float(additions.get(i, 0.0))
                                   for i in NCR_ADDITION_ITEMS]})
    if (ded["amount"] < 0).any() or (add["amount"] < 0).any():
        raise ValueError("차감·가산 항목은 음수일 수 없다 (부호 규약 위반)")

    net_worth = total_assets - total_liabilities
    d, a = float(ded["amount"].sum()), float(add["amount"].sum())
    return NetOperatingCapital(
        total_assets=total_assets, total_liabilities=total_liabilities,
        deductions=ded, additions=add, net_worth=net_worth,
        total_deduction=d, total_addition=a,
        net_operating_capital=net_worth - d + a,
    )


def compute_total_risk(market_risk: float, credit_risk: float,
                       operational_risk: float,
                       *, methods: dict[str, str] | None = None) -> TotalRisk:
    """총위험액 = 시장 + 신용 + 운영 위험액 (단순합 — 분산효과 미인정)."""
    vals = {"시장위험액": market_risk, "신용위험액": credit_risk,
            "운영위험액": operational_risk}
    if any(v < 0 for v in vals.values()):
        raise ValueError("위험액은 음수일 수 없다")
    methods = methods or {}
    df = pd.DataFrame({
        "component": list(vals),
        "amount": [float(v) for v in vals.values()],
        "method": [methods.get(k, "—") for k in vals],
    })
    return TotalRisk(by_component=df, market_risk=float(market_risk),
                     credit_risk=float(credit_risk),
                     operational_risk=float(operational_risk),
                     total=float(sum(vals.values())))


def required_capital(licenses: list[str] | dict[str, float]
                     ) -> tuple[float, pd.DataFrame]:
    """필요유지자기자본 = Σ (인가업무 단위별 최저자기자본 × 70%).

    dict를 주면 그 값을 **최저자기자본**으로 보고 동일하게 70%를 적용한다.
    분모가 0이나 음수가 되면 비율의 부호가 뒤집혀 자본부족 회사가 통과로
    표시되므로, 모든 값을 양수로 강제한다.
    """
    if isinstance(licenses, dict):
        table = dict(licenses)
    else:
        unknown = set(licenses) - set(LICENSE_MINIMUM_CAPITAL)
        if unknown:
            raise ValueError(f"미등록 인가업무 단위: {sorted(unknown)}")
        table = {lic: LICENSE_MINIMUM_CAPITAL[lic] for lic in licenses}
    if not table:
        raise ValueError("인가업무 단위가 없다 — 필요유지자기자본 분모가 0")
    bad = {k: v for k, v in table.items() if not (float(v) > 0)}
    if bad:
        raise ValueError(
            f"최저자기자본은 양수여야 한다 (분모 부호 역전 방지): {sorted(bad)}")

    df = pd.DataFrame({
        "license": list(table),
        "minimum_capital": [float(v) for v in table.values()],
    })
    df["requirement"] = df["minimum_capital"] * MAINTENANCE_FACTOR
    total = float(df["requirement"].sum())
    if total <= 0:
        raise ValueError("필요유지자기자본 합계가 비양수 — 산출 불가")
    return total, df


def prompt_action_grade(ncr: float) -> str:
    """적기시정조치 등급 — 낮은 임계부터 확인해 가장 강한 조치를 반환."""
    for grade in ("경영개선명령", "경영개선요구", "경영개선권고"):
        if ncr < NCR_PROMPT_ACTION[grade]:
            return grade
    return "해당없음"


def compute_ncr(
    total_assets: float,
    total_liabilities: float,
    *,
    market_risk: float,
    credit_risk: float,
    operational_risk: float,
    licenses: list[str] | dict[str, float],
    deductions: dict[str, float] | None = None,
    additions: dict[str, float] | None = None,
    risk_methods: dict[str, str] | None = None,
) -> NCRResult:
    """순자본비율 = (영업용순자본 − 총위험액) / 필요유지자기자본."""
    noc = compute_net_operating_capital(
        total_assets, total_liabilities,
        deductions=deductions, additions=additions)
    risk = compute_total_risk(market_risk, credit_risk, operational_risk,
                              methods=risk_methods)
    req, lic_df = required_capital(licenses)

    surplus = noc.net_operating_capital - risk.total
    ncr = surplus / req
    legacy = (noc.net_operating_capital / risk.total) if risk.total > 0 else float("inf")
    return NCRResult(
        noc=noc, risk=risk, required_capital=req, licenses=lic_df,
        surplus=surplus, ncr=ncr,
        action=prompt_action_grade(ncr),
        early_warning=ncr < NCR_EARLY_WARNING,
        legacy_ncr=legacy,
    )


# ---------------------------------------------------------------- 데모 합성

def synthesise_securities_firm(result, *, seed: int = 42) -> dict:
    """은행 포트폴리오 기반 합성 증권사 재무구조 — **예시용**.

    하니스의 기본 포트폴리오는 은행 북이므로, NCR 산출 구조를 보이기 위해
    자산 규모를 축소 스케일링해 증권사 형태로 변환한다. 실제 증권사 재무제표가
    아니며 규제 제출용으로 쓸 수 없다.
    """
    cap = result.meta["capital"]
    return synthesise_securities_firm_from_parts(
        float(cap.total), float(result.portfolio_summary["ead"].sum()),
        float(result.ecl["total"]), seed=seed)


def synthesise_securities_firm_from_parts(total_capital: float, total_ead: float,
                                          ecl_total: float, *,
                                          seed: int = 42) -> dict:
    """`synthesise_securities_firm` 의 부품 버전. 파이프라인이 결과 객체를 다
    조립하기 전에 같은 입력으로 부른다. 두 함수가 다른 수를 내면 화면과 2선이
    갈라지므로, 위 함수는 이쪽으로 위임만 한다.
    """
    rng = np.random.default_rng(seed)
    ead = float(total_ead)

    # 증권사 규모로 축소 (은행 북 대비 약 12%) — 예시 스케일.
    scale = 0.12
    total_assets = ead * scale
    equity = float(total_capital) * scale
    total_liabilities = total_assets - equity

    # 차감항목 — 자기자본 대비 관행적 비중 범위에서 결정론적으로 배분.
    ded_share = {"고정자산": 0.08, "특수관계인채권": 0.02, "임차보증금": 0.03,
                 "선급금·선급비용": 0.01, "이연법인세자산": 0.02, "무형자산": 0.02}
    deductions = {k: equity * v for k, v in ded_share.items()}
    additions = {"후순위차입금": equity * 0.10,
                 "대손충당금": float(ecl_total) * scale,
                 "자산평가이익": equity * 0.01}

    # 위험액 — 시장은 트레이딩 자산 기준, 신용은 EAD 기준, 운영은 영업규모 기준.
    market_risk = total_assets * 0.030
    credit_risk = total_assets * 0.018
    operational_risk = total_assets * 0.006

    return {
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "deductions": deductions,
        "additions": additions,
        "market_risk": market_risk,
        "credit_risk": credit_risk,
        "operational_risk": operational_risk,
        "licenses": ["투자매매업(인수)", "투자매매업(자기매매)",
                     "투자중개업", "신탁업"],
        "risk_methods": {"시장위험액": "표준방법 (예시)",
                         "신용위험액": "표준방법 (예시)",
                         "운영위험액": "기초지표법 (예시)"},
    }


def compute_ncr_from_result(result, *, seed: int = 42) -> NCRResult:
    """PipelineResult에서 합성 증권사 NCR 산출 (예시, 규제 제출용 아님).

    파이프라인이 이미 산출해 `result.ncr` 에 실었으면 그것을 돌려준다. 다시
    계산하면 2선이 본 값과 화면이 본 값이 두 벌이 된다.
    """
    cached = getattr(result, "ncr", None)
    if cached is not None:
        return cached
    inputs = synthesise_securities_firm(result, seed=seed)
    return _compute_from_inputs(inputs)


def compute_ncr_from_parts(total_capital: float, total_ead: float,
                           ecl_total: float, *, seed: int = 42) -> NCRResult:
    """파이프라인용. 결과 객체 없이 같은 합성 입력으로 NCR 을 산출한다."""
    return _compute_from_inputs(synthesise_securities_firm_from_parts(
        total_capital, total_ead, ecl_total, seed=seed))


def _compute_from_inputs(inputs: dict) -> NCRResult:
    return compute_ncr(
        inputs["total_assets"], inputs["total_liabilities"],
        market_risk=inputs["market_risk"],
        credit_risk=inputs["credit_risk"],
        operational_risk=inputs["operational_risk"],
        licenses=inputs["licenses"],
        deductions=inputs["deductions"],
        additions=inputs["additions"],
        risk_methods=inputs["risk_methods"],
    )


def reconcile_prior_period(current: NCRResult, prior: NCRResult) -> pd.DataFrame:
    """전월 대비 대사 (SEC-NCR-004) — 구성요소별 증감과 비율 기여도."""
    rows = [
        ("영업용순자본", prior.noc.net_operating_capital,
         current.noc.net_operating_capital),
        ("  자산총액", prior.noc.total_assets, current.noc.total_assets),
        ("  부채총액", prior.noc.total_liabilities, current.noc.total_liabilities),
        ("  차감항목", prior.noc.total_deduction, current.noc.total_deduction),
        ("  가산항목", prior.noc.total_addition, current.noc.total_addition),
        ("총위험액", prior.risk.total, current.risk.total),
        ("  시장위험액", prior.risk.market_risk, current.risk.market_risk),
        ("  신용위험액", prior.risk.credit_risk, current.risk.credit_risk),
        ("  운영위험액", prior.risk.operational_risk, current.risk.operational_risk),
        ("필요유지자기자본", prior.required_capital, current.required_capital),
    ]
    df = pd.DataFrame(rows, columns=["항목", "전월", "당월"])
    df["증감"] = df["당월"] - df["전월"]
    # 비율 기여도 — 필요유지자기자본이 바뀌면 단순 배분이 성립하지 않으므로
    # 분모 불변 가정 하의 근사임을 열 이름에 남긴다.
    df["NCR 기여(%p, 분모불변 가정)"] = np.where(
        df["항목"].isin(["영업용순자본", "총위험액"]),
        np.where(df["항목"] == "영업용순자본", 1.0, -1.0)
        * df["증감"] / current.required_capital * 100,
        np.nan)
    return df
