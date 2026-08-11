"""RYNTA BRD Level 1 업무요건 → 적합성검증 기준 항목 생성기.

`harness/domain_requirement_criteria.json`을 만든다. 손으로 고치지 않는다:
원문 레지스터가 바뀌면 이 생성기를 다시 돌린다.

근거(evidence)는 **하니스에 실재하는 파일만** 선언한다. 실재하지 않으면
`automated`로 주장할 수 없고 `manual`(사람 검토) 또는 `out_of_scope`(하니스
범위 밖)로 남긴다. `tools.domain_criteria verify`가 이를 강제한다.

사용:
    python -m tools.gen_domain_criteria --out harness/domain_requirement_criteria.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

SOURCE = "RYNTA_Business_Requirements_v9.6.0.html"
SOURCE_SHA256 = "e1a8daa2907c445effc1488a7d7a052d4844d2bd253f285653823be189c0dd16"
SOURCE_REGISTER = "risk_lib/regulatory/requirements_v960.py (리스크관리 팀에이전트)"

# 요건정의 마스터 8부문: CLAUDE.md §2
SECTIONS = {
    "01": "RDM·BIS비율",
    "02": "신용리스크·RWA",
    "03": "IFRS 9 ECL",
    "04": "시장리스크",
    "05": "ALM·IRRBB·유동성",
    "06": "운영리스크",
    "07": "통합위기상황분석",
    "08": "리스크 적합성검증",
    "--": "부문 미귀속 (플랫폼·상업·연계)",
}

# 검증 관점: CLAUDE.md §2 "부문 공통으로 검증 대상에 포함한다"
LENSES = ("데이터", "산식", "방법론", "내부통제", "문서화")

# (req_id, 원문 제목, 업권, 우선순위): requirements_v960.REQUIREMENTS 131건
REGISTER = (
    ("AIG-001", "AI 사용사례·위험등급 등록", "공통", "Must"),
    ("AIG-002", "Read-only 기본권한", "공통", "Must"),
    ("AIG-003", "Recommend-only 판단", "공통", "Must"),
    ("AIG-004", "Approval-first 실행", "공통", "Must"),
    ("AIG-005", "Tool Registry·최소권한", "공통", "Must"),
    ("AIG-006", "DLP·마스킹", "공통", "Must"),
    ("AIG-007", "Prompt·Tool·Output 전구간 로그", "공통", "Must"),
    ("AIG-008", "내부 평가셋·회귀테스트", "공통", "Must"),
    ("AIG-009", "Kill Switch·수동대체", "공통", "Must"),
    ("AIG-010", "LLM·모델 변경관리", "공통", "Must"),
    ("AIG-011", "근거·한계 표시", "공통", "Must"),
    ("AIG-012", "Human-in-the-loop 최종판단", "공통", "Must"),
    ("RDM-001", "유연한 원천 수집·등록", "공통", "Must"),
    ("RDM-002", "집계·가공 Rule Studio", "공통", "Must"),
    ("RDM-003", "Canonical Mapping·표준화", "공통", "Must"),
    ("RDM-004", "DQ Validation·Quality Gate", "공통", "Must"),
    ("RDM-005", "원천–산출–보고 Reconciliation", "공통", "Must"),
    ("RDM-006", "Field Lineage·Versioned Snapshot", "공통", "Must"),
    ("RDM-007", "데이터 예외·조치 Workflow", "공통", "Must"),
    ("RDM-008", "권한형 자연어 조회조건", "공통", "Must"),
    ("BNK-CAP-001", "BIS·Constraint", "은행", "Should"),
    ("BNK-CAP-002", "RAROC·거래전 의사결정", "은행", "Should"),
    ("BNK-CRE-001", "PD·LGD·EAD·CCF", "은행", "Must"),
    ("BNK-CRE-002", "SA/IRB RWA", "은행", "Must"),
    ("BNK-CRE-003", "신용위험경감(CRM)·CCF·법률", "은행", "Must"),
    ("BNK-CRE-004", "Stage·SICR", "은행", "Must"),
    ("BNK-CRE-005", "ECL 측정·시나리오", "은행", "Must"),
    ("BNK-CRE-006", "PMA·IRB–ECL·GL", "은행", "Must"),
    ("BNK-CRM-001", "공통 거버넌스", "은행", "Must"),
    ("BNK-CRM-002", "CSS Life Cycle", "은행", "Must"),
    ("BNK-CRM-003", "CSS 데이터·Target", "은행", "Must"),
    ("BNK-CRM-004", "CSS Scorecard", "은행", "Must"),
    ("BNK-CRM-005", "CSS 검증·전략", "은행", "Must"),
    ("BNK-CRM-006", "기업 재무모형", "은행", "Must"),
    ("BNK-CRM-007", "기업 비재무·대표자", "은행", "Must"),
    ("BNK-CRM-008", "기업 결합·Master Scale", "은행", "Must"),
    ("BNK-CRM-009", "기업 Override·EWS", "은행", "Must"),
    ("BNK-OTH-001", "운영리스크", "은행", "Should"),
    ("BNK-OTH-002", "시장·CCR/XVA", "은행", "Should"),
    ("BNK-OTH-003", "IRRBB·유동성", "은행", "Should"),
    ("BNK-OTH-004", "AI·기후·전략·평판", "은행", "Should"),
    ("BNK-ST-001", "Risk inventory·내부자본", "은행", "Must"),
    ("BNK-ST-002", "시나리오·TD/BU", "은행", "Must"),
    ("BNK-ST-003", "Cross-risk 전이", "은행", "Must"),
    ("BNK-ST-004", "손익·RWA·자본", "은행", "Must"),
    ("BNK-ST-005", "한도·경영조치", "은행", "Must"),
    ("BNK-ST-006", "Reverse Stress", "은행", "Must"),
    ("BNK-ST-007", "실행·Evidence", "은행", "Must"),
    ("COM-001", "고객·계약 가정", "공통", "Should"),
    ("COM-002", "순구축대가 산정", "공통", "Should"),
    ("COM-003", "ARR·Lifecycle·1년차·TCO 산정", "공통", "Should"),
    ("COM-004", "패키지 Preset", "공통", "Should"),
    ("COM-005", "Lifecycle 요율", "공통", "Should"),
    ("COM-006", "가격 승인·가정 표시", "공통", "Should"),
    ("COM-007", "ROI 이중계상 방지", "공통", "Could"),
    ("COM-008", "GTM Funnel 관리", "공통", "Could"),
    ("DAT-001", "Canonical Risk Data Model", "공통", "Must"),
    ("DAT-002", "기준일·유효기간", "공통", "Must"),
    ("DAT-003", "Source-to-report Lineage", "공통", "Must"),
    ("DAT-004", "Source Registry·Snapshot", "공통", "Must"),
    ("DAT-005", "DQ 규칙", "공통", "Must"),
    ("DAT-006", "수동조정 원장", "공통", "Must"),
    ("DAT-007", "원천–산출–보고 대사", "공통", "Must"),
    ("DAT-008", "보존·폐기·비식별", "공통", "Must"),
    ("GOV-001", "데이터 원천·기준시점 통제", "공통", "Must"),
    ("GOV-002", "DQ·Lineage 통제", "공통", "Must"),
    ("GOV-003", "산식·계산엔진 통제", "공통", "Must"),
    ("GOV-004", "신용평가모형 통제", "공통", "Must"),
    ("GOV-005", "통합 ST 통제", "공통", "Must"),
    ("GOV-006", "Market/Pricing 통제", "공통", "Must"),
    ("GOV-007", "AI/Agentic 통제", "공통", "Must"),
    ("GOV-008", "변경·Lifecycle 통제", "공통", "Must"),
    ("GOV-009", "Evidence·감사 통제", "공통", "Must"),
    ("INT-001", "Read-only Secure Connector", "공통", "Must"),
    ("INT-002", "파일·API·배치 연계", "공통", "Must"),
    ("INT-003", "계산엔진 Adapter", "공통", "Must"),
    ("INT-004", "시장데이터 Adapter", "공통", "Must"),
    ("INT-005", "IAM·SSO 연계", "공통", "Must"),
    ("INT-006", "Workflow·Ticket 연계", "공통", "Must"),
    ("INT-007", "보고서 Export", "공통", "Must"),
    ("INT-008", "재시도·멱등성·오류격리", "공통", "Must"),
    ("NFR-001", "배포모델", "공통", "Must"),
    ("NFR-002", "암호화·키관리", "공통", "Must"),
    ("NFR-003", "RBAC·직무분리", "공통", "Must"),
    ("NFR-004", "감사로그 불변성", "공통", "Must"),
    ("NFR-005", "성능·처리량", "공통", "Must"),
    ("NFR-006", "가용성·복구", "공통", "Must"),
    ("NFR-007", "확장성", "공통", "Must"),
    ("NFR-008", "Observability", "공통", "Must"),
    ("NFR-009", "재현성", "공통", "Must"),
    ("NFR-010", "보안검증", "공통", "Must"),
    ("NFR-011", "접근성·사용성", "공통", "Must"),
    ("NFR-012", "변경·배포·Rollback", "공통", "Must"),
    ("PLT-001", "Secure Connectors", "공통", "Must"),
    ("PLT-002", "Risk Data Mart", "공통", "Must"),
    ("PLT-003", "Evidence & Knowledge", "공통", "Must"),
    ("PLT-004", "Calculation & Validation", "공통", "Must"),
    ("PLT-005", "Scenario & Pricing", "공통", "Must"),
    ("PLT-006", "RAG & Agentic", "공통", "Must"),
    ("PLT-007", "Control & Observability", "공통", "Must"),
    ("PLT-008", "Reporting & Lifecycle", "공통", "Must"),
    ("PLT-009", "공통 자연어 조회조건 Compiler", "공통", "Must"),
    ("PLT-010", "정형 UI · Governed Schema", "공통", "Must"),
    ("PLT-011", "비정형 UI · Prompt-composable Layout", "공통", "Must"),
    ("PLT-012", "UI Preview·검증·승인·Rollback", "공통", "Must"),
    ("PLT-013", "Unauthorized Field·Layout 차단", "공통", "Must"),
    ("PLT-014", "F 적합성검증 포트폴리오 · Unified Run Context", "공통", "Must"),
    ("PLT-015", "Alert-to-Action Policy Binding", "공통", "Must"),
    ("PLT-016", "Pre-execution Hold · Scoped Kill Switch", "증권", "Must"),
    ("PLT-017", "Object-based 4-Eyes · Segregation of Duties", "공통", "Must"),
    ("PLT-018", "Evidence Drill-down · Version Diff · Replay Snapshot", "공통", "Must"),
    ("SEC-CCR-001", "Netting·담보·Exposure", "증권", "Should"),
    ("SEC-CCR-002", "XVA", "증권", "Should"),
    ("SEC-CCR-003", "Margin·Collateral", "증권", "Should"),
    ("SEC-LIQ-001", "Repo·단기조달", "증권", "Should"),
    ("SEC-LIQ-002", "Liquidity Stress·CFP", "증권", "Should"),
    ("SEC-MKT-001", "VaR/ES·Stress", "증권", "Must"),
    ("SEC-MKT-002", "Sensitivities·FRTB형 분석", "증권", "Must"),
    ("SEC-MKT-003", "P&L Attribution·한도", "증권", "Must"),
    ("SEC-NCR-001", "적용범위·인가", "증권", "Must"),
    ("SEC-NCR-002", "영업용순자본", "증권", "Must"),
    ("SEC-NCR-003", "총위험액", "증권", "Must"),
    ("SEC-NCR-004", "전월·공시 대사", "증권", "Must"),
    ("SEC-OAI-001", "운영손실·RCSA/KRI", "증권", "Should"),
    ("SEC-OAI-002", "AI·모델거버넌스", "증권", "Should"),
    ("SEC-OAI-003", "Agentic Close Workflow", "증권", "Should"),
    ("SEC-PRC-001", "시장데이터", "증권", "Must"),
    ("SEC-PRC-002", "상품명세·Pricing Model", "증권", "Must"),
    ("SEC-PRC-003", "가격·Greeks 회귀", "증권", "Must"),
    ("SEC-PRC-004", "Curve·Vol·Calibration", "증권", "Must"),
    ("SEC-PRC-005", "IPV·Valuation Adjustment", "증권", "Must"),
)

# req_id → (부문, 검증 관점, 검증 기준, 자동화, 근거 파일, 비고)
#
# 근거는 하니스에 실재하는 파일만 적는다. 자동 통제가 없으면 automated 로
# 주장하지 않는다: 통과가 곧 구현이 아니다 (지적 F-D01 유형).
MAP: dict[str, tuple] = {
    # ---- AIG · AI 거버넌스 → 부문 08 (검증 체계 자체)
    "AIG-001": ("08", ("내부통제",), "AI 사용사례가 중요도 등급과 함께 등록되고 등급별 최소 검증 심도·주기가 강제되는가", "automated", ("harness/model_materiality.json", "tools/validation_scope.py"), ""),
    "AIG-002": ("08", ("내부통제",), "기본 권한이 read-only 이고 쓰기 권한이 활동별로 열리는가", "automated", ("harness/permission_matrix.json", "middleware/permission_guard.py"), ""),
    "AIG-003": ("08", ("내부통제", "문서화"), "산출물이 권고에 머무르고 확정 판정을 스스로 내리지 않는가", "automated", ("harness/validation_policy.md", "middleware/draft_watermark_guard.py"), ""),
    "AIG-004": ("08", ("내부통제",), "실행 전 승인이 선행되고 자동 승격이 차단되는가", "automated", ("tools/conditional_approval.py", "tools/manifest.py"), ""),
    "AIG-005": ("08", ("내부통제",), "도구 목록과 활동별 최소권한이 SSoT 로 관리되는가", "automated", ("harness/permission_matrix.json", "harness/permission_policy.md"), ""),
    "AIG-006": ("08", ("데이터", "내부통제"), "개인식별정보가 입력·산출 양쪽에서 차단되는가", "automated", ("middleware/data_safety_guard.py",), ""),
    "AIG-007": ("08", ("내부통제",), "프롬프트·도구호출·산출이 전구간 로그로 남는가", "automated", ("middleware/run_logger.py",), ""),
    "AIG-008": ("08", ("방법론",), "내부 평가셋으로 회귀검증이 배포 전 전량 실행되는가", "automated", ("harness/golden_cases.json", "tools/golden_regression.py"), ""),
    "AIG-009": ("08", ("내부통제",), "실행 중단·수동대체 경로가 존재하는가", "manual", (), "하니스에 kill switch 구현이 없다: 운영 플랫폼 통제이며 사람 확인 항목으로 남긴다"),
    "AIG-010": ("08", ("내부통제",), "모델·프롬프트 변경이 사유·증거·롤백 기준과 함께 기록되는가", "automated", ("harness/change_manifest.json", "tools/manifest.py"), ""),
    "AIG-011": ("08", ("문서화",), "모든 산출물에 근거와 한계가 표시되는가", "automated", ("middleware/output_completeness_guard.py", "memory/known_limitations.json"), ""),
    "AIG-012": ("08", ("내부통제",), "최종 판단이 인간에게 유보되는가", "automated", ("harness/validation_policy.md", "docs/human_in_the_loop.md"), ""),

    # ---- RDM · 리스크 데이터 관리 → 부문 01
    "RDM-001": ("01", ("데이터",), "운영 추출 파일이 안전 경계를 거쳐 적재되는가", "automated", ("tools/data_adapter.py",), ""),
    "RDM-002": ("01", ("데이터",), "집계·가공 규칙이 사람이 검토 가능한 형태로 관리되는가", "manual", (), "Rule Studio 는 플랫폼 기능: 하니스는 규칙 산출물만 검증한다"),
    "RDM-003": ("01", ("데이터",), "표준 항목 정의가 SSoT 로 존재하고 매핑이 대조되는가", "automated", ("harness/data_definition.md",), ""),
    "RDM-004": ("01", ("데이터",), "스키마·품질 게이트가 실행 전에 걸리는가", "automated", ("middleware/schema_guard.py", "tools/data_profile.py"), ""),
    "RDM-005": ("01", ("데이터", "산식"), "원천-산출-보고 값이 대사되고 차이가 설명되는가", "automated", ("tools/provenance.py",), ""),
    "RDM-006": ("01", ("데이터",), "항목 계보와 버전 스냅샷이 재현 가능한 형태로 남는가", "automated", ("tools/provenance.py", "tools/pack_verify.py"), ""),
    "RDM-007": ("01", ("내부통제",), "데이터 예외가 조치 원장으로 추적되고 종결 요건이 강제되는가", "automated", ("tools/validation_finding.py",), ""),
    "RDM-008": ("01", ("내부통제",), "조회조건이 권한 범위를 넘지 않는가", "manual", (), "자연어 조회 컴파일러는 플랫폼 기능: 하니스에 대응 통제가 없다"),

    # ---- DAT · 데이터 요건 → 부문 01
    "DAT-001": ("01", ("데이터",), "표준 리스크 데이터 모형이 정의되고 산출이 그 정의를 따르는가", "automated", ("harness/data_definition.md",), ""),
    "DAT-002": ("01", ("데이터", "내부통제"), "기준일·유효기간이 규칙 단위로 분리 관리되는가", "automated", ("tools/reg_rules.py", "harness/regulatory_rule_catalog.json"), ""),
    "DAT-003": ("01", ("데이터",), "원천에서 보고까지 계보가 끊기지 않는가", "automated", ("tools/provenance.py",), ""),
    "DAT-004": ("01", ("데이터",), "원천 등록부와 스냅샷 해시로 입력이 고정되는가", "automated", ("tools/pack_verify.py",), ""),
    "DAT-005": ("01", ("데이터",), "품질 규칙이 코드로 존재하고 위반이 차단되는가", "automated", ("middleware/schema_guard.py",), ""),
    "DAT-006": ("01", ("데이터", "내부통제"), "수동조정이 사유·승인자와 함께 원장에 남고 제거 시 결론이 뒤집히는지 확인되는가", "manual", (), "하니스에 수동조정 원장이 없다: 적대적 검증 ADV-PROC-04 로만 다룬다"),
    "DAT-007": ("01", ("산식",), "원천·산출·보고 세 지점의 값이 대사되는가", "automated", ("tools/provenance.py",), ""),
    "DAT-008": ("01", ("내부통제",), "보존기간·폐기·비식별이 통제되는가", "automated", ("tools/audit_retention.py", "middleware/data_safety_guard.py"), ""),

    # ---- GOV · 거버넌스 통제 → 부문 08
    "GOV-001": ("08", ("데이터", "내부통제"), "데이터 원천과 기준시점이 산출물에 고정되어 재현되는가", "automated", ("tools/pack_verify.py",), ""),
    "GOV-002": ("08", ("데이터",), "품질·계보 통제가 실행 경로에 실제로 걸리는가", "automated", ("middleware/schema_guard.py", "tools/provenance.py"), ""),
    "GOV-003": ("08", ("산식",), "산식과 계산엔진이 독립 재계산으로 검증되는가", "automated", ("tools/independent_recalc.py",), ""),
    "GOV-004": ("02", ("방법론",), "신용평가모형의 성능·안정성·캘리브레이션이 정책 기준으로 점검되는가", "automated", ("harness/policies/credit_scoring.md", "skills/credit_scoring_validation.md"), ""),
    "GOV-005": ("07", ("방법론",), "통합 위기상황분석의 시나리오·전이 가정이 통제되는가", "automated", ("harness/policies/macro_scenario.md", "harness/scenario_floors.json"), ""),
    "GOV-006": ("04", ("방법론",), "시장·가격 산출의 방법론과 임계가 통제되는가", "automated", ("harness/policies/market_risk.md", "harness/market_risk_thresholds.json"), ""),
    "GOV-007": ("08", ("내부통제",), "AI·에이전트 실행이 권한·직무분리 통제 아래 있는가", "automated", ("harness/permission_matrix.json", "harness/sod_policy.json"), ""),
    "GOV-008": ("08", ("내부통제",), "변경이 제안-승인-검증-롤백 수명주기로 관리되는가", "automated", ("harness/change_manifest.json",), ""),
    "GOV-009": ("08", ("내부통제", "문서화"), "증빙과 감사 추적이 실행 단위로 남는가", "automated", ("tools/run_audit.py", "middleware/run_logger.py"), ""),

    # ---- BNK-CAP · 자본 → 부문 01
    "BNK-CAP-001": ("01", ("산식", "내부통제"), "CET1·기본자본·총자본·레버리지 비율과 완충자본 요구치가 재계산·대조되는가", "automated", ("harness/capital_adequacy_thresholds.json", "harness/policies/capital_adequacy.md", "src/vta/domains/capital.py"), ""),
    "BNK-CAP-002": ("01", ("방법론",), "RAROC 산정 가정과 거래전 의사결정 근거가 검증되는가", "manual", (), "하니스에 RAROC 산출·검증 경로가 없다"),

    # ---- BNK-CRE · 신용 → 부문 02·03
    "BNK-CRE-001": ("02", ("방법론", "산식"), "PD·LGD·EAD·CCF 추정과 검증 절차가 정책 기준을 충족하는가", "automated", ("harness/policies/pd_lgd_ead.md", "skills/pd_lgd_ead_validation.md"), ""),
    "BNK-CRE-002": ("02", ("산식",), "SA·IRB RWA 산출과 산출하한 적용이 재계산으로 확인되는가", "automated", ("harness/basel_risk_taxonomy.json", "harness/policies/capital_adequacy.md"), ""),
    "BNK-CRE-003": ("02", ("방법론", "문서화"), "신용위험경감의 적격성·법적 확실성이 확인되는가", "manual", (), "하니스에 CRM 적격성 판정 통제가 없다: 요청서 가정으로만 넘어온다"),
    "BNK-CRE-004": ("03", ("방법론",), "스테이지 배분과 SICR 판정 기준이 일관되게 적용되는가", "automated", ("harness/policies/ifrs9.md", "skills/ifrs9_ecl_validation.md"), ""),
    "BNK-CRE-005": ("03", ("산식", "방법론"), "ECL 측정과 시나리오 가중이 재계산·대조되는가", "automated", ("harness/policies/ifrs9.md", "tools/run_ifrs9_validation.py"), ""),
    "BNK-CRE-006": ("03", ("방법론", "내부통제"), "PMA·overlay 와 IRB-ECL 차이가 근거와 함께 설명되는가", "automated", ("harness/policies/ifrs9.md",), ""),

    # ---- BNK-CRM · 신용평가모형 → 부문 02
    "BNK-CRM-001": ("02", ("내부통제",), "모형 거버넌스 역할·승인 경로가 직무분리를 지키는가", "automated", ("harness/sod_policy.json", "middleware/sod_guard.py"), ""),
    "BNK-CRM-002": ("02", ("내부통제",), "모형 수명주기 단계별 산출물과 재검증 주기가 강제되는가", "automated", ("tools/validation_scope.py", "harness/model_materiality.json"), ""),
    "BNK-CRM-003": ("02", ("데이터",), "개발표본·목표변수 정의와 누수 차단이 확인되는가", "automated", ("middleware/leakage_guard.py", "middleware/sample_size_guard.py"), ""),
    "BNK-CRM-004": ("02", ("방법론",), "스코어카드 변별력·안정성·등급별 캘리브레이션이 임계로 판정되는가", "automated", ("tools/metric_ks_auc.py", "tools/metric_psi.py", "tools/binomial_calibration.py"), ""),
    "BNK-CRM-005": ("02", ("방법론",), "모형 검증 전략과 대안모형 대조가 수행되는가", "automated", ("skills/challenger_model_review.md", "harness/adversarial_protocol.json"), ""),
    "BNK-CRM-006": ("02", ("방법론",), "기업 재무모형의 변수 선택·추정이 검증되는가", "manual", (), "하니스에 기업 재무모형 전용 검증 절차가 없다: 일반 신용모형 절차로 대체 검토"),
    "BNK-CRM-007": ("02", ("방법론",), "비재무·대표자 평가 항목의 근거가 확인되는가", "manual", (), "정성 평가 항목: 자동 판정 불가, 사람 검토"),
    "BNK-CRM-008": ("02", ("산식",), "모형 결합과 마스터스케일 매핑이 재현되는가", "manual", (), "하니스에 마스터스케일 매핑 검증이 없다"),
    "BNK-CRM-009": ("02", ("내부통제",), "Override 와 조기경보의 승인·사후검증이 이루어지는가", "automated", ("harness/adversarial_protocol.json", "tools/validation_trigger.py"), ""),

    # ---- BNK-OTH · 기타 리스크
    "BNK-OTH-001": ("06", ("산식",), "운영리스크 SMA(BI·BIC·ILM) 산출과 손실자료 완전성이 확인되는가", "automated", ("harness/operational_risk_thresholds.json", "harness/policies/operational_risk.md", "src/vta/domains/operational.py"), ""),
    "BNK-OTH-002": ("04", ("산식",), "시장·CCR·CVA 산출이 재계산되고 임계로 판정되는가", "automated", ("harness/ccr_thresholds.json", "harness/cva_thresholds.json", "src/vta/domains/ccr.py", "src/vta/domains/cva.py"), ""),
    "BNK-OTH-003": ("05", ("산식",), "IRRBB(ΔEVE·ΔNII)와 유동성(LCR·NSFR)이 임계로 판정되는가", "automated", ("harness/irrbb_thresholds.json", "harness/liquidity_risk_thresholds.json", "src/vta/domains/irrbb.py", "src/vta/domains/liquidity.py"), ""),
    "BNK-OTH-004": ("--", ("방법론",), "AI·기후·전략·평판 리스크의 측정 가정이 검증되는가", "manual", (), "하니스에 해당 도메인 산출·검증 경로가 없다"),

    # ---- BNK-ST · 통합위기상황분석 → 부문 07
    "BNK-ST-001": ("07", ("방법론",), "리스크 인벤토리와 내부자본 산정이 연결되는가", "automated", ("harness/icaap_thresholds.json", "src/vta/domains/icaap.py"), ""),
    "BNK-ST-002": ("07", ("방법론",), "시나리오의 하향식·상향식 설계와 심도가 기준을 충족하는가", "automated", ("harness/scenario_floors.json", "harness/policies/macro_scenario.md"), ""),
    "BNK-ST-003": ("07", ("방법론",), "리스크 간 전이 경로가 모형에 반영되는가", "automated", ("skills/stress_test_validation.md",), ""),
    "BNK-ST-004": ("07", ("산식",), "시나리오가 손익·RWA·자본으로 전이되는 계산이 재현되는가", "automated", ("skills/stress_test_validation.md", "harness/scenario_floors.json"), ""),
    "BNK-ST-005": ("07", ("내부통제",), "한도 저촉 시 경영조치가 연결되는가", "manual", (), "경영조치 연계는 사람 결재 영역: 하니스는 저촉 사실만 표시한다"),
    "BNK-ST-006": ("07", ("방법론",), "역스트레스 임계 심도가 산출되고 독립 재산출 여부가 명시되는가", "manual", (), "시나리오 엔진을 재구현하지 않아 읽어 대조만 한다: 이월 CO-009 로 공시 중"),
    "BNK-ST-007": ("07", ("문서화",), "실행 증빙이 재현 가능한 형태로 남는가", "automated", ("tools/pack_verify.py", "middleware/run_logger.py"), ""),

    # ---- COM · 상업 (리스크검증 범위 밖)
    **{f"COM-{i:03d}": ("--", ("문서화",), "가격·수익 가정의 근거가 문서로 확인되는가", "out_of_scope", (), "상업·가격 요건: 리스크 적합성검증 범위 밖 (CLAUDE.md §2)") for i in range(1, 9)},

    # ---- INT · 연계
    "INT-001": ("--", ("내부통제",), "외부 연계가 read-only 로 제한되는가", "out_of_scope", (), "플랫폼 연계 요건: 하니스는 연계 결과물만 검증한다"),
    "INT-002": ("--", ("데이터",), "파일·API·배치 연계의 무결성이 확인되는가", "out_of_scope", (), "플랫폼 연계 요건"),
    "INT-003": ("--", ("산식",), "계산엔진 어댑터가 산출값을 변형하지 않는가", "out_of_scope", (), "플랫폼 연계 요건: 산출값 자체는 GOV-003 으로 검증"),
    "INT-004": ("--", ("데이터",), "시장데이터 어댑터의 출처·기준시점이 기록되는가", "out_of_scope", (), "플랫폼 연계 요건"),
    "INT-005": ("--", ("내부통제",), "IAM·SSO 연계가 권한 모형과 일치하는가", "out_of_scope", (), "플랫폼 연계 요건"),
    "INT-006": ("--", ("내부통제",), "조치 워크플로가 티켓으로 추적되는가", "out_of_scope", (), "플랫폼 연계 요건: 하니스는 Finding 원장으로 대체 (RDM-007)"),
    "INT-007": ("08", ("문서화",), "보고서 export 가 원본 산출물과 일치하는가", "automated", ("tools/report_export.py",), ""),
    "INT-008": ("--", ("내부통제",), "재시도·멱등성·오류격리가 보장되는가", "out_of_scope", (), "플랫폼 비기능 요건"),

    # ---- NFR · 비기능
    "NFR-001": ("--", ("내부통제",), "배포모델이 승인된 형태인가", "out_of_scope", (), "인프라 요건: 하니스 범위 밖"),
    "NFR-002": ("--", ("내부통제",), "암호화·키관리가 기준을 충족하는가", "out_of_scope", (), "인프라 요건: 하니스 범위 밖"),
    "NFR-003": ("08", ("내부통제",), "역할 기반 접근과 직무분리가 강제되는가", "automated", ("harness/sod_policy.json", "middleware/sod_guard.py"), ""),
    "NFR-004": ("08", ("내부통제",), "감사로그가 append-only 로 보존되는가", "automated", ("middleware/run_logger.py", "tools/audit_retention.py"), ""),
    "NFR-005": ("08", ("방법론",), "처리 성능이 측정되고 기준과 대조되는가", "automated", ("tools/benchmark.py",), ""),
    "NFR-006": ("--", ("내부통제",), "가용성·복구 목표가 충족되는가", "out_of_scope", (), "인프라 요건: 하니스 범위 밖"),
    "NFR-007": ("--", ("내부통제",), "확장성 요건이 충족되는가", "out_of_scope", (), "인프라 요건: 하니스 범위 밖"),
    "NFR-008": ("08", ("내부통제",), "실행 상태와 거버넌스 지표가 관측 가능한가", "automated", ("tools/dashboard.py", "tools/governance_kpi.py"), ""),
    "NFR-009": ("08", ("내부통제",), "동일 입력·동일 버전에서 산출물이 재현되는가", "automated", ("tools/pack_verify.py",), ""),
    "NFR-010": ("08", ("내부통제",), "보안 점검(개인정보·누수)이 실행 경로에 걸리는가", "automated", ("middleware/data_safety_guard.py", "middleware/leakage_guard.py"), ""),
    "NFR-011": ("--", ("문서화",), "접근성·사용성 기준이 충족되는가", "out_of_scope", (), "UI 요건: 하니스 범위 밖"),
    "NFR-012": ("08", ("내부통제",), "변경·배포·롤백 기준이 기록되고 지켜지는가", "automated", ("harness/change_manifest.json", "tools/manifest.py"), ""),

    # ---- PLT · 플랫폼
    "PLT-001": ("--", ("내부통제",), "커넥터 보안 요건이 충족되는가", "out_of_scope", (), "플랫폼 구성요소: 하니스 범위 밖"),
    "PLT-002": ("--", ("데이터",), "데이터 마트 구성이 표준 모형을 따르는가", "out_of_scope", (), "플랫폼 구성요소: 정의 검증은 DAT-001"),
    "PLT-003": ("08", ("문서화",), "증빙이 산출물에서 원천까지 추적되는가", "automated", ("tools/provenance.py",), ""),
    "PLT-004": ("08", ("산식",), "계산과 검증이 분리되어 독립 재계산이 가능한가", "automated", ("tools/independent_recalc.py",), ""),
    "PLT-005": ("--", ("방법론",), "시나리오·가격 엔진이 승인된 방법론을 따르는가", "out_of_scope", (), "플랫폼 구성요소: 방법론 검증은 GOV-005·GOV-006"),
    "PLT-006": ("--", ("방법론",), "검색증강·에이전트 구성이 통제되는가", "out_of_scope", (), "플랫폼 구성요소: 권한 통제는 AIG-005"),
    "PLT-007": ("08", ("내부통제",), "통제와 관측이 실행 단위로 작동하는가", "automated", ("middleware/run_logger.py", "tools/run_audit.py"), ""),
    "PLT-008": ("08", ("문서화",), "보고와 수명주기 관리가 산출물로 연결되는가", "automated", ("tools/report_pack.py", "tools/pack_archive.py"), ""),
    "PLT-009": ("--", ("내부통제",), "조회조건 컴파일러가 권한을 넘지 않는가", "out_of_scope", (), "플랫폼 구성요소: 하니스 범위 밖"),
    "PLT-010": ("--", ("내부통제",), "정형 UI 가 통제된 스키마만 노출하는가", "out_of_scope", (), "UI 요건: 하니스 범위 밖"),
    "PLT-011": ("--", ("내부통제",), "비정형 UI 구성이 승인 범위를 넘지 않는가", "out_of_scope", (), "UI 요건: 하니스 범위 밖"),
    "PLT-012": ("--", ("내부통제",), "UI 변경이 검증·승인·롤백을 거치는가", "out_of_scope", (), "UI 요건: 변경통제 자체는 NFR-012"),
    "PLT-013": ("--", ("내부통제",), "미승인 항목·레이아웃이 차단되는가", "out_of_scope", (), "UI 요건: 하니스 범위 밖"),
    "PLT-014": ("08", ("내부통제",), "적합성검증 실행이 단일 Run Context 로 묶이고 계획 대비 실제 실행이 감사되는가", "automated", ("harness/orchestration_matrix.json", "tools/run_audit.py"), "부문 08 의 핵심 요건: 본 하니스의 자기 부문"),
    "PLT-015": ("08", ("내부통제",), "임계 위반이 정책에 묶인 조치로 전환되는가", "automated", ("harness/validation_triggers.json", "tools/validation_trigger.py"), ""),
    "PLT-016": ("--", ("내부통제",), "실행 전 보류와 범위 한정 중단이 가능한가", "out_of_scope", (), "증권 업권 플랫폼 요건: 본 하니스는 은행 부문"),
    "PLT-017": ("08", ("내부통제",), "객체 단위 4-eyes 와 직무분리가 강제되는가", "automated", ("harness/sod_policy.json", "middleware/sod_guard.py"), ""),
    "PLT-018": ("08", ("문서화",), "증빙 드릴다운·버전 비교·재현 스냅샷이 제공되는가", "automated", ("tools/pack_diff.py", "tools/pack_verify.py"), ""),

    # ---- SEC · 증권 업권 (본 하니스는 은행 부문)
    **{rid: ("--", ("방법론",), title + " 산출·검증 절차가 기준을 충족하는가", "out_of_scope", (), "증권 업권 요건: 본 하니스의 검증 범위는 은행 8부문 (CLAUDE.md §2)")
       for rid, title, _scope, _pri in REGISTER if rid.startswith("SEC-")},
}


def build() -> dict:
    items = []
    for rid, title, scope, priority in REGISTER:
        section, lenses, criterion, automation, evidence, note = MAP[rid]
        items.append({
            "req_id": rid,
            "title": title,
            "scope": scope,
            "priority": priority,
            "section": section,
            "section_name": SECTIONS[section],
            "lens": list(lenses),
            "criterion": criterion,
            "automation": automation,
            "evidence": list(evidence),
            "note": note,
        })
    return {
        "schema_version": "1.0",
        "policy_version": "1.0",
        "source": SOURCE,
        "source_sha256": SOURCE_SHA256,
        "source_register": SOURCE_REGISTER,
        "description": (
            "RYNTA BRD Level 1 도메인 업무요건 131건을 적합성검증 기준 항목으로 "
            "전개한 것. automation='automated' 는 하니스에 자동 통제가 실재함을 "
            "뜻하며 evidence 파일이 실재해야만 주장할 수 있다 "
            "(tools.domain_criteria verify 가 강제). 'manual' 은 통제가 없어 사람 "
            "검토로 남긴 항목, 'out_of_scope' 는 은행 8부문 검증 범위 밖이다. "
            "automated 가 요건 전체를 덮는다는 뜻은 아니다."
        ),
        "automation_definition": {
            "automated": "하니스에 실행 가능한 통제가 존재하고 근거 파일이 실재함 (evidence 1건 이상 필수)",
            "manual": "하니스에 통제가 없어 사람 검토로 남김 (note 필수, evidence 0건)",
            "out_of_scope": "은행 8부문 적합성검증 범위 밖 (note 필수, evidence 0건)",
        },
        "sections": SECTIONS,
        "lenses": list(LENSES),
        "criteria": items,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="harness/domain_requirement_criteria.json")
    args = ap.parse_args(argv)
    data = build()
    Path(args.out).write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    n = len(data["criteria"])
    auto = sum(1 for c in data["criteria"] if c["automation"] == "automated")
    print(f"{args.out}: 기준 항목 {n}건 (automated {auto})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
