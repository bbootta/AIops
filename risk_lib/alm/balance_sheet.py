"""합성 재무상태표 — 여신 포트폴리오를 축으로 대차대조표를 만든다.

여신(EAD)은 포트폴리오에서 그대로 오고, HQLA·기타자산·조달구성은 국내 시중은행의
통상적 비중으로 결정론적으로(시드) 생성해 ALM(IRRBB/LCR/NSFR)이 신용 원장과
맞물린 입력을 쓰게 한다.

**만기 사다리에서 상수 가중 벡터를 걷어냈다.** 이 모듈은
`asset_w = [0.06, 0.08, …]` / `liab_w = [...]` 두 벡터로 사다리를 만들면서
`portfolio['maturity']`를 쓰지 않았다. 포트폴리오의 만기 분포를 바꿔도 사다리가
미동하지 않았고, 그 사다리를 소비하는 IRRBB·유동성비율·업무보고서가 전부
포트폴리오와 무관한 값을 보고했다. 지금은 `alm.liquidity.build_repricing_ladder`가
고정금리를 실제 잔존만기에, 변동금리를 **재설정 주기 안에 퍼진** 차기 재설정일에
슬로팅하고(BCBS d368 Annex 2), 비만기예금을 `alm_nmd_param`으로 **행태
슬로팅**한다 — 서식 각주가 감독당국 제출문서에 "비만기성 예금은 행태만기로
슬로팅되어 있다"고 적고 있으므로 그 문장이 사실이어야 한다.

변동금리를 주기 끝 한 점(3개월 재설정 → 0.25년)에 몰면 "오늘 전 계약이 동시에
재설정했다"는 뜻이 되어 최단 두 버킷이 구조적으로 비고, 그 사다리를 분자로 쓰던
외화유동성비율이 항상 0으로 나갔다. 조달도 만기 구간의 **중점**이 아니라 구간을
넘긴다 — 중점 3.0년은 버킷 상한과 정확히 같아 슬로팅이 경계 규약 하나로 뒤집혔다.

**이 사다리의 시간축은 리프라이싱이다.** 잔존만기 축이 필요한 소비처(제26조·
제63조 유동성비율)는 `alm.liquidity.build_contractual_balance_ladder`가 계약원장
에서 따로 접는다.

**NSFR 자산 분해의 임의 비율도 걷어냈다.** 은행 여신을 `×0.4`(6개월 이내) /
`×0.6`(1년 이상)으로 나누던 자리는 근거가 없었고, 잔존 5년 여신의 40%가 RSF
15% 가중을 받았다. 구간 경계는 `alm_nsfr_factor` 원장이 정하고 분할은 실제
잔존만기로 한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


# Repricing ladder used for IRRBB (bucket label, midpoint in years, upper bound).
REPRICING_BUCKETS = [
    ("0-1m",   1 / 24,  1 / 12),
    ("1-3m",   2 / 12,  3 / 12),
    ("3-6m",   4.5 / 12, 6 / 12),
    ("6-12m",  9 / 12,  1.0),
    ("1-2y",   1.5,     2.0),
    ("2-3y",   2.5,     3.0),
    ("3-5y",   4.0,     5.0),
    ("5-10y",  7.5,     10.0),
    ("10y+",   12.5,    20.0),
]

# 금리민감 부채 비중. 사다리는 금리민감 자산·부채만 담으므로 대차대조표 총액과
# 차이가 나며, 서식은 그 차를 "만기구간 미배분" 라인으로 드러낸다.
RATE_SENSITIVE_LIAB_SHARE = 0.93

# HQLA 채권의 잔존만기 범위(년). contracts.py의 HQLA 트랜치와 같은 범위다 —
# 두 곳이 달라지면 같은 자산이 사다리와 계약원장에서 다른 버킷에 놓인다.
HQLA_TENOR_RANGE = (0.5, 8.0)


@dataclass
class BalanceSheet:
    """All amounts in KRW (same unit as portfolio EAD)."""
    total_assets: float
    loans: float                      # = portfolio EAD total
    hqla: dict[str, float]            # level_1 / level_2a / level_2b (market value)
    other_assets: float
    funding: dict[str, float]         # category → amount
    equity: float
    repricing: pd.DataFrame           # bucket, t_mid, assets, liabilities, gap
    asset_split: dict[str, float] = field(default_factory=dict)  # NSFR asset buckets
    ladder_warnings: list = field(default_factory=list)          # ParamWarning

    def funding_total(self) -> float:
        return sum(self.funding.values())


def generate_balance_sheet(
    portfolio: pd.DataFrame,
    capital_total: float,
    *,
    seed: int = 42,
    asof: str | None = None,
) -> BalanceSheet:
    """Build a balance sheet around the loan book.

    Loans are taken as-is from the portfolio; the rest of the balance sheet is
    proportioned to total assets with mild seeded jitter (±5%) so different
    seeds yield slightly different but always-coherent sheets.

    `asof`는 계수 원장에 찍히는 기준일이며 잔액 생성에는 쓰이지 않는다. 사다리와
    NSFR 분해는 `asof`가 없어도 만들어진다 — 둘 다 잔존만기(연 단위)의 함수이고
    달력일이 필요한 것은 상환스케줄뿐이다.
    """
    # 순환 참조 회피 — params가 이 모듈의 REPRICING_BUCKETS를 읽고,
    # nsfr/liquidity가 이 모듈의 BalanceSheet를 읽는다. 함수 안에서 부르면
    # 두 방향 모두 성립한다.
    from risk_lib.alm.contracts import (
        FUNDING_PRODUCT_MAP, _ASSET_PRODUCT, _FUNDING_TENOR)
    from risk_lib.alm.liquidity import build_repricing_ladder
    from risk_lib.alm.nsfr import build_nsfr_factor, maturity_band_of
    from risk_lib.alm.params import (
        build_nmd_param, build_product_terms, build_time_buckets)

    rng = np.random.default_rng(seed + 101)
    loans = float(portfolio["ead"].sum())

    def jitter(x: float) -> float:
        return x * float(rng.uniform(0.95, 1.05))

    # Asset side: loans ~72% of total assets.
    total_assets = loans / jitter(0.72)
    hqla = {
        "level_1": total_assets * jitter(0.13),
        "level_2a": total_assets * jitter(0.04),
        "level_2b": total_assets * jitter(0.02),
    }
    other_assets = total_assets - loans - sum(hqla.values())

    # Funding side: liabilities = assets - equity.
    equity = capital_total
    liabilities = total_assets - equity
    w = {
        "retail_stable": jitter(0.28),
        "retail_less_stable": jitter(0.17),
        "corporate_operational": jitter(0.12),
        "corporate_non_operational": jitter(0.13),
        "wholesale_fi_lt6m": jitter(0.07),
        "wholesale_fi_6to12m": jitter(0.05),
        "funding_gt1y": jitter(0.18),
    }
    scale = liabilities / sum(w.values())
    funding = {k: v * scale for k, v in w.items()}

    # ---- 리프라이싱 사다리: 포트폴리오 만기 + NMD 행태 슬로팅 -------------
    hqla_tenors = dict(zip(hqla, rng.uniform(*HQLA_TENOR_RANGE, len(hqla))))
    rep, ladder_warnings = build_repricing_ladder(
        portfolio,
        funding=funding, hqla=hqla, hqla_tenor_years=hqla_tenors,
        asset_product_split=_ASSET_PRODUCT,
        funding_product_of={k: v[0] for k, v in FUNDING_PRODUCT_MAP.items()},
        nmd_category_of={k: v[1] for k, v in FUNDING_PRODUCT_MAP.items()},
        # 중점이 아니라 구간을 넘긴다 — 중점 3.0년은 버킷 상한과 정확히 같아
        # 슬로팅이 경계 규약 하나로 뒤집혔고, 계약원장은 이 구간에 트랜치를
        # 균등 배치한다.
        funding_tenor_range=dict(_FUNDING_TENOR),
        product_terms=build_product_terms(),
        buckets=build_time_buckets(), nmd_param=build_nmd_param(asof),
        liability_scale=RATE_SENSITIVE_LIAB_SHARE)

    # ---- NSFR 자산 분해: 구간 경계는 원장, 분할은 실제 잔존만기 ----------
    nf = build_nsfr_factor()
    nf_rsf = nf[nf["section"] == "RSF"]
    mat = (portfolio["maturity"].to_numpy(dtype=float)
           if "maturity" in portfolio.columns
           else np.zeros(len(portfolio)))
    ead = portfolio["ead"].to_numpy(dtype=float)
    ac = portfolio["asset_class"].astype(str).to_numpy()
    npl = ((portfolio["dpd"].to_numpy() >= 90) if "dpd" in portfolio.columns
           else np.zeros(len(portfolio), dtype=bool))

    cat = np.full(len(portfolio), "", dtype=object)
    cat[npl] = "npl"
    fi = (~npl) & (ac == "bank")
    cat[fi] = maturity_band_of(
        mat[fi], nf_rsf, ("loans_fi_lt6m", "loans_fi_6to12m",
                          "other_loans_ge1y"))
    mtg = (~npl) & (ac == "residential_mortgage")
    cat[mtg] = maturity_band_of(mat[mtg], nf_rsf,
                                ("loans_lt1y", "mortgages_ge1y"))
    rest = (~npl) & (~fi) & (~mtg)
    cat[rest] = maturity_band_of(mat[rest], nf_rsf,
                                 ("loans_lt1y", "other_loans_ge1y"))

    asset_split = {"hqla_l1": hqla["level_1"], "hqla_l2a": hqla["level_2a"],
                   "hqla_l2b": hqla["level_2b"]}
    for key in ("loans_fi_lt6m", "loans_fi_6to12m", "loans_lt1y",
                "mortgages_ge1y", "other_loans_ge1y", "npl"):
        asset_split[key] = float(ead[cat == key].sum())
    asset_split["other_assets"] = other_assets

    return BalanceSheet(
        total_assets=total_assets,
        loans=loans,
        hqla=hqla,
        other_assets=other_assets,
        funding=funding,
        equity=equity,
        repricing=rep,
        asset_split=asset_split,
        ladder_warnings=ladder_warnings,
    )
