"""v9.6.0 업무요건 ↔ 이 하네스 구현의 추적 — 증빙이 있어야 '반영'이다.

원칙 세 가지.

1. **증빙 없는 반영 표시는 없다.** 상태가 반영/부분이려면 실재하는 증빙
   (모듈·원장 테이블·화면 구획·테스트) 참조가 최소 1건 있어야 하고,
   그 참조는 tests/test_req_trace.py 가 실재를 검증한다 — 문서가 코드와
   갈라지는 유형(F-501 계열)을 요건 추적에서도 막는다.
2. **미반영을 숨기지 않는다.** 매핑되지 않은 요건은 전부 '미반영'으로
   집계돼 화면에 그대로 뜬다. 커버리지는 자랑이 아니라 재고조사다.
3. **부분은 부분이라고 쓴다.** 무엇이 되고 무엇이 안 되는지 note 에 적는다.

증빙 kind:
  module — risk_lib 모듈 경로 (import 가능해야 함)
  table  — 정규 원장 테이블명 (카탈로그에 있어야 함)
  screen — 에이전틱 UI 구획 라벨 (app._JS 안에 문자열로 있어야 함)
  test   — tests/ 아래 테스트 함수명 (파일에서 검색돼야 함)
"""

from __future__ import annotations

from risk_lib.regulatory.requirements_v960 import (
    REQUIREMENTS, SOURCE, SOURCE_SHA256,
)

# 상태: 반영 · 부분 · 미반영 (매핑에 없으면 미반영)
# 형식: id → (상태, ((kind, ref), …), note)
TRACE: dict[str, tuple[str, tuple[tuple[str, str], ...], str]] = {
    # ---- AIG · AI 거버넌스 -------------------------------------------------
    "AIG-001": ("반영", (("table", "agent_registry"),
                        ("test", "test_agent_registry_has_risk_tiers")),
                "위험등급 상·중·하 — 규칙 기반 분류 (규제 산출=상)"),
    "AIG-002": ("반영", (("table", "agent_registry"),
                        ("test", "test_no_agent_has_operational_write_permission")),
                "전 에이전트 write_allowed=false — NO AUTONOMOUS WRITE"),
    "AIG-003": ("반영", (("table", "ui_layout_proposal"), ("module", "risk_lib.ui_studio.layout")),
                "레이아웃·조회는 제안 전용, 판단을 확정하지 않는다"),
    "AIG-004": ("반영", (("screen", "승인 적용"), ("test", "test_approve_then_rollback_round_trip")),
                "승인 전 화면 미반영 + Rollback"),
    "AIG-005": ("반영", (("table", "agent_registry"), ("screen", "에이전트 레지스트리 · 최소 권한")),
                "도구 목록·권한이 원장으로 열거된다"),
    "AIG-006": ("부분", (("table", "ui_field_policy"),
                        ("test", "test_masked_field_condition_is_blocked_on_screen")),
                "필드 마스킹·집계최소단위는 있으나 전송 DLP는 없다"),
    "AIG-007": ("부분", (("table", "agent_activity"),),
                "활동 원장은 있으나 프롬프트 전문 로그는 데모 수준"),
    "AIG-008": ("반영", (("test", "test_engine_js_is_inlined_by_the_renderer"),
                        ("module", "risk_lib.validation.consistency")),
                "회귀 스위트 1,000+건 · 구조/인용 기준선 · 엔진 패리티"),
    "AIG-009": ("반영", (("screen", "Kill Switch"),
                        ("test", "test_kill_switch_stops_new_queries_without_any_dialog")),
                "사유 필수·대화상자 무의존·비정형 UI까지 차단"),
    "AIG-011": ("반영", (("screen", "3선이 도전해야 할 가정"), ("module", "risk_lib.validation.independent")),
                "라인별 산식·인용 + 요청서에 가정·한계 29건 생성 공시"),
    "AIG-012": ("반영", (("table", "gov_approval"), ("module", "risk_lib.validation.independent")),
                "4-Eyes + fail-closed 독립검증 게이트 + 조건부 결재 기록"),
    # ---- RDM ---------------------------------------------------------------
    "RDM-003": ("반영", (("table", "rdm_canonical_map"), ("table", "rdm_source_contract")), ""),
    "RDM-004": ("반영", (("table", "rdm_dq_result"), ("module", "risk_lib.datamodel.decompose")), ""),
    "RDM-005": ("반영", (("table", "rdm_reconciliation"), ("module", "risk_lib.regulatory.cross_form")),
                "원천–산출 대사 + 서식 간 교차 대사 9종"),
    "RDM-006": ("부분", (("table", "gov_evidence_node"), ("module", "risk_lib.archive")),
                "증빙 계보 7단계·판별 보관은 있으나 필드 단위 계보는 없다"),
    "RDM-007": ("반영", (("table", "gov_exception_action"),
                        ("screen", "예외·조치 워크플로")),
                "대사·DQ·IPV 예외가 표준 조치·담당·기한이 붙은 큐로 모인다"),
    "RDM-008": ("반영", (("module", "risk_lib.ui_studio.nl_query"),
                        ("test", "test_typing_recompiles_the_plan_and_changes_results")),
                "권한·마스킹·집계최소단위를 통과해야 조건이 된다"),
    # ---- DAT ---------------------------------------------------------------
    "DAT-001": ("반영", (("module", "risk_lib.datamodel.catalog"), ("screen", "데이터모델")),
                "정규 테이블 81장 · 컬럼 596개 · 입도 서술"),
    "DAT-002": ("반영", (("module", "risk_lib.archive"), ("screen", "기준일")),
                "기준일자/수행일자·판 체계 + 화면 기준일 전환"),
    "DAT-003": ("부분", (("table", "gov_evidence_node"), ("table", "gov_evidence_edge")),
                "실행 단위 계보 7단계 — 필드 단위는 아니다"),
    "DAT-004": ("반영", (("table", "rdm_snapshot"),
                        ("module", "risk_lib.archive")),
                "원천 스냅샷 원장 + 판별 보관·지문"),
    "DAT-005": ("반영", (("table", "rdm_dq_result"),), ""),
    "DAT-007": ("반영", (("table", "rdm_reconciliation"),
                        ("test", "test_forms_build_when_the_month_has_no_elapsed_business_day")), ""),
    # ---- GOV ---------------------------------------------------------------
    "GOV-001": ("반영", (("module", "risk_lib.repro"), ("test", "test_manifest_records_effective_asof")),
                "seed·asof 고정 + manifest 재현"),
    "GOV-002": ("반영", (("table", "rdm_dq_result"), ("table", "gov_evidence_edge")), ""),
    "GOV-003": ("반영", (("module", "risk_lib.pipeline"), ("module", "risk_lib.validation.consistency")),
                "결정론 엔진 + 자체검증 54건 + 서식검증 1,735건"),
    "GOV-004": ("부분", (("module", "risk_lib.models.rating"), ("table", "crm_model")),
                "PD/LGD 모형·백테스트는 있으나 승인 라이프사이클은 없다"),
    "GOV-005": ("반영", (("table", "st_calc_trace"), ("screen", "E 위기상황")),
                "14축 동시 충격 · 전 단계 추적표 · 경로-추적 일치"),
    "GOV-006": ("부분", (("table", "mkt_ipv"), ("table", "mkt_backtest_exception")),
                "IPV·백테스트·가격회귀는 있으나 승인 정책 연결은 없다"),
    "GOV-007": ("반영", (("table", "agent_registry"), ("table", "agent_killswitch")), ""),
    "GOV-008": ("부분", (("table", "chg_change_request"), ("table", "chg_regression_test")),
                "변경 팩토리 원장 — 배포 자동화는 하지 않는다(설계상)"),
    "GOV-009": ("반영", (("table", "gov_evidence_node"), ("module", "risk_lib.archive")),
                "증빙 계보 + MANIFEST SHA-256 + 판별 보관"),
    # ---- PLT · 에이전틱 UI -------------------------------------------------
    "PLT-009": ("반영", (("module", "risk_lib.ui_studio.nl_query"),
                        ("test", "test_query_hash_changes_with_the_sentence")), ""),
    "PLT-010": ("반영", (("screen", "정형 조회"), ("table", "ui_view")), ""),
    "PLT-011": ("반영", (("screen", "비정형 UI"), ("module", "risk_lib.ui_studio.layout")), ""),
    "PLT-012": ("반영", (("screen", "미리보기 생성"),
                        ("test", "test_approve_then_rollback_round_trip")), ""),
    "PLT-013": ("반영", (("test", "test_rejected_prompt_shows_the_reason_and_blocks_approval"),
                        ("table", "ui_field_policy")), ""),
    "PLT-014": ("부분", (("screen", "F 검증"),),
                "실행 단일 컨텍스트(run_id·지문)는 있으나 통합 알림 런은 없다"),
    "PLT-016": ("반영", (("screen", "killscope"),
                        ("test", "test_scoped_kill_only_stops_its_domain")),
                "범위형 정지 — 부문 정지 시 다른 부문 조회는 산다"),
    "PLT-017": ("반영", (("table", "gov_approval"),
                        ("test", "test_approvals_enforce_segregation_of_duties")), ""),
    "PLT-018": ("반영", (("screen", "단계를 누르면 상세"),
                        ("module", "risk_lib.archive")),
                "증빙 노드 드릴다운 + 실행 간 지문 대조"),
    # ---- BNK ---------------------------------------------------------------
    "BNK-CAP-001": ("반영", (("module", "risk_lib.capital.bis"), ("table", "cap_stack")), ""),
    "BNK-CAP-002": ("반영", (("module", "risk_lib.performance"),), "RAROC·경제자본·허들"),
    "BNK-CRE-001": ("반영", (("module", "risk_lib.models.rating"), ("table", "crm_pd_calibration")), ""),
    "BNK-CRE-002": ("반영", (("module", "risk_lib.capital.rwa_sa"), ("table", "rwa_sa_bucket")),
                    "SA + IRB + output floor"),
    "BNK-CRE-003": ("반영", (("module", "risk_lib.capital.crm"), ("table", "rdm_collateral")), ""),
    "BNK-CRE-004": ("반영", (("table", "ecl_result"),), "3-stage · SICR 트리거"),
    "BNK-CRE-005": ("반영", (("module", "risk_lib.provisioning"),), ""),
    "BNK-CRE-006": ("부분", (("module", "risk_lib.regulatory.provenance"),),
                    "IRB–ECL EL 대사는 있으나 PMA·GL 연결은 없다"),
    "BNK-CRM-004": ("부분", (("module", "risk_lib.models.rating"),),
                    "로지스틱 PD·등급화는 있으나 CSS 스코어카드 전주기는 없다"),
    "BNK-CRM-009": ("부분", (("table", "crm_ews_signal"), ("screen", "조기경보")),
                    "EWS 신호·단계는 있으나 Override 원장은 없다"),
    "BNK-OTH-001": ("반영", (("table", "opr_loss_event"), ("table", "opr_kri")),
                    "손실·KRI·PSMOR 원칙 매핑"),
    "BNK-OTH-002": ("반영", (("module", "risk_lib.ccr"), ("module", "risk_lib.frtb")),
                    "SA-CCR·CVA·FRTB·XVA·Greeks"),
    "BNK-OTH-003": ("반영", (("module", "risk_lib.alm"), ("table", "alm_lcr_item")),
                    "IRRBB·LCR·NSFR"),
    "BNK-ST-002": ("반영", (("table", "st_capital_path"),), "기준·악화·심각 3경로"),
    "BNK-ST-003": ("반영", (("table", "st_calc_trace"),), "신용→시장→운영→유동성→손익→자본 전이"),
    "BNK-ST-004": ("반영", (("table", "st_capital_path"), ("screen", "E 위기상황")), ""),
    "BNK-ST-005": ("부분", (("module", "risk_lib.limits"),),
                   "한도 엔진·위반 경보는 있으나 경영조치 연결은 없다"),
    "BNK-ST-007": ("반영", (("table", "st_calc_trace"),
                           ("test", "test_stress_screen_shows_every_calculation_block")), ""),
    # ---- SEC ---------------------------------------------------------------
    "SEC-NCR-001": ("부분", (("table", "pru_prompt_action"),), "적기시정조치 트리거까지"),
    "SEC-NCR-002": ("반영", (("module", "risk_lib.ncr"),), "영업용순자본"),
    "SEC-NCR-003": ("반영", (("module", "risk_lib.ncr"),), "총위험액"),
    "SEC-NCR-004": ("반영", (("table", "pru_liquidity_ratio"),), "전월·공시 대사"),
    "SEC-MKT-001": ("반영", (("table", "mkt_var_es"), ("table", "mkt_backtest_exception")), ""),
    "SEC-MKT-002": ("반영", (("module", "risk_lib.frtb"),), "민감도·FRTB SA/IMA"),
    "SEC-MKT-003": ("반영", (("module", "risk_lib.attribution"),
                            ("module", "risk_lib.limits")),
                    "P&L attribution + 다차원 한도 엔진"),
    "SEC-CCR-001": ("반영", (("module", "risk_lib.ccr"),), "netting·담보·SA-CCR EAD"),
    "SEC-CCR-002": ("반영", (("module", "risk_lib.ccr"),), "CVA·DVA·FVA·ColVA·MVA"),
    "SEC-PRC-003": ("반영", (("module", "risk_lib.ipv"),), "가격·Greeks 회귀"),
    "SEC-PRC-005": ("반영", (("table", "mkt_ipv"), ("screen", "독립가격검증")), ""),
    "SEC-OAI-001": ("부분", (("table", "opr_loss_event"),), "손실 원장 — RCSA는 없다"),
    # ---- INT · NFR ---------------------------------------------------------
    "INT-006": ("부분", (("module", "risk_lib.notifications"),), "webhook 발송까지 — 티켓 연계는 없다"),
    "INT-007": ("반영", (("module", "risk_lib.regulatory.forms"),),
                "업무보고서 xlsx · JSON · OpenAPI/GraphQL 스키마"),
    "NFR-009": ("반영", (("module", "risk_lib.repro"),
                        ("test", "test_manifest_records_effective_asof")),
                "seed·asof·코드리비전 고정 · reproduce CLI · 지문 대조"),
    "NFR-011": ("부분", (("test", "test_kill_switch_can_be_cancelled"),),
                "포커스 표시·키보드 경로 일부 — 전면 접근성 검증은 없다"),
}

STATUSES = ("반영", "부분", "미반영")


def build_trace() -> list[dict]:
    """레지스터 131건 전부에 상태를 붙인다 — 매핑에 없으면 미반영이다."""
    out = []
    for rid, title, sector, priority, n_ac in REQUIREMENTS:
        status, evidence, note = TRACE.get(rid, ("미반영", (), ""))
        out.append({
            "id": rid, "title": title, "sector": sector,
            "priority": priority, "n_ac": n_ac,
            "status": status,
            "evidence": [{"kind": k, "ref": r} for k, r in evidence],
            "note": note,
        })
    return out


def coverage() -> dict:
    rows = build_trace()
    by = {s: sum(1 for r in rows if r["status"] == s) for s in STATUSES}
    return {
        "source": SOURCE, "source_sha256": SOURCE_SHA256,
        "n": len(rows), **by,
        "n_evidence": sum(len(r["evidence"]) for r in rows),
    }
