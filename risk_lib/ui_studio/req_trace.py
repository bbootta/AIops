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
    "AIG-006": ("반영", (("table", "ui_field_policy"),
                        ("table", "aig_redaction_rule"),
                        ("module", "risk_lib.aig.trace"),
                        ("test", "test_masked_field_condition_is_blocked_on_screen")),
                "필드 마스킹·집계최소단위 + 전송 마스킹 규칙 원장(aig_redaction_rule)"),
    "AIG-007": ("부분", (("table", "agent_activity"),
                        ("table", "aig_agent_trace"),
                        ("module", "risk_lib.aig.trace")),
                "도구호출·출력 두 구간을 지문·사슬로 잇는 전구간 로그가 있다. "
                "프롬프트 본문은 비어 있다 — 이 저장소의 산출은 언어모형을 "
                "호출하지 않아 오간 본문이 존재하지 않는다"),
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
    "DAT-001": ("반영", (("module", "risk_lib.datamodel.catalog"), ("screen", "데이터모델"),
                        ("test", "test_architecture_doc_table_and_column_counts_match_the_catalog")),
                "정규 테이블 전건이 입도·기본키·단위·근거를 스펙으로 선언한다. "
                "장수·컬럼수는 ARCHITECTURE.md와 검사로 묶여 있어 여기 적지 않는다"),
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
                "결정론 엔진 + 자체검증 57건 + 서식검증 1,735건"),
    "GOV-004": ("반영", (("module", "risk_lib.governance.model_lifecycle"),
                        ("table", "gov_model_stage"), ("table", "gov_model_state"),
                        ("table", "gov_model_transition"),
                        ("test", "test_production_models_without_approval_evidence_are_flagged")),
                "모형 인벤토리 + 단계·상태·전이 원장. 승인 증빙 없는 운영 모형이 "
                "전이 판정에서 걸린다"),
    "GOV-005": ("반영", (("table", "st_calc_trace"), ("screen", "위기상황")),
                "14축 동시 충격 · 전 단계 추적표 · 경로-추적 일치"),
    "GOV-006": ("부분", (("table", "mkt_ipv"), ("table", "mkt_backtest_exception"),
                        ("table", "gov_pricing_control"),
                        ("table", "gov_pricing_result"),
                        ("test", "test_ipv_adapter_uses_notional_coverage")),
                "통제 5종 대장과 판정·미비 원장이 섰고 IPV 커버리지 관측이 공표 "
                "원장에서 온다. 관측이 금리 데스크 한 곳뿐이고 PLA·재현 통제는 "
                "실행 기록이 없어 '미실시'로 남는다"),
    "GOV-007": ("반영", (("table", "agent_registry"), ("table", "agent_killswitch")), ""),
    "GOV-008": ("부분", (("table", "chg_change_request"), ("table", "chg_regression_test"),
                        ("table", "gov_change_policy"), ("table", "gov_change_gate"),
                        ("test", "test_top_tier_regulation_change_requires_all_five_steps")),
                "변경 유형×위험등급별 필수 5단계 정책표와 fail-closed 배포 게이트가 "
                "있으나 **변경요청 접수 경로가 배선되지 않아 요청·영향·통제 원장이 "
                "비어 있다.** 배포 자동화는 하지 않는다(설계상)"),
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
    "PLT-014": ("반영", (("screen", "검증"), ("table", "gov_unified_run"),
                        ("table", "gov_run_domain"),
                        ("test", "test_unified_run_flags_missing_domains")),
                "실행 하나가 전 도메인을 덮는지 원장이 판정한다 — 미산출 도메인과 "
                "다른 run_id 혼입이 문제 목록으로 나온다"),
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
    "BNK-CRE-006": ("반영", (("module", "risk_lib.regulatory.provenance"),
                            ("table", "ecl_pma"), ("table", "ecl_gl_reconciliation"),
                            ("test", "test_reconciliation_without_a_gl_feed_is_not_marked_as_passing")),
                    "IRB–ECL EL 대사 + 모형외조정(PMA) 통제 원장 + 총계정원장 대사. "
                    "GL 피드가 없으면 대사를 통과로 적지 않는다"),
    "BNK-CRM-004": ("반영", (("module", "risk_lib.credit_rating.scorecard"),
                            ("table", "crm_scorecard_param"), ("table", "crm_scorecard_bin"),
                            ("table", "crm_obligor_score"), ("table", "crm_obligor_axis_score"),
                            ("test", "test_score_scale_is_a_linear_transform_that_leaves_pd_unchanged")),
                    "WOE 구간·모수·차주 점수·축 결합 원장. 점수 척도 변환이 PD를 "
                    "바꾸지 않는 것을 검사가 고정한다"),
    "BNK-CRM-009": ("반영", (("table", "crm_ews_signal"), ("screen", "조기경보"),
                            ("table", "crm_override"), ("table", "crm_override_reason"),
                            ("table", "crm_override_performance"),
                            ("test", "test_override_performance_counts_unapproved_changes")),
                    "EWS 신호·단계 + 등급변경 사유·범위 판정·사후성과 원장"),
    "BNK-OTH-001": ("반영", (("table", "opr_loss_event"), ("table", "opr_kri")),
                    "손실·KRI·PSMOR 원칙 매핑"),
    "BNK-OTH-002": ("반영", (("module", "risk_lib.ccr"), ("module", "risk_lib.frtb")),
                    "SA-CCR·CVA·FRTB·XVA·Greeks"),
    # 재평가(이번 회차). 직전 판정의 근거였던 "KRW 충격 모수가 비어 USD 프록시를
    # 쓴다"는 상태가 해소됐다. 현행 원문([별표 9-1] 개정 2026.1.29 · BCBS d578)을
    # 확보해 KRW 225/350/225가 원문확인으로 적재됐고, 파이프라인 헤드라인 계정이
    # 폐지된 d368_2016에서 별표9의1_2026으로 옮겨졌다. 제12항 다 충격후 하한 0,
    # 제13항 다 통화 간 상계 금지, 제21항 나 기본자본 15% 아웃라이어가 모두 산출에
    # 걸려 있고, 국내 고유 요건(제8항 비만기성예금 범주·제9~10항 행동옵션 범위·
    # 제15~20항 관리체계)과 제22항 공시서식 <표6>·<표7>이 원장으로 선다.
    #
    # 그래도 '반영'이 아니다. 제11항 자동금리옵션 리스크가 산출되지 않는다.
    # 옵션 인벤토리 원천이 없어 계수 원장만 있고 재평가가 없으며, ΔEVE는 그
    # add-on을 뺀 값이다. 기본 조기상환율·중도해지율도 규정이 값을 주지 않아
    # 자체추정이다. 두 공백이 ΔEVE 절대수준에 남아 있으므로 부분이다.
    "BNK-OTH-003": ("부분", (("module", "risk_lib.alm.cashflow"),
                            ("table", "alm_cashflow_bucket"),
                            ("table", "alm_irrbb_result"),
                            ("table", "alm_rate_shock_param"),
                            ("table", "kr_nmd_category"),
                            ("table", "kr_retail_behavioural_scope"),
                            ("table", "kr_irrbb_governance"),
                            ("table", "disc_irrbb_table6"),
                            ("test", "test_domestic_post_shock_floor_is_zero_and_binds"),
                            ("test", "test_outlier_verdict_is_made_against_the_tier1_threshold")),
                    "국내기준([별표 9-1] 개정 2026.1.29)으로 ΔEVE 6시나리오 × "
                    "계약/행동조정 2기준과 ΔNII를 계약 현금흐름에서 산출한다. "
                    "KRW 충격 225/350/225 원문확인 · 충격후 하한 0(제12항 다) · "
                    "통화 간 상계 금지(제13항 다) · 기본자본 15% 아웃라이어"
                    "(제21항 나) 적용. 비만기성예금 범주·행동옵션 범위·관리체계 "
                    "원장과 <표6>·<표7> 공시서식까지 선다. **제11항 자동금리옵션 "
                    "리스크는 옵션 인벤토리 원천이 없어 산출하지 않으며 ΔEVE에 "
                    "빠져 있다.** 기본 조기상환율·중도해지율은 규정 미제시로 "
                    "자체추정이다"),
    "BNK-ST-002": ("반영", (("table", "st_capital_path"),), "기준·악화·심각 3경로"),
    "BNK-ST-003": ("반영", (("table", "st_calc_trace"),), "신용→시장→운영→유동성→손익→자본 전이"),
    "BNK-ST-004": ("반영", (("table", "st_capital_path"), ("screen", "위기상황")), ""),
    "BNK-ST-005": ("반영", (("module", "risk_lib.limits"),
                           ("table", "lim_limit_definition"),
                           ("table", "st_action_playbook"), ("table", "st_management_action"),
                           ("test", "test_playbook_carries_the_source_clause")),
                   "한도 정의가 원장에서 오고(승인기구·근거 포함) 자본경로 위반에 "
                   "발동표가 붙는다"),
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
    "SEC-OAI-001": ("반영", (("table", "opr_loss_event"), ("table", "opr_rcsa_control"),
                            ("table", "opr_rcsa_assessment"), ("table", "opr_rcsa_action"),
                            ("test", "test_rcsa_uses_the_loss_event_vocabulary")),
                    "손실 원장 + RCSA 척도·통제·평가·조치 원장. 사건유형 어휘가 "
                    "손실 원장과 같다"),
    # ---- INT · NFR ---------------------------------------------------------
    "INT-006": ("부분", (("module", "risk_lib.notifications"),), "webhook 발송까지 — 티켓 연계는 없다"),
    "INT-007": ("반영", (("module", "risk_lib.regulatory.forms"),),
                "업무보고서 xlsx · JSON · OpenAPI/GraphQL 스키마"),
    "NFR-009": ("반영", (("module", "risk_lib.repro"),
                        ("test", "test_manifest_records_effective_asof")),
                "seed·asof·코드리비전 고정 · reproduce CLI · 지문 대조"),
    "NFR-011": ("부분", (("test", "test_kill_switch_can_be_cancelled"),),
                "포커스 표시·키보드 경로 일부 — 전면 접근성 검증은 없다"),

    # ---- 감사(2026-08-06)로 매핑을 되찾은 요건 ------------------------------
    # 아래는 구현이 있는데 TRACE에 키가 없어 기본값 '미반영'으로 집계되던 것들이다.
    # 누가 판정해서 미반영이 아니라 **아무도 판정하지 않아서** 미반영이었다.
    "DAT-006": ("반영", (("module", "risk_lib.adjustments"),
                        ("table", "aig_adjustment"),
                        ("screen", "수동조정"),
                        ("test", "test_material_adjustment_needs_senior_approval")),
                "SoD·중요성 임계·유효기간·증빙 통제 + 적용분만 값에 반영"),
    "PLT-015": ("반영", (("table", "gov_alert_policy"),
                        ("test", "test_alert_policy_binds_action_to_every_alert_type")),
                "경보 유형마다 조치·책임자·기한이 원장으로 묶인다"),
    "SEC-PRC-001": ("반영", (("module", "risk_lib.market_data"),
                            ("table", "mkt_risk_factor"),
                            ("test", "test_market_data_page_registered")),
                    "시장데이터 수집·검증·스냅샷 원장"),
    "SEC-PRC-004": ("반영", (("module", "risk_lib.market_data"),
                            ("test", "test_vol_surface_fits_within_tolerance")),
                    "무이표커브 부트스트랩 + 변동성면 캘리브레이션 + 무차익 검사"),
    "BNK-ST-006": ("반영", (("module", "risk_lib.stress.reverse"),
                           ("screen", "역스트레스"),
                           ("test", "test_reverse_stress_hits_target")),
                   "임계 심도 역산 + 다축 역스트레스 + 구속 축 식별"),
    "BNK-CRM-001": ("반영", (("module", "risk_lib.model_inventory"),
                            ("table", "crm_model"),
                            ("test", "test_crm_model_inventory_matches_source")),
                    "모형 인벤토리·소유자·검증주기·상태 원장"),
    # 플랫폼 우산 요건 3건은 구성요소가 상당히 있으나 요건 전체를 덮지는 않는다.
    # '반영'으로 올리면 감사에서 드러난 과대표시를 되풀이하는 것이다.
    "PLT-002": ("부분", (("module", "risk_lib.datamodel.catalog"),
                        ("table", "rdm_obligor"), ("table", "dat_mart_load"),
                        ("table", "dat_retention_policy"),
                        ("test", "test_retention_ledgers_match_their_specs")),
                "정규 원장·스펙 검증과 실행별 적재 이력·보존 정책·폐기 판정 원장이 "
                "있다. 별도 Data Mart 저장소는 없고 적재 이력은 실행이 실은 원장의 "
                "행수·지문 기록이다"),
    "PLT-004": ("부분", (("module", "risk_lib.pipeline"),
                        ("module", "risk_lib.validation.backtest")),
                "결정론 계산엔진 5종 + 검증 Lab은 있으나 사용자 정의 계산은 없다"),
    "PLT-005": ("부분", (("module", "risk_lib.stress.reverse"),
                        ("module", "risk_lib.market_data"),
                        ("module", "risk_lib.frtb")),
                "시나리오·역스트레스·프라이싱 엔진은 있으나 시나리오 저작 UI는 없다"),
    # rynta.py 커버리지 표가 covered로 적고 있던 4건 — 두 표가 어긋나 있었다.
    # 증빙 실재를 확인하고 여기로 옮긴다. 우산 요건 두 건은 '부분'이 정확하다.
    "BNK-CRM-005": ("부분", (("module", "risk_lib.models.discrimination"),
                            ("module", "risk_lib.validation.backtest"),
                            ("test", "test_pd_backtest_report_structure")),
                    "변별력(Gini·KS)·안정성(PSI)·백테스트는 있으나 등급전략 연계는 없다"),
    "BNK-CRM-008": ("반영", (("module", "risk_lib.models.rating"),
                            ("test", "test_crm_rating_grades_come_from_master_scale")),
                    "17등급 master scale + PD 구간 매핑 — 등급열은 문자열로 실체화된다"),
    "SEC-LIQ-002": ("부분", (("module", "risk_lib.alm.liquidity"),
                            ("table", "alm_survival_path"),
                            ("table", "alm_liquidity_stress_param"),
                            ("test", "test_liquidity_stress_scenarios")),
                    "만기 사다리·생존기간 경로를 현금흐름 원장에서 산출한다. "
                    "시장전반 시나리오는 유출률 미공표로 **미산출**이고, "
                    "목표 생존기간·CFP 트리거는 이사회 승인 원장이 없어 "
                    "산출만 하고 판정하지 않는다"),
    "SEC-OAI-002": ("부분", (("module", "risk_lib.model_inventory"),
                            ("module", "risk_lib.model_risk"),
                            ("test", "test_crm_model_inventory_matches_source")),
                    "모형 인벤토리·모형위험 등급은 있으나 증권 고유 거버넌스 축은 없다"),
    # 이번 시정(2026-08-06)으로 상태가 움직인 둘.
    "BNK-ST-001": ("부분", (("module", "risk_lib.icaap.economic_capital"),
                           ("table", "icaap_risk_taxonomy"), ("table", "icaap_materiality"),
                           ("table", "icaap_capital_map"),
                           ("test", "test_ec_covers_every_credit_rwa_component")),
                   "리스크 11종 인벤토리 × 3축 중요성 판정 × 내부자본 매핑 + "
                   "신용(SA·IRB·구조화·CCR)·시장·운영·IRRBB 경제자본. 기후는 EC로 "
                   "환산하지 않았다 — BNK-OTH-004 참조"),
    "BNK-OTH-004": ("부분", (("module", "risk_lib.stress.climate_capital"),),
                    "NGFS 3시나리오×7시점 CET1 경로는 산출하나 **경제자본으로 "
                    "환산하지 않는다** — 환산 방법론이 정해지지 않았다. 전략·평판은 없다"),

    # ---- 이번 회차(2026-08-10) 배선으로 판정이 바뀐 요건 --------------------
    # 원장이 서고 산출 경로에 연결됐다. 판정 근거는 원장 실재가 아니라
    # **실행이 그 원장을 실제로 만든다**는 것이며, 카탈로그 등재와
    # `test_every_catalog_table_is_materialized_or_declared`가 그것을 고정한다.
    "DAT-008": ("부분", (("table", "dat_retention_policy"),
                        ("table", "dat_retention_action"),
                        ("test", "test_disposal_is_not_decided_without_a_confirmed_retention_period")),
                "데이터 구분별 보존기간·보관 세대수 정책과 폐기 판정 원장. "
                "보존기간이 확정되지 않은 구분은 '판정불가'로 남는다. "
                "비식별 처리 자체는 구현하지 않았다"),
    "BNK-CRM-002": ("반영", (("module", "risk_lib.credit_rating.requirements"),
                            ("table", "crm_rating_requirement"),
                            ("table", "crm_lifecycle_event"),
                            ("table", "crm_lifecycle_compliance"),
                            ("test", "test_lifecycle_deadline_follows_the_requirement_ledger")),
                    "신용평가시스템 최소요건 원장과 개발·승인·재개발 생애주기 "
                    "기한 판정. 기한은 요건 원장에서 오고 소스에 없다"),
    "BNK-CRM-003": ("부분", (("table", "crm_dev_sample"),
                            ("table", "crm_sample_representativeness"),
                            ("test", "test_dev_sample_fails_the_five_year_observation_requirement")),
                    "개발표본·부도정의·대표성 판정 원장. 요건 행이 없으면 판정하지 "
                    "않는다. 실제 은행 표본이 아니라 합성 표본이다"),
    "BNK-CRM-006": ("반영", (("table", "crm_scorecard_factor"),
                            ("module", "risk_lib.credit_rating.scorecard"),
                            ("test", "test_scorecard_separates_defaulters")),
                    "기업 재무 4변수 WOE 스코어카드"),
    "BNK-CRM-007": ("반영", (("table", "crm_qualitative_item"),
                            ("table", "crm_qualitative_assessment"),
                            ("test", "test_qualitative_axes_are_used_in_the_scorecard")),
                    "비재무 6항목 평가와 축 결합. 척도를 벗어난 평가는 걸린다"),
    "SEC-CCR-003": ("부분", (("table", "ccr_csa_term"),
                            ("table", "ccr_collateral_position"),
                            ("table", "ccr_margin_call"), ("table", "ccr_margin_dispute"),
                            ("test", "test_margin_ledgers_match_specs_and_references")),
                    "CSA 조건·담보 포지션·마진콜·분쟁 원장. 감독 담보조정계수를 "
                    "확인하지 못해 조정을 적용하지 않고 그 사실을 경고로 남긴다 — "
                    "담보가치가 과대평가되고 콜 금액이 과소산출된다"),
    "SEC-LIQ-001": ("부분", (("table", "liq_funding_trade"), ("table", "liq_funding_ladder"),
                            ("table", "liq_funding_concentration"),
                            ("table", "liq_funding_limit"),
                            ("test", "test_funding_limits_are_not_judged_without_a_threshold")),
                    "단기조달 거래·사다리·집중도·한도 원장. 콜차입 한도 조문을 "
                    "열람하지 못했고 나머지 3종은 이사회 승인 내부한도 원장이 없어 "
                    "임계 4건이 NULL이며 판정하지 않는다"),
    "SEC-OAI-003": ("반영", (("table", "opr_close_task"), ("table", "opr_close_gate"),
                            ("test", "test_close_gate_blocks_a_step_whose_predecessor_is_incomplete")),
                    "마감 단계·게이트 원장. 단계 완료 여부를 플래그가 아니라 증빙 "
                    "원장의 행수로 판정하고, 선행 미완이면 차단한다"),
    "SEC-PRC-002": ("반영", (("table", "mkt_product"), ("table", "mkt_pricing_model"),
                            ("table", "mkt_product_model_map"),
                            ("test", "test_product_without_an_approved_official_model_cannot_be_priced")),
                    "상품·평가모형·매핑 원장. 승인된 공식평가 모형이 없는 상품은 "
                    "'평가불가'로 판정된다"),
    "INT-001": ("부분", (("table", "int_connector"), ("table", "int_connector_operation"),
                        ("table", "int_connector_violation"),
                        ("test", "test_every_registered_connector_is_read_only")),
                "커넥터 등록부와 조회전용 판정. 쓰기 동사·미등록·미승인 3종 위반을 "
                "잡는다. **연결 상태는 전건 '미연결'이다** — 이 저장소는 외부 "
                "시스템과 통신하지 않는다"),
    "INT-002": ("부분", (("table", "int_inbound_contract"), ("table", "int_inbound_delivery"),
                        ("test", "test_feed_without_a_contract_is_not_passed_through")),
                "수신 계약과 스키마·기준일·sha256 체크섬 판정. 커넥터가 미연결이라 "
                "전 피드가 '미수신'으로 남으며, 미수신도 수신 결과로 기록된다"),
    "INT-003": ("반영", (("table", "int_engine_adapter"), ("table", "int_engine_io"),
                        ("test", "test_adapters_satisfy_the_protocol")),
                "계산엔진 5종의 입출력 선언과 실행가능성 판정"),
    "INT-004": ("부분", (("table", "int_market_feed"), ("table", "int_feed_health"),
                        ("table", "int_feed_field_map"),
                        ("test", "test_synthetic_fallback_is_labelled_as_synthetic")),
                "시장데이터 피드 등록부·필드 매핑·건강도 원장. 전건 미연결이며 "
                "합성 대체분은 출처가 '합성'으로 찍히고 상태가 '정상'이 되지 않는다"),
    "INT-008": ("반영", (("table", "int_retry_policy"), ("table", "int_delivery_attempt"),
                        ("table", "int_quarantine"),
                        ("test", "test_idempotency_key_is_stable_and_content_sensitive")),
                "내용 지문을 포함한 sha256 멱등키·지수 백오프·격리. 정책에 없는 "
                "연계 유형은 재시도하지 않고 즉시 격리한다"),
    "NFR-003": ("반영", (("module", "risk_lib.governance.rbac"),
                        ("table", "gov_role"), ("table", "gov_role_permission"),
                        ("table", "gov_user_role"), ("table", "gov_sod_conflict"),
                        ("table", "gov_access_decision"),
                        ("test", "test_rbac_ledgers_match_their_specs")),
                "역할·권한·부여·직무분리 충돌·접근판정 원장. 권한 행이 없으면 "
                "거부다"),
    "NFR-004": ("반영", (("module", "risk_lib.governance.audit_chain"),
                        ("table", "gov_audit_chain"),
                        ("test", "test_editing_any_field_breaks_the_chain")),
                "승인·수동조정·접근판정·검증·산출 사건을 sha256 prev_hash로 잇는다. "
                "변조·삭제가 체인 검증에서 드러난다"),
}

# 아직 판정하지 않은 요건 — id → 사유.
#
# 예전에는 TRACE에 없으면 조용히 '미반영'이 됐다. 그러면 "판정해서 미반영"과
# "아무도 안 봐서 미반영"이 같은 칸에 들어가고, 실제로 구현이 있는 9건이 그렇게
# 묻혀 있었다(2026-08-06 감사). 이제 모든 요건은 TRACE 아니면 여기에 있어야 하고,
# `test_every_requirement_is_either_traced_or_declared_unassessed`가 그것을 강제한다.
# 사유는 요건별로 쓴다 — 공통 문구를 복사하면 이 목록이 다시 무의미해진다.
UNASSESSED: dict[str, str] = {
    "AIG-010": "LLM·모델 변경관리 — 모형 인벤토리는 있으나 LLM 판올림 절차는 미검토",
    "RDM-001": "유연한 원천 수집·등록 — 합성 생성기만 있고 원천 등록 경로 미검토",
    "RDM-002": "집계·가공 Rule Studio — 규칙이 코드에 있고 사용자 저작 경로 없음",



    # 플랫폼·비기능·연계 — 이 저장소는 산출 라이브러리라 상당수가 범위 밖이다.
    # 범위 밖이라는 판단 자체도 판정이므로 숨기지 않고 여기 적는다.
    "PLT-001": "Secure Connectors — 외부 연계 계층이 이 저장소에 없다",
    "PLT-003": "Evidence & Knowledge — 증빙 원장은 있으나 지식베이스 계층 없음",
    "PLT-006": "RAG & Agentic — 검색·생성 계층이 이 저장소에 없다",
    "PLT-007": "Control & Observability — Kill Switch·감사추적은 있으나 관측 계층 없음",
    "PLT-008": "Reporting & Lifecycle — 보고서 산출은 있으나 배포 수명주기 없음",
    "INT-005": "IAM·SSO 연계 — 인증 계층 범위 밖",
    "NFR-001": "배포모델 — 배포 형상이 정의되지 않았다",
    "NFR-002": "암호화·키관리 — 저장·전송 암호화 계층 범위 밖",
    "NFR-005": "성능·처리량 — 성능 목표·측정 없음",
    "NFR-006": "가용성·복구 — 운영 인프라 범위 밖",
    "NFR-007": "확장성 — 운영 인프라 범위 밖",
    "NFR-008": "Observability — 메트릭·트레이싱 계층 없음",
    "NFR-010": "보안검증 — 취약점 점검 절차 없음",
    "NFR-012": "변경·배포·Rollback — 화면 롤백은 있으나 배포 롤백 없음",

    "COM-001": "고객·계약 가정 — 사업 모델 요건, 산출 하네스 범위 밖",
    "COM-002": "순구축대가 산정 — 사업 모델 요건, 범위 밖",
    "COM-003": "ARR·Lifecycle·1년차·TCO — 사업 모델 요건, 범위 밖",
    "COM-004": "패키지 Preset — 사업 모델 요건, 범위 밖",
    "COM-005": "Lifecycle 요율 — 사업 모델 요건, 범위 밖",
    "COM-006": "가격 승인·가정 표시 — 사업 모델 요건, 범위 밖",
    "COM-007": "ROI 이중계상 방지 — 사업 모델 요건, 범위 밖",
    "COM-008": "GTM Funnel 관리 — 사업 모델 요건, 범위 밖",
}

STATUSES = ("반영", "부분", "미반영")


def build_trace() -> list[dict]:
    """레지스터 131건 전부에 상태를 붙인다.

    TRACE에 없으면 여전히 '미반영'이지만, 이제 그 사유가 UNASSESSED에서 note로
    따라붙는다. 사유가 비어 있는 미반영은 "아무도 판정하지 않았다"는 뜻이고
    테스트가 그 상태를 허용하지 않는다.
    """
    out = []
    for rid, title, sector, priority, n_ac in REQUIREMENTS:
        status, evidence, note = TRACE.get(
            rid, ("미반영", (), UNASSESSED.get(rid, "")))
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
