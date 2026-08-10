"""신용위험경감(CRM) 담보 배분 (1:1 · 1:N · M:1 · M:N).

`risk_lib.capital.crm`은 익스포저 1행에 담보 1건이 붙은 1:1 포괄법을 계산한다.
이 패키지는 그 위에 담보-익스포저 **관계**를 원장으로 두고, 담보 1건이 여러
익스포저를 덮거나 여러 담보가 한 익스포저에 겹치는 경우의 배분을 푼다.
"""

from risk_lib.crm.params import (
    MITIGATION_PARAM, PARAM_CODES, build_crm_mitigation_param, param_value,
)
from risk_lib.crm.link import (
    RELATION_TYPES, COLLATERAL_TERMS, EXPOSURE_TERMS, COLLATERAL_LINK,
    derive_graph, build_baseline_links, build_crm_link_universe,
)
from risk_lib.crm.allocation import ALLOC_RULES, ALLOCATION, allocate_crm
from risk_lib.crm.consistency import (
    check_allocation_maximality, check_link_completeness,
    run_crm_allocation_checks,
)

CRM_TABLES = (MITIGATION_PARAM, COLLATERAL_TERMS, EXPOSURE_TERMS,
              COLLATERAL_LINK, ALLOCATION)

__all__ = [
    "MITIGATION_PARAM", "PARAM_CODES", "build_crm_mitigation_param",
    "param_value",
    "RELATION_TYPES", "COLLATERAL_TERMS", "EXPOSURE_TERMS", "COLLATERAL_LINK",
    "derive_graph", "build_baseline_links", "build_crm_link_universe",
    "ALLOC_RULES", "ALLOCATION", "allocate_crm",
    "check_allocation_maximality", "check_link_completeness",
    "run_crm_allocation_checks", "CRM_TABLES",
]
