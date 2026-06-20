"""Model inventory & lifecycle governance — SR 11-7 tier system.

Top-IB risk shops maintain a model inventory with strict tier-based
governance:

  - **Tier 1 (high risk)**:  regulatory capital / valuation models
                              (IRB PD, IFRS9 ECL, VaR, FRTB IMA).
                              → annual independent validation + monthly
                              monitoring + board-level reporting.

  - **Tier 2 (medium risk)**: pricing, hedging, scenario models.
                              → biennial validation + quarterly monitoring.

  - **Tier 3 (low risk)**:   internal management info, tools, dashboards.
                              → triennial validation + annual review.

Each model entry tracks: ID, name, owner, tier, status (DEV / UAT / PROD /
RETIRED), last validation date, next due, regulatory citation, known
limitations, performance metrics, dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any


@dataclass
class ModelInventoryEntry:
    model_id: str
    name: str
    tier: int                        # 1, 2, 3
    owner: str
    status: str                      # DEV / UAT / PROD / RETIRED
    last_validation: str             # ISO date
    next_due: str                    # ISO date
    citation: str                    # regulatory ref
    purpose: str
    known_limitations: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)

    def days_overdue(self, today: str | None = None) -> int:
        ref = date.fromisoformat(today) if today else date.today()
        due = date.fromisoformat(self.next_due)
        return max(0, (ref - due).days)

    def is_overdue(self, today: str | None = None) -> bool:
        return self.days_overdue(today) > 0


def _yyyymmdd(d: date) -> str:
    return d.isoformat()


# ----- standard inventory --------------------------------------------------

def build_standard_inventory(*, today: date | None = None) -> list[ModelInventoryEntry]:
    """Risk model inventory matching the risk_lib pipeline."""
    today = today or date.today()
    one_year_ago = today - timedelta(days=200)
    next_year = today + timedelta(days=165)

    inv: list[ModelInventoryEntry] = [
        # ── Tier 1 — regulatory / valuation
        ModelInventoryEntry(
            model_id="PD_CORP", name="신용평가모형 (기업) PD",
            tier=1, owner="Risk Modelling",
            status="PROD",
            last_validation=_yyyymmdd(one_year_ago),
            next_due=_yyyymmdd(next_year),
            citation="Basel III CRE32 / 감독세칙 신용평가모형 검증",
            purpose="기업 차주 12M 부도확률 추정",
            known_limitations=["합성 데이터로 학습", "Gini 0.40 미달 세그먼트 존재"],
            metrics={"gini": 0.45, "ks": 0.32, "hl_p": 0.18},
        ),
        ModelInventoryEntry(
            model_id="PD_RETAIL", name="신용평가모형 (가계) PD",
            tier=1, owner="Risk Modelling",
            status="PROD",
            last_validation=_yyyymmdd(one_year_ago),
            next_due=_yyyymmdd(next_year),
            citation="Basel III CRE32 / 감독세칙",
            purpose="가계 신용대출 12M 부도확률 추정",
            metrics={"gini": 0.40, "ks": 0.28},
        ),
        ModelInventoryEntry(
            model_id="PD_MORTGAGE", name="신용평가모형 (주담대) PD",
            tier=1, owner="Risk Modelling",
            status="PROD",
            last_validation=_yyyymmdd(one_year_ago),
            next_due=_yyyymmdd(next_year),
            citation="Basel III CRE32 + LTV-driven RW",
            purpose="주담대 12M 부도확률 추정",
            metrics={"gini": 0.50, "ks": 0.38},
        ),
        ModelInventoryEntry(
            model_id="LGD_CORP", name="LGD 모형 (기업)",
            tier=1, owner="Risk Modelling",
            status="PROD",
            last_validation=_yyyymmdd(one_year_ago),
            next_due=_yyyymmdd(next_year),
            citation="Basel III CRE32 LGD floor + workout recovery",
            purpose="부도 시 손실률 추정",
            metrics={"mae": 0.08, "r2": 0.65},
        ),
        ModelInventoryEntry(
            model_id="ECL_IFRS9", name="IFRS9 ECL 산출 모형",
            tier=1, owner="Risk + 회계",
            status="PROD",
            last_validation=_yyyymmdd(one_year_ago),
            next_due=_yyyymmdd(next_year),
            citation="IFRS 9 5.5.3 / 5.5.5 / 5.5.11 / B5.5.42",
            purpose="3-stage 분류 + 12M·lifetime ECL + 거시연계 PIT",
            known_limitations=["거시 시나리오 가중 50/30/20 — Probabilistic update 권장"],
        ),
        ModelInventoryEntry(
            model_id="VAR_MARKET", name="시장리스크 VaR 모형",
            tier=1, owner="Market Risk",
            status="PROD",
            last_validation=_yyyymmdd(today - timedelta(days=300)),
            next_due=_yyyymmdd(today + timedelta(days=60)),
            citation="Basel III MAR / FRTB MAR99 (backtest traffic light)",
            purpose="99% 1d VaR + Greeks aggregation",
            metrics={"backtest_zone": "green", "pla_zone": "green"},
        ),
        ModelInventoryEntry(
            model_id="IRRBB", name="은행계정 금리리스크 (IRRBB)",
            tier=1, owner="ALM",
            status="PROD",
            last_validation=_yyyymmdd(one_year_ago),
            next_due=_yyyymmdd(next_year),
            citation="Basel III SRP31.90 IRRBB (2016)",
            purpose="6대 표준 shock의 ΔEVE / ΔNII 산출",
            dependencies=["RFET", "yield_curve_model"],
        ),
        ModelInventoryEntry(
            model_id="LCR_NSFR", name="유동성 비율 산출 (LCR/NSFR)",
            tier=1, owner="ALM",
            status="PROD",
            last_validation=_yyyymmdd(one_year_ago),
            next_due=_yyyymmdd(next_year),
            citation="Basel III LCR20.1 / NSF20.1",
            purpose="LCR (HQLA / 30d net outflow), NSFR (ASF/RSF)",
        ),

        # ── Tier 2 — pricing / scenario
        ModelInventoryEntry(
            model_id="STRESS_MACRO", name="거시 스트레스 시나리오 모형",
            tier=2, owner="Stress Test",
            status="PROD",
            last_validation=_yyyymmdd(one_year_ago),
            next_due=_yyyymmdd(today + timedelta(days=400)),
            citation="감독세칙 스트레스테스트 가이드라인 + Fed CCAR methodology",
            purpose="baseline/adverse/severe + 역스트레스",
        ),
        ModelInventoryEntry(
            model_id="XVA", name="XVA suite (CVA·DVA·FVA·ColVA·MVA)",
            tier=2, owner="Front Office Risk",
            status="PROD",
            last_validation=_yyyymmdd(today - timedelta(days=30)),
            next_due=_yyyymmdd(today + timedelta(days=700)),
            citation="Gregory (2020) · BCBS d325 BA-CVA · CRR2 Art. 381–386",
            purpose="파생거래 가격조정 5종",
            known_limitations=["EPE/ENE curves 합성 시나리오 기반"],
        ),
        ModelInventoryEntry(
            model_id="CLIMATE", name="기후리스크 모형 (전환·물리)",
            tier=2, owner="Climate Risk",
            status="UAT",
            last_validation=_yyyymmdd(today - timedelta(days=60)),
            next_due=_yyyymmdd(today + timedelta(days=700)),
            citation="NGFS Phase 4 + TCFD",
            purpose="탄소가격 → ΔPD, hazard → ΔLGD",
            known_limitations=["NGFS Phase 4 시나리오만 등록", "물리적 손실 지역화 미적용"],
        ),

        # ── Tier 3 — management info
        ModelInventoryEntry(
            model_id="RAF_KRI", name="RAF / KRI 스코어카드",
            tier=3, owner="Risk Strategy",
            status="PROD",
            last_validation=_yyyymmdd(today - timedelta(days=180)),
            next_due=_yyyymmdd(today + timedelta(days=900)),
            citation="감독세칙 RAF 가이드라인 · FSB Principles",
            purpose="12개 KRI 3단 한계 채점",
        ),
        ModelInventoryEntry(
            model_id="VINTAGE", name="Vintage curves + transition matrix",
            tier=3, owner="Credit Risk",
            status="PROD",
            last_validation=_yyyymmdd(today - timedelta(days=200)),
            next_due=_yyyymmdd(today + timedelta(days=900)),
            citation="감독세칙 자산건전성 분류",
            purpose="cohort × MOB 누적 부도율 + 1y migration matrix",
        ),
    ]
    return inv


@dataclass
class InventorySummary:
    total: int
    by_tier: dict[int, int]
    by_status: dict[str, int]
    n_overdue: int
    overdue_models: list[str]


def summarise_inventory(inv: list[ModelInventoryEntry],
                        *, today: str | None = None) -> InventorySummary:
    from collections import Counter
    by_tier = dict(Counter(e.tier for e in inv))
    by_status = dict(Counter(e.status for e in inv))
    overdue = [e.model_id for e in inv if e.is_overdue(today=today)]
    return InventorySummary(
        total=len(inv),
        by_tier=by_tier, by_status=by_status,
        n_overdue=len(overdue), overdue_models=overdue,
    )
