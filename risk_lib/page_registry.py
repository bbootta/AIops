"""Single source of truth for the ops report page set.

Adding a page means one PageSpec entry here plus the builder function
(in risk_lib/ops_pages/<domain>.py; core pages live in ops_pages/core_*). NAV and build_report_set both derive from PAGES.

Builders are referenced by (module, func) strings and resolved with
importlib at build time, so this module imports nothing heavy and the
ops page modules can keep importing chrome from report_chrome without a
circular import.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Callable

_CORE_OVR = "risk_lib.ops_pages.core_overview"
_CORE_CRD = "risk_lib.ops_pages.core_credit"
_CORE_CAP = "risk_lib.ops_pages.core_capital_alm"
_CREDIT = "risk_lib.ops_pages.credit"
_CAPITAL = "risk_lib.ops_pages.capital_stress"
_MARKET = "risk_lib.ops_pages.market_trading"
_CONC = "risk_lib.ops_pages.concentration_limits"
_PERF = "risk_lib.ops_pages.performance"
_NONFIN = "risk_lib.ops_pages.nonfinancial"
_GOV = "risk_lib.ops_pages.governance"


@dataclass(frozen=True)
class PageSpec:
    filename: str
    label: str                     # nav / index link text
    module: str                    # dotted path of the module holding the builder
    func: str                      # builder function name
    needs_portfolio: bool = False  # builder signature is (result, portfolio);
                                   # page is skipped when portfolio is None
    in_nav: bool = True            # False → ALM sub-tab, not the main nav bar

    def resolve(self) -> Callable:
        return getattr(importlib.import_module(self.module), self.func)


# Files in render order; main-nav links appear in this sequence.
PAGES: tuple[PageSpec, ...] = (
    PageSpec("index.html",         "0. 요약",         _CORE_OVR, "_page_summary"),
    PageSpec("01_portfolio.html",  "1. 포트폴리오",    _CORE_OVR, "_page_portfolio"),
    PageSpec("02_pd.html",         "2. PD모형",       _CORE_CRD, "_page_pd"),
    PageSpec("03_rwa.html",        "3. RWA",          _CORE_CAP, "_page_rwa"),
    PageSpec("04_capital.html",    "4. BIS·레버리지",  _CORE_CAP, "_page_capital"),
    PageSpec("05_ecl.html",        "5. ECL",          _CORE_CRD, "_page_ecl"),
    PageSpec("06_monitoring.html", "6. 모니터링",      _CORE_CRD, "_page_monitoring"),
    PageSpec("07_limits.html",     "7. 한도",         _CORE_CRD, "_page_limits"),
    PageSpec("08_rapm.html",       "8. RAPM",         _CORE_CRD, "_page_rapm"),
    PageSpec("09_stress.html",     "9. 스트레스",      _CORE_CAP, "_page_stress"),
    PageSpec("10_icaap.html",      "10. 내부자본",     _CORE_CAP, "_page_icaap"),
    PageSpec("11_alm.html",        "11. ALM",         _CORE_CAP, "_page_alm_hub"),
    PageSpec("11a_irrbb.html",     "IRRBB",           _CORE_CAP, "_page_irrbb", in_nav=False),
    PageSpec("11b_lcr.html",       "LCR",             _CORE_CAP, "_page_lcr",   in_nav=False),
    PageSpec("11c_nsfr.html",      "NSFR",            _CORE_CAP, "_page_nsfr",  in_nav=False),
    PageSpec("12_validation.html", "12. 검증",        _CORE_OVR, "_page_validation"),
    PageSpec("13_climate.html",    "13. 기후",        _NONFIN, "page_climate"),
    PageSpec("14_ccr.html",        "14. CCR/CVA",     _MARKET, "page_ccr"),
    PageSpec("15_op_loss.html",    "15. 운영손실",     _NONFIN, "page_op_loss"),
    PageSpec("16_sensitivity.html","16. 민감도",       _NONFIN, "page_sensitivity"),
    PageSpec("17_model_risk.html", "17. 모형",        _GOV, "page_model_risk"),
    PageSpec("18_concentration_deep.html", "18. 집중 D-D", _CONC, "page_concentration_deep"),
    PageSpec("19_raf.html",        "19. RAF",         _GOV, "page_raf"),
    PageSpec("20_pillar3.html",    "20. Pillar 3",    _GOV, "page_pillar3", needs_portfolio=True),
    PageSpec("21_mda.html",        "21. MDA",         _CAPITAL, "page_mda"),
    PageSpec("22_kri_trends.html", "22. KRI 트렌드",  _GOV, "page_kri_trends"),
    PageSpec("23_attribution.html","23. 귀속분석",     _PERF, "page_attribution"),
    PageSpec("24_vintage.html",    "24. Vintage",     _CREDIT, "page_vintage", needs_portfolio=True),
    PageSpec("25_data_quality.html", "25. DQ·정합성", _GOV, "page_data_quality", needs_portfolio=True),
    PageSpec("26_comparison.html", "26. 시점 비교",   _GOV, "page_comparison"),
    PageSpec("27_lgd_model.html",  "27. LGD모형",     _CORE_CRD, "_page_lgd_model"),
    PageSpec("28_model_challenger.html", "28. 챔피언/챌린저", _CORE_CRD, "_page_model_challenger"),
    PageSpec("29_irb_deep.html",   "29. IRB D-D",     _CREDIT, "page_irb_deep"),
    PageSpec("30_market_risk_deep.html", "30. 시장 D-D", _MARKET, "page_market_risk_deep"),
    PageSpec("31_op_risk_deep.html", "31. 운영 D-D",  _NONFIN, "page_op_risk_deep"),
    PageSpec("32_capital_stack.html", "32. 자본 스택", _CAPITAL, "page_capital_stack"),
    PageSpec("33_buffer_layering.html", "33. 버퍼 layer", _CAPITAL, "page_buffer_layering"),
    PageSpec("34_leverage_deep.html", "34. 레버리지 D-D", _CAPITAL, "page_leverage_deep"),
    PageSpec("35_sicr_detail.html",   "35. SICR 분해", _CREDIT, "page_sicr_detail"),
    PageSpec("36_pd_term_structure.html", "36. PD 잔존기간", _CREDIT, "page_pd_term_structure"),
    PageSpec("37_macro_scenario.html", "37. 거시 시나리오", _CREDIT, "page_macro_scenario"),
    PageSpec("38_provisioning_attribution.html", "38. 충당금 귀속", _CREDIT, "page_provisioning_attribution"),
    PageSpec("39_dpd_roll.html",   "39. DPD roll-rate", _CREDIT, "page_dpd_roll"),
    PageSpec("40_recovery_lgd.html", "40. 회수·LGD",  _CREDIT, "page_recovery_lgd"),
    PageSpec("41_cure_analysis.html", "41. Cure 분석", _CREDIT, "page_cure_analysis"),
    PageSpec("42_limit_dashboard.html", "42. 한도 dashboard", _CONC, "page_limit_dashboard"),
    PageSpec("43_large_exposure.html", "43. 거대익스포저", _CONC, "page_large_exposure"),
    PageSpec("44_concentration_stress.html", "44. 집중 스트레스", _CONC, "page_concentration_stress"),
    PageSpec("45_eva_sva.html",    "45. EVA/SVA",     _PERF, "page_eva_sva"),
    PageSpec("46_pricing_breakeven.html", "46. Pricing", _PERF, "page_pricing_breakeven"),
    PageSpec("47_rapm_scenario.html", "47. RAPM 시나리오", _PERF, "page_rapm_scenario"),
    PageSpec("48_reverse_stress_multi.html", "48. Multi-역스트레스", _CAPITAL, "page_reverse_stress_multi"),
    PageSpec("49_ccar_path.html",  "49. CCAR 경로",   _CAPITAL, "page_ccar_path"),
    PageSpec("50_climate_capital.html", "50. 기후 자본", _CAPITAL, "page_climate_capital"),
    PageSpec("51_liquidity_stress.html", "51. 유동성 stress", _CAPITAL, "page_liquidity_stress"),
    PageSpec("52_final_attestation.html", "52. 최종 결재", _CORE_OVR, "_page_final_attestation"),
    PageSpec("53_xva_full.html",   "53. XVA 전체",    _MARKET, "page_xva_full"),
    PageSpec("54_trading_sensitivities.html", "54. Trading Greeks", _MARKET, "page_trading_sensitivities"),
    PageSpec("55_scenario_library.html", "55. Scenario Library", _MARKET, "page_scenario_library"),
    PageSpec("56_frtb_ima.html",   "56. FRTB IMA",    _MARKET, "page_frtb_ima"),
    PageSpec("57_model_inventory.html", "57. Model Inventory", _GOV, "page_model_inventory"),
    PageSpec("58_explainability.html", "58. Explainability", _GOV, "page_explainability"),
    PageSpec("59_pillar3_full.html", "59. Pillar 3 Full", _GOV, "page_pillar3_full"),
    PageSpec("60_capital_simulation.html", "60. Capital Simulation", _CAPITAL, "page_capital_simulation"),
    PageSpec("61_intraday.html",   "61. Intraday",    _MARKET, "page_intraday"),
    PageSpec("62_cecl_ifrs9.html", "62. CECL vs IFRS9", _CREDIT, "page_cecl_ifrs9"),
)


def nav_items() -> list[tuple[str, str]]:
    """(filename, label) pairs for the main nav bar, in render order."""
    return [(p.filename, p.label) for p in PAGES if p.in_nav]
