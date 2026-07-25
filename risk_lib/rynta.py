"""RYNTA v9.0 제품 분류체계 · 요건 매니페스트 · 하니스 커버리지 추적.

RYNTA — Risk Yard with Neural Trustworthy Architecture.
결정론적 엔진이 계산하고, Agent는 조사·분류·설명·워크플로 조정을 지원하며,
중요한 결과는 책임 있는 사람이 승인하는 Financial Control Execution Layer.

본 모듈이 하는 일:
  1. 12 Canonical Product · 6 상업 suite 분류체계 (`PRODUCTS`, `SUITES`)
  2. BRD 요건 126건 매니페스트 로드 (`load_requirements`) — 원본
     `RYNTA_RiskOps_v9.0_navigation.xlsx`의 `10_Requirements` 시트에서 추출,
     원본 파일 SHA-256을 함께 보존
  3. **커버리지 추적** (`COVERAGE`, `coverage_frame`) — 각 요건이 이 하니스에서
     어떤 모듈·보고서 페이지로 증빙되는지의 1:1 매핑. 상태는 다음 4종:

     covered  — 산출·증빙이 하니스에 구현됨
     partial  — 일부만 구현 (미구현 부분을 gap에 명시)
     platform — 플랫폼/인프라 계층 (커넥터·IAM·배포) — 산출 하니스 범위 밖
     backlog  — RYNTA 범위이나 본 하니스 미구현

커버리지 상태는 낙관적으로 표기하지 않는다 — 미구현을 covered로 적으면
Requirement traceability 자체가 무효가 된다 (AIMS_POLICY §2-5).

참조: RYNTA_Vol1_v9.0_한국어_README.md, RYNTA_Business_Requirements_v9.0.html
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_DATA = Path(__file__).parent / "data" / "rynta_requirements_v9_0.json"

PACKAGE_NAME = "RYNTA — Risk Yard with Neural Trustworthy Architecture"
PACKAGE_TAGLINE = "Financial Control Execution Layer · 통제된 리스크 산출·증빙·의사결정"
PACKAGE_VERSION = "v9.0"


# ---------------------------------------------------------------- 분류체계

@dataclass(frozen=True)
class Product:
    id: str
    name: str
    family: str          # 제품군
    suite: str           # 소속 상업 suite ID
    buyer: str


PRODUCTS: tuple[Product, ...] = (
    Product("PRD-RDM", "Risk Data Fabric & Control Hub", "공통 기반",
            "RYNTA-FND", "CRO/CIO/CDO·리스크데이터오피스"),
    Product("PRD-AIG", "AI Governance & Agentic", "공통 거버넌스",
            "RYNTA-FND", "AI위원회·IT·보안"),
    Product("PRD-VAL", "Continuous & Independent Validation Assurance", "공통 독립검증",
            "RYNTA-FND", "CRO·모델리스크·독립검증"),
    Product("PRD-CRM", "Credit Rating Model Assurance", "신용·회계",
            "RYNTA-CRD", "신용리스크·모델검증"),
    Product("PRD-RWA", "RWA Assurance Engine", "신용·회계",
            "RYNTA-CRD", "RWA·자본관리"),
    Product("PRD-ECL", "IFRS 9 ECL Assurance", "신용·회계",
            "RYNTA-CRD", "회계/ECL·신용리스크"),
    Product("PRD-ST", "ICAAP & Integrated Stress Analytics", "자본·스트레스",
            "RYNTA-CAP", "CRO/CFO·자본관리"),
    Product("PRD-CAP", "Capital Ratio & RAPM", "자본·성과",
            "RYNTA-CAP", "CFO·자본/성과"),
    Product("PRD-ALM", "IRRBB, ALM & Liquidity RiskOps", "Treasury·Liquidity",
            "RYNTA-TRS", "ALM·자금"),
    Product("PRD-NCR", "Prudential Capital Reporting", "Markets·Prudential",
            "RYNTA-MKT", "CRO·재무·건전성규제 보고"),
    Product("PRD-MKT", "Market Risk & Pricing", "Markets·Pricing",
            "RYNTA-MKT", "시장리스크·퀀트"),
    Product("PRD-OPR", "Operational RiskOps", "운영회복탄력성",
            "RYNTA-OPR", "운영리스크·감사"),
)

SUITES: dict[str, str] = {
    "RYNTA-FND": "Foundation & Assurance",
    "RYNTA-CRD": "Credit & Accounting",
    "RYNTA-CAP": "Capital & Stress",
    "RYNTA-TRS": "Treasury & Liquidity",
    "RYNTA-MKT": "Markets & Prudential",
    "RYNTA-OPR": "Operational Resilience",
}


# ---------------------------------------------------------------- AI 가드레일

# As-is/To-be 문서 「필수 가드레일」 + BRD AIG-002~012.
GUARDRAILS: tuple[tuple[str, str, str], ...] = (
    ("조회 전용", "에이전트는 범위가 제한된 비변경 접근으로 시작한다.", "AIG-002"),
    ("제안 전용", "에이전트는 분석·매핑·조치를 제안하며 자동확정하지 않는다.", "AIG-003"),
    ("승인 우선", "중요 변경은 정책 게이트와 사람 승인이 필요하다.", "AIG-004"),
    ("최소 권한", "도구·데이터·테넌트 범위를 명시하고 기록한다.", "AIG-005"),
    ("Kill Switch", "에이전트·도구·워크플로 실행을 범위별 중단할 수 있다.", "AIG-009"),
)

# 「AI 자동확정 금지」 — Agent가 스스로 확정할 수 없는 결정 목록.
NO_AUTO_DECISION: tuple[str, ...] = (
    "신용등급·여신승인",
    "가격·거래",
    "PD·LGD·EAD 등 핵심 위험파라미터",
    "ECL·충당금·회계전표",
    "RWA·NCR·BIS 비율",
    "감독제출·공시",
    "경영조치",
    "운영코드·모형 배포",
)

# A–F 공통 AI Governance Baseline의 준거 기준 (통제설계 참조 — 자동 준수 아님).
AI_STANDARDS: tuple[tuple[str, str], ...] = (
    ("EU AI Act · Regulation (EU) 2024/1689",
     "위험기반 분류, 데이터 거버넌스, 기술문서·로그, 인간 감독, 정확성·강건성·사이버보안"),
    ("EU Trustworthy AI Ethics Guidelines",
     "인간 주도성, 기술적 안전, 개인정보·데이터, 투명성, 공정성, 사회·환경, 책무성"),
    ("ISO/IEC 42001:2023",
     "AI 경영시스템(AIMS)의 정책·역할·위험 및 기회·영향평가·운영통제·모니터링·지속개선"),
    ("NIST AI RMF 1.0",
     "Govern · Map · Measure · Manage를 평가셋·성능/영향 측정·시정조치·Lifecycle에 연결"),
)


# ---------------------------------------------------------------- 요건 매니페스트

@lru_cache(maxsize=1)
def load_manifest() -> dict:
    return json.loads(_DATA.read_text(encoding="utf-8"))


def load_requirements() -> list[dict]:
    """BRD 요건 126건 (id/title/sector/priority/stage/type/product/text/source)."""
    return load_manifest()["requirements"]


# ---------------------------------------------------------------- 커버리지

@dataclass(frozen=True)
class Coverage:
    status: str          # covered | partial | platform | backlog
    modules: str         # 구현 모듈 (risk_lib.*)
    pages: str           # 증빙 보고서 페이지 (ops/NN_*.html)
    gap: str = ""        # partial/backlog 사유


_C = Coverage

# 요건 ID → 하니스 증빙. 접두사 단위 기본값을 두고 개별 요건에서 덮어쓴다.
COVERAGE: dict[str, Coverage] = {
    # ---- 신용 RWA / ECL -------------------------------------------------
    "BNK-CRE-001": _C("covered", "risk_lib.models.pd_model · models.lgd_model · capital.crm",
                      "ops/02_pd · ops/27_lgd_model · ops/40_recovery_lgd"),
    "BNK-CRE-002": _C("covered", "risk_lib.capital.rwa_sa · rwa_irb · output_floor",
                      "ops/03_rwa · ops/29_irb_deep"),
    "BNK-CRE-003": _C("partial", "risk_lib.capital.crm",
                      "ops/03_rwa",
                      "담보 haircut·CCF·보증대체는 구현, 법률적 집행가능성(legal enforceability) 검토 워크플로는 미구현"),
    "BNK-CRE-004": _C("covered", "risk_lib.provisioning.ecl · ifrs9_deep",
                      "ops/35_sicr_detail · ops/05_ecl"),
    "BNK-CRE-005": _C("covered", "risk_lib.provisioning.ecl · provisioning.macro",
                      "ops/05_ecl · ops/37_macro_scenario"),
    "BNK-CRE-006": _C("partial", "risk_lib.provisioning.ifrs9_deep · risk_lib.cecl",
                      "ops/38_provisioning_attribution · ops/62_cecl_ifrs9",
                      "PMA(경영진 overlay)·IRB–ECL 격차 분석은 구현, GL 전표 연계는 미구현"),
    # ---- 신용평가모형 ---------------------------------------------------
    "BNK-CRM-001": _C("partial", "risk_lib.model_risk · model_inventory",
                      "ops/17_model_risk · ops/57_model_inventory",
                      "모형 인벤토리·검증주기는 구현, 모형위원회 승인 workflow는 미구현"),
    "BNK-CRM-002": _C("partial", "risk_lib.models.pd_model",
                      "ops/02_pd · ops/28_model_challenger",
                      "개발·검증·모니터링 산출은 구현, 운영 배포 lifecycle 게이트는 미구현"),
    "BNK-CRM-003": _C("partial", "risk_lib.data_gen · data_quality",
                      "ops/25_data_quality",
                      "합성 모집단·타깃 정의 구현, 실제 CSS 모집단 정책은 고객 데이터 필요"),
    "BNK-CRM-004": _C("covered", "risk_lib.models.pd_model · models.rating",
                      "ops/02_pd"),
    "BNK-CRM-005": _C("covered", "risk_lib.models.discrimination · validation.backtest",
                      "ops/02_pd · ops/12_validation"),
    "BNK-CRM-006": _C("partial", "risk_lib.models.pd_model",
                      "ops/02_pd",
                      "재무비율 기반 로지스틱 모형 구현, 기업 전용 재무제표 파이프라인은 미구현"),
    "BNK-CRM-007": _C("backlog", "", "",
                      "기업 비재무·대표자 평가 모듈 미구현"),
    "BNK-CRM-008": _C("covered", "risk_lib.models.rating",
                      "ops/02_pd"),
    "BNK-CRM-009": _C("partial", "risk_lib.monitoring.deep",
                      "ops/06_monitoring · ops/39_dpd_roll",
                      "EWS 지표·전이 모니터링 구현, Override 승인 원장은 미구현"),
    # ---- 통합 스트레스 / ICAAP -----------------------------------------
    "BNK-ST-001": _C("covered", "risk_lib.icaap.economic_capital",
                     "ops/10_icaap"),
    "BNK-ST-002": _C("covered", "risk_lib.stress.scenario · stress.narrative · scenario_library",
                     "ops/09_stress · ops/55_scenario_library"),
    "BNK-ST-003": _C("covered", "risk_lib.validation.cross_domain · stress.decomposition",
                     "ops/16_sensitivity · ops/52_final_attestation"),
    "BNK-ST-004": _C("covered", "risk_lib.stress.path · capital_simulation",
                     "ops/09_stress · ops/49_ccar_path · ops/60_capital_simulation"),
    "BNK-ST-005": _C("covered", "risk_lib.stress.recovery · mda · limits.limit_engine",
                     "ops/21_mda · ops/07_limits · ops/42_limit_dashboard"),
    "BNK-ST-006": _C("covered", "risk_lib.stress.reverse · stress.multi_reverse",
                     "ops/48_reverse_stress_multi"),
    "BNK-ST-007": _C("covered", "risk_lib.repro · audit_trail",
                     "ops/52_final_attestation · audit_ledger.json · manifest.json"),
    # ---- 자본·성과 ------------------------------------------------------
    "BNK-CAP-001": _C("covered", "risk_lib.capital.bis · bis_deep · leverage_deep",
                      "ops/04_capital · ops/32_capital_stack · ops/33_buffer_layering"),
    "BNK-CAP-002": _C("covered", "risk_lib.performance.rapm · rapm_deep",
                      "ops/08_rapm · ops/45_eva_sva · ops/46_pricing_breakeven · ops/47_rapm_scenario"),
    # ---- 은행 기타 부문 -------------------------------------------------
    "BNK-OTH-001": _C("covered", "risk_lib.op_loss",
                      "ops/15_op_loss · ops/31_op_risk_deep"),
    "BNK-OTH-002": _C("covered", "risk_lib.ccr · xva · sensitivities · frtb",
                      "ops/14_ccr · ops/53_xva_full · ops/54_trading_sensitivities · ops/56_frtb_ima"),
    "BNK-OTH-003": _C("covered", "risk_lib.alm.irrbb · alm.lcr · alm.nsfr · stress.liquidity",
                      "ops/11a_irrbb · ops/11b_lcr · ops/11c_nsfr · ops/51_liquidity_stress"),
    "BNK-OTH-004": _C("partial", "risk_lib.climate",
                      "ops/13_climate · ops/50_climate_capital",
                      "기후(전환·물리) 구현, 전략·평판 리스크 정성 평가는 미구현"),
    # ---- 증권 시장리스크 ------------------------------------------------
    "SEC-MKT-001": _C("covered", "risk_lib.capital.market_risk · frtb",
                      "ops/30_market_risk_deep · ops/56_frtb_ima"),
    "SEC-MKT-002": _C("covered", "risk_lib.sensitivities · frtb",
                      "ops/54_trading_sensitivities · ops/56_frtb_ima"),
    "SEC-MKT-003": _C("partial", "risk_lib.frtb",
                      "ops/56_frtb_ima",
                      "PLA(P&L attribution) 테스트 구현, 한도 위반 workflow는 미구현"),
    "SEC-CCR-001": _C("covered", "risk_lib.ccr",
                      "ops/14_ccr"),
    "SEC-CCR-002": _C("covered", "risk_lib.xva",
                      "ops/53_xva_full"),
    "SEC-CCR-003": _C("partial", "risk_lib.xva",
                      "ops/53_xva_full",
                      "MVA(margin) 구현, 담보 최적화·margin call workflow는 미구현"),
    "SEC-LIQ-001": _C("partial", "risk_lib.alm.balance_sheet",
                      "ops/11_alm",
                      "조달 구조 반영, Repo·단기조달 전용 모듈은 미구현"),
    "SEC-LIQ-002": _C("covered", "risk_lib.stress.liquidity",
                      "ops/51_liquidity_stress"),
    "SEC-PRC-001": _C("backlog", "", "", "시장데이터 거버넌스(Curve·Vol 원천 관리) 미구현"),
    "SEC-PRC-002": _C("partial", "risk_lib.sensitivities",
                      "ops/54_trading_sensitivities",
                      "Black-Scholes 계열 Greeks 구현, 상품명세 원장·엔진 버전관리는 미구현"),
    "SEC-PRC-003": _C("partial", "risk_lib.sensitivities",
                      "ops/54_trading_sensitivities",
                      "Greeks 산출 구현, 회귀테스트 harness는 미구현"),
    "SEC-PRC-004": _C("backlog", "", "", "Curve·Vol calibration 미구현"),
    "SEC-PRC-005": _C("backlog", "", "", "IPV·Valuation Adjustment workflow 미구현"),
    "SEC-NCR-001": _C("partial", "risk_lib.ncr.required_capital · LICENSE_CAPITAL_REQUIREMENT",
                      "ops/64_ncr",
                      "인가업무 단위별 필요자기자본 구조는 구현, 실제 인가 내역·"
                      "국가별 Rule Pack(US Net Capital·EU IFR/IFD)은 미구현"),
    "SEC-NCR-002": _C("partial", "risk_lib.ncr.compute_net_operating_capital",
                      "ops/64_ncr",
                      "자산−부채−차감+가산 구조와 규정 항목목록은 구현, "
                      "차감항목별 인정범위는 기관 승인 사양 필요"),
    "SEC-NCR-003": _C("partial", "risk_lib.ncr.compute_total_risk",
                      "ops/64_ncr",
                      "시장+신용+운영 단순합 구조는 구현, 위험액 세부 산출방법"
                      "(표준방법 세율·포지션 매핑)은 승인 사양 필요"),
    "SEC-NCR-004": _C("covered", "risk_lib.ncr.reconcile_prior_period",
                      "ops/64_ncr"),
    "SEC-OAI-001": _C("partial", "risk_lib.op_loss",
                      "ops/15_op_loss",
                      "손실 LDA 구현, RCSA/KRI 등록·조치 workflow는 미구현"),
    "SEC-OAI-002": _C("covered", "risk_lib.model_inventory · model_risk",
                      "ops/17_model_risk · ops/57_model_inventory"),
    "SEC-OAI-003": _C("backlog", "", "", "Agentic Close Workflow 미구현"),
    # ---- 거버넌스 통제 (GOV) -------------------------------------------
    "GOV-001": _C("covered", "risk_lib.repro (asof·seed·지문)",
                  "manifest.json · ops/25_data_quality"),
    "GOV-002": _C("partial", "risk_lib.data_quality · validation.consistency",
                  "ops/25_data_quality · ops/12_validation",
                  "DQ 규칙·대사 구현, field-level lineage 그래프는 미구현"),
    "GOV-003": _C("covered", "risk_lib.audit_trail · references",
                  "audit_ledger.json · ops/58_explainability"),
    "GOV-004": _C("covered", "risk_lib.validation.backtest · model_risk",
                  "ops/02_pd · ops/17_model_risk"),
    "GOV-005": _C("covered", "risk_lib.validation.cross_domain · stress.*",
                  "ops/09_stress · ops/52_final_attestation"),
    "GOV-006": _C("partial", "risk_lib.frtb · sensitivities",
                  "ops/56_frtb_ima · ops/54_trading_sensitivities",
                  "백테스트·PLAT 구현, 가격모형 독립검증(IPV) 게이트는 미구현"),
    "GOV-007": _C("covered", ".claude/agents/* · AIMS_POLICY.md",
                  "docs/aims_audits/*"),
    "GOV-008": _C("partial", "risk_lib.repro (git_commit) · tests/",
                  "manifest.json",
                  "코드 버전·골든 회귀 고정 구현, 변경승인 게이트 workflow는 미구현"),
    "GOV-009": _C("covered", "risk_lib.audit_trail",
                  "audit_ledger.json · ops/52_final_attestation"),
    # ---- AI 거버넌스 (AIG) ----------------------------------------------
    "AIG-001": _C("covered", "risk_lib.model_inventory · AIMS_POLICY.md §3",
                  "ops/57_model_inventory"),
    "AIG-002": _C("covered", ".claude/agents (tools 화이트리스트 · risk-validator는 Bash/Read 전용)",
                  "AIMS_POLICY.md §3"),
    "AIG-003": _C("covered", ".claude/agents (각 에이전트 AIMS 거버넌스 — 권고까지만)",
                  "AIMS_POLICY.md §2-1"),
    "AIG-004": _C("covered", ".claude/agents/risk-orchestrator (검증·심사 게이트)",
                  "ops/52_final_attestation (3단 서명란)"),
    "AIG-005": _C("covered", ".claude/agents frontmatter tools 필드",
                  "AIMS_POLICY.md §3"),
    "AIG-006": _C("backlog", "", "", "DLP·마스킹 미구현 (합성 데이터만 사용하므로 현 범위 밖)"),
    "AIG-007": _C("partial", "risk_lib.audit_trail",
                  "audit_ledger.json",
                  "산출 수치의 계보는 기록, Prompt·Tool·Output 전구간 로그는 하니스 밖(런타임 계층)"),
    "AIG-008": _C("covered", "tests/ (골든 회귀 582건)",
                  "ops/12_validation"),
    "AIG-009": _C("platform", "", "", "Kill Switch는 런타임 오케스트레이션 계층 책임"),
    "AIG-010": _C("platform", "", "", "LLM 모델 변경관리는 플랫폼 계층 책임"),
    "AIG-011": _C("covered", "risk_lib.explainability · references · abbreviations",
                  "ops/58_explainability · 전 페이지 인용 표기"),
    "AIG-012": _C("covered", "AIMS_POLICY.md §2-1 · 결재 서명란",
                  "ops/52_final_attestation"),
    # ---- 데이터 (RDM · DAT) ---------------------------------------------
    "RDM-001": _C("platform", "", "", "원천 수집·등록은 커넥터 계층"),
    "RDM-002": _C("partial", "risk_lib.pipeline (결정론적 집계)",
                  "ops/01_portfolio",
                  "집계 파이프라인 구현, 사용자 Rule Studio UI는 플랫폼 계층"),
    "RDM-003": _C("partial", "risk_lib.data_gen (canonical 스키마)",
                  "ops/01_portfolio",
                  "canonical 포트폴리오 스키마 고정, 원천 매핑 스튜디오는 플랫폼 계층"),
    "RDM-004": _C("covered", "risk_lib.data_quality · validation.consistency",
                  "ops/25_data_quality"),
    "RDM-005": _C("covered", "risk_lib.validation.consistency · cross_domain",
                  "ops/12_validation · ops/52_final_attestation"),
    "RDM-006": _C("partial", "risk_lib.repro (스냅샷 지문·버전)",
                  "manifest.json",
                  "포트폴리오 단위 스냅샷 지문 구현, field 단위 lineage는 미구현"),
    "RDM-007": _C("partial", "risk_lib.notifications",
                  "ops/25_data_quality",
                  "예외 경보 구현, 조치 workflow·티켓 연계는 플랫폼 계층"),
    "RDM-008": _C("platform", "", "", "자연어 조회조건 compiler는 플랫폼 계층"),
    "DAT-001": _C("covered", "risk_lib.data_gen (canonical risk data model)",
                  "ops/01_portfolio · ops/25_data_quality"),
    "DAT-002": _C("covered", "risk_lib.pipeline (asof 주입)",
                  "manifest.json (parameters.asof)"),
    "DAT-003": _C("partial", "risk_lib.audit_trail (figure→module→citation)",
                  "audit_ledger.json",
                  "산출 수치 계보 구현, 원천 필드까지의 lineage는 미구현"),
    "DAT-004": _C("covered", "risk_lib.repro.portfolio_fingerprint · RunManifest",
                  "manifest.json"),
    "DAT-005": _C("covered", "risk_lib.data_quality",
                  "ops/25_data_quality"),
    "DAT-006": _C("backlog", "", "", "수동조정(manual adjustment) 원장 미구현"),
    "DAT-007": _C("covered", "risk_lib.validation.consistency",
                  "ops/12_validation"),
    "DAT-008": _C("platform", "", "", "보존·폐기·비식별은 데이터 플랫폼 정책"),
    # ---- 비기능 (NFR) ---------------------------------------------------
    "NFR-001": _C("platform", "", "", "배포모델은 인프라 계층"),
    "NFR-002": _C("platform", "", "", "암호화·키관리는 인프라 계층"),
    "NFR-003": _C("partial", ".claude/agents (역할 분리: 산출·검증·심사)",
                  "AIMS_POLICY.md §3",
                  "에이전트 직무분리 구현, 시스템 RBAC은 플랫폼 계층"),
    "NFR-004": _C("partial", "risk_lib.audit_trail (append-only 원장)",
                  "audit_ledger.json",
                  "append-only 구조, 불변 저장(WORM)은 인프라 계층"),
    "NFR-005": _C("platform", "", "", "성능·처리량 SLA는 플랫폼 계층"),
    "NFR-006": _C("platform", "", "", "가용성·복구는 인프라 계층"),
    "NFR-007": _C("platform", "", "", "확장성은 인프라 계층"),
    "NFR-008": _C("partial", "risk_lib.intraday · notifications",
                  "ops/61_intraday",
                  "리스크 지표 모니터링 구현, 시스템 observability는 플랫폼 계층"),
    "NFR-009": _C("covered", "risk_lib.repro (seed·asof·지문·digest)",
                  "manifest.json · ops/58_explainability"),
    "NFR-010": _C("platform", "", "", "보안검증은 플랫폼 계층"),
    "NFR-011": _C("partial", "risk_lib.html_exec · printable (한글 렌더·인쇄)",
                  "executive.html · printable.html",
                  "가독성·인쇄 대응, WCAG 접근성 검증은 미수행"),
    "NFR-012": _C("partial", "tests/ · git",
                  "manifest.json (git_commit)",
                  "골든 회귀·버전 고정, 배포 Rollback은 플랫폼 계층"),
}

# 플랫폼 계층 요건군 — 산출 하니스 범위 밖 (기본값).
_PLATFORM_PREFIX = {
    "PLT": "플랫폼 아키텍처 계층 (커넥터·데이터마트·RAG·UI 스튜디오)",
    "INT": "연계 인터페이스 계층 (커넥터·API·IAM·티켓)",
    "COM": "상업·GTM 계층 (가격·계약·Funnel)",
}


# 요건 ↔ 담당 팀 에이전트 (.claude/agents). 산출 책임의 소재를 명시한다 —
# 주인 없는 요건은 아무도 산출하지 않는다.
AGENT_OWNER: dict[str, str] = {
    "PRD-CRM": "credit-rating-modeler",
    "PRD-RWA": "rwa-calculator",
    "PRD-ECL": "ifrs9-ecl-analyst",
    "PRD-ST":  "stress-test-engineer",
    "PRD-CAP": "bis-ratio-analyst",
    "PRD-MKT": "market-risk-analyst",
    "PRD-VAL": "risk-validator",
    "PRD-AIG": "aims-compliance-auditor",
    "PRD-RDM": "risk-orchestrator",
    "PRD-OPR": "risk-orchestrator",
    "PRD-ALM": "stress-test-engineer",
    "PRD-NCR": "prudential-capital-analyst",
}

# 개별 요건 단위 예외 (제품 기본값과 다른 담당).
_AGENT_OVERRIDE: dict[str, str] = {
    "BNK-CAP-002": "rapm-analyst",
    "BNK-ST-005":  "limit-manager",
    "BNK-CRM-009": "delinquency-pd-lgd-monitor",
    "BNK-OTH-002": "market-risk-analyst",
    "GOV-006":     "market-risk-analyst",
    "SEC-CCR-001": "market-risk-analyst",
    "SEC-CCR-002": "market-risk-analyst",
    "SEC-CCR-003": "market-risk-analyst",
}


def agent_owner(req_id: str, product_id: str) -> str:
    """요건의 담당 에이전트 — 미배정이면 빈 문자열."""
    if req_id in _AGENT_OVERRIDE:
        return _AGENT_OVERRIDE[req_id]
    return AGENT_OWNER.get(product_id, "")


def coverage_for(req_id: str) -> Coverage:
    """요건 ID의 커버리지 — 미등록 접두사는 플랫폼 계층 기본값."""
    if req_id in COVERAGE:
        return COVERAGE[req_id]
    prefix = req_id.split("-")[0]
    if prefix in _PLATFORM_PREFIX:
        return Coverage("platform", "", "", _PLATFORM_PREFIX[prefix])
    return Coverage("backlog", "", "", "커버리지 미평가")


def coverage_frame():
    """요건 126건 × 커버리지 DataFrame."""
    import pandas as pd
    rows = []
    for r in load_requirements():
        c = coverage_for(r["id"])
        rows.append({
            "id": r["id"], "title": r["title"], "product": r["product"],
            "suite": product_suite(r["product"]),
            "priority": r["priority"], "stage": r["stage"], "type": r["type"],
            "owner": agent_owner(r["id"], r["product"]),
            "status": c.status, "modules": c.modules, "pages": c.pages,
            "gap": c.gap,
        })
    return pd.DataFrame(rows)


def product_suite(product_id: str) -> str:
    for p in PRODUCTS:
        if p.id == product_id:
            return p.suite
    return ""


def coverage_summary() -> dict[str, int]:
    """상태별 요건 수."""
    df = coverage_frame()
    return {k: int(v) for k, v in df["status"].value_counts().items()}


def in_scope_ratio() -> float:
    """산출 하니스 범위(covered+partial+backlog) 중 covered 비율.

    플랫폼 계층 요건은 분모에서 제외한다 — 이 하니스가 책임지지 않는 요건을
    분모에 넣으면 커버리지가 부당하게 낮게 보인다.
    """
    df = coverage_frame()
    scoped = df[df["status"] != "platform"]
    if scoped.empty:
        return 0.0
    return float((scoped["status"] == "covered").sum()) / len(scoped)
