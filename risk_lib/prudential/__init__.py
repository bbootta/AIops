"""건전성 감독 도메인 — 은행업감독규정·은행법 편제에서 업무보고서가 요구하지만
기존 엔진에 없던 산출을 채운다.

  financials.py   재무상태표·손익계산서 요약 (업무보고서 기본 서식)
  liquidity.py    원화유동성비율 · 외화유동성비율 · 원화예대율
  ownership.py    대주주 신용공여 · 유가증권 투자 · 자회사 출자 · 부동산 소유 한도
  camel.py        경영실태평가 (자본·자산·경영·수익·유동성·리스크관리)
  pca.py          적기시정조치 판정 (경영개선권고·요구·명령)

모두 파이프라인 산출값(PipelineResult)과 대차대조표에서 유도하며, 새 가정을
도입하는 곳은 함수 docstring에 근거와 함께 명시한다.
"""
from risk_lib.prudential.financials import (
    FinancialStatements, build_financials,
)
from risk_lib.prudential.liquidity import (
    LiquidityRatios, compute_liquidity_ratios,
    KRW_LIQUIDITY_MIN, FX_LIQUIDITY_MIN, LOAN_DEPOSIT_MAX,
)
from risk_lib.prudential.ownership import (
    OwnershipLimits, compute_ownership_limits,
)
from risk_lib.prudential.camel import CamelRating, evaluate_camel
from risk_lib.prudential.pca import PromptAction, assess_prompt_action

__all__ = [
    "FinancialStatements", "build_financials",
    "LiquidityRatios", "compute_liquidity_ratios",
    "KRW_LIQUIDITY_MIN", "FX_LIQUIDITY_MIN", "LOAN_DEPOSIT_MAX",
    "OwnershipLimits", "compute_ownership_limits",
    "CamelRating", "evaluate_camel",
    "PromptAction", "assess_prompt_action",
]
